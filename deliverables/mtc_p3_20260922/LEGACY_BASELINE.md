# P3 旧规则诊断基线

2026-09-22：旧目录与旧执行实现先冻结，再完成无标签重放。旧实验效果不作为新版目标，也不把旧结论视为当前有效。此报告只描述旧规则在当前发现／开发材料上的可执行性、触发、未知及适用性问题；没有 FPR、TPR、F1 或攻击排名。

## 输入与隔离

只使用 P2 正式目录 `hybridguard_agent/artifacts/mtc_p2_frozen_20260922/` 的两张输入清单：发现集 **630 条／610 组**，开发集 **144 条／142 组**。共享入口只解析被这两张清单选中的 P1 行；保留验证集未读取、未评价、未解锁。P2 分组、种子、代表选择不变。没有启动后端、ngrok 或模型。

旧引擎输入仅由 App177 的三层值与显式 source status 构造；Browser67、安装／机型分组、split、标签和攻击元信息不进入旧谓词。`collector_app=featureapp` 与 schema 常量来自 P1 来源合同，仅满足旧采集路径关系。机型及分组只用于分母和外部结果定位。

## 冻结目录及执行口径

旧 device-mined 目录共有 **35 条**，其中 **10 条**有编译谓词，其余 **25 条 NOT_EXECUTABLE**；official-derived 目录 **22 条**中 **9 条**可执行，其余 **13 条 NOT_EXECUTABLE**。不可执行条目逐样本列明，在逐规则汇总中保留全部分母，不计为通过。

- `legacy_ordered`：直接执行原 deterministic 引擎，保留 CORE-002 短路，后续规则记录 `not_evaluated`。
- `legacy_independent_diagnostic`：调用相同旧谓词逐条诊断，说明短路之后哪些关系还能判断；这不是旧部署执行顺序。
- `legacy_original`：直接执行原 official semantic evaluator。
- `availability_gated_diagnostic`：在独立诊断／官方原结果上要求输入有明确 observed 状态、P1 quality=observed_value，缺失或已知 sentinel 记未知。没有改谓词、阈值、风险类型或旧引擎。

“违反”表示某关系的条件被触发，“条件未违反”不等于安全或正常。开发配置、ADB、电池、安装来源等 context 单独计数。unknown、unavailable、not_evaluated、not_executable 不进入可评估分母；not_applicable 也不当作通过。分组计数按唯一组去重；同组不同 OS 的类别可以重叠，不能将各类别组数相加当总组数。

## 两源结果

下表是可用性门槛后的独立诊断；原有短路模式另行保留。表内“未见违反且编译项完整”仅覆盖已编译部分，不包含其他不可执行目录项。

| 来源 | 集合 | 有违反的记录／组 | 未见违反但部分编译项未知（记录） | 未见违反且编译项完整（记录） |
|---|---|---:|---:|---:|
| device-mined | 发现 | 12／12 | 5 | 613 |
| device-mined | 开发 | 2／2 | 0 | 142 |
| official-derived | 发现 | 32／31 | 45 | 553 |
| official-derived | 开发 | 9／9 | 6 | 129 |

编译关系逐条统计如下。数值是“可评估记录／可评估组；违反；未知或未评价；context”；条件未违反项可由分母扣除。此处没有将 context 算作违反。

