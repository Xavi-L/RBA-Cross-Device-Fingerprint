# 候选参考文献库（第一轮）

检索日期：2026-05-08

项目题目：基于三端融合设备指纹的移动端无感风控系统设计与实现

说明：

- 本文件是候选库，不是最终参考文献列表。
- 优先选择 2023 年及以后的正式会议、期刊、出版社页面或官方技术文档，尽量避免 arXiv。
- 少量 2022 年及以前文献保留为“经典基础文献”，用于支撑设备指纹、WebView 安全和跨浏览器指纹等基础概念。
- 后续写论文时建议保留约 30-36 篇正式引用，正文引用和文末参考文献一一对应。

## 一、推荐最终优先引用的核心文献

| 编号 | 年份 | 文献 | 来源 | 类型 | 推荐度 | 适合支撑的论文位置 |
|---:|---:|---|---|---|---|---|
| R01 | 2023 | Shujiang Wu, Pengfei Sun, Yao Zhao, Yinzhi Cao. *Him of Many Faces: Characterizing Billion-scale Adversarial and Benign Browser Fingerprints on Commercial Websites* | NDSS 2023 | 会议论文 | A | 绪论/研究现状：浏览器指纹已用于商业风控与反欺诈，攻击者会构造对抗性指纹 |
| R02 | 2023 | Iskander Sanchez-Rola et al. *Rods with Laser Beams: Understanding Browser Fingerprinting on Phishing Pages* | USENIX Security 2023 | 会议论文 | A | 绪论：指纹不仅用于追踪，也被钓鱼与账号攻击生态利用 |
| R03 | 2024 | Meenatchi S. M. S. Annamalai, Igor Bilogrevic, Emiliano De Cristofaro. *FP-Fed: Privacy-Preserving Federated Detection of Browser Fingerprinting* | NDSS 2024 | 会议论文 | A | 研究现状/隐私：浏览器指纹检测、端侧训练、隐私保护 |
| R04 | 2025 | Maxime Huyghe, Clement Quinton, Walter Rudametkin. *BrowserFM: A Feature Model-based Approach to Browser Fingerprint Analysis* | NDSS MADWeb 2025 | 会议论文 | A | 研究现状：浏览器指纹与系统/硬件配置之间的映射关系 |
| R05 | 2024 | Soumaya Boussaha et al. *FP-tracer: Fine-grained Browser Fingerprinting Detection via Taint-tracking and Entropy-based Thresholds* | Proceedings on Privacy Enhancing Technologies 2024 | 会议/期刊 | A | 研究现状：浏览器指纹检测、JS API 调用、熵和污点追踪 |
| R06 | 2024 | Kris Heid, Jens Heider. *Haven't we met before? - Detecting Device Fingerprinting Activity on Android Apps* | EICC 2024 / ACM | 会议论文 | A | 研究现状：Android App 中设备指纹活动的检测与隐私影响 |
| R07 | 2023 | Abhishek Tiwari, Jyoti Prakash, Christian Hammer. *Demand-driven Information Flow Analysis of WebView in Android Hybrid Apps* | IEEE ISSRE 2023 | 会议论文 | A | WebView/JSBridge：Hybrid App 中 Java 与 JavaScript 信息流复杂性 |
| R08 | 2023 | Maria Papaioannou et al. *A Survey on Quantitative Risk Estimation Approaches for Secure and Usable User Authentication on Smartphones* | Sensors 2023 | 综述 | A | 绪论/研究现状：移动端风险估计与安全可用认证 |
| R09 | 2023 | Claudy Picard, Samuel Pierre. *RLAuth: A Risk-Based Authentication System Using Reinforcement Learning* | IEEE Access 2023 | 期刊论文 | A | RBA 背景：风险自适应认证、动态认证决策 |
| R10 | 2024 | Ismayil Hasanov et al. *Application of Large Language Models in Cybersecurity: A Systematic Literature Review* | IEEE Access 2024 | 综述 | A | 规则知识库：LLM 在网络安全分析中的应用背景 |
| R11 | 2023 | Ruimin Sun et al. *ShadowNet: A Secure and Efficient On-device Model Inference System for Convolutional Neural Networks* | IEEE S&P 2023 | 会议论文 | A | 端侧评分：端侧模型推理的安全性、效率和隐私动机 |
| R12 | 2023 | Youssef Abadade et al. *A Comprehensive Survey on TinyML* | IEEE Access 2023 | 综述 | A | 端侧轻量模型：资源受限设备上的轻量机器学习 |

