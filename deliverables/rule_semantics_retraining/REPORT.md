# 固定历史材料上的规则语义候选重训练

本轮已完成四组、原三折的真实重训练：12 次 fit、648 条留出预测，零失败、零重试。四组的逐条留出决策完全一致：攻击检出 27/54（50.00%），按配置与环境宏平均检出率 35.71%，clean 报警 0/108，可判断覆盖 162/162。三个修订组相对本轮原基线的提升均为 **0 个百分点**。

新语言条件和新 webdriver 条件均未进入最终模型。增加语言条件时选中规则不变；替换旧语言或旧 webdriver 条件时，前两折改选了已有的屏幕可用高度条件。语言替换组的新语言正向条件仍有训练信息，未入选不能解释为“没有价值”。

状态：`RETRAINING_COMPLETE_PENDING_REVIEW`。执行已经完成，等待用户审阅；本报告未启动新的参数搜索或训练。

## 1. 本轮比较的对象

本轮模型是从固定候选池中学习少量条件、再以 OR 连接的规则分类器。使用原 `GREEDY_OR + OP05`，比较改变候选语义后，选择器最终选择的规则和留出决策是否改变。

| 组别 | 候选池变化 | 真实 fit 数 |
| --- | --- | ---: |
| A / BASE | 原 W0 的 app_web67 候选池，重新训练以验证接入等价性 | 3 |
| B / LANG_ADD | 保留原池，增加固定语言首项关系条件 | 3 |
| C / LANG_REPLACE | 删除完整 languages 长度候选家族，加入固定语言首项关系条件 | 3 |
| D / WD_REPLACE | 删除旧 webdriver EQ:True 原子，加入 legacy 上报状态条件 | 3 |

新条件沿用原字段家族，保留原语法规定的正、负极性；没有强制入选、单独放宽支持要求或重复计算同一证据。C 在数值阈值编码前移除整个旧语言长度家族，因此不只是删除某一个已见阈值。

本轮的 27/54 是原 GREEDY_OR 三折 LOEO 比较轨道的基线。旧 R_KEEP 结果使用不同学习过程，旧 C 阶段使用 LOCO；全开发集拟合结果则属于训练集回代。它们不能与本轮数字直接相减，解释成此次修改造成的提升或退步。

## 2. 执行前固定的材料与约束

协议见 [CONTRACT.json](CONTRACT.json)，登记时间为 `2026-09-29T11:46:30.195119+00:00`。起始提交为 `e0755e1fce69d3f49527ad7d7ec84ec3df8df4c6`；本轮新增代码及结果在报告生成时尚未提交，具体执行代码身份记录于协议。

- 固定 162 条历史记录：54 个 attack 阶段、54 个 clean_pre 阶段、54 个 clean_post 阶段，组成 54 个已准入 triplet。
- 复用上一轮保存的 324 个候选结果单元，即两个候选各覆盖 162 条记录；新候选求值次数为 0。
- 语言候选为 `RSR-LANG-FIRST-v1`，版本 `1.0.0`；webdriver 候选为 `RSR-WEBDRIVER-STATE-v1`，版本 `1.0.0`，模式 `legacy_projection_v1`。
- 原始数据索引、定义、划分分别来自 R04 的 `DATA_INDEX.json`、`data/definitions.json`、`SPLIT_MANIFEST.json`，详见协议内引用。
- 候选缓存为 `deliverables/rule_semantics_candidate_evaluation/CANDIDATE_RESULTS.jsonl`。

| 折 | 留出环境 | 训练记录 | 留出记录 |
| --- | --- | ---: | ---: |
| LOEO-v1-01 | env-001 | 135 | 27 |
| LOEO-v1-02 | env-002 | 144 | 18 |
| LOEO-v1-03 | env-003 | 45 | 117 |

固定设置：目标为训练集 `MacroTPR_config_environment − 0.005 × complexity`；OP05 的 clean 报警预算为 `floor(0.05 × N_train_clean)`；最多六个单条件子句、目标复杂度最多 12；数值阈值仅由训练折分位点产生；支持要求、极性、家族约束、选择顺序与平局处理均沿用原协议。没有依据留出结果改参数。

这里的 162 是唯一历史记录数，648 是四组重复评估这些记录的预测位置数；均不代表 162 或 648 个独立设备/独立实验。材料此前已经用于研究，角色保持 `EXPOSED_RETROSPECTIVE_DEVELOPMENT`，不能表述成新的盲测。

## 3. 接入实现和边界

新增纯接入模块 `hybridguard_agent/research/rule_semantics_retraining.py`，复用原训练访问接口、数值编码器、选择器、模型序列化和预测逻辑。新增独立调度器 [run_experiment.py](run_experiment.py)，没有修改旧实验入口或重开已关闭的 C 阶段。

