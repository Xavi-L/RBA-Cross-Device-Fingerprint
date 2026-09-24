# S06 STEP_REPORT — E1 冻结主运行

记录日期：2026-09-24；本地完成，等待审查。本次不提交、不推送、不进入 S07。

**432/432 个预定单元完整且唯一地执行并落盘；两种方法的攻击检出和精确 0→1→0 均为 0/54。** 技术运行与保存结果一致性验收 PASS，不代表检测有效性通过。所有单元为 NO_ALERT；失败、弃判均为 0。时间对照事实仍 UNKNOWN，FPR 不可评估。

## 1. 版本、授权与实际运行绑定

- 审查与本次起止 HEAD：`f3f934d0f93d72e16b3d97e4e390796065e5fff8`，分支 main。未修改 Git 历史，原有 270 个无关工作区条目保留。
- 唯一快照：`05_freeze_r1`；freeze_revision：`formal-manipulation-freeze-r1`。
- protocol_digest：`9a6cb92a5d973a42d230305e176ab9ef824bca2e8aae045dafed515ce61c0f19`。
- 合同：`formal-manipulation-relation-risk-attribution-v2`；策略：`formal-manipulation-family-or-v2`；协议 schema 仍为 `formal-manipulation-protocol-v2`。
- run_id：`s06-e1-freeze-r1-20260924T044354Z`；新 job：[`RUNNABLE_JOB.json`](RUNNABLE_JOB.json)，摘要 `2cac526275d94d6b6d3b3be8d337893fe13fd4811888f24998026b37dacb9c75`。
- 本次用户授权单独记录在 [`AUTHORIZATION.json`](AUTHORIZATION.json)。先检查 154 个冻结绑定文件、48 份源码、28 份运行资源与继承语义，再从冻结 S06 静态清单建立新 runnable job；静态计划与 protocol 的历史未授权标记保持原样。

临时运行根目录：

```text
/private/var/folders/rk/2gmg78l55dl2m5ld98kpb3100000gn/T/hybridguard-s06-frozen-r1-5hxwg5re/frozen_sources
```

实际 v2 配置目录和策略路径：

```text
/private/var/folders/rk/2gmg78l55dl2m5ld98kpb3100000gn/T/hybridguard-s06-frozen-r1-5hxwg5re/frozen_sources/hybridguard_agent/config/formal_manipulation_role_gate_v2
/private/var/folders/rk/2gmg78l55dl2m5ld98kpb3100000gn/T/hybridguard-s06-frozen-r1-5hxwg5re/frozen_sources/hybridguard_agent/config/formal_manipulation_policy_v2/decision_policy.json
```

使用 Python 3.14.3 独立子进程（`-I -B -S`）、空 cwd、清除 PYTHONPATH；源码及资源复制内容逐项与冻结清单绑定，不回退主工作区。预测进程记录 36 个实际算法模块路径，评估进程 16 个；模块 `__file__`、配置路径、资源实际读取路径及启动预检分别保存在 [`PREDICT_PROCESS_AUDIT.json`](PREDICT_PROCESS_AUDIT.json) 与 [`EVALUATE_PROCESS_AUDIT.json`](EVALUATE_PROCESS_AUDIT.json)。编排脚本仅负责启动、IO 边界和计数，不替换规则或验证器。

启动准备发现冻结 `persistence.new_output` 要求 artifacts 及研究子目录已存在。本次仅在临时源码副本建立两个空目录，未改冻结文件、配置、输入或算法；操作在首个真实单元之前完成，见 [`JOB_BINDING.json`](JOB_BINDING.json)。没有失败的真实批次或重试。

旧报告里的“未推送”“待审查”是原记录时点；本次外审通过单独登记。协议中的旧 code_commit 与打包基线也是冻结历史，不替换成当前 HEAD。

## 2. 执行闭合、完整事件及防泄漏

固定两个变体 `final_v3_v2:App177:SRC-111`、`legacy19_v2:App177:SRC-111`，各 216 阶段：54 个准入攻击三态 × 3 阶段，加 18 个时间对照三时点 × 3 阶段。相同 payload 的不同评估单元保留。S02 其余 46 阶段属于后续已冻结描述范围，本步未执行。

