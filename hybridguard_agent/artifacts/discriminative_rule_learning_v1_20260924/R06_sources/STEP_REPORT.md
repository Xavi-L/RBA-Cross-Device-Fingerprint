# R06_SOURCE_REFIT：冻结来源重训练主分支

**主分支执行及技术验收完成，等待外部验收；R06 的拟合后来源删除分支仍未运行。** 本轮审查基线 `9376c775549e913e0e88b678d345a35fdd726081`。R05 外部验收独立登记于 `R05_EXTERNAL_ACCEPTANCE.json`，其原模型、预测、负面结果、报告和 VALIDATION 均保留。

## 绑定、授权与执行范围

继续使用 `../R04_freeze_r1/`，启动前实际核对文件并由快照原 launcher 检查 3,298 个资源文件、所有冻结作业/成员和依赖版本。完整性检查读取字节，不对全分区进行特征转换或标签解码。没有工作区学习代码或替代解释器/求解器回退。

- protocol digest：`4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`。
- FREEZE_MANIFEST 实际 SHA-256：`bff86c2423283d9ecdf6402c2975a747707cd7d521a328561ef676cdcff2ddad`。
- RESOURCE_MANIFEST 实际 SHA-256：`7e2aa45c9cf78abc106cb61e3863c5d89f2491fe0b406b645cd48fad80bd0de0`。
- 快照外 `R06_APPROVAL.json` SHA-256：`81db53765148e4cacd2b6b8fbd568ccfa281000e47fd05a1e529ca085123c579`，绑定全部 24 个精确 job IDs、train 成员与原共享账本。历史冻结授权字段没有改写。
- Python 3.12.14、HiGHS/highspy 1.12.0、NumPy 2.3.5，macOS-15.7-arm64-arm-64bit；实际模块/解释器/依赖路径见启动与运行核查记录。
- 原 dispatcher 执行 `--stage R06 --suite complete`；冻结清单中该 stage 恰好只有 `R06_SOURCE_REFIT`，不存在顺带执行次要分支。完整命令见 `DISPATCH_COMMAND.json`。
- UTC 2026-09-24T13:33:16.439567+00:00 至 2026-09-24T13:33:35.699652+00:00，wall time 19.260039 秒，退出码 0，attempt=1、自动重试=0。

| 单元 | 预期 | 实际去向 |
|---|---:|---|
| 新增 fit | 21 | 15 个 FITTED，6 个 EMPTY_CANDIDATE_POOL |
| 来源模型单元 | 24 | 15 COMPLETED、6 EMPTY_MODEL、3 REUSED |
| 预测记录 | 1,296 | 1,134 次本轮输出 + 162 条 R05 已关闭预测精确复用 |
| 每条件监督阶段 | 162 | attack/pre/post 各 54，54 完整三态 |
| 失败、超时、预算耗尽、缺失/重复单元 | — | 均为 0 |

8 个条件使用同一批 162 阶段；1,296 条记录和来源条件数不能当独立样本数。另 100 个描述阶段保持排除；UNKNOWN 时间对照、未标注 MTC 不补入 FPR 分母。

## 来源接入与候选范围

位序固定为 **O_u/H/E**。运行源码先按允许来源筛选原始 CAT 别名，再按规范身份合并，随后仅在本折 train 上计算支持度和选择。没有从 R05 已选规则删来源来冒充重训练，也没有把合并的 SRC-111 矩阵直接供所有子集使用。共同测量门控、OP05/alpha=0.05、支持度、复杂度、划分和 GREEDY_OR 均保持冻结版本。C 的 11 项登记与公共测量合同仍保留，不能把 O_u 位为 0 称为移除了全部官方知识。

| 条件 O_u/H/E | 允许来源 | 来源目录项 | 准入原始别名 | 规范原子 | 登记/支持合格字面量 | 结果 |
|---|---|---|---|---|---|---|
| SRC-000 | 无来源 | 0 | 0 | 0 | 0/0 | 3 个 EMPTY_MODEL |
| SRC-001 | E | 23 | 8 | 8 | 16/9 | 3 个 FITTED |
| SRC-010 | H | 14 | 0 | 0 | 0/0 | 3 个 EMPTY_MODEL |
| SRC-011 | H+E | 37 | 8 | 8 | 16/9 | 3 个 FITTED |
| SRC-100 | O_u | 9 | 4 | 4 | 8/6 | 3 个 FITTED |
| SRC-101 | O_u+E | 32 | 12 | 10 | 20/13 | 3 个 FITTED |
| SRC-110 | O_u+H | 23 | 4 | 4 | 8/6 | 3 个 FITTED |
| SRC-111 | O_u+H+E | 46 | 12 | 10 | 20/13 | 3 个 FITTED（精确复用） |

