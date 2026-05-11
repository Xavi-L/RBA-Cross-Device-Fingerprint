# RBA-Cross-Device-Fingerprint

HybridGuard 是一个面向移动端无感风控的三端融合设备指纹原型系统。项目重点不是提出新的机器学习算法，而是打通 Android Native、WebView 宿主容器、Web 前端运行环境三类原本割裂的指纹源，并在同一会话下完成采集、对齐、跨层语义规则分析和本地轻量评分闭环。

## 项目定位

系统验证的核心问题：

1. 三端设备指纹是否能相互形成呼应，例如 Native 物理屏幕与 Web DPR/逻辑屏幕、Native Build 信息与 Web UA、WebView JSBridge 与 App 宿主真实性。
2. 是否可以利用 LLM 分析不同层 feature 的语义对齐关系，形成规则知识库，避免只靠死板阈值打分。
3. 是否可以把 LLM/规则知识库产生的风险判断能力压缩成端侧轻量评分器，在 App 内完成“采集数据 + 本地评分”。

答辩和论文叙事请突出系统贡献：三端融合采集、会话对齐、跨层语义规则知识库、端侧闭环。随机森林和 MLP 只是轻量评分器的工程选型对比，不是本文算法创新点。

## 目录概览

```text
.
├── android_app/HybridGuard/        # Android 工程：旧采集 App 与端侧评分 App
│   ├── app/                        # 旧 App：三端采集后上报服务器
│   └── riskapp/                    # 新 App：三端本地采集 + 随机森林端侧评分
├── backend_server/                 # FastAPI 后端：前端探针托管、数据接收、会话合并
├── scoring/                        # 数据扩充、高危样本生成、规则知识库、LLM 批量打分脚本和中间数据
├── training/                       # MLP/随机森林训练、评估图表、Java 端侧推理代码
├── ablation/                       # 三端消融、跨层一致性消融、分组交叉验证与论文图表
├── run_browserstack.py             # BrowserStack 云真机采集脚本
├── 梁骁-毕业论文大纲.md            # 当前论文大纲，已按系统贡献重写
└── 毕业论文参考模板.docx           # 学校/导师参考模板
```

## 核心数据流

项目现在分为“离线标注训练链路”和“端侧评分运行链路”两条路径。

离线标注训练链路：

1. 旧采集 App `:app` 启动并生成 `session_id`。
2. `MainActivity.kt` 采集 Android Native 特征：构建指纹、内存、物理屏幕、电池、传感器、安全配置等。
3. WebView 加载后端托管的 `index.html`，通过 `WebAppInterface.kt` 获取 WebView 宿主特征。
4. 前端探针采集 Web 特征：Navigator、逻辑屏幕、WebGL、Canvas、算力挑战、时区等。
5. FastAPI 后端按 `session_id` 合并异步上报数据，并写入 JSON/JSONL。
6. 批量评分脚本读取 `scoring/rule_knowledge_base.json`，将跨层一致性、攻击场景和容错规则注入本地 LLM 提示词，输出 `risk_score` 和 `risk_reason`。
7. 训练脚本用带标签数据训练 MLP 与随机森林，当前随机森林效果、推理成本和 Java 部署路径更适合端侧。
8. `ablation/` 中的消融实验进一步验证：三端原始字段存在冗余，但跨层一致性和三端语义规则能更直接支撑风险判断。

端侧评分运行链路：

1. 新评分 App `:riskapp` 启动并生成 `session_id`，Native 层先在本机采集并拍平特征。
2. WebView 加载本地 `assets/local_probe.html`，不再依赖后端托管页面完成探针采集。
3. `ScoringWebBridge.kt` 提供 JSBridge 能力，收集 WebView 宿主特征、Canvas 哈希辅助能力，并接收 Web 探针 payload。
4. `RiskFeatureEncoder.java` 按训练阶段的 65 维特征顺序、类别编码和缺失值策略生成 `double[] input`。
5. `DeviceRiskScorer.java` 在 App 内执行 m2cgen 导出的随机森林推理，得到 0-100 风险分。
6. App 只把 `session_id`、`risk_score`、`risk_level`、`risk_reason`、`scoring_engine`、`feature_count` 等评分摘要上传到后端 `/api/risk/local-score`，原始三端指纹不出端。

## 关键文件

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/MainActivity.kt`  
  Android Native 特征采集与上报入口。

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/WebAppInterface.kt`  
  JSBridge 与 WebView 宿主环境特征采集入口。

- `backend_server/index.html`  
  Web 前端探针，采集浏览器/WebView 运行环境、WebGL、Canvas 和算力特征。

- `backend_server/main.py`  
  FastAPI 服务，负责接收、校验、合并、持久化旧采集链路的三端数据，并通过 `/api/risk/local-score` 接收新 App 的端侧评分结果。

- `scoring/rule_knowledge_base.md`、`scoring/rule_knowledge_base.json`  
  综合规则知识库。Markdown 版本用于论文说明和人工审阅，JSON 版本用于批量评分脚本读取，覆盖跨层一致性、核心完整性、攻击场景聚合、物理环境异常和容错规则。

