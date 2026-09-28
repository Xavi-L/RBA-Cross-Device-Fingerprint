"""Regression tests use real, isolated Git histories and metadata-only fixtures."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / 'deliverables/rule_semantics_revision/validate_design.py'
MODULE_SPEC = importlib.util.spec_from_file_location('rsr_design_validator', VALIDATOR_PATH)
validator = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(validator)


def git(root, *args):
    completed = subprocess.run(['git', *args], cwd=root, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    return completed.stdout.decode().strip()


class DesignValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template_dir = tempfile.TemporaryDirectory(prefix='rsr-validator-template-')
        cls.template = Path(cls.template_dir.name)
        git(cls.template, 'init', '-q')
        git(cls.template, 'config', 'user.name', 'Synthetic Validator Fixture')
        git(cls.template, 'config', 'user.email', 'fixture@example.invalid')
        git(cls.template, 'config', 'commit.gpgsign', 'false')
        (cls.template / 'unrelated.txt').write_text('synthetic baseline\n')
        git(cls.template, 'add', 'unrelated.txt')
        git(cls.template, 'commit', '-qm', 'synthetic baseline')
        cls.baseline = git(cls.template, 'rev-parse', 'HEAD')

        design = ROOT / validator.DESIGN_PATH
        spec = json.loads((design / 'CANDIDATE_SPEC.json').read_text())
        extra = json.loads((design / 'ADDITIONAL_SOURCES.json').read_text())
        # Only specifications, code, catalogs, evidence registers and saved model
        # identities are copied. No attack/clean record fixture is read or copied.
        paths = {validator.DESIGN_PATH / name for name in validator.FROZEN_DESIGN_FILES}
        paths.add(validator.DESIGN_PATH / 'validate_design.py')
        paths.update(Path(x) for x in (
            'deliverables/normal_app_behavior_review/SOURCE_REGISTER.json',
            'deliverables/normal_app_behavior_review/RULE_IMPACT.csv',
            'android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv',
            'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol/CANDIDATE_LEDGER.jsonl',
            'hybridguard_agent/research/rule_learning_v2/relations.py',
        ))
        paths.update(Path(x['path']) for x in spec['baseline_models'])
        paths.update(Path(x['local_path']) for x in extra['sources'] if x.get('local_path'))
        for relpath in sorted(paths):
            target = cls.template / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relpath, target)
        spec['actual_head'] = cls.baseline
        spec['first_review_commit'] = cls.baseline
        (cls.template / validator.DESIGN_PATH / 'CANDIDATE_SPEC.json').write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + '\n')
        git(cls.template, 'add', '--', *(p.as_posix() for p in sorted(paths)))
        git(cls.template, 'commit', '-qm', 'synthetic approved design')
        cls.approved = git(cls.template, 'rev-parse', 'HEAD')

    @classmethod
    def tearDownClass(cls):
        cls.template_dir.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rsr-validator-case-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(self.template, self.root)
        self.design = self.root / validator.DESIGN_PATH

    def validate(self, approved=None):
        return validator.validate(self.root, approved or self.approved)

    def assert_pass(self, report):
        self.assertEqual('PASS', report['status'], [x for x in report['checks'] if x['status'] == 'FAIL'])
        self.assertEqual(report['checks_total'], report['checks_passed'])

    def find_check(self, report, name):
        return next(x for x in report['checks'] if x['check'] == name)

    def run_main(self, *args, cwd=None):
        """Execute the real parser/function in another process, injecting only fixtures."""
        source = (
            'import importlib.util, pathlib, sys; '
            's=importlib.util.spec_from_file_location("validator", sys.argv[1]); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
            'raise SystemExit(m.main(sys.argv[4:], repo_root=pathlib.Path(sys.argv[2]), '
            'approved_design_commit=sys.argv[3]))'
        )
        return subprocess.run([sys.executable, '-c', source, str(VALIDATOR_PATH), str(self.root),
                               self.approved, *map(str, args)], cwd=cwd or self.root,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_baseline_then_approved_design_uses_ancestry_not_head_equality(self):
        git(self.root, 'checkout', '-q', '--detach', self.baseline)
        before = self.validate()
        self.assertEqual('FAIL', before['status'])
        self.assertEqual('FAIL', self.find_check(before, 'approved_design_is_ancestor_of_validation_HEAD')['status'])
        git(self.root, 'checkout', '-q', '--detach', self.approved)
        after = self.validate()
        self.assert_pass(after)
        self.assertEqual(self.baseline, after['design_starting_baseline'])
        self.assertEqual(self.approved, after['approved_design_commit'])
        self.assertEqual(self.approved, after['validation_head'])
        self.assertNotEqual(after['design_starting_baseline'], after['validation_head'])

    def test_unchanged_design_on_normal_descendant_passes(self):
        (self.root / 'unrelated.txt').write_text('synthetic descendant\n')
        git(self.root, 'add', 'unrelated.txt')
        git(self.root, 'commit', '-qm', 'unrelated descendant')
        report = self.validate()
        self.assert_pass(report)
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), report['validation_head'])
        self.assertNotEqual(report['validation_head'], report['approved_design_commit'])

    def test_each_frozen_file_version_difference_is_detected(self):
        for name in validator.FROZEN_DESIGN_FILES:
            with self.subTest(file=name):
                path = self.design / name
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                try:
                    report = self.validate()
                    identity = self.find_check(report, 'approved_design_file_identity')
                    self.assertEqual('FAIL', report['status'])
                    self.assertEqual('FAIL', identity['status'])
                    changed = [x for x in identity['detail']['files'] if x['status'] != 'MATCH']
                    self.assertEqual([{'path': (validator.DESIGN_PATH / name).as_posix(),
                                       'status': 'VERSION_DIFFERENCE'}], changed)
                finally:
                    path.write_bytes(original)

    def test_committed_design_revision_is_not_silently_approved(self):
        path = self.design / 'DESIGN.md'
        path.write_bytes(path.read_bytes() + b'\nSynthetic revision.\n')
        git(self.root, 'add', '--', str(path.relative_to(self.root)))
        git(self.root, 'commit', '-qm', 'unapproved design revision')
        report = self.validate()
        self.assertEqual('PASS', self.find_check(report, 'approved_design_is_ancestor_of_validation_HEAD')['status'])
        self.assertEqual('FAIL', self.find_check(report, 'approved_design_file_identity')['status'])

    def test_baseline_must_be_ancestor_of_approved_design(self):
        git(self.root, 'checkout', '-q', '--orphan', 'disconnected')
        git(self.root, 'commit', '-qm', 'disconnected approved fixture')
        report = self.validate(git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual('FAIL', report['status'])
        self.assertEqual('NOT_ANCESTOR', self.find_check(report, 'design_baseline_is_ancestor_of_approved_design')['detail']['status'])

    def test_missing_approved_history_is_explicitly_unverifiable(self):
        report = self.validate('f' * 40)
        self.assertEqual('FAIL', report['status'])
        self.assertEqual('UNVERIFIABLE', report['history_status'])
        self.assertEqual('UNVERIFIABLE', self.find_check(report, 'git_history_available')['detail']['status'])

    def test_missing_baseline_history_is_explicitly_unverifiable(self):
        path = self.design / 'CANDIDATE_SPEC.json'
        spec = json.loads(path.read_text())
        spec['actual_head'] = 'f' * 40
        path.write_text(json.dumps(spec))
        git(self.root, 'add', '--', str(path.relative_to(self.root)))
        git(self.root, 'commit', '-qm', 'fixture references unavailable baseline')
        report = self.validate(git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual('FAIL', report['status'])
        self.assertEqual('UNVERIFIABLE', report['history_status'])
        self.assertEqual('UNVERIFIABLE', self.find_check(report, 'git_history_available')['detail']['status'])

    def test_default_cli_full_json_and_historical_report_immutable_from_other_cwd(self):
        historical = (self.design / 'VALIDATION.json').read_bytes()
        status = git(self.root, 'status', '--porcelain=v1')
        run = self.run_main(cwd=Path(self.temp.name))
        self.assertEqual(0, run.returncode, run.stderr)
        report = json.loads(run.stdout)
        self.assert_pass(report)
        self.assertIn('checks', report)
        self.assertEqual('', run.stderr)
        self.assertEqual(historical, (self.design / 'VALIDATION.json').read_bytes())
        self.assertEqual(status, git(self.root, 'status', '--porcelain=v1'))

    def test_explicit_output_exclusively_creates_full_report(self):
        output = Path(self.temp.name) / 'new-validation.json'
        run = self.run_main('--output', output)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual(json.loads(run.stdout), json.loads(output.read_text()))
        self.assertEqual('CREATED', json.loads(run.stdout)['report_output']['status'])

    def test_existing_output_including_historical_report_never_overwritten(self):
        arbitrary = Path(self.temp.name) / 'existing.json'
        arbitrary.write_bytes(b'original report\n')
        for path in (arbitrary, self.design / 'VALIDATION.json'):
            with self.subTest(path=str(path)):
                before = path.read_bytes()
                run = self.run_main('--output', path)
                self.assertNotEqual(0, run.returncode)
                report = json.loads(run.stdout)
                self.assertEqual('FAIL', report['status'])
                self.assertEqual('REFUSED_OR_FAILED', report['report_output']['status'])
                self.assertEqual(before, path.read_bytes())

    def test_unrelated_staged_unstaged_untracked_changes_are_diagnostic_and_preserved(self):
        path = self.root / 'unrelated.txt'
        path.write_text('staged text\n')
        git(self.root, 'add', 'unrelated.txt')
        path.write_text('staged text plus unstaged text\n')
        (self.root / 'untracked.txt').write_text('untracked text\n')
        before_index = (self.root / '.git/index').read_bytes()
        before_status = git(self.root, 'status', '--porcelain=v1')
        before_content = path.read_bytes()
        report = self.validate()
        self.assert_pass(report)
        self.assertEqual(1, report['git_workspace']['staged_path_count'])
        self.assertFalse(report['git_workspace']['affects_design_result'])
        self.assertEqual(before_status, git(self.root, 'status', '--porcelain=v1'))
        self.assertEqual(before_content, path.read_bytes())
        self.assertEqual(before_index, (self.root / '.git/index').read_bytes())

    def test_changed_initial_status_snapshot_does_not_invalidate_design(self):
        snapshot = Path(self.temp.name) / 'initial-status.bin'
        snapshot.write_bytes(b'')
        (self.root / 'unrelated.txt').write_text('changed after snapshot\n')
        report = validator.validate(self.root, self.approved, snapshot)
        self.assert_pass(report)
        self.assertEqual('CHANGED', report['workspace_status_preservation']['status'])
        self.assertFalse(report['workspace_status_preservation']['affects_design_result'])

    def test_malformed_json_returns_complete_failure_json_without_traceback(self):
        (self.design / 'CANDIDATE_SPEC.json').write_text('{broken json')
        run = self.run_main()
        self.assertNotEqual(0, run.returncode)
        report = json.loads(run.stdout)
        self.assertEqual('FAIL', report['status'])
        self.assertEqual('JSONDecodeError', self.find_check(report, 'design_inputs_readable_and_well_formed')['detail']['type'])
        self.assertEqual('', run.stderr)

    def test_cli_cannot_override_approved_commit(self):
        run = self.run_main('--approved-design-commit', self.baseline)
        self.assertNotEqual(0, run.returncode)
        self.assertIn('unrecognized arguments', run.stderr)


if __name__ == '__main__':
    unittest.main()
