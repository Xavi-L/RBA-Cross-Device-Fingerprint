**固定 162 条历史监督材料：候选求值与训练前支持度报告**

已完成一次真实求值。语言首项关系得到 **3 T、159 F、0 U、0 FAILED**：保留旧长度条件的 3 个 T，另有 9 条原 attack 记录由旧 T 变为新 F，没有旧 F→新 T。108 条 clean 的响应均保持 F，因此本批材料没有显示额外检出或 clean 响应减少。9 条减少响应都属于 `w6-tool-058-legacy-default-v1`，三个环境各 3 条；保留的 3 条来自 env-003 的 `w9-stealth-boundary-languages-only-v1`。

webdriver legacy 得到 **18 T、0 F、144 U、0 FAILED**。其 T 集合与旧 W03 严格布尔 true 条件完全一致，其余 144 个旧 F 全部改为 U。这是对历史非 true 投影歧义的明确表达，未增加 T 集合所携带的判别信息；108 条 clean 全 U，不能称为正常判定或误报减少。

按冻结支持规则，语言正向条件在 LOEO 前两折具备最低支持，留出 env-003 的第三折不具备。前两折使用的是同一批 3 组三态，不能累加为 6 个独立支持。原语法允许的语言负向条件在三折都满足最低门槛，但全部 train clean 都为 T，最低支持通过本身不证明检测价值。webdriver 正反两种极性均因完整可用三态为零而不具备支持。

**建议暂不启动新的 fit。** 保留语言语义修正及 webdriver 状态/诊断模块，结束本轮固定函数对照，等待人工审阅；当前没有足够的新增响应收益或跨环境正向支持来支撑立即开展选择器对照。没有新增 T 不否定语义修正的解释价值，也不能据此断言未来组合绝无价值。本轮未检验组合或模型选择。

| 决策字段 | 本轮结论 |
| --- | --- |
| status | CANDIDATE_EVALUATION_COMPLETE_PENDING_REVIEW |
| execution_complete | true |
| language_signal_assessment | NO_NEW_TRUE_RESPONSES_VS_FIXED_LENGTH_REFERENCE；3 个旧 T 保留，9 个 attack T→F，clean 不变；正向支持局限于单环境/单配置/单 bundle。 |
| webdriver_information_overlap | SAME_TRUE_SET_NONTRUE_TO_UNKNOWN；18 个 T 完全重合，144 个 F→U。 |
| train_support_assessment | LANG POSITIVE：2/3 折满足；LANG NEGATIVE：3/3 折满足但 train clean 全 T；WEBDRIVER 两极性：0/3 折满足。仅最低支持诊断。 |
| recommended_next_action | NO_NEW_FIT_NOW；保留语义与诊断实现，审阅当前结果，本轮停止。 |

**执行身份、范围与分析顺序**

起始 HEAD 为 `3514a664e60917a66a614f3ca8aa635fcc3e7b7f`，已确认包含模块提交 `1e34677f307fc33b0552dde0dc6a14c77018cb66`、接入审计提交 `dcf60952de9292d658eaffbae6e723da9bc59a53` 与来源地址补齐提交。候选语义代码、转接器和接入登记与相应批准版本一致。本地原始子仓库固定在 `9698e8dfeb450094d99c46bdcff15283c995e3b3`，沿用已登记的 38 个必要来源路径，没有切换版本或重做总体来源调查。

权威范围为 `hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/C_confirmation/input_manifest.json` 的 `supervised_ids`。与旧接入清单核对为完全一致的 162 个唯一 ID；事后连接元数据得到 clean_pre/attack/clean_post 各 54 条。没有加入描述阶段、MTC、UNKNOWN 控制或新设备记录。

`EVALUATION_CONTRACT.json` 在 2026-09-28 11:46:25.866456 UTC 登记，早于 11:46:40.860881 UTC 开始的真实求值。仅保存本轮候选、转接代码、来源登记、ID 权威、固定参考与支持定义等 28 个必要文件的摘要，未进行全仓库哈希。旧 `AUDIT_CONTRACT.json` 和历史状态保持原样。

