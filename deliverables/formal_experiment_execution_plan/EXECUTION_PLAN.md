# HybridGuard 正式实验逐步实施计划

计划版本：`formal-experiment-execution-plan-v1-20260923`。编制日期：2026-09-23。当前进度：**S01、S02、S03 已完成；S03-R v2 外部审查通过；S04 已完成实现及合成工程验证；S05–S12 未执行。** 原始编制快照保留在第 2 节；最新执行事实见 `EXECUTION_STATUS.json`。

本计划依据 `HybridGuard_Experiment_Design/` 四份文件的完整内容，并核对两个本地仓库的源码、原始材料、保存结果和访问记录。工程验收是合同、实现、隔离和结果完整性；论文结论由真实结果决定。高检出、零误报、联合最优或每个模块有收益均不是验收条件。

## 1. 执行边界与路径约定

- 主仓库 M：`/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint`。
- 攻击仓库 A：`/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/hybridguard-browser-fingerprint-research`。
- 设计包 D：`M/HybridGuard_Experiment_Design`。
- 本计划 P：`M/deliverables/formal_experiment_execution_plan`。
- 新实验产物 R（**拟新增**）：`M/hybridguard_agent/artifacts/formal_manipulation_v1_20260923`。
- 新实现 N（**拟新增**）：`M/hybridguard_agent/research/manipulation_eval`。
- 新配置 K（**拟新增**）：`M/hybridguard_agent/config/formal_manipulation_v1`。
- 下文已有文件路径以 M 为根；`A/` 表示攻击仓库。R、N、K 及标明“拟新增”的脚本当前不存在，不能当作现成命令。

计划编制时已核对仓库、攻击仓库和祖先目录，未找到适用的实体 `AGENTS.md`；本轮遵循用户在会话中提供的 AGENTS 约束。未运行实验、检测器、材料校验器、测试、攻击工具、训练或模型调用，未启动服务，未修改业务代码、规则、数据及历史结果。仅按用户明确要求更新攻击仓库，并新建两份计划文件。资料包已经解压存在，无需另行解压。

后续“执行 Sxx”只授权该步列出的任务和聚焦测试。先读本文件、`EXECUTION_STATUS.json` 及依赖产物；依赖不满足则报告，不擅自补跑。每步保存真实验证记录、变更摘要、遗留事项并更新状态，然后停止。不自动提交、推送或执行下一步。P0–P6、原始输入、历史冻结目录和已保存结果始终只读；修正方法另起版本。

## 2. 计划编制时的状态核对

### 2.1 版本、差异与证据边界

| 项目 | 本机核对事实 | 处理 |
|---|---|---|
| 主仓库 | `main`，`bc305de024a0374e3dcc0d45c2f132203210e327`，与 D 的 `repo_commit` 完全一致 | 不更新或切换主仓库；冻结时同时记录相关工作区差异，不能只记录 HEAD |
| 主仓库未提交内容 | 计划写入前 `git status` 为 212 修改、1 删除、41 未跟踪条目；包含大量 Android build 产物 | 数字是 Git 状态条目数，不是全部未跟踪文件数量；保留原样，详细快照在进度 JSON |
| 相关源码差异 | `featureapp/build.gradle.kts`、`COLLECTION_METADATA.md`、`BrowserPairTransport.kt`、`ExpandedUploadWorker.kt`、`MainActivity.kt`、`gradle.properties`；新增 `CollectionTls.kt`、`CollectionNetworkFailure.kt`、资源与测试 | 本机已改为 1.6.4/TLS/HTTPS 入口，与 HEAD 的采集配置有差异；本离线实验不重建 APK，不用当前构建版本反写旧材料版本 |
| 研究链差异 | `hybridguard_agent/` 与 P6 相关受控文件无未提交差异；`knowledge_rule_validation/` 仅见 `.DS_Store` 未跟踪 | 本计划有可核对的实现基线，不等于整个工作区干净 |
| 攻击仓库更新 | 更新前 `4de5fa625e67887667f28f2c072aac464a7c2cb8`；联网 fetch 后在干净工作区 `merge --ff-only origin/main` 到 `9698e8dfeb450094d99c46bdcff15283c995e3b3`；HEAD=origin/main，更新后干净 | 没有 checkout/reset/clean/commit/push；网络沙箱首次阻止 SSH，授权通道重试成功 |
| 攻击侧新增提交 | 26 文件，主要为脱敏 ACM 草稿、claim ledger、公开汇总及 `execution_log/evidence/week10_rule_source_ledger_v1.jsonl` | 不把论文旧结果、攻击侧 W7/W6 规则视为主仓库当前 E/O 台账或新实验结果 |
| 资料包攻击基线 | D 只给 ZIP SHA-256 `fc0b1aaec61bbcde929105f064230f2b2713f5056682135e25db2dafe55c92af`，没有可验证的攻击仓库 commit | 本地 Git 更新不能证明与该 ZIP 逐字节相同；按包名、manifest、原始记录和引用关系做 S01 对照，无需为开始主线索要原 ZIP |
| 审计路径 | JSON 中有 `/mnt/data/attack_repo/...` | 仅是原审计环境定位信息；以 A 下实际路径解析，不创建这些外机目录 |

主仓库其余用户内容还包括 TLS/部署交付件、ngrok 配置、设备失败日志和 IDE 配置；均不在后续实验实现允许修改范围。S05 只对实际参与离线研究的源码、配置和输入做有限版本绑定，不做全库安全审计。

### 2.2 P0–P6：已完成内容、实际产物与复用范围

| 阶段 | 目前真实状态 | 已有路径与复用内容 |
|---|---|---|
| P0 | 完成；采购对账已取消，采集服务/ngrok 已退役 | `deliverables/mtc_p0_20260922/P0_REPORT.md`；最终源为 `backend_server/collection_backups/mtc_final_20260922/`。早期 `mtc_p0_20260922` open cutoff 只是历史，不重做结算 |
| P1 | 完成；1,028 合格 paired244，654 App-only，11 partial，6 同 session 额外观测，均无独立正常标签 | `deliverables/mtc_p1_20260922/P1_REPORT.md`；`hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/`。复用字段状态/质量、缺字段和零哨兵处理 |
| P2 | 完成；891 型号/系统代表、868 保守分组；发现/开发/保留 630/144/117 条、610/142/116 组 | `deliverables/mtc_p2_20260922/P2_REPORT.md`；`hybridguard_agent/artifacts/mtc_p2_frozen_20260922/`。复用代表、分组和暴露记录，891 不等于独立物理设备数 |
| P3 | 完成；45 候选、30 研究条目，r2 为修复 OS 解析后的权威版本 | `deliverables/mtc_p3_20260922/{P3_REPORT.md,SEMANTIC_REVIEW.md}`；`hybridguard_agent/artifacts/mtc_p3_discovery_20260922_r2/`。不重挖规则或重新筛选 |
| P4及后续收尾 | P4 初轮48活跃检查；后续目录 v3 已有87条、57活跃 | `deliverables/mtc_p4_20260922/P4_REPORT.md`；初轮权威 `_release`；当前 `config/paired244_rule_catalog.v3.json` 与 `deliverables/mtc_closed_resource_20260922/`、`deliverables/mtc_rule_backlog_20260922/` |
| P5 | 补采已取消 | `TODO.md`、`deliverables/paired244_reassessment_20260922/PLAN.md`；不得标 DONE 或重新作为前置采购任务 |
| P6 | 完成15条件×891=13,365主单元；已保存0失败的历史运行记录 | `deliverables/mtc_p6_20260923/` 与 `hybridguard_agent/artifacts/mtc_p6_fixed_20260923/`；直接复用关系覆盖、反例、来源与重复观测结果；不是新报警性能 |

P6 的 `RESERVED_ACCESS.json`/`RESERVED_RELEASE.json` 为 `CONSUMED_FIXED_EVALUATION`：117 主代表+18重复已读取。`RESERVED_FIRST_READ.json` 为 `2026-09-22T16:30:27Z`；更早全量 QC 已可见。P2 的旧 LOCKED 文件不证明现在仍是盲测。历史攻击侧已有评价和主仓库69对暴露也必须进入新 `exposure_history.json`。

### 2.3 已有实现与尚待补齐

| 领域 | 当前实现/结果 | 本计划新增边界 |
|---|---|---|
| 字段证据 | `evidence/paired244.py` 的 `build_paired_evidence`、`field_contract`、`VIEWS`，证据抽取前遮蔽，六种源状态与三种质量分开 | 复用；适配旧三态为同合同，保留 current-session-only，不附加 Browser |
| 规则 | `rules/paired244.py` 执行 ACTIVE 目录，逐条保留 `required_fields/used_fields/outcome`；目录有 `evidence_family`、来源及限制 | 不改冻结目录；新版本角色/适用性覆盖层把“可执行关系”与“可报警证据”分开 |
| 检索/验证 | `retrieval/paired244.py` 精确当前规则卡；`verification/paired244.py` 重算并检查证据引用 | 复用原验证；原 Verifier 要求 `attack_classification=NOT_EVALUATED`，新增策略使用独立输出和验证器，不能破坏旧合同 |
| 运行时 | `runtime/paired244.py::analyze_paired244_record`，融合关闭，校准分数 null，外部模型关闭 | 新增研究用报警层；不改线上/API链，不假称已有分类器 |
| App177兼容 | `scripts/run_mtc_p6_history.py::legacy_row` 已兼容旧177明确字段状态；P6 保存23清单/69对/138阶段，无排除与失败 | 不重做适配底座；新 loader 保留 clean_post、control_mid、失败尝试和独立事实侧表 |
| 旧攻击loader | `scripts/run_two_source_rule_classification.py::load_attack_pairs` 把 clean_post 归为 historical_post 并忽略 | 不能直接用于三态恢复；旧 input-set只作材料定位和暴露史 |
| 分组/汇总 | `scripts/build_mtc_experiment_plan.py` 的 UnionFind、link_keys、build_groups；`research/mtc_p6.py` 的 select_rules、summarize、paired_comparison | 复用思路/纯函数；攻击侧键需重新定义；无标签关系指标不能直接充当TPR/FPR |
| 绘图 | `ablation/make_figures.py` 为旧表硬编码数据源；旧 grouped ablation 含 RF 和风险标签 | 只借绘图样式；拟新增从本轮保存长表出图入口，不运行旧训练/绘图链 |

