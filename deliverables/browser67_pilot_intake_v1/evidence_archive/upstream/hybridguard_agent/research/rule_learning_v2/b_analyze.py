"""Saved-output arithmetic and attribution tables only; no fit or re-prediction."""
from collections import Counter

from hybridguard_agent.research.rule_learning.models import load_model as load_v1
from .common import ROOT, OUT as A_OUT, ROLE, read, lines, write, write_csv, write_lines, relative, folds
from .diagnose import baseline_jobs, saved_predictions, metadata, explicit_oof, ALERT
from .trial_summary import inspect_attempt
from . import b_engine
from .b_experiment import B_OUT


def model_record(name,model,path,training=None,audit=None):
    if model is None:
        return {'spec_id':name,'model_ref':relative(path),'status':audit['status'],'complexity':None,
                'clauses':None,'structure_reason':audit['structure_statistics']}
    comp=model.engine.to_dict()['complexity'] if hasattr(model,'engine') else model.to_dict()['complexity']
    atoms={a.atom_id:a for a in model.atoms}
    groups=training.get('signal_groups',{}) if training else {}
    return {'spec_id':name,'fold_id':model.binding['fold_id'],'model_ref':relative(path),'model_id':model.model_id,
        'status':model.status,'complexity':comp['objective_complexity'],'complexity_detail':comp,
        'clauses':[c.id for c in model.clauses],
        'selected_atoms':[{'atom_id':a.atom_id,'sources':a.sources,'surfaces':a.surfaces,'family':a.family,
                          'signal_group':groups.get(a.atom_id),'aliases':a.aliases,'provenance':a.provenance} for a in model.atoms],
        'registered_clauses':model.fit.get('registered_clause_count'),'eligible_clauses':model.fit.get('candidate_pool_size'),
        'selected_clauses':len(model.clauses),'cross_atoms_selected':[a.atom_id for a in model.atoms if len(a.surfaces)>1],
        'training_clean_budget':model.fit.get('clean_budget_count'),'training_result':model.fit.get('training_result'),
        'initialization':training.get('initialization') if training else None,
        'retained_trace':[r for r in training.get('trace',[]) if r['operation']=='RETAIN_SIGNAL'] if training else [],
        'not_selected_reason_counts':dict(Counter(reason for r in training.get('candidate_manifest',[]) if not r.get('selected') for reason in r.get('reasons',[]))) if training else None}


def collect(batch_ids=None):
    predictions={};models=[];audits=[]
    for name,dirs in baseline_jobs().items():
        predictions[name],_=saved_predictions(dirs)
        for d in dirs: models.append(model_record(name,load_v1(d/'model.json'),d/'model.json'))
    for rep in ('S_FLAT','J0'):
        predictions[rep]={}
        for f in folds():
            d=A_OUT/'trials'/('V2-A__'+rep+'__'+f['fold_id']+'__attempt01')
            job={'job_id':d.name,'representation':rep,'fold_id':f['fold_id'],'outer_test_ids':f['outer_test']}
            result=inspect_attempt(d,job)
            predictions[rep].update({r['opaque_id']:r for r in result['predictions']})
            models.append(model_record(rep,result['model'],d/'model.json',result['training'],result['audit']))
    account=read(B_OUT/'linked_budget_ledger.json')
    for batch in account['batches']:
        if batch_ids is not None and batch['batch_id'] not in batch_ids: continue
        if batch['state']!='CLOSED': raise ValueError('BATCH_NOT_CLOSED')
        spec=read(ROOT/batch['spec_ref'])
        for job in spec['jobs']:
            d=B_OUT/'trials'/(job['job_id']+'__attempt01')
            result=inspect_attempt(d,job,model_loader=b_engine.load_model)
            name=job['spec_id'];predictions.setdefault(name,{})
            if set(predictions[name]) & {r['opaque_id'] for r in result['predictions']}:
                raise ValueError('DUPLICATE_SPEC_FOLD_REQUIRES_NEW_VERSION_NAME')
            predictions[name].update({r['opaque_id']:r for r in result['predictions']})
            models.append(model_record(name,result['model'],d/'model.json',result['training'],result['audit']))
            audits.append(dict(result['audit'],job_id=job['job_id'],spec_id=name))
    return predictions,models,audits


def small_metrics(ms):
    fields=('numerator','denominator','expected_denominator','value','status','reason')
    return {k:{f:v[f] for f in fields if f in v} for k,v in ms.items()}


