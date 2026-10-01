"""Synthetic selector contracts; no study cohorts or held-out predictions."""
import copy
from dataclasses import replace
import json
import math
import unittest

from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess, V2Problem
from hybridguard_agent.research.rule_learning_v2.semantic_selection import (
    greedy_semantic, retain_semantic, semantic_catalog,
)

LANG = "app.web_data.navigator_layer.language"
LANGS = "app.web_data.navigator_layer.languages"
WD = "app.web_data.automation_surface_layer.webdriver"


def control(name, field=None, group=None, threshold=1):
    return Atom(name, "family:" + (field or name), ("app_web67",), ("SYNTHETIC",), (name,),
                "CONTROL_LE", {"field": field or "fixture." + name, "threshold": threshold,
                               "signal_group": group or name})


def saved(name="new", webdriver=False):
    field = WD if webdriver else LANGS
    return Atom(name, "family:" + field, ("app_web67",), ("SYNTHETIC",), (name,),
                "SAVED_SEMANTIC_STATE", {
                    "field": field, "field_refs": [WD] if webdriver else [LANG, LANGS],
                    "signal_group": "automation_flag" if webdriver else "language_preferences",
                    "semantic_version": "1.0.0", "input_schema_version": "rsr-input-v1",
                    "input_origin": "SAVED_CANDIDATE_RESULTS_NO_REEVALUATION",
                    "mode": "raw_observation_v1" if webdriver else "default",
                    "gate_version": "rsr-webdriver-raw-gate-v1" if webdriver else "rsr-language-first-gate-v1",
                    "candidate_id": name, "same_field_family_as": "old-display-id"})


def problem(atoms, attacks=None, n=6, mutate=None):
    rows, metadata = {}, {}
    for t in range(n):
        for phase in ("clean_pre", "attack", "clean_post"):
            sid = f"synthetic-{t}-{phase}"
            row = {a.atom_id: cell("T" if phase == "attack" and
                   (attacks is None or t in attacks[a.atom_id]) else "F") for a in atoms}
            if mutate:
                mutate(t, phase, row)
            rows[sid] = row
            metadata[sid] = {"supervised_label": int(phase == "attack"), "phase": phase,
                             "bundle_id": "synthetic", "triplet_id": str(t),
                             "environment_group_id": "synthetic", "config_id": "synthetic"}
    job = {"fold_id": "synthetic", "train_ids": list(rows), "outer_test_ids": ["unused-outer"]}
    access = TrainAccess(job, rows, metadata)
    return V2Problem(access, rows, atoms, math.inf)


def positive(name):
    return Clause((Literal(name),))


def selected_keys(p, clauses):
    catalog = semantic_catalog(p.atoms)
    return sorted((json.dumps(catalog[c.literals[0].atom_id]["key"], sort_keys=True),
                   c.literals[0].polarity) for c in clauses)


def at_cap(new_attacks=None, other_attacks=None, mutate=None, n=6):
    old = control("old", LANGS, "language_preferences")
    new = saved()
    others = tuple(control(f"other{i}") for i in range(5))
    atoms = (old, new) + others
    attacks = {a.atom_id: set(range(n)) for a in atoms}
    if new_attacks is not None:
        attacks["new"] = set(new_attacks)
    if other_attacks is not None:
        for a in others:
            attacks[a.atom_id] = set(other_attacks)
    p = problem(atoms, attacks, mutate=mutate, n=n)
    initial = tuple(positive(a.atom_id) for a in (old,) + others)
    return p, initial


