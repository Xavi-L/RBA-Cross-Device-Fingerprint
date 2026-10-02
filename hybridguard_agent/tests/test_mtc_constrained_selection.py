"""Focused synthetic tests; these fits are not the real experiment's fit ledger."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import json
import time
import unittest
from unittest.mock import patch

from hybridguard_agent.research import mtc_constrained_reselection as engine
from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess
from hybridguard_agent.research.rule_learning_v2.common import SURFACES
from hybridguard_agent.research.rule_learning_v2.semantic_selection import retain_semantic


def fixture(n=12, fields=('first', 'second'), mtc_n=20):
    atoms = [Atom('fixture:' + field, field, ('app_web67',), ('SYNTHETIC',), (field,),
                  'CONTROL_EQUALITY', {'field': 'fixture.' + field,
                                       'equals': True, 'encoder': 'BOOL_EQUALS'}) for field in fields]
    defs = {'atoms': [asdict(a) for a in atoms], 'single_surface_allowlists':
            {s: [a.atom_id for a in atoms if a.surfaces == (s,)] for s in SURFACES}}
    rows, meta = {}, {}
    for k in range(n):
        for phase in ('clean_pre', 'attack', 'clean_post'):
            sid = f'fixture-controlled-{k}-{phase}'
            rows[sid] = {a.atom_id: cell('T' if phase == 'attack' else 'F') for a in atoms}
            meta[sid] = {'bundle_id': 'fixture-bundle', 'triplet_id': f't{k}',
                         'phase': phase, 'supervised_label': int(phase == 'attack'),
                         'config_id': f'config{k % 2}', 'environment_group_id': f'env{k % 2}'}
    mtc = {f'fixture-mtc-{k}': {a.atom_id: cell('F') for a in atoms} for k in range(mtc_n)}
    mtc_meta = {sid: {'split': 'discovery', 'normal_basis': True, 'group_id': sid} for sid in mtc}
    job = {'fold_id': 'fixture-fold', 'train_ids': list(rows), 'outer_test_ids': ['fixture-outer']}
    return defs, job, rows, meta, mtc, mtc_meta


def prepare(data):
    defs, job, rows, meta, mtc, mtc_meta = data
    return engine.prepare_fold(job, rows, meta, defs, mtc, mtc_meta,
                               mtc_train_ids=tuple(mtc), mtc_evaluation_ids=['fixture-eval'])


def problem(prepared, scheme='A'):
    return engine._problem(prepared, scheme, time.monotonic() + 60)[0]


def positive(p, suffix):
    return next(c for c in p.candidates if c.id == 'fixture:' + suffix + ':POSITIVE')


class DualNormalSelectionTests(unittest.TestCase):
    def test_mtc_is_separate_population_not_support_or_triplets(self):
        prepared = prepare(fixture())
        p = problem(prepared)
        self.assertEqual(len(p.triplets), 12)
        self.assertEqual(len(p.ids), 36)
        self.assertEqual(len(p.clean), 24)
        self.assertEqual((p.budget, p.mtc_budget), (1, 1))
        self.assertTrue(set(p.mtc_ids).isdisjoint(p.ids))
        support = p.support['fixture:first:POSITIVE']
        self.assertEqual(support['true_attack_triplets'], 12)
        self.assertEqual(support['train_ids'], list(p.ids))
        with self.assertRaisesRegex(PermissionError, 'NOT_TRIPLET'):
            mutated = list(fixture())
            next(iter(mutated[5].values()))['triplet_id'] = 'fake'
            prepare(mutated)

    def test_two_separate_budgets_and_or_cannot_bypass(self):
        data = fixture()
        data[4]['fixture-mtc-0']['fixture:first'] = cell('T')
        data[4]['fixture-mtc-1']['fixture:second'] = cell('T')
        p = problem(prepare(data))
        first, second = positive(p, 'first'), positive(p, 'second')
        self.assertTrue(p.score((first,))['feasible'])
        self.assertTrue(p.score((second,))['feasible'])
        both = p.score((first, second))
        self.assertEqual((both['clean_alarms'], both['mtc_alarms']), (0, 2))
        self.assertFalse(both['partial_feasible'])
        self.assertFalse(both['feasible'])
        # A separate controlled violation cannot be diluted by 20 MTC normals.
        data = fixture()
        for sid in ['fixture-controlled-0-clean_pre', 'fixture-controlled-1-clean_pre']:
            data[2][sid]['fixture:first'] = cell('T')
        p = problem(prepare(data))
        self.assertFalse(p.score((positive(p, 'first'),))['partial_feasible'])

    def test_retention_cannot_reintroduce_mtc_violation(self):
        data = fixture()
        data[4]['fixture-mtc-0']['fixture:first'] = cell('T')
        data[4]['fixture-mtc-1']['fixture:second'] = cell('T')
        prepared = prepare(data)
        sparse, st = engine.fit_sparse(prepared, scheme='A')
        retained, rt = engine.fit_retention(prepared, scheme='A', initial_model=sparse, initial_training=st)
        self.assertEqual((sparse.status, retained.status), ('FITTED', 'FITTED'))
        self.assertEqual(len(retained.clauses), 1)
        self.assertEqual(retained.fit['training_result']['mtc_alarms'], 1)
        self.assertGreater(retained.fit['set_constraint_rejection_counts']['MTC_SET_NORMAL_BUDGET'], 0)

    def test_retention_quality_swap_cannot_break_mtc_budget(self):
        data = list(fixture())
        field = 'app.web_data.automation_surface_layer.webdriver'
        old = Atom('fixture:first', 'first', ('app_web67',), ('SYNTHETIC',), ('old',),
                   'CONTROL_EQUALITY', {'field': field, 'equals': True, 'encoder': 'BOOL_EQUALS'})
        new = Atom('fixture:second', 'second', ('app_web67',), ('SYNTHETIC',), ('new',),
                   'SAVED_SEMANTIC_STATE', {'field': field, 'field_refs': [field],
                       'semantic_version': '1.0.0', 'input_schema_version': 'rsr-input-v1',
                       'input_origin': 'SAVED_CANDIDATE_RESULTS_NO_REEVALUATION',
                       'mode': 'raw_observation_v1', 'gate_version': 'rsr-webdriver-raw-gate-v1'})
        data[0]['atoms'] = [asdict(old), asdict(new)]
        for k in (0, 1):
            data[4][f'fixture-mtc-{k}']['fixture:second'] = cell('T')
        p = problem(prepare(data))
        catalog = engine.semantic_catalog(p.atoms)
        self.assertEqual(catalog[old.atom_id]['signal_group'], catalog[new.atom_id]['signal_group'])
        self.assertGreater(catalog[new.atom_id]['quality'], catalog[old.atom_id]['quality'])
        first = positive(p, 'first')
        selected, outcome, trace = retain_semantic(p, (first,), time.monotonic() + 60)
        self.assertEqual(selected, (first,))
        self.assertEqual(trace, [])
        self.assertGreaterEqual(outcome['rejection_counts']['INFEASIBLE'], 1)
        self.assertGreater(p.constraint_rejections['MTC_SET_NORMAL_BUDGET'], 0)

    def test_scheme_b_candidate_gate_exact_90_and_model_coverage(self):
        data = fixture(mtc_n=100)
        for k in range(10):
            data[4][f'fixture-mtc-{k}']['fixture:first'] = cell('U')
        for k in range(10, 20):
            data[4][f'fixture-mtc-{k}']['fixture:second'] = cell('U')
        p = problem(prepare(data), 'B')
        a, b = positive(p, 'first'), positive(p, 'second')
        self.assertTrue(p.score((a,))['feasible'])
        self.assertTrue(p.score((b,))['feasible'])
        both = p.score((a, b))
        self.assertEqual(float(both['mtc_coverage']), 0.8)
        self.assertFalse(both['feasible'])
        selected, _, _ = retain_semantic(p, (a,), time.monotonic() + 60)
        self.assertEqual(selected, (a,))
        data[4]['fixture-mtc-10']['fixture:first'] = cell('U')
        p = problem(prepare(data), 'B')
        self.assertNotIn('fixture:first:POSITIVE', {c.id for c in p.candidates})
        reason = next(r for r in p.manifest if r['clause_id'] == 'fixture:first:POSITIVE')
        self.assertIn('MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT', reason['reasons'])

    def test_full_unknown_stays_unknown_and_b_reports_empty(self):
        data = fixture(fields=('first',))
        for row in data[4].values():
            row['fixture:first'] = cell('U')
        prepared = prepare(data)
        a, _ = engine.fit_sparse(prepared, scheme='A')
        b, _ = engine.fit_sparse(prepared, scheme='B')
        self.assertEqual((a.status, b.status), ('FITTED', 'EMPTY_MODEL'))
        self.assertEqual(a.fit['training_result']['mtc_state_counts']['U'], 20)
        self.assertEqual(engine.predict_current(a, 'same', data[4]['fixture-mtc-0'])['logical_state'], 'U')
        self.assertEqual(engine.predict_current(b, 'same', data[4]['fixture-mtc-0'])['decision'], 'EMPTY_MODEL')

    def test_mtc_three_valued_or_matches_prediction(self):
        data = fixture()
        data[4]['fixture-mtc-0'].update({'fixture:first': cell('T'), 'fixture:second': cell('U')})
        data[4]['fixture-mtc-1'].update({'fixture:first': cell('F'), 'fixture:second': cell('U')})
        p = problem(prepare(data))
        score = p.score((positive(p, 'first'), positive(p, 'second')))
        self.assertEqual(score['mtc_state_counts'],
                         {'expected': 20, 'defined': 19, 'T': 1, 'F': 18, 'U': 1, 'FAILED': 0, 'EMPTY_MODEL': 0})

    def test_evaluation_members_never_admitted_and_metadata_not_features(self):
        data = fixture()
        data[5]['fixture-mtc-0']['split'] = 'development'
        with self.assertRaisesRegex(PermissionError, 'DISCOVERY'):
            prepare(data)
        data = fixture()
        with self.assertRaisesRegex(PermissionError, 'EXACT_MTC'):
            engine.prepare_fold(data[1], data[2], data[3], data[0], data[4], data[5],
                                 mtc_train_ids=list(data[4]), mtc_evaluation_ids=['fixture-mtc-0'])
        prepared = prepare(data)
        model, _ = engine.fit_sparse(prepared, scheme='A')
        row = data[2]['fixture-controlled-0-attack']
        expected = engine.predict_current(model, 'id-a', row)
        actual = engine.predict_current(model, 'id-b', row | {'label': 'normal', 'model_id': 'phone',
                                                            'path': 'arbitrary', 'source': 'MTC'})
        self.assertEqual((expected['decision'], expected['logical_state']), (actual['decision'], actual['logical_state']))

    def test_high_memory_dpr_rejected_from_values_not_rule_names(self):
        for field in ('device_memory', 'device_pixel_ratio', 'renamed_measurement'):
            data = list(fixture(fields=(field,)))
            key = 'UNFITTED_CONTROL:fixture.' + field
            atom = Atom(key, field, ('app_web67',), ('SYNTHETIC',), (key,), 'UNFITTED_CONTROL',
                        {'field': 'fixture.' + field})
            data[0] = {'atoms': [asdict(atom)], 'single_surface_allowlists':
                       {s: [key] if s == 'app_web67' else [] for s in SURFACES}}
            data[2] = {sid: {key: {'value': 8 if data[3][sid]['phase'] == 'attack' else 2,
                                  'available': True, 'evaluation_status': 'OK'}} for sid in data[2]}
            data[4] = {sid: {key: {'value': 8, 'available': True, 'evaluation_status': 'OK'}} for sid in data[4]}
            prepared = prepare(data)
            with patch.object(engine, 'encode_train', side_effect=AssertionError('one shared encoder only')):
                a, stats = engine.fit_sparse(prepared, scheme='A')
                b, _ = engine.fit_sparse(prepared, scheme='B')
            self.assertEqual((a.status, b.status), ('EMPTY_MODEL', 'EMPTY_MODEL'))
            self.assertEqual(a.encoder, b.encoder)
            self.assertTrue(any('MTC_SET_NORMAL_BUDGET' in x['selection_reasons']
                                for x in stats['candidate_statistics']))
            numeric = prepared.encoder['numeric'][key]
            self.assertEqual(numeric['thresholds'], [2.0, 8.0])
            self.assertEqual(prepared.encoder['train_ids'], data[1]['train_ids'])
            changed = deepcopy(data)
            for row in changed[4].values():
                row[key]['value'] = 9999999
            self.assertEqual(prepare(changed).encoder, prepared.encoder)

    def test_retention_initialization_same_scheme_only_and_roundtrip(self):
        prepared = prepare(fixture())
        a, training = engine.fit_sparse(prepared, scheme='A')
        with self.assertRaisesRegex(PermissionError, 'OWN_SCHEME'):
            engine.fit_retention(prepared, scheme='B', initial_model=a, initial_training=training)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'new.json'
            engine.save_model(a, path)
            restored = engine.load_model(path)
            self.assertEqual(json.dumps(restored.to_dict(), sort_keys=True), json.dumps(a.to_dict(), sort_keys=True))
            from hybridguard_agent.research.rule_semantics_webgl1_cap8 import load_model as old_load
            with self.assertRaises(ValueError):
                old_load(path)
        self.assertTrue(a.model_id.startswith('mtc-reselection-'))
        with self.assertRaisesRegex(ValueError, 'IDENTITY'):
            replace(a, binding=a.binding | {'experiment_id': 'webgl1-cap8-comparison-v1'})


if __name__ == '__main__':
    unittest.main()
