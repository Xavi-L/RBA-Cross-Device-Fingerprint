# 6 Discussion and Limitations

## 6.1 Conditional Evidence and Evasion

Native and Host observations share the execution environment, so their value as references depends on which observations an adversary can alter independently. Preserving a selected constraint may require control of only one report: a memory edit that remains within the Native-derived envelope can already evade that check. The experiments characterize responses to the tested edits; resistance to adaptive or coordinated evasion and its implications for attacker effort require further evaluation.

## 6.2 Generality and Development Exposure

Controlled evidence covers correlated repetitions of 14 recipes on three emulators, rather than independent physical-device samples. Prior development exposure in both historical cohorts makes the reserved cohort retrospective. Refitted ablations and the fixed-capacity tree support conclusions only for the tested methods and settings.

Development diagnostics show further limits. A relation-augmented tree fits the paired material well but does not retain that benefit across both batch-level development checks. Resource extensions improve some detections but fail the admission constraints. Appendix A and the supplemental tables report these outcomes separately from the retained detector results.

## 6.3 Availability, Drift, and Integration

Evidence availability shapes candidate admission and current-record decisions. Changes in APIs, WebView providers, timing, locale, or containers can affect relation applicability. The benchmark includes U outcomes and zero FAILED or EMPTY_MODEL occurrences. Deployment studies should evaluate longitudinal robustness and transfer to physical devices, estimate execution failures, rejected associations, and empty selections, and assess response policies. These policies must distinguish unresolved evidence (U) from execution or association failures (FAILED), treating both as non-definitive outcomes.

Host geometry currently applies to zero-padding, identity-transform views. Integration into model construction requires joint evaluation of detection, alarms, availability, and complexity across window modes, keyboard interactions, and physical devices. Cached-evaluation timings exclude collection and communication; end-to-end costs require measurement.

## 6.4 Data Collection and Privacy

Environment observations collected for integrity checking may also enable tracking [9,12,18]. Controlled modifications use emulators; historical MTC records come from cloud-device collection. The MTC collector requests network access and network-state observation, excluding contacts, messages, photos, location, camera, and microphone. The public release uses random record identifiers and suppresses identifying strings, high-entropy values, and precise timestamps while separating privacy suppression from collection missingness. Retained fingerprint attributes and grouping can enable cross-record linkage.

Deployments should minimize retained observations, define responses to uncertain evidence, and measure effects on authentication, account takeover, and fraud.
