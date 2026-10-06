# 工程记录与采集计数边界

1. 本机原先无运行中的模拟器；沿用现有 API36.1 arm64 AVD，创建只读临时实例。未下载镜像或浏览器，未停止原 ADB server（PID 2282）。启动日志在 `private_runs/engineering/emulator.log`。
2. 原测试 App 是 v13，B1 归档 v16 APK 与其签名不同。首次 `adb install -r` 返回 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`（交互工具回执）；在本轮临时实例中备份原 APK、卸载该测试包、安装原归档 APK。安装身份由 `ENVIRONMENT.json` 和 `private_runs/engineering/environment/` 记录。本轮不把临时用户数据写回基础 AVD。
3. Chrome 首次启动、通知引导及“更新可用”菜单描述需要处理。界面语言/翻译目标均未作为网页偏好的替代；无账号操作。真实网页偏好脚本初次失败 JSON 和 UI XML 留在 `private_runs/engineering/`。修复使用实际菜单 resource ID 和有界 UI 等待。
4. 工程采集 `engineering/smoke01` 有 **12 个真实配对**，与正式结果分开；四类运行时干预各一轮三阶段。正常系统语言、时区、Browser 偏好另做 UI apply/restore 检查，这些操作本身未采指纹。冻结登记脚本第一次因探针路径少写 `probe/` 失败，修正引用后才生成正式冻结文件，探针未改动。
5. 首轮正式 `formal01` 有 **42 个真实配对**。其中正常 Browser 语言 UI 的临时值在立即进程重启后丢失；首次两个 change 的实际 navigator 未改变，保留为工程首次结果。不能用它们声称持久化偏好无效。
6. 在读取新批次模型输出之前登记 `ENGINEERING_ISSUE.json`。一次固定 15 秒等待/冷启动诊断证明偏好可持久化，保存于 `private_runs/engineering/preference-persistence-diagnostic.json`。最小修复前后的脚本分别是 `engineering_before/settings_control.py` 与 `settings_control.py`；摘要在 `ENGINEERING_REPAIR.json`。此前四类运行时控制和其余正常设置不改。
7. `ATTEMPT_SELECTION.json` 在补跑结果出来前规定：两个 `L_BROWSER_LANG` triplet 全部使用补跑，不依据模型分数选取或回退。`repair01` 计划 **6 次额外配对**。原始首轮 42 条从未覆盖。规范评价仍为 42 位置；原来被替代的六次实际采集不是被删除的失败，也不加入规范分母。
8. 全部采集计划合计 **12 冒烟 + 42 首轮 + 6 工程补跑 = 60 次实际配对尝试**。实际成功/缺端数以 `ACQUISITION_AUDIT.json` 为准。冻结评价预定 126 个模型位置、210 个条件位置；后续原始 App 重放是额外离线预测调用，不是额外采集或新增样本。

新 raw、tickets、回执、CDP/ADB ledger 保持本地，保留失败与实际调用。无模型训练，无最终消融，无新设备、语言或时区目标扩展。
