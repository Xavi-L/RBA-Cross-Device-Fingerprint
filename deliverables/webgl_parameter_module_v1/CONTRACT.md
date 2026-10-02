# WebGL 参数等价性观测合同 v1

## 边界与版本

本模块只记录并判断 H2：同一 WebGL context 中，同一枚举的数字 / 对应十进制字符串 / 数字查询是否一致。
不运行上一轮的扩展禁用查询 H1，不识别 GPU 品牌，也不产生模型告警。

| 项目 | 固定标识 |
| --- | --- |
| 观测 schema | `webgl-parameter-equivalence-observation-v1` |
| JavaScript 观测器 | `webgl-parameter-observer-v1` |
| 观测范围 | `fresh-webgl-contexts-v1` |
| 离线判定器 | `webgl-parameter-equivalence-v1` |
| 当前角色 | `observation_only`，未注册为选择器候选 |

观测器是 [独立 ES5 脚本](../../web_probe/webgl_parameter_observer.js)。加载脚本只定义公开对象，
不会采集、设置定时器、监听页面事件或上传数据。需要显式调用 `observe({realmBinding})`。
调用者不能覆盖版本标识；空白或缺失 realmBinding 属调用配置错误。

## 记录结构

顶层包含 `observation_schema_version`、`observer_revision`、`observation_scope`、`realm_binding` 和 `contexts`。
`contexts` 按固定顺序记录 `webgl`、`webgl2`，各使用新的 8×8 canvas，不操作调用方已有 context。

每个 context 记录：

- `context_type`、`context_creation_status` 与 `context_lost_at_end`。
- `extension_read_status`、`extension_available`、`extension_constants`：启用 debug renderer 扩展的结果。
- `preflight`：扩展初始化之后的错误队列与 context 状态。最多清理八个错误，非空错误保留原值。
- `control`：MAX_VERTEX_ATTRIBS（34921）的数字—字符串—数字三次调用。
- `parameters.vendor`、`parameters.renderer`：37445、37446 各自的三次调用。

每次调用都保留原始 `argument` / `argument_kind`、`read_status`、`pre_errors`、`drained`、
`context_lost_before`、`value_kind` / `value`、`error` 和 `context_lost_after`；异常另存 `exception`。
错误或未执行的调用不会被补上 renderer 默认值。异常对象/非有限数等意外返回值不会直接序列化为假正常值，
而是保留不符合预期的类型信息，使判定器输出 UNKNOWN。

观测器可能保存初始化错误之后的后续查询，便于诊断；**只要 preflight 非空，该 context 的完整判定仍为 UNKNOWN**。
这是新版本的明确保守条件，不是删除上一轮 UNKNOWN 的补救；需要下一步在真实 WebView 环境核实其影响。

## 判定顺序

公开入口位于 [纯 Python 模块](../../hybridguard_agent/research/webgl_parameter_equivalence.py)。
它不访问文件、网络、环境变量、训练标签或模型，不修改输入。

1. 校验完整 schema、观测器 revision、scope 和固定 context 集合。
2. 与调用方从采集上下文提供的 `expected_realm_binding` 比较，不能直接用输入记录自己的值作为独立绑定证据。
3. 校验 context 和扩展可用、枚举常量正确、preflight 无错误且无 context loss。
4. MAX_VERTEX_ATTRIBS 的三次查询必须为相同正整数，无错误、无漂移。控制失败时，该 context 为 UNKNOWN。
5. 对 vendor / renderer 分别验证参数值和参数类型、明确 observed 状态、无旧错误、无新错误、无 context loss、值为非占位字符串。
6. 数字前后读值不同：UNKNOWN / `TEMPORAL_INSTABILITY`；前后稳定但字符串参数结果不同：COUNTEREXAMPLE；三次一致：MATCH。

不同参数/上下文的汇总：至少一个符合全部条件的冲突可保留 COUNTEREXAMPLE，并保留其他 UNKNOWN 的明细；
只有两种请求的上下文、两项参数都可用且一致时才能给出整体 MATCH。其他情况是 UNKNOWN。
因此，“WebGL1 一致但 WebGL2 不可用”不会被报告成整个观测正常。

这是接口行为关系，不是恶意/授权或物理 GPU 的证明。合法脚本代理、浏览器问题和攻击代码都可能影响这些调用。
realm_binding 也只是与采集会话对应的声明，不是对页面 getter 原生性或硬件来源的认证。

## 最小调用

在研究脚本加载观测器以后，显式采集：

```javascript
var observation = window.HybridGuardWebGLParameterObserver.observe({
    realmBinding: "featureapp:" + collectionSessionId + ":main-frame"
});
```

离线读取该记录以后，用采集执行器确认的会话构造期望绑定：

```python
from hybridguard_agent.research.webgl_parameter_equivalence import evaluate_observation

result = evaluate_observation(
    observation,
    expected_realm_binding="featureapp:" + recorded_session_id + ":main-frame",
)
```

`evaluate_parameter_triplet` 是较低层的查询判定函数，不验证整个 schema/会话。
它可用于明确标注的旧查询回放，不能被当作完整观测接入或训练数据准入的替代品。

## 与既有数据、选择器的关系

本轮没有修改 canonical probe、App 适配器、后端接收合同或正式 177/67 字段目录。
独立脚本尚未被这些默认采集入口加载。下一步环境验证可由研究执行器显式加载并另存记录。

旧行为试验有 H2 原始三次查询，但缺少本独立观测器的 preflight 和控制项第三次读取。
回放只检查已记录的 H2 查询；不会把缺失项补成成功，也不会伪造新版本 envelope。
更早的 378 条训练材料连这些查询本身都没有，仍不能回填。

语义来源沿用 [可行性试验的来源核查](../webgl_behavior_feasibility_v1/SOURCES.md)。
取消 H1 与实际绘制后，本独立观测器的运行顺序不同，因此其完整运行适用性仍需下一阶段验证。
