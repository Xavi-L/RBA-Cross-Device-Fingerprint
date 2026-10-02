#!/usr/bin/env python3
"""Evaluate saved local timezone positions; no collection, fitting or imputation."""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research import normal_collection_evidence as normal
from hybridguard_agent.research import timezone_relation_sources as sources
from hybridguard_agent.research import mtc_timezone_relation as relation
from hybridguard_agent.research import mtc_timezone_candidates as candidates
from hybridguard_agent.research import mtc_reselection_candidates as old_candidates
from hybridguard_agent.research import mtc_relation_selection as baseline
from hybridguard_agent.research import mtc_timezone_selection as engine
from hybridguard_agent.research import memory_relation_validation as memory
from hybridguard_agent.research.rule_learning.contracts import cell


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


prior = module('timezone_local_saved_helpers', ROOT/'deliverables/mtc_constrained_reselection_v1/run_experiment.py')
collector = module('timezone_local_collection_helpers', HERE/'collect.py')
read = lambda path: json.loads(Path(path).read_text())
TZ_FIELDS = (relation.NATIVE_ZONE, relation.NATIVE_RAW, relation.WEB_ZONE, relation.WEB_OFFSET)
SHORT = dict(zip(TZ_FIELDS, ('native_timezone_id', 'native_timezone_offset_min', 'web_timezone_id', 'web_timezone_offset')))


def rows(path):
    if not path.exists(): return []
    with (gzip.open if str(path).endswith('.gz') else open)(path, 'rt') as stream:
        result = []
        for number, line in enumerate(stream, 1):
            if not line.strip(): continue
            try: result.append(json.loads(line))
            except (ValueError, TypeError): result.append({'read_error':'MALFORMED_JSON_LINE', 'line':number})
        return result


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def condition_state(value):
    return 'FAILED' if value['evaluation_status'] != 'OK' else 'U' if not value['available'] else 'T' if value['value'] else 'F'


def fixed_absolute(bound):
    """The preserved absolute condition, not an assertion of normal timezone."""
    if bound.get('status') != 'OK': return cell('FAILED', 'CURRENT_SOURCE_BINDING_FAILED')
    value = bound.get('features', {}).get(relation.WEB_OFFSET)
    if (bound.get('field_status', {}).get(relation.WEB_OFFSET) != 'observed'
            or bound.get('field_quality', {}).get(relation.WEB_OFFSET) != 'observed_value'
            or type(value) not in (int, float) or not math.isfinite(value)):
        return cell('U', 'CURRENT_WEB_OFFSET_UNAVAILABLE')
    return cell('T' if value > -480 else 'F', 'FIXED_WEB_OFFSET_GT_MINUS_480')


def adapt_current(raw, session_id, reference, environment):
    bound = sources.bind_timezone_batch(raw, session_id=session_id, source_reference=reference,
                                       environment_id='timezone-validation-'+environment)
    if bound['status'] != 'OK': raise ValueError(';'.join(bound.get('errors', [])))
    compiler, contract = memory.compiler()
    prepared = compiler.compile_record(raw['canonical_received_payload'], expected_session_id=session_id,
                                       source_reference=reference, measurement_contract=contract)
    return bound, candidates.extend(old_candidates.adapt_controlled(prepared), bound)


def model_set(out, settings):
    result=[]
    for manifest, prefix, implementation in ((ROOT/settings['baseline_models'], (ROOT/settings['baseline_models']).parent, baseline),
                                             (out/'models.json', out, engine)):
        for item in read(manifest)['models']:
            if item['stage'] != 'RETENTION': continue
            model=implementation.load_model(prefix/item['path'])
            if model.model_id != item['model_id']: raise ValueError('SAVED_MODEL_IDENTITY_MISMATCH')
            result.append(({k:item[k] for k in ('scheme','fold_id','model_id')}, implementation, model))
    if len(result) != 6: raise ValueError('THREE_BASELINE_AND_THREE_NEW_MODELS_REQUIRED')
    freeze=read(out/'MODELS_FROZEN.json')
    frozen_ids=freeze.get('model_ids',freeze.get('baseline_model_ids',[])+freeze.get('new_model_ids',[]))
    if freeze['status'] != 'FROZEN' or len(frozen_ids)!=6 or set(frozen_ids) != {m.model_id for _,_,m in result}:
        raise ValueError('LOCAL_MODELS_MUST_MATCH_FROZEN_SET')
    return result


