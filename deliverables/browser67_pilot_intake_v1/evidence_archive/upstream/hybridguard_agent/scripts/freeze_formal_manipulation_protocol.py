#!/usr/bin/env python3
"""Freeze S05 static protocol, explicitly naming BOTH new destinations."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hybridguard_agent.research.manipulation_eval.freeze import generate, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config-dir", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--parent-freeze", type=Path)
    parser.add_argument("--freeze-revision")
    args = parser.parse_args()
    if args.parent_freeze is not None or args.freeze_revision is not None:
        if args.parent_freeze is None or args.freeze_revision is None:
            parser.error("--parent-freeze and --freeze-revision must be supplied together")
        from hybridguard_agent.research.manipulation_eval.freeze_revision import revise, validate_revision
        result = (validate_revision(args.output, config_dir=args.config_dir, parent=args.parent_freeze) if args.validate_only else
                  revise(parent=args.parent_freeze, output=args.output, config_dir=args.config_dir, freeze_revision=args.freeze_revision))
    else:
        result = validate(args.output, config_dir=args.config_dir) if args.validate_only else generate(output=args.output, config_dir=args.config_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
