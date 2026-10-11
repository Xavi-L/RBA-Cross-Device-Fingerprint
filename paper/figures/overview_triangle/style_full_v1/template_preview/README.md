# Isolated preview in the project's existing ACM template

Open `hybridguard_draft.pdf`, page **7**, or `figure_page_07.png` to inspect the complete page, full caption, margins, header and adjacent prose. The current figure plus full caption and internal spacing occupies **48.7823%** of `textheight`, passing the strict `< 50%` requirement. The ideal `<= 48%` target is not met.

Sources are copied from `output/pdf/hybridguard_triangle_template_preview/`. The main entry, `acmart.cls` (`sigconf,anonymous,review`), sections, bibliography and class macros are byte-identical to those source files. `SOURCE_MANIFEST.json` lists the copied files. Only the copied `figures/overview_figure.tex` changes the included figure and adds layout measurement logging. The original project is not written.

The full caption is unchanged. The PDF is included with `width=\textwidth`, with no height cap, negative spacing, page-geometry changes or nonuniform scaling. Internal figure body fonts remain 7.84795 / 8.12983 PDF pt, matching 393f0faa.

From this directory:

```sh
latexmk -pdf -bibtex -interaction=nonstopmode -halt-on-error hybridguard_draft.tex
```

For the complete figure rebuild and measured checks, see [review notes](../REVIEW_NOTES.md). See [two-change notes](../DIRECTION_FIX_NOTES.md) and [template measurements](../TEMPLATE_CHECK.json) for results. The historical manuscript prose is preserved for layout context; this is not a research-content update or publication-readiness claim.
