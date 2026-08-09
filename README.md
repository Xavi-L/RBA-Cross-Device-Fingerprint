# HybridGuard: RBA Cross-Device Fingerprinting

[中文](#中文说明) | [English](#english)

HybridGuard is a research prototype for risk-based authentication (RBA). The current implementation scope is deliberately narrow: the latest FeatureApp release produces App177, an independent browser probe produces Browser67, and provenance-complete pairs form the formal paired244 unit. The repository also retains earlier apps, datasets, and model experiments as historical assets.

---

## 中文说明

### 项目简介

HybridGuard 面向移动端无感风控与风险认证场景。当前施工范围只包含：

- 最新 `:featureapp` 发布版（versionCode 8）采集的固定 App177；
- 独立 Browser 探针采集的固定 Browser67；
- 具有完整配对来源的 App177 + Browser67，作为正式 `paired244` 数据单元。

如果 Browser 采集失败，有效的 App177 不会被丢弃或填零，而是进入 App-only 留存视图。旧 `:app`、`:riskapp`、旧版数据与旧模型实验管线只作为历史资产保留，属于逻辑归档，不再是当前默认入口。

项目的核心贡献不是提出一个新的分类器，而是建立“三端采集 → 会话对齐 → 跨层语义互证 → 风险解释 → 端侧轻量评分”的完整系统链路。随机森林、MLP 和 Positive ElasticNet 是工程基线或外部融合组件，不应被表述为算法创新。

项目的长期目标仍是“采集 → 配对 → 跨层互证 → 风险解释”。但第一批施工只把最新数据的选择、配对、留存与 QC 框架跑起来，不接入 Agent、Evidence、模型或评分。

### 当前实现状态

当前活跃入口为 [`hybridguard_agent/scripts/build_latest_paired244_snapshot.py`](hybridguard_agent/scripts/build_latest_paired244_snapshot.py)，它只处理 FeatureApp `1.6.1-expanded-v2.2-browser-recovery` / versionCode 8 与对应的独立 Browser67，并产生：

- `paired_244.jsonl`：完成配对且通过契约校验的 244 维主视图；
- `app_only_177.jsonl`：Browser 未完成时保留的有效 App177；
- `quarantine.jsonl`、`sample_index.jsonl`、`selection_audit.jsonl` 以及 QC/manifest 文件。

当前工作树的第一批快照基线为：26 条最新 App177，其中 17 条进入 paired244、9 条进入 App-only 留存、0 条最新 App 被隔离。这些数据当前只用于开发与 QC，且无攻击标签，不能用来报告检测效果。

仓库中仍保留旧采集应用、风险规则、RF/MLP/GLM、消融和 Agentic/RAG 试验资产，但它们属于历史复核材料，不进入当前 paired244 第一批管线。

### 系统链路

```text
最新 FeatureApp ─> App177 ─┐
                              ├─> provenance 配对完成 ─> paired244 主视图
独立 Browser 探针 ─> Browser67 ─┘
                              └─> Browser 未完成 ─> 保留 App-only 177
```

当前与历史运行链路的边界：

| 组件 | 当前定位 | 采集/上传内容 | 主要去向 |
|---|---|---|---|
| `:featureapp` versionCode 8 | **当前活跃** | App177 + 采集状态与 receipt | paired244 或 App-only 177 |
| 独立 Browser 探针 | **当前活跃** | Browser67 + pair provenance | 完成配对时进入 paired244 |
| `:app` | 历史/逻辑归档 | 旧版 Native/WebView/Web payload | 仅用于历史复核 |
| `:riskapp` | 历史/逻辑归档 | 端侧随机森林评分摘要 | 仅用于历史复核 |

App 与 Browser 原始数据分开保存，由快照构建器依据 receipt、已关闭 batch 和 pair provenance 派生 244 维视图；不在采集端伪造或拼接缺失的 Browser 值。

### 仓库结构

```text
.
├── android_app/
│   ├── HybridGuard/                  # Android Studio 工程；当前只以 featureapp 为入口
│   └── ANDROID_STUDIO_APP_USAGE.md   # Android 启动、联网与验收说明
├── browser_probe_site/               # 当前独立 Browser67 探针
├── backend_server/                   # App/Browser 原始数据、receipt、batch 与 pair provenance
├── scoring/                          # 历史规则、攻击样本与 LLM 评分资产
├── training/                         # 历史 MLP/RF 训练与模型导出
├── ablation/                         # 历史消融、grouped CV 与论文结果
├── google_official_kb/               # Google 官方来源、风险卡与合并报告
├── zhipu_glm_eval/                   # GLM-5.2 直接风险评分评估
├── rf_grouped_fusion_validation/     # RF 代理的低成本分组融合预验证
├── llm_grouped_fusion_validation/    # GLM 分组融合、知识消融与重复画像验证
├── device_cloud_catalog/             # 国内外真机云设备目录与统计口径
├── hybridguard_agent/                # 当前 paired244/App-only 快照、QC 与历史管线
├── hybridguard_agent_rag_guide/      # 后期 Agentic/RAG 路线（非第一批）
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
- `POST /api/collect/fingerprint`：FeatureApp App177 上报（同一后端仍保留历史兼容路径）。

#### 2. 构建 Android App

在 Android Studio 中应打开 `android_app/HybridGuard`，而不是仓库根目录。命令行构建：

```bash
cd android_app/HybridGuard
./gradlew :featureapp:assembleDebug
```

当前只验收 `:featureapp`。它用 `-PhybridguardCollectEndpoint=...` 在构建时生成 endpoint。模拟器通常使用 `10.0.2.2`，真机可使用局域网 IP、`adb reverse` 或临时隧道。详细步骤见 [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md)。`:app` 与 `:riskapp` 的构建说明仅供历史复核。

#### 3. 构建当前 paired244 数据视图

```bash
conda activate cross-device-fingerprint
python hybridguard_agent/scripts/build_latest_paired244_snapshot.py \
  --run-id latest_paired244_YYYYMMDD
```

该命令仅做发布版选择、契约校验、配对、App-only 留存和 QC。旧消融、RF/MLP/GLM 与 Agent 管线的脚本仍在仓库中，但不应对当前小样本快照直接运行或作为默认验收。

### 历史实验结论与边界（非当前 paired244 结果）

下表只记录旧数据与旧模型管线的历史实验，不能作为当前 26 条最新 App 快照的评估结论。

| 验证项 | 历史结果 | 可以说明 | 不能说明 |
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
| 用 Android Studio 启动当前 FeatureApp | [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md) |
| 后端接口与 payload 示例 | [`backend_server/start_server.md`](backend_server/start_server.md) |
| 构建最新 paired244/App-only 快照 | [`hybridguard_agent/README.md`](hybridguard_agent/README.md) |
| 历史消融与 grouped CV | [`ablation/README.md`](ablation/README.md) |
| Google 官方知识库 | [`google_official_kb/README.md`](google_official_kb/README.md) |
| 历史 LLM 分组融合方案 | [`LLM_GROUPED_FUSION_PLAN.md`](LLM_GROUPED_FUSION_PLAN.md) |
| 历史 GLM targeted pilot | [`llm_grouped_fusion_validation/PILOT_REPORT.md`](llm_grouped_fusion_validation/PILOT_REPORT.md) |
| 历史数据冻结与标签接入 | [`hybridguard_agent/README.md`](hybridguard_agent/README.md) |
| 后期 Agentic/RAG 行动 | [`hybridguard_agent_rag_guide/README.md`](hybridguard_agent_rag_guide/README.md) |
| 论文和投稿材料 | [`thesis_materials/README.md`](thesis_materials/README.md) |
| 真机云调研 | [`device_cloud_catalog/`](device_cloud_catalog/) |

### 安全与数据说明

- 不要提交 API Key、BrowserStack/Sauce Labs 凭证、长期可用的隧道 URL 或本机绝对路径；
- 原始设备指纹可能包含隐私或可关联信息，公开共享前应脱敏、抽样并审查用途；
- 当前部分 Android endpoint 仍为硬编码配置，运行和公开发布前必须检查；
- 当前数据任务从 `hybridguard_agent/README.md` 进入；Agentic/RAG 分册属于后期路线。

---

## English

### Overview

HybridGuard targets frictionless mobile risk control and risk-based authentication. The current construction scope contains only:

- fixed App177 records from the latest `:featureapp` release (versionCode 8);
- fixed Browser67 records from the independent browser probe;
- App177 + Browser67 records with complete pairing provenance as the formal `paired244` unit.

If browser collection fails, a valid App177 record is retained in the App-only view; browser values are never fabricated or zero-filled. The legacy `:app`, `:riskapp`, older datasets, and older model pipelines remain as logically archived historical assets rather than active entry points.

The long-term goal remains collection, pairing, cross-layer corroboration, and risk explanation. This first construction batch only establishes release selection, pairing, retention, and QC for the latest data. It does not connect the Agent, Evidence, models, or scoring pipeline.

### Current Status

The active entry point is [`hybridguard_agent/scripts/build_latest_paired244_snapshot.py`](hybridguard_agent/scripts/build_latest_paired244_snapshot.py). It only processes FeatureApp `1.6.1-expanded-v2.2-browser-recovery` / versionCode 8 and the corresponding independent Browser67 records. It produces:

- `paired_244.jsonl` for provenance-complete 244-dimensional records that pass contract checks;
- `app_only_177.jsonl` for valid App177 records whose browser side did not complete;
- `quarantine.jsonl`, `sample_index.jsonl`, `selection_audit.jsonl`, plus QC and manifest files.

The current working-tree baseline contains 26 latest-release App177 records: 17 enter paired244, 9 enter App-only retention, and 0 latest App records are quarantined. This data is unlabeled and for development/QC only; it does not support detection-performance claims.

Legacy collection apps, risk rules, RF/MLP/GLM experiments, ablations, and Agentic/RAG prototypes remain in the repository for historical review. They are not part of this first paired244 pipeline.

### Pipeline

```text
Latest FeatureApp ─> App177 ─┐
                              ├─> provenance-complete pairing ─> paired244 main view
Independent browser ─> Browser67 ─┘
                              └─> browser incomplete ─> retain App-only 177
```

Current and historical runtime boundaries:

| Component | Current role | Collected/uploaded data | Main destination |
|---|---|---|---|
| `:featureapp` versionCode 8 | **Active** | App177 plus collection status and receipt | paired244 or App-only 177 |
| Independent browser probe | **Active** | Browser67 plus pair provenance | paired244 when pairing completes |
| `:app` | Historical/logically archived | Legacy Native/WebView/Web payload | Historical review only |
| `:riskapp` | Historical/logically archived | On-device RandomForest score summary | Historical review only |

App and browser raw inputs remain separate. The snapshot builder derives the 244-dimensional view from receipts, closed batches, and pair provenance; missing browser values are not fabricated at collection time.

### Repository Layout

```text
.
├── android_app/
│   ├── HybridGuard/                  # Android Studio project; featureapp is the active entry point
│   └── ANDROID_STUDIO_APP_USAGE.md   # Launch, networking, and acceptance guide
├── browser_probe_site/               # Active independent Browser67 probe
├── backend_server/                   # App/browser raw data, receipts, batches, and pair provenance
├── scoring/                          # Historical rules, attack samples, and LLM assets
├── training/                         # Historical MLP/RF training and model export
├── ablation/                         # Historical ablations, grouped CV, and paper results
├── google_official_kb/               # Official sources, knowledge cards, merge reports
├── zhipu_glm_eval/                   # Direct GLM-5.2 risk-scoring evaluation
├── rf_grouped_fusion_validation/     # Low-cost RF proxy for grouped fusion
├── llm_grouped_fusion_validation/    # GLM fusion, knowledge ablation, profile weighting
├── device_cloud_catalog/             # Domestic/international real-device cloud catalogs
├── hybridguard_agent/                # Active paired244/App-only snapshots, QC, and historical pipelines
├── hybridguard_agent_rag_guide/      # Later Agentic/RAG roadmap (not part of batch one)
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
- `POST /api/collect/fingerprint`: FeatureApp App177 upload (the backend still retains historical compatibility paths).

#### 2. Build the active Android app

Open `android_app/HybridGuard` in Android Studio, not the repository root. Command-line builds:

```bash
cd android_app/HybridGuard
./gradlew :featureapp:assembleDebug
```

Only `:featureapp` is part of the current acceptance scope. It accepts `-PhybridguardCollectEndpoint=...` at build time. Android emulators normally reach the host through `10.0.2.2`; physical devices can use a LAN address, `adb reverse`, or a temporary tunnel. See [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md). Instructions for `:app` and `:riskapp` are retained for historical review only.

#### 3. Build the current paired244 data view

```bash
conda activate cross-device-fingerprint
python hybridguard_agent/scripts/build_latest_paired244_snapshot.py \
  --run-id latest_paired244_YYYYMMDD
```

This command only performs release selection, contract validation, pairing, App-only retention, and QC. Legacy ablation, RF/MLP/GLM, and Agent scripts remain available, but they should not be run directly against the current small snapshot or treated as the default acceptance path.

### Historical Findings and Claim Boundaries (Not Current paired244 Results)

The table below records experiments from older datasets and model pipelines. It is not an evaluation of the current 26-App snapshot.

| Validation | Historical result | Supported claim | Unsupported claim |
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
| Launch the active FeatureApp in Android Studio | [`android_app/ANDROID_STUDIO_APP_USAGE.md`](android_app/ANDROID_STUDIO_APP_USAGE.md) |
| Inspect backend APIs and payload examples | [`backend_server/start_server.md`](backend_server/start_server.md) |
| Build the latest paired244/App-only snapshot | [`hybridguard_agent/README.md`](hybridguard_agent/README.md) |
| Review historical ablations and grouped CV | [`ablation/README.md`](ablation/README.md) |
| Inspect the Google-official knowledge base | [`google_official_kb/README.md`](google_official_kb/README.md) |
| Review the historical LLM grouped-fusion design | [`LLM_GROUPED_FUSION_PLAN.md`](LLM_GROUPED_FUSION_PLAN.md) |
| Read the historical GLM targeted pilot | [`llm_grouped_fusion_validation/PILOT_REPORT.md`](llm_grouped_fusion_validation/PILOT_REPORT.md) |
| Review historical snapshots and label integration | [`hybridguard_agent/README.md`](hybridguard_agent/README.md) |
| Continue the later Agentic/RAG roadmap | [`hybridguard_agent_rag_guide/README.md`](hybridguard_agent_rag_guide/README.md) |
| Reuse thesis/publication materials | [`thesis_materials/README.md`](thesis_materials/README.md) |
| Review device-cloud research | [`device_cloud_catalog/`](device_cloud_catalog/) |

### Security and Data Notes

- Do not commit API keys, BrowserStack/Sauce Labs credentials, long-lived tunnel URLs, or machine-specific absolute paths.
- Raw device fingerprints may contain private or linkable information; sanitize, sample, and review them before sharing.
- Some Android endpoints remain hardcoded and must be checked before running or publishing the project.
- Current data tasks begin at `hybridguard_agent/README.md`; Agentic/RAG workbooks belong to the later roadmap.
