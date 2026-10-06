#!/usr/bin/env python3
"""Read-only B2-A inference. No collection/training/formal split capabilities."""
import argparse, copy, csv, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import conditions as cond
from hybridguard_agent.research import mtc_relation_sources as source
from hybridguard_agent.research import timezone_relation_sources as time_source
from hybridguard_agent.research import mtc_timezone_selection as selection
from hybridguard_agent.research import mtc_timezone_candidates as candidates
from hybridguard_agent.research import mtc_reselection_candidates as base
from hybridguard_agent.research import mtc_cap8_data as historical
from hybridguard_agent.research.memory_relation_validation import compiler
from hybridguard_agent.research.manipulation_eval.adapter import adapt_payload
B1=ROOT/'deliverables/browser67_pilot_intake_v1'
P2=ROOT/'hybridguard_agent/artifacts/mtc_p2_frozen_20260922'
MTC=ROOT/'hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final'
RAW=ROOT/'backend_server/collection_backups/mtc_final_20260922/sources'
MODEL=ROOT/'deliverables/timezone_relation_validation_v1'
MODE='PILOT_DIAGNOSTIC_ONLY'
IDS=['mtc-rel-tz-6e10284c39b1b601ab406240','mtc-rel-tz-9c5fa0e310ba10a00e520b1c','mtc-rel-tz-4ae67bb9da899cc419dd525f']
USED={}
READ_ERRORS=[]
def ref(p,n=None):
    p=Path(p).resolve()
    s=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    return s+(':'+str(n) if n else '')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def use(p): USED[ref(p)]=digest(p);return Path(p)
def read(p):return json.loads(use(p).read_text())
def write(p,data):Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,rows):Path(p).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
def rows(p, selected=None):
    """Physical lines, no dropping malformed positions; optional selective decoding."""
    out=[]
    try:
        p=use(p)
        with p.open('rb') as stream:
            for n,line in enumerate(stream,1):
                if selected is not None and n not in selected:continue
                try:
                    r=json.loads(line)
                    if type(r) is not dict:raise ValueError('NOT_OBJECT')
                    out.append((n,r,None))
                except (ValueError,TypeError,UnicodeError) as e:out.append((n,None,type(e).__name__))
    except OSError as e:
        READ_ERRORS.append({'path':ref(p),'error':type(e).__name__})
    return out

def unique(records,key,value):
    found=[(n,r,e) for n,r,e in records if r and r.get(key)==value]
    if len(found)!=1:raise ValueError('MISSING_OR_DUPLICATE_'+key)
    return found[0]

def projection(r):
    if not isinstance(r,dict):raise ValueError('MISSING_PAIR')
    fs=r.get('features');st=r.get('field_status')
    if not isinstance(fs,dict) or not isinstance(st,dict):raise ValueError('INVALID_PAIR_MAPS')
    fields=set(sum(cond.DEPS.values(),[]))
    return {'features':{k:copy.deepcopy(v) for k,v in fs.items() if k in fields},
            'field_status':{k:copy.deepcopy(v) for k,v in st.items() if k in fields},
            'field_quality':{k:r.get('field_quality',{}).get(k,source._quality(k,v,st.get(k))) for k,v in fs.items() if k in fields},'errors':[]}

def capture_times(app,browser,ar,br):
    a=app.get('canonical_received_payload',{});b=browser.get('canonical_received_payload',{})
    at,bt=a.get('timestamp'),b.get('timestamp')
    numeric=lambda x:type(x) in (int,float)
    return {'app':time_source._time_evidence(a,app.get('session_id'),ar),
            'browser_payload_timestamp':bt,'browser_timestamp_source':br+'#canonical_received_payload.timestamp',
            'browser_collection_diagnostics':{k:v for k,v in b.get('collection_diagnostics',{}).items() if k in ('collection_started_at_ms','collection_finished_at_ms','collection_duration_ms')},
            'browser_minus_app_payload_seconds':bt-at if numeric(at) and numeric(bt) else None,
            'scope':'payload timestamps only; not atomic field read; never an App timezone date fallback'}

