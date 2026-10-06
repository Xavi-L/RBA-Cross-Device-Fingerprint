# App177主体实验

已完成结果见 [REPORT.md](REPORT.md)，配对缺口见 [PAIRED_COVERAGE.md](PAIRED_COVERAGE.md)。已有结果受覆盖保护，命令不会自动重训。使用原B3-A隔离环境，sklearn固定1.7.2，不安装新环境。

在仓库根目录分别执行以下命令。前3条用于一个**新的输出目录**；重新训练会产生新的真实调用，不应为了更好的分数重复运行。当前交付在本目录 `results/`。

```sh
APP_PY=deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python
APP_RUN=deliverables/app177_core_ablation_v1/run.py
APP_OUT=/tmp/app177-reproduction

# 1. Full回放、逐ID历史核对、候选编译回归；不拟合
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" "$APP_RUN" full --output "$APP_OUT"

# 2. 24次规则拟合＋3次树拟合；直接加载原三折编码器
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" "$APP_RUN" train --output "$APP_OUT"

# 3. 冻结模型评价；包含两阶段，主表固定RETENTION
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" "$APP_RUN" evaluate --output "$APP_OUT"

# 4. 只读取保存输出重汇总；0预测、0拟合、0采集
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" "$APP_RUN" summarize --output "$APP_OUT"
```

针对已交付结果的额外命令：

```sh
# 只重汇总当前交付
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" "$APP_RUN" summarize
# 用保存汇总重建中文报告；不加载预测器
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" deliverables/app177_core_ablation_v1/report.py
# 针对性测试，实际模型拟合0；测试API调用单列
PYTHONDONTWRITEBYTECODE=1 "$APP_PY" deliverables/app177_core_ablation_v1/run_tests.py
```

`verify.py`核对模型、初始化、配对来源，并保存树训练预算概率；第一次会进行2,646个**训练成员**预测，单独计数，不属于“仅重汇总”。`coverage.py`只沿已知成员及引用目录做配对覆盖检查，不预测/拟合/采集。v9/v11/v14/v15/v16保持各自身份，原2026c时区数据库依赖不改。

`train --resume-engineering`仅用于显式恢复未完成的工程执行，复用已保存规则模型；完整训练完成后拒绝该命令。本次第一棵树拟合后导出概率自检失败，修复后真实树fit共4次，其中3棵交付、1次工程尝试，详见 `results/engineering/ATTEMPTS.json`；没有规则或编码器重拟合。

主要文件：

- `SETTINGS.json`、`CANDIDATES.json`：固定设置、真实依赖、53模板及三折数值展开。
- `results/members.jsonl`、`folds/*/training_members.jsonl`：评价与实际训练成员、真实物理行号/原始引用。
- `results/FULL_REPLAY.json`、`full_predictions.jsonl.gz`：Full逐ID核对和3,771个输出。
- `results/models/*/{model,training}.json`：24个规则模型/轨迹/移除和候选去向；三个树JSON含预处理、精确训练权重、classes、概率树结构。
- `results/predictions.jsonl.gz`：新方案33,939个逐条输出、触发规则/树概率与缺测依赖。
- `results/summary/`：14配置、MTC组成、专项、60条App侧输出、两阶段及输入完整性CSV/JSON。
- `results/FIT_CALLS.jsonl`、`EXECUTION.json`、`TEST_CALLS.json`：研究拟合、工程尝试、预处理与测试调用分开。

没有复制整套历史raw、Browser证据、票据或private_runs；原始路径按既有授权范围引用。0采集、0 Browser重训，不自动启动W1，不执行git add/commit/push。
