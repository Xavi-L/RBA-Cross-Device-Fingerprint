# MTC 正常约束下的规则重新选择

本轮已完成固定两方案、三个环境留一折的训练和评价。这是已有数据上的分组开发评估；历史 reserved_validation 名称不表示新的独立盲测。

上一轮另列的 11 条整层缺失记录和 6 条同 session 额外观测本轮不新增训练或预测，去向仍见上一轮报告；本轮固定比较 891 主代表、137 配对重复及 654 App-only。

**工程修正披露：初次运行的评价结果已经打开，随后因旧观测适配错误按相同设置重跑。旧材料中的 -1 数值哨兵被误当作真实观测；修正针对输入解释，不改变候选定义、阈值生成、参数或模型选择方法。初次运行保留，不作为最终结果替换隐藏。**

实际拟合：初始 12 次 + 修正后 12 次 = 累计 24 次；编码器累计 6 次。首轮材料保留于 `attempt_01_pre_sentinel_fix.tar.gz`。详见 ENGINEERING_CORRECTIONS.json；下表仅汇总修正后的正式运行，EXECUTION.json 的调用数只对应当前一次运行。

只读比对保留的首轮和修正后结果：适配修正改变候选可用状态，最终入选条件、同折编码器和全部 16272 条对齐预测的最终决策均未改变。

- **A 完整候选池**：受控攻击检出 114/126（90.48%）；三个模型的 MTC 结果分别见下表，不选择最好一折。
- **B 历史 MTC 兼容候选模型**：受控攻击检出 96/126（76.19%）；三个模型的 MTC 结果分别见下表，不选择最好一折。

A 保留完整 50 项基础候选及原有数值展开；B 是历史 MTC 兼容候选模型，候选在 MTC 训练部分的 T/F 可评估比例和最终模型明确输出覆盖都要求至少 90%。两方案各折编码器只由本折受控训练记录生成，MTC 不生成阈值。

两个正常集合分别执行 floor(记录数 × 5%) 的 OR 集合报警预算，不能合并分母。每折受控正常 168 条允许 8 条、MTC discovery 630 条允许 31 条。5% 是固定开发操作点，不是部署标准，也不保证评价集达到它。容量上限 8 条、复杂度 16；每方案从新 GREEDY 开始再运行 R_KEEP。

保存预测包含 378 条不重复受控记录、1682 条不重复 MTC 记录、906 个 MTC 厂商／型号／系统组合。MTC 同一记录被三个模型计算，不增加独立样本量；下表逐模型列出。

## 受控数据的相同成员对照

三折留出受控记录互不重复，允许合并；未知、失败和空模型均在分母内。“全部记录不报警”以完整 378 条计算，包含漏检攻击，不能解释成正确正常数增加。

| 方案 | 攻击检出 | 配对正常报警 | 明确输出覆盖 | 全部记录不报警 | U | FAILED | EMPTY_MODEL |
|---|---|---|---|---:|---:|---:|---:|
| 原 CAP8 | 126/126（100.00%） | 0/252（0.00%） | 378/378（100.00%） | 252 | 0 | 0 | 0 |
| A 完整候选池 | 114/126（90.48%） | 0/252（0.00%） | 378/378（100.00%） | 264 | 0 | 0 | 0 |
| B 历史 MTC 兼容候选模型 | 96/126（76.19%） | 0/252（0.00%） | 378/378（100.00%） | 282 | 0 | 0 | 0 |

| 攻击配置 | 原 CAP8 | A 完整候选池 | B 历史 MTC 兼容候选模型 |
|---|---|---|---|
| w10-cdp-emulation-screen-metrics-only-v1 | 9/9（100.00%） | 6/9（66.67%） | 6/9（66.67%） |
| w10-cdp-emulation-timezone-only-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w6-tool-054-legacy-default-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w6-tool-055-legacy-default-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w6-tool-056-legacy-default-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w6-tool-058-legacy-default-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w9-rule-boundary-cdp-platform-only-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w9-rule-boundary-cdp-resource-pair-v1 | 9/9（100.00%） | 0/9（0.00%） | 0/9（0.00%） |
| w9-rule-boundary-cdp-ua-only-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w9-rule-boundary-cdp-ua-platform-desktop-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w9-rule-boundary-cdp-webdriver-only-v1 | 9/9（100.00%） | 9/9（100.00%） | 0/9（0.00%） |
| w9-stealth-boundary-languages-only-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w9-stealth-boundary-plugins-mime-v1 | 9/9（100.00%） | 9/9（100.00%） | 9/9（100.00%） |
| w9-stealth-boundary-webgl-pair-v1 | 9/9（100.00%） | 9/9（100.00%） | 0/9（0.00%） |

