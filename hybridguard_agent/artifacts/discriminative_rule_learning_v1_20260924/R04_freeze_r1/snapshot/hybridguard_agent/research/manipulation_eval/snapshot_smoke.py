"""Isolated SYNTHETIC-only S05-R packaging smoke; no real input loader.

The parent copies only frozen_sources. Each child starts with -I -B -S from an
empty cwd, loads this driver from that copy, and guards research-resource IO.
"""
from collections import Counter
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import sysconfig
import tempfile


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def child_main(root, output, mode, removed, bootstrap):
    root, out = Path(root).resolve(), Path(output).resolve()
    from hybridguard_agent.research.manipulation_eval.runtime_resources import (
        MANIFEST, ROLE, POLICY, SOURCE_FILES, ResourcePreflightError, preflight, resource_paths,
    )
    allowed = {root / p for p in resource_paths()} | {root / MANIFEST}
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    reads, violations, calls = [], [], Counter()
    state = {"phase": "SETUP", "case": None}
    input_sentinel = out / "NEVER_READ_REAL_INPUT.jsonl"

    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        flags = args[2] or 0
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing:
            ok = out in path.parents
        else:
            if root in path.parents:
                ok = path.suffix in {".py", ".pyc"} or path in allowed
                if path.suffix not in {".py", ".pyc"}:
                    reads.append({"path": str(path), "relative_path": str(path.relative_to(root)), **state})
            else:
                ok = stdlib in path.parents or out in path.parents
            if path == input_sentinel:
                ok = False
        if not ok:
            violations.append({"path": str(path), "writing": writing, **state})
            raise AssertionError("Research IO outside isolated snapshot/test output: " + str(path))

    # No subprocess inherits modules; this assertion is made before any local import.
    need(not bootstrap["preexisting_research_modules"], "Leaked modules at child bootstrap")
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "Missing isolated interpreter flags")
    need("PYTHONPATH" not in os.environ and "PYTHONHOME" not in os.environ, "Inherited Python search path")
    need(Path.cwd() != root and not list(Path.cwd().iterdir()), "Child cwd must start empty")
    sys.addaudithook(audit)

    def profile(frame, event, arg):
        if event != "call":
            return
        name = frame.f_code.co_name
        filename = frame.f_code.co_filename
        if filename.startswith(str(root) + os.sep):
            rel = str(Path(filename).relative_to(root))
            if rel == "hybridguard_agent/research/manipulation_eval/snapshot_smoke.py":
                return  # Instrument the execution chain, not this counter's iteration.
            calls[rel + "::" + name] += 1
            need(name not in {"evaluate_contract", "_relation_probe"}, "Single-relation probe is not the full chain")

    sys.setprofile(profile)
    state["phase"] = "PREFLIGHT"
    results, blocked = [], []
    if mode == "normal":
        precheck = preflight(root=root, require_manifest=True, config_dir=root / ROLE, policy_path=root / POLICY / "decision_policy.json")
        state["phase"] = "IMPORT_AND_CONTRACT"
        from hybridguard_agent.research.manipulation_eval.contract import load_contract, VERSION
        from hybridguard_agent.research.manipulation_eval.runner import worker
        from hybridguard_agent.research.manipulation_eval.synthetic import fixtures
        contract = load_contract(contract_version=VERSION, config_dir=root / ROLE, policy_path=root / POLICY / "decision_policy.json")
        cases = [f for f in fixtures() if f["fixture_id"] in {"consistent", "single_family_duplicate_rules"}]
        need(len(cases) == 2 and all(f["fixture_kind"] == "SYNTHETIC" for f in cases), "Synthetic fixture selection")
        # These expected decisions are inherited hand-declarations, before runtime.
        save(out / "SYNTHETIC_CASES.json", {"fixture_kind": "SYNTHETIC", "cases": cases,
             "input_construction": "Hand-declared Android 14 / ModelX / Adreno 650; conflict changes only App UA Android 14 to 15",
             "not_S06_units": True})
        required_calls = {
            "hybridguard_agent/evidence/paired244.py::build_paired_evidence",
            "hybridguard_agent/rules/paired244.py::execute_paired_rules",
            "hybridguard_agent/adapters/paired244_catalog.py::runtime_cards",
            "hybridguard_agent/verification/paired244.py::verify_paired_output",
            "hybridguard_agent/research/manipulation_eval/policy.py::build_events",
            "hybridguard_agent/research/manipulation_eval/policy.py::decide",
            "hybridguard_agent/research/manipulation_eval/verification.py::verify_policy_output",
        }
        for method in ("final_v3_v2", "legacy19_v2"):
            for fixture in cases:
                state.update(phase="FULL_CHAIN", case=method + ":" + fixture["fixture_id"])
                before = calls.copy()
                result = worker(fixture["payload"], contract=contract, condition_id="SRC-111", input_view="App177", method=method)
                delta = calls - before
                record = {"fixture_kind": "SYNTHETIC", "case_id": state["case"], "method": method, "input_view": "App177", "condition_id": "SRC-111",
                          "expected_decision": fixture["expected_decision"], "expected_score": fixture["expected_score"], "result": result,
                          "full_chain_call_counts": {k: delta[k] for k in sorted(required_calls)}}
                results.append(record)
                # Save failures as evidence too, before any assertion can abort.
                save(out / "SYNTHETIC_RESULTS.json", results)
                need(result["execution_status"] == "COMPLETED", "Synthetic unit FAILED: " + str(result["failure"]))
                need(result["risk"]["decision"] == fixture["expected_decision"] and result["risk"]["alert_score"] == fixture["expected_score"], "Predeclared synthetic result differs")
                need(result["original_runtime"]["verification"]["valid"] and result["verification"]["valid"], "Verifier did not accept")
                need(all(delta[k] > 0 for k in required_calls), "Incomplete execution chain")
                rows = result["original_runtime"]["rule_execution"]["rule_results"]
                need(len(rows) == (len(contract["catalog"]["rules"]) if method == "final_v3_v2" else 19), "Original rule execution incomplete")
                sources = {r["relative_path"] for r in reads if r["phase"] == "FULL_CHAIN" and r["case"] == state["case"]}
                need(set(SOURCE_FILES if method == "final_v3_v2" else SOURCE_FILES[:1]) <= sources, "runtime_cards did not load its required source documents")
    elif mode == "missing":
        need(removed in SOURCE_FILES and not (root / removed).exists(), "Omission fixture missing")
        precheck = None
        # Deliberately incomplete control-plane job: preflight must run first.
        # This is not authorization, a runnable S06 job, or a real input file.
        job = {"execution_scope": "FROZEN_FORMAL_EVALUATION", "test_purpose": "SYNTHETIC_STARTUP_REJECTION_ONLY"}
        job_path = out / "SYNTHETIC_REJECT_JOB.json"
        save(job_path, job)
        cli = root / "hybridguard_agent/scripts/run_formal_manipulation_eval.py"
        cli_out, api_out = out / "MUST_NOT_CREATE_CLI", out / "MUST_NOT_CREATE_API"
        sys.argv = [str(cli), "predict", "--inputs", str(input_sentinel), "--protocol", str(job_path), "--config-dir", str(root / ROLE),
                    "--policy", str(root / POLICY / "decision_policy.json"), "--contract-version", "formal-manipulation-relation-risk-attribution-v2", "--out", str(cli_out)]
        for entry in ("CLI", "API"):
            state.update(phase="MISSING_PREFLIGHT_" + entry, case=removed)
            try:
                if entry == "CLI":
                    runpy.run_path(str(cli), run_name="__main__")
                else:
                    from hybridguard_agent.research.manipulation_eval.runner import run_predictions
                    run_predictions(input_path=input_sentinel, protocol=job, contract=None, output=api_out)
            except ResourcePreflightError as exc:
                need(exc.code == "MISSING_RUNTIME_RESOURCE" and exc.paths == [removed], "Wrong missing-resource diagnosis")
                blocked.append({"entrypoint": entry, "code": exc.code, "paths": exc.paths, "message": str(exc), "rejected_before_input_and_output": True})
            else:
                raise AssertionError("Missing resource did not reject startup")
        need(not cli_out.exists() and not api_out.exists() and not input_sentinel.exists(), "Startup touched unit input/output")
        need(not any(k.endswith("::worker") for k in tuple(calls)), "Omission regression executed a unit")
    else:
        raise ValueError("Unknown synthetic test mode")
    sys.setprofile(None)
    state.update(phase="REPORT", case=None)
    modules = {n: str(Path(m.__file__).resolve()) for n, m in sys.modules.items() if n.startswith("hybridguard_agent") and getattr(m, "__file__", None)}
    need(all(root in Path(p).parents for p in modules.values()), "Module came from outside snapshot")
    need(not violations, "Resource access violation")
    record = {"status": "PASS", "fixture_kind": "SYNTHETIC", "mode": mode, "removed_resource": removed or None,
              "snapshot_copy": str(root), "cwd": str(Path.cwd()), "python_executable": sys.executable,
              "isolated_flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site, "dont_write_bytecode": sys.dont_write_bytecode},
              "bootstrap": bootstrap, "sys_path": sys.path, "PYTHONPATH": os.environ.get("PYTHONPATH"),
              "module_files": modules, "resource_reads": reads, "guard_violations": violations,
              "startup_preflight": precheck, "omission_rejections": blocked,
              "synthetic_unit_count": len(results), "real_prediction_count": 0, "S06_units": 0,
              "call_counts": dict(sorted(calls.items())), "single_relation_probe_calls": 0, "LLM_calls": 0,
              "results": [{"case_id": r["case_id"], "status": r["result"]["execution_status"], "decision": r["result"]["risk"]["decision"],
                           "score": r["result"]["risk"]["alert_score"], "original_verifier": r["result"]["original_runtime"]["verification"]["valid"],
                           "risk_verifier": r["result"]["verification"]["valid"], "full_chain_call_counts": r["full_chain_call_counts"]} for r in results]}
    save(out / "ISOLATION_AND_CHAIN.json", record)
    print(json.dumps({k: record[k] for k in ("status", "fixture_kind", "mode", "synthetic_unit_count", "real_prediction_count", "S06_units")}))


