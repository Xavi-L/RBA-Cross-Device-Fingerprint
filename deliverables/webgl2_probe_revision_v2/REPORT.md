# WebGL2 修复及正常图形路径对照报告

日期：2026-10-01。基线代码：`512ac0b7cfddd2691144ba8d959ca7d8a7635ba0`。

## 结论

已修复并版本化 WebGL2 采集。桌面浏览器中，旧的同 canvas 创建方式返回 false，
独立 canvas 与实际 v2 探针都返回 true。Android API 29/30/36 共收到 15 份正常
控制 payload，WebGL2 均为 observed/true，177 个字段状态均为 observed。
这证明本轮环境中的修复效果，不能改写历史 v1 数据或推断所有设备都支持 WebGL2。

正常切换模拟器图形路径，确实会改变 renderer、扩展数量、GLES 字符串和视口上限。
本轮没有可加入规则选择器的新 GPU 告警候选，没有训练或生成模型预测。
既有 CAP7 结果仍为 **117/126（92.86%）**，本轮没有新的检出率提升数字。

## 修复内容

1. 共享探针从 `expanded-web-67-v1` 升到 `expanded-web-67-v2`。WebGL1 与 WebGL2
   分别使用独立 canvas；67 个 Web 字段和 177 个 App 字段清单不变。
2. WebGL2 返回 null 记录 observed/false，抛异常记录 runtime_error/false；异常时
   false 只是回退值。WebGL1 与 WebGL2 状态独立，WebGL1 异常不再被覆盖成 not_applicable。
3. App 桥接回退及 Kotlin 字段状态报告器同步增加 webgl2 状态。App 升至 versionCode 13、
   `1.6.6-expanded-v2.2-webgl2-probe`。
4. 静态站同步同一核心，manifest 从核心读取版本；后端按“版本—已登记 bundle”校验。
   两个旧 v1 bundle 仍只能以 v1 身份接收，新 v2 不能与旧版本互相冒认。

