import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic 模型定义
class AndroidNativeData(BaseModel):
    """Android 原生数据模型"""
    device_model: str = Field(..., description="设备型号")
    device_brand: str = Field(..., description="设备品牌")
    os_version: str = Field(..., description="操作系统版本")
    cpu_abi: str = Field(..., description="CPU 架构")
    total_memory_gb: float = Field(..., description="总内存(GB)")
    screen_resolution_physical: str = Field(..., description="物理屏幕分辨率")
    uptime_ms: int = Field(..., description="设备运行时间(毫秒)")


class WebViewData(BaseModel):
    """WebView 数据模型"""
    user_agent: str = Field(..., description="用户代理")
    screen_resolution_logical: str = Field(..., description="逻辑屏幕分辨率")
    device_pixel_ratio: float = Field(..., description="设备像素比")
    webgl_vendor: str = Field(..., description="WebGL 供应商")
    webgl_renderer: str = Field(..., description="WebGL 渲染器")
    canvas_hash: str = Field(..., description="Canvas 指纹哈希")
    compute_task_time_ms: float = Field(..., description="计算任务耗时(毫秒)")
    jsbridge_injected: bool = Field(..., description="是否注入 JSBridge")


class WebData(BaseModel):
    """Web 数据模型"""
    user_agent: str = Field(..., description="用户代理")
    screen_resolution_logical: str = Field(..., description="逻辑屏幕分辨率")
    device_pixel_ratio: float = Field(..., description="设备像素比")
    webgl_vendor: str = Field(..., description="WebGL 供应商")
    webgl_renderer: str = Field(..., description="WebGL 渲染器")
    canvas_hash: str = Field(..., description="Canvas 指纹哈希")
    compute_task_time_ms: float = Field(..., description="计算任务耗时(毫秒)")


class FingerprintPayload(BaseModel):
    """设备指纹数据载荷"""
    session_id: str = Field(..., description="会话ID")
    timestamp: int = Field(..., description="时间戳(Unix)")
    client_ip: str = Field(..., description="客户端IP地址")
    android_native_data: Optional[AndroidNativeData] = Field(None, description="Android 原生数据")
    webview_data: Optional[WebViewData] = Field(None, description="WebView 数据")
    web_data: Optional[WebData] = Field(None, description="Web 数据")


# 创建 FastAPI 应用
app = FastAPI(
    title="跨端设备指纹收集服务",
    description="用于收集和验证跨设备指纹数据",
    version="1.0.0"
)


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
        # 打印接收日志
        dt = datetime.fromtimestamp(payload.timestamp)
        logger.info(
            f"✅ 成功接收设备指纹数据 | Session ID: {payload.session_id} | "
            f"时间: {dt.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"客户端IP: {payload.client_ip}"
        )

        # 数据持久化到 JSONL 文件
        data_dict = payload.model_dump()
        with open("collected_data.jsonl", "a", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False)
            f.write("\n")

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