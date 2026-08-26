# HybridGuard 顶层三端一致性规则对浏览器指纹攻击数据判别能力验证报告

**验证日期：** 2026-08-21

**规则对象：** 顶层 HybridGuard 项目的 27 条自然语言三端一致性规则，而不是子项目自身的 Week 7 机制规则。

**攻击数据来源：** 子项目 hybridguard-browser-fingerprint-research，已快进到 025690a2c330ba47a6a367787cf313e2a9bdda82。

**结论口径：** 同源 clean_pre → attack → clean_post 的条件性差分审计，以及 Week6 的受控字段变异敏感性检查；不是跨设备攻击检测率、FPR、准确率或未知攻击泛化结论。

> 范围纠正：先前放在子项目中的“ 一致性规则对攻击数据判别能力验证报告_20260821.md ”考察的是子项目 Week 7 规则，规则对象不符合本任务。本文才是针对 HybridGuard 顶层规则库的正式报告；前一份文件不应被引用为本任务结论。

## 一、结论摘要

顶层 HybridGuard 规则库不是“只有第一类攻击能区分”。以顶层规则的自然语言语义和其现有 38 个 consistency 特征重算后，得到以下分层结论：

| 数据轨 | 可直接区分的情况 | 当前不能可靠区分的情况 | 应如何表述 |
|---|---|---|---|
| 2026-08-12 formal CDP | 9/9 个 active 均有多条直接跨层冲突：R3、R10、R17、R19；R9、R18、R26、R27 进一步支持 | 无 | “该受控 CDP 条件下，规则对同源三态样本有稳定差分能力” |
| 2026-08-12 formal Stealth | 无可固定二值化的直接规则命中 | 6/6 active；仅 R26 平均分统一下降 0.1，不能单独作为阈值分类器 | “当前规则对该 Stealth 指纹规避场景没有可靠的独立判别能力” |
| Week6 desktop UA 受控变异 | 5/5：R3、R6、R10；R18、R19 也变化 | 无 | 规则敏感性通过，不是实测工具攻击率 |
| Week6 SwiftShader WebGL 受控变异 | 5/5：R7 | 无 | 规则敏感性通过，不是实测工具攻击率 |
| Week6 wrong Android model 受控变异 | 5/5：R3、R4 | 无 | 规则敏感性通过，不是实测工具攻击率 |
| Week6 headless automation UA 受控变异 | 5/5：R3、R6、R10、R20；R18、R19 也变化 | 无 | 规则敏感性通过，不是实测工具攻击率 |

因此，正确的总判断是：

1. 顶层规则已经覆盖了多种“破坏 Native—Web 或 WebView—Web 对齐关系”的变异，而不只是某一个类别。
2. 现有规则的明显盲区是 Stealth 所使用的 WebGL 伪装、hardwareConcurrency、languages、plugins 等浏览器表面：其中只有 WebGL 与 R7 有部分关系，但当前实现和自然语言阈值都不足以把该 AVD 场景稳定判为冲突。
3. 以上都是受控、同源、重复 AVD 条件下的案例结论。不能把 29 个有直接规则差分的 active/controlled 行与 6 个未检出的 Stealth 行合并成“检测率”，更不能外推为欺诈识别或未知攻击泛化能力。

## 二、这次到底评估了什么

### 2.1 被测规则库

本报告的唯一规则来源是顶层文件 HYBRID_APP三端跨端一致性测试规则.md：

| 规则组 | 自然语言规则编号 | 当前实现中的对应 consistency 特征 |
|---|---|---|
| 准入与缺失语义 | R1–R2 | 不单独形成特征；作为会话原始性、字段状态和“不评估”前置条件 |
| Native—Web | R3–R10 | model/UA、Android 版本、屏幕/DPR、CPU/platform、GPU/WebGL、触点、内存、桌面或脚本 UA |
| Native—WebView | R11–R16 | system HTTP agent、JSBridge、包名、安装来源、debug/cleartext |
| WebView—Web | R17–R20 | Chrome 主版本、WebView token、bridge/mobile/runtime 三联、python-requests |
| 三端组合 | R21–R27 | 核心完整性、manual/ADB 上下文、低风险组合、均分、失败计数 |

