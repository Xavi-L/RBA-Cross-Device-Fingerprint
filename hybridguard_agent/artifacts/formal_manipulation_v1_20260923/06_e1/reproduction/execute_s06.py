"""S06 process boundary and IO audit; algorithms come only from frozen r1.

predict executes the unchanged frozen runner once. evaluate starts separately,
accounts closed files before enabling fact reads, then calls the frozen join.
No monkeypatch, fallback, retry, predicate, decision or metric implementation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import sysconfig
import traceback


def read(path):
    return json.loads(Path(path).read_text())


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--binding", type=Path, required=True)
    p.add_argument("--phase", choices=("predict", "evaluate"), required=True)
    args = p.parse_args()
    binding = read(args.binding)
    out, snapshot, root = (Path(binding[k]).resolve() for k in ("step_output", "snapshot", "runtime_source_root"))
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    assert not any(n.startswith("hybridguard_agent") for n in sys.modules)
    assert "PYTHONPATH" not in os.environ and "PYTHONHOME" not in os.environ
    assert Path.cwd() == Path(binding["cwd"]) and not list(Path.cwd().iterdir())
    initial_sys_path = list(sys.path)
    sys.path.insert(0, str(root))
    from hybridguard_agent.research.manipulation_eval.runtime_resources import preflight, resource_paths, MANIFEST
    resource_set = {root / p for p in resource_paths()} | {root / MANIFEST}
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    controls = {args.binding.resolve(), Path(binding["job"]), out / "run_manifest.json", out / "AUTHORIZATION.json",
                snapshot / "protocol.json", Path(binding["static_plan"])}
    facts = {snapshot / "evaluation/evaluation_index.jsonl", snapshot / "evaluation/S01/triplet_registry.jsonl",
             snapshot / "evaluation/task_denominators.json"}
    state = {"worker_depth": 0, "facts_enabled": False}
    reads, writes, calls, methods, payload_keys = Counter(), Counter(), Counter(), Counter(), Counter()
    violations = []
    code_keys = {
        ("hybridguard_agent.research.manipulation_eval.runner", "worker"): "worker",
        ("hybridguard_agent.evidence.paired244", "build_paired_evidence"): "evidence",
        ("hybridguard_agent.rules.paired244", "execute_paired_rules"): "original_rules",
        ("hybridguard_agent.adapters.paired244_catalog", "runtime_cards"): "runtime_cards",
        ("hybridguard_agent.verification.paired244", "verify_paired_output"): "original_verifier",
        ("hybridguard_agent.research.manipulation_eval.policy", "build_events"): "risk_events",
        ("hybridguard_agent.research.manipulation_eval.policy", "decide"): "risk_policy",
        ("hybridguard_agent.research.manipulation_eval.verification", "verify_policy_output"): "risk_verifier",
        ("hybridguard_agent.research.manipulation_eval.provenance_revision", "evaluate_contract"): "forbidden_probe",
        ("hybridguard_agent.research.manipulation_eval.provenance_revision", "_relation_probe"): "forbidden_probe",
    }

    def audit(event, values):
        if event != "open" or not isinstance(values[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(values[0])).resolve()
        flags = values[2] or 0
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        side = "worker" if state["worker_depth"] else args.phase
        if writing:
            ok = out in path.parents and side != "worker"
            writes[(str(path), side)] += 1
        elif root in path.parents:
            ok = path.suffix in {".py", ".pyc"} or path in resource_set
        elif stdlib in path.parents:
            ok = True
        elif side == "worker":
            ok = False
        elif path in controls:
            ok = True
        elif args.phase == "predict":
            ok = path == Path(binding["input"])
        else:
            ok = ((out / "prediction") in path.parents or
                  (state["facts_enabled"] and (path in facts or (out / "evaluation") in path.parents)))
        if not writing and not (stdlib in path.parents) and path.suffix not in {".py", ".pyc"}:
            reads[(str(path), side)] += 1
        if not ok:
            violations.append({"path": str(path), "side": side, "writing": writing})
            raise RuntimeError("S06 IO boundary violation: " + str(path))

    sys.addaudithook(audit)
    job_data = Path(binding["job"]).read_bytes()
    assert hashlib.sha256(job_data).hexdigest() == binding["job_sha256"], "Job binding changed"
    job = json.loads(job_data)
    plan = read(binding["static_plan"])
    protocol = read(snapshot / "protocol.json")
    assert job["protocol_digest"] == protocol["protocol_digest"] == binding["protocol_digest"]
    assert protocol["freeze_revision"] == binding["freeze_revision"] == "formal-manipulation-freeze-r1"
    assert job["expected_units"] == plan["expected_units"] and job["variants"] == plan["variants"]
    assert job["freeze"] == {"status": "FROZEN", "protocol_version": protocol["protocol_version"], "authorized_execution_step": "S06"}
    precheck = preflight(root=root, require_manifest=True, config_dir=binding["config_dir"], policy_path=binding["policy_path"])
    status = "STARTED"
    started = now()
    receipt = None
    worker_argument_names = None

    def profile(frame, event, result):
        nonlocal worker_argument_names
        key = code_keys.get((frame.f_globals.get("__name__"), frame.f_code.co_name))
        if not key:
            return
        if event == "call":
            assert args.phase == "predict" and key != "forbidden_probe", "Evaluation/probe attempted detector work"
            assert root in Path(frame.f_code.co_filename).resolve().parents, "Runtime code outside snapshot copy"
            calls[key] += 1
            if key == "worker":
                state["worker_depth"] += 1
                methods[frame.f_locals["method"]] += 1
                payload_keys[tuple(sorted(frame.f_locals["payload"]))] += 1
                worker_argument_names = list(frame.f_code.co_varnames[:frame.f_code.co_argcount + frame.f_code.co_kwonlyargcount])
        elif event == "return" and key == "worker":
            state["worker_depth"] -= 1
            ordinal = calls["worker"] - 1
            unit = job["expected_units"][ordinal]
            row = {"ordinal": ordinal + 1, **unit, "attempt": 1, "returned_at": now(),
                   "execution_status": result.get("execution_status") if isinstance(result, dict) else "TECHNICAL_EXCEPTION_OUTSIDE_UNIT_RESULT",
                   "decision": result.get("risk", {}).get("decision") if isinstance(result, dict) else None}
            receipt.write(json.dumps(row, allow_nan=False) + "\n")
            receipt.flush()

    try:
        sys.setprofile(profile)
        if args.phase == "predict":
            from hybridguard_agent.research.manipulation_eval.contract import load_contract
            from hybridguard_agent.research.manipulation_eval.runner import run_predictions, validate_protocol
            contract = load_contract(contract_version=job["contract_version"], config_dir=binding["config_dir"], policy_path=binding["policy_path"])
            validate_protocol(job, contract)
            envelope = read(out / "run_manifest.json")
            assert envelope["status"] == "PREPARED" and not (out / "prediction").exists(), "No retry or overwrite"
            envelope.update(status="PREDICTING", prediction_started_at=started)
            save(out / "run_manifest.json", envelope)
            receipt = (out / "UNIT_EXECUTION_RECEIPTS.jsonl").open("x")
            result = run_predictions(input_path=binding["input"], protocol=job, contract=contract, output=out / "prediction")
            assert result["status"] == "PREDICTIONS_CLOSED" and result["prediction_count"] == len(job["expected_units"]) == calls["worker"]
            assert result["expected_units"] == job["expected_units"]
            envelope.update(status="PREDICTIONS_CLOSED", prediction_completed_at=result["completed_at"], detector_calls=calls["worker"],
                            prediction_count=result["prediction_count"], failure_count=result["failure_count"], facts_joined=False)
            save(out / "run_manifest.json", envelope)
        else:
            from hybridguard_agent.research.manipulation_eval.evaluation import load_closed_predictions, evaluate_saved
            # This finishes ALL saved-table accounting before facts become readable.
            closed, predictions = load_closed_predictions(out / "prediction")
            assert closed["expected_units"] == job["expected_units"] and closed["variants"] == job["variants"]
            assert closed["protocol_digest"] == binding["protocol_digest"] and closed["run_id"] == binding["run_id"]
            actual = [(r["opaque_id"], r["variant_id"]) for r in predictions]
            expected = [(r["opaque_id"], r["variant_id"]) for r in job["expected_units"]]
            assert actual == expected and len(actual) == len(set(actual)) == 432
            closure_time = now()
            save(out / "PREDICTION_CLOSURE.json", {"status": "PASS", "at": closure_time, "run_id": binding["run_id"],
                 "protocol_digest": binding["protocol_digest"], "job_sha256": binding["job_sha256"], "expected_units": len(expected),
                 "actual_units": len(actual), "unique_units": len(set(actual)), "ordered_exact_match": True,
                 "complete_rule_events": closed["rule_event_count"], "runtime_failure_abstention_tables_complete": True,
                 "facts_read_before_accounting": False, "files": [{"path": str(p), "bytes": p.stat().st_size} for p in sorted((out / "prediction").iterdir()) if p.is_file()]})
            state["facts_enabled"] = True
            result = evaluate_saved(prediction_dir=out / "prediction", index_path=snapshot / "evaluation/evaluation_index.jsonl",
                                    triplets_path=snapshot / "evaluation/S01/triplet_registry.jsonl", output=out / "evaluation")
            # Fixed task-member IDs, not just denominator totals, must agree.
            denominators = read(snapshot / "evaluation/task_denominators.json")
            joined = [json.loads(line) for line in (out / "evaluation/evaluation_joined.jsonl").read_text().splitlines()]
            for variant in job["variants"]:
                rows = [r for r in joined if r["variant_id"] == variant["variant_id"]]
                actual_sets = {"positive": {r["opaque_id"] for r in rows if r["evaluation_label"] == "POSITIVE"},
                               "clean_pre": {r["opaque_id"] for r in rows if r["evaluation"]["admission_fact"]["eligible_pre_control"]},
                               "clean_post": {r["opaque_id"] for r in rows if r["evaluation"]["admission_fact"]["eligible_post_control"]},
                               "control_mid": {r["opaque_id"] for r in rows if r["evaluation"]["admission_fact"]["eligible_temporal_control"] and r["evaluation"]["phase"] == "control_mid"}}
                assert all(ids == set(denominators[k]["members"]) for k, ids in actual_sets.items())
            envelope = read(out / "run_manifest.json")
            envelope.update(status="EVALUATION_CLOSED", facts_joined=True, prediction_closure_at=closure_time,
                            evaluation_process_started_at=started, facts_join_started_at=closure_time,
                            evaluation_completed_at=now(), evaluation_detector_calls=sum(calls.values()))
            save(out / "run_manifest.json", envelope)
        status = "PASS"
    except Exception as exc:
        status = "TECHNICAL_EXCEPTION"
        save(out / (args.phase.upper() + "_TECHNICAL_EXCEPTION.json"), {"status": status, "at": now(), "type": type(exc).__name__,
             "message": str(exc), "worker_calls": calls["worker"], "automatic_retry": False})
        raise
    finally:
        sys.setprofile(None)
        if receipt:
            receipt.close()
        modules = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                   if name.startswith("hybridguard_agent") and getattr(module, "__file__", None)}
        module_paths_valid = all(root in Path(path).parents for path in modules.values())
        audit_record = {"status": status, "phase": args.phase, "started_at": started, "finished_at": now(),
            "run_id": binding["run_id"], "protocol_digest": binding["protocol_digest"], "freeze_revision": binding["freeze_revision"], "job_sha256": binding["job_sha256"],
            "runtime_source_root": str(root), "config_dir": binding["config_dir"], "policy_path": binding["policy_path"],
            "orchestration_source": str(Path(__file__).resolve()), "orchestration_scope": "IO boundary/launch/accounting only; no algorithm replacement",
            "module_files": modules, "all_algorithm_modules_from_snapshot_copy": module_paths_valid,
            "initial_sys_path": initial_sys_path, "actual_sys_path": sys.path, "cwd": str(Path.cwd()), "python": sys.version,
            "interpreter_flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site, "dont_write_bytecode": sys.dont_write_bytecode},
            "PYTHONPATH": os.environ.get("PYTHONPATH"), "preflight": precheck, "call_counts": dict(calls), "worker_methods": dict(methods),
            "worker_argument_names": worker_argument_names, "worker_payload_keysets": [{"keys": list(k), "count": n} for k, n in payload_keys.items()],
            "read_paths": [{"path": path, "side": side, "count": count} for (path, side), count in sorted(reads.items())],
            "write_paths": [{"path": path, "side": side, "count": count} for (path, side), count in sorted(writes.items())],
            "boundary_violations": violations, "facts_enabled": state["facts_enabled"], "LLM_calls": 0, "retry_count": 0}
        save(out / (args.phase.upper() + "_PROCESS_AUDIT.json"), audit_record)
        assert module_paths_valid and not violations, "Execution boundary failed; retain outputs and stop"
    print(json.dumps({"phase": args.phase, "status": status, "worker_calls": calls["worker"], "facts_enabled": state["facts_enabled"]}))


if __name__ == "__main__":
    main()