def bind_v16(raw,sid,reference):
    """New explicit v16 contract; original compiler and timezone cells unchanged."""
    p=raw.get('canonical_received_payload',{});m=p.get('collection_manifest',{})
    if (raw.get('raw_payload_archive_schema_version')!='expanded-raw-payload-v1' or
        raw.get('session_id')!=sid or p.get('session_id')!=sid or not sid or
        m.get('collector_version_code')!=16 or type(m.get('collector_version_code')) is not int or
        m.get('collector_version_name')!='1.6.9-expanded-v2.2-geometry' or
        m.get('web_probe_revision')!='expanded-web-67-v2' or
        m.get('collection_protocol_version')!='featureapp-collection-protocol-v3'):
        raise ValueError('V16_CURRENT_APP_CONTRACT_MISMATCH')
    errors=source._field_sessions(p,sid)
    if errors:raise ValueError(';'.join(errors))
    full=adapt_payload(p)
    bound=source._result({'app_session_id':sid,'session_id':sid,'collector_version_code':16,
        'collector_version_name':m['collector_version_name'],'payload_id':raw.get('payload_sha256'),
        'adapter_version':'pilot-v16-current-app-v1','raw_reference':reference},
        full['features'],full['field_status'],full['field_quality'])
    bound=time_source._attach(bound,raw,reference)
    if bound['status']!='OK':raise ValueError(';'.join(bound['errors']))
    return bound

def compile_app(raw,sid,reference):
    bound=bind_v16(raw,sid,reference)
    c,contract=compiler()
    prepared=c.compile_record(raw['canonical_received_payload'],expected_session_id=sid,
        source_reference=reference,measurement_contract=contract)
    adapted=candidates.extend(base.adapt_controlled(prepared),bound)
    return adapted,bound

def load_models():
    frozen=read(MODEL/'MODELS_FROZEN.json')
    if frozen['status']!='FROZEN' or frozen['new_model_ids']!=IDS:raise ValueError('MODEL_FREEZE_MISMATCH')
    model_index=read(MODEL/'models.json')
    if isinstance(model_index,dict): model_index=model_index.get('models',model_index)
    models=[];manifest=[]
    for i,mid in enumerate(IDS,1):
        fold=f'WEBGL1-LOEO-v1-{i:02}'
        path=MODEL/f'trials/B_REL_TZ__{fold}__RETENTION/model.json';use(path)
        model=selection.load_model(path)
        if model.model_id!=mid or model.binding['fold_id']!=fold:raise ValueError('MODEL_ID_MISMATCH')
        if model.fit['relation_parameters']!=frozen['parameters'] or candidates.parameters()!=frozen['parameters']:raise ValueError('FROZEN_RELATION_PARAMETERS_MISMATCH')
        if not any(r['model_id']==mid and r['stage']=='RETENTION' and r['scheme']=='B_REL_TZ' for r in model_index):raise ValueError('MODEL_INDEX_MISMATCH')
        models.append(model);manifest.append({'model_id':mid,'fold':fold,'stage':'RETENTION','path':ref(path),'sha256':digest(path),'atoms':[a.atom_id for a in model.atoms]})
    return models,manifest

