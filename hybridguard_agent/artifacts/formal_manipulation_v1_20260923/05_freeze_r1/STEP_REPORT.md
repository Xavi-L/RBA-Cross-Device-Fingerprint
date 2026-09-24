# S05-R STEP_REPORT

完成时间：2026-09-24T04:13:00.074855+00:00。审查基线与当前 HEAD 均为 `595d30d690713f6ee800a7825cfe8199cee97565`。状态：本地工程验收 PASS，等待外部审查；只执行 S05-R，未提交或推送。

## 修复与继承

确认旧 `runtime_cards()` 读取三份未登记来源 JSON，AST import 闭包没有覆盖这些数据文件；旧 manifest 只能检查已登记文件。旧 `05_freeze`、配置、验收和推送前记录均未改。其静态 PASS 不等于独立运行资源完备，缺口由本修订单独记录。

新快照 `hybridguard_agent/artifacts/formal_manipulation_v1_20260923/05_freeze_r1`；新配置 `hybridguard_agent/config/formal_manipulation_protocol_v2_r1`。`freeze_revision=formal-manipulation-freeze-r1`，沿用 `formal-manipulation-protocol-v2`、`formal-manipulation-relation-risk-attribution-v2`、`formal-manipulation-family-or-v2`。原协议 code_commit/frozen_at、source_environment 和历史计划为继承时点；本次打包时间/基线/源码另列 PACKAGING_REVISION 和 packaging_environment。

- 原 digest：`d1eb5d9894ff8a9194692f8bcfdc22b7f6c603448f1f21ad8151980a3fb19d27`。
- 新 digest：`9a6cb92a5d973a42d230305e176ab9ef824bca2e8aae045dafed515ce61c0f19`。
- 实际 manifest 统计：154 份绑定文件，含 48 份参与源码、28 份显式运行资源。计数全部来自清单，生成器未写死新总数。
- 原 135 份绑定文件中，131 份字节相同，4 份仅有打包/启动变更；新增 19 份包含资源、打包/测试代码、资源清单、修订记录和历史验收副本。按类别详见 SNAPSHOT_DIFF.json。

补入的基线资源（完整清单另见 frozen_sources/RUNTIME_RESOURCES.json）：

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `mtc_closed_resource_sources.v1.json` | 2261 | `377f492d81d654d738b67967344d5420d1dab44d57b03953950140c8f4e0746e` |
| `mtc_p3_semantic_sources.v1.json` | 13310 | `dddbceaf1341ef597a61879e3ef7ff676f2abe628394696cad7fe3a1572b5ed9` |
| `paired244_review_sources.v1.json` | 1162 | `5c7dc9daae29f6b9d70c6750eaa9f875e47a4ff15e56546bb923233f7834e3f5` |

被替换的原绑定源码仅有：

- `frozen_sources/hybridguard_agent/research/manipulation_eval/freeze.py`
- `frozen_sources/hybridguard_agent/research/manipulation_eval/runner.py`
- `frozen_sources/hybridguard_agent/scripts/freeze_formal_manipulation_protocol.py`
- `frozen_sources/hybridguard_agent/scripts/run_formal_manipulation_eval.py`

新增 runtime_resources、freeze_revision、snapshot_smoke 和独立测试；原 worker/job validator AST 不变，全部原谓词/原 Verifier/风险策略/风险 Verifier/语义门控字节不变。CLI 预检位于完整链导入、合同载入、样本读取、输出创建之前；API 也在样本/输出/单元之前预检。删除清单条目不能隐藏缺件，不回退主工作区或其他配置。

有限读取点审查覆盖选定 final/legacy 链及 Verifier、导入时字段映射；除上述三份外未发现同类遗漏。未选择的上游生成器、通用检索、v2 catalog 等在 RESOURCE_READ_AUDIT.json 说明，不开展全库审计。

## 实验语义差异核对

SEMANTIC_INVARIANCE.json 逐项比较全部父快照已绑定文件，只有明确的打包源码允许变化；协议仅增打包修订字段并改 digest。所有来源文件和角色/家族/策略/指标/图表配置来自原字节或三份原基线资源，未重认定规则或标签。

