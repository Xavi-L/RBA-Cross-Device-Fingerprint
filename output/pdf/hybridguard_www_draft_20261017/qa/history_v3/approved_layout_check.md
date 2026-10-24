# Approved-edits layout check

**PASS — 8 main-text pages / 10 total pages.** The approved A1/A2/A3/B1 words are retained, and the conclusion now fits completely on page 8. References and Appendix A start on page 9. The first v3 build had 9 main-text pages / 11 total pages, with three conclusion lines on the extra page.

## Final artifact

- PDF: `build/matrix/HybridGuard_layout_v1_matrix.pdf`
- SHA-256: `bd00d76b84fb1da0a9c04c88a82a9113fc74377cf0e83e4380480e6f588f99dc`
- Size: 563,746 bytes
- Auxiliary file: `build/matrix/HybridGuard_layout_v1_matrix.aux`
- Rendered pages: `qa/render_approved/matrix/page-01.png` through `page-10.png`, Poppler at 120 dpi

## Retained layout changes

| Table | Before | After | Natural height recovered |
|---|---|---|---:|
| 1 | `0.145 / X / X / X` | `0.172 / 0.272 / 0.252 / X` of `textwidth` | 9.962 PDF pt |
| 2 | `0.205 / 0.135 / 0.10 / X` | `0.19 / 0.09 / 0.06 / X` of `textwidth` | 9.963 PDF pt |
| 3 matrix | `l / c / 6 X`; manually wrapped headers | Same column structure; forced header breaks replaced by spaces | 8.767 PDF pt |
| 6 | `0.34 columnwidth / c / X / X`; wrapped result headers | `0.26 columnwidth / c / 0.25 columnwidth / X`; single-line headers | 8.767 PDF pt |

Table 1’s WebView row and Table 2’s Controlled App role now avoid an extra natural line. Table 3’s existing full-width column system has sufficient room for all single-line headers: the measured maximum header width is about 49.36 PDF pt, below its resulting X-column width. Table 6’s longest record-family label measures about 59.15 pt; its result headers measure 58.07 and 75.45 pt, within the reassigned columns. All data rows remain legible without extra wrapping.

The table totals, `small` font selection, `tabcolsep`, `arraystretch=1.12`, caption text, and all cell words/numbers are preserved. Table 1/2/6 adjustments are conditional on `ifHGMatrix`; their baseline branch preserves its original column and header settings. Table 3’s change is confined to its existing matrix-only file.

`source/migrate_manuscript.py` now applies these transformations idempotently in `polish_matrix_layout`. The normal command `python3 source/build_pdf.py --variant matrix` generates the selected layout without a manual post-build patch.

## Float placement and page map

The final float registration is the retained v2 strategy: Table 2 is queued before §3.5, matrix Table 3 before §4.2, and Figure 3 before §4.3. Table 4/5/6 keep their original Results-section registration points. No additional float move, float option, or float-spacing adjustment remains.

| Item | First v3 build | Final |
|---|---:|---:|
| Table 1 / Figure 1 | 3 | 3 |
| Figure 2 | 4 | 4 |
| Table 2 | 5 | 5 |
| Table 3 / Figure 3 | 6 | 6 |
| Table 4 | 7 | 7 |
| Tables 5–6 | 8 | 8 |
| §6 / §6.1 starts | 8 | 7 |
| Conclusion ends | 9 | 8 |
| References / Appendix A starts | 10 | 9 |
| Final appendix page | 11 | 10 |

Table numbers 1–6 and figure numbers 1–3 match their labels and original subjects. Tables 5–6 remain on page 8; this preserves normal float order while keeping the approved text within the page budget.

## Content and template preservation

All eight generated section texts match the approved pre-layout content after whitespace normalization. The only paragraph-boundary change is the parent-authorized merge of B1 with the immediately following Device Memory explanation; no words changed. This child agent did not edit `input_markdown`.

All seven table-file captions are exact matches. All data bodies after the first midrule are exact matches. Table 3/6 headers match after replacing their old forced line breaks with ordinary spaces; Table 1/2 headers and bodies are exact. All nine frozen figure hashes match. The submitted abstract, main templates, class, bibliography, data files, and figure inclusion files remain unchanged. Body font sizes, margins, line spacing, row spacing, float spacing, and image dimensions were not reduced.

The final PDF matches the selected temporary candidate on all 10 pages by exact extracted text and 72-dpi raster pixels. A separate ZIP rebuild check verifies independent reproducibility at 120 dpi.

## Compilation and visual review

The final log has zero compile errors, unresolved references/citations, overfull boxes, or rerun warnings. Fifteen bibliography entries resolve. It retains the existing acmart warning caused by `printacmref=false`, plus 9 underfull hbox and 9 underfull vbox diagnostics. All 28 listed PDF font entries are embedded.

All 10 pages were rendered with Poppler. The child reviewed the complete contact sheet and affected page layouts, including the table headers, the p7–p8 continuation, and the complete conclusion. The root independently inspected every final page 1–10 and confirmed readability of Tables 1/2/3/6, the approved method additions, Appendix A additions, and the conclusion. No clipping, overlap, crowded header, or lost text was observed.

Earlier float-registration and local paragraph-breaking trials did not meet the 8-page target and were discarded. No temporary `looseness`, `tolerance`, API `allowbreak`, negative vertical space, page enlargement, font reduction, or global float-spacing override remains in the selected layout.