| 来源 | 规则 | 发现 | 开发 |
|---|---|---|---|
| device-mined | CORE-002 | 630/610；12；0；0 | 144/142；2；0；0 |
| device-mined | NVW-002 | 627/607；0；3；0 | 144/142；0；0；0 |
| device-mined | NVW-005 | 628/608；0；2；628 | 143/141；0；1；143 |
| device-mined | NW-002 | 630/610；0；0；0 | 144/142；0；0；0 |
| device-mined | NW-006 | 630/610；0；0；0 | 144/142；0；0；0 |
| device-mined | NW-007 | 630/610；0；0；0 | 144/142；0；0；0 |
| device-mined | PHYS-005 | 630/610；0；0；457 | 144/142；0；0；96 |
| device-mined | PHYS-006 | 630/610；0；0；6 | 144/142；0；0；0 |
| device-mined | SCENE-001 | 630/610；0；0；589 | 144/142；0；0；125 |
| device-mined | WVWEB-004 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-BRIDGE-001 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-DEVCONFIG-001 | 628/608；0；2；628 | 143/141；0；1；143 |
| official-derived | OFFDER-GPU-001 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-OS-001 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-OS-002 | 627/607；0；3；0 | 144/142；0；0；0 |
| official-derived | OFFDER-TOUCH-001 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-UA-001 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-UA-002 | 630/610；0；0；0 | 144/142；0；0；0 |
| official-derived | OFFDER-WEBVIEW-001 | 588/571；32；42；0 | 138/136；9；6；0 |

原有 deterministic 顺序下，CORE-002 在发现 12 条、开发 2 条触发后，其他 9 条谓词分别跳过 12／2 次。不能把 126 次短路跳过当作其他规则的正常通过。独立诊断用于补充这一可执行性事实，没有覆盖掉原顺序结果。

可用性门槛没有改变本批资料“可评估／违反／未知”的分类或发生违反的样本数；它将发现／开发 2／1 条 cleartext 的 unavailable（两源各一条关系）和 42／6 条 provider major 的 unavailable 明确标成 unknown_availability_gate。另有发现集 3 条 `system_http_agent` 无法解析 Android major，依然 unknown。P1 已知的 device_memory/hardware_concurrency 零回退不属于这 19 条旧谓词的输入，故不能由此声称旧引擎已经全面解决 sentinel。

## 反例解释与旧规则处置

**CORE-002 的 14 次触发全部来自 sensor_total_count < 10（实测 1–9），JSBridge 均为 true。** 本轮材料没有提供这些设备的攻击或无主动干预标签。低传感器数量应作为设备能力／上下文描述，不能把旧 `<10` 阈值直接用于未标注 MTC 的攻击判据。原始规则和历史短路实现保留用于诊断，不在本任务暗改部署。

**OFFDER-WEBVIEW-001 的 41 次违反全部满足 default UA、settings UA、App runtime UA 三者字符串完全一致；其 provider_major 都等于包 versionName 的首段，却不等于 UA 内的 Chrome major。** 来源代码 `ExpandedFingerprintCollector.kt:224–228` 将 `webview_provider_major` 设为 `parseMajor(webViewPackage.versionName)`；`parseMajor` 在第 435 行实现。当前字段表示 provider 包版本首段，并不保证共享 Chromium 的版本命名空间。此代码事实与现有反例共同反驳“所有 provider 的包版本首段都等于 Chrome major”的无条件关系。

| Provider 包 | 发现反例 | 开发反例 | 包版本首段 → UA Chrome major | 数据解释 |
|---|---:|---:|---|---|
| com.huawei.webview | 29 | 9 | 11–15 → 83–114 | vendor package version 与 UA 引擎 token 不同命名空间 |
| com.hihonor.webview | 1 | 0 | 1 → 116 | 同上，1.0.1.308 不是 Chromium 1 |
| com.android.webview（smartisan） | 2 | 0 | 4 → 62 | 即便常见包名也不能保证 versionName 首段可当 Chromium major |

上述解释针对观测字段的语义，不证明 APK 内实际 Chromium 二进制版本，也不证明设备安全。不能只按包名加入豁免，尤其两条 smartisan 反例说明包名本身不足以界定版本语义。

可定位的例子：

