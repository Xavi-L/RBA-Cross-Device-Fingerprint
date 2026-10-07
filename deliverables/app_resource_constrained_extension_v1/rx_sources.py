"""Narrow adapters to unchanged readers; private identities never leave local mappings."""
import sys, importlib.util, hashlib, gzip
from functools import lru_cache
from types import SimpleNamespace
from collections import Counter
from rx_common import *
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
@lru_cache(maxsize=1)
def legacy():
    original_path=sys.path[:];saved={k:sys.modules.get(k) for k in ('conditions','data','effects','common','adapter')}
    try:
        c1=module('rx_c1',HERE.parent/'browser67_cross_endpoint_diagnostic_v1/conditions.py')
        sys.modules['conditions']=c1
        matched=module('rx_matched',HERE.parent/'cross_endpoint_matched_controls_v1/evaluate.py')
        rc=module('rx_resource_conditions',RESOURCE/'conditions.py');sys.modules['conditions']=rc
        rd=module('rx_resource_data',RESOURCE/'data.py');sys.modules['data']=rd
        sys.modules['effects']=module('rx_resource_effects',RESOURCE/'effects.py')
        re=module('rx_resource_evaluate',RESOURCE/'evaluate.py')
        sys.modules['common']=module('rx_legacy_common',OLD/'common.py')
        sys.modules['adapter']=SimpleNamespace(b2a=matched.b2,b2b=matched)
        prep=module('rx_legacy_prep',OLD/'prepare_current.py')
        # Source binding is retained. Avoid repeated whole-archive digests in read helpers.
        matched.b2.use=lambda p:Path(p)
        return SimpleNamespace(c1=c1,rc=rc,rd=rd,re=re,b2=matched.b2,matched=matched,prep=prep)
    finally:
        sys.path[:]=original_path
        for k,v in saved.items():
            if v is None:sys.modules.pop(k,None)
            else:sys.modules[k]=v
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
@lru_cache(maxsize=16)
def physical_rows(path):
    p=ROOT/path
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else p.open()) as f:return [__import__('json').loads(line) for line in f]
def physical(ref):
    p,n=ref.rsplit(':',1);require(int(n)>0,'INVALID_PHYSICAL_LINE');return physical_rows(p)[int(n)-1]
def freeze_models():
    bases=read(OLD/'results/models.json');require(len(bases)==3,'EXACT_THREE_BASES')
    index(bases,lambda m:m['model_id']);full=legacy().rd.APP.full_models();locks={}
    for b in bases:
        app=full[b['base']['fold']];p=ROOT/b['base']['path'];raw=read(p)
        require(b['extensions']==['C1'] and b['status']=='SELECTED_EXTENSION','NOT_B2C_MAIN_C1')
        require(app.model_id==b['base_model_id']==b['base']['model_id'],'BASE_ID_MISMATCH')
        require(digest(p)==b['base']['sha256'],'FROZEN_APP_CHANGED')
        require(raw['clauses']==b['base']['clauses'],'BASE_CLAUSES_CHANGED')
        ep=legacy().b2.MODEL/'folds'/b['base']['fold']/'encoder.json'
        require(raw['encoder']==read(ep) and digest(ep)==b['base']['encoder_sha256'],'ENCODER_CHANGED')
        require(b['rule_count']==len(raw['clauses'])+1 and b['complexity']==len(raw['clauses'])+sum(len(c['literals']) for c in raw['clauses'])+2,'BASE_CAPACITY_CHANGED')
        cp=ROOT/b['condition_source']['path'];require(digest(cp)==b['condition_source']['sha256'],'C1_VERSION_CHANGED')
        require(read(OLD/'results'/f"{b['model_id']}.json")==b,'BASE_INDEX_FILE_MISMATCH')
        for f in (p,ep,cp,OLD/'results'/f"{b['model_id']}.json"):locks[str(f.relative_to(ROOT))]=digest(f)
    for f in (RESOURCE/'conditions.py',ROOT/'hybridguard_agent/research/mtc_resource_relations.py'):
        locks[str(f.relative_to(ROOT))]=digest(f)
    return bases,locks
