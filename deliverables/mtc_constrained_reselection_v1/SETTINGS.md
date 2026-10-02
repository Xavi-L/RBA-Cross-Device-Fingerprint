# MTC 正常约束下的规则重新选择：设置与成员说明

本轮是已有数据上的分组开发评估，不是独立盲测。参考提交为 `17bfe0f57f1af43f0f0e34d6db06864331d005cd`；历史模型、观测和结果只读复用。完整参数与实际成员 ID 已在运行前写入 [SETTINGS.json](SETTINGS.json)，训练完成前不打开新模型的 MTC development / reserved_validation 评价结果。

## 固定比较

| 项目 | A：完整候选池 + 双正常约束 | B：历史 MTC 兼容候选模型 + 双正常约束 |
|---|---|---|
| 基础候选 | WEBGL50 的原 50 项 | 同一 50 项 |
| 数值展开 | 原训练分位点方法，只用各折受控训练成员 | 复用同折 A 的编码器与阈值 |
| MTC 单候选可评估比例 | 不新增门槛；U 保留未验证身份 | 必须至少 90% 为 T/F |
| MTC 最终模型明确输出覆盖 | 不新增门槛，完整披露 U | 必须至少 90% |
| 受控正常 OR 集合预算 | 168 条的 5%，向下取整为 8 条 | 相同 |
| MTC 正常 OR 集合预算 | 630 条的 5%，向下取整为 31 条 | 相同 |
| 选择器 | 新 GREEDY，再以自己的新结果初始化 R_KEEP | 相同 |
| 目标及容量 | 原攻击配置宏平均目标、复杂度惩罚与语义排序；最多 8 条、复杂度 16 | 相同 |

两类正常预算分别计算，不用合并分母稀释报警。约束作用于整个 OR 集合，添加、剪枝、R_KEEP 添加和替换都受约束。原受控三态支持与覆盖要求仍生效，MTC 作为独立正常记录参与预算，不复制成 clean_pre / clean_post，不伪造 triplet。

每个方案三个留环境折，每折 GREEDY 与 R_KEEP 两个拟合阶段，共计划 **12 次拟合、6 个最终 R_KEEP 模型**；不额外训练全量模型，不追加参数网格，不根据评价表现追加方案。阈值编码器每折拟合一次，由 A、B 共用。5% 和两个 90% 都是本轮固定的开发设置，不是部署可接受标准或评价集保证。

若发现真实适配错误，只按相同设置修复重跑并保存实际调用数。运行中发现旧 audio/network/viewport 的 `-1` 哨兵被历史状态标为 observed，初始适配据此误当数值；修正后按相同固定设置重跑，首轮材料原样保留于 `attempt_01_pre_sentinel_fix.tar.gz`。初次评价已经打开的事实、累计调用数和修正范围须同时见 `ENGINEERING_CORRECTIONS.json` 与最终 REPORT.md，不把修复后结果包装为此前未见过的评价。

## 数据流向

| 数据 | 实际固定数量 | 用途 |
|---|---:|---|
| WebGL1 受控准入记录 | 378 | 三个完整环境，每折训练 252、留出评价 126；合并三折评价时每记录只计一次 |
| 受控攻击 | 126 | 每折训练攻击 84、留出攻击 42；配置支持和轨迹只从训练部分计算 |
| 受控配对正常 | 252 | 每折训练正常 168、留出正常 84 |
| MTC 主代表 discovery | 630 | 独立正常训练约束 |
| MTC 主代表 development | 144 | 不参与拟合的评价部分 |
| MTC 主代表 reserved_validation | 117 | 另一单列评价部分；历史名称不赋予新盲测资格 |
| MTC 配对重复 | 137 | 所有模型完成后的补充回放，不训练 |
| MTC App-only | 654 | 所有模型完成后的补充回放，不训练 |

MTC 主代表和机型关联分组直接复用 P2 清单，不重新挑选、不随机重拆。型号／系统组合不等于独立物理设备。MTC 记录被三个模型评价时，仍是同一条记录，不把三次评价当成三个独立样本，不投票或挑最好一折。

