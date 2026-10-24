# Tables 3–6: visual design and semantic preservation

This edit changes the presentation of four tables only. It does not change result counts, data provenance, experimental scope, or the manuscript's body, abstract, figures, or citations. The source baseline is `hybridguard_latex_v3`.

## Shared visual semantics

- `\HGFull`: every effective modification in the displayed denominator was detected.
- `\HGPartial`: strictly some, but not all, effective modifications were detected.
- `\HGNone`: no effective modification in that denominator was detected.
- These symbols encode observed outcomes, not broad capability claims or overall method quality. A cross does not assert that an untested capability is absent.
- `\HGWarn`: a nonzero count of alarms on the tested normal records. Zero normal alarms remain numeric; they are not rendered as a detection check or a claim of universal safety.
- `\HGOutcomeBar{T}{F}{U}{width}`: exact proportions of historical-normal alarm, definite-no-alert, and unknown outcomes. T is dark gray, F light gray, and U outlined white. There are no success/failure colors and no minimum-width inflation for small categories.

All table body text remains `\small`, with the original `\arraystretch=1.12`. Main-table fonts are not scaled down. Column spacing remains 4 pt in Tables 3 and 5, and 3 pt in Tables 4 and 6. Symbols are provided by the parent-owned `table_visuals.tex`.

## Table 3: controlled benchmark outcomes

The five existing grouped rows are retained. Adjacent equal result cells are expanded so that each of the six methods has an explicit symbol and count in every group row; this keeps column correspondence clear after the comparison background colors are removed. The old comparison colors (equal/more/fewer than Integrated App) are replaced by grayscale detection symbols. Every nonzero signed difference from Integrated App is printed in its method's cell, so the comparison information is not lost. Totals are emphasized uniformly across all six methods.

| Original presentation | Revised presentation | Preserved meaning |
|---|---|---|
| Group size | Recipes | Number of original recipes represented by the row; weights remain 1, 1, 2, 8, 2. |
| `9` / `9 (all detected)` | full-detection symbol + `9` | Nine detections out of nine effective modifications **per original recipe**. |
| `6` | partial-detection symbol + `6` | Six of the nine effective modifications detected. |
| `0` / `0 (all missed)` | zero-detection symbol + `0` | None of the nine effective modifications detected. |
| `0 (-9)`, `0 (-6)`, `9 (+3)` | same numbers plus the matching outcome symbol | Original signed detection difference from Integrated App is retained. |
| Adjacent merged equal results | six explicit method cells per group | Identical outcomes are repeated under their own method headings, without pooling records or changing group weights. |
| Gray/green/red comparison legend | observed-detection symbol legend | Visual emphasis encodes tested detection completeness; numerical deltas still encode the method comparison. |

Exact per-recipe detection vectors, in original method order (Integrated App, No MTC cap, Web-only, No memory, No timezone, App tree):

| Group | Weight | Detection vector |
|---|---:|---|
| CPU + memory | 1 | 9, 9, 0, 0, 9, 0 |
| Screen metrics | 1 | 6, 9, 6, 6, 6, 0 |
| Timezone; plugins/MIME | 2 | 9, 9, 9, 9, 9, 0 |
| Shared detections | 8 | 9, 9, 9, 9, 9, 9 |
| Webdriver; WebGL IDs | 2 | 0, 0, 0, 0, 0, 0 |

Totals remain 105/126, 108/126, 96/126, 96/126, 105/126, and 72/126; rates remain 83.3, 85.7, 76.2, 76.2, 83.3, and 57.1%; misses remain 21, 18, 30, 30, 21, and 54.

Retained qualifications: grouping uses complete six-method state-count vectors; recipe counts preserve original weighting; ablations are separately refitted; all methods have 0/252 controlled-normal alarms; U, FAILED, and EMPTY_MODEL are zero on these held-out positions; rules use saved RETENTION while the tree uses saved FITTED results; all eight dagger-marked recipe names are listed; the three additional no-cap screen detections have a distinct historical-normal cost linked to Table 5. The caption's adjacent-cell merging clause is removed because the revised table no longer merges method cells.

## Table 4: fixed specialist comparisons

