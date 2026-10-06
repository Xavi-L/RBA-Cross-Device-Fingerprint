"""Directed pairing inventory, not another detector or a collection command."""
from collections import Counter,defaultdict
import csv,json
from pathlib import Path
from data import ROOT,HERE,records,read,raw_at,settings


def build(out):
    members=[r['value'] for r in records(out/'members.jsonl')]
    s=settings();registry=[r['value'] for r in records(ROOT/s['mtc_p2_registry'])]
    mtc_by_session=defaultdict(list)
    for r in registry:mtc_by_session[r.get('app_session_id')].append(r)
    known_pairs={}
    for m in members:
        if m['cohort']=='paired60':
            raw=raw_at(m['raw_reference']);known_pairs[raw['session_id']]=m
    checks={};rows=[];details=[]
    for cohort in ['controlled','memory','timezone','screen','paired60']:
        scenarios=sorted({m['scenario'] for m in members if m['cohort']==cohort})
        for scenario in scenarios:
            selected=[m for m in members if m['cohort']==cohort and m['scenario']==scenario]
            paired=[];refs=[]
            for m in selected:
                raw=raw_at(m['raw_reference']);sid=raw['session_id'];backend=Path(m['raw_reference'].rsplit(':',1)[0]).parent
                directory=str(backend)
                if directory not in checks:
                    files=sorted(p.name for p in (ROOT/backend).iterdir())
                    checks[directory]={'files':files,'raw_browser_present':'raw_browser_payloads.jsonl' in files,'provenance_present':'browser_pair_provenance.jsonl' in files}
                pair=known_pairs.get(sid);legacy=mtc_by_session.get(sid,[])
                # MTC sessions are indexed for a potential exact match only.
                # Normal Browser records never fill an unrelated old attack position.
                if legacy and not pair:raise ValueError('UNEXPECTED_REUSABLE_MTC_SESSION_REQUIRES_REVIEW:'+sid)
                if pair:paired.append(m)
                d={'sample_id':m['sample_id'],'cohort':cohort,'scenario':scenario,'phase':m['phase'],'app_reference':m['raw_reference'],
                   'browser_reference':pair.get('browser_reference') if pair else None,'pair_reference':pair.get('pair_reference') if pair else None,
                   'mtc_exact_app_session_matches':len(legacy),'status':'COMPLETE_EXISTING_PAIR' if pair else 'MISSING_BROWSER_IN_REFERENCED_RUN_AND_KNOWN_PAIR_INDEX'}
                details.append(d);refs.append(m['source_reference'])
            groups=defaultdict(list)
            for m in paired:groups[m['group_id']].append(m)
            triples=sum(len(g)==3 and len({m['phase'] for m in g})==3 for g in groups.values())
            status='EXISTING_PAIRED_LANGUAGE_TIMEZONE_ONLY' if paired else 'APP_ONLY_EXISTING_MATERIAL'
            rows.append({'cohort':cohort,'scenario':scenario,'app_records':len(selected),'same_stage_browser_records':len(paired),
                'complete_pairs':len(paired),'complete_three_stage_groups':triples,'normal_records':sum(m['identity']=='NORMAL' for m in selected),
                'effective_interventions':sum(m['identity']=='EFFECTIVE_INTERVENTION' for m in selected),
                'no_observable_effect':sum(m['identity']=='NO_OBSERVABLE_EFFECT' for m in selected),
                'affected_endpoint':','.join(sorted({m.get('affected_endpoint') or 'unknown' for m in selected})),
                'comparison':'App-only component comparison; local paired language/timezone reference also available' if paired else 'App-only/current-App-internal component comparison',
                'status':status,'evidence_refs':';'.join(refs)})
    dest=HERE/'PAIRED_COVERAGE.csv'
    with dest.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'pairing_positions.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in details))
    (out/'PAIRING_SOURCE_CHECKS.json').write_text(json.dumps({'targeted_run_directories':checks,'exact_session_index':s['mtc_p2_registry'],
        'known_small_pair_index':'deliverables/cross_endpoint_constrained_extension_v1/results/members.jsonl',
        'scope':'Referenced App runs and known frozen pairing indexes only; no conjectured pairing or repository-wide audit',
        'rows':rows},ensure_ascii=False,indent=2)+'\n')
    lines=['# App参与双端检测的覆盖与剩余证据','',
        '本表按原App成员的实际raw引用定向检查其backend文件目录，并用完整App session精确匹配已知P2与60条双端索引。',
        '原378条及180条专项引用的12个backend目录均没有独立Browser raw或配对provenance文件，且在已知配对索引中无相同App session。',
        '因此这些已保存成员不能做同阶段双端比较；这不是根据“旧实验”名称推断，也不是断言全仓不存在其他未索引材料。MTC正常配对不能填补受控攻击的Browser缺项。','',
        '|材料|App位置|同阶段Browser|完整配对|完整三阶段组|正常|有效干预|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f"|{r['cohort']} / {r['scenario']}|{r['app_records']}|{r['same_stage_browser_records']}|{r['complete_pairs']}|{r['complete_three_stage_groups']}|{r['normal_records']}|{r['effective_interventions']}|")
    lines+=['','逐位置的真实文件与物理行号见 [pairing_positions.jsonl](results/pairing_positions.jsonl)；机器表见 [CSV](PAIRED_COVERAGE.csv)。',
        '', '## 三条证据线', '',
        '- App单端／内部跨层：本轮378条主体与专项统一回放、四项重选消融、小树对照，见REPORT。',
        '- App↔独立Browser语言／时区：既有18先导＋42匹配对照共60条，20组三阶段；4次App干预、10次Browser干预、46条正常。此前局部四视图与C1/C2实验保留。本轮只补App模型回放。',
        '- 其他App攻击配置的跨端贡献：原App受控及内存／屏幕专项缺少同阶段Browser与完整配对；本轮不能声称其双端组件消融已完成。',
        '', '## 最小下一轮：一个有针对性的配对补证批次（尚未授权采集）','',
        '优先只补 **w9-rule-boundary-cdp-resource-pair-v1＋memory_4GiB** 的真实App与独立Browser三阶段配对。前者覆盖旧CPU/内存联合修改，后者隔离App Web内存修改，最适合区分“App内部Native参照”与“未被修改的独立Browser参照”。先在一个已用环境、每配置3次重复完成同一组pre／change／post双端输入，并加匹配的无干预三阶段对照；无需重采378条。',
        '要论证App作为参照端，再在同一批次安排与这些字段相对应的Browser侧单端修改，并验证实际变化。若Browser不提供有效内存观测，保留U/无效尝试，不用另一端数值补齐。',
        '本方案缺的首先是上述阶段的真实配对输入；配对齐备后还需单独冻结可适用的跨端候选与同成员方法对照。当前C1/C2只覆盖语言/时区，不能直接代表资源跨端方法。',
        'UA、屏幕、webdriver、WebGL及其余工具配置仍在覆盖表中保留缺项。若论文要对它们作跨端有效性主张，需要相应后续证据；最小资源批次不自动关闭这些缺口。']
    (HERE/'PAIRED_COVERAGE.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':build(HERE/'results')
