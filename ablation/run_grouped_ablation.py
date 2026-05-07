import argparse
import hashlib
import json
import math
import os
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
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder

from run_consistency_ablation import (
    CONFIGS as CONSISTENCY_CONFIGS,
    HIGH_RISK_THRESHOLD,
    LAYER_PREFIXES,
    RANDOM_STATE,
    TARGET_COL,
    build_consistency_features,
    feature_set as consistency_feature_set,
    load_jsonl,
    raw_columns,
    save_feature_dictionary,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

N_SPLITS = 3

COARSE_CONFIGS = [
    ("native_only", "Native only", ("native",)),
    ("webview_only", "WebView only", ("webview",)),
    ("web_only", "Web only", ("web",)),
    ("native_webview", "Native + WebView", ("native", "webview")),
    ("native_web", "Native + Web", ("native", "web")),
    ("webview_web", "WebView + Web", ("webview", "web")),
    ("all_three", "Native + WebView + Web", ("native", "webview", "web")),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run grouped cross-validation ablation experiments for HybridGuard."
    )
    parser.add_argument(
        "--input",
        default=str(REPO_ROOT / "training" / "scored_data.jsonl"),
        help="Path to scored JSONL data.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(SCRIPT_DIR),
        help="Directory for grouped ablation results.",
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
    parser.add_argument(
        "--splits",
        type=int,
        default=N_SPLITS,
        help="Number of grouped CV folds. Use 3 by default because script data has three main templates.",
    )
    return parser.parse_args()


def clean(value):
    if value is None or pd.isna(value):
        return "null"
    text = str(value).strip()
    return text if text else "blank"


def row_text(row, col):
    value = row.get(col)
    if value is None or pd.isna(value):
        return ""
    return str(value)


def source_type(row):
    ua = row_text(row, "web_data.user_agent").lower()
    model = row_text(row, "android_native_data.device_model").lower()
    board = row_text(row, "android_native_data.device_board").lower()
    hardware = row_text(row, "android_native_data.device_hardware").lower()
    cpu = row_text(row, "android_native_data.cpu_abi").lower()
    renderer = row_text(row, "web_data.webgl_renderer").lower()
    sensor_count = row.get("android_native_data.sensor_total_count")
    jsbridge = row.get("webview_data.jsbridge_injected")

    script_like = (
        sensor_count is None
        or jsbridge is False
        or "python-requests" in ua
        or "windows nt" in ua
        or "headless" in ua
        or model == "windows pc fake"
        or (sensor_count is not None and sensor_count < 10)
        or "goldfish" in board
        or "ranchu" in hardware
        or "x86" in cpu
        or "swiftshader" in renderer
    )
    if script_like:
        return "script_attack"

    installer = row_text(row, "webview_data.installer_package").lower()
    timezone = row.get("web_data.timezone_offset")
    adb = row.get("android_native_data.is_adb_enabled")
    if installer == "manual" or timezone == 0 or adb is True:
        return "cloud_device"

    return "physical_device"


def script_template(row):
    ua = row_text(row, "web_data.user_agent").lower()
    model = row_text(row, "android_native_data.device_model").lower()
    board = row_text(row, "android_native_data.device_board").lower()
    hardware = row_text(row, "android_native_data.device_hardware").lower()
    sensor_count = row.get("android_native_data.sensor_total_count")
    jsbridge = row.get("webview_data.jsbridge_injected")

    if "python-requests" in ua or jsbridge is False or sensor_count is None:
        return "api_replay"
    if "windows nt" in ua or "headless" in ua or model == "windows pc fake":
        return "headless_pc"
    if "goldfish" in board or "ranchu" in hardware or (sensor_count is not None and sensor_count < 10):
        return "cheap_emulator"
    return "script_other"


def digest(parts):
    text = "|".join(clean(part) for part in parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def group_id(row):
    source = source_type(row)
    if source == "script_attack":
        template = script_template(row)
        return f"{source}::{template}"

    stable_parts = [
        row.get('android_native_data.build_fingerprint'),
        row.get('android_native_data.device_model'),
        row.get('android_native_data.screen_resolution_physical'),
        row.get('web_data.user_agent'),
        row.get('web_data.canvas_hash'),
    ]
    return f"{source}::{digest(stable_parts)}"


def selected_columns(df, layers):
    prefixes = tuple(LAYER_PREFIXES[layer] for layer in layers)
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


def metrics_for_predictions(y_true, pred):
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


def evaluate_cv_config(df, feature_frame, columns, splits, config_id, config_name, experiment_type, args):
    X = encode_features(feature_frame[columns])
    y = df[TARGET_COL].to_numpy()
    fold_metrics = []
    prediction_frames = []

    for fold, (train_idx, test_idx) in enumerate(splits, start=1):
        model = RandomForestRegressor(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        model.fit(X.iloc[train_idx], y[train_idx])
        pred = model.predict(X.iloc[test_idx])
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

        true_high = (y[test_idx] >= HIGH_RISK_THRESHOLD).astype(int)
        pred_high = (pred >= HIGH_RISK_THRESHOLD).astype(int)
        prediction_frames.append(
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

    return fold_metrics, prediction_frames


def summarize_fold_metrics(fold_df):
    metric_cols = [
        "mae",
        "rmse",
        "r2",
        "high_risk_precision",
        "high_risk_recall",
        "high_risk_f1",
        "high_risk_accuracy",
    ]
    rows = []
    for (experiment_type, config_id, config_name), group in fold_df.groupby(
        ["experiment_type", "config_id", "config_name"], sort=False
    ):
        row = {
            "experiment_type": experiment_type,
            "config_id": config_id,
            "config_name": config_name,
            "feature_count": int(group["feature_count"].iloc[0]),
            "folds": len(group),
        }
        for metric in metric_cols:
            row[f"{metric}_mean"] = group[metric].mean()
            row[f"{metric}_std"] = group[metric].std(ddof=0)
        rows.append(row)
    return pd.DataFrame(rows)


def build_group_metadata(df, splits):
    metadata = df[
        [
            "session_id",
            "source_type",
            "group_id",
            "llm_label.risk_score",
            "android_native_data.device_model",
            "webview_data.installer_package",
            "web_data.user_agent",
        ]
    ].copy()
    metadata.insert(0, "row_index", np.arange(len(df)))
    metadata["fold"] = -1
    for fold, (_, test_idx) in enumerate(splits, start=1):
        metadata.loc[test_idx, "fold"] = fold
    return metadata


def fold_distribution(metadata):
    rows = []
    for fold, fold_df in metadata.groupby("fold"):
        for source, source_df in fold_df.groupby("source_type"):
            rows.append(
                {
                    "fold": fold,
                    "source_type": source,
                    "rows": len(source_df),
                    "groups": source_df["group_id"].nunique(),
                    "risk_score_mean": source_df["llm_label.risk_score"].mean(),
                }
            )
    return pd.DataFrame(rows).sort_values(["fold", "source_type"])


def source_group_summary(metadata):
    return (
        metadata.groupby(["source_type", "group_id"], as_index=False)
        .agg(
            rows=("row_index", "count"),
            fold=("fold", "first"),
            risk_score_mean=("llm_label.risk_score", "mean"),
            sample_model=("android_native_data.device_model", "first"),
            sample_installer=("webview_data.installer_package", "first"),
            sample_ua=("web_data.user_agent", "first"),
        )
        .sort_values(["source_type", "rows"], ascending=[True, False])
    )


def build_grouped_splits(df, n_splits):
    script_groups = sorted(df.loc[df["source_type"] == "script_attack", "group_id"].unique())
    if len(script_groups) < n_splits:
        raise ValueError(
            f"Need at least {n_splits} script_attack groups, found {len(script_groups)}."
        )

    non_script_idx = df.index[df["source_type"] != "script_attack"].to_numpy()
    splitter = StratifiedGroupKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    non_script_splits = list(
        splitter.split(
            non_script_idx,
            y=df.iloc[non_script_idx]["source_type"],
            groups=df.iloc[non_script_idx]["group_id"],
        )
    )

    all_indices = np.arange(len(df))
    splits = []
    for fold_index, (_, non_script_test_pos) in enumerate(non_script_splits):
        script_test_group = script_groups[fold_index]
        script_test_idx = df.index[df["group_id"] == script_test_group].to_numpy()
        non_script_test_idx = non_script_idx[non_script_test_pos]
        test_idx = np.sort(np.concatenate([non_script_test_idx, script_test_idx]))
        train_idx = np.setdiff1d(all_indices, test_idx)
        splits.append((train_idx, test_idx))
    return splits


def save_plot(summary_df, output_dir):
    os.environ.setdefault("MPLCONFIGDIR", str(output_dir / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for experiment_type, name in [
        ("coarse_layer", "grouped_coarse_error_metrics.png"),
        ("consistency", "grouped_consistency_error_metrics.png"),
    ]:
        plot_df = summary_df[summary_df["experiment_type"] == experiment_type]
        labels = plot_df["config_name"].tolist()
        x = np.arange(len(labels))
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(x, plot_df["mae_mean"], yerr=plot_df["mae_std"], color="#246b8f", label="MAE mean")
        ax.plot(x, plot_df["rmse_mean"], color="#b13f2a", marker="o", linewidth=2, label="RMSE mean")
        ax.set_title(f"Grouped CV Ablation: {experiment_type}")
        ax.set_ylabel("Risk score error")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.grid(axis="y", alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / name, dpi=180)
        plt.close(fig)


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
    consistency_export = consistency_df.copy()
    consistency_export.insert(0, "group_id", df["group_id"])
    consistency_export.insert(0, "source_type", df["source_type"])
    if "session_id" in df.columns:
        consistency_export.insert(0, "session_id", df["session_id"])
    consistency_export.insert(0, "row_index", np.arange(len(df)))
    consistency_export[TARGET_COL] = df[TARGET_COL]
    consistency_export.to_csv(output_dir / "grouped_consistency_features.csv", index=False, encoding="utf-8")
    save_feature_dictionary(output_dir, consistency_df.columns)

    fold_metrics = []
    prediction_frames = []

    for config_id, config_name, layers in COARSE_CONFIGS:
        columns = selected_columns(df, layers)
        metrics, predictions = evaluate_cv_config(
            df,
            df,
            columns,
            splits,
            config_id,
            config_name,
            "coarse_layer",
            args,
        )
        fold_metrics.extend(metrics)
        prediction_frames.extend(predictions)
        print(f"coarse_layer | {config_name:<28} features={len(columns):>3}")

    for config_id, config_name, set_name in CONSISTENCY_CONFIGS:
        features, columns = consistency_feature_set(df, consistency_df, set_name)
        metrics, predictions = evaluate_cv_config(
            df,
            features,
            columns,
            splits,
            config_id,
            config_name,
            "consistency",
            args,
        )
        fold_metrics.extend(metrics)
        prediction_frames.extend(predictions)
        print(f"consistency  | {config_name:<28} features={len(columns):>3}")

    fold_df = pd.DataFrame(fold_metrics)
    summary_df = summarize_fold_metrics(fold_df)
    predictions_df = pd.concat(prediction_frames, ignore_index=True)
    metadata = build_group_metadata(df, splits)
    distribution_df = fold_distribution(metadata)
    group_summary_df = source_group_summary(metadata)

    fold_df.to_csv(output_dir / "grouped_ablation_fold_metrics.csv", index=False, encoding="utf-8")
    summary_df.to_csv(output_dir / "grouped_ablation_summary.csv", index=False, encoding="utf-8")
    predictions_df.to_csv(output_dir / "grouped_ablation_predictions.csv", index=False, encoding="utf-8")
    metadata.to_csv(output_dir / "grouped_sample_metadata.csv", index=False, encoding="utf-8")
    distribution_df.to_csv(output_dir / "grouped_fold_source_distribution.csv", index=False, encoding="utf-8")
    group_summary_df.to_csv(output_dir / "grouped_source_group_summary.csv", index=False, encoding="utf-8")

    with (output_dir / "grouped_ablation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary_df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    save_plot(summary_df, output_dir)

    print("\nGrouped source distribution:")
    print(distribution_df.to_string(index=False))
    print("\nSaved:")
    print(f"- {output_dir / 'grouped_ablation_summary.csv'}")
    print(f"- {output_dir / 'grouped_ablation_fold_metrics.csv'}")
    print(f"- {output_dir / 'grouped_fold_source_distribution.csv'}")
    print(f"- {output_dir / 'grouped_sample_metadata.csv'}")
    print(f"- {output_dir / 'grouped_coarse_error_metrics.png'}")
    print(f"- {output_dir / 'grouped_consistency_error_metrics.png'}")


if __name__ == "__main__":
    main()
