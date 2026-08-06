"""Adapt the existing rule knowledge base without treating it as executable code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hybridguard_agent.adapters.official_kb_adapter import canonicalize_knowledge_path, load_field_paths


AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
DEFAULT_RULE_KB = REPO_ROOT / "scoring" / "rule_knowledge_base.json"


class KnowledgeDriftError(RuntimeError):
    """Raised when the predicate registry no longer matches its reviewed KB."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rule_knowledge_base(path: Path = DEFAULT_RULE_KB) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rule_card_id(rule_id: str) -> str:
    return f"RULE-{rule_id}"


def _evidence_groups(category: str) -> list[str]:
    if category.startswith("Native-Web"):
        return ["cross_layer"]
    if category.startswith("Native-WebView"):
        return ["cross_layer", "runtime_context"]
    if category.startswith("WebView-Web"):
        return ["cross_layer"]
    if "容错" in category or "场景" in category or "物理" in category:
        return ["runtime_context"]
    return ["cross_layer", "runtime_context"]


def adapt_rule(rule: dict[str, Any], kb_version: str | None) -> dict[str, Any]:
    official = rule.get("official_knowledge") if isinstance(rule.get("official_knowledge"), dict) else {}
    canonical_paths = load_field_paths()
    raw_fields = [str(value) for value in rule.get("fields", []) if isinstance(value, str)]
    canonical_fields = sorted(
        {
            mapped
            for raw_path in raw_fields
            for mapped in [canonicalize_knowledge_path(raw_path, canonical_paths)]
            if mapped is not None
        }
    )
    unmapped_fields = sorted(
        raw_path
        for raw_path in raw_fields
        if canonicalize_knowledge_path(raw_path, canonical_paths) is None
    )
    return {
        "card_id": rule_card_id(str(rule["id"])),
        "kind": "deterministic_rule",
        "title": str(rule.get("name", rule["id"])),
        "source_rule_id": str(rule["id"]),
        "canonical_fields": canonical_fields,
        "evidence_groups": _evidence_groups(str(rule.get("category", ""))),
        "content": {
            "semantics": str(rule.get("trigger", "")),
            "trigger": str(rule.get("trigger", "")),
            "tolerance": str(rule.get("tolerance", "")),
            "reason_template": str(rule.get("risk_reason_template", "")),
        },
        "predicate": {
            "operator": "registry_controlled",
            "short_circuit": bool(rule.get("short_circuit", False)),
        },
        "provenance": {
            "source_refs": list(official.get("source_refs", [])),
            "official_card_refs": list(official.get("card_refs", [])),
            "evidence_strength": official.get("evidence_strength"),
            "inference_level": official.get("inference_level"),
            "unmapped_legacy_fields": unmapped_fields,
        },
        "applicability": "current",
        "status": "published",
        "version": kb_version,
    }


def load_rule_cards(path: Path = DEFAULT_RULE_KB) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    kb = load_rule_knowledge_base(path)
    rules = kb.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f"Rule knowledge base has no rules list: {path}")
    return kb, [adapt_rule(rule, kb.get("version")) for rule in rules]


def assert_pinned_rule_kb(predicate_registry: dict[str, Any], path: Path = DEFAULT_RULE_KB) -> str:
    expected = str(predicate_registry.get("rule_knowledge_base", {}).get("sha256", ""))
    actual = sha256_file(path)
    if not expected or expected != actual:
        raise KnowledgeDriftError(
            "The deterministic predicate registry was reviewed against a different rule KB hash; "
            "update and revalidate the registry before running."
        )
    return actual
