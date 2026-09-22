"""Describe frozen legacy rules on P2 discovery/development, without labels.

The ordered legacy engine is not repaired here. Independent predicate replay and
the availability gate are additional diagnostics, never silently substituted for
its short-circuit execution. Browser values and P2 control metadata are excluded
from the legacy App177 payload.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from hybridguard_agent.adapters.rule_kb_adapter import assert_pinned_rule_kb, load_rule_knowledge_base
from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2
from hybridguard_agent.official_semantics.evaluator import evaluate_official_semantics, load_semantic_catalog
from hybridguard_agent.rules.executor import _evaluate, execute_deterministic_rules, load_predicate_registry

SPLITS = ("discovery", "development")
LAYERS = ("android_native_data", "webview_data", "web_data")
FROZEN_FILES = (
    "hybridguard_agent/config/deterministic_rule_predicates.v1.json",
    "hybridguard_agent/config/official_semantic_relations.v1.json",
    "hybridguard_agent/rules/executor.py",
    "hybridguard_agent/official_semantics/evaluator.py",
    "hybridguard_agent/evidence/extractor.py",
    "hybridguard_agent/adapters/rule_kb_adapter.py",
    "hybridguard_agent/adapters/official_kb_adapter.py",
    "hybridguard_agent/schemas/field_registry.json",
    "hybridguard_agent/config/mtc_paired244_sources.v2.json",
    "scoring/rule_knowledge_base.json",
    "google_official_kb/feature_risk_cards.json",
)


def app_payload(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Build only the prior engine's documented App input, preserving statuses."""
    payload: dict[str, Any] = {name: {} for name in LAYERS}
    # These constants belong to the validated P1 source contract, not a label.
    payload.update(collector_app="featureapp", schema_version="expanded-v2.2-status")
    fields: dict[str, str] = {}
    lookup: dict[str, str] = {}
    for path, value in row["features"].items():
        parts = path.split(".")
        if parts[0] != "app":
            continue
        if len(parts) < 3 or parts[1] not in LAYERS:
            raise ValueError(f"Invalid App field path: {path}")
        canonical = f"{parts[1]}.{parts[-1]}"
        if canonical in lookup:
            raise ValueError(f"Legacy leaf mapping collides: {canonical}")
        lookup[canonical] = path
        payload[parts[1]][parts[-1]] = copy.deepcopy(value)
        if path in row.get("field_status", {}):
            fields[canonical] = row["field_status"][path]
    payload["collection_status"] = {"fields": fields}
    return payload, lookup


def availability_issues(row: dict[str, Any], fields: list[str], lookup: dict[str, str]) -> list[dict[str, Any]]:
    issues = []
    for field in sorted(set(fields)):
        if field == "collector_app":
            continue  # Fixed validated P1 contract; no label or P2 metadata.
        path = lookup.get(field)
        if path is None:
            issues.append({"field": field, "reason": "missing_field"})
            continue
        state = row.get("field_status", {}).get(path)
        quality = row.get("field_quality", {}).get(path)
        value = row["features"][path]
        if state != "observed":
            issues.append({"field": path, "reason": "source_status", "status": state})
        elif quality != "observed_value":
            issues.append({"field": path, "reason": "field_quality", "quality": quality})
        elif value is None or value == "":
            issues.append({"field": path, "reason": "missing_value"})
    return issues


def gate_result(row: dict[str, Any], result: dict[str, Any], lookup: dict[str, str]) -> dict[str, Any]:
    result = copy.deepcopy(result)
    issues = availability_issues(row, result.get("source_fields", []), lookup)
    result["pre_gate_outcome"] = result["outcome"]
    result["availability_issues"] = issues
    if issues:
        result["outcome"] = "unknown_availability_gate"
    return result


