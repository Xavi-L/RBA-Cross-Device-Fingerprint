#!/usr/bin/env python3
"""Build redacted EvidenceBundle v2 records from one frozen dataset snapshot.

Only the normalized three-layer payload and its field-availability sidecar are
read.  Labels, source/provider details, collection manifests, and attack
metadata are deliberately outside this build path.
"""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        required=True,
        help="Frozen snapshot directory containing normalized_expanded_v2.jsonl.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSONL path; defaults to evidence_bundles_v2.jsonl in the snapshot directory.",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    """Read object-only JSONL with precise input diagnostics."""
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object in {path}:{line_number}")
            yield value


def index_by_sample_id(path: Path) -> dict[str, dict[str, Any]]:
    """Return a one-to-one sample index, rejecting absent or duplicate keys."""
    index: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"Missing non-empty sample_id in {path}")
        if sample_id in index:
            raise ValueError(f"Duplicate sample_id in {path}: {sample_id}")
        index[sample_id] = row
    return index


def load_field_status_index(snapshot_dir: Path) -> dict[str, dict[str, Any]]:
    """Load the unified sidecar, or adapt the legacy inferred-only sidecar.

    The returned rows expose only ``sample_id`` and ``field_status``.  Legacy
    rows may contain source/session hashes, but those values are intentionally
    discarded before evidence extraction.
    """
    unified_path = snapshot_dir / "field_status.jsonl"
    if unified_path.exists():
        status_rows = index_by_sample_id(unified_path)
        output: dict[str, dict[str, Any]] = {}
        for sample_id, row in status_rows.items():
            field_status = row.get("field_status")
            if not isinstance(field_status, dict):
                raise ValueError(f"Missing object field_status for {sample_id} in {unified_path}")
            output[sample_id] = {"sample_id": sample_id, "field_status": field_status}
        return output

    legacy_path = snapshot_dir / "historical_field_status_backfill.jsonl"
    if not legacy_path.exists():
        raise FileNotFoundError(
            "Missing field-status sidecar: expected field_status.jsonl or "
            f"historical_field_status_backfill.jsonl in {snapshot_dir}"
        )
    legacy_rows = index_by_sample_id(legacy_path)
    output = {}
    for sample_id, row in legacy_rows.items():
        inferred = row.get("inferred_collection_status")
        if not isinstance(inferred, dict):
            raise ValueError(
                f"Missing object inferred_collection_status for {sample_id} in {legacy_path}"
            )
        output[sample_id] = {"sample_id": sample_id, "field_status": inferred}
    return output


def validate_one_to_one_sample_ids(
    normalized: dict[str, dict[str, Any]], field_status: dict[str, dict[str, Any]]
) -> None:
    """Ensure every normalized sample has exactly one availability record."""
    normalized_ids = set(normalized)
    field_status_ids = set(field_status)
    missing_status = sorted(normalized_ids - field_status_ids)
    orphan_status = sorted(field_status_ids - normalized_ids)
    if missing_status or orphan_status:
        details = []
        if missing_status:
            details.append(f"missing field status for {missing_status}")
        if orphan_status:
            details.append(f"field status has no normalized payload for {orphan_status}")
        raise ValueError("Snapshot sample IDs are not one-to-one: " + "; ".join(details))


def build_bundles(snapshot_dir: Path) -> list[dict[str, Any]]:
    """Build deterministic v2 bundles in stable sample-id order without persistence."""
    directory = snapshot_dir.resolve()
    normalized_path = directory / "normalized_expanded_v2.jsonl"
    if not normalized_path.exists():
        raise FileNotFoundError(f"Missing normalized snapshot input: {normalized_path}")
    normalized_rows = index_by_sample_id(normalized_path)
    field_status_rows = load_field_status_index(directory)
    validate_one_to_one_sample_ids(normalized_rows, field_status_rows)

    bundles: list[dict[str, Any]] = []
    for sample_id in sorted(normalized_rows):
        payload = normalized_rows[sample_id].get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"Missing object payload for {sample_id} in {normalized_path}")
        # Pass only the three runtime-safe pieces into the extractor.  In
        # particular, no manifest, label, source, provider, or session fields
        # are available to it from this builder.
        bundle = build_evidence_bundle_v2(
            {
                "sample_id": sample_id,
                "payload": payload,
                "field_status": field_status_rows[sample_id]["field_status"],
            },
            sample_id=sample_id,
        )
        if bundle["sample_id"] != sample_id:
            raise ValueError(f"Extractor changed snapshot sample_id for {sample_id}")
        bundles.append(bundle)
    return bundles


def write_bundles(output_path: Path, bundles: Iterable[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for bundle in bundles:
            handle.write(json.dumps(bundle, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    args = parse_args()
    snapshot_dir = args.snapshot_dir.resolve()
    output_path = (args.output or snapshot_dir / "evidence_bundles_v2.jsonl").resolve()
    bundles = build_bundles(snapshot_dir)
    write_bundles(output_path, bundles)
    print(f"EvidenceBundle v2 records written: {output_path} ({len(bundles)} rows)")


if __name__ == "__main__":
    main()
