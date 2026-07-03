# RBA-Cross-Device-Fingerprint

HybridGuard 是一个面向移动端无感风控的三端融合设备指纹原型系统。项目重点不是提出新的机器学习算法，而是打通 Android Native、WebView 宿主容器、Web 前端运行环境三类原本割裂的指纹源，并在同一会话下完成采集、对齐、跨层语义规则分析和本地轻量评分闭环。

## 项目定位

系统验证的核心问题：

1. 三端设备指纹是否能相互形成呼应，例如 Native 物理屏幕与 Web DPR/逻辑屏幕、Native Build 信息与 Web UA、WebView JSBridge 与 App 宿主真实性。
2. 是否可以利用 LLM 分析不同层 feature 的语义对齐关系，形成规则知识库，避免只靠死板阈值打分。
3. 是否可以把 LLM/规则知识库产生的风险判断能力压缩成端侧轻量评分器，在 App 内完成“采集数据 + 本地评分”。

后续投稿和仓库复用叙事请突出系统贡献：三端融合采集、会话对齐、跨层语义规则知识库、端侧闭环。随机森林和 MLP 只是轻量评分器的工程选型对比，不是本文算法创新点。

## 目录概览

```text
.
├── android_app/HybridGuard/        # Android 工程：采集、端侧评分、扩充采集三个 App
│   ├── app/                        # 旧 App：三端采集后上报服务器
│   ├── riskapp/                    # 端侧评分 App：本地采集 + 随机森林推理 + 摘要上报
│   └── featureapp/                 # 扩充采集 App：177 维三端原始特征采集上报，不做端侧评分
├── backend_server/                 # FastAPI 后端：前端探针托管、数据接收、会话合并、分文件落盘
├── scoring/                        # 数据扩充、高危样本生成、规则知识库、LLM 批量打分脚本和中间数据
├── training/                       # MLP/随机森林训练、评估图表、Java 端侧推理代码
├── ablation/                       # 三端消融、跨层一致性消融、分组交叉验证与论文图表
├── zhipu_glm_eval/                 # GLM-5.2 直接风险评分评估，与随机森林/教师标签对比
├── rf_grouped_fusion_validation/   # 随机森林代理的分组证据融合预验证
├── thesis_materials/               # 毕业论文成品、章节草稿、参考文献和可复用论文图
├── presentation/                   # 最终答辩稿、模板和讲稿
├── archive/graduation_submission/  # 已归档的学校提交件、旧答辩稿和修复备份
├── LLM_GROUPED_FUSION_PLAN.md      # LLM 分组评分 + 外部权重融合后续实验方案
├── run_browserstack.py             # BrowserStack 云真机采集脚本
├── 梁骁-毕业论文大纲.md            # 毕业论文大纲和后续论文改写参考
└── 第四章实验分析大纲.md            # 实验章节写作与结果解释参考
```

## 核心数据流

项目现在分为“离线标注训练链路”“扩充特征采集链路”“端侧评分运行链路”和“LLM/分组融合验证链路”四条路径。

离线标注训练链路：

1. 旧采集 App `:app` 启动并生成 `session_id`。
2. `MainActivity.kt` 采集 Android Native 特征：构建指纹、内存、物理屏幕、电池、传感器、安全配置等。
3. WebView 加载后端托管的 `index.html`，通过 `WebAppInterface.kt` 获取 WebView 宿主特征。
4. 前端探针采集 Web 特征：Navigator、逻辑屏幕、WebGL、Canvas、算力挑战、时区等。
5. FastAPI 后端按 `session_id` 合并异步上报数据，并写入 JSON/JSONL。
6. 批量评分脚本读取 `scoring/rule_knowledge_base.json`，将跨层一致性、攻击场景和容错规则注入本地 LLM 提示词，输出 `risk_score` 和 `risk_reason`。
7. 训练脚本用带标签数据训练 MLP 与随机森林，当前随机森林效果、推理成本和 Java 部署路径更适合端侧。
8. `ablation/` 中的消融实验进一步验证：三端原始字段存在冗余，但跨层一致性和三端语义规则能更直接支撑风险判断。

扩充特征采集链路：

