import argparse
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

TARGET_COL = "llm_label.risk_score"
HIGH_RISK_THRESHOLD = 80.0
RANDOM_STATE = 42
TEST_SIZE = 0.2

LAYER_PREFIXES = {
    "native": "android_native_data.",
    "webview": "webview_data.",
    "web": "web_data.",
}

RAW_IDENTITY_AND_ALIGNMENT_COLUMNS = {
    "android_native_data.device_model",
    "android_native_data.device_brand",
    "android_native_data.device_manufacturer",
    "android_native_data.device_product",
    "android_native_data.device_board",
    "android_native_data.device_hardware",
    "android_native_data.os_version",
    "android_native_data.os_api_level",
    "android_native_data.cpu_abi",
    "android_native_data.build_fingerprint",
    "android_native_data.screen_resolution_physical",
    "android_native_data.screen_density_dpi",
    "android_native_data.screen_xdpi",
    "android_native_data.screen_ydpi",
    "android_native_data.screen_scaled_density",
    "webview_data.webview_provider_version",
    "webview_data.webview_provider_version_code",
    "webview_data.system_http_agent",
    "web_data.user_agent",
    "web_data.platform",
    "web_data.screen_resolution_logical",
    "web_data.device_pixel_ratio",
    "web_data.webgl_vendor",
    "web_data.webgl_renderer",
    "web_data.canvas_hash",
}

CONFIGS = [
    ("raw_all", "Raw all", "raw_all"),
    ("raw_clean", "Raw cleaned", "raw_clean"),
    ("consistency_only", "Consistency only", "consistency_all"),
    ("raw_all_plus_consistency", "Raw all + Consistency", "raw_all_plus_consistency"),
    ("raw_clean_plus_consistency", "Raw cleaned + Consistency", "raw_clean_plus_consistency"),
    ("native_web_consistency", "Native-Web consistency", "native_web_consistency"),
    ("native_webview_consistency", "Native-WebView consistency", "native_webview_consistency"),
    ("webview_web_consistency", "WebView-Web consistency", "webview_web_consistency"),
    ("tri_layer_semantic", "Tri-layer semantic", "tri_layer_semantic"),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run RandomForest ablation with explicit cross-layer consistency features."
    )
    parser.add_argument(
        "--input",
        default=str(REPO_ROOT / "training" / "scored_data.jsonl"),
        help="Path to scored JSONL data.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(SCRIPT_DIR),
        help="Directory for consistency ablation results.",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=50,
        help="RandomForest tree count. Default matches training/train_randomforest.py.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="RandomForest max depth. Default matches training/train_randomforest.py.",
    )
    return parser.parse_args()


def load_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return pd.json_normalize(rows)


def text_value(row, col):
    value = row.get(col)
    if value is None or pd.isna(value):
        return ""
    return str(value)


def lower_text(row, col):
    return text_value(row, col).strip().lower()


def number_value(row, col, default=-1.0):
    value = row.get(col)
    if value is None or pd.isna(value):
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_value(row, col):
    value = row.get(col)
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def binary(value):
    if value is None:
        return -1.0
    return 1.0 if value else 0.0


def contains_token(container, token):
    token = (token or "").strip().lower()
    if not token or token in {"unknown", "null", "none"}:
        return False
    return token in container


