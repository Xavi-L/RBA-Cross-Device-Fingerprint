# 最小后续实施计划（未授权执行）

本计划不自动开启 V3、R10、独立确认、训练或采集。首个下一轮可验收里程碑只实现离线纯解析/状态模块与手工规格测试；不需要新增设备，也不读取真实样本计算候选。

## 两个优先方向

1. **语言 `RSR-LANG-FIRST-v1`**：完整支持域标签的首项关系。两字段及数组顺序已有；无拟合参数；能明确区别于长度和 primary 全列表成员关系。适用的历史采集来源仍须绑定，不能把当前源码当成全部历史 APK 证明。
2. **webdriver `RSR-WEBDRIVER-STATE-v1` 的 legacy 分支**：保持已报告 true，识别 observed false 的不可逆歧义，保留来源失败原因。完整原始状态 schema 只做解析接口，不假装旧 false 已恢复。其价值是可解释状态和覆盖报告，尚无新检测机制证明。

不设第三备选。固定时区无需新身份；UA 与内存尚缺关键配对/运行前提；MIME 只是旧数值条件加可信范围门控。全部一起改将同时改变采集、门控与表示，难以归因，也没有足够输入支撑。

## 可直接施工的文件与接口

下表全是**未来新增路径**，本轮不创建这些模块；旧 `rule_learning`、`rule_learning_v2`、采集器及其测试文件均不修改。

| 未来路径 | 最小职责 | 验收条件 |
|---|---|---|
| `hybridguard_agent/research/rule_semantics_revision_v1/contracts.py` | `SemanticCell(value, available, evaluation_status, reason, candidate_id, version)`；状态枚举与规格注册；分离 payload 和可信来源 binding | T/F 有 bool 值；U 为 value=null/available=false/status=OK；FAILED 为 status=FAILED，不能投入三值运算 |
| `.../input_adapter.py` | `read_observation(payload, field_ref)` 与 `validate_source_binding(binding)`；只读 features/status/quality，保留语言数组顺序；不接收 label/phase/config_id | 非 observed 或非 observed_value 为 U；非法 envelope 为 FAILED；无类型强制转换；缺来源绑定为 U |
| `.../language.py` | `limited_full_tag(value)` 与 `web_language_first_difference(observation, binding)`，严格按候选规格 | 仅大小写归一；保留地区/脚本；不引入训练词表、不补 fallback，不调用 Native Locale |
| `.../webdriver.py` | `webdriver_reported_state(observation, mode)`；mode=legacy_projection_v1 / raw_observation_v1 | legacy true=T，false=U；raw 成功 boolean false 才 F；读取错误/缺失分别 U；矛盾 record 为 FAILED |
| `.../manifest.py` | 记录语义/门控/采集/selector 的独立版本与旧身份重叠；只注册这两个优先方向 | 新 true 分支与旧 W03 不当两份独立证据；不改旧原子状态；来源 ID 可追到本设计 |
| `hybridguard_agent/tests/test_rule_semantics_revision_v1.py` | 手工、无设备、无真实标签的重点单元测试 | 覆盖下列边界；不导入实验 main、不 fit/predict，不扫描 attack/clean 文件 |
| `hybridguard_agent/tests/fixtures/rule_semantics_revision_v1/specification_examples.json` | 从本规格复制且标明人工例与契约版本 | 所有例均 `SPECIFICATION_EXAMPLES`、real_sample=false；不作为性能数据 |

`.../` 均指上表同一个 `hybridguard_agent/research/rule_semantics_revision_v1/`。不得通过直接调用旧实验入口顺带运行真实记录。需要 schema 新字段时另建新契约；旧 study_protocol 的 allowed_payload_keys 和禁入字段仍有效。

## 重点语义验收

- 语言：正常多项 fallback 与缩减单项 F；大小写 F；完整标签的地区/脚本差异 T；language 位于第二项 T 而旧 primary 成员关系 F；空数组、缺值、必要标签不支持、来源未配对 U；非法 envelope FAILED。尾项不参与首项比较，避免用不相关尾项把已可比较关系强制 U。
- webdriver：legacy observed true T、false U；fallback false/runtime_error U 且原因不同；raw API absent/非 boolean U；raw API存在且false F；未知内核仅能作“报告值”解释；互相矛盾的原始观察结构 FAILED。hash 枚举错误不得伪造为 getter 失败。raw 模式只依赖独立保存的 observation 状态，不能被旧兼容 bool 的整组 automation 错误覆盖；legacy 与 raw 模式由登记契约选择，不按结果回退。
- 公共状态：U 不转 F；FAILED 不进入普通 OR；缺字段不当攻击；更改业务 App 名、label 或 phase 不应影响模块（接口本身不接收它们）。
- 身份：B 的全列表 primary 关系不被首项关系覆盖；旧 W03 不被新状态版本重写；`V2REL:FIXED_NATIVE_VS_WEB_OFFSET_DIFFERS` 不重复注册。

模块验收完成即停止。若用户随后授权真实材料准入或实验，再进入以下独立阶段；通过规格单测不代表检测有效。

## 真实材料之前需要独立闭合的条件

