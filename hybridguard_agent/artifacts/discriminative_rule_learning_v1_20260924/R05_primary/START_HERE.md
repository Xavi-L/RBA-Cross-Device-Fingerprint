# R05 已完成运行的审查入口

先读 `STEP_REPORT.md` 和 `VALIDATION.json`，然后按 `RUN_MANIFEST.json`、三类 expected 清单与 `MODEL_MANIFEST.jsonl` 定位精确单元。

原始正式输出在 `dispatch/`。每个 job 的 `model.json`、`MODEL_FREEZE_RECEIPT.json`、`access_log.json`、`WORKER_STARTUP.json`、`receipt.json` 保留模型冻结、输入开放时点和实际资源路径；训练模型另有 `training.json`。外层预测关闭后才写 `evaluation_sidecar.json`、`metrics.json`。全局 `PREDICTION_CLOSURE.json`、`model_receipts.json`、`OOF.json` 保留整体验证。

`DISPATCH_COMMAND.json` 是已经执行的原命令记录，不是重新拟合的待办。不要重置共享 `../REAL_RESEARCH_BUDGET/ledger.json`，不要覆盖原 run 或重复运行已消耗 job。新阶段须独立明确授权，并按冻结 dispatcher 的阶段清单及 SRC-111 复用规则处理。

顶层长表由 `hybridguard_agent/scripts/export_rule_learning_r05.py` 只读导出。该程序使用冻结 Python、无 selector/predictor/solver imports，以排他创建保护现有导出；不要在本目录重跑以覆盖产物。若仅需重新审计，可阅读其断言及 `checks/validate_saved_metrics.py`，在独立输出副本运行，保持原始 dispatch 只读。后处理记录中的 refits=0、new_predictions=0 仅针对导出阶段，真实 R05 的次数为 27/2,106。

`ARTIFACT_MANIFEST.json` 为本轮交付的路径/摘要清单，并列出外部共享账本、导出源码和执行状态。它不是自动提交授权。所有历史 R04/R04-R1 日志与验收保留；新验收记录位于本目录。
