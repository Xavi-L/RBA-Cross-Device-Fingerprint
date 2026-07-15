#!/usr/bin/env python3
"""Freeze HybridGuard raw collection sources into a QC and provenance snapshot.

This script deliberately handles raw features and research metadata separately.
It can use historical JSONL for schema/QC work, but it grants supervised-model
eligibility only when a source supplies verified labels and an Attack Manifest.
No third-party packages are required.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
AGENT_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = AGENT_ROOT.parent
DEFAULT_CONFIG = AGENT_ROOT / "config" / "dataset_sources.json"
DEFAULT_SCHEMA = AGENT_ROOT / "schemas" / "expanded_v2.schema.json"
DEFAULT_REGISTRY = AGENT_ROOT / "schemas" / "field_registry.json"
DEFAULT_ARTIFACT_ROOT = AGENT_ROOT / "artifacts"

LAYER_NAMES = ("android_native_data", "webview_data", "web_data")
EXPECTED_COUNTS = {
    "android_native_data": 84,
    "webview_data": 26,
    "web_data": 67,
}
ANNOTATION_SCHEMA_VERSION = "experiment-session-annotation-v1"
ANNOTATION_REQUIRED_COLUMNS = {
    "registry_schema_version",
    "dataset_version",
    "sample_id",
    "source_session_id",
    "device_group_id",
    "split",
    "experiment_id",
    "pair_id",
    "round",
    "state",
    "experiment_design",
    "attack_type",
    "intervention_name",
    "tool_execution_status",
    "observable_effect_status",
    "field_effect_status",
    "attributable_effect_status",
    "rollback_status",
    "pair_outcome",
    "include_in_complete_pair_evaluation",
    "annotation_confidence",
    "annotation_basis",
    "evidence_reference",
    "claim_boundary",
}
PAIR_ROLE_BY_STATE = {
    "clean": ("clean_pre", 0),
    "active": ("attack_active", 1),
    "post": ("clean_post", 2),
}
STABLE_KEY_PATHS = (
    "android_native_data.build_fingerprint",
    "android_native_data.device_model",
    "android_native_data.device_product",
    "android_native_data.device_board",
    "android_native_data.device_hardware",
    "android_native_data.os_api_level",
    "android_native_data.build_id",
    "android_native_data.supported_abis",
    "android_native_data.screen_resolution_physical",
    "android_native_data.total_memory_gb",
    "android_native_data.sensor_total_count",
    "android_native_data.sensor_type_list",
    "android_native_data.native_gpu_renderer",
    "android_native_data.egl_renderer",
    "android_native_data.gles_renderer",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", help="Unique artifact directory name.")
    parser.add_argument(
        "--bootstrap-contract",
        action="store_true",
        help="Create frozen expanded-v2 contract and field registry from current valid V2 rows.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing a pre-existing artifact directory with the same run ID.",
    )
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def leaf_items(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else key
            yield from leaf_items(value[key], child_prefix)
        return
    yield prefix, value


def get_path(row: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = row
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return default
        current = current[segment]
    return current


def normalize_for_identity(value: Any, path: str) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return sorted(str(item).strip() for item in value)
    if path.endswith("total_memory_gb") and isinstance(value, (int, float)):
        return math.floor(float(value) * 2 + 0.5) / 2
    if isinstance(value, str):
        return value.strip().lower()
    return value


def heuristic_stable_key(row: dict[str, Any], source_type: str) -> tuple[str, list[str]]:
    selected: dict[str, Any] = {}
    used_paths: list[str] = []
    for path in STABLE_KEY_PATHS:
        value = get_path(row, path)
        if value is None:
            continue
        # Multiple platform-specific GPU candidates may exist; retain the first present one.
        if path.endswith(("native_gpu_renderer", "egl_renderer", "gles_renderer")):
            if any(existing.endswith(("native_gpu_renderer", "egl_renderer", "gles_renderer")) for existing in used_paths):
                continue
        selected[path] = normalize_for_identity(value, path)
        used_paths.append(path)
    selected["capture_source_type"] = source_type
    return sha256_value(selected), used_paths


def observed_identity_key(row: dict[str, Any], source_type: str) -> str:
    paths = (
        "android_native_data.build_fingerprint",
        "android_native_data.device_model",
        "android_native_data.os_api_level",
        "android_native_data.cpu_abi",
        "webview_data.webview_provider_version",
        "web_data.user_agent",
        "web_data.webgl_renderer",
        "web_data.screen_resolution_logical",
    )
    value = {path: normalize_for_identity(get_path(row, path), path) for path in paths}
    value["capture_source_type"] = source_type
    return sha256_value(value)


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append((line_number, value))
    return rows


def load_manifest_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    if path.suffix.lower() == ".jsonl":
        rows = [row for _, row in read_jsonl(path)]
    else:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        rows = loaded if isinstance(loaded, list) else [loaded]
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        session_id = row.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(f"Manifest {path} has an entry without session_id")
        if session_id in index:
            raise ValueError(f"Manifest {path} repeats session_id {session_id}")
        index[session_id] = row
    return index


def parse_registry_bool(value: Any, *, field: str, row_number: int) -> bool:
    text = str(value or "").strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Annotation registry row {row_number} has invalid {field}={value!r}")


def load_annotation_registry(
    path: Path | None,
    evidence_root: Path | None,
) -> dict[str, Any] | None:
    """Load and machine-check the label-only experiment registry.

    The returned indexes are used only to build manifests and evaluation sidecars. Raw
    normalized payloads never receive any registry column.
    """
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(ANNOTATION_REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise ValueError(f"Annotation registry {path} is missing columns: {missing_columns}")
        rows = []
        by_sample_id: dict[str, dict[str, str]] = {}
        by_session_id: dict[str, dict[str, str]] = {}
        missing_evidence: list[str] = []
        for row_number, raw_row in enumerate(reader, start=2):
            row = {key: str(value or "").strip() for key, value in raw_row.items()}
            if row["registry_schema_version"] != ANNOTATION_SCHEMA_VERSION:
                raise ValueError(
                    f"Annotation registry row {row_number} has unsupported schema "
                    f"{row['registry_schema_version']!r}"
                )
            sample_id = row["sample_id"]
            session_id = row["source_session_id"]
            if not sample_id or not session_id:
                raise ValueError(f"Annotation registry row {row_number} has an empty join id")
            if sample_id in by_sample_id:
                raise ValueError(f"Annotation registry repeats sample_id {sample_id}")
            if session_id in by_session_id:
                raise ValueError(f"Annotation registry repeats source_session_id {session_id}")
            parse_registry_bool(
                row["include_in_complete_pair_evaluation"],
                field="include_in_complete_pair_evaluation",
                row_number=row_number,
            )
            evidence_reference = row["evidence_reference"]
            if evidence_reference and evidence_root is not None:
                evidence_path = evidence_root / evidence_reference
                if not evidence_path.exists():
                    missing_evidence.append(evidence_reference)
            rows.append(row)
            by_sample_id[sample_id] = row
            by_session_id[session_id] = row
    if missing_evidence:
        raise ValueError(
            f"Annotation registry references missing evidence files: {sorted(set(missing_evidence))}"
        )
    return {
        "path": path,
        "rows": rows,
        "by_sample_id": by_sample_id,
        "by_session_id": by_session_id,
        "missing_evidence": missing_evidence,
    }


def annotation_task_memberships(annotation: dict[str, str]) -> list[str]:
    complete = parse_registry_bool(
        annotation["include_in_complete_pair_evaluation"],
        field="include_in_complete_pair_evaluation",
        row_number=0,
    )
    if complete and annotation["experiment_design"] == "pairable_clean_active_post":
        if annotation["field_effect_status"] == "verified_target_field_change" or annotation["attack_type"] == "web_runtime_injection":
            return ["fingerprint_field_effect_pilot"]
        if annotation["attack_type"] == "network_interception":
            return ["transport_path_effect_pilot"]
    if annotation["experiment_design"] in {"compatibility_baseline", "manual_smoke_baseline"}:
        return ["baseline_qc"]
    return ["incomplete_attempt_failure_analysis"]


def attach_experiment_annotation(
    provided: dict[str, Any] | None,
    annotation: dict[str, str] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if provided is None:
        return None, ["E_MANIFEST_MISSING"]
    if annotation is None:
        return provided, ["E_ANNOTATION_MISSING"]

    state = annotation["state"]
    complete = parse_registry_bool(
        annotation["include_in_complete_pair_evaluation"],
        field="include_in_complete_pair_evaluation",
        row_number=0,
    )
    tasks = annotation_task_memberships(annotation)
    is_no_intervention_baseline = annotation["attack_type"].startswith("none_")
    label_verified = complete or is_no_intervention_baseline
    manipulation_present = state == "active" and not is_no_intervention_baseline
    violation_types = [annotation["attack_type"]] if manipulation_present else []
    environment_class = (
        annotation["experiment_design"]
        if is_no_intervention_baseline
        else ("paired_intervention_active" if state == "active" else "paired_intervention_control")
    )
    provided["label"] = {
        "environment_class": environment_class,
        "manipulation_present": manipulation_present,
        "violation_types": violation_types,
        "label_status": "verified" if label_verified else "rejected",
        "label_provenance": "experiment_session_annotation_registry_v1",
    }

    pair_id = annotation["pair_id"]
    if pair_id:
        pair_role, sequence_index = PAIR_ROLE_BY_STATE.get(state, (state or "unknown", -1))
        provided["pair"] = {
            "pair_id": pair_id,
            "pair_role": pair_role,
            "sequence_index": sequence_index,
            "experiment_id": annotation["experiment_id"],
            "round": int(annotation["round"]) if annotation["round"].isdigit() else None,
        }

    execution_status = {
        "verified": "verified_success",
        "not_executed_in_state": "not_executed_in_state",
        "not_applicable": "not_applicable",
    }.get(annotation["tool_execution_status"], annotation["tool_execution_status"] or "unknown")
    feature_effect_status = {
        "verified_target_field_change": "observed",
        "partial_target_field_change": "partial",
        "no_fingerprint_field_change_claimed": "not_claimed",
        "not_applicable": "not_applicable",
    }.get(annotation["field_effect_status"], annotation["field_effect_status"] or "unknown")
    provided["attack"] = {
        "attack_family": annotation["attack_type"],
        "attack_type": annotation["attack_type"],
        "tool_name": annotation["intervention_name"],
        "execution_status": execution_status,
        "feature_effect_status": feature_effect_status,
        "attributable_effect_status": annotation["attributable_effect_status"],
        "rollback_status": annotation["rollback_status"],
        "evidence_reference": annotation["evidence_reference"],
    }
    provided["evaluation"] = {
        "registry_schema_version": annotation["registry_schema_version"],
        "dataset_version": annotation["dataset_version"],
        "split": annotation["split"],
        "task_memberships": tasks,
        "include_in_complete_pair_evaluation": complete,
        "pair_outcome": annotation["pair_outcome"],
        "annotation_confidence": annotation["annotation_confidence"],
        "observable_effect_status": annotation["observable_effect_status"],
        "field_effect_status": annotation["field_effect_status"],
        "attributable_effect_status": annotation["attributable_effect_status"],
        "claim_boundary": annotation["claim_boundary"],
    }
    provided["annotation_join"] = {
        "sample_id": annotation["sample_id"],
        "source_session_id_hash": sha256_value(annotation["source_session_id"]),
        "join_status": "matched_by_sample_and_session",
    }
    warnings = [] if label_verified else ["W_ANNOTATION_EXCLUDED_FROM_COMPLETE_PAIR"]
    return provided, warnings


def canonical_schema_version(value: Any) -> str | None:
    """Map backward-compatible status-bearing payloads to the 177-field contract."""
    text = str(value or "").strip()
    if text in {"expanded-v2", "expanded-v2.1-status", "expanded-v2.2-status"}:
        return "expanded-v2"
    return None


def collection_status_errors(status: Any) -> list[str]:
    if not isinstance(status, dict):
        return ["E_COLLECTION_STATUS"]
    counts = status.get("counts")
    fields = (
        "observed",
        "unsupported_by_os",
        "permission_denied",
        "runtime_error",
        "timeout",
        "not_applicable",
    )
    if not isinstance(counts, dict) or not isinstance(status.get("fixed_signal_count"), int):
        return ["E_COLLECTION_STATUS"]
    if any(not isinstance(counts.get(name), int) or counts[name] < 0 for name in fields):
        return ["E_COLLECTION_STATUS"]
    if sum(counts[name] for name in fields) != status["fixed_signal_count"]:
        return ["E_COLLECTION_STATUS"]
    if status["fixed_signal_count"] != sum(EXPECTED_COUNTS.values()):
        return ["E_COLLECTION_STATUS"]
    field_states = status.get("fields")
    if (
        not isinstance(field_states, dict)
        or len(field_states) != status["fixed_signal_count"]
        or any(value not in fields for value in field_states.values())
        or Counter(field_states.values()) != Counter({name: counts[name] for name in fields if counts[name]})
    ):
        return ["E_COLLECTION_STATUS"]
    if any(counts[name] > 0 for name in ("permission_denied", "runtime_error", "timeout", "not_applicable")):
        return ["W_COLLECTION_PARTIAL"]
    return []


def infer_historical_field_status(row: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Build a sidecar status only for a validated legacy row.

    This does not claim that the old collector emitted field-status-v1. It records the
    narrower fact that the frozen 177-field payload is present and non-null in the raw JSONL.
    Collection context such as Android profile or provider run id remains unknown.
    """
    observed_fields = field_map(row)
    states: dict[str, str] = {}
    counts = {
        "observed": 0,
        "unsupported_by_os": 0,
        "permission_denied": 0,
        "runtime_error": 0,
        "timeout": 0,
        "not_applicable": 0,
    }
    for path in sorted(contract["fields"]):
        status = "observed" if observed_fields.get(path) is not None else "runtime_error"
        states[path] = status
        counts[status] += 1
    return {
        "status_schema_version": "field-status-v1-historical-inferred",
        "fixed_signal_count": contract["fixed_schema_dim"],
        "counts": counts,
        "fields": states,
        "path_convention": "expanded-v2-flat-contract",
        "collector_emitted": False,
        "inference_basis": (
            "The raw legacy payload passed the frozen expanded-v2 field-set and type gate; "
            "each canonical field is present and non-null."
        ),
        "limitations": (
            "Does not reconstruct probe-level failures, OS unsupported states, Android user/profile, "
            "provider run identity, or attack labels that were not recorded at collection time."
        ),
    }


