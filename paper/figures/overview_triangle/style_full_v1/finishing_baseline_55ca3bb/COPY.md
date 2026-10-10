# 完整候选图文案与语义回归

内容基线为当前正式图 `../HybridGuard_overview_triangle.svg`、`../COPY.md` 和 `../README.md`；视觉基线为提交 `1b536b611690df44db3bebc4812bfab220887362` 的 `style_pilot_v1`。55 个正文文本条目完整保留，含重复出现的 Memory and timezone。图标内 JS 不计作新增正文。自动清单见 [CONTENT_MANIFEST.json](CONTENT_MANIFEST.json)，原有中英文图注见 [CAPTIONS.md](CAPTIONS.md)。

## 检测对象与同设备观察

- HybridGuard: Detecting device-fingerprint manipulation
- Manipulated reports may conflict across observation points.
- One device, multiple observation points
- Inside the app
- Device & OS / (Native) / Memory and timezone
- App container / (WebView Host) / Container settings
- Embedded webpage / (App Web) / Reported properties
- Standalone browser / On the same device / Separate web runtime

Native、Host、App Web 在 App 范围内。Browser 在 App 外、同设备框内；时区旁注与 Offline 在设备框外。任何观察点都不是真值。

## 比较关系

- Cross-check / reported properties
- System–web consistency / Memory and timezone
- Shared context / No detection rule
- Container–web geometry / Not in current detector
- App–browser consistency / Timezone reports

Native–App Web 内存/时区与 App–Browser 时区为蓝色实线比较；Host–App Web 几何为未进入当前检测器的赭色虚线比较；Native–Host 为无箭头的灰色上下文点线。比较表示相容性检查，不是所有字段相等、全属性跨浏览器验证或完整互证闭环。App 检测器仍同时采用视图内规则与选中的跨视图关系。

## 时区旁注

- Example: timezone
- Normal system change / System and web remain compatible
- Web-only modification / Reports may conflict

两组为解释性情形，没有前后时间箭头、实际 UTC 数值、样本量或检测结果。compatible 不是普遍安全保证；may conflict 不是已确认攻击。旁注不参与当前检测或规则开发流。

## 离线输入、选择操作与产物

- Offline
- Candidate checks / Within-view + cross-view
- Development data / Controlled modifications / Normal devices and settings
- Select detection rules
- Improve detection / Limit false alarms
- Limit undecidable cases / Keep rules simple
- Selected rules

两个输入独立进入选择操作；不构成 Candidate → Development 串行操作。四项为目标和约束，图中没有保证实现这些指标的标记。Selected rules 是规则产物；抽象页面和记录线没有新增规则、阈值、数据或证据。

## 当前检测、替代模式与结果

- Apply selected rules / Current observations only
- App observations only / App rules
- or
- App + linked browser observations / App + browser rules
- Manipulation alert
- No alert
- Insufficient evidence

当前观测绕过 Offline，固定规则从独立紫色端口进入共同规则应用区。两种模式为替代配置，不串行、不自动回退、不融合预测。只从共同应用区输出一条结果路径，没有结果汇合圆点；图中唯一数据汇合点用于 App 与 Browser 关联。当前预测不读阶段标签或未来恢复状态。

No alert 不改写为 Safe；缺测、Insufficient evidence 和执行失败不混同，执行失败单独记录。此处沿用正式稿的事实边界，没有重新审计模型或重跑研究实验。

## 研究评价说明

- Research evaluation
- Detection · False alarms · Undecidable cases · Ablations

评价条带无箭头，不是在线处理阶段，不返回 Offline。

## 保留的强调与字号

Cross-check、Reports may conflict 中的 conflict、Manipulation alert 保留原有红色。正文 28–29 单位，主节点名称 34、Browser 名称 32，统一衬线字体；不缩小正文、压窄文字或删减文案。
