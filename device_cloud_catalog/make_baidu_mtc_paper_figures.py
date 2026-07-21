#!/usr/bin/env python3
"""Generate publication-ready Baidu MTC Android catalog figures.

The source CSV is a catalog snapshot rather than a device-usage sample.  This
script deliberately removes Android 4.4.x records and exact duplicate
``device_label`` configurations before plotting, so every percentage in the
main figures uses the same, auditable unit: a unique catalog configuration.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

# Configure Matplotlib before importing it.  The workspace cannot always write
# to the user's default Matplotlib cache directory.
MPLCONFIG_DIR = Path(tempfile.gettempdir()) / "baidu-mtc-mplconfig"
MPLCONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIG_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = REPO_ROOT / "device_cloud_catalog"
CSV_PATH = CATALOG_DIR / "baidu_mtc_android_custom_models.csv"
OUTPUT_DIR = REPO_ROOT / "thesis_materials" / "top_journal_figures"

CM = 1 / 2.54
FIG_WIDTH_CM = 15.0
DPI = 600
FONT_SIZE = 9.5

# Match the project’s existing paper figures: Chinese captions can be added in
# Word/LaTex, while the vector masters remain suitable for English papers.
FONT_EN = FontProperties(family="Times New Roman", size=FONT_SIZE)
FONT_EN_BOLD = FontProperties(family="Times New Roman", size=FONT_SIZE, weight="bold")
FONT_EN_SMALL = FontProperties(family="Times New Roman", size=8.2)
FONT_EN_SMALL_BOLD = FontProperties(family="Times New Roman", size=8.2, weight="bold")

INK = "#1F2933"
MUTED = "#66788A"
GRID = "#DCE5ED"
SLATE = "#9AA9B8"
SLATE_LIGHT = "#EAF0F5"
PLUM = "#8063A3"
PLUM_DARK = "#583F71"
PLUM_LIGHT = "#E3D7ED"
TEAL = "#2A9D8F"
TEAL_DARK = "#1D796E"
TEAL_LIGHT = "#CAE7DF"
GOLD = "#E5A23D"
GOLD_DARK = "#A56716"
GOLD_LIGHT = "#F7E5B9"
ORANGE = "#D55E00"  # Reserved for exclusions / foldable overlays.
VERSION_CMAP = LinearSegmentedColormap.from_list(
    "android_generation", [PLUM_LIGHT, "#B9A5D0", TEAL, GOLD]
)
HEATMAP = LinearSegmentedColormap.from_list(
    "mtc_plum", ["#FBF8FC", "#E4D8ED", "#B99DCB", "#86639A", PLUM_DARK]
)

EXCLUDED_PATTERN = re.compile(r"^4\.4(?:\.|$)")
ANDROID_MAJOR_PATTERN = re.compile(r"^\s*(\d+)")
RESOLUTION_PATTERN = re.compile(r"^\s*(\d+)x(\d+)\s*$", re.IGNORECASE)


# Only spelling, language, case, or notation aliases are merged.  Product and
# sub-brand labels (e.g. HONOR, Redmi, iQOO, Civi) deliberately remain distinct.
BRAND_ALIASES = {
    "vivo": "vivo",
    "VIVO": "vivo",
    "荣耀(HONOR)": "HONOR",
    "iQOO(VIVO)": "iQOO",
    "Realme(真我)": "realme",
    "魅族(Meizu)": "Meizu",
    "努比亚(nubia)": "nubia",
    "联想(Lenovo)": "Lenovo",
    "三星(SAMSUNG)": "Samsung",
    "SAMSUNG(三星)": "Samsung",
    "华为(HUAWEI)": "Huawei",
    "HUAWEI(华为)": "Huawei",
    "小米(Xiaomi)": "Xiaomi",
    "Xiaomi(小米)": "Xiaomi",
    "红米(Redmi)": "Redmi",
    "Redmi(红米)": "Redmi",
    "一加(OnePlus)": "OnePlus",
    "OnePlus(一加)": "OnePlus",
    "SONY(索尼)": "Sony",
    "索尼(SONY)": "Sony",
    "谷歌(Google)": "Google",
    "Google": "Google",
    "MOTO(摩托罗拉)": "Motorola",
    "摩托罗拉(moto)": "Motorola",
    "诺基亚(Nokia)": "Nokia",
    "Nokia(诺基亚)": "Nokia",
    "ASUS(华硕)": "ASUS",
    "华硕(ASUS)": "ASUS",
    "SHARP(夏普)": "SHARP",
    "夏普(SHARP)": "SHARP",
}


def figure_size(height_cm: float) -> tuple[float, float]:
    """Return a standard thesis-figure size in inches."""

    return (FIG_WIDTH_CM * CM, height_cm * CM)


def setup_style() -> None:
    """Apply the restrained, vector-friendly house style."""

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "font.family": "Times New Roman",
            "font.size": FONT_SIZE,
            "axes.titlesize": FONT_SIZE,
            "axes.labelsize": FONT_SIZE,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.65,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.65,
            "grid.alpha": 0.9,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.major.width": 0.65,
            "ytick.major.width": 0.65,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
        }
    )


def parse_android_major(value: str) -> int:
    """Extract a robust Android major version, including preview labels."""

    match = ANDROID_MAJOR_PATTERN.match(str(value))
    if not match:
        raise ValueError(f"Cannot parse Android version: {value!r}")
    return int(match.group(1))


def parse_resolution(value: str) -> tuple[int, int]:
    """Return a portrait-agnostic (short edge, long edge) pixel pair."""

    match = RESOLUTION_PATTERN.match(str(value))
    if not match:
        raise ValueError(f"Cannot parse resolution: {value!r}")
    first, second = (int(part) for part in match.groups())
    return min(first, second), max(first, second)


def normalize_brand(value: str) -> str:
    """Merge known presentation aliases without merging distinct sub-brands."""

    return BRAND_ALIASES.get(value, value)


def load_analysis_data() -> tuple[pd.DataFrame, dict[str, int], pd.DataFrame]:
    """Load source rows, apply exclusions, then deduplicate configurations."""

    raw = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype=str).fillna("")
    required = {
        "brand_group",
        "device_name",
        "android_version",
        "resolution",
        "device_label",
        "is_overseas_label",
        "is_foldable_label",
    }
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"CSV is missing expected columns: {sorted(missing)}")

    is_android_44 = raw["android_version"].str.strip().str.match(EXCLUDED_PATTERN)
    excluded = raw.loc[is_android_44].copy()
    filtered = raw.loc[~is_android_44].copy()
    analysis = filtered.drop_duplicates(subset="device_label", keep="first").copy()

    # Guard the requested exclusion and the known catalog state from silently
    # drifting into an unreviewed new figure version.
    if len(excluded) != 4:
        raise ValueError(f"Expected four Android 4.4.x entries, found {len(excluded)}")
    if len(raw) != 1064 or len(filtered) != 1060 or len(analysis) != 1029:
        raise ValueError(
            "Unexpected catalog size after filtering/deduplication: "
            f"raw={len(raw)}, filtered={len(filtered)}, analysis={len(analysis)}"
        )

    analysis["android_major"] = analysis["android_version"].map(parse_android_major)
    analysis["brand_normalized"] = analysis["brand_group"].map(normalize_brand)
    resolution_pairs = analysis["resolution"].map(parse_resolution)
    analysis["short_edge_px"] = resolution_pairs.map(lambda item: item[0])
    analysis["long_edge_px"] = resolution_pairs.map(lambda item: item[1])

    stats = {
        "raw_entries": len(raw),
        "excluded_android_44": len(excluded),
        "version_filtered_entries": len(filtered),
        "exact_duplicate_entries": len(filtered) - len(analysis),
        "unique_configurations": len(analysis),
        "unique_device_names": analysis["device_name"].nunique(),
        "resolution_profiles": analysis["resolution"].nunique(),
        "overseas_labelled": int((analysis["is_overseas_label"] == "是").sum()),
        "foldable_labelled": int((analysis["is_foldable_label"] == "是").sum()),
    }
    return analysis, stats, excluded


def set_axis_fonts(ax: plt.Axes) -> None:
    """Make ticks and axis labels consistently English-paper sized."""

    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(FONT_EN_SMALL)
    ax.xaxis.label.set_fontproperties(FONT_EN)
    ax.yaxis.label.set_fontproperties(FONT_EN)
    ax.title.set_fontproperties(FONT_EN_BOLD)


def save_figure(fig: plt.Figure, stem: str) -> list[Path]:
    """Write editable vector masters plus a Word/PPT-ready raster copy."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for suffix in ("svg", "pdf", "png"):
        path = OUTPUT_DIR / f"{stem}.{suffix}"
        fig.savefig(path, dpi=DPI)
        paths.append(path)
    plt.close(fig)
    return paths


