# 屏幕观测模块本地工程收尾

2026-10-03；起始与结束 HEAD 均为 `b6da48961775a4ff79b2410fa8bee244b8e29071`。

**本地工程收尾完成；真机正常表现与整套模型接入尚未验证。** 保留一项明确限制：API29 默认启动的“调试端点关闭”检查未通过，不能称 12 个位置所有工程检查均通过。实际 App 默认采集、故障降级上传、后续新进程恢复及文件读取修复已有运行证据；本轮没有发现需要再修改 Android 的运行时缺陷。

本轮复用保存的 v16 APK，没有重建 APK、升级版本或修改 Android 源码；模型拟合 **0 次**。没有新关系、容差调整、旧 72 条重采、MTC 重采或付费资源调用。历史模型、APK、原始数据、配置、预测及研究报告未改动；原工作区 209 个未提交条目均保留。未提交或推送。

## 实际安装与 12 个预定位置

安装来源为 [已有 BUILD_v16.json](../screen_geometry_observation_v1/BUILD_v16.json) 指向的 `runtime/featureapp-v16-geometry-local-only.apk`。安装前 `aapt`、安装后包信息均核对为 **16 / 1.6.9-expanded-v2.2-geometry**；12 条原始记录的几何模块均为 **featureapp-geometry-v1.1**。设置和成员在采集前固定于 [SETTINGS.json](SETTINGS.json)，没有换环境或追加尝试。

| 环境 | 实际 WebView | 预定／尝试／收到原始记录 | 实际路径 |
|---|---|---|---|
| API29 / SwiftShader | 91.0.4472.114 | 6 / 6 / 6 | 正常→屏幕干预→恢复；默认启动；Web 几何降级；降级后新进程 |
| API30 / SwiftShader | 91.0.4472.114 | 3 / 3 / 3 | 正常→屏幕干预→恢复 |
| API36 / SwiftShader | 134.0.6998.135 | 3 / 3 / 3 | 正常→屏幕干预→恢复 |

三个环境的 A 路径各只执行一轮。共 **3/3 次可观测干预，3/3 组恢复**；11/12 条具有可用的同会话几何窗口，剩余 1 条是预定工程故障。session、文档、观测 ID 与 Host 前后快照由原绑定逻辑核对。全部 12 个会话各有一条 raw、一条 canonical、一条接收回执；这只说明按会话归档未重复，不把 HTTP 重试等同于重复组装。

采集原始证据见 [v16_smoke](v16_smoke/)，逐条结果与工程核对见 [v16_evaluation](v16_evaluation/)。操作状态保留 **10 条 COLLECTED、2 条 FAILED**；评价位置状态为 **10 条 EVALUATED、2 条 FAILED_EVIDENCE**，不是丢掉失败后的 10 条分母。

### 默认启动的限制

API29 的 `v16-DEFAULT` 与 `v16-POST_FAULT` 都从全新 App 进程启动，未传入开启 WebView 调试、等待 CDP 或探针延迟的参数，也没有调用 CDP 采集器。两条均由 App 自有路径上传 177 项旧字段目录和新增几何观测，几何各用一次尝试、4 ms 完成，三个条件均为 F。

但启动检查发现了 WebView 调试 socket，早于写出默认启动流程回执，因此原操作失败和两份缺失回执错误完整保留。原错误文本中的 “inherited” **不能证明调试设置被继承**。两条原始记录显示系统为 `userdebug`；对应 WebView 91 官方源码在 debug Android 上自动开启调试，并忽略关闭调用，足以解释该端点：[WebViewChromiumAwInit.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/91.0.4472.114/android_webview/glue/java/src/com/android/webview/chromium/WebViewChromiumAwInit.java)、[SharedStatics.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/91.0.4472.114/android_webview/glue/java/src/com/android/webview/chromium/SharedStatics.java)。App 的 `MainActivity` 则每次按本次 Intent 的默认 false 调用关闭接口。

因此，**默认采集不依赖 CDP 已实测；该环境中的调试端点关闭未获验证**。这两条作为工程位置单列，没有因为得到 F 就追认完整流程通过，也没有并入下面的 6 条有完整正常流程依据的分母。没有为此换设备、追加采集或修改 App。原始引用为 API29 `raw_expanded_payloads.jsonl` 的物理第 4、6 行。

