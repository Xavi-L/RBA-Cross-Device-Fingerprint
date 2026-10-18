# Implementation audit for the WWW methods section

Verified against repository code and saved contracts on 2026-10-17. No experiment was run. Paths are repository-relative.

## Data split and label admission

`deliverables/app177_core_ablation_v1/SETTINGS.json` points to `deliverables/mtc_constrained_reselection_v1/SETTINGS.json`, which binds `deliverables/webgl1_fresh_comparison_v1/prepared/FOLDS.json`.

| Model configuration | Held-out environment | Training | Held-out |
|---|---|---:|---:|
| 01 | webgl1-fresh-api29_swiftshader-v1 | 252 = 84 effective + 168 normal | 126 = 42 effective + 84 normal |
| 02 | webgl1-fresh-api30_swiftshader-v1 | same | same |
| 03 | webgl1-fresh-api36_swiftshader-v1 | same | same |

Three environments × 14 modification configurations × three repetitions × three stages = 378 positions. The union of the three outer test lists has exactly 378 unique positions; each position contributes only its held-out-model result to the 126/252 main denominators. Complete installation/bundle/triplet groups stay in one environment fold. WebView versions are 91.0.4472.114 for API29/30 and 134.0.6998.135 for API36 in the original collection protocol.

The collection uses clean_pre→attack→clean_post. Specialist display `change` is a collection stage, not automatically a positive label. Admission independently checks execution receipts, frozen parameters, actual declared-field changes and restoration. Training requires complete admitted triplets and label=int(phase==attack). The main 378 positions all passed; three installation smoke records are excluded. Neither candidate states nor detector outputs assign the labels. Source collection and admission: `deliverables/webgl1_fresh_comparison_v1/README.md`; exact input checks: `deliverables/app177_core_ablation_v1/data.py`; training checks: `hybridguard_agent/research/rule_learning_v2/adapter.py`.

MTC630 enters as independent normal records, not fabricated triplets. MTC144 and117 are excluded from fitting but are historical evaluation material, not a new blind test. Every specialist/MTC cohort is evaluated separately by each frozen model; repeated model outputs do not multiply N.

## Candidate representation and objective

Full App uses 50 base templates + three fixed relation templates (Native memory, Native timezone and same-Web viewport). Numerical threshold atoms use training-only .25/.5/.75 quantiles. Each ablation directly loads its original fold encoder: no threshold refit, no evaluation-derived preprocessing. Full expanded pools have 65/65/56 atoms before candidate admission. Web-only removes dependencies on Native/Host; no-memory/no-timezone removes both polarities of the respective relation while preserving legal single-field alternatives. New Host geometry and Browser C1/C2 do not enter this App pool.

For selected singleton-OR clause set S, SPARSE scores:

    J(S) = sum_i w_i [output_S(x_i)=T] - 0.005 C(S)
    C(S) = number_of_clauses + total_literal_occurrences.

The sum is over training effective-intervention positions. Weights give each configuration equal mass, each represented environment within a configuration equal mass, and each intervention position within that configuration/environment equal mass. Thus one singleton contributes complexity2 and objective penalty0.01. The objective is whole-OR detection, not the sum of individual rule detections.

Sources: `hybridguard_agent/research/rule_learning/selector.py` (`TrainProblem.score`), `hybridguard_agent/research/rule_learning_v2/adapter.py` (`V2Problem`), `hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json`.

## Frozen constraints

- Controlled-normal OR alarms ≤ floor(.05×168)=8.
- Separate MTC-discovery OR alarms ≤ floor(.05×630)=31. No-cap ablation changes only this cap to630.
- Each admitted candidate must be T/F on at least90% of MTC630; the final OR must yield T/F on at least90% of MTC630.
- Controlled final output T/F coverage must be at least80% separately for attack, clean_pre and clean_post phases.
- Candidate training support: at least three fully T/F triplets, at least two triggered attack triplets, at least one support bundle and one environment. These are modest engineering admission thresholds, not evidence of independent-device support.
- Maximum8 singleton OR clauses, complexity16, maximum2 clauses per family; no opposite polarities of the same atom. Other inherited caps (12 literal occurrences/distinct atoms) are nonbinding for the8-singleton limit.
- Candidate training execution failure is disallowed. EMPTY_MODEL and failed fits are distinct outcomes, never constant normal predictions.
- Deadline60 seconds per fit; no global-optimality claim. Five percent and90% are fixed development settings, not deployment guarantees or population confidence bounds.

