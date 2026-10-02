# WebGL 参数等价性模块 v1

从 [REPORT.md](REPORT.md) 了解进展，从 [CONTRACT.md](CONTRACT.md) 阅读输入、版本、绑定和 UNKNOWN 规则。

本轮完成独立观测器和纯判定器；离正式接入选择器通常还剩环境验证、候选/输入接入两步，之后才是重训。
脚本不会自动加入 App 或浏览器的默认采集；当前角色仅为 observation_only。

```sh
node --test browser_probe_site/tests/webgl-parameter-observation.test.mjs
python3 -B -m unittest hybridguard_agent.tests.test_webgl_parameter_equivalence -v
python3 -B deliverables/webgl_parameter_module_v1/replay_saved_queries.py
```

合成跨语言 fixture 由实际 JS 模块在明确的 fake WebGL API 中生成。需要改 fixture 时显式执行：

```sh
node browser_probe_site/tests/helpers/webgl-parameter-fixtures.mjs --write hybridguard_agent/tests/fixtures/webgl_parameter_equivalence_v1/observer_examples.json
```

它不是设备采集记录。回放只调用查询层函数，不为旧数据补造新 envelope、preflight 或控制项第三次查询。
