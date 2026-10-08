# 第一轮 App 论文图稿

本目录对应当前清单的F01、F02、F03a、F03b、F04及T01／T02／App部分T03，供导师选择正文和附录。稳定素材编号不等于最终论文图号。当前状态为**初稿已生成／待导师选择**，五张最终PNG及工作尺寸校样均已逐张查看；实际检查状态以[CHECK.json](CHECK.json)为准。

制图输入均为已保存结果。只读取、筛选、求和、换算比例和绘图；不采集、不拟合、不选规则、不执行模型或条件预测、不重新计时。没有访问私有原始指纹或外部模型服务，没有调用旧实验入口，也不改写`deliverables`内结果。第二、三轮未执行；本轮不自动提交或推送。

## 阅读入口

| ID | 内容 | 图像 | 绘图数据 |
|---|---|---|---|
| F01 | 14配置×6方法App检出 | [PNG](figures/F01.png) / [SVG](figures/F01.svg) | [CSV](data/F01.csv) |
| F02 | MTC历史正常输出组成，18条 | [PNG](figures/F02.png) / [SVG](figures/F02.svg) | [CSV](data/F02.csv) |
| F03a | 完整App方法的内存专项比较 | [PNG](figures/F03a.png) / [SVG](figures/F03a.svg) | [CSV](data/F03a.csv) |
| F03b | 固定R_REL与R_WEB8条件比较 | [PNG](figures/F03b.png) / [SVG](figures/F03b.svg) | [CSV](data/F03b.csv) |
| F04 | 正常系统换区与网页单独修改 | [PNG](figures/F04.png) / [SVG](figures/F04.svg) | [CSV](data/F04.csv) |

[CAPTIONS.md](CAPTIONS.md)逐图提供中文读图说明、能支持／不能支持的结论，以及英文论文图注。[FIGURES.json](FIGURES.json)保存源路径、摘要、筛选、合并、角色、分母、尺寸和产物清单。

配套表：[T01数据范围与用途](data/T01.csv)、[T02主结果](data/T02.csv)、[T03正常分组原计数及合计](data/T03.csv)、[F04全部正常30与修改6](data/F04_totals.csv)、[小树输入完整性](data/tree_input_integrity.csv)。T01中的原批次、子集和复用关系不构成可直接相加的总样本数。

## 方法与状态口径

| 顺序 | 原ID | 图内短名 | 中文解释 |
|---|---|---|---|
| 1 | APP_FULL | Full App | 当前App完整方法 |
| 2 | A_NO_MTC_CAP | No MTC alarm cap | 去MTC正常报警上限 |
| 3 | A_APP_WEB_ONLY | App Web only | 只看App网页 |
| 4 | A_NO_MEMORY_REL | No memory relation | 去系统—网页内存关系 |
| 5 | A_NO_TIMEZONE_REL | No timezone relation | 去系统—网页时区关系 |
| 6 | APP_TREE | Small App tree | 固定小容量App树 |

上述映射另存[methods.csv](data/methods.csv)；14种修改配置全名与短名见[configurations.csv](data/configurations.csv)，三个冻结配置全名与01／02／03映射见[folds.csv](data/folds.csv)。规则主阶段固定RETENTION，小树固定FITTED。Full不含跨端C1，App小树也不是语言／时区四视图树；未混入Browser模型、资源诊断组合或新Host几何条件。

T为报警，F为未报警，U为无法判断，FAILED为执行失败，EMPTY_MODEL为单独的空模型状态。明确输出数是T+F；F不是安全证明。零计数与无法判断分开保存；本轮所示EMPTY_MODEL均为0。

## 一次运行与仅检查保存图数据