数值实现直接调用顶层 ablation/run_consistency_ablation.py 的 build_consistency_features。该函数在 383–445 行构造 38 个 consistency 特征；本次没有调用子项目的 Week 7 evaluator，也没有训练或调用随机森林。

### 2.2 “可判别”的严格含义

一个规则在本报告中被称为“可直接区分”，必须同时满足：

1. 同一个 pair 的 attack 行相对 clean_pre 从一致/无风险信号转为该规则定义的明确不一致或强信号；
2. formal 数据的 clean_post 恢复为 clean_pre 对应状态；
3. 这种变化在该攻击条件的所有可用 pair 中复现；
4. 该变化符合自然语言规则的适用前提，而不只是实现中把“不适用”机械编码成 0。

下列情况不算“直接区分”：

- R9 内存、R18 WebView token、R26 平均分等仅为软证据或没有固定判定阈值；
- R23/R24 的 manual、ADB、满电等测试环境线索在 clean 与 attack 中同时出现；
- UA 已不声明 Android Mobile 时，R8 不适用，不能把特征值 0 误报为“移动 UA + 零触点”；
- UA 中无法解析 Android/Chrome 版本时，R4/R17 应是未评估，而不是版本冲突。

## 三、数据准入与证据边界

### 3.1 纳入计算的两条数据轨

| 数据轨 | 内容与规模 | 用途 | 是否可与其他轨合并成指标 |
|---|---:|---|---|
| 20260812 formal v2.2 | 5 个 bundle、45 条 raw payload：15 clean_pre、15 attack、15 clean_post；CDP 9 个 active，Stealth 6 个 active | 主案例：同源三态规则差分 | 否；仅 15 个 pair、3 个稳定设备组 |
| Week6 controlled pairs | 5 个 measured clean seed + 20 个 deliberate mutation；4 种变异各 5 个 | 第二轨：规则对已知字段变异的敏感性 | 否；没有 clean_post，且不是实测攻击工具结果 |

formal 五个 bundle 的组成可在子项目的 execution_log/evidence/20260812_local_collection_increment_summary.md 第 23–35 行核对。全部 45 条 raw 行都带有 177 个 observed 字段状态，满足当前 27 条规则所需的三端原始字段；formal 每个 pair 的 clean_pre 与 clean_post 在本次重算的 38 个 consistency 特征上完全恢复。

Week6 轨的组成是 5 个 clean seed 和四类各 5 个 deliberate mutation，来源说明见 execution_log/evidence/week6_data_portfolio_20260711.md 第 20–27 行。它只能回答“如果这些字段这样被改写，规则是否会变化”，不能回答“真实工具攻击的检出率”。

### 3.2 明确不纳入的攻击/数据目录

| 数据 | 不纳入当前判别结论的原因 | 正确状态 |
|---|---|---|
| 历史 Week7 CDP v2.1 | 旧 schema 与 v2.2 formal 不同 | 仅可做隔离的历史敏感性补充 |
| 历史 Stealth | 完整三态失败，只有有限 clean/partial evidence | 证据不足 |
| mitmproxy | 是 transport intervention；协议本身不要求指纹字段变化 | 不适用，不是 false negative |
| Week6 209 complete 元数据 | raw payload 在外部路径，且工具在场不等于字段攻击效果 | 不适用 |
| Week5 113 行 CSV | 当前 checkout 缺失对应 raw JSONL，无法运行顶层规则 | 证据不足 |
| VirtualXposed/E4 | 只有脱敏字段/哈希或 WebView crash，缺 matched baseline 与完整三端 raw | 不适用 |
| 21 条 compatibility baselines | 没有攻击标签、raw payload 或成对对照 | 不能估计 FPR 或判别能力 |
| 工具能力目录（82/24 等） | 不是字段效果样本 | 不适用 |

