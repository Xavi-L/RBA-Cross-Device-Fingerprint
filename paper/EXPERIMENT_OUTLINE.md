# HybridGuard 论文提纲：四项核心实验与图表安排

> 版本：2026-10-16。本文是论文动笔前的写作提纲，围绕本轮确定的四张结果图表组织论证，尚非论文正文或排版终稿。使用当前保存结果，不新增实验。图表已通过讨论稿可读性检查，尚未完成论文实际栏宽验收。

## 一、论文要讲清楚的主线

在当前受控材料中，跨层参照能够补充部分单层检查遗漏的修改，并区分某些正常变化与异常修改；正常报警约束限制了仅追求检出数带来的代价；加入独立 Browser 的跨端时区关系后，能力扩展到所测 Browser 时区修改，但两端语言修改仍然遗漏。

四项实验分别承担“展示总体效果”“解释正常代价”“解释机制”“展示扩展及边界”的任务。写作时应围绕这些问题展开，不把四张图表写成四段数字清单。

## 二、建议的全文结构与图表位置

以下章节号是写作建议，可随论文结构调整。图片内部的01–04及“表2/3/4”沿用讨论稿编号，最终图、表应分别按全文首次出现顺序重新编号；此处统一用“素材01–04”定位。

| 论文章节 | 本节内容 | 图表安排及作用 |
|---|---|---|
| 1 引言 | 说明单层观测的局限，以及为什么必须同时考虑检出、正常变化和无法判断 | 概括四项发现，完整图表留在实验部分 |
| 2 背景与威胁模型 | 区分 Native、WebView/宿主、App网页和独立Browser；说明正常变化、有效修改及攻击能力边界 | 为后续“修改发生在哪一端”建立清晰语义 |
| 3 方法 | 介绍跨层参照、正常报警约束、未知状态处理及跨端时区关系C1 | 先定义方法和条件，再在实验部分检验其作用 |
| 4.1 实验设置 | 交代材料、方法身份、计数单位、模型配置及评价边界 | 用简短文字或数据概况表解释所有分母 |
| 4.2 整体检测效果与组件消融 | 哪些修改可以检出，差异来自哪些组件，哪些仍遗漏 | **素材01：合并结果矩阵**，建立总体结果与缺口 |
| 4.3 正常报警约束的作用 | 为什么不能选择检出数最高的无上限版本 | **素材03：正常约束对照表**，紧接总体结果解释收益与代价 |
| 4.4 设备参照的机制验证 | 为什么设备参照比单字段条件更有用 | **素材02：专项纯表格**，分别解释补充检出和容忍正常变化 |
| 4.5 独立Browser带来的增量能力 | 跨端关系究竟补充了哪一类识别，哪些仍未解决 | **素材04：双端分组对照表**，定位新增能力及其边界 |
| 5 讨论与局限 | 汇总共同漏检、未接入条件、历史材料与开发使用等限制 | 回引四张图表，不把局部结果扩展成普遍泛化结论 |
| 6 相关工作 | 对照单层检测、跨层一致性与跨端参照等工作 | 说明研究差异，图表风格参考不充当方法有效性证据 |
| 7 结论 | 回答实验提出的问题，概括当前成立的发现及尚存缺口 | 不引入新结果 |

**正文顺序建议为01 → 03 → 02 → 04。** 四项的重要程度排序不变；调整展示顺序，是为了在读者看到108/126高于105/126时，立即说明取消正常报警上限的代价，再展开专项机制和跨端扩展。

## 三、4.1节必须先交代的实验设置

### 3.1 材料与分母

| 材料 | 当前图表使用范围 | 写作时的定位 |
|---|---|---|
| App主实验 | 14类修改配置，每类9次有效修改，共126次；受控正常252条 | 整体检测与组件比较，不能将修改次数解释为独立设备数 |
| MTC正常材料 | 630条约束训练记录；144条历史评价和117条历史保留评价 | 训练与历史评价分开，144/117分别报告，不称新的独立盲测 |
| 内存专项 | 18次有效修改、48条正常；另6次无可观察效果的操作 | 比较固定单条条件；无效果操作不并入有效修改分母 |
| 时区专项 | 6次有效修改、30条正常 | 6条正常换区属于30条正常的子集 |
| 屏幕专项 | 6次有效修改、66条正常 | 6条正常布局变化属于66条正常的子集 |
| 双端语言/时区材料 | 60个配对位置：14次有效修改、46条正常 | 来自18条先导与42条匹配材料，已有开发使用历史；正常46=12+34 |

这些材料承担不同的评价任务，部分存在来源或分析范围重叠，**不能将各表分母相加形成一个新的总体样本量或准确率**。

### 3.2 读图约定与方法身份

