# RBA / HybridGuard 研究阶段汇报

> **当前总状态：2026-10-06，App177主体实验已补齐，完整跨端证据仍有缺口。**
> App单端（Native／WebView Host／App Web）、App内部跨层和App↔独立Browser跨端分别评价；App177是研究主体，不能用Browser局部实验替代，也不降为只放附录的历史背景。

| 主线／任务 | 当前实际状态与证据 |
|---|---|
| Browser语言／时区局部扩展、四视图与消融 | **已完成并保留**；[B2-C](deliverables/cross_endpoint_constrained_extension_v1/REPORT.md)、[B3-A](deliverables/cross_endpoint_four_view_comparison_v1/REPORT.md)、[B3-B](deliverables/prepaper_evidence_closeout_v1/REPORT.md) |
| App Full统一回放 | **完成**；核心1,449位置／3,591模型输出，原主实验/MTC逐ID一致；60双端位置的180个App输出另计。[回放核对](deliverables/app177_core_ablation_v1/results/FULL_REPLAY.json) |
| App四项公平消融 | **完成24次规则拟合**，原三折编码器直接复用；每组新SPARSE→本组RETENTION。[主体报告](deliverables/app177_core_ablation_v1/REPORT.md) |
| App范围普通分类器 | **三折小树完成**；真实树fit为3次交付＋1次导出自检失败的工程尝试，单独登记；0编码器重拟合。[执行记录](deliverables/app177_core_ablation_v1/results/EXECUTION.json) |
| App参与跨端检测 | 已有语言/时区60条真实配对完成App-only补充回放；原14配置和专项缺同阶段Browser配对，其他范围的双端方法贡献与完整消融**仍待补证**。[覆盖清单](deliverables/app177_core_ablation_v1/PAIRED_COVERAGE.md) |
| 全项目实验完成／W1完整初稿 | **尚未满足，W1暂缓**；已有草稿保留。此前“开始写作”仅是Browser局部收尾判断，不代表完整研究结束。本轮0采集、0 Browser重训。 |

App主实验攻击检出：Full **105/126**；去MTC报警预算 **108/126**；Web-only **96/126**；去内存关系 **96/126**；去时区关系 **105/126**；小树 **72/126**，各方案旧受控正常均0/252报警。去MTC预算的三个模型均使全部891条MTC正常记录报警；去时区关系使6次正常系统换时区报警；去内存关系漏掉专项18次有效变化。Full仍有屏幕正常布局误报和MTC未知输出，完整分母、逐折状态与反例均在主体报告，不只展示收益。

**当前下一步仅建议一个最小资源配对补证批次**：原resource-pair＋memory_4GiB，补真实两端pre/change/post及匹配正常对照，再冻结适用的跨端方法比较；不重采全部378条。该方案未授权采集，亦不自动补齐其他配置的跨端主张。

## 历史阶段记录（原数字与当时调度保留；当前状态以上表为准）

> 面向导师的阶段材料；数据截至 **2026年10月3日**，同日修订研究范围与后续安排。  
> 已完成实验的事实基线：[`afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7`](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/commit/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7)。  
> **当前数字属于App侧阶段成果，不是完整paired244方法的最终结果。**本文不包含新增训练、采集或统一回放结果。后续安排见 [论文前实验与图表规划](RBA_PRE_PAPER_EXPERIMENT_PLAN.md)。
>
> **Browser先导接入更新：2026年10月6日。**语言/时区两配置已完成主仓B1接入：18阶段、6个三阶段组，重建18条paired244、0 App-only、0 quarantine；逐成员244项值、状态和来源索引与交付一致。原App侧成绩与上述历史基线日期保持不变。详见[本地接入验收报告](deliverables/browser67_pilot_intake_v1/REPORT.md)。

## 一、阶段结论

