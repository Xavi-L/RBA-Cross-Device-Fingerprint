#!/usr/bin/env python3
"""Validate official-document-derived semantic relations on two isolated cohorts.

The semantic decision sees only the collected payload and the reviewed
``official_derived_semantic_rule`` catalog.  Attack manifests are joined only
after both stage decisions have been produced, for eligibility, provenance,
grouping and direct ``baseline -> attack_active`` feature comparison.

Historical ``clean_post`` records are counted and ignored.  The runner neither
mines thresholds nor executes the separate device-mined rule registry.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.adapters.official_kb_adapter import (  # noqa: E402
    DEFAULT_OFFICIAL_CARDS,
    load_official_cards,
    sha256_file,
)
from hybridguard_agent.official_semantics.evaluator import (  # noqa: E402
    DEFAULT_SEMANTIC_CATALOG,
    evaluate_official_semantics,
    load_semantic_catalog,
)
from hybridguard_agent.scripts.run_two_source_rule_classification import (  # noqa: E402
    TWO_STATE_PROTOCOL_VERSION,
    direct_feature_comparison,
    load_attack_pairs,
    read_jsonl,
    repo_relative,
    stable_sample_id,
)
from hybridguard_agent.validation_inputs import (  # noqa: E402
    AttackInputSelection,
    attach_and_validate_observed_counts,
    resolve_attack_inputs,
)


SEMANTIC_VALIDATION_VERSION = "official-semantic-validation-v1"
NORMAL_RESULTS_FILENAME = "normal_semantic_results.jsonl"
ATTACK_RESULTS_FILENAME = "attack_semantic_pair_results.jsonl"
RELATION_SUMMARY_FILENAME = "semantic_relation_summary.csv"
CATALOG_SNAPSHOT_FILENAME = "semantic_relation_catalog_snapshot.json"
MANIFEST_FILENAME = "official_semantic_validation_manifest.json"
REPORT_FILENAME = "官方知识语义关联规则验证报告.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--normal-input", required=True, type=Path)
    attack_inputs = parser.add_mutually_exclusive_group()
    attack_inputs.add_argument(
        "--attack-manifest", action="append", default=[], type=Path
    )
    attack_inputs.add_argument("--attack-input-set", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def source_session_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("session_id")
    return value if isinstance(value, str) and value else None


def semantic_record(
    *,
    run_id: str,
    payload: dict[str, Any],
    sample_id: str,
    record_kind: str,
    stage: str,
    input_path: Path,
    input_line: int,
    pair_ref: str | None = None,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate without copying raw fingerprint values into the result."""

    result = evaluate_official_semantics(payload, sample_id=sample_id, catalog=catalog)
    return {
        "semantic_validation_version": SEMANTIC_VALIDATION_VERSION,
        "run_id": run_id,
        "knowledge_source_type": result["knowledge_source_type"],
        "record_kind": record_kind,
        "stage": stage,
        "pair_ref": pair_ref,
        "sample_id": sample_id,
        "source_session_id": source_session_id(payload),
        "input_ref": f"{repo_relative(input_path)}#line={input_line}",
        "decision": result["decision"],
        "relation_execution": result["relation_execution"],
        "decision_input_boundary": (
            "Payload fields plus the reviewed official-derived semantic catalog only; "
            "attack labels, tool names and device-mined predicates were not inputs."
        ),
    }


def relation_outcomes(record: dict[str, Any]) -> dict[str, str]:
    return {
        row["relation_id"]: row["outcome"]
        for row in record["relation_execution"]["relation_results"]
    }


def compact_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    decision = record["decision"]
    return {
        "sample_id": record["sample_id"],
        "decision_status": decision["decision_status"],
        "conclusion": decision["conclusion"],
        "research_semantic_alert": decision["research_semantic_alert"],
        "strong_inconsistency_relation_ids": decision[
            "strong_inconsistency_relation_ids"
        ],
        "soft_inconsistency_relation_ids": decision["soft_inconsistency_relation_ids"],
        "context_relation_ids": decision["context_relation_ids"],
        "indeterminate_relation_ids": decision["indeterminate_relation_ids"],
        "calibrated_risk_score": None,
        "evidence_hash": record["relation_execution"]["evidence_hash"],
        "relation_outcomes": relation_outcomes(record),
    }


