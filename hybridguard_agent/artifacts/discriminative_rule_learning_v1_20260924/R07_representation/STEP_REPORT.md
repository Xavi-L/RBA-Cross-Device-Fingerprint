# R07：冻结单层重训练与跨层表示比较

**R07_SINGLE_SURFACE_REFIT 主分支完成，等待外部验收。** 9 个正式作业一次执行，产出 3 个非空模型和 6 个合法空模型，486 条预期预测全部对账，无技术失败、超时、预算耗尽或自动重试。R05 比较只读取其原 3 个模型和 162 条已关闭预测。R06 主分支外部验收已独立登记；R06 父步骤仍为 PARTIALLY_COMPLETED，POSTFIT_DELETE 仍 NOT_RUN 且不作为 R07 前置。

## 版本、授权与运行

- 审查基线：`4a99e883c62994c1a5037b2bedc0da5205c69b7c`。
- 快照：`../R04_freeze_r1/`；实际启动检查通过 3,298 个资源，协议/配置/白名单/划分/源码/版本未改变。
- protocol digest：`4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4`。
- FREEZE_MANIFEST SHA-256：`bff86c2423283d9ecdf6402c2975a747707cd7d521a328561ef676cdcff2ddad`。
- RESOURCE_MANIFEST SHA-256：`7e2aa45c9cf78abc106cb61e3863c5d89f2491fe0b406b645cd48fad80bd0de0`。
- 快照外授权 `R07_APPROVAL.json` SHA-256：`fee973548d8971f310c8b538ebb16988ee12a9706fe436b69b8f13a8abd669c1`，绑定 9 个精确 jobs、train 成员和原真实账本；没有修改快照历史授权状态。
- Python 3.12.14、HiGHS/highspy 1.12.0、NumPy 2.3.5，macOS-15.7-arm64-arm-64bit；本轮算法为冻结 GREEDY_OR，不调用 IP 学习作为替代。
- 原 launcher/dispatcher `--stage R07 --suite complete` 从空 cwd 启动，新 worker 使用同一快照代码/依赖；实际路径见 RUNTIME_VALIDATION。
- UTC 2026-09-24T14:28:22.374750+00:00 至 2026-09-24T14:28:32.955324+00:00，wall 10.580544 秒；attempt=1、returncode=0。此后仅从保存产物导出和算术对账，没有新拟合、新阈值或新预测。

native84、app_web67、host26 × LOEO-v1 三折 × GREEDY_OR/OP05/SRC-111 的精确清单为 expected_fit_jobs、expected_model_units、expected_prediction_units。9 fit / 9 model / 486 prediction 同属 162 个监督阶段，每视图 attack/pre/post 各 54；视图数不增加独立样本数。100 个描述阶段、UNKNOWN 时间对照及未标注 MTC 不进入监督分母。

## 白名单、编码和隔离

R04-R1 单层白名单完整接入：Native 18目录+20固定控制+28数值输入，AppWeb 5+16+27，Host 5+17+7。Host目录精确为 CORE-002、NVW-005、OFFDER-BRIDGE-001、OFFDER-DEVCONFIG-001、P3-PROVIDER-PARSE；NVW-003/004未进入encoder或选择器。没有为了比较跨层而将单层缩成几条手选规则，也没有用R05/R06外层成绩改变候选。

| fold | 视图 | 原目录/固定/数值输入 | 编码后原子 | 登记/支持合格字面量 | 所选子句 | 复杂度 |
|---|---|---|---|---|---|---|
| LOEO-v1-01 | app_web67 | 5/16/27 | 49 | 98/68 | 6 | 12 |
| LOEO-v1-01 | host26 | 5/17/7 | 31 | 62/34 | 0 | 0 |
| LOEO-v1-01 | native84 | 18/20/28 | 73 | 146/82 | 0 | 0 |
| LOEO-v1-02 | app_web67 | 5/16/27 | 49 | 98/69 | 6 | 12 |
| LOEO-v1-02 | host26 | 5/17/7 | 31 | 62/34 | 0 | 0 |
| LOEO-v1-02 | native84 | 18/20/28 | 73 | 146/82 | 0 | 0 |
| LOEO-v1-03 | app_web67 | 5/16/27 | 56 | 112/74 | 1 | 2 |
| LOEO-v1-03 | host26 | 5/17/7 | 33 | 66/38 | 0 | 0 |
| LOEO-v1-03 | native84 | 18/20/28 | 76 | 152/87 | 0 | 0 |

9 套 encoder 保留全部 186 个逐折数值输入转换记录。分位点为 R01 固定的0.25/0.5/0.75，线性插值及重复阈值合并不变；只从本折train拟合，随后冻结在模型JSON中。固定目录原子使用原目录条件方向，控制条件使用自身T定义；不套用核心规范偏差的全局极性。

访问链逐作业核对：仅打开train特征/标签 → 精确白名单 → train编码/支持/选择 → 保存并加载含encoder的模型、形成冻结收据 → 打开outer_test特征 → 保存并关闭预测、对账 → 独立连接评价标签。各折训练数135/144/45，测试数27/18/117；train/outer的ID、bundle和环境组不交叉，与R05同折精确一致。最终预测表不含标签/phase/config，比较使用独立评价sidecar。

