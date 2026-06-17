# 本地环境配置说明

本文档面向刚克隆本项目的开发者，目标是在本地复现 HybridGuard 的主要运行链路：Python 后端、离线评分/训练/消融脚本，以及 Android App 构建。

项目 Python 环境使用 Miniconda，约定环境名为 `cross-device-fingerprint`。

## 1. 基础工具

请先安装或准备以下工具：

- Git
- Miniconda 或 Anaconda
- Python 3.10
- Android Studio，包含 Android SDK 36 和可用模拟器或真机
- JDK 21，或直接使用 Android Studio 自带的 JBR/Gradle toolchain

可选工具：

- LM Studio：用于本地 OpenAI-compatible API 风险打分脚本
- ngrok：用于真机访问本机后端
- BrowserStack 账号：用于 `run_browserstack.py` 云真机采集

## 2. 克隆项目

```bash
git clone <repo-url>
cd RBA-Cross-Device-Fingerprint
```

如果已经克隆好项目，直接进入项目根目录即可。

## 3. 创建 Conda 环境

如果本机还没有该环境：

```bash
conda create -n cross-device-fingerprint python=3.10 -y
conda activate cross-device-fingerprint
python -m pip install --upgrade pip
```

安装项目常用 Python 依赖：

```bash
python -m pip install \
  fastapi==0.135.1 \
  uvicorn==0.41.0 \
  pydantic==2.12.5 \
  pandas==2.3.3 \
  numpy==2.2.6 \
  scikit-learn==1.7.2 \
  scipy==1.15.3 \
  matplotlib==3.10.8 \
  seaborn==0.13.2 \
  torch==2.11.0 \
  joblib==1.5.3 \
  m2cgen==0.10.0 \
  openai==2.28.0 \
  Appium-Python-Client==5.3.0 \
  tqdm==4.67.3
```

如果某个平台暂时装不上完全相同的版本，可以先去掉 `==版本号` 后重试。后端运行只依赖 `fastapi`、`uvicorn`、`pydantic`；训练和实验脚本需要 `pandas`、`numpy`、`scikit-learn`、`matplotlib`、`seaborn`、`torch`、`m2cgen` 等包。

以后进入项目时，先激活环境：

```bash
conda activate cross-device-fingerprint
```

可以用下面的命令快速检查环境是否可用：

```bash
python - <<'PY'
import fastapi
import pandas
import sklearn
import torch
import openai
import m2cgen

print("cross-device-fingerprint Python environment is ready")
PY
```

## 4. 启动后端服务

后端位于 `backend_server/`。请从该目录启动，因为服务会用相对路径读取 `index.html`，并把本地数据写入当前目录下的 JSON/JSONL 文件。

```bash
cd backend_server
python main.py
```

也可以使用 uvicorn：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动成功后，在另一个终端中检查健康状态：

```bash
curl http://localhost:8000/health
```

预期响应：

```json
{"status":"healthy"}
```

后端本地输出文件：

- `backend_server/merged_sessions.json`：按 `session_id` 保存合并后的三端数据
- `backend_server/collected_data.jsonl`：保存扁平化后的三端采集记录
- `backend_server/local_score_results.jsonl`：保存 Android 端侧评分摘要

## 5. 运行离线评分、训练和消融脚本

### 5.1 本地 LLM 风险打分

`scoring/sorting_rule_kb.py` 默认连接本地 LM Studio OpenAI-compatible API：

```text
http://127.0.0.1:1234/v1
```

运行前请先在 LM Studio 中启动本地模型服务，并确认脚本中的模型名或命令行 `--model` 参数与本机模型一致。

示例：

```bash
conda activate cross-device-fingerprint
python scoring/sorting_rule_kb.py --limit 5 --model <local-model-name>
```

默认输入为 `scoring/simulated_bad_data.jsonl`，默认输出为 `scoring/simulated_bad_data_rule_kb_scored.jsonl`。

### 5.2 训练随机森林或 MLP

