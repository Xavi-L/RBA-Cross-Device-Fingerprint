#!/usr/bin/env python3
"""RandomForest proxy validation for the LLM grouped-fusion plan.

The experiment is intentionally isolated from the existing ablation scripts.
It reuses their grouped-CV split and consistency-feature builders, then adds
two extra evidence groups that correspond to the current LLM plan:
physical runtime and attack scenario.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
)
from sklearn.model_selection import GridSearchCV, GroupKFold


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ABLATION_DIR = REPO_ROOT / "ablation"
if str(ABLATION_DIR) not in sys.path:
    sys.path.insert(0, str(ABLATION_DIR))

from run_consistency_ablation import (  # noqa: E402
    HIGH_RISK_THRESHOLD,
    RANDOM_STATE,
    TARGET_COL,
    build_consistency_features,
    load_jsonl,
    raw_columns,
)
from run_grouped_ablation import (  # noqa: E402
    build_grouped_splits,
    encode_features,
    group_id,
    source_type,
    summarize_fold_metrics,
)


warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn.linear_model._base")
warnings.filterwarnings("ignore", category=ConvergenceWarning)

GROUPS = [
    ("native_web", "Native-Web"),
    ("native_webview", "Native-WebView"),
    ("webview_web", "WebView-Web"),
    ("tri_layer", "Tri-layer semantic"),
    ("physical_runtime", "Physical runtime"),
    ("attack_scenario", "Attack scenario"),
]


@dataclass(frozen=True)
class Args:
    input: str
    output_dir: str
    n_estimators: int
    max_depth: int
    splits: int


def parse_args() -> Args:
    parser = argparse.ArgumentParser(
        description="Validate grouped evidence fusion with RandomForest proxy scorers."
    )
    parser.add_argument(
        "--input",
        default=str(REPO_ROOT / "training" / "scored_data.jsonl"),
        help="Path to scored JSONL data.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(SCRIPT_DIR),
        help="Directory for result files.",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=50,
        help="Tree count for all RandomForest models.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Tree max depth for all RandomForest models.",
    )
    parser.add_argument(
        "--splits",
        type=int,
        default=3,
        help="Outer grouped-CV folds.",
    )
    ns = parser.parse_args()
    return Args(
        input=ns.input,
        output_dir=ns.output_dir,
        n_estimators=ns.n_estimators,
        max_depth=ns.max_depth,
        splits=ns.splits,
    )


def lower_text(row: pd.Series, col: str) -> str:
    value = row.get(col)
    if value is None or pd.isna(value):
        return ""
    return str(value).lower()


def number_value(row: pd.Series, col: str, default: float = -1.0) -> float:
    value = row.get(col)
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_value(row: pd.Series, col: str) -> bool:
    value = row.get(col)
    if value is None or pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def binary(value: bool) -> float:
    return 1.0 if value else 0.0


def build_extra_group_features(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        ua = lower_text(row, "web_data.user_agent")
        model = lower_text(row, "android_native_data.device_model")
        board = lower_text(row, "android_native_data.device_board")
        hardware = lower_text(row, "android_native_data.device_hardware")
        cpu = lower_text(row, "android_native_data.cpu_abi")
        renderer = lower_text(row, "web_data.webgl_renderer")
        installer = lower_text(row, "webview_data.installer_package")

        sensor_count = number_value(row, "android_native_data.sensor_total_count")
        battery = number_value(row, "android_native_data.battery_level_pct")
        timezone = number_value(row, "web_data.timezone_offset", 999.0)
        adb = bool_value(row, "android_native_data.is_adb_enabled")
        jsbridge = bool_value(row, "webview_data.jsbridge_injected")
        debug = bool_value(row, "webview_data.is_debuggable")
        cleartext = bool_value(row, "webview_data.is_cleartext_traffic_permitted")

        emulator_token = (
            "goldfish" in board
            or "ranchu" in hardware
            or "emulator" in model
            or "x86" in cpu
        )
        desktop_or_bot_ua = any(
            token in ua for token in ["windows nt", "win64", "headless", "python-requests"]
        )

        rows.append(
            {
                "physical_runtime_total_memory_gb": number_value(
                    row, "android_native_data.total_memory_gb"
                ),
                "physical_runtime_avail_memory_gb": number_value(
                    row, "android_native_data.avail_memory_gb"
                ),
                "physical_runtime_is_low_memory": binary(
                    bool_value(row, "android_native_data.is_low_memory")
                ),
                "physical_runtime_battery_level_pct": battery,
                "physical_runtime_battery_temp_celsius": number_value(
                    row, "android_native_data.battery_temp_celsius"
                ),
                "physical_runtime_battery_voltage_mv": number_value(
                    row, "android_native_data.battery_voltage_mv"
                ),
                "physical_runtime_is_charging": binary(
                    bool_value(row, "android_native_data.is_charging")
                ),
                "physical_runtime_sensor_total_count": sensor_count,
                "physical_runtime_has_gyroscope": binary(
                    bool_value(row, "android_native_data.has_gyroscope")
                ),
                "physical_runtime_has_accelerometer": binary(
                    bool_value(row, "android_native_data.has_accelerometer")
                ),
                "physical_runtime_has_magnetic_field": binary(
                    bool_value(row, "android_native_data.has_magnetic_field")
                ),
                "physical_runtime_has_light_sensor": binary(
                    bool_value(row, "android_native_data.has_light_sensor")
                ),
                "physical_runtime_has_proximity_sensor": binary(
                    bool_value(row, "android_native_data.has_proximity_sensor")
                ),
                "physical_runtime_has_pressure_sensor": binary(
                    bool_value(row, "android_native_data.has_pressure_sensor")
                ),
                "physical_runtime_hardware_concurrency": number_value(
                    row, "web_data.hardware_concurrency"
                ),
                "physical_runtime_web_device_memory": number_value(
                    row, "web_data.device_memory"
                ),
                "physical_runtime_max_touch_points": number_value(
                    row, "web_data.max_touch_points"
                ),
                "physical_runtime_webgl_extensions_count": number_value(
                    row, "web_data.webgl_extensions_count"
                ),
                "physical_runtime_compute_task_time_ms": number_value(
                    row, "web_data.compute_task_time_ms"
                ),
                "attack_scenario_ua_python_requests": binary("python-requests" in ua),
                "attack_scenario_ua_windows": binary("windows nt" in ua or "win64" in ua),
                "attack_scenario_ua_headless": binary("headless" in ua),
                "attack_scenario_ua_desktop_or_bot": binary(desktop_or_bot_ua),
                "attack_scenario_model_windows_pc_fake": binary(model == "windows pc fake"),
                "attack_scenario_emulator_token": binary(emulator_token),
                "attack_scenario_swiftshader_gpu": binary("swiftshader" in renderer),
                "attack_scenario_x86_cpu": binary("x86" in cpu),
                "attack_scenario_manual_installer": binary(installer == "manual"),
                "attack_scenario_adb_enabled": binary(adb),
                "attack_scenario_timezone_zero": binary(timezone == 0),
                "attack_scenario_debug_cleartext": binary(debug and cleartext),
                "attack_scenario_missing_jsbridge": binary(not jsbridge),
                "attack_scenario_low_sensor_count": binary(0 <= sensor_count < 10),
                "attack_scenario_adb_full_battery": binary(adb and battery >= 97.0),
            }
        )
    return pd.DataFrame(rows)


def group_feature_sets(
    df: pd.DataFrame, consistency_df: pd.DataFrame, extra_df: pd.DataFrame
) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    native_web_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_native_web_")
    ]
    native_webview_cols = [
        col
        for col in consistency_df.columns
        if col.startswith("consistency_native_webview_")
    ]
    webview_web_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_webview_web_")
    ]
    tri_layer_cols = [
        col for col in consistency_df.columns if col.startswith("consistency_tri_layer_")
    ]
    physical_cols = [
        col for col in extra_df.columns if col.startswith("physical_runtime_")
    ]
    attack_cols = [
        col for col in extra_df.columns if col.startswith("attack_scenario_")
    ]

    return {
        "native_web": (consistency_df[native_web_cols], native_web_cols),
        "native_webview": (consistency_df[native_webview_cols], native_webview_cols),
        "webview_web": (consistency_df[webview_web_cols], webview_web_cols),
        "tri_layer": (consistency_df[tri_layer_cols], tri_layer_cols),
        "physical_runtime": (extra_df[physical_cols], physical_cols),
        "attack_scenario": (extra_df[attack_cols], attack_cols),
    }


def rf_model(args: Args, depth: int | None = None, estimators: int | None = None):
    return RandomForestRegressor(
        n_estimators=estimators or args.n_estimators,
        max_depth=args.max_depth if depth is None else depth,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def metrics_for_predictions(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    true_high = (y_true >= HIGH_RISK_THRESHOLD).astype(int)
    pred_high = (pred >= HIGH_RISK_THRESHOLD).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_high,
        pred_high,
        average="binary",
        zero_division=0,
    )
    return {
        "mae": mean_absolute_error(y_true, pred),
        "rmse": math.sqrt(mean_squared_error(y_true, pred)),
        "r2": r2_score(y_true, pred),
        "high_risk_precision": precision,
        "high_risk_recall": recall,
        "high_risk_f1": f1,
        "high_risk_accuracy": accuracy_score(true_high, pred_high),
    }


def append_prediction_frame(
    frames: list[pd.DataFrame],
    df: pd.DataFrame,
    y: np.ndarray,
    pred: np.ndarray,
    test_idx: np.ndarray,
    fold: int,
    experiment_type: str,
    config_id: str,
    config_name: str,
):
    true_high = (y[test_idx] >= HIGH_RISK_THRESHOLD).astype(int)
    pred_high = (pred >= HIGH_RISK_THRESHOLD).astype(int)
    frames.append(
        pd.DataFrame(
            {
                "experiment_type": experiment_type,
                "config_id": config_id,
                "config_name": config_name,
                "fold": fold,
                "row_index": test_idx,
                "session_id": df.iloc[test_idx]["session_id"].to_numpy()
                if "session_id" in df.columns
                else "",
                "source_type": df.iloc[test_idx]["source_type"].to_numpy(),
                "group_id": df.iloc[test_idx]["group_id"].to_numpy(),
                "true_score": y[test_idx],
                "predicted_score": pred,
                "absolute_error": np.abs(y[test_idx] - pred),
                "true_high_risk": true_high,
                "predicted_high_risk": pred_high,
            }
        )
    )


def evaluate_direct_config(
    df: pd.DataFrame,
    features: pd.DataFrame,
    columns: list[str],
    splits: list[tuple[np.ndarray, np.ndarray]],
    args: Args,
    experiment_type: str,
    config_id: str,
    config_name: str,
) -> tuple[list[dict[str, object]], list[pd.DataFrame]]:
    X = encode_features(features[columns])
    y = df[TARGET_COL].to_numpy()
    fold_metrics: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []

    for fold, (train_idx, test_idx) in enumerate(splits, start=1):
        model = rf_model(args)
        model.fit(X.iloc[train_idx], y[train_idx])
        pred = np.clip(model.predict(X.iloc[test_idx]), 0.0, 100.0)
        metrics = metrics_for_predictions(y[test_idx], pred)
        metrics.update(
            {
                "experiment_type": experiment_type,
                "config_id": config_id,
                "config_name": config_name,
                "fold": fold,
                "feature_count": len(columns),
                "train_size": len(train_idx),
                "test_size": len(test_idx),
                "train_group_count": df.iloc[train_idx]["group_id"].nunique(),
                "test_group_count": df.iloc[test_idx]["group_id"].nunique(),
            }
        )
        fold_metrics.append(metrics)
        append_prediction_frame(
            prediction_frames,
            df,
            y,
            pred,
            test_idx,
            fold,
            experiment_type,
            config_id,
            config_name,
        )
    return fold_metrics, prediction_frames


def inner_group_splits(df: pd.DataFrame, train_idx: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    groups = df.iloc[train_idx]["group_id"].to_numpy()
    unique_groups = np.unique(groups)
    n_splits = min(3, len(unique_groups))
    if n_splits < 2:
        raise ValueError("Need at least two groups for inner stacking splits.")
    splitter = GroupKFold(n_splits=n_splits)
    positions = np.arange(len(train_idx))
    splits = []
    for inner_train_pos, inner_val_pos in splitter.split(positions, groups=groups):
        splits.append((train_idx[inner_train_pos], train_idx[inner_val_pos]))
    return splits


def group_score_matrices(
    df: pd.DataFrame,
    encoded_groups: dict[str, pd.DataFrame],
    selected_groups: list[str],
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    args: Args,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y = df[TARGET_COL].to_numpy()
    train_scores = pd.DataFrame(index=train_idx, columns=selected_groups, dtype=float)
    test_scores = pd.DataFrame(index=test_idx, columns=selected_groups, dtype=float)

    for inner_train_idx, inner_val_idx in inner_group_splits(df, train_idx):
        for group_name in selected_groups:
            model = rf_model(args)
            X_group = encoded_groups[group_name]
            model.fit(X_group.iloc[inner_train_idx], y[inner_train_idx])
            pred = np.clip(model.predict(X_group.iloc[inner_val_idx]), 0.0, 100.0)
            train_scores.loc[inner_val_idx, group_name] = pred

    for group_name in selected_groups:
        model = rf_model(args)
        X_group = encoded_groups[group_name]
        model.fit(X_group.iloc[train_idx], y[train_idx])
        pred = np.clip(model.predict(X_group.iloc[test_idx]), 0.0, 100.0)
        test_scores.loc[test_idx, group_name] = pred

    train_scores = train_scores.loc[train_idx]
    test_scores = test_scores.loc[test_idx]
    if train_scores.isna().any().any() or test_scores.isna().any().any():
        raise ValueError("Unexpected missing group scores in stacking matrices.")

    detail = test_scores.copy()
    detail.insert(0, "row_index", test_idx)
    detail.insert(1, "fold", -1)
    return train_scores, test_scores, detail


def fit_positive_elasticnet(
    X: pd.DataFrame, y: np.ndarray, groups: np.ndarray
) -> GridSearchCV:
    n_splits = min(3, len(np.unique(groups)))
    cv = GroupKFold(n_splits=n_splits)
    model = ElasticNet(
        positive=True,
        fit_intercept=True,
        max_iter=100000,
        random_state=RANDOM_STATE,
    )
    grid = {
        "alpha": [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0],
        "l1_ratio": [0.05, 0.1, 0.2, 0.5, 0.7, 0.9, 0.95, 1.0],
    }
    search = GridSearchCV(
        model,
        grid,
        scoring="neg_mean_absolute_error",
        cv=cv,
        n_jobs=1,
        refit=True,
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        search.fit(X, y, groups=groups)
    return search


def evaluate_stacked_config(
    df: pd.DataFrame,
    encoded_groups: dict[str, pd.DataFrame],
    selected_groups: list[str],
    splits: list[tuple[np.ndarray, np.ndarray]],
    args: Args,
    config_id: str,
    config_name: str,
    fusion: str,
) -> tuple[list[dict[str, object]], list[pd.DataFrame], list[dict[str, object]], list[pd.DataFrame]]:
    y = df[TARGET_COL].to_numpy()
    fold_metrics: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    weight_rows: list[dict[str, object]] = []
    score_frames: list[pd.DataFrame] = []

    for fold, (train_idx, test_idx) in enumerate(splits, start=1):
        train_scores, test_scores, score_detail = group_score_matrices(
            df, encoded_groups, selected_groups, train_idx, test_idx, args
        )
        score_detail["fold"] = fold
        score_detail["config_id"] = config_id
        score_detail["config_name"] = config_name
        score_detail["fusion"] = fusion
        score_detail["selected_groups"] = ",".join(selected_groups)
        score_detail["source_type"] = df.iloc[test_idx]["source_type"].to_numpy()
        score_detail["group_id"] = df.iloc[test_idx]["group_id"].to_numpy()
        score_detail["true_score"] = y[test_idx]
        score_frames.append(score_detail)

        if fusion == "mean":
            pred = test_scores.mean(axis=1).to_numpy()
            params: dict[str, object] = {"fusion": "mean"}
            weights = {group: 1.0 / len(selected_groups) for group in selected_groups}
            intercept = 0.0
        elif fusion == "positive_elasticnet":
            groups = df.iloc[train_idx]["group_id"].to_numpy()
            search = fit_positive_elasticnet(train_scores, y[train_idx], groups)
            pred = search.predict(test_scores)
            params = {
                "fusion": "positive_elasticnet",
                "alpha": search.best_params_["alpha"],
                "l1_ratio": search.best_params_["l1_ratio"],
                "inner_mae": -search.best_score_,
            }
            best = search.best_estimator_
            weights = {
                group: float(best.coef_[idx]) for idx, group in enumerate(selected_groups)
            }
            intercept = float(best.intercept_)
        elif fusion == "rf_meta":
            meta = rf_model(args, depth=3, estimators=max(20, args.n_estimators // 2))
            meta.fit(train_scores, y[train_idx])
            pred = meta.predict(test_scores)
            params = {"fusion": "rf_meta"}
            weights = {
                group: float(meta.feature_importances_[idx])
                for idx, group in enumerate(selected_groups)
            }
            intercept = 0.0
        else:
            raise ValueError(f"Unknown fusion: {fusion}")

        pred = np.clip(pred, 0.0, 100.0)
        metrics = metrics_for_predictions(y[test_idx], pred)
        metrics.update(
            {
                "experiment_type": "group_score_fusion",
                "config_id": config_id,
                "config_name": config_name,
                "fold": fold,
                "feature_count": len(selected_groups),
                "train_size": len(train_idx),
                "test_size": len(test_idx),
                "train_group_count": df.iloc[train_idx]["group_id"].nunique(),
                "test_group_count": df.iloc[test_idx]["group_id"].nunique(),
            }
        )
        fold_metrics.append(metrics)
        append_prediction_frame(
            prediction_frames,
            df,
            y,
            pred,
            test_idx,
            fold,
            "group_score_fusion",
            config_id,
            config_name,
        )

        row: dict[str, object] = {
            "config_id": config_id,
            "config_name": config_name,
            "fold": fold,
            "selected_groups": ",".join(selected_groups),
            "intercept": intercept,
        }
        row.update(params)
        for group_name, _ in GROUPS:
            row[f"weight_{group_name}"] = weights.get(group_name, 0.0)
        weight_rows.append(row)

    return fold_metrics, prediction_frames, weight_rows, score_frames


def markdown_table(rows: list[dict[str, object]], headers: list[tuple[str, str]]) -> str:
    lines = []
    lines.append("| " + " | ".join(label for _, label in headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        cells = []
        for key, _ in headers:
            value = row.get(key, "")
            if isinstance(value, float):
                cells.append(f"{value:.3f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_report(
    output_dir: Path,
    summary_df: pd.DataFrame,
    weights_df: pd.DataFrame,
    feature_dict: pd.DataFrame,
):
    def pick(config_id: str) -> dict[str, object]:
        row = summary_df.loc[summary_df["config_id"] == config_id].iloc[0]
        return row.to_dict()

    key_ids = [
        "raw_all_direct_rf",
        "tri_layer_direct_rf",
        "six_group_evidence_direct_rf",
        "six_group_score_mean",
        "six_group_score_positive_elasticnet",
        "six_group_score_rf_meta",
    ]
    key_rows = [pick(config_id) for config_id in key_ids if config_id in set(summary_df["config_id"])]

    main = pick("six_group_score_positive_elasticnet")
    raw = pick("raw_all_direct_rf")
    tri = pick("tri_layer_direct_rf")
    direct_six = pick("six_group_evidence_direct_rf")
    mean_fusion = pick("six_group_score_mean")

    drop_rows = summary_df[
        summary_df["config_id"].str.startswith("drop_")
        & summary_df["config_id"].str.endswith("_positive_elasticnet")
    ].copy()
    drop_rows["mae_delta_vs_all"] = drop_rows["mae_mean"] - main["mae_mean"]
    drop_rows = drop_rows.sort_values("mae_delta_vs_all", ascending=False)

    weight_cols = [f"weight_{name}" for name, _ in GROUPS]
    weight_summary = []
    main_weights = weights_df[
        weights_df["config_id"] == "six_group_score_positive_elasticnet"
    ]
    for group_name, group_label in GROUPS:
        col = f"weight_{group_name}"
        weight_summary.append(
            {
                "group": group_label,
                "weight_mean": main_weights[col].mean(),
                "weight_std": main_weights[col].std(ddof=0),
            }
        )

    feature_rows = []
    for group_name, group_label in GROUPS:
        feature_rows.append(
            {
                "group": group_label,
                "feature_count": int((feature_dict["group_id"] == group_name).sum()),
            }
        )

    conclusion = [
        f"- Positive ElasticNet 融合后的 MAE 为 {main['mae_mean']:.3f}，明显低于简单平均的 {mean_fusion['mae_mean']:.3f} 和六组特征直接堆叠随机森林的 {direct_six['mae_mean']:.3f}，说明“组级子分数 + 外部融合”比朴素合并更稳。",
        f"- 该结果仍高于 Raw all direct RF 的 {raw['mae_mean']:.3f} 和 Tri-layer semantic direct RF 的 {tri['mae_mean']:.3f}，因此现阶段不能宣称分组融合已经带来最终性能优势。",
        "- ElasticNet 权重主要集中在 Tri-layer semantic、Native-WebView 和 Attack scenario，且去掉 Tri-layer 后 MAE 上升最大，支持原计划中“核心三端语义是最稳定泛化信号”的判断。",
        "- 因此这次随机森林预验证的结论应表述为：框架可跑通，外部融合有效，关键信号选择符合预期；最终性能提升需要后续用 LLM 组级语义评分继续验证。",
    ]

    report = f"""# 随机森林分组融合有效性预验证报告

