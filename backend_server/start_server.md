# 后端服务启动与接口测试

本目录下的 FastAPI 服务负责托管 Web 探针、接收三端设备指纹、按 `session_id` 合并会话，并接收 `riskapp` 端侧评分摘要。

## 启动服务

正式云测采集时，在 `backend_server/` 目录下启动一个后端进程：

```bash
python3 main.py
```

也可以直接使用单 worker 的 uvicorn：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

一次后端进程从启动到停止就是一个自动生成的 `collection_batch_id`。多台云设备可以同时安装、打开 App 并上传；它们会并发连接到同一个后端，但在单 worker 内依次落盘，仍属于同一批次。App 不需要设置任何 batch Intent 参数。

当前持久化层是单进程 JSON/JSONL 文件。采集时保持一个 uvicorn worker；不要用 `--workers 2+`，也不要在同一目录启动第二个后端实例，否则多个进程会各自维护内存 session DB 并竞争写文件。正式采集不要使用 `--reload`：每次重载都会形成新的后端生命周期、也就是新批次。开发调试时可以使用 `--reload`，但不要把它的连续数据当成一个正式批次。若后续需要多 worker，应先把持久化迁移到数据库。

启动后访问：

- `GET /`：返回 `index.html` 前端探针。
- `GET /health`：健康检查。
- `GET /api/collect/readiness`：付费采集前检查 expanded schema、部分 payload 保存和回执能力，并显示当前打开的 `collection_batch_id`。
- `POST /api/collect/fingerprint`：接收 Native、WebView、Web 三端指纹分层 payload。
- `POST /api/risk/local-score`：接收 Android 端侧随机森林评分摘要。

## 健康检查

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/collect/readiness
```

预期响应：

```json
{"status":"healthy"}
```

## 正式批次结束与 provenance 导出

在云测平台开始前启动服务并记录 `/api/collect/readiness` 返回的
`collection_batch_id`（仅用于核对，不需要填入 App）。平台完成后用 `Ctrl+C` 正常停止
后端；这会关闭该批次。随后运行：

```bash
python3 export_session_provenance.py \
  --platform-provider '<platform-name>' \
  --input raw_expanded_payloads.jsonl \
  --receipts collection_receipts.jsonl \
  --output session_provenance.jsonl
```

导出器会自动选择 `collection_batches.jsonl` 中最新的已关闭批次，不需要
`--collection-batch-id`。平台名仍需明确提供，因为它参与 Profile HMAC，不能由后端
或批次 ID 诚实推断；没有真实平台 run ID 时不要填写 `--platform-run-id`。

## 三端指纹采集接口

当前后端模型使用分层结构。一次会话可以分多次上报，只要 `session_id` 相同，后端会合并到 `merged_sessions.json`；当 Native 和 Web 数据都存在时，会追加扁平化记录到 `collected_data.jsonl`。

`featureapp` 扩充采集模块会带上 `collector_app=featureapp` 和 `schema_version=expanded-v2.2-status`（后端仍兼容 expanded-v2/v2.1）。后端把完整或部分 expanded payload 单独写入 `expanded_merged_sessions.json` 和 `expanded_collected_data.jsonl`，并把 payload hash、重复抑制和验证警告写入 `collection_receipts.jsonl`。每条 receipt 和新的 `raw_expanded_payloads.jsonl` archive envelope 都自动附带当前 `collection_batch_id`；这不改变客户端 payload hash。新接收的 expanded 请求还会在合并/扁平化前写入 `raw_expanded_payloads.jsonl`，用于以 receipt 的 canonical `payload_sha256` 验证原始嵌套 payload；详见 `README.md`。

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
- `raw_expanded_payloads.jsonl`：追加保存新接收的 expanded canonical payload、receipt ID 与 payload hash；这是 provenance 导出的原始 payload 来源。
- `collection_receipts.jsonl`：每次 expanded 请求的服务器回执、payload hash、重复状态和非阻断验证警告。
- `collection_batches.jsonl`：后端生命周期批次账本，记录 `started`、正常 `closed_cleanly` 或下次启动恢复的 `unclean_shutdown_recovered`。它不是平台 run ID。
- `active_collection_batch.json`：仅在服务运行期间存在的本地恢复标记；正常停止时删除，异常停止后由下一次启动处理。
- `session_provenance.jsonl`：由 `export_session_provenance.py` 生成的 Profile、轮次与 receipt 关联 sidecar，不包含或替代 177 维原始 payload。
- `local_score_results.jsonl`：追加保存端侧评分摘要。

## `featureapp` 扩充特征维度

按固定字段键名统计，`featureapp` 当前扩充采集共 `177` 维：

- Android Native：`84` 维，新增 EGL/OpenGL ES 原生 GPU 佐证字段，异常情况下会额外上报 `graphics_layer.graphics_probe_error`。
- WebView 容器：`26` 维，异常情况下会额外上报 `exception_layer.error_msg`。
- Web 运行时：`67` 维，新增 AudioContext、字体 hash、Permissions API 状态和 plugin/MIME hash 字段。

App 界面里的 `Expanded feature count` 会把数组字段按元素个数计数，因此实机显示值可能随 `supported_abis`、`sensor_type_list`、`active_transport_types`、`languages` 的长度变化。

公开共享或投稿附录前，需要先评估这些 JSON/JSONL 文件中的原始指纹字段是否需要脱敏或抽样发布。
