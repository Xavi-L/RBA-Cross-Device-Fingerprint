#!/usr/bin/env python3
"""Frozen finite rule screening on P2 discovery, then untouched development.

Does not access reserved feature rows, optimize thresholds, train a model,
assign attack labels or change the production runtime.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.mtc_p3_candidates import evaluate_candidate
from hybridguard_agent.research.mtc_p3_data import load_split_records, inference_record


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, values):
    with path.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def aggregate(candidate, rows, results):
    if len(rows) != len(results):
        raise ValueError("Every admitted representative must have exactly one outcome")
    by_group = defaultdict(list)
    manufacturers = defaultdict(set)
    environments = defaultdict(Counter)
    for row, result in zip(rows, results):
        gid = row["_p2"]["group_id"]
        by_group[gid].append(result["outcome"])
        manufacturers[gid].add(row["_p2"]["profile"]["manufacturer"])
        profile = row["_p2"]["profile"]
        environments[(profile["manufacturer"], str(profile["android_api"]))][result["outcome"]] += 1
    group_outcomes = {}
    for gid, outcomes in by_group.items():
        # Any counterexample stays visible, even if another OS in the group is unknown.
        if "COUNTEREXAMPLE" in outcomes:
            result = "COUNTEREXAMPLE"
        elif "UNKNOWN" in outcomes:
            result = "UNKNOWN"
        elif "MATCH" in outcomes:
            result = "MATCH"
        else:
            result = "NOT_APPLICABLE"
        group_outcomes[gid] = result
    counts = Counter(group_outcomes.values())
    applicable = {g for g, o in group_outcomes.items() if o in {"MATCH", "COUNTEREXAMPLE"}}
    matching = sorted(g for g, o in group_outcomes.items() if o == "MATCH")
    return {"candidate_id": candidate["candidate_id"], "records": len(rows), "groups": len(by_group),
            "record_outcomes": dict(Counter(r["outcome"] for r in results)), "group_outcomes": dict(counts),
            "applicable_groups": len(applicable), "applicable_manufacturers": len({m for g in applicable for m in manufacturers[g]}),
            "matching_group_ids": matching,
            "counterexample_group_ids": sorted(g for g, o in group_outcomes.items() if o == "COUNTEREXAMPLE"),
            "unknown_group_ids": sorted(g for g, o in group_outcomes.items() if o == "UNKNOWN"),
            "group_agreement": counts["MATCH"] / len(applicable) if applicable else None,
            "unknown_reasons": dict(Counter(r["reason"] for r in results if r["outcome"] == "UNKNOWN")),
            "not_applicable_reasons": dict(Counter(r["reason"] for r in results if r["outcome"] == "NOT_APPLICABLE")),
            "environment_record_counts": [{"manufacturer": m, "android_api": api, "outcomes": dict(c)}
                                           for (m, api), c in sorted(environments.items())]}


def floor_met(summary, split, protocol):
    floor = protocol["candidate_support_floor"]["global_empirical"]
    return (summary["applicable_groups"] >= floor[split + "_groups"] and
            summary["applicable_manufacturers"] >= floor[split + "_manufacturers"])


def split_decision(candidate, summary, split, protocol):
    if candidate["admission_mode"] == "descriptive_only":
        return "DESCRIPTIVE_ONLY_SEMANTIC_LIMIT"
    if not floor_met(summary, split, protocol):
        return "INSUFFICIENT_APPLICABLE_SUPPORT"
    if summary["group_agreement"] < protocol["engineering_screening_min_group_agreement"]:
        return "COUNTEREXAMPLES_EXCEED_SCREEN"
    return "PASS_RESEARCH_SCREEN"


def evaluate_split(out, split, candidates, plan, protocol):
    rows = load_split_records(plan, split)
    summaries = {}
    all_results, exceptions = [], []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        results = []
        for row in rows:
            result = evaluate_candidate(candidate, inference_record(row))
            results.append(result)
            entry = {"candidate_id": cid, "sample_id": row["sample_id"], "group_id": row["_p2"]["group_id"],
                     "split": split, **result}
            all_results.append(entry)
            if result["outcome"] == "COUNTEREXAMPLE":
                exceptions.append({**entry, "profile": row["_p2"]["profile"],
                                   "source_line": row["_p2"]["source_line"],
                                   "app_payload_sha256": row["app"]["payload_sha256"],
                                   "browser_payload_sha256": row["browser"]["payload_sha256"],
                                   "values": {path: row["features"].get(path) for path in candidate["dependencies"]},
                                   "label_status": "unknown", "attack_inferred": False})
        summary = aggregate(candidate, rows, results)
        summary["screen_decision"] = split_decision(candidate, summary, split, protocol)
        summaries[cid] = summary
    write_json(out / f"{split}_summary.json", summaries)
    write_jsonl(out / f"{split}_results.jsonl", all_results)
    write_jsonl(out / f"{split}_counterexamples.jsonl", exceptions)
    return summaries


def execute(plan, baseline, config, out):
    if out.exists():
        raise ValueError("Output exists; never overwrite a frozen P3 run")
    protocol = json.loads((config / "mtc_p3_discovery_protocol.v1.json").read_text())
    catalog = json.loads((config / "mtc_p3_candidate_templates.v1.json").read_text())
    candidates = catalog["candidates"]
    old = json.loads((baseline / "summary.json").read_text())
    if old.get("version") != "mtc-legacy-rule-baseline-v1" or set(old.get("splits", {})) != {"discovery", "development"}:
        raise ValueError("Completed old-rule baseline must precede discovery")
    if Path(old["plan_dir"]).resolve() != plan.resolve():
        raise ValueError("Old baseline used a different P2 plan")
    p2_protocol = json.loads((plan / "protocol.json").read_text())
    if protocol["candidate_support_floor"] != p2_protocol["candidate_support_floor"]:
        raise ValueError("P2 support floors must stay unchanged")
    if len({c["candidate_id"] for c in candidates}) != len(candidates):
        raise ValueError("Duplicate candidate ID")
    sources = json.loads((config / "mtc_p3_semantic_sources.v1.json").read_text())
    source_ids = {s["id"] for s in sources["sources"]}
    for c in candidates:
        if not set(c["official_source_ids"]) <= source_ids:
            raise ValueError("Unresolved semantic source")
    out.mkdir(parents=True)
    for name in ("mtc_p3_discovery_protocol.v1.json", "mtc_p3_candidate_templates.v1.json", "mtc_p3_semantic_sources.v1.json"):
        shutil.copy2(config / name, out / name)
    shutil.copy2(__file__, out / "runner.py")
    for name in ("mtc_p3_candidates.py", "mtc_p3_data.py"):
        shutil.copy2(ROOT / "hybridguard_agent" / "research" / name, out / name)
    started = utc_now()
    discovery = evaluate_split(out, "discovery", candidates, plan, protocol)
    selected = [c["candidate_id"] for c in candidates if discovery[c["candidate_id"]]["screen_decision"] == "PASS_RESEARCH_SCREEN"]
    # This file is persisted before development feature access. No new candidate or
    # tolerance is introduced after seeing development counterexamples.
    write_json(out / "discovery_selection_FREEZE.json", {"frozen_at_utc": utc_now(), "candidate_ids": selected,
               "all_template_ids": [c["candidate_id"] for c in candidates], "parameters_frozen": True,
               "development_seen_by_this_runner": False,
               "prior_p3_development_exposure": protocol.get("prior_p3_development_exposure", False),
               "reserved_features_read": False})
    development = evaluate_split(out, "development", candidates, plan, protocol)
    final = []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        d, v = discovery[cid], development[cid]
        if cid not in selected:
            disposition = "NOT_SELECTED_DISCOVERY: " + d["screen_decision"]
        elif v["screen_decision"] != "PASS_RESEARCH_SCREEN":
            disposition = "HELD_AFTER_DEVELOPMENT: " + v["screen_decision"]
        else:
            disposition = {"empirical": "EMPIRICAL_RESEARCH_RELATION", "semantic": "SEMANTIC_RESEARCH_CONSTRAINT",
                           "collector": "COLLECTOR_CONSISTENCY_ONLY"}[candidate["admission_mode"]]
        final.append({**candidate, "disposition": disposition, "discovery": d, "development": v,
                      "exception_references": [f"{s}_counterexamples.jsonl#candidate_id={cid}" for s in ("discovery", "development")],
                      "reserved_validation": "NOT_EVALUATED_LOCKED", "risk_weight": None,
                      "empirical_selection_applied": True,
                      "evaluation_boundary": "Unlabelled relation observation, not FPR/TPR/attack or benign proof"})
    admitted = [c for c in final if c["disposition"] in {"EMPIRICAL_RESEARCH_RELATION", "SEMANTIC_RESEARCH_CONSTRAINT", "COLLECTOR_CONSISTENCY_ONLY"}]
    write_json(out / "candidate_catalog.v2.json", {"catalog_version": "mtc-candidate-catalog-v2", "candidates": final})
    write_json(out / "rule_catalog.v2.json", {"catalog_version": "mtc-research-rule-catalog-v2", "rules": admitted,
               "stage": "P3_OFFLINE_ONLY", "production_rule_catalog": False,
               "risk_scoring_allowed": False, "reserved_validation": "NOT_EVALUATED_LOCKED"})
    summary = {"p3_status": "COMPLETE", "started_at_utc": started, "completed_at_utc": utc_now(),
               "old_baseline": str(baseline.resolve()), "old_baseline_frozen_at": old["generated_at"],
               "p2_plan": str(plan.resolve()), "candidate_count": len(final),
               "discovery_selected_count": len(selected), "disposition_counts": dict(Counter(c["disposition"] for c in final)),
               "reserved_feature_rows_decoded": 0, "production_runtime_changed": False,
               "detection_metrics": "NOT_EVALUATED_NO_INDEPENDENT_LABELS", "models_trained": 0,
               "thresholds_fitted": 0, "new_candidate_search_after_development": False,
               "prior_p3_development_exposure": protocol.get("prior_p3_development_exposure", False),
               "research_principle": protocol["research_principle"]}
    # Counts come from execution, not expected MTC cohort sizes.
    summary["discovery_records"] = next(iter(discovery.values()))["records"]
    summary["development_records"] = next(iter(development.values()))["records"]
    write_json(out / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--baseline-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p3_legacy_20260922")
    parser.add_argument("--config-dir", type=Path, default=ROOT / "hybridguard_agent/config")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.plan_dir, args.baseline_dir, args.config_dir, args.out_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
