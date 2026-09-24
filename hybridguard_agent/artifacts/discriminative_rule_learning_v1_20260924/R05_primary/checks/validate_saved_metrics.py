"""Independent arithmetic over closed R05 outputs; no fit/predictor imports."""
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def macro(ids, metadata, alerted):
    groups = defaultdict(lambda: defaultdict(list))
    for oid in ids:
        m = metadata[oid]
        if m['supervised_label'] == 1:
            groups[m['config_id']][m['environment_group_id']].append(oid)
    numerator = sum((sum((Fraction(sum(alerted(i) for i in rows), len(rows))
        for rows in envs.values()), Fraction()) / len(envs) for envs in groups.values()), Fraction())
    return numerator, len(groups)


def check_extra_metrics(metrics, rows, metadata):
    ids = metrics['attack_tpr']['source_rows']
    n, d = macro(ids, metadata, lambda i: rows[i]['decision'] == 'MANIPULATION_ALERT')
    expected = {'MacroTPR_config_environment': (n, d)}
    triads = defaultdict(dict)
    for oid in ids:
        m = metadata[oid]
        triads[m['bundle_id'], m['triplet_id']][m['phase']] = rows[oid]['decision']
    eligible = [t for t in triads.values() if t.get('attack') == 'MANIPULATION_ALERT' and 'clean_post' in t]
    expected['conditional_recovery'] = (sum(t['clean_post'] == 'NO_ALERT' for t in eligible), len(eligible))
    for name, (n, d) in expected.items():
        m = metrics[name]
        assert abs(m['numerator'] - float(n)) < 1e-12 and m['denominator'] == d
        assert m['expected_denominator'] == d
        assert m['value'] == (float(n / d) if d else None)
        assert m['status'] == ('OK' if d else 'NOT_EVALUABLE')
    return 2


def main():
    out = Path(__file__).resolve().parents[1]
    prepared = read(out / 'RUN_PREPARED.json')
    freeze = Path(prepared['freeze_directory'])
    assert Path(sys.executable).resolve() == freeze / 'dependencies/python/bin/python3.12'
    metadata = {r['opaque_id']: r for r in lines(out / 'evaluation_sidecar.jsonl')}
    predictions = lines(out / 'oof_predictions.jsonl')
    by_job = defaultdict(dict)
    for r in predictions:
        by_job[r['model_unit_id']][r['opaque_id']] = r
    search = read(freeze / 'snapshot/hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json')
    train_checks = []
    for path in sorted((out / 'fold_models').glob('*.json')):
        m = read(path)
        if not m['binding']['fit_job_id']:
            continue
        f = m['fit']; result = f['training_result']; ids = f['train_ids']
        states = dict(zip(ids, result['states'], strict=True))
        assert set(states.values()) <= {'T', 'F', 'U'}
        assert f['train_expected_n'] == f['train_consumed_n'] == len(ids)
        n, d = macro(ids, metadata, lambda i: states[i] == 'T')
        objective = n / d - Fraction(str(search['objective']['lambda'])) * result['complexity']
        assert n / d == Fraction(result['macro_tpr']['numerator'], result['macro_tpr']['denominator'])
        assert objective == Fraction(result['objective']['numerator'], result['objective']['denominator'])
        if f['solver'] == 'HiGHS':
            assert f['gap'] == 0.0 and f['tie_break_complete'] and f['primary_optimal']
            assert abs(f['best_bound'] - float(objective)) < 1e-12
        train_checks.append({'model_unit_id': m['binding']['model_unit_id'], 'model_id': m['model_id'],
            'train_expected': len(ids), 'train_consumed': f['train_consumed_n'], 'execution_failed_states': 0,
            'macro_tpr': str(n / d), 'objective': str(objective), 'candidate_pool_size': f['candidate_pool_size'],
            'registered_clause_count': f['registered_clause_count'], 'status': 'PASS'})
    count = 0
    for item in lines(out / 'per_fold_metrics.jsonl'):
        report, rows = item['report'], by_job[item['model_unit_id']]
        count += check_extra_metrics(report['metrics'], rows, metadata)
        for strata in report['strata'].values():
            for metrics in strata.values():
                count += check_extra_metrics(metrics, rows, metadata)
    for item in read(out / 'metrics.json'):
        group, report = item['group'], item['report']
        rows = {r['opaque_id']: r for r in predictions if all(r.get(k) == v for k, v in group.items())}
        assert len(rows) == 162
        count += check_extra_metrics(report['metrics'], rows, metadata)
        for strata in report['strata'].values():
            for metrics in strata.values():
                count += check_extra_metrics(metrics, rows, metadata)
    # Check stored explanation logic only; never decode or transform original input.
    explanation_n = 0
    for r in predictions:
        if not r.get('clause_explanations'):
            continue
        atoms = {e['atom_id']: e['state'] for e in r['atom_explanations']}
        clauses = []
        for e in r['clause_explanations']:
            states = [atoms[l['atom_id']] if l['polarity'] == 'POSITIVE' else
                {'T': 'F', 'F': 'T', 'U': 'U'}[atoms[l['atom_id']]] for l in e['literals']]
            state = 'F' if 'F' in states else ('T' if all(s == 'T' for s in states) else 'U')
            assert state == e['state']; clauses.append(state)
        state = 'T' if 'T' in clauses else ('F' if all(s == 'F' for s in clauses) else 'U')
        assert state == r['logical_state']
        assert r['decision'] == {'T': 'MANIPULATION_ALERT', 'F': 'NO_ALERT', 'U': 'INSUFFICIENT_EVIDENCE'}[state]
        explanation_n += 1
    result = {'status': 'PASS', 'utc': datetime.now(timezone.utc).isoformat(),
        'python_executable': sys.executable, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'additional_macro_recovery_metrics_checked': count, 'saved_explanation_rows_checked': explanation_n,
        'train_objective_rows_checked': len(train_checks), 'train_rows': train_checks,
        'evidence_scope': 'Closed saved artifacts only; arithmetic/explanation consistency, not predicate re-extraction.',
        'refits': 0, 'new_predictions': 0}
    with (out / 'ADDITIONAL_METRIC_VALIDATION.json').open('x') as f:
        json.dump(result, f, indent=2, ensure_ascii=False); f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'train_rows'}))


if __name__ == '__main__':
    main()
