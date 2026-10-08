# 第三轮图注与证据边界

初稿已生成／供导师选用。F00、F09为独立素材；F10以T05表格交付。稳定素材名不是最终论文编号。


# F00 方法与分阶段实验流程示意／Method and staged experimental workflow

**中文图注。** 本图说明已实现的观察位置、离线开发／选择与当前记录判断流程，而非244项端到端训练或已部署的自动处置系统。采集App内的Native84、Host26和App Web67组成App177；独立Browser67经保存的会话、回执与来源关联形成paired244视图。数值仅指采集目录规模，不保证全部字段可用、被模型采用或应相等。Native／Host是额外观察位置，不是硬件真值；独立浏览器不是App WebView，也不代表另一台设备。同阶段来源绑定不保证原子同步，来源标识用于关联核对，不是检测特征。

App阶段由受控修改及其正常对照、MTC discovery630正常约束支持候选选择；当前三个冻结App完整模型均保留Native—App Web内存及日期感知时区参照。跨端阶段冻结App模型及编码器，在真实配对开发材料上比较有限增量，三个配置均接受跨端时区C1，均未接受语言C2。后续资源有限接入尝试仅保留S0，因此没有资源增强的已接受方法。正常报警、明确输出与复杂度约束按阶段和正常组分别执行，详细参数与独立模型身份见节点／连线来源映射。MTC144／117只保留历史评价身份，不加入训练，也不是新盲测。

当前判断仅使用当前记录与已选依赖所需观测、质量状态和绑定结果；修改前／修改中／恢复后、标签、目标值及场景属于离线开发或效果核验，不输入判断。App-only和配对方法有不同输入范围／接口，没有自动降级系统主张。配对关系缺值保留U，不能用App的F代替；选中依赖执行或绑定错误使整体FAILED，优先于其他条件的T。无FAILED时保持原逻辑：有T则T，全F才F，否则U。T为报警，F为未报警，U为无法判断；F不证明设备安全或没有干预。虚线表示已测试但未整合的Host几何／资源固定关系，不表示未来自动启用；四视图小树仅为方法比较证据，不替代本图接受规则主线。该示意不是性能图或泛化证明。

**English caption.** Implemented observation locations, staged offline development, and current-record decision interfaces. Native84, Host26, and App Web67 form the App177 catalog; a separately observed Browser67 record forms a paired244 view only after saved provenance binding. These counts describe catalog sizes, not guaranteed availability, model input counts, equality requirements, or numbers of devices. App rules are selected using controlled App modifications, their normal controls, and MTC training normals. The frozen App rules retain Native-to-App-Web memory and timezone references. A subsequent finite paired-development step accepts the cross-endpoint timezone condition C1 in all three saved configurations; no resource increment is accepted. Alarm, defined-output and complexity requirements are imposed by stage and normal cohort. MTC144/117 remain historical evaluation material, not training data or a new blind test.

The current App-only and paired interfaces are distinct; they use only current required observations and their quality/binding states. Development labels and before/during/recovery trajectories do not enter inference. Missing paired operands are not replaced by an App-only no-alert decision. Any selected execution/binding failure takes priority over an alert; otherwise the saved T/F/U logic is preserved. F means no alert, not device safety. Dashed branches denote tested but unintegrated Host geometry and resource diagnostics, not automatic activation. Four-view trees are comparison evidence only. Native/Host observations do not constitute hardware attestation; same-phase association does not establish atomic synchronization. This schematic makes no end-to-end paired244 training, deployment, identity-authentication or generalization claim.

## 紧邻图面的建议短注

- Solid: implemented flow / saved model dependency. Dashed: tested, not integrated.
- Catalog sizes only; not all fields are used or available.
- Provenance binds records; it is not a detection feature.
- Current input only; no pre/post inputs or automatic fallback.
- Selected failure takes priority. F is not a safety claim.

## 可复查来源

