"""Focused V2-A synthetic boundaries; never fits research members."""
import copy
import itertools
import tempfile
import unittest
from pathlib import Path

from hybridguard_agent.research.rule_learning.access import synthetic_fixture
from hybridguard_agent.research.rule_learning.baselines import project_core
from hybridguard_agent.research.rule_learning.contracts import cell, ledger, logic, negate, state
from hybridguard_agent.research.rule_learning.fold_data import FoldBatch
from hybridguard_agent.research.rule_learning.selector import TrainProblem, greedy, json_score
from hybridguard_agent.research.rule_learning.matrix import measurement_domain, Unavailable
from hybridguard_agent.official_semantics.evaluator import _evaluate_compiled
from hybridguard_agent.research.rule_learning_v2.common import definitions, V1, read
from hybridguard_agent.research.rule_learning_v2.adapter import (
    TrainAccess, V2Problem, approved_atoms, encode_train, raw_projection,
    fit_authorized, predict_current, save_model, load_model,
)
from hybridguard_agent.research.rule_learning_v2.pilot import failed_rows, check_settings, preserve_failed_attempt, attempt_predictions
from hybridguard_agent.research.rule_learning_v2.common import write_lines
from hybridguard_agent.research.rule_learning_v2.diagnose import posthoc_decision


def toy():
    name = 'UNFITTED_CONTROL:app.web_data.navigator_layer.hardware_concurrency'
    defs = {'atoms': [{'atom_id': name, 'family': 'CONTROL_FIELD:hardware', 'surfaces': ['app_web67'],
                      'sources': ['PROJECT_CONTROL_NOT_E_Ou_H_C'], 'aliases': [name],
                      'orientation': 'UNFITTED_NUMERIC_MEASUREMENT', 'provenance': {}}],
            'single_surface_allowlists': {'native84': [], 'app_web67': [name], 'host26': []}}
    rows, meta = {}, {}
    for t in range(6):
        for phase in ('clean_pre', 'attack', 'clean_post'):
            i = f'fixture-v2-{t}-{phase}'
            rows[i] = {name: {'value': 12 if phase == 'attack' else 4,
                             'available': True, 'evaluation_status': 'OK'}}
            meta[i] = {'supervised_label': int(phase == 'attack'), 'phase': phase,
                       'bundle_id': 'fixture-bundle', 'triplet_id': str(t),
                       'environment_group_id': 'fixture-env', 'config_id': 'fixture-config'}
    job = {'fold_id': 'fixture-v2-fold', 'train_ids': list(rows), 'outer_test_ids': ['fixture-outer'],
           'representation': 'S_FLAT'}
    return name, defs, job, rows, meta


def toy_fit():
    name, defs, job, rows, meta = toy()
    access = TrainAccess(job, rows, meta)
    model, training = fit_authorized(access, defs, {'study_version': 'discriminative-rule-learning-v2-20260925',
                       'fold_id': job['fold_id'], 'authorization_id': 'SYNTHETIC_V2_TEST_ONLY'})
    return name, model, training


