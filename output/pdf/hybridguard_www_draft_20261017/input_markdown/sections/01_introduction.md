# 1 Introduction

Web security decisions often depend on client reports about the execution environment. Browser-visible properties can help recognize returning clients or augment authentication [1,2], but a plausible value can still be fabricated. Targeted browser spoofing shows that an adversary can imitate fingerprint attributes through browser modifications [3]. Assessing report integrity therefore requires evidence beyond the plausibility of individual values.

Android hybrid applications offer complementary observations of the same execution. JavaScript runs inside a WebView whose host and underlying Android environment expose partially overlapping information [11]. A Web memory report may fit a global range yet exceed a device-specific envelope. A legitimate timezone change may move system and Web offsets together. Resizing the container may change webpage geometry without any report manipulation. These examples motivate interpreting Web reports against the context in which they were collected.

Consistency checking is established in fingerprinting research [4,6,7]. We ask a more specific question: **when do Native and Host references help distinguish a modified Web report from legitimate environmental variation, and what alarm and availability costs follow?** These references have their own timing, availability, and semantic limits. Their value depends on whether the relevant relationship can be assessed for the current observation.

HybridGuard associates Native, WebView Host, and App Web observations with an execution and evaluates semantic checks under explicit applicability conditions. It constructs compact detectors subject to constraints on normal alarms and definite-output coverage. The Integrated App detector combines within-view conditions with Native–Web memory and timezone relations. We evaluate Host geometry separately. An optional linked Browser, running in a separate execution context, adds an App–Browser timezone comparison.

In a controlled benchmark of 126 effective modifications and 252 normal record positions, Integrated App detects 105 modifications and a separately refitted Web-only detector detects 96; neither raises a controlled-normal alarm. A refitted no-memory alternative also detects 96, with all nine differences confined to the CPU-plus-memory recipe. Historical normal records reveal costs that this controlled benchmark misses: relaxing the normal-alarm constraint adds three detections but raises alarms on every historical evaluation record. The Browser extension similarly adds targeted detections while increasing unknown outcomes.

We make three contributions:

**Conditional evidence semantics.** An observation and decision model associates complementary Android measurements with an execution and distinguishes predicate violations, definite non-violations, unavailable evidence, and execution or association failures.

**Mechanism evidence.** Exploratory fixed-check comparisons examine how device-specific memory bounds, timezone co-change, and Host container context distinguish the tested report edits from legitimate variation. Native memory and timezone are integrated into the App detector; Host geometry remains a standalone study.

**Alarm and availability analysis.** Refitted detector alternatives and a linked-Browser extension quantify modification coverage alongside normal alarms and definite outputs. Together, these experiments characterize contextual evidence for report integrity within the studied settings.
