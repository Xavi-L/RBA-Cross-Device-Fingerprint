# 实验协议、防泄漏、指标与 OOD

> authoritative_for: split、案例隔离、baseline、K/R 矩阵、Oracle 评估、消融、指标、统计和 OOD
> read_when: 设计或运行实验、审计泄漏、比较方法、解释性能或构建论文结果
> do_not_read_when: 只做采集器、Schema 或单个运行模块实现
> default_read_budget: 每次只读 split、matrix、metrics、OOD 中相关锚点
> allowed_second_books: 03/04 用于数据划分；05/06 用于被评估模块

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| EVAL-SPLIT | 固定拆分与零泄漏 |
| EVAL-MATRIX | 阶段实验与 Baseline |
| EVAL-ABLATION | 单因素消融 |
| EVAL-METRICS | 检测、检索、可信度和统计 |
| EVAL-OOD | 未见设备、工具、来源和时间 |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
<a id="EVAL-SPLIT"></a>

## 12. 数据划分与防泄漏协议

### 12.1 固定拆分顺序

~~~text
原始数据和 manifest
  -> stable key 与 pair 构建
  -> 锁定最终 test groups
  -> 其余数据做 train/dev 或 nested grouped CV
  -> 仅 train 生成经验规则和案例索引
  -> dev 调检索、Prompt、阈值和融合
  -> 冻结全部版本
  -> 最终 test 只运行一次
~~~

### 12.2 必须为零的泄漏

- 同一 stable_device_key 跨 fold；
- 同一 pair 跨 fold；
- attack 与其 clean parent 跨 fold；
- test 样本参与规则生成；
- test 样本进入案例索引；
- test 数据影响 top-k、chunk、Prompt、阈值或超参数；
- 标签、工具、provider 或 fold 字段进入模型输入；
- 测试增强样本进入训练。

### 12.3 案例 RAG 约束

案例索引只能由当前外层训练 fold 构建，并排除：

- 相同 stable key；
- 相同 pair；
- 相同 evidence hash；
- 同一 clean 基线的派生攻击；
- 相同攻击配置的复制模板，除非实验明确研究模板匹配。

### 12.4 样本权重

训练时建议：

~~~text
sample_weight_i = 1 / group_size(group_id_i)
~~~

它减少重复画像对损失的支配，但不能替代 grouped split。

---

<a id="EVAL-MATRIX"></a>

## 13. 实验矩阵

### 13.1 阶段实验

| 阶段 | 核心问题 | 实验 | 继续条件 | 停止或降级条件 |
|---|---|---|---|---|
| S0 数据审计 | 数据能否支持实验 | Schema、重复、常量、单位、来源共因 | V2 契约稳定，manifest 完整 | clean/attack 采集链路不可比 |
| S1 金标准集 | 是否有独立真值 | clean–attack 配对、工具日志、人工复核 | 攻击成功可验证 | 只有 LLM 分数，没有事实标签 |
| S2 规则归纳 | 自动规则是否有效 | Manual、Official、Data-only、组合 KB | held-out 上覆盖或精度提高，FPR 不恶化 | 只记忆工具/provider |
| S3 检索单测 | 是否找到正确知识 | Exact、BM25、Dense、Hybrid、Oracle | 主检索超过强基线 | Oracle 也无收益，回到知识设计 |
| S4 端到端 | 是否改善最终任务 | 规则、传统模型、LLM、Full-KB、RAG | 主指标优于最强基线 | 只提高教师一致率 |
| S5 Verifier | 是否改善可信度 | RAG 与 RAG+Verifier 配对 | 错误引用明显下降 | 无收益或召回下降过大 |
| S6 OOD | 是否泛化 | 未见设备、工具、家族、provider、时间 | 主要 OOD 保留优势 | 仅 ID 有效，降级结论 |
| S7 系统指标 | 是否具备系统价值 | 延迟、token、成本、失败率 | 达到预注册目标 | 成本过高则定位离线分析 |

### 13.2 端到端 Baseline

至少包含：

1. Dummy/多数类。
2. 确定性规则执行器。
3. Native-only、WebView-only、Web-only。
4. 177 字段传统监督模型。
5. 显式跨层一致性传统模型。
6. clean-only 异常检测。
7. LLM direct，无知识。
8. LLM + Full-KB Prompt。
9. LLM + Exact/BM25。
10. LLM + Dense/Hybrid。
11. 主方法 Hybrid RAG + Verifier + external fusion。
12. Oracle retrieval。

传统模型必须使用新的独立事实标签重新训练。当前 llm_label 数据上的模型只能称为 teacher-distillation 或结构预验证 baseline。

### 13.3 知识来源矩阵

