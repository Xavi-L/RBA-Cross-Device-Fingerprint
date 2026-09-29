#!/usr/bin/env python3
"""One authorized combined pool, three sparse initializers and three R_KEEP fits."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from deliverables.rule_semantics_rkeep_retraining import run_experiment as saved_runner

stamp, read, lines = saved_runner.stamp, saved_runner.read, saved_runner.lines
write, canonical, digest = saved_runner.write, saved_runner.canonical, saved_runner.digest
candidate_subset = saved_runner.candidate_subset
FROZEN = saved_runner.FROZEN
PRIOR = 'deliverables/rule_semantics_rkeep_retraining'
GROUP = 'LANG_ADD_WD_REPLACE'
CONTROLS = ('BASE', 'LANG_ADD', 'WD_REPLACE')
STUDY = 'rule-semantics-combination-v1'
PHASE = 'RSR_COMBINATION'
ROLE = 'EXPOSED_RETROSPECTIVE_DEVELOPMENT'


def prepare(directory):
    if (directory/'CONTRACT.json').exists(): raise FileExistsError('CONTRACT_ALREADY_REGISTERED')
    tests = read(directory/'TEST_RESULTS.json')
    if tests['status'] != 'PASS' or tests['exit_code'] != 0: raise ValueError('TESTS_NOT_PASSED')
    previous = read(ROOT/PRIOR/'CONTRACT.json')
    budget = read(ROOT/PRIOR/'EXECUTION.json')
    if (not budget['execution_complete'] or budget['stop_reason']
            or not all(r['passed'] for r in budget['baseline_equivalence'])
            or budget['remaining_research_fits'] < 6 or budget['remaining_research_seconds'] < 540):
        raise ValueError('PREVIOUS_EXECUTION_NOT_SETTLED_OR_BUDGET_INSUFFICIENT')
    ids = previous['sample_ids']
    folds = [f for f in read(ROOT/previous['split_manifest_ref'])['folds'] if f['split_id']=='LOEO-v1']
    if len(ids)!=162 or len(set(ids))!=162 or [f['fold_id'] for f in folds]!=['LOEO-v1-01','LOEO-v1-02','LOEO-v1-03']:
        raise ValueError('FIXED_SCOPE_CONFLICT')
    if len([sid for f in folds for sid in f['outer_test']])!=162 or {sid for f in folds for sid in f['outer_test']}!=set(ids):
        raise ValueError('OOF_PARTITION_CONFLICT')
    for f in folds:
        if set(f['train']) & set(f['outer_test']) or set(f['train']) | set(f['outer_test']) != set(ids):
            raise ValueError('FOLD_SCOPE_CONFLICT')
    controls = []
    for group in CONTROLS:
        for f in folds:
            old = next(j for j in previous['jobs'] if j['group_id']==group and j['fold_id']==f['fold_id'])
            if old['train_ids']!=f['train'] or old['outer_test_ids']!=f['outer_test']:
                raise ValueError('CONTROL_SPLIT_MISMATCH')
            ref = f'{PRIOR}/trials/{old["job_id"]}'
            receipt = read(ROOT/ref/'receipt.json')
            if receipt['outcome']!='FITTED' or not receipt['predictions_closed']:
                raise ValueError('CONTROL_NOT_COMPLETED')
            controls.append({'group_id':group,'fold_id':f['fold_id'],'ref':ref,
                             'train_ids':f['train'],'outer_test_ids':f['outer_test']})
    jobs = []
    for stage, method in [('SPARSE','GREEDY_OR'),('RETENTION','R_KEEP_V1')]:
        for f in folds:
            jobs.append({'job_id':stage+'__'+f['fold_id'],'group_id':GROUP,'stage':stage,'method_id':method,
                'fold_id':f['fold_id'],'train_ids':f['train'],'outer_test_ids':f['outer_test'],
                'prediction_ids':f['outer_test'] if stage=='RETENTION' else [],
                'initial_model_ref':str((directory/'trials'/('SPARSE__'+f['fold_id'])/'model.json').relative_to(ROOT)) if stage=='RETENTION' else None,
                'initial_job_id':'SPARSE__'+f['fold_id'] if stage=='RETENTION' else None,'attempt':1})
    dependencies = [str(Path(__file__).resolve().relative_to(ROOT)),
        'hybridguard_agent/research/rule_semantics_combination.py',
        'hybridguard_agent/research/rule_semantics_retraining.py',
        'hybridguard_agent/research/rule_semantics_rkeep_retraining.py',
        'hybridguard_agent/research/rule_semantics_revision_v1/contracts.py',
        'deliverables/rule_semantics_rkeep_retraining/run_experiment.py',
        *['hybridguard_agent/research/rule_learning/'+n+'.py' for n in
          ('contracts','models','selector','predictor','baselines','fold_data','evaluation')],
        *['hybridguard_agent/research/rule_learning_v2/'+n+'.py' for n in ('adapter','b_engine','retention')],
        *['hybridguard_agent/config/rule_learning_v1_20260924/'+n+'.json' for n in ('learning_search_space','candidate_grammar')],
        previous['source_index'],previous['definitions_ref'],previous['split_manifest_ref'],previous['candidate_cache_ref'],
        PRIOR+'/CONTRACT.json',PRIOR+'/EXECUTION.json',str((directory/'TEST_RESULTS.json').relative_to(ROOT))]
    dependencies += [c['ref']+'/'+n for c in controls for n in ('model.json','predictions.jsonl','receipt.json')]
    identities = [{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in dependencies]
    contract = {'schema_version':'rsr-combination-contract-v1','registered_at':stamp(),
        'starting_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'authorization':'User requested LANG_ADD plus WD_REPLACE on the fixed R_KEEP evaluation. New combination only; three own-pool GREEDY initializers followed by three R_KEEP fits.',
        'study_version':STUDY,'phase':PHASE,'group_id':GROUP,'sample_ids':ids,'evaluation_role':ROLE,
        'source_index':previous['source_index'],'definitions_ref':previous['definitions_ref'],
        'split_manifest_ref':previous['split_manifest_ref'],'candidate_cache_ref':previous['candidate_cache_ref'],
        'candidate_cache_offsets':previous['candidate_cache_offsets'],'candidate_versions':previous['candidate_versions'],
        'candidate_change':'W0 + fixed language-first atom + legacy webdriver-state atom - old webdriver EQ:True; keep complete old language-length family.',
        'signal_groups':{'RSR-LANG-FIRST-v1':'language_preferences','RSR-WEBDRIVER-STATE-v1':'automation_flag'},
        'family_policy':previous['family_policy'],'search_space':previous['search_space'],'grammar':previous['grammar'],
        'retention':previous['retention'],'operating_point':'OP05','jobs':jobs,'saved_controls':controls,
        'execution_order':'Three own-pool sparse train-only fits, then three retention fits using matching saved sparse model/encoder. Only retention models produce held-out predictions.',
        'metrics':'Original full-denominator OOF metrics; paired comparisons to BASE, LANG_ADD and WD_REPLACE; descriptive interaction (combo-LANG_ADD)-(WD_REPLACE-BASE). Unknown or failed outcomes stay explicit.',
        'exposure':'Already exposed retrospective development; no independent confirmation or causal population interaction claim.',
        'failure_policy':'Preserve every attempted fit and partial prediction; stop after failure, no automatic retry or semantic/budget relaxation.',
        'budget':{'prior_ledger_ref':PRIOR+'/EXECUTION.json','base_fit_jobs':budget['cumulative_fit_jobs'],
            'base_charged_seconds':budget['cumulative_charged_seconds'],'max_new_fits':6,
            'max_sparse_fits':3,'max_retention_fits':3,'max_prediction_calls':162,
            'max_worker_seconds':90,'max_stage_seconds':540,'global_max_fits':200,'global_max_seconds':21600},
        'prohibited':['refit controls','sparse heldout predictions','new candidate calls','new collection','raw webdriver mode','LOCO','independent confirmation','full-development fit','old artifact mutation','commit','push'],
        'file_identities':identities}
    write(directory/'CONTRACT.json',contract)
    return {'status':'REGISTERED_BEFORE_FITS','jobs':6,'predictions':162,'contract_sha256':digest(contract)}


def validate_contract(c):
    if c['study_version']!=STUDY or len(c['jobs'])!=6: raise ValueError('CONTRACT_IDENTITY_CONFLICT')
    for f in c['file_identities']:
        if hashlib.sha256((ROOT/f['path']).read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('REGISTERED_DEPENDENCY_CHANGED:'+f['path'])


def worker(directory, job_id):
    from hybridguard_agent.research import rule_semantics_combination as engine
    c=read(directory/'CONTRACT.json');j=next(x for x in c['jobs'] if x['job_id']==job_id)
    d=directory/'trials'/job_id;d.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();events=[];fit_calls=0;pred_calls=0;predictions=[];error=None;stage_calls=0;threshold_calls=0
    def event(name,**kwargs): events.append({'event':name,'utc':stamp(),**kwargs})
    binding={'study_version':STUDY,'phase':PHASE,'group_id':GROUP,'method_id':j['method_id'],
        'fold_id':j['fold_id'],'split_id':'LOEO-v1','operating_point':'OP05','evaluation_role':ROLE,
        'protocol_digest':digest(c),'candidate_version':'RSR_FIXED_CACHE_1.0.0','model_unit_id':job_id,
        'input_manifest_ref':c['source_index']}
    try:
        index=read(ROOT/c['source_index']);base=(ROOT/c['source_index']).parent
        raw={sid:read(base/index[sid]['features'])['features'] for sid in j['train_ids']}
        meta={sid:read(base/index[sid]['evaluation']) for sid in j['train_ids']}
        cells=candidate_subset(ROOT/c['candidate_cache_ref'],j['train_ids'],c['candidate_cache_offsets'])
        event('TRAIN_ONLY_INPUTS_OPENED',train_ids=j['train_ids'],heldout_features_opened=0)
        kwargs={'binding':binding,'candidate_rows':cells}
        if j['stage']=='RETENTION':
            initial=directory/'trials'/j['initial_job_id']
            kwargs.update(initial_model=engine.load_model(initial/'model.json'),initial_training=read(initial/'training.json'))
            event('MATCHING_COMBINATION_INITIALIZER_LOADED',model_id=kwargs['initial_model'].model_id,ref=j['initial_job_id'])
        write(d/'FIT_STARTED.json',{'utc':stamp(),'job_id':job_id,'stage':j['stage'],'fit_count':1,'train_ids':j['train_ids']})
        fit_calls=1;stage_calls=None;threshold_calls=None
        fn=engine.fit_sparse if j['stage']=='SPARSE' else engine.fit_retention
        model,training=fn(j,raw,meta,read(ROOT/c['definitions_ref']),**kwargs)
        key='actual_sparse_fit_invocations' if j['stage']=='SPARSE' else 'actual_retention_invocations'
        stage_calls=model.fit[key]
        threshold_calls=model.fit['threshold_fit_calls']
        write(d/'training.json',training);engine.save_model(model,d/'model.json');restored=engine.load_model(d/'model.json')
        if canonical(model.to_dict())!=canonical(restored.to_dict()): raise ValueError('MODEL_ROUNDTRIP_MISMATCH')
        if restored.fit['train_ids']!=j['train_ids']: raise ValueError('MODEL_TRAIN_SCOPE_MISMATCH')
        event('MODEL_SAVED_RELOADED_FROZEN',model_id=restored.model_id,roundtrip_equal=True)
        if restored.status=='FAILED': raise RuntimeError('MODEL_FIT_FAILED')
        test_cells=candidate_subset(ROOT/c['candidate_cache_ref'],j['prediction_ids'],c['candidate_cache_offsets'])
        with (d/'PREDICTION_CALLS.jsonl').open('x') as calls,(d/'predictions.jsonl').open('x') as output:
            for sid in j['prediction_ids']:
                row=read(base/index[sid]['features'])['features']
                calls.write(json.dumps({'opaque_id':sid,'event':'PREDICT_INVOKED'})+'\n');calls.flush();pred_calls+=1
                result=engine.predict_current(restored,sid,row,candidate_cells=test_cells[sid])
                output.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');output.flush();predictions.append(result)
                if result['decision']=='FAILED':raise RuntimeError('SAVED_MODEL_PREDICTION_FAILED:'+sid)
        event('PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN',ids=j['prediction_ids'],count=len(predictions))
        outcome=restored.status
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        write(d/'ERROR.json',error);outcome='FAILED';done={r['opaque_id'] for r in predictions}
        with (d/'predictions.jsonl').open('a') as output:
            for sid in j['prediction_ids']:
                if sid in done: continue
                row={**binding,'opaque_id':sid,'decision':'FAILED','logical_state':None,'model_id':None,
                    'failure_reason':'RUNNER:'+str(exc),'source_rows':[sid],
                    'selected_atoms_available':0,'selected_atoms_expected':None,'clauses_defined':0,'clauses_expected':None}
                output.write(json.dumps(row,ensure_ascii=False)+'\n');predictions.append(row)
    event('JOB_CLOSED',outcome=outcome);write(d/'access_log.json',events)
    receipt={'job_id':job_id,'group_id':GROUP,'stage':j['stage'],'fold_id':j['fold_id'],'outcome':outcome,
        'actual_fit_invocations':fit_calls,'actual_stage_invocations':stage_calls,'actual_prediction_calls':pred_calls,
        'threshold_fit_calls':threshold_calls,'threshold_fit_calls_unit':'TRAIN_ENCODER_INVOCATION',
        'expected_predictions':len(j['prediction_ids']),'saved_prediction_positions':len(predictions),
        'new_candidate_calls':0,'attempt':1,'additional_retries':0,'charged_seconds':time.monotonic()-started,
        'predictions_closed':True,'evaluation_metadata_joined':False,'error':error}
    write(d/'receipt.json',receipt);return receipt


def run(directory):
    c=read(directory/'CONTRACT.json');validate_contract(c)
    if (directory/'EXECUTION.json').exists() or (directory/'JOURNAL.jsonl').exists():
        raise FileExistsError('EXISTING_EXECUTION_NO_AUTOMATIC_RETRY')
    receipts=[];stopped=None;start=time.monotonic()
    with (directory/'JOURNAL.jsonl').open('x') as journal:
        for j in c['jobs']:
            started=time.monotonic();journal.write(json.dumps({'event':'JOB_RESERVED','utc':stamp(),'job_id':j['job_id'],'max_fit_charge':1})+'\n');journal.flush()
            try:
                p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker','--directory',str(directory),'--job',j['job_id']],cwd=ROOT,
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=c['budget']['max_worker_seconds'])
                d=directory/'trials'/j['job_id']
                r=read(d/'receipt.json');r['worker_wall_seconds']=time.monotonic()-started;receipts.append(r)
                for name,value in [('stdout.txt',p.stdout),('stderr.txt',p.stderr)]:
                    if value:
                        with (d/name).open('x') as f:f.write(value)
                if p.returncode or r['outcome']=='FAILED': stopped='JOB_FAILED:'+j['job_id']
            except Exception as exc:
                stopped=type(exc).__name__+':'+str(exc)
                if not any(r['job_id']==j['job_id'] for r in receipts):
                    effective=dict(j,outer_test_ids=j['prediction_ids'])
                    r=saved_runner.settle_worker_failure(directory,effective,exc,time.monotonic()-started)
                    r.pop('new_sparse_fit_calls',None);r.pop('actual_retention_invocations',None)
                    r.update(stage=j['stage'],actual_stage_invocations=None if r['actual_fit_invocations'] else 0,
                             threshold_fit_calls=None if r['actual_fit_invocations'] else 0,
                             threshold_fit_calls_unit='TRAIN_ENCODER_INVOCATION')
                    model_path=directory/'trials'/j['job_id']/'model.json'
                    if model_path.exists():
                        try:
                            fit=read(model_path)['fit']
                            key='actual_sparse_fit_invocations' if j['stage']=='SPARSE' else 'actual_retention_invocations'
                            r.update(actual_stage_invocations=fit[key],threshold_fit_calls=fit['threshold_fit_calls'])
                        except (ValueError,TypeError,KeyError):pass
                    receipt_path=directory/'trials'/j['job_id']/'receipt.json'
                    receipt_path.rename(receipt_path.with_name('receipt.generic_settlement.json'))
                    write(receipt_path,r)
                    receipts.append(r)
                write(directory/'RUN_ERROR.json',{'job_id':j['job_id'],'reason':stopped,'traceback':traceback.format_exc()})
            journal.write(json.dumps({'event':'JOB_SETTLED','utc':stamp(),**receipts[-1]})+'\n');journal.flush()
            if stopped:break
    def count(key, stage=None):
        rows=[r for r in receipts if stage is None or r['stage']==stage]
        return sum(r[key] for r in rows) if all(r[key] is not None for r in rows) else None
    actual=sum((directory/'trials'/j['job_id']/'FIT_STARTED.json').exists() for j in c['jobs'])
    charged=sum(r.get('worker_wall_seconds',r['charged_seconds']) for r in receipts)
    report={'schema_version':'rsr-combination-execution-v1','status':'COMPLETE_PENDING_REVIEW' if len(receipts)==6 and not stopped else 'PARTIAL',
        'execution_complete':len(receipts)==6 and not stopped,'actual_fit_invocations':actual,
        'actual_sparse_fit_invocations':count('actual_stage_invocations','SPARSE'),
        'actual_retention_invocations':count('actual_stage_invocations','RETENTION'),
        'threshold_fit_calls':count('threshold_fit_calls'),'threshold_fit_calls_unit':'TRAIN_ENCODER_INVOCATION',
        'actual_prediction_calls':count('actual_prediction_calls'),'prediction_positions_saved':count('saved_prediction_positions'),
        'new_candidate_calls':0,'new_collection':0,'additional_retries':0,'control_refits':0,
        'unique_historical_records':162,'expected_prediction_positions':162,'jobs':receipts,'stop_reason':stopped,
        'charged_seconds':charged,'orchestration_elapsed_seconds':time.monotonic()-start,
        'prior_budget_ref':c['budget']['prior_ledger_ref'],'cumulative_fit_jobs':c['budget']['base_fit_jobs']+actual,
        'remaining_research_fits':c['budget']['global_max_fits']-c['budget']['base_fit_jobs']-actual,
        'cumulative_charged_seconds':c['budget']['base_charged_seconds']+charged,
        'remaining_research_seconds':c['budget']['global_max_seconds']-c['budget']['base_charged_seconds']-charged,
        'contract_sha256':digest(c)}
    write(directory/'EXECUTION.json',report);return report


def analyze(directory):
    from hybridguard_agent.research.rule_learning.evaluation import evaluate
    c=read(directory/'CONTRACT.json');ex=read(directory/'EXECUTION.json')
    if not ex['execution_complete']:raise ValueError('PARTIAL_EXECUTION_REQUIRES_REVIEW')
    ids=c['sample_ids'];index=read(ROOT/c['source_index']);base=(ROOT/c['source_index']).parent
    saved={g:[] for g in (*CONTROLS,GROUP)}
    for item in c['saved_controls']:
        rows=lines(ROOT/item['ref']/'predictions.jsonl')
        if len(rows)!=len(item['outer_test_ids']) or {r['opaque_id'] for r in rows}!=set(item['outer_test_ids']):raise ValueError('CONTROL_PREDICTION_SCOPE_CONFLICT')
        saved[item['group_id']]+=rows
    jobs=[]
    for j in c['jobs']:
        d=directory/'trials'/j['job_id'];rows=lines(d/'predictions.jsonl')
        if not read(d/'receipt.json')['predictions_closed'] or len(rows)!=len(j['prediction_ids']) or {r['opaque_id'] for r in rows}!=set(j['prediction_ids']):raise ValueError('NEW_PREDICTION_SCOPE_CONFLICT')
        if j['stage']=='RETENTION':saved[GROUP]+=rows
        m=read(d/'model.json');t=read(d/'training.json')
        jobs.append({'job_id':j['job_id'],'stage':j['stage'],'fold_id':j['fold_id'],'model_status':m['status'],
            'selected_clause_ids':m['fit']['training_result']['clause_ids'],'complexity':m['complexity'],
            'train_score':m['fit']['training_result'],'trace':t['trace'],
            'candidate_selection':[r for r in t['candidate_manifest'] if r['clause_id'].startswith('RSR-')],
            'D_initial':m['fit'].get('D_initial'),'D_final':m['fit'].get('D_final')})
    for g,rows in saved.items():
        if len(rows)!=162 or {r['opaque_id'] for r in rows}!=set(ids):raise ValueError('OOF_SCOPE_CONFLICT:'+g)
    meta={sid:read(base/index[sid]['evaluation']) for sid in ids}
    by={g:{r['opaque_id']:r for r in rows} for g,rows in saved.items()};groups={}
    for g,rows in saved.items():
        derived=[dict(r,executed_model_id=r['model_id'],executed_fold_id=r['fold_id'],model_id='OOF:'+g,fold_id='EXPLICIT_OOF_AGGREGATE') for r in rows]
        groups[g]=evaluate(ids,derived,meta,evaluation_role=ROLE)
    metric_names=('attack_tpr','MacroTPR_config_environment','clean_alarm_rate','decision_coverage','abstention_rate','failure_rate')
    comparisons={}
    for g in CONTROLS:
        changed=[];transitions=Counter()
        for sid in ids:
            a,b=by[g][sid],by[GROUP][sid];transitions[a['decision']+'->'+b['decision']]+=1
            if (a['decision'],a['logical_state'])!=(b['decision'],b['logical_state']):
                changed.append({'opaque_id':sid,'phase':meta[sid]['phase'],'config_id':meta[sid]['config_id'],
                    'fold_id':b['fold_id'],'old_decision':a['decision'],'new_decision':b['decision'],
                    'old_state':a['logical_state'],'new_state':b['logical_state']})
        comparisons[g]={'changed_records':changed,'decision_cross_table':dict(transitions),
            'metric_delta_percentage_points':{m:100*(groups[GROUP]['metrics'][m]['value']-groups[g]['metrics'][m]['value']) for m in metric_names},
            'gained_attack_alert_ids':[r['opaque_id'] for r in changed if r['phase']=='attack' and r['new_decision']=='MANIPULATION_ALERT'],
            'lost_attack_alert_ids':[r['opaque_id'] for r in changed if r['phase']=='attack' and r['old_decision']=='MANIPULATION_ALERT']}
    interaction_rows=[]
    for sid in ids:
        decisions={g:by[g][sid]['decision'] for g in saved};defined=all(d in ('MANIPULATION_ALERT','NO_ALERT') for d in decisions.values())
        a={g:int(d=='MANIPULATION_ALERT') for g,d in decisions.items()} if defined else {}
        interaction_rows.append({'opaque_id':sid,'phase':meta[sid]['phase'],'decisions':decisions,
            'value':a[GROUP]-a['LANG_ADD']-a['WD_REPLACE']+a['BASE'] if defined else None})
    all_defined=all(r['value'] is not None for r in interaction_rows)
    interaction={'role':'POST_HOC_DESCRIPTIVE_INTERACTION_NO_CAUSAL_CLAIM','formula':'COMBO-LANG_ADD-WD_REPLACE+BASE',
        'status':'COMPLETE_BINARY_DECISIONS' if all_defined else 'NOT_FULLY_IDENTIFIED',
        'rows':interaction_rows,'undefined_n':sum(r['value'] is None for r in interaction_rows),
        'metric_interaction_percentage_points':{m:100*(groups[GROUP]['metrics'][m]['value']-groups['LANG_ADD']['metrics'][m]['value']-groups['WD_REPLACE']['metrics'][m]['value']+groups['BASE']['metrics'][m]['value']) if all_defined else None for m in metric_names}}
    return {'schema_version':'rsr-combination-summary-v1','status':ex['status'],'evaluation_role':ROLE,
        'unique_historical_records':162,'new_prediction_positions':162,'reused_control_prediction_positions':486,
        'groups':groups,'comparisons':comparisons,'interaction':interaction,'jobs':jobs,'execution':ex,
        'limits':'Fixed exposed historical development LOEO; no independent confirmation or population FPR/generalization claim.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run','worker','analyze'))
    p.add_argument('--directory',type=Path,default=HERE);p.add_argument('--job');p.add_argument('--output',type=Path)
    a=p.parse_args();a.directory=a.directory.resolve()
    if a.output and a.action!='analyze':p.error('--output is analyze only')
    if a.output and a.output.exists():p.error('REFUSE_EXISTING_ANALYSIS_OUTPUT')
    result=worker(a.directory,a.job) if a.action=='worker' else globals()[a.action](a.directory)
    if a.output:write(a.output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('groups','comparisons','interaction','jobs','execution')},ensure_ascii=False,indent=2))
    return int(result.get('status')=='PARTIAL')

if __name__=='__main__':raise SystemExit(main())
