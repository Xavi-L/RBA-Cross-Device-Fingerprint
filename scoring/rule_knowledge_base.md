# HybridGuard 综合规则知识库

本文档是离线大模型风险标签生成阶段使用的规则知识库说明版，结构化版本见 `scoring/rule_knowledge_base.json`。知识库来源包括三类：`ablation/consistency_feature_rules.md` 中已经沉淀的跨层一致性规则，`scoring/sorting.py` 提示词中的核心评分规则，以及结合攻击样本模板和真实采集字段扩展出的同类风险场景规则。

规则知识库的目标不是把每个字段写成固定阈值，而是把三端设备指纹中的语义关系显式化：Native 层描述底层设备，WebView 层描述 App 宿主容器，Web 层描述浏览器运行时。可信样本应在型号、版本、屏幕、DPR、CPU、GPU、JSBridge、安装来源和物理状态上相互呼应；高风险样本往往表现为某一层缺失、某几层相互矛盾，或同时暴露模拟器、无头浏览器、脚本重放、云机房等场景特征。

## 一、评分原则

规则按以下顺序应用。

1. 先检查一票否决规则。若传感器数量极低、JSBridge 缺失、Native 容器链路缺失或 UA 明确为脚本客户端，直接判为高危，不再被低风险规则降级。
2. 再检查攻击场景组合。廉价模拟器、无头 PC 浏览器、接口重放等组合通常给 90 分以上；云真机、测试机架或群控设备在核心链路完整时通常给 35 到 45 分。
3. 再检查三端一致性。型号、Android 版本、屏幕/DPR、CPU/platform、硬件/GPU、WebView provider/UA 主版本等规则用于衡量同一会话是否像来自同一设备和同一 App 宿主。
4. 最后应用容错规则。ADB、debuggable、cleartext、屏幕高度误差、Web deviceMemory 近似值、WebView 小版本差异不应单独构成高危。

风险分区如下。

| 分数区间 | 风险含义 | 解释口径 |
|---:|---|---|
| 0-20 | 低风险 | 三端身份链条基本自洽，安装来源合理，未触发高危规则 |
| 21-34 | 轻中风险 | 存在单项弱异常或字段缺失，但不足以判定攻击 |
| 35-49 | 云机房/测试环境 | 核心设备链条存在，但 manual、ADB、满电、UTC 时区等组合更像测试机架 |
| 50-79 | 可疑 | 多项跨层矛盾或环境异常并存 |
| 80-100 | 高风险 | 命中一票否决、模拟器、无头浏览器、接口重放或严重身份撕裂 |

## 二、核心完整性规则

| 规则 ID | 规则名称 | 关联字段 | 触发条件 | 风险口径 |
|---|---|---|---|---|
| CORE-001 | Native 缺失与接口重放 | `android_native_data.*`、`webview_data.jsbridge_injected`、`web_data.user_agent` | Native 关键字段整体缺失或大量为 null，同时 JSBridge 未注入，或 UA 为 `python-requests` 等脚本客户端 | 疑似接口重放或脱离 App 宿主的脚本请求，90-100 分 |
| CORE-002 | 传感器或 JSBridge 一票否决 | `sensor_total_count`、`jsbridge_injected` | `sensor_total_count < 10` 或 `jsbridge_injected=false` | 底层设备完整性或宿主真实性不足，90-100 分 |
| CORE-003 | 关键传感器矩阵异常 | 传感器总数与陀螺仪、加速度计、磁力计、光线、距离传感器 | 传感器总数偏低且多项关键传感器缺失 | 疑似模拟器或精简虚拟环境，80-95 分 |

这组规则继承了 `sorting.py` 中最强的短路规则：传感器数量极少或 JSBridge 缺失时，不应再被安装来源、ADB 等其他特征降级解释。

## 三、Native-Web 一致性规则

