# HybridGuard dataset v1.0 candidate

**INTERNAL CANDIDATE — NOT APPROVED FOR PUBLICATION.** This directory ships reproducible extraction code, schema, aggregate statistics and review documents. The tracked `data/` directory contains **zero observations**. No dataset license has been selected. Do not upload the candidate or this repository as an anonymous artifact before the reviews in `RELEASE_REVIEW.md` are completed.

HybridGuard studies consistency between Android Native, WebView Host, App Web and a linked Browser Web observation. This candidate uses existing frozen records associated with the current anonymous WWW 2027 submission. It contains no new collection, attacks, training or detector evaluation. Saved detector outcomes are annotation evidence, not new results.

## Sources and statistical units

The internal de-identified export contains 1,509 original observations: 558 App177 and 951 Paired244. There are 1,506 structurally complete observations and three incomplete MTC observations. A view name identifies the observed endpoint arrangement and nominal schema, not a guarantee that every value exists or survives privacy suppression.

| Task subset | Observations | Interpretation |
|---|---:|---|
| Controlled App | 378 | 14 recipes × 3 repetitions × 3 emulator environments; 126 modified and 252 correlated pre/post controls |
| Historical MTC | 891 | Frozen representatives, historical discovery/development/reserved cohorts of 630/144/117; unlabeled |
| Memory specialist | 72 | 18 modifications, 48 controls and 6 no-effect operations |
| Timezone specialist | 36 | 6 modifications and 30 controls, including legitimate system changes |
| Host geometry specialist | 72 | 6 modifications and 66 controls; separate synchronized geometry measurements |
| Linked Browser development | 60 | Pilot 18 + matched 42; 14 modifications and 46 controls |

These are observations and experimental positions, **not 1,509 independent devices**. Source-specific grouping is retained through random IDs. Physical-device identity is not established. Studies share development history and emulator environments; their observation totals must not be used as independent replication counts. See `SOURCE_AUDIT.md`, `CONTROLLED_EVIDENCE.md` and `BROWSER_EVIDENCE.md`.

## Layout

- `schema.json`, `SCHEMA.md`, `field_catalog.json`: row contract, field types, units, availability and per-field privacy policy.
- `statistics.json`, `STATISTICS.md`: statistics computed from the final internal candidate, clearly separated from the zero-row public scope.
- `source_inventory.json`: audited source scope and file hashes; timestamp-bearing receipt basenames are hidden. Exact paths, row bindings and identity mappings are private.
- `manifest.json`, `quality_report.json`: version, publication gate and technical checks.
- `scripts/`, `tests/`: standard-library Python implementation and tests.
- `.private/candidate/`: ignored internal JSONL export. `.private/identity_map.json`, `provenance.jsonl`, `source_lock.json` and audits are **never** included in the review ZIP or committed.
- `data/`: placeholder only, pending explicit authorization and privacy approval.

Each observation joins `features.jsonl`, `metadata.jsonl` and `annotations.jsonl` on a random `sample_id`. `pairs.jsonl` represents 206 verified clean/active/post groups and 951 linked App–Browser observations. `features` contains only values, availability and privacy disposition; cohort, grouping, tools, labels and detector outputs are separate. Geometry measurements are explicitly outside the fixed 177/244 slots in `features.supplemental`.

## Rebuild and validation

Requirements: Python 3.10 or later and access to the frozen repository sources, including the available nested research checkout. No third-party Python dependencies are needed. From the repository root:

```sh
python3 dataset_release/hybridguard_v1/scripts/release.py all
python3 -m unittest discover -s dataset_release/hybridguard_v1/tests -v
python3 dataset_release/hybridguard_v1/scripts/release.py verify
python3 dataset_release/hybridguard_v1/scripts/load_example.py --data dataset_release/hybridguard_v1/.private/candidate
python3 dataset_release/hybridguard_v1/scripts/release.py package
```

The first `all` call freezes existing sources; later calls refuse changed source files. Exporter code revisions are recorded separately in `manifest.json`. A private mapping is reused so repeated builds retain release IDs. An independently created mapping intentionally yields different random IDs and the same observation-level statistics. The frozen source paths/hashes can be checked, but code cannot supply missing redistribution permission. Missing source files fail explicitly; a documentation-only checkout cannot rebuild the candidate.

The packager creates `.private/hybridguard_v1_INTERNAL_REVIEW_ONLY.zip` by an explicit allowlist. It contains de-identified candidate data and review documents, **no raw data, private mappings, row provenance, source lock or Git history**. It remains an internal review archive and is not an approved anonymous upload.

## Loading example

The following runs from this dataset directory after a successful build:

```python
from pathlib import Path
from scripts.load_example import load
records = load(Path('.private/candidate'))
features, metadata, annotation = records[0]
assert features['sample_id'] == metadata['sample_id'] == annotation['sample_id']
cell = features['fields']['web_data.device_memory']
# A usable value requires checking status and redaction, not only a non-null value.
usable = cell['collection_status'] == 'observed' and cell['redaction'] == 'none'
print(len(records), usable)
```

Within an extracted internal review ZIP, use `python3 scripts/load_example.py --data internal_candidate`.

## Research uses and limits

Suitable uses include evidence-availability analysis, controlled target-effect analysis, memory/timezone consistency and the separately recorded Host-geometry measurements. Paired244 supports linked-endpoint diagnostics; App177 has no Browser endpoint and is not interchangeable with Paired244.

This privacy-filtered candidate **does not reproduce every original detector input or every manuscript score**. It suppresses build/device strings, user agents, renderer strings, fingerprint hashes, exact timestamps, infrastructure and other free text. Annotation effects refer to the original evidence, even where target fields are suppressed. Numeric/boolean features and narrowly validated language/timezone/geometry semantics remain potentially identifying in combination. See `PRIVACY.md`.

`normal_control` means no declared target intervention in a supported controlled position, not comprehensive benignness. MTC observations remain `unlabeled`; reported no-target collection context does not establish a benign ground-truth label. Legacy collector `observed` status does not resolve sentinel ambiguity or prove scientific validity. No train/validation/test split is generated. Historical cohort membership is provenance with prior development exposure.

## Paper and permission status

Association: the current anonymous WWW 2027 manuscript, Evaluation Protocol, Results and reproducibility appendix. No author names, affiliations, email addresses or public repository URL are included here. Anonymous hosting, data ownership, third-party redistribution scope, institutional review, field-level risk and a dataset license require separate human approval. A pattern scan is not an anonymization guarantee.
