#!/usr/bin/env python3
"""Create one auditable two-source rule-classification run package.

The runner deliberately keeps three things separate:

* normal FeatureApp sessions and attack-session pairs;
* official-document cards (semantic/tolerance support) and executable legacy
  project-data rules;
* a two-state ``baseline -> attack_active`` comparison and historical
  ``clean_post`` records, which are ignored for the current comparison.

It never writes to raw inputs, changes thresholds, trains a model, or turns a
tool name into a rule result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    canonicalize_knowledge_path,
    load_field_paths,
)
from hybridguard_agent.adapters.rule_kb_adapter import (  # noqa: E402
    DEFAULT_RULE_KB,
    load_rule_knowledge_base,
    sha256_file,
)
from hybridguard_agent.evidence.extractor import canonical_json, normalize_payload  # noqa: E402
from hybridguard_agent.rules.executor import load_predicate_registry  # noqa: E402
from hybridguard_agent.runtime.service import analyze_payload  # noqa: E402


CLASSIFICATION_RUN_VERSION = "two-source-rule-classification-v1"
TWO_STATE_PROTOCOL_VERSION = "baseline-attack-v1"
OFFICIAL_DOCUMENT = "official_document"
DEVICE_MINED_RULE = "device_mined_rule"
ALERT_DECISION_STATUSES = {"manual_review_required", "inconsistency_observed"}

RUNTIME_RESULTS_FILENAME = "classification_records.jsonl"
RULE_RESULTS_FILENAME = "sample_rule_results.jsonl"
ATTACK_RESULTS_FILENAME = "attack_pair_results.jsonl"
RULE_CATALOG_FILENAME = "rule_source_catalog.csv"
OFFICIAL_SUMMARY_FILENAME = "official_knowledge_summary.csv"
RULE_SUMMARY_FILENAME = "rule_summary.csv"
FEATURE_DELTA_FILENAME = "feature_delta_summary.csv"
MANIFEST_FILENAME = "run_manifest.json"
ADVISOR_SUMMARY_FILENAME = "ADVISOR_SUMMARY.md"
MISSING = object()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Immutable identifier for this classification run.")
    parser.add_argument(
        "--normal-input",
        type=Path,
        required=True,
        help="Raw FeatureApp JSONL used only as the normal-data classification input.",
    )
    parser.add_argument(
        "--attack-manifest",
        type=Path,
        action="append",
        default=[],
        help=(
            "Attack sample-manifest JSONL. Repeat for each attack run. The sibling "
            "raw_payloads.jsonl is used read-only."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New output directory. Existing directories are rejected to prevent overwrite.",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Read object-only JSONL while retaining one-based line references."""

    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            text = raw_line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append((line_number, value))
    return rows


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


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def stable_sample_id(prefix: str, session_id: str | None, fallback: str) -> str:
    source = session_id or fallback
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def value_sha256(value: Any) -> str:
    """Hash a feature value so comparison artifacts do not duplicate raw fingerprints."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalized_value(normalized: dict[str, Any], canonical_path: str) -> Any:
    """Read one frozen 177-field path from the normalized three-layer payload."""

    layer_name, separator, leaf_name = canonical_path.partition(".")
    if not separator:
        return MISSING
    layer = normalized.get(layer_name)
    if not isinstance(layer, dict):
        return MISSING
    return layer.get(leaf_name, MISSING)


def direct_feature_comparison(
    baseline_payload: dict[str, Any],
    active_payload: dict[str, Any],
    annotated_mutations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare baseline and active payloads on the frozen feature contract.

    The comparison is deliberately separate from attack annotations.  An
    annotation is retained as provenance, but a field is only marked as
    changed when its normalized baseline and active values directly differ.
    Raw feature values are represented by canonical-JSON hashes in the output.
    """

    canonical_paths = load_field_paths()
    baseline, baseline_status = normalize_payload(baseline_payload)
    active, active_status = normalize_payload(active_payload)
    annotations_by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmapped_annotations: list[dict[str, Any]] = []
    for mutation in annotated_mutations:
        original_path = mutation.get("field_path")
        if not isinstance(original_path, str) or not original_path:
            unmapped_annotations.append(
                {
                    "manifest_field_path": original_path,
                    "reason": "missing_or_invalid_field_path",
                    "change_summary": mutation.get("change_summary"),
                }
            )
            continue
        canonical_path = canonicalize_knowledge_path(original_path, canonical_paths)
        if canonical_path is None:
            unmapped_annotations.append(
                {
                    "manifest_field_path": original_path,
                    "reason": "not_in_frozen_177_field_contract",
                    "change_summary": mutation.get("change_summary"),
                }
            )
            continue
        annotations_by_path[canonical_path].append(
            {
                "manifest_field_path": original_path,
                "change_summary": mutation.get("change_summary"),
            }
        )

    comparisons: dict[str, dict[str, Any]] = {}
    for canonical_path in sorted(canonical_paths):
        baseline_value = normalized_value(baseline, canonical_path)
        active_value = normalized_value(active, canonical_path)
        baseline_field_status = baseline_status.get(canonical_path)
        active_field_status = active_status.get(canonical_path)
        if baseline_value is MISSING or active_value is MISSING:
            comparison_status = "not_comparable_missing_value"
        elif (
            (baseline_field_status is not None and baseline_field_status != "observed")
            or (active_field_status is not None and active_field_status != "observed")
        ):
            comparison_status = "not_comparable_non_observed_field_status"
        elif canonical_json(baseline_value) == canonical_json(active_value):
            comparison_status = "unchanged"
        else:
            comparison_status = "changed"
        comparisons[canonical_path] = {
            "field_path": canonical_path,
            "comparison_status": comparison_status,
            "baseline_field_status": baseline_field_status or "not_supplied",
            "attack_active_field_status": active_field_status or "not_supplied",
            "baseline_value_sha256": (
                None if baseline_value is MISSING else value_sha256(baseline_value)
            ),
            "attack_active_value_sha256": (
                None if active_value is MISSING else value_sha256(active_value)
            ),
            "manifest_annotations": annotations_by_path.get(canonical_path, []),
        }

    annotated_field_results: list[dict[str, Any]] = []
    for canonical_path, annotations in sorted(annotations_by_path.items()):
        comparison = comparisons[canonical_path]
        for annotation in annotations:
            if comparison["comparison_status"] == "changed":
                annotation_status = "confirmed_by_direct_payload_comparison"
            elif comparison["comparison_status"] == "unchanged":
                annotation_status = "annotation_value_unchanged_in_direct_comparison"
            else:
                annotation_status = "annotation_not_comparable_in_direct_comparison"
            annotated_field_results.append(
                {
                    "manifest_field_path": annotation["manifest_field_path"],
                    "field_path": canonical_path,
                    "annotation_status": annotation_status,
                    "change_summary": annotation["change_summary"],
                    "baseline_value_sha256": comparison["baseline_value_sha256"],
                    "attack_active_value_sha256": comparison["attack_active_value_sha256"],
                }
            )

    direct_changed_fields = [
        comparison
        for comparison in comparisons.values()
        if comparison["comparison_status"] == "changed"
    ]
    for comparison in direct_changed_fields:
        comparison["annotated_by_attack_manifest"] = bool(comparison["manifest_annotations"])
        comparison["manifest_change_summaries"] = [
            annotation.get("change_summary")
            for annotation in comparison["manifest_annotations"]
            if annotation.get("change_summary")
        ]
        del comparison["manifest_annotations"]
    return {
        "comparison_version": "normalized-feature-delta-v1",
        "field_contract_size": len(canonical_paths),
        "direct_changed_field_count": len(direct_changed_fields),
        "direct_changed_fields": direct_changed_fields,
        "annotated_mutation_count": len(annotated_mutations),
        "annotated_field_results": annotated_field_results,
        "unmapped_annotation_fields": unmapped_annotations,
        "unannotated_direct_changed_field_count": sum(
            not field["annotated_by_attack_manifest"] for field in direct_changed_fields
        ),
    }


