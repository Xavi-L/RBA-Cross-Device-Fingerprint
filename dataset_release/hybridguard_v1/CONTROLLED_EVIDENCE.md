# Controlled and specialist evidence

All 558 selected controlled and specialist observations are included in the authorized Reviewer Release. The user explicitly confirmed the project lead's public authorization on 2026-10-25. Existing privacy filtering remains unchanged. The checks below verify consistency of existing records; they are not a new physical experiment or independent replication.

| Source | Selected observations | Normal controls | Effective modifications | No effect | Complete triplets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Controlled main benchmark | 378 | 252 | 126 | 0 | 126 |
| Memory specialist | 72 | 48 | 18 | 6 | 24 |
| Timezone specialist | 36 | 30 | 6 | 0 | 12 |
| Host geometry formal study | 72 | 66 | 6 | 0 | 24 |

The 558 selected observations have distinct source session identities. They are repeated measurements in three emulator environment categories, not 558 independent physical devices. No independent physical-device count or new train/test split is established. Each source has prior development exposure.

## Source locations and correspondence

The source locators below identify existing repository materials; they are not files included in a public data package. Raw identifiers and exact record-level mappings remain private.

| Source | Raw source pattern | Label and membership evidence | Paper relationship |
| --- | --- | --- | --- |
| Controlled main | `deliverables/webgl1_fresh_comparison_v1/runs/<environment>/backend/raw_expanded_payloads.jsonl` | `prepared/EFFECT_AUDIT.json`, `prepared/RAW_ROLE_INDEX.json`, configuration registry, sessions, accepted attempts and execution receipts | Controlled App benchmark in RQ1/RQ3 |
| Memory | `deliverables/memory_relation_validation_v1/runs/<environment>/backend/raw_expanded_payloads.jsonl` | `new_batch.jsonl.gz`, `summary.json`, operations and receipts | Standalone memory study in RQ2 |
| Timezone | `deliverables/timezone_relation_validation_v1/runs/<environment>/backend/raw_expanded_payloads.jsonl` | `new_batch.jsonl.gz`, operations, receipts and saved workflow/triplet evidence | Standalone timezone study in RQ2 |
| Host geometry | `deliverables/screen_geometry_observation_v1/runs/<environment>/backend/raw_expanded_payloads.jsonl` | `predictions.jsonl.gz`, operations, receipts, saved workflow and geometry bindings | Formal v15 Host geometry study in RQ2 |

Every selected row contains the actual Native 84, WebView Host 26 and App Web 67 feature structure under `expanded-v2.2-status`. Raw envelopes use `expanded-raw-payload-v1`. No Browser observation is present in these sources, and none is synthesized. All 558 selected payloads pass the existing App177 normalization adapter.

The original field-status counters contain 177 `observed` statuses per observation. This is a collection statement, not proof that every value is informative or useful for a detector. Field values, sentinel handling and normalized quality remain separate concepts. The current canonical adapter returns 98,766 `observed_value` cells across these 558 records; this does not validate every possible interpretation of those values.

## Performed evidence checks

The controlled benchmark has 381 raw records: 378 frozen primary observations and three excluded environment-registration smoke observations. The selected observations correspond to 14 recipes, three repetitions, three environments and three phases. All 126 saved effect audits pass. The exporter checks their declared values against the current raw payloads, verifies actual pre-to-active target changes and pre-to-post restoration, and checks accepted attempts, receipt/session associations and the execution receipt. A successful tool receipt alone is insufficient for a `modified` label.

The memory specialist contains 24 attempted interventions. The raw pre/active/post values and saved adjudications establish 18 effective target changes and six operations that reached an already-reported value. All 24 triplets restored. Receipts confirm no-op controls before and after intervention, removal of the future-document script and process cleanup. The six no-effect records remain `no_effect`; they are neither effective modifications nor silently added to the paper's 48 normal positions.

The timezone specialist includes legitimate system timezone changes and Web-only overrides. Saved workflow evidence, current-session receipt associations, raw target values and restoration agree for 12 triplets. Six Web-only changes are effective modifications; 30 positions have recorded normal-control support. A legitimate system co-change is not labeled as a malicious modification merely because a value changes.

The Host geometry task uses only the 72 formal v15 observations. The saved legacy screen values, synchronized Web geometry and Host-before/Host-after measurements match the raw geometry module. Current-session bindings, operation receipts, target-change evidence and restoration agree. There are 66 supported normal positions and six effective modifications. Synchronized geometry is supplemental evidence; it is not substituted for the original App177 Host fields.

The exporter does not execute collection, attacks, fitting or detector prediction. Saved specialist detector states are kept separate from target-effect labels. A detector alert is not evidence that an intervention occurred. The label `normal_control` describes the absence of the declared target manipulation under the recorded control workflow, not comprehensive benignness.

## Overlap and exclusions

Saved outputs across folds, retained models, ablations and historical replays reuse observations. They do not produce additional samples. In particular, the memory historical archive and the timezone model predictions reuse the main controlled and historical MTC records.

The Host geometry v15 replay repeats the same 72 selected observations and is excluded as a duplicate. Six preliminary geometry smoke observations and the later 12-position v16 engineering study are outside the frozen formal task. The latter retains ten evaluated positions and two `FAILED_EVIDENCE` positions; it is not merged into the formal benchmark. Exclusion does not relabel failures or unknown outcomes as successes.

Within this adapter, the selected source session identities do not overlap. This does not establish statistical independence between studies, devices or reused emulator environments. The global build checks overlap against the other adapters.

## Privacy and release boundary

The adapter returns original payloads, identifiers and exact source locators only to the private build pipeline. Public-facing records require release-specific random IDs and an explicit feature/metadata privacy policy. Raw session IDs, installation IDs, receipt IDs, document IDs, exact timestamps, local paths and internal infrastructure details must not be copied into the public package.

Geometry supplemental evidence contains document/session identifiers and detailed clocks. It remains private unless a dedicated allowlist extracts only approved measurements and status fields. Raw execution receipt filenames also contain exact timestamps. Consequently, the exact input inventory belongs in the private freeze manifest. The repository-facing source inventory retains file-content hashes and masks timestamp-bearing or sample-specific basenames. This inventory is excluded entirely from the Reviewer Release, because original source hashes and paths could expose provenance. These content hashes establish input consistency and do not establish anonymity. Public authorization is recorded separately in the release manifest. Hashing original identifiers does not establish anonymity.