## 二、浏览器指纹、Web 指纹与 Web 侧攻击

| 编号 | 年份 | 文献 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| W01 | 2023 | *Him of Many Faces: Characterizing Billion-scale Adversarial and Benign Browser Fingerprints on Commercial Websites* | NDSS 2023 | https://www.ndss-symposium.org/ndss-paper/him-of-many-faces-characterizing-billion-scale-adversarial-and-benign-browser-fingerprints-on-commercial-websites/ | A | 真实商业网站中浏览器指纹可用于区分良性/对抗性请求，适合支撑“指纹用于风控” |
| W02 | 2023 | *Rods with Laser Beams: Understanding Browser Fingerprinting on Phishing Pages* | USENIX Security 2023 | https://www.usenix.org/conference/usenixsecurity23/presentation/sanchez-rola | A | 钓鱼页面会采集浏览器指纹，说明指纹数据也会成为攻击链条的一部分 |
| W03 | 2023 | *Pool-Party: Exploiting Browser Resource Pools for Web Tracking* | USENIX Security 2023 | https://www.usenix.org/conference/usenixsecurity23/presentation/snyder | B | 浏览器内部资源池也可产生跨站跟踪信道，说明 Web 环境暴露面复杂 |
| W04 | 2024 | *FP-Fed: Privacy-Preserving Federated Detection of Browser Fingerprinting* | NDSS 2024 | https://www.ndss-symposium.org/ndss-paper/fp-fed-privacy-preserving-federated-detection-of-browser-fingerprinting/ | A | 检测指纹脚本可在端侧完成，适合支撑端侧处理与隐私保护 |
| W05 | 2025 | *BrowserFM: A Feature Model-based Approach to Browser Fingerprint Analysis* | NDSS MADWeb 2025 | https://doi.org/10.14722/madweb.2025.23017 | A | 浏览器指纹与浏览器、系统、硬件配置存在可分析映射，适合支撑跨层语义关系 |
| W06 | 2024 | *FP-tracer: Fine-grained Browser Fingerprinting Detection via Taint-tracking and Entropy-based Thresholds* | PoPETs 2024 | https://doi.org/10.56553/popets-2024-0092 | A | 指纹脚本可以通过 API 级别污点追踪和熵阈值检测 |
| W07 | 2024 | *Harnessing Multiplicity: Granular Browser Extension Fingerprinting through User Configurations* | ACSAC 2024 | https://doi.org/10.1109/ACSAC63791.2024.00029 | B | 浏览器扩展及其配置也会扩展指纹面，可用于说明 Web 指纹来源多样 |
| W08 | 2023 | Kiu Nai Pau et al. *The Development of a Data Collection and Browser Fingerprinting System* | Sensors 2023 | https://doi.org/10.3390/s23063087 | B | 浏览器指纹采集系统实现，可为 Web 探针设计提供背景 |
| W09 | 2024 | Marko Holbl et al. *Browser Fingerprinting: Overview and Open Challenges* | Information Modelling and Knowledge Bases XXXV | https://doi.org/10.3233/FAIA231163 | B | 浏览器指纹综述，可用于研究现状开头 |
| W10 | 2022 | *DRAWN APART: A Device Identification Technique based on Remote GPU Fingerprinting* | NDSS 2022 | https://www.ndss-symposium.org/ndss-paper/auto-draft-242/ | B | WebGL/GPU 可形成远程设备识别信号，适合支撑 WebGL 特征选择 |
| W11 | 2018 | Antoine Vastel et al. *Fp-Scanner: The Privacy Implications of Browser Fingerprint Inconsistencies* | USENIX Security 2018 | https://www.usenix.org/conference/usenixsecurity18/presentation/vastel | A（经典） | “指纹不一致性”本身具有检测价值，和本文跨层一致性实验非常贴近 |
| W12 | 2017 | Yinzhi Cao, Song Li, Erik Wijmans. *(Cross-)Browser Fingerprinting via OS and Hardware Level Features* | NDSS 2017 | https://www.ndss-symposium.org/ndss2017/ndss-2017-programme/cross-browser-fingerprinting-os-and-hardware-level-features/ | B（经典） | OS/硬件层特征能跨浏览器识别设备，支撑跨层硬件语义 |

## 三、Android、移动设备指纹与传感器/物理环境

