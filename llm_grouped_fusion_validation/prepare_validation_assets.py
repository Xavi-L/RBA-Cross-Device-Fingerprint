#!/usr/bin/env python3
"""Prepare offline assets for GLM grouped-fusion validation.

This script does not call GLM. It creates the no-official-knowledge rule-KB
ablation, stable-device grouping metadata, evidence JSONL files, and sample
manifests used by later paid/API steps.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sklearn.model_selection import train_test_split


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = REPO_ROOT / "training" / "scored_data.jsonl"
DEFAULT_RULE_KB = REPO_ROOT / "scoring" / "rule_knowledge_base.json"
RANDOM_STATE = 42
TEST_SIZE = 0.2

RUNTIME_PERTURBATIONS = {
    "android_native_data.uptime_ms": {"mode": "multiplier", "low": 0.70, "high": 1.30},
    "android_native_data.avail_memory_gb": {"mode": "multiplier", "low": 0.85, "high": 1.15},
    "android_native_data.battery_level_pct": {
        "mode": "add_int",
        "low": -12,
        "high": 12,
        "min": 0,
        "max": 100,
    },
    "android_native_data.battery_temp_celsius": {
        "mode": "add_float",
        "low": -2.5,
        "high": 2.5,
        "min": 15,
        "max": 55,
        "digits": 1,
    },
    "android_native_data.battery_voltage_mv": {
        "mode": "add_int",
        "low": -80,
        "high": 80,
        "min": 3000,
        "max": 5000,
    },
    "webview_data.bridge_latency_ms": {"mode": "multiplier", "low": 0.70, "high": 1.50},
    "web_data.compute_task_time_ms": {"mode": "multiplier", "low": 0.70, "high": 1.50},
}

FIVE_BANDS = [
    ("low", 0, 20),
    ("low_medium", 21, 34),
    ("medium_cloud_or_test", 35, 49),
    ("suspicious", 50, 79),
    ("high", 80, 100),
]

GROUP_NAMES = [
    "native_web",
    "native_webview",
    "webview_web",
    "tri_layer",
    "physical_runtime",
    "attack_scenario",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare validation assets.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Scored JSONL input.")
    parser.add_argument("--rule-kb", default=str(DEFAULT_RULE_KB), help="Current rule KB JSON.")
    parser.add_argument("--output-dir", default=str(SCRIPT_DIR), help="Output directory.")
    parser.add_argument(
        "--augmentations-per-row",
        type=int,
        default=2,
        help="Runtime perturbation variants per original row.",
    )
    parser.add_argument(
        "--targeted-per-family",
        type=int,
        default=12,
        help="Rows to select per rule/evidence family for targeted pilot.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def strip_official_knowledge(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_official_knowledge(item)
            for key, item in value.items()
            if key not in {"official_knowledge", "external_knowledge_base"}
        }
    if isinstance(value, list):
        return [strip_official_knowledge(item) for item in value]
    return value


def build_no_official_rule_kb(rule_kb: dict[str, Any]) -> dict[str, Any]:
    stripped = strip_official_knowledge(rule_kb)
    original_version = stripped.get("version", "unknown")
    stripped["version"] = f"{original_version}-no-official-ablation"
    stripped["ablation_note"] = (
        "Generated for K0 ablation: official_knowledge and external_knowledge_base "
        "metadata removed; scoring rules, score ranges, and evaluation order are kept."
    )
    return stripped


def get(row: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def set_path(row: dict[str, Any], path: str, value: Any) -> None:
    current = row
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def clean(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).strip()
    return text if text else "blank"


def lower(value: Any) -> str:
    return clean(value).lower()


def digest(payload: Any, length: int = 12) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def parse_android_major(text: Any) -> str:
    match = re.search(r"Android\s+(\d+)", clean(text), flags=re.IGNORECASE)
    return match.group(1) if match else "unknown"


def parse_chrome_major(text: Any) -> str:
    match = re.search(r"(?:Chrome|Chromium)/(\d+)", clean(text), flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"^(\d{2,4})(?:\.|$)", clean(text))
    return match.group(1) if match else "unknown"


def gpu_family(renderer: Any) -> str:
    text = lower(renderer)
    if "swiftshader" in text:
        return "swiftshader"
    if "adreno" in text:
        return "adreno"
    if "mali" in text:
        return "mali"
    if "apple" in text:
        return "apple"
    if "powervr" in text:
        return "powervr"
    return text[:40] if text else "unknown"


def ua_family(ua: Any) -> str:
    text = lower(ua)
    if "python-requests" in text:
        return "python_requests"
    if "headless" in text:
        return "headless_chrome"
    if "windows nt" in text or "win64" in text:
        return "desktop_windows"
    if " wv)" in text or "; wv" in text:
        return "android_webview"
    if "android" in text:
        return "android_browser"
    return "unknown"


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def source_type(row: dict[str, Any]) -> str:
    ua = lower(get(row, "web_data.user_agent"))
    model = lower(get(row, "android_native_data.device_model"))
    board = lower(get(row, "android_native_data.device_board"))
    hardware = lower(get(row, "android_native_data.device_hardware"))
    cpu = lower(get(row, "android_native_data.cpu_abi"))
    renderer = lower(get(row, "web_data.webgl_renderer"))
    sensor_count = get(row, "android_native_data.sensor_total_count")
    jsbridge = get(row, "webview_data.jsbridge_injected")

    script_like = (
        sensor_count is None
        or jsbridge is False
        or "python-requests" in ua
        or "windows nt" in ua
        or "headless" in ua
        or model == "windows pc fake"
        or (isinstance(sensor_count, (int, float)) and sensor_count < 10)
        or "goldfish" in board
        or "ranchu" in hardware
        or "x86" in cpu
        or "swiftshader" in renderer
    )
    if script_like:
        return "script_attack"

    installer = lower(get(row, "webview_data.installer_package"))
    timezone = get(row, "web_data.timezone_offset")
    adb = get(row, "android_native_data.is_adb_enabled")
    if installer == "manual" or timezone == 0 or adb is True:
        return "cloud_or_test_device"

    return "physical_device"


def script_template(row: dict[str, Any]) -> str:
    ua = lower(get(row, "web_data.user_agent"))
    model = lower(get(row, "android_native_data.device_model"))
    board = lower(get(row, "android_native_data.device_board"))
    hardware = lower(get(row, "android_native_data.device_hardware"))
    sensor_count = get(row, "android_native_data.sensor_total_count")
    jsbridge = get(row, "webview_data.jsbridge_injected")

    if "python-requests" in ua or jsbridge is False or sensor_count is None:
        return "api_replay"
    if "windows nt" in ua or "headless" in ua or model == "windows pc fake":
        return "headless_pc"
    if "goldfish" in board or "ranchu" in hardware or (
        isinstance(sensor_count, (int, float)) and sensor_count < 10
    ):
        return "cheap_emulator"
    return "script_other"


def stable_identity(row: dict[str, Any]) -> dict[str, Any]:
    source = source_type(row)
    if source == "script_attack":
        return {
            "source_type": source,
            "script_template": script_template(row),
            "device_model": get(row, "android_native_data.device_model"),
            "device_board": get(row, "android_native_data.device_board"),
            "device_hardware": get(row, "android_native_data.device_hardware"),
            "cpu_abi": get(row, "android_native_data.cpu_abi"),
            "sensor_total_count": get(row, "android_native_data.sensor_total_count"),
            "jsbridge_injected": get(row, "webview_data.jsbridge_injected"),
            "ua_family": ua_family(get(row, "web_data.user_agent")),
            "gpu_family": gpu_family(get(row, "web_data.webgl_renderer")),
        }

    sensor_flags = {
        name: get(row, f"android_native_data.{name}")
        for name in [
            "has_accelerometer",
            "has_gyroscope",
            "has_light_sensor",
            "has_magnetic_field",
            "has_pressure_sensor",
            "has_proximity_sensor",
        ]
    }
    ua = get(row, "web_data.user_agent")
    webview_version = get(row, "webview_data.webview_provider_version")
    return {
        "source_type": source,
        "build_fingerprint": get(row, "android_native_data.build_fingerprint"),
        "device_model": get(row, "android_native_data.device_model"),
        "device_product": get(row, "android_native_data.device_product"),
        "device_board": get(row, "android_native_data.device_board"),
        "device_hardware": get(row, "android_native_data.device_hardware"),
        "cpu_abi": get(row, "android_native_data.cpu_abi"),
        "os_api_level": get(row, "android_native_data.os_api_level"),
        "build_tags": get(row, "android_native_data.build_tags"),
        "build_type": get(row, "android_native_data.build_type"),
        "screen_resolution_physical": get(row, "android_native_data.screen_resolution_physical"),
        "screen_density_dpi": get(row, "android_native_data.screen_density_dpi"),
        "screen_xdpi": get(row, "android_native_data.screen_xdpi"),
        "screen_ydpi": get(row, "android_native_data.screen_ydpi"),
        "total_memory_gb": round(float(get(row, "android_native_data.total_memory_gb", -1)), 1),
        "sensor_total_count": get(row, "android_native_data.sensor_total_count"),
        "sensor_flags": sensor_flags,
        "webview_package": get(row, "webview_data.webview_provider_package"),
        "webview_chrome_major": parse_chrome_major(webview_version),
        "ua_android_major": parse_android_major(ua),
        "ua_chrome_major": parse_chrome_major(ua),
        "ua_family": ua_family(ua),
        "gpu_family": gpu_family(get(row, "web_data.webgl_renderer")),
        "canvas_hash": get(row, "web_data.canvas_hash"),
        "hardware_concurrency": get(row, "web_data.hardware_concurrency"),
        "web_device_memory": get(row, "web_data.device_memory"),
    }


def score_band(score: int | float | None) -> str:
    if score is None:
        return "unknown"
    for label, low, high in FIVE_BANDS:
        if low <= float(score) <= high:
            return label
    return "out_of_range"


def rule_family(row: dict[str, Any]) -> str:
    stype = source_type(row)
    ua = lower(get(row, "web_data.user_agent"))
    installer = lower(get(row, "webview_data.installer_package"))
    adb = get(row, "android_native_data.is_adb_enabled")
    debug = get(row, "webview_data.is_debuggable")
    cleartext = get(row, "webview_data.is_cleartext_traffic_permitted")
    jsbridge = get(row, "webview_data.jsbridge_injected")
    sensor_count = get(row, "android_native_data.sensor_total_count")

    if stype == "script_attack":
        if jsbridge is False or "python-requests" in ua:
            return "core_integrity"
        return "attack_scenario"
    if adb is True and debug is True and cleartext is True and installer != "manual":
        return "tolerance"
    if isinstance(sensor_count, (int, float)) and sensor_count < 20:
        return "physical_runtime"
    if installer == "manual" or adb is True:
        return "native_webview"
    return "tri_layer"


def evidence_payload(row: dict[str, Any]) -> dict[str, Any]:
    native = row.get("android_native_data", {})
    webview = row.get("webview_data", {})
    web = row.get("web_data", {})
    return {
        "native_web": {
            "device_model": native.get("device_model"),
            "device_brand": native.get("device_brand"),
            "device_product": native.get("device_product"),
            "os_api_level": native.get("os_api_level"),
            "cpu_abi": native.get("cpu_abi"),
            "screen_resolution_physical": native.get("screen_resolution_physical"),
            "screen_density_dpi": native.get("screen_density_dpi"),
            "user_agent": web.get("user_agent"),
            "platform": web.get("platform"),
            "screen_resolution_logical": web.get("screen_resolution_logical"),
            "device_pixel_ratio": web.get("device_pixel_ratio"),
            "webgl_renderer": web.get("webgl_renderer"),
            "canvas_hash": web.get("canvas_hash"),
        },
        "native_webview": {
            "build_fingerprint": native.get("build_fingerprint"),
            "device_model": native.get("device_model"),
            "webview_provider_package": webview.get("webview_provider_package"),
            "webview_provider_version": webview.get("webview_provider_version"),
            "app_package_name": webview.get("app_package_name"),
            "installer_package": webview.get("installer_package"),
            "is_debuggable": webview.get("is_debuggable"),
            "is_cleartext_traffic_permitted": webview.get("is_cleartext_traffic_permitted"),
            "jsbridge_injected": webview.get("jsbridge_injected"),
        },
        "webview_web": {
            "webview_provider_version": webview.get("webview_provider_version"),
            "system_http_agent": webview.get("system_http_agent"),
            "user_agent": web.get("user_agent"),
            "platform": web.get("platform"),
            "max_touch_points": web.get("max_touch_points"),
        },
        "tri_layer": {
            "device_model": native.get("device_model"),
            "sensor_total_count": native.get("sensor_total_count"),
            "jsbridge_injected": webview.get("jsbridge_injected"),
            "webview_provider_version": webview.get("webview_provider_version"),
            "user_agent": web.get("user_agent"),
            "platform": web.get("platform"),
            "webgl_renderer": web.get("webgl_renderer"),
        },
        "physical_runtime": {
            "total_memory_gb": native.get("total_memory_gb"),
            "avail_memory_gb": native.get("avail_memory_gb"),
            "is_low_memory": native.get("is_low_memory"),
            "battery_level_pct": native.get("battery_level_pct"),
            "battery_temp_celsius": native.get("battery_temp_celsius"),
            "battery_voltage_mv": native.get("battery_voltage_mv"),
            "is_charging": native.get("is_charging"),
            "uptime_ms": native.get("uptime_ms"),
            "sensor_total_count": native.get("sensor_total_count"),
            "has_accelerometer": native.get("has_accelerometer"),
            "has_gyroscope": native.get("has_gyroscope"),
            "has_magnetic_field": native.get("has_magnetic_field"),
            "has_light_sensor": native.get("has_light_sensor"),
            "has_pressure_sensor": native.get("has_pressure_sensor"),
            "has_proximity_sensor": native.get("has_proximity_sensor"),
            "hardware_concurrency": web.get("hardware_concurrency"),
            "device_memory": web.get("device_memory"),
            "compute_task_time_ms": web.get("compute_task_time_ms"),
            "webgl_extensions_count": web.get("webgl_extensions_count"),
        },
        "attack_scenario": {
            "device_model": native.get("device_model"),
            "device_board": native.get("device_board"),
            "device_hardware": native.get("device_hardware"),
            "cpu_abi": native.get("cpu_abi"),
            "build_fingerprint": native.get("build_fingerprint"),
            "sensor_total_count": native.get("sensor_total_count"),
            "is_adb_enabled": native.get("is_adb_enabled"),
            "battery_level_pct": native.get("battery_level_pct"),
            "installer_package": webview.get("installer_package"),
            "is_debuggable": webview.get("is_debuggable"),
            "is_cleartext_traffic_permitted": webview.get("is_cleartext_traffic_permitted"),
            "jsbridge_injected": webview.get("jsbridge_injected"),
            "user_agent": web.get("user_agent"),
            "platform": web.get("platform"),
            "timezone_offset": web.get("timezone_offset"),
            "webgl_renderer": web.get("webgl_renderer"),
            "max_touch_points": web.get("max_touch_points"),
        },
    }


def metadata_for_row(row: dict[str, Any], row_index: int) -> dict[str, Any]:
    identity = stable_identity(row)
    stable_key = digest(identity, length=16)
    stype = identity["source_type"]
    target = get(row, "llm_label.risk_score")
    payload = evidence_payload(row)
    return {
        "row_index": row_index,
        "evidence_id": f"orig-{row_index}",
        "base_row_index": row_index,
        "session_id": row.get("session_id", ""),
        "source_type": stype,
        "stable_device_key": stable_key,
        "group_id": f"{stype}::{stable_key}",
        "teacher_score": target,
        "teacher_band": score_band(target),
        "rule_family": rule_family(row),
        "evidence_hash": digest(payload, length=16),
        "is_augmented": False,
        "augmentation_id": "",
        "prompt_payload": payload,
    }


def perturb_value(value: Any, spec: dict[str, Any], rng: random.Random) -> Any:
    if value is None:
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value

    mode = spec["mode"]
    if mode == "multiplier":
        new_value = numeric * rng.uniform(float(spec["low"]), float(spec["high"]))
    elif mode == "add_int":
        new_value = numeric + rng.randint(int(spec["low"]), int(spec["high"]))
    elif mode == "add_float":
        new_value = numeric + rng.uniform(float(spec["low"]), float(spec["high"]))
    else:
        return value

    if "min" in spec:
        new_value = max(float(spec["min"]), new_value)
    if "max" in spec:
        new_value = min(float(spec["max"]), new_value)
    if mode == "add_int" or isinstance(value, int):
        return int(round(new_value))
    return round(new_value, int(spec.get("digits", 4)))


def perturb_row(row: dict[str, Any], row_index: int, augmentation_id: int) -> dict[str, Any]:
    rng = random.Random(RANDOM_STATE + row_index * 101 + augmentation_id)
    perturbed = copy.deepcopy(row)
    for path, spec in RUNTIME_PERTURBATIONS.items():
        set_path(perturbed, path, perturb_value(get(perturbed, path), spec, rng))
    return perturbed


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def choose_holdout_indices(row_count: int) -> set[int]:
    indices = list(range(row_count))
    _, test_idx = train_test_split(indices, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    return set(int(i) for i in test_idx)


def build_targeted_sample_rows(
    metadata_rows: list[dict[str, Any]],
    holdout_indices: set[int],
    per_family: int,
) -> list[dict[str, Any]]:
    rows_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in metadata_rows:
        if item["row_index"] in holdout_indices:
            rows_by_family[item["rule_family"]].append(item)

    selected = []
    for family in sorted(rows_by_family):
        family_rows = sorted(
            rows_by_family[family],
            key=lambda x: (x["teacher_band"], x["row_index"]),
        )
        for item in family_rows[:per_family]:
            selected.append(
                {
                    "row_index": item["row_index"],
                    "evidence_id": item["evidence_id"],
                    "session_id": item["session_id"],
                    "sample_set": "rule_targeted",
                    "rule_family": family,
                    "teacher_score": item["teacher_score"],
                    "teacher_band": item["teacher_band"],
                    "source_type": item["source_type"],
                    "group_id": item["group_id"],
                }
            )
    return selected


def build_sample_manifest(
    metadata_rows: list[dict[str, Any]],
    holdout_indices: set[int],
    targeted_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targeted_set = {row["row_index"] for row in targeted_rows}
    boundary_scores = {15, 20, 35, 38, 40, 42, 45}
    manifest = []
    for item in metadata_rows:
        row_index = item["row_index"]
        is_holdout = row_index in holdout_indices
        score = item["teacher_score"]
        is_boundary = is_holdout and score in boundary_scores
        manifest.append(
            {
                "row_index": row_index,
                "evidence_id": item["evidence_id"],
                "session_id": item["session_id"],
                "teacher_score": score,
                "teacher_band": item["teacher_band"],
                "source_type": item["source_type"],
                "stable_device_key": item["stable_device_key"],
                "group_id": item["group_id"],
                "group_size": item["group_size"],
                "sample_weight": item["sample_weight"],
                "rule_family": item["rule_family"],
                "evidence_hash": item["evidence_hash"],
                "full_holdout": is_holdout,
                "boundary_candidate": is_boundary,
                "rule_targeted_candidate": row_index in targeted_set,
            }
        )
    return manifest


def write_asset_summary(
    path: Path,
    metadata_rows: list[dict[str, Any]],
    targeted_rows: list[dict[str, Any]],
    augmented_count: int,
    rule_kb: dict[str, Any],
    no_official_kb: dict[str, Any],
) -> None:
    source_counts = Counter(row["source_type"] for row in metadata_rows)
    band_counts = Counter(row["teacher_band"] for row in metadata_rows)
    group_sizes = Counter(row["group_id"] for row in metadata_rows)
    repeated_groups = sum(1 for _, size in group_sizes.items() if size > 1)
    max_group_size = max(group_sizes.values())
    official_rules = sum(1 for rule in rule_kb.get("rules", []) if rule.get("official_knowledge"))
    lines = [
        "# Validation Asset Summary",
        "",
        f"- Original rows: {len(metadata_rows)}",
        f"- Augmented evidence rows: {augmented_count}",
        f"- Stable device groups: {len(group_sizes)}",
        f"- Repeated stable device groups: {repeated_groups}",
        f"- Largest group size: {max_group_size}",
        f"- Current rule KB version: `{rule_kb.get('version')}`",
        f"- K0 rule KB version: `{no_official_kb.get('version')}`",
        f"- Rules with official knowledge in current KB: {official_rules} / {len(rule_kb.get('rules', []))}",
        f"- Targeted pilot rows: {len(targeted_rows)}",
        "",
        "## Source Type Counts",
        "",
    ]
    for key, value in sorted(source_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Teacher Band Counts", ""])
    for key, value in sorted(band_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Generated Files",
            "",
            "- `rule_kb_no_official_ablation.json`",
            "- `group_metadata.csv`",
            "- `validation_sample_manifest.csv`",
            "- `targeted_sample_manifest.csv`",
            "- `llm_group_evidence.jsonl`",
            "- `llm_group_evidence_augmented.jsonl`",
            "- `perturbation_plan.json`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(Path(args.input))
    rule_kb = json.loads(Path(args.rule_kb).read_text(encoding="utf-8"))
    no_official_kb = build_no_official_rule_kb(rule_kb)
    write_json(output_dir / "rule_kb_no_official_ablation.json", no_official_kb)

    metadata_rows = [metadata_for_row(row, idx) for idx, row in enumerate(rows)]
    group_sizes = Counter(item["group_id"] for item in metadata_rows)
    for item in metadata_rows:
        item["group_size"] = group_sizes[item["group_id"]]
        item["sample_weight"] = round(1.0 / group_sizes[item["group_id"]], 8)

    holdout_indices = choose_holdout_indices(len(rows))
    targeted_rows = build_targeted_sample_rows(
        metadata_rows, holdout_indices, args.targeted_per_family
    )
    manifest_rows = build_sample_manifest(metadata_rows, holdout_indices, targeted_rows)

    evidence_rows = []
    metadata_csv_rows = []
    for item in metadata_rows:
        prompt_payload = item.pop("prompt_payload")
        evidence_rows.append({**item, "prompt_payload": prompt_payload})
        metadata_csv_rows.append(item)

    augmented_rows = []
    for row_index, row in enumerate(rows):
        base = metadata_rows[row_index]
        for augmentation_id in range(1, args.augmentations_per_row + 1):
            aug = perturb_row(row, row_index, augmentation_id)
            payload = evidence_payload(aug)
            augmented_rows.append(
                {
                    "row_index": row_index,
                    "evidence_id": f"aug-{row_index}-{augmentation_id}",
                    "base_row_index": row_index,
                    "session_id": row.get("session_id", ""),
                    "source_type": base["source_type"],
                    "stable_device_key": base["stable_device_key"],
                    "group_id": base["group_id"],
                    "group_size": base["group_size"],
                    "sample_weight": base["sample_weight"],
                    "teacher_score": base["teacher_score"],
                    "teacher_band": base["teacher_band"],
                    "rule_family": base["rule_family"],
                    "evidence_hash": digest(payload, length=16),
                    "is_augmented": True,
                    "augmentation_id": augmentation_id,
                    "prompt_payload": payload,
                }
            )

    write_csv(
        output_dir / "group_metadata.csv",
        metadata_csv_rows,
        [
            "row_index",
            "evidence_id",
            "base_row_index",
            "session_id",
            "source_type",
            "stable_device_key",
            "group_id",
            "group_size",
            "sample_weight",
            "teacher_score",
            "teacher_band",
            "rule_family",
            "evidence_hash",
            "is_augmented",
            "augmentation_id",
        ],
    )
    write_csv(
        output_dir / "validation_sample_manifest.csv",
        manifest_rows,
        [
            "row_index",
            "evidence_id",
            "session_id",
            "teacher_score",
            "teacher_band",
            "source_type",
            "stable_device_key",
            "group_id",
            "group_size",
            "sample_weight",
            "rule_family",
            "evidence_hash",
            "full_holdout",
            "boundary_candidate",
            "rule_targeted_candidate",
        ],
    )
    write_csv(
        output_dir / "targeted_sample_manifest.csv",
        targeted_rows,
        [
            "row_index",
            "evidence_id",
            "session_id",
            "sample_set",
            "rule_family",
            "teacher_score",
            "teacher_band",
            "source_type",
            "group_id",
        ],
    )
    write_jsonl(output_dir / "llm_group_evidence.jsonl", evidence_rows)
    write_jsonl(output_dir / "llm_group_evidence_augmented.jsonl", augmented_rows)
    write_json(
        output_dir / "perturbation_plan.json",
        {
            "principle": "Only session runtime fields are perturbed. Stable identity fields and all test folds remain original.",
            "random_state": RANDOM_STATE,
            "augmentations_per_row": args.augmentations_per_row,
            "runtime_perturbations": RUNTIME_PERTURBATIONS,
            "group_score_fields": [f"{name}_score" for name in GROUP_NAMES],
        },
    )
    write_asset_summary(
        output_dir / "ASSET_SUMMARY.md",
        metadata_rows,
        targeted_rows,
        len(augmented_rows),
        rule_kb,
        no_official_kb,
    )

    print(f"Prepared validation assets in {output_dir}")
    print(f"Rows: {len(rows)}; groups: {len(group_sizes)}; augmented: {len(augmented_rows)}")


if __name__ == "__main__":
    main()
