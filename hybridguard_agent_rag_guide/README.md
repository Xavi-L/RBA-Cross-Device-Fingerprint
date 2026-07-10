# HybridGuard Agent/RAG 工作索引

> 本文件是 Agent 处理 HybridGuard Agent/RAG 任务时的唯一默认入口。
>
> 本文件只负责全局约束、任务路由、当前阶段和权威来源，不承载详细方法。
>
> 禁止为了“先了解完整背景”一次性读取全部分册。

<a id="INDEX-GLOBAL-RULES"></a>

## 1. 五条全局不变量

1. **先划分数据，再生成经验规则和案例索引。** 最终测试数据不得参与规则发现、案例构建、Prompt、检索或阈值调优。
2. **session 数不等于 stable profile 数。** 所有规模报告必须同时给出会话数和稳定画像数。
3. **官方知识解释字段语义，不提供风险概率和项目阈值。**
4. **LLM 只能提出候选或做语义判断，不能直接修改正式知识库。**
5. **没有独立攻击真值时，不宣称真实攻击检测准确率。**

<a id="INDEX-READING-PROTOCOL"></a>

## 2. Agent 阅读协议

### 2.1 阅读预算

- README 不计入分册数量。
- 普通任务：README + 1 册。
- 跨域任务：README + 最多 2 册。
- 首轮每册最多读取 1–3 个锚点小节，不默认通读整册。
- 第二册必须满足第 5 节“两册组合白名单”。
- 看起来需要 3 册以上时，必须拆成多个子任务。
- 子 Agent 每个仍只读 1–2 册；主 Agent接收摘要，不重新通读所有分册。
- 系统级文档迁移或全局审计是唯一例外，但仍应先用锚点定位。

### 2.2 执行顺序

1. 识别 task_type 和预期交付物。
2. 查询第 4 节任务路由表。
3. 打开主分册，只搜索路由表给出的 Anchor。
4. 读取命中小节及其直接上下文。
5. 只有白名单触发条件成立时，读取第二册。
6. 开始工作前记录 Context Receipt。
7. 明确列出本次没有读取的分册，避免隐式扩张上下文。

推荐定位方式：

~~~bash
rg -n "DATA-STABLE-KEY" hybridguard_agent_rag_guide/03_DATA_SCHEMA_GROUPING_AND_QC.md
rg -n "RAG-RETRIEVAL" hybridguard_agent_rag_guide/05_KNOWLEDGE_RULES_AND_RETRIEVAL.md
rg -n "EVAL-OOD" hybridguard_agent_rag_guide/07_EXPERIMENTS_LEAKAGE_METRICS_AND_OOD.md
~~~

### 2.3 禁止行为

- 禁止顺序打开 01–09 全部分册。
- 禁止把根目录跳转页当作完整方法文档。
- 禁止因为某册提到另一册就自动读取依赖；只有当前任务真正涉及接口时才读。
- 禁止在多个分册复制同一事实或协议的完整正文。
- 禁止用旧 LLM 教师标签替代新攻击事实真值。

<a id="INDEX-CURRENT-SNAPSHOT"></a>

## 3. 当前最小快照

- current_phase：P0 数据与 Schema 接管。
- 当前 JSONL：155 个 session。
- expanded-v2：154 条；expanded-v1：1 条，正式 V2 流水线应隔离。
- 当前保守稳定画像：约 80 组，不等于 80 台已验证物理设备。
- 当前独立攻击标签和来源 manifest：不存在。
- 当前规则库：35 条规则。
- 当前官方知识：30 条来源元数据、20 张风险卡。
- 当前下一交付物：expanded_v2.schema.json、field_registry.json、历史 SampleManifest 和数据审计产物。

动态数字的唯一权威来源是 03_DATA_SCHEMA_GROUPING_AND_QC.md；本节只保留路由所需摘要。

<a id="INDEX-BOOKS"></a>

## 4. 分册与任务路由