### 降级上传与后续恢复

故障方式事先固定为测试侧 `Page.addScriptToEvaluateOnNewDocument` 包装 **Web 的 `HybridGuardProbe.captureWebViewGeometry`，使其返回 null**。没有永久 App 故障开关，没有改屏幕数值；故障脚本和两项针对性测试分别为 [fault_cdp.mjs](fault_cdp.mjs)、[test_fault_cdp.mjs](test_fault_cdp.mjs)。

API29 `v16-DEGRADE`（原始文件第 5 行）在 **304 ms、两次尝试**后以 `unavailable / web_binding_mismatch_or_missing` 结束，低于 5 秒总上限。旧 payload 仍收到并上传：177 项字段状态目录、webdriver 与 WebGL1 附加观测均保留；Host 条件为 **U**，两个旧条件为 F。该位置不进入正常误报或攻击检出统计。

上传后再观察 6 秒，调用次数仍为 2，观测内容未被改成成功，同一会话没有再次归档。随后 `v16-POST_FAULT` 的新进程恢复到可用几何窗口。这次运行验证的是 **Web 读取不可用的降级路径**，不声称实测 Native getter 异常或主动注入了迟到回调。Native 前／后 getter 异常、文档替换、销毁、迟到回调和一次完成仍由本轮重新运行的 11 项 Android 几何单元测试覆盖。

## 三个固定条件的结果

以下是单条件结果，没有接入或更新完整模型。表中为 T / F / U / FAILED；“明确覆盖”只计 T+F。

| 材料／分组 | 记录数 | 旧高度 >710 | 旧同 Web 关系 | Host 几何上界 |
|---|---:|---|---|---|
| v15 完整预定矩阵 | 72 | 12 / 60 / 0 / 0 | 0 / 72 / 0 / 0 | 6 / 66 / 0 / 0 |
| v15 有依据正常 | 66 | 6 / 60 / 0 / 0 | 0 / 66 / 0 / 0 | 0 / 66 / 0 / 0 |
| v15 有效干预 | 6 | 6 / 0 / 0 / 0 | 0 / 6 / 0 / 0 | 6 / 0 / 0 / 0 |
| v16 全部预定位置，含工程故障 | 12 | 3 / 9 / 0 / 0 | 0 / 12 / 0 / 0 | 3 / 8 / 1 / 0 |
| v16 A 路径的正常／恢复 | 6 | 0 / 6 / 0 / 0 | 0 / 6 / 0 / 0 | 0 / 6 / 0 / 0 |
| v16 A 路径有效干预 | 3 | 3 / 0 / 0 / 0 | 0 / 3 / 0 / 0 | 3 / 0 / 0 / 0 |

v16 Host 明确覆盖为 **11/12**；正常路径观察到的报警为 **0/6**，有效干预检出 **3/3**。其余两个默认启动位置的当前观测可以独立判为 F，但流程证据状态仍为 FAILED_EVIDENCE；这与条件执行失败不同。故障位置的 U 是正确保留的不可用状态，不是正常正确。三个环境中的重复观察不能当成新增真机人数；12 条冒烟未合入 v15 的 72 条，未改动 105/126 或 MTC 分数。

三个 A 组均保留了原判定器记录的非目标变化：运行耗时与 `performance_time_origin` 变化，`confounded=true` 未被清除。它们不参与这三个屏幕条件，也不据此扩大到完整模型归因。

## 损坏输入与 v15 一致性

新增 [screen_geometry_io.py](../../hybridguard_agent/research/screen_geometry_io.py)，由旧 v15 与新 v16 评价共用。JSONL/GZ 按物理行解码；空行占行号并留错误，坏 JSON、非对象、非法编码、缺失／错误类型的必要 ID 都有位置和错误类型。压缩流损坏保留已解出的行与流错误，不声称恢复不可读取的后续内容。

评价从固定配置生成预定位置，用操作 step、session 和回执绑定；不按坏行顺序猜身份。重复 step、重复 session 和跨环境 session 冲突不任取一条。无法归属的错误留在 `READ_ERRORS.json`；缺输入的预定位置保留 FAILED_INPUT／NOT_EXECUTED，流程证据缺损留 FAILED_EVIDENCE。有效当前记录缺几何观测继续沿用原 U／FAILED 语义。配置或预定清单不合法时停止，不输出默认分数。输出必须选新目录，仓库外路径也可用；旧无参数汇总入口现在只读。

