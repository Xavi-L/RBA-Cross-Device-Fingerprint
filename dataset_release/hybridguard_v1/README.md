# HybridGuard dataset v1.0 — Reviewer Release

**Public release of all 1,509 selected observations is authorized.** On 2026-10-25, the user explicitly confirmed the project lead's authorization for every included source: controlled experiments, specialist experiments, Linked Browser and MTC. This supersedes the earlier pending-authorization state. The existing privacy projection is retained. The data and designated accompanying resources are licensed under **Creative Commons Attribution 4.0 International (`CC-BY-4.0`)**; see `LICENSE_DATA.md` for scope and anonymous attribution. The bundled scripts have software-license status `NOT_SPECIFIED` and are excluded from this data-license grant. No external upload is performed by the build.

This directory contains the extraction implementation and repository-facing evidence. The separately built **Reviewer Release** is self-contained and excludes source locators, source digests, private mappings and repository history. The tracked `data/` directory still contains zero observations; this describes repository hosting, not the authorized release scope or archive contents.

HybridGuard studies consistency between Android Native, WebView Host, App Web and a linked Browser Web observation. The release uses existing frozen records associated with the current anonymous WWW 2027 submission. It performs no new collection, attacks, training or detector evaluation. Saved detector outcomes remain annotation evidence.

## Sources and statistical units

The release contains **1,509 observations: 558 App177 and 951 Paired244**. There are 1,506 structurally complete observations and three incomplete MTC observations, each lacking five original fields. A view identifies the actual endpoint arrangement and nominal schema; it does not guarantee that every value exists or survives privacy suppression.

| Task subset | Observations | Recorded evidence |
|---|---:|---|
| Controlled App | 378 | 126 modified and 252 correlated pre/post controls |
| Historical MTC | 891 | Historical discovery/development/reserved cohorts of 630/144/117; all unlabeled |
| Memory specialist | 72 | 18 modifications, 48 controls and 6 no-effect operations |
| Timezone specialist | 36 | 6 modifications and 30 controls, including legitimate system changes |
| Host geometry specialist | 72 | 6 modifications and 66 controls; separate synchronized geometry measurements |
| Linked Browser development | 60 | Pilot 18 + matched 42; 14 modifications and 46 controls |

The 618 non-MTC labels are verified against recorded evidence: 170 modified, 442 normal controls and six no-effect operations. The 891 MTC observations remain `unlabeled`. These are observations and experimental positions, **not 1,509 independent devices**. Physical-device identity and independence are unknown. Studies share development history and emulator environments. No new train/validation/test split is created. See `SOURCE_AUDIT.md`, `CONTROLLED_EVIDENCE.md` and `BROWSER_EVIDENCE.md`.

## Layout

- `schema.json`, `SCHEMA.md`, `field_catalog.json`: row contract, field types, units, availability and privacy policy.
- `statistics.json`, `STATISTICS.md`, `quality_report.json`: computed statistics and validation results.
- `manifest.json`: release scope, authorization statement, version and license status.
- `source_inventory.json`: repository-facing source audit. Original source paths and digests are excluded from the Reviewer Release.
- `scripts/`, `tests/`: Python implementation and tests; `reviewer_templates/` contains independent package documentation.
- `.private/candidate/`: sanitized intermediate data; `.private/` also holds private source bindings and the reusable identity map. These private materials are excluded from the release.
- `reviewer_release/Cross_View_Consistency_Dataset_v1.0_Reviewer.zip`: generated self-contained release archive, ignored by Git.
- `data/`: repository-hosting placeholder; it is not the release payload.

Each observation joins `features.jsonl`, `metadata.jsonl` and `annotations.jsonl` on the existing random `sample_id`. `pairs.jsonl` preserves 206 three-phase experiment groups and 951 real linked App–Browser observations. Features contain values, availability and privacy disposition; labels, grouping, tools and saved detector outcomes are separate. Synchronized geometry remains supplemental to the nominal 177/244 slots.

## Rebuild and validation

Requirements for rebuilding from original evidence: Python 3.10 or later and the frozen repository sources, including the available nested research checkout. No third-party Python dependencies are required. From the repository root:

```sh
python3 dataset_release/hybridguard_v1/scripts/release.py all
python3 dataset_release/hybridguard_v1/scripts/release.py verify
python3 dataset_release/hybridguard_v1/scripts/build_reviewer_release.py
python3 -m unittest discover -s dataset_release/hybridguard_v1/tests -v
```

Before writing, the extraction build automatically preserves the existing four candidate tables, private random-ID map and source lock in an immutable local comparison baseline. A missing map or changed baseline fails explicitly; it does not regenerate identifiers. The extraction build checks frozen inputs and reuses the private random-ID map. It does not change original records, labels, cohort membership or pairing. Missing evidence fails explicitly. A documentation-only checkout cannot reconstruct the original-source export; reviewers do not need those sources to load or validate the supplied release.

Extract `reviewer_release/Cross_View_Consistency_Dataset_v1.0_Reviewer.zip` into a new directory, change into its `cross_view_consistency_v1` folder and run:

```sh
python3 validate.py --root .
python3 load_example.py --data .
python3 validate.py --root . --recompute-statistics ../recomputed-statistics.json
```

The optional statistics output must be a new file outside the package. The validator requires the original 18-file inventory and rejects extra package entries.

For a license-only rebuild, preserve the previously published ZIP separately and pass `--preserve-data-from /path/to/previous.zip` to `build_reviewer_release.py`. The builder compares SHA-256 for the four JSONL tables and statistics.json before replacing the final ZIP; any difference fails. The before/after comparison and final archive checksum are recorded in `reviewer_release_report.json` and `license_update_report.json`.

The validator recomputes released-data statistics and checks schema, labels, references, completeness and packaging constraints. It validates the released projection and does not reproduce original detector predictions. `VALIDATION.md` records actual executed checks and results.

## Research uses and limits

Suitable uses include field-availability and redaction analysis, controlled target-effect analysis, memory/timezone consistency and separately recorded Host geometry. Paired244 supports linked-endpoint diagnostics; App177 has no Browser endpoint. `normal_control` describes the declared controlled condition, not comprehensive benignness. An observed collector status does not resolve legacy sentinel ambiguity.

The release **cannot fully reproduce original detector inputs or all manuscript scores**. Build/device strings, user agents, renderer strings, fingerprint hashes, exact timestamps and other sensitive values remain suppressed. Original intervention labels remain attached even when the changed field is suppressed. Saved detector outcomes are neither rerun predictions nor labeling ground truth.

Direct identity and infrastructure removal does not establish mathematical anonymity. Retained numeric, categorical, language/timezone, geometry and grouping combinations can support linkage, including to previously available records. Repository-facing evidence is deliberately excluded from the reviewer archive; do not upload this source directory as a substitute. Final hosting metadata and the selected sharing URL require manual inspection for double-blind review. See `PRIVACY.md` and `FIGSHARE_UPLOAD.md`.
