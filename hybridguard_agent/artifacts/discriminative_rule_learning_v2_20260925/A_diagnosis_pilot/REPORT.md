# V2-A：漏检诊断、字段参照核实与首轮平铺/联合表示试验

2026-09-25 · **COMPLETED_PENDING_USER_REVIEW** · 已停止，不自动进入 V2-B/C 或 R10。

**本批没有取得相对 W0 的增益。S_FLAT 与 J0 三折都选择了与保存 W0 完全相同的文字及阈值，162 个阶段决定也相同。J0 未选任何跨层原子。** 相对 C0，二者攻击检出净增3，但配置宏平均下降7.14个百分点，前两折复杂度从2升至12；不能称为整体权衡改善。

这些是已暴露材料上的开发结果。14配置是配置标识，3组是环境关联组；不推定14种独立机制或3台独立核验设备。54组三态共162个监督阶段，每种表示仍只有这些阶段；324条新预测不增加独立样本。100个描述阶段未进入fit或监督指标，UNKNOWN控制和未标注MTC未升级为clean。

## 结果与代价

宏平均按配置等权、配置内已代表环境等权。pre/post标签只限定声明干预表面。所有k/n保留原分母。

| 表示 | 微检出 | 配置/环境宏检出 | pre报警 | post报警 | 决策覆盖 | 弃判 | 失败 | 精确FTF | 三折复杂度 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| C0 | 24/54 (44.44%) | 42.86% | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 24/54 | 2/2/2 |
| W0 | 27/54 (50.00%) | 35.71% | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 27/54 | 12/12/2 |
| S_FLAT | 27/54 (50.00%) | 35.71% | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 27/54 | 12/12/2 |
| J0 | 27/54 (50.00%) | 35.71% | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 27/54 | 12/12/2 |
| POST_HOC_ENSEMBLE_DIAGNOSTIC | 36/54 (66.67%) | 57.14% | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 36/54 | 组件之和14/14/4；无新模型 |

四个学习表示的 decided-clean 报警均为0/108；本批没有空模型或失败。有限clean中0次报警不是总体FPR=0。选中原子可用性：C0为162/162，W0/S_FLAT/J0均387/387，后者分母按各折实际选中规则数加权。

候选池可用性与选中原子可用性不同：C0 1416/1620，W0 8736/8757，S_FLAT 25845/26190，J0 27261/27810；全部未可用候选仍保留U，未转成正常或攻击。详见 [metrics.csv](metrics.csv)、[逐折指标](metrics_by_fold.csv)、[候选可用性](candidate_availability.csv)、[基线候选可用性](baseline_candidate_availability.csv)。

S_FLAT的编码后原子为153/153/165，支持合格文字为184/185/199；J0为163/163/175和197/198/212。候选登记、训练支持、选中结构均保存在各trial的training.json/model.json，没有按外层成绩删池。原143个单表面输入包含28目录条件、53固定控制、62待拟合数值/列表长度输入；C0的12个来源候选按既定别名极性归为10个规范原子。没有把当前样本上输出相同视为全局别名。

事后OR逐项连接同折、同ID的已关闭C0/W0结果，覆盖全部162阶段。定义为：任一组件FAILED则FAILED；否则任一T则T；两者F则F；其余为U，EMPTY计入U。它是 **POST_HOC_ENSEMBLE_DIAGNOSTIC**，36/54及57.14%仅是事后组合诊断，既不是本次联合训练成绩，也不是独立确认或性能上限。没有重新训练C0/W0。组件之和只说明原模型复杂度，不冒充新模型复杂度。见 [完整组合记录](posthoc_ensemble_diagnostic.jsonl)。

## 全部14配置与新增/丢失

每格为攻击检出k/n；各配置的pre/post报警、弃判、失败本批均为0，决策覆盖均为全部预期阶段。完整分母和状态在 [逐配置指标](metrics_by_configuration.csv)。