1. 扩充采集 App `:featureapp` 独立于旧 `:app` 和 `:riskapp`，只做三端原始特征扩充采集和上报，不做端侧评分。
2. Native 层由 `ExpandedFingerprintCollector.kt` 采集 Build、内存、屏幕、电池、传感器、安全、存储、地区时区、网络状态和原生 GPU 等扩展字段。
3. WebView 加载本地 `assets/expanded_probe.html`，通过 `ExpandedWebBridge.kt` 汇总 WebView 宿主、设置项、浏览器运行时、WebGL、Canvas、AudioContext、字体 hash、权限状态、网络 API 和自动化表面信号。
4. App 上报时带上 `collector_app=featureapp` 和 `schema_version=expanded-v2`，后端单独写入 `backend_server/expanded_merged_sessions.json` 和 `backend_server/expanded_collected_data.jsonl`，不改动旧采集文件。
5. 按固定字段键名统计，当前扩充采集为 177 维：Native 84 维、WebView 26 维、Web 67 维。App 界面里的动态计数会把数组字段按元素数展开，因此实机显示值可能更高。

端侧评分运行链路：

1. 新评分 App `:riskapp` 启动并生成 `session_id`，Native 层先在本机采集并拍平特征。
2. WebView 加载本地 `assets/local_probe.html`，不再依赖后端托管页面完成探针采集。
3. `ScoringWebBridge.kt` 提供 JSBridge 能力，收集 WebView 宿主特征、Canvas 哈希辅助能力，并接收 Web 探针 payload。
4. `RiskFeatureEncoder.java` 按训练阶段的 65 维特征顺序、类别编码和缺失值策略生成 `double[] input`。
5. `DeviceRiskScorer.java` 在 App 内执行 m2cgen 导出的随机森林推理，得到 0-100 风险分。
6. App 只把 `session_id`、`risk_score`、`risk_level`、`risk_reason`、`scoring_engine`、`feature_count` 等评分摘要上传到后端 `/api/risk/local-score`，原始三端指纹不出端。

LLM/分组融合验证链路：

1. `LLM_GROUPED_FUSION_PLAN.md` 定义“LLM 分组评分 + 外部权重融合”的后续方案：LLM 负责每组语义风险子分数，Positive ElasticNet 等外部模型负责可复现的权重学习。
2. `zhipu_glm_eval/` 使用 GLM-5.2 直接读取三端 payload 和 `scoring/rule_knowledge_base.json` 做风险评分，并与教师标签、随机森林 holdout 结果对比。
3. `rf_grouped_fusion_validation/` 在暂时没有足够大模型算力时，用随机森林代理六组证据的组级子分数，先验证分组证据池和外部融合结构是否值得推进。

## 关键文件

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/MainActivity.kt`  
  Android Native 特征采集与上报入口。

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/WebAppInterface.kt`  
  JSBridge 与 WebView 宿主环境特征采集入口。

- `backend_server/index.html`  
  Web 前端探针，采集浏览器/WebView 运行环境、WebGL、Canvas 和算力特征。

- `backend_server/main.py`  
  FastAPI 服务，负责接收、校验、合并、持久化三端数据。旧 `:app` 写入 `merged_sessions.json` / `collected_data.jsonl`，`featureapp` 写入 `expanded_merged_sessions.json` / `expanded_collected_data.jsonl`，`:riskapp` 通过 `/api/risk/local-score` 写入 `local_score_results.jsonl`。所有 JSON/JSONL 都固定落在 `backend_server/` 下。

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

- `LLM_GROUPED_FUSION_PLAN.md`  
  后续 LLM 分组证据融合方案。核心设计是让 LLM 输出 Native-Web、Native-WebView、WebView-Web、Tri-layer semantic、Physical runtime、Attack scenario 六组风险子分数，再用 Positive ElasticNet 等外部融合模型学习权重。

- `ablation/run_randomforest_ablation.py`：粗粒度三端消融脚本，比较 Native、WebView、Web 单端/双端/三端原始特征组合。

- `ablation/run_consistency_ablation.py`：跨层一致性消融脚本，将三端之间的宽松语义匹配编码为 38 个 `consistency_*` 特征。

- `ablation/run_grouped_ablation.py`：分组交叉验证实验脚本，按真实设备、云测设备和脚本攻击模板分组，避免同源样本同时进入训练集和测试集。