def _refs(reference, run, step):
    return [reference, str(run/'operations.jsonl')+'#'+step, str(run/(step+'.cdp.json')), str(run/'environment.json')+'#commands']


def workflow_proof(bound, raw, op, receipt, commands, *, environment, run):
    """Verify response/value/session evidence, rather than trusting COLLECTED."""
    step, sid = op['step_id'], op.get('session_id')
    binding=bound.get('source_binding', {}); payload=raw.get('canonical_received_payload', {})
    manifest=payload.get('collection_manifest', {}); context='timezone-validation:'+environment+':'+step
    expected_target = op['target_timezone'] if op['process_type']=='A' and op['phase']=='change' else None
    reasons=[]
    if (op.get('status') != 'COLLECTED' or op.get('cdp_status') != 'COMPLETED'
            or receipt.get('status') != 'COMPLETED' or receipt.get('apply_status') != 'COMPLETED'
            or binding.get('binding_valid') is not True or sid != binding.get('app_session_id')
            or manifest.get('runtime_context') != context
            or manifest.get('collector_install_id') != op.get('collector_install_id')
            or receipt.get('raw_receipt', {}).get('session_id') != sid
            or receipt.get('raw_receipt', {}).get('received_before_rollback') is not True):
        reasons.append('CURRENT_OPERATION_RAW_RECEIPT_BINDING_FAILED')
    events=receipt.get('commands', [])
    methods=['Page.enable','Emulation.setTimezoneOverride','Page.navigate','Runtime.evaluate',
             'Emulation.setTimezoneOverride','Runtime.evaluate']
    if ([e.get('method') for e in events] != methods or any('result' not in e or e.get('error')
            or e.get('result', {}).get('errorText') or e.get('result', {}).get('exceptionDetails') for e in events)):
        reasons.append('CDP_COMMAND_RESPONSES_NOT_SUCCESSFUL')
    else:
        current=events[3].get('result', {}).get('result', {}).get('value', {})
        after=events[5].get('result', {}).get('result', {}).get('value', {})
        if (receipt.get('version') != 'timezone-only-cdp-v1' or receipt.get('target_timezone') != expected_target
                or receipt.get('changed_domains') != ([] if expected_target is None else ['Web timezone'])
                or events[1].get('params') != {'timezoneId':expected_target or ''}
                or events[2].get('params') != {'url':'file:///android_asset/expanded_probe.html'}
                or events[4].get('params') != {'timezoneId':''}
                or receipt.get('current_runtime_observation') != current
                or receipt.get('after_rollback_runtime_observation') != after
                or current.get('timezone_id') != bound.get('features', {}).get(relation.WEB_ZONE)
                or current.get('timezone_offset') != bound.get('features', {}).get(relation.WEB_OFFSET)):
            reasons.append('CDP_CURRENT_VALUES_OR_EXPECTED_OPERATION_MISMATCH')
    try:
        if not (normal._stamp(op['started_at']) <= normal._stamp(receipt['started_at'])
                <= normal._stamp(raw['server_received_at']) <= normal._stamp(receipt['finished_at'])
                <= normal._stamp(op['finished_at'])):
            reasons.append('OPERATION_RECEIPT_RAW_TIME_MISMATCH')
    except (KeyError, ValueError, TypeError): reasons.append('OPERATION_RECEIPT_TIME_UNAVAILABLE')
    receipt_name=step+'.cdp.json'
    matched=[i for i,c in enumerate(commands) if any(str(a).endswith('/'+receipt_name) for a in c.get('argv', []))]
    fresh=removed=system_verified=False
    if len(matched)==1:
        index=matched[0]; invocation=commands[index]
        starts=[i for i,c in enumerate(commands[:index]) if context in c.get('argv', [])]
        if len(starts)==1:
            start=starts[0]
            stops=[i for i,c in enumerate(commands[:start]) if c.get('argv', [])[-3:-1]==['am','force-stop']]
            if stops:
                stop=stops[-1]; check=commands[stop+1]
                fresh=(commands[stop].get('returncode')==0 and 'pidof' in check.get('argv', [])
                       and check.get('returncode')==1 and not check.get('stdout','').strip()
                       and commands[start].get('returncode')==0 and invocation.get('returncode')==0
                       and context in invocation.get('argv', []))
                system=op.get('system_change', {})
                if op['process_type']=='L' and op['phase'] in ('change','clean_post'):
                    wanted=system.get('requested_zone')
                    system_verified=(system.get('status')=='COMPLETED' and wanted
                        and system.get('after',{}).get('timezone_id')==wanted
                        and op.get('system_before',{}).get('timezone_id')==wanted
                        and op.get('system_after',{}).get('timezone_id')==wanted
                        and any(c.get('argv', [])[-4:]==['cmd','alarm','set-timezone',wanted]
                                and c.get('returncode')==0 for c in commands[stop:start]))
                else:
                    system_verified=(op.get('system_before',{}).get('timezone_id')
                                     ==op.get('system_after',{}).get('timezone_id')
                                     and bool(op.get('system_before',{}).get('timezone_id')))
        after_stops=[i for i in range(index+1,len(commands)) if commands[i].get('argv', [])[-3:-1]==['am','force-stop']]
        if after_stops:
            stop=after_stops[0]; check=commands[stop+1] if stop+1<len(commands) else {}
            removed=(commands[stop].get('returncode')==0 and 'pidof' in check.get('argv', [])
                     and check.get('returncode')==1 and not check.get('stdout','').strip()
                     and op.get('owned_app_process_absent_after') is True)
    if not fresh: reasons.append('FRESH_OWNED_APP_PROCESS_NOT_VERIFIED')
    if not system_verified: reasons.append('SYSTEM_SETTING_OPERATION_NOT_VERIFIED')
    return {'verified':not reasons,'session_id':sid,'operation_id':step,'noop':expected_target is None,
            'fresh_process_verified':fresh,'process_removed_verified':removed,'system_operation_verified':system_verified,
            'cdp_rollback_verified':receipt.get('rollback_status')=='COMPLETED' and op.get('cdp_rollback_status')=='COMPLETED'
                                    and 'CDP_COMMAND_RESPONSES_NOT_SUCCESSFUL' not in reasons
                                    and len(events)==6 and events[4].get('params')=={'timezoneId':''},
            'after_rollback_runtime_observation':deepcopy(receipt.get('after_rollback_runtime_observation')),
            'evidence_refs':_refs(binding.get('raw_reference'),run,step), 'reasons':reasons}