## MTC：逐模型、逐子集

每格保留各自完整分母。报警为已经观察到的触发；U 不能算正常通过，EMPTY_MODEL 不能算可用检测器。正常采集依据沿用上一轮 DATA_NOTES.md 的任务和批次记录；无依据记录仅计算报警比例，不回写历史标签。

| 方案 | 折 | 子集 | 预定/处理 | 报警 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 | 有正常依据的报警比例 |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| BASELINE | 01 | discovery（训练） | 630/630 | 597 | 0 | 33 | 0 | 0 | 597/630（94.76%） | 597/630（94.76%） |
| BASELINE | 01 | development（评价） | 144/144 | 135 | 0 | 9 | 0 | 0 | 135/144（93.75%） | 135/144（93.75%） |
| BASELINE | 01 | reserved_validation（评价） | 117/117 | 112 | 0 | 5 | 0 | 0 | 112/117（95.73%） | 112/117（95.73%） |
| BASELINE | 01 | 配对重复（补充） | 137/137 | 127 | 0 | 10 | 0 | 0 | 127/137（92.70%） | 127/137（92.70%） |
| BASELINE | 01 | App-only（补充） | 654/654 | 607 | 0 | 47 | 0 | 0 | 607/654（92.81%） | 607/654（92.81%） |
| BASELINE | 02 | discovery（训练） | 630/630 | 597 | 0 | 33 | 0 | 0 | 597/630（94.76%） | 597/630（94.76%） |
| BASELINE | 02 | development（评价） | 144/144 | 135 | 0 | 9 | 0 | 0 | 135/144（93.75%） | 135/144（93.75%） |
| BASELINE | 02 | reserved_validation（评价） | 117/117 | 112 | 0 | 5 | 0 | 0 | 112/117（95.73%） | 112/117（95.73%） |
| BASELINE | 02 | 配对重复（补充） | 137/137 | 127 | 0 | 10 | 0 | 0 | 127/137（92.70%） | 127/137（92.70%） |
| BASELINE | 02 | App-only（补充） | 654/654 | 607 | 0 | 47 | 0 | 0 | 607/654（92.81%） | 607/654（92.81%） |
| BASELINE | 03 | discovery（训练） | 630/630 | 597 | 0 | 33 | 0 | 0 | 597/630（94.76%） | 597/630（94.76%） |
| BASELINE | 03 | development（评价） | 144/144 | 135 | 0 | 9 | 0 | 0 | 135/144（93.75%） | 135/144（93.75%） |
| BASELINE | 03 | reserved_validation（评价） | 117/117 | 112 | 0 | 5 | 0 | 0 | 112/117（95.73%） | 112/117（95.73%） |
| BASELINE | 03 | 配对重复（补充） | 137/137 | 127 | 0 | 10 | 0 | 0 | 127/137（92.70%） | 127/137（92.70%） |
| BASELINE | 03 | App-only（补充） | 654/654 | 607 | 0 | 47 | 0 | 0 | 607/654（92.81%） | 607/654（92.81%） |
| A | 01 | discovery（训练） | 630/630 | 8 | 0 | 622 | 0 | 0 | 8/630（1.27%） | 8/630（1.27%） |
| A | 01 | development（评价） | 144/144 | 1 | 0 | 143 | 0 | 0 | 1/144（0.69%） | 1/144（0.69%） |
| A | 01 | reserved_validation（评价） | 117/117 | 2 | 0 | 115 | 0 | 0 | 2/117（1.71%） | 2/117（1.71%） |
| A | 01 | 配对重复（补充） | 137/137 | 1 | 0 | 136 | 0 | 0 | 1/137（0.73%） | 1/137（0.73%） |
| A | 01 | App-only（补充） | 654/654 | 4 | 0 | 650 | 0 | 0 | 4/654（0.61%） | 4/654（0.61%） |
| A | 02 | discovery（训练） | 630/630 | 8 | 0 | 622 | 0 | 0 | 8/630（1.27%） | 8/630（1.27%） |
| A | 02 | development（评价） | 144/144 | 1 | 0 | 143 | 0 | 0 | 1/144（0.69%） | 1/144（0.69%） |
| A | 02 | reserved_validation（评价） | 117/117 | 2 | 0 | 115 | 0 | 0 | 2/117（1.71%） | 2/117（1.71%） |
| A | 02 | 配对重复（补充） | 137/137 | 1 | 0 | 136 | 0 | 0 | 1/137（0.73%） | 1/137（0.73%） |
| A | 02 | App-only（补充） | 654/654 | 4 | 0 | 650 | 0 | 0 | 4/654（0.61%） | 4/654（0.61%） |
| A | 03 | discovery（训练） | 630/630 | 2 | 0 | 628 | 0 | 0 | 2/630（0.32%） | 2/630（0.32%） |
| A | 03 | development（评价） | 144/144 | 0 | 0 | 144 | 0 | 0 | 0/144（0.00%） | 0/144（0.00%） |
| A | 03 | reserved_validation（评价） | 117/117 | 1 | 0 | 116 | 0 | 0 | 1/117（0.85%） | 1/117（0.85%） |
| A | 03 | 配对重复（补充） | 137/137 | 1 | 0 | 136 | 0 | 0 | 1/137（0.73%） | 1/137（0.73%） |
| A | 03 | App-only（补充） | 654/654 | 0 | 0 | 654 | 0 | 0 | 0/654（0.00%） | 0/654（0.00%） |
| B | 01 | discovery（训练） | 630/630 | 8 | 619 | 3 | 0 | 0 | 627/630（99.52%） | 8/630（1.27%） |
| B | 01 | development（评价） | 144/144 | 1 | 142 | 1 | 0 | 0 | 143/144（99.31%） | 1/144（0.69%） |
| B | 01 | reserved_validation（评价） | 117/117 | 2 | 115 | 0 | 0 | 0 | 117/117（100.00%） | 2/117（1.71%） |
| B | 01 | 配对重复（补充） | 137/137 | 1 | 136 | 0 | 0 | 0 | 137/137（100.00%） | 1/137（0.73%） |
| B | 01 | App-only（补充） | 654/654 | 4 | 626 | 24 | 0 | 0 | 630/654（96.33%） | 4/654（0.61%） |
| B | 02 | discovery（训练） | 630/630 | 8 | 619 | 3 | 0 | 0 | 627/630（99.52%） | 8/630（1.27%） |
| B | 02 | development（评价） | 144/144 | 1 | 142 | 1 | 0 | 0 | 143/144（99.31%） | 1/144（0.69%） |
| B | 02 | reserved_validation（评价） | 117/117 | 2 | 115 | 0 | 0 | 0 | 117/117（100.00%） | 2/117（1.71%） |
| B | 02 | 配对重复（补充） | 137/137 | 1 | 136 | 0 | 0 | 0 | 137/137（100.00%） | 1/137（0.73%） |
| B | 02 | App-only（补充） | 654/654 | 4 | 626 | 24 | 0 | 0 | 630/654（96.33%） | 4/654（0.61%） |
| B | 03 | discovery（训练） | 630/630 | 2 | 625 | 3 | 0 | 0 | 627/630（99.52%） | 2/630（0.32%） |
| B | 03 | development（评价） | 144/144 | 0 | 143 | 1 | 0 | 0 | 143/144（99.31%） | 0/144（0.00%） |
| B | 03 | reserved_validation（评价） | 117/117 | 1 | 116 | 0 | 0 | 0 | 117/117（100.00%） | 1/117（0.85%） |
| B | 03 | 配对重复（补充） | 137/137 | 1 | 136 | 0 | 0 | 0 | 137/137（100.00%） | 1/137（0.73%） |
| B | 03 | App-only（补充） | 654/654 | 0 | 630 | 24 | 0 | 0 | 630/654（96.33%） | 0/654（0.00%） |

