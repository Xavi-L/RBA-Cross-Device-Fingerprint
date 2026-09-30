# 原始观测接入后的 R_KEEP 重训准备方案

状态：`PREPARATION_ONLY_NOT_AUTHORIZED_TO_TRAIN`。本文件登记下一次实验应遵守的方案和启动条件，不构成已经完成的训练协议登记；本轮不调用 fit、模型 predict、训练编码器或选择器，不新采集，不访问独立确认材料，不改历史协议和结果。后续用户授权训练后，才把满足启动条件的确定成员、代码版本、预算及任务清单冻结为新的执行合同。

**准备后的可行性结论：当前四折计划无法让新版 webdriver 条件进入合法最终模型。** 保存状态与原三值 OR/80%分阶段覆盖/OP05预算的独立必要条件证明见 `COVERAGE_FEASIBILITY.md` 和 `COVERAGE_FEASIBILITY.json`。后三折的数量支持已补齐，但旧 clean 的 U 使任何含该条件的 OR 都违反覆盖或报警约束。因此下列180条、16fit安排仅保留为未授权方案；它不能自动升级为“可以检验新版 webdriver 入选增益”的执行计划。数据准备通过与该研究目标被阻塞必须同时报告。

## 1. 已核实的比较对象

目标是在同一批准入数据、同一分割、同一学习程序上比较两个候选池：

| 组别 | 候选池 | 选择程序 |
| --- | --- | --- |
| `BASE` | 原 W0，保留旧 webdriver EQ:True 和完整旧语言长度家族 | 同池 GREEDY 初始化，再执行原 R_KEEP_V1 |
| `LANG_ADD_WD_REPLACE` | 保留旧语言长度家族，增加语言首项关系；删除旧 webdriver EQ:True，增加新版状态条件 | 同池 GREEDY 初始化，再执行原 R_KEEP_V1 |

不强制两项新条件入选，不创造“语言 AND webdriver”新谓词，不把原始观测模式或采集器版本本身作为攻击特征。语言新旧表达同属 `language_preferences`，webdriver 属于 `automation_flag`，不增加虚假的独立信号组。

已保存的历史比较确实为 BASE **45/54**、组合 **42/54**，均为原三折 LOEO；clean 均为 0/108，决策覆盖均为 162/162。组合少检出的三个位置都是 env-003 的 webdriver-only attack。组合结果与单独 WD_REPLACE 的全部 162 条决策相同。它们不是独立确认成绩，也不是 LOCO 或全开发集重代入成绩。

原历史样本中，新 webdriver 候选为 **18T、144U**。旧 strict-true 投影只能在旧值为 true 时支持真值；旧 false 不能证明原始 API 存在且返回 boolean false。三个训练折的完整 webdriver 可用 triplet 均为 0，clean_pre/post 均为 U；其中 attack 仍有 T，不能写成“完全没有攻击信号”。第三折最终五条规则，仍有容量，损失不能归因于六条容量已满。

可复核来源：`../rule_semantics_combination/REPORT.md`、`CONTRACT.json`、`SUMMARY.json`，以及 `../rule_semantics_rkeep_retraining/REPORT.md`。原选择逻辑见 `hybridguard_agent/research/rule_semantics_combination.py`、`rule_semantics_rkeep_retraining.py` 和 `rule_learning_v2/retention.py`。

## 2. 三类输入必须分开

| 输入集合 | 数量与含义 | 默认用途 |
| --- | --- | --- |
| H：历史监督材料 | 162 阶段，54 个已准入攻击 triplet；54 attack、54 clean_pre、54 clean_post；18 bundles、14 configs、3 环境关联组 | 保留原准入、成员、原始候选缓存和 legacy 模式；作为已暴露的历史开发基准 |
| N：新版单项干预三态 | 18 阶段，webdriver-only 与 language-only 各 3 个 triplet；6 active、12 pre/post | 先做独立事实准入与适配检查；合格后可以成为开发增量监督材料，不能自动成为确认集 |
| D：新版补充控制 | smoke 1、无攻击时间控制 9、仅调试连接控制 3，共 13 阶段 | 采集链路、字段变化与背景响应描述；默认不进入监督 fit 或 OP05 clean 分母 |

