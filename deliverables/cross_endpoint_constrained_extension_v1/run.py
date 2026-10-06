#!/usr/bin/env python3
"""One actual finite selection followed by replay; never changes historical files."""
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from collections import Counter
from common import *
from selector import SETTINGS, select
from inference import predict_saved

def run(output):
    import adapter as a
    from summarize import summarize
    out=Path(output).resolve();require(not out.exists(),'NEW_OUTPUT_DIRECTORY_REQUIRED')
    require(out.is_relative_to(HERE),'OUTPUT_MUST_BE_IN_THIS_DELIVERABLE')
    out.mkdir(parents=True)
    started=datetime.now(timezone.utc).isoformat(); calls=Counter();events=[]
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):
            events.append(event);raise RuntimeError('PROHIBITED:'+event)
        if event=='open':
            path,mode,flags=args
            if not isinstance(path,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                if not Path(os.fsdecode(path)).resolve().is_relative_to(out): raise RuntimeError('WRITE_OUTSIDE_NEW_OUTPUT')
    def profile(frame,event,arg):
        if event!='call': return
        path=frame.f_code.co_filename;name=frame.f_code.co_name
        if str(ROOT) not in path:return
        if name=='fit' or name.startswith('fit_') or name in ('train','prepare_fold','collect'):
            raise RuntimeError('FORBIDDEN_ORIGINAL_TRAINING_OR_COLLECTION:'+name)
        if path==str(HERE/'selector.py') and name=='select': calls['incremental_learning_tasks']+=1
        if path==str(HERE/'selector.py') and name=='score': calls['candidate_set_checks']+=1
        if path==str(HERE/'inference.py') and name=='predict_saved':calls['new_selected_model_combinations']+=1
        if path.endswith('/mtc_timezone_selection.py') and name=='predict_current':calls['new_raw_app_predictions']+=1
        if path==str(a.b2a.HERE/'conditions.py') and name=='evaluate':calls['new_raw_condition_predictions']+=1
    sys.addaudithook(guard);sys.setprofile(profile)
    bases,manifest=a.freeze()
    write(out/'SETTINGS.json',SETTINGS)
    write(out/'BASE_MODELS.json',manifest)
    write(out/'PRE_SELECTION_FREEZE.json',dict(time=datetime.now(timezone.utc).isoformat(),settings=SETTINGS,
        implementation={ref(p):digest(p) for p in HERE.glob('*.py')}, protocol_sha256=digest(HERE/'PROTOCOL.md'),
        no_evaluation_members_admitted=True, failure_semantics='selected FAILED has priority, then original Kleene OR'))
    small_m,small_i=a.small_cohorts(bases)
    train_m,train_i=a.mtc_cohorts(bases,('discovery',))
    members=train_m+small_m; inputs=train_i+small_i
    require(len(members)==690 and Counter(m['identity'] for m in members)=={'NORMAL':676,'EFFECTIVE_INTERVENTION':14},'DEVELOPMENT_DENOMINATORS')
    lookup=unique(inputs,lambda x:x['sample_id']);unique(members,lambda x:x['sample_id'])
    jsonl(out/'selection_members.jsonl',members);jsonl(out/'selection_inputs.jsonl',inputs)
    train_ids=[m['sample_id'] for m in members]
    # Physical material is retained by reference; group metadata stays out of inference.
    groups={}
    for m in members:groups.setdefault(m['group_id'],[]).append(m['sample_id'])
    require(all(len(v)==3 for k,v in groups.items() if not k.startswith('mtc-group-')),'INCOMPLETE_SCENARIO_GROUP')
    write(out/'selection_groups.json',groups)
    models=[]; all_checks=[]; candidate_outputs=[]
    for base,m in zip(bases,manifest):
        checks,winner,outputs=select(base.model_id,members,lookup,m['rule_count'],m['complexity'])
        all_checks.extend(checks);candidate_outputs.extend(outputs)
        chosen=winner['extensions'] if winner else None
        identity=dict(base_model_id=base.model_id,extensions=chosen,settings=SETTINGS,train_ids=train_ids,
            base_sha256=m['sha256'],selection_data_sha256=digest(out/'selection_inputs.jsonl'))
        mid='paired244-devext-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
        model=dict(schema='paired244-development-extension-v1',model_id=mid,mode=MODE,
            base_model_id=base.model_id,base=m,extensions=chosen,
            status=('SELECTED_EXTENSION' if chosen else 'BASELINE_RETAINED') if winner else 'NO_FEASIBLE_SET',
            selection_result=winner,selected_set=winner['set_id'] if winner else None,
            settings_ref='SETTINGS.json',train_members_ref='selection_members.jsonl',train_ids=train_ids,
            selection_inputs_sha256=identity['selection_data_sha256'],settings=SETTINGS,
            conditions=[d for d in read(a.b2a.HERE/'CANDIDATES_FROZEN.json')['definitions'] if d['id'] in (chosen or [])],
            condition_source=dict(path=ref(a.b2a.HERE/'conditions.py'),sha256=digest(a.b2a.HERE/'conditions.py')),
            rule_count=winner['rule_count'] if winner else None,complexity=winner['complexity'] if winner else None,
            no_new_app_fit=True,no_new_encoder_fit=True,learning_performed=True,
            scope='Development extension only; not original B_REL_TZ, not new CV or blind validation')
        models.append(model)
        write(out/(mid+'.json'),model)
    write(out/'models.json',models);write(out/'candidate_checks.json',all_checks)
    jsonl(out/'candidate_outputs.jsonl',candidate_outputs)
    write(out/'SELECTION_FROZEN.json',dict(time=datetime.now(timezone.utc).isoformat(),model_ids=[m['model_id'] for m in models],
        models_sha256=digest(out/'models.json'),learning_tasks=calls['incremental_learning_tasks'],candidate_set_checks=calls['candidate_set_checks'],
        development_positions=len(members),historical_evaluation_positions_admitted=0))
    # Held-out historical values are adapted only after selection results have been persisted.
    eval_m,eval_i=a.mtc_cohorts(bases,('development','reserved_validation'))
    members+=eval_m;inputs+=eval_i
    require(len(members)==951,'FINAL_951_MEMBERS')
    jsonl(out/'members.jsonl',members);jsonl(out/'inputs.jsonl',inputs)
    lookup=unique(inputs,lambda r:r['sample_id'])
    predictions=[]
    for model in models:
        for member in members:
            sid=member['sample_id'];item=lookup[sid];bs=item['base_states'][model['base_model_id']]
            s=predict_saved(model,bs,item['conditions']) if model['status']!='NO_FEASIBLE_SET' else 'FAILED'
            predictions.append(dict(sample_id=sid,base_model_id=model['base_model_id'],model_id=model['model_id'],
                base_state=bs,state=s,selected_conditions={c:item['conditions'][c] for c in (model['extensions'] or [])},
                failure_reason='NO_FEASIBLE_SET' if model['status']=='NO_FEASIBLE_SET' else 'SELECTED_INPUT_FAILED' if s=='FAILED' else None,
                execution='new_current_pair_OR_from_validated_saved_states'))
    jsonl(out/'predictions.jsonl',predictions)
    sys.setprofile(None)
    sources={**a.b2a.USED,**a.USED}
    write(out/'SOURCE_MANIFEST.json',dict(source_files=sources,base_models=manifest,
        versions={'pilot_app':16,'b2b_app':16,'mtc_app':[9,11],'pilot_browser':'expanded-web-67-v2','b2b_browser':'expanded-web-67-v2','mtc_browser':'expanded-web-67-v1'},
        privacy='No new complete raw payloads/tickets/operation logs copied; B2B private references local-only'))
    write(out/'EXECUTION.json',dict(started_at=started,completed_at=datetime.now(timezone.utc).isoformat(),mode=MODE,
        calls=dict(calls),saved_state_validation=dict(a.AUDIT),
        reused_base_predictions=2853,reused_condition_predictions=1902,
        new_raw_app_predictions=calls['new_raw_app_predictions'],new_raw_condition_predictions=calls['new_raw_condition_predictions'],
        app_fit_calls=0,encoder_fit_calls=0,collection_calls=0,finite_selection_is_learning=True,
        input_positions=951,development_positions=690,historical_evaluation_positions=261,
        independent_sample_multiplier=1,guarded=True,forbidden_events=events))
    summarize(out,out/'summary')
    print(json.dumps({'models':[(m['selected_set'],m['status']) for m in models],'calls':dict(calls)},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'results');args=p.parse_args();run(args.output)
