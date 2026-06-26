import argparse
import json
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GLM = SCRIPT_DIR / "outputs" / "glm52_holdout_jsonmode_full.jsonl"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "outputs" / "jsonmode_full_bands"

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


def load_glm_scores(path: Path) -> pd.DataFrame:
    records = []
    errors = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("error"):
                errors.append(item)
                continue
            label = item.get("glm_label", {})
            records.append(
                {
                    "row_index": int(item["row_index"]),
                    "session_id": item.get("session_id", ""),
                    "teacher_score": item.get("teacher_score"),
                    "glm_score": label.get("risk_score"),
                    "glm_reason": label.get("risk_reason", ""),
                    "model": item.get("model", ""),
                }
            )
    if not records:
        raise ValueError(f"No successful GLM records found in {path}")
    df = pd.DataFrame(records).drop_duplicates(subset=["row_index"], keep="last")
    df["teacher_score"] = pd.to_numeric(df["teacher_score"], errors="coerce")
    df["glm_score"] = pd.to_numeric(df["glm_score"], errors="coerce")
    df = df.dropna(subset=["teacher_score", "glm_score"])
    return df, errors


def band_for_score(score: float, bands: list[tuple[str, int, int]]) -> str:
    for label, lo, hi in bands:
        if lo <= score <= hi:
            return label
    return "out_of_range"


def add_bands(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["teacher_band_5"] = df["teacher_score"].apply(lambda x: band_for_score(x, FIVE_BANDS))
    df["glm_band_5"] = df["glm_score"].apply(lambda x: band_for_score(x, FIVE_BANDS))
    df["teacher_band_3"] = df["teacher_score"].apply(lambda x: band_for_score(x, THREE_BANDS))
    df["glm_band_3"] = df["glm_score"].apply(lambda x: band_for_score(x, THREE_BANDS))
    df["band5_match"] = df["teacher_band_5"] == df["glm_band_5"]
    df["band3_match"] = df["teacher_band_3"] == df["glm_band_3"]
    return df


def summarize(df: pd.DataFrame, errors: list[dict]) -> dict:
    summary = {
        "successful_rows": int(len(df)),
        "error_rows": int(len(errors)),
        "five_band_match_count": int(df["band5_match"].sum()),
        "five_band_match_rate": float(df["band5_match"].mean()),
        "three_band_match_count": int(df["band3_match"].sum()),
        "three_band_match_rate": float(df["band3_match"].mean()),
        "glm_score_distribution": {
            "min": float(df["glm_score"].min()),
            "max": float(df["glm_score"].max()),
            "mean": float(df["glm_score"].mean()),
            "median": float(df["glm_score"].median()),
        },
        "teacher_score_distribution": {
            "min": float(df["teacher_score"].min()),
            "max": float(df["teacher_score"].max()),
            "mean": float(df["teacher_score"].mean()),
            "median": float(df["teacher_score"].median()),
        },
        "five_band_teacher_counts": df["teacher_band_5"].value_counts().sort_index().to_dict(),
        "five_band_glm_counts": df["glm_band_5"].value_counts().sort_index().to_dict(),
        "three_band_teacher_counts": df["teacher_band_3"].value_counts().sort_index().to_dict(),
        "three_band_glm_counts": df["glm_band_3"].value_counts().sort_index().to_dict(),
    }
    return summary


def frame_to_markdown(df: pd.DataFrame) -> str:
    table = df.reset_index()
    headers = [str(col) for col in table.columns]
    rows = [[str(value) for value in row] for row in table.to_numpy().tolist()]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_summary_markdown(summary: dict, five_confusion: pd.DataFrame, three_confusion: pd.DataFrame) -> str:
    lines = [
        "# GLM-5.2 Score Band Analysis",
        "",
        f"- Successful rows: {summary['successful_rows']}",
        f"- Error rows: {summary['error_rows']}",
        f"- Five-band match: {summary['five_band_match_count']} / {summary['successful_rows']} ({summary['five_band_match_rate']:.2%})",
        f"- Three-band match: {summary['three_band_match_count']} / {summary['successful_rows']} ({summary['three_band_match_rate']:.2%})",
        f"- GLM score range: {summary['glm_score_distribution']['min']:.0f} - {summary['glm_score_distribution']['max']:.0f}",
        "",
        "## Five-Band Confusion",
        "",
        frame_to_markdown(five_confusion),
        "",
        "## Three-Band Confusion",
        "",
        frame_to_markdown(three_confusion),
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze GLM scores by rule-defined risk bands.")
    parser.add_argument("--glm-scores", default=str(DEFAULT_GLM), help="GLM JSONL output.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, errors = load_glm_scores(Path(args.glm_scores))
    df = add_bands(df)
    summary = summarize(df, errors)

    five_confusion = pd.crosstab(
        df["teacher_band_5"],
        df["glm_band_5"],
        rownames=["teacher"],
        colnames=["glm"],
        dropna=False,
    )
    three_confusion = pd.crosstab(
        df["teacher_band_3"],
        df["glm_band_3"],
        rownames=["teacher"],
        colnames=["glm"],
        dropna=False,
    )
    mismatches = df[~df["band5_match"]].sort_values(["teacher_band_5", "glm_band_5", "row_index"])

    df.to_csv(output_dir / "glm52_score_band_predictions.csv", index=False, encoding="utf-8")
    mismatches.to_csv(output_dir / "glm52_score_band_mismatches.csv", index=False, encoding="utf-8")
    five_confusion.to_csv(output_dir / "glm52_five_band_confusion.csv", encoding="utf-8")
    three_confusion.to_csv(output_dir / "glm52_three_band_confusion.csv", encoding="utf-8")
    (output_dir / "glm52_score_band_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "glm52_score_band_summary.md").write_text(
        write_summary_markdown(summary, five_confusion, three_confusion),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    main()
