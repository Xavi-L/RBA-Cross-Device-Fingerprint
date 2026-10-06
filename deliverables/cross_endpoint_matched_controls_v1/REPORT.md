# B2-B：正常设置与双向运行时干预对照

**结论：C1 可以补充 Browser-only 时区偏离；C2 提供双向语言差异信息，但真实浏览器首选语言已复现正常反例，不能单独视为攻击证据。** 本轮没有训练联合模型，也没有最终消融。

基于 `ad121b53015f34ce22644f27bceec5d9d24bcf4e`，复用原 B1 后端、v16 APK、原探针以及 B2-A 五个条件和三个 B_REL_TZ RETENTION 模型。唯一环境为 Android16/API36.1、arm64、Chrome/WebView **134.0.6998.135**，初始 en-US / Asia/Shanghai。与旧 x86_64 / Chrome133 先导独立登记；未为对齐旧环境下载或升级组件。完整环境和摘要在 [ENVIRONMENT.json](ENVIRONMENT.json)、[FROZEN.json](FROZEN.json)。

## 1. 数据流向、实际次数与有效性

| 数据批次 | 实际采集尝试 | App raw / Browser raw / 完整配对 | 进入规范评价的位置 | 说明 |
|---|---:|---:|---:|---|
| 工程冒烟 | 12 | 12 / 12 / 12 | 0 | 四类运行时干预各一组三阶段 |
| 首轮正式矩阵 | 42 | 42 / 42 / 42 | 36 | 七场景、两轮、三阶段；原始 42 条完整保留 |
| 限定工程补跑 | 6 | 6 / 6 / 6 | 6 | 仅两组 L_BROWSER_LANG，事前固定替换全部六位置 |
| 合计 | **60** | **60 / 60 / 60** | **42** | 不把额外采集加进评价分母 |

首轮正常 Browser 偏好在 UI 中已置顶法语，但脚本随即 force-stop，冷启动时法语项丢失；两条 change 的 navigator 因而未变。一次固定 **15 秒**等待后的冷启动 UI 核验确认该设置可持久化。最小修复只增加等待及冷启动后的偏好列表核对，然后补跑两个完整 triplet。没有调整目标值，也没有读取检测分数后挑样本。初次记录、旧脚本、问题、修复和事前来源选择分别见 [ENGINEERING_NOTES.md](ENGINEERING_NOTES.md)、[ENGINEERING_ISSUE.json](ENGINEERING_ISSUE.json)、[ENGINEERING_REPAIR.json](ENGINEERING_REPAIR.json)、[ATTEMPT_SELECTION.json](ATTEMPT_SELECTION.json)。

规范的 42 位置中，**34 正常、8 有效受控干预**均有执行、实际操作数、作用域与恢复依据；身份不由检测输出或 phase 名称单独决定。App/Browser 各 42 个有效来源、42 个 exact-ticket 配对，缺端/绑定失败为 0。14 个 triplet 的语言/时区相关操作数均恢复到 pre；这不表示所有 244 个动态指纹字段逐值不变。

App 控制只连接当阶段 App PID 的 WebView；Browser 控制只连接独立 Chrome 的 exact-ticket 页面。目标修改在 App 探针导航或 Browser adapter gate 放行前安装，保持至双端记录完成，随后撤销。原始控制区间、同一主机的服务端接收时刻、设备时间域、target/channel、持有结束观察和恢复均留存。审计见 [ACQUISITION_AUDIT.json](ACQUISITION_AUDIT.json)；规范位置逐条依据见 [results/qualification.jsonl](results/qualification.jsonl)。

## 2. 冻结条件与完整 App 模型输出

表内数字为位置数；三个模型分别执行，结果相同，所以并列展示，未选择最好一折。所有条件 **210 个位置**、模型 **126 个位置**均保留；本批 U=0、FAILED=0。

| 场景 | 本行位置数 | C1 | C2 | C3 | D1 | D2 | App折01 | App折02 | App折03 |
|---|---:|---|---|---|---|---|---|---|---|
| 全部 pre/post | 28 | 28F | 28F | 28F | 28T | 28F | 28F | 28F | 28F |
| L_SYS_LANG change（正常） | 2 | 2F | 2F | 2F | 2T | 2F | 2F | 2F | 2F |
| L_SYS_TZ change（正常） | 2 | 2F | 2F | 2F | 2T | 2F | 2F | 2F | 2F |
| L_BROWSER_LANG change（正常） | 2 | 2F | **2T** | **2T** | 2T | 2F | 2F | 2F | 2F |
| A_APP_LANG change | 2 | 2F | 2T | 2T | 2T | 2F | 2F | 2F | 2F |
| A_APP_TZ change | 2 | 2T | 2F | 2F | 2T | 2F | **2T** | **2T** | **2T** |
| A_BROWSER_LANG change | 2 | 2F | 2T | 2T | 2T | 2F | 2F | 2F | 2F |
| A_BROWSER_TZ change | 2 | 2T | 2F | 2F | 2T | 2F | 2F | 2F | 2F |