| 家族 | 缺口与最小解决件 | 当前允许的结论 |
|---|---|---|
| 语言 | 用已有采集构建/来源登记建立同次 Navigator 读取的关联；无法关联保留 U，不看攻击得分决定准入 | 不需要新设备即可实现公式；历史覆盖率未核验 |
| webdriver | 历史原始 false 不可恢复；未来若采集改版，分别记录 API presence 检查与一次 getter 读取；保存 presence_read_status/value_read_status、typeof、boolean、realm 关联；presence 检查异常不等于 API absent，两次观察不宣称原子化 | 先实现 legacy 信息损失表达；原始采集是另一个版本和授权 |
| UA | Host独立保留实例/文档/epoch、当前设置前后读数、probe关联与传播完成条件 | 当前只能描述旧快照差异，不能证明新候选门控 |
| 内存 | 运行构建与 AOSP/Chromium 路径绑定；低内存/测试覆盖分支；总量缓存时期；页/字节精度条件 | 条件公式明确；未知分支 U，不能用 Native is_low_memory 猜开关 |
| MIME | 独立于页面的精确构建/容器来源绑定；未知厂商分支不能默认无修改 | 133 指定源码预期成立；历史任意记录可否应用未证 |
| 时区 | 固定域复用；动态域另需共同参考 epoch 的两端 offset、时区来源与规则版本 | 不从 rawOffset/timestamp 推造 DST offset |

如无新设备约束持续存在，当前最实际结果就是两个纯模块、状态契约与人工测试；还可只读核对已有元数据是否覆盖上述前提。不能承诺补齐无法追溯的历史观察，更不能声称验证真实 FPR 改善。

## 后续对照设计：先固定 selector，再讨论策略

所有下列工作本轮均 **NOT_RUN / PENDING_SEPARATE_AUTHORIZATION**。不消费 V2-C 已关闭的预算，不新增 fit 作业。

保留原身份基线：

| 基线 | 保存模型 ID | 使用范围 |
|---|---|---|
| W0 / GREEDY_OR | `v2c-3def521e987075a27b52e2df` | 原保存模型与原报告，不在本轮重预测 |
| C0 / GREEDY_OR | `v2c-40ffc55faff1962cc57829ee` | 原保存模型与原报告；仅 OFFDER-UA-001 入选 |
| W0 / R_KEEP_V1 | `v2c-af691341a2d38032d88973b5` | 独立原身份；当前最终模型与 W0 结构相同不代表算法普遍等价 |

首轮授权实验固定 `GREEDY_OR + OP05`，使用同一组预先冻结的训练/测试成员、标签、原配置等权→配置内环境等权→环境内 attack stage 等权的层级 macro 权重、约束、seed 与 tie-break。沿用 `learning_search_space.json` 中 alpha=0.05、lambda=0.005、max_clauses=6、单子句长度1、最小分层决策覆盖0.8及相同 support 条件；不一边改语义一边换 R_KEEP、优化目标、阈值预算或极性选择规则。候选公式没有 train 参数；其他仍需数值编码的旧字段只沿用 train-only 流程。选中的具体规则允许变化，那是固定选择算法对新表示的结果，不是证明算法策略改进。

预先登记最小表示对照（不按成绩挑选）：

| 表示身份 | 相对同一基础表示的唯一改动 | 解释目标 |
|---|---|---|
| `RSR-REP-BASE-v1` | 按原 W0 表示重建的未来对照，保存历史 W0 仍是另一个身份 | 同协议下的表示基准；不是改写历史分数 |
| `RSR-REP-LANG-v1` | 只将 languages 长度数值候选族替换为 LANG-FIRST，其他表示不变 | 首项语义与长度信息的差异 |
| `RSR-REP-WDSTATUS-v1` | 只把旧 webdriver 布尔投影替换为 legacy 状态解释，T 谓词不变 | 信息丢失和 U 传播代价，不宣称新命中机制 |

首轮不合并两种修改，不自动运行 2×2/大量策略搜索。只需这三个预注册视图，作业数由随后独立执行计划在授权前固定。旧 support 要求 triplet 三阶段该原子均 T/F；legacy webdriver false→U 后，只要某阶段有该值，该 triplet 就不贡献完整可用支持。因此 WDSTATUS 可能不入候选池，不能为保入选放宽 support，也不能据此认定状态语义无效。这是条件推论，未在真实记录上计算。因支持/覆盖不够而未入选、EMPTY_MODEL 或失败都如实保留，不强制新条件入选。若只授权模块实现，到单测即止，不能借本表自动进入真实数据评价。

分别记录 `collector_contract_id`、`source_binding_id`、`gate_version`、`representation_id`、`selector_id`；新原始 webdriver 采集必须另取 collector/representation 身份，不能与 legacy 修改混算。将来若研究 UA/内存跨层关系，需先单列旧门控/新门控覆盖变化，再比较关系；有更丰富标签、UA token 或内存量化解析时，同层匹配对照获得完全相同解析产物与可用性信息。UA 同源传播和 MIME Host 范围门控仍不能称作独立跨层硬件信息。

只有再单独授权策略比较时，才在完全相同表示/数据/预算上对比 selector；不能把语义改动与 R_KEEP 改动一次合并后归因其中之一。

## 分母、失败和结论上限

按预期记录保留 `N_expected`；候选逐项报告 `N_T/N_F/N_U/N_FAILED`，总和必须等于预期分母。U 按缺字段、源失败、解析域、版本、信任、配对原因分解；同时保留多原因明细及固定首要原因，避免重复计数。模型决策另报 MANIPULATION_ALERT、NO_ALERT、INSUFFICIENT_EVIDENCE、EMPTY_MODEL、FAILED，不把 NO_ALERT 等同正常标签。

给出全分母上的报警/弃判/失败以及有效域内条件指标，明确不同有效域不能直接横比。按原标签与部署范围展示覆盖损失；不删除强制 U 的样本，不将 FAILED 丢掉，不把有效域缩小的少报警当检测能力提升。门控或版本由页面自报时不得作为可信豁免；Host 可被改写的威胁也必须声明。

没有新真实正常材料，不能验证真实误报改善或普通 App 泛化。手工规格例不加入旧正常分母，不能替代真实标签，不修历史成绩。最后交付模块检查报告或另授权实验报告，随后停止。
