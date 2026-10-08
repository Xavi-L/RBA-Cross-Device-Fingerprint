# RBA / HybridGuard：当前制图清单

**制定日期：2026-10-08｜当前阶段：已有实验结果的论文图表制作**

本清单是当前制图工作的执行入口，与[总体实验规划](RBA_PRE_PAPER_EXPERIMENT_PLAN.md)配套。旧规划保留多轮历史安排，不据此重启已经完成的实验。研究事实与论文表述以[导师实验总报告](RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md)和[最新统一结果](deliverables/app_browser_evidence_consolidation_v1/REPORT.md)为准。

**本次只编写清单，没有生成新图、重新采集、训练、选择模型、预测或计时。第一轮范围为F01、F02、F03a、F03b、F04；其余项目只是后续安排，不自动执行。** 导师正在写提纲，先准备可独立使用的图和图注，最终正文／附录位置与论文图号待提纲确定。

参考仓库提交：`2a83385d2f6119da90505e3a95518ae23296a9aa`；其中实验事实基线为`14540e6c946e6f6bd54ca3dca7d59694526ce6e0`。以下证据链接固定到前一提交。执行时核对实际文件摘要；若只有文档提交变化，不因此重做实验。

## 一、图集要讲清楚什么

第一条主线是**App主体**：当前App方法识别了哪些修改，系统内存／时区参照和MTC正常设备约束分别起什么作用。第二条是**App与独立Browser相互参照**：新增信息在哪个修改方向有用，什么时候会产生正常误报。第三条是**组合的代价**：单条关系有用，不等于能够通过完整方法的正常报警与明确输出要求。

图不能只显示检出，不显示正常代价；也不能把App、单条条件和小决策树的最好成绩拼成一个系统。

| 本清单中的名称 | 对应实验对象 | 图中必须保留的范围 |
|---|---|---|
| 当前App方法 | `APP_FULL`，B_REL_TZ的RETENTION结果 | App当前候选库；不是全部177字段都有独立贡献；不含新Host几何和Browser条件 |
| 双端基础方法 | `PAIRED_BASE`，原App加跨端时区C1 | 资源选择实际保留的S0；不是资源增强模型 |
| 资源诊断组合 | S0加M、B或W | 未通过接入要求；19/26不能标成已接受方法的成绩 |
| App小树 | `APP_TREE` | 相同App候选表示下的固定小容量参考 |
| 四视图小树 | V_APP／V_BROWSER／V_BOTH／V_BOTH_REL | 仅语言／时区有限表示，不能简称全部App177／Browser67模型 |
| 单条条件／专项 | 内存上界、单字段阈值、Host几何等 | 单项触发不等于整模检出；Host仍是专项 |

## 二、总清单与制作顺序

F编号是稳定素材编号，不是最终论文图号。一个图组允许输出若干独立文件，不能为了压成一张图而把字缩到难以阅读。下表是候选图集，不要求全部挤进正文；能够由表格更清楚说明的内容不强行画图。

