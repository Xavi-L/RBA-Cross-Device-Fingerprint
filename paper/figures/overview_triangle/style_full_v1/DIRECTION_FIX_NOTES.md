# 两处最小表达修正

基线为 `393f0faa2a839e1478c5fffe0943853cec299efe`，编辑前图稿和相关源文件保存在 `direction_fix_baseline_393f0faa/`，既有 baseline 目录未覆盖。

1. **明确输入方向。** 原 App、Browser 路径、上方独立分支和 `(856,463)` 配对点完全保留。在 App 竖段内添加向下箭头（约 `y=374`），Browser 竖段内添加向上箭头（约 `y=568`），复用原 `input-arrow` 样式。箭头均远离汇合圆点和转角；App-only 仍在 Browser 关联之前独立输入，配对点继续向右进入 paired 模式。
2. **删除时区横线。** 移除 `M1270 141H1782`。时区例子的五条文字及其位置、字号完全不变，没有添加替代装饰。

SVG 结构对比确认，除两个箭头和这条删线之外，其余可见元素完全一致。3600 × 1460 PNG 的差异也仅落在这三处局部区域，55 条正文及中英文图注全文保留。

重新编译原 ACM 模板：画布仍为 **180 × 73 mm**，图＋完整图注＋内部间距仍为 **107.32776 mm / 48.7823% textheight**；正文实际字号仍为 **7.84795 / 8.12983 PDF pt**。PDF 仍为矢量、文字可提取、字体嵌入，无新增栅格化。没有继续压缩版面。

检查扩展到可见分隔线、标签引线和对象承接线；原时区横线重叠可以复现，修正版无此问题，也无新增贴字。图标内部线条、框标题插槽和既有模块入口的边界接触单独分类；保留的既有主流程近距接触见 `CHECK.json`，未改动 Offline。已实际查看模板宽度 177.942 mm 对应的完整 96 dpi 预览、同尺度输入局部及完整模板第 7 页，两个箭头可辨认；实际显示毫米尺寸仍取决于查看器缩放。

- [输入通道同尺度前后对比，96 dpi](previews/direction_fix_inputs_before_after_96dpi.png)
- [时区例子同尺度前后对比，96 dpi](previews/direction_fix_timezone_before_after_96dpi.png)
- [完整图，模板宽度 96 dpi](previews/actual_template_width_96dpi.png)
- [最新完整模板页](template_preview/figure_page_07.png)
- [两项修正及输出检查](DIRECTION_FIX_CHECK.json) · [实际模板数据](TEMPLATE_CHECK.json)

再生成顺序：`build_candidate.py` → `render_pdf_and_check.cjs` → `build_template_preview.py` → `render_candidate.cjs` → `check_direction_fix.py`。Python 使用带 pdfplumber、pypdf、Pillow 的运行时；图像渲染和模板编译依赖沿用上一轮。

仅更新候选目录及其隔离预览；目录外 214 条既有工作区状态保持，正式图、样块、研究文件及正式论文正文未改。未提交或推送。
