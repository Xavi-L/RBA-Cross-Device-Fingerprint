"""Reproducible R03 synthetic delivery. Existing output directories are read-only."""
from collections import Counter
from dataclasses import fields
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

from .access import FormalFitRequest, synthetic_fixture
from .baselines import core_view, historical_seven_contract, single_surface_definitions, single_surface_view
from .contracts import CONFIG, ROOT, STUDY, binding, ledger, read_json, read_jsonl
from .evaluation import evaluate
from .models import load_model, save_model
from .predictor import predict_batch, predict_single_surface
from .selector import fit, selection_rows
from .solver import solver_environment
from .synthetic import FIXTURES, export_fixture

REVIEW_COMMIT = "daca1ff477383ded6b6c81600dbca1cb6270e9f9"
IMPLEMENTATION = ROOT / "hybridguard_agent/research/rule_learning"


def dump(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def dump_lines(path, rows):
    with Path(path).open("x") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def review_inputs():
    b = binding()
    cfg = {Path(ref).stem: read_json(ROOT / ref) for ref in b["config_refs"]}
    canonical = json.dumps({"configs": cfg, "candidates": ledger()}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != b["protocol_digest"]:
        raise ValueError("R01_FROZEN_CONFIG_BINDING_CHANGED")
    roles = read_jsonl(STUDY / "R01_protocol/DATA_ROLE_LEDGER.jsonl")
    evaluation = read_jsonl(STUDY / "R02_matrix/evaluation_index.jsonl")
    if roles != evaluation or Counter(r["supervised_label"] for r in roles) != {None: 100, 0: 108, 1: 54}:
        raise ValueError("R01_R02_DATA_ROLE_MISMATCH")
    splits = read_jsonl(STUDY / "R01_protocol/SPLIT_MEMBERSHIP.jsonl")
    folds = read_json(STUDY / "R02_matrix/FOLD_INPUT_MANIFEST.json")["folds"]
    if len(splits) != len(folds) or any(any(fold.get(k) != v for k, v in split.items())
            or fold["protocol_digest"] != b["protocol_digest"]
            or fold["test_fit_permissions"] or fold["descriptive_fit_permissions"]
            or fold["later_authorized_fit_partition"] != "train"
            for split, fold in zip(splits, folds)):
        raise ValueError("R01_R02_SPLIT_MISMATCH")
    manifests = read_jsonl(STUDY / "R02_matrix/candidate_manifest.jsonl")
    if len(manifests) != 57 or any(any(m[k] != v for k, v in c.items()) for c, m in zip(ledger(), manifests)):
        raise ValueError("R02_REGISTRY_MISMATCH")
    subprocess.run(["git", "merge-base", "--is-ancestor", REVIEW_COMMIT, "HEAD"], cwd=ROOT, check=True)
    protected_paths = [*b["config_refs"], str((STUDY / "R01_protocol").relative_to(ROOT)),
                       str((STUDY / "R02_matrix").relative_to(ROOT)), "RESEARCH_MAINLINE.md",
                       "deliverables/formal_experiment_execution_plan/EXECUTION_PLAN.md"]
    delta = subprocess.check_output(["git", "diff", REVIEW_COMMIT, "--name-only", "--", *protected_paths], cwd=ROOT, text=True)
    if delta.strip():
        raise ValueError("REVIEWED_PREREQUISITE_CHANGED:" + delta)
    return {"status": "PASS", "reviewed_commit": REVIEW_COMMIT,
            "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "relevant_prerequisite_differences": [], "protocol_digest": b["protocol_digest"],
            "config_count": len(cfg), "registered_candidates": 57, "stage_n": 262,
            "supervised_n": 162, "descriptive_n": 100, "fold_n": len(folds),
            "review_basis": "portable config/candidate/member/version checks; no old mtime or old PENDING replay",
            "real_matrix_rebuilt": False, "real_features_used_for_fit_or_prediction": False}


def protected_snapshot():
    paths = [ROOT / ref for ref in binding()["config_refs"]]
    paths += [ROOT / "RESEARCH_MAINLINE.md", ROOT / "deliverables/formal_experiment_execution_plan/EXECUTION_PLAN.md"]
    for directory in (STUDY / "R01_protocol", STUDY / "R02_matrix", ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923"):
        paths += [p for p in directory.rglob("*") if p.is_file()]
    return {str(p.relative_to(ROOT)): [p.stat().st_size, p.stat().st_mtime_ns] for p in paths}


class RecordedResults(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "status": "PASS"})


def run_synthetic_tests():
    from hybridguard_agent.tests import test_rule_learning_r03 as module
    module.EVIDENCE.clear()
    if not solver_environment()["available"]:
        raise RuntimeError("R03_ACCEPTANCE_REQUIRES_PINNED_LOCAL_HIGHS; install requirements-r03.txt in an isolated environment")
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResults).run(suite)
    if not result.wasSuccessful():
        raise AssertionError(stream.getvalue())
    return result.records, module.EVIDENCE.copy(), stream.getvalue()


def build(directory):
    out = Path(directory)
    if out.exists():
        raise FileExistsError("R03 delivery refuses to overwrite an existing directory")
    review = review_inputs()
    before = protected_snapshot()
    records, evidence, transcript = run_synthetic_tests()
    out.mkdir(parents=True)
    (out / "fixtures").mkdir(); (out / "models").mkdir()
    for name in FIXTURES:
        dump(out / "fixtures" / (name + ".json"), export_fixture(name))
    dump(out / "BINDING_REVIEW.json", review)
    dump(out / "R02_EXTERNAL_ACCEPTANCE.json", {
        "event": "R02_EXTERNAL_REVIEW_ACCEPTED", "date": "2026-09-24", "reviewed_commit": REVIEW_COMMIT,
        "authority": "User: R02 外部验收通过。执行 R03：选择器、合理基线和合成验证。",
        "accepted_step": "R02", "accepted_artifact": "R02_matrix/VALIDATION.json",
        "original_validation_and_execution_time_history_overwritten": False,
        "new_authorization": "R03_IMPLEMENTATION_AND_SYNTHETIC_VALIDATION_ONLY",
        "excluded": ["R04", "R05", "real fitting or ranking or thresholds", "real risk predictions", "legacy S07", "commit", "push"]})
    dump(out / "ENVIRONMENT.json", {"python": platform.python_version(), "executable_used": sys.executable,
        "platform": platform.platform(), "solver": solver_environment(), "requirements_ref": "hybridguard_agent/config/rule_learning_v1_20260924/requirements-r03.txt",
        "temporary_environment_is_formal_R04_freeze": False})
    demo, all_predictions, all_metrics, selections, traces = [], [], [], [], []
    for name in ("union_budget", "complementary", "redundant", "negative", "and_required", "infeasible", "low_coverage", "empty_pool"):
        for method in ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2"):
            access = synthetic_fixture(name)
            result = fit(access, access.batch("train"), method)
            key = name + "__" + method
            save_model(result.model, out / "models" / (key + ".json"))
            model = load_model(out / "models" / (key + ".json"))
            predictions = predict_batch(model, access.batch("outer_test"), access.view["view_id"])
            metrics = evaluate(access.batch("outer_test").ids, predictions, access.evaluation_metadata("outer_test"))
            all_predictions.extend(dict(r, fixture_id=name) for r in predictions)
            all_metrics.append({"fixture_id": name, "method": method, "model_id": model.model_id, "report": metrics})
            selections.extend(selection_rows(result))
            traces.append({"fixture_id": name, "method": method, "model_id": model.model_id, "trace": result.trace,
                           "candidate_manifest": result.candidate_manifest, "support": result.support})
            demo.append({"fixture_id": name, "method": method, "model_id": model.model_id, "status": model.status,
                         "fit_status": model.fit["status"], "selected": [c.id for c in model.clauses],
                         "training_summary": model.fit["training_result"], "fit_train_n": model.fit["train_expected_n"],
                         "prediction_expected_n": len(predictions), "clean_budget_count": model.fit["clean_budget_count"],
                         "best_bound": model.fit.get("best_bound"), "gap": model.fit.get("gap")})
    raw = synthetic_fixture("numeric")
    access = single_surface_view(raw, "native84")
    result = fit(access, access.batch("train"))
    save_model(result.model, out / "models/single_surface_native.json")
    reloaded = load_model(out / "models/single_surface_native.json")
    predictions = [predict_single_surface(reloaded, oid, row) for oid, row in zip(raw.batch("outer_test").ids, raw.batch("outer_test").records)]
    if predictions != predict_batch(reloaded, access.batch("outer_test"), access.view["view_id"]):
        raise AssertionError("FROZEN_ENCODER_ROUNDTRIP_MISMATCH")
    dump(out / "SINGLE_SURFACE_VALIDATION.json", {"status": "PASS", "encoder": reloaded.encoder,
        "synthetic_predictions": predictions, "model_id": reloaded.model_id,
        "R02_unfitted_inputs_are_boolean": False,
        "registered_input_counts": {s: Counter("unfitted_numeric" if a.atom_id.startswith("UNFITTED_CONTROL:") else "fixed" for a in single_surface_definitions(s)) for s in ("native84", "host26", "app_web67")}})
    source_views = []
    for bits in range(8):
        condition = "SRC-" + format(bits, "03b")
        view = core_view(synthetic_fixture("aliases"), condition)
        source_views.append({"condition": condition, "view_id": view.view["view_id"], "canonical_atom_n": len(view.atoms),
                             "atoms": [vars(a) for a in view.atoms], "learned_model": "NOT_FITTED_STATIC_INTERFACE_CHECK"})
    dump(out / "BASELINE_SOURCE_INTERFACES.json", {"status": "PASS", "historical_seven": historical_seven_contract(),
        "source_views": source_views, "real_source_retraining": "R06_NOT_RUN", "common_measurement_contract": "r01-measurement-v1"})
    dump_lines(out / "synthetic_predictions.jsonl", all_predictions)
    dump_lines(out / "synthetic_metrics.jsonl", all_metrics)
    dump_lines(out / "selection_rows.jsonl", selections)
    dump_lines(out / "training_traces.jsonl", traces)
    dump(out / "SYNTHETIC_DEMO_RESULTS.json", demo)
    dump(out / "HAND_CALCULATIONS.json", evidence["hand_metrics"])
    dump(out / "MODEL_VALIDATION.json", {"status": "PASS", "tests": [r for r in records if ".ModelTests." in r["test"] or ".SelectorTests." in r["test"]],
        "ip_exhaustive_checks": evidence["ip_exhaustive_checks"], "native_timeout": evidence["native_timeout"],
        "greedy_prune": evidence["greedy_prune"], "failure_branches": evidence["failure_branches"],
        "forced_failure_cases": "explicit synthetic injection, not observations of production solver reliability",
        "model_save_load_prediction_and_encoder_equivalence": True})
    dump(out / "LEAKAGE_VALIDATION.json", {"status": "PASS", "tests": [r for r in records if ".LeakageAndBaselineTests." in r["test"]],
        "formal_gate": "CLOSED_R03", "synthetic_origin": "NAMED_PROGRAMMATIC_RECIPES_NO_CALLER_DATA",
        "synthetic_flag_or_renamed_ID_admission": False, "old_R02_stage_denial_is_solver_failure": False,
        "test_labels": "fixed model prediction invariant", "train_labels": "coherent changed admission can change learned model",
        "boundary": "trusted-code workflow capability, not an OS sandbox against arbitrary Python reflection"})
    dump(out / "METRIC_VALIDATION.json", {"status": "PASS", "tests": [r for r in records if ".MetricTests." in r["test"]],
        "hand_fractions": evidence["hand_metrics"]["expected_fractions"], "unknown_truth_never_promoted": True,
        "missing_expected_predictions_count_as_failures": True})
    dump(out / "FORMAL_FIT_ENTRY.json", {"status": "CLOSED_R03_NOT_AUTHORIZATION", "request_fields": [f.name for f in fields(FormalFitRequest)],
        "issuer_entry": "access.open_formal_fit", "current_behavior": "always raises stage authorization error after request-shape checks",
        "R04_must_bind": ["R01 eight configs and digest", "R02 raw per-alias cells, reasons and cache lineage",
            "exact fold membership and S01 roles", "R03 code and synthetic fixtures", "HiGHS 1.12.0, NumPy 2.3.5, Python and platform",
            "single-surface metadata and encoder code", "source-specific projection and all aliases",
            "S06 historical method/input proof and original coverage schema", "expected fit/model/prediction job manifests",
            "global fit count/wall-clock priority and per-fit shared deadline", "freeze-before-test-read runner and explicit OOF aggregation"],
        "later_stage_must_authorize": "each real fit job; a caller-provided stage string or freeze file is insufficient"})
    with (out / "FOCUSED_TESTS.txt").open("x") as f:
        f.write(transcript)
    after = protected_snapshot()
    if before != after:
        raise AssertionError("PROTECTED_HISTORICAL_INPUTS_CHANGED")
    dump(out / "READ_ONLY_CHECK.json", {"status": "PASS", "protected_file_n": len(before),
        "check": "this invocation size/mtime before == after; separate from old execution-time validation",
        "snapshot": before, "historical_artifact_hash_scans": 0})
    summary = {"status": "PASS_IMPLEMENTATION_AND_SYNTHETIC_ONLY", "step": "R03", "user_acceptance": "PENDING",
        "reviewed_commit": REVIEW_COMMIT, "protocol_digest": binding()["protocol_digest"],
        "synthetic_tests_passed": len(records), "ip_exhaustive_comparisons": len(evidence["ip_exhaustive_checks"]),
        "saved_synthetic_models": len(demo) + 1, "saved_synthetic_demo_prediction_rows": len(all_predictions) + len(predictions),
        "saved_demo_status_counts": dict(Counter(r["status"] for r in demo)), "solver": solver_environment(),
        "real_fits": 0, "real_rule_rankings": 0, "real_threshold_fits": 0, "real_risk_predictions": 0,
        "real_source_retraining": 0, "matrix_rebuilds": 0, "legacy_S07": 0, "R04_R05_started": False,
        "column_generation": "NOT_IMPLEMENTED_NOT_AUTHORIZED_BY_R01", "git_commit_push": False,
        "completed_at": datetime.now(timezone.utc).isoformat(), "formal_fit_gate": "CLOSED_R03"}
    dump(out / "VALIDATION.json", summary)
    return summary


def validate(directory):
    out = Path(directory)
    review_inputs()
    records, evidence, _ = run_synthetic_tests()
    saved = read_json(out / "VALIDATION.json")
    if saved["protocol_digest"] != binding()["protocol_digest"] or saved["synthetic_tests_passed"] != len(records):
        raise ValueError("SAVED_VALIDATION_BINDING_OR_TEST_COUNT_CHANGED")
    for p in (out / "models").glob("*.json"):
        model = load_model(p)
        if model.binding["data_origin"] != "BUILTIN_SYNTHETIC" or model.fit["fit_scope"] != "SYNTHETIC_ONLY":
            raise ValueError("R03_ARTIFACT_NOT_SYNTHETIC")
        if any(not i.startswith("fixture-") for i in model.fit["train_ids"]):
            raise ValueError("R03_MODEL_IDS_NOT_FIXTURE_IDS")
    by_model = {load_model(p).model_id: load_model(p) for p in (out / "models").glob("*.json")}
    saved_predictions = read_jsonl(out / "synthetic_predictions.jsonl")
    for r in saved_predictions:
        model = by_model[r["model_id"]]
        access = synthetic_fixture(r["fixture_id"])
        current = {x["opaque_id"]: x for x in predict_batch(model, access.batch("outer_test"), access.view["view_id"])}[r["opaque_id"]]
        if dict(current, fixture_id=r["fixture_id"]) != r:
            raise ValueError("SAVED_PREDICTION_NOT_REPRODUCIBLE")
    for r in read_jsonl(out / "synthetic_metrics.jsonl"):
        access = synthetic_fixture(r["fixture_id"])
        predictions = [p for p in saved_predictions if p["model_id"] == r["model_id"]]
        actual = evaluate(access.batch("outer_test").ids, predictions, access.evaluation_metadata("outer_test"))
        if actual != r["report"]:
            raise ValueError("SAVED_METRICS_NOT_REPRODUCIBLE_FROM_SAVED_PREDICTIONS")
    single = read_json(out / "SINGLE_SURFACE_VALIDATION.json")
    raw = synthetic_fixture("numeric").batch("outer_test")
    predictions = [predict_single_surface(by_model[single["model_id"]], oid, row) for oid, row in zip(raw.ids, raw.records)]
    if predictions != single["synthetic_predictions"]:
        raise ValueError("SAVED_NUMERIC_ENCODER_NOT_REPRODUCIBLE")
    for name in FIXTURES:
        saved_fixture = read_json(out / "fixtures" / (name + ".json"))
        expected_fixture = json.loads(json.dumps(export_fixture(name)))
        if saved_fixture != expected_fixture:
            raise ValueError("SAVED_FIXTURE_RECIPE_MISMATCH:" + name)
    return {"status": "PASS_READ_ONLY", "synthetic_tests_passed": len(records),
            "saved_models": len(by_model), "real_fits": 0, "real_risk_predictions": 0}