三个模型 ID 依次为 `mtc-rel-tz-6e10284c39b1b601ab406240`、`mtc-rel-tz-9c5fa0e310ba10a00e520b1c`、`mtc-rel-tz-4ae67bb9da899cc419dd525f`。每折为 **2T/40F**；总计 **6T/120F**。每折在 34 正常位置为 34F，在 8 个干预位置为 2T/6F。App 模型只读取当前 App raw，不读取 Browser、pre/post 或操作标签。

C1 在 34 正常位置为 **0T/34F**，在 8 干预位置为 **4T/4F**。其中 App-only 时区已被原 App 模型触发；它新增的是两个 Browser-only 时区位置的信息。

C2/C3 各在正常位置为 **2T/32F**，干预位置为 **4T/4F**：四个语言干预位置中三个 App 模型均为 F，但同时有两个真实正常 Browser 偏好反例。正常报警与干预响应分别报告，不把二者合成“准确率”或一个已训练的联合分类器成绩。

D1 在 **42/42** 位置持续 T，不能算“因干预才检出”；D2 在 **42/42** 为 F，说明本轮语言修改保持了 language 与 languages[0] 自洽。C2/C3 本批同分不意味着普遍等价：固定语义测试中 `en-US/en-GB` 和 `zh-Hans/zh-Hant` 都是 C2=T、C3=F，没有新增这些实采场景。

完整分场景/阶段表和逐条结果见 [results/scenario_table.md](results/scenario_table.md)、[results/condition_states.csv](results/condition_states.csv)、[results/model_states.csv](results/model_states.csv)、[results/summary.json](results/summary.json)。

## 3. 正常设置与受控修改的实际操作数

以下各 change 行两轮一致。语言列表按原顺序保存；Web offset 使用两端原来的 UTC−local 分钟数，不反号。Native 记录的是原始时区 ID 与 raw offset，和 Web offset 的符号语义不同。

| 场景 | Native locale / zone（raw offset） | App language；languages；Web offset | Browser language；languages；Web offset |
|---|---|---|---|
| 基线与恢复 | en-US / Asia/Shanghai（+480） | en-US；[en-US]；−480 | en-US；[en-US,en]；−480 |
| L_SYS_LANG | fr-FR / Asia/Shanghai（+480） | fr-FR；[fr-FR,en-US]；−480 | fr-FR；[fr-FR,en-US,fr,en]；−480 |
| L_SYS_TZ | en-US / Asia/Tokyo（+540） | en-US；[en-US]；−540 | en-US；[en-US,en]；−540 |
| L_BROWSER_LANG | en-US / Asia/Shanghai（+480） | en-US；[en-US]；−480 | **fr-FR；[fr-FR,en-US,en]；−480** |
| A_APP_LANG | en-US / Asia/Shanghai（+480） | fr-FR；[fr-FR]；−480 | en-US；[en-US,en]；−480 |
| A_APP_TZ | en-US / Asia/Shanghai（+480） | en-US；[en-US]；−540 | en-US；[en-US,en]；−480 |
| A_BROWSER_LANG | en-US / Asia/Shanghai（+480） | en-US；[en-US]；−480 | **fr-FR；[fr-FR]；−480** |
| A_BROWSER_TZ | en-US / Asia/Shanghai（+480） | en-US；[en-US]；−480 | en-US；[en-US,en]；−540 |

−540 的 Web 时区 ID 为 Asia/Tokyo，其余为 Asia/Shanghai。系统法语设置同时把 Native language/country 改为 fr/FR，恢复为 en/US；其他场景 Native 保持 en/US。42 条完整相关操作数和两端 raw 物理行引用见 [results/operands.csv](results/operands.csv)。

