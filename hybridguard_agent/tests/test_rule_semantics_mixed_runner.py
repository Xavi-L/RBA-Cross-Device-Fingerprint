"""Runner gates and access ordering using invented IDs and a fake engine only."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("mixed_runner_for_test", ROOT / "deliverables/rule_semantics_retraining_preparation_v1/run_experiment.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def fixture():
    index, metadata, historical = [], {}, []
    for group, size in (("env-1", 27), ("env-2", 18), ("env-3", 117), ("new-env", 18)):
        mode = runner.MODES[int(group == "new-env")]
        for n in range(size):
            oid = "synthetic-" + group + "-" + str(n)
            phase = ("clean_pre", "attack", "clean_post")[n % 3]
            index.append({"opaque_id": oid, "observation_mode": mode})
            m = {"opaque_id": oid, "environment_group_id": group, "bundle_id": group,
                 "triplet_id": group + ":" + str(n // 3), "phase": phase, "config_id": "synthetic-config"}
            if mode == runner.MODES[0]:
                historical.append(oid)
                m["supervised_label"] = int(phase == "attack")
            else:
                m.update(observation_mode=mode, proposed_supervised_member=True,
                         proposed_supervised_label=int(phase == "attack"), fit_permission="DENIED_PREPARATION_ONLY")
            metadata[oid] = m
    ids = sorted(metadata)
    folds = []
    for n, group in enumerate(("env-1", "env-2", "env-3", "new-env"), 1):
        test = [i for i in ids if metadata[i]["environment_group_id"] == group]
        folds.append({"fold_id": "MIXED-LOEO-v1-" + str(n).zfill(2), "heldout_environment": group,
                      "train_ids": sorted(set(ids) - set(test)), "outer_test_ids": test})
    jobs = []
    for group in runner.GROUPS:
        for fold in folds:
            for stage in ("SPARSE", "RETENTION"):
                jobs.append({"job_id": group + "__" + fold["fold_id"] + "__" + stage,
                    "group_id": group, "stage": stage, "fold_id": fold["fold_id"],
                    "train_ids": fold["train_ids"], "outer_test_ids": fold["outer_test_ids"],
                    "initializer": group + "__" + fold["fold_id"] + "__SPARSE" if stage == "RETENTION" else None,
                    "max_prediction_calls": len(fold["outer_test_ids"]) if stage == "RETENTION" else 0})
    budget = {**runner.LIMITS, "prior_ledger_ref": "SYNTHETIC", "base_fit_jobs": 177,
              "base_charged_seconds": 100.0, "registered_fit_reservation": 0}
    contract = {"schema_version": "rsr-mixed-execution-registration-v1", "study_version": runner.STUDY,
        "phase": runner.PHASE, "engine_version": runner.ENGINE_VERSION, "experiment_id": "SYNTHETIC",
        "registered_at": "SYNTHETIC", "training_authorized": False, "admission_authorized": False,
        "sample_ids": ids, "source_modes": {r["opaque_id"]: r["observation_mode"] for r in index},
        "jobs": jobs, "folds": folds, "budget": budget, "blocking_reasons": [],
        "source_prepared_directory": "SYNTHETIC", "evaluation_role": "SYNTHETIC_TEST_ONLY"}
    auth = {k: deepcopy(contract[k]) for k in ("study_version", "phase", "experiment_id", "registered_at", "sample_ids", "jobs", "budget")}
    auth.update(schema_version="rsr-mixed-execution-authorization-v1", training_authorized=False,
                admission_authorized=False, authorization_ref=None)
    return index, metadata, historical, contract, auth


class FakeModel:
    def __init__(self, ids):
        self.fit, self.status, self.model_id = {"train_ids": ids}, "FITTED", "SYNTHETIC-MODEL"

    def to_dict(self):
        return {"fit": self.fit, "status": self.status, "model_id": self.model_id}


class FakeEngine:
    """No selector, encoder, model implementation or real fit is imported."""
    def __init__(self, timeline):
        self.timeline = timeline

    def fit_sparse(self, job, raw, metadata, definitions, **kwargs):
        self.timeline.append(("FAKE_FIT", job["job_id"]))
        assert set(raw) == set(metadata) == set(kwargs["source_modes"]) == set(job["train_ids"])
        assert not set(raw) & set(job["outer_test_ids"])
        return FakeModel(job["train_ids"]), {"synthetic": True}

    def fit_retention(self, job, raw, metadata, definitions, **kwargs):
        assert kwargs["initial_model"].fit["train_ids"] == job["train_ids"]
        return self.fit_sparse(job, raw, metadata, definitions, **kwargs)

    def save_model(self, model, path):
        runner.write(path, model.to_dict())

    def load_model(self, path):
        self.timeline.append(("MODEL_RELOAD", str(path)))
        return FakeModel(runner.read(path)["fit"]["train_ids"])

    def predict_current(self, model, oid, raw, candidate_cells=None, *, source_mode):
        self.timeline.append(("FAKE_PREDICT", oid))
        return {"opaque_id": oid, "decision": "NO_ALERT"}


class MixedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.index, self.metadata, self.old, self.contract, self.auth = fixture()

    def authorized_fixture(self):
        self.auth.update(training_authorized=True, admission_authorized=True, authorization_ref="SYNTHETIC_ONLY")

    def test_exact_plan_and_no_silent_old_162_or_extra_control(self):
        out = runner.validate_plan(self.index, self.metadata, self.contract["folds"], self.contract["jobs"], self.old)
        self.assertEqual((out["members"], out["jobs"], out["prospective_predictions"]), (180, 16, 360))
        with self.assertRaises(ValueError):
            runner.validate_plan(self.index[:162], self.metadata, self.contract["folds"], self.contract["jobs"], self.old)

    def test_registration_flag_or_preparation_label_cannot_authorize(self):
        self.contract["training_authorized"] = True
        with self.assertRaisesRegex(ValueError, "EXPLICIT_EXECUTION"):
            runner.execution_gate(self.contract, self.auth)
        proposed = next(m for m in self.metadata.values() if m.get("proposed_supervised_member"))
        with self.assertRaisesRegex(ValueError, "PROPOSED_LABELS"):
            runner._admitted_metadata(proposed, self.auth)

    def test_infeasible_goal_has_no_authorization_flag_bypass(self):
        self.authorized_fixture()
        self.contract["blocking_reasons"] = ["BLOCKED_FOR_STATED_WEBDRIVER_LEARNING_GOAL"]
        with patch.object(runner, "budget_snapshot", return_value=self.contract["budget"]):
            with self.assertRaisesRegex(ValueError, "FEASIBILITY_BLOCKER"):
                runner.execution_gate(self.contract, self.auth)

    def test_execution_layout_and_source_mode_binding_mismatch_rejected(self):
        self.authorized_fixture()
        with patch.object(runner, "budget_snapshot", return_value=self.contract["budget"]), \
                patch.object(runner, "coverage_review", return_value={"blocking_reasons": []}):
            runner.execution_gate(self.contract, self.auth)
            self.contract["source_modes"][self.old[0]] = "raw_observation_v1"
            with self.assertRaisesRegex(ValueError, "MIXED_180"):
                runner.execution_gate(self.contract, self.auth)
        bad = deepcopy(self.contract)
        bad["jobs"][1]["initializer"] = bad["jobs"][2]["job_id"]
        with self.assertRaisesRegex(ValueError, "INITIALIZER"):
            runner.validate_execution_layout(bad)

    def test_direct_worker_and_run_reject_unauthorized_before_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            runner.write(d / "CONTRACT.json", self.contract)
            runner.write(d / "auth.json", self.auth)
            before = sorted(d.iterdir())
            for action in (lambda: runner.run(d, d / "auth.json"),
                           lambda: runner.worker(d, d / "auth.json", self.contract["jobs"][0]["job_id"])):
                with self.assertRaisesRegex(ValueError, "EXPLICIT_EXECUTION"):
                    action()
            self.assertEqual(sorted(d.iterdir()), before)

    def test_fake_worker_train_freeze_test_close_then_label_order(self):
        self.authorized_fixture()
        timeline = []
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            for part in ("inputs", "evaluation"):
                (d / part).mkdir()
            runner.write(d / "CONTRACT.json", self.contract)
            runner.write(d / "auth.json", self.auth)
            runner.write(d / "RUN_STARTED.json", {"synthetic": True})
            runner.write(d / "DEFINITIONS.json", {})
            for oid in self.contract["sample_ids"]:
                mode = self.contract["source_modes"][oid]
                base = {name: {"value": 2 if name.startswith("UNFITTED_CONTROL:") else False,
                              "available": True, "evaluation_status": "OK", "reason": "SYNTHETIC"}
                        for name in runner.W0_ATOM_IDS}
                candidates = {name: {"candidate_id": name, "version": "1.0.0", "value": False,
                    "available": True, "evaluation_status": "OK", "reason": "SYNTHETIC",
                    "diagnostics": {"mode": mode} if name == runner.WD else {}}
                    for name in (runner.LANG, runner.WD)}
                runner.write(d / "inputs" / (oid + ".json"), {"opaque_id": oid,
                    "observation_mode": mode, "features": base, "candidate_cells": candidates})
                runner.write(d / "evaluation" / (oid + ".json"), self.metadata[oid])
            original_read = runner.read
            def tracked_read(path):
                timeline.append(("READ", str(path)))
                return original_read(path)
            with patch.object(runner, "budget_snapshot", return_value=self.contract["budget"]), \
                    patch.object(runner, "coverage_review", return_value={"blocking_reasons": []}), \
                    patch.object(runner, "read", side_effect=tracked_read):
                engine = FakeEngine(timeline)
                first, second = self.contract["jobs"][:2]
                sparse = runner.worker(d, d / "auth.json", first["job_id"], engine=engine)
                self.assertEqual(sparse["actual_prediction_calls"], 0)
                timeline.clear()
                retained = runner.worker(d, d / "auth.json", second["job_id"], engine=engine)
                self.assertEqual(retained["actual_prediction_calls"], len(second["outer_test_ids"]))
                self.assertEqual(retained["missing_prediction_positions"], 0)
                fit_index = next(i for i, (event, _) in enumerate(timeline) if event == "FAKE_FIT")
                frozen = next(i for i, (event, path) in enumerate(timeline) if event == "MODEL_RELOAD" and second["job_id"] in path)
                predict_indices = [i for i, (event, _) in enumerate(timeline) if event == "FAKE_PREDICT"]
                for oid in second["outer_test_ids"]:
                    feature = next(i for i, item in enumerate(timeline) if item == ("READ", str(d / "inputs" / (oid + ".json"))))
                    label = next(i for i, item in enumerate(timeline) if item == ("READ", str(d / "evaluation" / (oid + ".json"))))
                    self.assertGreater(feature, frozen)
                    self.assertGreater(label, max(predict_indices))
                self.assertLess(fit_index, frozen)
                events = original_read(d / "trials" / second["job_id"] / "access_log.json")
                names = [e["event"] for e in events]
                self.assertLess(names.index("PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN"), names.index("HELDOUT_METADATA_JOINED_AFTER_CLOSE"))
                with self.assertRaises(FileExistsError):
                    runner.worker(d, d / "auth.json", second["job_id"], engine=engine)


if __name__ == "__main__":
    unittest.main()
