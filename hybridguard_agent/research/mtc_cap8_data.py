"""Read the existing P2 membership for the explicitly authorized MTC replay.

This loader does not relabel or rewrite P1/P2, run a model, or choose records by
their feature values. Historical split names remain descriptive metadata. The
normal-condition assessment is a new, separate research sidecar based on the
routine collection task, retained raw record, and known collection batch.
"""

from collections import Counter
import json
from pathlib import Path


DATA_ADAPTER_VERSION = "mtc-cap8-data-v1"
SUBSETS = (
    "primary_representative",
    "paired_repeat_observation",
    "reserve_app_only_177",
    "reserve_partial",
    "reserve_repeated_observations",
)
VIEWS = ("paired_244", "app_only_177", "partial", "repeated_observations", "quarantine")
NORMAL_BASIS_ID = "mtc-routine-collection-research-normal-v1"
KNOWN_BATCHES = {
    "hgbatch-v1-20260917T030653431925Z-6e31771d4a": 9,
    "hgbatch-v1-20260921T040430015520Z-14ed4645c6": 11,
}
TASK_REFS = (
    "deliverables/mtc_20260916/百度MTC采集操作流程说明.md",
    "deliverables/mtc_20260917/提测说明.md",
    "deliverables/mtc_20260921_https/提测说明.md",
)
HISTORICAL_SOURCE_COMMIT = "134201114a8a15a682bb41ee94c796d14e550c9e"


def _ref(path, root, line=None):
    try:
        result = str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        result = str(Path(path).resolve())
    return result if line is None else f"{result}:{line}"


def _read_json(path, issues):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("JSON root is not an object")
        return result
    except (OSError, ValueError) as error:
        issues.append({"path": str(path), "reason": f"{type(error).__name__}: {error}"})
        return {}


def _read_jsonl(path, issues, project=None):
    """Keep physical line numbers, including blank/malformed lines."""
    rows = {}
    try:
        with path.open("rb") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    row = json.loads(line.decode("utf-8"))
                    if not isinstance(row, dict):
                        raise ValueError("JSONL row is not an object")
                    rows[number] = {"row": project(row) if project else row, "error": None}
                except (ValueError, TypeError, AttributeError) as error:
                    reason = f"{type(error).__name__}: {error}"
                    rows[number] = {"row": None, "error": reason}
                    issues.append({"path": str(path), "line": number, "reason": reason})
    except OSError as error:
        issues.append({"path": str(path), "reason": f"{type(error).__name__}: {error}"})
    return rows


def _raw_metadata(row):
    payload = row.get("canonical_received_payload", {})
    if not isinstance(payload, dict):
        raise ValueError("raw canonical payload is not an object")
    manifest = payload.get("collection_manifest", {})
    diagnostics = payload.get("collection_diagnostics", {})
    if not isinstance(manifest, dict) or not isinstance(diagnostics, dict):
        raise ValueError("raw collection metadata is not an object")
    return {
        "session_id": row.get("session_id"),
        "receipt_id": row.get("receipt_id"),
        "payload_sha256": row.get("payload_sha256"),
        "collection_batch_id": row.get("collection_batch_id"),
        "collector_app": payload.get("collector_app"),
        "manifest": manifest,
        "diagnostics": diagnostics,
    }


def _normal_basis(observation, raw, closed_batches, docs_available, evidence_refs):
    reasons = []
    app = observation.get("app", {})
    if not isinstance(app, dict):
        app = {}
    batch = observation.get("collection_batch_id")
    if not docs_available:
        reasons.append("routine_collection_task_document_missing")
    if batch not in KNOWN_BATCHES:
        reasons.append("not_a_reviewed_routine_mtc_batch")
    if batch not in closed_batches:
        reasons.append("closed_batch_record_missing")
    if not raw:
        reasons.append("raw_app_record_unavailable")
    else:
        for key in ("session_id", "payload_sha256"):
            if not app.get(key) or app.get(key) != raw.get(key):
                reasons.append(f"raw_app_{key}_binding_mismatch")
        if raw.get("collection_batch_id") != batch:
            reasons.append("raw_batch_binding_mismatch")
        manifest = raw.get("manifest", {})
        if raw.get("collector_app") != "featureapp":
            reasons.append("unrecognized_collector_app")
        if manifest.get("collector_version_code") != KNOWN_BATCHES.get(batch):
            reasons.append("collector_version_does_not_match_reviewed_batch")
        if manifest.get("collection_protocol_version") != "featureapp-collection-protocol-v3":
            reasons.append("collection_protocol_not_reviewed")
        if manifest.get("web_probe_revision") != "expanded-web-67-v1":
            reasons.append("web_probe_revision_not_reviewed")
    supported = not reasons
    return {
        "status": "research_normal_condition_supported" if supported else "basis_insufficient",
        "supported": supported,
        "basis_id": NORMAL_BASIS_ID,
        "reasons": reasons or ["routine_mtc_task_and_matching_retained_raw_closed_batch"],
        "evidence_refs": evidence_refs,
        "scope": "routine_collection_without_research_target_fingerprint_tampering",
        "assessment_kind": "task_and_batch_research_basis_not_per_device_attestation",
    }


