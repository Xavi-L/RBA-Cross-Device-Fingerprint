# HybridGuard 总览：三角互证版

2026-10-09，按导师建议，将图的视觉中心改为 **Native—WebView Host—App Web** 三个观察位置组成的三角，突出三条关系边。独立 Browser 位于三角外侧，以 C1 连接 App Web；离线规则开发与当前推理缩为辅助区域。

本版沿用上一版的衬线字体、浅色节点、细线图标和虚线分组，单独存放以便比较。上一版为 [overview_www_style](../overview_www_style/README.md)，其最近提交为 `09ee6f6ef8857a49e930be59ca0a12ccf1666843`。

- [HybridGuard_overview_triangle.svg](HybridGuard_overview_triangle.svg)：180 × 106 mm，可编辑 SVG。
- [HybridGuard_overview_triangle.png](HybridGuard_overview_triangle.png)：3600 × 2120 PNG 预览。
- [build_overview.py](build_overview.py)：独立 SVG 生成脚本，仅使用固定文案和绘图坐标。
- [render_preview.cjs](render_preview.cjs)：沿用本机现有 Sharp 渲染方式。

正文为29个 viewBox 单位（180 mm宽度下约8.22 pt），节点补充说明最小28个单位（约7.94 pt）。建议按通栏宽度使用；SVG 中所有文案保留为文本。

## 三角与线型

| 关系边 | 图中表达 | 当前证据边界 |
|---|---|---|
| Native ↔ App Web | 蓝色实线：Memory + timezone | 三个固定 B_REL_TZ RETENTION 模型均实际选入 Native–App Web 内存与时区关系的正向子句。 |
| WebView Host ↔ App Web | 赭色虚线：Viewport geometry | 新 Host 几何关系已单独研究，未进入当前固定 App；其新增观察模块不能与旧同 Web 视口关系或旧高度条件混同。 |
| Native ↔ WebView Host | 灰色点线：System context | 表达三端观察框架中的系统/宿主上下文联系；当前 App 候选池没有实际 Host 测量候选，这条边不声明已选规则或独立检测收益。 |
| App Web ↔ 独立 Browser | 蓝色实线：C1，UTC-offset mismatch | 会话/回执关联后比较两端数值 offset；C1 经预定四集合约束选择而入模。 |

**双向箭头表示参与互证或比较的两侧观察位置。** 它不表示规则双向执行、数据循环、因果关系，也不将任一端画成绝对真值。三角展示的是观察关系拓扑，只有标为 Selected 的关系边才被明确表示为进入当前保留模型。图中的 App Web 基础规则没有逐条展开，固定 App 模型不只包含三角边上的关系。

## 中文图注

**HybridGuard 的三端互证关系与当前记录判定。** Native、WebView Host 和 App Web 组成 App 内部的三角观察框架，分别提供设备/系统、容器/布局及网页运行时证据。蓝色实线标出当前已选关系，包括 Native–App Web 内存和时区关系，以及三角外 App Web–独立 Browser 的数值 UTC-offset 条件 C1；赭色虚线表示已研究但未集成的新 Host 几何关系；灰色点线仅表示 Native–Host 观察上下文，不声明其已进入当前模型。双向连线标识比较双方，不表示所有关系均已验证为可靠规则。离线开发使用既有开发数据：App 经 SPARSE 与 RETENTION 两阶段，C1 在四个预定集合中按正常报警、明确输出覆盖率和复杂度约束进行宏平均检出率选择。当前 App 与关联后的当前配对分别进入加载固定模型的 App-only 和 paired 接口，不经过离线开发，也没有 paired 到 App-only 的自动回退。T 为操纵报警，F 为未报警，U 为证据不足；选中依赖的执行或绑定失败优先输出 FAILED。字段数为目录口径，关联 ID 不是检测特征，配对不保证原子同步。

## English caption

**HybridGuard as a triangle of complementary observation views.** Native, WebView Host, and App Web provide device/system, container/layout, and webpage-runtime observations. Solid blue edges denote relations selected in the retained models: Native–App Web memory and timezone relations, and the App Web–independent Browser numeric UTC-offset condition C1. The dashed ochre edge denotes separately studied Host geometry that is not integrated; the dotted gray edge denotes Native–Host observation context outside the current App rule pool. Double-headed edges identify the views being compared, not bidirectional rule execution or trusted ground truth. Offline development applies App SPARSE selection and RETENTION, followed by constrained macro-detection selection over four cross-endpoint sets. Separate App-only and paired interfaces load fixed models and read only current inputs. T denotes a manipulation alert, F no alarm, and U insufficient evidence; execution or binding failures in selected inputs take precedence as FAILED. Paired inference has no automatic App-only fallback. Field counts describe catalogs, binding IDs are not detection features, and association does not imply atomic synchronization.

## 代码与结果依据

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

依赖使用本机已有 Python/Node 与 Sharp；Node 依赖目录可通过 `RBA_NODE_MODULES` 指定。生成过程不导入实验代码，不采集、拟合、选择、预测或计时。

本版实际检查记录（2026-10-09）：

- 已分别打开最终 Sharp/librsvg PNG 与 Chrome 154.0.8037.98 渲染图，检查三角双向连线、关系状态、Browser 外接关系与两个独立输入路径；未见文字遮挡、裁切或图标丢失。
- Chrome 检查46个文本元素，0越界、0文本包围框交叠；4个图标均正常显示。双向标记在两种渲染器中方向一致。兼容性结论限于这两个本机环境。
- SVG 无嵌入栅格图、无外部资源引用；文字可编辑，所有本地图标引用可解析。PNG 解码与3600 × 2120尺寸检查通过。
- 重复生成 SVG/PNG，与上述已检查版本逐字节一致。Python/Node 语法检查、文本空白检查及 README 文件链接检查通过。
- 本轮只新增本目录的5个文件；上一版图稿及其余213条已有工作区状态保留。没有修改研究代码、模型或实验结果，也没有运行新的研究训练或评价。
