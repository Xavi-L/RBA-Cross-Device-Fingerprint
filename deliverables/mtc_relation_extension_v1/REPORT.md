# 屏幕／资源关系扩展：已有 MTC 正常约束下的选择与评价

B_REL 攻击检出 **105/126**；保存 B 基线为 **96/126**。相同成员新增检出 9 条、损失检出 0 条。配对正常报警 B 为 0/252，B_REL 为 0/252。

**代价：每个模型在两部分 MTC 评价记录上，U 从 1 条变为 14 条；新增正常报警 0 条。** 未知增加意味着能明确判为不报警的正常记录减少，不能只用报警数不增加宣称无代价改善。各模型仍评价同一批 261 条记录。

本轮是已经使用材料上的分组开发评估，不是新独立盲测。仅扩展候选表示，保存 B 模型与预测直接复用；A 不重跑。两组正常数据各自执行 5% OR 集合报警预算，候选 MTC T/F 覆盖和最终训练明确输出覆盖均至少 90%；容量 8 条、复杂度 16、受控训练分位数编码器及选择目标保持原设置。

实际涉及 891 条不重复 MTC 记录、891 个厂商／型号／系统组合，以及 378 条受控记录。MTC 的三次模型评估不是三批独立样本，以下逐折列出。

## 同成员总体与逐配置比较

| 方案与集合 | 报警/分母 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 |
|---|---:|---:|---:|---:|---:|---|
| B 受控攻击 | 96/126 | 30 | 0 | 0 | 0 | 126/126（100.00%） |
| B 配对正常 | 0/252 | 252 | 0 | 0 | 0 | 252/252（100.00%） |
| B 受控全部 | 96/378 | 282 | 0 | 0 | 0 | 378/378（100.00%） |
| B_REL 受控攻击 | 105/126 | 21 | 0 | 0 | 0 | 126/126（100.00%） |
| B_REL 配对正常 | 0/252 | 252 | 0 | 0 | 0 | 252/252（100.00%） |
| B_REL 受控全部 | 105/378 | 273 | 0 | 0 | 0 | 378/378（100.00%） |

| 攻击配置 | B 检出 | B_REL 检出 | 变化 |
|---|---:|---:|---:|
| `w10-cdp-emulation-screen-metrics-only-v1` | 6/9 | 6/9 | +0 |
| `w10-cdp-emulation-timezone-only-v1` | 9/9 | 9/9 | +0 |
| `w6-tool-054-legacy-default-v1` | 9/9 | 9/9 | +0 |
| `w6-tool-055-legacy-default-v1` | 9/9 | 9/9 | +0 |
| `w6-tool-056-legacy-default-v1` | 9/9 | 9/9 | +0 |
| `w6-tool-058-legacy-default-v1` | 9/9 | 9/9 | +0 |
| `w9-rule-boundary-cdp-platform-only-v1` | 9/9 | 9/9 | +0 |
| `w9-rule-boundary-cdp-resource-pair-v1` | 0/9 | 9/9 | +9 |
| `w9-rule-boundary-cdp-ua-only-v1` | 9/9 | 9/9 | +0 |
| `w9-rule-boundary-cdp-ua-platform-desktop-v1` | 9/9 | 9/9 | +0 |
| `w9-rule-boundary-cdp-webdriver-only-v1` | 0/9 | 0/9 | +0 |
| `w9-stealth-boundary-languages-only-v1` | 9/9 | 9/9 | +0 |
| `w9-stealth-boundary-plugins-mime-v1` | 9/9 | 9/9 | +0 |
| `w9-stealth-boundary-webgl-pair-v1` | 0/9 | 0/9 | +0 |

屏幕单项从 6/9 变为 6/9；资源单项从 0/9 变为 9/9。

## MTC：训练与两部分评价分开

每格分母包含 U、FAILED 和 EMPTY_MODEL。明确不报警只是本模型的输出，不是未知或失败的替代标签；正常依据沿用常规采集说明。

