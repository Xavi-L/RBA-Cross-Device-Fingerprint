# 第二轮：App与独立Browser相互参照图稿

**初稿已生成／待导师选择。** 本目录交付F05a、F05b、F06a、F06b、F07a、F07b、F08共7幅独立素材；F编号不是最终论文图号，正文／附录位置和最终版面由导师决定。第一轮App图稿保持原样，第三轮F00、F09、F10等未执行。

本轮只读取保存结果，筛选、计数、换算比例并制图：0新增采集、0拟合、0选择、0模型或条件预测、0重新计时。参考提交为`5a6762b01ec3ab764ea56c6f741058888f80ade3`。当前源文件与导出关系见[FIGURES.json](FIGURES.json)，数值及保存产物检查见[CHECK.json](CHECK.json)，中英文论文图注及逐图证据边界见[CAPTIONS.md](CAPTIONS.md)。

| 素材 | 图稿 | 绘图数据 | 读图重点 |
|---|---|---|---|
| F05a 语言／时区双向作用 | [PNG](figures/F05a.png) · [SVG](figures/F05a.svg) | [CSV](data/F05a.csv) | 接受的跨端时区新增5次Browser时区检出；语言遗漏保留 |
| F05b 资源完整方法与固定检查 | [PNG](figures/F05b.png) · [SVG](figures/F05b.svg) | [CSV](data/F05b.csv) | M在Browser内存4方向补充B的3次信号；MTC正常背景紧邻展示 |
| F06a 四视图修改检出 | [PNG](figures/F06a.png) · [SVG](figures/F06a.svg) | [CSV](data/F06a.csv) | P0／P1／P2分开，P2双端与关系树同为4/8 |
| F06b 四视图正常报警 | [PNG](figures/F06b.png) · [SVG](figures/F06b.svg) | [CSV](data/F06b.csv) | 与F06a成对使用；P2无收益，P1训练正常仍2/34报警 |
| F07a 资源增量家族检出 | [PNG](figures/F07a.png) · [SVG](figures/F07a.svg) | [CSV](data/F07a.csv) | S0为保留方法13/26；19/26仅是未通过的诊断组合 |
| F07b 资源MTC正常代价 | [PNG](figures/F07b.png) · [SVG](figures/F07b.svg) | [CSV](data/F07b.csv) | 12条分配置记录；明确输出567/630降为560/630 |
| F08 真实语言偏好案例 | [PNG](figures/F08.png) · [SVG](figures/F08.svg) | [CSV](data/F08.csv) | 7个原位置和各方案角色；正常偏好不能改标为攻击 |

每幅PNG至少300 dpi，SVG保留矢量图元；工作尺寸、字号、格式检查和视觉核查的实际范围以`FIGURES.json`与`CHECK.json`为准。尚未查看的格式不得据另一格式的验收声称视觉通过。长来源ID保留在CSV，不占图面；不交付字体文件或复制私有原始指纹。

## 方法和材料角色

| 图中对象 | 实际身份 | 不能混称的对象 |
|---|---|---|
| Full App | 当前`APP_FULL`，不读取独立Browser | 四视图`V_APP`有限表示小树 |
| App + cross-endpoint timezone／S0 | 已接受`PAIRED_BASE`，冻结App加原跨端时区C1 | 资源增强后已接受模型 |
| Fixed M | Native与Browser内存上界检查 | 完整双端模型 |
| Fixed B | Browser内存>8固定检查 | 完整Browser-only方法 |
| Fixed W | 两端Web内存不同固定检查 | 已证明独立新增收益的完整方法 |
| S0+M／S0+B／S0+W | 未通过接入要求的保存诊断组合 | M／B／W单项，或重新选出的模型 |
| 四视图树 | 相同深度3小树；App 7项、Browser 4项、合用11项，关系增强加C1/C2 | App177／Browser67全部字段上限 |

T表示报警、F表示未报警、U表示无法判断、FAILED表示执行失败。修改上的T为检出，正常上的T为正常报警；F不等于安全认证。N是位置／记录数，不是设备数。配置不会产生三倍独立样本，不为三配置或三方案绘制置信区间或显著性标记。

F05a固定为18先导＋42匹配，共60位置：14修改、46正常。F05b是另一资源54位置：12修改、42正常。两批分别成图，不组成一个新总准确率。F07只按其原1005成员设计报告：744开发（718正常＋26修改），261历史正常（原144＋117分组保留）。已保存资源结果按实际模型ID读取，03的正常报警不套用01。

F06的三个方案保留原角色：P0训练690，在其中小实验60位置显示训练内结果；P1训练630 MTC＋42匹配，旧先导18整批留出；P2训练630 MTC＋18先导，匹配42整批留出。主图修改N为14／6／8，正常N为46／12／34。两批均有开发接触历史，整批留出不是新盲测。P1训练匹配正常2/34报警与每个双端树33/951部分缺测输入在配套表保留。

## 配套表与来源

[data目录](data/)中的配套表与映射补充图面。以下链接均指向本轮保存文件：

