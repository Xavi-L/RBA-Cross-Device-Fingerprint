# HybridGuard Android Studio 使用说明

本文档主要说明如何在 Android Studio 中启动和使用本项目的三种 Android App：

- `:app`：旧三端原始采集 App。
- `:riskapp`：端侧随机森林评分 App。
- `:featureapp`：扩充特征采集 App，当前为 `expanded-v2.2-status`，支持 API 21+。

以下路径默认相对仓库根目录。Android 工程实际位于：

```text
android_app/HybridGuard
```

在 Android Studio 中应打开 `android_app/HybridGuard` 这个目录，不是仓库根目录，也不是上一级 `android_app` 目录。

## 1. 三个 App 的用途区别

| Android Studio 模块 | 桌面图标名 | applicationId | 主要用途 | 是否上传原始指纹 | 后端输出 |
| --- | --- | --- | --- | --- | --- |
| `:app` | `Hybrid Guard` | `com.example.hybridguard` | 旧版 Native / WebView / Web 三端原始采集 | 是 | `backend_server/merged_sessions.json`、`backend_server/collected_data.jsonl` |
| `:riskapp` | `HybridGuard Local Risk` | `com.example.hybridguard.riskapp` | 在手机端本地采集、编码并执行随机森林评分 | 否，只上传评分摘要 | `backend_server/local_score_results.jsonl` |
| `:featureapp` | `HybridGuard Feature Collector` | `com.example.hybridguard.featureapp` | 扩充版三端原始特征采集，固定 177 维并带采集状态 | 是 | `backend_server/expanded_merged_sessions.json`、`backend_server/expanded_collected_data.jsonl`、`backend_server/collection_receipts.jsonl` |

三个 App 的 `applicationId` 不同，可以同时安装在同一台模拟器或真机上。

## 2. Android Studio 准备

1. 打开 Android Studio。
2. 选择 `File -> Open...`。
3. 打开：

   ```text
   android_app/HybridGuard
   ```

4. 如果 Android Studio 提示是否信任项目，选择信任。
5. 等待 Gradle Sync 完成。

本工程的关键构建配置：

- Gradle Wrapper：`9.3.1`
- Android Gradle Plugin：`9.1.0`
- Kotlin Compose plugin：`2.2.10`
- `compileSdk`：Android `36.1`
- `minSdk`：`:app` / `:riskapp` 为 `30`；`:featureapp` 为 `21`
- `targetSdk`：`36`
- Gradle toolchain：JDK `21`

如果 Sync 失败，优先检查：

- Android Studio 是否安装了 Android SDK 36。
- `Settings -> Build, Execution, Deployment -> Build Tools -> Gradle -> Gradle JDK` 是否使用 JDK 21 或 Android Studio 自带 JBR。
- 网络是否能访问 Gradle / Maven 仓库。本项目在 `settings.gradle.kts` 中配置了阿里云 Maven 镜像，但第一次 Sync 仍可能需要下载较多依赖。

## 3. 启动后端服务

三个 App 都可以在 Android Studio 中运行，但只要涉及上传结果，就需要后端服务可访问。

在终端中启动后端：

```bash
cd backend_server
python3 main.py
```

也可以使用：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动后检查：

```bash
curl http://localhost:8000/health
```

正常返回：

```json
{"status":"healthy"}
```

建议始终从 `backend_server/` 目录启动后端，因为服务会在该目录下写入 JSON / JSONL 输出文件。

## 4. 设备与后端地址选择

Android App 里目前存在硬编码后端地址。运行前先根据设备类型确认地址。

### 4.1 Android Studio 模拟器

模拟器访问宿主机电脑的后端，使用：

```text
http://10.0.2.2:8000
```

例如：

```text
http://10.0.2.2:8000/api/collect/fingerprint
http://10.0.2.2:8000/api/risk/local-score
```

`:featureapp` debug APK 默认使用 `http://10.0.2.2:8000/api/collect/fingerprint`，模拟器场景通常无需修改。真机云 APK 建议用 `-PhybridguardCollectEndpoint=...` 在构建时固化最终地址，不要在付费任务前临时改源码。

### 4.2 真机同一局域网

真机不能使用 `10.0.2.2`。如果电脑和手机在同一个 Wi-Fi 下，应使用电脑局域网 IP，例如：

```text
http://192.168.1.10:8000
```

对应接口：

```text
http://192.168.1.10:8000/api/collect/fingerprint
http://192.168.1.10:8000/api/risk/local-score
```

后端需要用 `--host 0.0.0.0` 启动，且电脑防火墙需要允许手机访问 8000 端口。

### 4.3 真机 USB + adb reverse

如果真机通过 USB 连接，也可以使用端口反向代理：

```bash
adb reverse tcp:8000 tcp:8000
```

