# MTC P4：paired244 执行链验收

本报告描述首轮 P4 v1 的冻结验收。后续 v2 首批见 [首批报告](../mtc_rule_backlog_20260922/REPORT.md)；当前 v3 共 57 项可执行，研究已在现有资源内收尾，P5 补采取消，见 [最新报告](../mtc_closed_resource_20260922/REPORT.md)。不要把本页历史的 48/37 数量或后续补采安排当作当前状态。

2026-09-22，状态：**P4 已完成**。先按用户要求把 P0–P3 的 55 个文件提交为 `2202c7c0d6630515693f3561cfd6dfa1d4b7c12c`，推送到 `origin/main` 并核对远端一致，然后开始本阶段。P4 改动目前保留在工作区，未包含在上述提交中。

本阶段将 Browser67 接入证据、规则、检索、Verifier 和 DecisionTrace，落实 P3 的旧规则处置。没有启动本机后端或 ngrok，没有改原始数据、切分、P3 筛选条件或规则容差，也没有解锁保留验证集。

## 执行结果

权威验收输出为 `hybridguard_agent/artifacts/mtc_p4_runtime_20260922_release/`。

| 验收项 | 结果 |
|---|---|
| 输入 | P2 发现 630 条／610 组，开发 144 条／142 组；共 774 个代表记录 |
| 两种输入视图 | Full244、App177 各运行 774 次，共 **1,548 次成功执行，0 失败** |
| P3 表达式兼容 | **23,220 次**逐项结果对照，0 语义变化；源不可用的 UNKNOWN 可明确细分为 NOT_EVALUATED |
| Browser 消费与隔离 | **9 项**已注册检查依赖 Browser；App177 的 **6,966 次**相关检查全部 NOT_EVALUATED，used_fields 为空 |
| 证据数量 | Full244 保留 244 个字段位置；App177 仅保留 177 个，不保留隐藏 Browser 值或状态 |
| 自动验证 | **48 项测试通过**：14 项新 P4 边界、34 项旧 App177／官方关系／旧桥接／消融兼容回归 |
| 禁止越界 | 保留特征解码 0、模型调用 0；不输出风险分数或攻击检测指标 |

开发验收中修复了输入文件句柄管理和非法状态类型保护，并补齐检索卡的固定容差／传感器类型参数，随后完成最终验收；各轮逐规则结果统计一致。较早的 `mtc_p4_runtime_20260922/`、`mtc_p4_runtime_20260922_final/` 均标记为已被后续验收替代，原输出保留；以 release 目录为准。

以上是执行能力和兼容性验收。Full244 与 App177 的差异不能直接解释为检测收益；尚无独立攻击标签，不能据此报告误报率、召回率、F1 或泛化能力。

## 新证据合同

`evidence-bundle-v3-paired244` 保留四个互不覆盖的表面：

- `app.android_native_data.*`：Native84。
- `app.webview_data.*`：宿主 WebView26。
- `app.web_data.*`：App Web67。
- `browser.web_data.*`：独立 Browser67。

输入必须声明 P1 的 `hybridguard-mtc-observation-v2` 合同，字段只能来自 244 目录。P2 loader 先按冻结清单校验代表记录及双端绑定；运行时再投影指定输入视图，之后才读取这些表面的值、状态、质量和 Browser 配对信息。实际 Browser 字段还要求 completed pair 及 App／Browser 回执、会话、payload 绑定信息。任意调用方自行拼出的 inline 对象不等于已经通过原始回执校验。

分组、机型画像、sample ID、session/receipt ID、标签和 scenario 不进入规则、检索或证据摘要。运行时样本 ID 由投影内容生成，实验 sample/group/split 仅由验收程序在执行之后外部关联。App 与 Browser 的解析 UA 事实也分别命名，不能覆盖对方。

状态和质量分开处理：unsupported、permission_denied、timeout、源缺失、deviceMemory／cores 的零哨兵、非法类型和非有限数不能产生冲突；合法 touch=0、false 和有语义的空列表保持原义。源不可用为 NOT_EVALUATED，解析不明确为 UNKNOWN；sensor 的 false 前提和可能简化的 UA 为 NOT_APPLICABLE，不算一致票。

这个新合同用于本地离线执行，保留投影后的指纹原值以执行精确谓词；它不宣称像旧 v2 一样隐藏全部 UA 等指纹值。检索与 trace 只引用字段路径和规则，不复制这些原值；完整原值只在本地 evidence 示例及原快照中。没有向外部模型发送数据。

## 旧规则处置与当前数量

新台账有 **87 个目录条目**，其中 **48 项可执行检查、2 项停用、37 项尚未实现**。这是目录／执行数量，不是 87 或 48 条独立、已验证的攻击规律。

