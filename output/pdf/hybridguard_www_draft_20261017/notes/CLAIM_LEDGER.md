# Evidence ledger for the WWW draft

Read-only audit on 2026-10-17. This ledger records saved evidence and implementation; it does not execute collection, fitting, candidate selection, prediction, condition evaluation or timing. Paths below are relative to the repository root. The controlling writing scope is `paper/EXPERIMENT_OUTLINE.md` (2026-10-16): overview plus materials 01, 03, 02, 04, in that order.

## Method identities and counting units

- `APP_FULL` is the three frozen `B_REL_TZ` RETENTION rule models. It includes Native–App Web memory and timezone references; it excludes standalone Browser C1, new Host geometry and later resource extensions. The App177 collection catalog has Native84 + Host26 + App Web67 fields; this is not evidence that all 177 fields, or each of the three surfaces, independently contributes to the fitted detector.
- `PAIRED_BASE` is frozen Full App OR accepted C1. It is neither a Browser-only model nor a resource extension or four-view tree.
- Four rule ablations were retrained from their own SPARSE initialization through RETENTION in each original fold; they are not post-hoc deletion from the selected final rule list. `APP_TREE` is a depth-3 shared-candidate-representation reference, not an upper bound for all machine learning or all raw App177 inputs.
- Counts are stage positions/controlled interventions, not independent devices. The three model configurations repeatedly evaluate the same specialist/MTC records and do not triple sample size. Equal aggregates do not prove recordwise equality.
- Detection rate = T / confirmed effective interventions; normal alarm proportion = T / supported normal records; defined-output coverage = (T+F)/N. U, FAILED and EMPTY_MODEL remain in the appropriate denominators. F means no selected condition triggered, not proven authenticity or safety.

Authoritative sources: `deliverables/app177_core_ablation_v1/{REPORT.md,SETTINGS.json}`, `deliverables/app_browser_evidence_consolidation_v1/REPORT.md`, `deliverables/cross_endpoint_constrained_extension_v1/{PROTOCOL.md,REPORT.md}`.

## Material 01: complete-model contribution matrix

| Method | Effective modifications T/N | Rate | Controlled normal alarms |
|---|---:|---:|---:|
| Full App | 105/126 | 83.33% | 0/252 |
| No MTC alarm cap | 108/126 | 85.71% | 0/252 |
| App Web only | 96/126 | 76.19% | 0/252 |
| No memory relation | 96/126 | 76.19% | 0/252 |
| No timezone relation | 105/126 | 83.33% | 0/252 |
| Small App tree | 72/126 | 57.14% | 0/252 |

All main-result U, FAILED and EMPTY_MODEL counts are zero. Five compressed rows preserve 14 configurations: resource (1), screen (1), timezone + plugins/MIME (2), common detections (8), webdriver + WebGL identifiers (2). The resource row is 9,9,0,0,9,0 out of 9; screen is 6,9,6,6,6,0; timezone/plugins is 9,9,9,9,9,0 for each original configuration; common detections are all 9; webdriver and WebGL identifiers are all 0.

Read-only CSV verification performed: all 12 method/identity rows in `results/summary/main.csv` equal their sums over all 168 configuration/identity rows in `configurations14.csv`. Source: `deliverables/app177_core_ablation_v1/results/summary/{main,configurations14,all_stages}.{csv,json}`. Display mapping: `paper/figures/experiment_storyboards_20261016/01_compact_groups.json`.

The Full App screen result is only 6/9; removing the MTC alarm cap adds three screen detections. Webdriver and WebGL misses are retained. MTC legacy raw WebGL and webdriver-false semantics prevent those candidates from meeting the 90% evaluability gate; this is a representation/availability boundary, not proof those manipulations are intrinsically undetectable.

## Material 03: normal-alarm constraint

Counts below are T/F/U, separately for each indicated model configuration. FAILED and EMPTY_MODEL are zero.