def parse_resolution(value):
    text = str(value or "").strip().lower()
    match = re.search(r"(\d{2,5})\s*x\s*(\d{2,5})", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_android_version(text):
    text = str(text or "")
    match = re.search(r"Android\s+(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def parse_chrome_major(text):
    text = str(text or "")
    match = re.search(r"(?:Chrome|Chromium)/(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"^\s*(\d{2,4})(?:\.|$)", text)
    if match:
        return int(match.group(1))
    return None


def screen_error(native_res, web_res, dpr):
    if not native_res or not web_res or dpr <= 0:
        return 1.0, 1.0, 1.0, 0.0

    def calc(nw, nh, ww, wh):
        width_error = abs(nw - ww * dpr) / max(nw, 1)
        height_error = abs(nh - wh * dpr) / max(nh, 1)
        max_error = max(width_error, height_error)
        return width_error, height_error, max_error

    w1, h1, m1 = calc(native_res[0], native_res[1], web_res[0], web_res[1])
    w2, h2, m2 = calc(native_res[0], native_res[1], web_res[1], web_res[0])
    width_error, height_error, max_error = (w1, h1, m1) if m1 <= m2 else (w2, h2, m2)
    score = max(0.0, 1.0 - max_error / 0.2)
    return width_error, height_error, max_error, score


def cpu_family(cpu_abi):
    text = str(cpu_abi or "").lower()
    if "arm64" in text or "aarch64" in text:
        return "arm64"
    if "armeabi" in text or "armv7" in text:
        return "arm"
    if "x86" in text or "i686" in text:
        return "x86"
    return "unknown"


def platform_family(platform):
    text = str(platform or "").lower()
    if "aarch64" in text or "armv8" in text or "arm64" in text:
        return "arm64"
    if "arm" in text:
        return "arm"
    if "i686" in text or "x86" in text or "win32" in text or "win64" in text:
        return "x86"
    return "unknown"


def hardware_family(*values):
    text = " ".join(str(v or "").lower() for v in values)
    if any(token in text for token in ["goldfish", "ranchu", "emulator"]):
        return "emulator"
    if any(token in text for token in ["qcom", "qualcomm", "kona", "lahaina", "kalama", "taro", "pineapple", "holi"]):
        return "qualcomm"
    if re.search(r"\bmt\d{4}", text) or re.search(r"\bk\d{4}", text) or "mediatek" in text:
        return "mediatek"
    if "kirin" in text or "huawei" in text or "maleoon" in text:
        return "huawei"
    if "exynos" in text or "s5e" in text or "samsung" in text:
        return "samsung"
    if "unknown" in text:
        return "unknown"
    return "unknown"


def gpu_family(vendor, renderer):
    text = f"{vendor or ''} {renderer or ''}".lower()
    if "swiftshader" in text or "angle (apple" in text or "headless" in text:
        return "software_desktop"
    if "adreno" in text or "qualcomm" in text:
        return "qualcomm"
    if "mali" in text or re.search(r"\barm\b", text):
        return "arm_mali"
    if "maleoon" in text or "huawei" in text:
        return "huawei"
    if "xclipse" in text or "samsung" in text:
        return "samsung"
    if "powervr" in text or "imagination" in text:
        return "powervr"
    return "unknown"


def gpu_match_score(hardware, gpu):
    if "unknown" in {hardware, gpu}:
        return -1.0
    if hardware == "qualcomm" and gpu == "qualcomm":
        return 1.0
    if hardware == "mediatek" and gpu in {"arm_mali", "powervr"}:
        return 0.85
    if hardware == "huawei" and gpu in {"arm_mali", "huawei"}:
        return 0.85
    if hardware == "samsung" and gpu in {"arm_mali", "samsung"}:
        return 0.85
    if hardware == "emulator" and gpu == "software_desktop":
        return 0.6
    if gpu == "software_desktop":
        return 0.0
    return 0.2


def model_ua_strength(row):
    ua = lower_text(row, "web_data.user_agent")
    model = lower_text(row, "android_native_data.device_model")
    product = lower_text(row, "android_native_data.device_product")
    board = lower_text(row, "android_native_data.device_board")
    brand = lower_text(row, "android_native_data.device_brand")
    manufacturer = lower_text(row, "android_native_data.device_manufacturer")
    if not ua:
        return -1.0
    if contains_token(ua, model):
        return 1.0
    if contains_token(ua, product):
        return 0.8
    if contains_token(ua, board):
        return 0.7
    if "android" in ua and (contains_token(ua, brand) or contains_token(ua, manufacturer)):
        return 0.55
    if "android" in ua:
        return 0.35
    return 0.0


def version_match_features(native_version, observed_version):
    if native_version is None or observed_version is None:
        return -1.0, 99.0
    delta = abs(native_version - observed_version)
    return (1.0 if delta == 0 else 0.0), float(delta)


def build_consistency_features(df):
    rows = []
    for _, row in df.iterrows():
        ua = text_value(row, "web_data.user_agent")
        ua_lower = ua.lower()
        system_agent = text_value(row, "webview_data.system_http_agent")

        native_android = parse_android_version(text_value(row, "android_native_data.os_version"))
        ua_android = parse_android_version(ua)
        agent_android = parse_android_version(system_agent)

        native_res = parse_resolution(text_value(row, "android_native_data.screen_resolution_physical"))
        web_res = parse_resolution(text_value(row, "web_data.screen_resolution_logical"))
        dpr = number_value(row, "web_data.device_pixel_ratio", 0.0)
        width_error, height_error, max_error, screen_score = screen_error(native_res, web_res, dpr)

        native_cpu = cpu_family(text_value(row, "android_native_data.cpu_abi"))
        web_platform = platform_family(text_value(row, "web_data.platform"))
        cpu_platform_known = native_cpu != "unknown" and web_platform != "unknown"

        native_hw = hardware_family(
            text_value(row, "android_native_data.device_hardware"),
            text_value(row, "android_native_data.device_board"),
            text_value(row, "android_native_data.device_product"),
            text_value(row, "android_native_data.device_manufacturer"),
        )
        web_gpu = gpu_family(
            text_value(row, "web_data.webgl_vendor"),
            text_value(row, "web_data.webgl_renderer"),
        )
        gpu_score = gpu_match_score(native_hw, web_gpu)

        model_strength = model_ua_strength(row)
        agent_model_strength = 1.0 if contains_token(
            system_agent.lower(),
            lower_text(row, "android_native_data.device_model"),
        ) else 0.0

        webview_provider_major = parse_chrome_major(text_value(row, "webview_data.webview_provider_version"))
        ua_chrome_major = parse_chrome_major(ua)
        chrome_match, chrome_delta = version_match_features(webview_provider_major, ua_chrome_major)

        ua_android_match, ua_android_delta = version_match_features(native_android, ua_android)
        agent_android_match, agent_android_delta = version_match_features(native_android, agent_android)

        jsbridge = bool_value(row, "webview_data.jsbridge_injected")
        adb = bool_value(row, "android_native_data.is_adb_enabled")
        cleartext = bool_value(row, "webview_data.is_cleartext_traffic_permitted")
        debuggable = bool_value(row, "webview_data.is_debuggable")

        installer = lower_text(row, "webview_data.installer_package")
        package_name = lower_text(row, "webview_data.app_package_name")
        timezone = number_value(row, "web_data.timezone_offset", 999.0)
        battery = number_value(row, "android_native_data.battery_level_pct", -1.0)
        sensor_count = number_value(row, "android_native_data.sensor_total_count", -1.0)
        touch_points = number_value(row, "web_data.max_touch_points", -1.0)
        native_memory = number_value(row, "android_native_data.total_memory_gb", -1.0)
        web_memory = number_value(row, "web_data.device_memory", -1.0)

        mobile_ua = "android" in ua_lower and "mobile" in ua_lower
        desktop_or_bot_ua = any(token in ua_lower for token in ["windows nt", "win64", "headless", "python-requests"])
        wv_token = "; wv" in ua_lower or " version/4.0 " in ua_lower
        official_installer = any(token in installer for token in ["packageinstaller", "browser", "vending"])
        manual_installer = installer == "manual"
        package_expected = package_name.startswith("com.example.hybridguard")
        memory_delta = abs(native_memory - web_memory) if native_memory >= 0 and web_memory >= 0 else 99.0
        memory_score = max(0.0, 1.0 - memory_delta / 4.0) if memory_delta != 99.0 else -1.0

        feature_row = {
            # Native-Web: same device surface exposed through OS and browser runtime.
            "consistency_native_web_model_ua_strength": model_strength,
            "consistency_native_web_model_ua_match": 1.0 if model_strength >= 0.8 else 0.0,
            "consistency_native_web_android_version_match": ua_android_match,
            "consistency_native_web_android_version_delta": ua_android_delta,
            "consistency_native_web_screen_width_error_ratio": width_error,
            "consistency_native_web_screen_height_error_ratio": height_error,
            "consistency_native_web_screen_max_error_ratio": max_error,
            "consistency_native_web_screen_score": screen_score,
            "consistency_native_web_screen_consistent_10pct": 1.0 if max_error <= 0.10 else 0.0,
            "consistency_native_web_cpu_platform_match": 1.0 if cpu_platform_known and native_cpu == web_platform else 0.0,
            "consistency_native_web_cpu_platform_known": 1.0 if cpu_platform_known else 0.0,
            "consistency_native_web_gpu_family_score": gpu_score,
            "consistency_native_web_gpu_family_match": 1.0 if gpu_score >= 0.8 else 0.0,
            "consistency_native_web_gpu_software_or_desktop": 1.0 if web_gpu == "software_desktop" else 0.0,
            "consistency_native_web_touch_mobile_match": 1.0 if mobile_ua and touch_points > 0 else 0.0,
            "consistency_native_web_memory_delta_gb": memory_delta,
            "consistency_native_web_memory_score": memory_score,
            "consistency_native_web_desktop_or_bot_ua": 1.0 if desktop_or_bot_ua else 0.0,
            # Native-WebView: App host view of the same OS/device.
            "consistency_native_webview_agent_model_match": agent_model_strength,
            "consistency_native_webview_agent_android_version_match": agent_android_match,
            "consistency_native_webview_agent_android_version_delta": agent_android_delta,
            "consistency_native_webview_bridge_injected": binary(jsbridge),
            "consistency_native_webview_package_expected": 1.0 if package_expected else 0.0,
            "consistency_native_webview_installer_official_like": 1.0 if official_installer else 0.0,
            "consistency_native_webview_installer_manual": 1.0 if manual_installer else 0.0,
            "consistency_native_webview_debug_cleartext_tension": 1.0 if debuggable and cleartext else 0.0,
            # WebView-Web: browser engine exposed by container and JS runtime.
            "consistency_webview_web_chrome_major_match": chrome_match,
            "consistency_webview_web_chrome_major_delta": chrome_delta,
            "consistency_webview_web_ua_has_wv_token": 1.0 if wv_token else 0.0,
            "consistency_webview_web_bridge_mobile_runtime_match": 1.0 if jsbridge and mobile_ua and wv_token else 0.0,
            "consistency_webview_web_non_browser_ua": 1.0 if "python-requests" in ua_lower else 0.0,
            # Tri-layer semantic consistency and known risk-rule alignment.
            "consistency_tri_layer_core_integrity_pass": 1.0 if sensor_count >= 10 and jsbridge else 0.0,
            "consistency_tri_layer_sensor_bridge_fail": 1.0 if sensor_count >= 0 and sensor_count < 10 or jsbridge is False else 0.0,
            "consistency_tri_layer_manual_timezone_or_adb": 1.0 if manual_installer and (timezone == 0 or adb) else 0.0,
            "consistency_tri_layer_adb_full_battery_signal": 1.0 if adb and battery >= 97.0 else 0.0,
            "consistency_tri_layer_official_installer_core_pass": 1.0 if official_installer and sensor_count >= 10 and jsbridge else 0.0,
            "consistency_tri_layer_mean_match_score": np.mean(
                [
                    max(model_strength, 0.0),
                    max(ua_android_match, 0.0),
                    screen_score,
                    max(gpu_score, 0.0),
                    max(chrome_match, 0.0),
                    1.0 if jsbridge else 0.0,
                ]
            ),
        }
        feature_row["consistency_tri_layer_failure_count"] = sum(
            1.0
            for key, value in feature_row.items()
            if key.startswith("consistency_")
            and (
                key.endswith("_match")
                or key.endswith("_pass")
                or key.endswith("_consistent_10pct")
            )
            and value == 0.0
        )
        rows.append(feature_row)
    return pd.DataFrame(rows)


def raw_columns(df):
    prefixes = tuple(LAYER_PREFIXES.values())
    return [col for col in df.columns if col.startswith(prefixes)]


def encode_features(frame):
    X = frame.copy()
    for col in X.columns:
        if X[col].dtype == "object" or X[col].dtype == "bool":
            X[col] = X[col].fillna("Unknown").astype(str)
            X[col] = LabelEncoder().fit_transform(X[col])
        else:
            X[col] = X[col].fillna(-1)
    return X


def feature_set(df, consistency_df, set_name):
    raw_all_cols = raw_columns(df)
    raw_clean_cols = [col for col in raw_all_cols if col not in RAW_IDENTITY_AND_ALIGNMENT_COLUMNS]

    native_web_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_native_web_")
    ]
    native_webview_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_native_webview_")
    ]
    webview_web_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_webview_web_")
    ]
    tri_layer_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_tri_layer_")
    ]
    consistency_cols = native_web_cols + native_webview_cols + webview_web_cols + tri_layer_cols

    if set_name == "raw_all":
        return df[raw_all_cols], raw_all_cols
    if set_name == "raw_clean":
        return df[raw_clean_cols], raw_clean_cols
    if set_name == "consistency_all":
        return consistency_df[consistency_cols], consistency_cols
    if set_name == "raw_all_plus_consistency":
        combined = pd.concat([df[raw_all_cols], consistency_df[consistency_cols]], axis=1)
        return combined, raw_all_cols + consistency_cols
    if set_name == "raw_clean_plus_consistency":
        combined = pd.concat([df[raw_clean_cols], consistency_df[consistency_cols]], axis=1)
        return combined, raw_clean_cols + consistency_cols
    if set_name == "native_web_consistency":
        return consistency_df[native_web_cols], native_web_cols
    if set_name == "native_webview_consistency":
        return consistency_df[native_webview_cols], native_webview_cols
    if set_name == "webview_web_consistency":
        return consistency_df[webview_web_cols], webview_web_cols
    if set_name == "tri_layer_semantic":
        return consistency_df[tri_layer_cols], tri_layer_cols
    raise ValueError(f"Unknown feature set: {set_name}")


