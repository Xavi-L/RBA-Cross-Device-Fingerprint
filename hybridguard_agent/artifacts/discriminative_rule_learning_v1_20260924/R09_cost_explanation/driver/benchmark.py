"""R09 v1: read-only fixed-model benchmark. No learning entry point or fit grant."""
import argparse
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import platform
import select
import subprocess
import sys
import time
from datetime import datetime, timezone

VERSION = "r09-fixed-inference-v1"
NOW = lambda: datetime.now(timezone.utc).isoformat()
NS = time.perf_counter_ns


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x]


def write(path, obj):
    with Path(path).open("x") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


def encoded(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def receive(process, deadline):
    remaining = (deadline-NS())/1e9
    require(remaining > 0, "NOT_RUN_BUDGET_EXHAUSTED")
    ready, _, _ = select.select([process.stdout], [], [], remaining)
    require(ready, "WORKER_TIMEOUT_REMAINING_BUDGET_EXHAUSTED")
    line = process.stdout.readline()
    require(line, "WORKER_EXITED_WITHOUT_RECEIPT")
    return json.loads(line)


class NoLearningImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"highspy", "hybridguard_agent.research.rule_learning.selector",
                        "hybridguard_agent.research.rule_learning.solver",
                        "hybridguard_agent.research.rule_learning.runner",
                        "hybridguard_agent.research.rule_learning.synthetic"}:
            raise RuntimeError("R09_LEARNING_IMPORT_FORBIDDEN:" + fullname)


def frozen_api(freeze):
    freeze = Path(freeze).resolve()
    require(Path(sys.executable).resolve() == (freeze / "dependencies/python/bin/python3.12").resolve(),
            "WRONG_INTERPRETER_NO_FALLBACK")
    sys.dont_write_bytecode = True
    sys.meta_path.insert(0, NoLearningImports())
    sys.path[:0] = [str(freeze / "snapshot"), str(freeze / "dependencies/site-packages")]
    from hybridguard_agent.research.rule_learning import models, predictor, baselines, contracts, access, fold_data
    # CPython 3.12 local monitoring instruments only forbidden code objects. It
    # does not replace selector bytes or profile every measured inference call.
    tool = 5
    sys.monitoring.use_tool_id(tool, "R09_NO_LEARNING")
    rejected = []
    def deny(code, offset):
        rejected.append(code.co_qualname)
        raise RuntimeError("R09_FIT_OR_TRAIN_ACCESS_FORBIDDEN:" + code.co_qualname)
    sys.monitoring.register_callback(tool, sys.monitoring.events.PY_START, deny)
    blocked = [access.authorize, access.open_formal_fit, baselines.core_view,
               baselines.single_surface_view, baselines.fixed_model, fold_data.TrainQuantiles.fit]
    for fn in blocked:
        sys.monitoring.set_local_events(tool, fn.__code__, sys.monitoring.events.PY_START)
    modules = {m.__name__: str(Path(m.__file__).resolve()) for m in
               (models, predictor, baselines, contracts, access, fold_data)}
    require(all(p.startswith(str(freeze / "snapshot") + os.sep) for p in modules.values()), "MODULE_FALLBACK")
    return models, predictor, baselines, contracts, modules, rejected


def validate_resources(out):
    manifest = read(out / "DRIVER_RESOURCE_MANIFEST.json")
    for row in manifest["files"]:
        path = Path(row["path"])
        require(path.is_file() and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "R09_RESOURCE_CHANGED:" + str(path))
    return manifest


def exact_prediction(model, projected, oid, reference, predictor):
    result = predictor.predict(model, oid, {"features": projected[oid], "view_id": model.view["view_id"]})
    # These are dispatcher annotations, never inferred from labels.
    result.update(experiment_id="R05_PRIMARY", evaluation_track="LOEO-v1")
    return result