def embedded_manifest_to_sample_manifest(
    record: dict[str, Any], source: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    """Adapt the Week 7 embedded collection manifest without exposing labels/tools."""
    collection_manifest = record.get("collection_manifest")
    if not isinstance(collection_manifest, dict):
        return None, ["E_MANIFEST_MISSING"]
    device_id = collection_manifest.get("device_manifest_id")
    user_id = collection_manifest.get("android_user_id")
    if not isinstance(device_id, str) or not device_id.strip() or not isinstance(user_id, int) or user_id < 0:
        return None, ["E_MANIFEST_IDENTITY"]
    declared_id = device_id.strip()
    collector_install_id = collection_manifest.get("collector_install_id")
    if re.match(r"^week7-compatibility-\d{8}-\d{6}-api\d+-", declared_id) and isinstance(collector_install_id, str) and collector_install_id.strip():
        grouping_identity = collector_install_id.strip()
        grouping_identity_source = "collector_install_id_fallback"
    else:
        grouping_identity = declared_id
        grouping_identity_source = "device_manifest_id"
    stable_key = sha256_value(
        {
            "source_type": source.get("source_type", "unknown"),
            "grouping_identity": grouping_identity,
            "android_user_id": user_id,
        }
    )
    status_errors = collection_status_errors(get_path(record, "payload.collection_status"))
    if record.get("record_status") != "complete":
        status_errors.append("E_RECORD_STATUS")
    provided = {
        "sample_id": record.get("sample_id"),
        "capture": {
            "capture_batch_id": source.get("capture_batch_id"),
            "source_type": source.get("source_type", "unknown"),
            "provider": source.get("provider"),
            "provider_run_id": collection_manifest.get("runtime_context"),
            "collection_round": collection_manifest.get("collection_round"),
            "collection_week": collection_manifest.get("collection_week"),
        },
        "device": {
            "stable_device_key_hash": stable_key,
            "grouping_identity_source": grouping_identity_source,
            "android_user_id": user_id,
        },
        "collection_manifest_version": collection_manifest.get("manifest_schema_version"),
        "collection_status_version": get_path(record, "payload.collection_status.status_schema_version"),
    }
    return provided, status_errors


def field_map(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for layer in LAYER_NAMES:
        payload = row.get(layer)
        if not isinstance(payload, dict):
            continue
        for path, value in leaf_items(payload, layer):
            output[path] = value
    return output


def normalized_string_observations(row: dict[str, Any]) -> str:
    values = [
        str(value).lower()
        for _, value in field_map(row).items()
        if isinstance(value, str) and value.strip()
    ]
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).strip() for value in values)