这一区分很重要：攻击工具目录、环境标签、历史旧规则结果，均不能自动变成“顶层 27 条规则已经识别的攻击正例”。

### 3.3 formal 轨的当前严格验证限制

当前 checkout 中，五个 formal bundle 的原始行、manifest、三态 sidecar 能支持结构性重放；但原 verifier 仍然 0/5 通过。原因是每个 bundle 缺少 3 个 attack active_runner_evidence 指向的 automation_logs JSON，合计 15 个。

原校验器在 execution_log/tools/verify_attack_run_bundle.mjs 第 238–246 行强制要求 active runner log 存在且被 success_evidence 引用；子项目 .gitignore 第 67–73 行又排除了这些 logs。因此本报告只可表述为：

> 基于已提交 raw payload、manifest、sidecar 与 clean/attack/post 结构的条件性规则判别审计。

不得表述为“目前 checkout 中所有 attack active 均已完成独立严格执行归因验证”。补齐原始 15 个 automation_logs 后，应重新运行五个 verifier，再升级 formal 轨的证据等级。

## 四、formal v2.2：顶层规则对两种实测浏览器攻击的结果

### 4.1 CDP browser API spoof：多条规则稳定区分，9/9

CDP 三个 API bundle 的 attack 行均将 Android WebView 表面改为 Windows Chrome，并改写 webdriver、platform、hardwareConcurrency、deviceMemory、UA。顶层规则直接观察到的差分如下：

| 规则 | clean_pre → attack 的现象 | 覆盖 | 性质 |
|---|---|---:|---|
| R3 Native 身份—UA | model/UA strength 1 → 0，match 1 → 0 | 9/9 | 直接冲突 |
| R9 内存软比较 | memory delta 约 0.066–0.415 GB → 13.585–14.066 GB；score → 0 | 9/9 | 强辅助，不能单独定性 |
| R10 桌面/脚本 UA | desktop_or_bot_ua 0 → 1 | 9/9 | 直接冲突 |
| R17 provider—Chrome major | match 1 → 0；主版本差 0 → 2、11 或 39 | 9/9 | 直接冲突 |
| R18 WebView token | token 1 → 0 | 9/9 | 辅助异常 |
| R19 bridge + mobile + WV | runtime match 1 → 0 | 9/9 | 直接冲突 |
| R26 全局均分 | 0.774108 或 0.932176 → 分别减 0.5 | 9/9 | 汇总支持，无独立阈值 |
| R27 失败计数实现 | 2 → 6 | 9/9 | 汇总支持，见第六节口径问题 |

因此，CDP 的条件性结论并不依赖 webdriver 这个子项目变异字段；即便 webdriver 不在顶层 27 条规则中，R3、R10、R17、R19 已足以在全部 9 个同源 pair 中给出明确跨层冲突。

以下字段变化不能误计为额外规则命中：

- R4 的 Android version feature 从 1 变为 -1、delta 变为 99，是 Windows UA 不再可解析 Android 版本；按自然语言 R4 应记“未评估”，不是版本冲突。
- R8 的 touch feature 从 1 变为 0，是 UA 已经不是 Android Mobile；按自然语言 R8 也不适用。
- R6 仍为一致：native x86 与 Win32 都被当前映射为 x86 家族。这是 CPU 家族规则的设计结果，不应把它写成检测命中。

### 4.2 Stealth fingerprint evasion：当前没有可靠直接判别，6/6

Stealth 两个 API bundle 的 active 行改写 hardwareConcurrency、WebGL vendor/renderer、languages、plugins，但保留 Android UA、platform、WebView token 与 JSBridge。重算后的唯一变化是：

