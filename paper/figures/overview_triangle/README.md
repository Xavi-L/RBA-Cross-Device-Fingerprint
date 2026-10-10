# HybridGuard：面向计算机领域读者的研究与方法总览

2026-10-10，在 `3443c16d8cd65e3575e84accce93bcb45a340cbc` 已完成图标、局部配色和细边框修订的三角稿上重构叙述。先说明检测对象及同设备多位置参照，再展示正常差异、离线规则选择、当前检测和研究评价。没有采用后来的精简或全图增色版本，也没有回退 Git。

## 交付与阅读顺序

- [最终 SVG](HybridGuard_overview_triangle.svg)：180 × 106 mm，文字可编辑。
- [最终 PNG](HybridGuard_overview_triangle.png)：3600 × 2120 px。
- [文案清单](COPY.md)：每个区域回答的问题、最终英文及连线含义。
- [生成脚本](build_overview.py)、[渲染脚本](render_preview.cjs)：只使用固定文案与坐标，不导入研究模块。
- [同宽前后对比](previews/before_after.png)：上方为本轮编辑前的3443c16，下方为最终稿；两幅同为1800 px显示宽度。
- [180 mm图宽预览](previews/actual_size.png)：按96 px/in换算为680 × 400 px，实际物理显示大小仍取决于查看器缩放。
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
| 固定模型输入 | 紫色单向线，Selected rules 标签 | 已选规则加载到共同检测区，两种模式使用各自规则集。 |
| 当前数据输入 | 黑色单向线 | App-only 和已关联的 App–Browser 当前观测分别进入对应模式，不经过 Offline。 |

底部输出连线共用三种结果的文字释义，不表示必须运行两个模式或融合两次结果。两种模式没有顺序、回退或相互调用关系。评价条带与机制例子均无流入检测器、流入选择器或反馈训练的箭头。

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
git show 3443c16d8cd65e3575e84accce93bcb45a340cbc:paper/figures/overview_triangle/HybridGuard_overview_triangle.png > /tmp/HybridGuard_triangle_3443c16.png
node paper/figures/overview_triangle/render_preview.cjs --before /tmp/HybridGuard_triangle_3443c16.png
```

Node 需可用的 Sharp；依赖目录可用 `RBA_NODE_MODULES` 指定。本轮使用编辑前保存的当前 PNG 作为比较输入。SVG、PNG、节点预览和同宽比较来自同一生成结果。LaTeX 同步方法见预览说明。

## 修改记录与本轮验收

- 用检测问题、观察角色与相容关系替换字段计数、内部编号、算法阶段和重复接口合同；新增一个紧凑时区示意和评价条带。
- 保留180 × 106 mm画布、四个图标定义及52/48单位图标尺寸。Native 改为360 × 140，Host370 × 138，App Web410 × 138，Browser410 × 132；主标题/正文仍保持可读字号，未压缩字体或纵向拉伸 SVG。
- 三角整体上移，Native 下缘346到下方节点上缘536为190单位净空；Browser 移到 App 外框下方且仍在同设备框内。右侧原大图例让位于机制例子；离线块用输入、选择、输出建立关系。底部两个大型接口重组为一个检测区中的两种输入模式。
- Native `#FAF0E2`、Host `#E9F0F9`、App Web `#EDF3E9`、Browser `#E9F3F3`、Offline `#EEE2FA` 保持原样；没有全局增色、渐变或阴影。红色 `#D62828` 仅用于 Cross-check、conflict 和 Manipulation alert。白底关系标签继续用 `#B9C0C8`、1.2单位细边框。
- 已打开本轮 PNG、Chrome 独立渲染及180 mm图宽预览。55个主图文本元素在 Chrome 中无画布越界、无文字间交叠，节点和离线输入/选择框中文字均在边界内。图标定义与编辑前一致；正文最小28单位。坐标检查只是辅助，结论同时依据实际渲染阅读。
- 已打开同宽前后对比与灰度稿：三角、独立 Browser 与两种输入模式清楚；比较边、研究虚线和无箭头上下文点线在灰度下仍可分。例子为两个分隔的当前情形，没有时间轴或模型输入线；Offline 候选输入与当前数据路径分开。
- 已重新导出矢量 PDF 并编译现有 ACM 模板：17页，Figure 1在第7页，正文通栏宽约177.94 mm。检查本轮全页缩略图、第7页及第16页；新图和图注无可见遮挡。最终编译日志无未解析引用、无水平溢出，保留模板原第16页1.47 pt纵向溢出警告但未见裁切。图 PDF 无栅格图像对象，Times New Roman已嵌入。此次记录只对应本轮新生成文件，不沿用旧稿验收。

以下为内容自检，**未做真实外部专家用户测试**：

| 读者问题 | 主图提供答案的位置 | 自检结果 |
|---|---|---|
| 检测什么？ | 总标题与 Manipulated reports may conflict… | 明确检测设备指纹报告可能被操纵，不保证所有修改可检出。 |
| 观察位置有何区别，是否同设备？ | One device 外框、Inside the app 内框、四个角色节点 | 区分系统、容器、嵌入网页和独立浏览器；前三者三角仍为主体。 |
| 比较为何可能帮助检测？ | Cross-check、两条已选关系与时区小例子 | 解释局部改写可能引发冲突，同时保留未集成及上下文状态。 |
| 正常运行数据为何不可缺少？ | Development data 中 Normal devices and settings，及 Limit false alarms / Limit undecidable cases | 正常差异与覆盖要求是选择约束，并非默认正常就不报警。 |
| 怎样用于当前输入、怎样评价？ | Apply selected rules 的并列模式、三个结果、Research evaluation | 当前观测与固定规则分开输入；研究评价与在线流程分开。 |

最终检查：脚本语法、图内定稿文案、关系状态、流向边界、README 链接、SVG 副本与 LaTeX 图注一致性检查通过，`git diff --check`通过。编辑前比较图与3443c16基线一致。目录外214条原有工作区状态保留，HEAD仍为3443c16d，暂存区为空。

只修改本图目录和必要 LaTeX 预览；没有运行采集、训练、规则重选或评价实验，没有自动提交或推送。
