"""Finite synthetic runner regressions; no historical records or model work.

A fake loader provides explicit synthetic payloads and real SourceBinding values.
Where function calls are permitted, tests wrap the approved semantic functions
instead of copying expected states into the runner's output.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research.rule_semantics_revision_v1 import (
    SourceBinding, web_language_first_difference, webdriver_reported_state,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'deliverables/rule_semantics_candidate_evaluation/evaluate_candidates.py'
LANG = 'app.web_data.navigator_layer.language'
LANGS = 'app.web_data.navigator_layer.languages'
WD = 'app.web_data.automation_surface_layer.webdriver'
LANG_ID = 'RSR-LANG-FIRST-v1'
WD_ID = 'RSR-WEBDRIVER-STATE-v1'
REF_LANG = 'REFERENCE_LANG_LENGTH_GT1'
REF_WD = 'REFERENCE_WEBDRIVER_STRICT_TRUE'


def payload(values):
    return {'record_schema_version': 'rsr-input-v1', 'features': deepcopy(values),
            'field_status': {key: 'observed' for key in values},
            'field_quality': {key: 'observed_value' for key in values}}


class SyntheticAudit:
    """Only explicit sample IDs can be loaded; exceptions are test-local faults."""
    def __init__(self, records):
        self.records = records
        self.calls = []

    def load_input(self, sample_id, mode):
        self.calls.append((sample_id, mode))
        item = self.records[(sample_id, mode)]
        if isinstance(item, Exception):
            raise item
        return deepcopy(item)


class CandidateEvaluationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('synthetic_evaluation_runner', SCRIPT)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        self.temp = tempfile.TemporaryDirectory(prefix='rsr-candidate-eval-')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'results'
        self.ids = ['SYNTHETIC-a', 'SYNTHETIC-b', 'SYNTHETIC-c']
        self.contract = {'sample_ids': list(self.ids), 'candidates': [
            {'candidate_id': LANG_ID, 'version': '1.0.0', 'mode': 'default',
             'loader_mode': 'LANGUAGE', 'gate_version': 'rsr-language-first-gate-v1'},
            {'candidate_id': WD_ID, 'version': '1.0.0', 'mode': 'legacy_projection_v1',
             'loader_mode': 'WEBDRIVER_LEGACY', 'gate_version': 'rsr-webdriver-legacy-gate-v1'},
        ]}
        self.records = {}
        for sample_id, language, webdriver in zip(self.ids, ['en-US', 'fr-CA', 'x-invalid'], [False, True, False]):
            for mode, values, scope in (
                ('LANGUAGE', {LANG: language, LANGS: ['en-US', 'fr-CA']}, 'navigator_sync_v1'),
                ('WEBDRIVER_LEGACY', {WD: webdriver}, 'webdriver_legacy_projection_v1'),
            ):
                self.records[sample_id, mode] = {
                    'payload': payload(values),
                    'source_binding': SourceBinding('SYNTHETIC-source-v1', scope),
                    'audit': {'readiness': 'READY', 'input_status': 'COMPLETE',
                              'source_status': 'SUPPORTED_BY_EXISTING_LINEAGE'},
                    'source_refs': {'adapted_input': 'SYNTHETIC-only#' + sample_id},
                    'metadata': {'label': 'SYNTHETIC-ignored', 'phase': 'SYNTHETIC-ignored'},
                }
        self.audit = SyntheticAudit(self.records)
        self.references = {sample_id: {
            REF_LANG: {'state': 'T', 'reason': 'SYNTHETIC-reference', 'candidate_invoked': False},
            REF_WD: {'state': 'T' if sample_id == self.ids[1] else 'F',
                     'reason': 'SYNTHETIC-reference', 'candidate_invoked': False},
        } for sample_id in self.ids}

    def run_records(self, *, output=None):
        return self.runner.evaluate_records(self.ids, self.contract, self.audit,
            self.references, self.output if output is None else output)

    def read_rows(self, filename):
        return [json.loads(line) for line in (self.output / filename).read_text().splitlines()]


    def test_exact_id_candidate_keys_and_real_function_calls(self):
        with patch.object(self.runner, 'web_language_first_difference', wraps=web_language_first_difference) as language, \
             patch.object(self.runner, 'webdriver_reported_state', wraps=webdriver_reported_state) as webdriver:
            self.run_records()
        rows = self.read_rows('CANDIDATE_RESULTS.jsonl')
        expected = {(sample_id, candidate['candidate_id'], candidate['mode'])
                    for sample_id in self.ids for candidate in self.contract['candidates']}
        actual = [(row['opaque_id'], row['candidate_id'], row['mode']) for row in rows]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(language.call_count, 3)
        self.assertEqual(webdriver.call_count, 3)
        for call in webdriver.call_args_list:
            self.assertEqual(call.kwargs['mode'], 'legacy_projection_v1')
        for function in (language, webdriver):
            for call in function.call_args_list:
                supplied = call.args[0]
                self.assertEqual(set(supplied), {'record_schema_version', 'features', 'field_status', 'field_quality'})
                self.assertIsInstance(call.kwargs['source_binding'], SourceBinding)
        states = {(row['opaque_id'], row['candidate_id']): row['state'] for row in rows}
        self.assertEqual([states[sample_id, LANG_ID] for sample_id in self.ids], ['F', 'T', 'U'])
        self.assertEqual([states[sample_id, WD_ID] for sample_id in self.ids], ['U', 'T', 'U'])
        self.assertTrue(all(row['candidate_invoked'] for row in rows))
        self.assertEqual(len(self.read_rows('REFERENCE_RESULTS.jsonl')), 6)

    def test_single_input_read_errors_keep_failed_slots_and_continue(self):
        self.records[self.ids[0], 'LANGUAGE'] = FileNotFoundError('SYNTHETIC missing input')
        self.records[self.ids[1], 'WEBDRIVER_LEGACY'] = json.JSONDecodeError('SYNTHETIC bad JSON', '{', 1)
        with patch.object(self.runner, 'web_language_first_difference', wraps=web_language_first_difference) as language, \
             patch.object(self.runner, 'webdriver_reported_state', wraps=webdriver_reported_state) as webdriver:
            self.run_records()
        rows = self.read_rows('CANDIDATE_RESULTS.jsonl')
        self.assertEqual(len(rows), 6)
        failed = [row for row in rows if row['state'] == 'FAILED']
        self.assertEqual(len(failed), 2)
        self.assertTrue(all(row['origin'] == 'INPUT_OR_EXECUTION_FAILURE' for row in failed))
        self.assertTrue(all(not row['candidate_invoked'] for row in failed))
        self.assertEqual(language.call_count + webdriver.call_count, 4)
        self.assertTrue(any(row['opaque_id'] == self.ids[2] and row['candidate_invoked'] for row in rows))

    def test_module_exception_preserves_invoked_and_later_records(self):
        def synthetic_fault(payload, *, source_binding):
            if payload['features'][LANG] == 'fr-CA':
                raise RuntimeError('SYNTHETIC module execution error')
            return web_language_first_difference(payload, source_binding=source_binding)
        with patch.object(self.runner, 'web_language_first_difference', side_effect=synthetic_fault) as language:
            self.run_records()
        rows = self.read_rows('CANDIDATE_RESULTS.jsonl')
        failed = [row for row in rows if row['state'] == 'FAILED']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['opaque_id'], self.ids[1])
        self.assertTrue(failed[0]['candidate_invoked'])
        self.assertEqual(language.call_count, 3)
        self.assertTrue(any(row['opaque_id'] == self.ids[2] and row['state'] == 'U' for row in rows))

    def test_missing_binding_or_nonready_audit_never_gets_manual_pass(self):
        self.records[self.ids[0], 'LANGUAGE']['source_binding'] = None
        self.records[self.ids[1], 'WEBDRIVER_LEGACY']['audit']['readiness'] = 'CONDITIONAL'
        with patch.object(self.runner, 'web_language_first_difference', wraps=web_language_first_difference) as language, \
             patch.object(self.runner, 'webdriver_reported_state', wraps=webdriver_reported_state) as webdriver:
            self.run_records()
        rows = self.read_rows('CANDIDATE_RESULTS.jsonl')
        self.assertEqual(len(rows), 6)
        blocked = [row for row in rows if not row['candidate_invoked']]
        self.assertEqual(len(blocked), 2)
        self.assertTrue(all(row['state'] == 'FAILED' for row in blocked))
        self.assertEqual(language.call_count + webdriver.call_count, 4)

    def test_labels_and_phase_outside_payload_do_not_change_candidate_results(self):
        self.run_records()
        before = self.read_rows('CANDIDATE_RESULTS.jsonl')
        for item in self.records.values():
            item['metadata'] = {'label': 'CHANGED', 'phase': 'CHANGED', 'tool': 'CHANGED', 'prediction': True}
        second = Path(self.temp.name) / 'changed-metadata'
        self.run_records(output=second)
        after = [json.loads(line) for line in (second / 'CANDIDATE_RESULTS.jsonl').read_text().splitlines()]
        signature = lambda rows: [(x['opaque_id'], x['candidate_id'], x['mode'], x['state'], x['reason']) for x in rows]
        self.assertEqual(signature(before), signature(after))

    def test_existing_result_directory_is_never_overwritten_or_reevaluated(self):
        self.run_records()
        before = {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}
        with patch.object(self.runner, 'web_language_first_difference', side_effect=AssertionError('must not reevaluate')), \
             patch.object(self.runner, 'webdriver_reported_state', side_effect=AssertionError('must not reevaluate')):
            with self.assertRaises((ValueError, FileExistsError)):
                self.run_records()
        after = {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}
        self.assertEqual(before, after)


    def metadata(self):
        return {sample_id: {'opaque_id': sample_id, 'phase': phase,
            'bundle_id': 'SYNTHETIC-bundle', 'triplet_id': 'SYNTHETIC-triplet',
            'config_id': 'SYNTHETIC-config', 'environment_group_id': 'SYNTHETIC-env',
            'label': 'SYNTHETIC-analysis-only'} for sample_id, phase in
            zip(self.ids, ['clean_pre', 'attack', 'clean_post'])}

    def save_contract(self):
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / 'EVALUATION_CONTRACT.json').write_text(json.dumps(self.contract))

    def test_actual_module_failed_return_is_distinct_from_runner_failure(self):
        self.records[self.ids[0], 'LANGUAGE']['payload']['field_status'][LANG] = 'SYNTHETIC-invalid-status'
        with patch.object(self.runner, 'web_language_first_difference', wraps=web_language_first_difference) as language:
            execution = self.run_records()
        row = next(x for x in self.read_rows('CANDIDATE_RESULTS.jsonl')
                   if x['opaque_id'] == self.ids[0] and x['candidate_id'] == LANG_ID)
        self.assertEqual(row['state'], 'FAILED')
        self.assertEqual(row['origin'], 'CANDIDATE_RETURN')
        self.assertTrue(row['candidate_invoked'])
        self.assertEqual(row['semantic_cell']['evaluation_status'], 'FAILED')
        self.assertIsNone(row['semantic_cell']['value'])
        self.assertFalse(row['semantic_cell']['available'])
        self.assertIsNone(row['exception_type'])
        self.assertEqual(execution['runner_failures'], 0)
        self.assertEqual(language.call_count, 3)

    def test_missing_duplicate_outside_keys_and_raw_mode_are_rejected(self):
        self.run_records()
        rows = self.read_rows('CANDIDATE_RESULTS.jsonl')
        self.runner.validate_result_keys(rows, self.ids, self.contract['candidates'])
        outside = deepcopy(rows)
        outside[0]['opaque_id'] = 'SYNTHETIC-outside'
        for malformed in (rows[:-1], rows + [deepcopy(rows[0])], outside):
            with self.subTest(keys=[r['opaque_id'] for r in malformed]):
                with self.assertRaisesRegex(ValueError, 'RESULT_KEYS'):
                    self.runner.validate_result_keys(malformed, self.ids, self.contract['candidates'])
        self.contract['candidates'][1]['mode'] = 'raw_observation_v1'
        with patch.object(self.runner, 'webdriver_reported_state', side_effect=AssertionError('raw forbidden')):
            with self.assertRaisesRegex(ValueError, 'UNAUTHORIZED_CANDIDATE_OR_MODE'):
                self.run_records(output=Path(self.temp.name) / 'invalid-mode')

    def test_unknown_and_failed_keep_complete_denominators(self):
        self.records[self.ids[0], 'LANGUAGE']['payload']['field_status'][LANG] = 'SYNTHETIC-invalid-status'
        self.run_records()
        summary = self.runner.build_summary(self.read_rows('CANDIDATE_RESULTS.jsonl'),
            self.read_rows('REFERENCE_RESULTS.jsonl'), self.metadata(), self.ids)
        candidate = summary['candidates'][LANG_ID]
        overall = candidate['overall']
        self.assertEqual({k: overall[k] for k in ('N_expected', 'N_T', 'N_F', 'N_U', 'N_FAILED')},
                         {'N_expected': 3, 'N_T': 1, 'N_F': 0, 'N_U': 1, 'N_FAILED': 1})
        for table in [overall, candidate['combined_clean'], *candidate['by_phase'].values()]:
            self.assertEqual(sum(table['N_' + state] for state in ('T', 'F', 'U', 'FAILED')), table['N_expected'])
            self.assertEqual(table['condition_true']['n'], table['N_expected'])
        self.assertEqual(candidate['combined_clean']['N_expected'], 2)
        self.assertEqual(candidate['combined_clean']['N_FAILED'], 1)
        self.assertEqual(candidate['combined_clean']['N_U'], 1)
        self.assertEqual(sum(candidate['primary_unavailable_reasons']['FAILED'].values()), 1)
        self.assertEqual(sum(candidate['primary_unavailable_reasons']['U'].values()), 1)
        self.assertTrue(summary['comparisons'][WD_ID]['same_T_set'])
        self.assertEqual(summary['comparisons'][WD_ID]['cross_table_old_to_new'], {'F->U': 2, 'T->T': 1})

    def test_triplets_use_explicit_group_and_phase_not_result_adjacency(self):
        self.records[self.ids[2], 'LANGUAGE']['payload']['features'][LANG] = 'en-US'
        self.run_records()
        candidates = self.read_rows('CANDIDATE_RESULTS.jsonl')
        references = self.read_rows('REFERENCE_RESULTS.jsonl')
        metadata = self.metadata()
        metadata[self.ids[0]]['phase'] = 'clean_post'
        metadata[self.ids[2]]['phase'] = 'clean_pre'
        summary = self.runner.build_summary(list(reversed(candidates)), references, metadata, self.ids)
        triplets = summary['candidates'][LANG_ID]['triplets']
        self.assertEqual(triplets['complete_triplets'], 1)
        self.assertEqual(triplets['patterns'], {'F->T->F': 1})
        self.assertEqual(triplets['groups'][0]['opaque_ids_in_phase_order'], list(reversed(self.ids)))
        del metadata[self.ids[1]]['triplet_id']
        summary = self.runner.build_summary(candidates, references, metadata, self.ids)
        triplets = summary['candidates'][LANG_ID]['triplets']
        self.assertEqual(triplets['complete_triplets'], 0)
        self.assertEqual(triplets['patterns'], {})
        self.assertTrue(any(gap['reason'] == 'EXPLICIT_TRIPLET_ID_MISSING' for gap in triplets['gaps']))

    def test_saved_analysis_joins_metadata_after_close_and_never_calls_candidates(self):
        self.save_contract()
        execution = self.run_records()
        before = {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()}
        calls = []
        def metadata_loader(ids):
            receipt = json.loads((self.output / 'EXECUTION.json').read_text())
            self.assertTrue(receipt['results_closed_before_analysis'])
            self.assertEqual(len(self.read_rows('CANDIDATE_RESULTS.jsonl')), 6)
            self.assertEqual(len(self.read_rows('REFERENCE_RESULTS.jsonl')), 6)
            self.assertEqual(ids, self.ids)
            calls.append('metadata_after_saved_results')
            return self.metadata()
        def support_builder(rows, metadata, contract):
            self.assertEqual(len(rows), 6)
            self.assertEqual(set(metadata), set(self.ids))
            self.assertEqual(contract, self.contract)
            calls.append('support_after_metadata')
            return {'SYNTHETIC_support_called': True}
        with patch.object(self.runner, 'web_language_first_difference', side_effect=AssertionError('analysis cannot evaluate')), \
             patch.object(self.runner, 'webdriver_reported_state', side_effect=AssertionError('analysis cannot evaluate')):
            result = self.runner.analyze_saved(self.output, metadata_loader=metadata_loader,
                                              support_builder=support_builder)
        self.assertEqual(calls, ['metadata_after_saved_results', 'support_after_metadata'])
        self.assertTrue(result['summary']['analysis_reads_saved_results_only'])
        self.assertTrue(result['summary']['execution_complete'])
        self.assertEqual(execution['new_candidate_actual_calls'], 6)
        self.assertEqual(execution['reference_actual_computations'], 0)
        self.assertEqual(execution['reference_cached_states_reused'], 6)
        self.assertEqual((execution['fit'], execution['model_prediction'], execution['new_collection']), (0, 0, 0))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir() if p.is_file()})

    def test_invalid_saved_keys_block_metadata_join_without_reexecution(self):
        self.save_contract()
        self.run_records()
        rows = self.read_rows('CANDIDATE_RESULTS.jsonl')
        # Corrupt only this temporary synthetic output, never project evidence.
        (self.output / 'CANDIDATE_RESULTS.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows[:-1]))
        with patch.object(self.runner, 'web_language_first_difference', side_effect=AssertionError('must not evaluate')), \
             patch.object(self.runner, 'webdriver_reported_state', side_effect=AssertionError('must not evaluate')), \
             patch.object(self.runner, 'load_metadata', side_effect=AssertionError('must validate before labels')):
            with self.assertRaisesRegex(ValueError, 'RESULT_KEYS'):
                self.runner.analyze_saved(self.output)


if __name__ == '__main__':
    unittest.main()
