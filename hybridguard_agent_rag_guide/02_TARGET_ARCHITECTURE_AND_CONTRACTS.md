# 目标架构与核心数据契约

> authoritative_for: 离线/在线架构、模块职责、建议目录、SampleManifest、EvidenceBundle、KnowledgeCard、DecisionTrace
> read_when: 设计模块、接口、中间表示、API 或跨模块数据流
> do_not_read_when: 只做数据统计、攻击采集或实验结果解释
> default_read_budget: 只读目标对象对应的锚点
> allowed_second_books: 03 用于 Schema/字段实现；05 或 06 用于运行逻辑

## Agent 锚点索引

| Anchor | 用途 |
|---|---|
| ARCH-PIPELINE | 总体架构与离线/在线边界 |
| ARCH-RESPONSIBILITIES | 模块职责边界 |
| CONTRACT-MANIFEST | SampleManifest |
| CONTRACT-EVIDENCE | EvidenceBundle |
| CONTRACT-KNOWLEDGE | KnowledgeCard |
| CONTRACT-TRACE | DecisionTrace |

> 阅读方法：先在本文件中搜索 Anchor，仅读取命中小节及其直接上下文；不要默认通读整册。

---
## 4. 目标系统架构

<a id="ARCH-PIPELINE"></a>

### 4.1 总体架构

~~~text
原始三端指纹
  -> expanded-v2 Schema 校验
  -> Canonical 字段规范化
  -> 确定性跨层比较与 EvidenceBundle
  -> 强制核心规则检查
  -> 字段感知知识检索
  -> LLM 六组语义评分
  -> 引用、字段、规则与输出验证
  -> 外部融合与校准
  -> RiskDecision + DecisionTrace
~~~

系统必须区分：

- **离线知识构建链路**：生成候选、验证规则、发布卡片、构建索引。
- **在线推理链路**：只读取冻结的 Schema、KB、索引、Prompt 和融合模型，不在线修改知识。

<a id="ARCH-RESPONSIBILITIES"></a>

### 4.2 模块职责边界

| 模块 | 负责 | 不负责 |
|---|---|---|
| Schema/Normalizer | 类型、路径、单位、枚举、缺失和隐私规范 | 风险判断 |
| Evidence Extractor | 确定性字段解析和跨层关系计算 | 生成最终风险分 |
| Rule Executor | 执行机器可验证规则和 short-circuit | 自由文本解释 |
| Retriever | 找到适用规则、官方依据、容错和训练内案例 | 决定规则真假 |
| LLM Reasoner | 六组语义判断、证据组织、结构化理由 | 直接修改 KB、隐式学习总分权重 |
| Verifier | 验证字段存在、规则条件、引用和输出 Schema | 重新发明风险结论 |
| Fusion/Calibration | 学习可复现的组级权重和阈值 | 解释原始字段语义 |
| Decision Logger | 保存完整版本和证据链 | 向模型暴露标签或测试元数据 |

### 4.3 推荐新目录

建议新增独立目录 hybridguard_agent，现有目录继续作为权威输入：

~~~text
hybridguard_agent/
├── README.md
├── config/
│   ├── pipeline.yaml
│   ├── retrieval.yaml
│   └── model_versions.yaml
├── schemas/
│   ├── expanded_v2.schema.json
│   ├── field_registry.json
│   ├── sample_manifest.schema.json
│   ├── evidence_bundle.schema.json
│   ├── knowledge_card.schema.json
│   └── decision_trace.schema.json
├── adapters/
│   ├── collected_data_adapter.py
│   ├── rule_kb_adapter.py
│   ├── official_kb_adapter.py
│   └── grouped_fusion_adapter.py
├── normalization/
├── evidence/
│   ├── extractors/
│   └── comparators/
├── knowledge/
│   ├── candidate_rules/
│   ├── published_cards/
│   └── source_snapshots/
├── rules/
├── retrieval/
├── reasoning/
├── verification/
├── fusion/
├── evaluation/
├── tests/
└── artifacts/
    └── run_id/
~~~

原则：

- 不复制已有大数据文件；
- 通过 adapter 读取现有规则、官方卡和验证资产；
- 新目录只承载新系统的 Schema、中间表示、索引、评估和运行产物；
- 每次实验输出独立 run_id 目录和 build manifest。

---

## 5. 四个核心中间表示

<a id="CONTRACT-MANIFEST"></a>

### 5.1 SampleManifest

SampleManifest 描述一条样本的来源、采集协议、配对关系、标签真值和分组信息。它不等于模型输入，也不应混进 177 个原始特征。

建议结构：

~~~json
{
  "manifest_version": "sample-manifest-v1",
  "sample_id": "smp-uuid",
  "session_id_hash": "sha256",
  "schema_version": "expanded-v2",
  "raw_payload_sha256": "sha256",
  "collector": {
    "app": "featureapp",
    "app_version": "1.0-expanded-collector",
    "git_commit": "commit-sha",
    "apk_sha256": "sha256"
  },
  "capture": {
    "captured_at_utc": "timestamp",
    "capture_batch_id": "batch-id",
    "source_type": "physical_local",
    "provider": "provider-name",
    "provider_run_id": "run-id"
  },
  "device": {
    "provider_device_id_hash": "hash-or-null",
    "stable_device_key_hash": "hash",
    "stable_key_version": "stable-key-v1",
    "baseline_sample_id": "clean-pre-id",
    "observed_identity_hash": "hash"
  },
  "pair": {
    "pair_id": "pair-uuid",
    "pair_role": "clean_pre",
    "sequence_index": 0
  },
  "label": {
    "environment_class": "cloud_real_device",
    "manipulation_present": false,
    "violation_types": [],
    "label_status": "verified",
    "label_provenance": "operator_and_tool_log"
  },
  "attack": null,
  "quality": {
    "qc_status": "pending",
    "qc_reasons": []
  }
}
~~~

