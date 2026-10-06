# B2-A：Browser 语言／时区跨端先导诊断

**PILOT_DIAGNOSTIC_ONLY；已完成实际离线回放。** 基于 B1 提交 `2cc21e3e2ccbceb936e33624680f419bd21a3aa5` 的公开证据。每轮保存 54 条冻结 App 预测（3×18）及 4,545 条条件结果（5×(18+891)）。0 次训练、0 次新增采集，没有联合模型或最终消融。本轮未提交或推送。

主要发现：三个 App 模型在全部先导上明确不报警，所有已选子句均为 F；C1 在三条 Browser 时区干预上偏离，C2/C3 在三条 Browser 语言干预上偏离。MTC 完整语言列表比较出现 194/891 正常偏离，首选／主语言比较各只有 1 条偏离与 1 条 U。结果仅适用于这批先导及已经使用过的历史 MTC 诊断材料。

2026-10-06 复审已修复加载器端点耦合、坏引用中断和重汇总漏检等问题；全部 54/4,545 条推理内容复现一致。详见 [复审报告](review_20261006/REVIEW_REPORT.md)及独立核对记录。

## 范围、固定定义与评价身份

- 先导为同一个 API36 环境的 18 条配对、6 组三阶段。12 条正常前后阶段与各 3 条语言／时区干预来自 B1 `verification.json` 和 `stage_inventory.jsonl`，保存于独立评价侧表，预测不参与定性。源 `label_status`、candidate、run_profile 和身份范围不变。
- MTC 只读取 P2 已定的 891 个 primary_representative：630/144/117，不重新抽代表，不计 137 重复或 654 App-only。真实物理设备身份仍未知；891 条均满足已有 routine-collection 研究正常依据，这不是逐设备无攻击证明。各 split 已有使用历史，不称新盲测。
- `CANDIDATES_FROZEN.json` 在读取 MTC 144/117 字段值前保存。之后未按结果改公式、解析范围或 U 门槛。C1/C2/C3 是三个独立候选，D1/D2 仅作解释，没有择优、投票或 OR/AND 拼接。
- C1：有限数值偏移直接比较，两侧均为 Web 的 UTC−local 分钟，布尔／非有限数拒绝，0 和 −1 有效。C2：固定 `limited_full_tag` 子集、小写后的完整首选标签。C3：同一解析成功后的主语言。没有下划线、旧标签别名等自动猜测或转换；不声称完整 BCP47 注册表有效性验证。
- D1 原样调用 `P3-X-LANGUAGES@2.0.1` 完整有序列表相等，不归一化、不去重，保留旧适用语义（包括空列表）。D2 检查 Browser 自身首选标签和非空字符串列表首项，用同一标签解析；不称 Browser-only 分类器。
- P3 的 MATCH→F、COUNTEREXAMPLE→T、UNKNOWN/NOT_APPLICABLE→U。T 只表示关系偏离，不能据此把正常记录重新标攻击。[官方依据与探针核对](SOURCES.md)说明语言是偏好而非硬件不变量。

## 表1：完整冻结 App 模型实际输出

T=MANIPULATION_ALERT，F=NO_ALERT，U=INSUFFICIENT_EVIDENCE；FAILED 单列。

| 模型 | 阶段组 | n | 报警 T | 不报警 F | U | FAILED |
|---|---|---:|---:|---:|---:|---:|
| WEBGL1-LOEO-v1-03 | 先导语言干预 | 3 | 0 | 3 | 0 | 0 |
| WEBGL1-LOEO-v1-03 | 先导正常 | 12 | 0 | 12 | 0 | 0 |
| WEBGL1-LOEO-v1-03 | 先导时区干预 | 3 | 0 | 3 | 0 | 0 |
| WEBGL1-LOEO-v1-01 | 先导语言干预 | 3 | 0 | 3 | 0 | 0 |
| WEBGL1-LOEO-v1-01 | 先导正常 | 12 | 0 | 12 | 0 | 0 |
| WEBGL1-LOEO-v1-01 | 先导时区干预 | 3 | 0 | 3 | 0 | 0 |
| WEBGL1-LOEO-v1-02 | 先导语言干预 | 3 | 0 | 3 | 0 | 0 |
| WEBGL1-LOEO-v1-02 | 先导正常 | 12 | 0 | 12 | 0 | 0 |
| WEBGL1-LOEO-v1-02 | 先导时区干预 | 3 | 0 | 3 | 0 | 0 |

