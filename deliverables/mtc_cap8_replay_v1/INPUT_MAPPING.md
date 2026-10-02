# CAP8 历史 MTC 输入映射

三个固定 WEBGL50 / RETENTION 模型使用相同的八条单条件规则，各模型身份、编码器、极性和阈值分别保留，见 [MODELS.json](MODELS.json)。以下写的是规则最终触发条件；数值编码器实际保存 `LE` 原子，再应用原模型的负极性。

适配入口为 `hybridguard_agent.research.mtc_cap8_replay.predict_historical_mtc`。接收 P1 原始 `hybridguard-mtc-observation-v2` 行，不更改其版本、数据值或历史标签。只支持已核对的 featureapp v9 / `1.6.2-expanded-v2.2-mtc` 与 v11 / `1.6.4-expanded-v2.2-mtc-https`，探针均为 `expanded-web-67-v1`。旧采集实现依据为提交 `134201114a8a15a682bb41ee94c796d14e550c9e` 的 `web_probe/canonical_web_probe.js`（navigator 同步读取：346–359 行；旧 webdriver 与 MIME：580–584 行）。v11 的 TLS 与地址改动不改变这些探针含义。

表中路径均为 App 原始 JSON 路径；P1 `features`、`field_status`、`field_quality` 使用加 `app.` 前缀的同名扁平 key。每条实际输出同时保存字段原值、是否存在、状态与质量。未选择的硬件并发数、Native 内存和 Browser 数据不进入预测。

| 保存规则 | 原字段路径 | 含义和单位 | 旧数据可评估情况与限制 |
|---|---|---|---|
| WebGL1 数字/数字字符串查询不等价 | `collection_observations.webgl_parameter.observation` | 对 37445 / 37446 的 numeric-before、numeric-string、numeric-after 原始查询以及 34921 控制查询 | v9/v11 没有这些原始观测，固定 U，原因 `LEGACY_WEBGL1_RAW_QUERY_OBSERVATION_ABSENT`；不从 vendor/renderer 名称推造，不从其他会话借值。 |
| MIME 数量 > 0 | `web_data.automation_surface_layer.mime_types_count` | `navigator.mimeTypes ? navigator.mimeTypes.length : 0` 的报告条目数 | observed 且质量正常的有限数值可按原阈值判断；0 保留为旧投影值，无法区分 API 缺失与空列表，不声称它证明 API 实际存在。 |
| webdriver 报告 true | `web_data.automation_surface_layer.webdriver` | 旧版 `navigator.webdriver === true` 布尔投影 | true 经既有 legacy 语义为 T；false 为 U（`LEGACY_NONTRUE_PROJECTION_AMBIGUOUS`），不能区分真实 false、属性缺失或非布尔值。T 仅为属性报告，不是攻击真值。 |
| 时区偏移 > -480 | `web_data.execution_layer.timezone_offset` | JS `Date.getTimezoneOffset`，分钟，UTC 减本地 | observed 且有限数值时可靠计算原条件；无单位转换。该条件可能命中正常时区设置。 |
| deviceMemory > 2 | `web_data.navigator_layer.device_memory` | `navigator.deviceMemory` 粗粒度、舍入及截断的 GiB 暴露值 | 正的有效观测可计算；旧脚本 `|| 0` 的默认 0 为 U（`AMBIGUOUS_NAVIGATOR_SENTINEL`），不能替换成实测 0，也不等同于设备物理 RAM。 |
| language 与 languages[0] 不同 | `web_data.navigator_layer.language`、`web_data.navigator_layer.languages` | 同一同步 navigator 读取中的完整有限域语言标签 | 复用既有语言关系语义；缺失、空列表、错误类型、不可支持的首项标签为 U；不借 Native/Browser 语言，不用列表尾项代替首项。 |
| CAT:NW-006 UA/platform | `web_data.navigator_layer.platform`、`web_data.navigator_layer.user_agent` | 固定桌面/脚本 UA 或桌面 platform 条件 | 复用冻结规则目录、字段门控、原解析器和 NW-006 原判定；两类均需可解释，否则 U；不读取型号/系统来补猜 UA 分类。 |
| DPR > 2.625 | `web_data.screen_layer.device_pixel_ratio` | CSS 像素到设备像素比例，无量纲 | observed 且有限数值时计算原阈值；不结合分辨率或 Native density 改写。 |

适配器直接复用 `matrix.field_state` 的数值类型、有限性、来源状态和默认值门控；`measure_historical_numeric` 同时对 `hardware_concurrency || 0` 保留 U，但该字段并未被三个模型选中。缺字段、来源不可用与错误数值类型为 U；非法状态枚举、结构损坏与执行异常为 FAILED。每个字段的原可用状态都保留，不强行填 observed。

语言与 webdriver 的 `rsr-input-v1` 是既有解释器的内存输入封套，并非新版采集版本。其 `SourceBinding` 来自上述外部已核对的旧采集合同，仅表示同步/来源关联，不证明页面值未经修改。webdriver 一直显式使用 `legacy_projection_v1`。`predict_replay(..., source_mode="raw_observation_v1")` 直接委托原 `predict_current`，原入口的 raw 限制不变；该分支用已有完整新输入做等价测试。

所有选中规则继续进入原 `transform_numeric` 与三值 `predict`：T OR U = T，F OR U = U，执行失败不会被改写为 U 或正常。`rule_results.state` 是保存极性后的规则状态，`atom_state` 是原始原子状态；模型身份与回放适配器版本分别记录。样本 ID、标签、型号、厂商、历史 split 只留在结果关联层。

开发修正记录：在任何真实 MTC 回放前，首次导入测试发现解释器函数名误写，已更正为 `webdriver_reported_state`；同时修正冻结目录的相对层级。初版 v11 版本名遗漏 `-https` 后缀，经枚举原 P1 元数据核对后更正，并增加 v11 正确版本名与错误版本名边界测试。以上均为适配实现修复，没有更改规则、阈值、选择算法、已有数据或历史实验结果。
