# HybridGuard 文献筛选总结

筛选日期：2026-09-02 至 2026-09-03

## 1. 筛选范围

本轮合并并去重了：

- 主仓库早期候选参考文献；
- 本科论文实际引用列表；
- 第二作者攻击研究仓库中的文献登记与分析材料；
- 针对跨层指纹一致性、WebView 跨边界分析和受控指纹操纵补充检索的新工作。

共形成 85 条去重记录，并按与当前论文主线的关系分为：

| 分类 | 数量 | 使用方式 |
|---|---:|---|
| CORE | 18 | Introduction、Related Work、Threat Model 和方法定位的核心引用 |
| SUPPORT | 23 | 支撑具体背景、字段语义、任务对照或未来 Browser67 讨论 |
| HISTORICAL_ONLY | 10 | 仅用于不限篇幅草稿中的历史 RF/MLP、LLM/RAG、teacher label 和端侧内容 |
| ARCHIVE | 34 | 从投稿主引用池移除，但保留为历史资料 |

## 2. Related Work 应收敛到三条主线

### 2.1 Browser fingerprint spoofing and inconsistency

核心工作包括：

- Fp-Scanner；
- FP-Inconsistent；
- Gummy Browsers；
- Him of Many Faces；
- BrowserFM；
- (Cross-)Browser Fingerprinting via OS and Hardware Level Features；
- Browser Fingerprinting: A Survey。

这组工作证明：攻击者可以伪造浏览器指纹，而属性之间的结构性不一致可能暴露反指纹修改或规避行为。

HybridGuard 不能宣称“首次利用指纹不一致检测攻击”。更准确的差异是：前述工作主要研究浏览器指纹内部关系，HybridGuard 把 Android Native、WebView Host 和 App Web Runtime 中具有来源和状态语义的观测组织为跨层完整性关系，并在受控两态协议下执行和验证这些关系。

### 2.2 Android WebView and Java--JavaScript boundaries

核心工作包括：

- A Large Scale Analysis of Android--Web Hybridization；
- BridgeTaint；
- Demand-Driven Information Flow Analysis of WebView in Android Hybrid Apps；
- Tracking Without Borders；
- Cross-Boundary Mobile Tracking；
- Android WebView、WebSettings 和 Native Bridges 官方文档。

这些工作说明 Android 原生代码、WebView 宿主和其中执行的 JavaScript 存在广泛的跨边界信息交换，并可从信息流、漏洞或跟踪角度进行联合分析。

HybridGuard 的任务区别是：它不主要检测 Java--JavaScript 污点传播或跟踪行为，而是把宿主和运行时观测转化为可重复计算的环境一致性证据，用于分析受控操纵是否破坏预期关系。

### 2.3 Fingerprints as authentication context: value and limits

核心基础文献：

- Device Fingerprinting for Augmenting Web Authentication；
- Mobile Device Fingerprinting Considered Harmful for Risk-Based Authentication；
- RBA survey 和 applied-in-the-wild study。

建议形成正反结合的叙事：设备指纹能够为口令之外的认证提供低摩擦上下文，但单一移动设备指纹存在相似性、稳定性和歧义问题。因此，HybridGuard 不把单字段值直接视为身份或攻击结论，而是强调多层互证、字段状态、来源审计、合法容错和不可判定状态。

## 3. 与当前任务不同但可用于对照的工作

以下论文解决的是“检测网页或 App 是否实施指纹采集”，而不是“判断被观测环境是否被操纵或跨层不一致”：

- FP-Fed；
- FP-tracer；
- FP-Radar；
- Haven't We Met Before? Detecting Device Fingerprinting Activity on Android Apps。

它们适合在 Related Work 中用一个小节明确任务差异，不应作为完全同任务 baseline。

## 4. 历史章节可暂时保留的文献

- LLM in Cybersecurity systematic review；
- Retrieval-Augmented Generation survey；
- JavaScript 漏洞检测中的 LLM 可靠性预印本；
- RLAuth；
- ShadowNet；
- TinyML survey；
- FSSDroid。

这些引用只服务于历史/预验证章节。若对应章节在正式稿中删除，相关引用也应删除。

## 5. 从主稿引用池移除的方向

以下研究与当前跨层环境一致性主线距离较远，默认不进入投稿正文：

- 肌肉震颤、触摸、按键动态等行为生物特征；
- 通用 Android malware 分类和特征选择；
- Deep Link、TLS 和证书校验；
- 通用端侧 CNN、NAS 和内存调度；
- 与现有字段和攻击场景关系弱的音频、RF 或其他单一侧信道指纹。

## 6. 元数据修正重点

- FP-Inconsistent 使用正式 IMC 2025 版本，而不是旧预印本记录；
- Fp-Scanner 使用 USENIX Security 2018 正式条目，不使用错误 ACM DOI；
- 2026 年 WebViewTracer/Cross-Boundary Mobile Tracking 使用正式 NDSS 页面；
- 动态官方文档需要在正式投稿前重新核对发布日期和访问日期；
- 预印本必须显式标记为 preprint，不能写成同行评审正式结果。

## 7. 引用纪律

- 核心主张优先引用正式会议、期刊和官方文档；
- 不从论文标题推断方法细节；
- 对只完成摘要或 artifact 复核的工作，不复述未经确认的实验数字；
- 同一段 Related Work 应同时写清楚“它解决了什么”和“为什么仍与 HybridGuard 不同”；
- 不使用“现有工作均未……”这类难以证明的全称判断；
- 正式写作时优先从 `references_curated.bib` 取 citation key。
