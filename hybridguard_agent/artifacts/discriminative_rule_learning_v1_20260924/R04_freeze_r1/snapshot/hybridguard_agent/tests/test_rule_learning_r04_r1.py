"""R04-R1 regressions run only in the copied freeze after original R04 tests."""
import copy
import subprocess
import unittest
from unittest.mock import patch

from hybridguard_agent.research.rule_learning.contracts import STUDY, read_json, read_jsonl
from hybridguard_agent.research.rule_learning.evaluation import evaluate
from hybridguard_agent.research.rule_learning.job_runtime import write_json
from hybridguard_agent.research.rule_learning.models import load_model
from hybridguard_agent.research.rule_learning.oof import aggregate_oof
from hybridguard_agent.research.rule_learning.runner import failed_rows, run
from hybridguard_agent.tests import test_rule_learning_r04 as original

COVERAGE = ('atom_coverage', 'clause_coverage')


class R04R1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = original.R04Tests
        cls.base, cls.snapshot, cls.out = base, base.snapshot, base.out
        cls.jobs = [j for j in base.jobs if j['fixture_id'] == 'complementary']
        wanted = {j['model_unit_id'] for j in cls.jobs}
        cls.rows = [r for r in base.predictions if r['model_unit_id'] in wanted]
        cls.receipts = {k: v for k, v in base.receipts.items() if k in wanted}
        cls.metadata = {}
        for j in cls.jobs:
            cls.metadata.update(read_json(base.runs['complete'] / 'jobs' / j['model_unit_id'] / 'evaluation_sidecar.json'))

    def assert_unknown_scopes(self, report, unknown_ids, names=COVERAGE):
        scopes = [report['metrics']] + [ms for groups in report['strata'].values() for ms in groups.values()]
        for scope in scopes:
            for name in names:
                metric = scope[name]
                if set(metric['source_rows']) & set(unknown_ids):
                    self.assertEqual(metric['status'], 'NOT_EVALUABLE')
                    for field in ('value', 'numerator', 'denominator', 'expected_denominator', 'minimum_nonzero_rate'):
                        self.assertIsNone(metric[field], (name, field, metric['stratum']))
                    self.assertEqual(metric['known_subset']['scope'], 'ONLY_ROWS_WITH_KNOWN_MODEL_CELL_COUNTS')
                    self.assertEqual(set(metric['known_subset']['source_rows']), set(metric['source_rows']) - set(unknown_ids))

    def test_16_existing_receipt_without_model_is_unknown_not_zero(self):
        a, b = self.jobs
        outcomes = []
        for state, execution in (('NOT_RUN_BUDGET_EXHAUSTED', None), ('FAILED', 'WORKER_ERROR'),
                                 ('FAILED', 'WORKER_WALL_LIMIT'), ('NOT_RUN_MISSING_REUSE_SOURCE', None)):
            with self.subTest(state=state, execution=execution):
                receipts = copy.deepcopy(self.receipts)
                # Even legacy placeholder zeros are unknown without a model.
                receipts[b['model_unit_id']] = {'model_unit_id': b['model_unit_id'], 'model_id': None,
                    'state': state, 'execution_status': execution, 'atoms': 0, 'clauses': 0}
                rows = [r for r in self.rows if r['model_unit_id'] == a['model_unit_id']] + failed_rows(b, state)
                for r in rows:
                    if r['model_unit_id'] == b['model_unit_id']:
                        r.update(selected_atoms_expected=0, clauses_expected=0)
                result = aggregate_oof(self.jobs, rows, receipts, self.metadata)[0]
                report = result['report']
                self.assert_unknown_scopes(report, b['outer_test_ids'])
                self.assertEqual(report['expected_stage_n'], 18)
                self.assertEqual(report['metrics']['failure_rate']['denominator'], 18)
                self.assertEqual(report['metrics']['failure_rate']['value'], .5)
                self.assertEqual(report['metrics']['attack_tpr']['denominator'], 6)
                self.assertEqual(report['metrics']['clean_alarm_rate']['denominator'], 12)
                self.assertEqual(report['metrics']['atom_coverage']['known_subset']['expected_denominator'], 18)
                outcomes.append(result)
        write_json(self.out / 'R1_RECEIPT_WITHOUT_MODEL.json', outcomes)
        original.EVIDENCE.append({'check': 'R1_existing_receipt_without_model', 'states': 4,
            'full_atom_and_clause_coverage': 'NOT_EVALUABLE_NULL', 'known_subset': '18/18 cells in 9/18 stages',
            'all_strata_checked': True, 'stage_denominator': 18})

    def test_17_known_model_missing_or_failed_predictions_retains_cells(self):
        for failed in (False, True):
            rows = copy.deepcopy(self.rows)
            if failed:
                rows[0].update(decision='FAILED', selected_atoms_available=0, clauses_defined=0,
                               selected_atoms_expected=0, clauses_expected=0)
            else:
                rows = rows[1:]
            result = aggregate_oof(self.jobs, rows, self.receipts, self.metadata)[0]
            for name in COVERAGE:
                metric = result['report']['metrics'][name]
                self.assertEqual(metric['status'], 'OK')
                self.assertEqual((metric['numerator'], metric['expected_denominator']), (34, 36))
                self.assertEqual(metric['value'], 34 / 36)
            self.assertEqual(result['report']['metrics']['failure_rate']['numerator'], 1)
            self.assertEqual(result['report']['metrics']['failure_rate']['denominator'], 18)
        write_json(self.out / 'R1_KNOWN_MODEL_MISSING_PREDICTION.json',
                   aggregate_oof(self.jobs, self.rows[1:], self.receipts, self.metadata))
        # A wholly missing prediction fold still uses its own model's counts,
        # including when its shape differs from the surviving fold's model.
        a, b = self.jobs
        receipts = copy.deepcopy(self.receipts)
        receipts[b['model_unit_id']].update(atoms=3, clauses=1)
        rows = [r for r in self.rows if r['model_unit_id'] == a['model_unit_id']]
        report = aggregate_oof(self.jobs, rows, receipts, self.metadata)[0]['report']
        self.assertEqual(report['metrics']['atom_coverage']['expected_denominator'], 45)
        self.assertEqual(report['metrics']['clause_coverage']['expected_denominator'], 27)
        self.assertEqual(report['metrics']['atom_coverage']['numerator'], 18)
        original.EVIDENCE.append({'check': 'R1_known_model_missing_prediction', 'coverage': '34/36', 'failure': '1/18'})

    def test_18_receipt_missing_counts_and_missing_receipt_propagate_to_strata(self):
        b = self.jobs[1]
        for absent in (False, True):
            receipts = copy.deepcopy(self.receipts)
            if absent:
                del receipts[b['model_unit_id']]
            else:
                del receipts[b['model_unit_id']]['atoms']
                receipts[b['model_unit_id']]['clauses'] = None
            result = aggregate_oof(self.jobs, self.rows, receipts, self.metadata)[0]
            self.assert_unknown_scopes(result['report'], b['outer_test_ids'])
        receipts = copy.deepcopy(self.receipts)
        receipts[b['model_unit_id']]['clauses'] = None
        report = aggregate_oof(self.jobs, self.rows, receipts, self.metadata)[0]['report']
        self.assertEqual(report['metrics']['atom_coverage']['value'], 1)
        self.assertEqual(report['metrics']['atom_coverage']['expected_denominator'], 36)
        self.assert_unknown_scopes(report, b['outer_test_ids'], ('clause_coverage',))
        empty = evaluate(list(self.metadata), [], self.metadata)
        self.assert_unknown_scopes(empty, list(self.metadata))

    def test_19_empty_models_and_constants_have_known_zero_counts(self):
        reports = read_json(self.base.runs['complete'] / 'OOF.json')
        checked = []
        for item in reports:
            receipt = item['folds'][0]['receipt']
            if receipt['state'] == 'EMPTY_MODEL' or item['group']['method_id'] in ('ALWAYS_NO_ALERT', 'ALWAYS_ABSTAIN'):
                for name in COVERAGE:
                    metric = item['report']['metrics'][name]
                    self.assertEqual(metric['expected_denominator'], 0)
                    self.assertIsNone(metric['value'])
                    self.assertEqual(metric['reason'], 'ZERO_SUPPORTED_DENOMINATOR')
                    self.assertNotIn('known_subset', metric)
                checked.append(item['group']['method_id'])
        self.assertIn('ALWAYS_NO_ALERT', checked)
        self.assertIn('ALWAYS_ABSTAIN', checked)
        self.assertGreater(len(checked), 2)
        for suite in ('budget_count', 'budget_time'):
            report = read_json(self.base.runs[suite] / 'OOF.json')[0]['report']
            for name in COVERAGE:
                self.assertIsNone(report['metrics'][name]['value'])
                self.assertIsNone(report['metrics'][name]['expected_denominator'])

    def test_20_dispatcher_worker_error_and_timeout_without_model(self):
        original_run = subprocess.run
        target = sorted(self.jobs, key=lambda j: (j['priority'], j['job_id']))[1]
        records = []
        for failure in ('error', 'timeout'):
            out = self.out / ('r1_worker_' + failure)
            def fail_one(cmd, *args, **kwargs):
                if 'worker' in cmd and target['model_unit_id'] in str(cmd):
                    if failure == 'timeout':
                        raise subprocess.TimeoutExpired(cmd, kwargs['timeout'])
                    return subprocess.CompletedProcess(cmd, 1, '', 'BUILTIN_TEST_INJECTED_WORKER_FAILURE')
                return original_run(cmd, *args, **kwargs)
            with patch('hybridguard_agent.research.rule_learning.runner.subprocess.run', side_effect=fail_one):
                run(self.snapshot.root, 'SYNTHETIC_R04', out, self.out / ('r1_worker_' + failure + '_budget.json'), suite='r1_worker_failure')
            receipt = read_json(out / 'model_receipts.json')[target['model_unit_id']]
            self.assertIsNone(receipt['model_id'])
            self.assertEqual(receipt['execution_status'], 'WORKER_WALL_LIMIT' if failure == 'timeout' else 'WORKER_ERROR')
            report = read_json(out / 'OOF.json')[0]['report']
            self.assert_unknown_scopes(report, target['outer_test_ids'])
            self.assertEqual(report['expected_stage_n'], 18)
            rows = read_jsonl(out / 'predictions.jsonl')
            self.assertTrue(all(r['selected_atoms_expected'] is None for r in rows if r['model_id'] is None))
            records.append({'failure_injection': failure, 'receipt': receipt, 'expected_stage_n': 18})
        original.EVIDENCE.append({'check': 'R1_dispatcher_failure_paths', 'injection_boundary': 'synthetic worker subprocess only',
                                 'records': records, 'real_worker_timeout_claimed': False})

    def test_21_three_exact_r02_whitelists_before_encoder_and_selector(self):
        out = self.out / 'r1_single_surfaces'
        run(self.snapshot.root, 'SYNTHETIC_R04', out, self.out / 'r1_single_budget.json', suite='r1_single_surfaces')
        columns = read_json(STUDY / 'R02_matrix/COLUMN_MANIFEST.json')
        controls = read_jsonl(STUDY / 'R02_matrix/fixed_control_manifest.jsonl')
        fixtures = read_json(self.snapshot.root / 'synthetic/R1_SURFACE_FIXTURES.json')
        evidence = {}
        jobs = [j for j in self.snapshot.synthetic if j['fixture_id'].startswith('r1-single-')]
        self.assertEqual(len(jobs), 3)
        for j in jobs:
            surface = j['input_view']
            with self.subTest(surface=surface):
                cats = set(columns['single_surface_catalog_columns'][surface])
                fixed = {c['atom_id'] for c in controls if c['surface'] == surface}
                numeric = {'UNFITTED_CONTROL:' + c['field'] for c in columns['control_columns']
                           if c['surface'] == surface and 'TRAIN_QUANTILE' in c['encoder']}
                expected = cats | fixed | numeric
                ctx = self.snapshot.context(j['job_id'], 'SYNTHETIC_R04')
                access = ctx.train()
                self.assertEqual({a.atom_id for a in access.atoms}, expected)
                self.assertTrue(all(set(r) == expected for r in access.batch('train').records))
                self.assertEqual(access.operations, [])
                path = out / 'jobs' / j['model_unit_id']
                m = load_model(path / 'model.json')
                self.assertEqual(set(m.encoder['fixed_atoms']), cats | fixed)
                self.assertEqual(set(m.encoder['numeric']), numeric)
                encoded = cats | fixed | {a for e in m.encoder['numeric'].values() for a in e['atom_ids']}
                self.assertEqual(set(m.view['input_atom_ids']), encoded)
                train = read_json(path / 'training.json')
                for cid in train['support']:
                    self.assertIn(cid.rsplit(':', 1)[0], encoded)
                self.assertTrue(set(a.atom_id for a in m.atoms) <= encoded)
                excluded = set(fixtures[surface]['excluded_same_surface_ids'])
                self.assertTrue(excluded)
                self.assertFalse(excluded & (set(m.encoder['fixed_atoms']) | set(m.encoder['numeric']) | encoded))
                events = read_json(path / 'access_log.json')
                names = [e['event'] for e in events]
                self.assertLess(names.index('SINGLE_SURFACE_ALLOWLIST_APPLIED'), names.index('TRAIN_TRANSFORM_FINISHED'))
                self.assertLess(names.index('MODEL_SAVED_LOADED_FROZEN'), names.index('OPEN_OUTER_TEST_FEATURE'))
                self.assertTrue(all(e['resource'].startswith('synthetic/') for e in events if e['event'] in
                    ('OPEN_TRAIN_FEATURE', 'OPEN_TRAIN_LABEL', 'OPEN_OUTER_TEST_FEATURE', 'OPEN_OUTER_EVALUATION_LABEL')))
                evidence[surface] = {'catalog_ids': sorted(cats), 'fixed_control_ids': sorted(fixed),
                    'unfitted_numeric_ids': sorted(numeric), 'raw_allowed_ids': sorted(expected),
                    'encoded_ids': sorted(encoded), 'excluded_same_surface_ids': sorted(excluded),
                    'support_candidate_n': len(train['support']), 'real_value_reads': 0}
        self.assertEqual(evidence['host26']['catalog_ids'], ['CAT:CORE-002', 'CAT:NVW-005', 'CAT:OFFDER-BRIDGE-001',
            'CAT:OFFDER-DEVCONFIG-001', 'CAT:P3-PROVIDER-PARSE'])
        self.assertTrue({'CAT:NVW-003', 'CAT:NVW-004'} <= set(evidence['host26']['excluded_same_surface_ids']))
        write_json(self.out / 'R1_SINGLE_SURFACE_VALIDATION.json', evidence)
        original.EVIDENCE.append({'check': 'R1_single_surface_exact_sets',
            'allowed_counts': {s: len(e['raw_allowed_ids']) for s, e in evidence.items()},
            'fixture_values': 'PROGRAMMATIC_SYNTHETIC_ONLY', 'real_R07_authorized': False})