真实进程复用一个 `InputAudit`，每条记录分别调用 `load_input(..., "LANGUAGE")` 和 `load_input(..., "WEBDRIVER_LEGACY")`。只将最小 payload 与实际 loader 提供的外部 SourceBinding 传入已批准函数；语言采用默认模式，webdriver 显式采用 `legacy_projection_v1`，两个候选版本均为 1.0.0。未调用 raw 模式。

候选及参考逐条结果于 11:46:41.373606 UTC 前保存并关闭，再运行独立 analyze 步骤连接 phase、label、config、environment 和 triplet 元数据。loader 为来源定位会读取含评价信息的旧登记，且这批材料此前已经暴露；这里是本批执行前登记和调用参数隔离，不是盲评。候选调用没有接收 ID、标签、阶段、配置、工具或旧预测。

**完整分母与原标注阶段响应**

T 仅表示固定候选条件成立，F 表示条件不成立；U 表示无法据此确定，FAILED 表示失败。以下比例均以该组全部预期记录为分母，不排除 U。每行 T+F+U+FAILED=N。合并 clean 与两个 clean 子组是不同展示口径，不能重复相加。

| 候选 | 分组 | N | T/F/U/FAILED | 条件成立 T/N | 有效 T/F 占比 | U/N | FAILED/N |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 语言 | 全体 | 162 | 3/159/0/0 | 3/162 | 162/162 | 0/162 | 0/162 |
| 语言 | clean_pre | 54 | 0/54/0/0 | 0/54 | 54/54 | 0/54 | 0/54 |
| 语言 | attack | 54 | 3/51/0/0 | 3/54 | 54/54 | 0/54 | 0/54 |
| 语言 | clean_post | 54 | 0/54/0/0 | 0/54 | 54/54 | 0/54 | 0/54 |
| 语言 | 合并 clean | 108 | 0/108/0/0 | 0/108 | 108/108 | 0/108 | 0/108 |
| webdriver legacy | 全体 | 162 | 18/0/144/0 | 18/162 | 18/162 | 144/162 | 0/162 |
| webdriver legacy | clean_pre | 54 | 0/0/54/0 | 0/54 | 0/54 | 54/54 | 0/54 |
| webdriver legacy | attack | 54 | 18/0/36/0 | 18/54 | 18/54 | 36/54 | 0/54 |
| webdriver legacy | clean_post | 54 | 0/0/54/0 | 0/54 | 0/54 | 54/54 | 0/54 |
| webdriver legacy | 合并 clean | 108 | 0/0/108/0 | 0/108 | 0/108 | 108/108 | 0/108 |

语言 attack 条件成立率为 3/54（5.56%），webdriver 为 18/54（33.33%）。这些是原标注阶段上的固定条件响应，不是新模型 TPR/FPR、准确率或替换模型后的成绩。没有报告排除 U 后的条件成立率。

语言无 U/FAILED；webdriver 的 144 个 U 首要原因全部为 `LEGACY_NONTRUE_PROJECTION_AMBIGUOUS`，按阶段分别为 54、36、54。其来源绑定有效，没有因来源错误、缺失或异常产生 U/FAILED。非互斥诊断中同名原因也出现 144 次，不再加到独立记录数。其他诊断及原始 SemanticCell 编码保存在逐条结果中。

**两个固定旧谓词的逐条对照**

精确复用已保存的 162 条记录中两个 singleton clause 的状态：`REFERENCE_LANG_LENGTH_GT1` 对应 `CONTROL:app.web_data.navigator_layer.languages:LE:1.0:NEGATIVE`；`REFERENCE_WEBDRIVER_STRICT_TRUE` 对应 `CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True:POSITIVE`。

缓存路径为 `hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/C_confirmation/trials/V2-C__ALL_DEVELOPMENT_162__W0__GREEDY_OR__attempt01/predictions.jsonl`。其 ID、source_rows、缓存身份、单字面量 clause、原子身份和极性均已核对；每条参考保存精确行引用、原子说明与缓存身份。仅提取这两个谓词状态，未使用模型决策或调用旧模型。

