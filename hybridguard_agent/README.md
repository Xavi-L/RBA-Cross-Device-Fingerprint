# HybridGuard 研究数据管线

这个目录把现有的采集、规则、官方知识和后续 Agent/RAG 研究组织成一条**可冻结、可重跑、不会把来源元数据泄漏进模型**的离线管线，并提供一条可选的、只读的确定性运行时。

它不替代现有目录：

- `backend_server/expanded_collected_data.jsonl` 仍是 expanded-v2 的原始采集输入；
- `scoring/rule_knowledge_base.json` 和 `google_official_kb/` 仍是规则与官方知识的权威来源；
- `hybridguard-browser-fingerprint-research/` 仍是攻击侧同学维护的执行日志和证据仓库；
- 本目录只生成契约、样本 manifest、QC、稳定分组、冻结快照和后续推理所需的中间产物。

历史云真机的 `field-status` 补标规则见 [HISTORICAL_FIELD_STATUS.md](HISTORICAL_FIELD_STATUS.md)。每个新快照都会同时生成统一的 `field_status.jsonl` sidecar：采集端已上报状态的样本保留该状态，历史样本才使用明确标注为 inferred 的补标。它不会改写原始 JSONL，也不会伪造缺失的 `collection_manifest`。

## 当前可复核快照

截至 2026-07-14，主仓库的 `expanded_collected_data.jsonl` 有 155 条记录：154 条 expanded-v2、1 条 expanded-v1。云真机记录具有可用的 177 字段原始 payload，但历史采集没有逐条 provider run ID、配对关系或攻击事实标签，因此当前仅用于 Schema/QC/稳定画像/检索联调，**不进入有监督攻击检测训练或最终效果评估**。

攻击侧仓库的 2026-07-11 release view 记录 393 条严格工具映射的实测会话：178 条 attack-capable/abnormal 且三端完整、184 条 attack-capable/abnormal 但缺层、31 条完整的合法隔离对照。release view 已脱敏且不含 177 字段 payload 或可关联 session ID，因此只作为攻击覆盖证据。

攻击侧 2026-07-15 已提供 51 行 verified label-only registry。管线同时按 `sample_id` 与 `source_session_id` 完成 51/51 双键校验，并把它与原始 177 字段严格分开。当前可形成 9 条 CDP 指纹字段影响 pilot 和 9 条 mitmproxy 传输路径 pilot；后者明确不宣称指纹字段变化，不能混入同一个正例类别。所有完整 pair 仍只在 `train` split，且 3 条 CDP active 的原始字段直接含有 intervention 名称，存在模板捷径。因此可以跑通 pilot 流程，但正式 held-out 攻击评估仍未解锁。详细映射见 [ANNOTATION_REGISTRY_INTEGRATION.md](ANNOTATION_REGISTRY_INTEGRATION.md)。

## 目录与职责

```text
hybridguard_agent/
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
├── scripts/build_dataset_snapshot.py  # Schema/QC/manifest/stable-group 冻结
├── scripts/build_evidence_bundles.py  # 无标签的确定性跨层证据
├── scripts/build_evidence_bundles_v2.py # 状态感知的脱敏 v2 证据
├── scripts/build_knowledge_manifest.py# 规则/官方知识版本边界
├── scripts/run_pipeline.py            # P0 快照与 v2 运行时输入的一键重跑入口
├── scripts/run_agent_runtime.py       # 离线只读分析入口
└── artifacts/<run_id>/                # 每次运行独立输出；默认不提交
```

一次 snapshot 生成：

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

## 第一版确定性运行时（当前可用）

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

## 首次与日常运行

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

## 接入真实攻击数据

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
- 当前攻击 release view 的 393 条不能和主仓库 155 条按行拼接：两边没有共享的可审计 `session_id`，且 release view 不含完整字段。
- 数据冻结后，再按 stable group/pair 切分训练、开发和测试；不得用测试集生成经验规则、案例索引、阈值或 Prompt。
- 运行时不会接收或返回 label、attack tool、provider、pair role、原始 UA、完整 build fingerprint、原始 session ID 或客户端 IP；知识卡也不会成为校准模型。

详细研究契约见 `hybridguard_agent_rag_guide/02_TARGET_ARCHITECTURE_AND_CONTRACTS.md`、`03_DATA_SCHEMA_GROUPING_AND_QC.md` 与 `04_ATTACK_COLLECTION_AND_PROVENANCE.md`。
