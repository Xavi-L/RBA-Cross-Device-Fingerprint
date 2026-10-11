# HybridGuard 横向重排验收

本轮以已审阅提交 `86aa74c0dad51af25ca1b787751f474c7b8d632a` 为基线，仅更新 `style_full_v1/` 候选稿。**真实 ACM 模板中，图、完整英文图注及内部间距占正文高度 48.7823%，满足严格 `< 50%` 的硬要求。** 尚未达到 `<= 48%` 的理想值，超出理想值约 1.72 mm。

## 布局变化

- App 内三角按逆时针 90° 的顶点顺序重排：Native 在左，App Web 在右上，WebView Host 在右下。图标和文字保持直立，三条关系组成三角拓扑。Browser 留在 App 虚线框外、同设备实线框内。
- 原底部长条检测区移到中间列。两种模式上下排列，以 `or` 表示替代；App 数据先分支，Browser 只接入 paired 的关联点。结果紧接共同外框下方，无模式串行、回退或结果融合。
- 右列上部保留时区例子，下部保留 Offline。材料、四项目标和 Selected rules 未删。紫色规则路径从右侧进入检测共同外框的独立下侧端口，与左侧黑色当前数据输入及共同结果箭头分开。
- Research evaluation 成为横跨中间与右侧的单行 footer，与左侧设备框底部处于同一高度范围，没有箭头，不作为线上阶段。
- 三列共用同一段纵向空间；检测区不再叠加在观测区下方。图高从 133 mm 降为 73 mm（降低约 45.1%），宽度仍为 180 mm。图标沿用原矢量，调整对象占位；字号、字体、颜色、字重、斜体和红字强调不变。局部换行与对齐适应新列宽。

## 真实模板测量

源工程为 `output/pdf/hybridguard_triangle_template_preview/`，复制到本目录 `template_preview/` 后编译。保留 `acmart` 的 `sigconf,anonymous,review` 选项、原入口、类文件、章节、参考文献及页边距。候选图仅按 `width=\textwidth` 等比插入，图注全文不变，无高度限制、负间距或非等比变形。

| 项目 | 86aa74c 基线 | 本轮候选 |
|---|---:|---:|
| SVG 本体宽 × 高 | 180 × 133 mm | 180 × 73 mm |
| 模板实际图宽 | 177.942 mm | 177.942 mm |
| 模板实际图高 | 131.55 mm | 72.182 mm |
| 图注与模板内部间距 | 35.146 mm | 35.146 mm |
| 图 + 图注 + 内部间距总高 | 166.70 mm | **107.328 mm** |
| 总高 / textheight | 75.7669% | **48.7823%** |
| 图内 28 / 29 单位正文的实际 PDF 字号 | 7.84795 / 8.12983 pt | **7.84795 / 8.12983 pt** |

模板日志实际记录 `textheight=626 pt`、图高 `205.37706 pt`、float 高 `305.37706 pt`，深度均为零。与半页上限相比还留有 **2.679 mm**；与 48% 理想值相比仍多 **1.721 mm**。此处 pt 是 TeX pt；表中图内实际字号是从 PDF 字符读取的 PDF pt。

Chrome 导出独立 PDF 实测 179.917 × 72.983 mm（页面单位取整），等比例置入模板。独立图及模板图页均无嵌入栅格图像，保留 318 个矢量图形对象；全部 55 条正文可从 PDF 提取。Times New Roman 字体实际嵌入且有 ToUnicode 映射，未用 CSS 声明替代实际字体检查。

## 内容、走线与页面核验

- 正文 55 条的文字及出现次数、中英文图注、图标内部矢量、全部文字字体样式和红字均与基线一致。只允许位置、换行和对齐变化。
- Native–App Web 的 memory/timezone、App Web–Browser 仍为蓝色双向 selected；Host–App Web 仍为赭色虚线及 `Not in current detector`；Native–Host 仍为无箭头灰色点线及 `No detection rule`。
- 当前数据不进入 Offline；规则与当前观测各有独立输入；例子和研究评价无流程边。`No alert` 不等于安全的完整图注保留。
- 实际路径解析确认 App 分支、paired 关联圆点、两种模式入口、规则独立入口及单一结果出口，无意外交叉或重叠。当前数据线总长从 1670 降至 684 单位，规则输入从 340 降至 170 单位；对象短承接线总长从 128 降至 64 单位。
- Chrome 实际字体和文字边界检查通过：无正文互相重叠、无主关系/流程线穿字、无越界、无文字压缩或栅格嵌入。查看了完整图、96 dpi 预览、灰度预览、实际 PDF 渲染及完整模板第 7 页。
- 实际编译得到 17 页预览，第 7 页含该图。图、完整图注、页眉及相邻正文视觉检查通过。本轮编译无 overfull hbox/vbox、缺字、字体警告或未解析引用；原基线第 16 页的纵向警告未在当前编译中出现。原模板关于 `printacmref=true` 的 ACM reference-format 提醒仍保留，未为此次版面验收修改类配置。

## 对照与范围

修改前 SVG/PNG/PDF、脚本、文案及真实模板 PDF/图页保存在 `compression_baseline_86aa74c/`；保存文件已与该提交直接逐字节比较。更早的 `baseline/` 和 `finishing_baseline_55ca3bb/` 保持原样。

- [同宽图稿对比](previews/compression_before_after_same_width.png)：两图使用相同横向比例和正常透明度。
- [模板宽度 96 dpi 对比](previews/compression_before_after_template_width_96dpi.png)：两图均对应 177.942 mm 的插入宽度（像素取整）。
- [真实模板整页对比](previews/compression_template_pages_same_scale.png)：基线与本轮实际 PDF 第 7 页均以 150 dpi 渲染，页面比例与透明度一致。
- [当前完整模板页](template_preview/figure_page_07.png)、[模板测量](TEMPLATE_CHECK.json)、[内容与路径检查](COMPRESSION_CHECK.json)、[PDF 检查](PDF_CHECK.json)、[工作区检查](WORKSPACE_CHECK.json)。

正式总图、`style_pilot_v1/`、正式论文入口、研究代码/数据/模型/结果未改；目录外 214 条既有工作区状态保持。没有运行研究实验，也没有自动提交或推送。保留历史正文只是用于真实版面预览，不构成对历史研究结论的重新验证。此候选已满足本轮内容及高度标准，等待导师审阅，不再展开新的美术探索。
