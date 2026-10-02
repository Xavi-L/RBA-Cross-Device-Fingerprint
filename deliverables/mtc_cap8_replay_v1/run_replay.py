#!/usr/bin/env python3
"""Read-only saved-model replay; summary subcommand reads saved outputs only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
SUBSETS = ("primary_representative", "paired_repeat_observation", "reserve_app_only_177",
           "reserve_partial", "reserve_repeated_observations")
LABELS = dict(zip(SUBSETS, ("主分析：型号／系统代表", "配对重复记录", "App-only", "整层缺失 partial", "同 session 额外观测")))
NAMES = {
    "RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1": "WebGL1 查询等价性",
    "RSR-WEBDRIVER-STATE-v1": "webdriver",
    "RSR-LANG-FIRST-v1": "语言首项关系",
    "CAT:NW-006": "UA/platform",
}


def short_rule(aid):
    if aid in NAMES:
        return NAMES[aid]
    field, threshold = aid.removeprefix("CONTROL:").rsplit(":LE:", 1)
    return field.rsplit(".", 1)[1] + " > " + threshold


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def ratio(num, den):
    return {"numerator": num, "denominator": den, "ratio": num / den if den else None}


def counts(rows):
    c = Counter(r["decision"] for r in rows)
    normal = [r for r in rows if r["normal_basis"].get("supported") is True]
    n = len(rows)
    alerts, no_alert = c["MANIPULATION_ALERT"], c["NO_ALERT"]
    return {"planned_records": n, "attempted_records": n,
            "processed_records": sum(r.get("prediction_attempted", r.get("load_error") is None) for r in rows),
            "alerts": alerts, "no_alert": no_alert, "unknown": c["INSUFFICIENT_EVIDENCE"],
            "failed": n - alerts - no_alert - c["INSUFFICIENT_EVIDENCE"],
            "defined_coverage": ratio(alerts + no_alert, n),
            "observed_alert_proportion": ratio(alerts, n),
            "normal_records": len(normal),
            "normal_observed_alert_proportion": ratio(sum(r["decision"] == "MANIPULATION_ALERT" for r in normal), len(normal)),
            "unsupported_normal_basis_records": n - len(normal)}


def _values(row):
    return {v["field"]: v.get("value") for rule in row["rules"] for v in rule.get("fields", [])}


def group_key(row, group):
    if group in ("manufacturer", "android_release"):
        return str(row["profile"].get(group, "UNKNOWN"))
    if group == "collector_version":
        return str(row.get("collector_version_code", "UNKNOWN"))
    if group == "webview_major":
        return str(row.get("webview_major", "UNKNOWN"))
    fields = {"device_memory": "app.web_data.navigator_layer.device_memory",
              "device_pixel_ratio": "app.web_data.screen_layer.device_pixel_ratio",
              "timezone_offset": "app.web_data.execution_layer.timezone_offset"}
    return json.dumps(_values(row).get(fields[group]), ensure_ascii=False)


def summarize_rows(rows):
    output = {"models": {}, "agreement": {}, "record_inventory": {
        "unique_records": len({r["sample_id"] for r in rows}), "model_evaluations": len(rows),
        "model_os_combinations": len({(r["profile"].get("manufacturer"), r["profile"].get("model"),
                                      r["profile"].get("android_release")) for r in rows if r["profile"]})}}
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model_id"]].append(r)
    for mid, model_rows in by_model.items():
        subsets = {}
        for subset in (*SUBSETS, *sorted({r["subset"] for r in model_rows} - set(SUBSETS))):
            current = [r for r in model_rows if r["subset"] == subset]
            result = counts(current)
            combinations = {(r["profile"].get("manufacturer"), r["profile"].get("model"), r["profile"].get("android_release")) for r in current if r["profile"]}
            result["model_os_combinations"] = len(combinations)
            rules, overlaps = {}, Counter()
            for r in current:
                triggers = [x["atom_id"] for x in r["rules"] if x.get("triggered")]
                if triggers:
                    overlaps[tuple(sorted(triggers))] += 1
                for rule in r["rules"]:
                    d = rules.setdefault(rule["atom_id"], {"T": 0, "F": 0, "U": 0, "FAILED": 0, "triggered": 0, "unique_alerts": 0, "normal_triggers": 0, "reasons": Counter()})
                    d[rule["state"] if rule["state"] in ("T", "F", "U") else "FAILED"] += 1
                    d["triggered"] += bool(rule.get("triggered"))
                    d["normal_triggers"] += bool(rule.get("triggered")) and r["normal_basis"].get("supported") is True
                    d["unique_alerts"] += rule.get("triggered") is True and len(triggers) == 1 and r["decision"] == "MANIPULATION_ALERT"
                    if rule["state"] not in ("T", "F"):
                        d["reasons"][rule.get("reason") or "UNSPECIFIED"] += 1
            result["rules"] = rules
            result["trigger_combinations"] = [{"rules": list(k), "n": v} for k, v in sorted(overlaps.items(), key=lambda x: (-x[1], x[0]))]
            result["groups"] = {}
            for group in ("manufacturer", "android_release", "collector_version", "device_memory", "device_pixel_ratio", "timezone_offset", "webview_major"):
                buckets = defaultdict(list)
                for r in current:
                    buckets[group_key(r, group)].append(r)
                result["groups"][group] = {k: counts(v) for k, v in sorted(buckets.items())}
            subsets[subset] = result
        output["models"][mid] = {"fold_id": model_rows[0]["fold_id"], "subsets": subsets}
    for subset in (*SUBSETS, *sorted({r["subset"] for r in rows} - set(SUBSETS))):
        samples = defaultdict(list)
        for r in rows:
            if r["subset"] == subset:
                samples[r["sample_id"]].append(r)
        expected = len(by_model)
        differences = [sid for sid, rr in samples.items() if len(rr) != expected or len({r["decision"] for r in rr}) != 1]
        rule_differences = [sid for sid, rr in samples.items() if len(rr) != expected or len({json.dumps([(q["atom_id"],q["state"],q.get("triggered")) for q in r["rules"]],sort_keys=True) for r in rr}) != 1]
        output["agreement"][subset] = {"distinct_records": len(samples), "models_per_record": expected,
            "same_decision_records": len(samples) - len(differences), "different_decision_ids": differences,
            "same_rule_states_records": len(samples) - len(rule_differences), "different_rule_state_ids": rule_differences}
    return output


def fraction(r):
    return f'{r["numerator"]}/{r["denominator"]}' + (f'（{r["ratio"]:.2%}）' if r["ratio"] is not None else '（无分母）')


def write_report(out, summary, run):
    main_stats = [m["subsets"][SUBSETS[0]] for m in summary["models"].values()]
    same_main = bool(main_stats) and all(s == main_stats[0] for s in main_stats)
    lead = (f'**三个模型分别回放后结果一致：{main_stats[0]["planned_records"]} 条主代表中报警 {main_stats[0]["alerts"]} 条，'
            f'有正常依据的已观察报警比例为 {fraction(main_stats[0]["normal_observed_alert_proportion"])}；'
            f'{main_stats[0]["unknown"]} 条无法判断，执行失败 {main_stats[0]["failed"]} 条。** '
            '这批正常真机上已有大量误报，原受控开发结果不能直接推广到真机。'
            if same_main else '三个模型分别回放，各自结果见下表，不选最好的一折。')
    lines = ["# 既有 MTC 真机数据上的补充回放评估", "",
        lead, "",
        "本轮只使用三个已保存 WEBGL50 / CAP8 / RETENTION 模型；无新训练、调阈值、删规则或投票。模型在运行前登记于 [MODELS.json](MODELS.json)。MTC 已参与早期关系发现、开发及评价，本轮不是独立盲测。", "",
        f'本轮共 {summary["record_inventory"]["unique_records"]} 条历史记录，覆盖 {summary["record_inventory"]["model_os_combinations"]} 个厂商／型号／系统组合，产生 {summary["record_inventory"]["model_evaluations"]} 次模型评估。主分析为 891 个组合；各子集组合有重叠，不能相加。', "",
        "主分析保留 P2 已选型号／系统代表；重复记录、App-only、partial 和同 session 额外观测分别报告。型号／系统组合不等于独立物理设备。正常条件指常规采集且没有实施本研究目标指纹篡改，允许调试连接与云平台自动化组件；依据及限制见 [DATA_NOTES.md](DATA_NOTES.md)，历史 unlabeled 未改写。", "",
        "## 实际结果", "", "每个单元格都是记录数；同一记录重复运行三个模型不增加样本量。明确输出覆盖和正常报警比例均保留未知、失败在分母内。", "",
        "| 模型折 | 数据子集 | 型号/系统组合 | 预定/处理 | 报警 | 明确不报警 | 未知 | 失败 | 明确输出覆盖 | 有正常依据的报警比例 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for m in summary["models"].values():
        for subset, s in m["subsets"].items():
            lines.append(f'| {m["fold_id"][-2:]} | {LABELS.get(subset, subset)} | {s["model_os_combinations"]} | {s["planned_records"]}/{s["processed_records"]} | {s["alerts"]} | {s["no_alert"]} | {s["unknown"]} | {s["failed"]} | {fraction(s["defined_coverage"])} | {fraction(s["normal_observed_alert_proportion"])} |')
    lines += ["", "无正常依据的记录只计报警比例，详见 summary.json；本次不能用未报警或未知宣称完整八条模型误报率为 0。", "", "## 哪些检查能测、误报由什么造成", "",
        "下表为每折主分析，T/F/U 是应用已保存极性后的规则值；数值条件保持原 NEGATIVE 极性（原子 LE 为 F 时规则触发）。独有报警表示该条是唯一触发规则。", "",
        "| 折 | 检查 | T | F | U | 失败 | 触发 | 独有报警 |",
        "|---|---|---:|---:|---:|---:|---:|---:|"]
    for m in summary["models"].values():
        for aid, stat in m["subsets"][SUBSETS[0]]["rules"].items():
            lines.append(f'| {m["fold_id"][-2:]} | {short_rule(aid)} | {stat["T"]} | {stat["F"]} | {stat["U"]} | {stat["FAILED"]} | {stat["triggered"]} | {stat["unique_alerts"]} |')
    lines += ["", "输入映射与单位见 [INPUT_MAPPING.md](INPUT_MAPPING.md)。逐记录保留输入值、原始状态、未知原因、规则极性与最终结果于 results.jsonl。", "",
        "旧 WebGL1 没有数字／数字字符串查询原始观测，始终 U；不由 GPU 名称推造。旧 webdriver false 无法分清真实 false、缺属性等，按既有 legacy 语义 U；true 只表示上报 true。deviceMemory 默认 0 保留为 U。其余值按冻结规则与编码器计算。硬件并发数并非这三个模型的已选规则，不参与本轮预测。", "",
        "## 分组、重复触发与解释", ""]
    group_models = list(summary["models"].items())[:1] if same_main else list(summary["models"].items())
    if same_main:
        lines += ["三个模型的下列统计逐项一致，分组和重叠表仅展示一份以避免重复；上述逐模型计数完整保留。", ""]
    for mid, m in group_models:
        s = m["subsets"][SUBSETS[0]]
        lines += [f'### 折 {m["fold_id"][-2:]}', "", f'模型 `{mid}`。', "", "触发组合（主分析）：", ""]
        for c in s["trigger_combinations"]:
            lines.append(f'- {" + ".join(short_rule(x) for x in c["rules"])}：{c["n"]}/{s["planned_records"]}。')
        lines += ["", "| 分组维度 | 取值 | 报警/记录 | 未知 |", "|---|---|---|---:|"]
        for g in ("device_memory", "collector_version", "android_release", "manufacturer"):
            grouped = list(s["groups"][g].items())
            if g == "manufacturer":
                grouped = sorted(grouped, key=lambda kv: -kv[1]["planned_records"])[:6]
            for value, stat in grouped:
                lines.append(f'| {g} | {value} | {fraction(stat["observed_alert_proportion"])} | {stat["unknown"]} |')
        for high in (False, True):
            bins = [v for k,v in s["groups"]["device_pixel_ratio"].items() if k != "null" and (float(k) > 2.625) == high]
            n, alerts, unknown = (sum(v[key] for v in bins) for key in ("planned_records", "alerts", "unknown"))
            lines.append(f'| device_pixel_ratio | {"> 2.625" if high else "<= 2.625"} | {fraction(ratio(alerts,n))} | {unknown} |')
        lines += [""]
    if same_main:
        s = main_stats[0]
        memory = next(v for k,v in s["rules"].items() if ".device_memory:LE:" in k)
        dpr = next(v for k,v in s["rules"].items() if ".device_pixel_ratio:LE:" in k)
        tz = next(v for k,v in s["rules"].items() if ".timezone_offset:LE:" in k)
        both = sum(c["n"] for c in s["trigger_combinations"] if any(".device_memory:LE:" in k for k in c["rules"]) and any(".device_pixel_ratio:LE:" in k for k in c["rules"]))
        lines += [f'内存规则触发 {memory["triggered"]}/891，贡献 {memory["unique_alerts"]} 条独有报警；DPR 触发 {dpr["triggered"]}/891，贡献 {dpr["unique_alerts"]} 条独有报警；两者重叠 {both} 条。时区触发 {tz["triggered"]}/891、独有 {tz["unique_alerts"]} 条，仅重复覆盖。其余五条未提供明确触发。', "",
            "报警直接集中于 navigator.deviceMemory 的 4/8 暴露值和 DPR 高于 2.625 的设备；这两个条件的并集覆盖全部主分析报警。v9、v11 和多个主流厂商均大量触发，不能归因于单一采集版本或某一个厂商。不同系统组有不同报警比例，但这里内存与显示配置也不同，不能单凭分组把系统版本当成原因。", ""]
    lines += ["厂商（上表仅列记录数最多六组）、Android 系统、WebView 版本原值、时区及所有补充子集的完整分组计数见 summary.json。WebView 的 -1 等历史原值未升级为确认的内核版本。这些是描述性统计，不作市场份额加权或因果归因。", "", "三模型逐记录比较：", ""]
    for subset, a in summary["agreement"].items():
        lines.append(f'- {LABELS.get(subset, subset)}：最终结果相同 {a["same_decision_records"]}/{a["distinct_records"]}；逐规则状态相同 {a["same_rule_states_records"]}/{a["distinct_records"]}。')
    lines += ["", "## 缺失观测与下一步", "",
        "主分析的 WebGL1 和 webdriver 各 891/891 为 U，无法确认任何完整八条模型的 NO_ALERT；65 条内存默认 0、4 条语言输入也无法用于对应检查。因此 47 条未知不是正确正常样本，844 条报警也不会因另两条未知而撤销。补采可能把部分未知变成报警或明确不报警，但不能抹去本轮已由可观测条件触发的报警。", "",
        "正常记录触发内存或 DPR 等规则，说明这些受控开发阈值把常见设备配置差异计作干预信号；应在后续独立授权的规则修订中优先检查其适用范围。本轮没有修改这些阈值。数值原值、单位、类型与 frozen encoder 均保留，具体分布见上表；默认 0 或缺失不作为真实低内存。", "",
        "优先修正规则解释与适用范围：不再将 deviceMemory > 2 或 DPR > 2.625 作为通用攻击证据；后续比较语义约束或限定适用条件时保留本轮反例。timezone_offset > -480 同样会命中合法时区，应一并复核。此处是建议，本轮模型保持原样。", "",
        "适配质量应由模式隔离、状态优先、原值保留和新输入路径与原预测等价测试判断；高报警比例本身不是适配错误的证据。旧 webdriver/WebGL1 的信息缺失属于采集能力限制，整层 timeout 也单列，不能通过适配还原。", "",
        "最小补采是对代表性的内存/DPR 范围、旧版本未知记录及目前没有触发的记录，追加同次 App 主 frame 的 WebGL1 数字/数字字符串查询结果，以及 webdriver 的属性存在、读取状态、类型和原始布尔值。资源字段改为保存 API 是否存在及读取成功状态，区分真值与默认哨兵。语言、UA/platform、时区、MIME、DPR 同次保留即可；当前八条模型不依赖独立 Browser 配对。无需先重采全套 244 字段，也不在本轮启动服务或设备任务。", "",
        "主分析的 4 条语言未知均为 observed 的空 languages 数组；最小补采应同时保存该 API 的存在与读取状态。MIME 的 0 也只能解释为旧版条目数投影，追加 API 状态可区分缺失与真正空列表。", "",
        "## 测试与复核", "",
        "真实回放前 56 项测试全部通过：20 项本轮适配/数据边界、2 项分母/重叠统计、34 项现有语言/webdriver 语义回归。未调用 fit；版本名等实现修正发生在首次真实回放前，详见 INPUT_MAPPING.md。原模型、新版入口、规则、阈值、历史数据和实验结果均未修改。", "",
        "## 复现与文件", "",
        "```bash", "python3 -m unittest hybridguard_agent.tests.test_mtc_cap8_replay hybridguard_agent.tests.test_mtc_cap8_summary hybridguard_agent.tests.test_rule_semantics_revision_v1",
        "# 真实回放写新目录，避免覆盖已保存结果", "python3 deliverables/mtc_cap8_replay_v1/run_replay.py run --output-dir /tmp/mtc_cap8_replay_new",
        "# 仅从保存结果重新汇总，不访问模型、不重新预测", "python3 deliverables/mtc_cap8_replay_v1/run_replay.py summarize --output-dir deliverables/mtc_cap8_replay_v1", "```", "",
        "- MODELS.json：运行前确定的三个模型及原路径、极性。",
        "- RUN.json：数据清单、读取问题、运行信息；不复制整套原始数据。",
        "- results.jsonl：逐条、逐模型预测和依据侧表。",
        "- summary.json：总体、逐规则、独有/重复触发、分组和模型一致性统计。",
        "- DATA_NOTES.md / INPUT_MAPPING.md：正常采集依据和输入语义。", "",
        f'运行时间：{run["finished_at"]}；读取问题数：{len(run["issues"])}。未自动提交、推送或开启下一阶段。', ""]
    if run["issues"]:
        lines += ["读取或执行问题（未静默排除）：", ""]
        lines.extend("- `" + json.dumps(issue, ensure_ascii=False) + "`" for issue in run["issues"])
    (out / "REPORT.md").write_text("\n".join(lines))


def summarize(out):
    rows = [json.loads(line) for line in (out / "results.jsonl").open()]
    run = json.loads((out / "RUN.json").read_text())
    summary = summarize_rows(rows)
    dump(out / "summary.json", summary)
    write_report(out, summary, run)
    return summary


def run_replay(out):
    from hybridguard_agent.research.mtc_cap8_data import load_mtc_replay_data
    from hybridguard_agent.research.mtc_cap8_replay import predict_historical_mtc, VERSION
    from hybridguard_agent.research.rule_semantics_webgl1_cap8 import load_model
    out.mkdir(parents=True, exist_ok=True)
    if (out / "results.jsonl").exists() or (out / "RUN.json").exists():
        raise FileExistsError("Replay requires a new results directory; use summarize to rebuild the report")
    selection = json.loads((HERE / "MODELS.json").read_text())
    loaded, issues = [], []
    for selected in selection["models"]:
        try:
            model = load_model(ROOT / selected["path"])
            if model.model_id != selected["model_id"]:
                raise ValueError("Saved model identity differs from pre-replay selection")
            loaded.append((selected, model, None))
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
            loaded.append((selected, None, error))
            issues.append({"model": selected["path"], "error": error})
    if out != HERE:
        dump(out / "MODELS.json", selection)
        for name in ("DATA_NOTES.md", "INPUT_MAPPING.md"):
            source = HERE / name
            if source.is_file() and not (out / name).exists():
                (out / name).write_bytes(source.read_bytes())
    data = load_mtc_replay_data(ROOT)
    issues.extend(data["issues"])
    with (out / "results.jsonl").open("x") as stream:
        for selected, model, model_error in loaded:
            for item in data["records"]:
                obs = item.get("observation") or {}
                error = item.get("load_error") or model_error
                try:
                    pred = predict_historical_mtc(model, obs) if not error else {"decision": "FAILED", "failure_reason": error}
                except Exception as exc:
                    pred = {"decision": "FAILED", "failure_reason": type(exc).__name__ + ": " + str(exc)}
                if not pred.get("rule_results"):
                    pred["rule_results"] = [{"clause_id": c["clause_id"], "atom_id": c["literals"][0]["atom_id"],
                        "polarity": c["literals"][0]["polarity"], "state": "FAILED", "reason": pred.get("failure_reason"),
                        "fields": [], "triggered": False} for c in selected["rules"]]
                row = {"sample_id": item["sample_id"], "subset": item["subset"], "model_id": selected["model_id"], "fold_id": selected["fold_id"],
                       "adapter_version": VERSION, "source_observation_mode": "legacy_projection_v1",
                       "profile": obs.get("profile", item.get("p2", {}).get("profile", {})),
                       "source_refs": obs.get("source_refs", {}), "metadata": item.get("metadata", {}),
                       "collector_version_code": obs.get("app", {}).get("collector_version_code"),
                       "collector_version_name": obs.get("app", {}).get("collector_version_name"),
                       "webview_major": obs.get("features", {}).get("app.webview_data.kernel_container_layer.webview_provider_major"),
                       "p2_group_id": item.get("p2", {}).get("group_id"), "historical_split": item.get("p2", {}).get("split"),
                       "historical_label": obs.get("label_status"), "normal_basis": item["normal_basis"],
                       "load_error": item.get("load_error"), "prediction_attempted": error is None,
                       "decision": pred["decision"], "logical_state": pred.get("logical_state"),
                       "failure_reason": pred.get("failure_reason"), "rules": pred.get("rule_results", []),
                       "triggered_rules": [x["atom_id"] for x in pred.get("rule_results", []) if x.get("triggered")]}
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    dump(out / "RUN.json", {"adapter_version": VERSION, "finished_at": datetime.now(timezone.utc).isoformat(),
          "evaluation_role": "SUPPLEMENTAL_REPLAY_ON_PREVIOUSLY_USED_MTC", "inventory": data["inventory"], "issues": issues,
          "models_selected_before_predictions": True, "new_training": False, "rule_changes": False})
    return summarize(out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("run", "summarize"))
    p.add_argument("--output-dir", type=Path, default=HERE)
    args = p.parse_args()
    result = run_replay(args.output_dir.resolve()) if args.command == "run" else summarize(args.output_dir.resolve())
    print(json.dumps({mid: {s: {k: v for k,v in stats.items() if k in ("planned_records","alerts","no_alert","unknown","failed")} for s,stats in model["subsets"].items()} for mid,model in result["models"].items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
