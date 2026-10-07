"""Render the research report from saved outputs; never evaluate models/conditions."""
from pathlib import Path
import json,collections
HERE=Path(__file__).resolve().parent;OUT=HERE/'results'
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines()]
def states(rs):
    c=collections.Counter(r['state'] for r in rs);return '/'.join(str(c[k]) for k in ['T','F','U','FAILED','EMPTY_MODEL'])
def main():
    summary=read(OUT/'summary/SUMMARY.json');positions=rows(OUT/'positions.jsonl');conds=rows(OUT/'conditions.jsonl');models=rows(OUT/'model_predictions.jsonl');mtc=rows(OUT/'mtc_conditions.jsonl');verify=read(OUT/'COLLECTION_VERIFICATION.json');exec_=read(OUT/'EXECUTION.json')
    scenarios=['A_APP_RESOURCE','A_APP_MEMORY4','A_BROWSER_RESOURCE','A_BROWSER_MEMORY4','N_APP_SHAM','N_BROWSER_SHAM'];names=list(dict.fromkeys(r['condition'] for r in conds));norm=[p for p in positions if p['identity']=='NORMAL'];by={p['sample_id']:p for p in positions}
    lines=['# App177＋独立Browser67：资源／内存配对补证','',
      '2026-10-07；承接提交 `4da140147dde91700d33d23ef70be0c20ca694ed`。本轮只补一个资源组，0模型拟合、0规则选择、0 Browser重训。App主体消融和语言／时区既有成果保持原样。',
      '',f"正式54个预定配对位置，实际确认{summary['effective_count']}次有效修改、{len(norm)}个正常位置；配对成立 {summary['pairs_valid']}/54。有效修改中混杂 {summary['effective_confounded']}、恢复未确认 {summary['effective_recovery_unconfirmed']}。这些是操作、当前raw与恢复核验的结果，不是直接把预定12／42填成事实。",'',
      '**研究含义**：在本批App侧资源修改中，独立Browser差异提供的是与原Native内存检查重叠的证据；在Browser侧，当前App Native能识别仅靠Browser大于8检查漏掉的4，但这个跨端上界在正常MTC中也有反例。两端Web简单相等的正常偏离更多，不能直接作为独立攻击报警。','',
      '## 1. 真实环境、操作与配对','',
      '使用本轮只读API36.1 arm64实例、归档FeatureApp v16，Chrome与WebView均为134.0.6998.135。实例原配置约2GiB RAM、1 CPU，未降低内存、调整CPU、修改宿主机时区或更换环境。两端正式页面初始deviceMemory=2、hardwareConcurrency=1；Native内存约1.93GiB。因此本次4是2→4的向上修改，没有实测8→4向下修改或原值即4的正式样本；这两类只由针对性测试覆盖，不能写成实测结论。',
      'App使用原字节file资产页面；Browser使用原字节loopback探针。存在性、读取状态、origin、isSecureContext、实际getter与原始采集值分别记录，about:blank只验证新文档。安全上下文和版本说明见 [字段语义](FIELD_SEMANTICS.md)，实际环境见 [ENVIRONMENT.json](ENVIRONMENT.json)。',
      '每轮按登记顺序交错六个过程，每组三阶段均重新真正采集两端。App资源16／48复用旧配置；Browser16／48是新镜像过程。空操作没有重新定义getter。控制保持到两端回执完成后撤销，前后核对资源、Native及主要非目标字段。',
      'pair ID和scenario group分开，按原始票据、回执、provenance与物理行绑定，不以时间或值猜配对。新原始关联与全部命令记录仅保存在被忽略的private_runs。分析使用RP001–RP054别名。',
      f"两端payload时间差为 {summary['sampling_interval_seconds']['min']}–{summary['sampling_interval_seconds']['max']} 秒（N={summary['sampling_interval_seconds']['N']}），不是原子同步读取。Native与另一端资源稳定依据单列。原runner的control_begin是准备开始；本批从CDP ledger另取目标端控制命令和撤销命令时间，避免把Browser较晚安装的控制误写成App导航前已生效。",'',
      '|过程|三阶段组|当前有效修改|正常|无效果／不支持／未确认|','|---|---:|---:|---:|---:|']
    for sc in scenarios:
        ps=[p for p in positions if p['scenario']==sc];counts=collections.Counter(p['identity'] for p in ps)
        lines.append(f"|{sc}|3|{sum(p['effect']['effective'] for p in ps)}|{counts['NORMAL']}|{len(ps)-counts['NORMAL']-counts['CONTROLLED_INTERVENTION']}|")
    lines+=['','联合过程按每项原字段变化分类，单内存过程保持CPU报告不变。有效修改即便检测F/U/FAILED或随后恢复失败，也保留在有效分母。完整逐位置核验在 [positions.jsonl](results/positions.jsonl)。',
      '', '## 2. 六个固定条件：修改端与正常成本分开','',
      '以下每格为 **T/F/U/FAILED/EMPTY_MODEL**。四类change各N=3；正常列含前后阶段和两个sham，共N='+str(len(norm))+'。T是条件偏离，只有在独立确认的有效修改位置才可讨论检出。','',
      '|条件|App 16/48|App内存4|Browser 16/48|Browser内存4|正常|','|---|---|---|---|---|---|']
    for name in names:
        cells=[states([r for r in conds if r['condition']==name and r['scenario']==sc and r['phase']=='change']) for sc in scenarios[:4]]
        cells.append(states([r for r in conds if r['condition']==name and r['identity']=='NORMAL']))
        lines.append('|'+name+'|'+'|'.join(cells)+'|')
    lines+=['', 'R_APP_MEMORY原样调用旧App内存关系；R_NATIVE_BROWSER_MEMORY复用其纯数值上界，但使用独立跨端身份与绑定；R_WEB_MEMORY_DIFFERENCE只比较两端有效Web内存。两个8阈值分别只读单端，CPU差异仅作诊断。缺失、默认0、无效质量为U，错配为FAILED，不借另一端数据填充。',
      '', '### App被修改：Browser是否新增检出','',
      '本批App修改的Native上界与两端Web差异触发交集见 [intersections.json](results/summary/intersections.json)。当两个条件都在同一条App修改上触发时，不能再次算成Browser新增检出。目标16显眼，大于8也能指出异常；目标4本身是正常设备可能报告的值，需要结合当前设备参照讨论。',
      '', '### Browser被修改：App提供什么','',
      'Browser16同时超过8和当前Native上界，参照条件与单字段检查重叠；Browser4未超过8，但高于本机Native对应的二次幂上界2。此时App Native及未被修改的App Web提供本机对照。它们不是不可篡改真值，也不证明对上界以内或双端同时修改仍有效。',
      '', '## 3. 九份冻结App模型：逐配置回放，不是新交叉验证','',
      '三份APP_FULL和两组既有消融的三份RETENTION模型共9份，各只读当前App。原规则、编码器、阈值不变，没有挑最好折或投票。以下是同54位置的分别回放，不能把模型次数当成样本量。每格仍为T/F/U/FAILED/EMPTY_MODEL。Browser列表示其干预位置上的App模型输出，不能自动解释成识别了Browser修改。','',
      '|方案|原折编号|App有效修改 N=6|Browser有效修改 N=6|正常 N=42|','|---|---|---|---|---|']
    for scheme,fold in dict.fromkeys((r['scheme'],r['fold']) for r in models):
        subsets=[[r for r in models if r['scheme']==scheme and r['fold']==fold and r['identity']=='CONTROLLED_INTERVENTION' and r['scenario'].startswith('A_'+end)] for end in ['APP','BROWSER']]
        subsets.append([r for r in models if r['scheme']==scheme and r['fold']==fold and r['identity']=='NORMAL'])
        lines.append('|'+scheme+'|'+fold+'|'+'|'.join(states(r) for r in subsets)+'|')
    phases=read(OUT/'summary/model_triplets.json');persistent=[x for x in phases if x['scenario'].startswith('A_BROWSER') and x['persistent_alarm']];new=[x for x in phases if x['scenario'].startswith('A_BROWSER') and x['new_change_alarm']]
    lines+=['',f"Browser过程共有{len(persistent)}个模型×三阶段组持续T，{len(new)}个组在change为T且pre/post均F。持续报警不能算看到Browser资源改变；单端模型输入范围从未增加Browser。逐组输出见 [model_triplets.csv](results/summary/model_triplets.csv)。",'',
      '三个Full模型均检出本批App有效修改6/6；去内存关系和Web-only均为0/6。Full的18个模型报警位置均由原MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE触发。三组模型在42条正常和6条Browser修改中均F，正常报警0；这支持本批App修改的内部Native参照贡献，也明确App-only整模没有因此看到Browser修改。', '', 'Full与去内存／Web-only在相同位置的增加和丢失报警ID保存在 [model_vs_full.json](results/summary/model_vs_full.json)。具体触发子句与每个原子状态见 [model_predictions.jsonl](results/model_predictions.jsonl)，不能把整模报警归给未触发的内存条件。','',
      '## 4. 891条真实正常MTC：反例与未知同时保留','',
      '沿用原P2代表与630／144／117分组、P1质量和已有正常过程依据。全部891条有研究正常流程支持；这不是逐设备安全证明，144／117也不是新盲测。六条件各算一次，不把891乘以模型折数。','',
      '|条件|discovery N=630|development N=144|reserved_validation N=117|合计 N=891|','|---|---|---|---|---|']
    for name in names:
        rs=[r for r in mtc if r['condition']==name];lines.append('|'+name+'|'+'|'.join([states([r for r in rs if r['group']==g]) for g in ['discovery','development','reserved_validation']]+[states(rs)])+'|')
    lines+=['', '正常两端Web内存差异62/891、CPU差异39/891；不能因为不符合简单相等假设就删除。这些差异可以与API近似化、实现或暴露口径不同相容，但没有逐设备机制证据时不能断言具体原因。',
      '跨端Native上界的3个正常T均为当前Native约3.63–3.67GiB、上界4、Browser报告8；2个在discovery、1个在reserved_validation。它们绑定和数值可比较，保留T，不在看到结果后改成U。App内部关系在这批材料0T，但有65U；跨端上界有50U；简单Web内存相等有88U。不能只比较报警而忽略未知成本。','',
      '### 相同4／16的正常与修改例子','']
    examples=read(OUT/'summary/normal_examples.json')
    for category in examples[:2]:
        lines.append('- '+category['category']+'：'+('按原P2顺序未找到正常Web报告该值的记录。' if not category['examples'] else '按原P2顺序选取，见下列引用。'))
        for e in category['examples']:
            values=e['values'];lines.append(f"  - `{e['sample_id']}`（{e['group']}）：N={values.get('app.android_native_data.memory_layer.total_memory_gb')}，A={values.get('app.web_data.navigator_layer.device_memory')}，B={values.get('browser.web_data.navigator_layer.device_memory')}；App上界={e['states']['R_APP_MEMORY']}，跨端上界={e['states']['R_NATIVE_BROWSER_MEMORY']}，Web差异={e['states']['R_WEB_MEMORY_DIFFERENCE']}。")
    lines+=['', '所有例子的原P2/P1与raw物理引用见 [normal_examples.json](results/summary/normal_examples.json)。本批修改4的当前设备N约1.93、原Web2，与正常设备报告4并不矛盾；不能跨设备借Native值构造反例。没有正常16时明确记为没有，不制造对照。','',
      '## 5. 执行边界、工程失败与下一步','',
      '正式矩阵只运行一次，54个位置分别保留。6个额外冒烟中2个完整配对、另1条单端App；4个位置失败，首次Chrome初始化、通知提示和页面放行超时记录保留。正式矩阵前完成最小初始化与清理修复，没有追加第三组冒烟，没有根据检测分数补采。详见 [ENGINEERING.json](ENGINEERING.json) 与 [采集核对](results/COLLECTION_VERIFICATION.json)。',
      '规范评价位置为486个App模型输出＋324个新条件输出＋5346个MTC条件输出。首轮模型投影遗漏旧编码器的UNFITTED_CONTROL数值列，使486位置全部FAILED；映射修正并对9模型做完整／局部投影一致性测试后，重放同一批486位置，实际模型预测共972次。原486个FAILED完整保留于results/engineering；没有重新拟合或挑选更有利模型。MTC第一次适配额外拒绝3个历史重复session，但原P2已按物理行、payload与P1回执明确选择一次上传；去掉额外session全局门控后，仅对3成员重算六条件，额外18次工程条件调用单列，第一次输出保留。没有修改公式、阈值、适用范围或正常反例身份。',
      '所有既有模型和原内存关系文件在本次载入前后摘要一致；新raw／票据／私有关联未公开。仅重汇总命令不调用采集、预测、拟合或网络，见 [README](README.md)。',
      '**下一步判断**：资源参照值得进入一次预注册、受正常预算约束的有限同成员联合比较，重点检验App作为Browser参照的增量与代价；本轮不自动执行。Native→Browser仍是有正常反例的研究候选；简单Web／CPU不相等不能直接升级为独立报警，更不能手工OR后宣称联合模型收益。向下修改、上界内修改与双端同时修改的真实覆盖仍有限。',
      '本批补齐的是这个资源组。UA、屏幕、WebGL及其他攻击范围的双端材料和方法对照缺口继续保留，不能据此宣布所有App跨端研究完成或启动完整论文定稿。','']
    (HERE/'REPORT.md').write_text('\n'.join(lines))
if __name__=='__main__':main()