- 修改记录上的报警记为检出，正常记录上的报警记为正常报警；未报警不等于已经证明安全。未知、执行失败与空模型状态须与未报警分开。
- “14类修改配置”是修改类型/操作配方；“01、02、03”是三个冻结模型配置。二者不能混用，重复作用于同批材料不增加独立样本，也不能视作三次独立重复来计算显著性。
- 完整App为`APP_FULL`，不含独立Browser跨端C1；App小树为固定表示与容量的参考方法，不能代表所有机器学习方法。素材01规则结果取保存的`RETENTION`阶段，小树取`FITTED`阶段。
- 素材02比较固定单条条件，不是完整方法的消融分数；素材04的`PAIRED_BASE`是完整App加已保留的跨端时区关系C1。
- 当前材料均有开发使用历史。汇总计数相同可以用于压缩展示，但不表示已经证明逐记录输出相同，也不能据此宣称独立设备或未见工具上的泛化。

## 四、4.2 整体检测效果与组件消融——素材01

**研究问题：** 完整App在当前修改集合中能检测什么，跨层信息带来的差异集中在哪里？

**放置位置：** 4.2节首次介绍六种方法的比较后，作为实验部分第一张主要结果图；正文引用后紧接解读。建议按跨双栏结果矩阵安排，正式排版再确认字体和宽度。

**论证作用：** 建立全文的总体结果，定位资源、屏幕等类别的组件差异，同时明确所有方法共同遗漏的修改。它是后续正常约束、机制专项和扩展实验的出发点。

![素材01：App整体检测与组件消融的合并结果矩阵](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/01_app_contribution_compact.png)

**中文图注草案：** App侧整体检测与组件消融结果。14类修改配置按六种方法的完整状态计数向量相同合并为5组，相邻方法结果相同时进一步合并单元格。格内数字表示每类配置9次有效修改中的检出数，括号表示相对完整App的每类检出差值；左侧配置数保留各组权重，总计仍以126次修改为分母。完整App检出105/126；去MTC报警上限检出108/126，其正常代价见素材03。资源修改的差异体现内存参照的作用，Webdriver与WebGL标识两类修改在所有比较方法中均未检出。

**图下注记：** 灰色表示与完整App检出数相同，绿色表示更多，红色表示更少，颜色不表示方法整体优劣。所有方法在本批受控正常记录上均为0/252报警；本图未知、失败和空模型计数均为0。规则方法与小树沿用各自保存阶段。5组是展示压缩，未删除原14类配置，也未增加样本。

**English caption draft:** App-side detection and component comparisons on 126 controlled effective modifications. Fourteen modification configurations are grouped into five rows when their complete six-method count vectors agree; adjacent equal cells are merged. Each cell gives detections out of nine modifications per original configuration, with differences relative to Full App in parentheses. Group sizes preserve the original weighting. Full App detects 105/126 modifications, versus 108/126 without the MTC alarm cap; the latter's normal-record cost is reported separately. Webdriver and WebGL-identifier modifications remain undetected by every compared method. All methods produce 0/252 alarms on the controlled normal records; unknown, failed and empty-model counts are zero.

**正文应展开的三点：**

1. 先报告105/126及共同漏检，不用总分掩盖类别差异。
2. 解释资源类中完整App相对网页单层、去内存关系方法多检出的9次，以及小树的具体缺口；结论限定于这些固定方法和材料。
3. 指出取消MTC报警上限多检出3次屏幕修改，并立即引出4.3节：这些额外检出是否伴随正常代价？去时区关系总分未变的问题留到4.4节解释。

**写作边界：** 不写“完整App总分最高”“消除了所有修改”“规则普遍优于机器学习”。本图也不能独立证明系统时区参照没有作用。

[可编辑SVG](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/01_app_contribution_compact.svg) · [合并映射与计数](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/01_compact_groups.json)

## 五、4.3 正常报警约束的作用——素材03

**研究问题：** 取消MTC正常报警上限获得的检出增益，是否足以支持采用该版本？

**放置位置：** 紧接4.2节的108/126与105/126比较，先提出收益与代价问题，再放本表。建议使用跨双栏三线表，以便保留两组正常材料及三种输出状态。

**论证作用：** 解释为什么只看受控修改检出数或受控正常0/252不够，为保留正常报警约束提供证据。取消的是报警上限，不能描述为完全移除MTC数据。

![素材03：保留与取消MTC正常报警上限的对照表](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/03_normal_constraint_table.png)

**中文表注草案：** 保留和取消MTC正常报警上限的正常记录输出比较。对144条历史评价记录，保留上限的模型配置01/02分别产生1条报警、135条未报和8条未知，配置03为0、136、8；对117条历史保留评价记录，对应结果为1、110、6和0、111、6。取消上限后，三个配置均对两组正常记录全部报警。该变化只使受控修改检出由105/126增至108/126，受控正常报警仍均为0/252，说明受控正常集合未揭示这项历史正常代价。

