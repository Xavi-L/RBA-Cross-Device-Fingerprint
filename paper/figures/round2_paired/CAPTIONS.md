# 第二轮双端与资源图注

状态：**初稿已生成／待导师选择**。F05a、F05b、F06a、F06b、F07a、F07b、F08是素材编号，正文／附录位置及最终论文图号待导师决定。图内数字对应本目录绘图CSV指向的保存结果；本轮不采集、拟合、选择、预测或重新计时。

T＝报警；F＝未报警；U＝无法判断；FAILED＝执行失败。F不表示已经证实安全。修改记录上的T作为检出，正常记录上的T作为正常报警。N是记录／评价位置数，不是独立设备数。三配置和三个P方案都不增加独立样本数，不能据此计算重复实验误差条。材料已有研究接触历史，整批留出的开发比较也不是新盲测。

**方法身份必须随图保留。** Full App是当前`APP_FULL`，不读取独立Browser；App + cross-endpoint timezone是接受的`PAIRED_BASE`，也是资源实验的S0。固定检查M＝Native参照的Browser内存上界，B＝Browser报告内存>8，W＝两端Web内存不同。M/B/W单项与S0+M/B/W诊断组合是不同对象。四视图树只使用App侧7项、Browser侧4项语言／时区派生测量；双端合用11项，关系增强再加C1/C2。它们不是Full App，也不是全部177／67字段的性能上限。

## F05a：语言／时区修改的双向作用

**中文读图结论。** 在原先导18＋匹配对照42的60个配对位置中，App语言、App时区、Browser语言、Browser时区有效修改分别为2、2、5、5次。Full App的检出依次为0/2、2/2、0/5、0/5；接受的App + cross-endpoint timezone依次为0/2、2/2、0/5、5/5。两方法在46条正常记录上均为T/F/U/FAILED＝0/46/0/0，四个修改家族均无U或FAILED。三个原配置的所有展示计数相同，图面压缩为每配置共同计数，CSV保留三配置；5/5没有变成15/15。

**能支持。** 在这60个已用于开发的位置上，跨端时区为冻结App方法补充了5次Browser时区识别，原App时区2次检出保留。**不能支持。** 语言修改仍漏检；不能宣称双端语言问题已解决、所有跨端方向均有效，或在未见设备／修改工具上泛化。正常0/46不能代替广机型正常评价，MTC代价另见资源图和配套表。

**English caption.** Direction-specific detection on 60 previously used development positions (18 pilot and 42 matched-control positions): App language (N=2), App timezone (N=2), Browser language (N=5), and Browser timezone (N=5). Full App uses the current App method without independent Browser inputs. App + cross-endpoint timezone is the retained PAIRED_BASE method. Adding the cross-endpoint timezone check detects five Browser timezone modifications; both language families remain undetected. Each cell reports alarm count/position count. All displayed N/T/F/U/FAILED counts agree across the three frozen configurations, so the figure shows their common counts; configuration-specific rows remain in the CSV. Both methods produce 0 alarms, 46 non-alarms, 0 unknowns and 0 failures on the 46 normal positions. These are development results, not a new blind evaluation.

**保存来源。** [members.jsonl](../../../deliverables/app_resource_constrained_extension_v1/results/members.jsonl)＋[inputs.jsonl](../../../deliverables/app_resource_constrained_extension_v1/results/inputs.jsonl)中`cohort in {pilot18,b2b42}`，按实际`base_model_id`读取`app_states/base_states`；与[统一paired表](../../../deliverables/app_browser_evidence_consolidation_v1/tables.json)及原跨端汇总交叉核对，不重新计算C1或组合。

## F05b：资源完整方法与固定检查

**中文读图结论。** 资源批次54条含四家族各3次有效修改与42条正常。Full App和PAIRED_BASE均检出App资源16/48与App内存4各3/3，对两个Browser修改家族均0/3。固定M对App两家族均0/3、Browser两家族均3/3；B仅Browser资源16/48为3/3，其余0/3；W四家族均3/3。所有列在本批正常记录上均为0/42报警，42/42明确不报警，U/FAILED均0。完整方法的三个配置展示计数相同；固定检查每个位置仅计一次。

