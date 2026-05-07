# Cross-Layer Consistency Feature Rules

本文档用自然语言说明 `run_consistency_ablation.py` 中的跨层一致性特征构造规则。它面向论文写作和答辩展示，重点解释三端原始字段如何被转换为 `consistency_*` 数值特征，以及这些特征为什么能表达“是否来自同一设备/同一 App 宿主环境”。

## 总体思想

随机森林不能直接理解“Web UA 与 Native 型号是否语义一致”这类关系。实验中先通过规则引擎把三端之间的关系转成数值特征，再让随机森林学习这些特征与 `risk_score` 的关系。

整体流程：

```text
Android Native 特征 + WebView 宿主特征 + Web 前端特征
    -> 解析型号、版本、屏幕、CPU、GPU、JSBridge、安装来源等语义元素
    -> 进行宽松跨层匹配
    -> 生成 consistency_* 数值特征
    -> 输入随机森林
```

“宽松匹配”的含义是：不要求字符串完全相等，而是承认不同层对同一设备信息的表达方式不同。例如 Native 的 `device_hardware=qcom` 与 WebGL 的 `Adreno` 不同名但语义一致；Native 物理分辨率和 Web 逻辑分辨率之间还要乘以 DPR，并允许状态栏、导航栏、安全区带来的误差。

## 缺失值与数值约定

规则中使用以下约定：

| 值 | 含义 |
|---:|---|
| `1.0` | 匹配、一致、规则命中或风险信号存在 |
| `0.0` | 不匹配、不一致、规则未命中或风险信号不存在 |
| `-1.0` | 关键输入缺失，无法判断 |
| `99.0` | 版本差异或数值差异无法计算时的哨兵值 |
| `0.0-1.0` | 宽松匹配强度或一致性分数 |

布尔值会转成数值：`true -> 1.0`，`false -> 0.0`，缺失为 `-1.0`。

## 一、Native-Web 一致性特征

这组特征比较 Android Native 层看到的底层设备信息，与 Web 前端 JavaScript 暴露出的浏览器运行环境是否一致。

### 1. 设备型号与 UA 宽松匹配

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.device_model` |
| Native | `android_native_data.device_product` |
| Native | `android_native_data.device_board` |
| Native | `android_native_data.device_brand` |
| Native | `android_native_data.device_manufacturer` |
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_model_ua_strength` | Native 型号/产品/主板/品牌在 Web UA 中的宽松匹配强度 |
| `consistency_native_web_model_ua_match` | 当匹配强度大于等于 `0.8` 时记为 `1.0`，否则为 `0.0` |

匹配强度规则：

| 条件 | 分数 |
|---|---:|
| UA 缺失 | `-1.0` |
| `device_model` 直接出现在 UA 中 | `1.0` |
| `device_product` 出现在 UA 中 | `0.8` |
| `device_board` 出现在 UA 中 | `0.7` |
| UA 含 Android，且包含品牌或厂商 | `0.55` |
| UA 只声明 Android，但没有型号/产品/品牌线索 | `0.35` |
| UA 不像 Android 移动环境 | `0.0` |

解释口径：

WebView 中的 UA 通常包含 Android 版本和设备型号。例如 Native 采到 `device_model=2211133C`，Web UA 中也出现 `2211133C Build/...`，说明 Web 层暴露的设备身份与 Native 层一致。如果 Native 是移动设备但 UA 是 Windows、Headless Chrome 或 `python-requests`，则说明 Web 层身份存在伪装或采集环境异常。

