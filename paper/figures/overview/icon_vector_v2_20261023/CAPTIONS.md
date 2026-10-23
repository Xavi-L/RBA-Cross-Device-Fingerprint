# Figure 1 captions and alternative text

## English caption

**Three complementary views of one Android app execution.** Native APIs expose device and OS properties, JavaScript exposes observations from the embedded webpage, and the WebView host exposes its containing view. The solid blue comparison denotes Native-Web memory-bound and effective-timezone relations used by the current detector. The dashed amber comparison denotes Host-Web geometry implemented and evaluated in a separate study, outside the current Full App detector and its candidate pool. The dotted gray connection denotes shared context, not an independent detection rule. Arrowheads indicate comparisons, not communication paths or mutual authentication. Association within one app execution does not imply atomic sampling, and no surface is trusted ground truth. Single-view checks, the optional linked Browser, and the complete decision process appear in Figure 2. Logos and pictograms are illustrative.

## 中文图注

**同一次 Android App 执行中的三个互补观测面。** Native API 提供设备与操作系统属性，JavaScript 提供内嵌网页的观测，WebView Host 提供承载网页的宿主视图信息。蓝色实线比较表示当前检测器使用的 Native-Web 内存上界与有效时区偏移关系；金色虚线比较表示已实现并单独评估的 Host-Web 几何关系，未纳入当前 Full App 检测器及其候选池；灰色点线仅表示共享上下文，不构成独立检测规则。箭头表示比较关系，不表示通信路径或相互认证。同一次 App 执行中的关联不意味着原子同步采样，任何观测面都不是可信真值。单视图检查、可选的关联 Browser 及完整判定流程见图2。Logo 和图标均为示意。

## Alternative text

A compact triangle inside one app-execution boundary. Device and OS information is at left, the in-app webpage is at upper right, and its app container is at lower right. Thick blue open arrows connect the device and webpage, with memory-limit and timezone icons and the label Used by detector. Thin dashed amber open arrows connect the webpage and container for a separate page-size study. A gray dotted lower edge marks shared app context and explicitly says No detection rule. Layered frames distinguish the views; three colorful app logos illustrate the container.

## 编辑说明

图1保留三角概览的职责，图2解释完整系统流程。三个端点不构成对称投票环，不表示三端均已纳入检测。Memory limit 表示容许上界，而非原始数值相等；时钟等号表示适用条件下的有效时区偏移一致性。Page-size check 指网页视口与宿主 View 的关系，不是要求整张网页内容高度等于设备屏幕。品牌不代表被测 App 清单。最终排版时将 Figure 2 换为正文中的自动交叉引用。
