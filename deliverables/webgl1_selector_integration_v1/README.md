# WebGL1 接入与完整链路验证

本轮已接通 FeatureApp 默认采集 → 后端原样保存 → 原始输入校验 → WebGL1 候选编译 → 选择器规则池登记。状态为 **INTEGRATED / LOCAL_SMOKE_PASS / RETRAINING_PENDING**。这是新增可供学习的候选条件，尚未产生包含它的已训练模型。

FeatureApp 更新为 versionCode **14**、`1.6.7-expanded-v2.2-webgl1`。APK 在本机 `runtime/featureapp-v14-local-only.apk`，采用本地调试接收地址，不是供攻击侧同学连接公网服务的交付包。后续对外采集应使用相同版本的公网配置构建，并重新核对实际收件地址。

## 接入内容

- `expanded_probe.html` 加载现有独立观察器，App 适配器在常规字段采集完成后调用一次。原始结果写入 `collection_observations.webgl_parameter`，包含采集版本、读取状态、完整原始观测和错误原因。
- 原始观测保留 WebGL1 与 WebGL2 两个上下文。固定 177/67 字段目录、`expanded-v2.2-status` 和 canonical probe v2 保持不变。`app_web67` 是沿用的选择器 Web 表面名称；新增的是该表面的附加候选，不是篡改固定字段目录。
- 后端既有附加元数据通道可以保留这些数据，无需增加判定逻辑。已核对原始归档、合并会话、展平导出，以及重复提交与显式 null/错误的保存。
- 新模块 `hybridguard_agent/research/webgl1_selector_integration.py` 注册 `RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1`。实际基础候选池通过 **49 → 50** 的扩展检查；旧定义、旧实验分组、条数限制和评分不变，新候选没有额外质量加分或强制入选待遇。
- 调用方必须提供独立登记的来源和收件回执中的预期 session。GPU 字符串、Android API、环境、攻击工具、phase 和标签均不作为新增候选特征进入选择器。

冻结的观察器、原始双上下文评估器和 WebGL1 纯评估模块均未改写。纯模块中原有 `research_candidate_not_registered` 表示当时的独立模块角色；本轮登记身份由新接入模块及 `REGISTRATION.json` 明确提供。

## 判断边界

| 状态 | 含义 |
|---|---|
| T | 上下文和控制查询通过质量门后，至少一个 WebGL1 参数具有稳定且有效的数字/数字字符串查询矛盾；另一参数为 U 不抹除这个已验证矛盾 |
| F | WebGL1 vendor 和 renderer 的所需查询关系都一致；不能解释为设备安全或没有任何攻击 |
| U | 来源/会话/版本/信封或上下文/控制门失败；或者没有有效矛盾、且至少一项参数因读取失败或不稳定等而未知 |

WebGL2 的 UNKNOWN 或独有矛盾仅保留诊断，不能提供 WebGL1 的 T/F。U 在既有选择器的取反和 OR 逻辑中仍为未知，不能补成正常。旧 378 条材料缺少这项原始观测，不能回填或套用本次观测。

## 实测结果

协议在开始采集前保存于 `PROTOCOL.json`。使用同一已有 `webgl.vendor` 攻击配置，在四个既有模拟器环境中各执行一组全新正常、攻击、恢复过程，共 12 条；每阶段均使用新 App 进程。CDP 只负责一致的导航与攻击装载，**不注入或手动调用观察器**。

| 环境 | 实际 WebView | 正常 / 攻击 / 恢复 | 完整链路 |
|---|---|---|---|
| API29 / SwiftShader | 91.0.4472.114 | F / T / F | PASS |
| API30 / SwiftShader | 91.0.4472.114 | F / T / F | PASS |
| API36 / host | 134.0.6998.135 | F / T / F | PASS |
| API36 / SwiftShader | 134.0.6998.135 | F / T / F | PASS |

