# HybridGuard：面向计算机领域读者的研究与方法总览

2026-10-10，在 `f80ec0a7a8b3922342fca75f13c9638271381de5` 研究与方法总览上作局部排版。核心文案、事实边界、三角、图标、浅色配色与正文大小均保留；本轮重排离线输入与底部检测区，并为连线和评价条带增加空间。

## 交付与阅读顺序

- [最终 SVG](HybridGuard_overview_triangle.svg)：180 × 125 mm，文字可编辑。
- [最终 PNG](HybridGuard_overview_triangle.png)：3600 × 2500 px。
- [文案清单](COPY.md)：每个区域回答的问题、最终英文及连线含义。
- [生成脚本](build_overview.py)、[渲染脚本](render_preview.cjs)：只使用固定文案与坐标，不导入研究模块。
- [同宽前后对比](previews/before_after.png)：上方为本轮编辑前的f80ec0a（180 × 106 mm），下方为最终稿（180 × 125 mm）；两幅同为1800 px显示宽度，保持各自纵横比。
- [下半部同尺度局部对比](previews/lower_before_after.png)：两幅均从y=680截取，均为每viewBox单位1 px，没有分别缩放来凑齐高度。
- [180 mm图宽预览](previews/actual_size.png)：按96 px/in换算为680 × 472 px，实际物理显示大小仍取决于查看器缩放。
- [节点实际尺寸](previews/icons_actual_size.png)、[图标细节](previews/icons_enlarged.png)：从最终图直接提取，未另画图标。
- [现有 ACM 模板预览](../../../output/pdf/hybridguard_triangle_template_preview/PREVIEW_NOTES.md)：同步矢量图、英文图注、编译 PDF 与图所在页预览。

正文28–29个 viewBox 单位，在180 mm图宽下约7.94–8.22 pt；主标题40、节点标题32–34。保留衬线字体与白色画布。角色名优先，论文术语 Native、WebView Host、App Web 作为次级名称。

## 正式英文图注

HybridGuard checks device-fingerprint reports for possible manipulation using complementary observations from the same device. Within-view and cross-view checks are evaluated on controlled modifications and normal operation to select compact detection rules under false-alarm and decision-coverage constraints. The selected detectors process current App observations alone or linked App–browser observations and return a manipulation alert, no alert, or insufficient evidence. The inset illustrates why changing a system setting need not have the same cross-view effect as modifying only a webpage’s report. Solid comparison edges indicate relations used in the detectors; Host–web geometry remains a separate study, and the dotted Native–Host link denotes context only. No observation point is trusted ground truth. No alert does not establish safety. Execution failures are recorded separately.

## 正式中文图注

HybridGuard 利用同一设备上的互补观测，检查设备指纹报告是否存在可能的操纵。视图内与跨视图检查在受控修改和正常运行数据上接受评估，以在误报与明确判定覆盖率约束下选出紧凑的检测规则。选出的检测器处理当前 App 观测，或已关联的 App–浏览器观测，并返回操纵报警、未报警或证据不足。插图说明，改变系统设置与仅修改网页报告，不一定产生相同的跨视图影响。实线比较边表示检测器采用的关系；Host–网页几何关系仍属单独研究，Native–Host 点线仅表示上下文。任何观察位置都不是可信真值。未报警不代表安全。执行失败单独记录。

## 线与边界的读法

| 类型 | 图中表达 | 含义 |
|---|---|---|
| 同设备范围 | 外层浅灰实线框 | App 与独立 Browser 均在同一物理设备上；Offline 与例子在框外。 |
| App 范围 | 内层灰色虚线框 | Native、Host、App Web 的三角；Browser 在 App 外。 |
| 已选比较关系 | 蓝色实线、两端开放箭头 | Native–App Web 内存与时区；App Web–Browser 时区。标识比较双方，不是双向预测、数据循环或认证。 |
| 已研究未集成 | 赭色虚线、两端开放箭头 | Host–App Web 几何；文字明确 Not in current detector。 |
| 仅上下文 | 灰色点线、无箭头 | Native–Host：No detection rule。 |
| 离线内部流 | 黑色单向线 | 独立 Candidate checks 与 Development data 进入选择，再输出规则。 |
| 固定模型输入 | 紫色单向线，Selected rules 标签 | 已选规则从右上独立端口加载到共同规则应用框，落点与右侧结果列表分离；两种模式使用各自规则集。 |
| 当前数据输入 | 黑色单向线 | App-only 从上方卡片左端进入；已关联 App–Browser 数据从下方卡片右端进入。二者不经过 Offline。 |

