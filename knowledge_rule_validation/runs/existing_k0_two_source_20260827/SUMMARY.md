# 两类知识规则分类与两态攻击验证：existing_k0_two_source_20260827

## 运行边界

- 当前比较只使用 `baseline -> attack_active`；历史 `clean_post` 未参与分类或成功判定。
- 本次没有重挖规则、调整阈值、训练模型或输出校准风险概率。
- `manual_review_required` 与 `inconsistency_observed` 计为显式报警；`insufficient_evidence` 既不是正常通过，也不是报警。

## 知识来源状态

| 来源 | 知识项 | 本次可独立执行的报警 predicate | 本次解释方式 |
|---|---:|---:|---|
| 官方文档知识 | 20 张官方卡 | 0 | 语义、容错与字段依据；不能被误报为独立官方报警规则。 |
| 真机数据/项目经验规则 | 35 条旧规则 | 10 | 仅已审阅的确定性 predicate 执行；其余规则保持 retrieval-only。 |

现有规则库中的官方卡片用于支撑字段语义和容错，而触发条件仍是项目内规则。故本次不能把“有官方引用的规则”伪装成纯官方规则，并把它们与经验规则做独立报警率比较。

## 正常数据分类结果

| 输入记录 | 显式报警 | 完成且未命中规则 | 仅上下文观察 | 证据不足 |
|---:|---:|---:|---:|---:|
| 229 | 0 | 0 | 0 | 229 |

完整决策状态计数：`{"insufficient_evidence": 229}`。

## 攻击工具两态验证

| 攻击对总数 | 可纳入两态验证 | baseline 显式报警 | attack_active 显式报警 | baseline 无报警转 active 报警 |
|---:|---:|---:|---:|---:|
| 15 | 15 | 0 | 9 | 9 |

攻击对只在工具执行已核验、字段效果已观察到且 baseline/active 都存在时计入两态验证分母。未满足这些条件的记录保留在 `attack_pair_results.jsonl`，但不计为成功或失败。

## 已观察到的攻击字段变化

- 覆盖 73 个 `工具 × 版本 × 配置 × field_path` 条目；其中 66 个字段在各自可用的同配置攻击对中均由 baseline/active 原始 payload 直接比较为变化，但仅 25 个同时满足攻击清单标注与直接比较确认。
- 攻击清单标注与直接比较不一致/不可比的字段对共 0 个；另有 135 个未由攻击清单标注的直接变化字段对，不能据此归因给攻击。
- 详见 `feature_delta_summary.csv`；该文件保存字段路径、直接变化分子/分母、标注核对结果与变化摘要，不重复复制完整原始 payload。

## 产物索引

- `run_manifest.json`：输入、规则版本、协议与计数。
- `rule_source_catalog.csv`：每条旧规则的主来源、官方补充依据与编译状态。
- `classification_records.jsonl`：逐样本/逐攻击阶段的确定性运行结果与 DecisionTrace。
- `sample_rule_results.jsonl`：逐样本 × 已编译规则的命中/未评估结果。
- `attack_pair_results.jsonl`：逐攻击对的 baseline/attack_active 比较。
- `rule_summary.csv`、`official_knowledge_summary.csv`、`feature_delta_summary.csv`：导师可筛选的汇总表。

## 结论边界

本包证明的是当前冻结规则在这些输入上的可复核执行与受控两态比较。它不是攻击召回率、误报率、欺诈概率或跨工具泛化性能结论。