def pilot():
    stages=rows(B1/'local_acceptance/stage_inventory.jsonl');ix=rows(B1/'local_acceptance/paired244_snapshot/sample_index.jsonl')
    paired=rows(B1/'local_acceptance/paired244_snapshot/paired_244.jsonl')
    ap=B1/'evidence_archive/data/raw_expanded_payloads.jsonl';bp=B1/'evidence_archive/data/raw_browser_payloads.jsonl'
    apps=rows(ap);browsers=rows(bp)
    v=read(B1/'evidence_archive/verification.json')
    if v['verification']!='passed' or v['verified_stages']!=18:raise ValueError('B1_VERIFICATION_REQUIRED')
    pub=read(B1/'PUBLICATION.json')
    expected={r['stored_path']:r['sha256'] for r in pub['archive_files']}
    for p in (ap,bp,B1/'evidence_archive/verification.json'):
        if digest(p)!=expected[str(p.relative_to(B1/'evidence_archive'))]:raise ValueError('B1_USED_MEMBER_DIGEST_MISMATCH')
    out=[];counts=Counter(r['sample_id'] for _,r,_ in stages if r)
    for n,s,e in stages:
        sid=s.get('sample_id') if s else f'bad-pilot-line-{n}'
        meta={'sample_id':sid,'cohort':'pilot','group':'normal' if s and s['stage'] in ('clean_pre','clean_post') else s.get('configuration_id','FAILED') if s else 'FAILED',
              'stage':s.get('stage') if s else None,'configuration':s.get('configuration_id') if s else None,'repeat':s.get('repeat') if s else None,
              'evaluation_basis':ref(B1/'local_acceptance/stage_inventory.jsonl',n),'label_scope':'independent B1 verified stage; original labels unchanged'}
        item={'meta':meta,'pair':{'errors':[]},'raw':None,'app_session':None}
        try:
            if e or not s or counts[sid]!=1 or s['stage'] not in ('clean_pre','attack_active','clean_post') or s['pair_binding_checked'] is not True or s['result']!='completed':raise ValueError('INVALID_STAGE_BINDING')
            _,index,_=unique(ix,'sample_id',sid);pn,r,_=unique(paired,'sample_id',sid)
            an,a,_=unique(apps,'session_id',index['app_session_id']);bn,b,_=unique(browsers,'browser_session_id',index['browser_session_id'])
            checks=[a['payload_sha256']==index['app_payload_sha256'],b['browser_payload_sha256']==index['browser_payload_sha256'],
                a['receipt_id']==index['app_receipt_id'],b['app_receipt_id']==a['receipt_id'],b['app_session_id']==a['session_id'],
                b['pair_id']==index['browser_pair_id'],b['canonical_received_payload']['pair_id']==b['pair_id'],
                b['canonical_received_payload']['browser_session_id']==b['browser_session_id'],b['canonical_received_payload']['web_probe_revision']=='expanded-web-67-v2',index['featureapp_version_code']==16]
            if not all(checks):raise ValueError('PILOT_RAW_PAIR_REFERENCE_MISMATCH')
            pair=projection(r);ar,br=ref(ap,an),ref(bp,bn)
            bound=bind_v16(a,index['app_session_id'],ar)
            bfeatures=source._flatten(b['canonical_received_payload']['web_data'],'browser.web_data')
            for field,value in pair['features'].items():
                original=bound['features'] if field.startswith('app.') else bfeatures
                if field not in original or original[field]!=value:raise ValueError('PAIRED_RAW_VALUE_MISMATCH:'+field)
                statuses=bound['field_status'] if field.startswith('app.') else {'browser.'+k:v for k,v in b['canonical_received_payload']['field_statuses'].items()}
                if statuses.get(field)!=pair['field_status'].get(field):raise ValueError('PAIRED_RAW_STATUS_MISMATCH:'+field)
            pair['times']=capture_times(a,b,ar,br)
            meta.update(app_reference=ar,browser_reference=br,pair_reference=ref(B1/'local_acceptance/paired244_snapshot/paired_244.jsonl',pn))
            item.update(pair=pair,raw=a,app_session=index['app_session_id'])
        except (ValueError,KeyError,TypeError) as exc:item['pair']={'errors':[str(exc)]}
        out.append(item)
    if len(out)!=18:raise ValueError('EXPECTED_18_PLANNED_PILOT_POSITIONS')
    return out

def mtc_members():
    registry=rows(P2/'sample_registry.jsonl')
    if any(e for _,_,e in registry):raise ValueError('UNREADABLE_REGISTRY_MEMBERSHIP_NOT_INFERRED')
    members=[(n,r) for n,r,_ in registry if r['analysis_role']=='primary_representative' and r['source_view']=='paired_244']
    if Counter(r['split'] for _,r in members)!=Counter({'discovery':630,'development':144,'reserved_validation':117}):raise ValueError('P2_MEMBERSHIP_COUNTS_CHANGED')
    return members

