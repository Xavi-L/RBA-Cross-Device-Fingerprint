# 屏幕同期观测与小规模几何关系验证

已完成 App 接入、构建、测试及一次正式 72 条采集。新增的一个 Host 几何上界条件检出 **6/6 次有效屏幕干预**，在 **66 条有依据的正常记录中报警 0/66**；旧高度条件同样检出 6/6，但把正常扩大 WebView 的 6 条记录报警。三个条件全部可评估，没有用增加 U 换取改善。这里比较的是单条条件，不是训练后的完整模型。

本轮 **0 次模型拟合**。基线提交为 `f03036516bcd95d1018540eca03d3d3bea35f62b`；旧模型、旧 378 条与 MTC 数据、历史分数保持原样。72 条来自三个模拟器环境的重复观察，不是 72 台设备，也不是新的真机人群误报估计。

## 实际采集与版本

| 环境 | 实际 WebView | 预定/尝试/接收/有效几何窗口 |
|---|---|---|
| API29 / SwiftShader | 91.0.4472.114 | 24/24/24/24 |
| API30 / SwiftShader | 91.0.4472.114 | 24/24/24/24 |
| API36 / SwiftShader | 134.0.6998.135 | 24/24/24/24 |

每环境 L1 旋转、L2 宿主布局扩大、L3 `WebView.zoomBy(1.25)`、A 原 CDP 屏幕配置各两组三阶段。预定矩阵只采了一次，无位置重试或替换。6 条 API29 工程冒烟另存 `smoke/`，不计入上述分母。

正式 72 条安装并核对的是 **v15 / 1.6.8-expanded-v2.2-geometry**，几何模块 `featureapp-geometry-v1`，原 schema 仍为 `expanded-v2.2-status`，新观测 schema 为 `webview-geometry-v1`。当前源码修正了异步 Host getter 的异常边界，另构建 **v16 / 1.6.9-expanded-v2.2-geometry**、模块 `featureapp-geometry-v1.1`。v16 未追加安装采集；不能把正式 v15 结果称作 v16 实测。两个 APK、构建记录和小范围源码差异均保留，见 [工程修正说明](ENGINEERING_CORRECTIONS.md)。旧 v14 APK 未覆盖。

## 现在测到了什么

新模块位于 `collection_observations.webview_geometry`，由 FeatureApp 正常上传路径主动采样，CDP 只控制实验。Android 主线程实际读取 WebView 的 View 尺寸、padding、窗口位置/可见矩形、父容器/窗口/insets、方向、density、WebSettings、缩放回调及其时刻。Web 在一段同步读取中保存视口、DPR、visualViewport、方向、viewport meta 和文档标识。固定 177/67 目录与既有 WebGL1、webdriver 附加观测保留。

本批确实读到了网页所在的 View 区域。例如 API29 默认 Host 为 **1080×1676 px**，收起 Android 信息区后变成 **1080×2211 px**；它不是一直取整块屏幕尺寸。定义的内容区域是 View 尺寸减自身 padding，仅减一次，不再扣系统栏 insets；可见裁剪矩形单独保存。当前自身 padding 为零。非零 padding 和复杂 View/祖先变换尚未建立适用口径。

采样为 Host 前读取→异步 Web 同步快照→Host 后读取。绑定同 session、实例、文档代次、唯一 observation ID；稳定性只看 Host 事件/前后状态及本时钟域的顺序，不看 Host/Web 是否一致。72 条均一次尝试成功，Host 窗口为 API29 **2–13 ms**、API30 **2–15 ms**、API36 **1–40 ms**；没有观测到超时、不稳定或读取失败。这不是原子同步保证，异常/销毁/迟到路径另有针对性测试。

旧 `screen_layer` 与新 Web 快照是两次读取，明确标记不同快照。本批数值碰巧全部一致，仍不混用操作数。Android 单调时钟与 Web performance 时钟不直接相减；没有缩放观测时不补 1。

## 唯一新增条件及对照结果

对宽、高分别计算：

`P = 当前 visualViewport CSS尺寸 × 当前 DPR × 当前 visualViewport.scale`

