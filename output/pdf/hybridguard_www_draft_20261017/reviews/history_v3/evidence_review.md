# HybridGuard v2 定稿审读：方法、结果与证据一致性

日期：2026-10-22。状态：**审读完成；仅提出建议，未改动论文正文、摘要、图或结果。**

审读版本：[最终 v2 PDF](sandbox:/workspace/scratch/fff1267c1d19/hybridguard_latex_v2/build/matrix/HybridGuard_layout_v1_matrix.pdf)。SHA-256：`4d49d439f85e67b11ef261b346caeadf4b90d7cb42ce45460d8fe16874e6b080`。PDF 共 10 页，主文 8 页。以下页码均对应这份稳定版本，另保留节号与源文件行号。

## 结论与修改优先级

本轮没有发现需要改动结果、分母或锁定摘要的硬错误。需要优先补足的是已有方法和诊断结果的操作定义：retention 的 semantic coverage/quality、附录的 S0/M/W/B 与 P0/P1/P2；读者审读另列的 same-Web viewport 定义应合并评估。memory 字段口径与设备 tzdb 版本未知是两项次一级澄清。作者采集事实与评审制品入口沿用既有待办，不作为本轮新发现的实验缺陷。

“必须”在本报告中指：若保留相应算法或诊断结果，应解释所用术语/代号；并不表示数值有误。E1 与 reader_review 的 R1 是同一问题，合并时只计一次。所有英文句子均为待评估建议稿；A1/A2 含占位符，不能直接应用。

| 项目 | 分级 | 最终 PDF 页码 | 评估 |
| --- | --- | --- | --- |
| E1 retention 两个量的定义 | 必须／优先澄清；与 reader R1 合并 | 4、10 | 方法自足性，建议优先 |
| E2 附录资源代号与四视图划分 | 必须／优先澄清 | 9 | 诊断结果可理解性，建议优先 |
| E3 Native memory 输入口径 | 建议 | 2–3 | 局部可重复性澄清 |
| E4 固定 tzdb 的版本边界 | 建议 | 3、8 | 局限具体化 |
| A1 实际采集与数据管理事实 | 作者确认 | 8 | 沿用现有清单 |
| A2 评审可访问制品入口 | 作者确认 | 9–10 | 依真实发布安排处理 |

## 待评估的具体修改

### E1　为 retention 的 semantic coverage 与 semantic quality 补操作定义

**分级：必须。** 优先澄清（与 reader R1 合并，只计一次）。置信度：高。位置：§3.4；附录 A.5，PDF 第 4、10 页；源文件 `hybridguard_latex_v1/input_markdown/sections/03_method.md` 第 45、47 行。

**原文短引**

> Additions must preserve training detections, increase semantic coverage, and satisfy the alarm and coverage constraints.

> Same-group swaps to registered higher-quality alternatives

**为何值得处理。** 前一段的 definite-output coverage 已有定义，而 semantic coverage 和 semantic quality 在主文与附录均未操作化。读者不能判断 retention 保留了什么，可能误以为是字段覆盖率、准确率或独立证据强度。实际 coverage 对 (语义组, 训练修改记录) 触发对去重后按训练检测权重求和；同一记录可被不同组分别计入。quality 只对正向文字的预登记偏好分数求和。

**最小英文建议稿（未应用）**

> Semantic coverage counts distinct (semantic group, modified training record) trigger pairs using the training detection weights, with groups assigned from field semantics. Semantic quality sums predefined preference scores for positive literals; these scores express observation preferences, not measured accuracy or independent evidence.

**放置与评估。** 在 §3.4 retention 段第一句之后插入两句；与 reader R1 采用同一修改，不重复添加。

**依据**

- [rba_review/repo_evidence/hybridguard_agent/research/rule_learning_v2/retention.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/rule_learning_v2/retention.py)，第 11–55, 58–64 行。
- [rba_review/repo_evidence/hybridguard_agent/research/rule_learning_v2/semantic_selection.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/hybridguard_agent/research/rule_learning_v2/semantic_selection.py)，第 1–6, 63–70, 85–94, 144–147, 168–170, 273–302 行。