def provider_diagnostic(row: dict[str, Any]) -> dict[str, Any]:
    """Explain provider/UA namespace evidence, without declaring a device safe."""
    _, lookup = app_payload(row)
    names = ("webview_provider_package", "webview_provider_version", "webview_provider_version_code",
             "webview_provider_major", "default_ua_native", "settings_user_agent")
    selected = [f"webview_data.{name}" for name in names] + ["web_data.user_agent"]
    values = {field: row["features"].get(lookup.get(field)) for field in selected}
    def chrome_major(value):
        match = re.search(r"(?:Chrome|CriOS)/(\d{1,3})", str(value or ""))
        return int(match.group(1)) if match else None
    version = values["webview_data.webview_provider_version"]
    version_head = str(version).split(".", 1)[0]
    version_head = int(version_head) if version_head.isdigit() else None
    runtime = values["web_data.user_agent"]
    provider_major = values["webview_data.webview_provider_major"]
    issues = availability_issues(row, selected, lookup)
    aligned = (values["webview_data.default_ua_native"] == values["webview_data.settings_user_agent"] == runtime)
    namespace_counterexample = (not issues and aligned and version_head == provider_major
                               and chrome_major(runtime) is not None and provider_major != chrome_major(runtime))
    return {"sample_id": row["sample_id"], "split": row["_p2"]["split"], "group_id": row["_p2"]["group_id"],
            "profile": row.get("profile"), "source_refs": row.get("source_refs"),
            "provider_package": values["webview_data.webview_provider_package"], "provider_version": version,
            "provider_version_code": values["webview_data.webview_provider_version_code"], "provider_major": provider_major,
            "version_name_first_component": version_head,
            "default_ua_chrome_major": chrome_major(values["webview_data.default_ua_native"]),
            "settings_ua_chrome_major": chrome_major(values["webview_data.settings_user_agent"]),
            "runtime_ua_chrome_major": chrome_major(runtime), "default_settings_runtime_ua_exact_equal": aligned,
            "availability_issues": issues, "namespace_equality_counterexample": namespace_counterexample,
            "evidence_fields": {lookup[field]: {"value": values[field], "status": row["field_status"].get(lookup[field]),
                                  "quality": row["field_quality"].get(lookup[field])} for field in selected if field in lookup},
            "interpretation": "Package version first component is not a universal Chromium-major namespace; observed UA agreement does not prove benign ground truth."}


def category(outcome: str) -> str:
    if outcome in {"matched", "inconsistent"}:
        return "violation"
    if outcome in {"not_matched", "consistent"}:
        return "condition_not_violated"
    if outcome == "context_observed":
        return "context"
    if outcome == "not_applicable":
        return "not_applicable"
    return "unknown_or_not_evaluated"


def evaluate_record(row, registry, kb, catalog):
    payload, lookup = app_payload(row)
    evidence = build_evidence_bundle_v2(payload, sample_id=row["sample_id"])
    ordered = execute_deterministic_rules(evidence, predicate_registry=registry)
    rules = {str(rule["id"]): rule for rule in kb["rules"]}
    independent = [_evaluate(rules[rule_id], spec, evidence["derived_facts"])
                   for rule_id, spec in registry["compiled_rules"].items()]
    official = evaluate_official_semantics(payload, sample_id=row["sample_id"], catalog=catalog)
    official_results = official["relation_execution"]["relation_results"]
    return {
        "device_mined_rule": {
            "legacy_ordered": ordered["rule_results"],
            "legacy_independent_diagnostic": independent,
            "availability_gated_diagnostic": [gate_result(row, r, lookup) for r in independent],
        },
        "official_derived_semantic_rule": {
            "legacy_original": official_results,
            "availability_gated_diagnostic": [gate_result(row, r, lookup) for r in official_results],
        },
    }, lookup


def new_aggregate():
    return {"outcomes": Counter(), "categories": Counter(), "groups": defaultdict(set),
            "all_groups": set(), "evaluable_groups": set(), "gate_changed": 0}


def aggregate_result(aggregate, result, group_id):
    outcome = result["outcome"]
    kind = category(outcome)
    aggregate["outcomes"][outcome] += 1
    aggregate["categories"][kind] += 1
    aggregate["groups"][kind].add(group_id)
    aggregate["all_groups"].add(group_id)
    if kind in {"violation", "condition_not_violated", "context"}:
        aggregate["evaluable_groups"].add(group_id)
    if "pre_gate_outcome" in result and result["pre_gate_outcome"] != outcome:
        aggregate["gate_changed"] += 1


