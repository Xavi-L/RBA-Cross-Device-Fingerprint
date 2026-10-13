# F01 rev3 caption

## English

Saved detection results for 14 App modification configurations and six methods. Cells show T/N with N=9 per row; discrete tints distinguish 9/9, 6/9 and 0/9. Totals over the 14 configurations are reported separately. Full App excludes standalone-browser C1 and unintegrated Host/resource conditions. Removing the MTC alarm cap cannot be judged superior here; normal-record costs are reported separately. These materials have a development-use history and are not a new experiment or blind test.

## 中文

基于已有保存评价，展示 14 种 App 修改配置与六种方法的检出结果。每格为 T/N，每行 N=9；浅冷蓝、灰蓝与暖灰分别提示 9/9、6/9、0/9 三档结果。14 行合计另列。Full App 不含独立 Browser C1 与未接入的 Host／资源条件。不能仅凭此图认定取消 MTC 报警上限更优，正常记录代价另报。这批材料已有开发使用历史，不是新实验或新盲测。

## Facts and sources outside the figure

- `F01_plot_data.csv` contains all 84 cells, full N/T/F/U/FAILED/EMPTY_MODEL/defined fields, source JSON pointers, source CSV row numbers, and the corresponding original F01 row. `ALIASES.json` preserves original method/configuration IDs, aliases and display orders. No rows are reordered or merged.
- Cell source: `deliverables/app177_core_ablation_v1/results/summary/configurations14.{csv,json}`, keyed by `(scheme, configuration, identity=EFFECTIVE_INTERVENTION)`. Original `paper/figures/round1_app/data/F01.csv` is cross-checked field by field. These are 14 modification configurations, not three frozen models.
- The rev1 check, preserved in `rev1_snapshot/CHECK.json`, verified cell totals against original `T02.csv` and `main.{csv,json}`. Rev2 and rev3 only check arithmetic agreement with that saved result. In the fixed method order they are 105/126, 108/126, 96/126, 96/126, 105/126 and 72/126. The figure reads the unchanged saved cell CSV; these totals are stated separately to keep the matrix compact.
- Controlled normal records give 0/252 alarms for each method. U, FAILED and EMPTY_MODEL are zero in these saved controlled modification/normal main results. These zeros do not apply to historical MTC normal evaluation or to other experiments. F means no alarm, not proven safety.
- `all_stages.{csv,json}` verifies RETENTION for the five rule methods and FITTED for APP_TREE using `cohort=controlled, subset=heldout` and the three original fold IDs. They partition the original held-out evaluation positions; neither methods nor repeated model predictions add independent samples.
- Full App excludes independent Browser C1, new Host geometry and unintegrated resource conditions. App Web only is not Browser only. Small App tree is not a four-view tree. Ablations are previously saved complete-method results, not retraining performed for this figure.
- Companion normal-results context is the existing F02 caption and data in `paper/figures/round1_app/`; no final paper figure/table number is assigned here. Its historical MTC population differs from the 252 controlled normal records. This redraw does not regenerate F02 or make a new evaluation of normal costs.
- Webdriver and WebGL zero detections and the Full App screen count of 6/9 remain visible. Equal main totals before/after removing the timezone relation do not establish that the relation is useless; the companion normal-system-timezone analysis has a different scope.
- This is detection on modification records, not overall accuracy, a new blind test, independent generalization, evidence of malicious intent, or an SOTA result. No uncertainty intervals, significance claims, new measurements, fitting, rule selection, prediction, timing or experiment-summary entrypoint are introduced.
- The ACM preview is an isolated copy of the existing real manuscript preview. Its surrounding historical prose is retained only to check layout; this task does not validate or update that manuscript's research claims.

## Revision history

The current caption accompanies `F01_main_rev3.*`. Rev2 review documents remain verbatim in `rev2_snapshot/`; rev1 documents remain in `rev1_snapshot/`. Rev3 uses exact discrete fills: 9/9 = pale cool blue (#DDE7F2), 6/9 = pale gray-blue (#E8ECF1), and 0/9 = pale warm gray (#F3F1EE). A small three-swatch legend occupies the existing title row. All numbers use the same dark-gray ink; no continuous scale or experiment change is introduced.
