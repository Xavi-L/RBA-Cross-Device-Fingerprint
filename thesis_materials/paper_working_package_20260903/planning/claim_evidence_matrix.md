# HybridGuard 主张—证据矩阵

本表用于约束草稿中的事实主张。`Current` 表示现阶段可以写成已经实现或已经观察到；`Historical` 表示来自旧数据或旧实验管线；`Future` 表示设计已明确但尚缺正式证据。

| 编号 | 论文主张 | 主要证据/模块 | 状态 | 安全写法 | 正式投稿前仍缺少的证据 |
|---|---|---|---|---|---|
| C01 | Android Hybrid 环境存在 Native、WebView Host 和 App Web Runtime 三个可相互关联的观测面 | FeatureApp 字段目录、采集实现、WebView/JSBridge 结构 | Current | HybridGuard explicitly separates three in-app observation surfaces. | 独立真机上的覆盖与稳定性统计 |
| C02 | FeatureApp 产生固定 App177 | versionCode 8/10 字段目录与 validator | Current | The collector emits a fixed-contract 177-signal App observation. | 统一最终 release lock |
| C03 | 独立系统浏览器产生固定 Browser67 | browser probe manifest、browser raw/analysis 路径 | Current | HybridGuard implements an independent 67-signal browser probe. | 大规模完成率与多浏览器覆盖 |
| C04 | App177 与 Browser67 可通过来源证据组成 paired244 | receipt、closed batch、pair provenance、snapshot builder | Current | Provenance-complete pairs are deterministically materialized as paired244. | 更多完整配对样本与跨平台验收 |
| C05 | Browser 失败时合法 App177 被保留且不补零 | `app_only_177`、selection audit、missingness policy | Current | Incomplete browser capture produces an App-only view rather than an imputed 244-vector. | 大规模失败原因统计 |
| C06 | 字段值和字段可用状态被分开保存 | field-status schema、snapshot output | Current | Values are interpreted together with explicit observed/unsupported/error states. | 不同 OS/设备族状态分布 |
| C07 | 控制面元数据不进入推理特征 | sample index、runtime index、EvidenceBundle 构建 | Current | Provenance and experiment-control metadata are separated from model-visible evidence. | 端到端自动泄漏检查 |
| C08 | 原始指纹可转化为确定性跨层证据 | EvidenceBundle v2、extractor、hash | Current | Identical frozen inputs and extractor versions produce reproducible evidence bundles. | 对全部字段和关系的覆盖测试 |
| C09 | 关系具有适用条件、容错、反例和不可判定状态 | semantic relation catalog、predicate config、verifier | Current | Relations are evaluated only when their premises are available and applicable. | 更多真实设备反例与数值容差校准 |
| C10 | 官方文档知识与 device-mined rule 分源治理 | official cards、official-derived catalog、device-mined predicates | Current | Official semantics and empirical predicates are executed and reported separately. | 规则晋级审核记录和独立开发/测试隔离 |
| C11 | 当前攻击评价采用 baseline -> attack_active 两态 | 攻击 manifests、input set、两态验证脚本 | Current | The controlled protocol compares a baseline observation with an attack-active observation. | 统一最终协议版本和更多独立环境 |
| C12 | 当前受控攻击评价对象是 App177 | 69 对输入均来自 App177-compatible payload | Current | The present controlled evaluation deliberately operates on App177. | 带 Browser67 的正式攻击重采集 |
| C13 | 9 条官方派生关系在 69 对中产生 51 个转换 | official semantic validation report | Current | 51/69 qualified pairs exhibited a no-alert-to-alert transition under the frozen official-derived relation set. | 预注册、独立真机、置信区间与未见配置测试 |
| C14 | 10 条 device-mined predicate 在 69 对中产生 33 个转换 | source-isolated validation report | Current | 33/69 qualified pairs exhibited a transition under the frozen device-mined predicate set. | 正常真机证据充分性、独立测试集 |
| C15 | 18 对受控配置未被两类冻结规则覆盖 | relation comparison report、direct field deltas | Current | Eighteen verified field-changing pairs did not trigger either frozen relation track. | 新关系设计应只用训练/开发数据，并独立复验 |
| C16 | 当前数字不是 recall/FPR | 实验设计和分母边界 | Current | Results are reported as controlled relation-transition counts. | 正式标签、独立设备分组和完整负样本设计 |
| C17 | Browser67 当前未进入主要规则/决策路径 | browser sidecar 标记、runtime output | Current | Browser-pair observations are currently attached for audit and are not used by rule execution. | Browser-aware evidence、规则和模型 |
| C18 | Browser67 的检测增量尚未确定 | 当前数据不足 | Future | The incremental detection value of Browser67 remains an open empirical question. | App-only/Browser-only/paired 对照和消融 |
| C19 | 7 个 tri-layer semantic 特征在旧 grouped CV 中优于 raw-all teacher-score 拟合 | `ablation/README.md`、grouped metrics | Historical | Historical grouped-CV results suggest that compact semantic features retain teacher-score information. | 独立事实标签和最新版字段合同复验 |
| C20 | 官方知识在 GLM targeted pilot 中未改善 MAE/RMSE | `llm_grouped_fusion_validation/PILOT_REPORT.md` | Historical | The pilot exposed tolerance and explanation effects rather than a demonstrated accuracy gain. | 修订 prompt、完整分组缓存和独立测试 |
| C21 | RAG/Verifier 可形成可审计推理原型 | runtime、retrieval、verification、DecisionTrace | Current/Historical | The prototype records retrieved knowledge, cited fields and verification outcomes. | 正式检索指标、人工评审和 ablation |
| C22 | 当前系统不能输出校准攻击概率 | `calibrated_risk_score=null`、`external_model_called=false` | Current | The deterministic runtime does not produce a calibrated attack probability. | 独立标签、校准集和冻结融合模型 |
| C23 | stable profile/pair/scenario 需要整组切分 | experiment protocol、admission gate | Current design | Samples sharing stable identity or scenario provenance are assigned to the same split. | 足量可信 stable groups；当前准入仍未满足 |
| C24 | 项目计划构建开放数据集和 Benchmark | 整体框架与协议设计 | Future | The repository defines a path toward a provenance-aware dataset and benchmark. | 数据规模、许可、脱敏、固定 split、基线和数据卡 |

## 使用方法

- Abstract、Introduction 和 Contributions 只使用 `Current` 且证据边界清晰的主张。
- `Historical` 内容统一放在历史/预验证章节，不与最新版数据和事实标签混写。
- `Future` 内容使用 future work、planned evaluation 或 open empirical question 等措辞。
- 每次数据、规则、release lock 或实验分母变化后，都应版本化更新本表。
