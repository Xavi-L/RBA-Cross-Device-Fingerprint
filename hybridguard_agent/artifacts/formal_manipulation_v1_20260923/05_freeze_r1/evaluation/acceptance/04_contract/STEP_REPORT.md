# S04 STEP_REPORT

完成时间：2026-09-23T16:08:35.612581+00:00（北京时间 2026-09-24）。审查及当前 HEAD：`8d2e8d55e34fcd75a4d6f3f5b9f0834862316554`。本步仅实现和合成验证，工程验收 PASS；未进入 S05、未执行正式实验、未提交或推送。

## 1. 合同与交付

语义/角色合同明确绑定 `formal-manipulation-relation-risk-attribution-v2`，研究范围 `featureapp-reported-identity-coherence-research-v2`，固定风险策略 `formal-manipulation-family-or-v2`。完整配置从 `hybridguard_agent/config/formal_manipulation_role_gate_v2/` 显式加载；新增策略/指标/variant/figure 配置使用独立 `hybridguard_agent/config/formal_manipulation_policy_v2/`。缺版本、混版本、配置缺件、ID/角色/家族冲突和阈值变化均拒绝，不按来源回退。

实现包括 contract、policy、原谓词基线适配、独立风险验证、worker/持久化、离线 evaluation、reporting、合成夹具及闭合 schema。`run_formal_manipulation_eval.py` 的 predict/evaluate 是分离入口；`plot_formal_manipulation_eval.py` 只消费保存结果；`validate_formal_manipulation_s04.py` 可在新目录重现静态/合成验收。

原 S03/S03-R 来源文件仅提供既有事实依据，旧 observation_only 角色和强归因前提不会覆盖 v2。旧报告的未推送/待审查措辞属于原完成时点；用户本次外审通过单独登记，不覆写历史。

## 2. 原链与风险层

完整当前链保留原 evidence、全部规则、精确卡片、关系 decision 和原 Verifier。87 项目录结果全部记录，其中 57 项 ACTIVE；原 `attack_classification=NOT_EVALUATED`、无校准概率保护保持。S03-R evaluate_contract/_relation_probe 不替代完整链；它只在合成共同有效域对照测试中使用，worker 仅调用已审定 A/B 门控。

风险资格要求角色为 alert_candidate、A=SUPPORTED、B=ELIGIBLE、原验证通过、原 outcome 为 MATCH 或 COUNTEREXAMPLE。MATCH 也计入可评估覆盖；只有 COUNTEREXAMPLE 触发该家族。固定家族 OR、阈值 1，无权重或搜索。分数是冲突家族个数，不是攻击概率；C 始终 UNKNOWN，不因风险提示变成攻击、未经授权或恶意意图的证明。

| 结果 | 精确条件 |
|---|---|
| MANIPULATION_ALERT | 至少一个符合资格的冲突家族 |
| NO_ALERT | 至少一个候选家族可评估，且无符合资格的冲突；同时保存覆盖 |
| INSUFFICIENT_EVIDENCE | 没有可评估候选家族，包括 C-only/B0 |
| FAILED | 输入解析/类型、规则、门控或验证异常；分数为 null、不保留有效风险票 |

每条事件保存原 outcome/结果、来源、原 evidence_family、decision_family、角色、字段要求/状态、A/B/C、参与标志和原因。失败时有完整目录槽位；如果原结果未产生则记 null/未产生，不伪造关系值。若原验证或后续风险层失败，已经产生的原结果仍保留，但无风险参与。原 Verifier 内重算和风险验证成本均包含在 timings/total 中。

## 3. 来源与比较定义

| 来源 | ACTIVE | 候选规则 | 候选家族 |
|---|---:|---:|---:|
| E | 23 | 5 | 5 |
| O_u | 9 | 2 | 2，与 E 共享 |
| H | 14 | 0 | 0 |
| C | 11 | 0 | 0 |

共 7 条候选、5 个家族。O_u 的 app_os/host_os 与 E 在共同有效域、同门控下重复；E 保留时不增加家族，固定 OR 二值增量受结构限制。H/C 没有候选，不能把它们的结构性零值解释成实测来源无价值。八个 SRC 条件及公共 C/门控完全沿用；来源排除作用于风险参与，完整观察链的事件仍保存，不能声称移除了所有官方知识或其执行成本。

旧 19 项基线精确包含 10 条原设备谓词与 9 条原语义谓词，关闭短路作完整关系基线，再使用相同 v2 风险合同。它有 4 条候选、2 个家族。旧 CORE-002 传感器分支及退休的 provider/Chrome 关系保留为历史诊断，不赋予攻击票；paired v1 的整个目录并非这 19 项。

