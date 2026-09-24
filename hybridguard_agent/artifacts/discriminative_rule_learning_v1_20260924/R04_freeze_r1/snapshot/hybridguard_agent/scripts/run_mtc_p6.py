#!/usr/bin/env python3
"""Run the predeclared MTC P6 matrix once, retaining failures and counterexamples."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.mtc_p6 import (
    SPLITS, METRICS, definitions, variants, read_json, read_lines, write_json,
    load_p6_rows, pack_result, group_outcome, summarize, paired_comparison,
)
from hybridguard_agent.runtime.paired244 import analyze_paired244_record
from hybridguard_agent.scripts.run_mtc_legacy_rule_baseline import evaluate_record, category, FROZEN_FILES
from hybridguard_agent.rules.executor import load_predicate_registry
from hybridguard_agent.adapters.rule_kb_adapter import load_rule_knowledge_base
from hybridguard_agent.official_semantics.evaluator import load_semantic_catalog

DEFAULT_PROTOCOL = ROOT / "hybridguard_agent/config/mtc_p6_protocol.v1.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def jsonl(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def metadata(row):
    p2 = row["_p2"]
    return {"sample_id": row["sample_id"], **p2, "profile": row["profile"],
            "collector_version_code": str(row["app"].get("collector_version_code", "unknown")),
            "browser_package": row["browser"].get("resolved_browser_package") or "unknown",
            "control_plane_joined_after_execution": True}


def execute_one(row, spec):
    started = perf_counter()
    try:
        result = analyze_paired244_record(row, input_view=spec["view"], catalog=spec["catalog_object"])
        packed, rules = pack_result(result, spec)
    except Exception as exc:
        packed = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}",
                  "active_checks": spec["active_count"], "metrics": None,
                  "attack_classification": "NOT_EVALUATED"}
        rules = []
    packed.update(variant=spec["id"], input_view=spec["view"], elapsed_ms=(perf_counter() - started) * 1000)
    return {**metadata(row), **packed}, rules


def freeze(output, plan, snapshot, protocol, specs):
    if output.exists():
        raise FileExistsError("P6 output exists; never overwrite or silently rerun reserved evaluation")
    if protocol["variants"] != definitions() or protocol["allowed_splits"] != list(SPLITS):
        raise ValueError("P6 matrix differs from the predeclared protocol")
    if (protocol["model_training"] or protocol["threshold_optimization"]
            or protocol["detection_metrics"] != "NOT_EVALUATED"):
        raise ValueError("Unsupported P6 claim or optimization")
    if specs["Full244"]["active_count"] != 57 or read_json(plan / "summary.json")["p2_status"] != "COMPLETE":
        raise ValueError("Require frozen v3 and completed P2")
    if read_json(plan / "reserved_validation_LOCK.json")["status"] != "LOCKED":
        raise ValueError("Do not rewrite the historical P2 lock")
    ledger = ROOT / protocol["release_ledger"]
    if ledger.exists():
        raise FileExistsError("This P6 protocol already claimed evaluation access; no silent second run")
    output.mkdir(parents=True)
    write_json(output / "protocol_FREEZE.json", protocol)
    write_json(output / "variant_registry.json", list(specs.values()))
    sources = set(FROZEN_FILES) | {
        "hybridguard_agent/research/mtc_p6.py", "hybridguard_agent/scripts/run_mtc_p6.py",
        "hybridguard_agent/config/mtc_p6_protocol.v1.json",
        "hybridguard_agent/scripts/run_mtc_p6_history.py", "hybridguard_agent/scripts/run_mtc_legacy_rule_baseline.py",
        "hybridguard_agent/evidence/paired244.py", "hybridguard_agent/rules/paired244.py",
        "hybridguard_agent/rules/legacy_backlog.py", "hybridguard_agent/research/mtc_closed_resource.py",
        "hybridguard_agent/research/mtc_p3_candidates.py", "hybridguard_agent/runtime/paired244.py",
        "hybridguard_agent/retrieval/paired244.py", "hybridguard_agent/adapters/paired244_catalog.py",
        "hybridguard_agent/verification/paired244.py", "hybridguard_agent/schemas/evidence_bundle_v3.schema.json",
        "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
        "knowledge_rule_validation/config/layer_ablation_attack_input_set.v1.json",
    }
    sources |= {str(p.relative_to(ROOT)) for p in (ROOT / "hybridguard_agent/config").glob("paired244*.json")}
    sources |= {str(p.relative_to(ROOT)) for pattern in ("mtc_p3*.json", "mtc_closed_resource*.json")
                for p in (ROOT / "hybridguard_agent/config").glob(pattern)}
    for name in sorted(sources):
        target = output / "frozen_sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    for name in ("summary.json", "protocol.json", "reserved_validation_LOCK.json", "split_manifest.jsonl"):
        target = output / "p2_control" / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(plan / name, target)
    write_json(output / "DATA_QC.json", read_json(snapshot / "manifest.json"))
    release = {"status": "FROZEN_FOR_FIXED_EVALUATION", "frozen_at_utc": now(),
               "protocol_frozen": True, "rules_frozen": True, "exposure_disclosed": True,
               "plan_dir": str(plan.resolve()), "snapshot_dir": str(snapshot.resolve()),
               "reserved_role": "fixed evaluation only; globally QC-exposed, not pristine external blind test",
               "historical_p2_lock_modified": False, "tuning_after_release": False}
    write_json(output / "RESERVED_RELEASE.json", release)
    claim_release(ledger, output, protocol)
    write_json(output / "RUN_STATUS.json", {"status": "RUNNING", "started_at_utc": now()})
    return output / "RESERVED_RELEASE.json"


def claim_release(ledger, output, protocol):
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("x", encoding="utf-8") as stream:
        json.dump({"protocol_version": protocol["protocol_version"], "status": "CLAIMED_BEFORE_FEATURE_READ",
                   "claimed_at_utc": now(), "output": str(output.resolve()), "p2_lock_modified": False,
                   "reserved_read_started": False, "new_rule_tuning_authorized": False}, stream, indent=2)
        stream.write("\n")


def verify_freeze(output, protocol):
    if read_json(output / "protocol_FREEZE.json") != protocol:
        raise ValueError("Protocol changed after freeze")
    for p in (output / "frozen_sources").rglob("*"):
        if p.is_file() and p.read_bytes() != (ROOT / p.relative_to(output / "frozen_sources")).read_bytes():
            raise ValueError("Implementation changed after freeze")


def legacy_replay(row, registry, kb, catalog):
    try:
        result, _ = evaluate_record(row, registry, kb, catalog)
        return {**metadata(row), "status": "COMPLETE", "results": result}
    except Exception as exc:
        return {**metadata(row), "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}


def finish(output, protocol, specs, rows, legacy_rows, repeats, history):
    indexed = defaultdict(list)
    for r in rows:
        indexed[(r["split"], r["variant"])].append(r)
    aggregates = [{"split": s, "variant": v, "active_checks": specs[v]["active_count"], **summarize(rs)}
                  for (s, v), rs in sorted(indexed.items())]
    write_json(output / "matrix_summary.json", aggregates)
    comparisons = []
    for split in SPLITS:
        for before, after in protocol["paired_contrasts"]:
            comparison = paired_comparison(indexed[(split, before)], indexed[(split, after)],
                bootstrap_replicates=protocol["bootstrap"]["replicates"], seed=protocol["bootstrap"]["seed"],
                interval=split == "reserved_validation")
            comparisons.append({"split": split, "before": before, "after": after, **comparison})
    write_json(output / "paired_comparisons.json", comparisons)
    rule_groups = defaultdict(lambda: defaultdict(list))
    rule_records = defaultdict(Counter)
    for r in rows:
        for rid in specs[r["variant"]]["active_rule_ids"]:
            state = r.get("rule_outcomes", {}).get(rid, "FAILED")
            key = (r["split"], r["variant"], rid)
            rule_groups[key][r["group_id"]].append(state)
            rule_records[key][state] += 1
    rule_summary = [{"split": s, "variant": v, "rule_id": rid,
                     "record_outcomes": dict(rule_records[(s, v, rid)]),
                     "group_outcomes": dict(Counter(group_outcome(states) for states in groups.values()))}
                    for (s, v, rid), groups in sorted(rule_groups.items())]
    write_json(output / "rule_summary.json", rule_summary)
    strata = defaultdict(list)
    for r in rows:
        if r["variant"] not in {"App177", "Full244"}:
            continue
        for dim, value in (("manufacturer", r["profile"]["manufacturer"]), ("android_api", str(r["profile"]["android_api"])),
                           ("collector_version_code", r["collector_version_code"]), ("browser_package", r["browser_package"])):
            strata[(r["split"], r["variant"], dim, value)].append(r)
    stratum_summary = [{"split": s, "variant": v, "dimension": d, "value": value,
                        "sparse_descriptive_only": len({r["group_id"] for r in rs}) < protocol["stratum_group_floor"],
                        **summarize(rs)} for (s, v, d, value), rs in sorted(strata.items())]
    write_json(output / "stratum_summary.json", stratum_summary)
    source_overlap = []
    for split in SPLITS:
        empirical = {r["sample_id"]: r for r in indexed[(split, "Full244_empirical")]}
        official = {r["sample_id"]: r for r in indexed[(split, "Full244_official")]}
        counts, group_counts = Counter(), defaultdict(set)
        for sid, emp in empirical.items():
            off = official[sid]
            if emp["status"] != "COMPLETE" or off["status"] != "COMPLETE":
                state = "FAILED"
            else:
                a, b = bool(emp["relation_evidence_families"]), bool(off["relation_evidence_families"])
                state = "both" if a and b else "empirical_only" if a else "official_only" if b else "neither_observed"
            counts[state] += 1
            group_counts[state].add(emp["group_id"])
        source_overlap.append({"split": split, "records": len(empirical), "record_categories": dict(counts),
                               "groups_per_observed_category_nonexclusive": {k: len(v) for k, v in group_counts.items()},
                               "neither_is_not_a_benign_label": True})
    write_json(output / "source_overlap.json", source_overlap)
    legacy_counts, legacy_groups, changes = defaultdict(Counter), defaultdict(lambda: defaultdict(list)), Counter()
    current = {r["sample_id"]: r for r in rows if r["variant"] == "App177"}
    for r in legacy_rows:
        if r["status"] != "COMPLETE":
            continue
        for lane, modes in r["results"].items():
            for mode, outcomes in modes.items():
                for item in outcomes:
                    rid = item.get("rule_id", item.get("relation_id"))
                    key = (r["split"], lane, mode, rid)
                    legacy_counts[key][item["outcome"]] += 1
                    legacy_groups[key][r["group_id"]].append(category(item["outcome"]))
                    if mode == "availability_gated_diagnostic":
                        new = current[r["sample_id"]].get("rule_outcomes", {}).get(rid, "NOT_ACTIVE_OR_FAILED")
                        changes[(r["split"], rid, item["outcome"], new)] += 1
    write_json(output / "legacy_summary.json", {"records": len(legacy_rows),
        "failed_records": sum(r["status"] != "COMPLETE" for r in legacy_rows),
        "rules": [{"split": s, "lane": l, "mode": m, "rule_id": rid, "record_outcomes": dict(c),
                   "groups_with_violation": sum("violation" in g for g in legacy_groups[(s, l, m, rid)].values())}
                  for (s, l, m, rid), c in sorted(legacy_counts.items())],
        "gated_old_to_v3_transitions": [{"split": s, "rule_id": rid, "old": a, "new": b, "records": n}
                                       for (s, rid, a, b), n in sorted(changes.items())]})
    repeat_summary = {"records": len(repeats), "failed_records": sum(r["status"] != "COMPLETE" for r in repeats),
        "changed_output_comparisons": sum(r.get("changed_rule_count", 0) > 0 for r in repeats),
        "same_installation_comparisons": sum(r.get("same_installation") is True for r in repeats),
        "same_installation_changed": sum(r.get("same_installation") is True and r.get("changed_rule_count", 0) > 0 for r in repeats),
        "claim": "Repeated observed model/OS or installation reports, not verified physical-device longitudinal stability."}
    write_json(output / "repeat_summary.json", repeat_summary)
    failures = sum(r["status"] != "COMPLETE" for r in [*rows, *legacy_rows, *repeats])
    summary = {"status": "COMPLETE" if not failures else "COMPLETE_WITH_FAILURES", "completed_at_utc": now(),
        "protocol_version": protocol["protocol_version"], "variants": len(specs), "primary_runtime_runs": len(rows),
        "legacy_original_records": len(legacy_rows), "repeat_runtime_runs": len(repeats), "failures": failures,
        "primary_cohort": {s: {"records": len(indexed[(s, "Full244")]),
                              "groups": len({r["group_id"] for r in indexed[(s, "Full244")]})} for s in SPLITS},
        "reserved_primary_features_evaluated": len(indexed[("reserved_validation", "Full244")]),
        "reserved_repeat_features_evaluated": sum(r["split"] == "reserved_validation" for r in repeats),
        "p2_lock_preserved": True, "model_calls": 0, "model_training": False, "threshold_optimization": False,
        "detection_metrics": "NOT_EVALUATED", "new_collection": False, "raw_data_modified": False,
        "historical_diagnostic": history, "timing_environment": {"python": platform.python_version(), "system": platform.system(),
                                                               "machine": platform.machine(), "timing_claim": "single sequential offline run including verifier; not phone latency"}}
    write_json(output / "summary.json", summary)
    return summary


def run(plan, snapshot, output, protocol_path=DEFAULT_PROTOCOL):
    protocol = read_json(protocol_path)
    specs = variants(protocol["variants"])
    release = freeze(output, plan, snapshot, protocol, specs)
    rows, legacy_rows, repeats = [], [], []
    registry, kb, legacy_catalog = load_predicate_registry(), load_rule_knowledge_base(), load_semantic_catalog()
    try:
        with (output / "results.jsonl").open("w") as results, (output / "counterexamples.jsonl").open("w") as counters, \
                (output / "legacy_original_results.jsonl").open("w") as old_results, (output / "repeat_results.jsonl").open("w") as repeated:
            for split in SPLITS:
                verify_freeze(output, protocol)
                if split == "reserved_validation":
                    write_json(output / "RESERVED_FIRST_READ.json", {"started_at_utc": now(), "rules_and_protocol_checked_before_read": True})
                    ledger = read_json(ROOT / protocol["release_ledger"])
                    ledger.update(reserved_read_started=True, reserved_read_started_at_utc=now())
                    write_json(ROOT / protocol["release_ledger"], ledger)
                inputs = load_p6_rows(plan, snapshot, split, "primary_representative", release)
                expected = protocol["primary_expected"][split]
                if len(inputs) != expected["records"] or len({r["_p2"]["group_id"] for r in inputs}) != expected["groups"]:
                    raise ValueError("Primary cohort differs from predeclared P2 counts")
                primary = {}
                print(f"P6 {split}: {len(inputs)} primary records, {len(specs)} fixed variants", flush=True)
                names = list(specs)
                for i, row in enumerate(inputs):
                    rotated = names[i % len(names):] + names[:i % len(names)]
                    for name in rotated:
                        result, rules = execute_one(row, specs[name])
                        rows.append(result); jsonl(results, result)
                        if name == "Full244":
                            profile_key = tuple(row["profile"][k] for k in ("manufacturer", "model", "android_release"))
                            if profile_key in primary:
                                raise ValueError("Duplicate P2 primary model/OS representative")
                            primary[profile_key] = result
                        for rule in rules:
                            if rule["outcome"] in {"COUNTEREXAMPLE", "POLICY_MISMATCH"}:
                                jsonl(counters, {**metadata(row), "variant": name, "rule_result": rule})
                    old = legacy_replay(row, registry, kb, legacy_catalog)
                    legacy_rows.append(old); jsonl(old_results, old)
                for row in load_p6_rows(plan, snapshot, split, "paired_repeat_observation", release):
                    result, _ = execute_one(row, specs["Full244"])
                    key = tuple(row["profile"][k] for k in ("manufacturer", "model", "android_release"))
                    base = primary[key]
                    result["reference_sample_id"] = base["sample_id"]
                    installation = row["profile"].get("collector_install_id")
                    result["same_installation"] = bool(installation) and installation == base["profile"].get("collector_install_id")
                    if result["status"] == base["status"] == "COMPLETE":
                        result["changed_rule_ids"] = [rid for rid, state in result["rule_outcomes"].items()
                                                      if state != base["rule_outcomes"][rid]]
                        result["changed_rule_count"] = len(result["changed_rule_ids"])
                    else:
                        result["status"] = "FAILED"
                    repeats.append(result); jsonl(repeated, result)
                results.flush(); old_results.flush(); counters.flush(); repeated.flush()
                print(f"P6 {split}: completed without modifying frozen rules", flush=True)
        from hybridguard_agent.scripts.run_mtc_p6_history import run_history
        history = run_history(output, protocol, specs["App177"])
        verify_freeze(output, protocol)
        summary = finish(output, protocol, specs, rows, legacy_rows, repeats, history)
        guard = read_json(release)
        guard.update(status="CONSUMED_FIXED_EVALUATION", completed_at_utc=now(),
                     primary_records=summary["reserved_primary_features_evaluated"],
                     repeat_records=summary["reserved_repeat_features_evaluated"], further_tuning_authorized=False)
        write_json(release, guard)
        ledger = read_json(ROOT / protocol["release_ledger"])
        ledger.update(status="CONSUMED_FIXED_EVALUATION", completed_at_utc=now(),
                      reserved_primary_records=summary["reserved_primary_features_evaluated"],
                      reserved_repeat_records=summary["reserved_repeat_features_evaluated"])
        write_json(ROOT / protocol["release_ledger"], ledger)
        write_json(output / "RUN_STATUS.json", {"status": summary["status"], "completed_at_utc": now()})
        return summary
    except Exception as exc:
        write_json(output / "RUN_STATUS.json", {"status": "FAILED", "failed_at_utc": now(),
                   "error": f"{type(exc).__name__}: {exc}", "completed_cells_retained": len(rows),
                   "reserved_read_started": (output / "RESERVED_FIRST_READ.json").exists(), "silent_rerun_allowed": False})
        ledger = read_json(ROOT / protocol["release_ledger"])
        ledger.update(status="FAILED_RETAINED_NO_SILENT_RETRY", failed_at_utc=now(), error=str(exc))
        write_json(ROOT / protocol["release_ledger"], ledger)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922")
    parser.add_argument("--snapshot-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.plan_dir, args.snapshot_dir, args.out_dir, args.protocol), ensure_ascii=False, indent=2))