**影响。** 不改锁定摘要；不改模型、数据、分母或结果；不需要新增实验。仅解释已有实现或原始研究报告已承认的边界。

### E2　解释附录诊断代号与四视图/划分的实际范围

**分级：必须。** 优先澄清。置信度：高。位置：附录 A.3；对应 §6.2，PDF 第 9 页；源文件 `hybridguard_latex_v1/input_markdown/supplement/00_Appendix_English.md` 第 19、21 行。

**原文短引**

> S0 detects 13/26; S0+M and S0+W detect 19/26; S0+B detects 16/26.

> The relation-augmented P0 fit yields 14/14 detections and 0/46 normal alarms; under P2, the relation-augmented view yields 4/8 and 6/34.

**为何值得处理。** 这些标签仅列出结果，没有给出其指代。读者既不能理解哪些资源条件未通过接入，也不能判断 P0 的拟合成绩与 P2 的整批留出诊断区别。四视图限定于语言/时区字段，并非全部 App/Browser 字段的模型上限；该范围对理解主文 §6.2 的论断有直接影响。

**最小英文建议稿（未应用）**

> S0 is the frozen Integrated App + C1 baseline. M adds a Native-to-Browser memory-envelope check, W tests inequality between App-Web and Browser memory reports, and B tests Browser memory above 8 GiB.

> The four-view diagnostic uses language and timezone measurements: App only, Browser only, their concatenation, and the concatenation augmented by C1/C2 states. P0 trains on the 630 discovery normals and both paired batches. P1 and P2 withhold the 18-position pilot and 42-position matched batch, respectively, while training on the discovery normals and the other batch.

**放置与评估。** 第一段放在 A.3 的 S07 数字前；第二段放在 S08 的 P0/P2 数字前。保留已有 development-use 和非独立复现实验的限定。

**依据**

- [deliverables/app_resource_constrained_extension_v1/rx_common.py](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_constrained_extension_v1/rx_common.py)，第 9–11 行。
- [deliverables/app_resource_constrained_extension_v1/REPORT.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_constrained_extension_v1/REPORT.md)，第 5, 14, 20, 60 行。
- [deliverables/app_resource_paired_validation_v1/FIELD_SEMANTICS.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_paired_validation_v1/FIELD_SEMANTICS.md)，第 3–15 行。
- [deliverables/cross_endpoint_four_view_comparison_v1/PROTOCOL.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/cross_endpoint_four_view_comparison_v1/PROTOCOL.md)，第 9, 19–21 行。
- [hybridguard_latex_v1/input_markdown/supplement/S08_full_aggregate_table.md](sandbox:/workspace/scratch/fff1267c1d19/hybridguard_latex_v1/input_markdown/supplement/S08_full_aggregate_table.md)，数据项：P0 V_BOTH_REL 14/14, 0/46; P1 V_BOTH_REL 6/6, 0/12; P2 V_BOTH_REL 4/8, 6/34。

**影响。** 不改锁定摘要；不改模型、数据、分母或结果；不需要新增实验。仅解释已有实现或原始研究报告已承认的边界。

### E3　明确 Native memory 的观测口径

**分级：建议。** 次一级建议。置信度：高。位置：§3.3 Native memory envelope，PDF 第 2、3 页；源文件 `hybridguard_latex_v1/input_markdown/sections/03_method.md` 第 21、25 行。

**原文短引**

> For observed, finite, positive memory measurements in GiB from the same bound App record

**为何值得处理。** GiB 说明单位，但没有说明 m_native 是内核可见总量，不能由空闲内存或零售标称 RAM 代入。当前字段名和数据处理是正确的；补一句可让读者准确复现 envelope 的输入。

**最小英文建议稿（未应用）**