旧语言操作数要求 observed/observed_value、列表类型且各元素为非空字符串；空列表长度为零。冻结阈值为 1.0，取 <=1.0 的负向字面量，U 保持 U。旧 webdriver 使用 observed/observed_value 与严格 bool 类型门控后比较 true。定义、代码身份与缓存模型 `v2c-3def521e987075a27b52e2df` 登记在执行合同中。这不代表整个旧长度候选族。

| 候选 | 旧→新 | 全体 | clean_pre | attack | clean_post |
| --- | --- | --- | --- | --- | --- |
| 语言 | F→F | 150 | 54 | 42 | 54 |
| 语言 | T→T | 3 | 0 | 3 | 0 |
| 语言 | T→F | 9 | 0 | 9 | 0 |
| 语言 | F→T | 0 | 0 | 0 | 0 |
| 语言 | 转为 U 或 FAILED | 0 | 0 | 0 | 0 |
| webdriver | T→T | 18 | 0 | 18 | 0 |
| webdriver | F→U | 144 | 54 | 36 | 54 |
| webdriver | 其他变化 | 0 | 0 | 0 | 0 |

语言 9 个旧 T→新 F 的模块原因均为 `FIRST_TAG_EQUAL`：列表长度大于一，但首项关系没有不一致；保留的 3 个 T 原因为 `FIRST_TAG_DIFFERS`。这是对不同语义问题的区分，不能把原 attack 的响应减少包装为正常误报收益，也不更改原标签。

| 旧→新 | opaque_id | 阶段 | 配置 | 环境 |
| --- | --- | --- | --- | --- |
| T->F | sample-0bffc108cdcd46498c072fd18758b023 | attack | w6-tool-058-legacy-default-v1 | env-001 |
| T->F | sample-22ed5502a1a24385bef4cb91046e3683 | attack | w6-tool-058-legacy-default-v1 | env-001 |
| T->F | sample-24e48e8890bc4126b5935b155cc639ee | attack | w6-tool-058-legacy-default-v1 | env-002 |
| T->F | sample-497f3bba454d455d81c1a533d98ac074 | attack | w6-tool-058-legacy-default-v1 | env-003 |
| T->F | sample-6d40e867146642de955768a0ed8200b3 | attack | w6-tool-058-legacy-default-v1 | env-003 |
| T->F | sample-7e19b3e0cd3542c99cbf9a8922f31614 | attack | w6-tool-058-legacy-default-v1 | env-002 |
| T->F | sample-86d5cc918c2e4806811a1b6a8083f3c1 | attack | w6-tool-058-legacy-default-v1 | env-002 |
| T->F | sample-9b52b2ee157c430d9d6d65e68f69d56a | attack | w6-tool-058-legacy-default-v1 | env-003 |
| T->F | sample-f5fa5cb164b64da88065e6b242e53e43 | attack | w6-tool-058-legacy-default-v1 | env-001 |
| T->T | sample-2b9de382d01b49d7a19a13821e13f5a5 | attack | w9-stealth-boundary-languages-only-v1 | env-003 |
| T->T | sample-437a6b1693cf4be99d0aa2e82bd219e5 | attack | w9-stealth-boundary-languages-only-v1 | env-003 |
| T->T | sample-698f3fcbada2411da6d5ef701a65b419 | attack | w9-stealth-boundary-languages-only-v1 | env-003 |

旧 F→新 T 的 ID 集为空，转为 U/FAILED 的语言 ID 集也为空。全部逐 ID 交叉分组（包括 webdriver 的 144 个 F→U）保存在 `SUMMARY.json.comparisons.*.ids_by_transition`，不另复制完整输入。

**配置与环境的描述性分布**

下表保留实际样本量；四状态顺序均为 T/F/U/FAILED。每个配置及环境的 clean_pre、attack、clean_post 完整四状态计数和 k/n 另见 `SUMMARY.json.candidates.*.by_config` 与 `by_environment`。各组语言 clean 全 F，webdriver clean 全 U。未计算宏平均，未将大小不同的配置等同于等样本权重。