- 采集字段规模：`android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv` 按 `layer` 计数：84/26/67；其余4行为metadata，不纳入177。Browser probe manifest的 `signal_count=67`。版本号从实际各批次来源核对，不将旧配置v8/v1写为现行统一版本。
- App候选依赖：`deliverables/app177_core_ablation_v1/CANDIDATE_DEPENDENCIES.md` 第3–7、61–67行；冻结App身份：`deliverables/timezone_relation_validation_v1/models.json#/models/{1,3,5}`，stage均为RETENTION。
- 有限配对开发：`deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md` 第3–15行；接受身份：`results/models.json#/{0,1,2}` 的 `extensions=["C1"]`。
- 资源未接入：`deliverables/app_resource_constrained_extension_v1/results/models.json#/{0,1,2}` 的 `selected_set=S0`、`status=BASELINE_RETAINED`、`extensions=[]`。
- 当前输入与失败优先级：`hybridguard_agent/research/rule_learning/predictor.py` 第24–64行；`deliverables/cross_endpoint_constrained_extension_v1/inference.py` 第10–36行；`selector.py` 第14–20行。
- 未整合Host专项：`deliverables/screen_geometry_observation_v1/SEMANTICS.md` 第3、23–35、45–47行。
- 完整逐节点状态、来源定位与连线含义见F00证据映射。


## F09 宿主实际显示区域：固定条件专项

**初稿已生成／供导师选用；固定条件专项，未纳入当前App完整模型。** 对照对象为旧高度阈值 `R_HEIGHT710`、旧同网页关系 `R_SAME_WEB` 和新宿主几何上界 `R_HOST_GEOMETRY`，不是三个重训模型或三个整模消融。

**中文图注。** 宿主几何参照在v15正式72个位置中减少正常布局变化造成的报警，同时保留局部屏幕修改检出。A展示6个有独立正常依据的布局扩大中间位置及6个确认实际生效的屏幕修改位置：旧高度阈值和Host上界均检出6/6修改，正常布局扩大时分别报警6/6和0/6；旧同网页关系两组均为0/6。B保留全部66个有依据正常位置和6个有效修改位置的T/F/U/FAILED计数。正常布局6是正常66的子集，不能相加。三个条件在72条上均无U或FAILED。72条来自3个模拟器环境的重复观察，不代表72台设备或真机人群误报率；旋转实际生效4/6，另2个无可观测效果的正常尝试完整保留在分场景CSV。

**English caption.** Host geometry reduces alarms caused by normal layout enlargement while retaining local screen-modification detections in the 72-position formal v15 matrix. Panel A compares three fixed conditions on six independently supported normal layout-enlargement positions and six observably effective screen modifications. Both the legacy height threshold and the Host upper bound detect all six modifications; they raise six and zero alarms, respectively, on the normal layout subset. The legacy same-Web relation raises no alarms in either group. Panel B reports complete T/F/U/FAILED counts for all 66 normal and six modified positions. The six layout positions are included in the 66 normal positions. All three conditions have explicit outputs on all 72 positions, with no U or FAILED. These are repeated observations in three emulator environments, not a device-population estimate. Rotation has an observed effect in four of six attempts; the two normal attempts without an observable effect are retained in the accompanying scene-level data. This fixed-condition study has not been integrated into the accepted App full model.

Host提供当前App中WebView实际占用的内容区域，而非整块物理屏幕。正常扩大容器后，网页高度可以合法增加，因此固定710阈值产生正常报警。Host关系按[SEMANTICS](../../../deliverables/screen_geometry_observation_v1/SEMANTICS.md)逐轴比较：网页视觉尺寸 × 同期DPR × 当前 `visualViewport.scale`，是否大于实测WebView内容区域加既定容差；容差为 `2 + 4 × 2^-23 × max(|P|, |H|, 1)` 物理像素。本轮只计数保存输出，不重新计算该关系。不补缺失scale、不按宽度比反推、不混用旧Web快照与新Host窗口。

本图支持“在本批正常布局变化中减少6次报警，同时保留6次局部检出”。它不支持“比旧高度新增6次检出”，不支持把当前完整App模型屏幕结果由6/9改写成9/9，也不能替代第一轮完整App模型的正常屏幕报警结果。固定容差不是所有WebView的规范保证；尚无广泛真机、非零WebView padding、折叠屏、分屏等正常覆盖。上界以内或多值协调修改可能不触发，Host不是真值认证层。

