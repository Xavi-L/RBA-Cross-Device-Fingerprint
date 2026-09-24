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
    browser_pair_evidence: dict[str, Any] | None = None
    browser_pair_status: str = "not_available_legacy_snapshot"


LATEST_MANIFEST_VERSION = "latest-featureapp-paired244-snapshot-v1"
LATEST_VIEW_KEYS = {
    "record_schema_version",
    "sample_id",
    "dataset_view",
    "dataset_role",
    "label_status",
    "feature_count",
    "features",
    "field_status",
}
LATEST_ALLOWED_FIELD_STATES = frozenset(
    {
        "observed",
        "unsupported_by_os",
        "permission_denied",
        "runtime_error",
        "timeout",
        "not_applicable",
    }
)


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


def _declared_snapshot_path(directory: Path, relative_path: Any, *, field: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"Latest snapshot manifest has no path for {field}")
    path = (directory / relative_path).resolve()
    if path.parent != directory:
        raise ValueError(f"Latest snapshot path must be a direct child of the snapshot: {field}")
    if not path.exists():
        raise FileNotFoundError(f"Missing latest snapshot input: {path}")
    return path


def _value_matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "array":
        return isinstance(value, list)
    return False


def _validate_latest_view_row(
    row: dict[str, Any],
    *,
    view: str,
    expected_fields: list[str],
    feature_types: dict[str, str],
) -> None:
    if set(row) != LATEST_VIEW_KEYS:
        raise ValueError(f"Latest {view} row contains unexpected or missing keys")
    if row.get("dataset_view") != view:
        raise ValueError(f"Latest snapshot row is in the wrong view: {view}")
    if (
        row.get("dataset_role") != "development_qc_only"
        or row.get("label_status") != "unlabeled"
    ):
        raise ValueError(f"Latest {view} row crosses the runtime data/label boundary")
    expected_record_version = (
        "hybridguard-paired244-view-v1"
        if view == "paired_244"
        else "hybridguard-app177-reserve-view-v1"
    )
    if row.get("record_schema_version") != expected_record_version:
        raise ValueError(f"Latest {view} row has an unsupported record version")
    features = row.get("features")
    field_status = row.get("field_status")
    if not isinstance(features, dict) or set(features) != set(expected_fields):
        raise ValueError(f"Latest {view} feature set does not match the frozen catalog")
    if not isinstance(field_status, dict) or set(field_status) != set(expected_fields):
        raise ValueError(f"Latest {view} field status does not match the frozen catalog")
    if row.get("feature_count") != len(expected_fields):
        raise ValueError(f"Latest {view} feature count is invalid")
    for field in expected_fields:
        status = field_status[field]
        value = features[field]
        if status not in LATEST_ALLOWED_FIELD_STATES:
            raise ValueError(f"Latest {view} field status is invalid: {field}")
        if status == "observed" and value is None:
            raise ValueError(f"Latest {view} observed field has no value: {field}")
        if value is not None and not _value_matches_type(value, feature_types[field]):
            raise ValueError(f"Latest {view} field type is invalid: {field}")


