#!/usr/bin/env python3
"""Evaluate cached GLM group scores with grouped-CV fusion.

Inputs are JSONL files produced by score_group_evidence_with_glm.py. Test folds
always use original evidence rows. Augmented evidence rows, when present, are
eligible only inside training folds.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "outputs" / "group_fusion"
RANDOM_STATE = 42
HIGH_RISK_THRESHOLD = 80.0

GROUP_SCORE_COLUMNS = [
    "native_web_score",
    "native_webview_score",
    "webview_web_score",
    "tri_layer_score",
    "physical_runtime_score",
    "attack_scenario_score",
]

CONFIGS = [
    ("D0_original_unweighted", "Original group scores, unweighted", False, False),
    ("W1_original_group_weighted", "Original group scores + group sample weight", True, False),
    ("P1_train_perturbed_unweighted", "Train-fold runtime perturbation, unweighted", False, True),
    (
        "WP_train_perturbed_group_weighted",
        "Train-fold runtime perturbation + group sample weight",
        True,
        True,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate cached GLM group-score fusion.")
    parser.add_argument(
        "--scores",
        nargs="+",
        required=True,
        help="One or more group-score JSONL files. Include originals and optional augmented scores.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--splits", type=int, default=3, help="Outer grouped-CV folds.")
    return parser.parse_args()


def load_score_rows(paths: list[Path]) -> pd.DataFrame:
    records = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("error"):
                    continue
                group_scores = item.get("group_scores", {})
                if not all(key in group_scores for key in GROUP_SCORE_COLUMNS):
                    continue
                record = {
                    "evidence_id": item.get("evidence_id"),
                    "row_index": int(item.get("row_index")),
                    "base_row_index": int(item.get("base_row_index", item.get("row_index"))),
                    "session_id": item.get("session_id", ""),
                    "source_type": item.get("source_type", ""),
                    "stable_device_key": item.get("stable_device_key", ""),
                    "group_id": item.get("group_id", ""),
                    "group_size": int(item.get("group_size") or 1),
                    "sample_weight": float(item.get("sample_weight") or 1.0),
                    "teacher_score": float(item.get("teacher_score")),
                    "teacher_band": item.get("teacher_band", ""),
                    "rule_family": item.get("rule_family", ""),
                    "evidence_hash": item.get("evidence_hash", ""),
                    "is_augmented": bool(item.get("is_augmented")),
                    "augmentation_id": item.get("augmentation_id", ""),
                    "knowledge_version": item.get("knowledge_version", ""),
                    "model": item.get("model", ""),
                }
                for key in GROUP_SCORE_COLUMNS:
                    record[key] = float(group_scores[key])
                records.append(record)
    if not records:
        raise ValueError("No successful group-score records found.")
    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["evidence_id"], keep="last")
    return df


def score_band(score: float) -> str:
    if score <= 20:
        return "low"
    if score <= 34:
        return "low_medium"
    if score <= 49:
        return "medium_cloud_or_test"
    if score <= 79:
        return "suspicious"
    return "high"


def choose_splits(original: pd.DataFrame, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    unique_groups = original["group_id"].nunique()
    n_splits = min(n_splits, unique_groups)
    if n_splits < 2:
        raise ValueError("Need at least two stable-device groups for grouped CV.")
    labels = original["teacher_score"].apply(score_band)
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    try:
        return list(
            splitter.split(
                original,
                y=labels,
                groups=original["group_id"].to_numpy(),
            )
        )
    except ValueError:
        fallback = GroupKFold(n_splits=n_splits)
        return list(fallback.split(original, groups=original["group_id"].to_numpy()))


def metrics_for_predictions(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    true_high = (y_true >= HIGH_RISK_THRESHOLD).astype(int)
    pred_high = (pred >= HIGH_RISK_THRESHOLD).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_high,
        pred_high,
        average="binary",
        zero_division=0,
    )
    result = {
        "mae": mean_absolute_error(y_true, pred),
        "rmse": math.sqrt(mean_squared_error(y_true, pred)),
        "high_risk_precision": precision,
        "high_risk_recall": recall,
        "high_risk_f1": f1,
        "high_risk_accuracy": accuracy_score(true_high, pred_high),
    }
    result["r2"] = r2_score(y_true, pred) if len(np.unique(y_true)) > 1 else 0.0
    return result


def make_train_frame(
    all_scores: pd.DataFrame,
    original_train_rows: pd.DataFrame,
    include_augmented: bool,
) -> pd.DataFrame:
    train_base_indices = set(original_train_rows["base_row_index"].astype(int))
    if include_augmented:
        train = all_scores[all_scores["base_row_index"].isin(train_base_indices)].copy()
    else:
        train = original_train_rows.copy()
    return train.sort_values(["base_row_index", "is_augmented", "evidence_id"])


def inner_group_splits(train: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    original_positions = np.where(~train["is_augmented"].to_numpy())[0]
    original_groups = train.iloc[original_positions]["group_id"].to_numpy()
    unique_groups = np.unique(original_groups)
    n_splits = min(3, len(unique_groups))
    if n_splits < 2:
        raise ValueError("Need at least two training groups for inner CV.")
    splitter = GroupKFold(n_splits=n_splits)
    splits = []
    for inner_train_orig_pos, inner_val_orig_pos in splitter.split(
        original_positions,
        groups=original_groups,
    ):
        val_positions = original_positions[inner_val_orig_pos]
        val_groups = set(train.iloc[val_positions]["group_id"])
        train_positions = np.array(
            [idx for idx in range(len(train)) if train.iloc[idx]["group_id"] not in val_groups],
            dtype=int,
        )
        splits.append((train_positions, val_positions))
    return splits


def fit_positive_elasticnet(
    train: pd.DataFrame,
    use_sample_weight: bool,
) -> tuple[ElasticNet, dict[str, float]]:
    X = train[GROUP_SCORE_COLUMNS].to_numpy(dtype=float)
    y = train["teacher_score"].to_numpy(dtype=float)
    weights = train["sample_weight"].to_numpy(dtype=float) if use_sample_weight else None
    grid_alpha = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]
    grid_l1 = [0.05, 0.1, 0.2, 0.5, 0.7, 0.9, 0.95, 1.0]

    best_score = math.inf
    best_params = {"alpha": 0.1, "l1_ratio": 0.5, "inner_mae": math.inf}
    for alpha in grid_alpha:
        for l1_ratio in grid_l1:
            fold_scores = []
            for train_pos, val_pos in inner_group_splits(train):
                model = ElasticNet(
                    alpha=alpha,
                    l1_ratio=l1_ratio,
                    positive=True,
                    fit_intercept=True,
                    max_iter=100000,
                    random_state=RANDOM_STATE,
                )
                fit_kwargs: dict[str, Any] = {}
                if weights is not None:
                    fit_kwargs["sample_weight"] = weights[train_pos]
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=ConvergenceWarning)
                    model.fit(X[train_pos], y[train_pos], **fit_kwargs)
                pred = np.clip(model.predict(X[val_pos]), 0, 100)
                fold_scores.append(mean_absolute_error(y[val_pos], pred))
            score = float(np.mean(fold_scores))
            if score < best_score:
                best_score = score
                best_params = {"alpha": alpha, "l1_ratio": l1_ratio, "inner_mae": score}

    model = ElasticNet(
        alpha=best_params["alpha"],
        l1_ratio=best_params["l1_ratio"],
        positive=True,
        fit_intercept=True,
        max_iter=100000,
        random_state=RANDOM_STATE,
    )
    fit_kwargs = {}
    if weights is not None:
        fit_kwargs["sample_weight"] = weights
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        model.fit(X, y, **fit_kwargs)
    return model, best_params


def summarize_fold_metrics(fold_metrics: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(fold_metrics)
    rows = []
    metric_cols = [
        "mae",
        "rmse",
        "r2",
        "high_risk_precision",
        "high_risk_recall",
        "high_risk_f1",
        "high_risk_accuracy",
    ]
    for config_id, group in df.groupby("config_id", sort=False):
        row = {
            "config_id": config_id,
            "config_name": group["config_name"].iloc[0],
            "folds": int(len(group)),
            "train_augmented": bool(group["train_augmented"].iloc[0]),
            "sample_weighted": bool(group["sample_weighted"].iloc[0]),
        }
        for col in metric_cols:
            row[f"{col}_mean"] = float(group[col].mean())
            row[f"{col}_std"] = float(group[col].std(ddof=0))
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(path: Path, summary: pd.DataFrame) -> None:
    lines = [
        "# Cached GLM Group Fusion Report",
        "",
        "| Config | Train perturbation | Sample weight | MAE | RMSE | High-risk F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| {row['config_name']} | {row['train_augmented']} | {row['sample_weighted']} | "
            f"{row['mae_mean']:.3f} | {row['rmse_mean']:.3f} | {row['high_risk_f1_mean']:.3f} |"
        )
    lines.extend(
        [
            "",
            "Test folds use only original evidence rows. Augmented evidence rows, if available, are used only in training folds.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_scores = load_score_rows([Path(path) for path in args.scores])
    original = all_scores[~all_scores["is_augmented"]].copy()
    if original.empty:
        raise ValueError("No original evidence scores found.")
    splits = choose_splits(original, args.splits)

    fold_metrics: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []

    for config_id, config_name, use_weight, include_augmented in CONFIGS:
        for fold, (train_pos, test_pos) in enumerate(splits, start=1):
            original_train = original.iloc[train_pos].copy()
            original_test = original.iloc[test_pos].copy()
            train = make_train_frame(all_scores, original_train, include_augmented)

            model, params = fit_positive_elasticnet(train, use_weight)
            X_test = original_test[GROUP_SCORE_COLUMNS].to_numpy(dtype=float)
            y_test = original_test["teacher_score"].to_numpy(dtype=float)
            pred = np.clip(model.predict(X_test), 0, 100)
            metrics = metrics_for_predictions(y_test, pred)
            metrics.update(
                {
                    "config_id": config_id,
                    "config_name": config_name,
                    "fold": fold,
                    "train_augmented": include_augmented,
                    "sample_weighted": use_weight,
                    "train_size": len(train),
                    "test_size": len(original_test),
                    "train_original_size": len(original_train),
                    "train_augmented_size": int(train["is_augmented"].sum()),
                    "train_group_count": train["group_id"].nunique(),
                    "test_group_count": original_test["group_id"].nunique(),
                    "alpha": params["alpha"],
                    "l1_ratio": params["l1_ratio"],
                    "inner_mae": params["inner_mae"],
                }
            )
            fold_metrics.append(metrics)

            weight_row = {
                "config_id": config_id,
                "config_name": config_name,
                "fold": fold,
                "intercept": float(model.intercept_),
                "alpha": params["alpha"],
                "l1_ratio": params["l1_ratio"],
                "inner_mae": params["inner_mae"],
            }
            for idx, col in enumerate(GROUP_SCORE_COLUMNS):
                weight_row[f"weight_{col.replace('_score', '')}"] = float(model.coef_[idx])
            weight_rows.append(weight_row)

            for idx, row in original_test.reset_index(drop=True).iterrows():
                prediction_rows.append(
                    {
                        "config_id": config_id,
                        "config_name": config_name,
                        "fold": fold,
                        "evidence_id": row["evidence_id"],
                        "row_index": row["row_index"],
                        "session_id": row["session_id"],
                        "source_type": row["source_type"],
                        "group_id": row["group_id"],
                        "teacher_score": row["teacher_score"],
                        "predicted_score": float(pred[idx]),
                        "absolute_error": abs(float(pred[idx]) - float(row["teacher_score"])),
                    }
                )

    fold_df = pd.DataFrame(fold_metrics)
    summary_df = summarize_fold_metrics(fold_metrics)
    predictions_df = pd.DataFrame(prediction_rows)
    weights_df = pd.DataFrame(weight_rows)

    fold_df.to_csv(output_dir / "fusion_fold_metrics.csv", index=False, encoding="utf-8")
    summary_df.to_csv(output_dir / "fusion_summary.csv", index=False, encoding="utf-8")
    predictions_df.to_csv(output_dir / "fusion_predictions.csv", index=False, encoding="utf-8")
    weights_df.to_csv(output_dir / "fusion_weights.csv", index=False, encoding="utf-8")
    write_report(output_dir / "fusion_report.md", summary_df)

    print(summary_df.to_json(orient="records", force_ascii=False, indent=2))
    print(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    main()
