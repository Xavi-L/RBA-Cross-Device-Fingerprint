# 单条 MTC 时间异常定向核对

对象仅为 `mtc-pair-hgpair-v1-a01c05ee9faf637996ed1ddc`。逐条来源与配对事件列在 `TIME_ANOMALY.json`；未修改原数据、原标签、筛选条件或 B2-A 输出。

| 时间来源 | App | Browser | 可作何解释 |
|---|---|---|---|
| payload timestamp，秒 | 1787209854，即 2026-08-20 07:10:54 UTC | 1790043483，即 2026-09-22 02:18:03 UTC | 相差 2,833,629 秒，但来源为客户端报告时钟，不能直接视为实际经过时间 |
| App acquisition，毫秒 | start 1787209851882；finish 1787209854726 | Browser finish 1790043483173 | App 内部起止与其 payload 秒值一致；不是单纯把毫秒当秒造成的差值 |
| 同一 backend batch 的服务端接收 UTC | 2026-09-22 02:17:31.477431Z | 2026-09-22 02:18:03.578398Z | 接收事件间隔 **32.100967 秒** |

配对 provenance 为 `completed`、`receipt_bound`，App receipt、Browser receipt 和 batch 对应。`ticket_issued`、Browser stage 事件与最终 `paired_at` 都在 9 月 22 日的这一服务端流程内；该 batch 从 9 月 21 日 04:04:30.015418Z 开始，到 9 月 22 日 08:34:37.729710Z 正常关闭。原始引用分别为 App raw 第 1614 行、Browser raw 第 973 行、provenance 第 973 行，配对事件物理行在 JSON 中逐条列明。

结论：现有证据支持约 32.1 秒的**服务端接收间隔**，不支持把 32.8 天直接称为实际配对等待。客户端时钟校正、陈旧 payload／采集时间来源等解释仍无法从这批记录唯一确定；也不能把服务端接收差直接当作两端特征的精确采集间隔。本次没有发现该条 receipt/pair/batch 关联冲突，但这不等于证明客户端时间准确。原 C1 的 offset 相等结果保留，不增加事后时间过滤，也不扩展为全 MTC 审计。
