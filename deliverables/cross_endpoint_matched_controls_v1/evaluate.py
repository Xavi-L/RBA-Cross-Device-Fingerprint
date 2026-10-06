"""Explicit new-batch adapter. Current-stage-only frozen inference, no fitting."""
import argparse, collections, hashlib, importlib.util, json, sys
from datetime import datetime
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT),str(HERE.parent/'browser67_cross_endpoint_diagnostic_v1')]
spec=importlib.util.spec_from_file_location('b2a_frozen',HERE.parent/'browser67_cross_endpoint_diagnostic_v1/run.py')
b2=importlib.util.module_from_spec(spec);spec.loader.exec_module(b2)
from hybridguard_agent.evidence.paired244 import field_contract
from hybridguard_agent.research.mtc_relation_sources import _flatten, _quality
CONDITIONS=('C1','C2','C3','D1','D2')
def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s] if Path(p).exists() else []
def write(p,r):Path(p).write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,rs):Path(p).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rs))
def require(x,msg):
    if not x:raise ValueError(msg)
def load_ref(run,ref,expected):
    require(isinstance(ref,dict) and ref.get('file')=='data/'+expected,'RAW_REFERENCE_PATH_MISMATCH')
    n=ref.get('line');require(type(n) is int and n>0,'INVALID_PHYSICAL_LINE')
    raw=(run/ref['file']).read_bytes().splitlines()[n-1]
    # One referenced-line check, not an archive-wide integrity scan.
    require(hashlib.sha256(raw).hexdigest()==ref.get('line_sha256'),'RAW_REFERENCE_LINE_CHANGED')
    return json.loads(raw),str((run/ref['file']).relative_to(ROOT))+':'+str(n)
def project(app,browser):
    contract=field_contract();out={'features':{},'field_status':{},'field_quality':{}}
    for side,raw in [('app',app),('browser',browser)]:
        if raw is None:continue
        p=raw['canonical_received_payload'];v=_flatten(p,side)
        statuses=p['collection_status']['fields'] if side=='app' else p['field_statuses']
        for field in contract:
            if not field.startswith(side+'.'):continue
            if field in v:out['features'][field]=v[field]
            status=statuses.get(field[len(side)+1:]);out['field_status'][field]=status
            if field in v:out['field_quality'][field]=_quality(field,v[field],status)
    return out
