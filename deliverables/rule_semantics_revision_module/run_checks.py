#!/usr/bin/env python3
"""Run the two approved synthetic test modules and record actual outcomes.

No unittest discovery, old predictors, training, or real research records.
Use --output NEW_PATH to retain a report; an existing path is never replaced.
The explicit-module Python API supports isolated artificial reporter regressions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
TEST_MODULES = (
    'hybridguard_agent.tests.test_rule_semantics_revision_v1',
    'hybridguard_agent.tests.test_rule_semantics_design_validator',
)


class RecordingResult(unittest.TextTestResult):
    """Keep started methods and non-method fixture callbacks in separate ledgers.

    unittest supplies an error holder, without startTest(), for class/module
    fixtures. Object identity, rather than the most recent method, owns events.
    """
    _PRIORITY = {'RUNNING': 0, 'PASS': 1, 'PASS_WITH_SUBTEST_SKIPS': 2,
                 'EXPECTED_FAILURE': 3, 'SKIP': 4, 'UNEXPECTED_SUCCESS': 5,
                 'FAIL': 6, 'ERROR': 7}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executions = []
        self.subtest_executions = []
        self.fixture_events = []
        self._method_records = {}
        # Retain identities even when unittest releases completed suite entries.
        self._test_objects = {}

    def startTest(self, test):
        item = {'test_id': test.id(), 'status': 'RUNNING', 'events': []}
        self._method_records[id(test)] = item
        self._test_objects[id(test)] = test
        self.executions.append(item)
        super().startTest(test)

    @staticmethod
    def _fixture_context(test):
        description = test.id()
        phase = description.partition(' (')[0]
        if phase in ('setUpClass', 'tearDownClass'):
            scope = 'CLASS'
        elif phase in ('setUpModule', 'tearDownModule'):
            scope = 'MODULE'
        else:
            scope = 'OTHER_NON_METHOD'
        return description, phase, scope

    def _event(self, test, status, **details):
        event = {'status': status, **details}
        item = self._method_records.get(id(test))
        if item is None:
            fixture_id, phase, scope = self._fixture_context(test)
            self.fixture_events.append({'fixture_id': fixture_id, 'phase': phase,
                                        'scope': scope, **event})
            return
        item['events'].append(event)
        if self._PRIORITY[status] >= self._PRIORITY[item['status']]:
            item['status'] = status
        # Events retain every failure/cleanup outcome; a later PASS cannot erase it.
        if 'error' in details:
            item['error'] = details['error']
        if 'reason' in details:
            item['reason'] = details['reason']

    def stopTest(self, test):
        item = self._method_records[id(test)]
        if item['status'] == 'RUNNING':
            # unittest does not emit addSuccess for a method with skipped subtests.
            item['status'] = 'PASS_WITH_SUBTEST_SKIPS' if any(
                x['test_id'] == test.id() and x['status'] == 'SKIP'
                for x in self.subtest_executions) else 'PASS'
        super().stopTest(test)

    def addSuccess(self, test):
        self._event(test, 'PASS')
        super().addSuccess(test)

    def addFailure(self, test, err):
        self._event(test, 'FAIL', error=self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self._event(test, 'ERROR', error=self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSkip(self, test, reason):
        parent = getattr(test, 'test_case', None)
        if parent is not None and id(parent) in self._method_records:
            self.subtest_executions.append({'test_id': parent.id(),
                'subtest_id': test.id(), 'status': 'SKIP', 'reason': reason})
            self._event(parent, 'PASS_WITH_SUBTEST_SKIPS',
                        kind='SUBTEST_SKIP', subtest_id=test.id(), reason=reason)
        else:
            skip_scope = ('CLASS_DECORATOR' if id(test) in self._method_records
                          and getattr(type(test), '__unittest_skip__', False)
                          else 'METHOD' if id(test) in self._method_records else 'FIXTURE')
            self._event(test, 'SKIP', reason=reason, skip_scope=skip_scope)
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        status = ('PASS' if err is None else
                  'FAIL' if issubclass(err[0], test.failureException) else 'ERROR')
        item = {'test_id': test.id(), 'subtest_id': subtest.id(), 'status': status}
        if err is not None:
            item['error'] = self._exc_info_to_string(err, subtest)
            self._event(test, status, kind='SUBTEST', subtest_id=subtest.id(),
                        error=item['error'])
        self.subtest_executions.append(item)
        super().addSubTest(test, subtest, err)

    def addExpectedFailure(self, test, err):
        self._event(test, 'EXPECTED_FAILURE', error=self._exc_info_to_string(err, test))
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self._event(test, 'UNEXPECTED_SUCCESS')
        super().addUnexpectedSuccess(test)


def collect_report(*, test_modules=None, specification_module=None, stream=None, command=None):
    """Execute only explicitly named modules; never discover or recurse into self.

    The default specification provider is the approved synthetic module. Artificial
    regressions may supply their own provider with SPECIFICATION_RESULTS and
    load_specification_fixtures; these are observations, not fabricated results.
    """
    names = tuple(TEST_MODULES if test_modules is None else test_modules)
    provider_name = TEST_MODULES[0] if specification_module is None else specification_module
    module = importlib.import_module(provider_name)
    module.SPECIFICATION_RESULTS.clear()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    start = time.monotonic()
    result = unittest.TextTestRunner(stream=sys.stderr if stream is None else stream,
                                    verbosity=2, resultclass=RecordingResult).run(suite)
    examples = list(module.SPECIFICATION_RESULTS)
    ids = [x.get('source_example_id') for x in examples if x.get('source_example_id')]
    expected_ids = {x['source_example_id'] for x in module.load_specification_fixtures()
                    if x.get('source_example_id')}
    executed_ids = set(ids)
    missing = sorted(expected_ids - executed_ids)
    unexpected = sorted(executed_ids - expected_ids)
    duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
    complete = not missing and not unexpected and not duplicates
    exit_code = 0 if result.wasSuccessful() and complete else 1
    return {
        'schema_version': 'rule-semantics-module-tests-v1',
        'status': 'PASS' if exit_code == 0 else 'FAIL',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'command': command if command is not None else [],
        'cwd': str(Path.cwd()), 'exit_code': exit_code,
        'test_modules': list(names), 'specification_module': provider_name,
        'independent_test_items': result.testsRun,
        'test_item_count_definition': 'Started unittest TestCase methods; subtests and non-method fixture events are counted separately, not added again',
        'fixture_event_count': len(result.fixture_events),
        'fixture_error_events': sum(x['status'] == 'ERROR' for x in result.fixture_events),
        'fixture_skip_events': sum(x['status'] == 'SKIP' for x in result.fixture_events),
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'expected_failures': len(result.expectedFailures),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'subtest_invocations': len(result.subtest_executions),
        'elapsed_seconds': round(time.monotonic() - start, 6),
        'tests': result.executions, 'fixture_events': result.fixture_events,
        'subtests': result.subtest_executions, 'specification_examples': examples,
        'specification_coverage': {'expected_approved_examples': len(expected_ids),
                                   'executed_approved_examples': len(executed_ids & expected_ids),
                                   'uncovered': missing, 'unexpected': unexpected,
                                   'duplicate_execution_ids': duplicates,
                                   'unique_execution': complete,
                                   'other_four_families': 'NOT_IMPLEMENTED_OR_EXECUTED_BY_AUTHORIZED_SCOPE'},
        'real_samples': False, 'real_collection_count': 0, 'fit_count': 0,
        'model_prediction_count': 0, 'real_record_candidate_evaluation_count': 0,
        'research_effectiveness': 'NOT_EVALUATED',
        'historical_record_applicability': 'NOT_AUDITED',
        'independent_confirmation': 'NOT_PERFORMED',
        'limits': 'Synthetic semantic functions and temporary Git regression fixtures only; U/FAILED can be expected successful test outcomes.',
    }


def main(argv=None, *, test_modules=None, specification_module=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error('Refusing to overwrite existing report: ' + str(args.output))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    command = ['PYTHONDONTWRITEBYTECODE=1', sys.executable, str(Path(__file__).resolve()),
               *(argv if argv is not None else sys.argv[1:])]
    report = collect_report(test_modules=test_modules, specification_module=specification_module,
                            command=command)
    if args.output is not None:
        with args.output.open('x', encoding='utf-8') as out:
            out.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
