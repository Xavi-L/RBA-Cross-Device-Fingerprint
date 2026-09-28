#!/usr/bin/env python3
"""Explicit synthetic suites only; never execute the real evaluation command."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from deliverables.rule_semantics_revision_module.run_checks import collect_report

MODULES = (
    'hybridguard_agent.tests.test_rule_semantics_revision_v1',
    'hybridguard_agent.tests.test_rule_semantics_input_readiness',
    'hybridguard_agent.tests.test_rule_semantics_input_audit',
    'hybridguard_agent.tests.test_rule_semantics_candidate_evaluation',
    'hybridguard_agent.tests.test_rule_semantics_train_support',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('REFUSE_EXISTING_TEST_REPORT')
    report = collect_report(test_modules=MODULES, command=[
        'PYTHONDONTWRITEBYTECODE=1', sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])
    report['schema_version'] = 'rsr-fixed-evaluation-tests-v1'
    report['scope'] = 'Synthetic and temporary-input-tree tests. Real execution counts are recorded separately in EXECUTION.json.'
    report['by_module'] = {name: dict(Counter(t['status'] for t in report['tests']
        if t['test_id'].startswith(name + '.'))) for name in MODULES}
    with args.output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'exit_code', 'independent_test_items',
        'failures', 'errors', 'skipped', 'subtest_invocations', 'by_module')}, indent=2))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