> Here, m_native is kernel-visible total memory reported by Android ActivityManager.MemoryInfo.totalMem, converted to GiB; m_web is the Web deviceMemory report.

**放置与评估。** 在内存公式之后、解释 Device Memory draft 之前；实际排版沿用现有数学变量和等宽 API 名。

**依据**

- [rba_review/repo_evidence/deliverables/memory_relation_validation_v1/SOURCES.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/memory_relation_validation_v1/SOURCES.md)，第 5, 17 行。
- [deliverables/app_resource_paired_validation_v1/FIELD_SEMANTICS.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/app_resource_paired_validation_v1/FIELD_SEMANTICS.md)，第 8 行。

**影响。** 不改锁定摘要；不改模型、数据、分母或结果；不需要新增实验。仅解释已有实现或原始研究报告已承认的边界。

### E4　具体说明固定 tzdb 与设备 tzdb 版本未记录的边界

**分级：建议。** 次一级建议。置信度：高。位置：§6.3；关联 §3.3 Native timezone reference，PDF 第 3、8 页；源文件 `hybridguard_latex_v1/input_markdown/sections/06_discussion.md` 第 15 行。

**原文短引**

> API changes, WebView providers, timing, locale conventions, and container behavior can alter a relation’s applicability.

关联原文：

> The Native IANA zone and collection interval determine the effective UTC offset under the fixed timezone database, 2026c.

**为何值得处理。** 现稿已列一般漂移风险，但没有交代设备侧 tzdb 版本未记录。原始专项报告明确承认它可能与固定 2026c 有规则差异；这说明在时间区间可靠、zone ID 可解析的情况下，合法偏移也可能不一致。补充能使固定数据库的证据边界更具体，不把可能性升级为已观察到的错误。

**最小英文建议稿（未应用）**

> The device-side timezone database version was not recorded, so differences from the fixed 2026c database can also produce legitimate offset disagreements.

**放置与评估。** 在 §6.3 一般漂移句之后补一句；不改摘要、不重写主结果。

**依据**

- [rba_review/repo_evidence/deliverables/timezone_relation_validation_v1/REPORT.md](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/d58e0680728f9adfdd5b550d00fd3f1674460b1e/deliverables/timezone_relation_validation_v1/REPORT.md)，第 143–145 行。

**影响。** 不改锁定摘要；不改模型、数据、分母或结果；不需要新增实验。仅解释已有实现或原始研究报告已承认的边界。

### A1　作者核定实际采集与数据管理事实

**分级：作者确认。** 沿用既有待办；非新实验要求。置信度：高（缺失判断）；具体事实待作者提供。位置：§6.4，PDF 第 8 页；源文件 `hybridguard_latex_v1/input_markdown/sections/06_discussion.md` 第 23、25 行。

**原文短引**

> Our controlled manipulations use emulators, and historical normals come from cloud-device collection.

**为何值得处理。** 现文准确说明可验证的来源与权限，但账号/设备授权、是否涉及真实用户、保留期限、实际伦理审查结论不能仅凭代码确定。既有 AUTHOR_FACTS_TO_CONFIRM.md 已列出这些作者事实，应由真实记录决定是否需要补入；不要写未经确认的批准、豁免或无人类参与声明。

**最小英文建议稿（未应用）**

> Controlled and cloud-device observations were collected during [verified dates] using [verified authorization/account scope]. [Verified participant or real-user status.] Access to the retained data is restricted to [verified scope], with [verified retention policy]. [Verified review or exemption statement, if applicable.]

**放置与评估。** 这只是带占位符的填写模板，不是可直接应用的论文稿。待作者确认后再形成 §6.4 的最短准确表述。

**依据**

- [hybridguard_text_v1/notes/AUTHOR_FACTS_TO_CONFIRM.md](sandbox:/workspace/scratch/fff1267c1d19/hybridguard_text_v1/notes/AUTHOR_FACTS_TO_CONFIRM.md)，第 5–14 行。

