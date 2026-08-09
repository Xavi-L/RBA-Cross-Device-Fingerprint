# HybridGuard 研究数据管线

这个目录把现有的采集、规则、官方知识和后续 Agent/RAG 研究组织成可冻结、可重跑的离线管线。当前默认入口只处理最新版 FeatureApp 的 App177 与独立 Browser67；下面保留的旧云数据、历史攻击 pilot 和确定性运行时属于逻辑归档，不进入最新 paired244 主视图。

它不替代现有目录：

- `backend_server/raw_expanded_payloads.jsonl` 与 receipt 是 App canonical 权威输入；`expanded_collected_data.jsonl` 只是配套的 analysis/projection 视图；
- `scoring/rule_knowledge_base.json` 和 `google_official_kb/` 仍是规则与官方知识的权威来源；
- `hybridguard-browser-fingerprint-research/` 仍是攻击侧同学维护的执行日志和证据仓库；
- 本目录只生成契约、样本 manifest、QC、稳定分组、冻结快照和后续推理所需的中间产物。

历史云真机的 `field-status` 补标规则见 [HISTORICAL_FIELD_STATUS.md](HISTORICAL_FIELD_STATUS.md)。旧 snapshot 管线使用独立的 `field_status.jsonl` sidecar；当前 paired244 入口直接保留 App177/Browser67 已上报的逐字段状态，并与特征值分栏存放。两条管线都不会改写原始 JSONL，也不会给 Browser 失败样本补造67项。

## 当前活跃入口：最新版 paired244 快照

第一批施工只负责数据选择、配对和 QC，不接入 Agent、Evidence、模型或评分。当前发布锁为：

- FeatureApp `1.6.1-expanded-v2.2-browser-recovery` / versionCode 8；
- App `expanded-v2.2-status`，固定177项；
- Browser `browser-web-v1-status`，固定67项；
- Browser Probe `expanded-web-67-v1`。

运行：

```bash
python3 hybridguard_agent/scripts/build_latest_paired244_snapshot.py \
  --run-id latest_paired244_YYYYMMDD
```

该入口以 canonical raw、receipt、已关闭 batch 和 completed pair provenance 为准；analysis/projection 存在时做一致性核对，但不会因为 analysis 行暂缺而漏掉可由 raw 完整证明的 App session。它生成：

- `paired_244.jsonl`：完整 App177 + Browser67 主视图，只含派生特征、逐字段状态和最小视图元数据；
- `app_only_177.jsonl`：App 有效但 Browser 尚未完成的留存视图，同样不混入 receipt/pair/batch 标识；
- `quarantine.jsonl`：App 或 pair 合同失败的隔离记录；
- `sample_index.jsonl`：不含特征值的控制面索引，集中保存 session、receipt、pair、batch、版本与留存原因；
- `selection_audit.jsonl`：每条 App 输入的接收、留存、旧版本排除或隔离原因；
- `feature_catalog.json`、`qc_summary.json`、`dataset_manifest.json`：字段顺序、QC 和冻结信息。

Browser 缺失值绝不填零。当前数据实跑结果为 26 条锁定 release 的 App177，其中17条进入 paired244，9条进入 App-only 留存，0条最新 App 被隔离；同文件内其他 FeatureApp release 和旧 Schema 仅计入 `excluded_legacy`。这些数据全部是 `development_qc_only`、`unlabeled`，不能据此报告攻击检测效果。

## 历史研究资产（逻辑归档）

以下内容记录旧快照和研究 pilot，保留用于复核，不再作为默认数据入口。截至 2026-07-14 的旧快照曾记录155条 expanded 数据；其历史采集没有逐条 provider run ID、配对关系或攻击事实标签，因此不进入最新版 paired244 主视图、有监督攻击检测训练或最终效果评估。

攻击侧仓库的 2026-07-11 release view 记录 393 条严格工具映射的实测会话：178 条 attack-capable/abnormal 且三端完整、184 条 attack-capable/abnormal 但缺层、31 条完整的合法隔离对照。release view 已脱敏且不含 177 字段 payload 或可关联 session ID，因此只作为攻击覆盖证据。

攻击侧 2026-07-15 已提供 51 行 verified label-only registry。管线同时按 `sample_id` 与 `source_session_id` 完成 51/51 双键校验，并把它与原始 177 字段严格分开。当前可形成 9 条 CDP 指纹字段影响 pilot 和 9 条 mitmproxy 传输路径 pilot；后者明确不宣称指纹字段变化，不能混入同一个正例类别。所有完整 pair 仍只在 `train` split，且 3 条 CDP active 的原始字段直接含有 intervention 名称，存在模板捷径。因此可以跑通 pilot 流程，但正式 held-out 攻击评估仍未解锁。详细映射见 [ANNOTATION_REGISTRY_INTEGRATION.md](ANNOTATION_REGISTRY_INTEGRATION.md)。

