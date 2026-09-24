"""S06 authorization/control-plane preparation only; never import a worker."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BASELINE = "f3f934d0f93d72e16b3d97e4e390796065e5fff8"
REVISION = "formal-manipulation-freeze-r1"
DIGEST = "9a6cb92a5d973a42d230305e176ab9ef824bca2e8aae045dafed515ce61c0f19"


def read(path):
    return json.loads(Path(path).read_text())


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    snapshot, out = a.snapshot.resolve(), a.output.resolve()
    repo = snapshot.parents[3]
    assert not (out / "RUNNABLE_JOB.json").exists(), "Never replace a prepared or executed job"
    assert not (out / "prediction").exists() and not (out / "evaluation").exists()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    assert head == BASELINE, "Review baseline conflict"
    sys.path.insert(0, str(snapshot / "frozen_sources"))
    from hybridguard_agent.research.manipulation_eval.freeze_revision import validate_revision
    validation = validate_revision(snapshot, config_dir=repo / "hybridguard_agent/config/formal_manipulation_protocol_v2_r1", parent=snapshot.parent / "05_freeze")
    assert validation["status"] == "PASS" and validation["protocol_digest"] == DIGEST and validation["freeze_revision"] == REVISION
    protocol, manifest = read(snapshot / "protocol.json"), read(snapshot / "FREEZE_MANIFEST.json")
    plan = read(snapshot / "step_execution_plans/S06.json")
    expected = [{k: r[k] for k in ("opaque_id", "variant_id", "input_line")} for r in
                map(json.loads, (snapshot / "expected_units.jsonl").read_text().splitlines()) if r["first_execution_step"] == "S06"]
    assert plan["not_a_runnable_S04_job"] is True and plan["status"] == "PLANNED_NOT_AUTHORIZED"
    assert expected == plan["expected_units"] and len(expected) == 432
    assert len({(r["opaque_id"], r["variant_id"]) for r in expected}) == len(expected)
    assert len({r["opaque_id"] for r in expected}) == 216
    assert Counter(r["variant_id"] for r in expected) == {m + ":App177:SRC-111": 216 for m in ("final_v3_v2", "legacy19_v2")}
    assert all(v["input_view"] == "App177" and v["condition_id"] == "SRC-111" for v in plan["variants"])
    assert {v["method"] for v in plan["variants"]} == {"final_v3_v2", "legacy19_v2"}
    assert protocol["execution_authorization"]["formal_execution_authorized"] is False
    out.mkdir(parents=True, exist_ok=True)
    save(out / "STARTUP_VALIDATION.json", validation)
    temp = Path(tempfile.mkdtemp(prefix="hybridguard-s06-frozen-r1-")).resolve()
    copied, cwd = temp / "frozen_sources", temp / "empty_cwd"
    shutil.copytree(snapshot / "frozen_sources", copied)
    cwd.mkdir()
    copied_entries = []
    for e in manifest["bound_files"]:
        if not e["path"].startswith("frozen_sources/"):
            continue
        target = copied / Path(e["path"]).relative_to("frozen_sources")
        data = target.read_bytes()
        assert len(data) == e["bytes"] and hashlib.sha256(data).hexdigest() == e["sha256"], e["path"]
        copied_entries.append({"bound_path": e["path"], "actual_path": str(target), "sha256": e["sha256"], "bytes": len(data)})
    # persistence.new_output enumerates these empty directories. No source or
    # resource file is changed, added, symlinked or sourced from the workspace.
    layout = copied / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923"
    layout.mkdir(parents=True)
    stamp = datetime.now(timezone.utc)
    run_id = "s06-e1-freeze-r1-" + stamp.strftime("%Y%m%dT%H%M%SZ")
    job = {"schema_version": "formal-prediction-job-v2", "study_version": protocol["study_version"],
           "run_id": run_id, "protocol_digest": DIGEST, "contract_version": protocol["contract_version"], "policy_version": protocol["policy_version"],
           "execution_scope": "FROZEN_FORMAL_EVALUATION", "variants": plan["variants"], "expected_units": expected,
           "freeze": {"status": "FROZEN", "protocol_version": protocol["protocol_version"], "authorized_execution_step": "S06"}}
    save(out / "RUNNABLE_JOB.json", job)
    binding = {"step": "S06", "run_id": run_id, "review_commit": BASELINE, "freeze_revision": REVISION, "protocol_digest": DIGEST,
               "snapshot": str(snapshot), "runtime_source_root": str(copied), "cwd": str(cwd), "step_output": str(out),
               "job": str(out / "RUNNABLE_JOB.json"), "job_sha256": hashlib.sha256((out / "RUNNABLE_JOB.json").read_bytes()).hexdigest(),
               "input": str(snapshot / "blind/inputs.jsonl"), "config_dir": str(copied / "hybridguard_agent/config/formal_manipulation_role_gate_v2"),
               "policy_path": str(copied / "hybridguard_agent/config/formal_manipulation_policy_v2/decision_policy.json"),
               "static_plan": str(snapshot / "step_execution_plans/S06.json"), "expected_units": len(expected), "stages": 216,
               "scope": "Only exact S06 unit list in frozen order, once; no upstream/synthetic/S07/S08/S10 execution, retries or parameter changes",
               "runtime_files_copied": copied_entries, "copy_has_workspace_fallback": False,
               "empty_directory_initialization": {"paths": [str(layout.parent), str(layout)], "reason": "Frozen persistence.new_output requires existing artifacts/study directories; initialized empty only in temporary runtime copy, before first execution", "source_or_data_change": False}}
    save(out / "JOB_BINDING.json", binding)
    save(out / "AUTHORIZATION.json", {"authorized_at": stamp.isoformat(), "authority": "User explicitly accepted S05-R and authorized S06 in this turn",
         "review_commit": BASELINE, "freeze_revision": REVISION, "protocol_digest": DIGEST, "authorized_step": "S06", "authorized_unit_count": len(expected),
         "upstream_or_synthetic_replay_authorized": False, "S07_authorized": False, "automatic_retry_authorized": False, "commit_or_push_authorized": False,
         "historical_frozen_authorization_modified": False})
    save(out / "run_manifest.json", {"schema_version": "s06-execution-envelope-v1", "status": "PREPARED", "run_id": run_id,
         "review_commit": BASELINE, "freeze_revision": REVISION, "protocol_digest": DIGEST, "job_sha256": binding["job_sha256"],
         "expected_units": len(expected), "prediction_run_manifest": "prediction/run_manifest.json", "started_at": stamp.isoformat(), "attempt": 1,
         "facts_joined": False, "detector_calls": 0, "LLM_calls": 0, "S07_executed": False})
    print(json.dumps({k: binding[k] for k in ("run_id", "freeze_revision", "protocol_digest", "expected_units", "stages", "runtime_source_root")}, indent=2))


if __name__ == "__main__":
    main()