底部共同规则应用框内，两种模式上下排列，并以 `or` 明确替代关系，各自规则说明保留。只有一条从共同框引向右侧结果列表的箭头，表示所选模式的结果；没有逐模式结果线、结果汇合点、融合或投票。唯一的当前数据汇合点用于 App 与 Browser 关联，不是检测结果融合。两种模式没有顺序、回退或相互调用关系。评价条带与机制例子均无流入检测器、流入选择器或反馈训练的箭头。

## 事实边界与实现对应

### 1. 检测对象、参照与字段目录

这里的 fingerprint manipulation 是设备指纹报告操纵，不是生物指纹识别或用户身份认证。多位置参照有助于发现部分局部修改、避免部分正常设置变化误报；不是所有修改都必然产生矛盾。观察位置并非可信真值，测量语义允许的相容关系不要求全部字段相等。未观察到矛盾也不能排除操纵。总体叙述依据[导师报告](../../../RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md)的结论、观察定义、时区专项和方法边界。

[字段目录](../../../android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv)中三类观测为 Native84、Host26、App Web67，合计 App177；另加 Browser67 构成 [paired244 目录视图](../../../hybridguard_agent/evidence/paired244.py)。这些数字是目录字段数，不是样本数、独立设备数、每条记录完整性或入模规则数。CSV 还含采集器、版本、会话和时间元数据行，它们不计入上述177。目录数移出主图，用观察位置及实际内容说明替代。

### 2. 三角中哪些关系真正入模

[App 消融报告](../../../deliverables/app177_core_ablation_v1/REPORT.md)及[候选依赖](../../../deliverables/app177_core_ablation_v1/CANDIDATE_DEPENDENCIES.md)给出50个 App Web 基础模板与3个固定关系模板：同 Web 视口、Native–Web 内存、Native–Web 时区。当前固定 App 同时含视图内规则和跨视图规则，不能把全部模型效果归因于图中的跨视图边。

本轮只读核对了三个保存的 B_REL_TZ RETENTION 模型：[01](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-01__RETENTION/model.json)、[02](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-02__RETENTION/model.json)、[03](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-03__RETENTION/model.json)。三者均含 `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE`、`MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS` 的正向子句，也含 App Web 视图内子句。图中“Memory and timezone”概括这两类关系，不表示简单的全部数值相等。

具体操作数也各有语义：[内存关系](../../../hybridguard_agent/research/mtc_resource_relations.py)比较 Native 的 `app.android_native_data.memory_layer.total_memory_gb` 与 Web 的 `app.web_data.navigator_layer.device_memory`；采用 Native 内存向上取二次幂的宽松包络，允许较低 Web 暴露，不要求两值相等。[Native–Web 时区关系](../../../hybridguard_agent/research/mtc_timezone_relation.py)使用 Native `locale_timezone_layer.native_timezone_id`、`native_timezone_offset_min` 及 Web `execution_layer.timezone_offset`；原同次采集起止时间只用于解释固定2026c时区规则，不是独立预测特征，也不是修改前/后记录。Native 标准时偏移不能直接充当含夏令时的当前偏移，Web 时区名称仅作诊断。

Host–App Web 几何是[单独研究](../../../deliverables/screen_geometry_observation_v1/SEMANTICS.md)，依赖新增 `collection_observations.webview_geometry`，具有有限布局适用域和非原子观察窗口。它未进入当前固定检测器，原 Host26 目录不能完整提供这些新增操作数；旧同 Web 视口或旧高度条件也不是这项新 Host 几何研究。当前 App 候选池没有实际 Host 测量候选，Native–Host 仅为共享上下文，不声明对应检测规则或独立收益。三条三角边未形成全部参与当前检测的闭环。

