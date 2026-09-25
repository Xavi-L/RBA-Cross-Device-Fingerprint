# V2-B：有限方法迭代开发结果

2026-09-25。状态：`COMPLETED_PENDING_USER_REVIEW`。本阶段提出 **W0 + R_KEEP_V1** 为主候选，不提出新备选。它在已暴露开发材料上检出 **45/54（83.33%）**，配置/环境宏平均 **78.57%**，clean_pre 与 clean_post 均 **0/54**，决策覆盖 **162/162**。相对保存的 W0 新增 18、丢失 0；代价是第三折复杂度从 2 增至 12，三折均达到六个单文字 OR 子句的上限。

这次增益可完全由原 Web 候选池内的选择偏好变化解释。联合表示和新跨层关系没有带来进一步增益；内存比例关系在一个留出环境中产生了 18 个 clean 报警。全部新增检出相对 W0 集中于一个留出环境关联组，不能据此宣称跨环境稳健性、跨层优越性或独立盲测通过。

## 范围、身份与证据

用户明确验收 A 提交 `72a7c74d97b04f0bcce202a5d482e02c1e4e9cad`，本轮只执行 B。A 的历史合同、结果与运行时源码快照保持只读；当前 `rule_learning_v2` 代码新增 B 身份及最小适配，复用原内核。没有更改 V1 capability、伪造 synthetic 真实记录或改写旧模型。

所有数字均为 `EXPOSED_RETROSPECTIVE_DEVELOPMENT`：沿用原 54 组三态、162 个监督阶段、14 配置及三折 LOEO。三个环境关联组不等于已经确认的三个独立物理设备。每组三态保持同折；100 个描述阶段未进入 fit 或监督指标，UNKNOWN 控制和未标注 MTC 没有改成 clean。

宏平均沿用原配置/环境权重，不是三个折 TPR 的简单平均。FTF 要求同组三态决定恰为 F/T/F。表中覆盖、弃判、失败以全部预期阶段为分母。所有 B 规格在这 162 阶段上均无弃判、失败或空模型；这不是对未出现输入状态的保证。

合同及执行证据见 [B_CONTRACT.json](B_CONTRACT.json)、[批次规格](batches/)、[trials.jsonl](trials.jsonl)、[execution_verification.json](execution_verification.json)。每次 trial 先保存规格并预留预算，仅把本折 train 交给编码、支持度和选择；模型/编码器保存并加载后才读取评价特征，预测文件关闭后才连接评价标签。39 次实际 trial 均有对应访问事件、一次明确模型拟合调用及 receipt。重新读取保存结果的归因不包含新 fit 或预测重生成。

## 失败汇总修复与实际测试

合成夹具确认旧 `diagnose.after_trials()` 在 worker 已失败、已保存 FAILED 行但 `model.json` 截断时仍抛出 `JSONDecodeError`，见 [engineering_reproduction.json](engineering_reproduction.json)。新增 `trial_summary.inspect_attempt()` 后：

- 明确 worker 失败时，在汇总内为全部预期 ID 构造 FAILED 决定，部分预测、损坏模型和训练文件保留原状。
- 不可读模型的复杂度等结构统计记为未知并保存原因，不把它当作正常空模型。
- 原成功 trial 后来损坏时标记 `INTEGRITY_EXCEPTION`；原 receipt 和预测不重写，派生评价保留失败分母。
- 正常成功 trial 的决定和指标保持不变。A 的六次 fit 及预测均未重跑。

最终执行 **36 个合成/回归测试，全部通过**：原 A 相关测试 11 个、失败汇总 7 个、互补保留 9 个、关系语义 9 个。覆盖缺失/截断模型、缺失/损坏训练文件、部分预测、正常成功、事后损坏；以及别名不刷 D、联合 clean 预算、严格 T/F/U、覆盖限制、重复性、标签隔离、train-only 阈值、冻结编码器复用、保存/加载和 Native 具体值依赖。完整命令及逐测试结果见 [final_engineering_semantic_tests.json](final_engineering_semantic_tests.json)。