Chrome 设置使用的是 **Preferred languages**，未用界面语言或翻译目标替代；官方说明与实际版本 UI 对照见 [PROTOCOL.md](PROTOCOL.md)。在正常独立偏好和 Browser 脚本语言干预中，C2/C3 的原始操作数都为 `(App=en-US, Browser=fr-FR)`，五个诊断输出也同为 `(F,T,T,T,F)`。仅依靠这些首选标签及当前五个条件的输出，再调差异阈值不能恢复操作意图。

但两者的 Browser 完整 languages 列表不同，**本轮并未证明所有原始字段或完整 paired244 输入不可区分**。把 `[fr-FR]` 的单一脚本配方记住，也不是一般性的“识别攻击意图”。保留这些正常反例用于后续正常约束，不能改标攻击、删除或制作永久语言白名单。

## 4. 时间异常、复核与交付边界

仅定向核对已知 MTC 配对 `mtc-pair-hgpair-v1-a01c05ee9faf637996ed1ddc`：payload 时间差仍为 2,833,629 秒，同一已正常关闭的 backend batch 中，服务端接收差为 **32.100967 秒**；receipt、ticket、pair 关联一致。客户端时钟校正或陈旧 payload 等具体原因仍不能唯一确定，既不能称实际等待 32.8 天，也不能把接收差当作精确采集间隔。详细时间域和引用见 [TIME_ANOMALY.md](TIME_ANOMALY.md)。原结果保留，没有事后时间过滤。

旧 18 条与本批独立。MTC891 仅引用 B2-A：C1 0T/866F/25U；C2/C3 各 1T/889F/1U；D1 194T/697F；D2 0T/885F/6U。原 zh-CN/en-US 正常偏离继续是正常反例。本轮没有重新评价全部 MTC，也没有更新旧 105/126 或宣称完整 paired244 模型成绩。

运行保护实际记录 **126 次原 App 模型调用、210 次固定条件调用、0 次训练**；禁止采集、子进程、网络及写历史目录。随后独立条件 oracle 检查 210 个结果，另用只有同阶段 App raw 的输入重放 126 次，完整预测对象逐条一致。仅重汇总还通过禁用预测/采集/进程/网络的检查，四份保存汇总文件字节一致。针对性测试为 4 个 Node、25 个新 Python、36 个原 B2-A 回归，共 **65 项通过**。证据索引见 [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)，命令见 [README.md](README.md)。

系统语言、时区、Chrome 偏好均恢复；本轮模拟器和三个本轮后端已退出，原 ADB server 保留。所有原有工作区状态保持不变，仅新增本交付目录。**没有提交或推送**；新完整指纹、票据和操作原始日志仍在忽略的本地 `private_runs/`，未扩大公开授权。

## 5. 下一步判断与唯一建议设计

1. **正常系统换语言/时区是否触发？** C1–C3 与三个 App 模型均不触发；D1 连同基线一直触发，属于持续列表差异。
2. **正常 Browser 偏好能否产生相同操作数？** 已复现与 Browser 脚本干预相同的 C2/C3 首选标签操作数；完整 lists 不同，不能声称全字段相同。
3. **同环境跨端条件有无双向补充信息？** 有。C1 补足 Browser-only 时区方向；C2 响应两个方向的语言偏离，但伴随正常报警。App-only 时区已由原模型响应，不计作新增覆盖。
4. **C1/C2 如何处置？** C1 有依据进入一次有限、研究范围内的联合选择；C2 可随正常约束进入候选审查，不能当独立高精度攻击证据。该结果仍是一个已暴露模拟器的局部对照，不是跨设备盲测或正式资格升级。
5. **哪些不能靠现有比较或阈值分开？** 正常独立 Browser 法语偏好与当前 Browser 脚本修改，在 C2/C3 标签输入及五个诊断输出上相同；D1/D2 也不能提供本批的意图区分。需承认这个语义边界，而不是删除正常点或放宽标注。

建议下一轮仅预登记**一个固定候选池的联合选择设计**：原候选池加本轮未改公式的 C1/C2，沿用原三折和阈值规则；将已有 development 正常语言反例及本轮正常偏好对照明确登记为开发约束，按完整 scenario_group 划分，禁止拆 pre/change/post 泄漏。一次性报告三个模型的收益、正常报警、U/FAILED 与不可行结果，不选最好折、不为 fr-FR 造白名单；若正常约束下 C2 不能被选入就保留未选中结论。pilot/run-scoped 材料须单独确认资格，不能自动加入正式训练或当成独立验证；这些已查看材料不能充当新的盲测。**本轮到此停止，不执行该设计、不训练、不开始最终消融。**
