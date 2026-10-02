# 时区关系：已有 MTC 正常约束下的选择与本地变化验证

保存 B_REL 检出 105/126，B_REL_TZ 检出 **105/126**；配对正常报警分别为 0/252 和 0/252。

本轮回答：在这批真实采集里，正常系统换时区的6个中间位置，新关系及三个新模型均不报警；仅Web修改的6次有效干预仍全部检出。MTC评价逐折报警从3/261、3/261、1/261降为2/261、2/261、0/261，U均保持14/261；没有增加未知或损失原攻击检出。改善是减少正常时区差异误报，而非提高总攻击检出。

同成员使用 378 条受控记录和 891 条 MTC 代表记录（891 个厂商／型号／系统组合）。这是已经使用材料上的开发评价，不是新独立盲测；MTC 同一记录被三个模型评价，不能累加为三倍独立样本。

本轮只增加一个日期感知时区关系。原 50 候选、内存/屏幕关系、受控训练编码器、双正常 5% 报警预算、90% MTC 可评估/模型覆盖要求、8 条/复杂度 16 和选择目标保持原样。三个折分别新 GREEDY 再 R_KEEP，共 6 次拟合，未额外训练或调参。

## 字段含义与日期依据

Native rawOffset 是标准时偏移（分钟，UTC 以东为正），Web getTimezoneOffset 是采集时的反向偏移。新关系使用同次 App 的 Native IANA ID 和设备侧开始/结束时间，以 Python zoneinfo、固定 IANA tzdb 2026c 算出当前偏移。只比较偏移，不比较时区 ID 文本；合法别名和相同偏移的不同地区不会仅因名字报警。

开始时间在 Native/Web 读取前，结束时间在二者读取后；这是包围范围，不是两者瞬间同步。跨偏移转换、动态地区缺可靠日期、未知 ID 或质量不足保留 U；执行/绑定错误为 FAILED。旧语法固定偏移域可在缺日期时复用原规则，绝不使用“今天”或上传时刻替代历史日期。0 和 -1 都是有效偏移。依据与采集代码见 SEMANTICS.md。

## 同成员模型评价

| 方案/集合 | 报警/预定数 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 |
|---|---:|---:|---:|---:|---:|---|
| B_REL 受控攻击 | 105/126 | 21 | 0 | 0 | 0 | 126/126（100.00%） |
| B_REL 配对正常 | 0/252 | 252 | 0 | 0 | 0 | 252/252（100.00%） |
| B_REL_TZ 受控攻击 | 105/126 | 21 | 0 | 0 | 0 | 126/126（100.00%） |
| B_REL_TZ 配对正常 | 0/252 | 252 | 0 | 0 | 0 | 252/252（100.00%） |
| B_REL/01/discovery | 8/630 | 571 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL/01/development | 1/144 | 135 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL/01/reserved_validation | 2/117 | 109 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL/02/discovery | 8/630 | 571 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL/02/development | 1/144 | 135 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL/02/reserved_validation | 2/117 | 109 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL/03/discovery | 2/630 | 577 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL/03/development | 0/144 | 136 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL/03/reserved_validation | 1/117 | 110 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL_TZ/01/discovery | 6/630 | 573 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL_TZ/01/development | 1/144 | 135 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL_TZ/01/reserved_validation | 1/117 | 110 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL_TZ/02/discovery | 6/630 | 573 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL_TZ/02/development | 1/144 | 135 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL_TZ/02/reserved_validation | 1/117 | 110 | 6 | 0 | 0 | 111/117（94.87%） |
| B_REL_TZ/03/discovery | 0/630 | 579 | 51 | 0 | 0 | 579/630（91.90%） |
| B_REL_TZ/03/development | 0/144 | 136 | 8 | 0 | 0 | 136/144（94.44%） |
| B_REL_TZ/03/reserved_validation | 0/117 | 111 | 6 | 0 | 0 | 111/117（94.87%） |

MTC discovery 为训练正常约束；144 条 development 与 117 条 reserved_validation 分开评价。已确认正常报警比例以各子集有依据的成员为分母，见 summary.json；未知/失败不当正常正确。全部计划成员逐 ID 对齐，实际处理数和失败数单列。

