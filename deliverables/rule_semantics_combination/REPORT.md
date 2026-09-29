# 语言首项增加与 webdriver 替换的组合实验

**组合结果为 42/54（77.78%），与单独替换 webdriver 的 162 条留出决策完全相同，没有观察到额外收益或损失。** 相对原 R_KEEP 或仅增加语言条件的 45/54，仍少检出 3 条 webdriver-only 边界攻击。语言-only 的 3 条攻击仍被检出。

本轮已完成 3 次新 GREEDY 初始化、3 次 R_KEEP 训练和 162 次留出预测，零失败、零重试。状态为 `COMPLETE_PENDING_REVIEW`；固定组合实验已完成，停止继续调参。

## 1. 组合的确切含义

按用户要求，候选池同时应用两项变化：**保留完整旧语言长度家族，增加语言首项关系；移除旧 webdriver EQ:True 条件，加入 webdriver legacy 状态条件。** 两个新候选由选择器自行决定是否使用，没有强制入选，也没有新造一个 AND 谓词。

新组合标识为 `LANG_ADD_WD_REPLACE`，独立研究身份为 `rule-semantics-combination-v1 / RSR_COMBINATION`。新语言仍属于 `language_preferences`，与旧长度条件共享字段家族；新 webdriver 属于 `automation_flag`。同一信号的新旧表达不增加独立信号组数量。

本轮比较的是这种候选池设计对固定 R_KEEP 的实际影响。“保留旧长度并增加首项条件”在此前实验中优于“删除旧长度再替换”，不等于新首项条件已经带来检出增益；此前 LANG_ADD 的预测与原 R_KEEP 相同。本轮也未将正常语义适用性等同于攻击判定能力。

## 2. 执行前固定的范围

协议见 [CONTRACT.json](CONTRACT.json)，登记于 `2026-09-29T12:48:24.518359+00:00`，在任何本轮真实 fit 之前。起始提交为 `e0755e1fce69d3f49527ad7d7ec84ec3df8df4c6`；本轮代码及结果尚未提交，执行代码身份在协议中登记。

- 固定原 162 条监督记录：54 attack、54 clean_pre、54 clean_post，组成 54 个已准入 triplet。
- 原三折 LOEO：训练/留出记录为 135/27、144/18、45/117，留出环境分别为 env-001、env-002、env-003。
- 保持原 OP05、支持要求、极性、家族限制、六子句/复杂度 12 上限、信号分组和 R_KEEP 排序规则。
- 两个新候选均复用已保存的 1.0.0 结果，webdriver 使用 `legacy_projection_v1`；新候选求值 0 次、新采集 0 次。
- 三个对照 BASE、LANG_ADD、WD_REPLACE 直接读取 [上一轮 R_KEEP 实验](../rule_semantics_rkeep_retraining/REPORT.md) 保存的模型与预测，对照重训次数为 0。

组合池此前没有自己的初始模型，不能将 WD_REPLACE 的初始模型换个名称冒充同池。本轮先对该组合做三折 GREEDY 训练，保存其完整候选池、支持、编码器和选中规则；再对同折模型执行 R_KEEP。GREEDY 阶段只作训练初始化，不读取留出特征，也不产生留出预测。

R_KEEP 仍从初始集合出发，只添加带来正的加权语义信号覆盖增量 D 的条件，允许宏检出增量为 0；保持初始攻击检出、原 clean 预算、支持和覆盖约束，不删除/交换初始化规则，不进行事后稀疏剪枝。

新代码为 `hybridguard_agent/research/rule_semantics_combination.py`，运行器为 [run_experiment.py](run_experiment.py)。旧代码、协议和结果未修改。每次仅打开本折训练记录与缓存单元；R_KEEP 模型保存并重载冻结后才读取留出输入，全部预测关闭后才接入评估标签。

## 3. 与三个已保存对照的结果

| 方案 | attack 检出 | 配置/环境宏检出 | clean 报警 | 决策覆盖 |
| --- | ---: | ---: | ---: | ---: |
| 原 R_KEEP / BASE，复用 | 45/54 = 83.33% | 11/14 = 78.57% | 0/108 | 162/162 |
| 仅增加语言首项 / LANG_ADD，复用 | 45/54 = 83.33% | 11/14 = 78.57% | 0/108 | 162/162 |
| 仅替换 webdriver / WD_REPLACE，复用 | 42/54 = 77.78% | 10/14 = 71.43% | 0/108 | 162/162 |
| **增加语言首项＋替换 webdriver，本轮新增** | **42/54 = 77.78%** | **10/14 = 71.43%** | **0/108** | **162/162** |

相对 BASE 和 LANG_ADD，组合的 attack 检出率下降 5.56 个百分点、宏检出下降 7.14 个百分点；新增检出 0 条、丢失 3 条。三条均为第三折 env-003 的 `w9-rule-boundary-cdp-webdriver-only-v1` attack，从 `MANIPULATION_ALERT` 变为 `NO_ALERT`。

相对 WD_REPLACE，三折最终规则集合逐项相同，所有 162 条的 decision 和 logical state 均相同，新增/丢失检出 ID 均为空。语言-only 配置仍为 3/3，保存的逐条解释中唯一 T 均为旧语言长度条件，不是新语言首项条件；webdriver-only 为 0/3。四组 clean_pre、clean_post 分别为 0/54，弃判、空模型和失败均为 0；组合精确 F-T-F 为 42/54。

