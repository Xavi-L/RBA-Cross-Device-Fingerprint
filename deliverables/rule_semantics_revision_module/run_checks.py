#!/usr/bin/env python3
"""Run exactly two synthetic test modules and record actual test/fixture outcomes.

No unittest discovery, old predictors, training, or real research records.
Use --output NEW_PATH to retain a report; an existing path is never replaced.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import time
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
TEST_MODULES = (
    'hybridguard_agent.tests.test_rule_semantics_revision_v1',
    'hybridguard_agent.tests.test_rule_semantics_design_validator',
)


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executions = []
        self.subtest_executions = []
        self._current = None

    def startTest(self, test):
        self._current = {'test_id': test.id(), 'status': 'RUNNING'}
        self.executions.append(self._current)
        super().startTest(test)

    def addSuccess(self, test):
        self._current['status'] = 'PASS'
        super().addSuccess(test)

    def addFailure(self, test, err):
        self._current.update(status='FAIL', error=self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self._current.update(status='ERROR', error=self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSkip(self, test, reason):
        self._current.update(status='SKIP', reason=reason)
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        item = {'test_id': test.id(), 'subtest_id': subtest.id(),
                'status': 'PASS' if err is None else 'FAIL'}
        if err is not None:
            item['error'] = self._exc_info_to_string(err, subtest)
            self._current['status'] = 'FAIL'
        self.subtest_executions.append(item)
        super().addSubTest(test, subtest, err)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error('Refusing to overwrite existing report: ' + str(args.output))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    module = importlib.import_module(TEST_MODULES[0])
    module.SPECIFICATION_RESULTS.clear()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in TEST_MODULES)
    start = time.monotonic()
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, resultclass=RecordingResult).run(suite)
    examples = list(module.SPECIFICATION_RESULTS)
    ids = [x.get('source_example_id') for x in examples]
    fixtures = module.load_specification_fixtures()
    expected_ids = {x['source_example_id'] for x in fixtures if x.get('source_example_id')}
    executed_ids = {x for x in ids if x}
    missing = sorted(expected_ids - executed_ids)
    complete = not missing and len(executed_ids) == len([x for x in ids if x])
    exit_code = 0 if result.wasSuccessful() and complete else 1
    report = {
        'schema_version': 'rule-semantics-module-tests-v1',
        'status': 'PASS' if exit_code == 0 else 'FAIL',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'command': ['PYTHONDONTWRITEBYTECODE=1', sys.executable,
                    str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])],
        'cwd': str(Path.cwd()), 'exit_code': exit_code,
        'test_modules': list(TEST_MODULES),
        'independent_test_items': result.testsRun,
        'test_item_count_definition': 'unittest TestCase methods; subtests are counted separately, not added again',
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'subtest_invocations': len(result.subtest_executions),
        'elapsed_seconds': round(time.monotonic() - start, 6),
        'tests': result.executions, 'subtests': result.subtest_executions,
        'specification_examples': examples,
        'specification_coverage': {'expected_approved_examples': len(expected_ids),
                                   'executed_approved_examples': len(executed_ids),
                                   'uncovered': missing, 'unique_execution': complete,
                                   'other_four_families': 'NOT_IMPLEMENTED_OR_EXECUTED_BY_AUTHORIZED_SCOPE'},
        'real_samples': False, 'real_collection_count': 0, 'fit_count': 0,
        'model_prediction_count': 0, 'real_record_candidate_evaluation_count': 0,
        'research_effectiveness': 'NOT_EVALUATED',
        'historical_record_applicability': 'NOT_AUDITED',
        'independent_confirmation': 'NOT_PERFORMED',
        'limits': 'Synthetic semantic functions and temporary Git regression fixtures only; U/FAILED can be expected successful test outcomes.',
    }
    if args.output is not None:
        with args.output.open('x', encoding='utf-8') as out:
            out.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
