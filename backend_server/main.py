import json
import logging
from datetime import datetime
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic 模型定义
class AndroidNativeData(BaseModel):
    """Android 原生数据模型 (工业级全量版)"""
    # A. 深度构建指纹
    device_model: Optional[str] = Field(None, description="设备型号")
    device_brand: Optional[str] = Field(None, description="设备品牌")
    device_manufacturer: Optional[str] = Field(None, description="设备制造商")
    device_product: Optional[str] = Field(None, description="产品代号")
    device_board: Optional[str] = Field(None, description="主板代号")
    device_hardware: Optional[str] = Field(None, description="底层硬件代号")
    os_version: Optional[str] = Field(None, description="操作系统版本")
    os_api_level: Optional[int] = Field(None, description="Android API 级别")
    cpu_abi: Optional[str] = Field(None, description="CPU 架构")
    build_fingerprint: Optional[str] = Field(None, description="系统完整指纹字符串")
    build_tags: Optional[str] = Field(None, description="构建标签(如 release-keys)")
    build_type: Optional[str] = Field(None, description="构建类型(如 user/userdebug)")
    uptime_ms: Optional[int] = Field(None, description="设备运行时间(毫秒)")

    # B. 真实内存探测
    total_memory_gb: Optional[float] = Field(None, description="物理总内存(GB)")
    avail_memory_gb: Optional[float] = Field(None, description="可用内存(GB)")
    is_low_memory: Optional[bool] = Field(None, description="是否处于低内存状态")

    # C. 物理屏幕深度参数
    screen_resolution_physical: Optional[str] = Field(None, description="物理屏幕分辨率")
    screen_density_dpi: Optional[int] = Field(None, description="屏幕像素密度(DPI)")
    screen_xdpi: Optional[float] = Field(None, description="X轴精确物理像素密度")
    screen_ydpi: Optional[float] = Field(None, description="Y轴精确物理像素密度")
    screen_scaled_density: Optional[float] = Field(None, description="字体缩放密度")

    # D. 电池动态物理量
    battery_level_pct: Optional[float] = Field(None, description="电池电量百分比")
    battery_temp_celsius: Optional[float] = Field(None, description="电池物理温度(摄氏度)")
    battery_voltage_mv: Optional[int] = Field(None, description="电池当前电压(毫伏)")
    is_charging: Optional[bool] = Field(None, description="是否正在充电")

    # E. 传感器全局矩阵
    sensor_total_count: Optional[int] = Field(None, description="系统传感器总数量")
    has_gyroscope: Optional[bool] = Field(None, description="是否有陀螺仪")
    has_accelerometer: Optional[bool] = Field(None, description="是否有加速度计")
    has_magnetic_field: Optional[bool] = Field(None, description="是否有地磁传感器")
    has_light_sensor: Optional[bool] = Field(None, description="是否有光线传感器")
    has_proximity_sensor: Optional[bool] = Field(None, description="是否有距离传感器")
    has_pressure_sensor: Optional[bool] = Field(None, description="是否有气压计")

    # F. 安全特征
    is_adb_enabled: Optional[bool] = Field(None, description="是否开启了USB调试")

class WebViewData(BaseModel):
    """WebView 容器与宿主环境特征 (满血版)"""
    # 基础通信特征
    jsbridge_injected: Optional[bool] = Field(None, description="是否注入 JSBridge")
    bridge_latency_ms: Optional[float] = Field(None, description="JSBridge通信延迟(毫秒)")
    
    # App 宿主安全特征
    is_debuggable: Optional[bool] = Field(None, description="App是否处于Debug模式")
    app_package_name: Optional[str] = Field(None, description="宿主App包名")
    installer_package: Optional[str] = Field(None, description="App安装渠道包名")
    
    # 内核真实溯源
    webview_provider_package: Optional[str] = Field(None, description="内核提供商包名")
    webview_provider_version: Optional[str] = Field(None, description="真实内核版本号")
    webview_provider_version_code: Optional[int] = Field(None, description="真实内核版本代码")
    
    # 容器安全配置
    is_multi_process: Optional[bool] = Field(None, description="是否开启多进程WebView")
    is_cleartext_traffic_permitted: Optional[bool] = Field(None, description="是否允许明文HTTP流量")
    
    # 宿主时间与编译特征
    first_install_time: Optional[int] = Field(None, description="宿主App首次安装时间戳")
    last_update_time: Optional[int] = Field(None, description="宿主App最后更新时间戳")
    target_sdk_version: Optional[int] = Field(None, description="编译目标SDK版本")
    min_sdk_version: Optional[int] = Field(None, description="最低支持SDK版本")
    
    # 底层网络探针
    system_http_agent: Optional[str] = Field(None, description="系统底层默认UA")
    error_msg: Optional[str] = Field(None, description="采集过程异常信息")

class WebData(BaseModel):
    """Web 数据模型 (火力加强版)"""
    user_agent: Optional[str] = Field(None, description="用户代理")
    screen_resolution_logical: Optional[str] = Field(None, description="逻辑屏幕分辨率")
    device_pixel_ratio: Optional[float] = Field(None, description="设备像素比")
    webgl_vendor: Optional[str] = Field(None, description="WebGL 供应商")
    webgl_renderer: Optional[str] = Field(None, description="WebGL 渲染器")
    canvas_hash: Optional[str] = Field(None, description="Canvas 指纹哈希")
    compute_task_time_ms: Optional[float] = Field(None, description="计算任务耗时(毫秒)")
    
    # 新增的高级特征接收字段
    color_depth: Optional[int] = Field(None, description="色彩深度")
    pixel_depth: Optional[int] = Field(None, description="像素深度")
    avail_width: Optional[int] = Field(None, description="可用屏幕宽度")
    avail_height: Optional[int] = Field(None, description="可用屏幕高度")
    hardware_concurrency: Optional[int] = Field(None, description="CPU逻辑核心数")
    device_memory: Optional[float] = Field(None, description="设备内存级别(GB)")
    max_touch_points: Optional[int] = Field(None, description="最大触控点数")
    language: Optional[str] = Field(None, description="语言")
    platform: Optional[str] = Field(None, description="平台标识")
    cookie_enabled: Optional[bool] = Field(None, description="是否启用Cookie")
    timezone_offset: Optional[int] = Field(None, description="时区偏移")
    timezone: Optional[str] = Field(None, description="时区名称")
    webgl_unmasked_vendor: Optional[str] = Field(None, description="底层显卡真实供应商")
    webgl_unmasked_renderer: Optional[str] = Field(None, description="底层显卡真实渲染器")
    webgl_extensions: Optional[list] = Field(None, description="WebGL扩展指令集数组")
    webgl_extensions_count: Optional[int] = Field(None, description="WebGL扩展指令集数量")
    local_storage_supported: Optional[bool] = Field(None, description="支持LocalStorage")
    session_storage_supported: Optional[bool] = Field(None, description="支持SessionStorage")
    indexed_db_supported: Optional[bool] = Field(None, description="支持IndexedDB")

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

        # 4. 将合并后的全量数据持久化保存到本地 JSON 文件
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions_db, f, ensure_ascii=False, indent=4)

        # 核心新增：只有当双端数据都“会师”完毕，才写入 jsonl 喂给大模型
        current_session = sessions_db[session_id]
        if current_session.get("android_native_data") and current_session.get("web_data"):
            save_to_jsonl(current_session)

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