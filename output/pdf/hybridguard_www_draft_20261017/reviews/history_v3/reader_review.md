# 定稿审读：读者理解与主文自足性

日期：2026-10-22。状态：最终稳定版定稿审读完成，建议尚未应用。

审读版本：`build/matrix/HybridGuard_layout_v1_matrix.pdf`，共 10 页，主文 8 页。SHA-256：`4d49d439f85e67b11ef261b346caeadf4b90d7cb42ce45460d8fe16874e6b080`。下文页码均对应这份最终 v2 PDF。

**本报告仅提出修改候选，所有建议均未应用。摘要继续冻结。** 审读采用“熟悉计算机领域、不了解本项目”的读者视角，重点判断读者能否理解论点、方法和对照，而不是逐句替换写作风格。

## 总体评估

现有问题—方法—四个研究问题—结果—边界的叙事完整，暂未发现需要重写主结论的读者逻辑矛盾。建议本轮优先评估两处短定义：retention 中的 coverage/quality，以及 same-Web viewport 对照。二者均可用已有实现事实解释，不影响摘要、数值、实验或冻结图。

另外两项属于可选信息摆放，不应为了“更完整”把八页稿扩成实现手册。

| 编号 | 候选 | 建议 | 净新增英文词数 |
|---|---|---|---:|
| R1 | 给 semantic coverage 和 semantic quality 操作定义 | 优先澄清 | 42 |
| R2 | 定义 same-Web viewport 对照实际比较的量 | 优先澄清 | 30 |
| R3 | 用一句具体说明关联核验依据 | 可选补充 | 14 |
| R4 | 是否把最终模型概要放回主文 | 暂不搬完整规则清单 | 15 |

优先两项 R1/R2 合计净新增 72 词。词数按空白分隔估算，仅衡量建议文本的篇幅；实际落版需要在批准后重新编译。

## R1　给 semantic coverage 和 semantic quality 操作定义

**位置：** §3.4，第 4 页；附录 A.5，第 10 页；input_markdown/sections/03_method.md 第 45、47 行。

**优先级：** 优先澄清。**置信度：** 高。方法说明缺口；非结果错误。

原文：

> Additions must preserve training detections, increase semantic coverage, and satisfy the alarm and coverage constraints.

**可能的阅读障碍：** 前一段刚定义 definite-output coverage，后一段引入未定义的 semantic coverage；读者可能把二者当作同一指标，也可能把 semantic quality 当成条件准确率或证据可信度。实际实现的 coverage 按语义组与训练修改记录去重，quality 是预登记的观测/语义偏好。

**最小英文候选（未应用）：**

> Semantic coverage counts distinct (semantic group, modified training record) trigger pairs using the training detection weights, with groups assigned from field semantics. Semantic quality sums predefined preference scores for positive literals; these scores express observation preferences, not measured accuracy or independent evidence.

**放置方式：** 在 §3.4 retention 段第一句之后插入；后续约束句保持。

**取舍判断：** 建议本轮评估通过后优先补充。它解释已有算法，不增添能力或实验，主要解决方法自足性与三个 coverage/quality 术语的混淆。

**完整上下文复核：** 第 4 页紧接 definite-output coverage 定义后使用这两个术语；第 10 页附录虽给出排序顺序，仍未解释它们如何计算。故此项在最终版中仍成立。

**篇幅：** 候选 42 词，净增加 42 词。摘要、结果和实验均不变。

证据：

- [rba_review/repo_evidence/hybridguard_agent/research/rule_learning_v2/retention.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/rule_learning_v2/retention.py)，第 11–55, 58–64 行。
- [rba_review/repo_evidence/hybridguard_agent/research/rule_learning_v2/semantic_selection.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/rule_learning_v2/semantic_selection.py)，第 1–6, 63–70, 85–94, 144–147, 168–170 行。

## R2　定义 same-Web viewport 对照实际比较的量

**位置：** §3.4 首段，第 4 页；§5.2 Host container context 和 Table 4，第 7 页；input_markdown/sections/03_method.md 第 37 行。

**优先级：** 优先澄清。**置信度：** 高。主对照解释缺口；非数值错误。

原文：

> The App pool contains 50 base templates and three fixed relations: Native memory, Native timezone, and same-Web viewport.

**可能的阅读障碍：** Native memory、Native timezone、Host geometry 均有明确操作定义；same-Web viewport 却只出现名称与 0/6、0/66 结果。不了解代码的读者无法判断它与 Host 上界的差别，也容易把 Host 的 DPR×scale 换算误套到这个同 Web 对照上。

**最小英文候选（未应用）：**

> The same-Web comparator flags either visual-viewport dimension exceeding the corresponding window.innerWidth or window.innerHeight by more than 1 CSS pixel, using positive, same-probe observations when visual-viewport scale is at least one.

**放置方式：** 在 §3.4 首段第一句列出三个固定关系之后插入，或紧邻 §5.2 首次解释该对照时插入一次；不重复两处添加。

**取舍判断：** 建议本轮评估通过后优先补充。已核对实际实现：scale≥1 是门槛，比较双方均为 CSS 像素；不乘 scale，不用 DPR 或 Host。无需新公式、新图、新表或实验。

**完整上下文复核：** 第 7 页表格与 Host 段明确给出对照结果，但没有补充 same-Web 的操作定义；第 4 页也仅列名。此项确实影响读者理解比较对象，仍应优先。

**篇幅：** 候选 30 词，净增加 30 词。摘要、结果和实验均不变。

证据：