| 方案／折／集合 | 报警/分母 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 |
|---|---:|---:|---:|---:|---:|---|
| B / 01 / MTC discovery（训练） | 8/630 | 619 | 3 | 0 | 0 | 627/630（99.52%） |
| B / 01 / MTC development（评价） | 1/144 | 142 | 1 | 0 | 0 | 143/144（99.31%） |
| B / 01 / MTC reserved_validation（评价） | 2/117 | 115 | 0 | 0 | 0 | 117/117（100.00%） |
| B / 02 / MTC discovery（训练） | 8/630 | 619 | 3 | 0 | 0 | 627/630（99.52%） |
| B / 02 / MTC development（评价） | 1/144 | 142 | 1 | 0 | 0 | 143/144（99.31%） |
| B / 02 / MTC reserved_validation（评价） | 2/117 | 115 | 0 | 0 | 0 | 117/117（100.00%） |
| B / 03 / MTC discovery（训练） | 2/630 | 625 | 3 | 0 | 0 | 627/630（99.52%） |
| B / 03 / MTC development（评价） | 0/144 | 143 | 1 | 0 | 0 | 143/144（99.31%） |
| B / 03 / MTC reserved_validation（评价） | 1/117 | 116 | 0 | 0 | 0 | 117/117（100.00%） |
| B_REL / 01 / MTC discovery（训练） | 8/630 | 571 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL / 01 / MTC development（评价） | 1/144 | 135 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL / 01 / MTC reserved_validation（评价） | 2/117 | 109 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL / 02 / MTC discovery（训练） | 8/630 | 571 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL / 02 / MTC development（评价） | 1/144 | 135 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL / 02 / MTC reserved_validation（评价） | 2/117 | 109 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL / 03 / MTC discovery（训练） | 2/630 | 577 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL / 03 / MTC development（评价） | 0/144 | 136 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL / 03 / MTC reserved_validation（评价） | 1/117 | 110 | 6 | 0 | 0 | 111/117（94.87%） |

正常依据分母和未知依据数量、按系统/采集版本分组、逐条转换及三模型一致性均在 summary.json 中保存。任何 U 增加均保留为覆盖损失，不当作降低误报。

## 新关系多提供了什么

新增两个固定关系模板：同一次 Web 探针的 visual/layout 视口边界，以及同一次 App Native 内核可见内存总量参照下的 Web 二次幂上包络。单位、适用域、历史实现差异和拒绝的等式见 SCREEN_REVIEW.md、RESOURCE_REVIEW.md。所有关系参数固定，无额外参数拟合。

最终模型实际选入：`MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE`。

| 折／关系字面量 | 攻击训练 T/分母 | 受控正常 T/分母 | MTC 正常 T/分母 | MTC T/F覆盖 | 入选 | 训练侧原因 |
|---|---:|---:|---:|---:|---|---|
| 01 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:NEGATIVE` | 60/84 | 168/168 | 579/630 | 579/630 | 否 | CONTROLLED_NORMAL_BUDGET_EXCEEDED; MTC_NORMAL_BUDGET_EXCEEDED; CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 01 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE` | 24/84 | 0/168 | 0/630 | 579/630 | 是 | SELECTED |
| 01 / `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1:NEGATIVE` | 84/84 | 168/168 | 593/630 | 593/630 | 否 | CONTROLLED_NORMAL_BUDGET_EXCEEDED; MTC_NORMAL_BUDGET_EXCEEDED; CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 01 / `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1:POSITIVE` | 0/84 | 0/168 | 0/630 | 593/630 | 否 | NO_TRAIN_ATTACK_TRIGGER; INSUFFICIENT_TRAIN_SUPPORT |
| 02 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:NEGATIVE` | 60/84 | 168/168 | 579/630 | 579/630 | 否 | CONTROLLED_NORMAL_BUDGET_EXCEEDED; MTC_NORMAL_BUDGET_EXCEEDED; CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 02 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE` | 24/84 | 0/168 | 0/630 | 579/630 | 是 | SELECTED |
| 02 / `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1:NEGATIVE` | 84/84 | 168/168 | 593/630 | 593/630 | 否 | CONTROLLED_NORMAL_BUDGET_EXCEEDED; MTC_NORMAL_BUDGET_EXCEEDED; CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 02 / `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1:POSITIVE` | 0/84 | 0/168 | 0/630 | 593/630 | 否 | NO_TRAIN_ATTACK_TRIGGER; INSUFFICIENT_TRAIN_SUPPORT |
| 03 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:NEGATIVE` | 60/84 | 168/168 | 579/630 | 579/630 | 否 | CONTROLLED_NORMAL_BUDGET_EXCEEDED; MTC_NORMAL_BUDGET_EXCEEDED; CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 03 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE` | 24/84 | 0/168 | 0/630 | 579/630 | 是 | SELECTED |
| 03 / `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1:NEGATIVE` | 84/84 | 168/168 | 593/630 | 593/630 | 否 | CONTROLLED_NORMAL_BUDGET_EXCEEDED; MTC_NORMAL_BUDGET_EXCEEDED; CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 03 / `REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1:POSITIVE` | 0/84 | 0/168 | 0/630 | 593/630 | 否 | NO_TRAIN_ATTACK_TRIGGER; INSUFFICIENT_TRAIN_SUPPORT |