def current_row(raw, op, reference, environment, models):
    sid=op.get('session_id') or ''
    bound=sources.bind_timezone_batch(raw,session_id=sid,source_reference=reference,environment_id='timezone-validation-'+environment)
    conditions={'R_ABSOLUTE':fixed_absolute(bound),'R_TZ':relation.evaluate(bound)[relation.TIMEZONE_ID]}
    row={'sample_id':'timezoneonly-'+sid if sid else 'unavailable:'+environment+':'+op['step_id'],
         'dataset':'timezone_local','environment':environment,**{k:op[k] for k in ('step_id','phase','target_timezone','process_type','round')},
         'operation':deepcopy(op),'source_binding':bound.get('source_binding',{}),'source_errors':bound.get('errors', []),
         'acquisition_time':bound.get('acquisition_time'),
         'observed_timezone':{SHORT[f]:bound.get('features',{}).get(f) for f in TZ_FIELDS},
         'operands':{f:{'value':bound.get('features',{}).get(f),'status':bound.get('field_status',{}).get(f),
                       'quality':bound.get('field_quality',{}).get(f)} for f in TZ_FIELDS},
         'conditions':{k:{**v,'state':condition_state(v)} for k,v in conditions.items()}}
    try:
        _,adapted=adapt_current(raw,sid,reference,environment)
        row['models']=[]
        for meta,implementation,model in models:
            prediction=implementation.predict_current(model,row['sample_id'],adapted['raw'])
            rules=prior.rule_rows(model,prediction,adapted)
            row['models'].append({**meta,'decision':prediction['decision'],'logical_state':prediction.get('logical_state'),
                                 'rules':rules,'triggered_rules':[r['clause_id'] for r in rules if r['state']=='T']})
    except Exception as exc:
        row['model_input_error']=type(exc).__name__+': '+str(exc)
        row['models']=[{**meta,'decision':'FAILED','reason':str(exc),'rules':[],'triggered_rules':[]} for meta,_,_ in models]
    prefixes=('app.web_data.navigator_layer.','app.web_data.screen_layer.','app.web_data.graphics_layer.',
              'app.web_data.automation_surface_layer.')
    row['major_non_target_fields']={f:deepcopy(v) for f,v in bound.get('features',{}).items() if f.startswith(prefixes)}
    if memory.NATIVE in bound.get('features',{}): row['major_non_target_fields'][memory.NATIVE]=bound['features'][memory.NATIVE]
    numeric=lambda v:type(v) in (int,float) and math.isfinite(v)
    observation=normal.observation_evidence(bound,TZ_FIELDS,value_predicates={relation.NATIVE_RAW:numeric,
        relation.WEB_OFFSET:numeric,relation.NATIVE_ZONE:lambda v:isinstance(v,str) and bool(v),
        relation.WEB_ZONE:lambda v:isinstance(v,str) and bool(v)})
    return row,bound,observation


