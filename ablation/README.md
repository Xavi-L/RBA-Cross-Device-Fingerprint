# Ablation Experiments

本目录保存三端设备指纹消融实验的脚本、固定划分、预测明细、指标表和图表。实验代码只读取 `training/scored_data.jsonl`，所有输出都写在 `ablation/` 下，不修改原有训练脚本、Android 工程或后端代码。

## 实验目标

HybridGuard 的论文重点不是证明某个机器学习算法更强，而是证明 Android Native、WebView 宿主容器、Web 前端运行环境之间存在可对齐、可互证、可发现矛盾的跨层语义关系。

因此本目录包含两类消融：

1. 粗粒度三端消融：直接比较 Native、WebView、Web 单端/双端/三端特征组合。
2. 跨层一致性消融：先把三端之间的宽松语义比对结果编码为显式一致性特征，再比较原始特征和一致性特征的效果。

第一类实验回答“每一端原始特征的信息量如何”；第二类实验回答“跨层语义比对本身是否是有效风险信号”。第二类更贴合论文主线。

## 公共设置

- 输入数据：`training/scored_data.jsonl`
- 样本数：1323
- 标签：`llm_label.risk_score`
- 模型：`RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)`
- 划分：固定 80/20 holdout，训练集 1058 条，测试集 265 条
- 高风险阈值：`risk_score >= 80`
- 主要回归指标：MAE、RMSE、R2
- 辅助分类指标：高风险 Precision、Recall、F1、Accuracy

随机森林参数与 `training/train_randomforest.py` 保持一致。所有实验组共用同一份训练/测试索引，索引保存于 `holdout_split_indices.json` 和 `consistency_holdout_split_indices.json`，方便复现和横向比较。

运行命令：

```bash
conda run -n cross-device-fingerprint python ablation/run_randomforest_ablation.py
conda run -n cross-device-fingerprint python ablation/run_consistency_ablation.py
conda run -n cross-device-fingerprint python ablation/run_grouped_ablation.py
conda run -n cross-device-fingerprint python ablation/make_figures.py
```

其中 `run_grouped_ablation.py` 是更推荐用于论文主实验的版本。它使用分组交叉验证，避免同一设备或同一攻击模板的近似样本同时出现在训练集和测试集中。前两个脚本是快速 holdout 版本，适合作为开发期检查和对照。

`make_figures.py` 会根据已有实验 CSV 生成论文和答辩用的五张主图，输出到 `figures/` 目录。每张图的用途、数据来源和讲解口径见 `figure_guide.md`。

## 实验一：粗粒度三端消融

脚本：[run_randomforest_ablation.py](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/ablation/run_randomforest_ablation.py)

输出：

- `ablation_summary.csv` / `ablation_summary.json`：指标汇总
- `ablation_predictions.csv`：每个测试样本在每个消融组下的预测结果
- `ablation_error_metrics.png`：MAE/RMSE 对比图
- `ablation_high_risk_f1.png`：高风险 F1 与特征数对比图

### 实验步骤

1. 读取 `training/scored_data.jsonl` 并用 `pandas.json_normalize` 展平嵌套 JSON。
2. 按字段前缀划分三端特征：Native 为 `android_native_data.*`，共 33 维；WebView 为 `webview_data.*`，共 14 维；Web 为 `web_data.*`，共 18 维。
3. 构造 7 个特征组合：三种单端、三种双端、完整三端。
4. 对每个组合单独训练随机森林，并在同一测试集上评估。

### 结果

| 配置 | 特征数 | MAE | RMSE | R2 | 高风险 F1 |
|---|---:|---:|---:|---:|---:|
| Native only | 33 | 1.222 | 2.198 | 0.9933 | 1.000 |
| WebView only | 14 | 1.139 | 1.537 | 0.9967 | 1.000 |
| Web only | 18 | 1.416 | 2.377 | 0.9922 | 1.000 |
| Native + WebView | 47 | 1.129 | 1.515 | 0.9968 | 1.000 |
| Native + Web | 51 | 1.219 | 2.177 | 0.9934 | 1.000 |
| WebView + Web | 32 | 1.131 | 1.537 | 0.9967 | 1.000 |
| Native + WebView + Web | 65 | 1.140 | 1.544 | 0.9967 | 1.000 |