保存结果中还计算了描述性交互差分 `组合 − LANG_ADD − WD_REPLACE + BASE`：所有逐 ID 值和指标差分均为 0，没有未知位置。由于 LANG_ADD 与 BASE 本来就逐条相同，这里的交互差分等于“组合减 WD_REPLACE”，不能将其包装成独立的强交互证据或总体因果结论。未知/失败输入在实现中保留为 null，不会按未报警补零。

完整指标、原始身份、三个配对对照及变化 ID 见 [SUMMARY.json](SUMMARY.json)。648 个比较位置包含本轮新增 162 条、复用对照 486 条，实际历史记录仍只有 162 条。

## 4. 选择与支持诊断

组合三个初始 GREEDY 模型分别有 6、6、1 条规则；最终 R_KEEP 为 6、6、5 条，对应复杂度 12、12、10。两个新候选在最终三个模型中均未入选。

前两折初始集合已满六条，R_KEEP 保留轨迹为空。新语言正向各有三个训练阳性，但在最终集合中没有新的信号覆盖；旧长度条件仍在。新语言负向还会超出 clean 预算。因此不能把其未入选简单说成“条件无信息”，也没有证据说明本次 R_KEEP 进行了替换后选择旧条件。

第三折新语言正向在 15 个可用训练 triplet 中 true attack 为 0，未达到训练支持门槛；负向会使 30 个训练 clean 报警，超过预算 1。R_KEEP 保留了原语言长度条件，所以语言-only 的检出没有丢失。

新 webdriver 的正负极性在三折均有 0 个完整可用 triplet，不能进入合格候选池。历史 strict-true 投影不能恢复全部原始状态，clean 前后态为 U；这不等于所有 attack 都没有 T，也不等于 144 条字段缺失。保留 U 的语义修订在本轮不能接替旧 webdriver 条件。

最终第三折还有一个规则位置空余，仍没有合法的新增信号条件。造成三条 webdriver 漏检的主要限制是新条件的训练可用性/支持，不能解释成“六条容量已满”。增加语言首项没有修复这个支持缺口，也没有新增留出检出。

## 5. 验证、计数及原始产物

执行前 **11 个独立测试方法全部通过**：组合模块 7 项、运行器 4 项，19 次 subtest 不重复计数，0 failures/errors/skipped。仅使用人工数据；包含候选池精确性、两缓存状态、初始化身份/成员/编码器、原 R_KEEP 数学过程、模型保存加载、配对交互、未知保留，以及预测/flush 失败停止并保留完整分母。

工程调试阶段，首次运行器测试有一个断言仍期待含未知时聚合交互为 0，与新的 null 合同不符；修正了测试预期，并单独验证完整二值结果。最终记录为 [TEST_RESULTS.json](TEST_RESULTS.json)。该人工测试问题发生在真实协议登记之前，不属于真实实验失败或重试。

已执行命令均退出 0；以下是记录，不是要求重跑：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_combination/run_checks.py --output deliverables/rule_semantics_combination/TEST_RESULTS.json
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_combination/run_experiment.py prepare
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_combination/run_experiment.py run
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_combination/run_experiment.py analyze --output deliverables/rule_semantics_combination/SUMMARY.json
```

| 项目 | 实际值 |
| --- | ---: |
| 新 fit 接口调用 | 6 |
| 实际 GREEDY / R_KEEP 调用 | 3 / 3 |
| 训练编码器拟合调用 | 3，均在 GREEDY 阶段；不是只有三个数值阈值 |
| 新留出预测 | 162，均为 R_KEEP；GREEDY 为 0 |
| 对照重训 / 新候选求值 / 新采集 | 0 / 0 / 0 |
| 真实失败 / 额外重试 | 0 / 0 |
| 共享研究 fit 累计 | 171 + 6 = 177/200 |
| 剩余研究 fit 容量 | 23，未继续使用 |

本轮计费耗时 2.065537 秒，编排墙钟 2.066858 秒；包含 worker 启动、输入、训练、保存重载及预测，不代表全部开发耗时。共享研究计费累计 163.786029/21600 秒。详见 [EXECUTION.json](EXECUTION.json) 和 [JOURNAL.jsonl](JOURNAL.jsonl)。

各 `trials/SPARSE__<fold>/`、`trials/RETENTION__<fold>/` 保存模型、训练支持和轨迹、访问日志、调用日志及回执。SPARSE 的预测文件为空，RETENTION 为 27、18、117 条。未提交或推送。

执行后两路只读复核通过：六个模型可重载，身份和训练成员匹配；R_KEEP 的初始化逐折指向本轮对应 SPARSE 模型，编码器一致；日志与预测调用、保存位置及预算计数一致。独立重算指标和逐 ID 差分得到同样结果。复核没有新 fit、预测、候选求值或测试执行。

## 6. 当前结论

在固定的 R_KEEP、原三折和这批历史材料上，同时实施两项修改的效果与单独替换 webdriver 相同：保住了原语言检出，但没有补回 webdriver 的三条损失。因此，当前没有性能证据支持采用该组合替代原 R_KEEP。

结果保持 `EXPOSED_RETROSPECTIVE_DEVELOPMENT`。没有新盲测、LOCO、全开发集重拟合、总体零误报或其他数据泛化结论；也没有根据这次留出结果继续放宽支持要求、扩容、改极性或强制选入条件。语义合理性与当前检测收益仍需分开讨论。

建议提交说明：`research: test combined language addition and webdriver replacement`。