12 条均为 177 字段 observed，原始归档、合并与导出的附加观测完全一致；三种格式编译出的候选结果也一致。四组目标字段变化、恢复、WebGL1 观测恢复、数字查询与常规 WebGL 字段对应关系，以及其余十个图形字段保持不变，全部通过。

候选共 **8 F、4 T、0 U**。未修改的双上下文评估仍为 **6 MATCH、4 COUNTEREXAMPLE、2 UNKNOWN**；两条 UNKNOWN 来自 API36 host 的正常/恢复记录。它们完整保留，不声称修好了 WebGL2。

原始记录在 `runs/*/backend/raw_expanded_payloads.jsonl`；`RESULTS.json` 包含逐条、逐组结果；`SAVED_CANDIDATE_CELLS.json` 保存编译后的候选。旧图形审查范围为 5 个 Native + 7 个 Web 字段。初版分析器误取 Web 字典，该范围适配错误已在首次完整分析前修正，原代码及修正说明保留于 `source_snapshot/analyze.py`、`ANALYZER_CORRECTION.json`；采集数据、候选语义和预定验收条件均未改变。

重点测试：Python 38、Node 35、后端 3、Android 单元测试 44，共 **120 项通过**；APK 构建通过。`TEST_RESULTS.json` 记录日志位置。八个本轮进程均结束，四个本地端口均关闭，见 `CLEANUP.json`。

## 选择器调用接口

```python
from hybridguard_agent.research.webgl1_selector_integration import (
    SourceRegistration, compile_payload, register_definitions, project_rows,
)

# source_reference 来自独立审核的采集协议，不能取自 payload 的自声明。
source = SourceRegistration(source_reference="reviewed-new-cohort-protocol")
saved_cells = {
    sid: compile_payload(payload, expected_session_id=sid, source_registration=source)
    for sid, payload in receipt_indexed_raw_payloads.items()
}
definitions = register_definitions(base_semantic_definitions)
rows = project_rows(base_feature_rows, definitions, saved_cells)
# definitions 与 rows 可交给既有 approved_atoms / encode_train / V2Problem。
# 训练必须由下一项实验明确提供各折 train/test、标签侧表、容量和执行登记。
```

`project_rows` 要求基础行与保存候选具有完全相同的成员集合，不读取标签，也不会重新评估观测。实际接口测试覆盖保存单元与既有子句执行器的 T/F/U 兼容、结构身份、重命名不变性、旧语义键保持不变，以及错误编码拒绝。历史实验运行器保留原冻结分组；下一轮应显式采用新注册入口。

## 重训准备结论

**代码接入已完成，整体效果尚未评估。本轮模型拟合 0 次、完整模型预测 0 次。** 上面的 4/4 是一个攻击配置的链路验证，不是整体模型检出率或正常真机误报率。

下一轮需要建立含这项观测的完整新对照批次：用 v14 重跑既有可重复攻击配置，并在相同环境中采正常、攻击、恢复；独立核对干预效果和标签，再让“不加新候选”与“加入新候选”两组在**同一批新数据、相同划分、相同七条容量**下重训比较。冻结规则、划分与比较口径应在查看新批次模型结果之前完成。

已有旧数据仍可保留作历史参照，但不能拿旧批次分数与新批次分数直接相减来归因 WebGL1 的提升。缺少真机不阻断这项受控内部比较；它仍不能提供新增正常真机或独立确认结论。WebGL2 修复不构成本轮 WebGL1 接入或该比较的前置条件。

重算本轮保存结果：`python3 -B deliverables/webgl1_selector_integration_v1/analyze.py`。该命令会写回分析输出，并非纯只读检查。重新采集必须另建目录和协议，当前运行器会拒绝覆盖已有记录。协议中的复制残留与实际执行口径见 `PROTOCOL_ERRATUM.md`。本报告记述接入完成时的状态，后续提交信息以 Git 记录为准。
