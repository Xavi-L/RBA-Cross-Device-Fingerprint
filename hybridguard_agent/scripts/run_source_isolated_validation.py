#!/usr/bin/env python3
"""Run source-isolated validation for official cards and device-mined rules.

This is deliberately a second, separate run from the two-source package.  It
does not overwrite or reinterpret that package:

* the official-document lane reads only official cards and reports field
  applicability/coverage; it never borrows a project threshold to emit an
  alert; and
* the device-mined lane runs only the frozen deterministic project predicates;
  official cards are not retrieved or used in its decision.

Both lanes receive the same normal records and the same two-state
``baseline -> attack_active`` pairs.  Historical ``clean_post`` remains out
of scope.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.adapters.official_kb_adapter import (  # noqa: E402
    DEFAULT_OFFICIAL_CARDS,
    load_official_cards,
    sha256_file as official_sha256_file,
)
from hybridguard_agent.adapters.rule_kb_adapter import (  # noqa: E402
    DEFAULT_RULE_KB,
    load_rule_knowledge_base,
    sha256_file as rule_sha256_file,
)
from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2, normalize_payload  # noqa: E402
from hybridguard_agent.rules.executor import execute_deterministic_rules, load_predicate_registry  # noqa: E402
from hybridguard_agent.scripts.run_two_source_rule_classification import (  # noqa: E402
    ALERT_DECISION_STATUSES,
    TWO_STATE_PROTOCOL_VERSION,
    direct_feature_comparison,
    load_attack_pairs,
    read_jsonl,
    repo_relative,
    stable_sample_id,
)
from hybridguard_agent.validation_inputs import (  # noqa: E402
    AttackInputSelection,
    attach_and_validate_observed_counts,
    resolve_attack_inputs,
)


SOURCE_ISOLATED_VALIDATION_VERSION = "source-isolated-validation-v1"
OFFICIAL_DOCUMENT = "official_document"
DEVICE_MINED_RULE = "device_mined_rule"

OFFICIAL_NORMAL_FILENAME = "official_document_normal_results.jsonl"
OFFICIAL_ATTACK_FILENAME = "official_document_attack_pair_results.jsonl"
OFFICIAL_SUMMARY_FILENAME = "official_document_card_summary.csv"
DEVICE_NORMAL_FILENAME = "device_mined_normal_results.jsonl"
DEVICE_ATTACK_FILENAME = "device_mined_attack_pair_results.jsonl"
DEVICE_RULE_SUMMARY_FILENAME = "device_mined_rule_summary.csv"
MANIFEST_FILENAME = "source_isolated_validation_manifest.json"
REPORT_FILENAME = "两类知识独立验证报告.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--normal-input", required=True, type=Path)
    attack_inputs = parser.add_mutually_exclusive_group()
    attack_inputs.add_argument(
        "--attack-manifest", action="append", default=[], type=Path
    )
    attack_inputs.add_argument("--attack-input-set", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def normalized_field_value(normalized: dict[str, Any], canonical_path: str) -> Any:
    layer_name, separator, leaf_name = canonical_path.partition(".")
    if not separator:
        return None
    layer = normalized.get(layer_name)
    if not isinstance(layer, dict) or leaf_name not in layer:
        return None
    return layer[leaf_name]


def official_card_assessments(payload: dict[str, Any], official_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assess only whether official-card fields are present and usable.

    The card source gives field semantics, tolerance and future official
    evidence paths, but deliberately contains no project-independent trigger
    predicate.  This function therefore returns coverage, never a risk alert.
    """

    normalized, field_status = normalize_payload(payload)
    rows: list[dict[str, Any]] = []
    for card in official_cards:
        fields = list(card.get("canonical_fields", []))
        applicability = str(card.get("applicability", "current"))
        observed_count = 0
        unavailable_count = 0
        missing_or_unknown_count = 0
        for field_path in fields:
            value = normalized_field_value(normalized, field_path)
            status = field_status.get(field_path)
            if status is not None and status != "observed":
                unavailable_count += 1
            elif value is None or value == "":
                missing_or_unknown_count += 1
            else:
                observed_count += 1
        if applicability == "future_only":
            coverage_status = "future_only_not_collected"
        elif not fields:
            coverage_status = "no_current_contract_fields"
        elif observed_count == len(fields):
            coverage_status = "fully_observed"
        elif observed_count == 0:
            coverage_status = "not_observed"
        else:
            coverage_status = "partially_observed"
        rows.append(
            {
                "official_card_id": card["card_id"],
                "source_card_id": card["source_card_id"],
                "applicability": applicability,
                "canonical_field_count": len(fields),
                "observed_field_count": observed_count,
                "unavailable_field_count": unavailable_count,
                "missing_or_unknown_field_count": missing_or_unknown_count,
                "coverage_status": coverage_status,
                "independent_alert": None,
                "decision_boundary": "no_independent_official_document_predicate_in_current_kb",
            }
        )
    return rows


