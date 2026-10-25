# Source audit and scope freeze

Status: internal candidate only. All sources require human authorization review; none is approved for public distribution. The audit inspected the current remote default-branch state before implementation and used the corresponding existing local sources. The exact repository revision, exact source paths and immutable input hashes are recorded in the ignored private source lock. `source_inventory.json` exposes file-level hashes and non-sensitive paths; precise receipt filenames remain private.

## Scope decisions

| Source | Available records / positions | Selected | Classification and reason |
|---|---:|---:|---|
| `deliverables/webgl1_fresh_comparison_v1` raw backend archives | 381 | 378 | `release_candidate`; three smoke observations excluded; 126 independently recorded target effects and 252 pre/post controls |
| `deliverables/memory_relation_validation_v1` new batch and raw archives | 72 | 72 | `release_candidate`; separate task; six no-effect operations retained |
| `deliverables/timezone_relation_validation_v1` new batch and raw archives | 36 | 36 | `release_candidate`; separate task; legitimate system changes retained as controls |
| `deliverables/screen_geometry_observation_v1` formal v15 batch | 72 | 72 | `release_candidate`; six earlier engineering-smoke observations excluded; geometry is not an integrated App-model result |
| `deliverables/cross_endpoint_constrained_extension_v1/results/members.jsonl` | 951 total; 60 controlled linked positions | 60 | `release_candidate`; 18 pilot + 42 canonical matched positions; raw endpoint and qualification joins checked |
| `hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/paired_244.jsonl` | 1,028 | 891 | `restricted`; frozen P2 representatives only, privacy/third-party release scope unresolved |
| Final MTC `app_only_177.jsonl` | 654 | 0 | `excluded` from the paper-linked cohort; real App-only records, not paired records with empty Browser slots |
| Final MTC `partial.jsonl` | 11 | 0 | `excluded`; partial source quality |
| Final MTC `repeated_observations.jsonl` | 6 | 0 | `excluded`; upstream repeat routing |
| Final MTC `quarantine.jsonl` | 0 | 0 | Empty audited view |
| Alternate MTC snapshot without `_final` suffix | 1,028 paired + 654 App-only + 11 partial + 6 repeats | 0 additional | `excluded`; all 1,028 paired sample identities overlap the final paired snapshot |
| Browser67 pilot snapshot/archive/rebuild | 18 paired | 0 additional | `excluded` as additional observations; the exact 18 are already selected in the linked study |
| Matched linked collection attempts | 48 | 42 via canonical member list | Six original attempts were replaced under the recorded selection procedure, not added as extra normals/modifications |
| Current `backend_server/expanded_collected_data.jsonl` | 229 | 0 | `excluded`; generic mutable historical path, 113 older and 116 status-bearing payloads; not the frozen paper MTC cohort |
| Week 6 evidence release CSV | 393 | 0 | `excluded`; redacted metadata cannot be joined to raw App177 payloads |
| Week 7 complete manifest / annotation registry | 51 / 51 | 0 | `excluded`; distinct historical pilot, outside the current paper denominator |
| Week 7 partial manifest | 466 | 0 | `excluded`; missing collection manifests, failure-analysis only |
| Legacy `latest_paired244_sources.json` route | Configuration exists; referenced latest snapshot absent | 0 | `unverified`; older collector/probe assumptions do not authorize inventing or relabeling a current snapshot |

The final technical candidate has **1,509 distinct original App observation identities**. Cross-selected-source identity overlap is zero. The absence of equal identities does not establish independence across environments, devices, collection batches or studies. Saved model predictions, folds, historical replays and duplicate archive copies are never counted as new observations.

## Source architecture and joins

The backend stores original received payloads, accepted collection receipts, sessions, Browser archives and pairing provenance separately. The frozen expanded-v2 field registry defines 84 Native, 26 Host and 67 App Web features; status-bearing versions preserve the conceptual App177 contract. Browser Web contributes a real additional 67-field payload. The collector CSV has 181 rows because four are top-level metadata; those are not extra fingerprint signals.

The generic `dataset_sources.json` config and `build_dataset_snapshot.py` provide existing provenance/QC and label separation. This exporter reuses the frozen normalizer and validator but does not infer collector-observed status from mere value presence. Historical split and labels come from the appropriate frozen registry, never the generic current backend path. Optional nested research evidence was available in the local checkout; absence in another checkout is a documented reconstruction dependency.

For MTC, the P2 `sample_registry.jsonl` selects `primary_representative` rows of the paired view. Snapshot source lines bind to original raw archives; App/Browser sessions, existing payload identity strings, profiles and completed pair receipts agree. The 891 representatives use 868 transitive groups, not 891 proven devices. Three selected App payloads lack five source fields each. Cohort labels remain unknown.

Controlled and specialist joins are described in `CONTROLLED_EVIDENCE.md`; Browser joins and replacement attempts are described in `BROWSER_EVIDENCE.md`. Private row provenance provides exact original file/line or selector references for every candidate. The candidate package contains no such identity mapping.

## Hashes, ownership and permissions

`source_inventory.json` records original file SHA-256 digests because this release task explicitly requires a frozen source inventory. These are integrity/provenance checks, not anonymization of sample IDs. Original sources are opened read-only. The private lock rejects source-content changes; exporter revisions are separately recorded in `manifest.json`.

Technical exportability, ownership, permission, privacy approval and scientific validity are distinct. `release_candidate` means the records have an executable export path, not approval. MTC is classified `restricted` pending third-party scope and privacy review. No written public redistribution approval or dataset license is supplied by code. Missing or unverified optional sources remain documented and excluded.

Existing raw records were already present in the public repository when this task began. This work adds no raw samples or mapping to Git and does not rewrite existing history. Prior exposure and linkage to original fingerprints require separate review before any anonymity claim.
