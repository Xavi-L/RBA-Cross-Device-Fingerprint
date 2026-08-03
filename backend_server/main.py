import json
import logging
import hashlib
import base64
import hmac
from datetime import datetime
import os
from pathlib import Path
import secrets
import tempfile
import time
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit
import uuid
import copy

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FlexibleBaseModel(BaseModel):
    """Keep collector experiment fields even when the schema evolves."""

    class Config:
        extra = "allow"


def model_to_dict(model: BaseModel, **kwargs) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


# Pydantic 模型定义
# 👇 1. 先定义 Android 原生特征的 6 个子层级 Model
class BuildFingerprintLayer(FlexibleBaseModel):
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

class NativeMemoryLayer(FlexibleBaseModel):
    total_memory_gb: Optional[float] = None
    avail_memory_gb: Optional[float] = None
    is_low_memory: Optional[bool] = None

class NativeScreenLayer(FlexibleBaseModel):
    screen_resolution_physical: Optional[str] = None
    screen_density_dpi: Optional[int] = None
    screen_xdpi: Optional[float] = None
    screen_ydpi: Optional[float] = None
    screen_scaled_density: Optional[float] = None

class BatteryDynamicsLayer(FlexibleBaseModel):
    battery_level_pct: Optional[float] = None
    battery_temp_celsius: Optional[float] = None
    battery_voltage_mv: Optional[int] = None
    is_charging: Optional[bool] = None

class SensorMatrixLayer(FlexibleBaseModel):
    sensor_total_count: Optional[int] = None
    has_gyroscope: Optional[bool] = None
    has_accelerometer: Optional[bool] = None
    has_magnetic_field: Optional[bool] = None
    has_light_sensor: Optional[bool] = None
    has_proximity_sensor: Optional[bool] = None
    has_pressure_sensor: Optional[bool] = None

class SecurityConfigLayer(FlexibleBaseModel):
    is_adb_enabled: Optional[bool] = None

# 👇 2. 将它们组合进最终的原生模型中
class AndroidNativeData(FlexibleBaseModel):
    """Android 原生数据模型 (工业级分层版)"""
    build_fingerprint_layer: Optional[BuildFingerprintLayer] = Field(None, description="构建指纹层")
    memory_layer: Optional[NativeMemoryLayer] = Field(None, description="物理内存层")
    screen_display_layer: Optional[NativeScreenLayer] = Field(None, description="物理显示层")
    battery_dynamics_layer: Optional[BatteryDynamicsLayer] = Field(None, description="电池动态层")
    sensor_matrix_layer: Optional[SensorMatrixLayer] = Field(None, description="传感器矩阵层")
    security_config_layer: Optional[SecurityConfigLayer] = Field(None, description="安全配置层")

# 👇 1. 先定义 WebView 容器的子层级 Model
class BridgeRoutingLayer(FlexibleBaseModel):
    jsbridge_injected: Optional[bool] = None
    bridge_latency_ms: Optional[float] = None

class KernelContainerLayer(FlexibleBaseModel):
    webview_provider_package: Optional[str] = None
    webview_provider_version: Optional[str] = None
    webview_provider_version_code: Optional[int] = None
    system_http_agent: Optional[str] = None
    default_ua_native: Optional[str] = None

class HostSecurityLayer(FlexibleBaseModel):
    is_debuggable: Optional[bool] = None
    app_package_name: Optional[str] = None
    installer_package: Optional[str] = None
    is_cleartext_traffic_permitted: Optional[bool] = None

class TemporalBuildLayer(FlexibleBaseModel):
    first_install_time: Optional[int] = None
    last_update_time: Optional[int] = None
    target_sdk_version: Optional[int] = None
    min_sdk_version: Optional[int] = None

class ExceptionLayer(FlexibleBaseModel):
    error_msg: Optional[str] = None

# 👇 2. 将它们组合进最终的容器模型中
class WebViewData(FlexibleBaseModel):
    """WebView 容器与宿主环境特征 (工业级分层版)"""
    bridge_routing_layer: Optional[BridgeRoutingLayer] = Field(None, description="通信桥接层")
    kernel_container_layer: Optional[KernelContainerLayer] = Field(None, description="内核容器层")
    host_security_layer: Optional[HostSecurityLayer] = Field(None, description="宿主安全层")
    temporal_build_layer: Optional[TemporalBuildLayer] = Field(None, description="时间与编译层")
    exception_layer: Optional[ExceptionLayer] = Field(None, description="异常记录层")
    
# 👇 1. 先定义子层级的 Model
class NavigatorLayer(FlexibleBaseModel):
    user_agent: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    hardware_concurrency: Optional[int] = None
    device_memory: Optional[float] = None
    max_touch_points: Optional[int] = None

class ScreenLayer(FlexibleBaseModel):
    screen_resolution_logical: Optional[str] = None
    device_pixel_ratio: Optional[float] = None
    color_depth: Optional[int] = None
    pixel_depth: Optional[int] = None
    avail_width: Optional[int] = None
    avail_height: Optional[int] = None

class GraphicsLayer(FlexibleBaseModel):
    webgl_vendor: Optional[str] = None
    webgl_renderer: Optional[str] = None
    webgl_extensions_count: Optional[int] = None
    canvas_hash: Optional[str] = None

class ExecutionLayer(FlexibleBaseModel):
    compute_task_time_ms: Optional[float] = None
    timezone_offset: Optional[int] = None

# 👇 2. 再将它们组合进最终的 WebData 模型中
class WebData(FlexibleBaseModel):
    """Web 数据模型 (工业级分层版)"""
    navigator_layer: Optional[NavigatorLayer] = Field(None, description="导航器环境层")
    screen_layer: Optional[ScreenLayer] = Field(None, description="屏幕显示层")
    graphics_layer: Optional[GraphicsLayer] = Field(None, description="图形渲染层")
    execution_layer: Optional[ExecutionLayer] = Field(None, description="执行算力层")

class FingerprintPayload(FlexibleBaseModel):
    """设备指纹数据载荷"""
    session_id: str = Field(..., description="会话ID")
    timestamp: int = Field(..., description="时间戳(Unix)")
    browser_ticket_request_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=256,
        description="Stable App-generated key for delayed browser-pair receipt binding",
    )
    client_ip: Optional[str] = Field(None, description="客户端IP地址")
    android_native_data: Optional[AndroidNativeData] = Field(None, description="Android 原生数据")
    webview_data: Optional[WebViewData] = Field(None, description="WebView 数据")
    web_data: Optional[WebData] = Field(None, description="Web 数据")

class LocalRiskScorePayload(FlexibleBaseModel):
    """App 端本地评分结果载荷，不包含三端原始指纹数据"""
    session_id: str = Field(..., description="会话ID")
    timestamp: int = Field(..., description="App 端评分时间戳(Unix)")
    risk_score: float = Field(..., description="端侧随机森林风险评分")
    risk_level: Optional[str] = Field(None, description="端侧风险等级")
    risk_reason: Optional[str] = Field(None, description="端侧评分说明")
    scoring_engine: Optional[str] = Field(None, description="端侧评分器标识")
    feature_count: Optional[int] = Field(None, description="端侧输入特征数量")


class BrowserTicketRequest(FlexibleBaseModel):
    """Bind one explicitly selected available-browser launch to featureapp."""

    app_session_id: str = Field(..., min_length=1, max_length=256)
    app_receipt_id: Optional[str] = Field(None, min_length=1, max_length=256)
    ticket_request_id: str = Field(..., min_length=1, max_length=256)
    app_payload_sha256: Optional[str] = Field(None, min_length=64, max_length=64)
    resolved_browser_package: Optional[str] = Field(None, max_length=512)
    selected_browser_package: Optional[str] = Field(None, max_length=512)
    launch_resolution_status: str = Field(..., min_length=1, max_length=128)
    selected_browser_activity: Optional[str] = Field(None, max_length=1024)
    browser_candidate_packages: list[str] = Field(default_factory=list)
    browser_selection_policy_revision: Optional[str] = Field(
        None,
        max_length=128,
    )
    web_probe_revision: str = Field(..., min_length=1, max_length=128)
    browser_probe_base_url: str = Field(..., min_length=1, max_length=4096)


class BrowserFingerprintPayload(FlexibleBaseModel):
    """Available-browser copy of the app collector's 67 Web signals."""

    pair_id: Optional[str] = Field(None, max_length=256)
    browser_session_id: str = Field(..., min_length=1, max_length=256)
    timestamp: int = Field(..., description="浏览器采集时间戳(Unix)")
    collector_app: str = Field(..., min_length=1, max_length=128)
    schema_version: str = Field(..., min_length=1, max_length=128)
    web_probe_revision: Optional[str] = Field(None, max_length=128)
    web_data: dict[str, Any] = Field(default_factory=dict)
    collection_diagnostics: Optional[dict[str, Any]] = None
    collection_status: Optional[dict[str, Any]] = None
    field_statuses: Optional[dict[str, str]] = None
    probe_metadata: Optional[dict[str, Any]] = None


class BrowserStagePayload(FlexibleBaseModel):
    """Small, non-feature telemetry emitted while the static probe is running."""

    pair_id: str = Field(..., min_length=1, max_length=256)
    stage: str = Field(..., min_length=1, max_length=64)
    launch_attempt: int = Field(1, ge=1, le=2)
    client_stage_at_ms: Optional[int] = Field(None, ge=0)


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
expanded_sessions_db = {}

