# R01 参考论文备忘

研究版本 `discriminative-rule-learning-v1-20260924`；核对日期 2026-09-24。
已阅读主线第 9 节、仓库 `research_references.bib`，并只核对其中链接的一手材料。没有开展扩展文献综述，没有在本步运行参考算法。

## 版本与已核实方法

**Boolean Decision Rules via Column Generation** — Sanjeeb Dash, Oktay Günlük, Dennis Wei; IBM Research; NeurIPS 2018, Advances in Neural Information Processing Systems 31; BibTeX key `dash2018boolean`。方法依据是[正式会议 PDF](https://proceedings.neurips.cc/paper_files/paper/2018/file/743394beff4b1282ba735e5e3723ed74-Paper.pdf)，不以预印本摘要替代。arXiv:1805.09901 的 v1/v2 日期分别为 2018-05-24 / 2020-08-05；正式版和预印本的实验数量表述不同，本协议不引用其效果数值。[arXiv 版本记录](https://arxiv.org/abs/1805.09901)

以下英文短备忘是对会议论文 §2 的压缩转述，中文项目设计在下节单列：

> DNF is an OR of AND clauses; CNF is an AND of OR clauses. A literal is a Boolean condition or its negation. Clauses form an unordered rule set. Section 2.1 minimizes Hamming loss under a complexity bound. Each false negative contributes once; a negative satisfying several selected clauses contributes several times. Ordinary 0–1 error counts that negative once. Clause complexity is one plus its number of conditions, summed across the model. Section 2.2 alternates a restricted master LP and a pricing problem for improving columns. Section 2.3 qualifies optimization bounds: LP optimality, integer recovery, and global integer optimality are different claims. Such training bounds do not establish test generalization.

这段为本项目的转述，不是原文逐字引述。[正式论文 §2.1–2.3](https://proceedings.neurips.cc/paper_files/paper/2018/file/743394beff4b1282ba735e5e3723ed74-Paper.pdf)

作者[会议幻灯片第 6–11 页](https://nips.cc/media/nips-2018/Slides/12722.pdf)进一步核对列生成的操作顺序：用少量子句求 restricted master LP，从对偶信息建立 pricing，加入负 reduced-cost 子句并再次求解，最后取得整数规则集合。仅在现成候选中选择子集不等于这个流程；启发式定价或提前超时不能自动继承精确定价下的最优性结论。

## 本项目直接借鉴与自行设计

直接借鉴的是带标签的简洁布尔集合、子句/文字条件的复杂度记账、有限 IP 与受预算控制的组合搜索思路。R01 选择的函数为 `MacroTPR_config_environment - 0.005*(clauses+literals)`，另施加整体 clean 报警预算和决策覆盖约束。clean 误报按模型 OR 并集计一次，与原文重复计罚的 Hamming loss 不同，不能原样借用其优化证明。

T/F/U、原始 UNKNOWN/NOT_APPLICABLE 原因、EMPTY_MODEL 与 FAILED、干预三态、S01 标签边界、来源台账、环境/配置划分及暴露管理是 HybridGuard 的设计。原论文不替本项目解决这些测量、关联或攻击真值问题。U 不是二值 0，CNF/DNF 的二值标签取反构造也不能未经核对直接覆盖本项目弃判语义。

本轮比较方法的准确名称如下：

| 方法 | 本协议含义 | 允许的结论 |
|---|---|---|
| 固定候选贪心 OR | 训练折内逐步加入条件并有限剪枝 | 找到的可行模型；没有全局最优保证 |
| 有限候选 IP OR / DNF2 | 固定有限文字/子句空间，精确计算集合报警并集 | 只按求解器状态报告此有限问题的 incumbent、bound、gap |
| 真正列生成 | restricted master、对偶、pricing、负 reduced cost 和整数恢复 | 当前未实现；不得以固定 57 项筛选冒充复现 |

启发式找不到满足约束的模型不证明整个搜索空间不可行。零训练误报、最优训练解或求解 gap 均不能证明测试泛化，更不能证明总体零误报。当前未实现列生成；只登记有条件的预算，不因其名称更复杂而默认启用。

## 后续实现前继续核对的位置

- 会议版 §2.1，式 (1)–(4)：原 Hamming 目标和复杂度约束，与本项目集合预算编码逐项比较。
- §2.2，式 (5)–(10)：定价符号、对偶方向、子句长度 D；只有实际新增 CG 才使用。
- §2.3：何时 LP 与整数最优重合、何时需要额外整数搜索、提前终止的有效界所需条件。
- §3：近似定价/随机化及计算限制；§4 和补充材料：离散化与实验实现细节。

本轮核对的是论文层面的定义与区别；求解器 API、数值容差、附录全部推导、作者代码版本和复现结果均 `NOT_IMPLEMENTED_OR_NOT_VERIFIED_IN_R01`。已有 BibTeX 保持原样，后续不得把这些未核实事项写成算法保证。
