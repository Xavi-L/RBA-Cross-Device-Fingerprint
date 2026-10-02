# WebGL 候选条件：语义、原始输入与适用范围

日期：2026-10-01。性质：**已暴露开发材料上的事后可行性核查**，不是新模型性能实验或独立确认。

**本轮没有准入新的 GPU 报警条件，也没有重训。** 已有 `NW-005` 家族关系在这批输入上均不适用，`OFFDER-GPU-001` 后端标记缺少独立风险资格；直接比较 renderer 字符串也缺少普遍成立的语义依据。另外，发现并在桌面浏览器复现了 WebGL2 采集假阴性，后续应先修复测量方式。

七条版本固定为开发参照：[BASELINE.json](BASELINE.json) 引用提交 `512ac0b7` 的三个原模型及原始结果，仍为 **117/126 检出、0/252 内部对照报警、378/378 明确输出**。本轮没有得到新的检出率或提升数字。

## 1. 输入与核查方法

只读取上一轮合同的 378 个成员：API29、API30、API36 各 126 条，共 126 个前态—干预—后态 triplet；126 条干预、252 条内部对照。按合同中的 source_ref/session_id 从 9 份原始归档提取记录，没有增加样本或读取独立确认材料。

核查范围包括 5 个 Native 图形字段和 7 个 Web 图形字段、原始字段状态、已有候选登记、采集源码、官方文档。将两个已有 v2 单关系合同分别应用于每条记录，共 756 次关系核查；这不是调用训练器或模型预测器。阶段、配置和环境标签只用于汇总，没有进入关系求值的四字段输入。

原始状态保留为 observed、NOT_APPLICABLE、NOT_ELIGIBLE、UNKNOWN 等。`SUMMARY.json` 中字段 usable 仅指显式 observed、类型有效且非空哨兵，不表示采集语义一定正确；WebGL2 历史 false 就是反例。

## 2. 实际字段有什么规律

12 个图形字段在全部 378 条记录中都有显式 observed 状态和有效类型。字段存在不等于适合构造硬件关系。

| 核查项 | 实际结果 | 含义 |
|---|---|---|
| Native renderer | 378/378 为同一个包含 Android Emulator、ANGLE、SwiftShader 的字符串 | 三个 Android 环境只有一种已观察 Native 图形实现，未形成跨 GPU 路径证据 |
| Native vendor / EGL vendor | 分别固定为 `Google (Google Inc. (Google))` / `Android` | 名称对应不同 API 层，不要求这两个字符串相同 |
| native_gpu_renderer / egl_renderer | 378/378 完全相等 | 当前采集器将同一次 GL_RENDERER 读取写入两个字段，并非独立佐证 |
| Web vendor/renderer | 360 条保留软件渲染描述，18 条变为 NVIDIA / Direct3D11 描述 | 18 条全在干预态，内部对照为 0/252；这是词汇出现计数，不是规则检出率 |
| WebGL 扩展数 | API29/30 为 21，API36 为 19 | 环境差异，同一 triplet 内不变 |
| 纹理尺寸、viewport、线宽 | 分别固定为 4096、8192x8192、1-1 | 当前干预没有改变这些字段 |
| webgl2_supported | 378/378 为 false | 存在采集上下文复用问题，不能解释为这批设备都不支持 WebGL2 |

18 个图形变化 triplet 中，9 个是 `w9-stealth-boundary-webgl-pair-v1`，另 9 个是 `w6-tool-058-legacy-default-v1`。变化都只落在检查范围内的 Web vendor/renderer，后态恢复；其他图形字段不变。CAP7 已检出后一组 9 条，漏掉的是前一组。因此不能把“观察到 18 个标记”写成“可能新增 18 个检出”。这里只核对了旧预测，没有把这些标记加入模型重新预测。

原始字符串变化表明干预效果被采到了；并不能单靠字符串认定实际 GPU、物理渲染路径或未经授权的攻击。

## 3. 以当前 v2 语义为准，不能沿用旧版结论