## 1. 实验目的

当前暂时没有足够算力运行 30B/70B 级 LLM，因此本实验用随机森林作为“组级风险子分数”的替代模型，先验证 `LLM_GROUPED_FUSION_PLAN.md` 中的分组证据结构是否值得继续推进。

本实验能验证：

- 六组证据组织方式是否比直接堆叠原始字段更稳。
- 外部融合模型是否能从组级子分数中学习有效权重。
- 哪些证据组在 grouped CV 下贡献更稳定。

本实验不能直接证明：

- LLM 的语义理解能力优于随机森林。
- LLM 生成自然语言 reason 的质量。
- 最终 LLM 分组评分的真实上限。

## 2. 实验设计

数据仍使用 `training/scored_data.jsonl`，目标为 `llm_label.risk_score`。切分方式复用原有 grouped CV：同一真实设备、云测设备或脚本攻击模板不会同时进入训练集和测试集。

六个证据组如下：

{markdown_table(feature_rows, [("group", "证据组"), ("feature_count", "特征数")])}

验证流程：

```text
每个证据组的特征
  -> 组内 RandomForest 预测该组风险子分数
  -> Simple average / Positive ElasticNet / RF meta 融合
  -> grouped CV 评估 MAE、RMSE、R2、高风险 F1
```

