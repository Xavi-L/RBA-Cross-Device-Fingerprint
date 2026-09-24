# S02 三态 App177 与时间对照兼容适配

工程验收：**PASS**。本步仅转换与结构校验；真实样本没有执行检测规则、报警策略或性能评价。

## 依赖与范围

本地 S01 报告、验证记录、13 项最终聚焦测试与材料/事实/阶段/三态/环境台账一致；未发现实质冲突。S01 未重跑、未重裁标签。依赖状态中遗留的未执行提示已按本地验收事实清除。
执行前 S01 已提交并推送；提交及远端确认记录在 EXECUTION_STATUS.json。S02 结果保持本地，停止于本步。

## 全量阶段去向

| 项目 | 数量 |
|---|---:|
| S01 原始阶段 | 262 |
| 转换成功 | 262 |
| 明确拒绝 | 0 |
| 唯一评估单元 | 262 |

`input_manifest.jsonl` 对每条 S01 raw 阶段给出唯一去向，并连接成功输入或拒绝记录以及评估侧表。缺少可用标签不是适配拒绝理由。

| Cohort（阶段） | 输入 | 成功 | 拒绝 |
|---|---:|---:|---:|
| lower_evidence_attack | 45 | 45 | 0 |
| temporal_control_unknown | 54 | 54 | 0 |
| admitted_attack_triplet | 162 | 162 | 0 |
| incomplete_attempt | 1 | 1 | 0 |

拒绝理由计数：`{}`。空对象表示没有适配拒绝，不表示证据均已准入。

## 阶段关联与包级历史

保留 88 组实际阶段关联：69 组完整攻击三态、18 组完整时间对照三时点、1 组原有不完整尝试。阶段计数：`{"clean_pre": 88, "attack": 69, "clean_post": 87, "control_mid": 18}`。
`phase_associations.json` 保留所有已有阶段及 sequence_index/round；完整组的 clean_post 均保留。不完整 CDP 尝试仍只有 clean_pre，缺少 attack/clean_post；Playwright 空失败包仍为 0 阶段。未制造阶段以补齐三态。31 包历史通过 `bundle_history.json` 引用 S01 inventory，失败和缺件状态不被转换结果覆盖。
相同推理 payload 的重复内容组 0 个，共涉及 0 个独立单元；均未去重。

## 字段、遮蔽与隔离

复用 paired244 的 App177 logical/flat 映射、当前 CSV 字段类型和 normalize_payload。三个状态相关映射均为完整且精确的 177 键；检查别名冲突、六态状态、类型及非有限值。旧 bootstrap JSON 有 54 个数字类型描述与当前 CSV 的 number 不同，沿用当前运行时 CSV，不将历史 integer 观测收窄为新约束。
合法 false、0、空列表原样保留；未观测状态不因有值升级为 observed。observed 的 device_memory/hardware_concurrency 零哨兵保留零及状态，质量标记 ambiguous_sentinel。无状态或观测值缺失不填造。
推理文件仅以随机 opaque_id 作外部关联键；其 payload 仅含固定 record_schema_version、adapter_version、features、field_status、field_quality。所有值来自当前阶段的注册字段，不含 Browser。标签、phase、工具/config、路径、session/install/group、执行回执、预期修改和未来 post 都在独立 evaluation_index 或其 S01/源引用中。字段本身合法的 UA 字符串不按工具关键词清洗。
合成聚焦测试：**15 项通过**，详见 FOCUSED_TESTS.txt。覆盖 flat/nested 等价、完整键集合、别名冲突、类型/非有限值、六态/零哨兵/空列表、元数据置换、未来 post 独立性、隐藏层值/状态/质量/派生摘要移除、同内容不同单元和明确拒绝。真实材料仅进行转换、源绑定与结构校验。
全部结构检查：`{"S01_saved_records_consistent": true, "all_262_raw_stages_accounted": true, "unique_candidate_coverage": true, "unique_raw_stage_coverage": true, "success_rejection_partition": true, "manifest_references_exact": true, "all_rejections_have_structural_reasons": true, "S01_facts_eligibility_groups_unchanged": true, "temporal_unknown_not_promoted": true, "all_original_phase_associations_preserved": true, "bundle_history_preserved_without_fabrication": true, "inference_payload_allowlist_and_177_fields": true, "focused_synthetic_tests_passed": true, "sources_and_S01_unchanged": true, "no_detector_or_admission_runtime_imported": true, "no_prediction_artifacts": true}`。

## 仍保留的事实限制

54 条时间对照阶段的 no_intervention 仍为 UNKNOWN，eligible_temporal_control 全为 false，不获得 FPR 资格。45 条较低证据攻击阶段仍缺直接日志等证据；转换成功不将其升级。原有 54 个攻击阶段/三态准入与前后各 54 条声明表面对照资格原样保留，不扩大到普遍正常标签。3 个环境关联组不是已核验独立物理设备数。
未启动补采或补日志；不修改阈值，不生成真实 predictions，不计算 TPR/FPR；S03–S12 未执行。P0–P6、S01 和攻击仓库原始材料只读。
