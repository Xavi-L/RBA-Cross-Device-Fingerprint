# R03 选择器、合理基线和合成验证

日期：2026-09-24。外部审查基线：`daca1ff477383ded6b6c81600dbca1cb6270e9f9`。
R01 协议绑定：`4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`。

R03 已完成三种选择器、模型/三值推理/解释/指标、基线与来源/单层接口的实现及合成验收。**35 项聚焦测试通过；14 个有限 IP 小实例与独立穷举一致。** 结论只涉及实现和合成合同，不涉及真实检测效果、优于基线或非空模型。R03 外部验收为 PENDING；完成后停止。

## 1. 依赖、外部验收与保护

已阅读主线、当前计划/状态、R01 八份配置、候选/角色/划分合同及 R02 交付。HEAD 等于审查提交；本步相关前置文件不存在后继差异。复核八份配置和候选的小规模绑定、57 项登记、262 行角色（162 监督、100 描述）及 17 个折的原成员和权限，一致。

R02 外部验收独立登记于 `R02_EXTERNAL_ACCEPTANCE.json`。R02 原 `VALIDATION.json`、STEP_REPORT 和执行时点记录中的 PENDING/no-Git 叙述均保持不变；当前调度另记验收。没有回退、重建 R01/R02，也没有重跑历史时点的 mtime/PENDING 门槛。

`READ_ONLY_CHECK.json` 保存本次生成前后 629 份前置/历史文件 size+mtime 相等的记录；这是本次工作区保护，不是可移植语义绑定的替代。`BINDING_REVIEW.json` 单独记录配置、成员、来源版本和审查提交核对。未对历史大文件重复做哈希扫描。完整工作区和状态历史前缀检查另见 `FINAL_REVIEW.json`。

真实模型拟合、真实支持/排名/阈值学习、真实风险预测、来源重训练、矩阵重建、旧 S07、R04/R05、提交和推送均为 **0 / 未执行**。

## 2. 已实现算法与求解器

源码在 `hybridguard_agent/research/rule_learning/`；详细数学/运行说明在 `hybridguard_agent/config/rule_learning_v1_20260924/ALGORITHMS_R03.md`，不修改八份 R01 JSON。

| 算法 | 实现与状态边界 |
|---|---|
| GREEDY_OR | train 支持、正目标增量、整个集合 clean 报警预算、复杂度、每层覆盖；最多 6 次增加和 1 次字典序删除遍历；60 秒；没有可行访问模型不证明不可行 |
| FINITE_IP_OR | 同一个有符号文字池；精确编码报警并集和 T/F/U 决策覆盖；120 秒共享截止时间；按 R01 层次逐步求解并列条件 |
| FINITE_IP_DNF2 | 预枚举允许的单文字和双文字 AND，最多 4,096 子句；相同目标/预算/支持和禁止组合；有限问题的 bound/gap 单独记录 |

求解器为 **HiGHS/highspy 1.12.0**，NumPy **2.3.5**，Python **3.12.14**，macOS arm64，单线程，seed 20260924，relative/absolute MIP gap target=0，整数可行性容差 1e-9。当前独立运行环境见 `ENVIRONMENT.json`；依赖固定在 `requirements-r03.txt`。没有付费求解器或静默算法回退。

目标仍为配置等权、配置内环境等权的 MacroTPR 减 `0.005 × (子句数+文字数)`。整个集合的 clean 报警计一次并集，预算 `floor(alpha*N_clean)`；attack/pre/post 各至少 80% 明确决策覆盖。支持统计只从本折完整 train 批次的准入三态产生，别名不重复计支持。复杂度和每家族上限沿用 R01。

整数缩放和分阶段固定并列目标避免用 epsilon 改主目标。每个 incumbent 经三值集合逻辑再次验证，保存主目标 bound/gap、主目标最优性与并列完成标记。有限 IP **不是列生成**。求解不可行、超时有解、超时无解、求解异常和空候选分别记录；正常空模型及负结果保留。

## 3. 合成验收与可复核产物