class SemanticSelectionTests(unittest.TestCase):
    def test_structural_key_excludes_display_ids_and_preserves_typed_predicates(self):
        original = saved("first")
        renamed = replace(original, atom_id="last", aliases=("different",), provenance={
            **original.provenance, "candidate_id": "other", "same_field_family_as": "changed"})
        self.assertEqual(semantic_catalog([original])["first"], semantic_catalog([renamed])["last"])
        self.assertEqual(semantic_catalog([original])["first"]["key"][0], LANGS)
        a = Atom("bool", "f", ("app_web67",), ("SYNTHETIC",), (), "CONTROL_EQUALITY",
                 {"field": "fixture.x", "encoder": "EQ", "equals": True})
        b = replace(a, atom_id="int", provenance={**a.provenance, "equals": 1})
        self.assertNotEqual(semantic_catalog([a, b])["bool"]["key"], semantic_catalog([a, b])["int"]["key"])
        for value in (math.inf, math.nan):
            with self.assertRaisesRegex(ValueError, "NON_JSON_OR_NONFINITE"):
                semantic_catalog([control("bad", threshold=value)])

    def test_duplicate_semantics_rejected_without_name_fallback(self):
        a = control("first", "fixture.same")
        b = replace(a, atom_id="last", aliases=("alias",))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SEMANTIC_KEY"):
            semantic_catalog([a, b])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SEMANTIC_KEY"):
            greedy_semantic(problem([a, b]), math.inf)

    def test_rename_reorder_invariant_including_backward_prune(self):
        atoms = [control(x, "fixture." + x) for x in ("a", "b", "c")]
        attacks = {"a": {0, 1, 2, 3}, "b": {0, 1, 4, 5}, "c": {2, 3, 6, 7}}
        first = problem(atoms, attacks, n=8)
        left, _, trace = greedy_semantic(first, math.inf)
        self.assertEqual({c.id for c in left}, {"b:POSITIVE", "c:POSITIVE"})
        self.assertEqual([t["removed"] for t in trace if t["operation"] == "PRUNE"], ["a:POSITIVE"])
        names = {"a": "z-last", "b": "y-middle", "c": "x-first"}
        renamed = [replace(a, atom_id=names[a.atom_id], aliases=(names[a.atom_id],)) for a in reversed(atoms)]
        second = problem(renamed, {names[k]: v for k, v in attacks.items()}, n=8)
        second.candidates = tuple(reversed(second.candidates))
        right, _, rtrace = greedy_semantic(second, math.inf)
        self.assertEqual(selected_keys(first, left), selected_keys(second, right))
        self.assertEqual([t["removed"] for t in rtrace if t["operation"] == "PRUNE"], ["z-last:POSITIVE"])

    def test_quality_only_after_original_numeric_criteria(self):
        old, new = control("old", LANGS, "language_preferences"), saved()
        p = problem([old, new], {"old": set(range(6)), "new": {0, 1}})
        selected, _, _ = greedy_semantic(p, math.inf)
        self.assertEqual(selected, (positive("old"),))
        tied = problem([old, new])
        self.assertEqual(greedy_semantic(tied, math.inf)[0], (positive("new"),))

    def test_quality_at_cap_swaps_without_forcing_or_expanding(self):
        p, initial = at_cap()
        selected, outcome, trace = retain_semantic(p, initial, math.inf)
        self.assertEqual(len(selected), 6)
        self.assertIn(positive("new"), selected)
        self.assertNotIn(positive("old"), selected)
        self.assertEqual([t["operation"] for t in trace], ["SWAP_SEMANTIC_QUALITY"])
        self.assertEqual(outcome["status"], "RETENTION_FEASIBLE")
        self.assertEqual(trace[0]["quality_after"], 1)

    def test_D_may_decrease_when_other_groups_preserve_detected_samples(self):
        p, initial = at_cap(new_attacks={0, 1})
        selected, outcome, trace = retain_semantic(p, initial, math.inf)
        self.assertIn(positive("new"), selected)
        self.assertLess(trace[0]["delta_D"], 0)
        self.assertLess(outcome["D_final"], outcome["D_initial"])
        self.assertEqual(p.score(initial)["states"], p.score(selected)["states"])

    def test_swap_rejects_attack_loss_even_if_overall_constraints_pass(self):
        p, initial = at_cap(new_attacks={0, 1}, other_attacks={0, 1})
        selected, outcome, _ = retain_semantic(p, initial, math.inf)
        self.assertEqual(set(selected), set(initial))
        self.assertGreater(outcome["rejection_counts"]["ATTACK_DETECTION_LOSS"], 0)

    def test_swap_rejects_new_clean_alarm_within_total_budget(self):
        def mutate(t, phase, rows):
            if t == 0 and phase == "clean_pre":
                rows["new"] = cell("T")
        p, initial = at_cap(mutate=mutate, n=20)
        self.assertEqual(p.budget, 2)
        selected, outcome, _ = retain_semantic(p, initial, math.inf)
        self.assertEqual(set(selected), set(initial))
        self.assertGreater(outcome["rejection_counts"]["NEW_CLEAN_ALARM"], 0)

    def test_swap_rejects_new_unknown_and_failed_candidate(self):
        for status in ("U", "FAILED"):
            def mutate(t, phase, rows):
                if t == 0 and phase == "clean_pre":
                    rows["new"] = cell(status)
            p, initial = at_cap(mutate=mutate)
            selected, outcome, _ = retain_semantic(p, initial, math.inf)
            self.assertEqual(set(selected), set(initial))
            if status == "U":
                self.assertIn(positive("new"), p.candidates)
                self.assertGreater(outcome["rejection_counts"]["DEFINED_SAMPLE_BECAME_UNKNOWN_OR_FAILED"], 0)
            else:
                self.assertNotIn(positive("new"), p.candidates)

    def test_negative_polarity_gets_no_quality_preference(self):
        old, new = control("old", LANGS, "language_preferences"), saved()
        def mutate(t, phase, rows):
            rows["new"] = cell("F" if phase == "attack" else "T")
        p = problem([old, new], mutate=mutate)
        selected, _, trace = retain_semantic(p, (positive("old"),), math.inf)
        self.assertEqual(selected, (positive("old"),))
        self.assertEqual(trace, [])
        # Numerically tied negative saved state loses to the field-first control
        # key; a mistaken atom-level quality bonus would select the negative.
        self.assertEqual(greedy_semantic(p, math.inf)[0], (positive("old"),))

    def test_exact_saved_gates_required_and_legacy_not_preferred(self):
        raw = saved("raw", webdriver=True)
        legacy = replace(raw, atom_id="legacy", provenance={**raw.provenance,
                         "mode": "legacy_projection_v1", "gate_version": "rsr-webdriver-legacy-gate-v1"})
        catalog = semantic_catalog([raw, legacy])
        self.assertEqual(catalog["raw"]["quality"], 1)
        self.assertEqual(catalog["legacy"]["quality"], 0)
        wrong = replace(saved(), provenance={**saved().provenance, "field_refs": [LANGS, LANG]})
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_SAVED_SEMANTIC"):
            semantic_catalog([wrong])

    def test_retention_rename_invariance_and_finite_termination(self):
        p, initial = at_cap(new_attacks={0, 1})
        left, outcome, _ = retain_semantic(p, initial, math.inf)
        # Rename IDs everywhere the kernel stores a display lookup, preserving
        # the same structural candidate problem, then reverse traversal order.
        q = copy.deepcopy(p)
        names = {a.atom_id: str(99-i) for i, a in enumerate(q.atoms)}
        q.atoms = tuple(replace(a, atom_id=names[a.atom_id], aliases=("changed",)) for a in reversed(q.atoms))
        converted = {c.id: Clause(tuple(sorted(Literal(names[l.atom_id], l.polarity) for l in c.literals)))
                     for c in q.candidates}
        q.states = {converted[k].id: value for k, value in q.states.items() if k in converted}
        q.candidates = tuple(reversed(tuple(converted.values())))
        right, other, _ = retain_semantic(q, tuple(converted[c.id] for c in initial), math.inf)
        self.assertEqual(selected_keys(p, left), selected_keys(q, right))
        self.assertEqual(outcome["visited_structural_keys"], other["visited_structural_keys"])
        self.assertEqual(len(outcome["visited_structural_keys"]), 2)
        self.assertEqual(retain_semantic(p, left, math.inf)[2], [])
        self.assertLess(len(outcome["visited_structural_keys"]), outcome["finite_operation_cap"])

    def test_six_clause_limit_and_time_limit_preserved(self):
        p = problem([control(str(i)) for i in range(7)])
        selected, _, trace = retain_semantic(p, (positive("0"),), math.inf)
        self.assertEqual(len(selected), 6)
        self.assertEqual(len(trace), 5)
        self.assertEqual(retain_semantic(p, (), 0)[1]["status"], "FAILED_FIT")
        self.assertEqual(retain_semantic(p, (positive("0"),), 0)[1]["status"], "TIME_LIMIT_FEASIBLE")


if __name__ == "__main__":
    unittest.main()
