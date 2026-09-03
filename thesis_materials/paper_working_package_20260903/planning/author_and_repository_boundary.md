# 两名作者与两个仓库的工作边界

本文档用于避免论文草稿在系统设计、攻击工具和实验结果之间出现归属混淆。作者顺序和最终 contribution statement 仍由导师决定；这里仅记录当前可从仓库事实确认的技术边界。

## 1. 主仓库：RBA-Cross-Device-Fingerprint

主仓库承担 HybridGuard 的系统和评价主线，包括：

- Android FeatureApp 与多层字段合同；
- Android Native、WebView Host 和 App Web Runtime 的 App177 采集；
- 独立 Browser67 探针；
- 后端 raw archive、receipt、batch、readiness 和幂等存储；
- App/Browser pair provenance 与 paired244 派生；
- App-only 留存、quarantine、sample index、selection audit、QC 和 dataset manifest；
- 字段状态、缺失语义、Schema 和版本冻结；
- SampleManifest、EvidenceBundle、KnowledgeCard、RiskDecision 和 DecisionTrace；
- 官方知识卡、官方派生语义关系和 device-mined rule 的分源治理；
- 确定性 predicate、检索、Verifier 和离线 runtime；
- 标签接入、stable group 准入、防泄漏 split 和实验控制面；
- RF/MLP、grouped CV、LLM 分组融合、知识消融和端侧评分等历史实验资产；
- 最终论文中的系统设计、数据治理、证据建模和整体评价框架。

论文中应以这些内容作为主要方法贡献，而不是把主线写成“攻击工具实现”。

## 2. 第二作者仓库：hybridguard-browser-fingerprint-research

第二作者仓库主要承担受控操纵和攻击侧实验资产，包括：

- 攻击能力与工具目录；
- Chrome DevTools Protocol、Playwright、Puppeteer、Stealth 等 runner 和配置；
- debug-only WebView 控制；
- baseline、attack_active 以及部分历史 clean_post 的采集；
- attack manifest、实验 session registry 和字段 mutation 标注；
- 工具执行、observable effect、字段 effect、归因和日志证据；
- 攻击配置、版本、适用环境和已知失败模式；
- 面向主仓的事实 sidecar 与可追溯交付。

主稿中不需要展开每个攻击工具的实现细节。最合适的落点是：

- Threat Model and Controlled Manipulations；
- Evaluation Dataset / Attack Cohorts；
- Per-configuration Coverage and Failure Analysis。

## 3. 共同形成的结果

以下结果由两个仓库共同支撑：

1. 攻击侧生成并验证受控 baseline/attack-active 输入；
2. 主仓将这些输入接入冻结的关系和规则评价框架；
3. 两条知识轨在相同分母上独立执行；
4. 最终报告关系转换、字段变化、覆盖交集和盲区。

因此，69 对受控实验的正确描述应体现协作关系：攻击仓库提供受控 manipulation、manifest 和执行证据，主仓提供字段合同、关系目录、规则执行、来源隔离、结果验证和报告口径。

## 4. Browser67/paired244 的后续分工

完整 Browser67 攻击数据到位前，当前攻击评价只使用 App177。后续重新采集时建议：

- 主仓冻结统一 FeatureApp、Browser probe、backend 和 pair provenance release；
- 攻击侧在每个 baseline 和 attack_active 阶段都尝试 Browser67；
- 攻击侧交付工具执行证据、事实标签、stable group 和 Browser capture status；
- 主仓统一完成 paired244 QC、EvidenceBundle、Browser-specific relations、grouped split、基线、消融和指标统计。

第二作者不需要复制主仓的数据治理、Agent/RAG 或模型训练管线；主仓也不应把攻击 runner 的开发细节写成自身独立成果。

## 5. 写作中的推荐措辞

推荐：

> Controlled manipulation runners and execution evidence were maintained in a companion attack-side repository, while HybridGuard provided the frozen collection contract, provenance-aware data pipeline, relation execution, and evaluation logic.

避免：

- `coauthor-built detector`：容易弱化第一作者对整体方法和系统的主导；
- 把所有攻击侧实现都归于主仓作者；
- 把主仓的关系验证写成第二作者仓库单独完成；
- 在正文中按个人逐项拆分过多工程细节。

最终 author contribution statement 可以按 Conceptualization、Methodology、Software、Validation、Investigation、Data Curation、Writing 和 Supervision 等角色组织，但应在导师确认后再定稿。
