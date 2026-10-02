# 内存关系的单字段对照与取值变化验证

旧模型新增的9条检出全部可由单字段对照解释（R_WEB8触发9/9）。新批次中，有效变化18次，R_REL触发18次、R_WEB8触发6次，仅关系识别12次；无可观测效应6次单列。

本轮固定比较单条条件 R_REL 与 R_WEB8；完整 B/B_REL 六个保存模型另列。模型训练 0 次，关系、阈值、编码器、选择器和未知语义均未修改。旧378条受控记录与891条MTC代表记录属于已有材料上的事后补充比较。

R_REL 沿用同次 App 的 Native 内核可见总内存 N（GiB）与 Web 暴露 W，检验 W 是否超过不小于 N 的最小二次幂。R_WEB8 只检验有效 W>8；8本身为F，缺失、默认0和错误类型保留U。固定条件与六个模型身份在新采集前写入 SETTINGS.json。版本依据见 SOURCES.md。

## 已有数据：完整分母

| 集合 | 条件 | T | F | U | FAILED | T/F覆盖 |
|---|---|---:|---:|---:|---:|---|
| controlled/all | R_REL | 36 | 342 | 0 | 0 | 378/378 |
| controlled/all | R_WEB8 | 18 | 360 | 0 | 0 | 378/378 |
| controlled/attack | R_REL | 36 | 90 | 0 | 0 | 126/126 |
| controlled/attack | R_WEB8 | 18 | 108 | 0 | 0 | 126/126 |
| controlled/normal | R_REL | 0 | 252 | 0 | 0 | 252/252 |
| controlled/normal | R_WEB8 | 0 | 252 | 0 | 0 | 252/252 |
| mtc/discovery | R_REL | 0 | 579 | 51 | 0 | 579/630 |
| mtc/discovery | R_WEB8 | 0 | 579 | 51 | 0 | 579/630 |
| mtc/development | R_REL | 0 | 136 | 8 | 0 | 136/144 |
| mtc/development | R_WEB8 | 0 | 136 | 8 | 0 | 136/144 |
| mtc/reserved_validation | R_REL | 0 | 111 | 6 | 0 | 111/117 |
| mtc/reserved_validation | R_WEB8 | 0 | 111 | 6 | 0 | 111/117 |
| saved_B_REL_additional_detections | R_REL | 9 | 0 | 0 | 0 | 9/9 |
| saved_B_REL_additional_detections | R_WEB8 | 9 | 0 | 0 | 0 | 9/9 |

原保存 B_REL 相比 B 新增的 9 条检出中，R_WEB8 同时触发 9 条。因此这批新增检出可以由显眼的单字段 W>8 解释，不能仅凭旧 resource-pair 结果证明 Native 参照不可替代。旧配置还同时设置了 hardwareConcurrency=48，本轮不把其效应归因混在一起。

| 旧攻击配置 | R_REL T/全分母 | R_WEB8 T/全分母 | 共同可评估 | 共同子集联合状态 R_REL/R_WEB8 |
|---|---:|---:|---:|---|
| w10-cdp-emulation-screen-metrics-only-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w10-cdp-emulation-timezone-only-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w6-tool-054-legacy-default-v1 | 9/9 | 0/9 | 9 | {'T/F': 9} |
| w6-tool-055-legacy-default-v1 | 9/9 | 0/9 | 9 | {'T/F': 9} |
| w6-tool-056-legacy-default-v1 | 9/9 | 9/9 | 9 | {'T/T': 9} |
| w6-tool-058-legacy-default-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-rule-boundary-cdp-platform-only-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-rule-boundary-cdp-resource-pair-v1 | 9/9 | 9/9 | 9 | {'T/T': 9} |
| w9-rule-boundary-cdp-ua-only-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-rule-boundary-cdp-ua-platform-desktop-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-rule-boundary-cdp-webdriver-only-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-stealth-boundary-languages-only-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-stealth-boundary-plugins-mime-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |
| w9-stealth-boundary-webgl-pair-v1 | 0/9 | 0/9 | 9 | {'F/F': 9} |

共同子集只用于辅助比较，未删除完整分母中的U或FAILED。summary.json 保存每组完整分母与共同子集的T/F/U/FAILED、联合状态、Web实际值分布和差异样本ID。historical.jsonl.gz 保留每条 N/W、字段状态、原始引用和原因。

