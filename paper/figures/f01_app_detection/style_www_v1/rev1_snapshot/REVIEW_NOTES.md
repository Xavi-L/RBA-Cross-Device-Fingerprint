# F01：App 修改检出热图候选

2026-10-13 生成验收快照。仅新增本目录，供论文正文审阅；未替换旧 F01、图册或已通过的 overview，生成阶段未提交或推送。数据、字体、矢量、真实模板和实际视觉自检通过，详见 `CHECK.json`。以下 HEAD、源文件摘要和工作区状态记录的是生成验收时点。

## 图稿与设计

- 主文件：`F01_main.svg`（可编辑文字与矢量）、`F01_main.pdf`（嵌字矢量）、`F01_main.png`（2126 × 921 px，约 300 dpi）。图稿宽高为 180 × 78 mm；旧图为 180 × 135 mm，高度减少约 42.2%。
- 原 PDF `_WWW__Lower_Barriers__Greater_Threat_.pdf` 的第 5 页整页及上方 Figure 1 已实际打开查看。采用其衬线字体、清楚的层级和轻量边界语言；没有复制参考图的截图、图元、三角形或流程结构。下方 Figure 2 未作为设计参考。
- 项目基准是当前 `overview_triangle/style_full_v1/` 推荐稿，已先读其 `REVIEW_NOTES.md`。图内字体全部为实际核验的 Times New Roman；正文深灰、次级灰和边界灰沿用 overview。单一蓝色顺序色阶使用浅蓝 `#e9f0f9`、中间蓝 `#96afd8` 和由 overview 蓝色降低亮度得到的 `#4469a7`。
- 原 14 行、6 列及显示次序完整保留。仅 Full App 列名加粗；所有单元格采用相同的 0-100% 映射。0/9、6/9、9/9 均显示原计数，颜色的相对明度单调，最小文字/背景对比约 5.49:1。
- 去掉图内大标题和重复状态说明，保留紧凑色标。通过行高、两行列名和减少上下留白压缩；没有缩小文字、非等比拉伸或删行。边界为轻灰细线，内部为细白分隔；没有新增分组或装饰图元。

## 数据与只读范围

84 格以 `(scheme, configuration, identity)` 与 `configurations14.{csv,json}` 及原 `F01.csv` 逐项核对；`F01_plot_data.csv` 保存每格全部状态、原 ID、别名和来源行号，`ALIASES.json` 保留原有顺序与换行映射。SVG 和 PDF 中全部 84 个位置的文字都与绘图数据一致。

| 方法 | 从格子计算的 T/N | 受控正常报警 |
|---|---:|---:|
| Full App | 105/126 | 0/252 |
| No MTC alarm cap | 108/126 | 0/252 |
| App Web only | 96/126 | 0/252 |
| No memory relation | 96/126 | 0/252 |
| No timezone relation | 105/126 | 0/252 |
| Small App tree | 72/126 | 0/252 |

这些合计与原 `T02.csv`、`main.{csv,json}` 及 `all_stages` 的对应保存阶段一致。规则为 RETENTION，小树为 FITTED；主修改/受控正常记录的 U、FAILED、EMPTY_MODEL 均为零。此处 0/252 和零状态不推广到 MTC。没有把不同方法、模型或配置的输出当成新增独立样本。其余研究边界与 95 词正式英文图注见 `CAPTIONS.md`。

执行前本地 HEAD 为 `7622ae7ec77546b5d933e1b1f9f6c73deff73a88`，与用户提供的远程基线一致；本轮没有联网刷新远程。`SOURCE_MANIFEST.json` 记录开始时 220 条既有 Git 状态，以及 281 个指定源数据、旧图/图册、overview 和模板文件的摘要。执行后这些摘要及本目录外状态一致。没有运行任何采集、训练、规则选择、预测、计时或旧批量制图/实验汇总入口。

## 真实 ACM 模板实测