关键约束：

- source_type 表示采集来源，不能使用 script_attack 这类隐含标签的值。
- attack_tool、provider、label、pair_role 等元数据不得进入模型输入或 retrieval query。
- 原始 manifest 保存采集事实；fold、group_size、sample_weight 写入派生 split manifest。
- 当前 155 条历史数据若无法回溯来源和标签，统一标记为 unlabeled。

<a id="CONTRACT-EVIDENCE"></a>

### 5.2 EvidenceBundle

EvidenceBundle 把 177 个字段转化为有限、可解释、可复现的六组证据。

~~~json
{
  "evidence_id": "evidence-uuid",
  "sample_id": "smp-uuid",
  "schema_version": "expanded-v2",
  "extractor_version": "version",
  "derived_facts": {
    "native_android_major": 14,
    "web_android_major": 14,
    "webview_chrome_major": 142,
    "web_chrome_major": 142,
    "native_gpu_family": "adreno",
    "web_gpu_family": "adreno"
  },
  "groups": {
    "native_web": {
      "observations": [],
      "comparisons": [],
      "anomalies": [],
      "query_fields": []
    },
    "native_webview": {},
    "webview_web": {},
    "tri_layer": {},
    "physical_runtime": {},
    "attack_scenario": {}
  },
  "mandatory_checks": [],
  "evidence_hash": "sha256",
  "redacted_for_external_model": true
}
~~~

要求：

- 屏幕、UA、版本、GPU、内存等比较先由确定性程序完成。
- EvidenceBundle 描述观测和矛盾，不直接生成最终总分。
- 相同输入和 extractor 版本必须得到相同 evidence_hash。
- 默认删除原始 client_ip、session_id、标签和攻击工具元数据。
- 完整 build fingerprint、UA、canvas/audio/font hash 等高基数字段应优先转成语义变量或 hash 引用，不原样发送给外部模型。

<a id="CONTRACT-KNOWLEDGE"></a>

### 5.3 KnowledgeCard

KnowledgeCard 统一表示规则、官方知识和训练内案例：

~~~json
{
  "card_id": "RULE-NW-001",
  "kind": "rule",
  "title": "Native 与 Web Android 主版本一致性",
  "canonical_fields": [
    "native.os.major",
    "web.ua.android_major"
  ],
  "evidence_groups": ["native_web"],
  "content": {
    "semantics": "字段语义说明",
    "trigger": "触发条件说明",
    "tolerance": "未知值和版本解析失败不单独高危",
    "counterexamples": []
  },
  "predicate": {
    "operator": "neq_when_both_known",
    "left": "native.os.major",
    "right": "web.ua.android_major"
  },
  "provenance": {
    "source_refs": [],
    "support_count": null,
    "counterexample_count": null,
    "created_from_split": null
  },
  "applicability": "current",
  "evidence_strength": "medium",
  "status": "published",
  "version": "version"
}
~~~

知识类型必须分层：

| 类型 | 内容 | 风险结论能力 |
|---|---|---|
| official | 官方字段语义、机制、限制和安全背景 | 不直接提供风险阈值 |
| deterministic_rule | 人工审核或程序可验证的跨层关系 | 可作为明确约束 |
| empirical_rule | 仅由训练数据归纳的候选规律 | 必须验证后才能发布 |
| empirical_case | 训练 fold 内的历史案例 | 只能作为相似证据 |

规则状态建议：

~~~text
draft
  -> candidate
  -> validated
  -> published
  -> deprecated

任一阶段也可以：
  -> rejected
~~~

<a id="CONTRACT-TRACE"></a>

### 5.4 DecisionTrace

DecisionTrace 保存一次推理的完整证据链：

~~~json
{
  "decision_id": "decision-uuid",
  "sample_id": "smp-uuid",
  "versions": {
    "schema": "version",
    "extractor": "version",
    "rule_kb": "version",
    "retrieval_index": "version",
    "prompt": "version",
    "model": "version",
    "fusion_model": "version"
  },
  "mandatory_rule_results": [],
  "retrieval": {
    "query_fields": [],
    "filters": {},
    "retrieved_cards": [],
    "retrieval_scores": []
  },
  "matched_rules": [],
  "group_scores": {},
  "group_reasons": {},
  "fusion": {
    "weights": {},
    "raw_score": 0,
    "final_score": 0
  },
  "citations": {
    "rule_ids": [],
    "card_ids": [],
    "source_ids": [],
    "field_ids": []
  },
  "verification": {
    "output_schema_valid": true,
    "citations_valid": true,
    "fields_observed": true,
    "short_circuit_respected": true,
    "future_evidence_absent": true
  },
  "risk_band": "low",
  "uncertainty": 0.0,
  "runtime": {
    "latency_ms": 0,
    "input_tokens": 0,
    "output_tokens": 0
  }
}
~~~

完整 DecisionTrace 用于复现、错误分析和论文案例；对外 API 可以只返回精简 RiskDecision。

---

