"""Execution boundaries with synthetic members and a fake engine; no real fit."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('raw_comparison_test', Path(__file__).with_name('run_comparison.py'))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ComparisonBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'prepared'
        self.directory.mkdir()
        ids = [f'synthetic-{i:03}' for i in range(378)]
        folds = []
        jobs = []
        for n in range(3):
            test = ids[n * 126:(n + 1) * 126]
            fold = {'fold_id': str(n), 'train_ids': sorted(set(ids) - set(test)), 'outer_test_ids': test}
            folds.append(fold)
            for group in runner.GROUPS:
                initial = f'{group}-{n}-SPARSE'
                for stage in ('SPARSE', 'RETENTION'):
                    jobs.append({**fold, 'job_id': f'{group}-{n}-{stage}', 'group_id': group,
                                 'stage': stage, 'initializer': initial,
                                 'max_prediction_calls': 126 if stage == 'RETENTION' else 0})
        self.contract = {'readiness': 'RAW_ONLY_COMPARISON_READY', 'experiment_id': 'synthetic-only',
                         'sample_ids': ids, 'jobs': jobs, 'folds': folds,
                         'source_modes': dict.fromkeys(ids, 'raw_observation_v1'),
                         'engine_study_version': 'synthetic-only', 'engine_phase': 'synthetic-only',
                         'evaluation_role': 'TEST_FIXTURE'}
        self.grant = {'training_authorized': True, 'admission_authorized': True,
                      'experiment_id': 'synthetic-only', 'sample_ids': ids,
                      'job_ids': [j['job_id'] for j in jobs], 'authorization_ref': 'TEST_ONLY_FAKE_ENGINE'}
        self.put(self.directory / 'CONTRACT.json', self.contract)
        self.put(self.root / 'EXECUTION_AUTHORIZATION.json', self.grant)
        self.put(self.root / 'EFFECT_AUDIT.json', {'status': 'PRIMARY_EFFECTS_PASS'})
        self.put(self.root / 'deliverables/rule_semantics_combination/EXECUTION.json',
                 {'cumulative_fit_jobs': 177, 'remaining_research_fits': 23})
        for name in ('ROOT', 'HERE'):
            p = patch.object(runner, name, self.root)
            p.start()
            self.addCleanup(p.stop)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_readiness_authorization_and_budget_are_required(self):
        runner.gate(self.directory)
        for field, value, expected in [('training_authorized', False, 'EXPLICIT_USER'),
                                       ('sample_ids', [], 'MEMBERSHIP_MISMATCH')]:
            self.put(self.root / 'EXECUTION_AUTHORIZATION.json', {**self.grant, field: value})
            with self.assertRaisesRegex(ValueError, expected):
                runner.gate(self.directory)
        self.put(self.root / 'EXECUTION_AUTHORIZATION.json', self.grant)
        self.put(self.root / 'deliverables/rule_semantics_combination/EXECUTION.json',
                 {'cumulative_fit_jobs': 178, 'remaining_research_fits': 22})
        with self.assertRaisesRegex(ValueError, 'BUDGET_CHANGED'):
            runner.gate(self.directory)

    def test_train_test_overlap_and_legacy_input_are_rejected(self):
        bad = deepcopy(self.contract)
        bad['jobs'][0]['train_ids'][0] = bad['jobs'][0]['outer_test_ids'][0]
        self.put(self.directory / 'CONTRACT.json', bad)
        with self.assertRaisesRegex(ValueError, 'INVALID_OUTER_SPLIT'):
            runner.gate(self.directory)
        bad = deepcopy(self.contract)
        bad['source_modes'][bad['sample_ids'][0]] = 'legacy_projection_v1'
        self.put(self.directory / 'CONTRACT.json', bad)
        with self.assertRaisesRegex(ValueError, 'RAW_ONLY'):
            runner.gate(self.directory)

    def fake_worker(self, fail=False):
        from hybridguard_agent.research import rule_semantics_mixed_retraining as engine
        job = self.contract['jobs'][1]
        model = SimpleNamespace(fit={'train_ids': job['train_ids']}, status='FITTED', model_id='fake')
        self.put(self.directory / 'RUN_STARTED.json', {})
        self.put(self.directory / 'DEFINITIONS.json', {})
        initial = self.directory / 'trials' / job['initializer']
        self.put(initial / 'receipt.json', {'outcome': 'FITTED'})
        self.put(initial / 'training.json', {})
        for n, oid in enumerate(self.contract['sample_ids']):
            self.put(self.directory / 'inputs' / f'{oid}.json',
                     {'opaque_id': oid, 'observation_mode': 'raw_observation_v1', 'features': {}, 'candidate_cells': {}})
            self.put(self.directory / 'evaluation' / f'{oid}.json',
                     {'opaque_id': oid, 'proposed_supervised_member': True,
                      'fit_permission': 'DENIED_PREPARATION_ONLY', 'proposed_supervised_label': int(n % 3 == 1),
                      'phase': 'attack' if n % 3 == 1 else 'clean_pre', 'environment_group_id': 'test',
                      'config_id': 'test', 'bundle_id': 'test', 'triplet_id': 'test'})
        real_read = runner.read
        fitted = False
        test_inputs = []
        test_labels = []

        def read(path):
            oid = Path(path).stem
            if oid in job['outer_test_ids']:
                self.assertTrue(fitted, 'Heldout material opened before fit completed')
                if Path(path).parent.name == 'inputs':
                    test_inputs.append(oid)
                elif Path(path).parent.name == 'evaluation':
                    predictions = self.directory / 'trials' / job['job_id'] / 'predictions.jsonl'
                    self.assertEqual(len(predictions.read_text().splitlines()), 126)
                    test_labels.append(oid)
            return real_read(path)

        def fit(*args, **kwargs):
            nonlocal fitted
            self.assertEqual(set(args[1]), set(job['train_ids']))
            self.assertEqual(set(args[2]), set(job['train_ids']))
            if fail:
                raise RuntimeError('deliberate synthetic failure')
            fitted = True
            return model, {}

        with patch.object(runner, 'read', side_effect=read), \
             patch.object(engine, 'fit_retention', side_effect=fit), \
             patch.object(engine, 'load_model', return_value=model), \
             patch.object(engine, 'save_model', side_effect=lambda m, p: self.put(p, {'fake': True})), \
             patch.object(engine, 'predict_current', side_effect=lambda m, oid, *a, **k: {'opaque_id': oid, 'decision': 'NO_ALERT'}):
            receipt = runner.worker(self.directory, job['job_id'])
        return job, receipt, test_inputs, test_labels

    def test_worker_opens_heldout_only_after_fit_and_labels_after_predictions(self):
        job, receipt, inputs, labels = self.fake_worker()
        self.assertEqual(receipt['outcome'], 'FITTED')
        self.assertEqual(inputs, job['outer_test_ids'])
        self.assertEqual(labels, job['outer_test_ids'])
        self.assertEqual(receipt['actual_prediction_calls'], 126)

    def test_failed_fit_is_charged_and_never_reads_heldout(self):
        job, receipt, inputs, labels = self.fake_worker(fail=True)
        self.assertEqual(receipt['outcome'], 'FAILED')
        self.assertEqual(receipt['actual_fit_invocations'], 1)
        self.assertEqual(receipt['actual_prediction_calls'], 0)
        self.assertEqual((inputs, labels), ([], []))
        self.assertTrue((self.directory / 'trials' / job['job_id'] / 'FIT_STARTED.json').exists())


if __name__ == '__main__':
    unittest.main()
