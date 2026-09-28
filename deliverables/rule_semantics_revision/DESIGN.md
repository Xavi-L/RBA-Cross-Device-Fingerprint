# 候选规则语义与适用条件修订设计

状态：DESIGN_ONLY。记录日期：2026-09-28。实际 HEAD 为 `c7e43762b429c0d3f7a0ee0e77101691b10b6be4`，包含第一轮调查提交。主要证据来自 [第一轮报告](../normal_app_behavior_review/REPORT.md) 及其 190 条来源登记；本目录只补充会改变候选前提的少量源码依据。

本轮没有实施候选、运行 App、采集、训练、选择规则、生成预测或打开独立确认材料。V1、V2-A/B/C、第一轮调查和旧模型均保留原样；V2-C 仍已关闭，独立确认仍待定。本设计不继承上一轮提交推送授权。

## 结论与下一步

先做两个方向：**语言首项关系的有限解析**和 **webdriver 历史投影的状态表达修正**。前者在来源已绑定的范围内有现成输入；后者能立即实现旧 `true`、旧 `false` 和来源失败的区别，但无法恢复历史原始 false/API 缺失。两者都是同层设计，不能包装成新的跨层检测能力。

没有一个新的跨层候选已同时具备完整语义和全部历史输入前提。UA 缺实例、配置阶段和独立 Host 配对；内存已有条件性源码对应，但缺运行构建、低内存分支和缓存时期证据；MIME 缺可信实现绑定；固定时区只是已有 B 关系。不能为凑两个跨层候选而假定这些条件天然满足。

立即停止把以下说法当成通用攻击解释：桌面 UA 即伪装；与平台默认 UA 不同即被改写；`timezone_offset > 0`、`deviceMemory > 2`、语言列表多于一项或历史核数大于 4 即异常硬件；MIME 数量是全部格式支持能力；`webdriver=false` 已证明没有自动化。这里停止的是过度归因，**不删除字段、不设人工报警白名单，也不重算历史成绩**。指定版本 MIME 非零及 webdriver true 仍可作为有清楚目标的候选信息，不能仅凭静态调查决定最终报警资格。

## 四层判断与两种部署

| 层次 | 本轮能够回答什么 | 本轮不能替代什么 |
|---|---|---|
| A 语义/可计算性 | 字段是什么、能否配对、如何归一化、何时 U | 实际覆盖率和源码对应历史 APK 的运行证明 |
| B 关系偏差 | T 是否偏离明确声明的关系/实现预期 | 攻击真值、动机、独立硬件身份 |
| C 判别价值 | 静态正常反例和待检验边界假设 | 正常发生率、真实 FPR、泛化成绩 |
| D 模型选择/报警 | 给出未来固定策略的对照设计 | 静态批准/永久禁用某字段或强制跨层入选 |

`CONTROLLED_HOST` 指自有或明确集成的 App，可登记配置来源、采集构建和生命周期。它允许设计可靠配对协议，不代表本仓库旧数据已经有该协议。`GENERAL_APP_WEBVIEW` 指第三方业务容器；除非有同等集成证据，否则不能假设可知其所有设置、实例或导航。

第三方正常业务 setter 的证据说明普适相等前提不成立，不能据此宣称自有采集 App 的历史记录已经误报。反过来，自有 App 固定设置也不能代表全部正常 App。历史评价的范围保持原样，新有效域和覆盖损失另列。App 名称、特定业务 UA、所谓兼容模式均不进入运行时豁免。

## 六个有限模板

具体字段、伪代码、状态和人工示例见 [CANDIDATE_SPEC.json](CANDIDATE_SPEC.json)。T 均只表示该候选定义成立。

| 模板 | 比较与实质变化 | 当前支持结论 | 优先级 |
|---|---|---|---|
| `RSR-UA-CONFIG-MISMATCH-v1` | 同实例、同文档、稳定配置阶段的当前 Host UA 与 JS UA 精确比较；公式源于 P3-UA-SETTINGS，新增配对/信任门控 | NEEDS_COLLECTION_METADATA | 暂缓 |
| `RSR-LANG-FIRST-v1` | 完整窄域标签的 language 与 languages[0] 比较；不是长度或全列表 primary 成员检测 | EXISTING_INPUTS_SUFFICIENT_FOR_PROPOSED_SCOPE | 第一 |
| `RSR-TZ-FIXED-v1` | 固定时区 ID、Native raw offset、Web 当前 offset 的窄域符号关系 | DUPLICATES_EXISTING_SEMANTICS | 复用 B，非新家族 |
| `RSR-MEM-QUANTIZED-v1` | 满足源码/运行条件后，页与 MiB 截断、低内存分支、最近二次幂量化的对应 | NEEDS_COLLECTION_METADATA | 暂缓 |
| `RSR-MIME-EXPECTED-v1` | 受信的精确 133.0.6943.137 Android WebView 实现域中计数是否非零；数值谓词仍是旧 W02 | NEEDS_COLLECTION_METADATA | 暂缓 |
| `RSR-WEBDRIVER-STATE-v1` | 区分报告 true、已证原始 false、API 缺失/非布尔、读取失败及历史投影不明 | NEEDS_COLLECTION_METADATA（legacy 解释器可先实现） | 第二，仅状态修正 |

