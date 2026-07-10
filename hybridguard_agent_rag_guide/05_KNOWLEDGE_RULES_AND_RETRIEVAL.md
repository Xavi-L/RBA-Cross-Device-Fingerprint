# 知识分层、规则晋级与字段感知检索

> authoritative_for: 四层知识、CandidateRule 晋级、KnowledgeCard 发布、Exact/BM25/Dense/Hybrid、Oracle 和检索负对照
> read_when: 转换规则库、扩展官方知识、生成候选规则、实现检索或 ContextPack
> do_not_read_when: 只做 LLM 输出校验、融合训练或数据采集
> default_read_budget: 默认只读 KNOW-PROMOTION 或 RAG-RETRIEVAL 中一个主题
> allowed_second_books: 02 用于 KnowledgeCard 契约；07 用于检索实验

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| KNOW-LAYERS | 四层知识库 |
| KNOW-PROMOTION | 候选规则生成、验证和晋级 |
| RAG-BASELINES | 为什么保留 Full-KB/Exact/BM25 |
| RAG-RETRIEVAL | 字段感知检索流程与对照 |
| RAG-ORACLE | Oracle retrieval 诊断 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
## 9. 知识库构建与规则晋级

<a id="KNOW-LAYERS"></a>

### 9.1 四层知识库

不要把所有内容拍平成一个无来源文本库。

#### A. 官方语义层

内容：

- Android/Chrome/WebView 官方字段语义；
- API 行为；
- 安全机制；
- 合法差异和限制；
- future-only 能力。

作用：

- 支撑字段含义和容错；
- 不直接提供项目风险阈值。

#### B. 确定性关系层

内容：

- 版本解析；
- 型号/UA 软匹配；
- WebView 与 Web Chrome 主版本；
- 物理屏幕与逻辑屏幕/DPR；
- Native GPU 与 WebGL GPU 族；
- JSBridge 和宿主关系；
- 核心 short-circuit。

这些关系应尽量转成机器可执行 predicate。

#### C. 经验规则层

内容：

- 仅从训练 fold 的配对 clean/attack 数据中发现的规律；
- 支持度、反例、适用场景和误报统计；
- 与官方知识和确定性规则的冲突检查。

经验规则必须保存 created_from_split，不能用测试数据生成。

#### D. 案例层

内容：

- 训练 fold 内的 EvidenceBundle；
- 已验证攻击配置；
- matched rules 和审核结果。

案例检索必须排除：

- 测试 fold；
- 相同 stable_device_key；
- 相同 pair；
- 相同 evidence_hash；
- 由测试样本派生的增强变体。

<a id="KNOW-PROMOTION"></a>

### 9.2 LLM 候选规则流程

~~~text
训练折配对差异和反例
  -> LLM 提出 CandidateRule
  -> 字段存在性检查
  -> predicate 编译
  -> 训练组支持度和反例统计
  -> dev 组泛化和 benign FPR 检查
  -> 官方知识/既有规则冲突检查
  -> 人工审核
  -> 正例、反例、边界单元测试
  -> 发布 KnowledgeCard
~~~

候选规则必须输出：

- 依赖字段；
- 适用场景；
- 可执行 predicate 或 semantic_only 标记；
- 支持样本；
- 反例；
- 容错条件；
- 可能的混淆因素；
- 证据来源；
- 训练 split；
- 建议状态。

LLM 不得直接写 scoring/rule_knowledge_base.json。

### 9.3 规则晋级门槛

经验规则进入 published 前至少满足：

1. 所有字段在 canonical registry 中存在。
2. predicate 可以执行，或明确标为 semantic_only。
3. 在训练组有最小支持度。
4. 在 dev 组仍有方向一致的信号。
5. 没有明显提高 clean FPR。
6. 没有把来源、provider、工具或 App 版本当作标签捷径。
7. 与官方语义不冲突。
8. 包含正例、反例和边界单元测试。
9. 有人工审核记录。

若 held-out attack family 无增益，应把结论降级为工具特定模式发现，不能宣称通用攻击规则。

---

## 10. 字段感知 RAG 设计

<a id="RAG-BASELINES"></a>

### 10.1 为什么第一版不应直接上复杂向量库

当前知识规模只有：

- 35 条主规则；
- 20 张官方卡；
- 30 条来源元数据。

在这一规模下，整库 Prompt、字段精确映射和 BM25 都是强基线。Dense/Hybrid RAG 必须证明：

- 检测或解释效果更好；
- 上下文更短；
- 延迟或成本更低；
- 引用更准确；
- 未来扩展性更好。

“使用了向量数据库”本身不是贡献。

<a id="RAG-RETRIEVAL"></a>

### 10.2 推荐检索流程

~~~text
EvidenceBundle
  -> 根据异常字段、证据组和场景构造查询
  -> schema/current/future 硬过滤
  -> canonical field 精确匹配
  -> rule priority 和 short-circuit 检查
  -> BM25/lexical 检索
  -> 可选 Dense 检索
  -> Hybrid 合并
  -> field overlap + evidence strength + tolerance rerank
  -> 同时补充触发卡、容错卡和反例卡
  -> 构造固定预算 ContextPack
~~~

关键规则：

- short-circuit 规则强制执行，不依赖 top-k。
- future-only 卡片必须硬过滤。
- 既要检索风险触发，也要检索 tolerance 和 counterexample。
- top-k 和 token budget 必须记录。
- 检索结果必须保留过滤原因和得分。
- 案例检索晚于规则/官方卡检索上线。

### 10.3 必须保留的检索对照

| 配置 | 方法 | 用途 |
|---|---|---|
| R0 | 无知识 | 零知识基线 |
| R1 | 整库 Prompt | 判断是否真的需要检索 |
| R2 | canonical field 到规则 Exact 映射 | 结构化任务强基线 |
| R3 | BM25 | 稀疏检索基线 |
| R4 | Dense | 语义检索基线 |
| R5 | Hybrid | 主候选 |
| R6 | Hybrid + metadata filter + reranker | 完整方案 |
| R7 | Oracle retrieval | 推理上界和错误归因 |
| R8 | Shuffled/wrong retrieval | 因果负对照 |

所有方案固定：

- LLM 模型；
- Prompt 主体；
- 输出 Schema；
- 温度；
- 上下文预算，或明确报告预算差异；
- 风险阈值和融合方式。

<a id="RAG-ORACLE"></a>

### 10.4 Oracle retrieval

Oracle retrieval 直接给模型人工标注的正确规则和证据卡，用于区分：

- Oracle 也差：知识或推理任务本身有问题；
- Oracle 好、实际 RAG 差：主要问题在检索；
- 实际 RAG 接近 Oracle：检索充分，应优化推理；
- Oracle 只改善解释：知识贡献应限定为可信度与可审计性。
