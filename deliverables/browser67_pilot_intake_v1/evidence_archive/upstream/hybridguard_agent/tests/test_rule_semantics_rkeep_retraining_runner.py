"""Three synthetic R_KEEP runner changes; no prior real data or model execution."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.tests.test_rule_semantics_retraining_runner import (
    dump, dump_lines, prediction, saved_candidate_rows,
)

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'rsr_rkeep_runner_test_target', REPO / 'deliverables/rule_semantics_rkeep_retraining/run_experiment.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def baseline_fixture(root):
    directory = root / 'output'
    job = {'job_id': 'BASE__fixture', 'historical_baseline_ref': 'historical', 'outer_test_ids': ['fixture-test']}
    dest = directory / 'trials' / job['job_id']
    old = root / 'historical'
    model = {
        'method_id': 'R_KEEP_V1', 'status': 'FITTED',
        'fit': {'train_ids': ['fixture-train'], 'training_result': {'clause_ids': ['keep:POSITIVE']},
                'D_initial': 1.0, 'D_final': 2.0, 'stop': 'NO_LEGAL_POSITIVE_SIGNAL_INCREMENT',
                'status': 'RETENTION_FEASIBLE'},
        'encoder': {'fixed_atoms': ['keep'], 'numeric': {'source': {
            'thresholds': [1.0], 'atom_ids': ['threshold-1'], 'status': 'FROZEN',
            'train_observed_n': 3, 'train_expected_n': 3, 'surface': 'old-metadata'}}},
        'clauses': [{'literals': [{'atom_id': 'keep', 'polarity': 'POSITIVE'}]}],
    }
    manifest = [{'clause_id': 'keep:POSITIVE', 'eligible': True, 'selected': True,
                 'signal_group': 'fixture-signal', 'reasons': [], 'triplets': 3,
                 'true_attack_triplets': 3, 'bundles': 1, 'environments': 1,
                 'phase_availability': {'clean_pre': {'expected': 3, 'defined': 3}},
                 'singleton_train_clean_alarms': 0}]
    training = {'candidate_manifest': manifest, 'signal_groups': {'keep': 'fixture-signal', 'threshold-1': 'fixture-other'},
                'initial_clause_ids': ['keep:POSITIVE'],
                'trace': [{'operation': 'RETAIN_SIGNAL', 'added': 'threshold-1:POSITIVE', 'delta_D': 1.0}]}
    dump(old / 'model.json', {'schema_version': 'v2-b-model-v1', 'model_id': 'old-wrapper', 'engine_structure': model})
    dump(old / 'training.json', training)
    dump_lines(old / 'predictions.jsonl', [prediction('fixture-test')])
    current = copy.deepcopy(model)
    current['encoder']['numeric']['source']['surface'] = 'app_web67'
    current['binding'] = {'new_version': 'wrapper only'}
    current_training = copy.deepcopy(training)
    current_training['candidate_manifest'][0]['new_diagnostic'] = 'wrapper only'
    dump(dest / 'model.json', current)
    dump(dest / 'training.json', current_training)
    dump_lines(dest / 'predictions.jsonl', [prediction('fixture-test', model='new-wrapper')])
    return directory, job, dest, current, current_training


class RkeepRunnerTests(unittest.TestCase):
    def test_baseline_unwraps_old_engine_structure_and_ignores_only_wrapper_surface(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory, job, _, _, _ = baseline_fixture(root)
            with patch.object(runner, 'ROOT', root):
                result = runner.baseline_check(directory, job)
            self.assertTrue(result['passed'])
            for key in ('method', 'numeric_encoder', 'retention_trace', 'retention_outcome',
                        'candidate_support_and_selection', 'selected_clauses'):
                self.assertTrue(result['checks'][key])

    def test_baseline_rejects_real_threshold_D_trace_or_selected_clause_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory, job, dest, baseline_model, baseline_training = baseline_fixture(root)
            with patch.object(runner, 'ROOT', root):
                for change, expected_check in [
                    ('threshold', 'numeric_encoder'), ('D', 'retention_outcome'),
                    ('trace', 'retention_trace'), ('clause', 'selected_clauses')]:
                    with self.subTest(change=change):
                        model = copy.deepcopy(baseline_model)
                        training = copy.deepcopy(baseline_training)
                        if change == 'threshold': model['encoder']['numeric']['source']['thresholds'] = [1.5]
                        elif change == 'D': model['fit']['D_final'] = 3.0
                        elif change == 'trace': training['trace'][0]['delta_D'] = 0.5
                        else: model['clauses'][0]['literals'][0]['polarity'] = 'NEGATIVE'
                        dump(dest / 'model.json', model)
                        dump(dest / 'training.json', training)
                        result = runner.baseline_check(directory, job)
                        self.assertFalse(result['passed'])
                        self.assertFalse(result['checks'][expected_check])

    def test_prepare_carries_159_fit_budget_and_each_matching_saved_initializer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / 'deliverables/rule_semantics_rkeep_retraining'
            directory.mkdir(parents=True)
            ids = [f'fixture-rkeep-{n:03}' for n in range(162)]
            folds = [{'split_id': 'LOEO-v1', 'fold_id': 'LOEO-v1-0' + str(n + 1),
                      'target': 'fixture-env-' + str(n), 'outer_test': ids[n * 54:(n + 1) * 54],
                      'train': ids[:n * 54] + ids[(n + 1) * 54:]} for n in range(3)]
            jobs = [{'job_id': group + '__' + f['fold_id'], 'group_id': group, 'fold_id': f['fold_id'],
                     'train_ids': f['train'], 'outer_test_ids': f['outer_test']} for group in runner.GROUPS for f in folds]
            budget_path = root / 'deliverables/rule_semantics_retraining/EXECUTION.json'
            objects = {
                directory / 'TEST_RESULTS.json': {'status': 'PASS', 'exit_code': 0},
                root / runner.PRIOR / 'EVALUATION_CONTRACT.json': {'sample_ids': ids, 'authority_ref': 'fixture-authority.json'},
                root / 'fixture-authority.json': {'supervised_ids': ids},
                root / runner.FROZEN / 'SPLIT_MANIFEST.json': {'folds': folds},
                budget_path: {'execution_complete': True, 'stop_reason': None, 'remaining_research_fits': 41,
                              'remaining_research_seconds': 21441.5, 'cumulative_fit_jobs': 159,
                              'cumulative_charged_seconds': 158.5},
                root / runner.INITIAL / 'CONTRACT.json': {'sample_ids': ids, 'selector': 'GREEDY_OR',
                                                        'operating_point': 'OP05', 'jobs': jobs},
                root / 'hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json': {},
                root / 'hybridguard_agent/config/rule_learning_v1_20260924/candidate_grammar.json': {},
            }
            for job in jobs:
                objects[root / runner.INITIAL / 'trials' / job['job_id'] / 'receipt.json'] = {
                    'predictions_closed': True, 'outcome': 'FITTED'}
            accessed, written = [], []
            def read_synthetic(path):
                path = Path(path)
                accessed.append(path)
                return copy.deepcopy(objects[path])
            with patch.object(runner, 'ROOT', root), \
                 patch.object(runner, '__file__', str(directory / 'run_experiment.py')), \
                 patch.object(runner, 'read', side_effect=read_synthetic), \
                 patch.object(runner, 'lines', return_value=saved_candidate_rows(ids)), \
                 patch.object(runner, 'candidate_offsets', return_value={}), \
                 patch.object(runner, 'write', side_effect=lambda path, value: written.append((Path(path), value))), \
                 patch.object(Path, 'read_bytes', return_value=b'SYNTHETIC_DEPENDENCY_CONTENT'), \
                 patch.object(runner.subprocess, 'check_output', return_value='fixture-starting-head\n'):
                result = runner.prepare(directory)
            self.assertEqual(result['jobs'], 12)
            self.assertEqual(len(written), 1)
            registered = written[0][1]
            self.assertEqual(registered['budget']['prior_ledger_ref'], 'deliverables/rule_semantics_retraining/EXECUTION.json')
            self.assertEqual(registered['budget']['base_fit_jobs'], 159)
            self.assertEqual(registered['budget']['base_charged_seconds'], 158.5)
            self.assertEqual(registered['budget']['max_new_fits'], 12)
            self.assertEqual(registered['budget']['new_sparse_fit_calls'], 0)
            self.assertIn(budget_path, accessed)
            self.assertFalse(any('C_confirmation' in str(path) for path in accessed))
            self.assertEqual(registered['selector'], 'R_KEEP_V1')
            for job in registered['jobs']:
                expected = runner.INITIAL + '/trials/' + job['job_id']
                self.assertEqual(job['initial_model_ref'], expected + '/model.json')
                self.assertEqual(job['initial_training_ref'], expected + '/training.json')


if __name__ == '__main__':
    unittest.main()
