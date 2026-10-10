# HybridGuard ACM Draft - Full Prose Revision

This package is the full-prose revision of the unlimited-length HybridGuard working draft. It is based on the uploaded ACM `acmart` template, the current HybridGuard repository evidence, the controlled-manipulation repository snapshot, and the curated literature review.

## What changed in this revision

All outline-style manuscript content has been converted into connected English prose. In particular, the revision rewrites the contribution list, observation-surface definitions, task boundaries, research questions, design principles, accepted data views, knowledge-source taxonomy, evidence-extraction steps, pair-qualification criteria, relation outcomes, reporting quantities, uncovered manipulation families, and the future Browser67 comparison matrix. Draft TODO markers and evidence-status callouts have been removed. Existing tables and the internal evidence-ledger appendix are retained without substantive redesign, as figures and tables are outside the scope of this pass.

## Compile

On Overleaf, set `hybridguard_draft.tex` as the main document and compile with pdfLaTeX/BibTeX. A typical local command is:

```bash
latexmk -pdf -bibtex -interaction=nonstopmode hybridguard_draft.tex
```

If the local `bibtex` executable is unavailable but `bibtex8` is installed, use:

```bash
pdflatex -interaction=nonstopmode hybridguard_draft.tex
bibtex8 hybridguard_draft
pdflatex -interaction=nonstopmode hybridguard_draft.tex
pdflatex -interaction=nonstopmode hybridguard_draft.tex
```

## Evidence boundaries retained

- Current controlled attack evaluation: **App177 only**.
- Experimental protocol: **baseline -> attack_active** only.
- Browser67/paired244: implemented data path, with **future detection-effect evaluation**.
- Current `51/69` and `33/69` values: controlled no-alert-to-alert transition counts, **not recall**.
- Historical grouped-CV, teacher-label, LLM/RAG, and on-device material: retained in a dedicated preliminary section and not merged with current controlled results.
- No manuscript page limit is imposed at this drafting stage.

## Main files

- `hybridguard_draft.tex`: main ACM file.
- `sections/01_introduction.tex`: Introduction with contributions rewritten as prose.
- `sections/02_background_related_work.tex`: literature-grounded Background and Related Work.
- `sections/03_problem_threat_model.tex` to `sections/09_future_browser67.tex`: full prose problem, method, results, historical, and future-evaluation chapters.
- `sections/10_discussion.tex` and `sections/11_conclusion.tex`: discussion and conclusion.
- `appendix/a_draft_evidence_ledger.tex`: internal claim-status ledger, retained for drafting.
- `references.bib`: curated bibliography.
- `hybridguard_draft.pdf`: compiled review copy.
- `compile_validation.md`: build and rendering checks for this revision.

Before formal submission, replace anonymous metadata, update the target venue fields and CCS terms, decide which historical material remains, remove or rewrite the internal evidence ledger, add final figures/tables, freeze the definitive data and relation releases, and normalize remaining bibliography metadata warnings.
