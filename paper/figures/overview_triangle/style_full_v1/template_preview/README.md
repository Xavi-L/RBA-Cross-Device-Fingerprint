# Isolated preview in the project's existing ACM template

Open `hybridguard_draft.pdf`, page **7**, or `figure_page_07.png` for the complete page with the candidate overview, formal English caption, margins and adjacent prose.

Sources were copied from `output/pdf/hybridguard_triangle_template_preview/`. The main entry, `acmart.cls` (`sigconf,anonymous,review`), sections, bibliography and class macros are unchanged. `SOURCE_MANIFEST.json` records their source hashes. Only the copied `figures/overview_figure.tex` changes the included figure and adds layout measurement logging. The original project is not written.

From this directory, compile with the original command:

```sh
latexmk -pdf -bibtex -interaction=nonstopmode -halt-on-error hybridguard_draft.tex
```

The figure PDF is already present in `figures/`; no shell escape, browser or font installation is needed for ordinary manuscript compilation in the existing TeX environment. No system font files were copied.

See [finishing notes](../FINISHING_NOTES.md) and [template measurements](../TEMPLATE_CHECK.json) for actual width, scale, fonts, occupied height and retained warnings. The supplied historical prose was preserved for layout context; this is not a research-content update or publication-readiness claim.
