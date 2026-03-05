启动服务

# 使用 uvicorn 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000

测试接口的 curl 命令

curl -X POST http://localhost:8000/api/collect/fingerprint \
-H "Content-Type: application/json" \
-d '{
    "session_id": "uuid-xxxx-xxxx-xxxx",
    "timestamp": 1678888888,
    "client_ip": "192.168.1.100",
    "android_native_data": {
    "device_model": "Pixel 7 Pro",
    "device_brand": "Google",
    "os_version": "Android 13",
    "cpu_abi": "arm64-v8a",
    "total_memory_gb": 11.5,
    "screen_resolution_physical": "1440x3120",
    "uptime_ms": 3600500
    },
    "webview_data": {
    "user_agent": "Mozilla/5.0 (Linux; Android 13; wv)...",
    "screen_resolution_logical": "412x892",
    "device_pixel_ratio": 3.5,
    "webgl_vendor": "Qualcomm",
    "webgl_renderer": "Adreno (TM) 730",
    "canvas_hash": "a1b2c3d4e5f6",
    "compute_task_time_ms": 12.5,
    "jsbridge_injected": true
    },
    "web_data": {
    "user_agent": "Mozilla/5.0 (Linux; Android 13)...",
    "screen_resolution_logical": "412x892",
    "device_pixel_ratio": 3.5,
    "webgl_vendor": "Qualcomm",
    "webgl_renderer": "Adreno (TM) 730",
    "canvas_hash": "a1b2c3d4e5f6",
    "compute_task_time_ms": 13.2
    }
}'

预期响应

{
"status": "success",
"session_id": "uuid-xxxx-xxxx-xxxx",
"message": "设备指纹数据已成功收集"
}

控制台日志示例

2026-03-05 10:30:45,123 - __main__ - INFO - ✅ 成功接收设备指纹数据 | Session ID: uuid-xxxx-xxxx-xxxx | 时间: 2023-03-15 21:21:28 | 客户端IP:
192.168.1.100