# Float proximity check (2026-10-25)

Verified against a fresh pdflatex build and main.aux. Each float has an explicit in-text reference; the float is at most one PDF page away from the start of its relevant discussion subsection.

| Float | PDF page | Related section | Section starts | Page gap | Context |
| --- | ---: | --- | ---: | ---: | --- |
| Table 1 | 2 | 2.1 | 2 | 0 | Related-work comparison |
| Figure 1 | 3 | 2.2 | 2 | 1 | Observation surfaces |
| Figure 2 | 4 | 3.1 | 3 | 1 | Collection and model-construction pipeline |
| Table 2 | 5 | 4.1 | 5 | 0 | Evaluation materials |
| Table 3 | 6 | 5.1 | 6 | 0 | RQ1 detection and ablations |
| Table 4 | 6 | 5.2 | 6 | 0 | RQ2 reference mechanisms |
| Figure 3 | 7 | 5.2 | 6 | 1 | RQ2 reference mechanisms |
| Table 5 | 7 | 5.3 | 7 | 0 | RQ3 normal alarms and availability |
| Table 6 | 8 | 5.4 | 7 | 1 | RQ4 linked-Browser extension |

- Table 3: p.6; Figure 3: p.7.
- Main text ends on p.8; entire PDF has 10 pages.
- All float placements pass the <=1-page proximity constraint.
