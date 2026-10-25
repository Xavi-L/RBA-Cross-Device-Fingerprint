# Cross-View Consistency Dataset v1.0 — Reviewer Release

This self-contained release contains **1,509 de-identified Android, WebView and linked Browser observations** associated with an anonymous WWW 2027 submission. The project lead has confirmed public authorization for every included source. All controlled experiments, specialist experiments, Linked Browser observations and selected MTC records are included. The dataset reuse license remains **PENDING_SELECTION**; `LICENSE_OPTIONS.md` records recommendations without applying a license.

## Load and validate

Extract the archive into a new directory, enter the `cross_view_consistency_v1` folder and run these commands from that folder. Only Python 3.10 or later and the Python standard library are needed; no network access or original research checkout is required.

```sh
python3 validate.py --root .
python3 load_example.py --data .
python3 validate.py --root . --recompute-statistics ../recomputed-statistics.json
```

The optional last command saves the recomputed statistics outside the package. The output must not already exist. Keep the extracted package at its original 18-file inventory; additional files or subdirectories inside it cause validation to fail.

The loader returns all 1,509 observations. The validator checks the schema, row counts, joins, view structure, explicit missingness, recorded labels, relationships and recomputed released-data statistics. Passing validation confirms consistency of this released projection. It does not constitute a new experiment or reproduce original detector predictions.

A minimal independent read is:

```python
import json
from pathlib import Path

root = Path('.')
def rows(name):
    with (root / name).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]

features = rows('features.jsonl')
metadata = {row['sample_id']: row for row in rows('metadata.jsonl')}
annotations = {row['sample_id']: row for row in rows('annotations.jsonl')}
assert len(features) == len(metadata) == len(annotations) == 1509
assert {row['sample_id'] for row in features} == set(metadata) == set(annotations)
cell = features[0]['fields']['web_data.device_memory']
usable = cell['collection_status'] == 'observed' and cell['redaction'] == 'none'
print(len(features), 'observations; first memory cell usable:', usable)
```

Check the value's meaning and legacy sentinel behavior as well as the status before scientific use. A null redacted value differs from an unavailable or absent measurement; false and zero are not automatically missing.

## Included observations

| Source | Observations | View | Labels |
|---|---:|---|---|
| Controlled App | 378 | App177 | 126 modified; 252 normal controls |
| Memory specialist | 72 | App177 | 18 modified; 48 normal controls; 6 no-effect |
| Timezone specialist | 36 | App177 | 6 modified; 30 normal controls |
| Host geometry specialist | 72 | App177 | 6 modified; 66 normal controls |
| Linked Browser pilot | 18 | Paired244 | 6 modified; 12 normal controls |
| Linked Browser matched study | 42 | Paired244 | 8 modified; 34 normal controls |
| Historical MTC | 891 | Paired244 | 891 unlabeled |
| Total | 1,509 | 558 App177; 951 Paired244 | 170 modified; 442 normal controls; 6 no-effect; 891 unlabeled |

Labels for 618 observations were checked against saved collection and intervention evidence. MTC labels remain unverified and are not supervised benign examples. A `normal_control` label identifies the recorded experimental condition; it is not comprehensive evidence of benignness.

App177 has 84 Native, 26 WebView Host and 67 App Web slots. Paired244 adds 67 genuinely collected Browser Web slots. All 558 App177 observations and 948 Paired244 observations have a complete original field structure. Three Paired244 MTC observations each lack five original fields; their missingness remains explicit. Collection availability and privacy suppression are tracked separately from structural completeness.

The release preserves 206 three-phase experiment groups and 951 App–Browser endpoint associations. Sample, group and relationship IDs are random release identifiers. Source-specific grouping and pairing are retained; physical-device identity and the number of independent devices are unknown. Historical MTC discovery/development/reserved counts are 630/144/117 and reflect prior development exposure. No new independent train/validation/test split is created.

## Files and analysis boundary

The package contains exactly 18 files:

| File | Content |
|---|---|
| `features.jsonl` | 1,509 rows of values, original slot presence, availability and redaction; geometry supplements are separate from nominal slots |
| `metadata.jsonl` | 1,509 source, group, view, cohort and quality rows |
| `annotations.jsonl` | 1,509 recorded-label, operation-effect and saved-outcome rows |
| `pairs.jsonl` | 1,157 relationships: 206 experiment groups and 951 linked endpoints |
| `schema.json` | Machine-readable record contracts |
| `field_catalog.json` | Types, units and privacy policy for all 244 nominal field paths |
| `statistics.json` | Computed released-data distributions |
| `quality_report.json` | Build-time consistency, evidence and preservation results |
| `manifest.json` | Version, authorized scope, license status and byte sizes for the other 17 files |
| `validate.py` | Standalone validation and descriptive-statistics recomputation |
| `load_example.py` | Standalone sidecar loading |
| `README.md` | Loading commands, file inventory and interpretation |
| `DATASET_CARD.md` | Population, provenance limits, label semantics and intended uses |
| `SCHEMA.md` | Human-readable field and record dictionary |
| `STATISTICS.md` | Human-readable aggregate statistics |
| `RELEASE_REVIEW.md` | Confirmed authorization and remaining decisions |
| `LICENSE_OPTIONS.md` | Unapplied license recommendations |
| `FIGSHARE_UPLOAD.md` | Suggested title, English description, keywords and upload file |

Use retained values to inspect availability, redaction, cross-view consistency, controlled mechanisms and recorded geometry. Reproduce aggregate counts and relationships using the validator. Do not infer missing Browser values, turn model-output rows into additional observations, or count repeated environments as independent replications.

The privacy projection suppresses identifying strings, high-entropy fingerprints, infrastructure and exact clocks. Some intervention targets are therefore absent from released values. **The original full detector and all manuscript scores cannot be reproduced from this projection.** Saved detector outcomes are annotations; they are not newly evaluated results or label ground truth.

The artifact excludes direct author metadata, original-source locators, source-digest inventories, raw logs, private identity mappings and repository history. Retained hardware, language/timezone, geometry, availability and grouping combinations may still support linkage. The checks do not prove global anonymity or prevent matching against other available records. Hosting-page anonymity must be checked separately when a sharing link is created.