def bind(run,plan,s,capture,duplicate=False):
    meta={**s,'cohort':'b2b_matched_local','app_reference':None,'browser_reference':None}
    a=b=None;ae=[];be=[];pe=[]
    if not capture or duplicate:
        error='DUPLICATE_CAPTURE_ID' if duplicate else 'CAPTURE_MISSING'
        return {'meta':meta,'raw':None,'app_session':None,'pair':{'features':{},'field_status':{},'field_quality':{},'errors':[error],'browser_errors':[error]},'app_errors':[error],'browser_errors':[error],'pair_errors':[error],'browser_raw':None}
    try:
        require(all(capture.get(k)==s[k] for k in ('sample_id','scenario_group_id','runtime_context','collection_round','phase','scenario')),'STAGE_IDENTITY_MISMATCH')
    except ValueError as e:ae.append(str(e));be.append(str(e))
    try:
        raw,ref=load_ref(run,capture.get('archives',{}).get('app'),'raw_expanded_payloads.jsonl')
        require(capture.get('endpoint_counts',{}).get('app')==1,'APP_CAPTURE_COUNT_NOT_UNIQUE')
        p=raw['canonical_received_payload'];m=p['collection_manifest'];sid=raw['session_id']
        require(sid==p['session_id'] and m['runtime_context']==s['runtime_context'] and m['collection_round']==s['collection_round'] and m['device_manifest_id']==plan['device_manifest_id'],'APP_STAGE_MISMATCH')
        require(raw.get('receipt_id') and raw.get('collection_batch_id'),'APP_RECEIPT_MISSING')
        b2.bind_v16(raw,sid,ref)
        require(not ae,';'.join(ae));a=raw;meta['app_reference']=ref
    except (ValueError,KeyError,TypeError,IndexError,OSError) as e:ae.append(str(e))
    try:
        raw,ref=load_ref(run,capture.get('archives',{}).get('browser'),'raw_browser_payloads.jsonl')
        require(capture.get('endpoint_counts',{}).get('browser')==1,'BROWSER_CAPTURE_COUNT_NOT_UNIQUE')
        ticket=capture.get('ticket') or {};sid=raw['browser_session_id']
        require(raw['pair_id']==ticket.get('pair_id') and raw['app_session_id']==ticket.get('app_session_id'),'BROWSER_TICKET_MISMATCH')
        require(ticket.get('selected_browser_package')==ticket.get('resolved_browser_package')==plan['browser_package'],'BROWSER_PACKAGE_MISMATCH')
        b2.check_browser(raw,sid=sid,pair_id=ticket['pair_id'],app_sid=ticket['app_session_id'],revision='expanded-web-67-v2',batch=ticket['collection_batch_id'])
        require(not be,';'.join(be));b=raw;meta['browser_reference']=ref
    except (ValueError,KeyError,TypeError,IndexError,OSError) as e:be.append(str(e))
    try:
        p,pr=load_ref(run,capture.get('archives',{}).get('provenance'),'browser_pair_provenance.jsonl')
        require(a is not None and b is not None,'INCOMPLETE_PAIR')
        require(p['pair_status']=='completed' and p['pair_id']==b['pair_id'] and p['app_session_id']==a['session_id']==b['app_session_id'],'PAIR_IDENTITY_MISMATCH')
        for k in ['app_receipt_id','app_payload_sha256']:
            require(p[k]==a[k.removeprefix('app_')],'APP_PROVENANCE_MISMATCH:'+k)
        for k in ['browser_receipt_id','browser_payload_sha256','browser_session_id','app_receipt_id','collection_batch_id']:
            require(p[k]==b[k],'BROWSER_PROVENANCE_MISMATCH:'+k)
        require(p['collection_batch_id']==a['collection_batch_id'],'BATCH_MISMATCH')
        require(p['selected_browser_package']==p['resolved_browser_package']==plan['browser_package'],'PAIR_PACKAGE_MISMATCH')
        meta['provenance_reference']=pr
    except (ValueError,KeyError,TypeError,IndexError,OSError) as e:pe.append(str(e))
    pair=project(a,b);pair['errors']=[*ae,*be,*pe];pair['browser_errors']=be.copy()
    if a and b:pair['times']=b2.capture_times(a,b,meta['app_reference'],meta['browser_reference'])
    return {'meta':meta,'raw':a,'app_session':a['session_id'] if a else None,'pair':pair,'app_errors':ae,'browser_errors':be,'pair_errors':pe,'browser_raw':b}
def operands(item):
    p=item['pair']['features'];out={}
    for side in ['app','browser']:
        out[side]={k:p.get(f'{side}.web_data.{layer}.{k}') for k,layer in [('language','navigator_layer'),('languages','navigator_layer'),('timezone_id','execution_layer'),('timezone_offset','execution_layer')]}
    out['native']={k:p.get('app.android_native_data.locale_timezone_layer.'+k) for k in ['native_locale','native_language','native_country','native_timezone_id','native_timezone_offset_min']}
    return out
