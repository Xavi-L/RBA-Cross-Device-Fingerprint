# 四项核心实验的结论导向设计草稿

这四张中文图稿用于讨论论证结构，尚不是论文排版终稿。只读取已经保存的实验结果，未采集、训练、选择模型、预测或重新计时。正式F01/F02/F03/F04/F05a和论文模板均未改动。编号01–04仅对应本次讨论顺序。

**第一张已有合并版：[PNG](01_app_contribution_compact.png) / [可编辑SVG](01_app_contribution_compact.svg)。**按六种方法完整的N/T/F/U/FAILED/EMPTY_MODEL向量相等，将14类配置归纳成5行；相邻方法状态相等时继续横向合并，84个原始格压缩为12个数值块。格内统一显示每类9次中的检出数，配置数列保留1、1、2、8、2。行序为资源、屏幕、小树特定漏检、共同检出、共同漏检。总计按配置数还原为105、108、96、96、105、72 /126，未增加或删除样本。

完整组成员和状态映射保存在`01_compact_groups.json`，验证在`01_COMPACT_CHECK.json`。原14行稿保留作明细。只重建第一张合并版可执行：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build_first_compact.py
```

**第二张已确认采用纯表格，暂时收束：[PNG](02_reference_mechanisms_table.png) / [可编辑SVG](02_reference_mechanisms_table.svg)。**采用黑白表格与组间细分隔，4列、7行；每组左侧合并专项名和样本量，数字只表示检出数或误报数，免去重复分母。设备参照条件以*标识。所有条件（包括同网页视口关系）均保留在表内，结论解释放在正文或表注。移除了彩色块、结论卡片与连接箭头。第三张修改期间未重新生成或改动此表。

数据见`02_table_data.json`，核对见`02_TABLE_CHECK.json`。独立重建命令：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build_second_table.py
```

**第二张前一版（保留对照）：[PNG](02_reference_mechanisms_clear.png) / [可编辑SVG](02_reference_mechanisms_clear.svg)。**统一为内存、时区、屏幕三行，左列固定回答有效修改是否检出，右列固定回答正常记录是否误报。以“多发现12次修改”“均全部发现”“减少6次误报”为主文字，精确计数作为次要说明。该版混合图卡和表格的样式未被用户接受，现由上述纯表格候选替代。

各行仍是固定单条检查的对照。内存使用全部18次有效修改与48条正常，时区使用6次有效修改与30条正常，屏幕使用6次有效修改与66条正常；三个专项不混成总体分数。完整正常集合取代上一版主格只展示的6条正常变化子集，具体误报仍来自正常换区或布局扩大。同网页视口的全部漏检、内存6次无效果操作、Host新几何尚未接入整模的边界均保留在图内。数据与验证见`02_clear_data.json`、`02_CLEAR_CHECK.json`。本轮只重绘第二张，已接受的第一张合并版及第三、四张未改动。

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build_second_clear.py
```

| 图 | 读者最应看到的结论 | 视觉设计 | 与现有素材的关系 |
|---|---|---|---|
| 01 App整体与消融 | 检出差异集中在哪些修改，哪些修改仍全部漏检 | 所有14×6格保留实数；完整方法作参照，其余格只高亮相对差异；总数和关键行注释贴近对应位置 | F01及T02的新讨论版本；差值底色不是原F01的绝对检出率色阶 |
| 02 内存、时区、屏幕 | 内存补充检出；时区和屏幕容忍正常变化且保留所测修改检出 | 三组固定条件的场景对照表；把正常操作和有效修改明确分开，格内直接写“检出/误报” | 内存来自F03b；时区、屏幕来自专项保存汇总。与F03a/F04的完整模型比较身份不同 |
| 03 MTC正常约束 | 取消正常报警上限只多检出3次，却使历史正常记录全部报警 | 黑白三线对照表，保留/取消上限分别列出报警、未报、未知；计数相同的配置合并，报警数加粗 | F02聚焦两种方法的讨论版本；原六方法全量源表继续保留 |
| 04 双端扩展 | 新增5次检出均来自Browser时区，两端语言修改仍漏检 | 分组列头对照表：方法为行，App/独立Browser的时区/语言为列；增加条数行突出唯一有增益的家族 | F05a的新讨论版本；不包含资源扩展或四视图树 |

## 设计意图与限制

01以差值高亮降低相同结果的视觉重复。绿色只表示多检出，不表示更值得采用；多检出3次的正常代价在03展开。去时区主表分数不变的原因在02用正常换区反例解释。小树是固定候选表示与容量下的参考，不能代表所有机器学习方法。

02使用固定单条条件，回答机制问题。内存额外12次来自4与8的向上变化；16的6次两种条件均检出。正常设置变化不是攻击。屏幕保留旧同网页视口关系的漏检结果；新Host几何尚未进入完整App模型，不能用其0/66替换整模结果。屏幕正常布局6条是66条正常中的子集；时区正常换区6条是30条正常中的子集。

**03当前候选为黑白三线对照表：[PNG](03_normal_constraint_table.png) / [可编辑SVG](03_normal_constraint_table.svg)。**两组历史正常材料分别保留144/117分母，每组01/02的相同计数合并一行，03单独一行；保留/取消报警上限各有报警、未报、未知三列。取消上限的三个配置计数相同，因此在每组内跨两行合并。报警数使用粗体，使0/1与144/117的差别直接可读。合并只表示所列计数相同，不表示逐记录状态相同或新增独立样本。

独立脚本`build_third_table.py`只读取保存的`mtc.json`与`main.json`。数据见`03_table_data.json`、`03_table_data.csv`；核对见`03_TABLE_CHECK.json`。本轮只生成第三张纯表格，未重新生成第一、二、四张，也未改动正式论文图表。

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build_third_table.py
```

