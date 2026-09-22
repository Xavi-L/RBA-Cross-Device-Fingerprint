# HybridGuard 研究数据管线

这个目录把现有的采集、规则、官方知识和后续 Agent/RAG 研究组织成可冻结、可重跑的离线管线。当前研究入口是下方 MTC v2 离线 QC 快照，接纳 v9 与 v11；v1 运行时适配属于 P4。旧 v8 管线、旧云数据和历史攻击 pilot 仅保留为历史材料，不混入 MTC 主视图。

它不替代现有目录：

- 当前权威输入是 `backend_server/collection_backups/mtc_final_20260922/sources/` 内的 App／Browser raw、receipt 与 provenance；后端根目录旧文件不进入 MTC 分析；
- `scoring/rule_knowledge_base.json` 和 `google_official_kb/` 保留历史 v1 规则与官方知识来源；当前 paired244 新链使用 `config/paired244_rule_catalog.v3.json`，历史验收保留 v1、v2 目录；
- `hybridguard-browser-fingerprint-research/` 仍是攻击侧同学维护的执行日志和证据仓库；
- 本目录只生成契约、样本 manifest、QC、冻结快照和离线运行所需的派生产物。

历史云真机的 `field-status` 补标规则见 [HISTORICAL_FIELD_STATUS.md](HISTORICAL_FIELD_STATUS.md)。旧 snapshot 管线使用独立的 `field_status.jsonl` sidecar；当前 paired244 入口直接保留 App177/Browser67 已上报的逐字段状态，并与特征值分栏存放。两条管线都不会改写原始 JSONL，也不会给 Browser 失败样本补造67项。

## 当前入口：MTC snapshot v2（2026-09-22）

本机后端与 ngrok 已退役，后续离线分析不再启动采集服务。统计以自有数据为准，采购对账已取消。研究遵循：旧实验只提供设计参考，不继承旧结论，也不以复现旧效果为验收目标。

用户已明确没有补采机会，现有数据就是全部资源。剩余规则研究已收尾：无法验证的条目关闭，描述性结果不升级成攻击规则；P5 补采取消，后续实验仅报告现有证据能支持的结论。当前结果见下方 v3 章节。

2026-09-23 按用户明确要求，将 MTC 最终原始冻结、P1 QC 快照和 P2 分组清单一并纳入 Git；数据入口与计数见 [数据交付说明](../deliverables/mtc_closed_resource_20260922/DATA_DELIVERY.md)。保留验证集的锁定状态不因数据提交而改变。

P0、P1 已完成：接收 1,029 条完成配对、891 个厂商／型号／系统组合；QC 主视图保留 1,028 条配对，仍覆盖 891 个组合。另 1 条配对保留为部分数据，原始记录不删除。v2 区分采集状态、已知默认哨兵和数值表示；P2 已冻结分组／切分和任务准入；P3 已完成旧规则基线与有限候选研究目录；P4 已接入 244 执行链。独立事实标签仍缺失，检测指标未准入，保留验证集继续锁定。

```bash
python3 hybridguard_agent/scripts/build_mtc_paired244_snapshot.py \
  --config hybridguard_agent/config/mtc_paired244_sources.v2.json \
  --output-dir hybridguard_agent/artifacts/mtc_v2_NEW_RUN
```

输出目录必须不存在。正式 P1 产物是 `artifacts/mtc_paired244_v2_20260922_final/`；详细报告与验证见 [P1 报告](../deliverables/mtc_p1_20260922/P1_REPORT.md)、[阶段计划](../deliverables/paired244_reassessment_20260922/PLAN.md)。以下 v8 命令及“最新”命名保留历史语义，不适用于本次 MTC 主研究。

## MTC P2：分组、切分与任务准入（已完成）

正式产物：`artifacts/mtc_p2_frozen_20260922/`。P1 的 891 个型号／系统统计口径不变；用于防泄漏时，同一厂商＋型号跨系统整组分配，合格配对涉及 868 个分组。发现／开发／保留验证各有 630／144／117 个代表记录，组数分别是 610／142／116。

