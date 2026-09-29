"""Synthetic/temp-file runner boundaries; never starts real fit or prediction."""
from __future__ import annotations

from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'rsr_retraining_runner_tests_target', REPO / 'deliverables/rule_semantics_retraining/run_experiment.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def saved_candidate_rows(ids):
    rows = []
    for sid in ids:
        for candidate, mode in runner.CANDIDATES.items():
            rows.append({'opaque_id': sid, 'candidate_id': candidate, 'mode': mode, 'state': 'U',
                         'candidate_invoked': True,
                         'semantic_cell': {'candidate_id': candidate, 'version': '1.0.0',
                            'value': None, 'available': False, 'evaluation_status': 'OK',
                            'reason': 'SYNTHETIC_CACHE_NOT_AN_EXECUTED_CANDIDATE',
                            'source_reason': None, 'diagnostics': {'real_sample': False}}})
    return rows


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def dump_lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


def prediction(sid, group='BASE', fold='fixture-fold', model='fixture-model'):
    return {'opaque_id': sid, 'group_id': group, 'fold_id': fold, 'model_id': model,
            'logical_state': 'F', 'decision': 'NO_ALERT', 'selected_atoms_available': 1,
            'selected_atoms_expected': 1, 'clauses_defined': 1, 'clauses_expected': 1}


def analysis_fixture():
    """162 hand-named positions mirror the fixed runner shape without real rows."""
    root = Path('/fixture-rsr-analysis-no-real-files')
    directory = root / 'output'
    ids = [f'fixture-rsr-analysis-{n:03}' for n in range(162)]
    jobs, objects, streams = [], {}, {}
    index = {sid: {'evaluation': 'meta/' + sid + '.json'} for sid in ids}
    for n, sid in enumerate(ids):
        objects[root / 'input/meta' / (sid + '.json')] = {
            'phase': ('clean_pre', 'attack', 'clean_post')[n % 3],
            'config_id': 'fixture-config', 'environment_group_id': 'fixture-env'}
    manifest = [{'clause_id': 'RSR-LANG-FIRST-v1:POSITIVE', 'eligible': True,
                 'selected': False, 'selection_reasons': ['SYNTHETIC_NOT_SELECTED'],
                 'reasons': [], 'literal_ids': ['RSR-LANG-FIRST-v1:POSITIVE']}]
    for group in runner.GROUPS:
        for fold in range(3):
            fold_id = 'fixture-fold-' + str(fold)
            selected_ids = ids[fold * 54:(fold + 1) * 54]
            job_id = group + '__' + fold_id
            job = {'job_id': job_id, 'group_id': group, 'fold_id': fold_id,
                   'outer_test_ids': selected_ids, 'train_ids': [sid for sid in ids if sid not in selected_ids]}
            jobs.append(job)
            dest = directory / 'trials' / job_id
            streams[dest / 'predictions.jsonl'] = [prediction(sid, group, fold_id, 'fixture-model-' + job_id)
                                                   for sid in selected_ids]
            objects[dest / 'receipt.json'] = {'predictions_closed': True}
            objects[dest / 'model.json'] = {'fit': {'training_result': {'clause_ids': []}},
                                           'complexity': {'clauses': 0}, 'status': 'EMPTY_MODEL'}
            objects[dest / 'training.json'] = {'candidate_manifest': copy.deepcopy(manifest)}
    objects[directory / 'CONTRACT.json'] = {'sample_ids': ids, 'source_index': 'input/INDEX.json', 'jobs': jobs}
    objects[directory / 'EXECUTION.json'] = {'execution_complete': True, 'status': 'SYNTHETIC_COMPLETE'}
    objects[root / 'input/INDEX.json'] = index
    return root, directory, ids, jobs, objects, streams


