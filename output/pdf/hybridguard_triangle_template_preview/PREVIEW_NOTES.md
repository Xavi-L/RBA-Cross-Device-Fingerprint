# HybridGuard overview in the supplied ACM template

Preview date: 2026-10-10

This is a figure-placement preview made from the supplied LaTeX ZIP. The original archive and the repository's overview source were left unchanged.

## What to open

- `hybridguard_draft.pdf`: the compiled 17-page review copy; Figure 1 is at the top of page 7.
- `previews/figure_page_07.png`: a rendered view of that complete page.
- `hybridguard_draft.tex`: main document for pdfLaTeX/BibTeX or Overleaf.
- `figures/overview_figure.tex`: the cross-column `figure*` block and caption.

## Placement and source

The current `paper/figures/overview_triangle/HybridGuard_overview_triangle.svg`, including the two thin label borders, was copied into `figures/`. The SVG was exported to a vector PDF using Chrome and embedded with `\includegraphics[width=\textwidth]` in a `figure*` environment. The image occupies approximately 177.94 mm of text width. Times New Roman fonts are embedded, all figure text remains extractable, and the figure PDF contains zero raster image objects.

Only `sections/04_system_design.tex` was changed among the supplied manuscript source files: it inputs the figure block and adds one neutral cross-reference sentence. The original English caption from the overview README was reused. The original ACM class options `sigconf,anonymous,review`, review line numbers, tables, bibliography, and manuscript prose were retained.

## Compile

The vector figure PDF is included, so ordinary LaTeX compilation does not need Chrome, SVG support, or shell escape.

```sh
latexmk -pdf -bibtex -interaction=nonstopmode -halt-on-error hybridguard_draft.tex
```

On Overleaf, select `hybridguard_draft.tex` as the main document and pdfLaTeX as the compiler. The included `figures/export_svg.cjs` is only for regenerating the figure PDF after a future SVG edit; it uses locally available Playwright/Chrome.

## Actual validation

- Compiled successfully with pdfLaTeX (TeX Live 2025), BibTeX, and latexmk; 17 pages, compared with 16 pages in the uploaded PDF.
- Zero unresolved citations/cross-references and zero overfull horizontal boxes in the final log.
- Rendered all 17 pages. Inspected the complete contact sheets, the figure page, and the bibliography/appendix transition. The figure, caption, margins, and body text show no visible clipping or overlap.
- One 1.47 pt overfull vertical-box warning remains near the bibliography/appendix transition on page 16; visual inspection showed no clipped or overlapping content there. The template's ACM reference-format setting and some underfull-box/float-placement warnings also remain.
- The supplied `compile_validation.md` describes the older original draft; this file records the new figure-insertion build.

## Content boundary

This preview changes placement, not the manuscript's research claims. The older manuscript still describes Browser detection evaluation as future work, while the current overview shows the selected fixed-model C1 condition. That textual alignment should be handled in a separate manuscript revision; the preview is not a fact-audited submission draft.
