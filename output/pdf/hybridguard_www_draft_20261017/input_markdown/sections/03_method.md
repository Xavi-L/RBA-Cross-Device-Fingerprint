# 3 HybridGuard Design

## 3.1 Collection and Association

HybridGuard preserves field values, collection states, and association context so that each comparison can be traced to the execution it describes. Source records and receipts support these binding checks. If external Browser collection is unavailable, the collector retains the App record without synthesizing Browser values. Association identifies the relevant observations; it does not imply atomic sampling or hardware attestation.

Collection context also determines applicability. For Host geometry, snapshots immediately before and after the Web snapshot establish Host stability within one collection. These are separate from the pre-intervention and post-restoration records used to evaluate the experiment. The detector uses only the current observation. Figure 2 separates this evaluation path from offline model construction.

![Figure 2. Offline construction and current-record evaluation.](../figures/HybridGuard_Fig2_pipeline_v2.png)

**Figure 2.** Constrained selection and retention produce frozen rules for current-record evaluation. The ordered decision list returns the first matching case: EMPTY_MODEL for an empty selection; FAILED for a relevant execution or binding failure; otherwise ALERT for any T, NO ALERT for all F, and UNKNOWN for the remaining cases. App-only and App-plus-Browser are two evaluated configurations. Host geometry is outside their selected checks.

## 3.2 Evidence States and Decisions

Each condition specifies its operands, source requirements, interpretation, applicability domain, and trigger. Its output is $r_j(x) \in \{\mathrm{T}, \mathrm{F}, \mathrm{U}, \mathrm{FAILED}\}$: T is an applicable, assessable trigger; F is a definite non-trigger; U indicates missing, insufficient, or inapplicable evidence; and FAILED records a relevant execution or association failure. An empty selection returns EMPTY_MODEL.

For a nonempty selection, required-input failures take precedence. Otherwise, any T produces ALERT, all F produces NO ALERT, and every remaining combination produces UNKNOWN. We record these three detector outputs as T, F, and U, respectively. A T can therefore coexist with another condition's U but cannot override FAILED. Missing unselected fields do not fail the detector. These states describe the available evidence: F does not certify authenticity, and U does not silently become a normal decision.

## 3.3 Semantic References

**Native memory envelope.** For observed, finite, positive memory measurements in GiB from the same bound App record, with $m_{\mathrm{native}} \ge 0.25$, the condition is

$$r_{\mathrm{mem}}(x)=T \iff m_{\mathrm{web}}>2^{\lceil\log_2 m_{\mathrm{native}}\rceil}.$$

Here, $m_{\mathrm{native}}$ is kernel-visible total memory reported by Android `ActivityManager.MemoryInfo.totalMem`, converted to GiB; $m_{\mathrm{web}}$ is the Web `deviceMemory` report. The Device Memory API draft describes approximate reporting with implementation-defined bounds [13]. This discontinued draft provides historical API context, not a runtime guarantee. Our power-of-two envelope is an engineering hypothesis that accommodates coarse reporting and permits lower Web exposure. It detects upward violations; within-envelope and coordinated modifications can remain compatible. Unusable operands yield U, and binding failures yield FAILED. The fixed Web-only comparator tests $m_{\mathrm{web}}>8$ GiB. For example, a Web report of 8 GiB exceeds a Native-derived 4 GiB envelope but not the global threshold. This example illustrates the predicate and adds no experimental record.

**Native timezone reference.** The Native IANA zone and collection interval determine the effective UTC offset under the fixed timezone database, 2026c. Let $o_{\mathrm{native}}(t)$ denote local-minus-UTC minutes at the applicable collection time and $o_{\mathrm{web}}$ denote Web getTimezoneOffset. The trigger is $o_{\mathrm{web}} \ne -o_{\mathrm{native}}(t)$, accounting for the Web API's UTC-minus-local convention [14]. Supported fixed-offset identifiers can be checked without a date when consistent with the observed Native standard offset. Different zone names with equal effective offsets are compatible. Missing reliable intervals for time-dependent zones, ambiguous transitions, or unusable observations yield U; database or association failures follow the failure policy. Zero and minus one are valid offsets, not missing-value sentinels.