**能支持。** 在本批Browser内存4方向，M补充B没有的3次信号；Browser内存16同时触发M与B。App侧6次已由Full App发现，W的App侧触发属于重叠证据。**不能支持。** 这不是五个同流程训练模型的比较，B不是完整Browser-only方法；单条件信号不代表资源已接入完整方法。本批原报告内存为2，改4是向上变化，未覆盖向下、上界以内或双端协调修改。

**必须紧邻保留的正常背景。** 固定条件的MTC891合计T/F/U/FAILED依次为M：3/838/50/0，B：0/841/50/0，W：62/741/88/0。它们是历史条件诊断，原630／144／117分组保留在T04；891合计不能代替分组评价。小批次0/42不表示一般正常设备没有代价。3条M正常触发保持有效正常反例，不改成U。

**English caption.** Full methods and fixed resource checks on 54 paired resource positions: three modifications per family and 42 normal positions. The full methods detect the six App-side modifications but none of the six Browser-side modifications. Fixed checks M, B and W respectively test a Native-referenced upper bound on Browser memory, Browser memory >8, and unequal Web memory reports across endpoints. M detects Browser memory=4 where B does not (3/3 versus 0/3); Browser memory=16 triggers both. W overlaps the App method on App-side modifications. Full-method counts agree across all three configurations; fixed checks count each position once. All columns have 0/42 normal alarms and no unknown or failed outputs in this small batch. Historical MTC normal counts (T/F/U/FAILED; N=891) are M=3/838/50/0, B=0/841/50/0 and W=62/741/88/0; the original 630/144/117 groups remain separate in T04. Memory=4 was an upward change from 2. These local condition effects neither establish accepted resource augmentation nor cover arbitrary memory manipulations.

**保存来源。** 资源联合`members/inputs`的`resource54`原成员；固定条件与[原资源分场景汇总](../../../deliverables/app_resource_paired_validation_v1/results/summary/scenarios.csv)核对，正常背景读取[mtc.csv](../../../deliverables/app_resource_paired_validation_v1/results/summary/mtc.csv)。不合并F05a的60条与本图54条形成新总准确率。

## F06a：四视图修改检出

**中文读图结论。** 同顺序四视图为App only、Browser only、Both、Both + relations，均为同容量深度3小树。P0检出依次4/14、14/14、14/14、14/14；P1依次6/6、6/6、6/6、6/6；P2依次8/8、4/8、4/8、4/8。主图所有U/FAILED均0，必须与F06b配套使用，不能只凭单端高检出推断其感知了另一端修改。

| 方案 | 原训练材料 | 图中评价位置与角色 | 修改N／正常N |
|---|---|---|---|
| P0 | 630 MTC＋18先导＋42匹配，共690 | 先导与匹配60条的训练内开发结果 | 14／46 |
| P1 | 630 MTC＋42匹配，共672 | 旧先导18条整批留出的开发比较 | 6／12 |
| P2 | 630 MTC＋18先导，共648 | 匹配42条整批留出的开发比较 | 8／34 |

**能支持。** 固定有限表示和容量下，当前材料可用于比较可见信息；跨端关系的正常侧影响必须结合F06b判断。**不能支持。** P2的Both与Both + relations均只检出4/8，没有关系增益；其App方向0/4、Browser方向4/4，训练没有App方向修改，不能声称覆盖所有家族。P1/P2不是新盲测，环境、版本和配方一起变化，不能单独归因于某版本。三个方案不能相加成28次独立修改测试或用方案波动生成误差条。

