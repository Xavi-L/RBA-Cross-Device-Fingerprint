"""R03 bounded synthetic acceptance; no real feature rows are loaded or fitted."""
import copy
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, product
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from hybridguard_agent.research.rule_learning.access import (
    FitAuthorizationError, FormalFitRequest, TrainingAccess, open_formal_fit, synthetic_fixture)
from hybridguard_agent.research.rule_learning.baselines import (
    adapt_historical_seven, core_view, fixed_model, historical_seven_contract,
    project_core, single_surface_definitions, single_surface_view, transform_numeric)
from hybridguard_agent.research.rule_learning.contracts import binding, cell, contract, ledger, logic, negate
from hybridguard_agent.research.rule_learning.evaluation import evaluate, model_stability
from hybridguard_agent.research.rule_learning.fold_data import FoldBatch, FoldData
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal, RuleModel, load_model, save_model
from hybridguard_agent.research.rule_learning.predictor import predict, predict_batch, predict_single_surface
from hybridguard_agent.research.rule_learning.selector import TrainProblem, compatible, fit, greedy
from hybridguard_agent.research.rule_learning.solver import solve_finite_ip, solver_environment
from hybridguard_agent.research.rule_learning.synthetic import make_fixture

EVIDENCE = {}


def trained(name, method="GREEDY_OR", point="OP05"):
    access = synthetic_fixture(name)
    result = fit(access, access.batch("train"), method, point)
    return access, result


def oracle(access, pool, method, point):
    """Separate exhaustive objective/feasibility arithmetic; never uses IP rows or score()."""
    batch = access.batch("train")
    meta = access.training_metadata(batch)
    atoms = {a.atom_id: a for a in access.atoms}
    nclean = sum(meta[i]["supervised_label"] == 0 for i in batch.ids)
    alpha = {"OP00": Fraction(0), "OP05": Fraction(1, 20), "OP10": Fraction(1, 10)}[point]
    best, visited = None, 0
    for k in range(1, min(6, len(pool)) + 1):
        for chosen in combinations(pool, k):
            visited += 1
            occurrences = sum(len(c.literals) for c in chosen)
            cost = k + occurrences
            if occurrences > 12 or cost > (18 if method == "FINITE_IP_DNF2" else 12):
                continue
            fam, signs, sets = {}, {}, [set(c.literals) for c in chosen]
            for c in chosen:
                for f in {atoms[l.atom_id].family for l in c.literals}:
                    fam[f] = fam.get(f, 0) + 1
                for l in c.literals:
                    signs.setdefault(l.atom_id, set()).add(l.polarity)
            if any(n > 2 for n in fam.values()) or any(len(v) > 1 for v in signs.values()):
                continue
            if any(a <= b or b <= a for a, b in combinations(sets, 2)):
                continue
            predictions = []
            for row in batch.records:
                clauses = []
                for c in chosen:
                    values = []
                    for l in c.literals:
                        raw = row[l.atom_id]
                        v = raw["value"] if raw["available"] else None
                        values.append(not v if l.polarity == "NEGATIVE" and v is not None else v)
                    clauses.append(False if False in values else True if all(v is True for v in values) else None)
                predictions.append(True if True in clauses else False if all(v is False for v in clauses) else None)
            clean = sum(p is True for i, p in zip(batch.ids, predictions) if meta[i]["supervised_label"] == 0)
            if clean > int(alpha * nclean):
                continue
            coverage = []
            for phase in ("clean_pre", "attack", "clean_post"):
                pairs = [(i, p) for i, p in zip(batch.ids, predictions) if meta[i]["phase"] == phase]
                coverage.append(Fraction(sum(p is not None for _, p in pairs), len(pairs)))
            if min(coverage) < Fraction(4, 5):
                continue
            grouped = {}
            for i, p in zip(batch.ids, predictions):
                if meta[i]["supervised_label"] == 1:
                    grouped.setdefault(meta[i]["config_id"], {}).setdefault(meta[i]["environment_group_id"], []).append(p is True)
            macro = sum((sum((Fraction(sum(v), len(v)) for v in envs.values()), Fraction()) / len(envs) for envs in grouped.values()), Fraction()) / len(grouped)
            objective = macro - Fraction(cost, 200)
            key = (-objective, -macro, clean, -min(coverage), cost, tuple(sorted(c.id for c in chosen)))
            if best is None or key < best[0]:
                best = (key, chosen)
    return best, visited


