# HybridGuard：表格可视化与紧凑版式


## 当前版本：2026-10-25 全量 LaTeX 重新编译

以 main 分支最新 main.tex 编译；保留已定稿图表，不运行历史迁移。
- 正文结束在第 8 页；全文 10 页。
- 当前 PDF 与 Overleaf ZIP 的所有 LaTeX、参考文献及图表源同步。
- 编译验证记录：qa/current_compilation_20261025.md。


## 当前版本：2026-10-25 定向正文精简与标题压缩

按确认方案完成八组正文去重与句式精简，正文减少约 185 个英文词；另缩短第 2.1、2.2、5.1、5.3 节标题。对应 Markdown 文本同步同一批改动。
- 保留摘要、结论、三张图、六张表、全部图表注释与实验数据。
- 保留第 3.4 节 0.005 系数说明、Host 容差定义和附录敏感性分析；不迁移其他正文到附录。
- 使用当前 `main.tex` 直接编译，不运行历史 Markdown 迁移。
- 最新正文终页、总页数及 PDF/ZIP 哈希以 `qa/current_compilation_20261025.md` 的编译结果为准。


## 精简前编译记录：2026-10-25 全量 LaTeX 重新编译

以 main 分支最新 main.tex 编译；保留已定稿图表，不运行历史迁移。
- 正文结束在第 9 页；全文 11 页。
- 当前 PDF 与 Overleaf ZIP 的所有 LaTeX、参考文献及图表源同步。
- 编译验证记录：qa/current_compilation_20261025.md。

## 当前版本：2026-10-24 正文去重

当前默认入口为 `main.tex`（`main_matrix.tex` 仍为兼容入口）。按用户确认的推荐方案完成五处去重：删除 §5.5 Synthesis、删除 §5.1 对表 3 的逐项复述及重复的重新拟合说明、精简 §4.3 核对过程、精简图 2 图注。相应 Markdown 输入已同步。

- 正文结束于第 8 页，参考文献从第 9 页开始，全文 10 页。
- 图 1/2/3 位于第 3/4/7 页；表 1–6 位于第 2/5/6/6/7/8 页。
- 摘要、方法正文、讨论、结论、三张图及六张表的数据与定稿内容保持一致。
- PDF、当前 LaTeX 和 Overleaf ZIP 对应同一版；ZIP 中的表 1 已同步为最新三列版。
- 本次编译与逐页检查记录见 `qa/deduplication_review_20261024.md`。
- 直接使用 `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` 编译，或使用 `source/build_pdf.py --variant matrix --no-migrate`；不要运行会重新生成历史图源的迁移流程。

以下记录保留各次历史调整的背景，页码以本节和本次核验记录为准。


更新：2026-10-22。本轮按用户要求改进六张表的视觉表达、压缩表内重复内容、将 Table 5 改为单栏，并将 Table 3 与 Figure 3 分开排版。已批准的 A1、A2、A3、B1 正文继续保留；B2 未应用。交付文件沿用原名，版本内容已更新。

**2026-10-23 合并版默认入口为 `main.tex`，与 `main_matrix.tex` 等价（两者都使用已验收的六表矩阵版），在 Overleaf 中选择 `main.tex`、pdfLaTeX。**

## 六张表的变化

| 表格 | 本轮处理 | 含义与保护范围 |
|---|---|---|
| Table 1 | 证据类型徽记、三行双列图例、短语化焦点列 | D/C/I/G/S/R 定义完整；不以叉号推断他人论文缺少能力；六篇/组引用与比较范围保持 |
| Table 2 | 合并 MTC/Specialist 材料组、Δ/N 简洁表头 | Δ=有效修改，N=正常记录；所有计数和开发使用等边界保持 |
| Table 3 | 六方法逐格显示检测符号与计数 | ✓全检出、半实心圆部分检出、×零检出；每原始 recipe 分母9，权重、非零差值和总量保持 |
| Table 4 | Memory/Timezone/Geometry 分组 | 检测符号与非零正常报警的三角符号分开；standalone/no-effect 等限定保留 |
| Table 5 | 单栏、cohort 分组、精确计数比例条 | T/F/U=报警/明确无报警/未知；深灰/浅灰/白；01/02等值并列而非汇总 |
| Table 6 | 简洁表头、检测符号、独立 normal 行 | 检测与正常报警不混用符号；开发材料限定保持 |

比例条由整数计数直接计算，不扩大微小段。全深灰条意味着该组正常记录全部报警。半实心圆是“部分检出”的类别标记，不表示50%。2026-10-23 合并中三张图换成当天经统一圆角验收的最新版 SVG，并逐一转成矢量 PDF；图注仍沿用已验收的科学说明文字，Table 3 与 Figure 3 分开。2026-10-24 试排：Figure 1 与 Figure 2 均使用 \textwidth 跨栏宽度，保留原 SVG/PDF 图内布局与比例，避免缩小图像造成的左右留白。

## 核验记录

