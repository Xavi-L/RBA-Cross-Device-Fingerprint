# R05 折内选择、折外评价与旧策略比较

状态：**执行与技术验证完成，等待外部验收**。审查基线 `772890fbb14fb50b35d9fa410fddf0b673563c02`。本次单独登记 R04-R1 外部验收于 `R04_R1_EXTERNAL_ACCEPTANCE.json`；R04/R04-R1 原报告、VALIDATION、历史授权字段与失败例保持原样。

本轮只运行用户明确授权的 R05：3 个 LOEO 折、3 个学习方法、OP05/OP00/OP10、4 个固定基线。主比较仍为 GREEDY_OR/OP05。没有按外层成绩选择操作点、改算法或重跑。R06、全开发集重拟合、采集、攻击工具、旧 S07、提交和推送均未执行。

## 绑定与实际执行

- 必须快照：`../R04_freeze_r1/`，没有工作区代码、其他解释器或求解器回退。
- 研究协议 digest：`4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`。
- 本次实际 FREEZE_MANIFEST SHA-256：`bff86c2423283d9ecdf6402c2975a747707cd7d521a328561ef676cdcff2ddad`。
- 本次实际 RESOURCE_MANIFEST SHA-256：`7e2aa45c9cf78abc106cb61e3863c5d89f2491fe0b406b645cd48fad80bd0de0`。
- 快照外本次授权 `R05_APPROVAL.json` SHA-256：`45ecd73c7fda8fdda19a50554e69010b26d2a686b7a5551973a4bb83fff6edeb`。授权绑定精确 job IDs、train 成员及共享真实研究账本。快照中的历史 `real_execution_authorized=false` 与旧验收时点字段没有改写。
- 运行依赖：快照 Python 3.12.14、HiGHS/highspy 1.12.0、NumPy 2.3.5，macOS-15.7-arm64-arm-64bit，单线程。系统框架依赖沿用冻结的同平台约束。
- 启动检查实际验证 3,298 个资源文件；完整性检查读取字节、不解码全分区特征或标签。实际模块/解释器/依赖路径与空 cwd 见 `PREFLIGHT.json`、`SOURCE_RUNTIME_VALIDATION.json`。
- 按已有 `launch.py run` → dispatcher → worker 路径执行，完整 argv 和 cwd 见 `DISPATCH_COMMAND.json`。UTC 2026-09-24T12:07:03.253193+00:00 至 2026-09-24T12:07:40.362831+00:00，wall time 37.109683 秒，exit 0，真实运行 attempt=1、重试=0。

每个单元均记录只读 train → train 内转换/支持度/选择 → 保存并加载、冻结模型 → 首次打开 outer_test 特征 → 保存/关闭并逐成员对账预测 → 打开 outer 评价标签。39 个访问日志均按精确资源路径/成员核对；每个模型 freeze_time 来自正式执行，早于该模型首次 outer 特征访问。预先固定的 R02 无标签缓存只读复用；核心视图不需要数值分位点拟合，本次数值阈值拟合数为 0。模型采用真实 LOEO-v1/R02_FIXED_CACHE/EXACT_AUTHORIZED_JOB_TRAIN_ONLY 血缘，没有 SYNTHETIC 标记或训练后手工改 JSON。

## 单元完整性与训练结果

| 对象 | 预期 | 实际完成 | 缺失/重复 | 空模型 | 失败/超时/预算耗尽 |
|---|---:|---:|---:|---:|---:|
| fit | 27 | 27 | 0 | 0 | 0 |
| model/基线单元 | 39 | 39（27 FITTED + 12 FIXED） | 0 | 0 | 0 |
| prediction | 2,106 | 2,106 | 0 | — | 0 |
| 每个 OOF 方法/操作点组 | 162 阶段 × 13 组 | 13 组齐全 | 0 | — | 0 |