三折分别为 `mtc-rel-tz-6e10284c39b1b601ab406240`、`mtc-rel-tz-9c5fa0e310ba10a00e520b1c`、`mtc-rel-tz-4ae67bb9da899cc419dd525f`，均为 B_REL_TZ RETENTION。直接加载保存模型和原编码器；模型文件摘要、ID、fold、关系参数与 MODELS_FROZEN/models 索引交叉核对。三次推理不把先导 n 从 18 扩成 54。

| 配置／轮次 | 模型01 clean_pre→attack_active→clean_post | 模型02 | 模型03 |
|---|---|---|---|
| language_fr / 1 | F → F → F | F → F → F | F → F → F |
| language_fr / 2 | F → F → F | F → F → F | F → F → F |
| language_fr / 3 | F → F → F | F → F → F | F → F → F |
| timezone_tokyo / 1 | F → F → F | F → F → F | F → F → F |
| timezone_tokyo / 2 | F → F → F | F → F → F | F → F → F |
| timezone_tokyo / 3 | F → F → F | F → F → F | F → F → F |

逐条轨迹和触发子句见 [TRAJECTORIES.json](results/TRAJECTORIES.json)。不是根据目标字段保持而预填结果：所有 54 条均调用原 `predict_current`。01/02 各六条、03 五条子句在每个阶段均为 F：Native 时区对 App Web 偏移、内存包络、MIME count 的负极性阈值、App 内 language/列表首项、平台/UA 规则、以及 01/02 的 inner_height 负极性阈值。原始 MIME count=0，故 `<=0` 原子为 T、负极性子句为 F；不能把原子 T 误写为模型报警。

实际推理只接收当前 App 三层输入，不包含 Browser、阶段、标签或未来恢复。当前 App 首选语言和 Web 偏移在三阶段均为 en-US、0；独立 Browser 才在 active 阶段变成 fr-FR 或 −540。原 App 模型没有感知这些 Browser 干预；原因是其信息范围不含该端，而非选中输入缺失，也不存在持续正常报警或干预时新增报警。

新薄适配明确接受真实 v16/v2，同会话、原始状态／数值和版本均核验，不改标 v14。复用原纯编译器、冻结阈值转换、T/F/U 和预测器。附加 WebGL/几何观察缺失不会把未被选中的模块失败传播给核心模型。18 条 App 实际都有有效设备起止区间；时区全部仍走原有 GMT 固定时区的无日期分支。回归测试额外覆盖动态时区缺日期→U，未用上传时间、performance_time_origin 或当前日期补值。2026c 依赖版本保持原参数；本批固定分支不加载动态 tzdb。

## 表2：单条条件的描述性偏离

可评估=(T+F)/n；偏离列同时给 T/预定 n 和 T/可评估数。U 不算正常通过，FAILED 不删除。候选正常偏离是潜在误报风险，不是已部署检测器的误报率，也未执行整体选择约束。

