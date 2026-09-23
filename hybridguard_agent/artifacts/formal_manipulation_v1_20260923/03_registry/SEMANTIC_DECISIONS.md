# S03 语义裁决

审定日期：2026-09-23。实现基线：`b3d8badee44577787bdcd3cb22d70a155b1bb613`；目录：`paired244_rule_catalog.v3.json`。本文件与本目录的机器可读台账共同描述 S03 覆盖层，不修改冻结 v3 或 P3/P6 结果。

## 1. 来源、适用性与角色分别维护

87 项目录中，57 项 ACTIVE 全部且唯一登记。来源按现有目录的 `source_lane` 和 `empirical_selection_applied` 判定，得到 E 23、O_u 9、H 14、C 11；没有版本数量差异，也没有为满足数量重分组。

- E：已有设备关系或经验研究关系。10 项的早期逐条筛选过程没有完整版本记录，保留缺口；引用官方定义作为门控依据不会把 E 变成 O_u。
- O_u：官方定义经过研究者推导、且当前目录未标记本轮经验筛选的 9 项。未标记不等于从未筛选，更不等于“纯官方规则”。
- H：官方定义、研究者推导和已记录的经验筛选共同构成的 14 项。当前统计仅说明来源流程，不说明报警有效性。
- C：采集器一致性、上下文和项目部署合同。其经验验证标志不改变 C 归属。

`official_definitions` 记录文档及其适用产品；`researcher_derivation` 记录谓词、参数与实现位置；`empirically_screened/screening_scope/discovery_split_ref` 记录筛选；`tolerance_source` 单独记录容差。1 CSS pixel、历史上下文阈值、模型 token 归一化和 GPU 字族名单均不能称为官方攻击判据。本步没有重新筛选或调整容差。

`provenance_group` 回答从何而来，`applicability_id` 指向当前字段条件，`decision_role` 回答允许承担何种作用。ACTIVE、COUNTEREXAMPLE、适用性 SUPPORTED 或来源组成员身份均不自动授予报警资格。SUPPORTED 在本步仅指已声明的观察范围成立。

## 2. UA reduction 必须区分产品

| 产品 | 本轮核实的范围 | S03 处理 |
|---|---|---|
| 桌面 Chrome | Chromium rollout 的 phase 5 从 M107 开始 | 不复制为 Android 或 WebView 条件 |
| Android Chrome（手机/平板） | phase 6 从 M110 开始，2023-05-11 更新记录 Android 110+ 客户端完成推出；还有提前试用与退出阶段 | 版本不是单条会话采用默认 UA 的证明 |
| Android WebView | 当前 Android 官方文章说明从 Android 17 起缩减默认 UA；默认形态含 Android 10 与 K；自定义 UA 有单独说明 | 使用独立产品范围，不沿用 Browser 的 >=107 |

