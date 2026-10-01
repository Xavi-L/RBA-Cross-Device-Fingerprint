"""Synthetic-only adapter checks; no campaign material or real fit budget."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_selector_v2 as engine
from hybridguard_agent.research.rule_learning.contracts import cell, state
from hybridguard_agent.research.rule_learning_v2.semantic_selection import CATALOG_VERSION
from hybridguard_agent.tests.test_rule_semantics_retraining import fixture, semantic, LANG, WD


def binding(job, method):
    return {'study_version': engine.STUDY_VERSION, 'phase': engine.PHASE,
            'experiment_id': 'semantic-selector-v2-raw-only-pilot-v1',
            'group_id': 'LANG_ADD_WD_REPLACE', 'method_id': method,
            'operating_point': 'OP05', 'fold_id': job['fold_id'],
            'evaluation_role': 'SYNTHETIC_ENGINEERING_ONLY'}


class SelectorAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs, cls.job, cls.rows, cls.meta, cls.candidates = fixture()
        cls.modes = dict.fromkeys(cls.rows, 'raw_observation_v1')
        for sid, m in cls.meta.items():
            cls.candidates[sid][WD] = semantic(WD, 'T' if m['phase'] == 'attack' else 'F')
            cls.candidates[sid][WD]['diagnostics']['mode'] = 'raw_observation_v1'
        cls.kwargs = dict(group='LANG_ADD_WD_REPLACE', source_modes=cls.modes, candidate_rows=cls.candidates)
        cls.initial, cls.training = engine.fit_sparse(cls.job, cls.rows, cls.meta, cls.defs,
                binding=binding(cls.job, 'GREEDY_SEMANTIC_V2'), **cls.kwargs)

    def test_two_stages_roundtrip_and_no_encoder_refit(self):
        self.assertEqual(self.initial.status, 'FITTED', self.initial.fit.get('failure'))
        with patch.object(engine, 'encode_train', side_effect=AssertionError('no refit')):
            model, training = engine.fit_retention(self.job, self.rows, self.meta, self.defs,
                binding=binding(self.job, 'R_KEEP_SWAP_V2'), initial_model=self.initial,
                initial_training=self.training, **self.kwargs)
        self.assertEqual(model.status, 'FITTED', model.fit.get('failure'))
        self.assertEqual(model.encoder, self.initial.encoder)
        self.assertEqual(model.fit['threshold_fit_calls'], 0)
        self.assertEqual(training['semantic_catalog'], self.training['semantic_catalog'])
        self.assertTrue(all(op['ids'] == self.job['train_ids'] for op in training['access_operations']))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.json'
            engine.save_model(model, path)
            restored = engine.load_model(path)
            self.assertEqual(json.dumps(model.to_dict(), sort_keys=True), json.dumps(restored.to_dict(), sort_keys=True))
            sid = next(i for i, m in self.meta.items() if m['phase'] == 'attack')
            result = engine.predict_current(restored, sid, self.rows[sid], self.candidates[sid], source_mode='raw_observation_v1')
            self.assertEqual(result['decision'], 'MANIPULATION_ALERT')

    def test_raw_only_exact_members_and_new_identity_before_fit(self):
        bad_modes = dict(self.modes)
        bad_modes[next(iter(bad_modes))] = 'legacy_projection_v1'
        with patch.object(engine, 'encode_train', side_effect=AssertionError('must not fit')):
            with self.assertRaises(PermissionError):
                engine.fit_sparse(self.job, self.rows, self.meta, self.defs,
                    binding=binding(self.job, 'GREEDY_SEMANTIC_V2'), **(self.kwargs | {'source_modes': bad_modes}))
            with self.assertRaises(PermissionError):
                engine.fit_sparse(self.job | {'outer_test_ids': [self.job['train_ids'][0]]}, self.rows, self.meta, self.defs,
                    binding=binding(self.job, 'GREEDY_SEMANTIC_V2'), **self.kwargs)
            with self.assertRaises(PermissionError):
                engine.fit_sparse(self.job, self.rows, self.meta, self.defs,
                    binding=binding(self.job, 'GREEDY_SEMANTIC_V2') | {'study_version': 'rule-semantics-mixed-retraining-v1'}, **self.kwargs)
        with self.assertRaises(PermissionError):
            engine.predict_current(self.initial, 'synthetic-test', {}, {}, source_mode='legacy_projection_v1')

    def test_saved_cell_states_are_not_repaired(self):
        sid = self.job['train_ids'][0]
        for value in ('T', 'F', 'U', 'FAILED'):
            pair = deepcopy(self.candidates[sid])
            pair[WD] = semantic(WD, value)
            pair[WD]['diagnostics']['mode'] = 'raw_observation_v1'
            projected = engine.project_rows({sid: self.rows[sid]}, self.defs, 'LANG_ADD_WD_REPLACE',
                     source_modes={sid: 'raw_observation_v1'}, candidate_rows={sid: pair})
            if value == 'FAILED':
                self.assertEqual(projected[sid][WD]['evaluation_status'], 'FAILED')
            else:
                self.assertEqual(state(projected[sid][WD]), value)

    def test_initializer_metadata_mismatch_never_retrains(self):
        bad = deepcopy(self.training)
        bad['semantic_catalog'] = {}
        with patch.object(engine, 'retain_semantic', side_effect=AssertionError('must not select')):
            for model, training in ((self.initial, bad),
                                    (replace(self.initial, binding=self.initial.binding | {'fold_id': 'wrong'}), self.training)):
                with self.assertRaises((PermissionError, ValueError)):
                    engine.fit_retention(self.job, self.rows, self.meta, self.defs,
                        binding=binding(self.job, 'R_KEEP_SWAP_V2'), initial_model=model,
                        initial_training=training, **self.kwargs)

    def test_display_id_cannot_override_language_group_in_audit_or_initializer(self):
        # This historical ID has a web-client shortcut in the old group mapper.
        # Its synthetic predicate here concerns language length, so all new
        # audit and initializer checks must follow the structural catalog.
        definitions, rows = deepcopy(self.defs), deepcopy(self.rows)
        display_id = 'CAT:NW-006'
        field = 'app.web_data.navigator_layer.languages'
        definitions['atoms'].append({
            'atom_id': display_id, 'family': 'CONTROL_FIELD:' + field,
            'surfaces': ['app_web67'], 'sources': ['SYNTHETIC_SOURCE_ONLY'],
            'aliases': [display_id], 'orientation': 'CONTROL_LE',
            'provenance': {'field': field, 'threshold': 1.5},
        })
        definitions['single_surface_allowlists']['app_web67'].append(display_id)
        for sid, row in rows.items():
            row[display_id] = cell('F' if self.meta[sid]['phase'] == 'attack' else 'T')
        initial, sparse_training = engine.fit_sparse(self.job, rows, self.meta, definitions,
            binding=binding(self.job, 'GREEDY_SEMANTIC_V2'), **self.kwargs)
        self.assertEqual(initial.status, 'FITTED', initial.fit.get('failure'))
        model, retained_training = engine.fit_retention(self.job, rows, self.meta, definitions,
            binding=binding(self.job, 'R_KEEP_SWAP_V2'), initial_model=initial,
            initial_training=sparse_training, **self.kwargs)
        self.assertEqual(model.status, 'FITTED', model.fit.get('failure'))
        for training in (sparse_training, retained_training):
            self.assertEqual(training['signal_groups'][display_id], 'language_preferences')
            self.assertEqual(training['semantic_catalog'][display_id]['signal_group'], 'language_preferences')
            self.assertEqual(training['signal_group_version'], CATALOG_VERSION)
            manifest = [r for r in training['candidate_manifest']
                        if r['clause_id'].rsplit(':', 1)[0] == display_id]
            self.assertEqual(len(manifest), 2)
            self.assertTrue(all(r['signal_group'] == 'language_preferences' for r in manifest))
        self.assertEqual(model.fit['signal_group_version'], CATALOG_VERSION)


if __name__ == '__main__':
    unittest.main()
