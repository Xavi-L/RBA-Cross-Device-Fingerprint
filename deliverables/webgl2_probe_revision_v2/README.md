# WebGL2 探针 v2 与正常图形路径验证

本目录保存采集修复和正常模拟器对照。没有攻击注入、模型训练、模型预测或独立确认材料访问。

- `REPORT.md`：结果、限制和后续判断。
- `PLAN.json`、`CONTROLS_STARTED.json`：首轮 11 次计划及执行前记录。
- `controls/`：原始 payload、接收日志、模拟器日志、启动命令和生命周期。
- `SUMMARY.json`、`OBSERVATIONS.json`：从原始记录提取的结果。
- `fresh_launch/`：针对两次 Activity 复用失败的单独启动流程验证；原结果保留。
- `BROWSER_RESULT.json`：本机浏览器中旧同 canvas 路径与实际 v2 探针对比。
- `JS_TESTS.log`、`BACKEND_TESTS.log`、`ANDROID_BUILD_TESTS.log`、`ANDROID_TEST_RESULTS.json`：检查结果。

离线复核（读取已保存原始材料，不启动模拟器）：

```sh
python3 -B deliverables/webgl2_probe_revision_v2/analyze.py
python3 -B deliverables/webgl2_probe_revision_v2/analyze.py --fresh-launch-check
```

代码检查：

```sh
node browser_probe_site/scripts/sync-probe.mjs
node --test browser_probe_site/tests/webgl-context.test.mjs browser_probe_site/tests/webdriver-observation.test.mjs browser_probe_site/tests/probe-contract.test.mjs
PYTHONDONTWRITEBYTECODE=1 HYBRIDGUARD_DATA_DIR=/private/tmp/hg-webgl2-unit-data backend_server/.venv-collection/bin/python -B -m unittest discover -s backend_server -p test_browser_pairing_contract.py
sh deliverables/webgl2_probe_revision_v2/build_local.sh
```

`build_local.sh` 会产生构建缓存和本地端点 APK。本轮已保存检查结果，并恢复原本干净的
已跟踪构建缓存，避免把临时本地配置写进既有构建产物；新的本地 APK 留在被忽略的
`runtime/featureapp-v13-local-only.apk`。不能把这个本地 APK 当成给攻击侧同学的公网版本。

`run_controls.py` 仅用于预先登记的新运行目录。现存 `CONTROLS_STARTED.json` 和目录
会使重复执行直接失败，不能覆盖本轮数据。首轮使用旧的 stop/start 方式；
`--fresh-launch-check` 使用已有的 process-absent-then-am-start-S-W-v1 控制方式。
后续采集应使用该方式，并登记新的协议和输出位置。

浏览器小验证可运行 `python3 -B deliverables/webgl2_probe_revision_v2/browser_serve.py`，
再访问 `http://127.0.0.1:8766/`。只提供 HTML 和探针两个文件，120 秒后自动关闭。
页面只显示结果，不上传数据。它验证桌面浏览器，不能替代 Android 记录。

服务端测试覆盖 v1 两个已登记 bundle、v2 新 bundle、跨版本冒认、未登记版本和
未登记 bundle。兼容旧版本仅指其与旧网页正确配对；升级到新网页须同步升级 App。
没有执行公网发布或 Git 提交推送。
