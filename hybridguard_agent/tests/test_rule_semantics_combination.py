"""Synthetic-only checks for the one authorized LANG_ADD_WD_REPLACE group.

Reuse hand-built prior fixture helpers without importing their TestCase classes.
No historical observation/cache is opened and no semantic candidate is invoked.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_combination as engine
from hybridguard_agent.research.rule_learning.baselines import transform_numeric
from hybridguard_agent.research.rule_learning.contracts import state
from hybridguard_agent.research.rule_learning.models import Clause, Literal
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess, V2Problem
from hybridguard_agent.research.rule_learning_v2.b_engine import frozen_atoms
from hybridguard_agent.research.rule_learning_v2.retention import diversity, retain, signal_group
from hybridguard_agent.tests.test_rule_semantics_retraining import (
    fixture, semantic, atom, LANG, WD, LANG_NUMERIC, OLD_WD, LANG_FAMILY, WD_FAMILY,
)


def binding(job, method):
    return {'study_version': 'rule-semantics-combination-v1', 'phase': 'RSR_COMBINATION',
            'group_id': 'LANG_ADD_WD_REPLACE', 'method_id': method, 'operating_point': 'OP05',
            'fold_id': job['fold_id'], 'evaluation_role': 'SYNTHETIC_ENGINEERING_FIXTURE'}


class CombinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.job, cls.rows, cls.metadata, cls.candidates = fixture()
        cls.initial, cls.initial_training = engine.fit_sparse(
            cls.job, cls.rows, cls.metadata, cls.defs,
            binding=binding(cls.job, 'GREEDY_OR'), candidate_rows=cls.candidates)

    def retain(self, *, initial=None, initial_training=None, job=None, candidates=None):
        job = self.job if job is None else job
        return engine.fit_retention(
            job, self.rows, self.metadata, self.defs, binding=binding(job, 'R_KEEP_V1'),
            candidate_rows=self.candidates if candidates is None else candidates,
            initial_model=self.initial if initial is None else initial,
            initial_training=self.initial_training if initial_training is None else initial_training)

    def old_problem(self):
        definitions = engine.group_definitions(self.defs)
        projected = engine.project_rows(self.rows, self.defs, self.candidates)
        atoms = frozen_atoms(definitions, self.initial.encoder, 'W0')
        encoded = {sid: transform_numeric(row, self.initial.encoder) for sid, row in projected.items()}
        problem = V2Problem(TrainAccess(self.job, projected, self.metadata), encoded, atoms, math.inf)
        return problem, {a.atom_id: signal_group(a) for a in atoms}

    def test_exact_two_candidate_pool_keeps_language_family_and_replaces_old_webdriver(self):
        definitions = copy.deepcopy(self.defs)
        threshold = 'CONTROL:app.web_data.navigator_layer.languages:LE:2.0'
        definitions['atoms'].append(atom(threshold, LANG_FAMILY))
        definitions['single_surface_allowlists']['app_web67'].append(threshold)
        before = copy.deepcopy(definitions)
        revised = engine.group_definitions(definitions)
        original = set(definitions['single_surface_allowlists']['app_web67'])
        actual = set(revised['single_surface_allowlists']['app_web67'])
        self.assertEqual(actual, (original - {OLD_WD}) | {LANG, WD})
        self.assertIn(LANG_NUMERIC, actual)
        self.assertIn(threshold, actual)
        self.assertEqual(definitions, before)
        by_id = {a['atom_id']: a for a in revised['atoms']}
        self.assertEqual(by_id[LANG]['family'], LANG_FAMILY)
        self.assertEqual(by_id[WD]['family'], WD_FAMILY)
        self.assertEqual(by_id[LANG]['provenance']['signal_group'], 'language_preferences')
        self.assertEqual(by_id[WD]['provenance']['signal_group'], 'automation_flag')

    def test_both_saved_cells_strictly_preserve_T_F_U_FAILED_and_missing_is_rejected(self):
        sid = self.job['train_ids'][0]
        rows = {sid: self.rows[sid]}
        for candidate in (LANG, WD):
            for value in ('T', 'F', 'U', 'FAILED'):
                with self.subTest(candidate=candidate, state=value):
                    pair = {LANG: semantic(LANG, 'F'), WD: semantic(WD, 'U')}
                    pair[candidate] = semantic(candidate, value)
                    projected = engine.project_rows(rows, self.defs, {sid: pair})
                    output = projected[sid][candidate]
                    if value == 'FAILED':
                        self.assertEqual(output['evaluation_status'], 'FAILED')
                        self.assertIs(output['value'], None)
                        self.assertIs(output['available'], False)
                    else:
                        self.assertEqual(state(output), value)
                    self.assertNotIn(OLD_WD, projected[sid])
                    self.assertEqual(projected[sid][LANG_NUMERIC], rows[sid][LANG_NUMERIC])
        for omitted in (LANG, WD):
            pair = copy.deepcopy(self.candidates[sid])
            del pair[omitted]
            with self.subTest(missing=omitted), self.assertRaises((ValueError, PermissionError)):
                engine.project_rows(rows, self.defs, {sid: pair})
        pair = copy.deepcopy(self.candidates[sid])
        pair[LANG].update(value=1, available=True)
        with self.assertRaises((ValueError, TypeError)):
            engine.project_rows(rows, self.defs, {sid: pair})

    def test_sparse_to_retention_reuses_exact_encoder_and_roundtrips_saved_models(self):
        with patch.object(engine, 'greedy', side_effect=AssertionError('retention must not run sparse search')):
            model, training = self.retain()
        self.assertEqual(self.initial.method_id, 'GREEDY_OR')
        self.assertEqual(model.method_id, 'R_KEEP_V1')
        self.assertEqual(self.initial.view['stage'], 'SPARSE')
        self.assertEqual(model.view['stage'], 'RETENTION')
        self.assertEqual(model.encoder, self.initial.encoder)
        self.assertEqual(model.fit['train_ids'], self.job['train_ids'])
        self.assertEqual(training['train_ids'], self.job['train_ids'])
        self.assertTrue(all(op['ids'] == self.job['train_ids'] for op in training['access_operations']))
        self.assertNotIn('numeric_thresholds', [op['operation'] for op in training['access_operations']])
        self.assertTrue(training['initialization']['candidate_support_and_training_score_verified'])
        with tempfile.TemporaryDirectory() as temporary:
            for stage, current_model in [('sparse', self.initial), ('retained', model)]:
                path = Path(temporary) / (stage + '.json')
                engine.save_model(current_model, path)
                restored = engine.load_model(path)
                self.assertEqual(restored.model_id, current_model.model_id)
                self.assertEqual(json.dumps(restored.to_dict(), sort_keys=True), json.dumps(current_model.to_dict(), sort_keys=True))
                for sid in self.job['train_ids'][:2]:
                    left = engine.predict_current(current_model, 'fixture-current', self.rows[sid], self.candidates[sid])
                    right = engine.predict_current(restored, 'fixture-current', self.rows[sid], self.candidates[sid])
                    self.assertEqual(left, right)

    def test_old_group_wrong_stage_or_train_scope_cannot_authorize_initialization(self):
        alternatives = [
            replace(self.initial, binding=dict(self.initial.binding, group_id='LANG_ADD')),
            replace(self.initial, binding=dict(self.initial.binding, study_version='rule-semantics-retraining-v1', phase='RSR_RETRAINING')),
            replace(self.initial, binding=dict(self.initial.binding, fold_id='fixture-other-fold')),
            replace(self.initial, method_id='R_KEEP_V1'),
            replace(self.initial, fit=dict(self.initial.fit, train_ids=self.job['train_ids'][:-1])),
        ]
        with patch.object(engine, 'retain', side_effect=AssertionError('bad initializer reached retention')):
            for initial in alternatives:
                with self.subTest(binding=initial.binding, method=initial.method_id), \
                     self.assertRaises((ValueError, PermissionError)):
                    self.retain(initial=initial)
            overlap = dict(self.job, outer_test_ids=[self.job['train_ids'][0]])
            with self.assertRaises((ValueError, PermissionError)):
                self.retain(job=overlap)
            contaminated = copy.deepcopy(self.candidates)
            contaminated['fixture-heldout'] = {LANG: semantic(LANG, 'T'), WD: semantic(WD, 'T')}
            with self.assertRaises((ValueError, PermissionError)):
                self.retain(candidates=contaminated)

    def test_original_retention_positive_signal_increment_and_group_dedup_are_unchanged(self):
        problem, groups = self.old_problem()
        expected, outcome, trace = retain(problem, self.initial.clauses, groups, math.inf)
        model, training = self.retain()
        self.assertEqual(model.clauses, expected)
        self.assertEqual(training['trace'], trace)
        self.assertEqual(model.fit['D_initial'], outcome['D_initial'])
        self.assertEqual(model.fit['D_final'], outcome['D_final'])
        self.assertTrue(all(row['delta_D'] > 0 for row in training['trace']))
        self.assertEqual(groups[LANG], 'language_preferences')
        self.assertEqual(groups[WD], 'automation_flag')
        old_id = next(a.atom_id for a in problem.atoms if a.atom_id == 'CONTROL:app.web_data.navigator_layer.languages:LE:1.0')
        old = Clause((Literal(old_id, 'NEGATIVE'),))
        new = Clause((Literal(LANG, 'POSITIVE'),))
        self.assertEqual(diversity(problem, (old,), groups), diversity(problem, (old, new), groups))

    def test_webdriver_U_support_rejection_keeps_full_train_denominator(self):
        model, training = self.retain()
        self.assertEqual(model.fit['train_consumed_n'], len(self.rows))
        self.assertNotIn(WD, {a.atom_id for a in model.atoms})
        self.assertNotIn(OLD_WD, model.encoder['fixed_atoms'])
        self.assertIn(LANG_NUMERIC, model.encoder['numeric'])
        for polarity in ('POSITIVE', 'NEGATIVE'):
            cid = WD + ':' + polarity
            support = training['support'][cid]
            self.assertEqual(support['triplets'], 0)
            self.assertEqual(support['phase_availability']['clean_pre']['U'], 6)
            self.assertEqual(support['phase_availability']['clean_post']['U'], 6)
            item = next(x for x in training['candidate_manifest'] if x['clause_id'] == cid)
            self.assertFalse(item['eligible'])
            self.assertIn('INSUFFICIENT_TRAIN_SUPPORT', item['reasons'])

    def test_sparse_and_retention_exceptions_preserve_FAILED_without_retry(self):
        with patch.object(engine, 'greedy', side_effect=RuntimeError('SYNTHETIC_SPARSE_FAILURE')) as sparse_call:
            sparse, sparse_training = engine.fit_sparse(
                self.job, self.rows, self.metadata, self.defs,
                binding=binding(self.job, 'GREEDY_OR'), candidate_rows=self.candidates)
        with patch.object(engine, 'retain', side_effect=RuntimeError('SYNTHETIC_RETAIN_FAILURE')) as retain_call:
            retained, retained_training = self.retain()
        self.assertEqual(sparse_call.call_count, 1)
        self.assertEqual(retain_call.call_count, 1)
        for model, training, reason in [(sparse, sparse_training, 'SYNTHETIC_SPARSE_FAILURE'),
                                       (retained, retained_training, 'SYNTHETIC_RETAIN_FAILURE')]:
            with self.subTest(method=model.method_id):
                self.assertEqual(model.status, 'FAILED')
                self.assertEqual(model.clauses, ())
                self.assertEqual(model.fit['train_ids'], self.job['train_ids'])
                self.assertIn(reason, str(model.fit) + str(training))
                self.assertEqual(engine.predict_current(model, 'fixture-current', self.rows[self.job['train_ids'][0]],
                                                        self.candidates[self.job['train_ids'][0]])['decision'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
