# F05a：已接受跨端时区检查的分方向检出增量

2026-10-13。唯一候选为 `F05a_main.svg/pdf/png`，是 F01、F03a/F04 之后的第三张正文数据图候选；F05a 仍是来源素材编号，不是最终论文图号。开始及完成时本地 HEAD 均为 `cb367ccd8e9d36d430e28a72f87fde9e0bb0a948`，与用户给出的远程基线相同；本轮未重新联网核验远程引用。暂存区为空，未提交或推送。

## 单栏设计与读法

从 86 mm 成品宽度直接布局，名义高度 40.3 mm；没有先画通栏大图再缩成单栏。四行依次为 App language、App timezone、Browser language、Browser timezone，顺序未变。四行共用一个 0–100% 的 Detection rate (%) 横轴，只标 0、50、100。

- Full App：灰色 `#737A80` 空心圆，始终在行内上方。
- App + C1：灰绿色 `#5B8574` 实心方块，始终在行内下方。
- 颜色、形状和实心/空心均编码**方法**；与前一张机制图按“修改/正常记录”编码的含义不同，图例明确写 Full App、App + C1。
- 每个标记旁均有深灰 `#343434` T/N，8 个点对应 8 份计数。行内上下偏移为 ±1.75 mm，横坐标严格为 T/N×100，无水平抖动、数据连线或增量箭头。
- 0% 与 100% 的计数朝绘图区内部排，零值符号保持完整大小。三组相同结果仍显示两个方法。Browser timezone 的 0/5 与 5/5 正常并列呈现，没有额外高亮。
- 正常 0/46 放在正式图注，避免占用第五行或被误读为 0% 检出；没有把正常结果省略。

图内没有大标题、F05a 编号、总分副图、大色带、背景框、colorbar 或误差条。全部图内文字采用实际 Times New Roman 正体，源字号统一为 31 单位，没有压扁文字。行距 7 mm，数字与两种方法的间距保持一致。

实际打开参考论文第 5 页 Figure 1 和第 6 页 Table 1，借鉴白底、细线、紧凑结构与清楚层级；未复制图像或图元。已接受 F01 按其当前说明使用 rev4，未使用早期蓝色热图。overview、F01 和 F03a/F04 仅作为只读风格参考。

## 数据及方法核对

原 `F05a.csv` 全部 30 行均读取：2 方法 × 3 配置 × 5 组，无重复或遗漏。按 `pilot18`、`b2b42` 精确筛选 `members.jsonl` 与 `inputs.jsonl`，得到 18 + 42 = 60 个配对评价位置，其中 14 修改、46 正常。没有加入 `resource54` 或其他批次。

三配置分别通过 `tables.json /models` 的 fold、实际 `base_model_id` 和 App 模型身份，对照原已接受 `models.json`。三者均为 RETENTION Full App 加仅有 C1 的已接受扩展；资源归档保留的是 S0 基础方法，不是资源增强结果。图中两方法的身份为：

| 图中短名 | 保存方法 | 读取的保存字段 |
|---|---|---|
| Full App | APP_FULL | app_states[实际配对基础模型 ID] |
| App + C1 | PAIRED_BASE | base_states[同一实际配对基础模型 ID] |

01/02/03 没有直接充当内部模型 ID。Full App 内部仍包含 Native–App Web 参照，只是不使用独立 Browser 输入。App + C1 不是 Browser-only、C1+C2、资源方法、小树、自动回退或动态切换。

每行 F05a 的输入行号与成员行号均核对到所筛选的保存组；在内存中按来源键连接两个文件，未导出来源成员 ID。按实际模型键统计保存 T/F/U/FAILED，逐项核对 N/T/F/U/FAILED/defined 和原比例；没有重新运行 App、C1 或组合推理。六条 `tables.json /paired` 的 App/Browser/NORMAL 汇总另行交叉核对通过。

| 修改类型 | Full App | App + C1 |
|---|---:|---:|
| App language | 0/2 | 0/2 |
| App timezone | 2/2 | 2/2 |
| Browser language | 0/5 | 0/5 |
| Browser timezone | 0/5 | 5/5 |

三个冻结配置的 10 个方法/组组合均满足全部状态计数一致，才压缩展示共同计数。修改总计核对为 2/14 与 7/14；正常两方法均为 T/F/U/FAILED = 0/46/0/0。展示批次的 U、FAILED 均为零。验收矩阵仅作为断言，实际绘图记录来自保存状态的统计。

5/5 没有变成 15/15，60 没有变成 180 个独立样本；不宣称逐条输出相同、独立重复、显著性或泛化。新增检出只发生在所测 Browser 时区修改，App 时区 2/2 保留，两类语言修改仍漏检。0/46 不替代广机型正常报警/缺测代价。该批次有开发接触历史，不是新盲测；不能与 F01 的 105/126 合成升级前后总性能。

`data/` 包含 30 行原 CSV 结果、30 行规范化状态、8 行绘图记录、6 行正常状态、60 行最小来源行定位、三配置实际模型映射、10 组压缩依据、六条统一汇总核对以及逐组来源映射。对九个数据文件做了限定的导出检查：没有复制原始指纹、会话 ID、回执或来源成员关联 ID；只保留必要文件、行号、方法/配置模型身份和计数。

## 实测单栏尺寸与图注预算