| 规则 ID | 规则名称 | 关联字段 | 触发条件 | 容错说明 |
|---|---|---|---|---|
| NW-001 | 型号与 UA 宽松匹配 | Native 型号、产品、主板、品牌、厂商，Web UA | Native 身份线索无法在 Android Web UA 中得到印证，或 UA 不像移动 Android 环境 | UA 只含 Android 但缺少型号时只作为弱异常 |
| NW-002 | Android 版本一致性 | `os_version`、`os_api_level`、Web UA | Native Android 主版本与 UA 声明版本不一致 | Android 16/API 36 是合法版本；无法解析时记为未知 |
| NW-003 | 屏幕与 DPR 软一致性 | `screen_resolution_physical`、`screen_resolution_logical`、`device_pixel_ratio` | 物理像素与逻辑像素 x DPR 的最大误差超过 10%，且横竖屏均无法解释 | 允许状态栏、导航栏、安全区造成高度误差 |
| NW-004 | CPU ABI 与 platform 一致性 | `cpu_abi`、`platform` | Native 为 ARM/ARM64，但 Web 暴露 Win32、Win64、x86 等平台矛盾 | platform 字段较粗糙，未知时不单独高危 |
| NW-005 | 硬件族与 WebGL GPU 一致性 | Native 硬件族，WebGL vendor/renderer | 真机硬件族对应 SwiftShader、Headless、Apple ANGLE 或桌面 GPU | MediaTek、Huawei、Samsung 可宽松匹配 Mali/PowerVR |
| NW-006 | 桌面或自动化 UA 痕迹 | Web UA、platform | UA/platform 包含 Windows NT、Win64、Headless、python-requests | 必须是明确桌面或脚本关键词 |
| NW-007 | 触控与移动 UA 一致性 | Web UA、`max_touch_points` | UA 声称 Android Mobile 但触点数为 0 | 不要求触点数量精确一致 |
| NW-008 | 内存容量软一致性 | `total_memory_gb`、`device_memory` | Native 总内存与 Web deviceMemory 差异过大，且伴随其他矛盾 | Web deviceMemory 粗粒度取整，3-4GB 差异可容忍 |

这部分规则对应消融实验中的 `consistency_native_web_*` 特征。它们强调宽松匹配而非字符串完全相等。例如屏幕需要按 DPR 换算，GPU 需要按硬件生态映射，型号需要在 UA 中做多级匹配。

## 四、Native-WebView 一致性规则

| 规则 ID | 规则名称 | 关联字段 | 触发条件 | 风险口径 |
|---|---|---|---|---|
| NVW-001 | system HTTP agent 与 Native 型号一致性 | `device_model`、`system_http_agent` | Native 型号无法在 WebView system HTTP agent 中得到印证 | 宿主层身份链条可能被改写 |
| NVW-002 | system HTTP agent 与 Android 版本一致性 | `os_version`、`system_http_agent` | Native Android 主版本与 system HTTP agent 中版本不一致 | 宿主层系统信息可能模板化 |
| NVW-003 | 预期 App 包名一致性 | `app_package_name` | 包名不以 `com.example.hybridguard` 开头 | 数据可能并非来自本文 App 宿主 |
| NVW-004 | 安装来源语义 | `installer_package` | `manual` 作为可疑部署线索；`packageinstaller`、`browser`、`vending` 作为合理来源线索 | manual 不单独高危，需要组合判断 |
| NVW-005 | Debug 与明文流量张力 | `is_debuggable`、`is_cleartext_traffic_permitted` | 两者同时为 true | 仅作为开发/测试辅助信号 |

这部分规则对应 `consistency_native_webview_*` 特征。它们主要回答一个问题：WebView 宿主提供的信息是否能和 Native 层看到的系统与 App 身份互相印证。

## 五、WebView-Web 一致性规则

| 规则 ID | 规则名称 | 关联字段 | 触发条件 | 容错说明 |
|---|---|---|---|---|
| WVWEB-001 | WebView provider 与 UA Chrome 主版本一致性 | `webview_provider_version`、Web UA | provider 主版本与 UA 中 Chrome/Chromium 主版本不一致 | 只比较主版本，小版本差异可容忍 |
| WVWEB-002 | Android WebView UA token | Web UA | UA 缺少 `; wv` 或 `Version/4.0` | 部分厂商 UA 可能省略 token，只作辅助 |
| WVWEB-003 | JSBridge 与移动 WebView 运行时一致性 | `jsbridge_injected`、Web UA | JSBridge、Android Mobile UA、WebView token 未能同时成立 | 缺少 token 不直接高危，需结合桥接和 UA 类型 |
| WVWEB-004 | 非浏览器 UA | Web UA | UA 包含 `python-requests`、`curl` 等脚本客户端 | App WebView 正常页面不应出现，90-100 分 |

这部分规则对应 `consistency_webview_web_*` 特征，关注 WebView 容器暴露的内核版本与 Web 运行时 UA 是否一致。

