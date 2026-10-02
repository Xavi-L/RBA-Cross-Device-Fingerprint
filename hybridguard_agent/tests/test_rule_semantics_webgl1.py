"""Synthetic adapter boundaries only; no experiment observations are loaded."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_capacity as old
from hybridguard_agent.research import rule_semantics_webgl1 as new
from hybridguard_agent.research import webgl1_selector_integration as webgl
from hybridguard_agent.research.rule_learning.contracts import cell, state
from hybridguard_agent.research.rule_learning_v2.capacity import PROFILE
from hybridguard_agent.tests.test_rule_semantics_capacity import independent_signals


def binding(job, group, method):
    return {"study_version": new.STUDY_VERSION, "phase": new.PHASE,
            "experiment_id": new.EXPERIMENT, "group_id": group, "method_id": method,
            "operating_point": "OP05", "fold_id": job["fold_id"],
            "capacity_profile": PROFILE["profile_id"], "evaluation_role": "SYNTHETIC_ONLY"}


def saved(s):
    return {"candidate_id": webgl.CANDIDATE_ID, "candidate_revision": webgl.CANDIDATE_REVISION,
            "registration_version": webgl.VERSION, "state": s,
            "value": {"T": True, "F": False, "U": None}[s], "available": s != "U",
            "evaluation_status": "OK", "reason": "SYNTHETIC", "diagnostics": {}}


class WebGLFreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.job, cls.rows, cls.meta, cls.candidates = independent_signals(2)
        # One synthetic configuration has only the new predicate; no label lookup
        # exists in the adapter, which receives only the saved cells below.
        second = "CONTROL:app.web_data.navigator_layer.cookie_enabled:EQ:True"
        for oid, m in cls.meta.items():
            cls.rows[oid][second] = cell("F")
            cls.candidates[oid][webgl.CANDIDATE_ID] = saved(
                "T" if m["config_id"] == "fixture-config-1" and m["phase"] == "attack" else "F")
        cls.modes = dict.fromkeys(cls.rows, "raw_observation_v1")
        cls.models = {}
        cls.training = {}
        for group in new.GROUPS:
            cls.models[group], cls.training[group] = new.fit_sparse(cls.job, cls.rows, cls.meta, cls.defs,
                group=group, binding=binding(cls.job, group, "GREEDY_SEMANTIC_V2"),
                source_modes=cls.modes, candidate_rows=cls.candidates)

    def test_only_one_registered_atom_changes_and_inputs_are_copied(self):
        before = deepcopy((self.defs, self.rows, self.candidates))
        base = new.group_definitions(self.defs, "BASE49")
        added = new.group_definitions(self.defs, "WEBGL50")
        self.assertEqual(base, old.group_definitions(self.defs, "LANG_ADD_WD_REPLACE"))
        self.assertEqual(added["atoms"][:-1], base["atoms"])
        self.assertEqual(added["atoms"][-1]["atom_id"], webgl.CANDIDATE_ID)
        b = new.project_rows(self.rows, self.defs, "BASE49", source_modes=self.modes, candidate_rows=self.candidates)
        w = new.project_rows(self.rows, self.defs, "WEBGL50", source_modes=self.modes, candidate_rows=self.candidates)
        for oid in self.rows:
            self.assertEqual({k: v for k, v in w[oid].items() if k != webgl.CANDIDATE_ID}, b[oid])
        self.assertEqual((self.defs, self.rows, self.candidates), before)

    def test_cap7_encoder_and_existing_semantic_catalog_unchanged(self):
        b, w = self.models["BASE49"], self.models["WEBGL50"]
        self.assertEqual((b.status, w.status), ("FITTED", "FITTED"))
        self.assertEqual(b.encoder, {**w.encoder, "fixed_atoms": [a for a in w.encoder["fixed_atoms"] if a != webgl.CANDIDATE_ID]})
        self.assertEqual(b.fit["capacity_profile"], w.fit["capacity_profile"])
        bc, wc = self.training["BASE49"]["semantic_catalog"], self.training["WEBGL50"]["semantic_catalog"]
        self.assertEqual(bc, {k: v for k, v in wc.items() if k != webgl.CANDIDATE_ID})
        self.assertEqual(wc[webgl.CANDIDATE_ID]["quality"], 0)

    def test_saved_retention_roundtrip_and_actual_extra_signal(self):
        group = "WEBGL50"
        with patch.object(new, "encode_train", side_effect=AssertionError("no refit")):
            m, training = new.fit_retention(self.job, self.rows, self.meta, self.defs,
                group=group, binding=binding(self.job, group, "R_KEEP_SWAP_V2"), source_modes=self.modes,
                candidate_rows=self.candidates, initial_model=self.models[group], initial_training=self.training[group])
        self.assertEqual(m.status, "FITTED", m.fit.get("failure"))
        self.assertEqual(m.fit["threshold_fit_calls"], 0)
        self.assertIn(webgl.CANDIDATE_ID, {a.atom_id for a in m.atoms})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.json"
            new.save_model(m, path)
            restored = new.load_model(path)
            self.assertEqual(json.dumps(restored.to_dict(), sort_keys=True), json.dumps(m.to_dict(), sort_keys=True))
            with self.assertRaises(ValueError):
                old.load_model(path)
        for oid, meta in self.meta.items():
            result = new.predict_current(restored, oid, self.rows[oid], self.candidates[oid], source_mode="raw_observation_v1")
            self.assertEqual(result["decision"], "MANIPULATION_ALERT" if meta["phase"] == "attack" else "NO_ALERT")

    def test_unknown_and_missing_new_cells_cannot_become_false(self):
        oid = next(i for i, m in self.meta.items() if m["phase"] == "clean_pre")
        cells = deepcopy(self.candidates[oid]); cells[webgl.CANDIDATE_ID] = saved("U")
        p = new.predict_current(self.models["WEBGL50"], oid, self.rows[oid], cells, source_mode="raw_observation_v1")
        self.assertEqual(p["decision"], "INSUFFICIENT_EVIDENCE")
        del cells[webgl.CANDIDATE_ID]
        p = new.predict_current(self.models["WEBGL50"], oid, self.rows[oid], cells, source_mode="raw_observation_v1")
        self.assertEqual(p["decision"], "FAILED")
        all_cells = deepcopy(self.candidates); del all_cells[oid][webgl.CANDIDATE_ID]
        with self.assertRaisesRegex(ValueError, "SAVED_WEBGL1_CELL_REQUIRED"):
            new.project_rows(self.rows, self.defs, "WEBGL50", source_modes=self.modes, candidate_rows=all_cells)

    def test_wrong_group_or_fold_initializer_and_test_rows_rejected(self):
        with patch.object(new, "retain_semantic", side_effect=AssertionError("must not select")):
            with self.assertRaises(PermissionError):
                new.fit_retention(self.job, self.rows, self.meta, self.defs, group="WEBGL50",
                    binding=binding(self.job, "WEBGL50", "R_KEEP_SWAP_V2"), source_modes=self.modes,
                    candidate_rows=self.candidates, initial_model=self.models["BASE49"], initial_training=self.training["BASE49"])
        with patch.object(new, "encode_train", side_effect=AssertionError("must not fit")):
            with self.assertRaises(PermissionError):
                new.fit_sparse(self.job, self.rows | {"fixture-outer": {}}, self.meta, self.defs,
                    group="WEBGL50", binding=binding(self.job, "WEBGL50", "GREEDY_SEMANTIC_V2"),
                    source_modes=self.modes, candidate_rows=self.candidates)
        with self.assertRaises(ValueError):
            replace(self.models["WEBGL50"], fit=self.models["WEBGL50"].fit | {"capacity_profile": PROFILE | {"max_clauses": 8}})

    def test_constant_false_candidate_does_not_force_selection(self):
        candidates = deepcopy(self.candidates)
        for cells in candidates.values():
            cells[webgl.CANDIDATE_ID] = saved("F")
        m, _ = new.fit_sparse(self.job, self.rows, self.meta, self.defs, group="WEBGL50",
            binding=binding(self.job, "WEBGL50", "GREEDY_SEMANTIC_V2"), source_modes=self.modes,
            candidate_rows=candidates)
        self.assertEqual(m.clauses, self.models["BASE49"].clauses)
        self.assertNotIn(webgl.CANDIDATE_ID, {a.atom_id for a in m.atoms})


if __name__ == "__main__":
    unittest.main()
