# 本次上传攻击包的只读校验报告

日期：2026-09-23。该报告是实际执行的材料校验，不是检测器性能实验。

ZIP SHA-256：`fc0b1aaec61bbcde929105f064230f2b2713f5056682135e25db2dafe55c92af`

## 汇总

完整攻击包 23 个，69 组三态（207 个阶段）。其中 18 个通过、5 个未通过：通过组覆盖 54 个攻击阶段和 108 个前/后阶段；未通过组覆盖 15 组三态。

无攻击时间对照 6 包，18 组三时点、54 个阶段；6 包全部通过。

## 解释边界

本次执行 ZIP 内 verify_attack_run_bundle.mjs 与 verify_no_attack_temporal_control_bundle.mjs；未运行攻击工具，未启动采集器或后台。校验涵盖仓库定义的完整性、引用、字段变化、恢复和回执准入。部分回执引用未随 ZIP 提供的私有原日志，因此不构成第三方现场验证，也不替代独立于检测结果的标签审阅。

5 个未通过包均缺少被引用的 automation_logs 文件。它们不是检测器漏报，更不证明历史实验没有发生；仅说明本次上传副本不足以通过既有校验。其他 18 包利用已有回执等材料通过，不意味着补齐了缺失的所有原始私有日志。

## 逐攻击包结果

| 包名 | 阶段数 | 校验结果 | 备注 |
|---|---:|---|---|
| `20260812_cdp_api30_formal_v4` | 9 | FAIL | 缺被引用执行日志，较低证据等级 |
| `20260812_cdp_api35_formal_v1` | 9 | FAIL | 缺被引用执行日志，较低证据等级 |
| `20260812_cdp_api36_formal_v1` | 9 | FAIL | 缺被引用执行日志，较低证据等级 |
| `20260812_stealth_api35_formal_v1` | 9 | FAIL | 缺被引用执行日志，较低证据等级 |
| `20260812_stealth_api36_formal_v2` | 9 | FAIL | 缺被引用执行日志，较低证据等级 |
| `20260823_api36_rule_boundary_cdp_platform_only_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_api36_rule_boundary_cdp_resource_pair_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_api36_rule_boundary_cdp_ua_only_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_api36_rule_boundary_cdp_ua_platform_desktop_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_api36_rule_boundary_cdp_webdriver_only_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_cdp_api30_controlled_v2` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_cdp_api35_controlled_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_cdp_api36_controlled_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_playwright_api36_controlled_v2` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_puppeteer_api30_controlled_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_stealth_api30_controlled_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_stealth_api35_controlled_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260823_stealth_api36_controlled_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260824_api36_cdp_emulation_v5_screen_metrics_only_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260824_api36_cdp_emulation_v5_timezone_only_v1_rerun1` | 9 | PASS | 满足仓库校验器准入 |
| `20260824_api36_stealth_languages_only_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260824_api36_stealth_plugins_mime_v1` | 9 | PASS | 满足仓库校验器准入 |
| `20260824_api36_stealth_webgl_pair_v1_rerun1` | 9 | PASS | 满足仓库校验器准入 |

## 无攻击时间对照

| 包名 | 阶段数 | 校验结果 |
|---|---:|---|
| `20260823_api30_no_attack_temporal_v6` | 9 | PASS |
| `20260823_api35_no_attack_temporal_v1` | 9 | PASS |
| `20260823_api36_no_attack_temporal_v1` | 9 | PASS |
| `20260823_api36_rule_boundary_no_attack_v2` | 9 | PASS |
| `20260824_api36_cdp_emulation_v5_no_attack_v1` | 9 | PASS |
| `20260824_api36_stealth_boundary_no_attack_v1` | 9 | PASS |

完整机器可读输出见 `attack_bundle_audit.json`。输出中目录路径只是本次分析环境路径，不是用户本地路径。
