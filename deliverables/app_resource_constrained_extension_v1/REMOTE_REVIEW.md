# 远端审核入口与原始证据范围

本次用户明确要求“提交推送改动，包括必要的私有数据，供远端审核”。已核实目标 `Xavi-L/RBA-Cross-Device-Fingerprint` 为 **public**；下列纳入Git的文件随提交公开可读。这是对之前仅保留本机私有原始材料的限定后续授权。

本次交付本轮有限选择的代码、三个独立身份模型、全部24集合/1,005成员输出、汇总、报告、测试与执行记录，以及[REVIEW_EVIDENCE.json](REVIEW_EVIDENCE.json)列出的16个必要证据文件（12,489,157字节）。文件留在原路径并保持原字节和物理行顺序；private_runs目录的一般忽略规则仍保留，通过精确文件白名单纳入这16项。

|范围|文件数|审核用途|
|---|---:|---|
|资源54 formal01|6|固定plan、captures、原始App/Browser、配对provenance、CDP命令时间记录；复核实际修改/恢复、C1与资源条件|
|resource54别名映射|1|RP001–RP054与真实sample/capture身份对应|
|旧匹配formal01与repair01|9|原始App/Browser/provenance、capture依据与canonical positions；旧60位置中42匹配位置的资源条件及当前输入复核|

旧匹配档案保留原42位置和固定修复6位置的完整文件，以维持物理引用和替换依据。被替换的原6位置只是历史档案，不加入本轮1,005成员。资源6条冒烟、模拟器/APK、后端运行日志、重复merged/collected数据以及其他私有目录均不交付。历史票据及轮询有效期已于2026-10-06结束，不用于重新采集。

MTC891的原raw/P2/P1及旧Browser先导18证据原已受Git跟踪，不重新打包。按当前适配读取路径检查了124个仓库文件，除这16项外没有额外未跟踪输入依赖；该交付核对没有新增预测或选择。执行前需要原工程运行环境，尤其原App时间关系要求固定 **tzdb 2026c**（`HYBRIDGUARD_TZDB_DIR`，默认`/usr/share/zoneinfo`），不会静默切换其他版本。

## 先看保存结果

- [REPORT.md](REPORT.md)：三张主表、约束失败原因、负面结论。
- [candidate_checks.json](results/candidate_checks.json)：全部24集合，包含空集和所有拒绝原因。
- [models.json](results/models.json)：三个配置均BASELINE_RETAINED；不是新联合检测增益。
- [unknown_overlap.json](results/summary/unknown_overlap.json)：联合明确输出从567/630降为560/630的7条新增U及逐ID交并集。
- [member_deltas.json](results/summary/member_deltas.json)：新增/丢失检出、正常报警、F→U、U→T及全部转换成员。
- [EXECUTION.json](results/EXECUTION.json)、[CURRENT_REPLAY.json](results/CURRENT_REPLAY.json)、[TESTS.json](results/TESTS.json)：科研调用、原始输入复核与测试调用分开记账。

VALIDATION.json中的staged/commit_push=false及研究报告历史段落，是实验完成时的快照；此次授权与交付范围以本文为准。没有再次执行选择或改写胜者。

## 保存状态重汇总与测试

在仓库根目录运行。重汇总输出到新目录，避免改写交付结果：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/summarize.py \
  deliverables/app_resource_constrained_extension_v1/results \
  --output /tmp/resource-extension-review-summary

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s deliverables/app_resource_constrained_extension_v1 -p 'test_*.py' -v
```

测试包含合成选择和历史评价值扰动回归，不新增交付模型或改写正式选择。

## 原始当前输入复核

复核全部1,005成员会新增3015次冻结App预测、1005次C1和6030个资源条件输出，不拟合、不选择、不采集。已有CURRENT_REPLAY拒绝覆盖；以下将所需保存输入复制到临时审核目录：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import shutil, subprocess, sys, tempfile
base = Path('deliverables/app_resource_constrained_extension_v1')
review_dir = Path(tempfile.mkdtemp(prefix='resource-extension-review-'))
for name in ('models.json', 'members.jsonl', 'inputs.jsonl',
             'combinations.jsonl', 'candidate_checks.json', 'FROZEN.json'):
    shutil.copyfile(base / 'results' / name, review_dir / name)
subprocess.run([sys.executable, str(base / 'verify_current.py'), str(review_dir)], check=True)
print(review_dir)
PY
```

对一个新的可信v16当前配对单独执行入口见[README](README.md)。票据与操作侧证据用于绑定和实际效果审核；目标、标签、场景、pre/post不进入模型推理。

本次交付不重新采集、不重复24集合学习、不放宽约束、不启动论文定稿；保留三配置空增量结论以及全部正常反例和未知。
