# ACM Full-Prose Draft Compile and PDF Validation

Validation date: 2026-09-02

## Revision scope

- Converted all outline-style lists and drafting callouts in the manuscript sections into connected prose.
- Removed all `itemize`, `enumerate`, and `description` environments from the section text.
- Removed all manuscript TODO markers and unused draft-status macros.
- Left existing tables and the internal evidence-ledger table structurally unchanged.
- Preserved the App177-only current evaluation, two-state protocol, Browser67 future-evaluation boundary, and historical/preliminary result separation.

## Build result

- Main source: `hybridguard_draft.tex`
- Document class: `acmart`, `sigconf, anonymous, review`
- Output: `hybridguard_draft.pdf`
- Page count: 16
- Bibliography database: 41 curated entries
- References appearing in the compiled draft: 31
- Undefined citations or cross-references: 0
- Overfull horizontal boxes: 0
- Overfull vertical boxes: 0
- Remaining TODO markers: 0

## PDF validation

- The PDF was opened successfully by Poppler and Ghostscript.
- Ghostscript completed a null-device parse with status 0.
- All 16 pages were rendered at 140 dpi.
- Representative pages covering the title and abstract, related work, problem formulation, system design, evidence pipeline, methodology, results, historical experiments, future Browser67 study, discussion, references, and evidence ledger were visually inspected.
- No clipped text, overlapping elements, broken glyphs, or malformed App177/Browser67/paired244 macros were observed.

## Non-blocking notes

- The ACM bibliography style reports metadata-completeness warnings for several proceedings entries, mainly missing venue address, publisher, or page information. These warnings do not leave unresolved citations.
- Some underfull box warnings remain because of two-column line breaking and the retained tables; they do not produce visible clipping or overlap.
- The internal evidence-ledger appendix is a drafting aid and should be removed or rewritten before formal submission.