与原模型的变化均用同一折、同一子集比较：

- A / 01：主代表合计 891 条，报警变化 -833，明确不报警变化 +0，U 变化 +833。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。
- A / 02：主代表合计 891 条，报警变化 -833，明确不报警变化 +0，U 变化 +833。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。
- A / 03：主代表合计 891 条，报警变化 -841，明确不报警变化 +0，U 变化 +841。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。
- B / 01：主代表合计 891 条，报警变化 -833，明确不报警变化 +876，U 变化 -43。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。
- B / 02：主代表合计 891 条，报警变化 -833，明确不报警变化 +876，U 变化 -43。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。
- B / 03：主代表合计 891 条，报警变化 -841，明确不报警变化 +884，U 变化 -43。分割用途保持独立，上面的逐子集结果才是训练与评价比较依据。

至少一部分新模型的未知多于明确不报警：只能称观察到的报警减少，完整判断仍受限，不能直接宣称已成为低误报可用模型。

正常主代表仍触发的新模型条件及实际原值示例（从已保存逐条预测取值，型号只作说明）：

- `CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE`：`mtc-pair-hgpair-v1-09fad2755842bc4e33a02d2f`，HUAWEI / DBY2-W00 / Android 12，discovery；原值 `[{"field": "app.web_data.screen_layer.inner_height", "value": 991, "status": "observed"}]`。
- `CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE`：`mtc-pair-hgpair-v1-1b4dc203495c4d05f67faa66`，samsung / SM-F9660 / Android 16，discovery；原值 `[{"field": "app.web_data.screen_layer.inner_height", "value": 756, "status": "observed"}]`。
- `CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE`：`mtc-pair-hgpair-v1-4317c8ba25b65fc2abb5cd37`，HTC / HTC U11 plus / Android 9，discovery；原值 `[{"field": "app.web_data.execution_layer.timezone_offset", "value": -420, "status": "observed"}]`。
- `CONTROL:app.web_data.execution_layer.timezone_offset:LE:-480.0:NEGATIVE`：`mtc-pair-hgpair-v1-f405df575df9b1041190e417`，HUAWEI / LON-L29 / Android 8.0.0，discovery；原值 `[{"field": "app.web_data.execution_layer.timezone_offset", "value": 0, "status": "observed"}]`。

