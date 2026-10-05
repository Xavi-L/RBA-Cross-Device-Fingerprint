"""Small, independent observation contracts; no repository or runtime access.

SourceBinding is supplied by an integrating caller under its collection contract.
It is not an attestation, authorization decision, or proof of genuine JS values.
Never construct it automatically from a page payload or a historical sample.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

VERSION = "1.0.0"
INPUT_SCHEMA_VERSION = "rsr-input-v1"
SOURCE_BINDING_VERSION = "rsr-source-binding-v1"
BINDING_SCOPES = frozenset(("navigator_sync_v1", "webdriver_legacy_projection_v1",
                            "webdriver_raw_observation_v1"))


class ContractError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class SourceBinding:
    """Caller-owned association only. Absence never defaults to trusted.

    Raw observations additionally require observer_revision and realm_binding.
    Identifiers are compared for association, never used as detector features.
    """
    source_contract_id: str
    observation_scope: str
    observer_revision: str | None = None
    realm_binding: str | None = None
    binding_version: str = SOURCE_BINDING_VERSION


@dataclass(frozen=True)
class Issue:
    state: str
    reason: str
    field: str | None = None
    source_reason: str | None = None

    def __post_init__(self):
        if self.state not in ("U", "FAILED") or type(self.reason) is not str or not self.reason:
            raise ValueError("INVALID_ISSUE")


@dataclass(frozen=True)
class SemanticCell:
    candidate_id: str
    version: str
    value: bool | None
    available: bool
    evaluation_status: str
    reason: str
    source_reason: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if any(type(x) is not str or not x for x in (self.candidate_id, self.version, self.reason)):
            raise ValueError("INVALID_CELL_IDENTITY_OR_REASON")
        if type(self.available) is not bool or type(self.evaluation_status) is not str:
            raise ValueError("INVALID_CELL_ENCODING")
        valid = ((self.evaluation_status == "OK" and
                  ((self.available is True and type(self.value) is bool) or
                   (self.available is False and self.value is None))) or
                 (self.evaluation_status == "FAILED" and self.available is False and self.value is None))
        if not valid:
            raise ValueError("INVALID_CELL_ENCODING")
        if self.source_reason is not None and type(self.source_reason) is not str:
            raise ValueError("INVALID_SOURCE_REASON")
        if type(self.diagnostics) is not dict:
            raise ValueError("INVALID_DIAGNOSTICS")
        # Detach diagnostics from all caller-owned input objects.
        object.__setattr__(self, "diagnostics", deepcopy(self.diagnostics))

    @property
    def state(self) -> str:
        """Derived display state, never a separately stored competing value."""
        if self.evaluation_status == "FAILED":
            return "FAILED"
        if not self.available:
            return "U"
        return "T" if self.value else "F"

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "version": self.version,
                "value": self.value, "available": self.available,
                "evaluation_status": self.evaluation_status, "reason": self.reason,
                "source_reason": self.source_reason, "diagnostics": deepcopy(self.diagnostics)}


def make_cell(candidate_id: str, state: str, reason: str, *,
              source_reason: str | None = None, diagnostics: dict | None = None) -> SemanticCell:
    if state not in ("T", "F", "U", "FAILED"):
        raise ValueError("INVALID_SEMANTIC_STATE")
    return SemanticCell(candidate_id, VERSION, {"T": True, "F": False}.get(state),
                        state in ("T", "F"), "FAILED" if state == "FAILED" else "OK",
                        reason, source_reason, {} if diagnostics is None else diagnostics)