完整研究目标仍是 **App177与独立Browser67组成的paired244跨端检测**：利用同一实验阶段的两端信息，区分正常设备／容器差异与指纹报告被操纵。当前已完成的主要开发集中在App177，尚不能据此宣称独立Browser67的价值已经得到完整验证。[R8][R9][R12][R13]

当前App侧阶段模型为 **B_REL_TZ**，保存了三个环境留出折的模型。在已有App侧受控主实验中，共检出 **105/126次干预（83.33%）**，配对正常对照报警 **0/252**。在本阶段未用于模型拟合的 **261条MTC评价记录**上，三个模型分别报警 **2、2、0条**，每个模型均有 **14条证据不足**，明确输出覆盖为 **247/261（94.64%）**。这些是App侧模型的成绩，不能标成完整paired244模型的成绩。[R2][R4][R13]

内存、时区、屏幕三个方向已经有针对性对照：内存展示额外识别能力，时区和屏幕展示对正常设置或布局变化的更好容忍。**内存和时区关系已经进入App侧阶段模型；屏幕新关系只完成局部验证和采集工程收尾，尚未进入该模型。**不能把各专项的最好结果拼成一个完整增强系统的成绩。[R3—R7]

**协作状态（2026-10-06接入验收更新）：**Browser语言/时区两配置先导已完成主仓接入；跨端关系开发与正式评价尚未完成，最终消融仍暂停。所验收材料来自1个API36模拟器的独立Chrome，18阶段＝6个干预位置＋12个前后对照位置；不能写成18种攻击、18台设备或全部Browser工具已完成。保留App侧成果，继续**暂停最终消融、最终模型定稿和最终图表冻结**，待跨端方法与评价范围明确后重新安排。

## 二、研究对象与主线

### 2.1 要解决的问题

研究关注：在Android设备指纹上报中，如何区分“正常设备、地区设置、页面布局或运行容器不同”与“指纹报告被操纵”，并给出可追查的风险提示。

本阶段不是以识别同一物理设备为主要评价目标，也不把报警直接等同于恶意意图、未经授权或真实硬件身份已经得到证明。[R8]

### 2.2 区分App内部跨层与App／Browser跨端

| 数据／范围 | 实际含义 | 当前进展 |
|---|---|---|
| App177 | 系统原生信息Native、Android WebView宿主Host、WebView内网页App Web三类观测 | 已完成多轮关系开发、正常真机约束和受控验证 |
| Browser67 | 独立浏览器页面的67项指纹；不是App WebView内的那67项 | MTC已有正常配对数据；语言/时区两配置先导已验收接入，跨端关系与正式评价待完成 |
| paired244 | 同一实验阶段中，经来源信息关联的App177与独立Browser67 | 完整攻击范围、跨端关系和联合检测评价尚待补齐 |

已有App关系输入代码明确只传入App内部三个观测面，不把独立Browser观测送入特征映射。因此，**App内部跨层关系有效，不等于App与独立Browser之间的跨端关系已经有效。**MTC中已经存在Browser67，和当前模型实际使用Browser67，是两件不同的事。[R1][R12][R13]

### 2.3 方法主线与待验证问题

**字段语义与采集实现核对 → 正常paired244与两端受控干预帮助构造和选择关系 → 当前阶段的配对会话独立判定 → 同时报出检出、正常报警、证据不足与失败。**

规则是否入选取决于数据中的判别表现，而不是事先固定报警白名单。训练和评价可以使用正常—干预—恢复的三阶段关联；实际预测只读取当前会话或当前阶段已配对的两端证据，不要求事先知道正常参考值，也不读取未来恢复结果。[R8][R12]

Browser侧数据接入后，需要分别研究：App侧受影响而Browser未观察到变化、Browser侧受影响而App未观察到变化，以及已有工具造成的两端共同变化。未变化的一端也可能提供参照；但同名字段不同不自动构成攻击，两端一起协调变化也可能保持关系相容。以上是待验证问题，不是已完成结论。[R12]

