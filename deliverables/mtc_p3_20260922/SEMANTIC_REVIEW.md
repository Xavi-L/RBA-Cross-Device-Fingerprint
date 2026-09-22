# P3 独立语义预审（2026-09-22）

本预审只使用字段目录、采集器代码、旧语义目录和重新访问的官方一手资料；未读取 MTC 指纹行、发现／开发结果或保留验证集。它限定可执行候选的语义范围，不给出任何候选的经验支持度，也不以恢复旧规则数量或旧实验效果为目标。实际准入由 P3 运行目录记录，不能把本表中的建议等同于已晋级规则。

来源登记见 `hybridguard_agent/config/mtc_p3_semantic_sources.v1.json`。`official_document` 只表示官方文档中的字段语义；由这些语义推出的项目关系标 `official_derived_semantic_rule`；使用发现集拟合的关系标 `device_mined_rule`，即使同时引用官方资料。采集器赋值带来的恒等式单列 `collector_implementation_invariant`，不计为发现了新的独立设备规律。

## 公共准入边界

- 每个依赖字段必须存在、类型正确、状态为 `observed`，且通过字段专用有效性检查。`FieldStatusReporter.kt:8` 明确说明零、空字符串和默认值仍可被标记为 observed；不能用状态代替有效性检查。
- 数值比较区分布尔与数值，允许 `8` 与 `8.0` 等价；拒绝非有限值。空值、unsupported、timeout、runtime_error、不可识别标识或默认哨兵进入 unknown／不适用分母，不能当一致。
- 本文路径省略 P1 顶层表面前缀：App 字段实际为 `app.<field>`，Browser 只有 `browser.web_data.*`。不得把 Browser 字段覆盖 App 同名字段。
- 经验支持度使用 P2 的可评估唯一分组：全局发现／开发至少 30／10 组和 3／2 厂商；限定范围至少 10／5 组。门槛只是工程筛选，不能自动证明安全判别力。无独立攻击标签时，冲突与差异都不能称为假阳性、漏报或攻击。
- 采集器代码验证的是当前源码语义。版本变化与 APK 实际行为必须由版本清单和样本证据约束；不能从当前代码推断所有历史版本完全相同。

## 1. OS／UA／WebView 容器

字段：`android_native_data.build_fingerprint_layer.{os_version,os_api_level}`；`webview_data.kernel_container_layer.{default_ua_native,system_http_agent,webview_provider_major,webview_provider_version}`；`webview_data.webview_settings_layer.settings_user_agent`；两端 `web_data.navigator_layer.user_agent`。

