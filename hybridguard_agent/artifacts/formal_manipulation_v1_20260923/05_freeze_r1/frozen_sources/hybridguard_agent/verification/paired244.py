"""Verify source-qualified citations and recompute the bounded offline decision."""
from hybridguard_agent.evidence.extractor import sha256_value
from hybridguard_agent.evidence.paired244 import VERSION, VIEWS, field_contract, surface_of
from hybridguard_agent.retrieval.paired244 import build_paired_context
from hybridguard_agent.rules.paired244 import execute_paired_rules, paired_decision


def verify_paired_output(bundle, execution, context, decision, catalog):
    expected_keys = {"evidence_bundle_version", "extractor_version", "input_view", "selected_surfaces", "present_surfaces",
                     "pair_admitted", "projection", "fields", "derived_facts", "boundary", "evidence_hash", "sample_id"}
    content = {k: v for k, v in bundle.items() if k not in {"evidence_hash", "sample_id"}}
    known = set(field_contract())
    fields = set(bundle["fields"])
    checks = {
        "evidence_contract_and_no_control_fields": set(bundle) == expected_keys and bundle["evidence_bundle_version"] == VERSION,
        "evidence_content_binding": sha256_value(content) == bundle["evidence_hash"],
        "fingerprint_projection_only": set(bundle["projection"]) == {"features", "field_status", "field_quality"}
            and all(set(v) == fields for v in bundle["projection"].values()) and fields <= known,
        "view_mask_precedes_execution": bundle["input_view"] in VIEWS
            and all(surface_of(p) in VIEWS[bundle["input_view"]] for p in fields),
        "field_references_are_surface_qualified": all(set(r["required_fields"]) <= known and
            all(p in fields and bundle["fields"][p]["available"] for p in r["used_fields"])
            for r in execution["rule_results"]),
        "browser_evidence_requires_pair_admission": bundle["pair_admitted"] or not any(
            p.startswith("browser.") for r in execution["rule_results"] for p in r["used_fields"]),
        "parsed_fact_sources_in_view": all(set(f["source_fields"]) <= fields for f in bundle["derived_facts"].values()),
        "execution_matches_evidence_and_catalog": execution == execute_paired_rules(bundle, catalog),
        "citations_and_cards_match_current_rules": context == build_paired_context(bundle, execution, catalog),
        "decision_matches_execution": decision == paired_decision(execution),
        "uncalibrated_no_attack_verdict": decision.get("calibrated_risk_score") is None
            and decision.get("attack_classification") == "NOT_EVALUATED" and "risk_score" not in decision,
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {"verifier_version": "paired244-verifier-v1", "valid": not errors, "checks": checks, "errors": errors}
