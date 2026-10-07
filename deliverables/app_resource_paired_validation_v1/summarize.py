"""Saved-output-only aggregation: no model imports, raw access, network or collection."""
from pathlib import Path
import json,csv,collections,argparse
HERE=Path(__file__).resolve().parent
STATES=('T','F','U','FAILED','EMPTY_MODEL')
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines()]
def write(p,r):Path(p).write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def grouped(rows,keys):
    groups=collections.defaultdict(list)
    for r in rows:groups[tuple(r.get(k) for k in keys)].append(r)
    out=[]
    for key,rs in groups.items():
        count=collections.Counter(r['state'] for r in rs)
        if set(count)-set(STATES):raise ValueError('UNEXPECTED_STATE:'+str(count))
        out.append(dict(zip(keys,key),N=len(rs),**{s:count[s] for s in STATES}))
    return out

def csv_rows(p,rs):
    if not rs:return
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def run(source=None,output=None):
    source=Path(source or HERE/'results');out=Path(output or source/'summary');out.mkdir(exist_ok=True,parents=True)
    cond=rows(source/'conditions.jsonl');models=rows(source/'model_predictions.jsonl');mtc=rows(source/'mtc_conditions.jsonl');positions=rows(source/'positions.jsonl');members=rows(source/'mtc_members.jsonl')
    for rs,n,keys in [(cond,324,['sample_id','condition']),(models,486,['sample_id','scheme','fold']),(mtc,5346,['sample_id','condition']),(positions,54,['sample_id'])]:
        assert len(rs)==n and len({tuple(r[k] for k in keys) for r in rs})==n
    tables={'new_conditions':grouped(cond,['condition','identity']),'scenarios':grouped(cond,['scenario','phase','identity','condition']),
      'models':grouped(models,['scheme','fold','identity']),'model_scenarios':grouped(models,['scheme','fold','scenario','phase','identity']),
      'mtc':grouped(mtc,['condition','group','identity'])}
    for k,rs in tables.items():write(out/(k+'.json'),rs);csv_rows(out/(k+'.csv'),rs)
    index=collections.defaultdict(dict)
    for r in cond:index[r['sample_id']][r['condition']]=r['state']
    intersections=[]
    for endpoint in ['APP','BROWSER']:
        for a,b in [('R_APP_MEMORY','R_WEB_MEMORY_DIFFERENCE'),('D_BROWSER_MEMORY8','R_NATIVE_BROWSER_MEMORY'),('D_BROWSER_MEMORY8','R_WEB_MEMORY_DIFFERENCE')]:
            rs=[p for p in positions if p['phase']=='change' and p['scenario'].startswith('A_'+endpoint) and p['effect']['effective']]
            cells=collections.Counter(('T' if index[p['sample_id']][a]=='T' else index[p['sample_id']][a],index[p['sample_id']][b]) for p in rs)
            intersections.append({'endpoint':endpoint,'condition_a':a,'condition_b':b,'N':len(rs),'states':[{'a':x,'b':y,'count':n} for (x,y),n in cells.items()]})
    write(out/'intersections.json',intersections)
    model_ix=collections.defaultdict(dict)
    for r in models:model_ix[(r['sample_id'],r['fold'])][r['scheme']]=r
    comparisons=[]
    for fold in sorted({r['fold'] for r in models}):
        for scheme in ['A_NO_MEMORY_REL','A_APP_WEB_ONLY']:
            for identity in sorted({p['identity'] for p in positions}):
                selected=[p for p in positions if p['identity']==identity]
                gains=[];losses=[]
                for p in selected:
                    m=model_ix[(p['sample_id'],fold)];a=m['APP_FULL']['state'];b=m[scheme]['state']
                    if a=='T' and b!='T':losses.append(p['sample_id'])
                    if b=='T' and a!='T':gains.append(p['sample_id'])
                comparisons.append({'fold':fold,'scheme':scheme,'identity':identity,'N':len(selected),'additional_alarm_ids':gains,'lost_alarm_ids':losses})
    write(out/'model_vs_full.json',comparisons)
    model_phase=[]
    for scheme,fold in dict.fromkeys((r['scheme'],r['fold']) for r in models):
        for scenario,round_ in dict.fromkeys((p['scenario'],p['round']) for p in positions):
            stages={r['phase']:r for r in models if r['scheme']==scheme and r['fold']==fold and r['scenario']==scenario and r['round']==round_}
            model_phase.append({'scheme':scheme,'fold':fold,'scenario':scenario,'round':round_,'pre':stages['pre']['state'],'change':stages['change']['state'],'post':stages['post']['state'],'new_change_alarm':stages['change']['state']=='T' and stages['pre']['state']=='F' and stages['post']['state']=='F','persistent_alarm':all(stages[x]['state']=='T' for x in ['pre','change','post'])})
    write(out/'model_triplets.json',model_phase);csv_rows(out/'model_triplets.csv',model_phase)

    by_mtc=collections.defaultdict(dict)
    for r in mtc:by_mtc[r['sample_id']][r['condition']]=r
    selected=[]
    for title,predicate in [('normal_reports_4',lambda v:4 in [v.get('app.web_data.navigator_layer.device_memory'),v.get('browser.web_data.navigator_layer.device_memory')]),('normal_reports_16',lambda v:16 in [v.get('app.web_data.navigator_layer.device_memory'),v.get('browser.web_data.navigator_layer.device_memory')]),('normal_web_memory_difference',lambda v:None not in [v.get('app.web_data.navigator_layer.device_memory'),v.get('browser.web_data.navigator_layer.device_memory')] and v.get('app.web_data.navigator_layer.device_memory')!=v.get('browser.web_data.navigator_layer.device_memory'))]:
        examples=[]
        for member in members:
            rs=by_mtc[member['sample_id']];values={k:v for r in rs.values() for k,v in r['operands'].items() if k.endswith(('total_memory_gb','device_memory'))}
            if predicate(values):
                examples.append({'sample_id':member['sample_id'],'group':member['group'],'values':values,'states':{k:r['state'] for k,r in rs.items()},'references':member})
                if len(examples)==3:break
        selected.append({'category':title,'examples':examples,'selection':'first up to3 in original P2 member order; no substitution if absent'})
    write(out/'normal_examples.json',selected)
    intervals=[p['times']['browser_minus_app_payload_seconds'] for p in positions if p.get('times') and isinstance(p['times'].get('browser_minus_app_payload_seconds'),(int,float))]
    summary={'formal_positions':len(positions),'identity_counts':dict(collections.Counter(p['identity'] for p in positions)),'scenario_identity_counts':{s:dict(collections.Counter(p['identity'] for p in positions if p['scenario']==s)) for s in dict.fromkeys(p['scenario'] for p in positions)},'effective_count':sum(p['effect']['effective'] for p in positions),'effective_confounded':sum(p['effect']['effective'] and p['effect']['confounded'] for p in positions),'effective_recovery_unconfirmed':sum(p['effect']['effective'] and (not p['effect']['runtime_restored'] or not p['effect']['resource_returned_to_pre']) for p in positions),'pairs_valid':sum(p['effect'].get('pair_valid',False) for p in positions),'normal_basis_counts':dict(collections.Counter(m.get('normal_basis',{}).get('status') for m in members)),'sampling_interval_seconds':{'N':len(intervals),'min':min(intervals) if intervals else None,'max':max(intervals) if intervals else None},'tables':tables,'intersections':intersections,'model_comparisons':comparisons,'fit_calls':0,'summary_prediction_calls':0,'summary_collection_calls':0,'summary_network_calls':0}
    write(out/'SUMMARY.json',summary);print(json.dumps({k:summary[k] for k in ['formal_positions','identity_counts','effective_count','effective_confounded','pairs_valid']}))
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();run(a.source,a.output)
