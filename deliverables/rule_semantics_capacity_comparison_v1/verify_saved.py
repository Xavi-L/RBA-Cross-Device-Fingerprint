#!/usr/bin/env python3
"""Read-only audit of closed capacity results, without fit/predict imports."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DPR = "CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE"


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def literal_ids(model):
    assert all(len(c["literals"]) == 1 for c in model["clauses"])
    return {l["atom_id"] + ":" + l["polarity"] for c in model["clauses"] for l in c["literals"]}


def counts(rows):
    return {"attack_alerts": sum(r["phase"] == "attack" and r["decision"] == "MANIPULATION_ALERT" for r in rows),
            "attack_n": sum(r["phase"] == "attack" for r in rows),
            "clean_alerts": sum(r["phase"] != "attack" and r["decision"] == "MANIPULATION_ALERT" for r in rows),
            "clean_n": sum(r["phase"] != "attack" for r in rows),
            "defined": sum(r["decision"] in ("MANIPULATION_ALERT", "NO_ALERT") for r in rows),
            "expected": len(rows), "decisions": dict(Counter(r["decision"] for r in rows))}


def verify():
    contract, execution, result = (read(HERE / name) for name in ("CONTRACT.json", "EXECUTION.json", "RESULTS.json"))
    assert execution["execution_complete"] and execution["stop_reason"] is None
    assert execution["actual_fit_jobs"] == 6 and execution["actual_prediction_calls"] == 378
    assert execution["cumulative_fit_jobs"] == 201 and execution["additional_retries"] == 0
    assert execution["remaining_round_fits"] == 0
    baseline = ROOT / contract["baseline_directory"]
    review = read(HERE / "PRE_RUN_REVIEW.json")
    for name in review["registered_source_files"]:
        assert (ROOT / name).read_bytes() == (HERE / "source_snapshot" / name).read_bytes()
    old_review = read(baseline / "PRE_RUN_REVIEW.json")
    for name in old_review["registered_source_files"]:
        assert (ROOT / name).read_bytes() == (baseline / "source_snapshot" / name).read_bytes()
    folds, attempts, pred_attempts = [], 0, 0
    for job in contract["jobs"]:
        folder = HERE / "trials" / job["job_id"]
        model, training, receipt = (read(folder / name) for name in ("model.json", "training.json", "receipt.json"))
        assert model["status"] == receipt["outcome"] == "FITTED"
        assert receipt["actual_fit_invocations"] == 1 and receipt["attempt"] == 1 and receipt["error"] is None
        assert receipt["actual_prediction_calls"] == job["max_prediction_calls"]
        assert read(folder / "FIT_STARTED.json")["count"] == 1
        attempts += 1
        call_ids = [r["opaque_id"] for r in lines(folder / "PREDICTION_CALLS.jsonl")]
        assert call_ids == (job["outer_test_ids"] if job["stage"] == "RETENTION" else [])
        pred_attempts += len(call_ids)
        assert model["fit"]["train_ids"] == model["encoder"]["train_ids"] == training["train_ids"] == job["train_ids"]
        assert model["binding"]["fold_id"] == model["encoder"]["fold_id"] == job["fold_id"]
        assert model["fit"]["capacity_profile"] == model["view"]["capacity_profile"] == contract["capacity_profile"]
        assert model["binding"]["capacity_profile"] == contract["capacity_profile"]["profile_id"]
        assert all(op["ids"] == job["train_ids"] for op in training["access_operations"])
        events = read(folder / "access_log.json")
        names = [event["event"] for event in events]
        assert names.index("TRAIN_ONLY_INPUTS_OPENED") < names.index("MODEL_SAVED_RELOADED_FROZEN")
        assert names.index("MODEL_SAVED_RELOADED_FROZEN") < names.index("PREDICTIONS_CLOSED_BEFORE_LABEL_JOIN") < names.index("HELDOUT_METADATA_JOINED_AFTER_CLOSE")
        assert len(model["clauses"]) <= 7 and model["complexity"]["objective_complexity"] <= 14
        old_folder = baseline / "trials" / f"SELECTOR_V2__{job['fold_id']}__{job['stage']}"
        old_model, old_training = read(old_folder / "model.json"), read(old_folder / "training.json")
        assert model["encoder"] == old_model["encoder"]
        for key in ("train_ids", "encoded_atoms", "support", "semantic_catalog", "signal_groups", "source_mode_manifest"):
            assert training[key] == old_training[key], key
        assert [{k: v for k, v in row.items() if k not in ("selected", "selection_reasons")} for row in training["candidate_manifest"]] == [
            {k: v for k, v in row.items() if k not in ("selected", "selection_reasons")} for row in old_training["candidate_manifest"]]
        if job["stage"] == "SPARSE":
            assert training["trace"][:6] == old_training["trace"]
            assert model["fit"]["threshold_fit_calls"] == 1
            assert len(training["trace"]) == 7 and training["trace"][6]["operation"] == "ADD"
            assert set(training["trace"][6]["selected"]) - set(training["trace"][5]["selected"]) == {DPR}
        else:
            initial = read(HERE / "trials" / job["initializer"] / "model.json")
            assert model["clauses"] == initial["clauses"] and model["encoder"] == initial["encoder"]
            assert model["fit"]["training_result"] == initial["fit"]["training_result"]
            assert model["fit"]["threshold_fit_calls"] == 0 and training["trace"] == []
            assert model["fit"]["initialization"]["model_id"] == initial["model_id"]
            assert literal_ids(model) == literal_ids(old_model) | {DPR}
            assert {"RSR-LANG-FIRST-v1:POSITIVE", "RSR-WEBDRIVER-STATE-v1:POSITIVE"} <= literal_ids(model)
            folds.append({"fold_id": job["fold_id"], "heldout_environment": job["heldout_environment"],
                "train_members_encoder_atoms_support_and_semantic_catalog_match_CAP6": True,
                "first_six_sparse_steps_match_CAP6": True, "seventh_added_clause": DPR,
                "clauses": len(model["clauses"]), "complexity": model["complexity"]["objective_complexity"],
                "retention_additions": 0, "retention_swaps": 0,
                "own_fold_initialization_without_refit": True})
    assert (attempts, pred_attempts) == (6, 378)
    all_rows = {}
    for name, group in result["groups"].items():
        directory = Path(group["prediction_source"])
        group_contract = read(directory / "CONTRACT.json")
        rows = []
        for job in group_contract["jobs"]:
            if job["stage"] != "RETENTION" or job["group_id"] != ("BASE" if name == "BASE" else "LANG_ADD_WD_REPLACE"):
                continue
            folder = directory / "trials" / job["job_id"]
            predictions, evaluations = lines(folder / "predictions.jsonl"), read(folder / "evaluation_rows.json")
            assert [p["opaque_id"] for p in predictions] == [r["opaque_id"] for r in evaluations] == job["outer_test_ids"]
            for pred, row in zip(predictions, evaluations, strict=True):
                assert pred["decision"] == row["decision"]
                if name == "CAP7":
                    states = [c["state"] for c in pred["clause_explanations"]]
                    assert len(states) == 7 and all(s in ("T", "F") for s in states)
                    assert pred["decision"] == ("MANIPULATION_ALERT" if "T" in states else "NO_ALERT")
                    assert pred["source_observation_mode"] == "raw_observation_v1"
            rows.extend(evaluations)
            fold = next(f for f in group["folds"] if f["fold_id"] == job["fold_id"])
            assert all(fold[k] == v for k, v in counts(evaluations).items())
        assert Counter(r["opaque_id"] for r in rows) == Counter(contract["sample_ids"])
        assert all(group[k] == v for k, v in counts(rows).items())
        by_config = defaultdict(list)
        for row in rows:
            by_config[row["config_id"]].append(row)
        for config, current in by_config.items():
            actual, saved = counts(current), group["configurations"][config]
            assert (actual["attack_alerts"], actual["attack_n"], actual["clean_alerts"], actual["clean_n"]) == (
                saved["alerts"], saved["n"], saved["clean_alerts"], saved["clean_n"])
        all_rows[name] = {r["opaque_id"]: r for r in rows}
    comparisons = {}
    for name in ("CAP6", "BASE", "PRIOR_COMBINATION"):
        changes = []
        for i in contract["sample_ids"]:
            before, after = all_rows[name][i], all_rows["CAP7"][i]
            assert {k: v for k, v in before.items() if k != "decision"} == {k: v for k, v in after.items() if k != "decision"}
            if before["decision"] != after["decision"]:
                changes.append({"opaque_id": i, "phase": before["phase"], "config_id": before["config_id"],
                    "environment_group_id": before["environment_group_id"], "reference_decision": before["decision"], "new_decision": after["decision"]})
        assert changes == result["changed_decisions"][name]
        regressions = [i for i, old in all_rows[name].items() if old["phase"] == "attack" and old["decision"] == "MANIPULATION_ALERT"
                       and all_rows["CAP7"][i]["decision"] != "MANIPULATION_ALERT"]
        new_clean = [i for i, old in all_rows[name].items() if old["phase"] != "attack" and old["decision"] != "MANIPULATION_ALERT"
                     and all_rows["CAP7"][i]["decision"] == "MANIPULATION_ALERT"]
        lost_defined = [i for i, old in all_rows[name].items() if old["decision"] in ("MANIPULATION_ALERT", "NO_ALERT")
                        and all_rows["CAP7"][i]["decision"] not in ("MANIPULATION_ALERT", "NO_ALERT")]
        assert not regressions
        assert not new_clean and not lost_defined
        assert all(r["phase"] == "attack" and r["reference_decision"] == "NO_ALERT" and r["new_decision"] == "MANIPULATION_ALERT" for r in changes)
        comparisons[name] = {"changed_decisions": len(changes), "gains_by_config": dict(Counter(r["config_id"] for r in changes)),
                             "attack_regressions": regressions, "new_clean_alerts": len(new_clean), "coverage_loss": len(lost_defined)}
    return {"status": "PASS", "review_method": "Saved-artifact cross-check; no fresh model evaluation or optimizer calls.",
        "new_fit_calls": 0, "new_prediction_calls": 0, "source_snapshots_match": True,
        "registered_source_files_checked": len(review["registered_source_files"]),
        "fits_and_predictions_accounted": {"fits": attempts, "predictions": pred_attempts},
        "folds": folds, "comparisons": comparisons, "findings": []}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write:
        with (HERE / "RESULT_REVIEW.json").open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
