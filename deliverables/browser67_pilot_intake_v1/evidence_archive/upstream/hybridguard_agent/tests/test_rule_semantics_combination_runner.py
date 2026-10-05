"""Combination-specific runner contracts, using mocked synthetic saved outputs."""
from __future__ import annotations

from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'rsr_combination_runner_test_target', REPO / 'deliverables/rule_semantics_combination/run_experiment.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def folds_for(ids):
    return [{'split_id': 'LOEO-v1', 'fold_id': 'LOEO-v1-0' + str(n + 1),
             'target': 'fixture-env-' + str(n), 'outer_test': ids[n * 54:(n + 1) * 54],
             'train': ids[:n * 54] + ids[(n + 1) * 54:]} for n in range(3)]


def analysis_fixture():
    root = Path('/fixture-combination-no-real-files')
    directory = root / 'output'
    ids = [f'fixture-combination-{n:03}' for n in range(162)]
    folds = folds_for(ids)
    objects, streams, controls, jobs = {}, {}, [], []
    decisions = {
        'BASE': {1: 'MANIPULATION_ALERT', 4: 'FAILED'},
        'LANG_ADD': {1: 'MANIPULATION_ALERT', 2: 'MANIPULATION_ALERT', 3: 'INSUFFICIENT_EVIDENCE'},
        'WD_REPLACE': {2: 'MANIPULATION_ALERT'},
        runner.GROUP: {0: 'MANIPULATION_ALERT', 2: 'MANIPULATION_ALERT'},
    }
    def predictions(group, fold):
        result = []
        for sid in fold['outer_test']:
            n = ids.index(sid)
            decision = decisions[group].get(n, 'NO_ALERT')
            result.append({'opaque_id': sid, 'group_id': group, 'fold_id': fold['fold_id'],
                           'model_id': 'fixture-model-' + group + fold['fold_id'], 'decision': decision,
                           'logical_state': {'MANIPULATION_ALERT': 'T', 'NO_ALERT': 'F',
                                             'INSUFFICIENT_EVIDENCE': 'U', 'FAILED': None}[decision]})
        return result
    for group in runner.CONTROLS:
        for fold in folds:
            ref = 'saved/' + group + '__' + fold['fold_id']
            controls.append({'group_id': group, 'fold_id': fold['fold_id'], 'ref': ref,
                             'train_ids': fold['train'], 'outer_test_ids': fold['outer_test']})
            streams[root / ref / 'predictions.jsonl'] = predictions(group, fold)
    for stage in ('SPARSE', 'RETENTION'):
        for fold in folds:
            jid = stage + '__' + fold['fold_id']
            job = {'job_id': jid, 'stage': stage, 'fold_id': fold['fold_id'],
                   'prediction_ids': [] if stage == 'SPARSE' else fold['outer_test']}
            jobs.append(job)
            dest = directory / 'trials' / jid
            streams[dest / 'predictions.jsonl'] = [] if stage == 'SPARSE' else predictions(runner.GROUP, fold)
            objects[dest / 'receipt.json'] = {'predictions_closed': True}
            objects[dest / 'model.json'] = {'status': 'FITTED', 'complexity': {'clauses': 1},
                'fit': {'training_result': {'clause_ids': ['fixture-literal:POSITIVE']}, 'D_initial': 1, 'D_final': 1}}
            objects[dest / 'training.json'] = {'trace': [], 'candidate_manifest': []}
    objects[directory / 'CONTRACT.json'] = {'sample_ids': ids, 'source_index': 'input/INDEX.json',
                                          'jobs': jobs, 'saved_controls': controls}
    objects[directory / 'EXECUTION.json'] = {'execution_complete': True, 'status': 'SYNTHETIC_COMPLETE'}
    objects[root / 'input/INDEX.json'] = {sid: {'evaluation': 'meta/' + sid + '.json'} for sid in ids}
    for n, sid in enumerate(ids):
        objects[root / 'input/meta' / (sid + '.json')] = {
            'phase': 'attack' if n < 54 else 'clean_pre' if n < 108 else 'clean_post',
            'config_id': 'fixture-config', 'environment_group_id': 'fixture-env'}
    return root, directory, ids, objects, streams