class RetrainingRunnerTests(unittest.TestCase):
    def test_candidate_cache_rejects_duplicates_missing_cells_and_identity_conflicts(self):
        ids = ['fixture-a', 'fixture-b']
        rows = saved_candidate_rows(ids)
        runner.validate_candidate_cache(rows, ids)
        for bad in [rows + [copy.deepcopy(rows[0])], rows[:-1]]:
            with self.subTest(size=len(bad)), self.assertRaisesRegex(ValueError, 'CANDIDATE_CACHE_SCOPE_CONFLICT'):
                runner.validate_candidate_cache(bad, ids)
        inconsistent = copy.deepcopy(rows)
        inconsistent[0]['state'] = 'F'
        with self.assertRaisesRegex(ValueError, 'CANDIDATE_CACHE_CELL_IDENTITY_CONFLICT'):
            runner.validate_candidate_cache(inconsistent, ids)

    def test_indexed_candidate_subset_reads_only_requested_record_ranges(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic-cache.jsonl'
            dump_lines(path, saved_candidate_rows(['fixture-first', 'fixture-wanted', 'fixture-last']))
            offsets = runner.candidate_offsets(path)
            allowed = {(entry['offset'], entry['length']) for entry in offsets['fixture-wanted']}
            original_open = Path.open
            consumed = []

            class BoundedReader:
                def __init__(self, file): self.file = file
                def __enter__(self): return self
                def __exit__(self, *args): self.file.close()
                def seek(self, offset):
                    if offset not in {pair[0] for pair in allowed}:
                        raise AssertionError('Read sought outside the requested synthetic sample')
                    return self.file.seek(offset)
                def read(self, length):
                    pair = (self.file.tell(), length)
                    if pair not in allowed:
                        raise AssertionError('Unbounded read or another sample was requested')
                    consumed.append(pair)
                    return self.file.read(length)
                def readline(self, *args): raise AssertionError('Subset must not scan every line')

            def open_bounded(file_path, mode='r', *args, **kwargs):
                self.assertEqual(Path(file_path), path)
                self.assertEqual(mode, 'rb')
                return BoundedReader(original_open(file_path, mode, *args, **kwargs))

            with patch.object(Path, 'open', open_bounded), patch.object(runner, 'lines', side_effect=AssertionError('full cache scan')):
                result = runner.candidate_subset(path, ['fixture-wanted'], offsets)
            self.assertEqual(set(result), {'fixture-wanted'})
            self.assertEqual(set(result['fixture-wanted']), set(runner.CANDIDATES))
            self.assertEqual(set(consumed), allowed)
            self.assertEqual(len(consumed), len(allowed))
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_REQUESTED_CANDIDATE_ID'):
                runner.candidate_subset(path, ['fixture-wanted', 'fixture-wanted'], offsets)
            missing = copy.deepcopy(offsets)
            missing['fixture-wanted'] = missing['fixture-wanted'][:1]
            with self.assertRaisesRegex(ValueError, 'EXPECTED_SAVED_CANDIDATE_MISSING'):
                runner.candidate_subset(path, ['fixture-wanted'], missing)
            duplicate = copy.deepcopy(offsets)
            duplicate['fixture-wanted'].append(duplicate['fixture-wanted'][0])
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_OFFSET_IDENTITY_OR_DUPLICATE'):
                runner.candidate_subset(path, ['fixture-wanted'], duplicate)

    def test_baseline_ignores_wrapper_metadata_but_rejects_threshold_and_eligibility_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'output'
            job = {'job_id': 'BASE__fixture', 'historical_baseline_ref': 'historical',
                   'outer_test_ids': ['fixture-test']}
            dest = directory / 'trials' / job['job_id']
            old = root / 'historical'
            numeric = {'numeric-source': {'thresholds': [1.0, 2.0], 'atom_ids': ['n1', 'n2'],
                                         'status': 'FROZEN', 'train_observed_n': 3, 'train_expected_n': 3}}
            model = {'fit': {'train_ids': ['fixture-train'], 'training_result': {'clause_ids': ['keep:POSITIVE']}},
                     'status': 'FITTED', 'encoder': {'fixed_atoms': ['keep'], 'numeric': numeric},
                     'clauses': [{'literals': [{'atom_id': 'keep', 'polarity': 'POSITIVE'}]}]}
            manifest = [{'clause_id': 'keep:POSITIVE', 'eligible': True, 'reasons': [], 'literal_ids': ['keep:POSITIVE']}]
            training = {'candidate_manifest': manifest, 'support': {'keep:POSITIVE': {'triplets': 3}}}
            dump(old / 'model.json', model)
            dump(old / 'training.json', training)
            dump_lines(old / 'predictions.jsonl', [prediction('fixture-test')])
            updated = copy.deepcopy(model)
            updated['encoder']['numeric']['numeric-source']['surface'] = 'app_web67'
            updated['binding'] = {'new_version': 'wrapper only'}
            new_training = copy.deepcopy(training)
            new_training['candidate_manifest'][0].update(selected=True, selection_reasons=[])
            new_training['encoded_atoms'] = [{'atom_id': key} for key in ['keep', 'n1', 'n2']]
            dump(dest / 'model.json', updated)
            dump(dest / 'training.json', new_training)
            dump_lines(dest / 'predictions.jsonl', [prediction('fixture-test', model='new-wrapper-id')])
            with patch.object(runner, 'ROOT', root):
                self.assertTrue(runner.baseline_check(directory, job)['passed'])
                updated['encoder']['numeric']['numeric-source']['thresholds'][0] = 1.5
                dump(dest / 'model.json', updated)
                check = runner.baseline_check(directory, job)
                self.assertFalse(check['passed'])
                self.assertFalse(check['checks']['numeric_encoder'])
                updated['encoder']['numeric']['numeric-source']['thresholds'][0] = 1.0
                dump(dest / 'model.json', updated)
                new_training['candidate_manifest'][0]['eligible'] = False
                dump(dest / 'training.json', new_training)
                check = runner.baseline_check(directory, job)
                self.assertFalse(check['passed'])
                self.assertFalse(check['checks']['candidate_manifest'])

    def test_interrupted_worker_settlement_preserves_full_denominator_counters_and_elapsed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            job = {'job_id': 'LANG_ADD__fixture', 'group_id': 'LANG_ADD', 'fold_id': 'fixture-fold',
                   'outer_test_ids': ['fixture-a', 'fixture-b', 'fixture-c']}
            dest = directory / 'trials' / job['job_id']
            dump(dest / 'FIT_STARTED.json', {'fit_count': 1})
            dump_lines(dest / 'PREDICTION_CALLS.jsonl', [{'opaque_id': sid, 'event': 'PREDICT_INVOKED'}
                                                       for sid in ['fixture-a', 'fixture-b']])
            successful = prediction('fixture-a', group='LANG_ADD')
            dump_lines(dest / 'predictions.jsonl', [successful])
            with (dest / 'predictions.jsonl').open('a') as stream:
                stream.write('{"interrupted":')
            receipt = runner.settle_worker_failure(directory, job, TimeoutError('synthetic timeout'), 12.75)
            self.assertEqual(receipt['outcome'], 'FAILED')
            self.assertEqual(receipt['actual_fit_invocations'], 1)
            self.assertEqual(receipt['actual_prediction_calls'], 2)
            self.assertEqual(receipt['saved_prediction_positions'], 3)
            self.assertEqual(receipt['expected_predictions'], 3)
            self.assertEqual(receipt['charged_seconds'], 12.75)
            self.assertEqual(receipt['malformed_partial_line_count'], 1)
            self.assertEqual(receipt['additional_retries'], 0)
            rows = runner.lines(dest / 'predictions.jsonl')
            self.assertEqual([row['opaque_id'] for row in rows], job['outer_test_ids'])
            self.assertEqual(rows[0], successful)
            self.assertEqual([row['decision'] for row in rows[1:]], ['FAILED', 'FAILED'])
            self.assertTrue((dest / 'predictions.interrupted.jsonl').exists())
            before_start = dict(job, job_id='BASE__never-started', group_id='BASE')
            receipt = runner.settle_worker_failure(directory, before_start, RuntimeError('launch failed'), 0.25)
            self.assertEqual((receipt['actual_fit_invocations'], receipt['actual_prediction_calls']), (0, 0))
            self.assertEqual(receipt['charged_seconds'], 0.25)
            self.assertEqual(receipt['saved_prediction_positions'], 3)
            interrupted = dict(job, job_id='WD_REPLACE__partial-receipt', group_id='WD_REPLACE')
            partial_dest = directory / 'trials' / interrupted['job_id']
            dump(partial_dest / 'FIT_STARTED.json', {'fit_count': 1})
            dump_lines(partial_dest / 'PREDICTION_CALLS.jsonl',
                       [{'opaque_id': 'fixture-a', 'event': 'PREDICT_INVOKED'}])
            with (partial_dest / 'PREDICTION_CALLS.jsonl').open('a') as stream:
                stream.write('{"opaque_id":')
            half_receipt = '{"outcome":'
            (partial_dest / 'receipt.json').write_text(half_receipt)
            receipt = runner.settle_worker_failure(directory, interrupted, TimeoutError('partial writes'), 9.5)
            self.assertIsNone(receipt['actual_prediction_calls'])
            self.assertEqual(receipt['known_prediction_invocation_records'], 1)
            self.assertIs(receipt['prediction_call_count_exact'], False)
            self.assertEqual(receipt['malformed_prediction_call_lines'], ['{"opaque_id":'])
            self.assertEqual(receipt['actual_fit_invocations'], 1)
            self.assertEqual(receipt['saved_prediction_positions'], 3)
            self.assertEqual(receipt['charged_seconds'], 9.5)
            self.assertEqual((partial_dest / 'receipt.interrupted.json').read_text(), half_receipt)
            self.assertEqual(runner.read(partial_dest / 'receipt.json'), receipt)

    def test_analyze_only_reads_saved_outputs_preserves_group_scope_and_selection_diagnostics(self):
        root, directory, ids, jobs, objects, streams = analysis_fixture()
        accesses, evaluations = [], []
        def read_saved(path):
            path = Path(path)
            accesses.append(('read', path))
            return copy.deepcopy(objects[path])
        def read_stream(path):
            path = Path(path)
            accesses.append(('lines', path))
            return copy.deepcopy(streams[path])
        def evaluate_synthetic(expected, rows, metadata, *, evaluation_role):
            self.assertEqual(set(metadata), set(ids))
            self.assertEqual({row['opaque_id'] for row in rows}, set(expected))
            self.assertEqual(evaluation_role, runner.ROLE)
            evaluations.append((list(expected), copy.deepcopy(rows)))
            return {'metrics': {key: {'value': 0.0} for key in (
                'attack_tpr', 'MacroTPR_config_environment', 'clean_alarm_rate',
                'decision_coverage', 'abstention_rate', 'failure_rate')},
                'decision_counts': dict(Counter(row['decision'] for row in rows))}
        from hybridguard_agent.research import rule_semantics_retraining as engine
        with patch.object(runner, 'ROOT', root), patch.object(runner, 'read', side_effect=read_saved), \
             patch.object(runner, 'lines', side_effect=read_stream), \
             patch.object(runner, 'write', side_effect=AssertionError('analysis write')), \
             patch.object(runner, 'write_lines', side_effect=AssertionError('analysis write')), \
             patch.object(runner, 'worker', side_effect=AssertionError('worker invoked')), \
             patch.object(engine, 'fit_group', side_effect=AssertionError('fit invoked')), \
             patch.object(engine, 'predict_current', side_effect=AssertionError('predict invoked')), \
             patch('hybridguard_agent.research.rule_learning.evaluation.evaluate', side_effect=evaluate_synthetic):
            summary = runner.analyze(directory)
        self.assertEqual(set(summary['groups']), set(runner.GROUPS))
        self.assertEqual(len(summary['jobs']), 12)
        self.assertEqual(summary['prediction_positions'], 648)
        self.assertEqual(len(evaluations), 16)
        for group, (expected, rows) in zip(runner.GROUPS, evaluations[:4], strict=True):
            self.assertEqual(expected, ids)
            self.assertEqual(len(rows), 162)
            self.assertEqual({row['group_id'] for row in rows}, {group})
            self.assertEqual({row['model_id'] for row in rows}, {'OOF:' + group})
        for job in summary['jobs']:
            self.assertEqual(job['candidate_selection'][0]['selection_reasons'], ['SYNTHETIC_NOT_SELECTED'])
            self.assertIs(job['candidate_selection'][0]['selected'], False)
        first_metadata = next(n for n, (_, path) in enumerate(accesses) if path.parent.name == 'meta')
        all_predictions = [n for n, (kind, _) in enumerate(accesses) if kind == 'lines']
        self.assertEqual(len(all_predictions), 12)
        self.assertLess(max(all_predictions), first_metadata)

    def test_analysis_rejects_partial_execution_or_missing_prediction_scope(self):
        root, directory, _, jobs, objects, streams = analysis_fixture()
        def read_saved(path): return copy.deepcopy(objects[Path(path)])
        def read_stream(path): return copy.deepcopy(streams[Path(path)])
        with patch.object(runner, 'ROOT', root), patch.object(runner, 'read', side_effect=read_saved), \
             patch.object(runner, 'lines', side_effect=read_stream), \
             patch('hybridguard_agent.research.rule_learning.evaluation.evaluate', side_effect=AssertionError('too early evaluation')):
            objects[directory / 'EXECUTION.json']['execution_complete'] = False
            with self.assertRaisesRegex(ValueError, 'PARTIAL_EXECUTION_REQUIRES_REVIEW'):
                runner.analyze(directory)
            objects[directory / 'EXECUTION.json']['execution_complete'] = True
            streams[directory / 'trials' / jobs[0]['job_id'] / 'predictions.jsonl'].pop()
            with self.assertRaisesRegex(ValueError, 'EXPECTED_PREDICTION_SCOPE_CONFLICT'):
                runner.analyze(directory)


if __name__ == '__main__':
    unittest.main()
