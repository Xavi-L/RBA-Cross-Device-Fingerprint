#!/usr/bin/env python3
"""Authorized R_KEEP four-view LOEO retraining from saved sparse initializers."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
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
FROZEN = 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1'
V2B = 'hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/B_development'
INITIAL = 'deliverables/rule_semantics_retraining'
PRIOR = 'deliverables/rule_semantics_candidate_evaluation'
BUDGET = INITIAL + '/EXECUTION.json'
GROUPS = ('BASE', 'LANG_ADD', 'LANG_REPLACE', 'WD_REPLACE')
CANDIDATES = {'RSR-LANG-FIRST-v1': 'default', 'RSR-WEBDRIVER-STATE-v1': 'legacy_projection_v1'}
ROLE = 'EXPOSED_RETROSPECTIVE_DEVELOPMENT'


def stamp(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(Path(path).read_text())
def lines(path): return [json.loads(line) for line in Path(path).read_text().splitlines() if line]
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
def write_lines(path, rows):
    with Path(path).open('x', encoding='utf-8') as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
def historical(fold):
    return f'{V2B}/trials/B01_retention__W0__R_KEEP_V1__{fold}__attempt01'


def validate_candidate_cache(rows, ids):
    expected = {(sid, cid, mode) for sid in ids for cid, mode in CANDIDATES.items()}
    keys = [(r['opaque_id'], r['candidate_id'], r['mode']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('CANDIDATE_CACHE_SCOPE_CONFLICT')
    from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SemanticCell
    for row in rows:
        # Saved raw encoding, not a state synthesized from expected labels.
        cell = SemanticCell(**row['semantic_cell'])
        if (cell.state != row['state'] or cell.candidate_id != row['candidate_id']
                or cell.version != '1.0.0' or not row['candidate_invoked']):
            raise ValueError('CANDIDATE_CACHE_CELL_IDENTITY_CONFLICT')


def candidate_offsets(path):
    offsets = {}
    with Path(path).open('rb') as stream:
        while True:
            offset = stream.tell(); line = stream.readline()
            if not line: break
            row = json.loads(line)
            offsets.setdefault(row['opaque_id'], []).append({'offset':offset,'length':len(line)})
    return offsets


def candidate_subset(path, ids, offsets):
    if len(ids) != len(set(ids)): raise ValueError('DUPLICATE_REQUESTED_CANDIDATE_ID')
    result = {}
    with Path(path).open('rb') as stream:
        for sid in ids:
            result[sid] = {}
            for loc in offsets[sid]:
                stream.seek(loc['offset']); row = json.loads(stream.read(loc['length']))
                if row['opaque_id'] != sid or row['candidate_id'] in result[sid]:
                    raise ValueError('CANDIDATE_OFFSET_IDENTITY_OR_DUPLICATE')
                result[sid][row['candidate_id']] = row['semantic_cell']
            if set(result[sid]) != set(CANDIDATES):
                raise ValueError('EXPECTED_SAVED_CANDIDATE_MISSING')
    return result


def prepare(directory):
    if (directory/'CONTRACT.json').exists(): raise FileExistsError('CONTRACT_ALREADY_REGISTERED')
    tests = read(directory/'TEST_RESULTS.json')
    if tests['status'] != 'PASS' or tests['exit_code'] != 0: raise ValueError('TESTS_NOT_PASSED')
    prior = read(ROOT/PRIOR/'EVALUATION_CONTRACT.json')
    ids = prior['sample_ids']
    authority = read(ROOT/prior['authority_ref'])['supervised_ids']
    if ids != authority or len(ids) != 162 or len(set(ids)) != 162: raise ValueError('FIXED_162_SCOPE_CONFLICT')
    validate_candidate_cache(lines(ROOT/PRIOR/'CANDIDATE_RESULTS.jsonl'), ids)
    split_ref = FROZEN+'/SPLIT_MANIFEST.json'
    folds = [f for f in read(ROOT/split_ref)['folds'] if f['split_id'] == 'LOEO-v1']
    if [f['fold_id'] for f in folds] != ['LOEO-v1-01', 'LOEO-v1-02', 'LOEO-v1-03']:
        raise ValueError('ORIGINAL_THREE_FOLDS_REQUIRED')
    test_ids = []
    for f in folds:
        if set(f['train']) & set(f['outer_test']) or set(f['train']) | set(f['outer_test']) != set(ids):
            raise ValueError('FOLD_SCOPE_CONFLICT')
        test_ids += f['outer_test']
    if len(test_ids) != 162 or set(test_ids) != set(ids): raise ValueError('OOF_PARTITION_CONFLICT')
    budget = read(ROOT/BUDGET)
    if not budget['execution_complete'] or budget['stop_reason'] or budget['remaining_research_fits'] < 12 or budget['remaining_research_seconds'] < 1080:
        raise ValueError('PRIOR_BUDGET_NOT_SETTLED_OR_INSUFFICIENT')
    jobs = [{'job_id': group+'__'+f['fold_id'], 'group_id':group, 'fold_id':f['fold_id'],
             'train_ids':f['train'], 'outer_test_ids':f['outer_test'], 'held_out_environment':f['target'],
             'initial_model_ref':f'{INITIAL}/trials/{group}__{f["fold_id"]}/model.json',
             'initial_training_ref':f'{INITIAL}/trials/{group}__{f["fold_id"]}/training.json',
             'historical_baseline_ref':historical(f['fold_id']), 'attempt':1}
            for group in GROUPS for f in folds]
    initial_contract=read(ROOT/INITIAL/'CONTRACT.json')
    if (initial_contract['sample_ids'] != ids or initial_contract['selector'] != 'GREEDY_OR'
            or initial_contract['operating_point'] != 'OP05' or len(initial_contract['jobs']) != 12):
        raise ValueError('INITIAL_EXPERIMENT_SCOPE_CONFLICT')
    for job in jobs:
        old_job=next(j for j in initial_contract['jobs'] if j['job_id']==job['job_id'])
        if any(old_job[k]!=job[k] for k in ('train_ids','outer_test_ids','group_id','fold_id')):
            raise ValueError('INITIAL_JOB_SCOPE_CONFLICT')
        receipt=read((ROOT/job['initial_model_ref']).with_name('receipt.json'))
        if not receipt['predictions_closed'] or receipt['outcome'] not in ('FITTED','EMPTY_MODEL'):
            raise ValueError('INITIAL_JOB_NOT_SETTLED')
    paths = [str(Path(__file__).resolve().relative_to(ROOT)),
        'hybridguard_agent/research/rule_semantics_rkeep_retraining.py',
        'hybridguard_agent/research/rule_semantics_retraining.py',
        'hybridguard_agent/research/rule_semantics_revision_v1/contracts.py',
        'hybridguard_agent/research/rule_learning_v2/adapter.py',
        'hybridguard_agent/research/rule_learning_v2/b_engine.py',
        'hybridguard_agent/research/rule_learning_v2/retention.py',
        *['hybridguard_agent/research/rule_learning/'+n+'.py' for n in
          ('contracts','models','selector','predictor','baselines','fold_data','evaluation')],
        *['hybridguard_agent/config/rule_learning_v1_20260924/'+n+'.json' for n in ('learning_search_space','candidate_grammar')],
        FROZEN+'/DATA_INDEX.json', FROZEN+'/data/definitions.json',split_ref,
        PRIOR+'/EVALUATION_CONTRACT.json',PRIOR+'/CANDIDATE_RESULTS.jsonl',BUDGET,
        INITIAL+'/CONTRACT.json',V2B+'/B_CONTRACT.json',V2B+'/signal_groups_v1.json',
        str((directory/'TEST_RESULTS.json').relative_to(ROOT))]
    for job in jobs:
        paths += [job['initial_model_ref'],job['initial_training_ref']]
    for f in folds:
        paths += [historical(f['fold_id'])+'/'+name for name in ('model.json','training.json','predictions.jsonl')]
    identities = [{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in paths]
    contract = {'schema_version':'rsr-rkeep-retraining-contract-v1', 'registered_at':stamp(),
        'starting_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'authorization':'User explicitly requested retesting semantic candidate improvements on R_KEEP in this chat on 2026-09-29; four original groups and three original folds, twelve retention fits from saved matching sparse initializers.',
        'study_version':'rule-semantics-rkeep-retraining-v1','phase':'RSR_RKEEP_RETRAINING','evaluation_role':ROLE,
        'sample_ids':ids,'source_index':FROZEN+'/DATA_INDEX.json','definitions_ref':FROZEN+'/data/definitions.json',
        'split_manifest_ref':split_ref,'candidate_cache_ref':PRIOR+'/CANDIDATE_RESULTS.jsonl',
        'candidate_cache_offsets':candidate_offsets(ROOT/PRIOR/'CANDIDATE_RESULTS.jsonl'),
        'candidate_versions':{k:{'version':'1.0.0','mode':v} for k,v in CANDIDATES.items()},
        'groups':{'BASE':'Unchanged W0 app_web67 candidates and saved sparse initializer, refit R_KEEP_V1',
            'LANG_ADD':'W0 plus fixed language-first cell; old length family retained',
            'LANG_REPLACE':'Remove complete unfitted languages length family, add fixed language-first cell',
            'WD_REPLACE':'Remove old webdriver EQ:True atom, add fixed legacy reported-state cell'},
        'family_policy':'Reuse original field family; both frozen grammar polarities; no duplicated evidence or forced inclusion.',
        'jobs':jobs,'selector':'R_KEEP_V1','operating_point':'OP05',
        'initialization':'Reuse each group/fold saved GREEDY model and frozen encoder. No new sparse fit or threshold fitting. Verify exact pool, support, train IDs and training score before retain.',
        'retention':{'version':'R_KEEP_V1','signal_group_version':'SEMANTIC_SIGNAL_GROUPS_V1',
            'new_atom_groups':{'RSR-LANG-FIRST-v1':'language_preferences','RSR-WEBDRIVER-STATE-v1':'automation_flag'},
            'objective':'Positive additional weighted (semantic signal group, train attack) coverage; preserve initial attack detection and original whole-set constraints.',
            'order':['delta_macro_tpr descending','delta_D descending','clean_alarms ascending','complexity ascending','clause_id ascending'],
            'operations':'Add only; no removal, replacement, or sparse pruning of the saved initialization.',
            'historical_code_note':'Current retention math and ordering match B01. Existing later timeout-status fix reports TIME_LIMIT_FEASIBLE or FAILED_FIT instead of an ordinary completion; no new change this round.'},
        'search_space':read(ROOT/'hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json'),
        'grammar':read(ROOT/'hybridguard_agent/config/rule_learning_v1_20260924/candidate_grammar.json'),
        'exposure':'Already exposed historical development material. Cached candidate states are fixed and label-independent; not blinded or independent confirmation.',
        'execution_order':'BASE three retention fits, verify saved B01 W0 R_KEEP equality, then nine variant retention fits. Each model saved/reloaded before held-out features; all predictions closed before evaluation metadata join.',
        'baseline_comparison':'Same train IDs, fixed/numeric encoder content, complete candidate manifest/support projection, selected clauses, signal groups, retention trace/D, train score, held-out logical states/decisions and coverage counts. Ignore study identity/time/version wrapper differences.',
        'metrics':'Original full-denominator evaluation and config-equal/environment-equal macro; explicit OOF only. Preserve abstentions, EMPTY_MODEL and failures.',
        'failure_policy':'Count every invoked fit and preserve errors; no automatic retries or budget/semantic relaxation. Baseline mismatch stops remaining groups.',
        'budget':{'prior_ledger_ref':BUDGET,'base_fit_jobs':budget['cumulative_fit_jobs'],
            'base_charged_seconds':budget['cumulative_charged_seconds'], 'max_new_fits':12,'new_sparse_fit_calls':0,
            'max_worker_seconds':90,'max_stage_seconds':1080,'global_max_fits':200,'global_max_seconds':21600,
            'carryover_authorization':'New explicit R_KEEP authorization uses capacity after the preceding twelve GREEDY fits; does not reopen C or reuse its unused retry quota.'},
        'prohibited':['new GREEDY fit','new collection','new candidate calls','raw webdriver mode','LOCO','full-development final fit','independent confirmation','old artifact mutation','commit','push'],
        'file_identities':identities}
    write(directory/'CONTRACT.json',contract)
    return {'status':'REGISTERED_BEFORE_FITS','jobs':len(jobs),'contract_sha256':digest(contract)}


def validate_contract(contract):
    if contract['study_version'] != 'rule-semantics-rkeep-retraining-v1' or len(contract['jobs']) != 12:
        raise ValueError('EXPERIMENT_IDENTITY_CONFLICT')
    for entry in contract['file_identities']:
        if hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('REGISTERED_DEPENDENCY_CHANGED:'+entry['path'])


def worker(directory, job_id):
    from hybridguard_agent.research import rule_semantics_rkeep_retraining as engine
    from hybridguard_agent.research import rule_semantics_retraining as sparse_engine
    contract = read(directory/'CONTRACT.json')
    job = next(j for j in contract['jobs'] if j['job_id']==job_id)
    dest=directory/'trials'/job_id
    dest.mkdir(parents=True, exist_ok=False)
    started=time.monotonic();events=[];fit_calls=0;retention_calls=0;pred_calls=0;predictions=[];error=None
    def event(name,**kwargs): events.append({'event':name,'utc':stamp(),**kwargs})
    binding={'study_version':contract['study_version'],'phase':contract['phase'],'group_id':job['group_id'],
        'method_id':'R_KEEP_V1','operating_point':'OP05','fold_id':job['fold_id'],'split_id':'LOEO-v1',
        'evaluation_role':ROLE,'protocol_digest':digest(contract),'candidate_version':'RSR_FIXED_CACHE_1.0.0',
        'model_unit_id':job_id,'input_manifest_ref':contract['source_index']}
    try:
        index=read(ROOT/contract['source_index']);base=(ROOT/contract['source_index']).parent
        raw={sid:read(base/index[sid]['features'])['features'] for sid in job['train_ids']}
        meta={sid:read(base/index[sid]['evaluation']) for sid in job['train_ids']}
        cells=candidate_subset(ROOT/contract['candidate_cache_ref'],job['train_ids'],contract['candidate_cache_offsets']) if job['group_id']!='BASE' else None
        initial_model=sparse_engine.load_model(ROOT/job['initial_model_ref'])
        initial_training=read(ROOT/job['initial_training_ref'])
        event('MATCHING_SPARSE_INITIALIZER_LOADED',model_id=initial_model.model_id,ref=job['initial_model_ref'])
        event('TRAIN_ONLY_INPUTS_OPENED',train_ids=job['train_ids'],heldout_features_opened=0)
        write(dest/'FIT_STARTED.json',{'utc':stamp(),'job_id':job_id,'fit_count':1,'attempt':1,'train_ids':job['train_ids']})
        fit_calls=1
        retention_calls=None  # Unknown if the interface aborts before returning its audit.
        model,training=engine.fit_group(job,raw,meta,read(ROOT/contract['definitions_ref']),
            group=job['group_id'],binding=binding,candidate_rows=cells,
            initial_model=initial_model,initial_training=initial_training)
        retention_calls=model.fit['actual_retention_invocations']
        write(dest/'training.json',training)
        engine.save_model(model,dest/'model.json')
        restored=engine.load_model(dest/'model.json')
        if canonical(model.to_dict())!=canonical(restored.to_dict()): raise ValueError('MODEL_SAVE_LOAD_MISMATCH')
        if restored.fit['train_ids']!=job['train_ids']: raise ValueError('MODEL_TRAIN_SCOPE_CONFLICT')
        event('MODEL_SAVED_RELOADED_FROZEN',model_id=restored.model_id,roundtrip_equal=True)
        test_cells=candidate_subset(ROOT/contract['candidate_cache_ref'],job['outer_test_ids'],contract['candidate_cache_offsets']) if job['group_id']!='BASE' else None
        with (dest/'PREDICTION_CALLS.jsonl').open('x') as calls, (dest/'predictions.jsonl').open('x') as output:
            for sid in job['outer_test_ids']:
                row=read(base/index[sid]['features'])['features']
                cell=test_cells[sid] if test_cells is not None else None
                calls.write(json.dumps({'opaque_id':sid,'event':'PREDICT_INVOKED'})+'\n');calls.flush()
                pred_calls+=1
                result=engine.predict_current(restored,sid,row,candidate_cells=cell)
                predictions.append(result)
                output.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');output.flush()
        event('PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN',ids=job['outer_test_ids'],count=len(predictions))
        outcome=restored.status
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        write(dest/'ERROR.json',error);outcome='FAILED'
        completed={r['opaque_id']:r for r in predictions}
        missing=[{**binding,'opaque_id':sid,'decision':'FAILED','logical_state':None,
            'model_id':None,'failure_reason':'RUNNER:'+str(exc),'source_rows':[sid],
            'selected_atoms_available':0,'selected_atoms_expected':None,'clauses_defined':0,'clauses_expected':None}
            for sid in job['outer_test_ids'] if sid not in completed]
        with (dest/'predictions.jsonl').open('a') as output:
            for row in missing:output.write(json.dumps(row,ensure_ascii=False)+'\n')
        predictions=list(completed.values())+missing
    event('JOB_CLOSED',outcome=outcome)
    write(dest/'access_log.json',events)
    receipt={'job_id':job_id,'group_id':job['group_id'],'fold_id':job['fold_id'],'outcome':outcome,
        'actual_fit_invocations':fit_calls,'actual_retention_invocations':retention_calls,
        'actual_prediction_calls':pred_calls,'new_candidate_calls':0,'new_sparse_fit_calls':0,'threshold_fit_calls':0,
        'expected_predictions':len(job['outer_test_ids']),'saved_prediction_positions':len(predictions),
        'attempt':1,'additional_retries':0,'charged_seconds':time.monotonic()-started,
        'predictions_closed':True,'evaluation_metadata_joined':False,'error':error}
    write(dest/'receipt.json',receipt)
    return receipt


def settle_worker_failure(directory, job, exc, elapsed):
    """Preserve a killed worker's evidence and settle every expected position."""
    dest=directory/'trials'/job['job_id'];dest.mkdir(parents=True,exist_ok=True)
    present=[];bad=[]
    path=dest/'predictions.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            try:present.append(json.loads(line))
            except (ValueError,TypeError):bad.append(line)
        path.rename(dest/'predictions.interrupted.jsonl')
    completed={r['opaque_id']:r for r in present if r.get('opaque_id') in job['outer_test_ids']}
    rows=[completed.get(sid,{'opaque_id':sid,'decision':'FAILED','logical_state':None,'model_id':None,
        'fold_id':job['fold_id'],'group_id':job['group_id'],'failure_reason':'WORKER_INTERRUPTED:'+str(exc),
        'selected_atoms_available':0,'selected_atoms_expected':None,'clauses_defined':0,'clauses_expected':None,
        'source_rows':[sid]}) for sid in job['outer_test_ids']]
    write_lines(path,rows)
    count_path=dest/'PREDICTION_CALLS.jsonl'
    calls=0;bad_calls=[]
    if count_path.exists():
        for line in count_path.read_text().splitlines():
            try:json.loads(line);calls+=1
            except (ValueError,TypeError):bad_calls.append(line)
    retention_calls=0 if not (dest/'FIT_STARTED.json').exists() else None
    if (dest/'model.json').exists():
        try:retention_calls=read(dest/'model.json')['fit']['actual_retention_invocations']
        except (ValueError,TypeError,KeyError):pass
    receipt={'job_id':job['job_id'],'group_id':job['group_id'],'fold_id':job['fold_id'],'outcome':'FAILED',
        'actual_fit_invocations':int((dest/'FIT_STARTED.json').exists()),'actual_prediction_calls':calls if not bad_calls else None,
        'actual_retention_invocations':retention_calls,'new_sparse_fit_calls':0,'threshold_fit_calls':0,
        'known_prediction_invocation_records':calls,'prediction_call_count_exact':not bad_calls,'malformed_prediction_call_lines':bad_calls,
        'new_candidate_calls':0,'expected_predictions':len(rows),'saved_prediction_positions':len(rows),
        'attempt':1,'additional_retries':0,'charged_seconds':elapsed,'predictions_closed':True,
        'evaluation_metadata_joined':False,'error':{'type':type(exc).__name__,'message':str(exc)},
        'interrupted_evidence_preserved':True,'malformed_partial_line_count':len(bad)}
    if (dest/'receipt.json').exists():(dest/'receipt.json').rename(dest/'receipt.interrupted.json')
    write(dest/'receipt.json',receipt)
    return receipt


