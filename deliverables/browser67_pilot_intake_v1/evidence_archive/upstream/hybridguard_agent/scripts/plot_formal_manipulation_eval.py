#!/usr/bin/env python3
"""Export figure source tables from closed saved evaluation; no inference."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


if __name__ == "__main__":
    from hybridguard_agent.research.manipulation_eval.reporting import export_figure_data
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", required=True, type=Path)
    parser.add_argument("--figure-spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export_figure_data(evaluation_dir=args.evaluation, output=args.out, figure_spec_path=args.figure_spec), ensure_ascii=False))
