"""Bounded V2-B batches with linked accounting and immutable real attempts."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from hybridguard_agent.research.rule_learning.evaluation import evaluate
from .common import ROOT, V1, FROZEN, OUT as A_OUT, DOC, ROLE, read, lines, write, write_lines, relative, stamp, digest, definitions, folds, budget_base
from .adapter import TrainAccess, approved_atoms
from .pilot import check_settings, preserve_failed_attempt
from . import b_engine
from .retention import signal_group, GROUP_VERSION
from .trial_summary import inspect_attempt

B_OUT = A_OUT.parent/'B_development'
AUTH = 'USER_V2_B_LIMITED_METHOD_ITERATION_20260925'


def base_account():
    previous = budget_base()
    a = read(A_OUT/'linked_budget_ledger.json')
    if (a['state'] != 'CLOSED_STOP_FOR_USER_REVIEW' or a['base'] != previous
            or a['actual_fits'] != len(a['attempts'])
            or not math.isclose(a['charged_seconds'], sum(x['elapsed_seconds'] for x in a['attempts']), abs_tol=1e-9)
            or any(x['state'] == 'RUNNING_RESERVED' for x in a['attempts'])):
        raise ValueError('A_LINKED_ACCOUNT_UNRESOLVED')
    fit_count = previous['used_fit_jobs'] + a['actual_fits']
    seconds = previous['charged_seconds'] + a['charged_seconds']
    if a['cumulative_fit_jobs'] != fit_count or not math.isclose(a['cumulative_charged_seconds'], seconds, abs_tol=1e-9):
        raise ValueError('A_CUMULATIVE_ACCOUNT_MISMATCH')
    return {'v1_and_r09':previous, 'A_ledger_ref':relative(A_OUT/'linked_budget_ledger.json'),
            'A_fit_jobs':a['actual_fits'],'A_charged_seconds':a['charged_seconds'],
            'used_fit_jobs':fit_count,'charged_seconds':seconds,
            'remaining_fits':previous['limits']['max_fit_jobs']-fit_count,
            'remaining_seconds':previous['limits']['wall_clock_seconds']-seconds}


def update_account(account):
    account['cumulative_fit_jobs'] = account['base']['used_fit_jobs'] + account['actual_fits']
    account['cumulative_charged_seconds'] = account['base']['charged_seconds'] + account['charged_seconds']
    account['remaining_stage_fits'] = 60-account['actual_fits']-account['reserved_fits']
    account['remaining_stage_seconds'] = 3600-account['charged_seconds']-account['reserved_seconds']
    account['remaining_research_fits'] = 200-account['cumulative_fit_jobs']-account['reserved_fits']
    account['remaining_research_seconds'] = 21600-account['cumulative_charged_seconds']-account['reserved_seconds']
    account['updated_at'] = stamp()
    tmp = B_OUT/'linked_budget_ledger.tmp'
    tmp.write_text(json.dumps(account,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp, B_OUT/'linked_budget_ledger.json')


def record(event):
    with (B_OUT/'trials.jsonl').open('a') as f:
        f.write(json.dumps(dict(utc=stamp(),**event),ensure_ascii=False)+'\n'); f.flush()


def start():
    if (B_OUT/'B_CONTRACT.json').exists():
        raise FileExistsError('B_ALREADY_INITIALIZED_RECONCILE_EXISTING_ACCOUNT')
    base = base_account(); settings = check_settings()
    contract = {'schema_version':'v2-b-contract-v1','phase':'V2-B','authorization_id':AUTH,
        'authorization':'Explicit pasted user request in current task; A accepted at 72a7c74d97b04f0bcce202a5d482e02c1e4e9cad.',
        'accepted_A_commit':'72a7c74d97b04f0bcce202a5d482e02c1e4e9cad','created_at':stamp(),
        'evaluation_role':ROLE,'stage_fit_cap':60,'stage_seconds_cap':3600,
        'max_new_specs_per_batch':4,'max_fits_per_batch':12,'worker_wall_cap_seconds':90,
        'shared_research_caps':{'fits':200,'seconds':21600},'base_account':base,
        'inherited_settings':settings,'A_contract_read_only_ref':relative(DOC/'DEFAULT_DEV_CONTRACT.json'),
        'fit_accounting':'Each independently learned model costs one fit; encoder/support/sparse initialization/retention are recorded internal stages. Saved sparse reuse does not refit its encoder. No unregistered diagnostic fit.',
        'billing_scope':'Each worker wall time includes input, all train stages, save/load, prediction and evaluation. Every attempted worker consumes the fit cap, including failures; no automatic retries.',
        'sparse_objective':'Inherited MacroTPR - 0.005*complexity',
        'retention_preference':{'name':'R_KEEP_V1','initialization':'Matching saved fold sparse model, or explicitly counted internal sparse initialization',
          'D':'sum_group sum_train_attack macro_weight[i] * any_T_in_group(S,i)',
          'constraints':'Original support, per-phase coverage >=0.8, no train failures, union clean floor(.05*N), <=6 clauses, <=12 complexity, original family caps, no attack detection loss',
          'tie_break':['higher_added_train_macro_detection','higher_added_D','lower_final_clean_alarms','lower_final_complexity','stable_clause_id'],
          'post_retention_sparse_pruning':False,'same_objective_claim':False,'new_optimization_or_generalization_guarantee':False},
        'relation_families_allowed':['memory','language','timezone'],
        'data':{'supervised_stages':162,'attack':54,'clean_pre':54,'clean_post':54,'triplets':54,'split':'original LOEO-v1, exact bundle/environment boundaries','descriptive_100_fit':False,'UNKNOWN_or_MTC_as_clean':False},
        'prediction':'Current allowed session fields only; no labels/phase/config/group/tool/IDs/paths/pre/post or modified-field lists in conditions',
        'freeze_before_evaluation_features':True,'predictions_close_before_evaluation_labels':True,
        'protected_paths':[relative(A_OUT),relative(V1),'hybridguard_agent/research/rule_learning','hybridguard_agent/config/rule_learning_v1_20260924'],
        'excluded':['new collection','attack tools','paid services','arbitrary string vocabulary or unique IDs','IP','DNF2','column generation','whole-development final fit','confirmation access','V2-C','R10','V3','automatic Git writes'],
        'stop':'Complete bounded attribution and one primary/at most one alternate or NO_IMPROVING_CANDIDATE; wait for user review'}
    write(B_OUT/'B_CONTRACT.json', contract)
    account={'schema_version':'v2-b-linked-budget-v1','base':base,'actual_fits':0,'charged_seconds':0.,
             'reserved_fits':0,'reserved_seconds':0.,'attempts':[],'batches':[],'state':'AUTHORIZED_RUNNING'}
    update_account(account)
    from hybridguard_agent.research.rule_learning.baselines import project_core
    from hybridguard_agent.research.rule_learning.contracts import ledger
    _, core=project_core({},ledger(),'SRC-111')
    atoms=approved_atoms(definitions())+core
    write(B_OUT/'signal_groups_v1.json', {'version':GROUP_VERSION,'created_before_real_fits':True,
       'basis':'Field provenance and predicate semantics, never holdout misses; grouping is a retention preference, not global logical equivalence.',
       'numeric_thresholds_inherit_raw_field_group':True,'polarity_does_not_create_a_new_group':True,
       'members':[{'atom_id':a.atom_id,'group':signal_group(a),'aliases':a.aliases,'family':a.family,'provenance':a.provenance} for a in atoms]})
    print(json.dumps({'base':base,'B_status':'INITIALIZED'},ensure_ascii=False))


def code_versions(paths=None):
    if paths is None: paths=[relative(p) for p in Path(__file__).parent.glob('*.py')]
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}


def prepare_batch(batch_id, specs, rationale, tests):
    account=read(B_OUT/'linked_budget_ledger.json')
    if account['state']!='AUTHORIZED_RUNNING': raise PermissionError('B_STAGE_CLOSED_REQUIRES_NEW_AUTHORIZATION')
    if account['base'] != base_account(): raise ValueError('HISTORICAL_BUDGET_CHANGED')
    if account['reserved_fits'] or any(a['state']=='RUNNING_RESERVED' for a in account['attempts']):
        raise ValueError('UNRECONCILED_EXISTING_BATCH')
    if not 1<=len(specs)<=4: raise ValueError('B_BATCH_SPEC_LIMIT')
    if any(read(B_OUT/t)['status']!='PASS' for t in tests): raise ValueError('SYNTHETIC_GATE_NOT_PASS')
    settings=check_settings(); jobs=[]
    fs=folds()
    for spec in specs:
        for f in fs:
            s=copy.deepcopy(spec)
            refs=s.pop('initial_model_refs',{})
            if refs: s['initial_model_ref']=refs[f['fold_id']]
            jobs.append(dict(s,job_id=batch_id+'__'+s['spec_id']+'__'+f['fold_id'],fold_id=f['fold_id'],
                 train_ids=f['train'],outer_test_ids=f['outer_test'],operating_point='OP05',attempt=1))
    n=len(jobs); seconds=90*n
    if n>12 or account['actual_fits']+n>60 or account['charged_seconds']+seconds>3600:
        raise ValueError('B_STAGE_OR_BATCH_BUDGET')
    if account['cumulative_fit_jobs']+n>200 or account['cumulative_charged_seconds']+seconds>21600:
        raise ValueError('SHARED_RESEARCH_BUDGET')
    d=B_OUT/'batches'/batch_id;d.mkdir(parents=True,exist_ok=False)
    codes=code_versions()
    # Only changed source bytes are stored, once per content version; no data copies.
    for path, sha in codes.items():
        destination=B_OUT/'code_versions'/(Path(path).stem+'-'+sha[:12]+'.py')
        if not destination.exists():
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes((ROOT/path).read_bytes())
    spec={'schema_version':'v2-b-batch-v1','batch_id':batch_id,'created_at':stamp(),'phase':'V2-B',
          'authorization_id':AUTH,'contract_ref':relative(B_OUT/'B_CONTRACT.json'),
          'basis_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'code_versions':codes,'candidate_group_version':GROUP_VERSION,'settings':settings,
          'evaluation_role':ROLE,'rationale':rationale,'synthetic_tests':tests,'specs':specs,'jobs':jobs,
          'base_and_prior_B_account':{k:account[k] for k in ['cumulative_fit_jobs','cumulative_charged_seconds','actual_fits','charged_seconds']},
          'reservation':{'fits':n,'seconds':seconds,'worker_cap':90},'automatic_retry':False,
          'source_index':relative(FROZEN/'DATA_INDEX.json'),'unique_supervised_stages':162}
    if any(s.get('relation_families') or s.get('matched_single_features') for s in specs):
        spec['relation_registry_ref']=relative(B_OUT/'relation_registry_v1.json')
        spec['relation_registry_digest']=digest(read(B_OUT/'relation_registry_v1.json'))
        spec['relation_version']=read(B_OUT/'relation_registry_v1.json')['version']
    write(d/'batch_spec.json',spec)
    account['reserved_fits']+=n;account['reserved_seconds']+=seconds
    account['batches'].append({'batch_id':batch_id,'spec_ref':relative(d/'batch_spec.json'),'state':'RESERVED','fits':n,'reserved_seconds':seconds})
    update_account(account);record({'event':'BATCH_RESERVED','batch_id':batch_id,'fits':n,'seconds':seconds})
    return spec


def validate(spec):
    c=read(B_OUT/'B_CONTRACT.json')
    if spec['authorization_id']!=AUTH or c['authorization_id']!=AUTH or spec['phase']!='V2-B':
        raise PermissionError('V2_B_AUTHORIZATION_REQUIRED')
    if spec['code_versions']!=code_versions(spec['code_versions']) or spec['settings']!=check_settings():
        raise PermissionError('CODE_OR_CONTRACT_CHANGED_NEW_BATCH_VERSION_REQUIRED')
    if spec.get('relation_registry_digest') and spec['relation_registry_digest']!=digest(read(ROOT/spec['relation_registry_ref'])):
        raise PermissionError('RELATION_REGISTRY_CHANGED')
    if not 1<=len(spec['specs'])<=4 or len(spec['jobs'])>12: raise PermissionError('B_BATCH_LIMIT')
    for j in spec['jobs']:
        f=next(f for f in folds() if f['fold_id']==j['fold_id'])
        if j['train_ids']!=f['train'] or j['outer_test_ids']!=f['outer_test']:
            raise ValueError('EXACT_INHERITED_FOLD_REQUIRED')


def execute(job, spec, dest):
    events=[]
    def event(name,**data): events.append({'event':name,'utc':stamp(),**data})
    index=read(FROZEN/'DATA_INDEX.json');raw={};meta={}
    for i in job['train_ids']:
        raw[i]=read(FROZEN/index[i]['features'])['features'];meta[i]=read(FROZEN/index[i]['evaluation'])
    event('EXACT_TRAIN_OPENED',ids=job['train_ids'],evaluation_members_opened=0)
    relation_rows=None
    if job.get('relation_families') or job.get('matched_single_features'):
        from .relations import load_payloads, relation_fields
        relation_rows=load_payloads(job['train_ids'],relation_fields(job))
        event('EXACT_TRAIN_RELATION_FIELDS_OPENED',ids=job['train_ids'])
    access=TrainAccess(job,b_engine.project_inputs(raw,definitions(),job['base_representation']),meta)
    binding={'study_version':'discriminative-rule-learning-v2-20260925','phase':'V2-B','protocol_digest':digest(spec),
             'authorization_id':AUTH,'fold_id':job['fold_id'],'split_id':'LOEO-v1','operating_point':'OP05',
             'candidate_version':spec['candidate_group_version']+'+'+spec.get('relation_version','NO_NEW_RELATIONS'),'input_manifest_ref':spec['source_index'],
             'model_unit_id':job['job_id'],'representation':job['representation'],'method_id':job['method'],
             'evaluation_role':ROLE,'data_origin':'V1_EXPOSED_DEVELOPMENT'}
    write_lines(dest/'fit_invocations.jsonl',[{'event':'FIT_STARTED','utc':stamp(),'operation':'V2_B_LEARN_ONE_MODEL','fit_count':1,
       'internal_stages':['saved_encoder_and_sparse_reuse' if job.get('initial_model_ref') else 'train_encoder_and_sparse_fit','train_support','train_signal_retention' if job['method']=='R_KEEP_V1' else 'sparse_selection'],'train_ids':job['train_ids']}])
    model,training=b_engine.fit_b(access,definitions(),job,binding,relation_rows)
    write(dest/'training.json',training);b_engine.save_model(model,dest/'model.json')
    model=b_engine.load_model(dest/'model.json')
    if model.fit['train_ids']!=job['train_ids']: raise ValueError('MODEL_TRAIN_MEMBERS')
    event('MODEL_ENCODER_SAVED_LOADED_FROZEN',model_id=model.model_id)
    predictions=[]
    for i in job['outer_test_ids']:
        raw=read(FROZEN/index[i]['features'])['features']
        payload=None
        if relation_rows is not None:
            payload=load_payloads([i],relation_fields(job))[i]
        event('OPEN_OWN_EVALUATION_FEATURE',opaque_id=i)
        projected=b_engine.project_inputs({i:raw},definitions(),job['base_representation'])[i]
        predictions.append(b_engine.predict_current(model,i,projected,payload))
    write_lines(dest/'predictions.jsonl',predictions)
    if [r['opaque_id'] for r in predictions]!=job['outer_test_ids']: raise ValueError('PREDICTION_CLOSURE')
    event('PREDICTIONS_SAVED_CLOSED',n=len(predictions))
    evaluation={i:read(FROZEN/index[i]['evaluation']) for i in job['outer_test_ids']}
    event('EVALUATION_SIDECAR_JOIN_AFTER_CLOSURE',ids=job['outer_test_ids'])
    write(dest/'metrics.json',evaluate(job['outer_test_ids'],lines(dest/'predictions.jsonl'),evaluation,evaluation_role=ROLE,strata=False))
    write(dest/'access_log.json',events)
    receipt={'state':model.status,'model_id':model.model_id,'fit_status':model.fit['status'],
             'predictions':len(predictions),'actual_fit_invocations':1,'ended_at':stamp()}
    write(dest/'receipt.json',receipt)


def run_batch(batch_id):
    if read(B_OUT/'linked_budget_ledger.json')['state']!='AUTHORIZED_RUNNING':
        raise PermissionError('B_STAGE_CLOSED_REQUIRES_NEW_AUTHORIZATION')
    spec=read(B_OUT/'batches'/batch_id/'batch_spec.json');validate(spec)
    for job in spec['jobs']:
        account=read(B_OUT/'linked_budget_ledger.json')
        prior=[a for a in account['attempts'] if a['job_id']==job['job_id']]
        if prior:
            if any(a['state']=='RUNNING_RESERVED' for a in prior): raise ValueError('RECONCILE_INTERRUPTED_ATTEMPT_BEFORE_CONTINUING')
            continue
        dest=B_OUT/'trials'/(job['job_id']+'__attempt01');dest.mkdir(parents=True,exist_ok=False)
        write(dest/'attempt_spec.json',{'job':job,'batch_spec_ref':relative(B_OUT/'batches'/batch_id/'batch_spec.json'),'batch_digest':digest(spec)})
        entry={'job_id':job['job_id'],'batch_id':batch_id,'spec_id':job['spec_id'],'state':'RUNNING_RESERVED',
               'started_at':stamp(),'directory':relative(dest),'reserved_seconds':90,'attempt':1}
        account['actual_fits']+=1;account['reserved_fits']-=1;account['attempts'].append(entry)
        update_account(account);record(dict(event='ATTEMPT_STARTED',**entry))
        started=time.monotonic()
        with (dest/'stdout.txt').open('x') as stdout,(dest/'stderr.txt').open('x') as stderr:
            try:
                result=subprocess.run([sys.executable,'-m','hybridguard_agent.research.rule_learning_v2.b_experiment','_worker',batch_id,job['job_id']],cwd=ROOT,stdout=stdout,stderr=stderr,timeout=90)
                if result.returncode: raise RuntimeError('WORKER_EXIT_'+str(result.returncode))
                receipt=read(dest/'receipt.json')
            except Exception as exc:
                receipt=preserve_failed_attempt(dest,job,type(exc).__name__+':'+str(exc))
        elapsed=time.monotonic()-started
        entry.update(state=receipt['state'],ended_at=stamp(),charged_seconds=elapsed,receipt=receipt)
        account['charged_seconds']+=elapsed;account['reserved_seconds']-=90
        update_account(account);record(dict(event='ATTEMPT_CLOSED',**entry))
        print(json.dumps({'job':job['job_id'],'state':entry['state'],'charged_seconds':elapsed}),flush=True)
    account=read(B_OUT/'linked_budget_ledger.json')
    next(b for b in account['batches'] if b['batch_id']==batch_id)['state']='CLOSED'
    update_account(account);record({'event':'BATCH_CLOSED','batch_id':batch_id})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','run','_worker']);p.add_argument('batch',nargs='?');p.add_argument('job',nargs='?');a=p.parse_args()
    if a.command=='start': start()
    elif a.command=='run': run_batch(a.batch)
    else:
        spec=read(B_OUT/'batches'/a.batch/'batch_spec.json');validate(spec)
        job=next(j for j in spec['jobs'] if j['job_id']==a.job)
        account=read(B_OUT/'linked_budget_ledger.json')
        active=next(x for x in account['attempts'] if x['job_id']==a.job)
        if active['state']!='RUNNING_RESERVED': raise PermissionError('NO_ACTIVE_B_FIT_RESERVATION')
        execute(job,spec,ROOT/active['directory'])