上表“来源目录项”是 E/O_u/H 原登记数量；“准入原始别名”经过 core 与 App177 可用角色限制；“规范原子”已经等价合并；字面量包含正/反极性。各折登记/支持合格字面量数量在本轮恰好相同，详细支持仍逐折保存。候选完整可用性、T/F/U/FAILED 和真实训练支持见 `CANDIDATE_AVAILABILITY.md`、`candidate_inventory.jsonl/csv`、`support_statistics.jsonl`，不将别名数当样本支持。

联合条件存在以下跨来源别名归并；全部原始别名和原目录偏差极性保留：

| 规范身份 | 原别名 | 原目录偏差极性 |
|---|---|---|
| DEVIATION:NVW-002 | NVW-002, OFFDER-OS-002 | E:POSITIVE, O_u:NEGATIVE |
| DEVIATION:NW-002 | NW-002, OFFDER-OS-001 | E:POSITIVE, O_u:NEGATIVE |

12 个共享规范原子×极性×折检查显示：E、O_u、联合来源在这些等价条件上的完整训练支持相同，合并没有重复计数。证明范围是冻结测量合同与当前保存的训练统计。

H 共登记 14 项：12 项是当前 App177 的单层/控制/诊断项，不能移入 R06 核心学习视图；另外 2 项依赖缺失的独立 Browser，其中唯一 H 核心跨层候选 `P3-UA-REDUCED-BROWSER` 结构不可用。因此 H 核心准入为 0；H 单独的空模型是候选范围结果，不能写成经过充分可用 H 候选训练后“效果差”，更不能推断 H 在其他视图无价值。

## 模型、训练约束与精确复用

E 与 H+E 在三个折均选择 **`DEVIATION:P3-UA-DEFAULT:POSITIVE`**（host26 默认 UA 与 app_web67 当前 UA 的不相等）；含 O_u 的四个条件均选择 **`DEVIATION:OFFDER-UA-001:POSITIVE`**（native84 Android 宿主与 app_web67 明确桌面/脚本标记的规范偏差）。两者原目录方向均为 NEGATIVE。每个非空模型 1 原子、1 子句、1 字面量、复杂度 2；未选负极性或组合。完整 24 单元的 ID、公式、来源和原冻结时间见 `MODEL_RULES.md`。

| fold | E 可用/真攻击三态 | O_u 可用/真攻击三态 | E 攻击检出/FTF | O_u 攻击检出/FTF |
|---|---|---|---|---|
| LOEO-v1-01 | 45/15 | 45/18 | 6/9 | 6/9 |
| LOEO-v1-02 | 48/18 | 48/21 | 3/6 | 3/6 |
| LOEO-v1-03 | 15/9 | 15/9 | 12/39 | 15/39 |

三个折的 train 阶段数为 135/144/45，clean 分母 90/96/30，集合级 OP05 报警预算 4/4/1。全部非空模型 train clean 报警为 0，attack/pre/post 决策覆盖均为 1.0，支持度/复杂度/覆盖约束满足。新非空模型 15 个为 HEURISTIC_FEASIBLE；3 个复用模型保留原 R05 状态。6 个空模型 train 覆盖为 0，feasible=false，理由为 EMPTY_CANDIDATE_POOL；它们是合法保留的空结果，未被包装成可行成功模型，也不冒充求解器失败。

21 个新单元均遵循 train 开放 → train 内转换/支持度/筛选 → 模型保存并加载冻结 → outer_test 转换/预测 → 关闭与逐成员对账 → 独立评价标签。SRC-111 本次只读 R05 保存产物，其访问证据指向原 R05 执行链，不能当成 3 条新训练链。核心视图无数值分位点拟合；没有新的阈值选择。

3 个 SRC-111 对应折模型的 ID、模型文件 SHA-256、freeze_time 和原文件 mtime 均与启动前一致；3 份模型、预测和关闭收据路径在原 R05 ledger `artifact_directory` 中保持不变。R06 只建立模型/训练引用及预测别名包装，逐记录核对除当前实验身份、执行来源引用外的保存结果完全一致。`REUSE_VALIDATION.json` 保留证据；没有创建新的 SRC-111 model.json、training.json、worker ticket 或拟合。