- `backend_server/rba_engine.py`、`scoring/sorting_rule_kb.py`  
  调用本地 LLM 进行风险分析和批量标签生成。`rba_engine.py` 偏交互式单条分析，`sorting_rule_kb.py` 面向 JSON 规则知识库驱动的批量标注。

- `scoring/augment_device_data.py`、`scoring/generate_bad_data.py`  
  真实样本扩充和高危样本生成。

- `training/train_randomforest.py`、`training/train_mlp.py`  
  轻量评分器训练与评估。随机森林可通过 `m2cgen` 导出 Java。

- `training/DeviceRiskScorer.java`  
  生成的随机森林 Java 推理代码，已复制到新 `riskapp` 模块作为端侧推理实现。

- `ablation/run_randomforest_ablation.py`：粗粒度三端消融脚本，比较 Native、WebView、Web 单端/双端/三端原始特征组合。

- `ablation/run_consistency_ablation.py`：跨层一致性消融脚本，将三端之间的宽松语义匹配编码为 38 个 `consistency_*` 特征。

- `ablation/run_grouped_ablation.py`：分组交叉验证实验脚本，按真实设备、云测设备和脚本攻击模板分组，避免同源样本同时进入训练集和测试集。

- `ablation/consistency_feature_rules.md`：跨层一致性特征构造规则的自然语言说明，也是综合规则知识库中 Native-Web、Native-WebView、WebView-Web 规则的重要来源。

- `ablation/figure_guide.md`：论文和展示用图片说明，整理了五张主图及补充图的用途、数据来源和讲解口径。

- `android_app/HybridGuard/riskapp/`
  新增的端侧评分 App。它加载本地 `assets/local_probe.html` 采集 Web/WebView 特征，Native 层在 App 内采集，随后用 `RiskFeatureEncoder.java` 还原训练时的 65 维输入并调用 `DeviceRiskScorer.java` 本地打分。

- `android_app/HybridGuard/riskapp/src/main/java/com/example/hybridguard/riskapp/MainActivity.kt`
  端侧评分 App 主流程：生成会话、合并三端 payload、调用随机森林、展示风险分并上传评分摘要。

- `android_app/HybridGuard/riskapp/src/main/java/com/example/hybridguard/riskapp/RiskFeatureEncoder.java`
  端侧特征适配器，固化训练侧 `json_normalize` 后的 65 维列顺序、类别编码和缺失值处理。

## 当前状态

已完成：

- Android Native / WebView / Web 三端特征采集原型。
- FastAPI 会话合并和本地持久化。
- 真实数据、扩充数据、高危模拟数据构建。
- 综合规则知识库整理为 `scoring/rule_knowledge_base.md` 和 `scoring/rule_knowledge_base.json`。
- 本地 LLM 基于规则知识库生成离线风险标签的流程。
- MLP 与随机森林轻量评分器训练和对比。
- 新增独立 `:riskapp` Android 模块，保留旧 `:app` 采集链路，并完成“本地采集 + 特征编码 + 随机森林推理 + 评分摘要上报”的端侧评分闭环。
- 后端新增 `/api/risk/local-score`，只接收端侧评分结果，不接收三端原始指纹。
- 三端粗粒度消融、跨层一致性消融和分组交叉验证实验。
- 将 38 个跨层一致性特征的构造规则整理为自然语言说明，并进一步合并进综合规则知识库，便于论文和答辩复用。
- 生成论文/展示用五类图：数据来源构成、fold 构成、holdout 与 grouped CV 对比、分组主结果、特征重要性。
- 论文大纲初稿，重点已调整为系统贡献。

待完成：

- 在更多真机/模拟风险样本上完成端侧评分闭环实验和系统开销评估。
- 论文正文撰写时，将 ablation 第三版分组实验结果整理进实验章节。

## 消融实验结论

消融实验材料统一放在 `ablation/` 下，尽量不改动原有 Android、后端和训练代码。实验使用 `training/scored_data.jsonl` 中 1323 条带 `llm_label.risk_score` 的样本，模型参数与训练侧随机森林保持一致：

```text
RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
```

### 实验设计

当前包含三层实验：

1. 粗粒度三端消融：直接比较 Native、WebView、Web 单端/双端/三端原始特征组合。
2. 跨层一致性消融：将 Native、WebView、Web 之间的宽松语义比对编码为 38 个显式一致性特征。
3. 分组交叉验证：按真实物理设备、云测真机设备、黑产脚本模板构造 `group_id`，避免同源样本同时出现在训练集和测试集。

第三版分组交叉验证是当前最推荐写入论文正文的主实验。快速 holdout 版本适合作为开发过程对照，用来说明随机切分会高估模型在未见设备/未见模板上的泛化能力。

### 主要结果

随机 holdout 下，完整三端特征与部分双端组合差异不明显，完整三端并不是 MAE/RMSE 极值。这不是实验失败，而是说明三端原始字段之间存在大量冗余和代理关系：Native 设备型号、Android 版本、屏幕信息会反映到 Web UA、DPR、逻辑屏幕；WebView provider 版本也会反映到 Web UA 的 Chrome/WebView 版本。

