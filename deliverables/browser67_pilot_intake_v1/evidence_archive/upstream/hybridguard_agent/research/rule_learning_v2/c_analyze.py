"""Read saved C results; never learns parameters or regenerates real predictions."""
from collections import Counter,defaultdict
import time

from hybridguard_agent.research.rule_learning.evaluation import evaluate
from hybridguard_agent.research.rule_learning.models import load_model as load_v1
from . import c_engine
from .b_analyze import model_record,small_metrics,flatten
from .c_experiment import C_OUT,R08,attempt_dir,verify
from .common import ROOT,read,lines,write,write_lines,write_csv,relative,stamp
from .diagnose import metadata,ALERT
from .trial_summary import inspect_attempt


def aggregate(name,rows,meta,track,role):
    ids=sorted(meta)
    derived=[dict(rows[i],executed_model_id=rows[i]['model_id'],executed_fold_id=rows[i]['fold_id'],
                  model_id='AGGREGATE:'+track+':'+name,fold_id='EXPLICIT_'+track+'_AGGREGATE',split_id=track) for i in ids]
    return evaluate(ids,derived,meta,evaluation_role=role)


def build():
    start=time.monotonic();meta=metadata();c=read(C_OUT/'C_CONTRACT.json');a=read(C_OUT/'linked_budget_ledger.json')
    if any(b['state']!='CLOSED' for b in a['batches']):raise ValueError('PLANNED_BATCHES_NOT_ALL_CLOSED')
    predictions=defaultdict(dict);models=[];integrity=[];execution=[];by_fold=[];trusted_models={}
    for job in c['jobs']:
        d=attempt_dir(job);r=inspect_attempt(d,dict(job,outer_test_ids=job['evaluation_ids']),c_engine.load_model)
        key=(job['track'],job['spec_id'])
        if job['track']=='FINAL_DEVELOPMENT_FIT' and r['model'] is not None:
            trusted_models[job['spec_id']]=r['model']
        if set(predictions[key])&{p['opaque_id'] for p in r['predictions']}:raise ValueError('DUPLICATE_EVALUATION_MEMBER')
        predictions[key].update({p['opaque_id']:p for p in r['predictions']})
        models.append(dict(model_record(job['spec_id'],r['model'],d/'model.json',r['training'],r['audit']),
                           track=job['track'],fold_id=job['fold_id']))
        integrity.append(dict(r['audit'],job_id=job['job_id']))
        fold_metrics=evaluate(job['evaluation_ids'],r['predictions'],{i:meta[i] for i in job['evaluation_ids']},evaluation_role=job['evaluation_role'],strata=False)
        by_fold.append(dict(flatten(job['spec_id'],job['fold_id'],fold_metrics['metrics']),track=job['track']))
        if r['audit']['status']=='OK':
            ev=read(d/'access_log.json');names=[e['event'] for e in ev]
            assert ev[0]['ids']==job['train_ids'] and r['model'].fit['train_ids']==job['train_ids']
            assert names.index('MODEL_ENCODER_SAVED_LOADED_FROZEN')<names.index('OPEN_EVALUATION_FEATURE_AFTER_FREEZE')<names.index('PREDICTIONS_SAVED_CLOSED')<names.index('EVALUATION_LABEL_JOIN_AFTER_CLOSURE')
            assert len(lines(d/'fit_invocations.jsonl'))==1
            receipt=read(d/'receipt.json');assert receipt['roundtrip_equal']==len(job['evaluation_ids'])
            execution.append({'job_id':job['job_id'],'train_n':len(job['train_ids']),'evaluation_n':len(job['evaluation_ids']),
                'role':job['evaluation_role'],'train_evaluation_overlap':len(set(job['train_ids'])&set(job['evaluation_ids'])),
                'freeze_features_predictions_labels_order':'PASS','roundtrip_equal':receipt['roundtrip_equal'],'fit_invocations':1})
    reuse=read(C_OUT/'C0_LOCO_REUSE.json')
    if all(r['status']=='COMPATIBLE_SAVED_ONLY' for r in reuse):
        saved=[r for r in lines(R08/'oof_predictions.jsonl') if r['method_id']=='GREEDY_OR' and r['operating_point']=='OP05']
        predictions[('LOCO-v1','C0__GREEDY_OR')]={r['opaque_id']:r for r in saved}
        for ref in reuse:
            m=load_v1(ROOT/ref['model_ref']);models.append(dict(model_record('C0__GREEDY_OR',m,ROOT/ref['model_ref']),track='LOCO-v1'))
            p=[r for r in saved if r['fold_id']==ref['fold_id']];ids=[r['opaque_id'] for r in p]
            result=evaluate(ids,p,{i:meta[i] for i in ids},evaluation_role=c_engine.LOCO_ROLE,strata=False)
            by_fold.append(dict(flatten('C0__GREEDY_OR',ref['fold_id'],result['metrics']),track='LOCO-v1'))
    overall=defaultdict(dict);table=[];by_config=[]
    for (track,name),rows in predictions.items():
        assert set(rows)==set(meta)
        role=c_engine.FINAL_ROLE if track=='FINAL_DEVELOPMENT_FIT' else c_engine.LOCO_ROLE
        result=aggregate(name,rows,meta,track,role)
        overall[track][name]={'metrics':small_metrics(result['metrics']),'evaluation_role':role,'expected_stages':len(meta),
             'decision_counts':result['decision_counts'],'complexity_by_fold':[m['complexity'] for m in models if m['track']==track and m['spec_id']==name]}
        table.append(dict(flatten(name,'ALL',result['metrics']),track=track,role=role,complexity_by_fold=overall[track][name]['complexity_by_fold']))
        for config,ms in result['strata']['config'].items():by_config.append(dict(flatten(name,config,ms),track=track))
    comparisons=[];attack=[i for i in meta if meta[i]['supervised_label']==1];clean=[i for i in meta if meta[i]['supervised_label']==0]
    for track in ('FINAL_DEVELOPMENT_FIT','LOCO-v1'):
        for candidate,reference in [('W0__R_KEEP_V1','W0__GREEDY_OR'),('W0__R_KEEP_V1','C0__GREEDY_OR'),('W0__GREEDY_OR','C0__GREEDY_OR')]:
            if (track,reference) not in predictions:continue
            now,old=predictions[(track,candidate)],predictions[(track,reference)]
            gained=[i for i in attack if now[i]['decision']==ALERT and old[i]['decision']!=ALERT]
            lost=[i for i in attack if now[i]['decision']!=ALERT and old[i]['decision']==ALERT]
            comparisons.append({'track':track,'spec_id':candidate,'reference':reference,'gained_attack_ids':gained,'lost_attack_ids':lost,
              'new_clean_alarm_ids':[i for i in clean if now[i]['decision']==ALERT and old[i]['decision']!=ALERT],
              'gained_by_config':dict(Counter(meta[i]['config_id'] for i in gained)),
              'lost_by_config':dict(Counter(meta[i]['config_id'] for i in lost))})
    final_jobs={j['spec_id']:j for j in c['jobs'] if j['track']=='FINAL_DEVELOPMENT_FIT'}
    final=trusted_models
    comparison={'status':'NOT_AVAILABLE_UNLESS_BOTH_FINAL_MODELS_VALID'}
    if all(n in final for n in ('W0__GREEDY_OR','W0__R_KEEP_V1')):
        sparse,keep=final['W0__GREEDY_OR'],final['W0__R_KEEP_V1'];training=read(attempt_dir(final_jobs['W0__R_KEEP_V1'])/'training.json')
        comparison={'status':'AVAILABLE','sparse_model_id':sparse.model_id,'candidate_model_id':keep.model_id,
            'initial_clause_count':len(sparse.clauses),'original_clause_limit':c['settings']['max_clauses'],
            'added_clause_ids':[r['added'] for r in training['trace'] if r['operation']=='RETAIN_SIGNAL'],
            'identical_clauses':sparse.clauses==keep.clauses,'identical_selected_atoms':sparse.atoms==keep.atoms,
            'identical_encoder_and_thresholds':sparse.encoder==keep.encoder,
            'identical_train_decisions':all(predictions[('FINAL_DEVELOPMENT_FIT','W0__GREEDY_OR')][i]['decision']==predictions[('FINAL_DEVELOPMENT_FIT','W0__R_KEEP_V1')][i]['decision'] for i in meta),
            'training_scope':'All authorized 162 supervised stages; resubstitution only, no B LOEO score attached.',
            'equivalence_limit':'Observed-output equality alone is not global logical equivalence; instance structure/encoder equality is checked separately. The two learning procedures are not claimed equivalent on other training sets.'}
    write(C_OUT/'metrics.json',dict(overall));write_csv(C_OUT/'metrics.csv',table)
    write_csv(C_OUT/'metrics_by_configuration.csv',by_config);write_csv(C_OUT/'metrics_by_fold.csv',by_fold)
    write(C_OUT/'gained_lost.json',comparisons);write(C_OUT/'model_manifest.json',models)
    write(C_OUT/'final_model_comparison.json',comparison);write(C_OUT/'trial_integrity_summary.json',integrity)
    write(C_OUT/'execution_verification.json',{'status':'PASS' if len(execution)==len(c['jobs']) else 'PARTIAL','checks':execution,
           'actual_fits':a['actual_fits'],'saved_prediction_count':sum(len(v) for (t,n),v in predictions.items() if not (t=='LOCO-v1' and n=='C0__GREEDY_OR')),
           'source':'Saved traces/receipts/model membership; no fit or real prediction regeneration.'})
    write_lines(C_OUT/'stage_comparison.jsonl',[{'track':track,'opaque_id':i,'phase':meta[i]['phase'],'config_id':meta[i]['config_id'],
                'decisions':{n:rows[i]['decision'] for (t,n),rows in predictions.items() if t==track}} for track in ('FINAL_DEVELOPMENT_FIT','LOCO-v1') for i in sorted(meta)])
    write(C_OUT/'analysis_timing.json',{'role':'READ_ONLY_SAVED_OUTPUT_ARITHMETIC','elapsed_seconds':time.monotonic()-start,'real_fits':0,'new_predictions':0,'utc':stamp()})
    return table


if __name__=='__main__':
    import json
    print(json.dumps([{k:r[k] for k in ['track','spec_id','attack_tpr_k','attack_tpr_n','MacroTPR_config_environment','pre_alarm_rate_k','post_alarm_rate_k','decision_coverage','failure_rate_k','complexity_by_fold']} for r in build()],ensure_ascii=False))