规范依据：[HTML canvas getContext](https://html.spec.whatwg.org/multipage/canvas.html#dom-canvas-getcontext)。
正常图形路径选择依据：[Android Emulator graphics acceleration](https://developer.android.com/studio/run/emulator-acceleration#accel-graphics)。
这些依据说明上下文与渲染模式语义；以下运行结果来自本仓库保存的原始 payload 和日志。

## 执行与失败保留

首轮使用预先记录的五个条件，单个条件只尝试一次：

| Android / 请求模式 | 计划 | 收到 | 结果 |
| --- | ---: | ---: | --- |
| API 36 / auto | 3 | 3 | 完成 |
| API 36 / host | 3 | 2 | 第三次启动复用已有 Activity，无新 payload，45 秒后停止 |
| API 36 / swiftshader | 3 | 2 | 同上 |
| API 29 / swiftshader | 1 | 1 | 完成 |
| API 30 / swiftshader | 1 | 1 | 完成 |

首轮仍记为 **9/11，存在两次失败**。两份 `start-3.log` 都出现
`Activity not started, intent has been delivered to currently running top-most instance`。
这是启动未产生新采集的直接证据；没有对应 payload，不能判断为 WebGL2 探测失败。

仓库既有 `run_expansion.py` 已实现 `process-absent-then-am-start-S-W-v1`。
本轮简化控制脚本最初遗漏了该保护。修订后，先连续两次确认旧 App 进程不在，再
`am start -S -W`，并拒绝 Activity 复用或非成功启动。按单独登记的
`fresh_launch/PLAN.json`，只验证 host、swiftshader 各三次，**6/6 成功**。
这支持启动保护在本轮修复了重复采集问题；不推断竞态的所有底层原因。
追加验证没有覆盖或补写原来的失败位置。

全部运行使用项目已有 AVD 的只读模式，写入临时层；每个条件独立数据目录、一个
uvicorn worker、本机端点。未使用攻击工具、WebView 调试控制或注入。
App 自动伴随的浏览器流程不是本轮验收对象，不能把 App177 收到当作 Browser67 配对完成。

## 正常路径的实际差异

“请求模式”与“实际 renderer”分别保留，未把 auto 或 host 参数本身当作硬件证明。

| 条件 | 实际 Native / App Web renderer 特征 | 扩展数 | 最大视口 | WebGL2 |
| --- | --- | ---: | --- | --- |
| API 36 auto | Android Emulator Translator / ANGLE / SwiftShader | 19 | 8192×8192 | true |
| API 36 swiftshader | 同上 | 19 | 8192×8192 | true |
| API 36 host | Android Emulator Translator / Apple M4 | 16 | 16384×16384 | true |
| API 29/30 swiftshader | Android Emulator Translator / ANGLE / SwiftShader | 21 | 8192×8192 | true |

本轮各组内读数一致；最大纹理为 4096，线宽范围为 1–1。host 的模拟器日志也记录
Apple M4，GLES 字符串为 `OpenGL ES 3.0 (4.1 Metal - 89.4)`；软件路径为
`OpenGL ES 3.1 (OpenGL ES 3.1.0 (ANGLE 2.1.1 git hash: fbf66f49c7cc))`。

同一 Mac 上已得到两种实际渲染路径，而不是三个独立设备或三个硬件平台。
15/15 的 Native 与 App Web renderer 文本相等；这批控制没有给出“正常时不相等”
的反例，也不足以证明“只要不相等就是攻击”。Native 的两个 renderer 字段仍来自
同一次读取，不能当成两份独立佐证。

## 对候选规则的影响

只对这批记录运行现有两条单关系适用性检查，未改变规则注册表或汇总成模型告警：

- `NW-005`：10 份软件路径为 NOT_APPLICABLE；5 份 Apple M4 路径为 UNKNOWN，
  原因是 Apple 不在当前已审阅的移动 GPU 家族解析范围内。可进入风险候选的记录为 0。
- `OFFDER-GPU-001`：软件路径 10 份不适用，host 路径 5 份可观察关系，
  但该规则角色仍为 observation_only；15/15 均 NOT_ELIGIBLE。没有出现 Direct3D/Windows 标记。

因此不能仅为补回历史九条 WebGL-only 漏检而扩大 GPU 名称解析或恢复旧强规则。
`webgl2_supported=false` 也不能直接升级为攻击条件：上下文在正常环境中可能创建失败，
并且历史 v1 false 受采集缺陷影响。本轮所有 true 只说明已测环境可创建上下文。

下一步建议单独登记 **v2 同版本的小规模成对攻击验证**，使用本轮已确认的 host 和软件路径，
检查 WebGL-only 修改前、修改后、恢复后的 renderer 与其他图形能力变化。先确认条件在
正常路径下何时适用，再讨论候选准入。跨 Native/App Web 的条件还涉及当前 W0 单表面范围，
需要单独说明；不能悄悄放入现有选择器后把变化全归功于语义修订。

## 验证与交付边界

- JavaScript：42 项通过，覆盖独立 canvas、两个探针各自失败、null、无 debug 扩展、
  App 桥接回退、ES5 与固定字段清单。
- Android：44 项单元测试通过，debug APK 构建通过；运行 payload 声明 App13 / probe v2。
- 后端：15 项配对契约测试通过，覆盖新旧版本登记、跨版本拒绝及未登记版本拒绝。
- 实际浏览器：旧同 canvas false、fresh canvas true、实际 v2 true，67 字段。
- 原始 payload 到摘要的读取和版本、轮次、字段状态核对由 `analyze.py` 保存并可复核。

测试 APK 只指向本地端点，保存在忽略的 runtime 目录；没有交付公网 APK、发布网页或部署后端。
正式切换须先部署后端，再同步新网页和 App，避免旧 App 的 v1 ticket 打开 v2 网页被拒绝。
本轮没有提交推送，历史数据、模型和独立确认边界保持原状。

之前的 [WebGL 可行性审计](../rule_semantics_webgl_feasibility_v1/REPORT.md) 保存
CAP7 历史字段诊断和基线结果。本报告的新正常控制只用于采集修复与适用性研究，
不能报告为真机误报率、跨设备泛化性能或新的攻击检出率。