| 条件 | 分组 | n | T | F | U | FAILED | 可评估 | T/预定 | T/可评估 |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| C1 | 先导正常 | 12 | 0 | 12 | 0 | 0 | 12/12 | 0/12 | 0/12 |
| C1 | 先导语言干预 | 3 | 0 | 3 | 0 | 0 | 3/3 | 0/3 | 0/3 |
| C1 | 先导时区干预 | 3 | 3 | 0 | 0 | 0 | 3/3 | 3/3 | 3/3 |
| C1 | MTC discovery | 630 | 0 | 610 | 20 | 0 | 610/630 | 0/630 | 0/610 |
| C1 | MTC development | 144 | 0 | 140 | 4 | 0 | 140/144 | 0/144 | 0/140 |
| C1 | MTC reserved_validation | 117 | 0 | 116 | 1 | 0 | 116/117 | 0/117 | 0/116 |
| C2 | 先导正常 | 12 | 0 | 12 | 0 | 0 | 12/12 | 0/12 | 0/12 |
| C2 | 先导语言干预 | 3 | 3 | 0 | 0 | 0 | 3/3 | 3/3 | 3/3 |
| C2 | 先导时区干预 | 3 | 0 | 3 | 0 | 0 | 3/3 | 0/3 | 0/3 |
| C2 | MTC discovery | 630 | 0 | 629 | 1 | 0 | 629/630 | 0/630 | 0/629 |
| C2 | MTC development | 144 | 1 | 143 | 0 | 0 | 144/144 | 1/144 | 1/144 |
| C2 | MTC reserved_validation | 117 | 0 | 117 | 0 | 0 | 117/117 | 0/117 | 0/117 |
| C3 | 先导正常 | 12 | 0 | 12 | 0 | 0 | 12/12 | 0/12 | 0/12 |
| C3 | 先导语言干预 | 3 | 3 | 0 | 0 | 0 | 3/3 | 3/3 | 3/3 |
| C3 | 先导时区干预 | 3 | 0 | 3 | 0 | 0 | 3/3 | 0/3 | 0/3 |
| C3 | MTC discovery | 630 | 0 | 629 | 1 | 0 | 629/630 | 0/630 | 0/629 |
| C3 | MTC development | 144 | 1 | 143 | 0 | 0 | 144/144 | 1/144 | 1/144 |
| C3 | MTC reserved_validation | 117 | 0 | 117 | 0 | 0 | 117/117 | 0/117 | 0/117 |
| D1 | 先导正常 | 12 | 12 | 0 | 0 | 0 | 12/12 | 12/12 | 12/12 |
| D1 | 先导语言干预 | 3 | 3 | 0 | 0 | 0 | 3/3 | 3/3 | 3/3 |
| D1 | 先导时区干预 | 3 | 3 | 0 | 0 | 0 | 3/3 | 3/3 | 3/3 |
| D1 | MTC discovery | 630 | 144 | 486 | 0 | 0 | 630/630 | 144/630 | 144/630 |
| D1 | MTC development | 144 | 30 | 114 | 0 | 0 | 144/144 | 30/144 | 30/144 |
| D1 | MTC reserved_validation | 117 | 20 | 97 | 0 | 0 | 117/117 | 20/117 | 20/117 |
| D2 | 先导正常 | 12 | 0 | 12 | 0 | 0 | 12/12 | 0/12 | 0/12 |
| D2 | 先导语言干预 | 3 | 0 | 3 | 0 | 0 | 3/3 | 0/3 | 0/3 |
| D2 | 先导时区干预 | 3 | 0 | 3 | 0 | 0 | 3/3 | 0/3 | 0/3 |
| D2 | MTC discovery | 630 | 0 | 625 | 5 | 0 | 625/630 | 0/630 | 0/625 |
| D2 | MTC development | 144 | 0 | 143 | 1 | 0 | 143/144 | 0/144 | 0/143 |
| D2 | MTC reserved_validation | 117 | 0 | 117 | 0 | 0 | 117/117 | 0/117 | 0/117 |

- C1 在 MTC 为 0 T、866 F、25 U；25 条都是 Browser offset 状态 runtime_error、质量 source_unavailable，尽管原值为 0 也不能当成有效零偏移。分组 U 为 20/4/1。没有因为跨端不一致或时间间隔而把值改 U。
- C2/C3 在 MTC 均为 1 T、889 F、1 U；唯一正常偏离位于 development：App zh-CN / Browser en-US，仍保留研究正常依据。唯一 U 位于 discovery，Browser zh-RCN 超出固定解析子集，未事后加别名。两种粒度本轮结果相同，不说明它们普遍等价，也不挑较好一个。
- D1 在 MTC 为 194 T、697 F，分组偏离 144/630、30/144、20/117；先导正常 12/12 也偏离。它主要反映容器完整偏好列表差异，不能直接当合格攻击判据。
- D2 无 T，MTC 有 6 U（5 个空列表，1 个超出标签解析范围），其余 885 F。本先导即使 Browser 修改后仍内部一致，故这个自洽关系没有新增干预信号。
- 两端 payload 时间戳差：先导 2–4 秒；MTC 2–2,833,629 秒。一条 `mtc-pair-hgpair-v1-a01c05ee9faf637996ed1ddc` 差约 32.8 天，offset 相等仍为 F。时钟、采集间隔或设置原因尚未核实；同阶段／同配对不等于原子同步。原始起止字段、时间戳及引用逐条保存，未当作更精确字段采集时刻。

