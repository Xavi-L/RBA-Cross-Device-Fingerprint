"""Experiment identity from operation/current raw/recovery, never detector outputs."""
from datetime import datetime
from conditions import A,B,AC,BC,N,operand

def instant(v):
    if not isinstance(v,str):raise ValueError('TIMESTAMP_MISSING')
    return datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
def major_fields(item,side):
    raw=item.get(side) if item else None
    if not raw:return None
    web=raw.get('canonical_received_payload',{}).get('web_data',{})
    selected={'navigator_layer':['user_agent','platform','language','languages'],
      'execution_layer':['timezone_id','timezone_offset'],
      'screen_layer':['screen_resolution_logical','color_depth','pixel_depth','device_pixel_ratio'],
      'graphics_layer':['webgl_renderer','webgl_vendor','webgl_max_texture_size','webgl2_supported']}
    return {layer+'.'+k:web.get(layer,{}).get(k) for layer,keys in selected.items() for k in keys}

def qualify(slot,cap,item,pre=None,post=None):
    r=item['record'];endpoint='app' if '_APP_' in slot['scenario'] else 'browser'
    active=slot['scenario'].startswith('A_') and slot['phase']=='change'
    out={'identity':'UNCONFIRMED','effective':False,'endpoint':endpoint,'fields':{},'confounded':False,'reasons':[]}
    if not cap or cap.get('result')=='NOT_EXECUTED':out['reasons']=['CAPTURE_MISSING_OR_UNEXECUTED'];return out
    restore=cap.get('restoration',[]);out['runtime_restored']=len(restore)==2 and all(x['status']=='COMPLETED' for x in restore)
    out['endpoint_available']={x:r['binding'].get(x,False) for x in ('app','browser')}
    out['pair_valid']=r['binding'].get('pair',False)
    targets=cap.get('control_route',{}).get('targets',{})
    fields={'deviceMemory':A if endpoint=='app' else B,'hardwareConcurrency':AC if endpoint=='app' else BC}
    before=cap.get(endpoint+'_before',{}).get('resources',{})
    operation=cap.get(endpoint+'_control',{})
    for key,target in targets.items():
        observed,error=operand(r,fields[key]);old=before.get(key,{})
        executed=key in operation.get('applied',[])
        changed=old.get('status')=='observed' and error is None and old.get('value')!=observed
        out['fields'][key]={'executed':executed,'original_readable':old.get('status')=='observed','before':old.get('value'),'current':observed,'target':target,'changed':changed,'target_reached':observed==target and error is None,'direction':'up' if changed and observed>old['value'] else 'down' if changed else 'unchanged' if error is None else 'unknown','restored':next((x.get('status')=='COMPLETED' for x in restore if x.get('endpoint')==endpoint),False)}
    # Observer read agrees with canonical collector values for each available endpoint.
    out['observer_matches_raw']={}
    for side,ks in [('app',(A,AC)),('browser',(B,BC))]:
        observed=cap.get(side+'_during',{}).get('resources',{})
        out['observer_matches_raw'][side]=all(operand(r,f)[1] is not None or operand(r,f)[0]==observed.get(k,{}).get('value') for k,f in zip(('deviceMemory','hardwareConcurrency'),ks)) and bool(observed)
    try:
        start=cap.get('control_start_command_at') or cap.get('control_begin');end=cap.get('control_restoration_begin') or cap.get('control_end')
        out['control_timing']={'preparation_begin':cap.get('control_preparation_begin'),'target_command_at':cap.get('control_start_command_at'),'restore_command_at':cap.get('control_restoration_begin'),'basis':cap.get('target_control_timing_basis')}
        out['held_through_receipts']=instant(end)>=max(instant(item[x]['server_received_at']) for x in ['app','browser']) and instant(start)<=instant(cap['browser_gate_release'] if endpoint=='browser' else cap['app_navigation_begin'])
    except (KeyError,TypeError,ValueError):out['held_through_receipts']=False
    changed_fields=[k for k,v in out['fields'].items() if v['executed'] and v['changed'] and v['target_reached']]
    out['subtype']='both_changed' if len(changed_fields)==2 else 'memory_only_changed' if changed_fields==['deviceMemory'] else 'cpu_only_changed' if changed_fields==['hardwareConcurrency'] else 'no_observable_change'
    other='browser' if endpoint=='app' else 'app';other_fields=(B,BC) if endpoint=='app' else (A,AC)
    pre_record=pre['record'] if pre else None;post_record=post['record'] if post else None
    out['resource_returned_to_pre']=bool(pre_record and post_record and all(operand(pre_record,f)==operand(post_record,f) for f in [N,A,B,AC,BC]))
    out['non_target_checks']={'other_endpoint_resources':bool(pre_record and all(operand(pre_record,f)==operand(r,f) for f in other_fields)),'native_memory':bool(pre_record and operand(pre_record,N)==operand(r,N)),
        'triplet_major_raw_fields':bool(pre and post and all(major_fields(pre,side)==major_fields(item,side)==major_fields(post,side) for side in ['app','browser'])),'same_page_major_fields':all(cap.get(side+'_before',{}).get('nontarget')==cap.get(side+'_held_until_end',{}).get('nontarget') for side in ['app','browser'])}
    if active:
        out['effective']=bool(changed_fields and out['observer_matches_raw'].get(endpoint) and r['binding'].get(endpoint))
        out['confounded']=not all(out['non_target_checks'].values())
        if out['effective']:
            out['identity']='CONTROLLED_INTERVENTION'
            if not out['held_through_receipts']:out['reasons'].append('BOTH_RECEIPT_INTERVAL_UNCONFIRMED')
            if out['confounded']:out['reasons'].append('NON_TARGET_CHANGE_OR_UNVERIFIED')
            if not out['runtime_restored'] or not out['resource_returned_to_pre']:out['reasons'].append('RECOVERY_FAILED_OR_UNCONFIRMED')
        elif targets and all(not v['original_readable'] for v in out['fields'].values()):out['identity']='UNSUPPORTED'
        elif out['fields'] and all(v['executed'] and not v['changed'] and v['target_reached'] for v in out['fields'].values()):out['identity']='NO_EFFECT'
    else:
        pristine=all(not cap.get(side+'_control',{}).get('applied') and all(cap.get(side+'_before',{}).get('resources',{}).get(k,{}).get('own') is None for k in ['deviceMemory','hardwareConcurrency']) for side in ['app','browser'])
        out['endpoint_normal_evidence']={side:pristine and out['endpoint_available'][side] and out['observer_matches_raw'][side] for side in ['app','browser']}
        if pristine and all(out['endpoint_available'].values()) and all(out['observer_matches_raw'][side] for side in ['app','browser'] if out['endpoint_available'][side]):out['identity']='NORMAL'
        # A later recovery failure cannot erase an independently evidenced pre normal.
        if slot['phase']=='post' and not out['resource_returned_to_pre']:out['reasons'].append('POST_DIFFERS_OR_PRE_UNAVAILABLE')
    return out
