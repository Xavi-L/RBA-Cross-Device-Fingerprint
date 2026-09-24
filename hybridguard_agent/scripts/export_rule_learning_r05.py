"""Audit/export closed R05 artifacts using stdlib only. Never fits or predicts.

Run with the frozen interpreter. Model, feature-transform, predictor and solver
modules are deliberately not imported. Source dispatcher outputs are read-only.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def json_lines(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def csv_file(path, data):
    columns = list(dict.fromkeys(k for row in data for k in row))
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in data:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def clause_id(clause):
    return ' & '.join(l['atom_id'] + ':' + l['polarity'] for l in clause['literals'])


def expected_metrics(ids, rows, metadata):
    """Independent arithmetic on saved decisions/counters, never inference."""
    pos = [i for i in ids if metadata[i]['supervised_label'] == 1]
    neg = [i for i in ids if metadata[i]['supervised_label'] == 0]
    phases = {p: [i for i in ids if metadata[i]['phase'] == p] for p in ('attack', 'clean_pre', 'clean_post')}
    alerts = lambda part: sum(rows[i]['decision'] == 'MANIPULATION_ALERT' for i in part)
    decided = lambda part: sum(rows[i]['decision'] in ('MANIPULATION_ALERT', 'NO_ALERT') for i in part)
    result = {'attack_tpr': (alerts(pos), len(pos)), 'clean_alarm_rate': (alerts(neg), len(neg)),
        'pre_alarm_rate': (alerts(phases['clean_pre']), len(phases['clean_pre'])),
        'post_alarm_rate': (alerts(phases['clean_post']), len(phases['clean_post'])),
        'decided_clean_alarm_rate': (alerts(neg), decided(neg)), 'decision_coverage': (decided(ids), len(ids)),
        'abstention_rate': (sum(rows[i]['decision'] in ('EMPTY_MODEL', 'INSUFFICIENT_EVIDENCE') for i in ids), len(ids)),
        'failure_rate': (sum(rows[i]['decision'] == 'FAILED' for i in ids), len(ids))}
    for name, n, d in [('atom_coverage', 'selected_atoms_available', 'selected_atoms_expected'),
                       ('clause_coverage', 'clauses_defined', 'clauses_expected')]:
        result[name] = (None, None) if any(rows[i].get(d) is None for i in ids) else (
            sum(rows[i][n] for i in ids), sum(rows[i][d] for i in ids))
    triads = defaultdict(dict)
    for i in ids:
        m = metadata[i]
        triads[m['bundle_id'], m['triplet_id']][m['phase']] = rows[i]['decision']
    complete = [t for t in triads.values() if set(t) == {'clean_pre', 'attack', 'clean_post'}]
    result['exact_FTF'] = (sum((t['clean_pre'], t['attack'], t['clean_post']) ==
                             ('NO_ALERT', 'MANIPULATION_ALERT', 'NO_ALERT') for t in complete), len(complete))
    return result


def check_metrics(saved, rows, metadata):
    ids = next(iter(saved.values()))['source_rows']
    expected = expected_metrics(ids, rows, metadata)
    for name, (n, d) in expected.items():
        m = saved[name]
        assert m['numerator'] == n and m['denominator'] == d, (name, n, d, m)
        assert m['expected_denominator'] == d
        assert m['value'] == (n / d if d else None)
        assert m['status'] == ('OK' if d else 'NOT_EVALUABLE')
    return len(expected)


def export(out):
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    out = Path(out).resolve()
    prepared, process = read(out / 'RUN_PREPARED.json'), read(out / 'PROCESS_RESULT.json')
    freeze, dispatch = Path(prepared['freeze_directory']), out / 'dispatch'
    assert process['returncode'] == 0 and process['attempt'] == 1 and process['automatic_retries'] == 0
    assert Path(sys.executable).resolve() == freeze / 'dependencies/python/bin/python3.12'
    assert sha(freeze / 'FREEZE_MANIFEST.json') == prepared['freeze_manifest_digest']
    assert sha(freeze / 'RESOURCE_MANIFEST.json') == prepared['resource_manifest_digest']
    assert sha(out / 'R05_APPROVAL.json') == prepared['approval_digest']
    jobs, fits, expected_predictions = (lines(out / n) for n in (
        'expected_model_units.jsonl', 'expected_fit_jobs.jsonl', 'expected_prediction_units.jsonl'))
    expected_job = {j['model_unit_id']: j for j in jobs}
    receipts, predictions, oof = read(dispatch / 'model_receipts.json'), lines(dispatch / 'predictions.jsonl'), read(dispatch / 'OOF.json')
    summary, closure = read(dispatch / 'SUMMARY.json'), read(dispatch / 'PREDICTION_CLOSURE.json')
    assert len(expected_job) == 39 and len(fits) == 27 and len(expected_predictions) == 2106
    assert set(receipts) == set(expected_job)
    wanted = {(r['model_unit_id'], r['opaque_id']): r for r in expected_predictions}
    received = {(r['model_unit_id'], r['opaque_id']): r for r in predictions}
    assert len(wanted) == len(received) == len(predictions) == 2106 and set(wanted) == set(received)
    assert closure['expected'] == closure['saved'] == 2106 and closure['digest'] == digest(predictions)
    ledger = read(prepared['budget_ledger_ref'])
    assert ledger['freeze_digest'] == prepared['freeze_manifest_digest']
    assert ledger['limits'] == read(freeze / 'protocol.json')['budget']
    assert ledger['order'] == prepared['priority_order'] and set(ledger['jobs']) == set(expected_job)
    assert ledger['used_fit_jobs'] == 27 and len(ledger['order']) == 39
    assert summary['jobs'] == 39 and summary['predictions'] == 2106 and summary['real_fits'] == 27
    # Evaluation labels come only from per-job sidecars written after closure.
    metadata, models, logs = {}, {}, {}
    for j in jobs:
        uid = j['model_unit_id']; path = dispatch / 'jobs' / uid
        if (path / 'evaluation_sidecar.json').exists():
            side = read(path / 'evaluation_sidecar.json')
            assert set(side) == set(j['outer_test_ids'])
            for oid, row in side.items():
                assert oid not in metadata or metadata[oid] == row
                metadata[oid] = row
        if (path / 'model.json').exists():
            models[uid], logs[uid] = read(path / 'model.json'), read(path / 'access_log.json')
    assert len(metadata) == 162
    assert Counter(m['phase'] for m in metadata.values()) == {'clean_pre': 54, 'attack': 54, 'clean_post': 54}
    assert all(m['data_role'] == 'SUPERVISED_DEVELOPMENT_BY_FOLD' and m['supervised_label'] == int(m['phase'] == 'attack') for m in metadata.values())
    search = read(freeze / 'snapshot/hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json')
    alphas = {p['id']: Fraction(str(p['alpha'])) for p in search['operating_points']}
    constraints, selected, support_rows, traces, candidates = [], [], [], [], []
    model_rows, source_rows, access_checks, runtime_checks, fold_reports = [], [], [], [], []
    raw_copies, arithmetic_checks = [], 0
    for j in jobs:
        uid, rec = j['model_unit_id'], receipts[j['model_unit_id']]
        path, m = dispatch / 'jobs' / uid, models.get(uid)
        context = {k: j[k] for k in ('model_unit_id', 'fit_job_id', 'fold_id', 'method_id', 'operating_point',
            'source_condition', 'input_view', 'evaluation_track', 'protocol_digest')}
        context.update(model_id=rec.get('model_id'), train_membership_ref='expected_model_units.jsonl#' + uid,
                       train_membership_digest=j['train_membership_digest'])
        model_rows.append({**context, 'state': rec['state'], 'model_status': rec.get('model_status'),
            'train_ids': j['train_ids'], 'outer_test_ids': j['outer_test_ids'], 'receipt': rec,
            'source_model_ref': 'dispatch/jobs/' + uid + '/model.json' if m else None})
        if m is None:
            selected.append({**context, 'record_type': 'NO_SAVED_MODEL', 'state': rec['state']})
            continue
        assert rec['model_id'] == m['model_id'] and rec['atoms'] == len(m['atoms']) and rec['clauses'] == len(m['clauses'])
        for k in ('model_unit_id', 'fit_job_id', 'fold_id', 'method_id', 'operating_point', 'source_condition',
                  'input_view', 'protocol_digest', 'train_membership_digest'):
            assert m['binding'][k] == j[k], (uid, k)
        assert m['binding']['data_origin'] == 'R02_FIXED_CACHE' and m['binding']['split_id'] == 'LOEO-v1'
        assert m['binding']['freeze_manifest_digest'] == prepared['freeze_manifest_digest']
        assert m['binding']['resource_manifest_digest'] == prepared['resource_manifest_digest']
        assert m['binding']['authorization_ref'] == str(out / 'R05_APPROVAL.json') + '#' + prepared['approval_digest']
        assert m['fit']['fit_scope'] == 'EXACT_AUTHORIZED_JOB_TRAIN_ONLY'
        assert m['fit']['train_ids'] == (j['train_ids'] if j['fit_job_id'] else [])
        assert set(j['train_ids']).isdisjoint(j['outer_test_ids'])
        assert {metadata[i]['bundle_id'] for i in j['train_ids']}.isdisjoint({metadata[i]['bundle_id'] for i in j['outer_test_ids']})
        assert {metadata[i]['environment_group_id'] for i in j['train_ids']}.isdisjoint({metadata[i]['environment_group_id'] for i in j['outer_test_ids']})
        events = logs[uid]; names = [e['event'] for e in events]
        for a, b in [('TRAIN_READY', 'TRAIN_TRANSFORM_FINISHED'), ('TRAIN_TRANSFORM_FINISHED', 'MODEL_SAVED_LOADED_FROZEN'),
                     ('MODEL_SAVED_LOADED_FROZEN', 'OPEN_OUTER_TEST_FEATURE'), ('OPEN_OUTER_TEST_FEATURE', 'PREDICTIONS_CLOSED_AND_RECONCILED'),
                     ('PREDICTIONS_CLOSED_AND_RECONCILED', 'OPEN_OUTER_EVALUATION_LABEL')]:
            assert names.index(a) < names.index(b), (uid, a, b)
        for event, ids, prefix in [('OPEN_TRAIN_FEATURE', j['train_ids'], 'data/current/'),
                                   ('OPEN_TRAIN_LABEL', j['train_ids'], 'data/evaluation/'),
                                   ('OPEN_OUTER_TEST_FEATURE', j['outer_test_ids'], 'data/current/'),
                                   ('OPEN_OUTER_EVALUATION_LABEL', j['outer_test_ids'], 'data/evaluation/')]:
            assert [e['resource'] for e in events if e['event'] == event] == [prefix + i + '.json' for i in ids]
        for operation in next(e for e in events if e['event'] == 'TRAIN_TRANSFORM_FINISHED')['access_operations']:
            assert operation['partition'] == 'train' and operation['ids'] == j['train_ids']
        freeze_event = next(e for e in events if e['event'] == 'MODEL_SAVED_LOADED_FROZEN')
        model_receipt = read(path / 'MODEL_FREEZE_RECEIPT.json')
        assert sha(path / 'model.json') == model_receipt['sha256'] == freeze_event['sha256']
        assert model_receipt['model_id'] == m['model_id']
        assert next(e for e in events if e['event'] == 'TRAIN_READY')['utc'] <= m['fit']['freeze_time'] <= freeze_event['utc']
        saved_rows = lines(path / 'predictions.jsonl')
        assert saved_rows == [r for r in predictions if r['model_unit_id'] == uid]
        assert next(e for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED')['predictions_digest'] == digest(saved_rows)
        startup = read(path / 'WORKER_STARTUP.json')
        assert startup['module_root'] == str(freeze / 'snapshot')
        assert startup['python_executable'] == str(freeze / 'dependencies/python/bin/python3.12')
        assert Path(startup['highspy_path']).is_relative_to(freeze / 'dependencies/site-packages')
        assert Path(startup['numpy_path']).is_relative_to(freeze / 'dependencies/site-packages')
        assert startup['freeze_digest'] == prepared['freeze_manifest_digest']
        assert list(Path(startup['cwd']).iterdir()) == []
        access_checks.append({**context, 'status': 'PASS', 'train_n': len(j['train_ids']), 'test_n': len(j['outer_test_ids']),
            'model_freeze_time': m['fit']['freeze_time'], 'first_test_open': next(e['utc'] for e in events if e['event'] == 'OPEN_OUTER_TEST_FEATURE'),
            'prediction_closed': next(e['utc'] for e in events if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED'),
            'first_test_label_open': next(e['utc'] for e in events if e['event'] == 'OPEN_OUTER_EVALUATION_LABEL'),
            'source_log': 'dispatch/jobs/' + uid + '/access_log.json'})
        runtime_checks.append({**context, **startup})
        report = read(path / 'metrics.json'); fold_reports.append({**context, 'report': report})
        row_index = {r['opaque_id']: r for r in saved_rows}
        arithmetic_checks += check_metrics(report['metrics'], row_index, metadata)
        raw_copies.append((path / 'model.json', out / 'fold_models' / (uid + '.json')))
        training = read(path / 'training.json') if (path / 'training.json').exists() else None
        atom_index = {a['atom_id']: a for a in m['atoms']}
        if training:
            raw_copies.append((path / 'training.json', out / 'training_logs' / (uid + '.json')))
            for cid, s in training['support'].items():
                assert s['train_ids'] == j['train_ids'] and s['statistics_scope'] == 'TRAIN_FOLD_ONLY'
                support_rows.append({**context, 'clause_id': cid, **s, 'source_ref': 'dispatch/jobs/' + uid + '/training.json#support'})
            candidates.extend({**context, **c} for c in training['candidate_manifest'])
            traces.extend({**context, 'trace_index': n, **t} for n, t in enumerate(training['trace']))
        for a in m['atoms']:
            source_rows.append({**context, **a})
        for clause in m['clauses']:
            cid = clause_id(clause)
            s = training['support'][cid] if training else None
            if s:
                assert s['eligible'] and s['triplets'] >= search['support']['minimum_available_triplets']
                assert s['true_attack_triplets'] >= search['support']['minimum_true_attack_triplets_per_literal_or_clause']
                assert s['bundles'] >= search['support']['minimum_support_bundles']
                assert s['environments'] >= search['support']['minimum_support_environments']
            for literal in clause['literals']:
                a = atom_index[literal['atom_id']]
                selected.append({**context, 'record_type': 'RULE_LITERAL', 'clause_id': cid, 'atom_id': a['atom_id'],
                    'polarity': literal['polarity'], 'orientation': a['orientation'], 'source_groups': a['sources'],
                    'aliases': a['aliases'], 'provenance': a['provenance'], 'surfaces': a['surfaces'],
                    'train_ids': m['fit']['train_ids'], 'support': s, 'model_status': m['status'], 'fit_status': m['fit']['status']})
        if not m['clauses']:
            selected.append({**context, 'record_type': 'MODEL_WITHOUT_RULES', 'model_status': m['status'],
                             'constant': m['constant'], 'fit_status': m['fit']['status'], 'train_ids': m['fit']['train_ids']})
        if j['fit_job_id']:
            f, states = m['fit'], m['fit']['training_result']['states']
            assert len(states) == len(j['train_ids'])
            phase_states = defaultdict(list)
            for oid, state in zip(j['train_ids'], states, strict=True):
                phase_states[metadata[oid]['phase']].append(state)
            nclean = len(phase_states['clean_pre']) + len(phase_states['clean_post'])
            clean_alerts = sum(s == 'T' for p in ('clean_pre', 'clean_post') for s in phase_states[p])
            budget = int(alphas[j['operating_point']] * nclean)
            coverage = {p: Fraction(sum(s in ('T', 'F') for s in ss), len(ss)) for p, ss in phase_states.items()}
            cost = sum(1 + len(c['literals']) for c in m['clauses'])
            limit = search['constraints']['max_complexity_extension' if j['method_id'] == 'FINITE_IP_DNF2' else 'max_complexity_primary']
            assert budget == f['clean_budget_count'] and nclean == f['clean_denominator']
            assert clean_alerts == f['training_result']['clean_alarms']
            assert cost == f['training_result']['complexity'] == m['complexity']['objective_complexity']
            for p, c in coverage.items():
                assert c == Fraction(f['training_result']['coverage'][p]['numerator'], f['training_result']['coverage'][p]['denominator'])
            satisfied = clean_alerts <= budget and min(coverage.values()) >= Fraction(str(search['constraints']['min_decision_coverage'])) and cost <= limit
            satisfied &= len(m['clauses']) <= search['constraints']['max_clauses'] and sum(len(c['literals']) for c in m['clauses']) <= search['constraints']['max_literals']
            assert m['status'] != 'FITTED' or satisfied and f['training_result']['feasible']
            constraints.append({**context, 'fit_status': f['status'], 'model_status': m['status'], 'train_n': len(j['train_ids']),
                'clean_n': nclean, 'alpha': float(alphas[j['operating_point']]), 'clean_budget': budget, 'clean_alerts': clean_alerts,
                'phase_decision_coverage': {p: float(c) for p, c in coverage.items()}, 'complexity': cost, 'complexity_limit': limit,
                'clauses': len(m['clauses']), 'constraints_satisfied': bool(satisfied), 'solver': f.get('solver'),
                'best_bound': f.get('best_bound'), 'gap': f.get('gap'), 'fit_seconds': f['elapsed_seconds'],
                'rule_ids': f['training_result']['clause_ids'], 'evidence': 'ARITHMETIC_OVER_SAVED_TRAIN_STATES_NO_INFERENCE'})
    assert len(models) == 39 and len(constraints) == 27  # This completed run, not a prerequisite for future success.
    metrics_rows, triplets = [], []
    oof_reconciliation = []
    for group_n, item in enumerate(oof):
        g, report = item['group'], item['report']
        matched = [j for j in jobs if all(j.get(k) == v for k, v in g.items())]
        assert len(matched) == item['expected_fold_n'] == 3
        uids = {j['model_unit_id'] for j in matched}
        group_rows = [r for r in predictions if r['model_unit_id'] in uids]
        rows = {r['opaque_id']: r for r in group_rows}
        assert len(rows) == len(group_rows) == report['expected_stage_n'] == 162
        assert report['supervised_positive_n'] == 54 and report['supervised_negative_n'] == 108 and report['descriptive_n'] == 0
        assert not item['missing_units'] and not item['unavailable_models']
        arithmetic_checks += check_metrics(report['metrics'], rows, metadata)
        scopes = [('ALL', 'ALL_EXPECTED', report['metrics'])]
        for dimension, strata in report['strata'].items():
            for label, ms in strata.items():
                arithmetic_checks += check_metrics(ms, rows, metadata)
                scopes.append((dimension, label, ms))
        for dimension, label, ms in scopes:
            for name, metric in ms.items():
                source_uids = sorted({rows[i]['model_unit_id'] for i in metric['source_rows']})
                metrics_rows.append({**g, **metric, 'metric_id': name, 'dimension': dimension, 'stratum_label': label,
                    'model_unit_ids': source_uids, 'model_ids': [receipts[u]['model_id'] for u in source_uids],
                    'train_membership_refs': ['expected_model_units.jsonl#' + u for u in source_uids],
                    'source_metrics_ref': 'dispatch/OOF.json#group=' + str(group_n)})
        for t in report['triplet_rows']:
            members = [rows[i] for i in t['source_rows']]
            assert len({r['model_unit_id'] for r in members}) == 1
            one = members[0]
            triplets.append({**g, **t, 'aggregate_fold_id': t['fold_id'], 'fold_id': one['fold_id'],
                'model_id': one['model_id'], 'model_unit_id': one['model_unit_id'],
                'train_membership_ref': 'expected_model_units.jsonl#' + one['model_unit_id']})
        oof_reconciliation.append({**g, 'folds': 3, 'stage_n': 162, 'positive_n': 54, 'negative_n': 108,
                                   'missing_units': 0, 'descriptive_n': 0, 'status': 'PASS'})
    assert len(oof) == 13 and len(triplets) == 702
    exports, events = [], []
    for n, r in enumerate(predictions, 1):
        j = expected_job[r['model_unit_id']]; expected = wanted[r['model_unit_id'], r['opaque_id']]
        assert r['model_id'] == receipts[r['model_unit_id']]['model_id']
        assert all(r[k] == expected[k] for k in ('fold_id', 'method_id', 'operating_point', 'source_condition', 'input_view', 'evaluation_track', 'protocol_digest'))
        assert r['selected_atoms_expected'] == receipts[r['model_unit_id']]['atoms']
        assert r['clauses_expected'] == receipts[r['model_unit_id']]['clauses']
        exported = {**r, 'prediction_unit_id': expected['prediction_unit_id'],
                    'train_membership_ref': 'expected_model_units.jsonl#' + r['model_unit_id'],
                    'source_prediction_ref': 'dispatch/predictions.jsonl#line=' + str(n)}
        exports.append(exported)
        ctx = {k: exported[k] for k in ('prediction_unit_id', 'opaque_id', 'model_unit_id', 'model_id', 'fold_id',
            'method_id', 'operating_point', 'source_condition', 'protocol_digest', 'train_membership_ref', 'source_prediction_ref')}
        for kind, key in [('ATOM', 'atom_explanations'), ('CLAUSE', 'clause_explanations')]:
            events.extend({**ctx, 'event_type': kind, **e} for e in r.get(key, []))
    all_data = read(freeze / 'DATA_INDEX.json')  # IDs/resource paths only; no feature decoding.
    excluded = sorted(set(all_data) - set(metadata))
    assert len(excluded) == 100 and set(metadata) == {r['opaque_id'] for r in expected_predictions}
    history = read(freeze / 'HISTORICAL_INPUT_PROOF.json')
    assert all(history[i]['status'] == 'EXACT_INPUT_AND_METHOD_MATCH' for i in metadata)
    saved_history = read(freeze / 'data/historical_predictions.json')
    historical = [r for r in predictions if r['method_id'] == 'HISTORICAL_SEVEN']
    assert all(r['decision'] == saved_history[r['opaque_id']]['risk']['decision'] for r in historical)
    primary = next(o for o in oof if o['group']['method_id'] == 'GREEDY_OR' and o['group']['operating_point'] == 'OP05')
    primary_rows = [r for r in exports if r['method_id'] == 'GREEDY_OR' and r['operating_point'] == 'OP05']
    missed = [{**r, 'evaluation_sidecar': metadata[r['opaque_id']], 'interpretation': 'POST_HOC_MISSED_ATTACK_SAVED_RULE_STATE_ONLY'}
              for r in primary_rows if metadata[r['opaque_id']]['supervised_label'] == 1 and r['decision'] != 'MANIPULATION_ALERT']
    direct_unknown = Counter((e['atom_id'], e.get('reason')) for r in predictions if r['method_id'] == 'DIRECT_CORE_OR'
                             for e in r['atom_explanations'] if e['state'] == 'U')
    for src, dst in raw_copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        assert not dst.exists()
        shutil.copy2(src, dst)
    json_lines(out / 'MODEL_MANIFEST.jsonl', model_rows)
    json_lines(out / 'FIT_RECONCILIATION.jsonl', constraints)
    json_lines(out / 'selected_rules.jsonl', selected)
    json_lines(out / 'rule_sources_aliases.jsonl', source_rows)
    json_lines(out / 'support_statistics.jsonl', support_rows)
    json_lines(out / 'candidate_admission.jsonl', candidates)
    json_lines(out / 'selection_trace.jsonl', traces)
    json_lines(out / 'oof_predictions.jsonl', exports)
    json_lines(out / 'rule_events.jsonl', events)
    json_lines(out / 'evaluation_sidecar.jsonl', [metadata[i] for i in sorted(metadata)])
    json_lines(out / 'failures/failures.jsonl', [r for r in exports if r['decision'] == 'FAILED'])
    json_lines(out / 'failures/abstentions.jsonl', [r for r in exports if r['decision'] in ('EMPTY_MODEL', 'INSUFFICIENT_EVIDENCE')])
    json_lines(out / 'analysis/missed_attacks.jsonl', missed)
    json_lines(out / 'triplet_results.jsonl', triplets)
    json_file(out / 'metrics.json', oof)
    json_lines(out / 'per_fold_metrics.jsonl', fold_reports)
    csv_file(out / 'metrics.csv', metrics_rows)
    csv_file(out / 'by_configuration.csv', [r for r in metrics_rows if r['dimension'] in ('config', 'config_environment')])
    csv_file(out / 'by_environment.csv', [r for r in metrics_rows if r['dimension'] == 'environment'])
    csv_file(out / 'training_constraints.csv', constraints)
    csv_file(out / 'fold_metrics.csv', [{k: v for k, v in f.items() if k != 'report'} | {'metric_id': name, **metric}
                                      for f in fold_reports for name, metric in f['report']['metrics'].items()])
    json_file(out / 'TRAINING_CONSTRAINT_VALIDATION.json', {'status': 'PASS', 'fit_n': len(constraints), 'rows': constraints,
        'validation_basis': 'saved training logical states joined to saved closed evaluation sidecars; arithmetic only',
        'refits': 0, 'new_predictions': 0})
    json_file(out / 'ACCESS_ORDER_VALIDATION.json', {'status': 'PASS', 'job_n': len(access_checks), 'jobs': access_checks})
    json_file(out / 'SOURCE_RUNTIME_VALIDATION.json', {'status': 'PASS', 'job_n': len(runtime_checks), 'jobs': runtime_checks})
    json_file(out / 'OOF_ARITHMETIC_VALIDATION.json', {'status': 'PASS', 'checked_metrics': arithmetic_checks,
        'scope': 'fold totals plus OOF totals and every saved stratum; eleven independently counted metrics', 'groups': oof_reconciliation})
    json_file(out / 'PREDICTION_RECONCILIATION.json', {'status': 'PASS', 'expected_fit': 27, 'fit_receipts': len(constraints),
        'expected_model': 39, 'model_receipts': len(receipts), 'expected_prediction': 2106, 'saved_prediction': len(predictions),
        'unique_supervised_stages': 162, 'positive_stages': 54, 'pre_stages': 54, 'post_stages': 54,
        'missing_or_duplicate_units': 0, 'model_states': dict(Counter(r['state'] for r in receipts.values())),
        'descriptive_stages_excluded': 100, 'descriptive_opaque_ids': excluded,
        'historical_saved_results_exactly_reused': len(historical), 'old_detector_calls': 0})
    json_file(out / 'BUDGET_AFTER.json', ledger)
    json_file(out / 'ANALYSIS_SUMMARY.json', {'primary': primary, 'model_states': dict(Counter(m['status'] for m in models.values())),
        'solver_statuses': dict(Counter(c['fit_status'] for c in constraints)), 'primary_missed_attack_n': len(missed),
        'direct_or_unknown_cells': [{'atom_id': k[0], 'reason': k[1], 'n': n} for k, n in sorted(direct_unknown.items())],
        'learner_clause_signatures': dict(Counter(json.dumps(m['clauses'], sort_keys=True) for u, m in models.items() if expected_job[u]['fit_job_id'])),
        'scientific_scope': 'EXPOSED_RETROSPECTIVE_GROUPED_EVALUATION_NOT_NEW_BLIND_TEST_OR_VERIFIED_MECHANISM_GENERALIZATION'})
    json_file(out / 'POSTPROCESS_MANIFEST.json', {'status': 'PASS', 'script': str(Path(__file__).resolve()), 'script_sha256': sha(__file__),
        'python_executable': sys.executable, 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'wall_seconds': time.monotonic() - clock, 'source_dispatch': str(dispatch), 'source_prediction_digest': sha(dispatch / 'predictions.jsonl'),
        'source_oof_digest': sha(dispatch / 'OOF.json'), 'read_only_saved_artifact_export': True, 'refits': 0, 'new_predictions': 0,
        'rows': {'models': len(model_rows), 'fits': len(constraints), 'selected_rule_records': len(selected),
                 'support_records': len(support_rows), 'candidate_records': len(candidates), 'trace_records': len(traces),
                 'prediction_records': len(exports), 'rule_events': len(events), 'triplets': len(triplets), 'metric_rows': len(metrics_rows)}})
    print(json.dumps({'status': 'PASS_SAVED_R05_AUDIT_EXPORT', 'fit': len(constraints), 'model': len(models),
                      'prediction': len(predictions), 'checked_metrics': arithmetic_checks, 'refits': 0, 'new_predictions': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    export(parser.parse_args().run)
