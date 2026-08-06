"""Verify citations, field references, and the uncalibrated-output boundary."""

from __future__ import annotations

from typing import Any

from hybridguard_agent.adapters.official_kb_adapter import load_official_cards
from hybridguard_agent.adapters.rule_kb_adapter import load_rule_cards


VERIFIER_VERSION = "runtime-verifier-v1"


def _contains_key(value: Any, forbidden_key: str) -> bool:
    if isinstance(value, dict):
        return forbidden_key in value or any(_contains_key(child, forbidden_key) for child in value.values())
    if isinstance(value, list):
        return any(_contains_key(child, forbidden_key) for child in value)
    return False


def verify_runtime_output(
    evidence_bundle: dict[str, Any],
    rule_execution: dict[str, Any],
    context_pack: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    _, rule_cards = load_rule_cards()
    _, official_cards = load_official_cards()
    known_card_ids = {card["card_id"] for card in rule_cards + official_cards}
    future_card_ids = {card["card_id"] for card in official_cards if card.get("applicability") == "future_only"}
    observed_fields = set(evidence_bundle.get("observed_fields", []))
    retrieved_card_ids = {card.get("card_id") for card in context_pack.get("cards", [])}
    result_fields_valid = all(
        set(result.get("source_fields", [])) <= observed_fields
        for result in rule_execution.get("rule_results", [])
    )
    result_card_ids = {result.get("card_id") for result in rule_execution.get("rule_results", [])}
    matched_cards_present = all(
        result.get("card_id") in retrieved_card_ids
        for result in rule_execution.get("rule_results", [])
        if result.get("outcome") in {"matched", "context_observed", "unknown", "unavailable"}
    )
    context_cards_known = all(card_id in known_card_ids for card_id in retrieved_card_ids)
    future_cards_absent = not bool(retrieved_card_ids & future_card_ids)
    no_risk_score = not _contains_key(decision, "risk_score") and decision.get("calibrated_risk_score") is None
    calibration_boundary = decision.get("calibration_status") == "not_available"
    checks = {
        "evidence_hash_present": isinstance(evidence_bundle.get("evidence_hash"), str) and len(evidence_bundle["evidence_hash"]) == 64,
        "rule_result_fields_observed": result_fields_valid,
        "rule_result_cards_known": result_card_ids <= known_card_ids,
        "retrieved_cards_known": context_cards_known,
        "matched_or_context_cards_retrieved": matched_cards_present,
        "future_only_cards_absent": future_cards_absent,
        "no_risk_score_emitted": no_risk_score,
        "calibration_explicitly_unavailable": calibration_boundary,
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "verification_version": VERIFIER_VERSION,
        "valid": not errors,
        "checks": checks,
        "errors": errors,
    }
