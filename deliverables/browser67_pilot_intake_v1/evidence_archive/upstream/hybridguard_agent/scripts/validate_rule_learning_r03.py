#!/usr/bin/env python3
"""Read-only R03 artifact and synthetic acceptance; no --write or real data flag."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.rule_learning.acceptance import validate
from hybridguard_agent.research.rule_learning.contracts import STUDY

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, default=STUDY / "R03_implementation")
    args = p.parse_args()
    print(json.dumps(validate(args.directory.resolve()), ensure_ascii=False))