| 原攻击配置 | B_REL | B_REL_TZ |
|---|---:|---:|
| w10-cdp-emulation-screen-metrics-only-v1 | 6/9 | 6/9 |
| w10-cdp-emulation-timezone-only-v1 | 9/9 | 9/9 |
| w6-tool-054-legacy-default-v1 | 9/9 | 9/9 |
| w6-tool-055-legacy-default-v1 | 9/9 | 9/9 |
| w6-tool-056-legacy-default-v1 | 9/9 | 9/9 |
| w6-tool-058-legacy-default-v1 | 9/9 | 9/9 |
| w9-rule-boundary-cdp-platform-only-v1 | 9/9 | 9/9 |
| w9-rule-boundary-cdp-resource-pair-v1 | 9/9 | 9/9 |
| w9-rule-boundary-cdp-ua-only-v1 | 9/9 | 9/9 |
| w9-rule-boundary-cdp-ua-platform-desktop-v1 | 9/9 | 9/9 |
| w9-rule-boundary-cdp-webdriver-only-v1 | 0/9 | 0/9 |
| w9-stealth-boundary-languages-only-v1 | 9/9 | 9/9 |
| w9-stealth-boundary-plugins-mime-v1 | 9/9 | 9/9 |
| w9-stealth-boundary-webgl-pair-v1 | 0/9 | 0/9 |

## 选择与贡献

- B_REL/01：6 条，复杂度 12，`mtc-rel-32aa33c7ffce80569b002e12`。条件：MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B_REL/02：6 条，复杂度 12，`mtc-rel-fe7d389097ff210ced2183f6`。条件：MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B_REL/03：5 条，复杂度 10，`mtc-rel-67a2bd2c906851f14ec9bc5c`。条件：MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; timezone_offset > -480.0（CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）。
- B_REL_TZ/01：6 条，复杂度 12，`mtc-rel-tz-6e10284c39b1b601ab406240`。条件：MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS:POSITIVE; MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B_REL_TZ/02：6 条，复杂度 12，`mtc-rel-tz-9c5fa0e310ba10a00e520b1c`。条件：MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS:POSITIVE; MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）; inner_height > 710.0（CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE）。
- B_REL_TZ/03：5 条，复杂度 10，`mtc-rel-tz-4ae67bb9da899cc419dd525f`。条件：MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS:POSITIVE; MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE; mime_types_count > 0.0（CONTROL:app.web_data.automation_surface_layer.mime_types_count:LE:0.0:NEGATIVE）; 语言首项关系偏离（RSR-LANG-FIRST-v1:POSITIVE）; UA/platform 关系偏离（CAT:NW-006:POSITIVE）。

| 折/时区候选 | 训练攻击 T | 受控正常 T | MTC T/F | MTC T | 入选 | 原因 |
|---|---:|---:|---:|---:|---|---|
| 01/NEGATIVE | 78/84 | 168/168 | 630/630 | 630/630 | False | CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 01/POSITIVE | 6/84 | 0/168 | 630/630 | 0/630 | True | SELECTED |
| 02/NEGATIVE | 78/84 | 168/168 | 630/630 | 630/630 | False | CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 02/POSITIVE | 6/84 | 0/168 | 630/630 | 0/630 | True | SELECTED |
| 03/NEGATIVE | 78/84 | 168/168 | 630/630 | 630/630 | False | CONTROLLED_SET_NORMAL_BUDGET; MTC_SET_NORMAL_BUDGET |
| 03/POSITIVE | 6/84 | 0/168 | 630/630 | 0/630 | True | SELECTED |

新时区关系在 3/3 个模型入选，旧绝对偏移条件在 0/3 个新模型保留；没有预先删除旧条件。
- 折 01：261 条 MTC 评价的报警 3→2，U 14→14；时区关系在42条该折攻击中触发 3 条，独有检出 3 条，重复触发 0 条。
- 折 02：261 条 MTC 评价的报警 3→2，U 14→14；时区关系在42条该折攻击中触发 3 条，独有检出 3 条，重复触发 0 条。
- 折 03：261 条 MTC 评价的报警 1→0，U 14→14；时区关系在42条该折攻击中触发 3 条，独有检出 3 条，重复触发 0 条。

新关系在 MTC 的630/144/117条分别全部为F；没有新时区U或正常T。完整模型仍保留内存缺测导致的51/8/6条U，前两折剩余正常报警来自高度条件。本轮不修改这些规则。全部14个攻击配置的检出与保存B_REL一致，没有检出损失。

