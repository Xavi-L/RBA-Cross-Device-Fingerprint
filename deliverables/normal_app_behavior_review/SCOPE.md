# 正常 App 指纹字段行为调研：范围与样本

访问/整理日期：2026-09-28。实际起始 HEAD：`b3a06ba77426fd858d234aabb14a1f0331ce38df`，与给定 V2-C 参考一致。未 reset。开始时不存在本目录；已先核对 V2-A/B 字段语义诊断及 V2-C 报告、确认计划和实际 model.json，接续而不覆盖旧结论。

本轮完成两层：官方语义与固定平台源码、真实 App/框架静态路径。**运行验证统一 NOT_PERFORMED；第三层运行测量明确排除，不是交付阻塞。** 不安装/运行 App、APK、模拟器、浏览器自动化，不连设备、不新增指纹、不fit、不重新预测、不改模型/阈值/标签/准入。不启动 V1/V2重跑、R10/V3或独立确认，不提交、推送或创建PR。

范围以Android App内嵌网页、Native/Host/App Web实际采集为主。系统与环境正常的语言、时区、资源差异保留；排除主动伪装并不假设设备同质，也不评价用户动机。

| 行为类别 | 口径 |
| --- | --- |
| A | App在默认或正常业务路径主动配置；业务按钮不是自动等于用户修改指纹选项 |
| B | 框架/SDK/内核封装默认机制；可选参数必须另核App是否提供 |
| C | 系统、设备、内核版本或资源差异 |
| D | API本身的近似、兼容、作用域、语法或版本限制 |
| E | 用户显式选择语言/覆盖等分支，含下次启动重用旧偏好；标USER_OPT_IN_OUT_OF_SCOPE |
| F | 外部干预、测试/调试/自动化配置；不充当正常发行App默认证据 |

研究用七档证据强度：SPEC_OR_API_DEFINED、ENGINE_IMPLEMENTATION_SUPPORTED、FRAMEWORK_CAPABILITY、APP_DEFAULT_PATH_SUPPORTED、APP_CONDITIONAL_PATH_SUPPORTED、NOT_FOUND_IN_SCOPED_CODE、UNRESOLVED。DEFAULT仅针对表中写明入口/对象；“组件初始化默认”不等于App所有用户每次启动都会进入。覆盖记录本身不是正面行为证据；mixed覆盖行用UNRESOLVED，具体发现另有独立行。所有未发现仅限声明目录、关键词、文件类型与人工深入路径。