所以最新 31 条是 6 个干预 active 和 25 个非 active 采集位置，并不等于 6 个已经准入的正标签加 25 个历史合同意义的 clean 标签。N 中的 pre/post 只有通过对应干预撤销、会话及采集证据准入后才能取得 0 标签；D 中的 control_mid 不能改名为 attack 以凑三态，也不能复制成 pre/post 来凑训练支持。31 条都可用于无标签的输入适配核对。

H 的来源入口仅为原组合合同列出的 162 个 sample_id。原 `R04_freeze_r1/DATA_INDEX.json` 有 262 条索引，不能因读取方便把另外 100 条描述性或低证据材料纳入训练。

N 的事实标签只表示两项声明干预在规定采集表面的施加/撤销状态，不能表示“所有行为恶意/良性”。使用工具执行记录、配置、原始包、接收回执及 pre/post 恢复证据完成事实登记；不能根据待评估候选是否为 T 或模型是否报警来决定是否准入。保存原计划的失败或被排除位置和理由，不能因不利响应而静默删样本。

准备产物可以登记这些证据支持的 proposed 标签并生成 prospective 分割，但当前 `fit_permission` 仍应为 `DENIED_PREPARATION_ONLY`。提议标签与当前训练授权是不同字段，不能因为分割已生成就开始训练。

## 3. 观察模式与数据适配合同

1. H 使用现有 `legacy_projection_v1` 结果，18T/144U 原样保留，不重写缓存，不用本机新 false 回填历史 false，也不从新工具日志推测旧采集时的 API 状态。
2. N/D 仅从原始包 `canonical_received_payload.collection_observations.webdriver` 读取新版观察，不以展平旧 bool 替代。显式映射至新候选所需的 observation 结构，并保留 schema、observer revision、realm、读取状态、API 存在性、值类型和 boolean 值。
3. realm 自述不是已验证来源。由外部包/回执/session/runtime_context 对应及采集身份核对建立 `SourceBinding`；重复、错 session、错 realm、字段矛盾、revision 不符必须拒绝或保留明确失败。缺失、非布尔、读取错误按既有候选合同保留 U，不能默认为 false。
4. 新候选缓存必须保留逐条模式和来源；同一候选 ID 跨 legacy/raw 的逻辑定义不变，但可用性不同。报告两种模式的 T/F/U/FAILED、完整 triplet 及支持计数，不能把 raw 的高可用性泛化到旧数据。
5. 正式重训不仅需要两项新候选，还需要 N 中完整 W0 输入投影。每个原 W0 原子所需源字段、状态与转换必须按冻结定义接入；未支持的输入保留 U/FAILED，不补零，不借历史同设备记录填值。原始数字输入只在本折 train 拟合旧分位数编码器。
6. 新适配器检查不调用训练或模型预测。人工边界至少覆盖旧 false 为 U、原始 false 为 F、原始 true 为 T、合法缺失/读取异常为 U、来源绑定不符被拒绝、原始数据不被修改及新旧模式显式区分。

## 4. 环境分组与关联闭包

原环境组为 env-001 27 阶段、env-002 18 阶段、env-003 117 阶段；三折训练/留出分别为 135/27、144/18、45/117。原分组依据 install/stable-key/alias/run-capture 的传递关联，不是简单按 Android API 版本分组；同 API、model、adb serial 或暂存端点本身不构成身份连接。

本机 31 条来自同一个全新 AVD userdata、同一安装、Android API 36、WebView 134.0.6998.135、App code 12。N 和 D 必须始终同侧；不能按 session、轮次、工具或干预类型拆成多个环境。新的环境关联组可在核对与 H 无 install/stable-key/alias/run-capture 连接后登记，登记名 `codex-local-api36-1-raw-v1`；这是来源关联组，不是已验证独立物理设备或新 API 域。

若发现与历史 env-003 的身份关联，必须合并相关组、重新生成并冻结分割，不能为维持四折强行当作第四环境。组数变化是协议修订，下面的四折预算和分母不能继续沿用。

