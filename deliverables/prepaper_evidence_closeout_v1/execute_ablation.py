"""Exactly three new original-selector tasks; full/S0 reuse, then 951 combinations."""
import argparse,copy,sys
from datetime import datetime,timezone
from collections import Counter
from closeout_io import *
from bridges import original_selector as s
from guards import audit_guard,profile_calls

def ablation_settings():
    settings=copy.deepcopy(s.SETTINGS)
    settings['normal_alarm_budgets']['b2b42']=34
    return settings

def freeze_sources():
    paths=[B2C/'selector.py',B2C/'inference.py',B2C/'prepare_current.py',B2C/'PROTOCOL.md',B2A/'conditions.py',B2A/'CANDIDATES_FROZEN.json',B2B/'ATTEMPT_SELECTION.json',ROOT/'hybridguard_agent/config/latest_experiment_protocol.v1.json']
    paths.extend(B3A/p for p in ('engine.py','features.py','PROTOCOL.md','VALIDATION.json'))
    paths.extend(B2C/'results'/p for p in ('models.json','members.jsonl','selection_members.jsonl','selection_inputs.jsonl','inputs.jsonl','candidate_checks.json','candidate_outputs.jsonl','predictions.jsonl','REPLAY_VERIFICATION.json'))
    paths.extend(B3A/'results'/p for p in ('models.json','features.jsonl','predictions.jsonl','SETTINGS.json','VERIFICATION.json'))
    for m in read(B2C/'results/models.json'):paths.append(ROOT/m['base']['path'])
    for m in read(B3A/'results/models.json'):paths.extend([B3A/'results'/m['path'],B3A/'results'/m['rules_path']])
    paths.extend(B3A/'results'/f'{p}_preprocessing.json' for p in ('P0','P1','P2'))
    return {ref(p):digest(p) for p in dict.fromkeys(paths)}