def hand_metric_fixture():
    a = synthetic_fixture("complementary")
    meta = a.evaluation_metadata("outer_test") | a.evaluation_metadata("descriptive_test_side")
    ids = tuple(meta)
    triplet_decisions = (("NO_ALERT", "MANIPULATION_ALERT", "NO_ALERT"),
                         ("MANIPULATION_ALERT", "INSUFFICIENT_EVIDENCE", "FAILED"),
                         ("EMPTY_MODEL", "FAILED", "NO_ALERT"))
    rows = []
    for j, oid in enumerate(ids):
        d = triplet_decisions[j // 3][j % 3] if j < 9 else "MANIPULATION_ALERT"
        defined = d in ("MANIPULATION_ALERT", "NO_ALERT")
        rows.append({"opaque_id": oid, "decision": d, "selected_atoms_available": 2 if defined else 1 if d == "INSUFFICIENT_EVIDENCE" else 0,
                     "selected_atoms_expected": 2, "clauses_defined": int(defined), "clauses_expected": 1})
    return ids, rows, meta


class ModelTests(unittest.TestCase):
    def test_truth_tables_and_unknown_negation(self):
        logic_contract = contract("measurement_contract")["logic"]
        for a, b in product("TFU", repeat=2):
            for op in ("AND", "OR"):
                self.assertEqual(logic((a, b), op), logic_contract[op][a+b])
        self.assertEqual(negate("U"), "U")
        for bad in (None, "FAILED", "NOT_REQUESTED"):
            with self.assertRaises((KeyError, ValueError)):
                negate(bad)
        with self.assertRaises(ValueError):
            logic((), "OR")

    def test_selected_failure_not_hidden_by_true_or_false(self):
        a, r = trained("complementary")
        for value in ("T", "F", "U"):
            p = predict(r.model, "test", {"features": {"A": cell(value), "B": cell("FAILED")}, "view_id": a.view["view_id"]})
            self.assertEqual(p["decision"], "FAILED")
        a, r = trained("and_required", "FINITE_IP_DNF2")
        p = predict(r.model, "test", {"features": {"A": cell("F"), "B": cell("FAILED")}, "view_id": a.view["view_id"]})
        self.assertEqual(p["decision"], "FAILED")

    def test_u_failed_unrequested_and_empty_are_distinct(self):
        a, r = trained("redundant")
        for raw, decision in (("U", "INSUFFICIENT_EVIDENCE"), ("FAILED", "FAILED"), ("NOT_REQUESTED", "FAILED")):
            p = predict(r.model, "test", {"features": {"A": cell(raw)}, "view_id": a.view["view_id"]})
            self.assertEqual(p["decision"], decision)
        empty, e = trained("empty_pool")
        self.assertEqual(predict(e.model, "test", {})["decision"], "EMPTY_MODEL")
        const = fixed_model(empty, "ALWAYS_NO_ALERT")
        self.assertEqual(predict(const, "test", {"features": {}, "view_id": empty.view["view_id"]})["decision"], "NO_ALERT")
        self.assertIsNone(e.model.fit["best_bound"])

    def test_save_load_predictions_and_model_mutation(self):
        a, r = trained("and_required", "FINITE_IP_DNF2")
        before = predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "model.json"
            save_model(r.model, p)
            saved = load_model(p)
            self.assertEqual(before, predict_batch(saved, a.batch("outer_test"), a.view["view_id"]))
            with self.assertRaises(FileExistsError):
                save_model(r.model, p)
            data = json.loads(p.read_text()); data["fit"]["train_ids"] = ["forged"]
            with self.assertRaises(ValueError):
                RuleModel.from_dict(data)
        r.model.fit["train_ids"] = []
        with self.assertRaisesRegex(ValueError, "FROZEN_MODEL"):
            _ = r.model.model_id

    def test_explanations_match_signed_clauses(self):
        a, r = trained("negative")
        p = predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])[1]
        self.assertEqual(p["decision"], "MANIPULATION_ALERT")
        self.assertEqual(p["atom_explanations"][0]["state"], "F")
        self.assertEqual(p["clause_explanations"][0]["literals"][0]["polarity"], "NEGATIVE")
        self.assertEqual(p["clause_explanations"][0]["state"], "T")

    def test_illegal_clause_and_sidecar_envelope(self):
        with self.assertRaises(ValueError):
            Clause(())
        with self.assertRaises(ValueError):
            Clause((Literal("A"), Literal("A", "NEGATIVE")))
        a, r = trained("complementary")
        row = a.batch("outer_test").records[0]
        p = predict(r.model, "test", {"features": row, "view_id": a.view["view_id"], "phase": "attack"})
        self.assertEqual(p["decision"], "FAILED")
        p = predict(r.model, "test", {"features": dict(row, label=1), "view_id": a.view["view_id"]})
        self.assertEqual(p["decision"], "FAILED")


