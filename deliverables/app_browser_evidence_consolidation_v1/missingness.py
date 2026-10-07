"""Twelve targeted P2/P1/raw chains; never executes a condition or a model."""
import json,math,re,sys
from collections import defaultdict,Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
EXT=HERE.parent/'app_resource_constrained_extension_v1'
RES=HERE.parent/'app_resource_paired_validation_v1'
sys.path.insert(0,str(ROOT))
from hybridguard_agent.research.mtc_relation_sources import _quality
N='app.android_native_data.memory_layer.total_memory_gb'
A='app.web_data.navigator_layer.device_memory'
B='browser.web_data.navigator_layer.device_memory'
AO='app.web_data.execution_layer.timezone_offset'
BO='browser.web_data.execution_layer.timezone_offset'
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(line) for line in Path(p).read_text().splitlines()]
def require(ok,reason):
    if not ok:raise ValueError(reason)
def index(rs,key=lambda r:r['sample_id']):
    result={key(r):r for r in rs};require(len(result)==len(rs),'DUPLICATE_SOURCE_ID');return result
def selected_physical(refs):
    """Decode only requested physical lines, retaining their original line identity."""
    wanted=defaultdict(set)
    for ref in refs:
        file,n=ref.rsplit(':',1);require(int(n)>0,'INVALID_PHYSICAL_REFERENCE');wanted[file].add(int(n))
    result={}
    for file,lines in wanted.items():
        path=(ROOT/file).resolve();require(path.is_relative_to(ROOT),'REFERENCE_OUTSIDE_REPOSITORY')
        with path.open() as f:
            for n,line in enumerate(f,1):
                if n in lines:result[f'{file}:{n}']=json.loads(line)
                if n>=max(lines):break
        require(all(f'{file}:{n}' in result for n in lines),'MISSING_PHYSICAL_RECORD:'+file)
    return result
def at(obj,path):
    for part in path.split('.'):
        if not isinstance(obj,dict) or part not in obj:return False,None
        obj=obj[part]
    return True,obj
def availability_class(present,value,status,derived_quality,snapshot_value,snapshot_status,snapshot_quality):
    usable=present and type(value) in (int,float) and math.isfinite(value) and value>0 and status=='observed' and derived_quality=='observed_value'
    if not usable:return 'A_RAW_UNAVAILABLE'
    if value!=snapshot_value or status!=snapshot_status or snapshot_quality!='observed_value':return 'B_ADAPTER_MISMATCH'
    return 'C_OTHER_DEPENDENCY_OR_CAUSE_UNCONFIRMED'
