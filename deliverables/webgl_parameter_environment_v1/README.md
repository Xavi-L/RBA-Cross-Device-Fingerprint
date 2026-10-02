# WebGL 参数等价性：实际环境验证 v1

这是三步计划的第 2 步：在现有模拟器上执行上一轮新增的独立观测器及纯判定器，
核实完整新合同的适用性。它不是旧 H2 查询的再次回放，也不是选择器重训。

- `PROTOCOL.json`：测量开始前固定的四组环境、24 个采集位置及通过条件。
- `PRE_RUN_REVIEW.json`、`TESTS.log`：执行前检查与 4 项会话绑定/准入边界测试。
- `source_snapshot/`：实际执行的观测器、判定器、协议、执行器、适配器和分析脚本。
- `runs/<cell>/`：每个环境的命令、WebView 版本、独立本地后端和生命周期记录。
- `runs/<cell>/attempts/<position>/OBSERVATION.json`：新版观测器的原始输出。
- 同目录 `BINDING.json`、`AUTOMATION.json`、`ATTEMPT.json`：会话对应与执行状态。
- `runs/<cell>/backend/raw_expanded_payloads.jsonl`：同会话收到的原始 App 数据。
- `ROWS.json`、`TRIPLETS.json`、`SUMMARY.json`：完整行、三阶段组和汇总结果。
- `REPORT.md`、`SCOPE.json`：最终结论、适用范围及下一步边界。

四组配置为 API 29 / SwiftShader、API 30 / SwiftShader、API 36 / host、
API 36 / SwiftShader。每组两轮，每轮正常—攻击—恢复。只有 API 36 比较两条渲染路径；
API 29 与 API 30 不能自动算成两个独立 WebView 版本。

攻击侧只加载既有 `puppeteer-extra-plugin-stealth@2.11.2` 的 `webgl.vendor` evasion。
正常和恢复阶段使用相同的调试连接、页面导航和观测器，每个阶段新启 App 进程。
恢复指去除干预后的新进程恢复，不是在当前页面修改代理。所有数据只上传本机专用接收器，单 worker。

完整通过需要：攻击目标 vendor/renderer 确实改变，原始图形字段及观测内容恢复，
非目标图形字段不变，WebGL1 数字查询与原始采集相符，且完整新判定结果为 MATCH—COUNTEREXAMPLE—MATCH。
原始错误、UNKNOWN 和不完整组均保留；没有重试、替换或事后修改规则。

可复核命令（仓库根目录）：

```sh
python3 -B -m unittest discover -s deliverables/webgl_parameter_environment_v1 -p 'test_boundaries.py' -v
python3 -B deliverables/webgl_parameter_environment_v1/analyze.py
```

第二条命令只重算并比较保存结果，不重新采集。首次生成结果使用 `--write`，已有结果拒绝覆盖。
`run_pairs.py` 是本次原始采集执行器，已有 `STARTED.json` 时拒绝重复启动。

观测器和判定器的正式合同见 [上一轮合同](../webgl_parameter_module_v1/CONTRACT.md)。
当前阶段没有接入默认采集入口、扩展正式字段目录、注册候选条件、回填旧数据或调用模型。
合法页面代理也可能引发接口不一致，本结果不能证明攻击意图、GPU 身份或真机误报率。
