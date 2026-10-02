# WebGL 行为一致性：最小可行性验证

日期：2026-10-01。状态：**十二次采集完成；参数等价性这一单项假设得到本地支持，两个检查的组合验收仍为 NOT_ESTABLISHED。**

这次找到的方向是检查 WebGL 接口本身是否自洽，不需要判断 renderer 应该写 Apple、NVIDIA 还是 SwiftShader。
它为下一步新增观测提供了依据，但还没有进入规则选择器，也没有产生整体检出率提升。

## 测了什么

使用同一个 Mac、App v13、本地 v2 探针、API 36 / WebView 134.0.6998.135，
在 host 与 SwiftShader 两条正常渲染路径上各执行两组“正常—加载插件—恢复”，共十二次采集。
每个阶段都重新启动 App 进程，使用同样的调试连接、导航和行为探针，只有攻击阶段加载插件。

攻击沿用已安装的 `puppeteer-extra-plugin-stealth 2.11.2` 的 `webgl.vendor`，
固定为此前的 NVIDIA / Direct3D11 配置，没有修改攻击侧仓库或实现新的攻击。
恢复使用一个不加载插件的新进程，不是在原进程中撤销代理。

行为探针为 WebGL1、WebGL2 各创建一张新的 8×8 canvas，并依次测量：

1. **H1：扩展启用门槛。** 未启用 debug renderer 扩展时，查询两个 unmasked 枚举应返回 null 和 INVALID_ENUM。
2. **H2：参数等价性。** 启用扩展后，使用“数字—对应十进制字符串—数字”查询同一个参数；三个值应一致且无错误。
3. **能力控制。** MAX_VERTEX_ATTRIBS 的数字/字符串查询应一致，最后一个有效属性索引应成功，第一个越界索引应报 INVALID_VALUE。
4. **真实绘制控制。** 编译并链接顶点/片元着色器、绘制红色三角形覆盖 8×8 画布，再读取 64 个 RGBA 像素。

这些预期来自接口规范和实现，而不是由本轮结果拟合阈值。
探针与判定器在运行开始时保存快照；上下文丢失、已有错误、异常、缺失值和前后数值漂移保留 UNKNOWN。
行为数据单独保存在 `BEHAVIOR.json`，通过前后两次 session_id 与同阶段原始 payload 对应；正式 177 字段未增加。

## 主要结果

| 检查 | 四次干预 | 八次正常/恢复 | 结论 |
| --- | --- | --- | --- |
| H2 参数等价性，WebGL1 | 4 次 COUNTEREXAMPLE | 8 次 MATCH | 本地机制支持 |
| H2 参数等价性，WebGL2 | 4 次 COUNTEREXAMPLE | 8 次 MATCH | 本地机制支持 |
| H1 扩展门槛，WebGL1 | 4 次 COUNTEREXAMPLE | 8 次 MATCH | 本地机制支持 |
| H1 扩展门槛，WebGL2 | 4 次 COUNTEREXAMPLE | 4 次 MATCH，4 次 UNKNOWN | 有正常对照不可判定 |
| 属性能力边界控制 | 两种上下文全部 MATCH | 两种上下文全部 MATCH | 未观察到区分作用 |
| 实际绘制及像素读取 | 两种上下文全部 MATCH | 两种上下文全部 MATCH | 未观察到区分作用 |

十二份原始 payload 均收到，177 字段均为 observed；四组 vendor/renderer 修改生效，
四组原始图形字段与完整行为上下文记录恢复一致，非目标十个图形字段四组均不变。
两个渲染路径、两种 WebGL 上下文均完成了实际绘制，总计二十四个上下文。
这些上下文不是二十四台独立设备，表中次数也不是独立测试集的 TPR/FPR。

H2 的具体例子，在 host 攻击阶段为：

| 调用 | 返回值 |
| --- | --- |
| `getParameter(37446)` | `ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)` |
| `getParameter("37446")` | `Android Emulator OpenGL ES Translator (Apple M4)` |
| 再次 `getParameter(37446)` | 与第一次相同的 NVIDIA 声明 |

三次查询都没有 WebGL 错误。正常/恢复阶段，三次均返回该路径原有的同一字符串。
SwiftShader 路径也复现相同模式。这里用到的是**相同参数语义对应不同结果**，
不是认定某个 GPU 名称不合法，也不是将字符串形式查询当作不可伪造的“真实 GPU”来源。

## 为什么可以提出 H2