## 选中了什么，淘汰依据是什么

候选统计只使用各折受控训练数据和 MTC discovery；攻击支持、配置覆盖、轨迹从不包含 MTC。完整逐候选统计、集合分数和操作轨迹保存在各 trial/training.json。以下新模型均为 R_KEEP 最终结果。

- A / 折 01,02：移除 `CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE; CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE`；新增 `CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE`。
- A / 折 03：移除 `CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE; CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE`；新增 `无`。
- B / 折 01,02：移除 `CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE; CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE; RSR-WEBDRIVER-STATE-v1:POSITIVE; RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1:POSITIVE`；新增 `CONTROL:app.web_data.screen_layer.inner_height:LE:710.0:NEGATIVE`。
- B / 折 03：移除 `CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE; CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE; RSR-WEBDRIVER-STATE-v1:POSITIVE; RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1:POSITIVE`；新增 `无`。

| 方案/折 | 状态 / 规则数 | 最终条件（数值为极性后的实际报警方向） |
|---|---|---|
| A/01 | FITTED / 7 | WebGL1 查询等价性偏离；mime_types_count > 0.0；webdriver 为 true；timezone_offset > -480.0；语言首项关系偏离；UA/platform 关系偏离；inner_height > 710.0 |
| B/01 | FITTED / 5 | mime_types_count > 0.0；timezone_offset > -480.0；语言首项关系偏离；UA/platform 关系偏离；inner_height > 710.0 |
| A/02 | FITTED / 7 | WebGL1 查询等价性偏离；mime_types_count > 0.0；webdriver 为 true；timezone_offset > -480.0；语言首项关系偏离；UA/platform 关系偏离；inner_height > 710.0 |
| B/02 | FITTED / 5 | mime_types_count > 0.0；timezone_offset > -480.0；语言首项关系偏离；UA/platform 关系偏离；inner_height > 710.0 |
| A/03 | FITTED / 6 | WebGL1 查询等价性偏离；mime_types_count > 0.0；webdriver 为 true；timezone_offset > -480.0；语言首项关系偏离；UA/platform 关系偏离 |
| B/03 | FITTED / 4 | mime_types_count > 0.0；timezone_offset > -480.0；语言首项关系偏离；UA/platform 关系偏离 |

各模型完整身份见 models.json。训练逐候选情况：

| 方案/折 | 展开 literal | 准入 | 完全无法在 MTC 训练上检验的入选条件 |
|---|---:|---:|---|
| A/01 | 124 | 93 | webdriver 为 true、WebGL1 查询等价性偏离 |
| B/01 | 124 | 89 | 无 |
| A/02 | 124 | 93 | webdriver 为 true、WebGL1 查询等价性偏离 |
| B/02 | 124 | 89 | 无 |
| A/03 | 106 | 74 | webdriver 为 true、WebGL1 查询等价性偏离 |
| B/03 | 106 | 70 | 无 |

准入不等于能进入 OR 集合，仍须通过两类正常集合预算；准入/预算拒绝原因完整保存在训练统计。A 的 WebGL1 和 webdriver 全 U，0 次观察触发不能解释为误报率 0。

