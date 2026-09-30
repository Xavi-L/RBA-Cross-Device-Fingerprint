#!/usr/bin/env python3
"""Mixed-mode execution registration; default invocation is read-only preflight.

Registration never authorizes a fit. Actual execution additionally requires an
independent, matching execution contract that explicitly admits the proposed
labels and authorizes training. This preparation round creates neither grant.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.rule_semantics_runtime_matrix import W0_ATOM_IDS

STUDY = "rule-semantics-mixed-retraining-v1"
PHASE = "RSR_MIXED_RETRAINING"
ENGINE_VERSION = "rsr-mixed-retraining-adapter-v1"
GROUPS = ("BASE", "LANG_ADD_WD_REPLACE")
MODES = ("legacy_projection_v1", "raw_observation_v1")
LANG, WD = "RSR-LANG-FIRST-v1", "RSR-WEBDRIVER-STATE-v1"
FROZEN = Path("hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1")
PRIOR = Path("deliverables/rule_semantics_combination")
OLD_CANDIDATES = Path("deliverables/rule_semantics_candidate_evaluation/CANDIDATE_RESULTS.jsonl")
LIMITS = {"max_new_fits": 16, "max_prediction_calls": 360, "max_worker_seconds": 90,
          "max_stage_seconds": 1440, "global_max_fits": 200, "global_max_seconds": 21600}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def keyed(rows, key):
    result = {}
    for row in rows:
        require(row[key] not in result, "DUPLICATE_" + key)
        result[row[key]] = row
    return result


def budget_snapshot(root=ROOT):
    previous = read(root / PRIOR / "EXECUTION.json")
    require(previous.get("execution_complete") is True and previous.get("stop_reason") is None,
            "PRIOR_BUDGET_NOT_SETTLED")
    require(previous["cumulative_fit_jobs"] == 177 and previous["remaining_research_fits"] == 23,
            "EXPECTED_SHARED_177_OF_200_BUDGET_CHANGED_REVIEW_REQUIRED")
    seconds = previous["cumulative_charged_seconds"]
    require(type(seconds) in (int, float) and math.isfinite(seconds)
            and seconds >= 0 and seconds + LIMITS["max_stage_seconds"] <= LIMITS["global_max_seconds"],
            "SHARED_TIME_BUDGET_INSUFFICIENT")
    return {**LIMITS, "prior_ledger_ref": str(PRIOR / "EXECUTION.json"), "base_fit_jobs": 177,
            "base_charged_seconds": seconds, "registered_fit_reservation": 0}


def coverage_review(prepared):
    path = Path(prepared).parent / "COVERAGE_FEASIBILITY.json"
    if not path.is_file():
        return {"evidence_ref": str(path), "blocking_reasons": ["COVERAGE_FEASIBILITY_REVIEW_PENDING"]}
    review = read(path)
    status = review.get("status")
    reasons = (["BLOCKED_FOR_STATED_WEBDRIVER_LEARNING_GOAL"]
               if status == "PROVED_INFEASIBLE_FOR_PRIMARY_OR_CONTAINING_NEW_WEBDRIVER"
               else [status] if type(status) is str and status.startswith("BLOCKED") else [])
    if not reasons:
        # This runner registers the fixed H162+N18 plan. A different conclusion
        # needs a new data/protocol registration, not a flag on this contract.
        reasons = ["FIXED_180_WEBDRIVER_GOAL_REQUIRES_NEW_PROTOCOL_REVIEW"]
    return {"evidence_ref": str(path), "review_status": status, "blocking_reasons": reasons}


def validate_execution_layout(contract):
    ids = set(contract["sample_ids"])
    folds = keyed(contract["folds"], "fold_id")
    jobs = keyed(contract["jobs"], "job_id")
    require(len(ids) == len(contract["sample_ids"]) == 180 and len(folds) == 4 and len(jobs) == 16,
            "EXACT_REGISTERED_180_FOUR_FOLD_SIXTEEN_JOB_LAYOUT_REQUIRED")
    positions = Counter()
    for f in folds.values():
        train, test = f["train_ids"], f["outer_test_ids"]
        require(len(train) == len(set(train)) and len(test) == len(set(test))
                and not set(train) & set(test) and set(train) | set(test) == ids,
                "REGISTERED_PARTITION_MISMATCH")
        positions.update(test)
    require(positions == Counter({i: 1 for i in ids}), "REGISTERED_OOF_MEMBERSHIP_MISMATCH")
    require({(j["group_id"], j["fold_id"], j["stage"]) for j in jobs.values()}
            == {(g, f, s) for g in GROUPS for f in folds for s in ("SPARSE", "RETENTION")},
            "REGISTERED_JOB_SET_MISMATCH")
    order = list(jobs)
    for j in jobs.values():
        f = folds[j["fold_id"]]
        init = j["group_id"] + "__" + j["fold_id"] + "__SPARSE" if j["stage"] == "RETENTION" else None
        require(j["job_id"] == j["group_id"] + "__" + j["fold_id"] + "__" + j["stage"]
                and j["train_ids"] == f["train_ids"] and j["outer_test_ids"] == f["outer_test_ids"]
                and j.get("initializer") == init
                and j["max_prediction_calls"] == (len(f["outer_test_ids"]) if init else 0)
                and (init is None or order.index(init) < order.index(j["job_id"])),
                "REGISTERED_JOB_SCOPE_OR_INITIALIZER_MISMATCH")
    require(sum(j["max_prediction_calls"] for j in jobs.values()) == 360, "REGISTERED_PREDICTION_BUDGET_MISMATCH")


def validate_plan(index, metadata, folds, jobs, historical_ids):
    """Pure member/group/job validation; proposed labels stay proposed here."""
    by_id, by_fold = keyed(index, "opaque_id"), keyed(folds, "fold_id")
    ids = set(by_id)
    require(len(ids) == 180 and set(metadata) == ids and len(by_fold) == 4, "EXACT_180_MEMBERS_FOUR_FOLDS_REQUIRED")
    modes = Counter(r["observation_mode"] for r in index)
    require(modes == {MODES[0]: 162, MODES[1]: 18}, "EXACT_MIXED_MODE_MEMBERSHIP_REQUIRED")
    require({i for i, r in by_id.items() if r["observation_mode"] == MODES[0]} == set(historical_ids)
            and len(historical_ids) == len(set(historical_ids)) == 162, "HISTORICAL_162_IDENTITY_MISMATCH")
    trips = defaultdict(dict)
    environments = set()
    for oid, row in by_id.items():
        m = metadata[oid]
        require(m.get("opaque_id") == oid and m.get("phase") in ("clean_pre", "attack", "clean_post"), "INVALID_MEMBER_METADATA")
        if row["observation_mode"] == MODES[1]:
            require(m.get("proposed_supervised_member") is True and m.get("fit_permission") == "DENIED_PREPARATION_ONLY",
                    "PREPARATION_LABEL_PERMISSION_CHANGED")
            label = m.get("proposed_supervised_label")
        else:
            label = m.get("supervised_label")
        require(type(label) is int and label == int(m["phase"] == "attack"), "PHASE_LABEL_MISMATCH")
        require(all(type(m.get(k)) is str and m[k] for k in ("environment_group_id", "config_id", "bundle_id", "triplet_id")),
                "GROUP_CONFIG_TRIPLET_MISSING")
        environments.add(m["environment_group_id"])
        t = trips[m["bundle_id"], m["triplet_id"]]
        require(m["phase"] not in t, "DUPLICATE_TRIPLET_PHASE")
        t[m["phase"]] = m
    require(len(environments) == 4 and len(trips) == 60, "ENVIRONMENT_OR_TRIPLET_COUNT_MISMATCH")
    for t in trips.values():
        require(set(t) == {"clean_pre", "attack", "clean_post"}
                and len({(m["environment_group_id"], m["config_id"]) for m in t.values()}) == 1,
                "INCOMPLETE_OR_SPLIT_TRIPLET")
    heldout = Counter()
    for fold in folds:
        train, test = fold["train_ids"], fold["outer_test_ids"]
        require(len(train) == len(set(train)) and len(test) == len(set(test)) and not set(train) & set(test)
                and set(train) | set(test) == ids, "PARTITION_MEMBERSHIP_MISMATCH")
        require({metadata[i]["environment_group_id"] for i in test} == {fold["heldout_environment"]}
                and all(metadata[i]["environment_group_id"] != fold["heldout_environment"] for i in train),
                "ENVIRONMENT_LEAKAGE")
        heldout.update(test)
    require(heldout == Counter({i: 1 for i in ids}), "ONE_OOF_POSITION_PER_MEMBER_REQUIRED")
    by_job = keyed(jobs, "job_id")
    expected = {(g, f, s) for g in GROUPS for f in by_fold for s in ("SPARSE", "RETENTION")}
    require(len(by_job) == 16 and {(j["group_id"], j["fold_id"], j["stage"]) for j in jobs} == expected,
            "EXACT_SIXTEEN_JOBS_REQUIRED")
    for j in jobs:
        f = by_fold[j["fold_id"]]
        require(j["train_ids"] == f["train_ids"] and j["outer_test_ids"] == f["outer_test_ids"], "JOB_FOLD_MEMBER_MISMATCH")
        require(j["job_id"] == j["group_id"] + "__" + j["fold_id"] + "__" + j["stage"], "JOB_IDENTITY_MISMATCH")
        init = j["group_id"] + "__" + j["fold_id"] + "__SPARSE" if j["stage"] == "RETENTION" else None
        require(j.get("initializer") == init and j["max_prediction_calls"] == (len(f["outer_test_ids"]) if init else 0),
                "INITIALIZER_OR_PREDICTION_SCOPE_MISMATCH")
    require(sum(j["max_prediction_calls"] for j in jobs) == 360, "EXACT_360_PREDICTIONS_REQUIRED")
    return {"members": 180, "historical_members": 162, "new_members": 18, "folds": 4,
            "triplets": 60, "jobs": 16, "prospective_predictions": 360}


def _candidate_index(rows):
    result = {}
    for row in rows:
        key = row["opaque_id"], row["candidate_id"], row["mode"]
        require(key not in result, "DUPLICATE_CANDIDATE_MODE_RECORD")
        result[key] = row
    return result


def validate_input_row(row):
    require(set(row["features"]) == W0_ATOM_IDS, "EXACT_W0_INPUT_KEYS_REQUIRED")
    for name, cell in row["features"].items():
        require(type(cell) is dict and set(cell) == {"value", "available", "evaluation_status", "reason"}
                and type(cell["available"]) is bool and type(cell["reason"]) is str and cell["reason"],
                "INVALID_BASE_CELL_SCHEMA")
        if cell["available"]:
            value = cell["value"]
            valid = (type(value) in (int, float) and math.isfinite(value)
                     if name.startswith("UNFITTED_CONTROL:") else type(value) is bool)
            require(cell["evaluation_status"] == "OK" and valid, "INVALID_AVAILABLE_BASE_CELL")
        else:
            require(cell["value"] is None and cell["evaluation_status"] in ("OK", "FAILED", "NOT_REQUESTED"),
                    "INVALID_UNAVAILABLE_BASE_CELL")
    require(set(row["candidate_cells"]) == {LANG, WD}, "EXACT_NEW_CANDIDATE_KEYS_REQUIRED")
    for name, cell in row["candidate_cells"].items():
        require(cell.get("candidate_id") == name and cell.get("version") == "1.0.0"
                and type(cell.get("available")) is bool and type(cell.get("reason")) is str,
                "INVALID_SEMANTIC_CELL_IDENTITY")
        require((cell["evaluation_status"] == "OK" and
                 ((cell["available"] is True and type(cell.get("value")) is bool)
                  or (cell["available"] is False and cell.get("value") is None)))
                or (cell["evaluation_status"] == "FAILED" and cell["available"] is False and cell.get("value") is None),
                "INVALID_SEMANTIC_CELL_STATE")
    require(row["candidate_cells"][WD].get("diagnostics", {}).get("mode") == row["observation_mode"],
            "WEBDRIVER_CELL_MODE_MISMATCH")


def prepared_materials(prepared, root=ROOT):
    """Registration-only materialization, not used inside a training worker."""
    prepared = Path(prepared)
    index = lines(prepared / "MIXED_INPUT_INDEX.jsonl")
    summary = read(prepared / "SUMMARY.json")
    require(summary["fit_calls"] == summary["model_prediction_calls"] == 0, "PREPARATION_HAS_EXECUTION")
    folds = read(prepared / "SPLIT_PLAN.json")["folds"]
    jobs = read(prepared / "JOB_PLAN.json")["jobs"]
    admissions = keyed(lines(prepared / "ADMISSION_MANIFEST.jsonl"), "opaque_id")
    new_base = keyed(lines(prepared / "BASE_INPUTS.jsonl"), "opaque_id")
    old_ids = read(root / PRIOR / "CONTRACT.json")["sample_ids"]
    old_cells = _candidate_index(lines(root / OLD_CANDIDATES))
    new_cells = _candidate_index(lines(prepared / "CANDIDATE_RESULTS.jsonl"))
    metadata, inputs = {}, {}
    for entry in index:
        oid, mode = entry["opaque_id"], entry["observation_mode"]
        if mode == MODES[0]:
            require(oid in old_ids, "UNREGISTERED_HISTORICAL_MEMBER")
            feature_ref, meta_ref = FROZEN / "data/current" / (oid + ".json"), FROZEN / "data/evaluation" / (oid + ".json")
            require(entry["features_ref"] == str(feature_ref) and entry["metadata_ref"] == str(meta_ref)
                    and entry["candidate_ref"] == str(OLD_CANDIDATES) + "#opaque_id=" + oid, "HISTORICAL_REFERENCE_MISMATCH")
            source = read(root / feature_ref)
            require(source["opaque_id"] == oid, "FEATURE_IDENTITY_MISMATCH")
            features, metadata[oid], cells = source["features"], read(root / meta_ref), old_cells
        elif mode == MODES[1]:
            require(entry["features_ref"] == "BASE_INPUTS.jsonl#opaque_id=" + oid
                    and entry["metadata_ref"] == "ADMISSION_MANIFEST.jsonl#opaque_id=" + oid
                    and entry["candidate_ref"] == "CANDIDATE_RESULTS.jsonl#opaque_id=" + oid,
                    "NEW_REFERENCE_MISMATCH")
            features, metadata[oid], cells = new_base[oid]["features"], admissions[oid], new_cells
        else:
            raise ValueError("UNREGISTERED_OBSERVATION_MODE")
        require(W0_ATOM_IDS.issubset(features), "W0_BASE_CELL_MISSING")
        base = {name: deepcopy(features[name]) for name in sorted(W0_ATOM_IDS)}
        records = {LANG: cells[oid, LANG, "default"], WD: cells[oid, WD, mode]}
        candidate_cells = {name: deepcopy(record["semantic_cell"]) for name, record in records.items()}
        inputs[oid] = {"opaque_id": oid, "observation_mode": mode, "features": base, "candidate_cells": candidate_cells,
                      "source_index_entry": deepcopy(entry),
                      "candidate_provenance": {name: {k: deepcopy(record[k]) for k in ("mode", "source_binding", "source_refs") if k in record}
                                               for name, record in records.items()}}
        validate_input_row(inputs[oid])
    report = validate_plan(index, metadata, folds, jobs, old_ids)
    return {"index": index, "metadata": metadata, "inputs": inputs, "folds": folds, "jobs": jobs,
            "definitions": read(root / FROZEN / "data/definitions.json"), "report": report}


def preflight(prepared=HERE / "prepared", root=ROOT):
    materials = prepared_materials(prepared, root)
    feasibility = coverage_review(prepared)
    return {"status": "BLOCKED_FOR_STATED_WEBDRIVER_LEARNING_GOAL", **materials["report"],
            "shared_budget": budget_snapshot(root), "fit_calls": 0, "model_prediction_calls": 0,
            "registration_performed_by_this_command": False, "training_authorized": False, "input_structure_status": "PASS",
            "coverage_feasibility": feasibility, "blocking_reasons": feasibility["blocking_reasons"]}


def register(directory, prepared=HERE / "prepared", root=ROOT):
    materials = prepared_materials(prepared, root)
    budget = budget_snapshot(root)
    feasibility = coverage_review(prepared)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    for part in ("inputs", "evaluation"):
        (directory / part).mkdir()
    for oid, row in materials["inputs"].items():
        write(directory / "inputs" / (oid + ".json"), row)
        write(directory / "evaluation" / (oid + ".json"), materials["metadata"][oid])
    write(directory / "DEFINITIONS.json", materials["definitions"])
    registered_at = stamp()
    contract = {"schema_version": "rsr-mixed-execution-registration-v1", "study_version": STUDY,
                "phase": PHASE, "engine_version": ENGINE_VERSION,
                "experiment_id": "RSR_MIXED_180_LOEO_4_V1", "registered_at": registered_at,
                "status": "REGISTERED_NOT_AUTHORIZED", "training_authorized": False,
                "admission_authorized": False, "sample_ids": sorted(materials["inputs"]),
                "source_modes": {i: r["observation_mode"] for i, r in materials["inputs"].items()},
                "source_prepared_directory": str(Path(prepared).resolve()),
                "coverage_feasibility": feasibility, "blocking_reasons": feasibility["blocking_reasons"],
                "jobs": materials["jobs"], "folds": materials["folds"], "budget": budget,
                "definitions_ref": "DEFINITIONS.json", "label_policy": "EXPLICIT_TARGET_INTERVENTION_ADMISSION_ONLY",
                "evaluation_role": "EXPOSED_RETROSPECTIVE_MIXED_MODE_DEVELOPMENT",
                "failure_policy": "Preserve failed attempts and stop; no retries, refits, extra predictions or relaxed constraints."}
    write(directory / "CONTRACT.json", contract)
    write(directory / "EXECUTION_CONTRACT_TEMPLATE.json", {
        "schema_version": "rsr-mixed-execution-authorization-v1", "study_version": STUDY,
        "phase": PHASE, "experiment_id": contract["experiment_id"], "registered_at": registered_at,
        "training_authorized": False, "admission_authorized": False, "authorization_ref": None,
        "sample_ids": contract["sample_ids"], "jobs": contract["jobs"], "budget": budget,
    })
    write(directory / "REGISTRATION.json", {"status": "REGISTERED_NOT_AUTHORIZED", **materials["report"],
          "fit_calls": 0, "model_prediction_calls": 0, "reserved_fits": 0, "reserved_seconds": 0})
    return {"directory": str(directory.resolve()), "status": "REGISTERED_NOT_AUTHORIZED", **materials["report"]}


def execution_gate(contract, authorization, root=ROOT):
    require(contract.get("schema_version") == "rsr-mixed-execution-registration-v1"
            and contract.get("study_version") == STUDY and contract.get("phase") == PHASE
            and contract.get("engine_version") == ENGINE_VERSION, "MIXED_REGISTRATION_IDENTITY_REQUIRED")
    require(authorization.get("schema_version") == "rsr-mixed-execution-authorization-v1"
            and authorization.get("training_authorized") is True and authorization.get("admission_authorized") is True,
            "EXPLICIT_EXECUTION_AND_ADMISSION_AUTHORIZATION_REQUIRED")
    require(type(authorization.get("authorization_ref")) is str and bool(authorization["authorization_ref"].strip()),
            "AUTHORIZATION_REFERENCE_REQUIRED")
    for key in ("study_version", "phase", "experiment_id", "registered_at", "sample_ids", "jobs", "budget"):
        require(authorization.get(key) == contract.get(key), "EXECUTION_CONTRACT_MISMATCH:" + key)
    require(contract["budget"] == budget_snapshot(root), "SHARED_BUDGET_CHANGED_REVIEW_REQUIRED")
    require(not contract.get("blocking_reasons"), "REGISTERED_FEASIBILITY_BLOCKER_REQUIRES_NEW_PROTOCOL")
    require(not coverage_review(contract["source_prepared_directory"])["blocking_reasons"],
            "COVERAGE_FEASIBILITY_BLOCKER_REQUIRES_NEW_PROTOCOL")
    require(len(contract["sample_ids"]) == len(set(contract["sample_ids"])) == 180
            and Counter(contract["source_modes"].values()) == {MODES[0]: 162, MODES[1]: 18}
            and set(contract["source_modes"]) == set(contract["sample_ids"])
            and len(contract["jobs"]) == 16, "MIXED_180_EXECUTION_IDENTITY_REQUIRED")
    validate_execution_layout(contract)


def _admitted_metadata(row, authorization):
    require(authorization.get("training_authorized") is True and authorization.get("admission_authorized") is True,
            "PROPOSED_LABELS_NOT_AUTHORIZED")
    result = deepcopy(row)
    if row.get("observation_mode") == MODES[1]:
        require(row.get("proposed_supervised_member") is True and row.get("fit_permission") == "DENIED_PREPARATION_ONLY",
                "UNREGISTERED_NEW_LABEL")
        result["supervised_label"] = row["proposed_supervised_label"]
        result["fit_permission"] = "ONLY_WHEN_IN_REGISTERED_OUTER_TRAIN"
        result["label_authorization_ref"] = authorization["authorization_ref"]
    require(type(result.get("supervised_label")) is int and result["supervised_label"] == int(result["phase"] == "attack"),
            "ADMITTED_LABEL_MISMATCH")
    return result


def worker(directory, authorization_path, job_id, *, root=ROOT, engine=None):
    """One unique attempt. Even direct worker calls must pass the full gate."""
    directory = Path(directory)
    contract, authorization = read(directory / "CONTRACT.json"), read(authorization_path)
    execution_gate(contract, authorization, root)
    require((directory / "RUN_STARTED.json").is_file(), "DISPATCH_REGISTRATION_REQUIRED")
    jobs = keyed(contract["jobs"], "job_id")
    require(job_id in jobs, "UNREGISTERED_JOB")
    job = deepcopy(jobs[job_id])
    destination = directory / "trials" / job_id
    destination.mkdir(parents=True, exist_ok=False)
    if engine is None:
        from hybridguard_agent.research import rule_semantics_mixed_retraining as engine
    started, events, predictions = time.monotonic(), [], []
    fit_calls = prediction_calls = 0
    error, outcome = None, "FAILED"

    def event(name, **values):
        events.append({"event": name, "utc": stamp(), **values})

    def row(oid):
        value = read(directory / "inputs" / (oid + ".json"))
        require(value["opaque_id"] == oid and value["observation_mode"] == contract["source_modes"][oid], "REGISTERED_INPUT_MISMATCH")
        validate_input_row(value)
        return value

    binding = {"study_version": STUDY, "phase": PHASE, "group_id": job["group_id"],
               "method_id": "GREEDY_OR" if job["stage"] == "SPARSE" else "R_KEEP_V1",
               "fold_id": job["fold_id"], "split_id": "MIXED-LOEO-v1", "operating_point": "OP05",
               "model_unit_id": job_id, "evaluation_role": contract["evaluation_role"],
               "input_manifest_ref": str(directory / "CONTRACT.json")}
    try:
        selected = {i: row(i) for i in job["train_ids"]}
        raw = {i: r["features"] for i, r in selected.items()}
        modes = {i: r["observation_mode"] for i, r in selected.items()}
        metadata = {i: _admitted_metadata(read(directory / "evaluation" / (i + ".json")), authorization) for i in job["train_ids"]}
        candidates = None if job["group_id"] == "BASE" else {i: r["candidate_cells"] for i, r in selected.items()}
        event("TRAIN_ONLY_INPUTS_OPENED", train_ids=job["train_ids"], heldout_features_opened=0)
        kwargs = {"group": job["group_id"], "binding": binding, "source_modes": modes, "candidate_rows": candidates}
        if job["stage"] == "RETENTION":
            initial_dir = directory / "trials" / job["initializer"]
            require(read(initial_dir / "receipt.json")["outcome"] in ("FITTED", "EMPTY_MODEL"), "INITIALIZER_NOT_COMPLETED")
            job["initial_model_ref"] = str(initial_dir / "model.json")
            kwargs.update(initial_model=engine.load_model(initial_dir / "model.json"), initial_training=read(initial_dir / "training.json"))
        write(destination / "FIT_STARTED.json", {"job_id": job_id, "utc": stamp(), "fit_count": 1})
        fit_calls = 1
        method = engine.fit_sparse if job["stage"] == "SPARSE" else engine.fit_retention
        model, training = method(job, raw, metadata, read(directory / "DEFINITIONS.json"), **kwargs)
        write(destination / "training.json", training)
        engine.save_model(model, destination / "model.json")
        restored = engine.load_model(destination / "model.json")
        require(json.dumps(model.to_dict(), sort_keys=True) == json.dumps(restored.to_dict(), sort_keys=True), "MODEL_ROUNDTRIP_MISMATCH")
        require(restored.fit["train_ids"] == job["train_ids"] and restored.status in ("FITTED", "EMPTY_MODEL"), "MODEL_FIT_FAILED_OR_SCOPE_MISMATCH")
        event("MODEL_SAVED_RELOADED_FROZEN", model_id=restored.model_id)
        prediction_ids = job["outer_test_ids"] if job["stage"] == "RETENTION" else []
        with (destination / "PREDICTION_CALLS.jsonl").open("x") as calls, (destination / "predictions.jsonl").open("x") as output:
            for oid in prediction_ids:
                current = row(oid)
                calls.write(json.dumps({"opaque_id": oid, "event": "PREDICT_INVOKED"}) + "\n")
                calls.flush()
                prediction_calls += 1
                result = engine.predict_current(restored, oid, current["features"],
                    candidate_cells=None if job["group_id"] == "BASE" else current["candidate_cells"], source_mode=current["observation_mode"])
                output.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
                output.flush()
                predictions.append(result)
                require(result["decision"] != "FAILED", "MODEL_PREDICTION_FAILED:" + oid)
        event("PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN", count=len(predictions))
        if predictions:
            evaluation = []
            for prediction in predictions:
                oid = prediction["opaque_id"]
                m = _admitted_metadata(read(directory / "evaluation" / (oid + ".json")), authorization)
                evaluation.append({"opaque_id": oid, "decision": prediction["decision"],
                    **{k: m[k] for k in ("supervised_label", "phase", "environment_group_id", "config_id", "bundle_id", "triplet_id")},
                    "observation_mode": contract["source_modes"][oid]})
            write(destination / "evaluation_rows.json", evaluation)
            event("HELDOUT_METADATA_JOINED_AFTER_CLOSE", count=len(evaluation))
        outcome = restored.status
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        write(destination / "ERROR.json", error)
    event("JOB_CLOSED", outcome=outcome)
    write(destination / "access_log.json", events)
    receipt = {"job_id": job_id, "group_id": job["group_id"], "stage": job["stage"], "fold_id": job["fold_id"],
               "outcome": outcome, "actual_fit_invocations": fit_calls, "actual_prediction_calls": prediction_calls,
               "saved_prediction_positions": len(predictions), "charged_seconds": time.monotonic() - started,
               "expected_prediction_positions": job["max_prediction_calls"],
               "missing_prediction_positions": job["max_prediction_calls"] - len(predictions),
               "not_attempted_prediction_positions": job["max_prediction_calls"] - prediction_calls,
               "attempt": 1, "additional_retries": 0, "error": error}
    write(destination / "receipt.json", receipt)
    return receipt


def run(directory, authorization_path, root=ROOT):
    directory = Path(directory)
    contract, authorization = read(directory / "CONTRACT.json"), read(authorization_path)
    execution_gate(contract, authorization, root)
    require(not (directory / "RUN_STARTED.json").exists(), "EXISTING_EXECUTION_NO_RETRY")
    write(directory / "RUN_STARTED.json", {"utc": stamp(), "authorization_ref": authorization["authorization_ref"], "jobs": 16})
    receipts, stopped, started = [], None, time.monotonic()
    with (directory / "JOURNAL.jsonl").open("x") as journal:
        for job in contract["jobs"]:
            before = time.monotonic()
            if before - started >= LIMITS["max_stage_seconds"]:
                stopped = "STAGE_BUDGET_EXHAUSTED"
                break
            journal.write(json.dumps({"event": "JOB_RESERVED", "job_id": job["job_id"], "max_fit_charge": 1}) + "\n")
            journal.flush()
            try:
                process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", job["job_id"],
                    "--directory", str(directory.resolve()), "--execution-contract", str(Path(authorization_path).resolve())],
                    cwd=root, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True,
                    timeout=LIMITS["max_worker_seconds"])
                target = directory / "trials" / job["job_id"]
                receipt = read(target / "receipt.json")
                for name, value in (("stdout.txt", process.stdout), ("stderr.txt", process.stderr)):
                    if value:
                        with (target / name).open("x") as stream:
                            stream.write(value)
                require(process.returncode == 0 and receipt["outcome"] in ("FITTED", "EMPTY_MODEL"), "WORKER_FAILED")
            except Exception as exc:
                target = directory / "trials" / job["job_id"]
                target.mkdir(parents=True, exist_ok=True)
                receipt = read(target / "receipt.json") if (target / "receipt.json").exists() else {
                    "job_id": job["job_id"], "group_id": job["group_id"], "stage": job["stage"], "outcome": "FAILED",
                    "actual_fit_invocations": int((target / "FIT_STARTED.json").exists()),
                    "actual_prediction_calls": len(lines(target / "PREDICTION_CALLS.jsonl")) if (target / "PREDICTION_CALLS.jsonl").exists() else 0,
                    "saved_prediction_positions": len(lines(target / "predictions.jsonl")) if (target / "predictions.jsonl").exists() else 0,
                    "error": {"type": type(exc).__name__, "message": str(exc)}, "attempt": 1, "additional_retries": 0}
                if not (target / "receipt.json").exists():
                    write(target / "receipt.json", receipt)
                stopped = type(exc).__name__ + ":" + str(exc)
            receipt["worker_wall_seconds"] = time.monotonic() - before
            receipt["expected_prediction_positions"] = job["max_prediction_calls"]
            receipt["missing_prediction_positions"] = job["max_prediction_calls"] - receipt["saved_prediction_positions"]
            receipt["not_attempted_prediction_positions"] = job["max_prediction_calls"] - receipt["actual_prediction_calls"]
            receipts.append(receipt)
            journal.write(json.dumps({"event": "JOB_SETTLED", **receipt}) + "\n")
            journal.flush()
            if stopped:
                break
    fits = sum((directory / "trials" / j["job_id"] / "FIT_STARTED.json").exists() for j in contract["jobs"])
    predictions = sum(r["actual_prediction_calls"] for r in receipts)
    charged = sum(r["worker_wall_seconds"] for r in receipts)
    require(fits <= 16 and predictions <= 360, "EXECUTION_BUDGET_EXCEEDED")
    report = {"schema_version": "rsr-mixed-execution-v1", "status": "COMPLETE_PENDING_REVIEW" if len(receipts) == 16 and not stopped else "PARTIAL",
              "execution_complete": len(receipts) == 16 and not stopped, "jobs": receipts, "stop_reason": stopped,
              "actual_fit_invocations": fits, "actual_prediction_calls": predictions, "additional_retries": 0,
              "charged_seconds": charged, "cumulative_fit_jobs": 177 + fits, "remaining_research_fits": 23 - fits,
              "expected_prediction_positions": 360,
              "saved_prediction_positions": sum(r["saved_prediction_positions"] for r in receipts),
              "not_attempted_prediction_positions": 360 - predictions,
              "unexecuted_jobs": [{"job_id": j["job_id"], "status": "NOT_RUN_AFTER_STOP", "expected_prediction_positions": j["max_prediction_calls"]}
                                  for j in contract["jobs"] if j["job_id"] not in {r["job_id"] for r in receipts}],
              "cumulative_charged_seconds": contract["budget"]["base_charged_seconds"] + charged,
              "remaining_research_seconds": 21600 - contract["budget"]["base_charged_seconds"] - charged}
    write(directory / "EXECUTION.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--register", action="store_true")
    actions.add_argument("--run", action="store_true")
    actions.add_argument("--worker", metavar="JOB_ID")
    parser.add_argument("--prepared", type=Path, default=HERE / "prepared")
    parser.add_argument("--directory", type=Path, default=HERE / "registered")
    parser.add_argument("--execution-contract", type=Path)
    args = parser.parse_args()
    if args.run or args.worker:
        if args.execution_contract is None:
            parser.error("--execution-contract is required")
        result = worker(args.directory, args.execution_contract, args.worker) if args.worker else run(args.directory, args.execution_contract)
    elif args.register:
        result = register(args.directory, args.prepared)
    else:
        result = preflight(args.prepared)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
