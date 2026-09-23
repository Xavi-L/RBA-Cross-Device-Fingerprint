# S03-R：关系、风险资格与归因合同修订

合同版本：`formal-manipulation-relation-risk-attribution-v2`。审查基线：`66f9cdc2d40c41ccec0999c7a6c8d68c0a1b415f`。审查日期：2026-09-23。v1 配置、验收目录、来源归属、家族、重叠矩阵及原测试均保留。本文件是独立修订，不反写 S03 v1 的零候选结论。

## 1. 为什么修订

源码复核确认：v1 `decision_role()` 没有返回 `alert_candidate` 的路径；八条建议候选在可观测字段合格后，仍因未证明“始终未被合法覆盖”或“实际物理渲染路径相同”而返回 UNKNOWN。这把风险线索要求提高到了强归因要求，也把可比较的关系压成不可评估。

改变结论的依据是合同逻辑与已有源码：Native/UA 型号、Android 主版本、已识别 renderer 家族的关系可以直接在声明字段上求值；授权、恶意意图、连续来源或物理路径则不是这些字段的输出。发现/开发记录只支持研究某种关系，不证明攻击检出能力。v2 将这两层与风险资格分开，没有新挖规则、调整阈值、查看正式预测挑规则或重新审计全部官方文档。

## 2. 三个独立轴

| 轴 | 状态 | 含义 |
|---|---|---|
| A `relation_applicability` | SUPPORTED / UNKNOWN / NOT_APPLICABLE | 当前字段是否允许按声明语义评估关系。SUPPORTED 不表示关系成立，更不表示攻击。 |
| 关系结果 `relation_result` | MATCH / COUNTEREXAMPLE / UNKNOWN / NOT_APPLICABLE / NOT_EVALUATED | 原关系的一致、冲突、不可判断、不适用；有限 probe 范围之外为未评估。 |
| B `risk_candidate_eligibility` | ELIGIBLE / NOT_ELIGIBLE / UNKNOWN / NOT_APPLICABLE | 在统一研究范围内，是否允许该关系作为待评价风险线索。关系一致的输入也可 ELIGIBLE；资格不是报警。 |
| C `attribution_certainty` | 本合同始终 UNKNOWN | 允许字段不能确定是否攻击、是否未经授权或是否恶意。C 不向 A/B 反向填入条件。 |

对已审定的候选关系，缺少 A 的字段：A=UNKNOWN、B=UNKNOWN。仅缺少额外风险参照：A 可以 SUPPORTED 并产生关系结果，B=UNKNOWN。明确的软件渲染或错误产品语义：A=NOT_APPLICABLE。明确观察/上下文角色始终 B=NOT_ELIGIBLE，包括字段缺失或关系有冲突的情况。未知归因可以与 SUPPORTED、ELIGIBLE、MATCH 或 COUNTEREXAMPLE 同时存在。

`alert_candidate` 沿用计划枚举，含义限于“可进入研究风险评估的候选关系”。以后若 S04 产生风险报警，其含义必须是**声明研究范围内的疑似操纵／风险提示**，不是确定性攻击真值、恶意意图或已校准攻击概率；`calibrated_attack_probability=null`。

## 3. 统一研究范围与不能软化的条件

范围版本 `featureapp-reported-identity-coherence-research-v2` 在 `research_scope.json` 中统一声明，八个来源条件全部引用同一份。Native 是声明干预未修改的相对参照，不是可信硬件根；规则比较当前 FeatureApp 的报告身份和渲染实现，不能证明物理设备身份。合法 UA、进程属性覆盖、OEM 差异、渲染路径变化都仍然合法；将来的误报必须按独立标签保留，不能靠改标签消除。

A 继续要求显式 observed、可用质量、正确类型、有限值、可解释语义；版本零值、opaque/多义版本、K 缩减身份、掩蔽型号、多个 model token、非 Dalvik 的 System agent、未知/多义 renderer 都不能强行比较。SwiftShader、llvmpipe、softpipe、swrast、lavapipe、swangle 不能作为硬件族证据。ANGLE 字样本身不代表 Windows，也不代表冲突。

B 的额外约束同样是当前字段条件。App UA 候选要求 default/settings 字符串可用且一致，default 的型号或主版本与 Native 参照相符；明确 settings 自定义是合法上下文，B=NOT_ELIGIBLE。default 缩减、别名/版本参照不明则 B=UNKNOWN。System 型号候选也要求 default UA 的显式型号与 Native 命名相符，限制别名解释；这不把 default 快照认证为连续来源。System OS 候选只在明确 Dalvik 与可解析主版本域内讨论进程属性自洽，不宣称当前 JS UA。

这里的 `settings_user_agent` 是 S02 允许的当前指纹字段，来自 WebSettings 快照；不是攻击配置或运行元数据。标签、工具、执行 config、phase、路径、session/install/group、回执、日志和未来 post 都不能选择或补充研究范围。