class V2SyntheticTests(unittest.TestCase):
    def test_exact_flat_candidate_set_and_core_alias_polarity(self):
        defs = definitions()
        atoms = approved_atoms(defs)
        self.assertEqual(len(atoms), 143)
        self.assertEqual({a.atom_id for a in atoms}, {n for ns in defs['single_surface_allowlists'].values() for n in ns})
        self.assertNotIn('CAT:NVW-003', {a.atom_id for a in atoms})
        self.assertNotIn('CAT:NVW-004', {a.atom_id for a in atoms})
        candidates = [c for c in ledger() if c['candidate_use']['core'] and c['candidate_use']['selectable_on_App177']]
        self.assertEqual(len(candidates), 12)
        row = {a.atom_id: cell('F') for a in atoms}
        row.update({c['atom_id']: cell('T' if c['direct_OR_deviation_polarity'] == 'POSITIVE' else 'F') for c in candidates})
        projected, canonical = project_core({'fixture': row}, ledger(), 'SRC-111')
        self.assertEqual(len(canonical), 10)
        self.assertTrue(all(state(c) == 'T' for c in projected['fixture'].values()))
        self.assertEqual(sorted(len(a.aliases) for a in canonical), [1]*8 + [2]*2)
        self.assertEqual(len(raw_projection({'fixture': row}, defs, 'S_FLAT')['fixture']), 143)
        self.assertEqual(len(raw_projection({'fixture': row}, defs, 'J0')['fixture']), 155)
        # Domain-sensitive NW-006 and OFFDER-UA-001 are NOT globally merged.
        self.assertIn('CAT:NW-006', {a.atom_id for a in atoms})
        self.assertIn('DEVIATION:OFFDER-UA-001', {a.atom_id for a in canonical})

    def test_three_value_logic_and_failed_measurement(self):
        for a, b in itertools.product('TFU', repeat=2):
            self.assertEqual(logic([a, b], 'OR'), 'T' if 'T' in (a,b) else 'F' if a == b == 'F' else 'U')
            self.assertEqual(logic([a, b], 'AND'), 'F' if 'F' in (a,b) else 'T' if a == b == 'T' else 'U')
        self.assertEqual(negate('U'), 'U')
        with self.assertRaises(ValueError): state(cell('FAILED'))

    def test_joint_exact_union_and_alias_support_not_multiplied(self):
        defs = definitions(); flat = approved_atoms(defs)
        _, _, job, toy_rows, meta = toy(); job['representation'] = 'J0'
        candidates = [c for c in ledger() if c['candidate_use']['core'] and c['candidate_use']['selectable_on_App177']]
        rows = {}
        for i in job['train_ids']:
            attack = meta[i]['phase']=='attack'
            row = {a.atom_id: ({'value':12 if attack else 4, 'available':True, 'evaluation_status':'OK'}
                              if a.atom_id.startswith('UNFITTED_CONTROL:') else cell('F')) for a in flat}
            row.update({c['atom_id']:cell('T' if attack == (c['direct_OR_deviation_polarity']=='POSITIVE') else 'F') for c in candidates})
            rows[i]=row
        access=TrainAccess(job,rows,meta)
        encoded,atoms,_,_=encode_train(access,defs,'J0')
        self.assertEqual(len(atoms),81+62*2+10)
        self.assertEqual(set(encoded[job['train_ids'][0]]),{a.atom_id for a in atoms})
        problem=V2Problem(access,encoded,atoms,float('inf'))
        for name in ('DEVIATION:NW-002:POSITIVE','DEVIATION:NVW-002:POSITIVE'):
            self.assertEqual(problem.support[name]['triplets'],6)
            self.assertEqual(problem.support[name]['true_attack_triplets'],6)

    def test_posthoc_full_state_truth_table(self):
        states=('MANIPULATION_ALERT','NO_ALERT','INSUFFICIENT_EVIDENCE','EMPTY_MODEL','FAILED')
        for a,b in itertools.product(states,repeat=2):
            actual=posthoc_decision(a,b)
            expected='FAILED' if 'FAILED' in (a,b) else 'MANIPULATION_ALERT' if 'MANIPULATION_ALERT' in (a,b) else 'NO_ALERT' if a==b=='NO_ALERT' else 'INSUFFICIENT_EVIDENCE'
            self.assertEqual(actual,expected)

    def test_train_only_quantiles_and_membership(self):
        name, defs, job, rows, meta = toy()
        access = TrainAccess(job, rows, meta)
        encoded, atoms, encoder, _ = encode_train(access, defs, 'S_FLAT')
        self.assertEqual(encoder['numeric'][name]['thresholds'], [4.0, 12.0])
        self.assertEqual(encoder['train_ids'], job['train_ids'])
        with self.assertRaises(PermissionError):
            access.assert_fit(FoldBatch(job['fold_id'], 'outer_test', ('fixture-outer',), ({name: {'value': 10000}},)), 'numeric_thresholds')
        with self.assertRaises(PermissionError):
            TrainAccess(job, dict(rows, **{'fixture-outer': rows[job['train_ids'][0]]}), meta)
        changed = copy.deepcopy(meta); changed[job['train_ids'][0]]['supervised_label'] = None
        with self.assertRaises(PermissionError): TrainAccess(job, rows, changed)
        self.assertEqual(len(encoded), 18)

    def test_inherited_kernel_parity_on_named_v1_toy(self):
        original = synthetic_fixture('complementary')
        batch = original.batch('train')
        p1 = TrainProblem(original, batch, 'GREEDY_OR', 'OP05')
        meta = original.training_metadata(batch)
        rows = dict(zip(batch.ids, batch.records))
        access = TrainAccess({'fold_id': batch.fold_id, 'train_ids': list(batch.ids),
                              'outer_test_ids': [], 'representation': 'S_FLAT'}, rows, meta)
        p2 = V2Problem(access, rows, original.atoms, float('inf'))
        self.assertEqual(p1.support, p2.support)
        self.assertEqual(p1.manifest, p2.manifest)
        a, _, ta = greedy(p1, float('inf')); b, _, tb = greedy(p2, float('inf'))
        self.assertEqual(a, b); self.assertEqual(ta, tb)
        self.assertEqual(json_score(p1.score(a)), json_score(p2.score(b)))

    def test_save_load_prediction_ignores_sidecar_and_preserves_failure(self):
        name, model, training = toy_fit()
        self.assertEqual(model.status, 'FITTED')
        class Poison(dict):
            def __getitem__(self, key):
                if key in ('label', 'phase', 'config_id', 'future_post'): raise AssertionError('LABEL_READ')
                return super().__getitem__(key)
        raw = Poison({name: {'value': 9999, 'available': True, 'evaluation_status': 'OK'},
                      'label': object(), 'phase': object()})
        before = copy.deepcopy(model.encoder)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model.json'; save_model(model, path); loaded = load_model(path)
            self.assertEqual(loaded.model_id, model.model_id)
            self.assertEqual(predict_current(model, 'fixture-outer', raw), predict_current(loaded, 'fixture-outer', raw))
            with self.assertRaises(FileExistsError): save_model(model, path)
        self.assertEqual(model.encoder, before)
        self.assertEqual(predict_current(model, 'fixture-outer', {name: cell('FAILED')})['decision'], 'FAILED')
        self.assertEqual(predict_current(model, 'fixture-outer', {name: cell('U')})['decision'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(predict_current(model, 'fixture-outer', raw)['decision'], 'MANIPULATION_ALERT')

    def test_failure_and_empty_model_remain_results(self):
        name, defs, job, rows, meta = toy()
        for row in rows.values(): row[name]['value'] = 4
        model, _ = fit_authorized(TrainAccess(job, rows, meta), defs,
                    {'study_version': 'discriminative-rule-learning-v2-20260925', 'fold_id': job['fold_id']})
        self.assertEqual(model.status, 'EMPTY_MODEL')
        self.assertEqual(predict_current(model, 'fixture-outer', {})['decision'], 'EMPTY_MODEL')
        rows[job['train_ids'][0]][name]['evaluation_status'] = 'FAILED'
        failed, _ = fit_authorized(TrainAccess(job, rows, meta), defs,
                    {'study_version': 'discriminative-rule-learning-v2-20260925', 'fold_id': job['fold_id']})
        self.assertEqual(failed.status, 'FAILED')
        job['job_id'] = 'fixture-attempt'
        self.assertEqual(failed_rows(job, 'fixture-error')[0]['decision'], 'FAILED')

    def test_worker_failure_keeps_partial_file_and_fails_all_expected(self):
        job={'job_id':'fixture-job','fold_id':'fixture-fold','representation':'S_FLAT',
             'outer_test_ids':['fixture-a','fixture-b']}
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp);original=[{'opaque_id':'fixture-a','decision':'MANIPULATION_ALERT'}]
            write_lines(dest/'predictions.jsonl',original)
            before=(dest/'predictions.jsonl').read_bytes()
            preserve_failed_attempt(dest,job,'SYNTHETIC_WORKER_FAILURE_AFTER_PARTIAL_WRITE')
            self.assertEqual((dest/'predictions.jsonl').read_bytes(),before)
            self.assertEqual([r['opaque_id'] for r in attempt_predictions(dest)],job['outer_test_ids'])
            self.assertTrue(all(r['decision']=='FAILED' for r in attempt_predictions(dest)))

    def test_native_anchor_is_validity_gate_not_version_comparison(self):
        relation = {'predicate_id': 'android_host_not_desktop_or_script_surface_v1', 'relation_id': 'fixture',
                    'name': 'fixture', 'severity': 'fixture', 'risk_use_status': 'fixture',
                    'premise_fields': [], 'official_card_refs': [], 'official_source_refs': [], 'inference_level': 'fixture'}
        facts = {'native.android_major': {'status': 'observed', 'value': 11},
                 'web.ua_class': {'status': 'observed', 'value': 'desktop_or_headless'},
                 'web.platform_class': {'status': 'observed', 'value': 'desktop'}}
        a = _evaluate_compiled(relation, {}, {}, facts)['outcome']
        facts['native.android_major']['value'] = 16
        self.assertEqual(a, _evaluate_compiled(relation, {}, {}, facts)['outcome'])
        facts['native.android_major']['value'] = None
        self.assertEqual(_evaluate_compiled(relation, {}, {}, facts)['outcome'], 'unknown')

    def test_v1_settings_unchanged(self):
        self.assertEqual(check_settings()['seed'], 20260924)


if __name__ == '__main__':
    unittest.main()
