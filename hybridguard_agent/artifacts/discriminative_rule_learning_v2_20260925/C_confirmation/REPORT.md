# V2-C：离线定型、配置留出内部评价与确认准备

`DEVELOPMENT_COMPLETE_CONFIRMATION_PENDING`，待用户审查。授权的内部工作已完成：修复 JSON null 完整性问题，冻结 B 的学习程序，完成 3 个全开发集模型和 28 次原 LOCO 拟合、保存结果复核及预声明结构探针。**独立确认未建立、未访问、未评分。** 目录名 C_confirmation 不表示确认成功。

关键结果：全开发集 W0 与 R_KEEP 的规则、所选原子、编码器及阈值相同，162 阶段训练决定也相同；R_KEEP 未补入规则。原 14 折 LOCO 中二者同为 33/54，宏检出 50.00%，新增/丢失均 0，clean 代价无新增，复杂度均 12。B 的 LOEO +18 检出增益没有在该配置留出轨道重现。保留 W0 + R_KEEP_V1 为用户已选待确认主候选，没有根据 C 结果重新选方法或放宽限制。

**工程修复与冻结。** 起始 HEAD 为用户验收的 `2d73be0695d4b11db27a83cfbe2d5f951eee4682`。先用合成夹具复现 training.json=null 和 receipt.json=null 均被旧检查误记 OK，见 [engineering_reproduction.json](engineering_reproduction.json)。现在必要对象 null/数组/字符串/数值/布尔值、必需字段/类型/状态缺失以及模型/训练/receipt/预测绑定异常都会显式记录。worker 失败覆盖所有预期 ID；原成功试验的损坏记 INTEGRITY_EXCEPTION；合法 FAILED/EMPTY 单列，汇总保留分母，不覆写原始文件。正常成功决定的回归保持不变。

实际测试命令（合成数据，无真实 fit）：

```sh
python3 -m unittest hybridguard_agent.tests.test_rule_learning_v2 hybridguard_agent.tests.test_rule_learning_v2_b_summary hybridguard_agent.tests.test_rule_learning_v2_b_retention hybridguard_agent.tests.test_rule_learning_v2_b_relations hybridguard_agent.tests.test_rule_learning_v2_c_summary hybridguard_agent.tests.test_rule_learning_v2_c_engine -v
```

[engineering_tests_02.json](engineering_tests_02.json)：实际运行 48 项、失败 0、错误 0，耗时 0.622610584 秒。覆盖原 A 的候选/别名/极性/T-F-U、train-only 编码、保存加载与标签隔离；原 B 的失败汇总、整集合 clean/覆盖约束、语义分组及匹配初始化；新增 C 的 null/类型/必需字段/绑定、B-C 同合成输入数学一致性、C 身份与关闭保护、复用初始化不隐式重训、原始字段探针转换。较早 [engineering_tests_01.json](engineering_tests_01.json) 的 50 次执行也通过，但包含被导入的 7 项重复发现；保留该记录，最终独立测试清单为 48 项，不把两次相加声称 98 项不同测试。没有重跑 B 的 39 次 fit。

只将原共享内核参数化为 B/C 身份，新增 C 入口；不改变候选、选择数学或 B 关闭保护。`retention.py` 与验收 B 提交逐字节相同，W0 SEMANTIC_SIGNAL_GROUPS_V1 映射一致。C 不加跨层关系或匹配解析原子。保留 OP05：lambda=.005、alpha=.05（整个 OR 集合 `floor(.05*N_clean_train)` 预算）、每 phase 覆盖≥.8、训练失败为零、支持度 3 完整可用三态/2 真攻击三态/1 bundle/1 环境、原家族上限、六单文字 OR 子句/复杂度≤12、分位点 .25/.5/.75 与原插值、seed=20260924 及稳定并列规则。R_KEEP 先用已计费的同训练集 W0，再按新增训练宏检出、D(S)、clean、复杂度、稳定子句 ID 的既定顺序保留信号，无保留后稀疏剪枝；不把它声称为原稀疏目标的同一优化。