这里以及后文省略 `hybridguard_agent/` 的模块路径均位于该目录下。

### 2.4 攻击原始材料与具体差异

本地存在 `A/reports/current/hybridguard_controlled_attack_matrix_teacher_brief_20260824.md`、`A/execution_log/evidence/*/attack_sample_manifest_v1.jsonl`、`control_sample_manifest_v1.jsonl`、`raw_payloads.jsonl`、run记录、runner receipts，以及两个校验器源码。静态清点与 D 一致：23完整攻击包=69三态/207阶段，另2不完整或空manifest；6无攻击包=18三时点/54阶段。已看到的262条 raw 均为 expanded-v2.2-status，显式177状态键与当前字段目录相符；这只是结构事实，不是新标签准入或校验PASS。

资料包记载18包PASS、5包FAIL，但**本轮未重跑校验器，不能称本机已经复验18包通过**。S01重新保存本地材料校验结果。5个旧包目前仍各缺3个 `automation_logs/*_{cdp,stealth}.json`，共15个 `success_evidence` 直接引用文件：

- `20260812_cdp_api30_formal_v4`
- `20260812_cdp_api35_formal_v1`
- `20260812_cdp_api36_formal_v1`
- `20260812_stealth_api35_formal_v1`
- `20260812_stealth_api36_formal_v2`

逐文件相对路径已在 D/`attack_bundle_audit.json` 的 `missing_success_evidence` 中列出，S01写本地化缺件清单。18其余包有runner receipts，但 `verifyRunnerReceipt` 对 `runner_log_sha256` 主要验证格式，不读取缺失的私有原日志；不能将回执支持写成第三方现场见证。

更具体地，54个runner receipts中48个未提供原日志路径，另6个V5回执虽有`runner_log_path`，对应screen/timezone两包的6个`automation_logs`原日志也不在本地。这与5旧包15个直接引用缺件是不同类别。V5已保存apply/rollback命令响应及runtime observations可以作为同源证据，不能变成独立见证。两不完整包为`20260823_cdp_api30_controlled_v1`（1行，记录INJECTION_NOT_OBSERVED）和`20260823_playwright_api36_controlled_v1`（0行，记录clean retained playwright marker），均保留为尝试失败，不能用后续成功版本抹去。

必须处理的两个实际风险：raw 的 `collection_manifest.runtime_context` 在攻击材料中含 `capture_*`、对照中含 `control_*`，会泄漏来源；不同 API36 `device_manifest_id/stable_device_key_hash` 仍可能具有相同 `collector_install_id`，按文件夹或旧alias分组会制造虚假独立性。前者彻底排除在推理输入之外；后者按安装/环境链接的传递闭包合组，并保留关联依据。矩阵说明的“独立campaign”不能推导为独立设备。

本次静态可辨认3个安装群，不能称3台已核验独立物理设备。sidecar的`device_identity_stability=verified_within_attack_run`与`identity_hash_method=sha256-canonical-stable-identity-v1`，也不同于`A/execution_log/protocols/device_identity_hash_mapping_v1.md`中的HMAC/provider_stable_profile合同；S01保留原值并记录解释映射，不假装已获得跨运行物理身份。

攻击release lock为`A/execution_log/evidence/featureapp_current_release_lock_v1.json`：1.6.3-expanded-v2.2-webview-control/code10、上游`3a16d89363c86f7ad487c5b12c764521390ea44c`。5旧包Web/WebView值为flat transport，18新包为logical nested，状态均为logical全路径。S02须兼容两形状，不能将旧release改成当前MTC v9/v11。

### 2.5 必须显式解决的文档冲突

1. **编号冲突**：本计划 E1–E6 始终指 D 的研究问题。P6历史 E1/E2=旧引擎/版本，E3/E4=输入/跨端，E5=来源，E6=边界，E7=历史诊断。保留历史编号，引用时加“P6历史”；不得修改旧文件来统一编号。
2. **P4历史安排过时**：P4下方曾写后续P5采集，当前TODO已取消。采用最新明确状态，P0已完成也不被旧记忆中的“未对账”倒退。
3. **只读审计入口会写文件**：`deliverables/mtc_p6_20260923/audit_saved_outputs.py` 末尾会覆盖历史 `FINAL_AUDIT.json`。后续仅复用核对逻辑，新增输出到R的入口，不直接执行该文件。
4. **P6逐规则事件不全**：`results.jsonl` 保存所有outcome，完整 `used_fields/reason` 只对 `counterexamples.jsonl` 的468条偏差/策略差异日志保存。新导出缺项标 `NOT_RECORDED_IN_P6`，不得补造完整trace或为补图重跑P6。
5. **App语义门控有缺口**：`NW-002/OFFDER-OS-001` 直接比较Android主版本；`P3-UA-REDUCED-BROWSER` 只处理Browser，不能宣称App UA reduction已统一处理。S03/S04在新策略层明确门控，冻结历史谓词不动。
6. **独立official_document卡为0**：来源分类不是RAG实验；不把攻击侧已有LLM公开汇总并入主链。

## 3. 研究问题、产物与论文图表映射

| 研究问题/资料包实验 | 固定条件 | 保存的原始输出 | 汇总指标 | 图表 | 能支持的表述与限制 |
|---|---|---|---|---|---|
| 方法与泄漏边界 | 四特征表面、三运行上下文；当前会话推理/评估侧连接 | input schema、allowlist、policy、验证记录 | 不涉及性能 | Fig.1 | 系统合同与数据流；不得画标签进入检测器 |
| E1 干预检出/撤销/对照 | legacy策略基线、当前目录关系策略、最终门控联合策略；同一准入集合 | S06 predictions/rule_events + S01独立facts | attack/pre/post/control各k/n；010；弃判/失败；分组/配置宏平均 | Fig.2、Fig.3、Table.2 | 可观测成功干预上的报警响应及恢复；不声称工具全部尝试成功率或随机因果识别 |
| E2 来源贡献 | C、C+E、C+O、C+E+O；O_u/H/E八条件 | S07逐条件预测、规则和family事件 | TPR/FPR/coverage条件增量、四格重叠、联合取消/新增 | Fig.3、Fig.4、Table.3 | 目录来源分组贡献；O含经验筛选；无结果不预写“官方精度/经验召回” |
| E3 多层依赖，App轨 | Native84/Host26/AppWeb67/NativeAppWeb151/App177；规则策略固定 | S08 App预测/事件、抽取前遮蔽记录 | 相同样本分母的召回/误报/覆盖变化 | Fig.3补充、Table.2/3 | 本方法依赖哪些输入；不是最佳单端对手比较 |
| E3 跨端覆盖，MTC轨 | P6 App177/Full244_no_cross/Full244 | P6 results、matrix_summary、paired_comparisons；S08复用索引 | 组等权可评估/未知/不适用、差异记录/组、成对变化 | Fig.5、Table.2 MTC分块 | 直接复用P6；可报告46.57→55.30与3→11，不能改称recall/FPR或8个攻击 |
| E4 语义与去重 | 最终策略和单因素诊断变体 | S09 predictions/rule_events/变化原因表 | 真值可用时误报/召回/弃判变化；score inflation、重复引用 | Table.3、Fig.4补充 | 门控贡献与来源删除分开；阈值1去重不改变二值报警是允许的结构结果 |
| E5 缺失/边界 | 配置/环境全分层；自然App-only/partial；固定合成遮蔽 | S10 boundary_results；P6 repeat_results | 覆盖/弃判、未恢复/无效应、可辨识边界；重复状态变化 | Table.1/2、边界附录 | 自然失败与合成缺失分开；不称未知设备/未知攻击族泛化 |
| E6 成本/解释 | 冻结输入，预定重复和硬件；程序引用核对 | S11 timing_samples、explanation_audit | median/P95、阶段计时、引用支持/违规/未核验 | Table.2/3、成本附录 | 离线成本与解释忠实性；P6一次计时只是历史参照，不是手机延迟 |
| 操作权衡 | 主策略与事前冻结离散条件；独立校准另议 | 同一冻结eval集真实预测 | 对照FPR×TPR并标coverage和n | Fig.6 | 只画实际操作点；无校准不画优化ROC；不将零观察误报写成总体0 |
| 样本可信度 | 原始候选→完整性→事实等级→准入，各档不丢 | inventory/facts/exclusions/failures/group registry | 包/三态/阶段/环境组分别计数 | Table.1 | 54/15/18只是D基线预期，本地准入数量以S01为准 |

Fig.2覆盖全部配置或使用S05预定的固定排序分面，不在结果后挑成功案例。Fig.3的0检出、弃判、失败、无合格标签使用不同符号。Fig.4同时呈现检测重叠与正常对照误报重叠；联合非OR时另列联合新增/取消。Fig.6稀疏样本画离散点，标明相关试验数量，不平滑出不存在的精度。

所有图表以保存的真实长表/历史结果生成；SVG/PDF为论文主产物，CSV/JSON为源表，PNG可做预览。字体、单/双栏宽度、色盲友好配色、线型和区间单位由S04定义，S12检查。不手填理想数值。正收益、零增益、负收益都输出同样完整的表格；负结果进入失效机制与适用边界，修改方法另起v2。

## 4. 步骤总表、依赖与最短主线

