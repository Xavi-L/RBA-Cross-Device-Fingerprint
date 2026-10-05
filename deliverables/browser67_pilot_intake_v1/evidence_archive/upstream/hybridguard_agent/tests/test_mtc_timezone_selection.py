"""Synthetic extension boundaries; no real experiment fit is run by these tests."""
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest

from hybridguard_agent.tests.test_mtc_constrained_selection import fixture
from hybridguard_agent.research import mtc_constrained_reselection as old_engine
from hybridguard_agent.research import mtc_timezone_selection as engine
from hybridguard_agent.research import mtc_timezone_candidates as adapter
from hybridguard_agent.research import mtc_timezone_relation as resource
from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.predictor import clause_state


def example(mtc_n=20):
    defs, job, rows, meta, mtc, mtc_meta = fixture(fields=('irrelevant',), mtc_n=mtc_n)
    for row in (*rows.values(), *mtc.values()):
        row['fixture:irrelevant'] = cell('F')
    atoms = adapter.registered_atoms()
    memory = resource.registered_atoms()[0].atom_id
    rel = {sid: {a.atom_id: cell('T' if a.atom_id == memory and meta[sid]['phase'] == 'attack' else 'F')
                 for a in atoms} for sid in rows}
    mr = {sid: {a.atom_id: cell('F') for a in atoms} for sid in mtc}
    return [defs, job, rows, meta, mtc, mtc_meta, rel, mr]


def prepare(data, **extra):
    defs, job, rows, meta, mtc, mm, rel, mr = data
    return engine.prepare_fold(job, rows, meta, defs, mtc, mm, rel, mr,
        adapter.registered_atoms(), adapter.parameters(), mtc_train_ids=list(mtc),
        mtc_evaluation_ids=['not-training'], **extra)


