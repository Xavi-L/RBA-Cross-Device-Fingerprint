# Hybrid App 三端跨端一致性测试规则

## 采集与判定

1. 同一条三端记录中的 Native、WebView 和 Web 数据必须由同一个会话组装。任一层不是该会话的原始采集结果时，不得参与三端一致性判断。

2. 字段因系统不支持、权限拒绝、运行错误、超时或不适用而无法获得时，该字段对应规则记为“未评估”，不得把缺失值伪造为一致，也不得直接当作不一致。明确采到 `jsbridge_injected=false` 的情形除外，应按桥接失败处理。任一一致性异常只表示观察到跨端关系异常，不能单独等同于攻击、欺诈或设备身份结论。

## Native 与 Web

3. Native 设备身份应能在 Web User-Agent 中得到宽松互证。设备型号直接出现时为强匹配；产品代号直接出现时也为强匹配；仅出现主板代号、品牌或厂商时只能作为弱证据，不能单独视为强匹配；User-Agent 仅声明 Android 而没有设备身份线索时同样只能作为弱证据；User-Agent 不像 Android 移动环境时视为不匹配。

4. Native 系统版本与 Web User-Agent 中解析出的 Android 主版本必须相同。任一侧无法解析版本时记录为未评估，不把它解释为版本一致或版本冲突。Android 16 与 API Level 36 均为合法版本，不得仅因版本较新而判定异常。

5. Native 物理屏幕宽高应与 Web 逻辑屏幕宽高乘以设备像素比相对应。比较时必须同时尝试横屏和竖屏，采用误差较小的方向；宽高中的最大相对误差不超过 10% 时视为一致。状态栏、导航栏和安全区造成的可用高度差不得按严格像素相等处理；最大相对误差达到 20% 或以上时，屏幕一致性分为 0。

6. Native CPU ABI 与 Web platform 必须属于同一处理器家族。`arm64` 或 `aarch64` 归为 arm64；`armeabi` 或 `armv7` 归为 arm；`x86` 或 `i686` 归为 x86；Web 侧的 `aarch64`、`armv8`、`arm64`、`arm`、`i686`、`x86`、`Win32`、`Win64` 按相同家族映射。两侧都能识别时才作一致性判断；任一侧无法识别时记为未评估。

7. Native 硬件家族与 WebGL GPU 家族应满足移动硬件映射：Qualcomm/qcom 应对应 Adreno 或 Qualcomm；MediaTek 应对应 Mali 或 PowerVR；Huawei/Kirin 应对应 Mali、Maleoon 或 Huawei；Samsung/Exynos 应对应 Mali、Xclipse 或 Samsung。真机硬件侧同时出现 SwiftShader、Apple ANGLE 或 Headless 等软件/桌面渲染标识时，视为强冲突。模拟器硬件与软件渲染只可作为模拟器线索，不能作为真机硬件一致性通过。

8. Web User-Agent 同时声明 `Android` 和 `Mobile` 时，`maxTouchPoints` 必须大于 0；移动 User-Agent 与零触点组合视为不一致。

9. Native 总内存与 Web `deviceMemory` 只进行软比较，不要求数值完全相等。两者差值为 0 GB 时内存一致性分为 1；分数随差值线性下降；差值达到或超过 4 GB 时分为 0。内存差异本身不得单独定性为异常。

10. Web User-Agent 出现 `Windows NT`、`Win64`、`Headless` 或 `python-requests` 时，与移动 Native 身份冲突。

## Native 与 WebView

11. Native 设备型号必须直接出现在 WebView 的 system HTTP agent 中；未出现时，Native 与 WebView 的设备型号互证失败。

12. Native 系统版本与 WebView system HTTP agent 中解析出的 Android 主版本必须相同。任一侧无法解析版本时记为未评估，不按版本冲突处理。

13. App WebView 采集必须成功注入 JSBridge。明确未注入时，视为 Native 与 WebView 宿主链路断裂。

14. WebView 宿主包名必须以 `com.example.hybridguard` 开头；不满足此前缀时，视为非预期 App 宿主。

15. 安装来源包含 `packageinstaller`、`browser` 或 `vending` 时，记为常规安装来源；安装来源严格等于 `manual` 时，记为辅助环境异常。`manual` 单独出现不得直接定性为攻击。

16. `is_debuggable=true` 且 `is_cleartext_traffic_permitted=true` 同时成立时，记为开发或测试环境张力；任一项单独成立不得直接定性为异常。

## WebView 与 Web

17. WebView provider 版本的主版本必须等于 Web User-Agent 中 Chrome 或 Chromium 的主版本；小版本差异不比较。任一主版本无法解析时记为未评估。

18. App WebView 场景下，Web User-Agent 包含 `; wv` 或 `Version/4.0` 时可加强 WebView 运行时一致性；缺少该标识只作为辅助异常，不能单独定性。

19. WebView 容器与 Web 运行时完整自洽必须同时满足三项：JSBridge 已注入、Web User-Agent 同时包含 `Android` 和 `Mobile`、Web User-Agent 包含 WebView 标识。三项中任一项不满足时，该三联一致性不通过。

20. App WebView 的 Web User-Agent 出现 `python-requests` 时，视为非浏览器脚本客户端，不得认定为正常 WebView 运行时。

## 三端组合

21. 三端核心完整性通过的条件是：Native 传感器总数不少于 10，且 WebView 的 JSBridge 已注入。两项同时满足才可记为核心完整性通过。

22. Native 传感器总数低于 10，或明确采到 JSBridge 未注入时，视为核心完整性失败；该失败为硬性失败，不得被其他低风险或一致性通过信号抵消。

23. 安装来源为 `manual` 且 Web 时区偏移为 0，或安装来源为 `manual` 且 Native ADB 已开启时，记为云机房、测试机架或批量部署的组合线索；该组合不得单独等同于攻击。

24. Native ADB 已开启且电量不低于 97% 时，记为测试机架、自动化真机群控或云真机的组合线索；该组合不得单独等同于攻击。

25. 常规安装来源、传感器总数不少于 10、JSBridge 已注入三项同时满足时，记为较强的低风险三端组合。

26. 全局三端一致性分由以下六项的非负得分取平均：设备身份与 Web User-Agent 的匹配强度、Native 与 Web 的 Android 主版本一致性、屏幕与设备像素比一致性、硬件家族与 WebGL GPU 家族一致性、WebView provider 与 User-Agent 的 Chrome 主版本一致性、JSBridge 注入状态。无法判断的项目按 0 参与该平均。

27. 一致性失败计数只统计既有“匹配”“通过”或“10% 屏幕一致”检查中结果为不通过的项目。多个不同层级的检查同时失败时，应保留每一项失败，不得合并为单一异常。
