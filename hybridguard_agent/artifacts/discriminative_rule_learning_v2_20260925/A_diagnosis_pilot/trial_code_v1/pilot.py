"""Bounded V2-A entry: prepare once, test, then at most six immutable attempts."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from hybridguard_agent.research.rule_learning.contracts import contract
from hybridguard_agent.research.rule_learning.evaluation import evaluate
from .common import *
from .adapter import TrainAccess, raw_projection, fit_authorized, save_model, load_model, predict_current


def check_settings():
    dev = read(DOC / 'DEFAULT_DEV_CONTRACT.json')['initial_learning_settings']
    search, grammar = contract('learning_search_space'), contract('candidate_grammar')
    expected = {
        'lambda': search['objective']['lambda'], 'alpha': next(p['alpha'] for p in search['operating_points'] if p['id'] == 'OP05'),
        'min_train_decision_coverage': search['constraints']['min_decision_coverage'],
        'coverage_strata': search['constraints']['coverage_strata'], 'max_clauses': search['constraints']['max_clauses'],
        'max_literals': search['constraints']['max_literals'], 'max_complexity': search['constraints']['max_complexity_primary'],
        'max_clause_length': search['constraints']['max_clause_length_primary'],
        'max_clauses_per_family': grammar['composition']['max_clauses_per_family'],
        'minimum_available_complete_triplets': search['support']['minimum_available_triplets'],
        'minimum_true_attack_triplets': search['support']['minimum_true_attack_triplets_per_literal_or_clause'],
        'minimum_support_bundles': search['support']['minimum_support_bundles'],
        'minimum_support_environments': search['support']['minimum_support_environments'],
        'numeric_quantiles': grammar['new_encoder']['number']['threshold_quantiles'],
        'numeric_interpolation': grammar['new_encoder']['number']['quantile_interpolation'],
        'seed': search['parameter_search']['seed'], 'greedy_max_additions': search['algorithms']['GREEDY_OR']['max_additions'],
        'backward_pruning_passes': search['algorithms']['GREEDY_OR']['backward_pruning_passes'],
        'fit_time_limit_seconds': search['algorithms']['GREEDY_OR']['time_limit_seconds_per_fit'],
        'training_execution_failures_max': search['constraints']['train_execution_failures_max']}
    if any(dev[k] != v for k, v in expected.items()):
        raise ValueError('V2_DEFAULT_AND_V1_SETTINGS_DIFFER')
    return expected


def code_version():
    directory = Path(__file__).parent
    return {relative(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob('*.py'))}


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    settings = check_settings()
    baseline = budget_base()
    fs, defs = folds(), definitions()
    all_meta = {r['opaque_id']: r for r in lines(V1 / 'R02_matrix/evaluation_index.jsonl')}
    jobs = []
    test_ids = []
    for f in fs:
        train, test = f['train'], f['outer_test']
        for field in ('bundle_id', 'environment_group_id'):
            if {all_meta[i][field] for i in train} & {all_meta[i][field] for i in test}:
                raise ValueError('FOLD_GROUP_BOUNDARY_OVERLAP:' + field)
        if any(all_meta[i]['supervised_label'] is None for i in train + test):
            raise ValueError('DESCRIPTIVE_FOLD_MEMBER')
        test_ids.extend(test)
    if len(test_ids) != 162 or len(set(test_ids)) != 162:
        raise ValueError('EXPECTED_162_DISTINCT_STAGES')
    for representation in ('S_FLAT', 'J0'):
        for f in fs:
            jobs.append({'job_id': 'V2-A__' + representation + '__' + f['fold_id'],
                         'representation': representation, 'method': 'GREEDY_OR', 'operating_point': 'OP05',
                         'split_id': 'LOEO-v1', 'fold_id': f['fold_id'], 'target': f['target'],
                         'train_ids': f['train'], 'outer_test_ids': f['outer_test'],
                         'descriptive_fit': False, 'attempt': 1})
    authority = {'authorization_id': 'USER_V2_A_20260925', 'source': 'Explicit user message in this task on 2026-09-25',
                 'phase': 'V2-A', 'status': 'AUTHORIZED_FOR_THIS_BATCH_ONLY',
                 'fit_specs': ['S_FLAT/GREEDY_OR/OP05', 'J0/GREEDY_OR/OP05'],
                 'max_fits_including_retries': 6, 'max_charged_seconds': 600,
                 'stop_after_batch': True, 'automatic_phase_advance': False,
                 'V1_dispatcher_grant': False, 'new_predicates_or_collection': False,
                 'full_development_refit_or_confirmation_access': False}
    write(OUT / 'AUTHORIZATION.json', authority)
    spec = {'schema_version': 'v2-a-batch-spec-v1', 'created_at': stamp(), 'phase': 'V2-A',
            'study_id': 'discriminative-rule-learning-v2-20260925', 'evaluation_role': ROLE,
            'authorization': authority, 'code_version': code_version(), 'adapter_version': VERSION,
            'basis_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'candidate_version': 'V1_R04_R1_EXACT_ALLOWLISTS_PLUS_CANONICAL_C0_NO_NEW_PREDICATES',
            'source_index': relative(FROZEN / 'DATA_INDEX.json'), 'definitions_ref': relative(FROZEN / 'data/definitions.json'),
            'single_surface_allowlists': defs['single_surface_allowlists'], 'settings': settings,
            'search_space': contract('learning_search_space'), 'grammar': contract('candidate_grammar'),
            'base_budget': baseline, 'max_actual_fits': min(6, baseline['remaining_fits']),
            'max_charged_seconds': min(600, baseline['remaining_seconds']),
            'job_wall_cap_seconds': 90, 'jobs': jobs, 'unique_supervised_stages': 162,
            'descriptive_stages_excluded_from_fit_and_metrics': 100,
            'expected_prediction_units': 324, 'failure_rows_keep_expected_ids': True,
            'automatic_retry': False, 'empty_or_low_detection_is_valid_result': True,
            'billing_scope': 'Worker wall time includes read, encoder, fit, freeze, prediction and evaluation; crashes reserve cap. Read-only diagnosis/report and synthetic tests are not real trial execution.'}
    write(OUT / 'batch_spec.json', spec)
    write(OUT / 'linked_budget_ledger.json', {'schema_version': 'v2-linked-research-budget-v1',
          'base': baseline, 'batch_spec_ref': relative(OUT / 'batch_spec.json'),
          'actual_fits': 0, 'charged_seconds': 0.0, 'attempts': [], 'state': 'READY'})
    print(json.dumps({'prepared_jobs': len(jobs), 'base_budget': baseline}, ensure_ascii=False))


def failed_rows(job, reason):
    return [{'opaque_id': i, 'model_id': None, 'model_unit_id': job['job_id'], 'fold_id': job['fold_id'],
             'representation': job['representation'], 'decision': 'FAILED', 'failure_reason': reason,
             'selected_atoms_available': 0, 'selected_atoms_expected': None,
             'clauses_defined': 0, 'clauses_expected': None} for i in job['outer_test_ids']]


def execute(job, spec, dest):
    events = []
    def event(name, **data):
        events.append({'event': name, 'utc': stamp(), **data})
    index = read(FROZEN / 'DATA_INDEX.json')
    raw, meta = {}, {}
    for i in job['train_ids']:
        raw[i] = read(FROZEN / index[i]['features'])['features']
        meta[i] = read(FROZEN / index[i]['evaluation'])
    event('EXACT_TRAIN_OPENED', ids=job['train_ids'], evaluation_members_opened=0)
    defs = definitions()
    access = TrainAccess(job, raw_projection(raw, defs, job['representation']), meta)
    binding = {'study_version': spec['study_id'], 'protocol_digest': digest(spec),
               'candidate_version': spec['candidate_version'], 'fold_id': job['fold_id'], 'split_id': 'LOEO-v1',
               'operating_point': 'OP05', 'input_manifest_ref': spec['source_index'],
               'data_origin': 'V1_EXPOSED_DEVELOPMENT', 'evaluation_role': ROLE,
               'authorization_id': spec['authorization']['authorization_id'],
               'model_unit_id': job['job_id'], 'representation': job['representation']}
    model, training = fit_authorized(access, defs, binding)
    write(dest / 'training.json', training)
    save_model(model, dest / 'model.json')
    model = load_model(dest / 'model.json')
    if model.fit['train_ids'] != job['train_ids']:
        raise ValueError('MODEL_TRAIN_MEMBER_MISMATCH')
    if model.encoder and (model.encoder['train_ids'] != job['train_ids'] or model.encoder['fold_id'] != job['fold_id']):
        raise ValueError('ENCODER_TRAIN_BINDING_MISMATCH')
    event('MODEL_ENCODER_SAVED_LOADED_FROZEN', model_id=model.model_id)
    predictions = []
    for i in job['outer_test_ids']:
        current = read(FROZEN / index[i]['features'])['features']
        event('OPEN_OWN_EVALUATION_FEATURE', opaque_id=i)
        predictions.append(predict_current(model, i, raw_projection({i: current}, defs, job['representation'])[i]))
    write_lines(dest / 'predictions.jsonl', predictions)
    if [r['opaque_id'] for r in predictions] != job['outer_test_ids']:
        raise ValueError('PREDICTION_CLOSURE_MEMBER_MISMATCH')
    event('PREDICTIONS_SAVED_CLOSED', n=len(predictions))
    evaluation = {i: read(FROZEN / index[i]['evaluation']) for i in job['outer_test_ids']}
    event('EVALUATION_SIDECAR_JOIN_AFTER_CLOSURE', ids=job['outer_test_ids'])
    write(dest / 'metrics.json', evaluate(job['outer_test_ids'], lines(dest / 'predictions.jsonl'), evaluation,
                                        evaluation_role=ROLE))
    write(dest / 'access_log.json', events)
    receipt = {'state': model.status, 'model_id': model.model_id, 'fit_status': model.fit['status'],
               'predictions': len(predictions), 'actual_fit_invocations': 1, 'ended_at': stamp()}
    write(dest / 'receipt.json', receipt)
    return receipt


def validate_spec(spec):
    if spec['phase'] != 'V2-A' or spec['authorization'] != read(OUT / 'AUTHORIZATION.json'):
        raise PermissionError('V2_A_BATCH_AUTHORIZATION_REQUIRED')
    if spec['authorization']['authorization_id'] != 'USER_V2_A_20260925':
        raise PermissionError('WRONG_BATCH_AUTHORIZATION')
    if spec['code_version'] != code_version() or spec['settings'] != check_settings():
        raise PermissionError('CODE_OR_SETTINGS_CHANGED_REQUIRE_RECORDED_NEW_ATTEMPT')
    if spec['single_surface_allowlists'] != definitions()['single_surface_allowlists']:
        raise ValueError('CANDIDATE_ALLOWLIST_CHANGED')
    actual = {(j['representation'], j['fold_id'], j['method'], j['operating_point']) for j in spec['jobs']}
    expected = {(r, f['fold_id'], 'GREEDY_OR', 'OP05') for r in ('S_FLAT', 'J0') for f in folds()}
    if actual != expected or len(spec['jobs']) != 6:
        raise PermissionError('ONLY_SIX_SPECIFIED_V2_A_JOBS')
    for j in spec['jobs']:
        f = next(f for f in folds() if f['fold_id'] == j['fold_id'])
        if j['train_ids'] != f['train'] or j['outer_test_ids'] != f['outer_test']:
            raise PermissionError('EXACT_INHERITED_FOLD_REQUIRED')


def update_ledger(state):
    p = OUT / 'linked_budget_ledger.json'
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, p)


def run():
    spec = read(OUT / 'batch_spec.json')
    validate_spec(spec)
    if read(OUT / 'synthetic_test_results.json')['status'] != 'PASS':
        raise PermissionError('SYNTHETIC_TESTS_REQUIRED_FIRST')
    if not (OUT / 'diagnosis.csv').exists() or not (OUT / 'posthoc_ensemble_diagnostic.jsonl').exists():
        raise PermissionError('SAVED_DIAGNOSIS_REQUIRED_BEFORE_REAL_FITS')
    lock = OUT / '.run.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        state = read(OUT / 'linked_budget_ledger.json')
        if state['attempts']:
            raise PermissionError('NO_AUTOMATIC_RERUN_OR_OVERWRITE_OF_ATTEMPTS')
        for job in spec['jobs']:
            fresh = budget_base()
            remaining = min(spec['max_charged_seconds'] - state['charged_seconds'], fresh['remaining_seconds'] - state['charged_seconds'])
            dest = OUT / 'trials' / (job['job_id'] + '__attempt01')
            dest.mkdir(parents=True, exist_ok=False)
            cap = min(spec['job_wall_cap_seconds'], remaining)
            if state['actual_fits'] >= min(spec['max_actual_fits'], fresh['remaining_fits']) or cap <= 0:
                write_lines(dest / 'predictions.jsonl', failed_rows(job, 'NOT_RUN_BUDGET_EXHAUSTED'))
                write(dest / 'receipt.json', {'state': 'NOT_RUN_BUDGET_EXHAUSTED', 'actual_fit_invocations': 0})
                continue
            attempt = {'job_id': job['job_id'], 'attempt': 1, 'started_at': stamp(), 'state': 'RUNNING_RESERVED',
                       'reserved_seconds': cap, 'artifact_directory': relative(dest), 'code_version': spec['code_version'],
                       'train_ids': job['train_ids'], 'evaluation_ids': job['outer_test_ids'], 'seed': spec['settings']['seed'],
                       'representation': job['representation'], 'fold_id': job['fold_id'], 'method': 'GREEDY_OR', 'operating_point': 'OP05'}
            state['actual_fits'] += 1
            state['charged_seconds'] += cap
            state['attempts'].append(attempt)
            update_ledger(state)
            with (OUT / 'trials.jsonl').open('a') as stream:
                stream.write(json.dumps(attempt, ensure_ascii=False) + '\n')
            write(dest / 'attempt_spec.json', {'job': job, 'batch_spec_ref': relative(OUT / 'batch_spec.json'),
                  'parent_pid': os.getpid(), 'reserved_seconds': cap, 'authorization_id': 'USER_V2_A_20260925'})
            start = time.monotonic()
            try:
                proc = subprocess.run([sys.executable, '-B', '-m', __package__ + '.pilot', '_worker', job['job_id']],
                                      cwd=ROOT, capture_output=True, text=True, timeout=cap)
                (dest / 'stdout.txt').write_text(proc.stdout)
                (dest / 'stderr.txt').write_text(proc.stderr)
                if proc.returncode:
                    raise RuntimeError('WORKER_EXIT_' + str(proc.returncode))
                receipt = read(dest / 'receipt.json')
            except (subprocess.TimeoutExpired, RuntimeError) as exc:
                receipt = {'state': 'FAILED', 'failure_reason': str(exc), 'actual_fit_invocations': 1}
                write(dest / 'worker_failure.json', receipt)
                if not (dest / 'predictions.jsonl').exists():
                    write_lines(dest / 'predictions.jsonl', failed_rows(job, str(exc)))
            elapsed = time.monotonic() - start
            attempt.update(state=receipt['state'], ended_at=stamp(), elapsed_seconds=elapsed, receipt=receipt)
            state['charged_seconds'] += elapsed - cap
            state.update(cumulative_fit_jobs=fresh['used_fit_jobs'] + state['actual_fits'],
                         cumulative_charged_seconds=fresh['charged_seconds'] + state['charged_seconds'])
            update_ledger(state)
            with (OUT / 'trials.jsonl').open('a') as stream:
                stream.write(json.dumps(attempt, ensure_ascii=False) + '\n')
            print(json.dumps({'job': job['job_id'], **receipt, 'charged_seconds': elapsed}), flush=True)
        state['state'] = 'CLOSED_STOP_FOR_USER_REVIEW'
        update_ledger(state)
    finally:
        os.close(fd)
        lock.unlink()


def worker(job_id):
    spec = read(OUT / 'batch_spec.json')
    validate_spec(spec)
    job = next(j for j in spec['jobs'] if j['job_id'] == job_id)
    dest = OUT / 'trials' / (job_id + '__attempt01')
    ticket = read(dest / 'attempt_spec.json')
    account = read(OUT / 'linked_budget_ledger.json')
    if ticket['parent_pid'] != os.getppid() or ticket['job'] != job or not any(
            a['job_id'] == job_id and a['state'] == 'RUNNING_RESERVED' for a in account['attempts']):
        raise PermissionError('LIVE_V2_RESERVATION_REQUIRED')
    execute(job, spec, dest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'run', '_worker'))
    parser.add_argument('job_id', nargs='?')
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, '_worker': lambda: worker(args.job_id)}[args.command]()
