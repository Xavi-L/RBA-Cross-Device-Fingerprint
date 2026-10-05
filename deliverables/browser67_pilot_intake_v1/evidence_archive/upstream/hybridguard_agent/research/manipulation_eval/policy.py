"""Independent, fixed family-OR risk layer over verified original relations."""
from __future__ import annotations

import copy

from hybridguard_agent.research.manipulation_eval import provenance_revision as gates
from hybridguard_agent.research.manipulation_eval.contract import POLICY_VERSION, VERSION

DECISION_SCHEMA = "manipulation-decision-v2"
C_UNKNOWN = {"status": "UNKNOWN", "reason": "current_fields_do_not_prove_authorization_attack_or_intent",
             "attack_proven": False, "calibrated_attack_probability": None}


def gate_axes(scope, projection):
    # Reuse only the reviewed A/B gates. The bounded S03-R relation probe is
    # deliberately absent: outcomes come from the full original runtime.
    relation, operands = gates._relation_gate(scope, projection)
    eligibility = gates._risk_gate(scope, projection, relation, operands)
    return {"relation_applicability": relation, "risk_candidate_eligibility": eligibility,
            "attribution_certainty": copy.deepcopy(C_UNKNOWN)}


def build_events(runtime, contract, *, condition_id, catalog, failure=False):
    selected = set(contract["conditions"][condition_id]["rule_ids"])
    rules = {r["rule_id"]: r for r in catalog["rules"]}
    results = {r["rule_id"]: r for r in runtime["rule_execution"]["rule_results"]} if runtime else {}
    bundle = runtime["evidence_bundle"] if runtime else {"fields": {}, "projection": {}}
    events = []
    for rid, rule in rules.items():
        original = results.get(rid)
        role = contract["roles"].get(rid)
        active = rule["status"] == "ACTIVE"
        if active and role and runtime and not failure:
            axes = gate_axes(contract["scopes"][rid], bundle["projection"])
        else:
            axes = {"relation_applicability": {"status": "UNKNOWN" if failure else "NOT_APPLICABLE",
                                               "reason": "runtime_not_available" if failure else "outside_active_v2_contract"},
                    "risk_candidate_eligibility": {"status": "NOT_ELIGIBLE", "reason": "outside_active_v2_candidate_contract"},
                    "attribution_certainty": copy.deepcopy(C_UNKNOWN)}
        outcome = original["outcome"] if original else None
        decision_role = role["decision_role"] if active and role else "inactive_or_legacy_diagnostic"
        in_condition = active and rid in selected
        if failure:
            reason = "unit_failed_no_risk_participation"
        elif not in_condition:
            reason = "source_condition_excluded" if active and role else "outside_active_v2_contract"
        elif decision_role != "alert_candidate":
            reason = "role_not_risk_candidate"
        elif axes["relation_applicability"]["status"] != "SUPPORTED":
            reason = "relation_not_supported"
        elif axes["risk_candidate_eligibility"]["status"] != "ELIGIBLE":
            reason = "risk_not_eligible"
        elif outcome not in {"MATCH", "COUNTEREXAMPLE"}:
            reason = "original_relation_not_evaluated"
        else:
            reason = "qualifying_conflict" if outcome == "COUNTEREXAMPLE" else "qualifying_match"
        participates = reason in {"qualifying_conflict", "qualifying_match"}
        fields = rule["dependencies"]
        scope = contract["scopes"].get(rid, {})
        events.append({"rule_id": rid, "catalog_status": rule["status"],
                       "source_condition_included": in_condition, "original_outcome": outcome,
                       "original_result": copy.deepcopy(original),
                       "original_outcome_recorded": original is not None,
                       "original_source_lane": rule["source_lane"],
                       "provenance_group": role["provenance_group"] if role else None,
                       "original_evidence_family": rule["evidence_family"],
                       "decision_family": role["decision_family"] if role else None,
                       "decision_role": decision_role, "required_fields": fields,
                       "used_fields": original["used_fields"] if original else [],
                       "additional_risk_required_fields": scope.get("additional_risk_required_fields", []),
                       "field_states": {f: copy.deepcopy(bundle["fields"].get(f))
                                        for f in dict.fromkeys(fields + scope.get("additional_risk_required_fields", []))},
                       **axes, "participates_in_risk": participates,
                       "triggers_family": participates and outcome == "COUNTEREXAMPLE",
                       "participation_reason": reason,
                       "verification_valid": bool(runtime) and not failure,
                       "contract_version": VERSION})
    return events


def capable_families(contract, condition_id, catalog):
    active = {r["rule_id"] for r in catalog["rules"] if r["status"] == "ACTIVE"}
    return sorted({contract["roles"][rid]["decision_family"]
                   for rid in contract["conditions"][condition_id]["rule_ids"]
                   if rid in active and contract["roles"][rid]["decision_role"] == "alert_candidate"})


def decide(events, contract, *, condition_id, catalog, failure=False):
    capable = capable_families(contract, condition_id, catalog)
    evaluated = sorted({e["decision_family"] for e in events if e["participates_in_risk"]}) if not failure else []
    triggered = sorted({e["decision_family"] for e in events if e["triggers_family"]}) if not failure else []
    unavailable = sorted(set(capable) - set(evaluated))
    decision = ("FAILED" if failure else "MANIPULATION_ALERT" if triggered else
                "NO_ALERT" if evaluated else "INSUFFICIENT_EVIDENCE")
    reason = {"FAILED": "parse_runtime_or_verification_failure", "MANIPULATION_ALERT": "qualified_family_conflict",
              "NO_ALERT": "evaluated_candidate_families_without_conflict",
              "INSUFFICIENT_EVIDENCE": "no_candidate_family_evaluable"}[decision]
    return {"decision_schema_version": DECISION_SCHEMA, "contract_version": VERSION,
            "policy_version": POLICY_VERSION, "research_scope_id": gates.SCOPE_ID,
            "decision": decision, "alert_score": None if failure else len(triggered),
            "score_meaning": "count_of_distinct_qualifying_conflict_families_not_probability",
            "threshold": 1, "reason_codes": [reason],
            "eligible_family_count": len(capable), "eligible_family_ids": capable,
            "evaluated_family_count": len(evaluated), "evaluated_family_ids": evaluated,
            "triggered_family_ids": triggered, "unavailable_family_ids": unavailable,
            "partial_coverage": bool(capable) and len(evaluated) < len(capable),
            "family_coverage": len(evaluated) / len(capable) if capable else None,
            "verification_valid": not failure, "calibrated_attack_probability": None,
            "attribution_certainty": copy.deepcopy(C_UNKNOWN), "attack_classification": "NOT_EVALUATED",
            "claim_boundary": contract["policy"]["alert_meaning"]}