def runtime_alert(record: dict[str, Any]) -> bool:
    return record["runtime"]["decision"]["decision_status"] in ALERT_DECISION_STATUSES


def compact_decision(record: dict[str, Any]) -> dict[str, Any]:
    decision = record["runtime"]["decision"]
    return {
        "sample_id": record["sample_id"],
        "source_session_id": record.get("source_session_id"),
        "decision_status": decision["decision_status"],
        "conclusion": decision["conclusion"],
        "alert": runtime_alert(record),
        "matched_rule_ids": decision["matched_rule_ids"],
        "context_rule_ids": decision["context_rule_ids"],
        "unknown_or_unavailable_rule_ids": decision["unknown_or_unavailable_rule_ids"],
        "unevaluated_mandatory_rule_ids": decision["unevaluated_mandatory_rule_ids"],
        "evidence_hash": decision["evidence_hash"],
    }


def make_classification_record(
    *,
    run_id: str,
    payload: dict[str, Any],
    sample_id: str,
    record_kind: str,
    stage: str,
    input_path: Path,
    input_line: int,
    pair_id: str | None = None,
    attack_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the existing deterministic runtime without exposing raw payload values."""

    result = analyze_payload(payload, sample_id=sample_id)
    source_session_id = payload.get("session_id")
    if not isinstance(source_session_id, str) or not source_session_id:
        source_session_id = None
    collection_status = payload.get("collection_status")
    manifest = payload.get("collection_manifest")
    return {
        "classification_record_version": CLASSIFICATION_RUN_VERSION,
        "run_id": run_id,
        "record_kind": record_kind,
        "stage": stage,
        "pair_id": pair_id,
        "sample_id": sample_id,
        "source_session_id": source_session_id,
        "input_ref": f"{repo_relative(input_path)}#line={input_line}",
        "schema_version": payload.get("schema_version"),
        "collector_app": payload.get("collector_app"),
        "collection_status_schema_version": (
            collection_status.get("status_schema_version")
            if isinstance(collection_status, dict)
            else None
        ),
        "collection_manifest_schema_version": (
            manifest.get("manifest_schema_version") if isinstance(manifest, dict) else None
        ),
        "attack_reference": attack_reference,
        "runtime": {
            "status": result["status"],
            "input": result["input"],
            "decision": result["decision"],
            "rule_execution": result["rule_execution"],
            "decision_trace": result["decision_trace"],
            "warnings": result["warnings"],
        },
    }


def build_rule_source_catalog() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Freeze the current source boundary without inventing pure-official alarms.

    The checked-in KB explicitly says its official cards support semantics and
    tolerance, while risk predicates/thresholds remain project rules and
    attack-template/experimental knowledge. Therefore every existing scoring
    rule is classified as a legacy ``device_mined_rule`` primary predicate;
    official cards remain a separately reported supporting source.
    """

    kb = load_rule_knowledge_base()
    registry = load_predicate_registry()
    compiled_ids = set(registry.get("compiled_rules", {}))
    rows: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for rule in kb.get("rules", []):
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule["id"])
        official = rule.get("official_knowledge")
        if not isinstance(official, dict):
            official = {}
        supporting_types = [OFFICIAL_DOCUMENT] if official.get("card_refs") or official.get("source_refs") else []
        row = {
            "rule_id": rule_id,
            "rule_name": str(rule.get("name", "")),
            "category": str(rule.get("category", "")),
            "primary_source_type": DEVICE_MINED_RULE,
            "supporting_source_types": supporting_types,
            "official_card_refs": list(official.get("card_refs", [])),
            "official_source_refs": list(official.get("source_refs", [])),
            "official_inference_level": official.get("inference_level"),
            "threshold_origin": "legacy_project_rule_or_attack_template_or_experimental_data",
            "execution_status": "compiled" if rule_id in compiled_ids else "retrieval_only_not_compiled",
            "source_classification_note": (
                "Official sources support field semantics/tolerance; this rule's trigger is still a "
                "project predicate and is not an independently executable official-document alarm."
            ),
        }
        rows.append(row)
        index[rule_id] = row
    return kb, rows, index


