# 后端服务启动与接口测试

本目录下的 FastAPI 服务负责托管 Web 探针、接收三端设备指纹、按 `session_id` 合并会话，并接收 `riskapp` 端侧评分摘要。

## 启动服务

在 `backend_server/` 目录下启动：

```bash
python3 main.py
```

也可以直接使用 uvicorn：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：

- `GET /`：返回 `index.html` 前端探针。
- `GET /health`：健康检查。
- `POST /api/collect/fingerprint`：接收 Native、WebView、Web 三端指纹分层 payload。
- `POST /api/risk/local-score`：接收 Android 端侧随机森林评分摘要。

## 健康检查

```bash
curl http://localhost:8000/health
```

预期响应：

```json
{"status":"healthy"}
```

## 三端指纹采集接口

当前后端模型使用分层结构。一次会话可以分多次上报，只要 `session_id` 相同，后端会合并到 `merged_sessions.json`；当 Native 和 Web 数据都存在时，会追加扁平化记录到 `collected_data.jsonl`。

新增的 `featureapp` 扩充采集模块会在上报中带上 `collector_app=featureapp` 和 `schema_version=expanded-v1`。后端会把这类扩充采集单独写入 `expanded_merged_sessions.json` 和 `expanded_collected_data.jsonl`，不改动旧采集文件。

```bash
curl -X POST http://localhost:8000/api/collect/fingerprint \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "uuid-xxxx-xxxx-xxxx",
    "timestamp": 1678888888,
    "client_ip": "192.168.1.100",
    "android_native_data": {
      "build_fingerprint_layer": {
        "device_model": "Pixel 7 Pro",
        "device_brand": "Google",
        "os_version": "Android 13",
        "cpu_abi": "arm64-v8a",
        "build_fingerprint": "google/panther/panther:13/..."
      },
      "memory_layer": {
        "total_memory_gb": 11.5,
        "avail_memory_gb": 6.2,
        "is_low_memory": false
      },
      "screen_display_layer": {
        "screen_resolution_physical": "1440x3120",
        "screen_density_dpi": 560
      },
      "battery_dynamics_layer": {
        "battery_level_pct": 76.0,
        "is_charging": true
      },
      "sensor_matrix_layer": {
        "sensor_total_count": 32,
        "has_gyroscope": true,
        "has_accelerometer": true
      },
      "security_config_layer": {
        "is_adb_enabled": false
      }
    },
    "webview_data": {
      "bridge_routing_layer": {
        "jsbridge_injected": true,
        "bridge_latency_ms": 2.3
      },
      "kernel_container_layer": {
        "webview_provider_package": "com.google.android.webview",
        "webview_provider_version": "142.0.7444.171",
        "system_http_agent": "Dalvik/2.1.0 ..."
      },
      "host_security_layer": {
        "is_debuggable": false,
        "app_package_name": "com.example.hybridguard",
        "installer_package": "com.android.vending"
      },
      "temporal_build_layer": {
        "target_sdk_version": 36,
        "min_sdk_version": 30
      }
    },
    "web_data": {
      "navigator_layer": {
        "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro; wv) ...",
        "language": "zh-CN",
        "platform": "Linux armv8l",
        "hardware_concurrency": 8
      },
      "screen_layer": {
        "screen_resolution_logical": "412x892",
        "device_pixel_ratio": 3.5,
        "color_depth": 24
      },
      "graphics_layer": {
        "webgl_vendor": "Qualcomm",
        "webgl_renderer": "Adreno (TM) 730",
        "canvas_hash": "a1b2c3d4e5f6"
      },
      "execution_layer": {
        "compute_task_time_ms": 13.2,
        "timezone_offset": -480
      }
    }
  }'
```

预期响应：

```json
{
  "status": "success",
  "session_id": "uuid-xxxx-xxxx-xxxx",
  "message": "设备指纹数据已成功收集"
}
```

## 端侧评分接口

`riskapp` 本地完成三端采集、特征编码和随机森林推理后，只上报评分摘要，不上传三端原始指纹。

```bash
curl -X POST http://localhost:8000/api/risk/local-score \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "uuid-xxxx-xxxx-xxxx",
    "timestamp": 1678888999,
    "risk_score": 42.0,
    "risk_level": "medium",
    "risk_reason": "WebView host and device signals are mostly consistent.",
    "scoring_engine": "random_forest_m2cgen",
    "feature_count": 65
  }'
```

预期响应：

```json
{
  "status": "success",
  "session_id": "uuid-xxxx-xxxx-xxxx",
  "message": "端侧评分结果已接收"
}
```

## 本地输出文件

所有 JSON/JSONL 输出路径都以 `backend_server/main.py` 所在目录为基准。即使从仓库根目录启动服务，数据文件也会写入 `backend_server/` 下。

- `merged_sessions.json`：按 `session_id` 保存最新合并后的嵌套三端数据。
- `collected_data.jsonl`：追加保存扁平化后的三端采集记录，供标注、训练和消融实验使用。
- `expanded_merged_sessions.json`：按 `session_id` 保存 `featureapp` 扩充采集的嵌套三端数据。
- `expanded_collected_data.jsonl`：追加保存 `featureapp` 扩充采集的扁平化实验记录。
- `local_score_results.jsonl`：追加保存端侧评分摘要。

## `featureapp` 扩充特征维度

按固定字段键名统计，`featureapp` 当前扩充采集共 `154` 维：

- Android Native：`79` 维。
- WebView 容器：`26` 维，异常情况下会额外上报 `exception_layer.error_msg`。
- Web 运行时：`49` 维。

App 界面里的 `Expanded feature count` 会把数组字段按元素个数计数，因此实机显示值可能随 `supported_abis`、`sensor_type_list`、`active_transport_types`、`languages` 的长度变化。

公开共享或投稿附录前，需要先评估这些 JSON/JSONL 文件中的原始指纹字段是否需要脱敏或抽样发布。
