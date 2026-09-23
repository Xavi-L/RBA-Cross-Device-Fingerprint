# S03-R STEP_REPORT

合同版本：`formal-manipulation-relation-risk-attribution-v2`。审查基线：`66f9cdc2d40c41ccec0999c7a6c8d68c0a1b415f`，已核对当前 HEAD 完全一致。完成时间：2026-09-23T14:58:45.926532+00:00。工程验收 PASS；合同等待用户审查，S04 未执行，未提交或推送。

## 1. 交付结论

已将 A 关系适用性、B 有限研究风险候选资格、C 攻击/授权/意图归因确定性分开。对可比较关系不再要求先证明攻击来源；合法替代解释继续限制风险解释与归因，不改为攻击标签。真正影响测量的缺失、类型/非有限值、零哨兵、缩减/掩蔽身份、错误产品语义、软件或未知 GPU 等门控仍保留。

逐条审查八条原建议候选后，7 条进入有限研究风险候选、涉及 5 个家族；OFFDER-GPU-001 的 backend marker 缺少足以升级为风险的独立可比身份主张，仍为 observation_only。未预设候选数量或来源收益，也没有把其余观察/上下文统一晋级。详细旧条件、新分类、当前字段、依据、反例和影响见 `ROLE_AND_GATE_REVISION.md`。

本次修正基于已有关系谓词能直接求值、而授权/物理来源不在其观测输出中的合同区别。原 S03 将二者合并是过强约束；修订不以正式预测、测试集效果或用户期待的检出率作为依据。

## 2. 来源、角色与家族

| 来源 | 原规则数 | 风险候选 | 观察 | 上下文 | 采集器 | 部署 | 候选家族数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| E | 23 | 5 | 13 | 4 | 1 | 0 | 5 |
| O_u | 9 | 2 | 4 | 2 | 1 | 0 | 2 |
| H | 14 | 0 | 14 | 0 | 0 | 0 | 0 |
| C | 11 | 0 | 0 | 3 | 6 | 2 | 0 |

候选精确 ID：`NW-001`、`NW-002`、`NW-005`、`NVW-001`、`NVW-002`、`OFFDER-OS-001`、`OFFDER-OS-002`。对应家族：model_app_ua、app_os、model_system_agent、host_os、native_app_gpu_family。

57 条 ACTIVE 的 E23/O_u9/H14/C11、原 evidence_family、27 个 decision_family、原重叠矩阵和四来源/八组合精确 ID 均保持。新版只覆盖 A/B/C 合同与七条角色，全部来源条件使用同一 v2 门控和统一研究范围。

O_u 的两个候选与 E 共享 app_os/host_os，且使用相同条件及等价关系表达；保留 E 时不增加候选家族，在计划中的固定家族 OR 策略下，其零二值增量存在事前结构原因。H/C 没有风险候选，零二值增量也不能解释为其来源无价值。来源组计数、关系来源和检测效果是不同事实；O_u 仍不是“纯官方规则”。

## 3. 新合同的有效边界

A=SUPPORTED 可以同时出现 MATCH 或 COUNTEREXAMPLE，表示关系可评估。B=ELIGIBLE 允许后续研究该关系的风险用途，不表示已经报警。缺 A 字段与仅缺风险参照分别报告：后者可以保留 A=SUPPORTED/关系冲突，同时 B=UNKNOWN。C 始终 UNKNOWN，不声称确定性攻击、未经授权、恶意意图或已校准概率。

App UA 风险候选增加可观测 default/settings 一致及 Native/default 命名或版本吻合条件；明确 settings 自定义时 B=NOT_ELIGIBLE，default 缩减或参照/别名不明时 B=UNKNOWN。System 型号也保留 default 命名参照；System OS 只比较明确 Dalvik 与可解析主版本。GPU 硬件族必须双方唯一且没有软件/掩蔽；正常 host/remote/hybrid 路径的可能性保留为归因和误报限制，不能据此把原 backend marker 自动晋级。

旧 16 条不可观测前提已逐项分类。窗口/zoom/display 与原通用 UA 等值解释的测量前提没有统一软化；Browser 旧版本范围缺口继续保留。其余 49 条未建议检查角色不变，ADB、模拟器、调试、部署、桥接等不能成为攻击票。既有 false、零 touch、空列表仍是合法观测。