逐规则贡献只解释已保存模型，不手工删规则生成另一个成绩。一个记录可能被多条关系触发，关系贡献数不能相加为样本数。

| 折／关系／集合 | 入选字面量触发 | 独有报警 | 比B新增攻击检出 | 比B新增正常报警 |
|---|---:|---:|---:|---:|
| 01 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE` / controlled_attack | 12/42 | 3 | 3 | 0 |
| 02 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE` / controlled_attack | 12/42 | 3 | 3 | 0 |
| 03 / `MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE` / controlled_attack | 12/42 | 3 | 3 | 0 |

内存关系增加了一个必须观测到的依赖，因此原来没有其他触发的记录会从 F 变为 U。其未知数量依次为 discovery 51/630、development 8/144、reserved_validation 6/117；原因计数见 summary.json。旧 deviceMemory 的 0 是含糊默认值，不能自动认作真实 0 或补为满足关系的 F。

新增检出例：`webgl1fresh-3373ac4b-b283-446f-8995-3cf186aae9f5`（`w9-rule-boundary-cdp-resource-pair-v1`），当前会话原始资源字段 `{"device_memory": 16.0, "total_memory_gb": 1.9532127380371094}`；上包络 `2.0` GiB。此说明只用当前采集，未借用 clean_pre/clean_post 做预测。

正常资源差异被保留为可评价满足：`mtc-pair-hgpair-v1-006a72c18d9adf2f7fc3db9b`，`{"device_memory": 8.0, "total_memory_gb": 10.928207397460938}`；原因 `WEB_MEMORY_WITHIN_NATIVE_POWER2_ENVELOPE`。

正常缺失例仍为未知：`mtc-pair-hgpair-v1-0f7593444184030d9497d448`，`{"device_memory": 0.0, "total_memory_gb": 2.7303314208984375}`；原因 `MEMORY_OPERAND_QUALITY_UNAVAILABLE:app.web_data.navigator_layer.device_memory`。

## 最终条件与实际正常反例

- B / WEBGL1-LOEO-v1-01：5 条，目标复杂度 10，状态 FITTED；`mtc-reselection-39aee46093ce141ef5571686`。条件：mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B / WEBGL1-LOEO-v1-02：5 条，目标复杂度 10，状态 FITTED；`mtc-reselection-535e5f2faef62bc7424f0b88`。条件：mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B / WEBGL1-LOEO-v1-03：4 条，目标复杂度 8，状态 FITTED；`mtc-reselection-56248e6001dec90e6fd48ca8`。条件：mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）。
- B_REL / WEBGL1-LOEO-v1-01：6 条，目标复杂度 12，状态 FITTED；`mtc-rel-32aa33c7ffce80569b002e12`。条件：MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B_REL / WEBGL1-LOEO-v1-02：6 条，目标复杂度 12，状态 FITTED；`mtc-rel-fe7d389097ff210ced2183f6`。条件：MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B_REL / WEBGL1-LOEO-v1-03：5 条，目标复杂度 10，状态 FITTED；`mtc-rel-67a2bd2c906851f14ec9bc5c`。条件：MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）。

