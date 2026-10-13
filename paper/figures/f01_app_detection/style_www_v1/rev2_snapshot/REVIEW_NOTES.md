# F01 rev2：紧凑表格化结果矩阵

2026-10-13。当前唯一候选为 `F01_main_rev2.svg/pdf/png`。基于已提交的 rev1（`163e409005be323f44470c9eebcdde4a993ec584`）进行本轮指定的降尺寸与去热图化修订。旧图稿、旧脚本和旧模板预览保留；旧版三个审阅文档的原样副本在 `rev1_snapshot/`。下文及 `CHECK.json` 的 Git 状态记录对应生成验收时点（提交前）。

## 本轮视觉修改

已实际查看根目录 `_WWW__Lower_Barriers__Greater_Threat_.pdf` 第 6 页整页及 Table 1 放大图。参考其白底、衬线文字、紧凑行距和横向规则线的表格阅读方式；没有复制表中数据、截图、分类或红绿强调。

- 主体为原顺序的 14 × 6 表格矩阵，每格保留 T/9。白底、深灰数字 `#343434`、仅三条细横线；无竖线、行分组、装饰或附图。
- 80 格为白色；仅四个 6/9 使用极浅蓝 `#eef3fa`。9/9 和 0/9 均为白底。浅色表示“部分检出”，不表示较大计数，也不是连续色阶。着色格占 4/84，着色面积约占整图 2.74%。数字是完整的信息载体。
- 取消渐变、colorbar 和图内图例，编码说明收进图注。Full App 仅列名加粗，不染整列。
- 顶部一行短标题。方法名最多两行；14 个配置名统一单行左对齐。行距从 4.2 mm 减为 3.5 mm，减少底部色条与留白。图内核心文字保留 31 SVG 单位，实际模板字号仍为 8.68616 PDF pt。
- 没有新增 summary row，以保持高度和表格清晰度。六方法总数依原顺序为 **105/126、108/126、96/126、96/126、105/126、72/126**，在 `CAPTIONS.md` 的独立事实段中保留。正式英文图注从 95 词压到 71 词。

## 新旧实际占高

两版采用相同真实 `acmart` 工程、`sigconf,anonymous,review` 选项与 `width=\textwidth` 等比插入。未修改模板字体、页边距、caption 字号或浮动间距，也没有裁图或非等比拉伸。

| 项目 | 已提交 rev1 | 当前 rev2 | 变化 |
|---|---:|---:|---:|
| SVG 标称宽 × 高 | 180 × 78 mm | 180 × 62.5 mm | 高度 −19.87% |
| 实际模板插入宽度 | 177.942 mm | 177.942 mm | 相同 |
| 实际插图占高 | 77.122 mm | 61.798 mm | −19.87% |
| 正式英文图注词数 | 95 | 71 | −24 词 |
| 图注及模板内部间距 | 27.414 mm | 23.548 mm | −3.866 mm |
| 图 + 完整图注 + 内部间距 | 104.536 mm | 85.346 mm | −19.190 mm / −18.36% |
| 合计占正文高度 | 47.513% | 38.791% | −8.722 个百分点 |
| 行标签和数字实际字号 | 8.68616 PDF pt | 8.68616 PDF pt | 不变 |
| 列名实际字号 | 8.96803 PDF pt | 8.68616 PDF pt | 统一为正文字号 |

正文区为 506.295 × 626 TeX pt，即 177.942 × 220.014 mm。占高测量来自编译时的实际图盒与浮动盒，合计包括完整图注和内部间距，不包括两版相同的外部浮动间距。

独立 PDF 页面实际为 179.917 × 62.484 mm（Chrome 页面单位取整）；SVG 为精确 180 × 62.5 mm。PNG 为 2126 × 738 px，300 dpi。上表模板值来自实际编译，不是仅从 SVG 高宽比例推算。

上一版主要问题是蓝色大面积填充占据视觉中心、连续色标对三种离散值没有必要，以及图与图注接近半页。新版将信息重心移回数字，取消色条，减少行距和冗长说明，在核心字号不变的条件下减少约 19.2 mm 总占高。

## 数据与研究口径

直接复用未改动的 `F01_plot_data.csv` 与 `ALIASES.json`；没有调用原批量制图、实验汇总、采集、拟合、规则选择、预测或计时入口。rev1 已完成的 CSV/JSON/阶段核对保存在 `rev1_snapshot/CHECK.json`；本轮只核对原有 84 格、显示顺序及与既有总数的算术一致性，不重新评价研究结果。

