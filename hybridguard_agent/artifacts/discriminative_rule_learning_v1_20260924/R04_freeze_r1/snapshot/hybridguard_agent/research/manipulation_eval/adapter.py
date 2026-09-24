"""S02: App177 conversion and structural checks, with no detector invocation.

Admission facts are read from S01 and copied to the evaluation side. Only
registered current-session fields reach the inference payload. Unknown labels
and failed/incomplete campaigns never select which source stages are adapted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import sys
import uuid

from hybridguard_agent.evidence.extractor import normalize_payload, sha256_value
from hybridguard_agent.evidence.paired244 import (
    STATES, VIEWS, field_contract, legacy_field_map, surface_of, valid_type,
)

ROOT = Path(__file__).resolve().parents[3]
VERSION = "app177-triplet-adapter-v1"
SCHEMA = "hybridguard-mtc-observation-v2"
STUDY = "formal_manipulation_v1_20260923"
SECTIONS = ("features", "field_status", "field_quality")
PAYLOAD_KEYS = frozenset((*SECTIONS, "record_schema_version", "adapter_version"))
APP_VIEWS = {k: v for k, v in VIEWS.items() if "browser67" not in v}
APP_VIEWS["NativePlusAppWeb151"] = VIEWS["NativeAppWeb151"]
MISSING = object()
FORBIDDEN_MODULES = ("hybridguard_agent.runtime", "hybridguard_agent.rules",
                     "hybridguard_agent.official_semantics", "hybridguard_agent.research.manipulation_eval.admission",
                     "hybridguard_agent.scripts.run_mtc_p6_history")


class AdaptationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(issue["code"] for issue in issues))


def issue(code, field=None, **details):
    return {"code": code, **({"field": field} if field is not None else {}), **details}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v, ensure_ascii=False, allow_nan=False) + "\n" for v in values))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@lru_cache(maxsize=1)
def mapping_contract():
    contract = {p: kind for p, kind in field_contract().items() if p.startswith("app.")}
    aliases = legacy_field_map()
    historical = json.loads((ROOT / "hybridguard_agent/schemas/expanded_v2.schema.json").read_text())
    if set(aliases) != set(historical["fields"]) or len(contract) != 177:
        raise ValueError("App177 mapping and legacy field names no longer agree")
    rows = [{"field": field, "source_logical_path": field.removeprefix("app."),
             "legacy_alias": alias, "type": contract[field], "surface": surface_of(field),
             "historical_bootstrap_types": historical["fields"][alias]}
            for alias, field in sorted(aliases.items(), key=lambda item: item[1])]
    return {"adapter_version": VERSION, "record_schema_version": SCHEMA,
            "field_count": len(rows), "surface_counts": dict(Counter(r["surface"] for r in rows)),
            "value_type_authority": "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
            "mapping_reused": "hybridguard_agent.evidence.paired244.legacy_field_map / field_contract",
            "normalization_reused": "hybridguard_agent.evidence.extractor.normalize_payload",
            "compatibility_reference": "scripts/run_mtc_p6_history.py::legacy_row (read only, never imported or executed)",
            "legacy_schema_note": historical["bootstrap_note"],
            "historical_numeric_type_differences": sum(r["historical_bootstrap_types"] != [r["type"]] for r in rows),
            "type_policy": "current CSV/runtime types; bootstrap integer observations do not narrow the current number contract",
            "status_policy": "exact canonical set of 177 registered fields, one explicit logical or legacy alias per field; six states only",
            "value_alias_policy": "accept flat/nested or equal dual aliases; reject conflicting registered aliases",
            "availability_policy": "never infer observed; typed unavailable values retained with source_unavailable; missing unavailable values stay null",
            "sentinel_policy": "observed device_memory/hardware_concurrency=0 retain zero and explicit status, quality=ambiguous_sentinel",
            "invalid_value_policy": "observed null/missing, wrong type, nonfinite or non-JSON field value rejects the stage",
            "inference_payload_keys": sorted(PAYLOAD_KEYS), "views": {k: list(v) for k, v in APP_VIEWS.items()},
            "fields": rows}


def at_path(value, path):
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def json_value_valid(value):
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(json_value_valid(child) for child in value)
    if type(value) is dict:
        return all(type(key) is str and json_value_valid(child) for key, child in value.items())
    return False


def equal_value(left, right):
    # JSON booleans must not compare equal to 0/1 through Python's bool subclass.
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(equal_value(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal_value(left[k], right[k]) for k in left)
    return left == right


def quality_for(field, value, state):
    if state != "observed":
        return "source_unavailable"
    if field.endswith((".device_memory", ".hardware_concurrency")) and value == 0:
        return "ambiguous_sentinel"
    return "observed_value"


def adapt_payload(raw):
    """Pure projection of one current raw payload; no IDs, facts, history or IO."""
    if not isinstance(raw, dict):
        raise AdaptationError([issue("INVALID_PAYLOAD_OBJECT")])
    errors = []
    if raw.get("schema_version") != "expanded-v2.2-status" or raw.get("collector_app") != "featureapp":
        errors.append(issue("UNSUPPORTED_RAW_CONTRACT"))
    for layer in ("android_native_data", "webview_data", "web_data"):
        if layer in raw and not isinstance(raw[layer], dict):
            errors.append(issue("INVALID_LAYER_SHAPE", layer))
    collection = raw.get("collection_status")
    if not isinstance(collection, dict):
        raise AdaptationError(errors + [issue("MISSING_EXPLICIT_FIELD_STATUS")])
    if collection.get("status_schema_version") != "field-status-v1" or collection.get("fixed_signal_count") != 177:
        errors.append(issue("INVALID_STATUS_HEADER"))
    supplied = collection.get("fields")
    if not isinstance(supplied, dict):
        raise AdaptationError(errors + [issue("MISSING_EXPLICIT_FIELD_STATUS")])
    specs = mapping_contract()["fields"]
    lookup = {key: spec["field"] for spec in specs for key in (spec["source_logical_path"], spec["legacy_alias"])}
    states, state_sources = {}, {}
    for key, state in supplied.items():
        field = lookup.get(key)
        if field is None:
            errors.append(issue("UNREGISTERED_STATUS_KEY", str(key)))
            continue
        if field in states:
            errors.append(issue("DUPLICATE_STATUS_ALIAS" if state == states[field] else "STATUS_ALIAS_CONFLICT", field,
                                source_keys=[state_sources[field], key]))
        else:
            states[field], state_sources[field] = state, key
        if not isinstance(state, str) or state not in STATES:
            errors.append(issue("INVALID_FIELD_STATUS", field))
    missing_states = sorted(set(s["field"] for s in specs) - set(states))
    if missing_states:
        errors.append(issue("MISSING_STATUS_KEYS", fields=missing_states))
    # Check values in only the two registered transport locations. Arbitrary
    # nested metadata can never win a leaf-name collision in normalize_payload.
    safe = {"collector_app": "featureapp", "schema_version": "expanded-v2.2-status",
            "android_native_data": {}, "webview_data": {}, "web_data": {},
            "collection_status": {"fields": {}}}
    for spec in specs:
        field, alias = spec["field"], spec["legacy_alias"]
        values = [(path, at_path(raw, path)) for path in dict.fromkeys((spec["source_logical_path"], alias))]
        present = [(path, value) for path, value in values if value is not MISSING]
        if len(present) > 1 and not equal_value(present[0][1], present[1][1]):
            errors.append(issue("VALUE_ALIAS_CONFLICT", field, source_paths=[p for p, _ in present]))
        value = present[0][1] if present else None
        state = states.get(field)
        if not json_value_valid(value):
            errors.append(issue("NONFINITE_OR_NON_JSON_VALUE", field))
        elif value is None:
            if state == "observed":
                errors.append(issue("OBSERVED_VALUE_MISSING_OR_NULL", field))
        else:
            try:
                typed = valid_type(value, spec["type"])
            except (ValueError, OverflowError):
                typed = False
            if not typed:
                errors.append(issue("INVALID_FIELD_TYPE", field, expected=spec["type"], actual=type(value).__name__))
        layer, leaf = alias.split(".")
        safe[layer][leaf] = copy.deepcopy(value)
        safe["collection_status"]["fields"][spec["source_logical_path"]] = state
    if errors:
        raise AdaptationError(errors)
    normalized, normalized_states = normalize_payload(safe)
    payload = {"record_schema_version": SCHEMA, "adapter_version": VERSION,
               "features": {}, "field_status": {}, "field_quality": {}}
    for spec in specs:
        field, alias = spec["field"], spec["legacy_alias"]
        layer, leaf = alias.split(".")
        value, state = normalized[layer][leaf], normalized_states[alias]
        payload["features"][field] = value
        payload["field_status"][field] = state
        payload["field_quality"][field] = quality_for(field, value, state)
    validate_inference_payload(payload)
    return payload


def selected_fields(view):
    if view not in APP_VIEWS:
        raise ValueError("S02 accepts App-only views; no Browser or Full244 fabrication")
    return {r["field"] for r in mapping_contract()["fields"] if r["surface"] in APP_VIEWS[view]}


def validate_inference_payload(payload, view="App177"):
    if set(payload) != PAYLOAD_KEYS or payload["record_schema_version"] != SCHEMA or payload["adapter_version"] != VERSION:
        raise ValueError("Inference envelope must contain only the fixed schema and current field sections")
    fields = selected_fields(view)
    for section in SECTIONS:
        if not isinstance(payload[section], dict) or set(payload[section]) != fields:
            raise ValueError(f"Inference {section} does not have the exact selected field set")
    contract = field_contract()
    for field in fields:
        value, state, quality = (payload[section][field] for section in SECTIONS)
        if not isinstance(state, str) or state not in STATES or not json_value_valid(value):
            raise ValueError(f"Invalid inference status/value: {field}")
        if value is None:
            if state == "observed":
                raise ValueError(f"Observed inference value missing: {field}")
        elif not valid_type(value, contract[field]):
            raise ValueError(f"Invalid inference value type: {field}")
        if quality != quality_for(field, value, state):
            raise ValueError(f"Inference quality contradicts the explicit status/value: {field}")


def project_payload(observation, view):
    """Mask before reading values/state/quality; drop all supplied derived data."""
    fields = sorted(selected_fields(view))
    projected = {"record_schema_version": SCHEMA, "adapter_version": VERSION,
                 **{name: {field: copy.deepcopy(observation[name][field]) for field in fields} for name in SECTIONS}}
    validate_inference_payload(projected, view)
    return projected


def test_log_result(text):
    final = text[text.rfind("COMMAND:"):] if "COMMAND:" in text else text
    count = re.search(r"Ran (\d+) tests?", final)
    passed = len(re.findall(r" \.\.\. ok$", final, re.MULTILINE))
    valid = bool(count and int(count.group(1)) == passed and re.search(r"^OK$", final, re.MULTILINE)
                 and "EXIT_CODE: 0" in final)
    return {"status": "PASS" if valid else "FAIL", "passed": passed,
            "reported_test_count": int(count.group(1)) if count else None}


def review_admission(directory):
    """Reconcile saved local records, without re-running S01 or adjudication."""
    facts = read_jsonl(directory / "facts_and_eligibility.jsonl")
    stages = read_jsonl(directory / "stage_accounting.jsonl")
    inventory = read_jsonl(directory / "material_inventory.jsonl")
    triplets = read_jsonl(directory / "triplet_registry.jsonl")
    validators = read_jsonl(directory / "validator_results.jsonl")
    summary = json.loads((directory / "SUMMARY.json").read_text())
    validation = json.loads((directory / "VALIDATION.json").read_text())
    groups = json.loads((directory / "environment_group_registry.json").read_text())["groups"]
    tests = test_log_result((directory / "FOCUSED_TESTS.txt").read_text())
    report = (directory / "STEP_REPORT.md").read_text()
    checks = {
        "saved_acceptance_pass": validation["status"] == "PASS" and all(validation["checks"].values()),
        "stage_fact_bijection": len(stages) == len(facts) == len({r["candidate_id"] for r in facts}) == summary["raw_rows"],
        "stage_candidate_refs_exact": all(len(r["candidate_refs"]) == 1 for r in stages)
            and {r["candidate_id"] for r in facts} == {c for r in stages for c in r["candidate_refs"]},
        "inventory_counts_match": len(inventory) == summary["candidate_bundles"] and sum(r["raw_rows"] for r in inventory) == len(stages),
        "eligibility_summary_match": all(summary[key] == sum(f[field] for f in facts) for key, field in (
            ("eligible_attack_stages", "eligible_detection"), ("eligible_pre_control_stages", "eligible_pre_control"),
            ("eligible_post_control_stages", "eligible_post_control"), ("eligible_temporal_control_stages", "eligible_temporal_control"))),
        "triplet_summary_match": sum(t["eligible_triplet"] for t in triplets) == summary["eligible_attack_triplets"],
        "temporal_unknown_preserved": all(f["no_intervention"]["status"] == "UNKNOWN" and not f["eligible_temporal_control"] for f in facts if f["kind"] == "control"),
        "environment_groups_match": len(groups) == summary["environment_groups"] and all(
            any(f["bundle_id"] in g["member_bundles"] and f["environment_group_id"] == g["group_id"] for g in groups) for f in facts),
        "saved_validator_counts_match": dict(Counter(f"{r['kind']}:{r['result']['status']}" for r in validators)) == summary["validator_results"],
        "test_log_matches_validation": tests["status"] == "PASS" and tests["passed"] == validation["synthetic_tests"]["passed"],
        "report_stage_counts_match": f"| 原始阶段 / 事实台账 / 成功绑定 | {summary['raw_rows']} / {summary['fact_rows']} / {summary['bound_phase_rows']} |" in report,
        "report_eligible_counts_match": f"| 准入攻击阶段 / 准入三态 | {summary['eligible_attack_stages']} / {summary['eligible_attack_triplets']} |" in report,
        "report_temporal_count_matches": f"| 准入时间对照阶段 | {summary['eligible_temporal_control_stages']} |" in report,
    }
    proof = {"status": "PASS" if all(checks.values()) else "CONFLICT", "checks": checks,
             "S01_rerun": False, "S01_relabelled": False, "source": str(directory), "S01_saved_tests": tests}
    if not all(checks.values()):
        raise ValueError("Local S01 records conflict: " + ", ".join(k for k, v in checks.items() if not v))
    return proof, inventory, stages, facts, summary


def cohort_of(fact, inventory):
    if fact["kind"] == "control":
        return "temporal_control_unknown"
    if not inventory["complete_nine_stage_candidate"]:
        return "incomplete_attempt"
    return "admitted_attack_triplet" if fact["eligible_triplet"] else "lower_evidence_attack"


def convert_unit(raw, admission_fact, metadata, source_issues=()):
    """Keep every evaluation unit, including identical inference payloads."""
    opaque = "sample-" + uuid.uuid4().hex
    rejection, inference, payload = None, None, None
    try:
        if source_issues:
            raise AdaptationError(list(source_issues))
        payload = adapt_payload(raw)
        inference = {"opaque_id": opaque, "payload": payload}
    except AdaptationError as error:
        rejection = {"adapter_version": VERSION, "opaque_id": opaque,
                     "candidate_id": admission_fact["candidate_id"], "raw_session_ref": admission_fact["raw_session_ref"],
                     "reason_codes": sorted({v["code"] for v in error.issues}), "issues": error.issues,
                     "label_availability_is_not_rejection_reason": True}
    status = "ADAPTED" if inference else "REJECTED"
    evaluation = {"opaque_id": opaque, "adapter_version": VERSION, **copy.deepcopy(metadata),
                  "candidate_id": admission_fact["candidate_id"], "bundle_id": admission_fact["bundle_id"],
                  "session_id": admission_fact["session_id"], "triplet_id": admission_fact["triplet_id"],
                  "phase": admission_fact["phase"], "environment_group_id": admission_fact["environment_group_id"],
                  "raw_session_ref": admission_fact["raw_session_ref"], "admission_fact": copy.deepcopy(admission_fact),
                  "adaptation_status": status}
    manifest = {"adapter_version": VERSION, "opaque_id": opaque, "candidate_id": admission_fact["candidate_id"],
                "status": status, "input_ref": None, "rejection_ref": None, "field_count": len(payload["features"]) if payload else 0,
                "source_payload_binding": copy.deepcopy(admission_fact["payload_binding"]),
                "source_raw_ref": admission_fact["raw_session_ref"], "evaluation_ref": None}
    return inference, manifest, evaluation, rejection


def source_path(root, reference):
    path = (root / reference.split("#", 1)[0]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise AdaptationError([issue("SOURCE_REFERENCE_OUTSIDE_ATTACK_REPOSITORY")])
    return path


def unique_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def parse_source_line(path, line, cache):
    try:
        if path not in cache:
            cache[path] = path.read_text().splitlines()
        text = cache[path][line - 1]
        value = json.loads(text, object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            raise ValueError("source row must be a JSON object")
        return value
    except (OSError, ValueError, IndexError) as error:
        raise AdaptationError([issue("SOURCE_ROW_UNREADABLE", source_ref=f"{path}#line={line}", detail=str(error))]) from error


def collect_source(stage, fact, inventory, attack_root, cache):
    metadata = {"cohort": cohort_of(fact, inventory), "sequence_index": None, "round": None,
                "material_history_ref": f"../01_admission/material_inventory.jsonl#bundle_id={fact['bundle_id']}",
                "original_release": inventory["original_release"], "S01_fact_ref": f"../01_admission/facts_and_eligibility.jsonl#candidate_id={fact['candidate_id']}"}
    try:
        path = source_path(attack_root, inventory["raw_ref"])
        raw = parse_source_line(path, stage["line"], cache)
        if (raw.get("session_id") != stage["session_id"] or stage["session_id"] != fact["session_id"]
                or fact["payload_binding"].get("raw_line") != stage["line"]
                or fact["raw_session_ref"] != inventory["raw_ref"] + "#session_id=" + str(stage["session_id"])):
            raise AdaptationError([issue("SOURCE_SESSION_OR_LINE_BINDING_MISMATCH")])
        if fact["payload_binding"]["status"] != "BOUND" or sha256_value(raw) != fact["payload_binding"]["actual_payload_digest"]:
            raise AdaptationError([issue("SOURCE_PAYLOAD_BINDING_MISMATCH")])
        manifest_path = source_path(attack_root, fact["manifest_ref"])
        line = int(fact["manifest_ref"].rsplit("#line=", 1)[1])
        sidecar = parse_source_line(manifest_path, line, cache)
        relation = sidecar.get("pair", sidecar.get("triplet", {}))
        role = relation.get("pair_role", relation.get("control_role"))
        triplet = relation.get("pair_id", relation.get("triplet_id"))
        if sidecar.get("session_id") != fact["session_id"] or role != fact["phase"] or triplet != fact["triplet_id"]:
            raise AdaptationError([issue("EVALUATION_PHASE_BINDING_MISMATCH")])
        run_path = source_path(attack_root, inventory["run_ref"])
        if run_path not in cache:
            cache[run_path] = json.loads(run_path.read_text())
        sessions = [s for s in cache[run_path]["sessions"] if s.get("session_id") == fact["session_id"]]
        if len(sessions) != 1:
            raise AdaptationError([issue("RUN_SESSION_NOT_UNIQUE")])
        session = sessions[0]
        metadata.update(sequence_index=relation.get("sequence_index"), round=relation.get("round", session.get("round")),
                        config_id=(fact.get("original_attack_annotation") or {}).get("config_id"),
                        tool=(fact.get("original_attack_annotation") or {}).get("tool_name"),
                        configuration_id=(fact.get("original_attack_annotation") or {}).get("configuration_id"),
                        collector_install_id=raw.get("collection_manifest", {}).get("collector_install_id"),
                        manifest_ref=fact["manifest_ref"], run_ref=inventory["run_ref"])
        return raw, metadata, []
    except AdaptationError as error:
        return {}, metadata, error.issues
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {}, metadata, [issue("EVALUATION_SOURCE_UNREADABLE", detail=str(error))]


def signatures(paths):
    return {str(p): {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns} if p.is_file() else None for p in sorted(set(paths))}


def association_rows(evaluations):
    grouped = defaultdict(list)
    for row in evaluations:
        grouped[(row["bundle_id"], row["triplet_id"])].append(row)
    result = []
    for (bundle, triplet), rows in sorted(grouped.items()):
        expected = ["clean_pre", "control_mid", "clean_post"] if rows[0]["admission_fact"]["kind"] == "control" else ["clean_pre", "attack", "clean_post"]
        phases = [r["phase"] for r in rows]
        result.append({"bundle_id": bundle, "triplet_id": triplet, "cohort": rows[0]["cohort"],
                       "phases": [{"opaque_id": r["opaque_id"], "phase": r["phase"], "sequence_index": r["sequence_index"],
                                   "round": r["round"], "adaptation_status": r["adaptation_status"]} for r in rows],
                       "complete_source_triplet": len(rows) == 3 and Counter(phases) == Counter(expected),
                       "missing_source_phases": sorted(set(expected) - set(phases)),
                       "all_available_stages_adapted": all(r["adaptation_status"] == "ADAPTED" for r in rows)})
    return result


def render_report(summary, validation):
    lines = ["# S02 三态 App177 与时间对照兼容适配", "",
             f"工程验收：**{validation['status']}**。本步仅转换与结构校验；真实样本没有执行检测规则、报警策略或性能评价。", "",
             "## 依赖与范围", "",
             "本地 S01 报告、验证记录、13 项最终聚焦测试与材料/事实/阶段/三态/环境台账一致；未发现实质冲突。S01 未重跑、未重裁标签。依赖状态中遗留的未执行提示已按本地验收事实清除。",
             "执行前 S01 已提交并推送；提交及远端确认记录在 EXECUTION_STATUS.json。S02 结果保持本地，停止于本步。", "",
             "## 全量阶段去向", "", "| 项目 | 数量 |", "|---|---:|",
             f"| S01 原始阶段 | {summary['input_stages']} |",
             f"| 转换成功 | {summary['converted']} |", f"| 明确拒绝 | {summary['rejected']} |",
             f"| 唯一评估单元 | {summary['evaluation_units']} |", "",
             "`input_manifest.jsonl` 对每条 S01 raw 阶段给出唯一去向，并连接成功输入或拒绝记录以及评估侧表。缺少可用标签不是适配拒绝理由。", "",
             "| Cohort（阶段） | 输入 | 成功 | 拒绝 |", "|---|---:|---:|---:|"]
    for cohort, counts in summary["cohorts"].items():
        lines.append(f"| {cohort} | {counts['input']} | {counts['converted']} | {counts['rejected']} |")
    lines.extend(["", "拒绝理由计数：`" + json.dumps(summary["rejection_reasons"], ensure_ascii=False) + "`。空对象表示没有适配拒绝，不表示证据均已准入。", "",
                  "## 阶段关联与包级历史", "",
                  f"保留 {summary['association_groups']} 组实际阶段关联：{summary['complete_attack_triplets']} 组完整攻击三态、{summary['complete_temporal_triplets']} 组完整时间对照三时点、{summary['incomplete_associations']} 组原有不完整尝试。阶段计数：`{json.dumps(summary['phases'], ensure_ascii=False)}`。",
                  "`phase_associations.json` 保留所有已有阶段及 sequence_index/round；完整组的 clean_post 均保留。不完整 CDP 尝试仍只有 clean_pre，缺少 attack/clean_post；Playwright 空失败包仍为 0 阶段。未制造阶段以补齐三态。31 包历史通过 `bundle_history.json` 引用 S01 inventory，失败和缺件状态不被转换结果覆盖。",
                  f"相同推理 payload 的重复内容组 {summary['identical_payload_groups']} 个，共涉及 {summary['units_in_identical_payload_groups']} 个独立单元；均未去重。", "",
                  "## 字段、遮蔽与隔离", "",
                  "复用 paired244 的 App177 logical/flat 映射、当前 CSV 字段类型和 normalize_payload。三个状态相关映射均为完整且精确的 177 键；检查别名冲突、六态状态、类型及非有限值。旧 bootstrap JSON 有 54 个数字类型描述与当前 CSV 的 number 不同，沿用当前运行时 CSV，不将历史 integer 观测收窄为新约束。",
                  "合法 false、0、空列表原样保留；未观测状态不因有值升级为 observed。observed 的 device_memory/hardware_concurrency 零哨兵保留零及状态，质量标记 ambiguous_sentinel。无状态或观测值缺失不填造。",
                  "推理文件仅以随机 opaque_id 作外部关联键；其 payload 仅含固定 record_schema_version、adapter_version、features、field_status、field_quality。所有值来自当前阶段的注册字段，不含 Browser。标签、phase、工具/config、路径、session/install/group、执行回执、预期修改和未来 post 都在独立 evaluation_index 或其 S01/源引用中。字段本身合法的 UA 字符串不按工具关键词清洗。",
                  f"合成聚焦测试：**{validation['synthetic_tests']['passed']} 项通过**，详见 FOCUSED_TESTS.txt。覆盖 flat/nested 等价、完整键集合、别名冲突、类型/非有限值、六态/零哨兵/空列表、元数据置换、未来 post 独立性、隐藏层值/状态/质量/派生摘要移除、同内容不同单元和明确拒绝。真实材料仅进行转换、源绑定与结构校验。",
                  f"全部结构检查：`{json.dumps(validation['checks'], ensure_ascii=False)}`。", "",
                  "## 仍保留的事实限制", "",
                  "54 条时间对照阶段的 no_intervention 仍为 UNKNOWN，eligible_temporal_control 全为 false，不获得 FPR 资格。45 条较低证据攻击阶段仍缺直接日志等证据；转换成功不将其升级。原有 54 个攻击阶段/三态准入与前后各 54 条声明表面对照资格原样保留，不扩大到普遍正常标签。3 个环境关联组不是已核验独立物理设备数。",
                  "未启动补采或补日志；不修改阈值，不生成真实 predictions，不计算 TPR/FPR；S03–S12 未执行。P0–P6、S01 和攻击仓库原始材料只读。", ""])
    return "\n".join(lines)


def prepare_adaptation(admission_dir, attack_root, output, test_log):
    """Convert the saved stage ledger, never select on task eligibility."""
    admission_dir, attack_root, output = (p.resolve() for p in (admission_dir, attack_root, output))
    if output.exists() or output.is_relative_to(admission_dir) or output.is_relative_to(attack_root):
        raise ValueError("Use a new output directory outside the read-only admission and source material")
    proof, inventory, stages, facts, admission_summary = review_admission(admission_dir)
    test_text = test_log.read_text()
    tests = test_log_result(test_text)
    if tests["status"] != "PASS":
        raise ValueError("S02 focused synthetic tests must pass before real conversion")
    proof["local_status_policy"] = "saved S01 acceptance is authoritative; no remote progress replacement or replay"
    original_triplets = read_jsonl(admission_dir / "triplet_registry.jsonl")
    sources = [p for p in admission_dir.rglob("*") if p.is_file()]
    sources.extend(source_path(attack_root, row[key]) for row in inventory for key in ("raw_ref", "manifest_ref", "run_ref"))
    before = signatures(sources)
    facts_by_id = {f["candidate_id"]: f for f in facts}
    bundles = {r["bundle_id"]: r for r in inventory}
    inputs, manifests, evaluations, rejections, accounting, cache = [], [], [], [], [], {}
    output.mkdir(parents=True)
    write_json(output / "DEPENDENCY_REVIEW.json", proof)
    (output / "FOCUSED_TESTS.txt").write_text(test_text)
    write_json(output / "field_mapping.json", mapping_contract())
    try:
        for stage in stages:
            fact = facts_by_id[stage["candidate_refs"][0]]
            raw, metadata, errors = collect_source(stage, fact, bundles[stage["bundle_id"]], attack_root, cache)
            inference, manifest, evaluation, rejection = convert_unit(raw, fact, metadata, errors)
            if inference is not None:
                inputs.append(inference)
                manifest["input_ref"] = f"inference_inputs.jsonl#line={len(inputs)}"
            if rejection is not None:
                rejections.append(rejection)
                manifest["rejection_ref"] = f"adapter_rejections.jsonl#line={len(rejections)}"
            evaluations.append(evaluation)
            manifest["evaluation_ref"] = f"evaluation_index.jsonl#line={len(evaluations)}"
            manifests.append(manifest)
            accounting.append({"S01_raw_stage": copy.deepcopy(stage), "candidate_id": fact["candidate_id"],
                               "opaque_id": manifest["opaque_id"], "status": manifest["status"],
                               "manifest_ref": f"input_manifest.jsonl#line={len(manifests)}"})
    except Exception as error:
        write_json(output / "RUN_FAILURE.json", {"status": "FAIL", "detail": str(error), "completed_stages": len(manifests)})
        raise
    for name, rows in (("inference_inputs", inputs), ("input_manifest", manifests), ("evaluation_index", evaluations),
                       ("adapter_rejections", rejections), ("stage_accounting", accounting)):
        write_jsonl(output / (name + ".jsonl"), rows)
    associations = association_rows(evaluations)
    write_json(output / "phase_associations.json", associations)
    history = [{"bundle_id": r["bundle_id"], "S01_inventory_ref": f"../01_admission/material_inventory.jsonl#line={i}",
                "raw_stage_count": r["raw_rows"], "material_disposition": r["material_disposition"],
                "run_status": r["run_status"], "fabricated_stages": 0} for i, r in enumerate(inventory, 1)]
    write_json(output / "bundle_history.json", history)
    # Re-read the deliverables to verify persisted coverage, not just loop counters.
    saved_inputs = read_jsonl(output / "inference_inputs.jsonl")
    saved_manifest = read_jsonl(output / "input_manifest.jsonl")
    saved_eval = read_jsonl(output / "evaluation_index.jsonl")
    saved_rejections = read_jsonl(output / "adapter_rejections.jsonl")
    for row in saved_inputs:
        if set(row) != {"opaque_id", "payload"}:
            raise ValueError("Inference row metadata isolation failed")
        validate_inference_payload(row["payload"])
    expected_ids = Counter(f["candidate_id"] for f in facts)
    success_ids = {r["opaque_id"] for r in saved_inputs}
    rejected_ids = {r["opaque_id"] for r in saved_rejections}
    eval_by_id = {r["opaque_id"]: r for r in saved_eval}
    actual_groups = {(r["bundle_id"], r["triplet_id"]): [p["phase"] for p in r["phases"]] for r in associations}
    forbidden_imports = sorted(name for name in sys.modules if any(name == p or name.startswith(p + ".") for p in FORBIDDEN_MODULES))
    checks = {
        "S01_saved_records_consistent": proof["status"] == "PASS",
        "all_262_raw_stages_accounted": len(stages) == len(saved_manifest) == len(saved_eval) == len(accounting) == 262,
        "unique_candidate_coverage": Counter(r["candidate_id"] for r in saved_manifest) == expected_ids
            == Counter(r["candidate_id"] for r in saved_eval) and set(expected_ids.values()) == {1},
        "unique_raw_stage_coverage": len({(r["bundle_id"], r["line"]) for r in stages}) == len(stages)
            and [r["S01_raw_stage"] for r in read_jsonl(output / "stage_accounting.jsonl")] == stages,
        "success_rejection_partition": not (success_ids & rejected_ids)
            and len(success_ids) + len(rejected_ids) == len(saved_inputs) + len(saved_rejections) == len(stages)
            and success_ids | rejected_ids == {r["opaque_id"] for r in saved_manifest} == set(eval_by_id),
        "manifest_references_exact": all(
            (r["status"] == "ADAPTED" and r["opaque_id"] in success_ids and r["rejection_ref"] is None
             and saved_inputs[int(r["input_ref"].split("=")[-1]) - 1]["opaque_id"] == r["opaque_id"])
            or (r["status"] == "REJECTED" and r["opaque_id"] in rejected_ids and r["input_ref"] is None
                and saved_rejections[int(r["rejection_ref"].split("=")[-1]) - 1]["opaque_id"] == r["opaque_id"])
            for r in saved_manifest),
        "all_rejections_have_structural_reasons": all(r["reason_codes"] and r["issues"] and r["label_availability_is_not_rejection_reason"] for r in saved_rejections),
        "S01_facts_eligibility_groups_unchanged": all(r["admission_fact"] == facts_by_id[r["candidate_id"]]
            and all(r[k] == r["admission_fact"][k] for k in ("phase", "session_id", "triplet_id", "environment_group_id")) for r in saved_eval),
        "temporal_unknown_not_promoted": all(r["admission_fact"]["no_intervention"]["status"] == "UNKNOWN"
            and not r["admission_fact"]["eligible_temporal_control"] for r in saved_eval if r["cohort"] == "temporal_control_unknown"),
        "all_original_phase_associations_preserved": len(actual_groups) == len(original_triplets)
            and all(Counter(actual_groups.get((r["bundle_id"], r["triplet_id"]), [])) == Counter(r["phase_roles"]) for r in original_triplets),
        "bundle_history_preserved_without_fabrication": len(history) == len(inventory)
            and all(sum(r["bundle_id"] == h["bundle_id"] for r in saved_eval) == h["raw_stage_count"] for h in history),
        "inference_payload_allowlist_and_177_fields": True,  # validated above; exceptions fail the command
        "focused_synthetic_tests_passed": tests["status"] == "PASS",
        "sources_and_S01_unchanged": signatures(sources) == before,
        "no_detector_or_admission_runtime_imported": not forbidden_imports,
        "no_prediction_artifacts": not any("prediction" in p.name.lower() for p in output.rglob("*")),
    }
    cohorts = {}
    for row in saved_eval:
        counts = cohorts.setdefault(row["cohort"], {"input": 0, "converted": 0, "rejected": 0})
        counts["input"] += 1
        counts["converted" if row["adaptation_status"] == "ADAPTED" else "rejected"] += 1
    payload_counts = Counter(json.dumps(r["payload"], sort_keys=True, ensure_ascii=False) for r in saved_inputs)
    summary = {"step": "S02", "adapter_version": VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
               "input_stages": len(stages), "converted": len(saved_inputs), "rejected": len(saved_rejections),
               "evaluation_units": len(saved_eval), "cohorts": cohorts,
               "rejection_reasons": dict(Counter(c for r in saved_rejections for c in r["reason_codes"])),
               "phases": dict(Counter(r["phase"] for r in saved_eval)), "association_groups": len(associations),
               "complete_attack_triplets": sum(r["complete_source_triplet"] and r["cohort"] != "temporal_control_unknown" for r in associations),
               "complete_temporal_triplets": sum(r["complete_source_triplet"] and r["cohort"] == "temporal_control_unknown" for r in associations),
               "incomplete_associations": sum(not r["complete_source_triplet"] for r in associations),
               "empty_bundles": [r["bundle_id"] for r in history if r["raw_stage_count"] == 0],
               "identical_payload_groups": sum(n > 1 for n in payload_counts.values()),
               "units_in_identical_payload_groups": sum(n for n in payload_counts.values() if n > 1),
               "field_status_counts": dict(Counter(v for r in saved_inputs for v in r["payload"]["field_status"].values())),
               "field_quality_counts": dict(Counter(v for r in saved_inputs for v in r["payload"]["field_quality"].values())),
               "S01_eligibility_retained": {k: v for k, v in admission_summary.items() if k.startswith("eligible_")},
               "temporal_no_intervention": "UNKNOWN", "environment_groups": admission_summary["environment_groups"],
               "performance_status": "NOT_EVALUATED", "detector_runs": 0, "prediction_rows": 0, "model_calls": 0,
               "threshold_changes": 0, "S01_rerun": False, "S03_started": False}
    validation = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "synthetic_tests": tests,
                  "scope": "real inputs: conversion and structural checks only; synthetic fixtures: field/masking/isolation tests",
                  "forbidden_modules_loaded": forbidden_imports, "real_detection_calls": 0, "real_predictions": 0,
                  "real_TPR_FPR_calculated": False, "missing_labels_cause_rejection": False}
    write_json(output / "source_snapshot.json", {"method": "size/mtime read-only check; per-stage S01 payload binding reused",
                                                "files": before, "unchanged": checks["sources_and_S01_unchanged"]})
    write_json(output / "SUMMARY.json", summary)
    write_json(output / "VALIDATION.json", validation)
    (output / "STEP_REPORT.md").write_text(render_report(summary, validation))
    if validation["status"] != "PASS":
        raise ValueError("S02 structural acceptance failed: " + ", ".join(k for k, v in checks.items() if not v))
    return {"status": validation["status"], "output": str(output), **summary}
