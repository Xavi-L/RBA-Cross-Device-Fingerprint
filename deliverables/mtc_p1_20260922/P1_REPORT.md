# MTC P1 快照与字段质量报告

执行日期：2026-09-22。**P0 与 P1 已完成；本报告保存 P1 交付时的状态。** 后续 P2 也已完成，分组、切分与任务准入见 [P2 报告](../mtc_p2_20260922/P2_REPORT.md)。本次 P1 结果是数据结构、来源关联和字段可用性的验收，不是规则有效性或检测效果验收。

用户已取消采购对账，全部统计以 MTC 实际留存数据为准。900 不再作为目标、分母或筛选条件。旧实验只参考设计思路；不继承旧结论、指标、方法排名，也不以达到旧效果作为优化目标或验收下限。

## 来源与停机

- 本机 ngrok、后端均已停止；后端于北京时间 16:34:37 正常关闭批次，8000 端口无监听，未找到匹配的自动启动项。旧 PID 文件已清理，启动文档已标为历史说明；后续不再使用本机采集链。
- 唯一来源为 `backend_server/collection_runs/mtc_20260917/` 的最终关闭批次副本：`backend_server/collection_backups/mtc_final_20260922/`，截止 `2026-09-22T08:39:43.167513Z`。所有批次 closed_cleanly，10 个源文件完整保留；Testin／后端根目录旧数据未纳入。
- 16:03 的旧 P0 副本保留历史状态；P1 只消费最终副本。没有重启服务、修改 raw、补造采集值或覆盖已有快照。

证据：[P0 报告](../mtc_p0_20260922/P0_REPORT.md)、[停机记录](../mtc_p0_20260922/RETIREMENT.json)、[最终冻结清单](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/backend_server/collection_backups/mtc_final_20260922/FREEZE_MANIFEST.json)。远端静态站点与 ECS 不在此次“本机后端和 ngrok”停机范围内。

## 可复现分母

| 口径 | 数量 | 含义 |
|---|---:|---|
| 后台完成配对 | 1,029 | 原始接收成功口径，不因 QC 改写 |
| 后台已配对型号／系统组合 | 891 | 厂商＋型号＋Android release，保留原始名称 |
| QC 配对主视图 `paired_244` | 1,028 | 各输入层均有实际观测；允许字段级不可用，不能解释为每条 244 个值均可评估 |
| QC 配对主视图型号／系统组合 | 891 | 原有组合覆盖全部保留；不是独立物理设备数 |
| App-only 主视图 | 654 | 无完成配对且 App 各层有观测的首条归档 |
| 部分数据视图 | 11 | 1 条完成配对＋10 条未完成配对；均仅 Native84 实际采集，App host26＋Web67 超时 |
| 同 session 额外观测 | 6 | 来自 5 个 session，保留完整内容和引用，不当作独立 session |
| 隔离视图 | 0 | 当前没有结构／类型／引用无法接受的行；部分数据已另行保留 |
| App 原始观测 | 1,699 | 1,028＋654＋11＋6，逐行唯一去向 |
| 唯一 App session | 1,693 | 1,029 已配对＋664 无完成配对 |
| App 回执 | 1,785 | 1,699 条原始归档回执＋86 条重传回执；全部已关联 |

v9／1.6.2 的 347 条配对全部保留；v11／1.6.4 的 682 条配对中，681 条进入主视图、1 条进入部分视图。完整配对主视图没有丢失任何型号／系统组合。

所有 App 上报仍覆盖 906 个型号／系统组合，其中 15 个没有完成配对。1,645 个配对尝试中 616 个无完成回执，失败分母和 10,847 条配对事件完整保留在 P0。它们不是新增样本或采购缺失机型，不能与 session 分母直接相加。

## P1 处理规则与实际结果

**版本与来源。** 新增 MTC 专用白名单配置，同时接纳 v9、v11；字段与 probe 契约读取冻结副本。历史 v8 配置和 v1 比较器保留原行为，研究 README 已将当前入口切到 MTC v2。

**回执与多次观测。** 配对优先按 provenance 指定的 App receipt、payload 标识、session、batch 关联，不能以同 session 的最后一条记录覆盖。1 条配对引用重传回执，在 duplicate=true、stored_new=false 且同 session／payload／batch 唯一匹配的条件下关联原始归档，保留两个 receipt ID。全部 86 条重传均有唯一原始归档。无配对 session 以首条归档作为主观测，额外版本单列；选择不依赖规则输出或数据效果。

**状态已声明的缺字段。** App 全量中 13 条 Android 5.1.1 观测原有 172 个字段，缺失的 5 项都已声明 unsupported_by_os：security_patch、三项 screen_mode_physical／refresh 字段、is_cleartext_traffic_permitted。派生视图添加 null 槽位并保留不可用状态，既不补估计值，也不修改 raw。其中 3 条有完成配对，分别是 smartisan SM801、OPPO R9 Plusm A、Hisense E81，均留在主视图。其余 10 条是 App-only。