### 2. Android 版本一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.os_version` |
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_android_version_match` | 从 Native OS 和 Web UA 中解析 Android 主版本，完全一致为 `1.0`，不一致为 `0.0`，缺失为 `-1.0` |
| `consistency_native_web_android_version_delta` | 两侧 Android 主版本的绝对差值；无法解析时为 `99.0` |

解析方式：

- Native 例：`Android 16` -> `16`
- Web UA 例：`Mozilla/5.0 (Linux; Android 16; ...)` -> `16`

解释口径：

同一 WebView 宿主中，Native OS 版本与 Web UA 中声明的 Android 版本应高度一致。版本不一致可能意味着 UA 被改写、Web 环境来自其他设备模板，或采集链路被代理。

### 3. 屏幕与 DPR 软一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.screen_resolution_physical` |
| Web | `web_data.screen_resolution_logical` |
| Web | `web_data.device_pixel_ratio` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_screen_width_error_ratio` | 物理宽度与 `Web 宽度 x DPR` 的相对误差 |
| `consistency_native_web_screen_height_error_ratio` | 物理高度与 `Web 高度 x DPR` 的相对误差 |
| `consistency_native_web_screen_max_error_ratio` | 宽高相对误差中的较大值 |
| `consistency_native_web_screen_score` | 屏幕一致性软分数，`max(0, 1 - max_error / 0.2)` |
| `consistency_native_web_screen_consistent_10pct` | 最大误差小于等于 `10%` 时为 `1.0` |

计算逻辑：

```text
width_error  = abs(native_width  - web_width  x dpr) / native_width
height_error = abs(native_height - web_height x dpr) / native_height
max_error    = max(width_error, height_error)
screen_score = max(0, 1 - max_error / 0.2)
```

规则会同时尝试横竖屏两种方向，选择误差更小的一种。

解释口径：

Native 层拿到的是物理像素，Web 层拿到的是 CSS 逻辑像素，二者并不直接相等，但应满足 `物理像素 ~= 逻辑像素 x DPR`。由于状态栏、导航栏、安全区会影响 Web 可用高度，所以使用软误差而不是严格等式。

### 4. CPU ABI 与 Web platform 一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.cpu_abi` |
| Web | `web_data.platform` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_cpu_platform_match` | Native CPU 家族与 Web platform 家族一致为 `1.0` |
| `consistency_native_web_cpu_platform_known` | 两侧都能识别出 CPU/platform 家族时为 `1.0` |

宽松映射：

| Native CPU ABI | 家族 |
|---|---|
| 包含 `arm64` 或 `aarch64` | `arm64` |
| 包含 `armeabi` 或 `armv7` | `arm` |
| 包含 `x86` 或 `i686` | `x86` |

| Web platform | 家族 |
|---|---|
| 包含 `aarch64`、`armv8`、`arm64` | `arm64` |
| 包含 `arm` | `arm` |
| 包含 `i686`、`x86`、`win32`、`win64` | `x86` |

解释口径：

真实 Android 手机常见组合是 Native `arm64-v8a` 对应 Web `Linux aarch64` 或相近 ARM platform。如果 Native 侧是 ARM 设备，而 Web 层暴露 `Win32`，则说明 Web 环境与底层设备身份不自洽。

### 5. 硬件族与 WebGL GPU 一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.device_hardware` |
| Native | `android_native_data.device_board` |
| Native | `android_native_data.device_product` |
| Native | `android_native_data.device_manufacturer` |
| Web | `web_data.webgl_vendor` |
| Web | `web_data.webgl_renderer` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_gpu_family_score` | Native 硬件族与 WebGL GPU 族的宽松匹配分 |
| `consistency_native_web_gpu_family_match` | 匹配分大于等于 `0.8` 时为 `1.0` |
| `consistency_native_web_gpu_software_or_desktop` | WebGL 显示 SwiftShader、Apple ANGLE、Headless 等软件/桌面渲染痕迹时为 `1.0` |

Native 硬件族识别：

| 线索 | 家族 |
|---|---|
| `goldfish`、`ranchu`、`emulator` | `emulator` |
| `qcom`、`qualcomm`、`kona`、`lahaina`、`kalama`、`taro`、`pineapple`、`holi` | `qualcomm` |
| `mtXXXX`、`kXXXX`、`mediatek` | `mediatek` |
| `kirin`、`huawei`、`maleoon` | `huawei` |
| `exynos`、`s5e`、`samsung` | `samsung` |

WebGL GPU 族识别：

| 线索 | 家族 |
|---|---|
| `SwiftShader`、`ANGLE (Apple...)`、`Headless` | `software_desktop` |
| `Adreno`、`Qualcomm` | `qualcomm` |
| `Mali`、`ARM` | `arm_mali` |
| `Maleoon`、`Huawei` | `huawei` |
| `Xclipse`、`Samsung` | `samsung` |
| `PowerVR`、`Imagination` | `powervr` |

匹配分规则：

| Native 硬件族 | WebGL GPU 族 | 分数 |
|---|---|---:|
| `qualcomm` | `qualcomm` | `1.0` |
| `mediatek` | `arm_mali` 或 `powervr` | `0.85` |
| `huawei` | `arm_mali` 或 `huawei` | `0.85` |
| `samsung` | `arm_mali` 或 `samsung` | `0.85` |
| `emulator` | `software_desktop` | `0.6` |
| 任意真机硬件族 | `software_desktop` | `0.0` |
| 未知 | 未知或无法判断 | `-1.0` |
| 其他组合 | 其他组合 | `0.2` |

解释口径：

GPU 是跨层比对中非常有价值的软证据。真机的底层 SoC 家族与 WebGL renderer 通常存在稳定对应关系，例如 Qualcomm 对 Adreno，MediaTek/Kirin/Samsung 常对 Mali 或其他移动 GPU。如果 Web 层暴露 Apple ANGLE、SwiftShader 或 Headless 渲染器，则可能不是手机本机 WebView。

### 6. 触控与移动 UA 一致性

相关字段：

| 层 | 字段 |
|---|---|
| Web | `web_data.user_agent` |
| Web | `web_data.max_touch_points` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_touch_mobile_match` | UA 同时包含 `Android` 和 `Mobile`，且 `max_touch_points > 0` 时为 `1.0` |

