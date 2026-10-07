# 资源有限增量接入实验

结论与全部24组检查见[REPORT.md](REPORT.md)。三配置均只保留基础App+C1：资源M/B加入后MTC训练明确输出降到560/630，低于90%；W另有正常报警/候选覆盖问题。固定条件有局部增量，不等于通过联合接入要求。

原始数据不复制、不重采。用户于本轮追加授权“提交推送改动，包括必要的私有数据，供远端审核”。据此将16个必要证据文件按原路径纳入Git，包括资源别名映射、正式54位置的raw／配对／操作记录，以及旧匹配42位置所需的原始档案与修复档案。目录名private_runs与一般忽略规则保留，其余私有产物继续忽略。精确范围与审核入口见[REMOTE_REVIEW.md](REMOTE_REVIEW.md)和[REVIEW_EVIDENCE.json](REVIEW_EVIDENCE.json)。目标仓库为public，纳入文件将随提交公开可读。

在仓库根目录运行。生产选择已完成一次，results存在时拒绝覆盖；再次运行选择须明确授权新的实验，不通过重复执行更改本轮胜者。

```sh
# 一次选择及冻结后的历史评价；0 App预测、0拟合、0采集
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/run.py \
  deliverables/app_resource_constrained_extension_v1/results

# 原始当前输入复核：0再选择/拟合。已完成时拒绝重复覆盖
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/verify_current.py \
  deliverables/app_resource_constrained_extension_v1/results

# 仅重汇总保存状态，不调用选择、预测、拟合、采集或网络
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/summarize.py \
  deliverables/app_resource_constrained_extension_v1/results

# 只从保存表格重建中文报告
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/report.py

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s deliverables/app_resource_constrained_extension_v1 -p 'test_*.py' -v
```

当前可信v16配对入口（一次App预测、一次C1、一次六条件接口；只组合所选条件）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/rx_inference.py \
  --model deliverables/app_resource_constrained_extension_v1/results/<model_id>.json \
  --input /absolute/private/path/current_pair.json
```

current_pair.json仅接受app、browser、provenance三个键：分别为原App archive envelope、Browser archive envelope及其completed配对provenance。绑定不合格按端点依赖返回FAILED；操作数不可用保留U。不要提供实验标签、目标、pre/post或选择元数据。传入的归档须来自可信本地接收端，内置检查不是第三方档案真实性认证。

旧MTC v9/v11使用rx_sources.legacy().prep.mtc_app及原P2/P1资源/时区绑定，不能冒充v16；verify_current.py给出完整可复用路径。其组件从当前绑定输入计算一次后共享给三个冻结App模型。独立的rx_inference.predict_prepared接口供受信任的适配层使用，不接收实验身份作判断。

核心证据：SETTINGS/FROZEN/SELECTION_FROZEN、members/inputs、candidate_checks、combinations、models和selected_predictions。CURRENT_REPLAY证明全部1005输入及3015当前模型输出一致；EXECUTION与TESTS把研究执行和测试调用分开。summary目录包含三张主表、批次结果、交并集、逐成员变迁和原正常反例。

源码中prepare阶段对缺输入保留具体异常并写BLOCKED，原始状态失败不会成为正常F。本次后续授权仅覆盖REVIEW_EVIDENCE.json列出的16个必要证据文件及本轮代码／结果／文档；不扩展到其他私有归档。
