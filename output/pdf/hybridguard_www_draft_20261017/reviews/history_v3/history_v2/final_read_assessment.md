<div class="eyebrow">HYBRIDGUARD · FINAL READ · 2026-10-22</div>

# 版式已微调，正文修改待评估

<div class="status">版式完成 · 8 页主文 / 10 页全文 · 正文修改 0 项 · 建议尚未应用</div>

本报告基于本轮稳定的分类矩阵 PDF。按照用户要求，先落实版式微调，再进行定稿审读；所有文字建议仅供评估，尚未改入论文。摘要和三张图继续冻结。

## 1. 已落实的版式微调

| 项目 | 原矩阵版 | 微调后 | 阅读效果 |
|---|---:|---:|---|
| Table 2：材料概览 | 第 6 页 | **第 5 页** | 与 §4 材料说明同页 |
| Table 3：分类矩阵 | 第 6 页 | 第 6 页 | 保留完整分类与总计 |
| Figure 3：机制图 | 第 7 页 | **第 6 页** | 与 §5.2 开头同页 |
| Table 4：专项比较 | 第 6 页 | 第 7 页 | 靠近三个详细机制段落 |
| Table 5、6 | 第 8 页 | 第 8 页 | 保持在首次讨论后一页 |

本轮仅调整三个浮动体在 LaTeX 中的登记位置，没有改变正文、图注、表内文字、数字、字号、边距、行距或图片尺寸。进一步前移 Table 5、6 的试排会使结果表出现在更早的章节、结果正文后移，因而未采用。主文仍在第 8 页结束；参考文献位于第 9 页，附录从第 9 页延续到第 10 页。

## 2. 审读结论与建议取舍

**没有发现需要改动主要实验数字、分母、核心结论或冻结摘要的硬性矛盾。** 本轮的修改价值集中在让读者看懂已有方法与比较设置，而不是改变研究主张。

**建议优先批准 A1、A2、A3，并一并补充 B1；B2 可以按作者偏好决定。** A1 与事实审读中的同名问题已合并，仅计一次。

| 编号 | 位置 | 评估 | 建议 | 净新增英文词数（约） |
|---|---|---|---|---:|
| A1 | §3.4（第 4 页）；附录 A.5（第 10 页） | 方法指标未定义 | 优先建议 | 42（主文） |
| A2 | §3.4（第 4 页）；§5.2 Host container context 与 Table 4（第 7 页） | 对照比较量未定义 | 优先建议 | 30（主文） |
| A3 | 附录 A.3（第 9 页）；相关讨论 §6.2（第 7 页） | 附录代号与划分未定义 | 优先建议 | 86（附录） |
| B1 | §3.3 Native memory envelope（第 2–3 页） | 内存测量口径 | 建议一并补充 | 19（主文） |
| B2 | §6.3（第 8 页）；方法对应 §3.3 Native timezone reference（第 3 页） | 时区数据库限制具体化 | 可选补充 | 21（主文） |

A1+A2 合计为主文增加约 **72 词**；加入 B1 后约 **91 词**。A3 约 **86 词**，只进入附录。词数按空白分隔估算，不含新段落的版式影响。建议尚未落稿，因此不能据此保证增补后仍为 8 页；批准后需重新编译核对。

以下五项都不要求新增实验，不改摘要，也不改实验数字。置信度均为高；具体实现和已保存记录支持其建议内容。

## 3. 逐项评估与最小英文建议

### A1 · 给 semantic coverage 和 semantic quality 操作定义

**位置：** §3.4（第 4 页）；附录 A.5（第 10 页）。**判断：** 优先建议。

**现文：**

> Additions must preserve training detections, increase semantic coverage, and satisfy the alarm and coverage constraints.

**评估：** 前一段刚定义 definite-output coverage，后一段引入未定义的 semantic coverage；读者可能把二者当作同一指标，也可能把 semantic quality 当成条件准确率或证据可信度。实际实现的 coverage 按语义组与训练修改记录去重，quality 是预登记的观测/语义偏好。

**最小建议稿（未应用）：**

> Semantic coverage counts distinct (semantic group, modified training record) trigger pairs using the training detection weights, with groups assigned from field semantics. Semantic quality sums predefined preference scores for positive literals; these scores express observation preferences, not measured accuracy or independent evidence.

**放置方式：** 在 §3.4 retention 段第一句之后插入；后续约束句保持。

**证据：**

- [retention.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/rule_learning_v2/retention.py)：11–55, 58–64
- [semantic_selection.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/rule_learning_v2/semantic_selection.py)：1–6, 63–70, 85–94, 144–147, 168–170

### A2 · 定义 same-Web viewport 对照实际比较的量

**位置：** §3.4（第 4 页）；§5.2 Host container context 与 Table 4（第 7 页）。**判断：** 优先建议。

**现文：**

> The App pool contains 50 base templates and three fixed relations: Native memory, Native timezone, and same-Web viewport.