def targeted_review():
    out=EXT/'results';members=index(rows(out/'members.jsonl'));inputs=index(rows(out/'inputs.jsonl'));models=read(out/'models.json')
    unknown=read(out/'summary/unknown_overlap.json');selected={};same={}
    for model in models:
        group={}
        for co in ('mtc_discovery','mtc_development','mtc_reserved_validation'):
            u=next(r for r in unknown if r['fold']==model['fold'] and r['cohort']==co)
            require(set(u['ids']['new_F_to_U_M'])==set(u['ids']['new_F_to_U_B']),'M_B_DIFFERENT_MISSING_IDS')
            group[co]=set(u['ids']['new_F_to_U_M'])
            for sid in group[co]:require(members[sid]['cohort']==co and members[sid]['identity']=='NORMAL','MISSING_MEMBER_GROUP_CHANGED')
        same[model['fold']]=group
    groups=list(same.values());require(all(g==groups[0] for g in groups),'MODEL_MISSING_IDS_DIFFER')
    require({k:len(v) for k,v in groups[0].items()}=={'mtc_discovery':7,'mtc_development':0,'mtc_reserved_validation':2},'MISSING_REVIEW_SCOPE_CHANGED')
    missing_ids=set().union(*groups[0].values())
    counter=read(out/'summary/normal_counterexamples.json');counter_ids={r['sample_id'] for r in counter}
    require(len(counter_ids)==3 and not missing_ids&counter_ids,'COUNTEREXAMPLE_SCOPE')
    ids=missing_ids|counter_ids;refs=set()
    for sid in ids:
        meta=members[sid]['source_meta']
        refs.update(meta[k] for k in ('evaluation_basis','pair_reference','app_reference','browser_reference'))
        refs.add(inputs[sid]['references']['original_inputs']['conditions']['C1'])
    original=selected_physical(refs)
    cells=index([r for r in rows(RES/'results/mtc_conditions.jsonl') if r['sample_id'] in ids],lambda r:(r['sample_id'],r['condition']))
    checks=[];missing=[];counterexamples=[];background=[];blockers=[]
    for sid in sorted(ids):
        m=members[sid];meta=m['source_meta'];stored=inputs[sid]
        reg=original[meta['evaluation_basis']];pair=original[meta['pair_reference']]
        app=original[meta['app_reference']];browser=original[meta['browser_reference']]
        ap=app['canonical_received_payload'];bp=browser['canonical_received_payload']
        bindings={
          'P2_member_split':reg['sample_id']==sid and reg['split']==meta['group'] and reg['source_view']=='paired_244' and reg['analysis_role']=='primary_representative',
          'P2_P1_physical':meta['pair_reference'].rsplit(':',1)[1]==str(reg['source_line']) and meta['app_reference'].rsplit(':',1)[1]==str(reg['app_raw_line']) and pair['source_refs']['app_raw_line']==reg['app_raw_line'] and str(pair['source_refs']['browser_raw_line'])==meta['browser_reference'].rsplit(':',1)[1],
          'P1_identity':pair['sample_id']==sid and pair['dataset_view']=='paired_244' and pair['pair']['pair_status']=='completed' and pair['qc']['status']=='passed',
          'App_payload_session':reg['app_session_id']==app['session_id']==ap['session_id']==pair['app']['session_id'] and reg['app_payload_sha256']==app['payload_sha256']==pair['app']['payload_sha256'],
          'Browser_payload_session':reg['browser_payload_sha256']==browser['browser_payload_sha256']==pair['browser']['payload_sha256'] and browser['browser_session_id']==bp['browser_session_id']==pair['browser']['session_id'],
          'pair_batch':browser['app_session_id']==app['session_id'] and browser['pair_id']==bp['pair_id']==pair['pair']['browser_pair_id'] and browser['collection_batch_id']==app['collection_batch_id']==pair['collection_batch_id']==pair['pair']['collection_batch_id'],
          'receipts':browser['browser_receipt_id']==pair['browser']['receipt_id'] and browser['app_receipt_id']==app['receipt_id']==pair['app']['receipt_id']==pair['app']['archived_receipt_id'],
          'research_normal_basis':m['identity']=='NORMAL' and meta['normal_basis']['status']=='research_normal_condition_supported' and meta['normal_basis']['supported'] is True,
        }
        require(all(bindings.values()),'TARGET_BINDING_FAILED:'+sid+':'+str([k for k,v in bindings.items() if not v]))
        projected={}
        for field,payload,side in [(N,ap,'app'),(A,ap,'app'),(B,bp,'browser'),(AO,ap,'app'),(BO,bp,'browser')]:
            local=field[len(side)+1:];present,value=at(payload,local)
            status=(payload['collection_status']['fields'] if side=='app' else payload['field_statuses']).get(local)
            quality=_quality(field,value,status) if present else None
            matches=(present==(field in pair['features']) and value==pair['features'].get(field) and status==pair['field_status'].get(field) and quality==pair['field_quality'].get(field))
            projected[field]=dict(present=present,value=value,status=status,derived_quality=quality,p1_quality=pair['field_quality'].get(field),p1_matches=matches)
        c1ref=stored['references']['original_inputs']['conditions']['C1'];c1=original[c1ref]
        require(c1['condition_id']=='C1' and c1['meta']['sample_id']==sid and c1['state']==stored['C1'],'SAVED_C1_BINDING')
        for op in c1['operands']:
            q=projected[op['field']]
            require(all(op[k]==q[v] for k,v in [('present','present'),('value','value'),('status','status'),('quality','derived_quality')]),'SAVED_C1_OPERANDS')
        for name in ('R_APP_MEMORY','R_NATIVE_BROWSER_MEMORY','R_WEB_MEMORY_DIFFERENCE','D_BROWSER_MEMORY8'):
            cell=cells[sid,name];require(cell['group']==meta['group'] and cell['identity']=='NORMAL','SAVED_CONDITION_GROUP')
            require(all(value==projected[f]['value'] for f,value in cell['operands'].items()),'SAVED_CONDITION_OPERANDS')
        p=projected[B]
        cls=availability_class(p['present'],p['value'],p['status'],p['derived_quality'],pair['features'].get(B),pair['field_status'].get(B),pair['field_quality'].get(B))
        if not all(q['p1_matches'] for q in projected.values()):blockers.append(dict(sample_id=sid,reason='RAW_P1_FIELD_DISAGREEMENT',classification=cls))
        all_app=[stored['app_states'][mo['base_model_id']] for mo in models];all_base=[stored['base_states'][mo['base_model_id']] for mo in models]
        probe=bp.get('probe_metadata',{});ua=bp.get('web_data',{}).get('navigator_layer',{}).get('user_agent','')
        match=re.search(r'Chrome/([^\s]+)',ua);ua_version=match.group(1) if match else 'NOT_RECORDED'
        secure=[]
        def search_secure(obj,path=''):
            if isinstance(obj,dict):
                for key,value in obj.items():
                    if key in ('isSecureContext','is_secure_context','secureContext','secure_context'):secure.append(dict(path=path+key,value=value))
                    search_secure(value,path+key+'.')
        search_secure(bp)
        common=dict(sample_id=sid,group=meta['group'],identity='NORMAL',raw_browser_present=p['present'],raw_browser_memory=p['value'],raw_field_status=p['status'],p1_quality=p['p1_quality'],derived_quality=p['derived_quality'],raw_p1_values_status_quality_equal=all(q['p1_matches'] for q in projected.values()),
            native_memory_gib=projected[N]['value'],app_web_memory=projected[A]['value'],app_memory_condition=cells[sid,'R_APP_MEMORY']['state'],app_models='/'.join(all_app),C1=stored['C1'],base_models='/'.join(all_base),M=cells[sid,'R_NATIVE_BROWSER_MEMORY']['state'],B=cells[sid,'D_BROWSER_MEMORY8']['state'],W=cells[sid,'R_WEB_MEMORY_DIFFERENCE']['state'],
            browser_page_origin=probe.get('page_origin','NOT_RECORDED'),secure_context_evidence=json.dumps(secure) if secure else 'NOT_RECORDED',probe_revision=bp.get('web_probe_revision','NOT_RECORDED'),reported_ua_chromium_version=ua_version,
            p2_reference=meta['evaluation_basis'],p1_reference=meta['pair_reference'],app_raw_reference=meta['app_reference'],browser_raw_reference=meta['browser_reference'],C1_reference=c1ref)
        if sid in missing_ids:
            require(stored['conditions']['M']==stored['conditions']['B']=='U' and all(x=='F' for x in all_app+all_base) and stored['C1']=='F','F_TO_U_SAVED_BASIS')
            common.update(classification=cls,condition_reason=cells[sid,'R_NATIVE_BROWSER_MEMORY']['reason'],
                quality_branch='mtc_relation_sources._quality: observed device_memory == 0 -> ambiguous_sentinel',
                U_branch='conditions.operand: quality != observed_value -> QUALITY_UNAVAILABLE; evaluate retains U',
                why_baseline_defined='App memory and C1 are F; Browser memory is not a selected dependency of S0',
                why_extension_unknown='selected M/B requires unavailable Browser memory; F OR U remains U',
                old_observation_recoverable=False if cls=='A_RAW_UNAVAILABLE' else None,
                mechanism='NOT_CONFIRMED: no recorded direct property availability/read exception/isSecureContext; origin and UA do not prove mechanism')
            missing.append(common)
        else:
            require(stored['conditions']['M']=='T' and p['derived_quality']=='observed_value','COUNTEREXAMPLE_NOT_VALID')
            common.update(native_upper_envelope_gib=cells[sid,'R_NATIVE_BROWSER_MEMORY']['upper_envelope_gib'],classification='VALID_NORMAL_DEVIATION_NOT_MISSING',condition_reason=cells[sid,'R_NATIVE_BROWSER_MEMORY']['reason'])
            counterexamples.append(common)
        checks.append(dict(sample_id=sid,group=meta['group'],bindings=bindings,fields=projected,
            payload_reference_comparison='compared stored P2/P1/archive payload identifiers and receipts; no archive-wide rehash',
            classification=cls if sid in missing_ids else 'NORMAL_COUNTEREXAMPLE'))
    require(Counter(r['group'] for r in counterexamples)=={'discovery':2,'reserved_validation':1},'COUNTEREXAMPLES_MOVED')
    result=dict(unique_missing_records=len(missing),missing_groups=dict(Counter(r['group'] for r in missing)),M_B_ids_identical=True,three_configuration_missing_ids_identical=True,
        classifications=dict(Counter(r['classification'] for r in missing)),normal_counterexamples=3,counterexample_groups=dict(Counter(r['group'] for r in counterexamples)),
        decoded_original_records=len(original),unique_App_raw_records=12,unique_Browser_raw_records=12,raw_origin_counts=dict(Counter(r['browser_page_origin'] for r in missing)),
        blocker_items=blockers,old_observation_recovery_closed=not blockers and all(r['classification']=='A_RAW_UNAVAILABLE' for r in missing),
        broader_mechanism='not established by these archives',condition_prediction_calls=0,model_prediction_calls=0,selection_calls=0,fit_calls=0,collection_calls=0,timing_experiments=0)
    return missing,counterexamples,checks,result
