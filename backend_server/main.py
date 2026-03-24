import json
import logging
from datetime import datetime
import os
from typing import Optional
import copy

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic 模型定义
# 👇 1. 先定义 Android 原生特征的 6 个子层级 Model
class BuildFingerprintLayer(BaseModel):
    device_model: Optional[str] = None
    device_brand: Optional[str] = None
    device_manufacturer: Optional[str] = None
    device_product: Optional[str] = None
    device_board: Optional[str] = None
    device_hardware: Optional[str] = None
    os_version: Optional[str] = None
    os_api_level: Optional[int] = None
    cpu_abi: Optional[str] = None
    build_fingerprint: Optional[str] = None
    build_tags: Optional[str] = None
    build_type: Optional[str] = None
    uptime_ms: Optional[int] = None

class NativeMemoryLayer(BaseModel):
    total_memory_gb: Optional[float] = None
    avail_memory_gb: Optional[float] = None
    is_low_memory: Optional[bool] = None

class NativeScreenLayer(BaseModel):
    screen_resolution_physical: Optional[str] = None
    screen_density_dpi: Optional[int] = None
    screen_xdpi: Optional[float] = None
    screen_ydpi: Optional[float] = None
    screen_scaled_density: Optional[float] = None

class BatteryDynamicsLayer(BaseModel):
    battery_level_pct: Optional[float] = None
    battery_temp_celsius: Optional[float] = None
    battery_voltage_mv: Optional[int] = None
    is_charging: Optional[bool] = None

class SensorMatrixLayer(BaseModel):
    sensor_total_count: Optional[int] = None
    has_gyroscope: Optional[bool] = None
    has_accelerometer: Optional[bool] = None
    has_magnetic_field: Optional[bool] = None
    has_light_sensor: Optional[bool] = None
    has_proximity_sensor: Optional[bool] = None
    has_pressure_sensor: Optional[bool] = None

class SecurityConfigLayer(BaseModel):
    is_adb_enabled: Optional[bool] = None

# 👇 2. 将它们组合进最终的原生模型中
class AndroidNativeData(BaseModel):
    """Android 原生数据模型 (工业级分层版)"""
    build_fingerprint_layer: Optional[BuildFingerprintLayer] = Field(None, description="构建指纹层")
    memory_layer: Optional[NativeMemoryLayer] = Field(None, description="物理内存层")
    screen_display_layer: Optional[NativeScreenLayer] = Field(None, description="物理显示层")
    battery_dynamics_layer: Optional[BatteryDynamicsLayer] = Field(None, description="电池动态层")
    sensor_matrix_layer: Optional[SensorMatrixLayer] = Field(None, description="传感器矩阵层")
    security_config_layer: Optional[SecurityConfigLayer] = Field(None, description="安全配置层")

# 👇 1. 先定义 WebView 容器的子层级 Model
class BridgeRoutingLayer(BaseModel):
    jsbridge_injected: Optional[bool] = None
    bridge_latency_ms: Optional[float] = None

class KernelContainerLayer(BaseModel):
    webview_provider_package: Optional[str] = None
    webview_provider_version: Optional[str] = None
    webview_provider_version_code: Optional[int] = None
    system_http_agent: Optional[str] = None
    default_ua_native: Optional[str] = None

class HostSecurityLayer(BaseModel):
    is_debuggable: Optional[bool] = None
    app_package_name: Optional[str] = None
    installer_package: Optional[str] = None
    is_cleartext_traffic_permitted: Optional[bool] = None

class TemporalBuildLayer(BaseModel):
    first_install_time: Optional[int] = None
    last_update_time: Optional[int] = None
    target_sdk_version: Optional[int] = None
    min_sdk_version: Optional[int] = None

class ExceptionLayer(BaseModel):
    error_msg: Optional[str] = None

