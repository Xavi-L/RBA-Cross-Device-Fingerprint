# 第一轮 App 图注与读图说明

状态：**初稿／待导师选择正文或附录**。F01、F02、F03a、F03b、F04是稳定素材编号，不是最终论文图号。

所有数字均从本轮CSV指向的已保存结果读取。材料已有开发使用历史，不能称为新盲测；本轮仅汇总和制图。T表示报警，F表示未报警，U表示无法判断，FAILED表示执行失败；F不表示已证安全。计数分母是记录／评价位置，不是设备数。

六方法顺序固定为：`APP_FULL`（Full App，当前App完整方法）、`A_NO_MTC_CAP`（No MTC alarm cap，去MTC正常报警上限）、`A_APP_WEB_ONLY`（App Web only，只看App网页）、`A_NO_MEMORY_REL`（No memory relation，去系统—网页内存关系）、`A_NO_TIMEZONE_REL`（No timezone relation，去系统—网页时区关系）、`APP_TREE`（Small App tree，固定小容量App树）。规则取RETENTION，小树取FITTED；Full不含跨端C1，也不是四视图树。四项消融是原先重新选择／拟合后保存的完整模型；本轮没有重训。图中01／02／03对应三个冻结配置，完整ID保存在`data/folds.csv`。

<a id="f01"></a>

## F01：14种修改配置的App检出

**读图说明。** 行是14种修改配置，列是六方法；每格为报警T/9，颜色为T/9换算的0—100%比例。全部14行均保留，含webdriver和WebGL的0/9。逐方法合计依次为105/126、108/126、96/126、96/126、105/126、72/126，见`data/T02.csv`。各方法受控前后正常均为0/252报警。所有这些主结果的U、FAILED、EMPTY_MODEL均为0。126个修改评价位置来自原环境留出结构的不重复合计，不能将三个模型对全批次的输出再相加；总计的分母126不同于单格9。

**能支持什么。** 在当前App候选表示及已保存开发评价中，内存关系被移除后，CPU与内存联合修改从Full的9/9报警变为0/9；屏幕修改Full为6/9，去MTC上限为9/9。去MTC上限虽多检出3/126，其正常设备代价必须同时看F02。

**不能支持什么。** 108/126不能单独标成最佳方法；受控正常0/252不替代MTC正常评价。当前webdriver/WebGL的0/9不等于这些修改在原则上不可检测，小树72/126也不是全部177个原始字段或所有机器学习方法的性能上限。此图不提供未见环境、未见修改方式的独立泛化证据。

**English caption.** **Detection across 14 App intervention configurations.** Cells show alarm counts T/N, with N=9 effective interventions per row; color uses a fixed 0–100% scale. The six methods yield 105/126, 108/126, 96/126, 96/126, 105/126, and 72/126 alarms, respectively, over non-overlapping evaluation positions in the original environment-held-out structure. Each method alarms on 0/252 controlled normal records; U, FAILED, and EMPTY_MODEL counts are zero. Rule methods use saved RETENTION results and the small App tree uses FITTED results. Removing the MTC alarm cap adds three detections but incurs the normal-record cost shown in F02. These materials have a development-use history and are not a new blind evaluation; repeated model outputs are not additional independent samples.

<a id="f02"></a>

## F02：MTC历史正常记录的输出组成

**读图说明。** 每个方法保留三个配置，共18条横向100%堆叠条。每条只把同一模型的development 144与reserved_validation 117相加，分母为261；discovery 630是训练约束部分，仅在`data/T03.csv`保留，不进入图中分母。四状态为T/F/U/FAILED，右侧同时列原计数与明确输出(T+F)/261；1—3条报警按真实比例绘制。全部18条的FAILED和EMPTY_MODEL均为0，空模型没有并入F。

Full的01／02／03配置分别为2/245/14/0、2/245/14/0、0/247/14/0，明确输出均247/261；去MTC上限均261/0/0/0，明确输出261/261。Web-only为3/257/1/0、3/257/1/0、1/259/1/0；去内存关系为2/258/1/0、2/258/1/0、0/260/1/0，两者明确输出均260/261。去时区关系为3/244/14/0、3/244/14/0、1/246/14/0，明确输出247/261。小树各配置均0/261/0/0，明确输出261/261。此处四个斜线分隔的计数顺序均为T/F/U/FAILED，分母均261。

**能支持什么。** 当前Full保留较低的正常报警计数，同时有14/261无法判断；去内存关系后未知为1/261，需与F03a中的检出损失并读。去MTC报警上限在三配置上均对261/261历史正常记录报警，展示了仅看F01主分数会漏掉的代价。

