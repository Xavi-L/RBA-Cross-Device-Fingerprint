"""Narrow read-only adapters for the three authorized cohorts; no collection."""
import collections, importlib.util, sys
from common import *
sys.dont_write_bytecode=True

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
b2b=module('b2c_original_b2b',HERE.parent/'cross_endpoint_matched_controls_v1/evaluate.py')
b2a=b2b.b2
b2b_summary=module('b2c_original_b2b_summary',b2b.HERE/'summarize.py')
B2A=b2a.HERE/'results'; B2B=b2b.HERE/'private_runs/formal01/evaluation'
USED={}
AUDIT=collections.Counter()

def use(path):
    key=ref(path)
    if key not in USED: USED[key]=digest(path)
    return Path(path)

def freeze():
    locks=read(use(b2b.HERE/'FROZEN.json'))['files']
    for path,sha in locks.items(): require(digest(use(ROOT/path))==sha,'B2B_FREEZE_CHANGED:'+path)
    models,manifest=b2a.load_models()
    index=read(use(b2a.MODEL/'models.json'))['models']
    prior=read(ROOT/'deliverables/mtc_relation_extension_v1/models.json')['models']
    for model,m in zip(models,manifest):
        path=use(ROOT/m['path']); stored=read(path)
        fold=model.binding['fold_id']; entry=next(r for r in index if r['model_id']==model.model_id)
        require(entry['stage']=='RETENTION' and entry['selected_clauses']==stored['clauses'],'INDEX_RULE_MISMATCH')
        require(read(use(b2a.MODEL/'folds'/fold/'encoder.json'))==stored['encoder'],'ENCODER_MISMATCH')
        old=next(r for r in prior if r['fold_id']==fold and r['stage']=='RETENTION')
        require(read(use(ROOT/'deliverables/mtc_relation_extension_v1'/old['path']))['encoder']==stored['encoder'],'HISTORICAL_ENCODER_CHANGED')
        require(stored['complexity']['objective_complexity']==len(stored['clauses'])+sum(len(c['literals']) for c in stored['clauses']),'COMPLEXITY_UNIT_CHANGED')
        m.update(rule_count=len(stored['clauses']),complexity=stored['complexity']['objective_complexity'],clauses=stored['clauses'],encoder_sha256=digest(b2a.MODEL/'folds'/fold/'encoder.json'))
    reviewed=read(use(b2a.HERE/'review_20261006/RESULT_COMPARISON.json'))
    for name in ('app_predictions.jsonl','condition_results.jsonl'):
        require(digest(use(B2A/name))==reviewed[name]['after_sha256'],'B2A_REVIEW_OUTPUT_CHANGED')
    old_manifest=read(use(B2A/'RUN_MANIFEST.json'))['input_and_loaded_dependency_sha256']
    # Current parsers/relations and model source must match the already reviewed execution.
    for p,sha in old_manifest.items():
        if p.endswith('.py') or p.endswith('/model.json'):
            require(digest(use(ROOT/p))==sha,'REVIEWED_IMPLEMENTATION_CHANGED:'+p)
    use(b2a.MODEL/'predictions.jsonl.gz');use(HERE/'PROTOCOL.md')
    for name in ('PLAN.json','ATTEMPT_SELECTION.json','ENVIRONMENT.json'): use(b2b.HERE/name)
    return models,manifest

def check_conditions(saved,pair):
    """Check exact current operands/statuses/quality against saved versioned output."""
    for cid,r in saved.items():
        require(cid in ('C1','C2') and r['state'] in STATES,'CANDIDATE_STATE')
        expected=[dict(field=k,present=k in pair['features'],value=pair['features'].get(k),
            status=pair['field_status'].get(k),quality=pair['field_quality'].get(k)) for k in b2a.cond.DEPS[cid]]
        require(r['operands']==expected,'SAVED_OPERANDS_CHANGED:'+cid)
        require(not pair.get('errors'), 'CURRENT_PAIR_BINDING_FAILED')
        AUDIT['validated_saved_condition_states']+=1

