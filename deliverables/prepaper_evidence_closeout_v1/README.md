# B3-B 论文前证据收尾

[中文结果报告](REPORT.md) · [主张—证据索引](CLAIM_EVIDENCE.md) · [固定协议](PROTOCOL.md)

本轮只新增3个“去匹配正常组报警上限”的有限选择任务（12次四集合检查），复用R_FULL与原S0，不拟合App、编码器或树。9个规则设置/基础配置均保存951位置结果。B3-A十二棵树保持冻结，图表只读其既有输出。

## 分离执行命令

从仓库根目录运行。研究/计时沿用B3-A隔离环境，绘图使用本目录独立`.plot-runtime`（matplotlib3.10.6），没有升级旧环境。依赖版本记录于`requirements-plot.txt`和`timing/TIMING_FREEZE.json`。

有限选择和离线组合评价（会新增3次选择；默认拒绝覆盖已有`results/`）：

```sh
python3 -B deliverables/prepaper_evidence_closeout_v1/execute_ablation.py
```

一次离线计时（不选择、不fit、不采集，默认拒绝覆盖已有`timing/`）：

```sh
deliverables/cross_endpoint_four_view_comparison_v1/.runtime/bin/python -B deliverables/prepaper_evidence_closeout_v1/measure_cost.py
```

只抽取既有日志时间字段（不重新采集、计时或推理）：

```sh
python3 -B deliverables/prepaper_evidence_closeout_v1/extract_existing_times.py
```

只从保存材料重汇总和制图（不会选择、预测、计时、训练）：

```sh
python3 -B deliverables/prepaper_evidence_closeout_v1/build_tables.py --output /tmp/b3b-review-tables
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B deliverables/prepaper_evidence_closeout_v1/plot_saved.py --tables /tmp/b3b-review-tables --output /tmp/b3b-review-figures
```

本轮实际主输出目录为`tables/`和`figures/`。每幅图含SVG、PNG、CSV；英文图例用于论文候选，中文边界说明在REPORT/CLAIM_EVIDENCE中。没有选取P0最佳树作为部署模型。

本目录Git属性保留生成CSV的原始行尾，以及SVG和工程失败快照的原始空白，避免提交/检出自动转换破坏保存材料的字节一致性。归档中的 `VALIDATION.json` 是实验结束、提交前的检查记录，其HEAD和工作区状态保留当时事实。

验证上述保存材料路径没有触发其他仓库执行代码，并逐字节比较30份表图：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B deliverables/prepaper_evidence_closeout_v1/verify_saved_only.py
```

此命令使用临时目录，不改正式结果。首次绘图环境可用 `python3 -m venv deliverables/prepaper_evidence_closeout_v1/.plot-runtime` 创建后，使用其pip安装本目录 `requirements-plot.txt` 中的固定依赖；原B3-A环境不动。

聚焦测试（其中额外原选择器调用属于测试，单独写入TEST_CALLS）：

```sh
python3 -B deliverables/prepaper_evidence_closeout_v1/run_tests.py
```

重新运行选择或计时需要使用新的本目录输出路径，例如`--output deliverables/prepaper_evidence_closeout_v1/reproduction_results_01`；不得覆盖或混淆已接受的运行。汇总/图源默认使用当前已接受的`results/`和`timing/`，重跑输出须先独立审核，不会自动替换。

## 审核入口

| 文件 | 用途 |
|---|---|
| `results/FREEZE.json` | 旧模型、预处理、条件、协议、数据及实现的本轮冻结引用 |
| `results/SETTINGS.json` / `SELECTION_FROZEN.json` | 唯一预算变动、选择先于历史评价、3个新增任务 |
| `results/models.json` / `R_*_01/02/03.json` | 三种设置、三个基础配置；新增消融标记ABLATION_ONLY |
| `results/candidate_checks.json` / `candidate_outputs.jsonl` | 12次集合检查和每个开发成员的组合状态 |
| `results/members.jsonl` / `predictions.jsonl` | 951位置、9个设置/配置输出，不累加为独立样本 |
| `tables/metric_index.jsonl` | 模型、输入、来源、角色、分子分母、未知/失败、成员ID与证据路径 |
| `tables/four_view_all_cohorts.csv` | P1/P2训练反例及144/117附加正常评价，不只保留好看的留出成绩 |
| `tables/rule_transitions.jsonl` | 相对R_FULL的所有状态变化，包括收益、损失和未知 |
| `timing/` | 1次预热/10遍原始批次、冻结环境、每模型等价验证、调用次数 |
| `existing_times/` | 同host日志区间与历史训练计时缺口，原日志仅引用 |
| `engineering_attempt01/02` / `ENGINEERING_EVENTS.json` | 正式计时之前的工程中止/失败；未生成计时样本，保留异常与调用记录 |
| `VALIDATION.json` / `TEST_CALLS.json` | 测试、汇总制图分离、计时不改变输出、旧工作区保护 |

计时包装从内存中的旧raw对象开始时，会包含原绑定校验和App内部关系适配；没有重新从设备采集，未将raw/票据复制到新目录。原B2-C公开入口、原树cells入口和缓存路径的起点不同，详见成本表的阶段定义；单独OR或树遍历不可称完整设备端延迟。

R_NO_CROSS复用S0，基础App不变。R_NO_MATCHED_NORMAL_CAP只把34条匹配正常的报警预算由1设为34，保留这些成员的覆盖检查和正常身份；这是机制消融，不是更宽松的部署政策。对144/117的历史评价不参与选择。

完整raw及private_runs继续仅在本机已有位置；远端可核对派生状态、模型、成员和图表，缺私有raw时不能宣称独立复核了所有采集原始证据。本轮不自动git add/commit/push，完成后停止实验并进入限定范围写作。