def worker(out, fold):
    start = NS()
    protocol = read(out / "benchmark_protocol.json")
    entry = next(x for x in read(out / "model_input_manifest.json")["models"] if x["fold_id"] == fold)
    verify_start = NS()
    validate_resources(out)
    verification_ns = NS() - verify_start
    t = NS()
    models, predictor, baselines, contracts, modules, rejected = frozen_api(protocol["freeze_root"])
    module_load_ns = NS() - t
    t = NS()
    model = models.load_model(entry["model_path"])
    model_load_ns = NS() - t
    t = NS()
    require(model.model_id == entry["model_id"] and model.binding == entry["binding"], "MODEL_BINDING_CHANGED")
    require(not model.encoder, "UNEXPECTED_ENCODER_PRIMARY_CORE")
    candidates = contracts.ledger()
    references = {r["opaque_id"]: r for r in lines(entry["predictions_path"])}
    inputs = {r["opaque_id"]: r for r in entry["inputs"]}
    require(set(references) == set(inputs), "REFERENCE_MEMBERSHIP_CHANGED")
    reference_setup_ns = NS() - t
    startup = dict(kind="STARTUP", fold_id=fold, pid=os.getpid(), utc=NOW(), executable=sys.executable,
        cwd=str(Path.cwd()), cwd_empty=not any(Path.cwd().iterdir()), module_paths=modules,
        resource_verification_ns=verification_ns, module_load_ns=module_load_ns,
        model_load_including_validation_ns=model_load_ns, reference_and_contract_setup_ns=reference_setup_ns,
        worker_startup_inclusive_ns=NS()-start, model_id=model.model_id, fit_calls=0,
        guard="CPYTHON312_LOCAL_PY_START_ON_FORBIDDEN_FUNCTIONS_AND_LEARNING_IMPORT_DENIAL")
    print(encoded(startup), flush=True)
    for line in sys.stdin:
        ticket = json.loads(line)
        if ticket.get("command") == "CLOSE":
            print(encoded({"kind": "CLOSED", "rejected_training_calls": rejected, "fit_calls": 0}), flush=True)
            return
        require(ticket["opaque_id"] in inputs, "INPUT_NOT_IN_FROZEN_TEST_MEMBERS")
        oid = ticket["opaque_id"]
        row = dict(ticket, kind="SAMPLE", record_role="BENCHMARK_ONLY", fold_id=fold,
                   model_id=entry["model_id"], method_id="GREEDY_OR", operating_point="OP05",
                   source_condition="SRC-111", input_view="core", pid=os.getpid(), utc=NOW(),
                   boolean_only_ns=None, explanation_only_ns=None,
                   separate_boolean_explanation_status="NOT_RECORDED_INTERLEAVED_FROZEN_PREDICTOR")
        row["input_ref"] = inputs[oid]["path"]
        t_all = NS()
        try:
            t = NS()
            raw = read(inputs[oid]["path"])["features"]
            row["cached_input_read_parse_ns"] = NS()-t
            t = NS()
            projected, _ = baselines.project_core({oid: raw}, candidates, "SRC-111")
            row["fixed_feature_conversion_ns"] = NS()-t
            t = NS()
            prediction = exact_prediction(model, projected, oid, references[oid], predictor)
            row["predict_including_explanation_and_model_integrity_ns"] = NS()-t
            t = NS()
            require(prediction == references[oid], "CLOSED_PREDICTION_SEMANTICS_CHANGED")
            row["semantic_verification_ns"] = NS()-t
            t = NS()
            serialized = encoded(prediction)
            row["prediction_serialization_ns"] = NS()-t
            row.update(status="MATCH", semantic_sha256=hashlib.sha256(serialized.encode()).hexdigest(),
                       decision=prediction["decision"], logical_state=prediction["logical_state"], error=None)
        except Exception as exc:
            row.update(status="FAILED", error=type(exc).__name__+":"+str(exc))
        row["sample_inclusive_ns"] = NS()-t_all
        print(encoded(row), flush=True)


