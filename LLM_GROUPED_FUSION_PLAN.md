# LLM 分组证据融合实验方案

本文档沉淀后续从随机森林转向大语言模型时的特征组织、分组评分、权重学习和消融实验设计。核心目标不是简单增加字段数量，而是把更多原始字段整理成可解释的分组证据，再用可复现的外部融合模型学习各组贡献。

## 背景结论

当前三端原始特征共 65 维：

- Native：33 维
- WebView：14 维
- Web：18 维

已有一致性消融说明，特征并不是越多越好。随机 holdout 下，`Raw all + Consistency` 的 103 维组合略优于原始 65 维；但在更严格的 grouped CV 下，只有 7 维的 `Tri-layer semantic` 反而表现最好：

| 配置 | 特征数 | grouped CV MAE | grouped CV RMSE | 高风险 F1 |
|---|---:|---:|---:|---:|
| Raw all | 65 | 2.642 | 4.455 | 1.000 |
| Raw all + Consistency | 103 | 3.407 | 5.831 | 0.519 |
| Native-WebView consistency | 8 | 2.608 | 4.408 | 1.000 |
| Tri-layer semantic | 7 | 2.281 | 3.358 | 1.000 |

因此后续实验不应追求“所有字段直接拼接后一定更强”，而应验证：

> 更多字段能否作为分组证据池，被 LLM 和组级融合模型有效吸收；同时，模型是否会自动把高泛化价值的 tri-layer 语义证据赋予更高权重。

## 总体流程

推荐使用“LLM 分组评分 + 外部权重融合”的混合结构：

```text
三端原始字段
  -> 规则脚本提取分组证据摘要
  -> LLM 对每组证据分别输出风险子分数
  -> ElasticNet 学习组级融合权重
  -> 输出 final_score 和可解释 reason
```

不要让 LLM 直接看完整 JSON 后隐式决定总分。更稳的方式是让 LLM 负责语义判断，让外部模型负责可复现的权重融合。

## 分组设计

初始可以设置 6 个分组：

| 分组 | 子分数 | 主要含义 |
|---|---|---|
| Native-Web | `native_web_score` | Native 底层设备信息与 Web JS 暴露环境是否一致 |
| Native-WebView | `native_webview_score` | Native 设备身份与 App/WebView 宿主信息是否一致 |
| WebView-Web | `webview_web_score` | WebView 内核、UA、JS 运行时是否一致 |
| Tri-layer semantic | `tri_layer_score` | 三端共同参与的核心完整性和高风险组合规则 |
| Physical runtime | `physical_runtime_score` | 传感器、电池、内存、算力、GPU 等物理运行环境可信度 |
| Attack scenario | `attack_scenario_score` | 脚本重放、无头浏览器、模拟器、云测/测试机架等攻击场景证据 |

每组子分数统一定义为：

```text
0   = 低风险 / 一致 / 没有异常
100 = 高风险 / 明显矛盾 / 强攻击证据
```

这个方向必须统一，否则后续非负权重就没有解释意义。

## LLM 输出格式

LLM 每次只输出结构化 JSON，避免自然语言难以解析：

```json
{
  "native_web_score": 10,
  "native_webview_score": 25,
  "webview_web_score": 5,
  "tri_layer_score": 15,
  "physical_runtime_score": 20,
  "attack_scenario_score": 8,
  "group_reasons": {
    "native_web": "Native 型号和 Web UA 基本一致，屏幕/DPR 误差可接受。",
    "native_webview": "JSBridge 存在，但 manual 安装和 debuggable 提供弱测试环境信号。",
    "webview_web": "WebView provider 与 UA Chrome 主版本一致。",
    "tri_layer": "传感器数量充足且 JSBridge 存在，核心完整性通过。",
    "physical_runtime": "电池、内存、算力和 WebGL 表现符合移动端。",
    "attack_scenario": "未命中脚本重放、无头浏览器或典型模拟器组合。"
  }
}
```

最终原因可以由程序把各组分数、权重和重要原因传回 LLM 生成，也可以直接模板化生成。关键是：总分权重不要藏在 prompt 里。

## 权重学习

融合模型使用组级子分数作为输入：

```text
final_score =
  w1 * native_web_score
+ w2 * native_webview_score
+ w3 * webview_web_score
+ w4 * tri_layer_score
+ w5 * physical_runtime_score
+ w6 * attack_scenario_score
+ b
```

推荐主方案：

```text
ElasticNet(positive=True)
```

原因：

- `positive=True` 保证组分数越高，总风险不会反向下降，解释性更强。
- L1 项可以把弱贡献分组压到 0，起到自动选择分组的作用。
- L2 项可以在分组高度相关时平滑权重，避免 Lasso 选择不稳定。
- 相比完全非负归一化权重，ElasticNet 更像正式机器学习方法，适合作为主实验。

同时建议保留两个对照：

| 模型 | 用途 |
|---|---|
| Simple average | 不学习权重的朴素基线 |
| Non-negative simplex | `w_i >= 0` 且 `sum(w_i)=1`，解释性最强的权重基线 |
| Positive ElasticNet | 主方案，自动收缩和选择分组 |
| Unconstrained ElasticNet | 预测性能上限对照，允许负系数但解释性较弱 |

