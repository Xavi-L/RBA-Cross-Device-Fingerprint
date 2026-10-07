# App资源／内存真实配对补证

> **2026-10-07后续审核授权**：用户已要求提交推送必要私有数据。正式formal01的plan、captures、private_command_events及三份raw/provenance档案按原路径纳入Git；资源别名映射随联合选择交付。目标仓库为public。详见[审核范围](../app_resource_constrained_extension_v1/REMOTE_REVIEW.md)与[16文件清单](../app_resource_constrained_extension_v1/REVIEW_EVIDENCE.json)。下文“未授权公开／不自动提交”保留为原采集阶段的授权边界，已由本次限定授权更新；其余私有文件仍忽略。

固定范围见 `PLAN.json`、`SETTINGS.json`、`FIELD_SEMANTICS.md`；结果见 `REPORT.md`。正式54位置，额外冒烟最多6位置，0模型拟合、0规则选择。保持原App模型、Browser成果和旧raw不变。

新raw、票据、完整操作日志、配对关联在本目录被Git忽略的 `private_runs/`。结果使用RP001–RP054分析别名；同阶段绑定在本地原始provenance核验。新raw未获公开授权。源码和结果均不自动提交／推送。

## 本次实际命令与运行前提

仓库根目录运行。仅使用本轮拥有的 `emulator-5580`，从 `Medium_Phone_API_36.1` 启动 `-read-only -no-snapshot-save -no-window -no-audio -no-boot-anim`；不能覆盖基础AVD或改变RAM/CPU。独立端口8000/8001/9340/9341必须空闲；不终止其他服务。安装B1归档v16，完成隔离Chrome的无账号首次启动与通知选择后记录 `environment.py`。`private_runs/OWNER.json`记录本轮实例及PID；不能照抄旧PID认领别的设备。

已有输出会拒绝覆盖。再次采集必须用新run_id、新私有目录和明确记录的额外授权，不能将以下命令重复调用当作原来的54位置。

```sh
# 采集后端单独运行；该命令只启动自己的后端
PYTHONDONTWRITEBYTECODE=1 backend_server/.venv-collection/bin/python \
  deliverables/app_resource_paired_validation_v1/backend.py \
  deliverables/app_resource_paired_validation_v1/private_runs/formal01

# 唯一正式矩阵；不预测、不拟合
node deliverables/app_resource_paired_validation_v1/collect.mjs \
  deliverables/app_resource_paired_validation_v1/private_runs/formal01/plan.json \
  deliverables/app_resource_paired_validation_v1/private_runs/formal01

# 891原MTC成员，六个固定条件；不采集，不运行App模型
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_paired_validation_v1/evaluate.py mtc

# 新54位置的9份冻结App模型＋6条件；复用已保存MTC结果
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_paired_validation_v1/evaluate.py \
  deliverables/app_resource_paired_validation_v1/private_runs/formal01

# 仅保存输出重汇总；0采集、0预测、0拟合、0联网
PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_paired_validation_v1/summarize.py
```

结束时创建**本轮对应目录**的 `backend.stop` 协作停止后端，停止自己启动的模拟器；不停止共享ADB服务。采集runner移除本轮forward/reverse。基础AVD不保存本轮App和Chrome修改。

测试：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s deliverables/app_resource_paired_validation_v1 -p 'test_*.py' -v
node --test deliverables/app_resource_paired_validation_v1/test_control.mjs
```

工程记录见 `ENGINEERING.json`。MTC首次适配额外拒绝了3个重复历史App session；P2已通过精确物理行、payload和P1回执定位一次上传。修复后仅重算这3成员的6条件，原输出保留于 `results/engineering/`，额外18次条件调用单列。`repair_mtc_binding.py`是这次修复的可复核记录；修正后的全新评价不需要再次执行修复脚本。公式、阈值和目标从未按结果改变。

首轮冻结模型投影混淆了编码后条件ID和原始数值列名，486位置均FAILED。修正映射后额外回放486位置，实际模型预测972次；第一次输出及原因见 `results/engineering/MODEL_PROJECTION_REPAIR.json`。`repair_model_projection.py`仅记录此次修复，修正后的新评价无需再次执行它。
