"""One frozen evaluation. No collection, fitting, tuning or model selection."""
from pathlib import Path
import sys,json,hashlib,datetime
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path[:0]=[str(HERE),str(ROOT)]
import conditions as c
import data as d
from effects import qualify
from hybridguard_agent.research import app177_ablation as ab

def write(p,v):
    Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,rs):Path(p).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rs))
def models():
    found=[]
    for fold,m in d.APP.full_models().items():
        entry=next(x for x in d.read(d.APP.FULL/'models.json')['models'] if x['model_id']==m.model_id)
        found.append(('APP_FULL',fold,m,d.APP.FULL/entry['path']))
    prior=HERE.parent/'app177_core_ablation_v1/results'
    for e in d.read(prior/'models.json')['models']:
        if e['scheme'] in ['A_NO_MEMORY_REL','A_APP_WEB_ONLY'] and e['stage']=='RETENTION':
            m=ab.AppModel.from_dict(d.read(prior/e['path']));assert m.model_id==e['model_id'] and m.binding['fold_id']==e['fold_id'];found.append((e['scheme'],e['fold_id'],m,prior/e['path']))
    assert len(found)==9
    return found

def required_raw_atoms(model):
    return ['UNFITTED_CONTROL:'+a.provenance['field'] if a.orientation=='CONTROL_LE' else a.atom_id for a in model.atoms]

def predict(model,scheme,item):
    raw=item['app'];sid=raw['session_id'] if raw else 'UNAVAILABLE'
    try:
        if not item['record']['binding']['app']:raise ValueError('CURRENT_APP_BINDING_FAILED')
        adapted=d.APP.adapt_raw(raw,sid,'current_app_raw',16,scheme,required=required_raw_atoms(model))
    except (KeyError,TypeError,ValueError) as e:adapted=d.APP.failed(str(e),scheme)
    impl=d.APP.full_engine if scheme=='APP_FULL' else ab
    p=impl.predict_current(model,sid,adapted['raw'])
    return {'model_id':model.model_id,'state':p.get('logical_state') or p['decision'],'decision':p['decision'],'failure_reason':p['failure_reason'],'triggered_rules':[x['clause_id'] for x in p['clause_explanations'] if x['state']=='T'],'rules':p['clause_explanations'],'atoms':p['atom_explanations']}

def run(directory):
    run=Path(directory).resolve();plan=d.read(run/'plan.json');assert len(plan['positions'])==54 and plan['mode']=='formal'
    out=HERE/'results'
    out.mkdir(exist_ok=True)
    if (out/'model_predictions.jsonl').exists():raise FileExistsError('USE_SAVED_SUMMARY')
    if not (out/'MTC_EXECUTION.json').exists():raise ValueError('RUN_MTC_EVALUATION_FIRST')
    frozen=models();refs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for *_,p in frozen}
    relation=ROOT/'hybridguard_agent/research/mtc_resource_relations.py';refs[str(relation.relative_to(ROOT))]=hashlib.sha256(relation.read_bytes()).hexdigest()
    captures=d.capture_records(run);ix={}
    for x in captures:ix.setdefault(x['sample_id'],[]).append(x)
    items={};caps={}
    for s in plan['positions']:
        rows=ix.get(s['sample_id'],[]);cap=rows[0] if len(rows)==1 else None;caps[s['sample_id']]=cap
        items[s['sample_id']]=d.bind(run,plan,s,cap,len(rows)>1)
    positions=[];conditions=[];predictions=[]
    for i,s in enumerate(plan['positions'],1):
        item=items[s['sample_id']];group=[x for x in plan['positions'] if x['scenario_group_id']==s['scenario_group_id']];pre=next(x for x in group if x['phase']=='pre');post=next(x for x in group if x['phase']=='post')
        effect=qualify(s,caps[s['sample_id']],item,items[pre['sample_id']],items[post['sample_id']])
        meta={'sample_id':f'RP{i:03}','scenario':s['scenario'],'round':s['round'],'phase':s['phase'],'identity':effect['identity'],'cohort':'resource54'}
        positions.append({**meta,'effect':effect,'errors':item['errors'],'capture_reference':str((run/'captures.jsonl').relative_to(HERE))+':'+str(i),'times':({'browser_minus_app_payload_seconds':item['times'].get('browser_minus_app_payload_seconds'),'scope':'same ticket/stage, not atomic reads'} if item['times'] else None),'resource_values':{f:item['record']['features'].get(f) for f in d.FIELDS}})
        conditions.extend({**meta,'condition':name,**value} for name,value in c.evaluate(item['record']).items())
        for scheme,fold,m,_ in frozen:predictions.append({**meta,'scheme':scheme,'fold':fold,**predict(m,scheme,item)})
    mtc=d.rows(out/'mtc_conditions.jsonl');members=d.rows(out/'mtc_members.jsonl')
    assert len(conditions)==324 and len(predictions)==486 and len(mtc)==5346
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in refs.items())
    jsonl(out/'positions.jsonl',positions);jsonl(out/'conditions.jsonl',conditions);jsonl(out/'model_predictions.jsonl',predictions)
    write(out/'EXECUTION.json',{'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fit_calls':0,'rule_selection_calls':0,'model_prediction_calls':486,'new_condition_calls':324,'mtc_condition_calls':5346,'mtc_engineering_condition_calls':18 if (out/'engineering/MTC_BINDING_REPAIR.json').exists() else 0,'frozen_files_before_after_unchanged':refs,'models':[{'scheme':s,'fold':f,'model_id':m.model_id,'path':str(p.relative_to(ROOT))} for s,f,m,p in frozen],'normal_basis_status_counts':dict(__import__('collections').Counter(m.get('normal_basis',{}).get('status') for m in members))})
    print(json.dumps({'model_calls':486,'new_condition_calls':324,'mtc_calls':5346,'fit_calls':0}))
def run_mtc():
    out=HERE/'results';out.mkdir(exist_ok=True)
    if (out/'mtc_conditions.jsonl').exists():raise FileExistsError('MTC_ALREADY_EVALUATED')
    mtc=[];members=[]
    for item in d.mtc():
        meta=item['meta'];members.append(meta)
        mtc.extend({'sample_id':meta['sample_id'],'cohort':'mtc','group':meta['group'],'identity':'NORMAL' if meta.get('normal_basis',{}).get('status') =='research_normal_condition_supported' else 'NORMAL_EVIDENCE_RECORDED','condition':name,**value} for name,value in c.evaluate(item['record']).items())
    assert len(mtc)==5346 and len(members)==891
    jsonl(out/'mtc_conditions.jsonl',mtc);jsonl(out/'mtc_members.jsonl',members)
    write(out/'MTC_EXECUTION.json',{'condition_calls':len(mtc),'fit_calls':0,'model_prediction_calls':0,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print('MTC conditions saved: '+str(len(mtc)))

if __name__=='__main__':
    if sys.argv[1]=='mtc':run_mtc()
    else:run(sys.argv[1])