早期两个合成测试夹具问题也保留：`engineering_tests_01.json` 中 JSON 元组/列表断言不一致，`retention_tests_01.json` 中玩具模型缺少 OP05 绑定；分别修正测试断言/夹具后通过，未触发真实重试。最后边界复核修正“超时且无可行 incumbent 应为 FAILED”和“阶段关闭后拒绝新批次”。39 个保存 receipt 均为 FITTED，没有超时；这两项不改变已运行结果，旧运行时版本仍在 `code_versions/`，详见 [postrun_engineering_note.json](postrun_engineering_note.json)。

## 互补保留改变了什么

`R_KEEP_V1` 是明确的新选择偏好：从严格对应本折、表示、编码、合同的已保存 GREEDY_OR/OP05 稀疏模型初始化，在原支持合格候选中补入规则。B01 使用保存的 W0/S_FLAT/J0；B03 使用 B02 同折保存模型。初始化均核对精确 train 成员、阈值、候选/支持集合和训练分数，没有重新学习初始化阈值或利用外层决定选规则。

信号分组版本为 `SEMANTIC_SIGNAL_GROUPS_V1`，真实试验前固定，依据字段来源和谓词语义。相同字段多个阈值、正负极性、重复别名不产生额外组；仅加 Native 有效性门控的 UA 表达仍归 Web 身份信号。信号组是保留偏好，不能把当前训练上碰巧同输出的不同谓词声明成全局语义别名。映射见 [signal_groups_v1.json](signal_groups_v1.json)。

保留量为 `D(S) = Σ_g Σ_train_attack_i w_i × any_T(S 中组 g 的条件, i)`。每次须严格增加 D，保持当前训练攻击检出，满足整个最终 OR 的 `floor(0.05 × N_train_clean)` 报警预算、各 phase 至少 0.8 决策覆盖、无训练失败、原支持门槛及家族上限、最多六子句/复杂度 12。按新增训练宏检出、新增 D、较少最终 clean 报警、较低复杂度、稳定 ID 依次决胜；不再用旧稀疏目标把补入条件删回。

前两折的初始模型已满六子句，未增加条件。第三折初始只有 `hardware_concurrency > 4`，训练宏检出已是 1；仍允许保留同样检出训练攻击的其他语义信号。实际顺序如下，所有阈值均来自本折保存编码器：

| 补入条件 | 信号组 | 新增 D | 新增训练宏检出 | 最终集合训练 clean 报警 |
|---|---|---:|---:|---:|
| `CAT:NW-006:POSITIVE`，既有 Web UA/platform 条件 | web_client_identity | 2/3 | 0 | 0 |
| Web webdriver 为 true | automation_flag | 2/3 | 0 | 0 |
| Web device_memory > 2 | memory_capacity | 2/3 | 0 | 0 |
| Web MIME 数量 > 0 | plugin_capability | 1/3 | 0 | 0 |
| Web languages 长度 > 1 | language_preferences | 1/3 | 0 | 0 |

第三折 D 从 1 增到 11/3，复杂度从 2 增到 12。旧目标 `MacroTPR − 0.005 × complexity` 从 0.99 降至 0.94；因此这不是修复 GREEDY_OR 的错误，也没有声称仍优化相同目标或拥有新泛化保证。完整选择轨迹见 [第三折 training.json](trials/B01_retention__W0__R_KEEP_V1__LOEO-v1-03__attempt01/training.json)。

主候选三折编码后文字候选数为 98/98/112，支持合格数 68/69/74，选中数均 6。主要未选原因包含支持不足、最终集合 clean 预算、结构/家族上限及没有新信号覆盖；一个候选可同时具有多个原因，原因计数不能相加当成独立候选数。全部规格计数见 [candidate_counts.csv](candidate_counts.csv)，每个 trial 保留候选状态和支持摘要。

## 全部规格结果与代价

`G` 表示原 GREEDY_OR/OP05；`R` 表示 R_KEEP_V1。C0/W0/S_FLAT/J0 是直接读取的保存结果，不计入 B 的 39 次 fit。每行均评价同一组 162 阶段，覆盖均 162/162、弃判和失败均 0/162。

