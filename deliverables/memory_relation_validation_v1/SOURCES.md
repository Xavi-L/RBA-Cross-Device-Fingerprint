# 固定条件与来源说明

两个条件、2/4/8/16四个目标、每环境两轮和六个保存模型身份已在新采集前写入 `SETTINGS.json`。不训练、不学习阈值，不把 R_WEB8 拼入 B。

- **R_REL**：直接调用 `hybridguard_agent/research/mtc_resource_relations.py::evaluate`；N来自同次App的 `android_native_data.memory_layer.total_memory_gb`，W来自 `web_data.navigator_layer.device_memory`。Native代码以 `totalMem / 1024³` 计量，单位实际为GiB，含义是内核可见总量，非空闲内存或零售标称RAM。原关系依据和适用域完整保留在 `../mtc_relation_extension_v1/RESOURCE_REVIEW.md`。
- **R_WEB8**：本轮固定单字段对照，有效W严格大于8为T，否则F。有效性使用原资源关系中Web操作数的规则：必须有字段、状态observed、质量observed_value、非布尔的正有限数值。缺失、默认0、-1、字符串、非有限数等为U。Native缺失不影响R_WEB8；原始记录无法读取或来源绑定失败属于执行FAILED。

## WebView版本与8的含义

实际本地环境在 `runs/*/environment.json` 中由 `dumpsys webviewupdate` 登记，必须与既有环境 API29/API30 的91.0.4472.114、API36的134.0.6998.135相符，否则该环境停止，不偷偷替换。App沿用v14（1.6.7-expanded-v2.2-webgl1），不构建或修改APK。

2026-10-02定向读取的两个对应Chromium源码版本均先取系统内存、按相邻二次幂就近舍入，并将大于8的暴露值裁剪为8：

- [Chromium 91.0.4472.114](https://raw.githubusercontent.com/chromium/chromium/91.0.4472.114/third_party/blink/common/device_memory/approximated_device_memory.cc)，21、31—59行。浏览工具缓存未命中后通过HTTP读取同一官方镜像路径，明确核对了58—59行的限制。
- [Chromium 134.0.6998.135](https://raw.githubusercontent.com/chromium/chromium/134.0.6998.135/third_party/blink/common/device_memory/approximated_device_memory.cc)，19、28—54行。
- [W3C Device Memory草案](https://www.w3.org/TR/device-memory/#computing-device-memory-value) 将上下界留给实现，并明确可随时间和设备类型变化。因此8是这些源码版本中的实现值，也是本轮提前固定的对照阈值；不是所有浏览器、年代或OEM二进制的永久保证。本轮没有反编译验证每个WebView APK。
- [Android MemoryInfo.totalMem](https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo#totalMem) 和仓库 `ExpandedFingerprintCollector.kt` 支持Native字段口径；旧关系参数未因新数据改动。

## 现有数据与新批次的界限

旧378条受控记录通过原 `mtc_relation_sources.load_controlled_sources` 沿原始引用读取；891条MTC记录使用上一轮P2成员、630/144/117划分、P1观测及正常采集依据。常规采集没有本研究目标篡改，调试/自动化组件本身不改变这一依据。历史标签不覆盖。MTC不是新独立盲测。

MTC逐条结果的 `source_view/source_line` 指向 `hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/<source_view>.jsonl`；`app_raw_line` 指向 `backend_server/collection_backups/mtc_final_20260922/sources/raw_expanded_payloads.jsonl`，配合 `app_session_id` 定位原同次App。独立Browser数据不进入本轮两个条件。

新批次的 `bind_memory_batch` 保留独立 `memoryonly-<session>` 身份，核验原始包络、payload与操作收据的同次会话，沿用v14原始状态和质量语义。字段编译复用旧prepare中的纯函数；不调用旧378成员准入、训练或选择，不假冒旧实验ID。

## 同流程与效果核验

沿用 `week6_webview_automation_runner.mjs` 的CDP `Page.addScriptToEvaluateOnNewDocument` 和导航方法，以及 `featureapp_webdriver_runtime_v1/cdp_transport_control.mjs` 的等待页面、局部连接与命令回执流程。

新 `memory_only_cdp.mjs` 的唯一写入是自身实验WebView中 `Navigator.prototype.deviceMemory` 和同一 `navigator.deviceMemory` 的getter。两个写入是同一个Web字段，不是两个独立观测。正常和恢复阶段仍注册 `void 0` 空操作，使用相同连接、导航和等待。hardwareConcurrency、UA、platform、webdriver、语言、屏幕、图形字段均没有修改语句。

每个阶段都是专用只读AVD上的新App进程；所有阶段在接收原始记录后退出App，消除当前realm的覆盖。另记录未来文档脚本移除回执，并用下一次clean_post真实Web值核验恢复。设置目标成功、原始字段发生变化、恢复成功、条件触发四者分开统计；设置2但原本就是2只能算无可观测效应。

所有模型只接收当前记录。pre/post、目标值、phase、标签和型号仅用于关联、效果与混杂分析。未读取其他设备的Native，也没有直接改JSON制造真实实验记录。单向上界关系允许降低W、允许包络内变化，这些是能力限制。