[C_CONTRACT.json](C_CONTRACT.json)、[METHOD_FREEZE.json](METHOD_FREEZE.json)、[input_manifest.json](input_manifest.json)、四份 batch_spec 和 [STRUCTURAL_PROBE_PLAN.json](STRUCTURAL_PROBE_PLAN.json) 均在第一笔 C fit 前保存。runtime_versions 对应实际源码摘要，V2 运行源码另存 code_versions。每折只用自己的 train 学阈值、支持度和选择；冻结程序不表示复制 B 的某一折阈值。

**全开发集最终模型：仅训练/重代入。** 明确列出的 162 个监督阶段全部训练，各54个 attack/pre/post；100个描述阶段排除，UNKNOWN/MTC身份未改变。

| 程序 | 模型 ID | 模型文件 |
|---|---|---|
| C0__GREEDY_OR | `v2c-40ffc55faff1962cc57829ee` | [model.json](trials/V2-C__ALL_DEVELOPMENT_162__C0__GREEDY_OR__attempt01/model.json) |
| W0__GREEDY_OR | `v2c-3def521e987075a27b52e2df` | [model.json](trials/V2-C__ALL_DEVELOPMENT_162__W0__GREEDY_OR__attempt01/model.json) |
| W0__R_KEEP_V1 | `v2c-af691341a2d38032d88973b5` | [model.json](trials/V2-C__ALL_DEVELOPMENT_162__W0__R_KEEP_V1__attempt01/model.json) |

| 程序 | 训练微检出 | 训练宏检出 | pre / post / 合并 clean 报警 | 覆盖 | U / EMPTY / FAILED | F-T-F | 子句 / 复杂度 |
|---|---|---|---|---|---|---|---|
| C0 + GREEDY_OR | 24/54 (44.44%) | 42.86% | 0/54 / 0/54 / 0/108 | 162/162 | 0 / 0 / 0 | 24/54 | 1 / 2 |
| W0 + GREEDY_OR | 48/54 (88.89%) | 85.71% | 0/54 / 0/54 / 0/108 | 162/162 | 0 / 0 / 0 | 48/54 | 6 / 12 |
| W0 + R_KEEP_V1 | 48/54 (88.89%) | 85.71% | 0/54 / 0/54 / 0/108 | 162/162 | 0 / 0 / 0 | 48/54 | 6 / 12 |

三个最终模型分别从全训练集生成，第三项明确复用第二项并计一次新 fit，没有内部再次拟合 GREEDY_OR。W0 初始化已到六子句上限，R_KEEP 没有加入空间，`added_clause_ids=[]`。两份最终实例的结构/所选原子、整个编码器/阈值和当前训练决定分别比较均相同；模型 ID 因程序身份与训练记录不同而不同。证据：[final_model_comparison.json](final_model_comparison.json) 和各 training.json。训练同输出本身不证明全局逻辑等价；本轮还核对了实例结构和编码器，仍不主张两个学习程序对其他训练集等价。

W0 两份最终模型的六个 OR 条件为：既有 NW-006（desktop/script UA 或 desktop platform）、webdriver=true、MIME计数>0、Web timezone_offset>0、device_memory>2、languages列表长度>1。阈值来自本次全训练集，均是已有编码/极性，不是新谓词。C0 为 `DEVIATION:OFFDER-UA-001:POSITIVE`，Native OS 有效性锚点不等于真正的版本值比较；其解释边界沿用 A 的已保存锚点诊断。

相对 C0，W0/R_KEEP 的训练描述新增24、丢失0；相对 W0，R_KEEP 新增0、丢失0。这些不是泛化增益。48/54 不能替代 B 的 LOEO 45/54，B 的 45/54 也没有归到任何全开发集模型名下。

**配置留出内部评价：LOCO-v1。** 精确复用 R02/R08 原 14 折，12 折 train153/test9，两个较大配置折 train135/test27；三态和 bundle 零交叉。每折 train/test 配置分离，但仍共享已有环境关联组，不能叫独立设备留出或未见机制验证。[input_manifest.json](input_manifest.json) 逐折列出重叠环境。只对 W0、R_KEEP 新 fit；[C0_LOCO_REUSE.json](C0_LOCO_REUSE.json) 的14个旧模型/162条预测均核对同折、同成员、OP05、SRC-111规范核心与原测量合同后引用，未重训 C0。

