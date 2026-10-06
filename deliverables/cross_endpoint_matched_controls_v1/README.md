# B2-B 入口

后续授权的提交范围和远端复现限制见 `REMOTE_REVIEW.md`。

结论见 `REPORT.md`，冻结范围见 `PROTOCOL.md`、`PLAN.json`、`FROZEN.json`。`ENVIRONMENT.json` 登记真实 API 36.1 arm64 / Chrome134 环境；原 B1/B2-A 不改。

新指纹、票据、操作 ledger、收据和逐条完整模型输入保存在 Git 忽略的 `private_runs/`。它们可本地复核，未获公开授权。本轮没有自动提交、推送。

## 本轮实际运行的主要命令

以下在仓库根目录执行。已有目录会拒绝覆盖，不能把重复运行当作原始采集。

```sh
python3 deliverables/cross_endpoint_matched_controls_v1/freeze.py
node deliverables/cross_endpoint_matched_controls_v1/make_plan.mjs deliverables/cross_endpoint_matched_controls_v1/PLAN.json b2b-api36p1-20261006-formal01 formal
backend_server/.venv-collection/bin/python deliverables/cross_endpoint_matched_controls_v1/backend.py deliverables/cross_endpoint_matched_controls_v1/private_runs/formal01
node deliverables/cross_endpoint_matched_controls_v1/collect.mjs deliverables/cross_endpoint_matched_controls_v1/PLAN.json deliverables/cross_endpoint_matched_controls_v1/private_runs/formal01
```

前置条件是仅本轮拥有的 emulator-5580，B1 归档 v16 APK，以及空闲的回环端口 8000/8001/9340/9341。模拟器使用 `-avd Medium_Phone_API_36.1 -port 5580 -read-only -no-snapshot-save -no-window -no-audio -no-boot-anim`；其余 ADB server、现有服务和基础 AVD 不动。新后端单独终端启动，结束时创建对应运行目录的 `backend.stop` 进行协作关闭。

首轮 Chrome 真实偏好未持久化的工程问题、一次 15 秒持久化核验和固定六位置补跑，见 `ENGINEERING_ISSUE.json`、`ENGINEERING_REPAIR.json`、`ATTEMPT_SELECTION.json`。原采集脚本快照留在 `engineering_before/`。补跑命令如下，使用同一环境、全新 backend/data：

```sh
backend_server/.venv-collection/bin/python deliverables/cross_endpoint_matched_controls_v1/backend.py deliverables/cross_endpoint_matched_controls_v1/private_runs/repair01
node deliverables/cross_endpoint_matched_controls_v1/collect.mjs deliverables/cross_endpoint_matched_controls_v1/private_runs/repair01/plan.json deliverables/cross_endpoint_matched_controls_v1/private_runs/repair01
```

## 冻结评价与已有结果复核

首轮 42 位置全部保留；六个明确工程补跑位置按事前清单替换进入规范的 42 位置评价，没有依据检测分数回选原位置。`meta.source_run` 和物理行引用指向实际使用的来源。

```sh
# 本轮首次评价：126 个模型位置、210 个条件位置；已有 evaluation 会拒绝覆盖。
python3 deliverables/cross_endpoint_matched_controls_v1/reproduce.py deliverables/cross_endpoint_matched_controls_v1/private_runs/formal01
# 复核保存结果：独立条件 oracle，并从同阶段 App raw 重放三个模型；不采集、不训练。
python3 deliverables/cross_endpoint_matched_controls_v1/check_saved.py deliverables/cross_endpoint_matched_controls_v1/private_runs/formal01
```

只读取保存结果的重汇总命令（不读取 raw、不导入预测模块、不采集、不训练、不联网）：

```sh
python3 deliverables/cross_endpoint_matched_controls_v1/summarize.py deliverables/cross_endpoint_matched_controls_v1/private_runs/formal01/evaluation --output /tmp/b2b-saved-summary
```

针对性测试：

```sh
node --test deliverables/cross_endpoint_matched_controls_v1/test_control.mjs
python3 -m unittest discover -s deliverables/cross_endpoint_matched_controls_v1 -p 'test_*.py' -v
python3 -m unittest discover -s deliverables/browser67_cross_endpoint_diagnostic_v1 -p test_diagnostic.py
```

依赖：已有 Node24、Python3、采集专用 `backend_server/.venv-collection`，以及原冻结时区关系要求的 tzdb2026c（本机实际满足）。没有重装或更新模型依赖。
