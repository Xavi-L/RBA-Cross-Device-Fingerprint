# F05a single-column candidate

## English

Full App and App + C1 (accepted cross-endpoint timezone check) on 60 saved development positions: 14 interventions, 46 normal. Points show detection rates with T/N labels. C1 adds Browser timezone detection; language edits remain undetected. Three frozen configurations share counts without pooling denominators. Both methods have 0/46 normal alarms. This is not a new blind test; broader normal costs are reported separately.

## 中文

比较 Full App 与 App + C1（已接受的跨端时区检查）：使用已有开发材料中的 60 个配对评价位置，包括 14 个修改位置与 46 个正常位置。点表示检出率，标注为 T/N。C1 新增 Browser 时区检出，两类语言修改仍未检出。三个冻结配置分别得到相同汇总计数，图中压缩展示但不合并分母。两方法正常报警均为 0/46。这不是新盲测；广机型正常记录代价另行报告。

## Interpretation and scope

- Full App is `APP_FULL`, the complete App method with Native-App Web references and no independent Browser input. App + C1 is `PAIRED_BASE`: Full App plus the accepted cross-endpoint timezone check. It is not Browser-only, a resource extension, C1+C2, a four-view tree, automatic fallback or dynamic selection.
- Only `pilot18` and `b2b42` are included: 18 + 42 = 60 saved evaluation positions, not 60 independent devices. `resource54` is excluded. App and Browser are different observation points on the same device.
- In the fixed order App language, App timezone, Browser language, Browser timezone, Full App detects 0/2, 2/2, 0/5, 0/5; App + C1 detects 0/2, 2/2, 0/5, 5/5. The five additional Browser-timezone detections comprise three pilot and two matched-control positions. The two existing App-timezone detections are retained.
- Intervention totals are 2/14 and 7/14, checked only for this batch. They are not added to or directly compared with F01's separate 105/126 denominator.
- Each method has T/F/U/FAILED = 0/46/0/0 on the shown normal records. U and FAILED are also zero on the shown interventions. These statements apply only to this small batch; they do not establish generally zero normal alarms or complete output coverage.
- All 30 source rows and their three configuration identities are retained. Equal N/T/F/U/FAILED/defined aggregates permit common counts to be displayed, without turning 5/5 into 15/15 or 60 positions into 180 independent samples. No record-level equality, independent repetitions, error bars or statistical significance is claimed.
- The results support the observed Browser-timezone increment and retention of the App-timezone result. They do not establish detection of arbitrary changes, all fields, all endpoint directions, unseen devices or modification tools. Both language families remain undetected. These materials had development contact and are not a new blind evaluation.
- The normal result stays in the formal caption, separate from the detection axis, to preserve the single-column height budget. Broader normal-record alarms and unknown-output costs remain separate evidence.
- Source locators use file paths, one-based line numbers, configuration/model IDs and aggregate counts. No raw fingerprints, session IDs, receipts or source-local member identifiers are exported. C1 is not recomputed.
- `F05a` remains a material ID, not a final paper figure number. The integration label is `fig:paired-timezone-gain`.
