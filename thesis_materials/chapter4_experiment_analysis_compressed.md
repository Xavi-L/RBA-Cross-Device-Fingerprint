# 第 4 章 实验设计与结果分析

本章基于HybridGuard已采集、构造和标注的三端设备指纹数据，对系统有效性进行实验分析。实验重点不是证明某个机器学习算法具有优势，而是验证Android Native、WebView宿主和Web前端三端融合是否能够提供有效风险信息，跨层一致性关系是否能够表达规则知识库中的风险判断逻辑，以及这类语义特征在更严格的分组验证下是否仍具有泛化能力。

## 4.1 实验环境与数据集说明

### 4.1.1 实验环境

本章实验依托HybridGuard原型系统完成。客户端侧包括Android原生采集模块、WebView宿主采集模块和Web前端探针模块；后端侧使用FastAPI接收三端数据，按`session_id`完成会话合并，并将合并结果保存为JSON与JSONL文件；离线侧使用综合规则知识库驱动大模型生成风险标签，再使用轻量模型进行风险分拟合和消融评估。

风险标签生成阶段使用第三章介绍的综合规则知识库。该知识库整合跨层一致性、核心完整性、物理与运行环境、攻击场景聚合和容错规则。大模型在标注时接收三端设备指纹JSON与规则知识库，输出结构化的`risk_score`和`risk_reason`，因此本章风险分是基于规则知识库进行综合分析后得到的连续评分。

轻量评估器采用随机森林回归模型，参数与训练侧和消融实验脚本保持一致：

```text
RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
```

随机森林在本章中的作用是评估不同特征组合对规则知识库风险标签的拟合能力，不作为本文算法创新点。所有消融实验脚本、指标表和图表均保存在`ablation/`目录下。

### 4.1.2 数据来源与样本规模

本章主要实验数据来自`training/scored_data.jsonl`，共 1323 条带风险标签样本。每条样本包含Android Native、WebView宿主和Web前端三类特征，并包含规则知识库驱动的大模型离线标注结果`llm_label.risk_score`。分组脚本根据设备字段、安装来源、调试状态、时区、UA和攻击模板等启发式信息，将样本划分为真实物理设备、云真机/测试环境和脚本攻击三类来源。

| 来源类型 | 样本数 | 分组数 | 含义 |
|---|---:|---:|---|
| `physical_device` | 286 | 65 | 未命中云测和脚本攻击启发式的真实设备类样本 |
| `cloud_device` | 737 | 77 | 安装来源、时区、ADB或云测特征命中测试环境启发式的样本 |
| `script_attack` | 300 | 3 | API重放、无头PC浏览器、廉价模拟器等脚本攻击模板 |

这里需要区分“样本数”和“分组数”。真实样本扩充、云真机采集和脚本攻击模板都可能产生相似样本。如果只按行随机切分，同一设备或同一攻击模板的近似记录可能同时出现在训练集和测试集中，使指标偏乐观。因此，本章除随机holdout外，还采用按`group_id`切分的分组交叉验证。数据来源构成图见`ablation/figures/figure_01_source_distribution.png`。

### 4.1.3 风险标签与分数分布

实验样本中的风险分范围为 0 到 100。根据`training/scored_data.jsonl`中的标签统计，主要分布如下。

| 风险分数 | 样本数 | 解释口径 |
|---:|---:|---|
| 15 | 297 | 低风险正常设备或较可信环境 |
| 20 | 1 | 低风险样本 |
| 35 | 10 | 较低风险但存在轻微异常 |
| 38 | 57 | 低到中风险边界样本 |
| 40 | 55 | 中低风险样本 |
| 42 | 348 | 云真机或测试环境常见中风险样本 |
| 45 | 255 | 云测、调试或轻微异常环境 |
| 92 | 63 | 高风险攻击样本 |
| 95 | 159 | 高风险攻击样本 |
| 98 | 78 | 高风险攻击样本 |

本章将`risk_score >= 80`作为高风险二分类阈值，对应 300 条高风险样本。连续风险分用于计算MAE、RMSE和R2，高风险阈值用于计算Precision、Recall、F1和Accuracy等辅助分类指标。由于标签来自规则知识库驱动的大模型离线标注流程，标签具有规则解释性，但仍需要在后续工作中结合人工复核和真实业务样本继续校准。

### 4.1.4 三端采集字段完整性统计