| Doc ID | 分册 | 权威范围 | 常见任务 | 首读 Anchor |
|---|---|---|---|---|
| HGRAG-01 | [研究总览与结论边界](01_OVERVIEW_AND_RESEARCH_BOUNDARIES.md) | 项目定位、威胁模型、能否宣称、H1–H6 | 研究方向、任务定义、结论边界 | RESEARCH-TASK / RESEARCH-CLAIMS |
| HGRAG-02 | [目标架构与核心契约](02_TARGET_ARCHITECTURE_AND_CONTRACTS.md) | 模块职责、目录、四个中间表示 | 新模块、接口、EvidenceBundle/KnowledgeCard/Trace 契约 | ARCH-PIPELINE / CONTRACT-* |
| HGRAG-03 | [数据、Schema、分组与 QC](03_DATA_SCHEMA_GROUPING_AND_QC.md) | 当前数字、177 字段、canonical path、stable key、QC | 数据审计、Schema、Normalizer、stable key | DATA-BASELINE / DATA-SCHEMA / DATA-STABLE-KEY |
| HGRAG-04 | [攻击采集与来源追踪](04_ATTACK_COLLECTION_AND_PROVENANCE.md) | 配对采集、Attack Manifest、事实标签和门槛 | 接入攻击工具、采集批次、样本审核 | ATTACK-PAIRING / ATTACK-PROTOCOL |
| HGRAG-05 | [知识、规则与检索](05_KNOWLEDGE_RULES_AND_RETRIEVAL.md) | 知识分层、规则晋级、Exact/BM25/Dense/Hybrid/Oracle | 规则卡、官方知识、CandidateRule、Retriever | KNOW-PROMOTION / RAG-RETRIEVAL |
| HGRAG-06 | [推理、Verifier 与融合](06_REASONING_VERIFICATION_AND_FUSION.md) | LLM 输入、六组评分、Verifier、Positive ElasticNet | grouped scorer、验证器、融合、隐私最小化 | RUNTIME-LLM-INPUT / RUNTIME-VERIFIER / RUNTIME-FUSION |
| HGRAG-07 | [实验、防泄漏、指标与 OOD](07_EXPERIMENTS_LEAKAGE_METRICS_AND_OOD.md) | split、baseline、消融、指标、统计、OOD | 实验设计、泄漏审计、结果分析 | EVAL-SPLIT / EVAL-MATRIX / EVAL-OOD |
| HGRAG-08 | [实施路线与验收](08_IMPLEMENTATION_ROADMAP_AND_ACCEPTANCE.md) | P0–P7、10 日清单、完成标准、当前优先级 | 下一步、任务拆分、阶段验收、进度汇报 | EXEC-PHASES / EXEC-PRIORITIES |
| HGRAG-09 | [论文、结论与风险](09_PAPER_WRITING_CLAIMS_AND_RISKS.md) | 论文结构、结论模板、风险登记 | 写论文、导师汇报、局限和伦理 | PAPER-PLAN / PAPER-CLAIMS / PAPER-RISKS |

### 4.1 按 task_type 路由

| task_type | 交付物示例 | 主分册与 Anchor | 允许的第二册 |
|---|---|---|---|
| direction | 研究路线、目标定义、可宣称范围 | 01：RESEARCH-TASK、RESEARCH-CLAIMS | 09，仅当输出论文措辞 |
| data_audit | 数据统计、重复画像、异常字段报告 | 03：DATA-BASELINE、DATA-QC | 无 |
| schema | expanded-v2 Schema、field registry、Normalizer | 03：DATA-SCHEMA、DATA-STABLE-KEY | 02，仅当修改中间表示契约 |
| architecture | 新目录、模块接口、数据对象 | 02：ARCH-PIPELINE、CONTRACT-* | 03/05/06 中与当前接口直接相连的一册 |
| attack_collection | Attack Manifest、clean/attack/post 流程 | 04：ATTACK-MANIFEST、ATTACK-PROTOCOL | 03 做 QC；或 07 锁定 split，二选一 |
| knowledge | KnowledgeCard、官方卡适配、规则晋级 | 05：KNOW-LAYERS、KNOW-PROMOTION | 02，仅当修改 KnowledgeCard Schema |
| retrieval | Exact/BM25/Hybrid/Reranker/ContextPack | 05：RAG-BASELINES、RAG-RETRIEVAL | 07，仅当做检索实验 |
| runtime | grouped scorer、Verifier、Fusion | 06：RUNTIME-* | 02 修改契约，或 05 接 Retriever，二选一 |
| experiment | baseline、消融、指标、OOD | 07：EVAL-MATRIX、EVAL-METRICS、EVAL-OOD | 被评估模块对应的一册 |
| roadmap | 当前下一步、P 阶段、验收 | 08：EXEC-PHASES、EXEC-PRIORITIES | 当前阶段对应技术分册 |
| paper | 论文方法、结果、结论或风险 | 09：PAPER-* | 01 写研究边界；或 07 写实验结果，二选一 |

<a id="INDEX-TWO-BOOK-WHITELIST"></a>

## 5. 两册组合白名单

只有以下跨域任务默认允许读取两册：

