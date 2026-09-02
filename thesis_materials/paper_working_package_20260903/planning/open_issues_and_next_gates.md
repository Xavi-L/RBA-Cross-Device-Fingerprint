# 未解决问题与下一阶段准入门槛

## 1. 当前不阻塞草稿写作的问题

以下问题需要在正式投稿前解决，但不妨碍当前把系统和历史材料写成不限篇幅草稿：

- Browser67 完整受控攻击配对数量不足；
- paired244 尚未完成检测增量实验；
- 历史实验仍使用 teacher risk score；
- LLM/RAG 的检测收益尚未得到独立事实标签支持；
- 当前没有按正式投稿页数压缩；
- 图片和结果表尚未最终设计。

## 2. 正式 App177 评价的门槛

在把当前受控结果升级为正式检测结果前，至少需要：

1. 冻结最终 FeatureApp、字段目录、backend 和攻击协议版本；
2. 为每个输入保存 canonical raw、receipt、batch、payload hash、manifest 和执行证据；
3. 使用可信、非空且不由标签或攻击类型派生的 stable group；
4. 将同一设备/画像、同一 scenario 和相关重复采集放入同一 split；
5. 规则生成、阈值、prompt、检索参数和融合参数只使用 train/development；
6. 最终 test 在版本冻结后只运行一次；
7. 正常输入必须具有足够证据，不能把 `insufficient_evidence` 计为正常通过；
8. 报告有效设备/环境比较数，而不是把重复 session 当作独立样本；
9. 为每类攻击报告执行已证实、字段效果已观察、规则已执行和报警已产生四个层次；
10. 以设备组或 pair 为重采样单位计算置信区间。

## 3. Browser67/paired244 重验门槛

在声称 Browser67 带来检测价值前，需要重新进行两态采集：

```text
baseline: App177 + Browser67 attempt
attack_active: App177 + Browser67 attempt
```

每个阶段必须具有明确的 `browser_capture_status`。成功时要有 raw Browser payload、receipt 和 completed pair provenance；失败时保留 App177，并记录 incomplete/unsupported 原因，不补造 Browser67。

正式比较至少包括：

- App177-only；
- Browser67-only；
- App177 + Browser67 raw baseline；
- App177 relations；
- App177 + Browser-specific relations；
- 完整方法移除 Browser67 的消融；
- 完整方法移除跨层关系、只拼接原始字段的对照。

还需要区分两类问题：

- Browser67 是否增加新的受控操纵可见性；
- Browser67 是否同时增加正常跨容器差异和误报风险。

因此，无显著提升、只改善特定攻击族、甚至因正常差异导致性能下降，均可能是合理且有价值的研究结果。

## 4. 关系和知识的晋级门槛

### 官方派生语义关系

- 官方文档只定义字段/API 语义，不自动提供攻击 verdict；
- 项目推导必须记录 premise fields、官方来源、推理强度、容错、反例和适用版本；
- 依赖数值容差、设备族或时间序列的关系，在正常数据校准前保持候选状态；
- 关系目录冻结后才能进入独立攻击评价。

### Device-mined rule

- 只能从预先指定的训练/开发数据产生；
- 必须保存支持样本、反例、适用范围和人工审核记录；
- 需要在未参与挖掘的正常设备和攻击 pair 上验证；
- 正常误报、不可判定和证据不足必须分别报告；
- 不能使用 provider、工具名、pair role、fold 或 session ID 等捷径字段。

## 5. LLM/RAG 进入核心贡献的门槛

只有满足以下条件后，才考虑将知识增强 Agent 提升为论文主要贡献：

- 使用独立事实标签而不是 teacher score；
- 设置无知识 LLM、整库 prompt、Exact/BM25/Dense/Hybrid retrieval 和 Oracle retrieval 等强基线；
- 报告检索 Recall@k、nDCG、MRR、字段/规则覆盖和无关卡片率；
- 报告 citation precision/recall、虚构字段率、无效规则触发率和 Verifier 拦截率；
- 进行官方知识、经验规则、容错/反例、字段过滤、reranker、Verifier 和外部融合消融；
- 严格防止 test 样本、相同设备画像和攻击模板进入知识构建或案例索引。

现阶段更安全的定位是：LLM/RAG 是可审计推理原型，官方知识的已观察价值主要体现在语义依据和容错边界暴露，而非已证明的数值精度提升。

## 6. 数据集与 Benchmark 发布门槛

- 明确数据许可、第三方平台条款和攻击工具发布边界；
- 删除或散列可识别设备、账号、session 和平台来源的敏感标识；
- 同时报告 session、App177、Browser67、paired244、App-only、stable group 和 scenario 数量；
- 提供字段目录、Schema、状态语义、QC、数据卡和版本历史；
- 冻结官方 split、任务定义、提交格式、基线和评测器；
- 对重复设备画像使用分组评价和必要的组内训练权重；
- 不把重复 session 数量表述为独立设备覆盖。

## 7. 建议的近期顺序

1. 继续完善不限篇幅英文草稿和术语一致性；
2. 冻结统一的两态攻击采集协议；
3. 补充正常真机与 stable group；
4. 统一 App177/Browser67 release lock；
5. 重新采集完整 paired244 攻击数据；
6. 完成 App177/Browser67/paired244 对照与消融；
7. 再决定历史 ML、LLM/RAG 和端侧内容在正式论文中的保留范围；
8. 最后根据目标 venue 压缩篇幅、重绘图表和完成统计检验。