def evaluate_config(df, consistency_df, train_idx, test_idx, config_id, config_name, set_name, args):
    features, columns = feature_set(df, consistency_df, set_name)
    if not columns:
        raise ValueError(f"No columns selected for {config_id}")

    X = encode_features(features)
    y = df[TARGET_COL]

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    model = RandomForestRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    true_high = (y_test.to_numpy() >= HIGH_RISK_THRESHOLD).astype(int)
    pred_high = (pred >= HIGH_RISK_THRESHOLD).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_high,
        pred_high,
        average="binary",
        zero_division=0,
    )

    summary = {
        "config_id": config_id,
        "config_name": config_name,
        "feature_set": set_name,
        "feature_count": len(columns),
        "train_size": len(train_idx),
        "test_size": len(test_idx),
        "mae": mean_absolute_error(y_test, pred),
        "rmse": math.sqrt(mean_squared_error(y_test, pred)),
        "r2": r2_score(y_test, pred),
        "high_risk_threshold": HIGH_RISK_THRESHOLD,
        "high_risk_precision": precision,
        "high_risk_recall": recall,
        "high_risk_f1": f1,
        "high_risk_accuracy": accuracy_score(true_high, pred_high),
    }

    predictions = pd.DataFrame(
        {
            "config_id": config_id,
            "config_name": config_name,
            "row_index": test_idx,
            "session_id": df.iloc[test_idx]["session_id"].to_numpy()
            if "session_id" in df.columns
            else "",
            "true_score": y_test.to_numpy(),
            "predicted_score": pred,
            "absolute_error": np.abs(y_test.to_numpy() - pred),
            "true_high_risk": true_high,
            "predicted_high_risk": pred_high,
        }
    )

    importance = pd.DataFrame(
        {
            "config_id": config_id,
            "config_name": config_name,
            "feature": columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    return summary, predictions, importance


def save_plots(summary_df, output_dir):
    os.environ.setdefault("MPLCONFIGDIR", str(output_dir / ".mplconfig"))
    output_dir.mkdir(parents=True, exist_ok=True)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = summary_df["config_name"].tolist()
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x, summary_df["mae"], color="#1f6f8b", label="MAE")
    ax.plot(x, summary_df["rmse"], color="#b13f2a", marker="o", linewidth=2, label="RMSE")
    ax.set_title("Consistency Ablation: Error Metrics")
    ax.set_ylabel("Risk score error")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "consistency_ablation_error_metrics.png", dpi=180)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    bars = ax1.bar(x, summary_df["high_risk_f1"], color="#2f7d4e", label="High-risk F1")
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("High-risk F1")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=30, ha="right")
    ax1.grid(axis="y", alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(x, summary_df["feature_count"], color="#744fa1", marker="s", linewidth=2, label="Feature count")
    ax2.set_ylabel("Feature count")

    ax1.set_title("Consistency Ablation: High-risk Detection and Feature Count")
    handles = [bars, ax2.lines[0]]
    ax1.legend(handles, [h.get_label() for h in handles], loc="lower right")
    fig.tight_layout()
    fig.savefig(output_dir / "consistency_ablation_high_risk_f1.png", dpi=180)
    plt.close(fig)


def save_feature_dictionary(output_dir, columns):
    rows = []
    for col in columns:
        if col.startswith("consistency_native_web_"):
            group = "Native-Web"
        elif col.startswith("consistency_native_webview_"):
            group = "Native-WebView"
        elif col.startswith("consistency_webview_web_"):
            group = "WebView-Web"
        elif col.startswith("consistency_tri_layer_"):
            group = "Tri-layer semantic"
        else:
            group = "Other"
        rows.append({"feature": col, "group": group})
    pd.DataFrame(rows).to_csv(output_dir / "consistency_feature_dictionary.csv", index=False, encoding="utf-8")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_jsonl(args.input)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COL}")

    consistency_df = build_consistency_features(df)
    consistency_export = consistency_df.copy()
    if "session_id" in df.columns:
        consistency_export.insert(0, "session_id", df["session_id"])
    consistency_export.insert(0, "row_index", np.arange(len(df)))
    consistency_export[TARGET_COL] = df[TARGET_COL]
    consistency_export.to_csv(output_dir / "consistency_features.csv", index=False, encoding="utf-8")
    save_feature_dictionary(output_dir, consistency_df.columns)

    indices = np.arange(len(df))
    train_idx, test_idx = train_test_split(
        indices,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    summaries = []
    prediction_frames = []
    importance_frames = []
    for config_id, config_name, set_name in CONFIGS:
        summary, predictions, importance = evaluate_config(
            df, consistency_df, train_idx, test_idx, config_id, config_name, set_name, args
        )
        summaries.append(summary)
        prediction_frames.append(predictions)
        importance_frames.append(importance)
        print(
            f"{config_name:<28} features={summary['feature_count']:>3} "
            f"MAE={summary['mae']:.2f} RMSE={summary['rmse']:.2f} "
            f"F1={summary['high_risk_f1']:.3f}"
        )

    summary_df = pd.DataFrame(summaries)
    predictions_df = pd.concat(prediction_frames, ignore_index=True)
    importance_df = pd.concat(importance_frames, ignore_index=True)

    summary_df.to_csv(output_dir / "consistency_ablation_summary.csv", index=False, encoding="utf-8")
    predictions_df.to_csv(output_dir / "consistency_ablation_predictions.csv", index=False, encoding="utf-8")
    importance_df.to_csv(output_dir / "consistency_feature_importance.csv", index=False, encoding="utf-8")

    top_importance_df = importance_df.groupby("config_id", group_keys=False).head(15)
    top_importance_df.to_csv(output_dir / "consistency_top_feature_importance.csv", index=False, encoding="utf-8")

    with (output_dir / "consistency_ablation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    split_payload = {
        "input": str(Path(args.input).resolve()),
        "row_count": len(df),
        "target": TARGET_COL,
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "train_indices": train_idx.tolist(),
        "test_indices": test_idx.tolist(),
    }
    with (output_dir / "consistency_holdout_split_indices.json").open("w", encoding="utf-8") as f:
        json.dump(split_payload, f, ensure_ascii=False, indent=2)

    save_plots(summary_df, output_dir)

    print("\nSaved:")
    print(f"- {output_dir / 'consistency_features.csv'}")
    print(f"- {output_dir / 'consistency_ablation_summary.csv'}")
    print(f"- {output_dir / 'consistency_ablation_predictions.csv'}")
    print(f"- {output_dir / 'consistency_top_feature_importance.csv'}")
    print(f"- {output_dir / 'consistency_ablation_error_metrics.png'}")
    print(f"- {output_dir / 'consistency_ablation_high_risk_f1.png'}")


if __name__ == "__main__":
    main()
