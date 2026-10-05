"""Pure input transfer for an externally registered FeatureApp collection.

The caller supplies both the expected session and separately reviewed source
bindings. Neither a payload's IDs nor its ``source_binding`` claims issue a
binding. This module does no file access, label admission, candidate evaluation,
training or prediction, and is not an adapter for historical legacy records.

The collector records field *status*, not field quality. For the three fields
here, quality is the explicit S02 policy: observed -> observed_value, other
recognized statuses -> source_unavailable. Missing/unknown status is never
upgraded or assigned a quality. This is a derived quality, not a new reading.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .rule_semantics_input_readiness import (
    BINDING_SCOPES_BY_MODE, FIELDS, MODES, RAW_MEMBERS, project_payload,
)
from .rule_semantics_revision_v1.contracts import INPUT_SCHEMA_VERSION, Issue, SourceBinding
from .rule_semantics_revision_v1.input_adapter import FIELD_STATUSES, binding_issues

VERSION = "featureapp-rule-semantics-runtime-input-v1"
RAW_SCHEMA = "expanded-v2.2-status"
OBSERVATION_SCHEMA = "app-web-observations-v1"
OBSERVER_REVISION = "app-webdriver-observer-v1"
QUALITY_POLICY = "explicit-field-status-quality-v1"
_MISSING = object()


class RuntimeInputError(ValueError):
    """The caller cannot pass an unregistered/mismatched input to a candidate."""

    def __init__(self, issues: tuple[Issue, ...]):
        self.issues = issues
        self.state = "FAILED" if any(i.state == "FAILED" for i in issues) else "U"
        self.reason = next((i.reason for i in issues if i.state == "FAILED"), issues[0].reason)
        super().__init__("; ".join(i.reason for i in issues))

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state, "reason": self.reason, "issues": [
            {"state": i.state, "reason": i.reason, "field": i.field,
             "source_reason": i.source_reason} for i in self.issues
        ]}


@dataclass(frozen=True)
class RuntimeInputs:
    """Detached transfer plus source gates; gates are not semantic results.

    Use ``input_for`` to obtain a mode's input. Its gate covers the registered
    envelope and source association only. A returned input can still evaluate
    to U/FAILED: missing field state, nonboolean webdriver values, read errors,
    malformed raw tuples and contradictions are intentionally not repaired.
    """

    payload: dict[str, Any]
    bindings: dict[str, SourceBinding | None]
    issues_by_mode: dict[str, tuple[Issue, ...]]

    def input_for(self, mode: str) -> tuple[dict[str, Any], SourceBinding]:
        if type(mode) is not str or mode not in MODES:
            raise ValueError("UNKNOWN_INPUT_MODE")
        if self.issues_by_mode[mode]:
            raise RuntimeInputError(self.issues_by_mode[mode])
        binding = self.bindings[mode]
        assert type(binding) is SourceBinding
        return project_payload(self.payload, mode), binding


def _at_path(payload: dict, path: str) -> Any:
    current: Any = payload
    for key in path.split("."):
        if type(current) is not dict:
            raise ValueError("MALFORMED_RUNTIME_FIELD_CONTAINER:" + path)
        if key not in current:
            return _MISSING
        current = current[key]
    return current


def adapt_runtime_payload(
    raw_payload: object, *, expected_session_id: str,
    source_bindings: dict[str, SourceBinding | None],
) -> RuntimeInputs:
    """Copy only the three registered fields and the optional raw webdriver tuple.

    ``expected_session_id`` must come from the caller's reviewed receipt/index,
    and ``source_bindings`` from its source registration, never from this raw
    payload. The raw binding's observer revision and main-frame realm must
    match this explicit FeatureApp contract and that external session. Mode
    selection is explicit through ``input_for``; raw and legacy never fallback.

    A failed transfer still returns detached evidence and per-mode gate issues
    for a preparation report. No failed gate can be retrieved by input_for.
    """
    projected: dict[str, Any] = {"record_schema_version": INPUT_SCHEMA_VERSION}
    issues: dict[str, list[Issue]] = {mode: [] for mode in MODES}
    bindings: dict[str, SourceBinding | None] = {mode: None for mode in MODES}

    def add(modes, state: str, reason: str, field: str | None = None) -> None:
        for mode in modes:
            issues[mode].append(Issue(state, reason, field))

    session_valid = type(expected_session_id) is str and bool(expected_session_id.strip())
    if not session_valid:
        add(MODES, "FAILED", "INVALID_EXPECTED_SESSION_ID")
    if type(source_bindings) is not dict:
        add(MODES, "FAILED", "INVALID_RUNTIME_SOURCE_REGISTRATION")
        source_bindings = {}
    elif set(source_bindings) - set(MODES):
        add(MODES, "FAILED", "UNKNOWN_RUNTIME_SOURCE_MODE")
    expected_realm = f"featureapp:{expected_session_id}:main-frame" if session_valid else None
    for mode in MODES:
        binding = source_bindings.get(mode)
        problems = binding_issues(binding, BINDING_SCOPES_BY_MODE[mode])
        issues[mode].extend(problems)
        if problems:
            continue
        assert type(binding) is SourceBinding
        bindings[mode] = deepcopy(binding)
        if mode == "WEBDRIVER_RAW":
            if binding.observer_revision != OBSERVER_REVISION:
                add((mode,), "FAILED", "RUNTIME_BINDING_OBSERVER_MISMATCH")
            if expected_realm is not None and binding.realm_binding != expected_realm:
                add((mode,), "FAILED", "RUNTIME_BINDING_REALM_MISMATCH")

    if type(raw_payload) is not dict:
        add(MODES, "FAILED", "INVALID_RUNTIME_PAYLOAD")
        raw_payload = {}
    if raw_payload.get("schema_version") != RAW_SCHEMA or raw_payload.get("collector_app") != "featureapp":
        add(MODES, "FAILED", "UNSUPPORTED_RUNTIME_PAYLOAD_CONTRACT")
    if session_valid and (type(raw_payload.get("session_id")) is not str or
                          raw_payload["session_id"] != expected_session_id):
        add(MODES, "FAILED", "RUNTIME_SESSION_MISMATCH")

    # Preserve only present values, including null, false and list order. A
    # malformed container is distinct from an absent field; no flatten fallback.
    for mode in ("LANGUAGE", "WEBDRIVER_LEGACY"):
        for field in FIELDS[mode]:
            try:
                value = _at_path(raw_payload, field.removeprefix("app."))
            except ValueError:
                add((mode,), "FAILED", "MALFORMED_RUNTIME_FIELD_CONTAINER", field)
                continue
            if value is not _MISSING:
                projected.setdefault("features", {})[field] = deepcopy(value)

    collection = raw_payload.get("collection_status", _MISSING)
    fields: dict = {}
    measurement_modes = ("LANGUAGE", "WEBDRIVER_LEGACY")
    if collection is not _MISSING:
        if type(collection) is not dict:
            add(measurement_modes, "FAILED", "MALFORMED_RUNTIME_COLLECTION_STATUS")
        elif collection.get("status_schema_version") != "field-status-v1":
            add(measurement_modes, "FAILED", "UNSUPPORTED_RUNTIME_STATUS_SCHEMA")
        elif "fields" in collection:
            if type(collection["fields"]) is not dict:
                add(measurement_modes, "FAILED", "MALFORMED_RUNTIME_STATUS_FIELDS")
            else:
                fields = collection["fields"]
    for mode in measurement_modes:
        for field in FIELDS[mode]:
            path = field.removeprefix("app.")
            if path not in fields:
                continue
            state = fields[path]
            projected.setdefault("field_status", {})[field] = deepcopy(state)
            if type(state) is str and state in FIELD_STATUSES:
                projected.setdefault("field_quality", {})[field] = (
                    "observed_value" if state == "observed" else "source_unavailable"
                )

    observations = raw_payload.get("collection_observations", _MISSING)
    raw_mode = ("WEBDRIVER_RAW",)
    if observations is _MISSING or observations is None:
        add(raw_mode, "U", "MISSING_RUNTIME_OBSERVATIONS")
    elif type(observations) is not dict:
        add(raw_mode, "FAILED", "MALFORMED_RUNTIME_OBSERVATIONS")
    else:
        if observations.get("observation_schema_version") != OBSERVATION_SCHEMA:
            add(raw_mode, "FAILED", "UNSUPPORTED_RUNTIME_OBSERVATION_SCHEMA")
        if "webdriver" not in observations:
            add(raw_mode, "U", "MISSING_RUNTIME_WEBDRIVER_OBSERVATION")
        else:
            observation = observations["webdriver"]
            copied = ({key: deepcopy(observation[key]) for key in RAW_MEMBERS if key in observation}
                      if type(observation) is dict else deepcopy(observation))
            projected["web_data"] = {"automation_surface_layer": {"webdriver_observation": copied}}
            if observation is None:
                add(raw_mode, "U", "MISSING_RUNTIME_WEBDRIVER_OBSERVATION")
            elif type(observation) is dict:
                for key, expected in (("observer_revision", OBSERVER_REVISION),
                                      ("realm_binding", expected_realm)):
                    value = observation.get(key)
                    if value is None or value == "":
                        add(raw_mode, "U", "MISSING_RUNTIME_OBSERVATION_IDENTITY", key)
                    elif type(value) is not str:
                        add(raw_mode, "FAILED", "INVALID_RUNTIME_OBSERVATION_IDENTITY", key)
                    elif expected is not None and value != expected:
                        add(raw_mode, "FAILED", "RUNTIME_OBSERVATION_IDENTITY_MISMATCH", key)

    return RuntimeInputs(projected, bindings, {
        mode: tuple(dict.fromkeys(problems)) for mode, problems in issues.items()
    })