# 如果本地已有数据文件，启动时先加载进来（防止重启服务器丢数据）
# 所有采集数据固定写在 backend_server/ 下，避免从不同目录启动时散落到项目根目录。
BACKEND_DIR = Path(__file__).resolve().parent
DB_FILE = BACKEND_DIR / "merged_sessions.json"
EXPANDED_DB_FILE = BACKEND_DIR / "expanded_merged_sessions.json"
COLLECTED_JSONL_FILE = BACKEND_DIR / "collected_data.jsonl"
EXPANDED_COLLECTED_JSONL_FILE = BACKEND_DIR / "expanded_collected_data.jsonl"
COLLECTION_RECEIPTS_JSONL_FILE = BACKEND_DIR / "collection_receipts.jsonl"
RAW_EXPANDED_PAYLOADS_JSONL_FILE = BACKEND_DIR / "raw_expanded_payloads.jsonl"
COLLECTION_BATCHES_JSONL_FILE = BACKEND_DIR / "collection_batches.jsonl"
ACTIVE_COLLECTION_BATCH_STATE_FILE = BACKEND_DIR / "active_collection_batch.json"
LOCAL_SCORE_JSONL_FILE = BACKEND_DIR / "local_score_results.jsonl"
RAW_BROWSER_PAYLOADS_JSONL_FILE = BACKEND_DIR / "raw_browser_payloads.jsonl"
BROWSER_PROVISIONAL_PAYLOADS_JSONL_FILE = (
    BACKEND_DIR / "browser_provisional_payloads.jsonl"
)
BROWSER_COLLECTED_DATA_JSONL_FILE = BACKEND_DIR / "browser_collected_data.jsonl"
BROWSER_PAIR_EVENTS_JSONL_FILE = BACKEND_DIR / "browser_pair_events.jsonl"
BROWSER_PAIR_PROVENANCE_JSONL_FILE = BACKEND_DIR / "browser_pair_provenance.jsonl"
EXPECTED_EXPANDED_SIGNAL_COUNT = 177
EXPECTED_BROWSER_SIGNAL_COUNT = 67
COLLECTION_BATCH_SCHEMA_VERSION = "backend-collection-batch-v1"
COLLECTION_BATCH_STATE_SCHEMA_VERSION = "backend-collection-batch-state-v1"
COLLECTION_BATCH_ID_SOURCE = "backend_process_lifecycle"
STORAGE_CONCURRENCY_MODE = "single_process_json_files"
BROWSER_PAIR_SCHEMA_VERSION = "browser-pair-v1"
BROWSER_TOKEN_SCHEMA_VERSION = "browser-pair-token-v1"
BROWSER_PAYLOAD_SCHEMA_VERSION = "browser-web-v1-status"
BROWSER_COLLECTOR_APP = "browserprobe"
BROWSER_WEB_PROBE_REVISION = "expanded-web-67-v1"
BROWSER_WEB_PROBE_SHA256 = (
    "c9c2523e9f044396e7e307a9d569bcb8a0fb69904596c122f8691d918211b9fd"
)
BROWSER_PROBE_METADATA_SCHEMA_VERSION = "browser-probe-metadata-v1"
BROWSER_ALLOWED_PROBE_ORIGINS = frozenset(
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "HYBRIDGUARD_BROWSER_PROBE_ORIGINS",
        "https://xavi-l.github.io",
    ).split(",")
    if origin.strip()
)
BROWSER_TICKET_TTL_SECONDS = 10 * 60
BROWSER_POLL_TTL_SECONDS = 60 * 60
BROWSER_FIELD_STATUS_SCHEMA_VERSION = "browser-field-status-v1"
BROWSER_ALLOWED_FIELD_STATES = {
    "observed",
    "unsupported_by_os",
    "permission_denied",
    "runtime_error",
    "timeout",
    "not_applicable",
}
BROWSER_STAGE_ORDER = {
    "launch_attempted": 0,
    "page_loaded": 1,
    "adapter_started": 2,
    "collection_started": 3,
    "collection_finished": 4,
    "upload_started": 5,
    "upload_failed": 6,
}
BROWSER_EXPECTED_WEB_FIELDS = frozenset(
    {
        "web_data.audio_layer.audio_context_supported",
        "web_data.audio_layer.audio_error",
        "web_data.audio_layer.audio_hash",
        "web_data.audio_layer.audio_output_latency",
        "web_data.audio_layer.audio_sample_rate",
        "web_data.automation_surface_layer.mime_types_count",
        "web_data.automation_surface_layer.mime_types_hash",
        "web_data.automation_surface_layer.plugin_probe_error",
        "web_data.automation_surface_layer.plugins_count",
        "web_data.automation_surface_layer.plugins_hash",
        "web_data.automation_surface_layer.webdriver",
        "web_data.execution_layer.compute_task_time_ms",
        "web_data.execution_layer.local_storage_available",
        "web_data.execution_layer.performance_time_origin",
        "web_data.execution_layer.session_storage_available",
        "web_data.execution_layer.timezone_id",
        "web_data.execution_layer.timezone_offset",
        "web_data.font_layer.available_font_hash",
        "web_data.font_layer.font_probe_count",
        "web_data.font_layer.font_probe_error",
        "web_data.graphics_layer.canvas_hash",
        "web_data.graphics_layer.webgl_aliased_line_width_range",
        "web_data.graphics_layer.webgl_extensions_count",
        "web_data.graphics_layer.webgl_max_texture_size",
        "web_data.graphics_layer.webgl_max_viewport_dims",
        "web_data.graphics_layer.webgl_renderer",
        "web_data.graphics_layer.webgl_vendor",
        "web_data.graphics_layer.webgl2_supported",
        "web_data.navigator_layer.cookie_enabled",
        "web_data.navigator_layer.device_memory",
        "web_data.navigator_layer.do_not_track",
        "web_data.navigator_layer.hardware_concurrency",
        "web_data.navigator_layer.language",
        "web_data.navigator_layer.languages",
        "web_data.navigator_layer.max_touch_points",
        "web_data.navigator_layer.online",
        "web_data.navigator_layer.platform",
        "web_data.navigator_layer.product",
        "web_data.navigator_layer.product_sub",
        "web_data.navigator_layer.user_agent",
        "web_data.navigator_layer.vendor",
        "web_data.network_api_layer.downlink_mbps",
        "web_data.network_api_layer.effective_type",
        "web_data.network_api_layer.rtt_ms",
        "web_data.network_api_layer.save_data",
        "web_data.permissions_layer.camera_permission_state",
        "web_data.permissions_layer.clipboard_read_state",
        "web_data.permissions_layer.geolocation_permission_state",
        "web_data.permissions_layer.microphone_permission_state",
        "web_data.permissions_layer.notification_permission_state",
        "web_data.permissions_layer.permission_query_errors",
        "web_data.permissions_layer.permissions_api_supported",
        "web_data.screen_layer.avail_height",
        "web_data.screen_layer.avail_width",
        "web_data.screen_layer.color_depth",
        "web_data.screen_layer.device_pixel_ratio",
        "web_data.screen_layer.inner_height",
        "web_data.screen_layer.inner_width",
        "web_data.screen_layer.orientation_angle",
        "web_data.screen_layer.orientation_type",
        "web_data.screen_layer.outer_height",
        "web_data.screen_layer.outer_width",
        "web_data.screen_layer.pixel_depth",
        "web_data.screen_layer.screen_resolution_logical",
        "web_data.screen_layer.visual_viewport_height",
        "web_data.screen_layer.visual_viewport_scale",
        "web_data.screen_layer.visual_viewport_width",
    }
)
SUPPORTED_EXPANDED_SCHEMA_VERSIONS = {
    "expanded-v2",
    "expanded-v2.1-status",
    "expanded-v2.2-status",
}


def _browser_hmac_key() -> bytes:
    configured = os.environ.get("HYBRIDGUARD_BROWSER_TOKEN_HMAC_KEY", "")
    if configured:
        return configured.encode("utf-8")
    # Tickets are intentionally bound to one backend-process batch. An ephemeral
    # fallback therefore fails closed after restart; production may provide a key
    # through the environment when stable signature verification is preferred.
    return secrets.token_bytes(32)


BROWSER_TOKEN_HMAC_KEY = _browser_hmac_key()


