"""Synthetic CAP8 boundaries; no captured observations or saved results loaded."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_webgl1 as cap7
from hybridguard_agent.research import rule_semantics_webgl1_cap8 as cap8
from hybridguard_agent.research import webgl1_selector_integration as webgl
from hybridguard_agent.research.rule_learning.contracts import cell, contract
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal
from hybridguard_agent.research.rule_learning_v2 import capacity as capacity7
from hybridguard_agent.tests.test_rule_semantics_capacity import independent_signals
from hybridguard_agent.tests.test_rule_semantics_webgl1 import binding as binding7, saved


def binding(job, group, method):
    return binding7(job, group, method) | {
        "study_version": cap8.STUDY_VERSION, "phase": cap8.PHASE,
        "experiment_id": cap8.EXPERIMENT, "capacity_profile": cap8.PROFILE["profile_id"]}


class WebGLCap8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_profile = deepcopy(capacity7.PROFILE)
        cls.old_apply = capacity7.apply_capacity
        cls.defs, cls.job7, cls.rows, cls.meta, cls.candidates = independent_signals(8)
        cls.job8 = cls.job7 | {"capacity_profile": cap8.PROFILE["profile_id"]}
        for candidates in cls.candidates.values():
            candidates[webgl.CANDIDATE_ID] = saved("F")
        cls.modes = dict.fromkeys(cls.rows, "raw_observation_v1")
        cls.old, cls.old_training = cap7.fit_sparse(cls.job7, cls.rows, cls.meta, cls.defs,
            group="BASE49", binding=binding7(cls.job7, "BASE49", "GREEDY_SEMANTIC_V2"),
            source_modes=cls.modes, candidate_rows=cls.candidates)
        cls.models, cls.training = {}, {}
        for group in cap8.GROUPS:
            cls.models[group], cls.training[group] = cap8.fit_sparse(cls.job8, cls.rows, cls.meta, cls.defs,
                group=group, binding=binding(cls.job8, group, "GREEDY_SEMANTIC_V2"),
                source_modes=cls.modes, candidate_rows=cls.candidates)

    def test_only_four_capacity_fields_change_and_old_globals_stay_frozen(self):
        before = SimpleNamespace(search=contract("learning_search_space"), grammar=contract("candidate_grammar"))
        capacity7.apply_capacity(before)
        expected_search, expected_grammar = deepcopy(before.search), deepcopy(before.grammar)
        after = cap8.apply_capacity(SimpleNamespace(search=before.search, grammar=before.grammar))
        expected_search["constraints"].update(max_clauses=8, max_complexity_primary=16)
        expected_search["algorithms"]["GREEDY_OR"]["max_additions"] = 8
        expected_grammar["composition"]["max_selected_clauses"] = 8
        self.assertEqual((after.search, after.grammar), (expected_search, expected_grammar))
        self.assertEqual(before.search["constraints"]["max_clauses"], 7)
        self.assertEqual(before.grammar["composition"]["max_selected_clauses"], 7)
        self.assertEqual(capacity7.PROFILE, self.old_profile)
        self.assertIs(capacity7.apply_capacity, type(self).old_apply)
        self.assertIs(cap7.PROFILE, capacity7.PROFILE)
        self.assertIsNot(cap8.PROFILE, cap7.PROFILE)
        self.assertIsNot(cap8.apply_capacity, cap7.apply_capacity)
        for name in ("greedy_semantic", "retain_semantic", "encode_train", "semantic_catalog"):
            self.assertIs(getattr(cap8, name), getattr(cap7, name))

    def test_eight_selected_without_pool_score_encoder_or_threshold_changes(self):
        model = self.models["BASE49"]
        self.assertEqual((self.old.status, model.status), ("FITTED", "FITTED"))
        self.assertEqual((len(self.old.clauses), len(model.clauses)), (7, 8))
        self.assertEqual(self.old.encoder, model.encoder)
        for key in ("support", "encoded_atoms", "semantic_catalog", "signal_groups"):
            self.assertEqual(self.old_training[key], self.training["BASE49"][key])
        self.assertEqual(self.old_training["trace"], self.training["BASE49"]["trace"][:7])
        for group in cap8.GROUPS:
            self.assertEqual(cap8.group_definitions(self.defs, group), cap7.group_definitions(self.defs, group))
            self.assertEqual(cap8.project_rows(self.rows, self.defs, group, source_modes=self.modes,
                                              candidate_rows=self.candidates),
                             cap7.project_rows(self.rows, self.defs, group, source_modes=self.modes,
                                               candidate_rows=self.candidates))
        self.assertNotIn(webgl.CANDIDATE_ID, {a.atom_id for a in self.models["WEBGL50"].atoms})
        self.assertEqual(self.models["BASE49"].clauses, self.models["WEBGL50"].clauses)

    def test_ninth_clause_and_modified_capacity_profile_rejected(self):
        model = self.models["BASE49"]
        extra = Atom("fixture-extra", "fixture-extra", ("app_web67",), ("SYNTHETIC",), ("fixture-extra",))
        with self.assertRaisesRegex(ValueError, "EXCEEDS_REGISTERED_CAPACITY"):
            replace(model, clauses=model.clauses + (Clause((Literal(extra.atom_id),)),), atoms=model.atoms + (extra,))
        with self.assertRaisesRegex(ValueError, "CAPACITY_MODEL_IDENTITY"):
            replace(model, fit=model.fit | {"capacity_profile": cap8.PROFILE | {"max_clauses": 9}})
        with self.assertRaisesRegex(ValueError, "EXCEEDS_REGISTERED_CAPACITY"):
            cap7.RuleModel(self.old.method_id, "FITTED", model.clauses, model.atoms, self.old.binding,
                           self.old.view, self.old.fit, encoder=self.old.encoder)

    def test_retention_roundtrip_and_cap7_cap8_loaders_reject_each_other(self):
        group = "WEBGL50"
        with patch.object(cap8, "encode_train", side_effect=AssertionError("no threshold refit")):
            model, _ = cap8.fit_retention(self.job8, self.rows, self.meta, self.defs, group=group,
                binding=binding(self.job8, group, "R_KEEP_SWAP_V2"), source_modes=self.modes,
                candidate_rows=self.candidates, initial_model=self.models[group], initial_training=self.training[group])
        self.assertEqual(model.status, "FITTED", model.fit.get("failure"))
        self.assertEqual(len(model.clauses), 8)
        self.assertEqual(model.fit["threshold_fit_calls"], 0)
        with tempfile.TemporaryDirectory() as temp:
            path7, path8 = Path(temp) / "cap7.json", Path(temp) / "cap8.json"
            cap7.save_model(self.old, path7)
            cap8.save_model(model, path8)
            restored = cap8.load_model(path8)
            self.assertEqual(json.dumps(model.to_dict(), sort_keys=True), json.dumps(restored.to_dict(), sort_keys=True))
            with self.assertRaises(ValueError):
                cap8.load_model(path7)
            with self.assertRaises(ValueError):
                cap7.load_model(path8)
        for oid, metadata in self.meta.items():
            result = cap8.predict_current(restored, oid, self.rows[oid], self.candidates[oid], source_mode="raw_observation_v1")
            self.assertEqual(result["decision"], "MANIPULATION_ALERT" if metadata["phase"] == "attack" else "NO_ALERT")

    def test_cross_capacity_group_fold_initializers_and_heldout_rows_rejected(self):
        with patch.object(cap8, "retain_semantic", side_effect=AssertionError("must not select")):
            for initial, training, job, expected in (
                    (self.old, self.old_training, self.job8, TypeError),
                    (self.models["BASE49"], self.training["BASE49"], self.job8, PermissionError),
                    (self.models["WEBGL50"], self.training["WEBGL50"], self.job8 | {"fold_id": "wrong-fold"}, PermissionError)):
                with self.subTest(initial=initial.model_id, fold=job["fold_id"]), self.assertRaises(expected):
                    cap8.fit_retention(job, self.rows, self.meta, self.defs, group="WEBGL50",
                        binding=binding(job, "WEBGL50", "R_KEEP_SWAP_V2"), source_modes=self.modes,
                        candidate_rows=self.candidates, initial_model=initial, initial_training=training)
        with patch.object(cap7, "retain_semantic", side_effect=AssertionError("must not select")), self.assertRaises(TypeError):
            cap7.fit_retention(self.job7, self.rows, self.meta, self.defs, group="BASE49",
                binding=binding7(self.job7, "BASE49", "R_KEEP_SWAP_V2"), source_modes=self.modes,
                candidate_rows=self.candidates, initial_model=self.models["BASE49"], initial_training=self.training["BASE49"])
        with patch.object(cap8, "encode_train", side_effect=AssertionError("must not fit")), self.assertRaises(PermissionError):
            cap8.fit_sparse(self.job8, self.rows | {"fixture-outer": {}}, self.meta, self.defs, group="BASE49",
                binding=binding(self.job8, "BASE49", "GREEDY_SEMANTIC_V2"), source_modes=self.modes,
                candidate_rows=self.candidates)

    def test_unknown_failure_and_raw_only_boundaries_preserved(self):
        oid = next(i for i, m in self.meta.items() if m["phase"] == "clean_pre")
        model = self.models["BASE49"]
        aid = model.atoms[0].atom_id
        for s, expected in (("U", "INSUFFICIENT_EVIDENCE"), ("FAILED", "FAILED")):
            row = deepcopy(self.rows[oid]); row[aid] = cell(s)
            result = cap8.predict_current(model, oid, row, self.candidates[oid], source_mode="raw_observation_v1")
            self.assertEqual(result["decision"], expected)
        cells = deepcopy(self.candidates); cells[oid][webgl.CANDIDATE_ID] = saved("U")
        projected = cap8.project_rows(self.rows, self.defs, "WEBGL50", source_modes=self.modes, candidate_rows=cells)
        self.assertIsNone(projected[oid][webgl.CANDIDATE_ID]["value"])
        self.assertFalse(projected[oid][webgl.CANDIDATE_ID]["available"])
        with self.assertRaises(PermissionError):
            cap8.predict_current(model, oid, self.rows[oid], self.candidates[oid], source_mode="legacy_projection_v1")


if __name__ == "__main__":
    unittest.main()
