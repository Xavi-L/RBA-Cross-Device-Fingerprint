"""Metadata-only job planning. Never reads feature values or ranks candidates."""
import copy
import hashlib
import json

from .contracts import STUDY, binding, contract, read_json, read_jsonl

LEARNERS = ("GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2")
FIXED = ("HISTORICAL_SEVEN", "DIRECT_CORE_OR", "ALWAYS_NO_ALERT", "ALWAYS_ABSTAIN")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def unit_id(*parts):
    return "__".join(parts)


def job(experiment, fold, method, point="OP05", source="SRC-111", view="core", *, origin="R02_FIXED_CACHE"):
    uid = unit_id(experiment, fold["fold_id"], method, point, source, view)
    search = contract("learning_search_space")
    primary = point in ("OP05", "NOT_APPLICABLE")
    priority = search["total_budget"]["priority"].index(experiment if primary and experiment in search["total_budget"]["priority"] else "SENSITIVITY")
    if experiment == "FINAL_DEVELOPMENT_REFIT":
        priority = len(search["total_budget"]["priority"])
    return {"job_id": uid, "model_unit_id": uid, "fit_job_id": uid if method in LEARNERS else None,
            "experiment_id": experiment, "authorization_stage": experiment.split("_")[0],
            "protocol_digest": binding()["protocol_digest"], "split_id": fold["split_id"],
            "fold_id": fold["fold_id"], "method_id": method, "operating_point": point,
            "source_condition": source, "input_view": view, "data_origin": origin,
            "train_ids": list(fold["train"]), "outer_test_ids": list(fold["outer_test"]),
            "train_membership_digest": digest(fold["train"]), "test_membership_digest": digest(fold["outer_test"]),
            "evaluation_track": fold["split_id"], "priority": priority,
            "fit_time_limit_seconds": search["algorithms"][method]["time_limit_seconds_per_fit"] if method in LEARNERS else 0,
            "state": "NOT_RUN_NOT_AUTHORIZED", "reuse_model_unit_id": None}


def prediction_units(models):
    return [{**{k: j[k] for k in ("model_unit_id", "experiment_id", "protocol_digest", "split_id", "fold_id",
              "method_id", "operating_point", "source_condition", "input_view", "evaluation_track", "data_origin")},
             "prediction_unit_id": j["model_unit_id"] + "__" + oid, "opaque_id": oid,
             "state": "NOT_RUN_NOT_AUTHORIZED"}
            for j in models for oid in j["outer_test_ids"]]


def plan_real_jobs():
    folds = read_json(STUDY / "R02_matrix/FOLD_INPUT_MANIFEST.json")["folds"]
    loeo = [f for f in folds if f["split_id"] == "LOEO-v1"]
    loco = [f for f in folds if f["split_id"] == "LOCO-v1"]
    result = []
    for f in loeo:
        for m in LEARNERS:
            for p in ("OP05", "OP00", "OP10"):
                result.append(job("R05_PRIMARY", f, m, p))
        result.extend(job("R05_PRIMARY", f, m, "NOT_APPLICABLE") for m in FIXED)
        for bits in range(8):
            j = job("R06_SOURCE_REFIT", f, "GREEDY_OR", source=f"SRC-{bits:03b}")
            if bits == 7:
                j["reuse_model_unit_id"] = job("R05_PRIMARY", f, "GREEDY_OR")["model_unit_id"]
                j["fit_job_id"] = j["reuse_model_unit_id"]
                j["state"] = "REUSE_EXACT_R05_SRC111_AFTER_AUTHORIZATION"
            result.append(j)
        result.extend(job("R07_SINGLE_SURFACE_REFIT", f, "GREEDY_OR", view=s) for s in ("native84", "app_web67", "host26"))
    for f in loco:
        result.extend(job("R08_CONFIG_TRANSFER", f, m, "OP05" if m in LEARNERS else "NOT_APPLICABLE")
                      for m in ("HISTORICAL_SEVEN", "DIRECT_CORE_OR", "GREEDY_OR"))
    ids = sorted(set(loeo[0]["train"] + loeo[0]["outer_test"]))
    final = job("FINAL_DEVELOPMENT_REFIT", {"split_id": "ALL_DEVELOPMENT-v1", "fold_id": "ALL_DEVELOPMENT-v1-01",
                "train": ids, "outer_test": []}, "GREEDY_OR")
    final["authorization_stage"] = "FINAL_DEVELOPMENT_REFIT_SEPARATE_AUTHORIZATION"
    result.append(final)
    result.sort(key=lambda r: (r["priority"], r["job_id"]))
    fits = [copy.deepcopy(j) for j in result if j["method_id"] in LEARNERS and not j["reuse_model_unit_id"]]
    assert len(fits) == 72 and len({j["fit_job_id"] for j in fits}) == len(fits)
    assert len(result) == 115
    return fits, result, prediction_units(result)