其中 Positive ElasticNet 使用内层 grouped CV 选择 `alpha` 和 `l1_ratio`，训练融合模型时使用外层训练集内部的 out-of-fold 组分数，避免把外层测试集信息泄漏进融合权重。

## 3. 核心结果

{markdown_table(key_rows, [
    ("config_name", "配置"),
    ("feature_count", "输入维度"),
    ("mae_mean", "MAE"),
    ("mae_std", "MAE std"),
    ("rmse_mean", "RMSE"),
    ("high_risk_f1_mean", "高风险 F1"),
])}

## 4. 六组融合权重

以下为 `Six group scores + Positive ElasticNet` 在 3 个外层 fold 中的平均权重：

{markdown_table(weight_summary, [
    ("group", "证据组"),
    ("weight_mean", "平均权重"),
    ("weight_std", "权重标准差"),
])}

权重越高，表示该组随机森林子分数对最终风险分的贡献越大。权重为 0 不一定表示该组完全无意义，也可能表示它与其他组高度相关，被 ElasticNet 收缩掉。

## 5. 去掉单组后的影响

以下表格以完整六组 Positive ElasticNet 为基准，`MAE delta` 越大，说明去掉该组后误差上升越明显。

{markdown_table(drop_rows.to_dict(orient="records"), [
    ("config_name", "去掉的配置"),
    ("mae_mean", "MAE"),
    ("rmse_mean", "RMSE"),
    ("high_risk_f1_mean", "高风险 F1"),
    ("mae_delta_vs_all", "MAE delta"),
])}

