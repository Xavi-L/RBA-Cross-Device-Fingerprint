#!/usr/bin/env python3
"""Build the offline, label-free controlled attack-scenario sidecar."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybridguard_agent.scenarios.controlled_triplet import (  # noqa: E402
    DEFAULT_POLICY_PATH,
    build_controlled_scenario_sidecar,
    write_controlled_scenario_sidecar,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        help="Defaults to controlled_scenario_sidecar_v1.json in the snapshot directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot_dir = args.snapshot_dir.resolve()
    output = (args.output or snapshot_dir / "controlled_scenario_sidecar_v1.json").resolve()
    sidecar = build_controlled_scenario_sidecar(snapshot_dir, args.policy)
    write_controlled_scenario_sidecar(output, sidecar)
    audit = sidecar["input_audit"]
    print(
        "Controlled scenario sidecar written: "
        f"{output} ({audit['paired_group_count']} pair groups; {audit['scenario_status_counts']})"
    )


if __name__ == "__main__":
    main()
