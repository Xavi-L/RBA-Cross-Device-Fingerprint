# 5 Results

## 5.1 RQ1: Detection and Component Comparisons

Integrated App detects 105/126 controlled modifications with 0/252 controlled-normal alarms (Table 3). The refitted Web-only and no-memory alternatives each detect 96/126; all nine differences occur in the CPU-plus-memory recipe. No-timezone retains 105/126 because an absolute-offset condition substitutes on this benchmark. Removing the MTC cap adds three screen detections, whose normal-data cost appears in Section 5.3. The fixed App tree detects 72/126.

**Table 3. Controlled benchmark-position outcomes.** All methods have zero U, FAILED, and EMPTY_MODEL counts on these held-out positions. Ablations are separately refitted models.

| Method | Detected / modified | Detection (%) | Missed | Normal alarms |
| --- | --- | --- | --- | --- |
| Integrated App | 105/126 | 83.3 | 21 | 0/252 |
| No MTC cap | 108/126 | 85.7 | 18 | 0/252 |
| Web-only | 96/126 | 76.2 | 30 | 0/252 |
| No memory | 96/126 | 76.2 | 30 | 0/252 |
| No timezone | 105/126 | 83.3 | 21 | 0/252 |
| App tree | 72/126 | 57.1 | 54 | 0/252 |

All six methods miss 9/9 webdriver-only and 9/9 WebGL-identifier modifications. Historical raw WebGL unavailability and lost webdriver-false semantics limit the admission of their corresponding candidates. These misses expose gaps in the available feature representation and candidate-admission process for the tested edits. Appendix A describes the recipe grouping, and the supplemental tables retain all 84 recipe-by-method cells.

## 5.2 RQ2: What References Contribute

The specialist studies evaluate fixed checks separately from the fitted detectors to distinguish three mechanisms (Figure 3; Table 4). Their comparators use Web memory above 8 GiB, Web timezone offset above −480 minutes, and Web height above 710 CSS pixels. The fixed thresholds provide study-specific reference points for comparing the three semantic mechanisms. Appendix A.5 describes their recorded freezing and the scope of these comparisons.

![Figure 3. How contextual references contribute.](../figures/HybridGuard_Fig3_mechanisms_v2.png)

**Figure 3.** Illustrative mechanisms on applicable observations. (a) A Web report of 8 GiB stays within the fixed 8 GiB comparator but exceeds the envelope derived from Native memory of 4 GiB. (b) After offsets are converted to the same sign convention, a normal system change moves Native and Web together, whereas a Web-only edit creates a mismatch. (c) A converted viewport dimension P exceeding the Host bound plus tolerance triggers the standalone geometry check.

**Table 4. Fixed specialist comparisons.** Normal system changes (6) and layout changes (6) are included in their respective normal denominators. U and FAILED are zero throughout. Six no-effect memory operations are excluded from both the 18 effective modifications and the 48 normals.

| Study | Fixed check | Detected / modified | Normal alarms |
| --- | --- | --- | --- |
| Memory | Web memory > 8 GiB | 6/18 | 0/48 |
| Memory | Native memory envelope | 18/18 | 0/48 |
| Timezone | Absolute Web offset | 6/6 | 6/30 |
| Timezone | Native timezone reference | 6/6 | 0/30 |
| Geometry | Fixed Web height | 6/6 | 6/66 |
| Geometry | Same-Web viewport relation | 0/6 | 0/66 |
| Geometry | Host upper bound (standalone) | 6/6 | 0/66 |

**Device-specific memory context.** The nine CPU-plus-memory positions separating Integrated App from the refitted alternatives also trigger the fixed 8 GiB check. That main-benchmark difference alone does not establish the need for a device-specific reference. The memory specialist supplies the distinction: the Native envelope detects 18/18 modifications, versus 6/18 for the global threshold, with 0/48 normal alarms for both. Its twelve additional detections are upward edits to 4 and 8 GiB; both checks detect six edits to 16 GiB. Neither triggers on the six no-effect operations targeting 2 GiB. These twelve specialist detections are separate from the nine App-model differences and concern the tested upward edits.

