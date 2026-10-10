# HybridGuard 总览：三角互证版

2026-10-09，在已回退的第一版三角稿 `a6c9aa597bbb74f2ae56f14a479e2d79bc41faf7` 上做局部修订。保留 **Native—WebView Host—App Web** 三角、外侧独立 Browser、右侧完整图例与离线开发模块，以及底部两个完整推理接口；画布、框位、字号、文字密度和留白均沿用第一版。

本版沿用上一版的衬线字体、浅色节点、细线图标和虚线分组，单独存放以便比较。上一版为 [overview_www_style](../overview_www_style/README.md)，其最近提交为 `09ee6f6ef8857a49e930be59ca0a12ccf1666843`。

- [HybridGuard_overview_triangle.svg](HybridGuard_overview_triangle.svg)：180 × 106 mm，可编辑 SVG。
- [HybridGuard_overview_triangle.png](HybridGuard_overview_triangle.png)：3600 × 2120 PNG 预览。
- [build_overview.py](build_overview.py)：独立 SVG 生成脚本，仅使用固定文案和绘图坐标。
- [render_preview.cjs](render_preview.cjs)：沿用本机现有 Sharp 渲染方式。
- [同宽前后对比](previews/before_after.png)：上方为本轮修改前的 a6c9aa5 第一版，下方为最终稿，两幅均为1800 px显示宽度。
- [图标实际尺寸预览](previews/icons_actual_size.png)：按180 mm图宽、96 px/in换算的三个完整节点。
- [图标放大预览](previews/icons_enlarged.png)：直接从最终 SVG 按每 viewBox 单位4 px渲染，检查笔画与细节。

正文为29个 viewBox 单位（180 mm宽度下约8.22 pt），节点补充说明最小28个单位（约7.94 pt）。建议按通栏宽度使用；SVG 中所有文案保留为文本。

## 三角与线型

| 关系边 | 图中表达 | 当前证据边界 |
|---|---|---|
| Native ↔ App Web | 蓝色实线：Memory + timezone | 三个固定 B_REL_TZ RETENTION 模型均实际选入 Native–App Web 内存与时区关系的正向子句。 |
| WebView Host ↔ App Web | 赭色虚线：Viewport geometry | 新 Host 几何关系已单独研究，未进入当前固定 App；其新增观察模块不能与旧同 Web 视口关系或旧高度条件混同。 |
| Native — WebView Host | 无箭头灰色点线：Shared context | 仅表达共享观察上下文；当前 App 候选池没有实际 Host 测量候选，这条边不声明已选规则或独立检测收益。 |
| App Web ↔ 独立 Browser | 蓝色实线：C1，UTC-offset mismatch | 会话/回执关联后比较两端数值 offset；C1 经预定四集合约束选择而入模。 |

**有箭头的比较边标识比较双方；无箭头灰色点线仅表示共享上下文。** 箭头不表示规则双向执行、数据循环、因果关系，也不将任一端画成绝对真值。三角展示的是观察关系拓扑，只有标为 Selected 的关系边才被明确表示为进入当前保留模型。图中的 App Web 基础规则没有逐条展开，固定 App 模型不只包含三角边上的关系。

## 中文图注

**HybridGuard 的三端互证关系与当前记录判定。** Native、WebView Host 和 App Web 组成 App 内部的三角观察框架，分别提供设备/系统、容器/设置及网页运行时证据。蓝色实线标出当前已选关系，包括 Native–App Web 内存和时区关系，以及三角外 App Web–独立 Browser 的数值 UTC-offset 条件 C1；赭色虚线表示已研究但未集成的新 Host 几何关系；无箭头灰色点线仅表示 Native–Host 共享上下文，不声明其已进入当前模型。有箭头的比较边标识比较双方，不表示所有关系均已验证为可靠规则。App 检测器结合视图内规则与选中的跨视图关系。离线开发使用既有开发数据：App 经 SPARSE 与 RETENTION 两阶段，C1 在四个预定集合中按正常报警、明确输出覆盖率和复杂度约束进行宏平均检出率选择。当前 App 与关联后的当前配对分别进入加载固定模型的 App-only 和 paired 接口，不经过离线开发，也没有 paired 到 App-only 的自动回退。T 为操纵报警，F 为未报警，U 为证据不足；选中依赖的执行或绑定失败优先输出 FAILED。字段数为目录口径，关联 ID 不是检测特征，配对不保证原子同步。

原 Host26 主要包括提供程序、设置、UA、桥接和应用元数据，因此节点副标题由 `Container & layout` 改为 `Container & settings`。新几何检查依赖额外的 `collection_observations.webview_geometry` 观测模块，不能解释为由原26字段完整提供。