class SelectorTests(unittest.TestCase):
    def test_one_pass_backward_prune_and_coverage_tie(self):
        _, r = trained("pruning")
        self.assertEqual([c.id for c in r.model.clauses], ["B:POSITIVE", "C:POSITIVE"])
        self.assertEqual([x["removed"] for x in r.trace if x["operation"] == "PRUNE"], ["A:POSITIVE"])
        EVIDENCE["greedy_prune"] = {"fixture": "pruning", "trace": r.trace, "selected": [c.id for c in r.model.clauses]}
        for method in ("GREEDY_OR", "FINITE_IP_OR"):
            _, result = trained("coverage_tie", method)
            self.assertEqual([c.id for c in result.model.clauses], ["B:POSITIVE"])

    def test_fixed_operating_points_and_unknown_negative_prediction(self):
        for point, expected in (("OP00", []), ("OP05", ["A:POSITIVE"]), ("OP10", ["A:POSITIVE", "B:POSITIVE"])):
            _, result = trained("union_budget", "FINITE_IP_OR", point)
            self.assertEqual([c.id for c in result.model.clauses], expected)
        a, result = trained("negative")
        p = predict(result.model, "fixture-neg-U", {"features": {"A": cell("U")}, "view_id": a.view["view_id"]})
        self.assertEqual(p["decision"], "INSUFFICIENT_EVIDENCE")
    def test_support_minima_and_finite_cap_without_ranking(self):
        for name, available, true_n in (("two_available", 2, 2), ("one_true_attack", 6, 1)):
            a = synthetic_fixture(name)
            p = TrainProblem(a, a.batch("train"), "GREEDY_OR", "OP05")
            self.assertEqual(p.support["A:POSITIVE"]["triplets"], available)
            self.assertEqual(p.support["A:POSITIVE"]["true_attack_triplets"], true_n)
            self.assertFalse(p.support["A:POSITIVE"]["eligible"])
        a = synthetic_fixture("cap_overflow")
        r = fit(a, a.batch("train"), "FINITE_IP_DNF2")
        self.assertEqual(r.model.fit["status"], "BRANCH_NOT_RUN_SEARCH_SPACE_EXCEEDS_CAP_NO_LABEL_RANK_TRUNCATION")
        self.assertEqual(r.support, {})

    def test_native_highs_zero_time_limit(self):
        import highspy
        h = highspy.Highs()
        h.setOptionValue("output_flag", False); h.setOptionValue("threads", 1); h.setOptionValue("time_limit", 0.0)
        x = h.addVariables(30, lb=0, ub=1, type=highspy.HighsVarType.kInteger)
        h.addConstr(h.qsum((i+1)*x[i] for i in range(30)) <= 117)
        h.setObjective(h.qsum((i*i % 17 + 1)*x[i] for i in range(30)), highspy.ObjSense.kMaximize)
        h.run()
        self.assertEqual(h.getModelStatus(), highspy.HighsModelStatus.kTimeLimit)
        self.assertFalse(h.getSolution().value_valid)
        EVIDENCE["native_timeout"] = {"solver": "HiGHS", "version": h.version(), "time_limit_seconds": 0,
            "status": h.getModelStatus().name, "incumbent": False,
            "note": "Zero-time backend status smoke; feasible-timeout and error handling use explicit synthetic injection."}
    def test_set_clean_union_budget(self):
        a = synthetic_fixture("union_budget")
        p = TrainProblem(a, a.batch("train"), "FINITE_IP_OR", "OP05")
        pos = [c for c in p.candidates if c.literals[0].polarity == "POSITIVE"]
        self.assertEqual(p.budget, 1)
        self.assertTrue(all(p.score((c,))["feasible"] for c in pos))
        self.assertEqual(p.score(pos)["clean_alarms"], 2)
        self.assertFalse(p.score(pos)["feasible"])
        for method in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2"):
            r = fit(a, a.batch("train"), method)
            self.assertEqual([c.id for c in r.model.clauses], ["A:POSITIVE"])
            self.assertEqual(r.model.fit["training_result"]["objective"]["value"], .49)

    def test_complementarity_and_redundancy(self):
        for name, expected in (("complementary", ["A:POSITIVE", "B:POSITIVE"]), ("redundant", ["A:POSITIVE"])):
            for method in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2"):
                _, r = trained(name, method)
                self.assertEqual([c.id for c in r.model.clauses], expected)

    def test_and_extension_and_certified_infeasibility(self):
        _, a = trained("and_required", "FINITE_IP_OR")
        _, b = trained("and_required", "FINITE_IP_DNF2")
        self.assertEqual(a.model.status, "EMPTY_MODEL")
        self.assertTrue(a.model.fit["infeasibility_proved"])
        self.assertEqual([c.id for c in b.model.clauses], ["A:POSITIVE & B:POSITIVE"])
        self.assertEqual(b.model.fit["training_result"]["objective"]["value"], .985)

    def test_heuristic_empty_does_not_prove_infeasible(self):
        _, g = trained("infeasible")
        _, ip = trained("infeasible", "FINITE_IP_OR")
        self.assertEqual(g.model.status, "EMPTY_MODEL")
        self.assertFalse(g.model.fit["infeasibility_proved"])
        self.assertTrue(ip.model.fit["infeasibility_proved"])

    def test_empty_unknown_failure_and_coverage_boundary(self):
        for name in ("empty_pool", "all_unknown", "failed_atom"):
            _, r = trained(name)
            self.assertEqual(r.model.status, "EMPTY_MODEL")
        for method in ("GREEDY_OR", "FINITE_IP_OR"):
            _, low = trained("low_coverage", method)
            _, boundary = trained("coverage_boundary", method)
            self.assertEqual(low.model.status, "EMPTY_MODEL")
            self.assertEqual(boundary.model.status, "FITTED")
            self.assertEqual(boundary.model.fit["training_result"]["minimum_coverage"]["value"], .8)

    def test_support_counts_complete_triplets_not_aliases_or_stages(self):
        a = core_view(synthetic_fixture("aliases"))
        p = TrainProblem(a, a.batch("train"), "GREEDY_OR", "OP05")
        s = p.support["DEVIATION:NW-002:POSITIVE"]
        self.assertEqual((s["triplets"], s["true_attack_triplets"], s["bundles"], s["environments"]), (6, 6, 1, 1))
        self.assertEqual(s["phase_availability"]["attack"]["T"], 6)
        self.assertEqual(len(p.ids), 18)
        a = synthetic_fixture("low_coverage")
        p = TrainProblem(a, a.batch("train"), "GREEDY_OR", "OP05")
        self.assertEqual(p.support["A:POSITIVE"]["triplets"], 3)

    def test_macro_weights_are_not_micro_weights(self):
        a = synthetic_fixture("macro_weights")
        p = TrainProblem(a, a.batch("train"), "FINITE_IP_OR", "OP05")
        for c in p.candidates:
            if c.literals[0].polarity == "POSITIVE":
                self.assertEqual(p.score((c,))["macro_tpr"], Fraction(1, 2))

    def test_grammar_family_subsumption_opposite_and_complexity(self):
        a = synthetic_fixture("complementary")
        g, s = contract("candidate_grammar"), contract("learning_search_space")
        self.assertFalse(compatible((Clause((Literal("A"),)), Clause((Literal("A", "NEGATIVE"),))), a.atoms, "FINITE_IP_OR", g, s))
        self.assertFalse(compatible((Clause((Literal("A"),)), Clause((Literal("A"), Literal("B")))), a.atoms, "FINITE_IP_DNF2", g, s))
        atoms = tuple(Atom(str(i), "shared", ("native84",), ("E",), (str(i),)) for i in range(7))
        clauses = tuple(Clause((Literal(str(i)),)) for i in range(7))
        self.assertFalse(compatible(clauses[:3], atoms, "GREEDY_OR", g, s))
        atoms = tuple(replace(a, family=a.atom_id) for a in atoms)
        self.assertFalse(compatible(clauses, atoms, "GREEDY_OR", g, s))

    def test_ip_against_exhaustive_oracle(self):
        records = []
        for name, method in product(("union_budget", "complementary", "redundant", "negative", "and_required", "low_coverage", "coverage_boundary"), ("FINITE_IP_OR", "FINITE_IP_DNF2")):
            a = synthetic_fixture(name)
            problem = TrainProblem(a, a.batch("train"), method, "OP05")
            best, visited = oracle(a, problem.candidates, method, "OP05")
            r = fit(a, a.batch("train"), method)
            actual = tuple(c.id for c in r.model.clauses)
            self.assertEqual(actual, tuple(sorted(c.id for c in best[1])) if best else ())
            if best:
                self.assertEqual(r.model.fit["status"], "OPTIMAL_FINITE_POOL")
                self.assertTrue(r.model.fit["tie_break_complete"])
                self.assertAlmostEqual(r.model.fit["best_bound"], -float(best[0][0]))
            records.append({"fixture": name, "method": method, "enumerated_subsets": visited,
                "selected": actual, "oracle_objective": -float(best[0][0]) if best else None,
                "solver_status": r.model.fit["status"], "gap": r.model.fit["gap"], "match": True})
        EVIDENCE["ip_exhaustive_checks"] = records

    def test_timeout_unavailable_error_and_incumbent_recheck(self):
        a = synthetic_fixture("complementary")
        p = TrainProblem(a, a.batch("train"), "GREEDY_OR", "OP05")
        self.assertEqual(greedy(p, 0)[1]["status"], "FAILED_FIT")
        with patch("hybridguard_agent.research.rule_learning.solver.solver_environment", return_value={"available": False, "solver": "HiGHS", "status": "NOT_RUN_SOLVER_UNAVAILABLE_NO_PAID_FALLBACK"}):
            r = fit(a, a.batch("train"), "FINITE_IP_OR")
            self.assertEqual(r.model.fit["status"], "NOT_RUN_SOLVER_UNAVAILABLE_NO_PAID_FALLBACK")
            self.assertEqual(r.model.status, "FAILED")
        valid = tuple(c for c in p.candidates if c.literals[0].polarity == "POSITIVE")
        failure_evidence = []
        for selected, outcome, expected in ((valid, {"status": "TIME_LIMIT_FEASIBLE", "best_bound": 1, "gap": .02}, "FITTED"),
                                            ((), {"status": "FAILED_FIT", "reason": "TIME_LIMIT_NO_INCUMBENT"}, "FAILED")):
            with patch("hybridguard_agent.research.rule_learning.solver.solve_finite_ip", return_value=(selected, outcome, [{"injected": True}])):
                r = fit(a, a.batch("train"), "FINITE_IP_OR")
                self.assertEqual(r.model.status, expected)
                failure_evidence.append({"injected_outcome": outcome, "validated_model_status": r.model.status,
                    "expected_prediction_rows": len(a.batch("outer_test").ids),
                    "decisions": [p["decision"] for p in predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])]})
                if expected == "FAILED":
                    self.assertTrue(all(p["decision"] == "FAILED" for p in predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])))
        with patch("hybridguard_agent.research.rule_learning.solver.solve_finite_ip", side_effect=RuntimeError("SYNTHETIC_SOLVER_ERROR")):
            self.assertEqual(fit(a, a.batch("train"), "FINITE_IP_OR").model.status, "FAILED")
        budget = synthetic_fixture("union_budget")
        with patch("hybridguard_agent.research.rule_learning.solver.solve_finite_ip", return_value=(valid, {"status": "TIME_LIMIT_FEASIBLE"}, [])):
            self.assertEqual(fit(budget, budget.batch("train"), "FINITE_IP_OR").model.status, "FAILED")
        EVIDENCE["failure_branches"] = failure_evidence


