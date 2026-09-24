"""Offline labels/phase join and fixed denominators; never imports a detector."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from pathlib import Path
from statistics import mean

from hybridguard_agent.research.manipulation_eval.contract import VERSION, POLICY_VERSION, keyed, read_json, read_jsonl
from hybridguard_agent.research.manipulation_eval.schemas import validate_record

ALERT = "MANIPULATION_ALERT"
NO_ALERT = "NO_ALERT"
ABSTAIN = "INSUFFICIENT_EVIDENCE"
GRADE = {"L1_RECEIPT_SUPPORTED", "L2_RAW_LOG_CORROBORATED"}
PHASES = ("clean_pre", "attack", "clean_post")


def evaluation_label(index):
    """Consume S01 adjudications verbatim; annotation, tool and phase cannot supply truth."""
    fact = index["admission_fact"]
    positive = fact["eligible_detection"]
    negative = any(fact[k] for k in ("eligible_pre_control", "eligible_post_control", "eligible_temporal_control"))
    if positive and negative:
        raise ValueError("Conflicting task admission")
    if positive and (fact["kind"] != "attack" or fact["phase"] != "attack"
                     or fact["execution"]["status"] != "SUPPORTED" or fact["observable_effect"]["status"] != "SUPPORTED"):
        raise ValueError("Positive admission lacks S01 execution/effect")
    if negative and fact["no_intervention"]["status"] != "SUPPORTED":
        raise ValueError("Negative admission lacks supported no_intervention; never promote UNKNOWN")
    if (positive or negative) and (fact["evidence_grade"] not in GRADE or fact.get("label_conflict", False)):
        raise ValueError("Admitted task contradicts saved evidence grade/conflict")
    if fact["eligible_pre_control"] and fact["phase"] != "clean_pre":
        raise ValueError("Pre-control phase mismatch")
    if fact["eligible_post_control"] and (fact["phase"] != "clean_post" or fact["rollback"]["status"] != "SUPPORTED"):
        raise ValueError("Post-control phase/rollback mismatch")
    for key in ("triplet_id", "phase", "environment_group_id", "bundle_id"):
        if index.get(key) != fact.get(key):
            raise ValueError("S02 index/S01 fact mapping conflict")
    return "POSITIVE" if positive else "NEGATIVE" if negative else "UNKNOWN"


def load_closed_predictions(directory):
    directory = Path(directory)
    manifest = read_json(directory / "run_manifest.json")
    if manifest.get("status") != "PREDICTIONS_CLOSED" or manifest.get("prediction_files_closed") is not True:
        raise ValueError("Join requires closed, fully accounted prediction files")
    if manifest["contract_version"] != VERSION or manifest["policy_version"] != POLICY_VERSION:
        raise ValueError("Saved prediction contract conflict")
    rows = read_jsonl(directory / "predictions.jsonl")
    expected = {(u["opaque_id"], u["variant_id"]) for u in manifest["expected_units"]}
    actual = {(r["opaque_id"], r["variant_id"]) for r in rows}
    if len(expected) != len(manifest["expected_units"]) or len(rows) != len(expected) or actual != expected:
        raise ValueError("Prediction denominator missing or duplicated")
    if manifest["prediction_count"] != len(rows) or manifest["failure_count"] != sum(r["execution_status"] == "FAILED" for r in rows):
        raise ValueError("Saved manifest counts disagree")
    variants = keyed(manifest["variants"], "variant_id")
    for r in rows:
        validate_record("predictions", r)
        if any(r[k] != manifest[k] for k in ("study_version", "run_id", "protocol_digest")):
            raise ValueError("Run binding mismatch")
        if any(r[k] != variants[r["variant_id"]][k] for k in ("condition_id", "method", "input_view")):
            raise ValueError("Variant binding mismatch")
    events = read_jsonl(directory / "rule_events.jsonl")
    event_keys = set()
    event_counts = Counter()
    for e in events:
        validate_record("rule_events", e)
        key = (e["opaque_id"], e["variant_id"])
        event_key = (*key, e["rule_id"])
        if key not in expected or event_key in event_keys:
            raise ValueError("Foreign or duplicate rule event")
        if any(e[k] != manifest[k] for k in ("study_version", "run_id", "protocol_digest")):
            raise ValueError("Rule event run binding mismatch")
        event_keys.add(event_key); event_counts[key] += 1
    if len(events) != manifest["rule_event_count"] or any(event_counts[(r["opaque_id"], r["variant_id"])] != (19 if r["method"] == "legacy19_v2" else 87) for r in rows):
        raise ValueError("Incomplete full-chain rule events")
    for table in ("failures", "abstentions", "runtime_records"):
        recorded = read_jsonl(directory / (table + ".jsonl"))
        for row in recorded:
            validate_record(table, row)
        required = {(r["opaque_id"], r["variant_id"]) for r in rows if table == "runtime_records"
                    or table == "failures" and r["execution_status"] == "FAILED"
                    or table == "abstentions" and r["risk"]["decision"] == ABSTAIN}
        if len(recorded) != len(required) or {(r["opaque_id"], r["variant_id"]) for r in recorded} != required:
            raise ValueError("Missing/duplicated saved failure, abstention or runtime record")
    return manifest, rows


def join_rows(predictions, index_rows):
    index = keyed(index_rows, "opaque_id")
    candidates = [r["candidate_id"] for r in index_rows if "candidate_id" in r]
    if len(candidates) != len(set(candidates)):
        raise ValueError("One S01 stage mapped to multiple evaluation units; do not inflate controls")
    joined = []
    for p in predictions:
        if p["opaque_id"] not in index:
            raise ValueError("Missing independent evaluation mapping")
        e = index[p["opaque_id"]]
        joined.append({"schema_version": "formal-evaluation-join-v2",
                       **{k: p[k] for k in ("study_version", "run_id", "protocol_digest", "opaque_id", "variant_id")},
                       "prediction": p, "evaluation": e, "evaluation_label": evaluation_label(e)})
    return joined


def rate_record(rows):
    counts = Counter(r["prediction"]["risk"]["decision"] for r in rows)
    n, alerts, failed = len(rows), counts[ALERT], counts["FAILED"]
    decided = alerts + counts[NO_ALERT]
    return {"n": n, "alert": alerts, "no_alert": counts[NO_ALERT], "abstain": counts[ABSTAIN], "failed": failed,
            "rate": alerts / n if n else None, "decision_coverage": decided / n if n else None,
            "conditional_rate": alerts / decided if decided else None,
            "identifiable_bounds": [alerts / n, (alerts + failed) / n] if n else None,
            "status": "NOT_EVALUATED_NO_ELIGIBLE_LABELS" if not n else "INCOMPLETE" if failed else "COMPLETE",
            "interval_method": "NO_POPULATION_CI_RELATED_ENVIRONMENT_GROUPS",
            "zero_wording": f"0/{n} observed" if n and not alerts else None}


def one_summary(rows):
    positive = [r for r in rows if r["evaluation_label"] == "POSITIVE"]
    negative = [r for r in rows if r["evaluation_label"] == "NEGATIVE"]
    fact = lambda r: r["evaluation"]["admission_fact"]
    controls = [r for r in negative if fact(r)["eligible_temporal_control"]]
    mid = [r for r in controls if r["evaluation"]["phase"] in {"control_mid", "mid"}]
    return {"scheduled": len(rows), "unknown_truth": sum(r["evaluation_label"] == "UNKNOWN" for r in rows),
            "all_decisions": dict(Counter(r["prediction"]["risk"]["decision"] for r in rows)),
            "positive_TPR": rate_record(positive), "verified_negative_all": rate_record(negative),
            "primary_control_mid_FPR": rate_record(mid), "temporal_all_points_FPR": rate_record(controls),
            "clean_pre_FPR": rate_record([r for r in negative if fact(r)["eligible_pre_control"]]),
            "clean_post_FPR": rate_record([r for r in negative if fact(r)["eligible_post_control"]])}


def triplet_results(rows, triplets):
    by_phase = {}
    for row in rows:
        e = row["evaluation"]
        key = (e["bundle_id"], e["triplet_id"], e["phase"])
        if key in by_phase:
            raise ValueError("Nonunique triplet phase; do not deduplicate equal payloads")
        by_phase[key] = row
    seen, output = set(), []
    for t in triplets:
        key = (t["bundle_id"], t["triplet_id"])
        if key in seen:
            raise ValueError("Duplicate frozen triplet denominator")
        seen.add(key)
        if not t["eligible_triplet"] or t["kind"] != "attack":
            continue
        members = [by_phase.get((*key, phase)) for phase in PHASES]
        decisions = [r["prediction"]["risk"]["decision"] if r else "MISSING_PHASE" for r in members]
        scores = [r["prediction"]["risk"]["alert_score"] if r else None for r in members]
        missing = [phase for phase, r in zip(PHASES, members) if r is None]
        failed = "FAILED" in decisions
        output.append({"bundle_id": key[0], "triplet_id": key[1], "phase_decisions": dict(zip(PHASES, decisions)),
                       "opaque_ids": {phase: r["opaque_id"] if r else None for phase, r in zip(PHASES, members)},
                       "success_010": decisions == [NO_ALERT, ALERT, NO_ALERT],
                       "missing_phases": missing, "status": "INCOMPLETE" if missing or failed else "COMPLETE",
                       "active_alert": decisions[1] == ALERT, "recovered_after_alert": decisions[1] == ALERT and decisions[2] == NO_ALERT,
                       "active_minus_pre": scores[1] - scores[0] if scores[0] is not None and scores[1] is not None else None,
                       "post_minus_pre": scores[2] - scores[0] if scores[0] is not None and scores[2] is not None else None})
    return output


def temporal_results(rows):
    groups = defaultdict(dict)
    phases = ("clean_pre", "control_mid", "clean_post")
    for row in rows:
        e = row["evaluation"]
        if e["admission_fact"]["kind"] != "control":
            continue
        key = (e["bundle_id"], e["triplet_id"])
        if e["phase"] in groups[key]:
            raise ValueError("Duplicate temporal control phase")
        groups[key][e["phase"]] = row
    output = []
    for (bundle, triplet), by_phase in sorted(groups.items()):
        members = [by_phase.get(p) for p in phases]
        scores = [r["prediction"]["risk"]["alert_score"] if r else None for r in members]
        output.append({"bundle_id": bundle, "triplet_id": triplet,
                       "phase_decisions": {p: r["prediction"]["risk"]["decision"] if r else "MISSING_PHASE" for p, r in zip(phases, members)},
                       "opaque_ids": {p: r["opaque_id"] if r else None for p, r in zip(phases, members)},
                       "phase_truth": {p: r["evaluation_label"] if r else "UNKNOWN" for p, r in zip(phases, members)},
                       "mid_minus_pre": scores[1] - scores[0] if scores[0] is not None and scores[1] is not None else None,
                       "post_minus_pre": scores[2] - scores[0] if scores[0] is not None and scores[2] is not None else None,
                       "truth_inferred_from_trajectory": False})
    return output


def matched_deltas(attack_trajectories, control_trajectories, frozen_matches):
    """Use predeclared environment/batch matching only; never search by scores."""
    attack = {(r["bundle_id"], r["triplet_id"]): r for r in attack_trajectories}
    control = {(r["bundle_id"], r["triplet_id"]): r for r in control_trajectories}
    output = []
    seen = set()
    for pair in frozen_matches:
        akey, ckey = tuple(pair["attack_key"]), tuple(pair["control_key"])
        if akey in seen or akey not in attack or ckey not in control or pair["matching_basis"] != "PREDECLARED_ENVIRONMENT_BATCH":
            raise ValueError("Invalid or duplicated predeclared delta matching")
        seen.add(akey)
        a, c = attack[akey]["active_minus_pre"], control[ckey]["mid_minus_pre"]
        output.append({**pair, "attack_delta": a, "control_delta": c,
                       "difference_in_deltas": a - c if a is not None and c is not None else None,
                       "status": "COMPLETE" if a is not None and c is not None else "INCOMPLETE",
                       "adds_negative_denominator_units": False, "causal_identification_claim": False})
    return output


def summarize(joined, triplets):
    variants = defaultdict(list)
    for row in joined:
        variants[row["variant_id"]].append(row)
    output, trajectories = [], []
    for vid, rows in sorted(variants.items()):
        summary = one_summary(rows)
        strata = []
        for dimension in ("configuration_id", "environment_group_id", "cohort", "evidence_grade", "api_level"):
            groups = defaultdict(list)
            for r in rows:
                e = r["evaluation"]
                value = e["admission_fact"].get(dimension) if dimension == "evidence_grade" else e.get(dimension)
                groups[str(value) if value is not None else "UNKNOWN"].append(r)
            strata.extend({"dimension": dimension, "value": key, **one_summary(members)} for key, members in sorted(groups.items()))
        ts = triplet_results(rows, triplets)
        macro = {}
        for metric in ("positive_TPR", "primary_control_mid_FPR", "verified_negative_all"):
            config_rates = [s[metric]["rate"] for s in strata if s["dimension"] == "configuration_id" and s[metric]["n"]]
            nested = defaultdict(lambda: defaultdict(list))
            for r in rows:
                e = r["evaluation"]
                nested[str(e.get("environment_group_id", "UNKNOWN"))][str(e.get("configuration_id", "UNKNOWN"))].append(r)
            group_rates = []
            for configs in nested.values():
                rates = [one_summary(rs)[metric]["rate"] for rs in configs.values() if one_summary(rs)[metric]["n"]]
                if rates:
                    group_rates.append(mean(rates))
            macro[metric] = {"configuration_equal_weight": mean(config_rates) if config_rates else None,
                             "environment_then_configuration_equal_weight": mean(group_rates) if group_rates else None,
                             "configuration_count": len(config_rates), "environment_group_count": len(group_rates),
                             "independent_device_claim": False}
        alerts = sum(t["active_alert"] for t in ts)
        triplet_summary = {"n": len(ts), "success_010": sum(t["success_010"] for t in ts),
                           "rate_010": sum(t["success_010"] for t in ts) / len(ts) if ts else None,
                           "incomplete": sum(t["status"] == "INCOMPLETE" for t in ts),
                           "active_alert_denominator": alerts, "recovered_after_alert": sum(t["recovered_after_alert"] for t in ts),
                           "conditional_recovery_rate": sum(t["recovered_after_alert"] for t in ts) / alerts if alerts else None,
                           "status": "NOT_EVALUATED" if not ts else "INCOMPLETE" if any(t["status"] == "INCOMPLETE" for t in ts) else "COMPLETE"}
        output.append({"variant_id": vid, **summary, "triplets": triplet_summary, "strata": strata, "macro": macro,
                       "temporal_trajectories": temporal_results(rows)})
        trajectories.extend({"variant_id": vid, **t} for t in ts)
    return {"schema_version": "formal-metrics-v2", "contract_version": VERSION, "policy_version": POLICY_VERSION,
            "variants": output, "denominator_policy": "Fixed admitted units; abstentions and failures retained; missing triplets never become 0.",
            "calibration": "NOT_RUN_NO_INDEPENDENT_CALIBRATION", "population_confidence_intervals": "NOT_ESTIMABLE_RELATED_GROUPS",
            "performance_scope": "Provided admitted evaluation set only; no claim about deployment prevalence."}, trajectories


def evaluate_saved(*, prediction_dir, index_path, triplets_path, output):
    # This is intentionally a distinct file entry point after prediction closure.
    manifest, predictions = load_closed_predictions(prediction_dir)
    joined = join_rows(predictions, read_jsonl(index_path))
    metrics, triplets = summarize(joined, read_jsonl(triplets_path))
    # Import persistence helpers only after the predictions are closed, never run a worker.
    from hybridguard_agent.research.manipulation_eval.persistence import new_output, write_json, write_jsonl
    out = new_output(output, inputs=[prediction_dir, index_path, triplets_path])
    metadata = {k: manifest[k] for k in ("study_version", "run_id", "protocol_digest", "execution_scope")}
    metrics.update(metadata)
    write_jsonl(out / "evaluation_joined.jsonl", joined)
    write_jsonl(out / "triplet_results.jsonl", [{**metadata, "schema_version": "formal-triplet-result-v2", **t} for t in triplets])
    write_jsonl(out / "temporal_results.jsonl", [{**metadata, "schema_version": "formal-temporal-result-v2", "variant_id": v["variant_id"], **t}
                                               for v in metrics["variants"] for t in v["temporal_trajectories"]])
    write_json(out / "metrics.json", metrics)
    rows = []
    for v in metrics["variants"]:
        for name in ("positive_TPR", "primary_control_mid_FPR", "verified_negative_all", "clean_pre_FPR", "clean_post_FPR"):
            rows.append({**metadata, "schema_version": "formal-metric-row-v2", "variant_id": v["variant_id"], "metric": name, **v[name]})
    with (out / "metrics.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["variant_id", "metric", "n"])
        writer.writeheader(); writer.writerows(rows)
    write_json(out / "evaluation_manifest.json", {**metadata, "schema_version": "formal-evaluation-manifest-v2",
               "status": "COMPLETE", "predictions_closed_before_join": True, "joined_units": len(joined),
               "prediction_run_id": manifest["run_id"], "detector_calls": 0, "LLM_calls": 0})
    return metrics