目标不是强迫全部244个字段参与最终模型，而是验证Browser67中有价值的信息和App↔Browser关系带来了什么。

### 2.4 已完成App侧研究的重要转折

最初，模型在受控环境中做到100%检出，但其中的内存、DPR等绝对阈值会在正常真机上大量触发。加入MTC正常约束后，这些条件被排除；随后引入关系检查，让判定从“值是否偏大”逐步转向“当前设备或宿主提供的信息是否相容”。[R2—R4]

因此，阶段价值不只是提高受控检出率，而是说明：**高检出需要与正常设备适应性一起评价；跨层参照在部分问题中能够增加信息，在另一些问题中能够减少正常变化导致的误报。**这些成果将作为完整paired244研究的App侧基线与可复用模块保留，不需要因Browser开发而全部重做。

## 三、现有数据基础

| 材料 | 规模与用途 | 统计边界 |
|---|---|---|
| MTC真机数据 | 1,028条合格配对记录，覆盖891种型号／系统组合；主分析选取891条代表记录，按630条训练约束、144条评价、117条评价使用 | 已包含独立Browser正常观测；当前阶段模型只使用其App侧输入。不是891台已经独立核验的物理手机，也不是按用户市场份额抽样 |
| App侧受控主实验 | 3个模拟器环境 × 14个配置 × 3轮 × 正常／干预／恢复，共378条；其中126条干预、252条正常对照 | 当前主表针对App侧输入；126条不是126种攻击，14个配置也不等于14种独立机制 |
| 内存专项 | 72条；24次修改尝试中18次有可观测变化，6次设置后数值未变；48条正常对照 | App侧固定模型和条件的局部对照；不与旧126条合成一个总检出率 |
| 时区专项 | 36条；6次正常系统时区变化、6次仅App Web修改；共30条确认正常位置 | 正常设置变化与目标干预分别标注 |
| 屏幕专项v15 | 72条；6次有效干预、66条确认正常；旋转实际生效4/6，布局变化和缩放分别生效6/6 | 比较App内独立条件，尚未评价整合后的完整模型 |
| 屏幕v16工程检查 | 12个位置，含一个预定故障和两个默认启动检查受限位置 | 工程材料单列，不增加研究样本量，不更新模型分数 |
| Browser67语言/时区先导 | 1个API36模拟器，独立Chrome/133.0.6943.137；2配置×3轮×3阶段＝18条paired244 | App v16、Browser probe v2；6次目标效果及恢复通过，不是检测率；不加入旧App成绩分母，正式分组为空 |

已保存App材料来源：[R1][R2][R4—R7][R13]。Browser先导来源为[本地主仓接入验收](deliverables/browser67_pilot_intake_v1/REPORT.md)：冻结核验18/18、自测试8/8通过，证据保持原样；候选事实仍为candidate、run_profile、run_scoped_unverified，原协议生成train/development/test 0/0/0及structural_ready=false。MTC中的历史“保留集”此前已经被使用，本文继续采用分组开发评价口径，不将它重新称为未接触的独立盲测。正常真机样本用于检查所测条件下的表现，不自动覆盖所有第三方App业务行为。

## 四、App侧研究结果总表

### 4.1 开发演进

下表用于说明App侧研究如何改进，**不是完整paired244最终结果，也不是严格消融表**：不同阶段还改变了候选或可用观测范围。MTC评价列统一使用144＋117＝261条记录，不混入630条训练约束数据。

| 阶段／模型 | 攻击检出／126 | 配对正常报警／252 | MTC评价报警／261：折1；折2；折3 | MTC证据不足／261：折1；折2；折3 |
|---|---:|---:|---|---|
| 原CAP8：受控满检出 | 126（100%） | 0 | 247；247；247 | 14；14；14 |
| A：加入MTC约束，保留全部候选 | 114（90.48%） | 0 | 3；3；1 | 258；258；260 |
| B：兼容旧MTC观测 | 96（76.19%） | 0 | 3；3；1 | 1；1；1 |
| B_REL：加入内存关系 | 105（83.33%） | 0 | 3；3；1 | 14；14；14 |
| **B_REL_TZ：加入时区关系，当前App侧阶段模型** | **105（83.33%）** | **0** | **2；2；0** | **14；14；14** |

