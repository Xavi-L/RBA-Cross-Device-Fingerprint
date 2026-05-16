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
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch


CM = 1 / 2.54
FIG_WIDTH_CM = 15.0
DPI = 600
FONT_SIZE = 10.5
FONT_CN = FontProperties(family="Songti SC", size=FONT_SIZE)
FONT_CN_BOLD = FontProperties(family="Songti SC", size=FONT_SIZE, weight="bold")
FONT_EN = FontProperties(family="Times New Roman", size=FONT_SIZE)
FONT_EN_BOLD = FontProperties(family="Times New Roman", size=FONT_SIZE, weight="bold")

INK = "#222222"
MUTED = "#666666"
GRID = "#E7EDF5"

SOURCE_ORDER = ["physical_device", "cloud_device", "script_attack"]
SOURCE_LABELS = {
    "physical_device": "Physical",
    "cloud_device": "Cloud",
    "script_attack": "Script",
}
SOURCE_LABELS_COMPACT = {
    "physical_device": "Phys.",
    "cloud_device": "Cloud",
    "script_attack": "Script",
}
SOURCE_COLORS = {
    "physical_device": "#2F80ED",
    "cloud_device": "#27AE60",
    "script_attack": "#F2994A",
}

GROUP_COLORS = {
    "raw": "#8DA0B6",
    "raw_plus": "#9B51E0",
    "native_web": "#27AE60",
    "native_webview": "#2F80ED",
    "webview_web": "#F2C94C",
    "tri_layer": "#EB5757",
    "consistency": "#9B51E0",
}

HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "hybridguard_heatmap",
    ["#F7FBFF", "#D6EAF8", "#7FC8F8", "#2F80ED", "#1455C0"],
)


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / name)


def figure_size(height_cm: float) -> tuple[float, float]:
    return (FIG_WIDTH_CM * CM, height_cm * CM)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": "Times New Roman",
            "font.size": FONT_SIZE,
            "axes.titlesize": FONT_SIZE,
            "axes.labelsize": FONT_SIZE,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.alpha": 0.6,
            "legend.frameon": False,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "legend.fontsize": FONT_SIZE,
            "legend.title_fontsize": FONT_SIZE,
            "axes.unicode_minus": False,
            "savefig.dpi": DPI,
        }
    )


def save(fig: plt.Figure, filename: str) -> Path:
    FIG_DIR.mkdir(exist_ok=True)
    output = FIG_DIR / filename
    fig.savefig(output, dpi=DPI)
    plt.close(fig)
    print(output.relative_to(ROOT))
    return output


def set_en_legend(legend) -> None:
    for text in legend.get_texts():
        text.set_fontproperties(FONT_EN)
    legend.get_title().set_fontproperties(FONT_EN)


def draw_donut(ax: plt.Axes, values: pd.Series, title: str, center_label: str) -> None:
    colors = [SOURCE_COLORS[source] for source in SOURCE_ORDER]
    total = values.sum()

    ax.pie(
        values.to_numpy(),
        startangle=92,
        counterclock=False,
        colors=colors,
        wedgeprops={"width": 0.36, "edgecolor": "white", "linewidth": 3},
    )

    ax.text(
        0,
        0.04,
        f"{int(total):,}",
        ha="center",
        va="center",
        fontproperties=FONT_EN_BOLD,
        color=INK,
    )
    ax.text(0, -0.28, center_label, ha="center", va="center", fontproperties=FONT_EN, color=MUTED)
    ax.set_title(title, pad=12, fontproperties=FONT_EN_BOLD)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


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

    fig, axes = plt.subplots(1, 2, figsize=figure_size(7.0))
    draw_donut(axes[0], samples, "Samples", "samples")
    draw_donut(axes[1], groups, "Device/template groups", "groups")

    legend_labels = [SOURCE_LABELS[source] for source in SOURCE_ORDER]
    legend_handles = [Patch(facecolor=SOURCE_COLORS[source], label=label) for source, label in zip(SOURCE_ORDER, legend_labels)]
    legend = fig.legend(handles=legend_handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.06))
    set_en_legend(legend)

    fig.suptitle("数据来源构成", y=0.97, fontproperties=FONT_CN_BOLD, color=INK)
    fig.text(
        0.5,
        0.88,
        "样本来源不均衡，分组评估可降低同源设备/模板泄漏。",
        ha="center",
        va="center",
        color=MUTED,
        fontproperties=FONT_CN,
    )
    fig.subplots_adjust(left=0.18, right=0.82, top=0.72, bottom=0.22, wspace=0.04)
    return save(fig, "figure_01_source_distribution.png")


