# S03 STEP_REPORT

完成时间：2026-09-23T12:15:23.997807+00:00。本地 HEAD：`b3d8badee44577787bdcd3cb22d70a155b1bb613`，与用户指定外部核查版本一致。本步工程验收 PASS；仅完成来源、角色、语义门控和证据家族，不表示检测策略或性能已验证。S04 未执行，S03 未提交、未推送。

## 1. 依赖与历史记录

开工读取 `EXECUTION_PLAN.md`、`EXECUTION_STATUS.json`、S01/S02 的 STEP_REPORT、VALIDATION、FOCUSED_TESTS、SUMMARY 及关联台账。保存验收分别为 13 / 15 项聚焦测试通过，报告和验收记录无实质冲突；本轮没有重跑 S01/S02，也没有覆盖其产物。

S01 报告完成于 2026-09-23T08:46:35Z，S02 报告完成于 2026-09-23T11:02:32Z；其中“仍在本地/尚未推送”等字样对应当时的推送前记录。随后 S01/S02 已分别随 a68fcec / b3d8bad 交付；S03 以当前真实 HEAD 为基线，不因旧字样回退状态。详见 `DEPENDENCY_REVIEW.json`。

继续沿用 S01 的 262 条事实、准入与 3 个环境关联组。S02 为 262 成功、0 拒绝：准入攻击三态 162、较低证据攻击 45、时间对照 54、不完整尝试 1；88 组阶段关联包括 69 组攻击三态、18 组时间对照和 1 组不完整尝试。空失败包仍引用 S01 inventory，不增加阶段。以上是已保存依赖事实，本轮没有读入真实 payload 执行门控或检测。

## 2. 来源与角色审定

| 来源 | 总规则 | alert_candidate | observation_only | context_only | collector_consistency | deployment_policy | 报警候选家族 | 来源有未决项的规则 | 必要报警门控不可实现的规则 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E | 23 | 0 | 18 | 4 | 1 | 0 | 0 | 20 | 11 |
| O_u | 9 | 0 | 6 | 2 | 1 | 0 | 0 | 9 | 4 |
| H | 14 | 0 | 14 | 0 | 0 | 0 | 0 | 14 | 1 |
| C | 11 | 0 | 0 | 3 | 6 | 2 | 0 | 7 | 0 |

合计 57 项 ACTIVE、38 observation_only、9 context_only、8 collector_consistency、2 deployment_policy、0 alert_candidate。计数与预期 E23/O_u9/H14/C11 一致；官方定义、研究者推导、经验筛选及容差来历逐条分列。O_u 指当前目录未标记本轮经验筛选的官方派生关系，不能称为纯官方规则。

**重要结构限制：计划建议的 8 条候选、5 个家族全部保留为观察，最终可报警家族为 0。** UA 默认/合法覆盖来源、可变 http.agent 的未覆盖状态，以及 GPU 合法 host/remote/hybrid rendering 的排除条件不能由当前允许字段完整确认。默认和 settings 快照相等不补足采集期间的来源语义；Dalvik/ANGLE 字样也不补足条件。降级依据为源码、语义和合成反例，没有依据正式预测、检测率或来源期望收益挑规则。逐候选字段、反例与必要条件见 `SEMANTIC_DECISIONS.md` 第 5 节和 `decision_roles.json`。

E、O_u、H、C 四组均预先没有报警角色，因此后续二值检测增量受结构限制。不能把零增量当作实测证据认定任何来源无价值，也不能将可能的全弃判解释为零误报或安全。未把计划推荐白名单当作已通过资格审定的清单。S04 合同的这一限制已显式保留，未实现、运行或调整 S04 策略。

来源精确清单如下；各组合完整清单另见 `source_conditions.json`。