| 配置 | 人工/确定性规则 | 官方知识 | 数据规则 | 案例 |
|---|---:|---:|---:|---:|
| K0 | 0 | 0 | 0 | 0 |
| K1 | 1 | 0 | 0 | 0 |
| K2 | 1 | 1 | 0 | 0 |
| K3 | 1 | 1 | 1 | 0 |
| K4 | 1 | 1 | 1 | 1 |

解释：

- K2–K1：官方知识贡献；
- K3–K2：数据规则贡献；
- K4–K3：案例检索贡献。

<a id="EVAL-ABLATION"></a>

### 13.4 单因素消融

#### 输入与语义

- 去 Native；
- 去 WebView；
- 去 Web；
- 只保留原始 177 字段；
- 只保留显式跨层关系；
- 只保留 Tri-layer；
- 去 GPU 新证据；
- 去新 23 字段。

#### 知识

- 去官方知识；
- 去经验规则；
- 去案例；
- 去 tolerance/counterexample；
- 用随机错配官方卡作为负对照。

#### 检索

- 去 field filter；
- 去 metadata filter；
- 去 reranker；
- Hybrid 改 BM25；
- Hybrid 改 Exact；
- 改 top-k；
- 去重开/关；
- shuffled retrieval。

#### 推理

- 完整 JSON direct；
- EvidenceBundle direct；
- 六组评分；
- 去 cited fields/rules 强制约束；
- 去 Verifier；
- 模板解释与 LLM 解释。

#### 数据与融合

- random split 与 grouped split，仅用于展示泄漏差异；
- 去 sample weight；
- 去 evidence hash 去重；
- 去训练 fold 运行时增强；
- simple average、simplex、Positive ElasticNet；
- 不同 provider/collector 版本敏感性。

---

<a id="EVAL-METRICS"></a>

## 14. 评价指标

### 14.1 检测

主指标：

- AUPRC；
- Macro-F1；
- 各攻击家族 F1；
- benign FPR；
- TPR@5% FPR；
- 数据足够后再报告 TPR@1% FPR；
- clean–attack 配对分数差；
- Balanced Accuracy。

AUROC 可以报告，但不能作为唯一主指标。

### 14.2 多标签完整性违规

- violation_types Micro-F1；
- violation_types Macro-F1；
- 各跨层关系 Precision/Recall；
- attack success 与 observed mutation 的区分能力。

### 14.3 检索

- Recall@k；
- Precision@k；
- nDCG@k；
- MRR；
- 正确字段和规则覆盖率；
- tolerance/counterexample 覆盖率；
- 无关卡片率；
- 重复卡片率；
- token 和检索延迟。

### 14.4 解释与可信度

- Citation Precision/Recall；
- 引用与结论一致率；
- Unsupported Claim Rate；
- Hallucinated Field Rate；
- Invalid Rule Trigger Rate；
- future-only 误引用率；
- 人工盲评的事实正确性与可操作性。

### 14.5 校准

- Brier Score；
- ECE；
- NLL；
- 风险可靠性图。

没有独立风险概率标签时，应校准 manipulation_present，而不是主观 LLM 风险分。

### 14.6 OOD 与稳定性

- ID 到 OOD 的相对下降；
- 多次 LLM 调用均值和标准差；
- 输出解析失败率；
- Prompt 小扰动稳定性；
- 单字段反事实修改的单调性；
- 时间外推稳定性。

### 14.7 系统指标

- p50/p95 延迟；
- 输入/输出 token；
- 单样本调用成本；
- 吞吐；
- 索引大小；
- API/解析失败率；
- 缓存命中率。

### 14.8 统计协议

- 置信区间按 stable_device_key 或 pair_id 做 group bootstrap；
- 不得按 session 行独立重采样；
- 配置比较使用 paired bootstrap 或 permutation test；
- 报告效果量和 95% CI；
- LLM 至少记录多个固定种子或重复调用的方差；
- 所有阈值在 dev 上固定。

---

<a id="EVAL-OOD"></a>

## 15. OOD 测试轨道

建议并行报告：

1. **Group-ID**：未见 stable_device_key，但攻击家族已见。
2. **Tool-OOD**：leave-one-attack-tool-out。
3. **Family-OOD**：leave-one-attack-family-out。
4. **Provider-OOD**：leave-one-provider-out。
5. **Brand/Device-OOD**：未见品牌或设备家族。
6. **Temporal-OOD**：未来采集批次。
7. **Adaptive-OOD**：只伪造部分字段或主动规避已知规则。

如果主方法只在 ID 上有效，论文结论必须降级为：

> 方法对已见环境和已见攻击模式有效，尚未证明未知攻击泛化。

---

