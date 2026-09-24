#!/usr/bin/env python3
"""Build an offline, receipt-bound MTC v2 QC snapshot from the retired P0 copy.

No collector/server is started. No rules, models, labels or split are inferred.
Every App archive row has one primary destination; revisions remain visible.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from hybridguard_agent.scripts import build_latest_paired244_snapshot as legacy
from hybridguard_agent.scripts.freeze_mtc_collection_p0 import PRINCIPLE, now
from hybridguard_agent.evidence.browser_pair_v2 import load_policy, quality_state, compare_record, semantic_equal

DEFAULT_CONFIG = REPO / "hybridguard_agent/config/mtc_paired244_sources.v2.json"
SCHEMA = "hybridguard-mtc-observation-v2"


def normalize_app(payload, release, fields, types):
    errors, features, statuses = legacy.validate_app_payload(payload, release, fields, types)
    missing, extra = set(fields) - set(features), set(features) - set(fields)
    insertable = bool(missing) and not extra and all(
        statuses.get(f) in legacy.ALLOWED_FIELD_STATES - {"observed"} for f in missing)
    if insertable:
        # A null slot carries an already-recorded unavailable state, not a value.
        features = {**features, **{f: None for f in missing}}
        errors = [e for e in errors if e != "Q_APP_FEATURESET_INVALID"]
    if set(features) == set(fields) and statuses:
        errors += legacy.feature_type_errors(features, statuses, types, "APP")
    if any(isinstance(v, float) and not math.isfinite(v) for v in features.values()):
        errors.append("Q_APP_NONFINITE_NUMBER")
    empty_layers = [root for root in legacy.APP_ROOTS
                    if not any(statuses.get(f) == "observed" for f in fields if f.startswith(root + "."))]
    return sorted(set(errors)), features, statuses, sorted(missing) if insertable else [], empty_layers


def resolve_pair_raw(pair, receipts, by_receipt, by_identity):
    matches = receipts.get(pair.get("app_receipt_id"), [])
    if len(matches) != 1:
        raise ValueError("Q_PAIR_APP_RECEIPT_NOT_UNIQUE")
    receipt = matches[0].value
    identity = (pair.get("app_session_id"), pair.get("app_payload_sha256"), pair.get("collection_batch_id"))
    if tuple(receipt.get(k) for k in ("session_id", "payload_sha256", "collection_batch_id")) != identity:
        raise ValueError("Q_PAIR_APP_RECEIPT_IDENTITY_MISMATCH")
    raw = by_receipt.get(pair.get("app_receipt_id"), [])
    alias = False
    if not raw and receipt.get("duplicate_payload") is True and receipt.get("stored_new_jsonl_row") is False:
        raw = by_identity.get(identity, [])
        alias = True
    if len(raw) != 1:
        raise ValueError("Q_PAIR_APP_ARCHIVE_NOT_UNIQUE")
    if tuple(raw[0].value.get(k) for k in ("session_id", "payload_sha256", "collection_batch_id")) != identity:
        raise ValueError("Q_PAIR_APP_ARCHIVE_IDENTITY_MISMATCH")
    return raw[0], receipt, alias


def projection_matches(analysis, payload):
    for key in ("session_id", "timestamp", "collector_app", "schema_version", "collection_manifest", "collection_status", "collection_diagnostics"):
        if analysis.get(key) != payload.get(key):
            return False
    for root in legacy.APP_ROOTS:
        leaves = legacy.feature_map(payload, (root,))
        flat = {f.rsplit(".", 1)[-1]: v for f, v in leaves.items()}
        if len(flat) != len(leaves) or legacy.canonical_json(flat) != legacy.canonical_json(analysis.get(root) or {}):
            return False
    return True


def profile(payload):
    m = payload["collection_manifest"]
    return {k: m.get(k) for k in ("manufacturer", "model", "android_release", "android_api", "collector_install_id")}


def app_record(raw, payload, features, statuses, inserted, empty_layers, policy):
    m = payload["collection_manifest"]
    return {
        "record_schema_version": SCHEMA, "sample_id": "mtc-app-" + raw.value["receipt_id"],
        "dataset_view": None, "dataset_role": "development_qc_only", "label_status": "unlabeled",
        "feature_count": len(features), "features": {"app." + k: v for k, v in features.items()},
        "field_status": {"app." + k: v for k, v in statuses.items()},
        "field_quality": {"app." + k: quality_state(k, features.get(k), v, policy) for k, v in statuses.items()},
        "app": {"session_id": payload["session_id"], "receipt_id": raw.value["receipt_id"],
                "archived_receipt_id": raw.value["receipt_id"], "payload_sha256": raw.value["payload_sha256"],
                "collector_version_code": m["collector_version_code"], "collector_version_name": m["collector_version_name"]},
        "profile": profile(payload), "identity_scope": "collector_install_profile_not_physical_device",
        "source_refs": {"app_raw_line": raw.line_number}, "collection_batch_id": raw.value["collection_batch_id"],
        "normalization": {"null_slots_added": ["app." + f for f in inserted], "raw_features_present": len(features) - len(inserted),
                          "values_imputed": False, "raw_modified": False},
        "qc": {"status": "partial" if empty_layers else "passed", "layers_without_observed_fields": empty_layers,
               "formal_experiment_admission": "NOT_EVALUATED_P2_REQUIRED"},
    }


def validate_app(raw, config, fields, types, analysis_by_session, receipts, batches, policy):
    envelope = raw.value
    payload = envelope.get("canonical_received_payload")
    if not isinstance(payload, dict):
        return None, None, ["Q_APP_CANONICAL_PAYLOAD_MISSING"], []
    m = payload.get("collection_manifest") or {}
    selected = [r for r in config["allowed_releases"] if m.get("collector_version_code") == r["featureapp_version_code"]
                and m.get("collector_version_name") == r["featureapp_version_name"]]
    if len(selected) != 1:
        return None, None, ["Q_APP_RELEASE_NOT_ALLOWLISTED"], []
    release = {**config["release_contract"], **selected[0]}
    errors, features, statuses, inserted, empty_layers = normalize_app(payload, release, fields, types)
    session = envelope.get("session_id")
    if not session or payload.get("session_id") != session:
        errors.append("Q_APP_SESSION_MISMATCH")
    if any(not isinstance(m.get(k), str) or not m[k] for k in ("manufacturer", "model", "android_release", "collector_install_id")):
        errors.append("Q_APP_PROFILE_INCOMPLETE")
    # One canonical payload identity check, required by the existing join contract.
    # There is deliberately no repeated whole-file cryptographic scan.
    if legacy.sha256_value(payload) != envelope.get("payload_sha256"):
        errors.append("Q_APP_PAYLOAD_IDENTITY_MISMATCH")
    matched = [a for a in analysis_by_session.get(session, []) if projection_matches(a.value, payload)]
    if len(matched) != 1:
        errors.append("Q_APP_ANALYSIS_PROJECTION_NOT_UNIQUE")
    rs = receipts.get(envelope.get("receipt_id"), [])
    receipt = rs[0].value if len(rs) == 1 else {}
    if (len(rs) != 1 or receipt.get("stored_new_jsonl_row") is not True or receipt.get("duplicate_payload") is not False
            or any(receipt.get(k) != envelope.get(k) for k in ("session_id", "payload_sha256", "collection_batch_id"))):
        errors.append("Q_APP_ARCHIVE_RECEIPT_MISMATCH")
    if any(v.get("collection_batch_id_source") != release["batch_id_source"] for v in (envelope, receipt)):
        errors.append("Q_APP_BATCH_SOURCE_INVALID")
    batch, batch_errors = legacy.validate_batch_ledger(batches.get(envelope.get("collection_batch_id"), []), True)
    errors += batch_errors
    if errors:
        return None, None, sorted(set(errors)), [a.line_number for a in matched]
    record = app_record(raw, payload, features, statuses, inserted, empty_layers, policy)
    record["source_refs"]["app_analysis_line"] = matched[0].line_number
    record["source_refs"]["app_receipt_line"] = rs[0].line_number
    observation = legacy.AppObservation(matched[0].value, envelope, payload, receipt, batch, features, statuses)
    return observation, record, [], [matched[0].line_number]


def field_quality_report(records, fields, types):
    """A fixed denominator per cohort/stratum; ambiguity is separate from status."""
    strata = defaultdict(lambda: {"rows": 0, "fields": defaultdict(Counter)})
    for row in records:
        group_values = {"all": "all", "version": str(row["app"]["collector_version_code"]),
                        "android_api": str(row["profile"]["android_api"])}
        if row.get("browser"):
            group_values["browser_package"] = str(row["browser"].get("resolved_browser_package"))
        for dim, value in group_values.items():
            group = strata[(dim, value)]
            group["rows"] += 1
            for field in fields:
                if field in row["features"]:
                    c = group["fields"][field]
                    c["present_slots"] += 1
                    c["status:" + row["field_status"][field]] += 1
                    c["quality:" + row["field_quality"][field]] += 1
                    if row["features"][field] is None:
                        c["null_values"] += 1
                    if field in row["normalization"]["null_slots_added"]:
                        c["derived_null_slots"] += 1
    return [{"dimension": dim, "value": val, "record_denominator": g["rows"],
             "fields": {f: {"type": types[f], **dict(c)} for f, c in sorted(g["fields"].items())}}
            for (dim, val), g in sorted(strata.items())]


def build(config_path, output):
    config = json.loads(config_path.read_text())
    if config.get("config_version") != "mtc-paired244-sources-v2":
        raise ValueError("Unsupported MTC configuration")
    freeze = legacy.resolve_repo_path(config["freeze_directory"])
    manifest = json.loads((freeze / "FREEZE_MANIFEST.json").read_text())
    p0 = json.loads((freeze / "SUMMARY.json").read_text())
    if (manifest.get("freeze_schema_version") != "mtc-p0-closed-source-copy-v2"
            or manifest.get("collection_retired") is not True or p0.get("p0_complete") is not True
            or Path(manifest["source_directory"]).name != "mtc_20260917"):
        raise ValueError("P1 requires the completed, retired MTC P0 source copy")
    if output.exists() or output == freeze or freeze in output.parents:
        raise ValueError("Output must be new and outside the P0 source freeze")
    source = freeze / "sources"
    tables = {Path(name).stem: legacy.read_jsonl(source / name) for name in manifest["source_files"] if name.endswith(".jsonl")}
    policy = load_policy(legacy.resolve_repo_path(config["comparison_policy"]))
    app_fields, web_fields, app_types, web_types = legacy.load_catalog(freeze / "contracts/expanded_v2_field_catalog.csv", 177, 67)
    probe = json.loads((freeze / "contracts/manifest.json").read_text())
    if probe.get("revision") != config["release_contract"]["browser_probe_revision"] or probe.get("signal_count") != 67:
        raise ValueError("Frozen Browser probe contract mismatch")
    receipts = legacy.index_many(tables["collection_receipts"], "receipt_id")
    batches = legacy.index_many(tables["collection_batches"], "collection_batch_id")
    analysis = legacy.index_many(tables["expanded_collected_data"], "session_id")
    raw_rows = tables["raw_expanded_payloads"]
    raw_by_receipt = legacy.index_many(raw_rows, "receipt_id")
    raw_by_identity = defaultdict(list)
    raw_by_session = legacy.index_many(raw_rows, "session_id")
    for raw in raw_rows:
        raw_by_identity[tuple(raw.value.get(k) for k in ("session_id", "payload_sha256", "collection_batch_id"))].append(raw)
    app_results, app_objects, app_errors, analysis_matches = {}, {}, {}, Counter()
    for raw in raw_rows:
        obs, record, errors, lines = validate_app(raw, config, app_fields, app_types, analysis, receipts, batches, policy)
        app_results[raw.line_number], app_objects[raw.line_number], app_errors[raw.line_number] = record, obs, errors
        analysis_matches.update(lines)
    pair_rows = tables["browser_pair_provenance"]
    pair_by_id = legacy.index_many(pair_rows, "pair_id")
    pair_by_browser = legacy.index_many(pair_rows, "browser_session_id")
    pair_by_app = legacy.index_many(pair_rows, "app_session_id")
    browser_analysis = legacy.index_many(tables["browser_collected_data"], "pair_id")
    browser_raw = legacy.index_many(tables["raw_browser_payloads"], "pair_id")
    views = {k: [] for k in ("paired_244", "app_only_177", "partial", "repeated_observations", "quarantine")}
    pair_audit, assigned, pair_records = [], {}, []
    for pair_row in pair_rows:
        pair = pair_row.value
        errors, raw, alias = [], None, False
        try:
            raw, receipt, alias = resolve_pair_raw(pair, receipts, raw_by_receipt, raw_by_identity)
            if len(pair_by_app.get(pair.get("app_session_id"), [])) != 1:
                raise ValueError("Q_PAIR_MULTIPLE_FOR_SESSION")
            obs = app_objects[raw.line_number]
            if obs is None:
                errors += app_errors[raw.line_number]
            else:
                # Alias affects only this derived binding. Original receipt remains in source_refs/app.
                joined, problems, _ = legacy.browser_pair_observation(
                    replace(obs, receipt=receipt), [pair_row], browser_analysis, browser_raw, pair_by_id, pair_by_browser,
                    config["release_contract"], web_fields, web_types)
                errors += problems
                if joined:
                    record = {**app_results[raw.line_number], **{k: joined[k] for k in ("features", "field_status", "browser", "pair")}}
                    record["sample_id"] = "mtc-pair-" + pair["pair_id"]
                    record["app"] = {**record["app"], "receipt_id": receipt["receipt_id"], "duplicate_receipt_alias": alias}
                    record["source_refs"] = {**record["source_refs"], "provenance_line": pair_row.line_number,
                                             "paired_app_receipt_line": receipts[receipt["receipt_id"]][0].line_number,
                                             "browser_raw_line": browser_raw[pair["pair_id"]][0].line_number,
                                             "browser_analysis_line": browser_analysis[pair["pair_id"]][0].line_number}
                    record["feature_count"] = len(record["features"])
                    record["field_quality"] = {k: quality_state(k.split(".", 1)[1], record["features"][k], v, policy)
                                               for k, v in record["field_status"].items()}
                    if any(isinstance(v, float) and not math.isfinite(v) for v in record["features"].values()):
                        errors.append("Q_PAIR_NONFINITE_NUMBER")
                    if not any(record["field_status"]["browser." + f] == "observed" for f in web_fields):
                        record["qc"] = {**record["qc"], "status": "partial", "layers_without_observed_fields": record["qc"]["layers_without_observed_fields"] + ["browser.web_data"]}
                    if not errors:
                        destination = "partial" if record["qc"]["status"] == "partial" else "paired_244"
                        record["dataset_view"] = destination
                        views[destination].append(record)
                        assigned[raw.line_number] = (destination, record["sample_id"])
                        pair_records.append(record)
        except ValueError as error:
            errors.append(str(error))
        audit = {"pair_id": pair.get("pair_id"), "provenance_line": pair_row.line_number,
                 "app_raw_line": raw.line_number if raw else None, "duplicate_receipt_alias": alias,
                 "destination": "quarantine" if errors else assigned[raw.line_number][0], "reasons": sorted(set(errors))}
        pair_audit.append(audit)
        if errors:
            views["quarantine"].append({"record_type": "pair", **audit})
    for session, rows in raw_by_session.items():
        paired_lines = [r.line_number for r in rows if r.line_number in assigned]
        primary = paired_lines[0] if paired_lines else min(r.line_number for r in rows)
        for raw in rows:
            line = raw.line_number
            if line in assigned:
                continue
            record = app_results[line]
            if record is None:
                destination = "quarantine"
                record = {"record_type": "app", "sample_id": "mtc-app-" + str(raw.value.get("receipt_id")),
                          "app_raw_line": line, "session_id": session, "reasons": app_errors[line]}
            elif line != primary:
                destination = "repeated_observations"
                record["revision_policy"] = "paired_receipt_first_else_first_archive_row; retained_without_quality_or_outcome_ranking"
            else:
                destination = "partial" if record["qc"]["status"] == "partial" else "app_only_177"
                record["browser_capture"] = "completed_pair_failed_qc" if session in pair_by_app else "no_completed_pair"
            record["dataset_view"] = destination
            views[destination].append(record)
            assigned[line] = (destination, record["sample_id"])
    selection = [{"source": "raw_expanded_payloads.jsonl", "source_line": r.line_number,
                  "session_id": r.value.get("session_id"), "receipt_id": r.value.get("receipt_id"),
                  "destination": assigned[r.line_number][0], "sample_id": assigned[r.line_number][1],
                  "reasons": app_errors[r.line_number]} for r in raw_rows]
    # Account for auxiliary records independently; these are not extra devices.
    auxiliary_issues = []
    for a in tables["expanded_collected_data"]:
        if analysis_matches[a.line_number] != 1:
            auxiliary_issues.append({"source": "expanded_collected_data.jsonl", "line": a.line_number,
                                     "reason": "analysis_not_uniquely_matched", "matches": analysis_matches[a.line_number]})
    for table in ("raw_browser_payloads", "browser_collected_data"):
        for row in tables[table]:
            if len(pair_by_id.get(row.value.get("pair_id"), [])) != 1:
                auxiliary_issues.append({"source": table + ".jsonl", "line": row.line_number, "reason": "browser_pair_not_unique"})
    receipt_audit = []
    for r in tables["collection_receipts"]:
        v = r.value
        identity = tuple(v.get(k) for k in ("session_id", "payload_sha256", "collection_batch_id"))
        candidates = raw_by_identity.get(identity, [])
        direct = raw_by_receipt.get(v.get("receipt_id"), [])
        status = "stored_archive" if v.get("stored_new_jsonl_row") is True and v.get("duplicate_payload") is False and len(direct) == 1 and direct == candidates else "duplicate_alias" if v.get("duplicate_payload") is True and v.get("stored_new_jsonl_row") is False and not direct and len(candidates) == 1 else "unresolved"
        receipt_audit.append({"source_line": r.line_number, "receipt_id": v.get("receipt_id"), "status": status,
                              "app_raw_lines": [x.line_number for x in candidates]})
        if status == "unresolved":
            auxiliary_issues.append({"source": "collection_receipts.jsonl", "line": r.line_number, "reason": "receipt_unresolved"})
    paired = views["paired_244"]
    paired_profiles = {(r["profile"]["manufacturer"], r["profile"]["model"], r["profile"]["android_release"]) for r in paired}
    all_app = [r for r in app_results.values() if r is not None]
    paired_fields = ["app." + f for f in app_fields] + ["browser." + f for f in web_fields]
    paired_types = {**{"app." + f: t for f, t in app_types.items()}, **{"browser." + f: t for f, t in web_types.items()}}
    comparisons = [compare_record(r, web_types, policy) for r in pair_records]
    comparison_counts = {f: dict(Counter(r["field_results"][f]["result"] for r in comparisons)) for f in web_fields}
    numeric_diagnostics = {}
    for field in web_fields:
        if web_types[field] != "number":
            continue
        c = Counter()
        for row in pair_records:
            a, b = "app." + field, "browser." + field
            if row["field_status"][a] == row["field_status"][b] == "observed":
                av, bv = row["features"][a], row["features"][b]
                c["both_observed"] += 1
                if legacy.canonical_json(av) != legacy.canonical_json(bv):
                    c["literal_differences"] += 1
                    c["numeric_representation_only" if semantic_equal(av, bv) else "value_differences"] += 1
        numeric_diagnostics[field] = dict(c)
    summary = {
        "dataset_manifest_version": "mtc-paired244-snapshot-v2", "created_at_utc": now(),
        "dataset_role": "development_qc_only", "label_status": "unlabeled", "research_principle": PRINCIPLE,
        "freeze_directory": str(freeze), "source_cutoff_utc": manifest["cutoff_utc"],
        "config_version": config["config_version"], "source_rows": {k: len(v) for k, v in tables.items()},
        "source_file_roles": {name: "retained_reference_only" if name in {
            "expanded_merged_sessions.json", "browser_pair_events.jsonl", "browser_provisional_payloads.jsonl"
        } else "qc_or_join_input" for name in manifest["source_files"]},
        "statistical_basis": "observed_mtc_inventory", "procurement_reconciliation": "NOT_REQUIRED_USER_WAIVED",
        "backend_completed_pairs": len(pair_rows), "backend_paired_model_os": p0["paired_manufacturer_model_os"],
        "qc_paired_244": len(paired), "qc_paired_model_os": len(paired_profiles),
        "view_counts": {k: len(v) for k, v in views.items()},
        "app_archive_destination_counts": dict(Counter(r["destination"] for r in selection)),
        "unique_app_sessions": len(raw_by_session), "multi_observation_sessions": sum(len(v) > 1 for v in raw_by_session.values()),
        "paired_release_counts": dict(Counter(str(r["app"]["collector_version_code"]) for r in paired)),
        "pair_destination_counts": dict(Counter(r["destination"] for r in pair_audit)),
        "duplicate_pair_receipt_aliases_resolved": sum(r["duplicate_receipt_alias"] and not r["reasons"] for r in pair_audit),
        "receipt_accounting": dict(Counter(r["status"] for r in receipt_audit)),
        "all_app_normalized_observations": sum(bool(r["normalization"]["null_slots_added"]) for r in all_app),
        "paired_normalized_observations": sum(bool(r["normalization"]["null_slots_added"]) for r in paired),
        "auxiliary_issue_count": len(auxiliary_issues), "raw_modified": False, "values_imputed": False,
        "p1_status": "COMPLETE" if not auxiliary_issues else "NEEDS_REVIEW",
        "p2_admission_and_splits": "NOT_EVALUATED", "rules_mined_or_run": False,
        "legacy_performance_target": False, "v1_runtime_compatibility": "NOT_COMPATIBLE_USE_EXPLICIT_P4_ADAPTER",
        "comparison_claim": "Cross-container value observations only; no attack labels or risk scores.",
        "comparison_cohort": "all_validated_completed_pairs_including_partial",
        "comparison_record_denominator": len(comparisons),
        "pair_comparison_counts": comparison_counts, "numeric_format_diagnostics": numeric_diagnostics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=output.name + ".building-", dir=output.parent))
    try:
        for view, records in views.items():
            legacy.write_jsonl(stage / (view + ".jsonl"), records)
        for filename, records in {"selection_audit": selection, "pair_qc_audit": pair_audit,
                                  "receipt_audit": receipt_audit, "auxiliary_issues": auxiliary_issues,
                                  "browser_pair_comparisons": comparisons}.items():
            legacy.write_jsonl(stage / (filename + ".jsonl"), records)
        legacy.write_json(stage / "manifest.json", summary)
        legacy.write_json(stage / "feature_catalog.json", {"feature_catalog_version": "mtc-paired244-feature-catalog-v2",
                          "paired_feature_order": paired_fields, "paired_feature_types": paired_types,
                          "browser_feature_count": 67, "known_sentinels": policy["ambiguous_sentinels"],
                          "sentinel_review_scope": "Only code-confirmed device_memory/hardware_concurrency zero fallbacks excluded; other sentinel semantics require field-specific review before rule mining."})
        legacy.write_json(stage / "field_quality.json", {
            "denominator_policy": "App cohort counts raw observations, including revisions; paired cohort counts QC admitted pairs. Neither is a physical-device denominator.",
            "app_observations": field_quality_report(all_app, paired_fields[:177], paired_types),
            "paired_244": field_quality_report(paired, paired_fields, paired_types)})
        legacy.write_json(stage / "config.json", config)
        legacy.write_json(stage / "comparison_policy.json", policy)
        shutil.copyfile(Path(__file__), stage / "builder.py")
        shutil.copyfile(REPO / "hybridguard_agent/evidence/browser_pair_v2.py", stage / "comparison.py")
        shutil.copyfile(Path(legacy.__file__), stage / "legacy_snapshot_helpers.py")
        shutil.copyfile(REPO / "hybridguard_agent/evidence/browser_pair.py", stage / "legacy_comparison_helpers.py")
        stage.rename(output)
    except Exception:
        shutil.rmtree(stage)
        raise
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = build(args.config.resolve(), args.output_dir.resolve())
    print(json.dumps({k: v for k, v in summary.items() if k not in {"pair_comparison_counts", "numeric_format_diagnostics"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