来源：[R2—R4]。受控378条在这些阶段均有明确输出。攻击126条来自三个不重叠的留出集合，可以汇总；每个模型分别评价同一批MTC记录，三个模型输出不能相加成三倍独立样本。

**结果解释：**A虽然少报警，但主要是大量记录无法判断，不能据此认为完整模型已经低误报可用。B在保持正常明确判断的同时压低报警，才显示正常真机约束的实质作用。内存关系恢复9条资源攻击检出，但增加旧数据上的未知；时区关系继续减少正常报警，没有新增未知或丢失攻击检出。[R2—R4]

### 4.2 App侧阶段模型的正常侧完整状态

| MTC子集 | 报警数：折1；折2；折3 | 明确不报警数：折1；折2；折3 | 每个模型的证据不足 | 每个模型的失败 |
|---|---|---|---:|---:|
| development，144条 | 1；1；0 | 135；135；136 | 8 | 0 |
| reserved_validation，117条 | 1；1；0 | 110；110；111 | 6 | 0 |
| **合计，261条** | **2；2；0** | **245；245；247** | **14** | **0** |

来源：[R4]。三个模型的观察报警比例分别为0.77%、0.77%、0%；明确输出覆盖均为94.64%。**0次观察报警不等于总体误报率为零，证据不足也不等于正确识别正常。**

### 4.3 App侧已知剩余问题

| 问题 | 保存结果 | 当前原因与边界 |
|---|---:|---|
| 屏幕单项 | 检出6/9，漏3条 | App侧阶段模型仍依赖绝对页面高度；新宿主几何条件尚未整合 |
| WebGL单项 | 检出0/9 | 旧MTC缺少新增查询观测，当前历史兼容模型未使用对应能力 |
| webdriver单项 | 检出0/9 | 旧投影缺少新版属性状态信息，当前历史兼容模型未使用对应能力 |
| 其余11个配置 | 各9/9 | 限定为已测试配置和参数，不代表任意变体 |
| MTC评价剩余报警 | 前两折各2/261；第三折0/261 | 前两折仍有绝对高度条件触发正常记录 |
| MTC评价证据不足 | 每折14/261 | 主要来自旧Web内存观测缺失或含糊默认值 |

来源：[R4]。这21条漏检与14条正常侧未知不是同一分母，不能混算。表中的WebGL／webdriver指当前App侧实验，不代表独立Browser67攻击已经得到评价；本次接入的Browser先导也不包含在这21条之中。

## 五、三项App侧专项证据

### 5.1 内存：相同Web数值，需要结合设备自身参照判断

新实验只修改App Web内存报告，不同时修改处理器数量、UA等字段。目标4、8、16分别产生6次有效变化：跨层内存关系检出18/18，单字段“Web内存大于8”检出6/18。48条正常对照均未报警。[R5]

正常MTC设备也可能报告4或8；跨层关系利用各自同次采集的Native参照，允许正常大内存设备，同时发现低内存环境的部分过高上报。原resource-pair新增9条检出本身都可以被“值大于8”解释，真正补强跨层价值的是后续4／8隔离实验，而不是固定改成16的成绩。[R5]

边界：它是宽松的单向上界，不识别所有向下修改或包络内修改；旧MTC中65条Web内存默认0仍保留未知，不补成正常。

### 5.2 时区：正常系统变化与仅网页变化可以区分

6次正常系统换时区，旧模型6次全部误报，新模型0次报警；6次只修改App内网页时区的有效干预，新旧模型均全部检出。新模型在30条确认正常位置上0次报警，并自动替换了旧绝对时区阈值。[R4]