- `ablation/consistency_feature_rules.md`：跨层一致性特征构造规则的自然语言说明，也是综合规则知识库中 Native-Web、Native-WebView、WebView-Web 规则的重要来源。

- `ablation/figures/figure_guide.md`：论文和展示用图片说明，整理了五张主图及补充图的用途、数据来源和讲解口径。

- `android_app/HybridGuard/riskapp/`
  新增的端侧评分 App。它加载本地 `assets/local_probe.html` 采集 Web/WebView 特征，Native 层在 App 内采集，随后用 `RiskFeatureEncoder.java` 还原训练时的 65 维输入并调用 `DeviceRiskScorer.java` 本地打分。

- `android_app/HybridGuard/riskapp/src/main/java/com/example/hybridguard/riskapp/MainActivity.kt`
  端侧评分 App 主流程：生成会话、合并三端 payload、调用随机森林、展示风险分并上传评分摘要。

- `android_app/HybridGuard/riskapp/src/main/java/com/example/hybridguard/riskapp/RiskFeatureEncoder.java`
  端侧特征适配器，固化训练侧 `json_normalize` 后的 65 维列顺序、类别编码和缺失值处理。

- `android_app/HybridGuard/featureapp/`
  新增的扩充特征采集 App。它保留三端采集结构，但面向后续实验收集更丰富原始字段，不执行端侧评分。

- `android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/ExpandedFingerprintCollector.kt`
  扩充 Native 和 WebView 宿主采集入口，覆盖设备构建、物理运行、网络、安全、存储、地区时区和 WebView 配置等字段。

- `android_app/HybridGuard/featureapp/src/main/assets/expanded_probe.html`
  扩充 Web/WebView 探针，采集浏览器运行时、WebGL、Canvas、网络 API、自动化表面和 JSBridge 连接延迟。

- `zhipu_glm_eval/score_with_glm.py`
  调用智谱 GLM-5.2 对 holdout 样本直接打风险分。脚本不会保存 API Key，支持 `ZHIPU_API_KEY`、`--api-key-file` 或 `--api-key-stdin`。

- `zhipu_glm_eval/analyze_score_bands.py`、`zhipu_glm_eval/compare_glm_rf.py`
  分别用于 GLM 风险区间匹配分析，以及 GLM、教师标签、随机森林 holdout 预测的对比。

- `rf_grouped_fusion_validation/run_rf_grouped_fusion_validation.py`
  随机森林代理的六组证据融合预验证脚本，复用 grouped CV，输出组级子分数、融合权重、折指标和预测明细。

- `rf_grouped_fusion_validation/REPORT.md`
  分组融合预验证报告，记录六组证据、Positive ElasticNet 融合结果、组权重和阶段性结论。

## 当前状态

已完成：

- 毕业论文最终提交和毕业答辩材料交付。
- Android Native / WebView / Web 三端特征采集原型。
- FastAPI 会话合并和本地持久化。
- 真实数据、扩充数据、高危模拟数据构建。
- 综合规则知识库整理为 `scoring/rule_knowledge_base.md` 和 `scoring/rule_knowledge_base.json`。
- 本地 LLM 基于规则知识库生成离线风险标签的流程。
- MLP 与随机森林轻量评分器训练和对比。
- 新增独立 `:riskapp` Android 模块，保留旧 `:app` 采集链路，并完成“本地采集 + 特征编码 + 随机森林推理 + 评分摘要上报”的端侧评分闭环。
- 后端新增 `/api/risk/local-score`，只接收端侧评分结果，不接收三端原始指纹。
- 新增独立 `:featureapp` Android 模块，保留旧 `:app` 和 `:riskapp`，只做扩充后三端原始特征采集和上报，不执行端侧评分。
- 后端新增扩充采集分流：`featureapp` 数据写入 `backend_server/expanded_merged_sessions.json` 和 `backend_server/expanded_collected_data.jsonl`，旧采集文件和端侧评分文件保持原用途。
- 当前 `featureapp` 固定字段为 177 维：Native 84 维、WebView 26 维、Web 67 维。
- 三端粗粒度消融、跨层一致性消融和分组交叉验证实验。
- 将 38 个跨层一致性特征的构造规则整理为自然语言说明，并进一步合并进综合规则知识库，便于论文和答辩复用。
- 生成论文/展示用五类图：数据来源构成、fold 构成、holdout 与 grouped CV 对比、分组主结果、特征重要性。
- 新增 `LLM_GROUPED_FUSION_PLAN.md`，沉淀 LLM 分组风险子分数、Positive ElasticNet 外部融合、nested grouped CV 和字段扩充原则。
- 新增 `zhipu_glm_eval/`，完成 GLM-5.2 直接风险评分评估；完整 holdout 风险区间匹配为 263/265，即 99.25%。
- 新增 `rf_grouped_fusion_validation/`，用随机森林代理组级子分数预验证分组融合结构；Positive ElasticNet 融合 MAE 为 2.968，高风险 F1 为 1.000，验证外部融合框架可跑通，但尚不宣称优于最强 `Tri-layer semantic` 基线。
- 毕业论文 `.docx` / `.pdf` 成品、章节草稿、参考文献材料和论文图表已保留在 `thesis_materials/`。
- 学校流程材料、旧版答辩稿和文档修复备份已归档到 `archive/graduation_submission/`；PPT 生成中间产物 `outputs/` 已清理。