def mutation_summaries(active_member: dict[str, Any] | None) -> list[dict[str, Any]]:
    if active_member is None:
        return []
    manifest = active_member["manifest"]
    attack = manifest.get("attack") if isinstance(manifest.get("attack"), dict) else {}
    mutations = attack.get("observed_mutations") if isinstance(attack, dict) else []
    if not isinstance(mutations, list):
        return []
    return [
        {
            "field_path": mutation.get("field_path"),
            "change_summary": mutation.get("change_summary"),
        }
        for mutation in mutations
        if isinstance(mutation, dict)
    ]


def tool_reference(active_member: dict[str, Any] | None) -> dict[str, Any]:
    if active_member is None:
        return {}
    manifest = active_member["manifest"]
    attack = manifest.get("attack") if isinstance(manifest.get("attack"), dict) else {}
    if not isinstance(attack, dict):
        attack = {}
    return {
        "tool_name": attack.get("tool_name"),
        "tool_version": attack.get("tool_version"),
        "attack_family": attack.get("attack_family"),
        "attack_type": attack.get("attack_type"),
        "config_id": attack.get("config_id"),
        "execution_status": attack.get("execution_status"),
        "feature_effect_status": attack.get("feature_effect_status"),
    }


def alert_transition(
    baseline: dict[str, Any] | None, active: dict[str, Any] | None
) -> str:
    if baseline is None or active is None:
        return "pair_incomplete_not_classified"
    baseline_alert = bool(baseline["decision"]["research_semantic_alert"])
    active_alert = bool(active["decision"]["research_semantic_alert"])
    if not baseline_alert and active_alert:
        return "baseline_no_alert_to_attack_active_alert"
    if baseline_alert and active_alert:
        return "alert_in_both_stages"
    if baseline_alert:
        return "baseline_alert_attack_active_not_alert"
    return "no_research_semantic_alert_in_either_stage"


