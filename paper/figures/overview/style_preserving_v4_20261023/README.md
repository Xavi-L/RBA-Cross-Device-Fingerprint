# HybridGuard Figure 1 — preserve-layout style revision v4

This revision applies Figure 2's colored pictograms, original app-logo assets, pale panels, and overlapping page outlines to the **current Figure 1 v3**. It is a visual revision for review, dated 2026-10-23.

## View and edit

- [Editable SVG](HybridGuard_Fig1_surfaces_v4.svg)
- [3200 px PNG preview](HybridGuard_Fig1_surfaces_v4.png)
- [1500 px review preview](Fig1_review_1500px.png)
- [Source package](source_materials.zip)
- [Preservation checks](QUALITY_CHECK.json)
- [Visual review](VISUAL_REVIEW.md)

The SVG contains editable text and vector geometry. It has **65 original text objects**, **zero embedded bitmap images**, and **zero external artwork dependencies**. Nimbus Sans and Nimbus Roman preserve v3's existing type metrics. Inkscape layers separate the App, external Browser, and C1 comparison; the original named component groups remain available for editing.

## Fixed baseline

The source is `../revision_v3_20261022/HybridGuard_Fig1_source_v3.zip`, read at repository commit `9ac8037a953280689062f906f5762536c40e1851`. Its editable SVG is preserved in `reference/HybridGuard_Fig1_surfaces_v3.svg`. The style reference is `../../system_design/semantic_vector_v1_20261023/HybridGuard_Fig2_semantic_v1.svg` at the same commit.

This is the **nested observation-surface v3 layout**: Native APIs and WebView Host / App Web on the left, separate external Browser above the C1 comparison on the right. It is not a reconstruction from the older triangle overview or the reverted icon-vector redraw.

The builder verifies that all original visible text strings and their complete SVG attributes are unchanged, including positions, size, font selections, color, and anchors. The original page dimensions, all nine main foreground rectangles, and every comparison / record-excerpt relation retain their geometry. The original line widths, dashed/dotted patterns, and arrow endpoints are preserved.

## Visual changes

1. A compact tray in existing space above the Native card uses the same six app marks as Figure 2: WeChat, WhatsApp, Instagram, TikTok, YouTube, and Alipay. Their source vector colors and shapes are retained.
2. Native, App Web, external Browser, and the two C1 record cards receive shallow offset page outlines. These are visual depth cues; the foreground card bounds are unchanged.
3. Memory, time, dimensions, document, and association symbols use saturated blue, green, and amber. The original `JS` badge becomes yellow. The Native collection interval receives a small interval symbol in the existing icon gutter.
4. A new vector WebView pictogram replaces the old embedded PNG at the same position and size. It is an original technical pictogram, not an official replacement product logo.
5. The two illustrative C1 offsets have blue clock symbols with different hands, and the existing offset-mismatch outcome has a red cross. The applicability row receives a small chain-link symbol. No new visible text is added.

The clocks schematically identify the two different offsets; they are not collection timestamps. The red cross belongs to the illustrated **C1 condition outcome**, not a whole-detector alert. App marks illustrate app identity and are not a new evaluated-brand list. The external Browser retains the original Chrome 133 / 134 implementation statement; no additional browser implementation is implied.

## Rebuild

Python 3 and Inkscape are required. From this directory:

```bash
python3 build_figure.py
```

This regenerates the main SVG, both previews, and `QUALITY_CHECK.json`. To regenerate only the SVG and structural checks, use `python3 build_figure.py --svg-only`. Source files, exact baseline, and notices are included in the source ZIP. The build uses Python's standard library.

This directory keeps the revision separate from the v3 archive and the existing manuscript asset. It does not alter the manuscript, captions, Figure 2, or any research results.

## Sources

See [asset provenance and attribution](assets/ATTRIBUTION.md) and the preserved source manifests. New technical icons are vector geometry authored for this revision. Existing Android and Chrome artwork is carried through from v3, while the six app assets come from Figure 2's existing asset directory.