### 结果解释

完整三端并没有在 MAE/RMSE 上成为绝对最优，双端组合 `Native + WebView` 和 `WebView + Web` 的误差甚至略低。这不是反常现象，而是说明当前数据中三端原始特征存在较强冗余和代理关系：

- Native 的设备型号、Android 版本、屏幕密度会反映到 Web UA、Web DPR、逻辑分辨率。
- WebView provider 版本会反映到 Web UA 的 Chrome/WebView 版本。
- WebView 宿主特征中包含安装来源、JSBridge、debuggable、target SDK 等强规则信号。
- 当前 LLM 标签逻辑中，传感器数量、JSBridge、ADB、安装来源、电量等少数强特征对风险分影响很大。

因此，简单删除某一端并不一定造成明显性能下降。这个实验更适合用来说明“按端粗删不能充分体现三端融合价值”，从而引出第二类实验：跨层一致性特征消融。

## 实验二：跨层一致性消融

脚本：[run_consistency_ablation.py](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/ablation/run_consistency_ablation.py)

输出：

- `consistency_features.csv`：每条样本构造出的 38 个跨层一致性特征
- `consistency_feature_rules.md`：跨层一致性特征构造规则的自然语言说明
- `consistency_feature_dictionary.csv`：一致性特征分组说明
- `consistency_ablation_summary.csv` / `consistency_ablation_summary.json`：指标汇总
- `consistency_ablation_predictions.csv`：预测明细
- `consistency_feature_importance.csv`：完整特征重要性
- `consistency_top_feature_importance.csv`：各实验组 Top 特征重要性
- `consistency_ablation_error_metrics.png`：MAE/RMSE 对比图
- `consistency_ablation_high_risk_f1.png`：高风险 F1 与特征数对比图

### 核心思路

随机森林本身不能理解“宽松语义匹配”。本实验先用规则把跨层关系转成数值特征，再交给随机森林学习这些关系特征与风险分之间的映射。

处理流程：

```text
三端原始特征
    -> 宽松语义解析与比对
    -> consistency_* 数值特征
    -> 随机森林回归 risk_score
```

例如，屏幕一致性不是要求完全相等，而是比较：

```text
Native 物理分辨率 ~= Web 逻辑分辨率 x Web DPR
```

并允许状态栏、导航栏、安全区带来的误差。GPU 一致性也不是字符串相等，而是把 `qcom/Qualcomm` 与 `Adreno`、`mt/MediaTek` 与 `Mali/PowerVR`、`Kirin/Huawei` 与 `Mali/Maleoon` 等关系编码为宽松匹配分。

### 一致性特征分组

| 分组 | 特征数量 | 语义 |
|---|---:|---|
| Native-Web | 18 | Android 底层环境与 Web JS 暴露环境是否一致 |
| Native-WebView | 8 | Android 底层环境与 App/WebView 宿主是否一致 |
| WebView-Web | 5 | WebView 容器与 Web 前端运行环境是否一致 |
| Tri-layer semantic | 7 | 三端共同参与的核心风险规则和综合一致性分 |

代表性特征：