| 编号 | 年份 | 文献 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| A01 | 2024 | *Haven't we met before? - Detecting Device Fingerprinting Activity on Android Apps* | EICC 2024 / ACM | https://doi.org/10.1145/3655693.3655695 | A | Android App 中存在设备指纹活动，可通过静态/动态分析识别 |
| A02 | 2024 | Erkan Kiymik, Ali Emre Ozturk. *Gyroscope-Based Smartphone Model Identification via WaveNet and EfficientNetV2 Ensemble* | IEEE Access 2024 | https://doi.org/10.1109/ACCESS.2024.3521226 | B | 传感器数据可用于智能手机型号识别，支撑“传感器矩阵/物理环境具有设备属性” |
| A03 | 2023 | Ameya Ramadurgakar et al. *Robust Measurements for RF Fingerprinting with Constellation Patterns of Radiated Waveforms* | IEEE PAINE 2023 / NIST | https://doi.org/10.1109/PAINE58317.2023.10318021 | C | 设备可通过硬件信号形成指纹，偏硬件侧，作为扩展背景 |
| A04 | 2023 | Yi Jiang et al. *MAUTH: Continuous User Authentication Based on Subtle Intrinsic Muscular Tremors* | IEEE Transactions on Mobile Computing | https://doi.org/10.1109/TMC.2023.3243687 | B | 移动传感器可支持无感/连续认证，支撑无感风控背景 |
| A05 | 2023 | Zhihao Shen et al. *CT-Auth: Capacitive Touchscreen-Based Continuous Authentication on Smartphones* | IEEE TKDE | https://doi.org/10.1109/TKDE.2023.3277879 | B | 手机触控硬件与行为可用于隐式认证，支撑无感认证研究现状 |
| A06 | 2023 | Yantao Li et al. *Memory-Augmented Autoencoder Based Continuous Authentication on Smartphones With Conditional Transformer GANs* | IEEE TMC | https://doi.org/10.1109/TMC.2023.3290834 | B | 智能手机连续认证中的异常/用户建模 |
| A07 | 2023 | Vincenzo Gattulli et al. *Touch events and human activities for continuous authentication via smartphone* | Scientific Reports 2023 | https://www.nature.com/articles/s41598-023-36780-3 | B | 触摸事件和人体活动可作为静默认证数据源 |
| A08 | 2023 | *Continuous User Authentication on Multiple Smart Devices* | Information 2023 | https://doi.org/10.3390/info14050274 | C | 多智能设备场景中的连续认证，可作为跨设备认证背景 |

## 四、风险自适应认证与移动端风控

| 编号 | 年份 | 文献 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| RBA01 | 2023 | *A Survey on Quantitative Risk Estimation Approaches for Secure and Usable User Authentication on Smartphones* | Sensors 2023 | https://doi.org/10.3390/s23062979 | A | 定量风险估计、智能手机认证、安全与可用性权衡 |
| RBA02 | 2023 | *RLAuth: A Risk-Based Authentication System Using Reinforcement Learning* | IEEE Access 2023 | https://doi.org/10.1109/ACCESS.2023.3286376 | A | RBA 根据上下文风险动态选择认证强度 |
| RBA03 | 2023 | *Defending Against Identity Threats Using Risk-Based Authentication* | Cybernetics and Information Technologies | https://doi.org/10.2478/cait-2023-0016 | B | 身份威胁与风险评分，包含设备安全/不安全分类思路 |
| RBA04 | 2023 | *Novelty Detection for Risk-based User Authentication on Mobile Devices* | IEEE GLOBECOM proceedings | https://doi.org/10.1109/GLOBECOM48099.2022.10000843 | B | 移动端 RBA 可通过新颖性检测识别异常上下文 |
| RBA05 | 2023 | *Continuous authentication with feature-level fusion of touch gestures and keystroke dynamics to solve security and usability issues* | Computers & Security 2023 | https://doi.org/10.1016/j.cose.2023.103363 | B | 多模态融合可改善安全与可用性，和本文“三端融合”叙事有相似逻辑 |

## 五、WebView、Hybrid App 与 JSBridge 安全