此时 App 中的后端地址应改成：

```text
http://127.0.0.1:8000
```

注意：使用 `adb reverse` 时，App 里必须写 `127.0.0.1` 或 `localhost`，不能继续写 `10.0.2.2`。

### 4.4 ngrok 或其他公网转发

如果需要云真机、外网真机或跨网络访问，可以使用 ngrok，把 App 地址改成 ngrok HTTPS 地址，例如：

```text
https://your-ngrok-domain.ngrok-free.app/api/collect/fingerprint
```

不要把长期有效的 ngrok 地址、账号或密钥提交到公开仓库。

## 5. 在 Android Studio 中运行指定 App

1. 确认后端已启动。
2. 在 Android Studio 顶部运行配置下拉框中选择模块：
   - `app`
   - `riskapp`
   - `featureapp`
3. 选择目标设备：模拟器或已连接真机。
4. 点击绿色运行按钮。

如果下拉框里没有对应模块：

1. 选择 `Run -> Edit Configurations...`。
2. 点击 `+`。
3. 选择 `Android App`。
4. `Module` 选择 `app`、`riskapp` 或 `featureapp`。
5. 保存后运行。

也可以在 Android Studio 的 Terminal 里先确认构建是否通过：

```bash
cd android_app/HybridGuard
./gradlew :app:assembleDebug
./gradlew :riskapp:assembleDebug
./gradlew :featureapp:assembleDebug
```

## 6. `:app` 旧三端原始采集 App

### 6.1 适用场景

`:app` 是最早的三端采集链路，用于采集：

- Android Native 层：Build、内存、物理屏幕、电池、传感器、安全配置等。
- WebView 宿主层：WebView provider、宿主 App 状态、默认 UA、安装时间等。
- Web 层：由后端托管的 `index.html` 探针采集 Navigator、Screen、WebGL、Canvas、算力挑战等。

它会上传原始三端指纹，主要用于旧数据采集和后端合并链路验证。

### 6.2 当前代码中的地址

当前 `:app` 需要关注这个文件：

```text
app/src/main/java/com/example/hybridguard/MainActivity.kt
```

其中有两个地址位置需要一起检查：

- `myWebView.loadUrl(...)`：WebView 加载探针网页。
- `Request.Builder().url(...)`：Native 层 POST 上传地址。

当前代码里这两个地址仍是一个 ngrok 地址。若使用本机模拟器和本机后端，建议改为：

```kotlin
myWebView.loadUrl("http://10.0.2.2:8000", extraHeaders)
```

以及：

```kotlin
.url("http://10.0.2.2:8000/api/collect/fingerprint")
```

真机时按第 4 节替换成局域网 IP、`127.0.0.1` + `adb reverse`，或 ngrok 地址。

### 6.3 运行后如何判断成功

运行 `:app` 后：

1. App 启动时会生成一个 `session_id`。
2. Native 层会先 POST 到后端。
3. WebView 会加载后端页面，页面通过 JSBridge 补充 WebView / Web 层数据。
4. 后端按同一个 `session_id` 合并。

成功后查看：

```text
backend_server/merged_sessions.json
backend_server/collected_data.jsonl
```

如果只看到 Native 数据，没有 Web 数据，通常是 WebView 没有成功加载后端页面，优先检查 `myWebView.loadUrl(...)` 的地址。

## 7. `:riskapp` 端侧评分 App

### 7.1 适用场景

`:riskapp` 用于验证端侧部署链路。它会：

1. 在手机端采集 Native 层特征。
2. 加载本地 `assets/local_probe.html`，采集 WebView / Web 层特征。
3. 用 `RiskFeatureEncoder.java` 编码为训练阶段固定的 65 维输入。
4. 调用 `DeviceRiskScorer.java` 中 m2cgen 导出的随机森林模型。
5. 只上传评分摘要，不上传原始三端指纹。

### 7.2 当前代码中的地址

需要关注：

```text
riskapp/src/main/java/com/example/hybridguard/riskapp/MainActivity.kt
```

其中：

```kotlin
private const val SCORE_ENDPOINT =
    "https://hemispheric-overmoist-candance.ngrok-free.dev/api/risk/local-score"
```

模拟器 + 本机后端时，建议改为：

```kotlin
private const val SCORE_ENDPOINT =
    "http://10.0.2.2:8000/api/risk/local-score"
```

真机时按第 4 节替换。

### 7.3 运行后如何判断成功

运行 `:riskapp` 后，界面上应该看到：

- Session ID。
- 本地随机森林风险分，例如 `Score xx.x / 100`。
- 上传状态。

成功后查看：

```text
backend_server/local_score_results.jsonl
```

如果界面显示本地分数但上传失败，说明端侧采集和评分已经跑通，问题只在后端地址或网络连接。