def finish_aggregate(key, value):
    split, source, mode, rule_id = key
    categories = dict(value["categories"])
    return {"split": split, "source": source, "mode": mode, "rule_id": rule_id,
            "records": sum(value["outcomes"].values()),
            "evaluable_records": sum(categories.get(c, 0) for c in ("violation", "condition_not_violated", "context")),
            "outcome_counts": dict(value["outcomes"]), "category_counts": categories,
            "total_groups": len(value["all_groups"]),
            "evaluable_groups": len(value["evaluable_groups"]),
            "groups_by_category": {k: len(v) for k, v in value["groups"].items()},
            "availability_gate_changed_records": value["gate_changed"]}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def freeze_sources(output_dir):
    frozen = output_dir / "frozen_legacy"
    for relative in FROZEN_FILES:
        target = frozen / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / relative, target)
    shutil.copyfile(Path(__file__), output_dir / "runner.py")
    return frozen


def run_baseline(plan_dir: Path, output_dir: Path):
    from hybridguard_agent.research.mtc_p3_data import load_split_records
    if output_dir.exists():
        raise ValueError(f"Refusing to replace existing output: {output_dir}")
    # Load only the two public P2 input lists through the guarded shared reader.
    rows_by_split = {split: load_split_records(plan_dir, split) for split in SPLITS}
    registry = load_predicate_registry()
    assert_pinned_rule_kb(registry)  # The existing historical contract, not a new integrity regime.
    kb = load_rule_knowledge_base()
    catalog = load_semantic_catalog()
    output_dir.mkdir(parents=True)
    frozen = freeze_sources(output_dir)
    aggregates = defaultdict(new_aggregate)
    counterexample_count = Counter()
    split_summaries = {}
    uncompiled = {
        "device_mined_rule": sorted(str(r["id"]) for r in kb["rules"] if str(r["id"]) not in registry["compiled_rules"]),
        "official_derived_semantic_rule": sorted(r["relation_id"] for r in catalog["relations"] if r["executable_status"] != "compiled_v1"),
    }
    with (output_dir / "sample_results.jsonl").open("w", encoding="utf-8") as samples, \
         (output_dir / "counterexamples.jsonl").open("w", encoding="utf-8") as counterexamples, \
         (output_dir / "provider_counterexample_diagnostics.jsonl").open("w", encoding="utf-8") as provider_diagnostics:
        for split, rows in rows_by_split.items():
            split_summary = {"records": len(rows), "groups": len({r["_p2"]["group_id"] for r in rows}),
                             "sample_outcomes": defaultdict(Counter), "group_outcomes": defaultdict(lambda: defaultdict(set))}
            for row in rows:
                controls = row["_p2"]
                if controls["split"] != split:
                    raise ValueError("Split control mismatch")
                results, lookup = evaluate_record(row, registry, kb, catalog)
                sample = {"sample_id": row["sample_id"], "split": split, "group_id": controls["group_id"],
                          "profile": row.get("profile"), "results": results,
                          "not_executable_rule_ids": uncompiled}
                samples.write(json.dumps(sample, ensure_ascii=False) + "\n")
                for source, modes in results.items():
                    for mode, evaluated in modes.items():
                        all_results = evaluated + [{"rule_id": rule_id, "outcome": "not_executable"} for rule_id in uncompiled[source]]
                        kinds = {category(r["outcome"]) for r in evaluated}
                        # A partial/unknown record is never labelled a clean/normal negative.
                        sample_status = ("violation_observed" if "violation" in kinds else
                                         "incomplete_compiled_assessment" if "unknown_or_not_evaluated" in kinds else
                                         "no_violation_observed_in_compiled_rules")
                        mode_key = source + "/" + mode
                        split_summary["sample_outcomes"][mode_key][sample_status] += 1
                        split_summary["group_outcomes"][mode_key][sample_status].add(controls["group_id"])
                        for result in all_results:
                            rule_id = result.get("rule_id", result.get("relation_id"))
                            aggregate_result(aggregates[(split, source, mode, rule_id)], result, controls["group_id"])
                            if mode != "availability_gated_diagnostic" or category(result["outcome"]) != "violation":
                                continue
                            fields = result.get("source_fields", [])
                            observed = {lookup[field]: {"value": row["features"][lookup[field]],
                                        "status": row["field_status"].get(lookup[field]),
                                        "quality": row["field_quality"].get(lookup[field])}
                                        for field in fields if field in lookup}
                            counterexamples.write(json.dumps({"sample_id": row["sample_id"], "split": split,
                                "group_id": controls["group_id"], "profile": row.get("profile"), "source": source,
                                "rule_id": rule_id, "outcome": result["outcome"], "evidence_fields": observed,
                                "claim": "Counterexample to legacy condition; no independent attack or benign label."}, ensure_ascii=False) + "\n")
                            counterexample_count[f"{split}/{source}"] += 1
                            if rule_id == "OFFDER-WEBVIEW-001":
                                provider_diagnostics.write(json.dumps(provider_diagnostic(row), ensure_ascii=False) + "\n")
            split_summary["sample_outcomes"] = {k: dict(v) for k, v in split_summary["sample_outcomes"].items()}
            split_summary["group_outcomes"] = {k: {outcome: len(groups) for outcome, groups in v.items()}
                                               for k, v in split_summary["group_outcomes"].items()}
            split_summaries[split] = split_summary
    rule_summaries = [finish_aggregate(key, aggregates[key]) for key in sorted(aggregates)]
    with (output_dir / "rule_summary.jsonl").open("w", encoding="utf-8") as handle:
        for summary in rule_summaries:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
    # Fail rather than conceal an engine/catalogue change while the run was executing.
    for relative in FROZEN_FILES:
        if (REPO / relative).read_bytes() != (frozen / relative).read_bytes():
            raise ValueError(f"Legacy source changed during the run: {relative}")
    summary = {"version": "mtc-legacy-rule-baseline-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
               "plan_dir": str(plan_dir.resolve()), "splits": split_summaries,
               "catalogues": {"device_mined_rule": {"total": len(kb["rules"]), "compiled": len(registry["compiled_rules"])},
                              "official_derived_semantic_rule": {"total": len(catalog["relations"]), "compiled": len(catalog["relations"]) - len(uncompiled["official_derived_semantic_rule"])}},
               "not_executable_rule_ids": uncompiled, "counterexample_records": dict(counterexample_count),
               "reserved_validation": "NOT_READ_NOT_EVALUATED",
               "legacy_target": "NONE", "metrics": {"FPR": None, "TPR": None, "F1": None},
               "payload_scope": "App177 features and source status only; Browser67 and P2 controls excluded",
               "input_constants": {"collector_app": "featureapp", "schema_version": "expanded-v2.2-status",
                                   "source": "frozen_legacy/hybridguard_agent/config/mtc_paired244_sources.v2.json"},
               "modes": {"legacy_ordered": "Unmodified deployed deterministic engine, including CORE-002 short-circuit",
                         "legacy_independent_diagnostic": "Unmodified predicate functions run independently; not deployed sequence",
                         "legacy_original": "Unmodified official evaluator",
                         "availability_gated_diagnostic": "Independent/original outcomes gated by explicit observed status and P1 observed_value quality; no threshold changes"},
               "group_count_boundary": "Categories may overlap within a group across distinct OS representatives; never add category group counts to infer total groups.",
               "claim_boundary": "Unlabelled descriptive compatibility replay; no normal/attack ground truth, no ranking or target based on old performance.",
               "frozen_files": list(FROZEN_FILES)}
    write_json(output_dir / "summary.json", summary)
    for path in frozen.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=REPO / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_baseline(args.plan_dir, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
