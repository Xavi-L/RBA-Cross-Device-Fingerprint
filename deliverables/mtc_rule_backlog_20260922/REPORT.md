# 37 项旧规则处置与首批可执行实现

> 本页为 v2 首批历史报告。用户随后明确不再补采；当时剩余 25 项现已收尾，默认 v3 共 57 项可执行，无开放研究／补采任务。最新状态见 [v3 报告](../mtc_closed_resource_20260922/REPORT.md)，下文数字和待办保留首批时点语义。

2026-09-22。用户授权按“逐项处置 → 可支持的检查先实现 → 重新研究 → 必要补采”推进。本批已完成逐项处置、首批实现与离线验收；**不宣称 37 项全部实现，也未进入 P5 补采或正式检测实验。**

## 结果

| 原来的 37 项 | 数量 | 现在的含义 |
|---|---:|---|
| 已接入 | 6 | 2 项部署策略检查、4 项上下文检查；不是新发现的攻击规律 |
| 合并处置 | 4 | 不再作为独立风险票；其中 2 项容错并入仍待研究的父项 |
| 停用 | 2 | 版本比较容错、无依据的低风险确认 |
| 待研究 | 17 | 字段可能存在，但判定条件、可比性或独立支持仍不足 |
| 待补数据 | 8 | 需要时间序列、经过验证的证明结果或导航来源等信息 |

整个 v2 目录仍为 **87 个条目：54 项可执行、4 项停用、4 项合并、17 项待研究、8 项待补数据**。此前 v1 为 48 可执行、2 停用、37 未实现。数量变化全部有逐项记录，未通过删除困难条目或将未知改成正常来提高通过数。54 项仍含共享证据，不能称为 54 条独立、有效的攻击规则。

详细 37 行处置及字段可用性见 [REVIEW.md](REVIEW.md)。原始数据、P3 参数、P4 v1 目录与历史验收产物均保留。

## 六项实现及实际观测

以下统计针对 774 条 Full244 主代表（发现 630、开发 144），不是独立物理设备数，也不是检测效果。

| ID | 新的可执行含义 | 观测结果 |
|---|---|---|
| NVW-003 | 包名精确匹配 `com.example.hybridguard.featureapp`，不用宽泛前缀 | 774 符合部署策略 |
| OFFDER-PACKAGE-001 | 包名及 versionCode/versionName 配对匹配 P1 已冻结的 v9、v11 部署清单；安装来源独立报告 | 774 符合部署策略 |
| NVW-004 | 区分具名安装器、采集器 `manual` 回退和未知值 | 148 具名安装器、626 `manual` 回退，均仅上下文 |
| WVWEB-002 | 记录 App Web UA 中 `wv` 与 `Version/4.0` 标记 | 774 两标记均出现，仅上下文 |
| TOL-001 | 分别记录 ADB、debuggable、cleartext 开关 | 771 可观察上下文、3 未评估 |
| OFFDER-NET-001 | 有采集器 API 条件的瞬时网络与 VPN 上下文 | 771 上下文、3 旧 API 不适用 |

网络上下文细分为 760 次常规网络观测、1 次 VPN 观测、10 次未观察到活动网络；均不产生攻击或安全结论。开发配置中 770 条三个开关均为 true，1 条 debuggable/cleartext 为 true；不据此归类云控、恶意或可信设备。

部署参数来自项目 `applicationId` 与 P1 的 `allowed_releases`，**没有根据本轮规则输出调整白名单**。部署一致只说明自报字段符合本项目已声明的采集配置；这些字段不是签名或硬件证明。对其他 App/批次不应套用此 MTC 策略。两个策略检查共享 `deployment_identity` 家族，不能计两张独立票。

## 采集语义与旧结论修订

