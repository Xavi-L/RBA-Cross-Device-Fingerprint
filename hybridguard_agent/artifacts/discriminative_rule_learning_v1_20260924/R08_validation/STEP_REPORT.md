# R08_CONFIG_TRANSFER：配置留出/配置迁移

**主分支完成，等待外部验收。** 严格按冻结LOCO-v1一次执行14个新增fit、42个模型/基线单元和486条预测。14个学习模型及28个固定基线单元全部COMPLETED；空模型、缺失、失败、超时、预算耗尽、重试均为0。这是实际运行事实，不是预设必须非空或成功的验收条件。

R07_SINGLE_SURFACE_REFIT外部验收独立记录，审查提交 `8e79a59bff6d382ec974b66a22abf1f755091719`；其原报告/VALIDATION及R05、R06结果不改。R07父步骤继续PARTIALLY_COMPLETED，固定遮蔽与状态/语义诊断NOT_RUN，Browser攻击NOT_AVAILABLE，不作为本轮前置。

## 冻结、授权与运行

- 只使用 `../R04_freeze_r1/` 原launcher/dispatcher/worker、包内解释器和依赖；原快照授权状态不改。
- 协议digest：`4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`。
- 实际FREEZE_MANIFEST SHA-256：`bff86c2423283d9ecdf6402c2975a747707cd7d521a328561ef676cdcff2ddad`。
- 实际RESOURCE_MANIFEST SHA-256：`7e2aa45c9cf78abc106cb61e3863c5d89f2491fe0b406b645cd48fad80bd0de0`。
- 快照外R08授权digest：`f7cc3483b14b608f6f12a9a4c96bd837a846aabb49eef643235a65a168803592`。授权绑定全部精确job IDs、train成员、冻结/资源摘要及原REAL_RESEARCH_BUDGET。启动实际校验3,298个资源，未回退工作区源码、其他解释器或求解器。
- Python 3.12.14，HiGHS/highspy 1.12.0，NumPy 2.3.5，macOS-15.7-arm64-arm-64bit；本分支只运行冻结GREEDY_OR，未增加IP或单层/集成实验。
- UTC 2026-09-24T15:22:01.995397+00:00 至 2026-09-24T15:22:38.855505+00:00，wall 36.860158秒，attempt=1、returncode=0、自动重试0。原始命令、路径、stdout/stderr和时点均保存。

每折GREEDY_OR在自身LOCO train重新学习。14个模型ID均新建、训练成员与任一R05 LOEO折不同；没有以R05模型替代。HISTORICAL_SEVEN通过冻结保存结果和逐ID输入/方法证明适配，162条结果精确匹配，旧检测器调用0；DIRECT_CORE_OR使用同合同10个规范偏差原子，固定基线不做数据选择。

## 成员、访问顺序和训练

三方法各有14折，每条监督阶段在该方法OOF中恰好一次：每方法162阶段（54 attack、54 pre、54 post，54完整三态）。486是重复方法评价记录，不是486独立样本。100描述阶段保持排除，UNKNOWN时间对照和MTC不补算FPR。

42条作业访问链均核对：只读train特征/标签 → train转换及学习器支持筛选/选规则 → 保存/加载/冻结模型 → 首次读本折outer_test特征 → 保存、关闭并对账预测 → 独立连接outer评价标签。固定基线也经此入口，但不拟合支持度/规则。核心视图仅使用R02与标签无关的固定缓存，本轮没有数值阈值学习；模型encoder均为空。

14折全部保持冻结精确成员，四个角色分区完整对账262阶段；bundle/session/triplet不跨两侧，R01声明的配置及关联边界原样保留。配置被完整排除在train之外，但所有测试环境在该折train中均有同环境材料，见fold_boundary_and_support及configuration_environment_support。

每个学习折从10个规范候选的20个正/反字面量起步，13个通过训练支持筛选，最终都选中 **DEVIATION:OFFDER-UA-001:POSITIVE**，1子句/1条件、复杂度2。来源O_u，别名OFFDER-UA-001；规范偏差的POSITIVE对应原目录条件的NEGATIVE方向，不能混称。公共测量门控与U语义不变。

12折train=153阶段、clean=102、预算floor(0.05×102)=5；留出tool-056与tool-058两折train=135、clean=90、预算4。所有训练模型clean报警0，各阶段决策覆盖1，支持度、集合预算和复杂度约束均满足。贪心状态HEURISTIC_FEASIBLE，停止no_positive_objective_improvement，不宣称全局最优或机制证明。全部候选支持与选择轨迹保留，不按外层成绩筛选。

## LOCO折外结果

| 方法 | 攻击TPR | pre报警 | post报警 | exact FTF | 决策覆盖 | 弃判 | 失败 | 原子/子句覆盖 | 复杂度 |
|---|---|---|---|---|---|---|---|---|---|
| GREEDY_OR | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 | 2 |
| HISTORICAL_SEVEN | 0/54 | 0/54 | 0/54 | 0/54 | 162/162 | 0/162 | 0/162 | 0/0 NE/null | 0 |
| DIRECT_CORE_OR | 24/54 | 0/54 | 0/54 | 0/54 | 24/162 | 138/162 | 0/162 | 1416/1620 | 20 |

主方法TPR=24/54=44.44%，配置宏平均=6/14=42.86%，exact FTF=24/54；pre/post各0/54、全部162阶段可决策。它比历史七条多检出24个攻击，但当前8个配置仍全部漏检。