## 4. 逐候选修订

下表简写的精确路径由 `source_bindings.jsonl` 的 `dependencies` 和 `applicability_policy.json` 的 `additional_risk_required_fields` 固定；没有新增采集字段。

| ID / 来源 / 家族 | v1 硬前提 | v2 A：关系条件 | v2 B 与角色变化 | v2 C / 合法反例 / 影响 |
|---|---|---|---|---|
| NW-001 / E / model_app_ua | 完整未覆盖来源与采集期间稳定性 | Native 型号和 App UA 单一显式 model-before-Build token；不恢复 K，不猜别名 | observation_only → alert_candidate；default/settings 一致，default token 与 Native 命名吻合；不明参照 UNKNOWN | 覆盖是否授权、采集间隔是否发生合法变化仍 UNKNOWN。DevTools 覆盖、OEM 别名可能构成合法反例；只提示报告身份不一致。 |
| NW-002 / E / app_os | 无法完全排除合法覆盖即 UNKNOWN | Native 和 App Android 主版本在严格/原解析器共同有效域，排除 Android10/K 与错误产品语义 | observation_only → alert_candidate；default/settings 一致且完整 default 主版本与 Native 相符 | 不证明默认链连续或覆盖未经授权；合法自定义 UA、兼容性覆盖、预览/opaque 值限制保留。 |
| OFFDER-OS-001 / O_u / app_os | 同上 | 与 NW-002 同一 A | observation_only → alert_candidate；与 NW-002 同一 B | 官方定义支持主版本关系的研究假设，不是官方攻击判定；不增加独立家族票。 |
| NVW-001 / E / model_system_agent | `http.agent` 必须证实从未覆盖 | 明确 Dalvik 及单一 model token，可解释的 Native 型号 | observation_only → alert_candidate；default App UA 型号与 Native 命名参照吻合；只研究进程属性自洽 | `System.setProperty` 合法覆盖、OEM 构造差异、预览版本仍可解释冲突。不是当前 JS UA；AOSP 默认与 Native 共源，不能称独立身份根。 |
| NVW-002 / E / host_os | 未证实合法 host 来源就 UNKNOWN | 明确 Dalvik，Native/agent 均可解析为正主版本 | observation_only → alert_candidate；统一声明相对 Native 的进程属性一致性假设 | 可变属性的来源与授权仍 UNKNOWN；合法属性覆盖可以误报，不能改成攻击标签。 |
| OFFDER-OS-002 / O_u / host_os | 同上 | 与 NVW-002 同一 A | observation_only → alert_candidate；与 NVW-002 同一 B | 保留官方派生来源，和 E 等价表达共享家族；不声称额外独立设备证据。 |
| NW-005 / E / native_app_gpu_family | 必须证明同一物理路径并完全排除 host/remote/hybrid | 两个 renderer 各解析为现有名单中的唯一硬件族；软件/掩蔽/未知/多义不比较 | observation_only → alert_candidate；有限的报告家族一致性假设，不要求字符串认证物理路径 | 正常不同路径、混合渲染等仍是合法替代解释，C=UNKNOWN；同族也不证明同 GPU/设备。 |
| OFFDER-GPU-001 / O_u / native_app_gpu_family | 同上 | 可观察有意义的 backend marker，继续排除软件/掩蔽的强比较 | observation_only 保留；B=NOT_ELIGIBLE | Direct3D/Windows 是后端词，不是两个已识别硬件族的冲突。正常 host/translation 反例削弱产品排除前提；不能为增加 O_u 收益而晋级。 |

以上得到 7 条候选、5 个家族，是逐条裁决结果，不是验收目标；没有要求来源组数量对称或都获得正收益。

## 5. 审查依据与局限

依据均为审查基线已有内容。下列 Python/配置路径以 `hybridguard_agent/` 为基准；Android 文件位于 `android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/`：

- `research/manipulation_eval/provenance.py`、v1 source/role/applicability/family 台账：确认旧角色和不可观测条件如何合并。
- `research/mtc_closed_resource.py::model_token/gpu_family/evaluate` 与 `config/mtc_closed_resource_protocol.v1.json`：沿用唯一 token、原有硬件族及声明发现/开发范围。NW-001、NVW-001、NW-005 的筛选仅是关系研究依据，不是新检出证据；没有重新加载发现/开发或保留集输入。
- `evidence/extractor.py::_android_major/_ua_android_major`、`rules/executor.py::_evaluate`、`official_semantics/evaluator.py::_evaluate_compiled`：保留 OS 主版本的原关系和 E/O_u 归一化结果。严格门控排除旧解析器可从任意字符串误提取数字的区域，不放宽预览/opaque 值。
- `ExpandedFingerprintCollector.kt` 241–242、394–395、472 行与 `MainActivity.kt` 165 行附近：default UA、可变 System 属性、同值 GPU 拷贝和 JS 前 settings 快照的实际来源。未修改采集代码。
- S03 v1 `primary_source_review.json` / `SEMANTIC_DECISIONS.md`：复用已核实的 WebView/Browser 区别、合法 UA 覆盖、AOSP 默认构造、ANGLE/软件/host 渲染语义。不可变文档修订和 AOSP 历史实现缺口仍为 UNKNOWN，本轮没有开展全量联网文档审计。

