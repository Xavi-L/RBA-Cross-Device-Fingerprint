# Tables 1–2: visual and compact layout revision

## Scope and implementation

Only `tables/table_01.tex` and `tables/table_02.tex` are modified by this task. The main prose, abstract, figures, citations, all material counts, and experiment boundaries are retained. Both table bodies remain two-column floats at `\small`, `\arraystretch=1.12`, and `\tabcolsep=4pt`; body compactness comes from column allocation, short labels, and removing repetition, not smaller type or tighter leading. After the root task's first PDF check confirmed single-line body rows and no overflow, the newly introduced evidence key and count/design footnote were set to `\footnotesize`, matching Tables 3–6. Their content and the table-body type size and leading remain unchanged. The Table 2 footnote marker has explicit spacing before and after it.

Table 1 uses the shared `\HGTag{...}` macro supplied by the root task. The six keys name evidence types. They do not mean supported/unsupported capabilities, and they do not rank the cited work. The original limiting caption is unchanged. All six keys have explicit definitions immediately below the table. A single rule and a bold method name distinguish the present study without adding an unsubstantiated superiority claim. The two focus columns have more horizontal space; evidence definitions are presented once in a three-row, two-column key.

Table 2 uses merged material-family labels (`Controlled`, `MTC`, `Specialist`, `Paired`) and thin rules to make the dataset hierarchy visible. The symbols Δ and N label counts of effective modifications and normal records, respectively; they are defined directly below the table. They are not detection or accuracy symbols. The controlled experiment design is attached by footnote `a` to its held-out row. Every other qualifier stays in the corresponding row. Grouping removes the repeated MTC/specialist prefixes without removing material identities.

No compilation was performed by this task. Final line breaks, overfull warnings, and page placement must be checked by the root build. The old table-specific mutations in `polish_matrix_layout()` must be disabled or adapted before rebuilding these rewritten files.

## Table 1: complete semantic mapping

| Original row | Original evidence | Revised evidence key (verbatim definition) | Original research focus → revised focus | Original present-study focus → revised focus |
| --- | --- | --- | --- | --- |
| FP-Scanner, `ref04` | Browser attributes; JavaScript/HTTP discrepancies | **D**: Browser attributes; JavaScript/HTTP discrepancies | Countermeasure-induced inconsistencies → unchanged | Associated Native and Host references → Associated Native/Host references |
| Picasso, `ref05` | Canvas challenge responses | **C**: Canvas challenge responses | Claimed device-class checking → unchanged | Current-record semantic compatibility → unchanged |
| FP-Inconsistent, `ref06` | Within-request and temporal inconsistencies | **I**: Within-request and temporal inconsistencies | Evasive bot traffic → unchanged | Controlled edits versus normal changes → Controlled edits vs. normal changes |
| BrowserFM, `ref07` | Fingerprint/configuration dependencies | **G**: Fingerprint/configuration dependencies | Configuration modeling and analysis → unchanged | Applicability and evidence-availability costs → Applicability + evidence-availability costs |
| WebView studies, `ref08,ref09,ref10` | App, JavaScript, and runtime observations | **S**: App, JavaScript, and runtime observations | Exposure and cross-boundary tracking → Exposure + cross-boundary tracking | Report-integrity assessment → unchanged |
| HybridGuard | Native, Host, App Web; optional Browser | **R**: Native, Host, App Web; Browser optional | Contextual references under explicit domains → Contextual references; explicit domains | Detection, normal alarms, and unknown outcomes → Detection, normal alarms, unknown outcomes |

The abbreviations `/`, `+`, and `vs.` in the focus cells replace conjunctions without changing the named concepts. `Browser optional`, `explicit domains`, `normal alarms`, and `unknown outcomes` remain explicit. No cross, blank capability cell, or newly inferred literature fact is introduced.

## Table 2: complete count and boundary mapping

The caption still specifies that counts are **record positions, not independent physical devices**.

| Original material | New material grouping / subset | Δ | N | Preserved role or boundary |
| --- | --- | ---: | ---: | --- |
| Controlled App | Controlled / App | 126 | 252 | `Disjoint held-out positions` remains in the row. Footnote a preserves `14 manipulation recipes × 3 repetitions × 3 environments`. |
| MTC discovery | MTC / Discovery | — | 630 | `Training-side constraints and tree training` remains verbatim. |
| MTC historical development | MTC / Historical development | — | 144 | `Historical evaluation with development exposure` remains verbatim. |
| MTC historically reserved | MTC / Historically reserved | — | 117 | `Historical evaluation; not a newly blinded cohort` remains verbatim. |
| Memory specialist | Specialist / Memory | 18 | 48 | `Fixed checks; 6 no-effect operations excluded` remains verbatim. |
| Timezone specialist | Specialist / Timezone | 6 | 30 | `Includes 6 normal system changes` remains verbatim. |
| Geometry specialist | Specialist / Geometry | 6 | 66 | `Includes 6 normal layout changes; not integrated` remains verbatim. |
| Paired App–Browser | Paired / App–Browser | 14 | 46 | `60 development-used positions: pilot 18 + matched 42` remains verbatim. |

The dashes in the three MTC modification cells are unchanged. No new interpretation of those dashes is asserted. The table does not label the historical or paired material as blinded or held out. The geometry specialist remains explicitly outside the integrated detector.