`fixtures/` 保存 25 个程序构造的合成 recipe，其中包含预期被拒绝的分组/超限夹具；这些文件不是从真实矩阵采样或改 ID 得到。`FOCUSED_TESTS.txt` 保存全部 35 项测试名和通过记录。

| 手算或边界 | 核对结果 |
|---|---|
| 两规则各 1 次 clean 报警，24 clean、OP05 预算 1 | 各自可行、并集 2 次不可行，最终只选字典序 A；目标 0.49 |
| 同一例固定 OP00/OP05/OP10 | 空模型 / A / A+B，未在测试数据上选操作点 |
| 互补覆盖、冗余 | 互补例保留 A+B；同输出冗余例只保留 A |
| 一次后向剪枝 | A 先入选，B/C 后续使 A 冗余，实际删除 A，保留 B+C；完整轨迹保存 |
| 需要 AND 才可行 | 有限 OR 证实无可行模型；DNF2 选 A AND B，目标 0.985 |
| 正反极性、覆盖并列、低覆盖、最小支持 | 反向条件可以正常学习；覆盖并列优先覆盖更高者；低覆盖不当成低误报成功；支持不足被记录 |
| 三值逻辑、空集与失败 | 18 个二元真值表单元均一致；NOT U=U；选中失败不能被 T OR 或 F AND 遮蔽；NOT_REQUESTED 不当成 U |
| IP 对穷举 | 14 个 OR/DNF2 小实例的集合、目标和可行性一致，范围限于有限支持池 |
| 超时/失败 | 原生 HiGHS time_limit=0 返回无 incumbent 的 kTimeLimit；可行超时、执行错误及不合格 incumbent 分支使用明确合成注入验证 |
| 保存/加载 | 模型及单层编码器往返后的预测逐记录一致；修改冻结内容、重复写入模型被拒绝 |

`models/` 保存 **25 个合成模型**：24 个算法小例含 13 个 FITTED、11 个 EMPTY_MODEL，另加 1 个单层模型。另保存 **225 条合成示例预测**：216 条在 `synthetic_predictions.jsonl`，9 条在 `SINGLE_SURFACE_VALIDATION.json`。FAILED/超时政策的注入记录单独保存在 `MODEL_VALIDATION.json`，不冒充生产求解器失败率。

`training_traces.jsonl`、`selection_rows.jsonl`、`SYNTHETIC_DEMO_RESULTS.json` 保存训练侧支持、候选去向、实际 train 分母、选择/剪枝和来源解释。模型输入来源指向合成 recipe；原真实 input manifest 仅作为协议出处保留。合成样本数、模型数和真实材料数不混用。

## 4. 基线、来源与单层对照

HISTORICAL_SEVEN 使用严格方法/输入/版本绑定的已保存 final 结果适配接口，匹配 7 条旧资格规则；缺失、未核对或失败单元保留 FAILED。没有用 R02 新测量值模拟旧归因门控，也没有重跑旧检测器。历史 family 覆盖与新原子/子句覆盖分开。

DIRECT_CORE_OR 只使用规范偏差正方向；在合成原始别名上验证 12 个核心目录项归为 10 个规范身份，未按支持筛选。它按 R01 免除学习集合上限并报告实际复杂度。显式 ALWAYS_NO_ALERT/ALWAYS_ABSTAIN 与 EMPTY_MODEL 分开。

来源接口先限制原始允许别名，后规范化。NW-002 与 OFFDER-OS-001 的原始 T 方向相反，但在规范偏差视图一致；联合视图保留两别名、只计一次支持。E 单独与 O_u 单独保留各自来源。联合域冲突为 FAILED，不能污染不包含该冲突别名的来源条件。SRC-000 保留空池；8 个条件的接口登记见 `BASELINE_SOURCE_INTERFACES.json`。没有真实来源重训练，留给 R06。

单层接口消费 R02 声明的同层目录/固定控制/未拟合数值元数据，在派生前限制表面。53 个固定控制原子和 62 个数值输入保持区别；`UNFITTED_CONTROL` 不能直接交给选择器或三值预测器。数值只从自己的 train 拟合 0.25/0.5/0.75 线性分位点并去重；合成 0–17 得到 4.25/8.5/12.75。测试极值或被遮蔽的其他层失败不改变阈值。冻结转换器与模型一起保存，预测时不再 fit。