# 👇 2. 将它们组合进最终的容器模型中
class WebViewData(BaseModel):
    """WebView 容器与宿主环境特征 (工业级分层版)"""
    bridge_routing_layer: Optional[BridgeRoutingLayer] = Field(None, description="通信桥接层")
    kernel_container_layer: Optional[KernelContainerLayer] = Field(None, description="内核容器层")
    host_security_layer: Optional[HostSecurityLayer] = Field(None, description="宿主安全层")
    temporal_build_layer: Optional[TemporalBuildLayer] = Field(None, description="时间与编译层")
    exception_layer: Optional[ExceptionLayer] = Field(None, description="异常记录层")
    
# 👇 1. 先定义子层级的 Model
class NavigatorLayer(BaseModel):
    user_agent: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    hardware_concurrency: Optional[int] = None
    device_memory: Optional[float] = None
    max_touch_points: Optional[int] = None

class ScreenLayer(BaseModel):
    screen_resolution_logical: Optional[str] = None
    device_pixel_ratio: Optional[float] = None
    color_depth: Optional[int] = None
    pixel_depth: Optional[int] = None
    avail_width: Optional[int] = None
    avail_height: Optional[int] = None

class GraphicsLayer(BaseModel):
    webgl_vendor: Optional[str] = None
    webgl_renderer: Optional[str] = None
    webgl_extensions_count: Optional[int] = None
    canvas_hash: Optional[str] = None

class ExecutionLayer(BaseModel):
    compute_task_time_ms: Optional[float] = None
    timezone_offset: Optional[int] = None

# 👇 2. 再将它们组合进最终的 WebData 模型中
class WebData(BaseModel):
    """Web 数据模型 (工业级分层版)"""
    navigator_layer: Optional[NavigatorLayer] = Field(None, description="导航器环境层")
    screen_layer: Optional[ScreenLayer] = Field(None, description="屏幕显示层")
    graphics_layer: Optional[GraphicsLayer] = Field(None, description="图形渲染层")
    execution_layer: Optional[ExecutionLayer] = Field(None, description="执行算力层")

class FingerprintPayload(BaseModel):
    """设备指纹数据载荷"""
    session_id: str = Field(..., description="会话ID")
    timestamp: int = Field(..., description="时间戳(Unix)")
    client_ip: Optional[str] = Field(None, description="客户端IP地址")
    android_native_data: Optional[AndroidNativeData] = Field(None, description="Android 原生数据")
    webview_data: Optional[WebViewData] = Field(None, description="WebView 数据")
    web_data: Optional[WebData] = Field(None, description="Web 数据")


# 创建 FastAPI 应用
app = FastAPI(
    title="跨端设备指纹收集服务",
    description="用于收集和验证跨设备指纹数据",
    version="1.0.0"
)

# 允许跨域资源共享（CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（仅限本地测试阶段这样写，生产环境需要改回具体域名）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法 (POST, GET 等)
    allow_headers=["*"],  # 允许所有请求头
)

# 模拟一个内存数据库，用于根据 session_id 暂存和合并数据
sessions_db = {}

# 如果本地已有数据文件，启动时先加载进来（防止重启服务器丢数据）
DB_FILE = "merged_sessions.json"
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r", encoding="utf-8") as f:
        sessions_db = json.load(f)

@app.get("/")
async def serve_frontend():
    """直接用 FastAPI 托管前端网页"""
    return FileResponse("index.html")

