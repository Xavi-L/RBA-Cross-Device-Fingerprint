import argparse
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
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

LAYER_PREFIXES = {
    "native": "android_native_data.",
    "webview": "webview_data.",
    "web": "web_data.",
}

CONFIGS = [
    ("native_only", "Native only", ("native",)),
    ("webview_only", "WebView only", ("webview",)),
    ("web_only", "Web only", ("web",)),
    ("native_webview", "Native + WebView", ("native", "webview")),
    ("native_web", "Native + Web", ("native", "web")),
    ("webview_web", "WebView + Web", ("webview", "web")),
    ("all_three", "Native + WebView + Web", ("native", "webview", "web")),
]

TARGET_COL = "llm_label.risk_score"
HIGH_RISK_THRESHOLD = 80.0
RANDOM_STATE = 42
TEST_SIZE = 0.2


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run quick RandomForest ablation experiments for HybridGuard feature layers."
    )
    parser.add_argument(
        "--input",
        default=str(REPO_ROOT / "training" / "scored_data.jsonl"),
        help="Path to scored JSONL data.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(SCRIPT_DIR),
        help="Directory for ablation results.",
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


def selected_columns(df, layers):
    prefixes = tuple(LAYER_PREFIXES[layer] for layer in layers)
    return [col for col in df.columns if col.startswith(prefixes)]


def encode_features(df, columns):
    X = df[columns].copy()
    encoders = {}
    for col in X.columns:
        if X[col].dtype == "object" or X[col].dtype == "bool":
            X[col] = X[col].fillna("Unknown").astype(str)
            encoder = LabelEncoder()
            X[col] = encoder.fit_transform(X[col])
            encoders[col] = encoder
        else:
            X[col] = X[col].fillna(-1)
    return X, encoders


def evaluate_config(df, train_idx, test_idx, config_id, config_name, layers, args):
    columns = selected_columns(df, layers)
    if not columns:
        raise ValueError(f"No feature columns selected for {config_id}")

    X, _ = encode_features(df, columns)
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

    rmse = math.sqrt(mean_squared_error(y_test, pred))
    summary = {
        "config_id": config_id,
        "config_name": config_name,
        "layers": "+".join(layers),
        "feature_count": len(columns),
        "train_size": len(train_idx),
        "test_size": len(test_idx),
        "mae": mean_absolute_error(y_test, pred),
        "rmse": rmse,
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

    return summary, predictions


def save_plots(summary_df, output_dir):
    os.environ.setdefault("MPLCONFIGDIR", str(output_dir / ".mplconfig"))
    output_dir.mkdir(parents=True, exist_ok=True)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = summary_df["config_name"].tolist()
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.bar(x, summary_df["mae"], color="#2f6f9f", label="MAE")
    ax.plot(x, summary_df["rmse"], color="#c9472c", marker="o", linewidth=2, label="RMSE")
    ax.set_title("RandomForest Ablation: Error Metrics")
    ax.set_ylabel("Risk score error")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "ablation_error_metrics.png", dpi=180)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(11, 5.6))
    bars = ax1.bar(x, summary_df["high_risk_f1"], color="#217a57", label="High-risk F1")
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("High-risk F1")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=25, ha="right")
    ax1.grid(axis="y", alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(x, summary_df["feature_count"], color="#7f4fb0", marker="s", linewidth=2, label="Feature count")
    ax2.set_ylabel("Feature count")

    ax1.set_title("RandomForest Ablation: High-risk Detection and Feature Count")
    handles = [bars, ax2.lines[0]]
    ax1.legend(handles, [h.get_label() for h in handles], loc="lower right")
    fig.tight_layout()
    fig.savefig(output_dir / "ablation_high_risk_f1.png", dpi=180)
    plt.close(fig)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_jsonl(args.input)
    if TARGET_COL not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COL}")

    y = df[TARGET_COL]
    indices = np.arange(len(df))
    train_idx, test_idx = train_test_split(
        indices,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    summaries = []
    prediction_frames = []
    for config_id, config_name, layers in CONFIGS:
        summary, predictions = evaluate_config(
            df, train_idx, test_idx, config_id, config_name, layers, args
        )
        summaries.append(summary)
        prediction_frames.append(predictions)
        print(
            f"{config_name:<24} features={summary['feature_count']:>2} "
            f"MAE={summary['mae']:.2f} RMSE={summary['rmse']:.2f} "
            f"F1={summary['high_risk_f1']:.3f}"
        )

    summary_df = pd.DataFrame(summaries)
    predictions_df = pd.concat(prediction_frames, ignore_index=True)

    summary_df.to_csv(output_dir / "ablation_summary.csv", index=False, encoding="utf-8")
    predictions_df.to_csv(output_dir / "ablation_predictions.csv", index=False, encoding="utf-8")

    with (output_dir / "ablation_summary.json").open("w", encoding="utf-8") as f:
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
    with (output_dir / "holdout_split_indices.json").open("w", encoding="utf-8") as f:
        json.dump(split_payload, f, ensure_ascii=False, indent=2)

    save_plots(summary_df, output_dir)

    print("\nSaved:")
    print(f"- {output_dir / 'ablation_summary.csv'}")
    print(f"- {output_dir / 'ablation_predictions.csv'}")
    print(f"- {output_dir / 'holdout_split_indices.json'}")
    print(f"- {output_dir / 'ablation_error_metrics.png'}")
    print(f"- {output_dir / 'ablation_high_risk_f1.png'}")


if __name__ == "__main__":
    main()
