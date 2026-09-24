# R01 新协议、候选语法与分组/数据角色冻结

日期：2026-09-24。研究：`discriminative-rule-learning-v1-20260924`。
实际工作区 HEAD：`cbd9f5a`，即合并 PR #5 的 main；允许后继提交，不依赖回退历史版本。未找到额外文件式 AGENTS.md，本轮遵循用户提供的适用指引及当前主线/v2 执行计划。

R01 交付范围为机器可读合同、元数据台账、分组成员、文献备忘和静态/合成验收。验收以本目录 `VALIDATION.json` 为准；用户验收仍为 PENDING。未实现学习器，真实训练/预测、攻击工具、上游校验器、旧 S07 均为 0。完成后停止，不自动提交、推送、建 PR 或执行 R02。

## 1. 候选清点结果

57 个 ACTIVE 原 ID 与 S03 来源逐项对齐：E23、O_u9、H14、C11。每项保留原谓词/参数/版本、字段类型/表面、来源与经验筛选历史、原家族/相关关系、旧角色、原子条件、结果映射、反例及新用途。来源不因新用途被重写，O_u 不称“纯官方”。

| 实际计算类型 | 数量 | 新用途 |
|---|---:|---|
| 跨表面关系 | 20 | 开放为核心候选；当前 8 项依赖 Browser |
| 同表面多字段关系 | 16 | 同层对照；其中 1 项依赖 Browser |
| 采集器自洽/拷贝关系 | 8 | 单层对照或诊断，不计独立跨层证据 |
| 部署策略 | 2 | 诊断保留，不作为跨层报警贡献 |
| 单字段上下文 | 3 | 条件明确者可入明确命名的同层对照 |
| 其他诊断 | 8 | 依赖字段多不等于比较了多个表面 |

当前 App177 可支持 12 个核心目录项：`NW-001, NW-002, NW-005, NVW-001, NVW-002, OFFDER-OS-001, OFFDER-OS-002, OFFDER-UA-001, OFFDER-UA-002, P3-SCREEN-APP, P3-UA-DEFAULT, P3-UA-SETTINGS`。两对 OS 等价表达只在相同 R01 测量域内归并，得到 10 个规范关系身份；原来源身份保留。它们不是已选中的报警规则。

旧 observation_only 中的 UA 表面类别、UA 快照等值和屏幕残差被纳入核心候选，不再要求先排除所有合法替代解释。合法 UA 覆盖、窗口/缩放差异、不同渲染路径继续作为反例和归因限制。旧七条仅作为人工历史基线。

测量限制仍有效：没有独立 Browser 的 9 项保留结构缺测；无法解析/缩减的型号和 OS、软件/掩蔽/多义 GPU 家族、非正尺寸/DPR、缺失和质量不足均为 U。不会把缺 Android token 的桌面 UA 当作一个已解析的 Android 版本冲突。OFFDER-GPU-001 实际检查 WebGL 后端词，Native 字符串仅作存在前提，因此归入诊断；其旧标题不能替代真实多表面比较。未新造核心跨层谓词。

为避免单层对手被人为削弱，另外固定 104 个注册字段的有限控制编码：Native48、AppWeb38、Host18，含布尔值、训练折数值分位点和明确的 UA/platform/languages 长度解析，加上既有同层关系。排除时间身份、任意字符串词表、hash 和错误文本。这些是后续 R02/R03 的声明接口，本轮没有求阈值或提取真实矩阵。

## 2. 测量与模型合同

T 由每个原子的明确条件决定。例如 NW-002 的条件是“版本不等”，原 COUNTEREXAMPLE 映射 T；OFFDER-OS-001 的条件是“版本相等”，同一原结果映射 F。P3-UA-DEFAULT 的 T 是字符串相等；NVW-005 的 T 是 debug 与 cleartext 同时开启。安装器等无论取何值都输出 CONTEXT_OBSERVED 的旧摘要不产生可学习布尔条件。

保存 value/available/reason、原 outcome/reason、字段状态、执行状态与缓存来源。U 的否定仍为 U；AND/OR 采用已保存的完整三值真值表。空模型为 EMPTY_MODEL/弃判，执行失败为 FAILED，均不冒充 NO_ALERT。显式常量不报警和全弃判作为参照单列。关系/原子覆盖、子句覆盖与最终决策覆盖分别计数。

旧原谓词和 outcome 保持只读。R02 仅在输入、谓词、参数和测量域完全一致时复用 final_v3_v2 的 original_result，不按旧 risk_candidate_eligibility 挡住新学习，也不直接继承混入归因前提的旧关系门控。同阶段另一历史方法不是第二个样本。46 个旧 S06 未执行阶段及新测量域需要的提取留到获授权的 R02。

## 3. 数据角色与划分

262 阶段全部登记；监督范围仍为 54 attack、54 pre、54 post。54 UNKNOWN 时间对照、45 低证据和 1 不完整阶段保持描述性。31 个材料包含空失败包都有去向。MTC 的角色通过原完整清单引用，全部无监督负例和前瞻资格。

已生成 3 个 LOEO 与 14 个 LOCO 外层折，每折全部 262 阶段都有训练侧、测试侧或对应描述侧归属。主 LOEO 使用事前固定参数，不做无法解释的稀疏内层调参；模型集合仍只在训练折学习。配置留出允许共享环境，不能称为机制独立或环境独立泛化。机制分区证据不足，保持 UNVERIFIED。详细成员、标签支持、混杂和回退见 `SPLIT_FEASIBILITY.md`、`FOLD_MANIFEST.json`。

