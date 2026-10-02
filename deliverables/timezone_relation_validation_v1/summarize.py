#!/usr/bin/env python3
"""Saved-results-only summary: no raw loading, prediction, training, or collection."""
import argparse
from collections import Counter, defaultdict
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('prior_summary',HERE.parent/'mtc_constrained_reselection_v1/summarize.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
SCHEMES=('B_REL','B_REL_TZ')
TZ='MTCREL:NATIVE_ZONE_AT_ACQUISITION_VS_WEB_OFFSET_DIFFERS'
SUBSETS=('discovery','development','reserved_validation')
ALERT='MANIPULATION_ALERT'

def read(path,default=None): return json.loads(path.read_text()) if path.exists() else default

def rows(path):
    if not path.exists(): return []
    with gzip.open(path,'rt') as s: return [json.loads(line) for line in s if line.strip()]

def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def validate(data,settings):
    expected={}
    for scheme in SCHEMES:
        for f in settings['folds']:
            expected[scheme,f['fold_id'],'controlled','heldout']=set(f['outer_test_ids'])
            for subset in SUBSETS: expected[scheme,f['fold_id'],'mtc',subset]=set(settings['mtc_primary_ids'][subset])
    actual=defaultdict(set)
    for r in data:
        k=r['scheme'],r['fold_id'],r['dataset'],r['subset']
        if r['sample_id'] in actual[k]: raise ValueError('DUPLICATE_PREDICTION')
        actual[k].add(r['sample_id'])
    if actual != expected: raise ValueError('PRESPECIFIED_EXACT_MEMBERS_REQUIRED')

def partition(r): return r['subset'] if r['dataset']=='mtc' else 'controlled_'+('attack' if r['stage']=='attack' else 'normal')

def local_summary(data):
    groups=defaultdict(list)
    # evaluate_local is required to supply process/effect-derived normal_basis.
    for r in data:
        groups['all_planned'].append(r)
        if r.get('normal_basis',{}).get('supported'): groups['confirmed_normal'].append(r)
        if r.get('process_type')=='L' and r.get('phase')=='change': groups['L_system_change'].append(r)
        if r.get('process_type')=='A' and r.get('phase')=='change': groups['A_web_only'].append(r)
        if r.get('observable_intervention') is True: groups['A_observable'].append(r)
    result={}
    for key,subset in groups.items():
        conds={name:dict(Counter(r.get('conditions',{}).get(name,{}).get('state','FAILED') for r in subset))
               for name in sorted({name for r in data for name in r.get('conditions',{})})}
        models=defaultdict(list)
        for r in subset:
            for m in r.get('models',[]): models[m['scheme']+'/'+m['fold_id']].append({**m,'normal_basis':r.get('normal_basis',{})})
        result[key]={'positions':len(subset),'conditions':conds,'models':{k:h.count_rows(v) for k,v in models.items()}}
    return result

def summarize(out=HERE):
    out=Path(out); settings=read(out/'SETTINGS.json'); members=read(ROOT/settings['membership_and_baseline_settings'])
    data=rows(out/'predictions.jsonl.gz');validate(data,members)
    result=h.summarize_rows(data)
    baseline={(r['fold_id'],r['sample_id']):r for r in data if r['scheme']=='B_REL'}
    transitions=defaultdict(Counter);tzstats={};counterexamples=[]
    for r in data:
        if r['scheme']!='B_REL_TZ':continue
        old=baseline[r['fold_id'],r['sample_id']]; part=partition(r); k=r['fold_id']+'/'+part
        transitions[k][old['decision']+' -> '+r['decision']]+=1
        relation=next(c for c in r['relation_results'] if c['atom_id']==TZ)
        stat=tzstats.setdefault(k,{'records':0,'T':0,'F':0,'U':0,'FAILED':0,'reasons':Counter(),
             'selected_triggers':0,'unique_selected_alerts':0,'repeated_selected_triggers':0})
        stat['records']+=1;stat[relation['state']]+=1;stat['reasons'][relation['reason']]+=1
        triggered=[c for c in r['rules'] if c['state']=='T'];selected=any(c['atom_id']==TZ for c in triggered)
        stat['selected_triggers']+=selected
        stat['unique_selected_alerts']+=selected and len(triggered)==1 and r['decision']==ALERT
        stat['repeated_selected_triggers']+=selected and len(triggered)>1
        oldtimezone=[c for c in old['rules'] if 'execution_layer.timezone_offset' in c['atom_id'] and c['state']=='T']
        if r['dataset']=='mtc' and (oldtimezone or relation['state']=='T'):
            counterexamples.append({'sample_id':r['sample_id'],'fold_id':r['fold_id'],'subset':r['subset'],
                'profile':r.get('profile'), 'normal_basis':r.get('normal_basis'),
                'old_decision':old['decision'],'new_decision':r['decision'],'old_timezone_trigger':oldtimezone,
                'timezone_relation':relation,'new_triggered_rules':r['triggered_rules']})
    result.update(decision_transitions=transitions,timezone_relation=tzstats)
    models=[];training=[]
    for scheme,directory in [('B_REL',HERE.parent/'mtc_relation_extension_v1'),('B_REL_TZ',out)]:
        for m in read(directory/'models.json')['models']:
            if m['stage']!='RETENTION':continue
            model=read(directory/m['path'])
            models.append({**m,'complexity':model['complexity'],'atoms':model['atoms']})
            if scheme=='B_REL_TZ':
                detail=read(directory/m['training_path'])
                training.append({'fold_id':m['fold_id'],'model_id':m['model_id'],
                    'timezone_candidates':[c for c in detail['candidate_statistics'] if c['atom_id']==TZ],
                    'trace':detail['trace']})
    result.update(models=models,timezone_training=training,execution=read(out/'EXECUTION.json'),
        memory_normal_review=read(out/'MEMORY_NORMAL_REVIEW.json'),validation=read(out/'VALIDATION.json'))
    local=rows(out/'new_batch.jsonl.gz');result['local']=local_summary(local)
    result['collection']=read(out/'COLLECTION.json',{})
    result['local_flow']=read(out/'LOCAL_EVALUATION.json',{})
    write(out/'summary.json',result);write(out/'NORMAL_TIMEZONE_EXAMPLES.json',counterexamples)
    render(out,result,counterexamples,local)
    return result

def metrics(s):
    return f"{s['alerts']}/{s['records']} | {s['no_alert']} | {s['unknown']} | {s['failed']} | {s['empty_model']} | {h.fraction(s['defined_coverage'])}"

def render(out,s,examples,local):
    old,new=(s['schemes'][x]['controlled_oof'] for x in SCHEMES)
    lines=['# 时区关系：已有 MTC 正常约束下的选择与本地变化验证','',
        f"保存 B_REL 检出 {old['attack']['alerts']}/{old['attack']['records']}，B_REL_TZ 检出 **{new['attack']['alerts']}/{new['attack']['records']}**；配对正常报警分别为 {old['clean']['alerts']}/{old['clean']['records']} 和 {new['clean']['alerts']}/{new['clean']['records']}。",'',
        f"同成员使用 {s['inventory']['unique_controlled_records']} 条受控记录和 {s['inventory']['unique_mtc_records']} 条 MTC 代表记录（{s['inventory']['mtc_model_os_combinations']} 个厂商／型号／系统组合）。这是已经使用材料上的开发评价，不是新独立盲测；MTC 同一记录被三个模型评价，不能累加为三倍独立样本。",'',
        '本轮只增加一个日期感知时区关系。原 50 候选、内存/屏幕关系、受控训练编码器、双正常 5% 报警预算、90% MTC 可评估/模型覆盖要求、8 条/复杂度 16 和选择目标保持原样。三个折分别新 GREEDY 再 R_KEEP，共 6 次拟合，未额外训练或调参。', '',
        '## 字段含义与日期依据','',
        'Native rawOffset 是标准时偏移（分钟，UTC 以东为正），Web getTimezoneOffset 是采集时的反向偏移。新关系使用同次 App 的 Native IANA ID 和设备侧开始/结束时间，以 Python zoneinfo、固定 IANA tzdb 2026c 算出当前偏移。只比较偏移，不比较时区 ID 文本；合法别名和相同偏移的不同地区不会仅因名字报警。', '',
        '开始时间在 Native/Web 读取前，结束时间在二者读取后；这是包围范围，不是两者瞬间同步。跨偏移转换、动态地区缺可靠日期、未知 ID 或质量不足保留 U；执行/绑定错误为 FAILED。旧语法固定偏移域可在缺日期时复用原规则，绝不使用“今天”或上传时刻替代历史日期。0 和 -1 都是有效偏移。依据与采集代码见 SEMANTICS.md。', '',
        '## 同成员模型评价','',
        '| 方案/集合 | 报警/预定数 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出覆盖 |','|---|---:|---:|---:|---:|---:|---|']
    for scheme in SCHEMES:
        for key,label in [('attack','受控攻击'),('clean','配对正常')]:
            lines.append(f'| {scheme} {label} | {metrics(s["schemes"][scheme]["controlled_oof"][key])} |')
    for scheme in SCHEMES:
        for fid,f in s['schemes'][scheme]['folds'].items():
            for sub in SUBSETS:lines.append(f'| {scheme}/{fid[-2:]}/{sub} | {metrics(f["mtc"][sub])} |')
    lines+=['','MTC discovery 为训练正常约束；144 条 development 与 117 条 reserved_validation 分开评价。已确认正常报警比例以各子集有依据的成员为分母，见 summary.json；未知/失败不当正常正确。全部计划成员逐 ID 对齐，实际处理数和失败数单列。','','| 原攻击配置 | B_REL | B_REL_TZ |','|---|---:|---:|']
    for config,v in old['configurations'].items():
        a=v['attack'];b=new['configurations'][config]['attack']
        lines.append(f'| {config} | {a["alerts"]}/{a["records"]} | {b["alerts"]}/{b["records"]} |')
    lines+=['','## 选择与贡献','']
    for m in s['models']:
        clauses=[h._short_clause(c) for c in m['selected_clauses']]
        lines.append(f'- {m["scheme"]}/{m["fold_id"][-2:]}：{m["rule_count"]} 条，复杂度 {m["complexity"].get("objective_complexity")}，`{m["model_id"]}`。条件：'+ '; '.join(clauses)+'。')
    lines+=['','| 折/时区候选 | 训练攻击 T | 受控正常 T | MTC T/F | MTC T | 入选 | 原因 |','|---|---:|---:|---:|---:|---|---|']
    for t in s['timezone_training']:
        for c in t['timezone_candidates']:
            a,n,m=(c.get(k,{}) for k in ('controlled_attack','controlled_clean','mtc_normal'))
            reasons=list(dict.fromkeys(c.get('admission_reasons',[])+c.get('selection_reasons',[])))
            lines.append(f'| {t["fold_id"][-2:]}/{c["polarity"]} | {a.get("T")}/{a.get("expected")} | {n.get("T")}/{n.get("expected")} | {m.get("defined")}/{m.get("expected")} | {m.get("T")}/{m.get("expected")} | {c["selected"]} | {"; ".join(reasons)} |')
    selected=sum(any(a['atom_id']==TZ for a in m['atoms']) for m in s['models'] if m['scheme']=='B_REL_TZ')
    absolute=sum(any('execution_layer.timezone_offset' in a['atom_id'] for a in m['atoms']) for m in s['models'] if m['scheme']=='B_REL_TZ')
    lines+=['',f'新时区关系在 {selected}/3 个模型入选，旧绝对偏移条件在 {absolute}/3 个新模型保留；没有预先删除旧条件。']
    for fid,f in s['schemes']['B_REL_TZ']['folds'].items():
        b=s['schemes']['B_REL']['folds'][fid]
        ev=('development','reserved_validation')
        na=sum(f['mtc'][x]['alerts'] for x in ev);ba=sum(b['mtc'][x]['alerts'] for x in ev)
        nu=sum(f['mtc'][x]['unknown'] for x in ev);bu=sum(b['mtc'][x]['unknown'] for x in ev)
        tz=s['timezone_relation'][fid+'/controlled_attack']
        lines.append(f'- 折 {fid[-2:]}：261 条 MTC 评价的报警 {ba}→{na}，U {bu}→{nu}；时区关系在42条该折攻击中触发 {tz["T"]} 条，独有检出 {tz["unique_selected_alerts"]} 条，重复触发 {tz["repeated_selected_triggers"]} 条。')
    lines+=['','新关系在 MTC 的630/144/117条分别全部为F；没有新时区U或正常T。完整模型仍保留内存缺测导致的51/8/6条U，前两折剩余正常报警来自高度条件。本轮不修改这些规则。全部14个攻击配置的检出与保存B_REL一致，没有检出损失。','',
        '逐规则独有/重复报警、训练排序轨迹、正常/攻击触发与不可用原因保存在 summary.json。贡献是保存模型的解释，不是事后删规则后的新模型成绩。','','## 既有正常时区反例','']
    seen=set()
    for e in examples:
        if e['sample_id'] in seen:continue
        seen.add(e['sample_id']);d=e['timezone_relation']['diagnostics'];p=e['profile'] or {}
        lines.append(f'- `{e["sample_id"]}`（{p.get("manufacturer")} {p.get("model")} / Android {p.get("android_release")}，{e["subset"]}）：Native `{d.get("native_timezone_id")}`，标准偏移 {d.get("native_standard_offset_min")}，期望 Web {d.get("expected_web_offset_min")}，实际 {d.get("web_timezone_offset_min")}；关系 {e["timezone_relation"]["state"]}，旧输出 {e["old_decision"]} → 新输出 {e["new_decision"]}。')
    lines+=['','逐条设备日期、字段值、同次原始引用和各折输出完整保存在 NORMAL_TIMEZONE_EXAMPLES.json；报警不会改变常规采集依据。正常 T 也保留，不能为减少报警改成 U。','','## 36 个本地预定位置','']
    if not local:lines+=['本地采集结果尚未生成。']
    else:
        lines+=['三个环境、UTC/Los_Angeles、L 正常系统变化/A Web 单独修改、前/中/后三阶段；这是三个环境的重复观察，不是 36 台设备。候选和六次拟合已在采集前冻结。','','| 集合 | 位置数 | 单条件输出 |','|---|---:|---|']
        for k,v in s['local'].items():lines.append(f'| {k} | {v["positions"]} | `{json.dumps(v["conditions"],ensure_ascii=False)}` |')
        lines+=['','| 集合/完整模型 | 报警/分母 | F | U | FAILED | EMPTY | 覆盖 |','|---|---:|---:|---:|---:|---:|---|']
        for k in ('confirmed_normal','A_observable','L_system_change'):
            for model,m in s['local'].get(k,{}).get('models',{}).items():lines.append(f'| {k}/{model} | {metrics(m)} |')
        flow=s['local_flow'];trios=flow.get('trios',[])
        lines+=['',f'真实原始记录绑定 {flow.get("raw_bound_positions",0)}/36；确认正常 {flow.get("confirmed_normal_positions",0)}/30 个预定正常位置。三阶段恢复 {sum(t.get("recovery")=="RESTORED" for t in trios)}/{len(trios)} 组。有效Web单独变化 {sum(t.get("observable_intervention") is True for t in trios)}/6；非目标混杂 {sum(t.get("confounded") is True for t in trios)} 组。']
        lines.append('')
        for env in s.get('collection',{}).get('environments',[]):
            lines.append(f'- {env["environment"]}：API {env.get("actual_android_api")}，App {env.get("app_version_name")}，完成 {env.get("raw_records")}/12；原系统设置 `{env.get("original_system_settings",{}).get("timezone_id")}` / auto_time_zone={env.get("original_system_settings",{}).get("auto_time_zone")}，最终恢复 {env.get("final_system_restoration",{}).get("status")}，自有进程退出 {env.get("owned_processes_exited")}。')
        lines+=['','API29/30 实际 WebView 为 91.0.4472.114，API36 为 134.0.6998.135，均在采集前核对。主要非目标原始检测字段没有变化；可用内存、运行时间和网络速率等自然波动保留。CDP额外运行时观察出现过视口瞬态，未进入原始采集屏幕字段，不将其混为检测输入。','', '实际执行、目标字段变化、恢复和非目标变化独立于报警判断；无可观测效应不算检出成功。normal_basis 依据有效观测和操作/撤销证据，不以 phase 单独定正常；失败位置保留。细节见 LOCAL_EVALUATION.json 与 new_batch.jsonl.gz。']
    if local:
        lines[4:4]=['本轮回答：在这批真实采集里，正常系统换时区的6个中间位置，新关系及三个新模型均不报警；仅Web修改的6次有效干预仍全部检出。MTC评价逐折报警从3/261、3/261、1/261降为2/261、2/261、0/261，U均保持14/261；没有增加未知或损失原攻击检出。改善是减少正常时区差异误报，而非提高总攻击检出。', '']
    lines+=['','## 能力边界与后续最小改进','',
        '关系识别的是同次Native地区/日期与Web当前偏移的冲突。同偏移的ID修改、Native与Web一起协调变化不会因此触发；正常系统换时区本身不应当被当作攻击。设备端时区数据库版本未知，可能与固定2026c存在规则差异；进程缓存、采集中途手动改设置也可能造成正常偏离，因此这仍是探索性一致性证据，不是官方攻击不变量。', '',
        '动态地区缺少可靠采集日期、跨转换区间或未知ID时必须U。设备开始/结束时间只能包围读值，不能证明设置在整个范围绝对稳定。若继续完善，最小补采是设备tzdb版本及Native当前有效偏移/读值时间；不需要重采全部MTC或调整本轮阈值。Python TZif解析使用已测试的CPython接口，换运行时须重跑时区边界测试。']
    lines+=['','## 正常依据修正与复现','',
        '上一轮内存实验离线复核24组全部恢复，48/48条确认正常，两条件及六模型各0/48报警，原结果不变。pre 需有效同次观测和正常流程；post 还需成功操作、明确撤销和恢复证据。失败/未恢复不能进入已确认正常分母。复核结果见 MEMORY_NORMAL_REVIEW.md/.json，原报告未覆盖。', '',
        '```bash', 'python3 -B deliverables/timezone_relation_validation_v1/summarize.py',
        '# 复现六次拟合及历史评价，必须新输出目录',
        'python3 -B deliverables/timezone_relation_validation_v1/run_experiment.py run --output-dir /tmp/timezone-reproduce',
        '# 本地采集必须已有 MODELS_FROZEN.json 且只使用本轮自有实例',
        'python3 -B deliverables/timezone_relation_validation_v1/collect.py --output-dir /tmp/timezone-reproduce',
        'python3 -B deliverables/timezone_relation_validation_v1/evaluate_local.py evaluate --output-dir /tmp/timezone-reproduce','```','',
        'summary.json、逐条输出和训练轨迹可复核；报告汇总不训练、不预测、不采集。旧数据、模型、规则和报告保持不变，未提交或推送。']
    lines+=['',f'针对性验证：{s.get("validation",{}).get("tests_passed",0)}项测试通过；6102条保存输出的规则OR与结果一致，3051条B_REL基线原样复用，六模型旧编码器与同折基线一致。测试命令和清理核验见VALIDATION.json；小范围工程修正见ENGINEERING_CORRECTIONS.json，实际拟合6次、采集36条、重拟合/重采均0。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE)
    summarize(p.parse_args().output_dir)
