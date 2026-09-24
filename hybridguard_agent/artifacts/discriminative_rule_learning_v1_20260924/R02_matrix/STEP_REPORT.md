# R02 状态感知关系矩阵与泄漏隔离

日期：2026-09-24。审查及执行基线：`283ff801ea3cfddce231c928017185db0f34683b`。
新提取实现：`r02-fixed-measurement-v1`；测量合同仍为 R01 的 `r01-measurement-v1`。
协议绑定：`4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`。

R02 已完成矩阵、行/列/来源登记、折权限、缓存血缘与聚焦验收。`VALIDATION.json` 记录 **12 项产物检查、29 项合成测试通过**。真实拟合、最终风险预测、全量标签排名、旧 S07 和 R03 执行次数均为 0。当前结论只涉及测量转换、对账和隔离，不涉及检出率、误报率、已选模型或算法收益；外部 R02 验收仍待审查。

## 1. 授权、版本和历史保护

- 已阅读 `RESEARCH_MAINLINE.md`、当前执行计划/状态、R01 八份配置、57 项完整候选台账、262 行数据角色和 17 个划分成员清单。
- 当前 HEAD 等于审查提交；影响本步的主线、计划、R01 配置/产物和被复用的谓词实现没有后续差异。262 份 S02 输入与 S06 冻结盲化输入逐记录相等；216 份 final 运行记录的输入投影也逐记录相等。9 个相关源码/目录/字段规范文件与 S06 源快照逐字节相等，具体清单见 `BINDING_REVIEW.json`。
- 本次用户对 R01 的外部验收独立记录在 `R01_EXTERNAL_ACCEPTANCE.json`，指明审查提交及授权范围。R01 原 `VALIDATION.json`、报告和历史中的 PENDING 时点记录均未覆盖。当前调度会另记 R01 外部验收和 R02 完成事件。
- 没有重跑 R01 旧验证脚本，也没有把旧工作区 mtime 或旧 `user_acceptance=PENDING` 当作当前语义前置条件。当前复核检查配置绑定、候选/来源版本、S01 资格、成员及测量语义。`READ_ONLY_CHECK.json` 只记录本次 R02 运行前后的文件 size/mtime 相等，与原 R01 工作区保护记录分开；不重复哈希历史大文件，不重建 R01、不改时间戳。
- 开发试运行位于 `/private/tmp/hybridguard-r02-dev-*`；正式目录一次性生成，已有产物/验收拒绝覆盖。初次调试修正了旧目录项省略空 `parameters` 时的读取方式，不修改旧目录或 R01 参数。

## 2. 行、候选与单元对账

全部 262 阶段各占一行，使用原 `opaque_id`；历史 final/legacy 两种方法不会产生两个样本。同内容但不同 ID 的评估单元不去重，合成测试覆盖这一边界。

| 材料角色 | 行数 | R02 处置 |
|---|---:|---|
| 准入三态 | 162 | 54 attack、54 pre、54 post，保留 S01 监督资格 |
| UNKNOWN 时间对照 | 54 | 描述性，无监督标签 |
| 较低证据 | 45 | 描述性，无监督标签 |
| 不完整尝试 | 1 | 描述性，无监督标签 |

57 项仍按 E23/O_u9/H14/C11 登记，原用途、来源、参数、版本、依赖及候选纳入理由均保留。主学习视图只使用 R01 指定的 12 个 App177 核心原子，并在规定的两对 OS 别名核对后形成 10 个规范偏差原子。其他项保留在登记/同层/诊断视图中，没有按全量输出筛选候选。

| 单元最终状态 | 数量 |
|---|---:|
| 登记总单元：262 × 57 | 14,934 |
| 可用 T/F | 10,622 |
| 测量不可用 U | 3,264 |
| 执行 FAILED | 0 |
| NOT_REQUESTED：四项无布尔条件的上下文摘要 | 1,048 |

最后一类为 NVW-004、OFFDER-NET-001、TOL-001、WVWEB-002：保留诊断登记和已有原 outcome，不把统一的 CONTEXT_OBSERVED 伪造成可学习布尔值。它们的逻辑 state 为 null，区别于 U。对应原始字段如属于 R01 控制字段清单，可通过声明的单层编码进入对照。

## 3. 缓存复用与必要提取

优先缓存为 S06 `final_v3_v2`、App177、SRC-111 的 `original_result`。逐单元核对输入投影、目录/参数、谓词及版本、依赖字段状态、原事件有效性，并重新检查 R01 测量域。旧 `risk_candidate_eligibility`、参与报警标记和旧归因门控不进入新资格或逻辑值计算。

