# Renderer 声明关系：官方语义、正常路径与候选准入

日期：2026-10-01。状态：**审计完成，两个新方向均不升级为告警候选，现有 NW-005 范围不变。**

本轮承接 [两条渲染路径的成对验证](../webgl2_paired_paths_v1/REPORT.md)，只做语义与反例核查。
交付三张候选卡、七条分级证据、十二份官方来源和七项本地依据，以及十个合成边界校验。
没有新采集、训练、模型预测、阈值选择、规则注册表修改或独立确认访问。

## 结论与处置

| 条件 | 能说明什么 | 本轮处置 |
| --- | --- | --- |
| Native / Web renderer 原文不同 | 两个上下文的描述字符串不同 | 不准入独立告警，保留诊断 |
| Android App Web 的 vendor/renderer 含 Direct3D / Windows | 声明了相应后端文本 | 保持 OFFDER-GPU-001 的 observation_only 角色 |
| NW-005 已知 GPU 家族不同 | 当前封闭范围内的家族声明不一致 | 保留原 v2 研究候选，不扩大解析范围 |

这些决定不抹去此前测得的修改效果：六次干预都改动了 renderer，恢复也完成。
区别在于，**“能发现本批字符串被改了”还不足以证明“这种字符串关系可以普遍作为告警”。**

## 字段到底来自哪里

本仓库 Native 采集器创建自己的 EGL pbuffer/context，然后读取 GL_VENDOR / GL_RENDERER。
`native_gpu_renderer` 和 `egl_renderer` 来自同一个 `glRenderer` 局部变量，不能当作两项独立证据。
App Web 采集器则从 WebGL1 上下文的 `WEBGL_debug_renderer_info` 扩展读取 unmasked 值；
扩展不可用时保留 `Unknown`。这时即便采集状态可记录为 observed，语义比较仍应弃权。

