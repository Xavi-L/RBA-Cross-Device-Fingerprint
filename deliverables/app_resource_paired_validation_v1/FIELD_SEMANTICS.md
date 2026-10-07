# 资源字段语义与本次版本

登记日期：2026-10-07。公式和目标先登记于 SETTINGS.json／PLAN.json，再执行正式矩阵与MTC条件评价。以下区分规范语义、版本实现和本次实测，不把新规范倒推为所有旧版本的行为。

- [W3C Device Memory](https://www.w3.org/TR/device-memory/) 将数值定义为近似容量，允许实现设定上下限；该接口需要安全上下文。它不是精确物理RAM，规范并未保证所有版本永久以8为上限。
- [HTML 并发硬件能力](https://html.spec.whatwg.org/multipage/workers.html#concurrent-hardware-capabilities) 允许用户代理报告可用逻辑处理器数量，也允许因资源限制或减少指纹暴露而降低。两个端点不相等本身不能证明干预。
- 实测 Chrome／WebView 均为 **134.0.6998.135**。[该版近似内存实现](https://raw.githubusercontent.com/chromium/chromium/134.0.6998.135/third_party/blink/common/device_memory/approximated_device_memory.cc) 从系统内存得到最邻近二次幂，并在该版将结果截到8；[getter](https://raw.githubusercontent.com/chromium/chromium/134.0.6998.135/third_party/blink/renderer/core/frame/navigator_device_memory.cc) 读取这个近似值，[IDL](https://raw.githubusercontent.com/chromium/chromium/134.0.6998.135/third_party/blink/renderer/core/frame/navigator_device_memory.idl) 标记SecureContext。[同版CPU getter](https://raw.githubusercontent.com/chromium/chromium/134.0.6998.135/third_party/blink/renderer/core/frame/navigator_concurrent_hardware.cc) 调用 `base::SysInfo::NumberOfProcessors()`。以上是所测版本依据，不泛化到MTC所有浏览器。
- v16 `ExpandedFingerprintCollector.kt` 通过 `ActivityManager.MemoryInfo.totalMem / (1024³)` 生成 `total_memory_gb`，单位实际为GiB。正式适配继续要求原状态和质量，不用可用内存或其他设备的内存替代。
- 原字节 `canonical_web_probe.js` 使用 `nav.deviceMemory || 0` 和 `nav.hardwareConcurrency || 0`。因此正式raw中的0可能代表不可观测；条件仍判U，不能补F。独立观察日志另外保留属性存在性、直接读取状态、原值、origin与isSecureContext，不替代正式采集。

本次自有只读API36.1实例原有约2GiB RAM、1 CPU；未加 `-memory`／`-cores`，未修改基础AVD。真实正式App页面是 `file:///android_asset/expanded_probe.html`（页面origin记为`file://`或实际返回值），Browser页面是 `http://127.0.0.1:8001/browser-probe.html`，通过既有ADB reverse连接本地后端。是否属于安全上下文以每个实际文档的 `isSecureContext` 为准，不从about:blank推断。

六条件的真实依赖在 `conditions.py::DEPS/BINDINGS`：App内存关系仅Native＋App Web；跨端上界仅Native＋Browser及当前配对；内存相等和CPU相等仅两端Web；两个8阈值各只读单端。Native最小范围0.25GiB，上界是覆盖N的最小二次幂，比较严格大于。bool、非有限数、非正值、CPU非整数、缺失／runtime_error／默认0为U；绑定错误为FAILED。有效正常反例仍为T，不改变适用范围以消除它。

本轮原App资源配置经 CONFIGURATIONS.json 核对为内存16＋CPU48；Browser资源过程是新镜像配置。目标4保持原样：若本来为4则记NO_EFFECT，若原值8则记向下修改；本次实测原值2，属于向上修改。`R_WEB_MEMORY_DIFFERENCE`和`D_CPU_DIFFERENCE`仅为差异诊断。上界以内的修改可能漏检，两个端点也可能同时受改动；本批仅覆盖登记的单端控制。