源工程为 `output/pdf/hybridguard_triangle_template_preview/`，隔离复制到本目录 `template_preview/`，保留真实 `acmart` 类及 `sigconf,anonymous,review` 选项。只在复制的图块中更换临时图引用、图注、无障碍说明并加入尺寸测量。图以 `width=\textwidth` 等比插入；主入口、类文件、章节、参考文献、字体配置和页边距字节不变。

| 项目 | 实测 |
|---|---:|
| textwidth | 506.295 TeX pt = 177.942 mm |
| textheight | 626 TeX pt = 220.014 mm |
| 实际插图宽 × 高 | 177.942 × 77.122 mm |
| 行标签、格内数字、图例字号 | 8.68616 PDF pt |
| 列名字号 | 8.96803 PDF pt |
| 英文图注词数 | 95 |
| 图注与模板内部间距 | 27.414 mm |
| 图 + 完整图注 + 内部间距 | 104.536 mm |
| 合计占 textheight | 47.5135% |
| 距 50% 上限余量 | 5.471 mm |

同一插入宽度下，overview 同级 28/29 单位正文的实测字号约 7.848/8.130 PDF pt；F01 的核心文字没有低于该下界。PDF 中文字可提取，字体嵌入且有 ToUnicode 映射；独立图和模板图页均无栅格图像，84 格也已按 PDF 空间位置核对。独立 PDF 的 179.917 × 77.978 mm 页面尺寸来自 Chrome 的页面单位取整；以上模板数字直接来自真实编译，而非 SVG 单位推算。

## 实际视觉检查

以下最终文件均已实际打开；不是只依据自动检查判定：

- 完整图 `F01_main.png`；实际模板宽度的正常屏幕预览 `previews/actual_template_width_96dpi.png`；灰度预览 `previews/grayscale_template_width_96dpi.png`。
- 实际 PDF 渲染 `previews/pdf_render_180dpi.png`；含完整英文图注及相邻正文的 ACM 第 7 页 `template_preview/figure_page.png`。
- 旧 F01 / 新 F01 同宽对照 `previews/old_new_same_width_96dpi.png`；当前 overview / 新 F01 同一论文尺度对照 `previews/overview_F01_same_width_96dpi.png`。所有面板都对应 177.942 mm，透明度正常，没有局部放大候选或缩小参考。

未见文字重叠、裁切、丢字、字体替换或乱码；零值、部分检出和满值在彩色及灰度下可读。行标签、列名和计数在 96 dpi 正常尺寸下可辨读，图注没有挤压邻接正文。首轮列名边界轻微相碰已通过增加行距修正，最终自动边界检查为零重叠。

## 边界与遗留项

没有未通过的本轮候选检查。保留原模板的 ACM reference-format 提醒，未为本任务改变模板配置；无 overfull、缺字、字体或未解析引用警告。96 dpi 预览遵循物理尺度换算，但未校准用户显示器，也未进行实物打印验收。

隔离模板沿用既有 overview 的浮动图槽位，仅用于验证版面；相邻历史正文及原图标签保留，不表示建议用 F01 替换正式 overview。现有预览工程共 17 页，本轮验证的是双栏正文中的单图占高，不是整篇八页终稿验收。F01 最终放置位置、编号及导师接受仍属后续论文整合；本轮按候选交付停止。

## 再生成

从仓库根目录运行这一个入口，仅输出本候选目录：

```sh
/Users/xavier/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B paper/figures/f01_app_detection/style_www_v1/build_candidate.py
```

依赖：bundled Python 的 pdfplumber、pypdf、Pillow；bundled Node 的 Playwright；本机 Chrome；Poppler；现有 TeX Live/latexmk。可用 `RBA_NODE`、`RBA_NODE_MODULES`、`RBA_CHROME` 指定同类本地依赖。`render_candidate.cjs` 只负责本图渲染与实际字体/边界检查；`check_candidate.py` 负责矢量检查、隔离模板编译、实测尺寸、预览和只读范围检查。

再生成会把 `CHECK.json` 中的视觉状态重置为 PENDING；新产物仍需实际打开复查，不能继承本次目视检查结论。所有数据断言从保存文件读取并计算，遇到冲突会报告键/字段并停止，不修补源结果。