解释口径：

移动 Android WebView 应具备触控能力。如果 UA 声称移动 Android，但触点数量为 0，可能存在桌面浏览器伪装移动 UA 的情况。

### 7. 内存容量软一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.total_memory_gb` |
| Web | `web_data.device_memory` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_memory_delta_gb` | Native 总内存与 Web deviceMemory 的绝对差 |
| `consistency_native_web_memory_score` | `max(0, 1 - memory_delta / 4)`，无法判断时为 `-1.0` |

解释口径：

Web 的 `deviceMemory` 是粗粒度近似值，不能与 Native 总内存严格相等。因此这里只使用软分数。差异在数 GB 内可以接受，过大差异则说明两层环境可能不一致。

### 8. 桌面或自动化 UA 痕迹

相关字段：

| 层 | 字段 |
|---|---|
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_web_desktop_or_bot_ua` | UA 包含 `Windows NT`、`Win64`、`Headless`、`python-requests` 时为 `1.0` |

解释口径：

移动端无感风控场景中，Web 层出现桌面、无头浏览器或脚本客户端 UA，是典型跨层身份冲突信号。

## 二、Native-WebView 一致性特征

这组特征比较 Native 层设备信息与 App/WebView 宿主层暴露的信息是否一致。

### 1. WebView system HTTP agent 与 Native 型号一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.device_model` |
| WebView | `webview_data.system_http_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_webview_agent_model_match` | Native `device_model` 出现在 WebView system HTTP agent 中时为 `1.0` |

解释口径：

WebView/系统 HTTP agent 通常会包含 Android 版本和 Build 型号。如果 Native 设备型号无法在该 agent 中互证，说明宿主侧身份链条可能不完整或被改写。