def instant(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def qualify(s,cap,current,pre,post):
    """Experiment identity only: this function cannot see predictions/conditions."""
    normal_intent=s['scenario'].startswith('L_') or s['phase']!='change'
    q={'intended_identity':'normal' if normal_intent else 'controlled_intervention','identity':'UNCONFIRMED','operation_effect':'UNKNOWN','fully_qualified':False,'reasons':[]}
    if not cap or current['pair']['errors']:
        q['reasons']=['PAIR_OR_CAPTURE_UNAVAILABLE'];return q
    o=operands(current);po=operands(pre) if pre else None;post_o=operands(post) if post else None
    restored=len(cap.get('restoration',[]))==2 and all(x['status']=='COMPLETED' for x in cap['restoration'])
    q['runtime_restored']=restored
    env=cap.get('setting',{}).get('after',{})
    baseline=env.get('locale')=='en-US' and env.get('timezone')=='Asia/Shanghai'
    pristine=all(not cap.get(e+'_before',{}).get(k,True) for e in ['app','browser'] for k in ['languageHasOwn','languagesHasOwn'])
    if s['phase']!='change':
        q['operation_effect']='NO_TARGET_MODIFICATION'
        setting_ok=cap.get('setting',{}).get('status') in ['NOT_NEEDED','EXECUTED']
        if not cap.get('control_installed') and baseline and pristine and setting_ok and restored:
            q.update(identity='NORMAL',fully_qualified=True)
        else:q['reasons'].append('NORMAL_BASELINE_OR_RECOVERY_UNCONFIRMED')
        if s['phase']=='post':
            q['restored_to_pre']=po==o
            if po!=o:q['fully_qualified']=False;q['reasons'].append('POST_OPERANDS_DIFFER_FROM_PRE')
        return q
    if normal_intent:
        status=cap.get('setting',{}).get('status')
        q['execution_status']=status
        q['operation_effect']='OBSERVED_CHANGE' if po and po!=o else 'NO_OBSERVABLE_EFFECT' if po else 'UNKNOWN'
        durability=s['scenario']!='L_BROWSER_LANG' or cap.get('setting',{}).get('operation',{}).get('durability_verified') is True
        if status=='EXECUTED' and not cap.get('control_installed') and pristine:
            q['identity']='NORMAL';q['fully_qualified']=restored and post_o==po and po is not None
            if not durability:q['fully_qualified']=False;q['reasons'].append('PREFERENCE_DURABILITY_NOT_VERIFIED')
            if not q['fully_qualified']:q['reasons'].append('NORMAL_SETTING_RECOVERY_UNCONFIRMED')
        else:q['reasons'].append('NORMAL_SETTING_NOT_VERIFIED')
        return q
    route=cap.get('control_route',{});endpoint=route.get('endpoint');other='browser' if endpoint=='app' else 'app'
    lang=s['scenario'].endswith('LANG')
    target=(o.get(endpoint,{}).get('language')=='fr-FR' and o.get(endpoint,{}).get('languages')==['fr-FR']) if lang else (o.get(endpoint,{}).get('timezone_offset')==-540 and o.get(endpoint,{}).get('timezone_id')=='Asia/Tokyo')
    changed=po is not None and o.get(endpoint)!=po.get(endpoint)
    q['operation_effect']='OBSERVED_CHANGE' if target and changed else 'NO_OBSERVABLE_EFFECT'
    q['non_target_unchanged']=bool(po and o[other]==po[other] and o['native']==po['native'])
    try:
        q['held_through_both_receipts']=instant(cap['control_end'])>=max(instant(current[k]['server_received_at']) for k in ['raw','browser_raw']) and instant(cap['control_begin'])<=instant(cap['app_navigation_begin'] if endpoint=='app' else cap['browser_gate_release'])
        held=cap[endpoint+'_held_until_end'];q['target_still_active_at_end']=all(held.get(k)==o[endpoint].get(k) for k in (['language','languages'] if lang else ['timezone_id','timezone_offset']))
    except (KeyError,TypeError,ValueError):q['held_through_both_receipts']=False;q['target_still_active_at_end']=False
    if cap.get('control_installed') and target and changed and q['non_target_unchanged'] and q['held_through_both_receipts'] and q['target_still_active_at_end']:
        q['identity']='CONTROLLED_INTERVENTION';q['fully_qualified']=restored and post_o==po
        if not q['fully_qualified']:q['reasons'].append('RESTORATION_FAILED_OR_UNCONFIRMED')
    else:q['reasons'].append('CONTROL_EFFECT_OR_SCOPE_UNCONFIRMED')
    return q
def run(directory):
    run=Path(directory).resolve();plan=read(run/'plan.json');slots=plan['positions']
    require(len(slots)==42 and len({s['sample_id'] for s in slots})==42,'EXACT_42_POSITIONS_REQUIRED')
    expected={(sc,r,ph) for sc in ['L_SYS_LANG','L_SYS_TZ','L_BROWSER_LANG','A_APP_LANG','A_APP_TZ','A_BROWSER_LANG','A_BROWSER_TZ'] for r in [1,2] for ph in ['pre','change','post']}
    require({(s['scenario'],s['round'],s['phase']) for s in slots}==expected,'MATRIX_CHANGED')
    locks=read(HERE/'FROZEN.json')
    for f,h in locks['files'].items():require(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,'FROZEN_SOURCE_CHANGED:'+f)
    models,manifest=b2.load_models();captures=lines(run/'captures.jsonl');by=collections.defaultdict(list)
    for n,c in enumerate(captures,1):by[c.get('sample_id')].append((run,n,c))
    attempt_selection=None
    if (HERE/'ATTEMPT_SELECTION.json').exists():
        attempt_selection=read(HERE/'ATTEMPT_SELECTION.json')
        affected={s['sample_id'] for s in slots if s['scenario']=='L_BROWSER_LANG'}
        require(set(attempt_selection['replacement_sample_ids'])==affected,'REPAIR_SCOPE_CHANGED')
        repair=(HERE/attempt_selection['replacement_run']).resolve()
        require(repair==HERE/'private_runs/repair01','REPAIR_DIRECTORY_MISMATCH')
        replacements=collections.defaultdict(list)
        for n,c in enumerate(lines(repair/'captures.jsonl'),1):replacements[c.get('sample_id')].append((repair,n,c))
        require(set(replacements)<=affected,'UNPLANNED_REPAIR_CAPTURE')
        for sid in affected:by[sid]=replacements[sid] # No fallback to a better original result.
    items={};caps={}
    for s in slots:
        cc=by[s['sample_id']];source,n,cap=cc[0] if len(cc)==1 else (run,None,None);caps[s['sample_id']]=cap
        items[s['sample_id']]=bind(source,plan,s,cap,len(cc)>1)
        items[s['sample_id']]['meta'].update(source_run=str(source.relative_to(HERE)),capture_reference=str((source/'captures.jsonl').relative_to(ROOT))+':'+str(n))
    # A raw session or pair cannot silently fill two different planned slots.
    for side,key in [('raw','session_id'),('browser_raw','browser_session_id'),('browser_raw','pair_id')]:
        ids=collections.Counter(i[side][key] for i in items.values() if i[side])
        for i in items.values():
            if i[side] and ids[i[side][key]]>1:
                i['pair']['errors'].append('REUSED_ENDPOINT_ID')
                if side=='raw':i['raw']=None;i['app_errors'].append('REUSED_APP_ID')
                else:i['pair']['browser_errors'].append('REUSED_BROWSER_ID')
    predictions=[];results=[];records=[]
    for s in slots:
        item=items[s['sample_id']];group=[x for x in slots if x['scenario_group_id']==s['scenario_group_id']]
        sibling=lambda ph:items[next(x['sample_id'] for x in group if x['phase']==ph)]
        q=qualify(s,caps[s['sample_id']],item,sibling('pre'),sibling('post'))
        records.append({'meta':item['meta'],'qualification':q,'operands':operands(item),'app_errors':item['app_errors'],'browser_errors':item['browser_errors'],'pair_errors':item['pair_errors']})
        for model in models:predictions.append(b2.predict_item(item,model))
        for cid in CONDITIONS:results.append({'meta':item['meta'],**b2.cond.evaluate(cid,item['pair'])})
    out=run/'evaluation';out.mkdir(exist_ok=False)
    write(out/'plan.json',plan);write(out/'models.json',manifest)
    jsonl(out/'positions.jsonl',records);jsonl(out/'app_predictions.jsonl',predictions);jsonl(out/'condition_results.jsonl',results)
    write(out/'evaluation_manifest.json',{'adapter':'b2b-current-v16-paired244-v1','positions':42,'model_positions':len(predictions),'condition_positions':len(results),'fit_calls':0,'current_stage_only':True,'browser_in_app_model':False,'source_locks':locks,'attempt_selection':attempt_selection,'privacy':'Local-only raw operands and identifiers; not authorized for publication.'})
    print(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_directory');run(p.parse_args().run_directory)
