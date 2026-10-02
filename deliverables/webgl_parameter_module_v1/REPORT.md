# WebGL 参数等价性：观测与纯判定模块

日期：2026-10-02。状态：**第一步模块封装完成，尚未接入选择器。**

新增独立 JavaScript 观测器与纯 Python 判定器，把上一轮得到本地支持的 H2 固化为带版本的接口。
观测器显式调用才采集；判定器只返回 MATCH / COUNTEREXAMPLE / UNKNOWN 及原因，不读取标签或模型。

## 已完成

- [独立观测器](../../web_probe/webgl_parameter_observer.js)：保留 ES5 兼容语法，分别创建 WebGL1/2 context，记录参数的原始类型、三次读值、GL 错误和状态。
- [纯判定器](../../hybridguard_agent/research/webgl_parameter_equivalence.py)：校验版本、外部会话绑定、上下文与扩展、数字参数控制项，再判断 vendor/renderer 参数等价性。
- [观测合同](CONTRACT.md)：明确 UNKNOWN、部分可用、控制失败和初始化错误的处理方式。
- 七项 JavaScript 测试、十二项 Python 测试，共 **19 项通过**。Python 直接消费真实 JS 观测器在假 WebGL API 上生成的四种合成记录，检查跨语言结构与判定。
- 从上一轮十二份保存材料中回放 **48 组 vendor/renderer 三次查询**，与冻结 H2 判定 **48/48 一致**：32 MATCH、16 COUNTEREXAMPLE。

四种合成记录、48 组查询都不是新增设备样本。这里的 48/48 是实现一致性，不是检测准确率。
完整新观测器尚未在模拟器/真机运行；只读回放不能替代下一步环境验证。

## 保留下来的限制

同一数字参数前后发生变化仍为 UNKNOWN，不能当作数值/字符串转换冲突。
字段缺失、占位值、类型不符、context loss、扩展缺失、错误队列不干净或控制项不一致，也不会变成正常通过。
初始化错误即使被清空，也保留并使该 context 的完整判定为 UNKNOWN。

本版只保留 H2 和数字枚举控制项，不执行上一轮 H1 或实际绘制。
运行顺序变化对 host/WebGL2 初始化错误的影响目前未知，需要用新观测器实测；不能直接继承旧原型的完整环境适用性。

上一轮两项组合的 `NOT_ESTABLISHED` 保持不变。没有重写旧结果、伪造新字段、启动新的采集、
修改正式 177/67 字段或默认采集入口，也没有训练/预测/注册候选。
CAP7 的既有 **117/126（92.86%）** 仍只是原结果，本轮没有新增整体提升数字。

## 离正式接入还剩几步

开始本轮时按三个里程碑估计，第一步现在已完成，通常还剩 **两步**：

| 步骤 | 工作与完成条件 | 当前状态 |
| --- | --- | --- |
| 1. 模块封装 | 新版本观测器、纯判定器、关键边界与保存查询回放 | 本轮完成 |
| 2. 环境与适用范围验证 | 使用新模块在可用 API 29/30/36 环境采集正常/攻击/恢复，核实实际 WebView 版本，检查 UNKNOWN 与正常反例，冻结适用范围 | 下一步 |
| 3. 正式输入与候选接入 | 接好新观测的保存/读取、schema 与来源绑定、候选注册和编译；明确缺失值策略，以同版本新材料冻结基线/增量训练协议并通过训练前检查 | 尚未开始 |
| 之后的实验 | 正式重训，比较整体检出、内部对照报警、明确输出率与逐配置变化 | 不计入“接入前两步” |

这个步数是工作拆分，不是保证剩余两轮对话就一定通过。若第二步出现合法环境中的冲突、
大范围 UNKNOWN 或版本差异，需要在接入前补修并验证。没有足够训练支持时也不会强行准入。
三种 API 标签不自动代表三种独立 WebView，仍以实际采集信息为准。

## 验证与材料

```sh
node --test browser_probe_site/tests/webgl-parameter-observation.test.mjs
python3 -B -m unittest hybridguard_agent.tests.test_webgl_parameter_equivalence -v
python3 -B deliverables/webgl_parameter_module_v1/replay_saved_queries.py
```

测试使用合成数据，不访问正式确认材料；回放只读上一轮已保存的 H2 原始查询。
结果见 `JS_TESTS.log`、`PYTHON_TESTS.log`、[REPLAY.json](REPLAY.json)。
本轮新增文件清单见 [DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json)。未提交推送或部署。
