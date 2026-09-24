# S05-R 冻结运行资源修订 r1

本修订基于审查版本 `595d30d690713f6ee800a7825cfe8199cee97565`，仅修复运行资源打包及启动检查，并以独立子进程的合成完整链验证快照。它不是实验设计、检测策略或 v2 协议 schema 的变更，也不授权 S06。

## 继承与版本

- 原目录 `hybridguard_agent/artifacts/formal_manipulation_v1_20260923/05_freeze/` 保持原样，其静态验收记录继续表示当时已登记文件的检查结果。此次确认的资源遗漏另行记录，不能把旧静态 PASS 解释为独立运行验证。
- 新目录 `hybridguard_agent/artifacts/formal_manipulation_v1_20260923/05_freeze_r1/`；新配置目录 `hybridguard_agent/config/formal_manipulation_protocol_v2_r1/`。
- 独立 `freeze_revision = formal-manipulation-freeze-r1`；新旧 `protocol_digest` 与继承关系见新 `protocol.json`、`PACKAGING_REVISION.json` 和 `FREEZE_MANIFEST.json`。
- 继续使用 `formal-manipulation-protocol-v2`、`formal-manipulation-relation-risk-attribution-v2`、`formal-manipulation-family-or-v2`；S04 job schema 和原单元 worker 不变。
- 原协议 `code_commit`、`frozen_at`、source_environment、计划及历史报告保留原记录时点；新增打包时间、审查基线和源码副本另记。历史“尚未推送”等措辞不是当前远端状态，也不触发重跑或覆盖。

## 有限修复

显式运行资源清单补入 `mtc_p3_semantic_sources.v1.json`、`paired244_review_sources.v1.json`、`mtc_closed_resource_sources.v1.json`，绑定其实际字节数和 SHA-256。完整清单是新快照的 `frozen_sources/RUNTIME_RESOURCES.json`；文件数从清单统计，不写死预期总数。读取点审查限于两个已冻结方法的完整调用链及 Verifier，见 `RESOURCE_READ_AUDIT.json`。

必需集合同时定义在打包代码中；删掉清单条目不能隐藏必需资源。预测 CLI 在导入完整链、载入合同、读取样本或创建输出前预检，预测 API 也在读取样本/创建输出/执行单元之前预检。缺件明确抛出 `MISSING_RUNTIME_RESOURCE` 和具体路径；清单缺项、摘要不符、资源或配置指向快照外均拒绝，不做主工作区回退。

修订生成器必须同时显式提供 `--parent-freeze`、`--freeze-revision`、`--output` 和 `--config-dir`。它复制父快照已绑定字节，仅替换明确列出的打包/启动/验证源码并补资源；不调用上游 admission、adapter.generate 或重新构造材料/单位集合。已有冻结目录、其子目录及已有协议配置受覆盖保护。

## 不变的实验定义

S01 标签/准入/环境组，S02 输入字节/阶段关联，57 ACTIVE / 7 候选 / 5 家族，v2 门控、家族 OR、阈值 1，来源条件、方法、视图、样本、各步 expected units、任务分母、指标/图表定义和暴露历史均继承原字节。原关系谓词、原 Verifier、风险策略和风险 Verifier 没有修改；单元 worker 和 job validator 的 AST 相同。逐文件分类差异见 `SEMANTIC_INVARIANCE.json` 和 `SNAPSHOT_DIFF.json`。

## 独立合成验收

验证输出放在独立的 `05_freeze_r1_validation/`。正常子进程仅复制新快照 `frozen_sources/` 到新临时目录，在空 cwd 下用 Python `-I -B -S` 启动，清除 PYTHONPATH/PYTHONHOME，无预先导入的研究模块。记录实际模块 `__file__`、资源读取路径和完整链调用次数，并守卫研究文件读取，禁止快照外回退。

`final_v3_v2 / App177 / SRC-111` 和 `legacy19_v2 / App177 / SRC-111` 各执行一致输入与共同有效域冲突输入。两种方法均预先声明为 NO_ALERT/0、MANIPULATION_ALERT/1；完整 evidence、原规则、runtime_cards、原 Verifier、v2 风险策略和风险 Verifier 都实际执行，不调用单关系 probe。其结果是 SYNTHETIC，不是正式 predictions 或 S06 单元。

另外为每份必需来源 JSON 新建临时测试副本并删除该文件，验证 CLI/API 在样本、输出和 worker 之前失败。该负向测试仅使用故意不完整的人工控制面 job，不创建可执行 S06 job，也不接入真实输入。

## 后续绑定与限制

S05-R 审查通过且另获 S06 授权后，应使用 `05_freeze_r1/protocol.json` 和新 digest，并显式传入 **同一修订快照内部** 的 `formal_manipulation_role_gate_v2` 配置与 `formal_manipulation_policy_v2/decision_policy.json`。旧快照保留为历史记录，不作为已完成独立运行验证的包。不能只换协议文件而继续从主工作区或旧快照加载代码/配置。

此验收只证明指定合成路径可独立运行、缺件能提前阻断，不证明真实性能或全部输入分支。时间对照 no_intervention 仍 UNKNOWN，无 FPR 资格；C 仍 UNKNOWN，风险提示不是攻击证明。H/C 无风险候选、O_u/E 共享家族等结构限制、Fig.6/配对差分关闭及材料暴露限制全部保留。停止等待审查，不执行 S06、不自动提交或推送。
