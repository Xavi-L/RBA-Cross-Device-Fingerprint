"""Synthetic-only tests for standalone semantics; no historic records or models.

The public fixture helpers are also used by the delivery report runner. They
call the implementation and never return a fixture's expected_state as a result.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from hybridguard_agent.research.rule_semantics_revision_v1.contracts import (
    SemanticCell, SourceBinding,
)
from hybridguard_agent.research.rule_semantics_revision_v1.language import (
    limited_full_tag, web_language_first_difference,
)
from hybridguard_agent.research.rule_semantics_revision_v1.manifest import module_manifest
from hybridguard_agent.research.rule_semantics_revision_v1.webdriver import webdriver_reported_state

FIXTURE_PATH = Path(__file__).parent / 'fixtures/rule_semantics_revision_v1/specification_examples.json'
REPO_ROOT = Path(__file__).resolve().parents[2]
LANG = 'app.web_data.navigator_layer.language'
LANGS = 'app.web_data.navigator_layer.languages'
WD = 'app.web_data.automation_surface_layer.webdriver'
LANG_ID = 'RSR-LANG-FIRST-v1'
WD_ID = 'RSR-WEBDRIVER-STATE-v1'
RAW_MODE = 'raw_observation_v1'
LEGACY_MODE = 'legacy_projection_v1'
SPECIFICATION_RESULTS: list[dict] = []


def load_specification_fixtures() -> list[dict]:
    """Load only the explicitly synthetic approved-example adaptations."""
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['specification_examples']


def load_boundary_fixtures() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['additional_boundary_examples']


def run_specification_fixture(example: dict) -> SemanticCell:
    """Execute either supported module from an explicit synthetic fixture."""
    descriptor = example['source_binding']
    if descriptor is None:
        binding = None
    elif descriptor.get('kind') == 'SYNTHETIC_CALLER_BINDING':
        binding = SourceBinding(**{k: v for k, v in descriptor.items() if k != 'kind'})
    else:
        # Deliberately keep page self-claims untyped and untrusted.
        binding = copy.deepcopy(descriptor)
    if example['candidate_id'] == LANG_ID:
        return web_language_first_difference(example['payload'], source_binding=binding)
    if example['candidate_id'] == WD_ID:
        return webdriver_reported_state(example['payload'], mode=example['mode'], source_binding=binding)
    raise ValueError('The synthetic runner is limited to the two authorized families')


def binding(scope='navigator_sync_v1', **changes):
    values = dict(source_contract_id='SYNTHETIC-test-contract-v1', observation_scope=scope)
    values.update(changes)
    return SourceBinding(**values)


def flat(values, **extra):
    p = {'record_schema_version': 'rsr-input-v1', 'features': copy.deepcopy(values),
         'field_status': {k: 'observed' for k in values},
         'field_quality': {k: 'observed_value' for k in values}}
    p.update(extra)
    return p


def language_payload(language='en-US', languages=None):
    return flat({LANG: language, LANGS: ['en-US'] if languages is None else languages})


def raw_payload(value=False, **overrides):
    record = {'api_present': True, 'presence_read_status': 'observed',
              'value_read_status': 'observed', 'value_type': 'boolean',
              'boolean_value': value, 'observer_revision': 'SYNTHETIC-observer-v1',
              'realm_binding': 'SYNTHETIC-realm-1'}
    record.update(overrides)
    return {'record_schema_version': 'rsr-input-v1',
            'web_data': {'automation_surface_layer': {'webdriver_observation': record}}}


def raw_record(payload):
    return payload['web_data']['automation_surface_layer']['webdriver_observation']


def raw_binding(**overrides):
    fields = {'observer_revision': 'SYNTHETIC-observer-v1', 'realm_binding': 'SYNTHETIC-realm-1'}
    fields.update(overrides)
    return binding('webdriver_raw_observation_v1', **fields)


class CellAssertions:
    def assert_cell(self, cell, expected, reason=None, candidate=None):
        self.assertIsInstance(cell, SemanticCell)
        self.assertEqual(cell.state, expected)
        encoded = cell.to_dict()
        encoding = {'T': (True, True, 'OK'), 'F': (False, True, 'OK'),
                    'U': (None, False, 'OK'), 'FAILED': (None, False, 'FAILED')}
        value, available, status = encoding[expected]
        self.assertIs(encoded['value'], value)
        self.assertIs(encoded['available'], available)
        self.assertEqual(encoded['evaluation_status'], status)
        self.assertEqual(encoded['version'], '1.0.0')
        self.assertIsInstance(encoded['reason'], str)
        self.assertTrue(encoded['reason'])
        self.assertNotIn('attack', encoded)
        self.assertNotIn('clean', encoded)
        if reason is not None:
            self.assertEqual(encoded['reason'], reason)
        if candidate is not None:
            self.assertEqual(encoded['candidate_id'], candidate)


class SpecificationFixtureTests(CellAssertions, unittest.TestCase):
    def test_approved_examples_execute_actual_modules(self):
        for example in load_specification_fixtures():
            with self.subTest(example_id=example['source_example_id']):
                before = copy.deepcopy(example)
                actual = run_specification_fixture(example)
                SPECIFICATION_RESULTS.append({
                    'source_example_id': example['source_example_id'],
                    'fixture_id': example['fixture_id'],
                    'candidate_id': example['candidate_id'],
                    'source_spec_version': example['source_spec_version'],
                    'real_sample': False, 'expected_state': example['expected_state'],
                    'actual': actual.to_dict(), 'actual_state': actual.state,
                    'passed': actual.state == example['expected_state'],
                })
                self.assert_cell(actual, example['expected_state'], candidate=example['candidate_id'])
                self.assertEqual(example, before)

    def test_additional_boundary_fixtures_execute_actual_modules(self):
        for example in load_boundary_fixtures():
            with self.subTest(fixture_id=example['fixture_id']):
                actual = run_specification_fixture(example)
                SPECIFICATION_RESULTS.append({
                    'source_example_id': None,
                    'fixture_id': example['fixture_id'],
                    'candidate_id': example['candidate_id'],
                    'source_spec_version': example['source_spec_version'],
                    'real_sample': False, 'expected_state': example['expected_state'],
                    'actual': actual.to_dict(), 'actual_state': actual.state,
                    'passed': actual.state == example['expected_state'],
                    'boundary_reason': example['boundary_reason'],
                })
                self.assert_cell(actual, example['expected_state'], candidate=example['candidate_id'])
                self.assertTrue(example['boundary_reason'])
                self.assertIs(example['real_sample'], False)

    def test_fixture_provenance_matches_all_and_only_authorized_spec_examples(self):
        source = json.loads((REPO_ROOT / 'deliverables/rule_semantics_revision/CANDIDATE_SPEC.json').read_text())
        approved = {(c['candidate_id'], ex['example_id']): (c, ex)
                    for c in source['candidates'] if c['candidate_id'] in {LANG_ID, WD_ID}
                    for ex in c['specification_examples']}
        fixtures = load_specification_fixtures()
        self.assertEqual(len(fixtures), len(approved))
        self.assertEqual({(f['candidate_id'], f['source_example_id']) for f in fixtures}, set(approved))
        for fixture in fixtures:
            with self.subTest(example_id=fixture['source_example_id']):
                candidate, example = approved[fixture['candidate_id'], fixture['source_example_id']]
                self.assertEqual(fixture['source_spec_version'], source['schema_version'])
                self.assertEqual(fixture['candidate_version'], candidate['version'])
                self.assertEqual(fixture['source_expected_state'], example['expected_state'])
                self.assertEqual(fixture['expected_state'], example['expected_state'])
                self.assertEqual(fixture['source_expected_reason'], example['reason'])
                self.assertIs(fixture['real_sample'], False)
                self.assertIs(fixture['source_executed'], False)
                self.assertIs(example['executed'], False)
                self.assertTrue(fixture['adaptation_notes'])


class LanguageTests(CellAssertions, unittest.TestCase):
    def evaluate(self, payload=None, source_binding=None):
        return web_language_first_difference(language_payload() if payload is None else payload,
                                             source_binding=binding() if source_binding is None else source_binding)

    def test_limited_parser_preserves_region_script_and_ascii_case(self):
        for raw, expected in [('EN-us', 'en-us'), ('ZH-hANS-cn', 'zh-hans-cn'),
                              ('es-419', 'es-419'), ('abc', 'abc'), ('en', 'en')]:
            with self.subTest(tag=raw):
                self.assertEqual(limited_full_tag(raw), expected)

    def test_parser_rejects_aliases_extensions_padding_and_partial_matches(self):
        for raw in ['und', 'mul', 'zxx', 'iw-IL', 'in-ID', 'ji', 'en-US-u-ca-gregory',
                    'x-private', 'en_US', ' en-US', 'en-US ', 'en-US\n', 'en-US\r\n',
                    'en\nUS', 'éñ', 'eſ-US', '', None, True, 42, ['en-US']]:
            with self.subTest(tag=raw):
                self.assertIsNone(limited_full_tag(raw))

    def test_first_item_relation_not_membership_or_primary_only(self):
        for language, values, expected in [
            ('zh-CN', ['zh-CN', 'en-US'], 'F'), ('en-US', ['en-us', 'en'], 'F'),
            ('en-US', ['fr-FR', 'en-US'], 'T'), ('en-US', ['en-GB'], 'T'),
            ('zh-Hans', ['zh-Hant'], 'T'), ('fr-FR', ['fr-FR'], 'F')]:
            with self.subTest(language=language, languages=values):
                self.assert_cell(self.evaluate(language_payload(language, values)), expected, candidate=LANG_ID)

    def test_invalid_operands_are_unavailable_without_coercion(self):
        for language, values in [('en-US', []), (None, ['en-US']), (True, ['en-US']),
                                 ('en-US', [42]), ('en-US', [None]), ('en-US', 'en-US'),
                                 ('en-US', ['en-US-u-ca-gregory'])]:
            with self.subTest(language=language, languages=values):
                self.assert_cell(self.evaluate(flat({LANG: language, LANGS: values})), 'U')

    def test_tail_is_retained_diagnosed_and_never_gates_relation(self):
        tail = ['fr-FR-u-ca-gregory', None, 42]
        for first, expected in [('en-US', 'F'), ('fr-FR', 'T')]:
            with self.subTest(first=first):
                cell = self.evaluate(language_payload('en-US', [first] + tail))
                self.assert_cell(cell, expected)
                self.assertEqual(cell.to_dict()['diagnostics']['languages_tail'], tail)
                self.assertEqual([x['index'] for x in cell.to_dict()['diagnostics']['tail_issues']], [1, 2, 3])

    def test_case_changes_and_tail_changes_preserve_relation(self):
        for first in ['en-us', 'fr-fr']:
            baseline = self.evaluate(language_payload('EN-US', [first])).state
            for language, changed_first, tail in [('en-US', first.upper(), [None]),
                                                   ('EN-us', first, ['x-private', 17]),
                                                   ('en-us', first.title(), [])]:
                with self.subTest(first=first, language=language, tail=tail):
                    cell = self.evaluate(language_payload(language, [changed_first] + tail))
                    self.assertEqual(cell.state, baseline)

    def test_both_fields_coherently_changed_still_compare_equal(self):
        for language in ['ar-SA', 'zh-Hant-TW', 'de']:
            with self.subTest(language=language):
                self.assert_cell(self.evaluate(language_payload(language, [language])), 'F')

    def test_missing_field_maps_or_related_values_are_unavailable(self):
        p = language_payload()
        for section in ['features', 'field_status', 'field_quality']:
            with self.subTest(section=section):
                missing_map = copy.deepcopy(p)
                del missing_map[section]
                self.assert_cell(self.evaluate(missing_map), 'U')
                missing_field = copy.deepcopy(p)
                del missing_field[section][LANG]
                self.assert_cell(self.evaluate(missing_field), 'U')
                null_field = copy.deepcopy(p)
                null_field[section][LANG] = None
                reason = 'MISSING_FIELD' if section == 'features' else 'MISSING_MEASUREMENT_STATE'
                self.assert_cell(self.evaluate(null_field), 'U', reason)

    def test_source_errors_remain_unavailable_and_preserve_source_reason(self):
        for source_status in ['runtime_error', 'timeout', 'permission_denied', 'unsupported_by_os', 'not_applicable']:
            with self.subTest(source_status=source_status):
                p = language_payload()
                p['field_status'][LANG] = source_status
                p['field_quality'][LANG] = 'source_unavailable'
                cell = self.evaluate(p)
                self.assert_cell(cell, 'U', 'SOURCE_STATUS_' + source_status.upper())
                self.assertEqual(cell.to_dict()['source_reason'], source_status)

    def test_known_status_quality_combinations_do_not_invent_contradictions(self):
        p = language_payload()
        p['field_status'][LANG] = 'runtime_error'
        self.assert_cell(self.evaluate(p), 'U', 'SOURCE_STATUS_RUNTIME_ERROR')
        for quality in ['source_unavailable', 'ambiguous_sentinel']:
            with self.subTest(quality=quality):
                p = language_payload()
                p['field_quality'][LANG] = quality
                self.assert_cell(self.evaluate(p), 'U')

    def test_missing_untrusted_or_wrong_scope_binding_are_distinct(self):
        p = language_payload()
        self.assert_cell(web_language_first_difference(p), 'U', 'SOURCE_BINDING_MISSING')
        self.assert_cell(web_language_first_difference(p, source_binding={'trusted': True, 'same_context': True}),
                         'U', 'SOURCE_BINDING_UNTRUSTED')
        self.assert_cell(self.evaluate(p, binding('webdriver_legacy_projection_v1')),
                         'U', 'SOURCE_CONTEXT_UNPAIRED')

    def test_invalid_schema_wrappers_and_related_enums_fail(self):
        invalid = [None, [], {}, {'record_schema_version': 'invented'},
                   {'record_schema_version': 1}, {'record_schema_version': 'rsr-input-v1', 'features': []}]
        for p in invalid:
            with self.subTest(payload=p):
                self.assert_cell(web_language_first_difference(p, source_binding=binding()), 'FAILED')
        for section in ['field_status', 'field_quality']:
            for value in ['invented', True, []]:
                with self.subTest(section=section, value=value):
                    p = language_payload()
                    p[section][LANG] = value
                    self.assert_cell(self.evaluate(p), 'FAILED')

    def test_unrelated_fields_metadata_and_unknown_engine_do_not_gate(self):
        base = self.evaluate().to_dict()
        p = language_payload()
        p['metadata'] = {'provider_version': 'UNKNOWN', 'app_name': 'business', 'trusted': False}
        p.update(label='attack', phase='synthetic', sample_id='unused', tools=['unused'], config={'x': 1})
        for section in ['features', 'field_status', 'field_quality']:
            p[section]['app.unrelated.invalid'] = {'arbitrary': [False, None]}
        self.assertEqual(self.evaluate(p).to_dict(), base)

    def test_key_order_determinism_no_input_mutation_and_fixed_issue_priority(self):
        p = language_payload('en-US', ['fr-FR', None])
        p['field_status'][LANG] = 'timeout'
        p['field_status'][LANGS] = 'runtime_error'
        before = copy.deepcopy(p)
        first = self.evaluate(p).to_dict()
        reordered = {k: dict(reversed(list(v.items()))) if isinstance(v, dict) else v
                     for k, v in reversed(list(p.items()))}
        self.assertEqual(self.evaluate(reordered).to_dict(), first)
        self.assertEqual(self.evaluate(p).to_dict(), first)
        self.assertEqual(p, before)

    def test_executor_exception_is_failed_not_source_unavailability(self):
        with patch('hybridguard_agent.research.rule_semantics_revision_v1.language.limited_full_tag',
                   side_effect=RuntimeError('synthetic executor failure')):
            self.assert_cell(self.evaluate(), 'FAILED', 'EXECUTOR_ERROR')


class WebdriverTests(CellAssertions, unittest.TestCase):
    def legacy(self, value=True, payload=None, source_binding=None):
        return webdriver_reported_state(flat({WD: value}) if payload is None else payload,
                                        mode=LEGACY_MODE,
                                        source_binding=binding('webdriver_legacy_projection_v1')
                                        if source_binding is None else source_binding)

    def raw(self, payload=None, source_binding=None):
        return webdriver_reported_state(raw_payload() if payload is None else payload, mode=RAW_MODE,
                                        source_binding=raw_binding() if source_binding is None else source_binding)

    def test_legacy_true_false_and_nonboolean_values(self):
        self.assert_cell(self.legacy(True), 'T', 'LEGACY_REPORTED_TRUE', WD_ID)
        self.assert_cell(self.legacy(False), 'U', 'LEGACY_NONTRUE_PROJECTION_AMBIGUOUS')
        self.assert_cell(self.legacy(None), 'U', 'MISSING_FIELD')
        for value in [0, 1, 'true', 'false', [], {}]:
            with self.subTest(value=value):
                self.assert_cell(self.legacy(value), 'U', 'INVALID_BOOLEAN_VALUE')

    def test_legacy_source_error_precedes_boolean_projection(self):
        for status in ['runtime_error', 'timeout']:
            with self.subTest(status=status):
                p = flat({WD: False})
                p['field_status'][WD] = status
                p['field_quality'][WD] = 'source_unavailable'
                cell = self.legacy(payload=p)
                self.assert_cell(cell, 'U', 'SOURCE_STATUS_' + status.upper())
                self.assertEqual(cell.to_dict()['source_reason'], status)

    def test_raw_true_false_and_nonboolean_types(self):
        self.assert_cell(self.raw(raw_payload(True)), 'T', 'RAW_REPORTED_TRUE', WD_ID)
        self.assert_cell(self.raw(raw_payload(False)), 'F', 'RAW_REPORTED_FALSE')
        for value_type in ['undefined', 'string', 'number', 'bigint', 'symbol', 'function', 'object']:
            with self.subTest(value_type=value_type):
                self.assert_cell(self.raw(raw_payload(None, value_type=value_type)), 'U', 'NONBOOLEAN_API_VALUE')

    def test_raw_absent_presence_failure_and_getter_failure_are_distinct(self):
        absent = raw_payload(None, api_present=False, value_type=None, value_read_status='not_attempted')
        self.assert_cell(self.raw(absent), 'U', 'API_ABSENT')
        presence_error = raw_payload(None, api_present=None, value_type=None,
                                     presence_read_status='runtime_error', value_read_status='not_attempted')
        getter_error = raw_payload(None, value_type=None, value_read_status='runtime_error')
        for p, reason in [(presence_error, 'PRESENCE_READ_ERROR'), (getter_error, 'VALUE_READ_ERROR')]:
            with self.subTest(reason=reason):
                cell = self.raw(p)
                self.assert_cell(cell, 'U', reason)
                self.assertEqual(cell.to_dict()['source_reason'], 'runtime_error')

    def test_raw_missing_members_objects_and_source_metadata_are_unavailable(self):
        for member in ['api_present', 'presence_read_status', 'value_read_status', 'value_type',
                       'boolean_value', 'observer_revision', 'realm_binding']:
            with self.subTest(member=member):
                p = raw_payload()
                del raw_record(p)[member]
                self.assert_cell(self.raw(p), 'U')
        for p in [{'record_schema_version': 'rsr-input-v1'},
                  {'record_schema_version': 'rsr-input-v1', 'web_data': None}]:
            with self.subTest(payload=p):
                self.assert_cell(self.raw(p), 'U', 'MISSING_OBSERVATION_METADATA')
        self.assert_cell(webdriver_reported_state(raw_payload(), mode=RAW_MODE), 'U', 'SOURCE_BINDING_MISSING')
        for changes in [{'observer_revision': None}, {'realm_binding': None}]:
            with self.subTest(binding=changes):
                self.assert_cell(self.raw(source_binding=raw_binding(**changes)), 'U')

    def test_raw_binding_mismatch_and_page_claims_cannot_authorize_observation(self):
        for changes in [{'observer_revision': 'different'}, {'realm_binding': 'different'}]:
            with self.subTest(binding=changes):
                self.assert_cell(self.raw(source_binding=raw_binding(**changes)), 'U', 'OBSERVATION_NOT_COMPARABLE')
        self.assert_cell(self.raw(source_binding={'trusted': True, 'same_context': True}),
                         'U', 'SOURCE_BINDING_UNTRUSTED')
        self.assert_cell(self.raw(source_binding=binding('navigator_sync_v1')), 'U', 'SOURCE_CONTEXT_UNPAIRED')

    def test_raw_impossible_record_combinations_fail(self):
        for changes in [
            {'api_present': False, 'value_read_status': 'not_attempted'},
            {'api_present': True, 'value_read_status': 'not_attempted', 'value_type': None, 'boolean_value': None},
            {'api_present': None}, {'presence_read_status': 'runtime_error'},
            {'value_read_status': 'runtime_error'}, {'value_type': 'string'},
            {'value_type': None}, {'boolean_value': None}, {'boolean_value': 'false'}]:
            with self.subTest(changes=changes):
                self.assert_cell(self.raw(raw_payload(True, **changes)), 'FAILED')

    def test_raw_invalid_enums_types_or_structure_fail(self):
        for changes in [{'presence_read_status': 'timeout'}, {'value_read_status': 'invented'},
                        {'value_type': 'bool'}, {'api_present': 1}, {'boolean_value': 0},
                        {'observer_revision': 123}, {'realm_binding': []}]:
            with self.subTest(changes=changes):
                self.assert_cell(self.raw(raw_payload(**changes)), 'FAILED')
        for path in ['web_data', 'automation_surface_layer', 'webdriver_observation']:
            with self.subTest(path=path):
                p = raw_payload()
                if path == 'web_data':
                    p[path] = []
                elif path == 'automation_surface_layer':
                    p['web_data'][path] = []
                else:
                    p['web_data']['automation_surface_layer'][path] = []
                self.assert_cell(self.raw(p), 'FAILED')

    def test_raw_success_ignores_old_group_and_hash_failures(self):
        p = raw_payload()
        p.update(features={WD: False}, field_status={WD: 'runtime_error'}, field_quality={WD: 'source_unavailable'},
                 diagnostics={'automation': 'later MIME getter failure', 'plugins_hash': 'hash failed'})
        self.assert_cell(self.raw(p), 'F', 'RAW_REPORTED_FALSE')
        # Raw does not validate the maps it never reads, even if old wrappers are invalid.
        p.update(features=[], field_status='old malformed state', field_quality=None)
        self.assert_cell(self.raw(p), 'F', 'RAW_REPORTED_FALSE')

    def test_explicit_modes_never_fall_back_to_obtain_available_state(self):
        self.assert_cell(self.raw(flat({WD: True})), 'U')
        self.assert_cell(self.legacy(payload=raw_payload(True)), 'U')
        both = raw_payload(False)
        both.update(flat({WD: True}))
        self.assert_cell(self.raw(both), 'F')
        self.assert_cell(self.legacy(payload=both), 'T')
        raw_record(both)['api_present'] = False
        self.assert_cell(self.raw(both), 'FAILED')
        self.assert_cell(self.legacy(payload=both), 'T')
        for mode in [None, True, '', 'auto', 'proposed-raw-state-v1']:
            with self.subTest(mode=mode):
                self.assert_cell(webdriver_reported_state(both, mode=mode, source_binding=raw_binding()),
                                 'FAILED', 'INVALID_WEBDRIVER_MODE')

    def test_unknown_engine_unrelated_metadata_key_order_and_repeatability(self):
        p = raw_payload(False)
        expected = self.raw(p).to_dict()
        p['metadata'] = {'engine_version': None, 'label': 'attack', 'app_name': 'not a gate'}
        p['source_binding'] = {'trusted': False}
        before = copy.deepcopy(p)
        self.assertEqual(self.raw(p).to_dict(), expected)
        p['web_data']['automation_surface_layer']['webdriver_observation'] = dict(reversed(list(raw_record(p).items())))
        reordered = dict(reversed(list(p.items())))
        self.assertEqual(self.raw(reordered).to_dict(), expected)
        self.assertEqual(self.raw(reordered).to_dict(), expected)
        self.assertEqual(p, before)

    def test_malformed_envelope_fails_and_known_contradiction_wins_missing_binding(self):
        for p in [None, [], {}, {'record_schema_version': 'unsupported'}]:
            with self.subTest(payload=p):
                self.assert_cell(webdriver_reported_state(p, mode=RAW_MODE), 'FAILED')
        contradictory = raw_payload(True, api_present=False, value_read_status='not_attempted')
        del raw_record(contradictory)['observer_revision']
        self.assert_cell(webdriver_reported_state(contradictory, mode=RAW_MODE), 'FAILED')
        del raw_record(contradictory)['value_read_status']
        self.assert_cell(webdriver_reported_state(contradictory, mode=RAW_MODE), 'FAILED')

    def test_executor_exception_is_failed(self):
        with patch('hybridguard_agent.research.rule_semantics_revision_v1.webdriver._raw_object',
                   side_effect=RuntimeError('synthetic executor failure')):
            self.assert_cell(self.raw(), 'FAILED', 'EXECUTOR_ERROR')


class ContractAndIsolationTests(CellAssertions, unittest.TestCase):
    def test_semantic_cell_rejects_inconsistent_encodings(self):
        base = dict(candidate_id=LANG_ID, version='1.0.0', value=None, available=False,
                    evaluation_status='OK', reason='SYNTHETIC')
        for changes in [{'value': True}, {'available': True}, {'evaluation_status': 'UNKNOWN'},
                        {'value': False, 'available': True, 'evaluation_status': 'FAILED'},
                        {'value': 1, 'available': True}, {'available': 0}]:
            with self.subTest(changes=changes):
                with self.assertRaises((TypeError, ValueError)):
                    SemanticCell(**(base | changes))

    def test_manifest_two_candidates_and_legacy_overlap_are_explicit(self):
        m = module_manifest()
        self.assertEqual(set(m['candidates']), {LANG_ID, WD_ID})
        self.assertEqual(m['input_schema_version'], 'rsr-input-v1')
        self.assertEqual(m['webdriver_overlap']['old_rule_id'], 'W03')
        self.assertIs(m['webdriver_overlap']['shared_discriminative_information'], True)
        self.assertIs(m['webdriver_overlap']['independent_evidence_counting_allowed'], False)
        self.assertEqual(m['research_effectiveness'], 'NOT_EVALUATED')
        m['candidates'].clear()
        self.assertEqual(set(module_manifest()['candidates']), {LANG_ID, WD_ID})

    def test_import_has_no_explicit_io_network_scan_or_old_experiment_imports(self):
        script = r'''
import builtins, copy, dataclasses, enum, importlib, json, os, pathlib, re, socket, subprocess, sys, typing
import hybridguard_agent, hybridguard_agent.research
sys.dont_write_bytecode = True
def forbidden(*args, **kwargs):
    raise AssertionError('Pure module import attempted explicit I/O or network')
builtins.open = forbidden
for name in ('read_text', 'read_bytes', 'write_text', 'write_bytes', 'glob', 'rglob', 'iterdir'):
    setattr(pathlib.Path, name, forbidden)
for name in ('listdir', 'scandir', 'walk'):
    setattr(os, name, forbidden)
socket.socket = forbidden
socket.create_connection = forbidden
subprocess.Popen = forbidden
subprocess.run = forbidden
prefix = 'hybridguard_agent.research.rule_semantics_revision_v1'
for suffix in ('', '.contracts', '.input_adapter', '.language', '.webdriver', '.manifest'):
    importlib.import_module(prefix + suffix)
for name in sys.modules:
    assert not name.startswith(('hybridguard_agent.research.rule_learning', 'hybridguard_agent.rules',
                                'hybridguard_agent.evidence', 'hybridguard_agent.official_semantics')), name
print('IMPORT_ISOLATION_OK')
'''
        process = subprocess.run([sys.executable, '-B', '-c', script], cwd=REPO_ROOT,
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(process.stdout.strip(), 'IMPORT_ISOLATION_OK')


if __name__ == '__main__':
    unittest.main()
