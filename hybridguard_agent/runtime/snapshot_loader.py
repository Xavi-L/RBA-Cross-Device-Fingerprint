"""Load one frozen snapshot sample without exposing its labels or provenance to runtime reasoning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from hybridguard_agent.adapters.official_kb_adapter import DEFAULT_OFFICIAL_CARDS, sha256_file as official_sha256
from hybridguard_agent.adapters.rule_kb_adapter import DEFAULT_RULE_KB, sha256_file as rule_sha256
from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2, validate_evidence_bundle_v2


@dataclass(frozen=True)
class RuntimeSample:
    snapshot: dict[str, Any]
    sample_id: str
    normalized_payload: dict[str, Any]
    field_status: dict[str, Any]
    input_quality: dict[str, Any]
    evidence_bundle: dict[str, Any] | None


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if text:
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise ValueError(f"Expected object in {path}:{line_number}")
                yield value


def _index_by_sample_id(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"Missing sample_id in {path}")
        if sample_id in result:
            raise ValueError(f"Duplicate sample_id in {path}: {sample_id}")
        result[sample_id] = row
    return result


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_field_status(snapshot_dir: Path) -> dict[str, dict[str, Any]]:
    unified = snapshot_dir / "field_status.jsonl"
    if unified.exists():
        return _index_by_sample_id(unified)
    legacy = snapshot_dir / "historical_field_status_backfill.jsonl"
    if not legacy.exists():
        raise FileNotFoundError(
            f"Missing field-status sidecar in {snapshot_dir}; build a current snapshot with field_status.jsonl."
        )
    return {
        row["sample_id"]: {
            "sample_id": row["sample_id"],
            "field_status": row.get("inferred_collection_status", {}),
        }
        for row in _read_jsonl(legacy)
    }


def _verify_knowledge_manifest(snapshot_dir: Path) -> dict[str, Any]:
    path = snapshot_dir / "knowledge_input_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing frozen knowledge manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected_rule = manifest.get("rule_knowledge_base", {}).get("sha256")
    expected_cards = manifest.get("official_feature_cards", {}).get("sha256")
    if expected_rule != rule_sha256(DEFAULT_RULE_KB) or expected_cards != official_sha256(DEFAULT_OFFICIAL_CARDS):
        raise ValueError("Frozen snapshot knowledge inputs no longer match the checked-out knowledge files")
    return manifest


def load_runtime_sample(snapshot_dir: Path, sample_id: str) -> RuntimeSample:
    directory = snapshot_dir.resolve()
    build_manifest_path = directory / "dataset_build_manifest.json"
    normalized_path = directory / "normalized_expanded_v2.jsonl"
    manifest_path = directory / "sample_manifest.jsonl"
    for path in (build_manifest_path, normalized_path, manifest_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing snapshot input: {path}")
    build_manifest = json.loads(build_manifest_path.read_text(encoding="utf-8"))
    normalized = _index_by_sample_id(normalized_path)
    manifests = _index_by_sample_id(manifest_path)
    status_rows = _load_field_status(directory)
    if sample_id not in normalized or sample_id not in manifests or sample_id not in status_rows:
        raise KeyError(f"Sample {sample_id} is not present in every required runtime snapshot view")
    manifest = manifests[sample_id]
    quality = manifest.get("quality")
    if not isinstance(quality, dict):
        raise ValueError(f"Snapshot manifest has no quality object for {sample_id}")
    evidence_path = directory / "evidence_bundles_v2.jsonl"
    evidence = _index_by_sample_id(evidence_path).get(sample_id) if evidence_path.exists() else None
    knowledge_manifest = _verify_knowledge_manifest(directory)
    normalized_payload = normalized[sample_id].get("payload")
    if not isinstance(normalized_payload, dict):
        raise ValueError(f"Snapshot normalized payload is not an object for {sample_id}")
    field_status = status_rows[sample_id].get("field_status")
    if not isinstance(field_status, dict):
        raise ValueError(f"Snapshot field status is not an object for {sample_id}")
    rebuilt_evidence = build_evidence_bundle_v2(
        {
            "sample_id": sample_id,
            "payload": normalized_payload,
            "field_status": field_status,
        },
        sample_id=sample_id,
    )
    if evidence is not None:
        validate_evidence_bundle_v2(evidence)
        if evidence.get("sample_id") != sample_id or evidence.get("evidence_hash") != rebuilt_evidence["evidence_hash"]:
            raise ValueError(
                "Frozen EvidenceBundle v2 does not match the normalized payload and field-status sidecar"
            )
    else:
        evidence = rebuilt_evidence
    return RuntimeSample(
        snapshot={
            "run_id": build_manifest.get("run_id"),
            "contract_sha256": build_manifest.get("schema_audit", {}).get("contract_sha256"),
            "knowledge_manifest_sha256": _hash_file(directory / "knowledge_input_manifest.json"),
            "knowledge_rule_kb_sha256": knowledge_manifest.get("rule_knowledge_base", {}).get("sha256"),
        },
        sample_id=sample_id,
        normalized_payload=dict(normalized_payload),
        field_status=dict(field_status),
        input_quality={
            "qc_status": quality.get("qc_status"),
            "qc_reasons": list(quality.get("qc_reasons", [])),
        },
        evidence_bundle=evidence,
    )