def check_base(pred,model,sid):
    require(pred['model_id']==model.model_id,'PREDICTION_MODEL_ID')
    rules=pred.get('rules',pred.get('clause_explanations',[]))
    require([r['clause_id'] for r in rules]==[c.id for c in model.clauses],'PREDICTION_RULES_CHANGED')
    s=state(pred)
    if s!='FAILED':
        ss=[r['state'] for r in rules]
        require(all(v in ('T','F','U') for v in ss),'SAVED_RULE_STATE')
        require(s==('T' if 'T' in ss else 'U' if 'U' in ss else 'F'),'SAVED_BASE_OR_MISMATCH')
    AUDIT['validated_saved_base_states']+=1
    return s

def qualify(position,cap):
    """Current identity/effect and recovery are independent, including future failures."""
    q=position['qualification']; meta=position['meta']
    normal=q.get('identity')=='NORMAL'
    # Original pre/post qualifier included restoration in identity. Use contemporaneous
    # operation evidence when that old gate alone would withhold a current normal identity.
    intended=meta['scenario'].startswith('L_') or meta['phase']!='change'
    if intended and cap:
        pristine=all(cap.get(e+'_before',{}).get(k) is False for e in ('app','browser') for k in ('languageHasOwn','languagesHasOwn'))
        setting=cap.get('setting',{}); env=setting.get('after',{})
        normal_operation=setting.get('status')=='EXECUTED' if meta['phase']=='change' else setting.get('status') in ('NOT_NEEDED','EXECUTED') and env.get('locale')=='en-US' and env.get('timezone')=='Asia/Shanghai'
        if normal_operation and pristine and cap.get('control_installed') is False: normal=True
    effective=q.get('identity')=='CONTROLLED_INTERVENTION' and q.get('operation_effect')=='OBSERVED_CHANGE'
    identity='NORMAL' if normal else 'EFFECTIVE_INTERVENTION' if effective else 'UNCONFIRMED'
    return dict(identity=identity,normal_identity_supported=normal,intervention_effect_confirmed=effective,
        operation_effect=q.get('operation_effect','UNKNOWN'),runtime_restored=q.get('runtime_restored'),
        full_recovery_qualified=q.get('fully_qualified') is True,identity_reasons=q.get('reasons',[]),
        app_input_available=not position['app_errors'],browser_input_available=not position['browser_errors'],
        pair_binding_available=not position['pair_errors'],source_identity=q.get('identity'))