def mtc(members):
    pp=MTC/'paired_244.jsonl';decoded={n:(r,e) for n,r,e in rows(pp,{r['source_line'] for _,r in members})}
    apps={n:(r,e) for n,r,e in rows(RAW/'raw_expanded_payloads.jsonl',{r['app_raw_line'] for _,r in members})}
    blines={r['source_refs']['browser_raw_line'] for r,e in decoded.values() if r and not e}
    browsers={n:(r,e) for n,r,e in rows(RAW/'raw_browser_payloads.jsonl',blines)}
    batches=rows(RAW/'collection_batches.jsonl');closed={r['collection_batch_id'] for _,r,e in batches if r and r.get('lifecycle_status')=='closed_cleanly'}
    docs=all((ROOT/p).is_file() for p in historical.TASK_REFS)
    for p in historical.TASK_REFS:
        if (ROOT/p).is_file():use(ROOT/p)
    ids=Counter(r['sample_id'] for _,r in members);refs=Counter(r['source_line'] for _,r in members)
    out=[]
    for line,m in members:
        sid=m['sample_id'];meta={'sample_id':sid,'cohort':'mtc','group':m['split'],'evaluation_basis':ref(P2/'sample_registry.jsonl',line),'original_label_status':m['label_status'],'pair_reference':ref(pp,m['source_line'])}
        pair={'errors':[]}
        try:
            if ids[sid]!=1 or refs[m['source_line']]!=1:raise ValueError('DUPLICATE_P2_ID_OR_REFERENCE')
            r,e=decoded.get(m['source_line'],(None,'MISSING_PAIR'))
            if e or not r:raise ValueError(e or 'MISSING_PAIR')
            if r['sample_id']!=sid or r['dataset_view']!='paired_244' or r['record_schema_version']!='hybridguard-mtc-observation-v2':raise ValueError('P2_P1_IDENTITY_MISMATCH')
            if r['source_refs']['app_raw_line']!=m['app_raw_line']:raise ValueError('P2_P1_RAW_REFERENCE_MISMATCH')
            a,ae=apps.get(m['app_raw_line'],(None,'MISSING_APP'))
            bn=r['source_refs']['browser_raw_line'];b,be=browsers.get(bn,(None,'MISSING_BROWSER'))
            if ae or be or not a or not b:raise ValueError(ae or be or 'MISSING_RAW_SIDE')
            for side,raw,key in [('app',a,'payload_sha256'),('browser',b,'browser_payload_sha256')]:
                if r[side]['payload_sha256']!=m[side+'_payload_sha256'] or raw[key]!=m[side+'_payload_sha256']:raise ValueError('MTC_PAYLOAD_REFERENCE_MISMATCH')
            if (a['session_id']!=m['app_session_id'] or r['app']['session_id']!=a['session_id'] or b['app_session_id']!=a['session_id'] or
                b['browser_session_id']!=r['browser']['session_id']):raise ValueError('MTC_SESSION_PAIR_MISMATCH')
            ar,br=ref(RAW/'raw_expanded_payloads.jsonl',m['app_raw_line']),ref(RAW/'raw_browser_payloads.jsonl',bn)
            meta.update(app_reference=ar,browser_reference=br,normal_basis=historical._normal_basis(r,historical._raw_metadata(a),closed,docs,[ar,*historical.TASK_REFS]))
            pair=projection(r);pair['times']=capture_times(a,b,ar,br)
        except (ValueError,KeyError,TypeError) as exc:pair={'errors':[str(exc)]}
        out.append({'meta':meta,'pair':pair})
    return out

def predict_item(item,model):
    meta=item['meta']
    try:
        if item['raw'] is None:raise ValueError('CURRENT_APP_RAW_MISSING')
        adapted,bound=compile_app(item['raw'],item['app_session'],meta['app_reference'])
        result=selection.predict_current(model,meta['sample_id'],adapted['raw'])
        evidence=[]
        for a in model.atoms:
            fields=a.provenance.get('field_refs') or [a.provenance.get('field')]
            fields=[f for f in fields if f]
            evidence.append({'atom_id':a.atom_id,'raw_operands':[{'field':f,'value':bound['features'].get(f),'present':f in bound['features'],'status':bound['field_status'].get(f),'quality':bound['field_quality'].get(f)} for f in fields],
                'relation_diagnostics':adapted['candidate_inputs'].get(a.atom_id,{}).get('diagnostics')})
        result.update(selected_rule_inputs=evidence,acquisition_time=bound['acquisition_time'])
    except (ValueError,KeyError,TypeError,PermissionError) as exc:
        result={'model_id':model.model_id,'decision':'FAILED','logical_state':None,'failure_reason':str(exc)}
    return dict(meta=meta,prediction=result)