**评估：** Native memory、Native timezone、Host geometry 均有明确操作定义；same-Web viewport 却只出现名称与 0/6、0/66 结果。不了解代码的读者无法判断它与 Host 上界的差别，也容易把 Host 的 DPR×scale 换算误套到这个同 Web 对照上。

**最小建议稿（未应用）：**

> The same-Web comparator flags either visual-viewport dimension exceeding the corresponding window.innerWidth or window.innerHeight by more than 1 CSS pixel, using positive, same-probe observations when visual-viewport scale is at least one.

**放置方式：** 在 §3.4 首段第一句列出三个固定关系之后插入，或紧邻 §5.2 首次解释该对照时插入一次；不重复两处添加。

**证据：**

- [mtc_screen_relations.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/mtc_screen_relations.py)：10–35, 77–121
- [CANDIDATES.json](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app177_core_ablation_v1/CANDIDATES.json)：3093–3139
- [CONDITIONS_FROZEN.json](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/screen_geometry_observation_v1/CONDITIONS_FROZEN.json)：31–35

### A3 · 解释附录诊断代号与四视图/划分的实际范围

**位置：** 附录 A.3（第 9 页）；相关讨论 §6.2（第 7 页）。**判断：** 优先建议。

**现文：**

> S0 detects 13/26; S0+M and S0+W detect 19/26; S0+B detects 16/26.

> The relation-augmented P0 fit yields 14/14 detections and 0/46 normal alarms; under P2, the relation-augmented view yields 4/8 and 6/34.

**评估：** 这些标签仅列出结果，没有给出其指代。读者既不能理解哪些资源条件未通过接入，也不能判断 P0 的拟合成绩与 P2 的整批留出诊断区别。四视图限定于语言/时区字段，并非全部 App/Browser 字段的模型上限；该范围对理解主文 §6.2 的论断有直接影响。

**最小建议稿（未应用）：**

> S0 is the frozen Integrated App + C1 baseline. M adds a Native-to-Browser memory-envelope check, W tests inequality between App-Web and Browser memory reports, and B tests Browser memory above 8 GiB.

> The four-view diagnostic uses language and timezone measurements: App only, Browser only, their concatenation, and the concatenation augmented by C1/C2 states. P0 trains on the 630 discovery normals and both paired batches. P1 and P2 withhold the 18-position pilot and 42-position matched batch, respectively, while training on the discovery normals and the other batch.

**放置方式：** 第一段放在 A.3 的 S07 数字前；第二段放在 S08 的 P0/P2 数字前。保留已有 development-use 和非独立复现实验的限定。

**证据：**

- [rx_common.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_constrained_extension_v1/rx_common.py)：9–11
- [REPORT.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_constrained_extension_v1/REPORT.md)：5, 14, 20, 60
- [FIELD_SEMANTICS.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_paired_validation_v1/FIELD_SEMANTICS.md)：3–15
- [PROTOCOL.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/cross_endpoint_four_view_comparison_v1/PROTOCOL.md)：9, 19–21
- `S08_full_aggregate_table.md`：P0 V_BOTH_REL 14/14, 0/46; P1 V_BOTH_REL 6/6, 0/12; P2 V_BOTH_REL 4/8, 6/34

### B1 · 明确 Native memory 的观测口径

**位置：** §3.3 Native memory envelope（第 2–3 页）。**判断：** 建议一并补充。

**现文：**

> For observed, finite, positive memory measurements in GiB from the same bound App record

**评估：** GiB 说明单位，但没有说明 m_native 是内核可见总量，不能由空闲内存或零售标称 RAM 代入。当前字段名和数据处理是正确的；补一句可让读者准确复现 envelope 的输入。

**最小建议稿（未应用）：**

> Here, m_native is kernel-visible total memory reported by Android ActivityManager.MemoryInfo.totalMem, converted to GiB; m_web is the Web deviceMemory report.

**放置方式：** 在内存公式之后、解释 Device Memory draft 之前；实际排版沿用现有数学变量和等宽 API 名。

**证据：**

- [SOURCES.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/memory_relation_validation_v1/SOURCES.md)：5, 17
- [FIELD_SEMANTICS.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_paired_validation_v1/FIELD_SEMANTICS.md)：8