更有价值的结果来自跨层一致性建模。快速 holdout 中，`Consistency only` 的 MAE/RMSE 为 `1.103/1.473`，略优于完整原始三端 `Raw all` 的 `1.140/1.544`，说明显式一致性特征本身就是有效风险信号。

分组交叉验证结果更保守，也更适合作为论文主结论：

| 配置 | 特征数 | MAE 均值 | RMSE 均值 | 高风险 F1 均值 |
|---|---:|---:|---:|---:|
| Raw all | 65 | 2.642 | 4.455 | 1.000 |
| Raw cleaned | 40 | 2.617 | 4.723 | 0.680 |
| Consistency only | 38 | 3.388 | 5.735 | 0.333 |
| Native-WebView consistency | 8 | 2.608 | 4.408 | 1.000 |
| Tri-layer semantic | 7 | 2.281 | 3.358 | 1.000 |

其中 `Tri-layer semantic` 仅使用 7 个三端语义规则特征，就在分组交叉验证中优于完整原始三端特征。这是目前最适合放进论文和答辩的核心结果：三端融合的价值不只是采集更多字段，而是建立 Native、WebView、Web 之间可对齐、可互证、可发现矛盾的语义关系。

### 论文表达口径

可以将实验结论概括为：

> 三端原始特征之间存在较强冗余，因此简单删除某一端并不能充分体现三端融合价值。进一步将跨层语义对齐关系显式编码后，少量一致性特征即可达到与完整原始三端特征相近甚至更优的风险分拟合效果。在更严格的分组交叉验证中，三端语义规则特征仍优于完整原始特征，说明跨层一致性建模不是依赖同源样本记忆，而是具备一定未见设备和未见攻击模板泛化能力。

### 运行命令

```bash
conda run -n cross-device-fingerprint python ablation/run_randomforest_ablation.py
conda run -n cross-device-fingerprint python ablation/run_consistency_ablation.py
conda run -n cross-device-fingerprint python ablation/run_grouped_ablation.py
conda run -n cross-device-fingerprint python ablation/make_figures.py
```

详细实验说明见 `ablation/README.md`。一致性特征构造规则见 `ablation/consistency_feature_rules.md`。综合规则知识库见 `scoring/rule_knowledge_base.md` 和 `scoring/rule_knowledge_base.json`。论文和答辩图表说明见 `ablation/figure_guide.md`。

## 端侧评分 App

旧采集 App 仍为 `:app`，新端侧评分 App 为 `:riskapp`：

```bash
cd android_app/HybridGuard
./gradlew :riskapp:assembleDebug
```

新 App 默认把评分结果上报到 `riskapp/src/main/java/com/example/hybridguard/riskapp/MainActivity.kt` 中的 `SCORE_ENDPOINT`。如果后端地址或 ngrok 地址变化，只需要修改该常量。后端接收文件为 `backend_server/local_score_results.jsonl`。

## 实验叙事建议

实验优先顺序建议如下：

1. 三端采集完整性与会话合并成功率。
2. 综合规则知识库与跨层语义对齐案例分析。
3. 三端粗粒度消融，说明按端粗删不足以体现核心价值。
4. 跨层一致性消融和分组交叉验证，作为论文主实验。
5. App 本地评分闭环与端侧开销。
6. 轻量评分器工程选型：随机森林 vs MLP。

随机森林优先于神经网络的理由：成本低、响应快、小样本结构化数据更稳定、端侧 Java 部署直接、打分依据更容易解释。不要把它包装成算法创新。

## 运行提示

Python 运行环境使用 Miniconda，环境名为 `cross-device-fingerprint`：

```bash
conda activate cross-device-fingerprint
```

后端本地运行通常在 `backend_server/` 下启动：

```bash
python3 main.py
```

LLM 打分脚本默认依赖本地 LM Studio OpenAI-compatible API，例如 `http://127.0.0.1:1234/v1`。规则知识库驱动的批量脚本为 `scoring/sorting_rule_kb.py`，默认读取 `scoring/rule_knowledge_base.json`，并把结果写入新的 `scoring/simulated_bad_data_rule_kb_scored.jsonl`，不会覆盖原有打分文件。运行前需要确认本地模型服务已启动，并检查脚本中的模型名。

Android App 中存在硬编码 ngrok URL：旧 `:app` 用于上传三端原始采集数据，新 `:riskapp` 用于上传端侧评分摘要。运行前需要根据当前后端地址修改。`run_browserstack.py` 也包含云真机采集相关配置，公开提交或共享前请先移除账号、密钥和临时 URL。

## Agent Notes

- 先读 `梁骁-毕业论文大纲.md`，再读代码。当前论文叙事已经明确：系统贡献优先，算法只是工程组件。
- 不要把第二章写成“相关技术介绍”，导师要求删除模板中的该章。
- 后续改端侧评分时，最危险的是训练侧特征编码和端侧 `double[] input` 顺序不一致。
- 若补实验，优先补端侧评分闭环、系统开销、采集完整性统计或更真实的未见设备样本，而不是继续堆模型。
- 不要提交真实密钥、BrowserStack 凭证、长期可用 ngrok 地址或原始隐私数据。
