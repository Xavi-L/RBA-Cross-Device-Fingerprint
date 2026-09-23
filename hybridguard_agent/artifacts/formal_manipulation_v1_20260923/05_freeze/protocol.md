# 运行前协议 formal-manipulation-protocol-v2

本文件解释同目录 `protocol.json`，机器规格和精确单元以绑定到 `FREEZE_MANIFEST.json` 的 JSON/JSONL 为准。冻结摘要：`d1eb5d9894ff8a9194692f8bcfdc22b7f6c603448f1f21ad8151980a3fb19d27`。

研究为已经暴露材料上的 App177 回放。S05 仅冻结；不代表执行 S06–S12 的授权。App 轨不附加 Browser；MTC 轨保留 P6 已消费保留集的访问历史，只复用保存结果，不称新盲测。

## 输入、分母及独立评估

`blind/inputs.jsonl` 是 S02 推理输入的逐字节副本，262 个独立 opaque ID。worker 仅收每次当前 payload；调度器持有 ID/行号/固定变体。`evaluation/` 保存 S01 facts、三态、inventory、排除、缺件和 S02 原索引/关联。标签、phase、工具、执行 config、路径、session/install/group、日志、回执、预期修改和未来 post 不进入 worker。

262 阶段包括准入攻击三态 162、时间对照 UNKNOWN 54、低证据攻击 45、不完整尝试 1。31 个候选包中含一个空包，继续引用原 inventory，不创建空包阶段。88 组阶段关联（69 完整攻击三态、18 时间对照三时点、1 不完整）均保存。独立物理设备数未知；3 个环境组只是关联分组。

性能任务分母固定为攻击 54、clean_pre 54、clean_post 54、精确 010 三态 54；全部已准入阴性阶段 108。时间对照 mid/全部三时点的阴性分母均为 0，不计算该 FPR；所有时间点仍保留描述与关联。未知事实总计 100 阶段，不能默认阴性。FAILED、弃判留在预定分母，覆盖、条件率和失败上下界单独报告。无独立环境总体区间、校准、阈值搜索或自然基率主张。

原 `configuration_id` 为空的旧配置按保留的 `config_id` 建评估汇总键，原值单列并保留 S02 原索引副本。共 20 个配置/对照展示键，其中 14 个准入攻击配置。API 分层 30/35/36 各 46/45/171 阶段。13 个机制键只是申明修改字段集合（含空集合），不等于 13 种已验证攻击机制。batch 保留原包身份；没有足以固定跨包共同批次的记录，因此所有 54 准入三态在 `control_matching.json` 明确未匹配，不按相近日期、命名或分数猜配对。

## 风险策略、比较及唯一执行

绑定 S03-R A/B/C v2 和 S04 family-or-v2。7 候选、5 家族、阈值 1；原 57 ACTIVE / 87 目录结果和 Verifier 保留。只有角色允许、A 支持、B 合格、原验证通过且关系为 MATCH/COUNTEREXAMPLE 才可评估候选家族。冲突产生风险提示；至少一族可评估且无冲突为 NO_ALERT；全无覆盖为 INSUFFICIENT_EVIDENCE；异常为 FAILED。C=UNKNOWN 不自动否决风险，也不被升级为攻击证明；分数不是概率。

| 首次执行步骤 | 固定条件 | 新单元数 |
|---|---|---:|
| S06 | 主 216 阶段 × final/legacy19、App177、SRC-111 | 432 |
| S07 | 主 216 阶段 × final/App177、SRC-000 至 SRC-110；111 复用 S06 | 1512 |
| S08 | 主 216 阶段 × final/SRC-111、Native84/Host26/AppWeb67/NativeAppWeb151；App177 复用 S06 | 864 |
| S10 | 其余 46 阶段 × final/App177/SRC-111，仅描述 | 46 |
| 合计 | 13 唯一变体，262 阶段均有去向 | 2854 |