面向后续投稿的建议工作：

- 在更多真机、云真机和真实攻击样本上补充端侧评分闭环实验和系统开销评估。
- 将毕业论文系统实现和实验材料压缩重写为投稿论文结构，突出跨层一致性建模和分组泛化实验。
- 公开共享或投稿附录前，完成 BrowserStack/ngrok 等运行配置脱敏，并评估原始指纹数据的隐私处理方式。

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

详细实验说明见 `ablation/README.md`。一致性特征构造规则见 `ablation/consistency_feature_rules.md`。综合规则知识库见 `scoring/rule_knowledge_base.md` 和 `scoring/rule_knowledge_base.json`。论文和展示图表说明见 `ablation/figures/figure_guide.md`。

## LLM 与分组融合实验

`LLM_GROUPED_FUSION_PLAN.md` 是后续从“规则/随机森林评分”推进到“LLM 分组语义评分”的主计划文档。核心思想不是把更多字段直接拼成一个大表，而是把三端证据拆成六个可解释分组：

1. Native-Web
2. Native-WebView
3. WebView-Web
4. Tri-layer semantic
5. Physical runtime
6. Attack scenario

推荐主线是：每组先由 LLM 输出 0-100 风险子分数，再由 Positive ElasticNet 等外部模型学习融合权重，避免总分权重藏在 prompt 内部。

`zhipu_glm_eval/` 用于评估 GLM-5.2 直接风险评分能力。脚本不会保存 API Key，运行时通过 `ZHIPU_API_KEY`、`--api-key-file` 或 `--api-key-stdin` 注入：

```bash
python3 zhipu_glm_eval/score_with_glm.py \
  --api-key-stdin \
  --all-holdout \
  --max-tokens 512 \
  --response-format-json \
  --disable-thinking \
  --output zhipu_glm_eval/outputs/glm52_holdout_jsonmode_full.jsonl

python3 zhipu_glm_eval/analyze_score_bands.py \
  --glm-scores zhipu_glm_eval/outputs/glm52_holdout_jsonmode_full.jsonl \
  --output-dir zhipu_glm_eval/outputs/jsonmode_full_bands
```

当前完整 holdout 风险区间分析结果：成功 265 条，错误 0 条，五档风险区间匹配 263/265，三档风险区间匹配 263/265，匹配率均为 99.25%。这更适合用来说明 GLM 风险区间判断与规则标签高度一致，而不是简单宣称它在 MAE 上全面优于随机森林。

`rf_grouped_fusion_validation/` 是低算力条件下的分组融合预验证。它不证明 LLM 本身更强，而是用随机森林代理每组风险子分数，先验证“组级子分数 + 外部融合”框架是否可复现、是否能学习合理权重：

```bash
python3 rf_grouped_fusion_validation/run_rf_grouped_fusion_validation.py
```

核心结果：`Six group scores + Positive ElasticNet` 的 grouped CV MAE 为 2.968，高风险 F1 为 1.000，明显优于简单平均和六组特征直接堆叠；权重主要集中在 Tri-layer semantic、Native-WebView 和 Attack scenario。它仍弱于当前最强的 `Tri-layer semantic direct RF`，因此论文表达应是“框架可跑通、外部融合有效、关键信号选择符合预期”，而不是“分组融合已经超过所有基线”。

