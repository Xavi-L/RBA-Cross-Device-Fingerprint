# 6 Discussion and Limitations

## 6.1 Conditional Evidence and Evasion

Native and Host observations share the execution environment, so their value as references depends on which observations an adversary can alter independently. Preserving a selected constraint may require control of only one report: a memory edit that remains within the Native-derived envelope can already evade that check. Our experiments characterize the detector's responses to the tested report edits; adaptive optimization, coordinated attacks, and their implications for bypass effort remain topics for further evaluation.

## 6.2 Generality and Development Exposure

Our attack evidence comprises a fixed set of manipulation recipes evaluated in three emulator environments. Repeated runs characterize outcomes within those settings and reflect correlated observations rather than independent physical-device samples. Historical normal records broaden the observed conditions; both historical cohorts have prior development exposure, so the historically reserved group is reported as a retrospective evaluation. Each ablation compares an alternative after refitting its construction stages. The shallow, fixed-capacity decision tree provides a bounded learning comparator, while Table 1 maps earlier systems by research scope; performance conclusions remain specific to the evaluated methods and settings.

Development diagnostics show further limits. A relation-augmented tree fits the paired material well but does not retain that benefit across both batch-level development checks. Resource extensions improve some detections but fail the admission constraints. Appendix A and the supplemental tables report these outcomes separately from the retained detector results.

## 6.3 Availability, Drift, and Integration

Missing evidence affects both candidate admission and current decisions. The webdriver and WebGL misses expose gaps in the selected representation, while C1 shows how adding a reference can reduce definite-output coverage. API changes, WebView providers, timing, locale conventions, and container behavior can alter a relation's applicability. Longitudinal robustness and transfer of attack results to physical devices remain unmeasured. A deployment policy must determine how to handle U and FAILED; neither state by itself establishes normality or attack.

The reported benchmark evaluations include U outcomes but no FAILED or EMPTY_MODEL outcomes. They therefore do not measure how often execution failures, rejected associations, or empty selections would occur in deployment, or how an operational policy should respond to them.

Host geometry remains a standalone mechanism study. Its current domain excludes nonzero padding and nonidentity transforms. Integrating it would require evaluating detection, alarms, availability, and complexity across window modes, keyboard interactions, and physical devices. The available cached-evaluation timings exclude collection and communication, so end-to-end runtime cost also remains open.

## 6.4 Data Collection and Privacy

Environment observations can enable tracking even when collected for integrity checking [9,12]. Our controlled manipulations use emulators, and historical normals come from cloud-device collection. The MTC collector requests network access and network-state observation, without requesting access to contacts, messages, photos, location, camera, or microphone. Limited permissions do not eliminate the privacy risks of fingerprinting.

The intended use is to assess report integrity. Deployments should minimize retained observations and validate any policy that acts on uncertain evidence. The present study does not measure authentication success, account-takeover prevention, or fraud reduction.
