"""Read saved tables only; emit auditable plotting sources, never predictions."""
from __future__ import annotations

from collections import defaultdict
import csv
import json
from pathlib import Path

from hybridguard_agent.research.manipulation_eval.contract import read_json, read_jsonl
from hybridguard_agent.research.manipulation_eval.persistence import new_output, write_json


def relation_role_diagnostic(events):
    """Current-v3 ungated relation projection; explicitly not a risk decision."""
    candidates = [e for e in events if e["decision_role"] == "alert_candidate" and e["source_condition_included"]]
    deviations = [e for e in candidates if e["original_outcome"] == "COUNTEREXAMPLE"]
    return {"diagnostic_id": "CURRENT_V3_RELATION_ROLE_PROJECTION", "claim_type": "RELATION_DIAGNOSTIC_NOT_RISK_PREDICTION",
            "original_candidate_conflict_rules": [e["rule_id"] for e in deviations],
            "original_candidate_conflict_families": sorted({e["decision_family"] for e in deviations}),
            "suppressed_by_v2": [{"rule_id": e["rule_id"], "A": e["relation_applicability"], "B": e["risk_candidate_eligibility"]}
                                 for e in deviations if not e["participates_in_risk"]],
            "raw_duplicate_rule_count": len(deviations),
            "dedup_binary_effect_at_threshold_one": "STRUCTURALLY_ZERO_ON_IDENTICAL_ELIGIBILITY",
            "not_a_third_independent_detector": True}


def source_overlap(joined, left, right):
    """Paired overlap of saved variants on identical admitted sample denominators."""
    index = {v: {r["opaque_id"]: r for r in joined if r["variant_id"] == v} for v in (left, right)}
    if set(index[left]) != set(index[right]):
        raise ValueError("Source comparison denominators differ")
    result = []
    for label in ("POSITIVE", "NEGATIVE", "UNKNOWN"):
        cells = {"both_alert": 0, "left_only": 0, "right_only": 0, "neither_alert": 0, "failed_pair": 0, "abstention_pair": 0}
        ids = []
        for opaque, a in index[left].items():
            b = index[right][opaque]
            if a["evaluation_label"] != b["evaluation_label"]:
                raise ValueError("Source comparison truth differs")
            if a["evaluation_label"] != label:
                continue
            ids.append(opaque)
            da, db = (r["prediction"]["risk"]["decision"] for r in (a, b))
            if "FAILED" in (da, db):
                cells["failed_pair"] += 1
                continue
            if "INSUFFICIENT_EVIDENCE" in (da, db):
                cells["abstention_pair"] += 1
            aa, ab = da == "MANIPULATION_ALERT", db == "MANIPULATION_ALERT"
            cells["both_alert" if aa and ab else "left_only" if aa else "right_only" if ab else "neither_alert"] += 1
        result.append({"left": left, "right": right, "label_scope": label, "n": len(ids), "opaque_ids": ids, **cells,
                       "net_alert_count_change": cells["right_only"] - cells["left_only"],
                       "status": "INCOMPLETE" if cells["failed_pair"] else "COMPLETE",
                       "claim_boundary": "Fixed source ablation with common gates; structural candidate overlap and no-candidate groups must accompany any increments."})
    return result


def export_figure_data(*, evaluation_dir, output, figure_spec_path):
    directory = Path(evaluation_dir)
    manifest = read_json(directory / "evaluation_manifest.json")
    if manifest["status"] != "COMPLETE" or not manifest["predictions_closed_before_join"]:
        raise ValueError("Figures require a completed saved evaluation join")
    metrics = read_json(directory / "metrics.json")
    joined = read_jsonl(directory / "evaluation_joined.jsonl")
    spec = read_json(figure_spec_path)
    if spec["contract_version"] != metrics["contract_version"]:
        raise ValueError("Figure contract differs from metrics")
    out = new_output(output, inputs=[evaluation_dir, figure_spec_path])
    base = {k: metrics[k] for k in ("study_version", "run_id", "protocol_digest", "execution_scope")}
    points = []
    for variant in metrics["variants"]:
        views = [{"dimension": "overall", "value": "ALL", **variant}, *variant["strata"]]
        for view in views:
            for metric in ("positive_TPR", "primary_control_mid_FPR", "clean_pre_FPR", "clean_post_FPR"):
                rate = view[metric]
                points.append({**base, "schema_version": "formal-figure-point-v2", "variant_id": variant["variant_id"],
                               "stratum": view["dimension"], "stratum_value": view["value"], "metric": metric,
                               "k": rate["alert"], "n": rate["n"], "rate": rate["rate"], "no_alert": rate["no_alert"],
                               "abstain": rate["abstain"], "failed": rate["failed"], "coverage": rate["decision_coverage"],
                               "status": rate["status"], "interval_method": rate["interval_method"],
                               "source_ref": f"metrics.json#variant={variant['variant_id']};stratum={view['dimension']}:{view['value']};metric={metric}"})
    with (out / "metric_points.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(points[0]) if points else ["variant_id", "metric", "n"])
        writer.writeheader(); writer.writerows(points)
    trajectories = [{**base, "schema_version": "formal-figure-stage-v2", "opaque_id": r["opaque_id"], "variant_id": r["variant_id"],
                     "phase": r["evaluation"]["phase"], "triplet_id": r["evaluation"]["triplet_id"],
                     "configuration_id": r["evaluation"].get("configuration_id"), "cohort": r["evaluation"].get("cohort"),
                     "decision": r["prediction"]["risk"]["decision"], "score": r["prediction"]["risk"]["alert_score"],
                     "source_ref": f"evaluation_joined.jsonl#row={i}"} for i, r in enumerate(joined, 1)]
    with (out / "stage_points.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(trajectories[0]) if trajectories else ["opaque_id", "variant_id", "phase"])
        writer.writeheader(); writer.writerows(trajectories)
    result = {**base, "schema_version": "formal-figure-manifest-v2", "source_tables": ["metrics.json", "evaluation_joined.jsonl"],
              "source_prediction_rows": len(joined), "metric_points": len(points), "stage_points": len(trajectories),
              "filters": "All saved variants and predefined strata; no result-dependent selection.",
              "paper_result": metrics["execution_scope"] != "SYNTHETIC_CONTRACT_TEST",
              "rendered_figures": [], "figure_status": "DATA_INTERFACE_ONLY_NO_PAPER_FIGURES_IN_S04",
              "figure_spec_version": spec["figure_spec_version"], "detector_calls": 0, "LLM_calls": 0}
    write_json(out / "FIGURE_MANIFEST.json", result)
    return result