**表下注记：** 数值为记录数；未知不计为未报，失败与空模型均为0。相同汇总计数合并展示，每个模型分别作用于同批记录，不合并配置分母。630条约束训练记录另计：保留上限三配置报警6/6/0条、各51条未知；取消上限均630条报警。144与117均为历史评价材料，并非新的独立盲测。

**English caption draft:** Normal-record outcomes with and without the MTC alarm cap. The two historical evaluation cohorts contain 144 and 117 records. With the cap, configurations 01/02 produce one alarm in each cohort, while configuration 03 produces none; unknown counts are eight and six, respectively. Removing the cap makes all records in both cohorts trigger alarms for every configuration, while increasing controlled-modification detections only from 105/126 to 108/126. Controlled normal alarms remain 0/252 for both methods. Equal counts are merged for display without pooling configurations. Unknowns remain separate, and failed and empty-model counts are zero. The 630 constraint-training records are reported separately. These are historical results, not a new blind evaluation.

**正文应展开的三点：**

1. 用“多检出3次，但两组历史正常全部报警”直接回答研究问题。
2. 说明为何正常材料必须覆盖受控环境之外的已有历史记录；0/252不能替代MTC正常评价。
3. 把约束的作用解释为限制正常代价，随后转入4.4节，讨论怎样利用设备参照改善具体条件的区分能力。

**写作边界：** 不把未知算成正常通过；不将受控修改合计的+3与某个历史模型配置强行配对，计算“每新增一次检出对应多少误报”的因果比值；不称已证明跨设备普遍低误报。

[可编辑SVG](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/03_normal_constraint_table.svg) · [表内计数及原分组](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/03_table_data.json)

## 六、4.4 设备参照的机制验证——素材02

**研究问题：** 设备参照如何帮助补充检出，同时避免把正常设置或布局变化误判为修改？

**放置位置：** 在介绍专项条件及其与完整模型的区别后放表。正文按内存、时区、屏幕三个短段落解读，不重复描述所有表格数字。建议先按跨双栏纯表格安排。

**论证作用：** 将总体比较中的现象落实到可解释的检查条件。内存说明“单字段阈值会遗漏”，时区与屏幕说明“低误报和有效检出需要共同考虑”。

![素材02：内存、时区与屏幕的设备参照专项表](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/02_reference_mechanisms_table.png)

**中文表注草案：** 固定单条检查条件在内存、时区和屏幕专项中的检出与正常报警。内存设备参照在18次有效修改中检出18次，网页内存大于8 GiB条件检出6次，两者在48条正常记录上均无报警。系统时区参照与绝对时区偏移条件均检出6次修改，但正常报警由6/30降至0/30。宿主几何上界与固定网页高度条件均检出6次屏幕修改，但正常报警由6/66降至0/66；同网页视口关系虽无正常报警，却未检出这6次修改。各专项分别比较，不合并成一个总体分数。

**表下注记：** 星号标识设备参照条件。内存另有6次无可观察效果的操作，两条件均未报警，不计入18次有效修改，也不记为漏检。时区正常换区6条和屏幕正常布局变化6条分别包含在30条和66条正常分母中。本表未知与失败均为0。宿主几何上界仍是独立专项条件，尚未接入完整App模型；不能用该条件的结果替换整体模型分数。

**English caption draft:** Specialist comparisons of fixed checks using device references. The memory-reference check detects 18/18 effective modifications, versus 6/18 for the Web-memory threshold, with 0/48 normal alarms for both. The system-timezone reference retains 6/6 detections while reducing normal alarms from 6/30 to 0/30. The host-geometry bound retains 6/6 screen-modification detections while reducing normal alarms from 6/66 to 0/66; the same-Web viewport relation detects none. Cohorts are separate. Six memory operations without an observable effect are excluded from the effective-modification denominator. Unknown and failed counts are zero. The host-geometry check is a standalone specialist condition and is not integrated into Full App.

**正文应展开的三点：**

1. 内存：解释设备相关上界为何能发现当前样本中被统一8 GiB阈值漏掉的12次修改；结论限于已测的向上修改。
2. 时区：指出素材01中去时区关系总检出未变，并不等于关系无用；本专项表明设备参照有助于区分正常换区和网页单独修改。这里的固定条件结果仍须与完整模型身份分开。
3. 屏幕：同时比较“能检出但有正常报警”“无正常报警但全部漏检”“保留检出且减少正常报警”三种状态，并明确新几何条件尚未接入整模。

**写作边界：** 不把三个专项拼成一个总体准确率，不将无效果操作记为漏检，不把专项条件结果说成完整App已获得的改进，也不外推到未测内存方向或屏幕环境。

[可编辑SVG](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/02_reference_mechanisms_table.svg) · [条件与计数映射](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/02_table_data.json)

