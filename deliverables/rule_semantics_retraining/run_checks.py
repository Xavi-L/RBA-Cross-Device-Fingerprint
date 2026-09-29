#!/usr/bin/env python3
"""Focused synthetic integration tests; no historical fitting or predictions."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone
import time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from deliverables.rule_semantics_revision_module.run_checks import RecordingResult
MODULES=('hybridguard_agent.tests.test_rule_semantics_retraining',
         'hybridguard_agent.tests.test_rule_semantics_retraining_runner')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.output.exists():p.error('REFUSE_EXISTING_TEST_REPORT')
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(m) for m in MODULES)
    started=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordingResult).run(suite)
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','exit_code':0 if result.wasSuccessful() else 1,
        'generated_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-started,
        'command':['PYTHONDONTWRITEBYTECODE=1',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],
        'test_modules':list(MODULES),'independent_test_items':result.testsRun,'test_item_definition':'Started TestCase methods; subtests and fixture events not added again',
        'tests':result.executions,'subtests':result.subtest_executions,'fixture_events':result.fixture_events,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'subtest_invocations':len(result.subtest_executions),
        'real_fit_calls':0,'real_model_prediction_calls':0,'real_candidate_calls':0,
        'synthetic_fit_note':'Training and prediction exercised only on artificial fixtures; forced failures are expected test cases.'}
    report['schema_version']='rsr-retraining-tests-v1'
    report['scope']='Synthetic fixtures only. Historical fit/predict/candidate calls are zero in this test command.'
    report['by_module']={m:dict(Counter(t['status'] for t in report['tests'] if t['test_id'].startswith(m+'.'))) for m in MODULES}
    with args.output.open('x') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','exit_code','independent_test_items','failures','errors','skipped','subtest_invocations','by_module')},indent=2))
    return report['exit_code']
if __name__=='__main__':raise SystemExit(main())