| ID | 名称 | 依赖 | 主要验收产物 | 对应实验 |
|---|---|---|---|---|
| S01 | 最小材料核验、事实准入与环境分组 | 无 | 01_admission台账、事实等级、缺件/关联表 | E1/E2/E5 |
| S02 | 三态App177与对照兼容适配 | S01材料结构已确定；不要求所有标签已补齐 | 02_inputs盲化输入/映射、合成测试 | E1–E5 |
| S03 | 来源、语义适用性与证据家族台账 | 无；可与S01/S02独立推进 | 03_registry来源/角色/门控表 | E2/E4 |
| S04 | 最小决策策略、评估合同与防泄漏实现 | S02、S03 | 04_contract策略/schema/评估器、合成验证 | E1–E6 |
| S05 | 运行前协议与版本冻结 | S01–S04 | 05_freeze协议、精确矩阵、分母及版本绑定 | 全部 |
| S06 | E1三态与无攻击对照主运行 | S05；相应标签/三态准入满足 | 06_e1真实预测、事件、指标 | E1 |
| S07 | E2四来源与混合来源八条件 | S05；通常S06后执行，但不按其效果调策略 | 07_e2来源预测、增量与重叠 | E2 |
| S08 | E3输入比较与P6保存结果复用 | App分支S05；P6导出分支可独立 | 08_e3输入结果、P6复用清单/源表 | E3 |
| S09 | E4语义、未知和去重诊断 | S05；对照S06冻结版本 | 09_e4单因素结果与变化原因 | E4 |
| S10 | E5自然缺失、边界与重复观测 | S05；复用S06–S09可用结果及P6 | 10_e5全配置/失败/缺失表 | E5 |
| S11 | E6重复计时与解释忠实性 | S05；已保存的S06/S07结果 | 11_e6计时样本/解释核对 | E6 |
| S12 | 图表、论文表述与复现包 | 各被引用步骤真实产物；缺支线可明确缺项交付 | 12_release六图三表/claim ledger/复现说明 | 全部 |

**最短实验主线：S01 → S02，与S03会合 → S04 → S05 → S06 → S07。** S03不应被缺日志卡住；S08的P6复用也不被攻击标签卡住。S07为独立授权步骤，不因S06完成自动启动。完整论文路线再执行S08–S12；没有标签的分支可以生成材料/覆盖描述，但不得生成需要真值的TPR/FPR。图表缺少对应正式结果时标NOT_EVALUATED，不用模拟值替补。

所有步骤的状态语义：`PENDING_AUTHORIZATION`未授权；实施后可为`DONE/PARTIAL/BLOCKED`，失败过程保留。仅授权并完成验收后才能标DONE。科学负结果不是BLOCKED；工程实现错误与材料缺失分别记原因。

## 5. 冻结合同与默认决策

### 5.1 三层证据与两条评价轨

1. **材料完整性**：文件存在、引用可解、session/payload绑定、状态键、run/receipt一致，输出 validator_status；不接触报警结果。
2. **事实/标签核验**：execution、observable_effect、rollback、no_intervention、环境关联分别给证据与状态。原manifest标签保留为原始声明，另建裁决字段；不覆盖原数据。
3. **检测性能**：仅在前两层事前准入固定后运行，预测保存后再与事实连接。

事实等级建议：`L2_RAW_LOG_CORROBORATED`（引用原日志可复核且绑定成立）、`L1_RECEIPT_SUPPORTED`（run/原始效应/恢复/回执一致但私有日志不全）、`L0_ANNOTATION_ONLY_OR_INCOMPLETE`、`CONFLICT`。等级描述证据可复核范围，不等于签名认证或独立现场见证。各事实同时用`SUPPORTED/REFUTED/UNKNOWN`，不能仅凭包级PASS生成SUPPORTED。

等级逐execution/effect/rollback/no_intervention事实评定；上面L1中的恢复一致仅适用于恢复事实本身。恢复失败或UNKNOWN不使已支持的execution/effect整体降档，也不取消其`eligible_detection`；检测、恢复与阴性资格分别裁决。

默认主分析可纳入L1/L2中经S01独立于检测器核对、可支持相应事实的记录；论文称“材料支持的受控干预/无干预对照”，保留 `independent_attestation=false`。若关键执行或无干预事实只有声明且无法支撑，则相应记录不进入TPR/FPR真值分母，仅描述报警。L0/CONFLICT单列；不可将15个缺件三态记成FN，也不能从材料流图抹去。对支持等级分别报告，不等新采购或无限补日志。

攻击准入依据当前干预效应与执行归因，不以未来恢复成功强行筛选主召回。分别冻结 `eligible_detection`、`eligible_triplet`、`eligible_pre_control`、`eligible_post_control`、`eligible_temporal_control`；post标签只有撤销/无残留事实支持才可作为阴性。三态分母按阶段齐备和可解释事实预定，恢复失败/未知另列，不能在结果后删掉。当前既有校验器偏向已恢复的成功包，故材料选择效应必须披露；主结果不能推广到所有工具尝试。

MTC全部保持未标注参考。不得拼接无关Browser制造攻击paired244，不训练MTC正常/模拟器攻击域分类器。Native仅是本次声明干预未修改的相对参照，不是可信硬件根。

### 5.2 版本化最小策略：推荐policy-v1

**S03-R v2 修订说明：**以下 policy-v1 为原设计记录。后续单独授权的 S04 应采用 `formal-manipulation-relation-risk-attribution-v2` 的 A/B/C 分离合同及统一研究范围；修订理由、候选与不可评估主张见 [版本化修订说明](S03_R_CONTRACT_REVISION_v2.md)。S03 v1 产物和原零候选验收保留；本修订不启动 S04。

**S04 实现记录：**已按外审通过的 v2 接入完整原链和独立风险层。接口与比较定义见 [S04 v2 实现说明](S04_CONTRACT_IMPLEMENTATION_v2.md)。当前 v3 的去门控角色投影仅为关系诊断；其合法风险视图与 final 共用 v2，不作为第三个独立检测器。原 policy-v1 条文及旧执行记录保留为历史记录。

保留所有关系检查及其原outcome，另设 `ManipulationDecision`。`source_lane`、目录ACTIVE和`COUNTEREXAMPLE`都不自动授予报警资格。

S03逐ID建立 `decision_role = alert_candidate / observation_only / context_only / collector_consistency / deployment_policy`；每条alert_candidate必须有当前会话可执行适用条件、允许反例和威胁模型理由。推荐小白名单候选如下，**不是已实现或已验证的报警规则**：

| 候选家族 | E候选 | O_u候选 | 必要约束 |
|---|---|---|---|
| model_app_ua | NW-001 | 无 | 明确model-before-Build token；缩减K、掩蔽、别名不明不比较 |
| app_os | NW-002 | OFFDER-OS-001 | Native和App UA可解析；同一UA reduction/产品适用门控；不把Android 10; K当真实OS |
| model_system_agent | NVW-001 | 无 | 明确Dalvik/System agent语义且模型token可比较；不能把可变http.agent当当前JS UA |
| host_os | NVW-002 | OFFDER-OS-002 | 只比较明确Dalvik/合法host来源的可解析版本；合法覆盖无法排除则观察 |
| native_app_gpu_family | NW-005 | OFFDER-GPU-001 | 明确可比较的Native硬件族；软件/掩蔽/未知/正常host rendering不报警；ANGLE字符串本身无效。覆盖层合并同源family而不改历史目录 |

如果某候选的必要反例排除条件无法从当前允许字段判断，S03必须降为observation_only或门控为UNKNOWN，不得利用攻击配置、阶段、执行日志补条件。上述家族仍是声明威胁模型下待评价的操纵线索，不是真值；有合法反例/误报要保留。角色最终表在S05前固定，只能根据语义/代码/合成边界修订，不能看新正式预测挑规则。

默认不投票：Bridge缺失；ADB/debug/cleartext/模拟器/测试环境；旧APK部署不符；touch=0；合法自定义UA导致的default/settings差异；屏幕尺寸/DPR可能的多窗口/zoom；内存近似、传感器/拷贝/解析自洽；普通跨容器差异。`NW-006/WVWEB-004/OFFDER-UA-001`等桌面/脚本UA外观有合法覆盖反例，默认仅观察，除非S03可从允许证据明确限定条件。H14可能没有可报警角色；这应事前披露，不把之后八条件相同误称为实验发现“H无用”。

确定性逻辑：

- verifier通过、适用条件SUPPORTED且所需字段可用的候选家族才可评估；同family规则用OR归并，但不要求不同表达式完全等价。
- `score = distinct eligible families with qualifying contradiction`；**一个**符合上述条件的家族即 `MANIPULATION_ALERT`，阈值固定1，无权重/搜索。理由是单字段干预可只产生一个独立线索，任意要求两票会预先排除它；限制由证据资格和语义承担。
- score=0且至少一个alarm-capable家族可评估：`NO_ALERT`，并报告partial_coverage及未知家族，不意味着安全。
- 没有可评估的报警家族或合法证据不足以确定适用性：`INSUFFICIENT_EVIDENCE`；解析/运行异常或verifier不通过另记FAILED，不能伪装NO_ALERT或普通弃判。
- C-only/B0无报警家族，默认弃判、决策覆盖0。若需要always-no-alert参考，必须独立命名，不能偷改B0含义。

输出 `decision_schema_version, policy_version, alert_score, decision, reason_codes, evaluated_family_count, eligible_family_count, triggered_family_ids, unavailable_family_ids, partial_coverage, verification_valid`；`calibrated_attack_probability=null`。原runtime的relation decision保持原样。

**预先确定的零效应**：在阈值1的OR策略下，取消去重不改变二值报警，只会膨胀score/引用数量。E4必须如实报告，不改成阈值2制造收益。来源共享的app_os/host_os/GPU等不能多票。

### 5.3 来源消融与语义消融

按当前目录核对：E=23 `device_mined_rule`；O=23 `official_derived_semantic_rule`；C=11（6 collector consistency、3 collector context、2 deployment）。O中14条标记经验筛选，O_u=9；E内部也有仅上下文角色。来源分类与决策角色是两列，不能用E/O数量代表判别力。

`source_registry.jsonl`最少包含：`rule_id, catalog_version, original_source_lane, provenance_group(E/O_u/H/C), semantic_origin, official_document_id, official_document_version, source_url, project_assumption, empirically_screened, screening_scope, tolerance_source, discovery_split_ref, dependencies, original_evidence_family, decision_family, applicability_id, decision_role, known_counterexamples, rationale, review_status`。没有证据的来源版本写UNKNOWN，不补造引用。O_u只是“未标记本轮经验筛选”，不是纯官方真理。

四来源条件C/E/O/EO与八组合 O_u/H/E（C固定）均按精确ID生成；四来源中的B0/E/O/EO已分别对应八条件的000/001/110/111，只运行唯一条件，保留映射，不重复当独立样本。主线是固定策略删来源，阈值、容差、公共门控、输入和分母不变。删除官方派生谓词后公共语义门控仍在，因此只是来源分组消融。UA reduction、未知、去重、原始等值诊断另为E4。