## English caption

**HybridGuard as a triangle of complementary observation views.** Native, WebView Host, and App Web provide device/system, container/settings, and webpage-runtime observations. Solid blue edges denote relations selected in the retained models: Native–App Web memory and timezone relations, and the App Web–independent Browser numeric UTC-offset condition C1. The dashed ochre edge denotes separately studied Host geometry that is not integrated; the arrowless dotted gray edge denotes only shared Native–Host context outside the current App rule pool. Arrowed comparison edges identify the views being compared, not bidirectional rule execution or trusted ground truth. The App detector combines within-view rules with selected cross-view relations. Offline development applies App SPARSE selection and RETENTION, followed by constrained macro-detection selection over four cross-endpoint sets. Separate App-only and paired interfaces load fixed models and read only current inputs. T denotes a manipulation alert, F no alarm, and U insufficient evidence; execution or binding failures in selected inputs take precedence as FAILED. Paired inference has no automatic App-only fallback. Field counts describe catalogs, binding IDs are not detection features, and association does not imply atomic synchronization.

The original Host26 catalog mainly covers provider, settings, UA, bridge, and app metadata. The new geometry check requires the additional `collection_observations.webview_geometry` observation module; its inputs are not fully supplied by those original 26 fields.

## 本轮图标与局部配色

| 位置 | 图标 | 含义与边界 |
|---|---|---|
| Native | 竖向手机、屏幕边界、简化六齿设置符号 | 设备/系统侧观测，不代表硬件可信根或不可伪造身份。沿用52单位图标槽和暖色线条。 |
| WebView Host | 有标题栏的应用外壳，包住折角页面 | 强调宿主容器位置，不表示新几何关系已入模。沿用48单位图标槽和蓝色线条，内部内容线较轻。 |
| App Web | 带折角及清晰 JS 字样的页面 | 强调网页脚本侧；独立 `app-web-js` symbol，沿用48单位图标槽和绿色线条。 |

三个图标表示同一设备上的不同观察位置，不是三个物理终端或三个可信真值。外轮廓沿用2.6单位圆角线条；小图标仅保留必要内线。标题起点、图标槽位置与大小均未改动。独立 Browser 继续使用原有 `web` symbol，其图形和调用参数完全保留。

Native `#FAF0E2`、Host `#E9F0F9`、App Web `#EDF3E9` 及底部接口颜色保持原样。仅新增独立 `offline_bg = #EEE2FA` 与 `browser_bg = #E9F3F3`，分别区分离线开发和独立 Browser；不改变共享的奶油色或绿色常量，不使用透明度冲淡或全局增饱和。

`accent_red = #D62828` 仅用于中央 **corroboration**、C1 的 **mismatch**、输出释义的 **Manipulation alert**。后者在同一个文本元素内用 `tspan` 着色并保留空格；T、F、U、其他文字和关系线保留原色。红字表示阅读重点，不是新增关系状态或攻击确认；蓝色已选关系、赭色已研究关系、灰色上下文的语义不变。

## 代码与结果依据

