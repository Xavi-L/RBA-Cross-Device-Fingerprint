"""Focused synthetic tests for the four frozen-semantic retraining adapters.

All observations below are hand-built fixture records. No real source file,
module candidate evaluation, production row, or old experiment is executed.
"""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_retraining as retraining
from hybridguard_agent.research.rule_learning.contracts import cell, state
from hybridguard_agent.research.rule_learning.models import Clause, Literal
from hybridguard_agent.research.rule_learning.predictor import clause_state

LANG = 'RSR-LANG-FIRST-v1'
WD = 'RSR-WEBDRIVER-STATE-v1'
LANG_FIELD = 'app.web_data.navigator_layer.languages'
LANG_NUMERIC = 'UNFITTED_CONTROL:' + LANG_FIELD
HARDWARE = 'UNFITTED_CONTROL:app.web_data.navigator_layer.hardware_concurrency'
OLD_WD = 'CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True'
LANG_FAMILY = 'CONTROL_FIELD:' + LANG_FIELD
WD_FAMILY = 'CONTROL_FIELD:app.web_data.automation_surface_layer.webdriver'


def semantic(candidate, value):
    return dict(cell(value), candidate_id=candidate, version='1.0.0',
                reason='SYNTHETIC_HAND_SPECIFIED_NOT_MODULE_EVALUATION',
                source_reason=None, diagnostics={'real_sample': False})


def atom(name, family, *, numeric=False):
    return {'atom_id': name, 'family': family, 'surfaces': ['app_web67'],
            'sources': ['SYNTHETIC_SOURCE_ONLY'], 'aliases': [name],
            'orientation': 'UNFITTED_NUMERIC_MEASUREMENT' if numeric else 'CANONICAL_DEVIATION',
            'provenance': {'real_sample': False, 'field': name.split(':')[1]}}


def fixture(*, baseline_discriminates=True):
    definitions = {'atoms': [atom(LANG_NUMERIC, LANG_FAMILY, numeric=True),
                             atom(HARDWARE, 'CONTROL_FIELD:hardware', numeric=True),
                             atom(OLD_WD, WD_FAMILY)],
                   'single_surface_allowlists': {'native84': [], 'host26': [],
                                                'app_web67': [LANG_NUMERIC, HARDWARE, OLD_WD]}}
    rows, metadata, candidates = {}, {}, {}
    for triplet in range(6):
        for phase in ('clean_pre', 'attack', 'clean_post'):
            oid = f'fixture-rsr-{triplet}-{phase}'
            attack = phase == 'attack'
            rows[oid] = {
                LANG_NUMERIC: {'value': 3 if attack else 1, 'available': True, 'evaluation_status': 'OK'},
                HARDWARE: {'value': 8 if attack and baseline_discriminates else 2,
                           'available': True, 'evaluation_status': 'OK'},
                OLD_WD: cell('T' if attack and baseline_discriminates else 'F'),
            }
            metadata[oid] = {'supervised_label': int(attack), 'phase': phase,
                             'bundle_id': 'fixture-rsr-bundle', 'triplet_id': str(triplet),
                             'environment_group_id': 'fixture-rsr-env', 'config_id': 'fixture-rsr-config'}
            candidates[oid] = {LANG: semantic(LANG, 'T' if attack else 'F'),
                               WD: semantic(WD, 'T' if attack else 'U')}
    job = {'fold_id': 'fixture-rsr-fold', 'train_ids': list(rows),
           'outer_test_ids': ['fixture-rsr-outer-test'], 'representation': 'W0'}
    return definitions, job, rows, metadata, candidates


def binding(job, group, **changes):
    value = {'study_version': 'rule-semantics-retraining-v1', 'phase': 'RSR_RETRAINING',
             'group_id': group, 'method_id': 'GREEDY_OR', 'operating_point': 'OP05',
             'fold_id': job['fold_id'], 'evaluation_role': 'SYNTHETIC_ENGINEERING_FIXTURE'}
    value.update(changes)
    return value


def candidate_rows(candidates, group):
    if group == 'BASE':
        return None
    candidate_id = WD if group == 'WD_REPLACE' else LANG
    return {oid: {candidate_id: values[candidate_id]} for oid, values in candidates.items()}


def names(definitions):
    return set(definitions['single_surface_allowlists']['app_web67'])