Android 官方 API 文档也区分 `totalMem`、可用内存与零售标称内存；`totalMem` 指内核可访问的总量。来源：[ActivityManager.MemoryInfo](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo#totalMem)。这支持明确观测口径，但不改变现有公式或检测结果。

### B2 · 具体说明固定 tzdb 与设备 tzdb 版本未记录的边界

**位置：** §6.3（第 8 页）；方法对应 §3.3 Native timezone reference（第 3 页）。**判断：** 可选补充。

**现文：**

> API changes, WebView providers, timing, locale conventions, and container behavior can alter a relation’s applicability.

**评估：** 现稿已列一般漂移风险，但没有交代设备侧 tzdb 版本未记录。原始专项报告明确承认它可能与固定 2026c 有规则差异；这说明在时间区间可靠、zone ID 可解析的情况下，合法偏移也可能不一致。补充能使固定数据库的证据边界更具体，不把可能性升级为已观察到的错误。

**最小建议稿（未应用）：**

> The device-side timezone database version was not recorded, so differences from the fixed 2026c database can also produce legitimate offset disagreements.

**放置方式：** 在 §6.3 一般漂移句之后补一句；不改摘要、不重写主结果。

**证据：**

- [REPORT.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/timezone_relation_validation_v1/REPORT.md)：143–145

此句表达的是原专项报告已记录的兼容性限制，不表示本次已经观察到由 tzdb 版本差异导致的误报警。它与摘要中具体测试批次的结果并不矛盾。

## 4. 暂不优先加入的内容

| 候选 | 评估与处理 |
|---|---|
| 在 §3.1 列出 session / pair / receipt / hash / batch 核验字段 | 可选，最小替换净增加约 14 词。现文与 Figure 2 已说明关联目的、处理顺序及非硬件证明边界；优先级低于 A1–A3。 |
| 把最终 6/6/5 条模型完整清单搬到主文 | 不建议。附录 A.5 已列完整条件，主文也交代主要整合关系及高度条件的配置差异。短模型规模句亦非必需。 |
| 全稿重写或继续堆叠局限声明 | 没有发现足以支持这一改动规模的问题。保留现有贡献、结果层级和已经写清的边界。 |

如作者希望考虑这两个可选句，原文、候选和证据见 `reader_review.md/json`。它们同样未应用。

## 5. 已核实、应保留的内容

主要计数、分母和三配置的统计单位未见矛盾。尤其检查了容易被汇总表掩盖的“九个差异”：只读取保存预测，以 `(sample_id, fold_id)` 对齐 378 个受控 held-out positions，没有重新推理或拟合。

| 与 Integrated App 比较 | 保存输出中的逐记录差异 | 结论 |
|---|---|---|
| Web-only | 恰好 9 个 T→F，全部属于 CPU-plus-memory | 原文可以保留 |
| No-memory | 恰好相同的 9 个 T→F | 原文可以保留 |
| No-timezone | 0 个状态差异 | 相同总计有逐记录支持 |
| No MTC cap | 3 个 F→T，全部属于 screen | 与总计及分类矩阵一致 |

这项检查避免了把“分类汇总相同”直接当成“逐记录预测相同”。完整筛选键、源文件校验和差异记录在 `evidence_review.json`。它核实保存结果与论文表述的一致性，不是独立重跑实验。

以下限定已经充分，不建议重复改写：Native/Host 不构成可信根；告警不等于恶意；主基准九个差异与内存专项十二个额外检出分开；Host geometry 是独立专项；替代模型经过重新拟合；历史数据和配对数据具有开发使用历史；C1 不含 timestamp gate；U、FAILED 与正常判断保持区分。

参考文献的 15 个引用身份和编号映射全部正常。本轮另抽查四项主来源：WebView 指纹预印本、BrowserFM、Cross-Boundary Mobile Tracking 及 Device Memory API 文档，未发现需要更正的标题、作者或相关范围表述。Device Memory 文档的 discontinued 状态已在正文正确标明。该抽查不等于重新审计所有文献的全部书目信息。来源记录见 `reference_spot_check.json`。

## 6. 沿用的作者事实待办

以下两项需要真实研究记录或实际发布安排，不能仅靠润色完成。它们已在上一轮清单中列出，本轮没有扩大为新增实验要求。

| 待办 | 需要作者核定的内容 | 本轮处理 |
|---|---|---|
| 采集与数据管理说明（§6.4，第 8 页） | 采集授权/账号范围、日期、是否涉及真实用户、保留和访问范围、实际审查或豁免情况 | 保留已核实的模拟器、云设备及权限表述；不补造未确认的声明 |
| 评审可访问的制品入口（附录 A.3/A.5，第 9–10 页） | 实际匿名入口和包含的代码、模型、完整表、记录范围 | 确认入口可用后再形成准确的一句制品说明 |

详细清单保存在 `notes/AUTHOR_FACTS_TO_CONFIRM.md`。作者事实尚未提供的句子不纳入可直接应用的批准集。

## 7. 核验范围和修改边界

版式：59 份受保护文件保持原字节；八节正文去除浮动体调用和条件命令后逐字符一致。三张图的九个资产全部保留，所有图表本体文件未变。基线版十页显示与上一轮一致。新版矩阵 PDF 全部页面已检查，无可见裁切、重叠、缺字或横向越栏。

日志保留已有的 `printacmref=false` 模板提示和末页输出阶段 1.499pt overfull vbox；没有新增 hbox 问题，实际页面内容和页脚未被挤压。

本轮落实到论文中的变更只有版式。建议英文句子、评估记录、查证结果均位于独立审读文件中。后续需按用户通过的编号应用文字修改，再检查摘要锁定、数据一致性和真实页数。

本报告绑定的 PDF SHA-256：`4d49d439f85e67b11ef261b346caeadf4b90d7cb42ce45460d8fe16874e6b080`。仓库证据固定在提交 `d58e0680728f9adfdd5b550d00fd3f1674460b1e`。
