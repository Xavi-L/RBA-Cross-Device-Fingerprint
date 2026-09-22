# MTC 后续实验事实标准

这是 P2 冻结的输入合同，不是待用户填分数的评审模板。当前没有符合本合同的真实 sidecar；缺失值继续为 unknown／null，不阻塞无标签规则发现。

机器合同：[mtc_experiment_fact_v2.schema.json](/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/hybridguard_agent/schemas/mtc_experiment_fact_v2.schema.json)。载入入口是 P2 builder 的 `--facts`；追加事实必须构建新版本，不能修改当前只读注册表。

| 事实 | 必要依据与绑定 | 不可用的替代依据 |
|---|---|---|
| 样本对应关系 | sample_id、App session、App payload 标识、Browser payload 标识全部精确匹配；无 Browser 时明确 null | 同一型号、同一 session 的别次上传、旧攻击 App 拼新 Browser |
| 无主动干预的参考记录 | 独立的本轮采集过程记录、无主动干预声明及证据引用 | MTC／真机来源、未告警、低风险分、字段一致 |
| 指纹干预正例 | controlled_intervention_record；真实执行 succeeded；field_effect=observed；具体目标字段；目标字段在该观测可用；外部核验 label_status=verified | 工具安装／启动成功、接口返回成功、网络路径被改、LLM／规则判断 |
| 指纹干预负例／baseline | 独立 baseline 记录；manipulation_present=false；execution=not_applicable；field_effect=no_configured_change；无主动干预事实 | 缺少攻击日志、没有命中规则、将 unknown 转为 false |
| 跨次身份 | 明确稳定 identity key、physical_device／provider_device_profile／device_profile 范围、已核验状态及支持记录 | collector_install_id 自动当物理设备、型号相同、指纹相似度、旧实验未复核分组 |
| 两态 scenario | 同 scenario、重复编号；baseline 与 attack_active 各一次；UTC 阶段记录有先后；可信身份一致；两阶段均为合格 paired244；独立事实标签 | 后补伪造阶段、跨不同设备拼样本、把 JSON 离线改值当真实工具效果 |

沿用 baseline → attack_active 两态，不恢复 clean_post 为必做条件。缺某阶段、整层采集失败、目标字段无变化、身份或时间证据不足都保留失败原因，不能静默删去后计算更好的效果。运输路径干预另立任务，不自动成为指纹字段操纵正例。

schema 使用 `baseline` 与 `attack_active` 阶段名称，不自动导入旧 clean_pre／clean_post 或旧标签。phase_started_at_utc 必须带 UTC 偏移；程序检查 baseline 时间早于 attack_active，但时间值的真实性仍需由引用的执行记录支持。

evidence_refs 是相对于原事实文件目录或绝对路径的本地证据文件引用。代码验证存在性、类型、双端 payload 绑定和内部一致性；它不替代证据内容核验，也不会因文件存在就自动把 unverified 升为 verified。冻结 input_manifest 保存原始引用基准目录。

所有标签、身份断言、scenario／阶段、攻击族、执行结果和效果事实仅进入控制平面与评价报告，不进入检测规则、LLM prompt、检索或模型特征。P2 提供的 inference projection 仅允许样本 ID、源文件／行号和两端 payload 引用。

检测任务至少还需每集合 5 个合格分组、每类至少 2 个分组，以及 P4 运行链、P5 真实证据和 P6 冻结评价协议。这些是程序下限而非统计充分性证明。当前所有类别的合格分组为 0，检测数据门槛明确为 false。