def baseline_check(directory,job):
    dest=directory/'trials'/job['job_id'];old=ROOT/job['historical_baseline_ref']
    new_model=read(dest/'model.json');old_model=read(old/'model.json')['engine_structure']
    training=read(dest/'training.json');original=read(old/'training.json')
    old_predictions={r['opaque_id']:r for r in lines(old/'predictions.jsonl')}
    new_predictions={r['opaque_id']:r for r in lines(dest/'predictions.jsonl')}
    def numeric(model):
        return {n:{k:v for k,v in x.items() if k!='surface'} for n,x in model['encoder']['numeric'].items()}
    manifest_keys=('clause_id','eligible','selected','signal_group','reasons','triplets',
        'true_attack_triplets','bundles','environments','phase_availability','singleton_train_clean_alarms')
    checks={'train_ids':new_model['fit']['train_ids']==old_model['fit']['train_ids'],
        'method':new_model['method_id']==old_model['method_id']=='R_KEEP_V1',
        'model_status':new_model['status']==old_model['status'],
        'fixed_atoms':set(new_model['encoder']['fixed_atoms'])==set(old_model['encoder']['fixed_atoms']),
        'numeric_encoder':numeric(new_model)==numeric(old_model),
        'selected_clauses':new_model['clauses']==old_model['clauses'],
        'candidate_support_and_selection':[{k:r.get(k) for k in manifest_keys} for r in training['candidate_manifest']]==[{k:r.get(k) for k in manifest_keys} for r in original['candidate_manifest']],
        'signal_groups':training['signal_groups']==original['signal_groups'],
        'initial_clauses':training['initial_clause_ids']==original['initial_clause_ids'],
        'retention_trace':training['trace']==original['trace'],
        'retention_outcome':all(new_model['fit'].get(k)==old_model['fit'].get(k) for k in ('D_initial','D_final','stop','status')),
        'training_result':new_model['fit']['training_result']==old_model['fit']['training_result'],
        'encoded_atom_ids':set(training['signal_groups'])==set(original['signal_groups']),
        'heldout_ids':set(new_predictions)==set(old_predictions)==set(job['outer_test_ids'])}
    keys=('logical_state','decision','selected_atoms_available','selected_atoms_expected','clauses_defined','clauses_expected')
    mismatches=[sid for sid in job['outer_test_ids'] if any(new_predictions[sid].get(k)!=old_predictions[sid].get(k) for k in keys)]
    checks['heldout_decisions_and_counts']=not mismatches
    return {'job_id':job['job_id'],'historical_ref':job['historical_baseline_ref'],
        'checks':checks,'mismatching_prediction_ids':mismatches,'passed':all(checks.values())}