def adjudicate_trio(members):
    """Only actual workflow/current observations determine effect and normality."""
    pre,mid,post=members
    basis=normal.normal_pre(pre['observation'],pre['workflow'])
    before,active,after=(m['observation'] for m in members)
    a,b,c=(o.get('values',{}) for o in (before,active,after))
    valid=all(o.get('valid') is True for o in (before,active,after))
    row=mid['row']; kind=row['process_type']
    web_changed=any(a.get(f)!=b.get(f) for f in (relation.WEB_ZONE,relation.WEB_OFFSET)) if valid else None
    native_changed=any(a.get(f)!=b.get(f) for f in (relation.NATIVE_ZONE,relation.NATIVE_RAW)) if valid else None
    system_values=[m['row']['operation'].get(key,{}).get('timezone_id')
                   for m in members for key in ('system_before','system_after')]
    system_same=all(v==system_values[0] for v in system_values) if all(system_values) else None
    major=set().union(*(m['row']['major_non_target_fields'].keys() for m in members))
    comparable=all(m['row']['major_non_target_fields'] for m in members)
    changes={f:[m['row']['major_non_target_fields'].get(f) for m in members] for f in sorted(major)
             if any(m['row']['major_non_target_fields'].get(f)!=pre['row']['major_non_target_fields'].get(f) for m in members[1:])}
    flow=mid['workflow']
    recovery_runtime=flow.get('after_rollback_runtime_observation') or {}
    clear_restored=(recovery_runtime.get('timezone_id')==a.get(relation.WEB_ZONE)
                    and recovery_runtime.get('timezone_offset')==a.get(relation.WEB_OFFSET)) if kind=='A' else True
    rollback={'verified':flow.get('cdp_rollback_verified') is True and flow.get('process_removed_verified') is True
              and post['workflow'].get('fresh_process_verified') is True and post['workflow'].get('system_operation_verified') is True
              and clear_restored and pre['row']['operation'].get('system_before',{}).get('timezone_id')
              ==post['row']['operation'].get('system_after',{}).get('timezone_id'),
              'from_operation_id':flow['operation_id'],'from_session_id':active.get('session_id'),
              'to_session_id':after.get('session_id'),'evidence_refs':flow.get('evidence_refs',[])+post['workflow'].get('evidence_refs',[])}
    pre['row']['normal_basis']=basis
    post['row']['normal_basis']=normal.normal_post(basis,after,post['workflow'],flow,rollback)
    if kind=='L':
        proof={'verified':flow.get('system_operation_verified') is True and flow.get('verified') is True,
               'from_session_id':before.get('session_id'),'to_session_id':active.get('session_id'),
               'expected_values':{relation.NATIVE_ZONE:row['target_timezone']},'evidence_refs':flow.get('evidence_refs',[])}
        row['normal_basis']=normal.normal_system_change(basis,active,flow,proof)
    else:
        row['normal_basis']={'supported':False,'kind':'web_only_intervention','reasons':['NOT_A_PLANNED_NORMAL_POSITION']}
    execution='EXECUTED' if flow.get('verified') else 'NOT_EXECUTED' if row['operation'].get('status')=='NOT_EXECUTED' else 'OPERATION_FAILED'
    effect='MISSING_OBSERVATION' if not valid else 'OBSERVABLE_CHANGE' if web_changed else 'NO_OBSERVABLE_EFFECT'
    confounded=bool(changes) or (kind=='A' and (native_changed or not system_same)) if comparable and valid else None
    evidence={'environment':row['environment'],'target_timezone':row['target_timezone'],'process_type':kind,
              'sample_ids':[m['row']['sample_id'] for m in members],'execution':execution,'effect':effect,
              'web_changed':web_changed,'native_changed':native_changed,'system_unchanged':system_same,
              'observable_intervention':kind=='A' and execution=='EXECUTED' and effect=='OBSERVABLE_CHANGE',
              'recovery':'RESTORED' if valid and a==c and rollback['verified'] else 'MISSING_OBSERVATION' if not valid else 'RECOVERY_NOT_VERIFIED',
              'confounded':confounded,'non_target_differences':changes,'major_non_target_field_count':len(major),
              'rollback_evidence':rollback,'normal_supported':[m['row']['normal_basis']['supported'] for m in members]}
    row['trio_evidence']=evidence
    row['observable_intervention']=evidence['observable_intervention']
    return evidence


