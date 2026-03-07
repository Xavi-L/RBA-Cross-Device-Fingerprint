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
    """Android 原生数据模型"""
    device_model: Optional[str] = Field(None, description="设备型号")
    device_brand: Optional[str] = Field(None, description="设备品牌")
    os_version: Optional[str] = Field(None, description="操作系统版本")
    cpu_abi: Optional[str] = Field(None, description="CPU 架构")
    total_memory_gb: Optional[float] = Field(None, description="总内存(GB)")
    screen_resolution_physical: Optional[str] = Field(None, description="物理屏幕分辨率")
    uptime_ms: Optional[int] = Field(None, description="设备运行时间(毫秒)")


class WebViewData(BaseModel):
    """WebView 数据模型"""
    user_agent: Optional[str] = Field(None, description="用户代理")
    screen_resolution_logical: Optional[str] = Field(None, description="逻辑屏幕分辨率")
    device_pixel_ratio: Optional[float] = Field(None, description="设备像素比")
    webgl_vendor: Optional[str] = Field(None, description="WebGL 供应商")
    webgl_renderer: Optional[str] = Field(None, description="WebGL 渲染器")
    canvas_hash: Optional[str] = Field(None, description="Canvas 指纹哈希")
    compute_task_time_ms: Optional[float] = Field(None, description="计算任务耗时(毫秒)")
    jsbridge_injected: Optional[bool] = Field(None, description="是否注入 JSBridge")


class WebData(BaseModel):
    """Web 数据模型"""
    user_agent: Optional[str] = Field(None, description="用户代理")
    screen_resolution_logical: Optional[str] = Field(None, description="逻辑屏幕分辨率")
    device_pixel_ratio: Optional[float] = Field(None, description="设备像素比")
    webgl_vendor: Optional[str] = Field(None, description="WebGL 供应商")
    webgl_renderer: Optional[str] = Field(None, description="WebGL 渲染器")
    canvas_hash: Optional[str] = Field(None, description="Canvas 指纹哈希")
    compute_task_time_ms: Optional[float] = Field(None, description="计算任务耗时(毫秒)")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)