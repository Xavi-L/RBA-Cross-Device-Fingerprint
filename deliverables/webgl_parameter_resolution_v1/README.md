# WebGL 部分通过问题：定位、候选定界、重新验证

本目录对应用户一次完成三个步骤的授权。执行顺序是先采集诊断数据，再固定候选合同，
最后使用新会话执行该合同的对照验证。没有进入选择器登记或模型训练。

## 文件与顺序

1. `diagnostic/PROTOCOL.json`：API 36 host / SwiftShader 各两轮正常—攻击—恢复，共 12 次 App 采集。
   每次在空白页和正式采集页上记录逐操作错误，共 96 个诊断 context 记录；另外保存未修改的 v1 完整观测。
2. `LOCALIZATION.json`：诊断行及汇总；`SCOPE_DECISION.json`：据此选择独立 WebGL1 范围的决定。
3. `CANDIDATE_CONTRACT.json`：新合同、质量要求、状态含义、已知范围限制及验证通过标准。
   `frozen_at` 早于后续验证的 `STARTED.json`。
4. `validation/`：四组已有环境中的新 24 次采集，8 个完整三阶段组。
   `CANDIDATE_SUMMARY.json` 是新候选结果；`SUMMARY.json` 保留旧双上下文判定器的完整结果。
   两者不是同一条谓词，不能互相替换。
5. `REPORT.md`：最终结论；`CLEANUP_CHECK.json`：运行进程和端口清理；`DELIVERY_MANIFEST.json`：交付状态。

每个运行目录都保存独立后端原始数据、会话绑定、采集计划、执行日志及源码快照。
诊断观测器会逐阶段读取并清空错误，以定位首次可见错误；这类数据只供定位，不能用来覆盖 v1 的 UNKNOWN。
新合同验证使用原有独立观测器，未加载诊断脚本。

候选实现为 [webgl1_parameter_candidate.py](../../hybridguard_agent/research/webgl1_parameter_candidate.py)。
它调用未修改的完整 envelope 判定器，读取验证过的 `contexts.webgl` 子结果，并保留完整结果及 WebGL2 诊断。
F 仅表示 WebGL1 的这项冲突未被观察到。WebGL1 本身不可用时仍为 U；WebGL2 单独发生冲突也不会变成该候选的 T。
这两个边界均有合成测试，不使用设备标签来决定谓词状态。

语义与原始数据合同继承 [独立观测器合同](../webgl_parameter_module_v1/CONTRACT.md)，
语义来源沿用 [官方来源记录](../webgl_behavior_feasibility_v1/SOURCES.md)。本轮未改变这些旧材料。

## 离线复核

以下命令在仓库根目录运行，不会启动模拟器或训练模型：

```sh
node --test deliverables/webgl_parameter_resolution_v1/test_diagnostic.mjs
python3 -B -m unittest hybridguard_agent.tests.test_webgl1_parameter_candidate -v
python3 -B deliverables/webgl_parameter_resolution_v1/diagnostic/analyze.py
python3 -B deliverables/webgl_parameter_resolution_v1/localize.py
python3 -B deliverables/webgl_parameter_resolution_v1/validation/analyze_candidate.py
```

分析命令默认只重算并比较已存结果；首次生成使用 `--write`，结果文件拒绝覆盖。
两个 `run_pairs.py` 是本轮原始采集脚本，已有 `STARTED.json` 时拒绝重复运行。
本轮记录均为可见开发材料；没有访问独立确认集，不用于估计真机误报率或整体模型提升。
