"""Read-only R02 acceptance; optional first-write saved checks, never R01 replay."""
from __future__ import annotations

import ast
from collections import Counter
import io
import json
from pathlib import Path
import subprocess
import unittest

from .build_matrix import ROOT, OLD, R01, CONFIG, REVIEW_COMMIT, contracts, read, rows, keyed, rel, write
from .fold_data import load_fold, TrainQuantiles
from .matrix import canonical_core


def validate(directory, save=False):
    out = Path(directory)
    targets = ["VALIDATION.json", "FOCUSED_CHECKS.json", "FOCUSED_TESTS.txt", "MATRIX_SCHEMA.json"]
    if save and any((out / p).exists() for p in targets):
        raise FileExistsError("Saved R02 acceptance cannot be overwritten")
    checks = []

    def check(name, fn):
        fn()
        checks.append({"check": name, "status": "PASS"})

    def require(value, detail="check failed"):
        if not value:
            raise AssertionError(detail)

    cfg, candidates, roles, splits, binding = contracts()
    manifest = read(out / "COLUMN_MANIFEST.json")
    matrix = keyed(rows(out / "candidate_matrix.jsonl"))
    av = keyed(rows(out / "availability_matrix.jsonl"))
    core = keyed(rows(out / "core_matrix.jsonl"))
    controls = keyed(rows(out / "control_inputs.jsonl"))
    fixed = keyed(rows(out / "fixed_control_matrix.jsonl"))
    index = keyed(rows(out / "evaluation_index.jsonl"))
    atom_list = list(rows(out / "atom_records.jsonl"))
    atoms = {}
    for c in atom_list:
        key = (c["opaque_id"], c["atom_id"])
        require(key not in atoms, "duplicate atom cell")
        atoms[key] = c
    summary = read(out / "SUMMARY.json")
    check("R01_config_binding_current_not_historical_mtime_or_PENDING", lambda: require(binding["protocol_digest"] == manifest["protocol_digest"] == summary["protocol_digest"]))
    check("all_262_unique_rows_and_57_unique_columns", lambda: require(
        set(matrix) == set(av) == set(core) == set(controls) == set(fixed) == set(index) == {r["opaque_id"] for r in roles}
        and len(matrix) == 262 and len(atoms) == 262 * 57
        and manifest["candidate_columns"] == [c["atom_id"] for c in candidates]))
    check("supervised_162_descriptive_100_and_exact_R01_roles", lambda: require(
        index == keyed(roles) and Counter(r["supervised_label"] for r in index.values()) == {None:100,0:108,1:54}))

    def schema_check():
        metadata = {"opaque_id", "protocol_digest", "candidate_version"}
        for data, n, extra in ((matrix,57,{"values","states"}), (av,57,{"available","reasons","evaluation_status"}),
            (core,10,{"values","states","available","reasons","evaluation_status"}),
            (controls,104,{"values","available","reasons","evaluation_status"}),
            (fixed,53,{"values","states","available","reasons","evaluation_status"})):
            for r in data.values():
                require(set(r) == metadata | extra)
                require(r["protocol_digest"] == binding["protocol_digest"] and r["candidate_version"] == "r01-atoms-v1")
                for k in extra:
                    require(type(r[k]) is list and len(r[k]) == n)
                if "states" in extra:
                    for j, s in enumerate(r["states"]):
                        require(s in ("T", "F", "U", None))
                        require(type(r["values"][j]) in (bool,type(None)))
                        require(r["values"][j] is {"T":True,"F":False}.get(s))
        for c in atom_list:
            require(set(cfg["measurement_contract"]["atom_record"]["required"]) <= set(c))
            require(c["evaluation_status"] in {"OK","FAILED","NOT_REQUESTED"})
            require(type(c["available"]) is bool)
            if c["evaluation_status"] == "OK":
                require(c["state"] in {"T","F","U"})
                require(c["available"] == (c["state"] != "U"))
            else:
                require(c["state"] is None and c["value"] is None and not c["available"])
            require(c["value"] is {"T":True,"F":False}.get(c["state"]))
    check("matrix_schema_and_U_FAILED_NOT_REQUESTED_separation", schema_check)

    def cells_reconcile():
        for oid in matrix:
            for j,c in enumerate(candidates):
                atom = atoms[oid,c["atom_id"]]
                require(matrix[oid]["values"][j] is atom["value"] and matrix[oid]["states"][j] == atom["state"])
                require(av[oid]["available"][j] == atom["available"] and av[oid]["reasons"][j] == atom["reason"]
                        and av[oid]["evaluation_status"][j] == atom["evaluation_status"])
                if "browser67" in c["observation_surfaces"]:
                    require(atom["state"] == "U" and atom["reason"] == "MISSING_SURFACE")
                if not c["measurement"]["defined"]:
                    require(atom["evaluation_status"] == "NOT_REQUESTED")
        require(len(list(rows(out / "candidate_manifest.jsonl"))) == 57)
        for a,b in zip(rows(out / "candidate_manifest.jsonl"),candidates):
            require(all(a[k] == v for k,v in b.items()), "candidate registration changed")
    check("matrix_cells_field_states_and_all_57_registry_uses_reconcile", cells_reconcile)

    def alias_reconcile():
        saved = list(rows(out / "ALIAS_CHECKS.jsonl"))
        expected = []
        for oid in sorted(matrix):
            merged = canonical_core(candidates,{c["atom_id"]:atoms[oid,c["atom_id"]] for c in candidates})
            require(all(c["alias_check"] == "PASS" for c in merged))
            require(core[oid]["states"] == [c["state"] for c in merged])
            require(core[oid]["available"] == [c["available"] for c in merged])
            expected.extend({"opaque_id":oid,**c} for c in merged if len(c["aliases"]) > 1)
        require(saved == expected and len(saved) == 524)
    check("all_524_alias_checks_domain_availability_reason_and_deviation_polarity", alias_reconcile)

    def lineage_reconcile():
        saved_events = {}
        for line, e in enumerate(rows(OLD / "06_e1/prediction/rule_events.jsonl"),1):
            if e["method"] == "final_v3_v2" and (e["opaque_id"],"CAT:"+e["rule_id"]) in atoms:
                saved_events[line] = e
        for a in atom_list:
            lin = a["cache_lineage"]
            ref = lin["preferred_event_ref"]
            if ref:
                e = saved_events[int(ref.rsplit("=",1)[1])]
                require((a["opaque_id"],a["atom_id"]) == (e["opaque_id"],"CAT:"+e["rule_id"]))
                original = e.get("original_result") or {}
                require(a["original_outcome"] == original.get("outcome") and a["original_reason"] == original.get("reason"))
            if lin["reuse"]:
                require(ref is not None and not lin["predicate_executed"])
                require(all(lin["checks"].get(k) is True for k in ("input","catalog_parameters","implementation_version","event_identity","predicate_and_version","field_states")))
                require(lin["checks"]["measurement_domain"] == "R01_PROFILE_VALID_FROZEN_PREDICATE_SAME_ON_THIS_DOMAIN")
                require(a["relation_result"]["outcome"] == a["original_outcome"])
                candidate = next(c for c in candidates if c["atom_id"]==a["atom_id"])
                require(a["state"] == candidate["measurement"]["outcome_to_state"][a["original_outcome"]])
        require(read(out / "CACHE_LINEAGE.json")["legacy_risk_eligibility_used"] is False)
    check("preferred_original_result_input_version_domain_and_line_by_line_lineage", lineage_reconcile)

    def folds_and_loader():
        folds=read(out / "FOLD_INPUT_MANIFEST.json")["folds"]
        require(len(folds)==17)
        for f,s in zip(folds,splits):
            require(all(f[k]==v for k,v in s.items()))
            require(f["current_R02_real_fit_permissions"]==f["test_fit_permissions"]==f["descriptive_fit_permissions"]==[])
            a=load_fold(out,f["fold_id"])
            require(len(a.batch("train").records)==len(s["train"]))
            for p in ("train","outer_test","descriptive_train_side","descriptive_test_side"):
                batch=a.batch(p)
                require(all(set(r)==set(manifest["core_columns"]) for r in batch.records))
                try:
                    a.assert_fit(batch,"support")
                except PermissionError:
                    pass
                else:
                    raise AssertionError("unauthorized real fit")
        for surface in ("native84","app_web67","host26"):
            a=load_fold(out,folds[0]["fold_id"],surface)
            for row in a.batch("train").records:
                for key in row:
                    if key.startswith("CAT:"):
                        require(key in manifest["single_surface_catalog_columns"][surface])
                    else:
                        require(surface == next(s["surface"] for s in manifest["control_columns"] if s["field"] in key))
    check("17_exact_folds_test_and_descriptive_denied_and_scoped_feature_loaders", folds_and_loader)

    def controls_check():
        transforms=read(out / "TRAIN_TRANSFORM_MANIFEST.json")
        require(len(transforms["numeric_fields"])==62 and transforms["real_thresholds"]==[])
        specs=list(rows(out / "fixed_control_manifest.jsonl"))
        require(len(specs)==53)
        states=keyed(rows(out / "control_field_states.jsonl"))
        require(set(states)==set(controls))
        require(all(set(r["field_states"])=={s["field"] for s in manifest["control_columns"]} for r in states.values()))
        for oid in controls:
            for j,s in enumerate(specs):
                i=s["control_input_column"]
                require(fixed[oid]["available"][j]==controls[oid]["available"][i])
                if controls[oid]["available"][i]:
                    require(fixed[oid]["values"][j] == (controls[oid]["values"][i]==s["equals"]))
        require(transforms["support_statistics"]==transforms["rule_rankings"]=="NOT_COMPUTED")
    check("104_controls_53_fixed_atoms_62_numeric_inputs_no_real_quantile_fit", controls_check)

    def accounting():
        cs=summary["counts"]
        expected={"registered_cells":len(atoms),"available_cells":sum(c["available"] for c in atom_list),
                  "unavailable_U_cells":sum(c["state"]=="U" for c in atom_list),
                  "failed_cells":sum(c["evaluation_status"]=="FAILED" for c in atom_list),
                  "not_requested_cells":sum(c["evaluation_status"]=="NOT_REQUESTED" for c in atom_list),
                  "reused_original_cells":sum(c["cache_lineage"]["reuse"] for c in atom_list),
                  "new_predicate_calls":sum(c["cache_lineage"]["predicate_executed"] for c in atom_list)}
        require(all(cs[k]==v for k,v in expected.items()))
        require(cs["registered_cells"]==sum(cs[k] for k in ("available_cells","unavailable_U_cells","failed_cells","not_requested_cells")))
        require(len(list(rows(out / "REJECTIONS.jsonl")))==cs["registered_cells"]-cs["reused_original_cells"])
        require(summary["real_fits"]==summary["risk_predictions"]==summary["full_label_rankings"]==summary["control_thresholds_fitted"]==0)
    check("all_cell_dispositions_and_zero_real_fit_prediction_rankings",accounting)

    def history_check():
        paths=[rel(R01),rel(CONFIG),rel(OLD),"hybridguard_agent/config/paired244_rule_catalog.v3.json"]
        require(not subprocess.check_output(["git","diff",REVIEW_COMMIT,"--",*paths],cwd=ROOT))
        acceptance=read(out / "R01_EXTERNAL_ACCEPTANCE.json")
        require(acceptance["reviewed_commit"]==REVIEW_COMMIT and acceptance["acceptance_status"]=="ACCEPTED_EXTERNAL")
        require(read(out / "READ_ONLY_CHECK.json")["same_size_and_mtime_before_after"] is True)
        for name in ("matrix.py","build_matrix.py"):
            tree=ast.parse((ROOT / "hybridguard_agent/research/rule_learning" / name).read_text())
            imported=[n.module or "" for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            require(not any("runtime" in n or n.endswith(".policy") for n in imported))
            require(not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="fit" for n in ast.walk(tree)))
    check("R01_and_history_read_only_external_acceptance_separate_no_runtime_or_fit_call",history_check)
    suite=unittest.defaultTestLoader.loadTestsFromName("hybridguard_agent.tests.test_rule_learning_r02")
    log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    check("synthetic_hand_truth_original_predicate_polarity_missing_failure_and_fit_permissions",lambda:require(result.wasSuccessful(),log.getvalue()))
    validation={"schema_version":"r02-validation-v1","status":"PASS","scope":"FIXED_MATRIX_AND_SYNTHETIC_ISOLATION_ONLY",
                "protocol_digest":binding["protocol_digest"],"checks":checks,"checks_passed":len(checks),
                "synthetic_tests":result.testsRun,"real_fits":0,"risk_predictions":0,
                "detection_rate_or_nonempty_model_gate":False,"historical_R01_acceptance_rewritten":False}
    schema={"schema_version":"r02-matrix-schema-v1","protocol_digest":binding["protocol_digest"],
            "row_key":"opaque_id","opaque_id_is_feature":False,"column_order":"COLUMN_MANIFEST.json",
            "X_value":"candidate_matrix.jsonl:values","X_available":"availability_matrix.jsonl:available",
            "X_reason":"availability_matrix.jsonl:reasons","state_values":["T","F","U",None],
            "state_null":"FAILED or NOT_REQUESTED, distinguished by evaluation_status; never a logical U",
            "value_values":[True,False,None],"OK_U":{"value":None,"available":False},
            "boolean_metadata_and_domain":"candidate_manifest.jsonl","audit_not_inference":"atom_records.jsonl",
            "evaluation_only":"evaluation_index.jsonl","field_state_and_cache_lineage":"atom_records.jsonl",
            "feature_load_entrypoint":"fold_data.load_fold","fit_permission_entrypoint":"fold_data.FoldData.assert_fit",
            "source_alias_provenance":"source_manifest.jsonl and COLUMN_MANIFEST.json:core_definitions",
            "all_262_rows_retained":True,"scalar_controls":"control_inputs.jsonl (62 numeric inputs not thresholded)",
            "fixed_control_atoms":"fixed_control_matrix.jsonl (53 columns)","input_paths_and_phase_groups_are_features":False,
            "control_field_states":"control_field_states.jsonl"}
    if save:
        write(out / "MATRIX_SCHEMA.json",schema)
        write(out / "FOCUSED_CHECKS.json",{"static_checks":checks,"synthetic_tests":result.testsRun,"status":"PASS"})
        with (out / "FOCUSED_TESTS.txt").open("x") as f:f.write(log.getvalue())
        write(out / "VALIDATION.json",validation)
    return validation