除已标注训练数据外，`backend_server/collected_data.jsonl`中保存了后端采集链路追加的 808 条有效记录。在这些记录中，样本均包含Native、WebView和Web三端字段，满足后续消融分析对字段完整性的要求。

| 特征层 | 字段数 | 代表字段 |
|---|---:|---|
| Android Native | 33 | 设备型号、品牌、系统版本、CPU ABI、物理屏幕、电池、传感器、ADB状态 |
| WebView宿主 | 14 | JSBridge注入、桥接延迟、WebView Provider、系统UA、安装来源、debuggable |
| Web前端 | 18 | Navigator、逻辑屏幕、DPR、WebGL、Canvas、算力耗时、时区 |

三端字段合计为 65 维原始特征。后续实验中的`Raw all`配置即使用这 65 维原始三端特征作为完整基线。字段完整性统计主要用于说明实验数据具备三端对齐基础，而不是作为大规模端侧稳定性测试结论。

## 4.2 实验目标、实验设计与评估指标

### 4.2.1 实验目标

本章实验围绕三个问题展开：第一，Android Native、WebView宿主和Web前端三端原始特征分别包含多少风险信息；第二，三端之间的跨层一致性关系是否比简单拼接原始字段更能体现系统价值；第三，在避免同源设备或同源攻击模板泄漏后，跨层一致性特征是否仍具有泛化能力。

这三个问题与本文贡献直接对应。本文重点是实现三端融合采集、会话对齐、规则知识库和端侧轻量评分闭环，消融实验用于验证三端数据是否有效、跨层语义关系是否能成为风险信号，以及这些信号在分组场景下是否稳定。

### 4.2.2 评估指标

由于风险标签是 0 到 100 的连续分数，本章以回归指标作为主要评估指标，包括平均绝对误差MAE、均方根误差RMSE和决定系数R2。

```text
MAE = mean(|y_true - y_pred|)
RMSE = sqrt(mean((y_true - y_pred)^2))
R2 = 1 - SSE / SST
```

MAE反映预测风险分与标签风险分之间的平均偏差，RMSE对较大误差更敏感，R2表示模型对风险分方差的解释程度。与此同时，本章将`risk_score >= 80`作为高风险阈值计算Precision、Recall、F1和Accuracy。高风险F1仅作为辅助指标，因为当前高风险样本主要来自规则明确的攻击模板，随机划分下容易出现饱和。

### 4.2.3 数据划分方式

本章使用两种数据划分方式。第一种是随机holdout，固定 80/20 划分，训练集 1058 条，测试集 265 条，随机种子为 42。该划分用于快速比较不同特征组的信息量。

第二种是分组交叉验证。该方法按`group_id`切分数据，同一真实设备、同一云测设备或同一脚本攻击模板不能同时出现在训练集和测试集中。由于脚本攻击样本由 3 个主模板生成，因此采用 3 折分组交叉验证，使每一折测试集都包含一个未见脚本攻击模板，同时包含一定数量的真实设备组和云测设备组。

| Fold | `physical_device` | `cloud_device` | `script_attack` |
|---:|---|---|---|
| 1 | 82 rows / 21 groups | 290 rows / 23 groups | 104 rows / 1 group |
| 2 | 128 rows / 21 groups | 236 rows / 28 groups | 97 rows / 1 group |
| 3 | 76 rows / 23 groups | 211 rows / 26 groups | 99 rows / 1 group |

分组划分比随机holdout更严格，更接近真实部署时遇到新设备和新攻击变体的情况。Fold构成图见`ablation/figures/figure_02_fold_distribution.png`，holdout与分组MAE对比图见`ablation/figures/figure_03_holdout_vs_grouped_mae.png`。

## 4.3 粗粒度三端特征消融实验

### 4.3.1 实验目的与分组

粗粒度三端消融实验直接按照特征来源划分Native、WebView和Web三类原始字段，比较单端、双端和完整三端组合对风险分的拟合效果。

| 配置 | 使用特征 | 特征数 | 实验目的 |
|---|---|---:|---|
| Native only | Android Native | 33 | 验证底层硬件、系统、电池、传感器等信息量 |
| WebView only | WebView宿主 | 14 | 验证JSBridge、安装来源、Provider、宿主安全信息量 |
| Web only | Web前端 | 18 | 验证UA、WebGL、Canvas、DPR、算力等信息量 |
| Native + WebView | Native + WebView | 47 | 验证底层系统与宿主容器组合 |
| Native + Web | Native + Web | 51 | 验证底层系统与前端运行环境组合 |
| WebView + Web | WebView + Web | 32 | 验证宿主容器与前端环境组合 |
| Native + WebView + Web | 三端完整原始特征 | 65 | 完整三端基线 |