| 项目 | 最终实测 |
|---|---:|
| SVG 名义宽 × 高 | 86 × 40.3 mm |
| PDF MediaBox 宽 × 高 | 86.106 × 40.217 mm |
| PNG（名义 300 dpi） | 1016 × 476 px |
| ACM columnwidth / linewidth | 84.754 mm |
| ACM textwidth | 177.942 mm |
| ACM textheight，即一栏正文高度 | 220.014 mm |
| 实际插图宽 × 高 | **84.754 × 39.586 mm** |
| 图内全部实际字号 | **8.64488 PDF pt** |
| 图注与内部间距 | 35.146 mm |
| 图 + 正式图注 + 内部间距 | **74.732 mm** |
| 占一栏正文高度 | **33.9671%** |
| 英文正式图注 | **62 词** |

33.9671% 是占**一栏正文高度**的比例，不是占整页面积的比例。实际栏宽由原 ACM 模板决定，没有将约 85–86 mm 的设计参考值写成虚构实测值。PDF 与名义尺寸存在 Chrome 页面单位取整差异，实际字号和插图尺寸均从输出 PDF/模板测得。

首次 75 词图注配 41.6 mm 图体时总占高为 83.881 mm。最终将正式图注收紧至 62 词，并去除少量顶部、类别间及轴周围留白；源字号始终为 31，方法标记间距始终为 3.5 mm，没有缩小字体。最终图体约 40 mm，总高进入 75 mm 目标。

**取舍明确保留：** 62 词低于建议的 75–95 词区间，该偏好项记为 false；没有把它写成全部偏好均达标。正式图注仍包含两方法及 C1 身份、检出率与 T/N、60/14/46、Browser 时区增量与语言遗漏、三配置共同汇总且不并分母、正常 0/46、已有开发而非新盲测，以及广机型正常代价另报。App 时区保留在图面与详细说明中清楚呈现。

## 真实模板检查

隔离副本来自仓库既有 `output/pdf/hybridguard_triangle_template_preview/`。保留原 `sigconf,anonymous,review`、class、字体、页边距、caption 样式和正文，仅在候选副本的临时图槽中使用 `figure`（非 `figure*`）、`width=\linewidth`、新图、新图注及测量代码。其余复制源码逐文件直接比对相同。没有负 vspace、缩小 caption、失真高度或图页裁切。

最终隔离工程为 16 页，图位于第 6 页左栏，完整图页保留正式图注及相邻正文。模板显示 Figure 1 是临时工程自动计数，不是本轮指定的最终图号。候选的可移植 `F05a_figure.tex` 使用独立 label `fig:paired-timezone-gain`；临时槽额外保留旧 label alias，使复制正文的既有引用不失效。模板整页是排版检查，不将未改的旧正文改称对本图的正式解读，也不代表完成整篇八页终稿。

模板无 overfull、缺字、字体回退或未解析引用；保留原 class 的 ACM reference-format 提醒。独立 PDF 全部文字位于页面边界内，未裁切字形。

## 自动验收与实际视觉验收

自动检查通过：保存数据/模型身份、三配置压缩条件、8 点/8 计数、严格横坐标、统一上下偏移、18 个可编辑文字节点、无重叠或越界、实际 TimesNewRomanPSMT、PDF 嵌字/ToUnicode/可提取文本和逐点空间计数。独立 PDF 与模板图页均无栅格图像；PDF 没有依赖外部链接或目的地。未复制系统字体文件。

实际打开并查看了以下最终六项，视觉状态单独记为 PASS：

1. `F05a_main.png`：完整图的四行、两方法和 8 份计数清楚，语言零值未省略。
2. `previews/actual_column_width_96dpi.png`：真实单栏对应 320 px 宽；行标签、图例和计数在此尺度下可读。
3. `previews/grayscale_column_width_96dpi.png`：空心圆/实心方块仍可分，零值符号完整。
4. `previews/pdf_render_180dpi.png`：实际矢量 PDF 渲染，端点及轴文字没有裁切。
5. `template_preview/figure_page.png`：整页检查正式图注、相邻正文和单栏布局。
6. `previews/accepted_figures_same_physical_scale_96dpi.png`：本图按 84.754 mm / 320 px，已接受 F01、F03a/F04、overview 按 177.942 mm / 673 px。它们保持相同物理比例，没有将本单栏图放大成与通栏图同宽。

未验证：实物打印、显示器物理尺寸校准、用户主观审美认可、整篇八页终稿。96 dpi 是输出约定，不是显示器校准结果。

## 保护与复现

首建基线保存在 `SOURCE_MANIFEST.json`。本轮开始与完成时的 699 个受保护图稿、图册、源数据/模型/结果和原模板文件的大小及修改时间相同，包括 overview、F01 全版本、F03a/F04、原 F05a 与原图册。目录外原有 240 条 Git 状态一致，HEAD 与暂存区未变。没有执行采集、训练、规则选择、预测、计时或旧实验汇总器；没有更新正式论文、图册或候选清单。

```sh
/Users/xavier/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B paper/figures/f05a_cross_endpoint/style_www_v1/build_candidate.py
```

依赖 Codex bundled Python/Node、Playwright、本机 Chrome、Times New Roman、TeX Live/latexmk 与 Poppler。仅生成本目录候选。首次生成需要预先保存的 `--baseline`，以后从本目录历史 manifest 读取受保护路径，并在每次生成前重新捕获当前 HEAD/暂存区/文件状态；不会要求未来 HEAD 等于首次 HEAD。时间戳以字符串跨 Python/Node 保存，避免纳秒精度损失。

隔离模板用 `latexmk -gg` 从头重建本目录副本，避免交付日志与已清理辅助文件形成不完整缓存。重建后自动检查与视觉检查分开：视觉状态会重置为 PENDING，须重新打开最终预览，不能自动复用本次 PASS。字体/编译器不可用时直接报错，不静默回退。
