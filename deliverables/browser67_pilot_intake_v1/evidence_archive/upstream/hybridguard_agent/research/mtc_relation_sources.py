"""Bind one saved App acquisition to the relation experiment's field inputs.

Only the three App surfaces are transferred. Independent Browser observations,
labels, phases, triplets and device identifiers never enter the feature map.
Identity checks bind existing references; this is not a new integrity audit.
Missing fields retain their absence for a relation to return U, whereas an
unreadable record or mismatched session is an explicit FAILED transfer.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re

VERSION = "mtc-relation-source-binding-v1"
INPUT_SCHEMA_VERSION = "same-acquisition-app-fields-v1"
ROOT = Path(__file__).resolve().parents[2]
APP_ROOTS = ("android_native_data", "webview_data", "web_data")
APP_PREFIXES = tuple("app." + name + "." for name in APP_ROOTS)
COLLECTOR_SOURCES = {
    9: "134201114a8a15a682bb41ee94c796d14e550c9e",
    11: "134201114a8a15a682bb41ee94c796d14e550c9e",
    14: "bdd0b11a915b3bf5028bb3600c21e8b7b10a1f54",
}
STATUSES = {"observed", "unsupported_by_os", "permission_denied", "runtime_error",
            "timeout", "not_applicable"}


def _allowed(sample_ids, allowed_ids):
    ids = list(sample_ids)
    if any(type(s) is not str or not s for s in ids) or len(ids) != len(set(ids)):
        raise ValueError("INVALID_OR_DUPLICATE_REQUESTED_SAMPLE_ID")
    if not set(ids).issubset(set(allowed_ids)):
        raise ValueError("SAMPLE_OUTSIDE_ALLOWED_STAGE_IDS")
    return ids


def _result(binding, features=None, statuses=None, qualities=None, errors=()):
    errors = list(errors)
    return {"status": "FAILED" if errors else "OK", "errors": errors,
            "features": deepcopy(features or {}) if not errors else {},
            "field_status": deepcopy(statuses or {}) if not errors else {},
            "field_quality": deepcopy(qualities or {}) if not errors else {},
            "source_binding": {**deepcopy(binding), "binding_version": VERSION,
                               "input_schema_version": INPUT_SCHEMA_VERSION,
                               "binding_valid": not errors,
                               "same_app_record": not errors,
                               "web_fields_same_sync_probe": not errors}}


def _field_sessions(container, session):
    """Reject explicit contrary binding claims; never borrow another session."""
    if "field_session_ids" not in container:
        return []
    sessions = container["field_session_ids"]
    if type(sessions) is not dict:
        return ["FIELD_SESSION_BINDINGS_NOT_AN_OBJECT"]
    return ["FIELD_SESSION_BINDING_MISMATCH:" + str(key) for key, value in sessions.items()
            if (str(key).startswith(APP_PREFIXES) or str(key).startswith(tuple(n + "." for n in APP_ROOTS)))
            and value != session]


def _flatten(value, prefix):
    if type(value) is not dict:
        return {prefix: deepcopy(value)}
    return {key: item for name, child in value.items()
            for key, item in _flatten(child, prefix + "." + name).items()}


def _quality(field, value, status):
    # Same explicit field-status and legacy zero policy as the existing App177
    # adapter. No measured value, including a -1 sentinel, is replaced here.
    if type(status) is not str or status not in STATUSES:
        return None
    if status != "observed":
        return "source_unavailable"
    if (field.endswith((".device_memory", ".hardware_concurrency"))
            and type(value) in (int, float) and value == 0):
        return "ambiguous_sentinel"
    return "observed_value"


def bind_controlled_record(sample_id, reference, raw_record, *, raw_reference=None):
    """Bind one externally referenced raw archive row; do not use its labels."""
    binding = {"sample_id": sample_id, "mode": "controlled_raw_app",
               "raw_reference": raw_reference, "quality_policy": "explicit-status-and-legacy-zero-v1"}
    errors = []
    if type(reference) is not dict:
        return _result(binding, errors=["CONTROLLED_REFERENCE_NOT_AN_OBJECT"])
    session = reference.get("session_id")
    binding.update(session_id=session, app_session_id=session, source_ref=reference.get("source_ref"))
    if (reference.get("opaque_id") != sample_id or not isinstance(session, str)
            or not session or sample_id != "webgl1fresh-" + session):
        errors.append("CONTROLLED_SAMPLE_SESSION_REFERENCE_MISMATCH")
    if reference.get("observation_mode") != "raw_observation_v1":
        errors.append("CONTROLLED_REFERENCE_NOT_RAW_OBSERVATION_V1")
    if type(raw_record) is not dict:
        return _result(binding, errors=[*errors, "RAW_ARCHIVE_ROW_NOT_AN_OBJECT"])
    payload = raw_record.get("canonical_received_payload")
    if type(payload) is not dict:
        return _result(binding, errors=[*errors, "RAW_APP_PAYLOAD_NOT_AN_OBJECT"])
    if raw_record.get("session_id") != session or payload.get("session_id") != session:
        errors.append("RAW_APP_SESSION_BINDING_MISMATCH")
    if (raw_record.get("raw_payload_archive_schema_version") != "expanded-raw-payload-v1"
            or payload.get("schema_version") != "expanded-v2.2-status"
            or payload.get("collector_app") != "featureapp"):
        errors.append("UNSUPPORTED_RAW_APP_CONTRACT")
    manifest = payload.get("collection_manifest")
    if type(manifest) is not dict:
        errors.append("RAW_APP_MANIFEST_NOT_AN_OBJECT")
        manifest = {}
    if (reference.get("environment_group_id") is not None
            and manifest.get("device_manifest_id") != reference["environment_group_id"]):
        errors.append("RAW_APP_ENVIRONMENT_BINDING_MISMATCH")
    collector_version = manifest.get("collector_version_code")
    if type(collector_version) is not int or collector_version != 14:
        errors.append("UNSUPPORTED_CONTROLLED_COLLECTOR_VERSION")
    errors.extend(_field_sessions(payload, session))
    binding.update(receipt_id=raw_record.get("receipt_id"),
                   payload_id=raw_record.get("payload_sha256"),
                   collector_version_code=manifest.get("collector_version_code"),
                   collector_version_name=manifest.get("collector_version_name"),
                   web_probe_revision=manifest.get("web_probe_revision"),
                   collection_source_commit=COLLECTOR_SOURCES.get(collector_version) if type(collector_version) is int else None,
                   sync_probe_reference="web_probe/canonical_web_probe.js#getScreenFeatures")
    features = {}
    for name in APP_ROOTS:
        if name in payload and type(payload[name]) is not dict:
            errors.append("RAW_APP_SURFACE_NOT_AN_OBJECT:" + name)
        elif name in payload:
            features.update(_flatten(payload[name], "app." + name))
    collection_status = payload.get("collection_status", {})
    if type(collection_status) is not dict or type(collection_status.get("fields", {})) is not dict:
        return _result(binding, errors=[*errors, "RAW_APP_FIELD_STATUS_NOT_AN_OBJECT"])
    statuses = {"app." + k: deepcopy(v) for k, v in collection_status.get("fields", {}).items()
                if isinstance(k, str) and k.startswith(tuple(n + "." for n in APP_ROOTS))}
    qualities = {k: q for k, s in statuses.items()
                 if (q := _quality(k, features.get(k), s)) is not None}
    return _result(binding, features, statuses, qualities, errors)


def _archive_selected(path, sessions):
    """Deserialize only selected sessions, retaining physical line references.

    The saved expanded-raw-payload-v1 format puts the envelope session before
    canonical_received_payload. We inspect that envelope prefix to locate rows;
    held-out payload bodies are not deserialized as training-side records.
    """
    found = defaultdict(list)
    with Path(path).open("rb") as stream:
        for number, line in enumerate(stream, 1):
            prefix = line.split(b'"canonical_received_payload"', 1)[0]
            match = re.search(rb'"session_id"\s*:\s*"([^"\\]+)"', prefix)
            session = match[1].decode("utf-8") if match else None
            if session not in sessions:
                continue
            try:
                row = json.loads(line)
                found[session].append((number, row, None))
            except (ValueError, UnicodeError) as exc:
                found[session].append((number, None, "UNREADABLE_RAW_APP_ROW:" + type(exc).__name__))
    return found


def load_controlled_sources(sample_ids, *, allowed_ids, repo_root=None, prepared_dir=None):
    """Return every requested ID, including transfer failures; never fit/label."""
    ids = _allowed(sample_ids, allowed_ids)
    root = Path(repo_root or ROOT).resolve()
    prepared = Path(prepared_dir or root / "deliverables/webgl1_fresh_comparison_v1/prepared")
    references, groups, result = {}, defaultdict(list), {}
    for sample_id in ids:
        try:
            reference = json.loads((prepared / "evaluation" / (sample_id + ".json")).read_text())
            if type(reference) is not dict:
                raise ValueError("REFERENCE_NOT_AN_OBJECT")
            if type(reference.get("session_id")) is not str or not reference["session_id"]:
                raise ValueError("INVALID_REFERENCE_SESSION_ID")
            source = reference.get("source_ref")
            if not isinstance(source, str) or not source:
                raise ValueError("MISSING_RAW_SOURCE_REFERENCE")
            path = (root / source / "backend/raw_expanded_payloads.jsonl").resolve()
            if not path.is_relative_to(root):
                raise ValueError("RAW_SOURCE_OUTSIDE_REPOSITORY")
            references[sample_id] = reference
            groups[path].append(sample_id)
        except (OSError, ValueError) as exc:
            result[sample_id] = _result({"sample_id": sample_id, "mode": "controlled_raw_app"},
                                        errors=["UNREADABLE_CONTROLLED_REFERENCE:" + str(exc)])
    for path, members in groups.items():
        sessions = {references[s].get("session_id") for s in members}
        try:
            rows = _archive_selected(path, sessions)
            source_error = None
        except (OSError, UnicodeError) as exc:
            rows, source_error = {}, "UNREADABLE_RAW_APP_ARCHIVE:" + str(exc)
        for sample_id in members:
            matches = rows.get(references[sample_id].get("session_id"), [])
            if source_error or len(matches) != 1 or matches[0][2]:
                reason = source_error or ("RAW_APP_SESSION_NOT_UNIQUE" if len(matches) > 1 else
                                         "RAW_APP_SESSION_MISSING" if not matches else matches[0][2])
                result[sample_id] = _result({"sample_id": sample_id, "mode": "controlled_raw_app",
                                             "source_ref": str(path.relative_to(root))}, errors=[reason])
            else:
                number, raw, _ = matches[0]
                result[sample_id] = bind_controlled_record(sample_id, references[sample_id], raw,
                    raw_reference=str(path.relative_to(root)) + ":" + str(number))
    return {sid: result[sid] for sid in ids}


def bind_mtc_observation(observation, expected_sample_id, *, allowed_ids, expected_registry):
    """Use the saved P1 App fields, checked against their frozen P2 reference.

    P1 already stores raw App values/status/quality without imputation. Browser
    fields and their independent session are discarded, never used as fallback.
    Existing payload IDs are compared as references, not recomputed as hashes.
    """
    _allowed([expected_sample_id], allowed_ids)
    binding = {"sample_id": expected_sample_id, "mode": "mtc_p1_legacy_app",
               "quality_policy": "retained_p1_field_quality"}
    if type(observation) is not dict or type(expected_registry) is not dict:
        return _result(binding, errors=["MTC_OBSERVATION_OR_REGISTRY_NOT_AN_OBJECT"])
    errors = []
    if (observation.get("sample_id") != expected_sample_id
            or expected_registry.get("sample_id") != expected_sample_id):
        errors.append("MTC_SAMPLE_ID_BINDING_MISMATCH")
    if observation.get("record_schema_version") != "hybridguard-mtc-observation-v2":
        errors.append("UNSUPPORTED_MTC_OBSERVATION_SCHEMA")
    app, refs = observation.get("app"), observation.get("source_refs")
    if type(app) is not dict or type(refs) is not dict:
        return _result(binding, errors=[*errors, "MTC_APP_OR_SOURCE_REFERENCE_NOT_AN_OBJECT"])
    if type(app.get("session_id")) is not str or not app["session_id"]:
        errors.append("MTC_INVALID_APP_SESSION_ID")
    for registry_key, actual in (("app_session_id", app.get("session_id")),
                                 ("app_payload_sha256", app.get("payload_sha256")),
                                 ("app_raw_line", refs.get("app_raw_line")),
                                 ("source_view", observation.get("dataset_view"))):
        expected = expected_registry.get(registry_key)
        if expected is None or actual is None or actual != expected:
            errors.append("MTC_APP_BINDING_MISMATCH:" + registry_key)
    if type(refs.get("app_raw_line")) is not int or refs["app_raw_line"] < 1:
        errors.append("MTC_INVALID_APP_RAW_LINE")
    collector_version = app.get("collector_version_code")
    if type(collector_version) is not int or collector_version not in (9, 11):
        errors.append("UNSUPPORTED_MTC_COLLECTOR_VERSION")
    errors.extend(_field_sessions(observation, app.get("session_id")))
    binding.update(session_id=app.get("session_id"), app_session_id=app.get("session_id"),
                   receipt_id=app.get("receipt_id"),
                   payload_id=app.get("payload_sha256"), app_raw_line=refs.get("app_raw_line"),
                   source_view=expected_registry.get("source_view"),
                   source_line=expected_registry.get("source_line"),
                   collector_version_code=app.get("collector_version_code"),
                   collector_version_name=app.get("collector_version_name"),
                   collection_source_commit=COLLECTOR_SOURCES.get(collector_version) if type(collector_version) is int else None,
                   sync_probe_reference="web_probe/canonical_web_probe.js#getScreenFeatures")
    transfer = {}
    for key in ("features", "field_status", "field_quality"):
        value = observation.get(key)
        if type(value) is not dict:
            errors.append("MTC_FIELD_SECTION_NOT_AN_OBJECT:" + key)
            transfer[key] = {}
        else:
            transfer[key] = {k: deepcopy(v) for k, v in value.items()
                             if isinstance(k, str) and k.startswith(APP_PREFIXES)}
    return _result(binding, transfer["features"], transfer["field_status"],
                   transfer["field_quality"], errors)
