"""Training-side integration checks; never invoke a real model fit/evaluation."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import time
import unittest

from hybridguard_agent.research import mtc_reselection_candidates as old
from hybridguard_agent.research import mtc_relation_candidates as adapter
from hybridguard_agent.research import mtc_relation_selection as engine
from hybridguard_agent.research import mtc_constrained_reselection as base_engine
from hybridguard_agent.research import mtc_relation_sources as source
from hybridguard_agent.research import mtc_resource_relations as memory
from hybridguard_agent.research import mtc_screen_relations as screen
from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.models import Clause, Literal
from hybridguard_agent.research.rule_learning_v2.adapter import approved_atoms
from hybridguard_agent.tests.test_mtc_constrained_selection import fixture

ROOT = Path(__file__).resolve().parents[2]


class RelationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = json.loads((ROOT / "deliverables/mtc_constrained_reselection_v1/SETTINGS.json").read_text())
        cls.job = cls.settings["folds"][0]
        cls.ids = cls.job["train_ids"]
        cls.directory = ROOT / cls.settings["controlled_source"]
        cls.inputs = {sid: json.loads((cls.directory / "inputs" / (sid + ".json")).read_text()) for sid in cls.ids}
        cls.bound = source.load_controlled_sources(cls.ids, allowed_ids=cls.ids)
        cls.base = {sid: old.adapt_controlled(row) for sid, row in cls.inputs.items()}
        cls.extended = {sid: adapter.adapt_controlled(row, cls.bound[sid]) for sid, row in cls.inputs.items()}
        cls.metadata = {}
        for sid in cls.ids:
            row = json.loads((cls.directory / "evaluation" / (sid + ".json")).read_text())
            cls.metadata[sid] = dict(row, supervised_label=row["proposed_supervised_label"])
        cls.mtc_ids = cls.settings["mtc_normal_train_ids"]
        wanted = set(cls.mtc_ids)
        with (ROOT / cls.settings["mtc_p2_registry"]).open() as stream:
            registry_rows = (json.loads(line) for line in stream)
            cls.registry = {r["sample_id"]: r for r in registry_rows if r["sample_id"] in wanted}
        locations = {(r["source_view"], r["source_line"]): r["sample_id"] for r in cls.registry.values()}
        cls.mtc = {}
        for view in {view for view, _ in locations}:
            with (ROOT / cls.settings["mtc_snapshot"] / (view + ".jsonl")).open() as stream:
                for number, line in enumerate(stream, 1):
                    if (view, number) in locations:
                        cls.mtc[locations[view, number]] = json.loads(line)
        cls.mtc_bound = {sid: source.bind_mtc_observation(cls.mtc[sid], sid, allowed_ids=cls.mtc_ids,
            expected_registry=cls.registry[sid]) for sid in cls.mtc_ids}
        cls.mtc_base = {sid: old.adapt_mtc(cls.mtc[sid]) for sid in cls.mtc_ids}
        cls.mtc_ext = {sid: adapter.adapt_mtc(cls.mtc[sid], cls.mtc_bound[sid]) for sid in cls.mtc_ids}

    def test_all_training_controlled_and_discovery_base50_cells_unchanged(self):
        self.assertEqual(len(self.ids), 252)
        self.assertEqual(len(self.mtc_ids), 630)
        for sid, old_record, extended, bound in (
                *((sid, self.base[sid], self.extended[sid], self.bound[sid]) for sid in self.ids),
                *((sid, self.mtc_base[sid], self.mtc_ext[sid], self.mtc_bound[sid]) for sid in self.mtc_ids)):
            self.assertEqual(bound["status"], "OK", sid)
            self.assertEqual(len(old_record["raw"]), 50)
            self.assertEqual({key: extended["raw"][key] for key in old_record["raw"]}, old_record["raw"], sid)
            self.assertEqual({key: extended["candidate_inputs"][key] for key in old_record["candidate_inputs"]},
                             old_record["candidate_inputs"], sid)
        self.assertEqual(len(approved_atoms(old.definitions())), 50)

    def test_real_training_encoder_equals_saved_b_and_new_parameters_are_fixed(self):
        atom_ids = {a.atom_id for a in adapter.registered_atoms()}
        take_rel = lambda rows: {sid: {key: row["raw"][key] for key in atom_ids} for sid, row in rows.items()}
        normal_meta = {sid: {"split": "discovery", "normal_basis": True,
                             "group_id": self.registry[sid]["group_id"]} for sid in self.mtc_ids}
        expected = json.loads((ROOT / "deliverables/mtc_constrained_reselection_v1/folds" /
                               self.job["fold_id"] / "encoder.json").read_text())
        prepared = engine.prepare_fold(self.job,
            {sid: self.base[sid]["raw"] for sid in self.ids}, self.metadata, old.definitions(),
            {sid: self.mtc_base[sid]["raw"] for sid in self.mtc_ids}, normal_meta,
            take_rel(self.extended), take_rel(self.mtc_ext), adapter.registered_atoms(), adapter.parameters(),
            mtc_train_ids=self.mtc_ids, expected_old_encoder=expected)
        self.assertEqual(prepared.common.encoder, expected)
        self.assertEqual(set(expected["train_ids"]), set(self.ids))
        self.assertFalse(prepared.relation_parameters["fitted"])
        self.assertEqual(prepared.relation_parameters["parameter_fit_calls"], 0)
        self.assertEqual(prepared.common.preparation["numeric_fit_member_ids"], expected["train_ids"])
        self.assertTrue(set(prepared.common.encoder["fixed_atoms"]).isdisjoint(atom_ids))

    def test_actual_relation_surfaces_and_equal_selection_quality(self):
        atoms = {a.atom_id: a for a in adapter.registered_atoms()}
        self.assertEqual(len(atoms), 2)
        self.assertEqual(atoms[memory.MEMORY_ID].surfaces, ("native84", "app_web67"))
        self.assertEqual(atoms[screen.ATOM_ID].surfaces, ("app_web67",))
        catalog = engine.semantic_catalog(tuple(atoms.values()))
        self.assertTrue(all(row["quality"] == 0 for row in catalog.values()))

    def test_normal_observed_memory_counterexamples_are_kept_as_true(self):
        for sid in self.mtc_ids:
            record = self.mtc_bound[sid]
            fields = record["features"]
            values = [fields.get(f) for f in memory.FIELDS]
            if all(record["field_status"].get(f) == "observed" and
                   record["field_quality"].get(f) == "observed_value" for f in memory.FIELDS) and all(
                    type(v) in (int, float) and v > 0 for v in values) and values[0] >= memory.MINIMUM_NATIVE_GIB:
                result = self.mtc_ext[sid]["raw"][memory.MEMORY_ID]
                self.assertTrue(result["available"], sid)
                self.assertEqual(result["value"], values[1] > memory.power_two_upper_envelope(values[0]), sid)
        # This synthetic normal-source counterexample may not be relabelled or
        # hidden by its profile, source label, or observed large-screen values.
        sid = self.mtc_ids[0]
        record = deepcopy(self.mtc_bound[sid])
        for field, value in zip(memory.FIELDS, (1.75, 8)):
            record["features"][field] = value
            record["field_status"][field] = "observed"
            record["field_quality"][field] = "observed_value"
        record.update(label="normal", model="large tablet", phase="clean_post", source="MTC")
        result = adapter.relation_cells(record)[memory.MEMORY_ID]
        self.assertTrue(result["available"])
        self.assertIs(result["value"], True)

    def test_control_metadata_does_not_change_cells_and_cross_record_binding_fails(self):
        sid, another = self.ids[:2]
        original = adapter.adapt_controlled(self.inputs[sid], self.bound[sid])
        prepared, bound = deepcopy(self.inputs[sid]), deepcopy(self.bound[sid])
        prepared.update(label="attack", model="model changed", phase="attack", tool="any")
        bound.update(label="normal", model="tablet", phase="clean_post", manufacturer="any")
        self.assertEqual(adapter.adapt_controlled(prepared, bound)["raw"], original["raw"])
        wrong = adapter.adapt_controlled(self.inputs[sid], self.bound[another])
        for atom in adapter.registered_atoms():
            self.assertEqual(wrong["raw"][atom.atom_id]["evaluation_status"], "FAILED")
        for key in self.base[sid]["raw"]:
            self.assertEqual(wrong["raw"][key], self.base[sid]["raw"][key])
        first, second = self.mtc_ids[:2]
        wrong = adapter.adapt_mtc(self.mtc[first], self.mtc_bound[second])
        for atom in adapter.registered_atoms():
            self.assertEqual(wrong["raw"][atom.atom_id]["evaluation_status"], "FAILED")

    def test_new_relations_have_whole_or_normal_budget_and_final_b_coverage(self):
        # Construct the same B scoring problem without performing any fit.
        defs, job, raw, meta, mtc, mm = fixture(fields=("irrelevant",), mtc_n=100)
        atoms = adapter.registered_atoms()
        rel = {sid: {a.atom_id: cell("T" if meta[sid]["phase"] == "attack" else "F") for a in atoms} for sid in raw}
        mr = {sid: {a.atom_id: cell("F") for a in atoms} for sid in mtc}
        for pos, aid in enumerate(a.atom_id for a in atoms):
            for sid in list(mtc)[pos * 5:pos * 5 + 5]:
                mr[sid][aid] = cell("T")
        def problem():
            prepared = engine.prepare_fold(job, raw, meta, defs, mtc, mm, rel, mr,
                atoms, adapter.parameters(), mtc_train_ids=list(mtc))
            return base_engine._problem(prepared.common, "B", time.monotonic() + 60)[0]
        p = problem()
        clauses = [Clause((Literal(a.atom_id, "POSITIVE"),)) for a in atoms]
        self.assertTrue(all(p.score((c,))["feasible"] for c in clauses))
        self.assertEqual(p.score(clauses)["mtc_alarms"], 10)
        self.assertFalse(p.score(clauses)["feasible"])
        self.assertIn("MTC_SET_NORMAL_BUDGET", p.score(clauses)["constraint_reasons"])
        for sid in mtc:
            for a in atoms:
                mr[sid][a.atom_id] = cell("F")
        for pos, aid in enumerate(a.atom_id for a in atoms):
            for sid in list(mtc)[pos * 10:pos * 10 + 10]:
                mr[sid][aid] = cell("U")
        p = problem()
        self.assertTrue(all(p.score((c,))["feasible"] for c in clauses))
        self.assertEqual(p.score(clauses)["mtc_coverage"], Fraction(4, 5))
        self.assertFalse(p.score(clauses)["feasible"])
        self.assertIn("MTC_SET_DECISION_COVERAGE_BELOW_90_PERCENT", p.score(clauses)["constraint_reasons"])


if __name__ == "__main__":
    unittest.main()
