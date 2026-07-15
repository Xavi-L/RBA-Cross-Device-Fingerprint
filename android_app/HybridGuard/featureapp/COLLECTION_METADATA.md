# featureapp 采集契约与付费批次验收

`:featureapp` 当前面向 Android API 21+，上报 `expanded-v2.2-status`。177 个原始信号仍按 Native 84、WebView 26、Web 67 的固定口径组织；新增对象都是采集元数据，不能作为模型特征。

## 三类元数据

- `collection_manifest`（`device-profile-manifest-v1`）：记录安装/Profile、Android API、WebView/App 版本、运行批次与轮次，用于稳定分组和追溯；
- `collection_status`（`field-status-v1`）：对 177 个固定信号逐项记录 `observed`、`unsupported_by_os`、`permission_denied`、`runtime_error`、`timeout` 或 `not_applicable`；
- `collection_diagnostics`：记录 Web 子探针状态和 Native 侧保底原因，用于解释默认值或空值来自“不支持”还是“采集失败”。

这里的 `collection_status.fields` 是采集可用性；攻击登记表中的 `field_effect_status` 是“干预是否改变了目标字段”。二者语义不同，不能互相替代。

## API 21+ 降级原则

`minSdk` 已降到 21，但新 API 不会被强行调用：Display Mode、Security Patch、NetworkCapabilities、cleartext policy、WebView provider、managed-profile 等能力按系统版本守卫。旧系统不支持的字段保留在 177 字段契约中，值为 `null`，状态为 `unsupported_by_os`；它们不是采集失败，也不要求伪造非空值。

运行 `python3 device_cloud_catalog/verify_featureapp_api21_coverage.py` 可复核当前百度 MTC CSV：1064 行中 Android 5.0+ 共 1060 行，只有 4 行 Android 4.4 被明确排除。

本地 Web 探针已移除 `async/await`、箭头函数、`Array.from` 等旧 WebView 可能无法解析的语法。若 WebView 页面、JSBridge 或子探针仍在 15 秒内没有返回，Native 层会生成带 `timeout` 状态的部分 payload 并继续上传，不会整条丢弃。

## 稳定画像和编排参数

首次启动会在 App 私有存储生成 `collector_install_id`。未提供外部设备标识时，它也作为 `device_manifest_id`，因此代表“该次安装所在的 Android Profile”，不等于跨重装、跨云机生命周期的物理设备 ID。

编排端可传入：

```text
com.example.hybridguard.featureapp.DEVICE_MANIFEST_ID  # provider/device 稳定标识
com.example.hybridguard.featureapp.RUNTIME_CONTEXT     # provider:run-id 等批次上下文
com.example.hybridguard.featureapp.COLLECTION_ROUND    # 同一 run 的轮次，从 1 开始
com.example.hybridguard.featureapp.COLLECT_ENDPOINT    # 仅 debug APK 接受的临时 endpoint
```

`DEVICE_MANIFEST_ID` 只接受 1–96 位字母、数字、`.`、`_`、`:`、`-`。攻击工具、攻击结果、clean/active/post 角色和人工标签必须留在独立登记表中。

## Endpoint、readiness 与回执

默认 endpoint 为模拟器使用的 `http://10.0.2.2:8000/api/collect/fingerprint`。为真机云构建 APK 时用 Gradle 属性固化地址：

```bash
./gradlew :featureapp:assembleDebug \
  -PhybridguardCollectEndpoint=https://example.test/api/collect/fingerprint
```

App 每个进程首次上传前会验证 `GET /api/collect/readiness`，确认后端支持当前 schema、部分 payload 和 collection receipt。POST 成功后还会检查响应中的 `receipt_id`、`session_id` 与 `payload_sha256`；仅 HTTP 200 或 ngrok HTML 页面不会被误判为采集成功。

后端输出：

- `expanded_merged_sessions.json`：按 session 保存的原始嵌套结构；
- `expanded_collected_data.jsonl`：完整或部分 expanded payload；
- `collection_receipts.jsonl`：每次请求的服务器接收时间、payload hash、重复抑制和验证警告。

## 付费批次前最低验收

1. 用最终部署地址构建 APK，并访问 `/api/collect/readiness`；
   当前后端必须保持单 uvicorn worker，不能让多个进程竞争 JSON/JSONL 文件；
2. 运行 `./gradlew :featureapp:lintDebug` 和 `./gradlew :featureapp:assembleDebug`；
3. 用本地 API 21、23、26、30 和最新 API 模拟器走至少一遍安装、启动、上传；免费随机真机只补充厂商差异，不承担完整边界覆盖；
4. 检查 App 显示 Uploaded，且 `collection_receipts.jsonl` 有相同 session 的有效回执；
5. 运行 `hybridguard_agent/scripts/run_pipeline.py`，确认新批次没有 schema/status 错误后再启动付费任务。

Android Lint 能确认代码不存在未守卫的新 API 调用，但不能证明 1060 台设备的厂商 WebView、网络和云平台编排都相同，因此保底上传、逐字段状态和服务器回执仍然必须保留。
