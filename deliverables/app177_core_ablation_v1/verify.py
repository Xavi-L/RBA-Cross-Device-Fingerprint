"""Focused saved-model checks and explicitly counted training-budget inference."""
from collections import Counter
from dataclasses import asdict
import csv,json
from pathlib import Path
from data import *
from run import write,dump_lines
import tree


def verify(out):
    entries=read(out/'models.json')['models'];fulls=full_models();checks=[];train_predictions=[];budgets=[]
    cached=out/'tree_training_predictions.jsonl.gz'
    if cached.exists():train_predictions=[r['value'] for r in records(cached)]
    prediction_calls=0
    for fold in settings()['folds']:
        fid=fold['fold_id'];full=fulls[fid]
        for scheme in engine.SCHEMES:
            e={x['stage']:x for x in entries if x['scheme']==scheme and x['fold_id']==fid}
            sparse=engine.AppModel.from_dict(read(out/e['SPARSE']['path']));keep=engine.AppModel.from_dict(read(out/e['RETENTION']['path']))
            assert sparse.encoder==keep.encoder==full.encoder
            assert keep.fit['initialization']['model_id']==sparse.model_id
            assert keep.fit['clean_budget_count']==sparse.fit['clean_budget_count']==8
            assert keep.fit['mtc_budget_count']==sparse.fit['mtc_budget_count']==(630 if scheme=='A_NO_MTC_CAP' else 31)
            stats=read((out/e['RETENTION']['path']).parent/'training.json')['candidate_statistics']
            assert {a.atom_id for a in keep.atoms}<={r['atom_id'] for r in stats if r['admitted']}
            assert all(engine.allowed(a,scheme) for a in keep.atoms)
            assert len(sparse.fit['train_ids'])==len(keep.fit['train_ids'])==252
            checks.append({'fold_id':fid,'scheme':scheme,'own_sparse_initialization':True,'encoder_shared':True,
                           'sparse_rules':len(sparse.clauses),'retention_rules':len(keep.clauses),
                           'same_clauses':sparse.clauses==keep.clauses,'sparse_score':sparse.fit['training_result'],
                           'retention_score':keep.fit['training_result']})
        e=next(e for e in entries if e['fold_id']==fid and e['scheme']=='APP_TREE');model=read(out/e['path'])
        assert model['parameters']==tree.PARAMS and model['classes'][model['positive_class_index']]==1
        assert model['train_ids']==fold['train_ids'] and model['mtc_train_ids']==settings()['mtc_normal_train_ids']
        assert model['encoder']==full.encoder
        if not cached.exists():
            cr,meta,mr,_,_=training(fold)
            for sid,item in {**cr,**mr}.items():
                pred=tree.predict(model,sid,item['raw']);prediction_calls+=1
                train_predictions.append(dict(sample_id=sid,fold_id=fid,model_id=model['model_id'],
                    population='mtc_normal' if sid in mr else 'controlled_attack' if meta[sid]['phase']=='attack' else 'controlled_normal',**pred))
        sub=[p for p in train_predictions if p['fold_id']==fid]
        for pop,budget in [('controlled_normal',8),('mtc_normal',31),('controlled_attack',None)]:
            ps=[p for p in sub if p['population']==pop];cs=Counter(p['state'] for p in ps)
            budgets.append(dict(fold_id=fid,population=pop,N=len(ps),**{s:cs[s] for s in STATES},budget=budget,
                                actual_budget_met=cs['T']<=budget if budget is not None else None))
    # Pair identity is verified using references and same-stage metadata only.
    # No Browser value is made available to an App predictor.
    pair_checks=[]
    for m in [r['value'] for r in records(out/'members.jsonl') if r['value']['cohort']=='paired60']:
        a=raw_at(m['raw_reference']);b=raw_at(m['browser_reference']);pp=a['canonical_received_payload'];manifest=pp['collection_manifest']
        cp,cn=m['capture_reference'].rsplit(':',1);cap=next(r['value'] for r in records(ROOT/cp) if r['line']==int(cn))
        assert manifest['runtime_context']==cap['runtime_context'] and manifest['collection_round']==cap['collection_round']
        assert b['app_session_id']==a['session_id']
        if m['subset']=='b2b42':
            assert cap['sample_id']==m['sample_id'];prp,prn=m['pair_reference'].rsplit(':',1)
            pr=next(r['value'] for r in records(ROOT/prp) if r['line']==int(prn))
            assert pr['pair_status']=='completed' and pr['app_session_id']==a['session_id'] and pr['browser_session_id']==b['browser_session_id']
        else:
            assert cap['configuration_id']==m['scenario'] and cap['stage']==m['phase'] and cap['pair_completed'] is True
            assert cap['archives']['app']['line']==int(m['raw_reference'].rsplit(':',1)[1])
        pair_checks.append({'sample_id':m['sample_id'],'current_app_stage_bound':True,'browser_same_app_session':True})
    if not cached.exists():dump_lines(cached,train_predictions)
    write(out/'VERIFICATION.json',{'passed':True,'rule_model_checks':checks,'paired_source_checks':pair_checks,
          'tree_training_budget_checks':budgets,'tree_budget_prediction_calls_this_run':prediction_calls,
          'tree_fit_calls':0,'rule_fit_calls':0,'collection_calls':0})
    with (out/'summary/tree_training_budgets.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(budgets[0]));w.writeheader();w.writerows(budgets)
    print(json.dumps({'passed':True,'training_budget_predictions':prediction_calls,'tree_budgets':budgets}),flush=True)

if __name__=='__main__':verify(HERE/'results')
