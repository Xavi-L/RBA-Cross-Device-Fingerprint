# 本轮模型、数据及正常采集依据

本轮是**既有 MTC 真机数据上的补充回放评估**。MTC 已参与早期关系发现、开发和评价；历史 `reserved_validation` 名称原样保留，不能解释为从未使用的独立盲测。本轮用户授权运行全部 P2 主代表及辅助记录，没有重新分组、挑选设备、建立训练集或调整规则。

三个固定 WEBGL50 / CAP8 / RETENTION 模型的标识、路径和原规则见 [MODELS.json](MODELS.json)。该清单在查看本轮检测结果前确定；逐模型输出，不选最好的一折，不投票，不把三个模型的评估次数加成独立样本数。历史观测适配器版本与原模型身份分别记录。

## 数据成员和分母

入口读取 `hybridguard_agent/artifacts/mtc_p2_frozen_20260922/sample_registry.jsonl`，按其 `source_view + source_line + sample_id` 绑定 P1 最终快照。保留既定用途、组别、split 和源记录顺序，不以报警、字段值或计算便利性改变成员。

| 本轮子集（P2 原用途） | 预定／可读记录 | 厂商＋型号＋Android release 组合 | 用途 |
| --- | ---: | ---: | --- |
| 主代表 `primary_representative` | 891／891 | 891 | 主分析；原 P2 每组合最早合格配对 |
| 配对重复 `paired_repeat_observation` | 137／137 | 104 | 补充；不增加主分析独立支持数 |
| App-only `reserve_app_only_177` | 654／654 | 324 | 补充；App 观测可用，不要求独立 Browser |
| 部分记录 `reserve_partial` | 11／11 | 2 | 单列；11 条 App host/Web 整层超时 |
| 同 session 额外观测 `reserve_repeated_observations` | 6／6 | 5 | 单列；来自 5 个已有 session |
| P1 隔离视图 `quarantine` | 0／0 | 0 | 单列盘点 |

共 1,699 条 App 原始观测、1,693 个 App session、906 个型号／系统组合。组合数不能在各子集之间相加，也不能解释为独立物理设备数。P1 的 `paired_244` 共 1,028 条，恰由 891 主代表与 137 配对重复构成。主代表原 split 为 discovery 630、development 144、reserved_validation 117；本轮保持不变。App-only 含 15 个未完成配对的型号／系统组合，其余与配对数据重叠。

读取结果为 1,699／1,699，源文件损坏、丢行或绑定失败为 0。11 条整层超时记录仍回放并单列，不能因为有 Native 或独立 Browser 观测而填补其缺失的 App Web。加载器保留读取失败的 P2 成员和错误原因；若原始 App 依据材料缺失而 P1 仍可读，继续预测，仅将正常依据置为不足。P2 成员清单损坏时保留未分配占位，不重新挑代表。

原始值来自 `mtc_paired244_v2_20260922_final` 的 `features`、`field_status`、`field_quality`；逐行原始 App/Browser 引用指向 `backend_server/collection_backups/mtc_final_20260922/sources/`。无须复制完整原始数据。旧 `unlabeled` / `unknown` 标签、历史任务准入状态和数据文件均不改写。

## 本轮的正常条件及证据

“正常”仅指**执行常规采集，没有实施本研究定义的目标指纹篡改**。允许设备调试连接、debug 签名 App、MTC 控制代理及自动化组件；正常记录不必符合检测规则。不能因模型报警改标攻击。

本轮新增 `normal_basis` 侧表状态 `research_normal_condition_supported`，依据如下：

1. [MTC 采集操作流程](../mtc_20260916/百度MTC采集操作流程说明.md) 的任务是安装启动采集 APK、处理独立浏览器引导、等待上传配对和记录失败；没有目标指纹篡改步骤。该文件给出平台流程伪代码，未把伪代码冒充供应商最终执行脚本。[完整需求](../mtc_20260916/百度MTC云真机采集需求说明.md) 明确保留原系统/WebView/浏览器，并指出云测控制环境不自动表示攻击。
2. [v9 提测说明](../mtc_20260917/提测说明.md) 将正式来源单独置于 `collection_runs/mtc_20260917`，网页自测另行隔离；[v11 提测说明](../mtc_20260921_https/提测说明.md) 记载改动为 HTTPS/TLS 兼容与域名，指纹字段及配对算法未变，合成链路检查在隔离目录，不计正式采集。
3. 最终留存 `sources/collection_batches.jsonl` 第 3–4 行对应批次 `hgbatch-v1-20260917T030653431925Z-6e31771d4a`：486 条 App 原始归档，全部 versionCode 9；第 5–6 行对应 `hgbatch-v1-20260921T040430015520Z-14ed4645c6`：1,213 条归档，全部 versionCode 11；两批次均 `closed_cleanly`。前两行另一个空批次无数据。这里只核对来源关联和行数，未重新做密码学完整性审计或采购对账。
4. 逐记录核对既有 raw 行的 session、已保存 payload 引用、批次及 collection manifest，与 P1 引用对应；全部为 `featureapp`、`featureapp-collection-protocol-v3`、`expanded-web-67-v1`。本轮正常依据不读取预测结果或用于分组的型号字段。
5. `FREEZE_MANIFEST.json` 记录来源截止 `2026-09-22T08:39:43.167513Z`、仓库参考 `134201114a8a15a682bb41ee94c796d14e550c9e`。该提交的 `MainActivity.kt` 将 Native、host、Web 采集值与状态直接组装落盘并上传；`expanded_webview_adapter.js` 调用共享 `HybridGuardWebProbe.collect`。历史 `web_probe/canonical_web_probe.js` 的同步 navigator 读取、`navigator.webdriver === true`、`deviceMemory || 0` / `hardwareConcurrency || 0` 是本轮 legacy 映射依据，不能使用今天已新增 raw observer 的脚本去解释旧记录。

按上述有限研究依据，1,699 条均有本轮正常条件支持。这是任务、采集实现和留存批次支持的研究侧表，**不是逐设备第三方无篡改认证**。本仓库所核对材料未提供供应商最终自动化脚本及逐设备完整操作录像；原始 manifest 的 `runtime_context` 均为 `unspecified`，没有据此杜撰 MTC 任务 ID。两个后端批次 ID 是来源标识，不等于供应商任务 ID。若未来有相反过程证据应更新侧表依据；不能以规则触发本身否定正常依据。

因此报告可称“有本轮正常采集依据记录中已观察到的报警比例”。大量规则未知时，它不是完整模型已验证的零误报率；未知和执行失败不计作正确正常。若某条来源依据不足，仍运行并报告报警比例，与上述有依据分母分开。

## 最小复核方式

从仓库根目录只读复核数据数量（不运行预测器）：

```bash
python3 -c 'import json; from hybridguard_agent.research.mtc_cap8_data import load_mtc_replay_data; d=load_mtc_replay_data(); print(json.dumps(d["inventory"], ensure_ascii=False, indent=2)); print(d["issues"])'
```

历史采集源码可用 `git show 134201114a8a15a682bb41ee94c796d14e550c9e:web_probe/canonical_web_probe.js` 查看。真实回放、从保存结果重汇总及结果解释见 [REPORT.md](REPORT.md)。