| 特征 | 含义 |
|---|---|
| `consistency_native_web_model_ua_strength` | Native 设备型号/product/board/brand 在 Web UA 中的宽松匹配强度 |
| `consistency_native_web_android_version_delta` | Native Android 版本与 Web UA Android 版本差异 |
| `consistency_native_web_screen_score` | 物理屏幕、Web 逻辑屏幕、DPR 的软一致性分 |
| `consistency_native_web_gpu_family_score` | Native 硬件族与 WebGL GPU 族的宽松匹配分 |
| `consistency_native_webview_agent_model_match` | Native 设备型号是否出现在 WebView system HTTP agent |
| `consistency_webview_web_chrome_major_match` | WebView provider 与 Web UA Chrome 主版本是否一致 |
| `consistency_tri_layer_sensor_bridge_fail` | 传感器严重缺失或 JSBridge 未注入的核心完整性失败 |
| `consistency_tri_layer_manual_timezone_or_adb` | manual 安装来源与时区/ADB 组合风险 |

### 实验组

| 配置 | 含义 |
|---|---|
| Raw all | 三端原始 65 维特征 |
| Raw cleaned | 去掉高基数身份字段和直接对齐字段后的原始特征 |
| Consistency only | 只使用 38 个跨层一致性特征 |
| Raw all + Consistency | 原始三端特征 + 一致性特征 |
| Raw cleaned + Consistency | 清理后的原始特征 + 一致性特征 |
| Native-Web consistency | 只使用 Native-Web 一致性特征 |
| Native-WebView consistency | 只使用 Native-WebView 一致性特征 |
| WebView-Web consistency | 只使用 WebView-Web 一致性特征 |
| Tri-layer semantic | 只使用三端语义规则特征 |

其中 `Raw cleaned` 删除了容易被随机森林直接记忆或直接完成对齐的字段，例如 `build_fingerprint`、`user_agent`、`canvas_hash`、屏幕分辨率、DPR、WebView provider version、WebGL renderer 等。这个配置用于观察：去掉高基数字符串和直接身份字段后，显式一致性特征是否仍然有价值。

### 结果

| 配置 | 特征数 | MAE | RMSE | R2 | 高风险 F1 |
|---|---:|---:|---:|---:|---:|
| Raw all | 65 | 1.140 | 1.544 | 0.9967 | 1.000 |
| Raw cleaned | 40 | 1.137 | 1.520 | 0.9968 | 1.000 |
| Consistency only | 38 | 1.103 | 1.473 | 0.9970 | 1.000 |
| Raw all + Consistency | 103 | 1.108 | 1.501 | 0.9969 | 1.000 |
| Raw cleaned + Consistency | 78 | 1.107 | 1.496 | 0.9969 | 1.000 |
| Native-Web consistency | 18 | 1.438 | 2.745 | 0.9895 | 1.000 |
| Native-WebView consistency | 8 | 2.479 | 4.591 | 0.9708 | 1.000 |
| WebView-Web consistency | 5 | 8.079 | 10.514 | 0.8467 | 1.000 |
| Tri-layer semantic | 7 | 1.111 | 1.469 | 0.9970 | 1.000 |

### 结果解释

`Consistency only` 的 MAE/RMSE 优于 `Raw all`，说明跨层一致性特征不是单纯的解释性附属信息，而是可以直接被轻量模型吸收的有效风险信号。这一点比粗粒度三端消融更能支撑论文主张：系统贡献不只是采集更多字段，而是把三端之间的语义关系显式建模。

`Raw all + Consistency` 和 `Raw cleaned + Consistency` 没有显著优于 `Consistency only`。这说明当前标签逻辑下，显式一致性特征已经覆盖了主要风险判断信息；加入更多原始字段后，随机森林没有获得明显额外收益，反而可能引入冗余特征和轻微噪声。

分组结果也很有解释价值：

- `Native-Web consistency` 单独使用时 MAE 为 1.438，说明底层系统与 Web 暴露环境的一致性具备较强独立判别力。
- `Native-WebView consistency` 单独使用时 MAE 为 2.479，说明 App/WebView 宿主真实性有用，但单独不足以完整拟合风险分。
- `WebView-Web consistency` 单独使用时 MAE 为 8.079，说明只看 WebView provider 与 Web UA/JSBridge 的关系信息量不足，需要 Native 侧参与。
- `Tri-layer semantic` 仅 7 个特征就达到 MAE 1.111、RMSE 1.469，说明三端共同参与的核心语义规则高度贴近当前 LLM 风险标签。

