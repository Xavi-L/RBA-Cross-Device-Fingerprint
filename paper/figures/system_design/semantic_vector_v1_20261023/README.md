# HybridGuard Figure 2 — semantic SVG revision

This directory contains an editable SVG reconstruction of the user-selected visual design dated **2026-10-23**. It replaces repeated decorative checklist rows with meaningful rule, value, and decision illustrations. The figure is archived as an independent revision; adding it here does not replace the existing frozen figure or update manuscript references.

### Icon and connector refinements - 2026-10-24

The In-app web/Device info link is now vertical between the two cards. The optional Browser-input link is centered on the vertical middle section of its dashed arrow, with a small background clearance so dashes do not cross the icon. The Saved checks arrow shaft ends at the triangular arrowhead base, removing the rounded-cap protrusion at its tip. In the Browser check, the Chrome badge moves 10 SVG units left and 7 units up to separate it from the clock.

All six displayed App logos use a rounded clip of the complete source canvas, with radius equal to 20% of its side, matching Figure 1 v5. Their original source assets and brand colors are retained. The 64 text objects and their attributes, outer dimensions, panel geometry, and scientific relations remain unchanged. The builder, SVG, PNG, PDF, and source package are synchronized; this revision is also used by the current manuscript figure inputs.

### Shared frame radii — 2026-10-23

Figures 1–3 now share physical corner radii of **1.2 mm for enclosing containers, 0.8 mm for content cards and page frames, and 0.5 mm for labels/highlights**. At this figure's 180 mm width, these correspond to 12, 8, and 5 SVG units. Front and rear page outlines use the same card radius; header fills use that radius minus their existing inset.

The revision changes only rectangle radii in the SVG. Frame positions and sizes, all 64 text objects and their attributes, arrows, colors, scientific data bars, and original logo/pictogram artwork retain their prior values. The build script, SVG, PNG, PDF, checks, and source package are synchronized. `FRAME_RADIUS_MM` in the portable builder records the shared style.

### Color refinement - 2026-10-23

Semantic icons now use saturated red (`#E53935`), green (`#16A34A`), and blue (`#1976D2`). This strengthens the Filter rejection cross and acceptance check, timezone decisions, memory warning, clock and viewport pictograms, and data-inspection icons. Memory illustrations share blue/red fills, and the filter funnel uses gold. The Results alert and check instances use the same status palette, with a white check on green.

The refinement is based on commit `98380b2e67ea7e4470ac97357dbae13abda0ff29`. An element comparison confirms that only SVG `fill` and `stroke` values changed: all geometry, 64 text elements, and layout are identical. Structural frames, large background areas, flow connectors, and brand colors retain their prior treatment. The SVG, PNG, PDF, build script, and source ZIP are synchronized.

## Files

| File | Purpose |
| --- | --- |
| [HybridGuard_Fig2_semantic_v1.svg](HybridGuard_Fig2_semantic_v1.svg) | Main editable vector figure, with named groups and Inkscape layers. Text remains SVG `text`; source brand SVGs are inlined. |
| [HybridGuard_Fig2_semantic_v1.png](HybridGuard_Fig2_semantic_v1.png) | 3,500-pixel-wide review preview exported from the SVG. |
| [HybridGuard_Fig2_semantic_v1.pdf](HybridGuard_Fig2_semantic_v1.pdf) | Vector export for document placement, approximately 180 × 90 mm. |
| [build_figure.py](build_figure.py) | Reproducible figure and export build script. |
| [assets/](assets/) | Original SVG assets used by the figure, with source and license documentation. |
| [reference/approved_raster_concept.png](reference/approved_raster_concept.png) | User-selected image-generation composition reference; this is not an SVG export. |
| [CAPTIONS.md](CAPTIONS.md) | English and Chinese captions and concise alternative text. |
| [SOURCE_MAP.json](SOURCE_MAP.json) | Machine-readable source and component mapping. |
| [QUALITY_CHECK.json](QUALITY_CHECK.json) | Recorded structural validation and export metadata. |
| [VISUAL_REVIEW.md](VISUAL_REVIEW.md) | Visual review, PDF inspection, and font information for the delivered export. |
| [source_materials.zip](source_materials.zip) | Source package containing the build script, assets, documentation, and main SVG; large rendered files are excluded. |