def run(directory):
    contract=read(directory/'CONTRACT.json');validate_contract(contract)
    if (directory/'EXECUTION.json').exists() or (directory/'JOURNAL.jsonl').exists():
        raise FileExistsError('EXISTING_EXECUTION_NO_AUTOMATIC_RETRY_USE_ANALYZE')
    receipts=[];baselines=[];stopped=None;start=time.monotonic()
    with (directory/'JOURNAL.jsonl').open('x') as journal:
        for job in contract['jobs']:
            job_started=time.monotonic()
            event={'event':'JOB_RESERVED','job_id':job['job_id'],'max_fit_charge':1,'utc':stamp()}
            journal.write(json.dumps(event)+'\n');journal.flush()
            try:
                process=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker','--directory',str(directory),'--job',job['job_id']],
                    cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=contract['budget']['max_worker_seconds'])
                dest=directory/'trials'/job['job_id']
                for name,value in [('stdout.txt',process.stdout),('stderr.txt',process.stderr)]:
                    if value:
                        with (dest/name).open('x') as f:f.write(value)
                receipt=read(dest/'receipt.json');receipt['worker_wall_seconds']=time.monotonic()-job_started;receipts.append(receipt)
                journal.write(json.dumps({'event':'JOB_SETTLED','utc':stamp(),**receipt})+'\n');journal.flush()
                if process.returncode or receipt['outcome']=='FAILED':
                    stopped='JOB_FAILED:'+job['job_id'];break
                if job['group_id']=='BASE':
                    check=baseline_check(directory,job);baselines.append(check)
                    write(dest/'BASELINE_EQUIVALENCE.json',check)
                    if not check['passed']:
                        stopped='BASELINE_MISMATCH:'+job['job_id'];break
            except Exception as exc:
                stopped=type(exc).__name__+':'+str(exc)
                if not any(r['job_id']==job['job_id'] for r in receipts):
                    receipt=settle_worker_failure(directory,job,exc,time.monotonic()-job_started);receipts.append(receipt)
                    journal.write(json.dumps({'event':'JOB_SETTLED','utc':stamp(),**receipt})+'\n');journal.flush()
                write(directory/'RUN_ERROR.json',{'job_id':job['job_id'],'message':stopped,'traceback':traceback.format_exc()})
                break
    charged=sum(r.get('worker_wall_seconds',r['charged_seconds']) for r in receipts)
    actual=sum((directory/'trials'/j['job_id']/'FIT_STARTED.json').exists() for j in contract['jobs'])
    report={'schema_version':'rsr-rkeep-retraining-execution-v1','status':'RETRAINING_COMPLETE_PENDING_REVIEW' if len(receipts)==12 and not stopped else 'PARTIAL',
        'execution_complete':len(receipts)==12 and not stopped,'actual_fit_invocations':actual,
        'actual_retention_invocations':sum(r['actual_retention_invocations'] for r in receipts) if all(r['actual_retention_invocations'] is not None for r in receipts) else None,
        'actual_prediction_calls':sum(r['actual_prediction_calls'] for r in receipts) if all(r['actual_prediction_calls'] is not None for r in receipts) else None,
        'known_prediction_invocation_records':sum(r.get('known_prediction_invocation_records',r['actual_prediction_calls']) for r in receipts),
        'prediction_positions_saved':sum(r['saved_prediction_positions'] for r in receipts),
        'new_candidate_calls':0,'new_collection':0,'additional_retries':0,'new_sparse_fit_calls':0,'threshold_fit_calls':0,
        'independent_historical_records':162,'expected_prediction_positions':648,'baseline_equivalence':baselines,
        'jobs':receipts,'stop_reason':stopped,'charged_seconds':charged,'orchestration_elapsed_seconds':time.monotonic()-start,
        'prior_budget_ref':contract['budget']['prior_ledger_ref'],
        'cumulative_fit_jobs':contract['budget']['base_fit_jobs']+actual,
        'remaining_research_fits':contract['budget']['global_max_fits']-contract['budget']['base_fit_jobs']-actual,
        'cumulative_charged_seconds':contract['budget']['base_charged_seconds']+charged,
        'remaining_research_seconds':contract['budget']['global_max_seconds']-contract['budget']['base_charged_seconds']-charged,
        'contract_sha256':digest(contract)}
    write(directory/'EXECUTION.json',report)
    return report


