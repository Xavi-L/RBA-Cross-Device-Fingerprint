# GLM-5.2 官方知识与重复画像扰动验证实验设计

## 1. 实验目标

本实验用于验证两个新增方法是否能提升 HybridGuard 风险评分效果：

1. Google 官方文档知识卡片合入主规则知识库后，是否能让 GLM-5.2 更准确地理解字段语义、规则边界和容错条件。
2. 针对重复设备画像的数据分组、样本降权和训练 fold 内运行时扰动，是否能提升分组融合模型在未见稳定设备画像上的泛化能力。

当前已有 GLM-5.2 direct scoring 在完整 holdout 上达到 `263 / 265 = 99.25%` 风险区间匹配，因此本实验不只追求总体命中率的微小提升，而重点观察以下更有解释力的指标：

- 边界样本是否减少误判。
- 高风险样本召回是否保持稳定。
- 模型理由是否更符合规则族和官方字段语义。
- 分组融合权重是否更稳定。
- 重复设备画像是否不再支配训练损失。

## 2. 待验证假设

### H1：官方知识卡片提升规则理解和容错边界

Google 官方文档本身不提供本项目的风险分数阈值，但能支撑字段语义、安全背景和合理容错边界。例如 WebView、JSBridge、User-Agent、传感器、Battery、WebGL、debuggable 和 cleartext 等字段的含义更加明确。

预期效果：

- GLM-5.2 对低风险但带弱开发配置的样本更谨慎，不轻易升为中高危。
- reason 更容易命中正确规则族。
- 不会错误声称当前数据中不存在的 Play Integrity、Key Attestation、WebView URL/origin 等 future-only 证据。

### H2：重复画像处理提升未见设备画像泛化

真实设备池和云测平台会产生大量会话样本，但稳定设备画像数量有限。如果同一设备画像重复出现在训练中，会放大该画像对损失函数的影响；如果同一画像同时进入训练和测试，还会导致评估泄漏。

预期效果：

- 使用 `stable_device_key` 作为 grouped CV 边界后，评估更接近未见设备画像场景。
- 使用 `sample_weight = 1 / group_size` 后，重复画像不会过度主导融合权重。
- 训练 fold 内运行时扰动可以提升模型对会话级波动的稳定性。

## 3. 数据与基线

数据源为：

```text
training/scored_data.jsonl
```

每条样本包含：

- `android_native_data`
- `webview_data`
- `web_data`
- `llm_label.risk_score`
- `llm_label.risk_reason`

已有基线：

- GLM-5.2 direct scoring full holdout：风险区间匹配 `263 / 265 = 99.25%`。
- 随机森林 grouped-fusion proxy：已证明“组级子分数 + Positive ElasticNet”优于简单平均和六组特征直接堆叠，但尚未超过 tri-layer direct RF。

因此，本实验将 direct scoring 和 grouped-fusion 分开验证。

## 4. 实验一：Google 官方知识卡片消融

### 4.1 对照版本

| 版本 | 规则库 | 说明 |
|---|---|---|
| K0 | `rule_kb_no_official_ablation.json` | 从当前规则库中移除 `official_knowledge` 和 `external_knowledge_base`，保留所有触发规则、分数区间和一票否决逻辑 |
| K1 | `scoring/rule_knowledge_base.json` | 当前已合入 Google 官方知识卡片的主规则知识库 |

K0/K1 的差别只在官方知识元数据。这样可以把实验结论限定为“官方知识是否帮助 GLM 理解规则”，而不是混入规则重调或阈值变化。

### 4.2 样本集

| 样本集 | 作用 |
|---|---|
| full holdout | 与既有 `zhipu_glm_eval` 结果对齐，观察整体区间匹配 |
| boundary set | 重点观察 `15/20/35/38/40/42/45` 这些低危、云测、测试机架边界分 |
| rule-targeted set | 按 `core_integrity`、`native_webview`、`physical_runtime`、`attack_scenario`、`tolerance`、`tri_layer` 抽样，检查具体规则族 |

### 4.3 调用方式

模型固定为：

```text
glm-5.2
```

生成参数固定为：

```text
temperature = 0.1
response_format = json_object
thinking = disabled
```

输出 schema 固定为：

```json
{
  "risk_score": 0,
  "risk_reason": "一句中文短理由"
}
```

若做分组评分，输出 schema 固定为：

```json
{
  "native_web_score": 0,
  "native_webview_score": 0,
  "webview_web_score": 0,
  "tri_layer_score": 0,
  "physical_runtime_score": 0,
  "attack_scenario_score": 0,
  "group_reasons": {
    "native_web": "一句中文短理由",
    "native_webview": "一句中文短理由",
    "webview_web": "一句中文短理由",
    "tri_layer": "一句中文短理由",
    "physical_runtime": "一句中文短理由",
    "attack_scenario": "一句中文短理由"
  }
}
```

### 4.4 评价指标

- 五档风险区间匹配率。
- 三档风险区间匹配率。
- MAE / RMSE。
- 高风险 Precision / Recall / F1。
- JSON 解析成功率。
- K1 相对 K0 的 paired improvement / worsened / unchanged 行数。
- reason 中 future-only 证据误引用次数。

### 4.5 成功标准

K1 相对 K0 应满足：

1. full holdout 区间匹配率不下降。
2. 高风险 Recall 不下降。
3. boundary set 中低危弱开发配置误升中危的数量减少或不增加。
4. reason 中不出现对未采集 future-only 证据的误引用。

## 5. 实验二：重复画像降权与训练扰动

### 5.1 stable_device_key

为避免设备画像泄漏，真实设备和云测设备使用稳定身份字段生成 `stable_device_key`：

