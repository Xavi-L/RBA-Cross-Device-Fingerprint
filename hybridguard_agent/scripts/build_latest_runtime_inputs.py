#!/usr/bin/env python3
"""Build runtime-safe inputs from one latest paired244 snapshot.

The latest dataset snapshot remains immutable.  This command writes a separate
derived directory containing App EvidenceBundle v2 records, optional redacted
Browser-pair observation sidecars, a runtime-safe sample index, and a compact
manifest.  Browser-pair observations are never passed to deterministic rules
or presented as attack/risk decisions by this builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.evidence.extractor import (  # noqa: E402
    validate_evidence_bundle_v2,
)
from hybridguard_agent.runtime import snapshot_loader  # noqa: E402


RUNTIME_INPUT_MANIFEST_VERSION = "latest-runtime-input-manifest-v1"
RUNTIME_SAMPLE_INDEX_VERSION = "latest-runtime-sample-index-v1"
APP_EVIDENCE_FILENAME = "evidence_bundles_v2.jsonl"
BROWSER_EVIDENCE_FILENAME = "browser_pair_evidence_v1.jsonl"
SAMPLE_INDEX_FILENAME = "runtime_sample_index.jsonl"
MANIFEST_FILENAME = "runtime_input_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        required=True,
        help="Latest paired244 snapshot containing dataset_manifest.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New derived-output directory; the source snapshot is never modified.",
    )
    parser.add_argument(
        "--browser-policy",
        type=Path,
        help="Optional Browser-pair comparison policy passed to the latest snapshot loader.",
    )
    parser.add_argument("--run-id", help="Optional derived runtime-input run identifier.")
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def _nonempty_string(value: Any, *, field: str, sample_id: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        suffix = f" for {sample_id}" if sample_id else ""
        raise ValueError(f"Missing non-empty {field}{suffix}")
    return value


def _dataset_view(sample: Any) -> str:
    direct = getattr(sample, "dataset_view", None)
    snapshot = getattr(sample, "snapshot", None)
    nested = snapshot.get("dataset_view") if isinstance(snapshot, dict) else None
    input_quality = getattr(sample, "input_quality", None)
    quality_view = input_quality.get("dataset_view") if isinstance(input_quality, dict) else None
    value = direct or nested or quality_view
    if value not in {"paired_244", "app_only_177"}:
        raise ValueError(f"Unsupported or missing latest dataset_view for {sample.sample_id}: {value!r}")
    return str(value)


def _snapshot_run_id(sample: Any) -> str | None:
    snapshot = getattr(sample, "snapshot", None)
    value = snapshot.get("run_id") if isinstance(snapshot, dict) else None
    return value if isinstance(value, str) and value else None


def _browser_evidence_hash(sidecar: dict[str, Any]) -> str:
    """Prefer an extractor-provided evidence hash, otherwise hash the redacted record."""
    for key in ("evidence_hash", "browser_pair_evidence_hash"):
        value = sidecar.get(key)
        if value is None:
            continue
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"Browser-pair sidecar has an invalid {key}")
        return value
    return hashlib.sha256(canonical_json(sidecar).encode("utf-8")).hexdigest()


def _browser_evidence_version(sidecar: dict[str, Any], sample_id: str) -> str:
    value = sidecar.get("browser_pair_evidence_version") or sidecar.get("schema_version")
    return _nonempty_string(value, field="browser_pair_evidence_version", sample_id=sample_id)


def _safe_index_row(sample: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    sample_id = _nonempty_string(getattr(sample, "sample_id", None), field="sample_id")
    dataset_view = _dataset_view(sample)
    browser_status = _nonempty_string(
        getattr(sample, "browser_pair_status", None),
        field="browser_pair_status",
        sample_id=sample_id,
    )
    sidecar = getattr(sample, "browser_pair_evidence", None)
    if sidecar is not None and not isinstance(sidecar, dict):
        raise ValueError(f"Browser-pair evidence must be an object for {sample_id}")
    if dataset_view == "paired_244" and sidecar is None:
        raise ValueError(f"paired_244 sample has no Browser-pair evidence: {sample_id}")
    if dataset_view == "app_only_177" and sidecar is not None:
        raise ValueError(f"App-only sample must not fabricate Browser-pair evidence: {sample_id}")
    if dataset_view == "paired_244" and browser_status != "available_not_assessed":
        raise ValueError(f"paired_244 sample has an invalid runtime Browser status: {sample_id}")
    if dataset_view == "app_only_177" and browser_status != "not_available_no_browser_payload":
        raise ValueError(f"App-only sample has an invalid runtime Browser status: {sample_id}")

    browser_version = _browser_evidence_version(sidecar, sample_id) if sidecar else None
    browser_hash = _browser_evidence_hash(sidecar) if sidecar else None
    return {
        "runtime_sample_index_version": RUNTIME_SAMPLE_INDEX_VERSION,
        "sample_id": sample_id,
        "dataset_view": dataset_view,
        "app_evidence_bundle_version": evidence["evidence_bundle_version"],
        "app_evidence_hash": evidence["evidence_hash"],
        "browser_pair_status": browser_status,
        "browser_pair_evidence_version": browser_version,
        "browser_pair_evidence_sha256": browser_hash,
        "browser_pair_rule_use": (
            "observation_only_not_rule_assessed"
            if sidecar is not None
            else "not_available_no_browser_payload"
        ),
    }


def _prepare_records(samples: Iterable[Any]) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    Counter[str],
    Counter[str],
    str | None,
]:
    app_evidence: list[dict[str, Any]] = []
    browser_evidence: list[dict[str, Any]] = []
    sample_index: list[dict[str, Any]] = []
    dataset_views: Counter[str] = Counter()
    browser_statuses: Counter[str] = Counter()
    sample_ids: set[str] = set()
    source_run_ids: set[str] = set()

    for sample in samples:
        sample_id = _nonempty_string(getattr(sample, "sample_id", None), field="sample_id")
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate runtime sample_id: {sample_id}")
        sample_ids.add(sample_id)
        evidence = getattr(sample, "evidence_bundle", None)
        if not isinstance(evidence, dict):
            raise ValueError(f"Latest runtime sample has no App EvidenceBundle v2: {sample_id}")
        validate_evidence_bundle_v2(evidence)
        if evidence.get("sample_id") != sample_id:
            raise ValueError(f"App EvidenceBundle sample_id mismatch for {sample_id}")

        index_row = _safe_index_row(sample, evidence)
        sidecar = getattr(sample, "browser_pair_evidence", None)
        if isinstance(sidecar, dict):
            if sidecar.get("sample_id") != sample_id:
                raise ValueError(f"Browser-pair evidence sample_id mismatch for {sample_id}")
            browser_evidence.append(dict(sidecar))

        app_evidence.append(dict(evidence))
        sample_index.append(index_row)
        dataset_views[index_row["dataset_view"]] += 1
        browser_statuses[index_row["browser_pair_status"]] += 1
        source_run_id = _snapshot_run_id(sample)
        if source_run_id is not None:
            source_run_ids.add(source_run_id)

    if len(source_run_ids) > 1:
        raise ValueError(f"Latest loader returned samples from multiple snapshot runs: {sorted(source_run_ids)}")
    app_evidence.sort(key=lambda row: row["sample_id"])
    browser_evidence.sort(key=lambda row: row["sample_id"])
    sample_index.sort(key=lambda row: row["sample_id"])
    source_run_id = next(iter(source_run_ids), None)
    return (
        app_evidence,
        browser_evidence,
        sample_index,
        dataset_views,
        browser_statuses,
        source_run_id,
    )


def build_runtime_inputs(
    snapshot_dir: Path,
    output_dir: Path,
    *,
    browser_policy_path: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a separate runtime-input artifact from one latest snapshot."""
    snapshot_dir = snapshot_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir == snapshot_dir or output_dir.is_relative_to(snapshot_dir):
        raise ValueError("Runtime-input output must be outside the immutable source snapshot")
    if output_dir.exists():
        raise FileExistsError(f"Runtime-input output already exists: {output_dir}")
    dataset_manifest_path = snapshot_dir / "dataset_manifest.json"
    if not dataset_manifest_path.exists():
        raise FileNotFoundError(f"Missing latest dataset manifest: {dataset_manifest_path}")
    source_manifest_hash = sha256_file(dataset_manifest_path)

    samples = snapshot_loader.load_latest_runtime_samples(
        snapshot_dir,
        browser_policy_path=browser_policy_path,
    )
    (
        app_evidence,
        browser_evidence,
        sample_index,
        dataset_views,
        browser_statuses,
        source_run_id,
    ) = _prepare_records(samples)

    output_dir.mkdir(parents=True)
    app_path = output_dir / APP_EVIDENCE_FILENAME
    browser_path = output_dir / BROWSER_EVIDENCE_FILENAME
    index_path = output_dir / SAMPLE_INDEX_FILENAME
    write_jsonl(app_path, app_evidence)
    write_jsonl(browser_path, browser_evidence)
    write_jsonl(index_path, sample_index)

    active_run_id = run_id or f"latest-runtime-{source_manifest_hash[:20]}"
    manifest = {
        "runtime_input_manifest_version": RUNTIME_INPUT_MANIFEST_VERSION,
        "run_id": active_run_id,
        "source_snapshot": {
            "run_id": source_run_id,
            "dataset_manifest_sha256": source_manifest_hash,
        },
        "counts": {
            "runtime_sample_count": len(sample_index),
            "app_evidence_bundle_v2_count": len(app_evidence),
            "browser_pair_evidence_v1_count": len(browser_evidence),
            "dataset_view_counts": dict(sorted(dataset_views.items())),
            "browser_pair_status_counts": dict(sorted(browser_statuses.items())),
        },
        "outputs": {
            "app_evidence": {
                "path": APP_EVIDENCE_FILENAME,
                "row_count": len(app_evidence),
                "sha256": sha256_file(app_path),
            },
            "browser_pair_evidence": {
                "path": BROWSER_EVIDENCE_FILENAME,
                "row_count": len(browser_evidence),
                "sha256": sha256_file(browser_path),
            },
            "runtime_sample_index": {
                "path": SAMPLE_INDEX_FILENAME,
                "row_count": len(sample_index),
                "sha256": sha256_file(index_path),
            },
        },
        "runtime_boundary": {
            "app_evidence_enters_deterministic_runtime": True,
            "browser_pair_evidence_enters_rule_execution": False,
            "browser_pair_evidence_role": "observation_only_not_rule_assessed",
            "calibrated_risk_score_available": False,
            "external_model_called": False,
        },
        "claim_boundary": (
            "Derived runtime inputs only. Browser-pair equality or difference is an observation, "
            "not an anomaly, attack label, calibrated risk score, metric, or generalization claim."
        ),
    }
    write_json(output_dir / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = build_runtime_inputs(
        args.snapshot_dir,
        args.output_dir,
        browser_policy_path=args.browser_policy,
        run_id=args.run_id,
    )
    counts = manifest["counts"]
    print(
        "Latest runtime inputs complete: "
        f"{counts['app_evidence_bundle_v2_count']} App evidence, "
        f"{counts['browser_pair_evidence_v1_count']} Browser-pair sidecars -> "
        f"{args.output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
