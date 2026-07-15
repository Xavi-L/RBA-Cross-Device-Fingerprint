# HybridGuard: RBA Cross-Device Fingerprinting

[中文](#中文说明) | [English](#english)

HybridGuard is a research prototype for risk-based authentication (RBA) that aligns Android Native, WebView host, and Web runtime fingerprints within one session. The repository contains the complete graduation-project system, experiment artifacts, and an ongoing roadmap toward a knowledge-grounded agentic risk-analysis system.

---

## 中文说明

### 项目简介

HybridGuard 面向移动端无感风控与风险认证场景，在同一 `session_id` 下采集并对齐三类原本割裂的设备证据：

- Android Native：设备构建、物理运行、传感器、安全配置、网络与存储等信号；
- WebView Host：宿主 App、WebView provider、JSBridge、WebSettings 与安装信息；
- Web Runtime：Navigator、屏幕、WebGL、Canvas、Audio、字体、权限与自动化表面信号。

项目的核心贡献不是提出一个新的分类器，而是建立“三端采集 → 会话对齐 → 跨层语义互证 → 风险解释 → 端侧轻量评分”的完整系统链路。随机森林、MLP 和 Positive ElasticNet 是工程基线或外部融合组件，不应被表述为算法创新。

当前研究主线正从传统“规则知识库 + 单模型评分”继续推进到知识支撑的 Agentic/RAG 架构：让 LLM 对分组证据进行语义判断，由 Verifier 检查证据引用与结论边界，再由可复现的外部模型完成总分融合。该 Agentic/RAG 架构目前是目标设计与分阶段实施路线，尚未全部落地。

### 当前实现状态

已实现：

- 三个相互隔离的 Android App：旧三端采集 `:app`、端侧评分 `:riskapp`、扩充采集 `:featureapp`；
- FastAPI 后端：Web 探针托管、三端会话合并、扩充数据分流、端侧评分摘要接收与 JSON/JSONL 持久化；
- `featureapp` 面向 API 21+ 的 expanded-v2.2-status 固定结构：Native 84 + WebView 26 + Web 67，共 177 个结构化字段，并上报 collection manifest、逐字段状态和探针诊断；
- `featureapp` readiness 预检、Web 超时保底、立即/后台重试、后端部分 payload 保存、collection receipt 与重复抑制；
- 35 条综合风险规则，以及 30 条 Google 官方来源、20 张知识卡片；其中 15 张已作为解释性元数据合入主规则库；
- 本地 LLM 标签生成、随机森林/MLP 训练、端侧 Java 随机森林推理和评分摘要上报闭环；
- 三端粗粒度消融、跨层一致性消融、按设备/模板分组的交叉验证；
- GLM-5.2 直接评分、Google 官方知识 K0/K1 消融、六组证据融合与重复画像降权的 targeted pilot；
- 真机云平台设备目录与可用性统计、毕业论文/答辩材料、投稿复用图表。

当前工作重点：

- 冻结 expanded-v2 的权威 JSON Schema、canonical field registry 和历史样本 manifest；
- 将 session 数与独立 `stable_device_key` / 稳定画像数分开统计，避免重复设备画像造成评估偏差；
- 补充带独立来源与攻击事实标签的 clean/attack/post 配对样本；
- 完成 K1.1 容错规则消融，以及完整 original/augmented GLM 分组分数缓存；
- 在严格 grouped CV、OOD 和泄漏审计下验证 Retriever、Verifier 与外部融合，而不是只在旧教师标签上追求更低误差。

截至 `2026-07-10` 的数据审计快照为 155 个 session：154 条 expanded-v2、1 条需要隔离的 expanded-v1；保守估计约 80 个稳定画像组。session 数、稳定画像数和已验证物理设备数不是同一口径。

### 系统链路

```text
Android Native ─┐
WebView Host ───┼─> session_id 对齐 ─> FastAPI 分流与持久化
Web Runtime ────┘                         │
                                         ├─> 规则/LLM 离线标注
                                         ├─> 跨层一致性与 grouped CV
                                         ├─> 六组语义评分 + 外部融合
                                         └─> 轻量模型导出 -> Android 端侧评分
```

三类运行链路彼此独立：

| App | 作用 | 上传内容 | 后端输出 |
|---|---|---|---|
| `:app` | 旧版三端采集 | 原始 Native/WebView/Web payload | `merged_sessions.json`、`collected_data.jsonl` |
| `:riskapp` | 端侧随机森林评分 | 风险分、等级、理由和引擎摘要 | `local_score_results.jsonl` |
| `:featureapp` | expanded-v2 扩充采集 | 177 字段三端原始 payload | `expanded_merged_sessions.json`、`expanded_collected_data.jsonl` |

`riskapp` 的 Web 探针和随机森林推理都在本地执行，后端只接收评分摘要。`featureapp` 不包含端侧评分逻辑；它的原始数据始终与旧采集和评分摘要文件分开保存。

### 仓库结构

```text
.
├── android_app/
│   ├── HybridGuard/                  # Android Studio 工程：app/riskapp/featureapp
│   └── ANDROID_STUDIO_APP_USAGE.md   # 三个 App 的启动、联网与验收说明
├── backend_server/                   # FastAPI、Web 探针与本地 JSON/JSONL 输出
├── scoring/                          # 数据扩充、攻击样本、规则库和 LLM 批量评分
├── training/                         # MLP/RF 训练、评估与 Java 模型导出
├── ablation/                         # 消融、grouped CV、结果表和论文图
├── google_official_kb/               # Google 官方来源、风险卡与合并报告
├── zhipu_glm_eval/                   # GLM-5.2 直接风险评分评估
├── rf_grouped_fusion_validation/     # RF 代理的低成本分组融合预验证
├── llm_grouped_fusion_validation/    # GLM 分组融合、知识消融与重复画像验证
├── device_cloud_catalog/             # 国内外真机云设备目录与统计口径
├── hybridguard_agent/                # 可重跑的数据冻结、标签 sidecar、QC 与无标签 EvidenceBundle 管线
├── hybridguard_agent_rag_guide/      # Agentic/RAG 目标架构、任务路由和实施分册
├── thesis_materials/                 # 论文成品、章节、参考文献和期刊风格图
├── presentation/                     # 答辩稿、模板与讲稿
├── archive/                          # 学校提交件与历史材料归档
├── web_client/                       # 独立 Web 客户端材料
├── ENVIRONMENT_SETUP.md              # 克隆后的完整环境配置
├── LLM_GROUPED_FUSION_PLAN.md        # 六组 LLM 子分数与外部融合方案
├── HYBRIDGUARD_AGENT_RAG_ACTION_GUIDE.md  # Agent 指南的根目录跳转页
├── run_browserstack.py               # BrowserStack 采集入口
└── sauce_appium_smoke.py             # Sauce Labs Appium 冒烟测试
```

### 快速开始

完整依赖、版本与验证步骤见 [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md)。主要环境为 Python 3.10、Conda、Android Studio、Android `compileSdk` 36.1、JDK 21 和仓库内 Gradle Wrapper 9.3.1。

#### 1. 启动后端

建议从 `backend_server/` 目录启动：

```bash
conda activate cross-device-fingerprint
cd backend_server
python main.py
```

健康检查：

```bash
curl http://localhost:8000/health
```

主要接口：

- `GET /`：Web 指纹探针；
- `GET /health`：健康检查；
- `POST /api/collect/fingerprint`：旧版与 expanded-v2 三端采集；
- `POST /api/risk/local-score`：端侧评分摘要。

#### 2. 构建 Android App

在 Android Studio 中应打开 `android_app/HybridGuard`，而不是仓库根目录。命令行构建：

```bash
cd android_app/HybridGuard
./gradlew :app:assembleDebug
./gradlew :riskapp:assembleDebug
./gradlew :featureapp:assembleDebug
```

三个模块都需要按运行环境检查后端地址。旧 `:app` 与 `:riskapp` 主要在各自的 `MainActivity.kt` 中配置；`:featureapp` 用 `-PhybridguardCollectEndpoint=...` 在构建时生成 endpoint。模拟器通常使用 `10.0.2.2`，真机可使用局域网 IP、`adb reverse` 或临时隧道。详细步骤见 [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md)。

#### 3. 运行核心离线实验

```bash
conda activate cross-device-fingerprint

python ablation/run_randomforest_ablation.py
python ablation/run_consistency_ablation.py
python ablation/run_grouped_ablation.py
python rf_grouped_fusion_validation/run_rf_grouped_fusion_validation.py
python llm_grouped_fusion_validation/prepare_validation_assets.py
```

训练脚本使用相对输入路径，需从 `training/` 目录运行：

```bash
cd training
python train_randomforest.py
python train_mlp.py
```

GLM-5.2 脚本支持 `ZHIPU_API_KEY`、`--api-key-file` 或 `--api-key-stdin`，不会主动把 API Key 写入仓库。在线调用和详细命令见 [`zhipu_glm_eval/README.md`](zhipu_glm_eval/README.md) 与 [`llm_grouped_fusion_validation/README.md`](llm_grouped_fusion_validation/README.md)。

### 当前实验结论与边界

| 验证项 | 当前结果 | 可以说明 | 不能说明 |
|---|---|---|---|
| grouped CV 三端语义特征 | 7 个特征，MAE 2.281、RMSE 3.358 | 跨层语义互证比简单堆叠原始字段更有价值 | 已具备真实攻击检测准确率 |
| RF 代理六组 + Positive ElasticNet | MAE 2.968，高风险 F1 1.000 | 分组子分数与外部融合框架可复现 | 已超过最强 Tri-layer baseline，或 RF 等价于 LLM |
| GLM-5.2 完整 holdout 风险区间 | 263/265，99.25% | 与既有规则标签的风险区间高度一致 | 对独立真实攻击真值达到 99.25% 准确率 |
| Google 官方知识 targeted K0/K1 | K1 未降低高风险 F1，但 MAE/RMSE 未改善 | 官方依据增强解释性并暴露容错边界 | 官方知识已经提升整体预测性能 |
| 重复画像降权 targeted pilot | MAE 7.983 → 6.318 | 小样本中存在正向信号 | 完整分组融合已完成或已形成稳定结论 |

最重要的结论边界：结构化预验证不等于完整 LLM 验证；控制同组样本跨折泄漏不等于消除重复画像训练偏置；旧 `llm_label` 是教师标签而不是独立攻击事实真值。

### 文档导航

| 目标 | 入口 |
|---|---|
| 从新克隆到本地运行 | [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md) |
| 用 Android Studio 启动三个 App | [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md) |
| 后端接口与 payload 示例 | [`backend_server/start_server.md`](backend_server/start_server.md) |
| 消融与 grouped CV | [`ablation/README.md`](ablation/README.md) |
| Google 官方知识库 | [`google_official_kb/README.md`](google_official_kb/README.md) |
| LLM 分组融合方案 | [`LLM_GROUPED_FUSION_PLAN.md`](LLM_GROUPED_FUSION_PLAN.md) |
| GLM targeted pilot | [`llm_grouped_fusion_validation/PILOT_REPORT.md`](llm_grouped_fusion_validation/PILOT_REPORT.md) |
| 数据冻结与 Week 7 标签接入 | [`hybridguard_agent/README.md`](hybridguard_agent/README.md) |
| Agentic/RAG 后续行动 | [`hybridguard_agent_rag_guide/README.md`](hybridguard_agent_rag_guide/README.md) |
| 论文和投稿材料 | [`thesis_materials/README.md`](thesis_materials/README.md) |
| 真机云调研 | [`device_cloud_catalog/`](device_cloud_catalog/) |

### 安全与数据说明

- 不要提交 API Key、BrowserStack/Sauce Labs 凭证、长期可用的隧道 URL 或本机绝对路径；
- 原始设备指纹可能包含隐私或可关联信息，公开共享前应脱敏、抽样并审查用途；
- 当前部分 Android endpoint 仍为硬编码配置，运行和公开发布前必须检查；
- 面向 Agent 的任务请从 `hybridguard_agent_rag_guide/README.md` 路由，只读取与当前任务相关的 1–2 份分册。

---

## English

### Overview

HybridGuard targets frictionless mobile risk control and risk-based authentication. It collects and aligns three previously isolated evidence sources under one `session_id`:

- Android Native signals: build identity, physical runtime, sensors, security settings, network, and storage;
- WebView Host signals: host app, WebView provider, JSBridge, WebSettings, and installation metadata;
- Web Runtime signals: Navigator, display, WebGL, Canvas, Audio, fonts, permissions, and automation surfaces.

The primary contribution is not a new classifier. It is an end-to-end pipeline covering tri-layer collection, session alignment, cross-layer semantic corroboration, risk explanation, and lightweight on-device scoring. RandomForest, MLP, and Positive ElasticNet are engineering baselines or fusion components rather than algorithmic contributions.

The active research direction extends the conventional rule-base and single-model pipeline into a knowledge-grounded agentic/RAG architecture. An LLM reasons over grouped evidence, a Verifier checks evidence use and claim boundaries, and a reproducible external model fuses group scores. This architecture is currently a target design with staged validation; it is not yet fully implemented.

### Current Status

Implemented:

- Three isolated Android apps: legacy tri-layer collection (`:app`), on-device scoring (`:riskapp`), and expanded collection (`:featureapp`);
- A FastAPI backend for probe hosting, session merging, expanded-data routing, local-score ingestion, and JSON/JSONL persistence;
- An API-21+ expanded-v2.2-status structure with 177 fields (84 Native, 26 WebView, and 67 Web), plus a collection manifest, per-field status, and probe diagnostics;
- Readiness preflight, Web-timeout fallback, immediate/background retries, partial-payload persistence, collection receipts, and duplicate suppression for `featureapp`;
- 35 risk rules plus 30 Google-official sources and 20 knowledge cards, 15 of which are attached to the main rule base as explanatory metadata;
- Local-LLM label generation, RandomForest/MLP training, Java model export, and an on-device scoring loop that uploads summaries only;
- Endpoint ablation, consistency ablation, and device/template-grouped cross-validation;
- GLM-5.2 direct scoring, K0/K1 official-knowledge ablation, six-group fusion, and a targeted repeated-profile weighting pilot;
- Device-cloud catalogs, thesis and defense artifacts, and publication-oriented figures.

Active work:

- Freeze the authoritative expanded-v2 JSON Schema, canonical field registry, and historical sample manifest;
- Report sessions separately from independent `stable_device_key` / stable-profile counts;
- Collect paired clean/attack/post samples with independent provenance and attack ground truth;
- Run a K1.1 tolerance-rule ablation and cache full original/augmented GLM group scores;
- Evaluate retrieval, verification, fusion, OOD behavior, and leakage under strict grouped splits instead of optimizing only against legacy teacher labels.

The data-audit snapshot dated `2026-07-10` contains 155 sessions: 154 expanded-v2 rows and one expanded-v1 row that must be isolated. The conservative estimate is approximately 80 stable-profile groups. Sessions, stable profiles, and verified physical devices are different quantities.

### Pipeline

```text
Android Native ─┐
WebView Host ───┼─> session_id alignment ─> FastAPI routing and persistence
Web Runtime ────┘                              │
                                              ├─> rule/LLM offline labeling
                                              ├─> consistency features and grouped CV
                                              ├─> six semantic scores + external fusion
                                              └─> lightweight export -> on-device scoring
```

The three runtime paths remain isolated:

| App | Purpose | Uploaded data | Backend output |
|---|---|---|---|
| `:app` | Legacy tri-layer collection | Raw Native/WebView/Web payload | `merged_sessions.json`, `collected_data.jsonl` |
| `:riskapp` | On-device RandomForest scoring | Score, level, reason, and engine summary | `local_score_results.jsonl` |
| `:featureapp` | Expanded-v2 collection | Raw 177-field tri-layer payload | `expanded_merged_sessions.json`, `expanded_collected_data.jsonl` |

`riskapp` runs its Web probe and RandomForest inference locally; the backend receives only a scoring summary. `featureapp` does not contain on-device scoring, and its raw data remains separate from legacy collection data and score summaries.

### Repository Layout

```text
.
├── android_app/
│   ├── HybridGuard/                  # Android Studio project: app/riskapp/featureapp
│   └── ANDROID_STUDIO_APP_USAGE.md   # Launch, networking, and acceptance guide
├── backend_server/                   # FastAPI, Web probe, and local JSON/JSONL outputs
├── scoring/                          # Augmentation, attack samples, rule base, LLM labeling
├── training/                         # MLP/RF training, evaluation, and Java export
├── ablation/                         # Ablations, grouped CV, tables, and paper figures
├── google_official_kb/               # Official sources, knowledge cards, merge reports
├── zhipu_glm_eval/                   # Direct GLM-5.2 risk-scoring evaluation
├── rf_grouped_fusion_validation/     # Low-cost RF proxy for grouped fusion
├── llm_grouped_fusion_validation/    # GLM fusion, knowledge ablation, profile weighting
├── device_cloud_catalog/             # Domestic/international real-device cloud catalogs
├── hybridguard_agent/                # Re-runnable snapshots, label sidecars, QC, and label-free evidence bundles
├── hybridguard_agent_rag_guide/      # Agentic/RAG architecture and routed workbooks
├── thesis_materials/                 # Thesis, chapters, references, journal-style figures
├── presentation/                     # Defense deck, template, and speaker notes
├── archive/                          # Archived submission and historical artifacts
├── web_client/                       # Standalone Web client materials
├── ENVIRONMENT_SETUP.md              # Fresh-clone environment setup
├── LLM_GROUPED_FUSION_PLAN.md        # Six LLM group scores and external fusion plan
├── HYBRIDGUARD_AGENT_RAG_ACTION_GUIDE.md  # Root pointer to the agent guide
├── run_browserstack.py               # BrowserStack collection entry point
└── sauce_appium_smoke.py             # Sauce Labs Appium smoke test
```

### Quick Start

See [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md) for pinned dependencies and validation steps. The primary stack is Python 3.10, Conda, Android Studio, Android `compileSdk` 36.1, JDK 21, and the repository Gradle Wrapper 9.3.1.

#### 1. Start the backend

Start it from `backend_server/`:

```bash
conda activate cross-device-fingerprint
cd backend_server
python main.py
```

Health check:

```bash
curl http://localhost:8000/health
```

Primary endpoints:

- `GET /`: Web fingerprint probe;
- `GET /health`: health check;
- `POST /api/collect/fingerprint`: legacy and expanded-v2 collection;
- `POST /api/risk/local-score`: on-device score summaries.

#### 2. Build the Android apps

Open `android_app/HybridGuard` in Android Studio, not the repository root. Command-line builds:

```bash
cd android_app/HybridGuard
./gradlew :app:assembleDebug
./gradlew :riskapp:assembleDebug
./gradlew :featureapp:assembleDebug
```

All three modules require a backend address appropriate for the target environment. The legacy `:app` and `:riskapp` primarily configure endpoints in their `MainActivity.kt` files; `:featureapp` accepts `-PhybridguardCollectEndpoint=...` at build time. Android emulators normally reach the host through `10.0.2.2`; physical devices can use a LAN address, `adb reverse`, or a temporary tunnel. See [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md).

#### 3. Run core offline experiments

```bash
conda activate cross-device-fingerprint

python ablation/run_randomforest_ablation.py
python ablation/run_consistency_ablation.py
python ablation/run_grouped_ablation.py
python rf_grouped_fusion_validation/run_rf_grouped_fusion_validation.py
python llm_grouped_fusion_validation/prepare_validation_assets.py
```

The training scripts use relative input paths and should be run from `training/`:

```bash
cd training
python train_randomforest.py
python train_mlp.py
```

GLM-5.2 scripts accept `ZHIPU_API_KEY`, `--api-key-file`, or `--api-key-stdin` and do not intentionally persist API keys. See [`zhipu_glm_eval/README.md`](zhipu_glm_eval/README.md) and [`llm_grouped_fusion_validation/README.md`](llm_grouped_fusion_validation/README.md) for online runs.

### Findings and Claim Boundaries

| Validation | Current result | Supported claim | Unsupported claim |
|---|---|---|---|
| Tri-layer semantic features under grouped CV | 7 features, MAE 2.281, RMSE 3.358 | Semantic corroboration is more useful than merely stacking raw fields | Proven real-attack detection accuracy |
| RF-proxy six groups + Positive ElasticNet | MAE 2.968, high-risk F1 1.000 | Group scores and external fusion are reproducible | It beats the strongest tri-layer baseline, or RF is equivalent to an LLM |
| Full-holdout GLM-5.2 risk bands | 263/265, 99.25% | High agreement with existing rule-derived label bands | 99.25% accuracy against independent real-attack truth |
| Targeted K0/K1 official-knowledge ablation | K1 preserved high-risk F1 but did not improve MAE/RMSE | Official evidence improves grounding and reveals tolerance boundaries | Official knowledge already improves overall prediction quality |
| Targeted repeated-profile weighting | MAE 7.983 -> 6.318 | A positive small-sample signal | Completed full fusion or a stable final conclusion |

Key boundaries: structural prevalidation is not full LLM validation; preventing group overlap across folds is not the same as eliminating repeated-profile training bias; legacy `llm_label` values are teacher labels, not independent attack ground truth.

### Documentation Map

| Goal | Entry point |
|---|---|
| Run a fresh clone locally | [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md) |
| Launch the three apps in Android Studio | [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md) |
| Inspect backend APIs and payload examples | [`backend_server/start_server.md`](backend_server/start_server.md) |
| Review ablations and grouped CV | [`ablation/README.md`](ablation/README.md) |
| Inspect the Google-official knowledge base | [`google_official_kb/README.md`](google_official_kb/README.md) |
| Review the LLM grouped-fusion design | [`LLM_GROUPED_FUSION_PLAN.md`](LLM_GROUPED_FUSION_PLAN.md) |
| Read the GLM targeted pilot | [`llm_grouped_fusion_validation/PILOT_REPORT.md`](llm_grouped_fusion_validation/PILOT_REPORT.md) |
| Freeze data and inspect the Week 7 label join | [`hybridguard_agent/README.md`](hybridguard_agent/README.md) |
| Continue the Agentic/RAG roadmap | [`hybridguard_agent_rag_guide/README.md`](hybridguard_agent_rag_guide/README.md) |
| Reuse thesis/publication materials | [`thesis_materials/README.md`](thesis_materials/README.md) |
| Review device-cloud research | [`device_cloud_catalog/`](device_cloud_catalog/) |

### Security and Data Notes

- Do not commit API keys, BrowserStack/Sauce Labs credentials, long-lived tunnel URLs, or machine-specific absolute paths.
- Raw device fingerprints may contain private or linkable information; sanitize, sample, and review them before sharing.
- Some Android endpoints remain hardcoded and must be checked before running or publishing the project.
- Agent tasks should begin at `hybridguard_agent_rag_guide/README.md` and read only the one or two routed workbooks relevant to the current task.