**影响。** 不改锁定摘要；不改模型、数据、分母或结果；不需要新增实验。需要作者提供真实事实后再决定最终文本。

### A2　作者核定评审可访问的实际制品入口

**分级：作者确认。** 沿用既有待办；按实际发布安排处理。置信度：高。位置：附录 A.3 / A.5，PDF 第 9、10 页；源文件 `hybridguard_latex_v1/input_markdown/supplement/00_Appendix_English.md` 第 17、29、33 行。

**原文短引**

> The implementation archive provides the 50 base templates and three relations

> Record-level outputs are retained in

**为何值得处理。** 附录已写清实现目录、模型与逐记录输出位置；但论文没有明确评审可访问入口，正文源包中的 S01–S09 也不能自动等同于完整实现 archive。需根据实际匿名发布安排确认入口和包含内容，不应自行把可识别作者的仓库链接放入匿名稿。

**最小英文建议稿（未应用）**

> The anonymized artifact at [verified review-access URL] contains [verified contents], including the implementation, saved models, and aggregate result tables.

**放置与评估。** 仅在入口与内容真实可用时加入附录 A.5；若实际尚未开放，则按真实状态改写，不能承诺不存在的制品。

**依据**

- [hybridguard_text_v1/notes/AUTHOR_FACTS_TO_CONFIRM.md](sandbox:/workspace/scratch/fff1267c1d19/hybridguard_text_v1/notes/AUTHOR_FACTS_TO_CONFIRM.md)，第 16–18 行。
- [hybridguard_latex_v1/input_markdown/supplement/00_Appendix_English.md](sandbox:/workspace/scratch/fff1267c1d19/hybridguard_latex_v1/input_markdown/supplement/00_Appendix_English.md)，第 17, 29–33 行。

**影响。** 不改锁定摘要；不改模型、数据、分母或结果；不需要新增实验。需要作者提供真实事实后再决定最终文本。

## 已核实可保留的关键表述

| 检查 | 结论与依据 |
| --- | --- |

| P1 锁定摘要与正文/表格的核心量一致 | 105/126 与 0/252；memory 18/18 vs 6/18 且均0/48；timezone均6/6、0/30 vs6/30；geometry均6/6、0/66 vs6/66 均一致。摘要既有 separate fixed-check / separate geometry 边界由正文进一步明确，不需改摘要。 依据：`00_abstract.md:11`；`05_results.md:5, 30–46`；`data/01_App总体.csv`；`data/04_专项条件.csv`。 |

| P2 Table 3 分组权重与总计一致 | 14 recipes × 6 methods=84 cells；五组大小1/1/2/8/2，每recipe 9个有效修改。加权检测数105/108/96/96/105/72，总分母126；漏检21/18/30/30/21/54及百分比均一致。分组表注只声称完整state-count vectors一致，不把同计数误称同预测。 依据：`tables/table_03_matrix.tex`；`input_markdown/supplement/00_Appendix_English.md:17`；`data/02_App分类.csv`。 |

| P3 九个 App 差异确有逐记录输出支持 | 按 (sample_id, fold_id) 对齐 controlled/heldout/RETENTION 的378个位置。Web-only与no-memory各仅9个 T→F，全属于 CPU-plus-memory recipe；其余369一致。No-timezone为0个状态差异。No-cap仅3个F→T，均为screen recipe。可以保留 all nine differences occur…；结论不是从相同总计推测。 依据：`deliverables/app177_core_ablation_v1/results/full_predictions.jsonl.gz`；`deliverables/app177_core_ablation_v1/results/predictions.jsonl.gz`。 |

| P4 三配置、历史 cohort 和分母未混用 | 01/02只因同计数并列，未池化；144/117分组、独立列出的630训练normal，以及每模型14/261→17/261的unknown计数一致。paired 14 modifications +46 normals是60位置，未因为3模型膨胀成42个攻击。历史development exposure限制已在正文说明。 依据：`05_results.md:52–61, 65–77`；`04_evaluation_protocol.md`；`data/03_MTC正常.csv`；`data/06_双端历史正常.csv`。 |