风险提示含义统一固定为“声明研究范围内疑似操纵／风险提示”，不是攻击真值。Native 只是声明干预未修改的相对参照；合法行为的标签不能因提示而修改。同一研究范围用于全部样本和来源条件，不读取 label、phase、tool、执行 config、session/install/group、回执、日志或 future post 补条件。当前允许的 WebSettings 指纹字段与禁止的执行配置侧元数据明确区分。

## 4. 验证结果与可行性

原 v1 测试文件原样保留，15 项回归通过；新版本独立 17 项聚焦测试通过，共 32 项。真实输出保存在 `FOCUSED_TESTS.txt`。测试覆盖三轴分离、候选路径可达、缺失/无效/不适用、归因未知、合法自定义/别名参照、Dalvik、GPU 软件与 backend marker、非候选角色、元数据隔离、掩蔽/质量、来源结构限制和目录覆盖防护。

35 个已保存合成夹具为七条候选分别提供一致、冲突、缺失、类型无效、不适用五种输入。35/35 期望匹配；全部候选均能到达 A=SUPPORTED、B=ELIGIBLE 的一致与冲突路径，同时 C=UNKNOWN。输入与逐例真实结果分别见 `SYNTHETIC_FIXTURES.jsonl`、`SYNTHETIC_RESULTS.jsonl`；这是合成关系验证，不是真实样本 predictions 或 S04 风险输出。

`DETECTION_FEASIBILITY.json` 状态为 `LIMITED_RISK_CONTRACT_HAS_REACHABLE_PATHS_NOT_VALIDATED_DETECTION`。说明当前合同存在有依据且可达的有限风险路径，允许后续审查 S04 合同可行性；不证明真实数据覆盖、检测性能或部署能力。真实 TPR/FPR、风险校准、来源效果均 NOT_EVALUATED。

保存后 30 项静态验收通过，确认来源/家族/字段闭合、八组合和共同门控一致、新配置副本相同、候选/归因结果一致、v1 语义函数与原测试未变、159 个登记的既有文件 size/mtime 未变、其他工作区改动保留、暂存区为空及 HEAD 未变。只读检查是有限工程边界核对，不是密码学认证；见 `VALIDATION.json` 和 `FINAL_REVIEW.json`。

## 5. 版本与覆盖风险修复

执行时同时显式指定：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m hybridguard_agent.research.manipulation_eval.provenance_revision \
  --output hybridguard_agent/artifacts/formal_manipulation_v1_20260923/03r_role_gate_v2 \
  --config-dir hybridguard_agent/config/formal_manipulation_role_gate_v2
```

`GENERATION.json` 保存实际绝对 output/config_dir。目的地现在必须成对显式提供、相互独立且新建或为空；仅换 output、指向旧配置、已有非空目录、重叠/嵌套或符号链接指向受保护目录，都会在写入前拒绝。已生成并验收的本版本不可原地重生成；复现时应提供两个新的空目录。

对 v1 `provenance.py` 的修改仅涉及目的地预检和 CLI 必填参数；旧角色/语义函数没有变化。新实现为 `provenance_revision.py`，共同安全入口为 `registry_output.py`；新测试独立于 v1 测试。

## 6. 产物、历史保留与停止点

新版配置共 7 份：applicability_policy、decision_roles、research_scope、source_conditions、family_bindings、precondition_classification、source_bindings。输出目录保存对应副本，以及逐候选修订说明、合成输入/结果、可行性、生成记录、聚焦测试、依赖检查、只读快照、最终复核、VALIDATION 和本报告。

计划修订见 `deliverables/formal_experiment_execution_plan/S03_R_CONTRACT_REVISION_v2.md`；EXECUTION_PLAN 以版本化链接声明后续 S04 应显式采用 v2 A/B/C 与同一研究范围，原 v1 章节和执行历史保留。EXECUTION_STATUS 将 S03-R 作为独立 revision 标为 DONE/PASS、AWAITING_USER_REVIEW；S03 v1 仍保存原验收，不覆盖零候选历史。

S01/S02 没有重跑：262 条原阶段、262 适配成功/0 拒绝、原标签/准入和阶段关联保持；54 条时间对照 no_intervention 仍 UNKNOWN，不晋级该分支 FPR。缺日志、L1 证据限制和三个环境关联组不等同独立物理设备的事实不变；不补 Browser、不补采、不补日志、不重挖规则、不重做全量文档审计。真实样本门控/预测、性能计算、阈值变更、LLM 调用均为 0。

本步完成后停止，等待审查。S04 未实现/未执行，本轮不提交或推送。
