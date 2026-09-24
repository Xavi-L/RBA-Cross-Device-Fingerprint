#!/usr/bin/env python3
"""R02 focused acceptance. Default read-only; --write refuses saved files."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from hybridguard_agent.research.rule_learning.build_matrix import STUDY
from hybridguard_agent.research.rule_learning.validate_matrix import validate

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,default=STUDY / "R02_matrix")
    p.add_argument("--write",action="store_true")
    args=p.parse_args()
    result=validate(args.directory.resolve(),save=args.write)
    print(json.dumps({k:result[k] for k in ("status","checks_passed","synthetic_tests","real_fits","risk_predictions")}))