**English caption.** Detection under four fixed depth-3 tree views: seven App-side language/timezone measurements, four Browser-side measurements, their eleven-measurement union, and that union with explicit C1/C2 relations. P0 trains on 690 positions and reports in-sample results on its 60 small-experiment positions (14 modifications). P1 trains on 630 MTC plus 42 matched positions and holds out all 18 pilot positions (6 modifications). P2 trains on 630 MTC plus 18 pilot positions and holds out all 42 matched positions (8 modifications). P1/P2 are historically exposed whole-batch development comparisons, not new blind tests. Counts are T/N, with no unknown or failed main outputs. Both and Both + relations detect 14/14, 6/6 and 4/8 under P0, P1 and P2, respectively. P2 provides no relation benefit: both views detect 0/4 App-side and 4/4 Browser-side modifications, and its training data contain no App-side modifications. Read jointly with F06b; high detection alone can reflect persistent normal alarms. These limited views do not represent the full 177/67-field feature spaces.

**保存来源。** [main_comparison.csv](../../../deliverables/cross_endpoint_four_view_comparison_v1/results/main_comparison.csv)全部12个格与[summary.csv](../../../deliverables/cross_endpoint_four_view_comparison_v1/results/summary/summary.csv)逐角色、批次核对；旧[four_view.csv](../../../deliverables/prepaper_evidence_closeout_v1/tables/four_view.csv)仅交叉参照。

## F06b：四视图正常报警

**中文读图结论。** 按F06a相同四视图顺序，P0正常报警依次2/46、30/46、32/46、0/46；P1依次12/12、12/12、12/12、0/12；P2依次32/34、6/34、6/34、6/34。加关系使P0、P1的Both正常报警从32/46、12/12降为0/46、0/12；P2同为6/34，没有收益。主图正常U/FAILED均0。

**紧邻反例。** P1关系树在其**训练匹配正常**上仍为2/34报警，不能只凭留出的0/12宣布全程无误报。每个双端小树的951个已保存输入位置中均有33个部分缺测；二值输出不等于恢复底层观测。训练、整批留出和历史MTC144／117的N/T/F/U/FAILED及输入完整性均在T04分别保留；历史261合计不并入主图正常分母。

**能支持。** 明确关系在P0和一个整批留出方向减少正常报警，收益局限于当前表示与材料。**不能支持。** P2没有复现收益，P1训练反例仍在；不能宣称关系树始终零误报，或二值输出意味着缺测问题已解决。P1单端对修改6/6报警也对正常12/12报警，不能据其高检出推断跨端识别能力。

**English caption.** Normal alarms accompanying F06a, with identical view and plan order. Normal denominators are 46 for P0 (in-sample development), 12 for P1 (held-out pilot), and 34 for P2 (held-out matched batch). Adding explicit relations reduces Both-view alarms from 32/46 to 0/46 in P0 and from 12/12 to 0/12 in P1, while both views remain at 6/34 in P2. P1's relation tree still alarms on 2/34 training matched-normal positions; its held-out 0/12 therefore does not imply absence of normal alarms throughout development. Main outputs have U=FAILED=0. Each dual-endpoint tree nevertheless uses partially missing inputs at 33/951 saved positions, so binary outputs do not establish complete measurement availability. T04 separates all training, development-holdout and historical MTC roles, retaining 144 and 117 historical normal groups. Previously exposed batches and recipe/environment differences limit generalization claims.

**保存来源。** 与F06a相同，另由`summary.csv`提取`P1/V_BOTH_REL/training/b2b42/NORMAL`和各角色`all`行的输入完整性；不把`all`与其细分身份重复累加。

## F07a：资源增量的家族检出与接入状态

**中文读图结论。** 原1005位置设计包含744开发位置（718正常＋26修改）和261历史正常；主图只报开发26次修改。八家族分母依次2、2、5、5、3、3、3、3。S0、S0+M、S0+B、S0+W检出分别13/26、19/26、16/26、19/26；S0仍遗漏语言修改和Browser资源修改。M/W补充6次Browser资源检出，B补充其中资源16/48的3次。三个配置在所画家族上的N/T/F/U/FAILED均相同，修改U/FAILED均0，按共同计数压缩图面，明细保留三配置。

**接入身份。** 只有S0是Retained；S0+M/B/W都是Diagnostic — rejected，不能把19/26写成已接受方法成绩。三批小实验正常共88条（12＋34＋42），这四组合、三个配置均为T/F/U/FAILED＝0/88/0/0；其零报警不能覆盖F07b的MTC代价。八家族宏平均分别50%、75%、62.5%、75%，在T04另列，与微平均13/26等分开。

