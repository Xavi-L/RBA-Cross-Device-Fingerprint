# ACM 草稿编译与版式验证记录

## 当前修订范围

本版本在此前 Full Prose 草稿基础上完成 evaluation 口径校正，明确拆分两条当前 App177 controlled evaluation track：

- attack-side 100-run stability campaign；
- main-repository 69-pair baseline -> attack-active re-evaluation。

摘要、Introduction、Evaluation Methodology、Current App177 Results、Discussion、Conclusion 和内部 evidence ledger 均已同步更新。Browser67/paired244 检测增量仍保持未来工作边界。

## 编译结果

- Main source：`hybridguard_draft.tex`
- Document class：`acmart`, `sigconf, anonymous, review`
- Output PDF：`HybridGuard_ACM_Draft_TwoTrack_20260903.pdf`
- Page count：18
- Undefined citations：0
- Undefined cross-references：0
- Overfull horizontal boxes：0
- 检测到 1 个约 1.47 pt 的 overfull vertical box；逐页渲染未观察到文字裁切、重叠或越界。
- Ghostscript null-device parse：status 0
- PDF：可打开、未加密、非扫描件

## PDF 视觉检查

PDF 按 150 dpi 全页渲染。重点检查了：

- 标题与摘要中的 two-track 定义；
- Evaluation Methodology 的双轨对照表；
- attack-side 100-run 结果表；
- main-repository 69-pair 结果表；
- cross-track coverage difference 解释；
- Discussion 中 evaluator versioning；
- Conclusion；
- evidence ledger。

未观察到破损 glyph、裁切、表格越界或列间重叠。

## 当前 Overleaf ZIP

`HybridGuard_ACM_Draft_Flattened_Overleaf_20260903.zip` 包含：

- `hybridguard_draft.tex`；
- `references.bib`；
- `README.md`。

章节与附录均已内联，不依赖外部 `\\input{...}` 文件；`acmart.cls` 与 `ACM-Reference-Format.bst` 由 Overleaf/TeX Live 提供。

该 ZIP 已重新解压并使用 pdfLaTeX + BibTeX 编译验证，得到 18 页 PDF，未解析 citation/reference 为 0。

## 完整性信息

- ZIP size：39,656 bytes
- ZIP SHA-256：`6971539f0a911ff0b2e082ece30c96ba20ef5b90b7db22942bdf848a095cf83e`
- PDF size：546,380 bytes
- PDF SHA-256：`378c6ee166b6d8d26aee1047b6752cc2383e8a2b077bbbd1a3b4ffa4c847e838`

## 当前研究边界

编译通过只证明 LaTeX 工程和版式可用，不提升实验结论等级。当前统一口径为：100-run 与 69-pair 是两个不可互换的 controlled track；它们使用不同统计单位和 evaluator 版本；headline counts 分别报告，不合并为 recall。229-record normal screen 不是 release-matched benign cohort；Browser67/paired244 detection gain 仍属于未来实验。