def reserve(out, protocol, manifest):
    base = read(protocol["shared_budget_ledger"])
    require(sha(protocol["shared_budget_ledger"]) == manifest["shared_budget_ledger_sha256"], "SHARED_BUDGET_CHANGED")
    remaining = base["limits"]["wall_clock_seconds"] - base["charged_seconds"]
    require(remaining > 0, "NOT_RUN_BUDGET_EXHAUSTED")
    state = dict(schema_version="r09-linked-nonfit-ledger-v1", shared_ledger=protocol["shared_budget_ledger"],
        shared_ledger_sha256=manifest["shared_budget_ledger_sha256"], base_used_fit_jobs=base["used_fit_jobs"],
        base_charged_seconds=base["charged_seconds"], limits=base["limits"], new_fit_jobs=0,
        state="RUNNING_RESERVED", reserved_seconds=min(remaining, protocol["benchmark_wall_cap_seconds"]),
        incremental_charged_seconds=min(remaining, protocol["benchmark_wall_cap_seconds"]), started_at=NOW(),
        no_new_fit_capability=True, reason="R04 frozen dispatcher has no R09 model jobs; linked nonfit account",
        future_accounting="Add this linked debit to the original ledger; never reset either account.")
    write(out / "TIMING_BUDGET_LEDGER.json", state)
    return state


def run(out):
    # The start marker makes even a crashed attempt non-repeatable in place.
    write(out / "BENCHMARK_ATTEMPT.json", {"utc": NOW(), "version": VERSION, "retry": False})
    protocol = read(out / "benchmark_protocol.json")
    manifest = read(out / "model_input_manifest.json")
    validate_resources(out)
    require(read(out / "synthetic_validation.json")["status"] == "PASS", "SYNTHETIC_GATE_FAILED")
    ledger = reserve(out, protocol, manifest)
    start = NS()
    deadline = start + int(ledger["reserved_seconds"]*1e9)
    processes, startups, rows, passes = {}, [], [], []
    all_inputs = sorted((i["opaque_id"], e["fold_id"]) for e in manifest["models"] for i in e["inputs"])
    failure = None
    raw_file = (out / "timing_raw.jsonl").open("x")
    try:
        cold_start = NS()
        for entry in manifest["models"]:
            fold = entry["fold_id"]
            work = out / "workers" / fold
            work.mkdir(parents=True)
            empty = work / "empty_cwd"
            empty.mkdir()
            err = (work / "stderr.txt").open("x")
            t = NS()
            p = subprocess.Popen([sys.executable, "-B", "-I", "-S", str(Path(__file__).resolve()),
                "worker", str(out), "--fold", fold], cwd=empty, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=err, text=True, bufsize=1)
            processes[fold] = (p, err)
            startup = receive(p, deadline)
            require(startup["kind"] == "STARTUP", "WORKER_STARTUP_FAILED")
            startup["parent_process_launch_through_ready_ns"] = NS()-t
            startups.append(startup)
            write(work / "STARTUP.json", startup)
        for phase, count in (("COLD", 1), ("WARMUP", 1), ("TIMED", 5)):
            for pass_number in range(1, count+1):
                pass_start = cold_start if phase == "COLD" else NS()
                audit_ns = 0
                for oid, fold in all_inputs:
                    require((NS()-start)/1e9 < ledger["reserved_seconds"], "NOT_RUN_BUDGET_EXHAUSTED")
                    ticket = dict(phase=phase, pass_number=pass_number, opaque_id=oid,
                                  sequence=len(rows)+1, command="PREDICT")
                    p = processes[fold][0]
                    t = NS()
                    p.stdin.write(encoded(ticket)+"\n")
                    p.stdin.flush()
                    record = receive(p, deadline)
                    record["ipc_request_response_inclusive_ns"] = NS()-t
                    require(record["opaque_id"] == oid and record["sequence"] == len(rows)+1, "WORKER_ORDER_CHANGED")
                    rows.append(record)
                    t = NS()
                    raw_file.write(encoded(record)+"\n")
                    raw_file.flush()
                    audit_ns += NS()-t
                    require(record["status"] == "MATCH", "BENCHMARK_SEMANTIC_OR_TECHNICAL_FAILURE_NO_RETRY")
                t = NS()
                os.fsync(raw_file.fileno())
                fsync_ns = NS()-t
                passes.append(dict(phase=phase, pass_number=pass_number, expected_n=len(all_inputs),
                    completed_n=len(all_inputs), elapsed_inclusive_ns=NS()-pass_start,
                    audit_serialization_write_flush_ns=audit_ns, audit_fsync_ns=fsync_ns))
    except Exception as exc:
        failure = type(exc).__name__+":"+str(exc)
    finally:
        raw_file.close()
        closures = []
        for fold, (p, err) in processes.items():
            try:
                if p.poll() is None and failure is None:
                    p.stdin.write('{"command":"CLOSE"}\n'); p.stdin.flush()
                    closures.append(dict(fold_id=fold, **json.loads(p.stdout.readline())))
                elif p.poll() is None:
                    p.terminate()
                p.wait(timeout=5)
            finally:
                err.close()
        elapsed = (NS()-start)/1e9
        ledger.update(state="COMPLETED" if failure is None else "FAILED", ended_at=NOW(),
            elapsed_seconds=elapsed, incremental_charged_seconds=min(elapsed, ledger["reserved_seconds"]),
            cumulative_fit_jobs_including_base=ledger["base_used_fit_jobs"],
            cumulative_charged_seconds_including_base=ledger["base_charged_seconds"]+min(elapsed, ledger["reserved_seconds"]))
        # Only this new R09 account is settled; the original shared ledger is read-only.
        (out / "TIMING_BUDGET_LEDGER.json").write_text(json.dumps(ledger, indent=2)+"\n")
        write(out / "timing_passes.json", passes)
        write(out / "BENCHMARK_CLOSURE.json", dict(status="PASS" if failure is None else "FAILED",
            expected_n=1134, observed_n=len(rows), matched_n=sum(r["status"]=="MATCH" for r in rows),
            error=failure, closures=closures, startups=startups, new_fit_jobs=0,
            missing_records_retained_as_not_run=True))
    require(failure is None, failure or "")