def evaluate(out):
    settings=read(out/'SETTINGS.json'); local=collector.validate_settings(settings)
    if (out/'new_batch.jsonl.gz').exists(): raise FileExistsError('Saved local predictions exist; use summarize')
    models=model_set(out,settings); result=[];trios=[]
    for env in local['environments']:
        eid=env['environment_group_id'];run=out/'runs'/eid
        operations={o['step_id']:o for o in rows(run/'operations.jsonl') if o.get('step_id')}
        raw_index=defaultdict(list)
        for line,raw in enumerate(rows(run/'backend/raw_expanded_payloads.jsonl'),1):
            if raw.get('session_id'):raw_index[raw['session_id']].append((line,raw))
        life=read(run/'environment.json') if (run/'environment.json').exists() else {}
        members=[]
        for planned in collector.positions(local):
            op={**planned,**operations.get(planned['step_id'],{'status':'NOT_EXECUTED','cdp_status':'NOT_EXECUTED'})}
            found=raw_index.get(op.get('session_id'),[])
            raw=found[0][1] if len(found)==1 else {}
            reference=(str((run/'backend/raw_expanded_payloads.jsonl').relative_to(ROOT)) if run.is_relative_to(ROOT)
                       else str(run/'backend/raw_expanded_payloads.jsonl'))+':'+str(found[0][0] if len(found)==1 else 'missing')
            row,bound,observation=current_row(raw,op,reference,eid,models)
            receipt_path=run/(op['step_id']+'.cdp.json')
            try:receipt=read(receipt_path) if receipt_path.exists() else {}
            except (ValueError, OSError):receipt={}
            flow=workflow_proof(bound,raw,op,receipt,life.get('commands',[]),environment=eid,
                                run=run.relative_to(ROOT) if run.is_relative_to(ROOT) else run)
            row['workflow_evidence']=flow; row['valid_observation']=observation['valid']
            members.append({'row':row,'workflow':flow,'observation':observation})
            if len(members)==3:
                trios.append(adjudicate_trio(members));result.extend(m['row'] for m in members);members=[]
    if len(result)!=36:raise ValueError('ALL_36_FIXED_POSITIONS_MUST_BE_RETAINED')
    with gzip.open(out/'new_batch.jsonl.gz','xt') as stream:
        for row in result:stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    return summarize(out)