各变体独立校准同一报警预算属于另一协议/版本。当前共享环境少且历史暴露，默认`NOT_RUN_NO_INDEPENDENT_CALIBRATION`；不设置无限网格、不在测试集挑阈值，也不阻塞主线。真要做须另授权，先固定共同校准分组、评价分组、覆盖约束和预算再运行。贡献百分点/交互可作为附录，不做负贡献也强凑100%的饼图。

### 5.4 推理与评估隔离合同

新输入适配器只输出当前会话的 `features/field_status/field_quality`，及运行时要求的固定schema。App轨无browser、pair或真实session/install/group/phase/config字段。opaque sample ID只由调度器持有，不能在规则/卡片/策略正文中使用；原始文件名和路径只留评估映射。

允许的指纹UA等即使包含Headless词也是观测值，不为“去泄漏”删除真实特征；禁止的是标签/工具/config/运行元数据伪装成特征。`collection_manifest.runtime_context`、manifest、expected_mutations、receipts、日志、未来post全隔离。MTC的pair binding仅由既有准入层产生，不把来源身份当检测特征。

预测worker只接受盲化输入与冻结策略，不读facts目录；先落盘关闭预测文件并登记完成/失败，再由评估器连接三态、环境和标签。需要的防泄漏测试包括：只改/置换标签与phase/config/工具名/路径不改变推理投影和预测；只改未来post不改变pre/active；同内容不同路径一致；遮蔽层的值/状态/质量/派生事实全部消失；raw中capture/control标记不能穿透allowlist；日志和facts故意不可读仍可预测。

### 5.5 保存格式从S04开始固定

所有长表带 `schema_version, study_version, run_id, protocol_digest`。键唯一；失败也占预定单元。表中的样本/variant连接键是调度器落盘附加，检测器不得通过ID推理。

| 文件/位置（均拟新增） | 关键字段与用途 |
|---|---|
| `R/01_admission/material_inventory.jsonl` | bundle_ref、manifest/raw/run/receipt引用、完整性状态、候选阶段数；包括空包/不完整包 |
| `R/01_admission/facts_and_eligibility.jsonl` | raw_session_ref、payload绑定、triplet/phase、原标签、execution/effect/rollback/no_intervention分项、证据引用/等级、裁决状态、各任务eligibility、独立见证状态；仅评估侧 |
| `R/01_admission/environment_group_registry.json` | group_id、成员、安装/稳定键/设备alias/批次关联边及证据、未知项、保守合组规则；不能从检测分数分组 |
| `R/01_admission/exclusions.jsonl` | 候选对象、准入前reason、影响任务、证据级别；缺材料与字段无效分开 |
| `R/02_inputs/input_manifest.jsonl` | opaque_id、输入文件引用、适配版本、字段数、源payload绑定；仅调度器可见原路径映射 |
| `R/02_inputs/inference_inputs.jsonl` | opaque_id外部封套+只含当前字段的payload；worker只收payload |
| `R/02_inputs/evaluation_index.jsonl` | opaque_id↔session/triplet/phase/config/tool/environment_group/release/cohort；独立评估侧表 |
| `R/03_registry/source_registry.jsonl` | 上述来源、家族、角色、适用性和来源不确定字段 |
| `R/<step>/predictions.jsonl` | opaque_id、variant/input_view、execution_status、policy/catalog/adapter版本、score、decision、reason、family数、coverage、verification、timings；不含标签、工具、阶段 |
| `R/<step>/rule_events.jsonl` | opaque_id、variant、rule_id、原outcome、source_group、required/used_fields、field状态、family、gate状态/原因、decision_role、是否参与报警；全ACTIVE事件，不只留触发项 |
| `R/<step>/failures.jsonl` | unit_id、stage、error_type、reason、retry_of、是否产生预测；不得吞掉异常 |
| `R/<step>/abstentions.jsonl` | 可由预测确定生成：unit_id、reason、不可用/不适用家族、输入视图 |
| `R/<step>/metrics.json`及`metrics.csv` | experiment/variant/stratum/cohort/evidence_grade；positive/negative/triplet分母，TP、NO_ALERT、ABSTAIN、FAILED，FP、010、coverage、宏平均、区间方法/可估性、版本 |
| `R/<step>/run_manifest.json` | 预定单元、开始/完成/失败、源码输入版本、输出文件、运行环境、resume/retry关联、实际调用次数 |
| `R/12_release/figure_data/*.csv`、`figures/*.{svg,pdf}`、`tables/*.{csv,md}` | 只从上述保存结果及P6导出生成；每图登记source rows、分母、版本和过滤条件 |

评估后联合表放`R/<step>/evaluation_joined.jsonl`，不能回喂worker。P6导出的outcome-only长表须额外 `origin=P6_SAVED_OUTPUT`、`detail_status=NOT_RECORDED_IN_P6`，不伪造新rule_events。

### 5.6 分母、统计与失败处理

- 候选/完整/准入/执行/有决定是不同分母；包数、三态数、阶段数、配置数、环境关联组数同时保留。
- 主TPR=`alert_positive/N_eligible_positive`，正例弃判与运行失败仍留分母；同时列`FN_no_alert/abstain/failed`，不把程序失败解释成规则反例。存在失败时主结果标INCOMPLETE，并报可识别上下界；不能只展示成功子集。
- 主对照FPR=`alert_verified_control_mid/N_verified_control_mid`；另报全部无攻击三时点以及attack clean_pre/clean_post各自k/n。弃判不是TN；同时报告阴性decision coverage和conditional FPR，不能靠弃判换低FPR。对照不因配给多个攻击配置而复制扩充n。
- 阴性运行失败时FPR也标INCOMPLETE；在固定阴性分母N上同时给出`FP/N`至`(FP+failed_negative)/N`的可识别范围，不能把失败隐含当TN。正例失败对应主TPR的`TP/N`至`(TP+failed_positive)/N`范围；弃判是已观测的策略输出，另报而非假装未知运行结果。
- 010只有精确`NO_ALERT→MANIPULATION_ALERT→NO_ALERT`成功；任何弃判/失败不算0，分母是冻结准入三态全体。另列报警后的恢复率及其明确条件分母，不能替代010。
- `s(active)-s(pre)`与control的`mid-pre`按事前环境/批次映射比较；无法合理配对就分层展示，不按分数寻找相似control。
- 配置宏平均每配置等权；环境宏平均先组内再组间。micro session结果只是描述。同三态和关联配置不拆分作独立设备；缺分组证据时保守合并并标unknown。
- 主线优先完整k/n和差值。当前环境过少，不给伪精确的总体置信区间；配置3次重复只展示计数。可选条件组bootstrap仅在S05预先注明足够重采样组时运行，固定2000次、seed=620260923，注明有限组条件性；不足不估。
- MTC组等权口径沿用P6；无真值时仅覆盖、差异、unknown、上下文、not_applicable。654/11/6等分类不能相加称为独立设备；精确连接方式沿用P1索引。
- 零次误报只能写`0/n observed`；相关session不代入独立二项上界。实验类比例不等于线上先验，precision/F1/accuracy只作次级且有标签适用范围；无自然基率不推业务precision。
- 冻结后错误修复保存原失败版本、原因和新run_id；规则/门控/阈值或准入改变必须v2。允许同版本只恢复尚未执行单元，不能覆盖失败或挑最好一次。性能负结果、未恢复、结构性零增益都继续分析出图。

## 6. 每步详细实施与验收

### S01 最小材料核验、事实准入与环境分组

【步骤 ID 与名称】S01 最小材料核验、事实准入与环境分组

【目的】建立与检测结果独立的输入、事实与关联组，支持E1/E2/E5，明确哪些材料能用于检测、误报、恢复。

【前置依赖】无。当前A原材料存在，可开始。缺15日志只阻断相应较低证据包晋级；无需等待它们完成全部工作。

【输入】D四文件；A矩阵说明；23完整及2不完整attack manifests、6control manifests、各包raw/run/receipts、被引用日志；`A/execution_log/tools/verify_attack_run_bundle.mjs`、`verify_no_attack_temporal_control_bundle.mjs`及其静态依赖。

【复用内容】复用两个只读校验器和现有payload/字段效应/恢复检查；不重新实现所有完整性逻辑、不运行攻击侧机制检测器，不继承其旧性能结论。

【具体任务】

1. 开始时重读Git状态及校验器副作用，固定本轮材料路径映射；只运行上述两个材料校验CLI，按bundle保存stdout/stderr/returncode到R，不能运行attack runner或论文评价器。
2. 对D中每包做存在性、阶段数、引用一致性对照；记录15日志、私有原日志和2不完整包，已撤销/重跑材料均保留历史关联，不依据报警选择版本。
3. 逐三态核验session↔raw、execution、expected字段效应、post恢复，保留`original_label`与独立裁决；无攻击control仅按其执行/效应/回执事实核验，原`verified_control`不自动升级。
4. 以安装标识、稳定键、设备manifest alias、run/批次链接做传递合组；同API不自动视独立；API36跨alias同install必须合并。未知物理身份留UNKNOWN。
5. 输出准入理由、证据等级、分任务eligibility与最小人工事实队列，冻结后不再按预测修订。此步不计算报警、TPR/FPR。

【拟新增／修改内容】拟新增 `N/admission.py`、`hybridguard_agent/scripts/prepare_formal_manipulation_inputs.py` 的admission子命令、`hybridguard_agent/tests/test_formal_manipulation_admission.py`；只写`R/01_admission/`。不改A校验器、原manifest或日志。

【关键决策】采用5.1证据等级；当前18PASS只是候选预期。缺原日志可保留L1且披露证据上限；关键事实无法确定则仅该任务不可准入。分组优先保守合并，不能把包/重复三次当设备。

【输出产物】`material_inventory.jsonl`、`validator_results.jsonl`、`facts_and_eligibility.jsonl`、`environment_group_registry.json`、`exclusions.jsonl`、`missing_materials.jsonl`、`manual_fact_queue.json`、`VALIDATION.json`、`STEP_REPORT.md`，均在`R/01_admission/`。