## 完整折外比较

NE 表示 NOT_EVALUABLE，value=null。下表原子与子句覆盖数值相同；原始指标分别保存。

| 条件 | 攻击检出 | pre 报警 | post 报警 | 精确 FTF | 弃判 | 失败 | 决策覆盖 | 原子/子句覆盖 | 每模型复杂度 |
|---|---|---|---|---|---|---|---|---|---|
| SRC-000 | 0/54 | 0/54 | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 0/0 NE | 0 |
| SRC-001 | 21/54 | 0/54 | 0/54 | 21/54 | 0/162 | 0/162 | 162/162 | 162/162 | 2 |
| SRC-010 | 0/54 | 0/54 | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 0/0 NE | 0 |
| SRC-011 | 21/54 | 0/54 | 0/54 | 21/54 | 0/162 | 0/162 | 162/162 | 162/162 | 2 |
| SRC-100 | 24/54 | 0/54 | 0/54 | 24/54 | 0/162 | 0/162 | 162/162 | 162/162 | 2 |
| SRC-101 | 24/54 | 0/54 | 0/54 | 24/54 | 0/162 | 0/162 | 162/162 | 162/162 | 2 |
| SRC-110 | 24/54 | 0/54 | 0/54 | 24/54 | 0/162 | 0/162 | 162/162 | 162/162 | 2 |
| SRC-111 | 24/54 | 0/54 | 0/54 | 24/54 | 0/162 | 0/162 | 162/162 | 162/162 | 2 |

无来源和 H 单独条件各 162/162 阶段 EMPTY_MODEL 弃判、0/162 决策覆盖；其 0 次 clean 动作报警不是低误报证据，decided-clean 为 0/0、NOT_EVALUABLE/null。空模型大小明确为 0，因此原子/子句分母为 0；这与模型缺失/大小未知时 expected_denominator=null 不同。该轮未出现模型大小未知，冻结 R04-R1 对该状态的处理保持不变。

E 的阶段攻击检出 21/54=38.89%，O_u 与联合条件 24/54=44.44%；全部非空条件 pre/post 报警各 0/54、弃判/失败均 0、决策覆盖 162/162。配置内环境等权 MacroTPR 分别为 5/14=35.71% 与 6/14=42.86%，不混同阶段微平均。所有非空条件每折规则一致，但三折一致性不构成总体稳定性保证；空模型的 Jaccard 为 0/0 NE，而非 1.0。

## 重点问题的结果与限制

1. **E 能学出部分替代方案。** 它实际重新训练得到了不同的 `P3-UA-DEFAULT` 规则，检出的 21 个攻击阶段全部包含于 O_u 的 24 个之中，clean 报警及决策覆盖相同。它不是完整等效替代：env-003 的 `w9-rule-boundary-cdp-platform-only-v1` 有 3 个攻击阶段，E 保存结果为 NO_ALERT，O_u 为 MANIPULATION_ALERT。
2. **O_u 单独与联合结果在本材料上相同。** SRC-100/101/110/111 的 162 个逐阶段决策、选中规则及各折复杂度一致；SRC-111 的模型身份仍是 R05 原模型，其他条件有各自新模型 ID。
3. **条件增量须按上下文解释。** 在 E 上加入 O_u，本轮增加 3 个攻击检出和 3 个精确 FTF，决策覆盖、clean 报警和复杂度不变。在 O_u 上加入 E，原始准入别名 4→12、规范候选 4→10，但未观察到检出、决策覆盖、所选规则覆盖或三折规则一致性的额外收益。E 保留了独立可学的部分替代规则；两组共有 2 个规范候选，其余候选未产生本轮增益，不据此宣称它们普遍无效。O_u 的贡献不能记为 100%。
4. **H 在本核心视图中没有新增可学习候选。** 加入 H 前后的对应条件候选与结果相同来自冻结视图的适用范围，不是可用 H 候选的竞争训练失败。其控制项、Browser 缺失和登记用途完整保留，真实单层研究并未在本次开展。

候选交集/规范别名/家族重叠见 `CANDIDATE_SOURCE_OVERLAP.json`；实际所选规则/别名/家族重叠见 `SELECTED_RULE_OVERLAP.json`；跨折规则集合一致性见 `RULE_STABILITY.json`。E 所选家族为 host_ua，O_u 所选家族为 app_surface，规则与别名没有交集却共享 21 个攻击检出，不能把规则 ID 不同当作独立贡献。28 对来源条件的同 ID 配对比较与具体差异见 `PAIRWISE_SOURCE_COMPARISON.json` 和 `analysis/paired_stage_differences.jsonl`。