| 规格 | attack 微检出 | 配置/环境宏检出 | pre 报警 | post 报警 | 合并 clean 报警 | FTF | 三折复杂度 |
|---|---:|---:|---:|---:|---:|---:|---|
| C0（保存基线） | 24/54 | 42.86% | 0/54 | 0/54 | 0/108 | 24/54 | 2 / 2 / 2 |
| W0（保存基线） | 27/54 | 35.71% | 0/54 | 0/54 | 0/108 | 27/54 | 12 / 12 / 2 |
| S_FLAT（A） | 27/54 | 35.71% | 0/54 | 0/54 | 0/108 | 27/54 | 12 / 12 / 2 |
| J0（A） | 27/54 | 35.71% | 0/54 | 0/54 | 0/108 | 27/54 | 12 / 12 / 2 |
| **W0 + R** | **45/54** | **78.57%** | **0/54** | **0/54** | **0/108** | **45/54** | **12 / 12 / 12** |
| S_FLAT + R | 45/54 | 78.57% | 0/54 | 0/54 | 0/108 | 45/54 | 12 / 12 / 12 |
| J0 + R | 45/54 | 78.57% | 0/54 | 0/54 | 0/108 | 45/54 | 12 / 12 / 12 |
| CX + G | 27/54 | 45.24% | 9/54 | 9/54 | 18/108 | 18/54 | 8 / 6 / 2 |
| JX + G | 27/54 | 35.71% | 0/54 | 0/54 | 0/108 | 27/54 | 12 / 12 / 2 |
| W_X + G | 27/54 | 35.71% | 0/54 | 0/54 | 0/108 | 27/54 | 12 / 12 / 2 |
| S_FLAT_X + G | 27/54 | 35.71% | 0/54 | 0/54 | 0/108 | 27/54 | 12 / 12 / 2 |
| CX + R | 30/54 | 52.38% | 9/54 | 9/54 | 18/108 | 21/54 | 8 / 6 / 4 |
| JX + R | 45/54 | 78.57% | 0/54 | 0/54 | 0/108 | 45/54 | 12 / 12 / 12 |
| W_X + R | 45/54 | 78.57% | 0/54 | 0/54 | 0/108 | 45/54 | 12 / 12 / 12 |
| S_FLAT_X + R | 45/54 | 78.57% | 0/54 | 0/54 | 0/108 | 45/54 | 12 / 12 / 12 |
| C0 + 仅内存关系 + G | 27/54 | 45.24% | 9/54 | 9/54 | 18/108 | 18/54 | 4 / 2 / 2 |
| C0 + 语言/时区，无内存 + G | 24/54 | 42.86% | 0/54 | 0/54 | 0/108 | 24/54 | 6 / 6 / 2 |

主候选相对 W0、S_FLAT、J0 均为新增 18、丢失 0；相对 C0 新增 21、丢失 0；没有新增 clean 报警。对应宏平均分别增加 42.86 和 35.71 个百分点。A 原来的 W0/S_FLAT/J0 对 C0 仍是新增 12、丢失 9，不能被 B 的结果改写。

逐配置检出如下。表内短名对应 [metrics_by_configuration.csv](metrics_by_configuration.csv) 的完整 config_id；该文件同时保留每配置 pre/post、覆盖、FTF 等指标。其他规格的结果、逐折及逐 ID 差集见 [metrics.json](metrics.json)、[metrics_by_fold.csv](metrics_by_fold.csv)、[gained_lost.json](gained_lost.json)、[stage_comparison.jsonl](stage_comparison.jsonl)。

| 配置短名 | C0 | W0 / S_FLAT / J0 | W0 + R | CX + G |
|---|---:|---:|---:|---:|
| screen-metrics-only | 0/3 | 0/3 | 0/3 | 0/3 |
| timezone-only | 0/3 | 0/3 | 0/3 | 0/3 |
| tool-054 | 3/3 | 3/3 | 3/3 | 3/3 |
| tool-055 | 3/3 | 3/3 | 3/3 | 3/3 |
| tool-056 | 9/9 | 9/9 | 9/9 | 9/9 |
| tool-058 | 0/9 | 9/9 | 9/9 | 3/9 |
| platform-only | 3/3 | 0/3 | 3/3 | 3/3 |
| resource-pair | 0/3 | 3/3 | 3/3 | 0/3 |
| ua-only | 3/3 | 0/3 | 3/3 | 3/3 |
| ua-platform-desktop | 3/3 | 0/3 | 3/3 | 3/3 |
| webdriver-only | 0/3 | 0/3 | 3/3 | 0/3 |
| languages-only | 0/3 | 0/3 | 3/3 | 0/3 |
| plugins-mime | 0/3 | 0/3 | 3/3 | 0/3 |
| webgl-pair | 0/3 | 0/3 | 0/3 | 0/3 |