WebGL 的 `getParameter` 参数类型是 GLenum，其 IDL 基础类型为 unsigned long。
Web IDL 的转换算法先进行数字转换，所以本轮使用的小正整数及对应十进制字符串应得到相同枚举。
[WebGL 规范](https://registry.khronos.org/webgl/specs/latest/1.0/)、[Web IDL 标准](https://webidl.spec.whatwg.org/)

已安装插件先调用原函数，然后对**转换之前收到的 JavaScript 参数**做严格数值比较，只在两个数字枚举上替换返回值。
因此字符串形式在这个版本中保留原调用结果。这个事前源码推断已被本轮运行结果支持。
它和 H1 是同一实现局限的两个表现，不能当作两个独立机制叠加贡献。
更多来源及版本限制见 [SOURCES.md](SOURCES.md)。

## UNKNOWN 与未通过的组合验收

host 路径的六个 WebGL2 上下文，在第一个 vendor 查询开始前，错误队列里都已经存在 INVALID_ENUM：
包括两次正常、两次攻击和两次恢复。记录器虽然清空了队列，但冻结判定器明确要求查询前没有旧错误，
所以该项保留 UNKNOWN。后一个 renderer 查询的前置错误队列为空。

已定位的是错误出现于**首个测量点之前**；具体由上下文初始化、属性读取还是更底层调用产生，尚未隔离。
它在正常阶段也存在，不能作为攻击专属证据。

因此，原组合判定在四组中只有 SwiftShader 的两组完成了 MATCH—COUNTEREXAMPLE—MATCH，
`SUMMARY.json` 中的整体可行性仍为 **NOT_ESTABLISHED**。
本轮没有删除旧错误、把 UNKNOWN 改成 MATCH、丢弃 host 记录、重跑补位或修改验收条件来把结果做成通过。

同时，H2 是运行前单独列出的假设，它的所有查询都有干净的错误状态且前后稳定；
两条路径的四组均符合预期，且能力/绘制控制全部通过。
因此可以支持更窄的结论：**参数等价性观测在本机这个插件配置上具有机制可行性，值得单独设计下一版本观测。**
[DIAGNOSIS.json](DIAGNOSIS.json) 将这项解释与原组合验收分开保存。

## 不能据此说什么

- 没有验证其他 WebView/浏览器版本、独立宿主、合法代理/隐私扩展，也没有测试不同攻击实现或插件修订版本。
- 接口不自洽可能来自脚本代理、浏览器问题或合法工具；本检查不能直接证明恶意、授权状态或物理 GPU。
- 插件若统一处理参数转换或保持接口契约，可能不再触发；本结果不是对所有 GPU 伪装的检测保证。
- 简单绘制在正常/攻击下全部一致，不能把这个像素结果当作 GPU 型号指纹或新增检测能力。
- 现有历史 378 行没有保存这些额外调用结果，不能补算、伪造新字段或直接宣布找回历史九条 WebGL 漏检。

本轮模型 fit **0**、model predict **0**、新增注册告警候选 **0**。
最近 CAP7 结果仍为 **117/126（92.86%）**，内部对照 **0/252**，WebGL 单项 **0/9**；这些指标本轮未重跑。

## 下一步建议

优先为 **H2 参数等价性**设计独立、带版本的观测字段与纯判定模块，保留 MATCH / COUNTEREXAMPLE / UNKNOWN，
先不参与模型告警。它只使用 Web 表面，不需要跨 Native 的物理 GPU 身份判断；
但仍然是新增观测，不能当作现有 Web 67 字段已包含的条件。

接着在已有 API 29 / 30 / 36 环境补充可用的正常与插件对照，核实参数转换、扩展缺失和上下文错误边界；
检查到实际 WebView 版本差异后，才能讨论覆盖范围，不能把三个 API 标签自动视为三个独立浏览器环境。
H1 的初始化错误问题单独处理，不作为 H2 的前置补救或改写本轮结果的理由。

待观测契约与正常边界通过，再冻结使用同一新采集版本的基线/增量对照，放回选择器比较整体效果。
这一阶段不要求重新采集真机，但结论仍必须保留模拟器和受控工具范围。

## 可复核材料

- [协议](PROTOCOL.json)、[运行前检查](PRE_RUN_REVIEW.json)、`source_snapshot/`：运行前的计划与判定源码。
- `runs/*/attempts/*/BEHAVIOR.json`：每个查询的原始入参类型、返回值、错误队列、上下文状态和绘制像素。
- `runs/*/backend/raw_expanded_payloads.jsonl`：同会话 App 原始 payload。
- [逐行结果](ROWS.json)、[成对结果](TRIPLETS.json)、[原组合结果](SUMMARY.json)、[诊断](DIAGNOSIS.json)。
- [测试日志](TESTS.log)：九项聚焦边界测试通过。
- [资源关闭检查](CLEANUP_CHECK.json)：两组接收器和模拟器均退出，四个专用端口关闭。

只读重算：

```sh
python3 -B deliverables/webgl_behavior_feasibility_v1/analyze.py
python3 -B deliverables/webgl_behavior_feasibility_v1/diagnose.py
```

不要重跑 `run_pairs.py`；启动标记拒绝重复执行。本轮只新增本研究目录，未提交推送、部署、
修改正式采集合同或访问独立确认材料。