| 计算路径 | 数量 | 含义 |
|---|---:|---|
| 直接复用原谓词结果 | 8,772 | 绑定及当前测量域通过，未再次执行谓词 |
| 必要的新版本单关系求值 | 1,850 | 全部来自旧缓存未覆盖的 46 个描述性阶段 |
| 仅重新判定测量不可用 | 3,264 | 不运行无意义谓词；记录字段/域原因和旧 outcome |
| 无布尔原子，不请求求值 | 1,048 | 诊断摘要保持登记 |

缓存覆盖本身是另一个维度：216 × 57 = 12,312 个原单元；46 × 57 = 2,622 个未覆盖单元，其中 46 行确认为 45 个低证据阶段和 1 个不完整阶段。已保存的 1,944 个 NOT_EVALUATED 单元均为缺 Browser 依赖。输入/目录参数/源码版本绑定不一致单元为 0；有缓存但被 R01 测量检查判为不可用、没有直接复用为布尔结果的单元为 2,676。所有单元保留，拒绝复用不等于丢弃行。

新求值仅调用已冻结的单关系函数，先限制到其依赖字段；没有运行完整检测器、风险聚合、模型或上游验证器，没有增加新跨层谓词。提取版本与旧谓词版本分开保存。`atom_records.jsonl` 保留原 outcome/reason、R02 `relation_result`、字段状态和缓存血缘；即使新提取与旧结果不同，也不覆盖保存的旧原值。未覆盖、未执行、合同不一致、测量域拒绝分别有状态。

U 原因：Browser 结构缺失 2,358；传感器存在条件的前件为 False 524；GPU 家族未知/掩蔽/多义 163；软件渲染 99；OS 解析或解析器共同域不足 60；无显式型号 Build token 30；非 mobile UA 不适用于 mobile-only 条件 30。类型错误属于测量不可用；记录 envelope 非法或关系执行异常属于 FAILED，合成夹具分别核对。

## 4. T/F/U、极性和等价归并

每个原子使用 R01 台账中的 T 定义和 outcome 映射。NW-002/NVW-002 的版本“不等”为 T；OFFDER-OS-001/002 的版本“相等”为 T，因此不能统一规定 MATCH=T 或 COUNTEREXAMPLE=T。

核心规范视图按 `direct_OR_deviation_polarity` 转到“偏差”为 T，再按相同 R01 profile 检查 value、availability、evaluation_status 和测量原因。两对别名的全部 **524 个逐行检查一致，冲突 0**；全部来源别名继续保存。来源子集可保留其允许的别名并维持规范偏差方向，不额外增加支持。冲突会输出 FAILED，而不是选取有利的别名。OFFDER-UA-002 的 trim 比较和 P3-UA-DEFAULT 的精确字符串比较没有错误合并。

逻辑否定只接受 T/F/U，U 的否定仍为 U；FAILED 和 NOT_REQUESTED 的 state 为 null，不能参与三值否定。没有运行最终 OR/AND 报警或学习极性。

29 项合成测试包含手工预期的所有 53 个已定义目录条件及原谓词一致性、OS 正反方向、来源子集、别名域冲突、UA 缩减/缺 token/模糊解析、合法 UA/窗口差异、GPU 不确定性、传感器空列表/False 前件、类型与执行失败、缓存缺失/未执行/版本不符、字段遮蔽和 fit/transform 边界。验收不以“表中有值”代替这些语义检查。

## 5. 覆盖与单层对照

以下覆盖均为 **POST_HOC_DESCRIPTIVE 的测量可用性**，不是决策覆盖、训练支持、规则排名或检测效果；加载器不消费这些汇总来筛选规则。

| 视图（全部 262 行） | 列数 | 可用单元 / 应有单元 | 覆盖 |
|---|---:|---:|---:|
| 原核心 App177 | 12 | 2,792 / 3,144 | 88.80% |
| 规范偏差核心 | 10 | 2,298 / 2,620 | 87.71% |
| Browser 依赖登记 | 9 | 0 / 2,358 | 0%：结构不可用 |
| Native 同层目录对照 | 18 | 4,192 / 4,716 | 88.89% |
| AppWeb 同层目录对照 | 5 | 1,280 / 1,310 | 97.71% |
| Host 同层目录对照 | 5 | 1,310 / 1,310 | 100% |

162 个监督阶段的规范核心覆盖为 **1,416 / 1,620 = 87.41%**；100 个描述阶段为 **882 / 1,000 = 88.20%**。保留全部原列，不因覆盖低而在全量上删列。