def official_record(
    *,
    run_id: str,
    payload: dict[str, Any],
    sample_id: str,
    record_kind: str,
    stage: str,
    input_path: Path,
    input_line: int,
    official_cards: list[dict[str, Any]],
    pair_ref: str | None = None,
) -> dict[str, Any]:
    session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
    cards = official_card_assessments(payload, official_cards)
    return {
        "source_isolated_validation_version": SOURCE_ISOLATED_VALIDATION_VERSION,
        "run_id": run_id,
        "knowledge_source_type": OFFICIAL_DOCUMENT,
        "record_kind": record_kind,
        "stage": stage,
        "pair_ref": pair_ref,
        "sample_id": sample_id,
        "source_session_id": session_id,
        "input_ref": f"{repo_relative(input_path)}#line={input_line}",
        "official_document_decision": {
            "decision_status": "not_independently_evaluable",
            "alert": None,
            "independent_predicate_count": 0,
            "reason": "Current official cards provide semantics/tolerance or future official attestation paths, not executable alarm conditions.",
        },
        "card_assessments": cards,
    }


def device_mined_decision(evidence_bundle: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    """Decide from project predicates only, without official-card retrieval."""

    matched = list(execution.get("matched_rule_ids", []))
    context = list(execution.get("tolerance_or_context_rule_ids", []))
    short_circuit = list(execution.get("short_circuit_status", {}).get("matched_rule_ids", []))
    unknown = [
        result["rule_id"]
        for result in execution.get("rule_results", [])
        if result.get("outcome") in {"unknown", "unavailable"}
    ]
    unevaluated_mandatory = list(
        execution.get("short_circuit_status", {}).get("unevaluated_mandatory_rule_ids", [])
    )
    if short_circuit:
        decision_status = "manual_review_required"
        conclusion = "deterministic_core_condition_observed"
    elif matched:
        decision_status = "inconsistency_observed"
        conclusion = "deterministic_inconsistency_observed"
    elif unknown or unevaluated_mandatory:
        decision_status = "insufficient_evidence"
        conclusion = "not_assessed"
    elif context:
        decision_status = "context_observed"
        conclusion = "collection_or_development_context_observed"
    else:
        decision_status = "completed"
        conclusion = "no_compiled_condition_observed"
    return {
        "decision_status": decision_status,
        "conclusion": conclusion,
        "alert": decision_status in ALERT_DECISION_STATUSES,
        "matched_rule_ids": matched,
        "context_rule_ids": context,
        "unknown_or_unavailable_rule_ids": unknown,
        "unevaluated_mandatory_rule_ids": unevaluated_mandatory,
        "evidence_hash": evidence_bundle["evidence_hash"],
        "calibrated_risk_score": None,
        "decision_boundary": (
            "Only deterministic device_mined_rule predicates were used. Official cards, labels, "
            "attack-tool metadata and calibrated scores were excluded from this decision."
        ),
    }


def device_mined_record(
    *,
    run_id: str,
    payload: dict[str, Any],
    sample_id: str,
    record_kind: str,
    stage: str,
    input_path: Path,
    input_line: int,
    pair_ref: str | None = None,
) -> dict[str, Any]:
    evidence_bundle = build_evidence_bundle_v2(payload, sample_id=sample_id)
    execution = execute_deterministic_rules(evidence_bundle)
    session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
    return {
        "source_isolated_validation_version": SOURCE_ISOLATED_VALIDATION_VERSION,
        "run_id": run_id,
        "knowledge_source_type": DEVICE_MINED_RULE,
        "record_kind": record_kind,
        "stage": stage,
        "pair_ref": pair_ref,
        "sample_id": sample_id,
        "source_session_id": session_id,
        "input_ref": f"{repo_relative(input_path)}#line={input_line}",
        "decision": device_mined_decision(evidence_bundle, execution),
        "rule_execution": execution,
    }


def compact_device_decision(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    decision = record["decision"]
    return {
        "sample_id": record["sample_id"],
        "decision_status": decision["decision_status"],
        "conclusion": decision["conclusion"],
        "alert": decision["alert"],
        "matched_rule_ids": decision["matched_rule_ids"],
        "context_rule_ids": decision["context_rule_ids"],
        "unknown_or_unavailable_rule_ids": decision["unknown_or_unavailable_rule_ids"],
        "unevaluated_mandatory_rule_ids": decision["unevaluated_mandatory_rule_ids"],
        "evidence_hash": decision["evidence_hash"],
        "rule_outcomes": rule_outcomes(record),
    }


def annotation_summaries(active_member: dict[str, Any] | None) -> list[dict[str, Any]]:
    if active_member is None:
        return []
    manifest = active_member["manifest"]
    attack = manifest.get("attack") if isinstance(manifest.get("attack"), dict) else {}
    mutations = attack.get("observed_mutations") if isinstance(attack, dict) else []
    if not isinstance(mutations, list):
        return []
    return [
        {"field_path": item.get("field_path"), "change_summary": item.get("change_summary")}
        for item in mutations
        if isinstance(item, dict)
    ]


def tool_reference(active_member: dict[str, Any] | None) -> dict[str, Any]:
    if active_member is None:
        return {}
    manifest = active_member["manifest"]
    attack = manifest.get("attack") if isinstance(manifest.get("attack"), dict) else {}
    if not isinstance(attack, dict):
        attack = {}
    return {
        "tool_name": attack.get("tool_name"),
        "tool_version": attack.get("tool_version"),
        "attack_family": attack.get("attack_family"),
        "attack_type": attack.get("attack_type"),
        "config_id": attack.get("config_id"),
        "execution_status": attack.get("execution_status"),
        "feature_effect_status": attack.get("feature_effect_status"),
    }


def official_changed_cards(
    baseline_record: dict[str, Any] | None,
    active_record: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if baseline_record is None or active_record is None or not isinstance(comparison, dict):
        return []
    changed_paths = {
        item["field_path"]
        for item in comparison.get("direct_changed_fields", [])
        if isinstance(item, dict) and isinstance(item.get("field_path"), str)
    }
    baseline_cards = {
        item["official_card_id"]: item
        for item in baseline_record["card_assessments"]
        if item["applicability"] == "current"
    }
    active_cards = {
        item["official_card_id"]: item
        for item in active_record["card_assessments"]
        if item["applicability"] == "current"
    }
    # The official card assessment intentionally stores counts rather than raw
    # values.  Match changed canonical fields against the card's original
    # canonical-field list by reconstructing it from the card source below.
    _, official_cards = load_official_cards()
    rows: list[dict[str, Any]] = []
    for card in official_cards:
        card_id = card["card_id"]
        if card_id not in baseline_cards or card_id not in active_cards:
            continue
        overlap = sorted(set(card.get("canonical_fields", [])) & changed_paths)
        if overlap:
            rows.append(
                {
                    "official_card_id": card_id,
                    "source_card_id": card["source_card_id"],
                    "changed_current_contract_fields": overlap,
                    "baseline_coverage_status": baseline_cards[card_id]["coverage_status"],
                    "attack_active_coverage_status": active_cards[card_id]["coverage_status"],
                    "alert": None,
                    "boundary": "field-overlap observation only; no official-document alert predicate exists",
                }
            )
    return rows


def evaluate_inputs(
    *,
    run_id: str,
    normal_input: Path,
    attack_manifests: list[Path],
    attack_metadata_by_manifest: dict[Path, dict[str, str]],
    official_cards: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    official_normal: list[dict[str, Any]] = []
    device_normal: list[dict[str, Any]] = []
    for line_number, payload in read_jsonl(normal_input):
        session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
        official_normal.append(
            official_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("official-normal", session_id, f"{normal_input}:{line_number}"),
                record_kind="normal_session",
                stage="normal",
                input_path=normal_input,
                input_line=line_number,
                official_cards=official_cards,
            )
        )
        device_normal.append(
            device_mined_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("device-normal", session_id, f"{normal_input}:{line_number}"),
                record_kind="normal_session",
                stage="normal",
                input_path=normal_input,
                input_line=line_number,
            )
        )

    official_pairs: list[dict[str, Any]] = []
    device_pairs: list[dict[str, Any]] = []
    for pair in load_attack_pairs(attack_manifests):
        input_metadata = attack_metadata_by_manifest[pair["manifest_path"].resolve()]
        baseline_member = pair["baseline"]
        active_member = pair["attack_active"]
        official_baseline: dict[str, Any] | None = None
        official_active: dict[str, Any] | None = None
        device_baseline: dict[str, Any] | None = None
        device_active: dict[str, Any] | None = None
        if baseline_member is not None:
            payload = baseline_member["raw_payload"]
            session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
            official_baseline = official_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("official-baseline", session_id, pair["pair_ref"]),
                record_kind="attack_stage",
                stage="baseline",
                input_path=pair["raw_payload_path"],
                input_line=baseline_member["raw_line"],
                official_cards=official_cards,
                pair_ref=pair["pair_ref"],
            )
            device_baseline = device_mined_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("device-baseline", session_id, pair["pair_ref"]),
                record_kind="attack_stage",
                stage="baseline",
                input_path=pair["raw_payload_path"],
                input_line=baseline_member["raw_line"],
                pair_ref=pair["pair_ref"],
            )
        if active_member is not None:
            payload = active_member["raw_payload"]
            session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
            official_active = official_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("official-active", session_id, pair["pair_ref"]),
                record_kind="attack_stage",
                stage="attack_active",
                input_path=pair["raw_payload_path"],
                input_line=active_member["raw_line"],
                official_cards=official_cards,
                pair_ref=pair["pair_ref"],
            )
            device_active = device_mined_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("device-active", session_id, pair["pair_ref"]),
                record_kind="attack_stage",
                stage="attack_active",
                input_path=pair["raw_payload_path"],
                input_line=active_member["raw_line"],
                pair_ref=pair["pair_ref"],
            )
        annotations = annotation_summaries(active_member)
        feature_comparison = (
            direct_feature_comparison(
                baseline_member["raw_payload"], active_member["raw_payload"], annotations
            )
            if baseline_member is not None and active_member is not None
            else None
        )
        common = {
            "source_isolated_validation_version": SOURCE_ISOLATED_VALIDATION_VERSION,
            "run_id": run_id,
            "protocol_version": TWO_STATE_PROTOCOL_VERSION,
            "pair_ref": pair["pair_ref"],
            "pair_id": pair["pair_id"],
            "attack_manifest_ref": repo_relative(pair["manifest_path"]),
            "input_cohort_id": input_metadata["cohort_id"],
            "input_cohort_label": input_metadata["cohort_label"],
            "relation_design_exposure": input_metadata["relation_design_exposure"],
            "acceptance_reference": input_metadata["acceptance_reference"],
            "eligible_for_two_state_validation": pair["eligible_for_two_state_validation"],
            "eligibility_issues": pair["eligibility_issues"],
            "ignored_historical_post_count": pair["ignored_historical_post_count"],
            "tool": tool_reference(active_member),
        }
        official_pairs.append(
            {
                **common,
                "knowledge_source_type": OFFICIAL_DOCUMENT,
                "official_document_decision_transition": "not_independently_evaluable_no_predicate",
                "baseline": official_baseline["official_document_decision"] if official_baseline else None,
                "attack_active": official_active["official_document_decision"] if official_active else None,
                "official_cards_with_direct_changed_fields": official_changed_cards(
                    official_baseline, official_active, feature_comparison
                ),
                "claim_boundary": "Official card field coverage/overlap only; no project threshold or device-mined rule was used.",
            }
        )
        if device_baseline is not None and device_active is not None:
            baseline_alert = device_baseline["decision"]["alert"]
            active_alert = device_active["decision"]["alert"]
            if not baseline_alert and active_alert:
                transition = "baseline_no_alert_to_attack_active_alert"
            elif baseline_alert and active_alert:
                transition = "alert_in_both_stages"
            elif baseline_alert:
                transition = "baseline_alert_attack_active_not_alert"
            else:
                transition = "no_explicit_alert_in_either_stage"
        else:
            transition = "pair_incomplete_not_classified"
        device_pairs.append(
            {
                **common,
                "knowledge_source_type": DEVICE_MINED_RULE,
                "baseline": compact_device_decision(device_baseline),
                "attack_active": compact_device_decision(device_active),
                "device_mined_rule_alarm_transition": transition,
                "feature_comparison": feature_comparison,
                "claim_boundary": "Only deterministic device-mined predicates were used; no official-card retrieval or attack-tool metadata entered the decision.",
            }
        )
    return official_normal, official_pairs, device_normal, device_pairs