新关系使用Native时区和采集日期计算预期偏移，没有把不含夏令时的标准偏移直接当作当天值。只修改ID但当前偏移不变、两侧一起协调变化，以及设备与固定规则库不一致，仍属于需要明确说明的边界。

### 5.3 屏幕：正常扩大页面区域不应因高度变大而报警

新增模块记录宿主前快照、网页同步读取和宿主后快照。局部比较中，新宿主几何上界与旧高度条件均检出6/6次屏幕干预；66条正常中新条件0次报警，旧高度条件6次报警，三个条件均无未知或失败。[R6]

增益是“保留局部检出，减少正常布局误报”，不是把App侧模型的屏幕检出提升到9/9。关系仅检查上界，当前约2像素的容差不是所有WebView的官方误差保证，且尚无该新增观测的正常真机验证。

v16已完成三个环境的安装运行、默认无CDP采集与故障降级检查。两个API29默认启动位置的调试端点关闭检查仍保留平台限制，不能称12个位置所有工程检查都通过；原v15的72条结果离线复核逐条不变。[R7]

## 六、阶段价值与下一步安排

### 6.1 目前能够支持的结论

1. **正常真机约束有实际作用。**受控高检出不能替代正常设备评价；广机型数据能暴露仅适合开发环境的绝对阈值。
2. **App内部跨层参照的价值可以追到具体问题。**内存增加部分识别能力，时区与屏幕减少正常变化导致的误报，而不是仅靠增加字段数量。
3. **缺失与失败需要单独处理。**不把无法评价的输入补成正常，才能同时解释低报警和实际判断覆盖。

这些结论支持App侧阶段成果，尚不证明Browser67的独立贡献或完整paired244方法的最终效果。[R2—R7][R13]

### 6.2 为什么暂缓最终消融

Browser67攻击材料补齐后，候选关系、攻击作用域、最终模型和对照范围都可能变化。现在直接以B_REL_TZ定稿并完成最终消融，等于提前把研究缩成App侧；之后还可能重复训练和作图。因此，本次调整为：

**保留App侧基线 → 先对齐一两个完整Browser配对样例 → 验收新批次并完善跨端关系与联合检测 → 重新确定最终对照／消融 → 再冻结表图和论文结果。**

E1统一回放可以作为App侧阶段整理，完成后不自动进入最终消融。B1已核验本次先导的两端阶段配对、浏览器版本、控制生效窗口和恢复。下一轮可明确授权范围后开展App冻结基线回放及少量先导跨端关系诊断；本批不自动并入旧E1分母，也不获得正式泛化评价资格。本次B1为0训练、0新增采集、0检测器评分，未执行E1、B2或E2。[R12]

最终对照将优先比较App177-only、Browser67-only、两端合用但无显式跨端关系、加入显式跨端关系四种方法；具体设置与组件消融待新材料和方法稳定后确定。不预设全部67项必须入选，不无限等待全部工具穷举。

### 6.3 论文表述边界

当前不宣称：完整paired244增强系统100%检出且真机零误报、三层或双端必然优于所有单端方法、覆盖所有工具及参数、Native／Host是不可操纵的硬件根信任，或者本研究已经实现列生成与全局最优性保证。[R8][R9]

工作题目可暂用：**《基于App与独立浏览器跨端一致性及正常设备约束的Android指纹操纵检测：一项探索性研究》**。这是目标定位，不是已完成成果的升级；最终题目与主张应由Browser接入后的证据决定。已有App侧结果可保留为论文阶段基线、专项案例和方法开发依据。

## 七、仓库证据索引

以下链接全部固定到已完成实验事实基线`afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7`，避免后续变化影响复核。文中[R编号]对应下表；连续编号表示多项证据。**“Browser攻击采集仍在进行”来自本轮项目负责人说明，不将旧协议或旧代码冒充新批次完成证据。**