def evaluate_inputs(
    *,
    run_id: str,
    normal_input: Path,
    attack_manifests: list[Path],
    attack_metadata_by_manifest: dict[Path, dict[str, str]],
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    relation_index = {
        relation["relation_id"]: relation for relation in catalog["relations"]
    }
    normal_records: list[dict[str, Any]] = []
    for line_number, payload in read_jsonl(normal_input):
        normal_records.append(
            semantic_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id(
                    "official-semantic-normal",
                    source_session_id(payload),
                    f"{repo_relative(normal_input)}#line={line_number}",
                ),
                record_kind="normal_input",
                stage="normal",
                input_path=normal_input,
                input_line=line_number,
                catalog=catalog,
            )
        )

    pair_results: list[dict[str, Any]] = []
    for pair in load_attack_pairs(attack_manifests):
        input_metadata = attack_metadata_by_manifest[pair["manifest_path"].resolve()]
        baseline_member = pair["baseline"]
        active_member = pair["attack_active"]
        baseline_record: dict[str, Any] | None = None
        active_record: dict[str, Any] | None = None
        if baseline_member is not None:
            payload = baseline_member["raw_payload"]
            baseline_record = semantic_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id(
                    "official-semantic-baseline",
                    source_session_id(payload),
                    pair["pair_ref"],
                ),
                record_kind="attack_stage",
                stage="baseline",
                input_path=pair["raw_payload_path"],
                input_line=baseline_member["raw_line"],
                pair_ref=pair["pair_ref"],
                catalog=catalog,
            )
        if active_member is not None:
            payload = active_member["raw_payload"]
            active_record = semantic_record(
                run_id=run_id,
                payload=payload,
                sample_id=stable_sample_id(
                    "official-semantic-active",
                    source_session_id(payload),
                    pair["pair_ref"],
                ),
                record_kind="attack_stage",
                stage="attack_active",
                input_path=pair["raw_payload_path"],
                input_line=active_member["raw_line"],
                pair_ref=pair["pair_ref"],
                catalog=catalog,
            )

        comparison = None
        if baseline_member is not None and active_member is not None:
            comparison = direct_feature_comparison(
                baseline_member["raw_payload"],
                active_member["raw_payload"],
                mutation_summaries(active_member),
            )
        compact_baseline = compact_record(baseline_record)
        compact_active = compact_record(active_record)
        new_inconsistencies: list[str] = []
        if compact_baseline is not None and compact_active is not None:
            new_inconsistencies = sorted(
                relation_id
                for relation_id, active_outcome in compact_active[
                    "relation_outcomes"
                ].items()
                if active_outcome == "inconsistent"
                and compact_baseline["relation_outcomes"].get(relation_id) != "inconsistent"
            )
        new_strong_inconsistencies = [
            relation_id
            for relation_id in new_inconsistencies
            if relation_index[relation_id]["severity"] == "strong"
        ]
        new_soft_inconsistencies = [
            relation_id
            for relation_id in new_inconsistencies
            if relation_index[relation_id]["severity"] == "soft"
        ]
        changed_fields = {
            item["field_path"]
            for item in (comparison or {}).get("direct_changed_fields", [])
            if isinstance(item, dict) and isinstance(item.get("field_path"), str)
        }
        direct_premise_evidence = [
            {
                "relation_id": relation_id,
                "severity": relation_index[relation_id]["severity"],
                "direct_changed_premise_fields": sorted(
                    set(relation_index[relation_id]["premise_fields"]) & changed_fields
                ),
            }
            for relation_id in new_inconsistencies
        ]
        pair_results.append(
            {
                "semantic_attack_pair_result_version": SEMANTIC_VALIDATION_VERSION,
                "run_id": run_id,
                "knowledge_source_type": catalog["knowledge_source_type"],
                "protocol_version": TWO_STATE_PROTOCOL_VERSION,
                "pair_ref": pair["pair_ref"],
                "pair_id": pair["pair_id"],
                "attack_manifest_ref": repo_relative(pair["manifest_path"]),
                "raw_payload_ref": repo_relative(pair["raw_payload_path"]),
                "input_cohort_id": input_metadata["cohort_id"],
                "input_cohort_label": input_metadata["cohort_label"],
                "relation_design_exposure": input_metadata[
                    "relation_design_exposure"
                ],
                "acceptance_reference": input_metadata["acceptance_reference"],
                "eligible_for_two_state_validation": pair[
                    "eligible_for_two_state_validation"
                ],
                "eligibility_issues": pair["eligibility_issues"],
                "ignored_historical_post_count": pair[
                    "ignored_historical_post_count"
                ],
                "tool": tool_reference(active_member),
                "baseline": compact_baseline,
                "attack_active": compact_active,
                "research_semantic_alert_transition": alert_transition(
                    baseline_record, active_record
                ),
                "new_inconsistency_relation_ids": new_inconsistencies,
                "new_strong_inconsistency_relation_ids": new_strong_inconsistencies,
                "new_soft_inconsistency_relation_ids": new_soft_inconsistencies,
                "new_inconsistency_direct_premise_evidence": direct_premise_evidence,
                "all_new_strong_inconsistencies_have_direct_premise_change": bool(
                    new_strong_inconsistencies
                )
                and all(
                    item["direct_changed_premise_fields"]
                    for item in direct_premise_evidence
                    if item["severity"] == "strong"
                ),
                "feature_comparison": comparison,
                "decision_join_order": (
                    "Both semantic decisions were computed from payloads before attack "
                    "manifest metadata was joined for validation reporting."
                ),
                "claim_boundary": catalog["boundary"],
            }
        )
    return normal_records, pair_results


def outcome_counts(records: Iterable[dict[str, Any]], relation_id: str) -> dict[str, int]:
    counts = Counter(
        relation_outcomes(record).get(relation_id, "not_evaluated") for record in records
    )
    return dict(sorted(counts.items()))


