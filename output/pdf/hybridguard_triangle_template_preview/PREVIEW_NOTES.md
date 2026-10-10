# HybridGuard research/method overview in the supplied ACM template

Preview date: 2026-10-10. This build synchronizes the research-narrative revision of `paper/figures/overview_triangle/`, based on the approved icon/color baseline `3443c16`. The original uploaded archive remains unchanged.

## What to open

- `hybridguard_draft.pdf`: newly compiled 17-page review copy; Figure 1 is on page 7.
- `previews/figure_page_07.png`: the newly rendered complete figure page.
- `hybridguard_draft.tex`: main document for pdfLaTeX/BibTeX or Overleaf.
- `figures/overview_figure.tex`: cross-column figure block, new formal English caption and accessibility description.

## This revision

The figure now introduces device-fingerprint manipulation, same-device observation roles, cross-checking, a timezone illustration, offline selection using controlled modifications and normal development data, two current-input modes and research evaluation. It retains the approved icons, pale palette, triangle and relation-status distinctions. The two thin white-label borders remain.

The current editable SVG was copied to `figures/`, exported to vector PDF with Chrome, and embedded with `\includegraphics[width=\textwidth]`. The native figure is 180 × 106 mm and occupies approximately 177.94 mm of manuscript text width. Times New Roman fonts are embedded and figure text remains extractable; the figure PDF has zero raster image objects. The English caption exactly follows the overview README apart from LaTeX punctuation encoding; the faithful Chinese caption is in that README.

## Compile

The vector figure PDF is included, so ordinary compilation needs neither Chrome nor SVG support nor shell escape.

```sh
latexmk -pdf -bibtex -interaction=nonstopmode -halt-on-error hybridguard_draft.tex
```

For Overleaf, select `hybridguard_draft.tex` and pdfLaTeX. `figures/export_svg.cjs` only regenerates the figure PDF after an SVG edit, using existing local Playwright/Chrome. The sibling ZIP is synchronized and includes the figure dependencies and editable source, excluding the compiled manuscript PDF and preview images.

## Validation for this generated build

- Successfully compiled with pdfLaTeX (TeX Live 2025), BibTeX and latexmk: 17 pages, Figure 1 on page 7.
- Final pass: zero unresolved citations/cross-references, zero overfull horizontal boxes, zero LaTeX errors.
- Rendered all 17 pages anew. Inspected the complete contact sheets, the figure page at 160 dpi and the bibliography/appendix transition. The updated figure and caption show no visible clipping or overlap.
- One original 1.47 pt overfull vertical-box warning remains near the bibliography/appendix transition on page 16, without visible clipping in the new render. Existing underfull-box and ACM reference-format warnings remain.
- These checks refer to this newly generated PDF, not the earlier figure-insertion preview. The supplied `compile_validation.md` remains the older original draft's record.

## Scope

This operation updates the overview SVG/PDF, caption/accessibility description, compiled manuscript preview, figure-page PNG and these notes. The original insertion reference in `sections/04_system_design.tex` still points to the same figure block and label; it requires no change. Other manuscript prose, tables, bibliography and ACM class options remain as supplied.

This is a layout preview, not a fully synchronized manuscript revision. The older body includes historical knowledge/LLM branches and describes Browser evaluation as future work; those claims were not imported into the overview. Aligning the manuscript text with the current fixed detectors is outside this figure-only task. No research code, data, labels, models or experimental statistics were changed, and no training, rule selection or evaluation experiment was run.