该实验属于“按端删除”的直观消融，适合观察每一端原始字段的信息量。但三端原始字段之间存在天然冗余，例如设备型号、系统版本、屏幕、WebView provider和UA会在不同层级中相互体现，因此本节结果还需要结合后续一致性特征实验解释。

### 4.3.2 随机Holdout结果与分析

随机holdout下的粗粒度消融结果如表 4-5 所示。

| 配置 | 特征数 | MAE | RMSE | R2 | 高风险F1 |
|---|---:|---:|---:|---:|---:|
| Native only | 33 | 1.222 | 2.198 | 0.9933 | 1.000 |
| WebView only | 14 | 1.139 | 1.537 | 0.9967 | 1.000 |
| Web only | 18 | 1.416 | 2.377 | 0.9922 | 1.000 |
| Native + WebView | 47 | 1.129 | 1.515 | 0.9968 | 1.000 |
| Native + Web | 51 | 1.219 | 2.177 | 0.9934 | 1.000 |
| WebView + Web | 32 | 1.131 | 1.537 | 0.9967 | 1.000 |
| Native + WebView + Web | 65 | 1.140 | 1.544 | 0.9967 | 1.000 |

所有配置在随机holdout下都取得较低误差，高风险F1均为 1.000。其中WebView only的MAE为 1.139，接近完整三端原始特征；Native + WebView的MAE为 1.129，是该表中最低值；完整三端原始特征的MAE为 1.140，并非绝对最优。

这一结果说明当前数据中的风险标签包含较强规则信号，且三端原始字段之间存在代理关系。WebView层的JSBridge、安装来源、debuggable、Provider和system UA与规则标签高度相关；Native层的设备、系统和屏幕信息也会部分反映到Web UA、DPR和WebGL。随机划分下，同源样本可能同时出现在训练集和测试集中，因此粗粒度消融的结论不是“字段越多越好”，而是“按端删除不足以体现三端融合的核心价值”。

### 4.3.3 分组交叉验证结果与分析

在分组交叉验证下，粗粒度消融结果更加保守。

| 配置 | 特征数 | MAE均值 | MAE标准差 | RMSE均值 | 高风险F1均值 |
|---|---:|---:|---:|---:|---:|
| Native only | 33 | 2.799 | 1.541 | 4.774 | 0.667 |
| WebView only | 14 | 1.541 | 0.435 | 2.643 | 1.000 |
| Web only | 18 | 12.188 | 7.175 | 23.381 | 0.333 |
| Native + WebView | 47 | 2.202 | 0.840 | 3.767 | 1.000 |
| Native + Web | 51 | 6.573 | 3.757 | 12.522 | 0.333 |
| WebView + Web | 32 | 3.053 | 0.994 | 5.100 | 0.978 |
| Native + WebView + Web | 65 | 2.642 | 1.004 | 4.455 | 1.000 |

与随机holdout相比，分组验证下整体误差明显上升，尤其是Web only的MAE达到 12.188，说明单独Web前端特征对未见设备或未见模板的泛化不足。WebView only和Native + WebView表现较强，主要因为JSBridge注入、安装来源、debuggable、WebView provider、system HTTP agent等字段直接体现宿主真实性和测试环境特征。

完整三端原始字段在分组验证中并未取得最优结果，说明Web层原始字段在未见设备或未见模板上可能引入噪声。该结果进一步支持后续实验动机：与其直接堆叠三端原始字段，不如把三端之间可解释的对齐、互证和矛盾关系显式编码。

## 4.4 跨层一致性特征构造与消融实验

### 4.4.1 实验目的

粗粒度三端消融只能回答“哪一端字段有信息量”，但不能直接回答“Native、WebView和Web三端之间是否形成可互证的语义关系”。三端融合的价值不应只体现在字段数量增加，而应体现在不同层级之间可以相互校验、相互印证和发现矛盾。因此，本节将三端之间的语义对齐关系编码为显式一致性特征，再评估这些特征对风险分拟合的作用。

### 4.4.2 一致性特征构造方法

