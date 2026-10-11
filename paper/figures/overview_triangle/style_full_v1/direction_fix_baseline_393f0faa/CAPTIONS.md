# 候选图中英文图注

沿用当前正式稿的原文，两段均未改写。

## English

HybridGuard checks device-fingerprint reports for possible manipulation using complementary observations from the same device. Within-view and cross-view checks are evaluated on controlled modifications and normal operation to select compact detection rules under false-alarm and decision-coverage constraints. The selected detectors process current App observations alone or linked App–browser observations and return a manipulation alert, no alert, or insufficient evidence. The inset illustrates why changing a system setting need not have the same cross-view effect as modifying only a webpage’s report. Solid comparison edges indicate relations used in the detectors; Host–web geometry remains a separate study, and the dotted Native–Host link denotes context only. No observation point is trusted ground truth. No alert does not establish safety. Execution failures are recorded separately.

## 中文

HybridGuard 利用同一设备上的互补观测，检查设备指纹报告是否存在可能的操纵。视图内与跨视图检查在受控修改和正常运行数据上接受评估，以在误报与明确判定覆盖率约束下选出紧凑的检测规则。选出的检测器处理当前 App 观测，或已关联的 App–浏览器观测，并返回操纵报警、未报警或证据不足。插图说明，改变系统设置与仅修改网页报告，不一定产生相同的跨视图影响。实线比较边表示检测器采用的关系；Host–网页几何关系仍属单独研究，Native–Host 点线仅表示上下文。任何观察位置都不是可信真值。未报警不代表安全。执行失败单独记录。