### UA：配置传播关系，不是独立硬件参照

平台默认值、实例设置、JS 暴露、HTTP 请求 UA、Java `http.agent` 是五个对象。仓库 Host 设置读数在 `configureWebView` 初始化时取得，随后经 bridge 返回；JS 适配器稍后采集。相同 session 并不证明同实例、同文档、同一稳定配置阶段。[LOC-007/008/011/012/027/029]

新候选要求 Host 协调的实例/文档 ID、配置 epoch、probe 前后当前设置读数，以及配置已传播的来源绑定。比较有效非空字符串，不 trim、不删业务后缀、不补 Android/型号 token。正式 setter 后两端一致为 F，一致改写也可 F；有效配对内失配为 T，可能来自 Web 单侧改写、回传差异或未建模机制，不能据 T 判断原因。UA setter 与 platform 不同步存在正常机制，不能由桌面 UA 加 ARM platform 直接归因攻击。[OFF-001/014–018，APPB-001/012/013，APPA-031]

现有 `webview_data` 经页面回传，由 MainActivity 重新组包；Native 数据则来自 Host 已采结果。Host 字段名称本身并不使其成为抗页面伪造的独立参照。版本、实例和配置不能由被检页面自行声称后即放行；后续需独立 Host 保留/附加这些信息。[RSR-LOC-003]

### 语言：保留首项、地区和脚本，承认同层

Native locale 是 Java 进程默认值，不是系统不可变真值；Resources、系统语言、JS 偏好与 HTTP 加权头也不等同。第一轮的 App locale/HTTP 路径不能直接证明 JS 同步。[LOC-006，OFF-003/004/005/019–024]

新关系沿用 B 的有限标签语法，但保留支持域中的脚本和地区，只做 ASCII 大小写归一。扩展/私用/历史别名不猜测。正常 fallback 和缩减列表只要首项与 language 一致就 F；不是按列表长度报警。仅 language 和首项必须通过窄域解析；尾项原样保留诊断，不参与门控，尾项扩展或异常不遮蔽已可计算的首项关系。新模板与 B 的 `V2SINGLE:WEB_PRIMARY_ABSENT_WEB_LIST` 不同：language 在第二项时，旧成员关系可 F，新首项关系 T。两端都来自同一 Navigator，合并改写无法识别。[LOC-008/022，OFF-002/023]

来源已绑定时，未知内核版本不妨碍描述字面自洽，但不能据此指认该内核违反实现或发生攻击。若来源配对、API 或必要标签证据不足，保持 U；不按页面自报版本豁免。

### 时区：固定域复用，动态域缺少同刻读数

Native 是 `TimeZone.getDefault().rawOffset / 60000`（本地减 UTC，分钟，不含 DST）；Web 是 `new Date().getTimezoneOffset()`（UTC 减本地，当前时刻）。上传 timestamp 和采集结束时间都不是两端共用的参考瞬间。IANA 区域名/别名不能靠当前 raw offset 或攻击配置恢复 DST 规则。[LOC-006/009，OFF-006/007/025–029/051/052]

固定时区窄域沿用 B：解析已有 UTC/GMT/Etc 固定格式，Native raw 必须与解析值一致，再比较其与 Web 值反号。复用 `V2REL:FIXED_NATIVE_VS_WEB_OFFSET_DIFFERS`，不新增同义原子、不改原域。动态扩展只列收集需求：同一参考 epoch 毫秒、Java `getOffset(epoch)`、JS `new Date(epoch)` 偏移、各自来源与规则版本；本轮不建立第七个模板。相同偏移不能证明同地区或无操纵。[LOC-022]

### 内存：现在能给条件公式，仍不能无条件 Q(Native)

定向补查纠正了“只能说两端不同口径”的笼统结论：已核 AOSP 路径中 ActivityManager 的 totalMem 经 Process/JNI 取 `sysinfo.totalram * mem_unit`；bionic 的物理页数也来自同一总量，并按页截断。Chromium 默认物理内存再按 MiB 整数截断。因此在指定实现、相同稳定内核总量且已排除覆盖分支时，来源对应可以推导。新增来源登记保存固定版本与定位，未复制第三方源码。

但 Chromium 83 的强制低内存分支可取 512 MiB；124/133 则取 min(512 MiB, 实际输入)，另有测试覆盖路径。Native `is_low_memory` 不能证明该开关。最近二次幂的中点向下、除 1024、上限 8 均有源码依据；已读量化函数没有显式 0.25 下限，不能把规范一般描述硬加到具体实现。Native `_gb` 实为 GiB，不能用动态 availMem 替代 totalMem。精确公式、整数转换边界和门控见规格。

