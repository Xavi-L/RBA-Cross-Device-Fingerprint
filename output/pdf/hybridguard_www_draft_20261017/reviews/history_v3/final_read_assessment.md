<div class="eyebrow">HYBRIDGUARD · APPROVED EDITS · 2026-10-22</div>

# A1、A2、A3、B1 已落实并核验

<div class="status">已通过的 4 项修改全部落稿 · 主文 8 页 / 全文 10 页 · 摘要与三张图继续冻结</div>

本报告记录本轮经用户明确批准的修改。此前的“建议尚未应用”评估保存在 `reviews/history_v2/`，其页码与 PDF 哈希仅对应上一轮版本。本轮没有把未批准的 B2 或其他文字建议一并加入。

## 1. 实际修改

| 编号 | 已落实内容 | 新版位置 | 新增英文词数 |
|---|---|---|---:|
| A1 | §3.4：semantic coverage / quality | 第 4 页 | 42 |
| A2 | §3.4：same-Web viewport 对照 | 第 4 页 | 30 |
| A3 | 附录 A.3：资源条件、四视图与批次划分 | 第 9 页 | 86 |
| B1 | §3.3：Native memory 观测口径 | 第 3 页 | 19 |

主文新增 91 个英文词，附录新增 86 个英文词，共 177 词。只有方法节和附录的输入稿发生文字变化；去掉四项新增句子后，两份输入稿均可逐字恢复上一轮原文。数学变量沿用原稿形式，API 名采用等宽字体。

## 2. 已加入论文的句子

### A1 · 给 semantic coverage 和 semantic quality 操作定义

**位置：** §3.4：semantic coverage / quality，第 4 页。

> Semantic coverage counts distinct (semantic group, modified training record) trigger pairs using the training detection weights, with groups assigned from field semantics. Semantic quality sums predefined preference scores for positive literals; these scores express observation preferences, not measured accuracy or independent evidence.

**修改前的问题：** 前一段刚定义 definite-output coverage，后一段引入未定义的 semantic coverage；读者可能把二者当作同一指标，也可能把 semantic quality 当成条件准确率或证据可信度。实际实现的 coverage 按语义组与训练修改记录去重，quality 是预登记的观测/语义偏好。

### A2 · 定义 same-Web viewport 对照实际比较的量

**位置：** §3.4：same-Web viewport 对照，第 4 页。

> The same-Web comparator flags either visual-viewport dimension exceeding the corresponding window.innerWidth or window.innerHeight by more than 1 CSS pixel, using positive, same-probe observations when visual-viewport scale is at least one.

**修改前的问题：** Native memory、Native timezone、Host geometry 均有明确操作定义；same-Web viewport 却只出现名称与 0/6、0/66 结果。不了解代码的读者无法判断它与 Host 上界的差别，也容易把 Host 的 DPR×scale 换算误套到这个同 Web 对照上。

### A3 · 解释附录诊断代号与四视图/划分的实际范围

**位置：** 附录 A.3：资源条件、四视图与批次划分，第 9 页。

> S0 is the frozen Integrated App + C1 baseline. M adds a Native-to-Browser memory-envelope check, W tests inequality between App-Web and Browser memory reports, and B tests Browser memory above 8 GiB.

> The four-view diagnostic uses language and timezone measurements: App only, Browser only, their concatenation, and the concatenation augmented by C1/C2 states. P0 trains on the 630 discovery normals and both paired batches. P1 and P2 withhold the 18-position pilot and 42-position matched batch, respectively, while training on the discovery normals and the other batch.

**修改前的问题：** 这些标签仅列出结果，没有给出其指代。读者既不能理解哪些资源条件未通过接入，也不能判断 P0 的拟合成绩与 P2 的整批留出诊断区别。四视图限定于语言/时区字段，并非全部 App/Browser 字段的模型上限；该范围对理解主文 §6.2 的论断有直接影响。

### B1 · 明确 Native memory 的观测口径

