#!/usr/bin/env python3
"""Freeze a stable MTC source copy and inventory receipts, without experiment QC.

An open backend batch stays open. The cutoff is a stable filesystem read window,
not a fabricated lifecycle close. Raw files are copied verbatim; no rules run.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
FILES = (
    "active_collection_batch.json", "collection_batches.jsonl",
    "collection_receipts.jsonl", "expanded_collected_data.jsonl",
    "expanded_merged_sessions.json", "raw_expanded_payloads.jsonl",
    "browser_collected_data.jsonl", "raw_browser_payloads.jsonl",
    "browser_provisional_payloads.jsonl", "browser_pair_events.jsonl",
    "browser_pair_provenance.jsonl",
)
PRINCIPLE = (
    "旧实验数据质量较低，新实验仅参考设计思路；不继承旧结论、指标或方法排名，"
    "不以达到旧效果为优化目标或验收下限。以新数据、独立事实和冻结协议形成结论。"
)


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path, rows):
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def signatures(source, retired=False):
    names = tuple(name for name in FILES if not (retired and name == "active_collection_batch.json"))
    observed = {p.name for p in source.iterdir() if p.is_file() and p.suffix in {".json", ".jsonl"}}
    if observed != set(names):
        raise ValueError(f"Source file set differs: missing={set(names)-observed}, extra={observed-set(names)}")
    result = {}
    for name in names:
        s = (source / name).stat()
        result[name] = {"size_bytes": s.st_size, "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns, "inode": s.st_ino}
    return result


def read_sources(folder, names=FILES):
    data, counts = {}, {}
    for name in names:
        text = (folder / name).read_text()
        if name.endswith(".jsonl"):
            numbered = [(i, json.loads(line)) for i, line in enumerate(text.splitlines(), 1) if line.strip()]
            if any(not isinstance(row, dict) for _, row in numbered):
                raise ValueError(f"Non-object JSONL row: {name}")
            data[name] = numbered
            counts[name] = len(numbered)
        else:
            data[name] = json.loads(text)
    return data, counts


def index(rows, key):
    result = defaultdict(list)
    for line, row in rows:
        result[row.get(key)].append((line, row))
    return result


def profile(payload):
    m = payload.get("collection_manifest", {})
    return tuple(m.get(k) for k in ("manufacturer", "model", "android_release"))


def profile_dict(key):
    return dict(zip(("manufacturer", "model", "android_release"), key))


def one(items):
    return items[0] if len(items) == 1 else None


def inventory(data, cutoff, expected_count=None, procurement_waived=False):
    procurement_status = "NOT_REQUIRED_USER_WAIVED" if procurement_waived else "UNRESOLVED_PURCHASE_ROSTER"
    rows = lambda name: data[name + ".jsonl"]
    app = rows("expanded_collected_data")
    raw_app = rows("raw_expanded_payloads")
    raw_browser = rows("raw_browser_payloads")
    receipts = rows("collection_receipts")
    pair_rows = rows("browser_pair_provenance")
    completed = [(line, row) for line, row in pair_rows if row.get("pair_status") == "completed"]
    raw_by_receipt = index(raw_app, "receipt_id")
    receipt_index = index(receipts, "receipt_id")
    browser_index = index(raw_browser, "browser_receipt_id")
    browser_analysis_index = index(rows("browser_collected_data"), "pair_id")
    raw_by_identity = defaultdict(list)
    for line, row in raw_app:
        raw_by_identity[(row.get("session_id"), row.get("payload_sha256"), row.get("collection_batch_id"))].append((line, row))

    pair_inventory, issues = [], []
    completed_by_session = defaultdict(list)
    paired_profiles = Counter()
    paired_installs = Counter()
    version_counts, api_counts, browser_counts, batch_counts = (Counter() for _ in range(4))
    for line, pair in completed:
        errors = []
        receipt = one(receipt_index[pair.get("app_receipt_id")])
        raw = one(raw_by_receipt[pair.get("app_receipt_id")])
        alias = False
        if raw is None and receipt is not None:
            r = receipt[1]
            candidates = raw_by_identity[(pair.get("app_session_id"), pair.get("app_payload_sha256"), pair.get("collection_batch_id"))]
            if r.get("duplicate_payload") is True and r.get("stored_new_jsonl_row") is False:
                raw = one(candidates)
                alias = raw is not None
        browser = one(browser_index[pair.get("browser_receipt_id")])
        browser_analysis = one(browser_analysis_index[pair.get("pair_id")])
        if receipt is None:
            errors.append("app_receipt_not_unique_or_missing")
        elif any(receipt[1].get(key) != expected for key, expected in (
            ("session_id", pair.get("app_session_id")), ("payload_sha256", pair.get("app_payload_sha256")),
            ("collection_batch_id", pair.get("collection_batch_id")),
        )):
            errors.append("app_receipt_reference_mismatch")
        if raw is None:
            errors.append("app_raw_not_uniquely_resolved")
        elif any(raw[1].get(key) != expected for key, expected in (
            ("session_id", pair.get("app_session_id")), ("payload_sha256", pair.get("app_payload_sha256")),
            ("collection_batch_id", pair.get("collection_batch_id")),
        )):
            errors.append("app_raw_reference_mismatch")
        if browser is None:
            errors.append("browser_raw_not_unique_or_missing")
        elif any(browser[1].get(key) != pair.get(key) for key in (
            "pair_id", "app_session_id", "app_receipt_id", "browser_session_id", "browser_payload_sha256", "collection_batch_id",
        )):
            errors.append("browser_raw_reference_mismatch")
        if browser_analysis is None:
            errors.append("browser_analysis_not_unique_or_missing")
        payload = raw[1].get("canonical_received_payload", {}) if raw else {}
        m = payload.get("collection_manifest", {})
        key = profile(payload)
        if any(v in (None, "") for v in key):
            errors.append("model_os_profile_incomplete")
        else:
            paired_profiles[key] += 1
        if m.get("collector_install_id"):
            paired_installs[m["collector_install_id"]] += 1
        version_counts[str(m.get("collector_version_name"))] += 1
        api_counts[str(m.get("android_api"))] += 1
        browser_counts[str(pair.get("selected_browser_package"))] += 1
        batch_counts[str(pair.get("collection_batch_id"))] += 1
        completed_by_session[pair.get("app_session_id")].append(pair["pair_id"])
        entry = {
            "pair_id": pair["pair_id"], "app_session_id": pair.get("app_session_id"),
            "paired_at": pair.get("paired_at"), "collection_batch_id": pair.get("collection_batch_id"),
            "profile": profile_dict(key), "collector_install_id": m.get("collector_install_id"),
            "collector_version_code": m.get("collector_version_code"), "collector_version_name": m.get("collector_version_name"),
            "reference_status": "unresolved" if errors else "duplicate_receipt_alias_resolved" if alias else "resolved",
            "provenance_line": line, "app_receipt_line": receipt[0] if receipt else None,
            "app_raw_line": raw[0] if raw else None, "browser_raw_line": browser[0] if browser else None,
            "browser_analysis_line": browser_analysis[0] if browser_analysis else None,
            "app_receipt_id": pair.get("app_receipt_id"),
            "archived_app_receipt_id": raw[1].get("receipt_id") if raw else None,
            "app_payload_sha256_from_ledger": pair.get("app_payload_sha256"),
            "reference_errors": errors, "experiment_qc_status": "NOT_EVALUATED",
        }
        pair_inventory.append(entry)
        if errors:
            issues.append({"pair_id": pair["pair_id"], "errors": errors})

    completed_ids = set(row["pair_id"] for row in pair_inventory)
    analysis_index = index(app, "session_id")
    app_inventory, all_profiles = [], defaultdict(set)
    for session, observations in sorted(analysis_index.items()):
        keys = {profile(row) for _, row in observations}
        for key in keys:
            all_profiles[key].add(session)
        app_inventory.append({
            "app_session_id": session, "analysis_rows": len(observations),
            "analysis_source_lines": [line for line, _ in observations],
            "profiles": [profile_dict(k) for k in sorted(keys, key=str)],
            "profile_metadata_conflict": len(keys) != 1,
            "completed_pair_ids": completed_by_session.get(session, []),
            "receipt_pairing_status": "completed" if session in completed_by_session else "no_completed_pair_at_cutoff",
            "experiment_qc_status": "NOT_EVALUATED",
        })

    events = rows("browser_pair_events")
    by_pair = defaultdict(list)
    for line, event in events:
        if event.get("pair_id"):
            by_pair[event["pair_id"]].append((line, event))
    attempts = []
    for pair_id, history in sorted(by_pair.items()):
        issued = [e for _, e in history if e.get("event") in {"ticket_issued", "provisional_ticket_issued"}]
        last = history[-1][1]
        stages = [e.get("browser_stage") for _, e in history if e.get("browser_stage")]
        deadlines = [e.get("poll_expires_at" if last.get("pair_status") == "awaiting_app" else "ticket_expires_at") for _, e in history]
        deadline = next((x for x in reversed(deadlines) if x), None)
        deadline_passed = bool(deadline and datetime.fromisoformat(deadline.replace("Z", "+00:00")) < datetime.fromisoformat(cutoff.replace("Z", "+00:00")))
        attempts.append({
            "pair_id": pair_id, "issued_event_count": len(issued), "event_count": len(history),
            "completed_receipt_at_cutoff": pair_id in completed_ids,
            "last_recorded_pair_status": last.get("pair_status"),
            "last_event": last.get("event"), "last_event_at": last.get("event_at"),
            "last_observed_browser_stage": stages[-1] if stages else None,
            "deadline": deadline, "deadline_passed_without_completed_receipt": deadline_passed and pair_id not in completed_ids,
            "deadline_interpretation": "offline_observation_only_not_backend_state_mutation",
        })
    noncomplete = [r for r in attempts if not r["completed_receipt_at_cutoff"]]
    profile_inventory = []
    for key in sorted(set(all_profiles) | set(paired_profiles), key=str):
        profile_inventory.append({
            **profile_dict(key), "app_session_count": len(all_profiles[key]),
            "completed_pair_count": paired_profiles[key],
            "procurement_match_status": procurement_status,
        })
    batch_latest = {}
    for _, row in rows("collection_batches"):
        batch_latest[row["collection_batch_id"]] = row
    summary = {
        "scope": "baidu_mtc_dedicated_directory_user_confirmed",
        "cutoff_utc": cutoff, "research_principle": PRINCIPLE,
        "completed_provenance_rows": len(completed), "unique_completed_pairs": len(completed_ids),
        "unique_paired_app_sessions": len(completed_by_session),
        "paired_install_profiles": len(paired_installs),
        "paired_manufacturer_model": len({key[:2] for key in paired_profiles}),
        "paired_manufacturer_model_os": len(paired_profiles),
        "repeated_model_os_groups": sum(n > 1 for n in paired_profiles.values()),
        "extra_model_os_sessions": sum(n - 1 for n in paired_profiles.values()),
        "repeated_install_groups": sum(n > 1 for n in paired_installs.values()),
        "extra_install_sessions": sum(n - 1 for n in paired_installs.values()),
        "app_analysis_rows": len(app), "app_analysis_unique_sessions": len(analysis_index),
        "extra_analysis_rows_same_session": len(app) - len(analysis_index),
        "app_sessions_without_completed_pair": len(set(analysis_index) - set(completed_by_session)),
        "all_app_model_os_profiles": len(all_profiles),
        "app_model_os_profiles_without_completed_pair": len(set(all_profiles) - set(paired_profiles)),
        "app_receipts": len(receipts), "duplicate_app_receipts": sum(r.get("duplicate_payload") is True for _, r in receipts),
        "receipt_validation_counts": dict(Counter(r.get("validation_status") for _, r in receipts)),
        "raw_app_archive_rows": len(raw_app), "raw_browser_archive_rows": len(raw_browser),
        "pair_reference_status_counts": dict(Counter(r["reference_status"] for r in pair_inventory)),
        "unresolved_pair_reference_count": len(issues),
        "browser_pair_attempts": len(attempts), "issued_pair_attempts": sum(r["issued_event_count"] > 0 for r in attempts),
        "uncompleted_pair_attempts": len(noncomplete),
        "uncompleted_last_recorded_states": dict(Counter(r["last_recorded_pair_status"] for r in noncomplete)),
        "deadline_elapsed_uncompleted_attempts": sum(r["deadline_passed_without_completed_receipt"] for r in noncomplete),
        "event_counts": dict(Counter(r.get("event") for _, r in events)),
        "paired_release_counts": dict(version_counts), "paired_api_counts": dict(api_counts),
        "paired_browser_package_counts": dict(browser_counts), "paired_batch_counts": dict(batch_counts),
        "batch_lifecycle_states": {k: v.get("lifecycle_status") for k, v in batch_latest.items()},
        "last_completed_at_utc": max((r["paired_at"] for r in pair_inventory), default=None),
        "procurement": {
            "expected_count_user_reported": None if procurement_waived else expected_count, "status": procurement_status,
            "purchase_roster_provided": False, "arithmetic_gap_only": None if procurement_waived or expected_count is None else expected_count - len(paired_profiles),
            "exact_missing_purchase_items": None,
            "boundary": "User accepted own observed inventory as the statistical basis; no purchase target or purchase completion rate." if procurement_waived else "The arithmetic gap is not an audited count of missing purchased devices; aliases and provider entries remain unmapped.",
        },
        "source_freeze_complete": True, "receipt_inventory_complete": not issues,
        "procurement_reconciliation_complete": False, "procurement_reconciliation_required": not procurement_waived,
        "statistical_basis": "observed_mtc_inventory", "p0_complete": procurement_waived and not issues,
        "formal_experiment_qc": "NOT_EVALUATED_P1_REQUIRED",
        "rules_executed": False, "old_experiment_performance_used_as_target": False,
    }
    if len(completed) != len(completed_ids):
        raise ValueError("Duplicate completed pair IDs; preserve source but do not certify P0 inventory")
    if set(completed_by_session) - set(analysis_index):
        raise ValueError("Completed pair lacks an App analysis session")
    if sum(paired_profiles.values()) != len(completed) or issues:
        raise ValueError(f"Pair references require investigation: {issues}")
    return summary, {
        "paired_receipt_inventory.jsonl": pair_inventory,
        "app_session_inventory.jsonl": app_inventory,
        "browser_attempt_inventory.jsonl": attempts,
        "model_os_inventory.jsonl": profile_inventory,
        "reference_issues.jsonl": issues,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    evidence = parser.add_mutually_exclusive_group(required=True)
    evidence.add_argument("--readiness", type=Path)
    evidence.add_argument("--retirement-evidence", type=Path)
    parser.add_argument("--expected-purchased", type=int)
    parser.add_argument("--procurement-waived", action="store_true")
    args = parser.parse_args()
    source, output = args.source_dir.resolve(), args.output_dir.resolve()
    if output.exists() or output == source or source in output.parents:
        raise ValueError("Output must be a new directory outside the live source")
    retired = args.retirement_evidence is not None
    readiness = json.loads((args.retirement_evidence or args.readiness).read_text())
    if retired:
        services = {r["service"]: r["status"] for r in readiness.get("services", [])}
        if services != {"ngrok": "stopped", "backend": "stopped"} or readiness.get("active_batch_file_exists") is not False or readiness.get("backend_port_8000_listening") is not False:
            raise ValueError("Retirement evidence does not confirm stopped collection")
    elif readiness.get("status") != "ready" or readiness.get("collection_storage_name") != source.name or readiness.get("collection_storage_isolated") is not True:
        raise ValueError("Readiness does not identify the requested isolated source")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output.name + ".building-", dir=output.parent))
    try:
        before = signatures(source, retired=retired)
        cutoff = now()
        copied = staging / "sources"
        copied.mkdir()
        for name in before:
            shutil.copyfile(source / name, copied / name)
            if (copied / name).stat().st_size != before[name]["size_bytes"]:
                raise RuntimeError("Copied byte length changed: " + name)
        if signatures(source, retired=retired) != before:
            raise RuntimeError("Live collection changed during copy; no freeze published")
        copy_finished = now()
        data, line_counts = read_sources(copied, before)
        active = data.get("active_collection_batch.json")
        if retired:
            latest = {r["collection_batch_id"]: r for _, r in data["collection_batches.jsonl"]}
            closed = readiness["batch_close"]
            if latest.get(closed["collection_batch_id"]) != closed or any(r.get("lifecycle_status") != "closed_cleanly" or r.get("event") != "closed" for r in latest.values()):
                raise ValueError("Frozen batch ledger does not confirm clean retirement")
        elif active["collection_batch_id"] != readiness.get("collection_batch_id"):
            raise ValueError("Readiness and frozen active batch differ")
        summary, ledgers = inventory(data, cutoff, args.expected_purchased, args.procurement_waived)
        summary["collection_retired"] = retired
        for filename, entries in ledgers.items():
            write_jsonl(staging / filename, entries)
        write_json(staging / "SUMMARY.json", summary)
        write_json(staging / ("retirement_evidence.json" if retired else "readiness_at_freeze.json"), readiness)
        contracts = staging / "contracts"
        contracts.mkdir()
        contract_paths = [
            "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
            "browser_probe_site/public/probe/manifest.json",
            "android_app/HybridGuard/featureapp/build.gradle.kts",
        ]
        for path in contract_paths:
            shutil.copyfile(REPO / path, contracts / Path(path).name)
        try:
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            revision = None
        manifest = {
            "freeze_schema_version": "mtc-p0-closed-source-copy-v2" if retired else "mtc-p0-stable-source-copy-v1",
            "freeze_directory": str(output), "source_directory": str(source),
            "cutoff_utc": cutoff, "stable_read_window_finished_utc": copy_finished,
            "backend_batch_lifecycle_changed": False, "active_batch_state_preserved": active,
            "collection_retired": retired,
            "boundary": "Source file set and metadata unchanged across copy window; JSON parsed from copied bytes. Batch lifecycle preserved exactly as recorded. Retirement requires all batches closed cleanly; experiment QC is a later gate.",
            "source_files": {name: {**before[name], "jsonl_record_count": line_counts.get(name)} for name in before},
            "contract_source_paths": contract_paths,
            "repository_head": revision, "code_state_note": "Existing working-tree changes retained; HEAD alone does not describe all working files.",
            "snapshot_access": "local read-only files, not a cryptographic or write-once attestation",
            "research_principle": PRINCIPLE,
        }
        write_json(staging / "FREEZE_MANIFEST.json", manifest)
        shutil.copyfile(Path(__file__), staging / "freeze_script.py")
        for path in staging.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        copied.chmod(0o555)
        contracts.chmod(0o555)
        staging.rename(output)
        print(json.dumps({"freeze_directory": str(output), "cutoff_utc": cutoff, "summary": summary}, ensure_ascii=False, indent=2))
    except Exception:
        # Never touch the source or a previous run; only remove our unpublished copy.
        for path in staging.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                path.chmod(0o644)
        shutil.rmtree(staging)
        raise


if __name__ == "__main__":
    main()