**冻结日志的限制：** `_derived` 创建新训练访问对象时重置 `operations` 列表，因此最终日志没有逐字段 numeric_thresholds 调用事件。不能将0条此类日志解释为没有阈值拟合，也不能补造逐调用收据。这里的train-only核验依据是实际train文件访问清单、被冻结的仅train能力容器与TrainQuantiles精确batch检查、encoder的fold/train_ids、模型字节冻结及首次outer读取时点；186条阈值来自保存encoder。没有在后处理重读数值或重算分位点。该记录粒度限制单独保留于ENCODER_ALLOWLIST_VALIDATION和ACCESS_ORDER_VALIDATION。

## 折外结果及代价

core 行为 R05 原主模型参照。NE=NOT_EVALUABLE/value=null。

| 视图 | 攻击检出 | pre报警 | post报警 | 精确FTF | 决策覆盖 | 弃判 | 失败 | 原子/子句覆盖 | 复杂度（折1/2/3） |
|---|---|---|---|---|---|---|---|---|---|
| native84 | 0/54 | 0/54 | 0/54 | 0/54 | 0/162 | 162/162 | 0/162 | 0/0 NE | 0/0/0 |
| app_web67 | 27/54 | 0/54 | 0/54 | 27/54 | 162/162 | 0/162 | 0/162 | 387/387 | 12/12/2 |
| host26 | 0/54 | 0/54 | 0/54 | 0/54 | 0/162 | 162/162 | 0/162 | 0/0 NE | 0/0/0 |
| core | 24/54 | 0/54 | 0/54 | 24/54 | 162/162 | 0/162 | 0/162 | 162/162 | 2/2/2 |

AppWeb 攻击检出27/54=50%，高于当前跨层24/54=44.44%，pre/post报警各0/54、弃判与失败0，决策覆盖均162/162。但AppWeb配置宏平均为5/14=35.71%，低于跨层6/14=42.86%；两者不是同一指标。AppWeb检出集中于5个配置，跨层覆盖6个配置；样本数较多的配置影响阶段微平均。

AppWeb两折有6子句/6字面量、复杂度12，达到冻结复杂度/添加上限；第三折1子句、复杂度2。跨层三折始终1子句、复杂度2。因此本轮AppWeb较高的阶段检出没有伴随clean报警或弃判增加，但伴随前两折复杂度增加；不能直接写成全面优于跨层。原子/子句覆盖分母387=27×6+18×6+117×1，非统一模型大小乘162。

Native/Host各三折均EMPTY_MODEL，162/162弃判、决策覆盖0。其0次clean动作报警不构成低误报证据，decided-clean为0/0 NE；已知空模型的原子/子句分母0、value=null。与无模型/大小未知时expected_denominator=null的合同不同。本轮没有模型缺失。

Native/Host不是空候选池：分别有82/82/87和34/34/38个支持合格字面量。保存的train统计显示，这些字面量单独的clean报警均超过相应4/4/1预算，见TRAIN_CANDIDATE_BUDGET_DIAGNOSTICS。贪心返回HEURISTIC_NO_FEASIBLE_MODEL_FOUND_EMPTY_MODEL、no_positive_objective_improvement；原求解状态infeasibility_proved=false保持不变，不冒充正式不可行证明。所有非空模型训练clean报警0、三阶段覆盖1.0，支持度/复杂度/集合预算满足；空模型feasible=false保留。

## 对R05漏检的逐ID恢复分析

| 单层 | 单层检出 | 与跨层交集 | 与跨层并集 | 补检跨层30个漏检 | 跨层独有 | 两者均未检出 |
|---|---|---|---|---|---|---|
| native84 | 0 | 0 | 24 | 0/30 | 24 | 30 |
| app_web67 | 27 | 15 | 36 | 12/30 | 9 | 18 |
| host26 | 0 | 0 | 24 | 0/30 | 24 | 30 |

AppWeb与跨层交集15、单层独有12、跨层独有9，互不包含。集合并集36仅描述保存结果的重叠，不是新训练或新生成的OR集成预测，也不是一个获评估的部署模型。Native和Host没有补检。

AppWeb补检的12个分布为 `w6-tool-058-legacy-default-v1` 9个、`w9-rule-boundary-cdp-resource-pair-v1` 3个；这两项正是R05完全漏检8配置中的2项。30个R05漏检ID全部保留在missed_attack_recovery.csv/jsonl，没有只列成功恢复。原8配置结果如下：