| 编号 | 证据入口 | 可以核对的内容 |
|---|---|---|
| R1 | [MTC数据范围与字段质量](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/mtc_p1_20260922/P1_REPORT.md) | 1,028条配对、891组合、App-only及部分数据的去向、采集版本和缺失语义 |
| R2 | [MTC约束下的规则重选](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/mtc_constrained_reselection_v1/REPORT.md) | CAP8、A、B同成员结果，630／144／117划分，双正常预算和覆盖要求 |
| R3 | [内存与屏幕关系扩展](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/mtc_relation_extension_v1/REPORT.md) | B_REL的105/126，资源新增9条、未知增加，以及无收益的同Web视口关系 |
| R4 | [时区关系与App侧阶段模型报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/timezone_relation_validation_v1/REPORT.md) | B_REL_TZ主表、逐配置、MTC状态、规则替换和36条时区专项 |
| R5 | [内存单字段对照与取值变化](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/memory_relation_validation_v1/REPORT.md) | 18次有效变化、R_REL与R_WEB8、48条正常及6次无可观测变化 |
| R6 | [屏幕同期观测报告](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/screen_geometry_observation_v1/REPORT.md)；[详细结果](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/screen_geometry_observation_v1/RESULTS.md)；[关系语义](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/screen_geometry_observation_v1/SEMANTICS.md) | v15的72条、6/6和0/66、实际旋转4/6、宿主原值与容差边界 |
| R7 | [屏幕v16工程收尾](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/screen_geometry_closeout_v1/REPORT.md)；[v15一致性复核](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/screen_geometry_closeout_v1/V15_CONSISTENCY.json) | 12个工程位置、降级、两条平台限制、旧72条逐条不变 |
| R8 | [既有研究主线](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/RESEARCH_MAINLINE.md) | 当前会话推理、数据驱动报警资格、三值逻辑、研究贡献边界；调度说明是历史状态 |
| R9 | [V2路线图](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/V2_DEVELOPMENT_ROADMAP.md) | 表示与学习分开比较、跨层优势需验证；旧阶段分数不当成本阶段成绩 |
| R10 | [App侧模型清单](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/timezone_relation_validation_v1/models.json)；[冻结身份](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/timezone_relation_validation_v1/MODELS_FROZEN.json) | 三个RETENTION模型的身份、规则、路径及固定依赖；SPARSE阶段不能混选 |
| R11 | [App侧模型逐条输出](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/timezone_relation_validation_v1/predictions.jsonl.gz)；[验证记录](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/deliverables/timezone_relation_validation_v1/VALIDATION.json) | 可下载的逐条结果、同成员与OR核验；压缩文件需下载后读取 |
| R12 | [攻击侧采集与paired244交付协议](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/ATTACK_SIDE_COLLECTION_SYNC_NOTE.md) | 每阶段App／Browser尝试、作用域、配对身份与失败保留；所列APK和探针版本为历史示例，新批次须重新对齐，不代表当前采集已完成 |
| R13 | [当前关系输入范围](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/afaa8bd88ac59b3deffeb83789e9ce6fc47a52f7/hybridguard_agent/research/mtc_relation_sources.py) | 只传入App内部Native／Host／App Web，独立Browser未进入当前特征映射，说明阶段模型的范围 |

核对路径：先看R4阶段主结果，再用R10确认模型身份、R11检查逐条输出；贡献解释查R5、R6及R4专项；完整paired244目标与当前输入缺口分别查R12、R13。各目录原始引用和操作回执继续保留，不能以本文汇总替代原始材料。


## B2-C 实际结果补记（2026-10-06）

已完成一次有限跨端增量选择：保持三个B_REL_TZ RETENTION App阶段模型与编码器不变，各比较空集、C1、C2、C1+C2，结果均选择C1。每个新开发模型在14次有效开发干预中由2次检出增至7次，新增5次Browser时区检出；46条小实验正常记录无新增报警。C2因两条真实正常Browser偏好触发而超过B2-B独立正常预算，未选入。

