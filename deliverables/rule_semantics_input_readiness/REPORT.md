# 现有监督材料的输入接入核查与报告器修复

现有材料能找回两个模块真正需要的历史输入。权威清单中的 **162/162 条记录均具备语言首项模块和 webdriver legacy 模块的后续求值条件**；本轮只核对来源、输入结构和无损转接，没有求候选结果。**raw 观察对象保存数为 0**，162 条都不能接入 raw 模式，也不能从旧 false 或 observed 状态恢复它。

主要限制是历史 raw 信息未保存，而不是语言数组已经丢失、缺少设备，或所有历史来源都无法关联。语言与 legacy 的有限来源关联有明确登记支持；“被测属性一定真实”“历史 APK 与源码逐字节等价”均不在结论中。

## 固定范围与实际结果

实际起始 HEAD：`1e34677f307fc33b0552dde0dc6a14c77018cb66`，已核对包含上一轮模块提交，未切换、重置或提交仓库。

范围只取 `hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/C_confirmation/input_manifest.json` 的 `supervised_ids`：162 项、162 个唯一 ID。它指定的 R04 `DATA_INDEX.json` 有 262 项，本轮精确选择其中162项。其余100个描述阶段、未标注 MTC 与其他 UNKNOWN 未进入字段分析或汇总。

| 接入模式 | 来源支持 / 条件性 / 未知 / 冲突 | 输入完整 / 缺失 / 有损 / 格式异常 | 可接入 / 条件性 / 阻断 |
|---|---:|---:|---:|
| LANGUAGE | 162 / 0 / 0 / 0 | 162 / 0 / 0 / 0 | 162 / 0 / 0 |
| WEBDRIVER_LEGACY | 162 / 0 / 0 / 0 | 162 / 0 / 0 / 0 | 162 / 0 / 0 |
| WEBDRIVER_RAW | 0 / 0 / 162 / 0 | 0 / 162 / 0 / 0 | 0 / 0 / 162 |

raw 的来源轴“未知”专指缺少 raw observer/realm/per-read 观察合同；不否认同一记录的 legacy 采集路径已知。其输入轴记“缺失”，因为所需观察对象从未保存；旧 strict-true 投影的信息损失另列为不可逆限制，不将它误计为 legacy 输入不完整。

162 个 ID 的索引、适配输入、raw session 与来源映射均精确命中，没有缺文件、损坏格式、记录身份冲突或冲突原始来源。三个所需字段的保留值、类型、语言数组顺序、原始状态及适配质量映射核对全部通过。三字段的已保存状态/质量均为 observed / observed_value；这只是旧输入可用性，不是新的语义结果。

接入判断固定后才汇总已有元数据：clean_pre、attack、clean_post 各54条，三个环境组分别27、18、117条；14个配置、18个来源包，各模式接入计数见 SUMMARY.json。18个包共同登记同一 FeatureApp code 10 构建，不是18种构建。没有因记录含受控干预而排除它。

完成状态：

- audit_execution = COMPLETE
- language_readiness = READY
- webdriver_legacy_readiness = READY
- webdriver_raw_readiness = BLOCKED

## 来源链与证据边界

每条 INPUT_MANIFEST.jsonl 都保存精确引用：

`监督 ID → R04 data/current + data/evaluation → R04 snapshot 的 CACHE_LINEAGE → S02 input_manifest 的 opaque_id → inference_inputs 的固定行 → raw_payloads 的 session_id/行 → paired_triplet_run 的同一 session`。

R04 的 `features` 是关系原子、控制特征及编码，不能充当原始字段。上游 S02 的 `features/field_status/field_quality` 才保留所需适配输入；其 raw 引用以 `hybridguard-browser-fingerprint-research/` 为根。来源追踪没有重新生成 R02 缓存或执行旧提取器。

SOURCE_BINDINGS.json 按18个来源包登记证据与范围，共用的关键证据包括：

- `featureapp_current_release_lock_v1.json`、各包 `paired_triplet_run.json.featureapp` 和逐会话采集元数据，将构建关联到历史提交 `3a16d89363c86f7ad487c5b12c764521390ea44c`、已保存 WebView 控制补丁及 app code 10。对已有 APK/catalog 标识只作登记字符串核对，没有重建或重新哈希。
- 该历史提交的 `expanded_probe.html` 391–408 行：同一同步 Navigator probe 从同一 `nav` 读取语言两字段；154–156 行复制数组并保序，849 行调用该 probe。不是按值相似或语言是否一致来判断上下文。
- 625–672 行采集 `navigator.webdriver === true` 投影；187–197、338–346、854 行展示整组 automation 的 fallback。组内其他读取失败可使先前信息丢失，历史 false 不足以反推 getter 原值、API 存在性或原始 typeof。
- 历史 `FieldStatusReporter.kt` 的层/probe 状态传播，以及提交 `b3d8badee44577787bdcd3cb22d70a155b1bb613` 的适配器，解释状态来源、直接复制值与数组顺序、quality 派生规则。相关 quality 是 S02 根据明确状态派生，不是 raw 原生质量字段。

