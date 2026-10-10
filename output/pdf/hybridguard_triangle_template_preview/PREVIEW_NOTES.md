# HybridGuard research/method overview in the supplied ACM template

Preview date: 2026-10-10. This build synchronizes the local layout revision of `paper/figures/overview_triangle/`, based on the research-narrative baseline `f80ec0a`. The original uploaded archive remains unchanged.

## What to open

- `hybridguard_draft.pdf`: newly compiled 17-page review copy; Figure 1 is on page 7.
- `previews/figure_page_07.png`: the newly rendered complete figure page.
- `hybridguard_draft.tex`: main document for pdfLaTeX/BibTeX or Overleaf.
- `figures/overview_figure.tex`: cross-column figure block, new formal English caption and accessibility description.

## This revision

The observation triangle, Browser position, icons, pale palette, core wording and relation semantics retain the f80ec0a baseline. The offline inputs are now full-width stacked entries, with independent paths into an aligned two-column goal area. A 50-unit channel separates the upper panels from a 270-unit rule-application frame. Two equal mode cards are stacked with “or”; their own rule descriptions remain. Black current-data arrows enter the corresponding cards, a separate purple port loads rules at the application header, and a single output arrow denotes the selected mode's result. The result list and research-evaluation strip have clear bottom spacing.

The editable SVG is now **180 × 125 mm**, with a matching 1800 × 1250 viewBox. `figures/export_svg.cjs` reads both physical dimensions from the SVG instead of hardcoding 106 mm. Chrome's PDF page rounding produces approximately 179.92 × 124.88 mm. The figure contains zero raster image objects.

A subsequent local correction aligns the pale triangle fill with the intersections of the three extended relation lines. Only that fill path changes; the relation paths, cards, wording and colors remain unchanged. The SVG/PNG comparisons, vector PDF and manuscript preview were regenerated after this correction.

The existing `\includegraphics[width=\textwidth]` reference is unchanged: it uses approximately 177.94 mm of ACM text width, just as in the baseline. No height constraint, vertical stretching or scaling back into the old height was introduced; text size at the same publication width remains unchanged. The formal English caption is unchanged, and the accessibility description reflects the alternative modes and single result arrow. The Chinese caption remains in the overview README.


## Compile

The vector figure PDF is included, so ordinary compilation needs neither Chrome nor SVG support nor shell escape.

```sh
latexmk -pdf -bibtex -interaction=nonstopmode -halt-on-error hybridguard_draft.tex
```

For Overleaf, select `hybridguard_draft.tex` and pdfLaTeX. `figures/export_svg.cjs` only regenerates the figure PDF after an SVG edit, using existing local Playwright/Chrome. The sibling ZIP is synchronized and includes the figure dependencies and editable source, excluding the compiled manuscript PDF and preview images.

## Validation for this generated build

- Successfully compiled with pdfLaTeX (TeX Live 2025), BibTeX and latexmk: 17 pages, Figure 1 on page 7.
- Final pass: zero unresolved citations/cross-references, zero overfull horizontal boxes, zero LaTeX errors.
- For the layout revision, rendered all 17 pages and inspected the contact sheets, figure page and bibliography/appendix transition. After the fill-only correction, recompiled the manuscript and rerendered page 7 at 160 dpi; inspected that new page, the triangle detail and the 180 mm preview. The fill now meets all three relation edges, with no new visible clipping or overlap in the figure or caption.
- The existing overfull vertical-box warning near the bibliography/appendix transition remains (about 1.45 pt in the latest build). That area showed no visible clipping during the preceding layout inspection. Existing underfull-box and ACM reference-format warnings remain.
- These checks refer to this newly generated layout PDF, not the f80ec0a preview. The supplied `compile_validation.md` remains the older original draft's record.

## Scope

This operation updates only the overview SVG/PDF, dimension-aware export script, accessibility description, compiled manuscript preview, figure-page PNG, preview ZIP and these notes. The formal caption is retained. The original insertion reference in `sections/04_system_design.tex` still points to the same figure block and label; it requires no change. Other manuscript prose, tables, bibliography and ACM class options remain as supplied.

This is a layout preview, not a fully synchronized manuscript revision. The older body includes historical knowledge/LLM branches and describes Browser evaluation as future work; those claims were not imported into the overview. Aligning the manuscript text with the current fixed detectors is outside this figure-only task. No research code, data, labels, models or experimental statistics were changed, and no training, rule selection or evaluation experiment was run.