采集器 `ExpandedFingerprintCollector.kt` 将安装器 null 写为 `manual`，捕获异常写为 `unknown`。因此 `manual` 不能直接翻译为“手动安装”，具名安装器也不能证明可信来源。Android 当前文档同样说明安装来源可以为空或改变：[InstallSourceInfo](https://developer.android.com/reference/android/content/pm/InstallSourceInfo#getInstallingPackageName())。

网络采集仅在 API ≥23 使用 `activeNetwork`/capabilities，旧 API 的部分布尔值是回退值；新检查在此边界返回不适用。网络类型只是当时的传输属性：[NetworkCapabilities](https://developer.android.com/reference/android/net/NetworkCapabilities#hasTransport(int))。无活动网络不被解释为“无 VPN”，多个网络类型也不被强制当成互斥身份。

UA 可以被 App 配置覆盖，因此标记有无只作词法观察，不作为 WebView 真值：[WebSettings](https://developer.android.com/reference/android/webkit/WebSettings#setUserAgentString(java.lang.String))。新规则保留依赖、固定参数和限制，检索卡能还原检查条件。

- `TOL-004` 停用：其小版本容错仍以 provider 包版本和 UA Chromium 版本可直接比较为前提，沿用 P3 已否定的通用假设。这是补齐旧处置的遗漏，不是本批又发现一个新的数据反例家族。
- `SCENE-004` 停用：安装来源、传感器数量和 bridge 不足以确认安全/低风险。本批没有证实它的检测性能，停用依据是结论缺少支持，不能说成新样本已统计推翻。
- `WVWEB-003` 合并到 bridge、UA 表面和标记观察；取消“共同成立即可强可信”的附加推断。
- `AGG-001` 改由当前逐条结果与去重 evidence family 汇总承担。旧平均分及风险阈值没有实现或沿用。
- `TOL-002`、`TOL-003` 分别并入 `NW-003`、`NW-008` 的研究要求。父项仍待研究，合并不表示屏幕/内存容差已解决。

## 执行与验收

默认 paired244 入口现使用 `paired244-runtime-catalog-v2`。执行状态明确区分 `PENDING_RESEARCH`、`PENDING_DATA`、`MERGED`、`DISABLED`；这些状态保留在完整 trace 中，不进入活跃检索卡，不被统计为通过。决策显式列出待研究/待数据/合并/停用项，`catalog_fully_assessed=false`。

部署不匹配输出 `POLICY_MISMATCH`，并单列部署策略差异，避免混成指纹关系反例。所有新增上下文检查都不会生成攻击分数。缺失、超时、权限不足、类型无效继续返回未评估；解析不清返回未知。缺标记、VPN、合法 false 不产生攻击推断。

- **62 项测试通过**：14 项本批边界，48 项 P4 和历史兼容验证。
- **1,548 次实际离线运行全部完成**：774 条代表 × Full244/App177。
- **74,304 次原检查对照无变化**：每次运行比较原有 48 项的完整结果。
- 另与冻结的 P4 release 逐规则汇总对比，**192 个 split/view/rule 单元完全一致**。
- 移除 Browser 后 **6,966 次 Browser 依赖检查均未评估且无已用字段**。
- 保留验证集仍锁定；未启动后端/ngrok、未训练模型、未调用模型、未调阈值、未修改源数据。

这些证明实现与兼容性，不证明检测准确率或泛化。声明字段可用性已对 37 项统计，但不等于候选关系可用：例如电池字段齐备仍缺时间序列；型号字段齐备仍需可比较的 UA 解析规范。字段不足或语义不足没有被转换为正常结果。

复现到新的输出目录：

```bash
python3 hybridguard_agent/scripts/run_mtc_rule_backlog.py \
  --out-dir hybridguard_agent/artifacts/mtc_rule_backlog_NEW_RUN
```

权威本批产物：`hybridguard_agent/artifacts/mtc_rule_backlog_20260922/`，含完整逐样本结果、trace、规则/原因汇总、字段可用性、固定首条示例、配置与实现副本。摘要见 [SUMMARY.json](SUMMARY.json)、[VALIDATION.json](VALIDATION.json)。历史 `run_mtc_p4_runtime.py` 显式固定 v1，重放历史验收不会自动改用新目录。

## 剩余工作

17 项研究与 8 项补数据未完成，具体顺序、最小证据和验收见 [NEXT_STEPS.md](NEXT_STEPS.md)。本次没有把待补数据伪装为可在当前 244 快照内完成的代码任务。P4 和本批改动仍在本地，未包含在此前已推送的 `2202c7c` 中。
