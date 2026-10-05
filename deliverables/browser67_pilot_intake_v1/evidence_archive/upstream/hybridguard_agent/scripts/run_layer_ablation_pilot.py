#!/usr/bin/env python3
"""Replay frozen rules on isolated App177 layer views; no training or tuning.

This is an input-availability pilot, not a comparison of optimally designed
single-layer detectors. Browser67 has no frozen decision path here and remains
NOT_EVALUATED. Labels are joined only after each stage has been evaluated.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.evidence.extractor import (
    LAYER_NAMES, build_evidence_bundle_v2, normalize_payload,
)
from hybridguard_agent.official_semantics.evaluator import (
    evaluate_official_semantics, load_semantic_catalog,
)
from hybridguard_agent.rules.executor import (
    execute_deterministic_rules, load_predicate_registry,
)
from hybridguard_agent.runtime.snapshot_loader import load_latest_runtime_samples
from hybridguard_agent.scripts.run_two_source_rule_classification import (
    attack_reference, load_attack_pairs, repo_relative, write_csv, write_json, write_jsonl,
)
from hybridguard_agent.validation_inputs import (
    attach_and_validate_observed_counts, resolve_attack_inputs,
)

DEFAULT_INPUT_SET = REPO_ROOT / "knowledge_rule_validation/config/layer_ablation_attack_input_set.v1.json"
NATIVE, HOST, WEB = LAYER_NAMES
GROUPS = {
    "native84": (NATIVE,),
    "webview_host26": (HOST,),
    "app_web67": (WEB,),
    "native_host110": (NATIVE, HOST),
    "native_appweb151": (NATIVE, WEB),
    "host_appweb93": (HOST, WEB),
    "app177": (NATIVE, HOST, WEB),
}
LANES = ("device_mined", "official_derived")
ASSESSED = {"matched", "not_matched", "consistent", "inconsistent", "context_observed"}
BLOCKED_GROUPS = {
    "browser67": "No frozen standalone Browser67 detector or attack-paired Browser67 input in this pilot.",
    "full244": "Attack cohort is App177 only; current Browser pairing sidecar is observation-only, not rule-assessed.",
}


def mask_payload(payload: dict, layers: tuple[str, ...]) -> dict:
    """Drop other layers BEFORE extraction, including nested wrappers/statuses."""
    if not layers or not set(layers) <= set(LAYER_NAMES):
        raise ValueError("Only nonempty App-layer views are executable")
    normalized, states = normalize_payload(payload)
    result = {key: normalized[key] for key in ("collector_app", "schema_version")}
    result.update({layer: copy.deepcopy(normalized[layer]) for layer in layers})
    result["collection_status"] = {"fields": {
        field: state for field, state in states.items()
        if field.split(".", 1)[0] in layers
    }}
    return result


def evaluate_view(payload: dict, layers: tuple[str, ...], *, catalog: dict, registry: dict) -> dict:
    masked = mask_payload(payload, layers)
    bundle = build_evidence_bundle_v2(masked, sample_id="blind-view")
    device = execute_deterministic_rules(bundle, predicate_registry=registry)
    semantic = evaluate_official_semantics(masked, sample_id="blind-view", catalog=catalog)
    output = {}
    for lane, rules in (
        ("device_mined", device["rule_results"]),
        ("official_derived", semantic["relation_execution"]["relation_results"]),
    ):
        rows = []
        for rule in rules:
            # Keep catalog/compiled predicate semantics unchanged. In particular,
            # do not split a multi-layer OR predicate into a new single-layer rule.
            excluded = sorted(({field.split(".", 1)[0] for field in rule["source_fields"]} & set(LAYER_NAMES)) - set(layers))
            outcome = rule["outcome"]
            reason = None
            if excluded:
                if outcome in {"matched", "inconsistent"}:
                    raise ValueError("A frozen predicate used an ablated dependency")
                outcome, reason = "not_evaluated", "ablated_layer"
            elif outcome == "not_evaluated":
                reason = "existing_short_circuit"
            elif outcome in {"unknown", "unavailable", "not_applicable"}:
                reason = "source_missing_unavailable_or_inapplicable"
            alert_capable = (
                rule.get("severity") == "strong" if lane == "official_derived"
                else "context_v1" not in rule["predicate_id"]
            )
            rows.append({
                "id": rule.get("rule_id", rule.get("relation_id")),
                "outcome": outcome, "not_evaluated_reason": reason,
                "source_fields": rule["source_fields"],
                "severity": rule.get("severity"),
                "alert_capable": alert_capable,
                "alert": alert_capable and outcome in {"matched", "inconsistent"},
            })
        assessable = [row["id"] for row in rows if row["alert_capable"] and row["outcome"] in ASSESSED]
        hits = [row["id"] for row in rows if row["alert"]]
        output[lane] = {
            "status": "ALERT" if hits else "NO_ALERT_OBSERVED" if assessable else "NOT_EVALUATED",
            "alert": bool(hits) if assessable else None,
            "assessed_alert_rule_ids": assessable,
            "matched_rule_ids": hits,
            "soft_inconsistency_ids": [row["id"] for row in rows if row["severity"] == "soft" and row["outcome"] == "inconsistent"],
            "outcome_counts": dict(Counter(row["outcome"] for row in rows)),
            "rules": rows,
        }
    return output


def compare_stages(baseline: dict, active: dict) -> dict:
    before = {row["id"]: row for row in baseline["rules"]}
    added = [rule for rule in active["matched_rule_ids"] if rule not in baseline["matched_rule_ids"]]
    transitions = [rule for rule in added if before[rule]["outcome"] in ASSESSED]
    return {
        "baseline_status": baseline["status"], "active_status": active["status"],
        "baseline_alert": baseline["alert"], "active_alert": active["alert"],
        "active_soft_inconsistency_ids": active["soft_inconsistency_ids"],
        "baseline_assessed_alert_rules": len(baseline["assessed_alert_rule_ids"]),
        "active_assessed_alert_rules": len(active["assessed_alert_rule_ids"]),
        "new_matched_rule_ids": added,
        "assessed_to_alert_rule_ids": transitions,
        "indeterminate_to_alert_rule_ids": sorted(set(added) - set(transitions)),
        "new_alert_pair": baseline["alert"] is False and active["alert"] is True,
    }


def summarize(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[key] for key in keys)].append(row)
    summary = []
    for values, members in sorted(grouped.items()):
        summary.append({
            **dict(zip(keys, values)), "pair_count": len(members),
            "baseline_alert_pairs": sum(row["baseline_alert"] is True for row in members),
            "active_alert_pairs": sum(row["active_alert"] is True for row in members),
            "active_soft_inconsistency_pairs": sum(bool(row["active_soft_inconsistency_ids"]) for row in members),
            "baseline_not_evaluated_pairs": sum(row["baseline_alert"] is None for row in members),
            "active_not_evaluated_pairs": sum(row["active_alert"] is None for row in members),
            "new_alert_pairs": sum(row["new_alert_pair"] for row in members),
            "pairs_with_assessed_rule_to_alert": sum(bool(row["assessed_to_alert_rule_ids"]) for row in members),
            "pairs_with_indeterminate_to_alert": sum(bool(row["indeterminate_to_alert_rule_ids"]) for row in members),
            "mean_active_assessed_alert_rules": round(sum(row["active_assessed_alert_rules"] for row in members) / len(members), 3),
        })
    return summary


def write_table(path: Path, rows: list[dict]) -> None:
    if rows:
        write_csv(path, list(rows[0]), rows)
    else:
        path.write_text("", encoding="utf-8")


def render_report(manifest: dict, summary: list[dict], configuration: list[dict]) -> str:
    counts = manifest["attack_inputs"]["observed_counts"]
    by_group = {(row["lane"], row["group"]): row for row in summary}
    empirical_web = by_group.get(("device_mined", "app_web67"), {})
    empirical_all = by_group.get(("device_mined", "app177"), {})
    semantic_nw = by_group.get(("official_derived", "native_appweb151"), {})
    semantic_all = by_group.get(("official_derived", "app177"), {})
    lines = [
        "# 单端与跨端规则输入消融 pilot", "",
        "本次固定现有经验规则与官方派生语义规则，逐条重建各输入视图的证据后重跑。两类判别器分别统计，不融合。没有模型训练、LLM 调用、阈值调整或正式测试集评估。", "",
        f"攻击材料：{counts['selected_manifest_count']} 个清单、{counts['eligible_pair_count']} 组合格 baseline→attack_active 对照、{counts['unique_config_id_count']} 个配置。沿用已接受的两态协议，{counts['ignored_historical_post_count']} 条历史 post 不参与本实验。旧设计已见与后续扩展 cohort 在 cohort_summary.csv 中分别保留；这些材料均不构成新的独立留出集。", "",
        "这是固定规则库的输入依赖和覆盖比较，不是为每一端重新设计最优检测器。分母是重复采集的受控对照对，不是独立设备数。App177 表示当前字段契约/输入上限，不表示每条记录177项均可用。", "",
        f"本轮经验规则的 App Web 单端/完整 App177 新增报警对数分别为 {empirical_web.get('new_alert_pairs', 0)}/{empirical_all.get('new_alert_pairs', 0)}；官方派生强语义规则的 Native＋App Web/完整 App177 分别为 {semantic_nw.get('new_alert_pairs', 0)}/{semantic_all.get('new_alert_pairs', 0)}。这只描述本轮配置，不能据此宣称三端必胜、单端一般无效或宿主层无用。", "",
        "## 输入组与判别边界", "",
        "Native84、WebView host26、App Web67，以及三种双端组合和 App177 全量组，均使用完全相同的攻击对。其他层在任何派生特征计算之前删除，保留所选层原有字段状态；规则缺少被删除的前提时为 NOT_EVALUATED，不补零、不作为异常、不拆分原规则。既有短路行为保留。", "",
        "Browser67 与 Full244：NOT_EVALUATED。本轮攻击材料无完整配对 Browser67，且现有 Browser sidecar 尚未进入判别；不把 App Web67 改名为 Browser67，也不替 Full244 填入 App177 结果。", "",
        "## 同一批攻击对的对比", "",
        "报警只表示当前规则命中/强语义矛盾；未报警不等于正常。无报警转报警要求 baseline 已有可评估报警规则，不能把 unknown→alert 当成无报警→报警。另保留同一规则从可评估非命中到命中的明细。NOT_EVALUATED 表示没有可评估的报警规则，仍可能执行了软偏差或上下文规则；软偏差不能升级为强报警，也不能与强报警计数相加。", "",
        "| 判别器 | 输入组 | 对照对 | baseline 报警 | active 报警 | active 软偏差 | 无报警→报警 | active 无可评估报警规则 | 平均可评估报警规则数 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(f"| {row['lane']} | {row['group']} | {row['pair_count']} | {row['baseline_alert_pairs']} | {row['active_alert_pairs']} | {row['active_soft_inconsistency_pairs']} | {row['new_alert_pairs']} | {row['active_not_evaluated_pairs']} | {row['mean_active_assessed_alert_rules']} |")
    lines += ["", "## 按攻击配置比较单端与全 App", "",
              "每格为 active 报警计数/对照对数，全部无可评估报警规则时显示 N/E。这些是描述性计数，不是检测率。", "",
              "| 判别器 | 配置 | Native84 | 宿主26 | App Web67 | App177 |", "|---|---|---:|---:|---:|---:|"]
    pivot = defaultdict(dict)
    for row in configuration:
        pivot[(row["lane"], row["config_id"])][row["group"]] = row
    for (lane, config), groups in sorted(pivot.items()):
        cells = []
        for group in ("native84", "webview_host26", "app_web67", "app177"):
            row = groups[group]
            cells.append("N/E" if row["active_not_evaluated_pairs"] == row["pair_count"] else f"{row['active_alert_pairs']}/{row['pair_count']}")
        lines.append(f"| {lane} | {config} | " + " | ".join(cells) + " |")
    lines += ["", "## 最新采集数据与后续正式实验", "",
              "最新采集数据只单独用于输入可用性/无标签判别 QC，不作为正常负例，不与攻击材料拼接计算准确率、F1、FPR 或召回率。", "",
              "```json", json.dumps(manifest["latest_qc"], ensure_ascii=False, indent=2), "```", "",
              "后续补齐同一设备/配置/阶段的 App177＋Browser67、独立设备组和可核验标签，再冻结实际消费 Browser 证据的判别器。按设备/场景分组开展正式实验；本次不训练、不调规则，也不把现有结果称为单端或跨端的一般性能。", "",
              "复核入口：pair_results.jsonl（逐对）、stage_results.jsonl（逐规则）、cohort_summary.csv（设计暴露分层）、configuration_summary.csv（配置分层）、latest_qc_results.jsonl（无标签QC）、run_manifest.json（输入选择与执行边界）。", ""]
    return "\n".join(lines)


def run_pilot(*, output_dir: Path, input_set: Path = DEFAULT_INPUT_SET, latest_snapshot: Path | None = None) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite pilot output: {output_dir}")
    selection = resolve_attack_inputs(input_set_path=input_set)
    pairs = load_attack_pairs(selection.manifests)
    attach_and_validate_observed_counts(selection, pairs)
    catalog, registry = load_semantic_catalog(), load_predicate_registry()
    stages, comparisons, excluded = [], [], []
    for pair in pairs:
        if not pair["eligible_for_two_state_validation"]:
            excluded.append({"pair_ref": pair["pair_ref"], "issues": pair["eligibility_issues"]})
            continue
        for group, layers in GROUPS.items():
            # No manifest/tool/label facts are passed to either decision function.
            before = evaluate_view(pair["baseline"]["raw_payload"], layers, catalog=catalog, registry=registry)
            after = evaluate_view(pair["attack_active"]["raw_payload"], layers, catalog=catalog, registry=registry)
            metadata = selection.metadata_by_manifest[pair["manifest_path"].resolve()]
            reference = attack_reference(pair["attack_active"], pair["manifest_path"])
            common = {"pair_ref": pair["pair_ref"], "group": group,
                      "cohort_id": metadata["cohort_id"],
                      "relation_design_exposure": metadata["relation_design_exposure"],
                      "config_id": reference["config_id"], "tool_name": reference["tool_name"]}
            for lane in LANES:
                for stage, result in (("baseline", before[lane]), ("attack_active", after[lane])):
                    member = pair[stage]
                    stages.append({**common, "lane": lane, "stage": stage,
                                   "input_ref": f"{repo_relative(pair['raw_payload_path'])}#line={member['raw_line']}", **result})
                comparisons.append({**common, "lane": lane, **compare_stages(before[lane], after[lane])})
    latest_rows, latest_qc = [], {"status": "NOT_SUPPLIED", "labels_used": False}
    if latest_snapshot is not None:
        samples = load_latest_runtime_samples(latest_snapshot)
        latest_qc = {"status": "UNLABELED_QC_ONLY", "labels_used": False,
                     "sample_count": len(samples),
                     "view_counts": dict(Counter(sample.input_quality["dataset_view"] for sample in samples)),
                     "source_snapshot": str(latest_snapshot.resolve())}
        for sample in samples:
            for group, layers in GROUPS.items():
                wrapped = {"payload": sample.normalized_payload, "field_status": sample.field_status}
                for lane, result in evaluate_view(wrapped, layers, catalog=catalog, registry=registry).items():
                    latest_rows.append({"sample_id": sample.sample_id, "dataset_view": sample.input_quality["dataset_view"],
                                        "group": group, "lane": lane, **result})
    manifest = {
        "pilot_version": "layer-input-ablation-pilot-v1",
        "attack_inputs": selection.provenance, "groups": GROUPS,
        "not_evaluated_groups": BLOCKED_GROUPS, "excluded_pairs": excluded,
        "latest_qc": latest_qc,
        "frozen_catalog_version": catalog["catalog_version"],
        "frozen_predicate_registry_version": registry["predicate_registry_version"],
        "compiled_rule_counts": {"device_mined": len(registry["compiled_rules"]),
                                 "official_derived": sum(row["executable_status"] == "compiled_v1" for row in catalog["relations"])},
        "execution": {"trained_model": False, "external_model_called": False,
                      "thresholds_tuned": False, "formal_evaluation": False,
                      "browser_evidence_used_for_decisions": False},
    }
    summary = summarize(comparisons, ("lane", "group"))
    configuration = summarize(comparisons, ("lane", "config_id", "group"))
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir / "run_manifest.json", manifest)
    write_json(output_dir / "semantic_catalog_snapshot.json", catalog)
    write_json(output_dir / "predicate_registry_snapshot.json", registry)
    write_jsonl(output_dir / "stage_results.jsonl", stages)
    write_jsonl(output_dir / "pair_results.jsonl", comparisons)
    write_jsonl(output_dir / "latest_qc_results.jsonl", latest_rows)
    write_table(output_dir / "summary.csv", summary)
    write_table(output_dir / "configuration_summary.csv", configuration)
    write_table(output_dir / "cohort_summary.csv", summarize(comparisons, ("lane", "cohort_id", "group")))
    (output_dir / "单端与跨端消融报告.md").write_text(render_report(manifest, summary, configuration), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attack-input-set", type=Path, default=DEFAULT_INPUT_SET)
    parser.add_argument("--latest-snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_pilot(output_dir=args.output_dir, input_set=args.attack_input_set, latest_snapshot=args.latest_snapshot)
    print(json.dumps({"output_dir": str(args.output_dir), "counts": result["attack_inputs"]["observed_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
