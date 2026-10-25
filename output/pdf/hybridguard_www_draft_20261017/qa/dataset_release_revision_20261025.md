# Anonymous dataset integration and abstract consistency review — 2026-10-25

## Outcome

- Base repository commit: `006791c0d31d880de7f300ecd1782dd716e5d528`.
- Current entry point: `main.tex`; the historical migration was not run.
- Main paper: 8 pages. References begin on page 9. Entire manuscript: 11 pages.
- Abstract: three paragraphs, 238 whitespace-delimited words (previous version: 257).
- PDF SHA-256: `16c3c97d4cd36344f82eeaa4c7e192de458e72ad5785fb45569aed6a096e4191`.
- Table 3 and Figure 3 remain on distinct pages 6 and 7. All main-paper floats are within one page of their relevant discussion subsection.
- No overfull boxes, undefined citations, or undefined cross-references in the final compilation. The existing ACM warning about `printacmref=false` remains a submission-template setting; that setting was not changed.

## Sources and precedence

1. Latest repository LaTeX at the base commit, rather than an older PDF or migration snapshot.
2. User screenshot: the Introduction release notice uses a bold heading, brief release statement, and anonymous URL.
3. User-supplied `HybridGuard_WWW2027_转发包_20261022.zip`: `notes/01_版面预算与结构.md`, `notes/03_证据映射与审稿检查.md`, `reviews/round2_review.md`, and `PAPER_IMPROVEMENT_LOG.md` define the statistical units and evidence boundaries. The ZIP is a 2026-10-22 content revision, not the latest manuscript or a verified eight-page layout. Older statements that data or geometry sensitivity are unavailable were superseded by current evidence.
4. Public artifact: https://anonymous.4open.science/r/cross-view-consistency-artifact-27D2/ . The actual reviewer ZIP was downloaded; its SHA-256 is `7e94f174f7bd5d7839caee78f5b6d1378e22bb67b2f7145658251e2deab4cf1e` (2,316,000 bytes). `README.md`, `DATASET_CARD.md`, `SCHEMA.md`, `STATISTICS.md`, `manifest.json`, and `LICENSE_DATA.md` were inspected. Both bundled Python tools passed; the validator recomputed released-data statistics.
5. Official WWW 2027 research CFP: https://www2027.thewebconf.org/research-track-papers/ . The long-paper limit is eight main pages and twelve total pages, with a self-contained main paper.

## Changes and reasons

| Location | Change | Evidence / reason |
| --- | --- | --- |
| Abstract | Retained three paragraphs; added dataset contribution and normal-alarm/definite-output construction constraints; stated 14 recipes on three emulator environments, 105/126 versus separately refitted 96/126 alternatives, and concentration in CPU-plus-memory; separated Host geometry and summarized historical/Browser costs. | Current §§3–5, table counts, ZIP round-two concerns, and actual release contents. Avoids treating all 105 detections as a cross-layer increment or calling recipes model configurations. |
| Introduction | Added the requested short **Code and Data Release** notice and anonymous URL; shortened repeated context and results summaries. | Screenshot form; actual availability of dataset, loading/validation scripts, and documentation. No claim of fully released detector code or complete experimental replay. |
| §4.1 and Table 2 note | Clarified historical-normal collection context and the 891 unverified MTC labels retained as unlabeled. | Release dataset card and annotations; preserves existing evaluation cohorts and denominators. |
| §4.3 | Added total, schemas, label scope, availability/redaction states, no-effect accounting, tools, and limits of score replay. | Release records and validator behavior. |
| §6.4 | Described random release identifiers and suppression of identifying/high-entropy values and precise clocks, distinguished from collection missingness; retained linkage risk. Shortened the repeated downstream-outcome paragraph. | Actual release projection and dataset card. |
| Conclusion | Connected reported findings with the public dataset and retained conditional interpretation. | Main experimental results and release scope. |
| Appendix A.3–A.5 | Distinguished original research archives from public release; documented source counts, labels, schema completeness, relationships, commands, CC BY 4.0 data/documentation scope and unspecified script software license, and validation boundaries. | Actual package and original experiment descriptions. |
| Appendix A.6 | Preserved all sensitivity values and explanatory claims; formatted the existing result grid as floating Table 7 with caption and reference. | Pure layout correction for a final-page column-balance overflow. |
| Markdown / provenance | Synchronized edited prose, including the previously stale appendix sensitivity text; recorded the explicit user authorization superseding the historical abstract freeze while preserving the baseline. | Current request explicitly includes abstract revision. |

## Dataset-to-experiment reconciliation

| Released source | Observations | Label breakdown |
| --- | ---: | --- |
| Controlled App | 378 | 126 modified + 252 normal controls |
| Memory specialist | 72 | 18 modified + 48 normal controls + 6 no-effect |
| Timezone specialist | 36 | 6 modified + 30 normal controls |
| Host geometry specialist | 72 | 6 modified + 66 normal controls |
| Linked Browser pilot and matched | 60 | 14 modified + 46 normal controls |
| Historical MTC | 891 | unlabeled; historical 630/144/117 groups |
| **Total** | **1,509** | **170 modified + 442 normal controls + 6 no-effect + 891 unlabeled** |

The first four sources make 558 App177 observations; the last two make 951 Paired244 observations. The 618 experimental labels were reconciled against saved evidence. These are observations, not independent devices; the release does not establish new blind splits. The six no-effect memory operations explain why the evaluation-table denominators sum to 1,503 while the released record count is 1,509.

## Preserved scope

- Method formulas, 0.005 coefficient, budgets, thresholds, candidate selection, and all empirical numeric results are unchanged.
- Host geometry remains standalone; refitted alternatives remain refitted; the 60 paired positions remain development-used; U is observed while FAILED/EMPTY_MODEL have no benchmark occurrences.
- Three main figures, six main-table data bodies, and all 18 bibliography entries are retained.
- The original submitted abstract remains in `baseline_source/`. Only the user-authorized current manuscript abstract is revised.
- No new experiment, detector training, or detector replay was claimed. Artifact validation checks the released data projection.

## Verification

The final PDF was rendered and all eleven pages inspected. The anonymous URL is clickable on page 1. Text, tables, figures, commands, equations, and the final sentence are complete and within their columns. `qa/float_proximity_20261025.md` records exact float placements. `qa/current_compilation_20261025.md` records the final source-package synchronization and rebuild check.

The Overleaf archive was independently extracted and rebuilt. Its PDF matches all eleven delivered pages in extracted text and rendered pixels. All archived source hashes and current-file matches passed.