| 配置 | N | 语言 T/F/U/FAILED | 语言 attack T/N | webdriver T/F/U/FAILED | webdriver attack T/N |
| --- | --- | --- | --- | --- | --- |
| w10-cdp-emulation-screen-metrics-only-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w10-cdp-emulation-timezone-only-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w6-tool-054-legacy-default-v1 | 9 | 0/9/0/0 | 0/3 | 3/0/6/0 | 3/3 |
| w6-tool-055-legacy-default-v1 | 9 | 0/9/0/0 | 0/3 | 3/0/6/0 | 3/3 |
| w6-tool-056-legacy-default-v1 | 27 | 0/27/0/0 | 0/9 | 9/0/18/0 | 9/9 |
| w6-tool-058-legacy-default-v1 | 27 | 0/27/0/0 | 0/9 | 0/0/27/0 | 0/9 |
| w9-rule-boundary-cdp-platform-only-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w9-rule-boundary-cdp-resource-pair-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w9-rule-boundary-cdp-ua-only-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w9-rule-boundary-cdp-ua-platform-desktop-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w9-rule-boundary-cdp-webdriver-only-v1 | 9 | 0/9/0/0 | 0/3 | 3/0/6/0 | 3/3 |
| w9-stealth-boundary-languages-only-v1 | 9 | 3/6/0/0 | 3/3 | 0/0/9/0 | 0/3 |
| w9-stealth-boundary-plugins-mime-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |
| w9-stealth-boundary-webgl-pair-v1 | 9 | 0/9/0/0 | 0/3 | 0/0/9/0 | 0/3 |

| 环境 | N | 语言 T/F/U/FAILED | 语言 attack T/N | webdriver T/F/U/FAILED | webdriver attack T/N |
| --- | --- | --- | --- | --- | --- |
| env-001 | 27 | 0/27/0/0 | 0/9 | 6/0/21/0 | 6/9 |
| env-002 | 18 | 0/18/0/0 | 0/6 | 3/0/15/0 | 3/6 |
| env-003 | 117 | 3/114/0/0 | 3/39 | 9/0/108/0 | 9/39 |

**明确三态 ID 配对**

按原权威 `(bundle_id, triplet_id)` 分组，在每组内依据明确 phase 取 clean_pre→attack→clean_post；没有按邻接或排序猜测配对。两个候选各为 54 个完整三态、162 条记录，无重复或配对缺口。逐组 ID、各阶段 opaque_id、状态及模式保存在 `SUMMARY.json.candidates.*.triplets.groups`。

| 候选 | F→T→F | 全 F | 含 U | 含 FAILED | 其他实际模式 |
| --- | --- | --- | --- | --- | --- |
| 语言 | 3 | 51 | 0 | 0 | 无 |
| webdriver legacy | 0 | 0 | 54 | 0 | 含 U 中：36 个 U→U→U，18 个 U→T→U |

**原三折 LOEO 的训练成员支持度**

折定义使用 `hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1/SPLIT_MANIFEST.json` 中 `split_id=LOEO-v1` 的三个原折。支持定义来自同一 R04 snapshot 的 `hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json#support`，实现核对 frozen `selector.py:99–120,151–155`。未调用学习或选择入口。

冻结门槛为：完整三态三个阶段均属于 T/F 的可用三态数 ≥3；其中 attack 字面量为 T 的三态 ≥2；这些支持来自 ≥1 bundle、≥1 environment。配置数照实记录但无单独最低门槛。定义并不要求用于 attack T 支持的三态必须为 F→T→F。训练 FAILED 会另行阻止准入。

冻结语法允许 POSITIVE 和 NEGATIVE，执行前已登记两种极性的诊断。NEGATIVE 只交换 T/F，保留 U/FAILED；没有从结果选择某一极性，也没有新增语义函数调用。所有统计只读该折 train 状态；test 成员保留作身份核对，不参与支持资格。完整成员、逐条件实际值/门槛/不满足原因及支持三态 ID 保存在 `TRAIN_SUPPORT_DIAGNOSTIC.json`。

