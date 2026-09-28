# 两个离线语义模块与设计校验器修复

状态：MODULE_IMPLEMENTATION_COMPLETE_PENDING_REVIEW。

起始 HEAD 与批准设计提交均为 `8eeeb2238bd829a7078efe009c46e3e7f052c576`，包含设计起始基线 `c7e43762b429c0d3f7a0ee0e77101691b10b6be4`。本轮实现仍在工作区，未提交，不能声称新代码已属于起始 HEAD；实际文件摘要见 IMPLEMENTATION_MANIFEST.json。

## 实际实现

新增 `hybridguard_agent/research/rule_semantics_revision_v1/` 六个文件：公共 SemanticCell/SourceBinding、小型输入适配、语言首项关系、webdriver 独立解释器和静态 manifest。模块导入无网络、目录扫描、研究执行或报告写入；仅用标准库，没有接入旧矩阵、predictor、learner 或实验调度器。

语言 `RSR-LANG-FIRST-v1` 使用完整匹配的固定 ASCII 标签子集，只做小写归一，保留地区和脚本。比较 `language` 与 `languages[0]`；尾项原样复制到诊断中，其扩展或非法类型不改变首项结果。这既不是语言列表长度，也不是 B 的全列表 primary 成员关系，更不是 Native/Web 比较。一致改写仍可得到 F。

webdriver `RSR-WEBDRIVER-STATE-v1` 的 mode 由调用方显式选择，无自动回退。legacy 模式只解释旧布尔值与来源状态：true 为 T，false 为 U；raw 模式解析独立的新观察对象，分别处理存在性、getter、类型、realm 和 observer 关联。raw 成功结果不受旧 automation 组的后续 MIME 错误或 hash 错误影响。本轮没有实现任何新 JS 采集。

旧谓词 `P=(navigator.webdriver === true)` 的 F 原本可正确表示 P 不成立；新模块要求更细的原始布尔报告信息，因此 legacy false→U 是新的状态语义，不是修复旧标签或宣布旧谓词错误。新 legacy true 与 W03 共享信息，manifest 明确禁止当两份独立证据计票。

## 接口与来源绑定

这是新的最小输入契约 `rsr-input-v1`，不冒充旧 177 字段 schema。扁平字段模式只读取所需的 `features/field_status/field_quality` 键；缺无关字段不影响计算。raw 模式只读取 `web_data.automation_surface_layer.webdriver_observation`，不检查它不依赖的旧兼容字段。

```python
from hybridguard_agent.research.rule_semantics_revision_v1 import (
    SourceBinding, web_language_first_difference, webdriver_reported_state,
)

lang = 'app.web_data.navigator_layer.language'
langs = 'app.web_data.navigator_layer.languages'
payload = {
    'record_schema_version': 'rsr-input-v1',
    'features': {lang: 'zh-CN', langs: ['zh-CN', 'en-US']},
    'field_status': {lang: 'observed', langs: 'observed'},
    'field_quality': {lang: 'observed_value', langs: 'observed_value'},
}
# 仅为合成示例；真实调用方须依据自己的采集契约提供关联。
binding = SourceBinding('SYNTHETIC-contract-v1', 'navigator_sync_v1')
cell = web_language_first_difference(payload, source_binding=binding)
assert cell.state == 'F'
```

raw 示例（只构造人工观察，不调用浏览器）：

```python
raw = {
    'record_schema_version': 'rsr-input-v1',
    'web_data': {'automation_surface_layer': {'webdriver_observation': {
        'api_present': True,
        'presence_read_status': 'observed',
        'value_read_status': 'observed',
        'value_type': 'boolean',
        'boolean_value': False,
        'observer_revision': 'SYNTHETIC-observer-v1',
        'realm_binding': 'SYNTHETIC-realm-1',
    }}},
}
binding = SourceBinding(
    'SYNTHETIC-contract-v1', 'webdriver_raw_observation_v1',
    observer_revision='SYNTHETIC-observer-v1', realm_binding='SYNTHETIC-realm-1',
)
cell = webdriver_reported_state(raw, mode='raw_observation_v1', source_binding=binding)
assert cell.state == 'F'  # 只说明成功观察到报告false，不证明无自动化。
```

`SourceBinding` 由调用方在 payload 外显式提供；普通页面字典中的 `trusted=true` 或 `same_context=true` 不会得到资格。这个轻量类型只声明采集来源关联，不提供密码学证明，不证明 JS 属性未被篡改，也不自动为历史数据建立绑定。缺绑定/原始观察保持 U；raw 的 observer/realm 与外部上下文不符也为 U。

SemanticCell 的 value/available/evaluation_status 编码严格区分 T/F/U/FAILED；state 是派生属性，不重复存储可能互相冲突的状态。结果不包含 attack/clean 判定。结构/枚举失败优先，其余原因按固定处理阶段与字段顺序决定；可见问题保存在去重后的 diagnostics.issues，不增加样本计数。

## 小型接口歧义的明确处理

