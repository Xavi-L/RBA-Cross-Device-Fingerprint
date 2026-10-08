# 论文素材图集：供导师选用

本入口按“方法—App主体—双端作用—正常代价—独立专项—成本”组织三轮独立素材。**初稿供导师选用；素材编号不是最终论文图号。** 正文／附录建议仅帮助选材，章节、图号、页数、版式与最终取舍仍由导师决定。三轮共14幅独立图稿及T05成本表已生成。第三轮F00、F09及T05的验收范围见[第三轮入口](round3_overview/README.md)与[CHECK.json](round3_overview/CHECK.json)。本导航不重绘旧图、不修改旧CSV。

三轮入口：[第一轮App主体](round1_app/README.md) · [第二轮双端作用](round2_paired/README.md) · [第三轮方法／Host专项／成本](round3_overview/README.md)。当前制图状态见[制图清单](../../RBA_CURRENT_FIGURE_PLAN.md)，综合证据口径见[导师报告](../../RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md)及[统一证据报告](../../deliverables/app_browser_evidence_consolidation_v1/REPORT.md)。旧两轮README中的“后续轮次未执行”是当轮停止点的历史说明；跨轮当前入口以本页及制图清单为准，旧交付文件保持原样。

## 方法

| 素材 | 短问题 | 图稿 | 图注、数据／映射 | 来源入口 | 正文／附录候选（导师定） |
|---|---|---|---|---|---|
| F00 | 从哪里观察、怎样选择、当前判断需要什么？ | [PNG](round3_overview/figures/F00.png) · [SVG](round3_overview/figures/F00.svg) | [中英图注](round3_overview/CAPTIONS.md) · [节点](round3_overview/data/F00_nodes.csv) · [连线](round3_overview/data/F00_edges.csv) | [App依赖](../../deliverables/app177_core_ablation_v1/CANDIDATE_DEPENDENCIES.md) · [跨端协议](../../deliverables/cross_endpoint_constrained_extension_v1/PROTOCOL.md) | 正文方法示意候选 |

F00区分离线选择和当前记录判断。App-only与配对输入是不同接口，不能解释为自动回退系统。目录规模App177／paired244不等于全部字段可用或端到端训练；来源标识用于配对，不是检测特征。虚线专项表示测试过但未整合，不是未来自动启用。

## App主体

| 素材 | 短问题 | 图稿 | 图注、绘图数据 | 来源入口 | 正文／附录候选（导师定） |
|---|---|---|---|---|---|
| F01 | 哪些修改能检出，去掉组件后怎样？ | [PNG](round1_app/figures/F01.png) · [SVG](round1_app/figures/F01.svg) | [图注](round1_app/CAPTIONS.md) · [CSV](round1_app/data/F01.csv) | [14配置原计数](../../deliverables/app177_core_ablation_v1/results/summary/configurations14.csv) | 正文主结果或附录完整热图；必须配F02 |
| F03a | 完整App方法在内存修改上有何表现？ | [PNG](round1_app/figures/F03a.png) · [SVG](round1_app/figures/F03a.svg) | [图注](round1_app/CAPTIONS.md) · [CSV](round1_app/data/F03a.csv) | [整模专项原计数](../../deliverables/app177_core_ablation_v1/results/summary/specialists.csv) | 正文组件证据候选 |
| F03b | 固定内存关系比单字段阈值多看到什么？ | [PNG](round1_app/figures/F03b.png) · [SVG](round1_app/figures/F03b.svg) | [图注](round1_app/CAPTIONS.md) · [CSV](round1_app/data/F03b.csv) | [固定条件保存汇总](../../deliverables/memory_relation_validation_v1/summary.json) | 正文解释或附录固定条件候选 |
| F04 | 正常系统换区与网页单改能否区分？ | [PNG](round1_app/figures/F04.png) · [SVG](round1_app/figures/F04.svg) | [图注](round1_app/CAPTIONS.md) · [CSV](round1_app/data/F04.csv) · [完整正常／修改状态](round1_app/data/F04_totals.csv) | [整模专项原计数](../../deliverables/app177_core_ablation_v1/results/summary/specialists.csv) · [时区语义](../../deliverables/timezone_relation_validation_v1/SEMANTICS.md) | 正文正常变化证据候选 |

配套表：[T01材料范围与用途](round1_app/data/T01.csv)、[T02主结果](round1_app/data/T02.csv)、[T03正常分组](round1_app/data/T03.csv)。Full App不含独立Browser C1或新Host几何。F03a的完整模型和F03b的固定条件是不同对象，不能互换成绩。

