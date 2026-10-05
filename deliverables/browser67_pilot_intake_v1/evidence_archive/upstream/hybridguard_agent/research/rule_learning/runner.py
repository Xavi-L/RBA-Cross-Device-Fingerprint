"""Single formal orchestration path; R04 issuance permits built-in toys only."""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from .access import FormalFitRequest, FitAuthorizationError, open_formal_fit
from .baselines import adapt_historical_seven, core_view, fixed_model, project_core, single_surface_view, transform_numeric
from .contracts import ledger, read_json, read_jsonl
from .evaluation import evaluate
from .job_manifest import LEARNERS, digest
from .job_runtime import FrozenSnapshot, file_digest, write_json
from .models import RuleModel, load_model, save_model
from .oof import KEYS, aggregate_oof
from .predictor import predict
from .selector import fit


def dump_lines(path, rows):
    with Path(path).open("x") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")


def history_model(access):
    return RuleModel("HISTORICAL_SEVEN", "FIXED", (), (), access.model_binding("NOT_APPLICABLE"), access.view,
        {"status": "FIXED_SAVED_HISTORY_ADAPTER", "train_ids": [], **access.fit_context(),
         "freeze_time": datetime.now(timezone.utc).isoformat()}, constant="NO_ALERT")


def execute_job(context, output):
    """Invoked only with a validated dispatcher ticket, never a public fit flag."""
    j = context.job
    if context.stage == "SYNTHETIC_R04" or not j["fit_job_id"]:
        access = context.train()
    else:
        s = context.snapshot
        access = open_formal_fit(FormalFitRequest(stage=j["authorization_stage"], authorization_record_ref=context.authorization_ref(),
            freeze_manifest_ref="FREEZE_MANIFEST.json#" + s.freeze_digest,
            resource_manifest_ref="RESOURCE_MANIFEST.json#" + s.resource_digest,
            expected_fit_job_ref="expected_fit_jobs.jsonl#" + j["fit_job_id"],
            **{k: j[k] for k in ("protocol_digest", "split_id", "fold_id", "method_id", "operating_point", "source_condition", "input_view")},
            train_membership_ref="SPLIT_MANIFEST.json#" + j["fold_id"] + ":" + j["train_membership_digest"]), context=context)
    if j["input_view"] != "core":
        access = single_surface_view(access, j["input_view"])
    elif access.view["kind"] == "RAW_CORE":
        access = core_view(access, j["source_condition"])
    elif j["source_condition"] != "SRC-111":
        raise ValueError("SOURCE_SUBSET_REQUIRES_RAW_ALIAS_PROJECTION")
    context.event("TRAIN_TRANSFORM_FINISHED", access_operations=access.operations, n=len(access.batch("train").ids))
    if j["method_id"] in LEARNERS:
        result = fit(access, access.batch("train"), j["method_id"], j["operating_point"])
        model = result.model
        write_json(output / "training.json", {"trace": result.trace, "support": result.support,
                   "candidate_manifest": result.candidate_manifest})
    else:
        model = history_model(access) if j["method_id"] == "HISTORICAL_SEVEN" else fixed_model(access, j["method_id"])
    save_model(model, output / "model.json")
    model = context.freeze_model(output / "model.json")
    write_json(output / "MODEL_FREEZE_RECEIPT.json", context.receipt)
    raw_test = context.open_test(model)
    if j["input_view"] != "core":
        test = {oid: transform_numeric(row, model.encoder) for oid, row in raw_test.items()}
    elif access.view["view_id"].startswith("CORE:"):
        test, _ = project_core(raw_test, ledger(), j["source_condition"])
    else:
        test = raw_test
    if j["method_id"] == "HISTORICAL_SEVEN":
        history = context._read(j["history_ref"], "OPEN_SAVED_HISTORY_AFTER_MODEL_FREEZE")
        proofs = context._read(j["history_proof_ref"], "OPEN_HISTORY_INPUT_PROOF")
        verified = [oid for oid in j["outer_test_ids"] if proofs[oid]["status"] == "EXACT_INPUT_AND_METHOD_MATCH"]
        rows = adapt_historical_seven(j["outer_test_ids"], [history[oid] for oid in j["outer_test_ids"]], verified)
        rows = [dict(r, **model.binding, model_id=model.model_id) for r in rows]
    else:
        rows = [predict(model, oid, {"features": test[oid], "view_id": model.view["view_id"]}) for oid in j["outer_test_ids"]]
    for r in rows:
        r.update({k: j[k] for k in KEYS})
    dump_lines(output / "predictions.jsonl", rows)
    context.close_predictions(rows)
    # Reload the saved, closed prediction file before the independent label join.
    predictions = read_jsonl(output / "predictions.jsonl")
    labels = context.evaluation()
    write_json(output / "metrics.json", evaluate(j["outer_test_ids"], predictions, labels,
               evaluation_role="SYNTHETIC_OUTER" if j["data_origin"] == "BUILTIN_SYNTHETIC" else "EXPOSED_RETROSPECTIVE_OUTER"))
    write_json(output / "evaluation_sidecar.json", labels)
    write_json(output / "access_log.json", context.events)
    return {"model_unit_id": j["model_unit_id"], "model_id": model.model_id,
            "state": "FAILED" if model.status == "FAILED" else "EMPTY_MODEL" if model.status == "EMPTY_MODEL" else "COMPLETED",
            "model_status": model.status, "atoms": len(model.atoms), "clauses": len(model.clauses)}


