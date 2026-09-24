"""Bounded legacy-input diagnostic; never part of the MTC denominator."""
from collections import Counter
from pathlib import Path

from hybridguard_agent.evidence.extractor import normalize_payload
from hybridguard_agent.evidence.paired244 import legacy_field_map, field_contract, valid_type
from hybridguard_agent.research.mtc_p6 import write_json, pack_result
from hybridguard_agent.runtime.paired244 import analyze_paired244_record
from hybridguard_agent.scripts.run_mtc_legacy_rule_baseline import evaluate_record
from hybridguard_agent.rules.executor import load_predicate_registry
from hybridguard_agent.adapters.rule_kb_adapter import load_rule_knowledge_base
from hybridguard_agent.official_semantics.evaluator import load_semantic_catalog


def legacy_row(payload):
    explicit = payload.get("collection_status", {}).get("fields")
    if not isinstance(explicit, dict) or len(explicit) != 177:
        raise ValueError("No complete explicit App177 field-status contract; do not infer observed from old values")
    normalized, states = normalize_payload(payload)
    mapping, contract = legacy_field_map(), field_contract()
    features, status, quality = {}, {}, {}
    for alias, path in mapping.items():
        layer, leaf = alias.split(".")
        value = normalized[layer].get(leaf)
        state = states.get(alias)
        features[path], status[path] = value, state
        quality[path] = "observed_value" if state == "observed" and valid_type(value, contract[path]) else "source_unavailable"
        if path.endswith((".device_memory", ".hardware_concurrency")) and value == 0 and state == "observed":
            quality[path] = "ambiguous_sentinel"
    return {"record_schema_version": "hybridguard-mtc-observation-v2", "features": features,
            "field_status": status, "field_quality": quality, "sample_id": "legacy-diagnostic-only"}


def run_history(output, protocol, spec):
    from hybridguard_agent.validation_inputs import resolve_attack_inputs
    from hybridguard_agent.scripts.run_two_source_rule_classification import load_attack_pairs
    from hybridguard_agent.scripts.run_mtc_p6 import ROOT, jsonl
    report = {"part_of_mtc_cohort": False, "detection_metrics": "NOT_EVALUATED", "new_data_requested": False,
              "legacy_outcomes_used_as_targets": False, "browser_pairing_created": False,
              "source_scope": protocol["historical_diagnostic"]["input_set"],
              "boundary": "Compatibility and output-change diagnostic only; old execution annotations are not fresh ground truth."}
    try:
        selection = resolve_attack_inputs(input_set_path=ROOT / protocol["historical_diagnostic"]["input_set"])
        pairs = load_attack_pairs(selection.manifests)
    except (ValueError, FileNotFoundError, OSError) as exc:
        report.update(status="CLOSED_INPUTS_UNAVAILABLE_OR_INCOMPATIBLE", reason=f"{type(exc).__name__}: {exc}")
        write_json(output / "historical_diagnostic.json", report)
        return report
    registry, kb, catalog = load_predicate_registry(), load_rule_knowledge_base(), load_semantic_catalog()
    skipped, failures, completed, changes = [], [], 0, Counter()
    conversion = {"matched": "COUNTEREXAMPLE", "inconsistent": "COUNTEREXAMPLE", "not_matched": "MATCH",
                  "consistent": "MATCH", "context_observed": "CONTEXT_OBSERVED", "not_applicable": "NOT_APPLICABLE",
                  "unknown_availability_gate": "UNKNOWN", "unknown": "UNKNOWN", "unavailable": "NOT_EVALUATED",
                  "not_evaluated": "NOT_EVALUATED"}
    with (output / "historical_stage_results.jsonl").open("w") as stream:
        for pair in pairs:
            if pair["eligibility_issues"]:
                skipped.append({"pair_ref": pair["pair_ref"], "reasons": pair["eligibility_issues"]})
                continue
            try:
                stage_rows = {stage: legacy_row(pair[stage]["raw_payload"]) for stage in ("baseline", "attack_active")}
            except ValueError as exc:
                skipped.append({"pair_ref": pair["pair_ref"], "reasons": [str(exc)]})
                continue
            for stage, row in stage_rows.items():
                try:
                    prior, _ = evaluate_record(row, registry, kb, catalog)
                    output_v3 = analyze_paired244_record(row, input_view="App177", catalog=spec["catalog_object"])
                    current, _ = pack_result(output_v3, spec)
                    old = {item.get("rule_id", item.get("relation_id")): conversion.get(item["outcome"], "UNKNOWN")
                           for modes in prior.values() for item in modes["availability_gated_diagnostic"]}
                    differences = [{"rule_id": rid, "old": state, "new": current["rule_outcomes"][rid]}
                                   for rid, state in old.items() if rid in current["rule_outcomes"]
                                   and state != current["rule_outcomes"][rid]]
                    changes.update(r["rule_id"] for r in differences)
                    jsonl(stream, {"pair_ref": pair["pair_ref"], "stage": stage, "status": "COMPLETE",
                                   "gated_legacy_outcomes": old, "current": current, "common_id_changes": differences})
                    completed += 1
                except Exception as exc:
                    failure = {"pair_ref": pair["pair_ref"], "stage": stage, "status": "FAILED", "error": str(exc)}
                    failures.append(failure); jsonl(stream, failure)
    report.update(status="DESCRIPTIVE_REPLAY_COMPLETE" if completed and not failures else
                  "COMPLETE_WITH_FAILURES" if failures else "CLOSED_NO_COMPARABLE_EXPLICIT_FIELD_STATUS",
                  selected_manifests=len(selection.manifests), selected_pairs=len(pairs), completed_stages=completed,
                  excluded_pairs=skipped, failures=failures, common_id_change_counts=dict(changes))
    write_json(output / "historical_diagnostic.json", report)
    return report
