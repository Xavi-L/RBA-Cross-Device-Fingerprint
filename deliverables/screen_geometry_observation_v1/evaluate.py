#!/usr/bin/env python3
"""Frozen single-condition evaluation and process-based normal/effect evidence."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from hybridguard_agent.research import screen_geometry_sources as sources
from hybridguard_agent.research import screen_geometry_relations as relation
from hybridguard_agent.research import mtc_screen_relations as old_screen
from hybridguard_agent.research import normal_collection_evidence as normal
from hybridguard_agent.research.rule_learning.contracts import cell

PREFIX = "app.web_data.screen_layer."
LEGACY_NORMAL_FIELDS = tuple(PREFIX + f for f in ("inner_width", "inner_height", "device_pixel_ratio",
                            "visual_viewport_width", "visual_viewport_height", "visual_viewport_scale"))
CONDITIONS = ("R_HEIGHT710", "R_SAME_WEB", "R_HOST_GEOMETRY")


def obj(value): return value if isinstance(value, dict) else {}


def array(value): return value if isinstance(value, list) else []


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def rows(path):
    if not path.exists(): return []
    with (gzip.open if str(path).endswith(".gz") else open)(path, "rt") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def state(value):
    return "FAILED" if value.get("evaluation_status") != "OK" else "U" if not value.get("available") else "T" if value["value"] else "F"


def current_conditions(bound):
    if bound.get("status") != "OK":
        return {name: {**cell("FAILED", "CURRENT_RAW_BINDING_FAILED"), "state":"FAILED"} for name in CONDITIONS}
    field = PREFIX + "inner_height"
    height = bound.get("features", {}).get(field)
    valid = (bound.get("field_status", {}).get(field) == "observed"
             and bound.get("field_quality", {}).get(field) == "observed_value" and relation.number(height))
    absolute = cell("T" if height > 710 else "F", "FIXED_CURRENT_INNER_HEIGHT_GT_710") if valid else cell("U", "CURRENT_INNER_HEIGHT_UNAVAILABLE")
    absolute["fields"] = {field: height}
    same = old_screen.evaluate(bound)[old_screen.ATOM_ID]
    same["fields"] = {f: bound.get("features", {}).get(f) for f in old_screen.FIELDS}
    cross = relation.evaluate(bound)[relation.ATOM_ID]
    result = {"R_HEIGHT710": absolute, "R_SAME_WEB": same, "R_HOST_GEOMETRY": cross}
    return {name: {**value, "state": state(value)} for name, value in result.items()}


def current_row(raw, operation, reference, environment, *, smoke=False):
    sid = operation.get("session_id") or ""
    bound = sources.bind_current(raw, session_id=sid, source_reference=reference,
             environment_id=("screen-geometry-smoke-" if smoke else "screen-geometry-") + environment)
    positive = {f: relation.number for f in LEGACY_NORMAL_FIELDS}
    observation = normal.observation_evidence(bound, LEGACY_NORMAL_FIELDS, value_predicates=positive)
    geometry = obj(bound.get("geometry"))
    web = obj(geometry.get("web"))
    legacy = {f.removeprefix(PREFIX): v for f, v in bound.get("features", {}).items() if f.startswith(PREFIX)}
    new_fields = {k: v.get("value") for k, v in obj(web.get("fields")).items() if isinstance(v, dict)}
    row = {"sample_id": "screengeometry-" + sid if sid else environment + "/" + operation["step_id"],
           "environment": environment, "step_id": operation["step_id"], "process_type": operation["process_type"],
           "round": operation["round"], "phase": operation["phase"], "raw_reference": reference,
           "source_binding": bound["source_binding"], "source_errors": bound.get("errors", []),
           "operation": deepcopy(operation), "conditions": current_conditions(bound),
           "geometry_evidence": bound.get("geometry_evidence", {}),
           "geometry_module_status": geometry.get("read_status") if isinstance(geometry, dict) else None,
           "legacy_screen": legacy, "web_geometry_values": new_fields,
           "host_before": geometry.get("host_before"), "host_after": geometry.get("host_after"),
           "geometry_operation_receipt": geometry.get("operation_receipt"),
           "geometry_attempts": [{k:a.get(k) for k in ("observation_id", "attempt_id", "read_status", "reason", "host_stable")}
                                 for a in array(geometry.get("attempts")) if isinstance(a, dict)],
           "same_snapshot_as_legacy_screen_layer": False,
           "legacy_vs_geometry_web_differences": {k: {"legacy": legacy[k], "geometry": new_fields[k]}
                 for k in sorted(set(legacy) & set(new_fields)) if legacy[k] != new_fields[k]},
           "valid_legacy_observation": observation["valid"], "observable_intervention": False,
           "material_role": "ENGINEERING_SMOKE" if smoke else "FROZEN_FORMAL_MATRIX"}
    prefixes = ("app.web_data.navigator_layer.", "app.web_data.execution_layer.",
                "app.web_data.graphics_layer.", "app.web_data.automation_surface_layer.")
    row["major_non_target_fields"] = {k:v for k,v in bound.get("features", {}).items() if k.startswith(prefixes)}
    return row, bound, observation


def _timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def workflow_proof(bound, raw, operation, receipt, commands, *, environment, run, settings, smoke=False):
    """Verify current raw, explicit commands and process lifecycle, never rules.

    Geometry availability is deliberately NOT a normal-label requirement.
    Actual host receipt, if present, is additional operation evidence. Without
    it the known App's successful launch arguments still establish a routine
    normal operation attempt; effectiveness is assessed separately.
    """
    errors = []
    complete_errors = []
    sid = operation.get("session_id")
    step = operation["step_id"]
    context = ("screen-geometry-smoke:" if smoke else "screen-geometry:") + environment + ":" + step
    payload = obj(raw.get("canonical_received_payload"))
    manifest = obj(payload.get("collection_manifest"))
    active = operation["process_type"] == "A" and operation["phase"] == "change"
    if (bound.get("status") != "OK" or operation.get("status") not in ("COLLECTED", "FAILED")
            or manifest.get("runtime_context") != context
            or manifest.get("collector_install_id") != operation.get("collector_install_id")):
        errors.append("CURRENT_RAW_OPERATION_BINDING_OR_STATUS_INVALID")
    events = array(receipt.get("commands"))
    expected_methods = ["Page.enable", "Emulation.setDeviceMetricsOverride" if active else "Emulation.clearDeviceMetricsOverride",
                        "Page.navigate", "Runtime.evaluate", "Emulation.clearDeviceMetricsOverride", "Runtime.evaluate"]
    successful = lambda c: isinstance(c, dict) and "result" in c and not c.get("error") and not obj(c.get("result")).get("exceptionDetails") and not obj(c.get("result")).get("errorText")
    current_commands_ok = (len(events) >= 3 and [obj(c).get("method") for c in events[:3]] == expected_methods[:3]
                           and all(successful(c) for c in events[:3]))
    command_ok = (len(events) == len(expected_methods)
                  and [obj(c).get("method") for c in events] == expected_methods and all(successful(c) for c in events))
    if (receipt.get("version") != "screen-only-cdp-v1" or receipt.get("active_screen_override") != active
            or obj(receipt.get("raw_receipt")).get("session_id") != sid
            or obj(receipt.get("raw_receipt")).get("received_before_rollback") is not True
            or not current_commands_ok):
        errors.append("CDP_CURRENT_COLLECTION_FLOW_NOT_VERIFIED")
    if not command_ok or receipt.get("status") != "COMPLETED" or operation.get("cdp_status") != "COMPLETED":
        complete_errors.append("COMPLETE_CDP_FLOW_OR_ROLLBACK_NOT_VERIFIED")
    if current_commands_ok:
        expected_params = settings["screen_configuration"]["cdpEmulation"]["applyCommands"][0]["params"] if active else {}
        if events[1].get("params") != expected_params or events[2].get("params", {}).get("url") != "file:///android_asset/expanded_probe.html":
            errors.append("CDP_FIXED_OPERATION_OR_NAVIGATION_MISMATCH")
    relevant = [(i,c) for i,c in enumerate(commands) if any(str(a).endswith("/" + step + ".cdp.json") for a in c.get("argv", []))]
    launches = [(i,c) for i,c in enumerate(commands) if context in c.get("argv", []) and "start" in c.get("argv", [])]
    fresh = removed = False
    host_args_verified = False
    preceding = []
    if len(relevant) == 1 and len(launches) == 1:
        ci, node = relevant[0]; li, launch = launches[0]
        preceding = commands[max(0,li-20):li]
        stopped = any(c.get("argv", [])[-3:-1] == ["am", "force-stop"] and c.get("returncode") == 0 for c in preceding)
        absent = any("pidof" in c.get("argv", []) and c.get("returncode") == 1 for c in preceding)
        fresh = li < ci and stopped and absent and launch.get("returncode") == 0
        if node.get("returncode") != 0: complete_errors.append("CDP_DRIVER_EXITED_WITH_ERROR")
        following = commands[ci+1:ci+8]
        removed = (operation.get("owned_app_process_absent_after") is True
                   and any(c.get("argv", [])[-3:-1] == ["am", "force-stop"] and c.get("returncode") == 0 for c in following)
                   and any("pidof" in c.get("argv", []) and c.get("returncode") == 1 for c in following))
        argv = launch.get("argv", [])
        expected_args = {"GEOMETRY_HIDE_HEADER": str(operation["process_type"] == "L2" and operation["phase"] == "change").lower(),
                         "GEOMETRY_ENABLE_ZOOM": str(operation["process_type"] == "L3").lower(),
                         "GEOMETRY_ZOOM_FACTOR": str(1.25 if operation["process_type"] == "L3" and operation["phase"] == "change" else 1.0)}
        host_args_verified = all(any(str(a).endswith("."+k) and i+1<len(argv) and argv[i+1]==v
                                    for i,a in enumerate(argv)) for k,v in expected_args.items())
    if not fresh: errors.append("FRESH_OWNED_PROCESS_NOT_VERIFIED")
    if not removed: complete_errors.append("OWNED_PROCESS_REMOVAL_NOT_VERIFIED")
    if not host_args_verified: errors.append("HOST_OPERATION_LAUNCH_ARGUMENTS_NOT_VERIFIED")
    expected_rotation = "1" if operation["process_type"] == "L1" and operation["phase"] == "change" else "0"
    # A successful supported system-operation request establishes a known
    # normal operation attempt. Target attainment is a separate outcome:
    # settings may settle after the before-read or the Activity may keep its
    # old orientation. Missing dumpsys parser output does not make collection
    # abnormal, especially when all geometry is unavailable.
    system_verified = all(any(c.get("argv", [])[-5:] == ["settings","put","system", key,value]
                             and c.get("returncode") == 0 for c in preceding)
                          for key,value in (("accelerometer_rotation","0"),("user_rotation",expected_rotation)))
    geometry_host = obj(obj(bound.get("geometry")).get("host_before"))
    actual_orientation = geometry_host.get("orientation")
    after_system = obj(operation.get("system_after"))
    orientation_achieved = (actual_orientation == (2 if expected_rotation == "1" else 1)
                           if actual_orientation in (1,2) else
                           expected_rotation in array(after_system.get("input_orientation"))
                           if array(after_system.get("input_orientation")) else None)
    if not system_verified: errors.append("SYSTEM_OPERATION_COMMAND_NOT_VERIFIED")
    host_receipt = obj(obj(bound.get("geometry")).get("operation_receipt"))
    if host_receipt:
        requested = operation.get("host_operation_request", {})
        if (host_receipt.get("host_header_requested_hidden") != requested.get("hide_header")
                or host_receipt.get("host_header_actual_visibility") != (8 if requested.get("hide_header") else 0)
                or host_receipt.get("zoom_controls_requested_enabled") != requested.get("enable_zoom")
                or host_receipt.get("zoom_factor_requested") != requested.get("zoom_factor")
                or host_receipt.get("zoom_execution") != ("invoked_void_api" if requested.get("zoom_factor") == 1.25 else "matched_noop")):
            errors.append("HOST_OPERATION_CURRENT_RECEIPT_MISMATCH")
    try:
        if not (_timestamp(operation["started_at"]) <= _timestamp(receipt["started_at"])
                <= _timestamp(raw["server_received_at"]) <= _timestamp(receipt["finished_at"])
                <= _timestamp(operation["finished_at"])):
            errors.append("CURRENT_RECEIPT_OPERATION_TIME_MISMATCH")
    except (KeyError, TypeError, ValueError): errors.append("CURRENT_RECEIPT_OPERATION_TIME_UNAVAILABLE")
    refs = [bound.get("source_binding", {}).get("raw_reference"), str(run / "operations.jsonl") + "#" + step,
            str(run / (step + ".cdp.json")), str(run / "environment.json") + "#commands"]
    return {"verified": not errors, "current_execution_verified": not errors,
            "complete_workflow_verified": not errors and not complete_errors,
            "session_id": sid, "operation_id": step, "noop": not active,
            "evidence_refs": refs, "reasons": errors, "fresh_process_verified": fresh,
            "complete_workflow_reasons": complete_errors,
            "process_removed_verified": removed, "system_operation_verified": system_verified,
            "actual_host_orientation": actual_orientation,
            "requested_orientation_achieved": orientation_achieved,
            "requested_system_settings_achieved": after_system.get("user_rotation") == expected_rotation and after_system.get("accelerometer_rotation") == "0",
            "host_launch_arguments_verified": host_args_verified,
            "host_current_receipt_available": bool(host_receipt),
            "cdp_rollback_verified": command_ok and receipt.get("rollback_status") == "COMPLETED",
            "normality_requires_geometry": False}


def adjudicate_trio(members):
    pre, mid, post = members
    observations = [m["observation"] for m in members]
    before, changed, after = [o.get("values", {}) for o in observations]
    effect_valid = all(o.get("valid") for o in observations[:2])
    recovery_valid = all(o.get("valid") for o in observations)
    baseline_basis = normal.normal_pre(observations[0], pre["workflow"])
    flow = mid["workflow"]
    process = mid["row"]["process_type"]
    target_changes = {k:[before.get(k), changed.get(k), after.get(k)] for k in LEGACY_NORMAL_FIELDS
                      if effect_valid and before.get(k) != changed.get(k)}
    geometry_available = all(isinstance(m["row"].get("host_before"),dict) for m in members[:2])
    host_changes = {}
    host_restored = None
    if geometry_available:
        wanted = ("width_px", "height_px", "orientation", "view_scale_x", "view_scale_y", "rotation_degrees")
        hosts = [obj(m["row"].get("host_before")) for m in members]
        host_changes = {k:[h.get(k) for h in hosts] for k in wanted if hosts[0].get(k) != hosts[1].get(k)}
        if hosts[2]: host_restored = all(hosts[0].get(k) == hosts[2].get(k) for k in wanted)
    executed = flow.get("current_execution_verified", flow.get("verified")) is True
    execution = "EXECUTED" if executed else "NOT_EXECUTED" if mid["row"]["operation"].get("status") == "NOT_EXECUTED" else "OPERATION_FAILED"
    effect = "MISSING_OBSERVATION" if not effect_valid else "OBSERVABLE_CHANGE" if target_changes or host_changes else "NO_OBSERVABLE_EFFECT"
    # Restoration uses observed current target fields, successful explicit clear,
    # fresh default App and actual system orientation; geometry is optional.
    rollback = {"verified": flow.get("cdp_rollback_verified") is True and flow.get("process_removed_verified") is True
                and flow.get("complete_workflow_verified", flow.get("verified")) is True
                and post["workflow"].get("fresh_process_verified") is True and post["workflow"].get("verified") is True
                and host_restored is not False,
                "from_operation_id": flow["operation_id"], "from_session_id": observations[1].get("session_id"),
                "to_session_id": observations[2].get("session_id"),
                "evidence_refs": flow["evidence_refs"] + post["workflow"]["evidence_refs"]}
    pre["row"]["normal_basis"] = baseline_basis
    post["row"]["normal_basis"] = normal.normal_post(baseline_basis, observations[2], post["workflow"], flow, rollback)
    if process.startswith("L"):
        proof = {"verified": executed, "from_session_id": observations[0].get("session_id"),
                 "to_session_id": observations[1].get("session_id"), "expected_values": changed,
                 "evidence_refs": flow["evidence_refs"]}
        mid["row"]["normal_basis"] = normal.normal_system_change(baseline_basis, observations[1], flow, proof)
    else:
        mid["row"]["normal_basis"] = {"supported": False, "kind":"screen_intervention_attempt", "reasons":["NOT_A_NORMAL_POSITION"]}
    major = set().union(*(m["row"]["major_non_target_fields"].keys() for m in members))
    confounds = {k:[m["row"]["major_non_target_fields"].get(k) for m in members] for k in sorted(major)
                if any(m["row"]["major_non_target_fields"].get(k) != pre["row"]["major_non_target_fields"].get(k) for m in members[1:])}
    observable = process == "A" and executed and effect_valid and bool(target_changes)
    evidence = {"environment":mid["row"]["environment"], "process_type":process, "round":mid["row"]["round"],
                "sample_ids":[m["row"]["sample_id"] for m in members], "execution":execution, "effect":effect,
                "observable_intervention":observable, "target_changes":target_changes, "host_changes":host_changes,
                "host_restored":host_restored,
                "requested_orientation_achieved": flow.get("requested_orientation_achieved"),
                "recovery":"RESTORED" if recovery_valid and before == after and rollback["verified"] else
                           "MISSING_OBSERVATION" if not recovery_valid else "RECOVERY_NOT_VERIFIED",
                "rollback_evidence":rollback, "non_target_differences":confounds,
                "confounded":bool(confounds) if major else None,
                "major_non_target_field_count":len(major),
                "normal_supported":[m["row"]["normal_basis"]["supported"] for m in members]}
    mid["row"]["observable_intervention"] = observable
    mid["row"]["trio_evidence"] = evidence
    return evidence


def _collector():
    spec = importlib.util.spec_from_file_location("screen_geometry_collector", HERE / "collect.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def evaluate(out=HERE, *, smoke=False):
    settings = read(out / "SETTINGS.json")
    collector = _collector(); collector.validate_settings(settings)
    destination = out / "smoke" if smoke else out
    if (destination / "predictions.jsonl.gz").exists(): raise FileExistsError("Saved predictions exist; use summarize")
    result = []
    for environment in settings["environments"][:1] if smoke else settings["environments"]:
        eid = environment["environment_group_id"]; run = destination / "runs" / eid
        operations = {o["step_id"]:o for o in rows(run / "operations.jsonl") if o.get("step_id")}
        archive = run / "backend/raw_expanded_payloads.jsonl"; indexed = defaultdict(list)
        for line, raw in enumerate(rows(archive), 1): indexed[raw.get("session_id")].append((line, raw))
        lifecycle = read(run / "environment.json", {})
        members = []
        for planned in collector.positions(settings, smoke):
            operation = {**planned, **operations.get(planned["step_id"], {"status":"NOT_EXECUTED", "cdp_status":"NOT_EXECUTED"})}
            matches = indexed.get(operation.get("session_id"), [])
            raw = matches[0][1] if len(matches) == 1 else {}
            reference = str(archive.relative_to(ROOT)) + ":" + str(matches[0][0] if len(matches) == 1 else "missing")
            row, bound, observation = current_row(raw, operation, reference, eid, smoke=smoke)
            receipt = read(run / (operation["step_id"] + ".cdp.json"), {})
            workflow = workflow_proof(bound, raw, operation, receipt, lifecycle.get("commands", []), environment=eid,
                        run=run.relative_to(ROOT), settings=settings, smoke=smoke)
            row["workflow_evidence"] = workflow
            members.append({"row":row, "observation":observation, "workflow":workflow})
            if len(members) == 3:
                adjudicate_trio(members); result.extend(m["row"] for m in members); members = []
    if len(result) != (6 if smoke else 72): raise ValueError("ALL_PLANNED_POSITIONS_MUST_BE_RETAINED")
    with gzip.open(destination / "predictions.jsonl.gz", "xt") as stream:
        for row in result: stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",",":")) + "\n")
    return summarize(destination, planned=6 if smoke else 72)


def statistics(data):
    count = len(data)
    values = {}
    for name in CONDITIONS:
        counts = {s:sum(r["conditions"][name]["state"] == s for r in data) for s in ("T","F","U","FAILED")}
        values[name] = {**counts, "explicit_coverage":{"numerator":counts["T"]+counts["F"], "denominator":count},
                        "alarm_proportion":{"numerator":counts["T"],"denominator":count}}
    return {"n":count, "conditions":values}


def summarize(out=HERE, *, planned=72):
    data = rows(out / "predictions.jsonl.gz")
    settings = read((out.parent if planned == 6 else out) / "SETTINGS.json")
    environments = settings["environments"][:1] if planned == 6 else settings["environments"]
    expected = {(e["environment_group_id"],p["step_id"]) for e in environments for p in _collector().positions(settings, planned == 6)}
    if len(data) != planned or {(r["environment"],r["step_id"]) for r in data} != expected:
        raise ValueError("SAVED_PLANNED_MEMBERS_MISSING_OR_DUPLICATED")
    trios = [r["trio_evidence"] for r in data if r.get("trio_evidence")]
    normal_rows = [r for r in data if r.get("normal_basis",{}).get("supported")]
    effective = [r for r in data if r.get("observable_intervention")]
    common = [r for r in data if all(r["conditions"][name]["state"] in ("T","F") for name in CONDITIONS)]
    summary = {"model_fit_calls":0, "planned_records":planned,
        "actual_attempted":sum(r["operation"].get("status") != "NOT_EXECUTED" for r in data),
        "actual_executed":sum(r.get("workflow_evidence",{}).get("verified") is True for r in data),
        "received_raw_records":sum(r["source_binding"].get("binding_valid") is True for r in data),
        "usable_geometry_windows":sum(r.get("geometry_evidence",{}).get("usable_window") is True for r in data),
        "all":statistics(data), "confirmed_normal":statistics(normal_rows),
        "attempted_intervention":statistics([r for r in data if r["process_type"]=="A" and r["phase"]=="change"]),
        "observable_intervention":statistics(effective), "common_evaluable_subset":statistics(common),
        "common_evaluable_normal":statistics([r for r in common if r.get("normal_basis",{}).get("supported")]),
        "common_evaluable_intervention":statistics([r for r in common if r.get("observable_intervention")]),
        "by_process_phase": {"/".join(key):statistics([r for r in data if (r["process_type"],r["phase"])==key])
                             for key in sorted({(r["process_type"],r["phase"]) for r in data})},
        "by_environment": {env:statistics([r for r in data if r["environment"]==env]) for env in sorted({r["environment"] for r in data})},
        "normal_change_by_process": {kind:statistics([r for r in normal_rows if r["process_type"]==kind and r["phase"]=="change"])
                                     for kind in ("L1","L2","L3")},
        "normal_observable_change_by_process": {kind:statistics([r for r in normal_rows if r["process_type"]==kind and r["phase"]=="change"
                         and r.get("trio_evidence",{}).get("effect")=="OBSERVABLE_CHANGE"])
                                     for kind in ("L1","L2","L3")},
        "no_observable_effect_positions":statistics([r for r in data if r.get("trio_evidence",{}).get("effect")=="NO_OBSERVABLE_EFFECT"]),
        "trio_execution":dict(Counter(t["execution"] for t in trios)),
        "trio_effects":dict(Counter(t["effect"] for t in trios)), "trio_recovery":dict(Counter(t["recovery"] for t in trios)),
        "normal_evidence_exclusions":[{"sample_id":r["sample_id"],"reasons":r["normal_basis"]["reasons"]}
            for r in data if (r["process_type"]!="A" or r["phase"]!="change") and not r["normal_basis"]["supported"]],
        "geometry_unavailability":dict(Counter(issue for r in data for issue in r.get("geometry_evidence",{}).get("issues",[]))),
        "condition_difference_rows":[r["sample_id"] for r in data if len({c["state"] for c in r["conditions"].values()})>1],
        "legacy_new_web_snapshot_difference_records":sum(bool(r["legacy_vs_geometry_web_differences"]) for r in data),
        "trios":trios}
    write(out / "SUMMARY.json", summary)
    render_results(out, summary, data)
    return summary


def render_results(out, summary, data):
    """Rebuild the numerical report exclusively from saved individual results."""
    def metric(group, name):
        c=group["conditions"][name];n=group["n"]
        return f'{c["T"]}/{c["F"]}/{c["U"]}/{c["FAILED"]}; {c["T"]+c["F"]}/{n}'
    groups=[("全部预定记录",summary["all"]),("有依据正常",summary["confirmed_normal"]),
            *[("正常变化位置 "+k+"（含无效尝试）",v) for k,v in summary["normal_change_by_process"].items()],
            *[("已核验实际正常变化 "+k,v) for k,v in summary["normal_observable_change_by_process"].items()],
            ("A全部预定尝试",summary["attempted_intervention"]),("A已核验有效变化",summary["observable_intervention"]),
            ("共同可评估子集",summary["common_evaluable_subset"]),
            ("共同子集内有依据正常",summary["common_evaluable_normal"]),
            ("共同子集内有效干预",summary["common_evaluable_intervention"])]
    lines=["# 保存结果重新汇总", "", "本页仅由 `predictions.jsonl.gz` 重建；没有采集、规则变化或模型拟合。各检查是单条条件，不是完整模型或临时集成。",
           "",f'预定 {summary["planned_records"]} 条；实际尝试 {summary["actual_attempted"]} 条，流程核验执行 {summary["actual_executed"]} 条，收到并绑定原始记录 {summary["received_raw_records"]} 条，有效同期几何窗口 {summary["usable_geometry_windows"]} 条。',
           "", "表格各格为 **T/F/U/FAILED；明确覆盖分子/完整分母**。报警比例为该格 T/该行 n；U、FAILED 均不计正常正确。共同子集只辅助比较，不替代全体预定成员。",
           "", "| 分组 | n | 旧高度 >710 | 旧同Web关系 | 新Host几何上界 |", "|---|---:|---|---|---|"]
    for title,group in groups:lines.append(f'| {title} | {group["n"]} | '+" | ".join(metric(group,n) for n in CONDITIONS)+" |")
    lines += ["", "逐组三阶段证据：执行 `"+json.dumps(summary["trio_execution"],ensure_ascii=False)+"`；实际效果 `"+json.dumps(summary["trio_effects"],ensure_ascii=False)+"`；恢复 `"+json.dumps(summary["trio_recovery"],ensure_ascii=False)+"`。",
              "",f'正常证据排除 {len(summary["normal_evidence_exclusions"])} 条；新旧 Web 快照存在数值差异 {summary["legacy_new_web_snapshot_difference_records"]} 条，两个快照没有混合进同一关系。',
              "", "## 原始数值例子", "", "以下每个环境/过程取固定首轮变化位置，不挑选最好的检测结果。P 为视觉CSS尺寸×DPR×visual scale，H 为实际Host内容区域；完整每轴容差和原因在逐条预测中。",
              "", "| 环境/过程 | Web visual宽×高; DPR; scale | Host H宽×高 px | 投影P宽×高 px | ε宽×高 px | 新条件 |", "|---|---|---|---|---|---|"]
    def short(value):return f"{value:.4f}" if type(value) in (int,float) else str(value)
    for row in data:
        if row["phase"]!="change" or row["round"]!=1:continue
        fields=row["web_geometry_values"];host=row.get("host_before") or {}
        axes=row["conditions"]["R_HOST_GEOMETRY"].get("diagnostics",{}).get("axes",{})
        px="×".join(short(axes.get(a,{}).get("projected_physical_px")) for a in ("width","height"))
        tolerance="×".join(short(axes.get(a,{}).get("tolerance_px")) for a in ("width","height"))
        web="×".join(short(fields.get("visual_viewport_"+a)) for a in ("width","height"))+"; "+short(fields.get("device_pixel_ratio"))+"; "+short(fields.get("visual_viewport_scale"))
        content="×".join(short(host.get("content_"+a+"_px")) for a in ("width","height"))
        lines.append(f'| {row["environment"]}/{row["process_type"]} | {web} | {content} | {px} | {tolerance} | {row["conditions"]["R_HOST_GEOMETRY"]["state"]} |')
    counterexamples=[r for r in data if r.get("normal_basis",{}).get("supported") and r["conditions"]["R_HOST_GEOMETRY"]["state"]=="T"]
    lines += ["",f'新关系正常反例共 {len(counterexamples)} 条，全部保留；'+("、".join('`'+r["sample_id"]+'`' for r in counterexamples) if counterexamples else "当前小批次没有观察到。"),
              "", "同期不可用原因：`"+json.dumps(summary["geometry_unavailability"],ensure_ascii=False)+"`。",
              "", "完整原始引用、正常依据、操作/恢复证据、非目标变化、条件结果和原因见 `predictions.jsonl.gz`；分组统计见 `SUMMARY.json`。本批是三个环境中的重复观察，不能据此估计真机人群误报率。旧MTC/旧378条没有补造几何输入，也没有改旧分数。", ""]
    (out/"RESULTS.md").write_text("\n".join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("command",choices=("evaluate","summarize"))
    parser.add_argument("--output-dir",type=Path,default=HERE);parser.add_argument("--smoke",action="store_true")
    args=parser.parse_args();out=args.output_dir.resolve()
    value=evaluate(out,smoke=args.smoke) if args.command=="evaluate" else summarize(out/"smoke" if args.smoke else out,planned=6 if args.smoke else 72)
    print(json.dumps({k:value[k] for k in ("planned_records","received_raw_records","usable_geometry_windows","trio_recovery")}))


if __name__=="__main__":main()