class BudgetLedger:
    """Persisted single-dispatcher budget. Crashed reservations consume their cap."""
    def __init__(self, path, freeze_digest, limits):
        self.path, self.limits = Path(path), copy.deepcopy(limits)
        self.lock = self.path.with_suffix(".lock")
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        self.lock_fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        self.state = read_json(self.path) if self.path.exists() else {
            "freeze_digest": freeze_digest, "limits": limits, "used_fit_jobs": 0,
            "charged_seconds": 0.0, "jobs": {}, "order": []}
        if self.state["freeze_digest"] != freeze_digest or self.state["limits"] != limits:
            self.close()
            raise ValueError("GLOBAL_BUDGET_BINDING_OR_LIMIT_CHANGED")

    def persist(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, self.path)

    def reserve(self, j):
        uid = j["model_unit_id"]
        if uid in self.state["jobs"]:
            raise ValueError("JOB_ALREADY_RESERVED_NO_SILENT_RETRY")
        remaining = self.limits["wall_clock_seconds"] - self.state["charged_seconds"]
        fits = bool(j["fit_job_id"] and not j["reuse_model_unit_id"])
        if remaining <= 0 or (fits and self.state["used_fit_jobs"] >= self.limits["max_fit_jobs"]):
            self.state["jobs"][uid] = {"state": "NOT_RUN_BUDGET_EXHAUSTED"}
            self.persist()
            return None
        cap = min(remaining, max(j["fit_time_limit_seconds"], 0) + 30)
        self.state["used_fit_jobs"] += fits
        self.state["charged_seconds"] += cap
        self.state["jobs"][uid] = {"state": "RUNNING_RESERVED", "reserved_seconds": cap}
        self.state["order"].append(uid)
        self.persist()
        return cap

    def settle(self, j, elapsed, state):
        old = self.state["jobs"][j["model_unit_id"]]
        self.state["charged_seconds"] += min(elapsed, old["reserved_seconds"]) - old["reserved_seconds"]
        old.update(state=state, elapsed_seconds=elapsed)
        self.persist()

    def close(self):
        if getattr(self, "lock_fd", None) is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
            self.lock.unlink()