| P5 refit、standalone specialist 与证据范围已区分 | 九个主benchmark差异与十二个memory专项新增检测明确分开；Host geometry不在Integrated App；固定比较器不被宣称为通用最优上限；refitted alternatives不等于删单规则的因果归因。 依据：`05_results.md:5, 24, 42–46`；`06_discussion.md:5–11, 19`；`00_Appendix_English.md:5, 35`。 |

| P6 T/F/U/FAILED、retention约束和停止原因已一致 | 必要输入失败优先于T；U未被当normal，未选字段缺失不会自动fail；EMPTY_MODEL先处理。主文区分addition与swap的额外nonregression要求。deadline为60秒，保存fit实际因heuristic stopping结束，未写成超时。benchmark无FAILED不等于未实现失败语义。C1无timestamp gate已明确。 依据：`03_method.md:15–17, 45–47, 51`；`06_discussion.md:17`；`00_Appendix_English.md:25, 31`；`rba_review/repo_evidence/hybridguard_agent/research/rule_learning_v2/semantic_selection.py:273–302`。 |


### “九个差异都发生在 CPU-plus-memory recipe”的逐记录核验

§5.1 的 “all nine differences occur in the CPU-plus-memory recipe” 可以保留。审读直接读取保存的逐记录输出，没有训练模型、重跑采集或生成新实验。两个压缩文件的 Git blob SHA 经核验后解压；按 `(sample_id, fold_id)` 对齐 `controlled / heldout / RETENTION`，共 378 个位置，其中 126 个有效修改、252 个 normal。

| 与 Integrated App 比较的已保存模型 | 匹配位置 | 状态差异 | 差异位置与方向 |
| --- | ---: | ---: | --- |
| A_APP_WEB_ONLY | 378 | 9 | 全为 CPU-plus-memory；Full T → alternative F |
| A_NO_MEMORY_REL | 378 | 9 | 同上，且是相同的九个记录 |
| A_NO_TIMEZONE_REL | 378 | 0 | 所有位置状态一致 |
| A_NO_MTC_CAP | 378 | 3 | 全为 screen metrics；Full F → alternative T |

因此结论不只是由 105 与 96 的总数相减得到，也不依赖“6/9 相同便代表逐条预测相同”的错误推断。完整差异记录键保存在配套 JSON 的 `saved_prediction_verification.comparisons`。

来源（固定提交 `d58e0680728f9adfdd5b550d00fd3f1674460b1e`）：

- `deliverables/app177_core_ablation_v1/results/full_predictions.jsonl.gz`：3,771 行，Git blob `026485d5c602e48c9c82c3ba2f2ff21b31c3405f`。

- `deliverables/app177_core_ablation_v1/results/predictions.jsonl.gz`：33,939 行，Git blob `3d09e00306518706675e10f3a8c8ab9887545103`。

## 审读边界与正式页码确认

本轮检查已有正文、附录、聚合表、保存模型定义及指定的逐记录输出。它确认写作与已有材料的一致性，没有独立重建干预标签或采集绑定，也没有替代原始实验复现。未发现需要因此追加实验的写作修正。

最终 PDF 的全文定位复核显示：S0/P0/P2 只在第 9 页 A.3 结果句出现，附近及其他章节没有定义；P1 未在论文中展开。semantic coverage/quality 在第 4 页方法段和第 10 页排序说明中被使用，但没有操作定义。memory 段位于第 2–3 页，未出现 `totalMem` 或 kernel-visible 口径；固定 2026c 描述位于第 3 页，相关局限建议放在第 8 页 §6.3。上述候选并非遗漏已写明上下文后提出的重复修改。

用户批准前，论文保持目前版本。可以优先评估 E1/E2 与 reader R2，然后决定是否一并采纳 E3/E4；A1/A2 等真实信息确认后再处理。