def old_members():
    ms=rows(OLD/'results/members.jsonl');ix=index(ms);l=legacy()
    registry={r['sample_id']:(n,r) for n,r in l.b2.mtc_members()}
    require(set(registry)=={m['sample_id'] for m in ms if m['cohort'].startswith('mtc_')},'EXACT_P2_MEMBERS')
    for sid,(n,r) in registry.items():
        m=ix[sid];meta=m['source_meta']
        require(m['cohort']=='mtc_'+r['split'] and m['identity']=='NORMAL','MTC_GROUP_OR_IDENTITY')
        require(m['role']==('selection' if r['split']=='discovery' else 'historical_evaluation'),'MTC_ROLE')
        require(meta['evaluation_basis']==l.b2.ref(l.b2.P2/'sample_registry.jsonl',n),'P2_REFERENCE_CHANGED')
        require(meta['app_reference']==l.b2.ref(l.b2.RAW/'raw_expanded_payloads.jsonl',r['app_raw_line']) and meta['pair_reference']==l.b2.ref(l.b2.MTC/'paired_244.jsonl',r['source_line']),'P2_PHYSICAL_BINDING_CHANGED')
    stages=rows(l.b2.B1/'local_acceptance/stage_inventory.jsonl')
    require({r['sample_id'] for r in stages}=={m['sample_id'] for m in ms if m['cohort']=='pilot18'},'EXACT_PILOT_MEMBERS')
    for r in stages:
        m=ix[r['sample_id']];require(m['phase']==r['stage'] and m['scenario']==r['configuration_id'],'PILOT_STAGE_CHANGED')
        require(m['identity']==('EFFECTIVE_INTERVENTION' if r['stage']=='attack_active' else 'NORMAL'),'PILOT_IDENTITY_CHANGED')
    plan=read(l.matched.HERE/'PLAN.json');selection=read(l.matched.HERE/'ATTEMPT_SELECTION.json')
    pp=index(rows(l.matched.HERE/'private_runs/formal01/evaluation/positions.jsonl'),lambda r:r['meta']['sample_id'])
    require({s['sample_id'] for s in plan['positions']}=={m['sample_id'] for m in ms if m['cohort']=='b2b42'},'EXACT_MATCHED_MEMBERS')
    for s in plan['positions']:
        m=ix[s['sample_id']];meta=m['source_meta'];pos=pp[s['sample_id']]
        require(all(meta[k]==s[k] for k in ('sample_id','scenario','phase','round')),'MATCHED_STAGE_CHANGED')
        run=selection['replacement_run'] if s['sample_id'] in selection['replacement_sample_ids'] else selection['original_run']
        require(meta['source_run']==run and meta==pos['meta'],'MATCHED_ATTEMPT_CHANGED')
        q=pos['qualification'];expected='NORMAL' if q['identity']=='NORMAL' else 'EFFECTIVE_INTERVENTION' if q['identity']=='CONTROLLED_INTERVENTION' and q['operation_effect']=='OBSERVED_CHANGE' else 'UNCONFIRMED'
        require(m['identity']==expected,'MATCHED_IDENTITY_CHANGED')
    require(len(ms)==951,'OLD_951');return ms