逐规则独有/重复报警、训练排序轨迹、正常/攻击触发与不可用原因保存在 summary.json。贡献是保存模型的解释，不是事后删规则后的新模型成绩。

## 既有正常时区反例

- `mtc-pair-hgpair-v1-4317c8ba25b65fc2abb5cd37`（HTC HTC U11 plus / Android 9，discovery）：Native `Asia/Phnom_Penh`，标准偏移 420，期望 Web -420.0，实际 -420；关系 F，旧输出 MANIPULATION_ALERT → 新输出 NO_ALERT。
- `mtc-pair-hgpair-v1-f405df575df9b1041190e417`（HUAWEI LON-L29 / Android 8.0.0，discovery）：Native `GMT`，标准偏移 0，期望 Web 0，实际 0；关系 F，旧输出 MANIPULATION_ALERT → 新输出 NO_ALERT。
- `mtc-pair-hgpair-v1-80bf24fd7b7f19393eace992`（asus ASUS_I002D / Android 12，reserved_validation）：Native `Asia/Phnom_Penh`，标准偏移 420，期望 Web -420.0，实际 -420；关系 F，旧输出 MANIPULATION_ALERT → 新输出 NO_ALERT。

逐条设备日期、字段值、同次原始引用和各折输出完整保存在 NORMAL_TIMEZONE_EXAMPLES.json；报警不会改变常规采集依据。正常 T 也保留，不能为减少报警改成 U。

## 36 个本地预定位置

三个环境、UTC/Los_Angeles、L 正常系统变化/A Web 单独修改、前/中/后三阶段；这是三个环境的重复观察，不是 36 台设备。候选和六次拟合已在采集前冻结。

| 集合 | 位置数 | 单条件输出 |
|---|---:|---|
| all_planned | 36 | `{"R_ABSOLUTE": {"F": 24, "T": 12}, "R_TZ": {"F": 30, "T": 6}}` |
| confirmed_normal | 30 | `{"R_ABSOLUTE": {"F": 24, "T": 6}, "R_TZ": {"F": 30}}` |
| L_system_change | 6 | `{"R_ABSOLUTE": {"T": 6}, "R_TZ": {"F": 6}}` |
| A_web_only | 6 | `{"R_ABSOLUTE": {"T": 6}, "R_TZ": {"T": 6}}` |
| A_observable | 6 | `{"R_ABSOLUTE": {"T": 6}, "R_TZ": {"T": 6}}` |

| 集合/完整模型 | 报警/分母 | F | U | FAILED | EMPTY | 覆盖 |
|---|---:|---:|---:|---:|---:|---|
| confirmed_normal/B_REL/WEBGL1-LOEO-v1-01 | 6/30 | 24 | 0 | 0 | 0 | 30/30（100.00%） |
| confirmed_normal/B_REL/WEBGL1-LOEO-v1-02 | 6/30 | 24 | 0 | 0 | 0 | 30/30（100.00%） |
| confirmed_normal/B_REL/WEBGL1-LOEO-v1-03 | 6/30 | 24 | 0 | 0 | 0 | 30/30（100.00%） |
| confirmed_normal/B_REL_TZ/WEBGL1-LOEO-v1-01 | 0/30 | 30 | 0 | 0 | 0 | 30/30（100.00%） |
| confirmed_normal/B_REL_TZ/WEBGL1-LOEO-v1-02 | 0/30 | 30 | 0 | 0 | 0 | 30/30（100.00%） |
| confirmed_normal/B_REL_TZ/WEBGL1-LOEO-v1-03 | 0/30 | 30 | 0 | 0 | 0 | 30/30（100.00%） |
| A_observable/B_REL/WEBGL1-LOEO-v1-01 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| A_observable/B_REL/WEBGL1-LOEO-v1-02 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| A_observable/B_REL/WEBGL1-LOEO-v1-03 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| A_observable/B_REL_TZ/WEBGL1-LOEO-v1-01 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| A_observable/B_REL_TZ/WEBGL1-LOEO-v1-02 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| A_observable/B_REL_TZ/WEBGL1-LOEO-v1-03 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| L_system_change/B_REL/WEBGL1-LOEO-v1-01 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| L_system_change/B_REL/WEBGL1-LOEO-v1-02 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| L_system_change/B_REL/WEBGL1-LOEO-v1-03 | 6/6 | 0 | 0 | 0 | 0 | 6/6（100.00%） |
| L_system_change/B_REL_TZ/WEBGL1-LOEO-v1-01 | 0/6 | 6 | 0 | 0 | 0 | 6/6（100.00%） |
| L_system_change/B_REL_TZ/WEBGL1-LOEO-v1-02 | 0/6 | 6 | 0 | 0 | 0 | 6/6（100.00%） |
| L_system_change/B_REL_TZ/WEBGL1-LOEO-v1-03 | 0/6 | 6 | 0 | 0 | 0 | 6/6（100.00%） |

