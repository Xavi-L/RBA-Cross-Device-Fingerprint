#!/usr/bin/env python3
"""Evaluate v16 using the same reader, binding and frozen condition logic."""
import argparse,json
from collections import Counter
from pathlib import Path
from profile import HERE,ROOT,evidence,load,validate


def single_workflow(bound,raw,operation,receipt,commands,*,planned,run,settings):
    sid=operation.get('session_id');step=planned['step_id']
    context=settings['context_prefix']+planned['environment']+':'+step
    launches=[(i,c) for i,c in enumerate(commands) if 'start' in c['argv'] and context in c['argv']]
    proof={'verified':False,'current_execution_verified':False,'operation_id':step,'session_id':sid,
           'noop':planned['control']=='default','evidence_refs':[evidence.reference(run/'environment.json'),bound['source_binding']['raw_reference']],
           'reasons':[],'normality_requires_geometry':False}
    payload=raw.get('canonical_received_payload',{})
    manifest=payload.get('collection_manifest',{}) if isinstance(payload,dict) else {}
    if bound.get('status')!='OK' or manifest.get('runtime_context')!=context:proof['reasons'].append('CURRENT_RAW_BINDING_FAILED')
    if len(launches)!=1:proof['reasons'].append('CURRENT_LAUNCH_NOT_UNIQUE')
    else:
        i,c=launches[0];prior=commands[max(0,i-20):i]
        if not (c.get('returncode')==0 and any(x['argv'][-3:-1]==['am','force-stop'] and x.get('returncode')==0 for x in prior)
                and any('pidof' in x['argv'] and x.get('returncode')==1 for x in prior)):
            proof['reasons'].append('FRESH_PROCESS_NOT_VERIFIED')
        if planned['control']=='default' and any(str(a).endswith(('.ENABLE_WEBVIEW_DEBUG','.WAIT_FOR_WEBVIEW_CONTROL','.PROBE_DELAY_MS')) for a in c['argv']):
            proof['reasons'].append('DEFAULT_START_CONTROL_EXTRAS_PRESENT')
    if operation.get('owned_app_process_absent_after') is not True:proof['reasons'].append('OWNED_PROCESS_CLEANUP_NOT_VERIFIED')
    if planned['control']=='fault':
        events=receipt.get('commands',[])
        expected=['Page.enable','Emulation.clearDeviceMetricsOverride','Page.addScriptToEvaluateOnNewDocument','Page.navigate',
                  'Runtime.evaluate','Runtime.evaluate','Page.removeScriptToEvaluateOnNewDocument','Emulation.clearDeviceMetricsOverride']
        if (receipt.get('version')!='screen-geometry-web-fault-v1' or receipt.get('status')!='COMPLETED'
                or [c.get('method') for c in events]!=expected or any('result' not in c or c.get('error') for c in events)
                or receipt.get('raw_receipt',{}).get('session_id')!=sid
                or receipt.get('late_raw_receipt',{}).get('session_id')!=sid):
            proof['reasons'].append('FIXED_WEB_FAULT_FLOW_NOT_VERIFIED')
    else:
        # The actual App-owned upload is independently verifiable from the
        # launch/process/raw evidence. The default debug-socket assertion is a
        # separate platform check, retained even when it failed.
        proof['default_debug_socket_check']=operation.get('error') or 'see launch receipt'
    proof['verified']=proof['current_execution_verified']=not proof['reasons']
    return proof


def engineering_checks(source,settings,rows):
    checks=[]
    for row in rows:
        try:
            checks.append(engineering_position(source,settings,row))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as error:
            # Supplemental engineering diagnostics must not invalidate other
            # positions after the shared evaluator has isolated damaged input.
            checks.append({'environment':row['environment'],'step_id':row['step_id'],
                'status':'FAILED_INPUT','errors':[evidence.issue(source/'runs'/row['environment'],
                'ENGINEERING_STRUCTURE_ERROR',detail=str(error))]})
    return checks