| 配置 | C0 | W0 | S_FLAT | J0 | 事后OR诊断 |
|---|---:|---:|---:|---:|---:|
| w10-cdp-emulation-screen-metrics-only-v1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| w10-cdp-emulation-timezone-only-v1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| w6-tool-054-legacy-default-v1 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| w6-tool-055-legacy-default-v1 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| w6-tool-056-legacy-default-v1 | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 |
| w6-tool-058-legacy-default-v1 | 0/9 | 9/9 | 9/9 | 9/9 | 9/9 |
| w9-rule-boundary-cdp-platform-only-v1 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| w9-rule-boundary-cdp-resource-pair-v1 | 0/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| w9-rule-boundary-cdp-ua-only-v1 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| w9-rule-boundary-cdp-ua-platform-desktop-v1 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| w9-rule-boundary-cdp-webdriver-only-v1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| w9-stealth-boundary-languages-only-v1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| w9-stealth-boundary-plugins-mime-v1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| w9-stealth-boundary-webgl-pair-v1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |

S_FLAT/J0相对C0的新增12个来自tool-058（9）和resource-pair（3）；丢失9个来自ua-only、ua-platform-desktop、platform-only，各3。相对W0新增0、丢失0；两种比较新增clean报警均0。精确ID保存在 [gained_lost.json](gained_lost.json)，全阶段决定并排保存在 [stage_comparison.jsonl](stage_comparison.jsonl)。

## 瓶颈在哪里

[diagnosis.csv](diagnosis.csv)保留162条记录，包括全部已检出记录及其pre/post。它的primary_reason针对C0漏检；[selection_diagnosis.csv](selection_diagnosis.csv)进一步区分W0/S_FLAT/J0的选择原因，避免把已有单字段信号的落选误记成“缺跨层规则”。[triplet_evidence.jsonl](triplet_evidence.jsonl)包含54组三态的原始声明字段变化、质量、全部C0状态、选中子句、候选支持和源路径。

- **观测与表示**：54/54攻击都有声明的非hash语义字段变化；没有证据将本批漏检归为未观测到变化。C0漏检30个中，12个主记REPRESENTATION_GAP，15个SIGNAL_WITHOUT_CROSS_REFERENCE，3个MEASUREMENT_UNAVAILABLE。分类针对当前字段/测量，不改变攻击资格或分母。
- **屏幕3个**：CSS几何和DPR确实变了，但现有P3-SCREEN-APP只比较短边残差，三态规范偏差均F/F/F。它没有表达其余窗口/长边信息；不是完全没有屏幕关系。留出env-003时可触发的屏幕单字段条件在train正例支持为0，又被支持度排除。合法缩放、旋转、窗口变化仍需区分，不能直接要求所有尺寸相等。
- **时区3个**：Web offset从0到420再回0；C0不表达该关系。单字段timezone_offset>0已经在W0候选中，但相应留出折train没有触发攻击，支持度排除。不是换名称或扩大候选就自动获得留出检出。
- **UA边界9个、webdriver3个、语言3个、plugins/MIME3个**：已有可用单表面条件。第三折只有45训练阶段/15攻击，hardware_concurrency>4已检出全部训练攻击，宏目标为1−0.005×2=0.99。UA/Webdriver条件的9个训练攻击、语言/插件条件的6个训练攻击全部包含在这15个中；增加条件没有训练检出收益而增加复杂度。留出边界配置打破了这种共变，形成18个FOLD_SHIFT漏检。该折0.99已达到非空规则复杂度至少2时的目标上界，因此不能把这一现象简单归因于贪心没找到更高训练目标。
- **WebGL 3个**：原始renderer/vendor变化存在，但Native软件渲染/ANGLE等不属于当前可判定硬件族域，相关核心条件为U；W0没有任意renderer字符串词表。保留MEASUREMENT_UNAVAILABLE，不用字符串差异或hash造规则。
- **Native/Host新增平铺条件**：三个训练折中，Native支持合格文字82/82/87、Host为34/34/38；它们每一条单独造成的clean报警都超出4/4/1预算。单文字OR加入其他条件不能消除这些已有报警，故本批平铺无新增可行信号。此结论只适用于当前池、单文字OR与预算，不延伸为其他组合形式无效。
- **J0的C0候选**：各折20个正负文字中，9个支持合格但超clean预算，7个未过支持/可用性，4个可行但相对已选集合训练攻击边际收益为0。没有任何跨层条件最终入选。前两折达到6子句上限也是实测限制，但未运行更大复杂度对照，不能宣称放宽就能改善外层。