def load_session_db(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def is_expanded_collector_payload(data: dict) -> bool:
    schema_version = str(data.get("schema_version", ""))
    return data.get("collector_app") == "featureapp" or schema_version.startswith("expanded-")


def canonical_payload_sha256(data: dict) -> str:
    encoded = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expanded_payload_warnings(data: dict) -> list[str]:
    """Return non-destructive validation warnings for an expanded collector upload.

    A paid cloud run must not lose a partial payload merely because one optional API or
    Web probe failed. The server stores it first, reports warnings in the receipt, and
    leaves formal schema eligibility to the offline snapshot pipeline.
    """
    warnings = []
    schema_version = str(data.get("schema_version", ""))
    if schema_version not in SUPPORTED_EXPANDED_SCHEMA_VERSIONS:
        warnings.append("W_SCHEMA_VERSION_UNRECOGNIZED")
    for layer in ("android_native_data", "webview_data", "web_data"):
        if not isinstance(data.get(layer), dict) or not data[layer]:
            warnings.append(f"W_LAYER_EMPTY:{layer}")

    manifest = data.get("collection_manifest")
    if not isinstance(manifest, dict):
        warnings.append("W_COLLECTION_MANIFEST_MISSING")
    else:
        if manifest.get("schema_version") != schema_version:
            warnings.append("W_MANIFEST_SCHEMA_MISMATCH")
        if not manifest.get("device_manifest_id"):
            warnings.append("W_DEVICE_MANIFEST_ID_MISSING")

    status = data.get("collection_status")
    if not isinstance(status, dict):
        warnings.append("W_COLLECTION_STATUS_MISSING")
    else:
        counts = status.get("counts")
        field_states = status.get("fields")
        fixed_count = status.get("fixed_signal_count")
        status_names = (
            "observed",
            "unsupported_by_os",
            "permission_denied",
            "runtime_error",
            "timeout",
            "not_applicable",
        )
        if fixed_count != EXPECTED_EXPANDED_SIGNAL_COUNT or not isinstance(counts, dict):
            warnings.append("W_COLLECTION_STATUS_INVALID")
        elif any(not isinstance(counts.get(name), int) for name in status_names):
            warnings.append("W_COLLECTION_STATUS_INVALID")
        elif sum(counts[name] for name in status_names) != EXPECTED_EXPANDED_SIGNAL_COUNT:
            warnings.append("W_COLLECTION_STATUS_INVALID")
        elif (
            not isinstance(field_states, dict)
            or len(field_states) != EXPECTED_EXPANDED_SIGNAL_COUNT
            or any(value not in status_names for value in field_states.values())
            or any(sum(value == name for value in field_states.values()) != counts[name] for name in status_names)
        ):
            warnings.append("W_COLLECTION_STATUS_INVALID")
        elif any(counts[name] > 0 for name in ("runtime_error", "timeout", "permission_denied")):
            warnings.append("W_COLLECTION_PARTIAL")
    return warnings


sessions_db = load_session_db(DB_FILE)
expanded_sessions_db = load_session_db(EXPANDED_DB_FILE)


class CollectionBatchError(RuntimeError):
    """Raised when a request cannot be attached to one server-lifecycle batch."""


# This stays process-local by design. The durable audit trail is the append-only
# ledger plus the active-state marker below; do not create a batch at import time.
active_collection_batch: Optional[dict] = None

# Browser tickets cannot outlive their server-lifecycle collection batch. The
# append-only files below are the durable audit artifacts; these maps only provide
# atomic/idempotent behavior while the single backend worker is running.
browser_pairs_db: dict[str, dict[str, Any]] = {}
browser_ticket_requests_db: dict[str, str] = {}


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


def append_jsonl_durably(record: dict, path: Path) -> None:
    """Append a small lifecycle record and flush it before serving requests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_json_atomically(record: dict, path: Path) -> None:
    """Replace the active-batch marker without exposing a partial JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        json.dump(record, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary_path.replace(path)


def read_jsonl_records(path: Path, description: str) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise CollectionBatchError(
                        f"Invalid JSON in {description} at {path}:{line_number}"
                    ) from error
                if not isinstance(record, dict):
                    raise CollectionBatchError(
                        f"Expected an object in {description} at {path}:{line_number}"
                    )
                records.append(record)
    except OSError as error:
        raise CollectionBatchError(f"Cannot read {description}: {path}") from error
    return records


def read_active_collection_batch_state() -> Optional[dict]:
    if not ACTIVE_COLLECTION_BATCH_STATE_FILE.exists():
        return None
    try:
        with ACTIVE_COLLECTION_BATCH_STATE_FILE.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise CollectionBatchError(
            f"Cannot read active collection batch state: {ACTIVE_COLLECTION_BATCH_STATE_FILE}"
        ) from error
    if not isinstance(state, dict) or not state.get("collection_batch_id"):
        raise CollectionBatchError(
            f"Invalid active collection batch state: {ACTIVE_COLLECTION_BATCH_STATE_FILE}"
        )
    return state


def clear_active_collection_batch_state() -> None:
    try:
        ACTIVE_COLLECTION_BATCH_STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def process_is_running(process_id: object) -> bool:
    """Best-effort guard against two backend processes using one JSONL directory."""
    if not isinstance(process_id, int) or process_id <= 0:
        return False
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def collection_batch_receipt_summary(collection_batch_id: str) -> dict:
    summary = {
        "receipt_count": 0,
        "stored_new_jsonl_row_count": 0,
        "duplicate_payload_count": 0,
        "last_receipt_at": None,
        "last_stored_receipt_at": None,
    }
    for receipt in read_jsonl_records(COLLECTION_RECEIPTS_JSONL_FILE, "collection receipts"):
        if receipt.get("collection_batch_id") != collection_batch_id:
            continue
        summary["receipt_count"] += 1
        received_at = receipt.get("server_received_at")
        if isinstance(received_at, str) and (
            summary["last_receipt_at"] is None or received_at > summary["last_receipt_at"]
        ):
            summary["last_receipt_at"] = received_at
        if receipt.get("stored_new_jsonl_row") is True:
            summary["stored_new_jsonl_row_count"] += 1
            if isinstance(received_at, str) and (
                summary["last_stored_receipt_at"] is None
                or received_at > summary["last_stored_receipt_at"]
            ):
                summary["last_stored_receipt_at"] = received_at
        if receipt.get("duplicate_payload") is True:
            summary["duplicate_payload_count"] += 1
    return summary


def open_collection_batch_starts() -> dict[str, dict]:
    starts: dict[str, dict] = {}
    closed_ids: set[str] = set()
    for event in read_jsonl_records(COLLECTION_BATCHES_JSONL_FILE, "collection batch ledger"):
        if event.get("collection_batch_schema_version") != COLLECTION_BATCH_SCHEMA_VERSION:
            continue
        batch_id = event.get("collection_batch_id")
        event_name = event.get("event")
        if not isinstance(batch_id, str) or not batch_id:
            raise CollectionBatchError("Collection batch ledger contains an event without collection_batch_id")
        if event_name == "started":
            if batch_id in starts:
                raise CollectionBatchError(
                    f"Collection batch ledger contains duplicate start events for {batch_id}"
                )
            starts[batch_id] = event
        elif event_name == "closed":
            if batch_id not in starts:
                raise CollectionBatchError(
                    f"Collection batch ledger closes unknown batch {batch_id}"
                )
            closed_ids.add(batch_id)
    return {
        batch_id: event
        for batch_id, event in starts.items()
        if batch_id not in closed_ids
    }


def recover_unclosed_collection_batches() -> None:
    """Close a previous process's open batch using only observable receipt time.

    A SIGKILL or host crash cannot provide a true shutdown timestamp. The next
    process therefore records the last server receipt as an upper-bound evidence
    point and labels the lifecycle as recovered rather than cleanly closed.
    """
    open_batches = open_collection_batch_starts()
    active_state = read_active_collection_batch_state()
    if active_state is not None:
        state_batch_id = active_state["collection_batch_id"]
        if state_batch_id in open_batches and process_is_running(
            active_state.get("backend_process_id")
        ):
            raise CollectionBatchError(
                f"Collection batch {state_batch_id} is still owned by backend process "
                f"{active_state.get('backend_process_id')}; do not start a second backend "
                "against the same JSON/JSONL directory."
            )
        open_batches.setdefault(state_batch_id, active_state)

    for batch_id, started_event in open_batches.items():
        summary = collection_batch_receipt_summary(batch_id)
        last_receipt_at = summary["last_receipt_at"]
        recovery_event = {
            "collection_batch_schema_version": COLLECTION_BATCH_SCHEMA_VERSION,
            "event": "closed",
            "collection_batch_id": batch_id,
            "started_at": started_event.get("started_at"),
            "ended_at": last_receipt_at,
            "ended_at_source": (
                "last_receipt_at" if last_receipt_at is not None else "not_observed"
            ),
            "recovery_detected_at": utc_now_iso(),
            "recovery_detection_source": "next_backend_start",
            "lifecycle_status": "unclean_shutdown_recovered",
            "boundary_rule": COLLECTION_BATCH_ID_SOURCE,
            **summary,
        }
        append_jsonl_durably(recovery_event, COLLECTION_BATCHES_JSONL_FILE)
        logger.warning(
            "Recovered unclean collection batch %s; last observable receipt=%s",
            batch_id,
            last_receipt_at,
        )
    if active_state is not None:
        clear_active_collection_batch_state()


def start_collection_batch() -> dict:
    """Create exactly one batch for the current ASGI server process lifecycle."""
    global active_collection_batch
    if active_collection_batch is not None:
        raise CollectionBatchError(
            f"Collection batch is already active: {active_collection_batch['collection_batch_id']}"
        )

    recover_unclosed_collection_batches()
    started_at = utc_now_iso()
    collection_batch_id = (
        f"hgbatch-v1-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}-"
        f"{uuid.uuid4().hex[:10]}"
    )
    started_event = {
        "collection_batch_schema_version": COLLECTION_BATCH_SCHEMA_VERSION,
        "event": "started",
        "collection_batch_id": collection_batch_id,
        "started_at": started_at,
        "lifecycle_status": "open",
        "boundary_rule": COLLECTION_BATCH_ID_SOURCE,
        "storage_concurrency_mode": STORAGE_CONCURRENCY_MODE,
        "backend_process_id": os.getpid(),
    }
    append_jsonl_durably(started_event, COLLECTION_BATCHES_JSONL_FILE)
    write_json_atomically(
        {
            "collection_batch_state_schema_version": COLLECTION_BATCH_STATE_SCHEMA_VERSION,
            "collection_batch_id": collection_batch_id,
            "started_at": started_at,
            "backend_process_id": os.getpid(),
        },
        ACTIVE_COLLECTION_BATCH_STATE_FILE,
    )
    active_collection_batch = started_event
    logger.info("Started collection batch %s", collection_batch_id)
    return dict(started_event)


def get_active_collection_batch() -> dict:
    if active_collection_batch is None:
        raise CollectionBatchError(
            "No active collection batch. Start the FastAPI server lifecycle before accepting uploads."
        )
    return dict(active_collection_batch)


def close_active_collection_batch() -> Optional[dict]:
    """Record a graceful lifecycle end after uvicorn stops accepting requests."""
    global active_collection_batch
    if active_collection_batch is None:
        return None
    active_batch = active_collection_batch
    summary = collection_batch_receipt_summary(active_batch["collection_batch_id"])
    closed_event = {
        "collection_batch_schema_version": COLLECTION_BATCH_SCHEMA_VERSION,
        "event": "closed",
        "collection_batch_id": active_batch["collection_batch_id"],
        "started_at": active_batch["started_at"],
        "ended_at": utc_now_iso(),
        "ended_at_source": "graceful_shutdown_hook",
        "lifecycle_status": "closed_cleanly",
        "boundary_rule": COLLECTION_BATCH_ID_SOURCE,
        "storage_concurrency_mode": STORAGE_CONCURRENCY_MODE,
        **summary,
    }
    append_jsonl_durably(closed_event, COLLECTION_BATCHES_JSONL_FILE)
    clear_active_collection_batch_state()
    active_collection_batch = None
    logger.info("Closed collection batch %s", closed_event["collection_batch_id"])
    return closed_event


def browser_token_now() -> int:
    return int(time.time())


def unix_time_to_utc_iso(timestamp: int) -> str:
    return datetime.utcfromtimestamp(timestamp).isoformat(timespec="seconds") + "Z"


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def browser_protocol_error(status_code: int, code: str, message: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers,
    )


def sign_browser_token(claims: dict[str, Any]) -> str:
    payload = json.dumps(
        claims,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = _base64url_encode(payload)
    signature = hmac.new(
        BROWSER_TOKEN_HMAC_KEY,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"hg1.{encoded_payload}.{_base64url_encode(signature)}"


def decode_browser_token(token: str) -> dict[str, Any]:
    try:
        prefix, encoded_payload, encoded_signature = token.split(".", 2)
        if prefix != "hg1":
            raise ValueError("unsupported token prefix")
        supplied_signature = _base64url_decode(encoded_signature)
        expected_signature = hmac.new(
            BROWSER_TOKEN_HMAC_KEY,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("signature mismatch")
        claims = json.loads(_base64url_decode(encoded_payload))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise browser_protocol_error(
            401,
            "BROWSER_TOKEN_INVALID",
            "Browser pairing token is malformed or has an invalid signature.",
        ) from error
    if not isinstance(claims, dict) or claims.get("token_schema_version") != BROWSER_TOKEN_SCHEMA_VERSION:
        raise browser_protocol_error(
            401,
            "BROWSER_TOKEN_INVALID",
            "Browser pairing token has an unsupported schema.",
        )
    return claims


def require_bearer_token(authorization: Optional[str]) -> str:
    if not isinstance(authorization, str):
        raise browser_protocol_error(
            401,
            "BROWSER_TOKEN_MISSING",
            "Authorization: Bearer <token> is required.",
        )
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise browser_protocol_error(
            401,
            "BROWSER_TOKEN_MISSING",
            "Authorization: Bearer <token> is required.",
        )
    return token.strip()


def append_browser_pair_event(
    event: str,
    pair: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    record = {
        "browser_pair_event_schema_version": "browser-pair-event-v1",
        "event": event,
        "event_at": utc_now_iso(),
        "pair_id": pair["pair_id"],
        "pair_status": pair["pair_status"],
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "ticket_request_id": pair["ticket_request_id"],
        "collection_batch_id": pair["collection_batch_id"],
        "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
        "app_session_id": pair["app_session_id"],
        "app_receipt_id": pair.get("app_receipt_id"),
        **extra,
    }
    append_jsonl_durably(record, BROWSER_PAIR_EVENTS_JSONL_FILE)
    return record


def validate_browser_probe_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError as error:
        raise browser_protocol_error(
            422,
            "BROWSER_PROBE_URL_INVALID",
            "browser_probe_base_url is not a valid URL.",
        ) from error
    is_local_http = (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    )
    if (
        (parsed.scheme != "https" and not is_local_http)
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise browser_protocol_error(
            422,
            "BROWSER_PROBE_URL_INVALID",
            "browser_probe_base_url must be HTTPS (or localhost HTTP) without user info.",
        )
    if parsed.fragment:
        raise browser_protocol_error(
            422,
            "BROWSER_PROBE_URL_INVALID",
            "browser_probe_base_url must not contain a fragment; pairing owns the fragment.",
        )
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if not is_local_http and origin not in BROWSER_ALLOWED_PROBE_ORIGINS:
        raise browser_protocol_error(
            422,
            "BROWSER_PROBE_ORIGIN_NOT_ALLOWED",
            "browser_probe_base_url origin is not in HYBRIDGUARD_BROWSER_PROBE_ORIGINS.",
        )
    return value.strip()


def build_browser_probe_url(
    browser_probe_base_url: str,
    pair_id: str,
    browser_ticket: str,
    browser_upload_url: str,
    browser_stage_url: str,
) -> str:
    """Put secrets in the fragment so they never reach static-host access logs."""
    parsed = urlsplit(validate_browser_probe_base_url(browser_probe_base_url))
    fragment_items = [
        ("pair_id", pair_id),
        ("browser_ticket", browser_ticket),
        ("browser_upload_url", browser_upload_url),
        ("browser_stage_url", browser_stage_url),
        ("launch_attempt", "1"),
    ]
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.query,
            urlencode(fragment_items),
        )
    )


def find_collection_receipt(receipt_id: str) -> Optional[dict[str, Any]]:
    matches = [
        record
        for record in read_jsonl_records(
            COLLECTION_RECEIPTS_JSONL_FILE,
            "collection receipts",
        )
        if record.get("receipt_id") == receipt_id
    ]
    if not matches:
        return None
    first_identity = (
        matches[0].get("session_id"),
        matches[0].get("payload_sha256"),
        matches[0].get("collection_batch_id"),
    )
    if any(
        (
            record.get("session_id"),
            record.get("payload_sha256"),
            record.get("collection_batch_id"),
        )
        != first_identity
        for record in matches[1:]
    ):
        raise CollectionBatchError(
            f"Collection receipt_id collision has conflicting identities: {receipt_id}"
        )
    return matches[-1]


def find_collection_receipt_by_ticket_request_id(
    ticket_request_id: str,
    app_session_id: str,
    collection_batch_id: str,
) -> Optional[dict[str, Any]]:
    """Find the first durable App receipt carrying one exact delayed-binding key."""
    matches = [
        record
        for record in read_jsonl_records(
            COLLECTION_RECEIPTS_JSONL_FILE,
            "collection receipts",
        )
        if record.get("browser_ticket_request_id") == ticket_request_id
        and record.get("collection_batch_id") == collection_batch_id
    ]
    if not matches:
        return None
    first_identity = (
        matches[0].get("session_id"),
        matches[0].get("payload_sha256"),
        matches[0].get("collection_batch_id"),
    )
    if any(
        (
            record.get("session_id"),
            record.get("payload_sha256"),
            record.get("collection_batch_id"),
        )
        != first_identity
        for record in matches[1:]
    ):
        raise CollectionBatchError(
            "browser_ticket_request_id has conflicting App receipt identities: "
            f"{ticket_request_id}"
        )
    if matches[0].get("session_id") != app_session_id:
        raise CollectionBatchError(
            "browser_ticket_request_id belongs to a different App session: "
            f"{ticket_request_id}"
        )
    return next(
        (
            record
            for record in matches
            if record.get("stored_new_jsonl_row") is True
        ),
        matches[0],
    )


def make_browser_token_claims(
    pair: dict[str, Any],
    token_use: str,
    token_jti: str,
    expires_at_unix: int,
) -> dict[str, Any]:
    return {
        "token_schema_version": BROWSER_TOKEN_SCHEMA_VERSION,
        "token_use": token_use,
        "pair_id": pair["pair_id"],
        "collection_batch_id": pair["collection_batch_id"],
        "app_session_id": pair["app_session_id"],
        "ticket_request_id": pair["ticket_request_id"],
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "app_receipt_id": pair.get("app_receipt_id"),
        "jti": token_jti,
        "iat": pair["issued_at_unix"],
        "exp": expires_at_unix,
    }


def current_browser_pair_status(pair: dict[str, Any], now: Optional[int] = None) -> str:
    pending_statuses = {
        "awaiting_app_and_browser",
        "awaiting_app",
        "awaiting_browser",
    }
    if pair["pair_status"] not in pending_statuses:
        return pair["pair_status"]
    effective_now = browser_token_now() if now is None else now
    expires_at_unix = (
        pair["poll_expires_at_unix"]
        if pair["pair_status"] == "awaiting_app"
        else pair["ticket_expires_at_unix"]
    )
    if effective_now <= expires_at_unix:
        return pair["pair_status"]
    pair["pair_status"] = "expired"
    if not pair.get("expiry_event_recorded"):
        pair["expiry_event_recorded"] = True
        append_browser_pair_event(
            "browser_ticket_expired",
            pair,
            ticket_expires_at=pair["ticket_expires_at"],
            poll_expires_at=pair["poll_expires_at"],
            expiry_reason=(
                "app_receipt_not_bound_before_poll_expiry"
                if pair.get("browser_payload_sha256")
                and pair.get("app_receipt_id") is None
                else "browser_payload_not_received_before_ticket_expiry"
            ),
        )
    return pair["pair_status"]


def browser_ticket_response(
    pair: dict[str, Any],
    duplicate_ticket_request: bool,
) -> dict[str, Any]:
    return {
        "status": "issued",
        "browser_pair_schema_version": BROWSER_PAIR_SCHEMA_VERSION,
        "pair_status": current_browser_pair_status(pair),
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "pair_id": pair["pair_id"],
        "browser_ticket": pair["browser_ticket"],
        "poll_token": pair["poll_token"],
        "probe_url": pair["probe_url"],
        "browser_upload_url": pair["browser_upload_url"],
        "browser_stage_url": pair["browser_stage_url"],
        "issued_at": pair["issued_at"],
        "expires_at": pair["ticket_expires_at"],
        "ticket_expires_at": pair["ticket_expires_at"],
        "poll_expires_at": pair["poll_expires_at"],
        "collection_batch_id": pair["collection_batch_id"],
        "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
        "app_session_id": pair["app_session_id"],
        "app_receipt_id": pair.get("app_receipt_id"),
        "app_payload_sha256": pair.get("app_payload_sha256"),
        "ticket_request_id": pair["ticket_request_id"],
        "web_probe_revision": pair["web_probe_revision"],
        "duplicate_ticket_request": duplicate_ticket_request,
    }


def issue_browser_ticket_for_upload_url(
    payload: BrowserTicketRequest,
    browser_upload_url: str,
    browser_stage_url: Optional[str] = None,
) -> dict[str, Any]:
    if browser_stage_url is None:
        parsed_upload_url = urlsplit(browser_upload_url)
        upload_parent = parsed_upload_url.path.rsplit("/", 1)[0]
        browser_stage_url = urlunsplit(
            (
                parsed_upload_url.scheme,
                parsed_upload_url.netloc,
                f"{upload_parent}/browser-stage",
                "",
                "",
            )
        )
    has_receipt_id = payload.app_receipt_id is not None
    has_payload_hash = payload.app_payload_sha256 is not None
    if has_receipt_id != has_payload_hash:
        raise browser_protocol_error(
            422,
            "APP_RECEIPT_BINDING_INCOMPLETE",
            "app_receipt_id and app_payload_sha256 must either both be present or both be absent.",
        )

    ticket_binding_mode = (
        "receipt_bound" if has_receipt_id else "provisional_session"
    )
    try:
        active_batch = get_active_collection_batch()
        if has_receipt_id:
            receipt = find_collection_receipt(str(payload.app_receipt_id))
        else:
            receipt = find_collection_receipt_by_ticket_request_id(
                payload.ticket_request_id,
                payload.app_session_id,
                active_batch["collection_batch_id"],
            )
    except CollectionBatchError as error:
        raise browser_protocol_error(503, "COLLECTION_BATCH_UNAVAILABLE", str(error)) from error
    if has_receipt_id and receipt is None:
        raise browser_protocol_error(
            404,
            "APP_RECEIPT_NOT_FOUND",
            "The referenced app collection receipt does not exist.",
        )
    app_payload_sha256: Optional[str] = None
    if receipt is not None:
        if receipt.get("session_id") != payload.app_session_id:
            raise browser_protocol_error(
                409,
                "APP_RECEIPT_SESSION_MISMATCH",
                "app_session_id does not match the referenced receipt.",
            )
        if receipt.get("collection_batch_id") != active_batch["collection_batch_id"]:
            raise browser_protocol_error(
                409,
                "APP_RECEIPT_BATCH_MISMATCH",
                "The referenced app receipt belongs to a different collection batch.",
            )
        if (
            receipt.get("collector_app") != "featureapp"
            or receipt.get("schema_version") not in SUPPORTED_EXPANDED_SCHEMA_VERSIONS
        ):
            raise browser_protocol_error(
                409,
                "APP_RECEIPT_NOT_EXPANDED",
                "Browser pairing requires an accepted featureapp expanded receipt.",
            )
        app_payload_sha256 = receipt.get("payload_sha256")
        if not isinstance(app_payload_sha256, str) or len(app_payload_sha256) != 64:
            raise browser_protocol_error(
                409,
                "APP_RECEIPT_HASH_MISSING",
                "The referenced app receipt has no canonical payload hash.",
            )
        if has_payload_hash:
            supplied_hash = str(payload.app_payload_sha256).lower()
            if any(character not in "0123456789abcdef" for character in supplied_hash):
                raise browser_protocol_error(
                    422,
                    "APP_PAYLOAD_HASH_INVALID",
                    "app_payload_sha256 must be a lowercase or uppercase SHA-256 hex digest.",
                )
            if not hmac.compare_digest(supplied_hash, app_payload_sha256.lower()):
                raise browser_protocol_error(
                    409,
                    "APP_PAYLOAD_HASH_MISMATCH",
                    "app_payload_sha256 does not match the referenced receipt.",
                )
        if (
            ticket_binding_mode == "provisional_session"
            and receipt.get("browser_ticket_request_id") != payload.ticket_request_id
        ):
            raise browser_protocol_error(
                409,
                "APP_RECEIPT_TICKET_REQUEST_MISMATCH",
                "The durable App receipt does not carry this ticket_request_id.",
            )
    if payload.web_probe_revision != BROWSER_WEB_PROBE_REVISION:
        raise browser_protocol_error(
            422,
            "WEB_PROBE_REVISION_UNSUPPORTED",
            f"web_probe_revision must be {BROWSER_WEB_PROBE_REVISION}.",
        )
    browser_probe_base_url = validate_browser_probe_base_url(payload.browser_probe_base_url)
    request_data = model_to_dict(payload, exclude_none=True)
    request_data["browser_probe_base_url"] = browser_probe_base_url
    request_sha256 = canonical_payload_sha256(request_data)
    request_key = f"{active_batch['collection_batch_id']}:{payload.ticket_request_id}"
    existing_pair_id = browser_ticket_requests_db.get(request_key)
    if existing_pair_id is not None:
        pair = browser_pairs_db[existing_pair_id]
        if pair["ticket_request_sha256"] != request_sha256:
            append_browser_pair_event(
                "ticket_request_replay_conflict",
                pair,
                presented_ticket_request_sha256=request_sha256,
                expected_ticket_request_sha256=pair["ticket_request_sha256"],
            )
            raise browser_protocol_error(
                409,
                "TICKET_REQUEST_REPLAY_CONFLICT",
                "ticket_request_id was already used with different request content.",
            )
        append_browser_pair_event(
            "ticket_request_idempotent_replay",
            pair,
            ticket_request_sha256=request_sha256,
        )
        return browser_ticket_response(pair, duplicate_ticket_request=True)

    now = browser_token_now()
    ticket_expires_at_unix = now + BROWSER_TICKET_TTL_SECONDS
    poll_expires_at_unix = now + BROWSER_POLL_TTL_SECONDS
    pair_digest = hmac.new(
        BROWSER_TOKEN_HMAC_KEY,
        (
            f"pair:{active_batch['collection_batch_id']}:"
            f"{payload.app_session_id}:{payload.ticket_request_id}"
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]
    pair_id = f"hgpair-v1-{pair_digest}"
    pair: dict[str, Any] = {
        "browser_pair_schema_version": BROWSER_PAIR_SCHEMA_VERSION,
        "pair_id": pair_id,
        "pair_status": (
            "awaiting_browser"
            if receipt is not None
            else "awaiting_app_and_browser"
        ),
        "ticket_binding_mode": ticket_binding_mode,
        "collection_batch_id": active_batch["collection_batch_id"],
        "collection_batch_started_at": active_batch["started_at"],
        "app_session_id": payload.app_session_id,
        "app_receipt_id": receipt.get("receipt_id") if receipt is not None else None,
        "app_payload_sha256": app_payload_sha256,
        "app_receipt_server_received_at": (
            receipt.get("server_received_at") if receipt is not None else None
        ),
        "ticket_request_id": payload.ticket_request_id,
        "ticket_request_sha256": request_sha256,
        "resolved_browser_package": payload.resolved_browser_package,
        "selected_browser_package": (
            payload.selected_browser_package or payload.resolved_browser_package
        ),
        "launch_resolution_status": payload.launch_resolution_status,
        "selected_browser_activity": payload.selected_browser_activity,
        "browser_candidate_packages": payload.browser_candidate_packages,
        "browser_selection_policy_revision": (
            payload.browser_selection_policy_revision
        ),
        "web_probe_revision": payload.web_probe_revision,
        "browser_probe_base_url": browser_probe_base_url,
        "browser_upload_url": browser_upload_url,
        "browser_stage_url": browser_stage_url,
        "issued_at_unix": now,
        "issued_at": unix_time_to_utc_iso(now),
        "ticket_expires_at_unix": ticket_expires_at_unix,
        "ticket_expires_at": unix_time_to_utc_iso(ticket_expires_at_unix),
        "poll_expires_at_unix": poll_expires_at_unix,
        "poll_expires_at": unix_time_to_utc_iso(poll_expires_at_unix),
        "browser_ticket_jti": secrets.token_urlsafe(18),
        "poll_token_jti": secrets.token_urlsafe(18),
    }
    pair["browser_ticket"] = sign_browser_token(
        make_browser_token_claims(
            pair,
            "browser_upload",
            pair["browser_ticket_jti"],
            ticket_expires_at_unix,
        )
    )
    pair["poll_token"] = sign_browser_token(
        make_browser_token_claims(
            pair,
            "pair_poll",
            pair["poll_token_jti"],
            poll_expires_at_unix,
        )
    )
    pair["probe_url"] = build_browser_probe_url(
        browser_probe_base_url,
        pair_id,
        pair["browser_ticket"],
        browser_upload_url,
        browser_stage_url,
    )
    browser_pairs_db[pair_id] = pair
    browser_ticket_requests_db[request_key] = pair_id
    append_browser_pair_event(
        (
            "ticket_issued"
            if ticket_binding_mode == "receipt_bound"
            else "provisional_ticket_issued"
        ),
        pair,
        ticket_request_id=pair["ticket_request_id"],
        ticket_request_sha256=pair["ticket_request_sha256"],
        ticket_expires_at=pair["ticket_expires_at"],
        poll_expires_at=pair["poll_expires_at"],
        resolved_browser_package=pair["resolved_browser_package"],
        selected_browser_package=pair["selected_browser_package"],
        launch_resolution_status=pair["launch_resolution_status"],
        selected_browser_activity=pair["selected_browser_activity"],
        browser_candidate_packages=pair["browser_candidate_packages"],
        browser_selection_policy_revision=(
            pair["browser_selection_policy_revision"]
        ),
        web_probe_revision=pair["web_probe_revision"],
        browser_probe_base_url=pair["browser_probe_base_url"],
        browser_upload_url=pair["browser_upload_url"],
        browser_stage_url=pair["browser_stage_url"],
    )
    return browser_ticket_response(pair, duplicate_ticket_request=False)


def authorize_browser_pair(
    token: str,
    expected_token_use: str,
    expected_pair_id: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    claims = decode_browser_token(token)
    if claims.get("token_use") != expected_token_use:
        raise browser_protocol_error(
            403,
            "BROWSER_TOKEN_WRONG_USE",
            "This token cannot be used for the requested browser-pair operation.",
        )
    try:
        active_batch = get_active_collection_batch()
    except CollectionBatchError as error:
        raise browser_protocol_error(503, "COLLECTION_BATCH_UNAVAILABLE", str(error)) from error
    if claims.get("collection_batch_id") != active_batch["collection_batch_id"]:
        raise browser_protocol_error(
            409,
            "BROWSER_TOKEN_BATCH_MISMATCH",
            "The browser pairing token belongs to a different collection batch.",
        )
    pair_id = claims.get("pair_id")
    if expected_pair_id is not None and pair_id != expected_pair_id:
        raise browser_protocol_error(
            403,
            "BROWSER_TOKEN_PAIR_MISMATCH",
            "The bearer token is not authorized for this pair_id.",
        )
    pair = browser_pairs_db.get(str(pair_id))
    if pair is None:
        raise browser_protocol_error(
            404,
            "BROWSER_PAIR_NOT_FOUND",
            "The browser pair is not active in this backend process.",
        )
    expected_jti_key = (
        "browser_ticket_jti" if expected_token_use == "browser_upload" else "poll_token_jti"
    )
    common_binding_mismatch = (
        claims.get("jti") != pair.get(expected_jti_key)
        or claims.get("app_session_id") != pair["app_session_id"]
        or claims.get("ticket_request_id") != pair["ticket_request_id"]
        or claims.get("ticket_binding_mode") != pair["ticket_binding_mode"]
        or claims.get("collection_batch_id") != pair["collection_batch_id"]
    )
    receipt_binding_mismatch = (
        pair["ticket_binding_mode"] == "receipt_bound"
        and claims.get("app_receipt_id") != pair.get("app_receipt_id")
    )
    if common_binding_mismatch or receipt_binding_mismatch:
        raise browser_protocol_error(
            403,
            "BROWSER_TOKEN_BINDING_MISMATCH",
            "Browser pairing token claims do not match the server-side pair.",
        )
    now = browser_token_now()
    expires_at = claims.get("exp")
    if not isinstance(expires_at, int) or now > expires_at:
        if expected_token_use == "browser_upload":
            current_browser_pair_status(pair, now)
        raise browser_protocol_error(
            410,
            "BROWSER_TOKEN_EXPIRED",
            "The browser pairing token has expired.",
        )
    return pair, claims


def normalized_browser_collection_status(
    incoming_data: dict[str, Any],
) -> dict[str, Any]:
    status = incoming_data.get("collection_status")
    alias = incoming_data.get("field_statuses")
    if status is None and isinstance(alias, dict):
        counts = {
            state: sum(value == state for value in alias.values())
            for state in sorted(BROWSER_ALLOWED_FIELD_STATES)
        }
        status = {
            "status_schema_version": BROWSER_FIELD_STATUS_SCHEMA_VERSION,
            "fixed_signal_count": EXPECTED_BROWSER_SIGNAL_COUNT,
            "counts": counts,
            "fields": dict(alias),
        }
    if not isinstance(status, dict):
        raise browser_protocol_error(
            422,
            "BROWSER_COLLECTION_STATUS_MISSING",
            "collection_status (or the field_statuses compatibility alias) is required.",
        )
    if status.get("status_schema_version") not in {
        BROWSER_FIELD_STATUS_SCHEMA_VERSION,
        "field-status-v1",
    }:
        raise browser_protocol_error(
            422,
            "BROWSER_STATUS_SCHEMA_INVALID",
            "collection_status.status_schema_version is unsupported.",
        )
    fields = status.get("fields")
    counts = status.get("counts")
    if not isinstance(fields, dict) or set(fields) != BROWSER_EXPECTED_WEB_FIELDS:
        raise browser_protocol_error(
            422,
            "BROWSER_FIELD_SET_MISMATCH",
            "collection_status.fields must contain exactly the canonical 67 web_data paths.",
        )
    if any(value not in BROWSER_ALLOWED_FIELD_STATES for value in fields.values()):
        raise browser_protocol_error(
            422,
            "BROWSER_FIELD_STATE_INVALID",
            "collection_status.fields contains an unsupported field state.",
        )
    if (
        status.get("fixed_signal_count") != EXPECTED_BROWSER_SIGNAL_COUNT
        or not isinstance(counts, dict)
        or any(not isinstance(counts.get(state), int) for state in BROWSER_ALLOWED_FIELD_STATES)
        or sum(counts[state] for state in BROWSER_ALLOWED_FIELD_STATES)
        != EXPECTED_BROWSER_SIGNAL_COUNT
        or any(
            counts[state] != sum(value == state for value in fields.values())
            for state in BROWSER_ALLOWED_FIELD_STATES
        )
    ):
        raise browser_protocol_error(
            422,
            "BROWSER_COLLECTION_STATUS_INVALID",
            "collection_status counts must exactly describe all 67 field states.",
        )
    if isinstance(alias, dict) and alias != fields:
        raise browser_protocol_error(
            422,
            "BROWSER_FIELD_STATUS_ALIAS_MISMATCH",
            "field_statuses conflicts with collection_status.fields.",
        )
    return copy.deepcopy(status)


def browser_web_data_paths(web_data: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for layer_name, layer_data in web_data.items():
        if not isinstance(layer_data, dict):
            paths.add(f"web_data.{layer_name}")
            continue
        for field_name in layer_data:
            paths.add(f"web_data.{layer_name}.{field_name}")
    return paths


def validate_and_normalize_browser_payload(
    incoming_data: dict[str, Any],
    pair: dict[str, Any],
) -> dict[str, Any]:
    if incoming_data.get("collector_app") != BROWSER_COLLECTOR_APP:
        raise browser_protocol_error(
            422,
            "BROWSER_COLLECTOR_APP_INVALID",
            f"collector_app must be {BROWSER_COLLECTOR_APP}.",
        )
    if incoming_data.get("schema_version") != BROWSER_PAYLOAD_SCHEMA_VERSION:
        raise browser_protocol_error(
            422,
            "BROWSER_SCHEMA_VERSION_INVALID",
            f"schema_version must be {BROWSER_PAYLOAD_SCHEMA_VERSION}.",
        )
    if incoming_data.get("pair_id") not in (None, pair["pair_id"]):
        append_browser_pair_event(
            "browser_payload_pair_id_conflict",
            pair,
            presented_pair_id=incoming_data.get("pair_id"),
        )
        raise browser_protocol_error(
            409,
            "BROWSER_PAYLOAD_PAIR_MISMATCH",
            "The diagnostic pair_id in the payload conflicts with the bearer token.",
        )
    probe_metadata = incoming_data.get("probe_metadata")
    if not isinstance(probe_metadata, dict):
        raise browser_protocol_error(
            422,
            "BROWSER_PROBE_METADATA_MISSING",
            "probe_metadata is required for browser provenance.",
        )
    pair_probe_url = urlsplit(pair["browser_probe_base_url"])
    expected_page_origin = f"{pair_probe_url.scheme}://{pair_probe_url.netloc}".rstrip("/")
    if probe_metadata.get("metadata_schema_version") != BROWSER_PROBE_METADATA_SCHEMA_VERSION:
        raise browser_protocol_error(
            422,
            "BROWSER_PROBE_METADATA_SCHEMA_INVALID",
            f"probe_metadata.metadata_schema_version must be "
            f"{BROWSER_PROBE_METADATA_SCHEMA_VERSION}.",
        )
    if probe_metadata.get("page_origin") != expected_page_origin:
        raise browser_protocol_error(
            409,
            "BROWSER_PROBE_PAGE_ORIGIN_MISMATCH",
            "probe_metadata.page_origin does not match the ticketed static probe origin.",
        )
    if (
        probe_metadata.get("core_revision") != pair["web_probe_revision"]
        or probe_metadata.get("expected_signal_count") != EXPECTED_BROWSER_SIGNAL_COUNT
    ):
        raise browser_protocol_error(
            409,
            "BROWSER_PROBE_CORE_CONTRACT_MISMATCH",
            "probe_metadata core revision or expected signal count is invalid.",
        )
    presented_core_sha256 = probe_metadata.get("core_bundle_sha256")
    if (
        not isinstance(presented_core_sha256, str)
        or not hmac.compare_digest(
            presented_core_sha256.lower(),
            BROWSER_WEB_PROBE_SHA256,
        )
    ):
        raise browser_protocol_error(
            409,
            "BROWSER_PROBE_CORE_HASH_MISMATCH",
            "probe_metadata.core_bundle_sha256 is not the deployed canonical Web probe.",
        )
    collection_diagnostics = incoming_data.get("collection_diagnostics")
    if (
        not isinstance(collection_diagnostics, dict)
        or not isinstance(collection_diagnostics.get("probe_statuses"), dict)
    ):
        raise browser_protocol_error(
            422,
            "BROWSER_COLLECTION_DIAGNOSTICS_MISSING",
            "collection_diagnostics.probe_statuses is required.",
        )
    metadata_revision = probe_metadata.get("web_probe_revision")
    presented_revision = incoming_data.get("web_probe_revision") or metadata_revision
    if presented_revision != pair["web_probe_revision"]:
        raise browser_protocol_error(
            409,
            "WEB_PROBE_REVISION_MISMATCH",
            "The browser payload revision does not match the issued ticket.",
        )
    web_data = incoming_data.get("web_data")
    if not isinstance(web_data, dict):
        raise browser_protocol_error(
            422,
            "BROWSER_WEB_DATA_INVALID",
            "web_data must be an object.",
        )
    present_paths = browser_web_data_paths(web_data)
    unexpected_paths = present_paths - BROWSER_EXPECTED_WEB_FIELDS
    if unexpected_paths:
        raise browser_protocol_error(
            422,
            "BROWSER_WEB_FIELD_UNEXPECTED",
            f"web_data contains non-canonical fields: {sorted(unexpected_paths)[:3]}",
        )
    normalized_status = normalized_browser_collection_status(incoming_data)
    observed_paths = {
        path
        for path, state in normalized_status["fields"].items()
        if state == "observed"
    }
    missing_observed_paths = observed_paths - present_paths
    if missing_observed_paths:
        raise browser_protocol_error(
            422,
            "BROWSER_OBSERVED_VALUE_MISSING",
            f"Observed fields have no web_data value: {sorted(missing_observed_paths)[:3]}",
        )
    normalized = copy.deepcopy(incoming_data)
    normalized["pair_id"] = pair["pair_id"]
    normalized["web_probe_revision"] = pair["web_probe_revision"]
    normalized["collection_status"] = normalized_status
    normalized.pop("field_statuses", None)
    return normalized


def browser_receipt_response(
    pair: dict[str, Any],
    duplicate_payload: bool,
) -> dict[str, Any]:
    completed = pair["pair_status"] == "completed"
    provisional_staged = pair["pair_status"] == "awaiting_app"
    return {
        "status": "success",
        "browser_pair_schema_version": BROWSER_PAIR_SCHEMA_VERSION,
        "pair_id": pair["pair_id"],
        "pair_status": pair["pair_status"],
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "receipt_id": pair["browser_receipt_id"],
        "browser_receipt_id": pair["browser_receipt_id"],
        "browser_session_id": pair["browser_session_id"],
        "browser_payload_sha256": pair["browser_payload_sha256"],
        "duplicate_payload": duplicate_payload,
        "receipt": {
            "receipt_schema_version": "browser-collection-receipt-v1",
            "receipt_id": pair["browser_receipt_id"],
            "browser_receipt_id": pair["browser_receipt_id"],
            "browser_session_id": pair["browser_session_id"],
            "browser_payload_sha256": pair["browser_payload_sha256"],
            "server_received_at": pair["browser_received_at"],
            "duplicate_payload": duplicate_payload,
            "stored_new_jsonl_row": completed and not duplicate_payload,
            "provisional_payload_staged": provisional_staged,
            "staged_new_jsonl_row": provisional_staged and not duplicate_payload,
            "collection_batch_id": pair["collection_batch_id"],
            "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
            "pair_id": pair["pair_id"],
        },
    }


def finalize_browser_pair(pair: dict[str, Any]) -> bool:
    """Write formal browser rows only after both App receipt and browser payload exist."""
    if pair["pair_status"] == "completed":
        return False
    if (
        pair.get("app_receipt_id") is None
        or pair.get("app_payload_sha256") is None
        or pair.get("browser_payload_sha256") is None
    ):
        return False
    incoming_data = pair.get("browser_incoming_data")
    normalized_data = pair.get("browser_normalized_data")
    if not isinstance(incoming_data, dict) or not isinstance(normalized_data, dict):
        raise CollectionBatchError(
            f"Browser pair {pair['pair_id']} has no staged canonical payload."
        )

    server_received_at = pair["browser_received_at"]
    browser_receipt_id = pair["browser_receipt_id"]
    payload_sha256 = pair["browser_payload_sha256"]
    raw_archive = {
        "raw_browser_payload_schema_version": "browser-raw-payload-v1",
        "server_received_at": server_received_at,
        "pair_id": pair["pair_id"],
        "ticket_request_id": pair["ticket_request_id"],
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "app_session_id": pair["app_session_id"],
        "app_receipt_id": pair["app_receipt_id"],
        "browser_session_id": pair["browser_session_id"],
        "browser_receipt_id": browser_receipt_id,
        "browser_payload_sha256": payload_sha256,
        "collection_batch_id": pair["collection_batch_id"],
        "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
        "collection_batch_started_at": pair["collection_batch_started_at"],
        "canonical_received_payload": incoming_data,
    }
    collected_record = {
        "browser_collected_data_schema_version": "browser-collected-data-v1",
        "server_received_at": server_received_at,
        "pair_id": pair["pair_id"],
        "ticket_request_id": pair["ticket_request_id"],
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "app_session_id": pair["app_session_id"],
        "app_receipt_id": pair["app_receipt_id"],
        "app_payload_sha256": pair["app_payload_sha256"],
        "browser_receipt_id": browser_receipt_id,
        "browser_payload_sha256": payload_sha256,
        "collection_batch_id": pair["collection_batch_id"],
        "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
        **normalized_data,
    }
    provenance_record = {
        "browser_pair_provenance_schema_version": "browser-pair-provenance-v1",
        "pair_id": pair["pair_id"],
        "pair_status": "completed",
        "ticket_request_id": pair["ticket_request_id"],
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "paired_at": utc_now_iso(),
        "collection_batch_id": pair["collection_batch_id"],
        "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
        "collection_batch_started_at": pair["collection_batch_started_at"],
        "app_session_id": pair["app_session_id"],
        "app_receipt_id": pair["app_receipt_id"],
        "app_payload_sha256": pair["app_payload_sha256"],
        "app_receipt_server_received_at": pair["app_receipt_server_received_at"],
        "browser_session_id": pair["browser_session_id"],
        "browser_receipt_id": browser_receipt_id,
        "browser_payload_sha256": payload_sha256,
        "browser_received_at": server_received_at,
        "resolved_browser_package": pair["resolved_browser_package"],
        "selected_browser_package": pair["selected_browser_package"],
        "launch_resolution_status": pair["launch_resolution_status"],
        "selected_browser_activity": pair["selected_browser_activity"],
        "browser_candidate_packages": pair["browser_candidate_packages"],
        "browser_selection_policy_revision": (
            pair["browser_selection_policy_revision"]
        ),
        "web_probe_revision": pair["web_probe_revision"],
        "browser_probe_base_url": pair["browser_probe_base_url"],
    }
    append_jsonl_durably(raw_archive, RAW_BROWSER_PAYLOADS_JSONL_FILE)
    append_jsonl_durably(collected_record, BROWSER_COLLECTED_DATA_JSONL_FILE)
    append_jsonl_durably(provenance_record, BROWSER_PAIR_PROVENANCE_JSONL_FILE)
    pair["pair_status"] = "completed"
    pair["browser_ticket_consumed_at"] = server_received_at
    append_browser_pair_event(
        "browser_payload_accepted",
        pair,
        browser_session_id=pair["browser_session_id"],
        browser_receipt_id=pair["browser_receipt_id"],
        browser_payload_sha256=pair["browser_payload_sha256"],
    )
    return True


def bind_provisional_pair_to_receipt(receipt: dict[str, Any]) -> bool:
    """Bind one persisted App receipt to its exact provisional ticket request."""
    ticket_request_id = receipt.get("browser_ticket_request_id")
    if not isinstance(ticket_request_id, str) or not ticket_request_id:
        return False
    request_key = f"{receipt.get('collection_batch_id')}:{ticket_request_id}"
    pair_id = browser_ticket_requests_db.get(request_key)
    if pair_id is None:
        return False
    pair = browser_pairs_db.get(pair_id)
    if pair is None or pair.get("ticket_binding_mode") != "provisional_session":
        return False
    if current_browser_pair_status(pair) == "expired":
        append_browser_pair_event(
            "app_receipt_binding_skipped",
            pair,
            binding_error="pair_expired",
            presented_app_receipt_id=receipt.get("receipt_id"),
        )
        return False
    expected_identity = (
        pair["app_session_id"],
        pair["collection_batch_id"],
        pair["ticket_request_id"],
    )
    presented_identity = (
        receipt.get("session_id"),
        receipt.get("collection_batch_id"),
        receipt.get("browser_ticket_request_id"),
    )
    app_payload_sha256 = receipt.get("payload_sha256")
    valid_hash = (
        isinstance(app_payload_sha256, str)
        and len(app_payload_sha256) == 64
        and all(character in "0123456789abcdefABCDEF" for character in app_payload_sha256)
    )
    valid_receipt = (
        expected_identity == presented_identity
        and receipt.get("collector_app") == "featureapp"
        and receipt.get("schema_version") in SUPPORTED_EXPANDED_SCHEMA_VERSIONS
        and valid_hash
    )
    if not valid_receipt:
        append_browser_pair_event(
            "app_receipt_binding_conflict",
            pair,
            presented_app_receipt_id=receipt.get("receipt_id"),
            presented_app_session_id=receipt.get("session_id"),
            presented_ticket_request_id=receipt.get("browser_ticket_request_id"),
        )
        return False
    if pair.get("app_receipt_id") is not None:
        if (
            pair.get("app_payload_sha256") == app_payload_sha256
            and pair.get("app_session_id") == receipt.get("session_id")
        ):
            if (
                pair.get("browser_payload_sha256") is not None
                and pair["pair_status"] != "completed"
            ):
                finalize_browser_pair(pair)
            return False
        append_browser_pair_event(
            "app_receipt_binding_conflict",
            pair,
            presented_app_receipt_id=receipt.get("receipt_id"),
            binding_error="pair_already_bound_to_different_receipt",
        )
        return False

    pair.update(
        {
            "app_receipt_id": receipt.get("receipt_id"),
            "app_payload_sha256": app_payload_sha256,
            "app_receipt_server_received_at": receipt.get("server_received_at"),
        }
    )
    browser_already_received = pair.get("browser_payload_sha256") is not None
    pair["pair_status"] = (
        "awaiting_app" if browser_already_received else "awaiting_browser"
    )
    append_browser_pair_event(
        "app_receipt_bound",
        pair,
        app_payload_sha256=app_payload_sha256,
        app_receipt_server_received_at=receipt.get("server_received_at"),
    )
    if browser_already_received:
        finalize_browser_pair(pair)
    return True


def store_browser_fingerprint(
    payload: BrowserFingerprintPayload,
    browser_ticket: str,
) -> dict[str, Any]:
    pair, _ = authorize_browser_pair(browser_ticket, "browser_upload")
    incoming_data = model_to_dict(payload, exclude_none=True)
    payload_sha256 = canonical_payload_sha256(incoming_data)
    if pair.get("browser_payload_sha256") is not None:
        if hmac.compare_digest(payload_sha256, pair["browser_payload_sha256"]):
            append_browser_pair_event(
                "browser_payload_idempotent_replay",
                pair,
                browser_session_id=pair["browser_session_id"],
                browser_receipt_id=pair["browser_receipt_id"],
                browser_payload_sha256=payload_sha256,
            )
            return browser_receipt_response(pair, duplicate_payload=True)
        append_browser_pair_event(
            "browser_payload_replay_conflict",
            pair,
            browser_session_id=incoming_data.get("browser_session_id"),
            presented_browser_payload_sha256=payload_sha256,
            accepted_browser_payload_sha256=pair["browser_payload_sha256"],
        )
        raise browser_protocol_error(
            409,
            "BROWSER_TICKET_REPLAY_CONFLICT",
            "The one-time browser ticket was already consumed by a different payload.",
        )
    if pair["pair_status"] not in {"awaiting_app_and_browser", "awaiting_browser"}:
        raise browser_protocol_error(
            410,
            "BROWSER_TICKET_EXPIRED",
            "The browser ticket is no longer active.",
        )
    normalized_data = validate_and_normalize_browser_payload(incoming_data, pair)

    server_received_at = utc_now_iso()
    browser_receipt_id = hashlib.sha256(
        f"{pair['pair_id']}:{payload_sha256}:{server_received_at}".encode("utf-8")
    ).hexdigest()[:24]
    pair.update(
        {
            "browser_session_id": incoming_data["browser_session_id"],
            "browser_receipt_id": browser_receipt_id,
            "browser_payload_sha256": payload_sha256,
            "browser_received_at": server_received_at,
            "browser_incoming_data": incoming_data,
            "browser_normalized_data": normalized_data,
        }
    )
    if pair.get("app_receipt_id") is None:
        pair["pair_status"] = "awaiting_app"
        provisional_record = {
            "browser_provisional_payload_schema_version":
                "browser-provisional-payload-v1",
            "staged_at": server_received_at,
            "pair_id": pair["pair_id"],
            "ticket_request_id": pair["ticket_request_id"],
            "ticket_binding_mode": pair["ticket_binding_mode"],
            "app_session_id": pair["app_session_id"],
            "app_receipt_id": None,
            "browser_session_id": pair["browser_session_id"],
            "browser_receipt_id": browser_receipt_id,
            "browser_payload_sha256": payload_sha256,
            "collection_batch_id": pair["collection_batch_id"],
            "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
            "collection_batch_started_at": pair["collection_batch_started_at"],
            "canonical_received_payload": incoming_data,
        }
        append_jsonl_durably(
            provisional_record,
            BROWSER_PROVISIONAL_PAYLOADS_JSONL_FILE,
        )
        append_browser_pair_event(
            "browser_payload_staged",
            pair,
            browser_session_id=pair["browser_session_id"],
            browser_receipt_id=pair["browser_receipt_id"],
            browser_payload_sha256=pair["browser_payload_sha256"],
        )
    else:
        finalize_browser_pair(pair)
    return browser_receipt_response(pair, duplicate_payload=False)


def record_browser_stage(
    payload: BrowserStagePayload,
    browser_ticket: str,
) -> dict[str, Any]:
    """Record how far the external browser reached without changing Web67 data."""
    if payload.stage not in BROWSER_STAGE_ORDER:
        raise browser_protocol_error(
            422,
            "BROWSER_STAGE_INVALID",
            f"stage must be one of {sorted(BROWSER_STAGE_ORDER)}.",
        )
    claims = decode_browser_token(browser_ticket)
    expected_token_use = (
        "pair_poll" if payload.stage == "launch_attempted" else "browser_upload"
    )
    if claims.get("token_use") != expected_token_use:
        raise browser_protocol_error(
            403,
            "BROWSER_STAGE_TOKEN_WRONG_USE",
            "The presented token cannot record this browser stage.",
        )
    pair, _ = authorize_browser_pair(
        browser_ticket,
        expected_token_use,
        expected_pair_id=payload.pair_id,
    )

    stage_key = f"{payload.launch_attempt}:{payload.stage}"
    observed_keys = pair.setdefault("browser_stage_keys", set())
    duplicate_stage = stage_key in observed_keys
    if not duplicate_stage:
        observed_keys.add(stage_key)
        if payload.stage == "launch_attempted":
            pair["app_launch_attempt_count"] = int(
                pair.get("app_launch_attempt_count", 0)
            ) + 1
            pair["latest_app_launch_attempt_at"] = utc_now_iso()
            pair["latest_launch_attempt"] = payload.launch_attempt
        else:
            pair["browser_stage_count"] = int(pair.get("browser_stage_count", 0)) + 1
            current_stage = pair.get("latest_browser_stage")
            if (
                current_stage not in BROWSER_STAGE_ORDER
                or BROWSER_STAGE_ORDER[payload.stage] >= BROWSER_STAGE_ORDER[current_stage]
            ):
                pair["latest_browser_stage"] = payload.stage
                pair["latest_browser_stage_at"] = utc_now_iso()
                pair["latest_launch_attempt"] = payload.launch_attempt
        append_browser_pair_event(
            "browser_stage_observed",
            pair,
            browser_stage=payload.stage,
            launch_attempt=payload.launch_attempt,
            client_stage_at_ms=payload.client_stage_at_ms,
        )

    return {
        "status": "success",
        "pair_id": pair["pair_id"],
        "pair_status": current_browser_pair_status(pair),
        "browser_stage": payload.stage,
        "launch_attempt": payload.launch_attempt,
        "duplicate_stage": duplicate_stage,
    }


def browser_pair_status_response(pair: dict[str, Any]) -> dict[str, Any]:
    pair_status = current_browser_pair_status(pair)
    response = {
        "status": "success",
        "browser_pair_schema_version": BROWSER_PAIR_SCHEMA_VERSION,
        "pair_id": pair["pair_id"],
        "pair_status": pair_status,
        "ticket_binding_mode": pair["ticket_binding_mode"],
        "ticket_request_id": pair["ticket_request_id"],
        "collection_batch_id": pair["collection_batch_id"],
        "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
        "app_session_id": pair["app_session_id"],
        "app_receipt_id": pair.get("app_receipt_id"),
        "app_payload_sha256": pair.get("app_payload_sha256"),
        "web_probe_revision": pair["web_probe_revision"],
        "issued_at": pair["issued_at"],
        "expires_at": pair["ticket_expires_at"],
        "ticket_expires_at": pair["ticket_expires_at"],
        "poll_expires_at": pair["poll_expires_at"],
        "latest_browser_stage": pair.get("latest_browser_stage"),
        "latest_browser_stage_at": pair.get("latest_browser_stage_at"),
        "latest_launch_attempt": pair.get("latest_launch_attempt"),
        "browser_stage_count": int(pair.get("browser_stage_count", 0)),
        "app_launch_attempt_count": int(pair.get("app_launch_attempt_count", 0)),
        "latest_app_launch_attempt_at": pair.get("latest_app_launch_attempt_at"),
    }
    if pair.get("browser_payload_sha256") is not None:
        response.update(
            {
                "browser_session_id": pair["browser_session_id"],
                "browser_receipt_id": pair["browser_receipt_id"],
                "browser_payload_sha256": pair["browser_payload_sha256"],
                "browser_received_at": pair["browser_received_at"],
            }
        )
    return response


@app.on_event("startup")
def start_collection_batch_for_server_lifecycle() -> None:
    start_collection_batch()


@app.on_event("shutdown")
def close_collection_batch_for_server_lifecycle() -> None:
    try:
        close_active_collection_batch()
    except Exception:
        # Leave the active marker behind so a later start can recover the boundary.
        logger.exception("Failed to record graceful collection batch shutdown")

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
        active_batch = get_active_collection_batch()
    except CollectionBatchError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

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
        incoming_data = model_to_dict(payload, exclude_unset=True, exclude_none=True)
        is_expanded_collector = is_expanded_collector_payload(incoming_data)
        target_sessions_db = expanded_sessions_db if is_expanded_collector else sessions_db
        target_db_file = EXPANDED_DB_FILE if is_expanded_collector else DB_FILE
        target_jsonl_file = EXPANDED_COLLECTED_JSONL_FILE if is_expanded_collector else COLLECTED_JSONL_FILE
        payload_sha256 = canonical_payload_sha256(incoming_data)
        server_received_at = datetime.utcnow().isoformat() + "Z"
        validation_warnings = expanded_payload_warnings(incoming_data) if is_expanded_collector else []
        existing_session = target_sessions_db.get(session_id)
        is_duplicate_payload = bool(existing_session) and all(
            existing_session.get(key) == value
            for key, value in incoming_data.items()
        )

        receipt = {
            "receipt_schema_version": "collection-receipt-v1",
            "receipt_id": hashlib.sha256(
                f"{session_id}:{payload_sha256}:{server_received_at}".encode("utf-8")
            ).hexdigest()[:24],
            "server_received_at": server_received_at,
            "session_id": session_id,
            "payload_sha256": payload_sha256,
            "collector_app": incoming_data.get("collector_app"),
            "schema_version": incoming_data.get("schema_version"),
            "browser_ticket_request_id": incoming_data.get(
                "browser_ticket_request_id"
            ),
            "storage_target": target_jsonl_file.name,
            "duplicate_payload": is_duplicate_payload,
            "stored_new_jsonl_row": not is_duplicate_payload,
            "validation_status": "accepted_with_warnings" if validation_warnings else "accepted",
            "validation_warnings": validation_warnings,
            "collection_batch_id": active_batch["collection_batch_id"],
            "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
            "collection_batch_started_at": active_batch["started_at"],
        }
        # Preserve the canonical request before session merging and analysis
        # flattening can alter its structure. Identical retries remain receipt-only.
        if is_expanded_collector and not is_duplicate_payload:
            raw_payload_archive = {
                "raw_payload_archive_schema_version": "expanded-raw-payload-v1",
                "server_received_at": server_received_at,
                "session_id": session_id,
                "receipt_id": receipt["receipt_id"],
                "payload_sha256": payload_sha256,
                "duplicate_payload": is_duplicate_payload,
                "stored_new_jsonl_row": True,
                "collection_batch_id": active_batch["collection_batch_id"],
                "collection_batch_id_source": COLLECTION_BATCH_ID_SOURCE,
                "collection_batch_started_at": active_batch["started_at"],
                "canonical_received_payload": incoming_data,
            }
            save_to_jsonl(raw_payload_archive, RAW_EXPANDED_PAYLOADS_JSONL_FILE)
            receipt["raw_payload_archived"] = True
            receipt["raw_payload_archive"] = RAW_EXPANDED_PAYLOADS_JSONL_FILE.name
        else:
            receipt["raw_payload_archived"] = False
    
        # 1. 检查是否是新会话。如果是，初始化一条空记录
        if session_id not in target_sessions_db:
            target_sessions_db[session_id] = {
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

        # 3. 将新数据合并到数据库记录中
        if "android_native_data" in incoming_data:
            target_sessions_db[session_id]["android_native_data"] = incoming_data["android_native_data"]
        if "webview_data" in incoming_data:
            target_sessions_db[session_id]["webview_data"] = incoming_data["webview_data"]
        if "web_data" in incoming_data:
            target_sessions_db[session_id]["web_data"] = incoming_data["web_data"]

        preserved_top_level_keys = {
            "session_id",
            "timestamp",
            "client_ip",
            "android_native_data",
            "webview_data",
            "web_data",
        }
        for key, value in incoming_data.items():
            if key not in preserved_top_level_keys:
                target_sessions_db[session_id][key] = value
        
        # 更新最新时间戳和 IP（如果有变化的话）
        if "client_ip" in incoming_data:
            target_sessions_db[session_id]["client_ip"] = incoming_data["client_ip"]
        target_sessions_db[session_id]["timestamp"] = incoming_data["timestamp"]

        # 4. 将合并后的全量数据持久化保存到本地 JSON 文件 (这里保存的是原始嵌套结构)
        with open(target_db_file, "w", encoding="utf-8") as f:
            json.dump(target_sessions_db, f, ensure_ascii=False, indent=4)

        current_session = target_sessions_db[session_id]
        
        # Expanded payload 即使缺一层也必须落入 JSONL，避免一次性付费采集因局部探针失败而整条丢失。
        # 旧采集链路仍保留原来的三端齐备条件。
        should_persist_jsonl = is_expanded_collector or (
            current_session.get("android_native_data") and current_session.get("web_data")
        )
        if should_persist_jsonl:
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
            if not is_duplicate_payload:
                save_to_jsonl(llm_session_data, target_jsonl_file)

        save_to_jsonl(receipt, COLLECTION_RECEIPTS_JSONL_FILE)
        try:
            bind_provisional_pair_to_receipt(receipt)
        except Exception:
            # The App receipt is already durable and remains authoritative.
            # A delayed browser bind may be retried by an identical App upload.
            logger.exception(
                "Failed to bind provisional browser pair after durable App receipt "
                f"{receipt['receipt_id']}"
            )

        # 返回成功响应
        return {
            "status": "success",
            "session_id": payload.session_id,
            "message": "设备指纹数据已成功收集",
            "receipt": receipt,
        }

    except Exception as e:
        logger.error(f"处理设备指纹数据时出错: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")


@app.post("/api/collect/browser-ticket")
async def issue_browser_ticket(
    payload: BrowserTicketRequest,
    request: Request,
):
    """Issue one short-lived browser upload token plus a longer-lived app poll token."""
    browser_upload_url = str(request.url_for("collect_browser_fingerprint"))
    browser_stage_url = str(request.url_for("collect_browser_stage"))
    return issue_browser_ticket_for_upload_url(
        payload,
        browser_upload_url,
        browser_stage_url,
    )


@app.post("/api/collect/browser-stage")
async def collect_browser_stage(
    payload: BrowserStagePayload,
    authorization: Optional[str] = Header(None),
):
    """Accept authenticated probe progress without adding fingerprint fields."""
    browser_ticket = require_bearer_token(authorization)
    return record_browser_stage(payload, browser_ticket)


@app.post("/api/collect/browser-fingerprint")
async def collect_browser_fingerprint(
    payload: BrowserFingerprintPayload,
    authorization: Optional[str] = Header(None),
):
    """Accept one canonical 67-field available-browser payload."""
    browser_ticket = require_bearer_token(authorization)
    return store_browser_fingerprint(payload, browser_ticket)


@app.get("/api/collect/browser-pairs/{pair_id}")
async def get_browser_pair_status(
    pair_id: str,
    authorization: Optional[str] = Header(None),
):
    """Let the App poll without exposing the browser upload credential."""
    poll_token = require_bearer_token(authorization)
    pair, _ = authorize_browser_pair(
        poll_token,
        "pair_poll",
        expected_pair_id=pair_id,
    )
    return browser_pair_status_response(pair)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}


@app.get("/api/collect/readiness")
async def collection_readiness():
    """Cloud-run preflight: confirm contract, partial-payload policy and output files."""
    active_batch = active_collection_batch
    return {
        "status": "ready",
        "readiness_schema_version": "featureapp-readiness-v1",
        "server_time_utc": datetime.utcnow().isoformat() + "Z",
        "supported_expanded_schema_versions": sorted(SUPPORTED_EXPANDED_SCHEMA_VERSIONS),
        "expected_expanded_signal_count": EXPECTED_EXPANDED_SIGNAL_COUNT,
        "accepts_partial_expanded_payloads": True,
        "duplicate_payload_suppression": True,
        "collection_receipts_enabled": True,
        "raw_expanded_payload_archive_enabled": True,
        "browser_pairing_enabled": True,
        "browser_provisional_ticket_enabled": True,
        "browser_pair_schema_version": BROWSER_PAIR_SCHEMA_VERSION,
        "browser_payload_schema_version": BROWSER_PAYLOAD_SCHEMA_VERSION,
        "browser_collector_app": BROWSER_COLLECTOR_APP,
        "browser_web_probe_revision": BROWSER_WEB_PROBE_REVISION,
        "browser_web_probe_sha256": BROWSER_WEB_PROBE_SHA256,
        "browser_allowed_probe_origins": sorted(BROWSER_ALLOWED_PROBE_ORIGINS),
        "expected_browser_signal_count": EXPECTED_BROWSER_SIGNAL_COUNT,
        "browser_ticket_ttl_seconds": BROWSER_TICKET_TTL_SECONDS,
        "browser_poll_ttl_seconds": BROWSER_POLL_TTL_SECONDS,
        "browser_ticket_transport": "url_fragment_then_bearer",
        "browser_stage_telemetry_enabled": True,
        "browser_stage_names": sorted(BROWSER_STAGE_ORDER),
        "browser_payload_duplicate_suppression": True,
        "browser_pair_artifacts": [
            RAW_BROWSER_PAYLOADS_JSONL_FILE.name,
            BROWSER_PROVISIONAL_PAYLOADS_JSONL_FILE.name,
            BROWSER_COLLECTED_DATA_JSONL_FILE.name,
            BROWSER_PAIR_EVENTS_JSONL_FILE.name,
            BROWSER_PAIR_PROVENANCE_JSONL_FILE.name,
        ],
        "storage_concurrency_mode": STORAGE_CONCURRENCY_MODE,
        "collection_batch_lifecycle_enabled": True,
        "collection_batch_id": (
            active_batch.get("collection_batch_id") if active_batch is not None else None
        ),
        "collection_batch_status": "open" if active_batch is not None else "not_initialized",
        "collection_batch_id_source": (
            COLLECTION_BATCH_ID_SOURCE if active_batch is not None else None
        ),
    }

@app.post("/api/risk/local-score")
async def collect_local_score(payload: LocalRiskScorePayload):
    """接收新 App 在端侧完成的随机森林评分结果"""
    try:
        result = model_to_dict(payload, exclude_none=True)
        result["server_received_at"] = datetime.utcnow().isoformat() + "Z"
        save_local_score_to_jsonl(result)
        return {
            "status": "success",
            "session_id": payload.session_id,
            "message": "端侧评分结果已接收"
        }
    except Exception as e:
        logger.error(f"处理端侧评分结果时出错: {str(e)}")
        raise HTTPException(status_code=500, detail="内部服务器错误")

def save_to_jsonl(merged_data: dict, jsonl_file_path: str = COLLECTED_JSONL_FILE):
    # 以 "a" (append 追加) 模式打开文件
    with open(jsonl_file_path, "a", encoding="utf-8") as f:
        # 把字典转成单行 JSON 字符串，并加上换行符
        json_line = json.dumps(merged_data, ensure_ascii=False)
        f.write(json_line + "\n")
        
    print(f"会话 {merged_data.get('session_id')} 已追加到 {jsonl_file_path}")

def save_local_score_to_jsonl(score_data: dict):
    jsonl_file_path = LOCAL_SCORE_JSONL_FILE

    with open(jsonl_file_path, "a", encoding="utf-8") as f:
        json_line = json.dumps(score_data, ensure_ascii=False)
        f.write(json_line + "\n")

    print(f"会话 {score_data.get('session_id')} 端侧评分已追加到 {jsonl_file_path}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