def add_panel_label(ax: plt.Axes, label: str) -> None:
    """Add a small top-left panel label without introducing card chrome."""

    ax.text(
        -0.12,
        1.06,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        color=PLUM_DARK,
        fontproperties=FONT_EN_BOLD,
    )


def annotate_bar_values(
    ax: plt.Axes,
    bars: Iterable,
    total: int,
    *,
    horizontal: bool = False,
    offset: float = 2.0,
) -> None:
    """Directly label counts and shares so the reader need not estimate."""

    for bar in bars:
        if horizontal:
            value = bar.get_width()
            ax.text(
                value + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{int(value)}  ({value / total:.1%})",
                ha="left",
                va="center",
                color=INK,
                fontproperties=FONT_EN_SMALL,
            )
        else:
            value = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + offset,
                f"{int(value)}",
                ha="center",
                va="bottom",
                color=INK,
                fontproperties=FONT_EN_SMALL,
            )


def draw_filter_ribbon(ax: plt.Axes, stats: dict[str, int]) -> None:
    """Show every scope decision in one thin, auditable provenance ribbon."""

    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    boxes = [
        (0.01, 0.10, 0.19, SLATE_LIGHT, PLUM_DARK, f"{stats['raw_entries']:,}", "Raw catalog entries"),
        (0.30, 0.10, 0.19, TEAL_LIGHT, TEAL_DARK, f"{stats['version_filtered_entries']:,}", "After Android 4.4.x exclusion"),
        (0.59, 0.10, 0.23, GOLD_LIGHT, GOLD_DARK, f"{stats['unique_configurations']:,}", "Unique catalog configurations"),
    ]
    for x, y, width, facecolor, value_color, value, label in boxes:
        patch = FancyBboxPatch(
            (x, y),
            width,
            0.44,
            boxstyle="round,pad=0.008,rounding_size=0.025",
            linewidth=0.8,
            edgecolor=GRID,
            facecolor=facecolor,
        )
        ax.add_patch(patch)
        ax.text(
            x + width / 2,
            y + 0.29,
            value,
            ha="center",
            va="center",
            color=value_color,
            fontproperties=FONT_EN_BOLD,
        )
        ax.text(
            x + width / 2,
            y + 0.12,
            label,
            ha="center",
            va="center",
            color=MUTED,
            fontproperties=FONT_EN_SMALL,
        )

    arrow_style = dict(arrowstyle="-|>", mutation_scale=10, linewidth=0.9, color=MUTED)
    ax.add_patch(FancyArrowPatch((0.205, 0.32), (0.295, 0.32), **arrow_style))
    ax.add_patch(FancyArrowPatch((0.495, 0.32), (0.585, 0.32), **arrow_style))
    ax.text(
        0.25,
        0.66,
        f"−{stats['excluded_android_44']} Android 4.4.x",
        ha="center",
        va="bottom",
        color=ORANGE,
        fontproperties=FONT_EN_SMALL_BOLD,
    )
    ax.text(
        0.54,
        0.66,
        f"−{stats['exact_duplicate_entries']} exact duplicate labels",
        ha="center",
        va="bottom",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    ax.text(
        0.01,
        0.98,
        "Scope and counting unit",
        ha="left",
        va="top",
        color=INK,
        fontproperties=FONT_EN_BOLD,
    )


def plot_version_distribution(ax: plt.Axes, data: pd.DataFrame, total: int) -> None:
    """Draw the Android-major distribution for the shared analysis unit."""

    versions = list(range(5, 18))
    counts = data["android_major"].value_counts().reindex(versions, fill_value=0)
    color_values = np.linspace(0.0, 1.0, len(versions))
    bar_colors = [VERSION_CMAP(value) for value in color_values]
    bar_colors[-1] = PLUM_DARK
    bars = ax.bar(versions, counts.to_numpy(), width=0.72, color=bar_colors, edgecolor="white", linewidth=0.7)
    annotate_bar_values(ax, bars, total, offset=2.7)
    ax.set_xlim(4.35, 17.65)
    ax.set_ylim(0, max(counts) * 1.24)
    ax.set_xticks(versions)
    ax.set_xticklabels([str(version) if version != 17 else "17*" for version in versions])
    ax.set_xlabel("Android major version")
    ax.set_ylabel("Configurations")
    ax.set_title("Android-version coverage", loc="left", pad=10)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    set_axis_fonts(ax)
    add_panel_label(ax, "A")
    android_11_plus = int(counts.loc[11:].sum())
    ax.text(
        0.995,
        0.93,
        f"Android 11+: {android_11_plus:,} ({android_11_plus / total:.1%})",
        transform=ax.transAxes,
        ha="right",
        va="top",
        color=TEAL_DARK,
        fontproperties=FONT_EN_SMALL_BOLD,
    )


def normalized_brand_counts(data: pd.DataFrame) -> pd.Series:
    """Return descending counts under the conservative alias-normalization rule."""

    return data["brand_normalized"].value_counts()


def plot_brand_pareto(ax: plt.Axes, data: pd.DataFrame, total: int) -> None:
    """Draw top ten normalized brand categories plus their long tail."""

    counts = normalized_brand_counts(data)
    top = counts.head(10)
    other = int(counts.iloc[10:].sum())
    labels = list(top.index) + ["Other"]
    values = list(top.to_numpy()) + [other]
    colors = [TEAL] * len(top) + [PLUM]
    positions = np.arange(len(labels))
    bars = ax.barh(positions, values, color=colors, height=0.64, edgecolor="white", linewidth=0.7)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) * 1.42)
    ax.set_xlabel("Configurations")
    ax.set_title("Top brand categories", loc="left", pad=10)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    annotate_bar_values(ax, bars, total, horizontal=True, offset=max(values) * 0.035)
    set_axis_fonts(ax)
    add_panel_label(ax, "B")


