"""Pure projection and structural checks for explicitly located adapted inputs.

The caller must first establish the record's data layer and exact lineage.  A
``features`` key alone does not establish that it contains raw observations.
This module never loads records, compares language values, interprets webdriver,
or calls a candidate/model.  Labels and collection phase are not decision inputs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .rule_semantics_revision_v1.contracts import INPUT_SCHEMA_VERSION, SourceBinding
from .rule_semantics_revision_v1.input_adapter import FIELD_QUALITIES, FIELD_STATUSES


VERSION = "1.0.0"
MODES = ("LANGUAGE", "WEBDRIVER_LEGACY", "WEBDRIVER_RAW")
LANGUAGE_FIELD = "app.web_data.navigator_layer.language"
LANGUAGES_FIELD = "app.web_data.navigator_layer.languages"
WEBDRIVER_FIELD = "app.web_data.automation_surface_layer.webdriver"
FIELDS = {
    "LANGUAGE": (LANGUAGE_FIELD, LANGUAGES_FIELD),
    "WEBDRIVER_LEGACY": (WEBDRIVER_FIELD,),
    "WEBDRIVER_RAW": (),
}
BINDING_SCOPES_BY_MODE = {
    "LANGUAGE": "navigator_sync_v1",
    "WEBDRIVER_LEGACY": "webdriver_legacy_projection_v1",
    "WEBDRIVER_RAW": "webdriver_raw_observation_v1",
}
SOURCE_STATUSES = (
    "SUPPORTED_BY_EXISTING_LINEAGE", "CONDITIONAL_ASSUMPTION", "UNRESOLVED", "CONFLICT"
)
INPUT_STATUSES = ("COMPLETE", "MISSING", "LOSSY", "MALFORMED")
RAW_PATH = ("web_data", "automation_surface_layer", "webdriver_observation")
RAW_MEMBERS = (
    "api_present", "presence_read_status", "value_read_status", "value_type",
    "boolean_value", "observer_revision", "realm_binding",
)
_TYPEOF_STRINGS = frozenset(
    ("undefined", "boolean", "number", "bigint", "string", "symbol", "function", "object")
)
_MISSING = object()


def _mode(mode: str) -> None:
    if type(mode) is not str or mode not in MODES:
        raise ValueError("UNKNOWN_INPUT_MODE")


def _raw_observation(payload: dict) -> Any:
    current = payload
    for index, key in enumerate(RAW_PATH):
        if key not in current:
            return _MISSING
        value = current[key]
        if index == len(RAW_PATH) - 1:
            return value
        if type(value) is not dict:
            raise ValueError("MALFORMED_RAW_CONTAINER:" + ".".join(RAW_PATH[:index + 1]))
        current = value
    raise AssertionError("EMPTY_RAW_PATH")


def project_payload(adapted_payload: dict, mode: str) -> dict[str, Any]:
    """Explicitly copy only the required observation keys, without repair.

    Missing maps/keys remain absent.  Present values, including false, null,
    unfamiliar enum strings, and array order, are deep-copied unchanged.  Bad
    container types raise ValueError instead of silently turning into empties.
    No caller/page metadata is promoted to a SourceBinding.
    """
    _mode(mode)
    if type(adapted_payload) is not dict:
        raise ValueError("MALFORMED_INPUT_ENVELOPE")
    result: dict[str, Any] = {"record_schema_version": INPUT_SCHEMA_VERSION}
    if mode == "WEBDRIVER_RAW":
        observation = _raw_observation(adapted_payload)
        if observation is not _MISSING:
            copied = ({key: deepcopy(observation[key]) for key in RAW_MEMBERS if key in observation}
                      if type(observation) is dict else deepcopy(observation))
            result["web_data"] = {"automation_surface_layer": {
                "webdriver_observation": copied,
            }}
        return result
    for section in ("features", "field_status", "field_quality"):
        if section not in adapted_payload:
            continue
        values = adapted_payload[section]
        if type(values) is not dict:
            raise ValueError("MALFORMED_INPUT_MAP:" + section)
        result[section] = {
            key: deepcopy(values[key]) for key in FIELDS[mode] if key in values
        }
    return result


def inspect_inputs(adapted_payload: dict, mode: str) -> dict[str, Any]:
    """Check retained shape/state only; never compute any candidate relation.

    COMPLETE means the input structure can be transferred, not that sources are
    available or any semantic result is determined.  Legacy false remains a
    complete strict-true projection.  LOSSY is reserved for the caller's proven
    conversion-lineage finding; a wrong type alone does not prove how it arose.
    Raw tuple consistency belongs to the later interpreter and is not checked.
    """
    _mode(mode)
    reasons: list[str] = []
    malformed = False
    missing = False
    availability: dict[str, Any] = {}
    limitations: list[str] = []

    def problem(kind: str, reason: str) -> None:
        nonlocal malformed, missing
        reasons.append(reason)
        malformed = malformed or kind == "MALFORMED"
        missing = missing or kind == "MISSING"

    def result() -> dict[str, Any]:
        return {
            "input_status": "MALFORMED" if malformed else "MISSING" if missing else "COMPLETE",
            "reasons": list(dict.fromkeys(reasons)),
            "availability": availability,
            "limitations": limitations,
        }

    if type(adapted_payload) is not dict:
        problem("MALFORMED", "MALFORMED_INPUT_ENVELOPE")
        return result()
    if mode == "WEBDRIVER_RAW":
        try:
            observation = _raw_observation(adapted_payload)
        except ValueError as exc:
            problem("MALFORMED", str(exc))
            return result()
        if observation is _MISSING or observation is None:
            problem("MISSING", "MISSING_RAW_OBSERVATION")
            return result()
        if type(observation) is not dict:
            problem("MALFORMED", "MALFORMED_RAW_OBSERVATION")
            return result()
        for key in RAW_MEMBERS:
            if key not in observation:
                problem("MISSING", "MISSING_RAW_MEMBER:" + key)
                continue
            value = observation[key]
            if key in ("api_present", "boolean_value"):
                if value is not None and type(value) is not bool:
                    problem("MALFORMED", "INVALID_RAW_MEMBER_TYPE:" + key)
            elif key == "presence_read_status":
                if type(value) is not str or value not in ("observed", "runtime_error"):
                    problem("MALFORMED", "INVALID_RAW_MEMBER_ENUM:" + key)
            elif key == "value_read_status":
                if type(value) is not str or value not in ("observed", "runtime_error", "not_attempted"):
                    problem("MALFORMED", "INVALID_RAW_MEMBER_ENUM:" + key)
            elif key == "value_type":
                if value is not None and (type(value) is not str or value not in _TYPEOF_STRINGS):
                    problem("MALFORMED", "INVALID_RAW_MEMBER_ENUM:" + key)
            elif value is None or value == "":
                problem("MISSING", "MISSING_RAW_MEMBER:" + key)
            elif type(value) is not str:
                problem("MALFORMED", "INVALID_RAW_MEMBER_TYPE:" + key)
        limitations.append("RAW_TUPLE_AND_REPORT_STATE_NOT_EVALUATED")
        return result()

    maps = {}
    for section in ("features", "field_status", "field_quality"):
        value = adapted_payload.get(section, _MISSING)
        if value is _MISSING:
            maps[section] = {}
        elif type(value) is not dict:
            problem("MALFORMED", "MALFORMED_INPUT_MAP:" + section)
            maps[section] = {}
        else:
            maps[section] = value
    for field in FIELDS[mode]:
        value = maps["features"].get(field, _MISSING)
        if value is _MISSING or value is None:
            problem("MISSING", "MISSING_FIELD:" + field)
        elif field == LANGUAGE_FIELD and type(value) is not str:
            problem("MALFORMED", "EXPECTED_STRING:" + field)
        elif field == LANGUAGES_FIELD:
            if type(value) is not list:
                problem("MALFORMED", "EXPECTED_ORDERED_ARRAY:" + field)
            elif not value:
                problem("MISSING", "EMPTY_ORDERED_ARRAY:" + field)
            elif type(value[0]) is not str:
                problem("MALFORMED", "EXPECTED_FIRST_ITEM_STRING:" + field)
        elif field == WEBDRIVER_FIELD and type(value) is not bool:
            problem("MALFORMED", "EXPECTED_STRICT_BOOLEAN:" + field)

        status = maps["field_status"].get(field, _MISSING)
        quality = maps["field_quality"].get(field, _MISSING)
        status_valid = type(status) is str and status in FIELD_STATUSES
        quality_valid = type(quality) is str and quality in FIELD_QUALITIES
        for section, item, valid in (("FIELD_STATUS", status, status_valid),
                                     ("FIELD_QUALITY", quality, quality_valid)):
            if item is _MISSING or item is None:
                problem("MISSING", "MISSING_" + section + ":" + field)
            elif not valid:
                problem("MALFORMED", "INVALID_" + section + ":" + field)
        availability[field] = (
            "UNKNOWN" if not (status_valid and quality_valid)
            else "OBSERVED_VALUE" if status == "observed" and quality == "observed_value"
            else "SOURCE_UNAVAILABLE"
        )
    if mode == "WEBDRIVER_LEGACY":
        limitations.append("LEGACY_STRICT_TRUE_PROJECTION_CANNOT_RECOVER_RAW_OBSERVATION")
    return result()


def readiness(source_status: str, input_status: str) -> str:
    """Combine two predeclared axes, without consulting values or labels."""
    if input_status != "COMPLETE":
        return "BLOCKED"
    if source_status == "SUPPORTED_BY_EXISTING_LINEAGE":
        return "READY"
    if source_status == "CONDITIONAL_ASSUMPTION":
        return "CONDITIONAL"
    return "BLOCKED"


def make_source_binding(registration: dict, mode: str) -> SourceBinding | None:
    """Construct only a supported, evidence-referenced caller registration.

    Evidence is established in the separate lineage audit, not by this type or
    a page flag.  This function neither discovers nor authenticates evidence.
    Observer/realm metadata, if registered, is copied; none is inferred.
    """
    _mode(mode)
    if type(registration) is not dict:
        return None
    modes = registration.get("modes")
    if type(modes) is not dict or type(modes.get(mode)) is not dict:
        return None
    entry = modes[mode]
    if entry.get("source_status") != "SUPPORTED_BY_EXISTING_LINEAGE":
        return None
    references = entry.get("evidence_refs")
    group_id = registration.get("source_group_id")
    if (type(references) is not list or not references or
            any(type(ref) is not str or not ref.strip() for ref in references) or
            type(group_id) is not str or not group_id.strip() or
            entry.get("binding_scope") != BINDING_SCOPES_BY_MODE[mode]):
        return None
    optional = {key: entry.get(key) for key in ("observer_revision", "realm_binding")}
    if any(value is not None and (type(value) is not str or not value.strip())
           for value in optional.values()):
        return None
    return SourceBinding(group_id, BINDING_SCOPES_BY_MODE[mode], **optional)
