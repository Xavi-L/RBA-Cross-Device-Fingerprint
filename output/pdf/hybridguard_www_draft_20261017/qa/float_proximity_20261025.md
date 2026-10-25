# Float proximity and pagination check (2026-10-25 Table 1 redesign)

Verified from fresh `build/main.aux`; all main-paper floats have an explicit prose reference.

| Float | PDF page | Related section | Section starts | Page gap | Context |
| --- | ---: | --- | ---: | ---: | --- |
| Table 1 | 2 | 2.1 | 2 | 0 | Related-work comparison |
| Figure 1 | 3 | 2.2 | 2 | 1 | Observation surfaces |
| Figure 2 | 4 | 3.1 | 3 | 1 | Collection and model-construction pipeline |
| Table 2 | 5 | 4.1 | 5 | 0 | Evaluation materials |
| Table 3 | 6 | 5.1 | 6 | 0 | RQ1 detection and ablations |
| Table 4 | 6 | 5.2 | 7 | 1 | RQ2 reference mechanisms |
| Figure 3 | 7 | 5.2 | 7 | 0 | RQ2 reference mechanisms |
| Table 5 | 7 | 5.3 | 7 | 0 | RQ3 normal alarms and availability |
| Table 6 | 8 | 5.4 | 8 | 0 | RQ4 linked-Browser extension |

- Float proximity <= 1 page: PASS.
- Table 3 on p.6 and Figure 3 on p.7: PASS.
- Main text ends on p.8; references begin on p.9; total: 11 pages.
- Main-text <= 8 pages: PASS. Total <= 12 pages: PASS.
- Float pages match the latest local baseline. Only Table 1 column widths and wording change; template, font sizes, margins, other figures/tables, and main.tex are unchanged.
