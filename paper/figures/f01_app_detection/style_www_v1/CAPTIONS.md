# F01 candidate caption

## English

Detection across 14 App modification configurations and six methods from saved evaluations. Cells show alarm detections T/N (N=9 per configuration); color encodes detection proportion on a shared 0-100% scale. Full App is the current App-only detector, excluding standalone-browser C1, new Host geometry, and unintegrated resource conditions. Rule methods use RETENTION outputs; the small App tree uses FITTED outputs. Normal-record costs are reported in the companion normal-results analysis; removing the MTC alarm cap must not be judged superior from this heatmap alone. These materials have a development-use history and do not constitute a new blind test.

## 中文

基于已有保存评价，展示六种方法在 14 种 App 修改配置上的检出结果。格内为报警检出数 T/N，每种修改配置 N=9；颜色统一编码 0-100% 检出比例。Full App 是当前仅使用 App 观测的检测方法，不含独立 Browser 的 C1、新 Host 几何或未接入资源条件。规则方法使用 RETENTION 输出，App 小树使用 FITTED 输出。正常记录上的代价见配套正常结果分析；不能仅凭本热图认定取消 MTC 报警上限更优。这批材料已有开发使用历史，不构成新盲测。

## Facts and sources outside the figure

- `F01_plot_data.csv` contains all 84 cells, full N/T/F/U/FAILED/EMPTY_MODEL/defined fields, source JSON pointers, source CSV row numbers, and the corresponding original F01 row. `ALIASES.json` preserves original method/configuration IDs, aliases and display orders. No rows are reordered or merged.
- Cell source: `deliverables/app177_core_ablation_v1/results/summary/configurations14.{csv,json}`, keyed by `(scheme, configuration, identity=EFFECTIVE_INTERVENTION)`. Original `paper/figures/round1_app/data/F01.csv` is cross-checked field by field. These are 14 modification configurations, not three frozen models.
- The generated `CHECK.json` reports totals computed from those cells, compared with original `T02.csv` and `main.{csv,json}`. In the fixed method order they are 105/126, 108/126, 96/126, 96/126, 105/126 and 72/126. These stated numbers are acceptance expectations, not hard-coded plotting values.
- Controlled normal records give 0/252 alarms for each method. U, FAILED and EMPTY_MODEL are zero in these saved controlled modification/normal main results. These zeros do not apply to historical MTC normal evaluation or to other experiments. F means no alarm, not proven safety.
- `all_stages.{csv,json}` verifies RETENTION for the five rule methods and FITTED for APP_TREE using `cohort=controlled, subset=heldout` and the three original fold IDs. They partition the original held-out evaluation positions; neither methods nor repeated model predictions add independent samples.
- Full App excludes independent Browser C1, new Host geometry and unintegrated resource conditions. App Web only is not Browser only. Small App tree is not a four-view tree. Ablations are previously saved complete-method results, not retraining performed for this figure.
- Companion normal-results context is the existing F02 caption and data in `paper/figures/round1_app/`; no final paper figure/table number is assigned here. Its historical MTC population differs from the 252 controlled normal records. This redraw does not regenerate F02 or make a new evaluation of normal costs.
- Webdriver and WebGL zero detections and the Full App screen count of 6/9 remain visible. Equal main totals before/after removing the timezone relation do not establish that the relation is useless; the companion normal-system-timezone analysis has a different scope.
- This is detection on modification records, not overall accuracy, a new blind test, independent generalization, evidence of malicious intent, or an SOTA result. No uncertainty intervals, significance claims, new measurements, fitting, rule selection, prediction, timing or experiment-summary entrypoint are introduced.
- The ACM preview is an isolated copy of the existing real manuscript preview. Its surrounding historical prose is retained only to check layout; this task does not validate or update that manuscript's research claims.