## 8. `:featureapp` v2 扩充特征采集 App

### 8.1 适用场景

`:featureapp` 是当前推荐用于扩充原始特征采集的 App，不做端侧评分，支持 Android API 21+。当前上报：

```text
collector_app=featureapp
schema_version=expanded-v2.2-status
```

固定字段键名统计为 177 维：

- Android Native：84 维。
- WebView 容器：26 维。
- Web 运行时：67 维。

每条记录同时带 `collection_manifest`、逐字段 `collection_status` 和探针级 `collection_diagnostics`。旧系统不支持的新 API 会记为 `unsupported_by_os`，不是强行填成“成功”；Web 探针超时也会保底上传 Native 和状态信息。

### 8.2 当前代码中的地址

默认 endpoint 由 `featureapp/build.gradle.kts` 的 BuildConfig 生成。模拟器默认地址是：

```text
http://10.0.2.2:8000/api/collect/fingerprint
```

真机或云平台构建：

```bash
./gradlew :featureapp:assembleDebug \
  -PhybridguardCollectEndpoint=https://example.test/api/collect/fingerprint
```

App 上传前会检查 `/api/collect/readiness`，POST 后会验证后端 collection receipt；仅收到 HTTP 200 不再等于采集成功。

### 8.3 运行后如何判断成功

运行 `:featureapp` 后，界面上应该看到：

- Session ID。
- `Expanded Native layer collected...`
- `Uploading expanded feature payload...`
- 上传成功后显示 `Expanded payload uploaded. Field status: ...`

成功后查看：

```text
backend_server/expanded_merged_sessions.json
backend_server/expanded_collected_data.jsonl
backend_server/collection_receipts.jsonl
```

`expanded_merged_sessions.json` 保存嵌套三端结构；`expanded_collected_data.jsonl` 保存完整或部分记录；`collection_receipts.jsonl` 用于核对服务器收到的 payload hash、重复抑制和状态警告。完整采集与付费前验收见 `featureapp/COLLECTION_METADATA.md`。

## 9. 推荐使用顺序

如果另一个研究员只是要开始采集或复现实验，建议按下面顺序：

1. 先启动后端并访问 `/health`。
2. 在 Android Studio 中运行 `:featureapp`，确认扩充采集链路可用。
3. 再运行 `:riskapp`，确认端侧评分链路可用。
4. 只有需要复查旧三端原始采集链路时，再运行 `:app`。

`featureapp` 和 `riskapp` 都使用本地 assets 探针，Android Studio 调试时更稳定；旧 `:app` 依赖后端托管页面，地址配置更容易出错。

## 10. 常见问题

### 10.1 Gradle Sync 失败

先确认 Android Studio 打开的目录是：

```text
android_app/HybridGuard
```

再检查 SDK 36、JDK 21 和网络依赖下载。如果第一次打开项目，Gradle Wrapper 和依赖下载会比较慢。

### 10.2 App 显示上传失败

按顺序检查：

1. 后端是否在运行。
2. `curl http://localhost:8000/health` 是否成功。
3. 模拟器是否使用 `10.0.2.2`。
4. 真机是否使用电脑局域网 IP、ngrok，或已经执行 `adb reverse`。
5. App 中的 endpoint 是否与当前访问方式一致。

### 10.3 模拟器能跑，真机不能上传

这是最常见的地址问题。`10.0.2.2` 只适用于 Android Studio 模拟器。真机需要局域网 IP、ngrok，或 `adb reverse` + `127.0.0.1`。

### 10.4 后端没有生成期望文件

确认运行的是哪个 App：

- `:app` 写入 `merged_sessions.json` / `collected_data.jsonl`。
- `:riskapp` 写入 `local_score_results.jsonl`。
- `:featureapp` 写入 `expanded_merged_sessions.json` / `expanded_collected_data.jsonl`。

还要确认后端是从 `backend_server/` 目录启动的。

### 10.5 `:app` 只有 Native 数据，没有 Web 数据

旧 `:app` 的 Web 层来自 `myWebView.loadUrl(...)` 加载的后端页面。如果这个 URL 没改对，Native POST 可能成功，但 WebView / Web 层不会补齐。

### 10.6 `:riskapp` 上传失败但分数显示正常

这通常说明端侧采集、特征编码和随机森林推理已经成功；只需要修正 `SCORE_ENDPOINT` 或后端网络。

## 11. 交付数据前的注意事项

这些 App 会采集设备指纹、WebView 环境、浏览器运行时和网络状态等信息。共享 JSON / JSONL 前，应先确认是否需要脱敏或抽样，尤其不要公开：

- 长期可用的 ngrok 地址。
- BrowserStack、云真机或其他平台凭证。
- 可追溯到真实个人设备的原始指纹记录。
- 本机或实验室内网地址等敏感环境信息。