NW-002/NVW-002 的早期逐条经验过程仍不完整；O_u 仍是“当前未标记本轮经验筛选的官方派生”，不是纯官方。v2 不用合法反例的存在推导“关系不可测”，也不用关系可测推导“反例非法”。新增 default 参照是统一的保守研究资格条件，不是按标签选择的例外，更不是新的正常样本筛选。

## 6. 其他不可观测前提没有统一软化

原有 16 条带 `unobservable_alert_preconditions` 的规则逐条列在 `precondition_classification.json`：

- UA 默认链/覆盖授权与 System 属性未覆盖证明，主要移到 C；A 的解释条件及 B 的可观测参照仍保留。
- GPU 的软件、掩蔽与字族唯一性是 A 的必要条件；真实物理路径/授权属于 C。OFFDER backend marker 另有 B 依据不足，继续观察。
- `P3-X-DPR`、`P3-X-SCREEN-SIZE`、`P3-SCREEN-APP`、`P3-SCREEN-BROWSER` 的窗口、zoom、display 等价影响旧等式含义，仍是 A 未解决条件，继续 UNKNOWN/观察。
- `OFFDER-UA-002`、`P3-UA-DEFAULT`、`P3-UA-SETTINGS` 的原通用等值解释仍缺采集间隔/实例条件，不升级风险角色。
- `P3-UA-REDUCED-BROWSER` 的 UA 未覆盖来源属于 C，但冻结 >=107/Android10 谓词的产品范围问题另影响 A；保留该缺口、观察角色和缺 Browser 时 UNKNOWN。

其余角色不变。ADB、模拟器、调试、桥接、网络、部署及 touch=0 不直接产生风险票。合法 false、零 touch、空列表继续可作为观察；无独立 Browser 时不补造。

## 7. 可行性与来源结构限制

35 个明确标记的合成夹具覆盖每条候选的一致、冲突、缺失、类型无效及不适用。七条候选的一致/冲突路径均为 A=SUPPORTED、B=ELIGIBLE、C=UNKNOWN；它们证明路径可达，不证明真实样本覆盖、准确率或风险校准。`SYNTHETIC_FIXTURES.jsonl` 和 `SYNTHETIC_RESULTS.jsonl` 保存输入、期望及真实执行结果。

E 有 5 条候选/5 个家族，O_u 有 2 条/2 个家族；H、C 均无风险候选。O_u 的 app_os/host_os 与 E 的同族表达使用相同 v2 条件，在共同有效域等价。因此保留 E 时，O_u 不增加候选家族；在计划中的固定家族 OR 逻辑下，其零二值增量会有事前结构原因，不能解释为官方知识无价值。H/C 的二值增量也不能用作来源无价值的实验结论。

57 个原 ID、E23/O_u9/H14/C11、27 个家族、原重叠矩阵、C 公共组和八个来源 ID 集全部保留。八组合的 v2 门控统一替换为三轴合同，不能只对某个来源放宽条件。删除 O_u/H 谓词仍保留公共语义门控，仍只能称来源分组消融。

## 8. 输出安全与后续边界

v1 和 v2 生成入口现在都必须显式传入 `--output` 与 `--config-dir`，并在任何写入前同时检查两者：不得相同/嵌套，不得指向 S01/S02/S03 v1 或其祖先/子目录（含符号链接解析），不得覆盖非空目的地。仅换 output 会报参数错误；显式旧 config 也会拒绝。v1 的角色和门控函数未改，原 15 项测试保留且通过。

本次使用独立 `03r_role_gate_v2` 输出与 `formal_manipulation_role_gate_v2` 配置，完整绝对路径记录在 `GENERATION.json`。32 项聚焦测试由原 v1 15 项和新 v2 17 项组成，全部通过。

S04 尚未实现或运行。后续若单独授权，需显式采用本版本 A/B/C 和研究范围；只有 A=SUPPORTED 且 B=ELIGIBLE 的候选关系可进入后续家族决策，C=UNKNOWN 不再自动否决，也不能被改成已证明攻击。必须继续区分未知/不适用/观察/执行失败，不得把弃判当 NO_ALERT。具体家族聚合仍属于 S04。

S01 时间对照 no_intervention=UNKNOWN 及 FPR 限制、L1/缺日志和环境关联限制保持不变；没有真实样本预测、TPR/FPR、阈值变更、模型调用、补采或补日志。真实检出、误报、来源收益、独立设备泛化、未经授权来源和恶意意图仍不可由本步声称。
