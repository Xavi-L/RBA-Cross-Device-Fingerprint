#!/usr/bin/env python3
"""Run one registered selector pilot, then reuse closed baseline predictions."""
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
EXPERIMENT = "semantic-selector-v2-raw-only-pilot-v1"
STUDY = "rule-semantics-selector-v2-pilot"
PHASE = "RSR_SELECTOR_V2_PILOT"
GROUP = "LANG_ADD_WD_REPLACE"
METHODS = {"SPARSE": "GREEDY_SEMANTIC_V2", "RETENTION": "R_KEEP_SWAP_V2"}
NEW_CANDIDATES = ("RSR-LANG-FIRST-v1", "RSR-WEBDRIVER-STATE-v1")
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


def gate(directory):
    directory = Path(directory)
    contract = read(directory / "CONTRACT.json")
    grant = read(directory / "AUTHORIZATION.json")
    require(contract.get("experiment_id") == EXPERIMENT
            and contract.get("engine_study_version") == STUDY
            and contract.get("engine_phase") == PHASE, "WRONG_EXPERIMENT_IDENTITY")
    require(contract.get("readiness") == "SELECTOR_V2_READY", "DATA_NOT_READY")
    require(grant.get("training_authorized") is True
            and grant.get("admission_authorized") is True, "EXPLICIT_USER_AUTHORIZATION_REQUIRED")
    ids, jobs, folds = contract["sample_ids"], contract["jobs"], contract["folds"]
    require(grant.get("experiment_id") == contract["experiment_id"]
            and grant.get("sample_ids") == ids
            and grant.get("job_ids") == [j["job_id"] for j in jobs]
            and grant.get("authorization_ref"), "AUTHORIZATION_MEMBERSHIP_MISMATCH")
    require(len(ids) == len(set(ids)) == 378 and len(jobs) == 6, "EXACT_REGISTERED_LAYOUT_REQUIRED")
    require(len({j["job_id"] for j in jobs}) == 6 and len(folds) == 3
            and len({f["fold_id"] for f in folds}) == 3, "UNIQUE_FOLDS_JOBS_REQUIRED")
    require(Counter((j["fold_id"], j["group_id"], j["stage"]) for j in jobs)
            == Counter((f["fold_id"], GROUP, s) for f in folds for s in METHODS),
            "EXACT_GROUP_STAGE_FOLD_JOBS_REQUIRED")
    require(set(contract["source_modes"]) == set(ids)
            and set(contract["source_modes"].values()) == {"raw_observation_v1"}, "RAW_ONLY_MEMBERS_REQUIRED")
    source = source_path(contract["source_directory"])
    baseline = source_path(contract["baseline_directory"])
    require(source == baseline and source != directory.resolve(), "FROZEN_SOURCE_BASELINE_REQUIRED")
    prior_contract = read(baseline / "CONTRACT.json")
    require(prior_contract["experiment_id"] == "raw-only-rkeep-three-env-fourteen-config-v1"
            and prior_contract["readiness"] == "RAW_ONLY_COMPARISON_READY", "WRONG_FROZEN_SOURCE")
    for key in ("sample_ids", "folds", "source_modes", "constraints", "evaluation_role"):
        require(contract[key] == prior_contract[key], "FROZEN_SOURCE_MISMATCH:" + key)
    require(Counter(i for f in folds for i in f["outer_test_ids"]) == Counter(ids), "OUTER_COVERAGE_NOT_EXACT")
    preceding = {}
    for job in jobs:
        require(Path(job["job_id"]).name == job["job_id"]
                and job["job_id"] not in ("", ".", ".."), "INVALID_JOB_DIRECTORY")
        train, test = job["train_ids"], job["outer_test_ids"]
        require(len(train) == len(set(train)) == 252 and len(test) == len(set(test)) == 126
                and not set(train) & set(test) and set(train) | set(test) == set(ids), "INVALID_OUTER_SPLIT")
        fold = next(f for f in folds if f["fold_id"] == job["fold_id"])
        require(all(job[k] == fold[k] for k in ("train_ids", "outer_test_ids", "heldout_environment")),
                "JOB_DIFFERS_FROM_REGISTERED_FOLD")
        require(job["max_prediction_calls"] == (126 if job["stage"] == "RETENTION" else 0),
                "PREDICTION_BUDGET_MISMATCH")
        if job["stage"] == "RETENTION":
            initializer = preceding.get(job.get("initializer"))
            require(initializer is not None and initializer["stage"] == "SPARSE"
                    and initializer["fold_id"] == job["fold_id"]
                    and initializer["group_id"] == job["group_id"], "OWN_FOLD_INITIALIZER_REQUIRED")
        preceding[job["job_id"]] = job
    prior = read(baseline / "EXECUTION.json")
    require(prior["execution_complete"] is True and prior["actual_fit_jobs"] == 12
            and prior["actual_prediction_calls"] == 756
            and prior["cumulative_fit_jobs"] == 189
            and prior["remaining_research_fits"] == 11, "SHARED_PRIOR_BUDGET_CHANGED")
    budget = contract["budget"]
    require(budget["base_fit_jobs"] == 189 and budget["remaining_fits"] == 11
            and budget["planned_fits"] == 6 and budget["max_worker_seconds"] == 90
            and budget["base_charged_seconds"] == prior["cumulative_charged_seconds"], "REGISTERED_BUDGET_MISMATCH")
    return contract, grant


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
    from hybridguard_agent.research import rule_semantics_selector_v2
    return rule_semantics_selector_v2


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
               "method_id": METHODS[job["stage"]], "fold_id": job["fold_id"], "split_id": "RAW-LOEO-v1",
               "operating_point": "OP05", "model_unit_id": job_id, "evaluation_role": contract["evaluation_role"],
               "input_manifest_ref": str(directory / "CONTRACT.json")}
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
            require(read(initial / "receipt.json")["outcome"] in SUCCESS, "INITIALIZER_NOT_READY")
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
    receipt = {"job_id": job_id, "group_id": job["group_id"], "fold_id": job["fold_id"], "stage": job["stage"],
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


def summarize(directory, contract):
    require(read(directory / "EXECUTION.json")["execution_complete"] is True, "ALL_JOBS_MUST_CLOSE_BEFORE_BASELINE_READ")
    baseline = source_path(contract["baseline_directory"])
    old = read(baseline / "CONTRACT.json")
    groups, saved = {}, {}
    for label, source, jobs, group_id in (("NEW_SCHEME", directory, contract["jobs"], GROUP),
                                           ("BASE", baseline, old["jobs"], "BASE"),
                                           ("PRIOR_COMBINATION", baseline, old["jobs"], GROUP)):
        rows, fold_rows = [], []
        for job in jobs:
            if job["group_id"] != group_id or job["stage"] != "RETENTION":
                continue
            current, model = closed_rows(source, job)
            rows.extend(current)
            selected = {literal["atom_id"] for clause in model["clauses"] for literal in clause["literals"]}
            fold_rows.append({"fold_id": job["fold_id"], "heldout_environment": job["heldout_environment"],
                              **metrics(current), "clauses": model["clauses"],
                              "selected_new_conditions": {cid: cid in selected for cid in NEW_CANDIDATES}})
        require(Counter(r["opaque_id"] for r in rows) == Counter(contract["sample_ids"]), "MATCHED_COMPARISON_COHORT_REQUIRED")
        groups[label] = {**metrics(rows), "folds": fold_rows, "prediction_source": str(source),
                         "reused_saved_predictions": label != "NEW_SCHEME"}
        saved[label] = {r["opaque_id"]: r for r in rows}
    changed = {}
    for label in ("BASE", "PRIOR_COMBINATION"):
        differences = []
        for oid in contract["sample_ids"]:
            before, after = saved[label][oid], saved["NEW_SCHEME"][oid]
            require({k: v for k, v in before.items() if k != "decision"}
                    == {k: v for k, v in after.items() if k != "decision"}, "MATCHED_COMPARISON_METADATA_MISMATCH")
            if before["decision"] != after["decision"]:
                differences.append({"opaque_id": oid, "phase": before["phase"], "config_id": before["config_id"],
                                    "environment_group_id": before["environment_group_id"],
                                    "reference_decision": before["decision"], "new_decision": after["decision"]})
        changed[label] = differences
    result = {"experiment_id": contract["experiment_id"], "evaluation_role": contract["evaluation_role"],
              "groups": groups, "changed_decisions": changed,
              "attack_alert_delta": groups["NEW_SCHEME"]["attack_alerts"] - groups["BASE"]["attack_alerts"],
              "prior_combination_attack_alert_delta": groups["NEW_SCHEME"]["attack_alerts"] - groups["PRIOR_COMBINATION"]["attack_alerts"],
              "baseline_fit_calls": 0, "baseline_prediction_calls": 0,
              "scope": "Exposed emulator development cohort; joint candidate-pool and selector change, not an isolated condition effect, independent confirmation, or normal App population FPR."}
    write(directory / "RESULTS.json", result)
    return result


def run(directory):
    directory = Path(directory)
    contract, grant = gate(directory)
    write(directory / "RUN_STARTED.json", {"at": stamp(), "experiment_id": EXPERIMENT,
                                           "authorization_ref": grant["authorization_ref"],
                                           "job_ids": [j["job_id"] for j in contract["jobs"]]})
    receipts, dispatches, stop = [], [], None
    for job in contract["jobs"]:
        started = time.monotonic()
        dispatches.append(job["job_id"])
        try:
            result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker", job["job_id"],
                                     "--directory", str(directory)], capture_output=True, text=True,
                                    timeout=contract["budget"]["max_worker_seconds"])
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
    complete = stop is None and len(receipts) == 6 and fits == 6 and predictions == 378
    if stop is None and not complete:
        stop = {"type": "AccountingMismatch", "reason": "DURABLE_CALL_COUNTS_DIFFER_FROM_REGISTERED_TOTAL"}
    execution = {"experiment_id": EXPERIMENT, "execution_complete": complete, "stop_reason": stop,
                 "actual_fit_jobs": fits, "actual_prediction_calls": predictions,
                 "prediction_accounting": "Durable pre-invocation call markers, including failed or timed-out workers; conservatively charged as attempts.",
                 "completed_jobs": len(receipts), "dispatched_jobs": dispatches,
                 "unexecuted_jobs": 6 - len(dispatches), "unclosed_jobs": len(dispatches) - len(receipts),
                 "cumulative_fit_jobs": contract["budget"]["base_fit_jobs"] + fits,
                 "remaining_research_fits": contract["budget"]["remaining_fits"] - fits,
                 "charged_seconds": charged, "cumulative_charged_seconds": contract["budget"]["base_charged_seconds"] + charged,
                 "additional_retries": 0, "baseline_fit_calls": 0, "baseline_prediction_calls": 0, "receipts": receipts}
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