### 3. Browser 比较的具体含义

蓝色 App–browser consistency 实际对应 C1。其[操作数](../../../deliverables/browser67_cross_endpoint_diagnostic_v1/conditions.py)是两端网页报告中的 `app.web_data.execution_layer.timezone_offset` 与 `browser.web_data.execution_layer.timezone_offset`，要求有效的数值 UTC offset，不是 Native 与 Browser 时区名称比较，也不代表所有 Browser 属性均已入模。

[保存的跨端模型](../../../deliverables/cross_endpoint_constrained_extension_v1/results/models.json)中三个冻结配置均选 S1、扩展仅为 C1。会话、回执、版本和来源用于关联当前观测，不是分类特征；关联不保证测量原子同步。Browser 资源扩展没有新增条件准入，本图未将其画入模型。

### 4. 时区小例子不是新实验

两行分别示意各自当前状态：正常系统时区改变后系统与网页仍可相容；只改网页报告则可能与系统观察冲突。两行没有前后时间箭头，不是推理所需的修改前/恢复后记录，也不增加两条开发样本或新的实验结果。

图中的正常情形不构成“所有正常行为永远相容”的保证：测量时刻、适用域、实现差异和可用性仍受既有语义约束。compatible 不直接等价于完整检测器 No alert；conflict 不等价于已确认攻击。示意依据[导师报告](../../../RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md)及[App 消融报告的时区专项](../../../deliverables/app177_core_ablation_v1/REPORT.md)，没有添加数值或检出率。

### 5. 选择程序与数据角色

Offline 是高层概括，四项文字表示目标与约束，不保证零误报、完全覆盖或任意规则空间的全局最优。候选检查是独立输入；没有将整个三角、上下文、未集成几何或机制例子送入当前规则选择。

App 选择与跨端增量选择是不同程序。App 的 [SPARSE 与 RETENTION 调度](../../../hybridguard_agent/research/mtc_timezone_selection.py)先进行稀疏规则选择，再按既有语义进行信号保留/质量替换；RETENTION 不是继续优化同一个稀疏目标。跨端[协议](../../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md)冻结 App、编码器、极性与参数，在 `[]`、`[C1]`、`[C2]`、`[C1,C2]` 四个预定集合中选择；先满足每类正常报警、明确输出覆盖、候选可用性和复杂度约束，再最大化四类干预的宏平均触发率，并按新增规则数与固定集合顺序决胜。有限空间的精确枚举不等于一般规则空间全局最优。

“Development data”只指原协议允许的开发材料，不能包含全部历史数据。App 使用各自受控开发折及 MTC discovery630 正常约束；跨端使用固定的 MTC discovery630、B1先导18、B2-B规范42，不把旧378条并入跨端选择。MTC development144/reserved_validation117 保持历史评价身份，不因名称或这张图改为训练数据或新的独立盲测。内存、时区、屏幕专项在所引用 App 消融报告中属于冻结后评价；本轮不改变其角色。三个模型重复评价不增加独立样本量。

跨端协议三类正常预算为31/0/1，明确输出覆盖要求每类至少90%，总规则≤8、复杂度≤16；这些内部约束留在此处，不占主图。具体 App 折、数据角色与准入仍以原报告和协议为准。

### 6. 当前输入、缺测与执行失败

[App 当前输入入口](../../../hybridguard_agent/research/mtc_timezone_selection.py)和[paired 输入入口](../../../deliverables/cross_endpoint_constrained_extension_v1/inference.py)只使用当前允许的观测、状态、质量和绑定错误，不读实验标签、阶段、训练/测试身份或未来恢复记录。App-only 使用固定 App；paired 使用其对应固定 App 加已选 C1。两者并列，不自动回退。

编码为 T = Manipulation alert，F = No alert，U = Insufficient evidence。T 不是攻击真值，F 不是 Safe。缺测、不可用或关系不适用按条件语义保留 U；有效数值零不能被任意当作缺测。执行/绑定失败单独记录为 FAILED，不是第四种风险等级。