主候选三折攻击检出为 9/9、6/6、30/39，W0 为 9/9、6/6、12/39。新增 18 条分布于 ua-only、platform-only、ua-platform-desktop、webdriver-only、languages-only、plugins-mime 六个配置，各 3 条，均来自第三折留出环境。相对 C0 的 21 条来自 tool-058 九条及 resource-pair、webdriver-only、languages-only、plugins-mime 各三条。重复阶段或多规格预测不能增加独立样本量。

## 新关系的真实参照、有效域和阻塞

实现版本 [relation_registry_v1.json](relation_registry_v1.json) 记录完整输入路径、单位、参数、采集代码位置、一手定义及合法反例。以下都是研究候选条件；取值不同不自动成为攻击事实。非 observed/observed_value、缺失、非法数值或不支持的语义均返回 U。

| 家族 | 实现及参数来源 | 限制与合法反例 |
|---|---|---|
| 内存 | `app.android_native_data.memory_layer.total_memory_gb` 与 `app.web_data.navigator_layer.device_memory`；计算 Web/Native 无量纲比例，原 Q25/Q50/Q75 只在本折 train 学习，沿用两种极性 | Native 是内核可用总内存，Web 是近似且可能量化/裁剪的能力值；不要求相等，不硬编码普适 8 GiB 上限。内核保留、虚拟化及浏览器隐私策略均可能合法改变比例。 |
| 语言 | Native `locale_timezone_layer.native_locale` 与 Web `navigator_layer.language/languages`；有限 primary subtag 比较、Native primary 是否在 Web 列表，无学习词表 | 大小写及有限 script/region 语法归一；只比较主语言，不推断完整 locale 或文字系统等价。扩展/private-use/未解析旧标记等返回 U。应用与浏览器语言偏好不同可以合法。 |
| 时区 | Native `locale_timezone_layer.native_timezone_id/native_timezone_offset_min` 与 Web `execution_layer.timezone_offset`；只在可解析固定 Native 时区、ID 与 offset 一致时比较 | Native 分钟向东、Web 分钟向西，比较前反号；GMT/UTC 等别名等价。动态 Native 时区/DST 缺乏可信观测时刻或当前 offset，保持 U，未拿 rawOffset 代替 DST 当前值。不同应用时区可合法。 |