def group_stats(data):
    return {'n':len(data),'conditions':{name:{s:sum(r['conditions'][name]['state']==s for r in data)
              for s in ('T','F','U','FAILED')} for name in ('R_ABSOLUTE','R_TZ')},
            'models':{mid:{s:sum(next(m for m in r['models'] if m['model_id']==mid)['decision']==s for r in data)
                     for s in ('MANIPULATION_ALERT','NO_ALERT','INSUFFICIENT_EVIDENCE','FAILED','EMPTY_MODEL')}
                      for mid in sorted({m['model_id'] for r in data for m in r['models']})}}


def summarize(out):
    saved=rows(out/'new_batch.jsonl.gz');settings=collector.validate_settings(read(out/'SETTINGS.json'))
    expected={(e['environment_group_id'],p['step_id']) for e in settings['environments'] for p in collector.positions(settings)}
    if len(saved)!=len(expected) or {(r['environment'],r['step_id']) for r in saved}!=expected:
        raise ValueError('SAVED_LOCAL_MEMBERSHIP_MISMATCH')
    trios=[r['trio_evidence'] for r in saved if r.get('trio_evidence')]
    effective={t['sample_ids'][1] for t in trios if t['observable_intervention']}
    result={'planned_positions':36,'processed_positions':len(saved),'model_fit_calls':0,'recollection_calls':0,
            'raw_bound_positions':sum(r.get('source_binding',{}).get('binding_valid') is True for r in saved),
            'planned_normal_positions':30,'confirmed_normal_positions':sum(r['normal_basis']['supported'] for r in saved),
            'trios':trios,'all':group_stats(saved),
            'confirmed_normal':group_stats([r for r in saved if r['normal_basis']['supported']]),
            'normal_system_change':group_stats([r for r in saved if r['process_type']=='L' and r['phase']=='change' and r['normal_basis']['supported']]),
            'web_only_attempts':group_stats([r for r in saved if r['process_type']=='A' and r['phase']=='change']),
            'web_only_observable_changes':group_stats([r for r in saved if r['sample_id'] in effective]),
            'normal_evidence_exclusions':[{'sample_id':r['sample_id'],'reasons':r['normal_basis']['reasons']}
                 for r in saved if (r['process_type']=='L' or r['phase']!='change') and not r['normal_basis']['supported']],
            'by_environment_target_type_phase':{'/'.join(key):group_stats([r for r in saved if
                   (r['environment'],r['target_timezone'],r['process_type'],r['phase'])==key])
                 for key in sorted({(r['environment'],r['target_timezone'],r['process_type'],r['phase']) for r in saved})}}
    write(out/'LOCAL_EVALUATION.json',result)
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('evaluate','summarize'))
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args=parser.parse_args(); out=args.output_dir.resolve()
    result=evaluate(out) if args.command=='evaluate' else summarize(out)
    print(json.dumps({k:result[k] for k in ('planned_positions','raw_bound_positions','confirmed_normal_positions')}))


if __name__=='__main__':main()
