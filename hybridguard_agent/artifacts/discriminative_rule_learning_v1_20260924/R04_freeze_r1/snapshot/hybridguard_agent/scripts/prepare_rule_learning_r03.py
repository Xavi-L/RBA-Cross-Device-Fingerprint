#!/usr/bin/env python3
"""Create R03 synthetic artifacts in a NEW directory; never train real records."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.rule_learning.acceptance import build
from hybridguard_agent.research.rule_learning.contracts import STUDY

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=STUDY / "R03_implementation")
    args = p.parse_args()
    print(json.dumps(build(args.output.resolve()), ensure_ascii=False))