def figure_catalog_scope_and_composition(data: pd.DataFrame, stats: dict[str, int]) -> list[Path]:
    """Create main Fig. 4-1: filtering provenance and two primary marginals."""

    fig = plt.figure(figsize=figure_size(12.0))
    grid = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.55, 5.35],
        width_ratios=[1.0, 1.02],
        left=0.10,
        right=0.96,
        top=0.94,
        bottom=0.20,
        hspace=0.42,
        wspace=0.42,
    )
    ribbon = fig.add_subplot(grid[0, :])
    version_ax = fig.add_subplot(grid[1, 0])
    brand_ax = fig.add_subplot(grid[1, 1])
    draw_filter_ribbon(ribbon, stats)
    plot_version_distribution(version_ax, data, stats["unique_configurations"])
    plot_brand_pareto(brand_ax, data, stats["unique_configurations"])
    fig.text(
        0.10,
        0.088,
        "Analysis unit: unique device_label configuration.  "
        f"{stats['resolution_profiles']} display profiles · "
        f"{stats['overseas_labelled']} overseas-labelled · "
        f"{stats['foldable_labelled']} foldable-labelled.",
        ha="left",
        va="center",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    fig.text(
        0.10,
        0.046,
        "* Android 17 labels are preview/beta entries in the catalog.",
        ha="left",
        va="center",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    return save_figure(fig, "fig4-1_baidu_mtc_catalog_scope_and_composition")


def figure_brand_android_coverage(data: pd.DataFrame, stats: dict[str, int]) -> list[Path]:
    """Create main Fig. 4-2: top-brand by Android-major coverage matrix."""

    brand_counts = normalized_brand_counts(data)
    top_brands = list(brand_counts.head(12).index)
    data_for_matrix = data.copy()
    data_for_matrix["matrix_brand"] = np.where(
        data_for_matrix["brand_normalized"].isin(top_brands),
        data_for_matrix["brand_normalized"],
        "Other",
    )
    row_order = top_brands + ["Other"]
    column_order = list(range(5, 18))
    matrix = (
        data_for_matrix.groupby(["matrix_brand", "android_major"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=row_order, columns=column_order, fill_value=0)
    )
    row_totals = matrix.sum(axis=1)
    col_totals = matrix.sum(axis=0)

    fig = plt.figure(figsize=figure_size(10.5))
    grid = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.25, 8.5],
        width_ratios=[1.3, 8.7],
        left=0.17,
        right=0.93,
        top=0.86,
        bottom=0.23,
        hspace=0.10,
        wspace=0.10,
    )
    corner_ax = fig.add_subplot(grid[0, 0])
    top_ax = fig.add_subplot(grid[0, 1])
    left_ax = fig.add_subplot(grid[1, 0])
    heat_ax = fig.add_subplot(grid[1, 1])
    corner_ax.set_axis_off()

    image = heat_ax.imshow(matrix.to_numpy(), aspect="auto", cmap=HEATMAP, interpolation="nearest")
    threshold = float(matrix.to_numpy().max()) * 0.56
    for row_index, row in enumerate(matrix.to_numpy()):
        for col_index, value in enumerate(row):
            if value >= 8:
                heat_ax.text(
                    col_index,
                    row_index,
                    str(int(value)),
                    ha="center",
                    va="center",
                    color="white" if value >= threshold else INK,
                    fontproperties=FONT_EN_SMALL_BOLD,
                )
    heat_ax.set_xticks(np.arange(len(column_order)))
    heat_ax.set_xticklabels([str(value) if value != 17 else "17*" for value in column_order])
    heat_ax.set_yticks(np.arange(len(row_order)))
    heat_ax.set_yticklabels(row_order)
    heat_ax.set_xlabel("Android major version")
    heat_ax.set_ylabel("")
    heat_ax.tick_params(axis="both", length=0)
    heat_ax.grid(False)
    heat_ax.axvline(column_order.index(11) - 0.5, color=INK, linewidth=0.8, alpha=0.45)
    set_axis_fonts(heat_ax)

    y_positions = np.arange(len(row_order))
    left_ax.barh(y_positions, row_totals.to_numpy(), height=0.64, color=GOLD_LIGHT, edgecolor="none")
    left_ax.invert_yaxis()
    left_ax.set_ylim(len(row_order) - 0.5, -0.5)
    left_ax.set_yticks([])
    left_ax.set_xlabel("Total", labelpad=3)
    left_ax.grid(axis="x")
    left_ax.grid(axis="y", visible=False)
    left_ax.spines["left"].set_visible(False)
    set_axis_fonts(left_ax)

    x_positions = np.arange(len(column_order))
    top_ax.bar(x_positions, col_totals.to_numpy(), width=0.66, color=GOLD_LIGHT, edgecolor="none")
    top_ax.set_xlim(-0.5, len(column_order) - 0.5)
    top_ax.set_xticks([])
    top_ax.set_ylabel("Total", labelpad=3)
    top_ax.grid(axis="y")
    top_ax.grid(axis="x", visible=False)
    top_ax.spines["bottom"].set_visible(False)
    set_axis_fonts(top_ax)

    colorbar = fig.colorbar(image, ax=heat_ax, fraction=0.038, pad=0.028)
    colorbar.set_label("Configurations", fontproperties=FONT_EN_SMALL)
    colorbar.ax.tick_params(labelsize=8.0, length=2)
    for label in colorbar.ax.get_yticklabels():
        label.set_fontproperties(FONT_EN_SMALL)
    fig.text(
        0.17,
        0.935,
        "Brand–Android coverage matrix",
        ha="left",
        va="bottom",
        color=INK,
        fontproperties=FONT_EN_BOLD,
    )
    fig.text(
        0.17,
        0.095,
        "Labels shown for n ≥ 8.  The Android 11 rule is a reference boundary.",
        ha="left",
        va="center",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    fig.text(
        0.17,
        0.050,
        "* Android 17 labels are preview/beta entries in the catalog.",
        ha="left",
        va="center",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    return save_figure(fig, "fig4-2_baidu_mtc_brand_android_coverage")


def figure_display_geometry(data: pd.DataFrame, stats: dict[str, int]) -> list[Path]:
    """Create main Fig. 4-3: resolution geometry and foldable coverage."""

    profiles = (
        data.groupby(["resolution", "short_edge_px", "long_edge_px"], as_index=False)
        .agg(
            configurations=("device_label", "size"),
            foldable_configurations=("is_foldable_label", lambda values: int((values == "是").sum())),
        )
        .sort_values("configurations", ascending=False)
    )
    max_count = float(profiles["configurations"].max())
    bubble_area = 16 + 720 * np.sqrt(profiles["configurations"] / max_count)

    fig, ax = plt.subplots(figsize=figure_size(9.2))
    ax.scatter(
        profiles["short_edge_px"],
        profiles["long_edge_px"],
        s=bubble_area,
        facecolor=TEAL,
        edgecolor="white",
        linewidth=0.7,
        alpha=0.68,
        zorder=3,
    )
    foldable = profiles.loc[profiles["foldable_configurations"] > 0]
    if not foldable.empty:
        foldable_area = 26 + 92 * np.sqrt(foldable["foldable_configurations"] / foldable["foldable_configurations"].max())
        ax.scatter(
            foldable["short_edge_px"],
            foldable["long_edge_px"],
            s=foldable_area,
            marker="D",
            facecolor="white",
            edgecolor=ORANGE,
            linewidth=1.25,
            zorder=5,
        )

    reference_x = np.linspace(450, 1750, 120)
    for ratio, label, x_anchor in ((16 / 9, "16:9", 730), (2.0, "18:9", 900), (20 / 9, "20:9", 1550)):
        reference_y = ratio * reference_x
        visible = reference_y <= 3900
        ax.plot(reference_x[visible], reference_y[visible], color=GRID, linewidth=0.9, linestyle="--", zorder=1)
        y_anchor = ratio * x_anchor
        ax.text(
            x_anchor,
            y_anchor + 38,
            label,
            ha="left",
            va="bottom",
            color=MUTED,
            fontproperties=FONT_EN_SMALL,
        )

    label_positions = {
        "2400x1080": (1110, 2770),
        "2160x1080": (1110, 2515),
        "2340x1080": (1110, 1840),
        "1920x1080": (1110, 1545),
    }
    for profile in profiles.head(4).itertuples(index=False):
        ax.annotate(
            f"{profile.long_edge_px}×{profile.short_edge_px}  (n={profile.configurations})",
            xy=(profile.short_edge_px, profile.long_edge_px),
            xytext=label_positions.get(profile.resolution, (profile.short_edge_px + 45, profile.long_edge_px + 50)),
            textcoords="data",
            ha="left",
            va="center",
            color=INK,
            fontproperties=FONT_EN_SMALL_BOLD,
            arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.55},
            zorder=6,
        )

    ax.set_xlim(400, 2300)
    ax.set_ylim(650, 4000)
    ax.set_xlabel("Short edge (px)")
    ax.set_ylabel("Long edge (px)")
    ax.set_title("Display-geometry coverage", loc="left", pad=10)
    ax.grid(True)
    set_axis_fonts(ax)
    legend_handles = [
        Line2D(
            [0], [0], marker="o", markersize=8, linestyle="", markerfacecolor=TEAL,
            markeredgecolor="white", label="Resolution profile (area scales with configurations)"
        ),
        Line2D(
            [0], [0], marker="D", markersize=7, linestyle="", markerfacecolor="white",
            markeredgecolor=ORANGE, markeredgewidth=1.2, label="Foldable-labelled configuration"
        ),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.01, 0.98),
        handletextpad=0.45,
        labelspacing=0.38,
        prop=FONT_EN_SMALL,
    )
    ax.text(
        0.995,
        0.02,
        f"{stats['resolution_profiles']} unique resolutions · {stats['foldable_labelled']} foldable-labelled configurations",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    fig.subplots_adjust(left=0.14, right=0.97, top=0.90, bottom=0.20)
    fig.text(
        0.14,
        0.085,
        "Each point represents one resolution profile; point area scales with unique configurations.",
        ha="left",
        va="center",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    fig.text(
        0.14,
        0.045,
        "Reference lines indicate aspect ratios; resolutions are normalized to short and long pixel edges.",
        ha="left",
        va="center",
        color=MUTED,
        fontproperties=FONT_EN_SMALL,
    )
    return save_figure(fig, "fig4-3_baidu_mtc_display_geometry_landscape")


def figure_counting_unit_audit(stats: dict[str, int]) -> list[Path]:
    """Create Fig. S1 as a provenance flow rather than another bar chart."""

    fig, ax = plt.subplots(figsize=figure_size(6.3))
    fig.subplots_adjust(left=0.06, right=0.96, top=0.86, bottom=0.18)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    stages = [
        (0.03, SLATE_LIGHT, SLATE, f"{stats['raw_entries']:,}", "Raw catalog\nentries"),
        (0.36, TEAL_LIGHT, TEAL_DARK, f"{stats['version_filtered_entries']:,}", "After Android 4.4.x\nexclusion"),
        (0.69, GOLD_LIGHT, GOLD_DARK, f"{stats['unique_configurations']:,}", "Analysis unit: unique\ndevice_label configuration"),
    ]
    for x, facecolor, value_color, value, label in stages:
        box = FancyBboxPatch(
            (x, 0.48), 0.25, 0.27,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            linewidth=0.75, edgecolor=GRID, facecolor=facecolor,
        )
        ax.add_patch(box)
        ax.text(x + 0.125, 0.65, value, ha="center", va="center", color=value_color, fontproperties=FONT_EN_BOLD)
        ax.text(x + 0.125, 0.535, label, ha="center", va="center", color=INK, fontproperties=FONT_EN_SMALL)

    arrow_style = dict(arrowstyle="-|>", mutation_scale=11, linewidth=0.95, color=MUTED)
    ax.add_patch(FancyArrowPatch((0.29, 0.615), (0.345, 0.615), **arrow_style))
    ax.add_patch(FancyArrowPatch((0.62, 0.615), (0.675, 0.615), **arrow_style))
    ax.text(0.318, 0.715, f"exclude {stats['excluded_android_44']} Android 4.4.x", ha="center", va="bottom", color=ORANGE, fontproperties=FONT_EN_SMALL_BOLD)
    ax.text(0.648, 0.715, f"remove {stats['exact_duplicate_entries']} exact duplicate labels", ha="center", va="bottom", color=MUTED, fontproperties=FONT_EN_SMALL)

    audit_box = FancyBboxPatch(
        (0.29, 0.08), 0.40, 0.20,
        boxstyle="round,pad=0.012,rounding_size=0.025",
        linewidth=0.75, edgecolor=GRID, facecolor=PLUM_LIGHT,
    )
    ax.add_patch(audit_box)
    ax.text(0.49, 0.205, f"{stats['unique_device_names']:,}", ha="center", va="center", color=PLUM_DARK, fontproperties=FONT_EN_BOLD)
    ax.text(0.49, 0.125, "Unique device_name values (name-level audit)", ha="center", va="center", color=INK, fontproperties=FONT_EN_SMALL)
    ax.add_patch(FancyArrowPatch((0.815, 0.47), (0.69, 0.285), connectionstyle="arc3,rad=-0.18", **arrow_style))
    ax.text(0.75, 0.325, f"{stats['unique_configurations'] - stats['unique_device_names']} fewer names\nthan configurations", ha="center", va="center", color=MUTED, fontproperties=FONT_EN_SMALL)
    ax.text(0.03, 0.97, "Counting-unit audit", ha="left", va="top", color=INK, fontproperties=FONT_EN_BOLD)
    ax.text(0.03, 0.89, "The 1,029 unique configurations are the denominator used throughout the figure set.", ha="left", va="top", color=MUTED, fontproperties=FONT_EN_SMALL)
    return save_figure(fig, "figS1_baidu_mtc_counting_unit_audit")


def figure_android_major_profile(data: pd.DataFrame, stats: dict[str, int]) -> list[Path]:
    """Create Fig. S2 as a generation-coverage profile, not a bar chart."""

    versions = list(range(5, 18))
    counts = data["android_major"].value_counts().reindex(versions, fill_value=0)
    total = stats["unique_configurations"]
    android_11_plus = int(counts.loc[11:].sum())
    colors = [VERSION_CMAP(value) for value in np.linspace(0.0, 1.0, len(versions))]
    colors[-1] = PLUM_DARK

    fig, ax = plt.subplots(figsize=figure_size(6.1))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.84, bottom=0.32)
    ax.axvspan(4.5, 10.5, facecolor=PLUM_LIGHT, alpha=0.46, zorder=0)
    ax.axvspan(10.5, 16.5, facecolor=TEAL_LIGHT, alpha=0.46, zorder=0)
    ax.axvspan(16.5, 17.5, facecolor=GOLD_LIGHT, alpha=0.54, zorder=0)
    ax.plot(versions, counts.to_numpy(), color=INK, linewidth=1.15, zorder=2)
    ax.scatter(versions, counts.to_numpy(), s=54, c=colors, edgecolor="white", linewidth=0.8, zorder=3)
    for version, count in counts.items():
        ax.text(version, count + 5.5, str(int(count)), ha="center", va="bottom", color=INK, fontproperties=FONT_EN_SMALL_BOLD)
    ax.axvline(10.5, color=TEAL_DARK, linewidth=0.85, zorder=1)
    ax.text(7.5, 158, "Android 5–10", ha="center", va="center", color=PLUM_DARK, fontproperties=FONT_EN_SMALL_BOLD)
    ax.text(13.5, 158, "Study scope: Android 11+", ha="center", va="center", color=TEAL_DARK, fontproperties=FONT_EN_SMALL_BOLD)
    ax.text(17.0, 158, "Preview", ha="center", va="center", color=GOLD_DARK, fontproperties=FONT_EN_SMALL_BOLD)
    ax.set_xlim(4.5, 17.5)
    ax.set_ylim(0, 170)
    ax.set_xticks(versions)
    ax.set_xticklabels([str(version) if version != 17 else "17*" for version in versions])
    ax.set_xlabel("Android major version")
    ax.set_ylabel("Unique configurations")
    ax.set_title("Android-generation coverage profile", loc="left", pad=10)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    set_axis_fonts(ax)
    fig.text(0.12, 0.135, f"Research boundary Android 11+: {android_11_plus:,} unique configurations ({android_11_plus / total:.1%}).", ha="left", va="center", color=TEAL_DARK, fontproperties=FONT_EN_SMALL_BOLD)
    fig.text(0.12, 0.075, "* Android 17 labels are preview/beta entries; bands denote catalogue cohorts, not performance tiers.", ha="left", va="center", color=MUTED, fontproperties=FONT_EN_SMALL)
    return save_figure(fig, "figS2_baidu_mtc_android_major_distribution")


def figure_normalized_brand_profile(data: pd.DataFrame, stats: dict[str, int]) -> list[Path]:
    """Create Fig. S3 as a ranked dot profile with an explicit long-tail split."""

    counts = normalized_brand_counts(data)
    top = counts.head(5)
    other = int(counts.iloc[5:].sum())
    labels = list(top.index) + ["Other categories"]
    values = list(top.to_numpy()) + [other]
    shares = np.asarray(values, dtype=float) / stats["unique_configurations"] * 100
    y_positions = np.arange(len(labels))
    colors = [TEAL] * len(top) + [PLUM]
    sizes = 52 + np.asarray(values) * 0.38

    fig, ax = plt.subplots(figsize=figure_size(6.1))
    fig.subplots_adjust(left=0.24, right=0.94, top=0.84, bottom=0.25)
    ax.hlines(y_positions, 0, shares, color=GRID, linewidth=1.35, zorder=1)
    ax.scatter(shares, y_positions, s=sizes, c=colors, edgecolor="white", linewidth=0.9, zorder=3)
    for value, share, y_position in zip(values, shares, y_positions):
        ax.text(share + 1.35, y_position, f"{value}  ({share:.1f}%)", ha="left", va="center", color=INK, fontproperties=FONT_EN_SMALL_BOLD)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 57)
    ax.set_xlabel("Share of unique configurations (%)")
    ax.set_title("Normalized brand-category concentration", loc="left", pad=10)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    set_axis_fonts(ax)
    named_total = int(top.sum())
    ax.text(0.995, 0.93, f"Top five named categories: {named_total:,} ({named_total / stats['unique_configurations']:.1%})", transform=ax.transAxes, ha="right", va="top", color=TEAL_DARK, fontproperties=FONT_EN_SMALL_BOLD)
    fig.text(0.24, 0.075, "“Other categories” pools the remaining normalized labels; not a market-share estimate.", ha="left", va="center", color=MUTED, fontproperties=FONT_EN_SMALL)
    return save_figure(fig, "figS3_baidu_mtc_normalized_brand_categories")


def main() -> None:
    setup_style()
    data, stats, excluded = load_analysis_data()
    outputs = []
    outputs.extend(figure_catalog_scope_and_composition(data, stats))
    outputs.extend(figure_brand_android_coverage(data, stats))
    outputs.extend(figure_display_geometry(data, stats))
    outputs.extend(figure_counting_unit_audit(stats))
    outputs.extend(figure_android_major_profile(data, stats))
    outputs.extend(figure_normalized_brand_profile(data, stats))

    print("Excluded Android 4.4.x entries:")
    for row in excluded.itertuples(index=False):
        print(f"  - {row.device_name} | {row.android_version} | {row.resolution}")
    print("\nGenerated files:")
    for path in outputs:
        print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