损坏测试只使用临时文件或原始记录的临时副本。覆盖好—坏—好、空行物理定位、null／数组／标量、0/-1 等原有观测边界、错误 ID、重复绑定、缺失／损坏回执、损坏环境文件、非法编码、截断 JSON/GZ 和解压失败。全层缺失夹具仍保留 **72/72 个预定位置**；v16 嵌套损坏夹具仍保留 **12/12 个位置**。这些故障夹具不计研究样本。

[V15_CONSISTENCY.json](V15_CONSISTENCY.json) 对 72 个原 sample ID 逐条比较了**全部原有嵌套字段**，包括来源、数值、三个条件、正常依据、干预效果、恢复和汇总，结果 **72/72 一致、汇总差异 0**。只允许新增错误追踪字段。24/24 组恢复，旋转实际生效 4/6，全部条件无 U/FAILED；上述结果并非只比较总数。重算输出在 [v15_replay](v15_replay/)，没有覆盖旧输出。

开发中的两处补充修正已包含在最终版本：给 v16 A 路径正确标记 `ENGINEERING_SMOKE`；附加工程核对也隔离嵌套损坏与读取错误。修正后只离线重算，12 条的条件、绑定、正常依据、效果、失败状态及整个数值汇总均未变。采集脚本今后也会先记录 socket 检查结果，错误措辞不再推断“继承”；本次两条原失败日志没有改写。另将 JSON 非有限数／重复对象键作为明确读取错误，避免写出时整批中断。

## 测试、复现和清理

本轮 Python **51/51**、Node/CDP **5/5**、Android Geometry **11/11** 通过。命令、范围及日志索引见 [TEST_RESULTS.json](TEST_RESULTS.json)，Android 使用隔离临时 build 目录，只跑几何单元测试，没有 assemble APK。

在仓库根目录执行；输出目录必须尚不存在：

```sh
# 完好 v15 离线回放和逐 ID 核对，不启动采集
python3 -B deliverables/screen_geometry_observation_v1/evaluate.py evaluate --input-dir deliverables/screen_geometry_observation_v1 --output-dir /tmp/geometry-v15-replay-new
python3 -B deliverables/screen_geometry_closeout_v1/verify_v15.py --replay-dir /tmp/geometry-v15-replay-new --output /tmp/geometry-v15-check-new.json

# 已保存的 v16 真正冒烟原始数据离线评价
python3 -B deliverables/screen_geometry_closeout_v1/evaluate.py --input-dir deliverables/screen_geometry_closeout_v1/v16_smoke --output-dir /tmp/geometry-v16-evaluation-new

# 只从旧保存预测重建数值报告，原目录只读
python3 -B deliverables/screen_geometry_observation_v1/evaluate.py summarize --input-dir deliverables/screen_geometry_observation_v1 --output-dir /tmp/geometry-v15-summary-new

# 相关回归
python3 -B -m unittest hybridguard_agent.tests.test_screen_geometry_io hybridguard_agent.tests.test_screen_geometry_evaluation hybridguard_agent.tests.test_screen_geometry_relations hybridguard_agent.tests.test_screen_geometry_collection
node --test deliverables/screen_geometry_observation_v1/test_screen_cdp.mjs deliverables/screen_geometry_closeout_v1/test_fault_cdp.mjs

# 本轮实际使用的独立入口（仅供复现；本轮不再执行）
python3 -B deliverables/screen_geometry_closeout_v1/collect.py --preflight
python3 -B deliverables/screen_geometry_closeout_v1/collect.py --output-dir /tmp/geometry-v16-smoke-new
```

三个环境的 `final_system_restoration` 均为 RESTORED，`owned_processes_exited=true`；结束时 5680/5681/8000/9222 没有监听。本轮仅启动自己的只读 AVD 实例和单 worker 本地接收器，已清理，没有停止用户已有服务。

剩余限制是 userdebug 平台的调试端点检查，以及尚未实施的真机正常表现和整套模型接入验证。没有发现阻止继续使用本地几何采集模块的代码问题；不由这次小规模工程冒烟推断真机普适误报率。本轮到此停止。