def load_official_cards() -> dict[str, dict[str, Any]]:
    source = json.loads(DEFAULT_OFFICIAL_CARDS.read_text(encoding="utf-8"))
    cards = source.get("cards")
    if not isinstance(cards, list):
        raise ValueError(f"Official cards file has no cards list: {DEFAULT_OFFICIAL_CARDS}")
    return {str(card["id"]): card for card in cards if isinstance(card, dict) and card.get("id")}


def classify_normal_records(run_id: str, normal_input: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, payload in read_jsonl(normal_input):
        session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
        records.append(
            make_classification_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("normal", session_id, f"{normal_input}:{line_number}"),
                record_kind="normal_session",
                stage="normal",
                input_path=normal_input,
                input_line=line_number,
            )
        )
    return records


def _attack_role(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"clean_pre", "baseline", "clean"}:
        return "baseline"
    if text in {"attack", "attack_active", "active"}:
        return "attack_active"
    if text in {"clean_post", "post", "attack_revoked", "revoked"}:
        return "historical_post"
    return None


def load_attack_pairs(manifest_paths: list[Path]) -> list[dict[str, Any]]:
    """Load sibling raw payloads and form only baseline/active comparison pairs."""

    pairs: list[dict[str, Any]] = []
    seen_pair_ids: set[str] = set()
    for manifest_path in manifest_paths:
        raw_payload_path = manifest_path.parent / "raw_payloads.jsonl"
        if not raw_payload_path.is_file():
            raise FileNotFoundError(f"Missing sibling raw attack payloads: {raw_payload_path}")
        raw_rows = read_jsonl(raw_payload_path)
        raw_by_session: dict[str, tuple[int, dict[str, Any]]] = {}
        for line_number, payload in raw_rows:
            session_id = payload.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise ValueError(f"{raw_payload_path}:{line_number} lacks session_id")
            if session_id in raw_by_session:
                raise ValueError(f"Duplicate attack raw session_id in {raw_payload_path}: {session_id}")
            raw_by_session[session_id] = (line_number, payload)

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for manifest_line, manifest in read_jsonl(manifest_path):
            pair = manifest.get("pair")
            if not isinstance(pair, dict):
                raise ValueError(f"{manifest_path}:{manifest_line} has no pair object")
            pair_id = pair.get("pair_id")
            session_id = manifest.get("session_id")
            if not isinstance(pair_id, str) or not pair_id:
                raise ValueError(f"{manifest_path}:{manifest_line} has no pair_id")
            if not isinstance(session_id, str) or not session_id:
                raise ValueError(f"{manifest_path}:{manifest_line} has no session_id")
            if session_id not in raw_by_session:
                raise ValueError(
                    f"{manifest_path}:{manifest_line} references missing raw session {session_id}"
                )
            grouped[pair_id].append(
                {
                    "manifest_line": manifest_line,
                    "manifest": manifest,
                    "raw_line": raw_by_session[session_id][0],
                    "raw_payload": raw_by_session[session_id][1],
                    "role": _attack_role(pair.get("pair_role")),
                }
            )

        for pair_id, members in sorted(grouped.items()):
            canonical_pair_id = f"{repo_relative(manifest_path)}::{pair_id}"
            if canonical_pair_id in seen_pair_ids:
                raise ValueError(f"Duplicate attack pair reference: {canonical_pair_id}")
            seen_pair_ids.add(canonical_pair_id)
            baseline = [member for member in members if member["role"] == "baseline"]
            active = [member for member in members if member["role"] == "attack_active"]
            ignored_post = [member for member in members if member["role"] == "historical_post"]
            issues: list[str] = []
            if len(baseline) != 1:
                issues.append(f"expected_one_baseline_found_{len(baseline)}")
            if len(active) != 1:
                issues.append(f"expected_one_attack_active_found_{len(active)}")
            active_manifest = active[0]["manifest"] if len(active) == 1 else {}
            attack = active_manifest.get("attack") if isinstance(active_manifest, dict) else {}
            if not isinstance(attack, dict):
                attack = {}
            if active and attack.get("execution_status") != "verified_success":
                issues.append("attack_execution_not_verified_success")
            if active and attack.get("feature_effect_status") != "observed":
                issues.append("attack_feature_effect_not_observed")
            pairs.append(
                {
                    "pair_ref": canonical_pair_id,
                    "pair_id": pair_id,
                    "manifest_path": manifest_path,
                    "raw_payload_path": raw_payload_path,
                    "baseline": baseline[0] if len(baseline) == 1 else None,
                    "attack_active": active[0] if len(active) == 1 else None,
                    "ignored_historical_post_count": len(ignored_post),
                    "eligibility_issues": issues,
                    "eligible_for_two_state_validation": not issues,
                }
            )
    return pairs


