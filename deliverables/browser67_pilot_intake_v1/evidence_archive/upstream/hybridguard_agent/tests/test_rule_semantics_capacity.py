"""Capacity-only synthetic checks; no saved experiment observations are loaded."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_capacity as new
from hybridguard_agent.research import rule_semantics_selector_v2 as old
from hybridguard_agent.research.rule_learning.contracts import cell, contract
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal, RuleModel
from hybridguard_agent.research.rule_learning_v2.capacity import EXPERIMENT, PROFILE, apply_capacity
from hybridguard_agent.tests.test_rule_semantics_retraining import fixture, semantic, LANG, WD
from hybridguard_agent.tests.test_rule_semantics_selector_v2 import binding as old_binding


def binding(job, method):
    return old_binding(job, method) | {"study_version": new.STUDY_VERSION, "phase": new.PHASE,
        "experiment_id": EXPERIMENT, "capacity_profile": PROFILE["profile_id"]}


def independent_signals(n):
    definitions, _, _, _, _ = fixture()
    fields = ("audio_layer.audio_context_supported", "navigator_layer.cookie_enabled", "navigator_layer.online",
              "permissions_layer.permissions_api_supported", "graphics_layer.webgl2_supported",
              "execution_layer.local_storage_available", "execution_layer.session_storage_available",
              "network_api_layer.save_data")[:n]
    names = []
    for field in fields:
        field = "app.web_data." + field
        name = "CONTROL:" + field + ":EQ:True"
        definitions["atoms"].append({"atom_id": name, "family": "CONTROL_FIELD:" + field,
            "surfaces": ["app_web67"], "sources": ["SYNTHETIC"], "aliases": [name],
            "orientation": "CONTROL_EQUALITY", "provenance": {"field": field, "equals": True,
                "encoder": "BOOL_EQ_TRUE", "predicate_version": "r01-fixed-control-equality-v1"}})
        definitions["single_surface_allowlists"]["app_web67"].append(name)
        names.append(name)
    rows, meta, candidates = {}, {}, {}
    for k in range(n):
        for repeat in range(3):
            for phase in ("clean_pre", "attack", "clean_post"):
                i = f"synthetic-capacity-{k}-{repeat}-{phase}"
                rows[i] = {a["atom_id"]: ({"value": 1, "available": True, "evaluation_status": "OK"}
                           if a["atom_id"].startswith("UNFITTED_CONTROL:") else cell("F")) for a in definitions["atoms"]}
                rows[i][names[k]] = cell("T" if phase == "attack" else "F")
                meta[i] = {"supervised_label": int(phase == "attack"), "phase": phase,
                    "bundle_id": f"fixture-{k}", "triplet_id": f"{k}-{repeat}",
                    "config_id": f"fixture-config-{k}", "environment_group_id": "fixture-env"}
                candidates[i] = {LANG: semantic(LANG, "F"), WD: semantic(WD, "F")}
                candidates[i][WD]["diagnostics"]["mode"] = "raw_observation_v1"
    job = {"fold_id": "capacity-fixture-fold", "train_ids": list(rows), "outer_test_ids": ["fixture-outer"],
           "representation": "W0", "capacity_profile": PROFILE["profile_id"]}
    return definitions, job, rows, meta, candidates


class CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.job, cls.rows, cls.meta, cls.candidates = independent_signals(7)
        cls.kwargs = {"group": "LANG_ADD_WD_REPLACE", "source_modes": dict.fromkeys(cls.rows, "raw_observation_v1"),
                      "candidate_rows": cls.candidates}
        cls.six, cls.six_training = old.fit_sparse(cls.job, cls.rows, cls.meta, cls.defs,
            binding=old_binding(cls.job, "GREEDY_SEMANTIC_V2"), **cls.kwargs)
        cls.seven, cls.seven_training = new.fit_sparse(cls.job, cls.rows, cls.meta, cls.defs,
            binding=binding(cls.job, "GREEDY_SEMANTIC_V2"), **cls.kwargs)

    def test_only_registered_capacity_fields_change(self):
        original_search, original_grammar = contract("learning_search_space"), contract("candidate_grammar")
        problem = SimpleNamespace(search=original_search, grammar=original_grammar)
        apply_capacity(problem)
        expected_search, expected_grammar = deepcopy(original_search), deepcopy(original_grammar)
        expected_search["constraints"].update(max_clauses=7, max_complexity_primary=14)
        expected_search["algorithms"]["GREEDY_OR"]["max_additions"] = 7
        expected_grammar["composition"]["max_selected_clauses"] = 7
        self.assertEqual((problem.search, problem.grammar), (expected_search, expected_grammar))
        self.assertEqual(original_search, contract("learning_search_space"))
        self.assertEqual(original_grammar, contract("candidate_grammar"))

    def test_seventh_independent_signal_selected_with_unchanged_prefix_and_encoder(self):
        self.assertEqual((self.six.status, self.seven.status), ("FITTED", "FITTED"))
        self.assertEqual((len(self.six.clauses), len(self.seven.clauses)), (6, 7))
        self.assertEqual(self.seven.encoder, self.six.encoder)
        self.assertEqual(self.seven_training["support"], self.six_training["support"])
        self.assertEqual(self.seven_training["semantic_catalog"], self.six_training["semantic_catalog"])
        self.assertEqual(self.seven_training["trace"][:6], self.six_training["trace"])
        self.assertEqual(self.seven.fit["training_result"]["macro_tpr"]["value"], 1.0)

    def test_retention_roundtrip_and_seventh_literal_inference(self):
        with patch.object(new, "encode_train", side_effect=AssertionError("no refit")):
            model, training = new.fit_retention(self.job, self.rows, self.meta, self.defs,
                binding=binding(self.job, "R_KEEP_SWAP_V2"), initial_model=self.seven,
                initial_training=self.seven_training, **self.kwargs)
        self.assertEqual(model.status, "FITTED", model.fit.get("failure"))
        self.assertEqual(model.clauses, self.seven.clauses)
        self.assertEqual(model.fit["threshold_fit_calls"], 0)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "seven.json"
            new.save_model(model, path)
            restored = new.load_model(path)
            self.assertEqual(json.dumps(restored.to_dict(), sort_keys=True),
                             json.dumps(model.to_dict(), sort_keys=True))
            for i, m in self.meta.items():
                prediction = new.predict_current(restored, i, self.rows[i], self.candidates[i], source_mode="raw_observation_v1")
                self.assertEqual(prediction["decision"], "MANIPULATION_ALERT" if m["phase"] == "attack" else "NO_ALERT")
            with self.assertRaises(ValueError):
                RuleModel.from_dict(json.loads(path.read_text()))

    def test_cap7_does_not_widen_old_model_or_allow_eighth_clause(self):
        with self.assertRaisesRegex(ValueError, "EXCEEDS_R01_BUDGET"):
            RuleModel(self.seven.method_id, self.seven.status, self.seven.clauses, self.seven.atoms,
                      self.seven.binding, self.seven.view, self.seven.fit, encoder=self.seven.encoder)
        extra = Atom("fixture-extra", "fixture-extra", ("app_web67",), ("SYNTHETIC",), ("fixture-extra",))
        with self.assertRaisesRegex(ValueError, "EXCEEDS_REGISTERED_CAPACITY"):
            replace(self.seven, clauses=self.seven.clauses + (Clause((Literal(extra.atom_id),)),),
                    atoms=self.seven.atoms + (extra,))
        with self.assertRaisesRegex(ValueError, "CAPACITY_MODEL_IDENTITY"):
            replace(self.seven, fit=self.seven.fit | {"capacity_profile": PROFILE | {"max_clauses": 8}})

    def test_old_initializer_or_wrong_profile_rejected_before_fit(self):
        with patch.object(new, "encode_train", side_effect=AssertionError("must not fit")):
            with self.assertRaises(PermissionError):
                new.fit_sparse(self.job | {"capacity_profile": "wrong"}, self.rows, self.meta, self.defs,
                    binding=binding(self.job, "GREEDY_SEMANTIC_V2"), **self.kwargs)
        with patch.object(new, "retain_semantic", side_effect=AssertionError("must not select")):
            with self.assertRaises(TypeError):
                new.fit_retention(self.job, self.rows, self.meta, self.defs,
                    binding=binding(self.job, "R_KEEP_SWAP_V2"), initial_model=self.six,
                    initial_training=self.six_training, **self.kwargs)

    def test_unknown_failure_and_raw_only_mode_remain_distinct(self):
        i = next(i for i, m in self.meta.items() if m["phase"] == "clean_pre")
        aid = self.seven.atoms[0].atom_id
        for state, expected in (("U", "INSUFFICIENT_EVIDENCE"), ("FAILED", "FAILED")):
            row = deepcopy(self.rows[i]); row[aid] = cell(state)
            p = new.predict_current(self.seven, i, row, self.candidates[i], source_mode="raw_observation_v1")
            self.assertEqual(p["decision"], expected)
        with self.assertRaises(PermissionError):
            new.predict_current(self.seven, i, self.rows[i], self.candidates[i], source_mode="legacy_projection_v1")


if __name__ == "__main__":
    unittest.main()