历史构建映射、运行分支、缓存时期及必要数值精度前提没有由现存字段充分证明。门控未知即 U；无经验容差、无全样本比例界限。B 的 Web/Native 比例产生正常代价的负结果原样保留，不包装成新量化成功证据。[LOC-021/022，OFF-030/031/032，新增 SMT-CHR*/SMT-AOSP* 来源，见 ADDITIONAL_SOURCES.json]

### MIME 与 webdriver：投影信息有边界

MIME 只把完整核到的 133.0.6943.137 链纳入源码预期 0。83/124 只有部分链，其他版本/厂商未知为 U。Host provider package/version 本身不是构建实现证明，也不允许页面自报代替独立部署绑定。计数/hash 不能恢复成员；没有 `pdfViewerEnabled`，不能计算 PDF 能力与枚举成员关系。插件和 MIME 也不是两个独立采集层。[OFF-015/037–044/048/049，LOC-010]

webdriver 的当前表达式是 `navigator.webdriver === true`。API 不存在、返回 false、其他 non-true 类型都会变成 observed false；但 getter 或外层计数读取抛错会使整个 automation probe 回退，status 为 runtime_error，适配器保留为来源不可用。这些错误并非全部和 observed false 合并。内部 hash 枚举 catch 又只记 `plugin_probe_error`，须与外层错误区分。[RSR-LOC-MW 来源]

新 legacy 解释：有效 observed true 为 T；observed false 为 U（不可逆 non-true 投影）；来源错误仍 U，并保留原原因。未来原始观察 schema 才能使“API 存在、成功读取、类型 boolean、值 false”得到 F。改变后模型可能增加弃判，不能宣称改善了准确率。true 是报告状态，不改旧攻击标签；本轮不将测试/外部自动化重新引入为普通 App 默认反例。

## 共同执行与信任契约

T/F/U 进入三值逻辑：NOT(U)=U；AND 有 F 则 F、全 T 才 T，否则 U；OR 有 T 则 T、全 F 才 F，否则 U。`FAILED` 是执行/结构验证失败，不是第四个普通逻辑值。当前模型选中原子的失败不会因另一原子 T 而静默忽略。源采集 runtime_error、API 不支持、字段缺失、合法但超出解析域通常是 U。[RSR-LOC-001，LOC-018]

新字段元数据全部标 `PROPOSED_NOT_COLLECTED`。依赖已知实现域的 MIME/内存及相应 UA 门控中，未知容器/构建是 U；语言与 webdriver 仍可在来源清楚时描述字面自洽/报告值，不由未知内核强制弃判。非法声明 schema、矛盾结构或执行器异常是 FAILED。两者都保留记录。阶段、标签、攻击配置、App 名和业务 UA 常量不得进入门控；配对 ID 仅用于质量验证，不能作为模型字符串特征。现有 study_protocol 不接受这些新增元数据，未来必须单独版本化适配契约，不能偷偷加入旧 V2 输入。[RSR-LOC-006]

门控通过不证明安全。页面删除值、制造解析域外值或篡改配置可强制 U；Host/Native 若可被 Hook，也可能失去参照价值。报告需保留全部预期样本，按候选展示 T/F/U/FAILED、原因和门控前后覆盖；同时给全分母与条件分母。有效域收窄引起的少报警不等于更好检测。

## 迁移与设计校验边界

[RULE_MIGRATION.csv](RULE_MIGRATION.csv) 对齐第一轮全部 17 条：六个最终 Web 条件、十个规范 C0 候选（只选中了 OFFDER-UA-001）、一个历史核数条件。OS 关系别名按原 ledger 归并；OFFDER-UA-002 与 P3-UA-DEFAULT 的 trim/typed 差异不合并；NW-006 与 OFFDER-UA-001 虽在已保存开发材料上同值，适用域不同，不全局合并。[LOC-004/005/026/028]

屏幕只保留 display/window/viewport/时序和 CSS/Native 单位的缺口；GPU 保留软件/未知族 U 和后端映射限制；核数没有 Native/Host 同义参照，ABI 不能补造。三个方向均不新增模板。

[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 给出下轮独立模块、接口、重点验收和固定选择策略对照。`VALIDATION.json` 只检查引用、字段、旧身份、规格完整性和设计边界，绝不是 App 行为、候选执行、模型或方法有效性验证。所有例子均为 `SPECIFICATION_EXAMPLES`，不是新增 clean/attack，不进入真实分母。

建议提交信息（仅建议，不执行）：`docs(research): specify bounded fingerprint rule semantics and applicability`。

可从仓库根目录重跑设计校验：`python3 deliverables/rule_semantics_revision/validate_design.py`。它只读取设计、字段目录、原候选登记和保存模型结构，不导入或执行候选/模型。可选 `--initial-status <本轮开始时的git-status文件>` 仅检查原 Git 状态条目是否保留；没有该文件则如实标为未检查。
