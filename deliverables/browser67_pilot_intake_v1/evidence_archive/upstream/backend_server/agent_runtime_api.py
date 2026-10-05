"""Read-only HTTP boundary for the deterministic HybridGuard Agent Runtime.

Only an inline three-layer fingerprint payload is accepted.  Dataset paths,
snapshot handles, and output locations are intentionally not API parameters:
offline snapshot construction remains a separate, auditable workflow.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

try:
    from agent_runtime_service import (
        KnowledgeDriftError,
        RuntimeContractError,
        analyze_agent_payload,
        get_agent_runtime_readiness,
    )
except ModuleNotFoundError:
    from backend_server.agent_runtime_service import (
        KnowledgeDriftError,
        RuntimeContractError,
        analyze_agent_payload,
        get_agent_runtime_readiness,
    )


AGENT_RUNTIME_REQUEST_VERSION = "agent-runtime-request-v1"
HTTP_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", None)
if HTTP_422 is None:  # FastAPI releases before RFC 9110's renamed constant.
    HTTP_422 = status.HTTP_422_UNPROCESSABLE_ENTITY

# The runtime does not need provenance, labels, provider metadata, snapshots,
# files, model outputs, or collection controls.  Keep the accepted envelope
# narrow even though the collector itself is intentionally forward-compatible.
ALLOWED_PAYLOAD_TOP_LEVEL_KEYS = frozenset(
    {
        "session_id",
        "timestamp",
        "client_ip",
        "collector_app",
        "schema_version",
        "browser_ticket_request_id",
        "android_native_data",
        "webview_data",
        "web_data",
        "collection_status",
        "field_status",
        "collection_manifest",
        "collection_diagnostics",
    }
)
FORBIDDEN_CONTROL_KEYS = frozenset(
    {
        "snapshot",
        "snapshot_dir",
        "snapshot_path",
        "dataset",
        "dataset_dir",
        "dataset_path",
        "artifact",
        "artifact_dir",
        "artifact_path",
        "input_file",
        "input_path",
        "output_file",
        "output_path",
        "file_path",
        "file_name",
        "archive_path",
        "directory",
        "path",
    }
)
SENSITIVE_VALUE_KEYS = frozenset(
    {
        "session_id",
        "client_ip",
        "user_agent",
        "system_http_agent",
        "default_ua_native",
        "build_fingerprint",
        "device_model",
    }
)


class AgentRuntimeRequest(BaseModel):
    """A bounded, non-persistent runtime request.

    ``ConfigDict`` is used because the repository's installed FastAPI runs on
    Pydantic v2.  Unknown request fields are rejected instead of being treated
    as filesystem or snapshot instructions.
    """

    model_config = ConfigDict(extra="forbid")

    request_schema_version: str = Field(default=AGENT_RUNTIME_REQUEST_VERSION)
    trace_detail: Literal["summary", "full"] = Field(default="summary")
    payload: dict[str, Any] = Field(..., description="Inline fingerprint payload only")


AnalyzeFunction = Callable[[dict[str, Any]], dict[str, Any]]
ReadinessFunction = Callable[[], dict[str, Any]]


def _find_forbidden_control_key(value: Any, prefix: str = "payload") -> str | None:
    """Find a path/dataset control key without echoing its untrusted value."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            current = f"{prefix}.{key_text}"
            if key_text.lower() in FORBIDDEN_CONTROL_KEYS:
                return current
            nested = _find_forbidden_control_key(child, current)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for index, child in enumerate(value):
            nested = _find_forbidden_control_key(child, f"{prefix}[{index}]")
            if nested is not None:
                return nested
    return None


def _validate_request_payload(payload: dict[str, Any]) -> None:
    unknown_keys = sorted(set(payload) - ALLOWED_PAYLOAD_TOP_LEVEL_KEYS)
    if unknown_keys:
        raise HTTPException(
            status_code=HTTP_422,
            detail="Only the documented inline fingerprint payload fields are accepted.",
        )
    forbidden_location = _find_forbidden_control_key(payload)
    if forbidden_location is not None:
        raise HTTPException(
            status_code=HTTP_422,
            detail="Snapshot, dataset, artifact, and file path controls are not accepted by this API.",
        )


