"""Compose deterministic evidence, rules, retrieval, verification, and trace output."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from hybridguard_agent.adapters.official_kb_adapter import DEFAULT_OFFICIAL_CARDS, sha256_file as official_sha256
from hybridguard_agent.adapters.rule_kb_adapter import (
    DEFAULT_RULE_KB,
    assert_pinned_rule_kb,
    load_rule_knowledge_base,
)
from hybridguard_agent.evidence.extractor import (
    EVIDENCE_EXTRACTOR_VERSION,
    build_evidence_bundle_v2,
    canonical_json,
    normalize_payload,
    sha256_value,
)
from hybridguard_agent.retrieval.exact_retriever import build_exact_context_pack, load_retrieval_policy
from hybridguard_agent.rules.executor import execute_deterministic_rules, load_predicate_registry
from hybridguard_agent.verification.verifier import verify_runtime_output


RUNTIME_RESPONSE_VERSION = "agent-runtime-response-v1"
RISK_DECISION_VERSION = "runtime-decision-v1"
DECISION_TRACE_VERSION = "decision-trace-v1"


class RuntimeContractError(RuntimeError):
    """Raised when the runtime cannot produce a verified, bounded output."""


def _hash_session_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("session_id")
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _decision_id(evidence_hash: str, rule_kb_hash: str) -> str:
    return f"decision-{sha256_value({'evidence_hash': evidence_hash, 'rule_kb_hash': rule_kb_hash})[:24]}"


def _decision_from_execution(evidence_bundle: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    matched = list(execution.get("matched_rule_ids", []))
    context = list(execution.get("tolerance_or_context_rule_ids", []))
    short_circuit = list(execution.get("short_circuit_status", {}).get("matched_rule_ids", []))
    unknown = [
        result["rule_id"]
        for result in execution.get("rule_results", [])
        if result.get("outcome") in {"unknown", "unavailable"}
    ]
    unevaluated_mandatory = list(
        execution.get("short_circuit_status", {}).get("unevaluated_mandatory_rule_ids", [])
    )
    if short_circuit:
        status = "manual_review_required"
        conclusion = "deterministic_core_condition_observed"
        action = "manual_review_and_preserve_provenance"
    elif matched:
        status = "inconsistency_observed"
        conclusion = "deterministic_inconsistency_observed"
        action = "review_evidence_and_continue_controlled_collection"
    elif unknown or unevaluated_mandatory:
        status = "insufficient_evidence"
        conclusion = "not_assessed"
        action = "collect_missing_evidence_or_complete_predicate_coverage"
    elif context:
        status = "context_observed"
        conclusion = "collection_or_development_context_observed"
        action = "retain_context_without_treating_it_as_an_attack_label"
    else:
        status = "completed"
        conclusion = "no_compiled_condition_observed"
        action = "continue_collection; no calibrated safety or attack claim is implied"
    return {
        "decision_version": RISK_DECISION_VERSION,
        "sample_id": evidence_bundle["sample_id"],
        "decision_status": status,
        "conclusion": conclusion,
        "recommended_action": action,
        "calibrated_risk_score": None,
        "calibration_status": "not_available",
        "matched_rule_ids": matched,
        "context_rule_ids": context,
        "unknown_or_unavailable_rule_ids": unknown,
        "unevaluated_mandatory_rule_ids": unevaluated_mandatory,
        "observation_ids": sorted(
            observation["observation_id"]
            for observations in evidence_bundle["evidence_groups"].values()
            for observation in observations
        ),
        "evidence_hash": evidence_bundle["evidence_hash"],
        "claim_boundary": (
            "This is a deterministic evidence-and-rules result. It is not a calibrated risk probability, "
            "attack label, fraud decision, or evidence of cross-device generalization."
        ),
    }


def _reasoning_summary(decision: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    outcomes = {
        "matched": 0,
        "context_observed": 0,
        "unknown": 0,
        "unavailable": 0,
        "not_matched": 0,
        "not_evaluated": 0,
    }
    for result in execution.get("rule_results", []):
        outcome = result.get("outcome")
        if outcome in outcomes:
            outcomes[outcome] += 1
    return {
        "reasoner_mode": "deterministic-template-v1",
        "summary": (
            f"Executed {sum(outcomes.values())} reviewed predicates: {outcomes['matched']} matched, "
            f"{outcomes['context_observed']} context observations, and "
            f"{outcomes['unknown'] + outcomes['unavailable']} unavailable or indeterminate results, and "
            f"{outcomes['not_evaluated']} predicates skipped after a short-circuit. "
            "No external LLM, empirical case retrieval, or calibrated fusion was used."
        ),
        "outcome_counts": outcomes,
        "decision_status": decision["decision_status"],
    }


def analyze_evidence_bundle(
    evidence_bundle: dict[str, Any],
    input_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    execution = execute_deterministic_rules(evidence_bundle)
    context_pack = build_exact_context_pack(evidence_bundle, execution)
    decision = _decision_from_execution(evidence_bundle, execution)
    decision_id = _decision_id(evidence_bundle["evidence_hash"], execution["rule_kb_sha256"])
    verification = verify_runtime_output(evidence_bundle, execution, context_pack, decision)
    if not verification["valid"]:
        raise RuntimeContractError(f"Runtime output verification failed: {verification['errors']}")
    trace = {
        "decision_trace_version": DECISION_TRACE_VERSION,
        "decision_id": decision_id,
        "sample_id": evidence_bundle["sample_id"],
        "versions": {
            "schema": evidence_bundle["schema_version"],
            "extractor": evidence_bundle["extractor_version"],
            "rule_kb": execution["rule_kb_version"],
            "rule_kb_sha256": execution["rule_kb_sha256"],
            "predicate_registry": execution["predicate_registry_version"],
            "retrieval": context_pack["retrieval_policy_version"],
            "retrieval_index": context_pack["retrieval_index_version"],
            "reasoner": "deterministic-template-v1",
            "fusion": "not_available_without_calibration",
        },
        "evidence_hash": evidence_bundle["evidence_hash"],
        "rule_execution": execution,
        "retrieval": {
            "query_fields": context_pack["query_fields"],
            "filters": context_pack["filters"],
            "retrieved_card_ids": [card["card_id"] for card in context_pack["cards"]],
            "excluded_card_ids": context_pack["excluded_card_ids"],
        },
        "reasoning": _reasoning_summary(decision, execution),
        "fusion": {
            "mode": "disabled_without_calibration",
            "raw_score": None,
            "final_score": None,
            "reason": "A future labelled, grouped evaluation is required before weights or thresholds are fitted.",
        },
        "citations": {
            "rule_ids": decision["matched_rule_ids"] + decision["context_rule_ids"],
            "card_ids": [card["card_id"] for card in context_pack["cards"]],
            "source_ids": sorted(
                {
                    source_id
                    for card in context_pack["cards"]
                    for source_id in card.get("provenance", {}).get("source_refs", [])
                }
            ),
            "field_ids": context_pack["query_fields"],
        },
        "verification": verification,
        "runtime": {
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "external_model_called": False,
            "decision_persisted": False,
        },
    }
    input_section = {
        "schema_version": evidence_bundle["schema_version"],
        "payload_sha256": input_metadata.get("payload_sha256") if input_metadata else None,
        "session_id_hash": input_metadata.get("session_id_hash") if input_metadata else None,
    }
    return {
        "response_schema_version": RUNTIME_RESPONSE_VERSION,
        "status": "completed",
        "decision_id": decision_id,
        "input": input_section,
        "decision": decision,
        "evidence_bundle": evidence_bundle,
        "rule_execution": execution,
        "context_pack": context_pack,
        "decision_trace": trace,
        "warnings": [
            "No calibrated score is emitted.",
            "Future-only evidence, empirical cases, labels, provider metadata, and attack tools are excluded.",
        ],
    }


def analyze_payload(payload: dict[str, Any], sample_id: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeContractError("Runtime payload must be a JSON object")
    normalized, _ = normalize_payload(payload)
    has_any_layer = any(normalized[layer] for layer in ("android_native_data", "webview_data", "web_data"))
    if not has_any_layer:
        raise RuntimeContractError("Runtime payload contains no supported fingerprint layer")
    evidence_bundle = build_evidence_bundle_v2(payload, sample_id=sample_id)
    return analyze_evidence_bundle(
        evidence_bundle,
        {
            "payload_sha256": sha256_value(normalized),
            "session_id_hash": _hash_session_id(payload),
        },
    )


def runtime_readiness() -> dict[str, Any]:
    registry = load_predicate_registry()
    rule_kb_hash = assert_pinned_rule_kb(registry)
    kb = load_rule_knowledge_base()
    policy = load_retrieval_policy()
    return {
        "status": "ready",
        "runtime_response_version": RUNTIME_RESPONSE_VERSION,
        "supported_schema_version": "expanded-v2",
        "evidence_extractor_version": EVIDENCE_EXTRACTOR_VERSION,
        "deterministic_only": True,
        "external_model_called": False,
        "decision_persistence": False,
        "calibration_status": "not_available",
        "rule_kb_version": kb.get("version"),
        "rule_kb_sha256": rule_kb_hash,
        "official_cards_sha256": official_sha256(DEFAULT_OFFICIAL_CARDS),
        "predicate_registry_version": registry.get("predicate_registry_version"),
        "retrieval_policy_version": policy.get("retrieval_policy_version"),
        "boundary": "Read-only evidence/rules/retrieval runtime; no labels, provider metadata, attack tools, raw identifiers, calibrated score, or persistence.",
    }