**不能支持什么。** MTC是历史正常材料，不提供攻击泛化证据。三配置重复使用相同261条记录，不产生783个独立样本，也不作为三个独立重复计算置信区间或显著性。小树的二值输出不表示缺失观测恢复：`tree_input_integrity`显示每配置在完整MTC891中有73/891记录包含未知候选，路径使用缺失原子的计数为0/891；该73/891不是本图261子集的缺测计数。算法输出口径不同，不能把小树0个U理解成输入测量更完整。本图Full的14/261 U不得与旧App+C1的17/261 U混用。

**English caption.** **Output composition on historical MTC normal records.** Each bar represents one method and one frozen configuration (01–03), combining development (N=144) and reserved-validation (N=117) counts for N=261; the discovery set (N=630), used for training constraints, is excluded. Bars retain the true proportions of alarms (T), no alarms (F), unknown outputs (U), and failures (FAILED); exact counts and defined outputs (T+F)/261 appear at right. FAILED and EMPTY_MODEL are zero throughout. Full App produces 2/261, 2/261, and 0/261 alarms, with 14/261 unknown outputs in each configuration; removing the MTC cap produces 261/261 alarms in all configurations. Binary tree outputs do not imply complete measurements: the saved input-integrity audit identifies unknown candidate inputs in 73/891 records of the full MTC cohort per configuration, a different denominator from this figure. The configurations reuse the same records and are not independent statistical replicates. These previously used normal materials do not establish attack generalization or a new blind-test result.

<a id="f03a"></a>

## F03a：完整App方法在内存专项上的表现

**读图说明。** 每个冻结配置均评价同一72个位置：18次有效修改、48条已定义正常对照、6次无可观测变化。六方法有效修改报警依次为18/18、18/18、0/18、0/18、18/18、0/18；正常各0/48，无变化各0/6。三配置这些汇总计数已经逐项核对相同，因此图中压缩成每方法一组，意为“各配置均为该计数”；全部配置仍保存在`data/F03a.csv`。这不表示已经比较并证明逐条输出相同，也不把18次修改扩成54次。所有所示子集的U、FAILED、EMPTY_MODEL均为0。

**能支持什么。** 在当前完整模型及所测内存专项上，Full与去内存关系、Web-only有18/18对0/18的检出差异。该差异须与F02中Full的14/261 U和去内存关系的1/261 U一并报告，呈现检出与观测需求之间的取舍。

**不能支持什么。** 本图不是“两条内存条件消融”，也不是旧B/B_REL专项模型比较。无变化的6个位置不算漏检攻击，亦不并入48条正常。F03a与F03b使用同一内存专项的不同分析层，不能叠加样本；向上修改中的18/18不保证向下修改、仍在上界内的有效修改、任意设备或任意内存口径可检出。

**English caption.** **Saved full-model outputs on the memory-only specialist batch.** For each frozen configuration, the batch contains 18 effective interventions, 48 defined normal controls, and six operations with no observable change. Effective-intervention alarms are 18/18, 18/18, 0/18, 0/18, 18/18, and 0/18 in the displayed method order; all methods produce 0/48 normal alarms and 0/6 alarms on unchanged operations. U, FAILED, and EMPTY_MODEL are zero. Each displayed count holds separately for configurations 01–03; identical aggregate counts are compressed visually, not pooled into a larger sample or asserted to prove identical record-level outputs. This compares saved complete methods, including previously retrained ablations, rather than the two fixed conditions in F03b. The shared batch has a development-use history and tests upward memory changes only; 18/18 does not establish detection of arbitrary memory changes. The availability cost on historical normal records is reported separately in F02.

<a id="f03b"></a>

## F03b：固定内存关系与单字段阈值

**读图说明。** 仅取原`summary.json`的`new_batch`，不取`historical/controlled`。R_REL使用同次Native总内存形成不小于它的最小二次幂上界，检查Web报告是否超出；R_WEB8仅检查有效Web报告W>8，W=8不会触发。目标4、8、16分别有6次有效变化：R_REL依次6/6、6/6、6/6，R_WEB8依次0/6、0/6、6/6；合计分别18/18和6/18。两条件正常均0/48。目标2原值未改变，6次操作两条件均0/6，独立保存而不作为第四组攻击检出率。全部主分母保留，U和FAILED均为0，未按共同可评估子集缩小分母。

正常分母核对：旧汇总的`new_batch.normal_phases.normal_basis_supported.n`为0，与其`planned_n=48`及两条件F=48是不同字段。本轮另读已有`timezone_relation_validation_v1/MEMORY_NORMAL_REVIEW.json`的汇总：确认正常48、缺支持0，且明确历史输出未修改、两条件均F=48。保留该旧字段，不用它替换绘图分母，也未重新复核原始记录。