**整层超时。** 另 11 条 App 原始观测只有 Native84；93 个 host／App Web 字段已声明 timeout。派生结构可表达这些 null 槽位，但记录明确进入 partial。唯一已配对的 HUAWEI STF-AL00／Android 9 具有真实 Browser67，仍不能当作 App177 完整观测或主视图完整配对。该型号另有合格配对，所以 891 组合覆盖不变。

**observed 默认哨兵。** 采集源码对 deviceMemory、hardwareConcurrency 使用 `|| 0`。v2 保留原 observed 状态，在独立 field_quality 中将这两个字段的 0 标为 ambiguous_sentinel，并拒绝据此生成值冲突。主视图 deviceMemory 的 App 端有 73 个 0，Browser 端有 63 个 0，涉及 105 条配对。maxTouchPoints=0、false、空字符串不作全局无效化。该覆盖仅限已核实的默认路径，其他字段的默认值含义尚需后续逐字段语义评估，observed 不等于已证明真实可用。

**数值比较 v2。** `8` 与 `8.0` 相同；布尔与数值、字符串与数值、null 与 0 不混淆；数组保持顺序。不可用状态及已知哨兵优先于值比较。保留原来的 39 项可作值观测、28 项不宜直接比较的范围；这只是同名字段差异观察，不意味着这 39 项在所有容器中理应相等。

下表数值诊断覆盖全部 1,029 条引用与结构有效的完成配对（包括部分记录）；只有两端 observed 的 1,028 条进入数值格式分解。它与主视图分母有明确区别。

| 字段 | 旧 JSON 字面差异 | 仅数字表示不同 | 数值确实不同 | v2 same／different／unavailable |
|---|---:|---:|---:|---|
| deviceMemory | 1,028 | 888 | 140 | 857／66／106 |
| devicePixelRatio | 648 | 643 | 5 | 1,023／5／1 |

deviceMemory 的 140 个数值差异中包含 74 条至少一端为 0 的记录；这些记录在 v2 中归为不可用，不被描述为真实跨端冲突。剩余 different 也不是攻击标签。没有用降低差异数来评价检测效果。

## 产物与使用

正式目录：[mtc_paired244_v2_20260922_final](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final)。之前无 `_final` 后缀的目录是第一次构建检查，不作为后续研究输入。

- `paired_244.jsonl`、`app_only_177.jsonl`、`partial.jsonl`、`repeated_observations.jsonl`、`quarantine.jsonl`：派生视图，raw 路径和行号可追溯。
- `selection_audit.jsonl`、`pair_qc_audit.jsonl`、`receipt_audit.jsonl`：全部 App 归档、配对和回执的处置去向。
- `field_quality.json`：App 全量观测与配对主视图分别按版本、API、浏览器分层统计；无配对 App 不伪造 browser 分层。
- [FIELD_QUALITY.md](FIELD_QUALITY.md)：主视图全部 244 个字段的状态、哨兵与 null 槽位统计。
- `browser_pair_comparisons.jsonl`：仅离线描述性比较；`manifest.json` 明确 comparison cohort 和分母。
- `feature_catalog.json`、`config.json`、`comparison_policy.json` 和实现副本：固定版本、命名空间、类型与本次处理约定。合并后的 session JSON、票据事件及 provisional 材料作为冻结参考留存，不当作额外指纹观测。

重建命令（输出必须是新目录）：

```bash
python3 hybridguard_agent/scripts/build_mtc_paired244_snapshot.py \
  --config hybridguard_agent/config/mtc_paired244_sources.v2.json \
  --output-dir hybridguard_agent/artifacts/mtc_v2_NEW_RUN
```

## 验证与下一阶段边界

29 项相关测试通过，覆盖数值类型、状态、哨兵、明确缺失与整层超时、重传证据、混合版本、指定回执与同 session 新观测、禁止覆盖旧输出，以及历史 v1 回归。未重跑 Android 构建或无关整仓测试。记录见 [TEST_RESULTS.json](TEST_RESULTS.json)。

额外直接核对所有输出与 raw：1,699 行各有唯一去向，1,029 条配对各有处置，原始 App／Browser 值全部保留，新增 null 均有原始不可用状态依据，QC 前后的 891 个组合集合完全相同。脚本：[verify_snapshot.py](verify_snapshot.py)，结果：[VALIDATION.json](VALIDATION.json)。

P1 快照统一标为 development_qc_only、unlabeled。QC 主视图准入不代表已经有可信正常／攻击标签，也不代表分组独立或正式测试可用。P2 需冻结安装实例／型号系统分组、重复观测用途、发现／开发／最终评价切分与任务准入。已查看全量字段质量和格式诊断的事实需保留在后续协议里。

v2 记录是新契约，不能直接交给只接受 v1 的 runtime loader。抽取适配及 Browser 真正参与规则／决策属于 P4；当前比较只生成旁路描述性材料。本轮未挖掘或执行规则、训练模型、调阈值或重跑效果实验，也未将旧结果作为目标。
