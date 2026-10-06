# B3-A 运行前固定协议

模式 DEVELOPMENT_FOUR_VIEW_COMPARISON；参考2524fb7155313cfdfbe4180fc601622b3ec8379a。0新采集；不修改B2-C或正式准入。不搜索参数。旧105/126、378保持App历史身份。

准确原字段由 expanded_v2_field_catalog.csv 核对：App Native locale_timezone_layer 的 native_locale/native_timezone_id/native_timezone_offset_min；App与Browser Web navigator_layer 的language/languages、execution_layer的timezone_offset。前缀分别 app.android_native_data、app.web_data、browser.web_data。禁止将样本/会话/配对ID、批次、标签、phase/scenario、目标、路径、旧模型输出、型号、ABI、版本、采集时间与未来恢复输入树。

App Web与Browser完全同构：language用原limited_full_tag；languages仅首项limited_full_tag与原列表长度，空列表长度0有效、首项缺失（不伪造语言），列表须为字符串数组，首项不支持的标签保留缺失。Native locale与zone ID为原非空字符串类别，不新增规范化；Native rawOffset数值原义（不含DST），Web偏移UTC-local，单位/符号保持原样。有限数值0/-1有效，bool不是数值但不全局作缺失哨兵。来源status非observed或quality非observed_value优先缺失，所以runtime_error的0不是测量。

V_APP为上述App侧语言/时区7个派生字段；V_BROWSER为4字段；V_BOTH拼接11字段；V_BOTH_REL严格追加原C1/C2类别T/F/U。C3、D1/D2不入池。V_BOTH含原C1/C2所需全部操作数，允许小树隐式利用关系；两个双端视图只有追加关系列这一项区别。

所需端点结构/绑定失败=>FAILED；双端另外要求可信同配对；单端不依赖另端或配对错误。有效来源中字段缺测保留原因。所需原字段派生测量全部不可用=>U，不依赖缺失模式推断正常。关系T/F/U不算独立可用原测量，FAILED不能编码成F。部分缺测可以进入树，但缺测判定数与输入完整率单列。

类别按训练部分出现的类别独热编码，固定保留计算缺失类别__MISSING__，缺测原因不作为额外类别；评价未见类别全零并明确记入unknown_categories，不扩充词表。数值用训练有效值中位数作计算填补，所有数值列始终有缺失指示；整列无有效值用计算占位0并记录all_training_missing，不回写原观测。关系列使用固定T/F/U独立列（公式预定义值域，非评价学习）。同一方案所有原字段只fit一份共享变换，V_BOTH与V_BOTH_REL复用完全相同原字段列；单端词表/中位数也只由自身字段训练值决定。

树参数固定criterion=gini, splitter=best, max_depth=3, min_samples_leaf=2, random_state=20261006, class_weight=None，其他参数记录实际默认。不采用默认predict的平局规则，按classes_定位正类概率>=0.5报警。

权重：正类总1/2，均分训练实际出现的四种方向/家族再家族内均分；正常总1/2，均分训练实际出现的MTC/先导/匹配来源再来源内均分。不存在的家族不补。身份/来源/家族仅供分组权重，不进入树。无可靠身份的记录保持UNCONFIRMED，不参与有监督fit；输入失败/全无效训练位置保留但明确不进入fit，不静默替换样本。当前预定成员若出现这种缺口，记录实际fit成员与名义成员差异。

P0训练discovery630+pilot18+b2b42=690；P1训练630+42=672，完整pilot18留出；P2训练630+18=648，完整b2b42留出。每方案四视图一次拟合，共12次。三方案均分别报告历史MTC144/117，训练按来源拆开。P1/P2全组三阶段不拆，原42替换来源固定。两批均曾接触，称整批留出开发比较；P2无App干预训练家族，App方向另列为未见作用端/配置。不能把环境、ABI、版本差异唯一归因于版本。

树无受约束OR保证，按固定正常630/12/34及31/0/1预算、90%明确输出另作诊断，未达标不调阈值。树的二值输出覆盖不等于观测完整率提高。冻结App和B2-C951条输出单列既有方法参考，不冒充P1/P2留出成绩。

保存训练/评价成员、固定表示、权重、词表/中位数、全部参数、JSON树结构/规则、概率状态/路径及原始引用。记录实验/测试/工程fit、transform、predict调用。只重汇总独立于numpy/sklearn与适配器。15条B2-C新增未知仅复用已有交集和保存状态给原因表，不重审/修复全MTC。

现有项目及本机Python未发现scikit-learn，隔离安装1.7.2并记录全部实际版本；不升级旧环境。官方API依据：https://scikit-learn.org/1.7/modules/generated/sklearn.tree.DecisionTreeClassifier.html 。固定随机种子并不消除不同环境间差异，保存结构与版本作为本次复现依据。

完成12比较、必要测试及报告后停止，只提出最终消融/成本/图表安排，不执行。私有raw/票据仍本地，不提交推送。
