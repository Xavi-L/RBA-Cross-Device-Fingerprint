# WWW draft compiled from current LaTeX — 2026-10-25 Table 1 redesign

- Baseline: latest local reviewed prose/layout, preserved separately as commit `1eda74bf` on top of remote main `1fdf0d71`.
- Manuscript change: `tables/table_01.tex` only. Other prose, tables, figures, bibliography, abstract, main.tex, template, and data match the local baseline exactly.
- Table 1 now separates Method, Evidence, and Evaluation; eight Study/Research focus cells, citation keys, surface marks, and Host/Browser footnotes are preserved.
- Seven cited studies checked against primary papers; exact sources and the FP-Inconsistent author-manuscript version caveat are in `table1_method_evidence_evaluation_20261025.md`.
- Table retains `table*`, `small`, 3 pt column padding, and 1.12 row stretch; only its column widths change. New three-column cells all occupy at most two lines.
- Entry: current `main.tex`; compiler: pdfLaTeX via latexmk. Historical migration was not run.
- Command: `latexmk -g -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build main.tex`.
- Main text ends on p.8; references begin on p.9; entire PDF has 11 pages.
- Main text <= 8 pages: PASS. Total <= 12 pages: PASS.
- Table 1 remains on p.2, immediately above Section 2. All other main-paper float pages match the local baseline.
- Overfull boxes: 0. Undefined citations/references: 0. Existing ACM `printacmref=false` warning and 13 ordinary Underfull messages remain.
- All 11 PDF pages rendered and inspected, including a separate full-page Table 1 preview: no clipping or overlapping text observed.
- Independent read-only review: PASS for scope preservation, first-six-column preservation, footnotes, semantics, pagination, and layout.
- `HybridGuard_WWW_Draft.pdf` copied from fresh `build/main.pdf`.
- Independent archive extraction and compilation: PASS (11 pages). All page text, labels, and rendered pixels match the workspace PDF.
- Archive contains 151 members (150 existing paths plus the new Table 1 evidence report); final member consistency: PASS. Only documentation/manifest updates follow the clean package build; all compiled inputs remain byte-identical.
- Existing automatic compilation workflow reviewed. It compiles main.tex, checks float placement, and refreshes PDF/ZIP; its eight-page test only warns. This delivery locally enforces the limit and includes precompiled artifacts with `[skip ci]`. Workflow unchanged.