## 七、4.5 独立Browser带来的增量能力——素材04

**研究问题：** 在完整App基础上加入跨端时区关系，增益具体发生在哪一端、哪一类修改？

**放置位置：** 实验部分最后一个核心结果小节。先明确完整App与完整App+C1的区别，再展示按App/独立Browser分组的表格，最后讨论仍未解决的语言修改。建议跨双栏排版，保留两级列头。

**论证作用：** 展示已有方法向独立Browser的有限扩展；通过分类型结果解释增益来源，避免仅用2/14→7/14暗示所有跨端修改都得到改善。

![素材04：App与独立Browser分组的增量能力对照表](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/04_cross_endpoint_table.png)

**中文表注草案：** 完整App与加入跨端时区关系C1后的分类型结果。App时区和语言修改各2次，独立Browser时区和语言修改各5次；加入C1后，Browser时区检出由0/5升至5/5，App时区保持2/2，两端语言仍为0/2与0/5。总检出由2/14增至7/14，5次新增全部来自Browser时区。同批46条正常记录上，两方法均无报警。增加条数行表示计数差，不表示百分点变化；粗体仅标记变化，不表示统计显著。

**表下注记：** 本批60条配对位置已有开发使用历史，含14次有效修改和46条正常；各类未知与失败均为0。三个冻结模型配置的展示计数相同，因此只显示共同计数，不将5/5扩为15/15，也不声称逐记录状态相同。另在历史MTC 261条记录（原144与117两组）上，各配置正常报警数不变，但未知由14增至17。0/46不能替代该正常侧背景，也不能作为新盲测或普遍零误报的证据。

**English caption draft:** Direction-specific detection counts for Full App and Full App plus the retained cross-endpoint timezone check C1. The five additional detections occur only for Browser timezone modifications; App timezone detections are retained and both language families remain undetected. Total detections increase from 2/14 to 7/14, with 0/46 normal alarms for both methods. The last row reports count differences, not percentage points; bold indicates changes, not significance. Counts agree across three frozen configurations and are displayed once. These 60 positions have development-use history. Across the separate historical MTC groups of 144 and 117 records, the combined unknown count increases from 14 to 17 out of 261 within each configuration, while the corresponding alarm count is unchanged.

**正文应展开的三点：**

1. 先把新增5次定位到Browser时区，而不是只报告总检出增加。
2. 指出App时区能力保留，但App和Browser语言修改均未改善，C1并不等于通用跨端检测能力。
3. 同时交代0/46正常报警和历史未知增加，形成对能力与代价的完整描述，并引出讨论部分。

**写作边界：** 不将完整App误写为Browser-only方法，不把C1称为语言关系模型，不将开发结果说成未见设备/工具的独立评价，也不与资源扩展或四视图树的结果混成一个“最终模型成绩”。

[可编辑SVG](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/04_cross_endpoint_table.svg) · [分类型计数与正常背景](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/04_table_data.json) · [WWW表格结构参考记录](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/paper/figures/experiment_storyboards_20261016/04_DESIGN_REFERENCES.json)

## 八、讨论与附录的安排

### 8.1 讨论部分回收的四个问题

1. **仍有哪些修改无法覆盖？** 回引素材01的Webdriver/WebGL共同漏检和素材04的语言修改遗漏，按各自实验材料分别讨论，不能把跨实验同名字段视作同一修改配方。
2. **为什么需要报告正常与未知？** 回引素材03的无上限正常报警，以及素材04的历史未知增加，区分未报、未知和失败。
3. **哪些机制证据尚未变成完整方法？** 回引素材02的新宿主几何条件，明确专项有效不等于已经接入整模。
4. **当前证据能推广到哪里？** 说明材料已有开发使用历史、有限修改配方与环境、冻结配置不构成独立重复；新的独立评价须另行设计，不能由现有图表替代。

### 8.2 主文与附录分工

| 留在主文 | 放入附录或补充材料 |
|---|---|
| 四张当前压缩图表及关键图/表注 | 素材01的原14类×6方法明细、五组完整成员及方法映射 |
| 每项实验的核心问题、主要结论与影响结论的边界 | 模型配置01/02/03逐配置完整计数，不能只保存合并后的版本 |
| 正常报警、未知与开发材料性质 | MTC630训练与144/117历史评价的完整状态表 |
| 两端语言未改善、新几何条件未接入等负面结果 | 专项修改配方、正常变化子集、无效果操作及原始来源定位 |

**动笔时的执行顺序：** 先写4.1，固定各类材料和方法的身份；再按01→03→02→04逐节写结果与解释；最后根据实际支持的结论写引言和贡献。正式排版时统一图表编号、语言和栏宽，移除图内与图注重复的说明；本提纲不要求现在重画或重跑实验。