## 配置与环境范围

env-001、env-002 上 E 与 O_u 检出均为 6/9、3/6；env-003 分别为 12/39、15/39。各环境配置组成不同，不能将该差异直接归因为环境因果效应，三个关联组也不是已核验的三个独立物理设备。

| 配置 ID | E / HE 攻击检出 | O_u 及含 O_u 条件攻击检出 |
|---|---|---|
| w10-cdp-emulation-screen-metrics-only-v1 | 0/3 | 0/3 |
| w10-cdp-emulation-timezone-only-v1 | 0/3 | 0/3 |
| w6-tool-054-legacy-default-v1 | 3/3 | 3/3 |
| w6-tool-055-legacy-default-v1 | 3/3 | 3/3 |
| w6-tool-056-legacy-default-v1 | 9/9 | 9/9 |
| w6-tool-058-legacy-default-v1 | 0/9 | 0/9 |
| w9-rule-boundary-cdp-platform-only-v1 | 0/3 | 3/3 |
| w9-rule-boundary-cdp-resource-pair-v1 | 0/3 | 0/3 |
| w9-rule-boundary-cdp-ua-only-v1 | 3/3 | 3/3 |
| w9-rule-boundary-cdp-ua-platform-desktop-v1 | 3/3 | 3/3 |
| w9-rule-boundary-cdp-webdriver-only-v1 | 0/3 | 0/3 |
| w9-stealth-boundary-languages-only-v1 | 0/3 | 0/3 |
| w9-stealth-boundary-plugins-mime-v1 | 0/3 | 0/3 |
| w9-stealth-boundary-webgl-pair-v1 | 0/3 | 0/3 |

E 仍漏检 33/54，O_u 与联合条件仍漏检 30/54，负面结果均保留。完整 8 条件的配置/环境/配置×环境指标见 `by_configuration.csv`、`by_environment.csv` 和保存的 OOF；没有只保留成功条件。当前材料已暴露，本结果属于回顾性分组评价，不是全新盲测或已经证实的机制泛化。合法 UA 覆盖/测试自动化仍限制归因；有限样本零 clean 报警不是总体 FPR 为零。

## 预算、验证与停止边界

原共享账本 `../REAL_RESEARCH_BUDGET/ledger.json` 从 27 次拟合增至 48 次，本次新增 21 次。原 39 个 R05 作业记录及 artifact_directory 逐项相等，没有重置或换用合成账本。冻结 dispatcher 的 `SUMMARY.real_fits=48` 是累计值，原输出不改写；本次计数使用 before/after 差值。预算本次增加 19.019183042 秒，累计 55.912774251/21600 秒；余 152 次拟合、21544.087225749 秒，后续阶段继续共享。端到端 wall time 与预算计费范围分开记录。

`VALIDATION.json` 汇总精确单元、3 份复用、21 条新访问链、空模型语义、累计与本次拟合计数分离、训练支持/预算/目标、9360 项折总计与所有分层指标算术，以及历史只读保护。实际本次审核模型单元数为 24，其中 21 个新拟合和 3 个复用；所有长表只从保存产物导出，后处理 new_fits=0、new_predictions=0、raw_feature_reads=0。完整源码为 `hybridguard_agent/scripts/export_rule_learning_r06.py`，与冻结学习运行代码分离；未改检测方法。

`source_drop_sensitivity.csv/jsonl` 为 9 个原预留“3 折 × 删除 E/O_u/H”项逐项标 **NOT_RUN**，结果为 null（CSV 留空），理由为冻结接口未实现且本次未授权。没有改快照临时执行，没有填 0，也没有与重训练结果混合。`BRANCH_STATUS.json` 明确 all_R06_branches_complete=false。

R01–R05 所有历史产物保持原样；R05 清单对共享账本/全局执行状态的摘要是 R05 执行时点记录，不用本次依法延续的账本去覆盖历史清单。当前外部验收、R06 预算和工作区保护记录另存本目录。

R06_SOURCE_REFIT 主分支完成，R06 父步骤保留部分完成状态，拟合后删除分支未运行。完成后停止等待验收；未执行 R07、其他分支、全开发集重拟合、补采、攻击工具、旧 S07、提交或推送。
