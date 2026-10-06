"""Saved-results-only recount: no imports of inference, collection, or training."""
import argparse, csv, json
from collections import Counter,defaultdict
from pathlib import Path
IDS=['mtc-rel-tz-6e10284c39b1b601ab406240','mtc-rel-tz-9c5fa0e310ba10a00e520b1c','mtc-rel-tz-4ae67bb9da899cc419dd525f']
CS=['C1','C2','C3','D1','D2']
def state(prediction):return 'FAILED' if prediction['decision']=='FAILED' else prediction.get('logical_state')
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def validate(plan,positions,predictions,conditions):
    ids=[s['sample_id'] for s in plan['positions']]
    if len(ids)!=42 or len(set(ids))!=42:raise ValueError('INVALID_PLAN_POSITIONS')
    expected=set(ids)
    if Counter(r['meta']['sample_id'] for r in positions)!=Counter(ids):raise ValueError('POSITION_MEMBERSHIP_MISMATCH')
    if Counter((r['meta']['sample_id'],r['prediction']['model_id']) for r in predictions)!=Counter((s,m) for s in ids for m in IDS):raise ValueError('MODEL_POSITION_MISMATCH')
    if Counter((r['meta']['sample_id'],r['condition_id']) for r in conditions)!=Counter((s,c) for s in ids for c in CS):raise ValueError('CONDITION_POSITION_MISMATCH')
    lookup={s['sample_id']:s for s in plan['positions']}
    for r in positions+predictions+conditions:
        s=lookup[r['meta']['sample_id']]
        if any(r['meta'][k]!=s[k] for k in ['phase','scenario','round','scenario_group_id']):raise ValueError('SAVED_STAGE_METADATA_MISMATCH')
    for r in predictions:
        if state(r['prediction']) not in ['T','F','U','FAILED']:raise ValueError('INVALID_MODEL_STATE')
    for r in conditions:
        if r['state'] not in ['T','F','U','FAILED']:raise ValueError('INVALID_CONDITION_STATE')
def summarize(directory,output):
    source=Path(directory);out=Path(output);out.mkdir(exist_ok=True,parents=True)
    plan=json.loads((source/'plan.json').read_text());p=rows(source/'positions.jsonl');a=rows(source/'app_predictions.jsonl');c=rows(source/'condition_results.jsonl')
    validate(plan,p,a,c)
    q={r['meta']['sample_id']:r['qualification'] for r in p}
    def subset(identity):return {sid for sid,v in q.items() if v['identity']==identity and v['fully_qualified']}
    groups={'all':set(q),'qualified_normal':subset('NORMAL'),'qualified_intervention':subset('CONTROLLED_INTERVENTION')}
    stats={}
    for name,sids in groups.items():
        stats[name]={'positions':len(sids),'conditions':{cid:dict(Counter(r['state'] for r in c if r['condition_id']==cid and r['meta']['sample_id'] in sids)) for cid in CS},'models':{mid:dict(Counter(state(r['prediction']) for r in a if r['prediction']['model_id']==mid and r['meta']['sample_id'] in sids)) for mid in IDS}}
    scenarios=list(dict.fromkeys(s['scenario'] for s in plan['positions']))
    table=[]
    for sc in scenarios:
        for phase in ['pre','change','post']:
            sids={s['sample_id'] for s in plan['positions'] if s['scenario']==sc and s['phase']==phase}
            table.append({'scenario':sc,'phase':phase,'planned':2,'conditions':{cid:dict(Counter(r['state'] for r in c if r['condition_id']==cid and r['meta']['sample_id'] in sids)) for cid in CS},'models':{mid:dict(Counter(state(r['prediction']) for r in a if r['prediction']['model_id']==mid and r['meta']['sample_id'] in sids)) for mid in IDS}})
    summary={'run_id':plan['run_id'],'planned_positions':42,'app_model_positions':len(a),'condition_positions':len(c),'flow':{'valid_app':sum(not r['app_errors'] for r in p),'valid_browser':sum(not r['browser_errors'] for r in p),'complete_pair':sum(not(r['app_errors']+r['browser_errors']+r['pair_errors']) for r in p),'identity_counts':dict(Counter(v['identity'] for v in q.values())),'fully_qualified':sum(v['fully_qualified'] for v in q.values())},'groups':stats,'by_scenario_phase':table,'fit_calls':0,'source':'Saved positions and results only; no raw reading or inference.'}
    write(out/'summary.json',summary)
    with (out/'condition_states.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['sample_id','scenario','round','phase','condition_id','state','reason','identity','fully_qualified'])
        for r in c:
            m=r['meta'];v=q[m['sample_id']];w.writerow([m['sample_id'],m['scenario'],m['round'],m['phase'],r['condition_id'],r['state'],r['reason'],v['identity'],v['fully_qualified']])
    with (out/'model_states.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['sample_id','scenario','round','phase','model_id','state','failure_reason'])
        for r in a:
            m=r['meta'];v=r['prediction'];w.writerow([m['sample_id'],m['scenario'],m['round'],m['phase'],v['model_id'],state(v),v.get('failure_reason','')])
    def cell(c):return '/'.join(f'{n}{s}' for s,n in c.items()) or '—'
    md=['| 场景 | 阶段（每项2位置） | C1 | C2 | C3 | D1 | D2 | App折01 | App折02 | App折03 |','|---|---|---|---|---|---|---|---|---|---|']
    for r in table:md.append('| '+' | '.join([r['scenario'],r['phase']]+[cell(r['conditions'][i]) for i in CS]+[cell(r['models'][i]) for i in IDS])+' |')
    (out/'scenario_table.md').write_text('\n'.join(md)+'\n')
    print(json.dumps({'flow':summary['flow'],'groups':stats},ensure_ascii=False))
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('evaluation_directory');p.add_argument('--output',required=True);a=p.parse_args();summarize(a.evaluation_directory,a.output)