| 产物/核对项 | 实际数量 |
| --- | ---: |
| 预定 / 唯一预测 / runtime / 逐单元回执 / 评估 join | 各 432 |
| final 完整规则事件 | 216 × 87 = 18,792 |
| legacy 完整规则事件 | 216 × 19 = 4,104 |
| 全部规则事件 | 22,896 |
| 准入攻击三态结果 | 54 × 2 = 108 |
| 时间对照关联结果 | 18 × 2 = 36 |
| 逐配置汇总、逐配置原因 | 各 20 × 2 = 40 |
| 失败 / 弃判记录 | 0 / 0，空文件保留 |

final 的 87 项包含 57 项 ACTIVE 及非 ACTIVE 目录处置，并非新增 87 条 ACTIVE。完整事件保留原 outcome、原规则结果、A/B/C、角色、来源、原/决策家族、是否参与与原因；runtime 保留完整 evidence、原执行、cards/context、原决定、原 Verifier 与风险 Verifier。432 份原/风险验证结果均 valid。

预测文件在 **04:44:53.914992 UTC** 关闭；**04:46:13.360487 UTC** 核对精确 432 单元及全表完备后才允许读取独立评估事实，**04:46:16.726122 UTC** 完成评估。见 [`PREDICTION_CLOSURE.json`](PREDICTION_CLOSURE.json)。worker 参数仅为 payload、冻结 contract、condition_id、input_view、method；payload 的顶层字段仅 adapter_version、features、field_quality、field_status、record_schema_version。标签、phase、tool、攻击 config、原路径、session/install/group、执行日志及未来 post 未送入 worker。这里冻结算法 contract 与研究变体参数不同于样本侧攻击配置。

原完整链实际调用：evidence 432、worker 432、原规则/runtime_cards 各 1,296、原 Verifier 864、风险事件 864、风险策略/风险 Verifier 各 432。多出的内部规则调用属于原 Verifier 的冻结重算逻辑，不是额外实验单元或重试。没有单关系 probe 替代完整链；评估及后续汇总调用检测器 0 次。

## 3. 固定分母主结果

下表每列分别以同一组 216 阶段评价；方法数不是独立样本数。

| 指标 | final_v3_v2 | legacy19_v2 |
| --- | --- | --- |
| 准入攻击阶段检出 | 0/54（0%） | 0/54（0%） |
| 准入 clean_pre 报警 | 0/54 observed | 0/54 observed |
| 准入 clean_post 报警 | 0/54 observed | 0/54 observed |
| 准入阴性阶段合计报警 | 0/108 observed | 0/108 observed |
| 精确 0→1→0 三态成功 | 0/54 | 0/54 |
| 曾在 attack 报警的三态数 | 0 | 0 |
| 报警后的条件恢复率 | 不可评估，分母 0 | 不可评估，分母 0 |
| 弃判 / 失败 | 0/216 / 0/216 | 0/216 / 0/216 |
| 决策覆盖（至少一个候选家族可评估） | 216/216 | 216/216 |
| 候选家族覆盖分布 | 195 阶段 4/5；21 阶段 2/5 | 195 阶段 2/2；21 阶段 1/2 |
| 时间对照描述性结果 | 54/54 NO_ALERT | 54/54 NO_ALERT |
| 时间对照 mid FPR / 全时点 FPR | 不可评估 / 不可评估 | 不可评估 / 不可评估 |

14 个攻击配置的等权 TPR 宏平均及按 3 个环境关联组再按配置的宏平均均为 0。可识别失败区间 `[0,0]` 仅描述当前固定样本中无失败/弃判造成的不确定性，不是总体置信区间。未计算部署 prevalence、precision/F1/accuracy、概率校准或独立设备总体 CI。

所有准入三态的 attack−pre 与 post−pre 分数差均为 0。因为没有 attack 报警，不能把 clean_post 的 NO_ALERT 写成“成功检出后恢复”。

## 4. 各配置结果

以下各行数值对两个方法均成立；完整 40 行见 [`configuration_summary.csv`](analysis/configuration_summary.csv)。所有行决策覆盖 100%，但家族覆盖不等于 100%。pre/post 分母只含独立准入的 clean 阶段。

