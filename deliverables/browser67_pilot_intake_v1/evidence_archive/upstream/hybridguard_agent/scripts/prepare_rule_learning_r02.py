#!/usr/bin/env python3
"""Build the R02 fixed matrix into a fresh directory; no fitting or prediction."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.rule_learning.build_matrix import STUDY, build

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=STUDY / "R02_matrix")
    args = p.parse_args()
    result = build(args.output.resolve())
    print(json.dumps({k: result[k] for k in ("rows", "registered_candidates", "counts", "alias_conflicts", "real_fits", "risk_predictions")}, ensure_ascii=False))
