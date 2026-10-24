# Approved deduplication and eight-page layout (2026-10-24)

Base commit: `8da8fa90675e454695593e7dd3f5240d62d89a1e`.

## Applied edits

1. Remove Section 5.5 Synthesis, which repeats the results and conclusion.
2. Remove the Section 5.1 enumeration already present in Table 3 and its note.
3. Remove the repeated Section 5.1 refitting explanation; Section 4.2 and Table 3 retain it.
4. Condense Section 4.3 reconciliation while preserving the lack of independent label/binding validation.
5. Condense Figure 2's caption; keep the first-matching-case reference to Section 3.2, both configurations, and standalone Host geometry.

The matching Markdown inputs are synchronized. Approximate source-word reduction is 187, including the removed heading and condensed caption.

## Verified output

- Main text ends on page 8; references start on page 9; total PDF length is 10 pages.
- Figure 1/2/3 pages: 3/4/7.
- Table 1/2/3/4/5/6 pages: 2/5/6/6/7/8.
- All figure and table labels resolve; no overfull-box or undefined-reference warnings.
- The complete conclusion fits on page 8 with remaining space in its right column.
- Results flow directly into Discussion and Limitations; no unique result or boundary statement was removed.
- Abstract, method prose, discussion, conclusion, references, figure assets, and authored tables match the base commit byte for byte.
- The original Overleaf archive still had the superseded Table 1. It is now synchronized to the current three-column table without modifying the repository's already-correct table.
- Current LaTeX sources and the Overleaf package contain the same five edits. Historical notes and suggested extended captions are preserved as historical material.

Compile the current source directly with `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`, or use the documented `--no-migrate` route. Do not regenerate from the legacy figure migration defaults.