在仓库根目录使用已有Matplotlib环境：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B paper/figures/round1_app/plot_round1.py
```

仅检查已保存的绘图CSV、分母和图清单，不重新渲染：

```sh
deliverables/prepaper_evidence_closeout_v1/.plot-runtime/bin/python -B paper/figures/round1_app/plot_round1.py --check-only
```

该入口只操作本轮产物；重复运行只更新本轮生成文件，遇到未经识别的已有成果会拒绝覆盖。可追加`--output /tmp/rba-round1-new`生成到新目录；新目录产物沿用本目录图注／README。`--check-only --output /tmp/rba-round1-new`只读该目录保存文件。源文件执行前后摘要、数值检查和视觉检查分开记录在CHECK.json。源数据有冲突时应报告具体行键／字段并保留已有产物，不自动挑选较好数字。当前数值来自CSV／JSON，Markdown报告仅用于解释材料角色、操作语义和边界。

## 主要读图结论与分母

F01六方法有效修改报警依次为105/126、108/126、96/126、96/126、105/126、72/126，受控正常均0/252。取消MTC报警上限多检出3/126，却在F02每配置的261/261历史正常上报警，不能仅凭主分数判为最佳。

F02只合并同一模型的development 144与reserved_validation 117，保留18个方法／配置输出。Full三个配置的报警为2/261、2/261、0/261，未知各14/261；去内存关系未知各1/261。MTC630训练约束部分在T03单列。小树二值输出不能说明缺失观测恢复，详见输入完整性表；全MTC的73/891未知候选计数不属于本图261子集分母。

F03a每配置的18次有效内存修改，Full、去MTC上限、去时区关系各18/18报警；Web-only、去内存关系、小树各0/18。六方法正常均0/48，无可观测变化均0/6。F03b使用同一批次的原固定条件，目标4／8／16各6次有效变化，R_REL为6/6、6/6、6/6，R_WEB8为0/6、0/6、6/6；两条件正常均0/48，目标2无变化另列。完整模型与固定条件的结果不能互相替换。

F04正常系统换区／网页单独修改，Full为0/6与6/6，Web-only和去时区关系均6/6与6/6；去MTC上限、去内存关系均0/6与6/6，小树为0/6与0/6。正常变化6是全部正常30的子集，不再相加。Full与去时区关系在旧主实验同为105/126，不否定这里的正常代价差别。

所有材料已有开发使用历史，不称新盲测。三个冻结配置重复评价同一材料，不增加独立样本，也不作为三次独立重复算置信区间或显著性。F03a／F04只在计数逐项相同时压缩展示，各配置完整CSV保留；相同汇总计数不等于已证明逐条状态相同。F03a与F03b共享72个内存位置；不能把两种分析叠加成144个样本。

## 检查与版面选择

数值检查覆盖CSV／JSON对应字段、六方法与14配置完整性、RETENTION／FITTED阶段、主表全部状态计数相加、MTC144+117且排除630、专项聚合层防重复、内存18/48/6与时区30含变化6、三配置独立保留、源定位与短名映射。当前独立数值交叉检查未发现上述源CSV／JSON计数冲突；统一`tables.json`的specialists仅保存ALL／ALL的126行，恰与主体相应子集一致，不是1332行全表缺失或数据冲突。

已完成440项来源与数值检查、338项保存产物检查；涉及的30个来源文件执行前后摘要一致。5张最终PNG均逐张查看，并查看按声明工作尺寸生成的96 dpi屏幕校样，未见裁剪、重叠或计数遮挡；这不是打印验收。字体最小8 pt，PNG为300 dpi。SVG通过矢量路径、无栅格图层和物理尺寸检查，未作SVG视觉验收。工作尺寸为F01 180×135 mm、F02 180×155 mm、F03a 180×86 mm、F03b 85×87 mm、F04 180×91 mm。最终采用的精确尺寸见FIGURES.json，不应直接缩小宽图来强塞单栏。

导师仍需决定：F01全文热图放正文还是附录；F03a和F03b哪一幅进入正文；F02／F04是否保留整幅宽图，以及最终论文图号与期刊版心。现阶段成果不称最终投稿图。

来源补充：旧内存汇总的正常依据子字段为0，与主计数48是不同字段；已有后续`MEMORY_NORMAL_REVIEW.json`确认48条正常、0条缺支持、两条件各F=48且历史输出未修改。本轮只读取其汇总佐证，保留旧字段；详见F03b图注与来源定位。
