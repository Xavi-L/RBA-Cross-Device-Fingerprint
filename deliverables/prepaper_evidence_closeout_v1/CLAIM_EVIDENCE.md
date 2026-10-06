# B3-B 主张与证据索引

本文支持开始撰写方法与评价，范围是 **paired244语言/时区双向干预的探索性证据，配合App侧历史专项**。三个研究层次分别保留模型身份：App历史开发/专项、B2-C有限增量规则方法、B3-A固定语言/时区四视图分类器。三者不拼接最好数字，树的加权正类分数不称作真实用户被攻击的概率。

机器索引：[metric_index.jsonl](tables/metric_index.jsonl)，每行登记模型、输入范围、批次、角色、计数/分母、U/FAILED、成员ID和逐条证据路径。所有图均有同名CSV；候选图和英文图注见 [FIGURES.json](figures/FIGURES.json)。

| ID | 可支持的有限主张 | 可复核证据与边界 |
|---|---|---|
| C01 | 固定单端视图存在正常/干预输入重合，缺少另一端会丢失部分区分信息。 | [B3-A相同测量分组](../cross_endpoint_four_view_comparison_v1/results/input_collisions.json)：App先导12正常与6个Browser干预相同；Browser匹配输入也有正常与App干预重合。仅限已声明视图，未证明全244字段的单端性能上限。 |
| C02 | 同学习器中，显式关系在部分开发设置减少正常报警，P2无收益也是结果。 | [四视图主表](tables/four_view.csv)、[fig01](figures/fig01_four_view_detection.svg)、[fig02](figures/fig02_four_view_normal_alarms.svg)。P0正常32/46→0/46，P1为12/12→0/12；P2均4/8检出、6/34正常报警。P1训练匹配仍2/34，详见[全来源附表](tables/four_view_all_cohorts.csv)。 |
| C03 | 正常设置反例实际影响增量集合选择。 | 原R_FULL选择C1；只去匹配正常组报警上限后，三个基础配置均选择C2。见[12个新集合检查](results/candidate_checks.json)、[消融表](tables/rule_ablation.csv)。两条正常Browser偏好均保留为T；其余正常预算和90%覆盖仍生效。不是完全去掉正常约束。 |
| C04 | C2的首选标签不一致会同时触发正常偏好与受控语言修改。 | [逐条反例](tables/preference_examples.csv)、[fig04](figures/fig04_preference_recipe.svg)。这里的C2只用两端language；完整列表不同，实际长度3与1不能说成全部原始输入相同。P0 REL采用长度<=2.5，存在配方依赖。 |
| C05 | 去跨端增量模块会失去当前已确认的Browser时区增益。 | R_NO_CROSS复用原S0，每基础配置2/14；R_FULL为7/14，差异5个Browser时区。见[逐成员转换](tables/rule_transitions.jsonl)。这不是重训App候选池，也不是B3-A的V_APP。 |
| C06 | “去匹配正常组报警上限”的更高总检出伴随检出交换及正常代价。 | 每配置9/14，相对R_FULL新增7语言、损失5 Browser时区；匹配正常增加2/34，历史144增加1个报警。不能只写“提升2次”，也不替换主模型或提高部署容忍度。 |
| C07 | 广机型正常证据、缺测与配对语义实质影响可评价范围与选择。 | [fig03](figures/fig03_rule_mtc_states.svg)、[MTC四状态表](tables/rule_mtc_composition.csv)。S12明确输出566/630<567/630，仍被拒绝。树双端有33/951部分缺测输入；二值输出没有恢复这些观测。 |
| C08 | 离线计算成本取决于调用入口与准备范围，状态OR不是完整推理。 | [成本表](tables/cost.csv)、[计时边界](timing/TIMING_FREEZE.json)、[原始批次](timing/batches.jsonl)、[逐条等价](timing/equivalence.jsonl)。B2-C公开接口含基础模型读取/摘要校验，树接口从派生cells开始；另列关系准备与已加载raw包装。P95是10遍批次均摊分布。 |
| C09 | 既有采集流程含设置、持久化等待、控制、上传、配对等待与恢复。 | [60条既有日志时间](existing_times/collection_log_intervals.csv)。只减同host UTC时钟的起止；15秒等待单列，纯探针时间未记录。不是新的采集或设备端性能测试。 |
| C10 | App内部参照的历史专项可作为独立附录证据。 | [memory](../memory_relation_validation_v1/REPORT.md)、[timezone](../timezone_relation_validation_v1/REPORT.md)、[screen](../screen_geometry_observation_v1/REPORT.md)，数据单位见[范围表](tables/data_scope.csv)。保留各自分母、工程版本和验证范围，不冒充本轮14次双向干预的额外样本。 |

## 明确不支持的表述

- 全244字段单端方法的性能上限，或完整系统普遍100%检出、零误报。
- P0高分能够迁移到任意设备、浏览器、脚本或语言修改；全面Browser工具覆盖已经完成。
- B3-A四视图就是主规则方法全部消融，或P1/P2是未接触的前瞻盲测。
- 树的二值输出修复旧缺测；多个基础配置、重复阶段或两个端能增加独立样本量。
- 四集合有限最优等同全局最优；加权predict_proba等同已校准部署攻击概率。
- 固定条件需要人为构造ROC，或当前受控正负比例的Precision/F1可以外推真实部署。

## 真正影响论文主张的剩余问题

广泛Browser工具/参数覆盖、未接触的新设备与独立泛化验证尚未完成，因此论文应保持探索性范围。正常浏览器偏好与脚本的配方/环境差异仍限制因果解释；需要在正文保留反例而非承诺普遍意图识别。历史缺测保留为未知，现有计时缺少设备采集与纯探针的统一时钟证据。以上限制不自动转化为新采集或调参任务；本轮完成后转入写作。
