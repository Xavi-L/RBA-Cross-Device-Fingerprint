#!/usr/bin/env python3
"""P4 execution acceptance on P2 admitted rows, never a detection experiment."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.mtc_p3_data import load_split_records
from hybridguard_agent.rules.paired244 import LEGACY_CATALOG as DEFAULT_CATALOG, load_catalog
from hybridguard_agent.runtime.paired244 import analyze_paired244_record
from hybridguard_agent.adapters.paired244_catalog import runtime_cards


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(plan, p3, output, splits=("discovery", "development")):
    if not splits or len(splits) != len(set(splits)) or not set(splits) <= {"discovery", "development"}:
        raise ValueError("Only distinct discovery/development splits are admitted; reserved stays locked")
    if output.exists():
        raise ValueError("Output exists; do not overwrite versioned P4 acceptance")
    catalog = load_catalog(DEFAULT_CATALOG)  # Historical P4 acceptance remains pinned to v1.
    p3_summary = json.loads((p3 / "summary.json").read_text())
    if p3_summary.get("p3_status") != "COMPLETE" or Path(p3_summary["p2_plan"]).resolve() != plan.resolve() or (p3 / "RUN_STATUS.json").exists():
        raise ValueError("Use the accepted P3 run tied to this P2 plan")
    p3_ids = {r["rule_id"] for r in catalog["rules"] if r["origin"] == "p3_research"}
    browser_ids = {r["rule_id"] for r in catalog["rules"] if r["status"] == "ACTIVE" and any(p.startswith("browser.") for p in r["dependencies"])}
    old_results = {}
    for split in splits:
        with (p3 / f"{split}_results.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["candidate_id"] in p3_ids:
                    key = (split, row["sample_id"], row["candidate_id"])
                    if key in old_results:
                        raise ValueError("Duplicate frozen P3 result")
                    old_results[key] = row["outcome"]
    output.mkdir(parents=True)
    shutil.copy2(DEFAULT_CATALOG, output / DEFAULT_CATALOG.name)
    for name in ("paired244_browser_relations.v1.json", "mtc_p3_semantic_sources.v1.json"):
        shutil.copy2(DEFAULT_CATALOG.parent / name, output / name)
    shutil.copy2(ROOT / "hybridguard_agent/schemas/evidence_bundle_v3.schema.json", output / "evidence_bundle_v3.schema.json")
    write_json(output / "runtime_cards.json", runtime_cards(catalog))
    code_files = ["scripts/run_mtc_p4_runtime.py", "evidence/paired244.py", "rules/paired244.py", "runtime/paired244.py",
                  "adapters/paired244_catalog.py", "retrieval/paired244.py", "verification/paired244.py"]
    for relative in code_files:
        target = output / "implementation" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "hybridguard_agent" / relative, target)
    started = datetime.now(timezone.utc).isoformat()
    rule_counts = defaultdict(Counter)
    counts = defaultdict(Counter)
    groups = defaultdict(set)
    checked_p3, masked_checks = 0, 0
    failed = []
    with (output / "results.jsonl").open("w", encoding="utf-8") as results_file, (output / "decision_traces.jsonl").open("w", encoding="utf-8") as traces:
        for split in splits:
            rows = load_split_records(plan, split)
            for index, row in enumerate(rows):
                for view in ("Full244", "App177"):
                    try:
                        result = analyze_paired244_record(row, input_view=view, catalog=catalog)
                    except Exception as exc:
                        failure = {"split": split, "input_sample_id": row["sample_id"], "input_view": view, "error": str(exc)}
                        failed.append(failure)
                        results_file.write(json.dumps({**failure, "status": "FAILED"}, ensure_ascii=False) + "\n")
                        continue
                    meta = {"input_sample_id": row["sample_id"], "group_id": row["_p2"]["group_id"], "split": split, "input_view": view,
                            "source_line": row["_p2"]["source_line"], "control_plane_joined_after_execution": True}
                    summary = {**meta, "status": "completed", "decision_id": result["decision_id"],
                               "evidence_hash": result["evidence_bundle"]["evidence_hash"], "decision": result["decision"],
                               "verification": result["decision_trace"]["verification"],
                               "selected_field_count": len(result["evidence_bundle"]["fields"])}
                    results_file.write(json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n")
                    traces.write(json.dumps({**meta, "trace": result["decision_trace"]}, ensure_ascii=False, separators=(",", ":")) + "\n")
                    if index == 0:
                        write_json(output / f"example_{split}_{view}.json", result)
                    counts[(split, view)][result["decision"]["decision_status"]] += 1
                    groups[(split, view)].add(row["_p2"]["group_id"])
                    for item in result["rule_execution"]["rule_results"]:
                        rid = item["rule_id"]
                        rule_counts[(split, view, rid)][item["outcome"]] += 1
                        if view == "App177" and rid in browser_ids:
                            if item["outcome"] != "NOT_EVALUATED" or item["used_fields"]:
                                raise AssertionError("Browser dependency evaluated after masking")
                            masked_checks += 1
                        if view == "Full244" and rid in p3_ids:
                            old = old_results[(split, row["sample_id"], rid)]
                            allowed = {"UNKNOWN", "NOT_EVALUATED"} if old == "UNKNOWN" else {old}
                            if item["outcome"] not in allowed:
                                raise AssertionError(f"Frozen P3 semantics drifted: {rid}: {old} -> {item['outcome']}")
                            checked_p3 += 1
    write_json(output / "rule_summary.json", [{"split": s, "input_view": v, "rule_id": rid, "outcomes": dict(c)}
                                            for (s, v, rid), c in sorted(rule_counts.items())])
    summary = {"p4_status": "COMPLETE" if not failed else "FAILED", "started_at_utc": started,
               "completed_at_utc": datetime.now(timezone.utc).isoformat(), "plan_dir": str(plan.resolve()), "p3_dir": str(p3.resolve()),
               "catalog_version": catalog["catalog_version"], "catalog_entries": len(catalog["rules"]),
               "catalog_status_counts": dict(Counter(r["status"] for r in catalog["rules"])),
               "source_lane_active_counts": dict(Counter(r["source_lane"] for r in catalog["rules"] if r["status"] == "ACTIVE")),
               "views": [{"split": s, "input_view": v, "records": sum(c.values()), "groups": len(groups[(s, v)]), "decision_status_counts": dict(c)}
                         for (s, v), c in sorted(counts.items())],
               "browser_dependent_active_rule_ids": sorted(browser_ids), "browser_masked_not_evaluated_checks": masked_checks,
               "frozen_p3_predicate_comparisons": checked_p3, "p3_outcome_drift": 0,
               "source_unavailable_mapping": "P3 UNKNOWN may become explicit P4 NOT_EVALUATED; never MATCH or COUNTEREXAMPLE",
               "runtime_failures": failed, "reserved_features_decoded": 0, "model_calls": 0,
               "detection_metrics": "NOT_EVALUATED_NO_INDEPENDENT_LABELS", "source_data_modified": False,
               "boundary": "Engineering execution/compatibility acceptance. No input-contribution, attack-effectiveness or generalization conclusion."}
    write_json(output / "summary.json", summary)
    if failed:
        raise RuntimeError("P4 acceptance has runtime failures; see output summary")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--p3-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p3_discovery_20260922_r2")
    parser.add_argument("--splits", nargs="+", choices=["discovery", "development"], default=["discovery", "development"])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.plan_dir, args.p3_dir, args.out_dir, tuple(args.splits)), ensure_ascii=False, indent=2))
