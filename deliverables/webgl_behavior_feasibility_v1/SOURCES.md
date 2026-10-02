# 语义与实现依据

核查日期：2026-10-01。这些来源支持接口契约，不能替代本轮运行结果或攻击归因。

| 依据 | 核查内容 | 范围 |
| --- | --- | --- |
| [Khronos WebGL 1.0 规范](https://registry.khronos.org/webgl/specs/latest/1.0/) | GLenum 是 unsigned long；getParameter 接受 GLenum；无效 pname 应产生 INVALID_ENUM 并返回 null | 接口声明与错误返回语义，不是 GPU 身份约束 |
| [Web IDL 标准](https://webidl.spec.whatwg.org/) §3.2.4.6 / §3.2.4.9 | unsigned long 的 JavaScript 转换使用整数转换算法，首先 ToNumber；本轮小正整数与对应十进制字符串得到同一枚举 | 不使用对象 valueOf、溢出、NaN、代理入参等额外边界 |
| [debug renderer 扩展规范](https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/) | 两个 unmasked 查询枚举及其字符串返回 | 是否暴露扩展取决于浏览器，不能强迫扩展存在 |
| [Khronos 测试的 Chromium 固定镜像](https://chromium.googlesource.com/chromium/deps/webgl/sdk/tests/+/ca8d511e3fa5808f8a43bf92a5a6130ce77f78de/conformance/extensions/webgl-debug-renderer-info.html) | runTestDisabled / runTestEnabled 明确区分启用前 INVALID_ENUM 与启用后 NO_ERROR | 历史上游测试，未在本轮直接运行该测试页面 |
| [Chromium 134 的 getParameter 实现](https://github.com/chromium/chromium/blob/134.0.6998.135/third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc#L3853) | 未启用 debug renderer 扩展时，返回 null 并产生 INVALID_ENUM；启用后取下层 renderer | 按所测 WebView 版本选择源码标签；没有做二进制构建认证 |
| [Chromium 134 的 enableVertexAttribArray 实现](https://github.com/chromium/chromium/blob/134.0.6998.135/third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc#L3090) | index 达到 MAX_VERTEX_ATTRIBS 时产生 INVALID_VALUE | 支持低分配量的能力边界控制，不测试 GPU 性能 |

Chromium 源码本地副本复用 [上一轮来源缓存](../renderer_semantics_review_v1/sources/chromium134_webgl.txt)，
没有再次下载或复制整仓库。

本轮真正执行的是已安装的 `puppeteer-extra-plugin-stealth 2.11.2` 中 `webgl.vendor`：

```
deliverables/rule_semantics_raw_only_expansion_v1/runtime/tool_node/node_modules/puppeteer-extra-plugin-stealth/evasions/webgl.vendor/index.js
```

源码先调用原 getParameter，再用原始入参的严格数值比较决定是否替换两个返回值。
这个流程给出两项事前假设：未启用扩展时仍可能返回伪装字符串；字符串形式枚举可能绕过该分支。
两者是同一个实现局限的不同表现，不按两个独立机制计算贡献。
自动化记录校验安装版本并保存实际配置；协议继承的攻击仓库提交号仅是前轮上下文，
不表示本轮从那个提交重新构建或验证了攻击仓库。

执行前保存了 `PROTOCOL.json`，开始时复制了五份直接参与执行/判定的源码到 `source_snapshot/`。
只读复核检查这些文件与快照一致；判定器在观察结果后没有修改。
采集使用既有本地 App v13 APK，不改正式 177 字段或 Web 67 字段合同，
行为观测以独立 `BEHAVIOR.json` 与同会话原始 payload 对应。
