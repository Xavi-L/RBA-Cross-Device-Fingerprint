"""Focused saved-data regressions; never runs the old selector/predictor tests."""
import csv
import json
import re
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import build
import report
from missingness import availability_class


class ConsolidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = build.read(build.HERE / 'tables.json')
        cls.check = build.read(build.HERE / 'CHECK.json')
        cls.members, cls.models, cls.predictions = report.saved_context(build.EXT / 'results')

    def test_historical_table_uses_all_three_model_ids(self):
        rows = report.normal_rows(self.members, self.models, self.predictions,
                                  ('mtc_development', 'mtc_reserved_validation'))
        self.assertEqual(rows, self.tables['historical_mtc'])
        self.assertEqual(len(rows), 24)
        self.assertEqual(len({(r['base_model_id'], r['set_id'], r['cohort']) for r in rows}), 24)
        for fold, expected in [('01', (1,132,11)), ('02', (1,132,11)), ('03', (0,133,11))]:
            r = next(r for r in rows if r['fold'].endswith(fold) and
                     r['set_id'] == 'S0' and r['cohort'] == 'mtc_development')
            self.assertEqual((r['T'],r['F'],r['U']), expected)
            self.assertEqual((r['n'], r['FAILED'], r['defined']), (144,0,133))
        r = next(r for r in rows if r['fold'].endswith('03') and
                 r['set_id'] == 'W' and r['cohort'] == 'mtc_reserved_validation')
        self.assertEqual((r['T'],r['F'],r['U'],r['n'],r['defined']), (16,93,8,117,109))

    def test_equal_counts_are_not_equal_member_states(self):
        members = [{'sample_id':'a'}, {'sample_id':'b'}]
        p = {('a','first','S0'):{'state':'T'}, ('b','first','S0'):{'state':'F'},
             ('a','second','S0'):{'state':'F'}, ('b','second','S0'):{'state':'T'}}
        self.assertEqual(report.state_differences(members,p,'first','second','S0'), ['a','b'])
        for r in self.tables['configuration_state_comparison']:
            self.assertEqual(len(r['different_ids']), 0 if r['second'].endswith('02') else 8)

    def test_display_rejects_duplicate_or_misidentified_saved_outputs(self):
        saved = list(self.predictions.values())
        for corrupted in (saved + [saved[0]], [{**saved[0], 'identity':'EFFECTIVE_INTERVENTION'}] + saved[1:]):
            def fixture_rows(path):
                return self.members if path.name == 'members.jsonl' else corrupted
            with patch.object(report, 'rows', side_effect=fixture_rows):
                with self.assertRaises(ValueError):
                    report.saved_context(build.EXT / 'results')

    def test_app_primary_is_retention_with_complete_configuration_denominators(self):
        stages = build.read(build.APP / 'results/summary/all_stages.json')
        for total in self.tables['app']['main']:
            stage = 'FITTED' if total['scheme'] == 'APP_TREE' else 'RETENTION'
            source = [r for r in stages if r['scheme']==total['scheme'] and r['stage']==stage
                      and r['cohort']=='controlled' and r['identity']==total['identity']]
            self.assertEqual(len(source), 3)
            for key in ('N','T','F','U','FAILED','EMPTY_MODEL','defined'):
                self.assertEqual(sum(r[key] for r in source), total[key])
            configs = [r for r in self.tables['app']['configurations14']
                       if r['scheme']==total['scheme'] and r['identity']==total['identity']]
            self.assertEqual(len(configs), 14)
            self.assertEqual({r['N'] for r in configs}, {18 if total['identity']=='NORMAL' else 9})

    def test_unavailable_raw_is_distinct_from_adapter_error(self):
        self.assertEqual(availability_class(True,0,'observed','ambiguous_sentinel',0,'observed','ambiguous_sentinel'), 'A_RAW_UNAVAILABLE')
        self.assertEqual(availability_class(False,None,'unsupported','source_unavailable',None,'unsupported','source_unavailable'), 'A_RAW_UNAVAILABLE')
        self.assertEqual(availability_class(True,8,'observed','observed_value',None,'observed','observed_value'), 'B_ADAPTER_MISMATCH')
        self.assertEqual(availability_class(True,8,'observed','observed_value',8,'observed','observed_value'), 'C_OTHER_DEPENDENCY_OR_CAUSE_UNCONFIRMED')

    def test_nine_unknowns_and_three_counterexamples_keep_their_identity(self):
        def csv_rows(name):
            with (build.HERE/name).open() as f:
                return list(csv.DictReader(f))
        missing = csv_rows('missingness_review.csv')
        counter = csv_rows('normal_counterexamples.csv')
        self.assertEqual(len(missing), 9)
        self.assertEqual(len(counter), 3)
        self.assertFalse({r['sample_id'] for r in missing} & {r['sample_id'] for r in counter})
        self.assertEqual(sum(r['group']=='discovery' for r in missing), 7)
        self.assertEqual(sum(r['group']=='reserved_validation' for r in missing), 2)
        self.assertTrue(all(r['raw_browser_memory']=='0' and r['raw_field_status']=='observed' and
                            r['p1_quality']=='ambiguous_sentinel' and r['M']==r['B']=='U' and
                            r['identity']=='NORMAL' for r in missing))
        self.assertTrue(all(r['M']=='T' and r['B']=='F' and r['identity']=='NORMAL' and
                            r['derived_quality']=='observed_value' for r in counter))
        checks = self.check['targeted_binding_checks']
        self.assertEqual(len(checks), 12)
        self.assertTrue(all(all(r['bindings'].values()) and r['raw_p1_fields_match'] for r in checks))

    def test_accepted_method_and_p2_negative_result_are_not_relabelled(self):
        self.assertEqual(set(self.tables['method_roles']), set(build.ROLES))
        for r in self.tables['resource_combinations']:
            self.assertEqual(r['feasible'], r['set_id']=='S0')
            if r['role']=='selection':
                self.assertEqual((r['N'],r['normal']['n'],r['modified']['n']), (744,718,26))
                self.assertEqual(r['modified']['T'], {'S0':13,'M':19,'B':16,'W':19}[r['set_id']])
            else:
                self.assertEqual((r['N'],r['normal']['n'],r['modified']['n']), (261,261,0))
        for view in ('V_BOTH','V_BOTH_REL'):
            r = build.one(self.tables['four_view'], plan='P2', view=view)
            self.assertEqual((r['attack_T'],r['attack_n'],r['normal_T'],r['normal_n']), (4,8,6,34))

    def test_report_render_and_local_links(self):
        report.render()  # display-only path, under the saved-only execution guard
        text = (build.EXT/'REPORT.md').read_text()
        self.assertNotIn('上表三个配置逐条状态相同', text)
        self.assertIn('|03|S0|development|144|0|133|11|0|133/144|', text)
        self.assertIn('配置03：基础MTC discovery为0/567/63/0', text)
        for name in ('REPORT.md','REPORT_CORRECTION.md'):
            p = build.HERE/name
            for link in re.findall(r'\]\(([^)]+)\)', p.read_text()):
                if not link.startswith(('https:','http:')):
                    self.assertTrue((p.parent/link.split('#')[0]).exists(), link)

    def test_guard_blocks_a_synthetic_engine_entry_before_its_body(self):
        namespace = {}
        exec(compile('def predict():\n    raise AssertionError("BODY_MUST_NOT_RUN")\n',
                     str(build.HERE/'synthetic_engine_fixture.py'), 'exec'), namespace)
        with build.saved_only_guard() as guard:
            with self.assertRaisesRegex(RuntimeError, 'SAVED_ONLY_ENGINE_CALL_BLOCKED'):
                namespace['predict']()
        self.assertEqual(guard['forbidden_engine_calls'], 1)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ConsolidationTests)
    with build.saved_only_guard() as guard:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    check = build.read(build.HERE/'CHECK.json')
    check['regression_tests'] = dict(tests_run=result.testsRun, failures=len(result.failures),
                                    errors=len(result.errors), passed=result.wasSuccessful(),
                                    saved_data_engine_guard=guard,
                                    synthetic_engine_attempts_intentionally_blocked=1,
                                    research_prediction_or_selection_calls=0)
    check['status'] = 'PASS' if result.wasSuccessful() else 'REGRESSION_FAILED'
    build.write_json('CHECK.json', check)
    sys.exit(0 if result.wasSuccessful() else 1)