`H = Android 实测 WebView尺寸 − 该轴两边padding`

当任一轴 `P > H + ε` 时 T；两轴均可判断且未超过时 F；缺失按三值 OR 保留 U，执行/绑定错误另记 FAILED。固定 `ε = 2 + 4×2^-23×max(|P|,|H|,1)` px；全环境同式，正式前固定，不拟合。2 px 是本研究的边缘量化预算，**不是所有 WebView 的官方误差保证**。字段口径、API/Chromium 源码依据及适用域见 [SEMANTICS.md](SEMANTICS.md)。不要求 DPR 等于 Android density，不把缩放回调等同于 Web scale，不使用 Host/Web 宽度比反推缩放。

| 单条条件 | 全72条 T/F/U/FAILED | 正常报警 | 有效A检出 | 明确覆盖 |
|---|---|---|---|---|
| 旧 `inner_height > 710` | 12/60/0/0 | 6/66（9.09%） | 6/6 | 72/72 |
| 旧同Web视口关系 | 0/72/0/0 | 0/66 | 0/6 | 72/72 |
| 新 Host 几何上界 | 6/66/0/0 | 0/66 | 6/6 | 72/72 |

共同可评估子集也是 72/72，正常 66/66、有效 A 6/6，与完整分母结果一致。全部正常与有效干预均由原始观测、同次操作回执和执行/恢复证据确认，不以检测输出贴标签；几何缺失本身不会取消已确认的正常身份。

正常变化中，L1 实际旋转 **4/6 次**，这 4 条三个条件都 F；API36 两次成功发送设置请求，但当前 Host 仍竖屏且后读 user_rotation 回到 0，记为 **无可观测效应**，保留正常尝试，不称旋转成功。原因未进一步排查或更换环境。L2 实际布局变化 **6/6 次**，旧高度全部 T，新关系全部 F；L3 实际缩放 **6/6 次**，三个条件均 F。24/24 组三阶段都恢复到基线，失败/缺失恢复为 0/24。

## 稳定矛盾和实际增益

正常布局扩大时，API29/30 的旧 innerHeight 从 639 变成 843，API36 从 710 变成 914，因而旧绝对高度条件误报。新关系同时观察到 Host 内容高度从 1676→2211 px、1865→2400 px，换算仍在上界内；它多提供了“网页是否装得进当前宿主区域”的信息。

原 CDP 配置仍为 width=393、height=851、DPR=2.75，其他参数原样。6 次均真实改变目标字段且撤销恢复。变化时实际 Web 视觉高度约 **851.047607 CSS px**，DPR 实读约 **2.750000149**，scale=1，换算 **2340.381047 px**；Host 高度仍分别是 1676、1676、1865 px，超过上界约 **664.381/664.381/475.381 px**，远大于约 2.001 px 预算。Host 前后稳定，这些矛盾没有转为 U。旧同Web关系因 Web 字段协调改变而不报警。

新条件没有比旧高度多检出这 6 次 A；本次增益是**保留相同局部检出，避免正常布局扩大造成的 6 次报警**。与旧同Web关系相比新增检出 6 次。本批未验证旧屏幕 9 条的完整模型分数，不能宣称把原屏幕 6/9 提高到 9/9。

API29/30 正常投影也有约 +2 px 的实际偏差，接近固定预算，原值全部保留；因此不能称精确等式。1.25 倍真实缩放使 Web 视觉尺寸相应缩小，换算范围不变。初始 onScaleChanged 常未发生，不能默认成 1；缩放时回调约 3.28125，而 Web scale 为 1.25，它们不等价。

核对的 33 个主要非目标 Web 字段中，仅 `compute_task_time_ms`、`performance_time_origin` 随会话变化；UA、platform、资源、语言、时区、图形及 automation 字段没有观察到变化。逐条三阶段证据保留全部差异，`confounded` 保守为 true；上述两个时间字段不进入本轮三条条件，不把它们藏掉或归因于屏幕篡改。

## 能力边界与下一步判断

