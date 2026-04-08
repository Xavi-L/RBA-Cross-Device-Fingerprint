import json
import random
import uuid
import time

def get_base_record(timestamp):
    """生成一个包含 100% 完整字段的基础骨架"""
    return {
        "session_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "client_ip": None,
        "android_native_data": {
            "device_model": "Unknown", "device_brand": "Unknown", "device_manufacturer": "Unknown",
            "device_product": "Unknown", "device_board": "Unknown", "device_hardware": "Unknown",
            "os_version": "Android 13", "os_api_level": 33, "cpu_abi": "arm64-v8a",
            "build_fingerprint": "unknown/release-keys", "build_tags": "release-keys", "build_type": "user",
            "uptime_ms": 1000000, "total_memory_gb": 8.0, "avail_memory_gb": 3.0, "is_low_memory": False,
            "screen_resolution_physical": "1080x2400", "screen_density_dpi": 480, "screen_xdpi": 400.0,
            "screen_ydpi": 400.0, "screen_scaled_density": 3.0, "battery_level_pct": 100.0,
            "battery_temp_celsius": 25.0, "battery_voltage_mv": 4000, "is_charging": False,
            "sensor_total_count": 30, "has_gyroscope": True, "has_accelerometer": True,
            "has_magnetic_field": True, "has_light_sensor": True, "has_proximity_sensor": True,
            "has_pressure_sensor": False, "is_adb_enabled": False
        },
        "webview_data": {
            "jsbridge_injected": True, "bridge_latency_ms": 2.0,
            "webview_provider_package": "com.google.android.webview", "webview_provider_version": "114.0.0.0",
            "webview_provider_version_code": 114000000, "system_http_agent": "Dalvik/2.1.0",
            "is_debuggable": False, "app_package_name": "com.example.hybridguard",
            "installer_package": "com.android.packageinstaller", "is_cleartext_traffic_permitted": True,
            "first_install_time": timestamp * 1000 - 86400000, "last_update_time": timestamp * 1000 - 86400000,
            "target_sdk_version": 33, "min_sdk_version": 24
        },
        "web_data": {
            "user_agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/114.0.0.0 Mobile Safari/537.36",
            "language": "zh-CN", "platform": "Linux aarch64", "hardware_concurrency": 8,
            "device_memory": 8.0, "max_touch_points": 5, "screen_resolution_logical": "360x800",
            "device_pixel_ratio": 3.0, "color_depth": 24, "pixel_depth": 24, "avail_width": 360,
            "avail_height": 800, "webgl_vendor": "Qualcomm", "webgl_renderer": "Adreno (TM) 650",
            "webgl_extensions_count": 25, "canvas_hash": "a1b2c3d4e5f6...",
            "compute_task_time_ms": 250.0, "timezone_offset": -480
        }
    }

def generate_bad_data(output_filepath, count=300):
    bad_data_list = []
    
    for _ in range(count):
        # 随机时间戳（过去一个月内）
        timestamp = int(time.time()) - random.randint(1000, 86400 * 30)
        record = get_base_record(timestamp)
        
        attack_type = random.choice(["api_replay", "headless_pc", "cheap_emulator"])

        if attack_type == "api_replay":
            # 【脱壳重放】：Native 字段全部置空 (模拟没有原生容器的情况)，桥接丢失
            for key in record["android_native_data"]:
                record["android_native_data"][key] = None
            
            record["webview_data"]["jsbridge_injected"] = False
            record["webview_data"]["bridge_latency_ms"] = 0.0
            record["webview_data"]["installer_package"] = None
            
            record["web_data"]["user_agent"] = "python-requests/2.25.1" # 典型的爬虫 UA

        elif attack_type == "headless_pc":
            # 【无头浏览器】：硬件伪造错误，传感器缺失，平台暴露 PC 特征
            record["android_native_data"]["device_model"] = "Windows PC Fake"
            record["android_native_data"]["sensor_total_count"] = 0
            for sensor in ["has_gyroscope", "has_accelerometer", "has_magnetic_field", "has_light_sensor", "has_proximity_sensor"]:
                record["android_native_data"][sensor] = False
            
            record["android_native_data"]["battery_temp_celsius"] = 0.0 # 电池温度死水一潭
            
            record["web_data"]["platform"] = "Win32"
            record["web_data"]["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HeadlessChrome/120.0.0.0 Safari/537.36"
            record["web_data"]["max_touch_points"] = 0
            record["web_data"]["compute_task_time_ms"] = 12.5 # PC CPU 算力过快
            record["web_data"]["webgl_renderer"] = "ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)"

        elif attack_type == "cheap_emulator":
            # 【廉价模拟器】：典型的 x86 架构，金鱼主板，软渲染 GPU
            record["android_native_data"]["device_board"] = "goldfish"
            record["android_native_data"]["device_hardware"] = "ranchu"
            record["android_native_data"]["cpu_abi"] = "x86"
            record["android_native_data"]["sensor_total_count"] = 1
            record["android_native_data"]["battery_temp_celsius"] = 20.0
            record["android_native_data"]["is_adb_enabled"] = True
            
            record["webview_data"]["installer_package"] = "manual"
            
            record["web_data"]["platform"] = "Linux i686"
            record["web_data"]["webgl_renderer"] = "Google SwiftShader" # 模拟器 CPU 软渲染标志
            record["web_data"]["compute_task_time_ms"] = 1500.8 # 算力极差
            record["web_data"]["timezone_offset"] = 0 # 默认 UTC 时区

        bad_data_list.append(record)

    with open(output_filepath, 'w', encoding='utf-8') as f:
        for data in bad_data_list:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
            
    print(f"✅ 成功生成 {count} 条对齐数据格式的高危指纹数据，已保存至 {output_filepath}")

if __name__ == "__main__":
    generate_bad_data("simulated_bad_data.jsonl", 300)