| 攻击配置 | 环境关联组 | 每方法阶段数 | 攻击检出 | pre 报警 | post 报警 | 精确 010 | 弃判 / 失败 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cdp_platform_only_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `cdp_resource_pair_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `cdp_screen_metrics_only_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `cdp_timezone_only_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `cdp_ua_only_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `cdp_ua_platform_desktop_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `cdp_webdriver_only_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `stealth_languages_only_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `stealth_plugins_mime_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `stealth_webgl_pair_v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `w6-tool-054-legacy-default-v1` | env-003 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `w6-tool-055-legacy-default-v1` | env-001 | 9 | 0/3 | 0/3 | 0/3 | 0/3 | 0 / 0 |
| `w6-tool-056-legacy-default-v1` | env-001;env-002;env-003 | 27 | 0/9 | 0/9 | 0/9 | 0/9 | 0 / 0 |
| `w6-tool-058-legacy-default-v1` | env-001;env-002;env-003 | 27 | 0/9 | 0/9 | 0/9 | 0/9 | 0 / 0 |

时间对照只作描述；下表同样每行、每方法分别计数，不合并为阴性分母。

| 时间对照配置 | 环境关联组 | 每方法阶段数 | pre / mid / post | NO_ALERT | 无干预事实 | FPR |
| --- | --- | ---: | --- | ---: | --- | --- |
| `CONTROL:20260823_api30_no_attack_temporal_v6` | env-001 | 9 | 3 / 3 / 3 | 9 | UNKNOWN | 不可评估 |
| `CONTROL:20260823_api35_no_attack_temporal_v1` | env-002 | 9 | 3 / 3 / 3 | 9 | UNKNOWN | 不可评估 |
| `CONTROL:20260823_api36_no_attack_temporal_v1` | env-003 | 9 | 3 / 3 / 3 | 9 | UNKNOWN | 不可评估 |
| `CONTROL:20260823_api36_rule_boundary_no_attack_v2` | env-003 | 9 | 3 / 3 / 3 | 9 | UNKNOWN | 不可评估 |
| `CONTROL:20260824_api36_cdp_emulation_v5_no_attack_v1` | env-003 | 9 | 3 / 3 / 3 | 9 | UNKNOWN | 不可评估 |
| `CONTROL:20260824_api36_stealth_boundary_no_attack_v1` | env-003 | 9 | 3 / 3 / 3 | 9 | UNKNOWN | 不可评估 |

6 个对照配置合计 54 时点、18 midpoints/方法，但 eligible 阴性分母仍为 0，结果存为 null 与 NOT_EVALUATED_NO_ELIGIBLE_LABELS。未以 MTC、已准入 clean 或其他阴性集合替换该分支。

## 5. 未检出、弃判与失败原因

两种方法各 54 个已准入攻击阶段均未报警：至少一个候选家族可评估，但没有满足冻结资格的关系冲突。原关系一致结果保持 MATCH；归因 UNKNOWN 没有额外否决已符合条件的风险资格。逐单元原因、候选事件和观察规则反例见 [`unit_diagnostics.jsonl`](analysis/unit_diagnostics.jsonl)、[`missed_positive_units.jsonl`](analysis/missed_positive_units.jsonl)；每配置原因见 [`configuration_reasons.json`](analysis/configuration_reasons.json)。这些是保存结果描述，不是对操纵因果机制的新认定。

final 的 7 个候选在 54 个攻击阶段上的原 outcome：

| rule_id | MATCH | UNKNOWN | NOT_APPLICABLE |
| --- | ---: | ---: | ---: |
| NVW-001 | 54 | 0 | 0 |
| NVW-002 | 54 | 0 | 0 |
| NW-001 | 33 | 0 | 21 |
| NW-002 | 33 | 21 | 0 |
| NW-005 | 0 | 39 | 15 |
| OFFDER-OS-001 | 33 | 21 | 0 |
| OFFDER-OS-002 | 54 | 0 | 0 |

legacy 保留其中 NVW-002、NW-002、OFFDER-OS-001、OFFDER-OS-002 四候选、两个家族，原 outcome 与对应列一致。final 总计 261 个候选 MATCH 事件；未支持门控包括 21 个缺显式 model/build token 事件、42 个不透明/非正/歧义 Android 版本事件、15 个软件渲染事件和 39 个无法唯一识别硬件家族事件。42 个版本事件是两条相关规则各 21 个阶段，不能当作 42 个独立样本。GPU 硬件家族关系在攻击阶段均不可评估，未为检测而把软件回退当硬件强比较。legacy 为 174 个候选 MATCH 及 42 个版本门控事件。

原完整关系链仍有观察信号：两种方法各 **36/54** 攻击阶段含非风险候选 COUNTEREXAMPLE，final 为 123 条、legacy 为 102 条事件。UA/platform 相关配置中可见 NW-006、OFFDER-UA-001/002 及 final 的 P3-UA 检查反例；GPU 相关配置中有 OFFDER-GPU-001 反例。它们按既有 observation_only/diagnostic 角色保留，未因本轮标签或结果晋级。资源、plugins、screen 等更改也不自动成为这七个身份关系候选的冲突。预期修改字段只在评估侧作为原声明记录，不据此伪造字段效果或风险票。

没有技术失败，也没有全部家族不可评估导致的弃判；本轮负面结果不能以“全弃判”解释。100% 决策覆盖仅指至少一个家族可评估。clean_pre/post 的零报警不能弥补攻击检出为零，不能据此宣称实用检测能力或总体低误报。

## 6. 保留的事实与研究限制

S01 标签、任务准入和环境组、S02 输入与三阶段关联全部不变；本次没有重跑上游、合成验收、P0–P6或采集。准入三态的 162 阶段/方法沿用 L1_RECEIPT_SUPPORTED，54 个时间对照阶段/方法沿用 L0_ANNOTATION_ONLY_OR_INCOMPLETE。没有独立证明所有干预尝试成功；只评价冻结准入集合，不泛化到全部工具尝试。

3 个环境组是环境关联组，不是 3 台已证明独立物理设备；材料已有发现/开发暴露历史，属于固定材料回放，不宣称新盲测总体。App177 未补造 Browser。风险归因仍 UNKNOWN、attack_classification 仍 NOT_EVALUATED；分数是冲突家族数，不是攻击概率。

来源归属、57 ACTIVE、7 候选/5 家族、共同门控、同家族去重、固定 OR 与阈值 1 全部不变。O_u 的候选家族与 E 重叠，H/C 无候选是预设结构限制；S06 只运行 SRC-111，不产生来源消融或联合增益结论。后续不能用本轮结果调规则、阈值、角色、标签或分组。

## 7. 验收、产物与停止状态

[`VALIDATION.json`](VALIDATION.json) 与 [`FOCUSED_CHECKS.txt`](FOCUSED_CHECKS.txt)：23/23 保存结果核对通过，无再次执行规则/Verifier。启动前的冻结/资源校验另见 [`STARTUP_VALIDATION.json`](STARTUP_VALIDATION.json)。519 个登记历史文件的 size/mtime 保持；Git 变动范围仅本步骤产物和当前计划/状态，未暂存、提交或推送。预测尝试各一次，无自动重试、挑选或覆盖。

保存结果检查器自查发现曾用简称 ALERT 比较，应使用冻结枚举 MANIPULATION_ALERT；仅修正检查器并重读保存文件。原预测、冻结评估器、正式 metrics 完全未改；全部保存决定为 NO_ALERT，因此本轮数值不受影响。初次检查记录保留在 [`audit_history`](audit_history/)，不隐藏该修正。

核心输出：

- [`predictions.jsonl`](prediction/predictions.jsonl)、[`rule_events.jsonl`](prediction/rule_events.jsonl)、[`runtime_records.jsonl`](prediction/runtime_records.jsonl)、[`failures.jsonl`](prediction/failures.jsonl)、[`abstentions.jsonl`](prediction/abstentions.jsonl)。
- [`evaluation_joined.jsonl`](evaluation/evaluation_joined.jsonl)、[`metrics.json`](evaluation/metrics.json)、[`metrics.csv`](evaluation/metrics.csv)、[`triplet_results.jsonl`](evaluation/triplet_results.jsonl)、[`temporal_results.jsonl`](evaluation/temporal_results.jsonl)。
- [`SUMMARY.json`](analysis/SUMMARY.json)、逐配置汇总/原因、逐单元诊断、时间对照描述长表。
- [`run_manifest.json`](run_manifest.json)、原预测关闭 manifest、job/授权/路径绑定、逐次回执及两个独立进程日志。[`reproduction/README.md`](reproduction/README.md) 说明实际调用及复核边界。

本次技术验收 PASS；科学结果是冻结两种方法均未检出 54 个准入攻击阶段。计时含审计/profile 开销，只作运行记录，未执行 S11/E6 性能计时实验。LLM 调用 0，合成运行 0，S07/S08/S10 等后续单元 0。S06 更新为 DONE、等待外部审查；下一步必须另获明确授权。