| 折 | 留出环境 | train 记录 | test 记录 | train 完整三态 |
| --- | --- | --- | --- | --- |
| LOEO-v1-01 | env-001 | 135 | 27 | 45 |
| LOEO-v1-02 | env-002 | 144 | 18 | 48 |
| LOEO-v1-03 | env-003 | 45 | 117 | 15 |

| 折 | 候选 | 极性 | 可用三态 | 可用三态中 attack T | 支持 bundle/env/config | 最低支持 | train clean 字面量 T/N |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LOEO-v1-01 | 语言 | POSITIVE | 45 | 3 | 1/1/1 | 满足 | 0/90 |
| LOEO-v1-01 | 语言 | NEGATIVE | 45 | 42 | 14/2/12 | 满足 | 90/90 |
| LOEO-v1-01 | webdriver | POSITIVE | 0 | 0 | 0/0/0 | 不满足 | 0/90 |
| LOEO-v1-01 | webdriver | NEGATIVE | 0 | 0 | 0/0/0 | 不满足 | 0/90 |
| LOEO-v1-02 | 语言 | POSITIVE | 48 | 3 | 1/1/1 | 满足 | 0/96 |
| LOEO-v1-02 | 语言 | NEGATIVE | 48 | 45 | 15/2/13 | 满足 | 96/96 |
| LOEO-v1-02 | webdriver | POSITIVE | 0 | 0 | 0/0/0 | 不满足 | 0/96 |
| LOEO-v1-02 | webdriver | NEGATIVE | 0 | 0 | 0/0/0 | 不满足 | 0/96 |
| LOEO-v1-03 | 语言 | POSITIVE | 15 | 0 | 0/0/0 | 不满足 | 0/30 |
| LOEO-v1-03 | 语言 | NEGATIVE | 15 | 15 | 5/2/3 | 满足 | 30/30 |
| LOEO-v1-03 | webdriver | POSITIVE | 0 | 0 | 0/0/0 | 不满足 | 0/30 |
| LOEO-v1-03 | webdriver | NEGATIVE | 0 | 0 | 0/0/0 | 不满足 | 0/30 |

语言正向第三折可用三态 15≥3，但 attack T=0<2，bundle=0<1、environment=0<1；其余两折各有同一批 3 个支持三态，来自 env-003、`20260824_api36_stealth_languages_only_v1` 单 bundle/单配置。语言负向虽然三折最低支持均满足，clean 90/90、96/96、30/30 全为 T，不能据此声称适合独立报警，也不能将正向第三折失败误写成整个带极性候选池都无准入支持。

webdriver 每折两种极性的可用三态、其中 attack T 支持、支持 bundle 和 environment 均为零，四项最低门槛均未满足。即使部分单条 attack 为 T，也因 clean 为 U 而不能形成满足完整可用要求的支持三态。表中的 clean T=0 保留全部 clean 分母，实际全部为 U，绝非已确认的正常结果。

三折成员与原清单逐项相同且 train/test 不相交；没有基于 test 结果判断支持。支持最低门槛通过与 selector 选择、clean 预算可行性及未来模型成绩分别是不同问题，后面三项均为 NOT_EVALUATED。未新建划分、运行 LOCO 或内部交叉验证。

**执行计数与有限测试**

| 项目 | 实际数量 |
| --- | --- |
| 独立历史记录 | 162 |
| 候选结果位置 / 实际新候选调用 | 324 / 324（每候选 162） |
| 固定参考结果位置 / 缓存复用 | 324 / 324 |
| 固定参考实际新计算 | 0 |
| runner 失败 / 参考读取失败 | 0 / 0 |
| 额外真实候选重试 | 0 |
| fit / model_prediction / new_collection | 0 / 0 / 0 |

所有候选结果均记录 `candidate_invoked=true`、attempt=1、origin=`CANDIDATE_RETURN`，没有候选返回 FAILED。执行器前置失败与模块返回失败分别编码；单条异常不会删除预期位置。真实执行没有工程失败、修复或重试。

