#!/usr/bin/env python3
"""Guarded complete replay: measured call counts and output-only writes."""
import argparse
from collections import Counter
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run


def reproduce(output):
    output = output.resolve()
    counts = Counter()
    writes = set()
    violations = []

    def inside(path):
        return Path(os.fsdecode(path)).resolve().is_relative_to(output)

    def deny(reason):
        violations.append(reason)
        raise RuntimeError(reason)

    def profile(frame, event, arg):
        if event != 'call': return
        name = frame.f_code.co_name
        prohibited = name == 'fit' or name.startswith('fit_') or name in ('prepare_fold', 'train', 'collect')
        if not prohibited and name not in ('predict_current', 'evaluate'): return
        filename = frame.f_code.co_filename
        if not filename.startswith(str(run.ROOT) + os.sep): return
        if prohibited: deny('FORBIDDEN_TRAINING_OR_COLLECTION:' + name)
        if filename.endswith('/mtc_timezone_selection.py') and name == 'predict_current': counts['app_prediction_calls'] += 1
        if filename == str(run.HERE / 'conditions.py') and name == 'evaluate': counts['condition_calls'] += 1

    def audit(event, args):
        if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect', 'socket.bind'):
            deny('FORBIDDEN_PROCESS_OR_NETWORK:' + event)
        if event == 'open':
            path, mode, flags = args
            writing = bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and not isinstance(path, int):
                if not inside(path): deny('WRITE_OUTSIDE_REPLAY_OUTPUT:' + os.fsdecode(path))
                writes.add(str(Path(os.fsdecode(path)).resolve().relative_to(output)))
        if event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.rename'):
            paths = args[:2] if event == 'os.rename' else args[:1]
            for path in paths:
                if not inside(path): deny('MUTATION_OUTSIDE_REPLAY_OUTPUT:' + os.fsdecode(path))

    # Separate CLI process: this permanent Python audit hook ends with the process.
    sys.addaudithook(audit)
    sys.setprofile(profile)
    try:
        run.run(output)
    finally:
        sys.setprofile(None)
    assert counts == Counter(app_prediction_calls=54, condition_calls=4545), counts
    run.write(output / 'RUNTIME_AUDIT.json', {'status': 'PASSED', 'actual_calls': dict(counts),
              'prohibited_training_collection_process_network_calls': violations,
              'write_scope': 'only requested fresh output directory', 'written_files': sorted(writes),
              'candidate_scope': run.MODE})
    print('Guarded replay passed: 54 App predictions, 4545 condition calls, no forbidden operation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reproduce(args.output)
