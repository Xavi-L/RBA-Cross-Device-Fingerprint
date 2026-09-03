# Paper Working Package Manifest

Snapshot date: 2026-09-03

Repository directory: `thesis_materials/paper_working_package_20260903/`

## Files

| Path | Purpose |
|---|---|
| `README.md` | Package overview, frozen writing boundaries and usage instructions |
| `planning/paper_scope_and_claim_boundaries.md` | Paper positioning, current/future boundary, two-state protocol and prohibited overclaims |
| `planning/claim_evidence_matrix.md` | Claim-by-claim evidence level, safe wording and missing prerequisites |
| `planning/author_and_repository_boundary.md` | Division of work between the main system repository and the companion attack repository |
| `planning/evaluation_track_reconciliation.md` | Reconciles the attack-side 100-run track with the main-repository 69-pair track |
| `planning/open_issues_and_next_gates.md` | Admission gates for formal App177, Browser67/paired244, RAG and benchmark evaluation |
| `literature/literature_screening_summary.md` | Consolidated screening decisions from 85 de-duplicated candidate references |
| `literature/P0_literature_deep_reading.md` | Focused reading notes for ten closest neighboring works |
| `literature/related_work_gap_matrix.md` | Task and novelty differences between HybridGuard and adjacent literature |
| `literature/references_curated.bib` | Curated core, support and historical-optional BibTeX entries |
| `writing/draft_claim_language.md` | Recommended and prohibited language for system, result and contribution claims |
| `draft/compile_validation.md` | Build history, archive contents and integrity information |
| `draft/HybridGuard_ACM_Draft_Flattened_Overleaf_20260903.zip` | Source-only, flattened ACM/Overleaf paper project with two-track evaluation wording |
| `draft/HybridGuard_ACM_Draft_TwoTrack_20260903.pdf` | Compiled review PDF corresponding to the updated flattened draft |

## Draft archive integrity

### Overleaf ZIP

- Size: `39,656` bytes
- SHA-256: `6971539f0a911ff0b2e082ece30c96ba20ef5b90b7db22942bdf848a095cf83e`
- Contents: `hybridguard_draft.tex`, `references.bib`, `README.md`
- ZIP integrity test: passed
- Flattened source compile: 18 pages, 0 unresolved citations/references

### Compiled PDF

- Size: `546,380` bytes
- SHA-256: `378c6ee166b6d8d26aee1047b6752cc2383e8a2b077bbbd1a3b4ffa4c847e838`
- Pages: 18
- Ghostscript parse: passed
- Render inspection: passed on title/abstract, methodology tables, results, discussion, conclusion and evidence ledger

## Current evaluation-version policy

The current draft preserves two complementary controlled App177 tracks rather than forcing one mixed denominator:

- attack-side stability campaign: 100 effect-positive active runs, attack-side frozen evaluator, 70/100 formal responses;
- main-repository paired re-evaluation: 69 qualified baseline-active pairs, 51/69 official-derived and 33/69 deterministic-registry transitions.

These counts use different statistical units and evaluator versions and must not be pooled into one detection metric.

## Version policy

This directory is a versioned paper-writing snapshot. Future updates should create a new dated directory or an explicitly versioned subdirectory when any of the following changes materially:

- FeatureApp or Browser probe release lock;
- App177/Browser67 field contract;
- attack-side stability-campaign denominator or evaluator ledger;
- main-repository qualified-pair denominator or evaluator catalogs;
- label and stable-group eligibility;
- Browser67/paired244 evaluation status;
- paper structure or target venue.