- [hybridguard_agent/research/mtc_screen_relations.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/mtc_screen_relations.py)，第 10–35, 77–121 行。
- [rba_review/repo_evidence/deliverables/app177_core_ablation_v1/CANDIDATES.json](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app177_core_ablation_v1/CANDIDATES.json)，第 3093–3139 行。
- [rba_review/repo_evidence/deliverables/screen_geometry_observation_v1/CONDITIONS_FROZEN.json](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/screen_geometry_observation_v1/CONDITIONS_FROZEN.json)，第 31–35 行。

## R3　用一句具体说明关联核验依据

**位置：** §3.1 第 1 段，第 2 页；相关 Figure 2，第 4 页；input_markdown/sections/03_method.md 第 5 行。

**优先级：** 可选补充。**置信度：** 中高。实现说明偏抽象；当前边界已清楚。

原文：

> Source records and receipts support these binding checks.

**可能的阅读障碍：** records、receipts 和 binding checks 都较抽象；读者能理解先关联再比较，但看不到核对哪些身份信息。正文和 Figure 2 已足够说明作用顺序、非原子采样和非硬件证明，因此不是当前论证成立的缺口。

**最小英文候选（未应用）：**

> App binding checks require matching record and session identities; paired inputs additionally cross-check pair identifiers, receipt identifiers, payload hashes, and collection batches.

**放置方式：** 若采纳，仅替换 §3.1 的这一句。

**取舍判断：** 可选；版面紧张时保留现文即可。不要为此添加接口表、协议流程或把回执描述为密码学签名证明。已有语义足够，新增句仅增强可核验的直观性。

**完整上下文复核：** 第 2 页关联段和第 4 页 Figure 2 已共同解释关联的作用与执行顺序，也明确不代表原子采样或硬件证明。现文足以支撑当前研究边界，故不升级为必改。

**篇幅：** 候选 22 词，替换原句 8 词，净增加 14 词。摘要、结果和实验均不变。

证据：

- [rba_review/repo_evidence/hybridguard_agent/research/mtc_relation_sources.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/mtc_relation_sources.py)，第 85–127 行。
- [rba_review/repo_evidence/deliverables/cross_endpoint_constrained_extension_v1/prepare_current.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/cross_endpoint_constrained_extension_v1/prepare_current.py)，第 10–30 行。

## R4　是否把最终模型概要放回主文

**位置：** §3.4 末尾，第 4 页；附录 A.5，第 10 页；相关引言第 1 页、结果第 7 页；input_markdown/supplement/00_Appendix_English.md 第 29 行。

**优先级：** 暂不搬完整规则清单。**置信度：** 中。可选的信息摆放选择。

原文：

> The resulting models have 6/6/5 clauses and complexity 12/12/10.

**可能的阅读障碍：** 主文讲了构造过程与最多八条的限制，实际最终规模和完整条件仅在附录。不过引言已交代 Native memory/timezone 被集成，结果说明了额外 height 条件的行为，附录 A.5 已完整列出模型；并不存在模型未记录的问题。

**最小英文候选（未应用）：**

> Final retention models contain six, six, and five clauses for configurations 01–03, respectively (Appendix A.5).

**放置方式：** 若作者希望让 compact detectors 更具体，可在 §3.4 末尾插入这一句；完整规则清单继续留在附录。

**取舍判断：** 不建议本轮将完整清单搬入主文：收益小于篇幅和术语负担。短规模句也不是必需，可待优先澄清项落版后再决定。

**完整上下文复核：** 第 1 页已有整合 memory/timezone 的贡献说明，第 7 页解释配置 01/02 与 03 的 height 条件差异，第 10 页给出完整清单与规模。读者可追溯模型，不存在需要补救的核心遗漏。

**篇幅：** 候选 15 词，净增加 15 词。摘要、结果和实验均不变。

证据：

- `input_markdown/supplement/00_Appendix_English.md`，第 29 行。
- `input_markdown/sections/01_introduction.md`，第 9 行。
- `input_markdown/sections/05_results.md`，第 46 行。

## 应保留、无需再改的内容

- 冻结摘要保持不变；已有贡献定位和结果层级不需要重写。
- 保留 Native/Host 非可信根、告警不等于恶意、无告警不等于真实性等边界；目前已足够，无需叠加新免责声明。
- 保留 main benchmark 九个差异与 memory specialist 十二个新增检测的分离说明。
- 保留 Host geometry 独立专项、未加入 Integrated App 的明确说明。
- 保留 refitted comparisons、historical development exposure、paired development-use 和 C1 无 timestamp gate 的限定。
- 保留 T/F/U 与 ALERT/NO ALERT/UNKNOWN 的显式映射；此前审读提过的问题已解决。
- 保留 Table 3 矩阵及总计，不需为了写作精简删掉分类信息。
- 未发现需要全稿语法润色或把现有主结论改写得更强的理由。

## 边界与下一步

本审读没有修改任何论文源文件、图注、表内文字或数字，也没有运行实验或编译 v2。最终 PDF 的完整相关上下文与页码已复核。仓库实现证据固定在提交 `d58e0680728f9adfdd5b550d00fd3f1674460b1e`；same-Web 的实际运算已核对，不能把 Host 的 DPR×scale 换算挪用到它身上。关联检查的候选句仅说明一致性核验，不宣称回执已提供密码学身份认证。

建议审批顺序：先评估 R1/R2；R3 按篇幅决定；R4 的完整规则迁移不建议采用。所有正文修改均需等待用户评估通过。