def _load_latest_views(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_manifest_version") != LATEST_MANIFEST_VERSION:
        raise ValueError("Unsupported latest paired244 snapshot manifest")
    if (
        manifest.get("dataset_role") != "development_qc_only"
        or manifest.get("label_status") != "unlabeled"
    ):
        raise ValueError("Latest runtime input must remain development-only and unlabeled")
    views = manifest.get("views")
    if not isinstance(views, dict):
        raise ValueError("Latest snapshot manifest has no views object")
    paired_meta = views.get("paired_244")
    app_only_meta = views.get("app_only_177")
    if not isinstance(paired_meta, dict) or not isinstance(app_only_meta, dict):
        raise ValueError("Latest snapshot manifest is missing paired/App-only views")
    paired_path = _declared_snapshot_path(
        directory, paired_meta.get("path"), field="views.paired_244"
    )
    app_only_path = _declared_snapshot_path(
        directory, app_only_meta.get("path"), field="views.app_only_177"
    )
    catalog_path = _declared_snapshot_path(
        directory, manifest.get("feature_catalog_path"), field="feature_catalog_path"
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("feature_catalog_version") != "latest-paired244-feature-catalog-v1":
        raise ValueError("Unsupported latest paired244 feature catalog")
    paired_order = catalog.get("paired_feature_order")
    feature_types = catalog.get("paired_feature_types")
    if (
        not isinstance(paired_order, list)
        or len(paired_order) != 244
        or len(set(paired_order)) != 244
        or not isinstance(feature_types, dict)
        or set(feature_types) != set(paired_order)
    ):
        raise ValueError("Latest paired244 feature catalog is incomplete")
    app_order = [field for field in paired_order if field.startswith("app.")]
    browser_order = [field for field in paired_order if field.startswith("browser.")]
    if len(app_order) != 177 or len(browser_order) != 67:
        raise ValueError("Latest feature catalog must contain App177 and Browser67")

    paired_rows = _index_by_sample_id(paired_path)
    app_only_rows = _index_by_sample_id(app_only_path)
    if set(paired_rows) & set(app_only_rows):
        raise ValueError("A latest sample appears in both paired244 and App-only views")
    if paired_meta.get("count") != len(paired_rows) or app_only_meta.get("count") != len(
        app_only_rows
    ):
        raise ValueError("Latest snapshot manifest view counts do not match the JSONL files")
    for row in paired_rows.values():
        _validate_latest_view_row(
            row,
            view="paired_244",
            expected_fields=paired_order,
            feature_types=feature_types,
        )
    for row in app_only_rows.values():
        _validate_latest_view_row(
            row,
            view="app_only_177",
            expected_fields=app_order,
            feature_types=feature_types,
        )

    return {
        "directory": directory,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "catalog": catalog,
        "catalog_path": catalog_path,
        "paired_rows": paired_rows,
        "app_only_rows": app_only_rows,
        "app_order": app_order,
    }


def validate_latest_snapshot_views(snapshot_dir: Path) -> None:
    """Validate the frozen App177/Browser67 views without constructing runtime evidence."""
    _load_latest_views(snapshot_dir.resolve())


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    current = target
    segments = path.split(".")
    for segment in segments[:-1]:
        child = current.setdefault(segment, {})
        if not isinstance(child, dict):
            raise ValueError(f"Cannot rebuild nested App177 path: {path}")
        current = child
    current[segments[-1]] = value


def _latest_runtime_sample(
    views: dict[str, Any],
    sample_id: str,
    browser_policy_path: Path | None,
    browser_policy: dict[str, Any] | None = None,
) -> RuntimeSample:
    paired_rows = views["paired_rows"]
    app_only_rows = views["app_only_rows"]
    if sample_id in paired_rows:
        row = paired_rows[sample_id]
        dataset_view = "paired_244"
    elif sample_id in app_only_rows:
        row = app_only_rows[sample_id]
        dataset_view = "app_only_177"
    else:
        raise KeyError(f"Sample {sample_id} is not present in the latest snapshot")

    payload: dict[str, Any] = {
        "collector_app": "featureapp",
        "schema_version": views["manifest"].get("selection", {}).get(
            "app_schema_version"
        ),
    }
    app_status: dict[str, str] = {}
    for prefixed_path in views["app_order"]:
        source_path = prefixed_path.removeprefix("app.")
        _set_path(payload, source_path, row["features"][prefixed_path])
        app_status[source_path] = row["field_status"][prefixed_path]
    field_status = {
        "status_schema_version": "field-status-v1",
        "fixed_signal_count": len(app_status),
        "fields": app_status,
    }
    evidence = build_evidence_bundle_v2(
        {"sample_id": sample_id, "payload": payload, "field_status": field_status},
        sample_id=sample_id,
    )
    validate_evidence_bundle_v2(evidence)

    browser_pair_evidence = None
    browser_pair_status = "not_available_no_browser_payload"
    if dataset_view == "paired_244":
        from hybridguard_agent.evidence.browser_pair import (
            DEFAULT_POLICY_PATH,
            build_browser_pair_evidence,
            load_browser_pair_policy,
        )

        policy = browser_policy or load_browser_pair_policy(
            browser_policy_path or DEFAULT_POLICY_PATH
        )
        browser_pair_evidence = build_browser_pair_evidence(
            row,
            views["catalog"],
            views["manifest"],
            policy,
        )
        browser_pair_status = "available_not_assessed"

    return RuntimeSample(
        snapshot={
            "snapshot_kind": "latest-paired244-v1",
            "run_id": views["manifest"].get("run_id"),
            "contract_sha256": _hash_file(views["catalog_path"]),
            "dataset_manifest_sha256": _hash_file(views["manifest_path"]),
            "knowledge_manifest_sha256": None,
            "knowledge_rule_kb_sha256": None,
        },
        sample_id=sample_id,
        normalized_payload=payload,
        field_status=field_status,
        input_quality={
            "qc_status": "passed",
            "qc_reasons": [],
            "dataset_view": dataset_view,
            "dataset_role": row.get("dataset_role"),
            "label_status": row.get("label_status"),
        },
        evidence_bundle=evidence,
        browser_pair_evidence=browser_pair_evidence,
        browser_pair_status=browser_pair_status,
    )


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


def _load_legacy_runtime_sample(directory: Path, sample_id: str) -> RuntimeSample:
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
            "snapshot_kind": "legacy-expanded-v2",
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


def load_latest_runtime_samples(
    snapshot_dir: Path,
    browser_policy_path: Path | None = None,
) -> list[RuntimeSample]:
    """Load every latest App177 sample once for offline runtime-input construction."""
    directory = snapshot_dir.resolve()
    if not (directory / "dataset_manifest.json").exists():
        raise FileNotFoundError(
            f"Missing latest snapshot manifest: {directory / 'dataset_manifest.json'}"
        )
    views = _load_latest_views(directory)
    sample_ids = sorted(set(views["paired_rows"]) | set(views["app_only_rows"]))
    browser_policy = None
    if views["paired_rows"]:
        from hybridguard_agent.evidence.browser_pair import (
            DEFAULT_POLICY_PATH,
            load_browser_pair_policy,
        )

        browser_policy = load_browser_pair_policy(
            browser_policy_path or DEFAULT_POLICY_PATH
        )
    return [
        _latest_runtime_sample(
            views,
            sample_id,
            browser_policy_path,
            browser_policy=browser_policy,
        )
        for sample_id in sample_ids
    ]


def load_runtime_sample(
    snapshot_dir: Path,
    sample_id: str,
    browser_policy_path: Path | None = None,
) -> RuntimeSample:
    directory = snapshot_dir.resolve()
    latest_manifest = directory / "dataset_manifest.json"
    legacy_manifest = directory / "dataset_build_manifest.json"
    if latest_manifest.exists() and legacy_manifest.exists():
        raise ValueError(
            "Snapshot directory ambiguously contains both latest and legacy manifests"
        )
    if latest_manifest.exists():
        return _latest_runtime_sample(
            _load_latest_views(directory), sample_id, browser_policy_path
        )
    if legacy_manifest.exists():
        return _load_legacy_runtime_sample(directory, sample_id)
    raise FileNotFoundError(
        f"Missing dataset_manifest.json or dataset_build_manifest.json in {directory}"
    )
