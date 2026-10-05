"""Full244/App177 execution, exact retrieval, verifier and deterministic trace."""
from hybridguard_agent.evidence.extractor import sha256_value
from hybridguard_agent.evidence.paired244 import build_paired_evidence
from hybridguard_agent.retrieval.paired244 import build_paired_context
from hybridguard_agent.rules.paired244 import execute_paired_rules, load_catalog, paired_decision
from hybridguard_agent.verification.paired244 import verify_paired_output


def analyze_paired244_record(record, *, input_view="Full244", catalog=None):
    selected_catalog = catalog if catalog is not None else load_catalog()
    bundle = build_paired_evidence(record, input_view)
    execution = execute_paired_rules(bundle, selected_catalog)
    context = build_paired_context(bundle, execution, selected_catalog)
    decision = paired_decision(execution)
    verification = verify_paired_output(bundle, execution, context, decision, selected_catalog)
    if not verification["valid"]:
        raise ValueError("Paired runtime output failed verification: " + ", ".join(verification["errors"]))
    decision_id = "paired-decision-" + sha256_value({"evidence": bundle["evidence_hash"], "catalog": execution["catalog_digest"]})[:24]
    active = {r["rule_id"] for r in selected_catalog["rules"] if r["status"] == "ACTIVE"}
    trace = {"decision_trace_version": "decision-trace-v2-paired244", "decision_id": decision_id,
             "evidence_hash": bundle["evidence_hash"], "input_view": input_view,
             "versions": {"evidence": bundle["evidence_bundle_version"], "catalog": selected_catalog["catalog_version"],
                          "catalog_digest": execution["catalog_digest"], "executor": execution["execution_version"],
                          "retrieval": context["context_pack_version"], "verifier": verification["verifier_version"]},
             "citations": {"rule_ids": [r["rule_id"] for r in execution["rule_results"] if r["rule_id"] in active],
                           "card_ids": [c["card_id"] for c in context["cards"]], "field_ids": context["query_fields"]},
             "rule_execution": execution, "decision": decision, "verification": verification,
             "fusion": {"enabled": False, "reason": "No independent calibration; shared evidence families are not summed."},
             "runtime": {"external_model_called": False, "raw_source_modified": False, "decision_persisted": False}}
    trace["versions"]["browser_relation_policy"] = "paired244-browser-relation-policy-" + selected_catalog["catalog_version"].rsplit("-", 1)[1]
    return {"response_schema_version": "agent-runtime-response-v2-paired244", "status": "completed",
            "decision_id": decision_id, "decision": decision, "evidence_bundle": bundle,
            "rule_execution": execution, "context_pack": context, "decision_trace": trace}


def paired_runtime_readiness(*, catalog=None):
    from collections import Counter
    catalog = catalog if catalog is not None else load_catalog()
    return {"runtime_version": "paired244-runtime-" + catalog["catalog_version"].rsplit("-", 1)[1], "status": "ready",
            "input_contract": "hybridguard-mtc-observation-v2", "catalog_version": catalog["catalog_version"],
            "catalog_entries": len(catalog["rules"]), "entry_status_counts": dict(Counter(r["status"] for r in catalog["rules"])),
            "external_model_called": False, "reserved_validation": "MANAGED_BY_EXPERIMENT_PROTOCOL",
            "reserved_access_granted_by_runtime": False, "detection_metrics": "NOT_EVALUATED"}