一致性特征来源于综合规则知识库中的跨层语义规则，并由`ablation/run_consistency_ablation.py`实现为数值特征。本实验共构造 38 个`consistency_*`特征，分为四组。

| 分组 | 特征数量 | 语义 |
|---|---:|---|
| Native-Web | 18 | Android底层环境与Web JS暴露环境是否一致 |
| Native-WebView | 8 | Android底层环境与App/WebView宿主是否一致 |
| WebView-Web | 5 | WebView容器与Web前端运行环境是否一致 |
| Tri-layer semantic | 7 | 三端共同参与的核心风险规则与综合一致性分 |

代表性特征如下。

| 特征 | 含义 |
|---|---|
| `consistency_native_web_model_ua_strength` | Native设备型号、产品、主板、品牌在Web UA中的宽松匹配强度 |
| `consistency_native_web_android_version_delta` | Native Android版本与Web UA Android版本差异 |
| `consistency_native_web_screen_score` | 物理屏幕、Web逻辑屏幕、DPR的软一致性分 |
| `consistency_native_web_gpu_family_score` | Native硬件族与WebGL GPU族的宽松匹配分 |
| `consistency_native_webview_agent_model_match` | Native设备型号是否出现在WebView system HTTP agent |
| `consistency_webview_web_chrome_major_match` | WebView Provider与Web UA Chrome主版本是否一致 |
| `consistency_tri_layer_sensor_bridge_fail` | 传感器严重缺失或JSBridge未注入 |
| `consistency_tri_layer_failure_count` | 多个一致性检查失败的聚合计数 |

这些特征强调“宽松匹配”而不是字符串完全相等。例如，屏幕一致性需要将Web逻辑像素乘以DPR后与Native物理像素比较，并允许状态栏、导航栏和安全区造成的误差；GPU关系也需要基于硬件族建立近似映射。Tri-layer semantic组则综合三端信息判断核心完整性、传感器与JSBridge是否失败、manual安装来源是否伴随时区或ADB、官方安装来源与核心完整性是否同时通过，以及多个一致性检查失败的聚合数量。

### 4.4.3 一致性消融实验分组

一致性消融实验设置如下。

| 配置 | 含义 |
|---|---|
| Raw all | 三端原始 65 维特征 |
| Raw cleaned | 删除高基数字符串和直接身份字段后的原始特征 |
| Consistency only | 只使用 38 个跨层一致性特征 |
| Raw all + Consistency | 原始三端特征 + 一致性特征 |
| Raw cleaned + Consistency | 清理后原始特征 + 一致性特征 |
| Native-Web consistency | 只使用Native-Web一致性特征 |
| Native-WebView consistency | 只使用Native-WebView一致性特征 |
| WebView-Web consistency | 只使用WebView-Web一致性特征 |
| Tri-layer semantic | 只使用三端语义规则特征 |

其中`Raw cleaned`用于减少模型对高基数字符串和直接身份字段的记忆，例如`build_fingerprint`、`user_agent`、`canvas_hash`、屏幕分辨率、WebView provider version和WebGL renderer等。Android安全检测中的特征子集选择研究也表明，对高维结构化特征进行筛选有助于降低冗余并提升模型可解释性 **【引用：M03】**。

### 4.4.4 随机Holdout结果与分析

随机holdout下的一致性消融结果如下。

| 配置 | 特征数 | MAE | RMSE | R2 | 高风险F1 |
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

`Consistency only`的MAE为 1.103，RMSE为 1.473，略优于完整原始三端特征`Raw all`。`Tri-layer semantic`仅使用 7 个特征，也取得MAE 1.111 和RMSE 1.469，接近甚至略优于完整原始特征。这说明规则知识库中的“字段关系”可以被轻量模型直接吸收，少量高质量语义规则即可表达主要风险判断逻辑。

`Raw all + Consistency`和`Raw cleaned + Consistency`没有明显优于`Consistency only`，说明当前标签体系下，显式一致性特征已经覆盖主要风险信息。`WebView-Web consistency`单独效果较弱，表明只看WebView provider与Web UA、JSBridge和WebView token的关系不足以完整判断风险，仍需要Native层参与。

## 4.5 分组交叉验证下的跨层一致性泛化分析

### 4.5.1 实验目的

