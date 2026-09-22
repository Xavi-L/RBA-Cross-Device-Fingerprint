"""Curated versioned cards: current predicates and caveats, not old risk text."""
import json
from pathlib import Path


def runtime_cards(catalog):
    path = Path(__file__).resolve().parents[1] / "config/mtc_p3_semantic_sources.v1.json"
    sources = {s["id"]: s for s in json.loads(path.read_text())["sources"]}
    if catalog["catalog_version"] != "paired244-runtime-catalog-v1":
        sources.update({s["id"]: s for s in json.loads((path.parent / "paired244_review_sources.v1.json").read_text())["sources"]})
    if catalog["catalog_version"] == "paired244-runtime-catalog-v3":
        sources.update({s["id"]: s for s in json.loads((path.parent / "mtc_closed_resource_sources.v1.json").read_text())["sources"]})
    cards = {}
    for rule in catalog["rules"]:
        if rule["status"] != "ACTIVE":
            continue
        card_id = "P4-RULE-" + rule["rule_id"]
        cards[card_id] = {"card_id": card_id, "rule_id": rule["rule_id"], "title": rule["title"],
                          "canonical_fields": rule["dependencies"], "source_lane": rule["source_lane"],
                          "origin": rule["origin"], "version": rule["version"],
                          "predicate": rule["predicate"], "parameters": rule.get("parameters", {}),
                          "limitations": rule["limitations"],
                          "disposition": rule["disposition_reason"], "risk_use": "uncalibrated_observation_only",
                          "official_sources": [{"source_id": sid, "title": sources[sid]["title"], "url": sources[sid]["url"]}
                                               for sid in rule["official_source_ids"]],
                          "legacy_official_source_ids": rule.get("legacy_official_source_ids", [])}
    return cards
