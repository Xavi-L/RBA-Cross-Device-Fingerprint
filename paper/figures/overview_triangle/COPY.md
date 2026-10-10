# Overview 最终文案清单

基线：`3443c16d8cd65e3575e84accce93bcb45a340cbc`，已完成图标、局部配色与细边框修订的版本。2026-10-10 本轮重构研究叙述；保留图标、浅色配色和三角主体，画布仍为180 × 106 mm。

以下为生成脚本使用的最终英文文案。换行仅服务于排版；正式中英文图注和实现限定见 README。

## A. 检测什么

- **HybridGuard: Detecting device-fingerprint manipulation**
- Manipulated reports may conflict across observation points.

指设备指纹报告的可能操纵；不声称所有修改都会产生矛盾。

## B. 从哪里观察，是否为同一设备

- 总边界：**One device, multiple observation points**
- App 分组：**Inside the app**
- Native：**Device & OS** / (Native) / Memory and timezone
- Host：**App container** / (WebView Host) / Container settings
- App Web：**Embedded webpage** / (App Web) / Reported properties
- Browser：**Standalone browser** / On the same device / Separate web runtime

前三者保留三角位置。Browser 在 App 外、同一设备边界内；例子和 Offline 均在设备边界外。字段目录计数移至 README。

## C. 为什么比较可能帮助检测

- 中央：**Cross-check** / reported properties
- Native—App Web：**System–web consistency** / Memory and timezone
- Native—Host：**Shared context** / No detection rule
- Host—App Web：**Container–web geometry** / Not in current detector
- App Web—Browser：**App–browser consistency** / Timezone reports

前后两条已选关系为蓝色实线比较边；几何为赭色虚线比较边；上下文为无箭头灰色点线。比较是测量语义允许的相容关系，不是所有字段逐项相等，也不表示可信真值。

## D. 机制例子：正常变化为何不同于局部改写

- **Example: timezone**
- **Normal system change** / System and web remain compatible
- **Web-only modification** / Reports may conflict

两个并列情形各表示自身当前观察的关系，不是时间序列、训练样本或检测器输入。正常情形是原理示意，不保证所有正常操作均相容；compatible 不等于完整检测器 No alert，conflict 不等于已确认攻击。

## E. 如何选规则，正常数据为何不可缺少

- **Select detection rules**；小标记 **Offline**
- 独立候选输入：**Candidate checks** / Within-view + cross-view
- 开发材料输入：**Development data** / Controlled modifications / Normal devices and settings
- 选择目标与约束：Improve detection / Limit false alarms / Limit undecidable cases / Keep rules simple
- 输出与模型连接标签：**Selected rules**

两个输入分别进入选择区，再输出规则。四项目标不是效果保证。没有从整个三角、例子或当前观测到离线区的箭头。具体 App 与跨端选择程序、开发与评价数据角色留在 README。

## F. 如何用于当前观测

- **Apply selected rules** / Current observations only
- 并列模式一：**App observations only** / App rules
- 并列模式二：**App + linked browser observations** / App + browser rules
- 两种模式共享输出释义，仅写一次：**Manipulation alert** / No alert / Insufficient evidence

两行短规则名使各输入模式与各自固定规则集对应。黑色单向线传送当前观测，紫色单向线加载已选规则；两模式不串行、不自动回退。输出汇合只共用结果词汇，不融合两次检测结果。编码、缺测和执行失败合同留在 README。

## G. 如何评价研究方法

- **Research evaluation**
- Detection · False alarms · Undecidable cases · Ablations

底部条带无流程箭头，表示研究评价范围，不是每次推理后的生产步骤，也不产生在线反馈。

## 文字与视觉权重

只将 Cross-check、例子中的 conflict、Manipulation alert 标为现有红色 `#D62828`。其余文字沿用深灰、蓝色关系、赭色研究关系和灰色上下文。例子与离线选择为辅助模块，三角观测与比较仍为主体。