**位置：** §3.3：Native memory 观测口径，第 3 页。

> Here, m_native is kernel-visible total memory reported by Android ActivityManager.MemoryInfo.totalMem, converted to GiB; m_web is the Web deviceMemory report.

**修改前的问题：** GiB 说明单位，但没有说明 m_native 是内核可见总量，不能由空闲内存或零售标称 RAM 代入。当前字段名和数据处理是正确的；补一句可让读者准确复现 envelope 的输入。

论文中 `m_native` 和 `m_web` 已排成现有公式的数学变量；`ActivityManager.MemoryInfo.totalMem` 与 `deviceMemory` 保持 API 拼写。

## 3. 版式与编译结果

最终 PDF 的主文在第 8 页结束，全文 10 页。四项新增文字完整保留，所有图片尺寸、字体、字号、页边距和行距沿用上一轮。矩阵版沿用上一轮的浮动体登记位置；本轮调整 Table 1、Table 2 的局部列宽，并让 Table 3 和 Table 6 的表头以单行显示，其中 Table 6 同步重分配列宽。所有表头用词、图注与数值保持原样。B1 定义与其后原有内存说明排在同一段。具体测量与检查见 `qa/approved_layout_check.md`。

| 图表 | 上轮版式版 | 本轮修改版 |
|---|---:|---:|
| Table 2 | 第 5 页 | 第 5 页 |
| Table 3 | 第 6 页 | 第 6 页 |
| Figure 3 | 第 6 页 | 第 6 页 |
| Table 4 | 第 7 页 | 第 7 页 |
| Table 5 | 第 8 页 | 第 8 页 |
| Table 6 | 第 8 页 | 第 8 页 |

## 4. 核验范围

- **修改范围：** A1、A2、B1 各出现一次，A3 的两个定义段各出现一次；没有额外改写原有句子。
- **冻结摘要：** 保持旧 draft 的 257 词、三段原文；源码与 PDF 提取结果均已核对。
- **图表与数据：** 三张图的 9 份冻结资产、图注、CSV 数据和参考文献保持原字节；表格可见文字与数值不变，局部列宽等版式差异单列核验。
- **结果：** 没有新增实验、采集、拟合或预测；没有改变已有检测/报警数字。
- **页面：** 最终 PDF 经渲染检查；交叉引用和参考文献解析状态见版式核验记录。

## 5. 作者事实与本轮边界

MTC 的研究使用、论文分析/发表与公开数据集等权限已按用户明确确认记录为允许。所属机构记录为北京航空航天大学；“据作者了解没有相关伦理审查要求”保留为作者当前了解，没有扩展为正式批准、豁免或机构认定。

这些更新保存在 `notes/AUTHOR_FACTS_TO_CONFIRM.md`。本轮正文修改仍限定在 A1、A2、A3、B1，没有额外增加采集日期、授权/伦理声明或匿名制品入口表述。B2 继续保持未应用。

## 6. 可编辑来源

源码包以 `main_matrix.tex` 为本轮已核验的编译入口。`input_markdown/` 保存批准后的输入文字，`sections/` 保存已生成且可直接编辑的 LaTeX。默认迁移流程与包内表格文件共同重现本轮文字、表格版式与浮动体安排。上一轮审读及版式记录已明确归档，避免把历史结论误当作当前状态。

源码 ZIP 已解压到全新临时目录，按默认流程执行迁移与编译。重编结果仍为 8 页主文、10 页全文，全部 10 页提取文本与 120 dpi 渲染像素均与交付 PDF 一致。59 个编译及迁移输入文件的哈希在迁移前后保持一致。测试完成后补齐审读与修改落实记录；最终打包保留这 59 个已测试输入。详见 `qa/package_rebuild_check.md`。

本报告绑定的 PDF SHA-256：`bd00d76b84fb1da0a9c04c88a82a9113fc74377cf0e83e4380480e6f588f99dc`。
