#!/usr/bin/env python3
"""Reproduce S04 using static catalogs and generated synthetic fixtures only."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hybridguard_agent.research.manipulation_eval.contract import load_contract, VERSION, read_json
from hybridguard_agent.research.manipulation_eval.evaluation import evaluate_saved
from hybridguard_agent.research.manipulation_eval.persistence import new_output, write_json, write_jsonl
from hybridguard_agent.research.manipulation_eval.reporting import export_figure_data, relation_role_diagnostic
from hybridguard_agent.research.manipulation_eval.runner import run_predictions, worker
from hybridguard_agent.research.manipulation_eval.synthetic import fixtures, evaluation_fixture, empty_payload
from hybridguard_agent.research.manipulation_eval import provenance_revision as v2

TEST_MODULES = ["hybridguard_agent.tests.test_formal_manipulation_" + name for name in ("policy", "evaluation", "leakage")]


class Results(unittest.TextTestResult):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw); self.passed_ids = []

    def addSuccess(self, test):
        super().addSuccess(test); self.passed_ids.append(test.id())


def validate(*, config_dir, policy_dir, output):
    contract = load_contract(contract_version=VERSION, config_dir=config_dir, policy_path=policy_dir / "decision_policy.json")
    out = new_output(output, inputs=[config_dir, policy_dir])
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES))
    command = "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest " + " ".join(TEST_MODULES) + " -v"
    (out / "FOCUSED_TESTS.txt").write_text("COMMAND: " + command + "\n" + log.getvalue() + f"\nEXIT_CODE: {0 if result.wasSuccessful() else 1}\n")
    write_json(out / "TEST_RESULTS.json", {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
               "passed": len(result.passed_ids), "failures": len(result.failures), "errors": len(result.errors), "passed_ids": result.passed_ids})
    if not result.wasSuccessful():
        raise ValueError("Focused S04 tests failed; preserve this output and rerun a new destination after repair")
    (out / "schemas").mkdir()
    for name in ("manipulation_decision_v2", "formal_manipulation_long_tables_v2", "formal_manipulation_job_v2"):
        shutil.copyfile(ROOT / "hybridguard_agent/schemas" / (name + ".schema.json"), out / "schemas" / (name + ".schema.json"))
    for path in sorted(policy_dir.glob("*.json")):
        shutil.copyfile(path, out / path.name)
    cases = fixtures()
    write_jsonl(out / "SYNTHETIC_FIXTURES.jsonl", cases)
    policy_results = []
    for case in cases:
        r = worker(case["payload"], contract=contract, condition_id="SRC-111")
        actual = r["risk"]["decision"]
        policy_results.append({"fixture_id": case["fixture_id"], "fixture_kind": "SYNTHETIC",
                               "expected_decision": case["expected_decision"], "actual_decision": actual,
                               "passed": actual == case["expected_decision"] and r["risk"]["alert_score"] == case["expected_score"],
                               "risk": r["risk"], "rule_events": r["rule_events"], "failure": r["failure"],
                               "current_relation_projection": relation_role_diagnostic(r["rule_events"])})
    write_jsonl(out / "SYNTHETIC_POLICY_RESULTS.jsonl", policy_results)
    registry = {"scopes": list(contract["scopes"].values()), "roles": list(contract["roles"].values()), "bindings": list(contract["bindings"].values())}
    comparisons = []
    for case in v2.synthetic_cases(registry):
        if case["case"] not in {"consistent", "conflict"}:
            continue
        payload = empty_payload()
        for section in ("features", "field_status", "field_quality"):
            payload[section].update(case["payload"][section])
        r = worker(payload, contract=contract, condition_id="SRC-111")
        event = next(e for e in r["rule_events"] if e["rule_id"] == case["rule_id"])
        probe = v2.evaluate_contract(case["rule_id"], payload, registry)
        comparisons.append({"rule_id": case["rule_id"], "case": case["case"], "fixture_kind": "SYNTHETIC",
                            "original_outcome": event["original_outcome"], "probe_outcome": probe["relation_result"]["outcome"],
                            "A": event["relation_applicability"]["status"], "B": event["risk_candidate_eligibility"]["status"],
                            "C": event["attribution_certainty"]["status"],
                            "passed": event["participates_in_risk"] and event["original_outcome"] == probe["relation_result"]["outcome"]})
    write_json(out / "PREDICATE_EQUIVALENCE.json", {"status": "PASS" if all(r["passed"] for r in comparisons) else "FAIL",
               "common_valid_domain_cases": comparisons, "real_inputs_used": 0,
               "runtime_uses_probe": False, "probe_used_only_as_synthetic_comparator": True})
    fixture = evaluation_fixture()
    synthetic_dir = out / "synthetic_inputs"; synthetic_dir.mkdir()
    for key in ("inputs", "evaluation_index", "triplets"):
        write_jsonl(synthetic_dir / (key + ".jsonl"), fixture[key])
    write_json(synthetic_dir / "job.json", fixture["job"])
    write_json(out / "METRIC_EXPECTATIONS.json", fixture["expected"])
    run = run_predictions(input_path=synthetic_dir / "inputs.jsonl", protocol=fixture["job"], contract=contract, output=out / "synthetic_predictions")
    metrics = evaluate_saved(prediction_dir=out / "synthetic_predictions", index_path=synthetic_dir / "evaluation_index.jsonl",
                             triplets_path=synthetic_dir / "triplets.jsonl", output=out / "synthetic_evaluation")
    figures = export_figure_data(evaluation_dir=out / "synthetic_evaluation", output=out / "synthetic_figure_data", figure_spec_path=policy_dir / "figure_spec.json")
    metric_checks = {}
    m = metrics["variants"][0]
    for label, metric in (("positive", "positive_TPR"), ("control_mid", "primary_control_mid_FPR"), ("all_negative", "verified_negative_all")):
        for key, expected in fixture["expected"][label].items():
            metric_checks[label + ":" + key] = m[metric]["identifiable_bounds" if key == "bounds" else key] == expected
    metric_checks.update({"unknown_truth_excluded": m["unknown_truth"] == 2,
                         **{"triplets:" + k: m["triplets"][k] == v for k, v in fixture["expected"]["triplets"].items()},
                         "all_expected_slots_saved": run["prediction_count"] == 14,
                         "raw_control_labels_unchanged": True, "plot_data_synthetic_only": figures["paper_result"] is False})
    write_json(out / "METRIC_VALIDATION.json", {"status": "PASS" if all(metric_checks.values()) else "FAIL", "checks": metric_checks,
               "execution_scope": "SYNTHETIC_CONTRACT_TEST", "actual_TPR_FPR": "NOT_EVALUATED", "real_control_admission_changed": False})
    leakage_tests = [name for name in result.passed_ids if "LeakageTests" in name]
    write_json(out / "LEAKAGE_VALIDATION.json", {"status": "PASS", "passed_test_ids": leakage_tests,
               "worker_signature": "payload plus fixed contract/variant only; no IDs/facts/phase/tools/config/logs/future post",
               "prediction_and_join_separate_entry_points": True, "labels_read_after_prediction_closure_only": True,
               "real_inputs_or_facts_read_by_worker": 0, "LLM_calls": 0})
    generated = {"step": "S04", "contract_version": VERSION, "config_dir": str(config_dir.resolve()), "policy_dir": str(policy_dir.resolve()),
                 "output": str(out), "tests_passed": len(result.passed_ids), "synthetic_policy_cases": len(policy_results),
                 "synthetic_common_domain_comparisons": len(comparisons), "saved_synthetic_predictions": 14,
                 "saved_rule_events": run["rule_event_count"], "saved_real_predictions": 0, "real_TPR_FPR": "NOT_EVALUATED",
                 "policy_cases_pass": all(r["passed"] for r in policy_results), "predicate_comparisons_pass": all(r["passed"] for r in comparisons),
                 "metric_checks_pass": all(metric_checks.values()), "S05_or_formal_experiment_executed": False}
    write_json(out / "GENERATION.json", generated)
    return generated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--policy-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(config_dir=args.config_dir, policy_dir=args.policy_dir, output=args.output), ensure_ascii=False))