| 程序 | 攻击微检出 | 配置/环境宏检出 | pre / post / 合并 clean 报警 | 决定覆盖 | U / EMPTY / FAILED | F-T-F | 每折子句 / 复杂度 |
|---|---|---|---|---|---|---|---|
| C0 + GREEDY_OR（R08保存） | 24/54 (44.44%) | 42.86% | 0/54 / 0/54 / 0/108 | 162/162 | 0 / 0 / 0 | 24/54 | 1 / 2 |
| W0 + GREEDY_OR | 33/54 (61.11%) | 50.00% | 0/54 / 0/54 / 0/108 | 162/162 | 0 / 0 / 0 | 33/54 | 6 / 12 |
| W0 + R_KEEP_V1 | 33/54 (61.11%) | 50.00% | 0/54 / 0/54 / 0/108 | 162/162 | 0 / 0 / 0 | 33/54 | 6 / 12 |

宏平均先在每配置内平均环境检出率，再平均14配置，因此不等于33/54。各模型的所选原子与子句覆盖均100%；C0为162/162，W0/R_KEEP为972/972。条件恢复分别24/24、33/33、33/33；完整F-T-F需 pre=NO_ALERT、attack=MANIPULATION_ALERT、post=NO_ALERT，所有失败仍保留原分母。

| 折 | 原配置 | C0 | W0 | R_KEEP |
|---|---|---|---|---|
| LOCO-v1-01 | `w10-cdp-emulation-screen-metrics-only-v1` | 0/3 | 0/3 | 0/3 |
| LOCO-v1-02 | `w10-cdp-emulation-timezone-only-v1` | 0/3 | 0/3 | 0/3 |
| LOCO-v1-03 | `w6-tool-054-legacy-default-v1` | 3/3 | 3/3 | 3/3 |
| LOCO-v1-04 | `w6-tool-055-legacy-default-v1` | 3/3 | 3/3 | 3/3 |
| LOCO-v1-05 | `w6-tool-056-legacy-default-v1` | 9/9 | 9/9 | 9/9 |
| LOCO-v1-06 | `w6-tool-058-legacy-default-v1` | 0/9 | 9/9 | 9/9 |
| LOCO-v1-07 | `w9-rule-boundary-cdp-platform-only-v1` | 3/3 | 3/3 | 3/3 |
| LOCO-v1-08 | `w9-rule-boundary-cdp-resource-pair-v1` | 0/3 | 0/3 | 0/3 |
| LOCO-v1-09 | `w9-rule-boundary-cdp-ua-only-v1` | 3/3 | 3/3 | 3/3 |
| LOCO-v1-10 | `w9-rule-boundary-cdp-ua-platform-desktop-v1` | 3/3 | 3/3 | 3/3 |
| LOCO-v1-11 | `w9-rule-boundary-cdp-webdriver-only-v1` | 0/3 | 0/3 | 0/3 |
| LOCO-v1-12 | `w9-stealth-boundary-languages-only-v1` | 0/3 | 0/3 | 0/3 |
| LOCO-v1-13 | `w9-stealth-boundary-plugins-mime-v1` | 0/3 | 0/3 | 0/3 |
| LOCO-v1-14 | `w9-stealth-boundary-webgl-pair-v1` | 0/3 | 0/3 | 0/3 |

所有配置的 pre/post 报警均0；逐配置/逐折完整分母、覆盖、弃判、失败和 FTF 见 [metrics_by_configuration.csv](metrics_by_configuration.csv)、[metrics_by_fold.csv](metrics_by_fold.csv)，整体见 [metrics.json](metrics.json)。[gained_lost.json](gained_lost.json) 保留攻击 ID 与逐配置新增/丢失；[stage_comparison.jsonl](stage_comparison.jsonl) 保留完整阶段对应。

R_KEEP 相对同轨 W0 新增0、丢失0、新clean报警0，复杂度差0。相对C0，两项均新增9、丢失0，全部来自 `w6-tool-058-legacy-default-v1`；代价是复杂度每折2→12。这是当前已暴露材料上的有限对照，不推出单层/跨层或来源的一般优越性。

