"""Read only the fields requested by a candidate, under a new explicit schema.

Not the old 177-field adapter. Related enum errors are validation failures;
missing values/statuses and known unavailable sources are U. Unrelated keys are
not traversed or used to infer a source, a label, or a candidate outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import (BINDING_SCOPES, INPUT_SCHEMA_VERSION, SOURCE_BINDING_VERSION,
                        ContractError, Issue, SourceBinding, make_cell)

FIELD_STATUSES = frozenset(("observed", "unsupported_by_os", "permission_denied",
                           "runtime_error", "timeout", "not_applicable"))
FIELD_QUALITIES = frozenset(("observed_value", "source_unavailable", "ambiguous_sentinel"))
_MISSING = object()


@dataclass(frozen=True)
class Observation:
    value: Any
    source_status: str | None
    source_quality: str | None
    issues: tuple[Issue, ...]


def validate_envelope(payload: object, *, field_maps: bool = True) -> None:
    if (type(payload) is not dict or
            type(payload.get("record_schema_version")) is not str or
            payload["record_schema_version"] != INPUT_SCHEMA_VERSION):
        raise ContractError("INVALID_SERIALIZED_RECORD_ENVELOPE")
    if field_maps:
        for section in ("features", "field_status", "field_quality"):
            if section in payload and type(payload[section]) is not dict:
                raise ContractError("INVALID_FIELD_MAP:" + section)


def read_observation(payload: object, field_ref: str) -> Observation:
    """No value coercion or required-field sweep. Issues have fixed precedence."""
    validate_envelope(payload)
    if type(field_ref) is not str or not field_ref:
        raise ContractError("INVALID_FIELD_REFERENCE")
    value = payload.get("features", {}).get(field_ref, _MISSING)
    status = payload.get("field_status", {}).get(field_ref)
    quality = payload.get("field_quality", {}).get(field_ref)
    issues = []
    # Enum errors are detected even if the value itself is absent.
    if status is not None and (type(status) is not str or status not in FIELD_STATUSES):
        issues.append(Issue("FAILED", "INVALID_FIELD_STATE_ENUM", field_ref))
    if quality is not None and (type(quality) is not str or quality not in FIELD_QUALITIES):
        issues.append(Issue("FAILED", "INVALID_FIELD_QUALITY_ENUM", field_ref))
    if type(status) is str and status in FIELD_STATUSES and status != "observed":
        issues.append(Issue("U", "SOURCE_STATUS_" + status.upper(), field_ref, status))
    if type(quality) is str and quality in FIELD_QUALITIES and quality != "observed_value":
        issues.append(Issue("U", "SOURCE_QUALITY_" + quality.upper(), field_ref, quality))
    if status is None or quality is None:
        issues.append(Issue("U", "MISSING_MEASUREMENT_STATE", field_ref))
    if value is _MISSING or value is None:
        issues.append(Issue("U", "MISSING_FIELD", field_ref))
    return Observation(None if value is _MISSING else value, status, quality, tuple(issues))


def binding_issues(binding: object, required_scope: str) -> tuple[Issue, ...]:
    """Validate the caller's association declaration, not the page's honesty."""
    if binding is None:
        return (Issue("U", "SOURCE_BINDING_MISSING"),)
    if type(binding) is not SourceBinding:
        return (Issue("U", "SOURCE_BINDING_UNTRUSTED"),)
    if (type(binding.binding_version) is not str or binding.binding_version != SOURCE_BINDING_VERSION or
            type(binding.observation_scope) is not str or binding.observation_scope not in BINDING_SCOPES or
            type(binding.source_contract_id) is not str or
            any(v is not None and type(v) is not str for v in (binding.observer_revision, binding.realm_binding))):
        return (Issue("FAILED", "INVALID_SOURCE_BINDING"),)
    if not binding.source_contract_id.strip():
        return (Issue("U", "MISSING_SOURCE_BINDING_METADATA"),)
    if binding.observation_scope != required_scope:
        return (Issue("U", "SOURCE_CONTEXT_UNPAIRED"),)
    return ()


def validate_source_binding(binding: object, required_scope: str) -> tuple[Issue, ...]:
    """Public spelling from the approved plan; returns issues, never a bool trust flag."""
    return binding_issues(binding, required_scope)


def issue_cell(candidate_id: str, issues, *, diagnostics: dict | None = None):
    """FAILED takes priority; otherwise caller-supplied fixed stage/field order.

    Dedupe identical findings without adding any extra sample or denominator.
    """
    unique = tuple(dict.fromkeys(issues))
    if not unique:
        raise ValueError("ISSUE_CELL_REQUIRES_ISSUE")
    primary = next((i for i in unique if i.state == "FAILED"), unique[0])
    details = dict(diagnostics or {})
    details["issues"] = [{"state": i.state, "reason": i.reason, "field": i.field,
                          "source_reason": i.source_reason} for i in unique]
    return make_cell(candidate_id, primary.state, primary.reason,
                     source_reason=primary.source_reason, diagnostics=details)
