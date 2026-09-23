# S04 v2 实现与原计划的接口说明

版本：`formal-s04-implementation-contract-v2`。审查输入：`8d2e8d55e34fcd75a4d6f3f5b9f0834862316554`。S03-R 外部审查通过后，仅授权 S04 的实现及合成验证。此记录不授权 S05 或正式实验。

## 固定绑定

风险策略为 `formal-manipulation-family-or-v2`，语义/角色合同为 `formal-manipulation-relation-risk-attribution-v2`，研究范围为 `featureapp-reported-identity-coherence-research-v2`。角色、门控、来源和家族只从 `hybridguard_agent/config/formal_manipulation_role_gate_v2/` 的完整七份配置加载；旧 source_registry 不参与运行时角色裁决。

新增策略、指标和图表配置位于 `hybridguard_agent/config/formal_manipulation_policy_v2/`。不向 S03/S03-R 目录增写或重生成配置。缺显式版本、缺文件、ID/来源/家族/角色冲突、混版本及阈值修改都明确拒绝，不回退。

## 关系层与风险层

当前目录仍执行原 evidence → rules → exact retrieval → original decision → original Verifier 链，保存 87 项目录结果，其中 57 项 ACTIVE；包括 MATCH、COUNTEREXAMPLE、UNKNOWN、NOT_EVALUATED、NOT_APPLICABLE、上下文与处置结果。原卡片和 `attack_classification=NOT_EVALUATED` 保持。S03-R probe 只用于合成对照，生产 worker 仅复用它的 A/B 门控函数。

独立风险层只接收角色允许、A=SUPPORTED、B=ELIGIBLE、原 Verifier 通过且原 outcome 为 MATCH/COUNTEREXAMPLE 的关系。家族 OR、阈值 1、无权重或搜索。C 始终 UNKNOWN。候选 7 条、家族 5 个；同族来源重复不加票。

`MANIPULATION_ALERT` 是限定研究范围的疑似操纵/风险提示；`NO_ALERT` 需要至少一个可评估家族；全无可评估候选为 `INSUFFICIENT_EVIDENCE`；解析、执行、门控或验证异常为 `FAILED`。失败没有有效分数或参与家族。NO_ALERT 报告覆盖且不证明安全；分数不是概率。门控异常不会在失败保存路径再次执行。

完整链的观察结果与来源条件选择分别保存。八条件排除某来源时，该来源结果继续保留在完整链审计记录中，但不参与风险家族评估；不能声称从整个运行时删除其知识、谓词或计算成本。

## 原计划三种比较的明确含义

1. **legacy19_v2**：从原 compiled registry 精确取 10 条设备谓词与 9 条旧语义谓词，保留原谓词，关闭短路以形成完整关系基线，再套用同一 v2 家族策略。旧 CORE-002 传感器条件保留为采集诊断；旧 OFFDER-WEBVIEW-001 仅历史诊断，无风险角色。实际候选 4 条、2 个家族。不能用 paired v1 的 48 项 ACTIVE 冒充旧 19 项。
2. **current_v3_relation_role_projection**：完整当前关系的角色投影，记录原候选冲突和 v2 排除原因。它是关系诊断，不是绕过 A/B 的第三个风险检测器。
3. **final_v3_v2**：完整 v3 关系与 v2 门控联合风险策略。按照本次“只有 A/B 通过才可报警”的要求，当前 v3 的合法风险视图与 final 是同一执行的别名；不给去门控诊断计算正式 TPR/FPR，也不伪造三种独立有效检测方法。原计划的第三种二值独立对比因此不可成立；差异改由保存的关系/门控事件解释。

这是接口/主张边界的显式修订，依据统一 v2 的必要条件，不依据正式预测。未来若要评价不符合 v2 的报警策略，必须另立研究版本。四项 E4 机制诊断在 variant spec 中规定为 S09 的单独授权内容；S04 不把诊断值写回风险预测。

## 运行、评估与绘图接口

`run_formal_manipulation_eval.py predict` 只接受盲化输入、固定 job、显式 contract/config/policy 和新输出目录。worker 无 opaque ID 参数；调度器在落盘时附加 ID 与变体键。相同 payload 的不同单元完整保留；预定缺件、坏 JSON、编码错误、类型错误和运行失败都有 FAILED 槽位。异常正文不进入输出。

`evaluate` 是独立入口，只在 `PREDICTIONS_CLOSED`、文件关闭并且全部预定单元/规则事件唯一对账后读取 S02 evaluation_index 和 S01 triplet 台账。标签、阶段、工具、配置、原路径、日志和未来 post 仅存在评估侧。预测、全部规则事件、原 runtime、失败和弃判文件保存后不可原地重跑。

`plot_formal_manipulation_eval.py` 只消费保存的 evaluation 输出，生成带源行、k/n、版本和过滤条件的 CSV/manifest。本步交付绘图数据接口和 figure spec，不发布论文图。S04 的全部执行产物明确为 SYNTHETIC_CONTRACT_TEST。

job schema 也定义将来正式运行的 `FROZEN_FORMAL_EVALUATION` 外形，须绑定 S05 冻结协议及单独授权的执行步骤；JSON 字段本身不能替代用户授权。本步未创建 S05 冻结协议或正式 job。

指标保留固定准入分母中的弃判、失败；失败报告可识别区间，弃判不计为正常。精确 010、条件恢复、配置/环境宏平均、三时点关联与预先配对的差分接口分别保存；不能按分数挑对照。相关环境不估总体置信区间，不校准概率。

## 下一步边界

S05 仍需单独授权，届时只能按本版本冻结真实分母、源码/配置/输入绑定、精确变体和独立评估侧表。本步合成通过不构成真实覆盖、TPR/FPR、来源收益或外部泛化证据。O_u 两个候选与 E 共享家族，H/C 无候选；结构性零增量不等于无研究价值。S01 时间对照 no_intervention 仍 UNKNOWN，不取得 FPR 资格；不补 Browser，不改原标签和环境关联组。