@lru_cache(maxsize=1)
def resource_bound():
    l=legacy();run=RESOURCE/'private_runs/formal01';plan=read(run/'plan.json')
    slots=index(plan['positions']);caps=index(l.rd.capture_records(run))
    require(set(slots)==set(caps),'RESOURCE_CAPTURE_IDS')
    # Match immutable scenario/round/phase first, then validate raw references and all stage IDs.
    by_key=index(list(slots.values()),lambda s:(s['scenario'],s['round'],s['phase']))
    result={};mapping=[]
    for p in rows(RESOURCE/'results/positions.jsonl'):
        key=(p['scenario'],p['round'],p['phase']);s=by_key[key];cap=caps[s['sample_id']]
        require(all(cap[k]==s[k] for k in ('sample_id','capture_id','scenario_group_id','runtime_context','collection_round')),'RESOURCE_PLAN_CAPTURE_IDENTITY')
        refpath,n=p['capture_reference'].rsplit(':',1)
        require(read_capture(RESOURCE/refpath,int(n))==next(c for c in rows(run/'captures.jsonl') if c['sample_id']==s['sample_id']),'RESOURCE_ALIAS_CAPTURE_REFERENCE')
        item=l.rd.bind(run,plan,s,cap)
        require(all(item['record']['binding'][k] for k in ('app','browser','pair')),'RESOURCE_RAW_BINDING')
        require(p['resource_values']=={f:item['record']['features'].get(f) for f in l.rd.FIELDS},'RESOURCE_VALUES_CHANGED')
        sid='resource54:'+p['sample_id'];result[sid]=(p,s,cap,item)
        mapping.append(dict(sample_id=sid,actual_sample_id=s['sample_id'],capture_id=cap['capture_id'],references=cap['archives']))
    require(len(result)==54 and len(by_key)==54,'RESOURCE_EXACT_MATRIX')
    return result,mapping
def read_capture(path,line):return rows(path)[line-1]
def raw_v16(member):
    l=legacy()
    if member['cohort']=='resource54':
        p,s,cap,item=resource_bound()[0][member['sample_id']]
        return item['app'],item['browser'],l.rd.raw_ref(RESOURCE/'private_runs/formal01',cap['archives']['provenance'],'browser_pair_provenance.jsonl')
    meta=member['source_meta'];a=physical(meta['app_reference']);b=physical(meta['browser_reference'])
    if member['cohort']=='b2b42':p=physical(meta['provenance_reference'])
    else:
        matches=[p for p in rows(l.b2.B1/'evidence_archive/data/browser_pair_provenance.jsonl') if p.get('pair_id')==b['pair_id']]
        require(len(matches)==1,'PILOT_PROVENANCE_UNIQUE');p=matches[0]
    return a,b,p
def prepare_v16(app,browser,provenance):
    l=legacy();errors={s:[] for s in ('app','browser','pair')}
    try:l.b2.bind_v16(app,app['session_id'],'current-app')
    except (KeyError,TypeError,ValueError) as e:errors['app'].append(str(e))
    try:
        l.b2.check_browser(browser,sid=browser['browser_session_id'],pair_id=browser['pair_id'],app_sid=browser['app_session_id'],revision='expanded-web-67-v2',batch=browser['collection_batch_id'])
    except (KeyError,TypeError,ValueError) as e:errors['browser'].append(str(e))
    try:
        require(provenance['pair_status']=='completed','PAIR_INCOMPLETE')
        for k in ('app_session_id','browser_session_id','pair_id','browser_receipt_id','browser_payload_sha256','app_receipt_id','collection_batch_id'):
            require(provenance[k]==browser[k],'PAIR_BROWSER:'+k)
        for k,ak in [('app_session_id','session_id'),('app_receipt_id','receipt_id'),('app_payload_sha256','payload_sha256'),('collection_batch_id','collection_batch_id')]:
            require(provenance[k]==app[ak],'PAIR_APP:'+k)
    except (KeyError,TypeError,ValueError) as e:errors['pair'].append(str(e))
    valid_a=app if not errors['app'] else None;valid_b=browser if not errors['browser'] else None
    r=l.rd.project(valid_a,valid_b);r['binding']={s:not errors[s] for s in errors}
    r['binding']['pair']=all(not e for e in errors.values());r['binding']['app_session_id']=app.get('session_id') if app else None
    pair=l.matched.project(valid_a,valid_b);pair['errors']=sum(errors.values(),[])
    pair={**{k:{f:v for f,v in pair[k].items() if f in l.c1.DEPS['C1']} for k in ('features','field_status','field_quality')},'errors':pair['errors']}
    return dict(app=valid_a,record=r,pair=pair,errors=errors)
