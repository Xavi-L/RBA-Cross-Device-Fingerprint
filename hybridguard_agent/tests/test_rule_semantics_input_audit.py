"""Synthetic source-tree integration tests; never open research records.

Each test injects a temporary repository, authority contract and source registry.
No candidate is evaluated: source and adapted fields are compared only to their
own prior versions, without comparing language to languages[0].
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'deliverables/rule_semantics_input_readiness/audit_inputs.py'
SPEC = importlib.util.spec_from_file_location('synthetic_input_audit_under_test', SCRIPT)
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)
LANG, LANGS, WD = audit_module.LANG, audit_module.LANGS, audit_module.WD
MODES = audit_module.MODES


class InputAuditIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rsr-input-audit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = {
            'authority': 'authority.json', 'scope_key': 'supervised_ids',
            'expected_denominator': 1, 'source_index': 'r04/DATA_INDEX.json',
            'raw_reference_root': 'raw',
            'mapping': {LANG: 'web_data.navigator_layer.language',
                        LANGS: 'web_data.navigator_layer.languages',
                        WD: 'web_data.automation_surface_layer.webdriver'},
        }
        supported = 'SUPPORTED_BY_EXISTING_LINEAGE'
        self.group = {
            'source_group_id': 'SYNTHETIC-featureapp-source',
            'raw_paths': ['raw/sessions.jsonl'],
            'paired_run_ref': 'raw/paired_run.json',
            'featureapp_registration': {'app_version_name': 'SYNTHETIC-build-v1'},
            'raw_metadata_requirements': {'collector_app': 'featureapp'},
            'modes': {
                'LANGUAGE': {'source_status': supported, 'binding_scope': 'navigator_sync_v1',
                             'evidence_refs': ['SYNTHETIC-registered-navigator-path']},
                'WEBDRIVER_LEGACY': {'source_status': supported,
                    'binding_scope': 'webdriver_legacy_projection_v1',
                    'evidence_refs': ['SYNTHETIC-registered-strict-true-path']},
                'WEBDRIVER_RAW': {'source_status': 'UNRESOLVED',
                    'binding_scope': 'webdriver_raw_observation_v1', 'evidence_refs': []},
            },
        }
        self.registrations = {'groups': [self.group]}
        self.payload = {
            'record_schema_version': 'hybridguard-mtc-observation-v2',
            'adapter_version': 'app177-triplet-adapter-v1',
            'features': {LANG: 'fr-CA', LANGS: ['en-US', 'fr-CA', 'en-US'], WD: False},
            'field_status': {LANG: 'observed', LANGS: 'observed', WD: 'observed'},
            'field_quality': {LANG: 'observed_value', LANGS: 'observed_value', WD: 'observed_value'},
        }
        self.raw = {
            'session_id': 'SYNTHETIC-session-a', 'collector_app': 'featureapp',
            'web_data': {'navigator_layer': {'language': 'fr-CA', 'languages': ['en-US', 'fr-CA', 'en-US']},
                         'automation_surface_layer': {'webdriver': False}},
            'collection_status': {'fields': {
                logical: 'observed' for logical in self.contract['mapping'].values()}},
        }
        self.manifest = {
            'opaque_id': 'sample-a', 'candidate_id': 'SYNTHETIC-source-candidate',
            'input_ref': 'adapted.jsonl#line=1',
            'source_raw_ref': 'sessions.jsonl#session_id=SYNTHETIC-session-a',
            'source_payload_binding': {'status': 'BOUND', 'raw_line': 1,
                'raw_session_ref': 'sessions.jsonl#session_id=SYNTHETIC-session-a'},
        }
        self.evaluation = {
            'opaque_id': 'sample-a', 'candidate_id': 'SYNTHETIC-source-candidate',
            'S02_input_ref': 's02/adapted.jsonl#line=1', 'session_id': 'SYNTHETIC-session-a',
            'label': 'SYNTHETIC-label-a', 'phase': 'SYNTHETIC-phase-a',
            'config_id': 'SYNTHETIC-config-a', 'tool': 'SYNTHETIC-tool-a',
        }
        self.write_json('authority.json', {'supervised_ids': ['sample-a'],
            'source_index': 'r04/DATA_INDEX.json'})
        self.write_json('r04/DATA_INDEX.json', {'sample-a': {'features': 'cache.json',
            'evaluation': 'evaluation.json'}})
        self.write_json('r04/cache.json', {'opaque_id': 'sample-a',
            'cache_lineage_ref': '../r02/CACHE_LINEAGE.json',
            'features': {'SYNTHETIC_ENCODED_CONTROL_NOT_INPUT': 123}})
        self.write_json('r02/CACHE_LINEAGE.json', {'input_manifest_ref': 's02/input_manifest.jsonl'})
        self.write_json('raw/paired_run.json', {'featureapp': self.group['featureapp_registration'],
            'sessions': [{'session_id': 'SYNTHETIC-session-a'}]})
        self.persist_records()

    def write_json(self, ref, data):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def write_lines(self, ref, rows):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    def persist_records(self):
        self.write_json('r04/evaluation.json', self.evaluation)
        self.write_lines('s02/input_manifest.jsonl', [self.manifest])
        self.write_lines('s02/adapted.jsonl', [{'opaque_id': 'sample-a', 'payload': self.payload}])
        self.write_lines('raw/sessions.jsonl', [self.raw])

    def audit(self):
        return audit_module.InputAudit(self.root, self.contract, self.registrations)

    def test_complete_inputs_preserve_false_order_types_and_exact_sources(self):
        audit = self.audit()
        result = audit.run()
        self.assertEqual(result['summary']['record_count'], 1)
        self.assertEqual(result['summary']['audit_execution'], 'COMPLETE')
        row = result['records'][0]
        self.assertEqual(row['source_refs']['adapted_input'], 's02/adapted.jsonl#line=1')
        self.assertEqual(row['post_decision_strata']['collector_build'], 'SYNTHETIC-build-v1')
        self.assertEqual(row['post_decision_strata']['source_bundle'], 'SYNTHETIC-featureapp-source')
        for mode in ('LANGUAGE', 'WEBDRIVER_LEGACY'):
            with self.subTest(mode=mode):
                self.assertEqual(row['modes'][mode]['readiness'], 'READY')
                loaded = audit.load_input('sample-a', mode)
                self.assertIsNotNone(loaded['source_binding'])
                self.assertEqual(loaded['payload']['record_schema_version'], 'rsr-input-v1')
                for section in ('features', 'field_status', 'field_quality'):
                    for field, value in loaded['payload'][section].items():
                        self.assertEqual(value, self.payload[section][field])
                        self.assertIs(type(value), type(self.payload[section][field]))
                self.assertNotIn('label', loaded['payload'])
                self.assertNotIn('SYNTHETIC_ENCODED_CONTROL_NOT_INPUT', loaded['payload']['features'])
        transferred = audit.load_input('sample-a', 'WEBDRIVER_LEGACY')['payload']['features'][WD]
        self.assertIs(transferred, False)
        languages = audit.load_input('sample-a', 'LANGUAGE')['payload']['features'][LANGS]
        self.assertEqual(languages, ['en-US', 'fr-CA', 'en-US'])
        languages.append('changed-only-in-return')
        self.assertEqual(audit.load_input('sample-a', 'LANGUAGE')['payload']['features'][LANGS],
                         ['en-US', 'fr-CA', 'en-US'])

    def test_non_target_jsonl_rows_only_expose_identity_and_load_is_rejected(self):
        self.write_json('r04/DATA_INDEX.json', {
            'sample-a': {'features': 'cache.json', 'evaluation': 'evaluation.json'},
            'OUTSIDE': {'features': 'MUST_NOT_OPEN.json', 'evaluation': 'MUST_NOT_OPEN.json'}})
        outside_manifest = {'opaque_id': 'OUTSIDE', '__SYNTHETIC_OUTSIDE__': True,
                            'payload': {'features': 'MUST_NOT_ANALYZE'}}
        outside_raw = {'session_id': 'OUTSIDE-session', '__SYNTHETIC_OUTSIDE__': True,
                       'web_data': {'languages': 'MUST_NOT_ANALYZE'}}
        self.manifest['source_payload_binding']['raw_line'] = 2
        self.write_lines('s02/input_manifest.jsonl', [outside_manifest, self.manifest])
        self.write_lines('raw/sessions.jsonl', [outside_raw, self.raw])
        real_loads = json.loads
        identity_reads = []

        class IdentityOnly(dict):
            def get(self, key, default=None):
                if key not in ('opaque_id', 'session_id'):
                    raise AssertionError('Analyzed outside-scope key: ' + key)
                identity_reads.append(key)
                return super().get(key, default)

            def __getitem__(self, key):
                raise AssertionError('Indexed outside-scope field: ' + str(key))

            def items(self):
                raise AssertionError('Iterated outside-scope fields')

        def guarded_loads(value, *args, **kwargs):
            item = real_loads(value, *args, **kwargs)
            return IdentityOnly(item) if isinstance(item, dict) and item.get('__SYNTHETIC_OUTSIDE__') else item

        with patch.object(audit_module.json, 'loads', guarded_loads):
            audit = self.audit()
            result = audit.run()
            self.assertEqual(result['summary']['record_count'], 1)
            self.assertEqual(result['records'][0]['opaque_id'], 'sample-a')
            self.assertEqual(result['records'][0]['modes']['LANGUAGE']['readiness'], 'READY')
            with self.assertRaisesRegex(audit_module.AuditError, 'OUTSIDE_AUTHORIZED'):
                audit.load_input('OUTSIDE', 'LANGUAGE')
        self.assertIn('opaque_id', identity_reads)
        self.assertIn('session_id', identity_reads)

    def test_missing_index_id_stays_in_each_mode_denominator(self):
        self.contract['expected_denominator'] = 2
        self.write_json('authority.json', {'supervised_ids': ['sample-a', 'missing-b'],
            'source_index': 'r04/DATA_INDEX.json'})
        result = self.audit().run()
        self.assertEqual(result['summary']['expected_denominator'], 2)
        self.assertEqual(result['summary']['record_count'], 2)
        self.assertEqual(result['summary']['audit_execution'], 'PARTIAL')
        missing = result['records'][1]
        self.assertEqual(missing['opaque_id'], 'missing-b')
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertEqual(sum(result['summary']['modes'][mode]['readiness'].values()), 2)
                self.assertEqual(missing['modes'][mode]['readiness'], 'BLOCKED')
                self.assertIn('INDEX_ENTRY_MISSING', missing['modes'][mode]['reasons'])

    def test_wrong_adapted_identity_is_a_conflict_without_guessing(self):
        self.write_lines('s02/adapted.jsonl', [{'opaque_id': 'wrong-id', 'payload': self.payload}])
        row = self.audit().run()['records'][0]
        for mode in MODES:
            self.assertEqual(row['modes'][mode]['source_status'], 'CONFLICT')
            self.assertFalse(row['modes'][mode]['binding_constructible'])
            self.assertIn('INFERENCE_IDENTITY_CONFLICT', row['modes'][mode]['reasons'])

    def test_conflicting_raw_duplicates_do_not_choose_a_matching_value(self):
        conflicting = deepcopy(self.raw)
        conflicting['web_data']['automation_surface_layer']['webdriver'] = True
        self.write_lines('raw/sessions.jsonl', [self.raw, conflicting])
        row = self.audit().run()['records'][0]
        self.assertEqual(row['modes']['LANGUAGE']['source_status'], 'CONFLICT')
        self.assertEqual(row['modes']['WEBDRIVER_LEGACY']['source_status'], 'CONFLICT')
        self.assertTrue(any('CONFLICTING_DUPLICATE_SOURCE' in reason
                            for reason in row['modes']['LANGUAGE']['reasons']))
        self.assertIsNone(self.audit().load_input('sample-a', 'LANGUAGE')['source_binding'])

    def test_missing_raw_keeps_complete_adapted_input_separate_from_unknown_source(self):
        (self.root / 'raw/sessions.jsonl').unlink()
        row = self.audit().run()['records'][0]
        for mode in ('LANGUAGE', 'WEBDRIVER_LEGACY'):
            with self.subTest(mode=mode):
                self.assertEqual(row['modes'][mode]['source_status'], 'UNRESOLVED')
                self.assertEqual(row['modes'][mode]['input_status'], 'COMPLETE')
                self.assertEqual(row['modes'][mode]['readiness'], 'BLOCKED')
                self.assertFalse(row['modes'][mode]['binding_constructible'])
        self.assertEqual(row['modes']['WEBDRIVER_RAW']['input_status'], 'MISSING')

    def test_value_and_status_transfer_conflicts_are_local_to_relevant_mode(self):
        for changed_kind in ('order', 'status'):
            with self.subTest(changed_kind=changed_kind):
                original = deepcopy(self.payload)
                if changed_kind == 'order':
                    self.payload['features'][LANGS] = ['fr-CA', 'en-US', 'en-US']
                else:
                    self.payload['field_status'][LANGS] = 'runtime_error'
                    self.payload['field_quality'][LANGS] = 'source_unavailable'
                self.persist_records()
                row = self.audit().run()['records'][0]
                language = row['modes']['LANGUAGE']
                self.assertEqual(language['source_status'], 'CONFLICT')
                self.assertEqual(language['input_status'], 'COMPLETE')
                self.assertEqual(language['readiness'], 'BLOCKED')
                self.assertEqual(row['modes']['WEBDRIVER_LEGACY']['readiness'], 'READY')
                self.assertTrue(any('UPSTREAM_ADAPTED_PRESERVATION_CONFLICT' in reason
                                    for reason in language['reasons']))
                self.payload = original

    def test_malformed_maps_do_not_abort_other_records_or_raw_mode(self):
        original = deepcopy(self.payload)
        self.contract['expected_denominator'] = 2
        self.write_json('authority.json', {'supervised_ids': ['sample-a', 'sample-b'],
            'source_index': 'r04/DATA_INDEX.json'})
        self.write_json('r04/DATA_INDEX.json', {
            'sample-a': {'features': 'cache.json', 'evaluation': 'evaluation.json'},
            'sample-b': {'features': 'cache-b.json', 'evaluation': 'evaluation-b.json'}})
        self.write_json('r04/cache-b.json', {'opaque_id': 'sample-b',
            'cache_lineage_ref': '../r02/CACHE_LINEAGE.json'})
        other_evaluation = {**self.evaluation, 'opaque_id': 'sample-b',
            'S02_input_ref': 's02/adapted.jsonl#line=2', 'session_id': 'SYNTHETIC-session-b'}
        self.write_json('r04/evaluation-b.json', other_evaluation)
        other_manifest = {**self.manifest, 'opaque_id': 'sample-b',
            'input_ref': 'adapted.jsonl#line=2',
            'source_raw_ref': 'sessions.jsonl#session_id=SYNTHETIC-session-b',
            'source_payload_binding': {'status': 'BOUND', 'raw_line': 2,
                'raw_session_ref': 'sessions.jsonl#session_id=SYNTHETIC-session-b'}}
        other_raw = {**deepcopy(self.raw), 'session_id': 'SYNTHETIC-session-b'}
        self.write_lines('s02/input_manifest.jsonl', [self.manifest, other_manifest])
        self.write_lines('raw/sessions.jsonl', [self.raw, other_raw])
        self.write_json('raw/paired_run.json', {'featureapp': self.group['featureapp_registration'],
            'sessions': [{'session_id': 'SYNTHETIC-session-a'}, {'session_id': 'SYNTHETIC-session-b'}]})
        for section in ('features', 'field_status'):
            with self.subTest(section=section):
                malformed = deepcopy(original)
                malformed[section] = []
                self.write_lines('s02/adapted.jsonl', [
                    {'opaque_id': 'sample-a', 'payload': malformed},
                    {'opaque_id': 'sample-b', 'payload': original}])
                result = self.audit().run()
                self.assertEqual(result['summary']['record_count'], 2)
                bad, good = result['records']
                for mode in ('LANGUAGE', 'WEBDRIVER_LEGACY'):
                    self.assertEqual(bad['modes'][mode]['input_status'], 'MALFORMED')
                    self.assertEqual(bad['modes'][mode]['readiness'], 'BLOCKED')
                    self.assertEqual(good['modes'][mode]['readiness'], 'READY')
                self.assertEqual(bad['modes']['WEBDRIVER_RAW']['input_status'], 'MISSING')

    def test_missing_upstream_value_or_status_is_unknown_not_conflicting(self):
        original_raw = deepcopy(self.raw)
        for missing_part in ('value', 'status'):
            with self.subTest(missing_part=missing_part):
                self.raw = deepcopy(original_raw)
                if missing_part == 'value':
                    del self.raw['web_data']['navigator_layer']['languages']
                else:
                    del self.raw['collection_status']['fields']['web_data.navigator_layer.languages']
                self.persist_records()
                row = self.audit().run()['records'][0]
                self.assertEqual(row['modes']['LANGUAGE']['source_status'], 'UNRESOLVED')
                self.assertEqual(row['modes']['LANGUAGE']['input_status'], 'COMPLETE')
                self.assertEqual(row['modes']['LANGUAGE']['readiness'], 'BLOCKED')
                self.assertFalse(row['modes']['LANGUAGE']['binding_constructible'])
                self.assertEqual(row['modes']['WEBDRIVER_LEGACY']['readiness'], 'READY')
                self.assertTrue(any('UPSTREAM_VALUE_OR_STATE_MISSING' in reason
                    for reason in row['modes']['LANGUAGE']['reasons']))
        self.raw = original_raw

    def test_missing_adapted_value_does_not_falsely_conflict_with_known_source(self):
        del self.payload['features'][LANGS]
        self.persist_records()
        row = self.audit().run()['records'][0]
        language = row['modes']['LANGUAGE']
        self.assertEqual(language['source_status'], 'SUPPORTED_BY_EXISTING_LINEAGE')
        self.assertEqual(language['input_status'], 'MISSING')
        self.assertEqual(language['readiness'], 'BLOCKED')
        self.assertEqual(row['modes']['WEBDRIVER_LEGACY']['readiness'], 'READY')
        self.assertNotIn(LANGS, self.audit().load_input('sample-a', 'LANGUAGE')['payload']['features'])
        self.assertFalse(any('PRESERVATION_CONFLICT' in reason for reason in language['reasons']))

    def test_conditional_source_has_complete_payload_but_no_binding(self):
        self.group['modes']['LANGUAGE']['source_status'] = 'CONDITIONAL_ASSUMPTION'
        loaded = self.audit().load_input('sample-a', 'LANGUAGE')
        self.assertEqual(loaded['audit']['input_status'], 'COMPLETE')
        self.assertEqual(loaded['audit']['readiness'], 'CONDITIONAL')
        self.assertIsNone(loaded['source_binding'])
        self.assertEqual(loaded['payload']['features'][LANGS], self.payload['features'][LANGS])

    def test_labels_phase_tool_and_predictions_do_not_change_decision_or_payload(self):
        before = self.audit().run()['records'][0]
        before_payload = self.audit().load_input('sample-a', 'LANGUAGE')['payload']
        self.evaluation.update(label='DIFFERENT-label', phase='DIFFERENT-phase',
            config_id='DIFFERENT-config', tool='DIFFERENT-tool', prediction=True)
        self.payload.update(label='UNTRUSTED-label', phase='UNTRUSTED-phase',
                            tool='UNTRUSTED-tool', prediction=True)
        self.persist_records()
        after = self.audit().run()['records'][0]
        self.assertEqual(before['modes'], after['modes'])
        self.assertEqual(before_payload, self.audit().load_input('sample-a', 'LANGUAGE')['payload'])
        self.assertNotEqual(before['post_decision_strata'], after['post_decision_strata'])

    def test_audit_and_loader_never_call_candidates_or_infer_missing_raw(self):
        with patch('hybridguard_agent.research.rule_semantics_revision_v1.language.web_language_first_difference',
                   side_effect=AssertionError('forbidden candidate call')) as language, \
             patch('hybridguard_agent.research.rule_semantics_revision_v1.webdriver.webdriver_reported_state',
                   side_effect=AssertionError('forbidden candidate call')) as webdriver:
            audit = self.audit()
            result = audit.run()
            for mode in MODES:
                loaded = audit.load_input('sample-a', mode)
                self.assertFalse(result['records'][0]['candidate_evaluation_performed'])
                if mode == 'WEBDRIVER_RAW':
                    self.assertEqual(loaded['audit']['input_status'], 'MISSING')
                    self.assertEqual(loaded['audit']['readiness'], 'BLOCKED')
                    self.assertEqual(loaded['payload'], {'record_schema_version': 'rsr-input-v1'})
                    self.assertIsNone(loaded['source_binding'])
            language.assert_not_called()
            webdriver.assert_not_called()
            self.assertEqual(result['summary']['execution_counts'],
                {'real_fit': 0, 'model_predictions': 0, 'real_new_candidate_evaluations': 0,
                 'new_collections': 0})

    def test_default_cli_is_read_only_and_existing_report_is_preserved(self):
        audit = self.audit()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        stdout = io.StringIO()
        with patch.object(audit_module, 'InputAudit', return_value=audit), redirect_stdout(stdout):
            self.assertEqual(audit_module.main([]), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result['summary']['record_count'], 1)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        output = self.root / 'reports'
        output.mkdir()
        existing = output / 'SUMMARY.json'
        existing.write_text('historical evidence', encoding='utf-8')
        with patch.object(audit_module, 'InputAudit', return_value=audit), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit) as raised:
            audit_module.main(['--output-dir', str(output)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(existing.read_text(), 'historical evidence')
        self.assertFalse((output / 'INPUT_MANIFEST.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