## 双端作用

| 素材 | 短问题 | 图稿 | 图注、绘图数据 | 来源入口 | 正文／附录候选（导师定） |
|---|---|---|---|---|---|
| F05a | 接受的跨端时区在哪个方向补充检出？ | [PNG](round2_paired/figures/F05a.png) · [SVG](round2_paired/figures/F05a.svg) | [图注](round2_paired/CAPTIONS.md) · [CSV](round2_paired/data/F05a.csv) | [接受模型与结果](../../deliverables/cross_endpoint_constrained_extension_v1/REPORT.md) | 正文双端作用候选 |
| F05b | 资源完整方法与固定检查分别看到什么？ | [PNG](round2_paired/figures/F05b.png) · [SVG](round2_paired/figures/F05b.svg) | [图注](round2_paired/CAPTIONS.md) · [CSV](round2_paired/data/F05b.csv) · [MTC固定条件背景](round2_paired/data/T04_f05_mtc_conditions.csv) | [资源固定条件结果](../../deliverables/app_resource_paired_validation_v1/results/summary/) | 正文解释或附录诊断候选 |
| F06a | 四视图小树的修改检出如何变化？ | [PNG](round2_paired/figures/F06a.png) · [SVG](round2_paired/figures/F06a.svg) | [图注](round2_paired/CAPTIONS.md) · [CSV](round2_paired/data/F06a.csv) | [四视图原比较](../../deliverables/cross_endpoint_four_view_comparison_v1/results/main_comparison.csv) | 正文方法比较候选；必须配F06b |
| F07a | 资源组合检出提高后是否真正获接入？ | [PNG](round2_paired/figures/F07a.png) · [SVG](round2_paired/figures/F07a.svg) | [图注](round2_paired/CAPTIONS.md) · [CSV](round2_paired/data/F07a.csv) · [全部24候选](round2_paired/data/T04_resource_candidates.csv) | [原选择结果](../../deliverables/app_resource_constrained_extension_v1/results/models.json) | 附录有限接入尝试候选；必须配F07b |

F05a的语言／时区60位置与F05b资源54位置分开；不组成新总准确率。四视图树是有限语言／时区方法比较，不是App177／Browser67全部字段的上限。资源S0+M/B/W的较高检出是未通过约束的诊断结果，只有S0保留。

## 正常代价与案例

| 素材 | 短问题 | 图稿 | 图注、绘图数据 | 来源入口 | 正文／附录候选（导师定） |
|---|---|---|---|---|---|
| F02 | 检出收益伴随多少正常报警与无法判断？ | [PNG](round1_app/figures/F02.png) · [SVG](round1_app/figures/F02.svg) | [图注](round1_app/CAPTIONS.md) · [CSV](round1_app/data/F02.csv) · [T03全部正常分组](round1_app/data/T03.csv) | [MTC原计数](../../deliverables/app177_core_ablation_v1/results/summary/mtc.csv) | 正文正常代价候选；与F01成套 |
| F06b | 四视图树的正常报警是否同步改善？ | [PNG](round2_paired/figures/F06b.png) · [SVG](round2_paired/figures/F06b.svg) | [图注](round2_paired/CAPTIONS.md) · [CSV](round2_paired/data/F06b.csv) · [训练／留出明细](round2_paired/data/T04_four_view_all_cohorts.csv) | [四视图原汇总](../../deliverables/cross_endpoint_four_view_comparison_v1/results/summary/summary.csv) | 正文正常比较候选；与F06a成套 |
| F07b | 资源接入为何因报警或未知未通过？ | [PNG](round2_paired/figures/F07b.png) · [SVG](round2_paired/figures/F07b.svg) | [图注](round2_paired/CAPTIONS.md) · [CSV](round2_paired/data/F07b.csv) · [原拒绝原因](round2_paired/data/T04_resource_candidates.csv) | [资源接入保存报告](../../deliverables/app_resource_constrained_extension_v1/REPORT.md) | 附录约束与代价候选；与F07a成套 |
| F08 | 正常语言偏好与脚本修改为何不能仅凭偏离分开？ | [PNG](round2_paired/figures/F08.png) · [SVG](round2_paired/figures/F08.svg) | [图注](round2_paired/CAPTIONS.md) · [7案例CSV](round2_paired/data/F08.csv) | [原案例表](../../deliverables/prepaper_evidence_closeout_v1/figures/fig04_preference_recipe.csv) | 正文或附录案例表候选，可最终作为Table |

