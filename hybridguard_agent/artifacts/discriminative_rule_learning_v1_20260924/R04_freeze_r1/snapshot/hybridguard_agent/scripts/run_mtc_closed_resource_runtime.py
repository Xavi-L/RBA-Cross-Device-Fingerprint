#!/usr/bin/env python3
"""Accept v3 against frozen v2 and the final research pass, using existing rows."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.mtc_p3_data import load_split_records
from hybridguard_agent.rules.paired244 import CONFIG, DEFAULT_CATALOG, V2_CATALOG, execute_paired_rules, load_catalog
from hybridguard_agent.runtime.paired244 import analyze_paired244_record
from hybridguard_agent.adapters.paired244_catalog import runtime_cards


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(plan, study, output, splits=("discovery", "development")):
    if not splits or len(set(splits)) != len(splits) or not set(splits) <= {"discovery", "development"}:
        raise ValueError("Only discovery/development allowed; reserved stays locked")
    if output.exists():
        raise ValueError("Never overwrite a closed-resource acceptance")
    catalog, previous = load_catalog(), load_catalog(V2_CATALOG)
    research = json.loads((study / "summary.json").read_text())
    if research.get("status") != "COMPLETE" or Path(research["plan_dir"]).resolve() != plan.resolve():
        raise ValueError("Research must be complete on this frozen P2 plan")
    admitted = set(research["admitted_rule_ids"])
    unchanged = {r["rule_id"] for r in previous["rules"] if r["status"] == "ACTIVE"}
    current_map = {r["rule_id"]: r for r in catalog["rules"]}
    if any(current_map[r["rule_id"]] != r for r in previous["rules"] if r["rule_id"] in unchanged):
        raise ValueError("Original 54 contracts changed")
    if {r["rule_id"] for r in catalog["rules"] if r["status"] == "ACTIVE"} != unchanged | admitted:
        raise ValueError("Runtime admission differs from frozen research")
    browser = {rid for rid, r in current_map.items() if r["status"] == "ACTIVE" and any(p.startswith("browser.") for p in r["dependencies"])}
    expected = {}
    for split in splits:
        with (study / f"{split}_results.jsonl").open(encoding="utf-8") as source:
            for line in source:
                r = json.loads(line)
                if r["candidate_id"] in admitted:
                    key = (split, r["sample_id"], r["candidate_id"])
                    if key in expected:
                        raise ValueError("Duplicate research result")
                    expected[key] = r["outcome"]
    output.mkdir(parents=True)
    config_names = (DEFAULT_CATALOG.name, V2_CATALOG.name, "paired244_browser_relations.v3.json",
                    "paired244_browser_relations.v2.json", "paired244_resource_closure.v1.json",
                    "paired244_review_sources.v1.json", "mtc_p3_semantic_sources.v1.json",
                    "mtc_closed_resource_sources.v1.json", "mtc_closed_resource_protocol.v1.json",
                    "mtc_closed_resource_candidates.v1.json")
    for name in config_names:
        shutil.copyfile(CONFIG / name, output / name)
    code = ("scripts/run_mtc_closed_resource_runtime.py", "scripts/build_paired244_catalog_v3.py",
            "research/mtc_closed_resource.py", "evidence/paired244.py", "rules/paired244.py", "rules/legacy_backlog.py",
            "runtime/paired244.py", "adapters/paired244_catalog.py", "retrieval/paired244.py", "verification/paired244.py")
    for relative in code:
        target = output / "implementation" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "hybridguard_agent" / relative, target)
    write_json(output / "runtime_cards.json", runtime_cards(catalog))
    counts, rules = defaultdict(Counter), defaultdict(Counter)
    comparisons = drift = study_checks = masked = 0
    failures = []
    started = datetime.now(timezone.utc).isoformat()
    with (output / "results.jsonl").open("w") as results, (output / "decision_traces.jsonl").open("w") as traces:
        for split in splits:
            for index, row in enumerate(load_split_records(plan, split)):
                for view in ("Full244", "App177"):
                    identity = {"split": split, "input_sample_id": row["sample_id"], "input_view": view}
                    try:
                        result = analyze_paired244_record(row, input_view=view, catalog=catalog)
                        current = {r["rule_id"]: r for r in result["rule_execution"]["rule_results"]}
                        old = {r["rule_id"]: r for r in execute_paired_rules(result["evidence_bundle"], previous)["rule_results"]}
                        comparisons += len(unchanged)
                        difference = sum(current[rid] != old[rid] for rid in unchanged)
                        drift += difference
                        if difference:
                            raise AssertionError("Original active check changed")
                        if view == "Full244":
                            for rid in admitted:
                                prior = expected[(split, row["sample_id"], rid)]
                                allowed = {"UNKNOWN", "NOT_EVALUATED"} if prior == "UNKNOWN" else {prior}
                                if current[rid]["outcome"] not in allowed:
                                    raise AssertionError("Research expression changed in runtime")
                                study_checks += 1
                        if view == "App177":
                            if any(current[rid]["outcome"] != "NOT_EVALUATED" or current[rid]["used_fields"] for rid in browser):
                                raise AssertionError("Browser masking failed")
                            masked += len(browser)
                        if result["decision"]["pending_data_rule_ids"] or result["decision"]["pending_research_rule_ids"]:
                            raise AssertionError("Final resource closure still requests work")
                        meta = {**identity, "group_id": row["_p2"]["group_id"], "source_line": row["_p2"]["source_line"],
                                "control_plane_joined_after_execution": True}
                    except Exception as exc:
                        failure = {**identity, "status": "FAILED", "error": str(exc)}
                        failures.append(failure)
                        results.write(json.dumps(failure, ensure_ascii=False) + "\n")
                        continue
                    results.write(json.dumps({**meta, "status": "completed", "decision": result["decision"],
                                              "verification": result["decision_trace"]["verification"]},
                                             ensure_ascii=False, separators=(",", ":")) + "\n")
                    traces.write(json.dumps({**meta, "trace": result["decision_trace"]}, ensure_ascii=False, separators=(",", ":")) + "\n")
                    counts[(split, view)][result["decision"]["decision_status"]] += 1
                    for rid, item in current.items():
                        rules[(split, view, rid)][item["outcome"]] += 1
                    if index == 0:
                        write_json(output / f"example_{split}_{view}.json", result)
    write_json(output / "rule_summary.json", [{"split": s, "input_view": v, "rule_id": rid, "outcomes": dict(c)}
                                            for (s, v, rid), c in sorted(rules.items())])
    summary = {"status": "COMPLETE" if not failures else "FAILED", "started_at_utc": started,
               "completed_at_utc": datetime.now(timezone.utc).isoformat(), "catalog_version": catalog["catalog_version"],
               "catalog_status_counts": dict(Counter(r["status"] for r in catalog["rules"])),
               "new_active_rule_ids": sorted(admitted), "plan_dir": str(plan.resolve()), "study_dir": str(study.resolve()),
               "views": [{"split": s, "input_view": v, "records": sum(c.values()), "decisions": dict(c)} for (s, v), c in sorted(counts.items())],
               "original_54_check_comparisons": comparisons, "original_check_drift": drift,
               "research_runtime_comparisons": study_checks, "browser_masked_checks": masked,
               "failures": failures, "reserved_features_decoded": 0, "model_calls": 0,
               "open_research_items": 0, "collection_requested": False, "source_data_modified": False,
               "all_claims_validated": False, "detection_metrics": "NOT_EVALUATED"}
    write_json(output / "summary.json", summary)
    if failures:
        raise RuntimeError("Closed-resource runtime failures persisted")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--study-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_closed_resource_study_20260922")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.plan_dir, args.study_dir, args.out_dir), ensure_ascii=False, indent=2))