**能支持。** 保存的诊断组合在指定Browser资源家族有额外信号；完整接入选择已经执行并留下负面结果。**不能支持。** 不代表这些增量已通过正常约束，也不能与App主实验105/126直接比较升降。未通过只限当前冻结基线和候选空间，不证明所有资源联合方法均不可能。

**English caption.** Family-specific detection and saved admission status in the original 1,005-position resource-extension design. Development contains 744 positions (718 normal and 26 modified); the other 261 positions are historical normal evaluation. The eight displayed modification families have N=2,2,5,5,3,3,3,3. The retained S0 detects 13/26, whereas diagnostic S0+M, S0+B and S0+W detect 19/26, 16/26 and 19/26, respectively. All three extensions were rejected by the saved admission checks. Family N/T/F/U/FAILED counts agree across the three configurations and are compressed here without tripling denominators. All modification outputs are defined and none fail. The 88 small-experiment normal positions produce 0 alarms and no unknowns or failures for these four combinations; read with the MTC costs in F07b. Macro-family detection (50%, 75%, 62.5%, 75%) is reported separately from these micro counts in T04. Local detection gains do not establish an accepted resource-augmented method.

**保存来源。** [families.csv](../../../deliverables/app_resource_constrained_extension_v1/results/summary/families.csv)逐家族结果与[candidate_checks.json](../../../deliverables/app_resource_constrained_extension_v1/results/candidate_checks.json)交叉核对；`feasible/selected/reasons`沿用原结果，未重新判定或选择。

## F07b：MTC正常侧的资源接入代价

**中文读图结论。** 12条分别对应四组合×三配置，分母始终为MTC discovery630正常位置。S0的明确输出为567/630（90.00%），加M/B/W均为560/630（88.89%）。01／02配置四组合报警依次6、8、6、46；03依次0、2、0、40。S0各63个U，三个增量各70个U，FAILED均0。90%参考线表示原开发要求的T＋F边界，不是允许90%误报，也不是普适部署标准；报警预算单独为31条。

**保存的拒绝原因。** M/B均为`MODEL_DEFINED_COVERAGE:mtc_discovery`；W还包含`NORMAL_ALARM_BUDGET:mtc_discovery`和`CANDIDATE_COVERAGE:W`。这些主图单增量没有容量拒绝。全部八集合×三配置仍有原24行：01／02的两增量集合MW、MB、WB及三增量MWB另有`RULE_BUDGET`和`COMPLEXITY_BUDGET`；03仅MWB另有这两项。配置01／02的S0为7规则／复杂度14，03为6／12，不把三配置称为容量相同。

**正常分组与未知来源。** 开发718正常的648/718＝90.25%不能替代MTC630的560/630判定。历史144与117在T04逐配置分开；同模型261辅助合计的S0报警为2／2／0、未知各17，S0+M报警3／3／1、未知各19，S0+B报警2／2／0、未知各19，S0+W报警24／24／22、未知各19。新增7条训练未知、2条历史未知及M的3条正常反例沿用[既有缺测说明](../../../deliverables/app_browser_evidence_consolidation_v1/REPORT.md)：前者是已保存不可用Browser内存报告，后者是有效正常超界，不能相互替换。另附[3条M正常反例保存状态](data/T04_resource_normal_counterexamples.csv)，分别为2条discovery与1条reserved；只保留脱敏案例名、配置状态及保存汇总中的定位，不复制原成员关联。本轮不重新读取原始记录或补U为F。

**能支持。** 加入资源条件虽然提高局部检出，但在原要求下明确输出不足，W另有正常报警及候选覆盖代价，所以实际保留S0。**不能支持。** 不能用小实验正常零报警或开发合计覆盖替代分来源约束，不能省略03的不同报警数，也不能把历史评价包装成独立阳性泛化证据。

