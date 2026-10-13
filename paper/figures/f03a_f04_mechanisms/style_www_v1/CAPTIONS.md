# F03a/F04 combined candidate

## English

Saved Native-App Web reference evaluations for memory (a) and timezone (b). Positions show alarm rates; labels show T/N. Intervention alarms indicate detection (higher preferred); normal alarms indicate false alarms (lower preferred). Memory: 18 effective interventions, 48 normal controls; six separate no-change operations yield 0/6 alarms for every method. Timezone: six App Web interventions and six normal system changes; the latter belong to 30 normal records. Counts hold separately for all three frozen configurations. Equal aggregates are displayed without pooling denominators. These development materials are not a new blind test. Broader normal-record costs are reported separately; specialist zeros do not establish generally low false alarms.

## 中文

基于保存结果展示 Native-App Web 参照在内存 (a) 和时区 (b) 专项中的表现。点的位置表示报警率，文字为 T/N。修改记录的报警表示检出，越高越好；正常记录的报警表示误报，越低越好。内存专项包含 18 次有效修改、48 条正常对照，另有 6 次无可观测变化的操作，各方法均为 0/6 报警。时区专项包含 6 次 App Web 单独修改和 6 次正常系统换区；后者属于全部 30 条正常记录的子集。三个冻结配置分别得到相同汇总计数，图中压缩展示而不合并分母。这批开发材料不是新盲测。广机型正常记录上的代价另报，本专项的零报警不说明一般误报率很低。

## Interpretation and scope

- This figure reads saved complete-model outputs and previously retrained ablations from F03a/F04. It does not use the two fixed conditions in F03b. Rule methods use RETENTION; Small App tree uses FITTED.
- Method IDs and order match the accepted F01. No MTC alarm cap does not remove MTC entirely. App Web only is not standalone Browser; Small App tree is not a four-view model. Full App excludes standalone-browser C1, new Host geometry and resource enhancements.
- All three configurations (WEBGL1-LOEO-v1-01/02/03) remain in `data/`. Compression requires equal N/T/F/U/FAILED/EMPTY_MODEL/defined counts. It does not establish identical record-level predictions, independent repetitions, confidence intervals or significance.
- The memory evidence covers the tested upward modifications. It does not establish detection of downward, within-envelope, coordinated or arbitrary memory changes. The six operations with no observable change are neither additional attacks nor part of the 48 normal controls.
- Timezone normal changes are exactly the two L_ scenarios at phase=change and identity=NORMAL. App Web interventions are exactly the two A_ scenarios at phase=change and identity=EFFECTIVE_INTERVENTION. ALL records are checked separately, never added to their constituent scenario rows.
- The shown groups have U=FAILED=EMPTY_MODEL=0. This does not remove Full App's unknown-output cost on historical MTC normal records. No MTC alarm cap matching Full App in these two small specialist batches does not establish comparable usefulness on broader normal records.
- Small App tree has zero alarms on both normal groups and also zero detection on both intervention groups. Its normal-side zeros must be read with its detection losses.
- Sources remain F03a/F04, not a newly numbered paper figure. The separate integration label is `fig:app-reference-mechanisms`.