**原计划比较的版本化澄清：**current-v3 去门控角色投影保存为关系诊断，不产生违背 v2 A/B 条件的正式风险预测；其合法风险视图与 final 是同一执行别名。因此本版没有第三个独立二值检测器，不能给该关系诊断报告正式 TPR/FPR或假称独立 SOTA。新增计划说明 `S04_CONTRACT_IMPLEMENTATION_v2.md` 明确这一约束。variant_plan 保存 2 个风险方法 × 5 个 App 视图 × 8 个来源条件的 80 个精确定义；不是运行了 80 个实验。E4 的其他机制诊断依旧由 S09 单独授权，不在本步执行真实对照。

## 4. 防泄漏、指标和保存接口

worker 只接收当前 payload 与固定合同/变体，不接收 opaque ID、标签、phase、tool、执行 config、原路径、session/install/group、日志、回执或未来 post。调度器只在保存时附加 ID；相同 payload 的不同单元不去重。先保存并关闭 predictions/rule_events/runtime_records/failures/abstentions，登记 PREDICTIONS_CLOSED，再由独立入口 join 评估侧事实。坏 JSON、编码异常、缺输入行和执行失败仍占预定单元。

离线评估核对完整/唯一单元与规则事件；事实资格和原标注分开。UNKNOWN 无干预事实不会获得 FPR 资格。正负分母保留弃判/失败，报告无报警、弃判、失败、decision coverage、conditional rate 和失败可识别范围。010 必须精确 NO_ALERT→MANIPULATION_ALERT→NO_ALERT；缺 post、失败、弃判都不算 0。攻击三态和时间对照三时点关联分别保存；差分接口只接受事前环境/批次映射，不按分数挑控制，不因重复配对扩大阴性分母。

配置宏平均与环境内配置等权再环境等权分开；相关环境不提供总体置信区间或校准概率。绘图输出 CSV 带源行、版本、k/n、失败/弃判和过滤条件。本步仅交付合成绘图源表，不生成论文性能图。

## 5. 合成验收结果

最终 **35/35** 聚焦测试通过（policy 15、evaluation 12、leakage 8）。保存 5 个策略边界夹具全部符合预期；7 个候选的一致/冲突共 **14/14** 个共同有效域对照与原谓词一致。端到端保存 **14 条合成预测状态行、1,218 条目录事件**（其中 ACTIVE 事件 798），包括 3 个预期 FAILED 单元，全部唯一对账。

合成手算正例分母 4（提示/无报警/弃判/失败各 1）；合成已验证 control_mid 分母同样为 4；全部合成阴性 8，另有 2 个 UNKNOWN 真值不入正负分母。冻结的合成三态分母 3，精确 010 成功 1，另外包含失败和缺 post；手算期望全部匹配。这些是程序测试的人造事实，**不表示 S01 的真实时间对照取得了阴性资格，也不是真实 TPR/FPR**。

防泄漏测试覆盖元数据/标签置换、未来 post、路径与同值不同单元、遮蔽值/状态/质量/派生事实、capture/control 标记、允许的 Headless UA 内容、false/0/空列表、日志/facts 故意不可读、closed schema、冻结/已有输出目录防护。验证失败、原结果/字段引用/门控/分数篡改、版本混用拒绝、v2 接入、来源门控相同和原谓词一致性均有聚焦测试。

初始 31 项测试中一项路径拒读夹具因 macOS 临时目录别名未命中而失败；修正测试 guard 的 resolve 后通过。生成产物时 34 项通过；末轮复核补充门控/验证异常的失败保存路径和编码异常槽位后，最终 35 项通过。三个时点日志及说明全部保留，不抹去旧行为证据。末轮修正不改变已保存合成输入的预测语义；保存的失败均为 parse 阶段，完整记录见 DEVELOPMENT_CHECK_HISTORY。

## 6. 仍保留的事实与研究限制

S01/S02/S03/S03-R 未重跑；262 条原阶段、原准入、分组和输入不变。54 条时间对照 no_intervention 仍 UNKNOWN，不进入对应 FPR；不补 Browser，不拼接无关会话。缺日志、L1 证据上限、三个环境关联组不等同独立物理设备、Native 仅相对参照等限制均保留。

当前工程证明限定合同可执行及合成边界正确，不证明真实候选覆盖、真实检测性能、来源正收益、物理身份/恶意意图、外部泛化或校准概率。合法自定义/OEM/渲染路径仍可能造成风险提示，必须保留合法标签。当前所有阈值/门控均不根据正式效果选择。

已登记的 238 个既有相关文件 size/mtime 保持一致，原链、冻结目录、S03/S03-R 配置和历史产物未修改；这是一项有限文件状态检查，不是密码学认证。工作区已有其他改动保留，HEAD 未变、暂存区为空。S04 更新为 DONE/PASS，S05 保持 PENDING_AUTHORIZATION。停止等待下一步授权。