| 跨域任务 | 第一册 | 第二册 | 第二册触发条件 |
|---|---|---|---|
| Schema 接入 EvidenceBundle | 03 | 02 | 要修改 EvidenceBundle 或 SampleManifest 契约 |
| EvidenceBundle 接入运行时 | 02 | 06 | 要实现 grouped scorer 或外部模型输入 |
| 攻击采集与 QC | 04 | 03 | 要执行 stable key、Schema 或 QC 门禁 |
| 攻击采集与锁定 split | 04 | 07 | 要生成正式 split manifest |
| KnowledgeCard/规则适配 | 05 | 02 | 要改变卡片字段或 predicate Schema |
| Retriever 接入运行时 | 05 | 06 | 要把 ContextPack 交给 Reasoner/Verifier |
| RAG 或 Verifier 消融 | 05 或 06 | 07 | 要运行对照、Oracle 或统计评估 |
| 实验结果写论文 | 07 | 09 | 要形成论文结果和结论措辞 |
| 论文问题定义 | 01 | 09 | 要写 Introduction、Threat Model 或 Claims |
| 阶段实施 | 08 | 对应技术分册 | 当前 P 阶段进入实际编码 |

需要第三册时，必须拆分。例如“实现 EvidenceBundle + Retriever + 完整消融”应拆成：

1. 02 + 03：EvidenceBundle 与 Schema；
2. 05 + 06：Retriever 与运行时；
3. 07：实验评估。

<a id="INDEX-AUTHORITY"></a>

## 6. 唯一权威来源

| 事实或决策 | 唯一权威分册 |
|---|---|
| 当前数据数字、字段类型、Schema、stable key、QC | 03 |
| clean/attack/post、Attack Manifest、采集门槛 | 04 |
| 模块边界与四个中间表示契约 | 02 |
| 知识分层、规则晋级、检索方法 | 05 |
| LLM 输入、六组评分、Verifier、Fusion | 06 |
| split、防泄漏、baseline、消融、指标、OOD | 07 |
| P0–P7、近期清单、完成状态 | 08 |
| 论文结构、结论模板、风险治理 | 09 |
| 项目定位、研究任务、能否宣称 | 01 |

其他分册只能链接或简要引用，不得维护第二套完整协议。

<a id="INDEX-CURRENT-PHASE"></a>

## 7. 当前阶段卡

~~~yaml
current_phase: P0
active_gate: 建立 expanded-v2 权威 Schema、canonical field registry 和历史 Manifest
dataset_snapshot:
  sessions: 155
  expanded_v2: 154
  expanded_v1_to_isolate: 1
frozen_schema: null
frozen_kb: scoring/rule_knowledge_base.json 当前版本
next_deliverable:
  - expanded_v2.schema.json
  - field_registry.json
  - sample_manifest.jsonl
  - schema_audit.json
blockers:
  - 历史样本缺少独立来源与攻击真值
last_updated: 2026-07-10
~~~

阶段状态变化只更新本节和 08 分册；不要在其他分册复制状态。

<a id="INDEX-CONTEXT-RECEIPT"></a>

## 8. Context Receipt

Agent 在开始较大任务前应记录：

~~~text
task_type:
deliverable:
primary_book:
primary_anchors:
secondary_book:
secondary_reason:
authoritative_artifacts:
assumptions:
explicitly_not_read:
~~~

示例：

~~~text
task_type: schema
deliverable: expanded_v2.schema.json
primary_book: HGRAG-03
primary_anchors: DATA-SCHEMA, DATA-STABLE-KEY
secondary_book: HGRAG-02
secondary_reason: 需要保证 Schema 与 EvidenceBundle 契约一致
authoritative_artifacts: backend_server/expanded_collected_data.jsonl
assumptions: 第 1 条 V1 隔离
explicitly_not_read: HGRAG-01,04,05,06,07,08,09
~~~

<a id="INDEX-CHANGE-RULES"></a>

## 9. 变更传播规则

1. 一个事实只在其权威分册维护。
2. 修改技术实现时，只更新对应分册和相关锚点。
3. 跨模块接口变化，只更新 02 契约、相关技术册的引用和本 README 路由。
4. 不在多个分册复制完整 JSON Schema、门槛、split 规则或实验矩阵。
5. 新增 task_type 时必须更新第 4 节路由。
6. 分册重命名或锚点变化时必须同步 README。
7. 当前阶段变化时只更新第 7 节和 08 分册。
8. 动态数据数字变化时只更新 03 分册，并在 README 第 3 节保留最小摘要。
9. 任何共享文档只使用仓库相对路径。
