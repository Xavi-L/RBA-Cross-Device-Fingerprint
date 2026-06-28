# Google Official Knowledge Base Collection

本目录用于收集 Google 官方技术文档中可用于 HybridGuard feature 风险鉴定的内容。当前已完成“来源收集 + 风险知识抽取 + 主规则知识库合入”，主知识库 `scoring/rule_knowledge_base.json` 已通过 `official_knowledge` 字段引用本目录中的卡片和来源。

## 文件说明

| 文件 | 作用 |
|---|---|
| `official_sources.jsonl` | Google 官方文档来源清单，包含 URL、关联字段、候选规则和抽取状态。 |
| `feature_risk_cards.json` | 从官方文档抽取出的 feature 风险知识卡片，按项目字段和规则组映射。 |
| `collection_report.md` | 给导师看的收集汇总，说明已覆盖哪些官方文档、能支撑哪些风险判断。 |
| `integration_plan.md` | 后续如何把本目录内容合入现有规则知识库和 LLM 分组融合流程。 |
| `integration_report.md` | 已合入/未合入卡片清单，以及每张卡片的选择或未选择理由。 |

## 使用边界

1. 本目录不复制官方文档全文，只保存短摘要、URL 和项目内可用的风险鉴定含义。
2. 官方文档多数只定义 API 字段语义，并不直接给出风控阈值；因此卡片中区分 `direct`、`derived`、`empirical` 三类推理强度。
3. 已合入主规则库的卡片只补充官方依据，不改变现有风险阈值、短路规则或评分区间。

## 与当前项目的关系

现有评分流程主要读取：

- `scoring/rule_knowledge_base.json`
- `scoring/rule_knowledge_base.md`
- `zhipu_glm_eval/score_with_glm.py`
- `scoring/sorting_rule_kb.py`

本目录已为主规则库补充：

- `source_refs`
- `official_basis`
- `inference_level`
- `evidence_strength`
- `tolerance_basis`

## 当前收集规模

- 官方来源：30 条
- 风险知识卡片：20 张
- 已选择并合入当前规则：15 张
- 暂不选择、仅作为 future feature 保留：5 张
- 当前只保留与已采集字段、现有规则或明确 future feature 强相关的来源；泛泛安全 checklist、普通发布说明和难以映射到本项目字段的资料暂不纳入。
