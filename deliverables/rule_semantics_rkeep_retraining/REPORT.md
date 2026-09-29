# 新语义候选在 R_KEEP_V1 上的重训练比较

本轮成功复现已有 R_KEEP 基线 **45/54（83.33%）**。增加语言首项条件仍为 45/54；用新条件替换旧语言长度条件，或替换旧 webdriver 条件，均降至 **42/54（77.78%）**。两种替换分别丢失 3 条语言边界攻击和 3 条 webdriver 边界攻击，没有新增检出。四组 clean 报警均为 0/108，可判断覆盖均为 162/162。

本轮完成 12 次真实 R_KEEP fit、12 次实际 retention 调用、648 条留出预测，零失败、零重试。状态为 `RETRAINING_COMPLETE_PENDING_REVIEW`；已完成执行和分析，等待用户审阅。

## 1. 本次比较与此前数字的关系

本轮按用户“重新测试对 R_KEEP 版本的改进情况”的授权执行。直接基线是 B 阶段的 `W0 + R_KEEP_V1`，采用其原三折 LOEO、OP05 和原互补保留算法。

- 27/54：旧 W0 / GREEDY_OR 轨道，也是上一轮语义候选实验的比较基线。
- 36/54：A 阶段 C0 OR W0 的事后组合诊断，本轮不比较该组合。
- **45/54：B 阶段 W0 + R_KEEP_V1，已在本轮三个 BASE trial 中复现。**

本轮回答的是新条件对已有 R_KEEP 改进版的作用；没有把前一轮的 27/54 当成本轮基线。

## 2. 固定方案与实施方式

执行前协议为 [CONTRACT.json](CONTRACT.json)，登记于 `2026-09-29T12:25:44.427373+00:00`。起始提交为 `e0755e1fce69d3f49527ad7d7ec84ec3df8df4c6`；本轮代码与结果尚未提交，执行代码身份保存在协议中。

| 组别 | 候选条件 | 初始化 | 新 R_KEEP fit |
| --- | --- | --- | ---: |
| BASE | 原 W0 | 上一轮 BASE 同折 GREEDY 模型 | 3 |
| LANG_ADD | 保留原池，增加语言首项关系 | 上一轮 LANG_ADD 同折模型 | 3 |
| LANG_REPLACE | 删除完整旧语言长度家族，加入语言首项关系 | 上一轮 LANG_REPLACE 同折模型 | 3 |
| WD_REPLACE | 删除旧 webdriver EQ:True 原子，加入 legacy 状态条件 | 上一轮 WD_REPLACE 同折模型 | 3 |

复用的是 [上一轮四组](../rule_semantics_retraining/REPORT.md) 已保存、已经实际训练的十二个初始模型及各自冻结编码器，不再调用 GREEDY 或重新拟合数值阈值。BASE 与旧 B01 的初始化语义相同；修订组使用相应修订候选池产生的初始化，避免把已删除旧条件从初始模型带回来。

数据仍为固定 162 条历史监督记录，即 54 个 attack、54 个 clean_pre、54 个 clean_post 阶段。三个训练/留出划分为 135/27、144/18、45/117，对应留出 env-001、env-002、env-003。四组使用同一批记录，648 个预测位置不是 648 个独立样本或设备。候选输入复用已经保存的 324 个单元，新候选求值次数为 0。

保留原 `R_KEEP_V1` 的全部数学选择规则：从初始集合出发，只添加带来正的加权信号覆盖增量 D 的条件；允许训练宏检出增量为 0；不降低初始攻击检出，满足整个 OR 的 clean 预算、支持、覆盖和结构约束。按新增宏检出、新增 D、较少 clean 报警、较低复杂度、稳定 clause ID 依次决定。最多六个单条件子句、复杂度 12，OP05、分阶段覆盖至少 0.8；不交换或删除初始化规则，不进行事后 sparse pruning。

新语言条件仍属于 `language_preferences`，新 webdriver 属于 `automation_flag`。同一字段的新旧表达不人为算成两个独立信号组。当前 retention 内核与旧 B01 的选择逻辑一致；其已有的超时状态修复会区分 `TIME_LIMIT_FEASIBLE` / `FAILED_FIT`，本轮没有超时，也没有修改该内核。

新增模块为 `hybridguard_agent/research/rule_semantics_rkeep_retraining.py`，调度器为 [run_experiment.py](run_experiment.py)。新身份为 `rule-semantics-rkeep-retraining-v1 / RSR_RKEEP_RETRAINING / R_KEEP_V1`。没有伪装成 GREEDY 或使用旧 B/C 阶段的授权入口。

## 3. 基线复现与训练边界