```bash
python3 hybridguard_agent/scripts/build_mtc_experiment_plan.py \
  --output-dir hybridguard_agent/artifacts/mtc_p2_NEW_RUN
```

P3 规则发现从 `discovery_inputs.jsonl` 进入，开发检查从 `development_inputs.jsonl` 进入；两者仅包含样本和源数据引用，不含标签、scenario 或阶段信息。保留验证集未导出执行输入，直到规则和评价协议冻结后再按新阶段合同解锁。P2 只建立准入控制，不运行规则或检测指标。

主代表记录按每型号／系统的最早合格配对固定，不按告警、分数、字段完整率选择。全部重复、App-only 和部分数据保留在同组；支持度按组计。全量 QC 已暴露的事实明确保留，不能把保留集称为从未查看的外部盲测集。详见 [P2 报告](../deliverables/mtc_p2_20260922/P2_REPORT.md)、[事实标准](../deliverables/mtc_p2_20260922/FACT_STANDARD.md)。

## MTC P3：旧规则重验与研究目录 v2（已完成）

权威输出：`artifacts/mtc_p3_legacy_20260922/` 与 `artifacts/mtc_p3_discovery_20260922_r2/`。发现／开发仅使用冻结的 630／144 个代表记录；保留验证继续锁定。45 个有限模板筛选后，30 项进入离线研究目录：10 经验关系、14 语义约束、6 采集器自洽项；15 项落选或仅描述，全部结果与反例保留。它们不是 30 条独立的新攻击规则，没有风险权重或检测效果结论。

旧基线发现 provider 包版本首段不能无条件当作 Chromium major；低传感器数量也不能直接当作攻击。处置与后续运行时边界见 [P3 报告](../deliverables/mtc_p3_20260922/P3_REPORT.md)、[候选清单](../deliverables/mtc_p3_20260922/CANDIDATES.md)、[旧规则基线](../deliverables/mtc_p3_20260922/LEGACY_BASELINE.md)。首次运行的 Native OS 前缀解析缺陷已修复，初次输出保留作废标记；修正版披露开发集先前暴露，不更改模板或筛选阈值。

```bash
python3 hybridguard_agent/scripts/run_mtc_p3_discovery.py \
  --config-dir hybridguard_agent/artifacts/mtc_p3_discovery_20260922_r2 \
  --out-dir hybridguard_agent/artifacts/mtc_p3_NEW_RUN
```

输出目录必须不存在。执行器只接收字段值、状态和质量，分组／画像仅用于外部统计；不向模型或规则输入标签。P3 的 44 项重点测试与完整反例核验已通过，后续 P4 执行链见下节。

## MTC P4：paired244 执行链（已完成）

`evidence-bundle-v3-paired244` 区分 Native、宿主、App Web 和 Browser 字段，Browser 真正进入规则、精确检索、Verifier 和 trace。P4 首轮验收固定的 `config/paired244_rule_catalog.v1.json` 有 87 个台账条目：48 项可执行检查、2 项停用、37 项未实现。48 项包含来源重叠和 6 项采集器自检，不代表 48 条独立攻击规律。默认入口现已升级到下方的 v3；历史验收命令仍固定 v1。

新链的 CORE-002 只检查 bridge，低传感器数量不再否决或短路；旧 provider 包版本＝Chromium 版本关系停用。旧 raw App177 入口仍保留 v1 历史语义用于重放，P1 v2 record 会自动路由新链；显式视图入口：

```python
from hybridguard_agent.runtime import analyze_paired244_record
result = analyze_paired244_record(p1_record, input_view="Full244")  # 或 App177
```

通过冻结 P2 清单重现工程验收：

```bash
python3 hybridguard_agent/scripts/run_mtc_p4_runtime.py \
  --out-dir hybridguard_agent/artifacts/mtc_p4_NEW_RUN
```

权威产物：`artifacts/mtc_p4_runtime_20260922_release/`。1,548 次执行无失败，23,220 次 P3 结果对照无变化；去掉 Browser 的 6,966 次相关检查均 NOT_EVALUATED。48 项新旧边界与兼容测试通过。模型、分数融合和攻击分类均关闭，不把输入比较当作检测收益。见 [P4 报告](../deliverables/mtc_p4_20260922/P4_REPORT.md)、[执行台账](../deliverables/mtc_p4_20260922/RULE_INVENTORY.md)。