@app.post("/api/collect/fingerprint")
async def collect_fingerprint(payload: FingerprintPayload):
    """
    收集设备指纹数据

    Args:
        payload: 设备指纹数据载荷

    Returns:
        成功响应
    """
    try:
        # # 打印接收日志
        # dt = datetime.fromtimestamp(payload.timestamp)
        # logger.info(
        #     f"✅ 成功接收设备指纹数据 | Session ID: {payload.session_id} | "
        #     f"时间: {dt.strftime('%Y-%m-%d %H:%M:%S')} | "
        #     f"客户端IP: {payload.client_ip}"
        # )

        # # 数据持久化到 JSONL 文件
        # data_dict = payload.model_dump()
        # with open("collected_data.jsonl", "a", encoding="utf-8") as f:
        #     json.dump(data_dict, f, ensure_ascii=False)
        #     f.write("\n")
        session_id = payload.session_id
    
        # 1. 检查是否是新会话。如果是，初始化一条空记录
        if session_id not in sessions_db:
            sessions_db[session_id] = {
                "session_id": session_id,
                "timestamp": payload.timestamp,
                "client_ip": payload.client_ip,
                "android_native_data": None,
                "webview_data": None,
                "web_data": None
            }
            print(f"发现新会话创建: {session_id}")
        else:
            print(f"收到已有会话的数据补充: {session_id}")

        # 2. 提取前端真正传过来的非空数据 (排除掉为 None 的默认字段)
        # 这一步是合并的魔法所在：只有前端传了的数据才会去覆盖现有的库
        incoming_data = payload.dict(exclude_unset=True, exclude_none=True)

        # 3. 将新数据合并到数据库记录中
        if "android_native_data" in incoming_data:
            sessions_db[session_id]["android_native_data"] = incoming_data["android_native_data"]
        if "webview_data" in incoming_data:
            sessions_db[session_id]["webview_data"] = incoming_data["webview_data"]
        if "web_data" in incoming_data:
            sessions_db[session_id]["web_data"] = incoming_data["web_data"]
        
        # 更新最新时间戳和 IP（如果有变化的话）
        if "client_ip" in incoming_data:
            sessions_db[session_id]["client_ip"] = incoming_data["client_ip"]
        sessions_db[session_id]["timestamp"] = incoming_data["timestamp"]

        # 4. 将合并后的全量数据持久化保存到本地 JSON 文件 (这里保存的是原始嵌套结构)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions_db, f, ensure_ascii=False, indent=4)

        current_session = sessions_db[session_id]
        
        # 👇 核心新增：数据降维 (Flatten) 逻辑
        if current_session.get("android_native_data") and current_session.get("web_data"):
            import copy
            llm_session_data = copy.deepcopy(current_session)
            
            # 1. 拍平 Web 前端数据
            if "web_data" in llm_session_data and llm_session_data["web_data"]:
                flat_web_data = {}
                for layer_name, layer_dict in llm_session_data["web_data"].items():
                    if isinstance(layer_dict, dict):
                        flat_web_data.update(layer_dict)
                llm_session_data["web_data"] = flat_web_data

            # 2. 拍平 Android 原生数据
            if "android_native_data" in llm_session_data and llm_session_data["android_native_data"]:
                flat_native_data = {}
                for layer_name, layer_dict in llm_session_data["android_native_data"].items():
                    if isinstance(layer_dict, dict):
                        flat_native_data.update(layer_dict)
                llm_session_data["android_native_data"] = flat_native_data

            # 3. 拍平 WebView 容器数据 (新加的逻辑)
            if "webview_data" in llm_session_data and llm_session_data["webview_data"]:
                flat_webview_data = {}
                for layer_name, layer_dict in llm_session_data["webview_data"].items():
                    if isinstance(layer_dict, dict):
                        flat_webview_data.update(layer_dict)
                llm_session_data["webview_data"] = flat_webview_data
            
            # 把彻底扁平化的大模型特供版数据追加到 jsonl 中
            save_to_jsonl(llm_session_data)

        # 返回成功响应
        return {
            "status": "success",
            "session_id": payload.session_id,
            "message": "设备指纹数据已成功收集"
        }

    except Exception as e:
        logger.error(f"处理设备指纹数据时出错: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}

def save_to_jsonl(merged_data: dict):
    jsonl_file_path = "collected_data.jsonl"
    
    # 以 "a" (append 追加) 模式打开文件
    with open(jsonl_file_path, "a", encoding="utf-8") as f:
        # 把字典转成单行 JSON 字符串，并加上换行符
        json_line = json.dumps(merged_data, ensure_ascii=False)
        f.write(json_line + "\n")
        
    print(f"会话 {merged_data.get('session_id')} 已追加到 collected_data.jsonl")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)