## 六、物理与运行环境规则

| 规则 ID | 规则名称 | 关联字段 | 触发条件 | 风险口径 |
|---|---|---|---|---|
| PHYS-001 | 模拟器硬件关键词 | `device_board`、`device_hardware`、`cpu_abi`、`webgl_renderer` | `goldfish`、`ranchu`、`emulator`、`x86` 与 SwiftShader 等同时出现 | Native 硬件和 WebGL 同时暴露模拟器特征 |
| PHYS-002 | WebGL 软件/桌面渲染 | `webgl_vendor`、`webgl_renderer` | SwiftShader、Headless、ANGLE Apple、VMware、VirtualBox 或明显桌面 GPU | 疑似模拟器、无头浏览器或桌面环境 |
| PHYS-003 | 算力耗时异常 | `compute_task_time_ms`、传感器、UA | 低于 50ms 且伴随桌面/无头/传感器缺失，或高于 800ms 且伴随机房线索 | 算力只作辅助，不单独高危 |
| PHYS-004 | 电池温度死值 | `battery_temp_celsius`、传感器、WebGL | 温度长期为 0、20.0、25.0 等模板值，且伴随模拟器证据 | 单条正常温度不扣分 |
| PHYS-005 | ADB 与满电组合 | `is_adb_enabled`、`battery_level_pct`、`is_charging` | ADB 开启且电量大于等于 97% | 符合测试机架、云真机或自动化群控特征，35-45 分 |
| PHYS-006 | 构建指纹调试/模拟器痕迹 | `build_fingerprint`、`build_tags`、`build_type` | 出现 `test-keys`、`dev-keys`、`generic`、`sdk_gphone`、`emulator`、`userdebug` | 发布构建 `user/release-keys` 为正常信号 |

这部分规则是在已有跨层一致规则基础上的扩展，主要来自 `generate_bad_data.py` 的攻击模板和 `rba_engine.py` 中对物理生态链路、渲染、算力和电池状态的分析维度。

## 七、攻击场景聚合规则

| 规则 ID | 场景 | 典型组合 | 建议分数 |
|---|---|---|---:|
| SCENE-001 | 云机房或测试机架 | 未命中一票否决；`installer_package=manual` 且时区为 0 或 ADB 开启；或 ADB 开启且电量大于等于 97% | 35-45 |
| SCENE-002 | 廉价模拟器 | `goldfish/ranchu/x86/SwiftShader/UTC` 与极少传感器组合出现 | 90-100 |
| SCENE-003 | 无头 PC 浏览器伪装 | Windows/Headless UA、Win32 platform、触点为 0、算力异常偏快、传感器缺失 | 90-100 |
| SCENE-004 | 官方来源与核心完整性通过 | 安装来源合理、传感器不少于 10、JSBridge 注入成功，且无高危规则 | 0-20 |

聚合规则负责把多个弱证据组合成可解释结论。特别需要区分“云真机/测试机架”和“模拟器/重放”：前者可能仍有真实传感器和 JSBridge，因此通常给中等风险；后者破坏了核心身份链路，应该给高风险。

## 八、容错规则

| 规则 ID | 容错对象 | 说明 |
|---|---|---|
| TOL-001 | 开发配置 | ADB、debuggable、cleartext 单独出现时不高危；只有和 manual、满电、UTC 等组合时才提高风险 |
| TOL-002 | 屏幕高度误差 | WebView 可用高度受状态栏、导航栏、安全区影响，不要求严格等于物理高度 |
| TOL-003 | 内存粗粒度 | Web deviceMemory 是近似值，和 Native 总内存允许数 GB 差异 |
| TOL-004 | WebView Chrome 小版本 | provider 与 UA 的 Chrome 主版本一致即可，小版本差异不单独扣分 |

容错规则是知识库的重要组成部分。它防止模型把开发阶段、厂商差异、浏览器 API 近似值和 UI 布局差异误判为攻击。

## 九、输出要求

大模型评分时应输出两个字段。

```json
{
  "risk_score": 0,
  "risk_reason": "三端身份链条基本自洽，安装来源合理，未触发高危规则。"
}
```

`risk_score` 必须是 0 到 100 的整数。`risk_reason` 使用一句中文短理由，指出主要命中规则；低风险样本说明三端自洽原因，高风险样本说明哪个层级发生了撕裂或命中了哪类攻击场景。