【验收标准】全部29完整候选包与2不完整包均有去向；manifest/raw引用可审计，不能默丢行；每个准入样本有独立事实理由和环境组；等级/准入完全不依赖检测器；验证器结果与D差异有解释。聚焦测试仅合成：缺引用、重复session、错payload、恢复失败、control被误标positive、同install跨alias合组；不跑性能。

【失败处理】校验器实现错误保留异常并停相应核验；缺材料降档/阻断该事实；无可观测效应或恢复失败按真实状态登记，不视为检测漏报。没有可核验对照时FPR分支阻断，适配/来源和P6复用可继续。

【停止点】保存材料核验、剩余事实清单及状态后停止，等待授权。

【后续调用指令】`执行 S01`。

### S02 三态App177与无攻击对照兼容适配

【步骤 ID 与名称】S02 三态App177与无攻击对照兼容适配

【目的】把旧App177材料送入当前确定性链，同时保留三态和无攻击对照给独立评估器；对应E1–E5。

【前置依赖】S01材料定位/结构部分完成；个别标签仍UNKNOWN不阻止适配，但不能提前计算性能。原始字段无法绑定只阻断对应样本。

【输入】S01 inventory和raw引用；`scripts/run_mtc_p6_history.py::legacy_row`、`evidence/paired244.py`、`schemas/expanded_v2.schema.json`、现177字段CSV；旧input-set及P6 historical diagnostic用于兼容事实参照。

【复用内容】保留legacy_row的flatten/alias映射、六状态、quality和deviceMemory/cores=0哨兵；当前raw明确177状态，不笼统宣称格式无法使用。

【具体任务】新增三态/control loader，支持`clean_pre/attack/clean_post/control_mid`的评估侧映射；检测侧只输出当前字段。检查状态键集合精确一致而非仅len=177、别名冲突、类型/非有限数；不从值补observed。保留合法false、touch=0、空列表，不统一当缺失。建立opaque ID与原路径的外部映射。对真实材料仅做转换/结构检查，不调用规则和策略；对合成夹具测试完整推理投影边界。

原始连接字段明确为：攻击`session_id`、`pair.pair_id/pair_role/sequence_index`；对照`triplet.triplet_id/control_role/sequence_index/round`。`attack.execution_status/feature_effect_status/observed_mutations/success_evidence/rollback_status`和`annotation_effects.*`只进入facts。复用`normalize_payload`处理flat/nested；两形状同时存在且值冲突时拒绝并记录，不静默择优。

【拟新增／修改内容】拟新增`N/adapter.py`，扩展拟新增prepare脚本的adapt子命令；新增`tests/test_formal_manipulation_adapter.py`；写`R/02_inputs/`。不修改P6历史脚本、原字段目录或APK。

【关键决策】复用现v2 observation外形但注明`adapter_version=app177-triplet-adapter-v1`；App轨无pair/browser字段，不推造244。capture/control runtime_context、collector/install/session、文件名、阶段和tool全部留评估侧。允许同内容多session并保留不同评估单元，不能因payload重复删除对照。

【输出产物】`inference_inputs.jsonl`、`input_manifest.jsonl`、`evaluation_index.jsonl`、`adapter_rejections.jsonl`、`field_mapping.json`、`VALIDATION.json`、`STEP_REPORT.md`。

【验收标准】S01每个候选阶段恰好转换或明确拒绝；三态/control索引不丢post；盲化payload只含allowlist。合成测试验证隐藏层值/状态/quality/派生摘要清除；元数据置换不改投影；真假/0/空列表/无状态的边界正确。真实材料此步没有任何新预测。

【失败处理】适配bug修复合成夹具后再转换；源状态缺失保留拒绝，不猜值；历史P6结果不因新适配失败被重写。

【停止点】完成转换和聚焦验证后停止。

【后续调用指令】`执行 S02`。

### S03 来源、混合来源、语义门控与证据家族

【步骤 ID 与名称】S03 来源、混合来源、语义门控与证据家族

【目的】回答E2/E4所需的真实来源归因与决策资格，不把引用数或规则数当贡献。

【前置依赖】无，可独立执行；不需要攻击预测或补日志。若来源证据无法核实，标UNKNOWN，只限制相关归因/角色。

【输入】`config/paired244_rule_catalog.v3.json`、`paired244_browser_relations.v3.json`、`deterministic_rule_predicates.v1.json`、`official_semantic_relations.v1.json`、`mtc_p3_semantic_sources.v1.json`、`paired244_review_sources.v1.json`、P3语义审查、P6 SOURCE_COVERAGE/SOURCE_OVERLAP，实际谓词和采集字段代码；A week10 ledger只作独立命名空间参照。

【复用内容】87目录/57ACTIVE、E23/O23/C11、O内14筛选标志、现evidence_family和引用；复用已有UA/GPU/provider解析，不重挖数据或新增批量规则。

【具体任务】逐ACTIVE ID核对来源/项目假设/经验筛选/容差来历与依赖；形成E/O_u/H/C精确清单。逐候选建立5.2报警角色及当前字段可执行门控，尤其App UA reduction、Dalvik、GPU软件fallback；将OFFDER-GPU与相关GPU线索的共享证据显式关联，保留原family列。建立家族共享图，区分完全重复、相关但不等价。按语义阅读必要的一手官方资料并冻结版本/适用产品；找不到存档则标来源缺口，不无限全网审计。

【拟新增／修改内容】拟新增`K/source_registry.jsonl`、`K/family_registry.json`、`K/applicability_policy.json`、`K/decision_roles.json`；`N/provenance.py`及`tests/test_formal_manipulation_registry.py`；复制审定表到`R/03_registry/`。不改原v3目录或P3结果。

【关键决策】来源、语义门控、decision_role三者正交；O_u不叫纯官方。推荐5.2小白名单，不能核实必要门控的候选降为观察；不依据已知历史攻击命中补规则。保留“官方语义可能取消不成立推断”的研究假设，不承诺必定降低误报。

Chrome独立Browser与Android WebView的UA reduction适用版本必须分别核实，不能把现Browser关系的`>=107`机械复制到App。P6旧来源选择未固定包含C，本轮C+E/C+O需从精确ID重新声明，不能只给P6条件换名字。

【输出产物】完整source/family/applicability/roles四表、`source_overlap_matrix.csv`、`source_uncertainties.jsonl`、`SEMANTIC_DECISIONS.md`、`VALIDATION.json`、`STEP_REPORT.md`。

【验收标准】57ACTIVE恰好分组一次，E=23、O_u=9、H=14、C=11或明确解释任何真实版本变化；每条角色有理由/反例/适用字段；同源家族不会因来源不同重复计数；未知来源版本未造假。测试只查ID闭合、字段已注册、来源八组合和家族合并边界；无真实预测。

【失败处理】台账不一致阻断该来源比较；必要门控不可实现则降角色并披露结构性覆盖损失，不以扩大警报集合凑结果。其余来源可继续，缺官方文档不引入LLM替代事实。

【停止点】提交可审阅的版本化台账后停止。

【后续调用指令】`执行 S03`。

### S04 决策策略、评估合同与防泄漏实现

【步骤 ID 与名称】S04 决策策略、评估合同与防泄漏实现

【目的】实现关系状态之外的最小报警层和可复现评价/绘图数据接口，对应E1–E6。

【前置依赖】S02、S03完成；报警候选、门控和family可执行。标签尚不足可以用合成夹具开发，不能借正式样本调参。

【输入】S02映射/schema、S03台账；当前runtime/rules/retrieval/verifier、`research/mtc_p6.py`纯汇总思路；本计划5.2–5.6合同。

【复用内容】完整原确定性链、原Verifier与卡片；单独包装策略，不去掉其NOT_EVALUATED保护。采用已有依赖和本地JSONL/CSV，不引入数据库/服务或训练平台。

【具体任务】实现policy-v1和独立验证器；实现预测worker与离线join/metrics的不同入口，schema拒绝泄漏；保存全部规则事件。实现legacy规则基线/current-v3关系角色策略/final门控联合策略的精确定义：旧19已编译检查保留旧谓词/诊断状态、使用同一外部家族决策骨架；原短路输出只作附录诊断，不能把其旧风险分数直接当报警。当前与最终差别仅列出的新语义门控，命名清楚、不可假称独立SOTA。建立全矩阵和图表manifest格式；评价函数用手算合成010、误报、弃判、缺post、运行失败案例验收。

【拟新增／修改内容】拟新增`N/policy.py`、`N/verification.py`、`N/runner.py`、`N/evaluation.py`、`N/reporting.py`；`K/decision_policy.json`、`K/variant_plan.json`、`K/figure_spec.json`；`hybridguard_agent/schemas/manipulation_decision_v1.schema.json`及长表schema；`hybridguard_agent/scripts/run_formal_manipulation_eval.py`和`plot_formal_manipulation_eval.py`；聚焦`tests/test_formal_manipulation_policy.py`、`test_formal_manipulation_evaluation.py`、`test_formal_manipulation_leakage.py`。模块名为拟新增，具体小文件可在本步内合理合并，但接口/边界不变。

【关键决策】阈值1，按eligible family去重；B0弃判；无校准概率。legacy-v3比较明确是规则版本基线，来源四组固定同最终门控策略。语义移除为机制诊断，不能当强基线。评估标签只在预测保存后join。

【输出产物】`R/04_contract/`下schema、policy、variant/figure spec、合成夹具预期与真实测试输出、`LEAKAGE_VALIDATION.json`、`METRIC_VALIDATION.json`、`STEP_REPORT.md`。此步不得产生正式样本predictions。

【验收标准】合成单线索报警、同家族双规则不加票、合法缩减UA/软件GPU/来源不足处理正确；篡改结果/字段引用失败；全部5.4泄漏测试通过；手算分母与汇总一致；故意失败仍保留预定单元；图表接口能消费合成测试输出，但测试图不得当论文结果交付。不扩展为全项目测试。

【失败处理】实现/指标错先修夹具与源码；必要字段不足按UNKNOWN/observation处理。无足够报警角色也如实保留策略边界，不临时改阈值或查看正式效果选方案。

【停止点】实现和合成验证完成即停止，仍不运行正式输入。