## 表3：固定规则选例与未解决问题

按 sample_id 排序，每个预先声明类别最多前三条；不存在的类别明确为空。完整必要操作数、状态与原始引用见 [EXAMPLES.json](results/EXAMPLES.json)，不重复完整日志或票据。

| 类别 | 按 ID 选中的例子及必要原值 | 解释及未解决问题 |
|---|---|---|
| 正常列表不同、首选相同 | `p244-105ab2c4442ee54a8a78d718`：D1=T，`[["en-US"], ["en-US", "en"]]`；引用 `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_expanded_payloads.jsonl:6` / `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_browser_payloads.jsonl:6`<br>`p244-21c71c9ecdc9d8c4542793b5`：D1=T，`[["en-US"], ["en-US", "en"]]`；引用 `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_expanded_payloads.jsonl:3` / `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_browser_payloads.jsonl:3`<br>`p244-24ca478046ed4efa7bbada79`：D1=T，`[["en-US"], ["en-US", "en"]]`；引用 `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_expanded_payloads.jsonl:18` / `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_browser_payloads.jsonl:18` | 列表差异不能证明攻击；先导 App=[en-US]、Browser=[en-US,en]，C2=F。 |
| Browser 单端变化 | `p244-2c60218a01ef5a5d46d871ef`：C2=T，`["en-US", "fr-FR"]`；引用 `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_expanded_payloads.jsonl:8` / `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_browser_payloads.jsonl:8`<br>`p244-3d8fd644f33d8ff32347cf38`：C1=T，`[0, -540]`；引用 `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_expanded_payloads.jsonl:11` / `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_browser_payloads.jsonl:11`<br>`p244-d538c8fd999b116527303e11`：C1=T，`[0, -540]`；引用 `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_expanded_payloads.jsonl:17` / `deliverables/browser67_pilot_intake_v1/evidence_archive/data/raw_browser_payloads.jsonl:17` | 当前 App 保持 en-US/0；变化关联由 B1 三阶段证据支持，不是从模型结果推断。 |
| MTC 正常跨端偏离 | `mtc-pair-hgpair-v1-e24e526c0ef5674e87549035`：C2=T，`["zh-CN", "en-US"]`；引用 `backend_server/collection_backups/mtc_final_20260922/sources/raw_expanded_payloads.jsonl:1514` / `backend_server/collection_backups/mtc_final_20260922/sources/raw_browser_payloads.jsonl:903` | 可能为容器语言偏好或独立设置差异，未核实原因；不改标攻击。 |
| 输入或语义不足 | `mtc-pair-hgpair-v1-123335e7b1afac2b8f50b018`：C1=U，`[-480, 0]`；引用 `backend_server/collection_backups/mtc_final_20260922/sources/raw_expanded_payloads.jsonl:229` / `backend_server/collection_backups/mtc_final_20260922/sources/raw_browser_payloads.jsonl:187`<br>`mtc-pair-hgpair-v1-12601facda1ea69a595073dd`：C2=U，`["zh-CN", "zh-RCN"]`；引用 `backend_server/collection_backups/mtc_final_20260922/sources/raw_expanded_payloads.jsonl:1361` / `backend_server/collection_backups/mtc_final_20260922/sources/raw_browser_payloads.jsonl:808`<br>`mtc-pair-hgpair-v1-15ce440ed6150229c7f00e55`：C1=U，`[-480, 0]`；引用 `backend_server/collection_backups/mtc_final_20260922/sources/raw_expanded_payloads.jsonl:512` / `backend_server/collection_backups/mtc_final_20260922/sources/raw_browser_payloads.jsonl:359` | 保留 U；数值占位不等于有效观测，未用猜测补值。 |
| 完整 App 模型正常报警 | 无（0 条） | 本批不存在此类例子；所有子句均 F，没有可归因的误报触发。 |