The main SVG is self-contained: artwork uses vector geometry and inline SVG assets, without bitmap images or external image links. The delivered export uses **Nimbus Sans**, with Arial and Liberation Sans as fallbacks. The PDF embeds its font subsets. Keep Nimbus Sans installed when rebuilding for the same text metrics; other editors may use one of the fallback fonts.

## Use and reproduce

Use the SVG for editing in Inkscape, the PNG for quick visual review, and the PDF for vector placement in the manuscript. Named groups separate the upper rule-construction flow, current records, example checks, and results.

The build requires **Python 3** and **Inkscape** on `PATH`. The Python script uses only the standard library. From the repository root:

```bash
cd paper/figures/system_design/semantic_vector_v1_20261023
python3 build_figure.py
```

The source ZIP contains everything needed to rebuild the figure. The large PNG/PDF exports and raster composition reference remain available separately in this repository directory.

For changes that need to survive regeneration, edit `build_figure.py` or the documented source assets, then rebuild. Direct SVG edits remain possible, but rebuilding replaces the generated SVG. Consult `QUALITY_CHECK.json` for the validation recorded for a particular build.

## Visual decisions

- App logos share one container. App Web uses unbranded stacked pages; external Browser Web uses stacked pages with browser logo badges.
- The upper flow uses distinct visual operations: admit usable candidates, reduce the set, add coverage, and save the checks. Ticks and crosses indicate actual acceptance or rejection relationships.
- The memory panel shows a derived upper bound; the timezone panel compares concrete values. These replace repeated tick-and-text decorations.
- Arrow weight, shape, and muted color distinguish the main flow, supporting comparisons, and optional Browser inputs. Brand colors remain in their original SVG assets.
- Saturated red, green, and blue emphasize meaningful states and technical pictograms. Red/green result-icon color overrides are applied only to displayed instances; the original asset SVG files are retained.
- The layout keeps the selection flow above current-record evaluation, with results alongside the examples.

## Method boundaries

The figure's method relationships were checked against [the method source](../../../../output/pdf/hybridguard_www_draft_20261017/sections/03_method.tex), with the [earlier visual archive](../visual_explorations_20261022/README.md) as design context.

The upper band uses normal and controlled-modification **development records** for candidate admission, sparse selection, and retention under normal-alarm and definite-output coverage constraints. “Page size” denotes a relation within the same Web observation, not Host–Web geometry. “More coverage” illustrates feasible retention additions; it does not depict online retraining.

The lower band evaluates **selected checks only** on bound current App records. The optional C1 configuration adds a comparison between validly linked App Web and external Browser timezone offsets. It is an optional configuration, not a fallback after another check fails. An absent Browser input does not create a synthetic Browser observation.

The memory example is schematic: Native memory of 3 GiB yields an upper bound of 4 GiB, while a Web report of 8 GiB exceeds it. The rule uses `m_web > 2^ceil(log2(m_native))`, subject to its applicability conditions; it does not require equality with Native memory. `UTC+8` and `UTC+9` are normalized effective-offset labels for readers, not raw JavaScript `getTimezoneOffset()` values.

### Result meanings and precedence

Evaluate the following rows in order. Required failures for selected checks take precedence over trigger decisions.

| Figure label | Method meaning |
| --- | --- |
| **No checks** | `EMPTY_MODEL`: the selected set is empty. |
| **Check failed** | `FAILED`: a required execution or association failure prevents evaluation of selected checks. |
| **Alert** | No required failure, and at least one selected check returns `T`. |
| **No alert** | The selected set is nonempty, and all selected checks return `F`. |
| **Cannot tell** | Remaining unresolved cases (`U`). |

Ordinary missing or inapplicable operands yield `U`, not `F`. A trigger may coexist with an unresolved check and still produce **Alert**, provided no required failure has occurred. Problems confined to unselected fields do not independently cause **Check failed**.

Logos, rule-family combinations, and example values are illustrations. They do not identify a tested-brand list, an exact selected set for every configuration, or experimental outcomes. **No alert does not establish device authenticity or safety.**