随机holdout可能让同一设备扩充样本、同一云真机环境或同一攻击模板样本同时进入训练集和测试集，从而高估模型泛化能力。因此，本节采用分组交叉验证，评估未见设备、未见云测环境和未见攻击模板上的表现。如果某组特征在分组验证中仍保持较低误差，则说明其语义关系具有更强泛化价值。

### 4.5.2 分组版一致性消融结果

分组交叉验证下的一致性消融结果如下。

| 配置 | 特征数 | MAE均值 | MAE标准差 | RMSE均值 | 高风险F1均值 |
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

对应图表见`ablation/figures/figure_04_grouped_main_results.png`和`ablation/grouped_consistency_error_metrics.png`。与随机holdout相比，分组验证下大多数配置误差上升，说明分组评估确实更加严格。

### 4.5.3 结果分析

`Consistency only`在随机holdout中略优于`Raw all`，但在分组交叉验证中MAE上升到 3.388，不再优于`Raw all`的 2.642。这说明 38 个一致性特征中既包含强语义规则，也包含依赖设备表达方式的宽松匹配规则。当测试集包含未见设备或未见模板时，部分型号、屏幕、GPU和UA关系可能出现新的表达形式，导致整体误差上升。

相比之下，`Tri-layer semantic`在分组验证中表现最好，MAE为 2.281，RMSE为 3.358，优于完整原始三端特征`Raw all`。该配置仅使用 7 个三端语义规则特征，却在更严格设置下取得最低误差，说明传感器与JSBridge完整性、manual安装来源与时区或ADB的组合、核心链路通过情况和失败计数等规则不依赖具体设备型号字符串，更容易跨设备和跨模板泛化。

`Native-WebView consistency`的MAE为 2.608，也优于`Raw all`，说明App宿主真实性、JSBridge、安装来源、debuggable和system HTTP agent是稳定风险信号。`Native-Web consistency`的MAE达到 12.733，则说明单独依赖型号、屏幕、GPU与UA的宽松匹配不足以处理未见设备，后续需要扩大设备覆盖并完善硬件族、GPU、UA和屏幕规则。

总体来看，在更严格的分组交叉验证下，三端语义规则特征仅使用 7 个特征便取得优于完整三端原始特征的误差表现，说明跨层一致性建模不是单纯依赖同源样本记忆，而是在未见设备和未见攻击模板上仍具有一定泛化能力。

## 4.6 特征重要性与跨层规则解释

### 4.6.1 实验目的

前几节主要从误差指标说明一致性特征有效。本节进一步分析随机森林在`Consistency only`配置下依赖哪些特征，以验证模型是否确实利用了跨层语义关系。特征重要性结果来自`ablation/consistency_top_feature_importance.csv`，对应图见`ablation/figures/figure_05_consistency_feature_importance.png`。

### 4.6.2 重要特征结果

`Consistency only`配置下排名靠前的特征如下。

| 特征 | 重要性 | 解释 |
|---|---:|---|
| `consistency_tri_layer_sensor_bridge_fail` | 0.1518 | 传感器严重缺失或JSBridge未注入，对高风险样本关键 |
| `consistency_native_webview_debug_cleartext_tension` | 0.1017 | debug与明文网络配置共同反映测试或调试宿主特征 |
| `consistency_native_web_model_ua_strength` | 0.0850 | Native设备身份与Web UA是否能相互印证 |
| `consistency_tri_layer_failure_count` | 0.0844 | 多个一致性检查失败的聚合信号 |
| `consistency_webview_web_ua_has_wv_token` | 0.0843 | Web UA是否呈现WebView运行时特征 |
| `consistency_native_web_model_ua_match` | 0.0839 | Native型号是否与Web UA直接匹配 |
| `consistency_tri_layer_manual_timezone_or_adb` | 0.0749 | manual安装来源结合时区或ADB的云机房风险 |

排名第一的`consistency_tri_layer_sensor_bridge_fail`同时涉及Native物理可信性和WebView宿主真实性。传感器严重缺失说明底层设备生态不完整，JSBridge未注入说明页面可能脱离App宿主，因此二者都是规则知识库中的核心完整性信号。

`consistency_native_webview_debug_cleartext_tension`和`consistency_tri_layer_manual_timezone_or_adb`反映测试环境和云机房特征。单独的debug、cleartext、manual、ADB或时区异常未必高危，但组合出现时更接近测试机架、云真机或群控环境。`consistency_native_web_model_ua_strength`、`consistency_native_web_model_ua_match`和`consistency_webview_web_ua_has_wv_token`则说明设备身份一致性和WebView宿主标记仍是重要辅助依据。