def failed_rows(job, reason):
    return [{**{k: job[k] for k in (*KEYS, "fold_id", "model_unit_id")}, "opaque_id": oid,
        "model_id": None, "decision": "FAILED", "failure_reason": reason,
        "selected_atoms_available": 0, "selected_atoms_expected": None,
        "clauses_defined": 0, "clauses_expected": None,
        "coverage_expectation": "RECEIPT_WITHOUT_MODEL"} for oid in job["outer_test_ids"]]


def reuse_result(snapshot, job, source_directory, output):
    """Exact SRC-111 saved model/prediction reuse. Model bytes stay unchanged."""
    source = Path(source_directory)
    uid = job["reuse_model_unit_id"]
    source_job = next(j for j in snapshot.models + snapshot.synthetic if j["model_unit_id"] == uid)
    for key in ("train_ids", "outer_test_ids", "method_id", "operating_point", "source_condition", "input_view",
                "fold_id", "split_id", "data_origin", "protocol_digest"):
        if job[key] != source_job[key]:
            raise ValueError("REUSE_NOT_IDENTICAL_JOB:" + key)
    m = load_model(source / "model.json")
    rec = read_json(source / "MODEL_FREEZE_RECEIPT.json")
    if (m.binding["model_unit_id"] != uid or m.binding["freeze_manifest_digest"] != snapshot.freeze_digest
            or m.fit["train_ids"] != job["train_ids"] or file_digest(source / "model.json") != rec["sha256"]):
        raise ValueError("REUSED_MODEL_BINDING_MISMATCH")
    original = read_jsonl(source / "predictions.jsonl")
    if [r["opaque_id"] for r in original] != job["outer_test_ids"] or any(r["model_id"] != m.model_id for r in original):
        raise ValueError("REUSED_PREDICTION_BINDING_MISMATCH")
    log = read_json(source / "access_log.json")
    closed = next(e for e in log if e["event"] == "PREDICTIONS_CLOSED_AND_RECONCILED")
    if closed["predictions_digest"] != digest(original):
        raise ValueError("REUSED_PREDICTION_CLOSURE_MISMATCH")
    rows = [dict(r, **{k: job[k] for k in KEYS}, model_unit_id=job["model_unit_id"],
                 executed_model_unit_id=uid, reused_from=str(source), executed_binding=copy.deepcopy(m.binding)) for r in original]
    dump_lines(output / "predictions.jsonl", rows)
    write_json(output / "REUSE_RECEIPT.json", {"original_receipt": rec, "model_id": m.model_id,
        "source_model_unit_id": uid, "alias_model_unit_id": job["model_unit_id"], "new_fit": False,
        "model_bytes_rewritten": False, "original_prediction_digest": digest(original)})
    return rows, {"model_unit_id": job["model_unit_id"], "model_id": m.model_id,
        "state": "REUSED" if m.status not in ("FAILED", "EMPTY_MODEL") else m.status,
        "model_status": m.status, "atoms": len(m.atoms), "clauses": len(m.clauses)}