## 37 项旧条目的处置与首批实现（v2）

首批当时逐项复核 37 项：6 项接入部署/上下文检查、4 项合并处置、2 项停用、17 项待研究、8 项待补数据。v2 目录仍为 87 项，其中 **54 项可执行**，不意味着 54 条独立攻击规则或全部旧规则已完成。剩余 25 项现已按下一节收尾，不再保留待研究／补采任务。

首批时默认入口采用 `paired244-runtime-catalog-v2`，当前已改为 v3；下面的历史首批命令固定使用 v2。旧 raw App177 行为保持历史版本。要显式重放 P4 v1 或首批 v2，可传入 `catalog=load_catalog(LEGACY_CATALOG)` 或 `catalog=load_catalog(V2_CATALOG)`，这些符号从 `hybridguard_agent.rules.paired244` 导入。

新增包名与版本检查依据已经声明的 MTC 部署清单，差异单列 `POLICY_MISMATCH`；安装来源、UA 标记、开发配置和网络仅报告上下文。`manual` 是采集器的 null 回退，不能证明实际手动安装；旧 API 网络回退明确不适用。`TOL-004` 的版本容错与 `SCENE-004` 的低风险确认停用。待研究、待补数据、合并和停用项保留在 trace 中，并排除于活跃检索卡。

```bash
python3 hybridguard_agent/scripts/run_mtc_rule_backlog.py \
  --out-dir hybridguard_agent/artifacts/mtc_rule_backlog_NEW_RUN
```

首批结果：1,548 次运行无失败、74,304 次原检查对照无变化、6,966 次 Browser 遮蔽检查通过；62 项重点及兼容测试通过。保留集未解锁，未调阈值或执行检测效果实验。详见 [历史首批报告](../deliverables/mtc_rule_backlog_20260922/REPORT.md)、[37 项初次处置](../deliverables/mtc_rule_backlog_20260922/REVIEW.md)。

## 现有资源内研究收尾与默认运行时（v3）

剩余 25 项已全部处置：**3 项新增限定检查、11 项仅保留描述、11 项无法验证关闭**。默认目录仍为 87 项：**57 可执行、11 描述性、11 无法验证关闭、4 合并、4 停用**，没有待研究或待补采条目。关闭不代表验证通过，57 项也不是独立的攻击检测规律。

新增 `NW-001`、`NVW-001`、`NW-005` 分别比较 Native 型号与 App UA 显式型号、Native 型号与 Dalvik 系统 HTTP agent 显式型号、Native GLES 与 App WebGL 的可识别 GPU 家族。型号缩减、模糊格式和未知 GPU 保留不适用／未知。四个候选和边界在统计前冻结；双边屏幕尺寸候选发现／开发均有大量反例，未启用，也未放宽容差。其余条目完成字段语义核对、描述汇总或缺证据关闭。

```bash
python3 hybridguard_agent/scripts/run_mtc_closed_resource_study.py \
  --out-dir hybridguard_agent/artifacts/mtc_closed_resource_study_NEW_RUN
python3 hybridguard_agent/scripts/run_mtc_closed_resource_runtime.py \
  --out-dir hybridguard_agent/artifacts/mtc_closed_resource_runtime_NEW_RUN
```

权威产物分别为 `artifacts/mtc_closed_resource_study_20260922/`、`artifacts/mtc_closed_resource_runtime_20260922/`。79 项重点和兼容测试通过；1,548 次运行无失败，83,592 次原 54 项结果对照无变化，2,322 次新增研究／运行时对照一致，6,966 次 Browser 遮蔽检查通过。当前 `analyze_paired244_record`、P1 record 的 `analyze_payload` 及 readiness 均使用 v3；历史 v1／v2 重放入口保留。

