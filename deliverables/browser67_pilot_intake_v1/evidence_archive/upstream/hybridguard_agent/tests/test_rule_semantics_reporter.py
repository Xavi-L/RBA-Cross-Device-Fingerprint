"""Artificial subprocess regressions for report attribution; no research records.

The subprocess runner receives ONLY temporary synthetic modules, never this test
module, so the reporter cannot recursively invoke its own regression suite.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / 'deliverables/rule_semantics_revision_module/run_checks.py'


class ReporterRegressionTests(unittest.TestCase):
    def simulate(self, sources, *, approved=(), existing_output=None):
        with tempfile.TemporaryDirectory(prefix='rsr-reporter-') as directory:
            root = Path(directory)
            names = [f'synthetic_reporter_case_{i}' for i in range(len(sources))]
            for i, source in enumerate(sources):
                header = 'import unittest\n'
                if i == 0:
                    header += ('SPECIFICATION_RESULTS = []\n'
                               f'APPROVED = {list(approved)!r}\n'
                               'def load_specification_fixtures():\n'
                               '    return [{"source_example_id": x} for x in APPROVED]\n')
                (root / (names[i] + '.py')).write_text(
                    header + textwrap.dedent(source), encoding='utf-8')
            output = root / 'report.json'
            if existing_output is not None:
                output.write_text(existing_output, encoding='utf-8')
            child = textwrap.dedent('''\
                import importlib.util, json, sys
                sys.dont_write_bytecode = True
                sys.path.insert(0, sys.argv[2])
                spec = importlib.util.spec_from_file_location('synthetic_reporter_runner', sys.argv[1])
                runner = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(runner)
                names = json.loads(sys.argv[3])
                args = ['--output', sys.argv[4]] if sys.argv[4] else []
                raise SystemExit(runner.main(args, test_modules=names, specification_module=names[0]))
            ''')
            command = [sys.executable, '-c', child, str(RUNNER), directory,
                       json.dumps(names), str(output) if existing_output is not None else '']
            proc = subprocess.run(command, capture_output=True, text=True, timeout=20,
                                  cwd=directory,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            if existing_output is not None:
                self.assertEqual(output.read_text(encoding='utf-8'), existing_output)
                return proc, None
            try:
                report = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                self.fail(f'No complete JSON report: {exc}; stderr={proc.stderr}')
            self.assertEqual(proc.returncode, report['exit_code'])
            self.assertEqual(len(report['tests']), report['independent_test_items'])
            self.assertEqual(len(report['fixture_events']), report['fixture_event_count'])
            self.assertFalse(report['real_samples'])
            return proc, report

    def assert_fixture_failure(self, report, *, methods, phase, scope):
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['exit_code'], 1)
        self.assertEqual(report['independent_test_items'], methods)
        self.assertEqual(report['fixture_error_events'], 1)
        self.assertEqual(report['fixture_events'][0]['phase'], phase)
        self.assertEqual(report['fixture_events'][0]['scope'], scope)
        self.assertEqual(report['fixture_events'][0]['status'], 'ERROR')

    def test_first_class_setup_failure_reports_json_and_unexecuted_example(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise RuntimeError('first setup failed')
                def test_not_reached(self):
                    SPECIFICATION_RESULTS.append({'source_example_id': 'approved-1'})
        '''], approved=['approved-1'])
        self.assert_fixture_failure(report, methods=0, phase='setUpClass', scope='CLASS')
        self.assertEqual(report['specification_examples'], [])
        self.assertEqual(report['specification_coverage']['uncovered'], ['approved-1'])
        self.assertEqual(report['specification_coverage']['executed_approved_examples'], 0)
        self.assertIn('first setup failed', report['fixture_events'][0]['error'])

    def test_later_class_setup_error_does_not_modify_pass(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_pass(self): pass
            class B(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise RuntimeError('later setup failed')
                def test_not_reached(self): pass
        '''])
        self.assert_fixture_failure(report, methods=1, phase='setUpClass', scope='CLASS')
        self.assertEqual(report['tests'][0]['status'], 'PASS')
        self.assertNotIn('error', report['tests'][0])
        self.assertIn('.B)', report['fixture_events'][0]['fixture_id'])

    def test_class_teardown_failure_keeps_method_pass_and_complete_coverage(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_pass(self):
                    SPECIFICATION_RESULTS.append({'source_example_id': 'approved-1'})
                @classmethod
                def tearDownClass(cls): raise RuntimeError('class teardown failed')
        '''], approved=['approved-1'])
        self.assert_fixture_failure(report, methods=1, phase='tearDownClass', scope='CLASS')
        self.assertEqual(report['tests'][0]['status'], 'PASS')
        self.assertEqual(report['specification_coverage']['uncovered'], [])
        self.assertTrue(report['specification_coverage']['unique_execution'])

    def test_module_setup_failure_has_no_method(self):
        _, report = self.simulate(['''
            def setUpModule(): raise RuntimeError('module setup failed')
            class A(unittest.TestCase):
                def test_not_reached(self): pass
        '''])
        self.assert_fixture_failure(report, methods=0, phase='setUpModule', scope='MODULE')

    def test_module_teardown_failure_keeps_prior_pass(self):
        _, report = self.simulate(['''
            def tearDownModule(): raise RuntimeError('module teardown failed')
            class A(unittest.TestCase):
                def test_pass(self): pass
        '''])
        self.assert_fixture_failure(report, methods=1, phase='tearDownModule', scope='MODULE')
        self.assertEqual(report['tests'][0]['status'], 'PASS')

    def test_class_fixture_skip_is_not_a_test_method(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise unittest.SkipTest('synthetic class skip')
                def test_not_reached(self): pass
        '''])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['independent_test_items'], 0)
        self.assertEqual(report['fixture_skip_events'], 1)
        self.assertEqual(report['fixture_events'][0]['scope'], 'CLASS')
        self.assertEqual(report['fixture_events'][0]['status'], 'SKIP')

    def test_class_decorator_skip_is_identified_without_inventing_fixture(self):
        _, report = self.simulate(['''
            @unittest.skip('class decorator skip')
            class A(unittest.TestCase):
                def test_skipped(self): pass
        '''])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['independent_test_items'], 1)
        self.assertEqual(report['fixture_event_count'], 0)
        self.assertEqual(report['tests'][0]['status'], 'SKIP')
        self.assertEqual(report['tests'][0]['events'][0]['skip_scope'], 'CLASS_DECORATOR')

    def test_normal_methods_subtests_and_method_skip_keep_correct_report(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_pass(self):
                    for value in (1, 2):
                        with self.subTest(value=value): self.assertGreater(value, 0)
                    SPECIFICATION_RESULTS.append({'source_example_id': 'approved-1'})
                @unittest.skip('ordinary skip')
                def test_skipped(self): pass
        '''], approved=['approved-1'])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['exit_code'], 0)
        self.assertEqual(report['independent_test_items'], 2)
        self.assertEqual(report['subtest_invocations'], 2)
        self.assertEqual([x['status'] for x in report['subtests']], ['PASS', 'PASS'])
        self.assertEqual([x['status'] for x in report['tests']], ['PASS', 'SKIP'])
        self.assertEqual(report['tests'][1]['events'][0]['skip_scope'], 'METHOD')
        self.assertEqual(report['fixture_event_count'], 0)
        self.assertEqual(report['specification_coverage']['executed_approved_examples'], 1)

    def test_multiple_method_events_and_subtest_errors_are_not_overwritten(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_multiple_subtests(self):
                    with self.subTest(kind='assertion'): self.fail('assertion failure')
                    with self.subTest(kind='exception'): raise ValueError('subtest error')
                    with self.subTest(kind='later_pass'): self.assertTrue(True)
                def tearDown(self): raise RuntimeError('method cleanup error')
        '''])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['independent_test_items'], 1)
        self.assertEqual(report['fixture_event_count'], 0)
        self.assertEqual(report['tests'][0]['status'], 'ERROR')
        self.assertEqual([x['status'] for x in report['tests'][0]['events']],
                         ['FAIL', 'ERROR', 'ERROR'])
        self.assertEqual([x['status'] for x in report['subtests']], ['FAIL', 'ERROR', 'PASS'])
        self.assertEqual(report['failures'], 1)
        self.assertEqual(report['errors'], 2)

    def test_subtest_skip_remains_separate_from_method_and_fixture(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_subtest_skip(self):
                    with self.subTest(kind='skip'): self.skipTest('one skipped subtest')
                    with self.subTest(kind='pass'): self.assertTrue(True)
        '''])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['tests'][0]['status'], 'PASS_WITH_SUBTEST_SKIPS')
        self.assertEqual(report['fixture_event_count'], 0)
        self.assertEqual(report['subtest_invocations'], 2)
        self.assertEqual([x['status'] for x in report['subtests']], ['SKIP', 'PASS'])

    def test_successful_methods_do_not_fill_missing_approved_results(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_pass(self): pass
        '''], approved=['never-executed'])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['exit_code'], 1)
        self.assertEqual(report['tests'][0]['status'], 'PASS')
        self.assertEqual(report['specification_coverage']['uncovered'], ['never-executed'])

    def test_multiple_fixture_errors_preserve_distinct_owners(self):
        _, report = self.simulate(['''
            class A(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise RuntimeError('A setup')
                def test_not_reached(self): pass
            class B(unittest.TestCase):
                def test_pass(self): pass
                @classmethod
                def tearDownClass(cls): raise RuntimeError('B teardown')
        '''])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['independent_test_items'], 1)
        self.assertEqual(report['tests'][0]['status'], 'PASS')
        self.assertEqual(report['fixture_error_events'], 2)
        self.assertEqual([x['phase'] for x in report['fixture_events']],
                         ['setUpClass', 'tearDownClass'])
        self.assertIn('.A)', report['fixture_events'][0]['fixture_id'])
        self.assertIn('.B)', report['fixture_events'][1]['fixture_id'])

    def test_existing_output_is_not_overwritten(self):
        proc, report = self.simulate(['''
            class A(unittest.TestCase):
                def test_not_reached(self): raise RuntimeError('must not run')
        '''], existing_output='historical evidence\n')
        self.assertIsNone(report)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('Refusing to overwrite existing report', proc.stderr)
        self.assertNotIn('must not run', proc.stderr)


if __name__ == '__main__':
    unittest.main()
