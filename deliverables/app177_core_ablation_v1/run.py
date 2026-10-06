#!/usr/bin/env python3
"""Separate Full replay, bounded training, frozen evaluation, and saved-only summary."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
from data import *


def stamp():return datetime.now(timezone.utc).isoformat()
def write(p,r):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def dump_lines(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with (gzip.open if p.suffix=='.gz' else open)(p,'xt') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
def prediction(model,item,sid,scheme):
    if scheme=='APP_TREE':
        import tree
        return tree.predict(model,sid,item['raw'])
    impl=full_engine if scheme=='APP_FULL' else engine
    p=impl.predict_current(model,sid,item['raw'])
    return {'decision':p['decision'],'state':p.get('logical_state') or p['decision'],
            'rules':p['clause_explanations'],'triggered_rules':[r['clause_id'] for r in p['clause_explanations'] if r['state']=='T'],
            'selected_atoms_available':p['selected_atoms_available'],'selected_atoms_expected':p['selected_atoms_expected'],
            'failure_reason':p['failure_reason'],'atom_states':[{'atom_id':r['atom_id'],'state':r['state'],'reason':r['reason']} for r in p['atom_explanations']]}


def row_predictions(rows,members,models,scheme,stage='RETENTION'):
    s=settings();fold_of={sid:f['fold_id'] for f in s['folds'] for sid in f['outer_test_ids']}
    for m in members:
        sid=m['sample_id'];folds=[fold_of[sid]] if m['cohort']=='controlled' else list(models)
        for fid in folds:
            model=models[fid];mid=model['model_id'] if isinstance(model,dict) else model.model_id
            yield {'sample_id':sid,'scheme':scheme,'fold_id':fid,'model_id':mid,'stage':stage,
                   'cohort':m['cohort'],'subset':m['subset'],'identity':m['identity'],'scenario':m['scenario'],
                   'phase':m['phase'],'affected_endpoint':m.get('affected_endpoint'),
                   **prediction(model,rows[sid],sid,scheme)}


def full(out):
    if (out/'full_predictions.jsonl.gz').exists():raise FileExistsError('FULL_ALREADY_REPLAYED_USE_SUMMARY')
    started=stamp();models=full_models();inputs,members=evaluation()
    saved={}
    for rec in records(FULL/'predictions.jsonl.gz'):
        r=rec['value']
        if r['model_id'] in IDS:
            key=(r['sample_id'],r['fold_id'])
            if key in saved:raise ValueError('DUPLICATE_FULL_SAVED_PREDICTION')
            saved[key]=(r,rec['reference'])
    predictions=list(row_predictions(inputs,members,models,'APP_FULL'))
    mismatches=[];checks=[]
    for p in predictions:
        key=(p['sample_id'],p['fold_id'])
        if key in saved:
            r,ref=saved[key];a=[(x['clause_id'],x['state']) for x in p['rules']];b=[(x['clause_id'],x['state']) for x in r['rules']]
            ok=p['decision']==r['decision'] and a==b
            checks.append({'sample_id':p['sample_id'],'fold_id':p['fold_id'],'reference':ref,'matched':ok})
            if not ok:mismatches.append({'key':key,'new':p,'old':r})
    # Available same-model local timezone and 60 paired outputs are additional regressions.
    prior_local={}
    for m in members:
        for r in m.get('saved_models',[]):
            if r.get('model_id') in IDS:prior_local[m['sample_id'],r['model_id']]=r
    for name in ['browser67_cross_endpoint_diagnostic_v1/results/app_predictions.jsonl','cross_endpoint_matched_controls_v1/private_runs/formal01/evaluation/app_predictions.jsonl']:
        for rec in records(ROOT/'deliverables'/name):
            r=rec['value'];q=r['prediction'];prior_local[r['meta']['sample_id'],q['model_id']]=q
    local_checks=[]
    for p in predictions:
        r=prior_local.get((p['sample_id'],p['model_id']))
        if r:
            ok=p['decision']==r['decision']
            original=r.get('rules',r.get('clause_explanations',[]))
            if original:ok=ok and [(x['clause_id'],x['state']) for x in p['rules']]==[(x['clause_id'],x['state']) for x in original]
            local_checks.append({'sample_id':p['sample_id'],'model_id':p['model_id'],'matched':ok})
            if not ok:mismatches.append({'key':(p['sample_id'],p['model_id']),'new':p,'old':r})
    # Check every raw v14 controlled candidate against its original prepared representation.
    candidate_diffs=[];candidate_checks=0
    for m in members:
        if m['cohort']!='controlled':continue
        sid=m['sample_id'];ref=m['raw_reference'];raw=raw_at(ref,sid.removeprefix('webgl1fresh-'))
        adapted=adapt_raw(raw,raw['session_id'],ref,14)
        for aid,c in inputs[sid]['raw'].items():
            candidate_checks+=1
            if {k:c[k] for k in ('value','available','evaluation_status')}!={k:adapted['raw'][aid][k] for k in ('value','available','evaluation_status')}:
                candidate_diffs.append({'sample_id':sid,'atom_id':aid,'saved':c,'current':adapted['raw'][aid]})
    core=sum(p['cohort']!='paired60' for p in predictions);supplement=sum(p['cohort']=='paired60' for p in predictions)
    if len(checks)!=3051 or core!=3591 or supplement!=180:raise ValueError('FULL_EXPECTED_POSITION_PRODUCT_MISMATCH')
    summary={'started_at':started,'closed_at':stamp(),'core_record_positions':1449,'core_model_positions':core,'paired_record_positions':60,
        'paired_model_positions':supplement,'prediction_calls':len(predictions),'fit_calls':0,'collection_calls':0,
        'historical_main_mtc_checks':checks,'same_model_specialist_and_paired_checks':local_checks,
        'current_compiler_candidate_checks':candidate_checks,'candidate_differences':candidate_diffs,'prediction_mismatches':mismatches,
        'passed':not mismatches and not candidate_diffs,'tzdb_version':tz.TZDB_VERSION,
        'specialist_full_prior_output_scope':'timezone36 available; memory72/screen72 newly replayed for B_REL_TZ'}
    dump_lines(out/'members.jsonl',[{k:v for k,v in m.items() if k!='saved_models'} for m in members])
    dump_lines(out/'full_predictions.jsonl.gz',predictions);write(out/'FULL_REPLAY.json',summary)
    write(out/'SOURCE_REFERENCES.json',sorted(USED))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('historical_main_mtc_checks','same_model_specialist_and_paired_checks','candidate_differences','prediction_mismatches')}),flush=True)
    if not summary['passed']:raise ValueError('FULL_REGRESSION_DIFFERENCES_RECORDED')


def train(out, resume=False):
    import tree
    s=settings();fulls=full_models()
    if not read(out/'FULL_REPLAY.json')['passed']:raise ValueError('FULL_REPLAY_MUST_PASS_BEFORE_ABLATION')
    if (out/'FIT_CALLS.jsonl').exists() and not resume:raise FileExistsError('NO_AUTOMATIC_REFITS_USE_EXPLICIT_RESUME')
    previous=[r['value'] for r in records(out/'FIT_CALLS.jsonl')] if resume else []
    def save_or_compare(path,value):
        if path.exists():
            if json.loads(json.dumps(value))!=json.loads(path.read_text()):raise ValueError('RESUME_FROZEN_INPUT_CHANGED')
        else:write(path,value)
    if (out/'EXECUTION.json').exists() or (out/'models.json').exists():raise FileExistsError('COMPLETED_TRAINING_CANNOT_BE_RESUMED_OR_REFITTED')
    start=stamp();entries=[];events=[];pre=[];regressions=[]
    with (out/'FIT_CALLS.jsonl').open('a' if resume else 'x') as log:
        for fold in s['folds']:
            fid=fold['fold_id'];rows,meta,mr,mm,members=training(fold);model=fulls[fid]
            ev=s['mtc_primary_ids']['development']+s['mtc_primary_ids']['reserved_validation']
            args=(fold,{i:r['raw'] for i,r in rows.items()},meta,{i:r['raw'] for i,r in mr.items()},mm,model.encoder)
            kw={'mtc_ids':s['mtc_normal_train_ids'],'evaluation_ids':ev}
            save_or_compare(out/'folds'/fid/'encoder.json',model.encoder)
            member_path=out/'folds'/fid/'training_members.jsonl'
            if member_path.exists():
                if [r['value'] for r in records(member_path)]!=members:raise ValueError('RESUME_TRAIN_MEMBERS_CHANGED')
            else:dump_lines(member_path,members)
            prepared=engine.prepare(*args,scheme='APP_FULL',**kw)
            # Same selected clauses, candidate semantics, score/constraints; no Full fitting.
            p,_=engine.problem(prepared,time.monotonic()+60)
            score=json.loads(json.dumps(engine.json_score(p.score(model.clauses))));expected=model.fit['training_result']
            diff={k:(score.get(k),v) for k,v in expected.items() if score.get(k)!=v}
            if diff:raise ValueError('FULL_TRAINING_SCORE_REGRESSION:'+str(diff))
            regressions.append({'fold_id':fid,'model_id':model.model_id,'training_score_matched':True,'full_refit_calls':0})
            pre.append({'fold_id':fid,'encoder_fit_calls':0,'preprocessing_fit_calls':0,'candidate_count':len(p.atoms),
                        'encoder_source':str((FULL/'folds'/fid/'encoder.json').relative_to(ROOT))})
            save_or_compare(out/'folds'/fid/'candidate_dependencies.json',[engine.dependency(a) for a in p.atoms])
            for scheme in engine.SCHEMES:
                prepared=engine.prepare(*args,scheme=scheme,**kw);initial=detail=None
                for stage in ('SPARSE','RETENTION'):
                    dest=out/'models'/f'{scheme}__{fid}__{stage}'
                    if (dest/'model.json').exists():
                        fitted=engine.AppModel.from_dict(read(dest/'model.json'));detail=read(dest/'training.json')
                        event=next(e for e in previous if e['scheme']==scheme and e['fold_id']==fid and e['stage']==stage)
                        entries.append(dict(event,closed_at=fitted.fit['freeze_time'],model_id=fitted.model_id,status=fitted.status,
                            path=str((dest/'model.json').relative_to(out)),rule_count=len(fitted.clauses),elapsed_seconds=fitted.fit['elapsed_seconds']))
                        if stage=='SPARSE':initial=fitted
                        continue
                    event={'kind':'rule','fold_id':fid,'scheme':scheme,'stage':stage,'started_at':stamp(),'attempt':1}
                    log.write(json.dumps(event)+'\n');log.flush()
                    fitted,detail=engine.fit(prepared,stage=stage,initial_model=initial,initial_training=detail)
                    dest=out/'models'/f'{scheme}__{fid}__{stage}'
                    write(dest/'model.json',fitted.to_dict());write(dest/'training.json',detail)
                    loaded=engine.AppModel.from_dict(read(dest/'model.json'))
                    if loaded.model_id!=fitted.model_id:raise ValueError('MODEL_ROUNDTRIP_FAILED')
                    e=dict(event,closed_at=stamp(),model_id=fitted.model_id,status=fitted.status,path=str((dest/'model.json').relative_to(out)),rule_count=len(fitted.clauses),elapsed_seconds=fitted.fit['elapsed_seconds'])
                    entries.append(e);events.append(e)
                    print(json.dumps({k:e[k] for k in ('scheme','fold_id','stage','status','rule_count')}),flush=True)
                    if stage=='SPARSE':initial=fitted
            event={'kind':'tree','fold_id':fid,'scheme':'APP_TREE','stage':'FITTED','started_at':stamp(),'attempt':1}
            event['attempt']=1+sum(e['kind']=='tree' and e['fold_id']==fid for e in previous)
            log.write(json.dumps(event)+'\n');log.flush()
            fitted=tree.fit(engine.prepare(*args,scheme='APP_TREE',**kw),out/'engineering'/('tree_fit_recovery_'+fid+'.json'))
            path=out/'models'/('APP_TREE__'+fid)/'model.json';write(path,fitted)
            e=dict(event,closed_at=stamp(),model_id=fitted['model_id'],status=fitted['status'],path=str(path.relative_to(out)),elapsed_seconds=fitted['elapsed_seconds'])
            entries.append(e);events.append(e);print(json.dumps(event),flush=True)
    write(out/'models.json',{'models':entries})
    write(out/'TRAINING_REGRESSION.json',regressions)
    write(out/'PREPROCESSING.json',pre)
    calls=[r['value'] for r in records(out/'FIT_CALLS.jsonl')]
    if Counter(e['kind'] for e in entries)!={'rule':24,'tree':3}:raise ValueError('EXPECTED_ACCEPTED_FIT_SET_MISMATCH')
    write(out/'EXECUTION.json',{'started_at':min(e['started_at'] for e in calls),'frozen_at':stamp(),
          'rule_fit_calls':sum(e['kind']=='rule' for e in calls),'tree_fit_calls':sum(e['kind']=='tree' for e in calls),'accepted_tree_models':3,
          'actual_calls':calls,'accepted_models':entries,'encoder_fit_calls':0,'preprocessing_fit_calls':0,'collection_calls':0,'engineering_fit_reruns':sum(e['kind']=='tree' for e in previous),
          'evaluation_rows_received_during_training':False,'all_fits_closed':True})


def evaluate(out):
    execution=read(out/'EXECUTION.json')
    if not execution['all_fits_closed'] or len(records(out/'FIT_CALLS.jsonl'))!=execution['rule_fit_calls']+execution['tree_fit_calls']:raise ValueError('ALL_FITS_MUST_CLOSE')
    if (out/'predictions.jsonl.gz').exists():raise FileExistsError('USE_SAVED_ONLY_SUMMARY')
    inputs,members=evaluation();saved_members=[r['value'] for r in records(out/'members.jsonl')]
    if saved_members!=[{k:v for k,v in m.items() if k!='saved_models'} for m in members]:raise ValueError('EVALUATION_MEMBERS_CHANGED')
    entries=read(out/'models.json')['models'];predictions=[]
    for scheme in (*engine.SCHEMES,'APP_TREE'):
        for stage in (('FITTED',) if scheme=='APP_TREE' else ('SPARSE','RETENTION')):
            models={e['fold_id']:(read(out/e['path']) if scheme=='APP_TREE' else engine.AppModel.from_dict(read(out/e['path']))) for e in entries if e['scheme']==scheme and e['stage']==stage}
            if len(models)!=3:raise ValueError('THREE_FROZEN_FOLDS_REQUIRED')
            predictions.extend(row_predictions(inputs,members,models,scheme,stage))
    dump_lines(out/'predictions.jsonl.gz',predictions)
    write(out/'EVALUATION.json',{'prediction_calls':len(predictions),'model_positions_per_scheme_stage':3771,'stages':9,
        'fit_calls':0,'collection_calls':0,'closed_at':stamp(),'frozen_at':execution['frozen_at']})
    print(json.dumps({'predictions':len(predictions),'fit_calls':0}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('full','train','evaluate','summarize'))
    p.add_argument('--resume-engineering',action='store_true');p.add_argument('--output',type=Path,default=HERE/'results');args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.command=='summarize':
        from summarize import summarize
        summarize(out)
    elif args.command=='train':train(out,resume=args.resume_engineering)
    else:globals()[args.command](out)
if __name__=='__main__':main()