def run_isolated(*, snapshot, output):
    """Parent never imports a detector; each temporary child starts afresh."""
    snapshot, out = Path(snapshot).resolve(), Path(output).resolve()
    need(not out.exists() and out != snapshot and snapshot not in out.parents and out not in snapshot.parents, "Use a new independent synthetic output directory")
    from hybridguard_agent.research.manipulation_eval.runtime_resources import SOURCE_FILES
    from hybridguard_agent.research.manipulation_eval.freeze_revision import verify_manifest
    manifest, protocol = verify_manifest(snapshot)
    out.mkdir(parents=True)
    save(out / "SYNTHETIC_TEST_PLAN.json", {"fixture_kind": "SYNTHETIC", "freeze_revision": protocol["freeze_revision"],
         "protocol_digest": protocol["protocol_digest"], "normal_expected": {m: {"consistent": ["NO_ALERT", 0], "single_family_duplicate_rules": ["MANIPULATION_ALERT", 1]}
              for m in ("final_v3_v2", "legacy19_v2")},
         "missing_resources": list(SOURCE_FILES), "missing_expected": "MISSING_RUNTIME_RESOURCE in CLI and API before samples/output/worker",
         "real_predictions": 0, "S06_units": 0, "child_flags": ["-I", "-B", "-S"]})
    bootstrap = ("import sys,os,json; b={'initial_sys_path':list(sys.path),'preexisting_research_modules':[n for n in sys.modules if n.startswith('hybridguard_agent')]};"
                 "sys.path.insert(0,sys.argv[1]); from hybridguard_agent.research.manipulation_eval.snapshot_smoke import child_main;"
                 "child_main(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],b)")
    summaries = []
    for name, mode, removed in [("normal", "normal", "")] + [("missing_" + Path(p).stem, "missing", p) for p in SOURCE_FILES]:
        with tempfile.TemporaryDirectory(prefix="hybridguard-s05r-synthetic-") as td:
            temp = Path(td).resolve()
            copied, cwd, child_out = temp / "snapshot", temp / "empty-cwd", temp / "SYNTHETIC"
            shutil.copytree(snapshot / "frozen_sources", copied)
            cwd.mkdir()
            child_out.mkdir()
            # Exact finite copy check; not a workspace scan or new material hash.
            for entry in manifest["bound_files"]:
                if entry["path"].startswith("frozen_sources/"):
                    rel = Path(entry["path"]).relative_to("frozen_sources")
                    need((copied / rel).read_bytes() == (snapshot / entry["path"]).read_bytes(), "Temporary snapshot copy differs")
            if removed:
                (copied / removed).unlink()
            env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            command = [sys.executable, "-I", "-B", "-S", "-c", bootstrap, str(copied), str(child_out), mode, removed]
            result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=45)
            dest = out / name
            shutil.copytree(child_out, dest)
            save(dest / "SUBPROCESS.json", {"command": command, "cwd": str(cwd), "returncode": result.returncode,
                 "source_snapshot": str(snapshot), "copied_snapshot_bytes_match": True, "PYTHONPATH_removed": True,
                 "copied_only_frozen_sources": True, "temporary_directory_deleted_after_test": True})
            (dest / "stdout.txt").write_text(result.stdout)
            (dest / "stderr.txt").write_text(result.stderr)
            need(result.returncode == 0, "Isolated synthetic child failed; inspect " + str(dest / "stderr.txt"))
            summaries.append(json.loads((dest / "ISOLATION_AND_CHAIN.json").read_text()))
    summary = {"status": "PASS", "scope": "INDEPENDENT_SNAPSHOT_SYNTHETIC_FULL_CHAIN_AND_STARTUP_OMISSION", "fixture_kind": "SYNTHETIC",
               "freeze_revision": protocol["freeze_revision"], "protocol_digest": protocol["protocol_digest"],
               "independent_subprocess_count": len(summaries), "synthetic_unit_count": sum(r["synthetic_unit_count"] for r in summaries),
               "omission_resource_cases": len([r for r in summaries if r["mode"] == "missing"]),
               "startup_rejection_count": sum(len(r["omission_rejections"]) for r in summaries),
               "normal_results": summaries[0]["results"], "all_modules_and_research_resources_from_copied_snapshot": True,
               "no_main_workspace_fallback": True, "real_predictions": 0, "S06_units": 0, "LLM_calls": 0,
               "metrics": "NOT_EVALUATED", "not_performance_or_full_input_coverage_proof": True}
    save(out / "SYNTHETIC_SMOKE_VALIDATION.json", summary)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run_isolated(snapshot=args.snapshot, output=args.output), ensure_ascii=False, indent=2))