| R05完全漏检配置 | 攻击数 | Native | AppWeb | Host |
|---|---|---|---|---|
| w10-cdp-emulation-screen-metrics-only-v1 | 3 | 0/3 | 0/3 | 0/3 |
| w10-cdp-emulation-timezone-only-v1 | 3 | 0/3 | 0/3 | 0/3 |
| w6-tool-058-legacy-default-v1 | 9 | 0/9 | 9/9 | 0/9 |
| w9-rule-boundary-cdp-resource-pair-v1 | 3 | 0/3 | 3/3 | 0/3 |
| w9-rule-boundary-cdp-webdriver-only-v1 | 3 | 0/3 | 0/3 | 0/3 |
| w9-stealth-boundary-languages-only-v1 | 3 | 0/3 | 0/3 | 0/3 |
| w9-stealth-boundary-plugins-mime-v1 | 3 | 0/3 | 0/3 | 0/3 |
| w9-stealth-boundary-webgl-pair-v1 | 3 | 0/3 | 0/3 | 0/3 |

AppWeb同时遗漏跨层能检出的9个，来自 `w9-rule-boundary-cdp-ua-only-v1`、`w9-rule-boundary-cdp-ua-platform-desktop-v1`、`w9-rule-boundary-cdp-platform-only-v1`，各3个，均在env-003外折。

存在“单层有信号、当前跨层候选未直接表达”的具体保存证据：前两折中6个w6-tool-058攻击命中mime_types_count>0和languages长度>1；第三折中另3个w6-tool-058及3个resource-pair攻击命中hardware_concurrency>4。冻结核心候选清单不读取这三个字段，其相应单字段条件没有直接表示；逐ID真子句与字段核对见representation_gap_cases.jsonl。这是当前候选表示的范围说明，不是硬件并发值、语言列表或插件数量在所有合法场景下都代表攻击，更不是机制因果证明。本轮没有据此增加跨层规则或重新设计V2。

## 环境、选中规则与来源解释

| 环境/折 | Native | AppWeb | Host | R05跨层 |
|---|---|---|---|---|
| env-001 | 0/9 | 9/9 | 0/9 | 6/9 |
| env-002 | 0/6 | 6/6 | 0/6 | 3/6 |
| env-003 | 0/39 | 12/39 | 0/39 | 15/39 |

AppWeb前两折选择相同六条件（NW-006正极性、mime_types_count>0、webdriver=True、timezone_offset>0、device_memory>2、languages长度>1），第三折只选择hardware_concurrency>4。三折所选文字集合Jaccard为1/0/0；R05跨层为1/1/1。空模型相互Jaccard保持0/0 NE。完整模型ID、条件、阈值和训练成员见MODEL_RULES、MODEL_MANIFEST、encoders/及RULE_STABILITY。

第三折只有45个训练阶段，两个环境的训练支持没有包含env-003的全部边界配置；其学到的单个资源阈值在外层检出12/39，并漏掉UA/platform边界。前两折训练较大的候选/配置支持与测试较窄的配置组成不同，不能把环境差异直接解释成环境因果效应或物理设备泛化。

R06的E和O_u跨层来源重训练回答来源问题，R07回答输入表示问题。R07的目录原子可以带E/H等来源，单字段控制编码明确登记PROJECT_CONTROL_NOT_E_Ou_H_C；不能把这些控制获益算成E来源的贡献，也不能把R06的H核心结构不可用与R07 Native/Host经过非空池训练后的空模型混为一谈。

完整14配置、3环境及配置×环境指标在by_configuration、by_environment、configuration_comparison和保存OOF中；本报告保留全部漏检、空模型和不同分母。当前材料已暴露，结果是回顾性分组评价；不是全新盲测、总体零FPR保证或已验证的机制泛化。

## 未运行分支、验证和停止

R07_FIXED_MODEL_MASK的3折×3遮蔽表面共9个预留项全部NOT_RUN/null，冻结接口未实现。本轮未修改快照补接口。R07_SEMANTIC_DIAGNOSTIC的NEGATE_U、FAILED_ATOM、DUPLICATE_ALIAS、EMPTY_MODEL四项仍为SYNTHETIC_ONLY登记；没有可调度R07作业入口或精确expected单元，本轮主分支授权下未另跑，均NOT_RUN/null。旧合成测试不冒充本次R07状态/门控实验。Browser攻击分支NOT_AVAILABLE；没有为App177补造Browser结果。

R07父步骤为PARTIALLY_COMPLETED，单层重训练主分支完成待外部验收；BRANCH_STATUS不把未运行分支标完成。R06父步骤继续PARTIALLY_COMPLETED，来源主分支已通过，POSTFIT_DELETE仍NOT_RUN且不阻塞本轮。

原dispatcher累计real_fits=57，本次增量9。共享账本从48增至57/200次拟合，计费增量10.423875458秒，累计66.336649709/21600秒，余143次、21533.663350291秒；原63个R05/R06作业记录与artifact_directory逐项不变，账本未重置。端到端wall与预算计费范围分别记录。

独立核算4,680个折级/OOF及全部分层指标项；9个新作业访问链、完整白名单、186个encoder条目、3份R05只读引用、三值解释与train目标/clean预算核对通过。数值逐调用日志限制如上，不写成不存在的执行证据。R01–R06历史文件保持原样，外部验收和本轮保护记录分开保存。历史清单中的全局状态/预算摘要属于原执行时点，不用新账本覆盖旧清单。

完成后停止等待验收。没有R08、全开发集重拟合、补采、攻击工具、旧S07、V2重设计、提交或推送。