训练脚本使用相对路径读取 `scored_data.jsonl`，因此需要进入 `training/` 目录运行：

```bash
cd training
python train_randomforest.py
python train_mlp.py
```

随机森林脚本会生成：

- `training/DeviceRiskScorer.java`
- `training/tree_test_predictions_results.csv`

MLP 脚本会生成：

- `training/shallow_risk_net.pth`
- `training/feature_scaler.pkl`
- `training/test_predictions_results.csv`

### 5.3 运行消融实验

消融脚本可以从项目根目录运行：

```bash
conda activate cross-device-fingerprint
python ablation/run_randomforest_ablation.py
python ablation/run_consistency_ablation.py
python ablation/run_grouped_ablation.py
python ablation/make_figures.py
```

输出会写入 `ablation/` 目录。详细说明见 `ablation/README.md`。

## 6. 构建 Android App

Android 工程位于 `android_app/HybridGuard/`，使用仓库内的 Gradle Wrapper。首次构建会下载 Gradle、Android Gradle Plugin 和相关依赖，需要网络可用。

```bash
cd android_app/HybridGuard
./gradlew :riskapp:assembleDebug
```

旧采集 App 也可以单独构建：

```bash
./gradlew :app:assembleDebug
```

推荐优先运行 `:riskapp`，它会在端侧完成三端采集、特征编码和随机森林评分，再把评分摘要上报到后端。

当前 Android 工程关键信息：

- Gradle Wrapper：9.3.1
- Android Gradle Plugin：9.1.0
- Kotlin Compose Plugin：2.2.10
- `compileSdk`：36.1
- `minSdk`：30
- Gradle toolchain：JDK 21

## 7. 配置 App 访问后端

项目中的 Android App 目前包含硬编码后端地址。换机器或换网络时，需要把地址改成当前可访问的后端地址。

旧采集 App：

- `android_app/HybridGuard/app/src/main/java/com/example/hybridguard/MainActivity.kt`
- 需要关注 WebView 加载地址和 `/api/collect/fingerprint` 上报地址

端侧评分 App：

- `android_app/HybridGuard/riskapp/src/main/java/com/example/hybridguard/riskapp/MainActivity.kt`
- 需要关注 `SCORE_ENDPOINT`

如果使用 Android 模拟器访问本机后端，通常可使用：

```text
http://10.0.2.2:8000
```

如果使用 USB 真机，可以选择：

```bash
adb reverse tcp:8000 tcp:8000
```

然后在 App 中使用：

```text
http://127.0.0.1:8000
```

如果使用同一局域网真机，也可以把地址改为电脑的局域网 IP，例如：

```text
http://192.168.x.x:8000
```

如果使用 ngrok，请启动隧道后把 App 中的硬编码 URL 改为新的 ngrok 域名。提交或公开分享代码前，请移除长期可用的 ngrok 地址、BrowserStack 凭证和其他敏感配置。

## 8. 常见问题

### `python main.py` 后访问不到首页

请确认是在 `backend_server/` 目录下启动服务。后端使用 `FileResponse("index.html")`，从项目根目录直接启动可能找不到前端探针页面。

### App 能安装但无法上报

请检查三点：

- 后端是否正在运行，并且 `/health` 返回 healthy
- App 中硬编码的后端 URL 是否是当前设备可访问的地址
- 如果是真机访问本机服务，是否已经配置 ngrok、局域网 IP 或 `adb reverse`

### 离线打分脚本报连接错误

`scoring/sorting_rule_kb.py` 和 `backend_server/rba_engine.py` 默认连接 `http://127.0.0.1:1234/v1`。请先启动 LM Studio 本地服务，或修改脚本中的 `base_url`、模型名和 API Key。

### Gradle 首次构建失败

优先确认 Android Studio、SDK 36、JDK 21 和网络代理是否正常。Gradle Wrapper 会自动下载指定版本的 Gradle，如果网络不可用，首次构建会失败。
