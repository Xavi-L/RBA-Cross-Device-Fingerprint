"""Pure interpretation of webdriver reports, never automation/attack labels.

The caller selects a registered observation mode and supplies a separate source
binding.  Neither that association nor this interpreter proves an unmodified
native getter.  No historical record is upgraded to a raw observation.
"""

from __future__ import annotations

from typing import Any

from .contracts import ContractError, SemanticCell, SourceBinding, make_cell
from .input_adapter import (
    Issue,
    binding_issues,
    issue_cell,
    read_observation,
    validate_envelope,
)


CANDIDATE_ID = "RSR-WEBDRIVER-STATE-v1"
LEGACY_MODE = "legacy_projection_v1"
RAW_MODE = "raw_observation_v1"
FIELD = "app.web_data.automation_surface_layer.webdriver"
OBSERVATION_PATH = "web_data.automation_surface_layer.webdriver_observation"

_RAW_FIELDS = (
    "api_present",
    "presence_read_status",
    "value_read_status",
    "value_type",
    "boolean_value",
    "observer_revision",
    "realm_binding",
)
_VALUE_TYPES = frozenset(
    {"undefined", "boolean", "number", "bigint", "string", "symbol", "function", "object"}
)
_MISSING = object()


def _legacy(payload: dict[str, Any], source_binding: SourceBinding | None) -> SemanticCell:
    observation = read_observation(payload, FIELD)
    issues = list(observation.issues)
    issues.extend(binding_issues(source_binding, "webdriver_legacy_projection_v1"))
    diagnostics = {"mode": LEGACY_MODE, "engine_state_attribution": "UNVERIFIED"}
    value = observation.value
    if not observation.issues:
        if type(value) is not bool:
            issues.append(Issue("U", "INVALID_BOOLEAN_VALUE", field=FIELD))
        elif value is False:
            issues.append(Issue("U", "LEGACY_NONTRUE_PROJECTION_AMBIGUOUS", field=FIELD))
    if issues:
        return issue_cell(CANDIDATE_ID, tuple(issues), diagnostics=diagnostics)
    return make_cell(CANDIDATE_ID, "T", "LEGACY_REPORTED_TRUE", diagnostics=diagnostics)


def _raw_object(payload: dict[str, Any]) -> dict[str, Any] | None:
    current: Any = payload
    for key in OBSERVATION_PATH.split("."):
        value = current.get(key, _MISSING)
        if value is _MISSING or value is None:
            return None
        if not isinstance(value, dict):
            raise ContractError("INVALID_OBSERVATION_STRUCTURE")
        current = value
    return current


def _raw_record_issues(observation: dict[str, Any]) -> tuple[list[Issue], dict[str, Any]]:
    """Validate only the supplied raw tuple, without filling absent information.

    Known contradictions remain FAILED even when another member or source
    association is absent.  Missing keys remain a separate U condition.
    """
    issues: list[Issue] = []
    diagnostics: dict[str, Any] = {
        "mode": RAW_MODE,
        "engine_state_attribution": "UNVERIFIED",
        "presence_and_getter_atomic": False,
    }
    missing = [key for key in _RAW_FIELDS if key not in observation]
    if missing:
        diagnostics["missing_observation_members"] = missing
        issues.append(Issue("U", "MISSING_OBSERVATION_METADATA", field=OBSERVATION_PATH))

    def invalid(reason: str, key: str) -> None:
        issues.append(Issue("FAILED", reason, field=f"{OBSERVATION_PATH}.{key}"))

    for key in ("api_present", "boolean_value"):
        if key in observation:
            value = observation[key]
            if value is not None and type(value) is not bool:
                invalid("INVALID_OBSERVATION_TYPE", key)
    for key, allowed in (
        ("presence_read_status", {"observed", "runtime_error"}),
        ("value_read_status", {"observed", "runtime_error", "not_attempted"}),
    ):
        if key in observation:
            value = observation[key]
            if type(value) is not str or value not in allowed:
                invalid("INVALID_OBSERVATION_ENUM", key)
    if "value_type" in observation:
        value = observation["value_type"]
        if value is not None and (type(value) is not str or value not in _VALUE_TYPES):
            invalid("INVALID_OBSERVATION_ENUM", "value_type")
    for key in ("observer_revision", "realm_binding"):
        if key in observation:
            value = observation[key]
            if value is None or value == "":
                issues.append(Issue("U", "MISSING_OBSERVATION_METADATA", field=f"{OBSERVATION_PATH}.{key}"))
            elif type(value) is not str:
                invalid("INVALID_OBSERVATION_TYPE", key)

    presence = observation.get("presence_read_status", _MISSING)
    present = observation.get("api_present", _MISSING)
    read_status = observation.get("value_read_status", _MISSING)
    value_type = observation.get("value_type", _MISSING)
    boolean_value = observation.get("boolean_value", _MISSING)
    contradictions: list[str] = []

    def contradict(condition: bool, reason: str) -> None:
        if condition:
            contradictions.append(reason)

    if presence == "runtime_error":
        contradict(present is not _MISSING and present is not None, "presence_error_has_result")
        contradict(read_status is not _MISSING and read_status != "not_attempted", "getter_after_presence_error")
        contradict(value_type is not _MISSING and value_type is not None, "presence_error_has_getter_type")
        contradict(boolean_value is not _MISSING and boolean_value is not None, "presence_error_has_getter_value")
    elif presence == "observed":
        contradict(present is None, "successful_presence_has_null_result")

    if present is False:
        contradict(read_status is not _MISSING and read_status != "not_attempted", "getter_after_api_absent")
        contradict(value_type is not _MISSING and value_type is not None, "absent_api_has_getter_type")
        contradict(boolean_value is not _MISSING and boolean_value is not None, "absent_api_has_getter_value")
    elif present is True:
        contradict(read_status == "not_attempted", "present_api_getter_not_attempted")

    if read_status in ("observed", "runtime_error"):
        contradict(present is not _MISSING and present is not True, "getter_attempt_without_present_api")
    if read_status in ("runtime_error", "not_attempted"):
        contradict(value_type is not _MISSING and value_type is not None, "unread_or_failed_getter_has_type")
        contradict(boolean_value is not _MISSING and boolean_value is not None, "unread_or_failed_getter_has_value")
    elif read_status == "observed":
        contradict(value_type is None, "successful_getter_has_null_type")

    if value_type == "boolean":
        contradict(boolean_value is not _MISSING and type(boolean_value) is not bool, "boolean_type_without_boolean_value")
    elif value_type is not _MISSING and value_type is not None:
        contradict(boolean_value is not _MISSING and boolean_value is not None, "nonboolean_type_has_boolean_value")
    elif value_type is None:
        contradict(boolean_value is not _MISSING and boolean_value is not None, "null_type_has_boolean_value")

    if contradictions:
        diagnostics["contradictions"] = contradictions
        issues.append(Issue("FAILED", "INCONSISTENT_OBSERVATION_RECORD", field=OBSERVATION_PATH))
    return issues, diagnostics


