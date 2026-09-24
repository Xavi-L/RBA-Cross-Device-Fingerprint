"""Audit/export closed R07_SINGLE_SURFACE_REFIT outputs and saved R05 comparison. Stdlib only; never fit/predict.

Uses saved per-job statistics/decisions plus frozen column metadata. It never
opens raw R02 feature records or imports any model, selector or transform code.
"""
import argparse
from collections import Counter, defaultdict
import copy
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path
import shutil
import sys
import time

KEYS = ('experiment_id', 'protocol_digest', 'split_id', 'method_id', 'operating_point',
        'source_condition', 'input_view', 'evaluation_track', 'data_origin')
PHASES = ('clean_pre', 'attack', 'clean_post')


def read(path): return json.loads(Path(path).read_text())
def lines(path): return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def csv_file(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def ratio(n, d):
    return {'numerator': n, 'denominator': d, 'value': n / d if d else None,
            'status': 'OK' if d else 'NOT_EVALUABLE'}


def allowed_sources(condition):
    return [s for s, bit in zip(('O_u', 'H', 'E'), condition.removeprefix('SRC-'), strict=True) if bit == '1']


def macro(ids, metadata, alerted):
    groups = defaultdict(lambda: defaultdict(list))
    for oid in ids:
        m = metadata[oid]
        if m['supervised_label'] == 1:
            groups[m['config_id']][m['environment_group_id']].append(oid)
    n = sum((sum((Fraction(sum(alerted(i) for i in rows), len(rows)) for rows in envs.values()), Fraction()) / len(envs)
             for envs in groups.values()), Fraction())
    return n, len(groups)


def expected_metrics(ids, rows, metadata):
    positive = [i for i in ids if metadata[i]['supervised_label'] == 1]
    negative = [i for i in ids if metadata[i]['supervised_label'] == 0]
    phases = {p: [i for i in ids if metadata[i]['phase'] == p] for p in PHASES}
    alerted = lambda part: sum(rows[i]['decision'] == 'MANIPULATION_ALERT' for i in part)
    decided = lambda part: sum(rows[i]['decision'] in ('MANIPULATION_ALERT', 'NO_ALERT') for i in part)
    metrics = {'attack_tpr': (alerted(positive), len(positive)), 'clean_alarm_rate': (alerted(negative), len(negative)),
        'pre_alarm_rate': (alerted(phases['clean_pre']), len(phases['clean_pre'])),
        'post_alarm_rate': (alerted(phases['clean_post']), len(phases['clean_post'])),
        'decided_clean_alarm_rate': (alerted(negative), decided(negative)), 'decision_coverage': (decided(ids), len(ids)),
        'abstention_rate': (sum(rows[i]['decision'] in ('EMPTY_MODEL', 'INSUFFICIENT_EVIDENCE') for i in ids), len(ids)),
        'failure_rate': (sum(rows[i]['decision'] == 'FAILED' for i in ids), len(ids))}
    for name, n, d in [('atom_coverage', 'selected_atoms_available', 'selected_atoms_expected'),
                      ('clause_coverage', 'clauses_defined', 'clauses_expected')]:
        metrics[name] = (None, None) if any(rows[i].get(d) is None for i in ids) else (
            sum(rows[i][n] for i in ids), sum(rows[i][d] for i in ids))
    metrics['MacroTPR_config_environment'] = macro(ids, metadata, lambda i: rows[i]['decision'] == 'MANIPULATION_ALERT')
    triads = defaultdict(dict)
    for oid in ids:
        m = metadata[oid]; triads[m['bundle_id'], m['triplet_id']][m['phase']] = rows[oid]['decision']
    complete = [t for t in triads.values() if set(t) == set(PHASES)]
    metrics['exact_FTF'] = (sum(tuple(t[p] for p in PHASES) == ('NO_ALERT', 'MANIPULATION_ALERT', 'NO_ALERT') for t in complete), len(complete))
    recovery = [t for t in triads.values() if t.get('attack') == 'MANIPULATION_ALERT' and 'clean_post' in t]
    metrics['conditional_recovery'] = (sum(t['clean_post'] == 'NO_ALERT' for t in recovery), len(recovery))
    return metrics


def check_metrics(saved, rows, metadata):
    ids = saved['attack_tpr']['source_rows']
    for name, (n, d) in expected_metrics(ids, rows, metadata).items():
        m = saved[name]
        assert m['source_rows'] == ids
        assert m['numerator'] == (float(n) if isinstance(n, Fraction) else n), (name, n, m)
        assert m['denominator'] == m['expected_denominator'] == d
        assert m['value'] == (float(n / d) if d else None)
        assert m['status'] == ('OK' if d else 'NOT_EVALUABLE')
    return 13


def export(out):
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    out = Path(out).resolve(); study = out.parent; dispatch = out / 'dispatch'
    prepared, process = read(out / 'RUN_PREPARED.json'), read(out / 'PROCESS_RESULT.json')
    freeze = Path(prepared['freeze_directory'])
    assert Path(sys.executable).resolve() == freeze / 'dependencies/python/bin/python3.12'
    assert process['returncode'] == 0 and process['attempt'] == 1 and process['automatic_retries'] == 0
    assert sha(freeze / 'FREEZE_MANIFEST.json') == prepared['freeze_manifest_digest']
    assert sha(freeze / 'RESOURCE_MANIFEST.json') == prepared['resource_manifest_digest']
    assert sha(out / 'R07_APPROVAL.json') == prepared['approval_digest']
    jobs = lines(out / 'expected_model_units.jsonl'); job_index = {j['model_unit_id']: j for j in jobs}
    receipts = read(dispatch / 'model_receipts.json'); predictions = lines(dispatch / 'predictions.jsonl')
    expected = {(r['model_unit_id'], r['opaque_id']) for r in lines(out / 'expected_prediction_units.jsonl')}
    assert len(jobs) == len(job_index) == len(receipts) == len(lines(out / 'expected_fit_jobs.jsonl')) == 9
    assert len(predictions) == len(expected) == 486 and {(r['model_unit_id'], r['opaque_id']) for r in predictions} == expected
    assert set(receipts) == set(job_index)
    closure = read(dispatch / 'PREDICTION_CLOSURE.json')
    assert closure['expected'] == closure['saved'] == 486 and closure['digest'] == digest(predictions)
    before, budget = read(out / 'BUDGET_BEFORE.json'), read(prepared['budget_ledger_ref'])
    assert budget['limits'] == before['limits'] and budget['freeze_digest'] == before['freeze_digest']
    assert budget['used_fit_jobs'] - before['used_fit_jobs'] == 9
    assert all(budget['jobs'][k] == v for k, v in before['jobs'].items())
    assert budget['order'] == before['order'] + prepared['priority_order']
    assert set(budget['jobs']) - set(before['jobs']) == set(job_index)
    assert budget['charged_seconds'] >= before['charged_seconds']
    summary = read(dispatch / 'SUMMARY.json')
    assert summary['jobs'] == 9 and summary['predictions'] == 486 and summary['real_fits'] == budget['used_fit_jobs'] == 57
    metadata = {}
    for j in jobs:
        part = read(dispatch / 'jobs' / j['model_unit_id'] / 'evaluation_sidecar.json')
        assert set(part) == set(j['outer_test_ids'])
        for oid, row in part.items():
            assert oid not in metadata or metadata[oid] == row
            metadata[oid] = row
    assert len(metadata) == 162 and Counter(m['phase'] for m in metadata.values()) == {p: 54 for p in PHASES}
    assert all(m['data_role'] == 'SUPERVISED_DEVELOPMENT_BY_FOLD' and m['supervised_label'] == int(m['phase'] == 'attack') for m in metadata.values())
    frozen_study = freeze / 'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924'
    search = read(freeze / 'snapshot/hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json')
    grammar = read(freeze / 'snapshot/hybridguard_agent/config/rule_learning_v1_20260924/candidate_grammar.json')
    definitions = read(freeze / 'data/definitions.json'); atoms_by_id = {a['atom_id']: a for a in definitions['atoms']}
    registry = read(out / 'SINGLE_SURFACE_INPUT_REGISTRY.json')['surfaces']
    model_rows, selected_rows, support_rows, candidates, traces, inventories = [], [], [], [], [], []
    train_checks, access_checks, runtime_checks, encoder_checks, thresholds, per_fold = [], [], [], [], [], []
    models, copies, contexts, encoders = {}, [], {}, []
    metric_checks = 0
    for j in jobs:
        uid, rec = j['model_unit_id'], receipts[j['model_unit_id']]
        source = dispatch / 'jobs' / uid; surface = j['input_view']; spec = registry[surface]
        m, training = read(source / 'model.json'), read(source / 'training.json')
        models[uid] = m; encoder = m['encoder']
        events = read(source / 'access_log.json'); names = [e['event'] for e in events]
        model_receipt = read(source / 'MODEL_FREEZE_RECEIPT.json')
        assert m['model_id'] == rec['model_id'] == model_receipt['model_id']
        assert sha(source / 'model.json') == model_receipt['sha256']
        assert len(m['atoms']) == rec['atoms'] and len(m['clauses']) == rec['clauses']
        for key in ('model_unit_id', 'fold_id', 'method_id', 'operating_point', 'source_condition', 'input_view', 'protocol_digest', 'train_membership_digest'):
            assert m['binding'][key] == j[key], (uid, key)
        assert m['binding']['data_origin'] == 'R02_FIXED_CACHE' and m['binding']['split_id'] == 'LOEO-v1'
        assert m['binding']['freeze_manifest_digest'] == prepared['freeze_manifest_digest']
        assert m['binding']['resource_manifest_digest'] == prepared['resource_manifest_digest']
        assert m['binding']['authorization_ref'] == str(out / 'R07_APPROVAL.json') + '#' + prepared['approval_digest']
        assert m['fit']['fit_scope'] == 'EXACT_AUTHORIZED_JOB_TRAIN_ONLY' and m['fit']['train_ids'] == j['train_ids']
        assert set(j['train_ids']).isdisjoint(j['outer_test_ids'])
        for key in ('bundle_id', 'environment_group_id'):
            assert {metadata[i][key] for i in j['train_ids']}.isdisjoint({metadata[i][key] for i in j['outer_test_ids']})
        for a, b in [('SINGLE_SURFACE_ALLOWLIST_APPLIED', 'TRAIN_READY'), ('TRAIN_READY', 'TRAIN_TRANSFORM_FINISHED'),
                     ('TRAIN_TRANSFORM_FINISHED', 'MODEL_SAVED_LOADED_FROZEN'), ('MODEL_SAVED_LOADED_FROZEN', 'OPEN_OUTER_TEST_FEATURE'),
                     ('OPEN_OUTER_TEST_FEATURE', 'PREDICTIONS_CLOSED_AND_RECONCILED'), ('PREDICTIONS_CLOSED_AND_RECONCILED', 'OPEN_OUTER_EVALUATION_LABEL')]:
            assert names.index(a) < names.index(b), (uid, a, b)
        for event, ids, prefix in [('OPEN_TRAIN_FEATURE', j['train_ids'], 'data/current/'), ('OPEN_TRAIN_LABEL', j['train_ids'], 'data/evaluation/'),
                                  ('OPEN_OUTER_TEST_FEATURE', j['outer_test_ids'], 'data/current/'), ('OPEN_OUTER_EVALUATION_LABEL', j['outer_test_ids'], 'data/evaluation/')]:
            assert [e['resource'] for e in events if e['event'] == event] == [prefix + i + '.json' for i in ids]
        operations = next(e for e in events if e['event'] == 'TRAIN_TRANSFORM_FINISHED')['access_operations']
        for op in operations: assert op['partition'] == 'train' and op['ids'] == j['train_ids']
        numeric_operation_events = sum(op['operation'] == 'numeric_thresholds' for op in operations)
        # The frozen _derived issuer creates a new operations list after numeric
        # fitting. Its saved list covers selection, not the earlier quantile
        # calls. Do not invent per-field call receipts from the encoder entries.
        frozen = next(e for e in events if e['event'] == 'MODEL_SAVED_LOADED_FROZEN')
        assert frozen['sha256'] == model_receipt['sha256']
        assert next(e for e in events if e['event'] == 'TRAIN_READY')['utc'] <= m['fit']['freeze_time'] <= frozen['utc']
        saved = lines(source / 'predictions.jsonl')
        assert next(e for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED')['predictions_digest'] == digest(saved)
        assert saved == [r for r in predictions if r['model_unit_id'] == uid]
        context = {k: j[k] for k in (*KEYS, 'model_unit_id', 'fit_job_id', 'fold_id', 'train_membership_digest')}
        context.update(model_id=m['model_id'], train_membership_ref='expected_model_units.jsonl#' + uid,
            original_model_ref=str(source / 'model.json'), original_training_ref=str(source / 'training.json'))
        contexts[uid] = context
        copies.extend([(source / 'model.json', out / 'fold_models' / (uid + '.json')),
                       (source / 'training.json', out / 'training_logs' / (uid + '.json'))])
        startup = read(source / 'WORKER_STARTUP.json')
        assert startup['module_root'] == str(freeze / 'snapshot') and startup['python_executable'] == str(freeze / 'dependencies/python/bin/python3.12')
        for name in ('highspy_path', 'numpy_path'): assert Path(startup[name]).is_relative_to(freeze / 'dependencies/site-packages')
        assert not list(Path(startup['cwd']).iterdir())
        runtime_checks.append({**context, 'status': 'PASS', **startup})
        access_checks.append({**context, 'status': 'PASS', 'train_n': len(j['train_ids']), 'test_n': len(j['outer_test_ids']),
            'freeze_time': m['fit']['freeze_time'], 'saved_and_loaded_at': frozen['utc'],
            'first_test_feature': next(e['utc'] for e in events if e['event'] == 'OPEN_OUTER_TEST_FEATURE'),
            'prediction_closed': next(e['utc'] for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED'),
            'first_test_label': next(e['utc'] for e in events if e['event'] == 'OPEN_OUTER_EVALUATION_LABEL'),
            'operations_partition': 'TRAIN_ONLY', 'log_ref': str(source / 'access_log.json')})
        white_event = next(e for e in events if e['event'] == 'SINGLE_SURFACE_ALLOWLIST_APPLIED')
        assert white_event['surface'] == surface and white_event['atom_ids'] == spec['all_input_ids']
        assert white_event['atom_ids'] == definitions['single_surface_allowlists'][surface]
        assert encoder['surface'] == surface and encoder['fold_id'] == j['fold_id'] and encoder['train_ids'] == j['train_ids']
        assert encoder['fixed_atoms'] == spec['catalog_ids'] + spec['fixed_control_ids']
        assert set(encoder['numeric']) == set(spec['unfitted_numeric_ids'])
        numeric_atoms = []
        for field, e in encoder['numeric'].items():
            assert e['train_expected_n'] == len(j['train_ids']) and 0 <= e['train_observed_n'] <= len(j['train_ids'])
            assert e['thresholds'] == sorted(set(e['thresholds'])) and len(e['thresholds']) <= 3
            assert e['status'] == ('FROZEN' if e['thresholds'] else 'NO_OBSERVED_TRAIN_VALUES')
            assert bool(e['thresholds']) == bool(e['train_observed_n'])
            assert e['atom_ids'] == ['CONTROL:' + field.removeprefix('UNFITTED_CONTROL:') + ':LE:' + repr(t) for t in e['thresholds']]
            numeric_atoms.extend(e['atom_ids'])
            thresholds.append({**context, 'input_id': field, **e, 'encoder_model_sha256': model_receipt['sha256'],
                'origin': 'SAVED_FROZEN_ENCODER', 'postprocess_refit': False})
        input_atoms = sorted(encoder['fixed_atoms'] + numeric_atoms)
        assert len(input_atoms) == len(set(input_atoms))
        assert m['view'] == {'view_id':'SINGLE:' + surface, 'kind':'SINGLE_SURFACE', 'surface':surface, 'input_atom_ids':input_atoms}
        assert 2 * len(input_atoms) <= grammar['new_encoder']['max_literals_per_surface']
        expected_clauses = {a + ':' + pol for a in input_atoms for pol in ('POSITIVE','NEGATIVE')}
        assert set(training['support']) == {c['clause_id'] for c in training['candidate_manifest']} == expected_clauses
        assert len(training['candidate_manifest']) == m['fit']['registered_clause_count'] == len(expected_clauses)
        assert sum(c['eligible'] for c in training['candidate_manifest']) == m['fit']['candidate_pool_size']
        assert not any(a.startswith('UNFITTED_CONTROL:') for a in input_atoms)
        encoder_checks.append({**context, 'status':'PASS', 'input_allowlist_ids':spec['all_input_ids'],
            'numeric_input_n':len(encoder['numeric']), 'encoded_atom_n':len(input_atoms),
            'exact_train_members':True, 'frozen_before_outer_read':True, 'unapproved_same_surface_catalog_ids':[],
            'saved_numeric_operation_events':numeric_operation_events,
            'numeric_call_log_limit':'Frozen _derived creates a fresh access.operations list; per-field quantile call events are not retained.',
            'train_only_evidence':['Exact train-only feature reads before freeze','Frozen _TrainOnlyData has no test partition',
                'TrainQuantiles.fit asserts exact train batch','Saved encoder train IDs and fold match the exact job',
                'Encoder is inside saved/loaded model before outer access'],
            'numeric_validation_scope':'Saved membership, ordered unique thresholds, declared count/status, generated IDs and frozen bytes plus frozen code/access boundary; no raw-value reread or refit.'})
        encoders.append({**context, 'encoder':encoder, 'model_sha256':model_receipt['sha256'], 'frozen_at':m['fit']['freeze_time']})
        available = {p:Counter() for p in PHASES}
        for cid, s in training['support'].items():
            assert s['statistics_scope'] == 'TRAIN_FOLD_ONLY' and s['train_ids'] == j['train_ids']
            assert s['triplets'] == len(set(map(tuple,s['complete_triplet_ids']))) == len(s['complete_triplet_ids'])
            assert s['true_attack_triplets'] == len(set(map(tuple,s['true_attack_triplet_ids'])))
            assert set(map(tuple,s['true_attack_triplet_ids'])) <= set(map(tuple,s['complete_triplet_ids']))
            support_rows.append({**context,'clause_id':cid,**s})
            if cid.endswith(':POSITIVE'):
                for phase in PHASES: available[phase].update(s['phase_availability'][phase])
        candidates.extend({**context,**c} for c in training['candidate_manifest'])
        traces.extend({**context,'trace_index':i,**t} for i,t in enumerate(training['trace']))
        for atom in m['atoms']:
            assert atom['atom_id'] in input_atoms and atom['surfaces'] == [surface]
            if atom['atom_id'] in encoder['fixed_atoms']:
                assert atom == atoms_by_id[atom['atom_id']]
                assert atom['orientation'] in ('CATALOG_CONDITION','CONTROL_EQUALITY')
            else:
                assert atom['orientation'] == 'CONTROL_LE' and atom['sources'] == ['PROJECT_CONTROL_NOT_E_Ou_H_C']
                field = 'UNFITTED_CONTROL:' + atom['provenance']['field']
                assert atom['provenance']['threshold'] in encoder['numeric'][field]['thresholds']
        for clause in m['clauses']:
            assert len(clause['literals']) == 1
            literal = clause['literals'][0]; atom = next(a for a in m['atoms'] if a['atom_id'] == literal['atom_id'])
            cid = literal['atom_id'] + ':' + literal['polarity']; s = training['support'][cid]
            assert s['eligible'] and s['triplets'] >= search['support']['minimum_available_triplets']
            assert s['true_attack_triplets'] >= search['support']['minimum_true_attack_triplets_per_literal_or_clause']
            selected_rows.append({**context,'record_type':'SELECTED_LITERAL','clause_id':cid,**literal,'atom':atom,'support':s})
        if not m['clauses']:
            selected_rows.append({**context,'record_type':'EMPTY_MODEL','reason':m['fit']['status'],'model_status':m['status']})
        f, result = m['fit'], m['fit']['training_result']
        states = dict(zip(j['train_ids'],result['states'],strict=True))
        assert f['train_expected_n'] == f['train_consumed_n'] == len(states)
        nclean = sum(metadata[i]['supervised_label'] == 0 for i in states)
        alarms = sum(s == 'T' and metadata[i]['supervised_label'] == 0 for i,s in states.items())
        clean_budget = int(Fraction('0.05') * nclean)
        assert f['clean_denominator'] == nclean and f['clean_budget_count'] == clean_budget and result['clean_alarms'] == alarms
        coverage = {p:Fraction(sum(s in ('T','F') for i,s in states.items() if metadata[i]['phase']==p),sum(metadata[i]['phase']==p for i in states)) for p in PHASES}
        cost = sum(1+len(c['literals']) for c in m['clauses']); n,d = macro(j['train_ids'],metadata,lambda i:states[i]=='T')
        assert n/d == Fraction(result['macro_tpr']['numerator'],result['macro_tpr']['denominator'])
        objective = n/d - Fraction(str(search['objective']['lambda'])) * cost
        assert objective == Fraction(result['objective']['numerator'],result['objective']['denominator'])
        assert cost == result['complexity'] == m['complexity']['objective_complexity']
        for p,c in coverage.items(): assert c == Fraction(result['coverage'][p]['numerator'],result['coverage'][p]['denominator'])
        feasible = alarms <= clean_budget and min(coverage.values()) >= Fraction('0.8') and cost <= 12 and len(m['clauses']) <= 6
        assert feasible == result['feasible']
        if m['status'] == 'FITTED':assert feasible
        if m['status'] == 'EMPTY_MODEL':
            assert not feasible and set(states.values()) == {'EMPTY_MODEL'}
            assert f['infeasibility_proved'] is False
        train_checks.append({**context,'status':'PASS','model_status':m['status'],'fit_status':f['status'],'stop':f['stop'],
            'train_expected_n':len(states),'clean_denominator':nclean,'clean_budget':clean_budget,'clean_alarms':alarms,
            'phase_decision_coverage':{p:float(c) for p,c in coverage.items()},'complexity':cost,'train_constraints_feasible':feasible,
            'macro_tpr':str(n/d),'objective':str(objective),'infeasibility_proved':f['infeasibility_proved']})
        inventories.append({**context,**spec['counts'],'encoded_atom_n':len(input_atoms),'registered_literal_n':len(expected_clauses),
            'eligible_literal_n':f['candidate_pool_size'],'selected_atoms':len(m['atoms']),'selected_clauses':len(m['clauses']),
            'complexity':cost,'model_status':m['status'],'fit_status':f['status'],'stop':f['stop'],
            'outcome_category':'FITTED_FROM_SUPPORTED_POOL' if m['status']=='FITTED' else 'NONEMPTY_POOL_NO_FEASIBLE_MODEL_FOUND_BY_GREEDY',
            'train_candidate_availability':{p:{**dict(c),'coverage':ratio(c['defined'],c['expected'])} for p,c in available.items()},
            'availability_counting':'Each encoded atom once, POSITIVE support only; no full outer candidate recomputation.'})
        model_rows.append({**context,'state':rec['state'],'model_status':m['status'],'fit_status':f['status'],
            'train_ids':j['train_ids'],'outer_test_ids':j['outer_test_ids'],'model_sha256':model_receipt['sha256'],
            'encoder_digest':digest(encoder),'freeze_time':f['freeze_time'],'receipt':rec,'complexity':m['complexity']})
        report = read(source/'metrics.json'); indexed = {r['opaque_id']:r for r in saved}
        metric_checks += check_metrics(report['metrics'],indexed,metadata)
        for strata in report['strata'].values():
            for ms in strata.values():metric_checks += check_metrics(ms,indexed,metadata)
        per_fold.append({**context,'source_report_ref':str(source/'metrics.json'),'report':report})

    reference_jobs = lines(out/'reference_R05_model_units.jsonl')
    reference_bindings = {r['model_unit_id']:r for r in read(out/'R05_REFERENCE_BINDINGS_BEFORE.json')['rows']}
    reference_predictions, reference_checks, reference_models = [], [], []
    all_jobs = jobs + reference_jobs
    for j in reference_jobs:
        uid=j['model_unit_id']; binding=reference_bindings[uid]; source=Path(binding['source_directory'])
        for name, old in binding['files'].items():
            p=source/name
            assert sha(p)==old['sha256'] and p.stat().st_mtime_ns==old['mtime_ns'] and p.stat().st_size==old['bytes']
        m=read(source/'model.json'); saved=lines(source/'predictions.jsonl'); report=read(source/'metrics.json')
        models[uid]=m
        assert m['model_id']==binding['model_id'] and m['fit']['freeze_time']==binding['freeze_time']
        assert digest(saved)==binding['saved_prediction_digest'] and [r['opaque_id'] for r in saved]==j['outer_test_ids']
        assert read(source/'evaluation_sidecar.json')=={i:metadata[i] for i in j['outer_test_ids']}
        indexed={r['opaque_id']:r for r in saved}; metric_checks+=check_metrics(report['metrics'],indexed,metadata)
        for strata in report['strata'].values():
            for ms in strata.values():metric_checks+=check_metrics(ms,indexed,metadata)
        context={k:j[k] for k in (*KEYS,'model_unit_id','fit_job_id','fold_id','train_membership_digest')}
        context.update(model_id=m['model_id'],train_membership_ref='reference_R05_model_units.jsonl#'+uid,
            original_model_ref=str(source/'model.json'),original_training_ref=str(source/'training.json'),
            comparison_role='SAVED_R05_CROSS_SURFACE_REFERENCE')
        contexts[uid]=context
        per_fold.append({**context,'source_report_ref':str(source/'metrics.json'),'report':report})
        reference_predictions.extend(saved)
        reference_models.append({**context,'model_sha256':binding['files']['model.json']['sha256'],
            'freeze_time':m['fit']['freeze_time'],'complexity':m['complexity'],'new_fit':False,'new_prediction':False})
        reference_checks.append({**context,'status':'PASS','reference_prediction_n':len(saved),
            'model_id_bytes_and_freeze_time_unchanged':True,'original_closed_prediction_digest':binding['saved_prediction_digest'],
            'all_original_file_times_unchanged':True,'new_fit':False,'new_prediction':False})
    assert len(reference_predictions)==162
    oof=read(dispatch/'OOF.json')
    reference_oof=[x for x in read(study/'R05_primary/dispatch/OOF.json') if x['group']['method_id']=='GREEDY_OR' and x['group']['operating_point']=='OP05']
    assert len(oof)==3 and len(reference_oof)==1
    all_predictions=predictions+reference_predictions; comparisons=oof+reference_oof
    metric_rows, triplets, summaries, by_view = [], [], [], {}
    for item in comparisons:
        group,report=item['group'],item['report'];view=group['input_view']
        group_jobs=[j for j in all_jobs if all(j[k]==v for k,v in group.items())];uids={j['model_unit_id'] for j in group_jobs}
        rows={r['opaque_id']:r for r in all_predictions if r['model_unit_id'] in uids};by_view[view]=rows
        assert len(rows)==report['expected_stage_n']==162 and len(group_jobs)==item['expected_fold_n']==3
        assert not item['missing_units'] and not item['unavailable_models'] and report['descriptive_n']==0
        role='SAVED_R05_CROSS_SURFACE_REFERENCE' if view=='core' else 'R07_SINGLE_SURFACE_REFIT'
        scopes=[('ALL','ALL_EXPECTED',report['metrics'])]
        for dim,strata in report['strata'].items():scopes.extend((dim,label,ms) for label,ms in strata.items())
        for dimension,label,ms in scopes:
            metric_checks+=check_metrics(ms,rows,metadata)
            for name,metric in ms.items():
                source_uids=sorted({rows[i]['model_unit_id'] for i in metric['source_rows']})
                metric_rows.append({**group,**metric,'dimension':dimension,'stratum_label':label,'metric_id':name,
                    'comparison_role':role,'model_unit_ids':source_uids,'model_ids':[models[u]['model_id'] for u in source_uids],
                    'fold_ids':sorted({contexts[u]['fold_id'] for u in source_uids}),
                    'train_membership_refs':[contexts[u]['train_membership_ref'] for u in source_uids]})
        for t in report['triplet_rows']:
            members=[rows[i] for i in t['source_rows']];assert len({r['model_unit_id'] for r in members})==1
            r=members[0];triplets.append({**group,**t,'aggregate_fold_id':t['fold_id'],'fold_id':r['fold_id'],
                'comparison_role':role,'model_id':r['model_id'],'model_unit_id':r['model_unit_id'],
                'train_membership_ref':contexts[r['model_unit_id']]['train_membership_ref']})
        summary_row={**group,'comparison_role':role,'new_fit_jobs':0 if view=='core' else 3,
            'reference_model_units':3 if view=='core' else 0,
            'model_statuses':dict(Counter(models[j['model_unit_id']]['status'] for j in group_jobs)),
            'complexity_by_fold':{j['fold_id']:models[j['model_unit_id']]['complexity']['objective_complexity'] for j in group_jobs},
            'selected_clauses_by_fold':{j['fold_id']:models[j['model_unit_id']]['clauses'] for j in group_jobs},
            'model_ids':[models[j['model_unit_id']]['model_id'] for j in group_jobs],
            'train_membership_refs':[contexts[j['model_unit_id']]['train_membership_ref'] for j in group_jobs]}
        for name,metric in report['metrics'].items():
            for field in ('numerator','denominator','expected_denominator','value','status'):summary_row[name+'_'+field]=metric[field]
        summaries.append(summary_row)

    exports,rule_events=[] ,[]
    for n,r in enumerate(predictions,1):
        uid=r['model_unit_id'];j=job_index[uid];m=models[uid]
        assert all(r[k]==j[k] for k in (*KEYS,'fold_id')) and r['model_id']==m['model_id']
        assert r['selected_atoms_expected']==len(m['atoms']) and r['clauses_expected']==len(m['clauses'])
        assert not {'supervised_label','phase','tool','config_id','environment_group_id','bundle_id','triplet_id'} & set(r)
        if m['status']=='EMPTY_MODEL':
            assert r['decision']=='EMPTY_MODEL' and r['logical_state'] is None
            assert r['selected_atoms_expected']==r['clauses_expected']==0
        else:
            atom_states={e['atom_id']:e['state'] for e in r['atom_explanations']}; states=[]
            assert set(atom_states)=={a['atom_id'] for a in m['atoms']}
            for clause,event in zip(m['clauses'],r['clause_explanations'],strict=True):
                lit=clause['literals'][0];s=atom_states[lit['atom_id']]
                if lit['polarity']=='NEGATIVE':s={'T':'F','F':'T','U':'U'}[s]
                assert s==event['state'];states.append(s)
            logical='T' if 'T' in states else ('F' if all(s=='F' for s in states) else 'U')
            assert logical==r['logical_state'] and r['decision']=={'T':'MANIPULATION_ALERT','F':'NO_ALERT','U':'INSUFFICIENT_EVIDENCE'}[logical]
        exported={**r,'saved_prediction_ref':str(dispatch/'predictions.jsonl')+':'+str(n),
            'train_membership_ref':contexts[uid]['train_membership_ref']}
        exports.append(exported)
        for kind,key in [('ATOM','atom_explanations'),('CLAUSE','clause_explanations')]:
            for e in r[key]:rule_events.append({**contexts[uid],'opaque_id':r['opaque_id'],'event_type':kind,**e,'saved_prediction_ref':exported['saved_prediction_ref']})
        if not r['atom_explanations']:
            rule_events.append({**contexts[uid],'opaque_id':r['opaque_id'],'event_type':r['decision'],'failure_reason':r['failure_reason'],
                'saved_prediction_ref':exported['saved_prediction_ref']})

    attack_ids={i for i,m in metadata.items() if m['supervised_label']==1}
    detected={v:{i for i in attack_ids if rows[i]['decision']=='MANIPULATION_ALERT'} for v,rows in by_view.items()}
    cross=detected['core'];missed=attack_ids-cross
    # Counts below are verified properties of the already-closed R05 reference,
    # never a target imposed on a newly trained single-surface result.
    assert len(cross)==24 and len(missed)==30
    configs=sorted({m['config_id'] for m in metadata.values()})
    missed_configs=[c for c in configs if not any(metadata[i]['config_id']==c for i in cross)]
    assert len(missed_configs)==8
    paired,paired_stages,config_rows,missed_rows,missed_config_rows=[],[],[],[],[]
    for view in ('native84','app_web67','host26'):
        rows=by_view[view];hits=detected[view]
        assert set(rows)==set(by_view['core'])==set(metadata)
        for oid in sorted(metadata):
            a,b=by_view['core'][oid],rows[oid];assert a['fold_id']==b['fold_id']
            ja=next(j for j in reference_jobs if j['fold_id']==a['fold_id']);jb=job_index[b['model_unit_id']]
            assert ja['train_ids']==jb['train_ids'] and ja['outer_test_ids']==jb['outer_test_ids']
            paired_stages.append({'input_view':view,'opaque_id':oid,'fold_id':b['fold_id'],'method_id':'GREEDY_OR','operating_point':'OP05',
                'source_condition':'SRC-111','single_model_id':b['model_id'],'single_model_unit_id':b['model_unit_id'],'single_decision':b['decision'],
                'cross_model_id':a['model_id'],'cross_model_unit_id':a['model_unit_id'],'cross_decision':a['decision'],
                'single_train_membership_ref':contexts[b['model_unit_id']]['train_membership_ref'],
                'cross_train_membership_ref':contexts[a['model_unit_id']]['train_membership_ref'],
                'evaluation_sidecar':metadata[oid],'scope':'COMPARISON_OF_SAVED_OOF_RECORDS_ONLY'})
        paired.append({'input_view':view,'cross_reference':'R05_GREEDY_OR_OP05_CORE_SRC111','expected_stage_n':162,'attack_n':54,
            'same_outer_ids_and_train_ids_each_fold':True,'single_detected_n':len(hits),'cross_detected_n':len(cross),
            'intersection_n':len(hits&cross),'union_n':len(hits|cross),'single_only_n':len(hits-cross),'cross_only_n':len(cross-hits),
            'neither_detected_n':len(attack_ids-(hits|cross)),'recovered_R05_miss_n':len(hits&missed),'R05_miss_denominator':len(missed),
            'intersection_ids':sorted(hits&cross),'union_ids':sorted(hits|cross),'single_only_ids':sorted(hits-cross),'cross_only_ids':sorted(cross-hits),
            'recovery_by_configuration':dict(Counter(metadata[i]['config_id'] for i in hits&missed)),
            'cross_only_by_configuration':dict(Counter(metadata[i]['config_id'] for i in cross-hits)),
            'set_relation':('EQUAL' if hits==cross else 'SINGLE_SUBSET_OF_CROSS' if hits<cross else 'CROSS_SUBSET_OF_SINGLE' if cross<hits else 'COMPLEMENTARY_NEITHER_CONTAINS_OTHER'),
            'union_is_descriptive_overlap_not_new_ensemble_prediction':True})
    for config in configs:
        ids=sorted(i for i,m in metadata.items() if m['config_id']==config); attacks=set(ids)&attack_ids
        row={'config_id':config,'attack_n':len(attacks),'expected_stage_n':len(ids),'source_rows':ids,
             'cross_detected_n':len(cross&attacks),'R05_completely_missed_configuration':config in missed_configs}
        for view in ('native84','app_web67','host26'):
            row.update({view+'_detected_n':len(detected[view]&attacks),view+'_recovered_n':len(detected[view]&attacks&missed),
                view+'_pre_alarm_n':sum(by_view[view][i]['decision']=='MANIPULATION_ALERT' for i in ids if metadata[i]['phase']=='clean_pre'),
                view+'_post_alarm_n':sum(by_view[view][i]['decision']=='MANIPULATION_ALERT' for i in ids if metadata[i]['phase']=='clean_post'),
                view+'_decided_n':sum(by_view[view][i]['decision'] in ('MANIPULATION_ALERT','NO_ALERT') for i in ids),
                view+'_abstained_n':sum(by_view[view][i]['decision'] in ('EMPTY_MODEL','INSUFFICIENT_EVIDENCE') for i in ids),
                view+'_failed_n':sum(by_view[view][i]['decision']=='FAILED' for i in ids)})
        config_rows.append(row)
        if config in missed_configs:missed_config_rows.append(copy.deepcopy(row))
    for oid in sorted(missed):
        r=by_view['core'][oid];row={'opaque_id':oid,'fold_id':r['fold_id'],**metadata[oid],
            'R05_model_id':r['model_id'],'R05_decision':r['decision'],'R05_model_ref':contexts[r['model_unit_id']]['original_model_ref']}
        recovered=[]
        for view in ('native84','app_web67','host26'):
            s=by_view[view][oid]
            row[view+'_decision']=s['decision'];row[view+'_model_id']=s['model_id'];row[view+'_model_unit_id']=s['model_unit_id']
            row[view+'_true_clause_ids']=[e['clause_id'] for e in s['clause_explanations'] if e['state']=='T']
            row[view+'_prediction_ref']=str(dispatch/'jobs'/s['model_unit_id']/'predictions.jsonl')+'#'+oid
            if s['decision']=='MANIPULATION_ALERT':recovered.append(view)
        row['recovered_by']=recovered;row['recovered_by_any_frozen_single_surface']=bool(recovered);missed_rows.append(row)
    stability=[]
    for view in ('native84','app_web67','host26','core'):
        part=[j for j in all_jobs if j['input_view']==view]
        for a,b in combinations(part,2):
            ma,mb=models[a['model_unit_id']],models[b['model_unit_id']]
            literals=lambda m:{l['atom_id']+':'+l['polarity'] for c in m['clauses'] for l in c['literals']}
            aa,bb=literals(ma),literals(mb)
            stability.append({'input_view':view,'fold_a':a['fold_id'],'fold_b':b['fold_id'],'model_id_a':ma['model_id'],'model_id_b':mb['model_id'],
                'selected_literal_jaccard':ratio(len(aa&bb),len(aa|bb)),'both_empty':not aa and not bb,
                'claim_scope':'Observed folds; no population stability or causal source attribution.'})

    catalog=lines(frozen_study/'R01_protocol/CANDIDATE_LEDGER.jsonl')
    core=[c for c in catalog if c['candidate_use']['core'] and c['candidate_use']['selectable_on_App177']]
    gap_cases=[]
    for view in ('native84','app_web67','host26'):
        for oid in sorted(detected[view]-cross):
            prediction=by_view[view][oid];m=models[prediction['model_unit_id']]
            details=[]
            for clause in prediction['clause_explanations']:
                if clause['state']!='T':continue
                lit=clause['literals'][0];atom=next(a for a in m['atoms'] if a['atom_id']==lit['atom_id'])
                prov=atom['provenance'];fields=prov.get('field_refs') or ([prov['field']] if prov.get('field') else [])
                details.append({'clause_id':clause['clause_id'],'atom':atom,'polarity':lit['polarity'],'saved_clause_state':'T',
                    'field_refs':fields,'cross_core_candidates_reading_these_fields':sorted({c['normalized_identity'] for c in core if set(fields)&set(c['dependencies'])})})
            gap_cases.append({'opaque_id':oid,'input_view':view,'fold_id':prediction['fold_id'],'model_id':prediction['model_id'],
                'config_id':metadata[oid]['config_id'],'environment_group_id':metadata[oid]['environment_group_id'],
                'R05_decision':by_view['core'][oid]['decision'],'single_decision':prediction['decision'],'true_conditions':details,
                'saved_prediction_ref':str(dispatch/'jobs'/prediction['model_unit_id']/'predictions.jsonl')+'#'+oid,
                'interpretation_limit':'Direct field/condition expressivity of frozen candidate inventory only; no new rule, causal claim or new prediction.'})
    fixed_mask=[]
    for j in reference_jobs:
        for surface in ('native84','app_web67','host26'):
            fixed_mask.append({'branch':'R07_FIXED_MODEL_MASK','fold_id':j['fold_id'],'base_model_unit_id':j['model_unit_id'],
                'base_model_id':models[j['model_unit_id']]['model_id'],'removed_surface':surface,'status':'NOT_RUN',
                'reason':'FROZEN_RESERVED_INTERFACE_UNIMPLEMENTED_NOT_AUTHORIZED_THIS_RUN','result':None,
                'attack_tpr':None,'pre_alarm_rate':None,'post_alarm_rate':None,'prediction_records':None})
    semantics=[{'branch':'R07_SEMANTIC_DIAGNOSTIC','variant':v,'scope':'SYNTHETIC_ONLY','status':'NOT_RUN',
        'reason':'NO_FROZEN_R07_JOB_DRIVER_OR_EXPECTED_UNITS_MAIN_BRANCH_ONLY','result':None,
        'previous_synthetic_tests_are_not_new_R07_experiment_results':True}
        for v in ('NEGATE_U','FAILED_ATOM','DUPLICATE_ALIAS','EMPTY_MODEL')]
    branches={'R07_SINGLE_SURFACE_REFIT':{'status':'COMPLETED_PENDING_EXTERNAL_REVIEW','authorized_this_run':True,
        'new_fit_jobs':9,'model_units':9,'prediction_records':486},
        'R07_FIXED_MODEL_MASK':{'status':'NOT_RUN','implemented_in_freeze':False,'authorized_this_run':False,'reserved_rows':9,'result':None},
        'R07_SEMANTIC_DIAGNOSTIC':{'status':'NOT_RUN','scope':'SYNTHETIC_ONLY','frozen_job_driver_available':False,
            'authorized_this_run':False,'registered_variants':4,'result':None},
        'R07_BROWSER_ATTACK':{'status':'NOT_AVAILABLE','reason':'NO_BROWSER_ATTACK_MATERIAL','result':None},
        'R06_parent_status':'PARTIALLY_COMPLETED','R06_POSTFIT_DELETE':'NOT_RUN','all_R07_branches_complete':False}
    budget_check={'status':'PASS','same_ledger_ref':prepared['budget_ledger_ref'],'reset':False,'synthetic_ledger':False,
        'prior_fit_jobs':before['used_fit_jobs'],'new_fit_jobs':9,'cumulative_fit_jobs':budget['used_fit_jobs'],
        'prior_charged_seconds':before['charged_seconds'],'incremental_charged_seconds':budget['charged_seconds']-before['charged_seconds'],
        'cumulative_charged_seconds':budget['charged_seconds'],'remaining_fit_jobs':budget['limits']['max_fit_jobs']-budget['used_fit_jobs'],
        'remaining_seconds':budget['limits']['wall_clock_seconds']-budget['charged_seconds'],
        'all_63_prior_job_records_preserved_exactly':True,'original_dispatch_SUMMARY_real_fits_is_cumulative':True}
    row_manifest=lines(frozen_study/'R02_matrix/ROW_MANIFEST.jsonl')
    descriptive=sorted({r['opaque_id'] for r in row_manifest}-set(metadata))
    assert len(descriptive)==100 and set(descriptive).isdisjoint(metadata)
    reconciliation={'status':'PASS','new_fit_jobs':9,'model_units':9,'expected_predictions':486,'saved_predictions':len(predictions),
        'unique_supervised_stages':162,'stage_counts':dict(Counter(m['phase'] for m in metadata.values())),
        'model_states':dict(Counter(r['state'] for r in receipts.values())),
        'prediction_decisions':dict(Counter(r['decision'] for r in predictions)),
        'R05_reference_models':3,'R05_reference_saved_predictions':162,'R05_new_fit_or_prediction_calls':0,
        'missing_or_duplicate_units':0,'retries':0,'excluded_descriptive_ids':descriptive,
        'numeric_encoder_jobs':9,'saved_numeric_field_transformers':len(thresholds),
        'counts_do_not_turn_surfaces_into_independent_samples':True}
    for src,dest in copies:
        assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        assert sha(src)==sha(dest)
    for encoder in encoders:write(out/'encoders'/(encoder['model_unit_id']+'.json'),encoder)
    for name,rows in [('MODEL_MANIFEST.jsonl',model_rows),('REFERENCE_MODEL_MANIFEST.jsonl',reference_models),
        ('selected_rules.jsonl',selected_rows),('support_statistics.jsonl',support_rows),('candidate_admission.jsonl',candidates),
        ('selection_trace.jsonl',traces),('candidate_inventory.jsonl',inventories),('encoder_thresholds.jsonl',thresholds),
        ('per_fold_metrics.jsonl',per_fold),('oof_predictions.jsonl',exports),('reference_R05_predictions.jsonl',reference_predictions),
        ('rule_events.jsonl',rule_events),('evaluation_sidecar.jsonl',[{'opaque_id':i,**m} for i,m in sorted(metadata.items())]),
        ('triplet_results.jsonl',triplets),('paired_comparison.jsonl',paired),('paired_stage_comparison.jsonl',paired_stages),
        ('missed_attack_recovery.jsonl',missed_rows),('representation_gap_cases.jsonl',gap_cases),
        ('fixed_model_mask.jsonl',fixed_mask),('semantic_state_diagnostics.jsonl',semantics),
        ('failures/failures.jsonl',[r for r in exports if r['decision']=='FAILED']),
        ('failures/abstentions.jsonl',[r for r in exports if r['decision'] in ('EMPTY_MODEL','INSUFFICIENT_EVIDENCE')])]:
        jsonl(out/name,rows)
    for name,rows in [('single_surface_metrics.csv',[r for r in summaries if r['input_view']!='core']),
        ('comparison_metrics.csv',summaries),('metrics.csv',metric_rows),('candidate_inventory.csv',inventories),
        ('encoder_thresholds.csv',thresholds),('training_constraints.csv',train_checks),('paired_comparison.csv',paired),
        ('fold_metrics.csv',[{k:v for k,v in row.items() if k!='report'}|{'metric_id':name,**m}
            for row in per_fold for name,m in row['report']['metrics'].items()]),
        ('missed_attack_recovery.csv',missed_rows),('missed_config_recovery.csv',missed_config_rows),('configuration_comparison.csv',config_rows),
        ('by_configuration.csv',[r for r in metric_rows if r['dimension'] in ('config','config_environment')]),
        ('by_environment.csv',[r for r in metric_rows if r['dimension']=='environment']),
        ('fixed_model_mask.csv',fixed_mask),('semantic_state_diagnostics.csv',semantics)]:csv_file(out/name,rows)
    write(out/'metrics.json',oof);write(out/'comparison_metrics.json',comparisons)
    write(out/'BRANCH_STATUS.json',branches);write(out/'RULE_STABILITY.json',stability)
    write(out/'RECONCILIATION.json',reconciliation);write(out/'BUDGET_AFTER.json',budget);write(out/'BUDGET_VALIDATION.json',budget_check)
    write(out/'ACCESS_ORDER_VALIDATION.json',{'status':'PASS','new_job_chains':9,'rows':access_checks,
        'numeric_operation_log_limitation':'Per-field quantile events are not retained by frozen _derived. Exact train-only reads, capability code, encoder membership, freeze bytes and access order are the audit basis.'})
    write(out/'RUNTIME_VALIDATION.json',{'status':'PASS','rows':runtime_checks})
    write(out/'ENCODER_ALLOWLIST_VALIDATION.json',{'status':'PASS','rows':encoder_checks,'saved_numeric_field_transformers':len(thresholds),
        'quantile_arithmetic_recomputed_after_run':False,'additional_raw_feature_reads':0,'new_threshold_fits':0})
    write(out/'TRAINING_VALIDATION.json',{'status':'PASS','rows':train_checks,'empty_models_are_not_proven_infeasible':True,
        'empty_nonempty_candidate_pool_results_retained':sum(m['status']=='EMPTY_MODEL' for uid,m in models.items() if uid in job_index)})
    write(out/'REFERENCE_VALIDATION.json',{'status':'PASS','reference_models':3,'saved_prediction_n':162,'new_fit':0,'new_prediction':0,'rows':reference_checks})
    write(out/'OOF_ARITHMETIC_VALIDATION.json',{'status':'PASS','independently_checked_metric_cells':metric_checks,
        'R07_groups':3,'R05_reference_groups':1,'folds_per_group':3,'expected_members_identical':True,
        'scope':'Saved fold and OOF metrics and every stratum; explanations checked algebraically without raw-data prediction.'})
    write(out/'POSTPROCESS_MANIFEST.json',{'status':'PASS','script':str(Path(__file__).resolve()),'script_sha256':sha(Path(__file__)),
        'python_executable':str(Path(sys.executable).resolve()),'input_OOF_sha256':sha(dispatch/'OOF.json'),
        'input_prediction_sha256':sha(dispatch/'predictions.jsonl'),'new_fits':0,'new_predictions':0,'raw_feature_reads':0,
        'original_artifact_changes':0,'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-clock,
        'rows':{'models':len(model_rows),'encoders':len(encoders),'numeric_transformers':len(thresholds),'support':len(support_rows),
            'candidates':len(candidates),'predictions':len(exports),'events':len(rule_events),'metrics':len(metric_rows),
            'paired_stage_rows':len(paired_stages),'missed_attack_rows':len(missed_rows),'gap_cases':len(gap_cases)}})
    print(json.dumps({'status':'PASS','models':len(model_rows),'predictions':len(exports),'reference_predictions':162,
        'metric_checks':metric_checks,'paired':[{'view':p['input_view'],'single':p['single_detected_n'],'intersection':p['intersection_n'],
            'union':p['union_n'],'recovered':p['single_only_n'],'cross_only':p['cross_only_n']} for p in paired],
        'new_fits':0,'new_predictions':0}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    export(parser.parse_args().out)
