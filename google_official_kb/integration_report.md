# Google 官方知识卡片合并报告

## 合并概况

本次将 `google_official_kb/feature_risk_cards.json` 中的 Google 官方文档知识卡片整合进主规则知识库 `scoring/rule_knowledge_base.json`。

合并结果：

- 官方来源：30 条。
- 风险知识卡片：20 张。
- 选择并合入当前规则：15 张。
- 暂不选择：5 张。
- 主规则库版本更新为：`2026-06-28-google-official-kb`。
- 35 条规则中，34 条新增 `official_knowledge` 元数据；`AGG-001` 是项目内部一致性聚合规则，未挂接单独官方卡片。

合并原则：

1. 只选择能支撑当前已采集字段或现有规则的卡片。
2. 只包含 `FUTURE-*` 目标的卡片暂不进入当前评分规则。
3. 官方文档用于支撑字段语义、安全背景和容错边界；风险阈值仍来自本项目规则、攻击模板和实验数据。
4. 不新增或修改任何规则的 `trigger`、`score_range`、`short_circuit`，只补充官方依据元数据。

## 已选择卡片

| 卡片 ID | 选择理由 | 合入的现有规则 |
|---|---|---|
| `GOKB-BUILD-001` | 当前已采集 Build、版本、ABI、构建指纹等字段，可支撑 Native 身份和构建/模拟器线索。 | `NW-001`、`NW-002`、`NW-004`、`NW-005`、`NVW-001`、`NVW-002`、`PHYS-006` |
| `GOKB-DISPLAY-001` | 当前已采集 Native 物理屏幕和 Web DPR/viewport，可支撑屏幕软一致性和高度误差容错。 | `NW-003`、`TOL-002` |
| `GOKB-SENSOR-001` | 当前已采集传感器总量和核心传感器布尔值，是核心完整性和模拟器判断的重要证据。 | `CORE-002`、`CORE-003`、`PHYS-001`、`SCENE-002`、`SCENE-004` |
| `GOKB-BATTERY-001` | 当前已采集电量、温度、充电状态等字段，可支撑测试机架/云真机组合线索。 | `PHYS-004`、`PHYS-005`、`SCENE-001` |
| `GOKB-WEBVIEW-001` | 当前已采集 WebView provider、默认 UA 和 settings UA，可支撑 WebView-Web 主版本一致性。 | `NVW-001`、`NVW-002`、`WVWEB-001`、`WVWEB-002`、`WVWEB-003`、`TOL-004` |
| `GOKB-WEBVIEW-002` | 当前采集链路依赖 JSBridge，官方 WebView API 可支撑宿主链路存在性判断。 | `CORE-001`、`CORE-002`、`WVWEB-003`、`SCENE-004` |
| `GOKB-UA-001` | 当前已采集 UA、platform、touch points 等 Web 运行时字段，可支撑软身份和桌面/自动化痕迹判断。 | `CORE-001`、`NW-001`、`NW-002`、`NW-004`、`NW-006`、`NW-007`、`WVWEB-002`、`WVWEB-004` |
| `GOKB-PACKAGE-001` | 当前已采集包名、版本、安装来源和安装时间，可支撑宿主真实性与安装来源语义。 | `NVW-003`、`NVW-004`、`SCENE-001`、`SCENE-004` |
| `GOKB-DEVCONFIG-001` | 当前已采集 ADB、developer options、debuggable、cleartext 等开发配置字段，可支撑测试环境辅助信号。 | `NVW-005`、`PHYS-005`、`SCENE-001`、`TOL-001` |
| `GOKB-MEMORY-001` | 当前已采集 Native 内存和 Web deviceMemory，可支撑粗粒度内存一致性与容错。 | `NW-008`、`TOL-003` |
| `GOKB-BOOT-001` | 当前已有 build tags/type 和 su_binary_present 弱线索；Verified Boot 是未来强证据，因此以混合方式支撑构建/Root 线索。 | `PHYS-006` |
| `GOKB-WEBVIEW-003` | 当前已有 JSBridge 字段，官方 native bridge 风险文档可补充安全边界和宿主链路解释。 | `CORE-001`、`CORE-002`、`WVWEB-003` |
| `GOKB-DEVCONFIG-002` | 官方 debuggable、cleartext 和 Network Security Config 风险文档能强化当前开发配置容错规则的依据。 | `NVW-005`、`SCENE-001`、`TOL-001` |
| `GOKB-AUTOMATION-001` | 当前已采集 webdriver、UA、platform、DPR、viewport 和算力耗时，可支撑自动化/移动模拟风险场景。 | `NW-003`、`NW-006`、`PHYS-002`、`PHYS-003`、`SCENE-003` |
| `GOKB-EMULATOR-001` | 当前已采集 hardware、product、ABI、传感器和 WebGL renderer，可支撑模拟器/AVD 背景解释。 | `NW-005`、`PHYS-001`、`PHYS-002`、`SCENE-002` |