原语言采集存在 `|| ''`、`|| []` 的 falsey 哨兵处理；本轮保留的是当时采集下来的字符串和数组，不承诺恢复 getter 的所有原始类型。当前162条具备必要结构，不代表标签一定落在新模块支持域，也不预判一致/不一致。

这些登记足以支持“这条记录来自哪种有限采集/转换路径”，不需要额外设备认证或逐条签字。它们不证明被测属性未受干预，也不是完整历史二进制证明。raw 所缺的原始观察对象、presence/getter 状态、原始类型及 observer/realm 关联均未被补造。

## 可复用转接与执行边界

新增纯转接代码 `hybridguard_agent/research/rule_semantics_input_readiness.py`，以及本目录 `audit_inputs.py`。只显式复制必要字段，保留类型、数组顺序、status/quality；不引入 ID、标签、phase、配置、工具或旧预测作为 payload 特征。SourceBinding 在 payload 外，仅针对已登记且来源支持的范围构造。条件性、未知、冲突来源不能得到有效绑定。

下面是下次授权时可使用的 loader；只构造输入，不调用语义函数：

```python
from deliverables.rule_semantics_input_readiness.audit_inputs import InputAudit

audit = InputAudit()
# sample_id 必须来自权威 supervised_ids，不能从 DATA_INDEX 全集任取。
item = audit.load_input(sample_id, "LANGUAGE")
payload = item["payload"]
binding = item["source_binding"]
readiness = item["audit"]
```

不会写出162份完整 payload。逐记录表保存引用、检查结论和原因；loader 在内存构造最小输入。缺键不填 false/空串，未知状态不变成 observed。raw 缺失的转接一致性通过只表示“仍然缺失”，不表示 raw 可接入。

本轮真实审计未调用 `web_language_first_difference`、`webdriver_reported_state` 或任何 fit/predict/batch。synthetic 集成测试将新候选入口设置为一调用就报错，验证定位/核查/转接路径的调用数为0。语义模块人工回归和真实记录审计使用独立脚本路径。

为定位来源读取了含历史标签的 R04 evaluation，以及含评价信息的来源登记；不声称“完全没见过标签”。判定函数与来源核对只使用所需字段、明确引用和采集元数据，已有 phase/config/environment 只用于事后分层。这批材料保持已暴露开发材料身份，没有重新获得盲测资格。

## 报告器修复与实际验证

唯一修改的既有文件：`deliverables/rule_semantics_revision_module/run_checks.py`。修复前实际复现两种错误：首类 setUpClass 失败引发 `NoneType.update` 异常；一个 PASS 后另一类初始化失败会错误修改前一个测试结果。

修复后按传入对象身份归属，fixture 事件与普通方法单独记录；覆盖 class/module 初始化与清理、类级/普通/subtest skip、多个错误及批准示例未执行的真实缺口。fixture 错误令总报告 FAIL、退出非0；故意失败的内部 fixture 是外层回归的预期结果，不混作项目测试失败。

实际最终命令（重新保存时使用新输出路径，已有报告拒绝覆盖）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_input_readiness/run_checks.py --output deliverables/rule_semantics_input_readiness/TEST_RESULTS.json
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/rule_semantics_input_readiness/audit_inputs.py --output-dir deliverables/rule_semantics_input_readiness
```

第一条退出0：**96项独立测试全部通过，0 failures、0 errors、0 skips**。其中原语义模块34项、临时 Git 设计校验14项、报告器13项、纯转接21项、临时输入树集成14项。266次子测试另列，不重复加到独立方法数。24个批准示例全部实际执行且唯一覆盖；其原规格 executed=false 及旧测试报告保持不变。

第二条退出0：**162条只读实际审计完成**，结果见 INPUT_MANIFEST.jsonl 与 SUMMARY.json。审计脚本开发中通过人工边界发现并修正坏 map 导致整批中断、将缺失误归来源冲突的问题，三项针对性回归已加入最终测试。真实记录的首次核查也是 COMPLETE，没有通过改变规则或排除记录凑齐分母。

未重跑旧训练、模型预测或研究实验。未修改旧数据、模型、标签、阈值、冻结结果、关闭状态、历史调查设计和报告；用户既有无关改动保留。历史报告中的“当时尚未提交”文字未改写。

## 下一步决策

可以在下一次明确授权后，固定这162个 ID、当前两候选版本与本轮登记，执行 **LANGUAGE 和 WEBDRIVER_LEGACY 的有限求值检查**，记录逐条返回状态/原因，并保留与旧 W03 的证据重叠说明。该求值尚未执行；本轮不需要再做泛泛来源调研，也不扩大到训练。

raw 模式仍不进入后续历史求值：缺少的具体证据已定位为历史未保存的独立 raw 观察及 observer/realm 关联。已查 raw_payloads、S02 输入、采集历史源码、控制补丁、release lock 和逐批次 run 登记；无法从现有 strict-true 布尔投影恢复这些信息。

本轮真实 fit=0、模型预测=0、新候选真实求值=0、新采集=0。接入 READY 不等于能检出攻击，本轮没有新的 T/F/U 分布、TPR、FPR、准确率或模型 decision coverage。

建议 commit message：`feat(research): audit supervised input readiness and fix fixture reporting`。

完成后停止等待审查；未 commit、push 或创建 PR。