**B 的收益是否重现。** 原B的LOEO事实单列如下，未重算/覆盖原预测：

| 保存的LOEO程序 | 微检出 | 宏检出 | pre / post | 相对W0新增/丢失 | 三折复杂度 |
|---|---|---|---|---|---|
| C0 | 24/54 | 42.86% | 0/54 / 0/54 | — | 2 / 2 / 2 |
| W0 | 27/54 | 35.71% | 0/54 / 0/54 | 0 / 0 | 12 / 12 / 2 |
| W0 + R_KEEP_V1 | 45/54 | 78.57% | 0/54 / 0/54 | +18 / -0 | 12 / 12 / 12 |

证据引用 [B CANDIDATE_SELECTION.json](../B_development/CANDIDATE_SELECTION.json)、[B REPORT.md](../B_development/REPORT.md)。B的增益全部出自第三个留出环境关联组，那里稀疏初始化尚有空位。C中全训练集及14个LOCO初始化全部已达六子句，保留轨迹都没有新增；逐实例记录见 [loco_model_comparison.json](loco_model_comparison.json)。因此本轮没有检验到 R_KEEP 相对W0的配置留出额外收益，也不能把无额外收益解释为两个程序全局等价或放宽上限必有收益。

LOCO的resource-pair、webdriver-only、languages-only、plugins-mime四配置各0/3，而B候选LOEO各3/3；两种留出方式训练成员不同，观察到的12条差异不归因为单一机制。LOCO未重新挑参数、改支持度或追补规则；全部21条LOCO漏检以及全训练集6条未检出保留。两轨材料重叠，不相加成108次独立攻击；D(S)分组的唯一因果作用仍未证实。

**合法变化风险与合成边界。** 在真实 fit 前声明18情景，三模型54个预期响应项；52项产生决定，C0只有一个子句，因此两个需要“两子句同时状态”的原子探针明确N/A。原始字段层15情景经既有 extract_atom/control_input/规范投影/冻结编码转换；另3情景仅检查预计算原子逻辑。全部标 `SYNTHETIC_SEMANTIC_OR_STRUCTURAL_PROBE`，没有附真实clean/attack标签，没有并入108控制/54攻击，没有真实FPR或泛化区间。

A=MANIPULATION_ALERT，N=NO_ALERT，U=INSUFFICIENT_EVIDENCE，F=FAILED。

| 情景 | 输入层 | C0 | W0及R_KEEP |
|---|---|---|---|
| `baseline_partial_android` | 原始字段 | N | N |
| `higher_memory` | 原始字段 | N | A |
| `higher_cpu` | 原始字段 | N | N |
| `multiple_languages` | 原始字段 | N | A |
| `changed_language_order` | 原始字段 | N | A |
| `pdf_mime_capability` | 原始字段 | N | A |
| `ua_brand_suffix` | 原始字段 | N | N |
| `desktop_request_ua` | 原始字段 | A | A |
| `authorized_webdriver` | 原始字段 | N | A |
| `timezone_minutes_west` | 原始字段 | N | A |
| `timezone_minutes_east` | 原始字段 | N | N |
| `missing_memory` | 原始字段 | N | U |
| `invalid_measurement_status` | 原始字段 | N | F |
| `missing_native_anchor` | 原始字段 | U | N |
| `invalid_native_anchor_status` | 原始字段 | F | N |
| `one_unknown_all_other_literals_false` | 预计算原子 | U | U |
| `true_or_unknown` | 预计算原子 | N/A | A |
| `failed_even_with_true` | 预计算原子 | N/A | F |

[structural_responses.jsonl](structural_responses.jsonl) 每项保存改变字段、保持一致的关联字段、场景目的、决定、触发子句、原子解释及合成/可实现性限制。内存夹具同时改变Web近似值8和Native7.5，语言顺序变化同步首选项，UA定制同步Host设置，时区正负符号与Native分钟/ID一致；未臆造Native核数或MIME成员列表。Android上的desktop请求UA是拟议内容协商场景，不是在声明x86物理硬件；相关真实WebView支持尚未验证。