因此，实验结论不是“字段越多越好”，而是：

> 三端原始特征之间存在大量冗余，但这种冗余正是跨层互证的基础。将 Native、WebView、Web 之间的可对齐关系显式编码后，少量一致性特征即可达到甚至略优于完整原始特征的风险分拟合效果，证明跨层语义比对是系统有效性的核心来源。

### 特征重要性

在 `Consistency only` 组中，随机森林最依赖的特征包括：

| 特征 | 重要性 | 解释 |
|---|---:|---|
| `consistency_tri_layer_sensor_bridge_fail` | 0.1518 | 传感器严重缺失或 JSBridge 未注入，对高风险样本非常关键 |
| `consistency_native_webview_debug_cleartext_tension` | 0.1017 | debug 与明文网络配置共同反映测试/调试宿主特征 |
| `consistency_native_web_model_ua_strength` | 0.0850 | Native 设备身份与 Web UA 是否能相互印证 |
| `consistency_tri_layer_failure_count` | 0.0844 | 多个一致性检查失败的聚合信号 |
| `consistency_webview_web_ua_has_wv_token` | 0.0843 | Web UA 是否呈现 WebView 运行时特征 |
| `consistency_native_web_model_ua_match` | 0.0839 | Native 型号是否与 Web UA 直接匹配 |
| `consistency_tri_layer_manual_timezone_or_adb` | 0.0749 | manual 安装来源结合时区或 ADB 的云机房风险 |

这些 Top 特征说明随机森林确实在利用“比对后的语义关系”，而不是只依赖原始字符串或单端字段。

## 实验三：分组交叉验证

脚本：[run_grouped_ablation.py](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/ablation/run_grouped_ablation.py)

输出：

- `grouped_ablation_summary.csv` / `grouped_ablation_summary.json`：分组交叉验证后的指标均值与标准差。
- `grouped_ablation_fold_metrics.csv`：每个配置在每一折上的具体指标。
- `grouped_ablation_predictions.csv`：每个测试样本的预测明细。
- `grouped_sample_metadata.csv`：每条样本的 `source_type`、`group_id` 和所在 fold。
- `grouped_fold_source_distribution.csv`：每一折测试集中的三类样本分布。
- `grouped_source_group_summary.csv`：每个分组的大小、来源类型和样本摘要。
- `grouped_coarse_error_metrics.png`：粗粒度消融的分组交叉验证图。
- `grouped_consistency_error_metrics.png`：一致性消融的分组交叉验证图。

### 为什么需要分组

当前数据来自三类来源：

| 来源类型 | 含义 | 识别逻辑 |
|---|---|---|
| `physical_device` | 真实物理设备 | 非 manual 安装、无明显脚本/模拟器特征、ADB/时区等未命中云测启发式 |
| `cloud_device` | 云测真机或测试机架设备 | `installer_package=manual`，或时区为 UTC，或 ADB 开启 |
| `script_attack` | 黑产脚本/模拟器/无头环境 | `python-requests`、Windows/Headless UA、JSBridge 缺失、传感器严重缺失、goldfish/ranchu/x86/SwiftShader 等 |

普通随机 holdout 是按“行”随机切分。如果同一台设备的扩充样本、同一台云测设备的相似样本、同一攻击模板生成的样本同时出现在训练集和测试集，模型会在测试时见到高度相似的数据，指标容易偏乐观。

分组交叉验证改为按 `group_id` 切分：

```text
同一 group_id 的所有样本只能进入同一个测试 fold 或训练 fold
```

分组策略：

