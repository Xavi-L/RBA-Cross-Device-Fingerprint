# R06_SOURCE_REFIT 审查入口

先读 `STEP_REPORT.md`、`VALIDATION.json`、`RUN_MANIFEST.json`。来源位序固定 O_u/H/E，8 个条件都保留相同的 162 个监督阶段分母。

`dispatch/` 是原 dispatcher 保存输出，保持只读。21 个新作业目录含训练、模型、冻结收据、预测、访问和评价记录；3 个 SRC-111 目录仅含原结果别名预测及 REUSE_RECEIPT。复用模型/训练在 `fold_models/*.ref.json`、`training_logs/*.ref.json` 精确引用 R05 原路径，未复制或重写为新模型。

`source_refit_metrics.csv` 是每来源条件总体比较；细分见配置/环境表，支持与可用性见 `CANDIDATE_AVAILABILITY.md`。预测不含评价标签，后者在独立 sidecar。JSONL/CSV 均保留方法、fold、来源、操作点、模型 ID 与 train 成员引用。

`SOURCE_CONDITIONS.json`、候选/已选规则重叠及稳定性文件区分别名、规范条件、家族和保存决策。`source_drop_sensitivity.csv/jsonl` 仅是未运行项的登记，不是 0 效果实验。

`DISPATCH_COMMAND.json` 是已经执行的命令，不得重跑覆盖产物或重置共享账本。原始 SUMMARY 的 real_fits=48 是 R05+R06 累计；本次 21 个新增 fit 见 BUDGET_VALIDATION。后处理脚本只读取保存结果，排他创建输出，不用于重训。后续任何步骤均需独立授权，本轮没有 Git 提交或推送授权。
