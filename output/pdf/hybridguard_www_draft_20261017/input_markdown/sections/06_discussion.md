# 6 Discussion and Limitations

## 6.1 Conditional Evidence and Evasion

Native and Host observations share the execution environment, so their value as references depends on which observations an adversary can alter independently. Preserving a selected constraint may require control of only one report: a memory edit that remains within the Native-derived envelope can already evade that check. The experiments characterize responses to the tested edits; resistance to adaptive or coordinated evasion and its implications for attacker effort require further evaluation.

## 6.2 Generality and Development Exposure

The controlled attack evidence covers 14 manipulation recipes across three emulator environments. Repeated runs capture correlated observations within these settings, distinct from independent physical-device samples. Historical normals widen the observed conditions, while prior development exposure in both historical cohorts makes the reserved cohort a retrospective evaluation. Ablations compare separately refitted alternatives. The shallow, fixed-capacity decision tree provides a bounded learning comparator, while Table 1 maps related studies by research scope; performance conclusions are specific to the tested methods and settings.

Development diagnostics show further limits. A relation-augmented tree fits the paired material well but does not retain that benefit across both batch-level development checks. Resource extensions improve some detections but fail the admission constraints. Appendix A and the supplemental tables report these outcomes separately from the retained detector results.

## 6.3 Availability, Drift, and Integration

Evidence availability shapes both candidate admission and current-record decisions. The missed webdriver and WebGL modifications reveal gaps in the selected representation, while C1 illustrates how an additional reference can reduce definite-output coverage. Changes in APIs, WebView providers, timing, locale conventions, or container behavior may also affect relation applicability. Longitudinal robustness and transfer of the attack results to physical devices require further evaluation. Deployment policies must handle U as unresolved evidence and FAILED as an execution or association failure, treating both as non-definitive outcomes.

The benchmark results include U outcomes, with zero occurrences of FAILED or EMPTY_MODEL. Deployment-oriented evaluation is needed to estimate the frequency of execution failures, rejected associations, and empty selections and to assess response policies for these states.

Host geometry remains a standalone mechanism study. Its current domain excludes nonzero padding and nonidentity transforms. Integrating it would require evaluating detection, alarms, availability, and complexity across window modes, keyboard interactions, and physical devices. The available cached-evaluation timings exclude collection and communication, so end-to-end runtime cost also remains open.

## 6.4 Data Collection and Privacy

Environment observations collected for integrity checking may also enable tracking [9,12]. Controlled modifications in this study use emulators, while historical normal records come from cloud-device collection. The MTC collector requests network access and network-state observation; contacts, messages, photos, location, camera, and microphone lie outside its requested permission scope. Fingerprint attributes can nevertheless remain identifying, motivating careful control of their collection and retention.

HybridGuard assesses client-report integrity. Deployments should minimize retained observations and evaluate policies for acting on uncertain evidence. Authentication success, account-takeover prevention, and fraud reduction are downstream outcomes requiring separate evaluation.