def analyze(directory):
    from hybridguard_agent.research.rule_learning.evaluation import evaluate
    from hybridguard_agent.research.rule_learning.contracts import DECISIONS
    contract=read(directory/'CONTRACT.json');execution=read(directory/'EXECUTION.json')
    if not execution['execution_complete']: raise ValueError('PARTIAL_EXECUTION_REQUIRES_REVIEW')
    ids=contract['sample_ids'];index=read(ROOT/contract['source_index']);base=(ROOT/contract['source_index']).parent
    # Load every completed prediction stream before analysis-only label access.
    saved={j['job_id']:lines(directory/'trials'/j['job_id']/'predictions.jsonl') for j in contract['jobs']}
    for j in contract['jobs']:
        rows=saved[j['job_id']]
        if len(rows)!=len(j['outer_test_ids']) or {r['opaque_id'] for r in rows}!=set(j['outer_test_ids']):
            raise ValueError('EXPECTED_PREDICTION_SCOPE_CONFLICT')
        if not read(directory/'trials'/j['job_id']/'receipt.json')['predictions_closed']:
            raise ValueError('PREDICTIONS_NOT_CLOSED')
    meta={sid:read(base/index[sid]['evaluation']) for sid in ids}
    groups={};bygroup={};jobs_out=[]
    for group in GROUPS:
        rows=[r for j in contract['jobs'] if j['group_id']==group for r in saved[j['job_id']]]
        if len(rows)!=162 or len({r['opaque_id'] for r in rows})!=162: raise ValueError('OOF_SCOPE_CONFLICT')
        bygroup[group]={r['opaque_id']:r for r in rows}
        derived=[dict(r,executed_model_id=r['model_id'],executed_fold_id=r['fold_id'],model_id='OOF:'+group,
            fold_id='EXPLICIT_OOF_AGGREGATE') for r in rows]
        evaluation=evaluate(ids,derived,meta,evaluation_role=ROLE)
        groups[group]=evaluation
    for j in contract['jobs']:
        d=directory/'trials'/j['job_id'];model=read(d/'model.json');training=read(d/'training.json')
        ev=evaluate(j['outer_test_ids'],saved[j['job_id']],meta,evaluation_role=ROLE)
        jobs_out.append({'job_id':j['job_id'],'group_id':j['group_id'],'fold_id':j['fold_id'],
            'selected_clause_ids':model['fit']['training_result']['clause_ids'],'complexity':model['complexity'],
            'model_status':model['status'],'initial_clause_ids':training['initial_clause_ids'],
            'retention_trace':training['trace'],'D_initial':model['fit'].get('D_initial'),'D_final':model['fit'].get('D_final'),
            'registered_literals':len(training['candidate_manifest']),
            'eligible_literals':sum(x['eligible'] for x in training['candidate_manifest']),
            'train_score':model['fit']['training_result'],'test_metrics':ev['metrics'],
            'candidate_selection':[r for r in training['candidate_manifest'] if any(x in r['clause_id'] for x in ('RSR-','navigator_layer.languages','automation_surface_layer.webdriver'))],'decision_counts':ev['decision_counts']})
    comparisons={}
    for group in GROUPS[1:]:
        transitions={};changed=[]
        for sid in ids:
            old=bygroup['BASE'][sid];new=bygroup[group][sid];key=old['decision']+'->'+new['decision']
            transitions.setdefault(key,[]).append(sid)
            if old['decision']!=new['decision']:
                m=meta[sid];changed.append({'opaque_id':sid,'old_decision':old['decision'],'new_decision':new['decision'],
                    'phase':m['phase'],'config_id':m['config_id'],'environment_group_id':m['environment_group_id'],
                    'fold_id':new['fold_id'],'old_model_id':old['model_id'],'new_model_id':new['model_id']})
        metrics=('attack_tpr','MacroTPR_config_environment','clean_alarm_rate','decision_coverage','abstention_rate','failure_rate')
        comparisons[group]={'decision_cross_table':{k:len(v) for k,v in transitions.items()},
            'ids_by_transition':transitions,'changed_records':changed,
            'metric_delta_percentage_points':{k:100*(groups[group]['metrics'][k]['value']-groups['BASE']['metrics'][k]['value']) for k in metrics},
            'gained_attack_alert_ids':[r['opaque_id'] for r in changed if r['phase']=='attack' and r['new_decision']=='MANIPULATION_ALERT'],
            'lost_attack_alert_ids':[r['opaque_id'] for r in changed if r['phase']=='attack' and r['old_decision']=='MANIPULATION_ALERT']}
    return {'schema_version':'rsr-rkeep-retraining-summary-v1','status':execution['status'],'execution_complete':True,
        'evaluation_role':ROLE,'independent_historical_records':162,'prediction_positions':648,
        'groups':groups,'jobs':jobs_out,'comparisons_to_BASE':comparisons,'execution':execution,
        'limits':'Original exposed development LOEO, fixed R_KEEP_V1 from matched saved sparse initializers; no independent confirmation, full-development refit, new collection or population FPR claim.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run','worker','analyze'))
    p.add_argument('--directory',type=Path,default=HERE);p.add_argument('--job');p.add_argument('--output',type=Path)
    args=p.parse_args();args.directory=args.directory.resolve()
    if args.output and args.action!='analyze':p.error('--output is analyze only')
    if args.output and args.output.exists():p.error('REFUSE_EXISTING_ANALYSIS_OUTPUT')
    result=worker(args.directory,args.job) if args.action=='worker' else globals()[args.action](args.directory)
    if args.output:write(args.output,result)
    if args.action == 'run' or (args.action == 'analyze' and args.output):
        print(json.dumps({k:v for k,v in result.items() if k not in ('groups','jobs','comparisons_to_BASE')},ensure_ascii=False,indent=2))
    else:print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get('status')!='PARTIAL' else 1

if __name__=='__main__':raise SystemExit(main())