先完成 BASE 三折并通过历史等价性校验，再执行其余九次 fit。每折与旧 `B_development/trials/B01_retention__W0__R_KEEP_V1__LOEO-v1-0{1,2,3}__attempt01/` 比较，**15 项全部通过**，包括训练成员、方法与模型状态、编码器、候选支持及选择、信号组、初始子句、保留轨迹及 D、训练分数、最终子句、留出成员及逐条决策/覆盖计数。仅忽略研究身份、时间和无关包装字段，没有容忍阈值或选择差异。

三折 BASE 的 `mismatching_prediction_ids` 均为空。详见各 BASE trial 的 `BASELINE_EQUIVALENCE.json`。

worker 只打开本折训练特征、标签和候选缓存单元，验证对应初始模型的完整候选池、支持、训练分数、编码器与成员后调用一次 retain。新模型保存并重载冻结后才打开留出特征/候选单元；预测文件关闭后，分析阶段才读取评估标签。保留 U/FAILED 语义以及全部预期分母，不将 unknown 改成 false。

## 4. 留出结果

| 组别 | attack 检出 | 配置/环境宏检出 | clean 报警 | 决策覆盖 | 对 BASE 的变化 |
| --- | ---: | ---: | ---: | ---: | --- |
| BASE | 45/54 = 83.33% | 11/14 = 78.57% | 0/108 | 162/162 | 基线 |
| LANG_ADD | 45/54 = 83.33% | 11/14 = 78.57% | 0/108 | 162/162 | 无逐条决策变化 |
| LANG_REPLACE | 42/54 = 77.78% | 10/14 = 71.43% | 0/108 | 162/162 | 丢失 3，新增 0 |
| WD_REPLACE | 42/54 = 77.78% | 10/14 = 71.43% | 0/108 | 162/162 | 丢失 3，新增 0 |

两种替换均使 attack 检出率下降 **5.56 个百分点**，宏检出下降 **7.14 个百分点**。各组 clean_pre 和 clean_post 分别为 0/54，弃判、空模型和失败均为 0；精确 F-T-F 与 attack 检出一致，分别为 45/54、45/54、42/54、42/54。

| 留出环境 | BASE | LANG_ADD | LANG_REPLACE | WD_REPLACE |
| --- | ---: | ---: | ---: | ---: |
| env-001 | 9/9 | 9/9 | 9/9 | 9/9 |
| env-002 | 6/6 | 6/6 | 6/6 | 6/6 |
| env-003 | 30/39 | 30/39 | 27/39 | 27/39 |

LANG_REPLACE 的全部三个变化均为第三折 `w9-stealth-boundary-languages-only-v1` 的 attack，由报警变为不报警。WD_REPLACE 的全部三个变化均为第三折 `w9-rule-boundary-cdp-webdriver-only-v1`，方向相同。其余记录决策不变。两个组丢失的是不同样本，不能把它们合并成一个实际运行过的“语言加 webdriver 联合替换”结果。

逐 ID 差异、完整配置/环境分母、原始模型身份和指标见 [SUMMARY.json](SUMMARY.json)。

## 5. 为什么没有提升，以及为什么替换会下降

十二个最终模型均未选入新语义候选。不能因此认定候选在所有场景都无价值；下面的限制分别作用于训练支持、规则容量和可用观测。

### 增加语言：旧模型完整保留，结果不变

前两折初始集合已经占满六条，新语言正向的训练信号也被原语言信号覆盖。第三折新语言正向在 15 个可用训练 triplet 中 true attack 为 0，未满足支持要求；负向会触发 30 个训练 clean 报警，超过预算 1。

原语言长度条件仍可保留。第三折 R_KEEP 在 hardware_concurrency >4 的初始模型上依次加入 UA/platform、旧 webdriver、device_memory、MIME 数量和旧语言长度，恢复已有的六条规则，最终模型及全部决策与 BASE 一致。

### 替换语言：旧信号被移除，新信号在关键训练折没有正例支持

前两折复用的语言替换初始化已满六条，其中旧语言长度条件由已有的 avail_height >732 取代，R_KEEP 没有追加任何规则。新语言正向在这两折各有三个 true attack，但受六条上限约束。

真正出现检出损失的是第三折：旧语言长度家族已经删除；新语言正向 **true attack=0**，未通过最低训练支持；负向则违反 clean 预算。R_KEEP 最终只选了五条、复杂度 10，恰好是 BASE 第三折集合减去旧语言长度条件。因此 **这三条漏检不能归因于规则数量已经满了**，关键限制是正向缺乏训练支持、负向超出 clean 预算。

### 替换 webdriver：历史投影造成 U，无法形成完整支持 triplet

新 webdriver legacy 条件沿用 18T、144U。144U 表示历史 strict-true 投影不足以恢复完整原始状态，不等于 144 条字段缺失。三折的正负极性均有 **0 个完整可用 triplet**，不能通过原支持要求。具体阻塞是 clean_pre/post 全为 U；三折训练 attack 的正向 T 数分别为 12、15、9，不能将其表述为“训练攻击中没有信号”。

