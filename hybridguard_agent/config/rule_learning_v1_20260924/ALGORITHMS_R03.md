# R03 实现说明与后续运行入口

本文件是 R03 实现说明，不是 R01 合同修订。八份 R01 JSON、候选台账、划分和测量定义保持原样，协议 digest 为 `4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`，正式绑定见 `R01_protocol/PROTOCOL_BINDING.json`。R03 源码位于 `hybridguard_agent/research/rule_learning/`。本步只运行程序构造的合成夹具。

## 1. 固定候选与训练统计

核心视图先按 `SRC-OuHE` 的允许来源筛原始 CAT 别名，再用 R01 的偏差方向规范化、检查每行的值/可用性/原因/测量域，最后形成规范原子。已合并的联合来源矩阵不能替代其他来源条件。规范原子保留允许别名、原始来源、全登记等价关系、字段依赖和规范代表；别名数不增加支持数。共同测量语义不会因为删除一个来源而被删除。

所有合格原子生成正、反两种文字；U 的否定仍为 U。OR 只使用单文字子句。DNF2 枚举所有单文字及允许的双文字子句，不允许同原子、同家族 AND。先检查 4,096 子句上限，再计算标签支持；超限整分支 NOT_RUN，不按标签排名截取。

支持只使用完整的本折 train 批次。同一 `(bundle_id, triplet_id)` 的 pre/attack/post 都明确为 T 或 F，才构成一个可用三态；其中 attack 为 T 才计一次真攻击三态支持。每个文字及每个子句分别满足：至少 3 个可用三态、2 个真攻击三态、1 个 bundle、1 个环境。保存配置、环境、bundle、三态和各 phase 的 T/F/U/FAILED 分母。两个来源别名或两个历史方法不增加样本数。

选中集合不允许同一原子同时出现正、反方向，不允许重复或被包含的子句；每个家族至多出现在 2 个子句。最多 6 子句、12 文字、12 不同原子；OR 复杂度至多 12，DNF2 至多 18。复杂度为子句数加文字出现次数。

## 2. 目标、预算与三值覆盖

各训练配置等权，配置内各已表示环境等权，配置×环境内的准入攻击阶段等权。最大化这个 MacroTPR 减去 `0.005 × 复杂度`。clean 报警按整个集合的报警并集计数，同一阶段触发多子句仍计 1 次。预算为 `floor(alpha × N_train_clean)`，固定 OP00/OP05/OP10 的 alpha 为 0/0.05/0.10；不从测试数据选择操作点。

每个 attack/clean_pre/clean_post 层的训练决策覆盖至少 0.8。三值 OR 在有 T 时为 T，全 F 才为 F，其余 U；AND 在有 F 时为 F，全 T 才为 T，其余 U。空模型为 EMPTY_MODEL，不作为全 F 分类器。任一选中原子执行失败使该行 FAILED，不能被另一个 T 或 F 短路隐藏。含失败训练单元的子句不满足零执行失败约束。

并列顺序：更高目标、更高 MacroTPR、更少 clean 报警、更高最小分层覆盖、更低复杂度、按字典序排列的带极性子句 ID。文字内部按 atom_id 后 polarity 字符串的字典序排列。原始目录的 T 与规范偏差的 T 不可混用。

## 3. GREEDY_OR

从空集开始，最多增加 6 次。在支持、集合 clean 预算和复杂度允许时选择严格正目标增益最大的下一规则。覆盖不达标的中间集合可以继续扩展，但只保留覆盖也可行的已访问模型。没有正增益、达到 6 次或 60 秒停止。

对最佳已访问可行集合，按字典序只做一次删除遍历；仅在全部约束仍满足且目标不降低时删除。计时包括候选构造、支持、选择和剪枝；到时有可行模型则报告 TIME_LIMIT_FEASIBLE，没有则 FAILED_FIT。正常停止但没有可行访问模型时保留 EMPTY_MODEL，并明确不构成不可行性证明。

## 4. 有限 IP OR / DNF2

使用本地开源 HiGHS 1.12.0（Python highspy，NumPy 2.3.5）。单线程，seed=20260924，relative/absolute MIP gap target=0，整数可行性容差 `1e-9`，每次拟合总上限 120 秒；所有并列细化共用这个截止时间。求解器缺失明确 NOT_RUN_SOLVER_UNAVAILABLE，不切换算法或付费求解器。

对每个候选子句设置选择变量 `z_j`。每行设置 `a_i`=至少一个选中子句为 T，`u_i`=至少一个选中子句为 U，`d_i`=可作明确决策。用 OR 的上下界精确约束 a/u，再以 `d >= a`、`d >= 1-u`、`d <= a+1-u` 得到 T/F 决策覆盖；要求至少一个选中子句，空模型单独处理。全 F 的集合可决策，有 T 的集合即使含 U 仍可决策。clean 预算约束为 `sum_clean a_i <= floor(alpha*N_clean)`。

