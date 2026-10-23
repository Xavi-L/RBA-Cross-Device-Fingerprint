# Visual and semantic review - Figure 1 v2

Reviewed on **2026-10-23**, using the prior frozen overview for semantic scope and the current Figure 2 for style.

## User requirements addressed

| Requirement | Delivered treatment |
| --- | --- |
| Recognizable icons and logos, with adequate saturation | Blue phone/clock/memory/viewport icons, blue-red memory-limit illustration, gold OS settings, and three original-color app logos. |
| Stacked frames for emphasis and depth | Three layers on Device & OS and In-app webpage; two on App container; a nested viewport inside the container. |
| Varied arrows with clear hierarchy | Thick blue solid open comparison arrows, thinner amber dashed open comparison arrows, and a gray dotted context edge without arrowheads. |
| Compact composition | Three-view triangle with explanatory pictograms in the upper-left and interior areas; the contextual edge slopes down toward the Host. |
| Moderate wording understandable outside the specialty | Plain object names as titles, technical names as subtitles, and concise relationship-scope labels. |

## Review and adjustments

The first PDF rasterization was reviewed for density, hierarchy, wording, and semantics. Separate visual-layout and method-scope reviews agreed that the triangle preserves the three different relation scopes and covers the requested design constraints.

Two spacing issues were corrected: the Memory limit / Time zone icon-and-label groups moved upward by 8 viewBox units to separate them from the Device & OS title; the small Host viewport moved upward by 4 units and its height decreased from 36 to 30 units to give the WebView Host subtitle more room.

The final SVG PNG export and final PDF rasterization were inspected after these adjustments. Labels fit their frames; no new overlap, clipping, or mistaken connection was identified. This is a design and semantic inspection, not a measured reader-comprehension study.

## Semantic checks

- Native-Web memory and effective-timezone relations are labeled as used by the current detector.
- Host-Web geometry is labeled Separate study, without claiming it is a current detector option or future work.
- The gray contextual edge has no arrowheads and explicitly says No detection rule.
- Memory is represented by a limit, not equality of raw values. The equal clocks symbolize effective-timezone agreement.
- Logos are illustrative. No fourth Browser vertex or fixed trusted-view checkmark is introduced.
- Complete detector processing remains in Figure 2; the earlier frozen overview is preserved.

## Export properties

The editable SVG uses a 1000 x 660 viewBox, sized 86 x 56.76 mm, with 16 live text elements. It contains no raster image elements or external image references. The PNG is 3000 x 1980 pixels. PDF inspection confirms a single page, zero image objects, and embedded Nimbus Sans Regular/Bold subsets. See `QUALITY_CHECK.json` for file hashes and the inspection record tied to these exports.