## Android App 运行

Android 工程保留三版 App：

- `:app`：旧三端采集 App，上传原始三端指纹。
- `:riskapp`：端侧评分 App，上传评分摘要，不上传原始三端指纹。
- `:featureapp`：扩充采集 App，上传扩充后三端原始特征，不做端侧评分。

```bash
cd android_app/HybridGuard
./gradlew :app:assembleDebug
./gradlew :riskapp:assembleDebug
./gradlew :featureapp:assembleDebug
```

本机 Android Studio 模拟器测试时，`featureapp` 默认使用 `http://10.0.2.2:8000/api/collect/fingerprint` 访问宿主机后端。真机测试时需要改为局域网 IP，或使用 `adb reverse` / ngrok。

各 App 对应的后端输出：

- `:app` -> `backend_server/merged_sessions.json`、`backend_server/collected_data.jsonl`
- `:featureapp` -> `backend_server/expanded_merged_sessions.json`、`backend_server/expanded_collected_data.jsonl`
- `:riskapp` -> `backend_server/local_score_results.jsonl`

如果后端地址变化，分别修改对应模块 `MainActivity.kt` 中的 endpoint 常量。

## 实验叙事建议

实验优先顺序建议如下：

1. 三端采集完整性与会话合并成功率。
2. 综合规则知识库与跨层语义对齐案例分析。
3. 三端粗粒度消融，说明按端粗删不足以体现核心价值。
4. 跨层一致性消融和分组交叉验证，作为论文主实验。
5. 扩充采集 App 的 177 维三端特征采集稳定性、缺失率和跨设备差异。
6. GLM-5.2 直接评分与规则标签的风险区间一致性，用作 LLM 语义判断能力证据。
7. LLM 分组子分数 + Positive ElasticNet 融合，验证分组证据池是否能在 grouped CV 下稳定泛化。
8. App 本地评分闭环与端侧开销。
9. 轻量评分器工程选型：随机森林 vs MLP。

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

后端所有采集输出都固定写入 `backend_server/`，即使从仓库根目录导入或启动也不会再散落到项目根目录。旧采集、扩充采集、端侧评分分别对应 `collected_data.jsonl`、`expanded_collected_data.jsonl` 和 `local_score_results.jsonl`。

LLM 打分脚本默认依赖本地 LM Studio OpenAI-compatible API，例如 `http://127.0.0.1:1234/v1`。规则知识库驱动的批量脚本为 `scoring/sorting_rule_kb.py`，默认读取 `scoring/rule_knowledge_base.json`，并把结果写入新的 `scoring/simulated_bad_data_rule_kb_scored.jsonl`，不会覆盖原有打分文件。运行前需要确认本地模型服务已启动，并检查脚本中的模型名。

`zhipu_glm_eval/` 调用在线 GLM-5.2 API，默认不会保存 API Key。公开共享前仍需检查 shell 历史、临时文件和输出目录，避免误留密钥或含隐私的原始指纹片段。

Android App 中存在硬编码后端地址：旧 `:app` 用于上传三端原始采集数据，`:riskapp` 用于上传端侧评分摘要，`:featureapp` 用于上传扩充特征。运行前需要根据当前后端地址修改。`run_browserstack.py` 也包含云真机采集相关配置，公开提交或共享前请先移除账号、密钥和临时 URL。

## Agent Notes

- 先读 `梁骁-毕业论文大纲.md`，再读代码。当前论文叙事已经明确：系统贡献优先，算法只是工程组件。
- 不要把第二章写成“相关技术介绍”，导师要求删除模板中的该章。
- 后续改端侧评分时，最危险的是训练侧特征编码和端侧 `double[] input` 顺序不一致。
- `:featureapp` 只用于扩充原始特征采集，不要把端侧评分逻辑混进去；它的输出应继续和旧 `:app` / `:riskapp` 文件隔离。
- LLM 分组融合实验的重点是组级语义分数和外部可复现权重，不要把更多字段直接堆进一个黑箱 prompt 后宣称性能提升。
- 若补实验，优先补端侧评分闭环、系统开销、采集完整性统计或更真实的未见设备样本，而不是继续堆模型。
- 不要提交真实密钥、BrowserStack 凭证、长期可用 ngrok 地址或原始隐私数据。
