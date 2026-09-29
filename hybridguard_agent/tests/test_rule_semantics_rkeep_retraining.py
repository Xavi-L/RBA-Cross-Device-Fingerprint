"""Focused R_KEEP boundary checks on hand-built fixtures, never real records.

The four GREEDY initializers below are synthetic setup only. This suite does not
open any historical model, source observation, label record, or candidate cache.
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

from hybridguard_agent.research import rule_semantics_retraining as greedy_engine
from hybridguard_agent.research import rule_semantics_rkeep_retraining as engine
from hybridguard_agent.research.rule_learning.baselines import transform_numeric
from hybridguard_agent.research.rule_learning.models import Clause, Literal
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess, V2Problem
from hybridguard_agent.research.rule_learning_v2.b_engine import frozen_atoms
from hybridguard_agent.research.rule_learning_v2.retention import diversity, retain, signal_group
from hybridguard_agent.tests.test_rule_semantics_retraining import (
    LANG, WD, LANG_NUMERIC, OLD_WD, fixture, binding as greedy_binding,
    candidate_rows, semantic,
)


def retention_binding(job, group):
    return {'study_version': 'rule-semantics-rkeep-retraining-v1', 'phase': 'RSR_RKEEP_RETRAINING',
            'method_id': 'R_KEEP_V1', 'operating_point': 'OP05', 'fold_id': job['fold_id'],
            'group_id': group, 'evaluation_role': 'SYNTHETIC_ENGINEERING_FIXTURE'}


class RkeepRetrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.job, cls.rows, cls.metadata, cls.candidates = fixture()
        cls.initials = {}
        for group in ('BASE', 'LANG_ADD', 'LANG_REPLACE', 'WD_REPLACE'):
            cls.initials[group] = greedy_engine.fit_group(
                cls.job, cls.rows, cls.metadata, cls.defs, group=group,
                binding=greedy_binding(cls.job, group), candidate_rows=candidate_rows(cls.candidates, group))

    def run_retention(self, group, *, initial=None, training=None, job=None, rows=None, metadata=None):
        model, initial_training = self.initials[group]
        job = self.job if job is None else job
        return engine.fit_group(job, self.rows if rows is None else rows,
                                self.metadata if metadata is None else metadata,
                                self.defs, group=group, binding=retention_binding(job, group),
                                candidate_rows=candidate_rows(self.candidates, group),
                                initial_model=model if initial is None else initial,
                                initial_training=initial_training if training is None else training)

    def old_problem(self, group):
        initial, _ = self.initials[group]
        selected = greedy_engine.group_definitions(self.defs, group)
        projected = greedy_engine.project_rows(self.rows, self.defs, group, candidate_rows(self.candidates, group))
        atoms = frozen_atoms(selected, initial.encoder, 'W0')
        encoded = {sid: transform_numeric(row, initial.encoder) for sid, row in projected.items()}
        access = TrainAccess(self.job, projected, self.metadata)
        problem = V2Problem(access, encoded, atoms, math.inf)
        groups = {a.atom_id: signal_group(a) for a in atoms}
        return problem, groups

    def test_saved_initialization_reuses_encoder_and_never_refits_greedy_or_quantiles(self):
        initial, _ = self.initials['LANG_REPLACE']
        before = json.dumps(initial.to_dict(), sort_keys=True)
        with patch.object(greedy_engine, 'encode_train', side_effect=AssertionError('hidden numeric fit')), \
             patch.object(greedy_engine, 'greedy', side_effect=AssertionError('hidden sparse fit')):
            model, training = self.run_retention('LANG_REPLACE')
        self.assertEqual(model.method_id, 'R_KEEP_V1')
        self.assertEqual(model.encoder, initial.encoder)
        self.assertEqual(model.fit['train_ids'], self.job['train_ids'])
        self.assertEqual(model.fit['actual_fit_invocations'], 1)
        self.assertEqual(model.fit['actual_retention_invocations'], 1)
        self.assertEqual(model.fit['new_sparse_fit_calls'], 0)
        self.assertEqual(model.fit['threshold_fit_calls'], 0)
        self.assertEqual(model.fit['candidate_evaluations'], 0)
        self.assertEqual(json.dumps(initial.to_dict(), sort_keys=True), before)
        self.assertNotIn('numeric_thresholds', [op['operation'] for op in training['access_operations']])
        self.assertTrue(training['initialization']['candidate_support_and_training_score_verified'])

    def test_wrong_initial_group_fold_train_members_and_status_reject_before_retention(self):
        initial, _ = self.initials['LANG_REPLACE']
        invalid = [
            replace(initial, binding=dict(initial.binding, group_id='BASE')),
            replace(initial, binding=dict(initial.binding, fold_id='fixture-other-fold')),
            replace(initial, method_id='R_KEEP_V1'),
            replace(initial, fit=dict(initial.fit, train_ids=initial.fit['train_ids'][:-1])),
            replace(initial, encoder=dict(initial.encoder, train_ids=initial.encoder['train_ids'][:-1])),
            replace(initial, status='FAILED', clauses=(), atoms=()),
        ]
        with patch.object(engine, 'retain', side_effect=AssertionError('invalid initial reached retention')):
            for wrong in invalid:
                with self.subTest(status=wrong.status, method=wrong.method_id, binding=wrong.binding), \
                     self.assertRaises((ValueError, PermissionError)):
                    self.run_retention('LANG_REPLACE', initial=wrong)
            overlapping = copy.deepcopy(self.job)
            overlapping['outer_test_ids'] = [self.job['train_ids'][0]]
            with self.assertRaises((ValueError, PermissionError)):
                self.run_retention('LANG_REPLACE', job=overlapping)

    def test_initial_threshold_candidate_pool_and_support_changes_are_rejected(self):
        initial, original_training = self.initials['LANG_ADD']
        bad_encoder = copy.deepcopy(initial.encoder)
        numeric = next(iter(bad_encoder['numeric'].values()))
        numeric['thresholds'][0] += 0.5
        tampered = replace(initial, encoder=bad_encoder)
        with self.assertRaises((ValueError, PermissionError)):
            self.run_retention('LANG_ADD', initial=tampered)
        variants = []
        missing_pool = copy.deepcopy(original_training)
        missing_pool['candidate_manifest'].pop()
        variants.append(missing_pool)
        wrong_support = copy.deepcopy(original_training)
        next(iter(wrong_support['support'].values()))['triplets'] += 1
        variants.append(wrong_support)
        for training in variants:
            with self.subTest(keys=list(training)), self.assertRaises((ValueError, PermissionError)):
                self.run_retention('LANG_ADD', training=training)

    def test_removed_language_and_webdriver_atoms_cannot_return_through_saved_encoder(self):
        baseline = self.initials['BASE'][0]
        for group in ('LANG_REPLACE', 'WD_REPLACE'):
            with self.subTest(group=group):
                initial, _ = self.initials[group]
                encoder = copy.deepcopy(initial.encoder)
                if group == 'LANG_REPLACE':
                    encoder['numeric'][LANG_NUMERIC] = copy.deepcopy(baseline.encoder['numeric'][LANG_NUMERIC])
                else:
                    encoder['fixed_atoms'].append(OLD_WD)
                contaminated = replace(initial, encoder=encoder)
                with patch.object(engine, 'retain', side_effect=AssertionError('removed atom reintroduced')), \
                     self.assertRaises((ValueError, PermissionError)):
                    self.run_retention(group, initial=contaminated)

    def test_original_retain_math_and_language_signal_group_are_preserved(self):
        group = 'LANG_ADD'
        problem, groups = self.old_problem(group)
        initial = self.initials[group][0]
        expected, outcome, trace = retain(problem, initial.clauses, groups, math.inf)
        model, training = self.run_retention(group)
        self.assertEqual(model.clauses, expected)
        self.assertEqual(model.fit['D_initial'], outcome['D_initial'])
        self.assertEqual(model.fit['D_final'], outcome['D_final'])
        self.assertEqual(training['trace'], trace)
        self.assertEqual(training['signal_groups'][LANG], 'language_preferences')
        length_id = next(a.atom_id for a in problem.atoms if a.atom_id.startswith('CONTROL:app.web_data.navigator_layer.languages:LE:1.0'))
        old_clause = Clause((Literal(length_id, 'NEGATIVE'),))
        new_clause = Clause((Literal(LANG, 'POSITIVE'),))
        self.assertEqual(groups[length_id], groups[LANG])
        self.assertEqual(diversity(problem, (old_clause,), groups),
                         diversity(problem, (old_clause, new_clause), groups))

    def test_webdriver_unknowns_keep_full_denominator_and_fail_original_support(self):
        model, training = self.run_retention('WD_REPLACE')
        self.assertEqual(model.fit['train_consumed_n'], len(self.rows))
        self.assertEqual(training['train_ids'], self.job['train_ids'])
        self.assertNotIn(WD, {a.atom_id for a in model.atoms})
        self.assertNotIn(OLD_WD, model.encoder['fixed_atoms'])
        for polarity in ('POSITIVE', 'NEGATIVE'):
            cid = WD + ':' + polarity
            support = training['support'][cid]
            self.assertEqual(support['triplets'], 0)
            self.assertEqual(support['phase_availability']['clean_pre']['U'], 6)
            self.assertEqual(support['phase_availability']['clean_post']['U'], 6)
            item = next(row for row in training['candidate_manifest'] if row['clause_id'] == cid)
            self.assertFalse(item['eligible'])
            self.assertIn('INSUFFICIENT_TRAIN_SUPPORT', item['reasons'])

    def test_save_load_preserves_identity_and_synthetic_current_row_predictions(self):
        model, _ = self.run_retention('LANG_REPLACE')
        self.assertIn(LANG, {a.atom_id for a in model.atoms})
        raw = self.rows[self.job['train_ids'][0]]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic-rkeep-model.json'
            engine.save_model(model, path)
            restored = engine.load_model(path)
            self.assertEqual(restored.model_id, model.model_id)
            self.assertEqual(json.dumps(restored.to_dict(), sort_keys=True), json.dumps(model.to_dict(), sort_keys=True))
            for value, decision in [('T', 'MANIPULATION_ALERT'), ('F', 'NO_ALERT'),
                                    ('U', 'INSUFFICIENT_EVIDENCE'), ('FAILED', 'FAILED')]:
                with self.subTest(candidate_state=value):
                    current = {LANG: semantic(LANG, value)}
                    before = engine.predict_current(model, 'fixture-rkeep-current', raw, current)
                    after = engine.predict_current(restored, 'fixture-rkeep-current', raw, current)
                    self.assertEqual(after, before)
                    self.assertEqual(after['decision'], decision)

    def test_retention_executor_failure_is_preserved_without_fallback_or_retry(self):
        with patch.object(engine, 'retain', side_effect=RuntimeError('SYNTHETIC_RETAIN_FAILURE')) as call:
            model, training = self.run_retention('BASE')
        self.assertEqual(call.call_count, 1)
        self.assertEqual(model.status, 'FAILED')
        self.assertEqual(model.clauses, ())
        self.assertEqual(model.fit['train_ids'], self.job['train_ids'])
        self.assertEqual(model.fit['actual_fit_invocations'], 1)
        self.assertEqual(model.fit['actual_retention_invocations'], 1)
        self.assertEqual(model.fit['new_sparse_fit_calls'], 0)
        self.assertEqual(model.fit['threshold_fit_calls'], 0)
        self.assertIn('SYNTHETIC_RETAIN_FAILURE', str(model.fit) + str(training))
        self.assertEqual(engine.predict_current(model, 'fixture-rkeep-current', self.rows[self.job['train_ids'][0]])['decision'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
