#!/usr/bin/env python3
"""Audit persisted P6 results without evaluating rules or rereading raw features."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from math import isclose
from pathlib import Path
from statistics import mean
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "hybridguard_agent/artifacts/mtc_p6_fixed_20260923"
P2 = ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922"
OLD = ROOT / "hybridguard_agent/artifacts/mtc_closed_resource_runtime_20260922"
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def lines(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def main():
    rows = list(lines(OUT / "results.jsonl"))
    specs = {r["id"]: r for r in read(OUT / "variant_registry.json")}
    manifest = list(lines(P2 / "split_manifest.jsonl"))
    primary = {r["sample_id"]: r for r in manifest if r["analysis_role"] == "primary_representative"}
    repeat_manifest = {r["sample_id"]: r for r in manifest if r["analysis_role"] == "paired_repeat_observation"}
    indexed = {(r["sample_id"], r["variant"]): r for r in rows}
    assert len(rows) == len(indexed) == 13365
    assert len(primary) == 891 and len(specs) == 15
    assert set(indexed) == {(sid, v) for sid in primary for v in specs}
    grouped = defaultdict(list)
    expected_counters = set()
    for row in rows:
        ref, spec = primary[row["sample_id"]], specs[row["variant"]]
        assert all(row[k] == ref[k] for k in ("split", "group_id", "analysis_role"))
        assert row["status"] == "COMPLETE" and row["verification_valid"] is True
        assert row["attack_classification"] == "NOT_EVALUATED"
        assert set(row["rule_outcomes"]) == set(spec["active_rule_ids"])
        assert len(row["rule_outcomes"]) == row["active_checks"] == spec["active_count"]
        assert Counter(row["rule_outcomes"].values()) == row["outcome_counts"]
        grouped[(row["split"], row["variant"])].append(row)
        for rid, outcome in row["rule_outcomes"].items():
            if outcome in {"COUNTEREXAMPLE", "POLICY_MISMATCH"}:
                expected_counters.add((row["sample_id"], row["variant"], rid, outcome))
    counters = list(lines(OUT / "counterexamples.jsonl"))
    actual_counters = {(r["sample_id"], r["variant"], r["rule_result"]["rule_id"],
                        r["rule_result"]["outcome"]) for r in counters}
    assert actual_counters == expected_counters and len(counters) == len(actual_counters)

    metric_comparisons = 0
    for summary in read(OUT / "matrix_summary.json"):
        cohort = grouped[(summary["split"], summary["variant"])]
        by_group = defaultdict(list)
        for row in cohort:
            by_group[row["group_id"]].append(row)
        assert summary["records"] == len(cohort) and summary["groups"] == len(by_group)
        assert summary["decision_counts"] == Counter(r["decision_status"] for r in cohort)
        for metric, reported in summary["group_weighted_means"].items():
            independent = mean(mean(r["metrics"][metric] for r in group) for group in by_group.values())
            assert isclose(independent, reported, rel_tol=1e-12, abs_tol=1e-12)
            metric_comparisons += 1

    catalog_checks = 0
    for spec in specs.values():
        source = read(OUT / "frozen_sources/hybridguard_agent/config" /
                      f"paired244_rule_catalog.{spec['catalog']}.json")
        source_rules = {r["rule_id"]: r for r in source["rules"]}
        selected = {r["rule_id"]: r for r in spec["catalog_object"]["rules"] if r["status"] == "ACTIVE"}
        assert set(selected) == set(spec["active_rule_ids"])
        for rid, rule in selected.items():
            assert rule == source_rules[rid]
            catalog_checks += 1

    old_decisions = 0
    for old in lines(OLD / "results.jsonl"):
        new = indexed[(old["input_sample_id"], old["input_view"])]
        assert old["status"] == "completed" and old["verification"]["valid"] is True
        assert old["decision"]["decision_status"] == new["decision_status"]
        old_decisions += 1
    old_rule_comparisons = 0
    for old in lines(OLD / "decision_traces.jsonl"):
        new = indexed[(old["input_sample_id"], old["input_view"])]
        outcomes = {r["rule_id"]: r["outcome"] for r in old["trace"]["rule_execution"]["rule_results"]}
        for rid, outcome in new["rule_outcomes"].items():
            assert outcomes[rid] == outcome
            old_rule_comparisons += 1
    assert old_decisions == 1548 and old_rule_comparisons == 88236

    legacy = list(lines(OUT / "legacy_original_results.jsonl"))
    assert len(legacy) == 891 and {r["sample_id"] for r in legacy} == set(primary)
    assert all(r["status"] == "COMPLETE" for r in legacy)
    repeats = list(lines(OUT / "repeat_results.jsonl"))
    assert len(repeats) == 137 and {r["sample_id"] for r in repeats} == set(repeat_manifest)
    for row in repeats:
        ref = indexed[(row["reference_sample_id"], "Full244")]
        assert row["status"] == "COMPLETE" and row["verification_valid"] is True
        assert row["group_id"] == ref["group_id"] and row["split"] == ref["split"]
        assert all(row["profile"][k] == ref["profile"][k] for k in ("manufacturer", "model", "android_release"))
        changed = sorted(k for k, value in row["rule_outcomes"].items() if value != ref["rule_outcomes"][k])
        assert changed == sorted(row["changed_rule_ids"])
        assert len(changed) == row["changed_rule_count"]
    historical = list(lines(OUT / "historical_stage_results.jsonl"))
    assert len(historical) == 138 and len({r["pair_ref"] for r in historical}) == 69
    assert all(r["status"] == "COMPLETE" and not r["common_id_changes"] for r in historical)
    assert all("sample_id" not in r for r in historical)

    frozen_sources = 0
    for path in (OUT / "frozen_sources").rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (ROOT / path.relative_to(OUT / "frozen_sources")).read_bytes()
            frozen_sources += 1
    assert (OUT / "p2_control/reserved_validation_LOCK.json").read_bytes() == (P2 / "reserved_validation_LOCK.json").read_bytes()
    assert read(P2 / "reserved_validation_LOCK.json")["status"] == "LOCKED"
    release, access = read(OUT / "RESERVED_RELEASE.json"), read(HERE / "RESERVED_ACCESS.json")
    assert release["status"] == access["status"] == "CONSUMED_FIXED_EVALUATION"
    protocol, status = read(OUT / "protocol_FREEZE.json"), read(OUT / "RUN_STATUS.json")
    first_read = read(OUT / "RESERVED_FIRST_READ.json")["started_at_utc"]
    assert protocol["declared_at_utc"] < release["frozen_at_utc"] < first_read < status["completed_at_utc"]
    assert access["reserved_primary_records"] == 117 and access["reserved_repeat_records"] == 18
    assert status["status"] == "COMPLETE" and not access["new_rule_tuning_authorized"]
    source_diff = subprocess.check_output([
        "git", "diff", "--name-only", "HEAD", "--", "backend_server/collection_backups/mtc_final_20260922",
        "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final", "hybridguard_agent/artifacts/mtc_p2_frozen_20260922",
    ], cwd=ROOT, text=True)
    assert not source_diff.strip()

    app = {r["sample_id"]: r for r in grouped[("reserved_validation", "App177")]}
    full = {r["sample_id"]: r for r in grouped[("reserved_validation", "Full244")]}
    no_cross = {r["sample_id"]: r for r in grouped[("reserved_validation", "Full244_no_cross")]}
    deviates = lambda r: r["metrics"]["relation_deviation_present"] == 1
    additions = {sid for sid in full if deviates(full[sid]) and not deviates(app[sid])}
    assert len(additions) == 8
    assert {sid for sid in no_cross if deviates(no_cross[sid])} == {sid for sid in app if deviates(app[sid])}
    assert len({full[sid]["group_id"] for sid in additions}) == 8
    assert all(any(full[sid]["rule_outcomes"][rid] == "COUNTEREXAMPLE"
                   for rid in specs["Full244"]["cross_rule_ids"]) for sid in additions)

    audit = {
        "status": "PASS", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_mode": "persisted outputs only; no rule rerun, raw-feature read, model call or tuning",
        "primary_unique_cells": len(indexed), "same_primary_cohort_in_all_variants": True,
        "failed_primary_cells": 0, "all_verifiers_valid": True, "all_attack_labels_not_evaluated": True,
        "counterexample_rows_accounted_for": len(counters), "independent_group_metric_comparisons": metric_comparisons,
        "selected_rule_objects_unchanged": catalog_checks, "frozen_source_files_unchanged": frozen_sources,
        "prior_discovery_development_decisions_identical": old_decisions,
        "prior_v3_active_rule_outcomes_identical": old_rule_comparisons,
        "legacy_original_records": len(legacy), "repeat_reference_comparisons": len(repeats),
        "historical_stages_separate_from_mtc": len(historical), "reserved_additional_cross_relation_records": len(additions),
        "p2_historical_lock_unchanged": True, "p6_reserved_access_consumed": True,
        "freeze_precedes_reserved_feature_read": True, "tracked_p0_p1_p2_no_diff_from_head": True,
    }
    (HERE / "FINAL_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
