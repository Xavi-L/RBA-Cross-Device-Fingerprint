"""Closed, predeclared C schedule. Default CLI action is read-only verification."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from hybridguard_agent.research.rule_learning.baselines import project_core
from hybridguard_agent.research.rule_learning.contracts import ledger
from hybridguard_agent.research.rule_learning.evaluation import evaluate
from hybridguard_agent.research.rule_learning.models import load_model as load_v1
from . import c_engine
from .adapter import TrainAccess
from .b_experiment import B_OUT, base_account as before_b
from .common import ROOT, V1, FROZEN, DOC, read, lines, write, write_lines, relative, stamp, digest, definitions
from .diagnose import metadata
from .pilot import check_settings, preserve_failed_attempt
from .retention import GROUP_VERSION, signal_group
from .trial_summary import inspect_attempt

C_OUT=B_OUT.parent/'C_confirmation'
R08=V1/'R08_validation'
AUTH=c_engine.AUTH
ACCEPTED_B='2d73be0695d4b11db27a83cfbe2d5f951eee4682'
WORKER_CAP=90


def account_base():
    b=read(B_OUT/'linked_budget_ledger.json')
    if (b['state']!='CLOSED_STOP_FOR_USER_REVIEW' or b['base']!=before_b()
            or b['reserved_fits'] or b['reserved_seconds'] or b['actual_fits']!=len(b['attempts'])
            or not math.isclose(b['charged_seconds'],sum(a['charged_seconds'] for a in b['attempts']),abs_tol=1e-9)
            or b['cumulative_fit_jobs']!=b['base']['used_fit_jobs']+b['actual_fits']
            or not math.isclose(b['cumulative_charged_seconds'],b['base']['charged_seconds']+b['charged_seconds'],abs_tol=1e-9)):
        raise ValueError('V1_R09_A_B_ACCOUNT_NOT_RECONCILED')
    return {'B_ledger_ref':relative(B_OUT/'linked_budget_ledger.json'),'prior_links':b['base'],
            'B_fits':b['actual_fits'],'B_charged_seconds':b['charged_seconds'],
            'used_fit_jobs':b['cumulative_fit_jobs'],'charged_seconds':b['cumulative_charged_seconds']}


def update_account(a):
    a['cumulative_fit_jobs']=a['base']['used_fit_jobs']+a['actual_fits']
    a['cumulative_charged_seconds']=a['base']['charged_seconds']+a['charged_seconds']
    a['remaining_research_fits']=200-a['cumulative_fit_jobs']-a['reserved_fits']
    a['remaining_research_seconds']=21600-a['cumulative_charged_seconds']-a['reserved_seconds']
    a['remaining_stage_fits']=36-a['actual_fits']-a['reserved_fits']
    a['remaining_stage_seconds']=1800-a['charged_seconds']-a['reserved_seconds']
    a['updated_at']=stamp()
    tmp=C_OUT/'linked_budget_ledger.tmp';tmp.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,C_OUT/'linked_budget_ledger.json')


def record(event):
    with (C_OUT/'trials.jsonl').open('a') as f:f.write(json.dumps(dict(utc=stamp(),**event),ensure_ascii=False)+'\n')


def runtime_versions():
    names=['c_engine','c_experiment','b_engine','adapter','retention','trial_summary','pilot','common']
    paths=[Path(__file__).parent/(n+'.py') for n in names]
    paths += [ROOT/'hybridguard_agent/research/rule_learning'/(n+'.py') for n in
              ['baselines','contracts','evaluation','fold_data','models','predictor','selector']]
    paths += [ROOT/'hybridguard_agent/config/rule_learning_v1_20260924'/(n+'.json') for n in
              ['candidate_grammar','learning_search_space']]
    return {relative(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def inherited_splits():
    fs=read(R08/'SPLIT_MEMBERS.json')['folds']
    original={f['fold_id']:f for f in read(V1/'R02_matrix/FOLD_INPUT_MANIFEST.json')['folds']}
    meta=metadata();all_ids=set(meta);seen=set();checks=[]
    if len(fs)!=14:raise ValueError('EXACT_ORIGINAL_14_LOCO_FOLDS_REQUIRED')
    for f in fs:
        old=original[f['fold_id']];train,test=set(f['train']),set(f['outer_test'])
        if f['train']!=old['train'] or f['outer_test']!=old['outer_test'] or train & test or train|test!=all_ids or seen & test:
            raise ValueError('ORIGINAL_LOCO_MEMBERSHIP_CHANGED')
        if {meta[i]['config_id'] for i in test}!={f['target']} or any(meta[i]['config_id']==f['target'] for i in train):
            raise ValueError('CONFIGURATION_BOUNDARY_VIOLATION')
        for key in ('triplet_id','bundle_id'):
            if {meta[i][key] for i in train}&{meta[i][key] for i in test}:raise ValueError('GROUP_BOUNDARY:'+key)
        seen|=test
        checks.append({'fold_id':f['fold_id'],'held_out_config':f['target'],'train_n':len(train),'test_n':len(test),
                       'exact_R02_R08_members':True,'triplet_bundle_overlap':0,
                       'shared_environment_groups':sorted({meta[i]['environment_group_id'] for i in train}&{meta[i]['environment_group_id'] for i in test})})
    if seen!=all_ids:raise ValueError('LOCO_EXPECTED_CLOSURE')
    return fs,checks


def compatible_c0(fs):
    jobs={j['fold_id']:j for j in lines(R08/'expected_fit_jobs.jsonl')}
    predictions=[r for r in lines(R08/'oof_predictions.jsonl') if r['method_id']=='GREEDY_OR' and r['operating_point']=='OP05']
    _,atoms=project_core({},ledger(),'SRC-111');expected_atoms=sorted(a.atom_id for a in atoms)
    out=[]
    for f in fs:
        try:
            j=jobs[f['fold_id']];path=R08/'fold_models'/(j['job_id']+'.json');m=load_v1(path)
            p=[r for r in predictions if r['fold_id']==f['fold_id']]
            if (j['train_ids']!=f['train'] or j['outer_test_ids']!=f['outer_test'] or m.fit['train_ids']!=f['train']
                    or m.binding['split_id']!='LOCO-v1' or m.binding['fold_id']!=f['fold_id']
                    or m.method_id!='GREEDY_OR' or m.binding['operating_point']!='OP05'
                    or sorted(m.view['input_atom_ids'])!=expected_atoms or m.view['source_condition']!='SRC-111'
                    or sorted(r['opaque_id'] for r in p)!=sorted(f['outer_test'])
                    or any(r['model_id']!=m.model_id for r in p)):
                raise ValueError('SAVED_C0_CONTRACT_OR_PREDICTION_BINDING_MISMATCH')
            out.append({'fold_id':f['fold_id'],'status':'COMPATIBLE_SAVED_ONLY','model_ref':relative(path),
                        'model_id':m.model_id,'predictions_ref':relative(R08/'oof_predictions.jsonl'),
                        'train_n':len(f['train']),'test_n':len(p),'source_condition':'SRC-111','operating_point':'OP05',
                        'measurement_contract':'Original R02 cache/canonical core and unchanged V1 configs',
                        'original_job_ref':relative(R08/'expected_fit_jobs.jsonl')+'#'+j['job_id']})
        except (ValueError,KeyError,TypeError,OSError) as exc:
            out.append({'fold_id':f['fold_id'],'status':'INCOMPATIBLE_NOT_POOLED','reason':str(exc),'new_fits':0})
    return out


def attempt_dir(job):return C_OUT/'trials'/(job['job_id']+'__attempt01')


def plan_jobs(fs):
    ids=sorted(metadata());jobs=[]
    def pair(track,fold,train,test,target=None):
        specs=[('C0','GREEDY_OR'),('W0','GREEDY_OR'),('W0','R_KEEP_V1')] if track=='FINAL_DEVELOPMENT_FIT' else [('W0','GREEDY_OR'),('W0','R_KEEP_V1')]
        for rep,method in specs:
            job={'job_id':'V2-C__'+fold+'__'+rep+'__'+method,'spec_id':rep+'__'+method,'representation':rep,
                 'base_representation':rep,'method':method,'track':track,'fold_id':fold,'train_ids':train,
                 'outer_test_ids':test,'evaluation_ids':train if track=='FINAL_DEVELOPMENT_FIT' else test,
                 'evaluation_role':c_engine.FINAL_ROLE if track=='FINAL_DEVELOPMENT_FIT' else c_engine.LOCO_ROLE,
                 'operating_point':'OP05','held_out_config':target,'attempt':1}
            if method=='R_KEEP_V1':job['initial_model_ref']=relative(C_OUT/'trials'/('V2-C__'+fold+'__W0__GREEDY_OR__attempt01')/'model.json')
            jobs.append(job)
    pair('FINAL_DEVELOPMENT_FIT','ALL_DEVELOPMENT_162',ids,[])
    for f in fs:pair('LOCO-v1',f['fold_id'],f['train'],f['outer_test'],f['target'])
    return jobs


def prepare(authorization,gate):
    if authorization!=AUTH:raise PermissionError('EXPLICIT_C_AUTHORIZATION_REQUIRED')
    if (C_OUT/'C_CONTRACT.json').exists():raise FileExistsError('C_EXISTS_RECONCILE_DO_NOT_REPLAN')
    test=read(C_OUT/gate)
    if test['status']!='PASS':raise ValueError('ENGINEERING_GATE_REQUIRED')
    subprocess.run(['git','merge-base','--is-ancestor',ACCEPTED_B,'HEAD'],cwd=ROOT,check=True)
    base=account_base();fs,boundaries=inherited_splits();jobs=plan_jobs(fs);codes=runtime_versions()
    saved=read(B_OUT/'signal_groups_v1.json')
    from .adapter import approved_atoms
    from .b_engine import selected_definitions
    mapping={m['atom_id']:m['group'] for m in saved['members']}
    if any(mapping[a.atom_id]!=signal_group(a) for a in approved_atoms(selected_definitions(definitions(),'W0'))):
        raise ValueError('B_SIGNAL_GROUP_MAPPING_CHANGED')
    path='hybridguard_agent/research/rule_learning_v2/retention.py'
    if subprocess.check_output(['git','show',ACCEPTED_B+':'+path],cwd=ROOT)!=(ROOT/path).read_bytes():raise ValueError('B_RETENTION_PROGRAM_CHANGED')
    for p,sha in codes.items():
        if '/rule_learning_v2/' in p:
            target=C_OUT/'code_versions'/(Path(p).stem+'-'+sha[:12]+'.py');target.parent.mkdir(exist_ok=True)
            with target.open('xb') as f:f.write((ROOT/p).read_bytes())
    contract={'schema_version':'v2-c-contract-v1','phase':'V2-C','authorization_id':AUTH,'created_at':stamp(),
       'accepted_B_commit':ACCEPTED_B,'accepted_candidate':'W0__R_KEEP_V1','method_development':False,
       'planned_fits':31,'stage_fit_cap':36,'engineering_retry_allowance':5,'retry_policy':'Only explicitly documented engineering failures; never tune or repeat a valid negative result; no automatic retry.',
       'stage_seconds_cap':1800,'research_limits':{'fits':200,'seconds':21600},'worker_wall_cap':WORKER_CAP,'max_batch_fits':12,
       'base_account':base,'settings':check_settings(),'signal_group_version':GROUP_VERSION,
       'signal_groups_ref':relative(B_OUT/'signal_groups_v1.json'),'retention_contract':read(B_OUT/'B_CONTRACT.json')['retention_preference'],
       'source_index':relative(FROZEN/'DATA_INDEX.json'),'data_role':'V1_EXPOSED_DEVELOPMENT','supervised_stages':162,
       'attack':54,'clean_pre':54,'clean_post':54,'descriptive_100_excluded':True,
       'billing_scope':'Worker wall time from launch through inputs, all registered train stages, save/load, roundtrip predictions and evaluation; every worker attempt debits a fit, including failures.',
       'fixed_inference_and_synthetic_timing':'Separate non-fit purpose/time records; never hidden threshold learning.',
       'jobs':jobs,'runtime_versions':codes,'engineering_gate':gate,
       'inference_inputs':'Current allowed session features only; no labels, phase, tool, configuration/environment/record IDs, paths, declared modifications or past/future session values.',
       'roles_not_pooled':[c_engine.FINAL_ROLE,c_engine.LOCO_ROLE,'B_SAVED_LOEO_DEVELOPMENT'],
       'confirmation_access':'NOT_AUTHORIZED','automatic_git':False,'stop':'DEVELOPMENT_COMPLETE_CONFIRMATION_PENDING when all internal required work is done; otherwise PARTIAL with explicit missing work.'}
    write(C_OUT/'C_CONTRACT.json',contract)
    write(C_OUT/'METHOD_FREEZE.json',{'created_at':contract['created_at'],'B_learning_program_unchanged':True,
       'retention_source_exact_accepted_B':True,'W0_signal_groups_equal_B':True,'settings':contract['settings'],
       'runtime_versions':codes,'data_dependent_fit':'Own train quantiles/support/selection for each job; saved matching W0 initialization reused only within the same train/fold.',
       'C0_W0_syntax':'Original core/SINGLE_SURFACE App Web candidates and polarity/aliases; no new relations or matched parser atoms.',
       'all_C_jobs_frozen_before_results':True,'all_jobs_ref':'C_CONTRACT.json','probe_plan_ref':'STRUCTURAL_PROBE_PLAN.json'})
    write(C_OUT/'input_manifest.json',{'source_index':contract['source_index'],'supervised_ids':sorted(metadata()),
       'membership_digest':digest(sorted(metadata())),'LOCO_boundaries':boundaries,'original_splits_ref':relative(R08/'SPLIT_MEMBERS.json'),
       'new_independent_material_opened':False})
    write(C_OUT/'C0_LOCO_REUSE.json',compatible_c0(fs))
    from .c_probes import specification
    write(C_OUT/'STRUCTURAL_PROBE_PLAN.json',specification())
    batches=[('C01_final',jobs[:3]),('C02_loco_01_06',jobs[3:15]),('C03_loco_07_12',jobs[15:27]),('C04_loco_13_14',jobs[27:])]
    account={'schema_version':'v2-c-linked-budget-v1','state':'AUTHORIZED_RUNNING','base':base,
             'actual_fits':0,'charged_seconds':0.,'reserved_fits':0,'reserved_seconds':0.,'attempts':[],'batches':[]}
    for name,subset in batches:
        batch={'batch_id':name,'created_at':stamp(),'contract_digest':digest(contract),'jobs':subset,
               'runtime_versions':codes,'max_reserved_seconds':WORKER_CAP*len(subset),'automatic_retry':False}
        write(C_OUT/'batches'/name/'batch_spec.json',batch)
        account['batches'].append({'batch_id':name,'state':'PLANNED','fit_n':len(subset)})
    update_account(account);record({'event':'ALL_31_JOBS_FROZEN_BEFORE_FIRST_FIT','contract_ref':'C_CONTRACT.json'})
    return {'planned_fits':len(jobs),'batches':[n for n,_ in batches],'base':base}


def validate(authorization):
    if authorization!=AUTH:raise PermissionError('EXPLICIT_C_AUTHORIZATION_REQUIRED')
    a=read(C_OUT/'linked_budget_ledger.json');c=read(C_OUT/'C_CONTRACT.json')
    if a['state']!='AUTHORIZED_RUNNING':raise PermissionError('C_CLOSED_NO_NEW_FITS')
    if a['base']!=account_base():raise ValueError('PRIOR_RESEARCH_ACCOUNT_CHANGED')
    if c['runtime_versions']!=runtime_versions() or c['settings']!=check_settings():raise PermissionError('FROZEN_C_PROGRAM_CHANGED_ENGINEERING_REVISION_REQUIRED')
    return a,c


def execute(job,c,dest):
    write(dest/'worker_claim.json',{'claimed_once_at':stamp(),'pid':os.getpid()})
    events=[]
    def event(name,**kw):events.append(dict(event=name,utc=stamp(),**kw))
    index=read(FROZEN/'DATA_INDEX.json');raw={};meta={};defs=definitions()
    for i in job['train_ids']:
        raw[i]=read(FROZEN/index[i]['features'])['features'];meta[i]=read(FROZEN/index[i]['evaluation'])
    event('EXACT_TRAIN_OPENED',ids=job['train_ids'],outer_members_opened=0,
          later_resubstitution_same_members=job['track']=='FINAL_DEVELOPMENT_FIT')
    access=TrainAccess(job,c_engine.project_inputs(raw,defs,job['representation']),meta)
    binding={'study_version':'discriminative-rule-learning-v2-20260925','phase':'V2-C','authorization_id':AUTH,
       'protocol_digest':digest(c),'candidate_version':GROUP_VERSION,'fold_id':job['fold_id'],'split_id':job['track'],
       'operating_point':'OP05','model_unit_id':job['job_id'],'representation':job['representation'],
       'method_id':job['method'],'train_membership_digest':digest(job['train_ids']),
       'evaluation_role':job['evaluation_role'],'data_origin':'V1_EXPOSED_DEVELOPMENT'}
    write_lines(dest/'fit_invocations.jsonl',[{'event':'FIT_STARTED','utc':stamp(),'fit_count':1,'train_ids':job['train_ids'],
       'operation':'C_LEARN_ONE_MODEL','internal_stages':['frozen_encoder_sparse_reuse' if job.get('initial_model_ref') else 'train_encoder_sparse_fit','train_support','signal_retention' if job['method']=='R_KEEP_V1' else 'sparse_selection']}])
    original,training=c_engine.fit_c(access,defs,job,binding)
    write(dest/'training.json',training);c_engine.save_model(original,dest/'model.json');model=c_engine.load_model(dest/'model.json')
    event('MODEL_ENCODER_SAVED_LOADED_FROZEN',model_id=model.model_id)
    predictions=[];roundtrip=0
    for i in job['evaluation_ids']:
        row=read(FROZEN/index[i]['features'])['features'];event('OPEN_EVALUATION_FEATURE_AFTER_FREEZE',opaque_id=i)
        projected=c_engine.project_inputs({i:row},defs,job['representation'])[i]
        pred=c_engine.predict_current(model,i,projected)
        if pred!=c_engine.predict_current(original,i,projected):raise ValueError('MODEL_SAVE_LOAD_PREDICTION_DIFFERENCE')
        roundtrip+=1;predictions.append(pred)
    write_lines(dest/'predictions.jsonl',predictions);event('PREDICTIONS_SAVED_CLOSED',n=len(predictions))
    evaluation={i:read(FROZEN/index[i]['evaluation']) for i in job['evaluation_ids']}
    event('EVALUATION_LABEL_JOIN_AFTER_CLOSURE',ids=job['evaluation_ids'],training_labels_previously_used=job['track']=='FINAL_DEVELOPMENT_FIT')
    write(dest/'metrics.json',evaluate(job['evaluation_ids'],predictions,evaluation,evaluation_role=job['evaluation_role'],strata=True))
    write(dest/'access_log.json',events)
    write(dest/'receipt.json',{'state':model.status,'model_id':model.model_id,'fit_status':model.fit['status'],
          'predictions':len(predictions),'roundtrip_equal':roundtrip,'actual_fit_invocations':1,'ended_at':stamp()})


def run_batch(name,authorization):
    lock=C_OUT/'execution.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    try:
        a,c=validate(authorization);b=read(C_OUT/'batches'/name/'batch_spec.json')
        if b['contract_digest']!=digest(c) or b['runtime_versions']!=c['runtime_versions']:raise ValueError('BATCH_BINDING')
        if any(j not in c['jobs'] for j in b['jobs']) or len(b['jobs'])>12:raise ValueError('UNREGISTERED_BATCH_JOB')
        entry=next(x for x in a['batches'] if x['batch_id']==name)
        if entry['state']!='PLANNED':raise PermissionError('BATCH_ALREADY_EXECUTED_OR_NEEDS_RECONCILIATION')
        if a['reserved_fits'] or any(x['state']=='RUNNING_RESERVED' for x in a['attempts']):raise ValueError('UNRESOLVED_RESERVATION')
        n=len(b['jobs']);seconds=WORKER_CAP*n
        if (a['actual_fits']+n>31 or a['charged_seconds']+seconds>1800 or
                a['cumulative_fit_jobs']+n>200 or a['cumulative_charged_seconds']+seconds>21600):raise ValueError('BUDGET_LIMIT')
        if any(x['job_id']==j['job_id'] for x in a['attempts'] for j in b['jobs']):raise ValueError('DUPLICATE_FIT_FORBIDDEN')
        a['reserved_fits']=n;a['reserved_seconds']=seconds;entry['state']='RESERVED';update_account(a)
        record({'event':'BATCH_RESERVED','batch_id':name,'fits':n,'seconds':seconds})
        for job in b['jobs']:
            dest=attempt_dir(job);dest.mkdir(parents=True,exist_ok=False)
            write(dest/'attempt_spec.json',{'job':job,'batch_spec_ref':relative(C_OUT/'batches'/name/'batch_spec.json'),'contract_digest':digest(c)})
            a=read(C_OUT/'linked_budget_ledger.json')
            trial={'job_id':job['job_id'],'batch_id':name,'track':job['track'],'spec_id':job['spec_id'],'state':'RUNNING_RESERVED',
                   'attempt':1,'directory':relative(dest),'started_at':stamp()}
            a['actual_fits']+=1;a['reserved_fits']-=1;a['attempts'].append(trial);update_account(a);record(dict(event='ATTEMPT_STARTED',**trial))
            started=time.monotonic();error=None
            with (dest/'stdout.txt').open('x') as out,(dest/'stderr.txt').open('x') as err:
                try:
                    process=subprocess.run([sys.executable,'-m','hybridguard_agent.research.rule_learning_v2.c_experiment','_worker','--batch',name,'--job',job['job_id'],'--authorization',AUTH],cwd=ROOT,stdout=out,stderr=err,timeout=WORKER_CAP)
                    if process.returncode:error='WORKER_EXIT_'+str(process.returncode)
                except subprocess.TimeoutExpired:error='WORKER_TIMEOUT'
            charged=time.monotonic()-started
            if error:preserve_failed_attempt(dest,dict(job,outer_test_ids=job['evaluation_ids']),error)
            result=inspect_attempt(dest,dict(job,outer_test_ids=job['evaluation_ids']),c_engine.load_model)
            a=read(C_OUT/'linked_budget_ledger.json');trial=next(x for x in a['attempts'] if x['job_id']==job['job_id'])
            trial.update(state='FAILED' if result['audit']['status']!='OK' else result['model'].status,
                         charged_seconds=charged,ended_at=stamp(),integrity_status=result['audit']['status'])
            a['charged_seconds']+=charged;a['reserved_seconds']-=WORKER_CAP;update_account(a)
            record(dict(event='ATTEMPT_CLOSED',**trial))
        a=read(C_OUT/'linked_budget_ledger.json');next(x for x in a['batches'] if x['batch_id']==name)['state']='CLOSED';update_account(a)
        record({'event':'BATCH_CLOSED','batch_id':name})
        return {'batch_id':name,'actual_fits':a['actual_fits'],'charged_seconds':a['charged_seconds']}
    finally:lock.unlink()


def verify():
    a=read(C_OUT/'linked_budget_ledger.json');c=read(C_OUT/'C_CONTRACT.json');checks=[]
    if a['base']!=account_base():raise ValueError('ACCOUNT_BASE_CHANGED')
    if not math.isclose(a['charged_seconds'],sum(x['charged_seconds'] for x in a['attempts']),abs_tol=1e-9):raise ValueError('ACCOUNT_SUM')
    for x in a['attempts']:
        job=next(j for j in c['jobs'] if j['job_id']==x['job_id'])
        result=inspect_attempt(ROOT/x['directory'],dict(job,outer_test_ids=job['evaluation_ids']),c_engine.load_model)
        checks.append(dict(result['audit'],job_id=job['job_id'],track=job['track'],expected_state=x['state']))
    return {'action':'READ_ONLY_SAVED_RESULT_VERIFICATION','state':a['state'],'actual_fits':a['actual_fits'],
            'charged_seconds':a['charged_seconds'],'checks':checks,'new_fits':0,'new_predictions':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',nargs='?',default='verify',choices=['verify','prepare','run','_worker'])
    parser.add_argument('--authorization');parser.add_argument('--gate');parser.add_argument('--batch');parser.add_argument('--job');args=parser.parse_args()
    if args.command=='verify':result=verify()
    elif args.command=='prepare':result=prepare(args.authorization,args.gate)
    elif args.command=='run':result=run_batch(args.batch,args.authorization)
    else:
        a,c=validate(args.authorization);job=next(j for j in c['jobs'] if j['job_id']==args.job)
        active=next(x for x in a['attempts'] if x['job_id']==args.job)
        if active['state']!='RUNNING_RESERVED' or active['batch_id']!=args.batch:raise PermissionError('NO_ACTIVE_C_RESERVATION')
        execute(job,c,ROOT/active['directory']);return
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
