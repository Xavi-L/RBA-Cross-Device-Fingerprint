"""Synthetic CAP8 source reuse, authorization, access and accounting checks."""
from copy import deepcopy
import importlib.util
import io
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / "deliverables/webgl1_cap8_comparison_v1/run_comparison.py"
spec = importlib.util.spec_from_file_location("webgl1_cap8_runner", PATH)
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
    return {"schema_version": runner.SOURCE_SCHEMA, "readiness": runner.SOURCE_READINESS,
            "source_collection_protocol": runner.SOURCE_PROTOCOL, "sample_ids": ids, "folds": folds,
            "source_modes": dict.fromkeys(ids, "raw_observation_v1"), "evaluation_role": runner.SOURCE_ROLE}


def fixture(directory, prepared=None):
    prepared = preparation() if prepared is None else prepared
    contract, grant = runner.configure_contract(prepared, source_directory=runner.SOURCE_DIRECTORY,
                                                 authorization_ref="synthetic-cap8")
    dump(directory / "CONTRACT.json", contract)
    dump(directory / "AUTHORIZATION.json", grant)
    source = runner.ROOT / runner.SOURCE_DIRECTORY
    dump(source / "PREPARATION.json", prepared)
    dump(source / "CONTRACT.json", {"experiment_id": runner.SOURCE_EXPERIMENT,
        "readiness": runner.SOURCE_READINESS, "protocol": {"experiment_id": runner.SOURCE_EXPERIMENT},
        **{k: prepared[k] for k in ("sample_ids", "folds", "source_modes", "evaluation_role")}})
    return contract, grant, source