### 4.6.3 规则解释与系统贡献对应关系

从规则类别看，特征重要性与本文系统设计高度对应。首先是宿主真实性，JSBridge注入、WebView UA标记、WebView provider与Chrome主版本一致性用于判断页面是否运行在预期App宿主中。其次是设备身份一致性，Native型号、产品、品牌、Android版本与Web UA的宽松匹配用于判断不同层级是否像来自同一台设备。

第三是物理可信性，传感器矩阵、电池状态、ADB、安装来源等特征组合用于区分真实用户设备、云真机/测试机架和模拟器。第四是渲染与运行环境一致性，WebGL renderer、GPU family、Headless、SwiftShader、platform和算力耗时等特征用于识别桌面环境、无头浏览器和软渲染模拟器。

总体而言，特征重要性结果证明模型关注的不是孤立字段，而是传感器、JSBridge、UA、安装来源、调试状态和运行环境之间的语义关系。这与本文系统贡献一致：HybridGuard的核心不是多采几个字段，而是建立Native、WebView和Web前端之间可采集、可对齐、可解释的跨层设备指纹关系。

## 4.7 本章讨论与局限性

### 4.7.1 实验结论汇总

本章实验可以归纳为四点结论。第一，粗粒度三端消融显示，单端或双端原始字段在随机划分下也能取得较低误差，说明三端原始字段之间存在较强冗余和代理关系。第二，跨层一致性消融显示，显式一致性特征可以达到与完整原始三端特征相近甚至更优的效果，`Tri-layer semantic`仅 7 个特征就接近完整三端原始特征。第三，分组交叉验证显示，随机holdout会高估泛化能力，而核心三端语义规则在分组设置下仍优于`Raw all`。第四，特征重要性分析显示，模型重点依赖传感器与JSBridge完整性、Native与Web UA匹配、WebView宿主标记、manual安装来源与ADB等跨层语义信号。

### 4.7.2 局限性说明

本章实验仍存在一些局限。首先，当前数据集规模有限，真实物理设备和真实攻击环境覆盖仍不足。虽然数据集中包含 1323 条带标签样本，但真实设备品牌、系统版本、WebView provider版本和网络环境仍有扩展空间。

其次，高风险攻击样本主要来自模板化构造，包括API重放、无头PC浏览器和廉价模拟器。模板化样本有助于验证规则知识库和一致性特征是否能识别典型风险场景，但仍不能完全代表真实攻击链路。

第三，风险标签由规则知识库驱动的大模型离线标注流程生成，虽然具备可解释性，但仍需要人工抽样复核或业务标注进一步验证。第四，本章主要是离线消融实验，没有将端侧运行耗时、功耗、内存占用和大规模真机闭环作为主要实验。第五，当前分组策略依赖启发式`source_type`和`group_id`构造，后续可在采集阶段记录更明确的分组元数据。

### 4.7.3 后续改进方向

后续工作可以从五个方面展开：第一，扩大真实设备覆盖，增加不同品牌、系统版本、WebView内核版本和网络环境下的样本；第二，构造更多跨层矛盾专项样本，例如Android真机搭配Windows UA、屏幕DPR不一致、WebGL软件渲染、JSBridge缺失等；第三，引入人工抽样复核，校准规则知识库和大模型标签；第四，对端侧评分App进行系统开销测试；第五，研究更轻量的规则执行或模型压缩方案，使三端语义规则更适合移动端部署。

## 4.8 本章小结

本章基于已标注的三端设备指纹数据，围绕三端融合有效性和跨层一致性建模展开实验分析。实验结果表明，Native、WebView和Web三类原始字段均包含风险信息，但原始字段之间存在较强冗余，简单拼接并不能完全体现三端融合价值。将设备型号与UA、Android版本、屏幕DPR、WebView provider、JSBridge、GPU、传感器、安装来源等跨层关系显式编码后，可以得到更贴近规则知识库判断逻辑的风险信号。

在更严格的分组交叉验证下，三端核心语义规则仅使用少量特征便优于完整原始三端特征，说明跨层一致性建模具有一定泛化能力。本文系统的关键价值不是提出新的机器学习模型，而是建立Android Native、WebView宿主和Web前端之间可采集、可对齐、可解释的跨层设备指纹关系，并为端侧风险评分闭环提供实验依据。
