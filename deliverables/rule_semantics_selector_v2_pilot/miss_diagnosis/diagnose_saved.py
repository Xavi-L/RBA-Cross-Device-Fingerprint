#!/usr/bin/env python3
"""Post-hoc arithmetic on saved inputs/encoders; no training or prediction API.

This does not search for a model or create a new model/prediction file. The one
specified DPR addition is an explanation of the saved training constraints,
not a seven-rule experiment. Heldout evidence reuses closed prediction files.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "deliverables/rule_semantics_raw_only_expansion_v1/prepared"
SCREEN = "w10-cdp-emulation-screen-metrics-only-v1"
WEBGL = "w9-stealth-boundary-webgl-pair-v1"
TARGETS = (SCREEN, WEBGL)
PHASES = ("clean_pre", "attack", "clean_post")
DPR = "CONTROL:app.web_data.screen_layer.device_pixel_ratio:LE:2.625:NEGATIVE"


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cell_state(cell):
    if cell.get("evaluation_status") != "OK":
        return "FAILED"
    if cell["available"] is False and cell["value"] is None:
        return "U"
    assert cell["available"] is True and type(cell["value"]) is bool
    return "T" if cell["value"] else "F"


def encoded_states(row, encoder):
    """Apply stored thresholds verbatim; no quantile computation or refit."""
    features = row["features"] | row["candidate_cells"]
    result = {name: cell_state(features[name]) for name in encoder["fixed_atoms"]}
    for name, fit in encoder["numeric"].items():
        cell = features[name]
        for aid, threshold in zip(fit["atom_ids"], fit["thresholds"], strict=True):
            if cell["evaluation_status"] != "OK":
                result[aid] = "FAILED"
            elif cell["available"] is False:
                assert cell["value"] is None
                result[aid] = "U"
            else:
                assert type(cell["value"]) in (int, float) and math.isfinite(cell["value"])
                result[aid] = "T" if cell["value"] <= threshold else "F"
    return result


def either(states):
    if not states:
        return "EMPTY_MODEL"
    if "FAILED" in states:
        return "FAILED"
    return "T" if "T" in states else "F" if all(s == "F" for s in states) else "U"


def clauses(model):
    assert all(len(c["literals"]) == 1 for c in model["clauses"])
    return [c["literals"][0]["atom_id"] + ":" + c["literals"][0]["polarity"] for c in model["clauses"]]


def counts(states, ids, meta, config=None):
    return {phase: {"n": len(current := [i for i in ids if meta[i]["phase"] == phase
                    and (config is None or meta[i]["config_id"] == config)]),
                    **{s: sum(states[i] == s for i in current) for s in ("T", "F", "U", "FAILED")}}
            for phase in PHASES}


def score(selected, pool, ids, meta, atoms, search, grammar):
    states = {i: either([pool[c][i] for c in selected]) for i in ids}
    configurations = defaultdict(lambda: defaultdict(list))
    for i in ids:
        if meta[i]["phase"] == "attack":
            configurations[meta[i]["config_id"]][meta[i]["environment_group_id"]].append(i)
    macro = sum((Fraction(sum(states[i] == "T" for i in members),
                          len(configurations) * len(envs) * len(members))
                 for envs in configurations.values() for members in envs.values()), Fraction())
    phases = counts(states, ids, meta)
    coverage = {p: Fraction(v["T"] + v["F"], v["n"]) for p, v in phases.items()}
    clean = phases["clean_pre"]["T"] + phases["clean_post"]["T"]
    limits = search["constraints"]
    budget = math.floor(Fraction("0.05") * (phases["clean_pre"]["n"] + phases["clean_post"]["n"]))
    aids = [c.rsplit(":", 1)[0] for c in selected]
    families = Counter(atoms[a]["family"] for a in aids)
    reasons = []
    if len(selected) > limits["max_clauses"]:
        reasons.append("MAX_CLAUSES")
    if len(selected) > limits["max_literals"]:
        reasons.append("MAX_LITERALS")
    if 2 * len(selected) > limits["max_complexity_primary"]:
        reasons.append("MAX_OBJECTIVE_COMPLEXITY")
    if len(set(aids)) > grammar["composition"]["max_distinct_atoms"]:
        reasons.append("MAX_DISTINCT_ATOMS")
    if any(n > grammar["composition"]["max_clauses_per_family"] for n in families.values()):
        reasons.append("FAMILY_LIMIT")
    if len(aids) != len(set(aids)):
        reasons.append("DUPLICATE_OR_CONTRADICTORY_ATOM")
    if clean > budget:
        reasons.append("CLEAN_BUDGET")
    if min(coverage.values()) < Fraction(str(limits["min_decision_coverage"])):
        reasons.append("PHASE_COVERAGE")
    if "FAILED" in states.values():
        reasons.append("EXECUTION_FAILURE")
    return {"states": states, "macro_tpr": macro,
            "objective": macro - Fraction(str(search["objective"]["lambda"])) * 2 * len(selected),
            "complexity": 2 * len(selected), "clauses": len(selected), "clean_alarms": clean,
            "clean_budget": budget, "coverage": coverage, "minimum_coverage": min(coverage.values()),
            "feasible": bool(selected) and not reasons, "constraint_failures": reasons}


def compact(score_value):
    return {k: v for k, v in score_value.items() if k != "states"}


def verify_score(actual, saved, ids):
    assert [actual["states"][i] for i in ids] == saved["states"]
    for key in ("objective", "macro_tpr", "minimum_coverage"):
        assert actual[key] == Fraction(saved[key]["numerator"], saved[key]["denominator"])
    for key in ("complexity", "clean_alarms", "feasible"):
        assert actual[key] == saved[key]
    assert all(actual["coverage"][p] == Fraction(saved["coverage"][p]["numerator"],
                                               saved["coverage"][p]["denominator"]) for p in PHASES)


def structural_key(selected, catalog):
    return sorted((catalog[c.rsplit(":", 1)[0]]["key"][0],
                   json.dumps(catalog[c.rsplit(":", 1)[0]]["key"][1:], sort_keys=True, separators=(",", ":")),
                   c.rsplit(":", 1)[1]) for c in selected)


def quality(selected, catalog):
    return sum(catalog[c.rsplit(":", 1)[0]]["quality"] for c in selected if c.endswith(":POSITIVE"))


def diagnose():
    contract = read(PILOT / "CONTRACT.json")
    execution = read(PILOT / "EXECUTION.json")
    assert execution["execution_complete"] and read(PILOT / "RESULT_REVIEW.json")["status"] == "PASS"
    search = read(ROOT / "hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json")
    grammar = read(ROOT / "hybridguard_agent/config/rule_learning_v1_20260924/candidate_grammar.json")
    raw = {i: read(SOURCE / "inputs" / (i + ".json")) for i in contract["sample_ids"]}
    meta = {i: read(SOURCE / "evaluation" / (i + ".json")) for i in contract["sample_ids"]}
    assert all(raw[i]["opaque_id"] == meta[i]["opaque_id"] == i for i in raw)
    by_triplet = defaultdict(dict)
    for i, m in meta.items():
        by_triplet[m["triplet_id"]][m["phase"]] = i
    evidence, candidate_rows, screen_trace, checks = [], [], [], []
    for job in contract["jobs"]:
        if job["stage"] != "RETENTION":
            continue
        folder = PILOT / "trials" / job["job_id"]
        model, training = read(folder / "model.json"), read(folder / "training.json")
        sparse = read(PILOT / "trials" / job["initializer"] / "training.json")
        ids = job["train_ids"]
        assert model["fit"]["train_ids"] == training["train_ids"] == ids
        atoms = {a["atom_id"]: a for a in training["encoded_atoms"]}
        encoded = {i: encoded_states(raw[i], model["encoder"]) for i in ids}
        assert all(set(row) == set(atoms) for row in encoded.values())
        pool = {}
        for record in training["candidate_manifest"]:
            cid = record["clause_id"]
            aid, polarity = cid.rsplit(":", 1)
            pool[cid] = {i: ({"T": "F", "F": "T"}.get(encoded[i][aid], encoded[i][aid])
                            if polarity == "NEGATIVE" else encoded[i][aid]) for i in ids}
            saved = training["support"][cid]
            phase_counts = counts(pool[cid], ids, meta)
            assert saved["train_ids"] == ids
            for phase, item in phase_counts.items():
                assert saved["phase_availability"][phase] == {"expected": item["n"],
                    "defined": item["T"] + item["F"], **{s: item[s] for s in ("T", "F", "U", "FAILED")}}
            complete = [trio for trio in by_triplet.values() if set(trio.values()) <= set(ids)
                        and all(pool[cid][i] in ("T", "F") for i in trio.values())]
            positive = [trio for trio in complete if pool[cid][trio["attack"]] == "T"]
            assert saved["triplets"] == len(complete) and saved["true_attack_triplets"] == len(positive)
            actual_positive = {(meta[t["attack"]]["bundle_id"], meta[t["attack"]]["triplet_id"]) for t in positive}
            assert actual_positive == {tuple(x) for x in saved["true_attack_triplet_ids"]}
            candidate_rows.append({"fold_id": job["fold_id"], "clause_id": cid,
                "eligible": record["eligible"], "support_reasons": record["reasons"], "selected": record["selected"],
                "signal_group": record["signal_group"], "field_refs": atoms[aid]["provenance"].get("field_refs", [atoms[aid]["provenance"].get("field")]),
                "train": phase_counts, "screen_train": counts(pool[cid], ids, meta, SCREEN),
                "webgl_train": counts(pool[cid], ids, meta, WEBGL),
                "support": {k: saved[k] for k in ("triplets", "true_attack_triplets", "bundles", "environments", "eligible")}})
        selected = clauses(model)
        current = score(selected, pool, ids, meta, atoms, search, grammar)
        verify_score(current, model["fit"]["training_result"], ids)
        assert DPR in pool and training["support"][DPR]["eligible"]
        addition = score(selected + [DPR], pool, ids, meta, atoms, search, grammar)
        marginal = [i for i in ids if meta[i]["phase"] == "attack"
                    and current["states"][i] != "T" and pool[DPR][i] == "T"]
        unique_coverage = []
        for removed in selected:
            other = [c for c in selected if c != removed]
            loss = [i for i in ids if meta[i]["phase"] == "attack" and current["states"][i] == "T"
                    and either([pool[c][i] for c in other] + [pool[DPR][i]]) != "T"]
            unique_coverage.append({"removed_clause_id": removed, "lost_train_attack_ids_if_replaced_by_DPR": loss,
                                   "lost_configurations": dict(Counter(meta[i]["config_id"] for i in loss))})
        previous = []
        for index, step in enumerate(sparse["trace"], 1):
            assert step["operation"] == "ADD"
            actual = score(step["selected"], pool, ids, meta, atoms, search, grammar)
            verify_score(actual, step["score"], ids)
            proposed = previous + [DPR]
            candidate = score(proposed, pool, ids, meta, atoms, search, grammar)
            numeric_tie = all(actual[k] == candidate[k] for k in
                              ("objective", "macro_tpr", "clean_alarms", "minimum_coverage", "complexity"))
            aq, dq = quality(step["selected"], training["semantic_catalog"]), quality(proposed, training["semantic_catalog"])
            reason = ("LOWER_OBJECTIVE" if actual["objective"] > candidate["objective"] else
                      "LOWER_REGISTERED_QUALITY_ON_NUMERIC_TIE" if numeric_tie and aq > dq else
                      "LATER_STRUCTURAL_KEY_ON_NUMERIC_AND_QUALITY_TIE" if numeric_tie and aq == dq
                      and structural_key(step["selected"], training["semantic_catalog"]) < structural_key(proposed, training["semantic_catalog"])
                      else "UNEXPLAINED")
            assert reason != "UNEXPLAINED"
            screen_trace.append({"fold_id": job["fold_id"], "step": index,
                "actual_added": list(set(step["selected"]) - set(previous)), "DPR_not_chosen_reason": reason,
                "actual": compact(actual), "DPR_at_same_step": compact(candidate),
                "numeric_tie": numeric_tie, "actual_quality": aq, "DPR_quality": dq})
            previous = step["selected"]
        current_records = [r for r in candidate_rows if r["fold_id"] == job["fold_id"]]
        firing = [r for r in current_records if r["webgl_train"]["attack"]["T"] > 0]
        min_clean = min(r["train"]["clean_pre"]["T"] + r["train"]["clean_post"]["T"] for r in firing)
        assert min_clean > current["clean_budget"]
        target_saved = {}
        for label, source, prefix in (("NEW_SCHEME", PILOT, "SELECTOR_V2"), ("BASE", SOURCE, "BASE"),
                                      ("PRIOR_COMBINATION", SOURCE, "LANG_ADD_WD_REPLACE")):
            jid = prefix + "__" + job["fold_id"] + "__RETENTION"
            saved_rows = read(source / "trials" / jid / "evaluation_rows.json")
            predictions = lines(source / "trials" / jid / "predictions.jsonl")
            assert [r["opaque_id"] for r in saved_rows] == [r["opaque_id"] for r in predictions] == job["outer_test_ids"]
            assert [r["decision"] for r in saved_rows] == [r["decision"] for r in predictions]
            target_saved[label] = {target: dict(Counter(r["decision"] for r in saved_rows
                if r["config_id"] == target and r["phase"] == "attack")) for target in TARGETS}
        encoded_pair_differences = []
        for tid, trio in by_triplet.items():
            if not set(trio.values()) <= set(ids) or meta[trio["attack"]]["config_id"] != WEBGL:
                continue
            encoded_pair_differences.append({"triplet_id": tid, **{phase:
                [a for a in atoms if encoded[trio["attack"]][a] != encoded[trio[phase]][a]]
                for phase in ("clean_pre", "clean_post")}})
        evidence.append({"fold_id": job["fold_id"], "heldout_environment": job["heldout_environment"],
            "train_n": len(ids), "encoded_atom_count": len(atoms), "literal_count": len(pool),
            "saved_train_model": compact(current), "screen_DPR_train_marginal_ids": marginal,
            "screen_DPR_hypothetical_addition_train_only": compact(addition),
            "screen_one_for_one_train_loss": unique_coverage,
            "screen_same_group_selected": [c for c in selected if training["signal_groups"][c.rsplit(":", 1)[0]] == training["signal_groups"][DPR.rsplit(":", 1)[0]]],
            "webgl_triggering_literal_count": len(firing), "webgl_triggering_literal_min_clean_alarms": min_clean,
            "webgl_OR_clean_bound_exceeds_budget": True, "webgl_paired_encoded_differences_train_only": encoded_pair_differences,
            "saved_outer_target_decisions": target_saved})
        checks.append({"fold_id": job["fold_id"], "all_saved_literal_support_counts_match": len(pool),
            "saved_greedy_trace_steps_match": len(sparse["trace"]), "saved_train_model_score_and_states_match": True,
            "closed_outer_predictions_equal_saved_evaluation_rows": True})
    # Read only exact primary target sessions from already-saved raw archives.
    targets = {i: m for i, m in meta.items() if m["config_id"] in TARGETS}
    by_run = defaultdict(dict)
    for i, m in targets.items():
        by_run[m["source_ref"]][m["session_id"]] = i
    raw_targets = []
    for ref, sessions in sorted(by_run.items()):
        archive = ROOT / ref / "backend/raw_expanded_payloads.jsonl"
        for saved in lines(archive):
            if saved["session_id"] not in sessions:
                continue
            i = sessions[saved["session_id"]]
            payload = saved["canonical_received_payload"]
            assert payload["session_id"] == saved["session_id"]
            graphics = payload["web_data"]["graphics_layer"]
            screen = payload["web_data"]["screen_layer"]
            raw_targets.append({"opaque_id": i, **{k: meta[i][k] for k in
                ("triplet_id", "phase", "config_id", "environment_group_id", "source_ref", "session_id")},
                "graphics": {k: graphics[k] for k in ("webgl_vendor", "webgl_renderer", "webgl2_supported", "webgl_extensions_count", "webgl_max_texture_size")},
                "screen": {k: screen[k] for k in ("device_pixel_ratio", "screen_resolution_logical", "inner_width", "inner_height")}})
    assert Counter(r["opaque_id"] for r in raw_targets) == Counter(targets.keys()) and len(raw_targets) == 54
    raw_by_id = {r["opaque_id"]: r for r in raw_targets}
    raw_webgl_triplets = []
    for tid, trio in by_triplet.items():
        if meta[trio["attack"]]["config_id"] != WEBGL:
            continue
        before, during, after = (raw_by_id[trio[p]]["graphics"] for p in PHASES)
        changed = [k for k in during if before[k] != during[k]]
        restored = before == after
        assert sorted(changed) == ["webgl_renderer", "webgl_vendor"] and restored
        raw_webgl_triplets.append({"triplet_id": tid, "changed_graphics_fields_in_inspected_set": changed,
                                   "five_inspected_graphics_fields_restored": restored})
    definitions = read(SOURCE / "DEFINITIONS.json")
    reference_relations = [{"atom_id": a["atom_id"], "surfaces": a["surfaces"],
        "in_W0_allowlist": a["atom_id"] in definitions["single_surface_allowlists"]["app_web67"],
        "field_refs": a["provenance"].get("field_refs")}
        for a in definitions["atoms"] if a["atom_id"] in ("CAT:NW-005", "CAT:OFFDER-GPU-001")]
    assert all(not r["in_W0_allowlist"] for r in reference_relations)
    results = {"status": "DIAGNOSIS_COMPLETE", "evaluation_role": "POST_HOC_EXPOSED_DEVELOPMENT_DIAGNOSIS",
        "scope": "Step 1 only. Saved thresholds/support/trace and closed predictions; no search, refit, new model or altered-model heldout evaluation.",
        "execution_account": {"new_fit_calls": 0, "new_threshold_fit_calls": 0,
            "new_model_prediction_api_calls": 0, "new_candidate_semantic_evaluator_calls": 0,
            "diagnostic_arithmetic": "Stored thresholds reapplied to train inputs; specified DPR candidate marginal/constraint/tie calculations. These are post-hoc train explanations, not new fitted results.",
            "cumulative_fit_jobs_unchanged": execution["cumulative_fit_jobs"],
            "remaining_old_protocol_fits_unchanged": execution["remaining_research_fits"]},
        "checks": checks, "folds": evidence, "raw_target_rows": len(raw_targets),
        "webgl_raw_triplets": raw_webgl_triplets, "GPU_relations_outside_W0": reference_relations,
        "findings": {"screen": "Supported clean-safe DPR condition has positive train marginal gain; rejected by tie order then six-clause/twelve-complexity limit. No currently selected clause can be swapped for DPR without losing some train attack detections.",
                     "webgl": "Vendor/renderer changes are absent from W0 atoms. Every existing literal firing on any train WebGL attack exceeds the clean budget by itself, so increasing singleton-OR capacity alone cannot fix these train misses."}}
    assert read(PILOT / "EXECUTION.json") == execution
    return {"RESULTS.json": results, "TRAIN_CANDIDATES.json": candidate_rows,
            "SCREEN_TRACE.json": screen_trace, "RAW_TARGET_RECORDS.json": raw_targets}


def serialize(value):
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator, "value": float(value)}
    raise TypeError(type(value).__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create diagnosis files once; never overwrite.")
    args = parser.parse_args()
    outputs = diagnose()
    if args.write:
        assert not any((HERE / name).exists() for name in outputs)
        for name, value in outputs.items():
            with (HERE / name).open("x") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, default=serialize, allow_nan=False)
                stream.write("\n")
    print(json.dumps({"status": outputs["RESULTS.json"]["status"],
                      "checks": outputs["RESULTS.json"]["checks"], "wrote": args.write}, ensure_ascii=False))
