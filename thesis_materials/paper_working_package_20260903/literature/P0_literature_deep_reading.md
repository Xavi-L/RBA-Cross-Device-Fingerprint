# P0 直接近邻文献精读与定位

本文档记录对 HybridGuard 最直接的十篇近邻工作的定向复核。目标不是写通用综述，而是确认每篇论文能安全支撑什么、不能支撑什么，以及 HybridGuard 的准确差异。

## 1. FP-Scanner

**工作**：Antoine Vastel et al., *Fp-Scanner: The Privacy Implications of Browser Fingerprint Inconsistencies*, USENIX Security 2018。

**核心问题**：浏览器反指纹或隐私工具修改部分属性时，是否会产生可检测的不一致。

**方法定位**：分析浏览器指纹属性之间的逻辑关系，并用不一致识别经过修改的浏览器环境。

**可安全引用的结论**：浏览器指纹中的属性关系本身具有分析价值，局部伪造可能破坏原本协调的配置。

**与 HybridGuard 的关系**：它是“显式不一致分析”的经典直接近邻。

**关键差异**：FP-Scanner 主要在浏览器指纹内部工作；HybridGuard 把关系扩展到 Android Native、WebView Host 和 App Web Runtime，并附加字段状态、来源证明和两态实验控制。

**禁止表述**：不能说 HybridGuard 首次利用 fingerprint inconsistency。

## 2. FP-Inconsistent

**工作**：Hari Venugopalan et al., *FP-Inconsistent: Measurement and Analysis of Fingerprint Inconsistencies in Evasive Bot Traffic*, IMC 2025。

**核心问题**：规避型机器人如何修改指纹，以及空间和时间不一致能否揭示这些修改。

**方法定位**：在 honey-site 流量中观察指纹随请求和属性组合产生的不一致，并构建测量和检测分析。

**可安全引用的结论**：面向规避的浏览器指纹操纵可能留下可测量的结构性和时间性矛盾。

**与 HybridGuard 的关系**：是当前最重要的近期近邻之一，直接支撑“字段关系比孤立字段更有价值”。

**关键差异**：它关注浏览器流量和浏览器内部属性；HybridGuard 关注 Android Hybrid 应用中的跨层宿主/运行时语义，并以可追溯受控 pair 为评价单位。

**禁止表述**：不能把其商业机器人结果与 HybridGuard 的 51/69 转换计数进行直接性能比较。

## 3. Gummy Browsers

**工作**：Zengrui Liu, Prakash Shrestha, Nitesh Saxena, *Gummy Browsers: Targeted Browser Spoofing Against State-of-the-Art Fingerprinting Techniques*, ACNS 2022。

**核心问题**：攻击者能否通过定向伪造浏览器属性冒充目标指纹。

**方法定位**：展示针对指纹系统的目标化 spoofing，并分析常见字段可被修改的程度。

**可安全引用的结论**：浏览器可见属性并非天然可信；攻击者可以协调修改多个暴露面以接近目标指纹。

**与 HybridGuard 的关系**：为威胁模型中“局部或多字段浏览器侧操纵”提供依据。

**关键差异**：HybridGuard 当前不解决目标身份克隆本身，而是检查被操纵表面是否与 Android 宿主和其他层保持语义一致。

## 4. BrowserFM

**工作**：Maxime Huyghe, Clement Quinton, Walter Rudametkin, *BrowserFM: A Feature Model-Based Approach to Browser Fingerprint Analysis*, MADWeb 2025。

**核心问题**：如何显式表示浏览器配置、系统/硬件环境和最终指纹特征之间的约束。

**方法定位**：使用 feature model 表达配置关系，并分析指纹的有效性和一致性。

**可安全引用的结论**：浏览器指纹属性不是独立变量，许多字段受浏览器、系统和硬件配置共同约束。

**与 HybridGuard 的关系**：支撑“把隐含关系显式化”的方法动机。

**关键差异**：HybridGuard 的关系不仅是配置模型，还结合采集 provenance、逐字段状态、受控 baseline/active pair、知识来源和可执行 predicate。

## 5. Tracking Without Borders

**工作**：Nipuna Weerasekara et al., *Tracking Without Borders: Studying the Role of WebViews in Bridging Mobile and Web Tracking*, PoPETs 2025。

**核心问题**：WebView 如何把移动端权限、标识和 Web 跟踪能力连接起来。

**方法定位**：分析真实应用中的 WebView、JavaScript 接口、Canvas 等跟踪机制和跨环境数据流。

**可安全引用的结论**：WebView 是移动和 Web 观测面之间的重要桥梁，原生能力和 Web 运行时不能总被当作彼此独立的安全域。

**与 HybridGuard 的关系**：支撑同时观察 Native、WebView Host 和 JavaScript Runtime 的现实必要性。

**关键差异**：该工作主要研究跟踪生态；HybridGuard 研究环境完整性和受控操纵造成的跨层关系违规。

## 6. Cross-Boundary Mobile Tracking / WebViewTracer

**工作**：Sohom Datta et al., *Cross-Boundary Mobile Tracking: Exploring Java-to-JavaScript Information Diffusion in WebViews*, NDSS 2026。