按声明信号而非偶然网络等背景波动分类，W0/S_FLAT/J0的27个漏检分别为FOLD_SHIFT 18、PRUNED_BY_SUPPORT 6、MEASUREMENT_UNAVAILABLE 3。所有未选择条件和正常侧代价可查 [训练瓶颈](training_bottlenecks.json)及各trial/training.json。SEARCH_LIMIT在本批没有独立支持；没有运行IP或DNF2。定向检查没有发现旧预测ID/模型映射不一致，不据此宣称完成全库工程审计。R06 E-only的21/54和R08 LOCO的24/54只作保存结果参照，未与LOEO混并，也未重跑。

## 名义跨层与实际信息增量

已选C0规则OFFDER-UA-001读取Native os_version。原始值并不恒定：Android11/15/16分别27/18/117阶段；但“有效Android主版本”门控在162/162阶段通过，具体版本值不参与桌面/脚本UA或platform的报警比较。其规范偏差与CAT:NW-006在本批162阶段完全相同。合成有效版本替换与无效锚点对照确认：有效11换16不改变结果，无法确定Native版本则为unknown。

这支持“本批主要是有效性门控”的判断，不能证明Native普遍无用。两个谓词的有效域不同：NW-006要求UA/platform类别都可解释，OFFDER-UA-001额外要求Native，但允许至少一个Web类别可解释。因此保留为不同候选，未合并成全局同义。证据见 [native_anchor_diagnostic.json](native_anchor_diagnostic.json)。

固定表示的同输入异标签诊断：C0只有3种向量，其中一组容纳30攻击和108clean；在这批有限样本上，确定性C0输入不能同时将这组攻击全报、clean全不报。W0各折完整候选向量的混合组均涉及3攻击；S_FLAT/J0各折为2/2/3攻击，且J0加入C0没有进一步拆分S_FLAT的组。平铺新增的状态差异没有转化为本批规则收益；某些差异可能来自负载等合法波动。这些是固定编码下的开发可分性诊断，**不是泛化上界、攻击真值或新模型成绩**，各折向量没有混成同一个编码器。见 [collision summary](input_collision_summary.json)。

## 最多三个后续关系家族及合法反例

[字段参照表](field_reference_inventory.csv)记录三个家族、七项组件，逐项区分Native/Web存在性、Host缺参照、单位、当前观测及阻塞。本批没有把以下方向实现为新谓词。

| 优先方向 | 已核实参照与收益假设 | 合法反例与未解决事项 |
|---|---|---|
| 资源能力，先限内存 | Native total_memory_gb及Web device_memory均162/162观测。Native实际为totalMem/1024³；Web是近似内存。可研究有语义的范围关系，减少绝对资源阈值捷径。 | 正常已存在Native约2.4145与Web 2；浏览器量化/限幅不等于操纵。Native/Host没有CPU核数字段，ABI/架构不是核数；CPU关系BLOCKED_MISSING_REFERENCE。 |
| 语言/列表，先限locale与languages | Native process locale=en-US，Web有真实成员/顺序；languages-only为fr-FR/fr，而既有编码只留长度。可研究有限语言类别或集合关系。 | 应用/浏览器语言偏好、地区标签、fallback及顺序可合法不同。tool-058的en-US/en仍包含Native locale，不保证新关系能补检它。插件/MIME仅持久化数量/hash，没有Native镜像或可用语义成员表。 |
| 时区语义对齐 | Native timezone ID/raw offset和Web Intl ID/Date offset都存在。可研究日期与符号统一后的关系。 | Native rawOffset不含DST，JS读取当前时刻且符号相反；当前Native全为GMT/0，无法验证DST和非零正常区。GMT、UTC、+00:00是已有合法别名反例，不能用字面ID差异。 |