当前 PDF 的页数、图表页码、哈希以及可见效果见 `reviews/final_read_assessment.md/json` 与同目录 HTML。当前版的审查记录与历史版分开保存。

| 文件 | 用途 |
|---|---|
| `reviews/final_read_assessment.md/json` | 表格改版结论、页码、最终 PDF 绑定 |
| `reviews/HybridGuard_final_read_assessment.html` | 可直接阅读的改版记录 |
| `qa/tables12_design.md` / `tables36_design.md` | 原表到新表的语义映射与设计说明 |
| `qa/tables_semantic_audit.md/json` | 六表数据、符号、限定、冻结正文与图的独立核验 |
| `qa/table_layout_check.md/json` | 编译、视觉与页数核验 |
| `qa/package_rebuild_check.md/json` | 独立解包后重新迁移和编译的核验 |
| `qa/package_manifest.json` | 当前 ZIP 文件与哈希清单 |

A1/A2/A3/B1 的上一轮落实记录已归档于 `reviews/history_v3/` 与 `qa/history_v3/`；其中历史页码和 PDF 哈希只对应当时版本。

## 内容保护

- 摘要保持提交过的257词、三段原文，冻结文本见 `baseline_source/abstract_verbatim.txt`。
- 三张图的 SVG/PDF/PNG 共九份资产与 `figures/FROZEN.json` 一致。
- `input_markdown/` 正文、九份聚合 CSV、十五条参考文献和批准事实记录均与上一轮一致。
- 只改表格短标签、表注和表现形式，不更改任何实验数字、含义或结论。
- 沿用 ACM 正文与表体字体、字号、行距及页边距。新表注采用统一的表注字号。
- 没有新增采集、拟合、预测或实验；没有新增伦理批准、机构豁免或匿名制品入口声明。

## 本地编译

已生成的 LaTeX、表格、冻结图、模板和参考文献均包含在包内，直接编译不需要 Python/Pandoc：

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

也可使用包内脚本：

```bash
python3 source/build_pdf.py --variant matrix --no-migrate
```

从已批准的 Markdown 重新生成章节和图注（需额外安装 Pandoc）：

```bash
python3 source/build_pdf.py --variant matrix
```

需要 TeX Live/MiKTeX、pdfLaTeX、BibTeX、latexmk、TikZ，以及 ACM 模板的 Libertine、newtx、Inconsolata 等依赖。共享视觉符号在 `table_visuals.tex`，直接使用 LaTeX 矢量路径，不依赖外部位图。

默认迁移覆盖 `frontmatter.tex`、`sections/*.tex` 与 `floats/*.tex`，保持独立维护的 `tables/*.tex` 不动。直接编辑正文 LaTeX 后请用 `--no-migrate` 或同步修改对应 Markdown。**2026-10-23 修复：** `main.tex` 不再使用旧总计表，而是与 `main_matrix.tex` 同用本轮已验收的六表矩阵版。原 `tables/table_03.tex` 仅保留作历史记录，不参与默认 PDF 编译。

## 来源与范围

原稿来源固定为仓库 `Xavi-L/RBA-Cross-Device-Fingerprint` 提交 `d58e0680728f9adfdd5b550d00fd3f1674460b1e` 的 `output/pdf/hybridguard_www_draft_20261017/`。本包在已落实 A1/A2/A3/B1 的版本上继续处理用户批准的表格与版式改进。

这是可编辑论文工作包，包含内部核对记录；它不等于匿名实验制品包，也不表示已经提交投稿平台。ZIP 不含采集原始归档、完整研究仓库、编译缓存或逐页渲染图片。


## 2026-10-23 修复版（表格恢复 + 最新三图）

- 采用 2026-10-22 完整表格定稿，不重画表格、不修改任何数据单元格、图例、统计口径和六张表注。完整逐项矩阵保存在 `tables/table_03_matrix.tex`。
- **默认 `main.tex` 及兼容 `main_matrix.tex` 均编译出正确六表矩阵版**；不再默认选择旧的 Table 3 总计表。
- 三张 SVG 原样取自 GitHub commit `a9122a085307e3a9aaf452c53c6dbc4915d49439`，仓库对应资源为
  - 图 1：`paper/figures/overview/style_preserving_v4_20261023/HybridGuard_Fig1_surfaces_v4.svg`
  - 图 2：`paper/figures/system_design/semantic_vector_v1_20261023/HybridGuard_Fig2_semantic_v1.svg`
  - 图 3：`paper/figures/fig3_mechanisms/HybridGuard_Fig3_mechanisms_v3.svg` （非 f03a）。
- 已核对 SVG 与 Git 对象的 SHA；PDF 由 SVG 矢量导出。
- 本地 PDF 10 页，正文 8 页，参考文献与附录 2 页。图 1、2、3 依次位于第 3、4、7 页；Table 1–6 依次位于第 3、5、6、6、7、8 页。
- 源码重编请使用 `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`，**不要先运行带迁移功能的生成脚本**，它会重写已经升级的图注/引用文件。
- 本交付是当前对话的修复版文件，未自动覆盖 Github 主分支上的旧 PDF。