def run(output):
    if output.exists():raise FileExistsError('NEW_OUTPUT_DIRECTORY_REQUIRED')
    output.mkdir(parents=True)
    definitions=read(HERE/'CANDIDATES_FROZEN.json')
    if definitions['mode']!=MODE:raise ValueError('DIAGNOSTIC_MODE_REQUIRED')
    models,model_manifest=load_models();members=mtc_members()
    write(output/'MODEL_MANIFEST.json',model_manifest)
    jsonl(output/'MTC_MEMBERS.jsonl',[dict(registry_line=n,**r) for n,r in members])
    ps=pilot();jsonl(output/'PILOT_EVALUATION_SIDECAR.jsonl',[x['meta'] for x in ps])
    predictions=[predict_item(x,m) for m in models for x in ps]
    jsonl(output/'app_predictions.jsonl',predictions)
    pairs=ps+mtc(members)
    results=[dict(meta=x['meta'],**cond.evaluate(cid,x['pair'])) for x in pairs for cid in cond.DEPS]
    jsonl(output/'condition_results.jsonl',results)
    jsonl(output/'failures.jsonl',[{'sample_id':x['meta']['sample_id'],'errors':x['pair']['errors']} for x in pairs if x['pair']['errors']]+[{'sample_id':x['meta']['sample_id'],'model_id':x['prediction']['model_id'],'error':x['prediction'].get('failure_reason')} for x in predictions if x['prediction']['decision']=='FAILED'])
    # Exact metadata dependencies used by the original pure compiler/adapter.
    frozen=ROOT/'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
    contract=frozen/'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol'
    for path in [frozen/'data/definitions.json',contract/'CANDIDATE_LEDGER.jsonl',contract/'SINGLE_SURFACE_FIELDS.json',ROOT/'hybridguard_agent/config/paired244_rule_catalog.v3.json',ROOT/'deliverables/webgl1_fresh_comparison_v1/prepared/DEFINITIONS.json',ROOT/'hybridguard_agent/config/latest_experiment_protocol.v1.json']:
        use(path)
    # Only loaded source modules and metadata contracts, not an exhaustive repo scan.
    for module in list(sys.modules.values()):
        p=getattr(module,'__file__',None)
        if p and Path(p).suffix=='.py' and Path(p).resolve().is_relative_to(ROOT):use(Path(p))
    for p in [ROOT/'web_probe/canonical_web_probe.js',HERE/'SOURCES.md',B1/'local_acceptance/experiment_plan/experiment_readiness.json',ROOT/'RBA_SUPERVISOR_REPORT.md',ROOT/'RBA_PRE_PAPER_EXPERIMENT_PLAN.md']:
        use(p)
    for path,sha in USED.items():
        if digest(ROOT/path)!=sha:raise ValueError('USED_INPUT_CHANGED:'+path)
    write(output/'RUN_MANIFEST.json',{'mode':MODE,'fit_calls':0,'new_collection_calls':0,'app_prediction_calls':len(predictions),'condition_calls':len(results),'planned_pairs':len(pairs),'original_formal_permissions_unchanged':True,'input_and_loaded_dependency_sha256':USED,'source_read_errors':READ_ERRORS,'normal_basis_counts':dict(Counter(x['meta'].get('normal_basis',{}).get('status','missing') for x in pairs if x['meta']['cohort']=='mtc'))})
    summarize(output)