class TimezoneSelectionTests(unittest.TestCase):
    def test_explicit_cross_surface_and_same_encoder_no_bonus(self):
        data = example()
        original = old_engine.prepare_fold(data[1], data[2], data[3], data[0], data[4], data[5],
            mtc_train_ids=list(data[4]), mtc_evaluation_ids=['not-training'])
        prepared = prepare(data, expected_old_encoder=original.encoder)
        self.assertEqual(prepared.common.encoder, original.encoder)
        memory = resource.registered_atoms()[0]
        self.assertEqual(set(memory.surfaces), {'native84', 'app_web67'})
        self.assertEqual(engine.semantic_catalog(prepared.common.atoms)[memory.atom_id]['quality'], 0)
        self.assertEqual(len(prepared.common.encoder['fixed_atoms']), 1)
        bad = deepcopy(original.encoder); bad['train_ids'] = ['not-training']
        with self.assertRaisesRegex(ValueError, 'OLD_CONTROLLED_TRAIN_ENCODER_CHANGED'):
            prepare(data, expected_old_encoder=bad)

    def test_new_relation_cannot_exceed_mtc_or_controlled_budget(self):
        data = example()
        aid = resource.registered_atoms()[0].atom_id
        for sid in list(data[7])[:2]:
            data[7][sid][aid] = cell('T')  # Two observed normal contradictions, not U.
        p = prepare(data)
        model, train = engine.fit(p, stage='SPARSE')
        self.assertEqual(model.status, 'EMPTY_MODEL')
        stat = next(x for x in train['candidate_statistics'] if x['clause_id'] == aid+':POSITIVE')
        self.assertEqual(stat['mtc_normal']['T'], 2)
        self.assertIn('MTC_SET_NORMAL_BUDGET', stat['selection_reasons'])
        # A separate controlled budget violation cannot be diluted by MTC.
        data = example()
        for sid in [s for s,m in data[3].items() if m['phase']=='clean_pre'][:2]:
            data[6][sid][aid] = cell('T')
        model, train = engine.fit(prepare(data), stage='SPARSE')
        self.assertEqual(model.status, 'EMPTY_MODEL')

    def test_b_coverage_and_own_retention_initialization(self):
        data = example(mtc_n=100)
        aid = resource.registered_atoms()[0].atom_id
        for sid in list(data[7])[:11]: data[7][sid][aid] = cell('U')
        model, train = engine.fit(prepare(data), stage='SPARSE')
        self.assertEqual(model.status, 'EMPTY_MODEL')
        stat = next(x for x in train['candidate_statistics'] if x['clause_id']==aid+':POSITIVE')
        self.assertIn('MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT', stat['admission_reasons'])
        good = prepare(example())
        sparse, st = engine.fit(good, stage='SPARSE')
        retained, rt = engine.fit(good, stage='RETENTION', initial_model=sparse, initial_training=st)
        self.assertEqual(retained.status, 'FITTED')
        self.assertEqual(retained.fit['initialization']['model_id'], sparse.model_id)
        self.assertEqual(retained.encoder, sparse.encoder)
        with self.assertRaises(PermissionError):
            engine.fit(good, stage='RETENTION', initial_model=retained, initial_training=rt)

    def test_exact_training_relation_members_and_fixed_parameters(self):
        data = example()
        data[6]['not-training'] = next(iter(data[6].values()))
        with self.assertRaises(PermissionError): prepare(data)
        data = example()
        params = adapter.parameters(); params['fitted'] = True
        with self.assertRaisesRegex(ValueError, 'FIXED_SEMANTIC'):
            engine.prepare_fold(data[1],data[2],data[3],data[0],data[4],data[5],data[6],data[7],
                adapter.registered_atoms(),params,mtc_train_ids=list(data[4]))

    def test_model_roundtrip_polarity_and_label_free_current_prediction(self):
        data = example()
        model, _ = engine.fit(prepare(data), stage='SPARSE')
        aid = resource.registered_atoms()[0].atom_id
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.json'
            engine.save_model(model,path)
            restored = engine.load_model(path)
            self.assertEqual(model.model_id, restored.model_id)
            raw = {**next(iter(data[2].values())), **{a.atom_id:cell('F') for a in adapter.registered_atoms()}}
            raw[aid] = cell('T')
            self.assertEqual(engine.predict_current(restored, 'any-id',raw)['decision'],'MANIPULATION_ALERT')
            raw.update(label='normal', model='tablet', phase='clean_post', source='MTC')
            self.assertEqual(engine.predict_current(restored,'other-id',raw)['decision'],'MANIPULATION_ALERT')
            raw[aid]=cell('U')
            self.assertEqual(engine.predict_current(restored,'any-id',raw)['decision'],'INSUFFICIENT_EVIDENCE')
            self.assertEqual(clause_state(model.clauses[0],{aid:cell('F')}),'F')

    def test_new_relation_or_union_and_retention_keep_separate_budget(self):
        data = example()
        names = [a.atom_id for a in adapter.registered_atoms()][-2:]
        for sid, meta in data[3].items():
            data[6][sid].update({name: cell('T' if meta['phase'] == 'attack' else 'F') for name in names})
        for number, name in enumerate(names):
            data[7][list(data[7])[number]][name] = cell('T')
        prepared = prepare(data)
        problem, _ = old_engine._problem(prepared.common, 'B', time.monotonic()+60)
        positive = [next(c for c in problem.candidates if c.id == name+':POSITIVE') for name in names]
        self.assertTrue(all(problem.score((c,))['feasible'] for c in positive))
        union = problem.score(positive)
        self.assertEqual((union['clean_alarms'], union['mtc_alarms'], union['mtc_budget']), (0, 2, 1))
        self.assertFalse(union['partial_feasible'])
        self.assertFalse(union['feasible'])
        sparse, training = engine.fit(prepared, stage='SPARSE')
        retained, _ = engine.fit(prepared, stage='RETENTION', initial_model=sparse, initial_training=training)
        self.assertEqual(len(retained.clauses), 1)
        self.assertEqual(retained.fit['training_result']['mtc_alarms'], 1)

    def test_two_individually_available_relations_cannot_break_final_or_coverage(self):
        data = example(mtc_n=100)
        names = [a.atom_id for a in adapter.registered_atoms()][-2:]
        for sid, meta in data[3].items():
            data[6][sid].update({name: cell('T' if meta['phase'] == 'attack' else 'F') for name in names})
        for number, name in enumerate(names):
            for sid in list(data[7])[number*10:(number+1)*10]:
                data[7][sid][name] = cell('U')
        prepared = prepare(data)
        problem, _ = old_engine._problem(prepared.common, 'B', time.monotonic()+60)
        positive = [next(c for c in problem.candidates if c.id == name+':POSITIVE') for name in names]
        self.assertTrue(all(problem.score((c,))['feasible'] for c in positive))
        self.assertEqual(float(problem.score(positive)['mtc_coverage']), 0.8)
        self.assertFalse(problem.score(positive)['feasible'])
        sparse, training = engine.fit(prepared, stage='SPARSE')
        retained, _ = engine.fit(prepared, stage='RETENTION', initial_model=sparse, initial_training=training)
        self.assertEqual(len(retained.clauses), 1)
        self.assertEqual(retained.fit['training_result']['mtc_state_counts']['defined'], 90)

    def test_old_model_identity_rejected_and_missing_relation_is_failure(self):
        data = example()
        model, _ = engine.fit(prepare(data), stage='SPARSE')
        self.assertTrue(model.model_id.startswith('mtc-rel-tz-'))
        self.assertEqual(engine.predict_current(model, 'current', {})['decision'], 'FAILED')
        original = old_engine.prepare_fold(data[1], data[2], data[3], data[0], data[4], data[5],
            mtc_train_ids=list(data[4]), mtc_evaluation_ids=['not-training'])
        old_model, old_training = old_engine.fit_sparse(original, scheme='B')
        with self.assertRaises(TypeError):
            engine.predict_current(old_model, 'current', {})
        with self.assertRaises(PermissionError):
            engine.fit(prepare(data), stage='RETENTION', initial_model=old_model, initial_training=old_training)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'relation.json'
            engine.save_model(model, path)
            with self.assertRaises(ValueError):
                old_engine.load_model(path)


if __name__ == '__main__':
    unittest.main()