**03前一版方格图保留作讨论对照：[PNG](03_normal_constraint_units.png) / [可编辑SVG](03_normal_constraint_units.svg)。**每格表示一条正常记录，所有图块中的方格物理面积相同；144条排为12×12，117条排为13×9，没有补位空格。红色为报警、浅灰为未报、黄色斜线为未知，每块下方直接写出完整计数。保留上限的01/02配置计数相同，合并展示；03单列；取消上限的三个配置计数相同，合并展示。只合并所列汇总计数，不推断逐记录输出相同，方格位置也不表示记录对应关系。该版保留了单次报警的可见性，但版面效率不如当前表格；原堆叠条形稿也保留对照。

03强调正常报警上限的作用，不能表述成完全移除MTC数据。受控修改合计105/126→108/126与受控正常0/252在当前表下注明，不能与单个历史配置计算一一对应的收益代价。训练630另列在注记；144和117是历史评价材料，不是新的独立盲测。每个配置作用于同一批记录，不能合并分母。失败与空模型均0，未知未改成不报警。

前一版方格图的数据与检查分别保存在`03_units_data.json`、`03_units_data.csv`、`03_UNITS_CHECK.json`。独立重建命令：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build_third_units.py
```

**04当前候选为分组列头对照表：[PNG](04_cross_endpoint_table.png) / [可编辑SVG](04_cross_endpoint_table.svg)。**先小范围查阅WWW主会原文，再采用方法为行、端点为分组列头的表格结构：App与独立Browser各保留时区和语言，末两列为总检出与正常报警。两种方法为完整App和完整App+跨端时区C1；增加条数行明确Browser时区+5、其余家族0。仅发生变化的检出格与对应差值加粗，不将粗体解释为统计显著。

设计依据是[PromptMM，WWW 2024，表5](https://arxiv.org/pdf/2402.17188)的方法/消融行与分组列头，以及[IMF，WWW 2023，表4](https://arxiv.org/pdf/2303.10816)的信息源组合对照。[Beyond the Crawl，WWW 2025，作者稿表5](https://openreview.net/pdf/ed73a9f8081b03dd34273b0ca0cc23011ac0e283.pdf)也保留分类型计数与汇总。这些是具体可核对的参考，不构成WWW图表使用频率统计或统一格式要求；增加条数行是针对本数据的适配。完整定位、选择理由及英文图注见`04_DESIGN_REFERENCES.json`。

本表保留各家族实际修改数2/2/5/5，避免只展示2→7总量而掩盖未改善的语言家族。三个配置汇总计数相同，仅压缩展示，不声称成员级输出完全相同或增加独立样本。配对正常46=先导12+匹配34，不能替换成旧匹配批次的34。正常0/46与历史MTC未知14→17同时保留，不能外推普遍低误报与覆盖完整；本批14次修改和46条正常均有开发使用历史。历史261仅为同模型144+117的辅助合计，原分组保留在导出数据。

原点阵版`04_cross_endpoint_gain.png/.svg`保留作早期草稿。本轮只生成第四项新表，前三项和正式图表均未改动。数据见`04_table_data.json`、`04_table_data.csv`，验证见`04_TABLE_CHECK.json`。独立重建命令：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build_fourth_table.py
```

## 文件与复现

- 每图均有PNG与可编辑文本SVG；SVG显示中文需要Heiti TC或替代字体。
- `build.py`：仅使用标准库和Matplotlib读取保存汇总并绘制，无研究引擎调用。
- `plotted_data.json`：保留绘图与边界注记用到的原始汇总行；重叠层级不能相加为新样本。
- `SOURCES.json`：数据来源及CSV行数，原数据中的source_path/source_locator继续保留。
- `CHECK.json`：来源算术、配置压缩、画布文字边界与人工看图检查。

在仓库根目录执行：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python paper/figures/experiment_storyboards_20261016/build.py
```

四图为宽幅讨论稿。正式论文制作时应根据单栏/双栏宽度重排字号与注释，并将完整边界移至图注；不能直接缩小后宣称通过论文尺寸验收。本次没有编译全文或修改论文正文。