| 特征/规则关联 | clean_pre → attack | 覆盖 | 能否作为直接检测 |
|---|---|---:|---|
| R7 GPU score | 0.6 → -1 | 6/6 | 否 |
| R7 software/desktop marker | 1 → 0 | 6/6 | 否，方向甚至不符合“风险增加”的语义 |
| R26 平均分 | 0.932176 → 0.832176 | 6/6 | 否；只有同 pair 基线下可见的 0.1 降幅 |
| R27 failure count | 2 → 2 | 6/6 | 否 |

根因有两个：

1. clean AVD 的 emulator + SwiftShader 在当前实现中得到 GPU score 0.6，已经不是 R7 的强匹配；attack 的 ANGLE (NVIDIA ... Direct3D11) 又被 parser 落入 unknown，无法形成明确的“真实硬件—桌面软件渲染”强冲突。
2. Stealth 的另外四个改写字段（hardwareConcurrency、languages、plugins，以及 webdriver 未变）没有对应的顶层 27 条规则或 38 个 consistency 特征。

所以，不能因为 R26 在 6/6 pair 中下降 0.1，就声称 Stealth 已被当前规则“检出”。正确结论是：当前规则对这一 Stealth 条件仍没有可独立二值化、可解释的直接判别规则。

## 五、Week6 controlled：四类受控变异均有顶层规则覆盖

Week6 不与 formal 合并统计，但它能验证规则库的实际覆盖范围。

| 变异 | 直接规则差分 | 覆盖 | 辅助或汇总变化 |
|---|---|---:|---|
| desktop UA | R3 model/UA 1 → 0；R6 CPU/platform 1 → 0；R10 0 → 1 | 5/5 | R17 3/5；R18、R19 5/5；R26、R27 均变化 |
| WebGL SwiftShader | R7 gpu score 0.85/1 → 0，gpu match 1 → 0，software marker 0 → 1 | 5/5 | R26、R27 均变化 |
| wrong Android model | R3 strength 1 → 0.35、match 1 → 0；R4 version 1 → 0、delta 0 → 20 | 5/5 | R17 3/5；R26、R27 均变化 |
| headless automation UA | R3 1 → 0；R6 1 → 0；R10 0 → 1；R20 0 → 1 | 5/5 | R18、R19 5/5；R9 仅部分；R26、R27 均变化 |

这里最重要的解释是：

- desktop/headless 的 R4、R8、部分 R17 不是负例，而是因为 UA 已无 Android/Chrome 可供规则解析，按 R2 应记为未评估；
- SwiftShader 之所以能被 R7 直接识别，是 Week6 clean 样本是可映射的真机硬件族，攻击结果是明确的软件桌面渲染标识；这和 formal Stealth 的 emulator + ANGLE/NVIDIA 场景不同；
- 因而“四类 5/5”说明规则对四种明确构造的跨层矛盾敏感，不说明四类实测攻击工具均以同样方式被识别。

## 六、27 条规则的覆盖矩阵与实现差距