【后续调用指令】`执行 S04`。

### S05 运行前协议、版本、输入、比较与指标冻结

【步骤 ID 与名称】S05 运行前协议、版本、输入、比较与指标冻结

【目的】在正式预测前固定研究自由度和全部图表分母，对应所有E。

【前置依赖】S01–S04完成其相关分支；每个拟报告TPR/FPR的样本有独立事实与准入。缺标签的支线可标NOT_EVALUATED并从性能矩阵声明关闭，不能自动补标签。

【输入】前四步产物、Git状态、相关源码/依赖版本、P6原协议与访问记录、本计划图表映射。

【复用内容】保留P0–P6规则/样本/分组/访问记录；沿用拒绝覆盖的产物习惯，不重新切MTC保留集。

【具体任务】固定候选/排除/各eligible任务分母，配置/机制/API/关联组、对照匹配；冻结policy/source/family/applicability、legacy与v3条件、八来源唯一条件、输入视图、E4诊断定义、E5缺失夹具/E6计时抽样、指标/区间/图表spec。将真实输入与评估侧表分目录；对参与本轮的精确源码/小配置/输入绑定做一次清单，不全库重哈希。保存原暴露史、未解决事实和允许/禁止读取列表。运行前预定每个(unit,variant)并输出只含ID/数量的dry-plan，不运行检测。

【拟新增／修改内容】拟新增`hybridguard_agent/scripts/freeze_formal_manipulation_protocol.py`、`K/protocol.json`；写`R/05_freeze/`，复制相关源码到其`frozen_sources/`。不改历史freeze/access。

【关键决策】study_version=`formal-manipulation-v1`；主分析固定策略、无训练/校准/模型；攻击轨暴露材料回放评价，MTC沿P6保存输出，不声称新盲测。固定E4四诊断：去UA reduction门控；未知被当可比的显式诊断模式；重复计票；原始无条件等值模式。后两种非原链行为必须明确合成机制诊断，不能伪装历史实现。

【输出产物】`protocol.json/.md`、`FREEZE_MANIFEST.json`、`expected_units.jsonl`、`variant_registry.json`、`metric_spec.json`、`figure_spec.json`、`exposure_history.json`、`evaluation_access_policy.json`、`VALIDATION.json`、`STEP_REPORT.md`。

【验收标准】每条件有精确ID/角色/门控/阈值；唯一单元数可重建；所有任务分母可由S01侧表生成；冻结源码和配置可追溯工作区差异；prediction产物仍不存在；没有未经说明的可调参数。冻结验证只查manifest/schema/集合一致性，不运行正式规则。

【失败处理】缺事实只关闭对应性能项；结构/版本不一致阻断该run。冻结后新增候选/阈值/门控/指标主定义必须另版本，不能覆盖。

【停止点】发布运行前冻结记录后停止，等待S06或其他具体授权。

【后续调用指令】`执行 S05`。

### S06 E1三态与无攻击时间对照主运行

【步骤 ID 与名称】S06 E1三态与无攻击时间对照主运行

【目的】回答报警是否随可观测干预出现、撤销后恢复，以及对照误报/弃判；只做E1。

【前置依赖】S05有效，相关检测/三态/对照标签分母非空且事实已冻结。无control标签只能报告该项不可评估，不把MTC补成负例。

【输入】05_freeze、02_inputs盲化当前会话、S01评估侧facts；三种S04定义的冻结策略版本。

【复用内容】旧19谓词/当前57关系与原runtime；复用S04 worker/评估器，不执行攻击或采集。

【具体任务】按冻结顺序执行每个阶段一次，先保存当前会话预测和全规则事件，再离线连接phase/triplet/标签。输出所有配置attack/pre/post/control的k/n、010、弃判/失败、score差；全对照54阶段与mid18阶段分别统计（最终n以准入为准），不得重复control扩分母。给出每配置失败机制与恢复分项，资源/plugins/screen等盲区不删除。

【拟新增／修改内容】只运行拟新增脚本，示例接口：`python3 -B hybridguard_agent/scripts/run_formal_manipulation_eval.py --step S06 --protocol <R/05_freeze/protocol.json> --out <R/06_e1>`。这是S04拟实现接口，不是本轮执行命令。只写`R/06_e1/`，不改规则/阈值。

【关键决策】保持原版本，所有结果含负面均接受；运行异常不自动重跑选优。无可观测干预是材料属性，不是算法漏报；可观察干预但无可区分关系是真实性能边界。

【输出产物】predictions、rule_events、failures、abstentions、evaluation_joined、metrics JSON/CSV、`triplet_results.jsonl`、`configuration_summary.csv`、run_manifest、VALIDATION、STEP_REPORT。

【验收标准】expected units全部落盘且唯一，成功或失败可对账；labels join发生在预测完成后；每条010可回溯三个独立决策；指标分母与freeze一致；无性能阈值验收。运行后只做保存结果一致性检查，不重复执行一轮验证效果。

【失败处理】实现异常保留FAILED并报PARTIAL，必要修复另技术run记录；缺材料只影响对应单元；低召回、高误报、不恢复均保存并继续后续分析，不回调策略。

【停止点】E1完整真实结果和限制保存后停止，不自动启动E2。

【后续调用指令】`执行 S06`。

### S07 E2目录来源与混合来源消融

【步骤 ID 与名称】S07 E2目录来源与混合来源消融

【目的】分解E/O联合、O_u/H/E混合来源的判别与弃判作用；对应E2。

【前置依赖】S05；推荐S06后执行以复用同版本E+O结果，但S06不是调整方法依据。若S06因基础实现缺陷不可信，先报告该具体阻塞，不能绕过。

【输入】source/family/roles台账、八唯一组合、冻结同一cohort/输入/公共门控；可复用S06完全匹配版本和输入的联合预测。

【复用内容】`research/mtc_p6.py::select_rules`的精确过滤思想；S04统一策略/评估器；四组与八组重合条件复用保存输出。

【具体任务】执行未已有的唯一来源组合；逐条件保存预测/全规则事件/家族。输出TPR、FPR、coverage、010、分组/配置宏平均；计算O|E与E|O条件百分点差、来源检出与对照误报四格。联合行为不同于OR的单元单列；H无报警角色的等同条件标structural-equivalence。全部来源ID与公共门控公开。

【拟新增／修改内容】用统一脚本`--step S07`写`R/07_e2/`；只在必要时补纯汇总缺陷且另记版本，不变更已冻结决策。新增`source_complementarity.csv`、`conditional_increments.csv`、`structural_equivalence.json`。

【关键决策】主结果是固定策略删来源；独立校准操作点默认不执行。两组引用重叠或相同family不能计为独立贡献。官方来源零新检出可能是门控/覆盖作用，也可能无收益；按数据写结论。

【输出产物】标准长表与metrics；上述互补/增量/结构等同表；`SOURCE_ABLATION_REPORT.md`、VALIDATION、STEP_REPORT。

【验收标准】全部组合使用同一准入/opaque ID集合；不改剩余规则容差/归一化/阈值；汇总可从保存预测重建；弃判和失败纳入；四组/八组映射无重复计数；负增量照样输出。

【失败处理】来源映射错属于实现错误并阻断受影响比较；缺标签不生成该性能指标；各组相同、联合下降均为可交付科学结果。

【停止点】E1+E2最小闭环交付后停止。

【后续调用指令】`执行 S07`。

### S08 E3多层输入比较与P6保存结果复用

【步骤 ID 与名称】S08 E3多层输入比较与P6保存结果复用

【目的】区分App方法对输入的依赖与MTC跨端关系覆盖，完成E3。

【前置依赖】App分支需S05；P6保存结果导出可独立授权执行。只要一分支缺依赖，完成可执行分支并标PARTIAL，不擅自补跑上游。

【输入】App冻结输入与五视图；P6 `results.jsonl`、`counterexamples.jsonl`、`matrix_summary.json`、`paired_comparisons.json`、`variant_registry.json`、repeat/source summaries及freeze/access记录。

【复用内容】`evidence/paired244.py::VIEWS`的Native84/Host26/AppWeb67/NativeAppWeb151/App177；P6 15条件的全部保存结果，尤其App177/Full_no_cross/Full244。

【具体任务】App在抽取前遮蔽，固定同一cohort和来源策略；验证隐藏字段/状态/派生值未残留。MTC仅导出已保存数据和成对组均值，保留发现/开发/保留分栏；核对13,365主行、45汇总、30比较、468偏差事件及137重复的保存结构。新导出核对逻辑写到新目录，绝不运行会覆写FINAL_AUDIT的旧审计入口。缺完整事件字段明确NOT_RECORDED。

【拟新增／修改内容】拟新增`hybridguard_agent/scripts/export_p6_saved_results.py`（只读输入、强制新out）；统一脚本`--step S08`处理App分支；写`R/08_e3/{app_input,p6_reuse}/`。

【关键决策】不重跑MTC检测器、不更换P6样本/阈值；新App对比不是最佳单端baseline；无Browser攻击不生成Full244攻击列。已有P6数值只支持关系覆盖/差异。

【输出产物】App标准长表；`p6_reuse_manifest.json`、`p6_outcomes_long.jsonl`、`p6_figure_source.csv`、`p6_comparisons.csv`、`P6_REUSE_BOUNDARY.md`；两分支VALIDATION/STEP_REPORT。

【验收标准】P6输入文件未被写入；来源版本/访问史随导出保存；Fig.5每值能追到保存结果；App共同分母和mask一致；没有把缺详情填为实际观察，没有MTC TPR/FPR。

【失败处理】本地逐行结果丢失时用仍存在的冻结汇总出受限图并标限制，缺失项目阻断而不是重跑P6；App失败照留。无输入增益不阻断。

【停止点】两分支各自如实报告完成度后停止。

【后续调用指令】`执行 S08`。

### S09 E4语义适用性、未知与证据去重诊断

【步骤 ID 与名称】S09 E4语义适用性、未知与证据去重诊断

【目的】区分官方派生关系新增与公共语义门控作用，检验未知与重复证据处理；对应E4。

【前置依赖】S05已冻结精确变体，S06同版本参考可用；无独立阴性标签不能计算误报减少。