| MTC集合 | W值分布 | 联合状态 R_REL/R_WEB8 |
|---|---|---|
| mtc/discovery | {'8.0': 357, '4.0': 197, '0.0': 51, '2.0': 24, '1.0': 1} | {'F/F': 579, 'U/U': 51} |
| mtc/development | {'8.0': 87, '4.0': 42, '2.0': 7, '0.0': 8} | {'F/F': 136, 'U/U': 8} |
| mtc/reserved_validation | {'2.0': 9, '8.0': 63, '4.0': 39, '0.0': 6} | {'F/F': 111, 'U/U': 6} |

旧126条攻击中：共同触发 18/126，仅R_REL触发 18/126，仅R_WEB8触发 0/126。R_REL的独有触发发生在旧多字段配置，不是新的memory-only隔离证据；与完整B/B_REL模型新增检出9条是不同分析层次。

常规采集正常依据沿用 mtc_cap8_replay_v1 的标签侧表；不覆盖历史 unlabeled 标签。MTC三个子集630/144/117分开，不把同一条记录的多模型输出当独立样本。

## 同样的 Web 值，来自各自同次 Native 参照的比较

- 正常MTC `mtc-pair-hgpair-v1-007de61ded2503c95b7c2c1c`：N=3.4720077514648438 GiB，W=4，R_REL=F。来源 `hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/paired_244.jsonl:128`；原App归档行 162，会话 `6c3abd99-b43e-4219-a146-6056ae848d8f`。
- 正常MTC `mtc-pair-hgpair-v1-0101722e2d013dbcd86e14a2`：N=5.258552551269531 GiB，W=4，R_REL=F。来源 `hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/paired_244.jsonl:60`；原App归档行 73，会话 `f09b8de7-331f-4a01-816b-72694fe780e1`。
- 正常MTC `mtc-pair-hgpair-v1-006a72c18d9adf2f7fc3db9b`：N=10.928207397460938 GiB，W=8，R_REL=F。来源 `hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/paired_244.jsonl:455`；原App归档行 671，会话 `3d2c015c-a304-4da9-9875-9433a007bcce`。
- 正常MTC `mtc-pair-hgpair-v1-015aa32174a9397deb52c6bc`：N=11.239200592041016 GiB，W=8，R_REL=F。来源 `hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/paired_244.jsonl:599`；原App归档行 964，会话 `1d6fc8aa-0b45-4039-99e5-37ec43bbbd27`。

这些例子各自保留原始绑定；它们与新实验的并列展示不是把不同记录拼成一个样本。

## 新 memory-only 本地采集

预定72个位置（3环境×4目标×2轮×3阶段），真实接收 72 条；不是72台设备。
- api29_swiftshader：COMPLETE，接收24/24；App 1.6.7-expanded-v2.2-webgl1，API 29；清理自有进程=True。
- api30_swiftshader：COMPLETE，接收24/24；App 1.6.7-expanded-v2.2-webgl1，API 30；清理自有进程=True。
- api36_swiftshader：COMPLETE，接收24/24；App 1.6.7-expanded-v2.2-webgl1，API 36；清理自有进程=True。

执行、变化和恢复分别计数：`{"execution": {"EXECUTED": 24}, "effect": {"NO_OBSERVABLE_EFFECT": 6, "OBSERVABLE_TARGET_CHANGE": 18}, "recovery": {"RESTORED": 24}, "confound_status": {"NO_OBSERVED_NON_TARGET_CHANGE": 24}}`。

| 环境 | 目标W | 轮次 | 操作 | 实际效果 | 恢复 | R_REL | R_WEB8 | 非目标差异 |
|---|---:|---:|---|---|---|---|---|---|
| api29_swiftshader | 2 | 1 | EXECUTED | NO_OBSERVABLE_EFFECT | RESTORED | F | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 2 | 2 | EXECUTED | NO_OBSERVABLE_EFFECT | RESTORED | F | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 4 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 4 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 8 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 8 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 16 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | T | NO_OBSERVED_NON_TARGET_CHANGE |
| api29_swiftshader | 16 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | T | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 2 | 1 | EXECUTED | NO_OBSERVABLE_EFFECT | RESTORED | F | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 2 | 2 | EXECUTED | NO_OBSERVABLE_EFFECT | RESTORED | F | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 4 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 4 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 8 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 8 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 16 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | T | NO_OBSERVED_NON_TARGET_CHANGE |
| api30_swiftshader | 16 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | T | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 2 | 1 | EXECUTED | NO_OBSERVABLE_EFFECT | RESTORED | F | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 2 | 2 | EXECUTED | NO_OBSERVABLE_EFFECT | RESTORED | F | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 4 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 4 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 8 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 8 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | F | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 16 | 1 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | T | NO_OBSERVED_NON_TARGET_CHANGE |
| api36_swiftshader | 16 | 2 | EXECUTED | OBSERVABLE_TARGET_CHANGE | RESTORED | T | T | NO_OBSERVED_NON_TARGET_CHANGE |

