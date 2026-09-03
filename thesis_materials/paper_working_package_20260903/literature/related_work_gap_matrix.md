# Related Work 差异矩阵

| 工作/方向 | 主要观测边界 | 主要任务 | 与 HybridGuard 的直接联系 | 不能混淆的差异 |
|---|---|---|---|---|
| Browser Fingerprinting: A Survey | 浏览器暴露属性 | 指纹技术分类、隐私和开放问题 | 提供字段和研究背景 | 不提出 Android 跨层完整性框架 |
| Device Fingerprinting for Augmenting Web Authentication | Web 设备指纹与认证 | 分类指纹方法及其认证用途 | 支撑指纹作为补充认证上下文 | 不验证受控 Android 环境操纵 |
| Mobile Device Fingerprinting Considered Harmful for RBA | 移动设备指纹 | 指纹稳定性与区分性限制 | 提醒避免把单一指纹当作强身份凭证 | HybridGuard 也尚未证明彻底解决稳定性问题 |
| Gummy Browsers | 浏览器内部属性 | 目标化浏览器指纹 spoofing | 支撑威胁模型中的多字段伪造能力 | 不使用 Android Native/WebView 宿主互证 |
| Fp-Scanner | 浏览器内部关系 | 检测反指纹修改造成的不一致 | 证明显式关系可暴露局部修改 | HybridGuard 不是首个 inconsistency detector |
| FP-Inconsistent | 浏览器请求的空间/时间指纹 | 测量规避型 bot 的不一致 | 最接近当前“操纵破坏关系”的近期工作 | 数据、攻击者、分母和指标不能直接比较 |
| Him of Many Faces | 商业网站浏览器指纹 | 良性/对抗性指纹的大规模刻画 | 支撑浏览器指纹在风控与对抗中的现实性 | 不提供 Android Hybrid 多层来源治理 |
| (Cross-)Browser Fingerprinting | 浏览器、OS、硬件 | 跨浏览器设备识别 | 支撑 OS/硬件与 Web 字段存在联系 | 目标是识别，不是完整性违规检测 |
| BrowserFM | 浏览器配置、系统、硬件和指纹 | 显式 feature-model 分析 | 支撑关系和配置约束显式化 | 不含 receipt/pair provenance 或两态攻击评价 |
| FP-Fed / FP-tracer / FP-Radar | 指纹脚本/API 行为 | 检测网站是否实施指纹采集 | 用于区分 task family | 不是检测被采集环境是否被操纵 |
| A Large Scale Analysis of Android--Web Hybridization | Android 应用与 WebView | 测量 Hybrid App 使用和边界 | 支撑 Hybrid 环境的现实普遍性 | 不执行运行时完整性关系 |
| BridgeTaint | Java/JavaScript bridge | 双向动态污点追踪 | 支撑 JSBridge 是真实跨语言边界 | 任务是信息流，不是设备环境一致性 |
| Demand-Driven WebView Analysis | Java 与 JavaScript source/sink | 面向需求的信息流分析 | 说明单语言分析不足 | 不使用固定设备指纹合同 |
| Tracking Without Borders | App、WebView、Web tracking | 测量 WebView 如何桥接移动和 Web 跟踪 | 支撑多层联合观测必要性 | 目标是 tracking，而非受控 manipulation |
| Cross-Boundary Mobile Tracking / WebViewTracer | Java 调用与 WebView JavaScript | 联合动态分析信息扩散 | 证明跨边界运行时联合观测可行 | 不提供跨层指纹 relation/pair evaluation |
| Bridges to Self | Web 与本地 App 上下文 | localhost 形成的 Web-to-App tracking | 与未来 External Browser 轨道相关 | 不等于 Browser67 已有检测增量 |
| HybridGuard | Android Native、WebView Host、App Web Runtime；可选 External Browser | 来源可追溯的跨层环境一致性与受控操纵分析 | 组合固定合同、状态语义、provenance、分源关系和两态 pair | 当前正式攻击结果仍只覆盖 App177；Browser67 增量待验证 |

## 推荐的 Related Work 组织

1. **Fingerprints as authentication and risk signals**：一篇正面分类工作加一篇限制性工作。
2. **Fingerprint spoofing and inconsistency detection**：Gummy Browsers、Fp-Scanner、FP-Inconsistent、BrowserFM。
3. **Detecting fingerprinting activity versus detecting manipulated environments**：用 FP-Fed、FP-tracer 等划分任务。
4. **Android WebView and cross-language analysis**：BridgeTaint、Demand-Driven Analysis、Tracking Without Borders、WebViewTracer。
5. **Positioning HybridGuard**：明确组合贡献和当前 Browser67 边界。

## 审稿人可能提出的问题

### “这不就是 Fp-Scanner/FP-Inconsistent 吗？”

回答重点：既有工作主要分析浏览器指纹内部关系；HybridGuard 的对象是 provenance-bound Android Native/WebView Host/App Web Runtime，关系同时具有字段状态、适用条件、合法容错、来源类别和受控 pair。

### “这不就是 WebView taint tracking 吗？”

回答重点：BridgeTaint/WebViewTracer 追踪程序信息流；HybridGuard 分析运行时环境表示的一致性，不恢复通用 source-to-sink flow。

### “为什么需要 Browser67？”

回答重点：External Browser 是新的容器和可见性来源，但也引入合法跨容器差异。当前只主张实现 paired-data path；增量价值和误报代价需要未来对照实验。

### “51/69 是不是 recall？”

回答重点：不是。它是冻结受控配置上 qualified pairs 的 relation transition count，缺少足够独立设备、正式负样本和预注册 held-out evaluation。

### “官方知识为什么能报警？”

回答重点：官方文档只定义字段语义；报警 predicate 是项目显式推导，必须称为 official-derived semantic relation，而不是官方 verdict。
