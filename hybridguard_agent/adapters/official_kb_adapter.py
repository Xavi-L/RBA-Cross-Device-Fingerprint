"""Adapt official feature cards onto the frozen 177-field canonical paths."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
DEFAULT_OFFICIAL_CARDS = REPO_ROOT / "google_official_kb" / "feature_risk_cards.json"
DEFAULT_FIELD_REGISTRY = AGENT_ROOT / "schemas" / "field_registry.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_field_paths(path: Path = DEFAULT_FIELD_REGISTRY) -> set[str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row["canonical_path"])
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("canonical_path"), str)
    }


def canonicalize_knowledge_path(path: str, canonical_paths: set[str]) -> str | None:
    if path in canonical_paths:
        return path
    parts = path.split(".")
    if len(parts) >= 3:
        candidate = f"{parts[0]}.{parts[-1]}"
        if candidate in canonical_paths:
            return candidate
    return None


def official_card_id(source_card_id: str) -> str:
    return f"OFFICIAL-{source_card_id}"


def adapt_official_card(card: dict[str, Any], canonical_paths: set[str], version: str | None) -> dict[str, Any]:
    source_card_id = str(card["id"])
    target_rule_ids = [str(item) for item in card.get("target_rule_ids", [])]
    canonical_fields = sorted(
        {
            canonical
            for item in card.get("project_fields", [])
            if isinstance(item, str)
            for canonical in [canonicalize_knowledge_path(item, canonical_paths)]
            if canonical is not None
        }
    )
    applicability = "future_only" if target_rule_ids and all(item.startswith("FUTURE-") for item in target_rule_ids) else "current"
    return {
        "card_id": official_card_id(source_card_id),
        "kind": "official",
        "title": str(card.get("name", source_card_id)),
        "source_card_id": source_card_id,
        "canonical_fields": canonical_fields,
        "target_rule_ids": target_rule_ids,
        "evidence_groups": list(card.get("groups", [])),
        "content": {
            "semantics": str(card.get("official_basis_summary", "")),
            "risk_extraction": str(card.get("risk_extraction", "")),
            "tolerance": str(card.get("tolerance", "")),
        },
        "provenance": {
            "source_refs": list(card.get("source_refs", [])),
            "evidence_strength": card.get("evidence_strength"),
            "inference_level": card.get("inference_level"),
        },
        "applicability": applicability,
        "status": "published",
        "version": version,
    }


def load_official_cards(
    cards_path: Path = DEFAULT_OFFICIAL_CARDS,
    registry_path: Path = DEFAULT_FIELD_REGISTRY,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = json.loads(cards_path.read_text(encoding="utf-8"))
    cards = source.get("cards")
    if not isinstance(cards, list):
        raise ValueError(f"Official knowledge has no cards list: {cards_path}")
    canonical_paths = load_field_paths(registry_path)
    return source, [adapt_official_card(card, canonical_paths, source.get("version")) for card in cards]