训练读取严格限制为本折 train IDs。缓存事先建立字节位置索引，训练只读取对应 train 单元；保存并重载冻结模型后，才读取本折 held-out 特征和候选单元。每条预测记录保留执行模型及折身份，预测文件关闭之后才在分析阶段接入评估标签。`U` 和 `FAILED` 保持原状态，未将 unknown 当作 false 或丢弃对应样本。

调度器保存 fit 开始标记、预测调用日志和实际耗时。异常或中断时保留已完成结果，并为未完成位置保存失败状态，不缩小分母；损坏的调用日志会显式保留计数未知及已知下界。本轮没有触发这些失败路径。

先执行 A 的三次 fit，并与原 R07 同折 `GREEDY_OR / OP05 / SRC-111 / app_web67` 结果比较，全部通过后才执行 B/C/D。每折均通过 11 项等价性核对：训练成员、模型状态、固定原子、数值编码器、选中子句、候选清单、完整支持统计、训练分数及状态、编码原子 ID、留出成员、留出决策及覆盖计数。比较忽略新增研究身份包装字段，但保留原语义字段。详见各 BASE trial 的 `BASELINE_EQUIVALENCE.json`。

## 4. 留出结果

| 组别 | attack 检出 | 宏平均检出率 | clean 报警 | 可判断覆盖 | 相对 A 检出率变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A / BASE | 27/54 = 50.00% | 35.71% | 0/108 | 162/162 | 基线 |
| B / LANG_ADD | 27/54 = 50.00% | 35.71% | 0/108 | 162/162 | 0 个百分点 |
| C / LANG_REPLACE | 27/54 = 50.00% | 35.71% | 0/108 | 162/162 | 0 个百分点 |
| D / WD_REPLACE | 27/54 = 50.00% | 35.71% | 0/108 | 162/162 | 0 个百分点 |

宏平均值为 `5/14`，按原协议先在配置内处理环境再对配置平均，不能用 27/54 代替。所有组均有 27 条 `MANIPULATION_ALERT`、135 条 `NO_ALERT`，`INSUFFICIENT_EVIDENCE`、`EMPTY_MODEL`、`FAILED` 均为 0。clean_pre、clean_post 分别为 0/54；精确 F-T-F 为 27/54。

B/C/D 相对 A 的 `changed_records`、新增检出 attack IDs、丢失检出 attack IDs 均为空；逐 ID 的 decision 与 logical state 均一致。这比只有总数相同更强，但仅适用于这批记录。

| 留出环境（四组相同） | attack 检出 | clean 报警 | 可判断覆盖 |
| --- | ---: | ---: | ---: |
| env-001 | 9/9 | 0/18 | 27/27 |
| env-002 | 6/6 | 0/12 | 18/18 |
| env-003 | 12/39 | 0/78 | 117/117 |

14 个配置中，`w6-tool-054`、`w6-tool-055`、`w6-tool-056`、`w6-tool-058` 和 `w9-rule-boundary-cdp-resource-pair-v1` 对应配置的 attack 全部检出；其余九个配置均未检出。完整配置名、分母、逐配置/环境结果和逐条差分见 [SUMMARY.json](SUMMARY.json)。不能把这批 clean 的 0/108 推广为总体零误报率。

## 5. 选择器实际选了什么

A 的前两折均选择六条：`CAT:NW-006` 正向、MIME 数量 >0、旧 webdriver=true、timezone_offset >0、device_memory >2、languages 长度 >1。以下表格描述最终集合；数值条件是训练编码器产生的控制条件，并非本轮发现的正常 App 普遍规律。

| 组别 | 前两折相对 A 的选中集合变化 | 第三折 | 新候选是否入选 |
| --- | --- | --- | --- |
| A / BASE | 原六条 | 仅 hardware_concurrency >4 | 不适用 |
| B / LANG_ADD | 无变化 | 仅 hardware_concurrency >4 | 否 |
| C / LANG_REPLACE | languages 长度 >1 被已有 avail_height >732 替代 | 仅 hardware_concurrency >4 | 否 |
| D / WD_REPLACE | 旧 webdriver=true 被已有 avail_height >732 替代 | 仅 hardware_concurrency >4 | 否 |

各组的子句数均为 6、6、1，目标复杂度均为 12、12、2。

### 语言增加组：信息被已有规则覆盖

新语言正向条件在前两折达到支持要求，但其三个训练阳性已经被最终旧规则集合覆盖，追加没有足够的正目标增益；第三折不满足正向支持要求。负向条件虽满足最低支持要求，但会触发过多 clean 报警，不能通过预算约束。因此最终规则与 A 完全一致。

### 语言替换组：有训练信息，但没有进入最终六条

C 的前两折按保存的选择 trace 依次加入：`CAT:NW-006`、MIME 数量 >0、旧 webdriver=true、timezone_offset >0、device_memory >2、avail_height >732。第六步达到六子句、复杂度 12 的上限，没有剪枝。该步训练目标增益分别为 `87/1300 ≈ 0.066923`、`43/700 ≈ 0.061429`。