**来源及筛选。** 主数值来自[SUMMARY.json](../../../deliverables/screen_geometry_observation_v1/SUMMARY.json)的 `normal_change_by_process/L2`、`confirmed_normal`、`observable_intervention`；分场景来自 `by_process_phase`、`normal_observable_change_by_process` 等原分组。只读[保存逐条输出](../../../deliverables/screen_geometry_observation_v1/predictions.jsonl.gz)的场景、阶段、`normal_basis.supported`、`observable_intervention`、`workflow_evidence.verified`及既存条件状态，交叉核对SUMMARY的24组效果／恢复依据。`change`本身不定义攻击，条件输出不参与正常身份判定。导出仅使用中性案例名及原文件物理行定位，不复制原成员、会话、设备或回执ID。定义见[冻结条件](../../../deliverables/screen_geometry_observation_v1/CONDITIONS_FROZEN.json)、[专项说明](../../../deliverables/screen_geometry_observation_v1/REPORT.md)及[结果说明](../../../deliverables/screen_geometry_observation_v1/RESULTS.md)。[V15_CONSISTENCY.json](../../../deliverables/screen_geometry_closeout_v1/V15_CONSISTENCY.json)与[工程收尾说明](../../../deliverables/screen_geometry_closeout_v1/REPORT.md)仅核对版本范围；v16的12个工程位置、早期冒烟、旧App378、MTC和资源54均未进入本图。

**配套表。** `F09.csv`保存3组×3条件的完整计数；`F09_scenarios.csv`保留12个互斥场景／阶段组；`F09_normal_changes.csv`保留正常尝试、实际生效及无效果子集；`F09_environments.csv`为环境分组；`F09_effects.csv`保留24组独立执行／效果／恢复依据；`F09_records.csv`为72行脱敏来源定位；`F09_conditions.csv`说明固定条件身份。不同层级的汇总不能相加。


## T05｜分阶段成本与既有时间记录（F10以表交付）

**中文结论。**旧计时的`R_FULL`是冻结App+C1跨端时区，三配置与P0四视图构成事先确定的主表；不按耗时挑行。所有21模型、148阶段组及1,480个记录批次完整保留。缓存已适配输入与已加载raw到输出的起点不同，不能把各阶段中位数或不同路径P95相加，也不能据此得出规则/树算法倍速。模型资源数值包含原保存包的预处理或来源元数据，不是裁剪部署包。先导18与匹配42的同host编排区间单独汇总，保留4条15秒偏好等待；60条纯探针耗时均未记录。三个历史App RETENTION内部fit区间可引用，但不代表完整训练；B2-C纯选择、B3-A树纯fit及旧B3-B有限选择独立耗时未记录。后续资源组合与新App消融没有重新计时，不套用旧值。

**English caption.** T05. Saved computational costs, model resources, and historical timing records. The prespecified main table covers three frozen App+C1 configurations and four P0 feature views. Loading is measured per model; other computational stages are amortized over the same 60-position batch. Medians and P95 values are displayed in milliseconds, with original microsecond values retained in CSV. P95 summarizes ten batch-amortized observations, not individual-request tail latency. Public interfaces, prepared-input inference, cached adapted-input paths, and loaded-raw wrappers have different and partly overlapping boundaries; their medians or percentiles must not be added or interpreted as an algorithm-speed ranking. All 21 models, 148 stage groups, and 1,480 recorded batches are retained. Resource sizes describe saved bundles and required base-model files, including preprocessing or provenance metadata, rather than a minimal deployment package. Historical same-host collection intervals include experimental orchestration and persistence waits; pure-probe duration remains unrecorded. No timing, training, selection, or prediction was rerun for this table.

**来源。**[cost.csv](../../../deliverables/prepaper_evidence_closeout_v1/tables/cost.csv)、[model_resources.csv](../../../deliverables/prepaper_evidence_closeout_v1/tables/model_resources.csv)、[TIMING_FREEZE](../../../deliverables/prepaper_evidence_closeout_v1/timing/TIMING_FREEZE.json)、[保存批次](../../../deliverables/prepaper_evidence_closeout_v1/timing/batches.jsonl)、[采集区间](../../../deliverables/prepaper_evidence_closeout_v1/existing_times/collection_log_intervals.csv)、[历史训练计时](../../../deliverables/prepaper_evidence_closeout_v1/existing_times/historical_training_timing.json)。阶段边界仅静态读取[原计时包装](../../../deliverables/prepaper_evidence_closeout_v1/cost_runtime.py)和[原测量程序](../../../deliverables/prepaper_evidence_closeout_v1/measure_cost.py)核对，未导入或运行。

**版式与停止点。**本轮交付表格T05，不制作F10耗时排行榜；清单应写“成本表T05已生成，图形化未制作／暂不需要”。
