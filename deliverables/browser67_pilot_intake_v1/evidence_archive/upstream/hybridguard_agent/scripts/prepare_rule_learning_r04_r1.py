"""Create a separate R04-R1 snapshot; independently verify synthetic work only."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hybridguard_agent.research.rule_learning.contracts import STUDY
from hybridguard_agent.research.rule_learning.freeze_revision import build_revision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=STUDY / 'R04_freeze')
    parser.add_argument('--out', type=Path, default=STUDY / 'R04_freeze_r1')
    args = parser.parse_args()
    build_revision(args.source, args.out)
    independent = Path(tempfile.mkdtemp(prefix='hybridguard-r04-r1-isolated-'))
    snapshot = independent / 'freeze'
    shutil.copytree(args.out, snapshot)
    cwd = independent / 'empty_cwd'
    cwd.mkdir()
    cmd = [str(snapshot / 'dependencies/python/bin/python3.12'), '-B', '-I', '-S', str(snapshot / 'launch.py'),
           'acceptance', str(snapshot), str(args.out.resolve() / 'isolated_validation')]
    completed = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=120)
    (args.out / 'ISOLATED_STDOUT.txt').write_text(completed.stdout)
    (args.out / 'ISOLATED_STDERR.txt').write_text(completed.stderr)
    (args.out / 'ISOLATED_PROCESS.json').write_text(json.dumps({'argv': cmd, 'cwd': str(cwd),
        'returncode': completed.returncode, 'snapshot_copy': str(snapshot), 'real_fit_authorizations': 0}, indent=2) + '\n')
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    print(json.dumps({'status': 'PASS_R04_R1_SYNTHETIC_ONLY', 'output': str(args.out), 'real_fits': 0, 'real_predictions': 0}))


if __name__ == '__main__':
    main()