机器可读分组/配置核对登记见 `GROUP_CONFIG_REVIEW.json`，状态为 `SUPPORTED_FOR_PROPOSED_DEVELOPMENT_SPLIT`。本轮已核对的实际身份为新 install `3bf8a19e-d4e5-445e-bf3e-d791618e8a87`、manifest `codex-local-api36-1-raw-v1`、AVD `Codex_Webdriver_Raw_API36_1`。在历史 `01_admission/environment_group_registry.json` 和 `R01_protocol/GROUP_GENERATION.json` 中没有这三个键的显式关联；历史 env-003 install 为 `0492da06-a60e-4b63-8a36-c59bb6078953`。两份历史边界攻击的 `paired_triplet_run.json` 为 `sdk_gphone64_x86_64/emu64xa`，新原始包及 `avd_config.ini` 为 `sdk_gphone64_arm64/emu64a`、arm64-v8a，`environment.json` 登记专用全新 userdata。当前证据支持新的安装来源关联组，未发现应与历史组合并的显式边；这不证明共享系统组件、采集机制等相关因素消失，也不构成独立物理设备核验。

新旧配置 ID 不凭工具名或相同被改字段自动合并。只有执行实现、有效参数和干预语义均有证据等价时，才在训练前冻结映射；否则保留新版两个独立配置 ID，并明确层级 macro 分母发生变化。机制 ID 不从配置名称推定。

本次两项配置已有实际可核对的对应，可保留原 config_id：新版三个 webdriver 日志均为 `cdp_webdriver_only_v1` / `w9-rule-boundary-cdp-webdriver-only-v1`、单字段 webdriver、注入 true，与历史 `20260823_api36_rule_boundary_cdp_webdriver_only_v1/paired_triplet_run.json` 的 `tool` 一致；新版三个语言日志均为 `stealth_languages_only_v1` / `w9-stealth-boundary-languages-only-v1`、单字段 languages、`[fr-FR,fr]`，与历史 `20260824_api36_stealth_languages_only_v1/paired_triplet_run.json` 的唯一 `navigator.languages` evasion 及参数一致，stealth 包版本均为2.11.2。新旧 App、WebView、宿主及 CPU 版本差异放在来源 sidecar，不删除、不当作完全相同运行环境；配置数因此维持14，两个已有配置新增一个来源环境。旧参数核对只读既有攻击资料，没有改动攻击侧仓库。

## 5. 推荐的开发比较：180 条、四环境整组留出

这是**有条件的准备方案**：仅当 N 六个 triplet 都通过事实准入、W0 适配和环境关联核对时，建立 H162 + N18 的新开发快照。D13 独立存放。H 的历史快照和 45/54、42/54 原结果保持不动。

| 留出组 | 训练阶段 | 留出阶段 | 留出 attack / pre / post | OP05 训练 clean 预算 |
| --- | ---: | ---: | ---: | ---: |
| env-001 | 153 | 27 | 9 / 9 / 9 | floor(102×0.05)=5 |
| env-002 | 162 | 18 | 6 / 6 / 6 | floor(108×0.05)=5 |
| env-003 | 63 | 117 | 39 / 39 / 39 | floor(42×0.05)=2 |
| codex-local-api36-1-raw-v1 | 162 | 18 | 6 / 6 / 6 | floor(108×0.05)=5 |

两个候选池共用同一份逐 ID 成员清单，每个监督阶段恰好留出一次，每个 bundle/triplet/安装关联整体同侧。学习程序的 alpha=0.05 不变；因为训练 clean 分母增长，整数预算随固定公式变化，这不是维持旧预算数值的实验。该变化必须在结果中披露。

关键反例预先保留：当新增 raw 环境被整组留出时，训练数据只有 H162，新 webdriver 仍没有完整可用 triplet。这一折不会因新增采集而自动恢复支持。另三折有 N 的完整观察，可能满足数量支持，但是否入选仍取决于同池初始化、收益和其他约束。不能为了让新规则在第四折可用而把部分同环境轮次留在 train。

结果必须分别列出 H162 和 N18 的留出成绩，再列整个新180分母；不能把新60个 attack 上的比例直接当作对旧54个 attack 的提升。对 H54 attack 的配对变化可与历史已保存结果描述比较，但训练数据和部分整数预算已经变化，属于增量训练加候选语义的开发效果，不能仅归因于语义改动。两个新训练组之间的差异才是在本次相同训练材料下比较候选池设计的直接主比较。

这条路线最多回答“现有混合观察模式材料上的回顾性开发比较”。只有一个 raw 来源组且两种单项干预，不能据此估计原始模式跨环境泛化、正常 App 总体误报率或现实攻击总体检出率。跨环境 raw 验证需要额外独立来源组，使留出 raw 组时训练仍有经过准入的 raw 支持；不能靠当前三轮重复替代。