| 编号 | 要回答的问题及建议图形 | 数据与方法 | 主要证据 | 当前状态／优先级／建议位置 |
|---|---|---|---|---|
| **F01 App配置检出热图** | 哪些修改依赖哪些App组件？14行配置×6列方法，格内写检出数/9；总结果另附表 | 原378条；完整App、4项重训消融、App小树 | S01、S02 | **第一轮待制作**；正文优先或正文摘要＋附录全图 |
| **F02 App正常输出组成** | 低正常报警是否由大量无法判断换来？横向100%堆叠条＋右侧精确计数 | MTC历史评价144＋117；6方法×3配置；训练630及两个评价子集另表 | S01、S02 | **第一轮待制作**；正文优先；不拿旧Browser图替代 |
| **F03 App内存作用** | a：移除参照后，完整方法在内存专项损失多少？b：同样上报4、8、16，系统参照和单字段阈值有何差别？ | a用当前App专项回放；b用原内存专项的固定两条件对照 | S02、S03 | **第一轮F03a/b待制作**；a或b择优正文，另一幅附录；不得混称同一模型 |
| **F04 App时区正常变化** | 去掉关系后，为什么旧总分不变却重新误报正常换区？报警率点图或计数热图，两类场景并列 | 同36条专项：正常系统变化6个中间位置、网页单独修改6个位置；全部正常30另表 | S02、S04 | **第一轮待制作**；正文优先 |
| **F05 双端分方向比较** | App修改和Browser修改分别由谁发现？ | 语言／时区60条与资源54条分别绘制；App、双端基础与资源单条件分栏 | S01、S05 | 第二轮；正文优先；不能把60与54合成一个总准确率 |
| **F06 四视图检出与正常代价** | 相同小树下，多一端信息或明确关系有什么作用？ | P0、P1、P2分别显示；检出图与正常报警图配套 | S06、S09 | 第二轮；已有旧图可复用数据和脚本，需统一风格；保留P2无收益和P1训练正常反例 |
| **F07 资源接入取舍** | 为什么能多发现修改，却没有接入当前完整方法？ | 同1,005成员；S0、S0+M/B/W，开发／历史分开，三个配置分开 | S07、S01 | 第二轮；正文优先；展示26次修改、MTC报警和567/630对560/630，明确后者未达标 |
| **F08 正常语言偏好反例** | 正常更改偏好与脚本修改，首选语言相同为什么仍不能用同一解释？ | 两条正常偏好、对应修改、完整列表长度及固定树输出 | S06、S09 | 第二轮按提纲选做；旧图可复用；列表长度差异不等于识别恶意意图 |
| **F00 方法与实验流程** | 哪些信息来自系统、宿主、App网页和独立Browser？训练与当前记录推理怎样分开？ | 实际已实现链路；Host专项、新资源未入选部分用明确旁支标记 | S00、S01 | 第三轮随提纲确定；示意图不是测量结果，不提前画成所有模块已联合部署 |
| **F09 宿主几何专项** | 正常布局扩大为何不应被固定高度误报？ | v15的72条；旧高度、同Web关系、新Host上界，正常66／修改6 | S08 | 第三轮候选；正文案例或附录；不宣传为整模改善，不混入v16工程位置 |
| **F10 运行成本** | 输入准备、判断、文件读取与采集配对各占什么成本？ | 既有分阶段计时；不新增基准测试 | S09 | 第三轮，优先成本表；不把批次均摊P95称单请求尾延迟 |
| **F11 早期开发与其他探索** | 为什么不以早期100%为最终卖点？WebGL专项证明了什么？ | 历史同成员开发对照、MTC高报警、WebGL局部观察各守原分母 | S00中相应历史证据索引 | 可选附录，优先表格；不把历史开发轨迹画成新方法持续泛化提升 |

配套表格：**T01数据范围与用途**；**T02当前App主结果**；**T03正常输出分组明细**；**T04双端分方向及资源24组合明细**；**T05分阶段成本**。第一轮只交T01的现有范围整理、T02和App部分T03；其他随对应图组制作。图表互补，不重复堆同一组数据。

## 三、第一轮的具体制作要求

### F01：App主体14配置热图

从S02的`configurations14.csv/json`读取六方法主阶段结果，必须与`main.csv/json`逐方法合计一致。此汇总已固定规则RETENTION和树FITTED；需要核查阶段时只读`all_stages`，不运行原汇总器或训练器。

每个修改配置分母为9，共14配置、126次修改；配对正常共252条。方法顺序固定为APP_FULL、A_NO_MTC_CAP、A_APP_WEB_ONLY、A_NO_MEMORY_REL、A_NO_TIMEZONE_REL、APP_TREE。列名使用易读英文简称，并在图注／映射CSV解释原ID。保留WebGL、webdriver的零检出及屏幕6/9，不只保留有收益的行。

热图显示0到100%的完整范围，每格标计数。无法判断／失败不是0检出格的另一种写法：若实际存在须额外标记并保留分母。总分是同一原环境留出结构下不重复位置的合计，不是把三个模型各自全量预测相加。

### F02：App在MTC上的正常输出

六方法各保留01／02／03三配置，主图可将144与117同一模型的计数相加为261；图注明确为两个历史正常评价部分的合计。630训练侧不能混入。T03同时保留630／144／117三列，便于核对。

