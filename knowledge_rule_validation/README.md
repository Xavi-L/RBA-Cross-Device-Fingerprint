# 两类知识规则的一次分类运行

本目录只保存一次、可复核的分类运行包。它不重挖规则、不改阈值、不训练模型。

当前知识边界如下：

- `official_document`：`google_official_kb/feature_risk_cards.json` 中的官方卡片；当前只提供字段语义、适用范围和容错依据，不是独立可执行的报警 predicate。
- `device_mined_rule`：`scoring/rule_knowledge_base.json` 中已有的项目/真机数据经验规则；只有已写入 `hybridguard_agent/config/deterministic_rule_predicates.v1.json` 的 predicate 会实际执行。

来源分类仍然只有上述两类。若基于官方字段定义进一步推导跨层兼容或一致性逻辑，执行产物必须标为 `official_derived_semantic_rule`：它保留官方卡片和文档来源，但 predicate 是项目推导，不能写成官方直接结论，也不能混入 `device_mined_rule` 的经验阈值。

攻击验证仅比较 `baseline -> attack_active`。历史 `clean_post` 仅被计数为已忽略的历史记录，不参与结果，也不再要求恢复一致。

运行入口：

```bash
python3 hybridguard_agent/scripts/run_two_source_rule_classification.py \
  --run-id existing_k0_two_source_YYYYMMDD \
  --normal-input backend_server/expanded_collected_data.jsonl \
  --attack-manifest hybridguard-browser-fingerprint-research/execution_log/evidence/20260812_cdp_api30_formal_v4/attack_sample_manifest_v1.jsonl \
  --attack-manifest hybridguard-browser-fingerprint-research/execution_log/evidence/20260812_cdp_api35_formal_v1/attack_sample_manifest_v1.jsonl \
  --attack-manifest hybridguard-browser-fingerprint-research/execution_log/evidence/20260812_cdp_api36_formal_v1/attack_sample_manifest_v1.jsonl \
  --attack-manifest hybridguard-browser-fingerprint-research/execution_log/evidence/20260812_stealth_api35_formal_v1/attack_sample_manifest_v1.jsonl \
  --attack-manifest hybridguard-browser-fingerprint-research/execution_log/evidence/20260812_stealth_api36_formal_v2/attack_sample_manifest_v1.jsonl \
  --output-dir knowledge_rule_validation/runs/existing_k0_two_source_YYYYMMDD
```

每个运行目录必须是新的，脚本拒绝覆盖。主要交付物：

- `ADVISOR_SUMMARY.md`：导师查看的结论、分母和边界。
- `rule_source_catalog.csv`、`official_knowledge_summary.csv`：两类知识的来源与可执行状态。
- `classification_records.jsonl`、`sample_rule_results.jsonl`：逐样本的确定性运行结果。
- `attack_pair_results.jsonl`：逐攻击对的 baseline/attack_active 结果，包含清单标注与原始 payload 直接 feature 对比的核对。
- `feature_delta_summary.csv`：按精确工具、版本、配置和字段聚合的直接变化分子/分母。未被攻击清单标注的变化保留为背景变化，不能归因给攻击。

运行结果只支持当前冻结输入上的确定性执行与受控两态比较；不输出误报率、攻击召回率、校准风险概率或跨工具泛化结论。

## 源隔离复核

既有 `runs/` 包保留两类知识的统一目录。若要让两类知识分别接受同一份正常输入和攻击两态输入的验证，使用独立入口：

```bash
python3 hybridguard_agent/scripts/run_source_isolated_validation.py \
  --run-id existing_k0_source_isolated_expanded_YYYYMMDD \
  --normal-input backend_server/expanded_collected_data.jsonl \
  --attack-input-set knowledge_rule_validation/config/official_semantic_attack_input_set.expanded_20260901.json \
  --output-dir knowledge_rule_validation/source_isolated_runs/existing_k0_source_isolated_expanded_YYYYMMDD
```

该运行会生成 `两类知识独立验证报告.md`。官方文档轨只允许读取官方卡片，因当前卡片没有独立触发 predicate，所以输出“可覆盖/不可独立判定”而不是虚构报警；数据挖掘规则轨只执行冻结的项目 predicate，不检索官方卡片，也不读取攻击工具标签。

## 官方知识语义关联层

`hybridguard_agent/config/official_semantic_relations.v1.json` 把官方卡片中的隐含关系显式化，并为每条关系记录 premise fields、官方卡片/文档来源、推理层级、容错、反例、执行状态和验证状态。当前目录共 22 条关系：只执行 9 条不需要经验阈值的 `compiled_v1`，其余涉及数值容差、设备族、时间序列、部署策略或未来服务端证据的关系继续保持候选状态。

独立验证入口：

```bash
python3 hybridguard_agent/scripts/run_official_semantic_validation.py \
  --run-id official_semantic_v1_expanded_YYYYMMDD \
  --normal-input backend_server/expanded_collected_data.jsonl \
  --attack-input-set knowledge_rule_validation/config/official_semantic_attack_input_set.expanded_20260901.json \
  --output-dir knowledge_rule_validation/official_semantic_runs/official_semantic_v1_expanded_YYYYMMDD
```

该入口只把 payload 和冻结语义目录交给执行器；攻击标签、工具名和 mutation 标注在 baseline/attack_active 分别判定后才用于分组及直接 feature 变化核对。主要产物包括：

- `官方知识语义关联规则验证报告.md`：导师可读的结果、反例和结论边界。
- `semantic_relation_summary.csv`：22 条关系的执行状态及正常/baseline/attack_active 结果。
- `normal_semantic_results.jsonl`、`attack_semantic_pair_results.jsonl`：逐样本与逐攻击对结果；不复制原始指纹值。
- `semantic_relation_catalog_snapshot.json`、`official_semantic_validation_manifest.json`：本次目录快照、输入协议、来源哈希和验证设计声明。

扩展输入清单会在运行前校验攻击侧仓库 revision、manifest 去重和文件存在性，并在解析后复核预期的 23 个 manifest、69 个合格对、69 条已忽略 `clean_post`、4 个工具名和 14 个精确配置。两个不完整/空 manifest 及排除原因也固定在清单中，不进入任何分母。

当前扩展运行为：

- [官方派生语义关系报告](official_semantic_runs/official_semantic_v1_expanded_20260901_r2/官方知识语义关联规则验证报告.md)：229 条正常输入强报警 0；69 个合格攻击对中 51 个无报警转报警。
- [官方直接卡片/数据挖掘规则源隔离报告](source_isolated_runs/existing_k0_source_isolated_expanded_20260901/两类知识独立验证报告.md)：数据挖掘轨在同一 69 对上有 33 个无报警转报警；229 条正常输入虽然显式报警为 0，但全部为 `insufficient_evidence`。
- [两类知识同分母对照报告](新增攻击配置两类知识独立验证对照报告_20260901.md)：33 对两轨都报，18 对仅官方派生轨报，18 对两轨都不报。

历史 `official_semantic_v1_20260901_r2` 继续保留。它使用的 15 个攻击对曾参与关系设计观察，尤其 `OFFDER-GPU-001` 受 stealth 的 Direct3D 变化启发；其 15/15 只能解释为同语料上的回顾性执行覆盖。扩展运行中的 54 个新对在目录冻结前未被查看，但因未预注册且仍来自同一受控模拟器/采集体系，也不能写成独立真机留出验证。