def official_card_summary(
    records: list[dict[str, Any]], official_cards: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cohort_names = ("normal", "baseline", "attack_active")
    bucket: dict[str, dict[str, Counter[str]]] = {
        card["card_id"]: {cohort: Counter() for cohort in cohort_names} for card in official_cards
    }
    for record in records:
        cohort = record["stage"]
        for assessment in record["card_assessments"]:
            bucket[assessment["official_card_id"]][cohort][assessment["coverage_status"]] += 1
    rows: list[dict[str, Any]] = []
    for card in official_cards:
        card_id = card["card_id"]
        rows.append(
            {
                "official_card_id": card_id,
                "source_card_id": card["source_card_id"],
                "title": card["title"],
                "applicability": card["applicability"],
                "canonical_fields": card["canonical_fields"],
                "normal_coverage_counts": dict(sorted(bucket[card_id]["normal"].items())),
                "attack_baseline_coverage_counts": dict(
                    sorted(bucket[card_id]["baseline"].items())
                ),
                "attack_active_coverage_counts": dict(
                    sorted(bucket[card_id]["attack_active"].items())
                ),
                "independent_alert_predicate": False,
                "validation_role": "field_semantics_tolerance_and_applicability_only",
            }
        )
    return rows


def rule_outcomes(record: dict[str, Any]) -> dict[str, str]:
    return {
        result["rule_id"]: result["outcome"] for result in record["rule_execution"]["rule_results"]
    }


def device_rule_summary(
    normal_records: list[dict[str, Any]], device_pairs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    kb = load_rule_knowledge_base()
    registry = load_predicate_registry()
    compiled = set(registry.get("compiled_rules", {}))
    baseline_by_pair = {
        pair["pair_ref"]: pair["baseline"] for pair in device_pairs if pair.get("baseline")
    }
    active_by_pair = {
        pair["pair_ref"]: pair["attack_active"] for pair in device_pairs if pair.get("attack_active")
    }
    rows: list[dict[str, Any]] = []
    for rule in kb.get("rules", []):
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule["id"])
        if rule_id not in compiled:
            rows.append(
                {
                    "rule_id": rule_id,
                    "rule_name": rule.get("name"),
                    "execution_status": "retrieval_only_not_compiled",
                    "normal_outcome_counts": {"not_compiled": len(normal_records)},
                    "attack_baseline_outcome_counts": {"not_compiled": len(baseline_by_pair)},
                    "attack_active_outcome_counts": {"not_compiled": len(active_by_pair)},
                    "baseline_to_active_match_count": "not_applicable",
                }
            )
            continue
        normal_counts = Counter(rule_outcomes(record).get(rule_id, "not_evaluated") for record in normal_records)
        baseline_counts = Counter(
            pair["baseline"]["rule_outcomes"].get(rule_id, "not_evaluated")
            for pair in device_pairs
            if pair.get("baseline")
        )
        active_counts = Counter(
            pair["attack_active"]["rule_outcomes"].get(rule_id, "not_evaluated")
            for pair in device_pairs
            if pair.get("attack_active")
        )
        active_match_count = sum(
            rule_id in pair["attack_active"]["matched_rule_ids"]
            for pair in device_pairs
            if pair.get("attack_active")
        )
        baseline_match_count = sum(
            rule_id in pair["baseline"]["matched_rule_ids"]
            for pair in device_pairs
            if pair.get("baseline")
        )
        transition_count = sum(
            rule_id not in pair["baseline"]["matched_rule_ids"]
            and rule_id in pair["attack_active"]["matched_rule_ids"]
            for pair in device_pairs
            if pair.get("baseline") and pair.get("attack_active")
        )
        rows.append(
            {
                "rule_id": rule_id,
                "rule_name": rule.get("name"),
                "execution_status": "compiled",
                "normal_outcome_counts": dict(sorted(normal_counts.items())),
                "attack_baseline_outcome_counts": dict(sorted(baseline_counts.items())),
                "attack_active_outcome_counts": dict(sorted(active_counts.items())),
                "attack_baseline_match_count": baseline_match_count,
                "attack_active_match_count": active_match_count,
                "baseline_to_active_match_count": transition_count,
            }
        )
    return rows


def device_decision_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(record["decision"]["decision_status"] for record in records).items()))