早期 v1 将两条 GPU 关系都列为 observation_only；当前 [v2 登记](../../hybridguard_agent/config/formal_manipulation_role_gate_v2/applicability_policy.json) 已修订 `NW-005`。本轮以 v2 求值结果为准：

| 关系 | 当前角色和条件 | 本批结果 | 处置 |
|---|---|---|---|
| NW-005 | 可作有限的已报告硬件家族一致性风险候选；两端须能唯一解析出已登记家族，排除软件/遮蔽值 | 378/378 NOT_APPLICABLE；风险可用 0/378 | 不接入本轮数据的重训 |
| OFFDER-GPU-001 | Windows/Direct3D 后端词汇观察；仍为 observation_only | 关系 378/378 NOT_APPLICABLE；风险资格 378/378 NOT_ELIGIBLE | 保留诊断用途 |

`NW-005` 不再要求先证明同一物理路径，才能成为有限的研究风险线索；实际攻击归因仍为 UNKNOWN。**这次阻碍是全部 Native 输入均为软件渲染，不是无法证明物理同源。** 此外，现有家族表只有 adreno、mali、powervr、tegra、vivante；NVIDIA 字符串也不在这个解析器的已知家族内，不能把未知解析结果改成冲突。

已有 W0 是 App Web 单表面候选池，这两条 Native↔Web 关系都不在其白名单中。若以后加入有效跨表面候选，需要另设输入扩展对照，不能仍宣称只修改了原有 W0 的一条条件。完整定义及当前角色保存在 [REVIEWED_RULES.json](REVIEWED_RULES.json)。

## 4. 其他候选为什么暂时不能直接加入

完整逐项处置见 [FEASIBILITY.json](FEASIBILITY.json)。

| 候选方向 | 证据与边界 | 当前结论 |
|---|---|---|
| Native/Web renderer 原文不相等 | 在当前数据上只出现于上述 18 条干预；但 `Adreno (TM) 650` 与 ANGLE 包装后的同家族名称就能原文不同 | 有区分度的观察，不是通用异常条件 |
| 同一 Web 的 vendor/renderer 名称冲突 | 当前攻击成套修改，两者都写 NVIDIA；vendor 还可能描述实现供应商或包装层 | 未建立可验证命名关系，不能宣称有检出收益 |
| 图形数值能力差异 | 已检查的扩展数、纹理/viewport/线宽在各 triplet 内不变 | 当前没有新增干预区分信号 |
| Native GLES 版本与 WebGL2 支持不一致 | API/上下文能力不能直接等同，且历史 WebGL2 测量有缺陷 | 先解决采集语义 |
| 与前态或后态相比发生变化 | 确实存在 18 组变化后恢复 | 可用于干预效果诊断；不是当前单次观测模型的候选输入 |

最后一项若发展成时序检测，必须另行定义可信前态和合法配置变化；不能把阶段标签或未来 clean_post 当作当前检测器特征。

“没有可直接准入的条件”不等于 GPU 信息没有研究价值，也不禁止研究有误报可能的经验假设。它表示当前只覆盖一种软件图形路径，既没有证明这些字符串关系的稳定性，也没有测到合法渲染路径切换时的代价。应先补这个最小证据缺口，再决定候选表达。

## 5. 官方语义与采集源码复核

本轮实时核对的官方来源及各自支持/不支持的结论见 [PRIMARY_SOURCES.json](PRIMARY_SOURCES.json)：

