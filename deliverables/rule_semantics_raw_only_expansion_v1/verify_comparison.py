"""Read saved artifacts to check admission, fold isolation and run accounting."""
import argparse
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def verify(directory, execution=False):
    contract = read(directory / 'CONTRACT.json')
    ids = contract['sample_ids']
    metadata = {i: read(directory / 'evaluation' / f'{i}.json') for i in ids}
    inputs = {i: read(directory / 'inputs' / f'{i}.json') for i in ids}
    effects = read(HERE / 'EFFECT_AUDIT.json')
    assert effects['status'] == 'PRIMARY_EFFECTS_PASS'
    assignments = effects['primary_assignments']
    assert len(assignments) == 42 and all(a['status'] == 'PASS' for a in assignments)
    admitted = [sid for a in assignments for t in a['triplets'] for sid in t['session_ids']]
    assert len(admitted) == len(set(admitted)) == 378
    assert set(ids) == {'rawonly-' + sid for sid in admitted}
    assert Counter(m['phase'] for m in metadata.values()) == dict.fromkeys(('clean_pre', 'attack', 'clean_post'), 126)
    assert sorted(Counter(m['environment_group_id'] for m in metadata.values()).values()) == [126] * 3
    assert sorted(Counter(m['config_id'] for m in metadata.values()).values()) == [27] * 14
    triplets = {}
    for i, meta in metadata.items():
        assert meta['opaque_id'] == inputs[i]['opaque_id'] == i
        assert meta['session_id'] == inputs[i]['session_id'] == i.removeprefix('rawonly-')
        assert meta['source_ref'] == inputs[i]['source_ref']
        assert meta['proposed_supervised_label'] == int(meta['phase'] == 'attack')
        assert meta['fit_permission'] == 'DENIED_PREPARATION_ONLY'
        triplets.setdefault(meta['triplet_id'], []).append(meta['phase'])
    assert len(triplets) == 126 and all(sorted(v) == ['attack', 'clean_post', 'clean_pre'] for v in triplets.values())
    heldout = []
    for fold in contract['folds']:
        train, test = set(fold['train_ids']), set(fold['outer_test_ids'])
        assert len(train) == 252 and len(test) == 126 and not train & test and train | test == set(ids)
        heldout.extend(fold['outer_test_ids'])
        for key in ('environment_group_id', 'bundle_id', 'triplet_id', 'session_id'):
            assert not {metadata[i][key] for i in train} & {metadata[i][key] for i in test}, key
        assert {metadata[i]['environment_group_id'] for i in test} == {fold['heldout_environment']}
    assert Counter(heldout) == Counter(ids)
    roles = read(directory / 'RAW_ROLE_INDEX.json')
    assert len(roles) == len({r['session_id'] for r in roles}) == 456
    assert {r['session_id'] for r in roles if r['role'] == 'PRIMARY_MEMBER'} == set(admitted)
    result = {'status': 'PASS', 'scope': 'Saved-artifact verification; no fit or predict calls',
              'primary_members': 378, 'complete_triplets': 126, 'environment_configuration_assignments': 42,
              'heldout_appearances_per_member': 1, 'cross_fold_environment_bundle_triplet_session_overlap': 0,
              'all_recorded_raw_sessions_accounted': len(roles),
              'process_counts': {k: sum(r[k] for r in effects['runs']) for k in
                                 ('saved', 'raw_saved', 'attempted', 'failed_attempts', 'not_attempted')}}
    if execution:
        saved = read(directory / 'EXECUTION.json')
        assert saved['execution_complete'] and saved['actual_fit_jobs'] == 12
        assert saved['actual_prediction_calls'] == 756
        assert (saved['cumulative_fit_jobs'], saved['remaining_research_fits']) == (189, 11)
        assert len(list((directory / 'trials').glob('*/FIT_STARTED.json'))) == 12
        seen = Counter()
        outcomes = Counter()
        joined = {g: [] for g in ('BASE', 'LANG_ADD_WD_REPLACE')}
        for job in contract['jobs']:
            dest = directory / 'trials' / job['job_id']
            model = read(dest / 'model.json')
            receipt = read(dest / 'receipt.json')
            assert model['fit']['train_ids'] == model['encoder']['train_ids'] == job['train_ids']
            assert model['binding']['experiment_id'] == contract['experiment_id']
            assert model['binding']['group_id'] == job['group_id']
            assert model['fit']['source_mode_manifest']['counts']['legacy_projection_v1'] == 0
            assert receipt['actual_fit_invocations'] == 1
            events = [e['event'] for e in read(dest / 'access_log.json')]
            assert events == ['TRAIN_ONLY_INPUTS_OPENED', 'MODEL_SAVED_RELOADED_FROZEN',
                              'PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN', 'HELDOUT_METADATA_JOINED_AFTER_CLOSE', 'JOB_CLOSED']
            predictions = [json.loads(line) for line in (dest / 'predictions.jsonl').read_text().splitlines()]
            calls = [json.loads(line) for line in (dest / 'PREDICTION_CALLS.jsonl').read_text().splitlines()]
            expected = job['outer_test_ids'] if job['stage'] == 'RETENTION' else []
            assert [r['opaque_id'] for r in predictions] == [r['opaque_id'] for r in calls] == expected
            assert len(expected) == receipt['actual_prediction_calls']
            evaluation = read(dest / 'evaluation_rows.json')
            assert [r['opaque_id'] for r in evaluation] == expected
            for predicted, row in zip(predictions, evaluation, strict=True):
                assert predicted['decision'] == row['decision']
                meta = metadata[row['opaque_id']]
                assert row['supervised_label'] == meta['proposed_supervised_label']
                assert all(row[key] == meta[key] for key in
                           ('phase', 'config_id', 'environment_group_id', 'bundle_id', 'triplet_id'))
            joined[job['group_id']].extend(evaluation)
            seen.update((job['group_id'], i) for i in expected)
            outcomes.update([receipt['outcome']])
        assert seen == Counter((g, i) for g in ('BASE', 'LANG_ADD_WD_REPLACE') for i in ids)
        reported = read(directory / 'RESULTS.json')
        for group, rows in joined.items():
            summary = reported['groups'][group]
            attack = [r for r in rows if r['phase'] == 'attack']
            clean = [r for r in rows if r['phase'] != 'attack']
            alerts = sum(r['decision'] == 'MANIPULATION_ALERT' for r in attack)
            assert summary['attack_alerts'] == alerts and summary['attack_n'] == len(attack) == 126
            assert summary['clean_alerts'] == sum(r['decision'] == 'MANIPULATION_ALERT' for r in clean)
            assert summary['clean_n'] == len(clean) == 252
            assert summary['decisions'] == dict(Counter(r['decision'] for r in rows))
            assert summary['tpr'] == alerts / 126
            for config, counts in summary['configurations'].items():
                current = [r for r in attack if r['config_id'] == config]
                assert counts == {'alerts': sum(r['decision'] == 'MANIPULATION_ALERT' for r in current), 'n': len(current)}
        result.update(actual_fit_calls=12, actual_prediction_calls=756, outcomes=dict(outcomes),
                      cumulative_fit_jobs=189, remaining_fits=11, access_order_verified=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execution', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(HERE / 'prepared', args.execution)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        with args.output.open('x') as stream:
            stream.write(encoded)
    print(encoded)
