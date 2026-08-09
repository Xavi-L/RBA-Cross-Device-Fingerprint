#!/usr/bin/env python3
"""Build the latest FeatureApp paired244/App-only/QC snapshot.

The collector payloads remain independent App177 and Browser67 records.  This
builder joins only provenance-complete browser pairs into a derived 244-feature
view.  A valid App177 record is retained when Browser67 is not complete; no
missing browser value is imputed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
AGENT_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = AGENT_ROOT.parent
DEFAULT_CONFIG = AGENT_ROOT / "config" / "latest_paired244_sources.json"
DEFAULT_ARTIFACT_ROOT = AGENT_ROOT / "artifacts" / "latest_paired244"

APP_ROOTS = ("android_native_data", "webview_data", "web_data")
ALLOWED_FIELD_STATES = frozenset(
    {
        "observed",
        "unsupported_by_os",
        "permission_denied",
        "runtime_error",
        "timeout",
        "not_applicable",
    }
)


@dataclass(frozen=True)
class SourceRow:
    line_number: int
    value: dict[str, Any]


@dataclass(frozen=True)
class AppObservation:
    analysis: dict[str, Any]
    raw_envelope: dict[str, Any]
    payload: dict[str, Any]
    receipt: dict[str, Any]
    batch: dict[str, Any]
    features: dict[str, Any]
    field_status: dict[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", help="Unique snapshot identifier.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Exact output directory. Defaults to artifacts/latest_paired244/<run-id>.",
    )
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_signature(path: Path) -> dict[str, Any]:
    """Return a stable input signature and reject a file changed while hashing."""
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    before_identity = (before.st_size, before.st_mtime_ns)
    after_identity = (after.st_size, after.st_mtime_ns)
    if before_identity != after_identity:
        raise RuntimeError(f"Snapshot input changed while being read: {path}")
    return {
        "size_bytes": after.st_size,
        "mtime_ns": after.st_mtime_ns,
        "sha256": digest,
    }


def read_jsonl(path: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object in {path}:{line_number}")
            rows.append(SourceRow(line_number=line_number, value=value))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def flatten_leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    flattened: dict[str, Any] = {}
    for key in sorted(value):
        child = f"{prefix}.{key}" if prefix else key
        flattened.update(flatten_leaves(value[key], child))
    return flattened


def feature_map(payload: dict[str, Any], roots: tuple[str, ...]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for root in roots:
        value = payload.get(root)
        if not isinstance(value, dict):
            continue
        flattened.update(flatten_leaves(value, root))
    return flattened


def index_many(rows: Iterable[SourceRow], key: str) -> dict[str, list[SourceRow]]:
    result: dict[str, list[SourceRow]] = defaultdict(list)
    for row in rows:
        value = row.value.get(key)
        if isinstance(value, str) and value:
            result[value].append(row)
    return result


def release_selection(
    analysis_rows: list[SourceRow],
    raw_rows: list[SourceRow],
    release: dict[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    """Select latest FeatureApp sessions, preferring canonical raw payload metadata."""
    raw_payloads = [
        row.value["canonical_received_payload"]
        for row in raw_rows
        if isinstance(row.value.get("canonical_received_payload"), dict)
    ]
    candidates = raw_payloads or [row.value for row in analysis_rows]
    if not candidates:
        return True, "release_metadata_missing", {}

    for value in candidates:
        manifest = value.get("collection_manifest")
        if (
            value.get("collector_app") == release["app_collector"]
            and value.get("schema_version") == release["app_schema_version"]
            and isinstance(manifest, dict)
            and manifest.get("collector_version_code") == release["featureapp_version_code"]
            and manifest.get("collector_version_name") == release["featureapp_version_name"]
        ):
            return True, "selected_latest_release", value

    observed = candidates[0]
    manifest = observed.get("collection_manifest")
    if observed.get("collector_app") != release["app_collector"]:
        return False, "collector_not_featureapp", observed
    if observed.get("schema_version") != release["app_schema_version"]:
        return False, "legacy_schema_version", observed
    if isinstance(manifest, dict) and (
        manifest.get("collector_version_code") is not None
        or manifest.get("collector_version_name") is not None
    ):
        return False, "legacy_featureapp_release", observed
    # Missing release metadata cannot prove that a session is legacy. Keep it
    # visible and let the strict App QC gate quarantine it if necessary.
    return True, "release_metadata_missing", observed


def load_catalog(
    path: Path, expected_app_count: int, expected_browser_count: int
) -> tuple[list[str], list[str], dict[str, str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    signal_rows = [
        row for row in rows if str(row.get("layer") or "").strip() in APP_ROOTS
    ]
    app_fields = [str(row.get("field") or "").strip() for row in signal_rows]
    if any(not field for field in app_fields) or len(set(app_fields)) != len(app_fields):
        raise ValueError("Feature catalog contains a blank or duplicate field")
    browser_fields = [field for field in app_fields if field.startswith("web_data.")]
    if len(app_fields) != expected_app_count or len(browser_fields) != expected_browser_count:
        raise ValueError(
            f"Feature catalog expected {expected_app_count}/{expected_browser_count} App/Browser fields, "
            f"got {len(app_fields)}/{len(browser_fields)}"
        )
    app_types = {
        str(row["field"]).strip(): str(row.get("type") or "").strip()
        for row in signal_rows
    }
    browser_types = {field: app_types[field] for field in browser_fields}
    if any(value not in {"boolean", "number", "string", "array"} for value in app_types.values()):
        raise ValueError("Feature catalog contains an unsupported field type")
    return app_fields, browser_fields, app_types, browser_types


def value_matches_catalog_type(value: Any, expected_type: str) -> bool:
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "array":
        return isinstance(value, list)
    return False


def feature_type_errors(
    features: dict[str, Any],
    statuses: dict[str, str],
    expected_types: dict[str, str],
    code: str,
) -> list[str]:
    for field, expected_type in expected_types.items():
        value = features.get(field)
        status = statuses.get(field)
        if status == "observed" and value is None:
            return [f"Q_{code}_OBSERVED_VALUE_MISSING"]
        if value is not None and not value_matches_catalog_type(value, expected_type):
            return [f"Q_{code}_FEATURE_TYPE_INVALID"]
    return []


def validate_collection_status(
    payload: dict[str, Any],
    expected_fields: list[str],
    expected_status_schema: str,
    expected_count: int,
    code_prefix: str,
) -> tuple[list[str], dict[str, str]]:
    reasons: list[str] = []
    status = payload.get("collection_status")
    if not isinstance(status, dict):
        return [f"Q_{code_prefix}_STATUS_MISSING"], {}
    fields = status.get("fields")
    counts = status.get("counts")
    if status.get("status_schema_version") != expected_status_schema:
        reasons.append(f"Q_{code_prefix}_STATUS_SCHEMA_INVALID")
    if status.get("fixed_signal_count") != expected_count:
        reasons.append(f"Q_{code_prefix}_STATUS_COUNT_INVALID")
    if not isinstance(fields, dict) or set(fields) != set(expected_fields):
        reasons.append(f"Q_{code_prefix}_STATUS_FIELDSET_INVALID")
        safe_fields: dict[str, str] = {}
    else:
        safe_fields = {str(key): str(value) for key, value in fields.items()}
        if any(value not in ALLOWED_FIELD_STATES for value in safe_fields.values()):
            reasons.append(f"Q_{code_prefix}_STATUS_VALUE_INVALID")
    if not isinstance(counts, dict) or any(not isinstance(counts.get(state), int) for state in ALLOWED_FIELD_STATES):
        reasons.append(f"Q_{code_prefix}_STATUS_SUMMARY_INVALID")
    elif safe_fields:
        expected_counts = Counter(safe_fields.values())
        if (
            sum(counts[state] for state in ALLOWED_FIELD_STATES) != expected_count
            or any(counts[state] != expected_counts[state] for state in ALLOWED_FIELD_STATES)
        ):
            reasons.append(f"Q_{code_prefix}_STATUS_SUMMARY_INVALID")
    alias = payload.get("field_statuses")
    if isinstance(alias, dict) and safe_fields and alias != fields:
        reasons.append(f"Q_{code_prefix}_STATUS_ALIAS_MISMATCH")
    return sorted(set(reasons)), safe_fields


def validate_app_payload(
    payload: dict[str, Any],
    release: dict[str, Any],
    app_fields: list[str],
    app_types: dict[str, str],
) -> tuple[list[str], dict[str, Any], dict[str, str]]:
    reasons: list[str] = []
    manifest = payload.get("collection_manifest")
    if payload.get("collector_app") != release["app_collector"]:
        reasons.append("Q_APP_COLLECTOR_INVALID")
    if payload.get("schema_version") != release["app_schema_version"]:
        reasons.append("Q_APP_SCHEMA_INVALID")
    if not isinstance(manifest, dict):
        reasons.append("Q_APP_MANIFEST_MISSING")
    else:
        if manifest.get("collector_version_code") != release["featureapp_version_code"]:
            reasons.append("Q_APP_RELEASE_CODE_INVALID")
        if manifest.get("collector_version_name") != release["featureapp_version_name"]:
            reasons.append("Q_APP_RELEASE_NAME_INVALID")
        if manifest.get("schema_version") != release["app_schema_version"]:
            reasons.append("Q_APP_MANIFEST_SCHEMA_INVALID")
    features = feature_map(payload, APP_ROOTS)
    if set(features) != set(app_fields):
        reasons.append("Q_APP_FEATURESET_INVALID")
    status_reasons, statuses = validate_collection_status(
        payload,
        app_fields,
        release["app_status_schema_version"],
        release["app_signal_count"],
        "APP",
    )
    reasons.extend(status_reasons)
    if set(features) == set(app_fields) and statuses:
        reasons.extend(feature_type_errors(features, statuses, app_types, "APP"))
    if not isinstance(payload.get("collection_diagnostics"), dict):
        reasons.append("Q_APP_DIAGNOSTICS_MISSING")
    return sorted(set(reasons)), features, statuses


def validate_browser_payload(
    payload: dict[str, Any],
    release: dict[str, Any],
    browser_fields: list[str],
    browser_types: dict[str, str],
) -> tuple[list[str], dict[str, Any], dict[str, str]]:
    reasons: list[str] = []
    if payload.get("collector_app") != release["browser_collector"]:
        reasons.append("Q_BROWSER_COLLECTOR_INVALID")
    if payload.get("schema_version") != release["browser_schema_version"]:
        reasons.append("Q_BROWSER_SCHEMA_INVALID")
    if payload.get("web_probe_revision") != release["browser_probe_revision"]:
        reasons.append("Q_BROWSER_PROBE_REVISION_INVALID")
    probe_metadata = payload.get("probe_metadata")
    if (
        not isinstance(probe_metadata, dict)
        or probe_metadata.get("core_revision") != release["browser_probe_revision"]
        or probe_metadata.get("expected_signal_count") != release["browser_signal_count"]
    ):
        reasons.append("Q_BROWSER_PROBE_METADATA_INVALID")
    features = feature_map(payload, ("web_data",))
    if set(features) != set(browser_fields):
        reasons.append("Q_BROWSER_FEATURESET_INVALID")
    status_reasons, statuses = validate_collection_status(
        payload,
        browser_fields,
        release["browser_status_schema_version"],
        release["browser_signal_count"],
        "BROWSER",
    )
    reasons.extend(status_reasons)
    if set(features) == set(browser_fields) and statuses:
        reasons.extend(feature_type_errors(features, statuses, browser_types, "BROWSER"))
    if not isinstance(payload.get("collection_diagnostics"), dict):
        reasons.append("Q_BROWSER_DIAGNOSTICS_MISSING")
    return sorted(set(reasons)), features, statuses


def current_git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def verify_release_files(config: dict[str, Any]) -> None:
    release = config["release"]
    build_file = resolve_repo_path(release["featureapp_build_file"])
    text = build_file.read_text(encoding="utf-8")
    code_match = re.search(r"\bversionCode\s*=\s*(\d+)", text)
    name_match = re.search(r'\bversionName\s*=\s*"([^"]+)"', text)
    if (
        code_match is None
        or int(code_match.group(1)) != release["featureapp_version_code"]
        or name_match is None
        or name_match.group(1) != release["featureapp_version_name"]
    ):
        raise ValueError("Latest paired244 config does not match FeatureApp build.gradle.kts")
    probe_manifest = json.loads(
        resolve_repo_path(config["sources"]["browser_probe_manifest"]).read_text(encoding="utf-8")
    )
    if (
        probe_manifest.get("revision") != release["browser_probe_revision"]
        or probe_manifest.get("signal_count") != release["browser_signal_count"]
    ):
        raise ValueError("Latest paired244 config does not match the browser probe manifest")


def validate_batch_ledger(
    rows: list[SourceRow], require_closed: bool
) -> tuple[dict[str, Any], list[str]]:
    if not rows:
        return {}, ["Q_APP_BATCH_MISSING"]
    reasons: list[str] = []
    values = [row.value for row in rows]
    if any(
        value.get("collection_batch_schema_version") != "backend-collection-batch-v1"
        for value in values
    ):
        reasons.append("Q_APP_BATCH_SCHEMA_INVALID")
    first = values[0]
    last = values[-1]
    if first.get("event") != "started" or first.get("lifecycle_status") != "open":
        reasons.append("Q_APP_BATCH_START_INVALID")
    if require_closed and (
        last.get("event") != "closed" or last.get("lifecycle_status") != "closed_cleanly"
    ):
        reasons.append("Q_APP_BATCH_NOT_CLOSED")
    return last, sorted(set(reasons))


def relevant_pair_events(
    app: AppObservation, event_rows: list[SourceRow]
) -> list[SourceRow]:
    """Keep only events bound to this App receipt/batch (or its provisional ticket)."""
    receipt_id = app.receipt.get("receipt_id")
    batch_id = app.raw_envelope.get("collection_batch_id")
    result: list[SourceRow] = []
    for row in event_rows:
        value = row.value
        if value.get("collection_batch_id") != batch_id:
            continue
        event_receipt = value.get("app_receipt_id")
        if event_receipt not in (None, receipt_id):
            continue
        result.append(row)
    return result


def app_observation(
    session_id: str,
    analysis_rows: list[SourceRow],
    raw_rows: list[SourceRow],
    receipt_by_id: dict[str, list[SourceRow]],
    batches_by_id: dict[str, list[SourceRow]],
    release: dict[str, Any],
    app_fields: list[str],
    app_types: dict[str, str],
) -> tuple[AppObservation | None, list[str]]:
    reasons: list[str] = []
    if len(analysis_rows) > 1:
        return None, ["Q_APP_ANALYSIS_DUPLICATE"]
    analysis = analysis_rows[0].value if analysis_rows else {}
    if not raw_rows:
        return None, ["Q_APP_RAW_ARCHIVE_MISSING"]
    if len(raw_rows) != 1:
        return None, ["Q_APP_RAW_ARCHIVE_DUPLICATE"]
    raw = raw_rows[0].value
    payload = raw.get("canonical_received_payload")
    if not isinstance(payload, dict):
        return None, ["Q_APP_CANONICAL_PAYLOAD_MISSING"]
    payload_reasons, features, statuses = validate_app_payload(
        payload, release, app_fields, app_types
    )
    reasons.extend(payload_reasons)
    # The backend analysis view intentionally flattens the three App layers;
    # canonical feature values remain authoritative in the raw archive. When
    # present, the analysis projection is checked against the raw contract.
    if analysis and (
        analysis.get("collector_app") != release["app_collector"]
        or analysis.get("schema_version") != release["app_schema_version"]
        or analysis.get("collection_manifest") != payload.get("collection_manifest")
        or analysis.get("collection_status") != payload.get("collection_status")
    ):
        reasons.append("Q_APP_ANALYSIS_RAW_MISMATCH")
    payload_hash = sha256_value(payload)
    if raw.get("session_id") != session_id or payload.get("session_id") != session_id:
        reasons.append("Q_APP_SESSION_JOIN_MISMATCH")
    if raw.get("payload_sha256") != payload_hash:
        reasons.append("Q_APP_HASH_MISMATCH")
    receipt_id = raw.get("receipt_id")
    receipts = receipt_by_id.get(str(receipt_id), [])
    if len(receipts) != 1:
        reasons.append("Q_APP_RECEIPT_MISSING" if not receipts else "Q_APP_RECEIPT_DUPLICATE")
        receipt: dict[str, Any] = {}
    else:
        receipt = receipts[0].value
        if (
            receipt.get("session_id") != session_id
            or receipt.get("payload_sha256") != payload_hash
            or receipt.get("stored_new_jsonl_row") is not True
            or receipt.get("duplicate_payload") is not False
        ):
            reasons.append("Q_APP_RECEIPT_MISMATCH")
    batch_id = raw.get("collection_batch_id")
    if (
        not isinstance(batch_id, str)
        or not batch_id
        or receipt.get("collection_batch_id") != batch_id
        or raw.get("collection_batch_id_source") != release["batch_id_source"]
        or receipt.get("collection_batch_id_source") != release["batch_id_source"]
    ):
        reasons.append("Q_APP_BATCH_MISMATCH")
    batch, batch_reasons = validate_batch_ledger(
        batches_by_id.get(str(batch_id), []), bool(release.get("require_closed_batch"))
    )
    reasons.extend(batch_reasons)
    if reasons:
        return None, sorted(set(reasons))
    return (
        AppObservation(
            analysis=analysis,
            raw_envelope=raw,
            payload=payload,
            receipt=receipt,
            batch=batch,
            features=features,
            field_status=statuses,
        ),
        [],
    )


def browser_pair_observation(
    app: AppObservation,
    provenance_rows: list[SourceRow],
    browser_analysis_by_pair: dict[str, list[SourceRow]],
    browser_raw_by_pair: dict[str, list[SourceRow]],
    provenance_by_pair: dict[str, list[SourceRow]],
    provenance_by_browser_session: dict[str, list[SourceRow]],
    release: dict[str, Any],
    browser_fields: list[str],
    browser_types: dict[str, str],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    if not provenance_rows:
        return None, [], []
    if len(provenance_rows) != 1:
        return None, ["Q_PAIR_MULTIPLE_COMPLETED_FOR_APP"], [
            str(row.value.get("pair_id") or "") for row in provenance_rows
        ]
    provenance = provenance_rows[0].value
    pair_id = str(provenance.get("pair_id") or "")
    browser_session_id = str(provenance.get("browser_session_id") or "")
    reasons: list[str] = []
    if provenance.get("browser_pair_provenance_schema_version") != release["pair_provenance_schema_version"]:
        reasons.append("Q_PAIR_PROVENANCE_SCHEMA_INVALID")
    if provenance.get("pair_status") != "completed":
        reasons.append("Q_PAIR_NOT_COMPLETED")
    if len(provenance_by_pair.get(pair_id, [])) != 1:
        reasons.append("Q_PAIR_ID_DUPLICATE")
    if len(provenance_by_browser_session.get(browser_session_id, [])) != 1:
        reasons.append("Q_BROWSER_SESSION_DUPLICATE")
    analysis_rows = browser_analysis_by_pair.get(pair_id, [])
    raw_rows = browser_raw_by_pair.get(pair_id, [])
    if len(analysis_rows) != 1:
        reasons.append("Q_BROWSER_ANALYSIS_MISSING" if not analysis_rows else "Q_BROWSER_ANALYSIS_DUPLICATE")
    if len(raw_rows) != 1:
        reasons.append("Q_BROWSER_RAW_MISSING" if not raw_rows else "Q_BROWSER_RAW_DUPLICATE")
    if reasons:
        return None, sorted(set(reasons)), [pair_id]
    analysis = analysis_rows[0].value
    raw = raw_rows[0].value
    payload = raw.get("canonical_received_payload")
    if not isinstance(payload, dict):
        return None, ["Q_BROWSER_CANONICAL_PAYLOAD_MISSING"], [pair_id]
    raw_reasons, browser_features, browser_status = validate_browser_payload(
        payload, release, browser_fields, browser_types
    )
    analysis_reasons, analysis_features, analysis_status = validate_browser_payload(
        analysis, release, browser_fields, browser_types
    )
    reasons.extend(raw_reasons)
    reasons.extend(analysis_reasons)
    if browser_features != analysis_features or browser_status != analysis_status:
        reasons.append("Q_BROWSER_ANALYSIS_RAW_MISMATCH")
    browser_hash = sha256_value(payload)
    app_hash = app.raw_envelope["payload_sha256"]
    batch_id = app.raw_envelope["collection_batch_id"]
    required_equalities = {
        "app_session_id": app.payload["session_id"],
        "app_receipt_id": app.receipt["receipt_id"],
        "app_payload_sha256": app_hash,
        "browser_session_id": payload.get("browser_session_id"),
        "browser_receipt_id": raw.get("browser_receipt_id"),
        "browser_payload_sha256": browser_hash,
        "collection_batch_id": batch_id,
    }
    for key, expected in required_equalities.items():
        if provenance.get(key) != expected or analysis.get(key) != expected:
            reasons.append("Q_PAIR_ID_RECEIPT_HASH_BATCH_MISMATCH")
            break
    if (
        raw.get("pair_id") != pair_id
        or payload.get("pair_id") != pair_id
        or raw.get("browser_session_id") != payload.get("browser_session_id")
        or raw.get("browser_receipt_id") != provenance.get("browser_receipt_id")
        or raw.get("browser_payload_sha256") != browser_hash
        or raw.get("collection_batch_id") != batch_id
        or raw.get("app_session_id") != app.payload["session_id"]
        or raw.get("app_receipt_id") != app.receipt["receipt_id"]
    ):
        reasons.append("Q_BROWSER_RAW_JOIN_MISMATCH")
    if reasons:
        return None, sorted(set(reasons)), [pair_id]
    combined_features = {
        **{f"app.{field}": app.features[field] for field in app.features},
        **{f"browser.{field}": browser_features[field] for field in browser_features},
    }
    combined_status = {
        **{f"app.{field}": app.field_status[field] for field in app.field_status},
        **{f"browser.{field}": browser_status[field] for field in browser_status},
    }
    sample_id = f"p244-{sha256_value({'pair_id': pair_id})[:24]}"
    return (
        {
            "record_schema_version": "hybridguard-paired244-view-v1",
            "sample_id": sample_id,
            "dataset_view": "paired_244",
            "dataset_role": "development_qc_only",
            "label_status": "unlabeled",
            "feature_count": len(combined_features),
            "features": combined_features,
            "field_status": combined_status,
            "app": {
                "session_id": app.payload["session_id"],
                "receipt_id": app.receipt["receipt_id"],
                "payload_sha256": app_hash,
                "collector_version_code": app.payload["collection_manifest"]["collector_version_code"],
                "collector_version_name": app.payload["collection_manifest"]["collector_version_name"],
                "analysis_available": bool(app.analysis),
            },
            "browser": {
                "session_id": payload["browser_session_id"],
                "receipt_id": raw["browser_receipt_id"],
                "payload_sha256": browser_hash,
                "resolved_browser_package": provenance.get("resolved_browser_package"),
                "web_probe_revision": payload["web_probe_revision"],
            },
            "pair": {
                "browser_pair_id": pair_id,
                "pair_status": "completed",
                "collection_batch_id": batch_id,
            },
            "identity": {
                "device_manifest_id": app.payload["collection_manifest"].get("device_manifest_id"),
                "identity_scope": "collector_install_profile_not_physical_device",
                "physical_device_id": None,
            },
        },
        [],
        [pair_id],
    )


def app_only_record(
    app: AppObservation,
    event_rows: list[SourceRow],
    invalid_pair_reasons: list[str],
    pair_ids: list[str],
) -> dict[str, Any]:
    latest = event_rows[-1].value if event_rows else {}
    if invalid_pair_reasons:
        capture_status = "attempted_incomplete"
        exclusion_reason = "completed_pair_failed_qc"
    elif event_rows:
        pair_ids = sorted(
            {
                str(row.value.get("pair_id"))
                for row in event_rows
                if isinstance(row.value.get("pair_id"), str) and row.value.get("pair_id")
            }
        )
        pair_status = latest.get("pair_status")
        expired = pair_status == "expired" or latest.get("event") == "browser_ticket_expired"
        unsupported = pair_status == "unsupported"
        capture_status = "unsupported" if unsupported else "attempted_incomplete"
        if expired:
            exclusion_reason = "browser_pair_expired"
        elif unsupported:
            exclusion_reason = "browser_capture_unsupported"
        else:
            exclusion_reason = f"pair_status_{pair_status or 'unknown'}_at_snapshot_cutoff"
    else:
        latest = {}
        capture_status = "not_requested"
        exclusion_reason = "no_pair_attempt_recorded"
    features = {f"app.{field}": app.features[field] for field in app.features}
    statuses = {f"app.{field}": app.field_status[field] for field in app.field_status}
    session_id = app.payload["session_id"]
    return {
        "record_schema_version": "hybridguard-app177-reserve-view-v1",
        "sample_id": f"app177-{sha256_value({'session_id': session_id})[:24]}",
        "dataset_view": "app_only_177",
        "dataset_role": "development_qc_only",
        "label_status": "unlabeled",
        "feature_count": len(features),
        "features": features,
        "field_status": statuses,
        "app": {
            "session_id": session_id,
            "receipt_id": app.receipt["receipt_id"],
            "payload_sha256": app.raw_envelope["payload_sha256"],
            "collector_version_code": app.payload["collection_manifest"]["collector_version_code"],
            "collector_version_name": app.payload["collection_manifest"]["collector_version_name"],
            "analysis_available": bool(app.analysis),
        },
        "browser_capture": {
            "status": capture_status,
            "paired_244_eligible": False,
            "exclusion_reason": exclusion_reason,
            "last_event": latest.get("event"),
            "last_pair_status": latest.get("pair_status"),
            "attempted_pair_ids": pair_ids,
            "pair_qc_reasons": sorted(set(invalid_pair_reasons)),
        },
        "collection": {"collection_batch_id": app.raw_envelope["collection_batch_id"]},
        "identity": {
            "device_manifest_id": app.payload["collection_manifest"].get("device_manifest_id"),
            "identity_scope": "collector_install_profile_not_physical_device",
            "physical_device_id": None,
        },
    }


def sample_index_row(record: dict[str, Any]) -> dict[str, Any]:
    app = record["app"]
    browser = record.get("browser") or {}
    pair = record.get("pair") or {}
    capture = record.get("browser_capture") or {
        "status": "completed",
        "paired_244_eligible": True,
        "exclusion_reason": None,
        "attempted_pair_ids": [pair.get("browser_pair_id")],
        "pair_qc_reasons": [],
    }
    collection_batch_id = pair.get("collection_batch_id") or record.get("collection", {}).get(
        "collection_batch_id"
    )
    return {
        "sample_index_version": "latest-paired244-sample-index-v1",
        "sample_id": record["sample_id"],
        "dataset_view": record["dataset_view"],
        "dataset_role": record["dataset_role"],
        "label_status": record["label_status"],
        "feature_count": record["feature_count"],
        "app_session_id": app["session_id"],
        "app_receipt_id": app.get("receipt_id"),
        "app_payload_sha256": app.get("payload_sha256"),
        "featureapp_version_code": app.get("collector_version_code"),
        "featureapp_version_name": app.get("collector_version_name"),
        "app_analysis_available": app.get("analysis_available"),
        "browser_session_id": browser.get("session_id"),
        "browser_receipt_id": browser.get("receipt_id"),
        "browser_payload_sha256": browser.get("payload_sha256"),
        "resolved_browser_package": browser.get("resolved_browser_package"),
        "browser_probe_revision": browser.get("web_probe_revision"),
        "browser_pair_id": pair.get("browser_pair_id"),
        "browser_capture_status": capture.get("status"),
        "paired_244_eligible": capture.get("paired_244_eligible"),
        "paired_exclusion_reason": capture.get("exclusion_reason"),
        "attempted_browser_pair_ids": capture.get("attempted_pair_ids", []),
        "browser_pair_qc_reasons": capture.get("pair_qc_reasons", []),
        "collection_batch_id": collection_batch_id,
        "device_manifest_id": record["identity"].get("device_manifest_id"),
        "identity_scope": record["identity"].get("identity_scope"),
    }


def data_view_row(record: dict[str, Any]) -> dict[str, Any]:
    """Keep model-facing observations free of provenance/control identifiers."""
    return {
        key: record[key]
        for key in (
            "record_schema_version",
            "sample_id",
            "dataset_view",
            "dataset_role",
            "label_status",
            "feature_count",
            "features",
            "field_status",
        )
    }


def build_snapshot(config_path: Path, output_dir: Path, run_id: str) -> dict[str, Any]:
    config_path = config_path.resolve()
    initial_config_signature = file_signature(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if file_signature(config_path) != initial_config_signature:
        raise RuntimeError("Snapshot config changed while being loaded")
    if output_dir.exists():
        raise FileExistsError(f"Snapshot output already exists: {output_dir}")
    release = config["release"]
    source_paths = {name: resolve_repo_path(path) for name, path in config["sources"].items()}
    input_paths = {
        "config": config_path,
        **source_paths,
        "featureapp_build_file": resolve_repo_path(release["featureapp_build_file"]),
    }
    input_signatures = {
        name: initial_config_signature if name == "config" else file_signature(path)
        for name, path in input_paths.items()
    }
    verify_release_files(config)
    jsonl_names = (
        "app_analysis",
        "app_raw",
        "app_receipts",
        "collection_batches",
        "browser_analysis",
        "browser_raw",
        "browser_pair_provenance",
        "browser_pair_events",
    )
    source_rows = {name: read_jsonl(source_paths[name]) for name in jsonl_names}
    app_fields, browser_fields, app_types, browser_types = load_catalog(
        source_paths["feature_catalog"],
        release["app_signal_count"],
        release["browser_signal_count"],
    )

    for source_name in ("app_analysis", "app_raw"):
        if any(
            not isinstance(row.value.get("session_id"), str)
            or not row.value.get("session_id")
            for row in source_rows[source_name]
        ):
            raise ValueError(f"{source_name} contains an App row without session_id")

    analysis_by_session = index_many(source_rows["app_analysis"], "session_id")
    raw_by_session = index_many(source_rows["app_raw"], "session_id")
    all_app_session_ids = set(analysis_by_session) | set(raw_by_session)
    exclusions: Counter[str] = Counter()
    selected_app_ids: set[str] = set()
    exclusion_by_session: dict[str, str] = {}
    observed_release_by_session: dict[str, dict[str, Any]] = {}
    selection_reason_by_session: dict[str, str] = {}
    for session_id in sorted(all_app_session_ids):
        selected, reason, observed = release_selection(
            analysis_by_session.get(session_id, []),
            raw_by_session.get(session_id, []),
            release,
        )
        observed_release_by_session[session_id] = observed
        selection_reason_by_session[session_id] = reason
        if selected:
            selected_app_ids.add(session_id)
        else:
            exclusion_by_session[session_id] = reason
            exclusions[reason] += 1

    receipt_by_id = index_many(source_rows["app_receipts"], "receipt_id")
    batches_by_id = index_many(source_rows["collection_batches"], "collection_batch_id")
    browser_analysis_by_pair = index_many(source_rows["browser_analysis"], "pair_id")
    browser_raw_by_pair = index_many(source_rows["browser_raw"], "pair_id")
    provenance_by_pair = index_many(source_rows["browser_pair_provenance"], "pair_id")
    provenance_by_app = index_many(source_rows["browser_pair_provenance"], "app_session_id")
    provenance_by_browser = index_many(source_rows["browser_pair_provenance"], "browser_session_id")
    events_by_app = index_many(source_rows["browser_pair_events"], "app_session_id")

    paired_rows: list[dict[str, Any]] = []
    app_only_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, Any]] = []
    for session_id in sorted(selected_app_ids):
        app, app_reasons = app_observation(
            session_id,
            analysis_by_session.get(session_id, []),
            raw_by_session.get(session_id, []),
            receipt_by_id,
            batches_by_id,
            release,
            app_fields,
            app_types,
        )
        if app is None:
            quarantine_rows.append(
                {
                    "quarantine_record_version": "latest-paired244-quarantine-v1",
                    "entity_type": "app_session",
                    "entity_id": session_id,
                    "reason_codes": app_reasons,
                }
            )
            continue
        completed = [
            row
            for row in provenance_by_app.get(session_id, [])
            if row.value.get("pair_status") == "completed"
        ]
        paired, pair_reasons, pair_ids = browser_pair_observation(
            app,
            completed,
            browser_analysis_by_pair,
            browser_raw_by_pair,
            provenance_by_pair,
            provenance_by_browser,
            release,
            browser_fields,
            browser_types,
        )
        if paired is not None:
            paired_rows.append(paired)
            continue
        if pair_reasons:
            quarantine_rows.append(
                {
                    "quarantine_record_version": "latest-paired244-quarantine-v1",
                    "entity_type": "browser_pair",
                    "entity_id": pair_ids[0] if len(pair_ids) == 1 else session_id,
                    "app_session_id": session_id,
                    "reason_codes": pair_reasons,
                }
            )
        event_rows = relevant_pair_events(app, events_by_app.get(session_id, []))
        app_only_rows.append(app_only_record(app, event_rows, pair_reasons, pair_ids))

    paired_rows.sort(key=lambda row: row["sample_id"])
    app_only_rows.sort(key=lambda row: row["sample_id"])
    quarantine_rows.sort(key=lambda row: (row["entity_type"], row["entity_id"]))
    index_rows = sorted(
        [sample_index_row(row) for row in paired_rows + app_only_rows],
        key=lambda row: row["sample_id"],
    )
    if any(row["feature_count"] != release["app_signal_count"] + release["browser_signal_count"] for row in paired_rows):
        raise ValueError("Internal paired244 feature-count invariant failed")
    if any(row["feature_count"] != release["app_signal_count"] for row in app_only_rows):
        raise ValueError("Internal App177 feature-count invariant failed")

    paired_app_ids = {row["app"]["session_id"] for row in paired_rows}
    app_only_ids = {row["app"]["session_id"] for row in app_only_rows}
    app_only_reason_by_id = {
        row["app"]["session_id"]: row["browser_capture"]["exclusion_reason"]
        for row in app_only_rows
    }
    quarantined_app_ids = {
        row["entity_id"] for row in quarantine_rows if row["entity_type"] == "app_session"
    }
    if (
        paired_app_ids & app_only_ids
        or paired_app_ids & quarantined_app_ids
        or app_only_ids & quarantined_app_ids
    ):
        raise ValueError("Latest App views are not mutually exclusive")
    if selected_app_ids != paired_app_ids | app_only_ids | quarantined_app_ids:
        raise ValueError("Latest App views do not exhaust the selected release")
    selection_audit_rows: list[dict[str, Any]] = []
    for session_id in sorted(all_app_session_ids):
        value = observed_release_by_session[session_id]
        if session_id in exclusion_by_session:
            outcome = "excluded_legacy"
            reason = exclusion_by_session[session_id]
        elif session_id in paired_app_ids:
            outcome = "paired_244"
            reason = "completed_pair_passed_qc"
        elif session_id in app_only_ids:
            outcome = "app_only_177"
            reason = app_only_reason_by_id[session_id]
        elif session_id in quarantined_app_ids:
            outcome = "quarantine"
            reason = "app_observation_failed_qc"
        else:
            outcome = "quarantine"
            reason = "selection_invariant_failed"
        manifest = value.get("collection_manifest") or {}
        selection_audit_rows.append(
            {
                "selection_audit_version": "latest-paired244-selection-audit-v1",
                "app_session_id": session_id,
                "analysis_source_lines": [
                    row.line_number for row in analysis_by_session.get(session_id, [])
                ],
                "raw_source_lines": [
                    row.line_number for row in raw_by_session.get(session_id, [])
                ],
                "observed_schema_version": value.get("schema_version"),
                "observed_featureapp_version_code": manifest.get("collector_version_code"),
                "observed_featureapp_version_name": manifest.get("collector_version_name"),
                "release_selection_reason": selection_reason_by_session[session_id],
                "outcome": outcome,
                "reason_code": reason,
            }
        )

    current_input_signatures = {
        name: file_signature(path) for name, path in input_paths.items()
    }
    changed_inputs = sorted(
        name
        for name in input_signatures
        if input_signatures[name] != current_input_signatures[name]
    )
    if changed_inputs:
        raise RuntimeError(
            "Snapshot inputs changed during build: " + ", ".join(changed_inputs)
        )

    output_dir.mkdir(parents=True)
    write_jsonl(output_dir / "paired_244.jsonl", map(data_view_row, paired_rows))
    write_jsonl(output_dir / "app_only_177.jsonl", map(data_view_row, app_only_rows))
    write_jsonl(output_dir / "quarantine.jsonl", quarantine_rows)
    write_jsonl(output_dir / "sample_index.jsonl", index_rows)
    write_jsonl(output_dir / "selection_audit.jsonl", selection_audit_rows)
    write_json(
        output_dir / "feature_catalog.json",
        {
            "feature_catalog_version": "latest-paired244-feature-catalog-v1",
            "paired_feature_count": len(app_fields) + len(browser_fields),
            "app_feature_count": len(app_fields),
            "browser_feature_count": len(browser_fields),
            "paired_feature_order": [f"app.{field}" for field in app_fields]
            + [f"browser.{field}" for field in browser_fields],
            "paired_feature_types": {
                **{f"app.{field}": app_types[field] for field in app_fields},
                **{f"browser.{field}": browser_types[field] for field in browser_fields},
            },
            "status_is_separate_from_feature_value": True,
        },
    )

    app_only_statuses = Counter(row["browser_capture"]["status"] for row in app_only_rows)
    browser_attempted_count = len(paired_rows) + sum(
        row["browser_capture"]["status"] != "not_requested" for row in app_only_rows
    )
    quarantine_reasons = Counter(
        reason for row in quarantine_rows for reason in row.get("reason_codes", [])
    )
    qc_summary = {
        "qc_summary_version": "latest-paired244-qc-summary-v1",
        "run_id": run_id,
        "counts": {
            "input_app_analysis_rows": len(source_rows["app_analysis"]),
            "input_app_raw_rows": len(source_rows["app_raw"]),
            "input_app_session_count": len(all_app_session_ids),
            "selected_latest_app_analysis_rows": sum(
                len(analysis_by_session.get(session_id, []))
                for session_id in selected_app_ids
            ),
            "selected_latest_app_raw_rows": sum(
                len(raw_by_session.get(session_id, [])) for session_id in selected_app_ids
            ),
            "selected_latest_app_session_count": len(selected_app_ids),
            "app177_valid_count": len(paired_rows) + len(app_only_rows),
            "browser_attempted_count": browser_attempted_count,
            "paired244_completed_count": len(paired_rows),
            "browser_incomplete_count": len(app_only_rows),
            "paired_244_count": len(paired_rows),
            "app_only_177_count": len(app_only_rows),
            "quarantined_app_count": sum(
                row["entity_type"] == "app_session" for row in quarantine_rows
            ),
            "quarantined_pair_count": sum(
                row["entity_type"] == "browser_pair" for row in quarantine_rows
            ),
        },
        "excluded_input_rows_by_reason": dict(sorted(exclusions.items())),
        "app_only_browser_status_counts": dict(sorted(app_only_statuses.items())),
        "quarantine_reason_counts": dict(sorted(quarantine_reasons.items())),
        "claim_boundary": "Collection/QC snapshot only; no attack label, score, accuracy, or generalization claim.",
    }
    write_json(output_dir / "qc_summary.json", qc_summary)

    source_inventory = {
        name: {
            "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            "row_count": len(source_rows[name]) if name in source_rows else None,
            **input_signatures[name],
        }
        for name, path in source_paths.items()
    }
    manifest = {
        "dataset_manifest_version": "latest-featureapp-paired244-snapshot-v1",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": current_git_commit(),
        "selection": {
            "featureapp_version_code": release["featureapp_version_code"],
            "featureapp_version_name": release["featureapp_version_name"],
            "app_schema_version": release["app_schema_version"],
            "browser_schema_version": release["browser_schema_version"],
            "browser_probe_revision": release["browser_probe_revision"],
            "pair_status": "completed",
        },
        "views": {
            "paired_244": {
                "path": "paired_244.jsonl",
                "count": len(paired_rows),
                "feature_count": release["app_signal_count"] + release["browser_signal_count"],
            },
            "app_only_177": {
                "path": "app_only_177.jsonl",
                "count": len(app_only_rows),
                "feature_count": release["app_signal_count"],
            },
            "quarantine": {
                "path": "quarantine.jsonl",
                "count": len(quarantine_rows),
            },
        },
        "dataset_role": config["policy"]["dataset_role"],
        "label_status": config["policy"]["label_status"],
        "missing_browser_values_are_never_imputed": True,
        "physical_device_count": None,
        "input_stability_check": "initial input signatures rechecked before output publication",
        "build_inputs": {
            name: {
                "path": str(path.relative_to(REPO_ROOT))
                if path.is_relative_to(REPO_ROOT)
                else str(path),
                **input_signatures[name],
            }
            for name, path in input_paths.items()
            if name in {"config", "featureapp_build_file"}
        },
        "source_inventory": source_inventory,
        "qc_summary_path": "qc_summary.json",
        "sample_index_path": "sample_index.jsonl",
        "selection_audit_path": "selection_audit.jsonl",
        "feature_catalog_path": "feature_catalog.json",
    }
    write_json(output_dir / "dataset_manifest.json", manifest)
    return manifest


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("latest_paired244_%Y%m%dT%H%M%SZ")
    output_dir = (args.output_dir or DEFAULT_ARTIFACT_ROOT / run_id).resolve()
    manifest = build_snapshot(args.config, output_dir, run_id)
    print(
        "Latest paired244 snapshot complete: "
        f"{manifest['views']['paired_244']['count']} paired, "
        f"{manifest['views']['app_only_177']['count']} App-only, "
        f"{manifest['views']['quarantine']['count']} quarantined -> {output_dir}"
    )


if __name__ == "__main__":
    main()
