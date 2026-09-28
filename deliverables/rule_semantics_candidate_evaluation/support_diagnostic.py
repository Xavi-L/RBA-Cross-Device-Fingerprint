"""Count fixed signed-candidate support from saved states, never fit or select.

Definition authority: R04_freeze_r1/snapshot/.../rule_learning/selector.py
lines 60-74, 99-120 and 151-155, plus that snapshot's learning_search_space.json
``support`` object.  No learner module is imported or called.  The caller must
close and reload candidate results before supplying them here.

Both frozen POSITIVE and NEGATIVE literals are counted without choosing one.
NEGATIVE flips only saved T/F; U and FAILED remain unchanged.  Success is not
model feasibility, selection, useful signal or independent alarm authority.
"""
from collections import Counter, defaultdict
from copy import deepcopy


PHASES = ("clean_pre", "attack", "clean_post")
STATES = ("T", "F", "U", "FAILED")
SUPPORT_THRESHOLDS = {
    "minimum_available_triplets": 3,
    "minimum_true_attack_triplets_per_literal_or_clause": 2,
    "minimum_support_bundles": 1,
    "minimum_support_environments": 1,
}
COUNT_FIELDS = {
    "minimum_available_triplets": "available_complete_triplets",
    "minimum_true_attack_triplets_per_literal_or_clause": "true_attack_triplets",
    "minimum_support_bundles": "support_bundles",
    "minimum_support_environments": "support_environments",
}


def _check_definition(support_contract):
    if not isinstance(support_contract, dict):
        raise ValueError("SUPPORT_CONTRACT_OBJECT_REQUIRED")
    if support_contract.get("statistics_scope") != "TRAIN_FOLD_ONLY":
        raise ValueError("SUPPORT_SCOPE_MUST_BE_TRAIN_FOLD_ONLY")
    if support_contract.get("availability_unit") != "COMPLETE_S01_ADMITTED_TRIPLET_ALL_THREE_ATOM_STATES_DEFINED":
        raise ValueError("SUPPORT_AVAILABILITY_DEFINITION_CHANGED")
    for name, value in SUPPORT_THRESHOLDS.items():
        if type(support_contract.get(name)) is not int or support_contract[name] != value:
            raise ValueError("UNREVIEWED_SUPPORT_THRESHOLD:" + name)


def _train_metadata(train_ids, metadata_by_id):
    """Read only train metadata, preserving explicit bundle/triplet identities."""
    groups = defaultdict(lambda: defaultdict(list))
    valid, issues = {}, []
    for opaque_id in train_ids:
        meta = metadata_by_id.get(opaque_id)
        if not isinstance(meta, dict):
            issues.append({"opaque_id": opaque_id, "reason": "TRAIN_METADATA_MISSING"})
            continue
        if any(type(meta.get(key)) is not str or not meta[key] for key in
               ("bundle_id", "triplet_id", "config_id", "environment_group_id")):
            issues.append({"opaque_id": opaque_id, "reason": "TRAIN_GROUP_IDENTITY_MISSING"})
            continue
        phase = meta.get("phase")
        if phase not in PHASES:
            issues.append({"opaque_id": opaque_id, "reason": "INVALID_TRAIN_PHASE"})
            continue
        if meta.get("supervised_label") != int(phase == "attack"):
            issues.append({"opaque_id": opaque_id, "reason": "LABEL_AND_ADMITTED_PHASE_DISAGREE"})
            continue
        valid[opaque_id] = meta
        groups[(meta["bundle_id"], meta["triplet_id"])][phase].append(opaque_id)
    complete, gaps = {}, []
    for key, phases in sorted(groups.items()):
        if set(phases) != set(PHASES) or any(len(ids) != 1 for ids in phases.values()):
            gaps.append({"bundle_id": key[0], "triplet_id": key[1],
                         "reason": "INCOMPLETE_OR_DUPLICATE_TRAIN_TRIPLET_PHASE",
                         "members_by_phase": dict(phases)})
            continue
        trio = {phase: phases[phase][0] for phase in PHASES}
        if len({(valid[i]["config_id"], valid[i]["environment_group_id"]) for i in trio.values()}) != 1:
            gaps.append({"bundle_id": key[0], "triplet_id": key[1],
                         "reason": "TRIPLET_GROUP_METADATA_MISMATCH", "members_by_phase": trio})
            continue
        complete[key] = trio
    return valid, complete, issues, gaps


