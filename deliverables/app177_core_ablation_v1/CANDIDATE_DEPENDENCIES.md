# 候选依赖与固定移除

原50项基础候选全部只读取App Web测量（含其原始Web观察模块），再加旧同Web视口、Native↔Web内存、Native↔Web时区3个模板。逐折展开数量为65、65、56；不是177个字段全部进入学习器。

源代码检查路径：`mtc_reselection_candidates` → dependency-only `matrix`，语言／webdriver各自runtime input，WebGL source gate，三个关系计算器。Native／Host测量不会参与基础50项的归一化或门控。新Host几何未加入。

本轮新v14/v15/v16编译入口按实际操作数投影，移除旧全177字段完整性前置检查；逐候选保留原测量核。378条×53模板的值／可用性／执行状态逐一一致。未选条件的缺测不会扩大模型失败范围。

|模板|测量层|关系族|Web-only删除|去内存删除|去时区删除|
|---|---|---|---|---|---|
|CAT:NW-006|app_web67|base|否|否|否|
|CAT:NW-007|app_web67|base|否|否|否|
|CAT:OFFDER-TOUCH-001|app_web67|base|否|否|否|
|CAT:P3-COLOR-APP|app_web67|base|否|否|否|
|CAT:WVWEB-004|app_web67|base|否|否|否|
|CONTROL:app.web_data.audio_layer.audio_context_supported:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.execution_layer.local_storage_available:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.execution_layer.session_storage_available:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.graphics_layer.webgl2_supported:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.cookie_enabled:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.online:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.network_api_layer.save_data:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.permissions_layer.permissions_api_supported:EQ:True|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.user_agent:EQ:script_client|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.user_agent:EQ:desktop_or_headless|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.user_agent:EQ:android_browser|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.user_agent:EQ:android_webview|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.platform:EQ:android|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.platform:EQ:mobile_or_ambiguous|app_web67|base|否|否|否|
|CONTROL:app.web_data.navigator_layer.platform:EQ:desktop|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.audio_layer.audio_output_latency|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.audio_layer.audio_sample_rate|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.automation_surface_layer.mime_types_count|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.automation_surface_layer.plugins_count|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.execution_layer.timezone_offset|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.font_layer.font_probe_count|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.graphics_layer.webgl_extensions_count|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.graphics_layer.webgl_max_texture_size|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.navigator_layer.device_memory|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.navigator_layer.hardware_concurrency|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.navigator_layer.max_touch_points|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.network_api_layer.downlink_mbps|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.network_api_layer.rtt_ms|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.avail_height|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.avail_width|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.color_depth|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.device_pixel_ratio|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.inner_height|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.inner_width|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.orientation_angle|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.outer_height|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.outer_width|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.pixel_depth|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.visual_viewport_height|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.visual_viewport_scale|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.screen_layer.visual_viewport_width|app_web67|base|否|否|否|
|UNFITTED_CONTROL:app.web_data.navigator_layer.languages|app_web67|base|否|否|否|
|RSR-WEBDRIVER-STATE-v1|app_web67|base|否|否|否|
|RSR-LANG-FIRST-v1|app_web67|base|否|否|否|
|RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1|app_web67|base|否|否|否|
|REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1|app_web67|same_web_viewport|否|否|否|
|MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE|app_web67,native84|memory_relation|是|是|否|
|MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS|app_web67,native84|timezone_relation|是|否|是|

精确操作数、状态/适用域、元信息、正负极性和每折数值派生项见 [CANDIDATES.json](CANDIDATES.json)。四组都从掩码后完整池重选；不是删除Full成品规则。Web-only保留真正同Web内部关系。

原WebGL1固定编译器的source gate只登记v14；本轮没有伪装v15/v16，旧MTC v9/v11也没有原始WebGL查询。该候选在新版本材料可为U，在MTC下因90%准入要求被排除，不能用GPU名称或新几何快照补造。
