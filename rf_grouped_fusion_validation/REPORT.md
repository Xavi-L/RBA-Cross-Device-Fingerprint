# 随机森林分组融合有效性预验证报告

## 1. 实验目的

当前暂时没有足够算力运行 30B/70B 级 LLM，因此本实验用随机森林作为“组级风险子分数”的替代模型，先验证 `LLM_GROUPED_FUSION_PLAN.md` 中的分组证据结构是否值得继续推进。

本实验能验证：

- 六组证据组织方式是否比直接堆叠原始字段更稳。
- 外部融合模型是否能从组级子分数中学习有效权重。
- 哪些证据组在 grouped CV 下贡献更稳定。

本实验不能直接证明：

- LLM 的语义理解能力优于随机森林。
- LLM 生成自然语言 reason 的质量。
- 最终 LLM 分组评分的真实上限。

## 2. 实验设计

数据仍使用 `training/scored_data.jsonl`，目标为 `llm_label.risk_score`。切分方式复用原有 grouped CV：同一真实设备、云测设备或脚本攻击模板不会同时进入训练集和测试集。

六个证据组如下：

| 证据组 | 特征数 |
|---|---|
| Native-Web | 18 |
| Native-WebView | 8 |
| WebView-Web | 5 |
| Tri-layer semantic | 7 |
| Physical runtime | 19 |
| Attack scenario | 15 |

验证流程：

```text
每个证据组的特征
  -> 组内 RandomForest 预测该组风险子分数
  -> Simple average / Positive ElasticNet / RF meta 融合
  -> grouped CV 评估 MAE、RMSE、R2、高风险 F1
```

其中 Positive ElasticNet 使用内层 grouped CV 选择 `alpha` 和 `l1_ratio`，训练融合模型时使用外层训练集内部的 out-of-fold 组分数，避免把外层测试集信息泄漏进融合权重。

## 3. 核心结果

| 配置 | 输入维度 | MAE | MAE std | RMSE | 高风险 F1 |
|---|---|---|---|---|---|
| Raw all direct RF | 65 | 2.642 | 1.004 | 4.455 | 1.000 |
| Tri-layer semantic direct RF | 7 | 2.281 | 0.466 | 3.358 | 1.000 |
| Six group evidence direct RF | 72 | 4.078 | 2.083 | 7.172 | 0.333 |
| Six group scores + mean | 6 | 5.420 | 1.709 | 7.602 | 0.667 |
| Six group scores + Positive ElasticNet | 6 | 2.968 | 0.065 | 4.132 | 1.000 |
| Six group scores + RF meta | 6 | 3.062 | 1.569 | 4.960 | 0.667 |

## 4. 六组融合权重

以下为 `Six group scores + Positive ElasticNet` 在 3 个外层 fold 中的平均权重：

| 证据组 | 平均权重 | 权重标准差 |
|---|---|---|
| Native-Web | 0.000 | 0.000 |
| Native-WebView | 0.398 | 0.365 |
| WebView-Web | 0.058 | 0.083 |
| Tri-layer semantic | 0.520 | 0.355 |
| Physical runtime | 0.000 | 0.000 |
| Attack scenario | 0.185 | 0.088 |

权重越高，表示该组随机森林子分数对最终风险分的贡献越大。权重为 0 不一定表示该组完全无意义，也可能表示它与其他组高度相关，被 ElasticNet 收缩掉。

## 5. 去掉单组后的影响

以下表格以完整六组 Positive ElasticNet 为基准，`MAE delta` 越大，说明去掉该组后误差上升越明显。

| 去掉的配置 | MAE | RMSE | 高风险 F1 | MAE delta |
|---|---|---|---|---|
| Drop Tri-layer semantic + Positive ElasticNet | 3.277 | 4.331 | 1.000 | 0.309 |
| Drop Native-WebView + Positive ElasticNet | 3.053 | 4.019 | 1.000 | 0.085 |
| Drop Physical runtime + Positive ElasticNet | 2.968 | 4.132 | 1.000 | 0.000 |
| Drop Native-Web + Positive ElasticNet | 2.968 | 4.132 | 1.000 | -0.000 |
| Drop WebView-Web + Positive ElasticNet | 2.905 | 4.081 | 1.000 | -0.063 |
| Drop Attack scenario + Positive ElasticNet | 2.710 | 4.031 | 1.000 | -0.258 |

## 6. 阶段性结论

- Positive ElasticNet 融合后的 MAE 为 2.968，明显低于简单平均的 5.420 和六组特征直接堆叠随机森林的 4.078，说明“组级子分数 + 外部融合”比朴素合并更稳。
- 该结果仍高于 Raw all direct RF 的 2.642 和 Tri-layer semantic direct RF 的 2.281，因此现阶段不能宣称分组融合已经带来最终性能优势。
- ElasticNet 权重主要集中在 Tri-layer semantic、Native-WebView 和 Attack scenario，且去掉 Tri-layer 后 MAE 上升最大，支持原计划中“核心三端语义是最稳定泛化信号”的判断。
- 因此这次随机森林预验证的结论应表述为：框架可跑通，外部融合有效，关键信号选择符合预期；最终性能提升需要后续用 LLM 组级语义评分继续验证。

- 这份结果可以作为“低算力条件下的方案有效性预验证”：它验证的是分组证据池和外部融合框架，而不是 LLM 本身。
- 后续有算力后，可以保持本实验的 grouped CV、输出表结构和汇报口径不变，只把组内 RandomForest 子分数替换为 LLM 对每组证据生成的 `0-100` 风险子分数。

## 7. 结果文件

- `rf_grouped_fusion_summary.csv`：各配置 grouped CV 汇总指标。
- `rf_grouped_fusion_fold_metrics.csv`：每折指标。
- `rf_grouped_fusion_predictions.csv`：每条测试样本预测明细。
- `rf_group_scores_by_fold.csv`：各融合配置下每条测试样本的组级随机森林子分数。
- `rf_grouped_fusion_weights.csv`：融合模型每折权重。
- `rf_group_feature_dictionary.csv`：六组特征映射。

## 8. 一句话总结

在暂时无法运行大模型的情况下，先用随机森林替代 LLM 完成组级风险评分，并在 grouped CV 下验证“分组证据 + 外部融合”的结构有效性；该实验不宣称随机森林等价于 LLM，而是为后续替换成 LLM 分组评分提供可复现的低成本预验证基线。
