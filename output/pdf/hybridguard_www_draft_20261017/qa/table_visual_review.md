# Final PDF visual review: Tables 4/6 and assigned pages

## Candidate binding

- PDF: `build/matrix/HybridGuard_layout_v1_matrix.pdf`
- SHA-256: `82fb37b0970666015928762e7c6913621474f28b80dab32ce014eb74274cd72e`
- Total PDF pages: 10; the conclusion is on page 8 and references begin on page 9.
- Reviewed render set: `qa/render_final/page_01.png` through `page_10.png`.
- Reviewer: `tables36_visual`, independently inspecting the final rendered PDF after source work.
- Scope: full-page inspection of pages 1, 2, 4, 9, and 10; focused supplementary inspection of page 6 (Table 4), page 8 (Table 6), and page 7 (single-column Table 5 and its surrounding flow). Pages 3 and 5 are assigned to the parent reviewer and are not claimed as visually reviewed here.

**Result: PASS for the inspected scope. No required source or layout change was identified.**

## Method

The existing final page images were inspected at their original 980 × 1268 pixel resolution. Each of the eight inspected PNGs was also compared, pixel for pixel, against an in-memory PyMuPDF render of the bound PDF at scale 1.6; all comparisons matched. This verifies that the reviewed images correspond to the stated PDF, rather than an earlier candidate. The PDF hash was rechecked after inspection and remained unchanged.

Visual inspection was supplemented by a text-block bounds check: no text block on the eight inspected pages extends beyond its page rectangle. This bounds check is supporting evidence; conclusions about overlap, alignment, and legibility come from the rendered-page inspection.

## Page-by-page findings

| PDF page | Scope | Finding | Required action |
|---|---|---|---|
| 1 | Full page | Title and anonymous-author line are centered and complete. The abstract, CCS block, keywords, and introduction fit their columns. The conference footer and page number remain separate from body text. No clipping or overlap observed. | None |
| 2 | Full page | Heading hierarchy, two-column flow, and the bottom-right displayed equation are legible. The equation remains inside the text area and above the page number. No clipping, column collision, or footer collision observed. | None |
| 4 | Full page | Figure 2, its labels, and its caption are complete and remain clear of following text. The equation and the two lower text columns fit. No overlapping rules, labels, or text observed. | None |
| 6 | Table 4 and surrounding layout | Table 4 is a single-column grouped comparison. Memory / Timezone / Geometry headings, the partial/full/zero detection symbols, warning triangles, and count fractions are distinguishable. The standalone qualifier remains fully visible. Its compact legend is readable and lies within the column. Table 3 above is also visibly separated from the following body. | None |
| 7 | Supplementary Table 5 / flow check | Table 5 occupies one column. Both cohort titles and N values, all four configuration rows, all T/F/U triples, and the grayscale bars are visible. The bar legend remains readable. Figure 3 is on this page, separate from Table 3 on page 6. | None |
| 8 | Table 6 and end-of-main-text check | Table 6 has a single-line header; the caption defines App as Integrated App. Check/cross symbols and values are distinguishable. The Normal alarms row is separated by a rule and contains plain numeric counts. The legend is complete and readable. The conclusion finishes on this page without overflow. | None |
| 9 | Full page | References [1]–[15] fit the left column with readable labels and wrapped URLs. Appendix A begins below the references and continues into the right column. Headings and text do not overlap. No clipped citation text or column spill observed. | None |
| 10 | Full page | Appendix A.4/A.5, equations/numbers in prose, and long monospace implementation paths wrap within their columns. Both columns end cleanly. The remaining lower-page whitespace is the natural end of the appendix, not missing or clipped content. | None |

## Table 4 and Table 6 small-legend assessment

Both legends use approximately 6.974 pt text, with the check-symbol font approximately 7.273 pt. At the reviewed render scale, the complete legends are readable and neither crosses the table or column boundary. Their interpretation remains explicit:

- Table 4: full / partial / none describes detection on tested modifications; the triangle denotes nonzero normal alarms.
- Table 6: the legend applies to modification rows only. The separately ruled normal row has no detection symbol.

No cropped glyph, missing-symbol box, accidental symbol substitution, or collision with a rule was observed. The numerical values remain the precise record of results; the symbols supplement them.

## Issues and handoff

- Blocking issues: none.
- Required visual fixes: none.
- Source changes performed during this review: none.
- Files written during this review: this Markdown record and `qa/table_visual_review.json` only.
- The parent reviewer covers pages 3 and 5 and the broader manuscript-wide approval. This record is bound only to the PDF hash stated above.