Khronos 将扩展返回值定义为底层图形驱动的描述。GLES 参考文档也明确认为 vendor + renderer
能够识别平台，并描述其跨版本稳定性。因此，“renderer 完全没有身份意义”同样不成立。
但这段说明针对 GL 实现所报告的平台，不能直接推出不同驱动、转译层和浏览器上下文必须返回
逐字相同的文本；这是本轮依据源码作出的范围判断。
参见 [WebGL 扩展规范](https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/)
与 [glGetString 参考](https://registry.khronos.org/OpenGL-Refpages/es2.0/xhtml/glGetString.xml)。

Chromium 134 的 Blink 实现，在扩展已启用时直接取当前 WebGL context 的 GL_RENDERER；
其下层可以包含图形转译。不要把普通 GL_RENDERER 查询中的通用 `WebKit WebGL` 文本与本项目采集的
unmasked 字段混为一谈。[对应源码](https://github.com/chromium/chromium/blob/134.0.6998.135/third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc#L3853)

## 为什么完整字符串相等不是可靠前提

按实测 WebView 的版本号选择 Chromium `134.0.6998.135` 标签，并根据 DEPS 选择 ANGLE
`914c97c116e09ef01a99fbbbe9cd28cda56552c7`。这里固定的是审计源码，**没有证明运行中的 WebView
二进制一定由该源码构建，也没有证明它启用了所有被审计的分支**。

ANGLE 正常构造 renderer 时，会拼接 backend vendor、renderer 和 version，并移除组成部分中的逗号。
版本细节还受 `isWebGL()` 影响。GL 后端支持裁剪部分 AMD renderer 中的 DRM 等细节，
官方测试保留了相应转换示例。因此，即使底层家族相同，包装或版本粒度不同仍可造成原文差异。
这支持否定“跨实现上下文必然逐字相等”的普遍前提。
参见 [renderer 构造](https://github.com/google/angle/blob/914c97c116e09ef01a99fbbbe9cd28cda56552c7/src/libANGLE/Context.cpp#L3394)、
[GL 后端处理](https://github.com/google/angle/blob/914c97c116e09ef01a99fbbbe9cd28cda56552c7/src/libANGLE/renderer/gl/DisplayGL.cpp#L36)
及 [对应测试](https://github.com/google/angle/blob/914c97c116e09ef01a99fbbbe9cd28cda56552c7/src/libANGLE/renderer/gl/DisplayGL_unittest.cpp#L48)。

Android 的 ANGLE 文档还描述了应用级 native / angle / default 驱动选择，说明转译层并不是攻击专属现象。
但是，上述条件性代码路径与 Linux/AMD 示例，**不能记成已在本 App 的 Android 真机上采集到的正常不等反例**。
当前二十份实测材料中，十四份无插件采集的 Native/Web renderer 都相等。
[Android 驱动选择文档](https://github.com/google/angle/blob/914c97c116e09ef01a99fbbbe9cd28cda56552c7/doc/DevSetupAndroid.md#L66)

## 为什么 Direct3D 标记仍只作观察

支持这个方向的事实是：ANGLE 的平台表把 Direct3D 列在 Windows 后端，而 Android 列出 GLES/Vulkan；
本批插件又恰好把 renderer 改成带 Direct3D11 的 NVIDIA 声明。
但模拟器的 Android 客体与图形宿主不是同一概念，不能由客体 OS 直接排除宿主渲染。
[ANGLE 平台矩阵](https://github.com/google/angle/blob/914c97c116e09ef01a99fbbbe9cd28cda56552c7/README.md#L24)

Android 官方模拟器设置页列出了 Windows ANGLE Direct3D 的正常选项。
同时，当前加速配置页说明 `angle` 自 27.0.2、`angle_indirect` 自 34.2.14 起弃用。
因此，本轮只能说**存在官方描述的合法宿主路径，并且必须限定版本**，不能说旧选项是今天推荐的模式。
ANGLE 的 D3D11 renderer 实现确实会在正常后端描述中加入该标记。
参见 [模拟器设置](https://developer.android.com/studio/run/devsite-two-way-merge-new)、
[加速选项及弃用信息](https://developer.android.com/studio/run/emulator-acceleration#accel-graphics)
和 [D3D11 描述实现](https://github.com/google/angle/blob/914c97c116e09ef01a99fbbbe9cd28cda56552c7/src/libANGLE/renderer/d3d/d3d11/Renderer11.cpp#L2285)。

仍缺的一步是 Windows 实测：尚未验证某一指定 Emulator/WebView 组合如何把宿主描述传到这四个采集字段。
这不是已经观测到的字段级正常 Direct3D 反例，也不能计算正常误报率；但足以说明目前无法把
“Android + Direct3D”当作无条件的攻击语义。既有 OFFDER-GPU-001 仍为 observation_only，
即使关系输出 COUNTEREXAMPLE，风险候选资格也仍为 NOT_ELIGIBLE。

## 现有家族规则保留什么边界

NW-005 当前比较的是两个 renderer **报告的家族**，不是证明物理 GPU 身份或攻击意图。
只有 observed、类型正确、非占位且能各自解析为一个已支持家族的值，才进入关系比较。
已支持家族为 Adreno、Mali、PowerVR、Tegra、Vivante；软件路径不适用，未知/多家族保持 UNKNOWN。

本轮不新增 Apple/NVIDIA，也不把“需要证明同物理渲染路径”重新加回 v2 前置条件。
真实路径及其授权属于归因问题，原 v2 已将其与声明一致性风险分开。
另一方面，保留这个研究候选也不意味着已证明所有合法双 GPU / 转译条件下家族都应相同。

现有二十行中，host 十行仍为 UNKNOWN，SwiftShader 十行仍为 NOT_APPLICABLE；
既有历史三百七十八行的 Native 都是 SwiftShader。因此，不能靠修改软件排除项或迎合本次 NVIDIA
伪装字符串，把这些数据变成 NW-005 的新合格证据。
另外，跨 Native/App Web 关系超出当前 W0 单表面输入；未来若引入，须单独版本化输入与对照协议。

## 复核结果与指标

- 十个合成边界全部通过：同家族不同包装、已知家族冲突、未知家族、多家族、软件路径、
  observed 占位值、错误观测状态、错误类型、相等但含 Direct3D 的字符串、缺少观测状态。
- 从二十份既有 raw payload 重算图形投影、诊断与两个现有关系，全部与保存结果一致。
- 六份干预的两个文本诊断均为 T，十四份无插件采集均为 F。这是本批观察计数，不是独立 TPR/FPR。
- 十九项来源记录的三十四个精确文本锚点，以及候选卡/反例之间的引用关系均通过检查。
- 新告警候选 **0**，新运行样本 **0**，模型 fit **0**，模型 predict **0**。

最近的 CAP7 结果仍为 **117/126（92.86%）**，内部对照 **0/252**，WebGL 单项仍 **0/9**。
此前相对 CAP6 的 +9 条 / +7.14 个百分点仍成立；**本轮没有进一步提升，也没有重跑得到下降**。
这些仍是已暴露开发材料的结果，不是独立确认或真实用户误报率。

## 下一步建议

先把这两个 renderer 文本方向作为“观察有效、告警语义不足”的阶段结果收口，保留 CAP7。
现阶段直接重训，缺少新的合格候选与可比较输入，不能合理期待补回九条 WebGL 漏检。

若继续针对 WebGL 推进，建议下一步先做**可执行行为与声明是否自洽的可行性设计**：
核查现有 WebGL API 的真实执行结果能否提供不同于可替换字符串的证据，并先列出正常浏览器、驱动和软件路径的变化边界。
这只是新的待验证假设，不保证能检出，也不在本轮实现或执行。
Windows 无攻击最小对照可用于解决本轮具体的字段暴露疑问；它需要可用 Windows 宿主及明确支持该模式的版本，
不需要重新收集真机，但也不能用同一 Mac 再跑几次替代。

## 材料与重现

- [候选卡](CANDIDATE_CARDS.json)：表达式、输入、适用条件、UNKNOWN 和准入结论。
- [来源登记](SOURCE_REGISTER.json)：官方版本、链接、缓存路径、精确锚点和结论限制。
- [反例与未决问题](COUNTEREXAMPLES.json)：静态、运行、合成证据分开。
- [合成输入](BOUNDARY_CASES.json)、[逐项结果](BOUNDARY_RESULTS.json)、[校验汇总](SUMMARY.json)。
- `sources/` 与 `FETCH_LOG.json`：官方源码/文档本地副本及获取记录。

只读复核（不访问网络、不采集、不训练）：

```sh
python3 -B deliverables/renderer_semantics_review_v1/verify.py
```

`--write` 仅重建本目录的两个结果 JSON；`fetch_primary.py` 是显式网络刷新工具，不在常规复核中调用。
本轮仅新增这个研究目录；保留上轮本地改动，没有提交、推送、部署或修改攻击侧仓库。
