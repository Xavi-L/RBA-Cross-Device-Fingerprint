"""Hand-built synthetic engineering checks; no real records or candidates.

Small synthetic fits exercise existing mathematical kernels. Only temporary
synthetic models are saved. No historical/local-campaign inputs are loaded.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_mixed_retraining as engine
from hybridguard_agent.research.rule_learning.contracts import state
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal, save_model
from hybridguard_agent.research.rule_learning_v2 import adapter, retention
from hybridguard_agent.tests.test_rule_semantics_retraining import fixture, semantic, LANG, WD, LANG_NUMERIC, OLD_WD


def binding(job, group, method="GREEDY_OR"):
    return {"study_version": engine.STUDY_VERSION, "phase": engine.PHASE,
            "group_id": group, "method_id": method, "operating_point": "OP05",
            "fold_id": job["fold_id"], "evaluation_role": "SYNTHETIC_ENGINEERING_ONLY"}


def mixed_fixture():
    definitions, job, rows, metadata, candidates = fixture()
    modes = {}
    for sid, meta in metadata.items():
        mode = "raw_observation_v1" if int(meta["triplet_id"]) < 3 else "legacy_projection_v1"
        modes[sid] = mode
        wd_state = "T" if meta["phase"] == "attack" else "F" if mode == "raw_observation_v1" else "U"
        candidates[sid][WD] = semantic(WD, wd_state)
        candidates[sid][WD]["diagnostics"]["mode"] = mode
    return definitions, job, rows, metadata, candidates, modes


class MixedRetrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.job, cls.rows, cls.metadata, cls.candidates, cls.modes = mixed_fixture()
        cls.sparse_models = {}
        for group in engine.GROUPS:
            cls.sparse_models[group] = engine.fit_sparse(
                cls.job, cls.rows, cls.metadata, cls.defs, group=group,
                binding=binding(cls.job, group), source_modes=cls.modes,
                candidate_rows=cls.candidates if group != "BASE" else None)

    def retain(self, group="LANG_ADD_WD_REPLACE", **overrides):
        initial, training = self.sparse_models[group]
        arguments = {"group": group, "binding": binding(self.job, group, "R_KEEP_V1"),
                     "source_modes": self.modes,
                     "candidate_rows": self.candidates if group != "BASE" else None,
                     "initial_model": initial, "initial_training": training}
        arguments.update(overrides)
        return engine.fit_retention(self.job, self.rows, self.metadata, self.defs, **arguments)

    def test_definitions_preserve_base_and_length_with_explicit_mixed_provenance(self):
        original = deepcopy(self.defs)
        self.assertEqual(engine.group_definitions(self.defs, "BASE"), self.defs)
        revised = engine.group_definitions(self.defs, "LANG_ADD_WD_REPLACE")
        names = set(revised["single_surface_allowlists"]["app_web67"])
        self.assertEqual(names, (set(self.defs["single_surface_allowlists"]["app_web67"]) - {OLD_WD}) | {LANG, WD})
        self.assertIn(LANG_NUMERIC, names)
        provenance = next(a["provenance"] for a in revised["atoms"] if a["atom_id"] == WD)
        self.assertEqual(provenance["mode"], "PER_RECORD_EXPLICIT_LEGACY_OR_RAW")
        self.assertEqual(set(provenance["mode_gate_versions"]), set(engine.SOURCE_MODES))
        self.assertEqual(self.defs, original)
        self.assertIs(engine.encode_train, adapter.encode_train)
        self.assertIs(engine.retain, retention.retain)

    def test_projection_preserves_four_states_and_modes_are_not_features(self):
        sid = self.job["train_ids"][0]
        raw = {sid: deepcopy(self.rows[sid])}
        for value in ("T", "F", "U", "FAILED"):
            with self.subTest(value=value):
                cells = {LANG: semantic(LANG, "F"), WD: semantic(WD, value)}
                cells[WD]["diagnostics"]["mode"] = "raw_observation_v1"
                before = deepcopy((raw, cells))
                projected = engine.project_rows(raw, self.defs, "LANG_ADD_WD_REPLACE",
                    source_modes={sid: "raw_observation_v1"}, candidate_rows={sid: cells})
                self.assertEqual((raw, cells), before)
                self.assertEqual(set(projected[sid]), (set(raw[sid]) - {OLD_WD}) | {LANG, WD})
                if value == "FAILED":
                    self.assertEqual(projected[sid][WD]["evaluation_status"], "FAILED")
                    self.assertIsNone(projected[sid][WD]["value"])
                else:
                    self.assertEqual(state(projected[sid][WD]), value)
                self.assertEqual(projected[sid][LANG_NUMERIC], raw[sid][LANG_NUMERIC])
        for mode in engine.SOURCE_MODES:
            modes = {sid: mode}
            self.assertEqual(engine.project_rows(raw, self.defs, "BASE", source_modes=modes), raw)

    def test_members_and_explicit_modes_fail_before_encoder(self):
        modes_missing = dict(self.modes)
        del modes_missing[self.job["train_ids"][0]]
        modes_extra = self.modes | {"SYNTHETIC-heldout": "raw_observation_v1"}
        modes_invalid = self.modes | {self.job["train_ids"][0]: "auto"}
        with patch.object(engine, "encode_train", side_effect=AssertionError("must not fit")) as encode:
            for modes in (None, modes_missing, modes_extra, modes_invalid):
                with self.subTest(modes=modes), self.assertRaises(PermissionError):
                    engine.fit_sparse(self.job, self.rows, self.metadata, self.defs, group="BASE",
                                      binding=binding(self.job, "BASE"), source_modes=modes)
            overlap = self.job | {"outer_test_ids": [self.job["train_ids"][0]]}
            with self.assertRaises(PermissionError):
                engine.fit_sparse(overlap, self.rows, self.metadata, self.defs, group="BASE",
                                  binding=binding(overlap, "BASE"), source_modes=self.modes)
            with self.assertRaises(PermissionError):
                engine.fit_sparse(self.job, self.rows, self.metadata, self.defs, group="BASE",
                                  binding=binding(self.job, "BASE"), source_modes=self.modes,
                                  candidate_rows=self.candidates)
            with self.assertRaises(PermissionError):
                engine.fit_sparse(self.job, self.rows, self.metadata, self.defs, group="BASE",
                                  binding=binding(self.job, "BASE") | {"study_version": "rule-semantics-combination-v1"},
                                  source_modes=self.modes)
            encode.assert_not_called()

    def test_missing_or_mismatched_cell_mode_is_not_supplied_by_sidecar(self):
        sid = self.job["train_ids"][0]
        for value in (None, "legacy_projection_v1", "auto"):
            with self.subTest(mode=value):
                candidates = deepcopy(self.candidates)
                if value is None:
                    del candidates[sid][WD]["diagnostics"]["mode"]
                else:
                    candidates[sid][WD]["diagnostics"]["mode"] = value
                with patch.object(engine, "encode_train", side_effect=AssertionError("must not fit")) as encode:
                    with self.assertRaises(PermissionError):
                        engine.fit_sparse(self.job, self.rows, self.metadata, self.defs,
                            group="LANG_ADD_WD_REPLACE", binding=binding(self.job, "LANG_ADD_WD_REPLACE"),
                            source_modes=self.modes, candidate_rows=candidates)
                    encode.assert_not_called()

    def test_both_stages_record_exact_modes_and_retention_does_not_refit(self):
        for group in engine.GROUPS:
            with self.subTest(group=group):
                initial, initial_training = self.sparse_models[group]
                with patch.object(engine, "encode_train", side_effect=AssertionError("must reuse encoder")), \
                     patch.object(engine, "greedy", side_effect=AssertionError("must reuse sparse stage")):
                    model, training = self.retain(group)
                self.assertEqual(model.encoder, initial.encoder)
                self.assertEqual(model.fit["source_mode_manifest"], initial.fit["source_mode_manifest"])
                self.assertEqual(training["source_mode_manifest"], initial_training["source_mode_manifest"])
                self.assertEqual(training["source_mode_manifest"]["per_record"], self.modes)
                self.assertEqual(model.fit["threshold_fit_calls"], 0)
                self.assertEqual(model.fit["actual_sparse_fit_invocations"], 0)
                self.assertEqual(model.fit["actual_retention_invocations"], 1)
                self.assertFalse(model.view["source_mode_feature"])
                self.assertTrue(all(op["ids"] == self.job["train_ids"] for op in training["access_operations"]))
                self.assertNotIn("numeric_thresholds", [op["operation"] for op in training["access_operations"]])
                for current in (initial, model):
                    with tempfile.TemporaryDirectory() as directory:
                        destination = Path(directory) / "synthetic-model.json"
                        engine.save_model(current, destination)
                        restored = engine.load_model(destination)
                        self.assertEqual(json.dumps(restored.to_dict(), sort_keys=True),
                                         json.dumps(current.to_dict(), sort_keys=True))

    def test_retention_rejects_wrong_initial_group_train_encoder_modes_and_identity(self):
        initial, training = self.sparse_models["LANG_ADD_WD_REPLACE"]
        changed_modes = dict(self.modes)
        sid = self.job["train_ids"][0]
        changed_modes[sid] = "legacy_projection_v1"
        changed_candidates = deepcopy(self.candidates)
        changed_candidates[sid][WD]["diagnostics"]["mode"] = "legacy_projection_v1"
        alternatives = [
            {"initial_model": self.sparse_models["BASE"][0], "initial_training": self.sparse_models["BASE"][1]},
            {"initial_model": replace(initial, binding=initial.binding | {"study_version": "rule-semantics-combination-v1"})},
            {"initial_model": replace(initial, fit=initial.fit | {"train_ids": self.job["train_ids"][:-1]})},
            {"initial_model": replace(initial, encoder=initial.encoder | {"version": "invented"})},
            {"source_modes": changed_modes, "candidate_rows": changed_candidates},
            {"initial_training": training | {"source_mode_manifest": {}}},
        ]
        with patch.object(engine, "retain", side_effect=AssertionError("must not retain")) as retained:
            for alternative in alternatives:
                with self.subTest(keys=list(alternative)), self.assertRaises((ValueError, PermissionError)):
                    self.retain(**alternative)
            retained.assert_not_called()

    def test_predict_requires_mode_and_legacy_only_model_metadata_is_rejected(self):
        initial, _ = self.sparse_models["LANG_ADD_WD_REPLACE"]
        atom = next(a for a in engine.group_definitions(self.defs, "LANG_ADD_WD_REPLACE")["atoms"] if a["atom_id"] == WD)
        wd_atom = Atom(**dict(atom, surfaces=tuple(atom["surfaces"]), sources=tuple(atom["sources"]), aliases=tuple(atom["aliases"])))
        # A synthetic WD-only structure isolates prediction-mode validation from
        # which valid sparse literal the unchanged tie-break happens to select.
        model = replace(initial, status="FITTED", clauses=(Clause((Literal(WD),)),), atoms=(wd_atom,))
        cells = {WD: semantic(WD, "F")}
        cells[WD]["diagnostics"]["mode"] = "raw_observation_v1"
        with patch.object(engine, "predict", wraps=engine.predict) as predictor:
            result = engine.predict_current(model, "SYNTHETIC-new-row", {}, cells, source_mode="raw_observation_v1")
            self.assertEqual(result["source_observation_mode"], "raw_observation_v1")
            features = predictor.call_args.args[2]["features"]
            self.assertEqual(set(features), {WD})
            self.assertNotIn("source_mode", features)
        with self.assertRaises(PermissionError):
            engine.predict_current(model, "SYNTHETIC-new-row", {}, cells, source_mode="auto")
        mismatch = engine.predict_current(model, "SYNTHETIC-new-row", {}, cells, source_mode="legacy_projection_v1")
        self.assertEqual(mismatch["decision"], "FAILED")
        old_atom = replace(wd_atom, provenance=wd_atom.provenance | {"mode": "legacy_projection_v1"})
        invalid = replace(model, atoms=(old_atom,))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-legacy-model.json"
            save_model(invalid, path)
            with self.assertRaises(PermissionError):
                engine.load_model(path)
        with self.assertRaises(PermissionError):
            engine.predict_current(invalid, "SYNTHETIC-new-row", {}, cells, source_mode="raw_observation_v1")

    def test_failures_are_recorded_once_without_fallback(self):
        with patch.object(engine, "greedy", side_effect=RuntimeError("SYNTHETIC sparse failure")) as selected:
            model, training = engine.fit_sparse(self.job, self.rows, self.metadata, self.defs,
                group="BASE", binding=binding(self.job, "BASE"), source_modes=self.modes)
        self.assertEqual(selected.call_count, 1)
        self.assertEqual(model.status, "FAILED")
        self.assertEqual(model.clauses, ())
        self.assertEqual(training["failure"]["stage"], "GREEDY_SELECTION")
        with patch.object(engine, "retain", side_effect=RuntimeError("SYNTHETIC retention failure")) as retained:
            model, training = self.retain()
        self.assertEqual(retained.call_count, 1)
        self.assertEqual(model.status, "FAILED")
        self.assertEqual(model.clauses, ())
        self.assertEqual(training["failure"]["stage"], "RKEEP_RETENTION")


if __name__ == "__main__":
    unittest.main()