### 2. WebView system HTTP agent 与 Native Android 版本一致性

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.os_version` |
| WebView | `webview_data.system_http_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_webview_agent_android_version_match` | Native Android 主版本与 system HTTP agent 中的 Android 主版本一致为 `1.0` |
| `consistency_native_webview_agent_android_version_delta` | 两者 Android 主版本差值；无法解析为 `99.0` |

解释口径：

App 宿主层的系统 agent 应与 Native OS 版本一致。如果 Native 层和 WebView 宿主层版本不一致，说明 WebView 宿主信息可能被替换或模板化。

### 3. JSBridge 注入状态

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.jsbridge_injected` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_webview_bridge_injected` | JSBridge 注入成功为 `1.0`，未注入为 `0.0`，缺失为 `-1.0` |

解释口径：

HybridGuard 的三端融合依赖 JSBridge 连接 WebView 和 Native。如果声称来自 App WebView 环境却没有 JSBridge，往往意味着宿主真实性异常、页面不在预期容器中，或采集被脚本/代理伪造。

### 4. App 包名一致性

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.app_package_name` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_webview_package_expected` | 包名以 `com.example.hybridguard` 开头时为 `1.0` |

解释口径：

实验 App 的预期包名是 `com.example.hybridguard` 或其相关模块。包名不符合预期时，说明数据可能并非来自本文 App 宿主。

### 5. 安装来源语义

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.installer_package` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_webview_installer_official_like` | 安装来源包含 `packageinstaller`、`browser`、`vending` 时为 `1.0` |
| `consistency_native_webview_installer_manual` | 安装来源严格等于 `manual` 时为 `1.0` |

解释口径：

安装来源是 App 宿主可信度的一部分。官方安装器、系统安装器或浏览器下载可以解释为较常见来源；`manual` 常与自动化部署、云机房或批量装机环境相关，需要结合 ADB、时区、电量等特征判断。

### 6. Debug 与明文流量张力

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.is_debuggable` |
| WebView | `webview_data.is_cleartext_traffic_permitted` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_native_webview_debug_cleartext_tension` | `is_debuggable=true` 且 `is_cleartext_traffic_permitted=true` 时为 `1.0` |

解释口径：

Debuggable 与允许明文流量同时出现，符合开发/测试环境特征。它不是单独判定高风险的充分条件，但可作为 App 宿主可信度和部署环境异常的辅助信号。

## 三、WebView-Web 一致性特征

这组特征比较 WebView 容器提供的浏览器内核信息，与 Web 前端 JavaScript 看到的运行环境是否一致。

### 1. WebView provider 与 Web UA Chrome 主版本一致性

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.webview_provider_version` |
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_webview_web_chrome_major_match` | WebView provider 主版本与 Web UA 中 Chrome 主版本一致为 `1.0` |
| `consistency_webview_web_chrome_major_delta` | 两者主版本差值；无法解析为 `99.0` |

解析方式：

- Provider 例：`145.0.7632.159` -> `145`
- UA 例：`Chrome/145.0.7632.159` -> `145`

解释口径：

Android WebView 的 provider 版本通常会反映到 Web UA 的 Chrome/WebView 版本。两者主版本差距较大时，说明 Web UA 可能被修改，或 Web 层并非来自该 WebView provider。

### 2. WebView UA token

相关字段：

| 层 | 字段 |
|---|---|
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_webview_web_ua_has_wv_token` | UA 包含 `; wv` 或 `Version/4.0` 时为 `1.0` |

解释口径：

Android WebView UA 通常包含 `; wv` 或 `Version/4.0` 等标记。缺少这些标记不一定代表异常，但在 App WebView 场景下会削弱宿主环境一致性。

### 3. JSBridge 与移动 WebView 运行时一致性

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.jsbridge_injected` |
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_webview_web_bridge_mobile_runtime_match` | JSBridge 注入、UA 是 Android Mobile、且 UA 有 WebView token 时为 `1.0` |

解释口径：

真实 App WebView 环境应同时满足：有 JSBridge、UA 呈现移动 Android、UA 呈现 WebView token。三者同时成立时，WebView 容器与 Web 运行时较为自洽。

### 4. 非浏览器 UA

相关字段：

| 层 | 字段 |
|---|---|
| Web | `web_data.user_agent` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_webview_web_non_browser_ua` | UA 包含 `python-requests` 时为 `1.0` |

解释口径：

`python-requests` 说明请求来自脚本 HTTP 客户端，而不是浏览器/WebView 运行环境。这是 WebView-Web 层面的强异常信号。

## 四、三端语义规则特征

这组特征不是简单比较两端字段，而是把 Native、WebView、Web 三端信号组合成更接近风控规则的语义特征。

### 1. 核心完整性通过

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.sensor_total_count` |
| WebView | `webview_data.jsbridge_injected` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_core_integrity_pass` | `sensor_total_count >= 10` 且 JSBridge 注入成功时为 `1.0` |

解释口径：

真实移动设备通常具备一定数量传感器，且本文 App 内应能注入 JSBridge。如果传感器数量合理且桥接存在，说明底层设备与 App 宿主基础完整性较好。

### 2. 传感器或 JSBridge 失败

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.sensor_total_count` |
| WebView | `webview_data.jsbridge_injected` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_sensor_bridge_fail` | `sensor_total_count < 10` 或 JSBridge 为 `false` 时为 `1.0` |

解释口径：

传感器严重缺失或 JSBridge 未注入，是当前规则标签体系中的一票否决式高风险信号。它常见于模拟器、无头环境、脚本请求或非预期宿主。

### 3. manual 安装来源与时区/ADB 组合

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.installer_package` |
| Web | `web_data.timezone_offset` |
| Native | `android_native_data.is_adb_enabled` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_manual_timezone_or_adb` | 安装来源为 `manual` 且时区为 `0` 或 ADB 开启时为 `1.0` |

解释口径：

`manual` 安装来源本身不一定高风险，但如果同时出现 UTC 时区或 ADB 开启，就更像云机房、测试机架或批量部署环境。

### 4. ADB 与满电组合

相关字段：

| 层 | 字段 |
|---|---|
| Native | `android_native_data.is_adb_enabled` |
| Native | `android_native_data.battery_level_pct` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_adb_full_battery_signal` | ADB 开启且电量大于等于 `97%` 时为 `1.0` |