| Cohort | Full App 01 and 02, each | Full App 03 | No cap 01/02/03, each |
|---|---:|---:|---:|
| MTC discovery, N=630, training constraint | 6/573/51 | 0/579/51 | 630/0/0 |
| MTC development, N=144, historical evaluation | 1/135/8 | 0/136/8 | 144/0/0 |
| MTC reserved_validation, N=117, historical evaluation | 1/110/6 | 0/111/6 | 117/0/0 |

Thus the 261 historical evaluation records contain Full App alarms 2/2/0, U=14 for every model, defined=247/261 (94.64%). Removing only the alarm cap adds 3/126 controlled detections but alarms on every record of each MTC group. MTC still participates in candidate/defined-output constraints in this ablation; do not call it complete removal of MTC data.

Other methods' aggregate historical T/F/U, N=261: Web-only 3/257/1, 3/257/1, 1/259/1; no-memory 2/258/1, 2/258/1, 0/260/1; no-timezone 3/244/14, 3/244/14, 1/246/14; tree 0/261/0 in all configurations. The tree has 73/891 MTC records with at least one unknown input candidate despite binary output; it does not restore missing observations.

Sources: `deliverables/app177_core_ablation_v1/results/summary/{mtc,tree_input_integrity}.{csv,json}`; storyboard `03_table_data.json`. Read-only verification confirmed all 18 original F02 rows equal development+reserved sums at N=261. Keep 144 and 117 separate in the manuscript's main table as specified by the controlling outline.

## Material 02: fixed specialist checks, not complete-model scores

| Specialist | Check | Detection | Normal alarms |
|---|---|---:|---:|
| Memory | Web memory > 8 GiB (`R_WEB8`) | 6/18 | 0/48 |
| Memory | Native memory envelope (`R_REL`) | 18/18 | 0/48 |
| Timezone | Absolute Web offset threshold (`R_ABSOLUTE`) | 6/6 | 6/30 |
| Timezone | Native timezone reference (`R_TZ`) | 6/6 | 0/30 |
| Screen | innerHeight > 710 (`R_HEIGHT710`) | 6/6 | 6/66 |
| Screen | Same-Web viewport relation (`R_SAME_WEB`) | 0/6 | 0/66 |
| Screen | Host geometry upper bound (`R_HOST_GEOMETRY`) | 6/6 | 0/66 |

Memory targets 4/8/16 GiB each have six effective operations: R_REL detects 6/6 in each; R_WEB8 detects 0/6,0/6,6/6. Target 2 GiB caused no observable change in six operations; both checks produce 0/6 alarms there. These six are separate from the 18 effective interventions and 48 normal records. Evidence covers tested upward modifications, not downward, within-envelope or coordinated changes.

Six normal timezone-change middle positions belong to the 30 normal records. Six normal Host-layout-change middle positions belong to the 66 normal records. Do not add these subset denominators again. All shown check U/FAILED counts are zero. Geometry uses v15 formal 72 positions, not v16 engineering tests; it is still standalone and cannot replace the Full App screen 6/9 result. Three emulator environments and repeated observations do not establish real-device or population FPR.

Sources: `paper/figures/experiment_storyboards_20261016/02_table_data.json`, `paper/figures/round1_app/data/F03b.csv`, `deliverables/memory_relation_validation_v1/{REPORT.md,summary.json}`, `deliverables/timezone_relation_validation_v1/{REPORT.md,summary.json}`, `deliverables/screen_geometry_observation_v1/{REPORT.md,SUMMARY.json}`.

## Material 04: accepted Browser timezone increment

| Method | App timezone | App language | Browser timezone | Browser language | Total | Normal |
|---|---:|---:|---:|---:|---:|---:|
| Full App | 2/2 | 0/2 | 0/5 | 0/5 | 2/14 | 0/46 |
| Full App + C1 | 2/2 | 0/2 | 5/5 | 0/5 | 7/14 | 0/46 |

Counts hold separately for all three model configurations. The five added detections are three pilot and two matched Browser-timezone positions. All shown U/FAILED counts are zero. The 60 positions comprise pilot18 + matched42 and have development-use history. They are not added to the App main denominator.

