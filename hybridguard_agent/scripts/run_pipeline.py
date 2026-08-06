#!/usr/bin/env python3
"""Run the repeatable P0 snapshot and bounded deterministic runtime preparation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = AGENT_ROOT / "artifacts"
SCRIPT_DIR = AGENT_ROOT / "scripts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bootstrap-contract", action="store_true")
    return parser.parse_args()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    snapshot_dir = ARTIFACT_ROOT / args.run_id
    command = [sys.executable, str(SCRIPT_DIR / "build_dataset_snapshot.py"), "--run-id", args.run_id]
    if args.bootstrap_contract:
        command.append("--bootstrap-contract")
    run(command)
    # Keep the historical v1 artifact for prior P0 consumers while emitting the
    # status-aware, redacted v2 bundle used by the new runtime.
    run([sys.executable, str(SCRIPT_DIR / "build_evidence_bundles.py"), "--snapshot-dir", str(snapshot_dir)])
    run([sys.executable, str(SCRIPT_DIR / "build_evidence_bundles_v2.py"), "--snapshot-dir", str(snapshot_dir)])
    run([sys.executable, str(SCRIPT_DIR / "build_knowledge_manifest.py"), "--snapshot-dir", str(snapshot_dir)])
    run([sys.executable, str(SCRIPT_DIR / "build_attack_scenario_sidecar.py"), "--snapshot-dir", str(snapshot_dir)])
    print(f"P0 snapshot and deterministic-runtime inputs completed: {snapshot_dir}")


if __name__ == "__main__":
    main()
