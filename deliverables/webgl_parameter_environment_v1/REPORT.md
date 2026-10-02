# WebGL 参数等价性实际环境验证

本轮完成三步计划的第 2 步。24/24 次采集、8/8 轮正常—攻击—恢复对照均完整，
但**双上下文 v1 的全部环境门槛未通过**：三组软件渲染配置通过，API 36 host 因正常状态下的 WebGL2 初始化错误保留 UNKNOWN。
完整结论为 `NOT_ESTABLISHED_FOR_FULL_MATRIX`，没有改动观测器、判定器或门槛来改变这个结果。

## 实际环境及结果

以下 WebView 版本均由本轮 `dumpsys webviewupdate` 和各条原始 App manifest 交叉确认，
不是根据 Android API 推测。全部配置位于同一台 Mac 的现有模拟器中。

| 配置 | 实际 WebView | 正常阶段 | 攻击阶段 | 恢复阶段 | 完整通过轮数 |
| --- | --- | --- | --- | --- | --- |
| API 29 / SwiftShader | 91.0.4472.114 | 2 MATCH | 2 COUNTEREXAMPLE | 2 MATCH | 2/2 |
| API 30 / SwiftShader | 91.0.4472.114 | 2 MATCH | 2 COUNTEREXAMPLE | 2 MATCH | 2/2 |
| API 36 / host | 134.0.6998.135 | 2 UNKNOWN | 2 COUNTEREXAMPLE | 2 UNKNOWN | 0/2 |
| API 36 / SwiftShader | 134.0.6998.135 | 2 MATCH | 2 COUNTEREXAMPLE | 2 MATCH | 2/2 |

这是三个 Android API、两个 WebView 版本、四组配置。只有 API 36 同时比较两条渲染路径；
没有验证 API 29/30 host、Windows 宿主、其他 WebView 版本或真机。

所有 24 条采集均保存完整的 177 字段及 observed 状态，并另存新版完整观测、会话对应记录和干预回执。
全部 8 轮均确认 vendor/renderer 两个目标值发生预期改变、另外 10 个图形字段不变，
恢复阶段的 12 个图形字段和 sidecar context 内容与干预前一致。没有失败位置、重试或替换样本。

完整观测的汇总是：8 个攻击阶段均出现有效参数冲突；16 个正常/恢复阶段中，12 个 MATCH、4 个 UNKNOWN。
符合全部预定通过条件的是 6/8 轮，不能写成 8/8 全面验证通过，也不能把 UNKNOWN 算成正常。

## WebGL2 的限制及 WebGL1 的可用范围

API 36 host 的 6 条观测中，WebGL2 的 preflight 均记录 `[1280]`，随后错误队列能够清空。
冻结的 v1 判定器仍将该 context 判为 `UNKNOWN / PREFLIGHT_ERRORS`。
错误同时存在于正常、攻击和恢复阶段，因此不能把这个错误当成攻击信号。
本轮没有定位错误产生的底层原因，也没有把后续读值正常当成忽略初始化错误的理由。

在相同的完整 envelope 中，WebGL1 子结果在全部 24 条上都有有效判定：

- 16/16 个正常及恢复阶段为 MATCH。
- 8/8 个攻击阶段为 COUNTEREXAMPLE。
- WebGL1 UNKNOWN 为 0；WebGL2 UNKNOWN 为 6。

这是已执行的相同数字—字符串—数字查询、控制项、错误状态和会话绑定共同支持的子结果。
它仅说明当前插件配置下的参数等价性差异，不证明真实 GPU、攻击意图、通用攻击检出率或真机误报率。
每轮仍使用同一个既有 `webgl.vendor` evasion；重复轮次并不是独立攻击机制。

## 对下一步接入的影响

当前选择器的 OR 语义是 `F OR U = U`，并且保留步骤拒绝 `DEFINED_SAMPLE_BECAME_UNKNOWN_OR_FAILED`。
所以直接加入双上下文总结果存在把原本可判断的正常样本变成 UNKNOWN 的风险。
这已用现有逻辑函数及最小手工状态复核，见 [INTEGRATION_READINESS.json](INTEGRATION_READINESS.json)；
没有执行历史模型预测，不能说整体模型已经退步或已经提升。

建议下一步**明确登记一个单独的 WebGL1 参数等价性候选**，读取验证过的 envelope 中 `contexts.webgl` 子结果；
WebGL2 和原始双上下文结论继续保存。WebGL1 缺失、错误或绑定不成立时依然输出 UNKNOWN。
这个提案是根据本轮开发材料形成的新候选范围，尚未实现、登记或用于训练，
也不会将本轮双上下文方案的未通过结论改写为通过。

接入工程还需要完成观测的 App/后端持久化、研究输入适配、明确的候选语义登记与编译、准入检查，
并在新冻结的同版本正常—攻击—恢复数据上验证。新的比较数据必须覆盖计划比较的攻击配置；
这 24 条只覆盖一个攻击配置，不能独自用于宣称整体改进。旧 378 条没有该观测，不能回填成功值。
这些工作完成后，才可在共同数据、相同划分下比较基线和新候选的重训结果。

本轮执行 0 次模型训练、0 次模型预测、0 个新候选登记；整体效果提升仍是 `NOT_EVALUATED`。
没有访问独立确认材料，没有修改攻击仓库或默认采集入口。

## 复核与交付

- 4 项会话绑定和准入边界测试通过，Python/Node 语法检查通过。
- 结果可由 `analyze.py` 从原始 App 数据、会话记录与观测器输出重算；执行协议及源快照保持一致。
- 4 个模拟器及 4 个接收器均正常退出，4 个专用端口已释放，见 [CLEANUP_CHECK.json](CLEANUP_CHECK.json)。
- 原始、逐条和逐轮结果均保留在本目录；适用范围及下一候选提案见 [SCOPE.json](SCOPE.json)。
- 本轮只新增此交付目录，保留之前的本地修改，未提交或推送。