The repeated Study column becomes full-width Memory, Timezone, and Geometry group headings. Every fixed-check label is retained verbatim, including `Host upper bound (standalone)`. The freed width supports one-line check names wherever feasible. Detection symbols accompany the original fractions; only positive normal-alarm fractions receive a warning triangle.

| Group / fixed check | Detection fraction and symbol | Normal alarms |
|---|---|---|
| Memory / Web memory > 8 GiB | partial, 6/18 | 0/48 |
| Memory / Native memory envelope | full, 18/18 | 0/48 |
| Timezone / Absolute Web offset | full, 6/6 | warning, 6/30 |
| Timezone / Native timezone reference | full, 6/6 | 0/30 |
| Geometry / Fixed Web height | full, 6/6 | warning, 6/66 |
| Geometry / Same-Web viewport relation | none, 0/6 | 0/66 |
| Geometry / Host upper bound (standalone) | full, 6/6 | 0/66 |

Retained qualifications: normal system changes (6) and layout changes (6) belong to the corresponding normal denominators; U and FAILED are zero; six no-effect memory operations are excluded from both the 18 effective modifications and 48 normals. The legend limits all outcome symbols to tested records.

## Table 5: single-column historical-normal outcomes

The float changes from `table*` to `table`; the table width changes from `\textwidth` to `\columnwidth`. Repeated cohort names and N values become two full-width cohort group headings. Configuration is shortened to `Config.`; the method names and all T/F/U triples are unchanged. Values appear above short, equal-width bars, with each segment determined solely by its count divided by that cohort's N.

| Cohort / N | Configuration | Integrated App T/F/U | No cap T/F/U |
|---|---|---|---|
| Historical development / 144 | 01 / 02 | 1 / 135 / 8 | 144 / 0 / 0 |
| Historical development / 144 | 03 | 0 / 136 / 8 | 144 / 0 / 0 |
| Historically reserved / 117 | 01 / 02 | 1 / 110 / 6 | 117 / 0 / 0 |
| Historically reserved / 117 | 03 | 0 / 111 / 6 | 117 / 0 / 0 |

The caption still states that configurations 01 and 02 have equal counts and are shown together without pooling. N is not doubled. T explicitly means alarm on these historical-normal records; F means definite no alert; U means unknown. A fully dark no-cap bar therefore means all normal records triggered an alarm, not successful detection. FAILED and EMPTY_MODEL remain zero. Bars are 0.30 of the outer column width and share the same total visual width within this table.

## Table 6: paired App–Browser outcomes

The four modification rows retain their original N and T counts, with full/none detection symbols. The normal-alarm row is separated by a rule and uses unadorned numerical counts, so the modification-detection legend cannot be mistaken for a safety claim.

| Record family | N | Integrated App T | Integrated App + C1 T |
|---|---:|---|---|
| App timezone | 2 | full, 2 | full, 2 |
| App language | 2 | none, 0 | none, 0 |
| Browser timezone | 5 | none, 0 | full, 5 |
| Browser language | 5 | none, 0 | none, 0 |
| Normal alarms | 46 | 0 | 0 |

The caption continues to distinguish T as detection for modification rows and alarm for the normal row. U and FAILED remain zero, and the paired material's development-use history remains explicit. The prior conditional column definitions are replaced by one layout with a flexible family column and fixed result widths; no data logic changes.

## Handoff and verification boundary

Source-level comparison against v3 passed: Table 3 group counts, signed deltas, totals, rates and misses match; Table 4 retains all seven check labels and fourteen fractions; all eight Table 5 printed triples match both the original values and the bar arguments, and each bar's counts sum to its cohort N; all five Table 6 rows retain their original counts, with no detection symbol on the normal-alarm row. The independent semantic-review agent also checked the v3 source/CSV mapping and found no change required.

The owning agent did not compile or change surrounding float placements. The parent will load the shared macros, compile the manuscript, inspect all four tables in rendered PDF, verify any line wraps and proportional bars, and handle Table 3 / Figure 3 separation. Particular visual checks: small historical T=1 bar segments must remain proportional rather than enlarged; the Table 4 standalone qualifier must remain visible; every normal-alarm row must keep its distinct meaning.