| 编号 | 年份 | 文献/资料 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| H01 | 2023 | *Demand-driven Information Flow Analysis of WebView in Android Hybrid Apps* | IEEE ISSRE 2023 | https://doi.org/10.1109/ISSRE59848.2023.00020 | A | WebView 中 Java/JavaScript 双向通信语义复杂，适合作为 JSBridge 章节核心文献 |
| H02 | 2021 | *Web access monitoring mechanism via Android WebView for threat analysis* | International Journal of Information Security | https://doi.org/10.1007/s10207-020-00534-3 | B | WebView 可成为攻击面，需要监控 WebView 中的访问行为 |
| H03 | 2021 | Mohamed A. El-Zawawy, Eleonora Losiouk, Mauro Conti. *Vulnerabilities in Android webview objects: Still not the end!* | Computers & Security | https://doi.org/10.1016/j.cose.2021.102395 | A（经典） | WebView 对象、JavaScript interface 和 WebViewClient 可能引入安全问题 |
| H04 | 2020 | *A Large Scale Analysis of Android-Web Hybridization* | Journal of Systems and Software | https://doi.org/10.1016/j.jss.2020.110775 | B（经典） | 大规模分析 Android 与 Web 混合应用，支撑 Hybrid App 背景 |
| H05 | 持续更新 | *WebView - Native bridges* | Android Developers | https://developer.android.com/privacy-and-security/risks/insecure-webview-native-bridges | A（官方资料） | Android 官方说明 native bridge 的风险与缓解措施 |
| H06 | 持续更新 | *Build web apps in WebView* | Android Developers | https://developer.android.com/develop/ui/views/layout/webapps/webview | A（官方资料） | WebView、JavaScript、addJavascriptInterface 的官方用法与风险提示 |
| H07 | 持续更新 | *WebView API reference* | Android Developers | https://developer.android.com/reference/android/webkit/WebView | A（官方资料） | `addJavascriptInterface` 安全说明，可引用到实现章节 |
| H08 | 持续更新 | *Load in-app content / WebViewAssetLoader* | Android Developers | https://developer.android.com/develop/ui/views/layout/webapps/load-local-content | B（官方资料） | 本项目 `riskapp` 本地探针页面可用作实现依据 |

## 六、Android 安全、特征工程与轻量模型

| 编号 | 年份 | 文献 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| M01 | 2024 | Thomas Sutter et al. *Dynamic Security Analysis on Android: A Systematic Literature Review* | IEEE Access 2024 | https://doi.org/10.1109/ACCESS.2024.3390612 | B | Android 动态安全分析综述，支撑移动安全背景 |
| M02 | 2023 | Hiroki Inayoshi, Shohei Kakei, Shoichi Saito. *Execution Recording and Reconstruction for Detecting Information Flows in Android Apps* | IEEE Access 2023 | https://doi.org/10.1109/ACCESS.2023.3240724 | B | Android App 信息流检测，和 WebView 信息流分析形成补充 |
| M03 | 2024 | Nikolaos Polatidis et al. *FSSDroid: Feature subset selection for Android malware detection* | World Wide Web 2024 | https://doi.org/10.1007/s11280-024-01287-y | B | Android 安全任务中的特征选择，支撑本文特征消融思路 |
| M04 | 2023 | *Android malware category detection using a novel feature vector-based machine learning model* | Cybersecurity 2023 | https://doi.org/10.1186/s42400-023-00139-y | C | Android 安全检测中结构化特征向量与 ML 分类 |
| M05 | 2023 | *Feature Selection for Android Malware Detection with Random Forest on Smartphones* | Revue d'Intelligence Artificielle 2023 | https://doi.org/10.18280/ria.370405 | C | 随机森林在 Android 安全检测中的轻量应用，可作为工程选型参考 |
| M06 | 2023 | *GenDroid: A query-efficient black-box Android adversarial attack framework* | Computers & Security 2023 | https://doi.org/10.1016/j.cose.2023.103359 | B | Android 安全模型也可能遭遇对抗攻击，作为风险讨论补充 |
| M07 | 2023 | *Evaluation and classification of obfuscated Android malware through deep learning using ensemble voting mechanism* | Scientific Reports 2023 | https://www.nature.com/articles/s41598-023-30028-w | C | Android 安全检测与集成学习背景 |

## 七、端侧推理、轻量化与隐私友好计算

| 编号 | 年份 | 文献 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| E01 | 2023 | *ShadowNet: A Secure and Efficient On-device Model Inference System for Convolutional Neural Networks* | IEEE S&P 2023 | https://doi.org/10.1109/SP46215.2023.10179382 | A | 端侧推理会带来模型隐私、安全和效率问题，但具备低延迟与隐私优势 |
| E02 | 2024 | *Overlay-ML: Unioning Memory and Storage Space for On-Device AI on Mobile Devices* | Applied Sciences 2024 | https://doi.org/10.3390/app14073022 | B | 移动端 on-device ML 的资源限制与数据管理挑战 |
| E03 | 2023 | *A Comprehensive Survey on TinyML* | IEEE Access 2023 | https://doi.org/10.1109/ACCESS.2023.3294111 | A | TinyML/轻量模型在资源受限设备上运行的总体背景 |
| E04 | 2024 | *OnceNAS: Discovering efficient on-device inference neural networks for edge devices* | Information Sciences 2024 | https://doi.org/10.1016/j.ins.2024.120567 | B | 边缘设备上模型复杂度与推理效率的权衡 |
| E05 | 2024 | *Inference latency prediction for CNNs on heterogeneous mobile devices and ML frameworks* | Performance Evaluation 2024 | https://doi.org/10.1016/j.peva.2024.102429 | B | 移动设备异构性会影响推理时延，可用于系统开销讨论 |