- Native：`build_fingerprint`、`device_model`、`device_product`、`device_board`、`device_hardware`、`cpu_abi`、`os_api_level`、`build_tags`、`build_type`。
- 屏幕与硬件：物理分辨率、DPI、总内存、传感器数量和核心传感器布尔集合。
- WebView/Web：WebView/Chrome 主版本、UA Android/Chrome 主版本、UA family、GPU family、`canvas_hash`、`hardware_concurrency`、`device_memory`。

脚本攻击类样本使用攻击模板相关稳定字段生成画像键，例如接口重放、无头 PC、廉价模拟器模板。

以下会话状态字段不进入 `stable_device_key`：

- `uptime_ms`
- `avail_memory_gb`
- 电量、电池温度、电压
- `bridge_latency_ms`
- `compute_task_time_ms`
- 语言、时区、网络状态
- 安装时间、更新时间

### 5.2 分组边界

每条样本的最终分组为：

```text
group_id = source_type + "::" + stable_device_key
```

grouped CV 要求同一 `group_id` 不得同时出现在训练 fold 和测试 fold。

### 5.3 样本权重

训练时可启用组内样本降权：

```text
sample_weight_i = 1 / group_size(group_id_i)
```

这样一个稳定设备画像在训练损失中的总权重近似为 1，避免重复采样多的画像主导模型。

### 5.4 运行时扰动

扰动只发生在训练 fold 内，测试 fold 必须保留原始采集数据。

初始扰动字段：

| 字段 | 扰动方式 |
|---|---|
| `android_native_data.uptime_ms` | 乘以 0.70 到 1.30 |
| `android_native_data.avail_memory_gb` | 乘以 0.85 到 1.15 |
| `android_native_data.battery_level_pct` | 加减 12，限制 0 到 100 |
| `android_native_data.battery_temp_celsius` | 加减 2.5 摄氏度，限制 15 到 55 |
| `android_native_data.battery_voltage_mv` | 加减 80 mV，限制 3000 到 5000 |
| `webview_data.bridge_latency_ms` | 乘以 0.70 到 1.50 |
| `web_data.compute_task_time_ms` | 乘以 0.70 到 1.50 |

不扰动以下可能改变真实场景判断的字段：

- `installer_package`
- `timezone_offset`
- `language`
- `user_agent`
- `webgl_renderer`
- `canvas_hash`
- `build_fingerprint`
- 设备型号、CPU、屏幕、传感器集合

### 5.5 融合实验矩阵

| 配置 | 样本权重 | 训练 fold 扰动 | 测试 fold |
|---|---:|---:|---|
| D0 | 否 | 否 | 原始样本 |
| W1 | 是 | 否 | 原始样本 |
| P1 | 否 | 是 | 原始样本 |
| WP | 是 | 是 | 原始样本 |

融合模型为：

```text
Positive ElasticNet
```

输入为六组 GLM 风险子分数：

```text
native_web_score
native_webview_score
webview_web_score
tri_layer_score
physical_runtime_score
attack_scenario_score
```

`alpha` 和 `l1_ratio` 通过内层 grouped CV 选择。

## 6. 总体 2x4 实验矩阵

最终组合为：

| 知识版本 | 融合训练策略 |
|---|---|
| K0 无官方知识 | D0 / W1 / P1 / WP |
| K1 官方知识 | D0 / W1 / P1 / WP |

这个矩阵可以回答三个问题：

1. 官方知识是否提升 GLM 分组子分数质量。
2. 重复画像降权和训练扰动是否提升外部融合泛化。
3. 官方知识与重复画像处理叠加后是否有额外收益。

## 7. 输出产物

本目录输出：

- `rule_kb_no_official_ablation.json`
- `group_metadata.csv`
- `validation_sample_manifest.csv`
- `targeted_sample_manifest.csv`
- `llm_group_evidence.jsonl`
- `llm_group_evidence_augmented.jsonl`
- `perturbation_plan.json`
- `outputs/knowledge_ablation/*`
- `outputs/group_fusion/*`

其中：

- `group_metadata.csv` 用于说明重复画像数量、组大小和样本权重。
- `validation_sample_manifest.csv` 用于选择 full holdout、boundary set 和 rule-targeted set。
- `llm_group_evidence_augmented.jsonl` 只用于训练 fold 内增强，不进入测试 fold。
- `fusion_weights.csv` 用于解释六组证据的贡献。

## 8. 汇报口径

建议向导师这样表述：

> 本实验将官方文档知识和重复画像处理拆成两个可验证问题。官方知识消融只移除/保留规则库中的官方依据元数据，不改变规则触发和分数阈值，用 paired ablation 观察 GLM-5.2 的规则理解和容错边界是否改善。重复画像处理则通过 stable_device_key 做 grouped CV，避免同一稳定设备画像跨训练和测试泄漏，并通过组内样本降权和训练 fold 内运行时扰动，验证分组融合模型在未见设备画像上的泛化稳定性。

如果结果提升明显，可以写成：

> Google 官方知识主要改善模型对字段语义和容错边界的解释一致性；重复画像降权和训练扰动主要改善未见稳定设备画像上的泛化稳定性。二者分别作用于 LLM 语义评分阶段和外部融合训练阶段，具有互补性。

如果结果提升不明显，也可以写成：

> 在当前 GLM-5.2 direct scoring 已接近风险区间天花板的情况下，官方知识和扰动增强没有显著改变总体命中率，但它们仍提供了更清晰的可解释依据、更严格的无泄漏评估边界，以及后续扩展大规模云测数据时可复用的实验框架。