def load_mtc_replay_data(repo_root=None, p2_dir=None, snapshot_dir=None, freeze_dir=None):
    """Return records, inventory and read issues without dropping failed members.

    ``record['observation']`` is the unmodified historical P1 object, or None
    when its planned row cannot be read/bound. Metadata and normal_basis must
    not enter the predictor. Count denominators come from the readable P2
    registry; no hard-coded 891 target or replacement representative is used.
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    p2 = Path(p2_dir) if p2_dir is not None else root / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922"
    snapshot = Path(snapshot_dir) if snapshot_dir is not None else root / "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final"
    freeze = Path(freeze_dir) if freeze_dir is not None else root / "backend_server/collection_backups/mtc_final_20260922"
    issues = []
    registry_path = p2 / "sample_registry.jsonl"
    registry = _read_jsonl(registry_path, issues)
    manifest = _read_json(snapshot / "manifest.json", issues)
    views = {name: _read_jsonl(snapshot / f"{name}.jsonl", issues) for name in VIEWS}
    raw_path = freeze / "sources/raw_expanded_payloads.jsonl"
    raw_rows = _read_jsonl(raw_path, issues, _raw_metadata)
    batches_path = freeze / "sources/collection_batches.jsonl"
    batch_rows = _read_jsonl(batches_path, issues)
    closed_batches = {
        item["row"].get("collection_batch_id")
        for item in batch_rows.values()
        if item["row"] and item["row"].get("lifecycle_status") == "closed_cleanly"
    }
    docs_available = all((root / path).is_file() for path in TASK_REFS)
    records = []
    used_references = set()
    seen_ids = set()
    for registry_line, item in registry.items():
        p2_row = item["row"] or {}
        subset = p2_row.get("analysis_role", "unassigned_registry_error")
        sample_id = p2_row.get("sample_id", f"unreadable-p2-registry-line-{registry_line}")
        view, number = p2_row.get("source_view"), p2_row.get("source_line")
        source_path = snapshot / f"{view}.jsonl"
        errors = [item["error"]] if item["error"] else []
        if not isinstance(subset, str):
            errors.append("P2_analysis_role_not_a_string")
            subset = "unassigned_registry_error"
        if not isinstance(sample_id, str):
            errors.append("P2_sample_id_not_a_string")
            sample_id = f"unreadable-p2-registry-line-{registry_line}"
        if not isinstance(p2_row.get("profile", {}), dict):
            errors.append("P2_profile_not_an_object")
        if type(number) is not int or number < 1 or view not in VIEWS:
            errors.append("invalid_or_missing_P2_source_reference")
            source = {}
        else:
            source = views[view].get(number, {})
            if (view, number) in used_references:
                errors.append("duplicate_P2_source_reference")
            used_references.add((view, number))
        observation = source.get("row")
        if observation is None:
            errors.append(source.get("error") or "planned_source_row_missing_or_unreadable")
        else:
            if observation.get("sample_id") != sample_id:
                errors.append("P2_to_P1_sample_id_mismatch")
            if observation.get("dataset_view") != view:
                errors.append("P2_to_P1_view_mismatch")
            if observation.get("record_schema_version") != "hybridguard-mtc-observation-v2":
                errors.append("unsupported_P1_record_schema")
            if not isinstance(observation.get("features"), dict):
                errors.append("P1_features_not_an_object")
            for key in ("app", "source_refs", "profile", "qc", "field_status", "field_quality"):
                if not isinstance(observation.get(key), dict):
                    errors.append(f"P1_{key}_not_an_object")
            for side in ("app", "browser"):
                expected = p2_row.get(f"{side}_payload_sha256")
                side_data = observation.get(side, {})
                if expected and (not isinstance(side_data, dict) or side_data.get("payload_sha256") != expected):
                    errors.append(f"P2_to_P1_{side}_payload_binding_mismatch")
        if sample_id in seen_ids:
            errors.append("duplicate_P2_sample_id")
        seen_ids.add(sample_id)
        row = observation if observation and not errors else {}
        refs = row.get("source_refs", {})
        raw_number = refs.get("app_raw_line", p2_row.get("app_raw_line"))
        raw = raw_rows.get(raw_number, {}).get("row") if type(raw_number) is int else None
        raw_manifest = (raw or {}).get("manifest", {})
        app = row.get("app", {})
        metadata = {
            "source_view": view,
            "source_line": number,
            "source_path": _ref(source_path, root),
            "p2_registry_reference": _ref(registry_path, root, registry_line),
            "raw_app_reference": _ref(raw_path, root, raw_number) if raw_number else None,
            "raw_browser_reference": _ref(freeze / "sources/raw_browser_payloads.jsonl", root, refs["browser_raw_line"]) if refs.get("browser_raw_line") else None,
            "profile": p2_row.get("profile", {}) if isinstance(p2_row.get("profile", {}), dict) else {},
            "group_id": p2_row.get("group_id"),
            "split": p2_row.get("split"),
            "analysis_role": subset,
            "collection_batch_id": row.get("collection_batch_id"),
            "collector_version_code": app.get("collector_version_code"),
            "collector_version_name": app.get("collector_version_name"),
            "web_probe_revision": raw_manifest.get("web_probe_revision"),
            "record_schema_version": row.get("record_schema_version"),
            "historical_label_status": row.get("label_status"),
            "p2_label_status": p2_row.get("label_status"),
            "layers_without_observed_fields": row.get("qc", {}).get("layers_without_observed_fields", []),
            "runtime_context": raw_manifest.get("runtime_context"),
        }
        evidence_refs = [*TASK_REFS, _ref(batches_path, root)]
        if metadata["raw_app_reference"]:
            evidence_refs.append(metadata["raw_app_reference"])
        basis = _normal_basis(row, raw, closed_batches, docs_available, evidence_refs)
        if errors:
            issues.append({"sample_id": sample_id, "subset": subset, "reason": "; ".join(errors)})
        records.append({
            "subset": subset, "sample_id": sample_id,
            "observation": observation if not errors else None,
            "p2": p2_row, "metadata": metadata, "normal_basis": basis,
            "load_error": "; ".join(errors) if errors else None,
        })
    for view, rows in views.items():
        for number, item in rows.items():
            if (view, number) not in used_references:
                issues.append({"path": str(snapshot / f"{view}.jsonl"), "line": number,
                               "reason": "P1_row_not_referenced_by_readable_P2_registry"})
    by_subset = {}
    for subset in (*SUBSETS, *sorted({r["subset"] for r in records} - set(SUBSETS))):
        selected = [r for r in records if r["subset"] == subset]
        profiles = [r["metadata"]["profile"] for r in selected]
        combinations = {(p.get("manufacturer"), p.get("model"), p.get("android_release")) for p in profiles if p}
        by_subset[subset] = {
            "planned": len(selected),
            "readable": sum(r["load_error"] is None for r in selected),
            "load_failures": sum(r["load_error"] is not None for r in selected),
            "normal_basis_supported": sum(r["normal_basis"]["supported"] for r in selected),
            "model_os_combinations": len(combinations),
            "layers_missing_records": sum(bool(r["metadata"]["layers_without_observed_fields"]) for r in selected),
            "split_counts": dict(Counter(r["metadata"]["split"] for r in selected)),
        }
    inventory = {
        "data_adapter_version": DATA_ADAPTER_VERSION,
        "p2_registry": _ref(registry_path, root),
        "p2_registry_rows": len(registry),
        "p2_registry_invalid_rows": sum(item["row"] is None for item in registry.values()),
        "source_cutoff_utc": manifest.get("source_cutoff_utc"),
        "view_declared_counts": manifest.get("view_counts", {}),
        "view_physical_rows": {view: len(rows) for view, rows in views.items()},
        "view_readable_rows": {view: sum(item["row"] is not None for item in rows.values()) for view, rows in views.items()},
        "subsets": by_subset,
        "raw_app_rows": len(raw_rows),
        "raw_app_readable_rows": sum(item["row"] is not None for item in raw_rows.values()),
        "normal_basis_id": NORMAL_BASIS_ID,
        "issue_count": len(issues),
        "independent_physical_device_count": None,
        "evaluation_kind": "supplementary_replay_on_previously_used_mtc_observations",
    }
    return {"records": records, "inventory": inventory, "issues": issues}