| 来源类型 | group_id 构造方式 |
|---|---|
| `physical_device` | `build_fingerprint + device_model + screen_resolution_physical + user_agent + canvas_hash` 的稳定哈希 |
| `cloud_device` | 同上，按云测设备/系统/WebView/渲染指纹形成设备组 |
| `script_attack` | 按攻击模板分为 `api_replay`、`headless_pc`、`cheap_emulator` |

由于脚本攻击样本当前只有三个主模板，分组实验采用 3 折。脚本中显式保证每折测试集都有一个未见脚本模板，同时真实设备和云测设备按组分布到三折。

### 每折分布

| Fold | physical_device | cloud_device | script_attack |
|---:|---:|---:|---:|
| 1 | 82 rows / 21 groups | 290 rows / 23 groups | 104 rows / 1 group |
| 2 | 128 rows / 21 groups | 236 rows / 28 groups | 97 rows / 1 group |
| 3 | 76 rows / 23 groups | 211 rows / 26 groups | 99 rows / 1 group |

这说明每个测试 fold 都覆盖真实物理设备、云测真机设备和黑产脚本数据三类场景，同时避免了同组样本跨训练/测试泄漏。

### 分组版粗粒度消融结果

| 配置 | 特征数 | MAE 均值 | MAE 标准差 | RMSE 均值 | 高风险 F1 均值 |
|---|---:|---:|---:|---:|---:|
| Native only | 33 | 2.799 | 1.541 | 4.774 | 0.667 |
| WebView only | 14 | 1.541 | 0.435 | 2.643 | 1.000 |
| Web only | 18 | 12.188 | 7.175 | 23.381 | 0.333 |
| Native + WebView | 47 | 2.202 | 0.840 | 3.767 | 1.000 |
| Native + Web | 51 | 6.573 | 3.757 | 12.522 | 0.333 |
| WebView + Web | 32 | 3.053 | 0.994 | 5.100 | 0.978 |
| Native + WebView + Web | 65 | 2.642 | 1.004 | 4.455 | 1.000 |

与随机 holdout 相比，分组后的误差明显上升，尤其 `Web only` 和 `Native + Web` 下降明显。这说明随机 holdout 的确存在同源样本带来的乐观估计。WebView-only 在当前数据集上表现较强，主要是因为 WebView 层包含 `jsbridge_injected`、安装来源、debuggable、SDK 版本、安装时间等与当前规则标签高度相关的强信号。

### 分组版一致性消融结果

| 配置 | 特征数 | MAE 均值 | MAE 标准差 | RMSE 均值 | 高风险 F1 均值 |
|---|---:|---:|---:|---:|---:|
| Raw all | 65 | 2.642 | 1.004 | 4.455 | 1.000 |
| Raw cleaned | 40 | 2.617 | 1.426 | 4.723 | 0.680 |
| Consistency only | 38 | 3.388 | 1.265 | 5.735 | 0.333 |
| Raw all + Consistency | 103 | 3.407 | 1.447 | 5.831 | 0.519 |
| Raw cleaned + Consistency | 78 | 3.331 | 1.777 | 5.846 | 0.667 |
| Native-Web consistency | 18 | 12.733 | 3.042 | 21.783 | 0.333 |
| Native-WebView consistency | 8 | 2.608 | 0.353 | 4.408 | 1.000 |
| WebView-Web consistency | 5 | 7.792 | 0.563 | 10.486 | 1.000 |
| Tri-layer semantic | 7 | 2.281 | 0.466 | 3.358 | 1.000 |

这个结果比快速版更保守，也更有解释力。`Tri-layer semantic` 仅用 7 个三端语义特征就取得 MAE 2.281、RMSE 3.358，优于 `Raw all` 的 MAE 2.642、RMSE 4.455。说明即使在按设备/模板分组的更严格评估下，三端核心语义规则仍然具备较强泛化能力。

同时，`Consistency only` 整体不再优于 `Raw all`，说明当测试集包含未见脚本模板时，仅靠全部一致性特征未必能稳定泛化。更稳的是三端语义规则特征本身，尤其是传感器与 JSBridge 完整性、manual 安装来源与时区/ADB、ADB 与满电等规则。这也符合当前标签生成逻辑。