14 行、6 方法、全部原始 ID 和分母保持不变，不作语义分组或成绩排序。Webdriver only 和 WebGL vendor / renderer 的全行 0/9、Full App 对 Screen metrics 的 6/9 保留。T/F/U/FAILED/EMPTY_MODEL/defined 等字段仍在原 CSV 中。规则方法 RETENTION、小树 FITTED、受控正常记录与历史 MTC 的边界及正常记录代价均保留在 `CAPTIONS.md`。不能仅凭本矩阵认定取消 MTC alarm cap 更优；这是有开发使用历史的保存评价，不是新实验或盲测。

## 真实模板及视觉验收

`template_preview_rev2/` 是 `output/pdf/hybridguard_triangle_template_preview/` 的隔离副本，只在复制的 figure 块替换图引用、图注、无障碍说明并加入测量。主入口、类文件、章节、参考文献和模板设置保持原样。使用既有 overview 的浮动槽位仅供排版测试，不表示替换正式 overview；相邻历史正文未作研究结论验收。

已实际打开并检查以下最终渲染：

- `F01_main_rev2.png`：完整输出。
- `previews_rev2/actual_template_width_96dpi.png` 与 `grayscale_template_width_96dpi.png`：673 px 对应 177.942 mm 的正常尺寸预览；数字和标签可读，灰度下不依赖浅色识别数值。
- `previews_rev2/pdf_render_180dpi.png`：最终矢量 PDF 的实际渲染。
- `template_preview_rev2/figure_page.png`：第 7 页的完整图、71 词正式图注及相邻正文。
- `previews_rev2/rev1_rev2_same_width_96dpi.png`：rev1/rev2 等宽、不改变透明度的对比。
- `previews_rev2/overview_F01_same_width_96dpi.png`：与当前通过版 overview 同一论文宽度的字体和整体气质比较；没有套用其大框组或流程逻辑。

数字没有拥挤或遮挡，标签无裁切、错行和异常换行；三条细规则线清楚。浏览器检查 111 个文字节点无重叠、越界或字体回退。浏览器行度量框在紧凑行之间相接，但实际数字墨迹距离格边最少 7 px（300 dpi）；PDF 字符度量框也完整位于对应行内。84 格均经过 SVG 文字、PDF 提取文字和 PDF 空间位置核对。

实际使用 Times New Roman 正体/粗体，与通过版 overview 一致；PDF 字体已嵌入并带 ToUnicode，独立 PDF 及模板图页均无栅格图像。可编辑 SVG 保留文字与矢量。自动验收和上述直接视觉检查均通过，详见 `CHECK.json`。

76 个指定的 rev1 图稿/脚本/预览、已通过 overview、源数据、参考及模板文件保持不变；目录外 220 条原有 Git 状态保持一致。旧版五个未跟踪的 TeX 中间文件也保留。没有改动其他图、正式 overview 或源评价。

## 遗留边界

没有未通过的本轮版式检查。仍保留原模板的 ACM reference-format 提醒；没有 overfull、缺字、字体回退或未解析引用。96 dpi 屏幕预览未做显示器物理校准，也没有实物打印验收。现有真实预览工程共 17 页：已验证本图在双栏正文中的插入效果和占高，未完成整篇 8 页终稿的排版验收。

## 复现

从仓库根目录运行：

```sh
/Users/xavier/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B paper/figures/f01_app_detection/style_www_v1/build_rev2.py
```

`build_rev2.py` 只读取原 CSV/映射并生成 rev2；`render_rev2.cjs` 导出并核验实际字体/边界；`check_rev2.py` 核验矢量、空间数据、模板占高并生成预览。依赖与 rev1 相同：bundled Python 的 pdfplumber/pypdf/Pillow、bundled Node 的 Playwright、本地 Chrome、Poppler、TeX Live/latexmk。可用 RBA_NODE/RBA_NODE_MODULES/RBA_CHROME 指定同类本地依赖。

再生成会将当前 `CHECK.json` 的视觉状态重置为 PENDING；新渲染必须重新打开检查。复现入口不覆盖 rev1 文件，旧版审阅信息保存在 `rev1_snapshot/`，本轮只交付这一版后停止。