def summarize(output):
    saved_a=rows(output/'app_predictions.jsonl');saved_c=rows(output/'condition_results.jsonl')
    if any(e or r is None for _,r,e in saved_a+saved_c):raise ValueError('UNREADABLE_SAVED_OUTPUT')
    predictions=[r for _,r,e in saved_a];results=[r for _,r,e in saved_c]
    if len(predictions)!=54 or len(results)!=4545:raise ValueError('SAVED_OUTPUT_DENOMINATORS_CHANGED')
    tables=[]
    for kind,records,key,st in [('model',predictions,lambda x:x['prediction']['model_id'],lambda x: {'MANIPULATION_ALERT':'T','NO_ALERT':'F','INSUFFICIENT_EVIDENCE':'U'}.get(x['prediction']['decision'],'FAILED')),('condition',results,lambda x:x['condition_id'],lambda x:x['state'])]:
        groups=defaultdict(Counter)
        for r in records:groups[(key(r),r['meta']['cohort'],r['meta']['group'])][st(r)]+=1
        for (name,cohort,group),c in sorted(groups.items()):
            n=sum(c.values());ev=c['T']+c['F'];tables.append(dict(kind=kind,id=name,cohort=cohort,group=group,n=n,**{s:c[s] for s in ('T','F','U','FAILED')},evaluable_fraction=f'{ev}/{n}',deviation_per_planned=f'{c["T"]}/{n}',deviation_per_evaluable=f'{c["T"]}/{ev}'))
    write(output/'SUMMARY.json',tables)
    with (output/'SUMMARY.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(tables[0]));w.writeheader();w.writerows(tables)
    trajectories=defaultdict(dict)
    for r in predictions:
        m=r['meta'];trajectories[(r['prediction']['model_id'],m['configuration'],m['repeat'])][m['stage']]={'sample_id':m['sample_id'],'decision':r['prediction']['decision'],'triggered_clauses':[c['clause_id'] for c in r['prediction'].get('clause_explanations',[]) if c['state']=='T']}
    write(output/'TRAJECTORIES.json',[{'model_id':k[0],'configuration':k[1],'repeat':k[2],'stages':v} for k,v in sorted(trajectories.items())])
    bypair=defaultdict(dict)
    for r in results:bypair[r['meta']['sample_id']][r['condition_id']]=r
    examples=defaultdict(list)
    for sid,rs in sorted(bypair.items()):
        m=rs['C1']['meta'];cats=[]
        if m['group']=='normal' and rs['D1']['state']=='T' and rs['C2']['state']=='F':cats.append('normal_list_diff_preferred_same')
        if m['cohort']=='pilot' and m['group'] in ('language_fr','timezone_tokyo'):cats.append('browser_intervention')
        if m['cohort']=='mtc' and any(rs[c]['state']=='T' for c in ('C1','C2','C3')):cats.append('mtc_normal_deviation')
        if any(x['state'] in ('U','FAILED') for x in rs.values()):cats.append('insufficient_input_or_semantics')
        for c in cats:
            if len(examples[c])<3:examples[c].append({'sample_id':sid,'rows':list(rs.values())})
    for r in sorted(predictions,key=lambda r:(r['meta']['sample_id'],r['prediction']['model_id'])):
        if r['meta']['group']=='normal' and r['prediction']['decision']=='MANIPULATION_ALERT' and len(examples['app_normal_alert'])<3:examples['app_normal_alert'].append(r)
    write(output/'EXAMPLES.json',dict(examples))
    overlap=[]
    for model in IDS:
        for cid in ('C1','C2','C3'):
            c=Counter()
            for r in predictions:
                if r['prediction']['model_id']==model and bypair[r['meta']['sample_id']][cid]['state']=='T':c[r['prediction']['decision']]+=1
            overlap.append({'model_id':model,'condition':cid,'candidate_T_model_decisions':dict(c)})
    write(output/'OVERLAP.json',overlap)
    print(json.dumps({'models':len(predictions),'conditions':len(results),'summary':str(output/'SUMMARY.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['run','summarize']);parser.add_argument('--output',type=Path,default=HERE/'results');args=parser.parse_args()
    if args.command=='run':run(args.output)
    else:summarize(args.output)