2,106 是同一批 162 个监督阶段在不同方法/操作点下的评价记录，不是 2,106 个独立样本。每组保留攻击 54、pre 54、post 54，共 54 个完整三态。另 100 个描述阶段排除在监督评价之外；UNKNOWN 时间对照与未标注 MTC 不用于补算 FPR。排除 ID 与逐单元去向见 `PREDICTION_RECONCILIATION.json`、`MODEL_MANIFEST.jsonl`、`FIT_RECONCILIATION.jsonl`。

27 个学习模型全部选择同一条 `DEVIATION:OFFDER-UA-001:POSITIVE`，每模型 1 子句、1 字面量、复杂度 2，包含 DNF2 的单字面量解；没有选择二元 AND。每折完整模型 ID、公式、来源和目录方向解释见 `MODEL_RULES.md`。规范 POSITIVE 对应原目录条件 NEGATIVE，U 不转成 T。

GREEDY_OR 的 9 次拟合状态为 HEURISTIC_FEASIBLE；18 次 IP 状态为 OPTIMAL_FINITE_POOL，gap=0、并列处理完成。最优性仅覆盖训练折有限且支持度合格的候选池，不是列生成或无限规则空间证明。OR 每折登记 20 字面量、支持后 13；DNF2 每折登记 188 子句，支持/有限剪枝后分别为 66、66、61。候选登记、支持、剪枝与选择轨迹分别保留。

| fold | train 阶段 | outer 阶段 | train clean | OP05 集合预算 | 实际 clean 报警 | 可用三态/真攻击三态支持 | outer 攻击检出 | 精确 FTF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LOEO-v1-01 | 135 | 27 | 90 | 4 | 0 | 45/18 | 6/9 | 6/9 |
| LOEO-v1-02 | 144 | 18 | 96 | 4 | 0 | 48/21 | 3/6 | 3/6 |
| LOEO-v1-03 | 45 | 117 | 30 | 1 | 0 | 15/9 | 15/39 | 15/39 |

三折 OP00 预算均为 0；OP10 预算依次 9、9、3。全部 27 个模型实际 train clean 报警均为 0，attack/pre/post 决策覆盖均为 1.0，训练执行失败为 0，支持度、子句/字面量/复杂度约束全部满足。三折选中规则的支持分别涉及 6/7/3 个批次、2/2/2 个环境、5/6/2 个配置；这是训练支持，不能称独立物理设备。训练目标与 clean 预算用保存的训练状态独立算术复核，未重新拟合。

## 折外比较

所有分母均是预期阶段或完整三态，失败/弃判不从分母移除。NE = NOT_EVALUABLE，value=null；atom 与 clause 覆盖在本轮各模型中数值相同。

| 方法 | 操作点 | 攻击检出 | pre 报警 | post 报警 | 精确 FTF | 决策覆盖 | 弃判 | 失败 | 原子覆盖 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALWAYS_ABSTAIN | NOT_APPLICABLE | 0/54 | 0/54 | 0/54 | 0/54 | 0/162 | 162/162 | 0/162 | 0/0 NE |
| ALWAYS_NO_ALERT | NOT_APPLICABLE | 0/54 | 0/54 | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 0/0 NE |
| DIRECT_CORE_OR | NOT_APPLICABLE | 24/54 | 0/54 | 0/54 | 0/54 | 24/162 | 138/162 | 0/162 | 1416/1620 |
| FINITE_IP_DNF2 | OP00 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| FINITE_IP_DNF2 | OP05 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| FINITE_IP_DNF2 | OP10 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| FINITE_IP_OR | OP00 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| FINITE_IP_OR | OP05 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| FINITE_IP_OR | OP10 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| GREEDY_OR | OP00 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| GREEDY_OR | OP05 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| GREEDY_OR | OP10 | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 |
| HISTORICAL_SEVEN | NOT_APPLICABLE | 0/54 | 0/54 | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 0/0 NE |

