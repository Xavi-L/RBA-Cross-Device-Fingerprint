"""Exact current-rule retrieval, preserving App/Browser-qualified field paths."""
from hybridguard_agent.adapters.paired244_catalog import runtime_cards


def build_paired_context(bundle, execution, catalog):
    cards = runtime_cards(catalog)
    active = {r["rule_id"] for r in catalog["rules"] if r["status"] == "ACTIVE"}
    relevant = [r for r in execution["rule_results"] if r["rule_id"] in active]
    return {"context_pack_version": "paired244-context-pack-v1", "catalog_version": catalog["catalog_version"],
            "evidence_hash": bundle["evidence_hash"],
            "query_fields": sorted({p for r in relevant for p in r["used_fields"]}),
            "cards": [cards[r["card_id"]] for r in relevant],
            "excluded_rule_ids": [r["rule_id"] for r in execution["rule_results"] if r["rule_id"] not in active],
            "empirical_cases_enabled": False, "control_plane_inputs_used": False,
            "retrieval_policy": "All active exact-rule cards retained, including unevaluated limitations; no truncation hides cited checks. Required but absent fields are not observed-query fields."}