保留验证集继续锁定，攻击分类为 `NOT_EVALUATED`，不训练模型、不拟合阈值。P6／P7 尚未执行；后续仅开展现有数据支持的固定规则输入、规则版本、知识来源及覆盖／冲突／未知比较，缺少标签的检测指标不进入本轮任务。详见 [研究收尾报告](../deliverables/mtc_closed_resource_20260922/REPORT.md)、[25 项最终处置](../deliverables/mtc_closed_resource_20260922/RESOLUTIONS.md)。

## 历史 v8 入口：paired244 快照、离线运行与实验准入

第一批施工已经完成数据选择、配对和 QC；第二批只把其中的 App177 接到既有 EvidenceBundle v2 与确定性离线运行时，并为完成配对的样本生成独立 Browser 对比 sidecar。Browser sidecar 不进入规则、检索或决策，也不产生模型分数。当前发布锁为：

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

基于上述快照构建第二批离线运行输入：

```bash
python3 hybridguard_agent/scripts/build_latest_runtime_inputs.py \
  --snapshot-dir hybridguard_agent/artifacts/latest_paired244/latest_paired244_YYYYMMDD \
  --output-dir /private/tmp/hybridguard_latest_runtime_inputs
```

该命令不回写快照，并分别生成：

- 26 条 App EvidenceBundle v2，覆盖17条 paired244 与9条 App-only；
- 17 条脱敏的 `browser-pair-evidence-v1` sidecar，每条固定比较67个同名 Web 字段；
- 26 条不含 session、receipt、pair、batch 或设备标识的运行时索引；
- 一份记录输入版本、数量和运行边界的 manifest。

Browser 对比采用冻结策略：39项做严格字面比较，28项因时序、权限域、网络或容器界面影响而只记为 `not_comparable`。`same`、`different`、`unavailable` 都只是采集观察，不是异常、攻击或设备身份结论。App-only 样本不会生成虚假的 Browser sidecar。

第三批只搭建实验控制面，不训练模型。它把外部核验的标签、指纹效果事实和可跨 run 的匿名稳定分组与 `sample_index.jsonl` 绑定，再按整组做确定性 train/development/test 切分。运行：

```bash
python3 hybridguard_agent/scripts/build_latest_experiment_plan.py \
  --snapshot-dir hybridguard_agent/artifacts/latest_paired244/latest_paired244_YYYYMMDD \
  --output-dir /private/tmp/hybridguard_latest_experiment_plan \
  --facts /path/to/latest_experiment_facts.jsonl
```

`--facts` 可以暂时不传。对当前小数据实跑时，命令会正常生成26条 inventory（17条 paired244 候选 + 9条 App177 reserve），但因为 verified label 和可信 stable group 都是0，`split_manifest.jsonl` 为空，`structural_ready=false`、`grouped_data_prerequisites_met=false`。这是预期的准入阻断，不是构建失败，也不会把 unlabeled 样本猜成正常类。

以后大批量数据到达后，只需提供 `latest-experiment-fact-v1` sidecar 并重跑该命令。事实必须用 `app_session_id + app_payload_sha256` 双重绑定；主任务只接收经核验的 `paired244_fingerprint_effect`，transport-only 与 Browser `different` 不会变成攻击正例。同一 stable group 和 scenario 始终在同一 split；App-only 仍保留在 inventory，不进入244维主指标。当前冻结协议要求每个 split 至少5个独立组、每类至少来自2个组，才会将 `grouped_data_prerequisites_met` 打开。这只表示分组数据骨架可交给后续实验器；第三批仍不授权训练、调阈值、查看最终测试集或报告性能指标。

## 历史研究资产（逻辑归档）

以下内容记录旧快照和研究 pilot，保留用于复核，不再作为默认数据入口。截至 2026-07-14 的旧快照曾记录155条 expanded 数据；其历史采集没有逐条 provider run ID、配对关系或攻击事实标签，因此不进入最新版 paired244 主视图、有监督攻击检测训练或最终效果评估。

攻击侧仓库的 2026-07-11 release view 记录 393 条严格工具映射的实测会话：178 条 attack-capable/abnormal 且三端完整、184 条 attack-capable/abnormal 但缺层、31 条完整的合法隔离对照。release view 已脱敏且不含 177 字段 payload 或可关联 session ID，因此只作为攻击覆盖证据。