【输入】冻结四诊断变体、同一App cohort/策略、S04合成边界；若引用MTC仅用已有P6反例，不新宣称其为误报。

【复用内容】已有UA/内存/时区/GPU解析与源状态合同；全规则事件便于定位改变的gate，保留历史v3原谓词。

【具体任务】逐一取消UA reduction、显式诊断未知处理、重复计票、原始等值解释，其他因素保持不变；合法UA缩减/近似内存/时区等价/字段失败合成案例单独列表。对每个变化事件列gate_before/after、family、标签证据及是否误报减少/漏报增加/弃判变化，不能只给总分。重复计票在阈值1下预期报警等同，报告score/解释重复变化。未知诊断不得真实改写输入为observed。

【拟新增／修改内容】统一脚本`--step S09`写`R/09_e4/`；用S04/S05冻结的诊断策略配置，新增纯结果表`gate_changed_events.jsonl`、`dedup_effects.csv`。禁止把诊断变体回写主策略。

【关键决策】未知硬当可比、删除必要保护等是机制诊断，不是强竞争baseline；单因素未实际覆盖的机制报告NOT_EXERCISED，不补造效果。去重仅有解释/分数收益时照实表述。

【输出产物】标准长表、gate/dedup变化表、`synthetic_semantic_cases.jsonl`、`SEMANTIC_EFFECT_REPORT.md`、VALIDATION、STEP_REPORT。

【验收标准】只变指定因素；相同样本/版本/分母；每项变化有保存证据；真假标签来源可追溯；合成与真实分表；零/负收益都呈现。

【失败处理】变体意外改变多因素视实现错误；样本不能覆盖机制则NOT_EXERCISED；精度召回变差是科学结果，不能调门控覆盖首轮。

【停止点】诊断结果保存后停止。

【后续调用指令】`执行 S09`。

### S10 E5边界、自然缺失与重复观测

【步骤 ID 与名称】S10 E5边界、自然缺失与重复观测

【目的】完整呈现配置盲区、自然失败、输入缺失与有限可迁移范围，对应E5。

【前置依赖】S05；App基于已完成S06–S09结果（未做的条件明确缺项），自然MTC分支依赖既有P1/P2/P6而非新标签。

【输入】S01全部候选/不完整/较低证据；保存预测；P1 App-only/partial/index、P6 repeat_results/repeat_summary；S05事前固定合成缺失集合。

【复用内容】P1自然缺失分类；P6 137重复结果，不重跑其稳定性；分组分层代码的组等权与稀疏层保留。

【具体任务】按机制/config/API/关联组/批次输出全部n，标已覆盖/未覆盖机制；较低证据15三态只作独立描述且仅在S05明确批准该描述矩阵时运行。自然App-only/partial可用同冻结策略新跑可用性/弃判，不计算FPR；同session额外观测保留连接。合成缺失限定为整层遮蔽、必要字段timeout/unsupported/quality异常，以及协调多字段相同/不可辨识夹具；不生成“真实攻击”标签。对重复变化、恢复失败、no-effect分项分析，不为负结果新增规则。

【拟新增／修改内容】统一脚本`--step S10`及S04结果汇总写`R/10_e5/`；输出`natural_missingness.jsonl`、`synthetic_missingness.jsonl`、`boundary_by_configuration.csv`、`repeat_reuse.csv`、`attempt_flow.csv`。现数据不改。

【关键决策】相同机制换客户端不叫未知族；API分层不叫跨设备泛化；物理身份未知保留。无足够独立环境不做迁移训练或交叉验证；合成边界只支持方法限制。

【输出产物】上述表、`BOUNDARY_REPORT.md`、failure/abstention明细、VALIDATION、STEP_REPORT。

【验收标准】全部配置/失败/较低证据有去向；自然与合成分母独立；P6重复不算新增独立设备；无相关标签就没有检测指标。只跑协议内掩码/缺失条件，不扩展随机大规模扰动搜索。

【失败处理】缺自然输入只阻断该可用性子表；缺标签照留描述。大量弃判、同输入不可区分、不恢复都作为边界交付。

【停止点】边界与缺失报告完成后停止。

【后续调用指令】`执行 S10`。

### S11 E6离线成本与解释忠实性

【步骤 ID 与名称】S11 E6离线成本与解释忠实性

【目的】给出可复核的运行成本和引用支持，而不是LLM自评或采集延迟；对应E6。

【前置依赖】S05计时协议和已保存S06/S07预测；解释只核对保存事件/卡片，不能借审阅调方法。

【输入】冻结输入、策略、运行环境；S06/S07事件、reason、cards、verifier；P6 RUNTIME_SUMMARY作一次旧计时参照。

【复用内容】原runtime/Verifier和机器引用检查；对全部保存解释做自动路径/版本/字段状态/角色核验，人工只审程序不能决定的语义事实。

【具体任务】按S05预定opaque ID排序抽24个阶段（不足24全取，分层规则事前固定），冷启动单列，3次warmup与20次测量；不因快慢换样本。记录解析、证据、规则、检索卡、Verifier、决策及total，Verifier内重算不得从成本删去。记录硬件/OS/Python、冷热与顺序、失败；输出median/P95与实际样本/重复数。解释全量程序核对；仅对规范含义/因果措辞未决事件建立最小人工队列，按S05预定选择规则且方法名盲化，不能让LLM自评分充当真值。

【拟新增／修改内容】拟新增`hybridguard_agent/scripts/benchmark_formal_manipulation_eval.py`，S04纯解释核对函数；写`R/11_e6/`。只增加研究包装计时，不能改predicate/主链算法。

【关键决策】计时是离线本机成本，样本重复不是独立设备；主线external_model_calls=0。人工解释无法完成时保留NOT_REVIEWED及自动证据一致性结果，不阻塞其他图表。

【输出产物】`timing_samples.jsonl`、`timing_summary.csv`、`runtime_environment.json`、`explanation_audit.jsonl`、`semantic_review_queue.json`、VALIDATION、STEP_REPORT。

【验收标准】每计时重复有原值/状态，sum与total差异可解释，冷暖分开；使用相同已冻结输入、输出与原正式预测一致（不含timing）；解释引用只能指向真实used_fields/当前rule/card，不引用缺失字段；LLM调用0。

【失败处理】环境计时噪声如实报告，不选最好次；输出不一致属实现错误，保留该run并阻断成本结论；人工未评保留未知；无成本优势是可接受结果。

【停止点】成本与解释证据保存后停止。

【后续调用指令】`执行 S11`。

### S12 图表、论文结果与复现包

【步骤 ID 与名称】S12 图表、论文结果与复现包

【目的】将真实结果转为六主图、三核心表、限制明确的论文表述和可复现材料；承接原P7尚未完成目标，不改P编号。

【前置依赖】所引用步骤的真实产物和验证记录。支线缺失允许交付标缺的部分版本；没有E1/E2真值结果不能把论文主检测结论标完成。

【输入】所有已完成步骤的保存结果、05_freeze figure/metric spec、P6导出、原资料包图表映射。

【复用内容】P6 Fig.5/来源关系/反例/重复/一次计时；旧绘图代码只复用样式，不复用旧模型结果或理想数字。

【具体任务】用拟新增绘图入口从结果长表生成Fig.1–6及Table.1–3、完整配置/较低证据/反例/缺失附录。为每图表建立source manifest和分母核对；输出`claim_ledger.csv`逐句绑定图表、条件、版本、数值、限制，明确正/零/负收益。最终论文结果段只写实际支持：互补、门控减少错误推断、仅覆盖/解释改善或没有增益均有独立路径。生成复现README、环境依赖、冻结源码/config、材料定位和运行命令；分享原始材料需另有授权，本步默认本地复现包不公开发布。

【拟新增／修改内容】完成`plot_formal_manipulation_eval.py`、拟新增`hybridguard_agent/scripts/package_formal_manipulation_reproduction.py`；写`R/12_release/`与`P/results_v1/`摘要（拟新增）。本步不修改攻击侧ACM草稿、历史P6报告或原始数据，不自动投稿/上传/commit/push。

【关键决策】图表只读保存结果，不触发检测器；策略改进另开v2，首轮保留。固定策略消融与独立校准操作点分表，未执行者明确NOT_EVALUATED。Full244真实攻击、总体零FPR、最佳单端、外部盲测、生产泛化和RAG收益不在现证据支持范围。

【输出产物】`figures/fig1..fig6.{svg,pdf}`（无数据项列缺失原因）、`tables/table1..table3.{csv,md}`、`figure_data/`、`FIGURE_MANIFEST.json`、`claim_ledger.csv`、`RESULTS_DRAFT_CN.md`、`LIMITATIONS.md`、`REPRODUCE.md`、`REPRODUCTION_MANIFEST.json`、VALIDATION、STEP_REPORT。

【验收标准】每性能数值可从冻结预测+独立facts重算；正文/表/图同分母同版本；图例区分0/未知/弃判/失败；视觉检查字号、布局、色彩和区间说明；图表生成离线重复输出数据一致且模型/检测调用为0。缺支线不伪造图片；复现包不包含无授权公开的原始日志。

【失败处理】绘图/汇总bug从保存结果修正并记版本；结果不理想仍完成分析图表；真值缺失明确限制而非写好看结论；复现依赖缺失列具体文件，不隐式调用新服务。

【停止点】交付图表、论文结果草稿和复现说明后停止；不自动开启改进版。

【后续调用指令】`执行 S12`。

## 7. 最小人工确认与阻塞范围

当前无需用户先做全面review；首先建议授权S01，由程序/现有证据完成可替代的核验。以下仅在S01无法从留存证据解决时进入具体事实队列，每项必须列bundle/triplet/payload引用：

| 需确认的具体事实 | 最小可提供材料 | 不处理时的边界 |
|---|---|---|
| 某control的三个时点确无主动注入，且未承接未清除的前次配置 | 对应run/操作者现有操作记录或可绑定session的启动/撤销日志；无需重新采集 | 仅该control的FPR资格UNKNOWN；不影响App适配/来源/P6 |
| 某receipt与缺失私有原日志之间的执行归因，或label与raw变化矛盾 | 精确引用日志/说明对应执行与payload，不要求全面评分 | 可有明确L1上限；若关键归因无支撑则描述性，不进入正例性能分母 |
| API36跨alias或重置环境的关系无法由install/稳定键/run解决 | 对应AVD/安装重置/执行批次关联记录 | 保守合组并标物理身份UNKNOWN；不给设备泛化/独立校准结论 |
| 5旧包缺的15个直接引用日志（仅希望晋级时） | D audit列出的准确automation_logs文件 | 默认较低证据附录；不阻塞18候选包主线，不要求必须补齐 |

