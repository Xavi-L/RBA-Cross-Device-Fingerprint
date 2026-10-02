# 资源关系语义核对

本轮实现一个内存关系模板，拒绝 CPU 跨层关系模板。参数在新模型训练及 144/117 条评价之前固定；不拟合比例、容差或内存阈值。这里的关系偏离是研究候选信号，不是官方定义的攻击证据。

## 字段实际含义

| 字段 | 表面与采集口径 | 单位与限制 |
|---|---|---|
| `app.android_native_data.memory_layer.total_memory_gb` | Native：`ActivityManager.getMemoryInfo` 后的 `MemoryInfo.totalMem` | 采集代码除以 `1024³`，实际为 GiB，名称中的 gb 不代表十进制 GB。它是内核可见总内存，排除部分内核以下固定分配；不是零售标称 RAM，也不是剩余空闲内存。 |
| `app.web_data.navigator_layer.device_memory` | Web：同次 App WebView 的 `navigator.deviceMemory` | GiB 量级的粗粒度暴露值，会舍入、裁剪；探针 `nav.deviceMemory || 0` 的 0 不能当真实零内存。 |
| `app.web_data.navigator_layer.hardware_concurrency` | Web：同次 `navigator.hardwareConcurrency` | 对用户代理潜在可用的逻辑处理器数量；浏览器允许下调。已有 Native/Host 没有同口径数量参照。 |

仓库依据：`ExpandedFingerprintCollector.kt:35-38,106-110,451`；`web_probe/canonical_web_probe.js:359-360`；`expanded_v2_field_catalog.csv:17,20,41-44,119,121`。以上 Kotlin 文件位于 `android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/`，字段目录在同项目 `src/main/assets/`。

官方依据：[Android MemoryInfo.totalMem](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo#totalMem) 区分内核总量和 `availMem`；[W3C Device Memory](https://www.w3.org/TR/device-memory/) 定义近似内存和实现相关边界；[HTML hardwareConcurrency](https://html.spec.whatwg.org/multipage/workers.html#dom-navigator-hardwareconcurrency) 允许用户代理因资源或隐私限制暴露较低数量。这里不把上述 API 名称误解为精确物理硬件值。

## 新模板：Web 内存超出 Native 的二次幂上包络

ID：`MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE`，版本 `mtc-resource-relations-v1`。真实表面为 `native84 + app_web67`；信号组仍为 `memory_capacity`，没有额外排序分或强制入选。

记 Native 内核总量为 N GiB，Web 暴露量为 W GiB，固定包络为 `E(N)=2^ceil(log2(N))`，即不小于 N 的最小二次幂。实现用二进制 `frexp/ldexp`，避免浮点对数把恰好二次幂的边界移错；无经验 epsilon。

- **T（已观察偏离）**：两项是同次 App 记录中的有效正有限数，N≥0.25 GiB，且 W>E(N)。即使记录有正常依据，也保留 T。
- **F（满足这个宽边界）**：有效域内 W≤E(N)。不要求 W=N，也不要求 W 精确等于量化后的桶；降低 Web 暴露值始终允许。
- **U（不足或不适用）**：字段缺失、质量不足、布尔/字符串/非有限类型、0/-1 等无效值，或者 N<0.25 GiB 的本研究未覆盖域。原因分开保存。
- **FAILED**：调用端未提供有效的同次 App 绑定。绑定器检查原始会话引用；单凭一个字段的值不能证明绑定。

这个上包络来自量化机制，而非本批数据分位数。[Chromium 131 的实现](https://raw.githubusercontent.com/chromium/chromium/131.0.6778.69/third_party/blink/common/device_memory/approximated_device_memory.cc) 第 19、32–54 行先取系统内存的整数 MiB，再在相邻二次幂中就近舍入，最后可向下裁剪。就近舍入不会越过这里采用的较宽上包络。[Chromium Linux 系统内存读取](https://raw.githubusercontent.com/chromium/chromium/main/base/system/sys_info_linux.cc) 第 25–47 行使用系统物理页数与页大小；Android/Bionic 的 [sysconf](https://raw.githubusercontent.com/aosp-mirror/platform_bionic/master/libc/bionic/sysconf.cpp) 第 183 行将相应读取委托给 `get_phys_pages`。这支持同一 Android 内核参照下的保守关系；它不证明两个字段构成独立硬件认证。

本实现不固定 8 GiB 上限，因此 32 GiB Native / 8 GiB Web 可满足；6 / 8 也满足。更低的隐私暴露或低端模式值不触发。N≥0.25 GiB 是事先声明的窄域，用于避开极小内存设备与实现下限的关系；不是从本轮评价学习的参数。

公开源码解释原理，不等于逐个 OEM WebView 二进制复现。厂家内核/浏览器改动、不同内存命名空间、未来上调的隐私下限或非同一物理上下文都可能破坏上述域假设。已有记录没有这些完整观测，不能凭报警反推它们存在，也不能据此偷偷转 U；真实正数超包络仍统计为正常侧候选触发。最低限度的后续核对是保留同次 Native 原始字节总量、实际 WebView 版本及内核/容器内存上下文，不是继续放宽经验比例。

## 与曾经误报的旧比例有何实质区别

旧 `V2REL.MEMORY_WEB_NATIVE_RATIO` 见 `hybridguard_agent/research/rule_learning_v2/relations.py:41-46,100-103`，训练侧为 `W/N` 拟合 Q25/Q50/Q75。历史 `B_development/REPORT.md:121-123` 已明确：某折训练阈值 `W/N>0.8283140429538769`，把正常 Native≈1.934 GiB、Web=2 的比例≈1.034 判为偏离，而另一正常环境 Native≈2.415 GiB、Web=2 的比例≈0.828。因此旧关系把正常内存规模差异带入报警，不支持把比例超过 1 当作攻击。

新模板不改名复用该阈值，也不要求恢复某个准确比值。上述两条正常反例均为 F；2.415 / 8 才超出固定量化上包络。是否有选择价值由相同 B 训练要求决定。

## 仅 discovery 的输入核验

按上一轮 `SETTINGS.json` 的原 630 条 discovery 代表记录定向读取，未读取 144/117 条的新模型评价。Native/Web 内存共 579/630 可比较，均满足包络；51/630 为 Web `device_memory=0.0`，历史质量已标记 `ambiguous_sentinel`，保持 U。候选可评估比例为 579/630=91.90%，是否满足训练支持与选择由正式运行器判定。

保留的具体正常差异例：`mtc-pair-hgpair-v1-b190cc28648e1470b2d70e4a`，Native=1.7889137268066406 GiB、Web=2；P1 `paired_244.jsonl:175`，原 App 行 214。`mtc-pair-hgpair-v1-d76c3d7c1cb898c6f2b3417e`，Native=1.7886772155761719 GiB、Web=2；P1 行 176，原 App 行 213。两项均明确 F，没有把 Web>Native 改成 U。

## 未实现 CPU 模板

字段目录、`ExpandedFingerprintCollector.kt:92-101` 与旧 `rule_learning_v2/field_inventory.py` 相互印证：只有 ABI、支持 ABI 数组、架构和硬件字符串，没有物理核数、在线逻辑 CPU 数量或当前进程可用处理器数。ABI 不是数量；不能靠型号查表补齐，也不能要求浏览器值等于整机核数。资源模板只新增一个，不凑第二个。

最小补采应同时保存系统在线逻辑处理器数、宿主进程 affinity/可用 CPU 集合，以及 Web 暴露值的同次时刻和浏览器限制上下文；`availableProcessors` 本身也不能冒充物理核数。本轮不启动补采。
