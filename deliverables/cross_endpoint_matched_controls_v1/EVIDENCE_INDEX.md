# 证据索引

以下引用均相对本交付目录。完整新指纹、tickets、CDP/ADB ledger 没有公开授权，保留在本地忽略目录；不能因本表出现路径就认为已经上传。

| 内容 | 文件 / 本地目录 |
|---|---|
| 协议、42 位置计划、初始冻结、环境 | `PROTOCOL.md`、`PLAN.json`、`FROZEN.json`、`ENVIRONMENT.json` |
| 工程故障、最小修复、预先选定六位置补跑 | `ENGINEERING_NOTES.md`、`ENGINEERING_ISSUE.json`、`ENGINEERING_REPAIR.json`、`ATTEMPT_SELECTION.json` |
| 修复前原采集设置代码 | `engineering_before/settings_control.py`（与初始冻结摘要匹配） |
| 12 次工程采集的全部 raw/receipts/pair events/provenance/CDP | `private_runs/engineering/smoke01/` |
| 首次 42 次正式采集，包含后来被替代的六次 | `private_runs/formal01/` |
| 六次明确补跑及持久化 UI 证据 | `private_runs/repair01/` |
| 持久化诊断与初次失败 JSON、UI XML | `private_runs/engineering/`、`private_runs/engineering/settings_ui/`、`private_runs/engineering/persistence_diagnostic_ui/` |
| 实际 APK、包版本、原 App 备份、启动日志 | `private_runs/engineering/environment/`、`private_runs/engineering/original-collector.apk`、`private_runs/engineering/emulator.log` |
| 42 个规范位置：原始引用、身份/作用域/恢复、相关原值 | `results/qualification.jsonl`、`results/operands.csv` |
| 126 个模型状态、210 个条件状态 | `results/model_states.csv`、`results/condition_states.csv` |
| 全模型规则输入、逐条实际预测、原始条件操作数 | `private_runs/formal01/evaluation/app_predictions.jsonl`、`condition_results.jsonl`、`positions.jsonl` |
| 首次实际调用及保护、独立重放 | `VALIDATION.json`；完整运行文件 `private_runs/formal01/evaluation/RUNTIME_AUDIT.json`、`SAVED_REPLAY_CHECK.json` |
| 仅保存结果重汇总检查 | `SUMMARY_GUARD.json`、`private_runs/summary-guard.log` |
| 60 次真实采集与三个后端的正常结束 | `ACQUISITION_AUDIT.json`，以及三个运行目录中的 `backend_lifecycle_summary.json` |
| 设置恢复、实例退出、原服务/工作区保留 | `CLEANUP.json`、`WORKTREE_PRESERVATION.json`、`private_runs/cleanup/` |
| 单条旧 MTC 时间异常，原值/服务端事件/生命周期行引用 | `TIME_ANOMALY.md`、`TIME_ANOMALY.json` |

`meta.source_run` 区分首轮和补跑；`app_reference`、`browser_reference`、`provenance_reference`、`capture_reference` 保留仓库相对路径和物理行号。`scenario_group_id` 只是实验分组，真实 `pair_id` 由票据与 provenance 绑定，二者不能互换。首轮和补跑相同预定位置使用不同实际 session/receipt/pair；没有按时间或字段相似拼接。

本目录的 `results/` 是必要派生结果及语言/时区操作数，完整新指纹没有复制到这里。所有本地原始文件保留，未自动提交或推送。
