# 草稿主张与结果措辞规范

## 1. 系统定位

推荐：

> HybridGuard is a provenance-aware cross-layer fingerprint consistency framework for Android Web environments.

> The current controlled evaluation operates on App177, while Browser67 and paired244 constitute an implemented but not yet fully evaluated paired-data track.

避免：

> HybridGuard is a production-ready fraud detector.

> HybridGuard authenticates users from device fingerprints.

## 2. App177

推荐：

> App177 combines 84 Android Native signals, 26 WebView-host signals, and 67 in-app Web runtime signals under a fixed field contract.

> The present attack study deliberately evaluates App177 because sufficiently complete external-browser attack pairs are not yet available.

避免：

> App177 uniquely identifies a physical device.

> All 177 fields are independently stable or trustworthy.

## 3. Browser67 与 paired244

推荐：

> HybridGuard implements an independent Browser67 collector and derives paired244 only when App and browser payloads, receipts, a closed batch, and pair provenance can be validated.

> When browser capture is incomplete, the valid App177 record is retained in an App-only view; missing browser values are never zero-imputed.

> The incremental detection value of Browser67 remains an empirical question for a future complete paired-data study.

避免：

> The evaluated detector jointly reasons over all 244 fields.

> Browser67 improves detection accuracy.

> App-only records are incomplete 244-dimensional samples.

## 4. 两态协议

推荐：

> Each qualified controlled comparison consists of a baseline observation and an attack-active observation collected under a versioned protocol.

> Historical clean-post observations are not part of the primary evaluation denominator.

避免：

> Every manipulation was successfully reversed.

> Recovery is required for all positive labels.

## 5. 51/69 与 33/69

推荐：

> On the frozen controlled cohort, 51 of 69 qualified pairs exhibited a baseline-no-alert to active-alert transition under the official-derived relation set.

> The independently executed device-mined predicate set produced 33 such transitions on the same qualified pairs.

> These values characterize relation coverage under the tested configurations; they are not interpreted as attack recall, production accuracy, or cross-device generalization.

避免：

> HybridGuard achieves 73.9% recall.

> The official rules detect 51 attacks.

> The remaining pairs are benign or safe.

## 6. 未覆盖配置

推荐：

> Eighteen qualified pairs changed catalogued fields but triggered neither frozen relation track, revealing current coverage gaps for WebDriver-only, resource, language, plugin/MIME, timezone, and screen-metric manipulations.

避免：

> These attacks failed.

> These configurations bypass HybridGuard in general.

> The corresponding fields are useless.

## 7. 官方知识

推荐：

> Official documents define field semantics, capabilities, limitations, and legitimate differences. Cross-layer predicates derived from those semantics remain project inferences rather than official risk verdicts.

> Relations that require empirical tolerances or device-family baselines remain candidates until calibrated on grouped normal data.

避免：

> Google/Android classifies the sample as malicious.

> Official knowledge provides ground-truth risk thresholds.

> Official knowledge has already improved detection performance.

## 8. Device-mined rules

推荐：

> Device-mined predicates are empirical relations derived from project data and maintained separately from official-semantic relations.

> Their validity is limited to the frozen data, devices, versions, and configurations on which they were generated and evaluated.

避免：

> The mined rules are universal Android invariants.

> Zero explicit alerts on insufficient-evidence samples proves a zero false-positive rate.

## 9. 历史 grouped CV

推荐：

> Historical grouped-CV experiments suggest that compact tri-layer semantic features retain more teacher-score information than the complete raw feature set under the evaluated split.

> These experiments use an LLM-derived teacher risk score and do not constitute independent attack-detection validation.

避免：

> Tri-layer features generalize to unseen attacks.

> The model achieves perfect high-risk classification on real attacks.

## 10. LLM/RAG

推荐：

> The knowledge-grounded runtime is an auditable reasoning prototype that records evidence, retrieved knowledge, citations, and verification outcomes.

> In the current targeted pilot, official knowledge exposed tolerance problems and improved provenance of explanations but did not demonstrate an overall MAE/RMSE gain.

避免：

> RAG significantly improves attack detection.

> The LLM produces calibrated risk probabilities.

> The verifier guarantees factual correctness.

## 11. 摘要模板句

> Android hybrid applications expose the same execution environment through partially overlapping Native, WebView-host, and JavaScript surfaces. HybridGuard collects these surfaces under a fixed contract, preserves field-level availability states and provenance, derives explicit cross-layer relations, and evaluates them on verified baseline-to-attack-active pairs. Current results are reported as controlled relation transitions rather than attack recall. An independent external-browser data path is implemented, while its incremental detection value remains future work.

## 12. 贡献列表模板

1. A fixed-contract, provenance-aware collection and data-governance pipeline for Android Native, WebView-host, in-app Web, and optional external-browser observations.
2. An explicit evidence representation and source-separated relation model with applicability, tolerance, counterexample, and not-assessed semantics.
3. A controlled App177 evaluation that reports per-configuration relation transitions, overlaps, and uncovered field-changing manipulations without converting them into unsupported recall claims.
4. An implemented Browser67/paired244 path and a pre-specified future evaluation for measuring both its incremental visibility and its benign cross-container variability.
