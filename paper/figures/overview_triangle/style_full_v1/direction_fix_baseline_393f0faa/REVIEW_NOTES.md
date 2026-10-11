# HybridGuard 完整候选稿：横向重排

当前唯一推荐稿基于 `86aa74c0dad51af25ca1b787751f474c7b8d632a`，完成观测 / 当前检测 / 说明与 Offline 三列重排。真实 ACM 模板中的图、完整图注及内部间距占正文高度 **48.7823%**，通过 `< 50%` 硬要求；未达到 `<= 48%` 理想目标。正文实际字号保持 **7.84795 / 8.12983 PDF pt**，55 条正文和完整中英文图注未改。

当前布局、验收数据和限制以 [COMPRESSION_NOTES.md](COMPRESSION_NOTES.md) 为准。[FINISHING_NOTES.md](FINISHING_NOTES.md)、`FINISHING_CHECK.json` 和 `check_finishing.py` 是上一轮 55ca3bb → 86aa74c 的历史记录/校验入口，不是本轮布局验收。旧的 formal/reference/finishing 比较图也仅保留历史用途。

## 当前交付

- [SVG](HybridGuard_overview_candidate.svg)、[PNG](HybridGuard_overview_candidate.png)、[矢量 PDF](HybridGuard_overview_candidate.pdf)
- [完整图预览](previews/chrome_full.png)、[180 mm / 96 dpi](previews/actual_180mm_96dpi.png)、[灰度](previews/grayscale_180mm_96dpi.png)、[实际 PDF 渲染](previews/pdf_180mm_render.png)
- [86aa74c 前后同宽对比](previews/compression_before_after_same_width.png)、[模板宽度对比](previews/compression_before_after_template_width_96dpi.png)、[实际模板整页对比](previews/compression_template_pages_same_scale.png)
- [完整模板 PDF，第 7 页](template_preview/hybridguard_draft.pdf)、[完整图页 PNG](template_preview/figure_page_07.png)
- [局部：观测三角](previews/triangle_detail.png)、[Browser](previews/browser_detail.png)、[检测](previews/detection_detail.png)、[Offline](previews/offline_detail.png)、[几何关系](previews/geometry_detail.png)、[时区例子](previews/timezone_detail.png)
- [中英文图注](CAPTIONS.md)、[正文清单](CONTENT_MANIFEST.json)、[图标来源及许可](assets/SOURCES.md)
- [Chrome 排版检查](CHECK.json)、[内容与路径检查](COMPRESSION_CHECK.json)、[PDF 检查](PDF_CHECK.json)、[模板检查](TEMPLATE_CHECK.json)、[工作区范围](WORKSPACE_CHECK.json)

## 再生成

从仓库根目录顺序运行，仅输出至本目录：

```sh
python3 -B paper/figures/overview_triangle/style_full_v1/build_candidate.py
node paper/figures/overview_triangle/style_full_v1/render_pdf_and_check.cjs
python3 -B paper/figures/overview_triangle/style_full_v1/build_template_preview.py
python3 -B paper/figures/overview_triangle/style_full_v1/check_compression.py
node paper/figures/overview_triangle/style_full_v1/render_candidate.cjs
```

依赖为带 `pdfplumber` / `pypdf` 的 Python、Sharp、Playwright、本机 Chrome、原 TeX Live/latexmk 及 Poppler。本轮使用 Codex bundled Python/Node。可用 `RBA_NODE_MODULES`、`RBA_CHROME` 指定依赖。PNG 来源于已核验字体的 Chrome 像素；PDF/模板页对照使用真实 PDF 的 Poppler 渲染。

本轮冻结基线保存在 `compression_baseline_86aa74c/`；检查脚本允许位置、对齐及换行变化，要求字体、字号、颜色、文案、图标内部矢量和语义不变。`check_compression.py` 从历史检查模块复用纯几何/PDF 工具函数，不执行历史收尾验收。目录外既有修改保持，不涉及研究计算、正式总图替换或自动提交推送。
