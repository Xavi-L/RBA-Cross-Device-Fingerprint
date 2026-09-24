"""Audit/export closed R06_SOURCE_REFIT outputs. Stdlib only; never fit/predict.

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
    out = Path(out).resolve(); study, dispatch = out.parent, out / 'dispatch'
    prepared, process = read(out / 'RUN_PREPARED.json'), read(out / 'PROCESS_RESULT.json')
    freeze = Path(prepared['freeze_directory'])
    assert Path(sys.executable).resolve() == freeze / 'dependencies/python/bin/python3.12'
    assert process['returncode'] == 0 and process['attempt'] == 1 and process['automatic_retries'] == 0
    assert sha(freeze / 'FREEZE_MANIFEST.json') == prepared['freeze_manifest_digest']
    assert sha(freeze / 'RESOURCE_MANIFEST.json') == prepared['resource_manifest_digest']
    assert sha(out / 'R06_APPROVAL.json') == prepared['approval_digest']
    jobs, fit_jobs, wanted_rows = (lines(out / n) for n in ('expected_model_units.jsonl', 'expected_fit_jobs.jsonl', 'expected_prediction_units.jsonl'))
    job_index = {j['model_unit_id']: j for j in jobs}
    receipts, predictions, oof = read(dispatch / 'model_receipts.json'), lines(dispatch / 'predictions.jsonl'), read(dispatch / 'OOF.json')
    assert len(jobs) == len(job_index) == len(receipts) == 24 and len(fit_jobs) == 21
    expected = {(r['model_unit_id'], r['opaque_id']): r for r in wanted_rows}
    received = {(r['model_unit_id'], r['opaque_id']): r for r in predictions}
    assert len(expected) == len(received) == len(predictions) == 1296 and set(expected) == set(received)
    assert set(receipts) == set(job_index)
    closure = read(dispatch / 'PREDICTION_CLOSURE.json')
    assert closure['expected'] == closure['saved'] == 1296 and closure['digest'] == digest(predictions)
    before, budget = read(out / 'BUDGET_BEFORE.json'), read(prepared['budget_ledger_ref'])
    assert budget['limits'] == before['limits'] and budget['freeze_digest'] == before['freeze_digest']
    assert budget['used_fit_jobs'] - before['used_fit_jobs'] == 21
    assert all(budget['jobs'][k] == v for k, v in before['jobs'].items())
    assert budget['order'] == before['order'] + prepared['priority_order']
    assert set(budget['jobs']) - set(before['jobs']) == set(job_index)
    assert budget['charged_seconds'] >= before['charged_seconds']
    summary = read(dispatch / 'SUMMARY.json')
    assert summary['jobs'] == 24 and summary['predictions'] == 1296
    assert summary['real_fits'] == budget['used_fit_jobs'] == 48  # Frozen SUMMARY is cumulative, not this-stage count.
    metadata = {}
    for j in jobs:
        if not j['reuse_model_unit_id']:
            part = read(dispatch / 'jobs' / j['model_unit_id'] / 'evaluation_sidecar.json')
            assert set(part) == set(j['outer_test_ids'])
            for oid, row in part.items():
                assert oid not in metadata or metadata[oid] == row
                metadata[oid] = row
    assert len(metadata) == 162 and Counter(m['phase'] for m in metadata.values()) == {p: 54 for p in PHASES}
    assert all(m['data_role'] == 'SUPERVISED_DEVELOPMENT_BY_FOLD' and m['supervised_label'] == int(m['phase'] == 'attack') for m in metadata.values())
    frozen_study = freeze / 'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924'
    catalog = lines(frozen_study / 'R01_protocol/CANDIDATE_LEDGER.jsonl')  # Frozen metadata only.
    search = read(freeze / 'snapshot/hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json')
    registry = {}
    for condition in sorted({j['source_condition'] for j in jobs}):
        sources = allowed_sources(condition)
        assigned = [c for c in catalog if c['provenance_group'] in sources]
        selected = [c for c in assigned if c['candidate_use']['core'] and c['candidate_use']['selectable_on_App177']]
        groups = defaultdict(list)
        for c in selected: groups[c['normalized_identity']].append(c)
        registry[condition] = {'source_condition': condition, 'bit_order': ['O_u', 'H', 'E'], 'allowed_sources': sources,
            'registered_source_catalog_n': len(assigned), 'allowed_raw_core_alias_n': len(selected), 'canonical_core_atom_n': len(groups),
            'raw_alias_ids': sorted(c['rule_id'] for c in selected), 'canonical_atom_ids': sorted(groups),
            'canonical_candidates': [{'atom_id': identity, 'family': members[0]['decision_family'],
                'allowed_aliases': sorted(c['rule_id'] for c in members),
                'all_registered_aliases': sorted(c['rule_id'] for c in catalog if c['normalized_identity'] == identity),
                'contributing_aliases': [{'raw_atom_id': c['atom_id'], 'rule_id': c['rule_id'], 'source': c['provenance_group'],
                    'deviation_polarity': c['direct_OR_deviation_polarity'], 'profile': c['measurement']['profile'],
                    'field_refs': c['dependencies']} for c in sorted(members, key=lambda c: c['rule_id'])]}
                for identity, members in sorted(groups.items())],
            'excluded_catalog_entries': [{'rule_id': c['rule_id'], 'source': c['provenance_group'],
                'reason': c['candidate_use']['inclusion_or_exclusion_reason'],
                'structural_unavailability': c['candidate_use']['structural_unavailability'],
                'core': c['candidate_use']['core'], 'selectable_on_App177': c['candidate_use']['selectable_on_App177'],
                'surfaces': c['observation_surfaces']} for c in assigned if c not in selected],
            'common_measurement_gates_removed': False,
            'candidate_availability_scope': 'saved train-fold support only; outer coverage measures selected model cells'}
    model_rows, selected_rows, support_rows, candidates, traces, inventories = [], [], [], [], [], []
    train_checks, access_checks, runtime_checks, reuse_checks, per_fold = [], [], [], [], []
    models, training_by_job, copy_requests, references = {}, {}, [], []
    metric_checks = 0
    reuse_before = {r['model_unit_id']: r for r in read(out / 'REUSE_BINDINGS_BEFORE.json')['rows']}
    for j in jobs:
        uid, rec = j['model_unit_id'], receipts[j['model_unit_id']]
        dest = dispatch / 'jobs' / uid; reused = bool(j['reuse_model_unit_id'])
        source = Path(before['jobs'][j['reuse_model_unit_id']]['artifact_directory']) if reused else dest
        m, training = read(source / 'model.json'), read(source / 'training.json')
        models[uid], training_by_job[uid] = m, training
        events = read(source / 'access_log.json'); names = [e['event'] for e in events]
        model_receipt = read(source / 'MODEL_FREEZE_RECEIPT.json')
        assert m['model_id'] == rec['model_id'] == model_receipt['model_id']
        assert sha(source / 'model.json') == model_receipt['sha256']
        assert len(m['atoms']) == rec['atoms'] and len(m['clauses']) == rec['clauses']
        assert m['binding']['model_unit_id'] == (j['reuse_model_unit_id'] if reused else uid)
        for key in ('fold_id', 'method_id', 'operating_point', 'source_condition', 'input_view', 'protocol_digest', 'train_membership_digest'):
            assert m['binding'][key] == j[key], (uid, key)
        assert m['binding']['data_origin'] == 'R02_FIXED_CACHE' and m['binding']['split_id'] == 'LOEO-v1'
        assert m['binding']['freeze_manifest_digest'] == prepared['freeze_manifest_digest']
        assert m['binding']['resource_manifest_digest'] == prepared['resource_manifest_digest']
        assert m['fit']['fit_scope'] == 'EXACT_AUTHORIZED_JOB_TRAIN_ONLY' and m['fit']['train_ids'] == j['train_ids']
        if not reused:
            assert m['binding']['authorization_ref'] == str(out / 'R06_APPROVAL.json') + '#' + prepared['approval_digest']
        assert set(j['train_ids']).isdisjoint(j['outer_test_ids'])
        for key in ('bundle_id', 'environment_group_id'):
            assert {metadata[i][key] for i in j['train_ids']}.isdisjoint({metadata[i][key] for i in j['outer_test_ids']})
        for a, b in [('TRAIN_READY', 'TRAIN_TRANSFORM_FINISHED'), ('TRAIN_TRANSFORM_FINISHED', 'MODEL_SAVED_LOADED_FROZEN'),
                     ('MODEL_SAVED_LOADED_FROZEN', 'OPEN_OUTER_TEST_FEATURE'), ('OPEN_OUTER_TEST_FEATURE', 'PREDICTIONS_CLOSED_AND_RECONCILED'),
                     ('PREDICTIONS_CLOSED_AND_RECONCILED', 'OPEN_OUTER_EVALUATION_LABEL')]:
            assert names.index(a) < names.index(b), (uid, a, b)
        for event, ids, prefix in [('OPEN_TRAIN_FEATURE', j['train_ids'], 'data/current/'), ('OPEN_TRAIN_LABEL', j['train_ids'], 'data/evaluation/'),
                                  ('OPEN_OUTER_TEST_FEATURE', j['outer_test_ids'], 'data/current/'), ('OPEN_OUTER_EVALUATION_LABEL', j['outer_test_ids'], 'data/evaluation/')]:
            assert [e['resource'] for e in events if e['event'] == event] == [prefix + i + '.json' for i in ids]
        for op in next(e for e in events if e['event'] == 'TRAIN_TRANSFORM_FINISHED')['access_operations']:
            assert op['partition'] == 'train' and op['ids'] == j['train_ids']
        frozen = next(e for e in events if e['event'] == 'MODEL_SAVED_LOADED_FROZEN')
        assert frozen['sha256'] == model_receipt['sha256']
        assert next(e for e in events if e['event'] == 'TRAIN_READY')['utc'] <= m['fit']['freeze_time'] <= frozen['utc']
        original = lines(source / 'predictions.jsonl')
        assert next(e for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED')['predictions_digest'] == digest(original)
        saved = lines(dest / 'predictions.jsonl')
        assert saved == [r for r in predictions if r['model_unit_id'] == uid]
        context = {k: j[k] for k in (*KEYS, 'model_unit_id', 'fit_job_id', 'fold_id', 'train_membership_digest')}
        context.update(model_id=m['model_id'], reused=reused, executed_model_unit_id=m['binding']['model_unit_id'],
            train_membership_ref='expected_model_units.jsonl#' + uid,
            original_model_ref=str(source / 'model.json'), original_training_ref=str(source / 'training.json'))
        if reused:
            check = reuse_before[uid]
            for name, old in check['files'].items():
                path = source / name
                assert sha(path) == old['sha256'] and path.stat().st_mtime_ns == old['mtime_ns']
            assert m['model_id'] == check['model_id'] and m['fit']['freeze_time'] == check['freeze_time']
            expected_alias = [dict(r, **{k: j[k] for k in KEYS}, model_unit_id=uid,
                executed_model_unit_id=j['reuse_model_unit_id'], reused_from=str(source), executed_binding=copy.deepcopy(m['binding'])) for r in original]
            assert saved == expected_alias
            rr = read(dest / 'REUSE_RECEIPT.json')
            assert rr['original_receipt'] == model_receipt and rr['original_prediction_digest'] == digest(original)
            assert rr['new_fit'] is False and rr['model_bytes_rewritten'] is False
            assert not (dest / 'model.json').exists() and not (dest / 'training.json').exists() and not (dest / 'dispatch_ticket.json').exists()
            reuse_checks.append({**context, 'status': 'PASS', 'receipt': rr, 'prediction_n': len(saved),
                'model_bytes_unchanged': True, 'freeze_time_unchanged': True, 'original_files_mtime_unchanged': True,
                'new_worker': False, 'new_fit': False, 'new_prediction_computation': False})
            references.append((out / 'fold_models' / (uid + '.ref.json'), {**context, 'type': 'EXACT_R05_MODEL_REFERENCE', 'sha256': model_receipt['sha256'], 'freeze_time': m['fit']['freeze_time']}))
            references.append((out / 'training_logs' / (uid + '.ref.json'), {**context, 'type': 'EXACT_R05_TRAINING_REFERENCE', 'sha256': sha(source / 'training.json')}))
        else:
            copy_requests.extend([(source / 'model.json', out / 'fold_models' / (uid + '.json')),
                                  (source / 'training.json', out / 'training_logs' / (uid + '.json'))])
        startup = read(source / 'WORKER_STARTUP.json')
        assert startup['module_root'] == str(freeze / 'snapshot') and startup['python_executable'] == str(freeze / 'dependencies/python/bin/python3.12')
        for name in ('highspy_path', 'numpy_path'):
            assert Path(startup[name]).is_relative_to(freeze / 'dependencies/site-packages')
        assert not list(Path(startup['cwd']).iterdir())
        runtime_checks.append({**context, 'status': 'PASS', 'runtime_origin': 'SAVED_R05_WORKER' if reused else 'NEW_R06_WORKER', **startup})
        access_checks.append({**context, 'status': 'PASS', 'access_origin': 'R05_REUSED_CHAIN' if reused else 'R06_NEW_CHAIN',
            'train_n': len(j['train_ids']), 'test_n': len(j['outer_test_ids']), 'freeze_time': m['fit']['freeze_time'],
            'first_test_feature': next(e['utc'] for e in events if e['event'] == 'OPEN_OUTER_TEST_FEATURE'),
            'prediction_closed': next(e['utc'] for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED'),
            'first_test_label': next(e['utc'] for e in events if e['event'] == 'OPEN_OUTER_EVALUATION_LABEL'), 'log_ref': str(source / 'access_log.json')})
        report = read(source / 'metrics.json')
        indexed = {r['opaque_id']: r for r in saved}
        metric_checks += check_metrics(report['metrics'], indexed, metadata)
        for strata in report['strata'].values():
            for ms in strata.values(): metric_checks += check_metrics(ms, indexed, metadata)
        per_fold.append({**context, 'source_report_ref': str(source / 'metrics.json'), 'report': report})
        condition = registry[j['source_condition']]
        canonical = condition['canonical_atom_ids']
        assert m['view']['input_atom_ids'] == canonical
        expected_clauses = {a + ':' + p for a in canonical for p in ('POSITIVE', 'NEGATIVE')}
        assert set(training['support']) == expected_clauses
        assert {c['clause_id'] for c in training['candidate_manifest']} == expected_clauses
        assert len(training['candidate_manifest']) == 2 * len(canonical) == m['fit']['registered_clause_count']
        assert sum(c['eligible'] for c in training['candidate_manifest']) == m['fit']['candidate_pool_size']
        available = {p: Counter() for p in PHASES}
        for cid, support in training['support'].items():
            assert support['statistics_scope'] == 'TRAIN_FOLD_ONLY' and support['train_ids'] == j['train_ids']
            assert support['triplets'] == len({tuple(t) for t in support['complete_triplet_ids']}) == len(support['complete_triplet_ids'])
            assert support['true_attack_triplets'] == len({tuple(t) for t in support['true_attack_triplet_ids']})
            assert set(map(tuple, support['true_attack_triplet_ids'])) <= set(map(tuple, support['complete_triplet_ids']))
            support_rows.append({**context, 'clause_id': cid, **support})
            if cid.endswith(':POSITIVE'):
                for phase in PHASES: available[phase].update(support['phase_availability'][phase])
        candidates.extend({**context, **c} for c in training['candidate_manifest'])
        traces.extend({**context, 'trace_index': i, **t} for i, t in enumerate(training['trace']))
        for atom in m['atoms']:
            match = next(a for a in condition['canonical_candidates'] if a['atom_id'] == atom['atom_id'])
            assert atom['orientation'] == 'CANONICAL_DEVIATION'
            assert atom['aliases'] == match['allowed_aliases']
            assert set(atom['sources']) <= set(condition['allowed_sources'])
            assert atom['provenance']['contributing_aliases'] == match['contributing_aliases']
        for clause in m['clauses']:
            for literal in clause['literals']:
                atom = next(a for a in m['atoms'] if a['atom_id'] == literal['atom_id'])
                cid = literal['atom_id'] + ':' + literal['polarity']; support = training['support'][cid]
                assert support['eligible'] and support['triplets'] >= search['support']['minimum_available_triplets']
                assert support['true_attack_triplets'] >= search['support']['minimum_true_attack_triplets_per_literal_or_clause']
                assert support['bundles'] >= 1 and support['environments'] >= 1
                selected_rows.append({**context, 'record_type': 'SELECTED_LITERAL', 'clause_id': cid, **literal,
                    'atom': atom, 'support': support})
        if not m['clauses']:
            selected_rows.append({**context, 'record_type': 'EMPTY_MODEL', 'reason': m['fit']['status'], 'model_status': m['status']})
        f, result = m['fit'], m['fit']['training_result']
        states = dict(zip(j['train_ids'], result['states'], strict=True))
        assert f['train_expected_n'] == f['train_consumed_n'] == len(states)
        assert set(states.values()) <= {'T', 'F', 'U', 'EMPTY_MODEL'}
        nclean = sum(metadata[i]['supervised_label'] == 0 for i in states)
        alarms = sum(s == 'T' and metadata[i]['supervised_label'] == 0 for i, s in states.items())
        budget_count = int(Fraction('0.05') * nclean)
        assert f['clean_denominator'] == nclean and f['clean_budget_count'] == budget_count and result['clean_alarms'] == alarms
        coverage = {p: Fraction(sum(s in ('T', 'F') for i, s in states.items() if metadata[i]['phase'] == p),
                    sum(metadata[i]['phase'] == p for i in states)) for p in PHASES}
        assert all(len(c['literals']) == 1 for c in m['clauses'])
        assert sum(len(c['literals']) for c in m['clauses']) <= search['constraints']['max_literals']
        cost = sum(1 + len(c['literals']) for c in m['clauses'])
        n, d = macro(j['train_ids'], metadata, lambda i: states[i] == 'T')
        assert n / d == Fraction(result['macro_tpr']['numerator'], result['macro_tpr']['denominator'])
        objective = n / d - Fraction(str(search['objective']['lambda'])) * cost
        assert objective == Fraction(result['objective']['numerator'], result['objective']['denominator'])
        assert cost == result['complexity'] == m['complexity']['objective_complexity']
        for p, c in coverage.items(): assert c == Fraction(result['coverage'][p]['numerator'], result['coverage'][p]['denominator'])
        feasible = alarms <= budget_count and min(coverage.values()) >= Fraction('0.8') and cost <= 12 and len(m['clauses']) <= 6
        assert feasible == result['feasible']
        if m['status'] == 'FITTED': assert feasible
        if m['status'] == 'EMPTY_MODEL':
            assert not canonical and not training['support'] and f['status'] == 'EMPTY_CANDIDATE_POOL'
            assert not feasible and set(states.values()) == {'EMPTY_MODEL'}
        train_checks.append({**context, 'status': 'PASS', 'model_status': m['status'], 'fit_status': f['status'],
            'train_expected_n': len(states), 'clean_denominator': nclean, 'clean_budget': budget_count, 'clean_alarms': alarms,
            'phase_decision_coverage': {p: float(c) for p, c in coverage.items()}, 'complexity': cost,
            'train_constraints_feasible': feasible, 'macro_tpr': str(n / d), 'objective': str(objective),
            'empty_outcome_is_not_solver_failure': m['status'] == 'EMPTY_MODEL'})
        inventories.append({**context, 'registered_source_catalog_n': condition['registered_source_catalog_n'],
            'raw_core_alias_n': condition['allowed_raw_core_alias_n'], 'canonical_atom_n': len(canonical),
            'registered_literal_n': f['registered_clause_count'], 'eligible_literal_n': f['candidate_pool_size'],
            'model_status': m['status'], 'fit_status': f['status'], 'selected_clause_n': len(m['clauses']),
            'selected_atom_n': len(m['atoms']), 'complexity': cost,
            'train_candidate_availability': {p: {**dict(counts), 'coverage': ratio(counts['defined'], counts['expected'])} for p, counts in available.items()},
            'availability_counting': 'canonical atoms once, POSITIVE support only; not aliases and not both polarities',
            'outcome_category': 'EMPTY_ADMITTED_POOL' if not canonical else 'FITTED_FROM_SUPPORTED_POOL'})
        model_rows.append({**context, 'state': rec['state'], 'model_status': m['status'], 'fit_status': f['status'],
            'train_ids': j['train_ids'], 'outer_test_ids': j['outer_test_ids'], 'model_sha256': model_receipt['sha256'],
            'freeze_time': f['freeze_time'], 'receipt': rec, 'complexity': m['complexity']})
    assert len(copy_requests) == 42 and len(reuse_checks) == 3 and len(models) == 24

    alias_checks = []
    for fold in sorted({j['fold_id'] for j in jobs}):
        by_condition = {j['source_condition']: j['model_unit_id'] for j in jobs if j['fold_id'] == fold}
        shared = set(registry['SRC-001']['canonical_atom_ids']) & set(registry['SRC-100']['canonical_atom_ids'])
        for atom in sorted(shared):
            for polarity in ('POSITIVE', 'NEGATIVE'):
                cid = atom + ':' + polarity
                stats = [training_by_job[by_condition[c]]['support'][cid] for c in ('SRC-001', 'SRC-100', 'SRC-101', 'SRC-111')]
                assert all(s == stats[0] for s in stats[1:])
                alias_checks.append({'fold_id': fold, 'clause_id': cid, 'conditions': ['SRC-001', 'SRC-100', 'SRC-101', 'SRC-111'],
                    'status': 'PASS_IDENTICAL_SUPPORT_NOT_ADDED_PER_ALIAS', 'triplets': stats[0]['triplets'],
                    'true_attack_triplets': stats[0]['true_attack_triplets']})
    metrics_rows, triplets, summaries = [], [], []
    by_condition = {}
    for item in oof:
        group, report = item['group'], item['report']; condition = group['source_condition']
        group_jobs = [j for j in jobs if all(j[k] == v for k, v in group.items())]
        uids = {j['model_unit_id'] for j in group_jobs}
        rows = {r['opaque_id']: r for r in predictions if r['model_unit_id'] in uids}
        by_condition[condition] = rows
        assert len(rows) == report['expected_stage_n'] == 162 and len(group_jobs) == item['expected_fold_n'] == 3
        assert not item['missing_units'] and not item['unavailable_models'] and report['descriptive_n'] == 0
        scopes = [('ALL', 'ALL_EXPECTED', report['metrics'])]
        for dim, strata in report['strata'].items(): scopes.extend((dim, label, ms) for label, ms in strata.items())
        for dimension, label, ms in scopes:
            metric_checks += check_metrics(ms, rows, metadata)
            for name, metric in ms.items():
                source_uids = sorted({rows[i]['model_unit_id'] for i in metric['source_rows']})
                metrics_rows.append({**group, **metric, 'dimension': dimension, 'stratum_label': label, 'metric_id': name,
                    'model_unit_ids': source_uids, 'model_ids': [receipts[u]['model_id'] for u in source_uids],
                    'train_membership_refs': ['expected_model_units.jsonl#' + u for u in source_uids]})
        for t in report['triplet_rows']:
            members = [rows[i] for i in t['source_rows']]; assert len({r['model_unit_id'] for r in members}) == 1
            r = members[0]
            triplets.append({**group, **t, 'aggregate_fold_id': t['fold_id'], 'fold_id': r['fold_id'],
                'model_id': r['model_id'], 'model_unit_id': r['model_unit_id'], 'train_membership_ref': 'expected_model_units.jsonl#' + r['model_unit_id']})
        summary_row = {**group, **{k: registry[condition][k] for k in ('allowed_sources', 'registered_source_catalog_n', 'allowed_raw_core_alias_n', 'canonical_core_atom_n')},
            'new_fit_jobs': sum(not j['reuse_model_unit_id'] for j in group_jobs), 'reused_models': sum(bool(j['reuse_model_unit_id']) for j in group_jobs),
            'model_states': dict(Counter(receipts[j['model_unit_id']]['state'] for j in group_jobs)),
            'selected_rule_ids': sorted({l['atom_id'] + ':' + l['polarity'] for j in group_jobs for c in models[j['model_unit_id']]['clauses'] for l in c['literals']}),
            'complexity_by_fold': {j['fold_id']: models[j['model_unit_id']]['complexity']['objective_complexity'] for j in group_jobs}}
        for name, metric in report['metrics'].items():
            for field in ('numerator', 'denominator', 'expected_denominator', 'value', 'status'):
                summary_row[name + '_' + field] = metric[field]
        summaries.append(summary_row)
    assert len(oof) == len(by_condition) == 8 and len(triplets) == 432
    overlaps, paired, differences, stability = [], [], [], []
    for a, b in combinations(sorted(by_condition), 2):
        ra, rb = registry[a], registry[b]
        raw_a, raw_b = set(ra['raw_alias_ids']), set(rb['raw_alias_ids'])
        canon_a, canon_b = set(ra['canonical_atom_ids']), set(rb['canonical_atom_ids'])
        families_a, families_b = {c['family'] for c in ra['canonical_candidates']}, {c['family'] for c in rb['canonical_candidates']}
        overlaps.append({'source_a': a, 'source_b': b, 'shared_raw_alias_ids': sorted(raw_a & raw_b),
            'shared_canonical_atom_ids': sorted(canon_a & canon_b), 'canonical_jaccard': ratio(len(canon_a & canon_b), len(canon_a | canon_b)),
            'shared_candidate_families': sorted(families_a & families_b), 'family_jaccard': ratio(len(families_a & families_b), len(families_a | families_b))})
        ids = sorted(by_condition[a]); assert set(ids) == set(by_condition[b])
        positive = [i for i in ids if metadata[i]['supervised_label'] == 1]
        alerts_a = {i for i in positive if by_condition[a][i]['decision'] == 'MANIPULATION_ALERT'}
        alerts_b = {i for i in positive if by_condition[b][i]['decision'] == 'MANIPULATION_ALERT'}
        differing = [i for i in ids if by_condition[a][i]['decision'] != by_condition[b][i]['decision']]
        paired.append({'source_a': a, 'source_b': b, 'expected_stage_n': 162, 'attack_n': 54,
            'decision_equal_n': 162 - len(differing), 'different_stage_ids': differing,
            'shared_detected_attack_ids': sorted(alerts_a & alerts_b), 'a_only_attack_ids': sorted(alerts_a - alerts_b),
            'b_only_attack_ids': sorted(alerts_b - alerts_a), 'both_missed_attack_n': 54 - len(alerts_a | alerts_b),
            'a_detected_n': len(alerts_a), 'b_detected_n': len(alerts_b)})
        for oid in differing:
            differences.append({'source_a': a, 'source_b': b, 'opaque_id': oid, 'decision_a': by_condition[a][oid]['decision'],
                'decision_b': by_condition[b][oid]['decision'], 'model_id_a': by_condition[a][oid]['model_id'],
                'model_id_b': by_condition[b][oid]['model_id'], 'fold_id': by_condition[a][oid]['fold_id'],
                'evaluation_sidecar': metadata[oid], 'scope': 'PAIRED_SAVED_OOF_DECISIONS_ONLY'})
    for condition in sorted(by_condition):
        part = [j for j in jobs if j['source_condition'] == condition]
        for a, b in combinations(part, 2):
            ma, mb = models[a['model_unit_id']], models[b['model_unit_id']]
            la = {l['atom_id'] + ':' + l['polarity'] for c in ma['clauses'] for l in c['literals']}
            lb = {l['atom_id'] + ':' + l['polarity'] for c in mb['clauses'] for l in c['literals']}
            stability.append({'source_condition': condition, 'fold_a': a['fold_id'], 'fold_b': b['fold_id'],
                'model_id_a': ma['model_id'], 'model_id_b': mb['model_id'], 'selected_literal_jaccard': ratio(len(la & lb), len(la | lb)),
                'both_empty': not la and not lb, 'same_selected_literals': la == lb,
                'claim_scope': 'Three observed folds; no population stability guarantee.'})
    # Also distinguish selected literal/family overlap from candidate-pool overlap.
    selected_overlap = []
    for fold in sorted({j['fold_id'] for j in jobs}):
        part = [j for j in jobs if j['fold_id'] == fold]
        for a, b in combinations(part, 2):
            ma, mb = models[a['model_unit_id']], models[b['model_unit_id']]
            sets = lambda m: ({l['atom_id'] + ':' + l['polarity'] for c in m['clauses'] for l in c['literals']},
                              {alias for atom in m['atoms'] for alias in atom['aliases']}, {atom['family'] for atom in m['atoms']})
            aa, ab = sets(ma), sets(mb)
            selected_overlap.append({'fold_id': fold, 'source_a': a['source_condition'], 'source_b': b['source_condition'],
                'shared_selected_literals': sorted(aa[0] & ab[0]), 'selected_literal_jaccard': ratio(len(aa[0] & ab[0]), len(aa[0] | ab[0])),
                'shared_selected_aliases': sorted(aa[1] & ab[1]), 'shared_selected_families': sorted(aa[2] & ab[2])})
    exports, events = [], []
    for n, r in enumerate(predictions, 1):
        key = r['model_unit_id'], r['opaque_id']; j = job_index[key[0]]
        assert all(r[k] == j[k] for k in (*KEYS, 'fold_id'))
        assert r['model_id'] == receipts[key[0]]['model_id']
        assert r['selected_atoms_expected'] == receipts[key[0]]['atoms'] and r['clauses_expected'] == receipts[key[0]]['clauses']
        m = models[key[0]]
        if m['status'] == 'EMPTY_MODEL':
            assert r['decision'] == 'EMPTY_MODEL' and r['logical_state'] is None
            assert r['selected_atoms_expected'] == r['clauses_expected'] == 0
        else:
            # Algebra over already-saved explanations only, no feature inference.
            atoms = {e['atom_id']: e['state'] for e in r['atom_explanations']}
            states = []
            for clause, event in zip(m['clauses'], r['clause_explanations'], strict=True):
                literal = clause['literals'][0]
                state = atoms[literal['atom_id']]
                if literal['polarity'] == 'NEGATIVE': state = {'T': 'F', 'F': 'T', 'U': 'U'}[state]
                assert state == event['state']; states.append(state)
            logical = 'T' if 'T' in states else ('F' if all(s == 'F' for s in states) else 'U')
            assert logical == r['logical_state']
            assert r['decision'] == {'T': 'MANIPULATION_ALERT', 'F': 'NO_ALERT', 'U': 'INSUFFICIENT_EVIDENCE'}[logical]
        row = {**r, 'prediction_unit_id': expected[key]['prediction_unit_id'], 'train_membership_ref': 'expected_model_units.jsonl#' + key[0],
            'source_prediction_ref': 'dispatch/predictions.jsonl#line=' + str(n)}
        exports.append(row)
        context = {k: row[k] for k in ('prediction_unit_id', 'model_unit_id', 'model_id', 'opaque_id', 'source_condition', 'fold_id', 'operating_point', 'train_membership_ref')}
        for kind, name in [('ATOM', 'atom_explanations'), ('CLAUSE', 'clause_explanations')]:
            events.extend({**context, 'event_type': kind, **e} for e in r.get(name, []))
    excluded = sorted(set(read(freeze / 'DATA_INDEX.json')) - set(metadata))  # metadata index only.
    assert len(excluded) == 100
    for src, dst in copy_requests:
        dst.parent.mkdir(parents=True, exist_ok=True); assert not dst.exists(); shutil.copy2(src, dst)
    for dst, data in references: write(dst, data)
    jsonl(out / 'MODEL_MANIFEST.jsonl', model_rows)
    jsonl(out / 'selected_rules.jsonl', selected_rows)
    jsonl(out / 'support_statistics.jsonl', support_rows)
    jsonl(out / 'candidate_admission.jsonl', candidates)
    jsonl(out / 'selection_trace.jsonl', traces)
    jsonl(out / 'candidate_inventory.jsonl', inventories)
    jsonl(out / 'per_fold_metrics.jsonl', per_fold)
    jsonl(out / 'oof_predictions.jsonl', exports)
    jsonl(out / 'rule_events.jsonl', events)
    jsonl(out / 'evaluation_sidecar.jsonl', [metadata[i] for i in sorted(metadata)])
    jsonl(out / 'triplet_results.jsonl', triplets)
    jsonl(out / 'failures/failures.jsonl', [r for r in exports if r['decision'] == 'FAILED'])
    jsonl(out / 'failures/abstentions.jsonl', [r for r in exports if r['decision'] in ('EMPTY_MODEL', 'INSUFFICIENT_EVIDENCE')])
    jsonl(out / 'analysis/paired_stage_differences.jsonl', differences)
    write(out / 'SOURCE_CONDITIONS.json', {'bit_order': ['O_u', 'H', 'E'], 'conditions': list(registry.values())})
    write(out / 'metrics.json', oof)
    write(out / 'PAIRWISE_SOURCE_COMPARISON.json', paired)
    write(out / 'CANDIDATE_SOURCE_OVERLAP.json', overlaps)
    write(out / 'SELECTED_RULE_OVERLAP.json', selected_overlap)
    write(out / 'RULE_STABILITY.json', stability)
    csv_file(out / 'source_refit_metrics.csv', summaries)
    csv_file(out / 'metrics.csv', metrics_rows)
    csv_file(out / 'by_configuration.csv', [r for r in metrics_rows if r['dimension'] in ('config', 'config_environment')])
    csv_file(out / 'by_environment.csv', [r for r in metrics_rows if r['dimension'] == 'environment'])
    csv_file(out / 'training_constraints.csv', train_checks)
    csv_file(out / 'candidate_inventory.csv', inventories)
    csv_file(out / 'fold_metrics.csv', [{k: v for k, v in row.items() if k != 'report'} | {'metric_id': name, **m}
        for row in per_fold for name, m in row['report']['metrics'].items()])
    reserved = read(freeze / 'protocol.json')['reserved_nonfit_units']['R06_POSTFIT_DELETE']
    not_run = [{'branch': 'R06_POSTFIT_DELETE', 'model_unit_id': uid, 'removed_source': source,
        'status': 'NOT_RUN', 'reason': 'RESERVED_INTERFACE_NOT_IMPLEMENTED_IN_FROZEN_R04_R1_AND_NOT_AUTHORIZED_THIS_RUN',
        'result': None, 'metric_value': None} for uid in reserved['base_models'] for source in reserved['source_removals']]
    jsonl(out / 'source_drop_sensitivity.jsonl', not_run)
    csv_file(out / 'source_drop_sensitivity.csv', not_run)
    write(out / 'BRANCH_STATUS.json', {'R06_SOURCE_REFIT': {'status': 'COMPLETED_PENDING_EXTERNAL_REVIEW'},
        'R06_POSTFIT_DELETE': {'status': 'NOT_RUN', 'implemented_in_freeze': False, 'authorized_this_run': False,
            'reserved_rows': len(not_run), 'metric_value': None}, 'all_R06_branches_complete': False})
    write(out / 'REUSE_VALIDATION.json', {'status': 'PASS', 'model_n': 3, 'reused_prediction_n': 162, 'new_fits': 0, 'new_predictions': 0, 'rows': reuse_checks})
    write(out / 'ACCESS_ORDER_VALIDATION.json', {'status': 'PASS', 'new_job_chains': 21, 'reused_original_chains': 3, 'rows': access_checks})
    write(out / 'SOURCE_RUNTIME_VALIDATION.json', {'status': 'PASS', 'rows': runtime_checks})
    write(out / 'TRAINING_VALIDATION.json', {'status': 'PASS', 'new_fit_jobs': 21, 'reused_models': 3,
        'rows': train_checks, 'empty_candidate_outcomes_retained_with_feasible_false': sum(not r['train_constraints_feasible'] for r in train_checks)})
    write(out / 'ALIAS_SUPPORT_VALIDATION.json', {'status': 'PASS', 'checked_shared_literal_fold_cases': len(alias_checks), 'rows': alias_checks})
    write(out / 'OOF_ARITHMETIC_VALIDATION.json', {'status': 'PASS', 'groups': 8, 'folds_per_group': 3,
        'independently_checked_metric_cells': metric_checks, 'metric_names': list(expected_metrics([], {}, {}).keys()),
        'scope': 'Saved fold and OOF totals plus every saved stratum; no new transform/fit/prediction.'})
    write(out / 'RECONCILIATION.json', {'status': 'PASS', 'new_fit_jobs': 21, 'model_units': 24, 'reused_models': 3,
        'expected_predictions': 1296, 'saved_predictions': 1296, 'new_prediction_computations': 1134, 'reused_prediction_records': 162,
        'unique_supervised_stages': 162, 'stage_counts': {p: 54 for p in PHASES}, 'excluded_descriptive_ids': excluded,
        'model_states': dict(Counter(r['state'] for r in receipts.values())),
        'prediction_decisions': dict(Counter(r['decision'] for r in predictions)),
        'missing_or_duplicate_units': 0, 'retries': 0})
    write(out / 'BUDGET_AFTER.json', budget)
    write(out / 'BUDGET_VALIDATION.json', {'status': 'PASS', 'prior_fit_jobs': before['used_fit_jobs'], 'new_fit_jobs': 21,
        'cumulative_fit_jobs': budget['used_fit_jobs'], 'prior_charged_seconds': before['charged_seconds'],
        'incremental_charged_seconds': budget['charged_seconds'] - before['charged_seconds'], 'cumulative_charged_seconds': budget['charged_seconds'],
        'all_39_R05_job_records_preserved_exactly': True, 'same_ledger_ref': prepared['budget_ledger_ref'],
        'original_dispatch_SUMMARY_real_fits_is_cumulative': True, 'remaining_fit_jobs': budget['limits']['max_fit_jobs'] - budget['used_fit_jobs'],
        'remaining_seconds': budget['limits']['wall_clock_seconds'] - budget['charged_seconds'], 'reset': False})
    write(out / 'POSTPROCESS_MANIFEST.json', {'status': 'PASS', 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'wall_seconds': time.monotonic() - clock, 'python_executable': sys.executable, 'script': str(Path(__file__).resolve()), 'script_sha256': sha(__file__),
        'input_prediction_sha256': sha(dispatch / 'predictions.jsonl'), 'input_OOF_sha256': sha(dispatch / 'OOF.json'),
        'raw_feature_reads': 0, 'new_fits': 0, 'new_predictions': 0, 'original_artifact_changes': 0,
        'rows': {'models': 24, 'support': len(support_rows), 'candidates': len(candidates), 'traces': len(traces), 'predictions': len(exports),
                 'events': len(events), 'triplets': len(triplets), 'metrics': len(metrics_rows)}})
    print(json.dumps({'status': 'PASS_SAVED_R06_EXPORT', 'new_fit_jobs': 21, 'reused_models': 3,
        'model_units': 24, 'prediction_records': 1296, 'metric_checks': metric_checks, 'additional_fits_or_predictions': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', required=True, type=Path)
    export(parser.parse_args().run)
