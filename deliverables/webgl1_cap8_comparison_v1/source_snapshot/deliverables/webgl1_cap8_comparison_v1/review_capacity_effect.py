#!/usr/bin/env python3
"""Compare closed CAP7/CAP8 artifacts; never fit models or invoke predictors."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json

from run_comparison import closed_rows, metrics, read, require, write

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "webgl1_fresh_comparison_v1"
GROUPS = ("BASE49", "WEBGL50")


def compare_rows(before, after):
    a = {r["opaque_id"]: r for r in before}
    b = {r["opaque_id"]: r for r in after}
    require(len(a) == len(b) == 378 and set(a) == set(b), "MATCHED_COHORT_REQUIRED")
    result = {k: [] for k in ("changes", "new_attack_alerts", "lost_attack_alerts",
                              "new_clean_alerts", "removed_clean_alerts", "newly_undefined")}
    for oid in sorted(a):
        x, y = a[oid], b[oid]
        require({k: v for k, v in x.items() if k != "decision"}
                == {k: v for k, v in y.items() if k != "decision"}, "SAVED_LABEL_METADATA_DIFFERS")
        if x["decision"] == y["decision"]:
            continue
        row = {**x, "before_decision": x["decision"], "after_decision": y["decision"]}
        del row["decision"]
        result["changes"].append(row)
        previous, current = x["decision"] == "MANIPULATION_ALERT", y["decision"] == "MANIPULATION_ALERT"
        if previous != current:
            kind = "attack" if x["phase"] == "attack" else "clean"
            key = ("new_" if current else "lost_" if kind == "attack" else "removed_") + kind + "_alerts"
            result[key].append(row)
        if x["decision"] in ("MANIPULATION_ALERT", "NO_ALERT") and y["decision"] not in ("MANIPULATION_ALERT", "NO_ALERT"):
            result["newly_undefined"].append(row)
    return result


def review():
    directories = {"CAP7": SOURCE, "CAP8": HERE}
    contracts = {c: read(d / "CONTRACT.json") for c, d in directories.items()}
    for capacity, directory in directories.items():
        require(read(directory / "EXECUTION.json")["execution_complete"] is True,
                "ALL_JOBS_MUST_CLOSE_BEFORE_CAPACITY_REVIEW:" + capacity)
    same_contract_basis = {k: contracts["CAP7"][k] == contracts["CAP8"][k]
                           for k in ("source_directory", "sample_ids", "folds", "source_modes", "selector_policy")}
    require(all(same_contract_basis.values()), "CROSS_CAPACITY_INPUT_CONTRACT_CHANGED")
    jobs, rows, summaries = {}, {}, {}
    for capacity, directory in directories.items():
        jobs[capacity] = {(j["group_id"], j["fold_id"], j["stage"]): j for j in contracts[capacity]["jobs"]}
        saved = read(directory / "RESULTS.json")
        rows[capacity], summaries[capacity] = {}, {}
        for group in GROUPS:
            collected = []
            for fold in contracts[capacity]["folds"]:
                current, _ = closed_rows(directory, jobs[capacity][group, fold["fold_id"], "RETENTION"])
                collected.extend(current)
            require(Counter(r["opaque_id"] for r in collected) == Counter(contracts[capacity]["sample_ids"]),
                    "EXACT_SAVED_PREDICTION_MEMBERS_REQUIRED")
            aggregate = metrics(collected)
            require(all(saved["groups"][group][k] == v for k, v in aggregate.items()), "SAVED_METRIC_MISMATCH")
            rows[capacity][group], summaries[capacity][group] = collected, aggregate

    audits = []
    rule_changes = []
    for group in GROUPS:
        for fold in contracts["CAP8"]["folds"]:
            fid = fold["fold_id"]
            for stage in ("SPARSE", "RETENTION"):
                data = {}
                for capacity, directory in directories.items():
                    job = jobs[capacity][group, fid, stage]
                    trial = directory / "trials" / job["job_id"]
                    data[capacity] = (read(trial / "training.json"), read(trial / "model.json"))
                (t7, m7), (t8, m8) = data["CAP7"], data["CAP8"]
                checks = {"encoder_equal": m7["encoder"] == m8["encoder"],
                          "encoded_atoms_equal": t7["encoded_atoms"] == t8["encoded_atoms"],
                          "semantic_catalog_equal": t7["semantic_catalog"] == t8["semantic_catalog"],
                          "support_equal": t7["support"] == t8["support"],
                          "train_ids_equal": t7["train_ids"] == t8["train_ids"],
                          "signal_groups_equal": t7["signal_groups"] == t8["signal_groups"]}
                audits.append({"group": group, "fold_id": fid, "stage": stage, "checks": checks,
                               "status": "PASS" if all(checks.values()) else "FAIL"})
                if stage == "RETENTION":
                    literals = lambda model: {(a["atom_id"], a["polarity"]) for c in model["clauses"] for a in c["literals"]}
                    a, b = literals(m7), literals(m8)
                    rule_changes.append({"group": group, "fold_id": fid,
                                         "cap7_clause_count": len(m7["clauses"]), "cap8_clause_count": len(m8["clauses"]),
                                         "cap7_complexity": m7["complexity"], "cap8_complexity": m8["complexity"],
                                         "added_literals": sorted(b - a), "removed_literals": sorted(a - b),
                                         "cap8_stop": m8["fit"]["stop"]})

    differences = {g: compare_rows(rows["CAP7"][g], rows["CAP8"][g]) for g in GROUPS}
    within = compare_rows(rows["CAP8"]["BASE49"], rows["CAP8"]["WEBGL50"])
    a, b = summaries["CAP8"]["BASE49"], summaries["CAP8"]["WEBGL50"]
    regression = [k for k in a["configurations"] if b["configurations"][k]["alerts"] < a["configurations"][k]["alerts"]]
    basis_pass = all(record["status"] == "PASS" for record in audits)
    within_basis_pass = read(HERE / "RESULTS.json")["shared_training_basis_audit"]["status"] == "PASS"
    improvement = basis_pass and within_basis_pass and b["attack_alerts"] > a["attack_alerts"] and not regression \
        and not within["new_clean_alerts"] and not within["newly_undefined"] and b["defined"] >= a["defined"]
    result = {"experiment_id": "webgl1-cap8-comparison-v1", "reviewed_at": datetime.now(timezone.utc).isoformat(),
              "status": "PASS" if basis_pass and within_basis_pass else "FAIRNESS_REVIEW_FAILED",
              "scope": "Saved prediction/model comparison on exposed reused development data; not independent confirmation",
              "same_contract_basis": same_contract_basis, "cross_capacity_basis_audits": audits,
              "within_cap8_basis_pass": within_basis_pass, "metrics": summaries,
              "capacity_effect_by_pool": differences, "cap8_candidate_effect": within,
              "cap8_candidate_attack_delta": b["attack_alerts"] - a["attack_alerts"],
              "cap8_candidate_attack_delta_percentage_points": 100 * (b["tpr"] - a["tpr"]),
              "cap8_configuration_regressions": regression, "registered_internal_improvement_condition_met": improvement,
              "rule_changes": rule_changes, "fit_calls_during_review": 0, "prediction_calls_during_review": 0,
              "cap7_predictions_reused_for_reporting_only": True, "cap8_predictions_newly_computed": True}
    write(HERE / "CAPACITY_EFFECT.json", result)
    return result


if __name__ == "__main__":
    result = review()
    print(json.dumps({k: result[k] for k in ("status", "cap8_candidate_attack_delta",
                     "cap8_candidate_attack_delta_percentage_points", "registered_internal_improvement_condition_met")}, indent=2))