R01 冻结的 104 个单层控制输入（Native48、AppWeb38、Host18）全部有可用的固定逐样本值；监督/描述分别为 16,848/16,848 和 10,400/10,400。这仅说明相应类型/测量合同可读。38 个布尔字段及明确 UA/platform 分类生成 **53 个固定相等条件**，三层分别为 20、16、17 列，当前可用率均为 100%。数值字段加 languages 长度合计 **62 个数值输入**只保存原始单样本测量，实际分位点、阈值及其布尔列尚未拟合；状态明确为 NOT_REQUESTED_REAL_FIT_NOT_AUTHORIZED，不能报告成已经完成的数值候选学习。

## 6. 隔离、权限和交付接口

特征矩阵只含 opaque join key、版本绑定、值/状态数组；标签、phase、tool、config、组、材料路径、三态关系保存在 `evaluation_index.jsonl`、行/折/来源/血缘侧表。纯转换函数不接收这些评价字段，推理 envelope 混入 phase/label 会拒绝。单层视图在派生前同时遮蔽其他层的值、状态和质量。

`fold_data.load_fold` 读取声明列并生成特征批次，不把侧表数据复制进特征记录。17 个折与 R01 成员完全一致：3 个环境留出、14 个配置留出；完整 bundle/三态保持同侧，配置留出仍明确共享环境，不重命名为独立机制测试。

`FoldData.assert_fit` 对支持度、排名、数值阈值、极性/组合选择和剪枝要求本折**完整 train 批次**，拒绝测试侧、描述侧、混入其他折或伪造行内容。R02 还拒绝真实 train 数据拟合，仅合成 `fixture-*` ID 可进入合成验证。`TrainQuantiles` 按冻结的线性分位点合同验证 fit/transform；测试极值和标签置换不改变训练阈值，transform 必须使用本折已冻结的 fit 状态，保留 U 和 FAILED。没有产出真实支持度表、标签排名、剪枝结果或学习模型。

主要文件：

- 矩阵：`candidate_matrix.jsonl`（X_value/state）、`availability_matrix.jsonl`（X_available/X_reason/status）、`core_matrix.jsonl`。
- 对照：`control_inputs.jsonl`、`control_field_states.jsonl`、`fixed_control_matrix.jsonl`、`fixed_control_manifest.jsonl`、`TRAIN_TRANSFORM_MANIFEST.json`。
- 侧表：`row_manifest.jsonl`、`candidate_manifest.jsonl`、`source_manifest.jsonl`、`evaluation_index.jsonl`、`COLUMN_MANIFEST.json`、`FOLD_INPUT_MANIFEST.json`。
- 追溯：`atom_records.jsonl`、`CACHE_LINEAGE.json`、`REJECTIONS.jsonl`、`ALIAS_CHECKS.jsonl`、`R01_EXTERNAL_ACCEPTANCE.json`、`BINDING_REVIEW.json`、`READ_ONLY_CHECK.json`。
- 验收：`MATRIX_SCHEMA.json`、`FOCUSED_CHECKS.json`、`FOCUSED_TESTS.txt`、`VALIDATION.json`、`SUMMARY.json` 和本报告。

`row_manifest.jsonl` 的 `input_ref` 沿用原 S02 input manifest 的相对引用，以原 `02_inputs/` 目录为根；`atom_records.jsonl` 的输入血缘另保存完整仓库相对路径。状态更新后的历史前缀、R01 冻结文件、R03–R10 待授权状态及无关工作区保留检查见 `FINAL_REVIEW.json`。

仓库根执行只读验收：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/validate_rule_learning_r02.py
```

需要复现矩阵时只允许新目录，不覆盖正式目录：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/prepare_rule_learning_r02.py --output <全新目录>
PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/validate_rule_learning_r02.py --directory <同一全新目录> --write
```

## 7. 留给后续的工作与停止点

R03 尚未执行：选择器、规则模型、风险推理、学习后的对照/来源适配、训练支持与剪枝、指标程序和相应合成验收仍待独立授权。R02 的权限/数值转换接口不构成真实训练授权。R04 冻结实际作业与资源后，R05 及后续步骤才可按各自授权执行 train-only 阈值/支持度/规则选择和折外风险预测。

真实关系覆盖已记录；所选集合可行性、检出率、误报率、模型收益、独立机制迁移和前瞻确认仍未评估。Browser 没有拼接，100 个描述阶段没有补标签，MTC 没有加入监督样本。R01 候选语法、划分、学习目标与原验证保持冻结；旧结果和工作区中无关 Android/TLS/build 改动保留。

完成后停在 R02，等待审查。不自动执行 R03，不自动提交或推送。