def run(snapshot_root, stage, output, budget_path, *, suite="complete", approval=None, approval_digest=None):
    orchestration_start = time.monotonic()
    snapshot = FrozenSnapshot(snapshot_root)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("RUN_OUTPUT_MUST_BE_NEW")
    # Suites and reduced budgets are frozen built-in synthetic scenarios; they
    # cannot supply records, rename real IDs or grant later-stage execution.
    if stage == "SYNTHETIC_R04":
        if approval is not None:
            raise FitAuthorizationError("SYNTHETIC_CAPABILITY_DOES_NOT_ACCEPT_FORMAL_GRANTS")
        suite_spec = snapshot.protocol["synthetic_suites"].get(suite)
        if suite_spec is None:
            raise ValueError("UNREGISTERED_SYNTHETIC_SUITE")
        jobs = [j for j in snapshot.synthetic if j["job_id"] in suite_spec["job_ids"]]
    else:
        if approval is None or approval_digest is None:
            raise FitAuthorizationError("R04_REAL_DATA_FIT_NOT_AUTHORIZED")
        snapshot.bind_formal_authorization(approval, approval_digest)
        if snapshot._formal_grant["stage"] != stage or suite != "complete":
            raise FitAuthorizationError("FORMAL_STAGE_OR_SUITE_NOT_APPROVED")
        if Path(budget_path).resolve() != Path(snapshot._formal_grant["budget_ledger_ref"]).resolve():
            raise FitAuthorizationError("FORMAL_SHARED_BUDGET_LEDGER_NOT_APPROVED")
        jobs = [j for j in snapshot.models if j["authorization_stage"] == stage]
        suite_spec = {"budget": snapshot.protocol["budget"]}
    jobs.sort(key=lambda j: (j["priority"], j["job_id"]))
    for j in jobs:
        snapshot.context(j["job_id"], stage).authorize()
    output.mkdir(parents=True)
    write_json(output / "STARTUP.json", snapshot.startup_audit)
    budget = BudgetLedger(budget_path, snapshot.freeze_digest, suite_spec["budget"])
    predictions, receipts, metadata = [], {}, {}
    charged_before_invocation = budget.state["charged_seconds"]
    try:
        for j in jobs:
            budget.state["charged_seconds"] = charged_before_invocation + time.monotonic() - orchestration_start
            cap = budget.reserve(j)
            dest = output / "jobs" / j["model_unit_id"]
            dest.mkdir(parents=True)
            if cap is None:
                rec = {"model_unit_id": j["model_unit_id"], "model_id": None, "state": "NOT_RUN_BUDGET_EXHAUSTED"}
                rows = failed_rows(j, rec["state"])
            else:
                if j["reuse_model_unit_id"]:
                    start = time.monotonic()
                    try:
                        prior = budget.state["jobs"].get(j["reuse_model_unit_id"], {})
                        if not prior.get("artifact_directory"):
                            raise ValueError("MISSING_SRC111_SOURCE_JOB_KEEP_EXPECTED_UNITS")
                        rows, rec = reuse_result(snapshot, j, prior["artifact_directory"], dest)
                    except (ValueError, OSError) as exc:
                        rec = {"model_unit_id": j["model_unit_id"], "model_id": None, "state": "NOT_RUN_MISSING_REUSE_SOURCE", "reason": str(exc)}
                        rows = failed_rows(j, rec["state"])
                    budget.settle(j, time.monotonic() - start, rec["state"])
                    predictions.extend(rows)
                    receipts[j["model_unit_id"]] = rec
                    continue
                ticket = {"job_id": j["job_id"], "job_digest": digest(j), "freeze_digest": snapshot.freeze_digest,
                          "parent_pid": os.getpid(), "nonce": uuid.uuid4().hex, "stage": stage, "cap_seconds": cap,
                          "approval": str(Path(approval).resolve()) if approval else None, "approval_digest": approval_digest}
                write_json(dest / "dispatch_ticket.json", ticket)
                cwd = dest / "empty_cwd"
                cwd.mkdir()
                cmd = [sys.executable, "-B", "-I", "-S", str(snapshot.root / "launch.py"), "worker", str(snapshot.root),
                       str(dest), str(dest / "dispatch_ticket.json")]
                start = time.monotonic()
                try:
                    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=cap, check=False)
                    (dest / "worker_stdout.txt").write_text(done.stdout)
                    (dest / "worker_stderr.txt").write_text(done.stderr)
                    if done.returncode:
                        raise RuntimeError("WORKER_FAILED:" + str(done.returncode))
                    rec = read_json(dest / "receipt.json")
                    rows = read_jsonl(dest / "predictions.jsonl")
                    metadata.update(read_json(dest / "evaluation_sidecar.json"))
                except (subprocess.TimeoutExpired, RuntimeError) as exc:
                    rec = {"model_unit_id": j["model_unit_id"], "model_id": None,
                           "state": "FAILED", "execution_status": "WORKER_WALL_LIMIT" if isinstance(exc, subprocess.TimeoutExpired) else "WORKER_ERROR",
                           "reason": type(exc).__name__ + ":" + str(exc)}
                    rows = failed_rows(j, rec["state"])
                budget.settle(j, time.monotonic() - start, rec["state"])
                budget.state["jobs"][j["model_unit_id"]]["artifact_directory"] = str(dest)
                budget.persist()
            predictions.extend(rows)
            receipts[j["model_unit_id"]] = rec
        # Global closure precedes evaluation of missing/failed/not-run units too.
        dump_lines(output / "predictions.jsonl", predictions)
        write_json(output / "PREDICTION_CLOSURE.json", {"expected": sum(len(j["outer_test_ids"]) for j in jobs),
                   "saved": len(predictions), "digest": digest(predictions), "closed_at": datetime.now(timezone.utc).isoformat()})
        data = read_json(snapshot.check_resource(snapshot.protocol["data_indices"]["BUILTIN_SYNTHETIC" if stage == "SYNTHETIC_R04" else "R02_FIXED_CACHE"]))
        for oid in sorted({i for j in jobs for i in j["outer_test_ids"]}):
            metadata[oid] = read_json(snapshot.check_resource(data[oid]["evaluation"]))
        write_json(output / "model_receipts.json", receipts)
        write_json(output / "OOF.json", aggregate_oof(jobs, predictions, receipts, metadata))
        budget.state["charged_seconds"] = charged_before_invocation + time.monotonic() - orchestration_start
        budget.persist()
        write_json(output / "SUMMARY.json", {"stage": stage, "suite": suite, "jobs": len(jobs),
                   "predictions": len(predictions),
                   "real_fits": 0 if stage == "SYNTHETIC_R04" else budget.state["used_fit_jobs"],
                   "real_predictions": 0 if stage == "SYNTHETIC_R04" else sum(r.get("model_id") is not None for r in predictions),
                   "budget": budget.state, "states": [r["state"] for r in receipts.values()]})
    finally:
        budget.close()


