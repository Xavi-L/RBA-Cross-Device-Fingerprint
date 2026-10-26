"""Offline extraction of the frozen 891 historical MTC representatives.

Only original collector observations are returned. The historical split is
provenance metadata; no label, detector decision, split, or feature is fitted.
Private identifiers are intentionally retained here for the release builder's
single pseudonymization boundary. Never serialize these records as public data.
"""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

SNAPSHOT = "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final"
PLAN = "hybridguard_agent/artifacts/mtc_p2_frozen_20260922"
RAW = "backend_server/collection_backups/mtc_final_20260922/sources"
SOURCE_ID = "mtc_historical_891"


def _jsonl(path: Path) -> list[tuple[int, dict]]:
    with path.open(encoding="utf-8") as handle:
        return [(line, json.loads(text)) for line, text in enumerate(handle, 1)
                if text.strip()]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("MTC adapter: " + message)


def extract(repo: Path) -> dict:
    repo = Path(repo)
    inputs: set[str] = set()

    def rows(relative: str) -> list[tuple[int, dict]]:
        inputs.add(relative)
        return _jsonl(repo / relative)

    def document(relative: str):
        inputs.add(relative)
        return json.loads((repo / relative).read_text(encoding="utf-8"))

    registry_path = PLAN + "/sample_registry.jsonl"
    registry = rows(registry_path)
    manifest = document(SNAPSHOT + "/manifest.json")
    summary = document(PLAN + "/summary.json")
    protocol = document("hybridguard_agent/config/mtc_experiment_protocol.v1.json")
    document("hybridguard_agent/config/mtc_paired244_sources.v2.json")
    source_config = document("hybridguard_agent/config/dataset_sources.json")
    _require(manifest.get("p1_status") == "COMPLETE", "P1 is not complete")
    _require(summary.get("p2_status") == "COMPLETE", "P2 is not complete")
    _require(protocol["primary_cohort"]["representative_unit"] ==
             "exact_manufacturer_model_android_release", "representative policy drift")
    _require(protocol["primary_cohort"]["representative_selection"] ==
             "smallest_app_raw_source_line_then_sample_id", "selection policy drift")

    views = {}
    for view, expected in manifest["view_counts"].items():
        values = rows(f"{SNAPSHOT}/{view}.jsonl")
        _require(len(values) == expected, "snapshot view count drift: " + view)
        views[view] = dict(values)
    selected = [(line, row) for line, row in registry
                if row.get("analysis_role") == "primary_representative"
                and row.get("source_view") == "paired_244"]
    split_counts = Counter(row["split"] for _, row in selected)
    _require(len(selected) == 891 and split_counts == {
        "discovery": 630, "development": 144, "reserved_validation": 117},
        "historical representative counts drift")
    _require(len({row["sample_id"] for _, row in selected}) == 891,
             "repeated selected sample identity")
    app_raw = dict(rows(RAW + "/raw_expanded_payloads.jsonl"))
    browser_raw = dict(rows(RAW + "/raw_browser_payloads.jsonl"))
    records = []
    groups_by_split: dict[str, set] = {}
    profiles = set()
    for registry_line, meta in selected:
        row = views["paired_244"].get(meta["source_line"])
        _require(row is not None, "missing selected snapshot row")
        _require(row["sample_id"] == meta["sample_id"], "snapshot sample binding drift")
        _require(row["record_schema_version"] == "hybridguard-mtc-observation-v2"
                 and row["feature_count"] == 244 and row["qc"]["status"] == "passed"
                 and row["pair"]["pair_status"] == "completed", "selected row contract drift")
        _require(row["profile"] == meta["profile"], "profile binding drift")
        refs = row["source_refs"]
        archived_app = app_raw[refs["app_raw_line"]]
        archived_browser = browser_raw[refs["browser_raw_line"]]
        # These existing identity strings are join keys, not new integrity scans.
        _require(archived_app["session_id"] == meta["app_session_id"] == row["app"]["session_id"],
                 "App session binding drift")
        _require(archived_app["payload_sha256"] == meta["app_payload_sha256"] == row["app"]["payload_sha256"],
                 "App archive identity drift")
        _require(archived_browser["browser_payload_sha256"] == meta["browser_payload_sha256"] == row["browser"]["payload_sha256"],
                 "Browser archive identity drift")
        _require(archived_browser["browser_session_id"] == row["browser"]["session_id"]
                 and archived_browser["app_session_id"] == archived_app["session_id"]
                 and archived_browser["pair_id"] == row["pair"]["browser_pair_id"],
                 "paired archive binding drift")
        payload = archived_app["canonical_received_payload"]
        browser_payload = archived_browser["canonical_received_payload"]
        _require(payload["session_id"] == archived_app["session_id"], "App envelope drift")
        _require(meta.get("label_status") == "unknown" and meta.get("manipulation_present") is None,
                 "unexpected MTC label facts require review")
        profile = tuple(row["profile"][k] for k in ("manufacturer", "model", "android_release"))
        _require(profile not in profiles, "repeated historical model/OS representative")
        profiles.add(profile)
        groups_by_split.setdefault(meta["split"], set()).add(meta["group_id"])
        records.append({
            "source_id": SOURCE_ID,
            "record_key": archived_app["session_id"],
            "app": payload,
            "browser": browser_payload["web_data"],
            "browser_status": browser_payload.get("collection_status", {}),
            "metadata": {
                "cohort": "historical_mtc_891_representatives",
                "environment": "cloud_real_device_reference_context",
                "collection_context": "normal_no_target_intervention_reported",
                "schema_version": payload.get("schema_version"),
                "browser_schema_version": browser_payload.get("schema_version"),
                "historical_split": meta["split"],
                "group_basis": "historical_transitive_model_install_session_group",
                "representative_basis": "exact_manufacturer_model_android_release",
                "physical_device_identity": "not_verified",
                "historical_holdout_pristine": False,
            },
            "annotation": {
                "label": "unlabeled",
                "label_verification": "unverified",
                "tool_execution_status": "unknown",
                "target_effect_status": "unknown",
                "detector_outcome": "unknown",
            },
            "group_key": meta["group_id"],
            "group_basis": "historical_transitive_model_install_session_group",
            "provenance": [
                {"path": registry_path, "line": registry_line},
                {"path": SNAPSHOT + "/paired_244.jsonl", "line": meta["source_line"]},
                {"path": RAW + "/raw_expanded_payloads.jsonl", "line": refs["app_raw_line"]},
                {"path": RAW + "/raw_browser_payloads.jsonl", "line": refs["browser_raw_line"]},
            ],
        })
    split_names = sorted(groups_by_split)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1:]:
            _require(not groups_by_split[left] & groups_by_split[right], "cross-split group overlap")

    sources = [{
        "source_id": SOURCE_ID, "path": SNAPSHOT + "/paired_244.jsonl",
        "status": "selected", "available": True,
        "raw_count": len(views["paired_244"]), "selected_count": 891,
        "excluded_count": len(views["paired_244"]) - 891,
        "reason": "Only the frozen P2 primary model/OS representatives are selected; repeat observations are excluded.",
        "schema_version": "expanded-v2.2-status plus browser-web-v1-status",
        "label_basis": "unlabeled; collection context is not independent benign ground truth",
        "group_basis": "historical_transitive_model_install_session_group",
        "historical_split_counts": dict(split_counts),
        "historical_group_counts": {k: len(v) for k, v in groups_by_split.items()},
        "authorization_status": "PENDING_CONFIRMATION",
    }]
    for view, values in views.items():
        if view == "paired_244":
            continue
        sources.append({
            "source_id": "mtc_snapshot_" + view,
            "path": f"{SNAPSHOT}/{view}.jsonl", "status": "excluded", "available": True,
            "raw_count": len(values), "selected_count": 0, "excluded_count": len(values),
            "reason": "Not a historical P2 primary paired representative; retained upstream for QC or missingness analysis.",
            "label_basis": "unlabeled", "authorization_status": "PENDING_CONFIRMATION",
        })
    # Legacy paths are audited independently. A generic historical config path
    # can change contents; it must not be relabeled as the frozen MTC cohort.
    for source in source_config["sources"]:
        path = source["path"]
        available = (repo / path).is_file()
        count = None
        if available:
            inputs.add(path)
            if source["input_kind"] == "evidence_csv":
                with (repo / path).open(encoding="utf-8", newline="") as handle:
                    count = sum(1 for _ in csv.DictReader(handle))
            else:
                count = len(_jsonl(repo / path))
        sources.append({
            "source_id": source["source_id"], "path": path,
            "status": "excluded" if available else "unavailable", "available": available,
            "raw_count": count, "selected_count": 0, "excluded_count": count,
            "reason": source["model_eligibility"] + "; outside the frozen MTC paper cohort",
            "label_basis": source.get("notes", "No per-sample independently verified manipulation label"),
            "optional": bool(source.get("optional")),
        })
    partial_path = "hybridguard-browser-fingerprint-research/execution_log/evidence/manifest_dataset_v1_partial.jsonl"
    partial_available = (repo / partial_path).is_file()
    partial_count = len(rows(partial_path)) if partial_available else None
    sources.append({
        "source_id": "attack_week7_manifest_partial_20260713", "path": partial_path,
        "status": "excluded" if partial_available else "unavailable", "available": partial_available,
        "raw_count": partial_count, "selected_count": 0, "excluded_count": partial_count,
        "reason": "Failure-analysis-only legacy rows without collection_manifest; not model-ready or part of historical MTC.",
        "label_basis": "unknown", "optional": True,
    })
    inputs.add("dataset_release/hybridguard_v1/scripts/adapter_mtc.py")
    return {"sources": sources, "records": records, "inputs": sorted(inputs), "issues": [
        "Historical reserved validation follows global QC and difference diagnostics; it is not a never-inspected external test.",
        "MTC collection context does not provide verified benign labels or proof of independent physical devices.",
        "Written MTC data redistribution scope and institutional review status remain pending confirmation.",
    ]}