def _sensitive_values(payload: Any) -> set[str]:
    """Collect meaningful raw values that must not reappear in a response."""
    values: set[str] = set()
    if isinstance(payload, Mapping):
        for key, child in payload.items():
            if str(key).lower() in SENSITIVE_VALUE_KEYS and isinstance(child, str):
                # Very short values tend to collide with ordinary response text;
                # longer source values are useful leak sentinels.
                if len(child.strip()) >= 8:
                    values.add(child.strip())
            values.update(_sensitive_values(child))
    elif isinstance(payload, list):
        for child in payload:
            values.update(_sensitive_values(child))
    return values


def _assert_response_is_redacted(payload: dict[str, Any], response: dict[str, Any]) -> None:
    rendered = json.dumps(response, ensure_ascii=False, sort_keys=True)
    if any(raw_value in rendered for raw_value in _sensitive_values(payload)):
        # Do not identify the value or its source field in a response/log.
        raise RuntimeContractError("Runtime response failed redaction validation.")


def _observation_counts(evidence_bundle: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for observations in evidence_bundle.get("evidence_groups", {}).values():
        if not isinstance(observations, list):
            continue
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            observed_status = str(observation.get("status", "unknown"))
            counts[observed_status] = counts.get(observed_status, 0) + 1
    return dict(sorted(counts.items()))


def _summary_response(result: dict[str, Any]) -> dict[str, Any]:
    """Return decision trace metadata without raw facts, cards, or full trace."""
    evidence_bundle = result["evidence_bundle"]
    execution = result["rule_execution"]
    trace = result["decision_trace"]
    return {
        "response_schema_version": result["response_schema_version"],
        "status": result["status"],
        "decision_id": result["decision_id"],
        "decision": result["decision"],
        "evidence_summary": {
            "evidence_bundle_version": evidence_bundle["evidence_bundle_version"],
            "evidence_hash": evidence_bundle["evidence_hash"],
            "supported_evidence_groups": evidence_bundle["coverage"]["supported_evidence_groups"],
            "not_assessed": evidence_bundle["coverage"]["not_assessed"],
            "observation_status_counts": _observation_counts(evidence_bundle),
        },
        "rule_execution_summary": {
            "rule_execution_version": execution["rule_execution_version"],
            "rule_kb_version": execution["rule_kb_version"],
            "rule_kb_sha256": execution["rule_kb_sha256"],
            "matched_rule_ids": execution["matched_rule_ids"],
            "context_rule_ids": execution["tolerance_or_context_rule_ids"],
            "unevaluated_rule_ids": execution["unevaluated_rule_ids"],
            "short_circuit_status": execution["short_circuit_status"],
        },
        "decision_trace": {
            "decision_trace_version": trace["decision_trace_version"],
            "versions": trace["versions"],
            "evidence_hash": trace["evidence_hash"],
            "reasoning": trace["reasoning"],
            "fusion": trace["fusion"],
            "verification": trace["verification"],
            "runtime": trace["runtime"],
        },
        "warnings": result["warnings"],
    }


def create_agent_runtime_router(
    analyze_function: AnalyzeFunction = analyze_agent_payload,
    readiness_function: ReadinessFunction = get_agent_runtime_readiness,
) -> APIRouter:
    """Create an isolated router suitable for a fresh FastAPI test app."""
    router = APIRouter(prefix="/api/agent", tags=["deterministic-agent-runtime"])

    @router.get("/readiness")
    async def agent_runtime_readiness_endpoint() -> dict[str, Any]:
        try:
            return readiness_function()
        except (KnowledgeDriftError, OSError, ValueError):
            # Config/KM drift is a service readiness problem, not a request
            # problem.  Avoid exposing local filesystem or configuration data.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent runtime configuration is not ready.",
            )

    @router.post("/analyze")
    async def analyze_agent_runtime(request: AgentRuntimeRequest) -> dict[str, Any]:
        if request.request_schema_version != AGENT_RUNTIME_REQUEST_VERSION:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Unsupported agent runtime request schema version.",
            )
        _validate_request_payload(request.payload)
        try:
            result = analyze_function(request.payload)
            _assert_response_is_redacted(request.payload, result)
        except KnowledgeDriftError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent runtime knowledge configuration requires review.",
            )
        except RuntimeContractError:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Agent runtime could not analyze the supplied payload.",
            )
        except (OSError, ValueError, KeyError, TypeError):
            # The bounded runtime should fail closed; it must not include input
            # values or internal paths in an error response.
            raise HTTPException(
                status_code=HTTP_422,
                detail="Agent runtime could not analyze the supplied payload.",
            )
        return result if request.trace_detail == "full" else _summary_response(result)

    return router


router = create_agent_runtime_router()