堆叠条表示报警、不报警、无法判断、执行失败的占比；右侧写原始计数及明确输出数/261，避免1—3条报警在图中消失。不能把小片段故意加宽；若需放大，另画清楚标明范围的辅助图，而不改变主图比例。空模型若出现另列，不归为不报警。

App小树能在部分测量缺失时输出二值，因此旁注输入完整性来源`tree_input_integrity.json`；不能写成小树恢复了缺测。此图是App主体，不复用旧App+C1图直接换标题。

### F03a：完整App方法的内存专项回放

同72条专项材料，按每个冻结配置分别读取：18次有效变化、48正常、6次无可观测变化。展示六方法的检出和正常代价；“无变化”单列，不纳入有效修改分母。可用点图／紧凑计数图，MTC缺测代价交由F02说明。

三个配置计数相同可在核对后压缩呈现，但必须写“每个配置均为该计数”，保留三份数据，不把18变54；仅汇总相等不能声称逐条状态相同。此图的主体是完整App模型，不是R_REL这条单条件。

### F03b：内存参照与单字段阈值

只读S03的保存条件结果。固定比较原R_REL与R_WEB8，按目标4、8、16分别展示各6次有效变化的触发。目标2的6次操作没有可观测变化，单列说明；48条正常对照另报。

当前数据的核对参照是R_REL 18/18、R_WEB8 6/18，两者正常0/48；4和8各6次为参照触发、单字段未触发，16各6次共同触发。它证明所测范围内的局部区别，不保证任意内存修改都可识别。数值必须由保存结果读取，不能将这段参照直接硬写成作图数据。

可以先做分组计数图，不强制追加散点图。未来若需要展示同样上报4在不同设备上的正常／修改案例，只能使用各自真实绑定的记录，不能借另一个设备的Native值作反事实样本。

### F04：正常系统换区与App网页单独改区

使用S02 `specialists`中`cohort=timezone`的保存行。正常中间位置为`scenario=L_*`、`phase=change`、`identity=NORMAL`，合计6；修改中间位置为`scenario=A_*`、`phase=change`、有效修改，合计6。不要再加`ALL`聚合行造成重复。全部30条正常作为独立汇总附表，不能与这6条再次相加。

展示六方法、三配置，并列“正常系统换区”和“网页单独修改”的报警计数。APP_FULL在正常变化0/6、修改6/6；去时区关系及Web-only在正常变化6/6、修改6/6。旧主实验Full与去时区都是105/126，不妨碍这里揭示正常代价。其他方法从结果文件读取，不猜测。

## 四、证据入口

S编号用于查源，不是新实验编号。目录链接中选用具体文件后，在每张图的清单内保存相对路径、文件摘要、筛选条件和输出CSV。

| 编号 | 固定入口 | 用途 |
|---|---|---|
| S00 | [导师实验总报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md) | 完整研究主线、论文表述和历史实验索引 |
| S01 | [统一机器表](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app_browser_evidence_consolidation_v1/tables.json)；[证据矩阵](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app_browser_evidence_consolidation_v1/evidence_matrix.csv) | 交叉核对角色、分母和分配置展示；不是从报告表格手抄数据 |
| S02 | [App主体保存汇总](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/tree/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app177_core_ablation_v1/results/summary)；[App报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app177_core_ablation_v1/REPORT.md) | main、configurations14、mtc、specialists、tree_input_integrity；F01—F04主体来源 |
| S03 | [内存条件保存汇总](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/memory_relation_validation_v1/summary.json)；[原专项报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/memory_relation_validation_v1/REPORT.md) | F03b；原固定条件及目标值分组，历史与新专项分开 |
| S04 | [时区专项报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/timezone_relation_validation_v1/REPORT.md) | 操作和语义解释；当前六方法数值仍取S02统一回放，不混用旧模型 |
| S05 | [资源配对报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app_resource_paired_validation_v1/REPORT.md)；[资源条件结果](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/tree/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app_resource_paired_validation_v1/results) | F05资源54、固定条件和正常反例 |
| S06 | [四视图主比较](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/cross_endpoint_four_view_comparison_v1/results/main_comparison.csv)；[完整分组结果](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/tree/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/cross_endpoint_four_view_comparison_v1/results) | F06／F08，P0/P1/P2、训练反例、输入完整性和相同输入例子 |
| S07 | [资源联合保存结果](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/tree/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app_resource_constrained_extension_v1/results)；[修正后报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/app_resource_constrained_extension_v1/REPORT.md) | F07；24组合、成员、未知交集和分配置正常输出 |
| S08 | [屏幕几何保存汇总](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/screen_geometry_observation_v1/SUMMARY.json)；[专项说明](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/screen_geometry_observation_v1/REPORT.md) | F09；同Web快照与Host测量、72条正式材料和容差边界 |
| S09 | [已有四图清单](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/prepaper_evidence_closeout_v1/figures/FIGURES.json)；[已有表格与成本](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/tree/2a83385d2f6119da90505e3a95518ae23296a9aa/deliverables/prepaper_evidence_closeout_v1/tables) | F06／F08复用，F10分阶段成本；旧图不自动覆盖后续App消融和资源结果 |

