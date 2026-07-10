# 论文写作、结论模板与风险治理

> authoritative_for: 并行写作安排、论文结构、强/受限/失败结论模板和风险登记
> read_when: 写论文、导师汇报、解释失败结果、撰写局限或伦理风险
> do_not_read_when: 只做数据、代码或实验执行
> default_read_budget: 只读 PAPER-PLAN、PAPER-CLAIMS 或 PAPER-RISKS 中相关锚点
> allowed_second_books: 01 用于研究边界；07 用于结果证据

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| PAPER-PLAN | 现在可写与实验后写 |
| PAPER-STRUCTURE | 推荐论文结构 |
| PAPER-CLAIMS | 三类结论模板 |
| PAPER-RISKS | 风险登记与对策 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
<a id="PAPER-PLAN"></a>

## 18. 论文同步写作计划

不要等所有实验结束再开始写论文。

### 18.1 现在就可以写

1. 研究背景与问题定义。
2. 三端 177 字段采集模型。
3. 威胁模型与攻击面。
4. 数据协议和 stable profile 口径。
5. 知识分层与规则晋级机制。
6. Agent/RAG 总体架构。
7. EvidenceBundle、KnowledgeCard 和 DecisionTrace。
8. 防泄漏实验协议。
9. 研究假设与预注册指标。
10. 伦理、隐私和局限。

### 18.2 必须等实验后写

1. 主结果。
2. 检索效果。
3. Verifier 贡献。
4. 知识来源消融。
5. OOD 泛化。
6. 系统成本。
7. 失败案例和局限的最终表述。

<a id="PAPER-STRUCTURE"></a>

### 18.3 推荐论文结构

~~~text
1. Introduction
2. Background and Threat Model
3. Three-Layer Fingerprint Schema and Dataset Protocol
4. Provenance-Aware Knowledge Construction
5. Field-Aware Retrieval and Verified Reasoning
6. Experimental Setup
7. Main Results and Ablations
8. OOD, Error Analysis, Efficiency and Ethics
9. Related Work
10. Conclusion
~~~

<a id="PAPER-CLAIMS"></a>

### 18.4 三种结论模板

#### 强结论

> 在同设备配对操纵基准上，主方法在固定误报率下优于规则、传统模型和直接 LLM；该优势在未见设备和未见攻击工具测试中仍然存在。Oracle、负检索对照和模块消融进一步表明，收益分别来自正确知识检索与输出验证。

#### 受限但有效

> 官方知识没有显著提高攻击检测率，但降低了边界样本误报和无依据引用，因此其主要价值是语义约束和可审计性。

#### 失败但有研究价值

> 数据归纳规则只改善了已见工具，对未见攻击家族没有稳定增益，因此当前证据仅支持工具特定模式发现，不支持通用攻击泛化。

---

<a id="PAPER-RISKS"></a>

## 19. 风险登记表

| 风险 | 早期信号 | 影响 | 对策 |
|---|---|---|---|
| 循环标签 | LLM 规则生成、评分和标签来自同一模型/数据 | 指标只能表示自我一致 | 独立攻击事实标签；teacher agreement 单列 |
| 环境共因 | 所有 attack/clean 分属不同 provider、App 或批次 | 模型学习来源捷径 | 同设备配对；source × label 交叉审计 |
| 重复画像泄漏 | random split 明显优于 grouped split | 泛化虚高 | stable key、pair group、group bootstrap |
| 字段语义错误 | 电压单位、屏幕字段被直接判风险 | 规则系统性误报 | canonical registry、单位与 tolerance |
| LLM 幻觉规则 | 引用不存在字段或未满足 trigger | 解释不可审计 | predicate、Verifier、正反单元测试 |
| RAG 不优于整库 | 小 KB 上 Full-KB 更强 | RAG 贡献不足 | 保留强基线；把价值转向成本/引用或放弃复杂检索 |
| 经验规则只记忆工具 | Tool-OOD/Family-OOD 崩溃 | 无未知攻击泛化 | held-out family；规则降级 |
| 低样本量 | 每 fold 独立攻击 group 太少 | CI 极宽、结论不稳定 | 优先扩 stable profile；降为 pilot |
| 外部模型隐私 | 原始指纹和标识直接发送 | 隐私与合规风险 | 只发脱敏 EvidenceBundle；hash ID |
| 不可复现 | Prompt、KB、索引和模型版本缺失 | 无法重跑论文结果 | DecisionTrace 和 run manifest |

---