[状态合成](../../../deliverables/cross_endpoint_constrained_extension_v1/selector.py)保持选中输入失败优先：任一选中输入 FAILED 时整模 FAILED；无 FAILED 时，有 T 为 T、全 F 为 F、否则 U。例如 `T OR U = T`、`F OR U = U`、`T OR FAILED = FAILED`。未选条件失败不额外影响模型。缺 Browser 不会自动改走 App-only，也不能用 App 的 F 兜底；关系 U 不意味着最终输出必然 U，应按既有合成规则处理。

### 7. 评价范围与明确排除

Detection、False alarms、Undecidable cases、Ablations 表示保存研究的评价维度，依据导师报告和 App 消融报告；不是每次推理后的生产流程，不连回训练。没有新增性能数字、全新独立盲测、LLM、RAG、知识图谱、自动阻断或在线学习。

给定图内文案与已保存事实没有阻止交付的冲突。两处容易产生过强理解的概括已用本节限定：正常时区例子不是普遍保证；“选择规则”汇总不同开发程序，不改变数据身份或最优性范围。未改写给定短文案的研究含义。

## 生成

在仓库根目录运行：

```sh
python3 -B paper/figures/overview_triangle/build_overview.py
node paper/figures/overview_triangle/render_preview.cjs
```

重建本轮比较时，只读提取基线 PNG：

```sh
git show f80ec0a7a8b3922342fca75f13c9638271381de5:paper/figures/overview_triangle/HybridGuard_overview_triangle.png > /tmp/HybridGuard_triangle_f80ec0a.png
node paper/figures/overview_triangle/render_preview.cjs --before /tmp/HybridGuard_triangle_f80ec0a.png
```

Node 需可用的 Sharp；依赖目录可用 `RBA_NODE_MODULES` 指定。本轮使用编辑前保存的当前 PNG 作为比较输入。SVG、PNG、节点预览和同宽比较来自同一生成结果。LaTeX 同步方法见预览说明。

## 局部排版修改与本轮验收

- 画布从180 × 106 mm增为 **180 × 125 mm**，viewBox从1800 × 1060同步变为1800 × 1250；宽度、字号、图标比例不变，没有纵向拉伸。正文仍为28–29单位。
- 同设备框与 App 框、三角节点、三角关系标签及连线、独立 Browser 及其蓝色比较线保持原坐标和大小。三角浅蓝底色按三条关系线延长线的交点构造，使填充边界贴合两条斜边及y=610底边，消除原有白缝；填充色仍为#f8fafb。时区例子仅收紧下部空隙及两行位置：框高281→251，文字行距保持35单位以上。
- Offline框从y=423、高439，调整为y=397、高461，底部对齐观测区y=858；宽度仍为562。Candidate checks与Development data使用相同x=1236、宽480及24单位文字左内边距。说明行距35，Controlled modifications与Normal devices and settings均完整成行。候选输入沿右侧28单位通道绕过开发数据条目，两者独立进入选择。
- 四项选择目标在浅紫底上排成两行两列，左列x=1240、右列x=1540，行距36；去掉限制列宽的内层白底框。Selected rules只出现一次，作为输出与模型加载线的起点。
- 上区底部y=858与检测框y=908之间留出 **50单位连接通道**。数据关联横线和规则加载横线使用各自水平范围，无交叉；当前数据不经过Offline。
- 检测框由高148增至 **270单位**，范围x=24、y=908、宽1140。两张模式卡均x=210、宽750、高80，文字左内边距24，规则说明行距34；卡片间留40单位并写or。App-only数据从左端进入上卡；关联数据从右端进入下卡。紫色模型线通过右上端口进入规则应用标题区域，与黑色数据端口分开。
- 删除沿底边绕行的App-only结果线及结果汇合点。共同检测框仅通过一条水平输出箭头连接右侧共享结果；输出列表x=1340，三行基线1030/1068/1106，行距38，整体按检测内容区垂直居中。
- 评价条带基线移至1224。实际文字边界距检测框下缘约21单位、距画布底边约20单位；它没有流程箭头。Native、Host、App Web、Browser、Offline的底色和三处红字保持不变。