def synthetic_evaluation(ids, rows, metadata, *, evaluation_role):
    assert evaluation_role == runner.ROLE
    assert len(rows) == len(ids) and {r['opaque_id'] for r in rows} == set(ids)
    counts = Counter(row['decision'] for row in rows)
    attacks = [row for row in rows if metadata[row['opaque_id']]['phase'] == 'attack']
    clean = [row for row in rows if metadata[row['opaque_id']]['phase'] != 'attack']
    attack_rate = sum(row['decision'] == 'MANIPULATION_ALERT' for row in attacks) / len(attacks)
    return {'decision_counts': dict(counts), 'metrics': {key: {'value': value} for key, value in {
        'attack_tpr': attack_rate, 'MacroTPR_config_environment': attack_rate,
        'clean_alarm_rate': sum(row['decision'] == 'MANIPULATION_ALERT' for row in clean) / len(clean),
        'decision_coverage': (counts['NO_ALERT'] + counts['MANIPULATION_ALERT']) / len(ids),
        'abstention_rate': counts['INSUFFICIENT_EVIDENCE'] / len(ids),
        'failure_rate': counts['FAILED'] / len(ids),
    }.items()}}


class CombinationRunnerTests(unittest.TestCase):
    def test_prepare_carries_171_budget_and_creates_only_three_sparse_plus_matching_retention_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / 'deliverables/rule_semantics_combination'
            directory.mkdir(parents=True)
            ids = [f'fixture-combination-{n:03}' for n in range(162)]
            folds = folds_for(ids)
            old_jobs = [{'job_id': group + '__' + f['fold_id'], 'group_id': group, 'fold_id': f['fold_id'],
                         'train_ids': f['train'], 'outer_test_ids': f['outer_test']}
                        for group in ('BASE', 'LANG_ADD', 'LANG_REPLACE', 'WD_REPLACE') for f in folds]
            prior = {'sample_ids': ids, 'split_manifest_ref': 'fixture-splits.json', 'jobs': old_jobs,
                     'source_index': 'input/INDEX.json', 'definitions_ref': 'input/definitions.json',
                     'candidate_cache_ref': 'input/candidates.jsonl', 'candidate_cache_offsets': {},
                     'candidate_versions': {'RSR-LANG-FIRST-v1': {'version': '1.0.0'},
                                            'RSR-WEBDRIVER-STATE-v1': {'version': '1.0.0'}},
                     'family_policy': 'SYNTHETIC_UNCHANGED_FAMILY', 'search_space': {}, 'grammar': {}, 'retention': {}}
            objects = {directory / 'TEST_RESULTS.json': {'status': 'PASS', 'exit_code': 0},
                       root / runner.PRIOR / 'CONTRACT.json': prior,
                       root / runner.PRIOR / 'EXECUTION.json': {
                           'execution_complete': True, 'stop_reason': None,
                           'baseline_equivalence': [{'passed': True}] * 3,
                           'remaining_research_fits': 29, 'remaining_research_seconds': 21438.0,
                           'cumulative_fit_jobs': 171, 'cumulative_charged_seconds': 162.0},
                       root / 'fixture-splits.json': {'folds': folds}}
            for job in old_jobs:
                objects[root / runner.PRIOR / 'trials' / job['job_id'] / 'receipt.json'] = {
                    'outcome': 'FITTED', 'predictions_closed': True}
            writes, accesses = [], []
            def read_synthetic(path):
                accesses.append(Path(path))
                return copy.deepcopy(objects[Path(path)])
            with patch.object(runner, 'ROOT', root), \
                 patch.object(runner, '__file__', str(directory / 'run_experiment.py')), \
                 patch.object(runner, 'read', side_effect=read_synthetic), \
                 patch.object(runner, 'write', side_effect=lambda path, obj: writes.append((Path(path), obj))), \
                 patch.object(Path, 'read_bytes', return_value=b'SYNTHETIC_DEPENDENCY'), \
                 patch.object(runner.subprocess, 'check_output', return_value='fixture-head\n'):
                result = runner.prepare(directory)
            self.assertEqual((result['jobs'], result['predictions']), (6, 162))
            self.assertEqual(len(writes), 1)
            registered = writes[0][1]
            self.assertEqual(registered['budget']['base_fit_jobs'], 171)
            self.assertEqual(registered['budget']['max_new_fits'], 6)
            self.assertEqual(registered['budget']['max_sparse_fits'], 3)
            self.assertEqual(registered['budget']['max_retention_fits'], 3)
            self.assertEqual(registered['budget']['prior_ledger_ref'], runner.PRIOR + '/EXECUTION.json')
            self.assertEqual(len(registered['saved_controls']), 9)
            self.assertEqual({x['group_id'] for x in registered['saved_controls']}, set(runner.CONTROLS))
            sparse = {j['fold_id']: j for j in registered['jobs'] if j['stage'] == 'SPARSE'}
            retained = [j for j in registered['jobs'] if j['stage'] == 'RETENTION']
            self.assertEqual(len(sparse), 3)
            self.assertEqual(len(retained), 3)
            for job in sparse.values():
                self.assertEqual(job['prediction_ids'], [])
                self.assertIsNone(job['initial_job_id'])
            for job in retained:
                initial = sparse[job['fold_id']]
                self.assertEqual(job['initial_job_id'], initial['job_id'])
                self.assertEqual(job['train_ids'], initial['train_ids'])
                self.assertEqual(job['prediction_ids'], job['outer_test_ids'])
            self.assertFalse(any('C_confirmation' in str(path) for path in accesses))

    def run_analysis(self, fixture_values):
        root, directory, _, objects, streams = fixture_values
        from hybridguard_agent.research import rule_semantics_combination as engine
        with patch.object(runner, 'ROOT', root), \
             patch.object(runner, 'read', side_effect=lambda path: copy.deepcopy(objects[Path(path)])), \
             patch.object(runner, 'lines', side_effect=lambda path: copy.deepcopy(streams[Path(path)])), \
             patch.object(runner, 'write', side_effect=AssertionError('analysis must not write')), \
             patch.object(engine, 'fit_sparse', side_effect=AssertionError('analysis sparse fit')), \
             patch.object(engine, 'fit_retention', side_effect=AssertionError('analysis retention fit')), \
             patch.object(engine, 'predict_current', side_effect=AssertionError('analysis prediction')), \
             patch('hybridguard_agent.research.rule_learning.evaluation.evaluate', side_effect=synthetic_evaluation):
            return runner.analyze(directory)

    def test_saved_control_comparisons_and_descriptive_interaction_use_correct_ids_and_signs(self):
        values = analysis_fixture()
        ids = values[2]
        for rows in values[4].values():
            for row in rows:
                if row['decision'] in ('FAILED', 'INSUFFICIENT_EVIDENCE'):
                    row.update(decision='NO_ALERT', logical_state='F')
        summary = self.run_analysis(values)
        self.assertEqual(summary['new_prediction_positions'], 162)
        self.assertEqual(summary['reused_control_prediction_positions'], 486)
        self.assertEqual(set(summary['comparisons']), set(runner.CONTROLS))
        comparisons = summary['comparisons']
        self.assertEqual(set(comparisons['BASE']['gained_attack_alert_ids']), {ids[0], ids[2]})
        self.assertEqual(comparisons['BASE']['lost_attack_alert_ids'], [ids[1]])
        self.assertEqual(comparisons['LANG_ADD']['gained_attack_alert_ids'], [ids[0]])
        self.assertEqual(comparisons['LANG_ADD']['lost_attack_alert_ids'], [ids[1]])
        self.assertEqual(comparisons['WD_REPLACE']['gained_attack_alert_ids'], [ids[0]])
        self.assertEqual(comparisons['WD_REPLACE']['lost_attack_alert_ids'], [])
        self.assertAlmostEqual(comparisons['BASE']['metric_delta_percentage_points']['attack_tpr'], 100 / 54)
        self.assertAlmostEqual(comparisons['LANG_ADD']['metric_delta_percentage_points']['attack_tpr'], 0)
        interaction = {r['opaque_id']: r for r in summary['interaction']['rows']}
        self.assertEqual([interaction[ids[n]]['value'] for n in range(3)], [1, 0, -1])
        self.assertAlmostEqual(summary['interaction']['metric_interaction_percentage_points']['attack_tpr'], 0)
        self.assertEqual(summary['interaction']['status'], 'COMPLETE_BINARY_DECISIONS')
        self.assertEqual(summary['interaction']['role'], 'POST_HOC_DESCRIPTIVE_INTERACTION_NO_CAUSAL_CLAIM')

    def test_unknown_or_failed_interaction_stays_null_and_partial_execution_is_rejected(self):
        values = analysis_fixture()
        ids = values[2]
        summary = self.run_analysis(values)
        interaction = {r['opaque_id']: r for r in summary['interaction']['rows']}
        self.assertIsNone(interaction[ids[3]]['value'])
        self.assertEqual(interaction[ids[3]]['decisions']['LANG_ADD'], 'INSUFFICIENT_EVIDENCE')
        self.assertIsNone(interaction[ids[4]]['value'])
        self.assertEqual(interaction[ids[4]]['decisions']['BASE'], 'FAILED')
        self.assertEqual(summary['interaction']['undefined_n'], 2)
        self.assertEqual(summary['interaction']['status'], 'NOT_FULLY_IDENTIFIED')
        self.assertTrue(all(value is None for value in
                            summary['interaction']['metric_interaction_percentage_points'].values()))
        values[3][values[1] / 'EXECUTION.json']['execution_complete'] = False
        with self.assertRaisesRegex(ValueError, 'PARTIAL_EXECUTION_REQUIRES_REVIEW'):
            self.run_analysis(values)

    def test_failed_prediction_or_failed_flush_stops_calls_and_preserves_all_positions(self):
        from hybridguard_agent.research import rule_semantics_combination as engine
        original_open = Path.open
        for fail_flush in (False, True):
            with self.subTest(fail_flush=fail_flush), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                directory = root / 'synthetic-output'
                job = {'job_id': 'RETENTION__fixture-fold', 'stage': 'RETENTION',
                       'method_id': 'R_KEEP_V1', 'fold_id': 'fixture-fold',
                       'initial_job_id': 'SPARSE__fixture-fold', 'train_ids': ['fixture-train'],
                       'prediction_ids': ['fixture-test-0', 'fixture-test-1', 'fixture-test-2']}
                contract = {'jobs': [job], 'source_index': 'inputs/INDEX.json',
                            'candidate_cache_ref': 'inputs/cells.jsonl', 'candidate_cache_offsets': {},
                            'definitions_ref': 'inputs/definitions.json'}
                index = {sid: {'features': sid + '.json', 'evaluation': sid + '.evaluation.json'}
                         for sid in job['train_ids'] + job['prediction_ids']}
                objects = {directory / 'CONTRACT.json': contract, root / 'inputs/INDEX.json': index,
                           root / 'inputs/definitions.json': {},
                           root / 'inputs/fixture-train.evaluation.json': {'phase': 'attack'},
                           directory / 'trials/SPARSE__fixture-fold/training.json': {}}
                for sid in index:
                    objects[root / 'inputs' / (sid + '.json')] = {'features': {'fixture-only': True}}
                fit = {'actual_retention_invocations': 1, 'threshold_fit_calls': 0,
                       'train_ids': job['train_ids']}
                model = SimpleNamespace(model_id='synthetic-retained', status='FITTED', fit=fit,
                    to_dict=lambda: {'model_id': 'synthetic-retained', 'status': 'FITTED', 'fit': fit})
                first = {'opaque_id': job['prediction_ids'][0], 'decision': 'FAILED',
                         'logical_state': None, 'model_id': model.model_id,
                         'failure_reason': 'SYNTHETIC_PREDICT_FAILURE'}
                accesses, flushes = [], []
                def read_synthetic(path):
                    accesses.append(Path(path))
                    return copy.deepcopy(objects[Path(path)])
                class FlushControlledOutput:
                    def __init__(self, stream):
                        self.stream = stream
                        self.pending = ''
                    def __enter__(self):
                        return self
                    def __exit__(self, *unused):
                        self.stream.close()
                    def write(self, value):
                        self.pending += value
                        return len(value)
                    def flush(self):
                        flushes.append(self.pending)
                        if fail_flush:
                            self.pending = ''
                            raise OSError('SYNTHETIC_FLUSH_FAILURE')
                        self.stream.write(self.pending)
                        self.stream.flush()
                        self.pending = ''
                def open_synthetic(path, mode='r', *args, **kwargs):
                    stream = original_open(path, mode, *args, **kwargs)
                    if path.name == 'predictions.jsonl' and mode == 'x':
                        return FlushControlledOutput(stream)
                    return stream
                with patch.object(runner, 'ROOT', root), \
                     patch.object(runner, 'read', side_effect=read_synthetic), \
                     patch.object(runner, 'candidate_subset', side_effect=lambda path, ids, offsets: {sid: {} for sid in ids}), \
                     patch.object(engine, 'fit_retention', return_value=(model, {})) as fit_mock, \
                     patch.object(engine, 'fit_sparse', side_effect=AssertionError('worker sparse fit')), \
                     patch.object(engine, 'load_model', return_value=model), \
                     patch.object(engine, 'save_model', side_effect=lambda current, path: runner.write(path, current.to_dict())), \
                     patch.object(engine, 'predict_current', return_value=first) as predict_mock, \
                     patch.object(Path, 'open', autospec=True, side_effect=open_synthetic):
                    receipt = runner.worker(directory, job['job_id'])
                destination = directory / 'trials' / job['job_id']
                saved = [json.loads(line) for line in (destination / 'predictions.jsonl').read_text().splitlines()]
                self.assertEqual(fit_mock.call_count, 1)
                self.assertEqual(predict_mock.call_count, 1)
                self.assertEqual(len(flushes), 1)
                self.assertEqual(receipt['actual_prediction_calls'], 1)
                self.assertEqual(receipt['outcome'], 'FAILED')
                self.assertEqual(receipt['saved_prediction_positions'], 3)
                self.assertEqual([row['opaque_id'] for row in saved], job['prediction_ids'])
                self.assertTrue(all(row['decision'] == 'FAILED' for row in saved))
                self.assertEqual(saved[0]['model_id'], None if fail_flush else model.model_id)
                self.assertTrue(saved[1]['failure_reason'].startswith('RUNNER:'))
                self.assertNotIn(root / 'inputs/fixture-test-1.json', accesses)
                self.assertFalse(any('fixture-test-' in p.name and '.evaluation' in p.name for p in accesses))


if __name__ == '__main__':
    unittest.main()
