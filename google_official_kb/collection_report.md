# Google 官方文档收集汇总

## 目标

要求可以拆成两步：

1. 尽可能收集 Google 官方技术文档中与设备、WebView、Chrome 运行时和完整性鉴定相关的信息。
2. 把其中可用于 feature 风险鉴定的内容，整理成可审阅、可引用、可合入现有规则知识库的外挂知识库。

当前已经建立独立目录 `google_official_kb/`，并完成两批官方来源和风险知识卡片草稿。截至本次扩展，目录内包含 30 条官方来源和 20 张风险知识卡片。

## 已收集的官方来源类别

| 类别 | 官方来源 | 可支撑的风险知识 |
|---|---|---|
| Native 设备身份 | Android `Build`、`Build.VERSION` | 设备型号、厂商、硬件、ABI、系统版本、构建指纹可作为 Native 层身份基准，用于跨层一致性检查。 |
| 物理显示 | Android `DisplayMetrics` | Native 物理像素与 Web 逻辑屏幕、DPR 做软一致性校验，并保留状态栏/导航栏容错。 |
| 传感器矩阵 | Android Sensors overview、`SensorManager` | 传感器总量和核心传感器完整性可作为真实移动设备证据，极端缺失可指向模拟器或精简虚拟环境。 |
| 电池运行时 | Android `BatteryManager` | 满电、接电、温度模板值等可作为云真机/测试机架辅助线索，但必须与 ADB、manual、UTC 等组合使用。 |
| WebView 宿主 | Android `WebView`、`WebSettings` | JSBridge、WebView provider、默认 UA、settings UA 可验证 App 宿主和 Web 运行时是否来自同一链路。 |
| UA 与 Web 身份 | Chrome User-Agent Client Hints | UA 可用于 Android 版本、型号、platform、WebView token 的软匹配，但不应做严格字符串判定。 |
| 包身份与安装来源 | Android `PackageManager` | App 包名、版本、安装来源、安装时间可用于宿主真实性和测试环境判断。 |
| 开发/安全配置 | `Settings.Global`、`NetworkSecurityPolicy` | ADB、开发者选项、代理、明文流量可作为开发/测试环境辅助信号，不应单独高危。 |
| 网络环境 | Android `NetworkCapabilities` | VPN、Wi-Fi、蜂窝、带宽等仅作为运行时背景，当前不建议独立成高危规则。 |
| 官方完整性信号 | Play Integrity overview/verdicts | 后续可新增官方 app/device/request integrity verdict，作为高强度官方证据。 |
| 官方完整性请求链路 | Play Integrity standard request | request hash、integrity token、服务端解密和 verdict 校验可作为 future 防重放链路。 |
| 硬件可信证明 | Android Key Attestation、AOSP Key and ID attestation | 硬件 keystore、证书链、challenge、TEE/StrongBox 安全级别可作为 future 设备真实性证据。 |
| 启动链完整性 | AOSP Verified Boot | verified boot state、device locked 可与 build tags、su_binary_present 等当前弱线索形成未来强证据。 |
| WebView 安全风险 | WebView native bridges、unsafe file inclusion、unsafe URI loading | 支撑 JSBridge、file/content access、URI scheme/host 校验等宿主安全姿态判断。 |
| 开发/网络安全风险 | android:debuggable、cleartext communications、Network Security Config | 把 debuggable、cleartext、debug overrides 等从经验信号升级为官方安全风险依据。 |
| 自动化和移动模拟 | Chrome DevTools Device Mode、ChromeDriver capabilities | 支撑 webdriver、桌面移动模拟、UA/viewport/DPR 伪造等无头/自动化风险场景。 |
| Android 虚拟设备 | Android Emulator、AVD Manager | 支撑模拟器/AVD 背景下的 hardware、ABI、sensor、WebGL renderer 组合证据解释。 |

## 与当前规则知识库的映射

第一批卡片主要可增强以下现有规则：