现有材料都已经暴露，外层仅提供后续拟合隔离下的回顾性内部评价。缺少前瞻确认只限制最终确认主张，不阻断 R02。没有补采或人工全面重标要求。

## 4. 学习目标和有限范围

- 整体集合目标：最大化配置等权、配置内环境等权的 MacroTPR，减去 `0.005 × (子句数 + 文字条件数)`。机制权重未核实，不填造。
- 主 clean 预算 α=0.05，敏感性仅 0 与 0.10；按 `floor(α×训练clean阶段数)` 限制 OR 并集报警。三个 LOEO 训练 clean 分母为 90/96/30，主预算为 4/4/1 次。外层效果不能选择操作点。
- 攻击、pre、post 分别要求至少 80% 决策覆盖；训练执行失败必须为 0。支持度仅在训练折计：至少 3 个完整可评估三态、至少 2 个攻击三态满足该文字/子句，至少 1 包/1 环境，保留专门规则的可能性，并披露相关性。
- 主方法为单关系文字的 OR，正反极性都可学；最多 6 子句。预定有限 AND 对照长度最多 2，总文字最多 12、复杂度最多 18；禁止同原子正反并存、重复/包含子句和同家族 AND。同家族最多 2 子句，等价来源不叠加支持。
- 固定 seed=20260924，不搜索 seed。贪心每 fit 最多 60 秒，有限 IP OR/DNF2 各 120 秒，1 线程，最多 4,096 候选子句；当前 10 个规范核心原子按不同家族长度 2 生成最多 188 个子句。单层文字上限每层 512。
- 贪心无正增益、长度用尽或超时停止，最多一次反向剪枝；并列按目标、MacroTPR、clean 报警数、覆盖、复杂度、规范 ID 确定。找不到可行访问模型不等于证明不可行。IP 如实记录 incumbent/bound/gap；无解、超时、缺求解器都有独立状态。
- 后续预定 fit 上界 75（相同 SRC-111 可复用），总限 200 作业/6 小时；不足时保留 NOT_RUN。真正列生成默认关闭，只登记有条件扩展的接口和 300 秒/50 轮/4,096 列预算，不能把有限 IP 称为列生成复现。

比较包含历史七条、同合同直接核心 OR、贪心集合、有限 IP OR/DNF2、同层重训练、来源八组合重训练、拟合后删来源/遮蔽的独立表、配置迁移和成本解释。当前 H 没有可供 App177 监督学习的核心跨表面项，因此 SRC-000/SRC-010 的核心池为空；应保留 EMPTY_MODEL，不伪造 H 的正收益，也不能据此断言 H 对其他表示/表面无用。

指标保留固定分母、未知、失败、弃判和完整三态；Fig.1–6 及核心表规定源长表、层次、分母和无数据状态。来源重训练与事后删除分开。时间对照/MTC 无相应真值时 TPR/FPR 保持不可评估。本轮没有真实效果图或理想数值。

## 5. 文件与复核

配置目录 `hybridguard_agent/config/rule_learning_v1_20260924/`：
`study_protocol.json`、`candidate_grammar.json`、`measurement_contract.json`、`split_policy.json`、`learning_search_space.json`、`metric_spec.json`、`experiment_matrix.json`、`figure_spec.json`。

本目录必需交付：`DATA_ROLE_LEDGER.jsonl`、`GROUP_SUPPORT.csv`、`SPLIT_FEASIBILITY.md`、`EXPOSURE_HISTORY.json`、`REFERENCE_READING.md`、`STEP_REPORT.md`、`VALIDATION.json`。

最小补充台账/核对：`CANDIDATE_LEDGER.jsonl`、`CONFIGURATION_REVIEW.json`、`MATERIAL_FLOW.jsonl`、`MTC_ROLE_DECLARATION.json`、`SINGLE_SURFACE_FIELDS.json`、`SPLIT_MEMBERSHIP.jsonl`、`FOLD_MANIFEST.json`、`GROUP_GENERATION.json`、`CONTRACT_SCHEMA.json`、`PROTOCOL_BINDING.json`、`READ_ONLY_BASELINE.json`、`REBUILD_CHECK.json`、`FOCUSED_CHECKS.json`、`SUMMARY.json`。

两个脚本仅作静态工作：`hybridguard_agent/scripts/prepare_rule_learning_r01.py` 生成元数据；`hybridguard_agent/scripts/validate_rule_learning_r01.py` 验证 schema、来源/字段/标签/成员、支持/预算、合成真值/分母及只读边界。没有导入检测器或学习器。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/validate_rule_learning_r01.py
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/prepare_rule_learning_r01.py --output <全新目录>
```

验收文件由验证脚本的 `--write` 首次保存；已有验收拒绝覆盖。曾因完善配置出现新协议 digest 待刷新，已只更新本轮小配置绑定。12 份生成元数据在临时新目录重建后逐文件一致。只做所引用历史文件 size/mtime 和相关 Git diff 核对，没有重复哈希历史大文件。旧冻结目录、标签、谓词、S06 结果均未改；原有 Android/TLS/build 工作区变更保留。

R01 的静态合同具备进入 R02 的技术前提；实际关系覆盖、训练可行性、检出能力、独立机制迁移和前瞻有效性尚未验证。当前状态只更新 R01，R02–R10 仍待授权。等待用户验收后停止。