代价是每模型MTC discovery新增12条F转U，明确覆盖从579/630降至567/630，恰为90%；历史development新增3条F转U，reserved_validation无新增未知，各组报警不增加。690个开发位置与261个历史评价位置分别报告，951位置已实际逐配对回放。三个配置不构成新数据三折交叉验证，两批小实验已经用于学习，原来源标签和正式准入不变。

证据入口：[B2-C报告](deliverables/cross_endpoint_constrained_extension_v1/REPORT.md)、[模型与运行入口](deliverables/cross_endpoint_constrained_extension_v1/README.md)、[12集合结果](deliverables/cross_endpoint_constrained_extension_v1/results/candidate_checks.csv)、[逐组结果](deliverables/cross_endpoint_constrained_extension_v1/results/summary/summary.csv)、[实际当前输入回放](deliverables/cross_endpoint_constrained_extension_v1/results/REPLAY_VERIFICATION.json)。完整paired244整体方法对照与最终消融尚未完成；没有训练Browser-only或平铺双端无关系模型，不能宣称跨端整体优于任意单端。原App阶段105/126等旧数字与各批历史身份保持原义。


## B3-A 四视图实际开发比较补记（2026-10-06）

已完成 P0/P1/P2 各四个固定小决策树，共12个预定模型，使用现有951个配对位置，无新增采集。App侧语言/时区、Browser侧、双端拼接、双端加原版C1/C2使用相同学习器、深度及权重规则；最后两组共享同一训练部分预处理，仅增加关系列。字段范围有限，不代表全部App177/Browser67的性能上限。

P0开发：双端拼接与加关系均检出14/14有效干预，正常小实验报警分别为32/46与0/46。P1整批留出旧先导：两种双端均检出6/6，正常报警由12/12降为0/12，但加关系模型在训练匹配正常仍报警2/34，超过预算1。P2整批留出42条匹配对照：两种双端结果完全相同，检出4/8、正常报警6/34，未选用C1/C2；其中训练未见App侧干预，评价App侧0/4，Browser侧4/4。全部未达标与无收益结果保留。

两批小实验此前均已接触，P1/P2是整批留出的开发比较，不能称前瞻盲测或真机泛化。固定fr-FR、列表长度和-540/-480等配方对分裂有影响；有些单端正常/干预输入完全相同，高检出同时伴随高正常报警，不能解释为识别操纵意图。树的二值输出虽为951/951，但双端完整输入仅918/951，每模型33条判定使用部分缺测输入，不能称观测覆盖提高。

27项测试通过，保存模型当前输入复现11,412/11,412一致；独立核对训练限定变换与权重，仅重汇总复现8份文件。实际树fit共17次：12次完成比较、1次首次工程导出失败前的拟合、4次合成测试拟合，均有账本；没有重训旧App或B2-C。三个旧配置、App105/126与378条继续独立保留，不混入本轮14次有效干预分母，正式准入权限未变。

证据入口：[B3-A中文报告](deliverables/cross_endpoint_four_view_comparison_v1/REPORT.md)、[代码及复现命令](deliverables/cross_endpoint_four_view_comparison_v1/README.md)、[主比较CSV](deliverables/cross_endpoint_four_view_comparison_v1/results/main_comparison.csv)、[逐来源完整状态](deliverables/cross_endpoint_four_view_comparison_v1/results/summary/summary.csv)、[调用与保护检查](deliverables/cross_endpoint_four_view_comparison_v1/VALIDATION.json)。本节补充此前“尚无单端/双端对照”的进展，不改写此前阶段记录；当前新增证据限于固定语言/时区任务。

现有证据支持“显式关系在部分开发配置中减少正常报警”，同时保留P2无增益和未见App端失败；不宣称完整paired244最终方法必然优于单端。下一步仅建议精简最终消融、成本及图表，未自动执行。