资料包原ZIP、采购清单、新正常标签、新Browser攻击配对均不是本轮计划或最短主线前置条件。不能确认的事实不猜，不能因为已报警而升级标签。解释主观语义只留下S11最小未决项，不要求用户重新做所有历史人工评分。

## 8. 主线、附录增强与不进入本轮的事项

- **主线必需**：材料分档/标签独立、三态/对照适配、来源与角色/家族、最小策略/隔离、冻结、E1/E2、P6复用、真实图表/论文限制。
- **附录增强**：O_u/H/E完整八条件（计算量小，纳入S07）；较低证据材料描述；自然/合成缺失分开；单因素语义与去重；成本分解与解释核对；旧引擎短路差异。可分步交付，不挡住E1/E2。
- **仅另行授权的扩展**：独立校准操作点、学习权重/复杂分类器、LLM/RAG四上下文、更多对手基线、公开发布、真paired244攻击补采或新采购。都不作为主线条件，不在S01–S12自动执行。
- **明确禁止**：拼Browser造攻击、将MTC来源当正常、调结果后仍叫盲测、删除失败/弃判/不利配置、重写历史freeze、把COUNTEREXAMPLE直接等同攻击、重复证据独立投票、无限规则重构。

## 9. 本轮交付与下一步

计划编制轮仅生成本文件与 `EXECUTION_STATUS.json`；当时没有任何S步骤完成。进度文件保存两个仓库版本、资料包基线、工作区原状、逐步依赖/预期产物/验收/阻塞和`next_authorization_step=S01`。

**计划编制时的第一个建议指令：`执行 S01`。** 它会复验现有材料校验器、建立独立事实准入与环境关联台账、列出真正缺件；不会运行检测策略、正式实验、攻击工具、训练、模型、采集服务，也不会修改原始标签或自动进入S02。

### S01 执行更新（2026-09-23）

前置设计/计划已提交并推送 `4826e26`；随后按本次授权执行 S01。31 包、262 个阶段均已入台账；完整攻击校验 18 PASS / 5 FAIL，时间对照 6 PASS，另 2 不完整包保留失败。54 个攻击阶段及三态按 L1 执行回执与独立 raw 效应核对准入；前后各 54 条只取得声明干预表面的对照资格。54 条时间对照阶段的无干预事实仍为 UNKNOWN，不进入该分支 FPR。3 个环境关联组不代表 3 台已核验物理设备。13 个聚焦合成测试通过。

报告：`hybridguard_agent/artifacts/formal_manipulation_v1_20260923/01_admission/STEP_REPORT.md`。S01 工程验收完成，缺件与事实队列保留；没有检测器、性能实验、攻击工具或模型调用。S01 完成时新产物尚未提交推送，S02 尚未执行；之后的交付与执行更新见下。

### S02 执行更新（2026-09-23）

先按授权将 S01 源码、计划状态与产物提交并推送 `a68fcec`，远端 main 已确认同一提交；其他 Android/TLS/构建/日志改动保留。本地 S01 报告、VALIDATION、最终 13 项测试与依赖台账一致，无实质冲突。只清除了 S02 遗留的“依赖未执行”提示，未因远端状态覆盖本地进度，未重跑 S01 或重裁事实。

S02 全量接收 262 条原始阶段：262 成功，0 拒绝；其中准入攻击三态 162 条、较低证据攻击 45 条、时间对照 54 条、不完整尝试 1 条。69 组攻击三态和 18 组时间对照三时点的关联完整；另 1 组保留仅 clean_pre，1 个空失败包继续只引用 S01 inventory。全部阶段唯一进入成功或拒绝台账，没有按标签筛选或按 payload 去重。

复用 App177 当前字段目录与映射，完成精确 177 状态键、别名冲突、类型、非有限值、零哨兵、flat/nested 兼容和推理 allowlist 校验。15 项合成聚焦测试通过，保存后索引和关联回读通过；真实材料仅转换与结构校验，没有检测规则、报警策略、predictions、TPR/FPR 或阈值变更。54 条时间对照的 no_intervention 仍为 UNKNOWN，原准入与 3 个环境关联组不变，缺件和证据等级限制继续保留。

报告：`hybridguard_agent/artifacts/formal_manipulation_v1_20260923/02_inputs/STEP_REPORT.md`。产物与验证已保存，本地 S02 状态为 DONE/PASS。S02 改动未提交、未推送；本轮已停止，S03 未执行，只有收到后续单独授权才可开始。


### S03 执行更新（2026-09-23）

当前 HEAD 已核对为 `b3d8badee44577787bdcd3cb22d70a155b1bb613`，与用户指定外部核查版本一致。上面的 S01/S02“仍在本地、未推送”是各自完成时的推送前记录；其后已交付，不改写历史产物，不重跑 S01/S02 或重裁事实。

57 项 ACTIVE 全部且唯一登记为 E 23 / O_u 9 / H 14 / C 11。来源、applicability、decision_role 分列，O_u 不称纯官方；27 个研究家族中 9 个跨来源共享，保留原 evidence_family。公共有效域上 4 对完全重复与同族不等价关系分别记录；四来源条件和 O_u/H/E 八组合都保存精确 ID、公共 C 及同一语义门控。

15 项静态/合成聚焦测试通过，保存产物回读验证通过。UA reduction 按 Chrome desktop M107、Chrome Android M110、当前 Android WebView Android 17 文档分别记录；冻结 Browser >=107 条件的差异进入新台账，未修改 v3。Dalvik 可变属性和合法 GPU 软件/host 渲染的边界继续保留。

**本步审定报警候选 0、报警家族 0。** 计划建议的 8 条候选均因允许字段不能完整确认必要的合法覆盖/渲染路径排除条件而降为 observation_only。各来源组后续二值增量受这一结构限制，不能将零增量解释为来源无价值；也不能将全弃判当作 NO_ALERT 或零误报。当前角色是语义与字段合同审定结果，未使用正式预测挑选规则。

报告：`hybridguard_agent/artifacts/formal_manipulation_v1_20260923/03_registry/STEP_REPORT.md`。本地 S03 为 DONE/PASS，工程通过不表示检测能力或性能已经验证。S01/S02 原产物和事实限制保留，时间对照 no_intervention 仍为 UNKNOWN；无真实预测、性能计算、阈值修改或 LLM 调用。S03 未提交、未推送，S04 未执行，等待下一步单独授权。


### S03-R v2 执行更新（2026-09-23，待审查）

基线 HEAD 核对为 `66f9cdc2d40c41ccec0999c7a6c8d68c0a1b415f`。独立版本 `formal-manipulation-relation-risk-attribution-v2` 将关系适用性、限定研究风险资格、攻击归因确定性分开。七条既有候选取得有限风险资格、涉及五个家族；OFFDER-GPU-001 仍观察，其余未建议检查角色不变。合法替代解释没有改成攻击真值，真正影响测量的门控继续保留。

原 S03 的 15 项测试和新版本 17 项测试通过；35 个合成夹具通过并证明各候选的一致/冲突路径可达，归因仍 UNKNOWN。没有真实预测或性能评估，没有实现 S04 聚合器。H/C 无风险候选，O_u 的两个家族与 E 共享且在共同有效域等价；零增量的结构限制不得解释为来源无价值。

独立产物位于 `hybridguard_agent/artifacts/formal_manipulation_v1_20260923/03r_role_gate_v2/`，配置位于 `hybridguard_agent/config/formal_manipulation_role_gate_v2/`。两者在命令中同时显式指定；只换 output、旧配置目的地或非空/重叠目录现在会在写入前拒绝。原 S03 语义函数、配置、产物及测试保留。

本地 S03-R 为 DONE/PASS、AWAITING_USER_REVIEW；[合同修订说明](S03_R_CONTRACT_REVISION_v2.md) 明确后续 S04 的版本绑定和仍不可评估的主张。S01/S02 不重跑，时间对照标签限制不变。完成后停止等待审查，不进入 S04，不提交或推送。


### S04 执行更新（2026-09-24，北京时间）

审查 HEAD 为 `8d2e8d55e34fcd75a4d6f3f5b9f0834862316554`，与执行开始及完成核对一致。S03-R 外审通过单独登记；旧报告中的“未推送”“待审查”为原记录时点，不覆盖或重跑历史产物。

采用 `formal-manipulation-relation-risk-attribution-v2` 与独立 `formal-manipulation-family-or-v2`：7 条候选、5 个家族，固定家族 OR 和阈值 1。完整原 v3 的 87 项目录结果、57 项 ACTIVE、原卡片和 Verifier 保持；旧 19 项原谓词作为单独版本基线，使用相同 v2 风险门控。全部来源条件保留公共 C 与相同门控，O_u/E 重叠、H/C 无候选的结构限制不变。

预测、全部规则事件、原 runtime、失败及弃判先保存关闭；之后独立连接评估侧标签、三态和时间对照。指标保留固定分母中的弃判/失败，报告覆盖、失败区间、精确 010、配置/环境宏平均；绘图入口只导出保存结果的来源表。类型/版本/配置混用失败均不会自动变成 NO_ALERT。

35 项最终聚焦测试通过，保存 5 个合成策略边界、14 个候选/原谓词共同有效域对照，以及 14 条合成评估预测与 1,218 条完整目录事件；合成手算分母和防泄漏验收通过。初始夹具路径故障及末轮异常路径修复有独立记录。产物：`hybridguard_agent/artifacts/formal_manipulation_v1_20260923/04_contract/`。

S04 DONE/PASS 只代表实现及合成工程验收。真实样本预测、真实 TPR/FPR、阈值搜索、采集和 LLM 调用均未执行；S01 时间对照仍 UNKNOWN、不取得 FPR 资格。S05 未开始，等待单独授权；本次不提交或推送。