第三折最终同样只有五条、复杂度 10，恰好是 BASE 第三折集合减去旧 webdriver=true。其余条件未补上三条 webdriver-only 攻击，结果从 45/54 降至 42/54。模型本身仍有完整决策覆盖，因为含大量 U 的新 webdriver 条件没有被选中；这不表示原始信息缺口已修复。

只读核对上一轮保存的候选缓存还确认：语言替换组丢失的三个留出 attack，其新语言谓词均为 T；webdriver 替换组丢失的三个留出 attack，其新 webdriver 谓词也均为 T。它们在这些攻击上的单条信号存在，但没有通过相应训练支持要求成为选中规则。不能用已经看到的留出 T 倒补训练支持。保存的逐条模型解释显示，BASE 在这些样本上的唯一 T 分别是被删除的旧语言长度条件或旧 webdriver 条件，替换模型剩余五条全部为 F。

## 6. 测试、原始产物与执行计数

执行前最终聚焦测试为 **11 个独立 TestCase 方法全部通过**：接入模块 8 项、调度器 3 项；18 次 subtest 不重复算独立测试。0 failures、0 errors、0 skipped。测试使用人工夹具，真实 fit/predict/候选求值均为 0；未重跑上一轮的 18 项测试。

调试时 runner 夹具曾因 macOS `/var` 与 `/private/var` 路径别名出现一次 error，修正了测试目录的 `resolve()`；实际实现未为此改变。最终测试结果见 [TEST_RESULTS.json](TEST_RESULTS.json)。人工预期失败测试不属于真实实验失败。

以下为已经执行且退出 0 的命令，不是要求重新执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_rkeep_retraining/run_checks.py --output deliverables/rule_semantics_rkeep_retraining/TEST_RESULTS.json
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_rkeep_retraining/run_experiment.py prepare
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_rkeep_retraining/run_experiment.py run
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_rkeep_retraining/run_experiment.py analyze --output deliverables/rule_semantics_rkeep_retraining/SUMMARY.json
```

| 执行项目 | 实际值 |
| --- | ---: |
| 新 R_KEEP fit 接口调用 | 12 |
| 实际 retention 调用 | 12 |
| 留出模型预测调用及保存位置 | 648 |
| 新 GREEDY fit / 阈值拟合 / 候选求值 / 新采集 | 0 / 0 / 0 / 0 |
| 真实训练失败 / 额外重试 | 0 / 0 |
| 共享研究 fit 累计 | 159 + 12 = 171/200 |
| 剩余研究 fit 容量 | 29，未继续使用 |

本轮计费耗时 3.286855 秒，编排墙钟 3.305838 秒；计费包含 worker 启动、输入、模型训练/保存重载和预测，不代表全部开发耗时。共享研究计费累计 161.720491/21600 秒。预算接续上一轮 [EXECUTION.json](../rule_semantics_retraining/EXECUTION.json)，没有回到旧 C 阶段的 147 次计数。

[EXECUTION.json](EXECUTION.json) 与 [JOURNAL.jsonl](JOURNAL.jsonl) 保存逐任务计数和结算。各 `trials/<group>__<fold>/` 保存模型、完整训练支持及保留轨迹、预测原始文件、访问日志、调用日志和回执。所有旧实验文件保持原样；没有提交或推送。

执行后的两路只读复核均通过：十二个模型可重载，初始化编码器与成员对应正确；访问日志符合训练、冻结、预测关闭的顺序；fit/retain/预测计数和唯一 `(group, sample_id)` 位置一致。独立从保存预测与标签重算得到相同指标和变化 ID，三折历史基线比较均通过。复核没有新增 fit、predict 或候选求值。

## 7. 本轮可得结论

**现有材料不支持把这两个新条件作为提升 R_KEEP 检出率的替代方案。** 仅增加语言条件没有收益；删除对应旧条件再换入新条件会各少检出三条。在当前固定评估中，保留原 R_KEEP 基线的成绩更好。

这不等于旧语言长度或旧 webdriver 表达已经被证明是普遍可靠的攻击规律。正常 App 行为的语义适用性，与固定历史样本上的检出能力，是不同问题。本轮负结果应保留，不能为了恢复成绩把 U 改为 false、放宽支持、或强行选入条件。

全部结果属于 `EXPOSED_RETROSPECTIVE_DEVELOPMENT`。本轮没有独立确认、新数据泛化、LOCO、全开发集最终拟合或总体零误报结论，也没有根据留出结果继续调整算法。固定四组比较完成后停止。

建议提交说明：`research: evaluate semantic candidates with fixed R_KEEP retention`。