主方法攻击检出 24/54=44.44%，clean 报警 0/108，精确 FTF 24/54，决策与所选规则覆盖 162/162。按冻结的配置、配置内环境等权宏平均为 6/14=42.86%，与阶段微平均不同。条件恢复 24/24 只针对已报警攻击，不能替代完整三态的 24/54。

相较 HISTORICAL_SEVEN，主方法多检出 24 个攻击阶段且本材料 clean 报警不变。历史基线的 162 条结果均通过冻结输入/方法证明复用，旧检测器调用为 0；不混入另一个历史方法作为额外样本。

DIRECT_CORE_OR 同样检出 24/54，却在另外 30 个攻击阶段及全部 108 个 clean 阶段弃判，故决策覆盖仅 24/162，FTF 为 0/54、条件恢复为 0/24。其 clean 动作报警 0/108 伴随 decided-clean 分母 0，后者为 NOT_EVALUABLE/null，不能宣称低误报。每阶段 OR 含 10 个规范原子，覆盖为 1,416/1,620；其中 NW-005 在全部 162 阶段为 U，无明确 T 时整个 OR 为 U。

| DIRECT_CORE_OR 原子 | 保存的 U 原因 | 单元数 |
|---|---|---:|
| DEVIATION:NW-001 | no_explicit_model_build_token | 21 |
| DEVIATION:NW-002 | OS_MAJOR_UNPARSEABLE_AMBIGUOUS_OR_PARSER_DISAGREEMENT | 21 |
| DEVIATION:NW-005 | SOFTWARE_NOT_HARDWARE_FAMILY | 45 |
| DEVIATION:NW-005 | UNKNOWN_MASKED_OR_AMBIGUOUS_HARDWARE_FAMILY | 117 |

ALWAYS_NO_ALERT 与 ALWAYS_ABSTAIN 分别展示全不报警和全弃判的分母。历史适配和两常数基线的 R01 原子/子句数量明确为 0，0/0 覆盖为 NOT_EVALUABLE/null；这不同于无模型或模型大小未知。本次实际无未知模型数量。若发生该状态，冻结 R04-R1 已验收的处理保留 expected_denominator=null、value=null，不能借其他折数量；本轮没有为产生失败而额外运行真实单元。

三种学习方法的三个操作点结果完全一致。本轮没有观察到 IP、DNF2 或更宽 clean 预算带来的额外检出；仍按原定 GREEDY_OR/OP05 为主比较，不按外层结果重新定主方法。

## 配置、环境与失效范围

主方法 env-001/env-002/env-003 的攻击检出分别为 6/9、3/6、15/39（66.67%、50.00%、38.46%），对应三个 outer 折。pre/post 报警各为 0/9、0/6、0/39，所有阶段均有确定决策。这些环境的配置组成不同，差异不能直接归因为环境因果效应。三环境关联组不等于已核验的三个独立物理设备。

| 配置 ID | 攻击检出 | 精确 FTF | 决策覆盖 |
|---|---:|---:|---:|
| `w10-cdp-emulation-screen-metrics-only-v1` | 0/3 | 0/3 | 9/9 |
| `w10-cdp-emulation-timezone-only-v1` | 0/3 | 0/3 | 9/9 |
| `w6-tool-054-legacy-default-v1` | 3/3 | 3/3 | 9/9 |
| `w6-tool-055-legacy-default-v1` | 3/3 | 3/3 | 9/9 |
| `w6-tool-056-legacy-default-v1` | 9/9 | 9/9 | 27/27 |
| `w6-tool-058-legacy-default-v1` | 0/9 | 0/9 | 27/27 |
| `w9-rule-boundary-cdp-platform-only-v1` | 3/3 | 3/3 | 9/9 |
| `w9-rule-boundary-cdp-resource-pair-v1` | 0/3 | 0/3 | 9/9 |
| `w9-rule-boundary-cdp-ua-only-v1` | 3/3 | 3/3 | 9/9 |
| `w9-rule-boundary-cdp-ua-platform-desktop-v1` | 3/3 | 3/3 | 9/9 |
| `w9-rule-boundary-cdp-webdriver-only-v1` | 0/3 | 0/3 | 9/9 |
| `w9-stealth-boundary-languages-only-v1` | 0/3 | 0/3 | 9/9 |
| `w9-stealth-boundary-plugins-mime-v1` | 0/3 | 0/3 | 9/9 |
| `w9-stealth-boundary-webgl-pair-v1` | 0/3 | 0/3 | 9/9 |