def _raw(payload: dict[str, Any], source_binding: SourceBinding | None) -> SemanticCell:
    observation = _raw_object(payload)
    if observation is None:
        issues = [Issue("U", "MISSING_OBSERVATION_METADATA", field=OBSERVATION_PATH)]
        issues.extend(binding_issues(source_binding, "webdriver_raw_observation_v1"))
        return issue_cell(CANDIDATE_ID, tuple(issues), diagnostics={"mode": RAW_MODE})

    issues, diagnostics = _raw_record_issues(observation)
    binding_problems = binding_issues(source_binding, "webdriver_raw_observation_v1")
    issues.extend(binding_problems)
    if not binding_problems:
        # Only a validated typed external association may authorize comparison.
        assert isinstance(source_binding, SourceBinding)
        if not source_binding.observer_revision:
            issues.append(Issue("U", "MISSING_OBSERVATION_METADATA", field="source_binding.observer_revision"))
        if not source_binding.realm_binding:
            issues.append(Issue("U", "MISSING_REALM_BINDING", field="source_binding.realm_binding"))
        for key in ("observer_revision", "realm_binding"):
            provided = observation.get(key)
            expected = getattr(source_binding, key)
            if type(provided) is str and provided and expected and provided != expected:
                issues.append(Issue("U", "OBSERVATION_NOT_COMPARABLE", field=f"{OBSERVATION_PATH}.{key}"))

    if observation.get("presence_read_status") == "runtime_error":
        issues.append(Issue("U", "PRESENCE_READ_ERROR", field=OBSERVATION_PATH, source_reason="runtime_error"))
    elif observation.get("api_present") is False:
        issues.append(Issue("U", "API_ABSENT", field=OBSERVATION_PATH))
    elif observation.get("value_read_status") == "runtime_error":
        issues.append(Issue("U", "VALUE_READ_ERROR", field=OBSERVATION_PATH, source_reason="runtime_error"))
    elif (
        observation.get("value_read_status") == "observed"
        and type(observation.get("value_type")) is str
        and observation["value_type"] in _VALUE_TYPES - {"boolean"}
    ):
        issues.append(Issue("U", "NONBOOLEAN_API_VALUE", field=OBSERVATION_PATH))

    if issues:
        return issue_cell(CANDIDATE_ID, tuple(issues), diagnostics=diagnostics)
    value = observation["boolean_value"]
    return make_cell(
        CANDIDATE_ID,
        "T" if value is True else "F",
        "RAW_REPORTED_TRUE" if value is True else "RAW_REPORTED_FALSE",
        diagnostics=diagnostics,
    )


def webdriver_reported_state(
    payload: Any, *, mode: str, source_binding: SourceBinding | None = None
) -> SemanticCell:
    """Interpret one explicitly selected report mode without fallback or I/O.

    Legacy strict-true information overlaps the old W03 predicate.  Its false
    projection cannot reveal raw false, absent API, or a nonboolean report.
    Raw successful boolean false means only a reported false value.  The raw
    mode deliberately ignores legacy field maps and plugin/MIME diagnostics.
    """
    try:
        if type(mode) is not str or mode not in (LEGACY_MODE, RAW_MODE):
            raise ContractError("INVALID_WEBDRIVER_MODE")
        validate_envelope(payload, field_maps=(mode == LEGACY_MODE))
        if mode == LEGACY_MODE:
            return _legacy(payload, source_binding)
        return _raw(payload, source_binding)
    except ContractError as exc:
        return make_cell(CANDIDATE_ID, "FAILED", exc.reason)
    except Exception as exc:
        return make_cell(
            CANDIDATE_ID,
            "FAILED",
            "EXECUTOR_ERROR",
            diagnostics={"exception_type": type(exc).__name__},
        )
