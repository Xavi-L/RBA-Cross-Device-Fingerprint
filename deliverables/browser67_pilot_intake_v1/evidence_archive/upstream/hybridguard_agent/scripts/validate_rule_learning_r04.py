"""Read-only validation: run a relocated copy, write only a new temp directory."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, default=STUDY / 'R04_freeze')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='r04-read-only-') as directory:
        directory = Path(directory)
        snapshot = directory / 'freeze'
        shutil.copytree(args.freeze, snapshot, ignore=lambda path, names: [n for n in names if n == 'isolated_validation'])
        cwd = directory / 'empty_cwd'
        cwd.mkdir()
        result = subprocess.run([str(snapshot / 'dependencies/python/bin/python3.12'), '-B', '-I', '-S', str(snapshot / 'launch.py'),
            'acceptance', str(snapshot), str(directory / 'validation')], cwd=cwd, text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr)
        saved = json.loads((directory / 'validation/SYNTHETIC_CHAIN_VALIDATION.json').read_text())
        print(json.dumps({'status': 'PASS_READ_ONLY_R04', 'synthetic_tests': saved['tests_run'],
                          'real_fits': 0, 'real_risk_predictions': 0}))


if __name__ == '__main__':
    main()