显示替代条件的差异来自各折受控训练生成的阈值：折 01 的 `inner_height > 710.0`：MTC 训练正常触发 6/630，入选；折 02 的 `inner_height > 710.0`：MTC 训练正常触发 6/630，入选；折 03 的 `inner_height > 639.0`：MTC 训练正常触发 37/630，未入选。前两折保留了显示干预的 6/9 检出；第三折损失 3/9。它是有训练支持的替代信号，但仍会把正常显示尺寸差异当成报警；37 条已经高于 MTC 允许的 31 条，不能为保留检出而放宽预算。

## 新漏检与替代条件

下面先用留出实际结果定位新漏检，再用已保存训练候选统计解释。单条在训练中可行不代表可与其他规则组成可行 OR 模型，也不保证留出集检出；启发式未找到组合不等于理论不可能。

重复原因按配置合并说明；每折完整候选计数和证据仍保存在 summary.json：

- **w10-cdp-emulation-screen-metrics-only-v1**：A 漏检 3 条、B 漏检 3 条。

  在出现该类新漏检的折／方案中，逐项诊断发现能触发留出攻击的候选均未通过其训练准入或单条正常预算；原因包括 `CONTROLLED_SET_NORMAL_BUDGET; INSUFFICIENT_TRAIN_SUPPORT; MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT; MTC_SET_NORMAL_BUDGET`。结论限于本轮生成的候选及固定设置，不代表不存在新表达或其他算法的改进空间。

  原条件 `device_pixel_ratio > 2.625（CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE）`：受控训练正常触发 0/168，MTC 训练触发 518/630；未入选原因 `MTC_SET_NORMAL_BUDGET`。

  例如候选 `inner_height > 639.0（CONTROL:app.web_data.screen_layer.inner_height:LE:639.0:NEGATIVE）` 也有训练配置触发，但受控正常 0/168、MTC 正常 37/630 已超出至少一个独立预算。

- **w9-rule-boundary-cdp-resource-pair-v1**：A 漏检 9 条、B 漏检 9 条。

  在出现该类新漏检的折／方案中，逐项诊断发现能触发留出攻击的候选均未通过其训练准入或单条正常预算；原因包括 `CONTROLLED_SET_NORMAL_BUDGET; INSUFFICIENT_TRAIN_SUPPORT; MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT; MTC_SET_NORMAL_BUDGET`。结论限于本轮生成的候选及固定设置，不代表不存在新表达或其他算法的改进空间。

  原条件 `device_memory > 2.0（CONTROL:app.web_data.navigator_layer.device_memory:LE:2.0:NEGATIVE）`：受控训练正常触发 0/168，MTC 训练触发 554/630；MTC 51/630 为 U；未入选原因 `MTC_SET_NORMAL_BUDGET`。

  例如候选 `hardware_concurrency > 1.0（CONTROL:app.web_data.navigator_layer.hardware_concurrency:LE:1.0:NEGATIVE）` 也有训练配置触发，但受控正常 0/168、MTC 正常 630/630 已超出至少一个独立预算。

- **w9-rule-boundary-cdp-webdriver-only-v1**：B 漏检 9 条。

  在出现该类新漏检的折／方案中，逐项诊断发现能触发留出攻击的候选均未通过其训练准入或单条正常预算；原因包括 `CONTROLLED_SET_NORMAL_BUDGET; INSUFFICIENT_TRAIN_SUPPORT; MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT; MTC_SET_NORMAL_BUDGET`。结论限于本轮生成的候选及固定设置，不代表不存在新表达或其他算法的改进空间。

  原条件 `webdriver 为 true（RSR-WEBDRIVER-STATE-v1:POSITIVE）`：受控训练正常触发 0/168，MTC 训练触发 0/630；MTC 630/630 为 U；未入选原因 `MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT`。

  例如候选 `downlink_mbps <= 9.575（CONTROL:app.web_data.network_api_layer.downlink_mbps:LE:9.575:POSITIVE）` 也有训练配置触发，但受控正常 44/168、MTC 正常 148/630 已超出至少一个独立预算。