def synthetic(freeze, dest):
    models, predictor, baselines, contracts, modules, rejected = frozen_api(freeze)
    checks = []
    def check(name, condition):
        require(condition, name); checks.append({"check": name, "status": "PASS"})
    def toy(status="FITTED", sign="POSITIVE", constant=None):
        active = status == "FITTED"
        a = models.Atom("toy", "synthetic_family", ("synthetic_surface",), ("E",), ("toy",))
        return models.RuleModel("GREEDY_OR", status,
            (models.Clause((models.Literal("toy", sign),)),) if active else (), (a,) if active else (),
            {"data_origin":"BUILTIN_SYNTHETIC", "fold_id":"SYNTHETIC", "fit_job_id":None},
            {"view_id":"SYNTHETIC", "input_atom_ids":["toy"]},
            {"status":"HAND_CONSTRUCTED_NO_FIT", "train_ids":[]}, constant=constant)
    for sign in ("POSITIVE", "NEGATIVE"):
        for value in ("T", "F", "U"):
            m = toy(sign=sign)
            cell = {"value": {"T":True,"F":False,"U":None}[value], "available":value!="U", "evaluation_status":"OK", "reason":"TOY"}
            p = predictor.predict(m, "synthetic", {"features":{"toy":cell},"view_id":"SYNTHETIC"})
            state = value if sign=="POSITIVE" or value=="U" else {"T":"F","F":"T"}[value]
            check(sign+":"+value, p["logical_state"] == state and p["decision"] == {"T":"MANIPULATION_ALERT","F":"NO_ALERT","U":"INSUFFICIENT_EVIDENCE"}[state])
            check("roundtrip:"+sign+":"+value, predictor.predict(models.RuleModel.from_dict(m.to_dict()), "synthetic", {"features":{"toy":cell},"view_id":"SYNTHETIC"})==p)
    for status in ("EMPTY_MODEL", "FAILED"):
        p = predictor.predict(toy(status=status), "synthetic", {"features":{},"view_id":"SYNTHETIC"})
        check(status, p["decision"] == status and p["logical_state"] is None)
    for constant in ("NO_ALERT", "INSUFFICIENT_EVIDENCE"):
        p = predictor.predict(toy(status="FIXED",constant=constant), "synthetic", {"features":{},"view_id":"SYNTHETIC"})
        check("constant:"+constant, p["decision"] == constant)
    for cell_status in ("FAILED", "NOT_REQUESTED"):
        p = predictor.predict(toy(), "synthetic", {"features":{"toy":contracts.cell(cell_status)},"view_id":"SYNTHETIC"})
        check("cell_failure_not_U:"+cell_status, p["decision"] == "FAILED" and p["logical_state"] is None)
    for op, values, expected in (("AND", ("T","U"), "U"), ("AND", ("F","U"), "F"),
                                 ("OR", ("T","U"), "T"), ("OR", ("F","U"), "U")):
        check(op+":"+str(values), contracts.logic(values, op)==expected)
    from hybridguard_agent.research.rule_learning import access
    from hybridguard_agent.research.rule_learning.fold_data import TrainQuantiles
    for fn, args in ((baselines.single_surface_view, (None, "native84")), (access.open_formal_fit, (None,)),
                     (TrainQuantiles("toy").fit, (None, None))):
        try: fn(*args)
        except RuntimeError as exc: check("no_fit_guard:"+fn.__name__, "R09_FIT_OR_TRAIN_ACCESS_FORBIDDEN" in str(exc))
        else: raise AssertionError("FIT_GUARD_DID_NOT_REJECT")
    try: __import__("hybridguard_agent.research.rule_learning.selector")
    except RuntimeError as exc: check("selector_import_rejected", "R09_LEARNING_IMPORT_FORBIDDEN" in str(exc))
    else: raise AssertionError("SELECTOR_IMPORT_ALLOWED")
    r,w=os.pipe()
    with os.fdopen(r) as stream:
        process=type("SyntheticPipe",(),{"stdout":stream})()
        os.write(w,b'{"synthetic":true}\n');os.close(w)
        check("worker_receipt_channel",receive(process,NS()+int(1e9))=={"synthetic":True})
        try:receive(process,NS()+int(1e9))
        except ValueError as exc:check("missing_worker_receipt_rejected","WITHOUT_RECEIPT" in str(exc))
        else:raise AssertionError("MISSING_RECEIPT_ALLOWED")
        try:receive(process,NS()-1)
        except ValueError as exc:check("budget_expiry_rejected","BUDGET_EXHAUSTED" in str(exc))
        else:raise AssertionError("EXPIRED_BUDGET_ALLOWED")
    # Real frozen metadata, artificial cells only: test opposite catalog polarity
    # before canonical alias merging, without reading any real measurement.
    candidates = contracts.ledger()
    selected = [c for c in candidates if c["candidate_use"]["core"] and c["candidate_use"]["selectable_on_App177"]]
    for desired in ("T", "F", "U"):
        raw = {}
        for c in selected:
            state = desired if c["direct_OR_deviation_polarity"]=="POSITIVE" or desired=="U" else {"T":"F","F":"T"}[desired]
            raw[c["atom_id"]] = {"value":{"T":True,"F":False,"U":None}[state], "available":state!="U", "evaluation_status":"OK", "reason":"TOY"}
        projected, atoms = baselines.project_core({"synthetic":raw}, candidates, "SRC-111")
        check("fixed_projection:"+desired, all(contracts.state(c)==desired for c in projected["synthetic"].values()))
    write(dest, {"status":"PASS","version":VERSION,"checks":checks,"fit_calls":0,
        "real_measurements_read":0,"hand_constructed_synthetic_models":True,"module_paths":modules,
        "guard_denials":rejected,"executable":sys.executable,"utc":NOW(),"driver_sha256":sha(__file__)})


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command", choices=["synthetic","run","worker"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--fold")
    parser.add_argument("--output", type=Path)
    args=parser.parse_args()
    if args.command=="synthetic": synthetic(args.path.resolve(), args.output.resolve())
    elif args.command=="run": run(args.path.resolve())
    else: worker(args.path.resolve(), args.fold)