`ExpandedFingerprintCollector.kt:76` 取 Android Build 版本，`:213` 起取当前 WebView 包信息，API 26 以下 provider 字段不适用。`MainActivity.kt:160` 在加载 probe 前保存同一 WebView 的 settings UA，当前源码没有设置自定义 UA。默认 UA 与实际 settings UA 仍是不同语义：API 明确允许应用覆盖 UA。[WebSettings](https://developer.android.com/reference/android/webkit/WebSettings#setUserAgentString(java.lang.String))；[WebView provider](https://developer.android.com/reference/android/webkit/WebView#getCurrentWebViewPackage())。

官方当前页面写明 WebView 默认 UA 从 Android 17 起简化；外部 Chrome 已自 107 简化。固定 Android 10／K 字段不代表真实 OS。页面发表于 2024 年但内容已经更新，不能沿用旧笔记的 Android 16 阈值。API 与版本映射若用于代码，应由可追溯版本契约提供，不能只靠 UA 推断。[Android WebView UA reduction](https://android-developers.googleblog.com/2024/12/user-agent-reduction-on-android-webview.html)。

有限候选：

| 模板 | 关系与执行边界 | 来源／处置 |
|---|---|---|
| UA-settings-runtime | App settings UA 与 App JS UA 精确相等，限同一实例且采样期间未改 settings | 官方派生＋项目生命周期前提；不适用于 Browser |
| UA-provider-major | 解析 provider version 首段，与 provider_major 对齐 | 采集器内部自洽；不能当独立跨层增益 |
| UA-provider-runtime | provider_major 与 App UA 的 Chrome 主版本兼容；要求非空、可解析、默认／未覆盖 UA 链有证据 | 官方派生候选；厂商包版本格式不能默认等于 Chromium 版本 |
| UA-OS-compatibility | Native OS 与 App UA 的 Android token 相容，先区分 reduced/default/custom；reduced 不作 OS 精确断言 | 有条件派生候选；Browser 独立分支，不能强制等版本 |

`system_http_agent` 来自 Java 系统属性；它不是当前 WebView renderer 的 UA。旧 OFFDER-OS-002 的直接主版本关系必须重新评估。UA desktop／headless 标记也可能来自授权调试或站点兼容设置，只能作为上下文，不能直接提供攻击标签。

## 2. 屏幕／DPR

最重要的字段语义修正：名为 `android_native_data.screen_display_layer.screen_resolution_physical` 的值，实际来自 `context.resources.displayMetrics.widthPixels/heightPixels`（采集器 `:40`、`:113`），应解释为 **App 可用显示区域像素尺寸**。它不是物理面板原生分辨率，也不等同于 mode。`screen_mode_physical_width/height` 来自 `Display.Mode`，API 23+，表示当前模式分辨率；官方明确说 UI 缩放可使 App 可用尺寸不同于 mode。[DisplayMetrics](https://developer.android.com/reference/android/util/DisplayMetrics#widthPixels)；[Display.Mode](https://developer.android.com/reference/android/view/Display.Mode#getPhysicalWidth())。

两端 `web_data.screen_layer.screen_resolution_logical` 来自 `screen.width/height`，单位 CSS px；`device_pixel_ratio` 是比值。DPR 包含 page zoom，visual viewport scale 是另一维度；`inner_*`、`outer_*`、`avail_*`、`visual_viewport_*` 对应不同区域。[CSSOM View](https://drafts.csswg.org/cssom-view/#dom-window-devicepixelratio)。

候选限为：App reported display 尺寸与各 Web 表面的 `CSS size × DPR` **分轴残差诊断**；必要时明确旋转归一，且保留原方向，不能排序后隐去所有方向差异。发现／开发可学习有界残差，但不能通过反例删除机型、放大容差或把高度改成宽度来追逐旧告警数。未知 page zoom、分屏、折叠状态、显示模式时，属于经验条件不足，不得称物理恒等式。`densityDpi / 160` 与 DPR 也只是受环境约束的候选；`xdpi/ydpi` 是另一物理量。API 34+ 自适应字体缩放使 `scaledDensity == density × fontScale` 不能当全局定律。[DisplayMetrics scaledDensity](https://developer.android.com/reference/android/util/DisplayMetrics#scaledDensity)。

## 3. GPU 语义与能力

字段：`android_native_data.graphics_layer.{native_gpu_vendor,native_gpu_renderer,egl_vendor,egl_renderer,gles_version}`；两端 `web_data.graphics_layer.{webgl_vendor,webgl_renderer,webgl_max_texture_size,webgl_max_viewport_dims,webgl_aliased_line_width_range,webgl_extensions_count,webgl2_supported}`。

采集器 `:391–396` 将同一 `glRenderer` 同时写入 native_gpu_renderer 和 egl_renderer；二者相等只证明赋值一致，不是两个独立 API 的佐证。`egl_vendor` 是 EGL 实现厂商，不应要求等于 GL_VENDOR。Web 只在 `WEBGL_debug_renderer_info` 扩展可用时读取 unmasked 字符串；扩展缺失不会自动使整个 probe 状态失败。官方允许隐藏 renderer/vendor，因此空、默认字符串或无法分类的结果必须保留 unknown。[Khronos 扩展规范](https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/)。

有限候选是经过明确词典归一的 Native／App Web／Browser GPU 家族兼容表。词典版本、unknown、ANGLE 包装、软件后端必须独立记录；不能只 substring 相同就证明同 GPU，也不能把 ANGLE 或 renderer 文本不同当攻击。能力上限、扩展数量受上下文和实现影响，适合作同容器条件经验关系，不能全局相等。

**新发现的探测缺陷：** `canonical_web_probe.js:321–324` 在同一 canvas 先请求 WebGL1，再请求 WebGL2。HTML 规定 canvas 已具有不同 context 类型时 `getContext` 返回 null。因此成功建 WebGL1 后的 `webgl2_supported=false` 可能由探测顺序造成，不能用来推断真实设备不支持 WebGL2。该字段本轮只记录探测结果／缺陷，不纳入能力规则；修复应在新的 probe 版本另行验证，不改写当前数据。[HTML getContext](https://html.spec.whatwg.org/multipage/canvas.html#dom-canvas-getcontext-dev)。

## 4. App Web–Browser 共同属性

有限候选字段为 `web_data.navigator_layer.{language,languages,max_touch_points,platform,hardware_concurrency}` 和 `web_data.execution_layer.{timezone_id,timezone_offset}`。两容器采用相同 JS 逻辑也不意味着同样的浏览器设置、隐私配置或内核行为。

语言可作 BCP 47 标记的有说明归一，不能丢弃区域后假装精确一致；浏览器独立语言选择与 Android App locale 可以不同。`languages` 是有序偏好表，除非关系明确定义为集合包含，否则不能任意排序消除反例。max_touch_points=0 是可能的真实值，不能通用当缺失。platform 是暴露的兼容字符串，不是 CPU ABI 认证。

hardwareConcurrency 表示 user agent 潜在可用逻辑处理器数量，允许因资源限制或反指纹而降低；两容器可以合法不同。缺失被本 probe 写成 0，0 应标 ambiguous sentinel；1 不应标哨兵。可测经验兼容／差异，不能强制等于硬件核数。[WHATWG hardwareConcurrency](https://html.spec.whatwg.org/multipage/workers.html#dom-navigator-hardwareconcurrency)。

时区有一个额外边界：Native `native_timezone_offset_min` 用 `TimeZone.rawOffset/60000`，是标准时偏移，不含夏令时；Web `timezone_offset` 用当前 `Date.getTimezoneOffset()`，符号相反且采用当日时区规则。因此 `native_offset == -web_offset` 不能全局成立。App Web 与 Browser 之间的当前 offset 可作为有时间／设置前提的经验关系；ID 字符串需考虑合法别名，不能仅文本不同定冲突。[Android TimeZone](https://developer.android.com/reference/java/util/TimeZone#getRawOffset())；[ECMAScript Date offset](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.prototype.gettimezoneoffset)。

## 5. deviceMemory／能力

字段为 `android_native_data.memory_layer.total_memory_gb` 与两端 `web_data.navigator_layer.device_memory`。Native 除数为 1024³，实际单位 GiB。W3C 定义 Web 值是粗量化的内存能力，具有实现自定且可随时间调整的上下界，并要求 secure context；不能把它当精确可用 RAM，也不能把固定上限 8 GiB 当永久标准。[Device Memory API，2026-03-30 Working Draft](https://www.w3.org/TR/2026/WD-device-memory-1-20260330/)。

当前 probe 采用 `nav.deviceMemory || 0`；observed 的 0 不能用于拟合内存关系。App 页面是 `file:///android_asset/expanded_probe.html`，Browser 为不同 origin／上下文，能力可用性应逐样本按状态和有效值判断。可执行候选是限定实现与版本后的量化兼容区间／分段表，源类型必须包含 `device_mined_rule`。不得直接比较 Native 总RAM与 Web 值精确相等，不能把所有残差包进无限容差。未掌握实现上限时，保留描述性结果。

同一 `MemoryInfo` 中 `0 <= avail_memory_gb <= total_memory_gb` 可以单列为语义自洽候选。Native totalMem 是内核可访问内存，排除了部分内核以下固定预留，不必等于零售标称容量；availMem 也不等同于完全未使用的 free RAM。该关系即使成立也不证明 Browser 内存值正确。[ActivityManager.MemoryInfo](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo)。

## 6. 传感器结构

统一路径前缀为 `android_native_data.sensor_matrix_layer.`。源码 `:141–157` 从同一个 sensorList 派生 distinct sorted type list、名称数、非空厂商数和总数，可执行内部结构约束：`len(sensor_type_list) <= sensor_total_count`、`sensor_name_count <= sensor_total_count`、`sensor_vendor_count <= sensor_total_count`，数量均为非负整数且 type list 无重复。这些关系不需要从 MTC 拟合，属于项目实现自洽，不能当三条独立跨层设备发现。

`has_*` 使用 `getDefaultSensor`，而列表使用 `getSensorList(TYPE_ALL)`。官方返回默认传感器要求传感器存在且应用具备权限；列表还包含 wake-up 和 non-wake-up 实例。因此 **不允许无条件双向等价** `has_X == (type_X in list)`。较保守模板为 `has_X=true -> type_X in list`，并保留列表和默认传感器调用时序／实现边界；false 且类型存在不足以判为结构冲突。[Android SensorManager](https://developer.android.com/reference/android/hardware/SensorManager#getDefaultSensor(int))。

有限类型映射：accelerometer=1，magnetic_field=2，gyroscope=4，light=5，pressure=6，proximity=8，gravity=9，rotation_vector=11，step_detector=18，step_counter=19（使用 Android Sensor 常量）。某类传感器缺失本身不表示攻击，不预设“所有手机都有”的规则。

## 7. Canvas／Audio／fonts／plugins

两端比较字段：`web_data.graphics_layer.canvas_hash`、`web_data.audio_layer.{audio_hash,audio_sample_rate,audio_context_supported,audio_error}`、`web_data.font_layer.{available_font_hash,font_probe_count,font_probe_error}`、`web_data.automation_surface_layer.{plugins_count,plugins_hash,mime_types_count,mime_types_hash,plugin_probe_error}`。

Canvas 哈希来自固定绘制任务的 PNG data URL；不能把不同内核／字体／渲染栈的字节差异直接定为欺骗。字体探测是 22 个候选字体的宽度比较近似，`font_probe_count` 是检测命中的候选数量，不是系统字体总数。`0 <= font_probe_count <= 22` 是当前代码边界；可作 QC，但不是经验发现。有效空列表的哈希与空字符串失败值必须区分。

Audio probe 用实时 context 的 sampleRate（不可用时 44100）构造 OfflineAudioContext；改变采样率会改变任务。`audio_output_latency` 优先 outputLatency、回退 baseLatency，混合了两个延迟语义，不能作为同一硬件量比较。仅在相同算法、采样率、实现／版本、无错误时评估稳定性；仍不能预设跨端哈希相同。Web Audio 官方明确 DSP、重采样、舍入、编译与 CPU 实现差异可产生指纹差异。[Web Audio 隐私考虑](https://www.w3.org/TR/webaudio/#privacy-security)。

plugins/mimeTypes 不是真实插件安装清单；现代 HTML 为 PDF 支持定义了固定兼容暴露，旧实现又可能不同。跨端计数／哈希相同只能是候选稳定性关系，非独立设备身份；0 可能是合法空列表，也可能由不存在 API 的回退造成，需保留可用性不明，不能自动当攻击。[WHATWG NavigatorPlugins](https://html.spec.whatwg.org/multipage/system-state.html#dom-navigator-plugins)。

这一家族的默认结果为版本条件下的描述性稳定性报告；若必要条件或重复观测不足，保留 deferred，不强行晋级。

## 执行建议与交付边界

优先执行 UA settings→runtime、屏幕分轴残差、有限 GPU 家族、共同属性差异、内存量化和传感器单向结构模板。所有模板分别统计 evaluated／conflict／unknown／not_applicable，保留全部反例与版本环境；语义冲突不自动转换成风险分数。

明确拒绝的快捷规则：Native 面板=App显示=Browser视口；所有 UA Android 版本一致；Native RAM=deviceMemory；所有 renderer 文本一致；has_sensor 与列表成员双向等价；WebGL2=false 即不支持；所有跨端哈希应一致。此拒绝来自源码与官方语义，不来自本轮样本差异。

本预审未验证候选的经验效果，未修改采集器、原始数据、P1 快照、P2 切分或保留验证集。已有旧规则的处置必须引用新的执行结果；本文件不能充当旧结论仍有效的证明。