原有效性计数为24/24操作执行、18/24可观测目标变化、6/24无可观测变化、24/24恢复；24/24未观察到所检查非目标字段变化。这些是操作／有效性证据，不是额外的模型检出样本。

**能支持什么。** 在此单字段向上修改批次中，系统参照相对W>8补充了目标4和8共12/18次信号。差别来自同次设备参照，不能仅因值为4或8就称为异常；图没有拼接不同设备的Native/Web值。

**不能支持什么。** 这是两个固定条件的触发比较，不能替代F03a完整模型结果。三环境、每目标两轮是有限环境重复观察，72个位置不等于72台设备；F03a与F03b也不是两次独立实验。所测有效变化均从2向上，尚不能给出向下变化、改变后仍在上界内或Native/Web协同变化的真实检出率。不能用18/18推广到任意内存修改，不能把目标2无变化当成已验证的上界内有效修改。

**English caption.** **Fixed memory-relation and single-field conditions on the saved memory-only batch.** At reported targets of 4, 8, and 16, each group contains six effective upward changes from an original report of 2. R_REL, which compares Web-reported memory against a power-of-two upper envelope of the same-record Native total memory, triggers on 6/6 changes in each group. R_WEB8, the fixed W>8 condition, triggers on 0/6, 0/6, and 6/6, respectively. Totals are 18/18 versus 6/18, with 0/48 triggers on normal controls for both conditions. Six target-2 operations cause no observable change and are listed separately (0/6 triggers each), not counted as missed attacks. U and FAILED are zero; denominators retain all planned positions in each group. These are saved condition outputs on the same previously used specialist batch as F03a, not independent new data or complete-model outputs. The results support a local distinction for upward changes and do not establish detection of downward or within-envelope changes.

<a id="f04"></a>

## F04：正常系统换时区与网页单独修改

**读图说明。** 两列分别是正常系统变化与网页单独修改，均显示报警T/6；正常列越低越好，修改列报警表示检出。正常列只汇总`L_America/Los_Angeles`、`L_UTC`中`phase=change`且`identity=NORMAL`的6个位置；修改列只汇总对应`A_`场景中`phase=change`且`identity=EFFECTIVE_INTERVENTION`的6个位置，没有加入ALL聚合行。六方法的“正常变化；修改”分别为0/6；6/6，0/6；6/6，6/6；6/6，0/6；6/6，6/6；6/6，0/6；0/6。

三配置各自均为上述计数，因此压缩展示，完整三配置保存在`data/F04.csv`。所有正常30条及有效修改6条另列`data/F04_totals.csv`；全部正常报警依次0/30、0/30、6/30、0/30、6/30、0/30。正常系统变化的6个位置是这30条的子集，不能相加为36条正常。以上所有行的U、FAILED、EMPTY_MODEL均为0。

**能支持什么。** Full与去时区关系在F01旧主实验同为105/126，但此处正常系统变化分别0/6与6/6报警，修改均6/6。总分相同仍可掩盖正常代价；关系的局部价值是容忍所测真实系统设置变化。小树正常0/6同时修改0/6，不能只展示正常侧作为胜出证据。

**不能支持什么。** 数值是当前六方法的保存输出，未混入旧时区专项模型预测；三配置不增加独立样本。该有限环境材料已有开发使用历史，不能称新盲测。地区名称不同但当前偏移相同、两端协调变化、时区数据库版本和读取不同步等仍是边界；本图不保证任意时区修改都能识别，也不证明恶意意图。

**English caption.** **Alarms on normal system time-zone changes and isolated App Web changes.** The first column contains six confirmed normal change-phase positions from L_America/Los_Angeles and L_UTC; fewer alarms are preferable. The second contains six effective App Web intervention positions from the corresponding A_ scenarios, where alarms indicate detection. Full App produces 0/6 versus 6/6 alarms, whereas App Web only and No timezone relation each produce 6/6 in both columns. No MTC alarm cap and No memory relation produce 0/6 versus 6/6; Small App tree produces 0/6 in both. These counts hold separately for all three frozen configurations, which are displayed compactly without pooling independent samples. The six normal change positions are included in the 30-record normal cohort reported separately; they must not be added again. U, FAILED, and EMPTY_MODEL are zero. Equal main-experiment totals of 105/126 for Full App and No timezone relation therefore conceal different normal-change costs. These saved outputs on previously used, limited-environment materials are not a new blind test or evidence for arbitrary time-zone modifications.