class Cap8RunnerTests(unittest.TestCase):
    def test_exact_twelve_fit_schedule_and_gate(self):
        prepared = preparation()
        contract, grant = runner.configure_contract(prepared, source_directory=runner.SOURCE_DIRECTORY, authorization_ref="synthetic")
        self.assertEqual(len(contract["jobs"]), 12)
        self.assertEqual(sum(j["max_prediction_calls"] for j in contract["jobs"]), 756)
        self.assertEqual(contract["capacity_profile"]["max_clauses"], 8)
        self.assertEqual(contract["capacity_profile"]["max_complexity"], 16)
        self.assertEqual(contract["capacity_profile"]["max_additions"], 8)
        self.assertEqual(contract["evaluation_role"], runner.EVALUATION_ROLE)
        self.assertNotEqual(contract["evaluation_role"], contract["source_evaluation_role"])
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "ROOT", Path(temp)):
            directory = Path(temp) / "study"
            contract, grant, source = fixture(directory, prepared)
            self.assertEqual(runner.gate(directory), (contract, grant))
            changed = deepcopy(contract)
            retained = next(j for j in changed["jobs"] if j["stage"] == "RETENTION" and j["group_id"] == "WEBGL50")
            retained["initializer"] = next(j["job_id"] for j in changed["jobs"] if j["stage"] == "SPARSE" and j["group_id"] == "BASE49")
            dump(directory / "CONTRACT.json", changed)
            with self.assertRaisesRegex(ValueError, "OWN_GROUP_FOLD_INITIALIZER_REQUIRED"):
                runner.gate(directory)
            dump(directory / "CONTRACT.json", contract)
            dump(source / "PREPARATION.json", prepared | {"readiness": "BLOCKED_INCOMPLETE_OR_FAILED_COHORT"})
            with self.assertRaisesRegex(ValueError, "CAP7_PREPARATION_NOT_READY"):
                runner.gate(directory)

    def test_old_authorization_and_old_capacity_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "ROOT", Path(temp)):
            directory = Path(temp) / "study"
            contract, grant, _ = fixture(directory)
            old_grant = {k: deepcopy(v) for k, v in grant.items() if k != "schema_version"}
            old_grant["experiment_id"] = runner.SOURCE_EXPERIMENT
            dump(directory / "AUTHORIZATION.json", old_grant)
            with self.assertRaisesRegex(ValueError, "CAP8_SPECIFIC_AUTHORIZATION_REQUIRED"):
                runner.gate(directory)
            dump(directory / "AUTHORIZATION.json", grant)
            contract["capacity_profile"].update(profile_id="W0_CAPACITY_7_V1", max_clauses=7, max_complexity=14, max_additions=7)
            dump(directory / "CONTRACT.json", contract)
            with self.assertRaisesRegex(ValueError, "EXACT_CAPACITY_PROFILE_REQUIRED"):
                runner.gate(directory)

    def test_gate_reads_only_source_admission_metadata_not_prior_results(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "ROOT", Path(temp)):
            directory = Path(temp) / "study"
            _, _, source = fixture(directory)
            with patch.object(runner, "read", wraps=runner.read) as reads:
                runner.gate(directory)
            paths = {call.args[0].resolve() for call in reads.call_args_list}
            self.assertEqual(paths, {p.resolve() for p in (directory / "CONTRACT.json", directory / "AUTHORIZATION.json",
                                     source / "PREPARATION.json", source / "CONTRACT.json")})

    def test_fixed_source_experiment_protocol_members_and_roles_are_required(self):
        with self.assertRaisesRegex(ValueError, "REGISTERED_CAP7_PREPARED_SOURCE_REQUIRED"):
            runner.configure_contract(preparation(), source_directory="unregistered/prepared", authorization_ref="synthetic")
        changes = (("experiment_id", "other", "SOURCE_EXPERIMENT_NOT_ADMITTED"),
                   ("sample_ids", ["replacement"], "SOURCE_ADMISSION_CHANGED:sample_ids"),
                   ("evaluation_role", "INDEPENDENT_CONFIRMATION", "EXPLICIT_SOURCE_REUSE_ROLE_REQUIRED"))
        for key, value, error in changes:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp, patch.object(runner, "ROOT", Path(temp)):
                directory = Path(temp) / "study"
                _, _, source = fixture(directory)
                admitted = runner.read(source / "CONTRACT.json")
                dump(source / "CONTRACT.json", admitted | {key: value})
                with self.assertRaisesRegex(ValueError, error):
                    runner.gate(directory)
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "ROOT", Path(temp)):
            directory = Path(temp) / "study"
            _, _, source = fixture(directory)
            prepared = runner.read(source / "PREPARATION.json")
            dump(source / "PREPARATION.json", prepared | {"source_collection_protocol": "somewhere/PROTOCOL.json"})
            with self.assertRaisesRegex(ValueError, "SOURCE_COLLECTION_PROTOCOL_MISMATCH"):
                runner.gate(directory)

    def test_own_cap8_initializer_receipt_rejects_cap7_and_other_group_or_fold(self):
        contract, _ = runner.configure_contract(preparation(), source_directory=runner.SOURCE_DIRECTORY, authorization_ref="synthetic")
        job = next(j for j in contract["jobs"] if j["stage"] == "RETENTION")
        receipt = {"outcome": "FITTED", "experiment_id": runner.EXPERIMENT,
                   "capacity_profile": contract["capacity_profile"]["profile_id"], "job_id": job["initializer"],
                   "group_id": job["group_id"], "fold_id": job["fold_id"], "stage": "SPARSE"}
        runner.validate_initializer_receipt(receipt, job, contract)
        for change in ({"experiment_id": runner.SOURCE_EXPERIMENT}, {"capacity_profile": "W0_CAPACITY_7_V1"},
                       {"group_id": "WEBGL50"}, {"fold_id": "other"}, {"stage": "RETENTION"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "OWN_CAP8_INITIALIZER_RECEIPT_REQUIRED"):
                runner.validate_initializer_receipt(receipt | change, job, contract)

    def test_durable_counts_charge_unclosed_fit_and_prediction_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            trial = directory / "trials/unclosed"
            dump(trial / "FIT_STARTED.json", {"count": 1})
            (trial / "PREDICTION_CALLS.jsonl").write_text('{"opaque_id":"one"}\n{"opaque_id":"two"}\n')
            self.assertFalse((trial / "receipt.json").exists())
            self.assertEqual(runner.durable_counts(directory), (1, 2))

    def test_worker_timeout_respects_remaining_total_limit_and_preserves_stop(self):
        contract, grant = runner.configure_contract(preparation(), source_directory=runner.SOURCE_DIRECTORY, authorization_ref="synthetic")
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
                    "evaluation_role": "SYNTHETIC_ONLY", "source_evaluation_role": "SYNTHETIC_SOURCE_ONLY",
                    "source_reuse": runner.source_reuse_registration(), "capacity_profile": {"profile_id": "SYNTHETIC"},
                    "jobs": [{"group_id": g, "stage": "RETENTION",
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