- **E（23）**：`CORE-002`, `NVW-001`, `NVW-002`, `NVW-005`, `NW-001`, `NW-002`, `NW-005`, `NW-006`, `NW-007`, `P3-SCREEN-APP`, `P3-SCREEN-BROWSER`, `P3-UA-DEFAULT`, `P3-UA-SETTINGS`, `P3-X-CORES`, `P3-X-DPR`, `P3-X-LANGUAGE`, `P3-X-SCREEN-SIZE`, `P3-X-TIMEZONE-OFFSET`, `P3-X-TOUCH`, `PHYS-005`, `PHYS-006`, `SCENE-001`, `WVWEB-004`。
- **O_u（9）**：`OFFDER-BRIDGE-001`, `OFFDER-DEVCONFIG-001`, `OFFDER-GPU-001`, `OFFDER-NET-001`, `OFFDER-OS-001`, `OFFDER-OS-002`, `OFFDER-TOUCH-001`, `OFFDER-UA-001`, `OFFDER-UA-002`。
- **H（14）**：`P3-COLOR-APP`, `P3-COLOR-BROWSER`, `P3-MEM-AVAILABLE`, `P3-SENSOR-ACCELEROMETER`, `P3-SENSOR-GRAVITY_SENSOR`, `P3-SENSOR-GYROSCOPE`, `P3-SENSOR-LIGHT_SENSOR`, `P3-SENSOR-MAGNETIC_FIELD`, `P3-SENSOR-PRESSURE_SENSOR`, `P3-SENSOR-PROXIMITY_SENSOR`, `P3-SENSOR-ROTATION_VECTOR`, `P3-SENSOR-STEP_COUNTER`, `P3-SENSOR-STEP_DETECTOR`, `P3-UA-REDUCED-BROWSER`。
- **C（11）**：`NVW-003`, `NVW-004`, `OFFDER-PACKAGE-001`, `P3-GPU-COPY`, `P3-PROVIDER-PARSE`, `P3-SENSOR-NAME_COUNT`, `P3-SENSOR-TYPE-COUNT`, `P3-SENSOR-TYPE-ORDER`, `P3-SENSOR-VENDOR_COUNT`, `TOL-001`, `WVWEB-002`。

## 3. 产品语义与一手来源

本轮核查 19 份相关一手文档，记录可确认的文档版本/日期、适用产品和未确认修订。Chrome desktop phase 5=M107；Chrome Android phase 6=M110；当前 Android WebView 文档描述 Android 17 默认 UA reduction。冻结 Browser 谓词的 >=107/Android10 范围与细分时间表存在差异，新覆盖层保存差异并拒绝把 Android10/K 当真实 OS/model，冻结 v3 保持原样。依据与链接见 `SEMANTIC_DECISIONS.md` 第 2 节及 `primary_source_review.json`。

Dalvik 只约束 system agent 的解释范围，不能当当前 JS UA；GPU 软件回退与合法 host rendering 不自动报警。9 条 Browser 依赖检查保留来源登记，但当前 App177 缺少独立 Browser 时保持 UNKNOWN，不补造字段。读取攻击仓库 week10 ledger 仅作独立命名空间参照，不合并其 W7/W6 编号。本轮不重挖规则、不扩大为完整历史存档审计。

## 4. 家族与重叠

57 条恰好各属于一个 decision_family，共 27 个家族。原 evidence_family 逐条保留；9 个家族跨来源共享：

| 共享 decision_family | 来源 | 精确规则 ID |
|---|---|---|
| app_os | E, O_u | NW-002, OFFDER-OS-001 |
| app_surface | C, E, O_u | NW-006, OFFDER-UA-001, WVWEB-002, WVWEB-004 |
| debug_cleartext | C, E, O_u | NVW-005, OFFDER-DEVCONFIG-001, TOL-001 |
| featureapp_bridge | E, O_u | CORE-002, OFFDER-BRIDGE-001 |
| host_os | E, O_u | NVW-002, OFFDER-OS-002 |
| host_ua | E, O_u | OFFDER-UA-002, P3-UA-DEFAULT, P3-UA-SETTINGS |
| mobile_touch | E, O_u | NW-007, OFFDER-TOUCH-001 |
| native_app_gpu_family | C, E, O_u | NW-005, OFFDER-GPU-001, P3-GPU-COPY |
| sensor_structure | C, H | P3-SENSOR-ACCELEROMETER, P3-SENSOR-GRAVITY_SENSOR, P3-SENSOR-GYROSCOPE, P3-SENSOR-LIGHT_SENSOR, P3-SENSOR-MAGNETIC_FIELD, P3-SENSOR-NAME_COUNT, P3-SENSOR-PRESSURE_SENSOR, P3-SENSOR-PROXIMITY_SENSOR, P3-SENSOR-ROTATION_VECTOR, P3-SENSOR-STEP_COUNTER, P3-SENSOR-STEP_DETECTOR, P3-SENSOR-TYPE-COUNT, P3-SENSOR-TYPE-ORDER, P3-SENSOR-VENDOR_COUNT |

