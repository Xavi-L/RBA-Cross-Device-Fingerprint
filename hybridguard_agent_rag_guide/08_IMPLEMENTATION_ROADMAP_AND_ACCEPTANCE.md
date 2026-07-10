# 实施路线、近期清单与完成标准

> authoritative_for: P0–P7 阶段、近期 10 日清单、验收门槛、当前优先级和仓库资产导航
> read_when: 决定下一步、制定任务、检查阶段完成度或做进度汇报
> do_not_read_when: 已有明确技术任务且只需具体实现细节
> default_read_budget: 只读当前 P 阶段和相关 Gate
> allowed_second_books: 进入具体阶段后，只读对应技术分册

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| EXEC-PHASES | P0–P7 实施路线 |
| EXEC-NEXT-10-DAYS | 近期 10 个工作日 |
| EXEC-DONE | 最终完成标准 |
| EXEC-PRIORITIES | 现在做与暂时不做 |
| EXEC-ASSETS | 仓库资产和外部参考 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
<a id="EXEC-PHASES"></a>

## 16. 分阶段实施路线

### P0：数据与 Schema 接管

目标：把当前 155 条数据变成可审计、可复现的 V2 数据底座。

交付物：

- expanded_v2.schema.json；
- field_registry.json；
- 历史 sample_manifest.jsonl；
- schema_audit.json；
- feature_profile.csv；
- stable_group_audit.csv；
- dataset_build_manifest.json；
- V1 隔离视图。

验收：

- 154 条 V2 全部通过；
- 1 条 V1 明确隔离；
- 177 字段均有类型、路径、稳定性、单位和用途分类；
- 23 个新增字段有处理策略；
- 历史数据统一 label=unlabeled；
- 不输出攻击分类指标。

### P1：EvidenceBundle

目标：用确定性代码把 177 字段转成六组证据。

交付物：

- canonical normalizer；
- stable key v1；
- UA、版本、屏幕、GPU、WebView comparator；
- 六组 extractor；
- EvidenceBundle JSONL；
- 单元测试；
- evidence hash。

验收：

- 每条 V2 一一生成 EvidenceBundle；
- 重复运行 hash 一致；
- GPU、UA、版本和屏幕比较有正反测试；
- 不向外部模型发送标签、IP 和原始 session；
- 所有 comparator 有 unknown/tolerance 分支。

### P2：知识卡与规则执行

目标：把现有规则和官方卡统一成可检索、可验证的 KnowledgeCard。

交付物：

- KnowledgeCard Schema；
- rule_kb_adapter；
- official_kb_adapter；
- canonical field alias；
- predicate Schema；
- deterministic matcher；
- selected/rejected 转换报告。

验收：

- 35 条现有规则全部转换；
- published、semantic_only、future-only 状态清晰；
- 核心规则和主要跨层规则可执行；
- 所有引用能解析到 card/source/field；
- 新 23 字段的首批 GPU 卡完成。

### P3：检索与 Verifier MVP

目标：先做强基线，再加入复杂 RAG。

交付物：

- Full-KB baseline；
- Exact field retrieval；
- BM25 retrieval；
- metadata filter；
- ContextPack；
- citation/field/rule/output verifier；
- retrieval evaluation set；
- Oracle retrieval。

验收：

- current/future 硬隔离；
- 核心预期规则 Recall@k 达到 100%；
- 错配和 shuffled retrieval 可运行；
- 记录 top-k、token、延迟和索引版本；
- 输出引用均存在且关联已观测字段。

### P4：在线推理闭环

目标：完成离线批处理和风险分析接口。

交付物：

- grouped scorer adapter；
- fusion adapter；
- DecisionTrace；
- 离线 batch runner；
- 后续可选 /api/risk/analyze。

验收：

- 原始接管流程能够读取 155 条历史数据；其中 154 条 V2 进入正式流水线，1 条 V1 被正确识别并隔离；
- 结构化输出解析率 100%；
- short-circuit 不被融合降级；
- future-only 误引用为 0；
- 外部请求无原始敏感标识；
- 每次决策记录完整版本。

### P5：配对攻击 Pilot

目标：建立独立事实标签和真实可验证攻击样本。

交付物：

- attack manifest；
- clean_pre/attack/clean_post 数据；
- tool logs 与 success evidence；
- pair audit；
- QC report；
- locked split manifest。

验收：