因此，分组实验给出的主结论应调整为：

> 随机 holdout 下，一致性特征可以达到甚至略优于原始三端特征；在更严格的分组交叉验证下，三端语义规则特征仍然优于完整原始特征，说明跨层一致性建模不是依赖同源样本记忆，而是具有一定未见设备/未见模板泛化能力。

## 如何看待高风险 F1

快速 holdout 中高风险 F1 基本都是 1.0。这说明当前数据集中的高风险样本在规则/LLM 标签体系下具有很强的显性特征，例如传感器严重缺失、JSBridge 未注入、Windows/Headless UA、manual 安装来源、ADB 与满电组合等。对于随机划分下的 `risk_score >= 80` 二分类任务，这些特征已经足够清晰。

分组交叉验证后，部分配置的高风险 F1 会下降，例如 Web only、Native + Web、Consistency only 等。这说明当同源设备和同源模板不再跨训练/测试泄漏时，模型对未见攻击模板的泛化难度明显上升。因此论文中不宜只看快速版 F1，更推荐重点分析：

- MAE/RMSE：不同特征组对连续风险分的拟合能力。
- 特征重要性：随机森林是否真正使用跨层一致性特征。
- 分组对比：Native-Web、Native-WebView、WebView-Web 各自贡献差异。

## 可写入论文的结论表达

可以采用如下表述：

> 按端粗粒度消融时，完整三端特征与部分双端组合在 MAE/RMSE 上差异较小。这说明三端原始特征之间存在较强相关性，某一端的字段往往可作为另一端状态的代理变量。因此，简单删除某一端并不能充分体现三端融合的核心价值。

> 进一步地，本文将三端之间的语义对齐关系显式编码为跨层一致性特征，包括设备型号与 UA 的宽松匹配、Android 版本一致性、屏幕分辨率与 DPR 的软一致性、WebView provider 与 UA Chrome 版本一致性、硬件族与 WebGL GPU 的宽松匹配、JSBridge 与 App 宿主真实性等。实验结果显示，仅使用 38 个一致性特征即可取得 MAE 1.103、RMSE 1.473，优于完整原始三端特征的 MAE 1.140、RMSE 1.544。这表明跨层语义比对是风险判断中的有效信息来源，也验证了本文系统设计中“三端融合不是简单拼接字段，而是建立可互证的语义关系”的核心观点。

> 为进一步避免数据扩充和模板化生成造成的乐观估计，本文采用分组交叉验证，使同一真实设备、同一云测设备或同一脚本攻击模板的样本不会同时出现在训练集和测试集。分组结果显示，整体误差较随机 holdout 明显上升，说明分组评估更接近未见设备和未见模板泛化场景。在该更严格设置下，三端语义规则特征仍取得 MAE 2.281、RMSE 3.358，优于完整原始三端特征的 MAE 2.642、RMSE 4.455，进一步说明跨层一致性建模不是依赖同源样本记忆，而是具备一定泛化能力。

## 局限与后续改进

当前已经包含快速 holdout 与分组交叉验证两个版本。论文主结果建议使用分组交叉验证，快速 holdout 作为对照或开发过程说明。后续如果继续增强实验，可考虑：

1. 跨层矛盾专项集：专门构造 Native、WebView、Web 互相矛盾的样本，例如 Native 是 Android 真机但 Web UA 是 Windows/Headless。
2. 更多真实端侧样本：减少模拟样本模板对特征重要性的影响。
3. 阈值敏感性分析：尝试 `risk_score >= 60/70/80` 的高风险阈值，避免单一阈值下 F1 过于饱和。
4. 显式来源标签：采集阶段直接记录 `source_type` 和 `template_id`，减少当前启发式分组的不确定性。

这些改进不会改变当前结论方向，但可以让实验更稳健。
