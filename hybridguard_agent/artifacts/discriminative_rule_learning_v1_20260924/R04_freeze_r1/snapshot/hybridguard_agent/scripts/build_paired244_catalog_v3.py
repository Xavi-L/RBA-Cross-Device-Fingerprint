#!/usr/bin/env python3
"""Close the remaining 25 items using the frozen, resource-limited study."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.mtc_closed_resource import candidates

CONFIG = ROOT / "hybridguard_agent/config"
STUDY = ROOT / "hybridguard_agent/artifacts/mtc_closed_resource_study_20260922"

REASONS = {
    "CORE-001": "现有主视图受完整配对/QC 准入选择，且没有独立重放事实；Native 缺失不能推出重放。现有资源无法验证，关闭。",
    "CORE-003": "已统计传感器数量与能力分布；缺少独立设备能力/攻击真值，不设数量阈值，仅保留描述。",
    "NW-004": "已统计 ABI/platform 对照；platform 是兼容性暴露，不是硬件 ABI 证明，不能把 32/64 位或字符串差异直接判异常。",
    "NW-008": "已统计 Native 内核可见 RAM 与 Web 内存暴露差异；口径及实现边界不同，不采用固定 GB 差值或相等规则。",
    "PHYS-001": "已统计硬件关键词；关键词缺少独立环境身份真值，不能验证模拟器检测能力，仅保留描述。",
    "PHYS-002": "已统计渲染关键词；软件回退不直接等于攻击，缺少可验证的后端环境标签，仅保留描述。",
    "SCENE-002": "组合项没有独立环境/攻击标签；若干弱线索相加不能完成验证。现有资源无法验证该场景结论，关闭。",
    "SCENE-003": "没有已核验的无头伪装两态及耗时控制证据；现有单次字段不足以验证组合结论，关闭。",
    "OFFDER-DISPLAY-001": "同一屏幕家族的双边候选已实测；官方字段语义不能保证 App 显示区域与 Web screen 等同，仅保留残差描述。",
    "OFFDER-MEMORY-001": "官方语义确认内核可见内存与受限近似物理内存口径不同；现有观察不能推出通用差值阈值，仅保留描述。",
    "OFFDER-SENSOR-001": "与 CORE-003 共用能力分布；官方 API 不规定真机必需的传感器总数，已有 P3 自洽规则继续单独保留。",
    "OFFDER-PLUGIN-001": "已统计插件/MIME 暴露；零同时可能为空或采集回退，非零也缺少跨版本攻击真值，仅保留描述。",
    "OFFDER-EMULATOR-001": "已统计 AVD/渲染/能力线索；官方机制不能代替当前样本的独立环境标签，不启用组合检测。",
    "PHYS-003": "缺少预热/负载可控的重复耗时记录；现有资源不再补采，关闭且不沿用 50/800ms。",
    "PHYS-004": "现有快照不能证明长期温度死值；无补采机会，关闭，不将同型号记录拼成时间序列。",
    "OFFDER-BATTERY-001": "无满足同实例/时间/状态条件的电池时间序列；无补采机会，关闭。",
    "OFFDER-PLAY-001": "现有 244 不含服务端验证的完整性 verdict；无新增数据，关闭。",
    "OFFDER-PLAY-002": "现有数据不含完整性 token 请求绑定及验证事实；无新增数据，关闭。",
    "OFFDER-KEY-001": "现有数据没有硬件证明链及挑战验证事实；无新增数据，关闭。",
    "OFFDER-BOOT-001": "现有 Build/su 观察不能代替经过验证的 boot/locked 证明；无新增数据，关闭。",
    "OFFDER-WEBSEC-001": "现有设置字段缺少同次导航 Origin/信任策略事实；无新增数据，关闭。",
}
CLOSED_SCENARIOS = {"CORE-001", "SCENE-002", "SCENE-003"}


def build_catalog_v3(study=STUDY):
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    summary = read(study / "summary.json")
    if summary.get("status") != "COMPLETE" or summary.get("protocol_version") != "mtc-closed-resource-study-v1":
        raise ValueError("Require completed resource-limited research")
    declared = read(study / "mtc_closed_resource_candidates.v1.json")["candidates"]
    if declared != candidates():
        raise ValueError("Candidate expressions drifted after research")
    freeze = read(study / "discovery_selection_FREEZE.json")
    admitted = {r["rule_id"]: r for r in read(study / "admitted_candidates.json")["candidates"]}
    if set(admitted) != set(summary["admitted_rule_ids"]) or not set(admitted) <= set(freeze["candidate_ids"]):
        raise ValueError("Admission not bound to the discovery freeze")
    for rid in admitted:
        if any(summary[s][rid]["screen_decision"] != "PASS_RESEARCH_SCREEN" for s in ("discovery", "development")):
            raise ValueError("Admitted candidate failed a fixed screen")
    catalog = copy.deepcopy(read(CONFIG / "paired244_rule_catalog.v2.json"))
    targets = [r for r in catalog["rules"] if r["status"] in {"NEEDS_RESEARCH", "NEEDS_DATA"}]
    if len(targets) != 25 or {r["rule_id"] for r in targets} != set(REASONS) | {c["rule_id"] for c in declared}:
        raise ValueError("Every remaining item must have one terminal resolution")
    resolutions = []
    for rule in targets:
        rid, previous = rule["rule_id"], rule["status"]
        if rid in admitted:
            candidate = admitted[rid]
            rule.update({k: copy.deepcopy(candidate[k]) for k in ("title", "implementation", "version", "predicate",
                        "dependencies", "parameters", "evidence_family", "source_lane", "limitations", "official_source_ids")})
            state = "ACTIVE"
            reason = "通过冻结发现/开发研究筛选，仅启用限定范围的一致性观察；旧广义风险结论未恢复。"
            rule.update(empirical_selection_applied=True, admission_mode="closed_resource_empirical_observation",
                        study_support={s: {k: summary[s][rid][k] for k in ("group_outcomes", "applicable_groups", "applicable_manufacturers")}
                                       for s in ("discovery", "development")})
        elif rid in {c["rule_id"] for c in declared}:
            state = "DESCRIPTIVE_ONLY"
            reason = "固定候选没有通过发现/开发研究筛选；全部反例保留，不放宽容差、不新增白名单，结束启用研究。"
        else:
            state = "CLOSED_UNVERIFIABLE" if previous == "NEEDS_DATA" or rid in CLOSED_SCENARIOS else "DESCRIPTIVE_ONLY"
            reason = REASONS[rid]
        rule.update(status=state, disposition_reason=reason, resolution_note=reason,
                    resource_constraint="EXISTING_DATA_ONLY_NO_COLLECTION", research_status="CLOSED",
                    closure_study="mtc-closed-resource-study-v1")
        if state != "ACTIVE":
            rule.update(version="closed-resource-disposition-v1", limitations=reason, predicate=None,
                        official_source_ids=[])
        for old_key in ("next_action_and_acceptance", "legacy_relation", "legacy_spec"):
            rule.pop(old_key, None)
        resolutions.append({"rule_id": rid, "previous_status": previous, "status": state, "reason": reason,
                            "collection_requested": False, "continued_research_requested": False})
    for rule in catalog["rules"]:
        if rule["status"] == "MERGED":
            rule["resolution_note"] = ("原容错已并入父项的最终描述性研究，不单独执行，父项不再等待研究或补采。"
                                       if rule["rule_id"] in {"TOL-002", "TOL-003"} else rule["disposition_reason"])
            rule.pop("next_action_and_acceptance", None)
    catalog.update(catalog_version="paired244-runtime-catalog-v3", previous_catalog_version="paired244-runtime-catalog-v2",
                   closure_version="mtc-closed-resource-study-v1", resource_policy="EXISTING_DATA_ONLY_NO_COLLECTION",
                   review_scope={"status": "CLOSED", "outstanding_items": 0, "all_claims_validated": False,
                                 "reserved_validation": "LOCKED", "detection_metrics": "NOT_EVALUATED"},
                   p4_status="RULE_RESEARCH_CLOSED_WITH_EXISTING_RESOURCES")
    policy = read(CONFIG / "paired244_browser_relations.v2.json")
    policy.update(policy_version="paired244-browser-relation-policy-v3", catalog_version=catalog["catalog_version"])
    resolution = {"version": "paired244-resource-closure-v1", "user_constraint": "Existing data only; no further collection or unresolved research loop.",
                  "study": str(study.relative_to(ROOT)), "remaining_items": 0, "entries": resolutions}
    return catalog, policy, resolution


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, default=STUDY)
    args = parser.parse_args()
    names = ("paired244_rule_catalog.v3.json", "paired244_browser_relations.v3.json", "paired244_resource_closure.v1.json")
    if any((CONFIG / n).exists() for n in names):
        raise ValueError("Never overwrite versioned closure")
    for name, value in zip(names, build_catalog_v3(args.study_dir)):
        (CONFIG / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
