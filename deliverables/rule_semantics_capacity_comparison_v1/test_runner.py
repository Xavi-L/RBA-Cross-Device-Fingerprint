"""Synthetic orchestration tests. Never imports or fits the research engine."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("capacity_runner", Path(__file__).with_name("run_comparison.py"))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class FakeEngine:
    """Deterministic file-boundary fixture, not a statistical model or fit."""

    def __init__(self):
        self.calls = []

    def fit_sparse(self, job, rows, labels, definitions, **kwargs):
        assert list(rows) == list(labels) == job["train_ids"]
        assert not set(rows) & set(job["outer_test_ids"])
        assert set(kwargs["source_modes"].values()) == {"raw_observation_v1"}
        assert list(kwargs["candidate_rows"]) == job["train_ids"]
        self.calls.append(("fake_fit", job["job_id"]))
        binding = kwargs["binding"]
        model = SimpleNamespace(fit={"train_ids": job["train_ids"]}, status="FITTED", model_id=job["job_id"],
                                binding=binding, method_id=binding["method_id"],
                                clauses=[{"literals": [{"atom_id": runner.NEW_CANDIDATES[0], "polarity": "POSITIVE"}]}])
        return model, {"synthetic_only": True}

    def fit_retention(self, *args, **kwargs):
        assert kwargs["initial_model"].method_id == "GREEDY_SEMANTIC_V2"
        return self.fit_sparse(*args, **kwargs)

    def save_model(self, model, path):
        self.calls.append(("save", model.model_id))
        runner.write(path, vars(model))

    def load_model(self, path):
        self.calls.append(("load", str(path)))
        return SimpleNamespace(**runner.read(path))

    def predict_current(self, model, oid, features, **kwargs):
        assert self.calls[-1][0] in ("load", "predict")
        self.calls.append(("predict", oid))
        return {"opaque_id": oid, "decision": "MANIPULATION_ALERT" if features["fixture_attack"] else "NO_ALERT"}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "pilot"
        self.source = self.root / "old"
        self.baseline = self.root / "six"
        self.directory.mkdir()
        self.patch_root = patch.object(runner, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        ids = [f"synthetic-{i:03}" for i in range(378)]
        folds = []
        for number in range(3):
            test = ids[number * 126:(number + 1) * 126]
            folds.append({"fold_id": f"fold-{number}", "heldout_environment": f"env-{number}",
                          "train_ids": [i for i in ids if i not in test], "outer_test_ids": test})
        old_jobs, jobs = [], []
        for fold in folds:
            for group in ("BASE", runner.GROUP):
                for stage in ("SPARSE", "RETENTION"):
                    job = {**deepcopy(fold), "job_id": f"{group}__{fold['fold_id']}__{stage}",
                           "group_id": group, "stage": stage, "capacity_profile": "W0_CAPACITY_7_V1", "max_prediction_calls": 126 if stage == "RETENTION" else 0}
                    if stage == "RETENTION":
                        job["initializer"] = f"{group}__{fold['fold_id']}__SPARSE"
                    old_jobs.append(job)
                    if group == runner.GROUP:
                        job = deepcopy(job)
                        job["job_id"] = "V2__" + job["job_id"]
                        if stage == "RETENTION":
                            job["initializer"] = "V2__" + job["initializer"]
                        jobs.append(job)
        self.contract = {"experiment_id": runner.EXPERIMENT, "engine_study_version": runner.STUDY,
                         "engine_phase": runner.PHASE, "readiness": "CAPACITY_COMPARISON_READY",
                         "source_directory": "old", "baseline_directory": "six", "sample_ids": ids,
                         "source_modes": {i: "raw_observation_v1" for i in ids}, "folds": folds, "jobs": jobs,
                         "evaluation_role": "EXPOSED_RETROSPECTIVE_DEVELOPMENT", "constraints": {"max_clauses": 7},
                         "capacity_profile": {"profile_id": "W0_CAPACITY_7_V1", "max_clauses": 7, "max_complexity": 14, "max_additions": 7, "max_literals": 12, "max_distinct_atoms": 12, "max_clauses_per_family": 2},
                         "budget": {"base_fit_jobs": 195, "round_fit_limit": 6, "planned_fits": 6, "revised_cumulative_limit": 201,
                                    "max_worker_seconds": 90, "max_total_seconds": 540, "base_charged_seconds": 171.0}}
        self.grant = {"experiment_id": runner.EXPERIMENT, "training_authorized": True, "admission_authorized": True,
                      "sample_ids": ids, "job_ids": [j["job_id"] for j in jobs], "authorization_ref": "SYNTHETIC_TEST_ONLY"}
        old = {**deepcopy(self.contract), "experiment_id": "raw-only-rkeep-three-env-fourteen-config-v1",
               "readiness": "RAW_ONLY_COMPARISON_READY", "jobs": old_jobs}
        old["constraints"] = {"max_clauses": 6}
        self.old_contract = old
        self.six_contract = deepcopy(old) | {"experiment_id": "semantic-selector-v2-raw-only-pilot-v1", "readiness": "SELECTOR_V2_READY", "jobs": deepcopy(jobs)}
        put(self.baseline / "CONTRACT.json", self.six_contract)
        put(self.baseline / "RESULT_REVIEW.json", {"status": "PASS"})
        put(self.baseline / "EXECUTION.json", {"execution_complete": True, "actual_fit_jobs": 6, "actual_prediction_calls": 378, "cumulative_fit_jobs": 195, "cumulative_charged_seconds": 171.0})
        put(self.directory / "BUDGET_AMENDMENT.json", {"experiment_id": runner.EXPERIMENT, "old_limit": 200, "new_limit": 201, "round_fits_authorized": 6, "authorization_ref": self.grant["authorization_ref"]})
        put(self.source / "CONTRACT.json", old)
        put(self.source / "EXECUTION.json", {"execution_complete": True, "actual_fit_jobs": 12,
                                            "actual_prediction_calls": 756, "cumulative_fit_jobs": 189,
                                            "remaining_research_fits": 11, "cumulative_charged_seconds": 171.0})
        put(self.source / "DEFINITIONS.json", {})
        for number, oid in enumerate(ids):
            phase = ("clean_pre", "attack", "clean_post")[number % 3]
            put(self.source / "inputs" / f"{oid}.json", {"opaque_id": oid, "observation_mode": "raw_observation_v1",
                                                        "features": {"fixture_attack": phase == "attack"}, "candidate_cells": {}})
            put(self.source / "evaluation" / f"{oid}.json", {"opaque_id": oid, "phase": phase,
                      "environment_group_id": f"env-{number // 126}", "config_id": f"cfg-{(number % 126) // 9}",
                      "bundle_id": f"bundle-{number // 9}", "triplet_id": f"triplet-{number // 3}",
                      "proposed_supervised_label": int(phase == "attack"), "proposed_supervised_member": True,
                      "fit_permission": "DENIED_PREPARATION_ONLY"})
        self.save_contract()

    def save_contract(self):
        put(self.directory / "CONTRACT.json", self.contract)
        put(self.directory / "AUTHORIZATION.json", self.grant)

    def dispatch(self):
        runner.write(self.directory / "RUN_STARTED.json", {"experiment_id": runner.EXPERIMENT,
                                                           "job_ids": [j["job_id"] for j in self.contract["jobs"]]})

    def test_gate_rejects_auth_split_initializer_and_budget_drift(self):
        runner.gate(self.directory)
        pristine = deepcopy(self.contract)
        self.grant["admission_authorized"] = False
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_REQUIRED"):
            runner.gate(self.directory)
        self.grant["admission_authorized"] = True
        self.contract["jobs"][0]["train_ids"][0] = self.contract["jobs"][0]["outer_test_ids"][0]
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "INVALID_OUTER_SPLIT"):
            runner.gate(self.directory)
        self.contract = deepcopy(pristine)
        self.contract["jobs"][1]["initializer"] = self.contract["jobs"][2]["job_id"]
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "OWN_FOLD_INITIALIZER_REQUIRED"):
            runner.gate(self.directory)
        self.contract = deepcopy(pristine)
        self.contract["budget"]["round_fit_limit"] = 7
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "REGISTERED_BUDGET_MISMATCH"):
            runner.gate(self.directory)

    def test_gate_rejects_changed_frozen_fold_and_legacy_mode(self):
        self.contract["folds"][0]["heldout_environment"] = "changed"
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "FROZEN_SOURCE_MISMATCH:folds"):
            runner.gate(self.directory)
        self.contract["folds"] = deepcopy(self.old_contract["folds"])
        self.contract["source_modes"][self.contract["sample_ids"][0]] = "legacy"
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "RAW_ONLY_MEMBERS_REQUIRED"):
            runner.gate(self.directory)

    def test_capacity_only_and_explicit_budget_amendment(self):
        self.contract["capacity_profile"]["max_additions"] = 6
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "EXACT_CAPACITY_PROFILE"):
            runner.gate(self.directory)
        self.contract["capacity_profile"]["max_additions"] = 7
        self.contract["constraints"]["max_literals"] = 14
        self.save_contract()
        with self.assertRaisesRegex(ValueError, "ONLY_CAPACITY_CONSTRAINT"):
            runner.gate(self.directory)
        del self.contract["constraints"]["max_literals"]
        self.save_contract()
        put(self.directory / "BUDGET_AMENDMENT.json", {})
        with self.assertRaisesRegex(ValueError, "BUDGET_REVISION_REQUIRED"):
            runner.gate(self.directory)

    def test_guard_blocks_inputs_until_frozen_and_labels_until_closed(self):
        job = self.contract["jobs"][0]
        access = runner.GuardedSource(self.source, job, "synthetic")
        heldout = job["outer_test_ids"][0]
        with self.assertRaisesRegex(ValueError, "HELDOUT_INPUT_OPEN_BEFORE_FREEZE"):
            access.input_row(heldout)
        with self.assertRaisesRegex(ValueError, "HELDOUT_LABEL_OPEN_BEFORE_PREDICTIONS_CLOSE"):
            access.metadata(heldout)
        access.phase = "FROZEN"
        access.input_row(heldout)
        with self.assertRaisesRegex(ValueError, "HELDOUT_LABEL_OPEN_BEFORE_PREDICTIONS_CLOSE"):
            access.metadata(heldout)
        access.phase = "PREDICTIONS_CLOSED"
        self.assertEqual(access.metadata(heldout)["supervised_label"], 0)

    def test_fake_worker_order_unique_attempt_and_saved_predictions(self):
        self.dispatch()
        engine = FakeEngine()
        with patch.object(runner, "load_engine", return_value=engine):
            for job in self.contract["jobs"][:2]:
                receipt = runner.worker(self.directory, job["job_id"])
                self.assertEqual(receipt["outcome"], "FITTED")
                self.assertEqual(receipt["actual_prediction_calls"], job["max_prediction_calls"])
            with self.assertRaises(FileExistsError):
                runner.worker(self.directory, self.contract["jobs"][0]["job_id"])
        self.assertEqual(runner.durable_counts(self.directory), (2, 126))
        rows, _ = runner.closed_rows(self.directory, self.contract["jobs"][1])
        self.assertEqual(len(rows), 126)
        self.assertEqual(sum(r["decision"] == "MANIPULATION_ALERT" for r in rows), 42)

    def test_timeout_charges_durable_prediction_calls_and_stops_without_retry(self):
        def timeout(command, **kwargs):
            job_id = command[command.index("--worker") + 1]
            trial = self.directory / "trials" / job_id
            trial.mkdir(parents=True)
            runner.write(trial / "FIT_STARTED.json", {"count": 1})
            (trial / "PREDICTION_CALLS.jsonl").write_text('{"opaque_id":"one"}\n{"opaque_id":"two"}\n')
            raise subprocess.TimeoutExpired(command, 90)
        with patch.object(runner.subprocess, "run", side_effect=timeout) as process, redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.run(self.directory)
        process.assert_called_once()
        execution = runner.read(self.directory / "EXECUTION.json")
        self.assertFalse(execution["execution_complete"])
        self.assertEqual(execution["actual_prediction_calls"], 2)
        self.assertEqual(execution["cumulative_fit_jobs"], 196)
        self.assertEqual(execution["remaining_round_fits"], 5)
        self.assertEqual(execution["unclosed_jobs"], 1)
        self.assertEqual(execution["unexecuted_jobs"], 5)
        self.assertEqual(execution["additional_retries"], 0)
        with self.assertRaises(FileExistsError):
            runner.run(self.directory)

    def test_comparison_reuses_saved_baselines_only_after_all_new_jobs_close(self):
        self.dispatch()
        engine = FakeEngine()
        with patch.object(runner, "load_engine", return_value=engine):
            for job in self.contract["jobs"]:
                runner.worker(self.directory, job["job_id"])
        for source, job in ([(self.source, j) for j in self.old_contract["jobs"]]
                            + [(self.baseline, j) for j in self.six_contract["jobs"]]):
            if job["stage"] != "RETENTION":
                continue
            dest = source / "trials" / job["job_id"]
            current = []
            for oid in job["outer_test_ids"]:
                meta = runner.read(self.source / "evaluation" / f"{oid}.json")
                current.append({**{k: meta[k] for k in ("opaque_id", "phase", "environment_group_id", "config_id", "bundle_id", "triplet_id")},
                                "supervised_label": meta["proposed_supervised_label"], "decision": "NO_ALERT"})
            put(dest / "receipt.json", {"outcome": "FITTED"})
            put(dest / "evaluation_rows.json", current)
            put(dest / "model.json", {"clauses": []})
            put(dest / "access_log.json", [{"event": name} for name in ("MODEL_SAVED_RELOADED_FROZEN",
                                  "PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN", "HELDOUT_METADATA_JOINED_AFTER_CLOSE")])
            (dest / "predictions.jsonl").write_text("".join(json.dumps({"opaque_id": r["opaque_id"], "decision": r["decision"]}) + "\n" for r in current))
        put(self.directory / "EXECUTION.json", {"execution_complete": False})
        with self.assertRaisesRegex(ValueError, "ALL_JOBS_MUST_CLOSE"):
            runner.summarize(self.directory, self.contract)
        put(self.directory / "EXECUTION.json", {"execution_complete": True})
        prior_calls = list(engine.calls)
        result = runner.summarize(self.directory, self.contract)
        self.assertEqual(engine.calls, prior_calls)
        self.assertEqual(result["attack_alert_delta"], 126)
        self.assertEqual(result["baseline_fit_calls"], 0)
        self.assertEqual(result["baseline_prediction_calls"], 0)
        self.assertEqual(len(result["changed_decisions"]["BASE"]), 126)
        self.assertIn("config_id", result["changed_decisions"]["BASE"][0])
        self.assertTrue(result["groups"]["CAP7"]["folds"][0]["selected_new_conditions"][runner.NEW_CANDIDATES[0]])


if __name__ == "__main__":
    unittest.main()
