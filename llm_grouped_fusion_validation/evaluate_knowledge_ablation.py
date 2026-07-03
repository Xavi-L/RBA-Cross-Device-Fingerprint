#!/usr/bin/env python3
"""Evaluate paired K0/K1 GLM scoring outputs.

The script supports direct-score JSONL from zhipu_glm_eval/score_with_glm.py
and grouped-score JSONL from score_group_evidence_with_glm.py. For grouped
scores, it evaluates the mean of the six group scores as a lightweight quality
check; final fusion should use evaluate_cached_group_fusion.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "outputs" / "knowledge_ablation"

FIVE_BANDS = [
    ("low", 0, 20),
    ("low_medium", 21, 34),
    ("medium_cloud_or_test", 35, 49),
    ("suspicious", 50, 79),
    ("high", 80, 100),
]

THREE_BANDS = [
    ("low", 0, 34),
    ("medium", 35, 79),
    ("high", 80, 100),
]

FUTURE_ONLY_TERMS = [
    "Play Integrity",
    "play integrity",
    "Key Attestation",
    "key attestation",
    "attestation",
    "完整性令牌",
    "证书链",
    "origin",
    "URL",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate K0/K1 knowledge ablation outputs.")
    parser.add_argument("--k0", required=True, help="K0 no-official GLM JSONL.")
    parser.add_argument("--k1", required=True, help="K1 official-knowledge GLM JSONL.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    return parser.parse_args()


def band_for_score(score: float, bands: list[tuple[str, int, int]]) -> str:
    for label, low, high in bands:
        if low <= score <= high:
            return label
    return "out_of_range"


def load_scores(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("error"):
                continue
            key = str(item.get("evidence_id", item.get("row_index")))
            score, reason = extract_score_reason(item)
            teacher = item.get("teacher_score")
            if teacher is None:
                teacher = item.get("teacher_score_from_glm_file")
            rows[key] = {
                "key": key,
                "row_index": item.get("row_index"),
                "evidence_id": item.get("evidence_id", ""),
                "session_id": item.get("session_id", ""),
                "teacher_score": float(teacher),
                "score": float(score),
                "reason": reason,
                "source_type": item.get("source_type", ""),
                "group_id": item.get("group_id", ""),
                "rule_family": item.get("rule_family", ""),
                "knowledge_version": item.get("knowledge_version", ""),
                "model": item.get("model", ""),
            }
    if not rows:
        raise ValueError(f"No successful scores found in {path}")
    return rows


def extract_score_reason(item: dict[str, Any]) -> tuple[float, str]:
    if "glm_label" in item:
        label = item.get("glm_label", {})
        return float(label.get("risk_score")), str(label.get("risk_reason", ""))

    group_scores = item.get("group_scores")
    if isinstance(group_scores, dict):
        values = [float(value) for value in group_scores.values()]
        reasons = item.get("group_reasons", {})
        reason = "；".join(str(value) for value in reasons.values()) if isinstance(reasons, dict) else ""
        return sum(values) / len(values), reason

    raise ValueError(f"Unsupported score row: {item.keys()}")


def mae(rows: list[dict[str, Any]]) -> float:
    return sum(abs(row["score"] - row["teacher_score"]) for row in rows) / len(rows)


def rmse(rows: list[dict[str, Any]]) -> float:
    return math.sqrt(
        sum((row["score"] - row["teacher_score"]) ** 2 for row in rows) / len(rows)
    )


def high_risk_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    tp = fp = tn = fn = 0
    for row in rows:
        true_high = row["teacher_score"] >= 80
        pred_high = row["score"] >= 80
        if true_high and pred_high:
            tp += 1
        elif not true_high and pred_high:
            fp += 1
        elif not true_high and not pred_high:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + tn) / len(rows),
        "true_high_count": tp + fn,
        "pred_high_count": tp + fp,
    }


def summarize(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        row["teacher_band_5"] = band_for_score(row["teacher_score"], FIVE_BANDS)
        row["pred_band_5"] = band_for_score(row["score"], FIVE_BANDS)
        row["teacher_band_3"] = band_for_score(row["teacher_score"], THREE_BANDS)
        row["pred_band_3"] = band_for_score(row["score"], THREE_BANDS)
    five_match = sum(row["teacher_band_5"] == row["pred_band_5"] for row in rows)
    three_match = sum(row["teacher_band_3"] == row["pred_band_3"] for row in rows)
    future_reason_hits = sum(
        any(term in row["reason"] for term in FUTURE_ONLY_TERMS) for row in rows
    )
    return {
        "name": name,
        "rows": len(rows),
        "mae": mae(rows),
        "rmse": rmse(rows),
        "five_band_match_count": five_match,
        "five_band_match_rate": five_match / len(rows),
        "three_band_match_count": three_match,
        "three_band_match_rate": three_match / len(rows),
        "future_only_reason_hits": future_reason_hits,
        "high_risk": high_risk_metrics(rows),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    k0 = summary["k0"]
    k1 = summary["k1"]
    delta = summary["delta"]
    lines = [
        "# Knowledge Ablation Report",
        "",
        "| Metric | K0 no official | K1 official | Delta |",
        "|---|---:|---:|---:|",
        f"| Rows | {k0['rows']} | {k1['rows']} | {delta['rows']} |",
        f"| MAE | {k0['mae']:.3f} | {k1['mae']:.3f} | {delta['mae']:.3f} |",
        f"| RMSE | {k0['rmse']:.3f} | {k1['rmse']:.3f} | {delta['rmse']:.3f} |",
        f"| Five-band match | {k0['five_band_match_rate']:.2%} | {k1['five_band_match_rate']:.2%} | {delta['five_band_match_rate']:.2%} |",
        f"| Three-band match | {k0['three_band_match_rate']:.2%} | {k1['three_band_match_rate']:.2%} | {delta['three_band_match_rate']:.2%} |",
        f"| High-risk F1 | {k0['high_risk']['f1']:.3f} | {k1['high_risk']['f1']:.3f} | {delta['high_risk_f1']:.3f} |",
        f"| Future-only reason hits | {k0['future_only_reason_hits']} | {k1['future_only_reason_hits']} | {delta['future_only_reason_hits']} |",
        "",
        f"- Paired improved rows: {summary['paired_counts']['improved']}",
        f"- Paired worsened rows: {summary['paired_counts']['worsened']}",
        f"- Paired unchanged rows: {summary['paired_counts']['unchanged']}",
        "",
        "Interpretation note: lower MAE/RMSE is better; higher band match and high-risk F1 are better; future-only reason hits should stay at 0.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    k0_scores = load_scores(Path(args.k0))
    k1_scores = load_scores(Path(args.k1))
    common_keys = sorted(set(k0_scores) & set(k1_scores))
    if not common_keys:
        raise ValueError("No overlapping rows/evidence IDs between K0 and K1.")

    k0_rows = [k0_scores[key] for key in common_keys]
    k1_rows = [k1_scores[key] for key in common_keys]
    paired_rows = []
    counts = {"improved": 0, "worsened": 0, "unchanged": 0}
    for key in common_keys:
        a = k0_scores[key]
        b = k1_scores[key]
        k0_abs = abs(a["score"] - a["teacher_score"])
        k1_abs = abs(b["score"] - b["teacher_score"])
        if k1_abs < k0_abs:
            status = "improved"
        elif k1_abs > k0_abs:
            status = "worsened"
        else:
            status = "unchanged"
        counts[status] += 1
        paired_rows.append(
            {
                "key": key,
                "row_index": b["row_index"],
                "evidence_id": b["evidence_id"],
                "session_id": b["session_id"],
                "teacher_score": b["teacher_score"],
                "source_type": b["source_type"],
                "rule_family": b["rule_family"],
                "k0_score": a["score"],
                "k1_score": b["score"],
                "k0_abs_error": k0_abs,
                "k1_abs_error": k1_abs,
                "abs_error_delta_k1_minus_k0": k1_abs - k0_abs,
                "status": status,
                "k0_reason": a["reason"],
                "k1_reason": b["reason"],
            }
        )

    k0_summary = summarize("K0_no_official", k0_rows)
    k1_summary = summarize("K1_official", k1_rows)
    summary = {
        "k0": k0_summary,
        "k1": k1_summary,
        "delta": {
            "rows": k1_summary["rows"] - k0_summary["rows"],
            "mae": k1_summary["mae"] - k0_summary["mae"],
            "rmse": k1_summary["rmse"] - k0_summary["rmse"],
            "five_band_match_rate": k1_summary["five_band_match_rate"]
            - k0_summary["five_band_match_rate"],
            "three_band_match_rate": k1_summary["three_band_match_rate"]
            - k0_summary["three_band_match_rate"],
            "high_risk_f1": k1_summary["high_risk"]["f1"] - k0_summary["high_risk"]["f1"],
            "future_only_reason_hits": k1_summary["future_only_reason_hits"]
            - k0_summary["future_only_reason_hits"],
        },
        "paired_counts": counts,
    }

    (output_dir / "knowledge_ablation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(
        output_dir / "knowledge_ablation_paired_rows.csv",
        sorted(paired_rows, key=lambda row: row["abs_error_delta_k1_minus_k0"], reverse=True),
        [
            "key",
            "row_index",
            "evidence_id",
            "session_id",
            "teacher_score",
            "source_type",
            "rule_family",
            "k0_score",
            "k1_score",
            "k0_abs_error",
            "k1_abs_error",
            "abs_error_delta_k1_minus_k0",
            "status",
            "k0_reason",
            "k1_reason",
        ],
    )
    write_markdown(output_dir / "knowledge_ablation_report.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    main()
