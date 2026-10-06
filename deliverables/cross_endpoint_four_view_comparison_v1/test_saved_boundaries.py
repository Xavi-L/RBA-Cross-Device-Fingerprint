"""Boundary checks using saved artifacts; never fit or load private raw data."""
import copy
import shutil
import tempfile
import unittest

import engine as e
from features import APP, BROWSER
from io_utils import HERE, Path, read, rows, write, jsonl
from summarize import summarize


class SavedBoundaries(unittest.TestCase):
    def test_current_endpoint_gates_and_browser_isolation(self):
        item = rows(HERE / 'results/features.jsonl')[-1]
        item = {k: copy.deepcopy(item[k]) for k in ('cells', 'endpoint_errors', 'pair_errors')}
        browser = read(HERE / 'results/P0_V_BROWSER.json')
        item['cells'] = {k: v for k, v in item['cells'].items() if k in BROWSER}
        item['endpoint_errors'] = {'app': ['BAD_REFERENCE'], 'browser': []}
        item['pair_errors'] = ['MISMATCH']
        self.assertIn(e.predict_current(browser, item)['state'], ('T', 'F'))
        item['endpoint_errors']['browser'] = ['MISSING_ENDPOINT']
        before = dict(e.COUNTS)
        self.assertEqual(e.predict_current(browser, item)['state'], 'FAILED')
        self.assertEqual(dict(e.COUNTS), before)
        item['endpoint_errors']['browser'] = []
        for cell in item['cells'].values():
            cell.update(value=None, available=False, reason='TEST_UNAVAILABLE')
        self.assertEqual(e.predict_current(browser, item)['state'], 'U')
        self.assertEqual(dict(e.COUNTS), before)

    def test_current_entry_rejects_evaluation_metadata(self):
        bundle = read(HERE / 'results/P0_V_APP.json')
        for key in ('sample_id', 'label', 'phase', 'scenario', 'source', 'version', 'timestamp', 'model_output'):
            with self.assertRaisesRegex(ValueError, 'INFERENCE_SIDECAR'):
                e.predict_current(bundle, {key: 'forbidden'})

    def summary_copy(self, target):
        for name in ('models.json', 'members.jsonl', 'predictions.jsonl', 'frozen_reference_predictions.jsonl'):
            shutil.copyfile(HERE / 'results' / name, target / name)

    def test_failed_effective_intervention_keeps_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.summary_copy(target)
            members = rows(target / 'members.jsonl')
            affected = next(m for m in members if m['cohort'] == 'b2b42' and m['identity'] == 'EFFECTIVE_INTERVENTION')
            affected['runtime_restored'] = False
            jsonl(target / 'members.jsonl', members)
            predictions = rows(target / 'predictions.jsonl')
            for row in predictions:
                if row['sample_id'] == affected['sample_id']:
                    row.update(state='FAILED', probability=None, leaf=None)
            jsonl(target / 'predictions.jsonl', predictions)
            before = dict(e.COUNTS)
            table = summarize(target, target / 'summary')
            selected = [r for r in table if r['cohort'] == 'b2b42' and r['group'] == 'EFFECTIVE_INTERVENTION']
            self.assertEqual(len(selected), 12)
            self.assertTrue(all(r['n'] == 8 and r['FAILED'] == 1 for r in selected))
            self.assertEqual(dict(e.COUNTS), before)

    def test_missing_prediction_position_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.summary_copy(target)
            jsonl(target / 'predictions.jsonl', rows(target / 'predictions.jsonl')[1:])
            with self.assertRaisesRegex(ValueError, 'OUTPUT_PRODUCT_MISMATCH'):
                summarize(target, target / 'summary')