| 现有规则 | 可补充的官方依据 |
|---|---|
| `CORE-001`、`CORE-002` | WebView JSBridge 官方机制、传感器矩阵官方 API。 |
| `NW-001`、`NW-002` | Android Build/Version 字段语义、Chrome UA 语义。 |
| `NW-003` | Android DisplayMetrics 与 Web DPR/viewport 的软一致性。 |
| `NW-004`、`PHYS-001` | Android ABI/hardware 字段与 Web platform/WebGL 的跨层比较。 |
| `NW-008`、`TOL-003` | Native memory 与 Web deviceMemory 的粗粒度容错。 |
| `NVW-001`、`NVW-002` | WebView/HTTP agent 与 Native 型号、系统版本的一致性。 |
| `NVW-003`、`NVW-004` | PackageManager 提供包身份和安装来源。 |
| `NVW-005`、`TOL-001` | ADB、debuggable、cleartext 只作为开发/测试辅助信号。 |
| `WVWEB-001`、`WVWEB-002`、`WVWEB-003` | WebView provider、WebSettings UA、Chrome UA 语义。 |
| `PHYS-004`、`PHYS-005`、`SCENE-001` | BatteryManager 与测试机架/云真机组合线索。 |
| `FUTURE-PLAY-001`、`FUTURE-PLAY-002` | Play Integrity 官方完整性 verdict 和标准请求链路，建议作为后续新增强证据。 |
| `FUTURE-KEY-001`、`FUTURE-BOOT-001` | Key Attestation 和 Verified Boot，可作为未来强设备真实性证据。 |
| `FUTURE-WVSEC-001` 到 `FUTURE-WVSEC-003` | WebView bridge、文件访问和 URI 加载安全风险，可作为 future WebView 安全姿态特征。 |
| `FUTURE-AUTO-001`、`SCENE-003` | Chrome 自动化、移动模拟和无头 PC 浏览器伪装风险。 |

## 当前结论

官方文档能直接支撑的不是某个固定风险分，而是字段语义和合理容错边界。更稳的表达是：

- Google 官方文档定义了 Build、WebView、WebSettings、SensorManager、BatteryManager、PackageManager、Play Integrity 等信号的语义。	
- 本项目基于这些官方语义和安全风险文档，把三端采集字段组织成跨层一致性、物理运行时、WebView 宿主安全和攻击场景证据。
- 风险阈值和分数区间仍来自本项目攻击模板、真实采集样本和已有实验，不应伪装成 Google 官方阈值。

## 本批暂缓的来源

以下内容虽然也来自 Google 或 Web 官方生态，但与当前项目字段映射较弱，暂不纳入：

- 泛泛移动安全 checklist：覆盖面太宽，难以转成具体 feature 风险卡片。
- 普通 Chrome/Android 发布说明：版本变化信息多，但对风险鉴定规则贡献不稳定。
- Google Play Install Referrer：可用于归因，但当前已有 `installer_package`，且本项目不是分发归因场景。
- WebGL/Canvas 指纹第三方资料：相关但不是 Google 官方，暂不满足导师的“官方技术文档”要求。
- 站点业务风控、广告反作弊类资料：与本项目三端设备指纹采集链路不够贴合。

## 当前合入状态

已完成主规则库合入：

- `scoring/rule_knowledge_base.json` 增加 `external_knowledge_base` 顶层元数据。
- 34 条规则增加 `official_knowledge` 字段。
- `AGG-001` 属于项目内部聚合规则，未挂接单独官方卡片。
- 详细选择/未选择理由见 `integration_report.md`。

## 下一步建议

1. 审核 `official_sources.jsonl` 中的 30 条来源是否都保留。
2. 审核 `feature_risk_cards.json` 中 20 张卡片的 `risk_extraction` 和 `tolerance` 是否符合论文口径。
3. 如果导师认可当前口径，可在论文或答辩材料中引用 `integration_report.md` 的合入统计。
4. `FUTURE-*` 规则只作为后续扩展计划，暂不参与当前实验打分，避免改变已有结果。
