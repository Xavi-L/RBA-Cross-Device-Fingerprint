# 4 Evaluation Protocol

## 4.1 Questions and Materials

We evaluate controlled App detection (RQ1), the contribution of semantic references (RQ2), normal alarms and evidence availability (RQ3), and the increment from a linked Browser (RQ4). Table 2 defines each study's denominator and role. Each study's reported rates summarize outcomes across its recorded evaluation positions. Because the studies have different development histories and may overlap in source records or analysis ranges, we report them separately.

**Table 2. Evaluation materials and their roles.** Counts are record positions, not independent physical devices.

| Material | Effective modifications | Normal records | Evaluation role |
| --- | --- | --- | --- |
| Controlled App | 126 | 252 | 14 manipulation recipes × 3 repetitions × 3 environments; disjoint held-out positions |
| MTC discovery | — | 630 | Training-side constraints and tree training |
| MTC historical development | — | 144 | Historical evaluation with development exposure |
| MTC historically reserved | — | 117 | Historical evaluation; not a newly blinded cohort |
| Memory specialist | 18 | 48 | Fixed checks; 6 no-effect operations excluded |
| Timezone specialist | 6 | 30 | Includes 6 normal system changes |
| Geometry specialist | 6 | 66 | Includes 6 normal layout changes; not integrated |
| Paired App–Browser | 14 | 46 | 60 development-used positions: pilot 18 + matched 42 |

The controlled App benchmark uses API 29, 30, and 36 emulators with SwiftShader. Fourteen manipulation recipes, three repetitions, and three environments yield 126 effective modifications. Each run contributes a normal pre-intervention record and a confirmed post-restoration record, yielding 252 correlated normal positions. Model configurations 01, 02, and 03 hold out API 29, 30, and 36, respectively. Each model uses 84 modified and 168 normal training positions, then evaluates 42 modified and 84 normal held-out positions. We aggregate these disjoint held-out positions once. Prior development exposure to the recipes and environments limits claims about unseen tools and physical devices.

The mobile test-cloud (MTC) collection contains 891 records organized by manufacturer, model, and Android release, with representatives recurring across collection positions. The 630-record discovery group supplies training constraints and tree training; the historical cohorts of 144 and 117 records have prior development exposure and are reported separately. Here, “normal” refers to records without the target manipulation, while debugging and automation may remain part of the collection context.

## 4.2 Compared Methods

Integrated App combines within-view and cross-view checks. Four alternatives each rebuild their sparse and retention stages: no MTC alarm cap, App Web information only, no memory, and no timezone. Removing the cap relaxes only the alarm budget; MTC assessability and coverage requirements remain. These are comparisons between refitted detectors. Web-only changes both the available information and the relations that can be constructed.

The App tree uses the same fold-specific admitted candidates, encoded as T/F/U indicators. It uses Gini splitting, depth three, and a minimum leaf size of two. Half the training weight goes to modifications, one quarter to controlled normals, and one quarter to MTC normals; modification weight is balanced across the 14 recipes. Together, these settings define a fixed-capacity decision-tree baseline over the admitted candidates. We evaluate saved fitted tree outputs and saved retention outputs for rule models. Specialist checks and Integrated App + C1 are reported separately.

## 4.3 Measures and Reconciliation

A T decision counts as a detection on an effective modification and as a normal alarm on a normal record. We tabulate F (definite no alert), U (unresolved evidence), FAILED, and EMPTY_MODEL separately, retaining U positions in the corresponding denominators. Model comparisons preserve each study's original record counts and distinguish aggregate totals from record-level predictions.

We reconcile saved output-state partitions and recipe-level counts with the reported totals and experiment identifiers. These presentation checks assess the consistency of archived results and their tabulation (Appendix A).