The normal cost must accompany the gain: on historical development144 the paired model is 1/132/11 for 01/02 and 0/133/11 for 03; reserved117 remains 1/110/6 or 0/111/6. Combined unknowns rise 14→17 out of 261, defined coverage 247/261→244/261 (94.64%→93.49%); alarm counts remain 2/2/0. C1 has no time-alignment gate; timestamp differences are diagnostic only, so temporal settings/DST changes remain a limitation.

Sources: `paper/figures/experiment_storyboards_20261016/04_table_data.json`, `paper/figures/round2_paired/data/F05a.csv`, `deliverables/cross_endpoint_constrained_extension_v1/{REPORT.md,PROTOCOL.md}`, `deliverables/app_browser_evidence_consolidation_v1/tables.json`.

C2, preferred-language mismatch, was a genuine candidate. It makes both normal Browser language-preference change records alarm, exceeding the separate matched-normal budget (2/34 > floor(.05×34)=1). C1+C2 also has only 566/630 defined MTC training outputs, below 90%. Neither candidate was removed based on its name; the fixed finite selection retains C1 only. Both language families remain undetected by the accepted method.

## Dataset provenance and interpretation

- QC paired main view has 1,028 records, represented by 891 manufacturer/model/Android-release combinations plus 137 repeats; there are 868 model families among paired records. 891 is not a physical-device count. Physical-device identity remains unknown.
- P2 grouped manufacturer/model families and known installation/session/scenario associations transitively. Primary representatives use earliest eligible archive order, independent of rule outcomes. Frozen representative split is 630/144/117; paired group counts are 610/142/116. Known same-model-across-OS, installation and session links do not cross splits.
- Earlier P2 `unlabeled`/`NOT_EVALUATED` files are retained. Later evaluation uses a separate research-normal-condition side table, supported by collection instructions, implementation and archived batches. Normal means no study-defined target modification, not third-party attestation or absence of cloud automation/debugging.
- All current materials have development contact. Outer environmental holdout controls fitting access, but does not establish untouched, independent or unseen-tool generalization after iterative research use.

Sources: `deliverables/mtc_p1_20260922/P1_REPORT.md`, `deliverables/mtc_p2_20260922/P2_REPORT.md`, `deliverables/mtc_cap8_replay_v1/DATA_NOTES.md`.

## Claims to avoid and disclosure boundaries

The draft retains a qualified, narrowly scoped first explicit Native--Host--App Web formulation claim following the related-work comparison documented in LITERATURE_VERIFICATION.md; this is not established by experimental counts or proof of global literature absence. Do not claim universal three-layer contribution, population zero FPR, general attack detection, exact/atomic cross-layer synchronization, trustworthy hardware attestation, or superiority to all machine learning. Root `Abstract.md` supplies the three-surface novelty intent; literature comparison, rather than experiment totals, is the basis for the qualified formulation claim. Consistency does not prove authenticity; coordinated modifications can satisfy all checks.

Do not import old 69/229 materials, early high detection rates, P6 difference/coverage counts, four-view-tree development results or unaccepted resource19/26 into this draft's main score. The accepted resource-extension selection retained S0; its negative result may be mentioned only with its own scope if needed.

Ethics evidence is limited: the current Android manifest declares INTERNET and ACCESS_NETWORK_STATE only; MTC requirements explicitly forbid blanket permissions, login-dependent collection, target fingerprint manipulation, attack tools and rooting for that collection. No IRB approval/exemption or participant-consent record was found in the relevant audited sources. Do not invent approval, exemption, participant consent or a completed public-data release. Source: `android_app/HybridGuard/featureapp/src/main/AndroidManifest.xml`, `deliverables/mtc_20260916/百度MTC云真机采集需求说明.md`, `deliverables/mtc_cap8_replay_v1/DATA_NOTES.md`. Raw fingerprints, ticket credentials and private operational records are outside the draft artifact.
