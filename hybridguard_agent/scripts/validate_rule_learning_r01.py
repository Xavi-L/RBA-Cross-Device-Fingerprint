#!/usr/bin/env python3
"""Focused R01 static joins and synthetic contract checks; no detector import.

Default is read-only. --write creates fresh VALIDATION/FOCUSED_CHECKS files only.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import copy
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923"
K = ROOT / "hybridguard_agent/config/rule_learning_v1_20260924"
L = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol"


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def parse(text):
    def reject(value):
        raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(text, object_pairs_hook=unique_keys, parse_constant=reject)


def read(path):
    return parse(path.read_text(encoding="utf-8"))


def lines(path):
    with path.open(encoding="utf-8") as stream:
        return [parse(line) for line in stream if line.strip()]


def schema(value, spec, loc="$"):
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "null": type(None)}
    kind = spec.get("type")
    if kind == "number":
        assert type(value) in (int, float) and math.isfinite(value), loc + ": number"
    elif kind:
        assert type(value) is types[kind], loc + ": " + kind
    if "enum" in spec:
        assert any(type(value) is type(v) and value == v for v in spec["enum"]), loc + ": enum"
    if "minimum" in spec:
        assert value >= spec["minimum"], loc + ": minimum"
    if "maximum" in spec:
        assert value <= spec["maximum"], loc + ": maximum"
    if type(value) is dict:
        assert set(spec.get("required", [])) <= value.keys(), loc + ": required"
        for key, child in spec.get("properties", {}).items():
            if key in value:
                schema(value[key], child, loc + "." + key)
    if type(value) is list:
        assert len(value) >= spec.get("minItems", 0), loc + ": minItems"
        for i, item in enumerate(value):
            schema(item, spec.get("items", {}), loc + "[%d]" % i)


def validate(write=False):
    checks = []

    def check(name, fn):
        fn()
        checks.append({"check": name, "status": "PASS"})

    def require(condition, message="assertion failed"):
        assert condition, message

    schemas = read(L / "CONTRACT_SCHEMA.json")
    cfg = {name: read(K / (name + ".json")) for name in schemas["documents"]}
    cand = lines(L / "CANDIDATE_LEDGER.jsonl")
    data = lines(L / "DATA_ROLE_LEDGER.jsonl")
    splits = lines(L / "SPLIT_MEMBERSHIP.jsonl")
    facts = {r["candidate_id"]: r for r in lines(OLD / "01_admission/facts_and_eligibility.jsonl")}
    index = {r["opaque_id"]: r for r in lines(OLD / "02_inputs/evaluation_index.jsonl")}
    source = {r["rule_id"]: r for r in lines(OLD / "03_registry/source_registry.jsonl")}
    catalog = {r["rule_id"]: r for r in read(ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json")["rules"] if r["status"] == "ACTIVE"}
    cby = {r["rule_id"]: r for r in cand}
    dby = {r["opaque_id"]: r for r in data}
    fm = read(OLD / "02_inputs/field_mapping.json")
    fields = {r["field"]: {"type": r["type"], "surface": r["surface"]} for r in fm["fields"]}
    fields.update({p.replace("app.", "browser.", 1): {"type": v["type"], "surface": "browser67"} for p, v in list(fields.items()) if p.startswith("app.web_data.")})
    for name, doc in cfg.items():
        check("schema_" + name, lambda n=name, d=doc: schema(d, schemas["documents"][n]))
    for name, rows in [("candidate_row", cand), ("data_row", data), ("split_row", splits)]:
        check("schema_" + name, lambda n=name, rs=rows: [schema(r, schemas[n]) for r in rs])
    check("all_57_ACTIVE_unique_and_sources", lambda: require(len(cand) == len(cby) == 57 and set(cby) == set(catalog) == set(source) and Counter(r["provenance_group"] for r in cand) == {"E": 23, "O_u": 9, "H": 14, "C": 11}))

    def candidate_reconcile():
        for r in cand:
            old, src = catalog[r["rule_id"]], source[r["rule_id"]]
            assert r["predicate"] == old["predicate"] and r["parameters"] == old.get("parameters", {})
            assert r["predicate_version"] == old["version"] and r["dependencies"] == old["dependencies"]
            assert r["provenance_group"] == src["provenance_group"] and r["original_family"] == old["evidence_family"]
            assert r["decision_family"] == src["decision_family"] and r["known_counterexamples"] == src["known_counterexamples"]
            assert r["measurement"]["profile"] in cfg["measurement_contract"]["profiles"]
            assert r["dependency_schema"] == [{"field": f, **fields[f]} for f in r["dependencies"]]
            assert r["candidate_use"]["inclusion_or_exclusion_reason"]
            assert r["measurement"]["outcome_to_state"]["UNKNOWN"] == "U"
            assert r["measurement"]["outcome_to_state"]["NOT_APPLICABLE"] == "U"
            assert not r["legacy_role_used_for_inclusion"]
            if r["candidate_use"]["core"]:
                assert len(r["observation_surfaces"]) >= 2
                assert r["relation_type"] == "CROSS_SURFACE_RELATION"
                assert r["candidate_use"]["allowed_polarities"] == ["POSITIVE", "NEGATIVE"]
            if "browser67" in r["observation_surfaces"]:
                assert not r["candidate_use"]["selectable_on_App177"]
        app_core = [r for r in cand if r["candidate_use"]["core"] and r["candidate_use"]["selectable_on_App177"]]
        assert len(app_core) == 12 and len({r["normalized_identity"] for r in app_core}) == 10
        assert any(r["legacy_S03R_role"] == "observation_only" for r in app_core)
        assert not cby["OFFDER-GPU-001"]["candidate_use"]["core"]
    check("candidate_predicate_source_family_fields_and_open_eligibility", candidate_reconcile)

    def fact_reconcile():
        assert len(data) == len(dby) == len(facts) == len(index) == 262
        assert {r["candidate_id"] for r in data} == set(facts)
        for r in data:
            f = facts[r["candidate_id"]]
            expected = 1 if f["eligible_detection"] else 0 if f["eligible_pre_control"] or f["eligible_post_control"] else None
            assert r["supervised_label"] == expected
            for key in ["environment_group_id", "bundle_id", "triplet_id", "phase", "session_id", "eligible_detection", "eligible_pre_control", "eligible_post_control", "eligible_temporal_control"]:
                assert r[key] == f[key]
            assert r["evidence_grade"] == f["evidence_grade"] and r["fact_status"] == f["adjudication_status"]
            assert r["no_intervention_status"] == f["no_intervention"]["status"]
            assert r["config_id"] == index[r["opaque_id"]]["config_id"]
            assert r["mechanism_id"] is None
            if expected is None:
                assert r["fit_permission"] == "DENIED" and r["data_role"] == "DESCRIPTIVE_ONLY"
            if r["cohort"] == "temporal_control_unknown":
                assert r["no_intervention_status"] == "UNKNOWN" and expected is None
        assert Counter(r["supervised_label"] for r in data) == {None: 100, 0: 108, 1: 54}
        assert Counter(r["cohort"] for r in data) == {"admitted_attack_triplet": 162, "temporal_control_unknown": 54, "lower_evidence_attack": 45, "incomplete_attempt": 1}
    check("all_262_roles_match_S01_no_UNKNOWN_promotion", fact_reconcile)

    def material_reconcile():
        flow = lines(L / "MATERIAL_FLOW.jsonl")
        old_inventory = lines(OLD / "01_admission/material_inventory.jsonl")
        assert len(flow) == len(old_inventory) == 31
        assert sum(r["source_stage_count"] for r in flow) == 262
        assert sum(r["source_stage_count"] == 0 for r in flow) == 1
        for row in flow:
            assert row["source_stage_count"] == sum(r["bundle_id"] == row["bundle_id"] for r in data)
        mtc = read(L / "MTC_ROLE_DECLARATION.json")
        assert not mtc["supervised_fit_allowed"] and mtc["current_reserved_status"] == "CONSUMED_IN_P6"
        assert len(lines(ROOT / mtc["population_manifest"])) == mtc["saved_counts"]["observations"] == 1699
    check("all_bundles_empty_attempt_and_MTC_reference_accounted", material_reconcile)

    def splits_reconcile():
        assert Counter(s["split_id"] for s in splits) == {"LOEO-v1": 3, "LOCO-v1": 14}
        expected = set(dby)
        for s in splits:
            sides = [s[k] for k in ["train", "outer_test", "descriptive_train_side", "descriptive_test_side"]]
            flat = sum(sides, [])
            assert len(flat) == len(set(flat)) == len(expected) and set(flat) == expected
            train_all = set(s["train"] + s["descriptive_train_side"])
            test_all = set(s["outer_test"] + s["descriptive_test_side"])
            assert all(dby[i]["supervised_label"] is not None for i in s["train"] + s["outer_test"])
            assert all(dby[i]["supervised_label"] is None for i in s["descriptive_train_side"] + s["descriptive_test_side"])
            assert all(dby[i][s["target_field"]] == s["target"] for i in test_all)
            assert all(dby[i][s["target_field"]] != s["target"] for i in train_all)
            for grouping in ["triplet_id", "bundle_id", "session_id"]:
                assert {dby[i][grouping] for i in train_all}.isdisjoint({dby[i][grouping] for i in test_all})
            # Reuse saved association/digest metadata; no raw file hashing.
            for side_a, side_b in [(train_all, test_all)]:
                saved_keys = lambda ids: {facts[dby[i]["candidate_id"]]["payload_binding"]["actual_payload_digest"] for i in ids}
                assert saved_keys(side_a).isdisjoint(saved_keys(side_b))
            if s["split_id"] == "LOEO-v1":
                for grouping in ["environment_group_id", "collector_install_id"]:
                    assert {dby[i][grouping] for i in train_all}.isdisjoint({dby[i][grouping] for i in test_all})
        for track in ["LOEO-v1", "LOCO-v1"]:
            test_ids = [i for s in splits if s["split_id"] == track for i in s["outer_test"]]
            assert len(test_ids) == len(set(test_ids)) == 162
    check("17_folds_all_members_triplets_bundles_sessions_saved_duplicates", splits_reconcile)

    def support_reconcile():
        with (L / "GROUP_SUPPORT.csv").open(encoding="utf-8", newline="") as stream:
            support = list(csv.DictReader(stream))
        assert sum(int(r["stages"]) for r in support) == 262
        assert sum(int(r["eligible_attack"]) for r in support) == 54
        assert sum(int(r["eligible_pre"]) for r in support) == 54
        assert sum(int(r["eligible_post"]) for r in support) == 54
        manifests = read(L / "FOLD_MANIFEST.json")
        byfold = {s["fold_id"]: s for s in splits}
        for fold in manifests:
            assert fold["status"] == "FEASIBLE_FIXED_PARAMETERS"
            for side in ["train", "outer_test"]:
                rows = [dby[i] for i in byfold[fold["fold_id"]][side]]
                saved = fold["sides"][side]
                assert saved["stages"] == len(rows)
                assert saved["attack"] == sum(r["supervised_label"] == 1 for r in rows)
                assert saved["clean"] == sum(r["supervised_label"] == 0 for r in rows)
                assert saved["pre"] == saved["post"] == saved["attack"]
                assert saved["environments"] == sorted({r["environment_group_id"] for r in rows})
                assert saved["configurations"] == sorted({r["config_id"] for r in rows})
                for op in cfg["learning_search_space"]["operating_points"]:
                    assert saved["clean_budgets"][op["id"]] == math.floor(op["alpha"] * saved["clean"] + 1e-10)
        loeo = [f for f in manifests if f["split_id"] == "LOEO-v1"]
        assert [f["sides"]["train"]["clean"] for f in loeo] == [90, 96, 30]
        assert [f["sides"]["outer_test"]["attack"] for f in loeo] == [9, 6, 39]
    check("support_fold_labels_configurations_environment_and_integer_budgets", support_reconcile)

    def search_contract():
        search = cfg["learning_search_space"]
        assert [p["alpha"] for p in search["operating_points"]] == [0.0, 0.05, 0.1]
        assert search["objective"]["lambda"] == 0.005 and search["constraints"]["min_decision_coverage"] == 0.8
        assert search["support"]["statistics_scope"] == "TRAIN_FOLD_ONLY"
        assert not search["parameter_search"]["inner_hyperparameter_search"] and not search["choose_operating_point_on_test"]
        assert search["parameter_search"]["seed"] == cfg["split_policy"]["seed"] == 20260924
        assert not search["algorithms"]["COLUMN_GENERATION"]["enabled"]
        jobs = sum(e.get("fit_job_count", e.get("fit_job_count_max", 0)) for e in cfg["experiment_matrix"]["experiments"])
        assert jobs == cfg["experiment_matrix"]["total_planned_fit_jobs_upper_bound"] == 75
        assert jobs <= search["total_budget"]["max_fit_jobs"]
        for name in ["GREEDY_OR", "FINITE_IP_OR", "FINITE_IP_DNF2"]:
            assert search["algorithms"][name]["time_limit_seconds_per_fit"] > 0
        assert not cfg["study_protocol"]["learning"]["legacy_role_is_eligibility_filter"]
        assert cfg["split_policy"]["primary"]["test_data_fit_permissions"] == []
        assert cfg["split_policy"]["mechanism"]["mechanism_id"] is None
    check("finite_objective_search_seed_time_budget_weights_and_failure_routes", search_contract)

    def primitives():
        single = read(L / "SINGLE_SURFACE_FIELDS.json")
        assert not single["thresholds_fitted"]
        assert len({r["field"] for r in single["fields"]}) == len(single["fields"])
        count = Counter()
        for r in single["fields"]:
            assert r["field"] in fields and r["surface"] == fields[r["field"]]["surface"]
            assert r["field"] not in single["excluded_numeric_fields"]
            count[r["surface"]] += {"BOOL_EQ_TRUE": 2, "TRAIN_QUANTILE_LE": 6, "UA_CLASS": 8, "PLATFORM_CLASS": 6, "LIST_LENGTH_TRAIN_QUANTILE": 6}[r["encoder"]]
        for surf, n in count.items():
            old_literals = 2 * sum(r["candidate_use"]["single_surface_control"] and r["observation_surfaces"] == [surf] for r in cand)
            assert n + old_literals <= 512
        assert set(count) == {"native84", "host26", "app_web67"}
    check("single_surface_controls_finite_registered_fields_no_global_fit", primitives)

    def synthetic():
        logic = cfg["measurement_contract"]["logic"]
        for a, b in itertools.product("TFU", repeat=2):
            expected_and = "F" if "F" in (a, b) else "T" if a == b == "T" else "U"
            expected_or = "T" if "T" in (a, b) else "F" if a == b == "F" else "U"
            assert logic["AND"][a + b] == expected_and
            assert logic["OR"][a + b] == expected_or
        assert logic["NOT"] == {"T": "F", "F": "T", "U": "U"}
        assert cby["NW-002"]["measurement"]["outcome_to_state"]["COUNTEREXAMPLE"] == "T"
        assert cby["OFFDER-OS-001"]["measurement"]["outcome_to_state"]["COUNTEREXAMPLE"] == "F"
        assert cby["P3-UA-DEFAULT"]["measurement"]["outcome_to_state"]["MATCH"] == "T"
        assert cby["NVW-005"]["measurement"]["outcome_to_state"]["CONTEXT_OBSERVED"] == "T"
        assert cby["NVW-004"]["measurement"]["outcome_to_state"]["CONTEXT_OBSERVED"] == "NO_BOOLEAN_ATOM"
        decisions = cfg["measurement_contract"]["decision"]
        assert len({decisions[k] for k in ["T", "F", "U", "empty_model", "any_selected_atom_execution_failed"]}) == 5
        def decision_from_synthetic_states(states, failed=False):
            if failed:
                return decisions["any_selected_atom_execution_failed"]
            if not states:
                return decisions["empty_model"]
            state = states[0]
            for value in states[1:]:
                state = logic["OR"][state + value]
            return decisions[state]
        assert decision_from_synthetic_states(["F", "F"]) == "NO_ALERT"
        assert decision_from_synthetic_states(["U", "U"]) == "INSUFFICIENT_EVIDENCE"
        assert decision_from_synthetic_states(["F", "U"]) == "INSUFFICIENT_EVIDENCE"
        assert decision_from_synthetic_states([]) == "EMPTY_MODEL"
        assert decision_from_synthetic_states(["T", "U"]) == "MANIPULATION_ALERT"
        assert decision_from_synthetic_states(["T"], failed=True) == "FAILED"
        assert logic["NOT"][cby["P3-UA-DEFAULT"]["measurement"]["outcome_to_state"]["NOT_APPLICABLE"]] == "U"
        # Hand-computed synthetic set-union counterexample: each rule's one FP
        # fits a 1/4 budget, but their disjoint union (2/4) does not.
        assert len({"c1"} | {"c2"}) > math.floor(0.25 * 4)
        # Precision on decided rows must not conceal abstention/failure.
        expected_clean, fp, decided, unknown, failed = 4, 1, 2, 1, 1
        assert fp / expected_clean == 0.25 and fp / decided == 0.5
        assert (fp + unknown + failed) / expected_clean == 0.75
    check("synthetic_TFU_18_pairs_negation_polarity_context_union_denominators", synthetic)

    def negative_probes():
        bad = copy.deepcopy(cfg["learning_search_space"])
        bad["operating_points"][0]["alpha"] = "0.05"
        for value, spec in [(bad, schemas["documents"]["learning_search_space"]), ({**data[0], "supervised_label": True}, schemas["data_row"]), ({**splits[0], "split_id": "RANDOM_STAGE"}, schemas["split_row"])]:
            try:
                schema(value, spec)
            except AssertionError:
                continue
            raise AssertionError("invalid schema fixture accepted")
        for text in ['{"x":1,"x":2}', '{"x":NaN}']:
            try:
                parse(text)
            except ValueError:
                continue
            raise AssertionError("invalid JSON accepted")
    check("negative_schema_type_enum_duplicate_key_and_nonfinite_probes", negative_probes)

    def figure_metric_consistency():
        metrics = cfg["metric_spec"]
        metric_ids = {r["id"] for r in metrics["metrics"]}
        for fig in cfg["figure_spec"]["figures"]:
            assert set(fig.get("metrics", [])) <= metric_ids | {"complexity"}
        fig3 = next(f for f in cfg["figure_spec"]["figures"] if f["id"] == "Fig3")
        assert fig3["denominators"] == {"attack": 54, "pre": 54, "post": 54, "clean": 108}
        assert not cfg["figure_spec"]["render_in_R01"]
        assert metrics["resolution"]["zero_denominator"]["value"] is None
        assert metrics["resolution"]["missing_truth"]["value"] is None
        assert metrics["stability"]["both_empty"] == "NOT_EVALUABLE"
    check("metric_figure_sample_units_denominators_and_unavailable_states", figure_metric_consistency)

    def readonly():
        baseline = read(L / "READ_ONLY_BASELINE.json")
        for r in baseline["protected_inputs"]:
            p = ROOT / r["path"]
            assert p.stat().st_size == r["size"] and p.stat().st_mtime_ns == r["mtime_ns"], r["path"]
        diff = subprocess.check_output(["git", "diff", "--name-only", "--", "hybridguard_agent/artifacts/formal_manipulation_v1_20260923", "hybridguard_agent/config/paired244_rule_catalog.v3.json", "hybridguard_agent/rules", "hybridguard_agent/evidence", "hybridguard_agent/research", "deliverables/formal_experiment_execution_plan/EXECUTION_PLAN_LEGACY_S01_S12_20260924.md", "deliverables/formal_experiment_execution_plan/EXECUTION_STATUS_LEGACY_S01_S12_20260924.json"], cwd=ROOT, text=True)
        assert not diff.strip(), diff
        for script in ["prepare_rule_learning_r01.py", "validate_rule_learning_r01.py"]:
            tree = ast.parse((ROOT / "hybridguard_agent/scripts" / script).read_text())
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            assert not any(name.startswith("hybridguard_agent") for name in imports)
        assert all(v == 0 for v in cfg["study_protocol"]["real_operations_in_R01"].values())
    check("protected_history_unchanged_no_detector_imports_zero_real_operations", readonly)

    def binding():
        canonical = json.dumps({"configs": cfg, "candidates": cand}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        assert hashlib.sha256(canonical.encode()).hexdigest() == read(L / "PROTOCOL_BINDING.json")["protocol_digest"]
    check("small_new_protocol_binding_only_no_historical_hash_scan", binding)
    def dispatch():
        path = "deliverables/formal_experiment_execution_plan/EXECUTION_STATUS.json"
        before = parse(subprocess.check_output(["git", "show", "HEAD:" + path], cwd=ROOT, text=True))
        current = read(ROOT / path)
        assert current["legacy_archive"] == before["legacy_archive"]
        assert current["preserved_evidence"] == before["preserved_evidence"]
        assert current["steps"][1:] == before["steps"][1:]
        assert current["history"][:len(before["history"])] == before["history"]
        assert current["steps"][0]["status"] == "DONE" and current["steps"][0]["user_acceptance"] == "PENDING"
        assert current["steps"][0]["protocol_digest"] == read(L / "PROTOCOL_BINDING.json")["protocol_digest"]
        assert current["scope"]["authorized_steps"] == ["R01"] and not current["scope"]["auto_advance"]
        assert current["next_authorization_step"] == "R02"
        assert all(s["status"] == "PENDING_AUTHORIZATION" and not s["authorized"] for s in current["steps"][1:])
    check("only_R01_completed_R02_pending_legacy_history_and_other_steps_preserved", dispatch)
    result = {"status": "PASS", "scope": "R01_STATIC_METADATA_AND_SYNTHETIC_CONTRACT_ONLY", "checks_passed": len(checks),
              "checks": checks, "real_fits": 0, "real_predictions": 0, "detector_calls": 0,
              "full_outcome_matrix_built": False, "candidate_effect_rankings": 0,
              "user_acceptance": "PENDING", "R02_technical_prerequisites": "READY_PENDING_USER_ACCEPTANCE_AND_AUTHORIZATION",
              "limits": ["measurement coverage and model feasibility await R02/R05", "mechanisms unverified", "no prospective confirmation", "three associated environments not independent physical devices"]}
    if write:
        for filename in ["VALIDATION.json", "FOCUSED_CHECKS.json"]:
            if (L / filename).exists():
                raise SystemExit("Refusing existing acceptance file: " + filename)
        for filename, obj in [("VALIDATION.json", result), ("FOCUSED_CHECKS.json", {"checks": checks, "synthetic_only": True, "command": "PYTHONDONTWRITEBYTECODE=1 python3 hybridguard_agent/scripts/validate_rule_learning_r01.py --write"})]:
            with (L / filename).open("x", encoding="utf-8") as stream:
                json.dump(obj, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    print(json.dumps({"status": result["status"], "checks_passed": len(checks), "real_fits": 0, "real_predictions": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    validate(parser.parse_args().write)