- 至少 3 个攻击家族；
- 每家族至少 5 个 stable key；
- 攻击成功率、配对完整率和回滚率达到第 7.5 节门槛；
- 失败攻击全部隔离；
- test groups 在规则生成前锁定。

### P6：候选规则与 RAG 实验

目标：验证自动候选、检索和 Verifier 是否各自有效。

交付物：

- candidate/validated/published/rejected 报告；
- K0–K4 知识矩阵；
- R0–R8 检索矩阵；
- 端到端 baseline；
- 单因素消融；
- OOD 结果；
- 错误分析；
- run manifests。

验收：

- 每次实验只改变一个变量；
- KB/index/Prompt/model/fusion 全部版本化；
- grouped leakage 为 0；
- 同时报告检测、检索、可信度、效率和置信区间；
- 结论严格匹配证据。

### P7：论文与发布产物

交付物：

- 数据说明和威胁模型；
- 方法章节；
- 实验协议；
- 主结果和消融表；
- OOD 与失败案例；
- 伦理、隐私和局限；
- 可复现运行说明；
- 脱敏 artifact manifest。

验收：

- 独立事实标签成立；
- RAG 相对强基线的价值明确；
- Oracle 分析闭环；
- 至少一个严格 OOD 轨道有可解释结果；
- 所有图表可从冻结产物重新生成。

---

<a id="EXEC-NEXT-10-DAYS"></a>

## 17. 近期执行清单

### 17.1 接下来 10 个工作日

### 第 1–2 天：冻结与 Schema

- [ ] 记录当前 JSONL hash。
- [ ] 隔离第 1 条 V1。
- [ ] 生成 154 条 V2 实验视图。
- [ ] 建立 expanded_v2.schema.json。
- [ ] 建立 field_registry.json。
- [ ] 明确 screen_resolution_physical 和 battery_voltage 语义。

### 第 3–4 天：Manifest 与审计

- [ ] 为 155 条历史数据生成回溯 manifest。
- [ ] 全部标记 label=unlabeled。
- [ ] 生成 stable group audit。
- [ ] 生成 feature profile 和常量/低变/异常报告。
- [ ] 定义未来采集 manifest Schema。

### 第 5–6 天：EvidenceBundle

- [ ] 复用 prepare_validation_assets.py 的稳定身份和六组结构。
- [ ] 实现 canonical normalizer。
- [ ] 实现 UA/版本/GPU/屏幕 comparator。
- [ ] 生成 EvidenceBundle JSONL。
- [ ] 加入 evidence hash 和隐私过滤。

### 第 7–8 天：知识统一与检索基线

- [ ] 将 35 条规则转换为 KnowledgeCard。
- [ ] 将 20 张官方卡适配到 canonical fields。
- [ ] 标记 future-only。
- [ ] 实现 Full-KB、Exact 和 BM25。
- [ ] 建立小规模 gold retrieval set。

### 第 9 天：Verifier

- [ ] 实现字段存在检查。
- [ ] 实现引用存在检查。
- [ ] 实现 predicate/short-circuit 检查。
- [ ] 实现 future-only 检查。
- [ ] 定义 DecisionTrace。

### 第 10 天：MVP Smoke Test

- [ ] 对 154 条 V2 完整跑通。
- [ ] 输出结构化运行报告。
- [ ] 汇总失败样本和字段语义问题。
- [ ] 冻结攻击采集前的第一版接口。

### 17.2 在开始大规模攻击采集前

- [ ] manifest 必填；
- [ ] stable key 从 clean_pre 生成并传播；
- [ ] pair_id 全链路可追踪；
- [ ] tool/version/config 可审计；
- [ ] success evidence 可验证；
- [ ] clean_post 回滚可验证；
- [ ] label/source 正交；
- [ ] QC 自动门禁；
- [ ] split_group_id 规则冻结；
- [ ] test groups 预留策略确定。

---

<a id="EXEC-DONE"></a>

## 20. 最终完成标准

项目进入正式论文结果阶段前，至少满足：

### 数据

- [ ] expanded-v2 Schema 冻结；
- [ ] 当前 V1 已隔离；
- [ ] 所有正式样本有 manifest；
- [ ] clean/attack 配对有独立成功证据；
- [ ] session 数和 stable profile 数同时报告；
- [ ] group leakage 为 0。

#### 知识