- [Khronos WEBGL_debug_renderer_info](https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/) 定义查询的是图形驱动描述，并说明隐私遮蔽和扩展暴露问题；它没有规定 Native/Web 字符串必须逐字相同。
- [Chromium SwiftShader](https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/swiftshader.md) 区分 GLES 驱动模式与 WebGL 软件回退模式。[ANGLE](https://chromium.googlesource.com/angle/angle/+/main/README.md) 支持多个 API 后端，Android 也使用 ANGLE。因此软件或 ANGLE 标记本身不是攻击。
- [Android Emulator 图形加速文档](https://developer.android.com/studio/run/emulator-acceleration#accel-graphics) 允许宿主 GPU 和多种软件渲染模式。由 guest Android 身份推断唯一物理 GPU 路径，缺乏依据。

仓库 Native 采集器 [ExpandedFingerprintCollector.kt](../../android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/ExpandedFingerprintCollector.kt) 创建独立 EGL/GLES 上下文，读取 GL_VENDOR、GL_RENDERER；第 391–396 行将同一个 glRenderer 写入两个 renderer 字段。

[canonical_web_probe.js](../../web_probe/canonical_web_probe.js) 第 324–325 行在同一 canvas 上先请求 webgl/experimental-webgl，再请求 webgl2。按 [HTML canvas 上下文规则](https://html.spec.whatwg.org/multipage/canvas.html#dom-canvas-getcontext)，已有不同类型上下文会使请求返回 null；因此第二步不是独立的能力探测。

最小桌面浏览器实测结果：

| 创建顺序 | 结果 |
|---|---|
| canvas A 先 WebGL1 | true |
| canvas A 再 WebGL2 | false |
| 独立 canvas B 请求 WebGL2 | true |
| canvas C 先 WebGL2、再 WebGL1 | true、false |

同一浏览器确实支持 WebGL2，却会被旧顺序测成 false，已确认这个实现缺陷。复现页面为 [context_probe.html](context_probe.html)，实际结果为 [BROWSER_CONTEXT_RESULT.json](BROWSER_CONTEXT_RESULT.json)。它只验证上下文模式行为，不证明任何历史 Android WebView 的 WebGL2 支持情况；不能把旧的 378 个 false 批量改成 true。

WebGL2 当前没有入选七条模型，本轮发现不自动改变之前保存的七条结果；未来修复后的值也不能偷偷回填原训练输入。

## 6. 下一步与所需资源

建议下一步做一个独立的采集修复小轮次：为 WebGL1 和 WebGL2 使用独立 canvas，处理上下文不可用的边界，更新探针版本及相应声明，完成合成边界测试和浏览器/现有模拟器冒烟验证。需要当前仓库、浏览器和已有 Android 模拟器，不需要借真机或更改攻击工具的规则。

为了继续研究 WebGL 检出，再补少量**无攻击的合法图形路径对照**：在可用模拟器上分别检查默认、host、软件渲染设置下的 Native/Web 观测；不支持的模式如实记录。它可检验字符串/路径假设的反例，不能替代硬件 GPU 家族数据。若要验证现有 NW-005，仍需能实际产生可比较已知硬件家族的环境；切换模拟器设置不保证满足这一条件。

随后才能决定是否登记新的有限风险候选。七条基线已经满额；即使未来有新信号，固定七条时仍可能发生取舍。第八条容量变化和候选变化应分别比较，不能承诺直接达到 126/126。

本轮在可行性核查处结束：新增拟合、阈值拟合、模型预测均为 0；现有累计拟合记录仍为 201。没有改采集器、旧合同、七条模型或原始数据，没有自动重训或推送。

## 7. 验证与重现

7 项重点边界测试覆盖：显式字段状态、ANGLE/同家族合法差异、真正家族差异但归因未知、六种软件路径、遮蔽/未知/歧义/未支持家族、后端标记无独立风险资格，以及标签隔离。测试结果见 [TESTS.log](TESTS.log)。

保存产物复核直接回读原始 JSONL 的对应行，核对 378 条成员、12 个字段的原值/状态、126 组配对、旧 CAP7 预测及标记出现的重叠范围；不会重新执行关系、拟合或模型预测。结果见 [VERIFICATION.json](VERIFICATION.json)。

```sh
python3 -B deliverables/rule_semantics_webgl_feasibility_v1/verify_saved.py
python3 -B -m unittest discover -s deliverables/rule_semantics_webgl_feasibility_v1 -p test_audit.py -v
```

`audit.py` 默认只读重算本次关系核查；`--write` 仅用于首次生成并拒绝覆盖现有产物。浏览器复现可在本机静态服务打开 context_probe.html，不读取或上传研究样本。