def write_report(
    path: Path,
    *,
    run_id: str,
    official_cards: list[dict[str, Any]],
    official_normal: list[dict[str, Any]],
    official_pairs: list[dict[str, Any]],
    device_normal: list[dict[str, Any]],
    device_pairs: list[dict[str, Any]],
    attack_input_selection: dict[str, Any],
) -> None:
    current_official_cards = [card for card in official_cards if card["applicability"] == "current"]
    future_official_cards = [card for card in official_cards if card["applicability"] == "future_only"]
    compiled_predicate_count = len(load_predicate_registry().get("compiled_rules", {}))
    official_normal_statuses = Counter(
        assessment["coverage_status"]
        for record in official_normal
        for assessment in record["card_assessments"]
        if assessment["applicability"] == "current"
    )
    official_changed_pair_count = sum(
        bool(pair["official_cards_with_direct_changed_fields"]) for pair in official_pairs
    )
    eligible_device_pairs = [pair for pair in device_pairs if pair["eligible_for_two_state_validation"]]
    device_transitions = [
        pair
        for pair in eligible_device_pairs
        if pair["device_mined_rule_alarm_transition"] == "baseline_no_alert_to_attack_active_alert"
    ]
    baseline_alerts = sum(bool(pair["baseline"]["alert"]) for pair in eligible_device_pairs if pair["baseline"])
    active_alerts = sum(
        bool(pair["attack_active"]["alert"]) for pair in eligible_device_pairs if pair["attack_active"]
    )
    no_alert_pairs = [
        pair
        for pair in eligible_device_pairs
        if pair["attack_active"] and not pair["attack_active"]["alert"]
    ]
    transition_rule_ids = sorted(
        {
            rule_id
            for pair in device_transitions
            for rule_id in pair["attack_active"]["matched_rule_ids"]
            if rule_id not in pair["baseline"]["matched_rule_ids"]
        }
    )
    per_tool: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    per_cohort: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for pair in eligible_device_pairs:
        tool = pair["tool"]
        key = (
            str(tool.get("tool_name") or "unknown"),
            str(tool.get("tool_version") or "unknown"),
            str(tool.get("config_id") or "unknown"),
        )
        per_tool[key].append(pair)
        per_cohort[
            (
                str(pair.get("input_cohort_id") or "unknown"),
                str(pair.get("input_cohort_label") or "unknown"),
            )
        ].append(pair)
    lines = [
        f"# 两类知识独立验证报告：{run_id}",
        "",
        "## 结论",
        "",
        "本报告是对既有两类知识分类包之外的一次**源隔离复核**：同一批正常样本和同一批 baseline/attack_active 攻击对，分别交给官方文档知识轨和数据挖掘规则轨处理；两轨不互相借用触发条件。",
        "",
        "- 官方文档轨当前有 0 条独立可执行报警 predicate。因此它的结果是字段语义/容错/适用性核验，不能写成“官方规则未报警”或“官方规则报警率为 0”。",
        (
            f"- 数据挖掘规则轨当前有 {compiled_predicate_count} 条已审阅并编译的 predicate。"
            f"它在 {len(device_normal)} 条正常输入上产生 "
            f"{sum(record['decision']['alert'] for record in device_normal)} 条显式报警；"
            "其中 `insufficient_evidence` 不能当作正常通过或误报率结论。"
        ),
        f"- 数据挖掘规则轨在 {len(eligible_device_pairs)} 个合格攻击对中出现 {len(device_transitions)} 个 `baseline 无报警 -> attack_active 报警` 转换；均应仅解释为当前受控样本上的确定性规则结果。",
        "",
        "## 源隔离方法",
        "",
        "| 知识轨 | 只允许使用 | 禁止使用 | 输出类型 |",
        "|---|---|---|---|",
        "| 官方文档知识 | 官方卡片的字段语义、容错、适用范围和 future official-attestation 路径 | 项目阈值、攻击模板、数据挖掘 predicate | 卡片字段覆盖与攻击前后字段重叠观察；报警为 N/A |",
        "| 数据挖掘规则 | 冻结规则库中已编译的确定性 predicate | 官方卡片检索、攻击工具名/标签、校准模型 | 逐样本规则执行与两态报警转换 |",
        "",
        "## 官方文档知识轨",
        "",
        f"- 卡片共 {len(official_cards)} 张：当前 177-feature 合同可适用 {len(current_official_cards)} 张，future-only {len(future_official_cards)} 张。",
        f"- 正常集的当前卡片-样本覆盖状态：`{json.dumps(dict(sorted(official_normal_statuses.items())), ensure_ascii=False)}`。",
        f"- 攻击对共 {len(official_pairs)} 个；其中 {official_changed_pair_count} 个对在直接比较中出现至少一个属于当前官方卡片字段范围的变化。该观察只说明官方语义覆盖到变化字段，不构成官方攻击告警。",
        "- 逐样本和逐攻击对的结果分别见 `official_document_normal_results.jsonl`、`official_document_attack_pair_results.jsonl`；卡片汇总见 `official_document_card_summary.csv`。",
        "",
        "## 数据挖掘规则轨",
        "",
        "| 正常输入 | 显式报警 | 决策状态计数 |",
        "|---:|---:|---|",
        f"| {len(device_normal)} | {sum(record['decision']['alert'] for record in device_normal)} | `{json.dumps(device_decision_counts(device_normal), ensure_ascii=False, sort_keys=True)}` |",
        "",
        "| 攻击对总数 | 合格两态对 | baseline 显式报警 | attack_active 显式报警 | 无报警转报警 |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(device_pairs)} | {len(eligible_device_pairs)} | {baseline_alerts} | {active_alerts} | {len(device_transitions)} |",
        "",
        "### 输入 cohort 结果",
        "",
        "| cohort | 合格对 | baseline 报警 | attack_active 报警 | 无报警转报警 |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, cohort_pairs in per_cohort.items():
        cohort_baseline_alerts = sum(
            bool(pair["baseline"]["alert"])
            for pair in cohort_pairs
            if pair["baseline"]
        )
        cohort_active_alerts = sum(
            bool(pair["attack_active"]["alert"])
            for pair in cohort_pairs
            if pair["attack_active"]
        )
        cohort_transitions = sum(
            pair["device_mined_rule_alarm_transition"]
            == "baseline_no_alert_to_attack_active_alert"
            for pair in cohort_pairs
        )
        lines.append(
            f"| {key[1]} (`{key[0]}`) | {len(cohort_pairs)} | "
            f"{cohort_baseline_alerts} | {cohort_active_alerts} | {cohort_transitions} |"
        )

    excluded_inputs = attack_input_selection.get("excluded_manifests", [])
    if excluded_inputs:
        lines.extend(
            [
                "",
                "### 明确排除的新 manifest",
                "",
            ]
        )
        for item in excluded_inputs:
            lines.append(f"- `{item['path']}`：`{item['reason']}`")

    lines.extend(
        [
            "",
            "### 工具/精确配置结果",
            "",
        "| 工具 | 工具/runner 版本 | 配置 | 合格对 | 无报警转报警 |",
        "|---|---|---|---:|---:|",
        ]
    )
    for key, pairs in sorted(per_tool.items()):
        transition_count = sum(
            pair["device_mined_rule_alarm_transition"] == "baseline_no_alert_to_attack_active_alert"
            for pair in pairs
        )
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {len(pairs)} | {transition_count} |")

    if no_alert_pairs:
        no_alert_by_config: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(
            list
        )
        for pair in no_alert_pairs:
            no_alert_by_config[
                (
                    str(pair["tool"].get("tool_name") or "unknown"),
                    str(pair["tool"].get("config_id") or "unknown"),
                )
            ].append(pair)
        lines.extend(
            [
                "",
                "### 已确认字段变化但未报警的配置",
                "",
                f"共 {len(no_alert_pairs)} 个合格对未触发当前 {compiled_predicate_count} 条冻结 predicate；下表字段均是 manifest 标注且被 payload 直接对比确认的变化。",
                "",
                "| 工具 | 配置 | 未报警合格对 | 已确认变化字段 |",
                "|---|---|---:|---|",
            ]
        )
        for key, config_pairs in sorted(no_alert_by_config.items()):
            confirmed_fields = sorted(
                {
                    item["field_path"]
                    for pair in config_pairs
                    for item in pair["feature_comparison"]["annotated_field_results"]
                    if item["annotation_status"]
                    == "confirmed_by_direct_payload_comparison"
                }
            )
            lines.append(
                f"| {key[0]} | {key[1]} | {len(config_pairs)} | "
                f"{', '.join(f'`{field}`' for field in confirmed_fields) or '-'} |"
            )
    lines.extend(
        [
            "",
            (
                f"本次新增报警转换涉及 predicate："
                f"`{', '.join(transition_rule_ids) or '-'}`。未触发的工具配置不应被写成已通过或安全，"
                f"只能说当前 {compiled_predicate_count} 条冻结 predicate 未观察到显式报警。"
            ),
            "",
            "## 边界",
            "",
            "本次没有重挖规则、调整阈值、训练模型或恢复 attack 后状态。它不产出误报率、攻击召回率、校准概率、欺诈结论或跨工具泛化结论。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_source_isolated_validation(
    *,
    run_id: str,
    normal_input: Path,
    attack_manifests: list[Path] | None = None,
    attack_input_set: Path | None = None,
    output_dir: Path,
) -> dict[str, Any]:
    normal_input = normal_input.resolve()
    output_dir = output_dir.resolve()
    if not normal_input.is_file():
        raise FileNotFoundError(f"Normal input does not exist: {normal_input}")
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists and will not be overwritten: {output_dir}")
    if not run_id.strip():
        raise ValueError("run_id must be non-empty")

    attack_selection: AttackInputSelection = resolve_attack_inputs(
        explicit_manifests=attack_manifests,
        input_set_path=attack_input_set,
    )

    official_source, official_cards = load_official_cards()
    official_normal, official_pairs, device_normal, device_pairs = evaluate_inputs(
        run_id=run_id,
        normal_input=normal_input,
        attack_manifests=attack_selection.manifests,
        attack_metadata_by_manifest=attack_selection.metadata_by_manifest,
        official_cards=official_cards,
    )
    attach_and_validate_observed_counts(attack_selection, device_pairs)
    official_attack_stage_records = []
    # The pair artifact contains the source-isolated official decision.  Keep
    # individual stage records alongside the normal records for card summary.
    for pair in load_attack_pairs(attack_selection.manifests):
        for role, stage in (("baseline", "baseline"), ("attack_active", "attack_active")):
            member = pair[role]
            if member is None:
                continue
            payload = member["raw_payload"]
            session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
            official_attack_stage_records.append(
                official_record(
                    run_id=run_id,
                    payload=payload,
                    sample_id=stable_sample_id(f"official-{stage}", session_id, pair["pair_ref"]),
                    record_kind="attack_stage",
                    stage=stage,
                    input_path=pair["raw_payload_path"],
                    input_line=member["raw_line"],
                    official_cards=official_cards,
                    pair_ref=pair["pair_ref"],
                )
            )
    official_summary_rows = official_card_summary(
        official_normal + official_attack_stage_records, official_cards
    )
    device_summary_rows = device_rule_summary(device_normal, device_pairs)

    output_dir.mkdir(parents=True, exist_ok=False)

    write_jsonl(output_dir / OFFICIAL_NORMAL_FILENAME, official_normal)
    write_jsonl(output_dir / OFFICIAL_ATTACK_FILENAME, official_pairs)
    write_jsonl(output_dir / DEVICE_NORMAL_FILENAME, device_normal)
    write_jsonl(output_dir / DEVICE_ATTACK_FILENAME, device_pairs)
    write_csv(
        output_dir / OFFICIAL_SUMMARY_FILENAME,
        [
            "official_card_id",
            "source_card_id",
            "title",
            "applicability",
            "canonical_fields",
            "normal_coverage_counts",
            "attack_baseline_coverage_counts",
            "attack_active_coverage_counts",
            "independent_alert_predicate",
            "validation_role",
        ],
        official_summary_rows,
    )
    write_csv(
        output_dir / DEVICE_RULE_SUMMARY_FILENAME,
        [
            "rule_id",
            "rule_name",
            "execution_status",
            "normal_outcome_counts",
            "attack_baseline_outcome_counts",
            "attack_active_outcome_counts",
            "attack_baseline_match_count",
            "attack_active_match_count",
            "baseline_to_active_match_count",
        ],
        device_summary_rows,
    )
    write_report(
        output_dir / REPORT_FILENAME,
        run_id=run_id,
        official_cards=official_cards,
        official_normal=official_normal,
        official_pairs=official_pairs,
        device_normal=device_normal,
        device_pairs=device_pairs,
        attack_input_selection=attack_selection.provenance,
    )
    registry = load_predicate_registry()
    manifest = {
        "source_isolated_validation_version": SOURCE_ISOLATED_VALIDATION_VERSION,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "protocol": {
            "version": TWO_STATE_PROTOCOL_VERSION,
            "states_compared": ["baseline", "attack_active"],
            "historical_clean_post": "ignored_not_used_for_current_validation",
        },
        "inputs": {
            "normal_path": repo_relative(normal_input),
            "normal_record_count": len(official_normal),
            "attack_manifest_paths": [
                repo_relative(path) for path in attack_selection.manifests
            ],
            "attack_pair_count": len(official_pairs),
            "ignored_historical_post_count": sum(
                item["ignored_historical_post_count"] for item in official_pairs
            ),
            "attack_input_selection": attack_selection.provenance,
        },
        "official_document_lane": {
            "cards_path": repo_relative(DEFAULT_OFFICIAL_CARDS),
            "cards_sha256": official_sha256_file(DEFAULT_OFFICIAL_CARDS),
            "cards_version": official_source.get("version"),
            "card_count": len(official_cards),
            "independent_executable_predicate_count": 0,
            "output_mode": "field_coverage_and_changed_field_overlap_only",
            "forbidden_inputs": ["device_mined_rule_thresholds", "attack_tool_labels", "calibrated_score"],
        },
        "device_mined_rule_lane": {
            "rule_kb_path": repo_relative(DEFAULT_RULE_KB),
            "rule_kb_sha256": rule_sha256_file(DEFAULT_RULE_KB),
            "rule_kb_version": load_rule_knowledge_base().get("version"),
            "compiled_predicate_count": len(registry.get("compiled_rules", {})),
            "output_mode": "deterministic_predicate_execution_only",
            "forbidden_inputs": ["official_card_retrieval", "attack_tool_labels", "calibrated_score"],
        },
        "outputs": {
            "official_normal": OFFICIAL_NORMAL_FILENAME,
            "official_attack": OFFICIAL_ATTACK_FILENAME,
            "official_summary": OFFICIAL_SUMMARY_FILENAME,
            "device_normal": DEVICE_NORMAL_FILENAME,
            "device_attack": DEVICE_ATTACK_FILENAME,
            "device_rule_summary": DEVICE_RULE_SUMMARY_FILENAME,
            "report": REPORT_FILENAME,
        },
    }
    write_json(output_dir / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = run_source_isolated_validation(
        run_id=args.run_id,
        normal_input=args.normal_input,
        attack_manifests=args.attack_manifest,
        attack_input_set=args.attack_input_set,
        output_dir=args.output_dir,
    )
    print(
        "Source-isolated validation written: "
        f"{args.output_dir} (normal={manifest['inputs']['normal_record_count']}, "
        f"attack_pairs={manifest['inputs']['attack_pair_count']})"
    )


if __name__ == "__main__":
    main()