新语言正向在前两折各有三个 true attack triplet，且其三个训练阳性仍未被最终集合覆盖。保存的最终集合诊断显示，追加该条件仍有正目标增益，但会变成第七条、复杂度 14，违反全局容量限制；这里不是语言家族配额不足。

因此可以确认“本次固定贪心过程未选中有训练信息的语言条件”。保存 trace 只记录每轮获胜集合，没有记录同轮全部未选提案的分数，不能进一步声称屏高的当轮增益严格更大，或这次明确由词典序平局处理决定。也不能据此断言放宽容量、换算法或换数据一定能提升留出效果。

### webdriver 替换组：历史输入不足以满足支持要求

新 webdriver legacy 条件保留上一轮的 18T、144U，正负极性在三折均无法满足完整 triplet 的支持要求，因而未进入可选集合。144 个 U 来自历史 strict-true 投影无法恢复完整原始状态，并不等于 144 条字段缺失。前两折最终改选已有屏高条件。

模型仍然覆盖全部 162 条，是因为包含大量 U 的新 webdriver 条件没有入选；这不表示缺失的原始状态已经补齐，也不表示 unknown 被成功转化为可靠 false。当前结果支持“在固定材料上可以由其他旧条件得到同样决策”，不支持“新 webdriver 语义已经改善检测”。

## 6. 测试、执行计数与复核

执行前的最终聚焦测试为 **18 个独立 TestCase 方法全部通过**：接入模块 12 项、调度器 6 项，0 failures、0 errors、0 skipped。27 次 subtest 不另算独立测试。覆盖候选池增删、完整语言家族移除、unknown/failed 保留、训练成员边界、模型保存重载、支持拒绝、缓存索引读取范围、基线比较及中断结算。

工程调试期间修正过测试夹具的 webdriver provenance 缺项，以及 tuple/list 序列化比较方式；这些发生在协议登记和真实训练之前。最终测试只使用人工夹具，真实 fit/模型预测/候选求值次数均为 0。测试中的预期失败路径不计为真实实验失败。详细记录见 [TEST_RESULTS.json](TEST_RESULTS.json)。

已执行的命令如下，均退出 0；这是执行记录，不是要求重新执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_retraining/run_checks.py --output deliverables/rule_semantics_retraining/TEST_RESULTS.json
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_retraining/run_experiment.py prepare
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_retraining/run_experiment.py run
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_retraining/run_experiment.py analyze --output deliverables/rule_semantics_retraining/SUMMARY.json
```

| 计数 | 实际值 |
| --- | ---: |
| 真实 fit 调用 | 12/12 |
| 真实模型预测调用与保存位置 | 648/648 |
| 新候选求值 | 0 |
| 新采集 | 0 |
| 真实训练失败、额外重试 | 0、0 |
| BASE 历史等价性 | 三折全部通过 |
| 共享研究 fit 累计 | 147 + 12 = 159/200 |
| 剩余研究 fit 容量 | 41（不是本轮追加执行授权） |

本轮计费耗时为 4.266879 秒，包含 worker 启动、输入、训练、模型保存重载和预测；编排墙钟耗时 4.290121 秒，不代表全部工程开发耗时。共享研究计费耗时累计 158.433636/21600 秒。详见 [EXECUTION.json](EXECUTION.json) 与 [JOURNAL.jsonl](JOURNAL.jsonl)。

执行后两路只读复核确认：12 个模型可重载且身份一致；训练成员与合同一致且不与留出成员相交；日志顺序为训练、冻结模型、预测关闭、任务关闭；12 个 fit 标记、648 条调用记录、648 条唯一 `(group, sample_id)` 预测和回执一致。使用已保存预测与评估标签独立计数得到相同结果。复核未增加 fit、predict 或候选求值。

各 `trials/<group>__<fold>/` 保留模型、完整训练输出、预测原始文件、访问日志、调用日志、回执及 stdout。旧 tracked 文件保持未修改。

## 7. 研究结论与停止位置

本轮已经回答了“把新候选放回规则选择器重新训练，整体效果是否提升”：在固定历史材料、原三折 LOEO 和固定 GREEDY_OR 约束下，**没有提升，也没有逐条决策变化**。候选语义修订和检测性能提升是两个需要分别验证的问题。

结果同时给出两个具体原因：语言条件的新增训练信息受到已有规则覆盖或最终全局容量限制影响；webdriver 历史 strict-true 投影无法恢复完整原始状态，产生 U，并受完整 triplet 支持要求限制。当前证据不足以判定新语义条件在其他学习过程或独立数据上的最终收益。

本轮停在四组比较及报告交付。未运行 R_KEEP 对照、LOCO、全开发集最终拟合或独立确认；未扩张规则容量、调整阈值、合并新条件组或采集新数据。后续如要研究这些方向，应作为新的明确比较设计，保留本次零提升结果。

建议提交说明：`research: compare semantic candidate retraining on fixed LOEO folds`。
