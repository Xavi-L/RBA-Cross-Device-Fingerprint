# HybridGuard 研究数据管线

这个目录把现有的采集、规则、官方知识和后续 Agent/RAG 研究组织成一条**可冻结、可重跑、不会把来源元数据泄漏进模型**的离线管线。

它不替代现有目录：

- `backend_server/expanded_collected_data.jsonl` 仍是 expanded-v2 的原始采集输入；
- `scoring/rule_knowledge_base.json` 和 `google_official_kb/` 仍是规则与官方知识的权威来源；
- `hybridguard-browser-fingerprint-research/` 仍是攻击侧同学维护的执行日志和证据仓库；
- 本目录只生成契约、样本 manifest、QC、稳定分组、冻结快照和后续推理所需的中间产物。

历史云真机的 `field-status` 补标规则见 [HISTORICAL_FIELD_STATUS.md](HISTORICAL_FIELD_STATUS.md)。它只生成不可混淆的 sidecar，不会改写原始 JSONL，也不会伪造缺失的 `collection_manifest`。

## 当前可复核快照

截至 2026-07-14，主仓库的 `expanded_collected_data.jsonl` 有 155 条记录：154 条 expanded-v2、1 条 expanded-v1。云真机记录具有可用的 177 字段原始 payload，但历史采集没有逐条 provider run ID、配对关系或攻击事实标签，因此当前仅用于 Schema/QC/稳定画像/检索联调，**不进入有监督攻击检测训练或最终效果评估**。

攻击侧仓库的 2026-07-11 release view 记录 393 条严格工具映射的实测会话：178 条 attack-capable/abnormal 且三端完整、184 条 attack-capable/abnormal 但缺层、31 条完整的合法隔离对照。release view 已脱敏且不含 177 字段 payload 或可关联 session ID，因此只作为攻击覆盖证据。

攻击侧 2026-07-15 已提供 51 行 verified label-only registry。管线同时按 `sample_id` 与 `source_session_id` 完成 51/51 双键校验，并把它与原始 177 字段严格分开。当前可形成 9 条 CDP 指纹字段影响 pilot 和 9 条 mitmproxy 传输路径 pilot；后者明确不宣称指纹字段变化，不能混入同一个正例类别。所有完整 pair 仍只在 `train` split，且 3 条 CDP active 的原始字段直接含有 intervention 名称，存在模板捷径。因此可以跑通 pilot 流程，但正式 held-out 攻击评估仍未解锁。详细映射见 [ANNOTATION_REGISTRY_INTEGRATION.md](ANNOTATION_REGISTRY_INTEGRATION.md)。

## 目录与职责

```text
hybridguard_agent/
├── config/dataset_sources.json        # 输入来源、事实边界与模型资格
├── ANNOTATION_REGISTRY_INTEGRATION.md # Week 7 标签接入、任务分流与结论边界
├── schemas/                           # 冻结的 expanded-v2 和 SampleManifest 契约
├── templates/attack_manifest.template.json
├── scripts/build_dataset_snapshot.py  # Schema/QC/manifest/stable-group 冻结
├── scripts/build_evidence_bundles.py  # 无标签的确定性跨层证据
├── scripts/build_knowledge_manifest.py# 规则/官方知识版本边界
├── scripts/run_pipeline.py            # 后续批次的一键 P0 重跑入口
└── artifacts/<run_id>/                # 每次运行独立输出；默认不提交
```

一次 snapshot 生成：

```text
raw JSONL + source config
  -> Schema 校验 / expanded-v1 隔离
  -> canonical field profile / stable-device grouping
  -> SampleManifest（元数据与特征分离）
  -> 标签登记表双键 join / task sidecar / pair audit
  -> 无标签 EvidenceBundle
  -> 冻结知识输入版本
  -> QC、来源-标签交叉表、build manifest、状态报告
```

当前已实现的是这条链路的 P0 数据层和确定性 EvidenceBundle。Retriever、Reasoner、Verifier、Fusion 和 DecisionTrace 将只读取冻结 snapshot；它们不会重新解释来源工具名或把 attack 标签塞进特征输入。

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

详细研究契约见 `hybridguard_agent_rag_guide/02_TARGET_ARCHITECTURE_AND_CONTRACTS.md`、`03_DATA_SCHEMA_GROUPING_AND_QC.md` 与 `04_ATTACK_COLLECTION_AND_PROVENANCE.md`。