- S01 标签、准入、环境关联组；S02 的 262 阶段输入字节及阶段关联不变；cohort 为 {"admitted_attack_triplet": 162, "incomplete_attempt": 1, "lower_evidence_attack": 45, "temporal_control_unknown": 54}。
- 57 ACTIVE / 7 候选 / 5 家族，v2 门控、固定家族 OR、阈值 1 不变；来源候选数为 {"E": 5, "O_u": 2, "H": 0, "C": 0}。O_u/E 共享家族、H/C 无风险候选的限制继续保留。
- 方法/视图/来源条件、主216与描述46、13唯一风险变体、2854计划单元不变；S06/S07/S08/S10 首次执行单元为 {"S06": 432, "S07": 1512, "S08": 864, "S10": 46}。E4、合成定义及计时 expected units 也逐字节不变。
- 攻击/pre/post/准入三态分母各54，合格阴性108；时间对照 control_mid 阴性分母0，no_intervention 仍 UNKNOWN、不取得 FPR 资格。无共同批次键不构造配对差分，指标/图表限制及暴露历史不变。
- 原05全部 149 份登记文件未改；原登记 416 份文件中，仅上述 4 份打包源码有变化，其他 size/mtime 未变，并有父快照逐字节比较补充。原 S01–S05 状态条目及 S03-R 修订条目不改；270 条已有无关 Git 脏状态保留，索引仍为空。未读取 P0–P6 预测结果或改写其历史产物。

## 独立快照合成验收

聚焦静态测试 9/9 通过；原 S05 测试日志保留且未重跑上游。独立输出位于 `hybridguard_agent/artifacts/formal_manipulation_v1_20260923/05_freeze_r1_validation`，每个子进程仅复制 `05_freeze_r1/frozen_sources` 至新临时目录，从空 cwd 用 `-I -B -S` 启动，移除 PYTHONPATH/PYTHONHOME，无预先导入研究模块。只复制源码/资源，不复制真实输入或评估标签。模块 __file__、运行资源路径、读取守卫结果、启动命令和 stdout/stderr 均保存。

| 人造单元（均 App177 / SRC-111） | 预期且实际结果 | 家族分数 | 执行/验证 |
| --- | --- | ---: | --- |
| final_v3_v2 / consistent | NO_ALERT | 0 | COMPLETED / 双 Verifier 通过 |
| final_v3_v2 / single_family_duplicate_rules | MANIPULATION_ALERT | 1 | COMPLETED / 双 Verifier 通过 |
| legacy19_v2 / consistent | NO_ALERT | 0 | COMPLETED / 双 Verifier 通过 |
| legacy19_v2 / single_family_duplicate_rules | MANIPULATION_ALERT | 1 | COMPLETED / 双 Verifier 通过 |

四单元均实际经过 evidence、完整原规则、runtime_cards、原 Verifier、v2 风险策略和风险 Verifier。每单元原规则/runtime_cards 各调用3次，原 Verifier 2次（含风险 Verifier 内复核）；不是只 import 或单关系 probe。final 保留全部目录结果含57 ACTIVE；legacy19 保留原19关系。分数只是家族计数，归因仍 UNKNOWN。

另三个新临时副本分别删除一份必需来源 JSON，CLI/API 共 6 次均明确报 MISSING_RUNTIME_RESOURCE 及具体路径；样本路径未读取、输出目录未创建、worker调用为0。故意不完整的人工控制面 job 仅用于验证启动顺序，不是执行 S06 的授权或输入。静态测试还覆盖“文件/登记同时删除”、摘要变化、重复/遗漏登记、配置外指及资源软链接回退拒绝。

开发阶段曾有一次测试工具计数器遍历异常（正常4单元已通过）；只修复 profiler 自计数及迭代方式，日志在 DEVELOPMENT_CHECK_HISTORY.json 和 INITIAL_HARNESS_FAILURE.txt。随后临时草案和最终快照均通过。全回合共12次人造完整单元执行（开发8、最终4），未以结果调规则/门控/夹具；最终验收只绑定新快照 digest 对应的4单元。

## 交付、限制与停止点

主要产物：FREEZE_MANIFEST / protocol.json / frozen_sources/RUNTIME_RESOURCES、RESOURCE_READ_AUDIT、PACKAGING_REVISION、SEMANTIC_INVARIANCE、SNAPSHOT_DIFF、INHERITED_SEMANTIC_SUMMARY、READ_ONLY_REVIEW、STATIC_VALIDATION、FOCUSED_TESTS、VALIDATION、独立 SYNTHETIC_ISOLATED 日志。计划追加说明见 deliverables/formal_experiment_execution_plan/S05_R_PACKAGING_REVISION_r1.md；执行状态单列 S05-R。

验收证明指定合成完整链可从修订快照独立运行、资源缺件可在单元前阻断；不证明真实检测性能或所有输入分支。真实 predictions、真实性能计算、LLM、采集、上游重跑均为0；S06单位0。风险提示不是攻击证明/恶意判断/已校准概率。S01时间对照限制、H/C和共享家族结构限制、既有材料暴露及设备独立性限制均保留。

停止等待审查。外部审查通过并另获 S06 授权后，才可使用本修订的 protocol/digest 及其内部源码、v2 config/policy；不能混用旧快照或主工作区。未执行 S06–S12，不自动提交或推送。