## 5. 权限、分母和指标

`access.synthetic_fixture(name)` 只发放内置合成数据能力，选择器不接受调用者提供的数据、`synthetic=True` 或改名的旧 FoldData。能力绑定完整 train 内容/成员/元数据/视图；测试、描述侧、跨折批次及被修改内容均被拒绝。R02 原有阶段限制作为权限错误处理，不转为算法 FAILED_FIT。

正式入口 `FormalFitRequest/open_formal_fit` 已声明必需的授权、冻结、资源、作业、协议/折/方法/来源/训练成员字段；**R03 中入口始终关闭**。仅传入所谓 R05/冻结标记不能获得真实 fit。能力是受信任代码中的工作流边界，不声称防御任意 Python 反射。R02 历史接口保持原样，其 synthetic 标志不构成新入口的授权。

训练侧分别保存实际 train/clean/各 phase 分母。预测每个预计 ID 独立给出 T/F/U、EMPTY_MODEL 或 FAILED；评价从 expected IDs 开始，漏行留作 FAILED。测试侧标签不改变固定模型预测；另一个一致的合成训练准入版本改变标签与角色后，所学模型由 A 改为 B，证明训练标签可以正常影响选择。

`HAND_CALCULATIONS.json` 的人工决定表用于指标算术，不是一个拟合模型的性能。3 个监督三态加 3 个未知标签行的手算结果为：TPR=1/3，clean 报警=1/6，决定条件下 clean 报警=1/4，精确 FTF=1/3，条件恢复=1/1，决策覆盖=8/12，弃判=2/12，失败=2/12，原子覆盖=17/24，子句覆盖=8/12。未知标签行不进入监督分母；正/负可识别上界分别为 1 和 1/2，不是总体置信区间。

`METRIC_VALIDATION.json` 核对 0 分母、无真值、缺失预测、分层统计及不同模型/轨道不能隐式混合；`LEAKAGE_VALIDATION.json` 核对权限和标签隔离。低覆盖不能仅凭零报警被描述成低误报模型。

## 6. 未执行分支与 R04 待绑定资源

- 真正列生成没有实现，R01 也未授权；本步不扩展谓词、语法、搜索范围或预算。
- 正式真实 fit 能力发放、全局作业预算调度、模型冻结后才读取外层输入的 runner、独立快照资源闭合和显式 OOF 汇总还未交付。这些是 R04/R05 的后续工作，当前接口明确拒绝运行。
- R04 须绑定 R01 八份配置和 digest、R02 原始别名/值/原因/血缘/角色/折、R03 源码/夹具、Python/HiGHS/NumPy/平台、单层字段和编码器、来源投影、历史七条实际输入/版本证明，以及预期 fit/model/prediction 清单、总预算和优先级。详见 `FORMAL_FIT_ENTRY.json`。临时 venv 不等于正式资源冻结。
- R06 的真实来源重训练、R07 的单层真实对照、后续独立机制/前瞻确认、成本和真实效果均未运行或未评价。

## 7. 复跑与停止

当前已验证的环境命令（仓库根）：

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/hybridguard-r03-venv/bin/python hybridguard_agent/scripts/validate_rule_learning_r03.py
```

可移植复核需 Python 3.12 的独立环境，按 `hybridguard_agent/config/rule_learning_v1_20260924/requirements-r03.txt` 安装固定依赖，再执行同一个验证脚本。默认系统 Python 未安装 HiGHS 时明确拒绝完整验收，不能把跳过 IP 称为通过。

`validate_rule_learning_r03.py` 只读验证保存的模型、预测、指标及夹具，同时运行合成测试。需要重新生成合成交付时，用 `prepare_rule_learning_r03.py --output <全新目录>`；已有目录拒绝覆盖。它不读取真实关系矩阵做拟合，不更新调度，不自动执行 R04。

当前状态更新为 R03 DONE / PASS_IMPLEMENTATION_AND_SYNTHETIC_ONLY / 外部验收 PENDING。R04 及后续保持待授权。未提交、未推送，等待审查。