DIRECT_CORE_OR也检出24/54，但30个攻击和全部108个clean阶段弃判，共138/162。其decided-clean分母0，值NOT_EVALUABLE/null；动作报警0不能解释为低误报。原子与子句覆盖均1416/1620；NW-005在全部阶段U，另NW-001/NW-002各21个U，保留原原因。无明确T且含U时OR仍U，不将U取反变T。历史七条适配模型结构显式0，原子/子句为0/0 NOT_EVALUABLE/null；不冒充原七条运行覆盖度。没有模型或大小未知时的R04-R1 NOT_EVALUABLE/null合同保持不变，本轮未出现该状态。

## 全部留出配置

下表均为GREEDY_OR/OP05。每折所选规则和复杂度相同；pre/post报警和失败/弃判均0，决策及原子/子句覆盖均完整。两固定基线的逐配置完整指标另存held_out_configuration_results和by_configuration。

| 折 | 留出配置 | train阶段/攻击 | train攻击检出 | clean预算/实际报警 | outer攻击检出 | 共享环境 |
|---|---|---|---|---|---|---|
| LOCO-v1-01 | w10-cdp-emulation-screen-metrics-only-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |
| LOCO-v1-02 | w10-cdp-emulation-timezone-only-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |
| LOCO-v1-03 | w6-tool-054-legacy-default-v1 | 153/51 | 21/51 | 5/0 | 3/3 | env-003 |
| LOCO-v1-04 | w6-tool-055-legacy-default-v1 | 153/51 | 21/51 | 5/0 | 3/3 | env-001 |
| LOCO-v1-05 | w6-tool-056-legacy-default-v1 | 135/45 | 15/45 | 4/0 | 9/9 | env-001, env-002, env-003 |
| LOCO-v1-06 | w6-tool-058-legacy-default-v1 | 135/45 | 24/45 | 4/0 | 0/9 | env-001, env-002, env-003 |
| LOCO-v1-07 | w9-rule-boundary-cdp-platform-only-v1 | 153/51 | 21/51 | 5/0 | 3/3 | env-003 |
| LOCO-v1-08 | w9-rule-boundary-cdp-resource-pair-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |
| LOCO-v1-09 | w9-rule-boundary-cdp-ua-only-v1 | 153/51 | 21/51 | 5/0 | 3/3 | env-003 |
| LOCO-v1-10 | w9-rule-boundary-cdp-ua-platform-desktop-v1 | 153/51 | 21/51 | 5/0 | 3/3 | env-003 |
| LOCO-v1-11 | w9-rule-boundary-cdp-webdriver-only-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |
| LOCO-v1-12 | w9-stealth-boundary-languages-only-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |
| LOCO-v1-13 | w9-stealth-boundary-plugins-mime-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |
| LOCO-v1-14 | w9-stealth-boundary-webgl-pair-v1 | 153/51 | 24/51 | 5/0 | 0/3 | env-003 |

未删除难配置；全部14个配置结果、训练支持、完整model ID/极性/来源与精确成员分别在MODEL_RULES、MODEL_MANIFEST、selected_rules、training_support_table和held_out_configuration_results中。配置×环境支持同时给train/outer身份；mechanism_id保持null。

## 与R05 LOEO分轨比较

R05的9个原模型和486条已关闭预测只作参照，未拟合或生成额外预测。三方法各自162个阶段的LOCO与LOEO决策逐ID完全一致，14个新LOCO学习模型和3个原LOEO学习模型也都选择同一规则签名；每个LOCO模型仍有独立新ID、真实创建时间与不同train成员。

规则与结果一致并不意味着两轨回答同一问题。LOCO按配置留出且共享环境，LOEO按环境关联组留出并受到配置组成差异影响；各自分母均单列54 attack/108 clean，未堆成更多独立样本或择优报告。LOCO中的环境分层只描述共享环境的结果，不称环境独立验证。

R07的AppWeb互补和36个检出集合并集没有被升级为新模型。本轮没有加入单层输入、联合候选、集成条件、补造规则或V2；R07已暴露结果未用于修改参数。

## 主张边界与未运行分支

本结果准确命名为“暴露材料上的回顾性配置留出/配置迁移”。训练/测试均来自同一历史材料，14折都共享环境和部分安装关联；不是新盲测、独立环境/批次/物理设备验证或机制泛化证明。clean只支持声明干预表面，有限样本零报警不保证总体FPR=0。

R08_MECHANISM保持NOT_EVALUABLE_UNVERIFIED_MECHANISM_PARTITION，mechanism_id/result=null；工具、配置、修改字段集合不充当机制标签。R08_PROSPECTIVE保持NOT_AVAILABLE/result=null，没有新材料、最终模型或确认访问。配置×环境表与不可评估机制表分开，未用旧数据重新切分填补。完整边界见generalization_claim_limits。

## 验证、预算与停止

新增轨独立核算2,067个指标单元（折总计、OOF总计及全部保存分层，13项指标），R05参照再核算1,638项；共3,705项。42个模型访问链/血缘、14份训练约束、14个配置边界、1,782原子及1,782子句解释、162条历史适配均通过保存结果复核。后处理没有真实fit、新阈值、新预测或原始特征重提取。

共享账本从57增至71/200次拟合，增量14；本次计费36.705145625秒，累计103.041795334/21600秒，剩余129次、21496.958204666秒。原72个R05/R06/R07账本记录及artifact_directory逐项不变。dispatcher SUMMARY.real_fits=71为累计值，不能误报为本轮71次。

R08父步骤PARTIALLY_COMPLETED，R08_CONFIG_TRANSFER完成待外部验收；其他分支明确不可评估/不可用。R07父步骤继续PARTIALLY_COMPLETED，主分支验收已单独登记，原负面结果/日志保留。历史文件保护与本次验收分开记录，旧清单中的状态/共享账本摘要仍代表旧执行时点，不回写旧验收。

完成后停止，等待审查。没有执行R09、其他分支、全开发集重拟合、V2、联合/集成、补采、攻击工具、旧S07、提交或推送。