本方案只登记四折这一个主比较，不新增“原三折 H 留出、N 全部只加入 train”的开发增量副分析，也不因四折结果不理想而切换分割。

## 6. 冻结选择器、预算和执行顺序

沿用原 OP05、lambda=0.005、seed=20260924、六个单条件子句、复杂度12、每阶段最低决策覆盖0.8、每家族上限2、正负极性及 U 的三值逻辑。训练配置等权，配置内环境等权，配置/环境内 attack 阶段等权；不按全体行均匀加权替换原 macro。

每个文字/子句的支持仍要求本折 train 中至少 **3 个三态均有定义的 triplet、2 个 true attack triplet、1 个支持 bundle、1 个支持环境**。本次单环境的三轮可以满足开发算法的最低数量要求，这不构成独立性或泛化保证；不得降低门槛、将 D 改成训练 triplet、强制选入或读取留出 T 来补足 train 支持。

R_KEEP 从各自同池 GREEDY 初始化出发，仅添加正的加权信号覆盖增量 D，允许训练宏检出增量为0；保持初始攻击检出与整个 OR 的预算、支持、覆盖和结构约束。按新增宏检出、新增 D、较少 clean 报警、较低复杂度、稳定 clause ID 排序。不删除、交换初始化条件，不事后 sparse pruning。

新的 train 成员改变后，不能复用旧模型作“同池初始化”，也不能只给旧模型改名字；每组每折须新做 GREEDY（含 train-only 编码器），保存后供自己的 R_KEEP 使用。两组×四折×两阶段 = **16 次 fit**，其中 GREEDY 8、R_KEEP 8；只有 R_KEEP 留出预测，共 **360 个位置（2×180）**。GREEDY 留出预测为0。每fit算法上限60秒，worker上限沿用90秒；新阶段最多1440秒。不另做调参、全开发集模型、LOCO、备用对照或追加训练。

最近完整预算账为 `../rule_semantics_combination/EXECUTION.json`：累计177/200 fits、163.78602862533216/21600秒；本轮准备消耗0 fits、0模型预测。若正式只执行上述16次，预计累计193/200，剩余7，仍须在登记前再次核对最新账。不能把剩余7视为自动重试权限；失败保留后停止。四折与备选三折一起需要28次，会超过当前剩余23，因此不得同时默认执行。

执行顺序为：确定准入与观察模式 → 完整输入及来源检查 → 冻结环境/config关联和逐ID分割 → 冻结合同与预算 → 每折只加载 train → train-only编码器/支持/GREEDY → 保存并核对同池初始化 → R_KEEP → 模型保存重载冻结 → 打开本折留出特征并预测 → 关闭预测文件 → 加入留出标签计算指标。身份或可用性失败保留明确状态，失败后无自动重试、换分组或放宽语义。

## 7. 启动条件与当前能得到的结论

已经具备：历史基线与组合的保存结果及精确分割；新版31条原始包与回执；单项干预6轮执行/恢复证据；新的 raw 观察格式；明确的固定支持与选择算法；可在不训练的情况下完成输入适配和分母核对。

正式 fit 前必须具备：N 逐阶段事实/准入记录、完整 W0 和两项新候选输入、逐条来源绑定、无跨折关联的分割清单、固定配置映射、每fold可用性/支持预检、通过聚焦边界测试的新研究入口、确定16个任务及预算的执行合同，以及用户对正式训练的授权。任何一项仍缺，状态保持准备中；单独通过 raw adapter 不等于全部训练输入已经就绪。

此外，当前已证明的覆盖可行性障碍不能靠完成执行入口消除。下一步需先明确是否只是接受“新 webdriver 必不会入选”的原约束负结果比较，还是另行设计观察模式分流或其他新研究问题。后者会改变协议，必须显式登记；本轮不选择放宽阈值、把 U 当 F、修改 OR 语义或排除不利历史材料来获得预期结果。

本轮可交付并核对以上准备材料，随后停止在 fit 前。新条件在本机表现为预期字段变化，只证明该环境中的观测与适配链路；是否选入、能否补回3条、整体效果是否改善均为 **NOT_EVALUATED**。未来报告必须保留负结果、U/FAILED、空模型、规则变化、新增/丢失样本、按环境/配置/观察模式分层的分母和完整三态 F-T-F；不把没有进入模型的新条件称为已经带来提升。
