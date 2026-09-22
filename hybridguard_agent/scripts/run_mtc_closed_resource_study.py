#!/usr/bin/env python3
"""One bounded final discovery/development pass, then close every outstanding item."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.evidence.paired244 import build_paired_evidence
from hybridguard_agent.research.mtc_closed_resource import candidates, describe, evaluate, summarize_descriptions, numeric_summary
from hybridguard_agent.research.mtc_p3_data import load_split_records
from hybridguard_agent.scripts.run_mtc_p3_discovery import aggregate, split_decision

CONFIG = ROOT / "hybridguard_agent/config"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_rows(path, rows):
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def evaluate_split(plan, output, split, declared, protocol):
    rows = load_split_records(plan, split)
    bundles = [build_paired_evidence(row) for row in rows]
    descriptions = [describe(bundle) for bundle in bundles]
    write_json(output / f"{split}_descriptive_summary.json", summarize_descriptions(descriptions))
    write_rows(output / f"{split}_descriptive_records.jsonl", [
        {"sample_id": row["sample_id"], "group_id": row["_p2"]["group_id"], **description}
        for row, description in zip(rows, descriptions)])
    summaries, all_results, exceptions = {}, [], []
    for candidate in declared:
        results = [evaluate(candidate, bundle["projection"]) for bundle in bundles]
        summary = aggregate(candidate, rows, results)
        summary["screen_decision"] = split_decision(candidate, summary, split, protocol)
        if candidate["predicate"] == "screen_two_dimensions":
            summary["max_css_residual_distribution"] = numeric_summary(
                [r["max_absolute_css_pixel_residual"] for r in results if "max_absolute_css_pixel_residual" in r])
        summaries[candidate["candidate_id"]] = summary
        for row, result in zip(rows, results):
            record = {"candidate_id": candidate["candidate_id"], "sample_id": row["sample_id"],
                      "group_id": row["_p2"]["group_id"], "split": split, **result}
            all_results.append(record)
            if result["outcome"] == "COUNTEREXAMPLE":
                exceptions.append({**record, "profile": row["_p2"]["profile"], "source_line": row["_p2"]["source_line"],
                                   "values": {p: row["features"][p] for p in candidate["dependencies"]},
                                   "attack_inferred": False})
    write_json(output / f"{split}_summary.json", summaries)
    write_rows(output / f"{split}_results.jsonl", all_results)
    write_rows(output / f"{split}_counterexamples.jsonl", exceptions)
    return summaries


def execute(plan, output):
    if output.exists():
        raise ValueError("Output exists; never overwrite a final study")
    protocol = json.loads((CONFIG / "mtc_closed_resource_protocol.v1.json").read_text())
    declared = json.loads((CONFIG / "mtc_closed_resource_candidates.v1.json").read_text())["candidates"]
    if declared != candidates() or protocol["permitted_feature_splits"] != ["discovery", "development"]:
        raise ValueError("Protocol/template drift before execution")
    p2 = json.loads((plan / "protocol.json").read_text())
    if p2["candidate_support_floor"] != protocol["candidate_support_floor"]:
        raise ValueError("P2 support floors changed")
    output.mkdir(parents=True)
    for name in ("mtc_closed_resource_protocol.v1.json", "mtc_closed_resource_candidates.v1.json",
                 "mtc_closed_resource_sources.v1.json", "paired244_legacy_review.v1.json"):
        shutil.copyfile(CONFIG / name, output / name)
    for rel in ("scripts/run_mtc_closed_resource_study.py", "research/mtc_closed_resource.py", "research/mtc_p3_data.py",
                "scripts/run_mtc_p3_discovery.py", "evidence/paired244.py"):
        target = output / "implementation" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "hybridguard_agent" / rel, target)
    try:
        discovery = evaluate_split(plan, output, "discovery", declared, protocol)
        selected = [cid for cid, summary in discovery.items() if summary["screen_decision"] == "PASS_RESEARCH_SCREEN"]
        write_json(output / "discovery_selection_FREEZE.json", {
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_ids": selected,
            "parameters_frozen": True, "development_opened_by_this_run": False,
            "prior_development_exposure": True, "reserved_features_decoded": 0})
        development = evaluate_split(plan, output, "development", declared, protocol)
        admitted = [c for c in declared if c["candidate_id"] in selected
                    and development[c["candidate_id"]]["screen_decision"] == "PASS_RESEARCH_SCREEN"]
        result = {"status": "COMPLETE", "protocol_version": protocol["protocol_version"],
                  "plan_dir": str(plan.resolve()), "candidate_count": len(declared),
                  "discovery": discovery, "development": development,
                  "admitted_rule_ids": [c["rule_id"] for c in admitted],
                  "reserved_features_decoded": 0, "model_calls": 0, "threshold_fitting": False,
                  "new_collection": False, "prior_development_exposure": True,
                  "detection_metrics": "NOT_EVALUATED", "completed_at_utc": datetime.now(timezone.utc).isoformat()}
        write_json(output / "admitted_candidates.json", {"candidates": admitted})
        write_json(output / "summary.json", result)
        return result
    except Exception as exc:
        write_json(output / "summary.json", {"status": "FAILED", "error": str(exc), "detection_metrics": "NOT_EVALUATED"})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = execute(args.plan_dir, args.out_dir)
    print(json.dumps({"status": summary["status"], "admitted": summary["admitted_rule_ids"],
                     "screens": {s: {rid: {k: v[k] for k in ("group_outcomes", "group_agreement", "screen_decision")}
                                      for rid, v in summary[s].items()} for s in ("discovery", "development")}},
                     ensure_ascii=False, indent=2))
