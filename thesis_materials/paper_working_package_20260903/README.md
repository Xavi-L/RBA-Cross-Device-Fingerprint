# HybridGuard 论文工作包（2026-09-03）

本目录集中保存从论文结构梳理、主张边界审查、文献筛选与精读，到 ACM 英文草稿生成过程中形成的可复用材料。它是**论文写作工作区和阶段性快照**，不是当前系统实现、正式数据集或最终投稿成品。

## 当前主草稿

`draft/HybridGuard_ACM_Draft_Flattened_Overleaf_20260903.zip` 是当前主草稿工程；`draft/HybridGuard_ACM_Draft_TwoTrack_20260903.pdf` 是对应的编译 PDF。当前版本已将二作攻击侧实验与主仓重评明确拆成两条互补、不可混算的 App177 evaluation track：

1. **attack-side stability campaign**：100 个 effect-positive active runs，使用攻击侧 frozen evaluator，主要回答攻击效果是否稳定复现以及攻击侧规则是否响应；
2. **main-repository paired re-evaluation**：69 个 qualified `baseline -> attack_active` pairs，使用主仓两套 frozen evaluator catalog，主要回答 matched pair 是否出现无报警到报警转换。

两条轨道的统计单位、纳入规则和 evaluator 版本不同，因此 `70/100`、`51/69`、`33/69` 分别报告，不合并成一个 detection rate，也不直接比较为同一个 recall 指标。

ZIP 使用 ACM 模板，并已将 section 和 appendix 内联到单一 `hybridguard_draft.tex`。为控制仓库体积，它不重复打包 Overleaf/TeX Live 已提供的 `acmart.cls` 与 `ACM-Reference-Format.bst`。上传 Overleaf 后将 `hybridguard_draft.tex` 设为 Main document 即可。

## 已冻结的写作口径

- 当前受控攻击验证对象是 App177，即 Android Native、WebView Host 与 App 内 Web Runtime。
- 当前论文同时保留 attack-side 100-run stability track 与 main-repository 69-pair paired track，但两者不混算。
- main-repository pair track 只使用 `baseline -> attack_active` 两态比较；源数据中的历史 post 状态不进入该分母。
- `70/100` 是 attack-side frozen evaluator 在 effect-positive active runs 上的 formal-response count。
- `51/69` 与 `33/69` 是主仓两套 frozen evaluator 在 qualified pairs 上的无报警到报警转换计数。
- 上述数字均不表述为 population recall、FPR、accuracy 或 production RBA performance。
- 229 条 main-repository normal-input records 是独立 calibration screen，不是 release-matched benign cohort。
- Browser67 与 paired244 的采集、配对、来源审计和缺失留存链路已经实现；其检测增量需要在获得足量完整配对数据后重新实验。
- 历史 grouped CV、teacher-label、RF/MLP、LLM/RAG、融合与端侧实验可以暂时写入不限篇幅草稿，但正式投稿前需要重新决定保留范围。
- 当前草稿不设置投稿页数限制。

## 目录说明

### `planning/`

保存论文范围、主张—证据矩阵、两名作者及两个仓库的成果边界、两条 evaluation track 的口径对齐，以及进入正式评估前仍需完成的准入条件。

### `literature/`

保存候选文献筛选结果、核心与支撑性参考文献、十篇直接近邻工作的精读材料，以及 Related Work 的定位差异。

### `writing/`

保存摘要、贡献和结果措辞的安全边界，以及阶段性写作说明。

### `draft/`

保存主 ACM 草稿 source-only 工程 ZIP、对应编译 PDF 和编译验证记录。

## 使用原则

1. 任何实验数字进入摘要或贡献列表前，都应回查 `planning/claim_evidence_matrix.md`、`planning/evaluation_track_reconciliation.md` 和 `writing/draft_claim_language.md`。
2. 不使用笼统的 “HybridGuard rules detected ...” 来混指不同 evaluator；应显式写 `attack-side frozen evaluator` 或 `main-repository evaluator`。
3. 引用文献前，优先查看 `literature/P0_literature_deep_reading.md`，避免对仅完成摘要级复核的工作复述未经确认的细节。
4. 新的 Browser67/paired244 实验完成后，应版本化更新本目录，而不是将当前 App177 结果静默替换。
5. `MANIFEST.md` 记录主草稿 ZIP/PDF 的 SHA-256、大小和目录清单，用于完整性核对。