## 未选择卡片

| 卡片 ID | 未选择理由 | 后续处理 |
|---|---|---|
| `GOKB-NET-001` | 网络传输类型、VPN、带宽等当前只适合作为低强度背景信息；没有独立现有规则承接，强行合入会稀释风险边界。 | 保留在外挂知识库，未来若新增网络环境分组或 VPN/代理场景规则再合入。 |
| `GOKB-PLAY-001` | Play Integrity verdict 是强官方证据，但当前项目尚未采集真实 token/verdict。 | 作为 `FUTURE-PLAY-001` 保留，不参与当前评分。 |
| `GOKB-PLAY-002` | Play Integrity 标准请求链路需要 request hash、integrity token 和服务端校验，当前数据集中不存在这些字段。 | 作为 `FUTURE-PLAY-002` 保留，后续做服务端挑战/防重放时合入。 |
| `GOKB-KEY-001` | Key Attestation 需要硬件 keystore、证书链、challenge 和服务端验证，当前采集 App 未实现。 | 作为 `FUTURE-KEY-001` 保留，后续增强设备真实性证明时合入。 |
| `GOKB-WEBVIEW-004` | WebView 文件访问和 URI 加载风险虽与当前 settings 字段部分相关，但缺少 loaded URL、scheme、host、origin 等关键上下文，暂不适合进入当前设备指纹评分。 | 作为 `FUTURE-WVSEC-002/003` 保留，后续采集 WebView 导航来源后再合入。 |

## 规则覆盖情况

已增强的规则类别：

- 核心完整性：`CORE-001` 到 `CORE-003`。
- Native-Web 一致性：`NW-001` 到 `NW-008`。
- Native-WebView 一致性：`NVW-001` 到 `NVW-005`。
- WebView-Web 一致性：`WVWEB-001` 到 `WVWEB-004`。
- 物理与运行环境：`PHYS-001` 到 `PHYS-006`。
- 攻击场景聚合：`SCENE-001` 到 `SCENE-004`。
- 容错规则：`TOL-001` 到 `TOL-004`。

未直接增强：

- `AGG-001`：这是本项目内部的一致性失败计数和平均一致性聚合规则。它依赖其他规则/特征的输出，不直接对应某一条 Google 官方 API 或安全文档，因此本次未挂接单独卡片。

## 合并后的使用边界

1. `official_knowledge` 字段可以进入 LLM prompt，帮助模型理解字段语义和容错边界。
2. 不应把 Google 官方文档解释成 Google 官方风险分数；官方文档不提供本项目的 0-100 分阈值。
3. future-only 卡片仍保留在 `google_official_kb/feature_risk_cards.json`，便于论文说明后续扩展方向，但当前不参与实验结果。
4. 如果后续实现 Play Integrity、Key Attestation 或 WebView URL/origin 采集，应先新增采集字段和实验验证，再把对应 `FUTURE-*` 卡片转入当前规则。