逐三阶段检查 44 项主要非目标字段；hardwareConcurrency实际值集合为 [1]。检查覆盖导航器、屏幕、图形、自动化表面、时区以及Native总内存，差异逐项保留；无差异仅限这些观测，不代表未观测状态全部相同。

| 同次新App记录 | N（GiB） | 上包络 | W | R_REL | R_WEB8 |
|---|---:|---:|---:|---|---|
| api29_swiftshader / `memoryonly-e2003ba0-806e-40a4-b850-991b38918116` | 1.9532127380371094 | 2.0 | 8.0 | T | F |
| api30_swiftshader / `memoryonly-7afde4bc-f3d2-420f-bd23-427b887c0a13` | 1.9370002746582031 | 2.0 | 8.0 | T | F |
| api36_swiftshader / `memoryonly-974388f2-0831-482d-a65c-5cfaf721d2b1` | 1.9252243041992188 | 2.0 | 8.0 | T | F |

这些N/W均来自表中各自同一次App会话，原始归档路径和行号见 new_batch.jsonl.gz 的 source_binding；与上面的正常MTC W=8相比，差别来自各自的Native参照。

| 新批次完整分母 | 条件 | T | F | U | FAILED | T/F覆盖 |
|---|---|---:|---:|---:|---:|---|
| all | R_REL | 18 | 54 | 0 | 0 | 72/72 |
| all | R_WEB8 | 6 | 66 | 0 | 0 | 72/72 |
| normal_phases | R_REL | 0 | 48 | 0 | 0 | 48/48 |
| normal_phases | R_WEB8 | 0 | 48 | 0 | 0 | 48/48 |

| 有效变化统计 | 条件 | T | F | U | FAILED | 全分母 |
|---|---|---:|---:|---:|---:|---:|
| observable_changes | R_REL | 18 | 0 | 0 | 0 | 18 |
| observable_changes | R_WEB8 | 6 | 12 | 0 | 0 | 18 |
| observable_unconfounded | R_REL | 18 | 0 | 0 | 0 | 18 |
| observable_unconfounded | R_WEB8 | 6 | 12 | 0 | 0 | 18 |
| no_observable_effect | R_REL | 0 | 6 | 0 | 0 | 6 |
| no_observable_effect | R_WEB8 | 0 | 6 | 0 | 0 | 6 |

实际可观测变化中，仅关系识别、R_WEB8不识别的有 12 次；目标值为 [4, 8]。无可观测效应单列，不当成检出成功。实际改变但落在包络内的F仍是检出边界，不重标为正常。

## 完整模型：六个保存模型分别评价