- **w9-stealth-boundary-webgl-pair-v1**：B 漏检 9 条。

  在出现该类新漏检的折／方案中，逐项诊断发现能触发留出攻击的候选均未通过其训练准入或单条正常预算；原因包括 `CONTROLLED_SET_NORMAL_BUDGET; INSUFFICIENT_TRAIN_SUPPORT; MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT; MTC_SET_NORMAL_BUDGET`。结论限于本轮生成的候选及固定设置，不代表不存在新表达或其他算法的改进空间。

  原条件 `WebGL1 查询等价性偏离（RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1:POSITIVE）`：受控训练正常触发 0/168，MTC 训练触发 0/630；MTC 630/630 为 U；未入选原因 `MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT`。

  例如候选 `audio_sample_rate <= 46050.0（CONTROL:app.web_data.audio_layer.audio_sample_rate:LE:46050.0:POSITIVE）` 也有训练配置触发，但受控正常 84/168、MTC 正常 8/630 已超出至少一个独立预算。

实际数值重叠例子（训练后只读核对，不影响模型）：

- `app.web_data.navigator_layer.device_memory` 在正常 Xiaomi / 23113RKC6C / Android 16 和攻击 `w6-tool-055-legacy-default-v1` 中同为 `8.0`。正常 ID `mtc-pair-hgpair-v1-006a72c18d9adf2f7fc3db9b`，攻击 ID `webgl1fresh-19087ce2-c09a-4725-87dc-df392437d0d9`。

完整引用见 OVERLAP_EXAMPLES.json。相同暴露值不表示物理硬件相等，但说明该绝对数值本身无法区分这些正常与干预记录。

## 旧观测限制和下一步

旧 MTC 没有 WebGL1 数字／数字字符串查询原始观测，webdriver false 投影不能恢复属性存在与读取状态；这些条件保留 U。旧 deviceMemory / hardwareConcurrency 默认 0 按哨兵处理，不能当作真实零值。来源、标签、型号、任务 ID 和历史 split 只作关联，不进入预测。

训练正常反例若让原高内存／高 DPR 条件超出独立预算，说明单一绝对阈值把合法设备范围和攻击值混在一起；本轮由同一通用预算机制淘汰，不手工封禁字段名。替代条件是否有支持、是否可观测和是否超出预算分别保存在候选统计与 new_misses 中。

最优先的具体修正方向是显示规则：核对正常高 viewport 设备与 screen-metrics 干预的同次字段关系，避免把 inner_height 的绝对高度继续当作通用攻击证据。本轮的 height 替代规则仍在命中正常显示差异，不能因为其报警数低于 5% 就赋予攻击语义。随后再针对 resource-pair 缺少可行替代的问题检查资源关系候选；不能把 Web 内存和 Native 物理内存强设为相等。

对于 A 仍依赖的未知条件，最小补采是同次 App 主 frame 的 WebGL1 原始查询和 webdriver 属性存在／读取状态／类型；补采用于验证正常侧表现，不能通过填 F 修饰当前结果。本轮没有新增候选关系或启动采集；额外拟合仅为已披露的工程适配修复。

## 运行记录和复现

执行摘要：`{"actual_fit_calls": 12, "all_fits_closed": true, "all_models_frozen_at": "2026-10-02T10:36:36.333352+00:00", "elapsed_seconds": 5.401639499999874, "encoder_fit_calls": 3, "encoder_source": "controlled_train_only_shared_per_fold", "engineering_corrections": [], "experiment_id": "mtc-constrained-reselection-v1", "fit_status_counts": {"FITTED": 12}, "input_adapter_version": "mtc-constrained-webgl50-input-adapter-v2", "mtc_evaluation_ids_used_for_fit": [], "new_evaluation_opened_during_training": false, "planned_fit_calls": 12}`。逐次拟合记录与完整训练成员见 EXECUTION.json。

```bash
# 仅从本轮保存的预测、训练统计和清单重建报告；不加载原数据，不训练、不预测
python3 deliverables/mtc_constrained_reselection_v1/summarize.py --output-dir deliverables/mtc_constrained_reselection_v1
```

`predictions.jsonl.gz` 无损压缩保存逐条结果及规则证据（汇总也兼容未压缩 .jsonl）；`models.json` 保存模型身份与路径；`summary.json` 保存完整逐配置、逐模型、逐规则和简洁系统分组统计及新漏检解释。SETTINGS.json 固定方案，EXECUTION.json 记录实际拟合次数和工程修正。原模型、历史数据和旧结果未作为汇总写入目标。

测试：60 项通过、0 项失败。只读复核 12 个阶段模型、3 个同折共享编码器、10848 条保存预测 OR 状态、3780 条 discovery 预测/训练状态一致；复核新增拟合 0 次、新增预测 0 次。完整命令和结果见 VALIDATION.json。