绝对值条件仍保留：inner_height 在 2/3 个新模型中，时区偏移在 3/3 个新模型中。本轮新增关系没有自动替换掉这些条件；实际正常显示/时区反例继续按原始输出保留。

下面保留已经触发模型的常规采集记录；报警不改变历史正常依据或 unlabeled 标签：

- HUAWEI / DBY2-W00 / Android 12，`mtc-pair-hgpair-v1-09fad2755842bc4e33a02d2f`，B/discovery：`inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）`；实际字段 `{"inner_height": 991}`。
- samsung / SM-F9660 / Android 16，`mtc-pair-hgpair-v1-1b4dc203495c4d05f67faa66`，B/discovery：`inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）`；实际字段 `{"inner_height": 756}`。
- Google / Pixel 9 / Android 17，`mtc-pair-hgpair-v1-3c1c4c103a641a3c3882afb4`，B/discovery：`inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）`；实际字段 `{"inner_height": 719}`。
- HTC / HTC U11 plus / Android 9，`mtc-pair-hgpair-v1-4317c8ba25b65fc2abb5cd37`，B/discovery：`timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）`；实际字段 `{"timezone_offset": -420}`。
- HUAWEI / LON-L29 / Android 8.0.0，`mtc-pair-hgpair-v1-f405df575df9b1041190e417`，B/discovery：`timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）`；实际字段 `{"timezone_offset": 0}`。
- asus / ASUS_I002D / Android 12，`mtc-pair-hgpair-v1-80bf24fd7b7f19393eace992`，B/reserved_validation：`timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）`；实际字段 `{"timezone_offset": -420}`。

## 仍不能解决的问题与下一步

视口关系检查的是同 Web 观测的一致性；协调修改 inner 与 visual 的干预可保持这一关系，不能据此补造 Native 等式。旧 Native displayMetrics 不是 WebView 的内容矩形，缺少同步窗口/insets/page zoom 参照，现有材料不能可靠检验完整跨层屏幕映射。屏幕/资源规则是否提升检出以以上保存结果为准，不因为低于 5% 就称它们为官方不变量。

Web 内存是粗粒度暴露值，Native totalMem 是内核可见内存总量，不是当前剩余可用内存，也不等于完整物理 RAM；两者不要求相等。CPU 参照字段不足时不发明核数。旧 MTC 的 WebGL1 和 webdriver 原始观测缺失保持不变；本轮不靠此类规则恢复检出，也不填 F。

最小补采仅作为后续建议：同次稳定布局时刻采 WebView 内容矩形、窗口 insets、方向、page zoom/visual scale和时间；如继续检查 CPU，采明确口径的当前进程可用处理器数并保留浏览器限制说明。已有关系的正常反例应先解释其采集口径与浏览器实现，不能改标攻击或转 U。本轮没有启动任何新采集。

## 运行与复现

实际拟合记录：`{"actual_fit_calls": 6, "encoder_fit_calls": 3, "engineering_reruns": 0, "planned_fit_calls": 6, "relation_parameter_fit_calls": 0}`。具体逐次调用见 FIT_CALLS.jsonl/EXECUTION.json；报告汇总不调用拟合或预测。

```bash
# 从保存结果重新汇总
python3 deliverables/mtc_relation_extension_v1/summarize.py --output-dir deliverables/mtc_relation_extension_v1
# 在新的输出目录复现有限实验
python3 deliverables/mtc_relation_extension_v1/run_experiment.py run --output-dir /tmp/mtc_relation_reproduce
```

逐条预测保存在 predictions.jsonl.gz；原始引用、模型身份、规则和新增关系的字段值/不可用原因可逐条追查。summary.json 保存总体、逐配置、逐折子集、逐规则贡献和简洁分组统计；models.json 和 trials 保存模型及训练轨迹。所有旧模型、数据和报告保持原样。

针对性测试 109 项通过、0 项失败（新增 49、既有回归 60）。预定与实际成员逐 ID 匹配：保存 6102 条模型输出，受控每方案 378 条、MTC 每模型 891 条。核验 6102 条保存输出的极性/OR，3051 条 B 预测原样复用。汇总与复核没有新增拟合或预测；完整命令与检查见 VALIDATION.json。
