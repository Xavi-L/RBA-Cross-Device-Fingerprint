# HybridGuard 论文工作包（2026-09-03）

本目录集中保存从论文结构梳理、主张边界审查、文献筛选与精读，到 ACM 英文草稿生成过程中形成的可复用材料。它是**论文写作工作区和阶段性快照**，不是当前系统实现、正式数据集或最终投稿成品。

## 当前主草稿

`draft/HybridGuard_ACM_Draft_Flattened_Overleaf_20260903.zip` 是本目录的主草稿工程。它使用 ACM 模板，并已将原提纲式章节改写为连续英文正文；图片和表格仍保留为后续工作。为控制 Git 仓库体积，该 ZIP 不包含编译 PDF，也不重复打包 Overleaf/TeX Live 已内置的 `acmart.cls` 与 `ACM-Reference-Format.bst`。工程已将各章节和附录内联到 `hybridguard_draft.tex`，上传 Overleaf 后将该文件设为 Main document 即可。

后续曾生成一个重点重写 Introduction / Related Work 的较短实验分支，但其余章节仍较接近骨架，因此未作为本工作包的主工程保存。相关文献精读成果已经以独立文档纳入 `literature/`。

## 已冻结的写作口径

- 当前受控攻击验证对象是 App177，即 Android Native、WebView Host 与 App 内 Web Runtime。
- 当前实验协议只使用 `baseline -> attack_active` 两态比较。
- 现有 51/69 与 33/69 是冻结受控配置上的无报警到报警转换计数，不表述为攻击召回率。
- Browser67 与 paired244 的采集、配对、来源审计和缺失留存链路已经实现；其检测增量需要在获得足量完整配对数据后重新实验。
- 历史 grouped CV、teacher-label、RF/MLP、LLM/RAG、融合与端侧实验可以暂时写入不限篇幅草稿，但正式投稿前需要重新决定保留范围。
- 当前草稿不设置投稿页数限制。

## 目录说明

### `planning/`

保存论文范围、主张—证据矩阵、两名作者及两个仓库的成果边界，以及进入正式评估前仍需完成的准入条件。

### `literature/`

保存候选文献筛选结果、核心与支撑性参考文献、十篇直接近邻工作的精读材料，以及 Related Work 的定位差异。

### `writing/`

保存摘要、贡献和结果措辞的安全边界，以及阶段性写作说明。

### `draft/`

保存主 ACM 草稿 source-only 工程 ZIP 和编译验证记录。

## 使用原则

1. 任何实验数字进入摘要或贡献列表前，都应回查 `planning/claim_evidence_matrix.md` 和 `writing/draft_claim_language.md`。
2. 引用文献前，优先查看 `literature/P0_literature_deep_reading.md`，避免对仅完成摘要级复核的工作复述未经确认的细节。
3. 新的 Browser67/paired244 实验完成后，应版本化更新本目录，而不是覆盖该阶段快照。
4. `MANIFEST.md` 记录主草稿 ZIP 的 SHA-256、大小和目录清单，用于完整性核对。