class LeakageAndBaselineTests(unittest.TestCase):
    def test_group_split_rejected_and_single_surface_metadata_adapter(self):
        with self.assertRaisesRegex(ValueError, "BUNDLE_SPLIT"):
            synthetic_fixture("invalid_split")
        definitions = {s: single_surface_definitions(s) for s in ("native84", "app_web67", "host26")}
        self.assertEqual(sum(a.atom_id.startswith("UNFITTED_CONTROL:") for rows in definitions.values() for a in rows), 62)
        self.assertEqual(sum(a.atom_id.startswith("CONTROL:") for rows in definitions.values() for a in rows), 53)
        for s, atoms in definitions.items():
            self.assertTrue(all(a.surfaces == (s,) for a in atoms))
    def test_test_descriptive_and_cross_fold_cannot_fit(self):
        a = synthetic_fixture("complementary")
        for part in ("outer_test", "descriptive_test_side", "descriptive_train_side"):
            with self.assertRaises(FitAuthorizationError):
                fit(a, a.batch(part))
        batch = replace(a.batch("train"), fold_id="another-fold")
        with self.assertRaises(FitAuthorizationError):
            fit(a, batch)
        records = copy.deepcopy(a.batch("train").records); records[0]["A"] = cell("T")
        with self.assertRaises(FitAuthorizationError):
            fit(a, replace(a.batch("train"), records=records))

    def test_synthetic_flag_renamed_ids_and_mutation_do_not_grant_fit(self):
        members, features, meta, atoms, view = make_fixture("complementary")
        old = FoldData(members, features, meta, synthetic=True)
        with self.assertRaisesRegex(FitAuthorizationError, "NOT_SYNTHETIC_FLAG_OR_RENAMED_IDS"):
            fit(old, old.batch("train"))
        stage_closed = FoldData(members, features, meta)
        with self.assertRaisesRegex(PermissionError, "R02_REAL_DATA_FIT_NOT_AUTHORIZED"):
            stage_closed.assert_fit(stage_closed.batch("train"), "support")
        with self.assertRaises(FitAuthorizationError):
            fit(stage_closed, stage_closed.batch("train"))
        with self.assertRaises(TypeError):
            synthetic_fixture("complementary", synthetic=True)
        with self.assertRaises(FitAuthorizationError):
            TrainingAccess(object(), members, features, meta, atoms, view, "fake")
        a = synthetic_fixture("complementary")
        oid = a.batch("train").ids[0]
        a._data._features[oid]["A"] = cell("T")
        with self.assertRaisesRegex(FitAuthorizationError, "CONTENT_CHANGED"):
            fit(a, a.batch("train"))

    def test_future_formal_entry_is_explicit_and_closed(self):
        req = FormalFitRequest("R05", "authorization.json", "freeze.json", "resources.json", "jobs.jsonl#1",
             binding()["protocol_digest"], "LOEO-v1", "fold-1", "GREEDY_OR", "OP05", "SRC-111", "core", "train.json")
        with self.assertRaisesRegex(FitAuthorizationError, "R03_REAL_DATA_FIT_NOT_AUTHORIZED"):
            open_formal_fit(req)
        with self.assertRaises(FitAuthorizationError):
            open_formal_fit({"synthetic": True})

    def test_test_labels_do_not_change_predictions_train_labels_can_change_fit(self):
        a, r = trained("label_sensitive")
        expected = predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])
        labels = a.evaluation_metadata("outer_test")
        for m in labels.values():
            m["supervised_label"] = 1 - m["supervised_label"]
        self.assertEqual(expected, predict_batch(r.model, a.batch("outer_test"), a.view["view_id"]))
        _, changed = trained("train_labels_changed")
        self.assertEqual([c.id for c in r.model.clauses], ["A:POSITIVE"])
        self.assertEqual([c.id for c in changed.model.clauses], ["B:POSITIVE"])

    def test_source_first_alias_polarity_and_no_double_support(self):
        raw = synthetic_fixture("aliases")
        e, o, union = (core_view(raw, s) for s in ("SRC-001", "SRC-100", "SRC-111"))
        name = "DEVIATION:NW-002"
        ea, oa, ua = (next(a for a in v.atoms if a.atom_id == name) for v in (e, o, union))
        self.assertEqual(ea.aliases, ("NW-002",))
        self.assertEqual(oa.aliases, ("OFFDER-OS-001",))
        self.assertEqual(set(ua.aliases), {"NW-002", "OFFDER-OS-001"})
        self.assertEqual(oa.sources, ("O_u",))
        self.assertEqual([r[name] for r in e.batch("train").records], [r[name] for r in o.batch("train").records])
        self.assertEqual(len(core_view(raw, "SRC-000").atoms), 0)
        with self.assertRaisesRegex(ValueError, "RAW_ALIAS_CELLS"):
            project_core(union._data._features, ledger(), "SRC-001")

    def test_alias_domain_conflicts_do_not_contaminate_other_source_conditions(self):
        raw = synthetic_fixture("aliases_conflict")
        e, union = core_view(raw, "SRC-001"), core_view(raw, "SRC-111")
        self.assertTrue(all(r["DEVIATION:NW-002"]["evaluation_status"] == "OK" for r in e.batch("train").records))
        self.assertTrue(all(r["DEVIATION:NW-002"]["evaluation_status"] == "FAILED" for r in union.batch("train").records))

    def test_direct_core_or_uses_only_deviation_direction_no_support_filter(self):
        a = core_view(synthetic_fixture("aliases"))
        model = fixed_model(a, "DIRECT_CORE_OR")
        self.assertEqual(len(model.clauses), 10)
        self.assertFalse(model.fit["support_filter"])
        self.assertTrue(all(l.polarity == "POSITIVE" for c in model.clauses for l in c.literals))
        decisions = predict_batch(model, a.batch("outer_test"), a.view["view_id"])
        self.assertEqual([r["decision"] for r in decisions[:3]], ["NO_ALERT", "MANIPULATION_ALERT", "NO_ALERT"])
        with self.assertRaises(ValueError):
            fixed_model(synthetic_fixture("aliases"), "DIRECT_CORE_OR")
        wrong = predict(model, "x", {"features": a.batch("train").records[0], "view_id": "CORE:SRC-100"})
        self.assertEqual(wrong["decision"], "FAILED")

    def test_numeric_train_fit_frozen_before_transform_and_masking(self):
        raw = synthetic_fixture("numeric")
        prepared = single_surface_view(raw, "native84")
        extreme = single_surface_view(synthetic_fixture("numeric_test_extreme"), "native84")
        masked = single_surface_view(synthetic_fixture("numeric_masked_failure"), "native84")
        key = "UNFITTED_CONTROL:native.number"
        self.assertEqual(prepared.encoder["numeric"][key]["thresholds"], [4.25, 8.5, 12.75])
        self.assertEqual(prepared.encoder, extreme.encoder)
        self.assertEqual(prepared.encoder, masked.encoder)
        self.assertTrue(all(a.surfaces == ("native84",) for a in prepared.atoms))
        self.assertTrue(all(not a.atom_id.startswith("UNFITTED_CONTROL:") for a in prepared.atoms))
        self.assertEqual(fit(raw, raw.batch("train")).model.status, "FAILED")
        r = fit(prepared, prepared.batch("train"))
        model = RuleModel.from_dict(r.model.to_dict())
        actual = [predict_single_surface(model, oid, row) for oid, row in zip(raw.batch("outer_test").ids, raw.batch("outer_test").records)]
        expected = predict_batch(model, prepared.batch("outer_test"), prepared.view["view_id"])
        self.assertEqual(actual, expected)

    def test_numeric_unknown_failed_and_not_requested_stay_distinct(self):
        p = single_surface_view(synthetic_fixture("numeric"), "native84")
        for status in ("U", "FAILED", "NOT_REQUESTED"):
            raw = {"CONTROL:native.flag": cell("F"), "UNFITTED_CONTROL:native.number": cell(status)}
            output = transform_numeric(raw, p.encoder)
            numeric = [c for k, c in output.items() if ":LE:" in k]
            self.assertTrue(all(c["value"] is None for c in numeric))
            self.assertTrue(all(c["evaluation_status"] == ("OK" if status == "U" else status) for c in numeric))

    def test_historical_saved_adapter_and_coverage_contract(self):
        spec = historical_seven_contract()
        self.assertEqual(len(spec["rule_ids"]), 7)
        row = {k: v for k, v in spec.items() if k != "rule_ids"}
        row.update(opaque_id="fixture-old", execution_status="COMPLETED", risk={"decision": "NO_ALERT", "family_coverage": .8})
        out = adapt_historical_seven(["fixture-old", "fixture-missing"], [row], {"fixture-old"})
        self.assertEqual([r["decision"] for r in out], ["NO_ALERT", "FAILED"])
        self.assertEqual(out[0]["historical_family_coverage"], .8)
        self.assertEqual(out[0]["selected_atoms_expected"], 0)
        with self.assertRaises(ValueError):
            adapt_historical_seven(["fixture-old"], [dict(row, method="legacy19")], {"fixture-old"})
        with self.assertRaises(ValueError):
            adapt_historical_seven(["fixture-old"], [row, row], {"fixture-old"})


