"""Formal study preparation: S01 admission or S02 adaptation, without detection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    admission = commands.add_parser("admission", help="read-only material validators and independent fact ledger")
    admission.add_argument("--attack-root", type=Path, default=REPO / "hybridguard-browser-fingerprint-research")
    admission.add_argument("--design-audit", type=Path, default=REPO / "HybridGuard_Experiment_Design/attack_bundle_audit.json")
    admission.add_argument("--output", type=Path, default=REPO / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923/01_admission")
    admission.add_argument("--reuse-validators", action="store_true", help="reuse an interrupted replay only if the recorded source files are unchanged")
    adapt = commands.add_parser("adapt", help="S02 App177 projection from the saved S01 ledger; no detector")
    adapt.add_argument("--admission-dir", type=Path, default=REPO / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923/01_admission")
    adapt.add_argument("--attack-root", type=Path, default=REPO / "hybridguard-browser-fingerprint-research")
    adapt.add_argument("--output", type=Path, default=REPO / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923/02_inputs")
    adapt.add_argument("--test-log", type=Path, required=True, help="saved successful S02 synthetic unittest output including exit code")
    args = parser.parse_args()
    if args.command == "admission":
        from hybridguard_agent.research.manipulation_eval.admission import prepare
        result = prepare(args.attack_root, args.design_audit, args.output, args.reuse_validators)
    else:
        from hybridguard_agent.research.manipulation_eval.adapter import prepare_adaptation
        result = prepare_adaptation(args.admission_dir, args.attack_root, args.output, args.test_log)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