全部 1,596 个无序对已登记。4 对仅在共同有效域上、归一化关系 outcome 中完全重复：NW-002/OFFDER-OS-001、NVW-002/OFFDER-OS-002、NVW-005/OFFDER-DEVCONFIG-001、CORE-002/OFFDER-BRIDGE-001。最后一对限制固定 FeatureApp 投影；可用性 envelope 和文本不承诺等价。

NW-005 的硬件族比较与 OFFDER-GPU-001 的桌面后端词检查相关但不等价；P3-GPU-COPY 只是同源拷贝。OFFDER-UA-002 的 trim 归一化与 P3-UA-DEFAULT 的原始等值也不等价。相同证据跨来源只有同一身份，来源数和规则数不增加独立支持票。这里只登记身份和关联，没有实现 S04 去重聚合或 score。

## 5. 条件集合与公共门控

八组合位序固定 O_u/H/E，公共 C 始终 11 条：

| 条件 ID | 附加来源 | 总规则数 | 四来源别名 |
|---|---|---:|---|
| SRC-000 | 无 | 11 | C / B0 |
| SRC-001 | E | 34 | E |
| SRC-010 | H | 25 | — |
| SRC-011 | H、E | 48 | — |
| SRC-100 | O_u | 20 | — |
| SRC-101 | O_u、E | 43 | — |
| SRC-110 | O_u、H | 34 | O |
| SRC-111 | O_u、H、E | 57 | EO |

每组保留相同版本的公共字段、observed/quality、产品 UA、GPU、缺失/未知门控。删除官方派生谓词仍保留官方语义支持的公共门控，所以只称来源分组消融，不称完全移除官方知识。四来源别名引用八个唯一 ID 集，不生成额外独立运行或样本；没有按 payload 去重评估单元。

## 6. 来源未决项与不可实现门控

`source_uncertainties.jsonl` 共 81 条记录：早期经验过程未完整记录 10、文档不可变修订未知 43、旧引用本轮未重新联网核实 11、必要报警前提不可观测 16、Browser 版本范围差异 1。这里是问题记录数，不是规则数或失败文档数；各组来源未决规则数分别 20/9/14/7（共 50，包含可读的一手文档但修订不明），不可实现前提规则数 11/4/1/0（共 16）。