Sources: `deliverables/app177_core_ablation_v1/SETTINGS.json`; `hybridguard_agent/research/mtc_constrained_reselection.py` (`DualNormalProblem`); `hybridguard_agent/research/rule_semantics_webgl1_cap8.py` (`PROFILE`, `apply_capacity`); `hybridguard_agent/config/rule_learning_v1_20260924/candidate_grammar.json`.

## SPARSE and RETENTION are different selection stages

SPARSE starts empty, greedily accepts strictly positive objective increments under partial feasibility, retains the best feasible visited set, and performs one deterministic backward-prune pass when deletion preserves feasibility and does not reduce J. Structural semantic keys, not display IDs, resolve final ties. The implementation is heuristic, not an exact optimizer.

RETENTION starts from the same variant's own same-fold SPARSE result and frozen encoder. It considers (a) additions that increase weighted semantic signal-group/attack-position coverage without losing any existing training attack detection, and (b) same-signal-group swaps to registered higher semantic quality. Swaps enforce no lost attack detections, no new controlled-normal alarms and no controlled defined-to-unknown/failed transitions. Every proposed set must satisfy the full dual-normal constraints. Addition ranking is larger macro-detection increment, larger semantic coverage increment, fewer controlled-normal alarms, higher controlled coverage, lower complexity, higher semantic quality, then structural order. The finite step cap is twice the clause cap. Importantly, the code states `old_sparse_objective_still_optimized=False`; do not describe the final RETENTION result as an optimum of J.

Four variants × three folds × two stages =24 saved rule fits. Full App is reused, not refitted. Main rule results use RETENTION consistently; the tree uses FITTED. Sources: `hybridguard_agent/research/{app177_ablation.py,rule_learning_v2/semantic_selection.py,rule_learning_v2/retention.py}` and `deliverables/app177_core_ablation_v1/REPORT.md`.

## Abstention and failure semantics

At runtime only the current record and selected frozen conditions are evaluated. Labels, scenario/direction, phase, split, model-training metadata and future restoration are not prediction features. Selected measured missing/unusable evidence yields U. Binding/structure/execution errors yield FAILED. A failure in any selected dependency dominates even a known T; unselected-field failures do not affect the model. If selected inputs are valid, OR is T when any input is T, F when all are F, U otherwise. Thus T OR U=T, F OR U=U. EMPTY_MODEL remains a separate result. Negation swaps T/F and leaves U.

Sources: `hybridguard_agent/research/rule_learning/{contracts.py,predictor.py}`, `hybridguard_agent/research/app177_ablation.py` (`predict_current`). The observed zero failures in the main batch does not remove these semantics.

## Fixed reference predicates

Memory: with observed positive finite GiB operands in the same bound App record, native memory at least0.25 GiB, alarm when Web memory exceeds the smallest power of two ≥ Native kernel-visible total memory. This is m_web>2^ceil(log2(m_native)); code uses frexp/ldexp to avoid boundary rounding. Lower Web exposures are allowed; no fixed browser8 GiB cap is assumed. Missing, nonpositive/default or invalid values yield U; bad same-record binding yields FAILED. Source: `hybridguard_agent/research/mtc_resource_relations.py`.

Native–App timezone: compare Web UTC-minus-local minutes to the negative effective IANA offset derived from Native zone ID over device acquisition start/end times using fixed tzdb2026c. The Native rawOffset alone is standard-time offset and not always the current offset. No comparison of zone-ID text; aliases/same-offset names are permitted. Ambiguous offset-transition interval, unreliable date for dynamic zones or invalid evidence yields U; documented fixed-offset historical domain can work without a date. Never substitute current time/upload time. Source: `hybridguard_agent/research/mtc_timezone_relation.py`, `deliverables/timezone_relation_validation_v1/{REPORT.md,SEMANTICS.md}`.

Standalone Host geometry: P_axis=visualViewport CSS size×DPR×visualViewport.scale; H_axis=Host View size−its padding. Alarm if either axis satisfies P>H+epsilon, with epsilon=2+4×2^-23×max(|P|,|H|,1) pixels. Fixed tolerance, no fitting. Independent Host-before/Web/Host-after binding/stability checks; not an atomic sample. Current established domain requires zero padding, visible/attached View and identity transform. Host/Web agreement does not determine stability, so stable contradictions remain T. This check is not in Full App. Source: `hybridguard_agent/research/screen_geometry_relations.py`; `deliverables/screen_geometry_observation_v1/REPORT.md`.

## Exact frozen C1 policy: do not silently change this in prose

