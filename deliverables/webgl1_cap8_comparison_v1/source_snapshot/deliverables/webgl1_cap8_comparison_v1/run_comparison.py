#!/usr/bin/env python3
"""Run CAP8 on the admitted CAP7 cohort, with fresh models and the same folds."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
EXPERIMENT = "webgl1-cap8-comparison-v1"
STUDY = "rule-semantics-webgl1-cap8-v1"
PHASE = "RSR_WEBGL1_CAP8_COMPARISON"
EVALUATION_ROLE = "EXPOSED_INTERNAL_DEVELOPMENT_CAPACITY_FOLLOWUP"
SOURCE_EXPERIMENT = "webgl1-fresh-cap7-comparison-v1"
SOURCE_DIRECTORY = "deliverables/webgl1_fresh_comparison_v1/prepared"
SOURCE_PROTOCOL = "deliverables/webgl1_fresh_comparison_v1/PROTOCOL.json"
SOURCE_ROLE = "EXPOSED_INTERNAL_DEVELOPMENT_FRESH_COHORT_COMPARISON"
SOURCE_SCHEMA = "webgl1-fresh-input-preparation-v1"
SOURCE_READINESS = "WEBGL1_FRESH_INPUTS_READY"
AUTHORIZATION_SCHEMA = "webgl1-cap8-comparison-authorization-v1"
GROUPS = ("BASE49", "WEBGL50")
METHODS = {"SPARSE": "GREEDY_SEMANTIC_V2", "RETENTION": "R_KEEP_SWAP_V2"}
NEW_CANDIDATES = ("RSR-LANG-FIRST-v1", "RSR-WEBDRIVER-STATE-v1", "RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1")
SUCCESS = ("FITTED", "EMPTY_MODEL")
DECISIONS = ("MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE", "EMPTY_MODEL", "FAILED")


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    with Path(path).open("x") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def source_path(value):
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts, "REPOSITORY_RELATIVE_SOURCE_REQUIRED")
    result = (ROOT / path).resolve()
    require(result.is_relative_to(ROOT.resolve()), "SOURCE_OUTSIDE_REPOSITORY")
    return result


def configure_contract(preparation, *, source_directory, authorization_ref):
    """Build reviewable schedule and authorization records without I/O or fitting."""
    from hybridguard_agent.research.rule_semantics_webgl1_cap8 import PROFILE
    require(source_directory == SOURCE_DIRECTORY, "REGISTERED_CAP7_PREPARED_SOURCE_REQUIRED")
    require(preparation.get("schema_version") == SOURCE_SCHEMA
            and preparation.get("readiness") == SOURCE_READINESS
            and preparation.get("source_collection_protocol") == SOURCE_PROTOCOL
            and preparation.get("evaluation_role") == SOURCE_ROLE, "ADMITTED_CAP7_PREPARATION_REQUIRED")
    ids, folds = preparation["sample_ids"], preparation["folds"]
    jobs = []
    for fold in folds:
        for group in GROUPS:
            initializer = None
            for stage in METHODS:
                job_id = "CAP8__" + group + "__" + fold["fold_id"] + "__" + stage
                job = {**deepcopy(fold), "job_id": job_id, "group_id": group,
                       "stage": stage, "representation": "W0", "capacity_profile": PROFILE["profile_id"],
                       "max_prediction_calls": len(fold["outer_test_ids"]) if stage == "RETENTION" else 0}
                if initializer:
                    job["initializer"] = initializer
                else:
                    initializer = job_id
                jobs.append(job)
    contract = {"schema_version": "webgl1-cap8-comparison-contract-v1", "experiment_id": EXPERIMENT,
                "engine_study_version": STUDY, "engine_phase": PHASE,
                "readiness": "WEBGL1_CAP8_COMPARISON_READY", "source_directory": source_directory,
                "sample_ids": deepcopy(ids), "folds": deepcopy(folds), "jobs": jobs,
                "source_modes": deepcopy(preparation["source_modes"]),
                "evaluation_role": EVALUATION_ROLE, "source_evaluation_role": preparation["evaluation_role"],
                "source_reuse": source_reuse_registration(), "capacity_profile": deepcopy(PROFILE),
                "candidate_difference": "WEBGL50_ADDS_ONLY_REGISTERED_WEBGL1_SAVED_CELL",
                "selector_policy": "semantic-ties-and-guarded-swap-v2",
                "budget": {"planned_fits": 12, "round_fit_limit": 12,
                           "max_prediction_calls": 756, "max_worker_seconds": 90, "max_total_seconds": 1080},
                "fit_count_basis": "2 pools x 3 LOEO folds x 2 unchanged stages; not a historical cumulative limit"}
    grant = {"schema_version": AUTHORIZATION_SCHEMA, "experiment_id": EXPERIMENT,
             "engine_study_version": STUDY, "engine_phase": PHASE,
             "capacity_profile": PROFILE["profile_id"], "source_directory": SOURCE_DIRECTORY,
             "source_experiment_id": SOURCE_EXPERIMENT,
             "training_authorized": True, "admission_authorized": True,
             "sample_ids": deepcopy(ids), "job_ids": [j["job_id"] for j in jobs],
             "authorization_ref": authorization_ref}
    return contract, grant


def source_reuse_registration():
    """Fixed source identity; no source model, prediction or mutable observation."""
    return {"mode": "READ_ONLY_REUSE_ADMITTED_CAP7_PREPARED", "source_experiment_id": SOURCE_EXPERIMENT,
            "source_directory": SOURCE_DIRECTORY, "source_collection_protocol": SOURCE_PROTOCOL,
            "source_preparation_schema": SOURCE_SCHEMA, "source_readiness": SOURCE_READINESS,
            "source_evaluation_role": SOURCE_ROLE,
            "member_and_fold_policy": "EXACT_SAME_378_AND_THREE_LOEO_FOLDS",
            "new_collection": False, "candidate_recomputed": False,
            "source_models_reused": False, "source_predictions_reused": False}


def gate(directory):
    from hybridguard_agent.research.rule_semantics_webgl1_cap8 import PROFILE
    directory = Path(directory)
    contract = read(directory / "CONTRACT.json")
    grant = read(directory / "AUTHORIZATION.json")
    require(contract.get("schema_version") == "webgl1-cap8-comparison-contract-v1"
            and contract.get("experiment_id") == EXPERIMENT
            and contract.get("engine_study_version") == STUDY
            and contract.get("engine_phase") == PHASE, "WRONG_EXPERIMENT_IDENTITY")
    require(contract.get("readiness") == "WEBGL1_CAP8_COMPARISON_READY", "DATA_NOT_READY")
    require(grant.get("schema_version") == AUTHORIZATION_SCHEMA
            and grant.get("engine_study_version") == STUDY
            and grant.get("engine_phase") == PHASE
            and grant.get("capacity_profile") == PROFILE["profile_id"]
            and grant.get("source_directory") == SOURCE_DIRECTORY
            and grant.get("source_experiment_id") == SOURCE_EXPERIMENT,
            "CAP8_SPECIFIC_AUTHORIZATION_REQUIRED")
    require(grant.get("training_authorized") is True
            and grant.get("admission_authorized") is True, "EXPLICIT_USER_AUTHORIZATION_REQUIRED")
    ids, jobs, folds = contract["sample_ids"], contract["jobs"], contract["folds"]
    require(grant.get("experiment_id") == contract["experiment_id"]
            and grant.get("sample_ids") == ids
            and grant.get("job_ids") == [j["job_id"] for j in jobs]
            and grant.get("authorization_ref"), "AUTHORIZATION_MEMBERSHIP_MISMATCH")
    require(len(ids) == len(set(ids)) == 378 and len(jobs) == 12, "EXACT_REGISTERED_LAYOUT_REQUIRED")
    require(all(type(i) is str and Path(i).name == i and i not in ("", ".", "..") for i in ids),
            "OPAQUE_MEMBER_FILENAME_REQUIRED")
    require(len({j["job_id"] for j in jobs}) == 12 and len(folds) == 3
            and len({f["fold_id"] for f in folds}) == 3
            and len({f["heldout_environment"] for f in folds}) == 3, "UNIQUE_FOLDS_JOBS_REQUIRED")
    require(Counter((j["fold_id"], j["group_id"], j["stage"]) for j in jobs)
            == Counter((f["fold_id"], g, s) for f in folds for g in GROUPS for s in METHODS),
            "EXACT_GROUP_STAGE_FOLD_JOBS_REQUIRED")
    require(set(contract["source_modes"]) == set(ids)
            and set(contract["source_modes"].values()) == {"raw_observation_v1"}, "RAW_ONLY_MEMBERS_REQUIRED")
    source = source_path(contract["source_directory"])
    require(contract["source_directory"] == SOURCE_DIRECTORY
            and source == (ROOT / SOURCE_DIRECTORY).resolve(), "REGISTERED_CAP7_PREPARED_SOURCE_REQUIRED")
    prepared = read(source / "PREPARATION.json")
    admitted = read(source / "CONTRACT.json")
    require(prepared.get("schema_version") == SOURCE_SCHEMA
            and prepared.get("readiness") == SOURCE_READINESS, "CAP7_PREPARATION_NOT_READY")
    require(prepared.get("source_collection_protocol") == SOURCE_PROTOCOL,
            "SOURCE_COLLECTION_PROTOCOL_MISMATCH")
    require(admitted.get("experiment_id") == SOURCE_EXPERIMENT
            and admitted.get("readiness") == SOURCE_READINESS
            and admitted.get("protocol", {}).get("experiment_id") == SOURCE_EXPERIMENT,
            "SOURCE_EXPERIMENT_NOT_ADMITTED")
    require(contract.get("source_reuse") == source_reuse_registration()
            and contract.get("source_evaluation_role") == SOURCE_ROLE
            and prepared.get("evaluation_role") == admitted.get("evaluation_role") == SOURCE_ROLE
            and contract.get("evaluation_role") == EVALUATION_ROLE, "EXPLICIT_SOURCE_REUSE_ROLE_REQUIRED")
    for key in ("sample_ids", "folds", "source_modes"):
        require(contract[key] == prepared[key], "FRESH_PREPARATION_CHANGED:" + key)
        require(contract[key] == admitted[key], "SOURCE_ADMISSION_CHANGED:" + key)
    require(contract["capacity_profile"] == PROFILE, "EXACT_CAPACITY_PROFILE_REQUIRED")
    require(contract["candidate_difference"] == "WEBGL50_ADDS_ONLY_REGISTERED_WEBGL1_SAVED_CELL"
            and contract["selector_policy"] == "semantic-ties-and-guarded-swap-v2", "ONLY_WEBGL1_POOL_EXTENSION_ALLOWED")
    require(Counter(i for f in folds for i in f["outer_test_ids"]) == Counter(ids), "OUTER_COVERAGE_NOT_EXACT")
    preceding = {}
    for job in jobs:
        require(job.get("capacity_profile") == PROFILE["profile_id"] and job.get("representation") == "W0", "JOB_CAPACITY_MISMATCH")
        require(Path(job["job_id"]).name == job["job_id"]
                and job["job_id"] not in ("", ".", ".."), "INVALID_JOB_DIRECTORY")
        require(job["job_id"] == "CAP8__" + job["group_id"] + "__" + job["fold_id"] + "__" + job["stage"],
                "CAP8_JOB_IDENTITY_REQUIRED")
        train, test = job["train_ids"], job["outer_test_ids"]
        require(len(train) == len(set(train)) == 252 and len(test) == len(set(test)) == 126
                and not set(train) & set(test) and set(train) | set(test) == set(ids), "INVALID_OUTER_SPLIT")
        fold = next(f for f in folds if f["fold_id"] == job["fold_id"])
        require(all(job[k] == fold[k] for k in ("train_ids", "outer_test_ids", "heldout_environment")),
                "JOB_DIFFERS_FROM_REGISTERED_FOLD")
        require(job["max_prediction_calls"] == (126 if job["stage"] == "RETENTION" else 0), "PREDICTION_COUNT_MISMATCH")
        if job["stage"] == "RETENTION":
            initializer = preceding.get(job.get("initializer"))
            require(initializer is not None and initializer["stage"] == "SPARSE"
                    and initializer["fold_id"] == job["fold_id"]
                    and initializer["group_id"] == job["group_id"], "OWN_GROUP_FOLD_INITIALIZER_REQUIRED")
        preceding[job["job_id"]] = job
    require(contract["budget"] == {"planned_fits": 12, "round_fit_limit": 12, "max_prediction_calls": 756,
            "max_worker_seconds": 90, "max_total_seconds": 1080}, "REGISTERED_RUN_LIMIT_MISMATCH")
    return contract, grant


def validate_initializer_receipt(receipt, job, contract):
    require(receipt.get("outcome") in SUCCESS, "INITIALIZER_NOT_READY")
    require(receipt.get("experiment_id") == EXPERIMENT
            and receipt.get("capacity_profile") == contract["capacity_profile"]["profile_id"]
            and receipt.get("job_id") == job["initializer"]
            and receipt.get("group_id") == job["group_id"]
            and receipt.get("fold_id") == job["fold_id"] and receipt.get("stage") == "SPARSE",
            "OWN_CAP8_INITIALIZER_RECEIPT_REQUIRED")


class GuardedSource:
    """Only outer-train rows during fitting, then inputs, then labels."""

    def __init__(self, source, job, authorization_ref):
        self.source, self.job = Path(source), job
        self.authorization_ref = authorization_ref
        self.phase = "TRAIN"

    def input_row(self, oid):
        require(oid in self.job["train_ids"]
                or self.phase == "FROZEN" and oid in self.job["outer_test_ids"],
                "HELDOUT_INPUT_OPEN_BEFORE_FREEZE")
        row = read(self.source / "inputs" / f"{oid}.json")
        require(row["opaque_id"] == oid and row["observation_mode"] == "raw_observation_v1", "INPUT_ID_MODE_MISMATCH")
        return row

    def metadata(self, oid):
        require(oid in self.job["train_ids"]
                or self.phase == "PREDICTIONS_CLOSED" and oid in self.job["outer_test_ids"],
                "HELDOUT_LABEL_OPEN_BEFORE_PREDICTIONS_CLOSE")
        row = read(self.source / "evaluation" / f"{oid}.json")
        require(row["opaque_id"] == oid and row["proposed_supervised_member"] is True
                and row["fit_permission"] == "DENIED_PREPARATION_ONLY", "UNREGISTERED_LABEL")
        require(row["phase"] in ("clean_pre", "attack", "clean_post")
                and type(row["proposed_supervised_label"]) is int
                and row["proposed_supervised_label"] == int(row["phase"] == "attack"), "LABEL_PHASE_MISMATCH")
        return {**row, "supervised_label": row["proposed_supervised_label"],
                "fit_permission": "ONLY_WHEN_IN_REGISTERED_OUTER_TRAIN",
                "label_authorization_ref": self.authorization_ref}


def load_engine():
    from hybridguard_agent.research import rule_semantics_webgl1_cap8
    return rule_semantics_webgl1_cap8


def durable_counts(directory):
    """Call attempts are charged even if a timeout prevents the final receipt."""
    fits, predictions = 0, 0
    for trial in (Path(directory) / "trials").glob("*"):
        fits += (trial / "FIT_STARTED.json").exists()
        calls = trial / "PREDICTION_CALLS.jsonl"
        if calls.exists():
            predictions += sum(bool(line.strip()) for line in calls.read_text().splitlines())
    return fits, predictions


def worker(directory, job_id):
    directory = Path(directory)
    contract, grant = gate(directory)
    dispatch = read(directory / "RUN_STARTED.json")
    require(dispatch.get("experiment_id") == EXPERIMENT
            and dispatch.get("job_ids") == [j["job_id"] for j in contract["jobs"]], "DISPATCH_NOT_REGISTERED")
    jobs = {j["job_id"]: j for j in contract["jobs"]}
    require(job_id in jobs, "UNREGISTERED_JOB")
    job = deepcopy(jobs[job_id])
    dest = directory / "trials" / job_id
    dest.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    events, fits, predictions, outcome, error = [], 0, 0, "FAILED", None
    source = GuardedSource(source_path(contract["source_directory"]), job, grant["authorization_ref"])

    def event(name, **values):
        events.append({"event": name, "utc": stamp(), **values})

    binding = {"study_version": contract["engine_study_version"], "phase": contract["engine_phase"],
               "experiment_id": contract["experiment_id"], "group_id": job["group_id"],
               "method_id": METHODS[job["stage"]], "fold_id": job["fold_id"], "split_id": "FRESH-WEBGL1-LOEO-v1",
               "operating_point": "OP05", "model_unit_id": job_id, "evaluation_role": contract["evaluation_role"],
               "source_experiment_id": SOURCE_EXPERIMENT, "source_evaluation_role": contract["source_evaluation_role"],
               "source_collection_protocol": SOURCE_PROTOCOL, "source_reuse_mode": contract["source_reuse"]["mode"],
               "input_manifest_ref": str(directory / "CONTRACT.json"),
               "capacity_profile": contract["capacity_profile"]["profile_id"]}
    try:
        engine = load_engine()
        selected = {i: source.input_row(i) for i in job["train_ids"]}
        labels = {i: source.metadata(i) for i in job["train_ids"]}
        event("TRAIN_ONLY_INPUTS_OPENED", train_ids=job["train_ids"], heldout_inputs_opened=0, heldout_metadata_opened=0)
        kwargs = {"group": job["group_id"], "binding": binding,
                  "source_modes": {i: "raw_observation_v1" for i in job["train_ids"]},
                  "candidate_rows": {i: r["candidate_cells"] for i, r in selected.items()}}
        if job["stage"] == "RETENTION":
            initial = directory / "trials" / job["initializer"]
            validate_initializer_receipt(read(initial / "receipt.json"), job, contract)
            job["initial_model_ref"] = str(initial / "model.json")
            kwargs.update(initial_model=engine.load_model(initial / "model.json"),
                          initial_training=read(initial / "training.json"))
        definitions = read(source.source / "DEFINITIONS.json")
        method = engine.fit_sparse if job["stage"] == "SPARSE" else engine.fit_retention
        write(dest / "FIT_STARTED.json", {"at": stamp(), "count": 1, "job_id": job_id})
        fits = 1
        model, training = method(job, {i: r["features"] for i, r in selected.items()}, labels, definitions, **kwargs)
        write(dest / "training.json", training)
        engine.save_model(model, dest / "model.json")
        model = engine.load_model(dest / "model.json")
        require(model.fit["train_ids"] == job["train_ids"] and model.status in SUCCESS, "FIT_FAILED_OR_WRONG_MEMBERS")
        require(all(model.binding.get(k) == value for k, value in binding.items()), "MODEL_BINDING_MISMATCH")
        require(model.method_id == METHODS[job["stage"]], "MODEL_METHOD_MISMATCH")
        source.phase = "FROZEN"
        event("MODEL_SAVED_RELOADED_FROZEN", model_id=model.model_id)
        results = []
        with (dest / "predictions.jsonl").open("x") as stream, (dest / "PREDICTION_CALLS.jsonl").open("x") as calls:
            for oid in (job["outer_test_ids"] if job["stage"] == "RETENTION" else []):
                row = source.input_row(oid)
                calls.write(json.dumps({"opaque_id": oid, "at": stamp()}) + "\n")
                calls.flush()
                predictions += 1
                result = engine.predict_current(model, oid, row["features"],
                                                candidate_cells=row["candidate_cells"], source_mode="raw_observation_v1")
                stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                results.append(result)
                require(result["opaque_id"] == oid and result["decision"] in DECISIONS, "INVALID_PREDICTION:" + oid)
                require(result["decision"] != "FAILED", "PREDICTION_FAILED:" + oid)
        require(len(results) == job["max_prediction_calls"], "PREDICTION_COUNT_MISMATCH")
        source.phase = "PREDICTIONS_CLOSED"
        event("PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN", count=len(results))
        evaluation = []
        for result in results:
            meta = source.metadata(result["opaque_id"])
            evaluation.append({**{k: meta[k] for k in ("opaque_id", "supervised_label", "phase", "environment_group_id",
                                                        "config_id", "bundle_id", "triplet_id")}, "decision": result["decision"]})
        write(dest / "evaluation_rows.json", evaluation)
        event("HELDOUT_METADATA_JOINED_AFTER_CLOSE", count=len(evaluation))
        outcome = model.status
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        write(dest / "ERROR.json", error)
    event("JOB_CLOSED", outcome=outcome)
    write(dest / "access_log.json", events)
    receipt = {"experiment_id": EXPERIMENT, "capacity_profile": contract["capacity_profile"]["profile_id"],
               "job_id": job_id, "group_id": job["group_id"], "fold_id": job["fold_id"], "stage": job["stage"],
               "outcome": outcome, "actual_fit_invocations": fits, "actual_prediction_calls": predictions,
               "expected_prediction_calls": job["max_prediction_calls"], "charged_seconds": time.monotonic() - started,
               "attempt": 1, "error": error}
    write(dest / "receipt.json", receipt)
    return receipt


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def closed_rows(directory, job):
    dest = Path(directory) / "trials" / job["job_id"]
    require(read(dest / "receipt.json")["outcome"] in SUCCESS, "COMPARISON_JOB_NOT_CLOSED")
    events = [e["event"] for e in read(dest / "access_log.json")]
    require(events.index("MODEL_SAVED_RELOADED_FROZEN") < events.index("PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN")
            < events.index("HELDOUT_METADATA_JOINED_AFTER_CLOSE"), "COMPARISON_ACCESS_ORDER_INVALID")
    rows = read(dest / "evaluation_rows.json")
    predictions = read_jsonl(dest / "predictions.jsonl")
    require([r["opaque_id"] for r in rows] == job["outer_test_ids"]
            and [r["opaque_id"] for r in predictions] == job["outer_test_ids"], "COMPARISON_PREDICTION_MEMBERS_MISMATCH")
    require([r["decision"] for r in rows] == [r["decision"] for r in predictions], "COMPARISON_DECISIONS_MISMATCH")
    return rows, read(dest / "model.json")


def metrics(rows):
    attack = [r for r in rows if r["phase"] == "attack"]
    clean = [r for r in rows if r["phase"] != "attack"]
    cfg = defaultdict(list)
    for row in rows:
        cfg[row["config_id"]].append(row)
    configurations = {}
    for name, current in sorted(cfg.items()):
        positive = [r for r in current if r["phase"] == "attack"]
        negative = [r for r in current if r["phase"] != "attack"]
        configurations[name] = {"alerts": sum(r["decision"] == "MANIPULATION_ALERT" for r in positive),
                                "n": len(positive), "clean_alerts": sum(r["decision"] == "MANIPULATION_ALERT" for r in negative),
                                "clean_n": len(negative), "decisions": dict(Counter(r["decision"] for r in current))}
    alerts = sum(r["decision"] == "MANIPULATION_ALERT" for r in attack)
    return {"attack_alerts": alerts, "attack_n": len(attack), "tpr": alerts / len(attack) if attack else None,
            "clean_alerts": sum(r["decision"] == "MANIPULATION_ALERT" for r in clean), "clean_n": len(clean),
            "defined": sum(r["decision"] in ("MANIPULATION_ALERT", "NO_ALERT") for r in rows), "expected": len(rows),
            "decisions": dict(Counter(r["decision"] for r in rows)),
            "macro_tpr": sum(v["alerts"] / v["n"] for v in configurations.values()) / len(configurations) if configurations else None,
            "configurations": configurations}


def shared_basis_audit(directory, contract):
    """Inspect saved fit artifacts only; never refit or compare selected subsets."""
    candidate = NEW_CANDIDATES[-1]
    audits = []
    for fold in contract["folds"]:
        record = {"fold_id": fold["fold_id"], "source": "SAVED_RETENTION_TRAINING_AND_ENCODER",
                  "selected_atom_sets_required_equal": False, "fit_calls": 0, "prediction_calls": 0}
        try:
            artifacts = {}
            for group in GROUPS:
                job = next(j for j in contract["jobs"] if j["fold_id"] == fold["fold_id"]
                           and j["group_id"] == group and j["stage"] == "RETENTION")
                dest = Path(directory) / "trials" / job["job_id"]
                artifacts[group] = (read(dest / "training.json"), read(dest / "model.json"))
            (bt, bm), (wt, wm) = artifacts["BASE49"], artifacts["WEBGL50"]
            ba = {a["atom_id"]: a for a in bt["encoded_atoms"]}
            wa = {a["atom_id"]: a for a in wt["encoded_atoms"]}
            bc, wc = bt["semantic_catalog"], wt["semantic_catalog"]
            be, we = bm["encoder"], wm["encoder"]
            checks = {
                "encoded_pool_adds_only_webgl1": set(wa) - set(ba) == {candidate} and not set(ba) - set(wa),
                "shared_encoded_atom_metadata_equal": all(wa.get(k) == v for k, v in ba.items()),
                "semantic_catalog_adds_only_webgl1": set(wc) - set(bc) == {candidate} and not set(bc) - set(wc),
                "shared_semantic_catalog_equal": all(wc.get(k) == v for k, v in bc.items()),
                "numeric_encoder_equal": be["numeric"] == we["numeric"],
                "fixed_atoms_add_only_webgl1": candidate not in be["fixed_atoms"]
                    and we["fixed_atoms"].count(candidate) == 1
                    and be["fixed_atoms"] == [a for a in we["fixed_atoms"] if a != candidate],
                "encoder_other_metadata_equal": {k: v for k, v in be.items() if k not in ("fixed_atoms", "numeric")}
                    == {k: v for k, v in we.items() if k not in ("fixed_atoms", "numeric")},
            }
            record.update(status="PASS" if all(checks.values()) else "FAIL", checks=checks,
                          base_encoded_atom_n=len(ba), webgl_encoded_atom_n=len(wa),
                          added_encoded_atom_ids=sorted(set(wa) - set(ba)),
                          removed_encoded_atom_ids=sorted(set(ba) - set(wa)))
        except (OSError, KeyError, TypeError, StopIteration, ValueError) as error:
            record.update(status="FAIL", error=type(error).__name__ + ":" + str(error))
        audits.append(record)
    return {"status": "PASS" if audits and all(a["status"] == "PASS" for a in audits) else "FAIL",
            "folds": audits, "action_on_failure": "REPORT_ONLY_NO_REFIT_OR_RETUNING"}


def summarize(directory, contract):
    require(read(directory / "EXECUTION.json")["execution_complete"] is True, "ALL_JOBS_MUST_CLOSE_BEFORE_COMPARISON")
    groups, saved = {}, {}
    for group in GROUPS:
        rows, fold_rows = [], []
        for job in contract["jobs"]:
            if job["group_id"] != group or job["stage"] != "RETENTION":
                continue
            current, model = closed_rows(directory, job)
            rows.extend(current)
            selected = {literal["atom_id"] for clause in model["clauses"] for literal in clause["literals"]}
            fold_rows.append({"fold_id": job["fold_id"], "heldout_environment": job["heldout_environment"],
                              **metrics(current), "clauses": model["clauses"],
                              "selected_new_conditions": {cid: cid in selected for cid in NEW_CANDIDATES}})
        require(Counter(r["opaque_id"] for r in rows) == Counter(contract["sample_ids"]), "MATCHED_COMPARISON_COHORT_REQUIRED")
        groups[group] = {**metrics(rows), "folds": fold_rows,
                         "selected_new_condition_folds": {cid: sum(f["selected_new_conditions"][cid] for f in fold_rows)
                                                          for cid in NEW_CANDIDATES},
                         "reused_saved_predictions": False}
        saved[group] = {r["opaque_id"]: r for r in rows}
    changes, gained, lost = [], [], []
    clean_gained, clean_lost, defined_lost = [], [], []
    for oid in contract["sample_ids"]:
        before, after = saved["BASE49"][oid], saved["WEBGL50"][oid]
        require({k: v for k, v in before.items() if k != "decision"}
                == {k: v for k, v in after.items() if k != "decision"}, "MATCHED_COMPARISON_METADATA_MISMATCH")
        a, b = before["decision"], after["decision"]
        if a != b:
            record = {**{k: before[k] for k in ("opaque_id", "phase", "config_id", "environment_group_id", "triplet_id")},
                      "reference_decision": a, "new_decision": b}
            changes.append(record)
            if before["phase"] == "attack":
                if a != "MANIPULATION_ALERT" and b == "MANIPULATION_ALERT":
                    gained.append(record)
                if a == "MANIPULATION_ALERT" and b != "MANIPULATION_ALERT":
                    lost.append(record)
            else:
                if a != "MANIPULATION_ALERT" and b == "MANIPULATION_ALERT":
                    clean_gained.append(record)
                if a == "MANIPULATION_ALERT" and b != "MANIPULATION_ALERT":
                    clean_lost.append(record)
            if a in ("MANIPULATION_ALERT", "NO_ALERT") and b not in ("MANIPULATION_ALERT", "NO_ALERT"):
                defined_lost.append(record)
    by_config = {cfg: {"newly_detected_attack_ids": [r["opaque_id"] for r in gained if r["config_id"] == cfg],
                       "lost_detected_attack_ids": [r["opaque_id"] for r in lost if r["config_id"] == cfg]}
                 for cfg in groups["BASE49"]["configurations"]}
    result = {"experiment_id": contract["experiment_id"], "evaluation_role": contract["evaluation_role"],
              "source_evaluation_role": contract["source_evaluation_role"], "source_reuse": contract["source_reuse"],
              "capacity_profile": contract["capacity_profile"], "new_collection": False,
              "groups": groups, "changed_decisions": changes,
              "attack_alert_delta": groups["WEBGL50"]["attack_alerts"] - groups["BASE49"]["attack_alerts"],
              "newly_detected_attacks": gained, "lost_detected_attacks": lost,
              "new_clean_alerts": clean_gained, "removed_clean_alerts": clean_lost,
              "newly_undefined": defined_lost, "paired_config_differences": by_config,
              "shared_training_basis_audit": shared_basis_audit(directory, contract),
              "baseline_fit_calls": 6, "baseline_prediction_calls": 378,
              "scope": "Read-only reuse of the admitted v14 CAP7 cohort and its three folds; both pools newly fitted at identical CAP8 with the same semantic selector. Only the saved WebGL1 candidate differs between pools. No new collection or independent confirmation; not normal App population FPR."}
    write(directory / "RESULTS.json", result)
    return result


def run(directory):
    directory = Path(directory)
    contract, grant = gate(directory)
    write(directory / "RUN_STARTED.json", {"at": stamp(), "experiment_id": EXPERIMENT,
                                           "authorization_ref": grant["authorization_ref"],
                                           "job_ids": [j["job_id"] for j in contract["jobs"]]})
    receipts, dispatches, stop = [], [], None
    run_started = time.monotonic()
    for job in contract["jobs"]:
        started = time.monotonic()
        total_remaining = contract["budget"]["max_total_seconds"] - (started - run_started)
        if total_remaining <= 0:
            stop = {"job_id": job["job_id"], "type": "RunDeadline", "reason": "REGISTERED_WALL_LIMIT", "wall_seconds": 0}
            break
        worker_timeout = min(contract["budget"]["max_worker_seconds"], total_remaining)
        dispatches.append(job["job_id"])
        try:
            result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", job["job_id"],
                                     "--directory", str(directory)], capture_output=True, text=True,
                                    timeout=worker_timeout)
            receipt_path = directory / "trials" / job["job_id"] / "receipt.json"
            require(receipt_path.exists(), "WORKER_DID_NOT_CLOSE_RECEIPT:" + result.stderr[-2000:])
            receipt = read(receipt_path)
            receipts.append(receipt)
            print(job["job_id"], receipt["outcome"], flush=True)
            require(result.returncode == 0 and receipt["outcome"] in SUCCESS, "WORKER_FAILED")
            require(receipt["actual_fit_invocations"] == 1
                    and receipt["actual_prediction_calls"] == job["max_prediction_calls"], "WORKER_CALL_COUNT_MISMATCH")
        except (Exception, KeyboardInterrupt) as error:
            stop = {"job_id": job["job_id"], "type": type(error).__name__, "reason": str(error),
                    "wall_seconds": time.monotonic() - started}
            break
    fits, predictions = durable_counts(directory)
    charged = sum(r["charged_seconds"] for r in receipts)
    if stop and stop["job_id"] not in {r["job_id"] for r in receipts}:
        charged += stop["wall_seconds"]
    complete = stop is None and len(receipts) == 12 and fits == 12 and predictions == 756
    if stop is None and not complete:
        stop = {"type": "AccountingMismatch", "reason": "DURABLE_CALL_COUNTS_DIFFER_FROM_REGISTERED_TOTAL"}
    execution = {"experiment_id": EXPERIMENT, "execution_complete": complete, "stop_reason": stop,
                 "source_reuse": contract["source_reuse"], "capacity_profile": contract["capacity_profile"],
                 "new_collection": False,
                 "actual_fit_jobs": fits, "actual_prediction_calls": predictions,
                 "prediction_accounting": "Durable pre-invocation call markers, including failed or timed-out workers; conservatively charged as attempts.",
                 "completed_jobs": len(receipts), "dispatched_jobs": dispatches,
                 "unexecuted_jobs": 12 - len(dispatches), "unclosed_jobs": len(dispatches) - len(receipts),
                 "remaining_round_fits": contract["budget"]["round_fit_limit"] - fits,
                 "charged_seconds": charged,
                 "additional_retries": 0, "fit_count_basis": contract["fit_count_basis"], "receipts": receipts}
    write(directory / "EXECUTION.json", execution)
    if complete:
        print(json.dumps(summarize(directory, contract), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(execution, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=HERE)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.directory, args.worker)
    elif args.run:
        run(args.directory)
    else:
        print(json.dumps({"mode": "READ_ONLY", "contract_present": (args.directory / "CONTRACT.json").exists(),
                          "execution_started": (args.directory / "RUN_STARTED.json").exists()}))