## 八、LLM 辅助安全分析与规则知识库

| 编号 | 年份 | 文献 | 来源 | 链接/DOI | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| L01 | 2024 | *Application of Large Language Models in Cybersecurity: A Systematic Literature Review* | IEEE Access 2024 | https://doi.org/10.1109/ACCESS.2024.3505983 | A | LLM 在网络安全任务中的应用综述，适合支撑“LLM 辅助风险分析” |
| L02 | 2025 | *When Software Security Meets Large Language Models: A Survey* | IEEE/CAA Journal of Automatica Sinica | https://doi.org/10.1109/JAS.2024.124971 | B | LLM 与软件安全结合的综述，可作为扩展材料 |
| L03 | 2024 | *IRIS: LLM-Assisted Static Analysis for Detecting Security Vulnerabilities* | 论文/项目页 | https://huggingface.co/papers/2405.17238 | C（需核对正式出版） | 神经符号/LLM+静态分析思路，可作为“LLM 不直接在线决策，而辅助规则构建”的类比 |

## 九、隐私、标准与官方技术资料

| 编号 | 年份 | 文献/资料 | 来源 | 链接 | 推荐度 | 可用观点 |
|---:|---:|---|---|---|---|---|
| S01 | 2025 | *Mitigating Browser Fingerprinting in Web Specifications* | W3C Group Note | https://www.w3.org/TR/fingerprinting-guidance/ | A（官方资料） | Web 标准层面对 fingerprinting 的定义、隐私风险与缓解建议 |
| S02 | 持续更新 | *Fingerprinting* | MDN Web Docs | https://developer.mozilla.org/en-US/docs/Glossary/Fingerprinting | B（官方资料） | 浏览器指纹定义与常见字段，可用于概念解释 |
| S03 | 持续更新 | *What is User-Agent reduction?* | Google Privacy Sandbox | https://privacysandbox.google.com/protections/user-agent | B（官方资料） | UA Reduction 说明，支撑 UA 字段隐私与稳定性变化 |
| S04 | 持续更新 | *Privacy on the web* | MDN Web Docs | https://developer.mozilla.org/en-US/docs/Web/Privacy | B（官方资料） | Web 隐私、第三方 Cookie、反跟踪背景 |

## 十、建议筛选策略

### 1. 最终参考文献数量建议

建议最终保留 32-36 篇：

- 设备指纹 / 浏览器指纹：8-10 篇
- Android / WebView / Hybrid App：5-7 篇
- 风险自适应认证与移动端无感认证：5-6 篇
- 端侧推理与轻量模型：3-4 篇
- LLM 安全分析与规则辅助：2-3 篇
- 官方标准/技术资料：2-4 篇

### 2. 论文正文中的使用方式

- 绪论：优先引用 R01、R02、R08、R09，说明移动端无感风控、浏览器指纹和 RBA 的研究背景。
- 国内外研究现状：按“Web 指纹”“移动端指纹与无感认证”“WebView/Hybrid App”“端侧评分”四组展开。
- 系统设计：引用 H05-H08 支撑 WebView/JSBridge、本地 Web 探针和安全边界。
- 规则知识库：引用 W05、W11、L01，强调“特征之间的一致性/不一致性”具有分析价值。
- 实验分析：引用 W01、W11、M03，支撑对抗性指纹、跨层一致性和特征消融设计。
- 端侧评分：引用 E01、E03，说明为什么需要轻量评分器和端侧部署。

### 3. 后续需要继续做的事

- 对 A 类文献逐篇精读摘要、方法、结论，提炼可直接写入论文的 1-2 句话。
- 查每篇正式 BibTeX 或 DOI，转为 GB/T 7714 格式。
- 对低推荐度 C 类文献谨慎使用，优先作为备用材料。
- 尽量减少 MDPI 和低影响来源在最终文献中的比例，避免参考文献看起来“水分”太重。
