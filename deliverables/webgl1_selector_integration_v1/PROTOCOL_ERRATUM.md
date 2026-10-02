# 接入协议复制残留说明

交付复核发现 `PROTOCOL.json` 保留了上一轮独立观察器验证协议的部分说明：`analysis.overall_gate` 仍提到 8 组，旧的排除/接入说明仍写不登记候选或不改默认采集。它们与同文件新的 `scope`、`planned_triplets=4`、`planned_payloads=12`、`acceptance`、`registration` 及实际接入任务冲突，属于复制遗留文字。

实际执行和验收为 4 个环境、各 1 组正常/攻击/恢复，共 12 条；包括默认采集、保存和候选登记，模型拟合与完整模型预测均为 0。运行器使用 `matrix` 中每环境 `triplets=1`；分析器核对 `planned_triplets`、`planned_payloads` 和逐组条件，未使用残留的“8 组”文字。结果和边界见 `RESULTS.json` 与 README。

保留原始协议、STARTED 和 source_snapshot，不追改已冻结的文件，不重采、不替换样本、不改变候选判定或验收条件。本说明不能作为新实验的授权或协议；下一轮须另写明确一致的协议。

另：`analyze.py` 会从保存记录重算并写回本目录的结果文件，属于可重现的分析命令，不是纯只读检查。交付前最后一次运行后的候选结果已核对未变，见 `FINAL_REVIEW.json`。
