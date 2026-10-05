"""Metrics over expected stage IDs. Abstentions/failures never leave denominators."""
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations

from .contracts import DECISIONS, PHASES
from .models import complexity


def rate(numerator, denominator, *, reason=None, no_truth=False, expected=None):
    return {"numerator": float(numerator) if isinstance(numerator, Fraction) else numerator,
            "denominator": denominator, "expected_denominator": denominator if expected is None else expected,
            "value": float(numerator / denominator) if denominator else None,
            "minimum_nonzero_rate": 1 / denominator if denominator else None,
            "status": "OK" if denominator else "NOT_EVALUABLE_NO_TRUTH" if no_truth else "NOT_EVALUABLE",
            "reason": reason if reason is not None else None if denominator else "ZERO_SUPPORTED_DENOMINATOR"}


def cell_coverage(ids, index, numerator_key, denominator_key):
    """Unknown model sizes invalidate the full scope, including each stratum.

    A recorded zero is a known zero (empty model/constant); None is unknown.
    Keep the known subset explicitly scoped, never use it as the full rate.
    """
    known = [i for i in ids if index[i].get(denominator_key) is not None]
    for i in known:
        n, d = index[i][numerator_key], index[i][denominator_key]
        if type(n) is not int or type(d) is not int or not 0 <= n <= d:
            raise ValueError("INVALID_MODEL_CELL_COUNTS")
    subset = rate(sum(index[i][numerator_key] for i in known),
                  sum(index[i][denominator_key] for i in known))
    if len(known) == len(ids):
        return subset
    return {"numerator": None, "denominator": None, "expected_denominator": None,
            "value": None, "minimum_nonzero_rate": None, "status": "NOT_EVALUABLE",
            "reason": "MISSING_MODEL_EXPECTED_CELL_COUNTS",
            "unknown_expected_source_rows": [i for i in ids if i not in known],
            "known_subset": {**subset, "scope": "ONLY_ROWS_WITH_KNOWN_MODEL_CELL_COUNTS",
                "source_rows": known, "stage_n": len(known),
                "model_unit_ids": sorted({index[i]["model_unit_id"] for i in known if index[i].get("model_unit_id")})}}


