**MTC P0 数据结算与来源冻结报告**

执行日期：2026-09-22。冻结截止：北京时间 16:03:44（`2026-09-22T08:03:44.176744Z`）。

**当前状态：P0 已完成。用户于 2026-09-22 明确取消采购对账，统计以 MTC 目录实际留存为准；本机后端和 ngrok 已退役。**

最终冻结：`backend_server/collection_backups/mtc_final_20260922/`，截止 `2026-09-22T08:39:43.167513Z`。后端于 `08:34:37.729710Z` 正常关闭批次，8000 端口无监听；ngrok 已停止，未找到匹配的自动启动项。后续不再启动本机采集链。最终副本包含 10 个源文件，所有批次均为 closed_cleanly，活动批次文件已由正常关闭钩子清除。计数与下方历史截止一致。

以下 16:03 冻结过程保留为历史记录；P1 只消费 16:39 的最终关闭批次副本。

**研究原则**

旧实验数据质量较低，新实验仅参考设计思路；不继承旧结论、指标或方法排名，不以达到旧效果为优化目标或验收下限。以新数据、独立事实和冻结协议形成结论。

旧实验只作为设计与实现参考。历史重放只诊断差异，不要求维持旧告警数、旧分数或方法排名。本轮 P0 没有执行任何规则、训练、阈值优化或新旧效果比较。

**冻结方式与边界**

- 唯一数据源：`backend_server/collection_runs/mtc_20260917/`，来源范围由本次会话确认为百度 MTC。
- 只读 readiness 核实后台 ready、数据目录隔离、当前批次 open；未停止或重启服务，未伪造关闭批次记录。
- 在 `2026-09-22T08:03:44.176744Z` 至 `2026-09-22T08:03:44.350345Z` 的复制窗口内，11 个源文件的大小、修改时间、变更时间与 inode 保持一致；固定复制约 147.35 MiB。
- 所有冻结 JSON／JSONL 已可解析，保存完整成功、失败、重复、provisional 和事件记录；没有为了匹配 900 而删行。
- 副本文件已设为只读，raw 子目录不可写；它是本地可复查的截止副本，不是密码学封存或一次写入存储。
- 16:03 副本中的活动批次当时仍为 open；该历史副本不作为 P1 输入，P1 已改为消费 16:39 的最终关闭批次副本。
- Testin／后端根目录历史数据未纳入；没有从多个目录合并来源。

冻结清单：[FREEZE_MANIFEST.json](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/backend_server/collection_backups/mtc_p0_20260922/FREEZE_MANIFEST.json)。

**接收结算**

| 口径 | 数量 | 解释 |
|---|---:|---|
| 完成配对的 provenance／唯一 pair ID | 1029 | 后台配对完成；尚非正式实验质量准入 |
| 对应唯一 App session | 1029 | 与完成配对一一对应 |
| 厂商＋型号＋Android release | 891 | 用户确认的机型／系统覆盖口径 |
| 仅厂商＋型号 | 868 | 同型号不同系统合并后的数量 |
| 已配对安装实例 | 959 | 安装标识，不是物理设备唯一标识 |
| 重复型号／系统组合 | 105 组 | 超出每组合首条的记录共 138 条 |
| 重复安装实例 | 57 组 | 超出每实例首条的记录共 70 条 |
| App 接收回执 | 1785 | 其中重复 payload 回执 86 条 |
| App 原始归档／分析记录 | 1699 | 去除重传回执后仍保留所有 payload 版本 |
| App 唯一 session | 1693 | 同 session 额外分析记录 6 条，不当独立 session |
| 尚无完成配对的 App session | 664 | 采集留存分母，尚未经过 P1，不能称为全部合格 App177 |
| 所有 App 上报中的型号／系统组合 | 906 | 其中 15 个组合没有完成配对 |
| Browser 原始归档 | 1029 | 按对应 browser receipt 关联 |

版本分布：v9／1.6.2 为 347 条；v11／1.6.4 为 682 条。最近完成配对时间为北京时间 14:27:17。两个有数据的 backend 生命周期批次都保留；它们不是云平台采购任务 ID。

**引用关联结果**

1,028 条完成配对可直接关联 App raw／receipt、Browser raw／analysis；另 1 条引用重传回执，依据回执的 duplicate 标志、相同 session、相同已记录 payload 标识与同一 batch，唯一关联到原始归档。后者保留了当前 receipt 和原始 archive receipt 两个 ID，没有修改任何原始记录。

