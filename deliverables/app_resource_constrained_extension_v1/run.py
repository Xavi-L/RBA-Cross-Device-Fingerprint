"""One finite selection, then historical evaluation; no raw collection or fitting."""
import argparse,sys,os,hashlib
from datetime import datetime,timezone
from rx_common import *
from rx_selector import select
import rx_sources as sources
import rx_prepare
def now():return datetime.now(timezone.utc).isoformat()
def run(out):
    out=Path(out).resolve();require(out.is_relative_to(HERE) and not out.exists(),'NEW_LOCAL_OUTPUT_REQUIRED');out.mkdir(parents=True)
    audit=Counter();start=now()
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError('OFFLINE_ONLY:'+event)
    def profile(frame,event,arg):
        if event!='call' or not frame.f_code.co_filename.startswith(str(ROOT)):return
        name=frame.f_code.co_name
        if name=='fit' or name.startswith('fit_') or name in ('train','collect','prepare_fold'):raise RuntimeError('NO_TRAIN_OR_COLLECTION:'+name)
        if frame.f_code.co_filename==str(HERE/'rx_selector.py'):
            if name=='select':audit['selection_learning_tasks']+=1
            if name=='score':audit['candidate_set_checks']+=1
        if name=='predict_current':raise RuntimeError('PREPARATION_MUST_REUSE_APP_OUTPUTS')
    sys.addaudithook(guard);sys.setprofile(profile)
    try:
        bases,locks=sources.freeze_models();write(out/'SETTINGS.json',SETTINGS)
        write(out/'FROZEN.json',dict(time=now(),source_head='1f05abe93fa76b74161d1653497d52d919d9f484',dependencies=locks,settings=SETTINGS,
            implementation={p.name:sources.digest(p) for p in HERE.glob('*.py')}))
        ms=rx_prepare.members();train=[m for m in ms if m['role']=='selection'];evaluation=[m for m in ms if m['role']=='historical_evaluation']
        ti,new,bindings=rx_prepare.prepare(train,bases,audit);ix=validate(train,ti,[b['model_id'] for b in bases],744)
        jsonl(out/'selection_members.jsonl',train);jsonl(out/'selection_inputs.jsonl',ti)
        jsonl(out/'new_conditions.jsonl',new);jsonl(out/'raw_binding_checks.jsonl',bindings)
        private=HERE/'private_runs';private.mkdir(exist_ok=True)
        write(private/'resource_alias_binding.json',sources.resource_bound()[1])
        models=[];checks=[];predictions=[]
        for b in bases:
            cs,winner,ps=select(b,train,ix);checks+=cs;predictions+=ps
            chosen=winner['extensions'] if winner else []
            payload=dict(base=b['model_id'],chosen=chosen,settings=SETTINGS,selection_ids=[m['sample_id'] for m in train],selection_input_digest=sources.digest(out/'selection_inputs.jsonl'))
            mid='resource-devext-'+hashlib.sha256(__import__('json').dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
            model=dict(schema='resource-constrained-extension-v1',model_id=mid,base_model_id=b['model_id'],
                base_ref=str((OLD/'results'/f"{b['model_id']}.json").relative_to(ROOT)),app_model_id=b['base_model_id'],fold=b['base']['fold'],
                extensions=chosen,selected_set=winner['set_id'] if winner else 'S0',
                status=('SELECTED_EXTENSION' if chosen else 'BASELINE_RETAINED') if winner else 'NO_FEASIBLE_SET',
                baseline_feasible=cs[0]['feasible'],selection_result=winner,base_rule_count=b['rule_count'],base_complexity=b['complexity'],
                rule_count=b['rule_count']+len(chosen),complexity=b['complexity']+2*len(chosen),
                added_clauses=[dict(literals=[dict(atom_id=CANDIDATES[c],polarity='POSITIVE')],complexity=2) for c in chosen],
                frozen_dependencies=locks,condition_source=str((RESOURCE/'conditions.py').relative_to(ROOT)),
                condition_version=locks[str((RESOURCE/'conditions.py').relative_to(ROOT))],settings_ref='SETTINGS.json',
                selection_members_ref='selection_members.jsonl',selection_inputs_ref='selection_inputs.jsonl',
                learning_performed=True,scope='development selection; historical evaluation is previously exposed normal material')
            models.append(model);write(out/(mid+'.json'),model)
        write(out/'models.json',models);write(out/'candidate_checks.json',checks)
        write(out/'SELECTION_FROZEN.json',dict(time=now(),model_ids=[m['model_id'] for m in models],selection_positions=744,
            evaluation_positions_admitted=0,learning_tasks=audit['selection_learning_tasks'],set_checks=audit['candidate_set_checks']))
        ei,extra,eb=rx_prepare.prepare(evaluation,bases,audit);require(not extra and not eb,'EVALUATION_SHOULD_REUSE_SAVED_STATES')
        allinputs=ti+ei;members=train+evaluation;ix=validate(members,allinputs,[b['model_id'] for b in bases],1005)
        for b in bases:
            for sid,chosen in SETS:
                for m in evaluation:
                    r=ix[m['sample_id']];predictions.append(dict(base_model_id=b['model_id'],set_id=sid,sample_id=m['sample_id'],state=combine(r['base_states'][b['model_id']],r['conditions'],chosen)))
        mi=index(members)
        for p in predictions:
            m=mi[p['sample_id']];p.update({k:m[k] for k in ('cohort','role','identity')});p['base_state']=ix[p['sample_id']]['base_states'][p['base_model_id']]
        require(set(index(predictions,lambda p:(p['sample_id'],p['base_model_id'],p['set_id'])))=={(m['sample_id'],b['model_id'],sid) for m in members for b in bases for sid,_ in SETS},'FULL_24120_CARTESIAN')
        jsonl(out/'members.jsonl',members);jsonl(out/'inputs.jsonl',allinputs);jsonl(out/'combinations.jsonl',predictions)
        selected=[]
        for model in models:
            for p in predictions:
                if p['base_model_id']==model['base_model_id'] and p['set_id']==model['selected_set']:
                    selected.append(dict(p,model_id=model['model_id'],model_status=model['status'],deployable=model['status']!='NO_FEASIBLE_SET'))
        jsonl(out/'selected_predictions.jsonl',selected)
        require(all(sources.digest(ROOT/p)==h for p,h in locks.items()),'FROZEN_SOURCE_CHANGED_AFTER_EXECUTION')
        audit['saved_state_combinations']=len(predictions)
        write(out/'EXECUTION.json',dict(status='COMPLETED',started=start,completed=now(),calls=dict(audit),
            new_raw_app_predictions=0,new_collection=0,app_fit=0,tree_fit=0,encoder_fit=0,
            finite_selection_is_learning=True,historical_sources_unchanged=True,
            resource_evaluate_semantics='each invocation returns all six original conditions; all six counted',
            prior_resource_execution_not_repeated={'app_predictions':972,'extra_MTC_conditions':18}))
    except Exception as e:
        write(out/'BLOCKED.json',dict(time=now(),reason=str(e),type=type(e).__name__,calls=dict(audit)))
        raise
    finally:sys.setprofile(None)
    from summarize import summarize
    summarize(out)
    print({'output':str(out),'selected':[(m['fold'],m['selected_set'],m['status']) for m in models],'calls':dict(audit)})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);run(p.parse_args().output)