`expected_units.jsonl` 给出每个 ID、变体、S02 行号、首次步骤。相同 payload 不去重，重复别名条件复用相同输出，不重复作独立样本。`variant_registry.json` 保留全部 80 条 S04 静态定义，明确本协议只选 13 条。current-v3 角色投影仅为关系诊断别名，没有第三个正式二值检测器。

E/O_u/H/C=23/9/14/11，公共 C 和语义门控相同。O_u 的两个候选与 E 共享家族，H/C 无候选；结构性零增量不能当作实测无价值。四来源映射固定 C/B0→000、E→001、O→110、EO→111，八条件只运行唯一 ID。来源分组消融不叫完全移除官方知识。

## 诊断、缺失、成本与图表

`diagnostic_spec.json` 精确冻结 D1 reduction 保护项删除、D2 合成 unknown shadow、D3 保存事件重复票、D4 合成 raw equality。原谓词及未指定因素保持；D1 不强行消除其他 parser/K-token 保护，未覆盖则 NOT_EXERCISED。D2/D4 不是新风险检测器，不给正式 TPR/FPR；D3 阈值 1 二值效应结构性为零。诊断 480 单元包括 D1/D3 各 216 真实材料计划派生项以及四诊断×12 合成输入。

`synthetic/fixtures.jsonl` 保存 12 个 E4、37 个 E5 输入（8 候选必要字段×4 unavailable/quality 条件、3 整层清空、2 协调相同的独立输入）。无真实攻击标签、无执行结果。字段值/状态/质量同时明确，整层清空不保留隐藏旧值；两个相同 payload 的 fixture 仍是两个单元。

`timing_spec.json` 和评估侧分层表固定 24 个 opaque ID、两方法和 1 冷/3 warmup/20 测量，共 1152 单元。包含 Verifier 重算、阶段值、失败、median/nearest-rank P95、硬件/OS/Python记录和语义输出一致性；不挑最快重复。解释先全量自动核对，未决语义按事前规则最多 12 条进入盲方法名队列；没有人工结果则 NOT_REVIEWED，不调用 LLM。

Fig.6 按总计划恢复为八来源离散操作点；当前 control_mid FPR 无标签，因此该图性能项关闭，不用 clean_pre/post 或 MTC 替换横轴、不绘制 ROC。全配置排序、阶段顺序、表/图源行、弃判/失败/缺标签符号和区间单位都已固定。P6 13,365 主行及 137 重复的原协议/消费记录保留；S05 未读取其逐行效果。自然 MTC 654/11/6 只冻结已有材料分类复用，不新建预测矩阵。

## 版本绑定与重现

主 HEAD `f00e699d2763afed5369774f01e5a0f632d8f5c6` 已推送；S05 新代码仍为工作区版本，由 source_environment 和实际源码副本绑定。44 个参与源码、25 个运行配置/字段资源连同输入、精确规格等共 135 文件进入有限 manifest；不是全库扫描。历史 source/config/facts、P0–P6 不修改。报告、测试日志、后续状态记录不进入自引用 digest。

生成命令（已执行；不对当前目录重跑）：

```text
python3 -B hybridguard_agent/scripts/freeze_formal_manipulation_protocol.py --output hybridguard_agent/artifacts/formal_manipulation_v1_20260923/05_freeze --config-dir hybridguard_agent/config/formal_manipulation_protocol_v2
```

只读验收可加 `--validate-only`；它只核对有限 manifest、schema 和集合，不执行规则。重新生成必须使用全新的两个目录，并保留旧冻结与失败记录。未来经授权运行时使用 `frozen_sources` 的完整内部布局与显式复制 v2 config/policy；不得从工作区默认路径混入新逻辑。

静态 `step_execution_plans` 不是 runnable job，不写 authorized_execution_step。S06 或其他步骤须单独授权后，才按冻结单元转成 S04 job；冻结本身不授予权限。S09/S10/S11 尚待其授权步骤实现符合固定定义的包装，须绑定新增包装源码，不能改主规则/门控/阈值。任何科学合同变化另起版本。
