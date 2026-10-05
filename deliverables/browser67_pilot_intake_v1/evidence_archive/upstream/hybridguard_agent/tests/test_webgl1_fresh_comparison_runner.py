"""Synthetic schedule, data-access and paired result accounting checks."""
from copy import deepcopy
import importlib.util
import io
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / "deliverables/webgl1_fresh_comparison_v1/run_comparison.py"
spec = importlib.util.spec_from_file_location("webgl1_fresh_runner", PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def preparation():
    ids = ["synthetic-" + str(i) for i in range(378)]
    folds = []
    for n in range(3):
        test = ids[n * 126:(n + 1) * 126]
        folds.append({"fold_id": "F" + str(n), "heldout_environment": "env" + str(n),
                      "train_ids": [i for i in ids if i not in test], "outer_test_ids": test})
    return {"readiness": "WEBGL1_FRESH_INPUTS_READY", "sample_ids": ids, "folds": folds,
            "source_modes": dict.fromkeys(ids, "raw_observation_v1"), "evaluation_role": "SYNTHETIC_ONLY"}


class FreshRunnerTests(unittest.TestCase):
    def test_exact_twelve_fit_schedule_and_gate(self):
        prepared = preparation()
        contract, grant = runner.configure_contract(prepared, source_directory="study/prepared", authorization_ref="synthetic")
        self.assertEqual(len(contract["jobs"]), 12)
        self.assertEqual(sum(j["max_prediction_calls"] for j in contract["jobs"]), 756)
        self.assertEqual(contract["capacity_profile"]["max_clauses"], 7)
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "ROOT", Path(temp)):
            directory = Path(temp) / "study"
            dump(directory / "CONTRACT.json", contract)
            dump(directory / "AUTHORIZATION.json", grant)
            dump(directory / "prepared/PREPARATION.json", prepared)
            self.assertEqual(runner.gate(directory), (contract, grant))
            changed = deepcopy(contract)
            retained = next(j for j in changed["jobs"] if j["stage"] == "RETENTION" and j["group_id"] == "WEBGL50")
            retained["initializer"] = next(j["job_id"] for j in changed["jobs"] if j["stage"] == "SPARSE" and j["group_id"] == "BASE49")
            dump(directory / "CONTRACT.json", changed)
            with self.assertRaisesRegex(ValueError, "OWN_GROUP_FOLD_INITIALIZER_REQUIRED"):
                runner.gate(directory)
            dump(directory / "CONTRACT.json", contract)
            dump(directory / "prepared/PREPARATION.json", prepared | {"readiness": "BLOCKED_INCOMPLETE_OR_FAILED_COHORT"})
            with self.assertRaisesRegex(ValueError, "FRESH_PREPARATION_NOT_READY"):
                runner.gate(directory)

    def test_worker_timeout_respects_remaining_total_limit_and_preserves_stop(self):
        contract, grant = runner.configure_contract(preparation(), source_directory="study/prepared", authorization_ref="synthetic")
        for elapsed, expected_timeout in ((0, 90), (1075, 5), (1080, None)):
            with self.subTest(elapsed=elapsed), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                times = [0, elapsed] + ([elapsed + expected_timeout] if expected_timeout else [])
                with patch.object(runner, "gate", return_value=(contract, grant)), \
                     patch.object(runner.time, "monotonic", side_effect=times), \
                     patch.object(runner, "durable_counts", return_value=(0, 0)), \
                     patch.object(runner.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture-worker", expected_timeout or 0)) as invoke, \
                     patch("sys.stdout", new_callable=io.StringIO), self.assertRaises(SystemExit):
                    runner.run(directory)
                execution = runner.read(directory / "EXECUTION.json")
                self.assertFalse(execution["execution_complete"])
                self.assertEqual(execution["additional_retries"], 0)
                if expected_timeout is None:
                    invoke.assert_not_called()
                    self.assertEqual(execution["stop_reason"]["type"], "RunDeadline")
                    self.assertEqual(execution["dispatched_jobs"], [])
                else:
                    invoke.assert_called_once()
                    self.assertEqual(invoke.call_args.kwargs["timeout"], expected_timeout)
                    self.assertEqual(execution["stop_reason"]["type"], "TimeoutExpired")
                    self.assertEqual(execution["stop_reason"]["wall_seconds"], expected_timeout)
                    self.assertEqual(execution["dispatched_jobs"], [contract["jobs"][0]["job_id"]])
                    self.assertEqual(execution["unclosed_jobs"], 1)

    def test_input_then_label_phase_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            for oid in ("train", "test"):
                dump(source / "inputs" / (oid + ".json"), {"opaque_id": oid, "observation_mode": "raw_observation_v1"})
                dump(source / "evaluation" / (oid + ".json"), {"opaque_id": oid, "proposed_supervised_member": True,
                     "fit_permission": "DENIED_PREPARATION_ONLY", "phase": "attack", "proposed_supervised_label": 1})
            guard = runner.GuardedSource(source, {"train_ids": ["train"], "outer_test_ids": ["test"]}, "synthetic")
            self.assertEqual(guard.input_row("train")["opaque_id"], "train")
            self.assertEqual(guard.metadata("train")["supervised_label"], 1)
            with self.assertRaisesRegex(ValueError, "HELDOUT_INPUT_OPEN_BEFORE_FREEZE"):
                guard.input_row("test")
            with self.assertRaisesRegex(ValueError, "HELDOUT_LABEL_OPEN_BEFORE_PREDICTIONS_CLOSE"):
                guard.metadata("test")
            guard.phase = "FROZEN"
            self.assertEqual(guard.input_row("test")["opaque_id"], "test")
            with self.assertRaises(ValueError):
                guard.metadata("test")
            guard.phase = "PREDICTIONS_CLOSED"
            self.assertEqual(guard.metadata("test")["supervised_label"], 1)

    def test_saved_shared_basis_audit_ignores_selected_subsets_and_reports_failure(self):
        webgl = runner.NEW_CANDIDATES[-1]
        jobs = [{"job_id": group, "group_id": group, "fold_id": "F", "stage": "RETENTION"}
                for group in runner.GROUPS]
        contract = {"folds": [{"fold_id": "F"}], "jobs": jobs}
        base_encoder = {"fixed_atoms": ["shared"], "numeric": {"numeric": {"thresholds": [3]}},
                        "train_ids": ["synthetic"], "fold_id": "F"}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for group in runner.GROUPS:
                extra = group == "WEBGL50"
                dump(directory / "trials" / group / "training.json", {
                    "encoded_atoms": [{"atom_id": "shared", "field": "source"}]
                        + ([{"atom_id": webgl, "field": "webgl"}] if extra else []),
                    "semantic_catalog": {"shared": {"key": "frozen"}}
                        | ({webgl: {"key": "webgl"}} if extra else {})})
                dump(directory / "trials" / group / "model.json", {
                    "atoms": [{"atom_id": webgl if extra else "shared"}],
                    "encoder": base_encoder | {"fixed_atoms": ["shared"] + ([webgl] if extra else [])}})
            result = runner.shared_basis_audit(directory, contract)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["folds"][0]["selected_atom_sets_required_equal"])
            path = directory / "trials/WEBGL50/model.json"
            model = runner.read(path)
            model["encoder"]["numeric"]["numeric"]["thresholds"] = [9]
            dump(path, model)
            result = runner.shared_basis_audit(directory, contract)
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["folds"][0]["checks"]["numeric_encoder_equal"])
            self.assertEqual(result["action_on_failure"], "REPORT_ONLY_NO_REFIT_OR_RETUNING")

    def test_new_and_lost_attack_alerts_are_separately_reported(self):
        rows = [{"opaque_id": "gained", "phase": "attack", "supervised_label": 1, "config_id": "webgl",
                 "environment_group_id": "env", "triplet_id": "t1", "bundle_id": "b"},
                {"opaque_id": "lost", "phase": "attack", "supervised_label": 1, "config_id": "other",
                 "environment_group_id": "env", "triplet_id": "t2", "bundle_id": "b"}]
        contract = {"sample_ids": [r["opaque_id"] for r in rows], "experiment_id": runner.EXPERIMENT,
                    "evaluation_role": "SYNTHETIC_ONLY", "jobs": [{"group_id": g, "stage": "RETENTION",
                    "fold_id": "F", "heldout_environment": "env"} for g in runner.GROUPS]}
        def closed(_, job):
            decisions = ["NO_ALERT", "MANIPULATION_ALERT"] if job["group_id"] == "BASE49" else ["MANIPULATION_ALERT", "NO_ALERT"]
            return [r | {"decision": d} for r, d in zip(rows, decisions)], {"clauses": []}
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "closed_rows", side_effect=closed), \
             patch.object(runner, "shared_basis_audit", return_value={"status": "SYNTHETIC_SEPARATE_TEST"}):
            directory = Path(temp)
            dump(directory / "EXECUTION.json", {"execution_complete": True})
            result = runner.summarize(directory, contract)
            self.assertEqual(result["attack_alert_delta"], 0)
            self.assertEqual([r["opaque_id"] for r in result["newly_detected_attacks"]], ["gained"])
            self.assertEqual([r["opaque_id"] for r in result["lost_detected_attacks"]], ["lost"])
            self.assertEqual(result["paired_config_differences"]["other"]["lost_detected_attack_ids"], ["lost"])


if __name__ == "__main__":
    unittest.main()