F06a／F06b保留P1训练正常反例与P2没有额外收益；不能只取P0最好结果。F08本质是案例表，最终可转论文表格，稳定素材名暂不改。补充[输入完整性](round2_paired/data/T04_four_view_input_completeness.csv)、[资源状态变化](round2_paired/data/T04_resource_deltas.csv)和[资源正常反例](round2_paired/data/T04_resource_normal_counterexamples.csv)。

## 独立Host专项

| 素材 | 短问题 | 图稿 | 图注、绘图数据 | 来源入口 | 正文／附录候选（导师定） |
|---|---|---|---|---|---|
| F09 | 当前网页占用区域能否减少固定高度误报？ | [PNG](round3_overview/figures/F09.png) · [SVG](round3_overview/figures/F09.svg) | [图注](round3_overview/CAPTIONS.md) · [CSV](round3_overview/data/F09.csv) · [分场景明细入口](round3_overview/README.md) | [v15正式结果](../../deliverables/screen_geometry_observation_v1/SUMMARY.json) · [几何语义](../../deliverables/screen_geometry_observation_v1/SEMANTICS.md) | 正文局部例证或附录专项候选 |

F09是三个固定条件的专项比较，未纳入当前完整App模型。仅用v15正式72位置，正常布局中间6位置是66正常的子集；不叠加分母，不混入v16工程材料。它不能替代F01／原App整模中的屏幕表现或屏幕专项整模误报结果；Host也不是硬件真值认证层。

## 成本

| 素材 | 短问题 | 可读表与结构化明细 | 来源入口 | 正文／附录候选（导师定） |
|---|---|---|---|---|
| F10／T05 | 当前双端基础与比较树各阶段需要多少计算和模型资源？ | [T05分阶段成本表](round3_overview/T05.md) · [本轮表格索引](round3_overview/README.md) | [全部21模型／148阶段组成本](../../deliverables/prepaper_evidence_closeout_v1/tables/cost.csv) · [模型资源](../../deliverables/prepaper_evidence_closeout_v1/tables/model_resources.csv) · [冻结计时设置](../../deliverables/prepaper_evidence_closeout_v1/timing/TIMING_FREEZE.json) | 正文简表或附录完整边界表候选 |

F10以T05表格交付，**图形化未制作／暂不需要**，不将其写成缺实验或已生成成本图。主表按方法覆盖展示三个当前App+C1配置及P0四视图树，不按速度挑行。加载按模型、其他阶段通常按固定60位置批次均摊；不同起点与重叠路径的中位数／P95不能相加。P95是10批均摊值的分位数，不是单请求尾延迟。后续资源组合与App新消融没有重新计时，不套用旧值。[采集区间](../../deliverables/prepaper_evidence_closeout_v1/existing_times/collection_log_intervals.csv)与[历史训练记录](../../deliverables/prepaper_evidence_closeout_v1/existing_times/historical_training_timing.json)单列范围，未记录的纯探针耗时不补造。

## 成套使用与共同口径

1. F01检出必须同时保留F02正常输出，不能只报告取消正常报警约束后的收益。
2. F06a与F06b成套，保留P1训练反例和P2无收益。
3. F07a更高检出必须同时保留F07b的未通过原因，不能把诊断组合写成资源增强已接受方法。
4. F03a完整模型与F03b固定条件不能互相替换；同批分析不增加独立样本数。
5. F09固定Host专项不能替代当前完整App模型的屏幕误报结果。

T为报警、F为未报警、U为无法判断、FAILED为执行／绑定失败。F不是设备安全证明，0计数与无数据不同。不同分母、开发／历史评价用途和配置分别保留；不取最好配置代表整体，不把重复评价当新独立样本。MTC144／117保持历史评价身份，不能称新盲测。

前两轮仅核对文件存在、命名和图注／数据链接；它们的原始视觉验收范围分别见[第一轮检查](round1_app/CHECK.json)和[第二轮检查](round2_paired/CHECK.json)。第三轮实际视觉与数值范围单列于[第三轮检查](round3_overview/CHECK.json)，不由其他格式或旧验收推定。本轮不重做实验、不复制整套raw／日志，不创建新网站或额外发布渠道。

**F11仍为可选／未制作。** 剩余工作是导师选材、章节对应与版面／文字修订；不自动开启F11、新实验、调模型或整篇论文写作。