## 目录与职责

```text
hybridguard_agent/
├── config/latest_paired244_sources.json # 当前 FeatureApp/Browser 发布锁与输入
├── config/dataset_sources.json        # 输入来源、事实边界与模型资格
├── config/deterministic_rule_predicates.v1.json # 已审阅的可执行规则及 KB hash
├── ANNOTATION_REGISTRY_INTEGRATION.md # Week 7 标签接入、任务分流与结论边界
├── schemas/                           # 冻结的 expanded-v2、Evidence/Trace 契约
├── evidence/extractor.py              # 脱敏的 EvidenceBundle v2
├── rules/executor.py                  # 确定性 predicate（不产生风险分）
├── retrieval/exact_retriever.py       # 精确规则/字段知识卡检索
├── verification/verifier.py           # 引用、字段与无校准分边界核验
├── runtime/                           # 组合运行时和冻结快照加载器
├── templates/attack_manifest.template.json
├── scripts/build_latest_paired244_snapshot.py # 当前177+67配对、留存与QC入口
├── scripts/build_dataset_snapshot.py  # Schema/QC/manifest/stable-group 冻结
├── scripts/build_evidence_bundles.py  # 无标签的确定性跨层证据
├── scripts/build_evidence_bundles_v2.py # 状态感知的脱敏 v2 证据
├── scripts/build_knowledge_manifest.py# 规则/官方知识版本边界
├── scripts/run_pipeline.py            # P0 快照与 v2 运行时输入的一键重跑入口
├── scripts/run_agent_runtime.py       # 离线只读分析入口
└── artifacts/<run_id>/                # 每次运行独立输出；默认不提交
```

历史 `build_dataset_snapshot.py` 管线生成以下内容（不属于 paired244 第一批）：

```text
raw JSONL + source config
  -> Schema 校验 / expanded-v1 隔离
  -> canonical field profile / stable-device grouping
  -> SampleManifest（元数据与特征分离）
  -> 标签登记表双键 join / task sidecar / pair audit
  -> field_status（与特征分离的可用性 sidecar）
  -> v1 EvidenceBundle（兼容旧 P0 消费者）+ v2 EvidenceBundle（运行时）
  -> controlled_scenario_input_v1（无标签、无工具名的配对安全投影）
  -> controlled_scenario_sidecar_v1（离线 clean/active/post 对照）
  -> 冻结知识输入版本
  -> QC、来源-标签交叉表、build manifest、状态报告
```

## 历史第一版确定性运行时

该运行时目前只消费历史 `normalized_expanded_v2.jsonl`，尚未接入 `paired_244.jsonl` 或 `app_only_177.jsonl`；第一批不会修改 Evidence、runtime 或 DecisionTrace。

运行时把一条三层 payload 处理成下面的闭环：

```text
payload + field_status
  -> EvidenceBundle v2（只保留派生事实和字段路径）
  -> 已审阅的确定性规则
  -> 当前规则/官方知识卡的精确检索
  -> Verification + DecisionTrace
  -> 未校准的结构化结论
```

第一版只真正评估两组证据：`cross_layer` 和 `runtime_context`。`browser_pair`、`attack_scenario`、经验案例检索和校准融合都会显式返回 `not_assessed`，而不是假装有结论。输出中的 `calibrated_risk_score` 固定为 `null`；“不匹配”只表示需要复核的观察，不等于攻击、欺诈或跨设备泛化能力。

`attack_scenario v1` 是一条**独立的离线实验支路**，并不改变上面的单样本运行时：它只读取 `controlled_scenario_input_v1.jsonl`、归一化 payload、field-status 与冻结比较策略，把同一受控实验的 `clean_pre -> attack_active -> clean_post` 三次采集进行对照。当前 v1 只检查 5 个已验证的 CDP 目标字段是否“中间改变、结束后恢复”；标签、工具名、攻击类型和登记表不进入该 builder。它的结果是“受控字段变化是否被观察到”，不是恶意判定、在线攻击告警或风险分数。