def evaluate(expected_ids, predictions, metadata, *, evaluation_role="SYNTHETIC_TEST", strata=True):
    ids = tuple(expected_ids)
    if len(ids) != len(set(ids)) or any(i not in metadata for i in ids):
        raise ValueError("METRIC_EXPECTED_IDS_OR_METADATA_INVALID")
    index = {}
    bindings = set()
    for row in predictions:
        oid = row["opaque_id"]
        if oid not in ids or oid in index or row["decision"] not in DECISIONS:
            raise ValueError("METRIC_DUPLICATE_UNEXPECTED_OR_INVALID_PREDICTION")
        if row.get("model_id"):
            bindings.add((row.get("protocol_digest"), row.get("split_id"), row.get("fold_id"), row["model_id"]))
        index[oid] = row
    if len(bindings) > 1:
        raise ValueError("DIFFERENT_MODEL_FOLD_OR_TRACK_REQUIRES_EXPLICIT_OOF_AGGREGATOR")
    first = predictions[0] if predictions else {}
    context = {k: first.get(k, "NOT_PROVIDED") for k in ("protocol_digest", "split_id", "fold_id", "model_id",
        "study_version", "candidate_version", "input_manifest_ref", "method_id", "operating_point")}
    missing = [i for i in ids if i not in index]
    for oid in missing:
        index[oid] = {"opaque_id": oid, "decision": "FAILED", "failure_reason": "MISSING_EXPECTED_PREDICTION",
                      "selected_atoms_available": 0, "selected_atoms_expected": None,
                      "clauses_defined": 0, "clauses_expected": None}
    truth = {i: metadata[i]["supervised_label"] for i in ids}
    if any(v is not None and (type(v) is not int or v not in (0, 1)) for v in truth.values()):
        raise ValueError("INVALID_SUPERVISED_TRUTH")
    if any(truth[i] is not None and (metadata[i]["phase"] not in PHASES or truth[i] != int(metadata[i]["phase"] == "attack")) for i in ids):
        raise ValueError("METRIC_LABEL_ADMISSION_PHASE_CONFLICT")
    positive = [i for i in ids if truth[i] == 1]
    negative = [i for i in ids if truth[i] == 0]
    phases = {p: [i for i in ids if truth[i] is not None and metadata[i]["phase"] == p] for p in PHASES}
    counts = Counter(index[i]["decision"] for i in ids)
    alerts = lambda rows: sum(index[i]["decision"] == "MANIPULATION_ALERT" for i in rows)
    defined = lambda rows: sum(index[i]["decision"] in ("MANIPULATION_ALERT", "NO_ALERT") for i in rows)
    no_truth = not positive and not negative
    metrics = {
        "attack_tpr": rate(alerts(positive), len(positive), no_truth=no_truth),
        "clean_alarm_rate": rate(alerts(negative), len(negative), no_truth=no_truth),
        "pre_alarm_rate": rate(alerts(phases["clean_pre"]), len(phases["clean_pre"]), no_truth=no_truth),
        "post_alarm_rate": rate(alerts(phases["clean_post"]), len(phases["clean_post"]), no_truth=no_truth),
        "decided_clean_alarm_rate": rate(alerts(negative), defined(negative), no_truth=no_truth),
        "decision_coverage": rate(defined(ids), len(ids)),
        "abstention_rate": rate(counts["INSUFFICIENT_EVIDENCE"] + counts["EMPTY_MODEL"], len(ids)),
        "failure_rate": rate(counts["FAILED"], len(ids)),
    }
    # Missing rows retain the model's expected atom/clause counts when known.
    atom_sizes = {r["selected_atoms_expected"] for r in predictions}
    clause_sizes = {r["clauses_expected"] for r in predictions}
    for field, sizes in (("selected_atoms_expected", atom_sizes), ("clauses_expected", clause_sizes)):
        # Never borrow counts across folds/models. Unbound hand-metric tables
        # retain their declared uniform shape; OOF supplies every row itself.
        scopes = {(r.get("model_unit_id"), r.get("fold_id"), r.get("model_id")) for r in predictions}
        if (len(scopes) == 1 and len(sizes) == 1 and first.get("fold_id") != "EXPLICIT_OOF_AGGREGATE"
                and not ("model_id" in first and first["model_id"] is None)):
            for oid in missing:
                index[oid][field] = next(iter(sizes))
    for name, numerator_key, denominator_key in (("atom_coverage", "selected_atoms_available", "selected_atoms_expected"),
                                                ("clause_coverage", "clauses_defined", "clauses_expected")):
        metrics[name] = cell_coverage(ids, index, numerator_key, denominator_key)
    config_env = defaultdict(lambda: defaultdict(list))
    for oid in positive:
        config_env[metadata[oid]["config_id"]][metadata[oid]["environment_group_id"]].append(oid)
    macro_numerator = sum((sum((Fraction(alerts(rows), len(rows)) for rows in envs.values()), Fraction()) / len(envs)
                           for envs in config_env.values()), Fraction())
    metrics["MacroTPR_config_environment"] = rate(macro_numerator, len(config_env), no_truth=no_truth)
    if config_env:
        metrics["MacroTPR_config_environment"]["minimum_nonzero_rate"] = float(min(
            Fraction(1, len(config_env) * len(envs) * len(rows)) for envs in config_env.values() for rows in envs.values()))
    triplets = defaultdict(dict)
    for oid in positive + negative:
        m = metadata[oid]
        key = (m["bundle_id"], m["triplet_id"])
        if m["phase"] in triplets[key]:
            raise ValueError("METRIC_DUPLICATE_TRIPLET_PHASE")
        triplets[key][m["phase"]] = oid
    triplet_rows, complete, exact, recovery_den, recovery = [], 0, 0, 0, 0
    for (bundle, triplet), members in sorted(triplets.items()):
        full = set(members) == set(PHASES)
        pre, attack, post = (index[members[p]]["decision"] if p in members else None for p in PHASES)
        success = full and (pre, attack, post) == ("NO_ALERT", "MANIPULATION_ALERT", "NO_ALERT")
        complete += full; exact += success
        eligible_recovery = "attack" in members and "clean_post" in members and attack == "MANIPULATION_ALERT"
        recovery_den += eligible_recovery
        recovery += eligible_recovery and post == "NO_ALERT"
        triplet_rows.append({**context, "bundle_id": bundle, "triplet_id": triplet,
            "pre_id": members.get("clean_pre"), "attack_id": members.get("attack"), "post_id": members.get("clean_post"),
            "pre_decision": pre, "attack_decision": attack, "post_decision": post,
            "exact_FTF": success, "status": "COMPLETE" if full else "INCOMPLETE_ADMITTED_TRIPLET",
            "source_rows": list(members.values())})
    metrics["exact_FTF"] = rate(exact, complete, no_truth=no_truth)
    metrics["conditional_recovery"] = rate(recovery, recovery_den, no_truth=no_truth)
    intervals = {}
    for name, rows in (("positive", positive), ("negative", negative)):
        unknown = sum(index[i]["decision"] in ("INSUFFICIENT_EVIDENCE", "EMPTY_MODEL", "FAILED") for i in rows)
        intervals[name] = {"lower": rate(alerts(rows), len(rows), no_truth=no_truth),
                           "upper": rate(alerts(rows) + unknown, len(rows), no_truth=no_truth),
                           "is_population_CI": False}
    groups = {}
    if strata:
        for group in ("environment", "config", "config_environment", "phase"):
            grouped = defaultdict(list)
            keys = {"environment": ("environment_group_id",), "config": ("config_id",),
                    "config_environment": ("config_id", "environment_group_id"), "phase": ("phase",)}[group]
            for oid in ids:
                grouped[" | ".join(str(metadata[oid][k]) for k in keys)].append(oid)
            groups[group] = {name: evaluate(part, [index[i] for i in part], metadata,
                evaluation_role=evaluation_role, strata=False)["metrics"] for name, part in sorted(grouped.items())}
            for name, ms in groups[group].items():
                for metric in ms.values():
                    metric["stratum"] = group + ":" + name
    for metric_id, metric in metrics.items():
        metric.update(context, metric_id=metric_id, stratum="ALL_EXPECTED", evaluation_role=evaluation_role, source_rows=list(ids))
    return {"status": "INCOMPLETE_EXPECTED_PREDICTIONS" if missing else "COMPLETE", "evaluation_role": evaluation_role,
            "expected_stage_n": len(ids), "received_prediction_n": len(predictions), "missing_ids": missing,
            "supervised_positive_n": len(positive), "supervised_negative_n": len(negative),
            "descriptive_n": len(ids) - len(positive) - len(negative),
            "decision_counts": {d: counts[d] for d in DECISIONS}, "metrics": metrics,
            "identification_intervals": intervals, "triplet_rows": triplet_rows,
            "incomplete_admitted_triplets": sum(r["status"] != "COMPLETE" for r in triplet_rows), "strata": groups}


def model_stability(models):
    rows = []
    for a, b in combinations(models, 2):
        left = {(l.atom_id, l.polarity) for c in a.clauses for l in c.literals}
        right = {(l.atom_id, l.polarity) for c in b.clauses for l in c.literals}
        r = rate(len(left & right), len(left | right))
        if not left and not right:
            r["reason"] = "BOTH_MODELS_EMPTY"
        rows.append(dict(r, model_a=a.model_id, model_b=b.model_id, fold_a=a.binding["fold_id"], fold_b=b.binding["fold_id"]))
    return rows