def worker(root, output, ticket_path):
    ticket = read_json(ticket_path)
    if ticket["parent_pid"] != os.getppid() or not ticket["nonce"]:
        raise FitAuthorizationError("WORKER_REQUIRES_LIVE_DISPATCHER_TICKET")
    snapshot = FrozenSnapshot(root)
    if ticket["stage"] != "SYNTHETIC_R04":
        if not ticket.get("approval") or not ticket.get("approval_digest"):
            raise FitAuthorizationError("WORKER_REAL_GRANT_REQUIRED")
        snapshot.bind_formal_authorization(ticket["approval"], ticket["approval_digest"])
    context = snapshot.context(ticket["job_id"], ticket["stage"])
    if digest(context.job) != ticket["job_digest"] or snapshot.freeze_digest != ticket["freeze_digest"]:
        raise FitAuthorizationError("DISPATCH_TICKET_BINDING_MISMATCH")
    write_json(Path(output) / "WORKER_STARTUP.json", snapshot.startup_audit)
    receipt = execute_job(context, Path(output))
    write_json(Path(output) / "receipt.json", receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "worker", "verify", "acceptance"))
    parser.add_argument("root")
    parser.add_argument("output", nargs="?")
    parser.add_argument("extra", nargs="?")
    parser.add_argument("--suite", default="complete")
    parser.add_argument("--stage", default="SYNTHETIC_R04")
    parser.add_argument("--approval")
    parser.add_argument("--approval-digest")
    args = parser.parse_args()
    if args.command == "acceptance":
        from .freeze_acceptance import validate
        validate(args.output)
    elif args.command == "verify":
        print(json.dumps(FrozenSnapshot(args.root).startup_audit))
    elif args.command == "worker":
        worker(args.root, args.output, args.extra)
    else:
        run(args.root, args.stage, args.output, args.extra, suite=args.suite,
            approval=args.approval, approval_digest=args.approval_digest)


if __name__ == "__main__":
    main()