C1 (`cross-web-offset-v1`) compares:

    app.web_data.execution_layer.timezone_offset
      != browser.web_data.execution_layer.timezone_offset

Both operands use the same Web convention: UTC-minus-local minutes. Both must be present, non-null, status=`observed`, quality=`observed_value`, and finite int/float (bool and numeric strings are not accepted). Values0 and−1 are legitimate, not sentinels. Numeric equality treats int/float equal values alike. The frozen implementation does not impose an offset range, timestamp proximity, time-alignment or DST-transition gate. Times are diagnostics only. Therefore it is wrong to claim C1 checks a synchronized pair or turns a large timestamp gap into U.

- Pair source/binding/structural errors → FAILED.
- Missing, non-observed, unavailable-quality, null, nonnumeric or nonfinite operand → U.
- Valid unequal numbers → T; valid equal numbers → F.
- The existing saved contract is frozen; writing the manuscript does not authorize adding a temporal gate, changing normalization, imputing Browser values or relabeling old outputs.

This is distinct from the date-aware Native–App timezone reference above. A reported timestamp difference of2,833,629 seconds was preserved in prior review; it was not verified as a true acquisition interval and did not change the C1 state. Temporal changes and settings/DST differences remain limitations, not erased observations.

Sources: `deliverables/browser67_cross_endpoint_diagnostic_v1/{conditions.py,CANDIDATES_FROZEN.json,review_20261006/REVIEW_REPORT.md}`, `hybridguard_agent/research/mtc_p3_candidates.py` (`P3-X-TIMEZONE-OFFSET`, `_semantic_equal`, `evaluate_candidate`).

The accepted paired model uses frozen App OR C1. If C1 is U and App is F, output is U; if App is T and C1 is U, output is T. Any selected FAILED causes FAILED, including AppT+C1FAILED. No dynamic fallback treats missing Browser input as normal. The App-only model can still be evaluated separately when its own record is valid. Sources: `deliverables/cross_endpoint_constrained_extension_v1/{selector.py,inference.py,PROTOCOL.md}`.

## C1/C2 extension selection and normal counterexamples

For each frozen App model, enumerate no extension, C1, C2, C1+C2. Development members are MTC630 + pilot18 + matched42, i.e.676 normal +14 effective interventions. Separate normal alarm budgets are31/630,0/12,1/34, with at least90% defined outputs for each normal group and90% MTC candidate evaluability. Total capacity remains8 clauses/complexity16. Among feasible sets maximize the mean of four family detection fractions (App language/timezone and Browser language/timezone), then fewer added rules, then fixed set order.

C1 is selected in all three configurations. It has610/630 defined training outputs; App51U and C1 20U overlap in8 records, yielding63U and567/630=90% combined coverage. C2 causes two normal Browser language-preference changes to alarm:2/34 exceeds1. C1+C2 has566/630 defined (<90%) and the same normal-budget failure. Historical144/117 enter only after selection freeze, while retaining prior-use disclosure. Sources: `deliverables/cross_endpoint_constrained_extension_v1/{selector.py,PROTOCOL.md,REPORT.md}`.

## Small-tree reference

Saved sklearn1.7.2 settings: gini/best, max_depth3, min_samples_leaf2, random_state20261006, class_weight=None; positive probability≥0.5. Inputs are all admitted same-fold candidate atoms,63/63/54, each encoded into fixed disjoint T/F/U indicators, not just the final selected rules. Training uses controlled252 + MTC630. Attack weights total1/2, equally allocated by configuration; controlled normal and MTC normal each total1/4. There are three delivered trees and one separately retained failed export engineering fit; do not claim only three fit calls. No identifiers, Browser fields or future restoration features enter. Source: `deliverables/app177_core_ablation_v1/{tree.py,SETTINGS.json,REPORT.md}`.

## Ethics statement evidence boundary

The source manifest currently declares only INTERNET and ACCESS_NETWORK_STATE. MTC instructions describe collection without account login, camera/microphone/location/contact/photo permissions, blanket browser grants, target fingerprint modifications or attack tools. Local intervention reports describe self-owned emulator instances and restored settings. These support a factual description of the collection design. They do not establish an IRB determination or participant consent. None was located in the relevant audited documentation; the final author must verify any such claim before submission. Raw payloads, stable identifiers, credentials and provider operational details are not required in the paper package. Sources: `android_app/HybridGuard/featureapp/src/main/AndroidManifest.xml`, `deliverables/mtc_20260916/百度MTC云真机采集需求说明.md`, `deliverables/mtc_cap8_replay_v1/DATA_NOTES.md`.