**Legitimate timezone co-change.** Both checks detect 6/6 modifications. The absolute-offset check also alarms on six normal system changes; the Native reference avoids those alarms. Thus, unchanged main-benchmark detection after removing Native timezone hides a difference in handling legitimate changes. Modification totals alone do not expose this benefit.

**Host container context.** The fixed Web-height check detects 6/6 modifications but alarms on 6/66 normals. The same-Web viewport relation avoids normal alarms yet misses all six modifications. The Host bound achieves 6/6 detection and 0/66 alarms. This standalone result does not describe Integrated App: configurations 01/02 retain the old height check and alarm on the six normal layout changes, while configuration 03 misses the six modifications. Integrating the Host specialist requires a separate model-construction evaluation.

## 5.3 RQ3: Normal Alarms and Unavailable Evidence

Removing the historical-normal alarm cap raises controlled detection from 105 to 108 but alarms on every record in both historical groups (Table 5). Both alternatives have 0/252 controlled-normal alarms, so the controlled benchmark alone conceals this cost. Saved uncapped models include broad conditions such as hardware concurrency greater than one and language-list length greater than one. The controlled-normal budget alone does not adequately constrain these checks on MTC records.

**Table 5. Historical-normal outcomes.** T denotes alarm, F definite no alert, and U unknown. Configurations 01 and 02 have equal counts and are displayed together, not pooled. FAILED and EMPTY_MODEL are zero.

| Cohort | N | Configuration | Integrated App: T / F / U | No cap: T / F / U |
| --- | --- | --- | --- | --- |
| Historical development | 144 | 01 / 02 | 1 / 135 / 8 | 144 / 0 / 0 |
| Historical development | 144 | 03 | 0 / 136 / 8 | 144 / 0 / 0 |
| Historically reserved | 117 | 01 / 02 | 1 / 110 / 6 | 117 / 0 / 0 |
| Historically reserved | 117 | 03 | 0 / 111 / 6 | 117 / 0 / 0 |

On the separate 630 training normals, Integrated App configurations 01/02/03 produce 6/6/0 alarms and 51 unknowns each; uncapped models alarm on all 630. We keep these training outcomes separate from evaluation. Each Integrated App configuration yields 14/261 unknowns across the two historical evaluation groups. Removing memory reduces that count to 1/261 but also loses resource detections. A tree can return a definite label when some candidate states are unknown, because its traversed path need not use those candidates. Binary output does not imply complete observation.

## 5.4 RQ4: Increment from a Linked Browser

On the 60 development-used positions that also support extension selection, C1 raises detection from 2/14 to 7/14 (Table 6). All five additions are Browser timezone modifications. The extension preserves App timezone detections but adds no language detections; both methods have 0/46 normal alarms. All three frozen configurations give these counts, which we report once rather than as 42 modified positions. The results describe the selected extension on this material, without estimating future paired-data performance.

**Table 6. Paired App–Browser outcomes.** T is detection for modification rows and alarm for the normal row. U and FAILED are zero on this paired material; it has development-use history.

| Record family | N | Integrated App: T | Integrated App + C1: T |
| --- | --- | --- | --- |
| App timezone | 2 | 2 | 2 |
| App language | 2 | 0 | 0 |
| Browser timezone | 5 | 0 | 5 |
| Browser language | 5 | 0 | 0 |
| Normal alarms | 46 | 0 | 0 |

C1 also raises historical unknowns from 8/144 to 11/144 in development, while leaving 6/117 in the historically reserved group. The combined count increases from 14/261 (5.4%) to 17/261 (6.5%) per model, with unchanged alarms. C1 has no timestamp gate, so the observed 0/46 normal alarms does not establish robustness to asynchronous legitimate timezone changes. The paired language operations differ from the language-list recipe detected in the App benchmark. C1 provides a targeted increment for the tested timezone edits, accompanied by lower definite-output coverage.
