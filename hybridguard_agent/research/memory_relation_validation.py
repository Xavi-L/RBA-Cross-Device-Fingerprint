"""Frozen relation vs a Web-only control; no fitting or new model construction.

The memory-only batch has its own identity. It reuses the current raw payload
compiler without pretending to be part of the old webgl1fresh experiment.
"""
from copy import deepcopy
from functools import lru_cache
import importlib.util
import math
from pathlib import Path

from . import mtc_resource_relations as relation
from . import mtc_relation_sources as sources
from . import mtc_relation_candidates as extended
from . import mtc_reselection_candidates as base
from .rule_learning.contracts import cell

VERSION = "memory-relation-validation-v1"
ROOT = Path(__file__).resolve().parents[2]
WEB = relation.WEB_MEMORY
NATIVE = relation.NATIVE_MEMORY
TARGETS = (2, 4, 8, 16)


def state(value):
    return ("FAILED" if value.get("evaluation_status") != "OK" else
            "U" if not value.get("available") else "T" if value["value"] else "F")


def web8(record):
    """Only Web value/status/quality are read; even a missing Native is irrelevant."""
    if not isinstance(record, dict) or any(not isinstance(record.get(k), dict)
            for k in ("features", "field_status", "field_quality")):
        return cell("U", "WEB_MEMORY_INPUT_MISSING")
    if WEB not in record["features"]:
        return cell("U", "WEB_MEMORY_MISSING")
    value = record["features"][WEB]
    if record["field_status"].get(WEB) != "observed" or record["field_quality"].get(WEB) != "observed_value":
        return cell("U", "WEB_MEMORY_QUALITY_UNAVAILABLE")
    if type(value) not in (int, float) or not math.isfinite(value):
        return cell("U", "WEB_MEMORY_NOT_FINITE_NUMBER")
    if value <= 0:
        return cell("U", "WEB_MEMORY_NONPOSITIVE_OR_DEFAULT")
    return cell("T" if value > 8 else "F", "WEB_MEMORY_GT_8" if value > 8 else "WEB_MEMORY_LE_8")


def compare(record):
    # Acquisition/parse failures are separate from the Web-only predicate. A
    # missing Native operand alone never prevents R_WEB8 evaluation.
    if record.get("status") != "OK":
        measured = {name: cell("FAILED", "SOURCE_READ_OR_BINDING_FAILED") for name in ("R_REL", "R_WEB8")}
    else:
        measured = {"R_REL": relation.evaluate(record)[relation.MEMORY_ID], "R_WEB8": web8(record)}
    return {name: {**value, "state": state(value)} for name, value in measured.items()}


def bind_memory_batch(raw, *, session_id, source_reference, environment_id):
    """Explicit new v14 raw batch binding; no old ID/path allowlist relaxed."""
    binding = {"sample_id": "memoryonly-" + session_id, "app_session_id": session_id,
               "mode": VERSION, "raw_reference": source_reference}
    errors = []
    if not isinstance(raw, dict):
        return sources._result(binding, errors=["RAW_ROW_NOT_OBJECT"])
    payload = raw.get("canonical_received_payload")
    if not isinstance(payload, dict):
        return sources._result(binding, errors=["RAW_PAYLOAD_MISSING"])
    manifest = payload.get("collection_manifest", {})
    if not isinstance(manifest, dict):
        manifest = {}
    if (not session_id or raw.get("session_id") != session_id or payload.get("session_id") != session_id):
        errors.append("CURRENT_APP_SESSION_MISMATCH")
    if (raw.get("raw_payload_archive_schema_version") != "expanded-raw-payload-v1"
            or payload.get("schema_version") != "expanded-v2.2-status"
            or payload.get("collector_app") != "featureapp"
            or type(manifest.get("collector_version_code")) is not int
            or manifest["collector_version_code"] != 14):
        errors.append("UNSUPPORTED_MEMORY_BATCH_COLLECTOR")
    if not environment_id or manifest.get("device_manifest_id") != environment_id:
        errors.append("CURRENT_APP_ENVIRONMENT_MISMATCH")
    errors += sources._field_sessions(payload, session_id)
    features = {}
    for name in sources.APP_ROOTS:
        if name in payload:
            if not isinstance(payload[name], dict):
                errors.append("APP_SURFACE_NOT_OBJECT:" + name)
            else:
                features.update(sources._flatten(payload[name], "app." + name))
    statuses = payload.get("collection_status", {})
    if not isinstance(statuses, dict) or not isinstance(statuses.get("fields"), dict):
        errors.append("FIELD_STATUS_MISSING")
        statuses = {}
    else:
        statuses = {"app." + k: v for k, v in statuses["fields"].items()
                    if isinstance(k, str) and k.startswith(tuple(n + "." for n in sources.APP_ROOTS))}
    qualities = {k: sources._quality(k, features.get(k), v) for k, v in statuses.items()}
    binding.update(collector_version_code=manifest.get("collector_version_code"),
                   collector_version_name=manifest.get("collector_version_name"),
                   receipt_id=raw.get("receipt_id"), raw_schema=raw.get("raw_payload_archive_schema_version"))
    return sources._result(binding, features, statuses, qualities, errors)