## B3-B 最小消融、成本与论文表图收尾（2026-10-06）

本轮已完成主方法的两个最小消融、一次离线成本统计及统一候选表图。保持原B2-C三个App+C1、三个基础App、C1/C2、B3-A十二棵树与预处理不变，复用同一951位置（690开发、261历史正常评价）。App历史开发/专项、B2-C有限增量规则方法、B3-A语言/时区四视图仍是三个独立研究层次，保留原105/126、378条等历史分母，不拼接最好成绩。

R_FULL复用原App+C1，每配置检出7/14；R_NO_CROSS复用原可行S0，每配置2/14。仅去掉匹配正常组报警上限（预算1→34，含义是消融中不以该组报警淘汰集合，不是部署容忍度提高）后，三次原有限选择均选择C2，每配置9/14。实际交换为新增7次语言检出、失去5次Browser时区检出，并新增2/34匹配正常报警；两条正常浏览器偏好没有删除、改标或置U。MTC预算31、先导预算0、90%覆盖、8规则/16复杂度、宏平均与固定排序不变；C1+C2仍因566/630明确输出低于567/630而被拒绝。新增模型标记ABLATION_ONLY，不替代主方法。MTC的T/F/U/FAILED、历史144/117新增1个报警和逐成员变化分别保存。

B3-A保留全部原结果：P0双端与REL均14/14、正常32/46与0/46；P1留出先导均6/6、正常12/12与0/12，但REL训练匹配仍报警2/34；P2均4/8、正常6/34，REL无增益。P0 REL依赖Browser语言列表长度≤2.5；双端33/951部分缺测没有被二值输出修复。P1/P2不是未接触盲测，四视图不等于主规则方法的全部消融。

离线成本固定21模型、相同60条开发配对，一次预热与10遍，保存1,480个批次；区分加载、已加载raw适配、关系/输入准备、准备后判断、原公开接口及缓存包装。1,260项四路径等价检查全部通过。P95是批次均摊分布，不是单请求尾延迟；既有采集日志的同host墙钟区间与15秒人为等待单列，纯探针与未记录的纯训练时长不补造。两次计时前工程失败及额外测试调用保留，没有追加计时追求最好值。

15项针对性测试通过；仅保存材料重汇总/制图复现30份文件字节一致，生成4幅SVG/PNG/CSV图、348行机器指标索引和10项主张证据索引。正式新选择仅3任务/12检查，测试额外6选择/22检查单列；App、编码器、树新fit与新增采集均0。旧模型和证据保持冻结，保护已有工作区改动，本轮未自动提交推送。

证据入口：[B3-B中文报告](deliverables/prepaper_evidence_closeout_v1/REPORT.md)、[三设置逐条输出](deliverables/prepaper_evidence_closeout_v1/results/predictions.jsonl)、[统一指标索引](deliverables/prepaper_evidence_closeout_v1/tables/metric_index.jsonl)、[成本表](deliverables/prepaper_evidence_closeout_v1/tables/cost.csv)、[候选图清单](deliverables/prepaper_evidence_closeout_v1/figures/FIGURES.json)、[主张与证据](deliverables/prepaper_evidence_closeout_v1/CLAIM_EVIDENCE.md)、[复现命令](deliverables/prepaper_evidence_closeout_v1/README.md)、[最终复核](deliverables/prepaper_evidence_closeout_v1/VALIDATION.json)。

本补记更新此前“精简消融、成本与表图尚未执行”的状态，不改写历史阶段。现在可以进入方法和评价正文写作，明确范围为 **paired244语言/时区双向干预的探索性证据，配合App侧历史专项**。广泛Browser攻击工具/参数覆盖、独立新设备泛化、配方与环境混杂、历史缺测及纯探针计时缺口仍限制论文主张；它们不自动转化为下一轮开发。本轮完成后停止实验，不追加采集、分类器、预算、容差或关系试验。
