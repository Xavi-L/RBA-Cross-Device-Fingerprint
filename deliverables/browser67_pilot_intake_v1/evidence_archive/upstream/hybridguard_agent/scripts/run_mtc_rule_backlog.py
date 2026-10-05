#!/usr/bin/env python3
"""Accept the reviewed backlog first batch on admitted discovery/development rows."""
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
from hybridguard_agent.adapters.paired244_catalog import runtime_cards
from hybridguard_agent.research.mtc_p3_data import load_split_records
from hybridguard_agent.rules.paired244 import V2_CATALOG as DEFAULT_CATALOG, LEGACY_CATALOG, execute_paired_rules, load_catalog
from hybridguard_agent.runtime.paired244 import analyze_paired244_record

CONFIG = DEFAULT_CATALOG.parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(plan, output, splits=("discovery", "development")):
    if not splits or len(splits) != len(set(splits)) or not set(splits) <= {"discovery", "development"}:
        raise ValueError("Only discovery/development permitted; reserved stays locked")
    if output.exists():
        raise ValueError("Do not overwrite a versioned backlog run")
    catalog, baseline = load_catalog(DEFAULT_CATALOG), load_catalog(LEGACY_CATALOG)
    review = json.loads((CONFIG / "paired244_legacy_review.v1.json").read_text())
    changed = {r["rule_id"] for r in review["entries"]}
    unchanged = {r["rule_id"] for r in baseline["rules"] if r["status"] == "ACTIVE"}
    browser = {r["rule_id"] for r in catalog["rules"] if r["status"] == "ACTIVE"
               and any(p.startswith("browser.") for p in r["dependencies"])}
    if any(next(n for n in catalog["rules"] if n["rule_id"] == old["rule_id"]) != old
           for old in baseline["rules"] if old["rule_id"] in unchanged):
        raise ValueError("Original executable contracts changed")
    output.mkdir(parents=True)
    for name in (DEFAULT_CATALOG.name, LEGACY_CATALOG.name, "paired244_browser_relations.v2.json",
                 "paired244_browser_relations.v1.json", "mtc_paired244_sources.v2.json",
                 "paired244_legacy_review.v1.json", "paired244_review_sources.v1.json",
                 "mtc_p3_semantic_sources.v1.json"):
        shutil.copyfile(CONFIG / name, output / name)
    for relative in ("scripts/run_mtc_rule_backlog.py", "scripts/build_paired244_catalog_v2.py",
                     "rules/legacy_backlog.py", "rules/paired244.py", "evidence/paired244.py",
                     "adapters/paired244_catalog.py", "retrieval/paired244.py", "verification/paired244.py",
                     "runtime/paired244.py"):
        target = output / "implementation" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "hybridguard_agent" / relative, target)
    write_json(output / "runtime_cards.json", runtime_cards(catalog))
    started = datetime.now(timezone.utc).isoformat()
    views, outcomes, reasons, coverage = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    groups = defaultdict(set)
    comparisons = masked = drift = 0
    failures = []
    with (output / "results.jsonl").open("w", encoding="utf-8") as summaries, \
            (output / "decision_traces.jsonl").open("w", encoding="utf-8") as traces:
        for split in splits:
            rows = load_split_records(plan, split)
            for index, row in enumerate(rows):
                for view in ("Full244", "App177"):
                    identity = {"input_sample_id": row["sample_id"], "split": split, "input_view": view}
                    try:
                        result = analyze_paired244_record(row, input_view=view, catalog=catalog)
                        current = {r["rule_id"]: r for r in result["rule_execution"]["rule_results"]}
                        previous = {r["rule_id"]: r for r in execute_paired_rules(result["evidence_bundle"], baseline)["rule_results"]}
                        comparisons += len(unchanged)
                        differences = sum(current[rid] != previous[rid] for rid in unchanged)
                        drift += differences
                        if differences:
                            raise AssertionError("An original executable check changed")
                        if view == "App177" and any(current[rid]["outcome"] != "NOT_EVALUATED"
                                                  or current[rid]["used_fields"] for rid in browser):
                            raise AssertionError("Browser masking failed")
                        # Group/identity metadata only joins the verified output.
                        meta = {**identity, "group_id": row["_p2"]["group_id"],
                                "source_line": row["_p2"]["source_line"], "control_plane_joined_after_execution": True}
                    except Exception as exc:
                        failure = {**identity, "status": "FAILED", "error": str(exc)}
                        failures.append(failure)
                        summaries.write(json.dumps(failure, ensure_ascii=False) + "\n")
                        continue
                    masked += len(browser) if view == "App177" else 0
                    summaries.write(json.dumps({**meta, "status": "completed", "decision_id": result["decision_id"],
                                                "decision": result["decision"], "verification": result["decision_trace"]["verification"]},
                                               ensure_ascii=False, separators=(",", ":")) + "\n")
                    traces.write(json.dumps({**meta, "trace": result["decision_trace"]}, ensure_ascii=False, separators=(",", ":")) + "\n")
                    views[(split, view)][result["decision"]["decision_status"]] += 1
                    groups[(split, view)].add(meta["group_id"])
                    for rid, item in current.items():
                        outcomes[(split, view, rid)][item["outcome"]] += 1
                        if rid in changed:
                            reasons[(split, view, rid)][item["reason"]] += 1
                    if view == "Full244":
                        for entry in review["entries"]:
                            fields = result["evidence_bundle"]["fields"]
                            required = entry["required_fields"]
                            available = bool(required) and all(p in fields and fields[p]["available"] for p in required)
                            coverage[(split, entry["rule_id"])]["all_declared_fields_available" if available
                                                                    else "missing_unavailable_or_uncollected"] += 1
                    if index == 0:
                        write_json(output / f"example_{split}_{view}.json", result)
    write_json(output / "rule_summary.json", [{"split": s, "input_view": v, "rule_id": rid, "outcomes": dict(c)}
                                            for (s, v, rid), c in sorted(outcomes.items())])
    write_json(output / "review_reason_summary.json", [{"split": s, "input_view": v, "rule_id": rid, "reasons": dict(c)}
                                                       for (s, v, rid), c in sorted(reasons.items())])
    write_json(output / "review_field_coverage.json", {"boundary": "Declared legacy fields only; availability does not establish semantic comparability or validity.",
               "rows": [{"split": s, "rule_id": rid, "counts": dict(c)} for (s, rid), c in sorted(coverage.items())]})
    summary = {"status": "COMPLETE" if not failures else "FAILED", "scope": "37-item dispositions and first six policy/context implementations",
               "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
               "plan_dir": str(plan.resolve()), "catalog_version": catalog["catalog_version"],
               "review_status_counts": dict(Counter(r["status"] for r in review["entries"])),
               "catalog_status_counts": dict(Counter(r["status"] for r in catalog["rules"])),
               "new_executable_rule_ids": sorted(r["rule_id"] for r in review["entries"] if r["status"] == "ACTIVE"),
               "views": [{"split": s, "input_view": v, "records": sum(c.values()), "groups": len(groups[(s, v)]),
                          "decision_status_counts": dict(c)} for (s, v), c in sorted(views.items())],
               "original_48_check_comparisons": comparisons, "original_check_drift": drift,
               "browser_masked_not_evaluated_checks": masked, "runtime_failures": failures,
               "all_37_implemented": False,
               "remaining_research": sum(r["status"] == "NEEDS_RESEARCH" for r in review["entries"]),
               "remaining_data": sum(r["status"] == "NEEDS_DATA" for r in review["entries"]),
               "reserved_features_decoded": 0, "model_calls": 0, "threshold_fitting": False,
               "detection_metrics": "NOT_EVALUATED", "source_data_modified": False}
    write_json(output / "summary.json", summary)
    if failures:
        raise RuntimeError("Backlog runtime failures persisted; see summary")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.plan_dir, args.out_dir), ensure_ascii=False, indent=2))