实际项目版本分层如下（[LOC-023](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/b3a06ba77426fd858d234aabb14a1f0331ce38df/hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/C_confirmation/input_manifest.json#L1-L12)、[LOC-024](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/b3a06ba77426fd858d234aabb14a1f0331ce38df/hybridguard_agent/artifacts/formal_manipulation_v1_20260923/02_inputs/inference_inputs.jsonl#L1-L262)、[LOC-025](https://github.com/Xavi-L/RBA-Cross-Device-Fingerprint/blob/b3a06ba77426fd858d234aabb14a1f0331ce38df/android_app/HybridGuard/featureapp/build.gradle.kts#L58-L80)）：

| 材料层 | 核实的版本 | 限制 |
| --- | --- | --- |
| V2最终模型训练成员对应的既有记录 | App code10 / 1.6.3-expanded-v2.2-webview-control；Android11/API30、15/API35、16/API36；Google WebView 83.0.4103.106、124.0.6367.219、133.0.6943.137 | 仅只读162成员的版本字段；对应27/18/117阶段，不是独立设备数；不重算性能 |
| 当前工作区采集源码 | code11 / 1.6.4-expanded-v2.2-mtc-https；min21、target36、compile36.1 | 当前源码不能冒称历史code10 APK逐字一致；仅比较已见API路径和既有字段，不重新构建 |
| 固定内核源码 | UA/locale/timezone深追133；deviceMemory及plugin容器补83/124 | tag与记录版本对应，不等于已验证商业二进制或厂商patch；未逐项覆盖每个历史版本 |
| 动态官方资料 | Android API、HTML、ECMAScript、Device Memory、WebDriver、RFC9110、Khronos，访问日见来源表 | 最新规范不自动适用于旧实现 |
| App/框架 | 行为搜索前解析各官方upstream HEAD为以下固定commit | 检查main/生产模块与入口，不宣称就是商店发布APK；实际App锁定依赖另核 |

主版本结论以V2 App177三版本为准。初期查看到更广MTC metadata只用于辨认资料层，未把MTC并入监督分母、未替代V2版本锚点，也未为本轮新增采集。

初始样本按真实App、源码可访问、内嵌网页容器与技术/业务覆盖预选；**在行为搜索前固定**，没有依据是否支持当前规则换样。8个真实App、3个独立框架；无DISCOVERY_SAMPLE。Thunderbird/K-9为一个项目，NewPipeExtractor仅是实际依赖，不另计App；Joplin使用RN WebView但独立框架HEAD不被当成其13.16.2版本。便利样本不是市场随机抽样。

| 项目 | 分类 | 固定提交 | 选取理由 |
| --- | --- | --- | --- |
| Wikipedia | APP / 百科 | [89f8e5abdc95](https://github.com/wikimedia/apps-android-wikipedia/tree/89f8e5abdc957133efb0b1b944cbb5751a619a35) | 广泛使用的原生百科阅读App；内容阅读WebView可核查 |
| Thunderbird / K-9 | APP / 邮件 | [0cffe006be79](https://github.com/thunderbird/thunderbird-android/tree/0cffe006be790a4e75659d5a4356d1f17947a427) | 邮件内容内嵌HTML渲染，与百科业务不同 |
| AntennaPod | APP / 播客 | [d3c01a5cd7bd](https://github.com/AntennaPod/AntennaPod/tree/d3c01a5cd7bd54952578477e2ad1935e51551857) | 媒体App的节目说明HTML渲染 |
| Nextcloud | APP / 云文件 | [d8e3ce42d12f](https://github.com/nextcloud/android/tree/d8e3ce42d12fc839b2d9b2d8f631ea3e2fca10b4) | 云文件客户端认证与内嵌网页路径 |
| React Native WebView | FRAMEWORK / 跨平台WebView组件 | [054572b18782](https://github.com/react-native-webview/react-native-webview/tree/054572b187824084aa19e709f5d2f569a33a6f4a) | 常用框架组件，核查默认设置与可选属性边界 |
| Capacitor | FRAMEWORK / 混合App运行框架 | [145560ee590d](https://github.com/ionic-team/capacitor/tree/145560ee590d86637dc9dd2e2c9f4c08b0f631c0) | 默认Bridge初始化与框架配置机制 |
| NewPipe | APP / 视频播放 | [7e5df38aad4b](https://github.com/TeamNewPipe/NewPipe/tree/7e5df38aad4b2c035332b3f71aee3064d4fdaae4) | 独立真实视频App，检查内嵌网页/订阅相关生产容器 |
| WordPress Android | APP / 内容发布 | [9ad2e38005b1](https://github.com/wordpress-mobile/WordPress-Android/tree/9ad2e38005b1292f1927bc463b9abb7c78afce81) | 独立内容发布App，检查编辑器与认证浏览器容器 |
| Signal Android | APP / 通信 | [6151a523373e](https://github.com/signalapp/Signal-Android/tree/6151a523373e02f37d6a367fe448bd15a3de1a72) | 独立通信App，检查内嵌网页及验证业务容器 |
| Joplin | APP / 笔记 | [4c0e2bc0e221](https://github.com/laurent22/joplin/tree/4c0e2bc0e221e934023b20f462f035aa3321f4b5) | 独立跨平台笔记App，检查移动端WebView及配置透传 |
| Flutter webview_flutter | FRAMEWORK / Flutter WebView封装 | [ba0364a650af](https://github.com/flutter/packages/tree/ba0364a650af47374ffb1412595e3bf789ae5c99) | 与其他框架区分的Flutter Android容器封装 |

每个项目六组覆盖、关键词、目录、深入链、配置来源及负面/未知结果见 [APP_CODE_EVIDENCE.csv](APP_CODE_EVIDENCE.csv)。HTTP请求、Java默认locale、WebView设置、JS暴露、UI格式化分别计证据；多个页面同项目不重复计App。WordPress/Nextcloud/NewPipe有正常业务WebView UA设置，Wikipedia/AntennaPod另有HTTP UA路径；不将两类相加成5个网页UA案例。

共享依赖限制：Joplin明确RN WebView 13.16.2；NewPipe锁定Extractor 13a655fe53e0c3065f88725fc1fb594c3ede0169，其PoToken注册空实现为负证据。Capacitor/Flutter为能力样本，未证明这8个App采用其特定能力。详细对应在B-002/B-021..027/A-012..015。

网络失败已记录并用等价一手raw/codeload源码继续；没有把搜索摘要、论坛、博客或旧聊天当事实。固定源码精确行范围、最小支持命题、不支持扩展与依赖ID见 [SOURCE_REGISTER.json](SOURCE_REGISTER.json)。下载源码仅在临时目录静态读取，未复制第三方源树或原始数据进交付。

历史保护：原工作区有用户改动与构建产物，本轮只新增本目录。未修改V2关闭状态、历史报告/合同/源码快照/模型与108控制分母。未以报警倒推标签；表内“正常可满足机制”是语义与代码推论，不是新clean记录或真实FPR。校验只检查本交付引用/表结构/模型身份映射，不作重型完整性审计。

停止点：两层调研交付即停止。后续只建议有边界的源码补查/采集口径设计；不自动进入实现、采集、训练或确认。
