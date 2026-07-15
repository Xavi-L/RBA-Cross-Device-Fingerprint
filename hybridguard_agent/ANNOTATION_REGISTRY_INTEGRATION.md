# Week 7 标签登记表接入结论

接入来源：`hybridguard-browser-fingerprint-research/execution_log/evidence/experiment_session_annotation_registry_v1.csv`。

## 机器审计结果

- 登记表 51 行，Week 7 manifest 数据 51 行；
- `sample_id` 匹配 51/51；
- `source_session_id` 匹配 51/51；
- 两个 join key 指向同一登记行 51/51；
- 重复 ID、漏标行和缺失 evidence reference 均为 0；
- 同学仓库自带的 registry verifier 为 13/13 passed。

因此它满足我们需要的“标签只做 sidecar、能回到原始会话、有实验和证据来源、区分成功/失败/回滚”的要求。管线不会把工具名、pair role、split 或标签列写入 `normalized_expanded_v2.jsonl` 和 Blind RAG EvidenceBundle。

## 任务分流

不能把 18 条完整 pair session 全部当作同一种指纹攻击数据：

| 任务 | session | active 正例 | 用途 |
|---|---:|---:|---|
| `fingerprint_field_effect_pilot` | 9 | 3 | CDP 确认改变 177 字段中的目标 Web 字段；可用于训练流程冒烟 |
| `transport_path_effect_pilot` | 9 | 3 | mitmproxy 只确认传输路径变化，明确不宣称 177 字段变化；单独评估 |
| `baseline_qc` | 24 | 0 | 21 条兼容基线 + 3 条 manual smoke，不自动进入攻击配对训练 |
| `incomplete_attempt_failure_analysis` | 9 | 不作为正例 | 7 条失败网络尝试 + 2 条 stealth partial，仅用于失败分析 |

当前 6 个完整 triplet 全在登记表的 `train` split，development/test 没有完整攻击 pair。因此现在可以跑通 pilot 训练数据构建，但不能报告 held-out 攻击检测准确率或跨设备泛化结论。

另外，3 条 CDP active 正例的原始 UA/platform 字段直接出现了规范化后的 `Chrome DevTools Protocol` 字样。这不是标签登记表泄漏，而是攻击产物本身暴露工具模板；小模型很可能学会字符串捷径。因此这 9 条只能用于流程冒烟，后续还需要不同工具/配置、独立设备组和不含显式工具名的攻击正例。

## 管线产物

每次运行 `hybridguard_agent/scripts/run_pipeline.py` 会额外生成：

- `annotation_registry_audit.json`：双键覆盖、证据文件和 join 状态；
- `supervised_task_candidates.csv`：按任务分开的 label sidecar；
- `pair_audit.csv`：完整 triplet、stable key、split 和 incomplete-excluded 状态；
- `attack_shortcut_audit.csv`：干预名是否直接出现在原始观测字段中；
- `dataset_build_manifest.json`：pilot 数量和 held-out gate。

历史云真机 154 条 expanded-v2 仍只补 `field-status-v1-historical-inferred` sidecar：可以确认原始 177 字段存在，但不能补造当时未记录的 `collection_manifest` 或攻击标签。
