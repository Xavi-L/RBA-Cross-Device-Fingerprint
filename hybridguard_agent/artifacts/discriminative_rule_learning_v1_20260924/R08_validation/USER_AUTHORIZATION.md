# R08 配置留出专用授权落盘

用户外部验收 R07_SINGLE_SURFACE_REFIT，审查提交 8e79a59bff6d382ec974b66a22abf1f755091719。R07 父步骤保持 PARTIALLY_COMPLETED；固定模型遮蔽、状态/语义诊断仍 NOT_RUN，Browser 攻击仍 NOT_AVAILABLE，不作为本分支前置。

仅授权冻结 R08_CONFIG_TRANSFER：LOCO-v1 精确14折，GREEDY_OR/OP05、HISTORICAL_SEVEN、DIRECT_CORE_OR，core/SRC-111，14新增fit、42模型/基线单元、486预期预测记录。继续使用 R04_freeze_r1 原 dispatcher、包内解释器/依赖和原 REAL_RESEARCH_BUDGET 账本。不改快照、候选、阈值来源、alpha、支持度、复杂度、选择器或划分。

每个 GREEDY_OR 作业在本折 train 内重新学习，不能用 R05 LOEO 模型替代。历史七条只适配精确绑定的保存结果，不重跑旧检测器。每作业先仅打开train、完成选择、保存/加载/冻结模型，再打开outer_test转换/预测，关闭并对账后独立连接标签。失败、超时、空模型及预算耗尽保留原尝试，不自动重试或择优。

按配置迁移命名，披露共享环境；R08_MECHANISM 保持 NOT_EVALUABLE_UNVERIFIED_MECHANISM_PARTITION，R08_PROSPECTIVE 保持 NOT_AVAILABLE，结果为 null。与 R05 LOEO 保存结果分轨，不叠加独立样本数或择优报告；R07 并集36只保留为旧诊断，不作为集成模型或本次结果。

后处理只读取保存产物。100描述阶段、UNKNOWN时间对照、未标注MTC排除监督分母。完成后停止等待验收，不执行R09、V2、单层/联合/集成训练、全开发集重拟合、补采、攻击工具、旧S07、其他分支、提交或推送。
