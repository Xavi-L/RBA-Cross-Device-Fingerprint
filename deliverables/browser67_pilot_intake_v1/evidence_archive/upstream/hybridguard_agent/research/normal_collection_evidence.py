"""Normal-denominator evidence, separate from detector outputs and phase labels.

The pure helpers consume observation and operation proofs tied to a session.
Batch-specific code must verify those proofs against raw data and receipts. The
memory review below does so without modifying or recollecting the old batch.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import gzip
import json
import math
from pathlib import Path

VERSION = "normal-collection-evidence-v1"
ROOT = Path(__file__).resolve().parents[2]


def observation_evidence(bound, required_fields, *, value_predicates=None):
    """Keep valid zero/negative offsets; callers may add field-specific checks."""
    binding = bound.get("source_binding", {})
    reasons = []
    if (bound.get("status") != "OK" or binding.get("binding_valid") is not True
            or binding.get("same_app_record") is not True
            or not binding.get("app_session_id") or not binding.get("raw_reference")):
        reasons.append("CURRENT_RAW_BINDING_NOT_VERIFIED")
    values = {}
    for field in required_fields:
        value = bound.get("features", {}).get(field)
        valid = (field in bound.get("features", {})
                 and bound.get("field_status", {}).get(field) == "observed"
                 and bound.get("field_quality", {}).get(field) == "observed_value"
                 and value is not None
                 and not (type(value) is float and not math.isfinite(value)))
        predicate = (value_predicates or {}).get(field)
        if not valid or (predicate is not None and not predicate(value)):
            reasons.append("OBSERVATION_UNAVAILABLE:" + field)
        values[field] = deepcopy(value)
    if not values:
        reasons.append("REQUIRED_OBSERVATIONS_NOT_SPECIFIED")
    return {"valid": not reasons, "session_id": binding.get("app_session_id"),
            "values": values, "source_reference": binding.get("raw_reference"), "reasons": reasons}


def _normal_base(observation, workflow, kind):
    reasons = list(observation.get("reasons", []))
    if observation.get("valid") is not True:
        reasons.append("VALID_CURRENT_OBSERVATION_REQUIRED")
    if (workflow.get("verified") is not True or not workflow.get("operation_id")
            or not workflow.get("evidence_refs")
            or workflow.get("session_id") != observation.get("session_id")):
        reasons.append("CURRENT_OPERATION_NOT_VERIFIED")
    if workflow.get("noop") is not True:
        reasons.append("NORMAL_WEB_WORKFLOW_NOT_VERIFIED")
    return {"version": VERSION, "kind": kind, "supported": False,
            "session_id": observation.get("session_id"),
            "values": deepcopy(observation.get("values", {})),
            "evidence_refs": [observation.get("source_reference"), *workflow.get("evidence_refs", [])],
            "reasons": reasons}


def _finish(result):
    result["reasons"] = list(dict.fromkeys(result["reasons"]))
    result["evidence_refs"] = list(dict.fromkeys(x for x in result["evidence_refs"] if x))
    result["supported"] = not result["reasons"]
    return result


def normal_pre(observation, workflow):
    """A planned clean label is never a substitute for a verified no-op flow."""
    return _finish(_normal_base(observation, workflow, "normal_pre"))


def normal_post(baseline_basis, observation, workflow, intervention, rollback):
    """Require the matching operation, rollback proof and restored raw values."""
    result = _normal_base(observation, workflow, "normal_post")
    if baseline_basis.get("supported") is not True:
        result["reasons"].append("NORMAL_BASELINE_NOT_VERIFIED")
    if (intervention.get("verified") is not True or not intervention.get("operation_id")
            or not intervention.get("session_id") or not intervention.get("evidence_refs")):
        result["reasons"].append("MATCHING_OPERATION_NOT_SUCCESSFUL")
    if (rollback.get("verified") is not True or not rollback.get("evidence_refs")
            or rollback.get("from_operation_id") != intervention.get("operation_id")
            or rollback.get("from_session_id") != intervention.get("session_id")
            or rollback.get("to_session_id") != observation.get("session_id")
            or len({baseline_basis.get("session_id"), intervention.get("session_id"),
                    observation.get("session_id")}) != 3):
        result["reasons"].append("MATCHING_ROLLBACK_NOT_VERIFIED")
    if (not baseline_basis.get("values")
            or observation.get("values") != baseline_basis.get("values")):
        result["reasons"].append("BASELINE_VALUES_NOT_RESTORED")
    result["evidence_refs"] += [*baseline_basis.get("evidence_refs", []),
                                *intervention.get("evidence_refs", []), *rollback.get("evidence_refs", [])]
    return _finish(result)


def normal_system_change(baseline_basis, observation, workflow, system_change):
    """An L middle stage is normal only with verified legitimate system change.

    expected_values are measured settings/observables confirmed by the batch
    runner, never detector predictions; unchanged requested settings are legal.
    """
    result = _normal_base(observation, workflow, "normal_system_change")
    expected = system_change.get("expected_values", {})
    if baseline_basis.get("supported") is not True:
        result["reasons"].append("NORMAL_BASELINE_NOT_VERIFIED")
    if (system_change.get("verified") is not True or not system_change.get("evidence_refs")
            or system_change.get("from_session_id") != baseline_basis.get("session_id")
            or system_change.get("to_session_id") != observation.get("session_id")
            or not expected or any(observation.get("values", {}).get(k) != v for k, v in expected.items())):
        result["reasons"].append("NORMAL_SYSTEM_CHANGE_NOT_VERIFIED")
    result["evidence_refs"] += [*baseline_basis.get("evidence_refs", []), *system_change.get("evidence_refs", [])]
    return _finish(result)


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    if not Path(path).exists():
        return []
    with (gzip.open if str(path).endswith(".gz") else open)(path, "rt") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def verify_memory_position(root, environment, step, operation, raw, raw_reference, receipt, commands):
    """Match saved raw, CDP response and process command receipt for one slot.

    No detector result is read. A COMPLETED metadata flag alone is insufficient.
    This adapter is intentionally specific to the unchanged memory batch.
    """
    from . import memory_relation_validation as memory
    errors = []
    sid = operation.get("session_id") or ""
    bound = memory.bind_memory_batch(raw, session_id=sid, source_reference=raw_reference,
                                    environment_id="memory-validation-" + environment)
    fields = (memory.NATIVE, memory.WEB, "app.web_data.navigator_layer.hardware_concurrency")
    positive = lambda v: type(v) in (int, float) and math.isfinite(v) and v > 0
    observation = observation_evidence(bound, fields, value_predicates={f: positive for f in fields})
    payload = raw.get("canonical_received_payload", {})
    manifest = payload.get("collection_manifest", {})
    context = "memory-validation:" + environment + ":" + step
    if (operation.get("step_id") != step or operation.get("status") != "COLLECTED"
            or operation.get("cdp_status") != "COMPLETED" or receipt.get("status") != "COMPLETED"
            or manifest.get("runtime_context") != context
            or manifest.get("collector_install_id") != operation.get("collector_install_id")):
        errors.append("OPERATION_RAW_IDENTITY_OR_STATUS_MISMATCH")
    noop = receipt.get("target_gib") is None
    target = operation.get("target_gib")
    if noop != (not step.endswith("-attack")):
        errors.append("PLANNED_OPERATION_NOT_PERFORMED")
    wanted = "void 0;" if noop else (f"(() => {{ const value = {target};\n"
          "    Object.defineProperty(Navigator.prototype, 'deviceMemory', {configurable:true, get:() => value});\n"
          "    Object.defineProperty(navigator, 'deviceMemory', {configurable:true, get:() => value});\n  })();")
    events = receipt.get("commands", [])
    expected_methods = ["Page.enable", "Page.addScriptToEvaluateOnNewDocument", "Page.navigate",
                        "Runtime.evaluate", "Page.removeScriptToEvaluateOnNewDocument"]
    if ([c.get("method") for c in events] != expected_methods
            or any("result" not in c or c.get("error") or c.get("result", {}).get("errorText")
                   or c.get("result", {}).get("exceptionDetails") for c in events)):
        errors.append("CDP_COMMAND_RECEIPTS_NOT_SUCCESSFUL")
    else:
        runtime = events[3].get("result", {}).get("result", {}).get("value", {})
        if (receipt.get("version") != "memory-only-cdp-v1" or receipt.get("source") != wanted
                or receipt.get("injected_properties") != ([] if noop else ["navigator.deviceMemory"])
                or (not noop and receipt.get("target_gib") != target)
                or events[1].get("params", {}).get("source") != wanted
                or events[2].get("params", {}).get("url") != "file:///android_asset/expanded_probe.html"
                or events[4].get("params", {}).get("identifier") != events[1].get("result", {}).get("identifier")
                or receipt.get("future_document_script_removed") is not True
                or receipt.get("current_runtime_observation") != runtime
                or runtime.get("deviceMemory") != observation["values"][memory.WEB]
                or runtime.get("hardwareConcurrency") != observation["values"][fields[2]]):
            errors.append("CDP_WORKFLOW_OR_CURRENT_RAW_VALUES_MISMATCH")
    try:
        if not (_stamp(operation["started_at"]) <= _stamp(receipt["started_at"])
                <= _stamp(receipt["finished_at"]) <= _stamp(operation["finished_at"])
                and _stamp(operation["started_at"]) <= _stamp(raw["server_received_at"])
                <= _stamp(operation["finished_at"])):
            errors.append("OPERATION_RECEIPT_TIME_MISMATCH")
    except (KeyError, ValueError, TypeError):
        errors.append("OPERATION_RECEIPT_TIME_MISSING")
    receipt_name = step + ".cdp.json"
    matched = [i for i, c in enumerate(commands) if any(str(a).endswith("/" + receipt_name) for a in c.get("argv", []))]
    removed = fresh = False
    if len(matched) == 1:
        i = matched[0]
        before = commands[max(0, i-6):i]
        after = commands[i+1:i+3]
        fresh = (len(before) == 6 and before[0].get("argv", [])[-3:-1] == ["am", "force-stop"]
                 and before[0].get("returncode") == 0 and "pidof" in before[1].get("argv", [])
                 and before[1].get("returncode") == 1 and context in before[2].get("argv", [])
                 and before[2].get("returncode") == 0
                 and commands[i].get("returncode") == 0
                 and ("noop" if noop else str(target)) == commands[i].get("argv", [None])[-1])
        removed = (len(after) == 2 and after[0].get("argv", [])[-3:-1] == ["am", "force-stop"]
                   and after[0].get("returncode") == 0 and "pidof" in after[1].get("argv", [])
                   and after[1].get("returncode") == 1
                   and operation.get("owned_app_process_absent_after") is True)
    if not fresh:
        errors.append("FRESH_OWNED_PROCESS_NOT_VERIFIED")
    prefix = "deliverables/memory_relation_validation_v1/runs/" + environment + "/"
    proof = {"verified": not errors and observation["valid"], "session_id": sid, "operation_id": step,
             "noop": noop, "fresh_process_verified": fresh, "process_removed_verified": removed,
             "evidence_refs": [prefix + "operations.jsonl#" + step, prefix + receipt_name,
                               prefix + "environment.json#commands", raw_reference], "reasons": errors}
    return observation, proof


def review_memory_batch(root=ROOT):
    """Read all 72 planned slots; return revised eligibility without rewriting history."""
    from . import memory_relation_validation as memory
    root = Path(root)
    old = root / "deliverables/memory_relation_validation_v1"
    settings = _read(old / "SETTINGS.json")
    predictions = {r["step_id"] + "/" + r["environment"]: r for r in _rows(old / "new_batch.jsonl.gz")}
    reviews, groups = [], []
    for env in settings["environments"]:
        eid = env["environment_group_id"]
        run = old / "runs" / eid
        operations = {r["step_id"]: r for r in _rows(run / "operations.jsonl")}
        raw_rows = _rows(run / "backend/raw_expanded_payloads.jsonl")
        environment = _read(run / "environment.json") if (run / "environment.json").exists() else {}
        for target in settings["targets_gib"]:
            for number in range(1, settings["rounds"] + 1):
                members = {}
                for phase in settings["phases"]:
                    step = f"memory-{target}-r{number}-{phase}"
                    op = operations.get(step, {})
                    matches = [(i, r) for i, r in enumerate(raw_rows, 1)
                               if op.get("session_id") and r.get("session_id") == op["session_id"]]
                    receipt_path = run / (step + ".cdp.json")
                    raw_reference = None
                    if len(matches) == 1 and receipt_path.exists():
                        line, raw = matches[0]
                        raw_reference = f"{(run/'backend/raw_expanded_payloads.jsonl').relative_to(root)}:{line}"
                        obs, workflow = verify_memory_position(root, eid, step, op, raw, raw_reference,
                                                               _read(receipt_path), environment.get("commands", []))
                    else:
                        obs = {"valid": False, "session_id": op.get("session_id"), "values": {},
                               "reasons": ["CURRENT_RAW_OR_RECEIPT_MISSING_OR_AMBIGUOUS"]}
                        workflow = {"verified": False, "session_id": op.get("session_id"), "noop": False,
                                    "operation_id": step, "evidence_refs": [], "reasons": obs["reasons"]}
                    saved = predictions.get(step + "/" + eid, {})
                    saved_matches = (saved.get("source_binding", {}).get("app_session_id") == obs.get("session_id")
                                     and saved.get("source_binding", {}).get("raw_reference") == raw_reference
                                     and all(saved.get("operands", {}).get(f, {}).get("value") == obs.get("values", {}).get(f)
                                             for f in (memory.NATIVE, memory.WEB)))
                    if not saved_matches:
                        obs["valid"] = False
                        obs["reasons"].append("SAVED_PREDICTION_RAW_BINDING_MISMATCH")
                    members[phase] = {"observation": obs, "workflow": workflow, "operation": op, "saved": saved,
                                      "step_id": step, "raw_reference": raw_reference}
                pre, active, post = (members[p] for p in ("clean_pre", "attack", "clean_post"))
                pre_basis = normal_pre(pre["observation"], pre["workflow"])
                rollback = {"verified": (active["workflow"].get("process_removed_verified") is True
                             and post["workflow"].get("fresh_process_verified") is True
                             and active["operation"].get("collector_install_id") == post["operation"].get("collector_install_id")),
                            "from_operation_id": active["step_id"],
                            "from_session_id": active["observation"].get("session_id"),
                            "to_session_id": post["observation"].get("session_id"),
                            "evidence_refs": active["workflow"].get("evidence_refs", []) + post["workflow"].get("evidence_refs", [])}
                post_basis = normal_post(pre_basis, post["observation"], post["workflow"], active["workflow"], rollback)
                groups.append({"environment": eid, "target_gib": target, "round": number,
                               "pre_normal_supported": pre_basis["supported"], "post_normal_supported": post_basis["supported"],
                               "operation_verified": active["workflow"]["verified"],
                               "rollback_verified": rollback["verified"],
                               "values_restored": pre["observation"].get("values") == post["observation"].get("values")})
                for phase, current in members.items():
                    basis = pre_basis if phase == "clean_pre" else post_basis if phase == "clean_post" else {
                        "supported": False, "kind": "intervention_slot", "reasons": ["NOT_A_PLANNED_NORMAL_POSITION"]}
                    reviews.append({"environment": eid, "target_gib": target, "round": number, "phase": phase,
                                    "step_id": current["step_id"], "sample_id": current["saved"].get("sample_id"),
                                    "raw_reference": current["raw_reference"], "normal_basis": basis,
                                    "observation_valid": current["observation"]["valid"],
                                    "workflow_verified": current["workflow"]["verified"],
                                    "workflow_reasons": current["workflow"].get("reasons", []),
                                    "condition_states": {k: c["state"] for k, c in current["saved"].get("conditions", {}).items()},
                                    "model_states": {m["model_id"]: m["decision"] for m in current["saved"].get("models", [])}})
    confirmed = [r for r in reviews if r["normal_basis"]["supported"]]
    normal_slots = [r for r in reviews if r["phase"] in ("clean_pre", "clean_post")]
    return {"version": VERSION, "scope": "offline review of saved memory batch; no model fits or recollection",
            "basis": "Normal pre requires valid same-session raw and successful no-op CDP/fresh-process workflow; post also requires matching successful intervention, process exit, fresh process, and restored Native/Web/CPU values. Detector outputs never determine eligibility.",
            "historical_outputs_modified": False, "planned_records": settings["planned_records"],
            "reviewed_records": len(reviews), "planned_normal_positions": len(normal_slots),
            "confirmed_normal_n": len(confirmed), "normal_without_support_n": len(normal_slots)-len(confirmed),
            "groups_n": len(groups), "verified_rollback_groups_n": sum(g["rollback_verified"] and g["values_restored"] for g in groups),
            "conditions_on_confirmed_normal": {name: dict(Counter(r["condition_states"].get(name, "FAILED") for r in confirmed))
                for name in ("R_REL", "R_WEB8")},
            "models_on_confirmed_normal": {m["model_id"]: dict(Counter(r["model_states"].get(m["model_id"], "FAILED") for r in confirmed))
                for m in settings["saved_models"]},
            "all_planned_flow": {"valid_observation_n": sum(r["observation_valid"] for r in reviews),
                "verified_operation_n": sum(r["workflow_verified"] for r in reviews),
                "condition_states": {name: dict(Counter(r["condition_states"].get(name, "FAILED") for r in reviews))
                                     for name in ("R_REL", "R_WEB8")}},
            "groups": groups, "records": reviews}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT/"deliverables/timezone_relation_validation_v1")
    args = parser.parse_args()
    result = review_memory_batch()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/"MEMORY_NORMAL_REVIEW.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    (args.output_dir/"MEMORY_NORMAL_REVIEW.md").write_text(
        "# 上轮内存实验正常分母离线复核\n\n"
        "本轮补充流程证据侧表，未覆盖旧报告、模型、原始记录或预测，也未重采内存数据。"
        "计划 clean 不能直接进入正常误报分母。pre 要有有效同次观测和无修改正常流程；"
        "post 另需对应操作成功、旧 App 进程确已退出、新进程正常采集、值恢复。"
        "报警结果不参与正常资格判断。\n\n"
        f"复核保存的 {result['groups_n']} 组、{result['reviewed_records']}/{result['planned_records']} 个预定位置。"
        f"{result['verified_rollback_groups_n']} 组有撤销与恢复支持；"
        f"{result['confirmed_normal_n']}/{result['planned_normal_positions']} 个正常位置满足依据，"
        f"{result['normal_without_support_n']} 个正常位置依据不足。\n\n"
        "核对了每位置的 session、runtime_context、安装标识、原始引用及值，CDP 命令响应和当前运行时值，"
        "正常阶段的 void 0 脚本，App 启停命令返回码与进程缺席，以及 pre/post 的 Native 内存、Web 内存和 CPU 值。"
        "72 个位置全部留在流向统计中；U/FAILED 不会因筛选正常分母而消失。\n\n"
        f"确认正常分母中的两条件状态：{json.dumps(result['conditions_on_confirmed_normal'], ensure_ascii=False)}。"
        f"六个保存模型状态分别为：{json.dumps(list(result['models_on_confirmed_normal'].values()), ensure_ascii=False)}。"
        "本次真实材料中原 0/48 报警结果保持不变，同时修正过去仅按 phase != attack 取正常分母的统计边界。\n\n"
        "逐条证据与全部预定位置状态见 MEMORY_NORMAL_REVIEW.json。复现命令：\n\n"
        "```bash\nPYTHONDONTWRITEBYTECODE=1 python3 -m hybridguard_agent.research.normal_collection_evidence\n```\n")
    print(json.dumps({k: result[k] for k in ("planned_records", "confirmed_normal_n", "groups_n", "verified_rollback_groups_n")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