如果无约束模型明显优于非负模型，说明某些组分数方向、样本偏差或组间相关性需要重新检查。

## alpha 和 l1_ratio 选择

`alpha` 和 `l1_ratio` 是超参数，不是一次模型训练中直接学到的参数。它们应通过验证集或交叉验证选择。

推荐使用 nested grouped CV：

```text
for 每个外层 GroupKFold:
    留出一个未见 group 作为外层测试集

    在外层训练集内部:
        对 alpha 和 l1_ratio 做网格搜索
        用内层 GroupKFold 选择 MAE 最低的组合

    用最佳 alpha/l1_ratio 在外层训练集重新训练
    在外层测试集评估最终泛化性能
```

建议初始搜索空间：

```text
l1_ratio = [0.05, 0.1, 0.2, 0.5, 0.7, 0.9, 0.95, 1.0]
alpha    = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]
```

解释口径：

- 最佳 `l1_ratio` 靠近 0：更需要 Ridge 式平滑收缩，说明多个证据组都应保留。
- 最佳 `l1_ratio` 靠近 1：更接近 Lasso，说明模型倾向于自动删掉弱证据组。
- 最佳 `l1_ratio` 位于中间：说明既需要保留多组证据，又需要压低弱组权重。

## 消融实验矩阵

后续至少比较以下配置：

| 实验组 | 输入 | 融合方式 | 目的 |
|---|---|---|---|
| LLM direct | 完整 JSON 或摘要 | LLM 直接总分 | 黑箱上限/对照 |
| Tri-layer only | tri-layer 证据 | 单组分数 | 验证 7 条核心语义规则是否仍最强 |
| All group average | 全部分组子分数 | 简单平均 | 不学习权重的基线 |
| Simplex weighted | 全部分组子分数 | 非负归一权重 | 最强解释性权重基线 |
| Positive ElasticNet | 全部分组子分数 | 非负 ElasticNet | 主方案 |
| Unconstrained ElasticNet | 全部分组子分数 | 无约束 ElasticNet | 预测性能上限对照 |
| Ablated groups | 去掉某一组 | Positive ElasticNet | 判断每组边际贡献 |

评价指标：

- MAE
- RMSE
- R2
- 高风险 Precision / Recall / F1
- grouped CV 均值和标准差
- 学到的组权重稳定性

## 数据泄漏注意事项

权重学习和 `alpha/l1_ratio` 选择都不能在最终测试 fold 上完成。否则会把测试集信息泄漏进模型选择。

必须坚持：

```text
外层 grouped CV 只用于最终评估
内层 grouped CV 才用于选超参数
```

另外，LLM 生成的组分数可以缓存成 CSV/JSONL，但缓存时要保留：

- `session_id`
- `source_type`
- `group_id`
- 各组 score
- 各组 reason
- 使用的模型名
- prompt 版本
- 生成时间

这样后续才能复现实验。

## 字段扩充原则

如果后续挖掘更多原始字段，应优先满足：

- 非常量：top 值占比不要过高。
- 可解释：能映射到设备、宿主、运行时或攻击场景证据。
- 可跨层比对：最好能和另一层字段形成一致性关系。
- 可稳定采集：不同 Android/WebView 版本下缺失率可控。

不建议直接把高基数字符串原样喂给融合模型，例如完整 `user_agent`、完整 `build_fingerprint`、完整 `canvas_hash`。更好的做法是解析为语义变量：

- Android 主版本
- Chrome/WebView 主版本
- 是否包含 `wv`
- 是否 headless / python-requests
- 硬件族
- GPU 族
- 是否模拟器关键词

## 推荐实现步骤

1. 新增脚本生成分组证据摘要，例如 `ablation/run_llm_grouped_fusion.py`。
2. 复用现有 `group_id` 划分逻辑，保证 grouped CV 一致。
3. 为每条样本生成 LLM 分组子分数，并缓存为 `ablation/llm_group_scores.csv`。
4. 在缓存的组分数上实现 ElasticNet nested grouped CV。
5. 导出：
   - `llm_grouped_fusion_summary.csv`
   - `llm_grouped_fusion_fold_metrics.csv`
   - `llm_grouped_fusion_weights.csv`
   - `llm_grouped_fusion_predictions.csv`
6. 和现有 `Raw all`、`Raw all + Consistency`、`Tri-layer semantic` 结果横向比较。

## 论文表达口径

可以这样概括：

> 在随机森林消融中，简单增加一致性特征并不必然提升分组泛化性能，说明跨层设备指纹中存在显著冗余和组间相关性。为进一步利用大语言模型的语义判断能力，本文将三端字段整理为若干跨层证据组，由大语言模型分别生成组级风险分数，再通过带非负约束的 ElasticNet 学习组级融合权重。该设计既避免了 prompt 内部隐式加权，也保留了各证据组对最终风险评分的可解释贡献。

如果最终 ElasticNet 权重主要集中在 `tri_layer_score`，这不是失败，而可以解释为：

> 完整证据池为模型提供了候选信息，但在严格的 grouped CV 设置下，模型自动收敛到少量三端语义核心证据，说明真正稳定泛化的风险信号来自跨层核心完整性，而不是字段数量本身。
