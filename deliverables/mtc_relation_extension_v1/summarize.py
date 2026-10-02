#!/usr/bin/env python3
"""Summarize saved B/B_REL artifacts only: no data adapter, fit, or prediction."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.parent / "mtc_constrained_reselection_v1"
spec = importlib.util.spec_from_file_location("mtc_saved_summary_helpers", BASE / "summarize.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
SCHEMES = ("B", "B_REL")
SUBSETS = ("discovery", "development", "reserved_validation")
SUBSET_NAMES = {"discovery": "MTC discovery（训练）", "development": "MTC development（评价）",
                "reserved_validation": "MTC reserved_validation（评价）"}
ALERT = "MANIPULATION_ALERT"
count_rows = helpers.count_rows
fraction = helpers.fraction


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def resolve(directory, value):
    path = Path(value)
    if path.is_absolute():
        return path
    return directory / path if (directory / path).exists() else ROOT / path


def effective_settings(directory, settings):
    """Members remain exactly the previous fixed IDs, not rediscovered by score."""
    if "folds" in settings and "mtc_primary_ids" in settings:
        return settings
    ref = (settings.get("membership_and_baseline_settings") or settings.get("members_settings_ref")
           or settings.get("baseline_settings_ref"))
    members = read_json(resolve(directory, ref)) if ref else read_json(BASE / "SETTINGS.json")
    if not isinstance(members, dict):
        raise ValueError("SAVED_MEMBERS_SETTINGS_REQUIRED")
    return {**members, **settings}


def validate_saved_members(rows, settings):
    if not settings.get("folds") or not settings.get("mtc_primary_ids"):
        raise ValueError("PRESPECIFIED_FOLD_AND_MTC_MEMBERS_REQUIRED")
    expected = {}
    for scheme in SCHEMES:
        for fold in settings["folds"]:
            expected[(scheme, fold["fold_id"], "controlled", "heldout")] = set(fold["outer_test_ids"])
            for subset in SUBSETS:
                expected[(scheme, fold["fold_id"], "mtc", subset)] = set(settings["mtc_primary_ids"][subset])
    actual = defaultdict(set)
    seen = set()
    for row in rows:
        key = row["scheme"], row["fold_id"], row["dataset"], row["subset"]
        if (*key, row["sample_id"]) in seen:
            raise ValueError("DUPLICATE_PREDICTION")
        seen.add((*key, row["sample_id"]))
        actual[key].add(row["sample_id"])
    if any(expected.get(key, set()) != actual.get(key, set()) for key in set(expected) | set(actual)):
        raise ValueError("SAVED_SETTINGS_MEMBER_MISMATCH")


def row_key(row):
    return row["fold_id"], row["dataset"], row["subset"], row["sample_id"]


def saved_example(row, evidence):
    return {"sample_id": row["sample_id"], "fold_id": row["fold_id"], "subset": row["subset"],
            "profile": row.get("profile", {}), "decision": row["decision"],
            "normal_basis": row.get("normal_basis", {}), "source_refs": row.get("source_refs", {}),
            "source_ref": row.get("source_ref"), "configuration_id": row.get("configuration_id"),
            "stage": row.get("stage"), "evidence": evidence}


def summarize_rows(rows, settings=None):
    if settings is not None:
        validate_saved_members(rows, settings)
    if set(r["scheme"] for r in rows) != set(SCHEMES):
        raise ValueError("EXACT_B_AND_B_REL_SCHEMES_REQUIRED")
    summary = helpers.summarize_rows(rows)
    summary["schema_version"] = "mtc-relation-extension-summary-v1"
    summary["schemes"] = {scheme: summary["schemes"][scheme] for scheme in SCHEMES}
    old = {row_key(r): r for r in rows if r["scheme"] == "B"}
    changes = defaultdict(lambda: {"gained_attack_ids": [], "lost_attack_ids": [],
                                  "new_normal_alert_ids": [], "removed_normal_alert_ids": [],
                                  "decision_transitions": Counter()})
    for row in rows:
        if row["scheme"] != "B_REL":
            continue
        before = old[row_key(row)]
        partition = (row["fold_id"], row["dataset"], row["subset"])
        current = changes[partition]
        current["decision_transitions"][before["decision"] + " -> " + row["decision"]] += 1
        gained, lost = before["decision"] != ALERT and row["decision"] == ALERT, before["decision"] == ALERT and row["decision"] != ALERT
        if row["dataset"] == "controlled" and row.get("stage") == "attack":
            if gained:
                current["gained_attack_ids"].append(row["sample_id"])
            if lost:
                current["lost_attack_ids"].append(row["sample_id"])
        elif row.get("normal_basis", {}).get("supported") is True:
            if gained:
                current["new_normal_alert_ids"].append(row["sample_id"])
            if lost:
                current["removed_normal_alert_ids"].append(row["sample_id"])
    summary["comparisons"] = [{"fold_id": f, "dataset": d, "subset": s, **v}
                              for (f, d, s), v in sorted(changes.items())]
    summary["relation_analysis"] = relation_analysis(rows)
    summary["normal_counterexamples"] = normal_counterexamples(rows)
    return summary


def relation_analysis(rows):
    """Raw relation T is kept separate from selected-rule contribution."""
    old = {row_key(r): r for r in rows if r["scheme"] == "B"}
    result = {}
    for row in rows:
        if row["scheme"] != "B_REL":
            continue
        partition = "controlled_attack" if row["dataset"] == "controlled" and row.get("stage") == "attack" else (
            "controlled_clean" if row["dataset"] == "controlled" else row["subset"])
        selected = row.get("rules", [])
        triggered = [r for r in selected if r.get("state") == "T"]
        before = old[row_key(row)]
        for relation in row.get("relation_results", []):
            aid = relation["atom_id"]
            key = row["fold_id"] + "|" + partition + "|" + aid
            stat = result.setdefault(key, {"fold_id": row["fold_id"], "subset": partition, "atom_id": aid,
                "records": 0, "T": 0, "F": 0, "U": 0, "FAILED": 0, "selected_literal_T": 0,
                "unique_selected_rule_alerts": 0, "new_attack_detections_vs_B": 0,
                "new_normal_alerts_vs_B": 0, "raw_relation_T_already_alerted_by_B": 0,
                "unknown_reasons": Counter(), "normal_T_examples": [], "observed_normal_examples": []})
            stat["records"] += 1
            state = relation.get("state", "FAILED")
            stat[state if state in ("T", "F", "U") else "FAILED"] += 1
            if state not in ("T", "F"):
                stat["unknown_reasons"][relation.get("reason", "UNSPECIFIED")] += 1
            active = [r for r in triggered if r.get("atom_id") == aid]
            stat["selected_literal_T"] += bool(active)
            stat["unique_selected_rule_alerts"] += bool(active) and len(triggered) == 1 and row["decision"] == ALERT
            stat["raw_relation_T_already_alerted_by_B"] += state == "T" and before["decision"] == ALERT
            new_alert = bool(active) and row["decision"] == ALERT and before["decision"] != ALERT
            if partition == "controlled_attack":
                stat["new_attack_detections_vs_B"] += new_alert
                if new_alert and len(stat.setdefault("new_attack_examples", [])) < 3:
                    stat["new_attack_examples"].append(saved_example(row, relation))
            elif row.get("normal_basis", {}).get("supported") is True:
                stat["new_normal_alerts_vs_B"] += new_alert
                if state == "T" and len(stat["normal_T_examples"]) < 3:
                    stat["normal_T_examples"].append(saved_example(row, relation))
                if state in ("T", "F") and len(stat["observed_normal_examples"]) < 2:
                    stat["observed_normal_examples"].append(saved_example(row, relation))
    return list(result.values())


def normal_counterexamples(rows):
    result = []
    seen = set()
    per_clause = Counter()
    for row in rows:
        if row["dataset"] != "mtc" or row["decision"] != ALERT or row.get("normal_basis", {}).get("supported") is not True:
            continue
        for rule in row.get("rules", []):
            if rule.get("state") != "T":
                continue
            cid = helpers._clause_id(rule)
            key = row["sample_id"], cid
            if key in seen or per_clause[cid] >= 3:
                continue
            seen.add(key); per_clause[cid] += 1
            result.append({"scheme": row["scheme"], **saved_example(row, rule)})
    return result


def relation_training(training, relation_ids):
    rows = []
    for c in training.get("candidate_statistics", []):
        if c.get("atom_id") not in relation_ids:
            continue
        attack, clean, mtc = (c.get(k, {}) for k in ("controlled_attack", "controlled_clean", "mtc_normal"))
        flags = []
        if not attack.get("T", 0):
            flags.append("NO_TRAIN_ATTACK_TRIGGER")
        if mtc.get("defined", 0) < .9 * mtc.get("expected", 0):
            flags.append("MTC_EVALUABLE_COVERAGE_BELOW_90_PERCENT")
        if clean.get("T", 0) > int(.05 * clean.get("expected", 0)):
            flags.append("CONTROLLED_NORMAL_BUDGET_EXCEEDED")
        if mtc.get("T", 0) > int(.05 * mtc.get("expected", 0)):
            flags.append("MTC_NORMAL_BUDGET_EXCEEDED")
        if c.get("admitted") and not c.get("selected") and not c.get("singleton_budget_reasons"):
            flags.append("ADMITTED_BUT_NOT_SELECTED_BY_FIXED_SEARCH")
        rows.append({**c, "diagnostic_classification": flags})
    return rows


def model_evidence(directory, entries):
    result = []
    for entry in entries:
        if entry.get("stage") not in ("RETENTION", "R_KEEP"):
            continue
        path = resolve(directory, entry["path"])
        model = read_json(path)
        if not isinstance(model, dict) or model.get("model_id") != entry["model_id"]:
            raise ValueError("SAVED_MODEL_ID_MISMATCH")
        result.append({"scheme": entry["scheme"], "fold_id": entry["fold_id"], "model_id": entry["model_id"],
            "status": model["status"], "clauses": model.get("clauses", []), "atoms": model.get("atoms", []),
            "complexity": model.get("complexity", {}), "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)})
    return result


def metrics_cells(stats):
    return (f'{stats["alerts"]}/{stats["records"]} | {stats["no_alert"]} | {stats["unknown"]} | '
            f'{stats["failed"]} | {stats["empty_model"]} | {fraction(stats["defined_coverage"])}')


def brief_fields(fields):
    return json.dumps({f["field"].rsplit(".", 1)[-1]: f.get("value") for f in fields},
                      ensure_ascii=False, sort_keys=True)


def render_report(summary, execution, settings):
    old, new = (summary["schemes"][s]["controlled_oof"] for s in SCHEMES)
    gained = sum(len(c["gained_attack_ids"]) for c in summary["comparisons"])
    lost = sum(len(c["lost_attack_ids"]) for c in summary["comparisons"])
    selected_relations = sorted({a["atom_id"] for m in summary.get("models", []) if m["scheme"] == "B_REL"
                                 for a in m["atoms"] if a["atom_id"] in summary.get("relation_ids", [])})
    lines = ["# 屏幕／资源关系扩展：已有 MTC 正常约束下的选择与评价", "",
        f'B_REL 攻击检出 **{new["attack"]["alerts"]}/{new["attack"]["records"]}**；保存 B 基线为 **{old["attack"]["alerts"]}/{old["attack"]["records"]}**。相同成员新增检出 {gained} 条、损失检出 {lost} 条。配对正常报警 B 为 {old["clean"]["alerts"]}/{old["clean"]["records"]}，B_REL 为 {new["clean"]["alerts"]}/{new["clean"]["records"]}。', "",
        "本轮是已经使用材料上的分组开发评估，不是新独立盲测。仅扩展候选表示，保存 B 模型与预测直接复用；A 不重跑。两组正常数据各自执行 5% OR 集合报警预算，候选 MTC T/F 覆盖和最终训练明确输出覆盖均至少 90%；容量 8 条、复杂度 16、受控训练分位数编码器及选择目标保持原设置。", "",
        f'实际涉及 {summary["inventory"]["unique_mtc_records"]} 条不重复 MTC 记录、{summary["inventory"]["mtc_model_os_combinations"]} 个厂商／型号／系统组合，以及 {summary["inventory"]["unique_controlled_records"]} 条受控记录。MTC 的三次模型评估不是三批独立样本，以下逐折列出。', "",
        "## 同成员总体与逐配置比较", "",
        "| 方案与集合 | 报警/分母 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 |",
        "|---|---:|---:|---:|---:|---:|---|"]
    coverage_changes = []
    for fold, data in summary["schemes"]["B_REL"]["folds"].items():
        previous = summary["schemes"]["B"]["folds"][fold]
        before_u = sum(previous["mtc"][s]["unknown"] for s in ("development", "reserved_validation"))
        after_u = sum(data["mtc"][s]["unknown"] for s in ("development", "reserved_validation"))
        normal_added = sum(len(c["new_normal_alert_ids"]) for c in summary["comparisons"]
                           if c["fold_id"] == fold and c["dataset"] == "mtc" and c["subset"] != "discovery")
        coverage_changes.append((before_u, after_u, normal_added))
    if coverage_changes and len(set(coverage_changes)) == 1:
        before_u, after_u, normal_added = coverage_changes[0]
        any_fold = next(iter(summary["schemes"]["B_REL"]["folds"].values()))
        evaluation_n = sum(any_fold["mtc"][s]["records"] for s in ("development", "reserved_validation"))
        cost = (f'**代价：每个模型在两部分 MTC 评价记录上，U 从 {before_u} 条变为 {after_u} 条；'
                f'新增正常报警 {normal_added} 条。** 未知增加意味着能明确判为不报警的正常记录减少，'
                f'不能只用报警数不增加宣称无代价改善。各模型仍评价同一批 {evaluation_n} 条记录。')
        lines[4:4] = [cost, ""]
    for scheme in SCHEMES:
        for key, name in (("attack", "受控攻击"), ("clean", "配对正常"), ("all", "受控全部")):
            lines.append(f'| {scheme} {name} | {metrics_cells(summary["schemes"][scheme]["controlled_oof"][key])} |')
    lines += ["", "| 攻击配置 | B 检出 | B_REL 检出 | 变化 |", "|---|---:|---:|---:|"]
    for config, before in old["configurations"].items():
        after = new["configurations"][config]
        lines.append(f'| `{config}` | {before["attack"]["alerts"]}/{before["attack"]["records"]} | {after["attack"]["alerts"]}/{after["attack"]["records"]} | {after["attack"]["alerts"]-before["attack"]["alerts"]:+d} |')
    focus = []
    for pattern, label in (("screen-metrics", "屏幕单项"), ("resource-pair", "资源单项")):
        matching = [c for c in old["configurations"] if pattern in c]
        if len(matching) == 1:
            c = matching[0]
            a, b = old["configurations"][c]["attack"], new["configurations"][c]["attack"]
            focus.append(f'{label}从 {a["alerts"]}/{a["records"]} 变为 {b["alerts"]}/{b["records"]}')
    if focus:
        lines += ["", "；".join(focus) + "。"]
    mtc_changes = [c for c in summary["comparisons"] if c["dataset"] == "mtc" and c["subset"] != "discovery"]
    if mtc_changes and all(not c["new_normal_alert_ids"] and not c["removed_normal_alert_ids"]
                           and all(k.split(" -> ")[0] == k.split(" -> ")[1] for k in c["decision_transitions"])
                           for c in mtc_changes):
        lines += ["", "两部分 MTC 评价的每条最终输出均与保存 B 相同：没有减少既有正常报警，也没有借增加 U 换取报警下降。"]
    lines += ["", "## MTC：训练与两部分评价分开", "",
        "每格分母包含 U、FAILED 和 EMPTY_MODEL。明确不报警只是本模型的输出，不是未知或失败的替代标签；正常依据沿用常规采集说明。", "",
        "| 方案／折／集合 | 报警/分母 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 |",
        "|---|---:|---:|---:|---:|---:|---|"]
    for scheme in SCHEMES:
        for fold, data in summary["schemes"][scheme]["folds"].items():
            for subset in SUBSETS:
                lines.append(f'| {scheme} / {fold.rsplit("-",1)[-1]} / {SUBSET_NAMES[subset]} | {metrics_cells(data["mtc"][subset])} |')
    lines += ["", "正常依据分母和未知依据数量、按系统/采集版本分组、逐条转换及三模型一致性均在 summary.json 中保存。任何 U 增加均保留为覆盖损失，不当作降低误报。", "",
        "## 新关系多提供了什么", "",
        "新增两个固定关系模板：同一次 Web 探针的 visual/layout 视口边界，以及同一次 App Native 内核可见内存总量参照下的 Web 二次幂上包络。单位、适用域、历史实现差异和拒绝的等式见 SCREEN_REVIEW.md、RESOURCE_REVIEW.md。所有关系参数固定，无额外参数拟合。", "",
        ("最终模型实际选入：" + "、".join(f'`{a}`' for a in selected_relations) + "。") if selected_relations else "本轮最终模型没有选入新增关系。关系通过输入检查不等于拥有攻击区分信息，也不强制进入模型。", "",
        "| 折／关系字面量 | 攻击训练 T/分母 | 受控正常 T/分母 | MTC 正常 T/分母 | MTC T/F覆盖 | 入选 | 训练侧原因 |",
        "|---|---:|---:|---:|---:|---|---|"]
    for model in summary.get("candidate_training", []):
        for c in model["relations"]:
            a, n, m = (c.get(k, {}) for k in ("controlled_attack", "controlled_clean", "mtc_normal"))
            reasons = list(dict.fromkeys(c.get("diagnostic_classification", []) + c.get("admission_reasons", []) + c.get("singleton_budget_reasons", []) + c.get("selection_reasons", [])))
            lines.append(f'| {model["fold_id"].rsplit("-",1)[-1]} / `{c["clause_id"]}` | {a.get("T",0)}/{a.get("expected",0)} | {n.get("T",0)}/{n.get("expected",0)} | {m.get("T",0)}/{m.get("expected",0)} | {m.get("defined",0)}/{m.get("expected",0)} | {"是" if c.get("selected") else "否"} | {"; ".join(reasons)} |')
    contributions = [r for r in summary["relation_analysis"] if r["selected_literal_T"] or r["new_attack_detections_vs_B"] or r["new_normal_alerts_vs_B"]]
    lines += ["", "逐规则贡献只解释已保存模型，不手工删规则生成另一个成绩。一个记录可能被多条关系触发，关系贡献数不能相加为样本数。"]
    if contributions:
        lines += ["", "| 折／关系／集合 | 入选字面量触发 | 独有报警 | 比B新增攻击检出 | 比B新增正常报警 |", "|---|---:|---:|---:|---:|"]
        for r in contributions:
            lines.append(f'| {r["fold_id"].rsplit("-",1)[-1]} / `{r["atom_id"]}` / {r["subset"]} | {r["selected_literal_T"]}/{r["records"]} | {r["unique_selected_rule_alerts"]} | {r["new_attack_detections_vs_B"]} | {r["new_normal_alerts_vs_B"]} |')
    else:
        lines += ["", "新增关系对最终模型的独有攻击检出和新增正常报警均为 0；完整原始关系 T/F/U/FAILED 和不可用原因仍已保存，不能将未入选解释成普遍无用或理论不可解。"]
    first_fold = next(iter(summary["schemes"]["B_REL"]["folds"]))
    memory_unknown = [r for r in summary["relation_analysis"] if r["fold_id"] == first_fold
                      and "MEMORY" in r["atom_id"] and r["subset"] in SUBSETS]
    if memory_unknown:
        lines += ["", "内存关系增加了一个必须观测到的依赖，因此原来没有其他触发的记录会从 F 变为 U。其未知数量依次为 " +
                  "、".join(f'{r["subset"]} {r["U"]}/{r["records"]}' for r in memory_unknown) +
                  "；原因计数见 summary.json。旧 deviceMemory 的 0 是含糊默认值，不能自动认作真实 0 或补为满足关系的 F。"]
    novel_examples = [e for r in summary["relation_analysis"] for e in r.get("new_attack_examples", [])]
    if novel_examples:
        e = novel_examples[0]
        lines += ["", f'新增检出例：`{e["sample_id"]}`（`{e["configuration_id"]}`），当前会话原始资源字段 `{brief_fields(e["evidence"].get("fields", []))}`；上包络 `{e["evidence"].get("diagnostics", {}).get("upper_envelope_gib")}` GiB。此说明只用当前采集，未借用 clean_pre/clean_post 做预测。']
    training_diagnostics = summary.get("relation_training_diagnostics", {}).get("mtc_discovery", {})
    for aid, diagnostic in training_diagnostics.items():
        if "MEMORY" not in aid:
            continue
        for state, label in (("F", "正常资源差异被保留为可评价满足"), ("U", "正常缺失例仍为未知")):
            examples = diagnostic.get("examples", {}).get(state, [])
            if examples:
                e = examples[0]
                lines += ["", f'{label}：`{e["sample_id"]}`，`{brief_fields(e.get("fields", []))}`；原因 `{e.get("reason")}`。']
    lines += ["", "## 最终条件与实际正常反例", ""]
    for model in summary.get("models", []):
        clauses = [helpers._short_clause(c) for c in model["clauses"]]
        complexity = model.get("complexity", {})
        lines.append(f'- {model["scheme"]} / {model["fold_id"]}：{len(clauses)} 条，目标复杂度 {complexity.get("objective_complexity", "未提供")}，状态 {model["status"]}；`{model["model_id"]}`。条件：' + "; ".join(clauses) + "。")
    new_models = [m for m in summary.get("models", []) if m["scheme"] == "B_REL"]
    height_models = sum(any("screen_layer.inner_height" in a["atom_id"] for a in m["atoms"]) for m in new_models)
    timezone_models = sum(any("execution_layer.timezone_offset" in a["atom_id"] for a in m["atoms"]) for m in new_models)
    if new_models:
        lines += ["", f'绝对值条件仍保留：inner_height 在 {height_models}/{len(new_models)} 个新模型中，时区偏移在 {timezone_models}/{len(new_models)} 个新模型中。本轮新增关系没有自动替换掉这些条件；实际正常显示/时区反例继续按原始输出保留。']
    if summary["normal_counterexamples"]:
        lines += ["", "下面保留已经触发模型的常规采集记录；报警不改变历史正常依据或 unlabeled 标签：", ""]
        for example in summary["normal_counterexamples"]:
            p = example["profile"]
            evidence = example["evidence"]
            values = evidence.get("fields", [])
            lines.append(f'- {p.get("manufacturer")} / {p.get("model")} / Android {p.get("android_release")}，`{example["sample_id"]}`，{example["scheme"]}/{example["subset"]}：`{helpers._short_clause(evidence)}`；实际字段 `{brief_fields(values)}`。')
    relation_normal = [e for r in summary["relation_analysis"] for e in r["normal_T_examples"]]
    unique_normal = {}
    for e in relation_normal:
        unique_normal.setdefault((e["sample_id"], e["evidence"]["atom_id"]), e)
    if unique_normal:
        lines += ["", "新关系自身也观察到正常偏离（即使未入选，也保留 T）：", ""]
        for e in list(unique_normal.values())[:4]:
            lines.append(f'- `{e["sample_id"]}` / `{e["evidence"]["atom_id"]}`：`{json.dumps(e["evidence"].get("fields", []), ensure_ascii=False, sort_keys=True)}`。')
    lines += ["", "## 仍不能解决的问题与下一步", "",
        "视口关系检查的是同 Web 观测的一致性；协调修改 inner 与 visual 的干预可保持这一关系，不能据此补造 Native 等式。旧 Native displayMetrics 不是 WebView 的内容矩形，缺少同步窗口/insets/page zoom 参照，现有材料不能可靠检验完整跨层屏幕映射。屏幕/资源规则是否提升检出以以上保存结果为准，不因为低于 5% 就称它们为官方不变量。", "",
        "Web 内存是粗粒度暴露值，Native totalMem 是内核可见内存总量，不是当前剩余可用内存，也不等于完整物理 RAM；两者不要求相等。CPU 参照字段不足时不发明核数。旧 MTC 的 WebGL1 和 webdriver 原始观测缺失保持不变；本轮不靠此类规则恢复检出，也不填 F。", "",
        "最小补采仅作为后续建议：同次稳定布局时刻采 WebView 内容矩形、窗口 insets、方向、page zoom/visual scale和时间；如继续检查 CPU，采明确口径的当前进程可用处理器数并保留浏览器限制说明。已有关系的正常反例应先解释其采集口径与浏览器实现，不能改标攻击或转 U。本轮没有启动任何新采集。", "",
        "## 运行与复现", "",
        f'实际拟合记录：`{json.dumps({k:v for k,v in execution.items() if k in ("actual_fit_calls", "real_fit_calls", "planned_fit_calls", "encoder_fit_calls", "relation_parameter_fit_calls", "engineering_reruns", "engineering_corrections", "completed_at", "status")}, ensure_ascii=False, sort_keys=True)}`。具体逐次调用见 FIT_CALLS.jsonl/EXECUTION.json；报告汇总不调用拟合或预测。', "",
        "```bash", "# 从保存结果重新汇总", "python3 deliverables/mtc_relation_extension_v1/summarize.py --output-dir deliverables/mtc_relation_extension_v1",
        "# 在新的输出目录复现有限实验", "python3 deliverables/mtc_relation_extension_v1/run_experiment.py run --output-dir /tmp/mtc_relation_reproduce", "```", "",
        "逐条预测保存在 predictions.jsonl.gz；原始引用、模型身份、规则和新增关系的字段值/不可用原因可逐条追查。summary.json 保存总体、逐配置、逐折子集、逐规则贡献和简洁分组统计；models.json 和 trials 保存模型及训练轨迹。所有旧模型、数据和报告保持原样。"]
    if summary.get("validation"):
        validation = summary["validation"]
        lines += ["", f'针对性测试 {validation.get("tests_passed", 0)} 项通过、{validation.get("tests_failed", 0)} 项失败（新增 {validation.get("new_tests", 0)}、既有回归 {validation.get("prior_regression_tests", 0)}）。'
                  f'预定与实际成员逐 ID 匹配：保存 {summary["inventory"]["model_evaluations"]} 条模型输出，受控每方案 {summary["inventory"]["unique_controlled_records"]} 条、MTC 每模型 {summary["inventory"]["unique_mtc_records"]} 条。'
                  f'核验 {validation.get("saved_prediction_polarity_OR_and_decision_checks", 0)} 条保存输出的极性/OR，{validation.get("saved_B_rows_reused_identically", 0)} 条 B 预测原样复用。汇总与复核没有新增拟合或预测；完整命令与检查见 VALIDATION.json。']
    return "\n".join(lines) + "\n"


def summarize(directory=HERE):
    directory = Path(directory)
    path = directory / "predictions.jsonl.gz"
    if not path.exists():
        path = directory / "predictions.jsonl"
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    settings = effective_settings(directory, read_json(directory / "SETTINGS.json", {}))
    summary = summarize_rows(rows, settings)
    registry = read_json(directory / "models.json", {"models": []})
    entries = registry.get("models", []) if isinstance(registry, dict) else registry
    summary["models"] = model_evidence(directory, entries)
    if not any(m["scheme"] == "B" for m in summary["models"]):
        base_registry = read_json(BASE / "models.json")["models"]
        summary["models"] = model_evidence(BASE, [m for m in base_registry if m["scheme"] == "B"]) + summary["models"]
    relation_ids = sorted({r["atom_id"] for row in rows for r in row.get("relation_results", [])})
    summary["relation_ids"] = relation_ids
    summary["candidate_training"] = []
    for entry in entries:
        if entry.get("scheme") != "B_REL" or entry.get("stage") not in ("RETENTION", "R_KEEP"):
            continue
        training = read_json(resolve(directory, entry["training_path"]))
        summary["candidate_training"].append({"model_id": entry["model_id"], "fold_id": entry["fold_id"],
            "overview": helpers.candidate_overview(training), "relations": relation_training(training, set(relation_ids))})
    summary["validation"] = read_json(directory / "VALIDATION.json", {})
    summary["relation_training_diagnostics"] = read_json(directory / "RELATION_TRAIN_DIAGNOSTICS.json", {})
    execution = read_json(directory / "EXECUTION.json", {})
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    (directory / "REPORT.md").write_text(render_report(summary, execution, settings))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    result = summarize(args.output_dir)
    print(json.dumps(result["inventory"], ensure_ascii=False))