def _state_for(index, opaque_id, candidate_key):
    rows = index.get((opaque_id, *candidate_key), [])
    if len(rows) != 1:
        return "FAILED", "SAVED_RESULT_MISSING" if not rows else "SAVED_RESULT_DUPLICATED"
    state = rows[0].get("state")
    if state not in STATES:
        return "FAILED", "SAVED_RESULT_STATE_INVALID"
    return state, None


def build_train_support(candidate_results, metadata_by_id, split_manifest,
                        support_contract, candidate_keys):
    """Return per-LOEO-fold signed support from already saved result objects.

    ``support_contract`` is exactly json.load(frozen_learning_search_space)
    ["support"]. ``split_manifest`` is the whole R04 SPLIT_MANIFEST.json.
    ``candidate_keys`` is [(candidate_id, mode), ...]; language uses ``default``
    and webdriver uses ``legacy_projection_v1``. Result states outside each
    fold's train members are never consulted for support. Test membership is
    retained for reference/disjointness checks only; LOCO folds are ignored.
    """
    _check_definition(support_contract)
    keys = [tuple(k) for k in candidate_keys]
    if not keys or len(set(keys)) != len(keys) or any(
            len(k) != 2 or any(type(v) is not str or not v for v in k) for k in keys):
        raise ValueError("INVALID_OR_DUPLICATE_CANDIDATE_KEYS")
    if not isinstance(split_manifest, dict) or not isinstance(split_manifest.get("folds"), list):
        raise ValueError("SPLIT_MANIFEST_FOLDS_REQUIRED")
    # Index identities only. In particular, do not inspect held-out state here.
    index = defaultdict(list)
    for row in candidate_results:
        if isinstance(row, dict):
            key = (row.get("opaque_id"), row.get("candidate_id"), row.get("mode"))
            index[key].append(row)
    rows, selected_folds = [], []
    for fold in split_manifest["folds"]:
        if fold.get("split_id") != "LOEO-v1":
            continue
        fold_id = fold.get("fold_id")
        if not isinstance(fold_id, str) or fold_id in selected_folds:
            raise ValueError("INVALID_OR_DUPLICATE_LOEO_FOLD")
        selected_folds.append(fold_id)
        train, test = fold.get("train"), fold.get("outer_test")
        if not isinstance(train, list) or not isinstance(test, list) or any(
                type(i) is not str or not i for i in train + test):
            raise ValueError("INVALID_SPLIT_MEMBERS")
        membership_issues = []
        if len(set(train)) != len(train) or len(set(test)) != len(test):
            membership_issues.append("DUPLICATE_SPLIT_MEMBERS")
        if set(train) & set(test):
            membership_issues.append("TRAIN_TEST_MEMBER_OVERLAP")
        # Avoid counting duplicated stages even when a malformed split is given.
        train_ids = list(dict.fromkeys(train))
        meta, triplets, metadata_issues, pairing_gaps = _train_metadata(train_ids, metadata_by_id)
        if not triplets:
            membership_issues.append("TRAIN_REQUIRES_COMPLETE_ADMITTED_TRIPLETS")
        for candidate_id, mode in keys:
            for polarity in ("POSITIVE", "NEGATIVE"):
                candidate_key = (candidate_id, mode)
                states, result_issues = {}, []
                for opaque_id in train_ids:
                    value, reason = _state_for(index, opaque_id, candidate_key)
                    states[opaque_id] = ({"T": "F", "F": "T", "U": "U", "FAILED": "FAILED"}[value]
                                         if polarity == "NEGATIVE" else value)
                    if reason:
                        result_issues.append({"opaque_id": opaque_id, "reason": reason})
                available = [key for key, trio in triplets.items()
                             if all(states[i] in ("T", "F") for i in trio.values())]
                positive = [key for key in available if states[triplets[key]["attack"]] == "T"]
                positive_meta = [meta[triplets[key]["attack"]] for key in positive]
                phase_counts = {}
                for phase in PHASES:
                    members = [i for i in train_ids if i in meta and meta[i]["phase"] == phase]
                    counts = Counter(states[i] for i in members)
                    phase_counts[phase] = {"expected": len(members),
                        "defined": counts["T"] + counts["F"], **{s: counts[s] for s in STATES}}
                rec = {"candidate_id": candidate_id, "mode": mode, "literal_polarity": polarity,
                    "fold_id": fold_id, "split_id": "LOEO-v1", "held_out_environment": fold.get("target"),
                    "statistics_scope": "TRAIN_FOLD_ONLY", "train_ids": train_ids,
                    "outer_test_ids_reference_only": list(test), "expected_train_stages": len(train),
                    "unique_train_stages": len(train_ids), "complete_metadata_triplets": len(triplets),
                    "available_complete_triplets": len(available), "true_attack_triplets": len(positive),
                    "support_bundles": len({m["bundle_id"] for m in positive_meta}),
                    "support_environments": len({m["environment_group_id"] for m in positive_meta}),
                    "support_configurations": len({m["config_id"] for m in positive_meta}),
                    "complete_metadata_triplet_ids": [list(k) for k in triplets],
                    "available_complete_triplet_ids": [list(k) for k in available],
                    "true_attack_triplet_ids": [list(k) for k in positive],
                    "phase_availability": phase_counts,
                    "unassigned_metadata_stage_count": len(train_ids) - len(meta),
                    "train_state_counts": {s: sum(v == s for v in states.values()) for s in STATES},
                    "membership_issues": membership_issues, "metadata_issues": metadata_issues,
                    "triplet_pairing_gaps": pairing_gaps, "saved_result_issues": result_issues}
                checks = {name: {"actual": rec[COUNT_FIELDS[name]], "minimum": support_contract[name],
                                "satisfied": rec[COUNT_FIELDS[name]] >= support_contract[name]}
                          for name in SUPPORT_THRESHOLDS}
                rec["minimum_support_conditions"] = checks
                rec["support_thresholds_satisfied"] = all(c["satisfied"] for c in checks.values())
                rec["no_train_execution_failures"] = rec["train_state_counts"]["FAILED"] == 0
                reasons = [name.upper() + "_NOT_MET" for name, c in checks.items() if not c["satisfied"]]
                if not rec["no_train_execution_failures"]:
                    reasons.append("TRAIN_EXECUTION_FAILURE")
                if membership_issues or metadata_issues or pairing_gaps:
                    reasons.append("TRAIN_MEMBERSHIP_OR_PAIRING_INVALID")
                rec["support_eligible"] = not reasons
                rec["reasons"] = reasons
                clean = [i for i in train_ids if i in meta and meta[i]["phase"] in ("clean_pre", "clean_post")]
                rec["train_clean_literal_true"] = {"k": sum(states[i] == "T" for i in clean), "n": len(clean)}
                rec["model_feasibility_or_selection"] = "NOT_EVALUATED"
                rows.append(rec)
    if not selected_folds:
        raise ValueError("NO_ORIGINAL_LOEO_FOLDS")
    return {"schema_version": "rsr-signed-train-support-v1",
        "source_definition": {"frozen_search_support": deepcopy(support_contract),
            "code": "R04_freeze_r1/snapshot/hybridguard_agent/research/rule_learning/selector.py:99-120,151-155",
            "metadata_pairing": "Exact train (bundle_id, triplet_id), unique clean_pre/attack/clean_post"},
        "literal_polarity": "BOTH_FROZEN_POLARITIES_NO_SELECTION", "selected_folds": selected_folds,
        "fold_candidate_diagnostics": rows,
        "candidate_fold_summary": [{"candidate_id": cid, "mode": mode, "fold_id": fid,
            "support_by_polarity": {r["literal_polarity"]: {"minimum_support_satisfied": r["support_thresholds_satisfied"],
                "eligible_with_no_train_failure_and_valid_pairing": r["support_eligible"]}
                for r in rows if (r["candidate_id"], r["mode"], r["fold_id"]) == (cid, mode, fid)}}
            for fid in selected_folds for cid, mode in keys],
        "eligible_signed_candidate_fold_count": sum(r["support_eligible"] for r in rows),
        "expected_candidate_fold_count": len(keys) * len(selected_folds),
        "expected_signed_diagnostic_count": 2 * len(keys) * len(selected_folds),
        "execution_counts": {"candidate_calls": 0, "fit": 0, "model_prediction": 0},
        "limits": ["Only saved result states were counted, separately within each original LOEO train partition.",
            "Both old grammar polarities are counted from saved states; no polarity is selected and no new candidate is invoked.",
            "Support pass is necessary, not model feasibility, selection, independent alarm authority or evidence of useful signal.",
            "No whole-model clean budget, objective, coverage constraint, ranking, pruning, encoder or model was evaluated."]}