- [ ] 官方、确定性、经验和案例知识分层；
- [ ] 每张卡有 provenance、version、status；
- [ ] 经验规则只来自训练组；
- [ ] 核心规则可执行；
- [ ] future-only 在线硬隔离。

### 系统

- [ ] EvidenceBundle 可复现；
- [ ] Full-KB、Exact、BM25、Hybrid 和 Oracle 可运行；
- [ ] LLM 输出结构化；
- [ ] Verifier 可拦截无依据输出；
- [ ] 外部融合可复现；
- [ ] DecisionTrace 完整。

### 实验

- [ ] 强 baseline 齐全；
- [ ] 检索和生成分别评估；
- [ ] 单因素消融；
- [ ] 至少一个严格 OOD 轨道；
- [ ] stable-group 置信区间；
- [ ] 失败和受限结果也按预设条件报告。

### 论文

- [ ] 问题定义不夸大；
- [ ] 不把教师一致率写成攻击准确率；
- [ ] 不把云设备、ADB 或 debuggable 等价为恶意；
- [ ] 不把 session 数等价为独立设备数；
- [ ] 所有结果可从冻结 artifact 重新生成。

---

<a id="EXEC-PRIORITIES"></a>

## 21. 当前优先级结论

### 现在立即做

1. Schema 与 canonical field registry。
2. 回溯 SampleManifest 和数据审计。
3. stable key 与 split 规范。
4. EvidenceBundle。
5. 现有规则/官方卡适配。
6. Full-KB、Exact、BM25 和 Verifier MVP。
7. 攻击采集 manifest 与配对协议。

### 暂时不要做

1. 用当前 154 条 V2 训练攻击分类器。
2. 让 LLM 直接把候选规则写入正式 KB。
3. 在没有强基线前直接部署复杂向量库。
4. 使用随机行切分证明泛化。
5. 把当前数据标成 benign。
6. 预设 RAG 一定提高最终分数。
7. 等所有实验做完再开始写论文。

### 项目下一阶段的正确完成定义

下一阶段完成，不是指“已经证明 RAG 提升了准确率”，而是指：

> 177 字段数据可以稳定转成可审计证据；现有规则和官方知识可以被字段感知检索；LLM 输出可以被验证；所有运行都有完整版本追踪；后续真实攻击数据能够以无泄漏的配对协议进入同一套系统。

做到这一点后，再进入攻击数据扩采、候选规则验证和正式消融，返工风险最低，论文证据链也最完整。

---

<a id="EXEC-ASSETS"></a>

## 22. 参考仓库资产

- [README.md](../README.md)
- [LLM_GROUPED_FUSION_PLAN.md](../LLM_GROUPED_FUSION_PLAN.md)
- [backend_server/expanded_collected_data.jsonl](../backend_server/expanded_collected_data.jsonl)
- [backend_server/expanded_merged_sessions.json](../backend_server/expanded_merged_sessions.json)
- [backend_server/main.py](../backend_server/main.py)
- [scoring/rule_knowledge_base.json](../scoring/rule_knowledge_base.json)
- [google_official_kb/feature_risk_cards.json](../google_official_kb/feature_risk_cards.json)
- [google_official_kb/official_sources.jsonl](../google_official_kb/official_sources.jsonl)
- [google_official_kb/integration_plan.md](../google_official_kb/integration_plan.md)
- [llm_grouped_fusion_validation/EXPERIMENT_DESIGN.md](../llm_grouped_fusion_validation/EXPERIMENT_DESIGN.md)
- [llm_grouped_fusion_validation/PILOT_REPORT.md](../llm_grouped_fusion_validation/PILOT_REPORT.md)
- [llm_grouped_fusion_validation/prepare_validation_assets.py](../llm_grouped_fusion_validation/prepare_validation_assets.py)
- [llm_grouped_fusion_validation/score_group_evidence_with_glm.py](../llm_grouped_fusion_validation/score_group_evidence_with_glm.py)
- [llm_grouped_fusion_validation/evaluate_cached_group_fusion.py](../llm_grouped_fusion_validation/evaluate_cached_group_fusion.py)

外部方法参考：

- [RAGAS: Automated Evaluation of Retrieval Augmented Generation](https://aclanthology.org/2024.eacl-demo.16/)
- [ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems](https://aclanthology.org/2024.naacl-long.20/)
- [The Web Conference 2026 Research Tracks](https://www2026.thewebconf.org/calls/research-tracks.html)