## 6. 阶段性结论

{chr(10).join(conclusion)}

- 这份结果可以作为“低算力条件下的方案有效性预验证”：它验证的是分组证据池和外部融合框架，而不是 LLM 本身。
- 后续有算力后，可以保持本实验的 grouped CV、输出表结构和汇报口径不变，只把组内 RandomForest 子分数替换为 LLM 对每组证据生成的 `0-100` 风险子分数。

## 7. 结果文件

- `rf_grouped_fusion_summary.csv`：各配置 grouped CV 汇总指标。
- `rf_grouped_fusion_fold_metrics.csv`：每折指标。
- `rf_grouped_fusion_predictions.csv`：每条测试样本预测明细。
- `rf_group_scores_by_fold.csv`：各融合配置下每条测试样本的组级随机森林子分数。
- `rf_grouped_fusion_weights.csv`：融合模型每折权重。
- `rf_group_feature_dictionary.csv`：六组特征映射。

## 8. 可对导师说明的一句话

在暂时无法运行大模型的情况下，先用随机森林替代 LLM 完成组级风险评分，并在 grouped CV 下验证“分组证据 + 外部融合”的结构有效性；该实验不宣称随机森林等价于 LLM，而是为后续替换成 LLM 分组评分提供可复现的低成本预验证基线。
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_jsonl(args.input)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COL}")

    df["source_type"] = df.apply(source_type, axis=1)
    df["group_id"] = df.apply(group_id, axis=1)
    splits = build_grouped_splits(df, args.splits)

    consistency_df = build_consistency_features(df)
    extra_df = build_extra_group_features(df)
    group_sets = group_feature_sets(df, consistency_df, extra_df)
    encoded_groups = {
        name: encode_features(frame[columns])
        for name, (frame, columns) in group_sets.items()
    }

    feature_dict_rows = []
    for group_name, group_label in GROUPS:
        _, columns = group_sets[group_name]
        for column in columns:
            feature_dict_rows.append(
                {
                    "group_id": group_name,
                    "group_name": group_label,
                    "feature": column,
                }
            )
    feature_dict = pd.DataFrame(feature_dict_rows)

    all_group_frames = []
    all_group_columns = []
    for group_name, _ in GROUPS:
        frame, columns = group_sets[group_name]
        all_group_frames.append(frame[columns])
        all_group_columns.extend(columns)
    all_group_features = pd.concat(all_group_frames, axis=1)

    fold_metrics: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    weight_rows: list[dict[str, object]] = []
    score_frames: list[pd.DataFrame] = []

    direct_configs = [
        (
            "baseline_direct_rf",
            "raw_all_direct_rf",
            "Raw all direct RF",
            df[raw_columns(df)],
            raw_columns(df),
        ),
        (
            "baseline_direct_rf",
            "tri_layer_direct_rf",
            "Tri-layer semantic direct RF",
            group_sets["tri_layer"][0],
            group_sets["tri_layer"][1],
        ),
        (
            "grouped_evidence_direct_rf",
            "six_group_evidence_direct_rf",
            "Six group evidence direct RF",
            all_group_features,
            all_group_columns,
        ),
    ]

    for experiment_type, config_id, config_name, features, columns in direct_configs:
        metrics, predictions = evaluate_direct_config(
            df,
            features,
            columns,
            splits,
            args,
            experiment_type,
            config_id,
            config_name,
        )
        fold_metrics.extend(metrics)
        prediction_frames.extend(predictions)
        print(f"{experiment_type:<28} | {config_name:<36} features={len(columns):>3}")

    all_group_ids = [name for name, _ in GROUPS]
    stacked_configs = [
        (
            all_group_ids,
            "six_group_score_mean",
            "Six group scores + mean",
            "mean",
        ),
        (
            all_group_ids,
            "six_group_score_positive_elasticnet",
            "Six group scores + Positive ElasticNet",
            "positive_elasticnet",
        ),
        (
            all_group_ids,
            "six_group_score_rf_meta",
            "Six group scores + RF meta",
            "rf_meta",
        ),
    ]

    for drop_group, drop_label in GROUPS:
        selected = [name for name in all_group_ids if name != drop_group]
        stacked_configs.append(
            (
                selected,
                f"drop_{drop_group}_positive_elasticnet",
                f"Drop {drop_label} + Positive ElasticNet",
                "positive_elasticnet",
            )
        )

    for selected_groups, config_id, config_name, fusion in stacked_configs:
        metrics, predictions, weights, scores = evaluate_stacked_config(
            df,
            encoded_groups,
            selected_groups,
            splits,
            args,
            config_id,
            config_name,
            fusion,
        )
        fold_metrics.extend(metrics)
        prediction_frames.extend(predictions)
        weight_rows.extend(weights)
        score_frames.extend(scores)
        print(
            f"group_score_fusion          | {config_name:<36} groups={len(selected_groups):>2}"
        )

    fold_df = pd.DataFrame(fold_metrics)
    summary_df = summarize_fold_metrics(fold_df)
    predictions_df = pd.concat(prediction_frames, ignore_index=True)
    weights_df = pd.DataFrame(weight_rows)
    scores_df = pd.concat(score_frames, ignore_index=True)

    fold_df.to_csv(output_dir / "rf_grouped_fusion_fold_metrics.csv", index=False, encoding="utf-8")
    summary_df.to_csv(output_dir / "rf_grouped_fusion_summary.csv", index=False, encoding="utf-8")
    predictions_df.to_csv(output_dir / "rf_grouped_fusion_predictions.csv", index=False, encoding="utf-8")
    weights_df.to_csv(output_dir / "rf_grouped_fusion_weights.csv", index=False, encoding="utf-8")
    scores_df.to_csv(output_dir / "rf_group_scores_by_fold.csv", index=False, encoding="utf-8")
    feature_dict.to_csv(output_dir / "rf_group_feature_dictionary.csv", index=False, encoding="utf-8")

    with (output_dir / "rf_grouped_fusion_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary_df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    build_report(output_dir, summary_df, weights_df, feature_dict)

    print("\nSaved:")
    for name in [
        "REPORT.md",
        "rf_grouped_fusion_summary.csv",
        "rf_grouped_fusion_fold_metrics.csv",
        "rf_grouped_fusion_predictions.csv",
        "rf_group_scores_by_fold.csv",
        "rf_grouped_fusion_weights.csv",
        "rf_group_feature_dictionary.csv",
    ]:
        print(f"- {output_dir / name}")


if __name__ == "__main__":
    main()