def figure_fold_distribution() -> Path:
    fold_dist = load_csv("grouped_fold_source_distribution.csv")
    folds = sorted(fold_dist["fold"].unique())

    fig, axes = plt.subplots(1, 2, figsize=figure_size(7.8))
    panels = [
        (axes[0], "rows", "Test samples"),
        (axes[1], "groups", "Test groups"),
    ]

    for ax, metric, title in panels:
        pivot = (
            fold_dist.pivot(index="fold", columns="source_type", values=metric)
            .reindex(index=folds, columns=SOURCE_ORDER)
            .fillna(0)
        )
        matrix = pivot.to_numpy()
        totals = pivot.sum(axis=1).to_numpy()

        image = ax.imshow(matrix, cmap=HEATMAP_CMAP, aspect="auto")
        threshold = matrix.max() * 0.52
        for row_idx, (fold, total) in enumerate(zip(folds, totals)):
            for col_idx, source in enumerate(SOURCE_ORDER):
                value = matrix[row_idx, col_idx]
                text_color = "white" if value >= threshold else INK
                ax.text(
                    col_idx,
                    row_idx,
                    f"{int(value)}",
                    ha="center",
                    va="center",
                    fontproperties=FONT_EN_BOLD,
                    color=text_color,
                )
            ax.text(
                len(SOURCE_ORDER) + 0.18,
                row_idx,
                f"Total {int(total)}",
                ha="left",
                va="center",
                fontproperties=FONT_EN,
                color=MUTED,
            )

        ax.set_title(title, fontproperties=FONT_EN_BOLD)
        ax.set_xticks(np.arange(len(SOURCE_ORDER)))
        ax.set_xticklabels([SOURCE_LABELS_COMPACT[source] for source in SOURCE_ORDER], fontproperties=FONT_EN)
        ax.set_yticks(np.arange(len(folds)))
        ax.set_yticklabels([f"Fold {fold}" for fold in folds], fontproperties=FONT_EN)
        ax.set_xlim(-0.5, len(SOURCE_ORDER) + 1.18)
        ax.tick_params(axis="both", length=0)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle("分组交叉验证各折构成", y=0.97, fontproperties=FONT_CN_BOLD, color=INK)
    fig.text(
        0.5,
        0.88,
        "每一折均覆盖三类来源，并按设备组或脚本模板整体留出。",
        ha="center",
        va="center",
        color=MUTED,
        fontproperties=FONT_CN,
    )
    fig.subplots_adjust(left=0.10, right=0.96, top=0.76, bottom=0.14, wspace=0.42)
    return save(fig, "figure_02_fold_distribution.png")


