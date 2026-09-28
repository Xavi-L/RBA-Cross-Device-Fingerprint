#!/usr/bin/env python3
"""Only the five named synthetic/regression suites; no real input audit here."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from deliverables.rule_semantics_revision_module.run_checks import collect_report

MODULES = (
    'hybridguard_agent.tests.test_rule_semantics_revision_v1',
    'hybridguard_agent.tests.test_rule_semantics_design_validator',
    'hybridguard_agent.tests.test_rule_semantics_reporter',
    'hybridguard_agent.tests.test_rule_semantics_input_readiness',
    'hybridguard_agent.tests.test_rule_semantics_input_audit',
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New JSON path only; existing reports refused.')
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error('REFUSE_EXISTING_REPORT: ' + str(args.output))
    report = collect_report(test_modules=MODULES,
        command=['PYTHONDONTWRITEBYTECODE=1', sys.executable, str(Path(__file__).resolve()),
                 *(sys.argv[1:] if argv is None else argv)])
    report['schema_version'] = 'rsr-input-readiness-tests-v1'
    report['suite_scope'] = 'Synthetic module/reporter/adapter tests and temporary Git/input-tree fixtures only; real input audit separately in SUMMARY.json.'
    report['historical_record_applicability'] = 'SEE_SEPARATE_INPUT_READINESS_SUMMARY'
    report['by_module'] = {name: dict(Counter(t['status'] for t in report['tests']
        if t['test_id'].startswith(name + '.'))) for name in MODULES}
    report['expected_inner_fixture_failures'] = 'Reporter regressions intentionally induce inner fixture failures and assert complete FAIL reports/nonzero exits. Those are successful outer regression assertions, not actual project failures.'
    report['reproduced_before_fix'] = [
        'First setUpClass error: AttributeError (NoneType has no attribute update) before a method started.',
        'After a PASS, another class setUpClass error incorrectly changed the prior method to ERROR.',
    ]
    if args.output is not None:
        with args.output.open('x', encoding='utf-8') as f:
            f.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'exit_code', 'independent_test_items',
        'failures', 'errors', 'skipped', 'fixture_event_count', 'subtest_invocations', 'by_module')},
        ensure_ascii=False, indent=2))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