| 范围 | 保存表与映射 | 审阅内容 |
|---|---|---|
| F05 两批与配置 | [分批状态](data/T04_f05_cohorts.csv) · [成员来源定位](data/T04_f05_members.csv) · [配置压缩依据](data/T04_f05_compression.csv) | 60与54分别保留；三个配置不增分母 |
| F05 固定条件正常背景 | [MTC条件状态](data/T04_f05_mtc_conditions.csv) | M/B/W原630／144／117组，891仅辅助合计 |
| F05 名称与角色 | [方法映射](data/T04_f05_methods.csv) · [家族映射](data/T04_f05_families.csv) | Full App、PAIRED_BASE与固定检查分别命名 |
| F06 完整状态 | [全部角色与批次](data/T04_four_view_all_cohorts.csv) · [主图分家族](data/T04_four_view_main_families.csv) · [输入完整性](data/T04_four_view_input_completeness.csv) | 原N/T/F/U/FAILED、P1训练2/34反例、P2修改方向、每个双端树33/951部分缺测 |
| F06 方案与模型身份 | [模型映射](data/T04_four_view_model_mapping.csv) · [方案映射](data/T04_four_view_scheme_mapping.csv) · [视图映射](data/T04_four_view_view_mapping.csv) | 12棵树、训练／评价角色与有限表示范围 |
| F07 原24候选 | [候选检查](data/T04_resource_candidates.csv) · [八家族状态](data/T04_resource_families.csv) · [候选覆盖](data/T04_resource_candidate_quality.csv) | 原feasible/selected/reasons、容量及微平均／宏平均，不重新选择 |
| F07 正常分组 | [各来源正常状态](data/T04_resource_normals.csv) · [完整批次状态](data/T04_resource_cohorts.csv) · [辅助合计](data/T04_resource_aggregates.csv) | MTC630、历史144／117逐配置保留；261与718合计不替代原组，小实验正常88另列 |
| F07 增量与反例 | [状态变化计数](data/T04_resource_deltas.csv) · [专项正常状态](data/T04_resource_special_normals.csv) · [3条M正常反例](data/T04_resource_normal_counterexamples.csv) | 新增未知与正常报警分别保留；反例为2条discovery和1条reserved，使用脱敏案例名与保存汇总定位，不复制原成员关联 |
| F07 图面映射 | [家族映射](data/resource_family_mapping.csv) · [组合映射](data/resource_combination_mapping.csv) | S0与S0+M/B/W身份分开，其他组合仍为诊断 |
| F08 案例与角色 | [7个原位置及来源定位](data/F08.csv) | 每行P方案训练／整批留出角色；7×3输出不是21个独立样本 |

主要来源为[统一机器表](../../../deliverables/app_browser_evidence_consolidation_v1/tables.json)、[资源联合保存结果](../../../deliverables/app_resource_constrained_extension_v1/results/)、[资源固定条件保存汇总](../../../deliverables/app_resource_paired_validation_v1/results/summary/)、[四视图主比较](../../../deliverables/cross_endpoint_four_view_comparison_v1/results/main_comparison.csv)及其[完整汇总](../../../deliverables/cross_endpoint_four_view_comparison_v1/results/summary/summary.csv)、[原7行案例表](../../../deliverables/prepaper_evidence_closeout_v1/figures/fig04_preference_recipe.csv)。每幅筛选、汇总、压缩依据和源摘要由`FIGURES.json`记录。旧第一轮与其他`deliverables`图稿不覆盖。

## 运行与检查

在仓库根目录运行一次制图：

```bash
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B paper/figures/round2_paired/plot_round2.py
```

只检查已经保存的本轮产物：

```bash
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B paper/figures/round2_paired/plot_round2.py --check-only
```

入口不加载模型对象，不导入原实验拟合／预测／条件计算／选择入口，不执行第一轮主流程，不读取私有原始指纹。图面状态来自既存逐位置输出或保存汇总，不重新计算C1或资源条件。检查需对照原始计数和图元，区分0与N=0，避免同时累加`ALL`和细分行，并确认源摘要前后不变。检查保存产物不能冒充视觉验收；最终PNG逐幅及工作尺寸校样的人工查看范围、SVG结构／尺寸检查范围记录在`CHECK.json`。

## 审阅时必须同时保留的结果

F05a支持当前接受方法在Browser时区方向的5次局部增益；F05b支持Native参照在所测Browser内存4方向超出单字段阈值的3次固定条件信号。F06a/b共同显示关系在P0和P1减少正常报警，而P2没有收益。F07a的更高检出必须与F07b的接入失败一起使用：只有S0保留，资源诊断组合不能写成最终模型成绩。

正常代价分别由F05b的MTC条件背景、F06b及其P1训练反例、F07b的报警与未知、F08的两条正常语言偏好承担。W的正常报警与候选覆盖不足、24组合中真实的容量拒绝、03配置差异均保留。既有缺测说明中的7条新增训练未知、2条历史未知、3条M正常反例沿用原身份，不通过补值或重算消除。

本轮止于初稿供导师选择；不新增实验、不重训、不重新选择、不自动提交或推送，不继续第三轮。
