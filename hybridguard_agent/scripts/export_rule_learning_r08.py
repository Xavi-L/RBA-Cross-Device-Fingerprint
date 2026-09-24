"""Audit/export closed R08_CONFIG_TRANSFER artifacts using stdlib only. Never fits or predicts.

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


PHASES = ('clean_pre', 'attack', 'clean_post')


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
    out = Path(out).resolve()
    prepared, process = read(out / 'RUN_PREPARED.json'), read(out / 'PROCESS_RESULT.json')
    freeze, dispatch = Path(prepared['freeze_directory']), out / 'dispatch'
    assert process['returncode'] == 0 and process['attempt'] == 1 and process['automatic_retries'] == 0
    assert Path(sys.executable).resolve() == freeze / 'dependencies/python/bin/python3.12'
    assert sha(freeze / 'FREEZE_MANIFEST.json') == prepared['freeze_manifest_digest']
    assert sha(freeze / 'RESOURCE_MANIFEST.json') == prepared['resource_manifest_digest']
    assert sha(out / 'R08_APPROVAL.json') == prepared['approval_digest']
    jobs, fits, expected_predictions = (lines(out / n) for n in (
        'expected_model_units.jsonl', 'expected_fit_jobs.jsonl', 'expected_prediction_units.jsonl'))
    expected_job = {j['model_unit_id']: j for j in jobs}
    receipts, predictions, oof = read(dispatch / 'model_receipts.json'), lines(dispatch / 'predictions.jsonl'), read(dispatch / 'OOF.json')
    summary, closure = read(dispatch / 'SUMMARY.json'), read(dispatch / 'PREDICTION_CLOSURE.json')
    assert len(expected_job) == 42 and len(fits) == 14 and len(expected_predictions) == 486
    assert set(receipts) == set(expected_job)
    wanted = {(r['model_unit_id'], r['opaque_id']): r for r in expected_predictions}
    received = {(r['model_unit_id'], r['opaque_id']): r for r in predictions}
    assert len(wanted) == len(received) == len(predictions) == 486 and set(wanted) == set(received)
    assert closure['expected'] == closure['saved'] == 486 and closure['digest'] == digest(predictions)
    ledger = read(prepared['budget_ledger_ref'])
    assert ledger['freeze_digest'] == prepared['freeze_manifest_digest']
    assert ledger['limits'] == read(freeze / 'protocol.json')['budget']
    before = read(out / 'BUDGET_BEFORE.json')
    assert ledger['order'] == before['order'] + prepared['priority_order']
    assert set(ledger['jobs']) - set(before['jobs']) == set(expected_job)
    assert all(ledger['jobs'][k] == v for k, v in before['jobs'].items())
    assert ledger['used_fit_jobs'] - before['used_fit_jobs'] == 14 and len(ledger['order']) == 114
    assert summary['jobs'] == 42 and summary['predictions'] == 486 and summary['real_fits'] == ledger['used_fit_jobs'] == 71
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
        assert m['binding']['data_origin'] == 'R02_FIXED_CACHE' and m['binding']['split_id'] == 'LOCO-v1'
        assert m['binding']['freeze_manifest_digest'] == prepared['freeze_manifest_digest']
        assert m['binding']['resource_manifest_digest'] == prepared['resource_manifest_digest']
        assert m['binding']['authorization_ref'] == str(out / 'R08_APPROVAL.json') + '#' + prepared['approval_digest']
        assert m['fit']['fit_scope'] == 'EXACT_AUTHORIZED_JOB_TRAIN_ONLY'
        assert m['fit']['train_ids'] == (j['train_ids'] if j['fit_job_id'] else [])
        assert set(j['train_ids']).isdisjoint(j['outer_test_ids'])
        assert {metadata[i]['bundle_id'] for i in j['train_ids']}.isdisjoint({metadata[i]['bundle_id'] for i in j['outer_test_ids']})
        for field in ('config_id', 'session_id'):
            assert {metadata[i][field] for i in j['train_ids']}.isdisjoint({metadata[i][field] for i in j['outer_test_ids']})
        assert all(metadata[i]['mechanism_id'] is None for i in j['outer_test_ids'])
        assert not m['encoder']  # Frozen core cache; no numeric fitting in this branch.
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
    assert len(models) == 42 and len(constraints) == 14  # This completed run, not a prerequisite for future success.
    metrics_rows, triplets = [], []
    oof_reconciliation = []
    for group_n, item in enumerate(oof):
        g, report = item['group'], item['report']
        matched = [j for j in jobs if all(j.get(k) == v for k, v in g.items())]
        assert len(matched) == item['expected_fold_n'] == 14
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
        oof_reconciliation.append({**g, 'folds': 14, 'stage_n': 162, 'positive_n': 54, 'negative_n': 108,
                                   'missing_units': 0, 'descriptive_n': 0, 'status': 'PASS'})
    assert len(oof) == 3 and len(triplets) == 162
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
        'scope': 'fold totals plus OOF totals and every saved stratum; thirteen independently counted metrics', 'groups': oof_reconciliation})
    json_file(out / 'PREDICTION_RECONCILIATION.json', {'status': 'PASS', 'expected_fit': 14, 'fit_receipts': len(constraints),
        'expected_model': 42, 'model_receipts': len(receipts), 'expected_prediction': 486, 'saved_prediction': len(predictions),
        'unique_supervised_stages': 162, 'positive_stages': 54, 'pre_stages': 54, 'post_stages': 54,
        'missing_or_duplicate_units': 0, 'model_states': dict(Counter(r['state'] for r in receipts.values())),
        'descriptive_stages_excluded': 100, 'descriptive_opaque_ids': excluded,
        'historical_saved_results_exactly_reused': len(historical), 'old_detector_calls': 0})
    json_file(out / 'BUDGET_AFTER.json', ledger)
    json_file(out / 'ANALYSIS_SUMMARY.json', {'primary': primary, 'model_states': dict(Counter(m['status'] for m in models.values())),
        'solver_statuses': dict(Counter(c['fit_status'] for c in constraints)), 'primary_missed_attack_n': len(missed),
        'direct_or_unknown_cells': [{'atom_id': k[0], 'reason': k[1], 'n': n} for k, n in sorted(direct_unknown.items())],
        'learner_clause_signatures': dict(Counter(json.dumps(m['clauses'], sort_keys=True) for u, m in models.items() if expected_job[u]['fit_job_id'])),
        'scientific_scope': 'EXPOSED_CONFIG_TRANSFER_SHARED_ENVIRONMENTS_NOT_INDEPENDENT_ENVIRONMENT_OR_MECHANISM_TEST'})
    extra = export_config_track(out, jobs, models, metadata, predictions, receipts, oof, constraints)
    json_file(out / 'POSTPROCESS_MANIFEST.json', {'status': 'PASS', 'script': str(Path(__file__).resolve()), 'script_sha256': sha(__file__),
        'python_executable': sys.executable, 'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'wall_seconds': time.monotonic() - clock, 'source_dispatch': str(dispatch), 'source_prediction_digest': sha(dispatch / 'predictions.jsonl'),
        'source_oof_digest': sha(dispatch / 'OOF.json'), 'read_only_saved_artifact_export': True, 'refits': 0, 'new_predictions': 0,
        'config_track_checks': extra,
        'rows': {'models': len(model_rows), 'fits': len(constraints), 'selected_rule_records': len(selected),
                 'support_records': len(support_rows), 'candidate_records': len(candidates), 'trace_records': len(traces),
                 'prediction_records': len(exports), 'rule_events': len(events), 'triplets': len(triplets), 'metric_rows': len(metrics_rows)}})
    print(json.dumps({'status': 'PASS_SAVED_R08_CONFIG_AUDIT_EXPORT', 'fit': len(constraints), 'model': len(models),
                      'prediction': len(predictions), 'checked_metrics': arithmetic_checks, 'refits': 0, 'new_predictions': 0}))


def export_config_track(out, jobs, models, metadata, predictions, receipts, oof, constraints):
    """Compare saved tracks without refitting, inference, pooling or selection."""
    prepared = read(out / 'RUN_PREPARED.json')
    freeze, study = Path(prepared['freeze_directory']), out.parent
    frozen_study = freeze / 'snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924'
    frozen_folds = {f['fold_id']: f for f in read(out / 'SPLIT_MEMBERS.json')['folds']}
    all_metadata = {r['opaque_id']: r for r in lines(frozen_study / 'R01_protocol/DATA_ROLE_LEDGER.jsonl')}
    assert all(all_metadata[i] == r for i, r in metadata.items())
    boundary, train_support, config_environment = [], [], []
    for fid, f in sorted(frozen_folds.items()):
        ids = f['train'] + f['outer_test'] + f['descriptive_train_side'] + f['descriptive_test_side']
        assert len(ids) == len(set(ids)) == len(all_metadata) == 262
        side = {i: 'train' for i in f['train'] + f['descriptive_train_side']}
        side.update({i: 'test' for i in f['outer_test'] + f['descriptive_test_side']})
        for key in ('bundle_id', 'session_id', 'triplet_id'):
            groups = defaultdict(set)
            for i in ids:
                if all_metadata[i].get(key) is not None: groups[all_metadata[i][key]].add(side[i])
            assert all(len(s) == 1 for s in groups.values()), (fid, key)
        assert {metadata[i]['config_id'] for i in f['outer_test']} == {f['target']}
        assert f['target'] not in {metadata[i]['config_id'] for i in f['train']}
        assert all(metadata[i]['data_role'] == 'SUPERVISED_DEVELOPMENT_BY_FOLD' for i in f['train'] + f['outer_test'])
        for i in f['descriptive_train_side'] + f['descriptive_test_side']:
            assert all_metadata[i]['supervised_label'] is None and all_metadata[i]['fit_permission'] == 'DENIED'
        train_env = sorted({metadata[i]['environment_group_id'] for i in f['train']})
        test_env = sorted({metadata[i]['environment_group_id'] for i in f['outer_test']})
        shared = sorted(set(train_env) & set(test_env))
        install_shared = sorted({metadata[i]['collector_install_id'] for i in f['train']} &
                                {metadata[i]['collector_install_id'] for i in f['outer_test']})
        boundary.append({'fold_id': fid, 'split_id': 'LOCO-v1', 'held_out_config': f['target'],
            'train_n': len(f['train']), 'test_n': len(f['outer_test']), 'descriptive_n': 100,
            'train_environments': train_env, 'outer_environments': test_env, 'shared_environments': shared,
            'shared_collector_install_ids': install_shared, 'bundle_session_triplet_crossing_n': 0,
            'all_262_partitioned_exactly': True, 'mechanism_id': None, 'mechanism_partition_status': 'UNVERIFIED',
            'R01_related_boundary_preserved': True, 'new_split_or_payload_extraction': False,
            'status': 'PASS_CONFIG_HOLDOUT_WITH_DISCLOSED_SHARED_ENVIRONMENTS'})
        learner = next(j for j in jobs if j['fold_id'] == fid and j['method_id'] == 'GREEDY_OR')
        uid = learner['model_unit_id']; m = models[uid]
        saved_train = read(out / 'dispatch/jobs' / uid / 'training.json')
        support = saved_train['support']
        train_support.append({'fold_id': fid, 'held_out_config': f['target'], 'model_unit_id': uid, 'model_id': m['model_id'],
            'train_ids': f['train'], 'outer_test_ids': f['outer_test'], 'train_membership_digest': learner['train_membership_digest'],
            'train_stage_counts': dict(Counter(metadata[i]['phase'] for i in f['train'])),
            'outer_stage_counts': dict(Counter(metadata[i]['phase'] for i in f['outer_test'])),
            'train_config_n': len({metadata[i]['config_id'] for i in f['train']}), 'train_environments': train_env,
            'shared_environments': shared, 'registered_clauses': len(support),
            'support_eligible_clauses': sum(s['eligible'] for s in support.values()),
            'clean_budget_count': m['fit']['clean_budget_count'], 'clean_train_denominator': m['fit']['clean_denominator'],
            'training_result': m['fit']['training_result'], 'complexity': m['complexity'],
            'selected_clauses': m['clauses'], 'selected_support': {clause_id(c): support[clause_id(c)] for c in m['clauses']},
            'model_ref': 'dispatch/jobs/' + uid + '/model.json', 'support_ref': 'dispatch/jobs/' + uid + '/training.json',
            'statistics_scope': 'SAVED_TRAIN_ONLY_NO_NEW_RULE_RANKING'})
        for partition, members in [('train', f['train']), ('outer_test', f['outer_test'])]:
            groups = defaultdict(list)
            for i in members: groups[metadata[i]['config_id'], metadata[i]['environment_group_id']].append(i)
            for (config, env), group in sorted(groups.items()):
                counts = Counter(metadata[i]['phase'] for i in group)
                config_environment.append({'evaluation_track': 'LOCO-v1', 'fold_id': fid, 'held_out_config': f['target'],
                    'partition': partition, 'config_id': config, 'environment_group_id': env, 'mechanism_id': None,
                    'mechanism_status': 'UNVERIFIED_NOT_INFERRED_FROM_TOOL_CONFIG_OR_FIELD_SET',
                    'stage_n': len(group), 'triplet_n': len({(metadata[i]['bundle_id'], metadata[i]['triplet_id']) for i in group}),
                    'attack_n': counts['attack'], 'clean_pre_n': counts['clean_pre'], 'clean_post_n': counts['clean_post'],
                    'source_rows': group, 'evaluation_sidecar_ref': 'evaluation_sidecar.jsonl'})
    assert len(boundary) == len(train_support) == 14
    # Fixed references are loaded from saved R05 files only, after this R08 run closed.
    reference_jobs = lines(out / 'reference_R05_model_units.jsonl')
    before = read(out / 'BUDGET_BEFORE.json')
    refs, reference_rows, reference_models, reference_checks = [], [], {}, []
    ref_metric_checks = 0
    for j in reference_jobs:
        uid = j['model_unit_id']; src = Path(before['jobs'][uid]['artifact_directory'])
        assert src == study / 'R05_primary/dispatch/jobs' / uid
        m, rec, log = read(src / 'model.json'), read(src / 'MODEL_FREEZE_RECEIPT.json'), read(src / 'access_log.json')
        saved = lines(src / 'predictions.jsonl'); side = read(src / 'evaluation_sidecar.json')
        closed = next(e for e in log if e['event'] == 'PREDICTIONS_CLOSED_AND_RECONCILED')
        assert sha(src / 'model.json') == rec['sha256'] and m['model_id'] == rec['model_id']
        assert closed['predictions_digest'] == digest(saved)
        assert [r['opaque_id'] for r in saved] == j['outer_test_ids']
        assert all(r['model_id'] == m['model_id'] and r['model_unit_id'] == uid for r in saved)
        assert m['binding']['split_id'] == 'LOEO-v1' and m['binding']['data_origin'] == 'R02_FIXED_CACHE'
        assert m['binding']['train_membership_digest'] == j['train_membership_digest']
        assert m['fit']['train_ids'] == (j['train_ids'] if j['fit_job_id'] else [])
        assert all(metadata[i] == side[i] for i in j['outer_test_ids'])
        assert all(set(j['train_ids']) != set(n['train_ids']) for n in jobs)
        assert m['model_id'] not in {n['model_id'] for n in models.values()}
        reference_rows.extend(saved); reference_models[uid] = m
        ref_metric_checks += check_metrics(read(src / 'metrics.json')['metrics'], {r['opaque_id']: r for r in saved}, metadata)
        refs.append({'model_unit_id': uid, 'model_id': m['model_id'], 'fold_id': j['fold_id'], 'split_id': 'LOEO-v1',
            'method_id': j['method_id'], 'operating_point': j['operating_point'], 'source_condition': j['source_condition'],
            'input_view': j['input_view'], 'comparison_role': 'SAVED_SEPARATE_TRACK_REFERENCE_NOT_R08_JOB',
            'train_ids': j['train_ids'], 'outer_test_ids': j['outer_test_ids'], 'train_membership_digest': j['train_membership_digest'],
            'original_model_ref': str(src / 'model.json'), 'original_predictions_ref': str(src / 'predictions.jsonl'),
            'model_sha256': rec['sha256'], 'prediction_sha256': sha(src / 'predictions.jsonl'),
            'model_freeze_time': m['fit']['freeze_time'], 'predictions_closed_at': closed['utc'],
            'new_model_fit': False, 'new_prediction_calls': 0})
        reference_checks.append({'model_unit_id': uid, 'status': 'PASS_SAVED_MODEL_AND_CLOSED_PREDICTION_REFERENCE',
            'model_id_unchanged': True, 'bytes_and_creation_time_unchanged': True, 'LOCO_train_members_differ': True})
    assert len(refs) == 9 and len(reference_rows) == 486
    ref_oof = [g for g in read(study / 'R05_primary/dispatch/OOF.json') if g['group']['method_id'] in ('HISTORICAL_SEVEN','DIRECT_CORE_OR') or
               (g['group']['method_id'] == 'GREEDY_OR' and g['group']['operating_point'] == 'OP05')]
    assert len(ref_oof) == 3
    track_metrics, paired, config_results, comparisons = [], [], [], []
    for g in ref_oof:
        ref_rows = {r['opaque_id']: r for r in reference_rows if r['method_id'] == g['group']['method_id']}
        assert len(ref_rows) == 162 and g['expected_fold_n'] == 3
        ref_metric_checks += check_metrics(g['report']['metrics'], ref_rows, metadata)
        for strata in g['report']['strata'].values():
            for ms in strata.values(): ref_metric_checks += check_metrics(ms, ref_rows, metadata)
    for groups, label in [(oof, 'R08_LOCO_NEW_CONFIG_HOLDOUT'), (ref_oof, 'R05_LOEO_SAVED_ENVIRONMENT_HOLDOUT')]:
        for g in groups:
            for name, metric in g['report']['metrics'].items():
                track_metrics.append({**g['group'], 'comparison_role': label, 'metric_id': name, **metric,
                    'expected_fold_n': g['expected_fold_n'], 'track_not_pooled': True})
    for j in jobs:
        uid = j['model_unit_id']; m = models[uid]; f = frozen_folds[j['fold_id']]
        report = read(out / 'dispatch/jobs' / uid / 'metrics.json')
        config_results.append({'evaluation_track': 'LOCO-v1', 'fold_id': j['fold_id'], 'held_out_config': f['target'],
            'method_id': j['method_id'], 'operating_point': j['operating_point'], 'source_condition': j['source_condition'],
            'input_view': j['input_view'], 'model_unit_id': uid, 'model_id': m['model_id'], 'train_ids': j['train_ids'],
            'outer_test_ids': j['outer_test_ids'], 'train_membership_digest': j['train_membership_digest'],
            'fit_performed': bool(j['fit_job_id']), 'model_state': receipts[uid]['state'], 'complexity': m['complexity'],
            'selected_rules': m['clauses'], 'held_out_metrics': report['metrics'], 'model_ref': 'dispatch/jobs/' + uid + '/model.json'})
    for method in ('GREEDY_OR', 'HISTORICAL_SEVEN', 'DIRECT_CORE_OR'):
        a = {r['opaque_id']: r for r in predictions if r['method_id'] == method}
        b = {r['opaque_id']: r for r in reference_rows if r['method_id'] == method}
        assert set(a) == set(b) == set(metadata) and len(a) == 162
        for oid in sorted(a):
            paired.append({'opaque_id': oid, 'method_id': method, 'config_id': metadata[oid]['config_id'],
                'environment_group_id': metadata[oid]['environment_group_id'], 'phase': metadata[oid]['phase'],
                'LOCO_model_id': a[oid]['model_id'], 'LOCO_model_unit_id': a[oid]['model_unit_id'], 'LOCO_fold_id': a[oid]['fold_id'],
                'LOCO_decision': a[oid]['decision'], 'LOEO_model_id': b[oid]['model_id'], 'LOEO_model_unit_id': b[oid]['model_unit_id'],
                'LOEO_fold_id': b[oid]['fold_id'], 'LOEO_decision': b[oid]['decision'], 'same_decision': a[oid]['decision'] == b[oid]['decision'],
                'comparison_only_not_new_prediction_or_independent_sample': True})
        for config in sorted({m['config_id'] for m in metadata.values()}):
            ids = [i for i in sorted(metadata) if metadata[i]['config_id'] == config]
            ma, mb = expected_metrics(ids, a, metadata), expected_metrics(ids, b, metadata)
            comparisons.append({'config_id': config, 'method_id': method, 'same_expected_stage_ids': True, 'stage_n_per_track': len(ids),
                'LOCO_model_ids': sorted({a[i]['model_id'] for i in ids}), 'LOEO_model_ids': sorted({b[i]['model_id'] for i in ids}),
                'LOCO_fold_ids': sorted({a[i]['fold_id'] for i in ids}), 'LOEO_fold_ids': sorted({b[i]['fold_id'] for i in ids}),
                'LOCO_attack_T_n': ma['attack_tpr'][0], 'LOEO_attack_T_n': mb['attack_tpr'][0], 'attack_n_per_track': ma['attack_tpr'][1],
                'LOCO_exact_FTF_n': ma['exact_FTF'][0], 'LOEO_exact_FTF_n': mb['exact_FTF'][0],
                'same_decision_n': sum(a[i]['decision'] == b[i]['decision'] for i in ids), 'pooled_metric': None,
                'train_members_are_different': True, 'scope': 'CONFIG_TRANSFER_VS_ENVIRONMENT_HOLDOUT_SAVED_COMPARISON'})
    signatures = lambda mm: dict(Counter(clause_id(c) for m in mm for c in m['clauses']))
    learned = [m for m in models.values() if m['method_id'] == 'GREEDY_OR']
    ref_learned = [m for m in reference_models.values() if m['method_id'] == 'GREEDY_OR']
    rule_comparison = {'R08_LOCO_fitted_model_n': len(learned), 'R05_LOEO_saved_model_n': len(ref_learned),
        'R08_LOCO_clause_occurrences': signatures(learned), 'R05_LOEO_clause_occurrences': signatures(ref_learned),
        'all_LOCO_models_new_distinct_ids': len({m['model_id'] for m in learned}) == 14,
        'same_signature_does_not_mean_same_train_members_or_model': True, 'new_reference_fit_or_prediction_calls': 0}
    branch_status = {'R08_CONFIG_TRANSFER': {'status': 'COMPLETED_PENDING_EXTERNAL_REVIEW', 'authorized_this_run': True,
                        'new_fit_jobs': 14, 'model_units': 42, 'prediction_records': 486},
        'R08_MECHANISM': {'status': 'NOT_EVALUABLE_UNVERIFIED_MECHANISM_PARTITION', 'result': None,
                         'mechanism_id': None, 'reason': 'FROZEN_PARTITION_NOT_VERIFIED_NO_TOOL_CONFIG_FIELDSET_PROXY'},
        'R08_PROSPECTIVE': {'status': 'NOT_AVAILABLE', 'result': None, 'reason': 'NO_NEW_INDEPENDENT_UNEXPOSED_MATERIAL'},
        'R07_parent_status': 'PARTIALLY_COMPLETED', 'all_R08_branches_complete': False}
    registry = {'schema_version': 'r08-validation-track-registry-v1', 'protocol_digest': prepared['protocol_digest'],
        'tracks': [
            {'track_id': 'LOCO-v1', 'branch': 'R08_CONFIG_TRANSFER', 'name': '配置留出/配置迁移', 'status': 'COMPLETED_PENDING_EXTERNAL_REVIEW',
             'methods': ['GREEDY_OR/OP05','HISTORICAL_SEVEN','DIRECT_CORE_OR'], 'fold_n': 14, 'new_fit_n': 14,
             'model_n': 42, 'prediction_n': 486, 'unique_stage_n': 162, 'attack_n_per_method': 54,
             'shared_environment_allowed': True, 'independent_environment_claim': False, 'independent_mechanism_claim': False,
             'expected_members_ref': 'expected_model_units.jsonl', 'OOF_ref': 'dispatch/OOF.json'},
            {'track_id': 'LOEO-v1', 'branch': 'R05_PRIMARY', 'name': '环境关联组留出，已保存参照', 'status': 'SAVED_REFERENCE_ONLY',
             'fold_n': 3, 'new_fit_n': 0, 'new_prediction_n': 0, 'saved_reference_model_n': 9, 'saved_reference_prediction_n': 486,
             'unique_stage_n': 162, 'source_ref': str(study/'R05_primary/dispatch/OOF.json'), 'pooled_with_LOCO': False},
            {'branch': 'R08_MECHANISM', **branch_status['R08_MECHANISM']},
            {'branch': 'R08_PROSPECTIVE', **branch_status['R08_PROSPECTIVE']}],
        'independent_samples_across_tracks_or_methods_are_not_additive': True,
        'descriptive_stages_excluded': 100, 'R07_union_36_is_not_an_R08_model': True}
    json_file(out / 'validation_track_registry.json', registry)
    json_file(out / 'BRANCH_STATUS.json', branch_status)
    json_file(out / 'prospective_access_log.json', {'status': 'NOT_AVAILABLE', 'result': None, 'new_material': None,
        'events': [], 'new_final_model': None, 'reason': 'NO_INDEPENDENT_UNEXPOSED_MATERIAL_NO_ACCESS_ATTEMPT'})
    json_file(out / 'SPLIT_BOUNDARY_VALIDATION.json', {'status': 'PASS', 'folds': boundary, 'R01_splits_changed': False,
        'rule_fit_or_predictions_from_this_audit': 0, 'raw_feature_values_read': 0,
        'related_edges_basis': 'Exact frozen members plus all-stage bundle/session/triplet metadata; R01 frozen duplicate/association boundary retained without re-extraction.'})
    csv_file(out / 'fold_boundary_and_support.csv', boundary)
    json_lines(out / 'training_support_table.jsonl', train_support)
    csv_file(out / 'training_support_table.csv', train_support)
    csv_file(out / 'configuration_environment_support.csv', config_environment)
    json_lines(out / 'held_out_configuration_results.jsonl', config_results)
    csv_file(out / 'held_out_configuration_results.csv', config_results)
    json_lines(out / 'REFERENCE_R05_MODEL_MANIFEST.jsonl', refs)
    json_lines(out / 'reference_R05_predictions.jsonl', reference_rows)
    json_file(out / 'reference_R05_metrics.json', ref_oof)
    json_file(out / 'REFERENCE_VALIDATION.json', {'status': 'PASS', 'saved_models': 9, 'saved_predictions': 486,
        'new_reference_fits': 0, 'new_reference_predictions': 0, 'checked_metric_cells': ref_metric_checks, 'rows': reference_checks})
    csv_file(out / 'LOCO_LOEO_track_metrics.csv', track_metrics)
    csv_file(out / 'LOCO_LOEO_configuration_comparison.csv', comparisons)
    json_lines(out / 'LOCO_LOEO_stage_comparison.jsonl', paired)
    json_file(out / 'LOCO_LOEO_rule_comparison.json', rule_comparison)
    budget = read(prepared['budget_ledger_ref'])
    json_file(out / 'BUDGET_VALIDATION.json', {'status': 'PASS', 'same_ledger_ref': prepared['budget_ledger_ref'],
        'prior_fit_jobs': before['used_fit_jobs'], 'new_fit_jobs': budget['used_fit_jobs']-before['used_fit_jobs'],
        'cumulative_fit_jobs': budget['used_fit_jobs'], 'prior_charged_seconds': before['charged_seconds'],
        'incremental_charged_seconds': budget['charged_seconds']-before['charged_seconds'],
        'cumulative_charged_seconds': budget['charged_seconds'], 'remaining_fit_jobs': budget['limits']['max_fit_jobs']-budget['used_fit_jobs'],
        'remaining_seconds': budget['limits']['wall_clock_seconds']-budget['charged_seconds'], 'reset': False, 'synthetic_ledger': False,
        'all_72_prior_job_entries_and_artifact_directories_unchanged': True, 'original_dispatch_real_fits_field_is_cumulative': True})
    return {'config_fold_boundaries': len(boundary), 'saved_reference_models': len(refs), 'saved_reference_predictions': len(reference_rows),
        'reference_metric_cells': ref_metric_checks, 'same_decisions_by_method': dict(Counter(r['method_id'] for r in paired if r['same_decision'])),
        'new_fit_or_prediction_calls': 0, 'new_numeric_thresholds': 0, 'pooled_LOCO_LOEO_metrics': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    export(parser.parse_args().run)
