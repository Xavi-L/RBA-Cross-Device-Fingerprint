# S05 运行前冻结说明 v2

协议：`formal-manipulation-protocol-v2`；study：`formal-manipulation-v1`。本次先按用户授权交付 S04，提交 `f00e699d2763afed5369774f01e5a0f632d8f5c6` 已推送且远端 SHA 核对一致，再执行 S05 静态冻结。S01–S04 报告中的“未推送”“等待审查”保留为原记录时点，不覆盖验收历史。

独立配置目录为 `hybridguard_agent/config/formal_manipulation_protocol_v2/`，独立产物为 `hybridguard_agent/artifacts/formal_manipulation_v1_20260923/05_freeze/`。生成器必须同时显式指定 output/config-dir；目的地已存在、重叠或落入历史保护目录（含符号链接解析后）时先拒绝写入。

## 不变合同

采用 S03-R 的 `formal-manipulation-relation-risk-attribution-v2` 和 S04 的 `formal-manipulation-family-or-v2`。57 ACTIVE，E/O_u/H/C=23/9/14/11；7 候选、5 家族；同家族 OR、阈值 1。原完整规则结果与 Verifier 不变；角色允许、A=SUPPORTED、B=ELIGIBLE、原关系 MATCH/COUNTEREXAMPLE 且验证通过才可参与风险评估。C 保持 UNKNOWN，风险提示不变成攻击、未经授权、恶意意图或概率的证明。

v1 来源表仅保存来源依据；v2 配置七件完整绑定。O_u 两候选与 E 共享家族，H/C 无候选的结构限制不变。公共语义门控保留，来源分组消融不等于移除所有官方知识。

## 固定运行范围

- S06：216 阶段 × final_v3_v2 / legacy19_v2，共 432 唯一单元。当前 v3 关系投影为 final 的诊断别名，无第三个独立二值检测器。
- S07：同 216 阶段 × 八来源；联合 SRC-111 复用 S06，新增 1,512 单元。四来源映射仍 C/B0=000、E=001、O=110、EO=111。
- S08 App：同 216 阶段 × 五视图；App177 联合条件复用 S06，新增 864 单元。无 Browser 攻击视图。P6 只做已保存输出复用。
- S10：45 条低证据阶段及 1 条不完整阶段，固定 final/App177/SRC-111，共 46 个描述单元；不进入检测性能分母。空包继续引用 inventory，未造阶段。

共 13 个不同风险变体、2,854 个唯一真实材料计划单元。80 个 S04 静态组合中未选的 67 个不在本协议运行。计划单元不是已执行预测；相同 payload 的不同 ID 不去重。

S01 的准入攻击阶段/三态各 54，clean_pre/post 各 54。54 条时间对照 no_intervention 仍 UNKNOWN；主 control_mid FPR 分母为 0，关闭此性能项，保留描述。S01/S02 没有已登记的跨包共同批次键，因此 54 准入三态均不构造与时间对照的配对差分；按环境/配置分层，不能用命名、日期相近或检测分数冒充配对证据。

## S05 明确的接口和图表修订

1. S04 离线汇总读取 `configuration_id`。S02 有合法 null，同时保留 `config_id`。冻结评估索引按 `configuration_id → config_id → CONTROL:<bundle_id>` 确定汇总键，并在 `S02_configuration_id` 保存原值；原 S02 完整副本和 admission_fact 逐条不变。这仅在评估侧发生，避免将全部旧配置归到 null 组。API 来自已适配的显式 Native 字段，机制只是 S01 申明修改字段集合，不重新认定机制标签。
2. S04 figure_spec 的 Fig.6 占位描述为缺失/成本/解释，与总计划第 3 节的操作点图不同。S05 新版 figure_spec 将 Fig.6 固定为八个事前来源条件的离散 control_mid FPR × TPR 操作点，成本/边界放表与附录。当前 FPR 标签不足，Fig.6 此项 NOT_EVALUATED；不把 clean_pre/post 或 MTC 偷换为横轴分母，不画 ROC 或平滑曲线。
3. E4 精确定义四种诊断，均独立于正式风险输出。D1 只去掉 v2 中 `_reduced` 拒绝条件，原 model_token/其他必要条件仍保留；D2 只在合成 shadow accessor 中显式忽略可用性，不填值、不改原 observed；D3 仅从保存事件派生重复规则票，阈值 1 下二值增量结构性为零；D4 仅合成原始 JSON 等值，不冒充原链。D1/D3 涉及主 216 阶段的保存输入/事件；D2/D4 不在真实材料上产生替代检测器。任何绕过 v2 的检测性能主张仍不可评估。
4. E5 固定 49 个合成输入中的 37 个缺失/协调边界案例；另 12 个用于 E4，所有 payload 完整保存且不分配攻击真值。自然 MTC 的 654 App-only、11 partial、6 同 session 额外观测在本协议只复用已有材料分类，不安排新策略预测。若以后需要自然 MTC 运行，须先另行冻结其输入和精确单元，不能临时扩矩阵。
5. E6 固定主集合的环境×cohort×phase 分层，组内 opaque ID 排序，轮转选 24 阶段；两方法各 1 冷启动、3 warmup、20 测量，共 1,152 个计划重复。预定序列、median/nearest-rank P95、失败处理、Verifier 重算成本及解释审查队列规则均入协议。样本重复不是独立设备，不选最快次。

## 停止与后续授权

S05 仅做静态清单、schema/集合检查、文件复制和有限版本绑定。没有运行原谓词、门控或风险 worker，没有真实/合成新预测或真实 TPR/FPR。S04 的旧合成输出是历史产物。

冻结 status 不授权执行。`step_execution_plans` 使用不能被 S04 predict 接受的静态计划 schema；未来只有在单步授权后才将对应精确单元转成 runnable job，并明确绑定冻结源码、输入和 v2 路径。不得自动进入 S06，不自动提交或推送 S05。