目标权重以训练分母的最小公倍数缩放为整数，不使用微小 epsilon 混合并列目标。依次求解并固定主目标、MacroTPR、clean 报警、最小覆盖、复杂度，再按候选字典序固定选择位。每个阶段都保存状态；字典序细化超时不称完整并列最优。过大的整数缩放明确 NOT_RUN，不冒称精确数值求解。

每个 incumbent 都再由独立的三值集合计算验证全部约束。日志记录求解器版本、状态、主目标 best bound/gap、主目标是否证明最优、并列细化是否完成和时间。只有证实有限支持池不可行才报告 NO_FEASIBLE_MODEL；超时无 incumbent 或求解异常为 FAILED_FIT。不同来源/可用性不能借用旧模型的可行性。

这两个算法是**固定有限候选 MILP**，没有 restricted master 或 pricing，也没有列生成。与 [Dash 等会议论文 §2–3](https://proceedings.neurips.cc/paper_files/paper/2018/file/743394beff4b1282ba735e5e3723ed74-Paper.pdf) 的 Hamming 目标及列生成流程不同，本实现使用项目 R01 的报警并集、clean 预算与三值覆盖。[HiGHS Python 接口](https://ergo-code.github.io/HiGHS/dev/interfaces/python/) 用于核对 API；执行版本以实际环境记录为准。

## 5. 模型、解释、基线和指标

模型保存算法、状态、实际 train ID、协议/折/输入来源、允许来源和别名、极性、子句、字段依赖、冻结数值转换器、求解状态和复杂度。保存拒绝覆盖既有文件；加载检查内容 ID 和复杂度；冻结对象内容被更改后拒绝推理。合成模型绑定合成 recipe，原 R01 真实 input manifest 仅保留为协议来源，不冒充合成输入。

推理只接受当前样本特征和匹配的视图 ID，不接受标签、phase、tool、config、路径或三态侧表。解释列出选中原子的状态/来源/方向以及每个子句的真值，不能把风险提示改称意图或授权证明。

HISTORICAL_SEVEN 适配匹配 ID、历史方法/输入/版本合同的已保存 final 结果；实际输入一致性证明由后续冻结 runner 提供。历史 family 覆盖与 R01 原子覆盖分列。DIRECT_CORE_OR 只对规范偏差正向 OR、不做训练支持筛选，并按 R01 免除学习模型子句上限、报告实际复杂度。常量 NO_ALERT/ABSTAIN 显式命名。

单层对照先限制该表面的字段/元数据，再在本折 train 上拟合数值 0.25/0.5/0.75 线性分位点，去重并冻结 LE 转换器，之后才生成布尔文字。数值无训练可用值时不生成阈值；保留 U/FAILED/NOT_REQUESTED。固定目录条件保留目录方向，控制编码来源为 PROJECT_CONTROL_NOT_E_Ou_H_C。使用同一 GREEDY_OR 目标、支持和预算。

指标以 expected IDs 为分母入口，缺失预测补为 FAILED 计数；描述性真值不进入 TP/FP 等监督计数。保存 TPR、clean/pre/post 报警率、决定条件下 clean 报警率、精确 FTF、条件恢复、弃判/失败、决策/原子/子句覆盖、分组 MacroTPR，以及不可识别范围。0 分母保存 null 和状态。不同模型/折/track 不隐式混合；R04/R05 还需实现显式的 expected-unit OOF 汇总器。

## 6. 拟合授权与 R04 资源

R03 的公共合成入口 `access.synthetic_fixture(name)` 只构造登记的 toy recipe，不接收调用者提供的数据或 `synthetic=True`。选择器和新单层入口要求发放的能力对象及完整原 train 内容；测试、描述侧、改 ID、伪造旧 FoldData 或修改能力内数据都不能通过。

R02 的旧 fixture API 保留用于历史兼容性；它的布尔 synthetic 标志及 ID 前缀**不构成 R03 授权**。`R02_REAL_DATA_FIT_NOT_AUTHORIZED` 是阶段权限拒绝，R03 不把它转成求解失败。这里是受信任代码中的工作流边界，不声称防御任意 Python 反射或篡改源码。

后续入口为 `FormalFitRequest` / `open_formal_fit`，声明授权记录、资源冻结、作业条目、协议、折、方法、操作点、来源、输入视图和 train 成员。R03 中此入口始终关闭；传入 R05 字符串或一个 freeze 文件不会自动获得真实拟合能力。

R04 还需绑定：八份合同、R02 原始别名单元及血缘/侧表/划分，R03 源码和夹具，Python/HiGHS/NumPy 与平台，单层字段/编码器和来源投影，历史七条输入/版本证明，预计 fit/model/prediction 单元，全局 200 fits/21,600 秒预算调度和优先级，以及模型冻结先于测试侧读取的运行器。独立快照、空 cwd 运行和 OOF 汇总属于 R04/R05 的后续工作。本文件及临时 venv 不等于完成 R04 冻结或授权 R05。