内存/处理器语义依据分别见 [W3C Device Memory](https://www.w3.org/TR/device-memory/) 和 [WHATWG hardwareConcurrency](https://html.spec.whatwg.org/multipage/workers.html#dom-navigator-hardwareconcurrency)；rawOffset不含DST见 [Java TimeZone](https://docs.oracle.com/javase/8/docs/api/java/util/TimeZone.html#getRawOffset--)。这里没有从这些资料抽取新阈值。采集代码和实际样本路径见字段表；源码解释不冒充对历史APK重新执行验证。

**下一批首先应研究训练分布中的信号共变与互补规则保留问题，再有限比较上述有真实参照的关系。** 单纯并池已经被本批否定为有效改进；单纯降低支持度也不能解决零训练触发。语言/时区新关系在当前留出折仍可能缺乏正例支持；任何收益假设都须保持这个反例。支持度/目标/复杂度的对照若要做，应与表示变化分开登记，并需下一批授权。未开启这些工作。

## 实现、检查与预算

新代码位于`hybridguard_agent/research/rule_learning_v2/`。复用V1 TrainQuantiles、canonical_core/project_core、transform_numeric、三值预测、TrainProblem的候选/支持/评分方法及greedy；仅适配V2训练容器与初始化、组合视图、模型封装和批次入口。没有申请V1内部capability，没有把真实记录标synthetic，没有改旧model.json，也没有重建旧dispatcher。

每次fit前已有 [batch_spec.json](batch_spec.json)与attempt_spec。worker只装载精确train成员和train标签，依次完成encoder/支持/选择，保存并加载V2模型后才打开本折评价特征；预测保存关闭后再连接评价sidecar。三折训练135/144/45、评价27/18/117，继承bundle及环境边界。每折所有62个数值输入的阈值都与同折已保存V1编码器一致，未从评价成员拟合。

拟合前10项合成边界检查通过，包括精确候选集合、别名/极性、T/F/U、train-only量化、旧数学内核一致性、保存加载、标签毒化隔离、空/失败模型和Native门控。首次合成夹具缺少展示元数据name而报错，修复后通过；该失败保留在 [test results](synthetic_test_results.json)，不涉及真实fit。

真实6次fit全部一次成功，未重试。运行环境为Python 3.14.3 / macOS-15.7-arm64-arm-64bit-Mach-O；这里的执行耗时用于本批计费，不作跨机器性能比较。事后代码检查补强了worker在部分预测写出后失败的保存路径：原文件保留，同时为全部预期阶段生成FAILED记录；新增1项定向合成测试通过。此改动不影响任何已完成trial，未重训或重生成其预测。运行时原源码已保存于 [trial_code_snapshot.json](trial_code_snapshot.json)，补强说明见 [postrun_engineering_note.json](postrun_engineering_note.json)。结果复核只读取保存产物，见 [verification.json](verification.json)。

原账本71次fit、103.041795334秒，加R09非fit扣账0.805261084秒，启动基数为103.847056418秒。V2-A新增6次fit、9.565894708秒计费，研究累计77/200次、113.412951126/21600秒；剩123次、21486.587048874秒。V2-A的6次fit额度已全部使用；剩余研究额度不构成下一批授权。计费采用预先保存的批次定义：worker wall覆盖读入、编码、训练、冻结、预测和评价；只读诊断/文档与合成夹具不计为真实trial执行。

[trials.jsonl](trials.jsonl)记录每次开始、结束和结果；[关联账本](linked_budget_ledger.json)保留原账本及R09引用，原账本未改写、未归零。所有模型、全编码器阈值、支持、选择轨迹、解释、预测与访问顺序位于`trials/`。

ZIP按相对路径只新增文件。原可变状态按原字节归档到`deliverables/v2_development/V1_STATUS_AT_V2_START.json`后，仅更新调度及V2指针；历史步骤、冻结快照和R01–R09结果保留。本批不自动commit、push或创建PR。V2-A完成，等待用户审查。