- **E**：来源未决规则 `CORE-002`, `NW-001`, `NW-002`, `NW-005`, `NW-006`, `NW-007`, `NVW-001`, `NVW-002`, `NVW-005`, `WVWEB-004`, `PHYS-005`, `PHYS-006`, `SCENE-001`, `P3-X-CORES`, `P3-X-DPR`, `P3-X-SCREEN-SIZE`, `P3-SCREEN-APP`, `P3-SCREEN-BROWSER`, `P3-UA-DEFAULT`, `P3-UA-SETTINGS`；不可实现的报警前提规则 `NW-001`, `NW-002`, `NW-005`, `NVW-001`, `NVW-002`, `P3-X-DPR`, `P3-X-SCREEN-SIZE`, `P3-SCREEN-APP`, `P3-SCREEN-BROWSER`, `P3-UA-DEFAULT`, `P3-UA-SETTINGS`。
- **O_u**：来源未决规则 `OFFDER-OS-001`, `OFFDER-OS-002`, `OFFDER-UA-001`, `OFFDER-UA-002`, `OFFDER-TOUCH-001`, `OFFDER-BRIDGE-001`, `OFFDER-DEVCONFIG-001`, `OFFDER-GPU-001`, `OFFDER-NET-001`；不可实现的报警前提规则 `OFFDER-OS-001`, `OFFDER-OS-002`, `OFFDER-UA-002`, `OFFDER-GPU-001`。
- **H**：来源未决规则 `P3-COLOR-APP`, `P3-COLOR-BROWSER`, `P3-UA-REDUCED-BROWSER`, `P3-MEM-AVAILABLE`, `P3-SENSOR-ACCELEROMETER`, `P3-SENSOR-MAGNETIC_FIELD`, `P3-SENSOR-GYROSCOPE`, `P3-SENSOR-LIGHT_SENSOR`, `P3-SENSOR-PRESSURE_SENSOR`, `P3-SENSOR-PROXIMITY_SENSOR`, `P3-SENSOR-GRAVITY_SENSOR`, `P3-SENSOR-ROTATION_VECTOR`, `P3-SENSOR-STEP_DETECTOR`, `P3-SENSOR-STEP_COUNTER`；不可实现的报警前提规则 `P3-UA-REDUCED-BROWSER`。
- **C**：来源未决规则 `NVW-004`, `OFFDER-PACKAGE-001`, `P3-PROVIDER-PARSE`, `P3-SENSOR-NAME_COUNT`, `P3-SENSOR-VENDOR_COUNT`, `P3-SENSOR-TYPE-COUNT`, `P3-SENSOR-TYPE-ORDER`；不可实现的报警前提规则 无。

固定 Android 16 AOSP tag 访问失败后，用官方镜像 master 只核对默认 agent 构造；历史精确修订保持 UNKNOWN。所有缺口均有 uncertainty_id、对应规则、原因和影响；未补造文档版本、日志或会话条件，也未为消除缺口启动补采。

## 7. 验证与边界

命令：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest hybridguard_agent.tests.test_formal_manipulation_registry -v`。15 项静态/合成聚焦测试通过，真实输出保存为 `FOCUSED_TESTS.txt`。覆盖 ID 闭合、来源与角色分离、精确八组合、公共门控保留、家族与等价区别、App/Browser UA 边界、Dalvik 可变属性、GPU 软件/host 路径、缺 Browser、false/零/空列表/非有限值、状态质量、元数据隔离及来源 UNKNOWN 保留。

保存后回读四表、来源集合、1,596 对和未决台账，核对静态构建与配置副本一致；135 个已登记的 S01/S02 和相关既有源码/配置文件的 size/mtime 与开工快照一致。既有未提交 Android/TLS/build 等 Git 状态条目保留，HEAD 未变、暂存区为空。该检查是有限只读边界核对，不是密码学完整性认证。详细真实检查见 `FINAL_REVIEW.json` 和 `VALIDATION.json`。

真实材料门控/规则/报警运行 0、真实 predictions 0、外部 LLM 调用 0、性能计算 NOT_EVALUATED、阈值修改 0。没有实施 S04、补造 Browser、晋级时间对照或重裁 S01 标签。合成门控测试只产生 SUPPORTED/NOT_APPLICABLE/UNKNOWN 的适用性结果，没有 relation outcome 或 ManipulationDecision。

## 8. 产物与停止点

配置目录 `hybridguard_agent/config/formal_manipulation_v1/` 保存 source_registry、family_registry、applicability_policy、decision_roles、source_conditions 及 primary_source_review。本目录保存对应副本、source_overlap_matrix、source_uncertainties、SEMANTIC_DECISIONS、SUMMARY、STRUCTURAL_CHECKS、FOCUSED_TESTS、DEPENDENCY_REVIEW、READ_ONLY_BASELINE、FINAL_REVIEW、VALIDATION 和本报告。实现为 `research/manipulation_eval/provenance.py`，测试为 `tests/test_formal_manipulation_registry.py`。

S03 本地状态更新为 DONE/PASS 后停止；S04 等待单独授权。本轮不提交、不推送。S01 的缺件与证据等级、54 条时间对照 no_intervention=UNKNOWN/FPR 未准入、环境组不等同物理设备、当前 App177 无 Browser，以及来源修订与报警门控缺口全部保留。
