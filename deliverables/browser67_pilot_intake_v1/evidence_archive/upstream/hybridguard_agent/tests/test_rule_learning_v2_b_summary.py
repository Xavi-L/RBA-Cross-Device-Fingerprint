"""Synthetic regressions for partial/damaged trial output; no research fits."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hybridguard_agent.tests.test_rule_learning_v2 import toy, toy_fit
from hybridguard_agent.research.rule_learning_v2 import diagnose
from hybridguard_agent.research.rule_learning_v2.adapter import save_model, predict_current
from hybridguard_agent.research.rule_learning_v2.common import write, write_lines, read, lines
from hybridguard_agent.research.rule_learning_v2.pilot import preserve_failed_attempt
from hybridguard_agent.research.rule_learning_v2.trial_summary import inspect_attempt


class SummaryTests(unittest.TestCase):
    def fixture(self, d):
        _, _, _, raw, meta = toy()
        _, model, training = toy_fit()
        job = {'job_id': 'fixture', 'fold_id': 'fixture-v2-fold', 'representation': 'S_FLAT',
               'outer_test_ids': list(raw)}
        predictions = [predict_current(model, i, row) for i, row in raw.items()]
        save_model(model, d/'model.json'); write(d/'training.json', training)
        write_lines(d/'predictions.jsonl', predictions)
        write(d/'receipt.json', {'state': model.status, 'model_id': model.model_id})
        return job, meta, predictions

    def assert_failed(self, d, job):
        before = {p.name: p.read_bytes() for p in d.iterdir()}
        result = inspect_attempt(d, job)
        self.assertEqual([r['opaque_id'] for r in result['predictions']], job['outer_test_ids'])
        self.assertEqual({r['decision'] for r in result['predictions']}, {'FAILED'})
        self.assertIsNone(result['model'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in d.iterdir()})
        return result

    def test_worker_failure_no_model(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); job = {'job_id':'fixture','fold_id':'f','representation':'S_FLAT','outer_test_ids':['a','b']}
            preserve_failed_attempt(d, job, 'fixture crash')
            result = self.assert_failed(d, job)
            self.assertEqual(result['audit']['status'], 'WORKER_FAILED')
            self.assertFalse(result['audit']['model_readable'])

    def test_worker_failure_truncated_model(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); job, _, _ = self.fixture(d)
            (d/'model.json').write_text('{"unfinished":')
            preserve_failed_attempt(d, job, 'fixture crash')
            result = self.assert_failed(d, job)
            self.assertTrue(any(x['artifact']=='model.json' for x in result['audit']['issues']))

    def test_worker_failure_missing_or_corrupt_training(self):
        for kind in ('missing','corrupt'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as t:
                d = Path(t); job, _, _ = self.fixture(d)
                if kind=='missing': (d/'training.json').unlink()
                else: (d/'training.json').write_text('{')
                preserve_failed_attempt(d, job, 'fixture crash')
                result = self.assert_failed(d, job)
                self.assertFalse(result['audit']['training_readable'])

    def test_partial_predictions_and_broken_failure_rows_keep_all_ids(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); job, _, predictions = self.fixture(d)
            (d/'predictions.jsonl').write_text(json.dumps(predictions[0])+'\n')
            preserve_failed_attempt(d, job, 'fixture partial prediction crash')
            (d/'failure_predictions.jsonl').write_text('{')
            self.assert_failed(d, job)

    def test_successful_trial_is_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); job, _, predictions = self.fixture(d)
            result = inspect_attempt(d, job)
            self.assertEqual(result['audit']['status'], 'OK')
            self.assertEqual(result['predictions'], predictions)
            self.assertEqual(json.loads(json.dumps(result['model'].to_dict())), read(d/'model.json'))
            self.assertEqual(result['training'], read(d/'training.json'))

    def test_later_corruption_explicit_integrity_exception_receipt_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); job, _, _ = self.fixture(d)
            (d/'model.json').write_text('{')
            result = self.assert_failed(d, job)
            self.assertEqual(result['audit']['status'], 'INTEGRITY_EXCEPTION')
            self.assertEqual(result['audit']['receipt_state'], 'FITTED')

    def test_after_trials_completes_and_keeps_failed_denominators(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); base = root/'fixture';base.mkdir()
            job, meta, baseline = self.fixture(base)
            fold = {'fold_id':'fixture-v2-fold','train':[],'outer_test':job['outer_test_ids']}
            for rep in ('S_FLAT','J0'):
                d = root/'trials'/('V2-A__'+rep+'__fixture-v2-fold__attempt01');d.mkdir(parents=True)
                preserve_failed_attempt(d, dict(job,representation=rep), 'fixture crash')
                (d/'model.json').write_text('{')
            write_lines(root/'posthoc_ensemble_diagnostic.jsonl', baseline)
            patches = [patch.object(diagnose,'OUT',root), patch.object(diagnose,'metadata',return_value=meta),
                       patch.object(diagnose,'raw_cache',return_value={}),
                       patch.object(diagnose,'baseline_jobs',return_value={'C0':[],'W0':[]}),
                       patch.object(diagnose,'saved_predictions',return_value=({r['opaque_id']:r for r in baseline},[])),
                       patch.object(diagnose,'folds',return_value=[fold])]
            from contextlib import ExitStack, redirect_stdout
            import io
            with ExitStack() as stack, redirect_stdout(io.StringIO()):
                for p in patches: stack.enter_context(p)
                diagnose.after_trials()
            result = read(root/'metrics.json')['S_FLAT']
            self.assertEqual(result['metrics']['failure_rate']['numerator'], len(meta))
            self.assertEqual(result['metrics']['attack_tpr']['denominator'], 6)
            self.assertEqual(result['metrics']['clean_alarm_rate']['denominator'], 12)
            self.assertIsNone(next(r for r in read(root/'model_manifest.json') if r['representation']=='S_FLAT')['complexity'])


if __name__ == '__main__': unittest.main()
