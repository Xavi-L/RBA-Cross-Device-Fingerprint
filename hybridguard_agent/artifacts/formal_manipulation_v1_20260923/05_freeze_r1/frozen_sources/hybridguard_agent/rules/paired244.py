"""Execute versioned paired244 checks with explicit surfaces and dispositions."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from hybridguard_agent.adapters.rule_kb_adapter import assert_pinned_rule_kb
from hybridguard_agent.evidence.extractor import _derived_facts, normalize_payload, sha256_value
from hybridguard_agent.evidence.paired244 import field_contract, legacy_payload
from hybridguard_agent.official_semantics.evaluator import _evaluate_compiled
from hybridguard_agent.research.mtc_p3_candidates import evaluate_candidate
from hybridguard_agent.rules.executor import _evaluate
from hybridguard_agent.rules.legacy_backlog import IMPLEMENTATION, evaluate_reviewed_rule
from hybridguard_agent.research.mtc_closed_resource import IMPLEMENTATION as CLOSED_IMPLEMENTATION, evaluate as evaluate_closed

CONFIG = Path(__file__).resolve().parents[1] / "config"
LEGACY_CATALOG = CONFIG / "paired244_rule_catalog.v1.json"
V2_CATALOG = CONFIG / "paired244_rule_catalog.v2.json"
DEFAULT_CATALOG = CONFIG / "paired244_rule_catalog.v3.json"
CATALOG_POLICIES = {"paired244-runtime-catalog-v1": "paired244_browser_relations.v1.json",
                    "paired244-runtime-catalog-v2": "paired244_browser_relations.v2.json",
                    "paired244-runtime-catalog-v3": "paired244_browser_relations.v3.json"}
INACTIVE_OUTCOMES = {"RETIRED": "DISABLED", "NOT_IMPLEMENTED": "NOT_IMPLEMENTED",
                     "NEEDS_RESEARCH": "PENDING_RESEARCH", "NEEDS_DATA": "PENDING_DATA", "MERGED": "MERGED",
                     "DESCRIPTIVE_ONLY": "DESCRIPTIVE_ONLY", "CLOSED_UNVERIFIABLE": "CLOSED_UNVERIFIABLE"}


def load_catalog(path=DEFAULT_CATALOG):
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if catalog.get("catalog_version") not in CATALOG_POLICIES:
        raise ValueError("Unsupported paired244 catalog")
    ids = [r["rule_id"] for r in catalog["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate runtime rule ID")
    for rule in catalog["rules"]:
        if not set(rule["dependencies"]) <= set(field_contract()):
            raise ValueError("Rule references an unknown evidence field")
        if rule.get("standalone_attack_decision") is not False or rule.get("risk_weight") is not None:
            raise ValueError("P4 catalog cannot assign attack labels or risk weights")
        if rule["status"] not in {"ACTIVE", *INACTIVE_OUTCOMES}:
            raise ValueError("Unknown catalog disposition")
        if rule.get("implementation") == IMPLEMENTATION and rule["status"] != "ACTIVE":
            raise ValueError("Reviewed implementation must be explicitly active")
        if catalog["catalog_version"].endswith("-v3") and rule["status"] in {"NOT_IMPLEMENTED", "NEEDS_DATA", "NEEDS_RESEARCH"}:
            raise ValueError("Closed-resource catalog cannot retain pending work")
    assert_pinned_rule_kb({"rule_knowledge_base": catalog["legacy_kb_binding"]})
    policy = json.loads((CONFIG / CATALOG_POLICIES[catalog["catalog_version"]]).read_text())
    expected_browser = {r["rule_id"]: r["dependencies"] for r in catalog["rules"]
                        if r["status"] == "ACTIVE" and any(p.startswith("browser.") for p in r["dependencies"])}
    if (policy.get("catalog_version") != catalog["catalog_version"] or
            {r["rule_id"]: r["dependencies"] for r in policy["active_browser_relations"]} != expected_browser):
        raise ValueError("Browser relation policy drifted from the runtime catalog")
    return catalog


def execute_paired_rules(bundle, catalog):
    projection = bundle["projection"]
    results = []
    for rule in catalog["rules"]:
        refs = rule["dependencies"]
        result = {"rule_id": rule["rule_id"], "source_lane": rule["source_lane"],
                  "origin": rule["origin"], "evidence_family": rule["evidence_family"],
                  "predicate": rule["predicate"], "rule_version": rule["version"],
                  "required_fields": refs, "used_fields": [], "card_id": "P4-RULE-" + rule["rule_id"],
                  "outcome": "NOT_EVALUATED", "reason": "", "availability_issues": []}
        if rule["status"] != "ACTIVE":
            result.update(outcome=INACTIVE_OUTCOMES[rule["status"]],
                          reason=rule["disposition_reason"])
            if catalog["catalog_version"].endswith("-v3") and "resolution_note" in rule:
                result.update(resolution_note=rule["resolution_note"],
                              related_or_replacement_ids=rule.get("related_or_replacement_ids", []))
            elif rule["status"] in {"NEEDS_DATA", "NEEDS_RESEARCH", "MERGED"}:
                result.update(next_action=rule["next_action_and_acceptance"],
                              related_or_replacement_ids=rule["related_or_replacement_ids"],
                              uncollected_or_derived_fields=rule["uncollected_or_derived_fields"])
            results.append(result)
            continue
        issues = [{"field": p, "reason": "field_or_surface_not_in_input_view" if p not in bundle["fields"]
                   else bundle["fields"][p]["unavailable_reason"]}
                  for p in refs if p not in bundle["fields"] or not bundle["fields"][p]["available"]]
        if issues:
            result.update(reason="required_evidence_unavailable", availability_issues=issues)
            results.append(result)
            continue
        # Each predicate sees only its own declared dependencies, including status.
        restricted = {k: {p: projection[k][p] for p in refs} for k in projection}
        normalized, states = normalize_payload(legacy_payload(restricted))
        facts = _derived_facts(normalized, states)
        if rule.get("implementation") == CLOSED_IMPLEMENTATION:
            result.update(evaluate_closed(rule, restricted))
        elif rule.get("implementation") == IMPLEMENTATION:
            result.update(evaluate_reviewed_rule(rule, restricted))
        elif rule["origin"] == "p3_research":
            raw = evaluate_candidate(rule, restricted)
            result.update(outcome=raw["outcome"], reason=raw["reason"])
            if "absolute_css_pixel_residual" in raw:
                result["absolute_css_pixel_residual"] = raw["absolute_css_pixel_residual"]
        elif rule["predicate"] == "featureapp_bridge_only_v2":
            value = restricted["features"][refs[0]]
            result.update(outcome="MATCH" if value is True else "COUNTEREXAMPLE" if value is False else "UNKNOWN",
                          reason="bridge_presence_only_sensor_count_is_not_a_veto")
        elif rule["origin"] == "legacy_device":
            spec = copy.deepcopy(rule["legacy_spec"])
            spec["short_circuit"] = False
            raw = _evaluate({"id": rule["rule_id"]}, spec, facts)
            result.update(outcome={"matched": "COUNTEREXAMPLE", "not_matched": "MATCH", "context_observed": "CONTEXT_OBSERVED",
                                   "unknown": "UNKNOWN", "unavailable": "NOT_EVALUATED"}[raw["outcome"]], reason=raw["detail"])
        elif rule["origin"] == "legacy_official":
            raw = _evaluate_compiled(rule["legacy_relation"], normalized, states, facts)
            result.update(outcome={"consistent": "MATCH", "inconsistent": "COUNTEREXAMPLE", "context_observed": "CONTEXT_OBSERVED",
                                   "not_applicable": "NOT_APPLICABLE", "unknown": "UNKNOWN", "unavailable": "NOT_EVALUATED"}[raw["outcome"]],
                          reason=raw["detail"])
        else:
            raise ValueError("Unknown rule implementation")
        result["used_fields"] = list(refs)
        results.append(result)
    return {"execution_version": "paired244-rule-execution-" + catalog["catalog_version"].rsplit("-", 1)[1],
            "catalog_version": catalog["catalog_version"],
            "catalog_digest": sha256_value(catalog), "evidence_hash": bundle["evidence_hash"], "rule_results": results,
            "short_circuit_enabled": False, "risk_scoring_enabled": False}


def paired_decision(execution):
    results = execution["rule_results"]
    relations = [r["rule_id"] for r in results if r["outcome"] == "COUNTEREXAMPLE" and r["source_lane"] != "collector_derived_consistency"]
    collector = [r["rule_id"] for r in results if r["outcome"] == "COUNTEREXAMPLE" and r["source_lane"] == "collector_derived_consistency"]
    uncertain = [r["rule_id"] for r in results if r["outcome"] in {"UNKNOWN", "NOT_EVALUATED"}]
    context = [r["rule_id"] for r in results if r["outcome"] == "CONTEXT_OBSERVED"]
    status = ("relation_deviation_observed" if relations else "collector_consistency_issue" if collector
              else "partially_assessed" if uncertain else "context_observed" if context else "no_deviation_observed")
    decision = {"decision_version": "paired244-observation-decision-v1", "decision_status": status,
            "relation_deviation_rule_ids": relations, "collector_issue_rule_ids": collector,
            "unknown_or_not_evaluated_rule_ids": uncertain, "context_rule_ids": context,
            "not_applicable_rule_ids": [r["rule_id"] for r in results if r["outcome"] == "NOT_APPLICABLE"],
            "deviation_evidence_families": sorted({r["evidence_family"] for r in results if r["rule_id"] in relations}),
            "calibrated_risk_score": None, "calibration_status": "not_available", "attack_classification": "NOT_EVALUATED",
            "claim_boundary": "Checks are not independent votes. Deviations, context, missing data and no observed deviation are not attack/benign labels or detection-performance evidence."}
    if execution["catalog_version"] != "paired244-runtime-catalog-v1":
        policies = [r["rule_id"] for r in results if r["outcome"] == "POLICY_MISMATCH"]
        decision.update(decision_version="paired244-observation-decision-v2",
                        deployment_policy_mismatch_rule_ids=policies,
                        deployment_policy_evidence_families=sorted({r["evidence_family"] for r in results if r["rule_id"] in policies}),
                        pending_research_rule_ids=[r["rule_id"] for r in results if r["outcome"] == "PENDING_RESEARCH"],
                        pending_data_rule_ids=[r["rule_id"] for r in results if r["outcome"] == "PENDING_DATA"],
                        merged_rule_ids=[r["rule_id"] for r in results if r["outcome"] == "MERGED"],
                        retired_rule_ids=[r["rule_id"] for r in results if r["outcome"] == "DISABLED"],
                        catalog_fully_assessed=False)
        if policies and not relations and not collector:
            decision["decision_status"] = "deployment_policy_mismatch_observed"
        if execution["catalog_version"].endswith("-v3"):
            decision.update(decision_version="paired244-observation-decision-v3",
                            descriptive_only_rule_ids=[r["rule_id"] for r in results if r["outcome"] == "DESCRIPTIVE_ONLY"],
                            closed_unverifiable_rule_ids=[r["rule_id"] for r in results if r["outcome"] == "CLOSED_UNVERIFIABLE"],
                            catalog_dispositions_complete=True, collection_requested=False,
                            research_backlog_open=False)
    return decision