@lru_cache(maxsize=1)
def compiler():
    # Reuse only this pure current-payload compiler, not its old cohort admission.
    path = ROOT / "deliverables/webgl1_fresh_comparison_v1/prepare.py"
    spec = importlib.util.spec_from_file_location("memory_current_raw_compiler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.metadata_contract()


def adapt_memory_batch(raw, *, session_id, source_reference, environment_id):
    bound = bind_memory_batch(raw, session_id=session_id, source_reference=source_reference,
                              environment_id=environment_id)
    if bound["status"] != "OK":
        raise ValueError("MEMORY_BATCH_BINDING_FAILED:" + ";".join(bound["errors"]))
    module, contract = compiler()
    prepared = module.compile_record(raw["canonical_received_payload"], expected_session_id=session_id,
                                     source_reference=source_reference, measurement_contract=contract)
    # base adapter depends on raw observation semantics, not a sample-ID prefix.
    adapted = extended.extend(base.adapt_controlled(prepared), bound)
    adapted["batch_adapter_version"] = VERSION
    return bound, adapted


def operand_details(bound):
    return {field: {"value": deepcopy(bound.get("features", {}).get(field)),
                    "present": field in bound.get("features", {}),
                    "status": bound.get("field_status", {}).get(field),
                    "quality": bound.get("field_quality", {}).get(field)} for field in (NATIVE, WEB)}


def intervention_effect(pre, active, post, operation):
    """Effect/rollback adjudication never reads either detector's output.

    Missing observations or failed operations are retained, not silently made
    into negatives. Any actual change remains a change even inside the bound.
    """
    rows = (pre, active, post)
    values = [r.get("operands", {}).get(WEB, {}).get("value") if r else None for r in rows]
    valid = []
    for r, value in zip(rows, values):
        operand = r.get("operands", {}).get(WEB, {}) if r else {}
        valid.append(operand.get("status") == "observed" and operand.get("quality") == "observed_value"
                     and type(value) in (int, float) and math.isfinite(value) and value > 0)
    execution = ("NOT_EXECUTED" if not operation or operation.get("cdp_status") == "NOT_EXECUTED" else
                 "EXECUTED" if operation.get("cdp_status") == "COMPLETED" else "OPERATION_FAILED")
    target = operation.get("target_gib") if operation else None
    if not all(valid[:2]):
        effect = "MISSING_OBSERVATION"
    elif values[1] == values[0]:
        effect = "NO_OBSERVABLE_EFFECT"
    elif values[1] == target:
        effect = "OBSERVABLE_TARGET_CHANGE"
    else:
        effect = "CHANGED_BUT_TARGET_NOT_REACHED"
    recovery = "MISSING_OBSERVATION" if not (valid[0] and valid[2]) else "RESTORED" if values[0] == values[2] else "RECOVERY_FAILED"
    return {"execution": execution, "effect": effect, "recovery": recovery,
            "position_attempted": bool(operation), "cdp_attempted": execution != "NOT_EXECUTED",
            "values_pre_active_post": values, "target_reached": bool(valid[1] and values[1] == target),
            "effect_positive": execution == "EXECUTED" and effect == "OBSERVABLE_TARGET_CHANGE"}