class MetricTests(unittest.TestCase):
    def test_hand_calculated_denominators_and_identification_intervals(self):
        ids, rows, meta = hand_metric_fixture()
        report = evaluate(ids, rows, meta)
        expected = {"attack_tpr": (1, 3), "clean_alarm_rate": (1, 6), "pre_alarm_rate": (1, 3), "post_alarm_rate": (0, 3),
                    "decided_clean_alarm_rate": (1, 4), "exact_FTF": (1, 3), "conditional_recovery": (1, 1),
                    "decision_coverage": (8, 12), "abstention_rate": (2, 12), "failure_rate": (2, 12),
                    "atom_coverage": (17, 24), "clause_coverage": (8, 12)}
        for name, (n, d) in expected.items():
            self.assertEqual((report["metrics"][name]["numerator"], report["metrics"][name]["denominator"]), (n, d))
        self.assertEqual(report["descriptive_n"], 3)
        self.assertEqual(report["identification_intervals"]["positive"]["upper"]["value"], 1)
        self.assertEqual(report["identification_intervals"]["negative"]["upper"]["value"], .5)
        EVIDENCE["hand_metrics"] = {"note": "Hand-specified decision table tests metric arithmetic; it is not one fitted model's performance.",
                                     "rows": rows, "metadata": meta, "expected_fractions": expected, "actual": report}

    def test_missing_predictions_remain_expected_failures(self):
        ids, rows, meta = hand_metric_fixture()
        r = evaluate(ids, rows[1:], meta)
        self.assertEqual(r["expected_stage_n"], 12)
        self.assertEqual(r["received_prediction_n"], 11)
        self.assertEqual(r["status"], "INCOMPLETE_EXPECTED_PREDICTIONS")
        self.assertEqual(r["metrics"]["clean_alarm_rate"]["denominator"], 6)
        self.assertEqual(r["metrics"]["atom_coverage"]["denominator"], 24)
        with self.assertRaises(ValueError):
            evaluate(ids, rows + [rows[0]], meta)

    def test_zero_denominators_empty_and_descriptive_no_truth(self):
        a, r = trained("empty_pool")
        predictions = predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])
        report = evaluate(a.batch("outer_test").ids, predictions, a.evaluation_metadata("outer_test"))
        self.assertEqual(report["metrics"]["decided_clean_alarm_rate"]["status"], "NOT_EVALUABLE")
        self.assertEqual(report["metrics"]["decision_coverage"]["value"], 0)
        desc = a.batch("descriptive_test_side")
        report = evaluate(desc.ids, predict_batch(r.model, desc, a.view["view_id"]), a.evaluation_metadata("descriptive_test_side"))
        self.assertEqual(report["metrics"]["clean_alarm_rate"]["status"], "NOT_EVALUABLE_NO_TRUTH")
        self.assertIsNone(report["metrics"]["attack_tpr"]["value"])

    def test_mixed_models_need_explicit_oof_and_empty_stability(self):
        a, r = trained("complementary")
        rows = predict_batch(r.model, a.batch("outer_test"), a.view["view_id"])
        rows[0]["model_id"] = "another-model"
        with self.assertRaises(ValueError):
            evaluate(a.batch("outer_test").ids, rows, a.evaluation_metadata("outer_test"))
        _, empty = trained("empty_pool")
        self.assertEqual(model_stability([empty.model, empty.model])[0]["status"], "NOT_EVALUABLE")
        self.assertEqual(model_stability([empty.model, r.model])[0]["value"], 0)


if __name__ == "__main__":
    unittest.main()
