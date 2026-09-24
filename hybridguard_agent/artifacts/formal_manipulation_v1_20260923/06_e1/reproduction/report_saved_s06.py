"""S06 saved-output exports only: no detector imports or prediction execution.

Existing frozen metrics remain canonical. Configuration rates are copied from
their saved strata and checked against saved joined rows. Additional outputs
explain coverage, trajectories and reasons without changing any decision.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from statistics import mean

ALERT, NO_ALERT, ABSTAIN = "MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE"


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def save(path, value):
    with Path(path).open("x") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")


def save_lines(path, values):
    with Path(path).open("x") as f:
        for value in values:
            f.write(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def csv_rows(path, values):
    with Path(path).open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--step-output", required=True, type=Path)
    a = p.parse_args()
    root = a.step_output.resolve()
    assert read(root / "PREDICTION_CLOSURE.json")["status"] == "PASS"
    assert read(root / "EVALUATE_PROCESS_AUDIT.json")["status"] == "PASS"
    assert read(root / "evaluation/evaluation_manifest.json")["predictions_closed_before_join"]
    out = root / "analysis"
    out.mkdir(exist_ok=False)
    metrics = read(root / "evaluation/metrics.json")
    joined = list(rows(root / "evaluation/evaluation_joined.jsonl"))
    trajectories = list(rows(root / "evaluation/triplet_results.jsonl"))
    expected = read(root / "RUNNABLE_JOB.json")["expected_units"]
    key = lambda r: (r["opaque_id"], r["variant_id"])
    by_unit = {key(r): r for r in joined}
    assert len(by_unit) == len(joined) == len(expected) and set(by_unit) == {key(r) for r in expected}
    failures = {key(r): r for r in rows(root / "prediction/failures.jsonl")}
    candidate_events, noncandidate_counterexamples = defaultdict(list), defaultdict(list)
    for event in rows(root / "prediction/rule_events.jsonl"):
        if event["decision_role"] == "alert_candidate" and event["source_condition_included"]:
            candidate_events[key(event)].append({k: event[k] for k in ("rule_id", "provenance_group", "decision_family", "original_outcome",
                "relation_applicability", "risk_candidate_eligibility", "attribution_certainty", "participates_in_risk", "triggers_family", "participation_reason")})
        elif event["original_outcome"] == "COUNTEREXAMPLE":
            noncandidate_counterexamples[key(event)].append({k: event[k] for k in ("rule_id", "decision_role", "participation_reason", "provenance_group")})
    diagnostics = []
    for unit in expected:
        joined_row = by_unit[key(unit)]
        e, pred = joined_row["evaluation"], joined_row["prediction"]
        risk, label = pred["risk"], joined_row["evaluation_label"]
        decision = risk["decision"]
        if decision == "FAILED":
            classification, reason = "TECHNICAL_FAILURE", "saved_pipeline_failure_not_a_scientific_negative"
        elif decision == ABSTAIN:
            classification, reason = "ABSTENTION", "no_candidate_family_evaluable_under_frozen_gates"
        elif label == "POSITIVE" and decision == NO_ALERT:
            classification, reason = "MISSED_ADMITTED_POSITIVE", "evaluable_candidate_families_have_no_qualifying_conflict"
        elif label == "NEGATIVE" and decision == ALERT:
            classification, reason = "ALERT_ON_ADMITTED_NEGATIVE", "qualifying_conflict_on_independently_admitted_clean_stage"
        elif label == "UNKNOWN":
            classification, reason = "UNKNOWN_TRUTH_DESCRIPTIVE_ONLY", "no_FPR_or_TPR_eligibility_inferred_from_trajectory_or_decision"
        else:
            classification, reason = "ADMITTED_TASK_DECISION", "saved_frozen_policy_result"
        events = candidate_events[key(unit)]
        assert risk["attribution_certainty"]["status"] == "UNKNOWN" and risk["calibrated_attack_probability"] is None
        assert not (decision == NO_ALERT and risk["evaluated_family_count"] == 0)
        annotation = e["admission_fact"].get("original_attack_annotation") or {}
        diagnostics.append({"opaque_id": unit["opaque_id"], "variant_id": unit["variant_id"], "method": pred["method"],
            "configuration_id": e["configuration_id"], "bundle_id": e["bundle_id"], "triplet_id": e["triplet_id"], "phase": e["phase"],
            "cohort": e["cohort"], "evaluation_label": label, "decision": decision, "alert_score": risk["alert_score"],
            "classification": classification, "primary_reason": reason,
            "eligible_family_ids": risk["eligible_family_ids"], "evaluated_family_ids": risk["evaluated_family_ids"],
            "triggered_family_ids": risk["triggered_family_ids"], "unavailable_family_ids": risk["unavailable_family_ids"],
            "candidate_events": events, "candidate_gate_reason_counts": dict(Counter(
                ev["participation_reason"] + ":A=" + ev["relation_applicability"]["reason"] + ":B=" + ev["risk_candidate_eligibility"]["reason"] for ev in events)),
            "noncandidate_original_counterexamples": noncandidate_counterexamples[key(unit)],
            "declared_expected_mutations_evaluation_only": annotation.get("expected_mutations", []),
            "failure": failures.get(key(unit)), "reason_scope": "Description of saved outcomes/gates; no causal attack attribution or retrospective rule selection"})
    save_lines(out / "unit_diagnostics.jsonl", diagnostics)
    save_lines(out / "missed_positive_units.jsonl", [r for r in diagnostics if r["evaluation_label"] == "POSITIVE" and r["decision"] != ALERT])
    save_lines(out / "admitted_negative_alerts.jsonl", [r for r in diagnostics if r["evaluation_label"] == "NEGATIVE" and r["decision"] == ALERT])
    configs, temporal, summary = [], [], []
    metric_names = ("positive_TPR", "clean_pre_FPR", "clean_post_FPR", "primary_control_mid_FPR", "verified_negative_all")
    for variant in metrics["variants"]:
        vid = variant["variant_id"]
        selected = [r for r in joined if r["variant_id"] == vid]
        ts = [r for r in trajectories if r["variant_id"] == vid]
        ds = [r for r in diagnostics if r["variant_id"] == vid]
        selected_method = selected[0]["prediction"]["method"]
        assert len(selected) == 216 and len(ts) == variant["triplets"]["n"] == 54
        assert sum(t["success_010"] for t in ts) == variant["triplets"]["success_010"]
        assert variant["primary_control_mid_FPR"]["n"] == 0 and variant["primary_control_mid_FPR"]["rate"] is None
        assert variant["temporal_all_points_FPR"]["n"] == 0 and variant["temporal_all_points_FPR"]["rate"] is None
        for stratum in [s for s in variant["strata"] if s["dimension"] == "configuration_id"]:
            cid = stratum["value"]
            members = [r for r in selected if str(r["evaluation"]["configuration_id"]) == cid]
            ids = {r["opaque_id"] for r in members}
            trips = [t for t in ts if set(t["opaque_ids"].values()) & ids]
            assert all(set(t["opaque_ids"].values()) <= ids for t in trips), "Triplet spans configuration keys; do not silently regroup"
            decisions = Counter(r["prediction"]["risk"]["decision"] for r in members)
            assert len(members) == stratum["scheduled"] and dict(decisions) == stratum["all_decisions"]
            row = {"variant_id": vid, "method": selected_method, "configuration_id": cid,
                   "cohorts": ";".join(sorted({r["evaluation"]["cohort"] for r in members})),
                   "environment_groups": ";".join(sorted({r["evaluation"]["environment_group_id"] for r in members})),
                   "scheduled": len(members), "alert": decisions[ALERT], "no_alert": decisions[NO_ALERT], "abstain": decisions[ABSTAIN], "failed": decisions["FAILED"],
                   "decision_coverage": (decisions[ALERT] + decisions[NO_ALERT]) / len(members), "unknown_truth": stratum["unknown_truth"]}
            for metric in metric_names:
                row.update({metric + "_" + k: stratum[metric][k] for k in ("n", "alert", "no_alert", "abstain", "failed", "rate", "decision_coverage", "status")})
            row.update(triplet_n=len(trips), success_010=sum(t["success_010"] for t in trips),
                       rate_010=sum(t["success_010"] for t in trips) / len(trips) if trips else None,
                       triplets_with_abstention=sum(ABSTAIN in t["phase_decisions"].values() for t in trips),
                       triplets_with_failure=sum("FAILED" in t["phase_decisions"].values() for t in trips),
                       attack_alert_triplets=sum(t["active_alert"] for t in trips), recovered_after_alert=sum(t["recovered_after_alert"] for t in trips),
                       mean_attack_minus_pre=mean(v) if (v := [t["active_minus_pre"] for t in trips if t["active_minus_pre"] is not None]) else None,
                       mean_post_minus_pre=mean(v) if (v := [t["post_minus_pre"] for t in trips if t["post_minus_pre"] is not None]) else None)
            configs.append(row)
            controls = [r for r in members if r["evaluation"]["admission_fact"]["kind"] == "control"]
            if controls:
                assert all(r["evaluation_label"] == "UNKNOWN" and r["evaluation"]["admission_fact"]["no_intervention"]["status"] == "UNKNOWN" for r in controls)
                for phase in ("ALL_POINTS", "clean_pre", "control_mid", "clean_post"):
                    rs = controls if phase == "ALL_POINTS" else [r for r in controls if r["evaluation"]["phase"] == phase]
                    dc = Counter(r["prediction"]["risk"]["decision"] for r in rs)
                    temporal.append({"variant_id": vid, "configuration_id": cid, "phase": phase, "n": len(rs),
                        "alert": dc[ALERT], "no_alert": dc[NO_ALERT], "abstain": dc[ABSTAIN], "failed": dc["FAILED"],
                        "truth": "UNKNOWN", "FPR": None, "FPR_status": "NOT_EVALUATED_NO_ELIGIBLE_LABELS", "scope": "DESCRIPTIVE_ONLY_NO_NEGATIVE_LABEL_PROMOTION"})
        missing_positive = [r for r in ds if r["evaluation_label"] == "POSITIVE" and r["decision"] != ALERT]
        counts = Counter(r["prediction"]["risk"]["decision"] for r in selected)
        row = {"variant_id": vid, "method": selected_method, "scheduled": len(selected), "all_decisions": dict(counts),
               "abstentions": counts[ABSTAIN], "failures": counts["FAILED"], "decision_coverage": (counts[ALERT] + counts[NO_ALERT]) / len(selected),
               "candidate_family_coverage_distribution": dict(Counter(str(r["prediction"]["risk"]["evaluated_family_count"]) + "/" + str(r["prediction"]["risk"]["eligible_family_count"]) for r in selected)),
               "unknown_truth": variant["unknown_truth"], "metrics": {name: variant[name] for name in metric_names}, "triplets": variant["triplets"],
               "triplets_with_abstention": sum(ABSTAIN in t["phase_decisions"].values() for t in ts),
               "triplets_with_failure": sum("FAILED" in t["phase_decisions"].values() for t in ts),
               "macro": variant["macro"], "missed_positive_primary_reasons": dict(Counter(r["primary_reason"] for r in missing_positive)),
               "candidate_gate_reasons_on_missed_positives": dict(Counter(reason for r in missing_positive for reason, count in r["candidate_gate_reason_counts"].items() for _ in range(count))),
               "technical_failure_types": dict(Counter(r["failure"]["stage"] + ":" + r["failure"]["error_type"] for r in ds if r["failure"])),
               "time_control_descriptive_decisions": dict(Counter(r["prediction"]["risk"]["decision"] for r in selected if r["evaluation"]["admission_fact"]["kind"] == "control")),
               "temporal_control_FPR": None, "temporal_control_FPR_status": "NOT_EVALUATED_NO_ELIGIBLE_LABELS"}
        summary.append(row)
    assert sum(r["scheduled"] for r in configs) == len(joined)
    assert sum(r["positive_TPR_n"] for r in configs) == sum(v["positive_TPR"]["n"] for v in metrics["variants"])
    assert sum(r["triplet_n"] for r in configs) == len(trajectories)
    save(out / "configuration_summary.json", configs)
    csv_rows(out / "configuration_summary.csv", configs)
    save(out / "temporal_control_descriptive.json", temporal)
    csv_rows(out / "temporal_control_descriptive.csv", temporal)
    save(out / "SUMMARY.json", {"status": "SAVED_OUTPUT_ANALYSIS_COMPLETE", "run_id": metrics["run_id"], "protocol_digest": metrics["protocol_digest"],
        "variants": summary, "configuration_rows": len(configs), "unit_diagnostic_rows": len(diagnostics),
        "science_and_technical_results_separated": True, "detector_calls": 0, "LLM_calls": 0,
        "statistical_limits": "Exposed admitted material replay, related environment groups, no deployment prevalence, independent-device or calibrated-probability claim",
        "time_control_policy": "UNKNOWN remains UNKNOWN; descriptive outputs never counted as FPR",
        "report_check": "Configuration counts reconcile with canonical frozen evaluator strata and exact triplet IDs; canonical metrics files not rewritten"})
    print(json.dumps({"status": "PASS", "configuration_rows": len(configs), "unit_diagnostic_rows": len(diagnostics), "detector_calls": 0}))


if __name__ == "__main__":
    main()