真实原始记录绑定 36/36；确认正常 30/30 个预定正常位置。三阶段恢复 12/12 组。有效Web单独变化 6/6；非目标混杂 0 组。

- api29_swiftshader：API 29，App 1.6.7-expanded-v2.2-webgl1，完成 12/12；原系统设置 `Asia/Shanghai` / auto_time_zone=1，最终恢复 RESTORED，自有进程退出 True。
- api30_swiftshader：API 30，App 1.6.7-expanded-v2.2-webgl1，完成 12/12；原系统设置 `Asia/Shanghai` / auto_time_zone=1，最终恢复 RESTORED，自有进程退出 True。
- api36_swiftshader：API 36，App 1.6.7-expanded-v2.2-webgl1，完成 12/12；原系统设置 `Asia/Shanghai` / auto_time_zone=1，最终恢复 RESTORED，自有进程退出 True。

API29/30 实际 WebView 为 91.0.4472.114，API36 为 134.0.6998.135，均在采集前核对。主要非目标原始检测字段没有变化；可用内存、运行时间和网络速率等自然波动保留。CDP额外运行时观察出现过视口瞬态，未进入原始采集屏幕字段，不将其混为检测输入。

实际执行、目标字段变化、恢复和非目标变化独立于报警判断；无可观测效应不算检出成功。normal_basis 依据有效观测和操作/撤销证据，不以 phase 单独定正常；失败位置保留。细节见 LOCAL_EVALUATION.json 与 new_batch.jsonl.gz。

## 能力边界与后续最小改进

关系识别的是同次Native地区/日期与Web当前偏移的冲突。同偏移的ID修改、Native与Web一起协调变化不会因此触发；正常系统换时区本身不应当被当作攻击。设备端时区数据库版本未知，可能与固定2026c存在规则差异；进程缓存、采集中途手动改设置也可能造成正常偏离，因此这仍是探索性一致性证据，不是官方攻击不变量。

动态地区缺少可靠采集日期、跨转换区间或未知ID时必须U。设备开始/结束时间只能包围读值，不能证明设置在整个范围绝对稳定。若继续完善，最小补采是设备tzdb版本及Native当前有效偏移/读值时间；不需要重采全部MTC或调整本轮阈值。Python TZif解析使用已测试的CPython接口，换运行时须重跑时区边界测试。

## 正常依据修正与复现

上一轮内存实验离线复核24组全部恢复，48/48条确认正常，两条件及六模型各0/48报警，原结果不变。pre 需有效同次观测和正常流程；post 还需成功操作、明确撤销和恢复证据。失败/未恢复不能进入已确认正常分母。复核结果见 MEMORY_NORMAL_REVIEW.md/.json，原报告未覆盖。

```bash
python3 -B deliverables/timezone_relation_validation_v1/summarize.py
# 复现六次拟合及历史评价，必须新输出目录
python3 -B deliverables/timezone_relation_validation_v1/run_experiment.py run --output-dir /tmp/timezone-reproduce
# 本地采集必须已有 MODELS_FROZEN.json 且只使用本轮自有实例
python3 -B deliverables/timezone_relation_validation_v1/collect.py --output-dir /tmp/timezone-reproduce
python3 -B deliverables/timezone_relation_validation_v1/evaluate_local.py evaluate --output-dir /tmp/timezone-reproduce
```

summary.json、逐条输出和训练轨迹可复核；报告汇总不训练、不预测、不采集。旧数据、模型、规则和报告保持不变，未提交或推送。

针对性验证：81项测试通过；6102条保存输出的规则OR与结果一致，3051条B_REL基线原样复用，六模型旧编码器与同折基线一致。测试命令和清理核验见VALIDATION.json；小范围工程修正见ENGINEERING_CORRECTIONS.json，实际拟合6次、采集36条、重拟合/重采均0。
