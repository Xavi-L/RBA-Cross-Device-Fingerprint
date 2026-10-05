#!/usr/bin/env python3
"""Build an auditable per-session provenance sidecar for expanded collections.

The exporter intentionally derives a *platform profile* from the collection
provider plus the platform's declared unique brand/model/OS tuple. It never
claims that the value is a provider physical-device identifier.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import stat
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_PAYLOADS = BACKEND_DIR / "raw_expanded_payloads.jsonl"
DEFAULT_RECEIPTS = BACKEND_DIR / "collection_receipts.jsonl"
DEFAULT_BATCH_LEDGER = BACKEND_DIR / "collection_batches.jsonl"
DEFAULT_OUTPUT = BACKEND_DIR / "session_provenance.jsonl"
DEFAULT_PROFILE_HMAC_KEY_FILE = BACKEND_DIR.parent / ".hybridguard_profile_hmac_key"
PROFILE_HMAC_DOMAIN = "hybridguard-provider-profile-v1"
PROVENANCE_SCHEMA_VERSION = "session-provenance-v2"
BACKEND_BATCH_SCHEMA_VERSION = "backend-collection-batch-v1"
BACKEND_BATCH_ID_SOURCE = "backend_process_lifecycle"
LEGACY_BATCH_ID_SOURCE = "legacy_cli_supplied"


class ProvenanceError(ValueError):
    """Raised when inputs cannot support an unambiguous provenance record."""


JsonlEntry = tuple[int, dict[str, Any]]


def canonical_payload_sha256(payload: dict[str, Any]) -> str:
    """Match the backend's canonical receipt hash representation."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_jsonl(path: Path) -> list[JsonlEntry]:
    if not path.is_file():
        raise ProvenanceError(f"JSONL input does not exist: {path}")

    entries: list[JsonlEntry] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ProvenanceError(
                    f"Invalid JSON at {path}:{line_number}: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise ProvenanceError(f"Expected JSON object at {path}:{line_number}")
            entries.append((line_number, record))
    return entries


def normalise_text(value: Any) -> str:
    return " ".join(str(value).strip().split()).upper()


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def record_collection_batch_id(record: dict[str, Any]) -> str | None:
    return optional_text(record.get("collection_batch_id"))


def read_backend_batch_contexts(batch_ledger: Path) -> dict[str, dict[str, Any]]:
    """Return lifecycle context indexed by a backend-generated batch ID.

    The ledger is append-only. A terminal event is required for automatic
    selection because the user-defined batch boundary is service start through
    service shutdown, not an arbitrary point while the server is still running.
    """
    if not batch_ledger.exists():
        return {}
    if not batch_ledger.is_file():
        raise ProvenanceError(f"Batch ledger is not a file: {batch_ledger}")

    starts: dict[str, tuple[int, dict[str, Any]]] = {}
    closed: dict[str, tuple[int, dict[str, Any]]] = {}
    for line_number, event in read_jsonl(batch_ledger):
        if event.get("collection_batch_schema_version") != BACKEND_BATCH_SCHEMA_VERSION:
            continue
        batch_id = record_collection_batch_id(event)
        if batch_id is None:
            raise ProvenanceError(
                f"Batch ledger event at {batch_ledger}:{line_number} has no collection_batch_id"
            )
        event_name = event.get("event")
        if event_name == "started":
            if batch_id in starts:
                raise ProvenanceError(f"Batch ledger has duplicate start events for {batch_id}")
            starts[batch_id] = (line_number, event)
        elif event_name == "closed":
            if batch_id not in starts:
                raise ProvenanceError(f"Batch ledger closes unknown batch {batch_id}")
            if batch_id in closed:
                raise ProvenanceError(f"Batch ledger has duplicate close events for {batch_id}")
            closed[batch_id] = (line_number, event)

    contexts: dict[str, dict[str, Any]] = {}
    for batch_id, (started_line, started_event) in starts.items():
        closed_entry = closed.get(batch_id)
        closed_event = closed_entry[1] if closed_entry is not None else None
        contexts[batch_id] = {
            "collection_batch_id": batch_id,
            "collection_batch_id_source": BACKEND_BATCH_ID_SOURCE,
            "collection_batch_lifecycle_status": (
                closed_event.get("lifecycle_status") if closed_event is not None else "open"
            ),
            "collection_batch_started_at": started_event.get("started_at"),
            "collection_batch_ended_at": (
                closed_event.get("ended_at") if closed_event is not None else None
            ),
            "collection_batch_ended_at_source": (
                closed_event.get("ended_at_source") if closed_event is not None else None
            ),
            "collection_batch_ledger": batch_ledger.name,
            "collection_batch_started_ledger_line": started_line,
            "collection_batch_closed_ledger_line": (
                closed_entry[0] if closed_entry is not None else None
            ),
            "collection_batch_is_closed": closed_event is not None,
        }
    return contexts


def resolve_collection_batch_context(
    *,
    requested_batch_id: str | None,
    batch_ledger: Path,
) -> dict[str, Any]:
    """Select a closed backend batch, or an explicit legacy fallback batch."""
    contexts = read_backend_batch_contexts(batch_ledger)
    requested = optional_text(requested_batch_id)
    if requested is not None:
        context = contexts.get(requested)
        if context is not None:
            if not context["collection_batch_is_closed"]:
                raise ProvenanceError(
                    f"Collection batch {requested} is still open; stop the backend before exporting it"
                )
            return context
        return {
            "collection_batch_id": requested,
            "collection_batch_id_source": LEGACY_BATCH_ID_SOURCE,
            "collection_batch_lifecycle_status": "not_recorded_legacy",
            "collection_batch_started_at": None,
            "collection_batch_ended_at": None,
            "collection_batch_ended_at_source": None,
            "collection_batch_ledger": None,
            "collection_batch_started_ledger_line": None,
            "collection_batch_closed_ledger_line": None,
            "collection_batch_is_closed": None,
        }

    closed_contexts = [context for context in contexts.values() if context["collection_batch_is_closed"]]
    if not closed_contexts:
        raise ProvenanceError(
            "No closed backend collection batch is available. Stop the backend first, "
            "or pass --collection-batch-id only for a legacy unbatched export."
        )
    return max(
        closed_contexts,
        key=lambda context: context["collection_batch_closed_ledger_line"],
    )


def select_payload_entries_for_batch(
    payload_entries: list[JsonlEntry],
    batch_context: dict[str, Any],
) -> list[JsonlEntry]:
    """Keep only rows whose archive envelope belongs to the selected batch."""
    selected: list[JsonlEntry] = []
    batch_id = batch_context["collection_batch_id"]
    source = batch_context["collection_batch_id_source"]
    for entry in payload_entries:
        _, record = entry
        record_batch_id = record_collection_batch_id(record)
        if source == BACKEND_BATCH_ID_SOURCE:
            if record_batch_id == batch_id:
                selected.append(entry)
        elif source == LEGACY_BATCH_ID_SOURCE and record_batch_id is None:
            selected.append(entry)
        else:
            raise ProvenanceError(f"Unknown collection batch source: {source}")

    if not selected:
        raise ProvenanceError(
            f"No payload records belong to selected collection batch {batch_id}"
        )
    return selected


def load_profile_hmac_key(
    hmac_key_env: str,
    hmac_key_file: Path,
) -> tuple[str, str]:
    """Load a profile key without ever serialising it into a sidecar.

    An explicitly set environment variable takes precedence for CI. Local runs
    default to the ignored repository-root key file, which must not be readable
    by group or other users on POSIX hosts.
    """
    environment_key = optional_text(os.environ.get(hmac_key_env))
    if environment_key is not None:
        return environment_key, "environment"

    if not hmac_key_file.exists():
        raise ProvenanceError(
            f"Neither {hmac_key_env} nor profile HMAC key file exists: {hmac_key_file}"
        )
    if hmac_key_file.is_symlink() or not hmac_key_file.is_file():
        raise ProvenanceError(f"Profile HMAC key file must be a regular file: {hmac_key_file}")
    if os.name == "posix" and stat.S_IMODE(hmac_key_file.stat().st_mode) & 0o077:
        raise ProvenanceError(
            f"Profile HMAC key file is readable by group/other users: {hmac_key_file}; "
            "run chmod 600 on it"
        )
    file_key = optional_text(hmac_key_file.read_text(encoding="utf-8"))
    if file_key is None:
        raise ProvenanceError(f"Profile HMAC key file is empty: {hmac_key_file}")
    return file_key, "file"


def nested_value(value: Any, field_name: str) -> Any:
    """Find a field in a collector layer that may still be nested."""
    if not isinstance(value, dict):
        return None
    if field_name in value:
        return value[field_name]
    for child in value.values():
        result = nested_value(child, field_name)
        if result is not None:
            return result
    return None


def payload_from_entry(entry: JsonlEntry) -> tuple[dict[str, Any], bool]:
    """Return payload and whether the input is an immutable raw archive record."""
    _, record = entry
    archived_payload = record.get("canonical_received_payload")
    if isinstance(archived_payload, dict):
        return archived_payload, True
    return record, False


def required_session_id(payload: dict[str, Any], source: str) -> str:
    session_id = optional_text(payload.get("session_id"))
    if session_id is None:
        raise ProvenanceError(f"Missing session_id in {source}")
    return session_id


def receipt_time(receipt: dict[str, Any], source: str) -> datetime:
    value = optional_text(receipt.get("server_received_at"))
    if value is None:
        raise ProvenanceError(f"Missing server_received_at in {source}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProvenanceError(f"Invalid server_received_at in {source}: {value}") from error


def extract_device_fields(payload: dict[str, Any], source: str) -> dict[str, Any]:
    native_data = payload.get("android_native_data")
    model = optional_text(nested_value(native_data, "device_model"))
    os_version = optional_text(nested_value(native_data, "os_version"))
    if model is None or os_version is None:
        raise ProvenanceError(
            f"{source} is missing device_model or os_version required for the profile rule"
        )

    return {
        "brand": optional_text(nested_value(native_data, "device_brand")),
        "model": model,
        "os_version": os_version,
        "android_api": nested_value(native_data, "os_api_level"),
    }


def profile_id(
    *,
    hmac_key: str,
    platform_provider: str,
    brand: str | None,
    model: str,
    os_version: str,
) -> str:
    """Return a non-reversible profile pseudonym for one provider catalog key."""
    material = "\x1f".join(
        (
            PROFILE_HMAC_DOMAIN,
            normalise_text(platform_provider),
            normalise_text(brand or ""),
            normalise_text(model),
            normalise_text(os_version),
        )
    )
    digest = hmac.new(
        hmac_key.encode("utf-8"), material.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"hgprof-v1-{digest[:24]}"


def select_receipt(
    receipts: list[JsonlEntry],
    session_id: str,
    collection_batch_id: str,
    collection_batch_id_source: str,
) -> tuple[int, dict[str, Any]]:
    persisted = [entry for entry in receipts if entry[1].get("stored_new_jsonl_row") is True]
    if not persisted:
        raise ProvenanceError(
            f"Session {session_id} has no receipt with stored_new_jsonl_row=true"
        )
    if collection_batch_id_source == BACKEND_BATCH_ID_SOURCE:
        persisted = [
            entry
            for entry in persisted
            if record_collection_batch_id(entry[1]) == collection_batch_id
        ]
    elif collection_batch_id_source == LEGACY_BATCH_ID_SOURCE:
        persisted = [
            entry for entry in persisted if record_collection_batch_id(entry[1]) is None
        ]
    else:
        raise ProvenanceError(
            f"Unknown collection batch source: {collection_batch_id_source}"
        )
    if not persisted:
        raise ProvenanceError(
            f"Session {session_id} has no stored receipt bound to collection batch "
            f"{collection_batch_id}"
        )
    return min(
        persisted,
        key=lambda entry: (receipt_time(entry[1], f"receipt for {session_id}"), entry[0]),
    )


def index_unique_payloads(payload_entries: list[JsonlEntry]) -> dict[str, JsonlEntry]:
    by_session: dict[str, JsonlEntry] = {}
    for entry in payload_entries:
        line_number, _ = entry
        payload, _ = payload_from_entry(entry)
        session_id = required_session_id(payload, f"payload line {line_number}")
        if session_id in by_session:
            previous_line, _ = by_session[session_id]
            raise ProvenanceError(
                f"Session {session_id} appears more than once in payload input "
                f"(lines {previous_line} and {line_number}); export one immutable payload per session"
            )
        by_session[session_id] = entry
    return by_session


def index_receipts(receipt_entries: list[JsonlEntry]) -> dict[str, list[JsonlEntry]]:
    by_session: dict[str, list[JsonlEntry]] = defaultdict(list)
    for entry in receipt_entries:
        line_number, receipt = entry
        session_id = required_session_id(receipt, f"receipt line {line_number}")
        by_session[session_id].append(entry)
    return by_session


def verify_raw_archive(
    entry: JsonlEntry,
    payload: dict[str, Any],
    receipt: dict[str, Any],
    collection_batch_id: str,
    collection_batch_id_source: str,
) -> None:
    line_number, archive = entry
    archive_hash = optional_text(archive.get("payload_sha256"))
    receipt_hash = optional_text(receipt.get("payload_sha256"))
    calculated_hash = canonical_payload_sha256(payload)
    if not archive_hash or not receipt_hash:
        raise ProvenanceError(f"Raw archive or receipt hash missing for archive line {line_number}")
    if archive_hash != calculated_hash or receipt_hash != calculated_hash:
        raise ProvenanceError(
            f"Raw archive hash mismatch for session {payload.get('session_id')} at line {line_number}"
        )
    archive_receipt_id = optional_text(archive.get("receipt_id"))
    if archive_receipt_id and archive_receipt_id != optional_text(receipt.get("receipt_id")):
        raise ProvenanceError(
            f"Raw archive receipt_id mismatch for session {payload.get('session_id')}"
        )
    archive_batch_id = record_collection_batch_id(archive)
    receipt_batch_id = record_collection_batch_id(receipt)
    if collection_batch_id_source == BACKEND_BATCH_ID_SOURCE:
        if archive_batch_id != collection_batch_id or receipt_batch_id != collection_batch_id:
            raise ProvenanceError(
                f"Raw archive/receipt batch mismatch for session {payload.get('session_id')}; "
                f"expected {collection_batch_id}, archive={archive_batch_id}, receipt={receipt_batch_id}"
            )
    elif collection_batch_id_source == LEGACY_BATCH_ID_SOURCE:
        if archive_batch_id is not None or receipt_batch_id is not None:
            raise ProvenanceError(
                f"Legacy batch fallback cannot relabel server-batched session {payload.get('session_id')}"
            )
    else:
        raise ProvenanceError(
            f"Unknown collection batch source: {collection_batch_id_source}"
        )


def build_provenance_records(
    *,
    payload_entries: list[JsonlEntry],
    receipt_entries: list[JsonlEntry],
    platform_provider: str,
    collection_batch_id: str,
    collection_batch_id_source: str = LEGACY_BATCH_ID_SOURCE,
    collection_batch_lifecycle_status: str = "not_recorded_legacy",
    collection_batch_started_at: str | None = None,
    collection_batch_ended_at: str | None = None,
    collection_batch_ended_at_source: str | None = None,
    collection_batch_ledger: str | None = None,
    profile_hmac_key: str,
    profile_hmac_key_id: str = "profile-hmac-key-v1",
    profile_hmac_key_source: str = "direct",
    platform_run_id: str | None = None,
    payload_source_name: str,
) -> list[dict[str, Any]]:
    provider = optional_text(platform_provider)
    batch_id = optional_text(collection_batch_id)
    if provider is None or batch_id is None:
        raise ProvenanceError("platform_provider and collection_batch_id must be non-empty")
    if collection_batch_id_source not in {
        BACKEND_BATCH_ID_SOURCE,
        LEGACY_BATCH_ID_SOURCE,
    }:
        raise ProvenanceError(f"Unknown collection batch source: {collection_batch_id_source}")
    if not profile_hmac_key:
        raise ProvenanceError("profile HMAC key must be non-empty")
    if optional_text(profile_hmac_key_id) is None:
        raise ProvenanceError("profile HMAC key id must be non-empty")

    payload_by_session = index_unique_payloads(payload_entries)
    receipts_by_session = index_receipts(receipt_entries)
    pending: list[dict[str, Any]] = []
    api_by_profile_basis: dict[tuple[str, str, str, str], str] = {}

    for session_id, payload_entry in payload_by_session.items():
        line_number, _ = payload_entry
        payload, is_raw_archive = payload_from_entry(payload_entry)
        selected_receipt_entry = select_receipt(
            receipts_by_session.get(session_id, []),
            session_id,
            batch_id,
            collection_batch_id_source,
        )
        _, receipt = selected_receipt_entry
        if is_raw_archive:
            verify_raw_archive(
                payload_entry,
                payload,
                receipt,
                batch_id,
                collection_batch_id_source,
            )

        device = extract_device_fields(payload, f"payload line {line_number}")
        resolved_profile_id = profile_id(
            hmac_key=profile_hmac_key,
            platform_provider=provider,
            brand=device["brand"],
            model=device["model"],
            os_version=device["os_version"],
        )
        profile_basis = (
            normalise_text(provider),
            normalise_text(device["brand"] or ""),
            normalise_text(device["model"]),
            normalise_text(device["os_version"]),
        )
        api_value = optional_text(device["android_api"])
        if api_value is not None:
            previous_api_value = api_by_profile_basis.setdefault(profile_basis, api_value)
            if previous_api_value != api_value:
                raise ProvenanceError(
                    "Inconsistent os_api_level for one provider brand/model/os profile: "
                    f"{device['brand']!r}/{device['model']!r}/{device['os_version']!r} "
                    f"has {previous_api_value} and {api_value}"
                )
        pending.append(
            {
                "session_id": session_id,
                "payload_line": line_number,
                "payload": payload,
                "is_raw_archive": is_raw_archive,
                "receipt": receipt,
                "receipt_time": receipt_time(receipt, f"receipt for {session_id}"),
                "profile_id": resolved_profile_id,
                "device": device,
            }
        )

    # One app launch creates one UUID. Receipt order is server-observed and avoids
    # trusting mutable client clocks; session_id makes an equal timestamp deterministic.
    pending.sort(key=lambda record: (record["receipt_time"], record["session_id"]))
    rounds_by_profile: dict[tuple[str, str], int] = defaultdict(int)
    records: list[dict[str, Any]] = []
    resolved_run_id = optional_text(platform_run_id)

    for item in pending:
        payload = item["payload"]
        receipt = item["receipt"]
        device = item["device"]
        resolved_profile_id = item["profile_id"]
        round_key = (batch_id, resolved_profile_id)
        rounds_by_profile[round_key] += 1
        webview_data = payload.get("webview_data")
        collection_manifest = payload.get("collection_manifest")
        declared_round = (
            collection_manifest.get("collection_round")
            if isinstance(collection_manifest, dict)
            else None
        )
        records.append(
            {
                "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
                "session_id": item["session_id"],
                "collection_batch_id": batch_id,
                "collection_batch_id_source": collection_batch_id_source,
                "collection_batch_lifecycle_status": collection_batch_lifecycle_status,
                "collection_batch_started_at": collection_batch_started_at,
                "collection_batch_ended_at": collection_batch_ended_at,
                "collection_batch_ended_at_source": collection_batch_ended_at_source,
                "collection_batch_ledger": collection_batch_ledger,
                "platform_provider": provider,
                "platform_run_id": resolved_run_id,
                "platform_run_id_status": "provided" if resolved_run_id else "not_available",
                "profile_id": resolved_profile_id,
                "profile_id_scope": "provider_catalog_brand_model_os",
                "profile_id_source": "backend_derived",
                "profile_key_version": "profile-v1",
                "profile_hmac_key_id": profile_hmac_key_id,
                "profile_hmac_key_source": profile_hmac_key_source,
                "profile_uniqueness_rule": "platform_declared_unique_brand_model_os",
                "collection_round": rounds_by_profile[round_key],
                "collection_round_source": "first_stored_receipt_order",
                "declared_collection_round": declared_round,
                "declared_collection_round_source": (
                    "collection_manifest" if declared_round is not None else "not_available"
                ),
                "platform_device_hash": None,
                "platform_device_hash_status": "not_collected_not_required",
                "device_hash": resolved_profile_id,
                "device_hash_scope": "provider_model_os_profile",
                "device_hash_is_platform_device_id": False,
                "receipt_id": receipt.get("receipt_id"),
                "payload_sha256": receipt.get("payload_sha256"),
                "server_received_at": receipt.get("server_received_at"),
                "receipt_validation_status": receipt.get("validation_status"),
                "receipt_validation_warnings": receipt.get("validation_warnings", []),
                "payload_record_source": payload_source_name,
                "payload_record_line": item["payload_line"],
                "raw_payload_available": item["is_raw_archive"],
                "payload_sha256_verification": (
                    "verified_canonical_raw_archive"
                    if item["is_raw_archive"]
                    else "not_verifiable_from_flattened_analysis_record"
                ),
                "collector_app": payload.get("collector_app"),
                "schema_version": payload.get("schema_version"),
                "device_brand": device["brand"],
                "device_model": device["model"],
                "os_version": device["os_version"],
                "android_api": device["android_api"],
                "webview_provider_package": nested_value(webview_data, "webview_provider_package"),
                "webview_provider_version": nested_value(webview_data, "webview_provider_version"),
                "webview_provider_version_code": nested_value(webview_data, "webview_provider_version_code"),
                "app_package_name": nested_value(webview_data, "app_package_name"),
                "app_version_name": nested_value(webview_data, "app_version_name"),
                "app_version_code": nested_value(webview_data, "app_version_code"),
            }
        )
    return records


def write_jsonl_atomically(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_path.parent,
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    temporary_path.replace(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_RAW_PAYLOADS,
        help="Canonical raw archive for new batches; pass expanded_collected_data.jsonl only for legacy export.",
    )
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument(
        "--batch-ledger",
        type=Path,
        default=DEFAULT_BATCH_LEDGER,
        help="Backend lifecycle ledger used to select the latest closed batch automatically.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--platform-provider", required=True)
    parser.add_argument(
        "--collection-batch-id",
        help="Select one closed backend batch, or supply a legacy batch label when input lacks server batch metadata.",
    )
    parser.add_argument("--platform-run-id")
    parser.add_argument(
        "--profile-hmac-key-id",
        default="profile-hmac-key-v1",
        help="Non-secret key-rotation label recorded in the sidecar.",
    )
    parser.add_argument(
        "--hmac-key-env",
        default="HYBRIDGUARD_PROFILE_HMAC_KEY",
        help="Environment variable taking precedence over the local profile key file; never put the key on the command line.",
    )
    parser.add_argument(
        "--hmac-key-file",
        type=Path,
        default=DEFAULT_PROFILE_HMAC_KEY_FILE,
        help="Ignored local key file used when the environment variable is absent.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved_input = args.input.resolve()
    resolved_receipts = args.receipts.resolve()
    resolved_batch_ledger = args.batch_ledger.resolve()
    resolved_output = args.output.resolve()
    if resolved_output in {resolved_input, resolved_receipts, resolved_batch_ledger}:
        raise SystemExit("Output must not overwrite an input JSONL file.")

    try:
        hmac_key, hmac_key_source = load_profile_hmac_key(
            args.hmac_key_env,
            args.hmac_key_file.expanduser().absolute(),
        )
        batch_context = resolve_collection_batch_context(
            requested_batch_id=args.collection_batch_id,
            batch_ledger=resolved_batch_ledger,
        )
        payload_entries = select_payload_entries_for_batch(
            read_jsonl(resolved_input),
            batch_context,
        )
        records = build_provenance_records(
            payload_entries=payload_entries,
            receipt_entries=read_jsonl(resolved_receipts),
            platform_provider=args.platform_provider,
            collection_batch_id=batch_context["collection_batch_id"],
            collection_batch_id_source=batch_context["collection_batch_id_source"],
            collection_batch_lifecycle_status=batch_context["collection_batch_lifecycle_status"],
            collection_batch_started_at=batch_context["collection_batch_started_at"],
            collection_batch_ended_at=batch_context["collection_batch_ended_at"],
            collection_batch_ended_at_source=batch_context["collection_batch_ended_at_source"],
            collection_batch_ledger=batch_context["collection_batch_ledger"],
            profile_hmac_key=hmac_key,
            profile_hmac_key_id=args.profile_hmac_key_id,
            profile_hmac_key_source=hmac_key_source,
            platform_run_id=args.platform_run_id,
            payload_source_name=resolved_input.name,
        )
    except ProvenanceError as error:
        raise SystemExit(str(error)) from error
    write_jsonl_atomically(records, resolved_output)
    print(f"Wrote {len(records)} provenance records to {resolved_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
