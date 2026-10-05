"""Exact-rule and canonical-field retrieval without a vector database."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hybridguard_agent.adapters.official_kb_adapter import load_official_cards
from hybridguard_agent.adapters.rule_kb_adapter import load_rule_cards


AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = AGENT_ROOT / "config" / "retrieval_policy.v1.json"
CONTEXT_PACK_VERSION = "context-pack-v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_retrieval_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _card_view(card: dict[str, Any], reason: str, source_rule_id: str | None = None) -> dict[str, Any]:
    view = {
        "card_id": card["card_id"],
        "kind": card["kind"],
        "title": card["title"],
        "canonical_fields": card.get("canonical_fields", []),
        "content": card.get("content", {}),
        "provenance": card.get("provenance", {}),
        "retrieval_reason": reason,
    }
    if source_rule_id is not None:
        view["source_rule_id"] = source_rule_id
    return view


def build_exact_context_pack(
    evidence_bundle: dict[str, Any],
    rule_execution: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_policy = policy or load_retrieval_policy()
    _, rule_cards = load_rule_cards()
    _, official_cards = load_official_cards()
    rule_by_id = {card["source_rule_id"]: card for card in rule_cards}

    relevant_results = [
        result
        for result in rule_execution.get("rule_results", [])
        if result.get("outcome") in {"matched", "context_observed", "unknown", "unavailable"}
    ]
    selected_rule_ids = [str(result["rule_id"]) for result in relevant_results]
    query_fields = sorted(
        {
            field
            for result in relevant_results
            for field in result.get("source_fields", [])
        }
    )
    selected: list[tuple[int, dict[str, Any]]] = []
    for result in relevant_results:
        card = rule_by_id.get(str(result["rule_id"]))
        if card is None:
            continue
        rank = {"matched": 300, "context_observed": 240, "unknown": 180, "unavailable": 170}[result["outcome"]]
        selected.append((rank, _card_view(card, f"rule_{result['outcome']}", str(result["rule_id"]))))

    referenced_official_ids = {
        card_id
        for rule_id in selected_rule_ids
        for card_id in rule_by_id.get(rule_id, {}).get("provenance", {}).get("official_card_refs", [])
    }
    for card in official_cards:
        if card.get("applicability") != "current":
            continue
        target_rule_ids = set(card.get("target_rule_ids", []))
        overlap = set(card.get("canonical_fields", [])) & set(query_fields)
        source_card_id = card.get("source_card_id")
        if source_card_id in referenced_official_ids:
            selected.append((220, _card_view(card, "official_card_for_selected_rule")))
        elif target_rule_ids & set(selected_rule_ids):
            selected.append((200, _card_view(card, "official_target_rule_overlap")))
        elif overlap:
            selected.append((160, _card_view(card, "canonical_field_overlap")))

    unique: dict[str, tuple[int, dict[str, Any]]] = {}
    for rank, card in selected:
        card_id = str(card["card_id"])
        if card_id not in unique or rank > unique[card_id][0]:
            unique[card_id] = (rank, card)
    cards = [card for _, card in sorted(unique.values(), key=lambda item: (-item[0], item[1]["card_id"]))]
    max_cards = int(active_policy.get("max_cards", 16))
    cards = cards[:max_cards]
    future_excluded = sorted(
        card["card_id"] for card in official_cards if card.get("applicability") == "future_only"
    )
    return {
        "context_pack_version": CONTEXT_PACK_VERSION,
        "retrieval_policy_version": active_policy.get("retrieval_policy_version"),
        "retrieval_index_version": sha256_value(
            {
                "rule_kb_sha256": rule_execution.get("rule_kb_sha256"),
                "policy": active_policy,
                "card_ids": sorted(card["card_id"] for card in rule_cards + official_cards),
            }
        ),
        "sample_id": evidence_bundle.get("sample_id"),
        "evidence_hash": evidence_bundle.get("evidence_hash"),
        "query_fields": query_fields,
        "filters": {
            "applicability": "current",
            "future_cards_excluded": bool(active_policy.get("future_only_excluded", True)),
            "empirical_cases_enabled": bool(active_policy.get("empirical_cases_enabled", False)),
        },
        "cards": cards,
        "excluded_card_ids": future_excluded,
        "boundary_note": active_policy.get("boundary"),
    }