**English caption.** Saved output composition on 630 MTC discovery normal positions for four combinations and three configurations. Bars retain the true proportions of alarms (T), non-alarms (F), unknowns (U), and failures. S0 has 567/630 defined outputs (90.00%); each diagnostic extension has 560/630 (88.89%). Alarm counts for S0, S0+M, S0+B and S0+W are 6/8/6/46 in configurations 01 and 02, and 0/2/0/40 in configuration 03. Unknown counts are 63 for S0 and 70 for each extension; failures are zero. The 90% line denotes the original T+F requirement, independently of the 31-alarm budget. M/B fail joint defined-output coverage; W additionally fails the normal-alarm budget and its candidate-coverage requirement. Rejection reasons are retained from the original checks. The 718-normal development aggregate cannot replace the 630-normal MTC requirement. T04 preserves all 24 candidate checks, capacity differences, and the separate historical 144/117 groups. Seven newly unknown development positions and two historical positions retain their archived unavailable measurements; three valid M normal counterexamples remain normal alarms. No condition was re-evaluated or reselected for this figure.

**保存来源。** [candidate_checks.json](../../../deliverables/app_resource_constrained_extension_v1/results/candidate_checks.json)、[candidate_checks.csv](../../../deliverables/app_resource_constrained_extension_v1/results/summary/candidate_checks.csv)、原已保存组合及[统一分配置MTC表](../../../deliverables/app_browser_evidence_consolidation_v1/tables.json)。

## F08：正常Browser语言偏好与脚本修改案例

**中文读图结论。** 本图保留7个真实位置：旧先导Browser语言修改3次、匹配批次正常Browser语言偏好2次、匹配批次Browser语言修改2次。它们展示的App首选语言均为en-us、Browser首选语言均为fr-fr，固定C2均T；正常偏好Browser列表长3，脚本修改长1。P0关系树对两条正常偏好为F、五条脚本修改为T；P1/P2关系树对七条均T，包含对两条正常偏好的误报。这里只展示实际列表长度，没有据长度编造列表成员。

| 案例来源 | 数量 | P0角色 | P1角色 | P2角色 |
|---|---:|---|---|---|
| 旧先导修改 | 3 | 训练内 | 整批留出开发 | 训练内 |
| 匹配正常偏好 | 2 | 训练内 | 训练内 | 整批留出开发 |
| 匹配修改 | 2 | 训练内 | 训练内 | 整批留出开发 |

**能支持。** 当前C2使用的首选标签差异同时出现在正常偏好与修改中，不能单靠该差异判断意图。已保存[P0关系树分支](../../../deliverables/cross_endpoint_four_view_comparison_v1/results/P0_V_BOTH_REL.txt)在C1非T且C2为T的分支使用Browser列表长度≤2.5；这解释了当前长度1／3配方如何被P0区分。**不能支持。** 不能说全部244项输入相同、列表长1就是攻击规律，或模型理解了恶意意图。图不是攻击成功率，不把7位置×3树输出合计成21个测试样本；P0是训练内，P1/P2包含不同训练／留出角色。

**English caption.** Seven saved Browser-language cases: three pilot script modifications, two matched normal preference changes, and two matched script modifications. All show App preferred language en-us, Browser preferred language fr-fr, and a triggering fixed C2 mismatch check. Browser list length is 3 for the two normal preference cases and 1 for the five script cases. The P0 relation tree outputs F for normal preferences and T for scripts; P1 and P2 output T for all seven, including the normal cases. P0 includes both batches in training; P1 trains on the matched batch and holds out the pilot, while P2 does the reverse. The archived P0 tree uses a Browser list-length threshold of 2.5 within its language-relation branch. This is evidence of dependence on the observed recipes, not a universal attack rule or proof of intent recognition. Only saved list lengths are shown; full raw inputs are not claimed identical. The seven positions are not 21 independent tests across three trees.

**保存来源。** 完整读取[fig04_preference_recipe.csv](../../../deliverables/prepaper_evidence_closeout_v1/figures/fig04_preference_recipe.csv)七行并保留原行引用；必要字段对照它引用的保存`features/predictions`。模型输出是报警／不报警状态，不是实际受攻击概率。