攻击侧 2026-07-15 已提供 51 行 verified label-only registry。管线同时按 `sample_id` 与 `source_session_id` 完成 51/51 双键校验，并把它与原始 177 字段严格分开。当前可形成 9 条 CDP 指纹字段影响 pilot 和 9 条 mitmproxy 传输路径 pilot；后者明确不宣称指纹字段变化，不能混入同一个正例类别。所有完整 pair 仍只在 `train` split，且 3 条 CDP active 的原始字段直接含有 intervention 名称，存在模板捷径。因此可以跑通 pilot 流程，但正式 held-out 攻击评估仍未解锁。详细映射见 [ANNOTATION_REGISTRY_INTEGRATION.md](ANNOTATION_REGISTRY_INTEGRATION.md)。

## 目录与职责

```text
hybridguard_agent/
├── config/latest_paired244_sources.json # 当前 FeatureApp/Browser 发布锁与输入
├── config/browser_pair_comparison.v1.json # 39项严格比较/28项不比较的冻结策略
├── config/latest_experiment_protocol.v1.json # 准入、可信分组和确定性切分协议
├── config/dataset_sources.json        # 输入来源、事实边界与模型资格
├── config/deterministic_rule_predicates.v1.json # 已审阅的可执行规则及 KB hash
├── ANNOTATION_REGISTRY_INTEGRATION.md # Week 7 标签接入、任务分流与结论边界
├── schemas/                           # 冻结的 expanded-v2、Evidence/Trace 契约
├── evidence/extractor.py              # 脱敏的 EvidenceBundle v2
├── evidence/browser_pair.py           # 独立 Browser 配对观察 sidecar
├── rules/executor.py                  # 确定性 predicate（不产生风险分）
├── retrieval/exact_retriever.py       # 精确规则/字段知识卡检索
├── verification/verifier.py           # 引用、字段与无校准分边界核验
├── runtime/                           # 组合运行时和冻结快照加载器
├── templates/attack_manifest.template.json
├── scripts/build_latest_paired244_snapshot.py # 当前177+67配对、留存与QC入口
├── scripts/build_latest_runtime_inputs.py # 最新快照到离线运行输入的桥接
├── scripts/build_latest_experiment_plan.py # 标签/分组准入与无泄漏 split 骨架
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

## 确定性运行时与当前第二批桥接

运行时现在可以读取历史 `normalized_expanded_v2.jsonl`，也可以读取当前 `paired_244.jsonl` / `app_only_177.jsonl`。最新分支只从视图中重建 App177 payload 与 field status，再生成既有 EvidenceBundle v2；sample index 中的 session、receipt、pair、batch 等控制面字段不会进入推理。

运行时把一条三层 payload 处理成下面的闭环：

```text
payload + field_status
  -> EvidenceBundle v2（只保留派生事实和字段路径）
  -> 已审阅的确定性规则
  -> 当前规则/官方知识卡的精确检索
  -> Verification + DecisionTrace
  -> 未校准的结构化结论
```

当前运行时仍只真正评估两组 App 证据：`cross_layer` 和 `runtime_context`。`browser_pair`、`attack_scenario`、经验案例检索和校准融合都会显式返回 `not_assessed`，而不是假装有结论。第二批没有修改 EvidenceBundle v2、规则库或 DecisionTrace；运行结果只附 Browser sidecar 的状态、哈希与汇总，并固定标记 `used_by_rule_execution=false`。输出中的 `calibrated_risk_score` 固定为 `null`，`external_model_called=false`。

直接用最新快照运行一条样本：

```bash
python3 hybridguard_agent/scripts/run_agent_runtime.py \
  --snapshot-dir hybridguard_agent/artifacts/latest_paired244/latest_paired244_YYYYMMDD \
  --sample-id YOUR_SAMPLE_ID \
  --output /private/tmp/hybridguard_runtime_result.jsonl
```

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

## 历史管线接入真实攻击数据（非当前 paired244/第二批）

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