规则库原本是自然语言知识库。只有写入 `deterministic_rule_predicates.v1.json`、并且与冻结规则库 SHA-256 完全一致的少量规则才会执行；其余规则被记录为 `unevaluated_rule_ids`。命中 short-circuit 规则后，后续 predicate 会明确标为 `not_evaluated`，不会悄悄继续计算或给出低风险结论。

## 历史管线运行方式（非默认）

首次冻结现有云真机数据：

```bash
python3 hybridguard_agent/scripts/build_dataset_snapshot.py \
  --bootstrap-contract \
  --run-id cloud_baseline_20260714
```

后续云真机或攻击数据补充后，更新 `config/dataset_sources.json` 中的输入路径/manifest，再运行：

```bash
python3 hybridguard_agent/scripts/run_pipeline.py \
  --run-id snapshot_YYYYMMDD
```

不要覆盖旧 `artifacts/<run_id>/`。实验只引用某个明确的 run ID 与其 `dataset_build_manifest.json`。

用冻结快照分析一个样本（结果写到新的输出文件，不回写快照）：

```bash
python3 hybridguard_agent/scripts/run_agent_runtime.py \
  --snapshot-dir hybridguard_agent/artifacts/snapshot_YYYYMMDD \
  --sample-id YOUR_SAMPLE_ID \
  --output /private/tmp/hybridguard_runtime_result.jsonl
```

如果需要 HTTP 服务，可从 `backend_server/` 启动独立的只读应用：

```bash
uvicorn agent_runtime_app:app --host 127.0.0.1 --port 8001
```

它只提供 `GET /api/agent/readiness` 和 `POST /api/agent/analyze`。默认 `trace_detail: "summary"` 不返回完整证据包或知识卡；`"full"` 用于本地审计。不要用 `main:app` 来替代这个独立应用：主采集服务的既有启动生命周期会维护 collection batch，而独立运行时不会。

构建或复核某个冻结快照的受控场景 sidecar：

```bash
python3 hybridguard_agent/scripts/build_attack_scenario_sidecar.py \
  --snapshot-dir hybridguard_agent/artifacts/snapshot_YYYYMMDD
```

生成的 `controlled_scenario_sidecar_v1.json` 只保存 sample ID、配对键哈希、字段状态和字段值哈希。当前完整 pair 全在 train split，所以它只能作为受控回放和回归验证，不能产出准确率、阈值或跨设备泛化结论。

## 历史管线接入真实攻击数据（非 paired244 第一批）

每个攻击样本必须同时具备：

1. expanded-v2.1-status、expanded-v2.2-status 或兼容的原始177字段 JSONL；
2. 与 `session_id` 一一对应的 `collection_manifest` / SampleManifest；
3. 同稳定画像的 `clean_pre -> attack -> clean_post` 配对信息；
4. 可与样本关联的 verified label/attack registry，其中记录工具成功、可观察字段影响和回滚状态。

以 `templates/attack_manifest.template.json` 为模板。把新来源添加到 `config/dataset_sources.json` 后，snapshot 会自动：

- 合并 manifest 事实，但不把 `tool_name`、`pair_role`、`label`、provider 等字段写进模型特征；
- 同时校验登记表 `sample_id` 和原始 `source_session_id`，任何错配都会使 snapshot 构建失败；
- 将指纹字段影响和仅传输路径影响分成独立任务；
- 仅将 complete、verified 且字段效果为 observed 的 CDP triplet 列为指纹任务 pilot 候选；
- 检查配对稳定键一致性；
- 输出 held-out gate；当前 complete pair 全在 train，不把 pilot 误写成正式评估。

## 使用边界

- 云真机、模拟器、ADB 或远程采集方式是来源/运行环境，不自动等于攻击或正常。
- 一条 session 不等于一台独立设备；所有报告同时查看 session 数和 stable-device group 数。
- 历史攻击 release view 的393条不能和历史155条主仓快照按行拼接：两边没有共享的可审计 `session_id`，且 release view 不含完整字段；二者都不进入当前 latest-only paired244 入口。
- 数据冻结后，再按 stable group/pair 切分训练、开发和测试；不得用测试集生成经验规则、案例索引、阈值或 Prompt。
- 运行时不会接收或返回 label、attack tool、provider、pair role、原始 UA、完整 build fingerprint、原始 session ID 或客户端 IP；知识卡也不会成为校准模型。

详细研究契约见 `hybridguard_agent_rag_guide/02_TARGET_ARCHITECTURE_AND_CONTRACTS.md`、`03_DATA_SCHEMA_GROUPING_AND_QC.md` 与 `04_ATTACK_COLLECTION_AND_PROVENANCE.md`。