def small_cohorts(models):
    members=[]; inputs=[]
    old_a=rows(use(B2A/'app_predictions.jsonl'));old_c=rows(use(B2A/'condition_results.jsonl'))
    pa=unique(old_a,lambda r:(r['meta']['sample_id'],r['prediction']['model_id']))
    pc=unique([r for r in old_c if r['meta']['cohort']=='pilot' and r['condition_id'] in ('C1','C2')],lambda r:(r['meta']['sample_id'],r['condition_id']))
    ps=b2a.pilot(); require(len(ps)==18,'PILOT_SIZE')
    for item in ps:
        meta=item['meta'];sid=meta['sample_id'];cond={c:pc[sid,c] for c in ('C1','C2')}
        require(all(r['meta']==meta for r in cond.values()),'PILOT_SIDECAR_CHANGED')
        check_conditions(cond,item['pair'])
        base={m.model_id:check_base(pa[sid,m.model_id]['prediction'],m,sid) for m in models}
        normal=meta['stage']!='attack_active'
        members.append(dict(sample_id=sid,cohort='pilot18',role='selection',identity='NORMAL' if normal else 'EFFECTIVE_INTERVENTION',
            normal_identity_supported=normal,intervention_effect_confirmed=not normal,
            operation_effect='OBSERVED_CHANGE' if not normal else 'NO_TARGET_MODIFICATION',runtime_restored=True,full_recovery_qualified=True,
            app_input_available=item['raw'] is not None,browser_input_available=not item['pair']['errors'],pair_binding_available=not item['pair']['errors'],
            family='Browser_language' if meta['configuration']=='language_fr' else 'Browser_timezone',
            scenario=meta['configuration'],phase=meta['stage'],group_id=f"pilot18:{meta['configuration']}:{meta['repeat']}",
            environment='B1_API36_x86_64_Chrome133',source_label_scope='candidate/run-scoped; original formal permissions unchanged',source_meta=meta))
        inputs.append(dict(sample_id=sid,base_states=base,conditions={c:r['state'] for c,r in cond.items()},
            references={'base':{m.model_id:ref(B2A/'app_predictions.jsonl',old_a.index(pa[sid,m.model_id])+1) for m in models},
            'conditions':{c:ref(B2A/'condition_results.jsonl',old_c.index(r)+1) for c,r in cond.items()}}))
    plan=read(use(B2B/'plan.json')); pp=rows(use(B2B/'positions.jsonl')); aa=rows(use(B2B/'app_predictions.jsonl'));cc=rows(use(B2B/'condition_results.jsonl'))
    b2b_summary.validate(plan,pp,aa,cc)
    require(plan==read(b2b.HERE/'PLAN.json'),'B2B_PLAN_CHANGED')
    require(read(use(B2B/'models.json'))==read(B2A/'MODEL_MANIFEST.json'),'B2B_BASE_MANIFEST_CHANGED')
    selection=read(b2b.HERE/'ATTEMPT_SELECTION.json'); replacements=set(selection['replacement_sample_ids'])
    ap=unique(aa,lambda r:(r['meta']['sample_id'],r['prediction']['model_id'])); cp=unique(cc,lambda r:(r['meta']['sample_id'],r['condition_id']))
    for p in pp:
        meta=p['meta'];sid=meta['sample_id'];expected=selection['replacement_run'] if sid in replacements else selection['original_run']
        require(meta['source_run']==expected,'ATTEMPT_SELECTION_CHANGED')
        run=b2b.HERE/expected;caps=rows(use(run/'captures.jsonl')); matches=[(i,c) for i,c in enumerate(caps,1) if c['sample_id']==sid]
        require(len(matches)==1,'CAPTURE_MEMBERSHIP');line,cap=matches[0]
        require(meta['capture_reference']==ref(run/'captures.jsonl',line),'CAPTURE_REFERENCE_CHANGED')
        slot=next(s for s in plan['positions'] if s['sample_id']==sid)
        item=b2b.bind(run,plan,slot,cap)
        require(item['meta']['app_reference']==meta['app_reference'] and item['meta']['browser_reference']==meta['browser_reference'],'B2B_RAW_REFERENCE_CHANGED')
        cond={c:cp[sid,c] for c in ('C1','C2')};check_conditions(cond,item['pair'])
        base={m.model_id:check_base(ap[sid,m.model_id]['prediction'],m,sid) for m in models}
        q=qualify(p,cap)
        fam={'A_APP_LANG':'App_language','A_APP_TZ':'App_timezone','A_BROWSER_LANG':'Browser_language','A_BROWSER_TZ':'Browser_timezone'}.get(meta['scenario'])
        members.append(dict(sample_id=sid,cohort='b2b42',role='selection',**q,family=fam,scenario=meta['scenario'],phase=meta['phase'],group_id=meta['scenario_group_id'],
            environment='B2B_API36.1_arm64_Chrome134',source_label_scope='candidate/run-scoped; independent operation sidecar',source_meta=meta))
        inputs.append(dict(sample_id=sid,base_states=base,conditions={c:r['state'] for c,r in cond.items()},
            references={'qualification':ref(B2B/'positions.jsonl',pp.index(p)+1),'base':{m.model_id:ref(B2B/'app_predictions.jsonl',aa.index(ap[sid,m.model_id])+1) for m in models},
            'conditions':{c:ref(B2B/'condition_results.jsonl',cc.index(r)+1) for c,r in cond.items()}}))
    require(collections.Counter(m['identity'] for m in members if m['cohort']=='b2b42')=={'NORMAL':34,'EFFECTIVE_INTERVENTION':8},'B2B_IDENTITY_CHANGED')
    return members,inputs

