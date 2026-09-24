#!/usr/bin/env python3
"""S06 saved-output accounting only. Never imports or runs a detector/Verifier."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def read(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    binding = read(out / "JOB_BINDING.json")
    snapshot = Path(binding["snapshot"])
    repo = snapshot.parents[3]
    checks = []

    def check(name, condition, detail):
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            raise AssertionError(name)

    key = lambda r: (r["opaque_id"], r["variant_id"])
    job = read(out / "RUNNABLE_JOB.json")
    static = read(snapshot / "step_execution_plans/S06.json")
    protocol = read(snapshot / "protocol.json")
    expected = job["expected_units"]
    expected_keys = [key(r) for r in expected]
    expected_set = set(expected_keys)
    variants = {r["variant_id"]: r for r in job["variants"]}
    check("exact_static_unit_binding", expected == static["expected_units"] and job["variants"] == static["variants"]
          and len(expected_keys) == len(expected_set) == 432 and len({k[0] for k in expected_keys}) == 216,
          "432 unique method-stage units; 216 unique stages; same frozen order and two App177/SRC-111 variants")
    check("historical_authorization_preserved", static["status"] == "PLANNED_NOT_AUTHORIZED"
          and static["not_a_runnable_S04_job"] and protocol["execution_authorization"]["formal_execution_authorized"] is False
          and job["freeze"]["authorized_execution_step"] == "S06", "Only new job carries this S06 authorization")
    check("job_and_version_binding", hashlib.sha256((out / "RUNNABLE_JOB.json").read_bytes()).hexdigest() == binding["job_sha256"]
          and job["protocol_digest"] == protocol["protocol_digest"] == binding["protocol_digest"]
          and protocol["freeze_revision"] == binding["freeze_revision"] == "formal-manipulation-freeze-r1"
          and job["contract_version"] == "formal-manipulation-relation-risk-attribution-v2"
          and job["policy_version"] == "formal-manipulation-family-or-v2", "Explicit r1 / v2 binding; no schema or policy fallback")
    startup = read(out / "STARTUP_VALIDATION.json")
    check("frozen_startup_validation", startup["status"] == startup["startup_resource_preflight"] == "PASS"
          and startup["protocol_digest"] == binding["protocol_digest"],
          {k: startup[k] for k in ("bound_file_count", "source_count", "resource_count", "semantic_invariance")})
    pred = list(rows(out / "prediction/predictions.jsonl"))
    check("predictions_exact_once", [key(r) for r in pred] == expected_keys and len({key(r) for r in pred}) == 432,
          "No missing, duplicate, substituted or extra units")
    predictions = {key(r): r for r in pred}
    check("prediction_binding_and_no_evaluation_metadata", all(
        r["protocol_digest"] == job["protocol_digest"] and r["run_id"] == job["run_id"]
        and r["contract_version"] == job["contract_version"] and r["policy_version"] == job["policy_version"]
        and not (set(r) & {"evaluation", "evaluation_label", "phase", "tool", "config", "original_path", "session", "install", "group", "post"})
        for r in pred), "Prediction envelope has only job identity and worker outputs")
    receipts = list(rows(out / "UNIT_EXECUTION_RECEIPTS.jsonl"))
    check("single_attempt_receipts", [key(r) for r in receipts] == expected_keys
          and [r["ordinal"] for r in receipts] == list(range(1, 433))
          and all(r["attempt"] == 1 for r in receipts), "432 returns, one attempt each; no automatic retries")
    event_counts, event_ids = Counter(), set()
    mandatory = {"original_outcome", "original_result", "decision_role", "provenance_group", "original_evidence_family",
                 "decision_family", "relation_applicability", "risk_candidate_eligibility", "attribution_certainty",
                 "participates_in_risk", "participation_reason", "verification_valid"}
    event_shape = True
    for event in rows(out / "prediction/rule_events.jsonl"):
        k = key(event)
        ek = (*k, event["rule_id"])
        event_shape &= k in expected_set and mandatory <= set(event) and ek not in event_ids
        event_ids.add(ek)
        event_counts[k] += 1
    check("complete_original_rule_events", event_shape and set(event_counts) == expected_set
          and all(n == (87 if variants[k[1]]["method"] == "final_v3_v2" else 19) for k, n in event_counts.items()),
          {"rows": sum(event_counts.values()), "final_catalog_per_unit": 87, "legacy_catalog_per_unit": 19,
           "final_ACTIVE_rules": 57, "includes_non_active_dispositions": True})
    runtime_keys, bad_verification = [], []
    for record in rows(out / "prediction/runtime_records.jsonl"):
        runtime_keys.append(key(record))
        if not (record["runtime"]["verification"]["valid"] and record["risk_verification"]["valid"]):
            bad_verification.append(key(record))
    check("saved_runtime_and_verifier_results", runtime_keys == expected_keys and not bad_verification,
          {"runtime_rows": len(runtime_keys), "saved_original_and_risk_verifiers_valid": not bad_verification,
           "verifier_reexecutions_in_this_check": 0})
    failures = list(rows(out / "prediction/failures.jsonl"))
    abstentions = list(rows(out / "prediction/abstentions.jsonl"))
    check("failure_and_abstention_accounting", {key(r) for r in failures} == {key(r) for r in pred if r["risk"]["decision"] == "FAILED"}
          and {key(r) for r in abstentions} == {key(r) for r in pred if r["risk"]["decision"] == "INSUFFICIENT_EVIDENCE"},
          {"failure_rows": len(failures), "abstention_rows": len(abstentions), "empty_files_retained": True})
    pa, ea = (read(out / n) for n in ("PREDICT_PROCESS_AUDIT.json", "EVALUATE_PROCESS_AUDIT.json"))
    root = Path(binding["runtime_source_root"])
    copy_paths = {r["actual_path"] for r in binding["runtime_files_copied"]}
    check("runtime_sources_configs_resources", all(a["all_algorithm_modules_from_snapshot_copy"]
          and a["config_dir"] == binding["config_dir"] and a["policy_path"] == binding["policy_path"]
          and a["preflight"]["status"] == "PASS" and not a["preflight"]["sample_files_read"]
          and all(Path(v).is_relative_to(root) and v in copy_paths for v in a["module_files"].values())
          and all(p in copy_paths for p in a["preflight"]["digest_checked_paths"])
          for a in (pa, ea)) and binding["copy_has_workspace_fallback"] is False,
          {"prediction_modules": len(pa["module_files"]), "evaluation_modules": len(ea["module_files"]),
           "resource_count": pa["preflight"]["resource_count"], "actual_paths": "PREDICT_PROCESS_AUDIT.json / EVALUATE_PROCESS_AUDIT.json"})
    check("isolated_subprocesses", all(a["interpreter_flags"] == {"dont_write_bytecode": True, "isolated": 1, "no_site": 1}
          and a["PYTHONPATH"] is None and a["cwd"] == binding["cwd"] for a in (pa, ea)),
          "Separate -I -B -S interpreters; empty cwd; frozen runtime plus standard library")
    check("full_chain_without_evaluation_reexecution", pa["call_counts"] == {
        "evidence": 432, "original_rules": 1296, "original_verifier": 864, "risk_events": 864,
        "risk_policy": 432, "risk_verifier": 432, "runtime_cards": 1296, "worker": 432}
        and not ea["call_counts"] and all(a["retry_count"] == a["LLM_calls"] == 0 for a in (pa, ea)),
        "Original Verifiers recompute internally; 432 experimental worker calls, no second experimental pass")
    check("worker_evaluation_isolation", not pa["facts_enabled"] and not pa["boundary_violations"] and not ea["boundary_violations"]
          and pa["worker_argument_names"] == ["payload", "contract", "condition_id", "input_view", "method"]
          and pa["worker_payload_keysets"] == [{"count": 432, "keys": ["adapter_version", "features", "field_quality", "field_status", "record_schema_version"]}]
          and not any("/evaluation/" in r["path"] for r in pa["read_paths"]),
          "Allowed current-session payload only; job identity stays in scheduler; independent facts opened only by evaluation")
    closure = read(out / "PREDICTION_CLOSURE.json")
    pm, em = read(out / "prediction/run_manifest.json"), read(out / "evaluation/evaluation_manifest.json")
    envelope = read(out / "run_manifest.json")
    check("closure_precedes_fact_join", pm["status"] == "PREDICTIONS_CLOSED" and pm["prediction_files_closed"]
          and not pm["facts_read"] and closure["status"] == "PASS" and not closure["facts_read_before_accounting"]
          and datetime.fromisoformat(pm["completed_at"]) < datetime.fromisoformat(closure["at"])
          <= datetime.fromisoformat(envelope["facts_join_started_at"])
          and em["predictions_closed_before_join"] and em["detector_calls"] == 0,
          {"prediction_closed": pm["completed_at"], "accounting_closed_and_join_enabled": closure["at"]})
    joined = list(rows(out / "evaluation/evaluation_joined.jsonl"))
    check("independent_join_exact_units", [key(r) for r in joined] == expected_keys
          and all(r["prediction"] == predictions[key(r)] for r in joined), "432 rows joined without replacing any saved decision")
    denominators = read(snapshot / "evaluation/task_denominators.json")
    metrics = read(out / "evaluation/metrics.json")
    metric_map = {"positive_TPR": "positive", "clean_pre_FPR": "clean_pre", "clean_post_FPR": "clean_post",
                  "verified_negative_all": "all_negative", "primary_control_mid_FPR": "control_mid"}
    denom_report = {}
    for variant in metrics["variants"]:
        vid = variant["variant_id"]
        selected = [r for r in joined if r["variant_id"] == vid]
        actual_members = {
            "positive": {r["opaque_id"] for r in selected if r["evaluation_label"] == "POSITIVE"},
            "all_negative": {r["opaque_id"] for r in selected if r["evaluation_label"] == "NEGATIVE"},
        }
        for phase in ("clean_pre", "clean_post", "control_mid"):
            actual_members[phase] = {r["opaque_id"] for r in selected if r["evaluation_label"] == "NEGATIVE" and r["evaluation"]["phase"] == phase}
        for metric, task in metric_map.items():
            ids = actual_members[task]
            assert ids == set(denominators[task]["members"])
            dc = Counter(r["prediction"]["risk"]["decision"] for r in selected if r["opaque_id"] in ids)
            m = variant[metric]
            assert m["n"] == len(ids) == denominators[task]["n"]
            for field, decision in {"alert": "MANIPULATION_ALERT", "no_alert": "NO_ALERT", "abstain": "INSUFFICIENT_EVIDENCE", "failed": "FAILED"}.items():
                assert m[field] == dc[decision]
            assert m["rate"] == (dc["MANIPULATION_ALERT"] / len(ids) if ids else None)
        denom_report[vid] = {k: {f: variant[k][f] for f in ("n", "alert", "no_alert", "abstain", "failed", "rate", "status")} for k in metric_map}
    check("frozen_denominators_and_metric_arithmetic", True, denom_report)
    controls = [r for r in joined if r["evaluation"]["admission_fact"]["kind"] == "control"]
    check("temporal_truth_unknown_and_FPR_unavailable", len(controls) == 108
          and all(r["evaluation_label"] == "UNKNOWN" and r["evaluation"]["admission_fact"]["no_intervention"]["status"] == "UNKNOWN" for r in controls)
          and all(v["primary_control_mid_FPR"]["n"] == v["temporal_all_points_FPR"]["n"] == 0
                  and v["primary_control_mid_FPR"]["rate"] is v["temporal_all_points_FPR"]["rate"] is None for v in metrics["variants"]),
          "54 UNKNOWN temporal stages per method; 18 midpoints per method; eligible FPR denominator 0, not observed 0%")
    trips = list(rows(out / "evaluation/triplet_results.jsonl"))
    temporal = list(rows(out / "evaluation/temporal_results.jsonl"))
    joined_map = {key(r): r for r in joined}
    for t in trips + temporal:
        for phase, oid in t["opaque_ids"].items():
            r = joined_map[(oid, t["variant_id"])]
            assert r["evaluation"]["phase"] == phase and r["evaluation"]["triplet_id"] == t["triplet_id"]
            assert r["prediction"]["risk"]["decision"] == t["phase_decisions"][phase]
    for v in metrics["variants"]:
        ts = [t for t in trips if t["variant_id"] == v["variant_id"]]
        assert {(t["bundle_id"], t["triplet_id"]) for t in ts} == {tuple(m) for m in denominators["eligible_triplets"]["members"]}
        assert len(ts) == v["triplets"]["n"] == denominators["eligible_triplets"]["n"]
        for t in ts:
            assert t["success_010"] == (t["phase_decisions"] == {"clean_pre": "NO_ALERT", "attack": "MANIPULATION_ALERT", "clean_post": "NO_ALERT"})
        assert sum(t["success_010"] for t in ts) == v["triplets"]["success_010"]
    check("triplet_and_temporal_traceability", len(trips) == 108 and len(temporal) == 36,
          "Every phase points to a saved independent unit; eligible 010 denominator 54 per method; all 18 temporal trajectories per method retained")
    configs = read(out / "analysis/configuration_summary.json")
    diagnostics = list(rows(out / "analysis/unit_diagnostics.jsonl"))
    check("configuration_and_unit_long_tables", len(configs) == 40 and sum(r["scheduled"] for r in configs) == 432
          and [key(r) for r in diagnostics] == expected_keys,
          "14 admitted attack configurations + 6 UNKNOWN controls, separately per method; all 432 unit reasons retained")
    check("bounded_risk_claims", all(r["risk"]["threshold"] == 1 and r["risk"]["calibrated_attack_probability"] is None
          and r["risk"]["attribution_certainty"]["status"] == "UNKNOWN" and r["risk"]["attack_classification"] == "NOT_EVALUATED"
          for r in pred), "Frozen family OR threshold 1; no inferred attack truth/probability or source contribution")
    baseline = read(out / "PREEXECUTION_READONLY_BASELINE.json")
    changed = [name for name, value in baseline.items() if not (repo / name).is_file()
               or {"size": (repo / name).stat().st_size, "mtime_ns": (repo / name).stat().st_mtime_ns} != value]
    check("historical_files_unchanged", not changed, {"registered_files": len(baseline), "changed": changed,
          "scope": "S01/S02/S03/S03-R/S04/S05/S05-R artifact and acceptance file size/mtime; no regeneration"})
    before = set(read(out / "PREEXECUTION_GIT_STATUS.json")["entries"])
    now = set(filter(None, subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"], cwd=repo).decode().split("\0")))
    allowed_prefix = str(out.relative_to(repo)) + "/"
    allowed_exact = {"deliverables/formal_experiment_execution_plan/EXECUTION_PLAN.md", "deliverables/formal_experiment_execution_plan/EXECUTION_STATUS.json"}
    unexpected = [r for r in now - before if not (r[3:].startswith(allowed_prefix) or r[3:] in allowed_exact)]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    index_clean = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo).returncode == 0
    check("git_scope_and_stop_boundary", before <= now and not unexpected and head == binding["review_commit"] and index_clean,
          {"existing_dirty_entries_preserved": len(before), "unexpected_new_changes": unexpected, "head": head,
           "index_empty": index_clean, "no_new_S07_S08_S10_paths": True})
    result = {"schema_version": "s06-saved-output-validation-v1", "status": "PASS", "at": datetime.now(timezone.utc).isoformat(),
              "scope": "SAVED_OUTPUT_ACCOUNTING_ONLY_NO_DETECTOR_OR_VERIFIER_REEXECUTION", "run_id": job["run_id"],
              "review_commit": head, "freeze_revision": binding["freeze_revision"], "protocol_digest": job["protocol_digest"],
              "contract_version": job["contract_version"], "policy_version": job["policy_version"],
              "expected_units": len(expected), "actual_unique_units": len(predictions), "rule_events": sum(event_counts.values()),
              "runtime_records": len(runtime_keys), "evaluation_rows": len(joined), "configuration_rows": len(configs),
              "failures": len(failures), "abstentions": len(abstentions), "checks_passed": len(checks), "checks": checks,
              "performance_is_not_an_acceptance_threshold": True,
              "scientific_result": {v["variant_id"]: {"attack": v["positive_TPR"], "triplets": v["triplets"]} for v in metrics["variants"]},
              "actual_experimental_worker_calls": 432, "detector_calls_during_this_validation": 0, "LLM_calls": 0,
              "synthetic_calls_this_step": 0, "upstream_reruns": 0, "S07_executed": False, "commit_or_push": False}
    save(out / "VALIDATION.json", result)
    with (out / "FOCUSED_CHECKS.txt").open("x") as stream:
        stream.write("S06 saved-output consistency checks; no detector, Verifier, synthetic or upstream replay.\n")
        for c in checks:
            stream.write(f"{c['status']} {c['name']}: {json.dumps(c['detail'], ensure_ascii=False)}\n")
        stream.write(f"RESULT: {len(checks)}/{len(checks)} PASS. No performance-based acceptance threshold.\n")
    print(json.dumps({k: result[k] for k in ("status", "checks_passed", "actual_unique_units", "rule_events", "failures", "abstentions")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