class RuleSemanticsRetrainingTests(unittest.TestCase):
    def test_A_preserves_original_W0_pool_and_input_objects(self):
        definitions, _, rows, _, _ = fixture()
        before = copy.deepcopy((definitions, rows))
        output = retraining.group_definitions(definitions, 'BASE')
        projected = retraining.project_rows(rows, definitions, 'BASE')
        self.assertEqual(output, definitions)
        self.assertEqual(projected, rows)
        self.assertEqual((definitions, rows), before)
        projected[next(iter(projected))][OLD_WD]['value'] = 'changed copy'
        self.assertEqual((definitions, rows), before)

    def test_B_adds_exactly_one_language_atom_without_removing_originals(self):
        definitions, _, rows, _, candidates = fixture()
        output = retraining.group_definitions(definitions, 'LANG_ADD')
        self.assertEqual(names(output), names(definitions) | {LANG})
        self.assertEqual(len(output['atoms']), len(definitions['atoms']) + 1)
        projected = retraining.project_rows(rows, definitions, 'LANG_ADD', candidate_rows(candidates, 'LANG_ADD'))
        for oid, row in projected.items():
            self.assertEqual(set(row), set(rows[oid]) | {LANG})
            for old_id, old_value in rows[oid].items():
                self.assertEqual(row[old_id], old_value)
            self.assertEqual(state(row[LANG]), 'T' if oid.endswith('-attack') else 'F')

    def test_C_removes_every_language_length_threshold_but_no_other_atom(self):
        definitions, _, rows, _, candidates = fixture()
        threshold_ids = ['CONTROL:' + LANG_FIELD + ':LE:1.0', 'CONTROL:' + LANG_FIELD + ':LE:2.0']
        unrelated = 'CONTROL:' + LANG_FIELD + '_unrelated:LE:1.0'
        for name in threshold_ids + [unrelated]:
            definitions['atoms'].append(atom(name, LANG_FAMILY if name in threshold_ids else 'CONTROL_FIELD:unrelated'))
            definitions['single_surface_allowlists']['app_web67'].append(name)
            for row in rows.values():
                row[name] = cell('F')
        before = copy.deepcopy((definitions, rows, candidates))
        output = retraining.group_definitions(definitions, 'LANG_REPLACE')
        removed = {LANG_NUMERIC, *threshold_ids}
        self.assertEqual(names(output), (names(definitions) - removed) | {LANG})
        self.assertTrue(removed.isdisjoint({entry['atom_id'] for entry in output['atoms']}))
        projected = retraining.project_rows(rows, definitions, 'LANG_REPLACE', candidate_rows(candidates, 'LANG_REPLACE'))
        for oid, row in projected.items():
            self.assertEqual(set(row), (set(rows[oid]) - removed) | {LANG})
            self.assertEqual(row[unrelated], rows[oid][unrelated])
            self.assertEqual(row[OLD_WD], rows[oid][OLD_WD])
            self.assertEqual(row[HARDWARE], rows[oid][HARDWARE])
        self.assertEqual((definitions, rows, candidates), before)

    def test_D_replaces_only_old_webdriver_and_preserves_U_without_coercion(self):
        definitions, _, rows, _, candidates = fixture()
        output = retraining.group_definitions(definitions, 'WD_REPLACE')
        self.assertEqual(names(output), (names(definitions) - {OLD_WD}) | {WD})
        projected = retraining.project_rows(rows, definitions, 'WD_REPLACE', candidate_rows(candidates, 'WD_REPLACE'))
        for oid, row in projected.items():
            self.assertNotIn(OLD_WD, row)
            self.assertEqual(row[LANG_NUMERIC], rows[oid][LANG_NUMERIC])
            self.assertEqual(row[HARDWARE], rows[oid][HARDWARE])
            self.assertEqual(state(row[WD]), 'T' if oid.endswith('-attack') else 'U')

    def test_new_cell_conversion_accepts_four_encodings_and_rejects_invalid_contracts(self):
        definitions, _, all_rows, _, _ = fixture()
        oid = next(iter(all_rows))
        rows = {oid: all_rows[oid]}
        for expected in ('T', 'F', 'U', 'FAILED'):
            with self.subTest(state=expected):
                projected = retraining.project_rows(rows, definitions, 'LANG_ADD', {oid: {LANG: semantic(LANG, expected)}})
                actual = projected[oid][LANG]
                self.assertEqual(actual['evaluation_status'], 'FAILED' if expected == 'FAILED' else 'OK')
                if expected == 'FAILED':
                    self.assertIs(actual['available'], False)
                    self.assertIsNone(actual['value'])
                else:
                    self.assertEqual(state(actual), expected)
        for changes in ({'candidate_id': WD}, {'version': 'invented'}, {'value': 1},
                        {'available': 1}, {'evaluation_status': 'NOT_REQUESTED'},
                        {'value': True, 'available': False}):
            with self.subTest(changes=changes):
                value = semantic(LANG, 'T') | changes
                with self.assertRaises((ValueError, TypeError)):
                    retraining.project_rows(rows, definitions, 'LANG_ADD', {oid: {LANG: value}})

    def test_train_boundary_rejects_extra_missing_and_outer_members_before_fit(self):
        definitions, job, rows, metadata, candidates = fixture()
        crows = candidate_rows(candidates, 'LANG_ADD')
        extra = copy.deepcopy(crows)
        extra['fixture-rsr-outer-test'] = {LANG: semantic(LANG, 'T')}
        missing = copy.deepcopy(crows)
        del missing[job['train_ids'][0]]
        for bad_candidates in (extra, missing):
            with self.subTest(candidate_ids=list(bad_candidates)):
                with self.assertRaises((ValueError, PermissionError)):
                    retraining.fit_group(job, rows, metadata, definitions, group='LANG_ADD',
                                         binding=binding(job, 'LANG_ADD'), candidate_rows=bad_candidates)
        contaminated_rows = copy.deepcopy(rows)
        contaminated_metadata = copy.deepcopy(metadata)
        contaminated_rows['fixture-rsr-outer-test'] = copy.deepcopy(rows[job['train_ids'][0]])
        contaminated_metadata['fixture-rsr-outer-test'] = copy.deepcopy(metadata[job['train_ids'][0]])
        with self.assertRaises((ValueError, PermissionError)):
            retraining.fit_group(job, contaminated_rows, contaminated_metadata, definitions,
                                 group='BASE', binding=binding(job, 'BASE'))
        overlap = copy.deepcopy(job)
        overlap['outer_test_ids'] = [job['train_ids'][0]]
        with self.assertRaises((ValueError, PermissionError)):
            retraining.fit_group(overlap, rows, metadata, definitions, group='BASE', binding=binding(overlap, 'BASE'))

    def test_negative_polarity_leaves_unknown_and_new_atoms_share_original_families(self):
        definitions, _, rows, _, candidates = fixture()
        for group, new_id, old_family in [('LANG_ADD', LANG, LANG_FAMILY), ('WD_REPLACE', WD, WD_FAMILY)]:
            with self.subTest(group=group):
                output = retraining.group_definitions(definitions, group)
                self.assertEqual(next(a['family'] for a in output['atoms'] if a['atom_id'] == new_id), old_family)
                clause = Clause((Literal(new_id, 'NEGATIVE'),))
                self.assertEqual(clause_state(clause, {new_id: semantic(new_id, 'U')}), 'U')
                self.assertEqual(clause_state(clause, {new_id: semantic(new_id, 'T')}), 'F')
                self.assertEqual(clause_state(clause, {new_id: semantic(new_id, 'F')}), 'T')

    def test_synthetic_webdriver_U_causes_support_rejection_without_dropping_rows(self):
        definitions, job, rows, metadata, candidates = fixture()
        model, training = retraining.fit_group(job, rows, metadata, definitions, group='WD_REPLACE',
                                               binding=binding(job, 'WD_REPLACE'),
                                               candidate_rows=candidate_rows(candidates, 'WD_REPLACE'))
        self.assertEqual(model.fit['train_ids'], job['train_ids'])
        self.assertEqual(model.fit['train_consumed_n'], len(job['train_ids']))
        for polarity in ('POSITIVE', 'NEGATIVE'):
            clause_id = WD + ':' + polarity
            item = next(item for item in training['candidate_manifest'] if item['clause_id'] == clause_id)
            self.assertFalse(item['eligible'])
            self.assertIn('INSUFFICIENT_TRAIN_SUPPORT', item['reasons'])
            support = training['support'][clause_id]
            self.assertEqual(support['triplets'], 0)
            self.assertEqual(support['phase_availability']['clean_pre']['U'], 6)
            self.assertEqual(support['phase_availability']['clean_pre']['expected'], 6)
        self.assertNotIn(WD, {a.atom_id for a in model.atoms})

    def test_synthetic_model_roundtrip_preserves_predictions_and_frozen_encoder(self):
        definitions, job, rows, metadata, candidates = fixture(baseline_discriminates=False)
        model, _ = retraining.fit_group(job, rows, metadata, definitions, group='LANG_REPLACE',
                                        binding=binding(job, 'LANG_REPLACE'),
                                        candidate_rows=candidate_rows(candidates, 'LANG_REPLACE'))
        self.assertEqual(model.status, 'FITTED')
        self.assertIn(LANG, {a.atom_id for a in model.atoms})
        self.assertNotIn(LANG_NUMERIC, model.encoder['numeric'])
        self.assertIn(HARDWARE, model.encoder['numeric'])
        self.assertEqual(model.encoder['train_ids'], job['train_ids'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic-model.json'
            retraining.save_model(model, path)
            loaded = retraining.load_model(path)
            self.assertEqual(json.loads(json.dumps(loaded.to_dict())),
                             json.loads(json.dumps(model.to_dict())))
            self.assertEqual(loaded.model_id, model.model_id)
            raw = rows[job['train_ids'][0]]
            for candidate_state, decision in [('T', 'MANIPULATION_ALERT'), ('F', 'NO_ALERT'),
                                              ('U', 'INSUFFICIENT_EVIDENCE'), ('FAILED', 'FAILED')]:
                with self.subTest(candidate_state=candidate_state):
                    current = {LANG: semantic(LANG, candidate_state)}
                    expected = retraining.predict_current(model, 'fixture-current', raw, current)
                    actual = retraining.predict_current(loaded, 'fixture-current', raw, current)
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual['decision'], decision)

    def test_group_and_frozen_selector_binding_reject_unregistered_variations(self):
        definitions, job, rows, metadata, _ = fixture()
        for group in ['ALL_NEW_RULES', 'LANG_AND_WD', None]:
            with self.subTest(group=group), self.assertRaises((ValueError, PermissionError)):
                retraining.group_definitions(definitions, group)
        for changes in [{'operating_point': 'OP10'}, {'method_id': 'R_KEEP_V1'},
                        {'fold_id': 'fixture-other-fold'}, {'group_id': 'WD_REPLACE'}]:
            with self.subTest(binding=changes), self.assertRaises((ValueError, PermissionError)):
                retraining.fit_group(job, rows, metadata, definitions, group='BASE',
                                     binding=binding(job, 'BASE', **changes))

    def test_failed_candidate_remains_failed_and_cannot_be_selected(self):
        definitions, job, rows, metadata, candidates = fixture()
        crows = candidate_rows(candidates, 'LANG_ADD')
        failed_id = job['train_ids'][0]
        crows[failed_id][LANG] = semantic(LANG, 'FAILED')
        model, training = retraining.fit_group(job, rows, metadata, definitions, group='LANG_ADD',
                                               binding=binding(job, 'LANG_ADD'), candidate_rows=crows)
        for polarity in ('POSITIVE', 'NEGATIVE'):
            clause_id = LANG + ':' + polarity
            item = next(item for item in training['candidate_manifest'] if item['clause_id'] == clause_id)
            self.assertFalse(item['eligible'])
            self.assertIn('TRAIN_EXECUTION_FAILURE', item['reasons'])
            self.assertEqual(training['support'][clause_id]['phase_availability']['clean_pre']['FAILED'], 1)
        self.assertEqual(model.fit['train_consumed_n'], len(rows))
        self.assertNotIn(LANG, {a.atom_id for a in model.atoms})

    def test_selector_failure_returns_failed_model_and_preserves_attempt(self):
        definitions, job, rows, metadata, _ = fixture()
        with patch.object(retraining, 'greedy', side_effect=RuntimeError('SYNTHETIC_SELECTOR_FAILURE')):
            model, training = retraining.fit_group(job, rows, metadata, definitions, group='BASE',
                                                   binding=binding(job, 'BASE'))
        self.assertEqual(model.status, 'FAILED')
        self.assertEqual(model.fit['train_ids'], job['train_ids'])
        self.assertEqual(model.fit['train_consumed_n'], len(rows))
        self.assertIn('SYNTHETIC_SELECTOR_FAILURE', str(model.fit) + str(training))
        self.assertEqual(model.clauses, ())
        result = retraining.predict_current(model, 'fixture-current', rows[job['train_ids'][0]])
        self.assertEqual(result['decision'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
