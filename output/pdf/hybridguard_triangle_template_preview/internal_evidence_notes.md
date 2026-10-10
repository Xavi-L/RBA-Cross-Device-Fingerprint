# Internal Evidence Notes for the ACM Draft

## Current facts used in the draft

- App177 = 84 Android Native + 26 WebView host + 67 in-app Web signals.
- Browser67 = independent system-browser Web probe with 67 signals.
- paired244 = provenance-complete derived App177 + Browser67 view.
- Latest development/QC snapshot: 26 accepted App177; 17 paired244; 9 App-only; unlabeled.
- Current controlled set: 229 normal App177 observations; 23 accepted manifests; 69 qualified baseline-active pairs; 4 tool families; 14 exact configuration IDs.
- Current official-derived set: 9 executable relations; 51 baseline-no-alert to active-alert transitions.
- Current device-mined set: 10 executable predicates; 33 transitions.
- Pair overlap: 33 both sources; 18 official-derived only; 0 device-mined only; 18 neither.
- Current uncovered configuration groups: WebDriver-only, resource pair, languages-only, plugins/MIME, timezone-only, screen-metrics-only.
- Historical grouped CV: tri-layer semantic 7 features, MAE 2.281, RMSE 3.358; raw all, MAE 2.642, RMSE 4.455.
- Historical GLM targeted pilot: knowledge-off MAE 2.367 / RMSE 3.291; knowledge-on MAE 2.750 / RMSE 4.649; no evidence of aggregate numerical gain.

## Mandatory phrasing rules

- Do not call 51/69 recall.
- Do not claim zero FPR.
- Do not say current decisions use 244 fields.
- Do not infer an attack from Browser disagreement.
- Do not attribute project-derived rules to Android/Chrome as official verdicts.
- Do not merge current controlled and historical teacher-label metrics.
- Do not use clean_post in the paper protocol.
