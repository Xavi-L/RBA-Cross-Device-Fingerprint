# HybridGuard: Cross-Layer Consistency as Integrity Evidence for Android Web Environments

Anonymous Author(s)

## Abstract

Web services use browser-visible environment reports to recognize clients and inform security decisions, yet reports can be modified without corresponding device changes. In cooperating Android hybrid applications, Native system measurements, WebView Host context, and App Web reports expose complementary views of an execution. Their semantic relationships can reveal report inconsistencies while accommodating legitimate environmental variation.

HybridGuard associates these observations, checks their semantic compatibility under explicit applicability conditions, and records unavailable evidence and execution failures separately. It constructs compact detectors subject to normal-alarm and definite-output constraints. The Integrated App detector combines within-view checks with Native–Web memory and timezone relations; Host geometry is evaluated separately. We release 1,509 de-identified App and App–Browser observations with documented schemas, label provenance, and validation scripts to support research on cross-view consistency.

Across 14 manipulation recipes on three emulator environments, Integrated App detects 105/126 effective modifications, versus 96/126 for separately refitted Web-only and no-memory alternatives; none raises an alarm on 252 controlled-normal positions. All nine detection differences occur in the CPU-plus-memory recipe. A fixed Native memory reference detects 18/18 tested upward modifications versus 6/18 for a global Web threshold, with no alarms on 48 normal positions. Separate Native-timezone and Host-geometry studies each retain 6/6 detections while avoiding six comparator alarms on legitimate changes. Historical records and a linked-Browser extension further expose alarm and evidence-availability costs. These findings support cross-layer consistency as conditional integrity evidence when a semantically related reference remains informative beyond a manipulated report.

**CCS Concepts:** Security and privacy → Web application security; Intrusion/anomaly detection and malware mitigation.

**Keywords:** Android WebView; environment report integrity; cross-layer consistency; fingerprint manipulation; semantic references.