| 机型／Android | provider version（versionCode） | provider major | default/settings/runtime Chrome major | App raw 行／pair ID |
|---|---|---:|---:|---|
| HONOR ALT-AN00／14 | com.hihonor.webview 1.0.1.308（584511401） | 1 | 116／116／116 | 964／hgpair-v1-015aa32174a9397deb52c6bc |
| HUAWEI DCO-AL00／12 | com.huawei.webview 15.0.4.326（21311） | 15 | 114／114／114 | 1461／hgpair-v1-0d2ce54eac9ebbc9576227d0 |
| smartisan OE106／8.1.0 | com.android.webview 4.4（15） | 4 | 62／62／62 | 221／hgpair-v1-5d25a14a8823624f4e198dcb |

完整 41 条 provider 诊断保留必要原始值、状态、quality、机型版本、分组与源行引用；55 条两源违反实例均保留，未挑选性删除。

| 旧规则范围 | P3 处置 | 依据与限制 |
|---|---|---|
| CORE-002 sensor 分支 | 不晋级为新版攻击判据；保留能力／上下文诊断，桥接分支单独分析 | 14 条触发均为低传感器数，缺乏独立攻击标签；旧阈值和短路收益未获证明 |
| OFFDER-WEBVIEW-001 | 不保留跨 provider 无条件包版本首段＝UA Chrome major 的风险解释 | 41 条有状态支持的命名空间反例；后续必须有明确字段语义和版本范围，不能按现有反例简单调阈值或包名豁免 |
| NW-002 / NVW-002 / NW-006 / NW-007 / WVWEB-004；OFFDER-OS/UA/TOUCH/BRIDGE/GPU 已编译项 | 保留为待独立验证的历史假设／诊断，不因零违反认定已验证规则 | 当前没有攻击真值；Android UA 可解析边界仍有 3 条未知；没有外部或保留集支持 |
| NVW-005 / PHYS-005 / PHYS-006 / SCENE-001；OFFDER-DEVCONFIG-001 | context 独立报告，不并入攻击效果 | 开发构建、ADB、高电量等是采集环境观测，不是攻击标签 |
| 25 条未编译 device-mined、13 条不可执行 official 关系 | 继续 NOT_EXECUTABLE／待语义、谓词或缺失证据 | 不由检索卡片存在推断已运行，更不以未知代替正常 |

这些处置是新版候选准入建议；没有修改旧执行器、旧配置或历史目录。P4 若集成新执行路径，仍需明确采纳版本和边界。旧/new 数量与触发数不是优化目标。

## 产物与复现

正式产物：`hybridguard_agent/artifacts/mtc_p3_legacy_20260922/`。

- `frozen_legacy/`：两个旧目录、两个旧执行器、extractor、适配器、rule KB、official cards、field registry 与来源合同副本。
- `runner.py`：冻结基线时的原运行器；`provider_diagnostic_runner.py`：后续纯解释诊断扩展的运行器副本，未改变基线结果。
- `sample_results.jsonl`：774 条逐样本、多来源、多执行口径结果，包含未编译 ID 清单。
- `rule_summary.jsonl`：298 条按 split／source／mode／rule 汇总，可评估、违反、未知、context 及组分母。
- `counterexamples.jsonl`：55 条独立诊断违反，保留必要输入、状态、quality 及样本引用。
- `provider_counterexample_diagnostics.jsonl`：41 条完整 provider 命名空间反例诊断。
- `summary.json`：冻结与运行范围、执行模式及未评价边界。

```bash
python3 hybridguard_agent/scripts/run_mtc_legacy_rule_baseline.py \
  --plan-dir hybridguard_agent/artifacts/mtc_p2_frozen_20260922 \
  --output-dir hybridguard_agent/artifacts/mtc_p3_legacy_NEW_RUN
python3 -m unittest hybridguard_agent.tests.test_mtc_legacy_baseline \
  hybridguard_agent.tests.test_official_semantic_relations -v
```

6 项新增边界与 8 项官方关系历史回归，共 **14 项测试通过**。覆盖输入隔离、叶字段冲突、已知 sentinel／缺状态／合法 false 和 0、旧短路与独立诊断区别、未知分母、组内去重、provider 版本命名空间及状态门槛。未训练模型，未计算检测效果，未评价保留集。