| 方案／折 | 集合 | 报警 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出/全分母 |
|---|---|---:|---:|---:|---:|---:|---|
| B/WEBGL1-LOEO-v1-01 | all | 0 | 72 | 0 | 0 | 0 | 72/72 |
| B/WEBGL1-LOEO-v1-01 | normal | 0 | 48 | 0 | 0 | 0 | 48/48 |
| B/WEBGL1-LOEO-v1-01 | active_attempts | 0 | 24 | 0 | 0 | 0 | 24/24 |
| B/WEBGL1-LOEO-v1-01 | observable_changes | 0 | 18 | 0 | 0 | 0 | 18/18 |
| B/WEBGL1-LOEO-v1-02 | all | 0 | 72 | 0 | 0 | 0 | 72/72 |
| B/WEBGL1-LOEO-v1-02 | normal | 0 | 48 | 0 | 0 | 0 | 48/48 |
| B/WEBGL1-LOEO-v1-02 | active_attempts | 0 | 24 | 0 | 0 | 0 | 24/24 |
| B/WEBGL1-LOEO-v1-02 | observable_changes | 0 | 18 | 0 | 0 | 0 | 18/18 |
| B/WEBGL1-LOEO-v1-03 | all | 0 | 72 | 0 | 0 | 0 | 72/72 |
| B/WEBGL1-LOEO-v1-03 | normal | 0 | 48 | 0 | 0 | 0 | 48/48 |
| B/WEBGL1-LOEO-v1-03 | active_attempts | 0 | 24 | 0 | 0 | 0 | 24/24 |
| B/WEBGL1-LOEO-v1-03 | observable_changes | 0 | 18 | 0 | 0 | 0 | 18/18 |
| B_REL/WEBGL1-LOEO-v1-01 | all | 18 | 54 | 0 | 0 | 0 | 72/72 |
| B_REL/WEBGL1-LOEO-v1-01 | normal | 0 | 48 | 0 | 0 | 0 | 48/48 |
| B_REL/WEBGL1-LOEO-v1-01 | active_attempts | 18 | 6 | 0 | 0 | 0 | 24/24 |
| B_REL/WEBGL1-LOEO-v1-01 | observable_changes | 18 | 0 | 0 | 0 | 0 | 18/18 |
| B_REL/WEBGL1-LOEO-v1-02 | all | 18 | 54 | 0 | 0 | 0 | 72/72 |
| B_REL/WEBGL1-LOEO-v1-02 | normal | 0 | 48 | 0 | 0 | 0 | 48/48 |
| B_REL/WEBGL1-LOEO-v1-02 | active_attempts | 18 | 6 | 0 | 0 | 0 | 24/24 |
| B_REL/WEBGL1-LOEO-v1-02 | observable_changes | 18 | 0 | 0 | 0 | 0 | 18/18 |
| B_REL/WEBGL1-LOEO-v1-03 | all | 18 | 54 | 0 | 0 | 0 | 72/72 |
| B_REL/WEBGL1-LOEO-v1-03 | normal | 0 | 48 | 0 | 0 | 0 | 48/48 |
| B_REL/WEBGL1-LOEO-v1-03 | active_attempts | 18 | 6 | 0 | 0 | 0 | 24/24 |
| B_REL/WEBGL1-LOEO-v1-03 | observable_changes | 18 | 0 | 0 | 0 | 0 | 18/18 |

模型逐条输出及实际触发条件见 new_batch.jsonl.gz。预测只读当前App原始记录；三阶段关系只用于事后变化/恢复核验。非目标字段差异在 summary.json 的 triplets 中逐项保存，混杂记录保留，完整模型报警不能全部归因于内存。

实际触发条件集合：`{"B": [], "B_REL": ["MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE:POSITIVE"]}`。这里分别报告同一批记录的三个模型，不把结果相加为更多样本。

## 能力与限制

W=16 的旧新增检出并不必须依赖 Native。新批次4/8的额外识别和同次Native值见上述实测结果。降低W、改成仍在当前包络内的值、原本相同的设置均不能被这条单向上界关系当作偏离。Native过小或无效、Web默认0/缺失等保留U；来源绑定错误为FAILED。

本轮固定目标没有低于2的值，没有为补充结果追加目标或更改AVD内存。设置2但原W为2的记录不证明能识别包络内的有效修改。“降低W”或“改变但仍在包络内”的漏检边界由固定公式和单元测试说明，不能冒充真实采集的检测结果。

内存两条件在891条MTC上均未触发，65条旧Web默认0仍为U，不能把它们当明确正常。完整模型仍保留非内存条件的旧报警：development三折为1、1、0条/144，reserved_validation为2、2、1条/117，主要是inner_height/时区；这些保存输出的上下文在summary.json中另列，不是本轮新增误报。B_REL每折评价U仍为8+6条，未通过单字段对照偷偷补F。

MTC正常触发与未知以上表为准，不因报警改变正常依据。这里没有验证所有浏览器/OEM共享内存口径，不宣称官方攻击不变量，也不以少量模拟器验证替代真机正常人群证据。新小批次不与旧126条攻击合并计算总体检出率。

## 复现

```bash
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/memory_relation_validation_v1/evaluate.py summarize
# 新输出目录中先复制 SETTINGS.json，再依次运行：
python3 deliverables/memory_relation_validation_v1/evaluate.py historical --output-dir <新目录>
python3 deliverables/memory_relation_validation_v1/collect.py --output-dir <新目录>
python3 deliverables/memory_relation_validation_v1/evaluate.py new --output-dir <新目录>
```

采集入口拒绝覆盖已有 runs；仅启动与清理本轮自有进程。原始记录位于各环境 runs/*/backend/raw_expanded_payloads.jsonl，操作与撤销证据位于 operations.jsonl、*.cdp.json 和 environment.json。

测试与检查：43项测试通过，模型拟合0次；完整命令及检查见 VALIDATION.json。