最终相关测试：**92 个独立 TestCase 方法 PASS**，0 failure、0 error、0 skip。原语义模块 34、输入转接 21、接入审计 14、新执行器/汇总 12、新支持度 11。另有 263 次 subtest invocation，不重复加到独立测试数；原 24 个规范示例沿用既有测试，没有改写。

新增测试使用人工输入或临时文件，覆盖 ID/候选组合完整性、实际函数调用、缺文件/坏 JSON/模块失败后继续、U 与 FAILED 全分母、标签参数隔离、结果关闭后分析、明确三态 ID 配对、train-only 支持、拒绝覆盖、分析不重求值及无 fit/predict/raw 调用。未破坏真实记录，也未运行全库实验。

实际命令均退出 0（工作目录为仓库根，Python 实际解析为 `/opt/homebrew/opt/python@3.14/bin/python3.14`）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_candidate_evaluation/run_checks.py --output deliverables/rule_semantics_candidate_evaluation/TEST_RESULTS.json
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_candidate_evaluation/evaluate_candidates.py evaluate
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_candidate_evaluation/evaluate_candidates.py analyze --output-dir deliverables/rule_semantics_candidate_evaluation
```

第二条仅执行过一次。第三条基于已关闭的结果和旧评价元数据生成本轮汇总。已有产物时不要重复 evaluate；输出使用排他创建并拒绝覆盖。若需只读再分析，可执行以下入口，仅向 stdout 输出，且不会调用候选：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_candidate_evaluation/evaluate_candidates.py analyze
```

`TEST_RESULTS.json` 保存完整最终命令、逐方法状态和计数；`EXECUTION.json` 保存真实调用及关闭时点。测试中的合成函数调用不属于 324 次真实历史记录调用。

**解释边界与交付范围**

这是固定函数在已暴露开发材料上的描述性实证检查。162 是不同记录数，不是 162 台设备或 162 个独立统计观测；同一三态、bundle、配置、环境间存在依赖。54 个 attack 的原标注不能扩大成普遍攻击真值；clean 标签仅表示记录表面上没有声明的干预，也不证明普遍正常性。

语言 clean 0/108 不证明正常 App 总体零误报；webdriver clean 108/108 U 更不能用于此类主张。语言的首项差异提供比列表长度更具体的同层一致性解释，但本批没有旧长度条件之外的新 T，且全部正向支持集中于一个环境。本次固定对照未估计独立确认性能、跨设备泛化或正常 App 总体分布。

本轮只新增当前交付目录与两个定向测试文件。没有改写已批准候选模块、转接器、旧模型、原标签、来源审计或历史指标；没有提交、推送、创建 PR、训练、采集或开启独立确认。

| 产物 | 内容 |
| --- | --- |
| EVALUATION_CONTRACT.json | 本批执行前固定 ID、实现/输入身份、两个参考和支持定义 |
| CANDIDATE_RESULTS.jsonl | 324 个候选位置、真实 SemanticCell、来源引用、输入摘要与调用记录 |
| REFERENCE_RESULTS.jsonl | 324 个独立固定参考位置及缓存出处 |
| EXECUTION.json | 真实执行时间和调用/重试计数 |
| SUMMARY.json | 完整分母、原因、配置/环境、逐 ID 对照与三态明细 |
| TRAIN_SUPPORT_DIAGNOSTIC.json | 原 LOEO 三折、两候选、两极性的 12 项 train-only 诊断 |
| TEST_RESULTS.json | 最终 92 个独立测试方法及单独 subtest 计数 |
| evaluate_candidates.py / support_diagnostic.py / run_checks.py | 最小执行/只读分析、纯支持计数、定向测试入口 |
| REPORT.md | 描述性结果、单独研究决策字段、证据边界 |
| hybridguard_agent/tests/test_rule_semantics_candidate_evaluation.py | 执行器与汇总测试 |
| hybridguard_agent/tests/test_rule_semantics_train_support.py | 支持边界与 train-only 测试 |

建议 commit message：`research: evaluate fixed semantic candidates and diagnose train support`。本轮停在 `CANDIDATE_EVALUATION_COMPLETE_PENDING_REVIEW`，未执行该提交。