def flatten(name,stratum,ms):
    result={'spec_id':name,'stratum':stratum}
    for k,v in ms.items():
        result[k+'_k']=v['numerator'];result[k+'_n']=v['denominator'];result[k]=v['value'];result[k+'_status']=v['status']
    return result


def summarize(destination,batch_ids=None):
    predictions,models,audits=collect(batch_ids)
    meta=metadata();ids=sorted(meta);overall={};table=[];by_config=[];by_fold=[]
    for name,rows in predictions.items():
        if set(rows)!=set(ids): raise ValueError('ALL_162_EXPECTED_STAGES_REQUIRED')
        result=explicit_oof(name,rows,meta)
        overall[name]={'metrics':small_metrics(result['metrics']),'evaluation_role':ROLE,
                       'expected_stages':162,'positive':54,'negative':108,
                       'decision_counts':result['decision_counts'],'prediction_evidence':'model_manifest.json and original per-trial predictions.jsonl'}
        row=flatten(name,'ALL',result['metrics']);row['complexity_by_fold']=[m['complexity'] for m in models if m['spec_id']==name]
        row['role']=ROLE;table.append(row)
        for key,ms in result['strata']['config'].items():by_config.append(flatten(name,key,ms))
        for f in folds():
            sub={i:meta[i] for i in f['outer_test']};ms=explicit_oof(name,{i:rows[i] for i in sub},sub)['metrics']
            by_fold.append(flatten(name,f['fold_id'],ms))
    comparisons=[];pairs=set()
    new=[n for n in predictions if n not in ('C0','W0','S_FLAT','J0')]
    for name in new:
        pairs.update((name,base) for base in ('C0','W0','S_FLAT','J0'))
        rep,method=name.split('__',1)
        if method=='R_KEEP_V1' and rep+'__GREEDY_OR' in predictions:pairs.add((name,rep+'__GREEDY_OR'))
        for reference_rep in ('CX','JX','W_X','S_FLAT_X'):
            reference=reference_rep+'__'+method
            if reference in predictions and reference!=name:pairs.add((name,reference))
        if method=='R_KEEP_V1' and name!='W0__R_KEEP_V1':pairs.add((name,'W0__R_KEEP_V1'))
    attack=[i for i in ids if meta[i]['supervised_label']==1];clean=[i for i in ids if meta[i]['supervised_label']==0]
    for name,reference in sorted(pairs):
        if reference not in predictions:continue
        now,before=predictions[name],predictions[reference]
        gained=[i for i in attack if now[i]['decision']==ALERT and before[i]['decision']!=ALERT]
        lost=[i for i in attack if now[i]['decision']!=ALERT and before[i]['decision']==ALERT]
        alarms=[i for i in clean if now[i]['decision']==ALERT and before[i]['decision']!=ALERT]
        comparisons.append({'spec_id':name,'reference':reference,'gained_attack_ids':gained,'lost_attack_ids':lost,
           'new_clean_alarm_ids':alarms,'gained_by_config':dict(Counter(meta[i]['config_id'] for i in gained)),
           'lost_by_config':dict(Counter(meta[i]['config_id'] for i in lost))})
    write(destination/'metrics.json',overall);write_csv(destination/'metrics.csv',table)
    write_csv(destination/'metrics_by_configuration.csv',by_config);write_csv(destination/'metrics_by_fold.csv',by_fold)
    write(destination/'gained_lost.json',comparisons);write(destination/'model_manifest.json',models)
    write(destination/'trial_integrity_summary.json',audits)
    write_lines(destination/'stage_comparison.jsonl',[{'opaque_id':i,'phase':meta[i]['phase'],'config_id':meta[i]['config_id'],
                'decisions':{name:rows[i]['decision'] for name,rows in predictions.items()}} for i in ids])
    return table


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('batch',nargs='?');a=p.parse_args()
    destination=B_OUT/'batches'/a.batch if a.batch else B_OUT
    rows=summarize(destination,[a.batch] if a.batch else None)
    print(json.dumps([{k:r[k] for k in ['spec_id','attack_tpr_k','attack_tpr_n','MacroTPR_config_environment','pre_alarm_rate_k','post_alarm_rate_k','decision_coverage','failure_rate_k','complexity_by_fold']} for r in rows],ensure_ascii=False))