**Host geometry reference (standalone).** The Web interface reports visual-viewport dimensions in CSS pixels and a separate scale factor [15]. For each axis, $P$ is the CSS dimension multiplied by device-pixel ratio and viewport scale; $H_{\mathrm{view}}$ is the Host View size minus its own padding. The trigger is

$$P>H_{\mathrm{view}}+\epsilon,\quad \epsilon=2+4\cdot2^{-23}\max(|P|,|H_{\mathrm{view}}|,1)\ \text{pixels}.$$

Applicability requires bound snapshots, independently assessed Host stability, finite positive dimensions and scale, an attached visible View, zero padding, and an identity View transform. Other cases yield U. Stability is assessed independently of Host–Web agreement, allowing stable contradictions to trigger. The tolerance is an engineering choice. This specialist is outside Integrated App and its candidate pool.

## 3.4 Constrained Construction and Retention

The App pool contains 50 base templates and three fixed relations: Native memory, Native timezone, and same-Web viewport. The same-Web comparator flags either visual-viewport dimension exceeding the corresponding `window.innerWidth` or `window.innerHeight` by more than 1 CSS pixel, using positive, same-probe observations when visual-viewport scale is at least one. Each template defines a condition over available fields. Training-only encoding and threshold expansion instantiate 65/65/56 atoms before admission in configurations 01/02/03. Admission checks candidate polarity and assessability. Historical evaluation records do not supply threshold quantiles. A literal selects an admitted polarity; each clause contains one literal, and the detector ORs its selected clauses using Section 3.2.

For a set $S$ of singleton clauses, the sparse stage uses

$$J(S)=\frac{1}{14}\sum_{k=1}^{14}d_k(S)-0.005\,C(S).$$

Here $k$ indexes the 14 manipulation recipes. For each recipe, $d_k$ averages whole-detector detections over the three effective modifications in each training environment, then equally across the two training environments. $C(S)$ counts clauses plus literal occurrences, so each selected literal adds two complexity units. The search uses greedy improving additions, the best feasible prefix, and backward pruning. This heuristic allows at most eight clauses, complexity 16, two conditions per registered family, and no opposite polarities of one atom.

Controlled-normal and historical training-normal alarm budgets are 8/168 and 31/630. Candidate assessability measures the fraction of records yielding T or F for that candidate; definite-output coverage measures the same fraction for the whole detector. Historical candidate assessability and final coverage must each reach 90%. Controlled coverage must reach 80% in each pre, modified, and post phase. Fits allow no execution failures and have a 60-second deadline.

Retention starts from each configuration's sparse solution. Semantic coverage counts distinct (semantic group, modified training record) trigger pairs using the training detection weights, with groups assigned from field semantics. Semantic quality sums predefined preference scores for positive literals; these scores express observation preferences, not measured accuracy or independent evidence. Additions must preserve training detections, increase semantic coverage, and satisfy the alarm and coverage constraints. Same-group swaps to registered higher-quality alternatives additionally forbid new controlled-normal alarms or lost definite controlled outputs. Retention seeks additional semantic coverage or higher semantic quality without continuing to maximize $J$. Each rule-based App configuration is evaluated using its saved retention model; stages are not selected separately for individual result cells.

## 3.5 Optional Linked Browser

Integrated App + C1 adds a timezone comparison between linked App Web and Browser records. C1 requires observed field status, observed-value quality, and finite numeric non-Boolean operands. Unequal offsets under the shared Web sign convention trigger T; missing operands yield U, and invalid association yields FAILED. C1 has no timestamp gate and does not inherit the Native relation's interval handling.

Extension selection considers no addition, C1, language condition C2, and C1+C2 on the frozen App base. Normal-alarm budgets are 31/630, 0/12, and 1/34 for historical training, pilot, and matched normals. Each normal group must retain 90% definite outputs, and historical candidate assessability must reach 90%. C2 alarms on two matched normal preference changes; C1+C2 also yields only 566/630 definite historical training outputs. We therefore retain C1 under these constraints on development-used material. It is an extension of the frozen App model, not a jointly retrained classifier or an automatic fallback.