def execute(output):
    out=Path(output).resolve();require(out.is_relative_to(HERE) and not out.exists(),'NEW_LOCAL_OUTPUT_REQUIRED');out.mkdir()
    audit_guard(out);calls=profile_calls(True)
    old_models=read(B2C/'results/models.json');settings=ablation_settings()
    write(out/'SETTINGS.json',dict(settings=settings,only_change={'normal_alarm_budgets.b2b42':{'before':1,'after':34}},new_selection_tasks=3,candidate_checks=12,usage='ABLATION_ONLY',interpretation='Remove matched-normal alarm cap only, not deployment tolerance'))
    write(out/'FREEZE.json',dict(time=datetime.now(timezone.utc).isoformat(),sources=freeze_sources(),protocol_sha256=digest(HERE/'PROTOCOL.md'),historical_evaluation_admitted=False))
    members=rows(B2C/'results/selection_members.jsonl');inputs=index(rows(B2C/'results/selection_inputs.jsonl'))
    require(len(members)==690 and set(inputs)=={m['sample_id'] for m in members},'TRAIN_MEMBERSHIP')
    require(Counter(m['identity'] for m in members)=={'NORMAL':676,'EFFECTIVE_INTERVENTION':14},'TRAIN_IDENTITIES')
    require(sum(m['identity']=='NORMAL' and m['cohort']=='b2b42' for m in members)==34,'MATCHED_NORMAL_REMOVED')
    require(sum(m['identity']=='NORMAL' and m['scenario']=='L_BROWSER_LANG' and m['phase']=='change' for m in members)==2,'PREFERENCE_REMOVED')
    checks=[];candidate=[];models=[]
    old_checks=read(B2C/'results/candidate_checks.json')
    for fold,old in enumerate(old_models,1):
        mid=old['base_model_id'];base=old['base']
        cc,winner,pp=s.select(mid,members,inputs,base['rule_count'],base['complexity'],settings)
        checks+=cc;candidate+=pp
        require(winner is not None,'NO_FEASIBLE_ABLATION')
        s0=next(c for c in old_checks if c['base_model_id']==mid and c['set_id']=='S0');require(s0['feasible'],'ORIGINAL_S0_NOT_FEASIBLE')
        for setting,chosen,result in [('R_FULL',old['extensions'],old['selection_result']),('R_NO_CROSS',[],s0),('R_NO_MATCHED_NORMAL_CAP',winner['extensions'],winner)]:
            predictor=copy.deepcopy(old)
            if setting!='R_FULL':
                identity=dict(setting=setting,base_model_id=mid,extensions=chosen,settings=settings if setting.endswith('_CAP') else s.SETTINGS)
                new_id='paired244-ablation-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
                predictor.update(model_id=new_id,mode='ABLATION_ONLY',extensions=chosen,status='SELECTED_EXTENSION' if chosen else 'BASELINE_RETAINED',selected_set=result['set_id'],selection_result=result,rule_count=result['rule_count'],complexity=result['complexity'],usage='ABLATION_ONLY',deployment_eligible=False,conditions=[d for d in read(B2A/'CANDIDATES_FROZEN.json')['definitions'] if d['id'] in chosen],learning_performed=setting.endswith('_CAP'),settings=settings if setting.endswith('_CAP') else s.SETTINGS)
            wrapper=dict(setting=setting,fold=fold,model_id=predictor['model_id'],base_model_id=mid,usage='FROZEN_MAIN_REFERENCE' if setting=='R_FULL' else 'ABLATION_ONLY',predictor=predictor,
                source=ref(B2C/'results/models.json') if setting=='R_FULL' else ref(B2C/'results/candidate_checks.json') if setting=='R_NO_CROSS' else 'new_original_selector',input_scope='frozen_App_atoms_plus_'+('+'.join(chosen) or 'no_cross'),allowed_sets=['S0'] if setting=='R_NO_CROSS' else [k for k,_ in s.SETS])
            models.append(wrapper);write(out/(setting+f'_{fold:02d}.json'),wrapper)
    write(out/'models.json',models);write(out/'candidate_checks.json',checks);jsonl(out/'candidate_outputs.jsonl',candidate)
    write(out/'SELECTION_FROZEN.json',dict(time=datetime.now(timezone.utc).isoformat(),calls=dict(calls),historical_values_admitted=False,model_ids=[m['model_id'] for m in models],models_sha256=digest(out/'models.json')))
    # Only now admit development144/reserved117 values. They never enter select.
    all_members=rows(B2C/'results/members.jsonl');all_inputs=index(rows(B2C/'results/inputs.jsonl'))
    require(len(all_members)==951 and set(all_inputs)=={m['sample_id'] for m in all_members},'951_MEMBERSHIP')
    for m in members:require(m==index(all_members)[m['sample_id']],'DEVELOPMENT_MEMBER_CHANGED')
    old_predictions={(p['model_id'],p['sample_id']):p for p in rows(B2C/'results/predictions.jsonl')}
    old_s0={(p['base_model_id'],p['sample_id']):p['state'] for p in rows(B2C/'results/candidate_outputs.jsonl') if p['set_id']=='S0'}
    predictions=[]
    for model in models:
        selected=model['predictor']['extensions'];mid=model['base_model_id']
        for member in all_members:
            sid=member['sample_id'];inp=all_inputs[sid];base=inp['base_states'][mid]
            if model['setting']=='R_FULL':value=old_predictions[model['model_id'],sid]['state'];execution='reused_verified_R_FULL'
            elif model['setting']=='R_NO_CROSS':
                value=base;execution='reused_verified_S0_base'
                if member['role']=='selection':require(value==old_s0[mid,sid],'S0_REPLAY_MISMATCH')
            else:value=s.combine(base,inp['conditions'],selected);execution='new_saved_state_combination'
            predictions.append(dict(sample_id=sid,model_id=model['model_id'],base_model_id=mid,setting=model['setting'],fold=model['fold'],state=value,base_state=base,selected_conditions={c:inp['conditions'][c] for c in selected},role=member['role'],execution=execution,input_reference=ref(B2C/'results/inputs.jsonl',list(all_inputs).index(sid)+1)))
    jsonl(out/'members.jsonl',all_members);jsonl(out/'predictions.jsonl',predictions)
    require(calls['select']==3 and calls['score']==12,'NEW_SELECTION_COUNTS')
    sys.setprofile(None)
    write(out/'EXECUTION.json',dict(status='PASSED',calls=dict(calls),new_selection_tasks=3,candidate_checks=12,new_prediction_combinations=2853,reused_full_predictions=2853,reused_base_predictions=2853,tree_fit=0,app_fit=0,encoder_fit=0,collection=0,positions=951,development=690,historical_evaluation=261))
    print(json.dumps({'new_winners':[(m['fold'],m['predictor']['selected_set']) for m in models if m['setting'].endswith('_CAP')],'calls':dict(calls)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'results');execute(p.parse_args().output)