## 五、统一制作规则

**数据与图注。** 每图标明方法、记录角色、分母、所用配置、统计范围，以及最重要的一条限制。开发拟合、已接触材料的整批留出、历史正常评价分别命名；不称新盲测。三个配置不产生三倍样本，不以配置间差异冒充统计置信区间。比率从保存计数计算，不生成虚构误差棒、p值、ROC或平滑趋势。

**排版。** 图内使用简短英文，中文说明放审阅页，同时提供可用于论文的英文图注。不在坐标轴堆内部阶段代号。普通单图预留约85 mm、宽图约175—180 mm的阅读尺寸；这是当前工作尺寸，不是某会议格式要求。最终尺寸下正文字号宜不小于8 pt；不适合单栏就保留宽图，不做所有尺寸组合。

**图形。** 每张图独立导出，不做难以阅读的大拼盘。统一方法顺序、图例和单位；颜色以外同时用文字、符号或纹理区分。计数／比例条形轴从0起；热图有固定色标、格内计数，未知不能涂成成功或零。零次报警可标0/N，但不写“总体误报率为零”。

**文件。** 新论文素材建议放`paper/figures/`，第一轮使用`paper/figures/round1_app/`，不覆盖旧deliverables中的图、脚本和数据。每幅交付SVG、PNG和绘图CSV；SVG作为矢量源，PNG按最终尺寸至少300 dpi。暂不要求PDF或投稿模板。不要提交字体文件、复制私有原始指纹或把完整会话标识印在图中。

**可复现性。** 提供单一只读绘图入口、一个FIGURES.json、一个CAPTIONS.md与一个简短README。FIGURES记录ID、状态、源文件摘要、筛选／合并规则、模型角色、输出路径。CSV保留必要原计数、分母和来源键。允许读取已保存的逐条结果进行汇总，但不调用predict、fit、select、采集或计时入口，也不重新计算科学条件。

## 六、执行批次与完成标准

| 批次 | 范围 | 停止点 |
|---|---|---|
| **第一轮：App主体** | F01、F02、F03a、F03b、F04，共5幅独立图；T01、T02、App部分T03 | 数值核对、实际渲染、逐图视觉检查完成；交初版供导师选择，不自动进入第二轮 |
| 第二轮：双端及资源 | F05、F06、F07；F08按提纲取舍 | 明确App与Browser各方向、正常反例和资源未接入结果，不能只有最好一组 |
| 第三轮：提纲适配 | F00；F09／F10／F11按需要取舍 | 根据导师提纲安排正文／附录、统一图号与尺寸，不新开实验 |

第一轮应核对的已有参照数：App六方法依次105、108、96、96、105、72/126，正常均0/252；Full的261条MTC评价报警2/2/0，未知各14；去MTC报警预算各261条全报警；去内存关系未知各1。其余明细从保存文件取，不从本文反推。

数据验证必须防止同时累加`ALL`行和细分行。每个图元能定位到源行或明确的源筛选；图中数值、导出CSV和图注互相一致。制图只能改善表达，不能改善实验成绩。若发现真实来源冲突，保留文件并记录具体冲突，不改值凑参照。

**当前状态记录：**F01/F02/F03a/F03b/F04＝待执行；F06/F08＝已有历史图源、待本阶段复用；其余＝后续候选。完成一轮后在此处更新实际产物与检查链接，保留其余状态，不把“清单已编写”写成“图已完成”。
