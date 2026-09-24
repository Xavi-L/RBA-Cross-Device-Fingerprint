#!/usr/bin/env python3
"""Separate prediction-only and saved-output evaluation entry points."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    predict = sub.add_parser("predict", help="Blind job; accepts no evaluation index or facts")
    for name in ("inputs", "protocol", "config-dir", "policy", "out"):
        predict.add_argument("--" + name, type=Path, required=True)
    predict.add_argument("--contract-version", required=True)
    evaluate = sub.add_parser("evaluate", help="Join only after prediction files close; never run a detector")
    for name in ("predictions", "evaluation-index", "triplets", "out"):
        evaluate.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "predict":
        from hybridguard_agent.research.manipulation_eval.runtime_resources import preflight
        # A job is control-plane metadata. Check resources before importing the
        # execution chain, loading a contract or opening any sample/output file.
        job_header = json.loads(args.protocol.read_text())
        preflight(require_manifest=job_header.get("execution_scope") == "FROZEN_FORMAL_EVALUATION",
                  config_dir=args.config_dir, policy_path=args.policy)
        from hybridguard_agent.research.manipulation_eval.contract import load_contract, read_json
        from hybridguard_agent.research.manipulation_eval.runner import run_predictions
        contract = load_contract(contract_version=args.contract_version, config_dir=args.config_dir, policy_path=args.policy)
        result = run_predictions(input_path=args.inputs, protocol=read_json(args.protocol), contract=contract, output=args.out)
        print(json.dumps({k: result[k] for k in ("status", "prediction_count", "failure_count", "real_sample_predictions")}, ensure_ascii=False))
    else:
        from hybridguard_agent.research.manipulation_eval.evaluation import evaluate_saved
        result = evaluate_saved(prediction_dir=args.predictions, index_path=args.evaluation_index, triplets_path=args.triplets, output=args.out)
        print(json.dumps({"variants": len(result["variants"]), "execution_scope": result["execution_scope"], "detector_calls": 0}))


if __name__ == "__main__":
    main()
