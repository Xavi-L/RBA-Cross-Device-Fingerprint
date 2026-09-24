# 本次 R07 用户授权记录

用户外部验收 R06_SOURCE_REFIT，审查提交 4a99e883c62994c1a5037b2bedc0da5205c69b7c。R06 父步骤保持 PARTIALLY_COMPLETED；R06_POSTFIT_DELETE 仍 NOT_RUN，不要求在进入 R07 前补做，不填 0、不标完成。

仅授权 R07 冻结可执行主分支：native84、app_web67、host26 × 3 LOEO 折 × GREEDY_OR/OP05，共 9 个真实 fit。使用 R04_freeze_r1 的原 dispatcher、精确 expected jobs、R04-R1 已验收白名单（目录原子 + 固定控制 + train-only 数值分位点），同一 REAL_RESEARCH_BUDGET 账本，不重置。不得按已暴露 R05/R06 外层成绩修改候选、alpha、支持度、复杂度、选择器、划分或门控。

每作业 train-only 读取和阈值拟合、支持度及选择 → 保存/加载/冻结 model/encoder → outer_test 转换预测 → 关闭对账 → 独立评价标签。R05 GREEDY_OR/OP05 仅只读其保存的模型和已关闭预测作为共同 ID/分母下的跨层对照，不重拟合或补预测。

R05 漏检攻击恢复、交并集和配置比较只来自已保存 R07 预测。来源与表示解释分开。未实现固定模型遮蔽和语义/状态诊断登记 NOT_RUN/null，不改冻结快照补接口；没有 Browser 攻击材料时不制造结果。

完成后停止等待验收；不设计 V2，不自动执行 R08、其他分支、全开发集重拟合、补采、攻击工具、旧 S07、提交或推送。技术失败保留原尝试，不重试选优。