- [App177 字段目录](../../../android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv)：84个 Native、26个 Host、67个 App Web 字段；Host26 不包含新模块的同期几何操作数。
- [当前 App 候选依赖](../../../deliverables/app177_core_ablation_v1/CANDIDATE_DEPENDENCIES.md)及[App 消融报告](../../../deliverables/app177_core_ablation_v1/REPORT.md#L24)：50个 App Web 基础模板及3个关系模板；没有实际 Host 测量候选。
- 实际读取三份固定模型的 `clauses`：[01](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-01__RETENTION/model.json)、[02](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-02__RETENTION/model.json)、[03](../../../deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-03__RETENTION/model.json)。三份均含 `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE` 和 `MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS` 的正向子句。
- [新 Host 几何语义](../../../deliverables/screen_geometry_observation_v1/SEMANTICS.md)：独立新增观察模块、有限布局域、非原子观察窗口；未改旧模型。Host26/App Web67 的目录计数不保证旧记录具备新增几何操作数。
- [C1 操作数](../../../deliverables/browser67_cross_endpoint_diagnostic_v1/conditions.py#L5)、[四集合选择协议](../../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md)、[保存选择结果](../../../deliverables/cross_endpoint_constrained_extension_v1/results/models.json)：C1 比较 App Web 与 Browser 的 `execution_layer.timezone_offset`，不比较 Native 与 Browser 时区名称。
- [App 当前输入接口](../../../hybridguard_agent/research/mtc_timezone_selection.py#L143)、[paired 当前输入接口](../../../deliverables/cross_endpoint_constrained_extension_v1/inference.py#L10)、[状态合成](../../../deliverables/cross_endpoint_constrained_extension_v1/selector.py#L14)：当前输入与离线开发分离、选中输入失败优先、无自动回退。

较复杂的限定延续[上一版完整事实说明](../overview_www_style/README.md)：SPARSE 与 RETENTION 并非同一目标的连续优化；有限跨端空间选择不等于任意规则空间全局最优。Browser 资源扩展经过选择但无新增条件准入，本版从主图移至此说明，没有将其画成已集成。历史 MTC 的144+117仍是历史评价记录，与开发正常数据630分开，未变为新盲测。目录数不保证逐条完整或全部入模；T 不是攻击真值，F 不是设备安全；`T OR U = T`、`F OR U = U`、`T OR FAILED = FAILED`。本图对合法输入的状态概括不替代接口契约。

## 生成与检查

在仓库根目录执行：

```sh
python3 -B paper/figures/overview_triangle/build_overview.py
node paper/figures/overview_triangle/render_preview.cjs
```

渲染脚本同时生成两个图标预览。重建同宽对比时，从指定提交只读提取原 PNG，并作为输入：

```sh
git show a6c9aa597bbb74f2ae56f14a479e2d79bc41faf7:paper/figures/overview_triangle/HybridGuard_overview_triangle.png > /tmp/HybridGuard_triangle_a6c9aa5.png
node paper/figures/overview_triangle/render_preview.cjs --before /tmp/HybridGuard_triangle_a6c9aa5.png
```

本轮实际比较输入是在任何编辑前保存的当前第一版 PNG，并核对与 a6c9aa5 的文件一致。依赖使用本机已有 Python/Node 与 Sharp；Node 依赖目录可通过 `RBA_NODE_MODULES` 指定。生成过程不导入实验代码，不采集、拟合、选择、预测或计时。

图标与局部配色修订的检查记录（2026-10-09，后续边框补充见文末）：

- 与保存的第一版逐项比较 SVG：180 × 106 mm、`0 0 1800 1060`、所有主框尺寸、坐标、字号和图标槽均不变。46个正文文本元素仅有两处指定短标签替换；图标定义内另有可编辑的 `JS`。PNG 实际解码尺寸为3600 × 2120。
- 已打开最终 Sharp/librsvg PNG、Chrome 154.0.8037.98 渲染图、180 mm图宽预览、同宽前后对比及图标原尺寸/放大预览。手机和设置符号、外壳内嵌页面、JS文档可分别辨认；没有新增遮挡、裁切或图标丢失。保留原来的结构饱满程度，只有指定两块底色与三处红字变化。兼容性结论限于这两个本机渲染环境。
- Chrome 检查46个正文文本元素：0越界、0文本间包围框交叠；三个新图标与正文无包围框交叠。原 Browser 图标与计数文本的包围框在前后均有约2.84 × 1单位的微小交叠，实际渲染未见笔画遮挡；其符号和位置保持原样。输出释义的62个字符（含空格）完整保留，`tspan` 未引入换行或丢失空格。
- 灰色上下文边与图例均无箭头，也没有 `url(#None)`；其余比较边和当前输入路径的坐标、线型、线宽、颜色与箭头均未变。`web` symbol 与 Browser 调用参数逐项一致，App Web 使用独立符号。SVG 无嵌入栅格、无外部资源引用，所有本地引用可解析，文字保持可编辑。
- Python/Node 语法、`git diff --check`、README 文件链接与三份预览尺寸检查通过。只更新本目录5个原文件并新增3份预览；目录外213条已有工作区状态保留，HEAD仍为 a6c9aa5，暂存区为空；未执行提交或推送。

本轮事实复核限于上述字段目录、候选依赖、新几何语义、三份固定模型的 `clauses` 及原 README；其余依据链接和既有边界说明予以保留，没有重新执行全仓库审计。没有修改研究代码、模型、数据或实验结果，也没有运行训练或规则重选。

边框补充（2026-10-09）：为 `Shared context` 和 `Memory + timezone` 两个白底标签框添加统一浅灰色 `#B9C0C8` 细边框，线宽1.2 viewBox单位（180 mm图宽下约0.34 pt）。重新生成 SVG、PNG 和同宽对比；与补充前 SVG 逐元素核对，仅两框的描边颜色与线宽发生变化。已查看本次最终 PNG、180 mm图宽预览和中央边框细节，边界可辨且未遮挡文字。其余框、文字、布局与关系线均保留。