未改写已批准的设计 JSON 或文档。新接口作以下明确选择，并有边界测试：

- 顶层 `record_schema_version` 缺失/非法为 FAILED；新 schema 中相关值、status/quality 缺失或显式 null 视为缺证据 U。legacy 值 null 为 MISSING_FIELD，不强转成 false。
- 相关 status/quality 的非 null 非法枚举为 FAILED。已知来源 runtime_error/timeout 保留为 U，并保存 source_reason；不因一个已知 quality 值而凭空新增失败域。遵循已批准门控和旧 field_state 的来源不可用处理，不为两个枚举强加未批准的组合表。
- raw 的存在性/getter status 只接受设计登记的枚举；例如 raw `presence_read_status='timeout'` 是非法新结构，不能与 legacy 合法 timeout 状态混淆。若未来扩展 raw 超时状态，须另改输入契约。
- raw 没有另加重复 schema 字段，以顶层新 schema 与显式 mode 确定格式。缺成员为 U；已有成员即使另有缺项，只要形成不可能同时成立的元组，就返回 FAILED。存在性检查和 getter 是两次观察，不宣称原子性。
- 同一次来源的含义由外部 binding_scope 声明；未知内核不阻断字面语言关系或 webdriver 报告值。所有版本/来源字符串都不是可学习特征。

## 校验器修复

唯一改动的既有文件是 `deliverables/rule_semantics_revision/validate_design.py`。校验器分开记录设计起始基线、批准设计提交、验证 HEAD，核查祖先关系而非要求 HEAD 永远等于 c7e4376。对六个受保护设计文件与批准提交做逐字节比较；正常后继提交可通过，后继设计修订仍报告 VERSION_DIFFERENCE。缺 Git 历史明确 UNVERIFIABLE，不伪造通过。

默认输出完整 JSON 到 stdout，不写历史 VALIDATION.json；显式 `--output` 使用独占创建，拒绝覆盖任何已有目标。无关 staged/unstaged 状态只作诊断，不导致设计失败。Git 读取设置 `GIT_OPTIONAL_LOCKS=0`，避免 status 刷新索引元数据。回归测试使用真正的临时 Git 历史；只在临时夹具内创建测试提交。

## 实际测试和复核

最终组合命令（从任意工作目录可用，输出路径必须不存在）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/deliverables/rule_semantics_revision_module/run_checks.py --output /Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/deliverables/rule_semantics_revision_module/TEST_RESULTS.json
```

该 runner 只加载两个指定 unittest 模块，不做全库 discover；记录实际执行的测试方法、子测试及人工夹具返回值。也可直接运行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v hybridguard_agent.tests.test_rule_semantics_revision_v1 hybridguard_agent.tests.test_rule_semantics_design_validator
```

最终测试：退出码 0；48 个独立测试方法全部通过，0 failures、0 errors、0 skipped。另记 205 次子测试调用，不重复计入独立测试项数。覆盖所有 24 个已批准的语言/webdriver 示例及 13 个新增边界夹具；新增理由和 source_example_id 在人工夹具内，预期和实际返回值另存在 TEST_RESULTS.json。原设计示例的 executed=false 保持原样，其余四类候选未执行。性质检查覆盖大小写、尾项、键顺序、输入不变、无模式回退、无业务元信息参与和导入无副作用。T/F/U/FAILED 均可为正确的预期结果，不等同测试是否失败。

开发中曾发现并修复两类工程问题：校验器首次回归有 1 项索引字节保留失败，因 Git status 可选刷新而触发；模块测试首次有 3 个子测试期望与 null-as-missing 接口不一致，明确接口后修正测试，非 null 非法枚举仍验证 FAILED。最终结果不隐去这些修复，也不把初次失败算成最终通过。

修复后的设计核查命令：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/deliverables/rule_semantics_revision/validate_design.py --output /Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/deliverables/rule_semantics_revision_module/DESIGN_VALIDATION.json
```

本次设计核查：退出码 0，41/41 检查通过，从 /private/tmp 以绝对脚本路径执行。这是静态设计身份/一致性检查，与上面的模块人工执行结果分开；历史 VALIDATION.json 未覆盖。重新保存结果时请改用新的输出文件名。

## 交付边界

没有修改旧 V1/V2 源码、模型、阈值、标签、结果、关闭状态、原采集器或第一轮调查；现存无关本地改动保留。真实采集、fit、模型预测、真实记录候选求值均为 0，没有启动 V3、R10 或独立确认。

来源绑定仍须由未来集成方依据采集契约提供；历史 observed false 的原始状态不可恢复，历史 APK 适用性未核验。未来若接入 legacy false→U，可能减少完整 triplet 支持或增加弃判，本轮未计算真实影响。模块通过不证明真实误报改善。

- research_effectiveness=NOT_EVALUATED
- historical_record_applicability=NOT_AUDITED
- independent_confirmation=NOT_PERFORMED

建议提交信息（本轮不执行）：`feat(research): add offline language and webdriver semantics modules`。