6 个配置检出全部已准入攻击，另外 8 个配置合计 30 个攻击阶段未检出。`analysis/missed_attacks.jsonl` 保存其模型/折/配置与解释；选中条件在这 30 条均为 F，没有模型执行失败、缺值或弃判。该事实表明本次所选 UA 类偏差对这些材料没有报警，不能据此宣称攻击未生效、重标标签或临时补规则。完整方法×操作点×配置×环境结果见 CSV 与原始 OOF。

27 个学习模型选中相同规则，体现本轮分组结果的规则一致性；只选中 O_u 来源不构成 E/O_u/H 的因果贡献结论，来源子集重训练仍属 R06。已暴露数据与先前语义开发历史保留，本结果属于**已暴露材料上的回顾性分组评价**，不是全新盲测或未经验证的机制泛化。有限材料中 0 次 clean 报警不是总体 FPR 为 0 的保证。

## 验证、预算与交付

`VALIDATION.json` 汇总启动绑定、精确单元、39 条访问链、27 次训练约束/目标、OOF 与分层算术、来源/极性和历史只读保护。`OOF_ARITHMETIC_VALIDATION.json` 对折总计和 OOF 总体/所有分层独立核算 6,006 项指标；补充核查折/OOF 总体与分层的宏平均和条件恢复 2,340 项，及 1,620 条保存解释的三值逻辑。两类检查只读取已关闭产物。

补充审计脚本首次因历史适配记录合法省略 clause_explanations 出现 KeyError；只修正该新审计脚本的可选字段读取，失败尝试写出产物 0，第二次纯算术审计通过。该记录见 `checks/POSTPROCESS_ATTEMPTS.json`，没有修改冻结实现、模型、预测或重试真实作业。

共享真实预算账本为 `../REAL_RESEARCH_BUDGET/ledger.json`。本次使用 27/200 fit jobs，dispatcher 累计计费 36.893591209/21600 秒；余额为 173 jobs、21563.106408791 秒。37.11 秒端到端时间与预算计费范围不同，均保留。启动检查、导出、人工阅读时间不冒充模型求解时间。后续另获授权时必须延续该账本，不能重置或改用合成账本。

主要交付：`fold_models/`、`training_logs/`、`selected_rules.jsonl`、`support_statistics.jsonl`、`candidate_admission.jsonl`、`selection_trace.jsonl`、`rule_sources_aliases.jsonl`、`oof_predictions.jsonl`、`rule_events.jsonl`、`triplet_results.jsonl`、`metrics.json/csv`、`per_fold_metrics.jsonl`、`by_configuration.csv`、`by_environment.csv`、`failures/`、原始 `dispatch/`、授权/资源/预算/访问收据及各验收文件。数据导出保留模型 ID、fold、来源条件、操作点和训练成员引用，评价标签保存在独立 sidecar。

本次新增源码仅是已保存产物的审计/导出；选择器、原子语法、测量语义、划分、标签、支持度/目标/alpha/复杂度和冻结运行源码均未改。原 R01–R04-R1 保护检查与原执行时点验证分开，见 `READ_ONLY_CHECK.json`；没有运行旧 mtime/user_acceptance 验证或修改历史时间戳。

当前执行状态将 R05 标为 DONE、技术验收 PASS、外部验收 PENDING。R06 及其他步骤仍未获本次授权；未做全开发集重拟合、额外阈值搜索、来源消融、单层真实训练、前瞻确认或复采。到此停止，等待审查。