本轮实际检查（仅对应本轮重新生成文件）：

- 排版修订时已打开完整PNG、Chrome独立渲染、同宽整图对比、同尺度下半部对比及680 × 472实际图宽预览。除后续贴合关系线的三角底色轮廓外，上半部观察组与四个图标逐元素保持不变；检测卡片上下替代关系、独立规则端口和单条结果箭头可直接读出。增加高度没有改变任何既有词语的字号。
- 原图所有可见词语均保留，仅新增or；重新换行及四项目标之间的分隔符变化不影响其含义。主要正文仍为28–29单位，模式卡规则说明行距34、输入条目说明行距35、目标行距36、结果行距38。
- Chrome检查55个主图文本元素：无文字间交叠、无画布越界、无节点/输入条目/模式卡越界。逐段检查当前数据、模型、离线输入输出与结果线，没有穿过文字；结合渲染确认线与框可区分。连接通道内横线距上框26、下框24单位，paired纵向线距模式卡50单位，模型线距检测框36单位，没有沿检测底边回折的线。
- 三角实线/虚线/无箭头点线与Browser比较边完全保留。两个离线输入各自进入选择，没有Candidate→Development串行线；唯一当前数据汇合点是App–Browser关联。当前观测绕过Offline，两种模式无互连、回退、结果融合或投票，机制例子和评价条带均无流程箭头。
- 已重导矢量图PDF并编译ACM预览：17页，Figure 1在第7页。SVG原生宽180 mm；模板仍按原约177.94 mm正文通栏宽度使用，未设置高度限制或压回旧框。查看本轮全页缩略图、第7页和第16页，新图与图注无可见遮挡或裁切。最终日志无未解析引用、无水平溢出、无LaTeX错误；模板原1.47 pt纵向溢出警告仍在第16页，实际页面未见受损。
- 正式中英文图注与事实对应段落保留；仅更新布局说明和LaTeX无障碍描述。PNG为3600 × 2500，矢量导出页面约179.92 × 124.88 mm（Chrome页面单位取整），未使用旧106 mm高度。
- 底色贴合修正后再次生成全部图稿与对比预览，并重导矢量PDF、重新编译17页ACM预览。与此次修正前的SVG逐项比较，唯一变化为底色路径；连线、节点、文字、线型和配色未变。实际查看新的三角局部放大图、180 mm宽度预览和论文第7页，确认两条斜边及底边无白缝、无新增遮挡。最新编译无未解析引用、水平溢出或LaTeX错误；已有纵向溢出警告约1.45 pt，不属于本次图形问题。


以下为内容自检，**未做真实外部专家用户测试**：

| 读者问题 | 主图提供答案的位置 | 自检结果 |
|---|---|---|
| 检测什么？ | 总标题与 Manipulated reports may conflict… | 明确检测设备指纹报告可能被操纵，不保证所有修改可检出。 |
| 观察位置有何区别，是否同设备？ | One device 外框、Inside the app 内框、四个角色节点 | 区分系统、容器、嵌入网页和独立浏览器；前三者三角仍为主体。 |
| 比较为何可能帮助检测？ | Cross-check、两条已选关系与时区小例子 | 解释局部改写可能引发冲突，同时保留未集成及上下文状态。 |
| 正常运行数据为何不可缺少？ | Development data 中 Normal devices and settings，及 Limit false alarms / Limit undecidable cases | 正常差异与覆盖要求是选择约束，并非默认正常就不报警。 |
| 怎样用于当前输入、怎样评价？ | Apply selected rules 的上下可选模式、三个结果、Research evaluation | 当前观测与固定规则分开输入；研究评价与在线流程分开。 |

本轮只修改该图目录和对应的必要 LaTeX 预览。研究代码、数据、模型与统计不变；不执行训练、规则重选或评价实验，不自动提交或推送。