def attack_reference(member: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    manifest = member["manifest"]
    attack = manifest.get("attack") if isinstance(manifest.get("attack"), dict) else {}
    annotation = (
        manifest.get("annotation_effects")
        if isinstance(manifest.get("annotation_effects"), dict)
        else {}
    )
    return {
        "attack_manifest_ref": f"{repo_relative(manifest_path)}#line={member['manifest_line']}",
        "tool_name": attack.get("tool_name"),
        "tool_version": attack.get("tool_version"),
        "attack_family": attack.get("attack_family"),
        "attack_type": attack.get("attack_type"),
        "config_id": attack.get("config_id"),
        "execution_status": attack.get("execution_status"),
        "feature_effect_status": attack.get("feature_effect_status"),
        "observable_effect_status": annotation.get("observable_effect_status"),
        "field_effect_status": annotation.get("field_effect_status"),
        "attributable_effect_status": annotation.get("attributable_effect_status"),
    }


def classify_attack_pairs(run_id: str, pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return per-stage records and pair-level results, never classifying clean_post."""

    records: list[dict[str, Any]] = []
    pair_results: list[dict[str, Any]] = []
    for pair in pairs:
        baseline_member = pair["baseline"]
        active_member = pair["attack_active"]
        baseline_record: dict[str, Any] | None = None
        active_record: dict[str, Any] | None = None
        if baseline_member is not None:
            payload = baseline_member["raw_payload"]
            session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
            baseline_record = make_classification_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("attack-baseline", session_id, pair["pair_ref"]),
                record_kind="attack_stage",
                stage="baseline",
                input_path=pair["raw_payload_path"],
                input_line=baseline_member["raw_line"],
                pair_id=pair["pair_ref"],
                attack_reference=attack_reference(baseline_member, pair["manifest_path"]),
            )
            records.append(baseline_record)
        if active_member is not None:
            payload = active_member["raw_payload"]
            session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
            active_record = make_classification_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id("attack-active", session_id, pair["pair_ref"]),
                record_kind="attack_stage",
                stage="attack_active",
                input_path=pair["raw_payload_path"],
                input_line=active_member["raw_line"],
                pair_id=pair["pair_ref"],
                attack_reference=attack_reference(active_member, pair["manifest_path"]),
            )
            records.append(active_record)

        active_manifest = active_member["manifest"] if active_member is not None else {}
        attack = active_manifest.get("attack") if isinstance(active_manifest, dict) else {}
        if not isinstance(attack, dict):
            attack = {}
        mutations = attack.get("observed_mutations")
        if not isinstance(mutations, list):
            mutations = []
        mutation_summaries = [
            {
                "field_path": mutation.get("field_path"),
                "change_summary": mutation.get("change_summary"),
            }
            for mutation in mutations
            if isinstance(mutation, dict)
        ]
        if baseline_member is not None and active_member is not None:
            feature_comparison = direct_feature_comparison(
                baseline_member["raw_payload"],
                active_member["raw_payload"],
                mutation_summaries,
            )
        else:
            feature_comparison = None
        if baseline_record is not None and active_record is not None:
            baseline_alert = runtime_alert(baseline_record)
            active_alert = runtime_alert(active_record)
            if not baseline_alert and active_alert:
                transition = "baseline_no_alert_to_attack_active_alert"
            elif baseline_alert and active_alert:
                transition = "alert_in_both_stages"
            elif baseline_alert:
                transition = "baseline_alert_attack_active_not_alert"
            else:
                transition = "no_explicit_alert_in_either_stage"
        else:
            baseline_alert = None
            active_alert = None
            transition = "pair_incomplete_not_classified"
        pair_results.append(
            {
                "attack_pair_result_version": CLASSIFICATION_RUN_VERSION,
                "run_id": run_id,
                "protocol_version": TWO_STATE_PROTOCOL_VERSION,
                "pair_ref": pair["pair_ref"],
                "pair_id": pair["pair_id"],
                "attack_manifest_ref": repo_relative(pair["manifest_path"]),
                "raw_payload_ref": repo_relative(pair["raw_payload_path"]),
                "eligible_for_two_state_validation": pair["eligible_for_two_state_validation"],
                "eligibility_issues": pair["eligibility_issues"],
                "ignored_historical_post_count": pair["ignored_historical_post_count"],
                "tool": {
                    "tool_name": attack.get("tool_name"),
                    "tool_version": attack.get("tool_version"),
                    "attack_family": attack.get("attack_family"),
                    "attack_type": attack.get("attack_type"),
                    "config_id": attack.get("config_id"),
                    "config_sha256": attack.get("config_sha256"),
                    "execution_status": attack.get("execution_status"),
                    "feature_effect_status": attack.get("feature_effect_status"),
                },
                "baseline": compact_decision(baseline_record) if baseline_record else None,
                "attack_active": compact_decision(active_record) if active_record else None,
                "data_mined_rule_alarm_transition": transition,
                "official_document_alarm_status": "not_independently_executable_in_current_rule_kb",
                "annotated_feature_mutation_count": len(mutation_summaries),
                "annotated_feature_mutations": mutation_summaries,
                "feature_comparison": feature_comparison,
                "claim_boundary": (
                    "This is a controlled two-state rule-execution comparison. It does not produce a "
                    "calibrated attack probability, fraud rate, or cross-tool generalization claim."
                ),
            }
        )
    return records, pair_results


def flatten_rule_results(
    records: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        execution = record["runtime"]["rule_execution"]
        for result in execution["rule_results"]:
            rule_id = result["rule_id"]
            source = catalog[rule_id]
            rows.append(
                {
                    "run_id": record["run_id"],
                    "sample_id": record["sample_id"],
                    "source_session_id": record.get("source_session_id"),
                    "record_kind": record["record_kind"],
                    "stage": record["stage"],
                    "pair_id": record.get("pair_id"),
                    "knowledge_source_type": source["primary_source_type"],
                    "rule_id": rule_id,
                    "rule_name": source["rule_name"],
                    "category": source["category"],
                    "outcome": result["outcome"],
                    "short_circuit": result["short_circuit"],
                    "source_fields": result["source_fields"],
                    "detail": result["detail"],
                    "official_card_refs": source["official_card_refs"],
                    "official_source_refs": source["official_source_refs"],
                }
            )
    return rows


def rule_outcomes(record: dict[str, Any]) -> dict[str, str]:
    return {
        str(result["rule_id"]): str(result["outcome"])
        for result in record["runtime"]["rule_execution"]["rule_results"]
    }


def build_rule_summary(
    catalog_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    pair_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normal = [record for record in records if record["record_kind"] == "normal_session"]
    baseline_by_pair = {
        record["pair_id"]: record
        for record in records
        if record["record_kind"] == "attack_stage" and record["stage"] == "baseline"
    }
    active_by_pair = {
        record["pair_id"]: record
        for record in records
        if record["record_kind"] == "attack_stage" and record["stage"] == "attack_active"
    }
    summary: list[dict[str, Any]] = []
    for item in catalog_rows:
        rule_id = item["rule_id"]
        if item["execution_status"] != "compiled":
            summary.append(
                {
                    **item,
                    "normal_outcome_counts": {"not_compiled": len(normal)},
                    "attack_baseline_outcome_counts": {"not_compiled": len(baseline_by_pair)},
                    "attack_active_outcome_counts": {"not_compiled": len(active_by_pair)},
                    "baseline_to_active_match_count": "not_applicable",
                }
            )
            continue
        normal_counts = Counter(rule_outcomes(record).get(rule_id, "not_evaluated") for record in normal)
        baseline_counts = Counter(
            rule_outcomes(record).get(rule_id, "not_evaluated") for record in baseline_by_pair.values()
        )
        active_counts = Counter(
            rule_outcomes(record).get(rule_id, "not_evaluated") for record in active_by_pair.values()
        )
        transitions = 0
        for pair in pair_results:
            if not pair["eligible_for_two_state_validation"]:
                continue
            pair_ref = pair["pair_ref"]
            baseline = baseline_by_pair.get(pair_ref)
            active = active_by_pair.get(pair_ref)
            if baseline is None or active is None:
                continue
            if (
                rule_outcomes(baseline).get(rule_id) != "matched"
                and rule_outcomes(active).get(rule_id) == "matched"
            ):
                transitions += 1
        summary.append(
            {
                **item,
                "normal_outcome_counts": dict(sorted(normal_counts.items())),
                "attack_baseline_outcome_counts": dict(sorted(baseline_counts.items())),
                "attack_active_outcome_counts": dict(sorted(active_counts.items())),
                "baseline_to_active_match_count": transitions,
            }
        )
    return summary


def build_feature_delta_summary(pair_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    configuration_pairs: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for pair in pair_results:
        if not pair["eligible_for_two_state_validation"]:
            continue
        tool = pair["tool"]
        configuration = (
            str(tool.get("tool_name") or "unknown"),
            str(tool.get("tool_version") or "unknown"),
            str(tool.get("config_id") or "unknown"),
        )
        configuration_pairs[configuration].add(pair["pair_ref"])
        comparison = pair.get("feature_comparison")
        if not isinstance(comparison, dict):
            continue

        annotations_by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for annotation in comparison.get("annotated_field_results", []):
            if isinstance(annotation, dict) and isinstance(annotation.get("field_path"), str):
                annotations_by_path[annotation["field_path"]].append(annotation)
        direct_changed_by_path: dict[str, dict[str, Any]] = {}
        for changed in comparison.get("direct_changed_fields", []):
            if isinstance(changed, dict) and isinstance(changed.get("field_path"), str):
                direct_changed_by_path[changed["field_path"]] = changed

        for field_path in sorted(set(annotations_by_path) | set(direct_changed_by_path)):
            key = (*configuration, field_path)
            item = grouped.setdefault(
                key,
                {
                    "tool_name": key[0],
                    "tool_version": key[1],
                    "config_id": key[2],
                    "field_path": key[3],
                    "direct_change_pair_refs": set(),
                    "annotation_listed_pair_refs": set(),
                    "annotation_confirmed_pair_refs": set(),
                    "annotation_mismatch_pair_refs": set(),
                    "unannotated_direct_change_pair_refs": set(),
                    "change_summaries": set(),
                    "alarm_transition_pair_refs": set(),
                },
            )
            changed = direct_changed_by_path.get(field_path)
            annotations = annotations_by_path.get(field_path, [])
            if changed is not None:
                item["direct_change_pair_refs"].add(pair["pair_ref"])
                if not annotations:
                    item["unannotated_direct_change_pair_refs"].add(pair["pair_ref"])
                if pair["data_mined_rule_alarm_transition"] == "baseline_no_alert_to_attack_active_alert":
                    item["alarm_transition_pair_refs"].add(pair["pair_ref"])
                for summary in changed.get("manifest_change_summaries", []):
                    if isinstance(summary, str) and summary:
                        item["change_summaries"].add(summary)
            for annotation in annotations:
                item["annotation_listed_pair_refs"].add(pair["pair_ref"])
                if annotation.get("annotation_status") == "confirmed_by_direct_payload_comparison":
                    item["annotation_confirmed_pair_refs"].add(pair["pair_ref"])
                else:
                    item["annotation_mismatch_pair_refs"].add(pair["pair_ref"])
                summary = annotation.get("change_summary")
                if isinstance(summary, str) and summary:
                    item["change_summaries"].add(summary)

    rows: list[dict[str, Any]] = []
    for key, item in sorted(grouped.items()):
        configuration = key[:3]
        eligible_pair_count = len(configuration_pairs[configuration])
        direct_change_pair_count = len(item["direct_change_pair_refs"])
        annotation_confirmed_pair_count = len(item["annotation_confirmed_pair_refs"])
        stable_direct_change = direct_change_pair_count == eligible_pair_count and eligible_pair_count > 0
        stable_attack_attributable_change = (
            stable_direct_change and annotation_confirmed_pair_count == eligible_pair_count
        )
        rows.append(
            {
                "tool_name": key[0],
                "tool_version": key[1],
                "config_id": key[2],
                "field_path": key[3],
                "eligible_pair_count": eligible_pair_count,
                "direct_change_pair_count": direct_change_pair_count,
                "direct_change_rate": (
                    direct_change_pair_count / eligible_pair_count if eligible_pair_count else None
                ),
                "stable_direct_change_within_available_pairs": stable_direct_change,
                "annotation_listed_pair_count": len(item["annotation_listed_pair_refs"]),
                "annotation_confirmed_pair_count": annotation_confirmed_pair_count,
                "annotation_mismatch_pair_count": len(item["annotation_mismatch_pair_refs"]),
                "unannotated_direct_change_pair_count": len(
                    item["unannotated_direct_change_pair_refs"]
                ),
                "pair_refs_with_direct_change": sorted(item["direct_change_pair_refs"]),
                "change_summaries": sorted(item["change_summaries"]),
                "pairs_with_data_mined_alarm_transition": len(item["alarm_transition_pair_refs"]),
                "stability_interpretation": (
                    "consistent_across_available_pairs_for_this_exact_tool_version_config"
                    if stable_direct_change
                    else "not_consistent_across_available_pairs_for_this_exact_tool_version_config"
                ),
                "stable_attack_attributable_change_within_available_pairs": stable_attack_attributable_change,
                "attack_attribution_interpretation": (
                    "manifest_annotated_and_directly_confirmed_across_all_available_pairs"
                    if stable_attack_attributable_change
                    else "direct_change_not_fully_attributable_to_attack_with_current_manifest_and_pairs"
                ),
            }
        )
    return rows


def build_official_summary(
    official_cards: dict[str, dict[str, Any]], records: list[dict[str, Any]], catalog: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    retrieved_by_card: dict[str, set[str]] = defaultdict(set)
    for record in records:
        cards = record["runtime"]["decision_trace"]["citations"].get("card_ids", [])
        for card_id in cards:
            if isinstance(card_id, str) and card_id.startswith("OFFICIAL-"):
                retrieved_by_card[card_id.removeprefix("OFFICIAL-")].add(record["sample_id"])
    rows = []
    for card_id, card in sorted(official_cards.items()):
        targets = [str(item) for item in card.get("target_rule_ids", [])]
        linked_compiled = [
            item for item in targets if catalog.get(item, {}).get("execution_status") == "compiled"
        ]
        rows.append(
            {
                "knowledge_source_type": OFFICIAL_DOCUMENT,
                "official_card_id": card_id,
                "card_name": card.get("name"),
                "inference_level": card.get("inference_level"),
                "evidence_strength": card.get("evidence_strength"),
                "target_rule_ids": targets,
                "linked_compiled_rule_ids": linked_compiled,
                "source_refs": card.get("source_refs", []),
                "retrieved_sample_count": len(retrieved_by_card.get(card_id, set())),
                "independent_alarm_predicate": False,
                "classification_role": "semantic_and_tolerance_support_only",
            }
        )
    return rows


def decision_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(record["runtime"]["decision"]["decision_status"] for record in records).items()))


def write_advisor_summary(
    path: Path,
    *,
    run_id: str,
    normal_records: list[dict[str, Any]],
    pair_results: list[dict[str, Any]],
    catalog_rows: list[dict[str, Any]],
    official_rows: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
) -> None:
    compiled_count = sum(item["execution_status"] == "compiled" for item in catalog_rows)
    normal_alerts = sum(runtime_alert(record) for record in normal_records)
    normal_completed = sum(
        record["runtime"]["decision"]["decision_status"] == "completed" for record in normal_records
    )
    normal_context = sum(
        record["runtime"]["decision"]["decision_status"] == "context_observed"
        for record in normal_records
    )
    normal_insufficient = sum(
        record["runtime"]["decision"]["decision_status"] == "insufficient_evidence"
        for record in normal_records
    )
    eligible_pairs = [item for item in pair_results if item["eligible_for_two_state_validation"]]
    transitions = [
        item
        for item in eligible_pairs
        if item["data_mined_rule_alarm_transition"] == "baseline_no_alert_to_attack_active_alert"
    ]
    baseline_alerts = sum(bool(item.get("baseline", {}).get("alert")) for item in eligible_pairs)
    active_alerts = sum(bool(item.get("attack_active", {}).get("alert")) for item in eligible_pairs)
    official_retrieved = sum(item["retrieved_sample_count"] > 0 for item in official_rows)
    stable_direct_feature_rows = sum(
        bool(item["stable_direct_change_within_available_pairs"]) for item in feature_rows
    )
    stable_attack_attributable_feature_rows = sum(
        bool(item["stable_attack_attributable_change_within_available_pairs"])
        for item in feature_rows
    )
    annotation_mismatch_count = sum(int(item["annotation_mismatch_pair_count"]) for item in feature_rows)
    unannotated_direct_change_count = sum(
        int(item["unannotated_direct_change_pair_count"]) for item in feature_rows
    )
    lines = [
        f"# 两类知识规则分类与两态攻击验证：{run_id}",
        "",
        "## 运行边界",
        "",
        "- 当前比较只使用 `baseline -> attack_active`；历史 `clean_post` 未参与分类或成功判定。",
        "- 本次没有重挖规则、调整阈值、训练模型或输出校准风险概率。",
        "- `manual_review_required` 与 `inconsistency_observed` 计为显式报警；`insufficient_evidence` 既不是正常通过，也不是报警。",
        "",
        "## 知识来源状态",
        "",
        "| 来源 | 知识项 | 本次可独立执行的报警 predicate | 本次解释方式 |",
        "|---|---:|---:|---|",
        (
            f"| 官方文档知识 | {len(official_rows)} 张官方卡 | 0 | 语义、容错与字段依据；不能被误报为独立官方报警规则。 |"
        ),
        (
            f"| 真机数据/项目经验规则 | {len(catalog_rows)} 条旧规则 | {compiled_count} | 仅已审阅的确定性 predicate 执行；其余规则保持 retrieval-only。 |"
        ),
        "",
        "现有规则库中的官方卡片用于支撑字段语义和容错，而触发条件仍是项目内规则。故本次不能把“有官方引用的规则”伪装成纯官方规则，并把它们与经验规则做独立报警率比较。",
        "",
        "## 正常数据分类结果",
        "",
        "| 输入记录 | 显式报警 | 完成且未命中规则 | 仅上下文观察 | 证据不足 |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(normal_records)} | {normal_alerts} | {normal_completed} | {normal_context} | {normal_insufficient} |",
        "",
        f"完整决策状态计数：`{json.dumps(decision_counts(normal_records), ensure_ascii=False, sort_keys=True)}`。",
        "",
        "## 攻击工具两态验证",
        "",
        "| 攻击对总数 | 可纳入两态验证 | baseline 显式报警 | attack_active 显式报警 | baseline 无报警转 active 报警 |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(pair_results)} | {len(eligible_pairs)} | {baseline_alerts} | {active_alerts} | {len(transitions)} |",
        "",
        "攻击对只在工具执行已核验、字段效果已观察到且 baseline/active 都存在时计入两态验证分母。未满足这些条件的记录保留在 `attack_pair_results.jsonl`，但不计为成功或失败。",
        "",
        "## 已观察到的攻击字段变化",
        "",
        (
            f"- 覆盖 {len(feature_rows)} 个 `工具 × 版本 × 配置 × field_path` 条目；其中 "
            f"{stable_direct_feature_rows} 个字段在各自可用的同配置攻击对中均由 baseline/active 原始 payload 直接比较为变化，"
            f"但仅 {stable_attack_attributable_feature_rows} 个同时满足攻击清单标注与直接比较确认。"
        ),
        (
            f"- 攻击清单标注与直接比较不一致/不可比的字段对共 {annotation_mismatch_count} 个；"
            f"另有 {unannotated_direct_change_count} 个未由攻击清单标注的直接变化字段对，不能据此归因给攻击。"
        ),
        "- 详见 `feature_delta_summary.csv`；该文件保存字段路径、直接变化分子/分母、标注核对结果与变化摘要，不重复复制完整原始 payload。",
        "",
        "## 产物索引",
        "",
        f"- `{MANIFEST_FILENAME}`：输入、规则版本、协议与计数。",
        f"- `{RULE_CATALOG_FILENAME}`：每条旧规则的主来源、官方补充依据与编译状态。",
        f"- `{RUNTIME_RESULTS_FILENAME}`：逐样本/逐攻击阶段的确定性运行结果与 DecisionTrace。",
        f"- `{RULE_RESULTS_FILENAME}`：逐样本 × 已编译规则的命中/未评估结果。",
        f"- `{ATTACK_RESULTS_FILENAME}`：逐攻击对的 baseline/attack_active 比较。",
        f"- `{RULE_SUMMARY_FILENAME}`、`{OFFICIAL_SUMMARY_FILENAME}`、`{FEATURE_DELTA_FILENAME}`：导师可筛选的汇总表。",
        "",
        "## 结论边界",
        "",
        "本包证明的是当前冻结规则在这些输入上的可复核执行与受控两态比较。它不是攻击召回率、误报率、欺诈概率或跨工具泛化性能结论。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_classification(
    *,
    run_id: str,
    normal_input: Path,
    attack_manifests: list[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Run once and create a new, self-describing output directory."""

    normal_input = normal_input.resolve()
    attack_manifests = [path.resolve() for path in attack_manifests]
    output_dir = output_dir.resolve()
    if not normal_input.is_file():
        raise FileNotFoundError(f"Normal input does not exist: {normal_input}")
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists and will not be overwritten: {output_dir}")
    if not run_id.strip():
        raise ValueError("run_id must be non-empty")
    output_dir.mkdir(parents=True, exist_ok=False)

    kb, catalog_rows, catalog_index = build_rule_source_catalog()
    official_cards = load_official_cards()
    normal_records = classify_normal_records(run_id, normal_input)
    pairs = load_attack_pairs(attack_manifests)
    attack_records, pair_results = classify_attack_pairs(run_id, pairs)
    all_records = normal_records + attack_records
    rule_result_rows = flatten_rule_results(all_records, catalog_index)
    rule_summary_rows = build_rule_summary(catalog_rows, all_records, pair_results)
    official_rows = build_official_summary(official_cards, all_records, catalog_index)
    feature_rows = build_feature_delta_summary(pair_results)

    write_jsonl(output_dir / RUNTIME_RESULTS_FILENAME, all_records)
    write_jsonl(output_dir / RULE_RESULTS_FILENAME, rule_result_rows)
    write_jsonl(output_dir / ATTACK_RESULTS_FILENAME, pair_results)
    write_csv(
        output_dir / RULE_CATALOG_FILENAME,
        [
            "rule_id",
            "rule_name",
            "category",
            "primary_source_type",
            "supporting_source_types",
            "official_card_refs",
            "official_source_refs",
            "official_inference_level",
            "threshold_origin",
            "execution_status",
            "source_classification_note",
        ],
        catalog_rows,
    )
    write_csv(
        output_dir / OFFICIAL_SUMMARY_FILENAME,
        [
            "knowledge_source_type",
            "official_card_id",
            "card_name",
            "inference_level",
            "evidence_strength",
            "target_rule_ids",
            "linked_compiled_rule_ids",
            "source_refs",
            "retrieved_sample_count",
            "independent_alarm_predicate",
            "classification_role",
        ],
        official_rows,
    )
    write_csv(
        output_dir / RULE_SUMMARY_FILENAME,
        [
            "rule_id",
            "rule_name",
            "category",
            "primary_source_type",
            "supporting_source_types",
            "execution_status",
            "normal_outcome_counts",
            "attack_baseline_outcome_counts",
            "attack_active_outcome_counts",
            "baseline_to_active_match_count",
            "official_card_refs",
        ],
        rule_summary_rows,
    )
    write_csv(
        output_dir / FEATURE_DELTA_FILENAME,
        [
            "tool_name",
            "tool_version",
            "config_id",
            "field_path",
            "eligible_pair_count",
            "direct_change_pair_count",
            "direct_change_rate",
            "stable_direct_change_within_available_pairs",
            "annotation_listed_pair_count",
            "annotation_confirmed_pair_count",
            "annotation_mismatch_pair_count",
            "unannotated_direct_change_pair_count",
            "pair_refs_with_direct_change",
            "change_summaries",
            "pairs_with_data_mined_alarm_transition",
            "stability_interpretation",
            "stable_attack_attributable_change_within_available_pairs",
            "attack_attribution_interpretation",
        ],
        feature_rows,
    )
    write_advisor_summary(
        output_dir / ADVISOR_SUMMARY_FILENAME,
        run_id=run_id,
        normal_records=normal_records,
        pair_results=pair_results,
        catalog_rows=catalog_rows,
        official_rows=official_rows,
        feature_rows=feature_rows,
    )

    manifest = {
        "classification_run_version": CLASSIFICATION_RUN_VERSION,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "protocol": {
            "version": TWO_STATE_PROTOCOL_VERSION,
            "states_compared": ["baseline", "attack_active"],
            "historical_clean_post": "ignored_not_used_for_current_classification",
        },
        "inputs": {
            "normal": {
                "path": repo_relative(normal_input),
                "record_count": len(normal_records),
                "schema_versions": dict(
                    sorted(Counter(record["schema_version"] for record in normal_records).items())
                ),
            },
            "attack": {
                "manifest_paths": [repo_relative(path) for path in attack_manifests],
                "pair_count": len(pair_results),
                "eligible_two_state_pair_count": sum(
                    bool(item["eligible_for_two_state_validation"]) for item in pair_results
                ),
                "ignored_historical_post_count": sum(
                    int(item["ignored_historical_post_count"]) for item in pair_results
                ),
            },
        },
        "knowledge": {
            "rule_kb_path": repo_relative(DEFAULT_RULE_KB),
            "rule_kb_version": kb.get("version"),
            "rule_kb_sha256": sha256_file(DEFAULT_RULE_KB),
            "rule_count": len(catalog_rows),
            "compiled_rule_count": sum(item["execution_status"] == "compiled" for item in catalog_rows),
            "official_cards_path": repo_relative(DEFAULT_OFFICIAL_CARDS),
            "official_card_count": len(official_cards),
            "official_document_independent_alarm_predicate_count": 0,
            "source_boundary": (
                "Official cards are semantic/tolerance support only in the current KB. Existing "
                "project predicates are reported as device_mined_rule with official support retained."
            ),
        },
        "outputs": {
            "classification_records": RUNTIME_RESULTS_FILENAME,
            "sample_rule_results": RULE_RESULTS_FILENAME,
            "attack_pair_results": ATTACK_RESULTS_FILENAME,
            "rule_source_catalog": RULE_CATALOG_FILENAME,
            "official_knowledge_summary": OFFICIAL_SUMMARY_FILENAME,
            "rule_summary": RULE_SUMMARY_FILENAME,
        "feature_delta_summary": FEATURE_DELTA_FILENAME,
            "advisor_summary": ADVISOR_SUMMARY_FILENAME,
        },
        "claim_boundary": (
            "A deterministic classification and controlled two-state comparison only; no calibrated "
            "risk probability, recall, false-positive rate, fraud label, or cross-tool generalization claim."
        ),
        "feature_comparison_boundary": (
            "Feature deltas directly compare normalized values on the frozen 177-field contract. "
            "Raw values are represented by hashes; unannotated deltas are not attributed to the attack."
        ),
    }
    write_json(output_dir / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = run_classification(
        run_id=args.run_id,
        normal_input=args.normal_input,
        attack_manifests=args.attack_manifest,
        output_dir=args.output_dir,
    )
    print(
        "Two-source classification run written: "
        f"{args.output_dir} (normal={manifest['inputs']['normal']['record_count']}, "
        f"attack_pairs={manifest['inputs']['attack']['pair_count']})"
    )


if __name__ == "__main__":
    main()
