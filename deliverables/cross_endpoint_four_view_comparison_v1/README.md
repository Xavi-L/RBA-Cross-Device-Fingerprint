# B3-A 四视图小树开发比较

结果与边界见 [REPORT.md](REPORT.md)，拟合前约定见 [PROTOCOL.md](PROTOCOL.md)。12 个预定模型均已完成，使用同一批 951 个配对位置；P0 为开发拟合，P1/P2 为整批留出的开发比较。这里的 App-only 仅指 App 侧语言/时区视图，不是全部 App177 字段的性能上限。

## 文件入口

| 文件 | 内容 |
|---|---|
| `features.py` / `source_adapter.py` | 9 个原字段、11 个固定派生测量；原配对适配器与 v9/v11/v16 状态 |
| `engine.py` / `run.py` | 固定权重、训练部分预处理、12 次拟合、概率阈值与 JSON 树推理 |
| `results/SETTINGS.json` / `PRE_FIT_FREEZE.json` | 固定设置、实际默认参数、拟合前代码/依赖记录 |
| `results/members.jsonl` / `PLANS.json` | 951 个位置的独立身份、原三阶段组、训练/评价成员 |
| `results/features.jsonl` / `SOURCE_MANIFEST.json` | 必要派生特征、原缺测原因和来源引用，无完整 raw 副本 |
| `results/models.json` / `P{0,1,2}_V_*.json` / `.txt` | 12 个模型的身份、权重、预处理、树结构和规则 |
| `results/predictions.jsonl` | 11,412 行概率、状态、叶节点、输入完整性与未见类别 |
| `results/summary/` | 来源/家族/正常场景分组、T/F/U/FAILED、预算、双端差异、冻结参考 |
| `results/main_comparison.csv` / `input_collisions.json` / `recipe_audit.json` | 主比较、同输入反例与分裂特征检查 |
| `results/known_15_unknown_reasons.csv` | 已知 15 个 F→U 的旧交集/状态原因，不重审全 MTC |
| `results/VERIFICATION.json` / `SUMMARY_GUARD.json` | 当前输入逐条复现及仅重汇总检查 |
| `VALIDATION.json` / `TEST_CALLS_*.json` / `TEST_RESULTS_*.txt` | 全轮调用账本、测试与保护检查 |
| `engineering_attempt01/` | 一次拟合后 JSON 导出失败的原记录及部分输出 |

## 环境和已执行命令

检查了本机 Homebrew Python 3.9/3.10/3.13/3.14、项目 collection venv 和 Codex bundled runtime，没有发现可用 sklearn。因此使用 Python 3.13.5 新建本目录隔离环境，安装固定 `scikit-learn==1.7.2`；旧研究环境没有升级。实际依赖见 [ENVIRONMENT.json](ENVIRONMENT.json) 与 [requirements-frozen.txt](requirements-frozen.txt)，`.runtime/` 被忽略。依赖安装可能需要网络；下面的研究运行不需要网络或设备。

以下命令从仓库根目录执行。已完成的正式输出是 `results/`，程序拒绝覆盖已存在的输出目录。

```sh
deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python -B deliverables/cross_endpoint_four_view_comparison_v1/run_tests.py --pattern test_comparison.py
deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python -B deliverables/cross_endpoint_four_view_comparison_v1/run_tests.py --pattern test_export.py
deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python -B deliverables/cross_endpoint_four_view_comparison_v1/run.py
deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python -B deliverables/cross_endpoint_four_view_comparison_v1/verify_saved.py
python3 -B deliverables/cross_endpoint_four_view_comparison_v1/check_summary.py
python3 -B deliverables/cross_endpoint_four_view_comparison_v1/analyze_saved.py
deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python -B deliverables/cross_endpoint_four_view_comparison_v1/run_tests.py --pattern test_saved_boundaries.py
```

前两组测试分别保存为 `TEST_CALLS_01/02.json`，最后一组为 `TEST_CALLS_03.json`；对应文本日志保留。首次实验在第一个模型拟合后导出失败，修正仅将 numpy 整数转为 Python 整数，详见失败目录。第二次运行完成全部 12 个模型。上面的列表是成功执行的命令集合，不省略失败调用；全轮合计 17 次树 fit（12 正式 + 1 工程失败 + 4 合成测试）。

需要重新拟合时，使用相同依赖和一个新目录，例如在 `run.py` 后追加：

```sh
--output deliverables/cross_endpoint_four_view_comparison_v1/reproduction_01
```

这会增加 12 次新拟合，本轮未再次执行。原始加载依赖本机 B2-B `private_runs`、先导档案和已验证 P1 快照；不要求重新采集。跨机器/版本的拟合结果不保证字节相同，因此同时保存实际树结构和本次软件版本。远端没有私有 raw 时仍可检查派生输入、模型、逐条输出并执行下面的重汇总；不能冒称远端已独立核验私有采集原始证据。

## 仅重汇总：无拟合、无预测、无原始数据读取

```sh
python3 -B deliverables/cross_endpoint_four_view_comparison_v1/summarize.py deliverables/cross_endpoint_four_view_comparison_v1/results --output /tmp/b3a-summary-review
```

只使用已保存的成员、模型索引和预测。无需 numpy/sklearn，不加载适配器。`check_summary.py` 对这一路径设置执行/读取限制，已复现 8 个完全一致的汇总文件。`analyze_saved.py` 同样只读保存结果，但会在 `results/` 重写诊断表；它也没有预测/训练入口。

## 当前输入复现

`engine.predict_current(bundle, item)` 接收一个保存模型和已可信绑定的当前测量投影；`item` 仅有 `cells`、`endpoint_errors`、`pair_errors`。用 `source_adapter` 适配原始记录，再由 `features.extract` 得到该投影。标签、来源、版本、样本 ID、场景、未来恢复、历史预测不进入此入口。它使用 JSON 树，不重新 fit。`verify_saved.py` 已对 12×951 位置逐条核对概率、状态、叶节点和未见类别，并独立重算训练成员的词表、中位数和权重。

公开派生字段只含本任务允许的语言、首项、长度、时区与关系状态；没有复制整条语言列表、完整采集 raw、票据或两个 B1 ZIP。路径/ID 仅作为评价和引用元数据。旧模型、条件、正式权限及历史 App105/126、378 身份保持原义。本轮无 git add/commit/push。