def engineering_position(source,settings,row):
    run=source/'runs'/row['environment'];loaded=evidence.read_jsonl(evidence.archive_path(run))
    sid=row['operation'].get('session_id');matches=[r for r in loaded.records if r['value'].get('session_id')==sid]
    raw=matches[0]['value'] if len(matches)==1 else {};payload=raw.get('canonical_received_payload',{})
    observations=payload.get('collection_observations',{});geometry=observations.get('webview_geometry',{})
    canonical=evidence.read_jsonl(run/'backend/expanded_collected_data.jsonl')
    receipts=evidence.read_jsonl(run/'backend/collection_receipts.jsonl')
    x={'environment':row['environment'],'step_id':row['step_id'],'session_id':sid,
       'errors':loaded.errors+canonical.errors+receipts.errors,
       'raw_reference':row['raw_reference'],'operation_status':row['operation'].get('status'),
       'raw_archive_records_for_session':len(matches),
       'canonical_records_for_session':sum(r['value'].get('session_id')==sid for r in canonical.records),
       'receipt_records_for_session':sum(r['value'].get('session_id')==sid for r in receipts.records),
       'fixed_status_field_count':len(payload.get('collection_status',{}).get('fields',{})),
       'webdriver_observation_retained':bool(observations.get('webdriver')),
       'webgl_observation_retained':bool(observations.get('webgl_parameter')),
       'module_version':geometry.get('collector_version'),'geometry_status':geometry.get('read_status'),
       'geometry_reason':geometry.get('reason'),'attempts':len(geometry.get('attempts',[])),
       'elapsed_ms':geometry.get('finished_elapsed_realtime_ms',0)-geometry.get('started_elapsed_realtime_ms',0),
       'bound_window':row.get('geometry_evidence',{}).get('usable_window',False),
       'condition_states':{k:v['state'] for k,v in row['conditions'].items()}}
    if row['process_type']=='DEGRADE':
        receipt,errors=evidence.read_object(run/(row['step_id']+'.cdp.json'));x['errors']+=errors
        x.update(fault_scope='Web geometry function returns null; not a Native getter exception',
            after_upload=receipt.get('after_upload'),after_deadline=receipt.get('after_deadline'),
            late_observation_seconds=receipt.get('late_observation_seconds'),excluded_from_normal_and_attack_rates=True)
        x['degradation_pass']=(not x['errors'] and x['raw_archive_records_for_session']==x['canonical_records_for_session']==1
            and x['fixed_status_field_count']==177 and x['webdriver_observation_retained'] and x['webgl_observation_retained']
            and x['geometry_status']=='unavailable' and x['attempts']==2 and 0<=x['elapsed_ms']<=5000
            and receipt.get('after_upload')==receipt.get('after_deadline')
            and receipt.get('after_deadline',{}).get('calls')==2 and receipt.get('late_observation_seconds',0)>=6)
    if row['process_type'] in ('DEFAULT','POST_FAULT'):
        life,errors=evidence.read_object(run/'environment.json');x['errors']+=errors
        context=settings['context_prefix']+row['environment']+':'+row['step_id']
        launch=[c for c in life.get('commands',[]) if context in c.get('argv',[]) and 'start' in c.get('argv',[])]
        args=launch[0]['argv'] if len(launch)==1 else []
        native=payload.get('android_native_data',{}).get('build_fingerprint_layer',{})
        x.update(default_launch_without_debug_or_wait_extras=bool(args) and not any(str(a).endswith(('.ENABLE_WEBVIEW_DEBUG','.WAIT_FOR_WEBVIEW_CONTROL','.PROBE_DELAY_MS')) for a in args),
            os_build_type=native.get('build_type'),os_build_fingerprint=native.get('build_fingerprint'),
            debug_endpoint_disabled_verified=False,
            debug_check_limit='WebView91 SharedStatics ignores disabling on debug Android; initial socket assertion retained as FAILED',
            no_cdp_collection_used=bool(args) and not errors and not any(
                context in c.get('argv',[]) and Path(str(c.get('argv',[''])[0])).name=='node'
                for c in life.get('commands',[])))
    return x

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',type=Path,default=HERE/'v16_smoke')
    p.add_argument('--output-dir',type=Path,default=HERE/'v16_evaluation');p.add_argument('--settings',type=Path,default=HERE/'SETTINGS.json');args=p.parse_args()
    s=validate(evidence.read_object(args.settings,required=True)[0]);ev=load('evaluate')
    if args.output_dir.resolve()==args.input_dir.resolve():raise ValueError('Evaluation requires a new output directory')
    rows,errors=ev.evaluate_positions(args.input_dir,s,s['positions'],smoke=True,identity_prefix=s['identity_prefix'],context_prefix=s['context_prefix'],single_workflow=single_workflow)
    summary=ev.save_evaluation(args.output_dir,rows,errors,12)
    checks=engineering_checks(args.input_dir,s,rows)
    ev.write(args.output_dir/'ENGINEERING_CHECKS.json',{'positions':checks,
        'success_path_nine':ev.statistics([r for r in rows if r['process_type']=='A']),
        'degradation_excluded_from_normal_and_attack_rates':True,'model_fit_calls':0})
    print(json.dumps({k:summary[k] for k in ('planned_records','received_raw_records','usable_geometry_windows','trio_recovery','position_status_counts')}))


if __name__=='__main__':main()