def mtc_cohorts(models, splits):
    registry=[(n,r) for n,r in b2a.mtc_members() if r['split'] in splits]
    old_members=unique(rows(use(B2A/'MTC_MEMBERS.jsonl')),lambda r:r['sample_id'])
    for n,r in registry: require(old_members[r['sample_id']]==dict(registry_line=n,**r),'P2_SAVED_MEMBERS_CHANGED')
    items=b2a.mtc(registry)
    old_c=rows(use(B2A/'condition_results.jsonl'))
    pc=unique([r for r in old_c if r['meta']['cohort']=='mtc' and r['meta']['group'] in splits and r['condition_id'] in ('C1','C2')],lambda r:(r['meta']['sample_id'],r['condition_id']))
    old_a=rows(use(b2a.MODEL/'predictions.jsonl.gz'))
    selected=[(n,r) for n,r in enumerate(old_a,1) if r['model_id'] in IDS and r['dataset']=='mtc' and r['subset'] in splits]
    pa=unique(selected,lambda nr:(nr[1]['sample_id'],nr[1]['model_id']))
    require(len(pa)==len(items)*3 and len(pc)==len(items)*2,'MTC_CARTESIAN_MEMBERSHIP')
    members=[]; inputs=[]; lookup={r['sample_id']:r for _,r in registry}
    for item in items:
        meta=item['meta'];sid=meta['sample_id'];r=lookup[sid]; cond={c:pc[sid,c] for c in ('C1','C2')}
        require(all(x['meta']==meta for x in cond.values()),'MTC_METADATA_CHANGED')
        check_conditions(cond,item['pair'])
        require(meta['normal_basis']['supported'] is True,'MTC_NORMAL_BASIS_UNCONFIRMED')
        base={}
        for m in models:
            n,p=pa[sid,m.model_id]
            require(p['scheme']=='B_REL_TZ' and p['fold_id']==m.binding['fold_id'],'MTC_MODEL_BINDING')
            require(p['source_line']==r['source_line'] and p['source_refs']['app_raw_line']==r['app_raw_line'] and p['source_view']==r['source_view'] and p['historical_split']==r['split'],'MTC_PREDICTION_SOURCE')
            require({k:v for k,v in p['normal_basis'].items() if k!='evidence_refs'}=={k:v for k,v in meta['normal_basis'].items() if k!='evidence_refs'},'MTC_NORMAL_BASIS_CHANGED')
            require(set(p['normal_basis']['evidence_refs'])==set(meta['normal_basis']['evidence_refs'])|{ref(b2a.RAW/'collection_batches.jsonl')},'MTC_NORMAL_REFERENCES_CHANGED')
            for rel in p['relation_results']:
                b=rel['source_binding']
                require(b['app_session_id']==r['app_session_id'] and b['payload_id']==r['app_payload_sha256'] and b['collector_version_code']==p['collector_version_code'],'MTC_PAYLOAD_BINDING')
            base[m.model_id]=check_base(p,m,sid)
        members.append(dict(sample_id=sid,cohort='mtc_'+r['split'],role='selection' if r['split']=='discovery' else 'historical_evaluation',identity='NORMAL',
            normal_identity_supported=True,intervention_effect_confirmed=False,operation_effect='NOT_APPLICABLE',runtime_restored=None,full_recovery_qualified=None,
            app_input_available=True,browser_input_available=True,pair_binding_available=True,family=None,scenario='routine_mtc',phase='observation',group_id=r['group_id'],
            environment=r['profile'],source_label_scope=r['label_status'],original_metric_eligible=r['metric_eligible'],source_meta=meta))
        inputs.append(dict(sample_id=sid,base_states=base,conditions={c:v['state'] for c,v in cond.items()},
            references={'registry':meta['evaluation_basis'],'base':{m.model_id:ref(b2a.MODEL/'predictions.jsonl.gz',pa[sid,m.model_id][0]) for m in models},
            'conditions':{c:ref(B2A/'condition_results.jsonl',old_c.index(v)+1) for c,v in cond.items()}}))
    return members,inputs