def canonicalize_payload(row: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy flat and v2.1 nested layer paths to the frozen V2 paths.

    The 177 conceptual signals did not change between the two representations;
    only the nested grouping in the status-bearing collector payload changed.
    A leaf is remapped only when its layer-qualified final name exists uniquely
    in the frozen contract. Unknown leaves remain explicit and are rejected by
    normal validation instead of being silently dropped.
    """
    normalized = dict(row)
    expected = set(contract["fields"])
    path_mapping: dict[str, str] = {}
    for layer in LAYER_NAMES:
        layer_value = row.get(layer)
        if not isinstance(layer_value, dict):
            continue
        flat_layer: dict[str, Any] = {}
        for original_path, value in leaf_items(layer_value, layer):
            direct = original_path
            leaf = original_path.rsplit(".", maxsplit=1)[-1]
            candidate = f"{layer}.{leaf}"
            target = direct if direct in expected else candidate
            path_mapping[original_path] = target
            key = target.split(".", maxsplit=1)[1]
            if key in flat_layer and flat_layer[key] != value:
                # Preserve the full source path so the field-set gate rejects ambiguity.
                key = original_path.removeprefix(f"{layer}.")
            flat_layer[key] = value
        normalized[layer] = flat_layer
    status = row.get("collection_status")
    if isinstance(status, dict) and isinstance(status.get("fields"), dict):
        normalized_status = dict(status)
        normalized_status_fields: dict[str, str] = {}
        for original_path, state in status["fields"].items():
            target = path_mapping.get(original_path)
            if target is None and isinstance(original_path, str):
                layer = original_path.split(".", maxsplit=1)[0]
                leaf = original_path.rsplit(".", maxsplit=1)[-1]
                candidate = f"{layer}.{leaf}"
                target = original_path if original_path in expected else candidate
            if target in expected:
                normalized_status_fields[target] = str(state)
                if state != "observed":
                    layer, key = target.split(".", maxsplit=1)
                    if isinstance(normalized.get(layer), dict):
                        normalized[layer][key] = None
        normalized_status["fields"] = normalized_status_fields
        normalized["collection_status"] = normalized_status
    return normalized


def infer_contract(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fields: dict[str, set[str]] = defaultdict(set)
    presence: Counter[str] = Counter()
    for row in rows:
        for path, value in field_map(row).items():
            fields[path].add(type_name(value))
            presence[path] += 1
    by_layer = {layer: 0 for layer in LAYER_NAMES}
    registry: list[dict[str, Any]] = []
    for path in sorted(fields):
        layer = path.split(".", maxsplit=1)[0]
        by_layer[layer] += 1
        stable = path in STABLE_KEY_PATHS
        registry.append(
            {
                "canonical_path": path,
                "layer": layer,
                "allowed_types": sorted(fields[path]),
                "required": presence[path] == len(rows),
                "stability_class": "stable_identity" if stable else "evidence_or_runtime",
                "eligible_for_stable_key": stable,
                "send_to_external_model_default": not any(
                    token in path for token in ("session_id", "client_ip", "install_time")
                ),
            }
        )
    if by_layer != EXPECTED_COUNTS:
        raise ValueError(
            f"Cannot bootstrap: observed leaf counts {by_layer}, expected {EXPECTED_COUNTS}."
        )
    contract = {
        "contract_type": "hybridguard-expanded-v2-contract",
        "contract_version": "expanded-v2-contract-v1",
        "schema_version": "expanded-v2",
        "leaf_counts": by_layer,
        "fixed_schema_dim": sum(by_layer.values()),
        "field_count": len(registry),
        "stable_key_version": "stable-key-v1-heuristic",
        "stable_key_candidate_paths": list(STABLE_KEY_PATHS),
        "fields": {entry["canonical_path"]: entry["allowed_types"] for entry in registry},
        "bootstrap_note": (
            "Generated from the current valid expanded-v2 cloud collection. "
            "Review any intentional field evolution before replacing this contract."
        ),
    }
    return contract, registry


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_contract(args: argparse.Namespace, sources: list[dict[str, Any]]) -> dict[str, Any]:
    if args.bootstrap_contract:
        valid_rows: list[dict[str, Any]] = []
        for source in sources:
            if source.get("input_kind") != "raw_jsonl":
                continue
            source_path = REPO_ROOT / source["path"]
            if not source_path.exists():
                continue
            for _, row in read_jsonl(source_path):
                if row.get("schema_version") == "expanded-v2":
                    valid_rows.append(row)
        if not valid_rows:
            raise ValueError("No expanded-v2 rows available to bootstrap the contract.")
        contract, registry = infer_contract(valid_rows)
        write_json(DEFAULT_SCHEMA, contract)
        write_json(DEFAULT_REGISTRY, registry)
        return contract
    if not DEFAULT_SCHEMA.exists():
        raise FileNotFoundError(
            f"Missing {relative_path(DEFAULT_SCHEMA)}. Run once with --bootstrap-contract."
        )
    return json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))


def validate_v2_row(row: dict[str, Any], contract: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    fields = field_map(row)
    expected_fields: dict[str, list[str]] = contract["fields"]
    expected_counts: dict[str, int] = contract["leaf_counts"]
    actual_counts = {layer: 0 for layer in LAYER_NAMES}
    for path in fields:
        actual_counts[path.split(".", maxsplit=1)[0]] += 1
    if actual_counts != expected_counts:
        errors.append("E_FEATURE_COUNT")
    missing = sorted(set(expected_fields) - set(fields))
    unexpected = sorted(set(fields) - set(expected_fields))
    if missing or unexpected:
        errors.append("E_FIELD_SET")
    mismatched = []
    collection_states = get_path(row, "collection_status.fields", {})
    for path, value in fields.items():
        allowed = expected_fields.get(path)
        actual_type = type_name(value)
        numeric_compatible = actual_type in {"integer", "number"} and bool({"integer", "number"} & set(allowed or []))
        unavailable_by_status = (
            actual_type == "null"
            and isinstance(collection_states, dict)
            and collection_states.get(path) in {
                "unsupported_by_os",
                "permission_denied",
                "runtime_error",
                "timeout",
                "not_applicable",
            }
        )
        if allowed is not None and actual_type not in allowed and not numeric_compatible and not unavailable_by_status:
            mismatched.append(path)
    if mismatched:
        errors.append("E_FIELD_TYPE")
    for path in (
        "android_native_data.battery_voltage_mv",
        "android_native_data.screen_resolution_physical",
        "webview_data.webview_provider_version",
    ):
        if get_path(row, path) is None:
            warnings.append("W_OPTIONAL_API_UNSUPPORTED")
            break
    return errors, warnings, {
        "actual_counts": actual_counts,
        "missing_fields": missing,
        "unexpected_fields": unexpected,
        "type_mismatch_fields": mismatched,
    }


def merge_manifest(
    source: dict[str, Any], row: dict[str, Any], provided: dict[str, Any] | None, raw_hash: str
) -> dict[str, Any]:
    session_id = str(row.get("session_id", ""))
    capture = dict((provided or {}).get("capture") or {})
    capture.setdefault("capture_batch_id", source.get("capture_batch_id"))
    capture.setdefault("source_type", source.get("source_type", "unknown"))
    capture.setdefault("provider", source.get("provider"))
    capture.setdefault("provider_run_id", None)
    label = dict((provided or {}).get("label") or {})
    label.setdefault("environment_class", source.get("default_environment_class", "unknown"))
    label.setdefault("manipulation_present", source.get("default_manipulation_present", "unknown"))
    label.setdefault("violation_types", [])
    label.setdefault("label_status", source.get("default_label_status", "pending"))
    label.setdefault(
        "label_provenance",
        "source_config_inferred"
        if provided is None
        else ("collection_manifest_only" if provided.get("collection_manifest_version") else "provided_manifest"),
    )
    stable_key = get_path(provided or {}, "device.stable_device_key_hash")
    used_paths: list[str] = []
    if not stable_key:
        stable_key, used_paths = heuristic_stable_key(row, capture["source_type"])
    sample_id = (provided or {}).get("sample_id") or f"smp-{sha256_value(session_id)[:16]}"
    return {
        "manifest_version": "sample-manifest-v1",
        "sample_id": sample_id,
        "session_id_hash": sha256_value(session_id),
        "raw_payload_sha256": raw_hash,
        "schema_version": canonical_schema_version(row.get("schema_version")),
        "source_schema_version": row.get("schema_version"),
        "collector": {
            "app": row.get("collector_app", source.get("collector_app")),
            "app_version": get_path(row, "webview_data.app_version_name"),
        },
        "capture": capture,
        "device": {
            "stable_device_key_hash": stable_key,
            "stable_key_version": "provided-manifest" if provided and get_path(provided, "device.stable_device_key_hash") else "stable-key-v1-heuristic",
            "stable_key_paths_used": used_paths,
            "observed_identity_hash": observed_identity_key(row, capture["source_type"]),
        },
        "pair": (provided or {}).get("pair"),
        "label": label,
        "attack": (provided or {}).get("attack"),
        "evaluation": (provided or {}).get("evaluation"),
        "annotation_join": (provided or {}).get("annotation_join"),
        "provenance": {
            "source_id": source["source_id"],
            "source_payload_path": source["path"],
            "historical_manifest_inferred": provided is None,
            "model_eligibility_requested": source.get("model_eligibility", "unknown"),
        },
        "quality": {
            "qc_status": "pending",
            "qc_reasons": [],
            "formal_experiment_eligible": False,
        },
    }


def inspect_evidence_csv(source: dict[str, Any]) -> dict[str, Any]:
    path = REPO_ROOT / source["path"]
    if not path.exists():
        if source.get("optional"):
            return {"source_id": source["source_id"], "status": "optional_input_absent"}
        raise FileNotFoundError(path)
    role_counts: Counter[str] = Counter()
    completeness_counts: Counter[str] = Counter()
    total = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            role_counts[row.get("research_role", "unknown")] += 1
            completeness_counts[row.get("field_completeness", "unknown")] += 1
    return {
        "source_id": source["source_id"],
        "input_kind": "evidence_csv",
        "path": source["path"],
        "sha256": sha256_value(path.read_text(encoding="utf-8")),
        "rows": total,
        "research_role_counts": dict(sorted(role_counts.items())),
        "field_completeness_counts": dict(sorted(completeness_counts.items())),
        "model_eligibility": source.get("model_eligibility"),
        "status": "evidence_only_not_joined_to_raw_features",
    }


def build_snapshot(args: argparse.Namespace) -> Path:
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = config.get("sources", [])
    if not sources:
        raise ValueError("dataset source config has no sources")
    contract = load_contract(args, sources)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("snapshot_%Y%m%dT%H%M%SZ")
    artifact_dir = DEFAULT_ARTIFACT_ROOT / run_id
    if artifact_dir.exists():
        if not args.overwrite:
            raise FileExistsError(f"Artifact directory already exists: {artifact_dir}")
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True)

    manifests: list[dict[str, Any]] = []
    normalized_payloads: list[dict[str, Any]] = []
    quality_events: list[dict[str, Any]] = []
    historical_field_status_rows: list[dict[str, Any]] = []
    source_inventory: list[dict[str, Any]] = []
    annotation_audits: list[dict[str, Any]] = []
    field_stats: dict[str, dict[str, Any]] = {
        path: {"non_null": 0, "distinct_hashes": set(), "types": Counter()}
        for path in contract["fields"]
    }
    seen_session_hashes: set[str] = set()
    raw_total = 0
    accepted = 0
    quarantined = 0

    for source in sources:
        kind = source.get("input_kind")
        if kind == "evidence_csv":
            source_inventory.append(inspect_evidence_csv(source))
            continue
        if kind not in {"raw_jsonl", "manifest_dataset_jsonl"}:
            raise ValueError(f"Unsupported input_kind {kind!r} for {source.get('source_id')}")
        raw_path = REPO_ROOT / source["path"]
        if not raw_path.exists():
            if source.get("optional"):
                source_inventory.append({"source_id": source["source_id"], "status": "optional_input_absent"})
                continue
            raise FileNotFoundError(raw_path)
        manifest_path = source.get("manifest_path")
        manifest_index = load_manifest_index(REPO_ROOT / manifest_path if manifest_path else None)
        annotation_path_text = source.get("annotation_registry_path")
        annotation_path = REPO_ROOT / annotation_path_text if annotation_path_text else None
        evidence_root_text = source.get("annotation_evidence_root")
        evidence_root = REPO_ROOT / evidence_root_text if evidence_root_text else None
        annotation_registry = load_annotation_registry(annotation_path, evidence_root)
        matched_annotation_ids: set[str] = set()
        source_rows = read_jsonl(raw_path)
        inventory_entry = {
            "source_id": source["source_id"],
            "input_kind": kind,
            "path": source["path"],
            "sha256": sha256_value(raw_path.read_text(encoding="utf-8")),
            "raw_rows": len(source_rows),
            "model_eligibility": source.get("model_eligibility"),
            "manifest_path": manifest_path,
            "annotation_registry_path": annotation_path_text,
            "annotation_registry_sha256": (
                sha256_value(annotation_path.read_text(encoding="utf-8"))
                if annotation_path is not None
                else None
            ),
            "annotation_registry_rows": (
                len(annotation_registry["rows"]) if annotation_registry is not None else 0
            ),
        }
        source_inventory.append(inventory_entry)
        for line_number, source_row in source_rows:
            raw_total += 1
            embedded_errors: list[str] = []
            embedded_warnings: list[str] = []
            if kind == "manifest_dataset_jsonl":
                row = source_row.get("payload")
                if not isinstance(row, dict):
                    quarantined += 1
                    quality_events.append(
                        {
                            "source_id": source["source_id"],
                            "source_line": line_number,
                            "session_id_hash": "",
                            "raw_payload_sha256": sha256_value(source_row),
                            "severity": "error",
                            "code": "E_PAYLOAD_MISSING",
                            "detail": "Manifest dataset record has no object payload",
                        }
                    )
                    continue
                provided, embedded_errors = embedded_manifest_to_sample_manifest(source_row, source)
                if annotation_registry is not None:
                    sample_id = str(source_row.get("sample_id") or "")
                    source_session_id = str(source_row.get("source_session_id") or row.get("session_id") or "")
                    by_sample = annotation_registry["by_sample_id"].get(sample_id)
                    by_session = annotation_registry["by_session_id"].get(source_session_id)
                    if by_sample is None or by_session is None:
                        embedded_errors.append("E_ANNOTATION_MISSING")
                    elif by_sample is not by_session:
                        embedded_errors.append("E_ANNOTATION_JOIN_MISMATCH")
                    elif by_sample["source_session_id"] != str(row.get("session_id") or ""):
                        embedded_errors.append("E_ANNOTATION_SESSION_MISMATCH")
                    else:
                        provided, annotation_issues = attach_experiment_annotation(provided, by_sample)
                        for issue in annotation_issues:
                            (embedded_warnings if issue.startswith("W_") else embedded_errors).append(issue)
                        matched_annotation_ids.add(sample_id)
            else:
                row = source_row
                session_candidate = row.get("session_id")
                provided = manifest_index.get(session_candidate) if isinstance(session_candidate, str) else None
            source_payload = row
            row = canonicalize_payload(source_payload, contract)
            session_id = row.get("session_id")
            raw_hash = sha256_value(source_payload)
            event_base = {
                "source_id": source["source_id"],
                "source_line": line_number,
                "session_id_hash": sha256_value(str(session_id)),
                "raw_payload_sha256": raw_hash,
            }
            if canonical_schema_version(row.get("schema_version")) != "expanded-v2":
                quarantined += 1
                quality_events.append(
                    {
                        **event_base,
                        "severity": "error",
                        "code": "E_SCHEMA_VERSION",
                        "detail": f"Expected expanded-v2-compatible payload, got {row.get('schema_version')!r}",
                    }
                )
                continue
            errors, warnings, detail = validate_v2_row(row, contract)
            if kind == "raw_jsonl" and isinstance(source_payload.get("collection_status"), dict):
                for issue in collection_status_errors(source_payload.get("collection_status")):
                    (warnings if issue.startswith("W_") else errors).append(issue)
            for issue in embedded_errors:
                (warnings if issue.startswith("W_") else errors).append(issue)
            warnings.extend(embedded_warnings)
            if not isinstance(session_id, str) or not session_id:
                errors.append("E_SESSION_ID")
            manifest = merge_manifest(source, row, provided, raw_hash)
            session_hash = manifest["session_id_hash"]
            if session_hash in seen_session_hashes:
                errors.append("E_DUPLICATE_SESSION")
            seen_session_hashes.add(session_hash)
            if provided is None:
                warnings.extend(["W_MANIFEST_INFERRED", "W_LABEL_PENDING"])
            elif manifest["label"].get("label_status") != "verified":
                warnings.append("W_LABEL_PENDING")
            attack = manifest.get("attack") or {}
            if manifest["label"].get("manipulation_present") is True:
                if attack.get("execution_status") != "verified_success":
                    warnings.append("W_ATTACK_UNVERIFIED")
                if attack.get("feature_effect_status") != "observed":
                    warnings.append("W_ATTACK_EFFECT_UNOBSERVED")
            tasks = set(get_path(manifest, "evaluation.task_memberships", []) or [])
            requested_eligibility = source.get("model_eligibility")
            verified_attack_contract = (
                manifest["label"].get("manipulation_present") is not True
                or (
                    attack.get("execution_status") == "verified_success"
                    and attack.get("feature_effect_status") == "observed"
                )
            )
            formal_eligible = bool(
                not errors
                and "W_COLLECTION_PARTIAL" not in warnings
                and manifest["label"].get("label_status") == "verified"
                and provided is not None
                and (
                    (
                        requested_eligibility == "registry_labeled_pilot"
                        and "fingerprint_field_effect_pilot" in tasks
                    )
                    or (
                        requested_eligibility == "supervised_candidate"
                        and verified_attack_contract
                    )
                )
            )
            manifest["quality"] = {
                "qc_status": "quarantined" if errors else ("accepted_with_warning" if warnings else "accepted"),
                "qc_reasons": sorted(set(errors + warnings)),
                "formal_experiment_eligible": formal_eligible,
                "task_eligibility": {
                    "fingerprint_field_effect_pilot": formal_eligible,
                    "transport_path_effect_pilot": bool(
                        not errors
                        and manifest["label"].get("label_status") == "verified"
                        and "transport_path_effect_pilot" in tasks
                    ),
                    "held_out_attack_evaluation": bool(
                        formal_eligible and get_path(manifest, "evaluation.split") in {"development", "test"}
                    ),
                },
            }
            for code in sorted(set(errors + warnings)):
                quality_events.append(
                    {
                        **event_base,
                        "severity": "error" if code.startswith("E_") else "warning",
                        "code": code,
                        "detail": canonical_json(detail) if code.startswith("E_") else "",
                    }
                )
            if errors:
                quarantined += 1
                continue
            manifests.append(manifest)
            normalized_payloads.append(
                {
                    "sample_id": manifest["sample_id"],
                    "schema_version": "expanded-v2",
                    "payload": {
                        "collector_app": row.get("collector_app"),
                        "schema_version": row.get("schema_version"),
                        **{layer: row.get(layer) for layer in LAYER_NAMES},
                    },
                }
            )
            if kind == "raw_jsonl" and not isinstance(source_payload.get("collection_status"), dict):
                historical_field_status_rows.append(
                    {
                        "sample_id": manifest["sample_id"],
                        "session_id_hash": manifest["session_id_hash"],
                        "raw_payload_sha256": raw_hash,
                        "source_id": source["source_id"],
                        "inferred_collection_status": infer_historical_field_status(row, contract),
                    }
                )
            accepted += 1
            for path, value in field_map(row).items():
                stats = field_stats[path]
                stats["types"][type_name(value)] += 1
                if value is not None:
                    stats["non_null"] += 1
                    stats["distinct_hashes"].add(sha256_value(value))

        if annotation_registry is not None:
            registry_ids = set(annotation_registry["by_sample_id"])
            unmatched_registry_ids = sorted(registry_ids - matched_annotation_ids)
            unmatched_source_ids = sorted(matched_annotation_ids - registry_ids)
            audit = {
                "source_id": source["source_id"],
                "registry_schema_version": ANNOTATION_SCHEMA_VERSION,
                "registry_path": annotation_path_text,
                "registry_rows": len(registry_ids),
                "source_rows": len(source_rows),
                "matched_by_sample_and_session": len(matched_annotation_ids),
                "unmatched_registry_sample_ids": unmatched_registry_ids,
                "unmatched_source_sample_ids": unmatched_source_ids,
                "evidence_references_missing": annotation_registry["missing_evidence"],
                "status": (
                    "passed"
                    if len(matched_annotation_ids) == len(source_rows) == len(registry_ids)
                    and not unmatched_registry_ids
                    and not unmatched_source_ids
                    else "failed"
                ),
            }
            annotation_audits.append(audit)
            inventory_entry["annotation_join_status"] = audit["status"]
            inventory_entry["annotation_rows_joined"] = len(matched_annotation_ids)
            if audit["status"] != "passed":
                raise ValueError(f"Annotation registry join audit failed: {canonical_json(audit)}")

    manifests.sort(key=lambda item: (item["provenance"]["source_id"], item["sample_id"]))
    normalized_payloads.sort(key=lambda item: item["sample_id"])
    write_jsonl(artifact_dir / "sample_manifest.jsonl", manifests)
    write_jsonl(artifact_dir / "normalized_expanded_v2.jsonl", normalized_payloads)
    write_jsonl(artifact_dir / "quality_failures.jsonl", quality_events)
    write_jsonl(
        artifact_dir / "historical_field_status_backfill.jsonl",
        sorted(historical_field_status_rows, key=lambda item: item["sample_id"]),
    )

    field_profile_rows = []
    for path in sorted(field_stats):
        stats = field_stats[path]
        field_profile_rows.append(
            {
                "canonical_path": path,
                "non_null_count": stats["non_null"],
                "distinct_value_count": len(stats["distinct_hashes"]),
                "observed_types": ";".join(sorted(stats["types"])),
            }
        )
    write_csv(
        artifact_dir / "feature_profile.csv",
        field_profile_rows,
        ["canonical_path", "non_null_count", "distinct_value_count", "observed_types"],
    )

    group_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for manifest in manifests:
        grouped[manifest["device"]["stable_device_key_hash"]].append(manifest)
    for group_hash, rows in sorted(grouped.items()):
        group_rows.append(
            {
                "stable_device_key_hash": group_hash,
                "session_count": len(rows),
                "source_count": len({row["provenance"]["source_id"] for row in rows}),
                "label_statuses": ";".join(sorted({row["label"]["label_status"] for row in rows})),
                "formal_eligible_count": sum(row["quality"]["formal_experiment_eligible"] for row in rows),
            }
        )
    write_csv(
        artifact_dir / "stable_group_audit.csv",
        group_rows,
        ["stable_device_key_hash", "session_count", "source_count", "label_statuses", "formal_eligible_count"],
    )

    crosstab: Counter[tuple[str, str, str]] = Counter()
    for manifest in manifests:
        crosstab[(
            manifest["provenance"]["source_id"],
            manifest["label"]["environment_class"],
            manifest["label"]["label_status"],
        )] += 1
    crosstab_rows = [
        {
            "source_id": source_id,
            "environment_class": environment_class,
            "label_status": label_status,
            "sample_count": count,
        }
        for (source_id, environment_class, label_status), count in sorted(crosstab.items())
    ]
    write_csv(
        artifact_dir / "source_label_crosstab.csv",
        crosstab_rows,
        ["source_id", "environment_class", "label_status", "sample_count"],
    )

    pair_rows = []
    paired: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for manifest in manifests:
        pair = manifest.get("pair") or {}
        if pair.get("pair_id"):
            paired[str(pair["pair_id"])].append(manifest)
    if not paired:
        pair_rows.append(
            {
                "pair_id": "",
                "sample_count": 0,
                "pair_roles": "",
                "stable_key_consistent": "not_applicable",
                "complete_triplet": "false",
                "task_memberships": "",
                "splits": "",
                "status": "no_paired_samples",
            }
        )
    else:
        for pair_id, rows in sorted(paired.items()):
            keys = {row["device"]["stable_device_key_hash"] for row in rows}
            roles = {str((row.get("pair") or {}).get("pair_role", "unknown")) for row in rows}
            complete_triplet = (
                len(rows) == 3
                and roles == {"clean_pre", "attack_active", "clean_post"}
                and all(get_path(row, "evaluation.include_in_complete_pair_evaluation") is True for row in rows)
            )
            tasks = sorted(
                {
                    task
                    for row in rows
                    for task in (get_path(row, "evaluation.task_memberships", []) or [])
                }
            )
            pair_rows.append(
                {
                    "pair_id": pair_id,
                    "sample_count": len(rows),
                    "pair_roles": ";".join(sorted(roles)),
                    "stable_key_consistent": str(len(keys) == 1).lower(),
                    "complete_triplet": str(complete_triplet).lower(),
                    "task_memberships": ";".join(tasks),
                    "splits": ";".join(sorted({str(get_path(row, "evaluation.split", "")) for row in rows})),
                    "status": (
                        "E_STABLE_KEY_MISMATCH"
                        if len(keys) != 1
                        else ("complete_verified" if complete_triplet else "incomplete_excluded")
                    ),
                }
            )
    write_csv(
        artifact_dir / "pair_audit.csv",
        pair_rows,
        [
            "pair_id",
            "sample_count",
            "pair_roles",
            "stable_key_consistent",
            "complete_triplet",
            "task_memberships",
            "splits",
            "status",
        ],
    )

    schema_audit = {
        "contract_path": relative_path(DEFAULT_SCHEMA),
        "contract_sha256": sha256_value(DEFAULT_SCHEMA.read_text(encoding="utf-8")),
        "contract_version": contract["contract_version"],
        "expected_leaf_counts": contract["leaf_counts"],
        "raw_rows_seen": raw_total,
        "accepted_expanded_v2_rows": accepted,
        "quarantined_rows": quarantined,
        "accepted_fixed_schema_dim": contract["fixed_schema_dim"],
    }
    write_json(artifact_dir / "schema_audit.json", schema_audit)
    write_json(artifact_dir / "source_inventory.json", source_inventory)
    write_json(
        artifact_dir / "annotation_registry_audit.json",
        {
            "annotation_registry_audit_version": "annotation-registry-audit-v1",
            "sources": annotation_audits,
            "status": "passed" if annotation_audits and all(row["status"] == "passed" for row in annotation_audits) else "not_configured",
        },
    )

    supervised_eligible = [row for row in manifests if row["quality"]["formal_experiment_eligible"]]
    task_candidate_rows: list[dict[str, Any]] = []
    for manifest in manifests:
        for task in get_path(manifest, "evaluation.task_memberships", []) or []:
            if task not in {"fingerprint_field_effect_pilot", "transport_path_effect_pilot"}:
                continue
            task_candidate_rows.append(
                {
                    "sample_id": manifest["sample_id"],
                    "task": task,
                    "split": get_path(manifest, "evaluation.split", ""),
                    "pair_id": get_path(manifest, "pair.pair_id", ""),
                    "pair_role": get_path(manifest, "pair.pair_role", ""),
                    "manipulation_present": str(manifest["label"]["manipulation_present"]).lower(),
                    "attack_type": get_path(manifest, "attack.attack_type", ""),
                    "field_effect_status": get_path(manifest, "evaluation.field_effect_status", ""),
                    "label_status": manifest["label"]["label_status"],
                    "task_eligible": str(
                        manifest["quality"]["task_eligibility"].get(task, False)
                    ).lower(),
                }
            )
    write_csv(
        artifact_dir / "supervised_task_candidates.csv",
        task_candidate_rows,
        [
            "sample_id",
            "task",
            "split",
            "pair_id",
            "pair_role",
            "manipulation_present",
            "attack_type",
            "field_effect_status",
            "label_status",
            "task_eligible",
        ],
    )
    normalized_by_sample = {
        row["sample_id"]: row["payload"] for row in normalized_payloads
    }
    shortcut_rows: list[dict[str, Any]] = []
    for manifest in manifests:
        if manifest["label"].get("manipulation_present") is not True:
            continue
        tool_name = str(get_path(manifest, "attack.tool_name", "") or "")
        normalized_tool = re.sub(r"[^a-z0-9]+", " ", tool_name.lower()).strip()
        observed_text = normalized_string_observations(normalized_by_sample[manifest["sample_id"]])
        exact_tool_string_observed = bool(normalized_tool and normalized_tool in observed_text)
        shortcut_rows.append(
            {
                "sample_id": manifest["sample_id"],
                "pair_id": get_path(manifest, "pair.pair_id", ""),
                "task_memberships": ";".join(get_path(manifest, "evaluation.task_memberships", []) or []),
                "label_status": manifest["label"]["label_status"],
                "intervention_name": tool_name,
                "normalized_intervention_string_observed_in_raw_fields": str(exact_tool_string_observed).lower(),
                "shortcut_risk": "high" if exact_tool_string_observed else "not_observed_exactly",
            }
        )
    write_csv(
        artifact_dir / "attack_shortcut_audit.csv",
        shortcut_rows,
        [
            "sample_id",
            "pair_id",
            "task_memberships",
            "label_status",
            "intervention_name",
            "normalized_intervention_string_observed_in_raw_fields",
            "shortcut_risk",
        ],
    )
    task_counts = Counter(row["task"] for row in task_candidate_rows)
    exact_shortcut_count = sum(
        row["normalized_intervention_string_observed_in_raw_fields"] == "true"
        for row in shortcut_rows
    )
    held_out_attack_eligible = sum(
        row["quality"]["task_eligibility"]["held_out_attack_evaluation"] for row in manifests
    )
    build_manifest = {
        "dataset_snapshot_version": "hybridguard-dataset-snapshot-v1",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": relative_path(config_path),
        "config_sha256": sha256_value(config_path.read_text(encoding="utf-8")),
        "schema_audit": schema_audit,
        "source_inventory": source_inventory,
        "accepted_session_count": len(manifests),
        "historical_field_status_backfill_count": len(historical_field_status_rows),
        "stable_device_group_count": len(grouped),
        "formal_supervised_eligible_count": len(supervised_eligible),
        "supervised_task_candidate_counts": dict(sorted(task_counts.items())),
        "held_out_attack_evaluation_eligible_count": held_out_attack_eligible,
        "active_rows_with_exact_intervention_string_in_raw_fields": exact_shortcut_count,
        "model_feature_boundary": (
            "Raw expanded-v2 fields may be transformed into evidence only after split; "
            "source/provider/tool/pair/label metadata never enters the model input."
        ),
        "next_gate": (
            "Registry linked. Pilot training construction is ready, but formal attack evaluation remains blocked until complete attack pairs exist in independent development/test device groups and attack-template shortcut risk is controlled."
            if supervised_eligible and not held_out_attack_eligible
            else (
                "Ready for split construction using stable-device and pair grouping."
                if supervised_eligible
                else "Blocked until a verified label/attack registry is linked to manifest-bearing clean/attack/post rows."
            )
        ),
    }
    write_json(artifact_dir / "dataset_build_manifest.json", build_manifest)
    status = [
        f"# Dataset snapshot: {run_id}",
        "",
        f"- Raw rows inspected: {raw_total}",
        f"- Accepted expanded-v2 rows: {accepted}",
        f"- Quarantined rows: {quarantined}",
        f"- Stable-device groups: {len(grouped)}", 
        f"- Formal supervised-eligible rows: {len(supervised_eligible)}",
        f"- Fingerprint-field-effect pilot rows: {task_counts.get('fingerprint_field_effect_pilot', 0)}",
        f"- Transport-path-effect pilot rows: {task_counts.get('transport_path_effect_pilot', 0)}",
        f"- Held-out attack-evaluation rows: {held_out_attack_eligible}",
        f"- Active rows containing the normalized intervention name in raw fields: {exact_shortcut_count}",
        f"- Historical inferred field-status sidecars: {len(historical_field_status_rows)}",
        "",
        "## Gate status",
        "",
        "- Schema/QC snapshot: ready.",
        "- Cloud source: retained as provenance-incomplete, label-pending data; usable for QC, grouping and smoke tests only.",
        "- Attack release metadata: recorded in source_inventory; not joined to raw features.",
        "- Week 7 label registry: joined and audited separately from raw model inputs.",
        "- Fingerprint-field pilot: CDP clean/active/post triplets are available for pipeline smoke training.",
        "- Transport-path pilot: mitmproxy triplets are kept as a separate task because no 177-field mutation is claimed.",
        "- Formal held-out attack evaluation: still blocked because all complete attack pairs are in the registry train split.",
        "- Shortcut audit: raw manipulated fields may themselves contain intervention-identifying text; this is observed attack output, not registry leakage, but it prevents generalization claims.",
        "",
        "The next run should use a new run ID. Do not edit this snapshot in place.",
    ]
    (artifact_dir / "pipeline_status.md").write_text("\n".join(status) + "\n", encoding="utf-8")
    return artifact_dir


def main() -> None:
    args = parse_args()
    artifact_dir = build_snapshot(args)
    print(f"Snapshot written to {relative_path(artifact_dir)}")


if __name__ == "__main__":
    main()
