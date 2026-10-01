#!/usr/bin/env python3
"""Inspect saved models/decisions only; never import the training engine."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def main():
    contract = read(HERE / "CONTRACT.json")
    execution = read(HERE / "EXECUTION.json")
    results = read(HERE / "RESULTS.json")
    assert execution["execution_complete"]
    assert (execution["actual_fit_jobs"], execution["actual_prediction_calls"]) == (6, 378)
    assert (execution["cumulative_fit_jobs"], execution["remaining_research_fits"]) == (195, 5)
    assert execution["additional_retries"] == 0
    trials, folds = [], []
    for job in contract["jobs"]:
        folder = HERE / "trials" / job["job_id"]
        model, training = read(folder / "model.json"), read(folder / "training.json")
        assert model["fit"]["train_ids"] == training["train_ids"] == job["train_ids"]
        assert model["status"] == "FITTED" and len(model["clauses"]) <= 6
        assert model["fit"]["training_result"]["complexity"] <= 12
        selected = [literal for clause in model["clauses"] for literal in clause["literals"]]
        atoms = {literal["atom_id"] for literal in selected}
        operations = dict(Counter(step["operation"] for step in training["trace"]))
        item = {"job_id": job["job_id"], "stage": job["stage"], "fold_id": job["fold_id"],
                "selected_literals": selected, "clauses": len(model["clauses"]),
                "complexity": model["fit"]["training_result"]["complexity"],
                "selected_new_conditions": {name: name in atoms for name in
                    ("RSR-LANG-FIRST-v1", "RSR-WEBDRIVER-STATE-v1")},
                "accepted_operations": operations, "stop": model["fit"]["stop"],
                "threshold_fit_calls": model["fit"]["threshold_fit_calls"]}
        trials.append(item)
        if job["stage"] == "RETENTION":
            initial = read(HERE / "trials" / job["initializer"] / "model.json")
            assert model["encoder"] == initial["encoder"]
            item["unchanged_from_sparse"] = model["clauses"] == initial["clauses"]
            item["D_initial"] = model["fit"]["D_initial"]
            item["D_final"] = model["fit"]["D_final"]
            rows = read(folder / "evaluation_rows.json")
            assert [r["opaque_id"] for r in rows] == job["outer_test_ids"]
            folds.append({"fold_id": job["fold_id"], "heldout_environment": job["heldout_environment"],
                          "attacks": sum(r["phase"] == "attack" for r in rows),
                          "attack_alerts": sum(r["phase"] == "attack" and r["decision"] == "MANIPULATION_ALERT" for r in rows),
                          "decision_counts": dict(Counter(r["decision"] for r in rows))})
    current = results["groups"]["NEW_SCHEME"]
    comparisons = {}
    for label in ("BASE", "PRIOR_COMBINATION"):
        before = results["groups"][label]
        regressions, gains = [], []
        for config, old in before["configurations"].items():
            new = current["configurations"][config]
            assert (old["n"], old["clean_n"]) == (new["n"], new["clean_n"])
            delta = new["alerts"] - old["alerts"]
            if delta:
                (gains if delta > 0 else regressions).append({"config_id": config,
                    "old_alerts": old["alerts"], "new_alerts": new["alerts"], "n": new["n"]})
        clean_worse = any(current["configurations"][c]["clean_alerts"] > v["clean_alerts"]
                          for c, v in before["configurations"].items())
        nonregression = (current["attack_alerts"] >= before["attack_alerts"] and not regressions
                         and not clean_worse and current["defined"] >= before["defined"])
        comparisons[label] = {"attack_alert_delta": current["attack_alerts"] - before["attack_alerts"],
            "changed_decision_count": len(results["changed_decisions"][label]),
            "configuration_gains": gains, "configuration_regressions": regressions,
            "observed_nonregression_against_this_reference": nonregression}
    print(json.dumps({"read_only_saved_artifact_check": "PASS", "new_fit_calls": 0,
        "new_prediction_calls": 0, "trials": trials, "folds": folds,
        "comparisons": comparisons,
        "actual_retention_swaps": sum(t["accepted_operations"].get("SWAP_SEMANTIC_QUALITY", 0) for t in trials),
        "interpretation": "Both new conditions entered during sparse selection. Retention performed no accepted operation. This run does not demonstrate added performance from the swap mechanism."},
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