这个候选在当前 App 布局域内有局部价值，尚不足以直接替换完整模型中的高度条件。它只检查上界：缩小型干预、同步改变多项值且仍满足上界的干预可以漏检；CDP 改变渲染/暴露状态也可能保持相容。Host 读取独立于 Web，但不是不可干预的硬件真值。

本轮没有真机、折叠屏、分屏、IME 或非零 WebView padding 的正常覆盖。旧 MTC/旧378条缺这些同期字段，不回填、不拼接，直接接入现有训练会遇到可评估覆盖不足。下一轮若继续，最值得做的是用当前 App 正常路径在少量真实设备上核对布局/方向/缩放及量化预算，保留正常反例；再决定能否纳入相同约束下的候选比较。本轮没有执行该补采、选择器接入或训练。

## 交付、测试与复现

实现入口：Android `WebViewGeometryObserver.kt`、`GeometrySamplingPolicy.kt` 与 MainActivity/桥接；Web `web_probe/webview_geometry_observer.js`；Python `screen_geometry_sources.py`、`screen_geometry_relations.py`；本目录 `collect.py`、`screen_cdp.mjs`、`evaluate.py`、`summarize.py`。逐条输出在 `predictions.jsonl.gz`，原始引用在每条记录中；原始采集位于各 `runs/*/backend/raw_expanded_payloads.jsonl`，没有复制整套历史数据。[RESULTS.md](RESULTS.md) 给出详细分组和固定首轮原值，[SUMMARY.json](SUMMARY.json) 为机器可读汇总。

测试通过：v15 Android **51** 项；v16 Android **55** 项（包含前者，不能相加）；最终 Python **43** 项；Web/CDP **21** 项；后端 **4** 项。覆盖线程/有界状态机、异常完成、旧回调、同次绑定、单位和三值逻辑、损坏/null 输入、正常身份与效果/恢复分离、后端保留与旧目录兼容。Android 日志和计数见 `BUILD*.json`、`runtime/build*.log`；Python 日志见 `runtime/python-tests.log`。

从仓库根目录运行：

```bash
# 当前 v16 源码构建；独立目录，不覆盖 v15 或已有 build 输出
zsh deliverables/screen_geometry_observation_v1/build.sh /tmp/screen-geometry-build-reproduce

# 相关 Python 测试
python3 -B -m unittest hybridguard_agent.tests.test_screen_geometry_relations hybridguard_agent.tests.test_screen_geometry_evaluation hybridguard_agent.tests.test_screen_geometry_collection hybridguard_agent.tests.test_mtc_screen_relations
node --test browser_probe_site/tests/webview-geometry-observation.test.mjs browser_probe_site/tests/featureapp-webgl-integration.test.mjs browser_probe_site/tests/probe-contract.test.mjs deliverables/screen_geometry_observation_v1/test_screen_cdp.mjs
(cd backend_server && .venv-collection/bin/python -B -m unittest test_geometry_observation_storage test_collection_contract)

# 本次首次真实运行使用的命令；已有结果目录会拒绝重新采集/覆盖预测
python3 -B deliverables/screen_geometry_observation_v1/collect.py --preflight
python3 -B deliverables/screen_geometry_observation_v1/collect.py
python3 -B deliverables/screen_geometry_observation_v1/evaluate.py evaluate

# 仅从保存预测重新生成 SUMMARY.json 和 RESULTS.md，不启动任何采集或训练
python3 -B deliverables/screen_geometry_observation_v1/summarize.py
```

如需独立重算条件而不启动采集，可在仓库内新建结果目录，复制本目录 SETTINGS.json 并把其中 runs 软链接到本目录 runs，再传 `evaluate.py evaluate --output-dir <新目录>`。如需重新真实采集须显式选择新目录并复制 SETTINGS/CONDITIONS_FROZEN；固定矩阵仍指向保存的 v15 APK，不自动换用 v16。

三个正式环境及冒烟环境均使用本轮自有只读 AVD，系统设置恢复已核对；自有接收器与模拟器已退出，5680/5681/8000/9222 端口释放。初始 209 项未提交路径状态仍保留，构建写入独立临时目录。未暂存、提交、推送或开始下一阶段。
