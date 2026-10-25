# Release validation

Result: **PASS** for the authorized Reviewer Release v1.0. All selected sources have project-lead public authorization. Dataset and bundled-code licenses remain unselected; no upload was performed.

## Executed checks

| Check | Result |
|---|---|
| Existing dataset tests | 28 passed |
| Added release tests | 34 passed |
| Entire dataset suite | 62 passed, 0 failed, 0 errors, 0 skipped; 8.112 seconds |
| Source freeze and original evidence reconciliation | Passed for all 1,509 observations |
| Preconversion preservation baseline | Feature values, annotations, pairs, random IDs, source groups, redactions and missingness unchanged; metadata only updates authorization status |
| Historical private source lock and identity map | Byte-for-byte unchanged |
| Schema, feature policy, field types and availability | 5,684 JSONL rows validated |
| Observations and views | 1,509: 558 App177 + 951 Paired244 |
| Recorded-evidence labels | 618: 170 modified + 442 normal_control + 6 no_effect |
| MTC uncertainty and missingness | All 891 remain unlabeled; 3 each lack 5 original App fields |
| Relationships | 206 experiment triplets + 951 real linked-endpoint associations |
| Standalone isolated loading | Passed outside repository using isolated Python, standard library only; all 1,509 loaded |
| Standalone statistics | Exact equality for all exported aggregates and field-level distributions |
| Package inventory and integrity | Exactly 18 allowlisted files; byte sizes and ZIP CRC passed |
| ZIP metadata | Fixed neutral timestamps/permissions; no path traversal, links, extra fields or comments |
| Anonymous artifact content | No matched original source paths/digests/UUIDs, known author identities, email, credentials, project links or document author metadata |
| Private material exclusion | No mapping, provenance, raw captures, internal logs, Git history or repository source audit |
| Rebuild failure behavior | Final archive replaced only after isolated validation succeeds; existing identity map cannot be silently regenerated |
| Repository diff and sample ignores | Passed; generated samples and archive remain ignored |

The negative tests cover schema and type errors, missing/extra tables, duplicate JSON keys, non-finite values, same-size statistic corruption, unknown-label promotion, no-effect labels, phase/group mismatches, missing fields, unredacted values, leaked mapping/identities/credentials/digests, symbolic links, unsafe ZIP paths and metadata, and baseline loss or modification. Deterministic ZIP output is exercised with different source filesystem times.

Commands and individual test results are in `test_report.json`; the final artifact file sizes and standalone results are in `reviewer_release_report.json`. The builder keeps the fresh isolation directory location in private build records only. The release archive is `reviewer_release/Cross_View_Consistency_Dataset_v1.0_Reviewer.zip`.

These checks verify released-data consistency and recorded-source agreement. They do not establish independent physical-device counts, independent experimental replication, full replay of the original detector or immunity to external content matching. Future hosting-page anonymity is untested until the manually chosen sharing mode is inspected. Source ownership and public redistribution authorization are confirmed, not pending.
