import json
import logging
import hashlib
from datetime import datetime
import os
from pathlib import Path
import tempfile
from typing import Optional
import uuid
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
EXPECTED_EXPANDED_SIGNAL_COUNT = 177
COLLECTION_BATCH_SCHEMA_VERSION = "backend-collection-batch-v1"
COLLECTION_BATCH_STATE_SCHEMA_VERSION = "backend-collection-batch-state-v1"
COLLECTION_BATCH_ID_SOURCE = "backend_process_lifecycle"
STORAGE_CONCURRENCY_MODE = "single_process_json_files"
SUPPORTED_EXPANDED_SCHEMA_VERSIONS = {
    "expanded-v2",
    "expanded-v2.1-status",
    "expanded-v2.2-status",
}


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
