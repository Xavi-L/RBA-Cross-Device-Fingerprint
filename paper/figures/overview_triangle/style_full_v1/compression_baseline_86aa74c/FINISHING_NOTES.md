# 完整候选总图局部收尾

本轮基线为已审阅提交 `55ca3bbadb6d4ca7aef3cb7e06b6356c86b02f52`。开始时该候选目录没有后续工作区差异。编辑前的 SVG、PNG、PDF、源脚本、文案和检查记录共 14 个文件保存在 [finishing_baseline_55ca3bb/](finishing_baseline_55ca3bb/)，其 SHA-256 记录见 [SNAPSHOT.json](finishing_baseline_55ca3bb/SNAPSHOT.json)。原有 `baseline/` 仍是更早正式图基线，未覆盖。

## 修改与取舍

- Native 长托线、Host 上/右半框、App Web 多边括线及 Browser 左/下半框，缩减为 **4 段各 32 单位的短承接线**。对象级辅助线总长从 2582 降为 128 单位，未降低透明度。同设备/App 边界、标签短引线保留；四个对象的图标、位置、填充和全部说明保持不变。
- App Web–Browser 蓝色比较线直接落到两个图形底色边缘，缩短了原来的横向绕行。其余比较边的端点继续落在对象组边缘；有歧义的文字侧保留短承接线。四条关系的颜色、线型、双向箭头/无箭头状态不变。
- App 观测现在只有一个出口，在 `(100,963)` 分支：一支独立进入 App-only；另一支与 Browser 在 `(965,963)` 关联，再直接下行进入 paired。唯一圆点保留在真实关联处，普通分支不新增端口装饰。当前数据线总长从 1879 降为 1670 单位，转折从 4 处降为 2 处。
- **入口仍为 App-only 左侧、paired 右侧。** 尝试同侧时，Browser 路径会穿过独立 App-only 输入，或需要绕过上方模式、穿越 `or` 所在空白。因此按“无新交叉、少折返优先于形式一致”的要求保留两侧入口。两张卡片右缘从 960 收至 910，仅收去空白；文字和字号不变，配对通道与卡片保持 55 单位距离。
- 紫色规则加载线改为下行后直接进入公共规则应用区标题侧，独立于数据端口。共同输出箭头、上下替代模式、`or`、三种结果和评价条带均保留，没有串行、回退或融合。

## 内容、实际路径和字体检查

[FINISHING_CHECK.json](FINISHING_CHECK.json) 与 [CHECK.json](CHECK.json) 同时记录本轮检查。55 个正文条目及出现次数与本轮编辑前清单相同；中英文图注逐字节保留。四个观察对象的 SVG 分组逐项相同，字体层级、红色强调和配色未变。

检查直接解析实际 SVG 路径、箭头、模式矩形和关联圆点：App 分支在 Browser 关联之前，App-only 可独立到达，paired 需要两方关联输入，模型与数据端口分开，结果仅从共同检测区输出。除明确的分支及关联外，无流程线相交或重叠；无连线穿字。没有白色遮罩、裁剪路径或透明度处理掩盖冲突。

实际查看了全图、三角及 Browser 端点、下方走线局部前后对照、180 mm 灰度预览和实际 PDF 渲染。SVG 无重复 ID、失效 marker、外链资源、嵌入栅格、嵌套整图、非等比文字缩放。Chrome 的真实平台字体记录为 `TimesNewRomanPSMT`、`TimesNewRomanPS-BoldMT`、`TimesNewRomanPS-ItalicMT`，没有 fallback。新 PNG 和局部预览直接来自这次 Chrome 渲染，避免另一个 SVG 渲染器替换字体。

[PDF_CHECK.json](PDF_CHECK.json) 确认独立 PDF 为一页、零栅格图像，文字可提取，实际 Times New Roman 字体均嵌入并带 ToUnicode。没有复制系统字体文件。

## 真实 ACM 模板版面