本轮未解引用的完成配对为 **0 条**。这属于引用存在性与一致性检查，没有额外重算全库密码学摘要，也没有将引用通过写成字段质量通过。前次发现的缺字段、timeout 和 observed 哨兵问题仍交给 P1。

配对、App、机型与尝试明细分别保存于冻结目录的 `paired_receipt_inventory.jsonl`、`app_session_inventory.jsonl`、`model_os_inventory.jsonl` 和 `browser_attempt_inventory.jsonl`。

**未完成尝试与失败分母**

共 1645 个已发票据的配对尝试，其中 1029 个有 completed receipt，616 个截至冻结仍无完成回执。未完成尝试最后持久化状态如下：

| 最后记录状态 | 尝试数 |
|---|---:|
| awaiting_browser | 492 |
| awaiting_app_and_browser | 32 |
| awaiting_app | 2 |
| expired | 90 |

616 次未完成尝试均已超过记录中的相关期限，这是离线按时间计算的事实；未改写后台状态，也不将 526 条尚未落盘为 expired 的旧记录描述成“仍在进行采集”。

616 是尝试数，664 是无完成配对的 App session 数；一次 session 可能对应不同尝试，且部分 App 不一定有票据。两者不可相加，也不能当 616 或 664 台设备。工具冲突、超时、分阶段事件均在原始事件账本保留，不删去失败来提高结果。

**已上报 App、但该型号／系统组合尚无完成配对的 15 项**

这些是后台观测到的无完整配对组合，继续保留在 App／失败分母中；不视为缺失采购项，也不再要求采购映射。

| 厂商 | 型号 | Android release | App session 数 |
|---|---|---|---:|
| HONOR | GIA-AN00 | 12 | 1 |
| HUAWEI | ASK-AL00x | 9 | 5 |
| HUAWEI | EVA-TL00 | 6.0 | 14 |
| HUAWEI | FDR-A01w | 5.1.1 | 2 |
| HUAWEI | FLA-AL10 | 9 | 1 |
| HUAWEI | HUAWEI RIO-AL00 | 6.0.1 | 1 |
| HUAWEI | HUAWEI VNS-TL00 | 6.0 | 2 |
| HUAWEI | LLD-AL20 | 9 | 5 |
| HUAWEI | MED-AL00 | 10 | 2 |
| HUAWEI | TRT-AL00 | 7.0 | 3 |
| LENOVO | Lenovo K32c36 | 5.1.1 | 3 |
| Xiaomi | Redmi 8 | 9 | 6 |
| ZUK | ZUK Z1 | 5.1.1 | 3 |
| samsung | SM-G1600 | 6.0.1 | 9 |
| samsung | SM-G6100 | 8.0.0 | 1 |

**统计依据与采购边界**

用户已确认订单全部机型都在现有材料中，并明确取消对账。后续使用自有统计：已配对型号／系统组合 891，所有 App 上报组合 906。900 不再作为目标、分母或质量验收门槛；不计算采购完成率，不要求提供采购清单。

状态为 `NOT_REQUIRED_USER_WAIVED`，并非“已逐项核对订单”。15 个没有完成配对的组合、失败和重复记录仍保留。旧的 16:03 只读快照保存当时状态；本报告与最终快照记录最新决定。

**验证与后续**

已通过 7 项重点边界测试（另覆盖取消采购目标、退役来源不得含活动批次）：重传回执别名、无重传证据拒绝、Browser／App session 错配拒绝、复制期间源文件变化中止、既有冻结目录拒绝覆盖。测试使用隔离临时夹具，不修改真实采集数据。

本轮脚本：[freeze_mtc_collection_p0.py](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/hybridguard_agent/scripts/freeze_mtc_collection_p0.py)。验证记录：[VALIDATION.json](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/deliverables/mtc_p0_20260922/VALIDATION.json)。聚合清单：[P0_SUMMARY.json](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/deliverables/mtc_p0_20260922/P0_SUMMARY.json)。

原始冻结数据位于已被 Git 忽略的 collection_backups 中；工作区原有修改保持原样，未提交或推送。P0 按用户修订后的范围已完成；字段／状态质量进入 P1，实验分组及事实标签仍属于 P2。