| 规则 | formal CDP | formal Stealth | Week6 覆盖 | 本批判定 |
|---|---|---|---|---|
| R1 会话原始性 | 15 个三态 pair 可作前置验证 | 同左 | 只有 clean/mutation 对 | 准入条件，不做攻击分类 |
| R2 未评估语义 | 177 字段状态齐全 | 同左 | 无 field-status | 准入/解释条件 |
| R3 身份—UA | 9/9 | 不变 | desktop、wrong model、headless 各 5/5 | 强覆盖 |
| R4 Android 版本 | 未评估 | 不变 | wrong model 5/5 | 只对可解析 Android UA 有效 |
| R5 屏幕—DPR | 不变 | 不变 | 本批均不改屏幕 | 尚无攻击覆盖 |
| R6 ABI—platform | 不命中，x86/Win32 同族 | 不变 | desktop、headless 各 5/5 | 取决于 Native CPU 家族 |
| R7 硬件—WebGL | 不变 | 解析盲区 | SwiftShader 5/5 | 真机软件渲染强，Stealth AVD 未覆盖 |
| R8 Mobile—touch | 不适用 | 不变 | 无合适样本 | 当前没有直接案例 |
| R9 内存 | CDP 9/9 软差分 | 不变 | headless 部分变化 | 辅助，不单独定性 |
| R10 桌面/脚本 UA | CDP 9/9 | 不变 | desktop、headless 各 5/5 | 强覆盖 |
| R11–R16 Native—WebView | 三端宿主字段不随攻击变化 | 同左 | 不随四变体变化 | 本批不区分；manual/debug 等仅上下文 |
| R17 provider—UA | CDP 9/9 | 不变 | desktop、wrong model 各 3/5 | 强辅助，解析失败时未评估 |
| R18 WebView token | CDP 9/9 | 不变 | desktop、headless 各 5/5 | 辅助异常 |
| R19 bridge/mobile/WV | CDP 9/9 | 不变 | desktop、headless 各 5/5 | 强覆盖 |
| R20 python-requests | 不命中 | 不命中 | headless 5/5 | 窄但强的脚本规则 |
| R21–R22 核心完整性 | clean/attack 都通过 | clean/attack 都通过 | 不变 | 不能识别 Web-only 注入 |
| R23–R24 manual/ADB | clean/attack 都是测试环境线索 | 同左 | 不构成攻击差分 | 仅上下文 |
| R25 低风险组合 | manual 环境下不通过，且无差分 | 同左 | 无差分 | 不是攻击判据 |
| R26 均分 | 9/9 下降 0.5 | 6/6 下降 0.1 | 四类均下降 | 只作排序/汇总 |
| R27 失败计数 | 9/9 增加 | 不变 | 四类均增加 | 需先修正计数语义 |

当前实现至少有三处必须显式说明的差距：

1. **R7 的 ANGLE/NVIDIA 解析空白。** run_consistency_ablation.py 第 251–265 行只把 SwiftShader、ANGLE (Apple...)、Headless 归为 software_desktop。generic ANGLE (NVIDIA ... Direct3D11) 被归为 unknown。它既没转成可解释的 desktop GPU，也使 software marker 从 1 变为 0。
2. **R27 的机械计数不完全等价于自然语言规则。** 第 435–445 行按特征名后缀计所有 0。它会把非 Android Mobile UA 的 touch_mobile_match=0 计为失败，也会把“非官方安装器但核心完整”之类低风险条件未满足计入失败；这与 R2、R8、R25、R27 的自然语言语义不完全一致。R27 在本报告中只能作为实现层汇总，不应取代逐条规则解释。
3. **浏览器表面覆盖不足。** formal CDP 的 webdriver 与 Stealth 的 hardwareConcurrency、languages、plugins 均是 sidecar 明确变化字段，但当前 27 条/38 特征没有直接规则。字段变化不等于现有规则已识别，二者必须分开报告。

## 七、让规则能覆盖更多攻击数据的下一步

### 7.1 先修复正式证据，而不是先报更高指标

1. 补回五个 formal bundle 的 15 个 automation_logs JSON，保留路径、内容哈希和 manifest 引用。
2. 在子项目根目录逐个执行 node execution_log/tools/verify_attack_run_bundle.mjs execution_log/evidence/<bundle>。
3. 只有五个 bundle 都通过后，才把 formal 轨从“sidecar 支持的条件性审计”升级为“当前 checkout 可严格复核的受控攻击案例”。

### 7.2 补足 Stealth 的规则覆盖，但避免把 AVD 特征硬编码成攻击

建议将新增规则分成“单行跨层语义”和“有可信基线时的变化检测”两层：