def pair_outcome_counts(
    pairs: Iterable[dict[str, Any]], stage: str, relation_id: str
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for pair in pairs:
        member = pair.get(stage)
        if isinstance(member, dict):
            counts[member["relation_outcomes"].get(relation_id, "not_evaluated")] += 1
    return dict(sorted(counts.items()))


def build_relation_summary(
    catalog: dict[str, Any],
    normal_records: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    eligible = [pair for pair in pairs if pair["eligible_for_two_state_validation"]]
    rows: list[dict[str, Any]] = []
    for relation in catalog["relations"]:
        relation_id = relation["relation_id"]
        compiled = relation["executable_status"] == "compiled_v1"
        if compiled:
            normal_counts: Any = outcome_counts(normal_records, relation_id)
            baseline_counts: Any = pair_outcome_counts(eligible, "baseline", relation_id)
            active_counts: Any = pair_outcome_counts(eligible, "attack_active", relation_id)
            new_inconsistency_count: Any = sum(
                relation_id in pair["new_inconsistency_relation_ids"] for pair in eligible
            )
        else:
            normal_counts = {"not_executed": len(normal_records)}
            baseline_counts = {"not_executed": len(eligible)}
            active_counts = {"not_executed": len(eligible)}
            new_inconsistency_count = "not_applicable"
        rows.append(
            {
                "relation_id": relation_id,
                "relation_name": relation["name"],
                "relation_type": relation["relation_type"],
                "inference_level": relation["inference_level"],
                "executable_status": relation["executable_status"],
                "predicate_id": relation["predicate_id"],
                "severity": relation["severity"],
                "risk_use_status": relation["risk_use_status"],
                "premise_fields": relation["premise_fields"],
                "official_card_refs": relation["official_card_refs"],
                "official_source_refs": relation["official_source_refs"],
                "tolerance": relation["tolerance"],
                "counterexamples": relation["counterexamples"],
                "validation_status": relation["validation_status"],
                "normal_outcome_counts": normal_counts,
                "attack_baseline_outcome_counts": baseline_counts,
                "attack_active_outcome_counts": active_counts,
                "baseline_to_active_new_inconsistency_count": new_inconsistency_count,
            }
        )
    return rows


def decision_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    return dict(
        sorted(Counter(record["decision"]["decision_status"] for record in records).items())
    )


def count_outcome(summary: dict[str, Any], outcome: str) -> int:
    value = summary.get(outcome, 0)
    return int(value) if isinstance(value, int) else 0


def write_report(
    path: Path,
    *,
    run_id: str,
    catalog: dict[str, Any],
    normal_records: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    relation_summary: list[dict[str, Any]],
    attack_input_selection: dict[str, Any],
) -> None:
    compiled = [row for row in relation_summary if row["executable_status"] == "compiled_v1"]
    pending = [row for row in relation_summary if row["executable_status"] != "compiled_v1"]
    eligible = [pair for pair in pairs if pair["eligible_for_two_state_validation"]]
    normal_alerts = sum(record["decision"]["research_semantic_alert"] for record in normal_records)
    baseline_alerts = sum(
        bool(pair["baseline"]["research_semantic_alert"])
        for pair in eligible
        if pair["baseline"]
    )
    active_alerts = sum(
        bool(pair["attack_active"]["research_semantic_alert"])
        for pair in eligible
        if pair["attack_active"]
    )
    transitions = [
        pair
        for pair in eligible
        if pair["research_semantic_alert_transition"]
        == "baseline_no_alert_to_attack_active_alert"
    ]
    directly_supported_transitions = sum(
        pair["all_new_strong_inconsistencies_have_direct_premise_change"]
        for pair in transitions
    )
    no_alert_pairs = [
        pair
        for pair in eligible
        if pair["attack_active"]
        and not pair["attack_active"]["research_semantic_alert"]
    ]
    normal_indeterminate = sum(
        bool(record["decision"]["indeterminate_relation_ids"])
        for record in normal_records
    )
    per_tool: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    per_cohort: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for pair in eligible:
        tool = pair["tool"]
        key = (
            str(tool.get("tool_name") or "unknown"),
            str(tool.get("tool_version") or "unknown"),
            str(tool.get("config_id") or "unknown"),
        )
        per_tool[key].append(pair)
        cohort_key = (
            str(pair.get("input_cohort_id") or "unknown"),
            str(pair.get("input_cohort_label") or "unknown"),
            str(pair.get("relation_design_exposure") or "not_declared"),
        )
        per_cohort[cohort_key].append(pair)
    pending_statuses: dict[str, list[str]] = defaultdict(list)
    for row in pending:
        pending_statuses[row["executable_status"]].append(row["relation_id"])

    design_exposures = {key[2] for key in per_cohort}
    if {
        "inspected_before_semantic_catalog_freeze",
        "not_inspected_before_semantic_catalog_freeze",
    }.issubset(design_exposures):
        design_interpretation = (
            "旧版 cohort 曾参与语义目录设计观察；新增 cohort 在目录冻结前未被查看，"
            "可用于检查冻结关系面对新增配置时的行为。但本次未预注册，且仍来自同一受控"
            "模拟器/采集体系，因此不是独立真机留出集或攻击泛化证明。"
        )
    elif "inspected_before_semantic_catalog_freeze" in design_exposures:
        design_interpretation = (
            "本次攻击样本在语义目录冻结前已被查看，只能解释为同语料回顾性执行覆盖，"
            "不是独立留出验证。"
        )
    else:
        design_interpretation = (
            "输入清单没有声明样本参与语义目录设计的状态，因此本报告不把它表述为独立留出验证。"
        )

    if normal_alerts == 0:
        normal_interpretation = (
            f"当前 {len(normal_records)} 条正常输入没有出现研究语义报警；但其中 "
            f"{normal_indeterminate} 条至少有一项关系不可判定，因此这不是总体误报率或全关系正常通过证明。"
        )
    else:
        normal_interpretation = (
            f"当前正常输入出现 {normal_alerts} 条研究语义报警，说明至少一条关系存在反例；"
            "在定位并复核这些样本前，不能宣称该语义层满足正常数据不报警。"
        )

    lines = [
        f"# 官方知识语义关联规则验证报告：{run_id}",
        "",
        "## 结论",
        "",
        (
            f"本次从 20 张官方知识卡中整理出 {len(catalog['relations'])} 条带来源、容错和反例的语义关系。"
            f"其中 {len(compiled)} 条不依赖经验阈值，已作为 `official_derived_semantic_rule` 独立执行；"
            f"其余 {len(pending)} 条因需要真机容差、设备族、时间序列、部署策略或未来服务端字段而未执行。"
        ),
        "",
        f"- {normal_interpretation}",
        (
            f"- {len(eligible)} 个合格两态攻击对中，baseline 研究语义报警 {baseline_alerts} 个，"
            f"attack_active 报警 {active_alerts} 个，`baseline 无报警 -> attack_active 报警` {len(transitions)} 个。"
        ),
        f"- {len(transitions)} 个报警转换中有 {directly_supported_transitions} 个能直接回连到 baseline/attack_active payload 中实际变化的关系前提字段。",
        f"- {design_interpretation}",
        "- 这些报警表示项目审阅的官方派生关系被违反，不是 Google/Android 官方风险结论，也不是攻击、欺诈或概率评分。",
        "",
        "## 知识边界与执行方法",
        "",
        "| 层次 | 来源与作用 | 本次是否执行 |",
        "|---|---|---|",
        "| `official_direct` | 官方文档直接给出的安全/完整性 verdict；当前主要是尚未采集的 Play Integrity/Key Attestation 服务端证据 | 否 |",
        "| `official_derived_semantic_rule` | 官方文档定义字段语义，本项目显式推导跨层兼容、一致或上下文关系 | 仅执行 9 条 `compiled_v1` |",
        "| `device_mined_rule` | 真机数据、攻击模板或既有实验形成的经验 predicate | 本报告不读取、不执行 |",
        "",
        "语义执行器只读取 payload 与冻结语义目录。攻击工具名、攻击标签和 mutation 标注在两个阶段分别完成判定后才连接进报告，用于验证分组和直接 feature 变化核对，不能反向触发关系。历史 `clean_post` 不进入判定或比较。",
        "",
        "## 正常输入",
        "",
        "| 输入数 | 研究语义报警 | 至少一项不可判定 | 决策状态计数 |",
        "|---:|---:|---:|---|",
        f"| {len(normal_records)} | {normal_alerts} | {normal_indeterminate} | `{json.dumps(decision_counts(normal_records), ensure_ascii=False, sort_keys=True)}` |",
        "",
        "## 攻击工具两态验证",
        "",
        "| 攻击对总数 | 合格两态对 | baseline 报警 | attack_active 报警 | 无报警转报警 | 忽略 clean_post |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {len(pairs)} | {len(eligible)} | {baseline_alerts} | {active_alerts} | {len(transitions)} | {sum(pair['ignored_historical_post_count'] for pair in pairs)} |",
        "",
        "### 输入 cohort 结果",
        "",
        "| cohort | 设计暴露状态 | 合格对 | baseline 报警 | attack_active 报警 | 无报警转报警 | 新增矛盾关系 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for key, cohort_pairs in per_cohort.items():
        cohort_baseline_alerts = sum(
            bool(pair["baseline"]["research_semantic_alert"])
            for pair in cohort_pairs
            if pair["baseline"]
        )
        cohort_active_alerts = sum(
            bool(pair["attack_active"]["research_semantic_alert"])
            for pair in cohort_pairs
            if pair["attack_active"]
        )
        cohort_transitions = sum(
            pair["research_semantic_alert_transition"]
            == "baseline_no_alert_to_attack_active_alert"
            for pair in cohort_pairs
        )
        cohort_relations = sorted(
            {
                relation_id
                for pair in cohort_pairs
                for relation_id in pair["new_inconsistency_relation_ids"]
            }
        )
        lines.append(
            f"| {key[1]} (`{key[0]}`) | `{key[2]}` | {len(cohort_pairs)} | "
            f"{cohort_baseline_alerts} | {cohort_active_alerts} | {cohort_transitions} | "
            f"{', '.join(cohort_relations) or '-'} |"
        )

    excluded_inputs = attack_input_selection.get("excluded_manifests", [])
    if excluded_inputs:
        lines.extend(
            [
                "",
                "### 明确排除的新 manifest",
                "",
                "以下输入没有进入任何分母或规则执行：",
                "",
            ]
        )
        for item in excluded_inputs:
            lines.append(f"- `{item['path']}`：`{item['reason']}`")

    lines.extend(
        [
            "",
            "### 工具/精确配置结果",
            "",
        "| 工具 | 版本 | 配置 | 合格对 | attack_active 报警 | 无报警转报警 | 新增矛盾关系 |",
        "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for key, tool_pairs in sorted(per_tool.items()):
        tool_active_alerts = sum(
            bool(pair["attack_active"]["research_semantic_alert"])
            for pair in tool_pairs
            if pair["attack_active"]
        )
        tool_transitions = sum(
            pair["research_semantic_alert_transition"]
            == "baseline_no_alert_to_attack_active_alert"
            for pair in tool_pairs
        )
        relation_ids = sorted(
            {
                relation_id
                for pair in tool_pairs
                for relation_id in pair["new_inconsistency_relation_ids"]
            }
        )
        lines.append(
            f"| {key[0]} | {key[1]} | {key[2]} | {len(tool_pairs)} | "
            f"{tool_active_alerts} | {tool_transitions} | {', '.join(relation_ids) or '-'} |"
        )

    if no_alert_pairs:
        no_alert_by_config: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(
            list
        )
        for pair in no_alert_pairs:
            no_alert_by_config[
                (
                    str(pair["tool"].get("tool_name") or "unknown"),
                    str(pair["tool"].get("config_id") or "unknown"),
                )
            ].append(pair)
        lines.extend(
            [
                "",
                "### 已确认字段变化但未报警的覆盖缺口",
                "",
                (
                    f"共 {len(no_alert_pairs)} 个合格对已由 manifest 标注且被 payload 直接对比确认字段变化，"
                    "但冻结的 9 条 `compiled_v1` 关系未产生强矛盾报警。这是当前语义层的覆盖缺口，"
                    "不是工具执行失败，也不能被写成这些配置安全。"
                ),
                "",
                "| 工具 | 配置 | 未报警合格对 | 清单标注且直接对比确认的字段 |",
                "|---|---|---:|---|",
            ]
        )
        for key, config_pairs in sorted(no_alert_by_config.items()):
            confirmed_fields = sorted(
                {
                    item["field_path"]
                    for pair in config_pairs
                    for item in pair["feature_comparison"]["annotated_field_results"]
                    if item["annotation_status"]
                    == "confirmed_by_direct_payload_comparison"
                }
            )
            lines.append(
                f"| {key[0]} | {key[1]} | {len(config_pairs)} | "
                f"{', '.join(f'`{field}`' for field in confirmed_fields) or '-'} |"
            )

    lines.extend(
        [
            "",
            "## 已执行关系逐项结果",
            "",
            "| 关系 | 强度 | 正常 inconsistent | baseline inconsistent | attack_active inconsistent | baseline -> active 新增 inconsistent |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in compiled:
        lines.append(
            f"| {row['relation_id']} {row['relation_name']} | {row['severity']} | "
            f"{count_outcome(row['normal_outcome_counts'], 'inconsistent')} | "
            f"{count_outcome(row['attack_baseline_outcome_counts'], 'inconsistent')} | "
            f"{count_outcome(row['attack_active_outcome_counts'], 'inconsistent')} | "
            f"{row['baseline_to_active_new_inconsistency_count']} |"
        )

    lines.extend(
        [
            "",
            "## 暂不执行的候选关系",
            "",
            "这些关系不是被删除，而是因当前证据不足而保持候选状态，避免用人为阈值制造报警：",
            "",
        ]
    )
    for status, relation_ids in sorted(pending_statuses.items()):
        lines.append(f"- `{status}`：{', '.join(sorted(relation_ids))}")
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            "本次只验证冻结样本上的确定性语义关系，不重挖经验规则、不调阈值、不训练模型，也不使用攻击撤销阶段。当前结果不能外推为总体误报率、攻击召回率、跨设备/跨版本稳定性或生产风控能力；需要继续用独立真机数据验证关系反例，并为候选数值关系建立分组容差后，才可升级执行状态。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_official_semantic_validation(
    *,
    run_id: str,
    normal_input: Path,
    attack_manifests: list[Path] | None = None,
    attack_input_set: Path | None = None,
    output_dir: Path,
) -> dict[str, Any]:
    normal_input = normal_input.resolve()
    output_dir = output_dir.resolve()
    if not normal_input.is_file():
        raise FileNotFoundError(f"Normal input does not exist: {normal_input}")
    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists and will not be overwritten: {output_dir}"
        )
    if not run_id.strip():
        raise ValueError("run_id must be non-empty")

    attack_selection: AttackInputSelection = resolve_attack_inputs(
        explicit_manifests=attack_manifests,
        input_set_path=attack_input_set,
    )

    catalog = load_semantic_catalog()
    official_source, official_cards = load_official_cards()
    normal_records, pairs = evaluate_inputs(
        run_id=run_id,
        normal_input=normal_input,
        attack_manifests=attack_selection.manifests,
        attack_metadata_by_manifest=attack_selection.metadata_by_manifest,
        catalog=catalog,
    )
    observed_input_counts = attach_and_validate_observed_counts(
        attack_selection, pairs
    )
    relation_summary = build_relation_summary(catalog, normal_records, pairs)

    output_dir.mkdir(parents=True, exist_ok=False)

    write_jsonl(output_dir / NORMAL_RESULTS_FILENAME, normal_records)
    write_jsonl(output_dir / ATTACK_RESULTS_FILENAME, pairs)
    write_csv(
        output_dir / RELATION_SUMMARY_FILENAME,
        [
            "relation_id",
            "relation_name",
            "relation_type",
            "inference_level",
            "executable_status",
            "predicate_id",
            "severity",
            "risk_use_status",
            "premise_fields",
            "official_card_refs",
            "official_source_refs",
            "tolerance",
            "counterexamples",
            "validation_status",
            "normal_outcome_counts",
            "attack_baseline_outcome_counts",
            "attack_active_outcome_counts",
            "baseline_to_active_new_inconsistency_count",
        ],
        relation_summary,
    )
    write_json(output_dir / CATALOG_SNAPSHOT_FILENAME, catalog)
    write_report(
        output_dir / REPORT_FILENAME,
        run_id=run_id,
        catalog=catalog,
        normal_records=normal_records,
        pairs=pairs,
        relation_summary=relation_summary,
        attack_input_selection=attack_selection.provenance,
    )

    compiled_count = sum(
        relation["executable_status"] == "compiled_v1" for relation in catalog["relations"]
    )
    eligible = [pair for pair in pairs if pair["eligible_for_two_state_validation"]]
    manifest = {
        "semantic_validation_version": SEMANTIC_VALIDATION_VERSION,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "protocol": {
            "version": TWO_STATE_PROTOCOL_VERSION,
            "states_compared": ["baseline", "attack_active"],
            "historical_clean_post": "ignored_not_used_for_current_validation",
        },
        "inputs": {
            "normal_path": repo_relative(normal_input),
            "normal_record_count": len(normal_records),
            "attack_manifest_paths": [
                repo_relative(path) for path in attack_selection.manifests
            ],
            "attack_pair_count": len(pairs),
            "eligible_attack_pair_count": len(eligible),
            "ignored_historical_post_count": sum(
                pair["ignored_historical_post_count"] for pair in pairs
            ),
            "attack_input_selection": attack_selection.provenance,
        },
        "official_derived_semantic_lane": {
            "knowledge_source_type": catalog["knowledge_source_type"],
            "official_cards_path": repo_relative(DEFAULT_OFFICIAL_CARDS),
            "official_cards_sha256": sha256_file(DEFAULT_OFFICIAL_CARDS),
            "official_cards_version": official_source.get("version"),
            "official_card_count": len(official_cards),
            "semantic_catalog_path": repo_relative(DEFAULT_SEMANTIC_CATALOG),
            "semantic_catalog_sha256": sha256_file(DEFAULT_SEMANTIC_CATALOG),
            "semantic_catalog_version": catalog["catalog_version"],
            "semantic_relation_count": len(catalog["relations"]),
            "compiled_relation_count": compiled_count,
            "not_executed_relation_count": len(catalog["relations"]) - compiled_count,
            "decision_inputs": ["collected_payload", "reviewed_official_semantic_catalog"],
            "forbidden_decision_inputs": [
                "attack_tool_name",
                "attack_label",
                "attack_manifest_mutation_annotation",
                "device_mined_rule_registry",
                "calibrated_score",
            ],
            "validation_design": {
                "role": (
                    "mixed_design_seen_and_post_freeze_configuration_evaluation"
                    if observed_input_counts["legacy_pair_count"]
                    and observed_input_counts["new_pair_count"]
                    else "retrospective_same_corpus_execution_check"
                ),
                "independent_held_out_attack_validation": False,
                "reason": (
                    "The legacy cohort informed the semantic catalog. Newly pulled cohorts "
                    "were not inspected before catalog freeze, but this evaluation was not "
                    "preregistered and remains within the same controlled emulator and "
                    "collection infrastructure."
                ),
                "legacy_design_seen_pair_count": observed_input_counts[
                    "legacy_pair_count"
                ],
                "post_freeze_configuration_pair_count": observed_input_counts[
                    "new_pair_count"
                ],
            },
        },
        "observed_results": {
            "normal_research_semantic_alert_count": sum(
                record["decision"]["research_semantic_alert"] for record in normal_records
            ),
            "attack_baseline_research_semantic_alert_count": sum(
                bool(pair["baseline"]["research_semantic_alert"])
                for pair in eligible
                if pair["baseline"]
            ),
            "attack_active_research_semantic_alert_count": sum(
                bool(pair["attack_active"]["research_semantic_alert"])
                for pair in eligible
                if pair["attack_active"]
            ),
            "baseline_no_alert_to_attack_active_alert_count": sum(
                pair["research_semantic_alert_transition"]
                == "baseline_no_alert_to_attack_active_alert"
                for pair in eligible
            ),
            "alert_transition_with_direct_changed_premise_count": sum(
                pair["research_semantic_alert_transition"]
                == "baseline_no_alert_to_attack_active_alert"
                and pair[
                    "all_new_strong_inconsistencies_have_direct_premise_change"
                ]
                for pair in eligible
            ),
        },
        "outputs": {
            "normal_results": NORMAL_RESULTS_FILENAME,
            "attack_results": ATTACK_RESULTS_FILENAME,
            "relation_summary": RELATION_SUMMARY_FILENAME,
            "catalog_snapshot": CATALOG_SNAPSHOT_FILENAME,
            "report": REPORT_FILENAME,
        },
        "claim_boundary": catalog["boundary"],
    }
    write_json(output_dir / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = run_official_semantic_validation(
        run_id=args.run_id,
        normal_input=args.normal_input,
        attack_manifests=args.attack_manifest,
        attack_input_set=args.attack_input_set,
        output_dir=args.output_dir,
    )
    print(
        "Official semantic validation written: "
        f"{args.output_dir} (normal={manifest['inputs']['normal_record_count']}, "
        f"attack_pairs={manifest['inputs']['attack_pair_count']})"
    )


if __name__ == "__main__":
    main()
