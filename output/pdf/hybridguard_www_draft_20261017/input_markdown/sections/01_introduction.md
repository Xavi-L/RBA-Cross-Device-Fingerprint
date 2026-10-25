# 1 Introduction

Web security decisions often depend on client reports about the execution environment. Browser-visible properties can help recognize returning clients or augment authentication [1,2], but a plausible value can still be fabricated. Targeted browser spoofing shows that an adversary can imitate fingerprint attributes through browser modifications [3]; large-scale commercial measurements also characterize adversarial browser fingerprints [16]. Assessing report integrity therefore requires evidence beyond the plausibility of individual values.


Android hybrid applications expose complementary observations across JavaScript, the WebView host, and Android [11]. A plausible Web memory report may exceed a device-specific envelope; legitimate timezone changes may move system and Web offsets together; container resizing may legitimately change webpage geometry. These cases motivate interpreting reports against their collection context.

Prior work already uses fingerprint consistency [4,6,7]. We ask: **when do Native and Host references distinguish modified Web reports from legitimate environmental variation, and at what alarm and availability cost?** A reference is useful when its semantic relationship, timing, and availability permit the comparison.

HybridGuard associates Native, WebView Host, and App Web observations with an execution and evaluates semantic checks under explicit applicability conditions. It constructs compact detectors subject to constraints on normal alarms and definite-output coverage. The Integrated App detector combines within-view conditions with Native–Web memory and timezone relations. We evaluate Host geometry separately because the original App model-construction records lack the paired Host–Web snapshots this relation requires. An optional linked Browser, running in a separate execution context, adds an App–Browser timezone comparison.

On 126 controlled modifications and 252 normal positions, Integrated App detects 105 modifications versus 96 for a separately refitted Web-only detector, with no normal alarms. Relaxing the historical-normal alarm constraint adds three detections but alarms on every historical evaluation record. The Browser extension adds targeted detections while increasing unknown outcomes.

We make three contributions:

**Conditional evidence semantics.** An observation and decision model associates complementary Android measurements with an execution and distinguishes predicate violations, definite non-violations, unavailable evidence, and execution or association failures.

**Mechanism evidence.** Exploratory fixed-check comparisons examine how device-specific memory bounds, timezone co-change, and Host container context distinguish the tested report edits from legitimate variation.

**Alarm and availability analysis.** Refitted detectors and a linked-Browser extension quantify modification coverage, normal alarms, and definite outputs.

**Code and Data Release.** To support research on cross-view consistency, we release our dataset, loading and validation scripts, and documentation at [https://anonymous.4open.science/r/cross-view-consistency-artifact-27D2/](https://anonymous.4open.science/r/cross-view-consistency-artifact-27D2/).