解释口径：

ADB 常开且长期接近满电，符合测试机架、自动化真机群控或云真机环境的物理特征。

### 5. 官方安装来源与核心完整性通过

相关字段：

| 层 | 字段 |
|---|---|
| WebView | `webview_data.installer_package` |
| Native | `android_native_data.sensor_total_count` |
| WebView | `webview_data.jsbridge_injected` |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_official_installer_core_pass` | 安装来源近似官方，传感器数量不少于 10，且 JSBridge 注入成功时为 `1.0` |

解释口径：

该特征代表一个较强的低风险组合：安装来源合理，Native 设备完整，WebView 桥接正常。

### 6. 三端平均一致性分

相关字段：

该特征综合以下信号：

| 信号 |
|---|
| Native-Web 型号/UA 匹配强度 |
| Native-Web Android 版本匹配 |
| Native-Web 屏幕一致性分 |
| Native-Web GPU 家族匹配分 |
| WebView-Web Chrome 主版本匹配 |
| JSBridge 注入状态 |

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_mean_match_score` | 上述六类信号取非负值后求平均 |

解释口径：

该特征提供一个全局自洽度指标。它不是单一规则，而是对多个跨层互证关系的聚合。

### 7. 一致性失败计数

相关字段：

该特征统计所有名称以 `_match`、`_pass`、`_consistent_10pct` 结尾，且值为 `0.0` 的一致性检查数量。

生成特征：

| 特征 | 规则 |
|---|---|
| `consistency_tri_layer_failure_count` | 多项一致性检查失败的计数 |

解释口径：

单个不一致可能来自正常系统差异、权限限制或采集误差；多个不一致同时出现，则更能说明设备身份链条存在系统性矛盾。

## 五、论文/答辩中的表达建议

可以将上述规则概括为三句话：

1. 原始三端指纹不是简单拼接，而是存在可对齐的语义锚点，例如型号、系统版本、屏幕、DPR、GPU、WebView provider、JSBridge 和安装来源。
2. 系统通过宽松语义匹配把这些锚点转换成可计算的一致性特征，既保留跨层互证能力，又避免严格字符串匹配带来的误判。
3. 随机森林端侧模型学习的是这些一致性特征与风险标签之间的组合关系，从而实现对规则知识库的轻量压缩。

可以用于论文中的表述：

> 跨层一致性特征并不要求三端字段完全相同，而是根据不同层的表达方式建立语义映射。例如 Native 层的物理屏幕需与 Web 层逻辑屏幕和 DPR 共同计算，Native 层硬件族需与 WebGL renderer 的 GPU 家族进行宽松匹配，WebView provider 版本需与 Web UA 中的 Chrome 主版本对齐。通过这种方式，系统将原始设备指纹中的隐式关系转化为显式数值特征，使轻量模型能够学习设备身份自洽性与风险评分之间的关系。

## 六、局限说明

这些规则是面向当前 HybridGuard 原型和当前数据集设计的工程规则，不是通用设备识别标准。后续如果扩展到更多厂商、浏览器内核或 App 宿主环境，需要继续补充硬件族映射、WebView token 规则、安装来源白名单和异常 UA 模板。

此外，当前规则刻意采用宽松匹配，是为了降低误伤。例如屏幕高度允许状态栏/导航栏误差，GPU 族允许 MediaTek 对 Mali/PowerVR 的多对一关系。答辩时应强调：宽松匹配不是降低判别力，而是为了让跨层比对更符合真实移动端系统的表达差异。
