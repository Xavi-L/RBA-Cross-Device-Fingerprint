# WebGL2 v2：两种正常渲染路径下的成对修改验证

日期：2026-10-01。状态：**本轮执行完成，暂无新增告警候选**。

## 主要结果

在 API 36 / WebView 134.0.6998.135 上，使用同一 App v13、同一 v2 探针，
分别运行 host（Apple M4）和 swiftshader 路径。每种路径做三组
“正常—攻击—恢复”，另做一次不连接调试器的普通采集。

**20/20 份 payload 收到，177 字段均为 observed；6/6 组字段修改生效，6/6 组恢复完整。**
这说明修改效果和恢复可复现，不是检测模型取得了 100% 检出率。

在预先指定的 12 个图形字段中，攻击只改变了 Web vendor / renderer；其余十个字段
在 6/6 组中均未变化。WebGL2 在正常、攻击、恢复阶段全部为 observed/true。
因此，修复后的 WebGL2 支持字段在本配置中**没有区分作用**，不能据此补回历史漏检。

本轮没有训练、预测、调整阈值或修改候选注册表，既有 CAP7 结果仍为
117/126（92.86%）；没有新的整体效果提升数字。

## 控制方式

协议先保存在 `PROTOCOL.json`，启动时写入 `STARTED.json`。两条路径各 10 次采集，
没有失败、补位或自动重试。所有采集只进入本地独立数据目录，模拟器使用只读 AVD。

三阶段都使用独立新进程、相同的 WebView 调试等待、Puppeteer Connection 和
`Page.navigate` 流程。只有攻击阶段启用既有 `webgl.vendor` 插件，固定值为：

- vendor：`Google Inc. (NVIDIA)`；
- renderer：`ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)`。

使用已安装的 `puppeteer-extra-plugin-stealth 2.11.2` 和 `puppeteer-core 25.3.0`，
配置对应 `w9-stealth-boundary-webgl-pair-v1`。本地适配器沿用旧攻击 runner 的
插件调用及页面适配方式，增加匹配的无插件控制；没有修改攻击侧仓库。
这验证单个已知插件配置，不代表完整自动化浏览器或所有 WebGL 规避方法。

恢复方式是结束攻击进程，在新进程中不加载插件，再读取字段。
“恢复”不表示在原攻击进程内撤销补丁。

每种路径的一次普通采集与该路径六次匹配正常采集的 12 个图形字段一致。
因此本轮未观察到调试连接/导航本身改变这组字段；这个结论只覆盖这些字段和已测环境。
App 伴随的浏览器配对不在本轮验收范围内。

## 观察值

| 路径 | 正常 / 恢复 renderer | 攻击 renderer | 扩展数 | 最大视口 | WebGL2 |
| --- | --- | --- | ---: | --- | --- |
| host | Android Emulator Translator / Apple M4 | NVIDIA GTX 1660 / Direct3D11 | 16，全程不变 | 16384×16384，全程不变 | true，全程不变 |
| swiftshader | Android Emulator Translator / ANGLE / SwiftShader | NVIDIA GTX 1660 / Direct3D11 | 19，全程不变 | 8192×8192，全程不变 | true，全程不变 |

两条路径下，最大纹理均为 4096，线宽范围均为 1–1。五个 Native 图形字段在各自三阶段
均保持不变。单独记录的 canvas hash 在全部 20 份记录中也相同。

对插件实际安装源码的检查显示，它代理 WebGL1 和 WebGL2 的 `getParameter`，
只替换两个 unmasked vendor / renderer 枚举的返回值，其他参数仍读取原值。
这与本轮原始数据一致。源码声明本身不替代运行证据，修改效果以对应 raw payload 为准。

## 候选条件如何处理

| 观察方向 | 本轮证据 | 本轮决定 |
| --- | --- | --- |
| WebGL2 支持状态 | 20/20 为 true，含全部六次攻击 | 不新增区分条件 |
| 扩展数、纹理/视口上限、线宽 | 不随本次攻击改变；部分值随正常渲染路径变化 | 不据此拟合阈值 |
| Native / Web renderer 文本不一致 | 六次攻击全部出现；14 次无插件采集均未出现 | 保留诊断观察，尚不能准入通用强告警 |
| Web renderer 出现 Direct3D 标记 | 六次攻击全部出现；14 次无插件采集均未出现 | 保留原 observation_only 角色 |

后两行是对本批受控记录的观察计数，不是独立测试集上的 TPR / FPR。
本轮只覆盖同一 Mac 的两种模拟器渲染路径，没有覆盖正常但 renderer 不一致的条件，
也没有测试不同伪装字符串；当前恰好区分本批记录，不足以证明普适语义。

按现有规则适用性检查：

- `NW-005`：host 的 10 份记录均 UNKNOWN，原因是当前具名 GPU 家族解析范围不能
  判断 Apple M4 这组操作数；swiftshader 的 10 份记录均 NOT_APPLICABLE。
  不能把 UNKNOWN 或软件路径排除改作违规。
- `OFFDER-GPU-001`：host 的三次攻击产生关系 COUNTEREXAMPLE，其余七份为 MATCH；
  swiftshader 的十份仍不适用。全部 20 份风险候选状态均为 NOT_ELIGIBLE，
  因为此规则仍是 observation_only。COUNTEREXAMPLE 不等于已输出模型告警。

跨 Native / App Web 的关系还超出当前 W0 的单表面输入范围。因此，本轮明确决定：
**不把上述观察直接放入现有选择器，不报告检出提升，不改写旧数据。**

下一步应先做 renderer 声明关系的语义与正常反例审计，产出包含适用条件、UNKNOWN
处理和范围要求的候选卡。可以先使用既有材料和官方源码，不要求立即新增真机。
如果仍缺少支持一般化的证据，就保留观察性结果；在同一环境反复增加同一种攻击次数，
不能补齐这项语义缺口。

## 可复核材料

- `runs/*/backend/raw_expanded_payloads.jsonl`：原始接收 payload。
- `runs/*/attempts/*/AUTOMATION.json`：连接、启用插件、导航记录。
- `runs/*/attempts/*/ATTEMPT.json`：阶段、会话、raw 行号和成功/失败状态。
- `ROWS.json`：12 字段原值、状态及两条既有关系的结果。
- `TRIPLETS.json`：逐组修改、非目标字段与恢复对照。
- `SUMMARY.json`：计数、普通/匹配控制对照与边界。
- `TESTS.log`：七项针对未知、失败、遗漏阶段、非目标变化及恢复的边界测试通过。
- `VERIFICATION.log`：从原始材料重算并核对保存结果。

全部专用进程与端口在执行后关闭。本轮只新增该研究目录，未提交推送或公网部署，
未访问独立确认材料，也未触碰历史训练结果。
