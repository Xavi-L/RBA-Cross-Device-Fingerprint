# B2-C 入口

后续授权交付范围见 [REMOTE_REVIEW.md](REMOTE_REVIEW.md)。

结果见 [REPORT.md](REPORT.md)。三份新的开发模型位于 `results/paired244-devext-*.json`，索引为 `results/models.json`。此次是已执行的有限增量学习；三个冻结 App 模型及其编码器未重新训练。原始新指纹/票据/日志仍在 B2-B 的本机 private_runs，没有复制或扩大公开范围；未提交或推送。

## 实际选择与回放命令

从仓库根目录运行。本次 `results/` 已存在，选择命令拒绝覆盖。需要复核现有结果时优先使用下面的 verify 或保存结果重汇总；另行授权重新选择时必须换本目录中的全新输出目录。

```sh
python3 -B deliverables/cross_endpoint_constrained_extension_v1/run.py
python3 -B deliverables/cross_endpoint_constrained_extension_v1/verify.py deliverables/cross_endpoint_constrained_extension_v1/results
```

首次命令实际执行三个增量选择任务、12个候选集合检查、2853次选定模型OR组合。输入使用经身份、原始引用、冻结版本、逐条规则与操作数核验的2853条基线输出和1902条C1/C2输出。完整模型已生成并对951位置回放。`verify.py` 随后实际从60条v16原始配对，以及891条MTC原P1 App观测＋采集时间raw，调用冻结预测器和C1各2853次，全部与保存结果一致。它不重新选择、不拟合、不采集。

第一遍验证后增加推理输入键和条件文件身份检查，修正恢复子集为完整三阶段组；第二遍全量验证仍一致。两遍证据回放合计5706次App预测、5706次选中C1预测；不增加输入位置或独立样本。当前推理单元夹具另调用7次App、4次C1；既有回归测试单列。真实数据评价值扰动测试另外调用3次选择器、12次集合检查，以验证结果不变，不生成新模型或调参；不能将测试重执行说成零学习。

## 只读取保存结果的重汇总

```sh
python3 -B deliverables/cross_endpoint_constrained_extension_v1/summarize.py deliverables/cross_endpoint_constrained_extension_v1/results --output /tmp/b2c-saved-summary
python3 -B deliverables/cross_endpoint_constrained_extension_v1/check_summary.py
```

只需保存的 `members.jsonl`、`models.json`、`predictions.jsonl`；不需要B2-B私有raw。guard检查禁止选择、预测、raw读取、网络和子进程，四个汇总文件与已保存结果逐字节相同。

## 单个当前配对推理

`inference.predict_current(model, app_input, pair)` 的 `app_input.raw` 是冻结适配器生成的**当前App**原始规则单元（未拟合的新阈值不得传入），`pair` 只允许 C1/C2 所需4个字段的 features/field_status/field_quality 与绑定错误。缺字段保留U，绑定失败保留FAILED；完全没有Browser时不丢弃有效App。失败遵循原选中输入失败优先规则。

例如在Python中将本目录加入`sys.path`后：

```python
from common import read
from prepare_current import v16_pair
from inference import predict_current
model = read('deliverables/cross_endpoint_constrained_extension_v1/results/paired244-devext-c2e38381be26f0a91709871b.json')
# app_archive、browser_archive、provenance是同一当前配对的三个已读取JSON对象。
app_input, pair = v16_pair(app_archive, browser_archive, provenance)
result = predict_current(model, app_input, pair)
```

也支持 `inference.py --model MODEL_JSON --input CURRENT_JSON`，CURRENT_JSON结构为 `{"app_input": ..., "pair": ...}`。不要为远端审核复制完整私有输入。MTC v9/v11需使用 `prepare_current.mtc_app` 保留原P1质量语义及原采集时间raw，再把核验后的当前配对交给 `pair_inputs`；不能把历史MTC伪装成v16。具体完整路径示例见 `verify.py`。

`predict_saved` 仅用于已通过 `adapter.py` 核验的保存状态组合，不是未经核验的外部状态接入口。真实标签、目标、场景、方向、pre/post与恢复只在选择/评价侧表，推理不读取它们。

## 测试和证据

```sh
python3 -B -m unittest discover -s deliverables/cross_endpoint_constrained_extension_v1 -p 'test_*.py' -v
python3 -B -m unittest discover -s deliverables/cross_endpoint_matched_controls_v1 -p 'test_*.py'
python3 -B -m unittest discover -s deliverables/browser67_cross_endpoint_diagnostic_v1 -p test_diagnostic.py
```

新30项＋既有25＋36项共91项通过。本机具有原已验证数据与依赖；完整重新适配/当前输入重放及部分测试需要本机B2-B private_runs，远端仅凭此次派生文件不能复现私有原始输入。保存结果重汇总可以直接复现。

- `PROTOCOL.md` / `results/SETTINGS.json` / `PRE_SELECTION_FREEZE.json`：运行前范围、预算、排序、冻结。
- `selection_members.jsonl` / `selection_groups.json` / `selection_inputs.jsonl`：690开发成员、完整场景组、校验后的状态及物理行引用。
- `candidate_checks.json/.csv` / `candidate_outputs.jsonl`：12集合、8280个逐成员组合、实际不可行原因。
- `models.json` / `SELECTION_FROZEN.json`：三个选择结果与独立模型身份；历史144/117适配前已写出。
- `members.jsonl` / `inputs.jsonl` / `predictions.jsonl`：951位置、2853新组合输出与基线同成员比较。
- `summary/`：按模型、原组、身份、方向/家族、正常场景、完整恢复组统计的T/F/U/FAILED与交集ID。
- `COVERAGE_ANALYSIS.json`：C1未知与基线未知交集；不能用单条候选覆盖替代模型覆盖。
- `current_input_replay.jsonl` / `REPLAY_VERIFICATION*.json`：实际当前输入回放及独立算术校验。
- `SOURCE_MANIFEST.json` / `EXECUTION.json` / `VALIDATION.json` / 测试日志：原始引用、调用分类与验证。
- `preparation_attempt01/`：选择前正常依据引用序列化差异导致的停止，保留失败，没有学习结果重选。
