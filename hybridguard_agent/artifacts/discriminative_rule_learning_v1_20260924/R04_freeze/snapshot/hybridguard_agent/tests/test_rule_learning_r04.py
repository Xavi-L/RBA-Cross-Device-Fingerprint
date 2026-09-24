"""R04 acceptance inside a relocated freeze; no real grant is ever issued."""
from dataclasses import replace
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from hybridguard_agent.research.rule_learning.access import FormalFitRequest, FitAuthorizationError, open_formal_fit
from hybridguard_agent.research.rule_learning.contracts import ROOT, read_json, read_jsonl
from hybridguard_agent.research.rule_learning.job_manifest import digest
from hybridguard_agent.research.rule_learning.job_runtime import FrozenSnapshot, file_digest
from hybridguard_agent.research.rule_learning.models import load_model
from hybridguard_agent.research.rule_learning.oof import aggregate_oof
from hybridguard_agent.research.rule_learning.runner import BudgetLedger, run, worker

OUTPUT = None
EVIDENCE = []


class R04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ROOT.parent
        cls.snapshot = FrozenSnapshot(cls.root)
        cls.out = Path(OUTPUT)
        cls.out.mkdir(parents=True)
        cls.runs = {}
        for suite in ("complete", "budget_count", "budget_time"):
            out = cls.out / suite
            run(cls.root, "SYNTHETIC_R04", out, cls.out / (suite + "_budget.json"), suite=suite)
            cls.runs[suite] = out
        cls.jobs = cls.snapshot.synthetic
        cls.by_id = {j["model_unit_id"]: j for j in cls.jobs}
        cls.receipts = read_json(cls.runs["complete"] / "model_receipts.json")
        cls.predictions = read_jsonl(cls.runs["complete"] / "predictions.jsonl")
        cls.models = {uid: load_model(cls.runs["complete"] / "jobs" / (cls.by_id[uid]["reuse_model_unit_id"] or uid) / "model.json") for uid in cls.receipts}

    def test_01_dispatcher_complete_chain_and_access_order(self):
        self.assertEqual(len(self.receipts), 20)
        self.assertEqual(len(self.predictions), 180)
        for uid, model in self.models.items():
            if self.by_id[uid]["reuse_model_unit_id"]:
                continue
            path = self.runs["complete"] / "jobs" / uid
            events = read_json(path / "access_log.json")
            names = [e["event"] for e in events]
            self.assertLess(names.index("TRAIN_READY"), names.index("MODEL_SAVED_LOADED_FROZEN"))
            self.assertLess(names.index("MODEL_SAVED_LOADED_FROZEN"), names.index("OPEN_OUTER_TEST_FEATURE"))
            self.assertLess(names.index("PREDICTIONS_CLOSED_AND_RECONCILED"), names.index("OPEN_OUTER_EVALUATION_LABEL"))
            self.assertTrue(all(e["resource"].startswith("synthetic/") for e in events if e["event"] in (
                "OPEN_TRAIN_FEATURE", "OPEN_TRAIN_LABEL", "OPEN_OUTER_TEST_FEATURE", "OPEN_OUTER_EVALUATION_LABEL")))
            self.assertTrue(Path(read_json(path / "WORKER_STARTUP.json")["cwd"]).name == "empty_cwd")
            self.assertEqual(list((path / "empty_cwd").iterdir()), [])
            self.assertEqual(model.binding["data_origin"], "BUILTIN_SYNTHETIC")
            self.assertEqual(model.binding["input_manifest_ref"], "synthetic/DATA_INDEX.json")
            self.assertEqual(model.binding["train_membership_digest"], self.by_id[uid]["train_membership_digest"])
        EVIDENCE.append({"check": "ordered_dispatcher_chain", "jobs": 20, "expected_predictions": 180,
                         "real_semantic_feature_or_label_reads": 0})

    def test_02_numerical_encoder_frozen_without_test_fit(self):
        a, b = [next(m for uid, m in self.models.items() if self.by_id[uid]["fixture_id"] == n)
                for n in ("numeric", "numeric_test_extreme")]
        self.assertEqual(a.encoder["numeric"], b.encoder["numeric"])
        self.assertEqual(a.encoder["numeric"]["UNFITTED_CONTROL:native.number"]["thresholds"], [4.25, 8.5, 12.75])
        for m in (a, b):
            self.assertNotIn("UNFITTED_CONTROL:web.number", m.encoder["numeric"])
            self.assertEqual(m.encoder["train_ids"], m.fit["train_ids"])

    def test_03_alias_projection_source_and_empty_model(self):
        ms = {self.by_id[u]["source_condition"]: m for u, m in self.models.items()
              if self.by_id[u]["fixture_id"] == "aliases" and m.method_id == "GREEDY_OR"}
        self.assertEqual(ms["SRC-000"].status, "EMPTY_MODEL")
        for a in ms["SRC-001"].atoms:
            self.assertEqual(a.sources, ("E",))
            self.assertTrue(a.provenance["all_registered_equivalent_aliases"])
        for m in ms.values():
            self.assertEqual(len(m.atoms), len({a.atom_id for a in m.atoms}))
        self.assertEqual(len(ms["SRC-111"].fit["train_ids"]), 18)

    def test_04_manual_oof_two_folds_and_missing_fold(self):
        jobs = [j for j in self.jobs if j["fixture_id"] == "complementary"]
        ids = {j["model_unit_id"] for j in jobs}
        rows = [r for r in self.predictions if r["model_unit_id"] in ids]
        receipts = {k: v for k, v in self.receipts.items() if k in ids}
        metadata = {}
        for j in jobs:
            metadata.update(read_json(self.runs["complete"] / "jobs" / j["model_unit_id"] / "evaluation_sidecar.json"))
        full = aggregate_oof(jobs, rows, receipts, metadata)[0]
        self.assertEqual(full["report"]["metrics"]["attack_tpr"]["numerator"], 6)
        self.assertEqual(full["report"]["metrics"]["attack_tpr"]["denominator"], 6)
        self.assertEqual(full["report"]["metrics"]["clean_alarm_rate"]["denominator"], 12)
        self.assertEqual(full["report"]["metrics"]["exact_FTF"]["numerator"], 6)
        retained = {jobs[0]["model_unit_id"]: receipts[jobs[0]["model_unit_id"]]}
        partial = aggregate_oof(jobs, [r for r in rows if r["model_unit_id"] in retained], retained, metadata)[0]
        self.assertEqual(partial["report"]["expected_stage_n"], 18)
        self.assertEqual(partial["report"]["metrics"]["attack_tpr"]["denominator"], 6)
        self.assertEqual(partial["report"]["metrics"]["attack_tpr"]["value"], .5)
        self.assertEqual(partial["report"]["metrics"]["failure_rate"]["value"], .5)
        self.assertEqual(len(partial["missing_units"]), 9)
        self.assertEqual(partial["report"]["metrics"]["atom_coverage"]["status"], "NOT_EVALUABLE")
        EVIDENCE.append({"check": "manual_OOF", "complete_attack": "6/6", "clean": "0/12", "exact_FTF": "6/6",
                         "missing_fold_attack": "3/6", "missing_fold_failures": "9/18", "missing_units": 9})

    def test_05_oof_rejects_mixed_points_sources_tracks_models(self):
        metadata = {}
        for uid in self.receipts:
            source = self.by_id[uid]["reuse_model_unit_id"] or uid
            metadata.update(read_json(self.runs["complete"] / "jobs" / source / "evaluation_sidecar.json"))
        for key in ("operating_point", "source_condition", "evaluation_track", "fold_id", "model_id"):
            rows = copy.deepcopy(self.predictions)
            rows[0][key] = "FORGED"
            with self.assertRaises(ValueError):
                aggregate_oof(self.jobs, rows, self.receipts, metadata)
        with self.assertRaises(ValueError):
            aggregate_oof(self.jobs, self.predictions + self.predictions[:1], self.receipts, metadata)

    def test_06_budget_count_and_time_retain_units(self):
        for suite, expected_states in (("budget_count", ["COMPLETED", "NOT_RUN_BUDGET_EXHAUSTED"]),
                                       ("budget_time", ["NOT_RUN_BUDGET_EXHAUSTED"] * 2)):
            summary = read_json(self.runs[suite] / "SUMMARY.json")
            self.assertEqual(summary["states"], expected_states)
            self.assertEqual(summary["predictions"], 18)
            report = read_json(self.runs[suite] / "OOF.json")[0]["report"]
            self.assertEqual(report["expected_stage_n"], 18)
            self.assertEqual(report["metrics"]["attack_tpr"]["denominator"], 6)
            self.assertEqual(report["status"], "INCOMPLETE_EXPECTED_OOF_UNITS")
        summary = read_json(self.runs["complete"] / "SUMMARY.json")
        self.assertEqual(summary["budget"]["order"], [j["job_id"] for j in sorted(self.jobs, key=lambda j: (j["priority"], j["job_id"]))])
        ledger = BudgetLedger(self.out / "budget_count_budget.json", self.snapshot.freeze_digest,
                             self.snapshot.protocol["synthetic_suites"]["budget_count"]["budget"])
        try:
            j = next(j for j in self.jobs if j["fixture_id"] == "complementary")
            with self.assertRaises(ValueError):
                ledger.reserve(j)
        finally:
            ledger.close()

    def test_07_early_test_labels_and_description_denied(self):
        j = self.jobs[0]
        ctx = self.snapshot.context(j["job_id"], "SYNTHETIC_R04")
        with self.assertRaisesRegex(FitAuthorizationError, "BEFORE_MODEL_FREEZE"):
            ctx.open_test(self.models[j["model_unit_id"]])
        with self.assertRaisesRegex(FitAuthorizationError, "BEFORE_PREDICTION_CLOSURE"):
            ctx.evaluation()
        access = ctx.train()
        self.assertEqual(set(access._data._features), set(j["train_ids"]))
        for partition in ("outer_test", "descriptive_test_side", "descriptive_train_side"):
            with self.assertRaises(FitAuthorizationError):
                access.batch(partition)

    def test_08_forged_job_and_cross_fold_model_denied(self):
        with self.assertRaises(FitAuthorizationError):
            self.snapshot.context("FORGED", "SYNTHETIC_R04")
        a, b = [j for j in self.jobs if j["fixture_id"] == "complementary"]
        ctx = self.snapshot.context(a["job_id"], "SYNTHETIC_R04")
        with self.assertRaises(FitAuthorizationError):
            ctx.validate_model(self.models[b["model_unit_id"]])
        ctx.job["train_ids"] = []
        with self.assertRaises(FitAuthorizationError):
            ctx.train()
        from hybridguard_agent.research.rule_learning.selector import fit
        from hybridguard_agent.research.rule_learning.baselines import core_view
        ctx = self.snapshot.context(a["job_id"], "SYNTHETIC_R04")
        access = ctx.train()
        with self.assertRaisesRegex(FitAuthorizationError, "FIT_METHOD_OR_POINT"):
            fit(access, access.batch("train"), "FINITE_IP_OR", "OP05")
        raw = next(j for j in self.jobs if j["fixture_id"] == "aliases" and j["method_id"] == "GREEDY_OR" and j["source_condition"] == "SRC-111")
        access = self.snapshot.context(raw["job_id"], "SYNTHETIC_R04").train()
        with self.assertRaisesRegex(FitAuthorizationError, "PROJECTED_SOURCE_VIEW"):
            core_view(access, "SRC-001")

    def test_09_formal_request_every_binding_and_stage_denial(self):
        j = next(j for j in self.snapshot.models if j["fit_job_id"])
        ctx = self.snapshot.context(j["job_id"], "R05")
        request = FormalFitRequest(stage=j["authorization_stage"], authorization_record_ref=ctx.authorization_ref(),
            freeze_manifest_ref="FREEZE_MANIFEST.json#" + self.snapshot.freeze_digest,
            resource_manifest_ref="RESOURCE_MANIFEST.json#" + self.snapshot.resource_digest,
            expected_fit_job_ref="expected_fit_jobs.jsonl#" + j["fit_job_id"],
            **{k: j[k] for k in ("protocol_digest", "split_id", "fold_id", "method_id", "operating_point", "source_condition", "input_view")},
            train_membership_ref="SPLIT_MANIFEST.json#" + j["fold_id"] + ":" + j["train_membership_digest"])
        with self.assertRaisesRegex(FitAuthorizationError, "R04_REAL_DATA_FIT_NOT_AUTHORIZED"):
            open_formal_fit(request, context=ctx)
        for field in vars(request):
            with self.assertRaises(FitAuthorizationError):
                open_formal_fit(replace(request, **{field: "FORGED"}), context=ctx)
        self.assertEqual(ctx.events, [])
        lineage = ctx.lineage()
        self.assertEqual(lineage["data_origin"], "R02_FIXED_CACHE")
        self.assertEqual(lineage["split_id"], "LOEO-v1")
        self.assertEqual(lineage["input_manifest_ref"], "DATA_INDEX.json")
        self.assertNotIn("synthetic.py", json.dumps(lineage))
        with self.assertRaises(FitAuthorizationError):
            self.snapshot.context(j["job_id"], "SYNTHETIC_R04")
        with self.assertRaises(FitAuthorizationError):
            run(self.root, "R05", self.out / "forbidden_real", self.out / "forbidden_budget.json")
        self.assertFalse((self.out / "forbidden_real").exists())
        EVIDENCE.append({"check": "formal_request", "mutated_fields_denied": len(vars(request)),
                         "matching_request": "R04_REAL_DATA_FIT_NOT_AUTHORIZED", "real_train_open_events": 0,
                         "unfitted_real_lineage_descriptor": lineage})

    def test_10_absent_or_modified_resource_rejects_startup(self):
        # Relocate the entire freeze. Hard links avoid redundant copying; we only
        # unlink or replace a clone entry, never write through a shared inode.
        with tempfile.TemporaryDirectory(prefix="r04-refusal-") as directory:
            clone = Path(directory) / "freeze"
            shutil.copytree(self.root, clone, copy_function=os.link,
                            ignore=lambda path, names: [n for n in names if n == "isolated_validation"])
            target = clone / "data/definitions.json"
            original = target.read_bytes()
            target.unlink()
            cwd = Path(directory) / "empty"
            cwd.mkdir()
            cmd = [str(clone / "dependencies/python/bin/python3.12"), "-B", "-I", "-S", str(clone / "launch.py"), "verify", str(clone)]
            missing = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("MISSING_OR_EXTERNAL_RESOURCE", missing.stderr)
            target.write_bytes(original + b" ")
            changed = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(changed.returncode, 0)
            self.assertIn("RESOURCE_DIGEST_MISMATCH", changed.stderr)
            target.write_bytes(original)
            resources = read_json(clone / "RESOURCE_MANIFEST.json")
            frozen = read_json(clone / "FREEZE_MANIFEST.json")
            saved_resources = copy.deepcopy(resources)
            saved_frozen = copy.deepcopy(frozen)
            def replace_json(path, value):
                path.unlink()
                path.write_text(json.dumps(value))
            resources["runtime"]["python"] = "0.0.0"
            replace_json(clone / "RESOURCE_MANIFEST.json", resources)
            frozen["manifest_digests"]["RESOURCE_MANIFEST.json"] = file_digest(clone / "RESOURCE_MANIFEST.json")
            replace_json(clone / "FREEZE_MANIFEST.json", frozen)
            version = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(version.returncode, 0)
            self.assertIn("RUNTIME_PLATFORM_OR_PYTHON_VERSION_CONFLICT", version.stderr)
            resources, frozen = saved_resources, saved_frozen
            models = read_jsonl(clone / "expected_model_units.jsonl")
            models[0]["train_ids"] = models[0]["train_ids"][:-1]
            models[0]["train_membership_digest"] = digest(models[0]["train_ids"])
            path = clone / "expected_model_units.jsonl"
            path.unlink()
            path.write_text(''.join(json.dumps(r) + '\n' for r in models))
            for entry in resources["files"]:
                if entry["path"] == "expected_model_units.jsonl":
                    entry.update(bytes=path.stat().st_size, sha256=file_digest(path))
            replace_json(clone / "RESOURCE_MANIFEST.json", resources)
            frozen["manifest_digests"]["RESOURCE_MANIFEST.json"] = file_digest(clone / "RESOURCE_MANIFEST.json")
            frozen["manifest_digests"]["expected_model_units.jsonl"] = file_digest(path)
            replace_json(clone / "FREEZE_MANIFEST.json", frozen)
            membership = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(membership.returncode, 0)
            self.assertIn("EXACT_JOB_DIFFERS_FROM_R01_MEMBERS_OR_PLAN", membership.stderr)
            EVIDENCE.append({"check": "startup_refusal", "missing_exit": missing.returncode,
                "modified_exit": changed.returncode, "version_conflict_exit": version.returncode,
                "resealed_member_conflict_exit": membership.returncode, "resource": "data/definitions.json", "jobs_started": 0})

    def test_11_no_direct_worker_without_dispatcher(self):
        path = self.out / "forged_ticket.json"
        path.write_text(json.dumps({"parent_pid": -1, "nonce": "fake", "stage": "SYNTHETIC_R04"}))
        with self.assertRaises(FitAuthorizationError):
            worker(self.root, self.out, path)

    def test_12_models_reload_and_fixed_inference_ignore_labels(self):
        from hybridguard_agent.research.rule_learning.predictor import predict
        from hybridguard_agent.research.rule_learning.baselines import transform_numeric, project_core
        from hybridguard_agent.research.rule_learning.contracts import ledger
        index = read_json(self.root / "synthetic/DATA_INDEX.json")
        for uid, m in self.models.items():
            j = self.by_id[uid]
            if j["method_id"] == "HISTORICAL_SEVEN":
                self.assertEqual(predict(m, j["outer_test_ids"][0], {})["decision"], "FAILED")
                continue
            raw = {i: read_json(self.root / index[i]["features"])["features"] for i in j["outer_test_ids"]}
            if m.encoder:
                rows = {i: transform_numeric(r, m.encoder) for i, r in raw.items()}
            elif m.view["view_id"].startswith("CORE:"):
                rows, _ = project_core(raw, ledger(), j["source_condition"])
            else:
                rows = raw
            saved = read_jsonl(self.runs["complete"] / "jobs" / uid / "predictions.jsonl")
            self.assertEqual([predict(m, i, {"features": rows[i], "view_id": m.view["view_id"]})["decision"] for i in rows],
                             [r["decision"] for r in saved])
            # Sidecar permutations have no parameter/route into prediction.
            meta = read_json(self.runs["complete"] / "jobs" / (j["reuse_model_unit_id"] or uid) / "evaluation_sidecar.json")
            for value in meta.values():
                value["supervised_label"] = 1 - value["supervised_label"]
            self.assertEqual([predict(m, i, {"features": rows[i], "view_id": m.view["view_id"]})["decision"] for i in rows],
                             [r["decision"] for r in saved])

    def test_13_failed_empty_historical_preserved(self):
        self.assertEqual(Counter(r["state"] for r in self.receipts.values()),
                         {"COMPLETED": 13, "EMPTY_MODEL": 5, "FAILED": 1, "REUSED": 1})
        for uid, rec in self.receipts.items():
            rows = [r for r in self.predictions if r["model_unit_id"] == uid]
            if rec["state"] in ("FAILED", "EMPTY_MODEL"):
                self.assertEqual({r["decision"] for r in rows}, {rec["state"]})
            if self.by_id[uid]["method_id"] == "HISTORICAL_SEVEN":
                self.assertEqual({r["historical_family_coverage"] for r in rows}, {.8})
                self.assertTrue(all(r["coverage_status"].startswith("HISTORICAL_FAMILY") for r in rows))

    def test_14_reuse_dispatcher_does_not_refit_or_rewrite_model(self):
        j = next(j for j in self.jobs if j["reuse_model_unit_id"])
        out = self.runs["complete"] / "jobs" / j["model_unit_id"]
        proof = read_json(out / "REUSE_RECEIPT.json")
        self.assertFalse(proof["new_fit"])
        self.assertFalse(proof["model_bytes_rewritten"])
        self.assertFalse((out / "model.json").exists())
        self.assertEqual(self.receipts[j["model_unit_id"]]["model_id"], self.receipts[j["reuse_model_unit_id"]]["model_id"])
        self.assertEqual(read_json(self.runs["complete"] / "SUMMARY.json")["budget"]["used_fit_jobs"], 15)

    def test_15_changed_test_labels_do_not_change_dispatcher_predictions(self):
        a = next(j for j in self.jobs if j["fixture_id"] == "complementary")
        b = next(j for j in self.jobs if j["fixture_id"] == "complementary_test_labels")
        self.assertEqual(self.models[a["model_unit_id"]].clauses, self.models[b["model_unit_id"]].clauses)
        pa = [r["decision"] for r in self.predictions if r["model_unit_id"] == a["model_unit_id"]]
        pb = [r["decision"] for r in self.predictions if r["model_unit_id"] == b["model_unit_id"]]
        self.assertEqual(pa, pb)
        ma = read_json(self.runs["complete"] / "jobs" / a["model_unit_id"] / "metrics.json")
        mb = read_json(self.runs["complete"] / "jobs" / b["model_unit_id"] / "metrics.json")
        self.assertEqual(ma["metrics"]["attack_tpr"]["value"], 1)
        self.assertEqual(mb["metrics"]["attack_tpr"]["value"], 0)
        EVIDENCE.append({"check": "separate_test_label_permutation_through_dispatcher", "predictions_identical": True,
                         "original_toy_TPR": "3/3", "permuted_toy_TPR": "0/3", "real_performance": False})


from collections import Counter
