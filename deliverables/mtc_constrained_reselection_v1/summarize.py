#!/usr/bin/env python3
"""Rebuild the MTC constrained comparison using saved artifacts only.

This module deliberately does not import a data loader, predictor or selector.
It preserves failures and unknown outputs in every denominator and never pools
the three evaluations of the same MTC record into independent observations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECISIONS = ("MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE", "FAILED", "EMPTY_MODEL")
SCHEMES = ("BASELINE", "A", "B")
SUBSETS = ("discovery", "development", "reserved_validation", "paired_redundant", "app_only")
SCHEME_NAMES = {"BASELINE": "原 CAP8", "A": "A 完整候选池", "B": "B 历史 MTC 兼容候选模型"}
SUBSET_NAMES = {"discovery": "discovery（训练）", "development": "development（评价）",
                "reserved_validation": "reserved_validation（评价）",
                "paired_redundant": "配对重复（补充）", "app_only": "App-only（补充）"}


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "ratio": numerator / denominator if denominator else None}


def fraction(value):
    suffix = f'（{value["ratio"]:.2%}）' if value["ratio"] is not None else "（无分母）"
    return f'{value["numerator"]}/{value["denominator"]}{suffix}'


def count_rows(rows):
    """Count all outcomes; EMPTY_MODEL and FAILED are never normal successes."""
    c = Counter(row["decision"] for row in rows)
    unexpected = set(c) - set(DECISIONS)
    if unexpected:
        raise ValueError("UNRECOGNIZED_DECISION:" + ",".join(sorted(unexpected)))
    normal = [row for row in rows if row.get("normal_basis", {}).get("supported") is True]
    n = len(rows)
    alerts, no_alert = c["MANIPULATION_ALERT"], c["NO_ALERT"]
    return {"planned_records": n, "processed_records": n - c["FAILED"], "records": n,
            "alerts": alerts, "no_alert": no_alert, "unknown": c["INSUFFICIENT_EVIDENCE"],
            "failed": c["FAILED"], "empty_model": c["EMPTY_MODEL"],
            "defined_coverage": ratio(alerts + no_alert, n),
            "observed_alert_proportion": ratio(alerts, n), "normal_records": len(normal),
            "normal_observed_alert_proportion": ratio(sum(r["decision"] == "MANIPULATION_ALERT" for r in normal), len(normal)),
            "unsupported_normal_basis_records": n - len(normal), "decisions": dict(c)}


def validate_saved_members(rows, settings):
    """Compare to the prespecified saved list, including a jointly missing row."""
    if not settings.get("folds"):
        return
    expected = {}
    schemes = ["BASELINE", *settings.get("schemes", {})]
    for scheme in schemes:
        for fold in settings["folds"]:
            fid = fold["fold_id"]
            expected[(scheme, fid, "controlled", "heldout")] = set(fold["outer_test_ids"])
            for subset, ids in {**settings.get("mtc_primary_ids", {}), **settings.get("supplementary_ids", {})}.items():
                expected[(scheme, fid, "mtc", subset)] = set(ids)
    actual = defaultdict(set)
    for row in rows:
        actual[(row["scheme"], row["fold_id"], row["dataset"], row["subset"])].add(row["sample_id"])
    for key in set(expected) | set(actual):
        if expected.get(key, set()) != actual.get(key, set()):
            raise ValueError("SAVED_SETTINGS_MEMBER_MISMATCH:" + repr(key))


def _model_os(row):
    profile = row.get("profile") or {}
    return (profile.get("manufacturer"), profile.get("model"), profile.get("android_release")) if profile else None


def _clause_id(rule):
    return rule.get("clause_id") or rule.get("id") or (str(rule.get("atom_id")) + ":" + str(rule.get("polarity", "POSITIVE")))


def _rules(rows):
    stats = {}
    for row in rows:
        rules = row.get("rules", [])
        triggered = [rule for rule in rules if rule.get("state") == "T"]
        for rule in rules:
            cid = _clause_id(rule)
            stat = stats.setdefault(cid, {"atom_id": rule.get("atom_id"), "polarity": rule.get("polarity"),
                                          "T": 0, "F": 0, "U": 0, "FAILED": 0,
                                          "unique_alerts": 0, "unknown_reasons": Counter()})
            state = rule.get("state", "FAILED")
            stat[state if state in ("T", "F", "U") else "FAILED"] += 1
            stat["unique_alerts"] += state == "T" and len(triggered) == 1 and row["decision"] == "MANIPULATION_ALERT"
            if state not in ("T", "F"):
                stat["unknown_reasons"][rule.get("reason") or "UNSPECIFIED"] += 1
    return stats


def _controlled(rows):
    attack = [row for row in rows if row.get("stage") == "attack"]
    clean = [row for row in rows if row.get("stage") in ("clean_pre", "clean_post")]
    if len(attack) + len(clean) != len(rows):
        raise ValueError("CONTROLLED_STAGE_MISSING_OR_INVALID")
    configs = {}
    for config in sorted({row["configuration_id"] for row in rows}):
        current = [row for row in rows if row["configuration_id"] == config]
        ca = count_rows([row for row in current if row["stage"] == "attack"])
        cc = count_rows([row for row in current if row["stage"] != "attack"])
        configs[config] = {"attack": ca, "clean": cc, "all": count_rows(current)}
    rates = [v["attack"]["observed_alert_proportion"]["ratio"] for v in configs.values() if v["attack"]["records"]]
    return {"attack": count_rows(attack), "clean": count_rows(clean), "all": count_rows(rows),
            "macro_attack_detection": sum(rates) / len(rates) if rates else None,
            "configurations": configs, "rules": _rules(rows)}


def _group_stats(rows):
    result = {}
    for group in ("manufacturer", "android_release", "collector_version_code"):
        buckets = defaultdict(list)
        for row in rows:
            value = row.get(group) if group == "collector_version_code" else (row.get("profile") or {}).get(group)
            buckets[str(value if value is not None else "UNKNOWN")].append(row)
        result[group] = {key: count_rows(values) for key, values in sorted(buckets.items())}
    return result


def summarize_rows(rows):
    """Validate alignment before comparing; baseline and new schemes share IDs."""
    seen = set()
    members = defaultdict(set)
    scheme_rows = defaultdict(list)
    for row in rows:
        key = (row["scheme"], row["fold_id"], row["dataset"], row["subset"], row["sample_id"])
        if key in seen:
            raise ValueError("DUPLICATE_PREDICTION:" + repr(key))
        seen.add(key)
        if row["dataset"] not in ("controlled", "mtc"):
            raise ValueError("UNRECOGNIZED_DATASET")
        members[(row["scheme"], row["fold_id"], row["dataset"], row["subset"])].add(row["sample_id"])
        scheme_rows[row["scheme"]].append(row)
    schemes = sorted(scheme_rows, key=lambda s: (SCHEMES.index(s) if s in SCHEMES else len(SCHEMES), s))
    partitions = sorted({key[1:] for key in members})
    for part in partitions:
        expected = members[(schemes[0], *part)]
        for scheme in schemes[1:]:
            if members[(scheme, *part)] != expected:
                raise ValueError("COMPARISON_MEMBER_MISMATCH:" + repr((scheme, *part)))
    summary = {"schema_version": "mtc-constrained-summary-v1", "schemes": {}, "alignment": "EXACT_MEMBERS_PER_FOLD_AND_SUBSET",
               "inventory": {"unique_controlled_records": len({row["sample_id"] for row in rows if row["dataset"] == "controlled"}),
                             "unique_mtc_records": len({row["sample_id"] for row in rows if row["dataset"] == "mtc"}),
                             "mtc_model_os_combinations": len({_model_os(row) for row in rows if row["dataset"] == "mtc" and _model_os(row)}),
                             "model_evaluations": len(rows)}, "comparisons": {}}
    for scheme in schemes:
        current = scheme_rows[scheme]
        controlled = [row for row in current if row["dataset"] == "controlled"]
        if len({row["sample_id"] for row in controlled}) != len(controlled):
            raise ValueError("CONTROLLED_OOF_RECORD_REPEATED_ACROSS_FOLDS")
        item = {"controlled_oof": _controlled(controlled), "folds": {}, "mtc_agreement": {}}
        for fold in sorted({row["fold_id"] for row in current}):
            fold_rows = [row for row in current if row["fold_id"] == fold]
            model_ids = sorted({row["model_id"] for row in fold_rows})
            if len(model_ids) != 1:
                raise ValueError("MULTIPLE_MODELS_IN_ONE_SCHEME_FOLD")
            f = {"model_id": model_ids[0], "controlled": _controlled([row for row in fold_rows if row["dataset"] == "controlled"]), "mtc": {}}
            for subset in sorted({row["subset"] for row in fold_rows if row["dataset"] == "mtc"}, key=lambda s: (SUBSETS.index(s) if s in SUBSETS else 99, s)):
                subset_rows = [row for row in fold_rows if row["dataset"] == "mtc" and row["subset"] == subset]
                f["mtc"][subset] = {**count_rows(subset_rows), "model_os_combinations": len({_model_os(row) for row in subset_rows if _model_os(row)}),
                                      "rules": _rules(subset_rows), "groups": _group_stats(subset_rows)}
            item["folds"][fold] = f
        for subset in sorted({row["subset"] for row in current if row["dataset"] == "mtc"}):
            per_sample = defaultdict(list)
            for row in current:
                if row["dataset"] == "mtc" and row["subset"] == subset:
                    per_sample[row["sample_id"]].append(row)
            different = [sid for sid, values in per_sample.items() if len(values) != len(item["folds"]) or len({v["decision"] for v in values}) != 1]
            item["mtc_agreement"][subset] = {"unique_records": len(per_sample), "models": len(item["folds"]),
                                             "same_decision_records": len(per_sample) - len(different), "different_decision_ids": sorted(different)}
        summary["schemes"][scheme] = item
    if "BASELINE" in summary["schemes"]:
        base = summary["schemes"]["BASELINE"]
        for scheme, item in summary["schemes"].items():
            if scheme == "BASELINE":
                continue
            compare = {"controlled_attack_alert_change": item["controlled_oof"]["attack"]["alerts"] - base["controlled_oof"]["attack"]["alerts"], "mtc_by_fold": {}, "selected_rule_changes": {}}
            for fold, f in item["folds"].items():
                compare["mtc_by_fold"][fold] = {subset: {"denominator": s["records"],
                    "alert_change": s["alerts"] - base["folds"][fold]["mtc"][subset]["alerts"],
                    "no_alert_change": s["no_alert"] - base["folds"][fold]["mtc"][subset]["no_alert"],
                    "unknown_change": s["unknown"] - base["folds"][fold]["mtc"][subset]["unknown"]} for subset, s in f["mtc"].items()}
                old_rules = set(base["folds"][fold]["controlled"]["rules"])
                new_rules = set(f["controlled"]["rules"])
                compare["selected_rule_changes"][fold] = {"removed": sorted(old_rules - new_rules), "added": sorted(new_rules - old_rules), "retained": sorted(old_rules & new_rules)}
            summary["comparisons"][scheme] = compare
    return summary


def candidate_overview(training):
    candidates = training.get("candidate_statistics", [])
    admission = Counter(reason for c in candidates for reason in c.get("admission_reasons", []))
    singleton = Counter(reason for c in candidates for reason in c.get("singleton_budget_reasons", []))
    selected = [c for c in candidates if c.get("selected")]
    return {"expanded_literals": len(candidates), "admitted": sum(bool(c.get("admitted")) for c in candidates),
            "selected": len(selected), "admission_reasons": dict(admission), "singleton_budget_reasons": dict(singleton),
            "selected_clauses": [c["clause_id"] for c in selected], "whole_set_result": training.get("whole_set_result", {}),
            "selected_mtc_unverified": [c["clause_id"] for c in selected if (c.get("mtc_normal") or {}).get("defined", 0) == 0],
            "selected_training_evidence": [{"clause_id": c["clause_id"], "controlled_clean": c.get("controlled_clean", {}),
                "controlled_attack": c.get("controlled_attack", {}), "mtc_normal": c.get("mtc_normal", {})} for c in selected],
            "display_height_candidates": [{"clause_id": c["clause_id"], "selected": c.get("selected"),
                "controlled_clean": c.get("controlled_clean", {}), "mtc_normal": c.get("mtc_normal", {})}
                for c in candidates if ":screen_layer.inner_height:" in ":" + c.get("atom_id", "").replace("app.web_data.", "") and c.get("polarity") == "NEGATIVE"]}


def _configs(candidate):
    value = candidate.get("triggered_config_ids", [])
    return set(value) if isinstance(value, (list, dict)) else set()


def explain_new_misses(rows, training_by_model, diagnostics=()):
    baseline = {(r["fold_id"], r["sample_id"]): r for r in rows if r["scheme"] == "BASELINE" and r["dataset"] == "controlled" and r.get("stage") == "attack"}
    buckets = defaultdict(list)
    for row in rows:
        if row["scheme"] != "BASELINE" and row["dataset"] == "controlled" and row.get("stage") == "attack":
            old = baseline.get((row["fold_id"], row["sample_id"]))
            if old and old["decision"] == "MANIPULATION_ALERT" and row["decision"] != "MANIPULATION_ALERT":
                buckets[(row["scheme"], row["fold_id"], row["model_id"], row["configuration_id"])].append((row, old))
    explanations = []
    for (scheme, fold, model, config), pairs in sorted(buckets.items()):
        candidates = training_by_model.get(model, {}).get("candidate_statistics", [])
        selected = {c["clause_id"] for c in candidates if c.get("selected")}
        old_rules = sorted({_clause_id(rule) for _, old in pairs for rule in old.get("rules", []) if rule.get("state") == "T"})
        old_candidates = [{"clause_id": c["clause_id"], "selected": c.get("selected"),
                           "admission_reasons": c.get("admission_reasons", []), "singleton_budget_reasons": c.get("singleton_budget_reasons", []),
                           "selection_reasons": c.get("selection_reasons", []), "controlled_clean": c.get("controlled_clean", {}),
                           "mtc_normal": c.get("mtc_normal", {})} for c in candidates if c["clause_id"] in old_rules]
        alternatives = [c for c in candidates if config in _configs(c)]
        locally_feasible = [c for c in alternatives if c.get("admitted") and not c.get("singleton_budget_reasons")]
        reasons = Counter(reason for c in alternatives for reason in (*c.get("admission_reasons", []), *c.get("singleton_budget_reasons", [])))
        classification = ("TRAIN_SUPPORTED_SINGLETON_CANDIDATES_EXIST_COMBINATION_NOT_ESTABLISHED" if locally_feasible else
                          "NO_SINGLETON_CANDIDATE_PASSES_SAVED_TRAIN_CHECKS_FOR_THIS_CONFIGURATION" if alternatives else
                          "NO_SAVED_TRAIN_TRIGGER_FOR_THIS_CONFIGURATION")
        by_clause = {c["clause_id"]: c for c in candidates}
        observed_alternatives = []
        for diagnostic in diagnostics:
            if (diagnostic.get("scheme"), diagnostic.get("fold_id"), diagnostic.get("configuration_id")) != (scheme, fold, config):
                continue
            if not diagnostic.get("heldout_attack_T", 0):
                continue
            candidate = by_clause.get(diagnostic["clause_id"], {})
            observed_alternatives.append({**diagnostic, "train_admitted": candidate.get("admitted"),
                "selected": candidate.get("selected"), "train_admission_reasons": candidate.get("admission_reasons", []),
                "train_singleton_budget_reasons": candidate.get("singleton_budget_reasons", []),
                "train_controlled_clean": candidate.get("controlled_clean", {}),
                "train_mtc_normal": candidate.get("mtc_normal", {}),
                "train_selected_reason": candidate.get("selection_reasons", [])})
        heldout_admissible = [c for c in observed_alternatives if c["train_admitted"] and not c["train_singleton_budget_reasons"]]
        explanations.append({"scheme": scheme, "fold_id": fold, "model_id": model, "configuration_id": config,
            "new_missed_sample_ids": [r["sample_id"] for r, _ in pairs], "new_decisions": dict(Counter(r["decision"] for r, _ in pairs)),
            "baseline_triggered_clauses": old_rules, "baseline_clauses_not_selected": [cid for cid in old_rules if cid not in selected],
            "baseline_clause_training_evidence": old_candidates, "train_trigger_candidate_n": len(alternatives),
            "train_singleton_admissible_candidate_ids": [c["clause_id"] for c in locally_feasible],
            "train_alternative_rejection_reasons": dict(reasons), "classification": classification,
            "train_trigger_candidate_evidence": [{"clause_id": c["clause_id"], "admitted": c.get("admitted"),
                "selected": c.get("selected"), "controlled_clean": c.get("controlled_clean", {}),
                "mtc_normal": c.get("mtc_normal", {}), "admission_reasons": c.get("admission_reasons", []),
                "singleton_budget_reasons": c.get("singleton_budget_reasons", [])} for c in alternatives],
            "heldout_triggering_candidates": observed_alternatives,
            "heldout_triggering_train_singleton_admissible_candidate_ids": [c["clause_id"] for c in heldout_admissible],
            "limitation": "训练配置触发和单条预算不是留出替代检出保证；未穷举所有集合，不能声称理论不可能。"})
    return explanations


def normal_alert_examples(rows):
    """Examples come only from saved main-subset predictions, never new reads."""
    examples = defaultdict(list)
    seen = defaultdict(set)
    for row in rows:
        if (row["scheme"] == "BASELINE" or row["dataset"] != "mtc"
                or row["subset"] not in ("discovery", "development", "reserved_validation")
                or row["decision"] != "MANIPULATION_ALERT" or not row.get("normal_basis", {}).get("supported")):
            continue
        for rule in row.get("rules", []):
            if rule.get("state") != "T":
                continue
            cid = _clause_id(rule)
            fields = rule.get("fields", [])
            key = (row["sample_id"], json.dumps(fields, sort_keys=True, ensure_ascii=False))
            if key in seen[cid] or len(examples[cid]) >= 3:
                continue
            seen[cid].add(key)
            examples[cid].append({"sample_id": row["sample_id"], "scheme": row["scheme"], "fold_id": row["fold_id"],
                "subset": row["subset"], "profile": row.get("profile", {}), "fields": fields,
                "source_refs": row.get("source_refs", {})})
    return dict(examples)


def _short_clause(clause):
    if isinstance(clause, str):
        cid = clause
    else:
        cid = clause.get("clause_id") or clause.get("id")
        if not cid and clause.get("literals"):
            cid = " & ".join(literal["atom_id"] + ":" + literal.get("polarity", "POSITIVE") for literal in clause["literals"])
        if not cid:
            return json.dumps(clause, ensure_ascii=False, sort_keys=True)
    if cid.startswith("CONTROL:") and ":LE:" in cid:
        field, threshold = cid.removeprefix("CONTROL:").split(":LE:")
        value, polarity = threshold.rsplit(":", 1)
        return field.rsplit(".", 1)[-1] + (" > " if polarity == "NEGATIVE" else " <= ") + value + "（" + cid + "）"
    names = {"RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1:POSITIVE": "WebGL1 查询等价性偏离",
             "RSR-WEBDRIVER-STATE-v1:POSITIVE": "webdriver 为 true",
             "RSR-LANG-FIRST-v1:POSITIVE": "语言首项关系偏离", "CAT:NW-006:POSITIVE": "UA/platform 关系偏离"}
    return names[cid] + "（" + cid + "）" if cid in names else cid


def render_report(summary, models, execution, settings):
    budget = settings.get("normal_budget", {})
    brief_execution = {key: value for key, value in execution.items() if key not in ("fits", "mtc_train_ids")}
    brief_execution["fit_status_counts"] = dict(Counter(fit.get("status", "UNKNOWN") for fit in execution.get("fits", [])))
    lines = ["# MTC 正常约束下的规则重新选择", "",
             "本轮已完成固定两方案、三个环境留一折的训练和评价。这是已有数据上的分组开发评估；历史 reserved_validation 名称不表示新的独立盲测。", "",
             "A 保留完整 50 项基础候选及原有数值展开；B 是历史 MTC 兼容候选模型，候选在 MTC 训练部分的 T/F 可评估比例和最终模型明确输出覆盖都要求至少 90%。两方案各折编码器只由本折受控训练记录生成，MTC 不生成阈值。", "",
             f'两个正常集合分别执行 floor(记录数 × 5%) 的 OR 集合报警预算，不能合并分母。每折受控正常 {budget.get("controlled_clean_per_fold", 168)} 条允许 {budget.get("controlled_allowed_alerts", 8)} 条、MTC discovery {len(settings.get("mtc_normal_train_ids", [])) if "mtc_normal_train_ids" in settings else 630} 条允许 {budget.get("mtc_allowed_alerts_if_all_supported", 31)} 条。5% 是固定开发操作点，不是部署标准，也不保证评价集达到它。容量上限 8 条、复杂度 16；每方案从新 GREEDY 开始再运行 R_KEEP。', "",
             f'保存预测包含 {summary["inventory"]["unique_controlled_records"]} 条不重复受控记录、{summary["inventory"]["unique_mtc_records"]} 条不重复 MTC 记录、{summary["inventory"]["mtc_model_os_combinations"]} 个 MTC 厂商／型号／系统组合。MTC 同一记录被三个模型计算，不增加独立样本量；下表逐模型列出。', "",
             "## 受控数据的相同成员对照", "",
             "三折留出受控记录互不重复，允许合并；未知、失败和空模型均在分母内。“全部记录不报警”以完整 378 条计算，包含漏检攻击，不能解释成正确正常数增加。", "",
             "| 方案 | 攻击检出 | 配对正常报警 | 明确输出覆盖 | 全部记录不报警 | U | FAILED | EMPTY_MODEL |",
             "|---|---|---|---|---:|---:|---:|---:|"]
    conclusions = []
    for scheme, item in summary["schemes"].items():
        if scheme == "BASELINE":
            continue
        totals = [tuple(sum(f["mtc"].get(subset, {}).get(field, 0) for subset in ("discovery", "development", "reserved_validation"))
                        for field in ("records", "alerts", "no_alert", "unknown", "failed", "empty_model")) for f in item["folds"].values()]
        if totals and len(set(totals)) == 1:
            n, alerts, no_alert, unknown, failed, empty = totals[0]
            main = f'三个模型各自在 {n} 条主代表中报警 {alerts}、明确不报警 {no_alert}、U {unknown}、失败 {failed}、空模型输出 {empty}'
        else:
            main = "三个模型的 MTC 结果分别见下表，不选择最好一折"
        conclusions.append(f'- **{SCHEME_NAMES.get(scheme, scheme)}**：受控攻击检出 {fraction(item["controlled_oof"]["attack"]["observed_alert_proportion"])}；{main}。')
    lines[4:4] = conclusions + [""]
    if summary.get("engineering_corrections"):
        correction = summary["engineering_corrections"]
        accounting = summary.get("fit_invocation_accounting", {})
        lines[4:4] = ["**工程修正披露：初次运行的评价结果已经打开，随后因旧观测适配错误按相同设置重跑。旧材料中的 -1 数值哨兵被误当作真实观测；修正针对输入解释，不改变候选定义、阈值生成、参数或模型选择方法。初次运行保留，不作为最终结果替换隐藏。**", "",
                       f'实际拟合：初始 {accounting.get("initial_fit_calls", 0)} 次 + 修正后 {accounting.get("final_fit_calls", 0)} 次 = 累计 {accounting.get("actual_fit_calls_total", 0)} 次；编码器累计 {accounting.get("actual_encoder_fit_calls_total", 0)} 次。首轮材料保留于 `{correction.get("initial_attempt", {}).get("archive", "未登记")}`。详见 ENGINEERING_CORRECTIONS.json；下表仅汇总修正后的正式运行，EXECUTION.json 的调用数只对应当前一次运行。', ""]
        if correction.get("saved_result_comparison_after_fix"):
            lines[8:8] = ["只读比对保留的首轮和修正后结果：适配修正改变候选可用状态，最终入选条件、同折编码器和全部 16272 条对齐预测的最终决策均未改变。", ""]
    if settings.get("out_of_scope_retained"):
        scope = settings["out_of_scope_retained"]
        lines[4:4] = [f'上一轮另列的 {scope.get("partial", 0)} 条整层缺失记录和 {scope.get("same_session_extra", 0)} 条同 session 额外观测本轮不新增训练或预测，去向仍见上一轮报告；本轮固定比较 891 主代表、137 配对重复及 654 App-only。', ""]
    for scheme, item in summary["schemes"].items():
        c = item["controlled_oof"]
        lines.append(f'| {SCHEME_NAMES.get(scheme, scheme)} | {fraction(c["attack"]["observed_alert_proportion"])} | {fraction(c["clean"]["observed_alert_proportion"])} | {fraction(c["all"]["defined_coverage"])} | {c["all"]["no_alert"]} | {c["all"]["unknown"]} | {c["all"]["failed"]} | {c["all"]["empty_model"]} |')
    lines += ["", "| 攻击配置 | " + " | ".join(SCHEME_NAMES.get(s, s) for s in summary["schemes"]) + " |",
              "|---|" + "---|" * len(summary["schemes"])]
    configs = sorted({k for item in summary["schemes"].values() for k in item["controlled_oof"]["configurations"]})
    for config in configs:
        lines.append("| " + config + " | " + " | ".join(fraction(item["controlled_oof"]["configurations"][config]["attack"]["observed_alert_proportion"]) for item in summary["schemes"].values()) + " |")
    lines += ["", "## MTC：逐模型、逐子集", "", "每格保留各自完整分母。报警为已经观察到的触发；U 不能算正常通过，EMPTY_MODEL 不能算可用检测器。正常采集依据沿用上一轮 DATA_NOTES.md 的任务和批次记录；无依据记录仅计算报警比例，不回写历史标签。", "",
              "| 方案 | 折 | 子集 | 预定/处理 | 报警 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 | 有正常依据的报警比例 |",
              "|---|---|---|---|---:|---:|---:|---:|---:|---|---|"]
    for scheme, item in summary["schemes"].items():
        for fold, f in item["folds"].items():
            for subset, s in f["mtc"].items():
                lines.append(f'| {scheme} | {fold[-2:]} | {SUBSET_NAMES.get(subset, subset)} | {s["planned_records"]}/{s["processed_records"]} | {s["alerts"]} | {s["no_alert"]} | {s["unknown"]} | {s["failed"]} | {s["empty_model"]} | {fraction(s["defined_coverage"])} | {fraction(s["normal_observed_alert_proportion"])} |')
    lines += ["", "与原模型的变化均用同一折、同一子集比较：", ""]
    for scheme, comparison in summary["comparisons"].items():
        for fold, subsets in comparison["mtc_by_fold"].items():
            main = [s for key, s in subsets.items() if key in ("discovery", "development", "reserved_validation")]
            lines.append(f'- {scheme} / {fold[-2:]}：主代表合计 {sum(s["denominator"] for s in main)} 条，报警变化 {sum(s["alert_change"] for s in main):+d}，明确不报警变化 {sum(s["no_alert_change"] for s in main):+d}，U 变化 {sum(s["unknown_change"] for s in main):+d}。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。')
    if any(s["unknown"] > s["no_alert"] for scheme, item in summary["schemes"].items() if scheme != "BASELINE" for f in item["folds"].values() for s in f["mtc"].values()):
        lines += ["", "至少一部分新模型的未知多于明确不报警：只能称观察到的报警减少，完整判断仍受限，不能直接宣称已成为低误报可用模型。"]
    if summary.get("normal_alert_examples"):
        lines += ["", "正常主代表仍触发的新模型条件及实际原值示例（从已保存逐条预测取值，型号只作说明）：", ""]
        for cid, examples in summary["normal_alert_examples"].items():
            for example in examples[:2]:
                profile = example["profile"]
                values = [{"field": f.get("field"), "value": f.get("value"), "status": f.get("source_status")} for f in example["fields"]]
                lines.append(f'- `{cid}`：`{example["sample_id"]}`，{profile.get("manufacturer", "UNKNOWN")} / {profile.get("model", "UNKNOWN")} / Android {profile.get("android_release", "UNKNOWN")}，{example["subset"]}；原值 `{json.dumps(values, ensure_ascii=False)}`。')
    lines += ["", "## 选中了什么，淘汰依据是什么", "",
              "候选统计只使用各折受控训练数据和 MTC discovery；攻击支持、配置覆盖、轨迹从不包含 MTC。完整逐候选统计、集合分数和操作轨迹保存在各 trial/training.json。以下新模型均为 R_KEEP 最终结果。", ""]
    for scheme, comparison in summary["comparisons"].items():
        changes = comparison["selected_rule_changes"]
        groups = defaultdict(list)
        for fold, change in changes.items():
            groups[json.dumps(change, sort_keys=True)].append(fold[-2:])
        for change_json, folds in groups.items():
            change = json.loads(change_json)
            lines += [f'- {scheme} / 折 {",".join(folds)}：移除 `{"; ".join(change["removed"]) or "无"}`；新增 `{"; ".join(change["added"]) or "无"}`。']
    if any(model.get("scheme") != "BASELINE" and model.get("stage") == "RETENTION" and model.get("status") != "FITTED" for model in models):
        lines += ["", "存在最终 EMPTY_MODEL 或 FAILED：此折没有交付可用的已拟合模型；保持原固定设置，不临时放宽约束。具体状态如下。"]
    lines += ["", "| 方案/折 | 状态 / 规则数 | 最终条件（数值为极性后的实际报警方向） |", "|---|---|---|"]
    for model in models:
        if model.get("stage") not in ("RETENTION", "R_KEEP"):
            continue
        overview = summary.get("candidate_training", {}).get(model["model_id"], {})
        selected = model.get("selected_clauses", overview.get("selected_clauses", []))
        names = [_short_clause(clause).split("（", 1)[0] for clause in selected]
        lines.append(f'| {model["scheme"]}/{model["fold_id"][-2:]} | {model.get("status", "UNKNOWN")} / {model.get("rule_count", len(selected))} | {"；".join(names) or "无规则，不算正常通过"} |')
    lines += ["", "各模型完整身份见 models.json。训练逐候选情况：", "", "| 方案/折 | 展开 literal | 准入 | 完全无法在 MTC 训练上检验的入选条件 |", "|---|---:|---:|---|"]
    for model in models:
        overview = summary.get("candidate_training", {}).get(model["model_id"])
        if not overview:
            continue
        unverified = "、".join(_short_clause(cid).split("（", 1)[0] for cid in overview["selected_mtc_unverified"])
        lines.append(f'| {model["scheme"]}/{model["fold_id"][-2:]} | {overview["expanded_literals"]} | {overview["admitted"]} | {unverified or "无"} |')
    lines += ["", "准入不等于能进入 OR 集合，仍须通过两类正常集合预算；准入/预算拒绝原因完整保存在训练统计。A 的 WebGL1 和 webdriver 全 U，0 次观察触发不能解释为误报率 0。"]
    height_examples = []
    for model in models:
        if model.get("scheme") != "A" or model.get("stage") != "RETENTION":
            continue
        overview = summary.get("candidate_training", {}).get(model["model_id"], {})
        current = overview.get("display_height_candidates", [])
        kept = [c for c in current if c["selected"]]
        for c in kept or current:
            mtc = c["mtc_normal"]
            height_examples.append(f'折 {model["fold_id"][-2:]} 的 `{_short_clause(c["clause_id"]).split("（", 1)[0]}`：MTC 训练正常触发 {mtc.get("T", 0)}/{mtc.get("expected", 0)}，{"入选" if c["selected"] else "未入选"}')
    if height_examples:
        lines += ["", "显示替代条件的差异来自各折受控训练生成的阈值：" + "；".join(height_examples) + "。前两折保留了显示干预的 6/9 检出；第三折损失 3/9。它是有训练支持的替代信号，但仍会把正常显示尺寸差异当成报警；37 条已经高于 MTC 允许的 31 条，不能为保留检出而放宽预算。"]
    lines += ["", "## 新漏检与替代条件", "",
              "下面先用留出实际结果定位新漏检，再用已保存训练候选统计解释。单条在训练中可行不代表可与其他规则组成可行 OR 模型，也不保证留出集检出；启发式未找到组合不等于理论不可能。"]
    if not summary.get("new_misses"):
        lines += ["", "没有发现相对原模型新增的受控攻击漏检。"]
    grouped_misses = defaultdict(list)
    for miss in summary.get("new_misses", []):
        grouped_misses[miss["configuration_id"]].append(miss)
    lines += ["", "重复原因按配置合并说明；每折完整候选计数和证据仍保存在 summary.json："] if grouped_misses else []
    for config, misses in sorted(grouped_misses.items()):
        loss_by_scheme = defaultdict(set)
        for miss in misses:
            loss_by_scheme[miss["scheme"]].update(miss["new_missed_sample_ids"])
        losses = "、".join(f"{scheme} 漏检 {len(ids)} 条" for scheme, ids in sorted(loss_by_scheme.items()))
        lines += ["", f"- **{config}**：{losses}。"]
        actual = [c for miss in misses for c in miss.get("heldout_triggering_candidates", [])]
        admissible = sorted({c for miss in misses for c in miss["heldout_triggering_train_singleton_admissible_candidate_ids"]})
        if admissible:
            lines += ["", "  训练后只读诊断发现，留出攻击仍有通过训练准入和单条预算的候选触发：" + "; ".join(admissible) + "。当前搜索没有找到保留它们的最终可行组合；不能写成理论无解。"]
        elif actual:
            reasons = sorted({reason for c in actual for reason in (*c["train_admission_reasons"], *c["train_singleton_budget_reasons"])})
            lines += ["", "  在出现该类新漏检的折／方案中，逐项诊断发现能触发留出攻击的候选均未通过其训练准入或单条正常预算；原因包括 `" + "; ".join(reasons) + "`。结论限于本轮生成的候选及固定设置，不代表不存在新表达或其他算法的改进空间。"]
        else:
            lines += ["", "  保存诊断没有建立可用的替代触发；训练支持不能直接当作留出检出保证。"]
        old_evidence = {}
        for miss in misses:
            for candidate in miss["baseline_clause_training_evidence"]:
                clean, mtc = candidate["controlled_clean"], candidate["mtc_normal"]
                key = (candidate["clause_id"], clean.get("T", 0), mtc.get("T", 0), tuple(candidate["selection_reasons"]))
                old_evidence[key] = candidate
        for candidate in old_evidence.values():
            clean, mtc = candidate["controlled_clean"], candidate["mtc_normal"]
            unknown_note = f'；MTC {mtc.get("U", 0)}/{mtc.get("expected", 0)} 为 U' if mtc.get("U") else ""
            lines += ["", f'  原条件 `{_short_clause(candidate["clause_id"])}`：受控训练正常触发 {clean.get("T", 0)}/{clean.get("expected", 0)}，MTC 训练触发 {mtc.get("T", 0)}/{mtc.get("expected", 0)}{unknown_note}；未入选原因 `{"; ".join(candidate["selection_reasons"])}`。']
        alternatives = {c["clause_id"]: c for miss in misses for c in miss["train_trigger_candidate_evidence"]
                        if c["admitted"] and c["singleton_budget_reasons"] and c["clause_id"] not in {e[0] for e in old_evidence}}
        nearest = sorted(alternatives.values(), key=lambda c: (c["controlled_clean"].get("T", 0), c["mtc_normal"].get("T", 0), c["clause_id"]))
        for candidate in nearest[:1]:
            clean, mtc = candidate["controlled_clean"], candidate["mtc_normal"]
            lines += ["", f'  例如候选 `{_short_clause(candidate["clause_id"])}` 也有训练配置触发，但受控正常 {clean.get("T", 0)}/{clean.get("expected", 0)}、MTC 正常 {mtc.get("T", 0)}/{mtc.get("expected", 0)} 已超出至少一个独立预算。']
    if summary.get("overlap_examples"):
        lines += ["", "实际数值重叠例子（训练后只读核对，不影响模型）：", ""]
        shown = set()
        for example in summary["overlap_examples"]:
            key = (example.get("field"), example.get("value"), example.get("normal_sample_id"))
            if key in shown:
                continue
            shown.add(key)
            profile = example.get("normal_profile", {})
            lines.append(f'- `{example.get("field")}` 在正常 {profile.get("manufacturer")} / {profile.get("model")} / Android {profile.get("android_release")} 和攻击 `{example.get("configuration_id")}` 中同为 `{example.get("value")}`。正常 ID `{example.get("normal_sample_id")}`，攻击 ID `{example.get("attack_sample_id")}`。')
        lines += ["", "完整引用见 OVERLAP_EXAMPLES.json。相同暴露值不表示物理硬件相等，但说明该绝对数值本身无法区分这些正常与干预记录。"]
    lines += ["", "## 旧观测限制和下一步", "",
              "旧 MTC 没有 WebGL1 数字／数字字符串查询原始观测，webdriver false 投影不能恢复属性存在与读取状态；这些条件保留 U。旧 deviceMemory / hardwareConcurrency 默认 0 按哨兵处理，不能当作真实零值。来源、标签、型号、任务 ID 和历史 split 只作关联，不进入预测。", "",
              "训练正常反例若让原高内存／高 DPR 条件超出独立预算，说明单一绝对阈值把合法设备范围和攻击值混在一起；本轮由同一通用预算机制淘汰，不手工封禁字段名。替代条件是否有支持、是否可观测和是否超出预算分别保存在候选统计与 new_misses 中。", "",
              "最优先的具体修正方向是显示规则：核对正常高 viewport 设备与 screen-metrics 干预的同次字段关系，避免把 inner_height 的绝对高度继续当作通用攻击证据。本轮的 height 替代规则仍在命中正常显示差异，不能因为其报警数低于 5% 就赋予攻击语义。随后再针对 resource-pair 缺少可行替代的问题检查资源关系候选；不能把 Web 内存和 Native 物理内存强设为相等。", "",
              "对于 A 仍依赖的未知条件，最小补采是同次 App 主 frame 的 WebGL1 原始查询和 webdriver 属性存在／读取状态／类型；补采用于验证正常侧表现，不能通过填 F 修饰当前结果。本轮没有新增候选关系或启动采集；额外拟合仅为已披露的工程适配修复。", "",
              "## 运行记录和复现", "",
              f'执行摘要：`{json.dumps(brief_execution, ensure_ascii=False, sort_keys=True)}`。逐次拟合记录与完整训练成员见 EXECUTION.json。', "",
              "```bash", "# 仅从本轮保存的预测、训练统计和清单重建报告；不加载原数据，不训练、不预测", "python3 deliverables/mtc_constrained_reselection_v1/summarize.py --output-dir deliverables/mtc_constrained_reselection_v1", "```", "",
              "`predictions.jsonl.gz` 无损压缩保存逐条结果及规则证据（汇总也兼容未压缩 .jsonl）；`models.json` 保存模型身份与路径；`summary.json` 保存完整逐配置、逐模型、逐规则和简洁系统分组统计及新漏检解释。SETTINGS.json 固定方案，EXECUTION.json 记录实际拟合次数和工程修正。原模型、历史数据和旧结果未作为汇总写入目标。"]
    validation = summary.get("validation", {})
    if validation:
        lines += ["", f'测试：{validation.get("tests_passed", 0)} 项通过、{validation.get("tests_failed", 0)} 项失败。只读复核 {validation.get("final_saved_models_verified", 0)} 个阶段模型、{validation.get("shared_controlled_only_fold_encoders_verified", 0)} 个同折共享编码器、{validation.get("saved_prediction_OR_states_verified", 0)} 条保存预测 OR 状态、{validation.get("discovery_prediction_training_consistency_rows", 0)} 条 discovery 预测/训练状态一致；复核新增拟合 {validation.get("verification_fit_calls", 0)} 次、新增预测 {validation.get("verification_predict_calls", 0)} 次。完整命令和结果见 VALIDATION.json。']
    return "\n".join(lines) + "\n"


def _json(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def _training_path(directory, value):
    path = Path(value)
    if path.is_absolute():
        return path
    # Registry entries may be experiment-relative or repository-relative.
    relative = directory / path
    return relative if relative.exists() else HERE.parents[1] / path


def summarize(directory=HERE):
    directory = Path(directory)
    compressed = directory / "predictions.jsonl.gz"
    path = compressed if compressed.exists() else directory / "predictions.jsonl"
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    settings = _json(directory / "SETTINGS.json", {})
    validate_saved_members(rows, settings)
    summary = summarize_rows(rows)
    registry = _json(directory / "models.json", {"models": []})
    models = registry.get("models", []) if isinstance(registry, dict) else registry
    training_by_model = {}
    for model in models:
        if model.get("scheme") == "BASELINE" or model.get("stage") not in ("RETENTION", "R_KEEP"):
            continue
        path = model.get("training_path")
        if path:
            training_by_model[model["model_id"]] = json.loads(_training_path(directory, path).read_text())
    summary["candidate_training"] = {model: candidate_overview(training) for model, training in training_by_model.items()}
    diagnostic_path = directory / "EVAL_CANDIDATE_DIAGNOSTICS.jsonl"
    diagnostics = [json.loads(line) for line in diagnostic_path.read_text().splitlines() if line.strip()] if diagnostic_path.exists() else []
    summary["new_misses"] = explain_new_misses(rows, training_by_model, diagnostics)
    summary["normal_alert_examples"] = normal_alert_examples(rows)
    summary["overlap_examples"] = _json(directory / "OVERLAP_EXAMPLES.json", {}).get("examples", [])
    summary["engineering_corrections"] = _json(directory / "ENGINEERING_CORRECTIONS.json", {})
    summary["validation"] = _json(directory / "VALIDATION.json", {})
    execution = _json(directory / "EXECUTION.json", {})
    initial = summary["engineering_corrections"].get("initial_attempt", {})
    summary["fit_invocation_accounting"] = {"initial_fit_calls": initial.get("fit_calls", 0),
        "final_fit_calls": execution.get("actual_fit_calls", 0),
        "actual_fit_calls_total": initial.get("fit_calls", 0) + execution.get("actual_fit_calls", 0),
        "actual_encoder_fit_calls_total": initial.get("encoder_fit_calls", 0) + execution.get("encoder_fit_calls", 0)}
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (directory / "REPORT.md").write_text(render_report(summary, models, execution, settings))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    summary = summarize(args.output_dir)
    print(json.dumps({"schemes": list(summary["schemes"]), "inventory": summary["inventory"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