def collect_holdout_vs_grouped() -> pd.DataFrame:
    holdout_coarse = load_csv("ablation_summary.csv")
    holdout_consistency = load_csv("consistency_ablation_summary.csv")
    grouped = load_csv("grouped_ablation_summary.csv")

    items = [
        ("web_only", "coarse_layer", "Web only"),
        ("webview_only", "coarse_layer", "WebView only"),
        ("raw_all", "consistency", "Raw all"),
        ("consistency_only", "consistency", "Cons. only"),
        ("native_webview_consistency", "consistency", "N-WV cons."),
        ("tri_layer_semantic", "consistency", "Tri semantic"),
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
    comparison["delta"] = comparison["grouped_mae"] - comparison["holdout_mae"]
    comparison = comparison.sort_values("delta", ascending=False)
    y = np.arange(len(comparison))

    fig, ax = plt.subplots(figsize=figure_size(7.8))
    ax.axvline(0, color="#9AA6B2", linewidth=1.0, linestyle="--")
    max_delta = comparison["delta"].max()
    colors = [
        "#EB5757" if delta >= 4 else "#F2994A" if delta >= 1.5 else "#2F80ED"
        for delta in comparison["delta"]
    ]
    bars = ax.barh(y, comparison["delta"], color=colors, height=0.56, edgecolor="white", linewidth=1.2)

    for bar, row in zip(bars, comparison.itertuples(index=False)):
        ax.text(
            bar.get_width() + max_delta * 0.035,
            bar.get_y() + bar.get_height() / 2,
            f"+{row.delta:.2f} ({row.holdout_mae:.2f} -> {row.grouped_mae:.2f})",
            ha="left",
            va="center",
            fontproperties=FONT_EN,
            color=INK,
        )

    ax.set_title("Generalization gap after grouped split", fontproperties=FONT_EN_BOLD)
    ax.set_xlabel("MAE increase (Grouped CV - random holdout)", fontproperties=FONT_EN)
    ax.set_yticks(y)
    ax.set_yticklabels(comparison["label"], fontproperties=FONT_EN)
    ax.invert_yaxis()
    ax.set_xlim(-0.25, max_delta * 1.58)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.suptitle("随机留出的误差偏乐观", y=0.97, fontproperties=FONT_CN_BOLD, color=INK)
    fig.text(
        0.5,
        0.88,
        "横轴表示分组交叉验证相对随机留出增加的 MAE。",
        ha="center",
        va="center",
        color=MUTED,
        fontproperties=FONT_CN,
    )
    fig.subplots_adjust(left=0.19, right=0.96, top=0.74, bottom=0.16)
    return save(fig, "figure_03_holdout_vs_grouped_mae.png")


def collect_grouped_main_results() -> pd.DataFrame:
    grouped = load_csv("grouped_ablation_summary.csv")
    items = [
        ("raw_all", "consistency", "Raw all"),
        ("raw_clean", "consistency", "Raw cleaned"),
        ("consistency_only", "consistency", "Cons. only"),
        ("raw_all_plus_consistency", "consistency", "Raw+cons."),
        ("raw_clean_plus_consistency", "consistency", "Cleaned+cons."),
        ("native_webview_consistency", "consistency", "N-WV cons."),
        ("tri_layer_semantic", "consistency", "Tri semantic"),
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
    fig, (ax, table_ax) = plt.subplots(
        1,
        2,
        figsize=figure_size(9.2),
        gridspec_kw={"width_ratios": [1.28, 0.72]},
    )

    raw_all = results.loc[results["label"] == "Raw all"].iloc[0]
    ax.axvline(raw_all["mae"], color="#9AA6B2", linestyle="--", linewidth=1.0, zorder=0)
    ax.axhline(raw_all["rmse"], color="#9AA6B2", linestyle="--", linewidth=1.0, zorder=0)

    def point_color(label: str) -> str:
        if label == "Tri semantic":
            return GROUP_COLORS["tri_layer"]
        if label == "N-WV cons.":
            return GROUP_COLORS["native_webview"]
        if "cons." in label or label == "Cons. only":
            return GROUP_COLORS["consistency"]
        return GROUP_COLORS["raw"]

    def point_size(feature_count: int) -> float:
        return 68 + np.sqrt(feature_count) * 36

    number_offsets = {
        "Tri semantic": (16, 8),
        "N-WV cons.": (-24, -18),
        "Raw cleaned": (-22, 18),
        "Raw all": (24, -16),
        "Cleaned+cons.": (-26, 20),
        "Cons. only": (18, -22),
        "Raw+cons.": (28, 14),
    }

    display_rows = list(results.itertuples(index=False))
    for idx, row in enumerate(display_rows, start=1):
        color = point_color(row.label)
        marker = "*" if row.label == "Tri semantic" else "o"
        ax.scatter(
            row.mae,
            row.rmse,
            s=point_size(row.feature_count),
            color=color,
            marker=marker,
            edgecolor="white",
            linewidth=1.6,
            alpha=0.95,
            zorder=3,
        )
        offset = number_offsets[row.label]
        ax.annotate(
            str(idx),
            xy=(row.mae, row.rmse),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            va="center",
            fontproperties=FONT_EN_BOLD,
            color="white",
            bbox={"boxstyle": "circle,pad=0.18", "facecolor": color, "edgecolor": "white", "linewidth": 1.0},
            arrowprops={
                "arrowstyle": "-",
                "color": "#C7D2E0",
                "lw": 0.8,
                "shrinkA": 4,
                "shrinkB": 5,
            },
            zorder=4,
        )

    x_min = max(0, results["mae"].min() - 0.42)
    x_max = results["mae"].max() + 0.22
    y_min = max(0, results["rmse"].min() - 0.48)
    y_max = results["rmse"].max() + 0.48
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("MAE (lower is better)", fontproperties=FONT_EN)
    ax.set_ylabel("RMSE (lower is better)", fontproperties=FONT_EN)
    ax.grid(True, axis="both")
    ax.text(
        0.04,
        0.96,
        "Dashed lines: Raw all baseline",
        transform=ax.transAxes,
        color=MUTED,
        fontproperties=FONT_EN,
        ha="left",
        va="top",
    )

    table_ax.set_axis_off()
    table_ax.text(0.00, 0.98, "Config / dim.", transform=table_ax.transAxes, fontproperties=FONT_EN_BOLD, color=INK, va="top")

    for idx, row in enumerate(display_rows, start=1):
        y_pos = 0.84 - (idx - 1) * 0.105
        color = point_color(row.label)
        marker = "*" if row.label == "Tri semantic" else "o"
        table_ax.scatter(0.04, y_pos, s=70, color=color, marker=marker, edgecolor="white", linewidth=1.0, transform=table_ax.transAxes)
        table_ax.text(0.10, y_pos, str(idx), transform=table_ax.transAxes, fontproperties=FONT_EN_BOLD, color=INK, va="center")
        table_ax.text(0.20, y_pos, row.label, transform=table_ax.transAxes, fontproperties=FONT_EN, color=INK, va="center")
        table_ax.text(0.94, y_pos, f"{row.feature_count}", transform=table_ax.transAxes, fontproperties=FONT_EN, color=INK, ha="right", va="center")

    table_ax.text(
        0.02,
        0.06,
        "Bubble size = feature count",
        transform=table_ax.transAxes,
        fontproperties=FONT_EN,
        color=MUTED,
        va="bottom",
    )

    fig.suptitle("分组交叉验证下的一致性消融主结果", y=0.97, fontproperties=FONT_CN_BOLD, color=INK)
    fig.text(
        0.5,
        0.88,
        "三端语义仅用 7 个特征，即低于原始三端基线。",
        ha="center",
        va="center",
        color=MUTED,
        fontproperties=FONT_CN,
    )
    fig.subplots_adjust(left=0.11, right=0.97, top=0.78, bottom=0.14, wspace=0.10)
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

    fig, ax = plt.subplots(figsize=figure_size(10.6))
    colors = [GROUP_COLORS[group] for group in top["group"]]
    y = np.arange(len(top))
    bars = ax.barh(y, top["importance"], color=colors, height=0.58, edgecolor="white", linewidth=1.1)

    ax.set_yticks(y)
    ax.set_yticklabels(top["label"], fontproperties=FONT_EN)
    ax.invert_yaxis()
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    max_value = top["importance"].max()
    ax.set_xlim(0, max_value * 1.28)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    for bar, value in zip(bars, top["importance"]):
        ax.text(
            value + max_value * 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            ha="left",
            fontproperties=FONT_EN,
            color=INK,
        )

    legend_handles = [
        Patch(facecolor=GROUP_COLORS["tri_layer"], label="Tri-layer"),
        Patch(facecolor=GROUP_COLORS["native_webview"], label="Native-WebView"),
        Patch(facecolor=GROUP_COLORS["native_web"], label="Native-Web"),
        Patch(facecolor=GROUP_COLORS["webview_web"], label="WebView-Web"),
    ]
    legend = ax.legend(handles=legend_handles, loc="lower right", prop=FONT_EN)
    set_en_legend(legend)

    ax.set_xlabel("Feature importance", fontproperties=FONT_EN)
    fig.suptitle("跨层一致性特征重要性", y=0.97, fontproperties=FONT_CN_BOLD, color=INK)
    fig.text(
        0.5,
        0.88,
        "重要信号主要来自跨层完整性与 Native-WebView 对齐关系。",
        ha="center",
        va="center",
        color=MUTED,
        fontproperties=FONT_CN,
    )
    fig.subplots_adjust(left=0.40, right=0.96, top=0.78, bottom=0.12)
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
