# S01 材料核验、事实准入与环境分组

工程验收：见 `VALIDATION.json`。本步只做材料校验和事实裁决；检测性能保持 `NOT_EVALUATED`。

## 材料与准入

| 项目 | 数量 |
|---|---:|
| 候选包（含失败尝试） | 31 |
| 完整攻击包 / 三态 | 23 / 69 |
| 时间对照包 / 三时点 | 6 / 18 |
| 不完整或空包 | 2 |
| 原始阶段 / 事实台账 / 成功绑定 | 262 / 262 / 262 |
| 准入攻击阶段 / 准入三态 | 54 / 54 |
| 准入 clean_pre / clean_post | 54 / 54 |
| 准入时间对照阶段 | 0 |
| 环境关联组 | 3 |

## 事实裁决与限制

- 完整攻击材料的本地校验结果与设计审计逐包对账；完整包之外的两次失败尝试也保存 stdout、stderr、returncode、run errors 和关联。
- 执行归因为 L1：核对 receipt 与 session、runtime_context、run、配置及工具版本，再结合 active MEASURED 记录。私有原日志缺失，不能称独立现场见证。
- 可观察效应和恢复逐声明字段从已绑定 raw 重算，包括字段状态、原值、active 值、post 值；其 L2 仅指这部分原始观测可复核，不升级执行归因。
- clean_pre/post 的 L1 依据同一有回执三态中的 not_run、absence 观测与 raw 一致；post 额外要求全部声明字段已恢复。只支持声明干预表面的对照，不是绝对正常标签。
- 时间对照虽通过结构校验，但材料只有 run/sidecar 的 none、clean、空 active_tooling 声明及原始指纹；没有可绑定的启动、清理或操作记录来排除主动/残留干预。因此无干预事实保持 UNKNOWN，当前不能报告该分支 FPR。字段稳定不是无干预证明。
- 旧包原始字段效应仍保留；缺失直接执行日志时，执行归因 UNKNOWN，不能进入正例分母，也不能计作检测漏报。
- 检测资格不依赖未来 post 或恢复成功。三阶段齐备且事实可解释时保留失败/未知恢复轨迹；post 阴性资格单独决定。既有材料受恢复导向的历史选包影响，不能推广到工具全部尝试成功率。
- 原标签和原始数据未修改；所有记录 `independent_attestation=false`。本步没有规则报警、TPR/FPR、训练、模型调用或新攻击执行。

## 缺件与分组

- `MISSING_DIRECT_SUCCESS_EVIDENCE`：15。
- `PRIVATE_RUNNER_LOG_PATH_UNDISCLOSED`：48。
- `PRIVATE_RUNNER_LOG_MISSING`：6。
- 15 个直接 success_evidence 缺件与 54 个私有日志限制是不同类别，详见 `missing_materials.jsonl`。
- API36 两个 alias 通过相同 collector_install_id 合并；run/capture、安装、稳定键和 alias 关联做传递闭包。API、型号、ADB serial、共享接收端不作为独立身份依据。
- 三个关联组不等于三台已核验独立物理设备。保留原 sha256-canonical-stable-identity-v1 / verified_within_attack_run，不改写成 HMAC/provider_stable_profile。
- `manual_fact_queue.json` 按 6 个时间对照包列最小无干预证据需求，按 5 个旧包列可选晋级日志；均不阻断 S01 完成，不要求全面人工评分或新采集。
- `_rerun1` 只保留来源命名关系；当前副本没有对应原始包时标明缺失，不猜撤回原因或抹去历史失败。

## 逐包核验

| 包 | 原始阶段 | 校验 | 材料去向 | 环境组 |
|---|---:|---|---|---|
| `20260812_cdp_api30_formal_v4` | 9 | failed | COMPLETE_CANDIDATE | env-001 |
| `20260812_cdp_api35_formal_v1` | 9 | failed | COMPLETE_CANDIDATE | env-002 |
| `20260812_cdp_api36_formal_v1` | 9 | failed | COMPLETE_CANDIDATE | env-003 |
| `20260812_stealth_api35_formal_v1` | 9 | failed | COMPLETE_CANDIDATE | env-002 |
| `20260812_stealth_api36_formal_v2` | 9 | failed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api30_no_attack_temporal_v6` | 9 | passed | COMPLETE_CANDIDATE | env-001 |
| `20260823_api35_no_attack_temporal_v1` | 9 | passed | COMPLETE_CANDIDATE | env-002 |
| `20260823_api36_no_attack_temporal_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api36_rule_boundary_cdp_platform_only_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api36_rule_boundary_cdp_resource_pair_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api36_rule_boundary_cdp_ua_only_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api36_rule_boundary_cdp_ua_platform_desktop_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api36_rule_boundary_cdp_webdriver_only_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_api36_rule_boundary_no_attack_v2` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_cdp_api30_controlled_v1` | 1 | failed | INCOMPLETE_ATTEMPT_RETAINED | env-001 |
| `20260823_cdp_api30_controlled_v2` | 9 | passed | COMPLETE_CANDIDATE | env-001 |
| `20260823_cdp_api35_controlled_v1` | 9 | passed | COMPLETE_CANDIDATE | env-002 |
| `20260823_cdp_api36_controlled_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_playwright_api36_controlled_v1` | 0 | failed | INCOMPLETE_ATTEMPT_RETAINED | env-003 |
| `20260823_playwright_api36_controlled_v2` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260823_puppeteer_api30_controlled_v1` | 9 | passed | COMPLETE_CANDIDATE | env-001 |
| `20260823_stealth_api30_controlled_v1` | 9 | passed | COMPLETE_CANDIDATE | env-001 |
| `20260823_stealth_api35_controlled_v1` | 9 | passed | COMPLETE_CANDIDATE | env-002 |
| `20260823_stealth_api36_controlled_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_cdp_emulation_v5_no_attack_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_cdp_emulation_v5_screen_metrics_only_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_cdp_emulation_v5_timezone_only_v1_rerun1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_stealth_boundary_no_attack_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_stealth_languages_only_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_stealth_plugins_mime_v1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |
| `20260824_api36_stealth_webgl_pair_v1_rerun1` | 9 | passed | COMPLETE_CANDIDATE | env-003 |

## 复现与停止点

初次执行：`PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/prepare_formal_manipulation_inputs.py admission --output <新的输出目录>`。
中断后仅已有材料校验记录时可加 `--reuse-validators`；必须通过相关源文件 size/mtime 核对。已有 VALIDATION.json 的输出拒绝覆盖。
本轮在源码实现期间先逐包保存了 31 次 CLI 输出，随后复用这些输出生成台账，没有重复运行材料校验器。

聚焦合成测试命令：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest hybridguard_agent.tests.test_formal_manipulation_admission -v`；实际记录见 `FOCUSED_TESTS.txt`。
验收检查只读取保存事实、引用和分母；相关原材料 size/mtime 保持不变。P0–P6、攻击仓库及历史结果均未写入。
本轮 S01 产物仍在工作区。前置设计/计划提交 `4826e2649a734b709a05fd4717f63e7adb50e95b` 已推送并核对远端 main。
S02 未执行；逐步状态以 `deliverables/formal_experiment_execution_plan/EXECUTION_STATUS.json` 为准。