内存的字段语义分别依据 [Android totalMem](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo#totalMem) 和 [W3C Device Memory](https://www.w3.org/TR/2026/WD-device-memory-1-20260330/)；有限语言解析依据 [RFC 5646](https://www.rfc-editor.org/rfc/rfc5646) 及 [HTML NavigatorLanguage](https://html.spec.whatwg.org/multipage/system-state.html#dom-navigator-languages)。Native 时区采用标准偏移而 Web Date 反映其时刻的本地偏移，定义见 [Java TimeZone](https://docs.oracle.com/javase/8/docs/api/java/util/TimeZone.html#getRawOffset--) 与 [ECMAScript getTimezoneOffset](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.prototype.gettimezoneoffset)。实现采用比完整标准更窄的明确有效域。

Native/Host CPU 核数仍无参照，未用 ABI 冒充；插件/MIME 没有第二来源语义成员，未造镜像。以上两个扩展保持 BLOCKED。时区动态域同样未实现。各折支持不足继续排除：例如第三折训练没有语言不一致或时区差异的正例，相关正极性候选无法准入，即使已知外层存在相应改动。

语言新增了列表成员语义，因此同时实现 `W_X` 和 `S_FLAT_X`：同样解析 Web language 与 languages 的 primary，判断前者是否缺于后者，完全不读 Native。内存两侧原始数值已经在 S_FLAT，Web offset 已在 W0，因此不另造重复单表面规格。`CX=C0+三家族`，`JX=S_FLAT+CX`；JX 本身不额外加入匹配单表面新原子。按同选择策略分别比较 JX、W_X、S_FLAT_X，未将单表面新增解析能力冒充跨层贡献。

## 归因：选择收益、表示负结果与环境适配

在相同 R_KEEP_V1 下，S_FLAT、J0、JX、W_X、S_FLAT_X 与 W0 的三折选中 clause ID（含阈值）及全部 162 阶段决定完全一致；较大表示均未选中跨层原子。在原 G 下，JX/W_X/S_FLAT_X 同样复现 W0 的规则和决定。因此当前主收益属于**原候选池内选择偏好变化**，不能归因于新增输入、新关系或更强搜索。

三类新函数在合成扰动中确实依赖 Native 的具体值，不是仅检查有效性；但实测 Native/Web primary 均为 en（162/162），Native offset 均为 0（162/162）。于是语言跨层成员关系在当前材料上与匹配 Web 成员关系全等，固定时区关系与 Web offset 非零条件全等。这些是当前数据上的冗余，不能升级为全局别名。证据及每条记录的原始引用见 [relation_evidence.json](relation_evidence.json)。

CX + G 对 C0 只新增 tool-058 三条，没有丢失攻击，却新增 env-001 全部九组的 pre/post 报警各九条，FTF 反而由 24/54 降至 18/54。第一折训练学到 `Web/Native memory > 0.8283140429538769`；留出环境 clean 的 Web memory 仍为 2，Native 约 1.934 GiB，比例约 1.034，超过阈值。训练中的其他环境 Native 约 2.415 GiB，clean 比例约 0.828。该判别把正常环境内存规模差异带入报警。

为隔离三家族混合变化，最后仅做两规格消融：C0 + 仅内存的全部 162 决定与 CX + G 完全相同；去掉内存后全部 162 决定与 C0 完全相同。这支持“当前 CX 的攻击新增与 clean 代价由内存关系带来”，并未支持安全的跨层可分性增益。CX + R 在第三折再保留内存比例条件，检出 resource-pair 三条，达到 30/54，但 18 个 clean 报警仍在。

主候选也存在开发适配风险：绝对 Web 内存/核数、UA/platform、webdriver、语言和 MIME 数量条件均可能响应合法设备、浏览器定制或获准自动化。信号组与研究方向是在已暴露材料后提出的；折内训练隔离不消除研究者选择带来的适配。有限 clean 的 0/108 只描述本批已标注控制，不等于总体零误报。

## 剩余九条漏检

主候选余下 screen-metrics-only 三条、timezone-only 三条、webgl-pair 三条，见 [remaining_misses.csv](remaining_misses.csv)。逐记录继续关联 A 的诊断和 B 当前同折支持/决定，而非为漏检记录单独造规则。

| 数量 | 主要原因 | 已有证据与下一步 |
|---:|---|---|
| 6 | 支持度排除：screen/timezone 各三条 | 对应变化在其本折 train 没有满足原门槛的正例。时区关系语法已经实现，仍不能手工准入外层独有正例。需要独立环境×机制的训练支持和合法屏幕/时区变化控制；本轮未放宽门槛。 |
| 3 | 测量不可用：WebGL pair | A 已指出 Native 软件渲染/ANGLE 相关比较域问题；现有合法测量不足以形成可靠第二来源语义参照。需要先解决测量域与合法渲染器差异，额外采集须另行授权。 |

当前证据没有把这九条归为“搜索不够强”；也没有证明任何未来表示都不可分。新增语言/时区语法可能保留了过去未表达的语义，但在这批材料中实际值冗余或本折支持不足。主收益解决的是已有合格信号被稀疏目标舍弃的问题，余下瓶颈转向训练支持与可用测量。

## 预算与留痕

启动时已关联 V1 原账本、R09 非 fit 扣账及 A：71 + 6 = **77 fits**，累计 **113.412951126 秒**。B 按 worker 实际 wall time 收费，包含读入、已登记的编码/支持/稀疏选择/保留、保存加载、预测及评价；未把内存阈值拟合或规则保留藏在只读诊断中。合成测试和读取已保存结果不计真实 fit。

| 批次 | 规格数 | 实际 fit | 计费秒 | 目的 |
|---|---:|---:|---:|---|
| B01_retention | 3 | 9 | 5.906302375 | 同候选池选择偏好 |
| B02_relations | 4 | 12 | 12.091047457 | 原选择策略下的新关系及匹配解析 |
| B03_crossed | 4 | 12 | 7.287039375 | 同表示/同策略交叉对照 |
| B04_memory_attribution | 2 | 6 | 1.891826790 | 内存家族归因 |
| **B 合计** | **13** | **39** | **27.176215998** | **真实失败 0，重试 0** |

39 个模型共保存 **2,106 条新预测**，重复覆盖同一 162 个监督阶段。各批均在规格运行前预留、完成后核销，预留余额为零。没有重跑 A、C0/W0 或做全开发集最终拟合。

关联研究累计 **116/200 fits、140.589167124/21600 秒**，实际剩余 **84 fits、21459.410832876 秒**。B 自身尚未使用的 21 fits/3572.823784002 秒在阶段关闭后不构成继续授权。原始逐次时间与扣账见 [linked_budget_ledger.json](linked_budget_ledger.json)；预算没有归零，全部有效负结果和早期测试问题保留。

## 候选决策、C 的最小条件与停止

[CANDIDATE_SELECTION.json](CANDIDATE_SELECTION.json) 选择 **W0 + R_KEEP_V1** 这一学习程序及其三个已保存折模型，尚未拟合一个全开发集最终模型。选择同时考虑宏/微检出、clean、覆盖、失败、复杂度及来源：它改善了宏和微检出，当前 clean/覆盖没有损失；在较大表示完全同结果时选择输入范围最小的原 W0。第三折复杂度增加及合法场景误报风险明确保留，因此不是无代价全面优于 C0。C0 继续作为低复杂度基线，不另包装成 B 的新备选。

不推荐 CX 作为备选：其 clean 代价和较差 FTF 已有实证；增加语言/时区但去掉内存仅提高复杂度而未改变 C0 决定。较大的 flat/joint/matched 版本没有显示额外价值。必要归因已经足够，未为用满 60 fits 继续搜索。

进入 C 的最小计划只提出以下条件，本轮未执行：

1. 用户审查 B 后，先冻结候选语法、信号组、学习程序、支持/clean/覆盖操作点和比较指标；另行决定是否授权最终训练。确认标签开放前封存待比较模型/程序及预期成员。
2. 另行授权真实独立材料、标签裁决及必要采集，交叉覆盖环境和配置。优先加入合法高内存/核数、语言偏好与列表、时区/DST、PDF/MIME、UA 定制和获准自动化控制，避免当前默认值与攻击机制绑定。
3. 对 C0、W0 与主候选做预期 ID 配对比较，报告宏/微检出、pre/post/合并 clean、覆盖、FTF、失败及复杂度，并按真正独立组表达不确定性；不根据确认结果继续调参。

尚不能成立的主张包括：新盲测通过、跨层优于单层、未见机制泛化、总体零 FPR、新优化/泛化定理、C 已完成。A 的 C0 OR W0 = 36/54 继续只作 `POST_HOC_ENSEMBLE_DIAGNOSTIC`，本轮未重命名或训练成集成成绩。

实现位于 `hybridguard_agent/research/rule_learning_v2/`，新增针对性测试位于 `hybridguard_agent/tests/test_rule_learning_v2_b_*.py`。本目录保存必要编码器、模型、规则/信号组、预测解释、选择轨迹和代码版本，没有复制完整 V1/A 数据或巨型训练矩阵。可重复的合成测试命令为：

```sh
python3 -m unittest hybridguard_agent.tests.test_rule_learning_v2 hybridguard_agent.tests.test_rule_learning_v2_b_summary hybridguard_agent.tests.test_rule_learning_v2_b_retention hybridguard_agent.tests.test_rule_learning_v2_b_relations -v
```

可变计划与状态记录 A 已验收、B 完成待审查；账本关闭。未执行 V2-C、R10、V3、独立确认、新采集或攻击工具，也未 commit、push 或创建 PR。建议后续获准提交时使用：`research: develop V2-B complementary rule retention and relation controls`。
