#!/usr/bin/env python3
"""Run the read-only HybridGuard Agent runtime over inline JSON or a frozen snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2  # noqa: E402
from hybridguard_agent.runtime.service import analyze_evidence_bundle, analyze_payload  # noqa: E402
from hybridguard_agent.runtime.snapshot_loader import load_runtime_sample  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="One JSON object or JSONL of inline payloads/archive envelopes.")
    source.add_argument("--snapshot-dir", type=Path, help="Frozen artifact directory containing runtime sidecars.")
    parser.add_argument("--sample-id", help="Required with --snapshot-dir; optional override for a one-object --input.")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL; never overwrites source data.")
    return parser.parse_args()


def read_json_or_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    if value is not None:
        if not isinstance(value, dict):
            raise ValueError("Input JSON must be an object")
        return [value]
    rows = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Input JSONL line {line_number} is not an object")
        rows.append(value)
    return rows


def main() -> None:
    args = parse_args()
    if args.snapshot_dir is not None:
        if not args.sample_id:
            raise ValueError("--sample-id is required with --snapshot-dir")
        runtime_sample = load_runtime_sample(args.snapshot_dir, args.sample_id)
        evidence = runtime_sample.evidence_bundle or build_evidence_bundle_v2(
            {
                "sample_id": runtime_sample.sample_id,
                "payload": runtime_sample.normalized_payload,
                "field_status": runtime_sample.field_status,
            }
        )
        result = analyze_evidence_bundle(
            evidence,
            {
                "payload_sha256": None,
                "session_id_hash": None,
                "snapshot_run_id": runtime_sample.snapshot.get("run_id"),
            },
        )
        if runtime_sample.snapshot.get("snapshot_kind") == "latest-paired244-v1":
            pair_evidence = runtime_sample.browser_pair_evidence
            result["browser_pair_evidence"] = {
                "status": runtime_sample.browser_pair_status,
                "browser_pair_evidence_version": (
                    pair_evidence.get("browser_pair_evidence_version")
                    if pair_evidence
                    else None
                ),
                "evidence_hash": (
                    pair_evidence.get("evidence_hash") if pair_evidence else None
                ),
                "summary": pair_evidence.get("summary") if pair_evidence else None,
                "used_by_rule_execution": False,
                "claim_boundary": (
                    pair_evidence.get("claim_boundary")
                    if pair_evidence
                    else "No completed Browser67 pair is available for this App177 sample."
                ),
            }
            result["warnings"].append(
                "Browser-pair evidence is audit-only and was not used by rules, retrieval, or the decision."
            )
        results = [result]
    else:
        results = [
            analyze_payload(row, sample_id=args.sample_id)
            for row in read_json_or_jsonl(args.input)
        ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Agent runtime decisions written: {args.output} ({len(results)} rows)")


if __name__ == "__main__":
    main()
