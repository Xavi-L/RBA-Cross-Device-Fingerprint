"""Render Chinese review tables from saved outputs only."""
from rx_common import *
def render(out=HERE/'results'):
    summary=read(out/'summary/SUMMARY.json');checks=read(out/'candidate_checks.json');models=read(out/'models.json')
    unknown=read(out/'summary/unknown_overlap.json');details=read(out/'summary/member_deltas.json')
    folds={m['base_model_id']:m['fold'][-2:] for m in models}
    state=lambda c:'/'.join(str(c[k]) for k in ('T','F','U','FAILED'))
    reason={'NORMAL_ALARM_BUDGET:mtc_discovery':'MTC正常报警超预算','MODEL_DEFINED_COVERAGE:mtc_discovery':'联合明确输出不足90%',
            'CANDIDATE_COVERAGE:W':'W候选覆盖不足90%','RULE_BUDGET':'规则超8','COMPLEXITY_BUDGET':'复杂度超16'}
    lines=['# 冻结App+C1上的资源增量选择与同成员比较','',
      '**结论：三个配置均仅空增量S0可行，保留原B2-C基础方法。在当前冻结基线和约束下，没有可接入的资源条件。**',
      'M与B的主要限制是联合未知覆盖；W还超过正常报警预算且候选自身覆盖不足。空增量保持原App+C1推理语义，不是EMPTY_MODEL，也不是将训练失败伪装成达标。三份基础模型本身通过新增四组正常要求。','',
      '实际完成3个有限集合选择任务、24个集合检查。这属于学习；本轮0新增采集、0 App训练、0树拟合、0数值编码器拟合。没有重跑App四项消融，没有修改旧模型、C1、六资源条件、原目标4/16、二次幂上界或正常反例。','',
      '## 1. 身份、共同输入与学习边界','',
      '固定1,005个批次记录：MTC discovery630、旧Browser先导18（12正常/6修改）、原匹配42（34正常/8修改）、资源54（42正常/12修改）、MTC development144及reserved_validation117。选择744位置包含718正常与26有效修改；历史评价261位置全为正常。三配置重复运行不会增加独立样本量。','',
      'B2-C三个真实身份来自旧results/models.json，均为冻结App+C1，绝不使用B3-B去正常上限的C2消融。App规则/极性/编码器与条件版本核验记录见FROZEN.json。原MTC P2代表及630/144/117分组、P1质量、物理行/payload/receipt绑定沿用旧读取器，并在本轮全部原始输入复核。','',
      '资源别名加resource54命名空间；通过原scenario/round/phase找到固定计划项，再校验capture_id、sample_id、runtime_context、collection_round及原始票据绑定，不按行号猜配对。完整映射位于private_runs/resource_alias_binding.json，本次后续授权将该映射与必要原始证据按白名单纳入Git审核，见REMOTE_REVIEW.md。6条资源冒烟和旧被替换的6条语言设置记录未进入。操作效果、恢复与检测分别保存，54条原身份未改写。','',
      '旧951×3基础输出复用并逐身份核对；资源54×3 App Full输出复用，新算54次C1（实际均F，并非依据场景填F）。旧60条从各自真实App/Browser原始配对调用六条件60次，实际360个条件输出（均F）；MTC891和资源54的三个候选逐条复用。','',
      '集合固定为S0、M、W、B、MW、MB、WB、MWB；候选顺序M/W/B。选中依赖FAILED优先，然后T/F/U的原OR语义；未选错误不污染输出。容量包括基础App+C1及每个新增正向单文字子句（1规则、复杂度2）。前两个基础7/14，第三个6/12。四组正常上限31/0/1/2，分别至少90%明确输出；候选在MTC discovery至少90%明确。','',
      '## 2. 主表一：全部24个开发集合检查','',
      '正常格为T/F/U/FAILED。另列MTC联合明确输出；其余三组每个集合均100%明确。宏平均为八家族同权，微平均分母固定26。完整机器可读表见[候选检查](results/candidate_checks.json)及[CSV](results/summary/candidate_checks.csv)。','',
      '|配置|集合|宏平均|修改T/26|MTC正常630|明确/630|先导正常12|匹配正常34|资源正常42|规则/复杂度|可行与原因|',
      '|---|---|---:|---:|---|---:|---|---|---|---|---|']
    for c in checks:
        ns=c['normals'];lines.append('|'+ '|'.join([folds[c['base_model_id']],c['set_id'],f"{c['macro']['value']:.1%}",str(c['micro']['T']),state(ns['mtc_discovery']),str(ns['mtc_discovery']['defined']),state(ns['pilot18']),state(ns['b2b42']),state(ns['resource54']),f"{c['rule_count']}/{c['complexity']}",'通过' if c['feasible'] else '；'.join(reason.get(r,r) for r in c['reasons'])])+'|')
    lines+=['','基础在MTC上为6T/561F/63U，明确567/630，恰好90%。M、B单独候选均589/630明确（93.49%），加入基础却都变成560/630（88.89%），因此即使有剩余容量也不满足要求。W只有560/630明确（88.89%），联合正常报警46条超过31。第三配置可容纳两个新增条件，但覆盖限制仍阻止接入。','',
      '## 3. 主表二：固定组合与真实选择的八家族结果','',
      '各格为T/N；这些修改位置本轮均无U/FAILED。M/B/W为**未通过约束的诊断组合**，不能作为已接入方法报告。真实选择S0的八家族宏平均50%，微平均13/26；这些成绩使用了三批小实验进行选择，不是新盲测。','',
      '|配置|组合|接入状态|App语言|App时区|Browser语言|Browser时区|App资源16/48|App内存4|Browser资源16/48|Browser内存4|微平均|宏平均|',
      '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for model in models:
        for sid in ('S0','M','B','W','SELECTED'):
            key=model['selected_set'] if sid=='SELECTED' else sid;c=next(c for c in checks if c['base_model_id']==model['base_model_id'] and c['set_id']==key)
            lines.append('|'+ '|'.join([model['fold'][-2:],('真实选择 '+key) if sid=='SELECTED' else key,'通过' if c['feasible'] else '诊断/不合格',*[f"{c['families'][f]['T']}/{c['families'][f]['n']}" for f in FAMILIES],f"{c['micro']['T']}/26",f"{c['macro']['value']:.1%}"])+'|')
    lines+=['','App侧6条资源修改原Full已经全部触发；M不在这些App侧位置触发，W虽也触发但与基础报警重叠，均不能重复算Browser增益。Browser资源16/48的3条被M和B同时识别，不能独占归功于Native参照。Browser内存4的3条只有M/W触发而B不触发，是当前App Native参照相对单字段大于8的直接补充证据。','',
      '基础+M与基础+B仅是在同一个完整App+C1背景下增加不同检查，不是完整Browser-only分类器与完整App方法的公平重训比较。向下、上界以内、双端同时修改没有因此获得新的真实覆盖。','',
      '## 4. 主表三：相对基础的逐成员变化','',
      '表中训练=开发744，历史=261正常。新增/丢失检出只数有效修改；F→U与U→T按该组全部位置列出，当前新增F→U均在正常记录。全部八集合、六批次及每条交集ID见[逐成员变化](results/summary/member_deltas.json)和[CSV](results/summary/deltas.csv)。','',
      '|配置|集合|范围|新增检出|丢失检出|新增正常报警|F→U|U→T|', '|---|---|---|---:|---:|---:|---:|---:|']
    for model in models:
        for sid in ('S0','M','B','W'):
            for group in ('selection','historical_evaluation'):
                r=next(r for r in summary['deltas'] if r['fold']==model['fold'] and r['set_id']==sid and r['group']==group)
                lines.append('|'+ '|'.join([model['fold'][-2:],sid,'开发744' if group=='selection' else '历史261',*[str(r[k]) for k in ('new_detection','lost_detection','new_normal_alarm','F_to_U','U_to_T')]])+'|')
    lines+=['','所有固定组合本轮均无丢失检出、无新增FAILED；这只是当前成员的结果，不修改FAILED优先级。真实选择与基础逐条相同，增益、损失、正常新增报警和未知新增均为0。旧先导、匹配、资源分别统计于逐成员变化文件；正常Browser语言偏好change为2/2 F，资源sham为18/18 F，三个配置、全部集合一致。','',
      '## 5. 未知叠加与正常反例','',
      'MTC discovery：App单端51U，C1为20U，两者交集8，基础联合63U。资源M/B各41U，与基础63U交集34，联合70U；新增7条恰为基础F→U。W为70U并包含基础全部63U。必须使用这些逐ID集合，不能把单条件93.49%覆盖直接当联合覆盖。','',
      '7条新增训练U在原资源条件中均为Browser device_memory的QUALITY_UNAVAILABLE；原始输入复核仍与保存状态一致，没有把它们默认补F。每条ID以及六批次的交并集保存在[unknown_overlap.json](results/summary/unknown_overlap.json)。','',
      '|集合|MTC development144 T/F/U/FAILED|MTC reserved117 T/F/U/FAILED|', '|---|---|---|']
    for sid in ('S0','M','B','W'):
        cs=[next(r for r in details if r['fold']==models[0]['fold'] and r['set_id']==sid and r['group']==co)['normal'] for co in ('mtc_development','mtc_reserved_validation')]
        lines.append('|'+sid+'|'+state(cs[0])+'|'+state(cs[1])+'|')
    lines+=['','上表三个配置逐条状态相同；完整分别结果保留。144/117是在选择冻结后评价的历史接触正常材料，不能提供未见攻击检出率，也不称独立盲测。','',
      'M的3条正常反例保持原组：']
    for r in summary['counterexamples']:lines.append(f"- `{r['sample_id']}`：{r['cohort']}，{r['identity']}，{r['role']}。")
    lines+=['','其Native约3.63–3.67GiB、二次幂上界4、Browser内存8。两条discovery增加正常报警，reserved的一条仍留在评价组；不改变为U、不移入训练，也不因总占比小而把Native称为硬件真值。W在正常MTC有62次偏离，训练40、历史22；这些不能当作攻击标签。','',
      '## 6. 实际入口、执行账本与停止点','',
      '三个新模型有独立resource-devext身份，保留旧基础引用、扩展集合、条件版本和选择状态；均为BASELINE_RETAINED。当前可信App/Browser配对入口见[README](README.md)，v16原始档案经receipt/payload配对绑定后推理；原MTC入口沿用P1质量及原App时间/内存适配。标签/家族/目标/pre/post/设备ID不进入推理。','',
      '选择阶段复用2853个旧B2-C输出、162个资源App输出、2835个资源候选状态；新执行54次C1、60次六条件接口＝360条件输出，以及162次基础OR组合。三次选择检查24集合，保存24,120个模型/集合/成员状态。','',
      '冻结后当前输入复核覆盖全部1,005成员：3015次原App预测、1005次C1、1005次六条件接口＝6030条件输出，全部与保存状态一致；同时独立复算24,120个OR与24组约束/目标/优胜者，无再次选择。合计本轮研究预测/核验为3015 App预测、1059 C1、6390资源条件输出；候选集合学习单列3任务/24检查。历史972次App预测、18次MTC修复未重做。','',
      '14项针对性测试通过，包括四组预算、逐ID未知并集、端点隔离、错配、FAILED优先、空扩展、容量、平局/无可行集合、实际261评价值扰动不影响选择、当前入口一致性、仅重汇总禁用推理/选择/拟合/联网并逐文件相同。测试的合成选择与扰动回归调用在TESTS.json单列，不算新的科研模型或样本。','',
      '**唯一最小下一步：先对这7条新增正常U做一份基于现有原始证据的字段可用性说明，明确当前App+C1与Browser内存联合依赖的适用边界。** 本轮不放宽90%门槛、不增加容量、不采新设备、不启动同方法联合消融；本次可接入性问题已有负面答案，保留已有基础方法。','',
      'App主体消融、语言/时区局部跨端证据和资源配对继续有效。UA、屏幕、WebGL的双端修改/正常代价与同方法比较仍不足，限制“通用跨端覆盖”“多设备/未见工具泛化”“完整244字段公平比较”等尚无支持的主张；不是自动要求穷举所有剩余字段。W1完整定稿未启动，也不宣称项目完整结束。用户后续已明确授权提交推送本轮改动和必要私有数据。REVIEW_EVIDENCE.json列出纳入Git的16个必要原始证据文件；其他私有产物继续忽略。目标仓库为public，纳入文件可公开访问。原执行快照中未提交／未推送状态是此前实验停止点的历史记录。','']
    (HERE/'REPORT.md').write_text('\n'.join(lines))
if __name__=='__main__':render()