48 项由旧规则 18 项加 P3 30 项组成；按来源为 20 项经验／历史设备检查、22 项官方派生检查、6 项采集器自洽检查。自然语言旧条目没有被自动当成已执行成功，P3 落选和描述性模板也没有趁运行时接入时晋级。

- **CORE-002 改写：** 仅检查 FeatureApp bridge。传感器数量低不再触发否决，也不会导致后续规则跳过。传感器数量仍是原始能力事实，不生成攻击标签。
- **WVWEB-001 与 OFFDER-WEBVIEW-001 停用：** 两者都基于不成立的 provider 包版本首段＝Chromium major 假设。后者原来可执行，前者原来只是未实现的目录条目，因此活跃旧实现由 19 减为 18。它们不进入检索证据卡或风险解释。
- **P3-PROVIDER-PARSE 保留：** 包版本首段解析仍可检查采集器是否自洽，但不比较 Chromium 版本。
- **其他历史检查保留来源和限制：** 零违反不代表已经验证检测能力。开发配置、ADB／电量、测试环境等仍只是上下文。

相似关系按 `evidence_family` 标明共享证据，包括 Native/App OS、bridge、UA、screen 等。由于部分表达式在缺失语义、适用性或字符串空白处理上有差别，不凭名字相近强行合并。所有关系独立留痕，但不把它们累加为独立风险票；融合及权重关闭。完整逐项处置见 [RULE_INVENTORY.md](RULE_INVENTORY.md)。

## 规则、检索、Verifier 与 trace

`paired244_rule_catalog.v1.json` 是新链唯一执行目录；`paired244_browser_relations.v1.json` 明确 9 项 Browser 依赖和限制，加载时校验与目录一致。P3 的 30 项依赖、参数和表达式保持冻结；旧规则通过有版本的适配器执行，历史引擎本身未修改。

执行器只将各规则声明的字段传给谓词；每个结果区分 required_fields 与实际 used_fields。缺失字段可以出现在 required_fields，但不能被伪装为已经使用。全部 ACTIVE 项均执行，不启用短路。

检索按当前规则精确选取 48 张卡，卡中标明来源、当前谓词、固定参数、版本和限制；不引用停用关系的旧风险文案、不读标签或经验案例、不因截断丢失已引用规则。缺失 Browser 时可以检索该规则的适用性说明，但 Browser 字段不会进入 observed query 或 used_fields。

Verifier 检查命名空间、输入视图、配对准入、字段引用、证据绑定和当前规则卡，并重新执行谓词核对结果与决定。测试已证明错误的 App/Browser 引用、伪造结果、改变来源标签、伪造风险分数会验证失败。这里验证的是程序与证据的一致性，不是现实世界攻击真值。

DecisionTrace v2 包含规则／证据／Browser policy／检索／Verifier 版本，全部检查结果、字段和卡引用、决定及验证项。决定只有关系偏差、采集器自洽问题、上下文、部分可评估或未见偏差；`attack_classification=NOT_EVALUATED`，校准风险分数为 null。状态 completed 表示程序运行完成。

## 入口与产物

旧 App177 的 `analyze_payload` 和旧 snapshot CLI 保持 v1 行为，包含历史短路，供历史重放使用；P3 的处置只在显式 P4 新链生效。`analyze_payload` 接收到 P1 v2 record 时会路由新链；直接接口为：

```python
from hybridguard_agent.runtime import analyze_paired244_record
full = analyze_paired244_record(p1_record, input_view="Full244")
app = analyze_paired244_record(p1_record, input_view="App177")
```

正式工程验收使用冻结 P2 清单，不直接遍历全量 P1 文件：

```bash
python3 hybridguard_agent/scripts/run_mtc_p4_runtime.py \
  --out-dir hybridguard_agent/artifacts/mtc_p4_NEW_RUN
```

只允许 discovery/development，不提供 reserved 选项，输出目录必须不存在。CLI 将执行失败写入失败结果与 FAILED summary，保留在尝试分母，不静默删除。

最终目录含 `results.jsonl`（1,548 次结果）、`decision_traces.jsonl`（同数完整 trace）、`rule_summary.json`、4 个按固定首条代表生成的 evidence/context 示例、目录／policy／schema／当前实现副本。原始数据和这些大体积逐样本产物继续留在本地忽略目录；可提交的总结见 [P4_SUMMARY.json](P4_SUMMARY.json) 和 [VALIDATION.json](VALIDATION.json)。

后续为 P5 的真实受控两态数据与 P6 的正式评价协议／实验。P4 没有补造攻击样本、拼接旧 App 与新 Browser，也没有把合成边界测试称为真实设备攻击验证。