只读来源为仓库已有的 `output/pdf/hybridguard_triangle_template_preview/`，不是另造的 ACM 外观页面。隔离副本在 [template_preview/](template_preview/)，沿用原 `acmart` 类、`sigconf,anonymous,review` 选项、原正文、宏、页边距及 `figure*` + `includegraphics[width=\textwidth]`。主入口、类文件、正文和参考文献与来源逐字节相同；副本中只改图块引用、同步正式英文图注，并加入不改变排版的尺寸日志。

使用项目现有的 pdfLaTeX、BibTeX、latexmk 实际编译，得到 **17 页，第 7 页包含 Figure 1**。已打开并检查该完整页面，包含页眉、行号、图、正式英文图注、相邻双栏正文和页码，没有可见遮挡、裁切或箭头贴字；没有缩小模板字体、负 `vspace`、高度限制或非等比缩放。

| 项目 | 实测 |
|---|---|
| 独立 SVG | 180 × 133 mm，画布高度不变 |
| 独立 PDF 页 | 179.9167 × 133.0113 mm，Chrome 页面取整 |
| 模板 `textwidth` | 506.295 TeX pt = **177.9423 mm** |
| 插入图宽 × 高 | **177.9423 × 131.5517 mm** |
| 相对 180 mm SVG 宽度 | 98.8569%；相对实际导出 PDF 页宽 98.9026% |
| 图内 28/29 单位正文实际字号 | **7.84795 / 8.12983 PDF pt**（PDF pt = 1/72 inch） |
| 正式英文图注 | 原模板 Linux Libertine Bold，8.9664 PDF pt（约 9 TeX pt） |
| 图、图注及模板内部间距合计 | **474.3009 TeX pt = 166.6977 mm** |
| 占模板正文高度 | **75.77%**；下方仍有双栏正文，未预设半页目标 |

尺寸来自编译日志中的实际图盒及浮动体盒，而非截图估算；PDF 字体和字号由最终文件提取。图注与冻结英文原文一致（仅 TeX 标点编码和断行差异），模板页保持矢量路径、可提取文字，未整图栅格化。详情见 [TEMPLATE_CHECK.json](TEMPLATE_CHECK.json)。

## 对照与交付

- [收尾前完整候选稿 vs 收尾后，同宽、正常透明度](previews/finishing_before_after_same_width.png)
- [对象括线与端点局部前后对照](previews/finishing_endpoints_before_after.png)
- [下方数据路径局部前后对照](previews/finishing_routes_before_after.png)
- [真实模板完整第 7 页](template_preview/figure_page_07.png)、[17 页隔离论文预览 PDF](template_preview/hybridguard_draft.pdf)
- [候选 SVG](HybridGuard_overview_candidate.svg)、[PNG](HybridGuard_overview_candidate.png)、[独立矢量 PDF](HybridGuard_overview_candidate.pdf)

本轮对照使用 `finishing_baseline_55ca3bb/` 中的完整候选稿。旧 `before_after_same_width.png` 仍是较早正式图与当前候选的背景对照，不能当作本轮前后版本。

## 保留的限制与停止点

- 同侧模式入口建议未采用，原因与几何取舍如上；已消除原来两条 App 长距离平行出口及配对关联后的横向折返。
- 最终编译没有水平溢出、未解析引用、缺字或字体替换警告；原模板第 16 页仍有约 **1.452 TeX pt 的纵向溢出警告**，已查看该页，未见裁切。原有 underfull、浮动体位置和 ACM reference-format 提醒仍保留。图所在第 7 页的版面检查通过，不将整篇日志表述为零警告。
- 这是现有论文预览工程的版面验收。其较早正文包含历史研究描述，本轮按要求保持不变，没有据此重新审计或更新论文研究结论，也没有进行纸质打印、外部读者测试或导师验收。
- 正式总图、`style_pilot_v1`、正式论文入口与正文、研究代码/数据/模型均未改；其他 214 项工作区状态保持原样。未运行训练、规则重选或性能评价，未 commit/push。

本轮结论：不必要的对象半框已缩减，当前数据路径更少转折且无新增交叉，图与正式英文图注通过现有真实模板的图所在页检查。仍为待审候选稿；到此停止，不自动替换正式总图或宣称可直接投稿。
