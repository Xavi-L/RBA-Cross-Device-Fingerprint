"""Recheck original Verifier, evidence references, v2 gates and risk arithmetic."""
from hybridguard_agent.verification.paired244 import verify_paired_output
from hybridguard_agent.research.manipulation_eval.policy import build_events, capable_families


def verify_policy_output(runtime, events, decision, contract, *, condition_id, catalog):
    from hybridguard_agent.research.manipulation_eval.schemas import RISK, validate_schema
    try:
        validate_schema(decision, RISK)
        schema_valid = True
    except ValueError:
        schema_valid = False
    original = verify_paired_output(runtime["evidence_bundle"], runtime["rule_execution"],
                                    runtime["context_pack"], runtime["decision"], catalog)
    expected_events = build_events(runtime, contract, condition_id=condition_id, catalog=catalog)
    capable = set(capable_families(contract, condition_id, catalog))
    evaluated, triggered = set(), set()
    for e in expected_events:
        if e["participates_in_risk"]:
            evaluated.add(e["decision_family"])
            if e["original_outcome"] == "COUNTEREXAMPLE":
                triggered.add(e["decision_family"])
    expected = "MANIPULATION_ALERT" if triggered else "NO_ALERT" if evaluated else "INSUFFICIENT_EVIDENCE"
    reasons = {"MANIPULATION_ALERT": "qualified_family_conflict", "NO_ALERT": "evaluated_candidate_families_without_conflict",
               "INSUFFICIENT_EVIDENCE": "no_candidate_family_evaluable"}
    checks = {"closed_risk_schema": schema_valid,
              "bounded_meaning_and_reasons": decision["reason_codes"] == [reasons[expected]]
                and decision["claim_boundary"] == contract["policy"]["alert_meaning"] and decision["verification_valid"] is True,
              "original_verifier_valid": original["valid"], "complete_events_and_gate_evidence": events == expected_events,
              "family_selection_and_deduplication": decision["eligible_family_ids"] == sorted(capable)
                and decision["evaluated_family_ids"] == sorted(evaluated) and decision["triggered_family_ids"] == sorted(triggered)
                and decision["unavailable_family_ids"] == sorted(capable - evaluated),
              "counts_score_threshold_and_decision": decision["eligible_family_count"] == len(capable)
                and decision["evaluated_family_count"] == len(evaluated) and decision["alert_score"] == len(triggered)
                and decision["threshold"] == 1 and decision["decision"] == expected,
              "coverage": decision["partial_coverage"] == (bool(capable) and len(evaluated) < len(capable))
                and decision["family_coverage"] == (len(evaluated) / len(capable) if capable else None),
              "no_attack_attribution_or_probability": decision["attribution_certainty"]["status"] == "UNKNOWN"
                and decision["attribution_certainty"]["attack_proven"] is False
                and decision["attribution_certainty"]["calibrated_attack_probability"] is None
                and decision["calibrated_attack_probability"] is None and decision["attack_classification"] == "NOT_EVALUATED",
              "original_protective_decision_retained": runtime["decision"]["attack_classification"] == "NOT_EVALUATED"
                and runtime["decision"]["calibrated_risk_score"] is None,
              "explicit_version": decision["contract_version"] == contract["version"]
                and decision["policy_version"] == contract["policy"]["policy_version"]}
    return {"verifier_version": "formal-risk-verifier-v2", "valid": all(checks.values()), "checks": checks,
            "original_verification": original, "errors": [k for k, v in checks.items() if not v]}
