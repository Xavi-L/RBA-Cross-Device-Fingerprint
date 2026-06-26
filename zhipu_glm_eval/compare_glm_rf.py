import argparse
import json
import math
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
DEFAULT_INPUT = REPO_ROOT / "training" / "scored_data.jsonl"
DEFAULT_GLM = SCRIPT_DIR / "outputs" / "glm52_holdout_sample_scores.jsonl"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "outputs"
TARGET_COL = "llm_label.risk_score"
HIGH_RISK_THRESHOLD = 80.0
RANDOM_STATE = 42
TEST_SIZE = 0.2


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return rows


def load_glm_scores(path: Path) -> pd.DataFrame:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("error"):
                continue
            label = item.get("glm_label", {})
            records.append(
                {
                    "row_index": int(item["row_index"]),
                    "session_id": item.get("session_id", ""),
                    "teacher_score_from_glm_file": item.get("teacher_score"),
                    "glm_score": label.get("risk_score"),
                    "glm_reason": label.get("risk_reason", ""),
                    "model": item.get("model", ""),
                }
            )
    if not records:
        raise ValueError(f"No successful GLM records found in {path}")
    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["row_index"], keep="last")
    df["glm_score"] = pd.to_numeric(df["glm_score"], errors="coerce")
    df = df.dropna(subset=["glm_score"])
    return df


def prepare_randomforest_predictions(rows: list[dict]) -> pd.DataFrame:
    df = pd.json_normalize(rows)
    y = df[TARGET_COL]
    cols_to_drop = [
        "session_id",
        "timestamp",
        "client_ip",
        "llm_label.risk_score",
        "llm_label.risk_reason",
    ]
    X = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
    for col in X.columns:
        if X[col].dtype == "object" or X[col].dtype == "bool":
            X[col] = X[col].fillna("Unknown").astype(str)
            X[col] = LabelEncoder().fit_transform(X[col])
        else:
            X[col] = X[col].fillna(-1)

    indices = list(range(len(df)))
    train_idx, test_idx = train_test_split(indices, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1)
    model.fit(X.iloc[train_idx], y.iloc[train_idx])
    pred = model.predict(X.iloc[test_idx])
    return pd.DataFrame(
        {
            "row_index": test_idx,
            "session_id": df.iloc[test_idx]["session_id"].to_numpy()
            if "session_id" in df.columns
            else "",
            "teacher_score": y.iloc[test_idx].to_numpy(),
            "rf_score": pred,
        }
    )


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    result = {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": math.sqrt(mean_squared_error(y_true, y_pred)),
        "pearson": pd.Series(y_true).corr(pd.Series(y_pred), method="pearson"),
        "spearman": pd.Series(y_true).corr(pd.Series(y_pred), method="spearman"),
    }
    if len(np.unique(y_true)) > 1:
        result["r2"] = r2_score(y_true, y_pred)
    else:
        result["r2"] = None
    return result


def high_risk_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    true_high = (y_true >= HIGH_RISK_THRESHOLD).astype(int)
    pred_high = (y_pred >= HIGH_RISK_THRESHOLD).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_high,
        pred_high,
        average="binary",
        zero_division=0,
    )
    return {
        "threshold": HIGH_RISK_THRESHOLD,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy_score(true_high, pred_high),
        "true_high_count": int(true_high.sum()),
        "pred_high_count": int(pred_high.sum()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare GLM scores with RandomForest predictions.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Original scored JSONL.")
    parser.add_argument("--glm-scores", default=str(DEFAULT_GLM), help="GLM JSONL output.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(Path(args.input))
    rf_df = prepare_randomforest_predictions(rows)
    glm_df = load_glm_scores(Path(args.glm_scores))
    merged = glm_df.merge(rf_df, on=["row_index", "session_id"], how="inner")
    if merged.empty:
        raise ValueError("No overlapping GLM rows and RandomForest holdout rows.")

    merged["glm_abs_error_vs_teacher"] = (merged["glm_score"] - merged["teacher_score"]).abs()
    merged["rf_abs_error_vs_teacher"] = (merged["rf_score"] - merged["teacher_score"]).abs()
    merged["glm_abs_diff_vs_rf"] = (merged["glm_score"] - merged["rf_score"]).abs()
    merged = merged.sort_values("glm_abs_error_vs_teacher", ascending=False)

    y_teacher = merged["teacher_score"].to_numpy(dtype=float)
    glm_score = merged["glm_score"].to_numpy(dtype=float)
    rf_score = merged["rf_score"].to_numpy(dtype=float)

    metrics = {
        "sample_size": int(len(merged)),
        "model": merged["model"].dropna().iloc[0] if "model" in merged and not merged.empty else "",
        "glm_vs_teacher": regression_metrics(y_teacher, glm_score),
        "rf_vs_teacher_same_rows": regression_metrics(y_teacher, rf_score),
        "glm_vs_rf": regression_metrics(rf_score, glm_score),
        "glm_high_risk_vs_teacher": high_risk_metrics(y_teacher, glm_score),
        "rf_high_risk_vs_teacher_same_rows": high_risk_metrics(y_teacher, rf_score),
        "score_means": {
            "teacher": float(np.mean(y_teacher)),
            "glm": float(np.mean(glm_score)),
            "rf": float(np.mean(rf_score)),
        },
    }

    predictions_path = output_dir / "glm52_vs_randomforest_predictions.csv"
    metrics_path = output_dir / "glm52_vs_randomforest_metrics.json"
    summary_path = output_dir / "glm52_vs_randomforest_summary.md"
    merged.to_csv(predictions_path, index=False, encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(
        "\n".join(
            [
                "# GLM-5.2 vs RandomForest Pilot",
                "",
                f"- Sample size: {metrics['sample_size']}",
                f"- GLM vs teacher MAE/RMSE: {metrics['glm_vs_teacher']['mae']:.3f} / {metrics['glm_vs_teacher']['rmse']:.3f}",
                f"- RF vs teacher MAE/RMSE on same rows: {metrics['rf_vs_teacher_same_rows']['mae']:.3f} / {metrics['rf_vs_teacher_same_rows']['rmse']:.3f}",
                f"- GLM high-risk F1: {metrics['glm_high_risk_vs_teacher']['f1']:.3f}",
                f"- RF high-risk F1 on same rows: {metrics['rf_high_risk_vs_teacher_same_rows']['f1']:.3f}",
                "",
                "See `glm52_vs_randomforest_predictions.csv` for per-sample details.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Saved predictions: {predictions_path}")
    print(f"Saved metrics: {metrics_path}")


if __name__ == "__main__":
    main()