辅助重叠统计见 [OVERLAP.json](results/OVERLAP.json)：C1 的 3 条 T 对每个 App 模型都是明确 F；C2/C3 各 3 条 T 也如此；模型 U/FAILED 的重叠均为 0。这是保存输出的交集，不是将关系 OR 入模型后的系统检出率。历史 105/126 等 App 成绩未更新。

## 下一轮判断和最小对照

C1、C2 有资格作为**下一轮有限联合选择的待检候选**，不是本轮已通过选择或获得生产资格。C1 具有额外端点信息且历史有效值未观察到正常偏离，但仍有缺测和非同步风险；C2 同样有新增先导信息，但正常语言偏好本来允许不同。C3 作为固定粗粒度比较保留，当前不能证明优于 C2；地区／脚本变化会被它漏掉。D1 保留观察，D2 保留输入自洽解释，不作为新增分类器。

最小补充应先覆盖：① 同设备、独立正常浏览器语言偏好与“仅地区／脚本变化”的成对正常及受控干预；② 两端真实采集间隔、合法设置变化和 DST 附近的正常时区对照，并另有仅 Browser 偏移改变的对照；③ 针对 runtime_error offset 和空语言列表的可重复采集状态检查；④ 核查上述长时间差配对的原始设备时钟和生命周期。正常用户偏好与同值操纵可能观测相同，单靠相等关系或调阈值不能识别意图；缺测需要改善证据，C3 的粒度信息损失也不能靠数值阈值恢复。

## 复现、测试及停止边界

从仓库根目录实际运行（新输出目录；不覆盖既有结果）：

```sh
python3 -B deliverables/browser67_cross_endpoint_diagnostic_v1/run.py run --output /tmp/b2a-diagnostic-review
```

只读保存的逐条输出重汇总（仅重写派生汇总）：

```sh
python3 -B deliverables/browser67_cross_endpoint_diagnostic_v1/run.py summarize
```

定向测试：

```sh
python3 -B -m unittest discover -s deliverables/browser67_cross_endpoint_diagnostic_v1 -p 'test_*.py' -v
python3 -B -m unittest hybridguard_agent.tests.test_latest_experiment_plan -v
```

36 项诊断测试 + 10 项原协议测试通过（含本次复审新增的 17 项边界回归）。覆盖 App/Browser 隔离、模型摘要与身份、版本／同会话、缺日期时区分支、未选模块、类型／状态／大小写／粒度、P3 方向、正常偏离不改标签、错配／缺端／重复与物理坏行、分母及禁止训练／采集调用。独立完整复现每轮仍为 54/4545 条，逐条输出、汇总、轨迹、例子、重叠及失败文件均一致；不是额外样本。

只核对实际使用的输入、模型和加载依赖，未重做 B1、未复制其 488 文件。`RUN_MANIFEST.json` 保存使用摘要；`MODEL_MANIFEST.json`、`MTC_MEMBERS.jsonl` 和 `PILOT_EVALUATION_SIDECAR.jsonl` 保留身份清单。`failures.jsonl` 当前为空；U 留在逐条输出而非丢弃。正式 readiness 仍 structural_ready=false、split_assigned_count=0、report_performance_metrics=false；诊断入口没有改旧协议或绕过其正式拒绝逻辑。

初次汇总的侧表阶段枚举修正为 B1 实际 `attack_active`；这只是元数据分组修复，未改变任何预测／条件状态。随后补齐 C1 U 行的时间诊断，完整独立复现验证结果一致。新结果仅写本目录和临时复现目录，未写历史数据、根报告或冻结模型。完成后停止，不自动提交／推送、不启动后续训练、消融或采集。