依据：[Chromium UA reduction 时间表](https://www.chromium.org/updates/ua-reduction/)、[Android WebView UA reduction](https://android-developers.googleblog.com/2024/12/user-agent-reduction-on-android-webview.html)。后者页面标注的初始发布日期为 2024-12-06，本轮记录的是 2026-09-23 访问的当前正文，具体修订号 UNKNOWN，不能用初始发布日期证明正文当时已经如此。

冻结 `P3-UA-REDUCED-BROWSER` 使用 Chrome >=107 和 Android 10，并未要求 K；这与产品细分时间表不一致。新台账明确保留该差异和 observation_only 角色，原谓词、参数和旧结果保持不变。公共门控遇到 `Android 10; K` 缩减形态时，不把其暴露 OS/model 当成真实设备值；早于普遍推出的 opt-in 或模拟形态也不提供可比较的型号事实。完整非 K token 也不会仅凭版本被认定为可信默认 UA。

WebView 的 `getDefaultUserAgent` 与实例 `getUserAgentString` 是不同观测，实例 UA 可设置。[WebSettings API](https://developer.android.com/reference/android/webkit/WebSettings) 与 [DevTools UA override](https://developer.chrome.com/docs/devtools/device-mode/override-user-agent) 均说明合法覆盖渠道。当前采集代码先保存 settings，再执行 JS probe；两个 host 字符串相同不能证明后续 JS 读取期间没有合法覆盖。这里缺的是采集语义前提，不要求新增签名、远程证明或补日志。

Native `Build.VERSION.RELEASE` 是面向用户的 opaque string，不保证数字格式；`Build.MODEL` 是产品型号名称，不是与所有 UA token 一一对应的标准 ID。[Build.VERSION](https://developer.android.com/reference/android/os/Build.VERSION)、[Build](https://developer.android.com/reference/android/os/Build)。只对明确可解析值讨论关系，K、预览字符串、歧义 token 和不明别名不强行补齐。

## 3. Dalvik/System agent 与当前 JS UA 不互换

collector 的 `system_http_agent` 来自 `System.getProperty("http.agent")`。AOSP 默认构造使用 Dalvik、系统版本以及符合条件时的 MODEL/Build.ID；这只说明该实现的默认构造，不证明任意历史会话保留默认值。[AOSP RuntimeInit](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/master/core/java/com/android/internal/os/RuntimeInit.java)。固定 Android 16 tag 的访问失败，替代使用官方镜像 master 阅读构造逻辑；历史样本对应的实现修订仍为 UNKNOWN。

`http.agent` 是可变的进程属性；合法 `System.setProperty` 可以保留 Dalvik 外观并改变内容。[System API](https://developer.android.com/reference/java/lang/System)。因此明确 Dalvik 语法只是比较范围的必要条件，不能证明属性来源未变；它也不是当前 WebView JS UA。默认 agent 和 Native 使用同一 Build 来源，不能算两个独立设备身份锚点。

## 4. GPU 是渲染路径描述

`WEBGL_debug_renderer_info` 暴露渲染实现描述，扩展可能因隐私策略不可用；它不认证物理 GPU。[Khronos 扩展，revision 8](https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/)。ANGLE 支持多种后端及 Android，单独出现 ANGLE 不等于 Windows。[ANGLE 项目文档](https://chromium.googlesource.com/angle/angle/+/main/README.md)。SwiftShader 可作为 CPU 驱动或 WebGL 回退路径；自动回退的弃用不等于所有软件路径非法。[Chromium SwiftShader 文档](https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/swiftshader.md)。Android Emulator 支持 host 与软件渲染选择。[Android 图形加速文档](https://developer.android.com/studio/run/emulator-acceleration)。移动主干文档的不可变修订号没有核实，台账保持 UNKNOWN。

门控将 SwiftShader、llvmpipe、softpipe、swrast、lavapipe、swangle 识别为不可做硬件族强比较的范围；掩蔽、未知或多义族保持 UNKNOWN。即使 Native 是 Adreno、WebView 出现另一个族或 Direct3D 字样，当前字符串仍不足以排除合法 host/remote/hybrid rendering，不能补用工具名、配置或环境组完成排除。

`NW-005` 比较硬件字族，`OFFDER-GPU-001` 检查桌面后端标记，二者相关但不等价。当前 collector 将同一个 `glRenderer` 赋给 `native_gpu_renderer` 与 `egl_renderer`；`P3-GPU-COPY` 是拷贝自洽观察，不是另一张支持票。三条在新覆盖层归入 `native_app_gpu_family`，原 evidence_family 全部保留。

## 5. 八条建议报警候选的本步处置

| 规则 ID | 本研究家族 | 允许的当前字段摘要 | 无法由当前合同确认的必要前提 | 最终角色 |
|---|---|---|---|---|
| NW-001 | model_app_ua | Native model、App UA、default/settings UA | 可比较型号及采集期间合法 UA 覆盖的排除；快照相等不证明持续默认来源 | observation_only |
| NW-002 | app_os | Native OS、App UA、default/settings UA | 排除缩减形态后，仍不能确认采集期间 UA 来源和合法覆盖边界 | observation_only |
| OFFDER-OS-001 | app_os | 同上 | 同上 | observation_only |
| NVW-001 | model_system_agent | Native model、system_http_agent | Dalvik 外观不证明可变属性保留默认来源 | observation_only |
| NVW-002 | host_os | Native OS、system_http_agent | 合法覆盖不能从当前属性值排除 | observation_only |
| OFFDER-OS-002 | host_os | 同上 | 同上 | observation_only |
| NW-005 | native_app_gpu_family | Native renderer、App WebGL renderer | 不能确认同一物理渲染路径并排除正常 host/remote/hybrid 路径 | observation_only |
| OFFDER-GPU-001 | native_app_gpu_family | Native/EGL renderer、App WebGL vendor/renderer | 同上；桌面后端词本身不足以判断非法操纵 | observation_only |

精确完整字段名、每条当前条件、反例与理由见 `source_registry.jsonl` 和 `applicability_policy.json`；不从此表摘要重建字段合同。威胁模型保留“Native 参照未被同向修改”的限定，但该限定不使合法 UA 覆盖或 host rendering 自动成为攻击。这八条分属五个建议家族，均已逐条审定，最终报警候选为 0。门控会在明确越界时返回 NOT_APPLICABLE，在合法前提无法确认时返回 UNKNOWN；不会返回攻击预测。

这比计划的小白名单建议更保守，依据是当前字段合同与合法反例，不是任何正式预测或检测率。不能把将来八个来源条件没有二值增量解释为来源没有价值；当前报警资格为空，本来就不具备这种比较的结构条件。后续若执行计划中的 S04，应保留该事实并单独说明合同可行性，不能悄悄晋级这些角色或把全弃判改成 NO_ALERT。本步不实现 S04。

## 6. 其他角色与公共门控

Bridge 属采集器合同；debug/cleartext、touch=0、测试环境为上下文；部署包/版本匹配是项目策略。普通跨容器差异、内存近似、屏幕/zoom 差异和传感器自洽不自动获得报警资格。传感器 positive flag 的隐含关系只在正前提下观察，false 和空列表合法；[SensorManager](https://developer.android.com/reference/android/hardware/SensorManager) 的默认传感器、权限与动态变化限制仍保留。[DisplayMetrics](https://developer.android.com/reference/android/util/DisplayMetrics) 表示应用可用显示信息，不能把采集器中的 physical 命名当物理屏幕等式；[CSSOM View](https://drafts.csswg.org/cssom-view/) 的 DPR/page zoom 和深度兼容语义也不提供攻击标签。

全部门控只访问每条声明的 `features`、`field_status`、`field_quality`，要求字段显式 observed 且质量可用。未知、非有限值、类型错误及特定 API 零哨兵不按“正常”解释；合法 false、touch=0 和空列表不丢失。UA、GPU 等必要语义条件未知时不会退回读标签、phase、工具、config、路径、session/install/group、回执或未来 post。合成测试证明这些元数据无法改变门控或补齐缺失前提。

9 条现有检查依赖独立 Browser 字段；其来源登记继续保留。S02 的 App177 材料没有 Browser 时保持缺失并返回 UNKNOWN，不复制 App Web 字段填造 Browser。

## 7. 家族、等价与来源消融

57 条映射到 27 个 decision_family，其中 9 个跨来源共享。`source_overlap_matrix.csv` 枚举全部 1,596 个无序规则对，区分公共有效域上的完全重复、同族但不等价、共享输入但主张不同及无声明输入重叠。无重叠不代表统计独立。

只有以下四对在共同有效字段域及归一化关系 outcome 上记为完全重复：`NW-002 / OFFDER-OS-001`、`NVW-002 / OFFDER-OS-002`、`NVW-005 / OFFDER-DEVCONFIG-001`、`CORE-002 / OFFDER-BRIDGE-001`。最后一对限定固定 FeatureApp 投影，不推广至任意执行 envelope；可用性分支和解释文本不承诺逐字相同。`OFFDER-UA-002 / P3-UA-DEFAULT` 使用同一 UA 对，但前者派生事实会 trim 字符串、后者比较原始值，不能记为完全等价。

公共 C 固定 11 条。八组合位序固定为 O_u/H/E：000=11、001=34、010=25、011=48、100=20、101=43、110=34、111=57 条；各条件精确 ID 和相同公共门控列于 `source_conditions.json`。四来源别名 C/B0、E、O、EO 分别对应 SRC-000、SRC-001、SRC-110、SRC-111；O=O_u∪H。别名不得增加独立样本或重复运行，同 payload 的不同评估单元也不能因此合并。

删除 O_u/H 谓词仍保留公共 UA/GPU/未知语义门控，只能称“来源分组消融”，不能称完全移除官方知识。本步仅定义成员关系和共享证据身份，不实现家族 OR 聚合、score、阈值或任何报警输出。

## 8. 证据限制与查阅边界

本轮查阅 19 份相关一手文档，保存适用产品、可确认版本、访问日期和范围；无法确认的修订及未重新联网核实的旧引用逐项进入 `source_uncertainties.jsonl`。来源修订 UNKNOWN 不等同于定义不存在，也不能伪装为历史样本版本已证实。AOSP 固定 tag 一次访问失败后保留缺口，没有继续无限追查。

读取 P6 SOURCE_COVERAGE/SOURCE_OVERLAP 仅用于既有来源、家族和历史条件边界；未用旧重叠统计、命中或新预测决定角色，未读取正式逐样本 predictions。攻击仓库 week10 的 W7/W6 台账是独立命名空间，不凭类似名字或数量合并为主仓库 57 条。

S01 的 262 条事实、任务准入和 3 个环境关联组保持不变；这些组不是已证明的独立物理设备。54 条时间对照 no_intervention 仍为 UNKNOWN，相关 FPR 资格仍受限。S02 的 262 条转换成功、0 拒绝及 88 组阶段关联完整保留。缺件、较低证据和执行回执的限制不因 S03 改变；没有补采、补日志或 LLM 调用，也没有真实样本预测、检测性能计算及阈值修改。
