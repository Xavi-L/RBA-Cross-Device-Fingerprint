# 2 Background, Prior Work, and Scope

## 2.1 Fingerprint Consistency and Contextual References

Fingerprinting research examines relationships as well as individual attributes. FP-Scanner detects countermeasure-induced inconsistencies, including discrepancies across JavaScript and HTTP reports [4]. Picasso compares canvas challenge responses against device-class expectations [5]. FP-Inconsistent studies spatial and temporal inconsistencies in evasive bot traffic [6]. BrowserFM models dependencies among fingerprints, system characteristics, and browser configurations [7]. Our study builds on this use of consistency as evidence.

WebView research examines both sides of the application–Web boundary. WVProfiler studies fingerprint exposure through Android WebView instrumentation [8]; Tracking Without Borders examines tracking across Java/Kotlin, JavaScript, and runtime behavior [9]; Cross-Boundary Mobile Tracking studies Java-to-JavaScript information diffusion [10]. Our focus is a current Web report's compatibility with associated Android device and container measurements, including relation applicability, missing evidence, and behavior under edits and legitimate changes. Table 1 maps these research scopes.

**Table 1. Research scopes of selected related studies.** The comparison pairs their examined evidence and research focus with corresponding aspects investigated in HybridGuard.

| Work | Evidence examined | Research focus | Focus of the present study |
| --- | --- | --- | --- |
| FP-Scanner [4] | Browser attributes; JavaScript/HTTP discrepancies | Countermeasure-induced inconsistencies | Associated Native and Host references |
| Picasso [5] | Canvas challenge responses | Claimed device-class checking | Current-record semantic compatibility |
| FP-Inconsistent [6] | Within-request and temporal inconsistencies | Evasive bot traffic | Controlled edits versus normal changes |
| BrowserFM [7] | Fingerprint/configuration dependencies | Configuration modeling and analysis | Applicability and evidence-availability costs |
| WebView studies [8–10] | App, JavaScript, and runtime observations | Exposure and cross-boundary tracking | Report-integrity assessment |
| HybridGuard | Native, Host, App Web; optional Browser | Contextual references under explicit domains | Detection, normal alarms, and unknown outcomes |

## 2.2 Observation Surfaces and Conditional Compatibility

Let $E$ denote the execution state and container context. An observation $x = (N(E), H(E), W(E))$ associates Native system and hardware measurements, WebView Host context, and App Web reports. The App schema has 177 catalogued fields: 84 Native, 26 Host, and 67 App Web. An optional Browser contributes 67 fields from a separate Web execution, yielding a 244-field paired schema when validly associated. Selected detectors use subsets of these fields. Association does not imply atomic sampling, and no surface is trusted ground truth.

![Figure 1. Associated observation surfaces and integration boundaries.](../figures/HybridGuard_Fig1_surfaces_v2.png)

**Figure 1.** HybridGuard observation surfaces and evaluation roles. Solid blue denotes Native–App Web memory and timezone checks incorporated into Integrated App. Dashed ochre marks Host–Web geometry evaluated separately from Integrated App candidate selection, while dotted Native–Host indicates shared context. A validly linked external Browser enables the optional C1 timezone comparison with App Web. Field counts indicate catalogued schema attributes; detectors select subsets for evaluation.

A semantic relation $C_j$ constrains observations within a stated applicability domain. A local edit may replace $W(E)$ with $W^{\prime}(E)$ while a reference stays unchanged; a legitimate change may shift related observations together. Compatibility accounts for differences in API units, precision, and abstractions. The notation $E$ describes the execution context; checks use the collected measurements.

A violation of an applicable relation provides **conditional report-integrity evidence**: the observed values conflict with the declared constraint. The evidence identifies a relational inconsistency, while attribution to an altered operand and the underlying true values remain unresolved. In evaluation, a trigger on a known effective modification counts as a detection.

## 2.3 Adversary and Claim Boundary

We use controlled browser overrides or emulation to edit resource, browser, locale, display, and graphics reports exposed to the Web application while a compared reference may remain unchanged. An operation counts as effective only when its effect is observed at the target surface. The detector receives the current observation, without operation labels, earlier baselines, or recovery records.

The intended setting is a cooperating Android application that collects Native and Host measurements alongside its embedded webpage. An ordinary remote website needs such integration to obtain these observations. Native and Host measurements are themselves mutable; being outside a local Web override does not make them administratively or statistically independent.

An alert supplies evidence of report incompatibility, not malicious intent, account takeover, or attacker identity. Conversely, no alert does not certify authenticity. An adversary may preserve the selected relations through either local or coordinated changes. We do not evaluate resistance to collector or backend compromise or adaptive evasion. Tracking and device re-identification are outside the evaluation.
