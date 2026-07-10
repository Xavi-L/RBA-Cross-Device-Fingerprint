# LLM 推理、Verifier 与外部融合

> authoritative_for: LLM 最小输入、六组输出、Verifier 检查、Positive ElasticNet 和运行期约束
> read_when: 实现 grouped scorer、Verifier、Fusion、在线风险推理或外部模型隐私最小化
> do_not_read_when: 只做知识卡构建、攻击采集或总体实验设计
> default_read_budget: 只读输入、六组评分或融合中的相关锚点
> allowed_second_books: 05 用于 Retriever 输出；02 用于 DecisionTrace/接口契约

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| RUNTIME-LLM-INPUT | 外部 LLM 输入最小化 |
| RUNTIME-GROUPED-REASONING | 六组结构化评分 |
| RUNTIME-VERIFIER | 字段、规则、引用和 future-only 验证 |
| RUNTIME-FUSION | 外部融合与约束 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
## 11. LLM 推理与外部融合

<a id="RUNTIME-VERIFIER"></a>

### 10.5 Verifier

Verifier 至少检查：

1. cited field 是否真实存在于 EvidenceBundle。
2. cited rule/card 是否真实存在。
3. rule predicate 是否被满足。
4. short-circuit 是否被正确执行。
5. future-only 证据是否被误用。
6. reason 中是否出现 payload 不支持的事实。
7. group score 和 risk direction 是否一致。
8. JSON 输出是否符合 Schema。

建议输出：

- accepted；
- accepted_with_correction；
- rejected_for_regeneration；
- rejected_for_manual_review。

---

<a id="RUNTIME-LLM-INPUT"></a>

### 11.1 LLM 输入

默认只发送：

- 脱敏 EvidenceBundle；
- 已检索 KnowledgeCard；
- 输出 Schema；
- 固定评分方向和容错说明。

默认不发送：

- 原始 IP；
- 原始 session ID；
- provider 账号或设备槽位；
- attack_tool、label、fold；
- 完整高基数身份字符串；
- 测试集元数据。

<a id="RUNTIME-GROUPED-REASONING"></a>

### 11.2 六组评分

继续复用现有六组：

1. Native–Web；
2. Native–WebView；
3. WebView–Web；
4. Tri-layer semantic；
5. Physical runtime；
6. Attack scenario。

LLM 输出每组：

- score；
- cited_fields；
- cited_rules；
- supporting_evidence；
- tolerance_evidence；
- uncertainty；
- reason。

LLM 不应在 Prompt 中隐式学习最终总分权重。

<a id="RUNTIME-FUSION"></a>

### 11.3 外部融合

继续以 Positive ElasticNet 为主候选，同时保留：

- simple average；
- non-negative simplex；
- unconstrained ElasticNet；
- deterministic policy；
- 不做融合的 direct total score。

权重学习必须：

- nested grouped CV；
- 训练 fold 内选超参数；
- stable group sample weight；
- 测试 fold 原始数据不增强；
- 保存每 fold 权重和稳定性。

风险总分应视为策略输出；主检测指标优先使用 manipulation_present 和 violation_types。

---