| 建议 | 目的 | 需要的约束 |
|---|---|---|
| 扩展 R7 GPU parser | 识别 generic ANGLE (NVIDIA/AMD/Intel) 与 Direct3D/OpenGL 桌面 renderer | 先在物理机、合法 emulator、多个 WebView 版本收集负例；不要把所有 ANGLE 一律判攻击 |
| 新增 emulator renderer 关系 | 对同一 Native emulator 身份下的 SwiftShader ↔ desktop discrete GPU 转换形成显式状态 | 单行只能记环境异常；只有同 stable-device + 同 app/WebView version 基线的突变才可记“表面变化” |
| 新增 webdriver 规则 | WebView 场景的 navigator.webdriver=true 作为浏览器自动化强信号 | 明确它是自动化/环境信号，不单独推出欺诈或真实攻击 |
| 新增 Native CPU 核数—hardwareConcurrency 宽松比较 | 覆盖 Stealth 的 HC 改写 | 先采集可信 native core count，允许 Web API 的粗粒度和版本差异 |
| 新增 Native locale—Web languages 对齐 | 覆盖 Stealth 的 languages 改写 | 处理语言列表顺序、主语言/地区退化和用户多语言配置 |
| 新增 Android WebView plugins 约束 | 覆盖 plugins 0 → 3 | 需先确定不同 WebView/ROM 的正常取值范围，避免零样本硬阈值 |

最关键的是最后一层：Stealth 这类攻击能够保持单行 UA、平台、桥接字段“看上去合理”。若要可靠发现它，应把同一稳定设备、同一 App 与 WebView 版本下的 clean baseline 作为单独的 provenance-aware delta 规则。它不能被伪装成当前 27 条单行一致性规则的自然结果。

### 7.3 扩展验证设计

1. 使用多个物理设备、不同 SoC、不同 Android/WebView 主版本和多个独立 stable-device group；不要把重复 AVD session 当成新设备。
2. 每个新增攻击工具都采集 clean_pre → attack → clean_post，记录原始 runner log、固定配置、实际 field effect 和恢复证据。
3. 增加“合法自动化/合法 emulator/调试开发”负例，以衡量新增 R7、webdriver、plugins 等规则的环境误报，而不是只用攻击样本设计规则。
4. 固定规则版本与判定阈值后，按 stable-device/scenario 整组切分，才考虑正式统计评估；在此之前保留为受控案例验证。

## 八、可复核操作记录

本次执行的是顶层实现的 feature builder，输入来自子项目 raw payload；没有修改原始数据，也没有使用 nested Week 7 规则。

1. 子项目已执行 fast-forward 拉取：f3fbfae → 025690a；当前为 main...origin/main。
2. formal 输入：五个 20260812 CDP/Stealth bundle 的 raw_payloads.jsonl 与 attack_sample_manifest_v1.jsonl。
3. Week6 输入：execution_log/evidence/week6_controlled_pair_dataset_20260711.jsonl。
4. 重算入口：ablation/run_consistency_ablation.py 的 build_consistency_features。
5. formal 比较单位：同一 pair 的 clean_pre、attack、clean_post；Week6 比较单位：同一 pair_id 的 clean 与 deliberate mutation。
6. 当前 strict verifier 复跑结果：五个 formal bundle 都因缺少相应 active runner automation log 失败；该失败已按第三节边界纳入结论。

## 九、最终结论

顶层 HybridGuard 三端一致性规则确实能对多种浏览器指纹改写形成可解释的跨层差分：formal CDP 9/9，以及 Week6 的四种受控变异各 5/5 都至少有一条明确规则命中。它们不是只覆盖“第一类”。

但这不意味着规则库已经覆盖所有子项目攻击数据。formal Stealth 的 6/6 active 正好证明了当前规则的盲区：GPU 解析、emulator 语义、hardwareConcurrency、languages 与 plugins 尚未形成稳健的顶层判定规则。下一步应补齐严格日志证据，并用受控负例和可信同设备基线扩展这些关系；在此之前，最严谨的结论仍是“受控案例级可判别性”，而不是通用攻击检测能力。
