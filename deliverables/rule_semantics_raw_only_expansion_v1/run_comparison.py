#!/usr/bin/env python3
"""Execute one frozen raw-only comparison; unique jobs, own-train inputs only."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
GROUPS=('BASE','LANG_ADD_WD_REPLACE')


def read(path):return json.loads(Path(path).read_text())
def write(path,data):
    with Path(path).open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def stamp():return datetime.now(timezone.utc).isoformat()
def require(ok,reason):
    if not ok:raise ValueError(reason)


def gate(directory):
    contract=read(directory/'CONTRACT.json');grant=read(HERE/'EXECUTION_AUTHORIZATION.json')
    require(contract['readiness']=='RAW_ONLY_COMPARISON_READY','DATA_NOT_READY')
    require(grant.get('training_authorized') is True and grant.get('admission_authorized') is True,'EXPLICIT_USER_AUTHORIZATION_REQUIRED')
    require(grant.get('experiment_id')==contract['experiment_id'] and grant.get('sample_ids')==contract['sample_ids']
            and grant.get('job_ids')==[j['job_id'] for j in contract['jobs']] and grant.get('authorization_ref'),'AUTHORIZATION_MEMBERSHIP_MISMATCH')
    require(len(contract['sample_ids'])==len(set(contract['sample_ids']))==378 and len(contract['jobs'])==12,'EXACT_REGISTERED_LAYOUT_REQUIRED')
    require(len({j['job_id'] for j in contract['jobs']})==12 and len(contract['folds'])==3,'UNIQUE_FOLDS_JOBS_REQUIRED')
    require(Counter((j['fold_id'],j['group_id'],j['stage']) for j in contract['jobs'])
            ==Counter((f['fold_id'],g,s) for f in contract['folds'] for g in GROUPS for s in ('SPARSE','RETENTION')),'EXACT_GROUP_STAGE_FOLD_JOBS_REQUIRED')
    require(set(contract['source_modes'])==set(contract['sample_ids']) and set(contract['source_modes'].values())=={'raw_observation_v1'},'RAW_ONLY_MEMBERS_REQUIRED')
    for job in contract['jobs']:
        require(len(job['train_ids'])==252 and len(job['outer_test_ids'])==126
                and not set(job['train_ids'])&set(job['outer_test_ids'])
                and set(job['train_ids'])|set(job['outer_test_ids'])==set(contract['sample_ids']),'INVALID_OUTER_SPLIT')
        fold=next(f for f in contract['folds'] if f['fold_id']==job['fold_id'])
        require(job['train_ids']==fold['train_ids'] and job['outer_test_ids']==fold['outer_test_ids'],'JOB_DIFFERS_FROM_REGISTERED_FOLD')
    prior=read(ROOT/'deliverables/rule_semantics_combination/EXECUTION.json')
    require(prior['cumulative_fit_jobs']==177 and prior['remaining_research_fits']==23,'SHARED_PRIOR_BUDGET_CHANGED')
    require(read(HERE/'EFFECT_AUDIT.json')['status']=='PRIMARY_EFFECTS_PASS','INDEPENDENT_EFFECT_REVIEW_REQUIRED')
    return contract,grant


def worker(directory,job_id):
    contract,grant=gate(directory)
    require((directory/'RUN_STARTED.json').exists(),'DISPATCH_NOT_REGISTERED')
    jobs={j['job_id']:j for j in contract['jobs']}
    require(job_id in jobs,'UNREGISTERED_JOB')
    job=deepcopy(jobs[job_id]);dest=directory/'trials'/job_id;dest.mkdir(parents=True,exist_ok=False)
    from hybridguard_agent.research import rule_semantics_mixed_retraining as engine
    started=time.monotonic();events=[];fits=predictions=0;outcome='FAILED';error=None;phase='TRAIN'
    def event(name,**values):events.append({'event':name,'utc':stamp(),**values})
    def input_row(oid):
        require(oid in job['train_ids'] or phase=='FROZEN' and oid in job['outer_test_ids'],'HELDOUT_INPUT_OPEN_BEFORE_FREEZE')
        row=read(directory/'inputs'/f'{oid}.json')
        require(row['opaque_id']==oid and row['observation_mode']=='raw_observation_v1','INPUT_ID_MODE_MISMATCH')
        return row
    def metadata(oid):
        require(oid in job['train_ids'] or phase=='PREDICTIONS_CLOSED' and oid in job['outer_test_ids'],'HELDOUT_LABEL_OPEN_BEFORE_PREDICTIONS_CLOSE')
        row=read(directory/'evaluation'/f'{oid}.json')
        require(row['proposed_supervised_member'] is True and row['fit_permission']=='DENIED_PREPARATION_ONLY','UNREGISTERED_LABEL')
        require(type(row['proposed_supervised_label']) is int and row['proposed_supervised_label']==int(row['phase']=='attack'),'LABEL_PHASE_MISMATCH')
        return {**row,'supervised_label':row['proposed_supervised_label'],'fit_permission':'ONLY_WHEN_IN_REGISTERED_OUTER_TRAIN','label_authorization_ref':grant['authorization_ref']}
    binding={'study_version':contract['engine_study_version'],'phase':contract['engine_phase'],
             'experiment_id':contract['experiment_id'],'group_id':job['group_id'],
             'method_id':'GREEDY_OR' if job['stage']=='SPARSE' else 'R_KEEP_V1',
             'fold_id':job['fold_id'],'split_id':'RAW-LOEO-v1','operating_point':'OP05',
             'model_unit_id':job_id,'evaluation_role':contract['evaluation_role'],'input_manifest_ref':str(directory/'CONTRACT.json')}
    try:
        selected={i:input_row(i) for i in job['train_ids']}
        labels={i:metadata(i) for i in job['train_ids']}
        event('TRAIN_ONLY_INPUTS_OPENED',train_ids=job['train_ids'],heldout_inputs_opened=0,heldout_metadata_opened=0)
        kwargs={'group':job['group_id'],'binding':binding,'source_modes':{i:'raw_observation_v1' for i in job['train_ids']},
                'candidate_rows':None if job['group_id']=='BASE' else {i:r['candidate_cells'] for i,r in selected.items()}}
        if job['stage']=='RETENTION':
            initial=directory/'trials'/job['initializer']
            require(read(initial/'receipt.json')['outcome'] in ('FITTED','EMPTY_MODEL'),'INITIALIZER_NOT_READY')
            job['initial_model_ref']=str(initial/'model.json')
            kwargs.update(initial_model=engine.load_model(initial/'model.json'),initial_training=read(initial/'training.json'))
        write(dest/'FIT_STARTED.json',{'at':stamp(),'count':1,'job_id':job_id});fits=1
        method=engine.fit_sparse if job['stage']=='SPARSE' else engine.fit_retention
        model,training=method(job,{i:r['features'] for i,r in selected.items()},labels,read(directory/'DEFINITIONS.json'),**kwargs)
        write(dest/'training.json',training);engine.save_model(model,dest/'model.json');model=engine.load_model(dest/'model.json')
        require(model.fit['train_ids']==job['train_ids'] and model.status in ('FITTED','EMPTY_MODEL'),'FIT_FAILED_OR_WRONG_MEMBERS')
        phase='FROZEN';event('MODEL_SAVED_RELOADED_FROZEN',model_id=model.model_id)
        results=[]
        with (dest/'predictions.jsonl').open('x') as stream, (dest/'PREDICTION_CALLS.jsonl').open('x') as calls:
            for oid in (job['outer_test_ids'] if job['stage']=='RETENTION' else []):
                row=input_row(oid);predictions+=1
                calls.write(json.dumps({'opaque_id':oid,'at':stamp()})+'\n');calls.flush()
                result=engine.predict_current(model,oid,row['features'],candidate_cells=None if job['group_id']=='BASE' else row['candidate_cells'],source_mode='raw_observation_v1')
                stream.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();results.append(result)
                require(result['decision']!='FAILED','PREDICTION_FAILED:'+oid)
        phase='PREDICTIONS_CLOSED';event('PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN',count=len(results))
        evaluation=[]
        for result in results:
            meta=metadata(result['opaque_id'])
            evaluation.append({**{k:meta[k] for k in ('opaque_id','supervised_label','phase','environment_group_id','config_id','bundle_id','triplet_id')},'decision':result['decision']})
        write(dest/'evaluation_rows.json',evaluation)
        event('HELDOUT_METADATA_JOINED_AFTER_CLOSE',count=len(evaluation));outcome=model.status
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()};write(dest/'ERROR.json',error)
    event('JOB_CLOSED',outcome=outcome);write(dest/'access_log.json',events)
    receipt={'job_id':job_id,'group_id':job['group_id'],'fold_id':job['fold_id'],'stage':job['stage'],'outcome':outcome,
             'actual_fit_invocations':fits,'actual_prediction_calls':predictions,'expected_prediction_calls':job['max_prediction_calls'],
             'charged_seconds':time.monotonic()-started,'attempt':1,'error':error}
    write(dest/'receipt.json',receipt);return receipt


def summarize(directory,contract):
    groups={};saved={}
    for group in GROUPS:
        rows=[];fold_rows=[]
        for job in contract['jobs']:
            if job['group_id']!=group or job['stage']!='RETENTION':continue
            dest=directory/'trials'/job['job_id']
            if not (dest/'evaluation_rows.json').exists():continue
            current=read(dest/'evaluation_rows.json');rows.extend(current)
            model=read(dest/'model.json')
            fold_rows.append({'fold_id':job['fold_id'],'heldout_environment':job['heldout_environment'],
                              'attack_alerts':sum(r['phase']=='attack' and r['decision']=='MANIPULATION_ALERT' for r in current),
                              'attack_n':sum(r['phase']=='attack' for r in current),'clauses':model['clauses']})
        attack=[r for r in rows if r['phase']=='attack'];clean=[r for r in rows if r['phase']!='attack']
        cfg=defaultdict(list)
        for row in attack:cfg[row['config_id']].append(row['decision']=='MANIPULATION_ALERT')
        tp=sum(r['decision']=='MANIPULATION_ALERT' for r in attack)
        groups[group]={'attack_alerts':tp,'attack_n':len(attack),'tpr':tp/len(attack) if attack else None,
                       'clean_alerts':sum(r['decision']=='MANIPULATION_ALERT' for r in clean),'clean_n':len(clean),
                       'defined':sum(r['decision'] in ('MANIPULATION_ALERT','NO_ALERT') for r in rows),'expected':378,
                       'decisions':dict(Counter(r['decision'] for r in rows)),
                       'macro_tpr':sum(sum(v)/len(v) for v in cfg.values())/len(cfg) if cfg else None,
                       'configurations':{k:{'alerts':sum(v),'n':len(v)} for k,v in sorted(cfg.items())},'folds':fold_rows}
        saved[group]={r['opaque_id']:r for r in rows}
    changed=[{'opaque_id':i,'base':saved['BASE'][i]['decision'],'combination':saved['LANG_ADD_WD_REPLACE'][i]['decision'],'phase':saved['BASE'][i]['phase']}
             for i in sorted(set(saved['BASE'])&set(saved['LANG_ADD_WD_REPLACE'])) if saved['BASE'][i]['decision']!=saved['LANG_ADD_WD_REPLACE'][i]['decision']]
    result={'evaluation_role':contract['evaluation_role'],'groups':groups,'changed_decisions':changed,
            'attack_alert_delta':groups['LANG_ADD_WD_REPLACE']['attack_alerts']-groups['BASE']['attack_alerts'],
            'scope':'New matched raw-only 14-configuration development cohort; not improvement relative to historical 45/54, independent confirmation, or normal App population FPR.'}
    write(directory/'RESULTS.json',result);return result


def run(directory):
    contract,grant=gate(directory)
    write(directory/'RUN_STARTED.json',{'at':stamp(),'authorization_ref':grant['authorization_ref'],'jobs':12})
    receipts=[];stop=None
    for job in contract['jobs']:
        started=time.monotonic()
        try:
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',job['job_id'],'--directory',str(directory)],capture_output=True,text=True,timeout=90)
            receipt_path=directory/'trials'/job['job_id']/'receipt.json'
            if not receipt_path.exists():raise RuntimeError('Worker did not close receipt: '+result.stderr[-2000:])
            receipt=read(receipt_path);receipts.append(receipt)
            print(job['job_id'],receipt['outcome'],flush=True)
            if result.returncode or receipt['outcome'] not in ('FITTED','EMPTY_MODEL'):raise RuntimeError('Worker failed')
        except Exception as error:
            stop={'job_id':job['job_id'],'reason':str(error),'wall_seconds':time.monotonic()-started};break
    attempted=[p for p in (directory/'trials').glob('*/FIT_STARTED.json')]
    fits=len(attempted);charged=sum(r['charged_seconds'] for r in receipts)
    if stop and stop['job_id'] not in {r['job_id'] for r in receipts}:charged+=stop['wall_seconds']
    execution={'execution_complete':stop is None and len(receipts)==12,'stop_reason':stop,'actual_fit_jobs':fits,
               'actual_prediction_calls':sum(r['actual_prediction_calls'] for r in receipts),'unexecuted_jobs':12-len(receipts),
               'cumulative_fit_jobs':177+fits,'remaining_research_fits':23-fits,'charged_seconds':charged,
               'cumulative_charged_seconds':contract['budget']['base_charged_seconds']+charged,'additional_retries':0,'receipts':receipts}
    write(directory/'EXECUTION.json',execution)
    if execution['execution_complete']:print(json.dumps(summarize(directory,contract),ensure_ascii=False,indent=2))
    else:print(json.dumps(execution,ensure_ascii=False,indent=2));raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,default=HERE/'prepared')
    parser.add_argument('--run',action='store_true');parser.add_argument('--worker')
    args=parser.parse_args()
    if args.worker:worker(args.directory,args.worker)
    elif args.run:run(args.directory)
    else:print(json.dumps({'mode':'READ_ONLY','contract_present':(args.directory/'CONTRACT.json').exists(),'execution_started':(args.directory/'RUN_STARTED.json').exists()}))