原三条安装冒烟继续不进入受控主实验。上一轮另列的 11 条整层缺失及 6 条同 session 额外观测本轮不扩入比较分母，仍可在 [上一轮报告](../mtc_cap8_replay_v1/REPORT.md) 查询去向。

原 CAP8 基线优先复用保存预测：受控来自对应三个 WEBGL50 / RETENTION trial；MTC 来自上一轮 `results.jsonl`。按本轮相同成员和 split 对齐；不把旧 844/891 与某个更小的新评价子集直接比较。报告重汇总逐方案、折和子集核对全部成员与 SETTINGS.json 一致，未知、失败和 EMPTY_MODEL 保留在分母内。

## 正常采集依据和观测含义

复用 [上一轮 DATA_NOTES.md](../mtc_cap8_replay_v1/DATA_NOTES.md) 及逐记录 `normal_basis` 侧表：依据已有常规 MTC 任务、采集脚本和保留的批次记录，研究正常条件是没有实施本研究目标指纹篡改。允许设备调试连接和云平台自动化组件，不以规则是否报警判断其是否正常，也不把原历史 `unlabeled` 覆盖成新标签。

有依据的正常样本报告已观察报警比例；若某记录依据不足，只报告一般报警比例并保存原因。没有第三方逐设备认证，也不重做采购对账。

新版受控与旧 MTC 经过独立命名的共同候选适配入口。采集模式只决定如何解释观测，不能成为预测特征。所有 50 项基础候选保留字段依赖、单位、原值状态、可评估性及原因；标签、来源、型号、任务 ID 和 split 只用于关联与分组。

- 旧 WebGL1 缺少数字／数字字符串查询原始观测，保留 U，不从 GPU 名称或其他会话补造。
- 旧 webdriver false 的投影损失按 legacy 语义保留 U；不会把旧布尔字段冒充新版 raw 合同。
- 旧 deviceMemory / hardwareConcurrency 默认 0 不当作真实测量值；数值状态、类型和单位均保留。
- 一个已知 T 可以使 OR 报警；F OR U 仍为 U。缺少条件不会导致整批丢弃，也不能通过删除未知规则把 A 称为完整已验证模型。

## 复现

在仓库根目录运行。正式目录已有结果时，不覆盖；指定新的输出目录可以重新完成同一固定设置，但会实际再次拟合，应只在明确需要复现时执行。

```bash
# 本轮相关测试（不重跑其他大型实验）
python3 -m unittest hybridguard_agent.tests.test_mtc_reselection_candidates hybridguard_agent.tests.test_mtc_constrained_selection hybridguard_agent.tests.test_mtc_reselection_runner hybridguard_agent.tests.test_mtc_reselection_reporting

# 复现实验：先完成全部固定拟合，再打开评价部分并汇总
python3 deliverables/mtc_constrained_reselection_v1/run_experiment.py run --output-dir /tmp/mtc_constrained_reselection_reproduction

# 也可分开执行 train 和 evaluate；evaluate 检查所有模型已完成
python3 deliverables/mtc_constrained_reselection_v1/run_experiment.py train --output-dir /tmp/mtc_constrained_reselection_staged
python3 deliverables/mtc_constrained_reselection_v1/run_experiment.py evaluate --output-dir /tmp/mtc_constrained_reselection_staged

# 只从保存结果重建 summary.json / REPORT.md；不训练、不预测、不加载原观测
python3 deliverables/mtc_constrained_reselection_v1/summarize.py --output-dir deliverables/mtc_constrained_reselection_v1
```

模型身份和路径在 `models.json`，逐候选训练统计及搜索轨迹在各 trial 的 `training.json`，实际调用数及工程修正在 `EXECUTION.json`。`predictions.jsonl.gz` 无损压缩保存逐条预测（汇总兼容未压缩 `.jsonl`），训练完成后的 `EVAL_CANDIDATE_DIAGNOSTICS.jsonl` 和 `OVERLAP_EXAMPLES.json` 只用于解释漏检及实际取值重叠，不影响模型选择。

本轮完成实现、测试、训练、评价与报告后停止，不启动后端或新采集，不购买服务，不自动提交或推送。