**核心问题**：如何同时观察 Java 方法调用和 WebView 内部 JavaScript 执行，以刻画跨边界信息扩散。

**方法定位**：提出 WebViewTracer，并在真实 Android 应用中联合追踪 Java 与 JavaScript 行为。

**可安全引用的结论**：跨语言、跨 WebView 边界的联合动态观测是可行且必要的，单侧分析会遗漏部分行为。

**与 HybridGuard 的关系**：证明多层联合观测并非纯工程便利，而是 Android Web 安全分析的重要方法基础。

**关键差异**：WebViewTracer 关注信息扩散和 tracking；HybridGuard 关注固定合同的设备环境特征、来源审计和关系验证。

## 7. BridgeTaint

**工作**：Junyang Bai et al., *BridgeTaint: A Bi-Directional Dynamic Taint Tracking Method for JavaScript Bridges in Android Hybrid Applications*, IEEE TIFS 2019。

**核心问题**：如何跨 JavaScript bridge 双向追踪敏感数据流。

**方法定位**：动态污点追踪 Java 和 JavaScript 之间的交互。

**可安全引用的结论**：Hybrid App 中的信息和能力能够双向跨越 Java/JavaScript bridge，因此跨语言边界需要显式建模。

**与 HybridGuard 的关系**：支撑 WebView Host 和 JSBridge 作为独立观测层的合理性。

**关键差异**：HybridGuard 不执行通用污点追踪，也不把 bridge 数据流本身作为攻击标签；它使用 bridge 和宿主状态构建环境完整性证据。

## 8. iWanDroid / Demand-Driven WebView Analysis

**工作方向**：Android Hybrid App 中面向需求的跨语言信息流分析，正式相关版本包括 ISSRE 2023 的 *Demand-Driven Information Flow Analysis of WebView in Android Hybrid Apps*。

**核心问题**：如何在不分析全部程序状态的情况下，针对特定 source/sink 或安全查询连接 Java 和 JavaScript 信息流。

**可安全引用的结论**：传统单语言分析难以完整覆盖 Hybrid App 的跨语言行为，WebView 需要专门的桥接建模。

**与 HybridGuard 的关系**：共同强调跨边界语义，但分析对象和证据形态不同。

**关键差异**：iWanDroid 类工作以程序 source/sink 和漏洞为中心；HybridGuard 以运行时设备/宿主特征和一致性关系为中心。

## 9. Mobile Device Fingerprinting Considered Harmful for RBA

**工作**：Jan Spooren, Davy Preuveneers, Wouter Joosen, 2015。

**核心问题**：移动设备指纹是否足够稳定和区分性强，能够可靠用于风险认证。

**可安全引用的结论**：移动设备之间可能共享大量相同或粗粒度属性，环境变化也会降低指纹稳定性；将单一设备指纹直接视为强身份凭证存在风险。

**与 HybridGuard 的关系**：是重要的反面基础文献，提醒论文不要把“更多字段”自动等同于可靠认证。

**关键差异**：HybridGuard 尝试通过跨层关系、状态语义和来源治理减少孤立字段的歧义，但当前不能宣称已经彻底解决移动指纹稳定性问题。

## 10. Device Fingerprinting for Augmenting Web Authentication

**工作**：Furkan Alaca, Paul C. van Oorschot, ACSAC 2016。

**核心问题**：设备指纹方法如何分类，以及它们如何作为 Web 认证的附加信号。

**可安全引用的结论**：设备指纹更适合作为认证的补充上下文，而不是替代强身份凭证；方法需要在可部署性、稳定性、唯一性和抗伪造性之间权衡。

**与 HybridGuard 的关系**：支撑把环境完整性结果作为 RBA 的输入，而不是把系统描述成独立完成身份认证。

## 11. 由精读得到的新颖性边界

论文应明确承认：

- 既有工作已经研究浏览器指纹伪造和内部不一致；
- 既有工作已经对 Android WebView 的 Java/JavaScript 边界进行程序分析和测量；
- 既有工作已经讨论设备指纹对认证的价值和局限。

HybridGuard 的贡献更准确地来自这些要素的组合：

1. 在同一 Android 采集协议中区分 Native、WebView Host 和 App Web Runtime；
2. 使用固定字段合同及逐字段可用状态；
3. 用 receipt、batch、payload hash、manifest 和 pair provenance 管理来源；
4. 将关系表示为带适用条件、容错、反例和不可判定状态的可执行证据；
5. 将官方语义与经验规则分源执行；
6. 在 `baseline -> attack_active` 受控 pair 上报告冻结关系集的行为；
7. 把 External Browser 作为独立 paired-data 轨道，并暂不预设其检测增量。

推荐定位句：

> Prior work has detected inconsistencies within browser fingerprints and traced information flow across Android WebViews; HybridGuard instead studies provenance-bound semantic consistency across Android Native, the WebView host, and the in-app Web runtime under controlled two-state manipulations, while treating external-browser evidence as a separate paired-data track whose detection value remains to be evaluated.
