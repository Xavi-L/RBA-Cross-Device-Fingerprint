#!/usr/bin/env python3
"""Build paper and presentation figures from ablation experiment outputs."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"
MPLCONFIG_DIR = ROOT / ".mplconfig"
MPLCONFIG_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIG_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


SOURCE_ORDER = ["physical_device", "cloud_device", "script_attack"]
SOURCE_LABELS = {
    "physical_device": "Physical devices",
    "cloud_device": "Cloud/lab devices",
    "script_attack": "Script attacks",
}
SOURCE_COLORS = {
    "physical_device": "#3f7d4d",
    "cloud_device": "#2f6f9f",
    "script_attack": "#b44b3b",
}

GROUP_COLORS = {
    "raw": "#4e5d6c",
    "native_web": "#3f7d4d",
    "native_webview": "#2f6f9f",
    "webview_web": "#8a6f2a",
    "tri_layer": "#c76039",
    "consistency": "#6a5f9f",
}


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / name)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#d7dce2",
            "grid.linewidth": 0.8,
            "grid.alpha": 0.6,
            "legend.frameon": False,
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "axes.labelcolor": "#1f2937",
            "axes.titlecolor": "#111827",
            "savefig.bbox": "tight",
            "savefig.dpi": 220,
        }
    )


def save(fig: plt.Figure, filename: str) -> Path:
    FIG_DIR.mkdir(exist_ok=True)
    output = FIG_DIR / filename
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)
    print(output.relative_to(ROOT))
    return output


def figure_source_distribution() -> Path:
    metadata = load_csv("grouped_sample_metadata.csv")
    group_summary = load_csv("grouped_source_group_summary.csv")

    samples = (
        metadata["source_type"]
        .value_counts()
        .reindex(SOURCE_ORDER)
        .fillna(0)
        .astype(int)
    )
    groups = (
        group_summary.groupby("source_type")["group_id"]
        .nunique()
        .reindex(SOURCE_ORDER)
        .fillna(0)
        .astype(int)
    )

    labels = [SOURCE_LABELS[s] for s in SOURCE_ORDER]
    colors = [SOURCE_COLORS[s] for s in SOURCE_ORDER]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    panels = [
        (axes[0], samples, "Sample Count by Source", "Samples"),
        (axes[1], groups, "Group Count by Source", "Groups"),
    ]

    for ax, series, title, xlabel in panels:
        values = series.to_numpy()
        total = values.sum()
        bars = ax.barh(labels, values, color=colors, height=0.55)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
        ax.invert_yaxis()
        max_value = max(values) if len(values) else 1
        ax.set_xlim(0, max_value * 1.22)
        for bar, value in zip(bars, values):
            pct = value / total if total else 0
            ax.text(
                bar.get_width() + max_value * 0.025,
                bar.get_y() + bar.get_height() / 2,
                f"{value:,} ({pct:.1%})",
                va="center",
                ha="left",
                color="#1f2937",
                fontsize=9,
            )

    fig.suptitle("Dataset Source Composition", y=1.04, fontsize=15, fontweight="bold")
    return save(fig, "figure_01_source_distribution.png")


def figure_fold_distribution() -> Path:
    fold_dist = load_csv("grouped_fold_source_distribution.csv")
    folds = sorted(fold_dist["fold"].unique())

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    panels = [
        (axes[0], "rows", "Test Samples per Fold"),
        (axes[1], "groups", "Test Groups per Fold"),
    ]

    for ax, metric, title in panels:
        pivot = (
            fold_dist.pivot(index="fold", columns="source_type", values=metric)
            .reindex(index=folds, columns=SOURCE_ORDER)
            .fillna(0)
        )
        bottom = np.zeros(len(folds))
        totals = pivot.sum(axis=1).to_numpy()
        small_threshold = max(totals) * 0.06
        x = np.arange(len(folds))
        for source in SOURCE_ORDER:
            values = pivot[source].to_numpy()
            bars = ax.bar(
                x,
                values,
                bottom=bottom,
                label=SOURCE_LABELS[source],
                color=SOURCE_COLORS[source],
                width=0.62,
            )
            for bar, value, base in zip(bars, values, bottom):
                if value <= 0:
                    continue
                if value < small_threshold:
                    y_pos = base + value + max(totals) * 0.012
                    color = "#1f2937"
                    va = "bottom"
                else:
                    y_pos = base + value / 2
                    color = "white"
                    va = "center"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    y_pos,
                    f"{int(value)}",
                    ha="center",
                    va=va,
                    color=color,
                    fontsize=9,
                    fontweight="bold",
                )
            bottom += values

        y_pad = max(totals) * 0.04
        for xi, total in zip(x, totals):
            ax.text(
                xi,
                total + y_pad,
                f"Total {int(total)}",
                ha="center",
                va="bottom",
                fontsize=9,
                color="#1f2937",
            )

        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels([f"Fold {fold}" for fold in folds])
        ax.set_ylabel(metric.title())
        ax.set_ylim(0, max(totals) * 1.16)
        ax.grid(axis="y")
        ax.grid(axis="x", visible=False)

    axes[0].legend(loc="upper left", bbox_to_anchor=(0, 1.18), ncol=3)
    fig.suptitle("Grouped Cross-Validation Fold Composition", y=1.06, fontsize=15, fontweight="bold")
    return save(fig, "figure_02_fold_distribution.png")


def collect_holdout_vs_grouped() -> pd.DataFrame:
    holdout_coarse = load_csv("ablation_summary.csv")
    holdout_consistency = load_csv("consistency_ablation_summary.csv")
    grouped = load_csv("grouped_ablation_summary.csv")

    items = [
        ("web_only", "coarse_layer", "Web only"),
        ("webview_only", "coarse_layer", "WebView only"),
        ("raw_all", "consistency", "Raw all"),
        ("consistency_only", "consistency", "Consistency only"),
        ("native_webview_consistency", "consistency", "N-WV consistency"),
        ("tri_layer_semantic", "consistency", "Tri-layer semantic"),
    ]

    rows = []
    for config_id, experiment_type, label in items:
        holdout_df = holdout_coarse if experiment_type == "coarse_layer" else holdout_consistency
        holdout_row = holdout_df.loc[holdout_df["config_id"] == config_id].iloc[0]
        grouped_row = grouped.loc[
            (grouped["experiment_type"] == experiment_type)
            & (grouped["config_id"] == config_id)
        ].iloc[0]
        rows.append(
            {
                "label": label,
                "holdout_mae": holdout_row["mae"],
                "grouped_mae": grouped_row["mae_mean"],
                "grouped_mae_std": grouped_row["mae_std"],
            }
        )
    return pd.DataFrame(rows)


def figure_holdout_vs_grouped_mae() -> Path:
    comparison = collect_holdout_vs_grouped()
    x = np.arange(len(comparison))
    width = 0.36

    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    holdout_bars = ax.bar(
        x - width / 2,
        comparison["holdout_mae"],
        width,
        label="Random holdout",
        color="#8fb3c9",
    )
    grouped_bars = ax.bar(
        x + width / 2,
        comparison["grouped_mae"],
        width,
        yerr=comparison["grouped_mae_std"],
        capsize=4,
        label="Grouped CV",
        color="#d08b5b",
        error_kw={"elinewidth": 1.2, "ecolor": "#6b7280"},
    )

    ax.set_title("Random Holdout vs Grouped CV Error")
    ax.set_ylabel("MAE (lower is better)")
    ax.set_xticks(x)
    ax.set_xticklabels(comparison["label"], rotation=22, ha="right")
    ax.legend(loc="upper left")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)

    for bars in (holdout_bars, grouped_bars):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.15,
                f"{height:.2f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color="#1f2937",
            )

    return save(fig, "figure_03_holdout_vs_grouped_mae.png")


def collect_grouped_main_results() -> pd.DataFrame:
    grouped = load_csv("grouped_ablation_summary.csv")
    items = [
        ("raw_all", "consistency", "Raw all"),
        ("raw_clean", "consistency", "Raw cleaned"),
        ("consistency_only", "consistency", "Consistency only"),
        ("raw_all_plus_consistency", "consistency", "Raw all + consistency"),
        ("raw_clean_plus_consistency", "consistency", "Raw cleaned + consistency"),
        ("native_webview_consistency", "consistency", "N-WV consistency"),
        ("tri_layer_semantic", "consistency", "Tri-layer semantic"),
    ]

    rows = []
    for config_id, experiment_type, label in items:
        row = grouped.loc[
            (grouped["experiment_type"] == experiment_type)
            & (grouped["config_id"] == config_id)
        ].iloc[0]
        rows.append(
            {
                "label": label,
                "mae": row["mae_mean"],
                "mae_std": row["mae_std"],
                "rmse": row["rmse_mean"],
                "rmse_std": row["rmse_std"],
                "feature_count": int(row["feature_count"]),
            }
        )
    return pd.DataFrame(rows).sort_values("mae", ascending=True)


def figure_grouped_main_results() -> Path:
    results = collect_grouped_main_results()
    labels = [f"{row.label}\n{row.feature_count} features" for row in results.itertuples()]
    y = np.arange(len(results))
    colors = [
        "#c76039" if label.startswith("Tri-layer") else "#6f8fa8"
        for label in results["label"]
    ]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.7), sharey=True)
    metrics = [
        (axes[0], "mae", "mae_std", "MAE"),
        (axes[1], "rmse", "rmse_std", "RMSE"),
    ]

    for ax, metric, std_metric, title in metrics:
        bars = ax.barh(
            y,
            results[metric],
            xerr=results[std_metric],
            color=colors,
            height=0.58,
            capsize=4,
            error_kw={"elinewidth": 1.2, "ecolor": "#6b7280"},
        )
        ax.set_title(f"Grouped CV {title}")
        ax.set_xlabel(f"{title} (lower is better)")
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
        max_value = (results[metric] + results[std_metric]).max()
        ax.set_xlim(0, max_value * 1.24)
        for bar, value in zip(bars, results[metric]):
            ax.text(
                bar.get_width() + max_value * 0.03,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.2f}",
                va="center",
                ha="left",
                fontsize=9,
                color="#1f2937",
            )

    axes[0].invert_yaxis()
    fig.suptitle("Main Consistency Ablation under Grouped CV", y=1.03, fontsize=15, fontweight="bold")
    return save(fig, "figure_04_grouped_main_results.png")


def short_feature_name(feature: str) -> str:
    mapping = {
        "consistency_tri_layer_sensor_bridge_fail": "Tri: sensor + bridge fail",
        "consistency_native_webview_debug_cleartext_tension": "N-WV: debug + cleartext",
        "consistency_native_web_model_ua_strength": "N-Web: model-UA strength",
        "consistency_tri_layer_failure_count": "Tri: failure count",
        "consistency_webview_web_ua_has_wv_token": "WV-Web: UA has wv token",
        "consistency_native_web_model_ua_match": "N-Web: model-UA match",
        "consistency_tri_layer_manual_timezone_or_adb": "Tri: manual + TZ/ADB",
        "consistency_native_webview_agent_android_version_match": "N-WV: Android match",
        "consistency_native_webview_agent_model_match": "N-WV: model match",
        "consistency_native_webview_agent_android_version_delta": "N-WV: Android delta",
        "consistency_native_webview_installer_manual": "N-WV: manual installer",
        "consistency_tri_layer_core_integrity_pass": "Tri: core integrity pass",
    }
    if feature in mapping:
        return mapping[feature]
    return feature.replace("consistency_", "").replace("_", " ")


def feature_group(feature: str) -> str:
    if feature.startswith("consistency_tri_layer"):
        return "tri_layer"
    if feature.startswith("consistency_native_webview"):
        return "native_webview"
    if feature.startswith("consistency_native_web"):
        return "native_web"
    if feature.startswith("consistency_webview_web"):
        return "webview_web"
    return "consistency"


def figure_consistency_feature_importance() -> Path:
    importance = load_csv("consistency_top_feature_importance.csv")
    top = (
        importance.loc[importance["config_id"] == "consistency_only"]
        .sort_values("importance", ascending=False)
        .head(12)
        .copy()
    )
    top["label"] = top["feature"].map(short_feature_name)
    top["group"] = top["feature"].map(feature_group)
    top = top.iloc[::-1]

    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    colors = [GROUP_COLORS[group] for group in top["group"]]
    bars = ax.barh(top["label"], top["importance"], color=colors, height=0.58)

    ax.set_title("Top Consistency Features Used by Random Forest")
    ax.set_xlabel("Feature importance")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    max_value = top["importance"].max()
    ax.set_xlim(0, max_value * 1.23)
    for bar, value in zip(bars, top["importance"]):
        ax.text(
            bar.get_width() + max_value * 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            ha="left",
            fontsize=9,
            color="#1f2937",
        )

    legend_handles = [
        Patch(facecolor=GROUP_COLORS["tri_layer"], label="Tri-layer semantic"),
        Patch(facecolor=GROUP_COLORS["native_webview"], label="Native-WebView"),
        Patch(facecolor=GROUP_COLORS["native_web"], label="Native-Web"),
        Patch(facecolor=GROUP_COLORS["webview_web"], label="WebView-Web"),
    ]
    ax.legend(handles=legend_handles, loc="lower right")

    return save(fig, "figure_05_consistency_feature_importance.png")


def main() -> None:
    setup_style()
    figure_source_distribution()
    figure_fold_distribution()
    figure_holdout_vs_grouped_mae()
    figure_grouped_main_results()
    figure_consistency_feature_importance()


if __name__ == "__main__":
    main()