已证实的是这些冻结函数对这些夹具的响应：高内存、更多语言、MIME>0、获准webdriver、Web分钟西偏移+60均触发独立OR条件；Web偏移-480不触发该时区条件；desktop请求UA还触发C0。核数8和UA品牌后缀在本夹具中不触发，不能据此保证所有核数/UA变化安全。缺失内存使W0/R_KEEP弃判，缺失Native有效性锚点使C0弃判；非法测量状态保持FAILED。原子级T或U仍报警，某选中原子执行失败即使另一个为T仍FAILED，符合原不短路失败语义，不作为修改模型的理由。

真实观测仅包括已暴露材料上保存的108个pre/post控制无报警；这些控制不能代表上述尚未采集的全部合法变化。结构报警是正常侧适用边界风险，不是实际误报发生率；0/108也不是总体零FPR。下一步应按 [CONFIRMATION_PLAN.md](CONFIRMATION_PLAN.md) 优先覆盖这些真实正常变化，而非把合成探针包装成新数据或用报警重裁决其标签。

**计费与可复核性。** 四批3/12/12/4，共31次实际fit（3最终、28LOCO），失败0、重试0。真实worker计费 13.577589837136 秒，包含启动/输入、编码/支持/选择、保存加载、预测与评价；不是本次开发总墙钟时间。V1/R09/A/B先前116fits/140.589167123549秒未归零；当前累计147fits/154.166756960685秒，全研究剩余53fits/21445.833243039317秒。C未用5次工程重试额度不转成新实验授权。

[linked_budget_ledger.json](linked_budget_ledger.json)、[trials.jsonl](trials.jsonl) 保存预留、尝试、核销与关闭；全部原始输出保留。31个新模型、810条新保存预测（486训练重代入+324LOCO）全部通过保存加载决定一致性，810不是独立样本数；旧C0的162条预测只引用。[execution_verification.json](execution_verification.json) 核对每job一次fit、精确训练成员及“冻结→打开评价特征→关闭预测→加入评价标签”的顺序；全训练集的标签原本就是训练输入，已明确标重代入，不伪装标签盲态。[trial_integrity_summary.json](trial_integrity_summary.json) 为31/31 OK。[model_manifest.json](model_manifest.json) 列31个新模型和14个旧C0引用、规则/复杂度及训练证据；同目录各模型包含编码器。

合成测试、固定模型52条实际探针决定与只读汇总另记 [nonfit_activity.json](nonfit_activity.json)，未隐藏参数学习。默认复核入口只读，不拟合、不重新生成真实预测：

```sh
python3 -m hybridguard_agent.research.rule_learning_v2.c_experiment
```

新训练入口要求明确C身份/授权、登记job和预留；单次worker claim、已执行batch保护及阶段关闭保护阻止重复执行。当前运行源码与合同摘要一致；V1源码/配置/冻结结果与A/B结果没有改动，270个原有非本轮Git状态条目仍保留。工程和收束说明见 [postrun_engineering_note.json](postrun_engineering_note.json)、[verification.json](verification.json)。

**可成立的结论与尚缺事项。** 已修复null完整性漏洞并通过相关回归；按冻结程序可复现地产生待确认模型；同池R_KEEP的B环境留出收益未扩展为本次配置留出额外收益；最终阈值存在必须用真实正常材料检查的适用范围。当前不能声称独立盲测通过、跨层优于单层、未见机制泛化、真实总体零FPR、D(S)唯一因果解释或生产安全性。

独立确认尚缺另行授权的真实材料与标签、实际独立设备/环境交叉覆盖、效果/恢复及合法性证据，以及用户预先决定的检出/报警/覆盖/失败目标、样本量和停止合同。计划与 [confirmation_record_template.json](confirmation_record_template.json) 已准备，但没有开封或采集。内部必需工作完成，确认仍PENDING；[completion.json](completion.json) 与当前调度状态一致。停止等待用户审查，不因负结果重开B，不进入R10/V3，不自动commit/push/PR。

建议 commit message：`research: finalize V2-C models and internal configuration holdout evaluation`
