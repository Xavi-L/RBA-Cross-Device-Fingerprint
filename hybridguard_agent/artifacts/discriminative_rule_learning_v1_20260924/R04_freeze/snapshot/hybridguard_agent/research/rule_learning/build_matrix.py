"""R02 materialization, accounting and portable semantic/source checks."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from .matrix import VERSION, SECTIONS, extract_atom, canonical_core, control_input, mask

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923"
FROZEN = OLD / "05_freeze_r1"
STUDY = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924"
R01 = STUDY / "R01_protocol"
CONFIG = ROOT / "hybridguard_agent/config/rule_learning_v1_20260924"
REVIEW_COMMIT = "283ff801ea3cfddce231c928017185db0f34683b"
SOURCE_FILES = ["hybridguard_agent/evidence/extractor.py", "hybridguard_agent/evidence/paired244.py",
                "hybridguard_agent/rules/executor.py", "hybridguard_agent/rules/legacy_backlog.py",
                "hybridguard_agent/official_semantics/evaluator.py", "hybridguard_agent/research/mtc_p3_candidates.py",
                "hybridguard_agent/research/mtc_closed_resource.py", "hybridguard_agent/config/paired244_rule_catalog.v3.json",
                "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def keyed(items, key="opaque_id"):
    result = {}
    for item in items:
        k = item[key]
        if k in result:
            raise ValueError("DUPLICATE_ID:" + str(k))
        result[k] = item
    return result


def rel(path):
    return str(path.relative_to(ROOT))


def write(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def write_rows(path, items):
    with path.open("x", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def contracts():
    cfg = {p.stem: read(p) for p in sorted(CONFIG.glob("*.json"))}
    candidates = list(rows(R01 / "CANDIDATE_LEDGER.jsonl"))
    roles = list(rows(R01 / "DATA_ROLE_LEDGER.jsonl"))
    splits = list(rows(R01 / "SPLIT_MEMBERSHIP.jsonl"))
    canonical = json.dumps({"configs": cfg, "candidates": candidates}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    binding = read(R01 / "PROTOCOL_BINDING.json")
    assert hashlib.sha256(canonical.encode()).hexdigest() == binding["protocol_digest"]
    assert len(cfg) == 8 and len(keyed(candidates, "rule_id")) == 57 and len(keyed(roles)) == 262
    return cfg, candidates, roles, splits, binding


def protected_paths():
    # Current-run protection is separate from the historical R01 mtime record.
    paths = [ROOT / r["path"] for r in read(R01 / "READ_ONLY_BASELINE.json")["protected_inputs"]]
    paths += list(R01.iterdir()) + list(CONFIG.glob("*.json"))
    paths += [ROOT / p for p in SOURCE_FILES] + [FROZEN / "frozen_sources" / p for p in SOURCE_FILES]
    paths += [OLD / "06_e1/prediction/rule_events.jsonl", OLD / "06_e1/prediction/runtime_records.jsonl",
              FROZEN / "blind/inputs.jsonl", FROZEN / "FREEZE_MANIFEST.json"]
    return sorted(set(p for p in paths if p.is_file()))


def snapshot(paths):
    return {rel(p): {"size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns} for p in paths}


def load_materials(candidates, roles):
    source_checks = {p: (ROOT / p).read_bytes() == (FROZEN / "frozen_sources" / p).read_bytes() for p in SOURCE_FILES}
    assert all(source_checks.values()), "REVIEW_CHANGED_SOURCE_BEFORE_EXTRACTION"
    catalog = read(ROOT / SOURCE_FILES[-2])
    cat = keyed((r for r in catalog["rules"] if r["status"] == "ACTIVE"), "rule_id")
    assert set(cat) == {c["rule_id"] for c in candidates}
    sources = keyed(rows(OLD / "03_registry/source_registry.jsonl"), "rule_id")
    fields = {r["field"]: {"field": r["field"], "type": r["type"], "surface": r["surface"]}
              for r in read(OLD / "02_inputs/field_mapping.json")["fields"]}
    fields.update({p.replace("app.", "browser.", 1): {**s, "field": p.replace("app.", "browser.", 1), "surface": "browser67"}
                   for p,s in list(fields.items()) if p.startswith("app.web_data.")})
    for c in candidates:
        r = cat[c["rule_id"]]
        assert all(c[k] == r[k] for k in ("predicate", "dependencies"))
        assert c["parameters"] == r.get("parameters", {})
        assert c["predicate_version"] == r["version"]
        assert c["provenance_group"] == sources[c["rule_id"]]["provenance_group"]
        assert c["dependency_schema"] == [fields[p] for p in c["dependencies"]]
    inputs = keyed(rows(OLD / "02_inputs/inference_inputs.jsonl"))
    frozen_inputs = keyed(rows(FROZEN / "blind/inputs.jsonl"))
    assert inputs == frozen_inputs
    assert set(inputs) == {r["opaque_id"] for r in roles}
    facts = keyed(rows(OLD / "01_admission/facts_and_eligibility.jsonl"), "candidate_id")
    for r in roles:
        f = facts[r["candidate_id"]]
        label = 1 if f["eligible_detection"] else 0 if f["eligible_pre_control"] or f["eligible_post_control"] else None
        assert r["supervised_label"] == label
        assert all(r[k] == f[k] for k in ("phase", "bundle_id", "triplet_id", "environment_group_id"))
    runtime_inputs = {}
    for line, r in enumerate(rows(OLD / "06_e1/prediction/runtime_records.jsonl"), 1):
        if r["method"] != "final_v3_v2":
            continue
        oid = r["opaque_id"]
        assert oid not in runtime_inputs
        runtime = r.get("runtime")
        projection = runtime["evidence_bundle"]["projection"] if runtime else None
        # Equality is semantic JSON equality, no repeated big-file hashing.
        equal = projection == {s: inputs[oid]["payload"][s] for s in SECTIONS}
        runtime_inputs[oid] = {"input_matches": equal, "line": line, "protocol_digest": r["protocol_digest"]}
    cache, events_seen, ignored_methods = {}, 0, Counter()
    for line, event in enumerate(rows(OLD / "06_e1/prediction/rule_events.jsonl"), 1):
        events_seen += 1
        if event["method"] != "final_v3_v2":
            ignored_methods[event["method"]] += 1
            continue
        if event["rule_id"] not in cat:
            continue
        key = (event["opaque_id"], event["rule_id"])
        assert key not in cache
        event["R02_event_line"] = line
        cache[key] = event
    assert len(runtime_inputs) == 216 and len(cache) == 216 * 57
    return inputs, cat, cache, runtime_inputs, {
        "source_byte_equality": source_checks, "all_262_S02_inputs_equal_S06_frozen_inputs": True,
        "runtime_input_records": len(runtime_inputs),
        "runtime_input_equal": sum(r["input_matches"] for r in runtime_inputs.values()),
        "preferred_method": "final_v3_v2", "preferred_active_cells": len(cache),
        "ignored_other_method_event_counts": dict(ignored_methods), "event_rows_scanned": events_seen,
        "historical_large_files_hashed": 0,
    }


def fold_manifest(splits, roles, binding):
    role_by = keyed(roles)
    records = []
    for s in splits:
        parts = {k: s[k] for k in ("train", "outer_test", "descriptive_train_side", "descriptive_test_side")}
        flat = [i for ids in parts.values() for i in ids]
        assert len(flat) == len(set(flat)) == 262 and set(flat) == set(role_by)
        assert all(role_by[i]["supervised_label"] is not None for p in ("train", "outer_test") for i in parts[p])
        assert all(role_by[i]["supervised_label"] is None for p in ("descriptive_train_side", "descriptive_test_side") for i in parts[p])
        left = set(parts["train"] + parts["descriptive_train_side"])
        right = set(parts["outer_test"] + parts["descriptive_test_side"])
        for grouping in (("bundle_id",), ("bundle_id", "triplet_id")):
            assert not {tuple(role_by[i][k] for k in grouping) for i in left} & {tuple(role_by[i][k] for k in grouping) for i in right}
        if s["split_id"] == "LOEO-v1":
            assert not {role_by[i]["environment_group_id"] for i in left} & {role_by[i]["environment_group_id"] for i in right}
        records.append({**s, "protocol_digest": binding["protocol_digest"], "model_id": "NOT_FITTED",
                        "fixed_current_sample_cache": "PERMITTED_ALL_PARTITIONS_LABEL_INDEPENDENT",
                        "current_R02_real_fit_permissions": [],
                        "later_authorized_fit_partition": "train",
                        "test_fit_permissions": [], "descriptive_fit_permissions": [],
                        "learned_transform_test_access": "ONLY_AFTER_OWN_TRAIN_FIT_AND_FREEZE",
                        "data_dependent_operations": ["numeric_thresholds", "support", "ranking", "polarity_selection", "combination_selection", "pruning"]})
    return {"schema_version": "r02-fold-input-manifest-v1", "folds": records, "fold_count": len(records)}


def build(out):
    out = Path(out)
    if out.exists():
        raise FileExistsError("R02 output must be a new directory; saved acceptance is never overwritten")
    cfg, candidates, roles, splits, binding = contracts()
    subprocess.run(["git", "merge-base", "--is-ancestor", REVIEW_COMMIT, "HEAD"], cwd=ROOT, check=True)
    review_paths = ["RESEARCH_MAINLINE.md", "deliverables/formal_experiment_execution_plan/EXECUTION_PLAN.md",
                    rel(CONFIG), rel(R01), *SOURCE_FILES]
    diff = subprocess.check_output(["git", "diff", REVIEW_COMMIT, "--", *review_paths], cwd=ROOT, text=True)
    assert not diff, "REVIEW_IMPACTING_DIFF_BEFORE_BUILD"
    protected = protected_paths()
    before = snapshot(protected)
    inputs, catalog, cache, runtime_inputs, material_checks = load_materials(candidates, roles)
    out.mkdir(parents=True)
    write(out / "R01_EXTERNAL_ACCEPTANCE.json", {
        "event": "R01_EXTERNAL_REVIEW_ACCEPTED", "date": "2026-09-24", "reviewed_commit": REVIEW_COMMIT,
        "authority": "User: R01 外部验收通过。执行 R02：状态感知关系矩阵与泄漏隔离。",
        "original_validation_ref": rel(R01 / "VALIDATION.json"), "original_validation_modified": False,
        "original_execution_user_acceptance": "PENDING_AT_R01_EXECUTION_TIME",
        "acceptance_status": "ACCEPTED_EXTERNAL", "authorization": "R02_ONLY_NO_REAL_FIT_RISK_PREDICTION_R03_OR_GIT_DELIVERY"})
    common = {k: binding[k] for k in ("study_version", "protocol_digest", "candidate_version", "input_manifest_ref")}
    common.update(extraction_version=VERSION, split_id="NOT_APPLICABLE_FIXED_SAMPLE_CACHE", fold_id="NOT_APPLICABLE", model_id="NOT_FITTED")
    write(out / "BINDING_REVIEW.json", {**common, "reviewed_commit": REVIEW_COMMIT,
          "actual_HEAD": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
          "impacting_diff": [], "R01_config_binding": "PASS", "R01_candidate_role_source_member_checks": "PASS",
          "historical_mtime_check": "NOT_REPLAYED_EXECUTION_TIME_ONLY",
          "historical_PENDING_acceptance_check": "NOT_REPLAYED_SUPERSEDED_BY_EXTERNAL_EVENT", **material_checks})
    candidate_columns = [c["atom_id"] for c in candidates]
    control_specs = read(R01 / "SINGLE_SURFACE_FIELDS.json")["fields"]
    fixed_control_columns = []
    for i, spec in enumerate(control_specs):
        enc = spec["encoder"]
        categories = [True] if enc == "BOOL_EQ_TRUE" else cfg["candidate_grammar"]["new_encoder"]["string_parsers"][enc.lower()]["categories"] if enc in {"UA_CLASS", "PLATFORM_CLASS"} else []
        for category in categories:
            fixed_control_columns.append({"atom_id": "CONTROL:" + spec["field"] + ":EQ:" + str(category),
                "field": spec["field"], "surface": spec["surface"], "encoder": enc, "equals": category,
                "control_input_column": i, "provenance_group": "PROJECT_CONTROL_NOT_E_Ou_H_C",
                "fit_required": False, "predicate_version": "r01-fixed-control-equality-v1"})
    matrix, availability, atoms, canonical, controls, aliases, fixed_controls, control_states = [], [], [], [], [], [], [], []
    counters, rejections = Counter(), []
    input_manifest = keyed(rows(OLD / "02_inputs/input_manifest.jsonl"))
    for oid, inp in sorted(inputs.items()):
        cells = []
        for c in candidates:
            event = cache.get((oid, c["rule_id"]))
            runtime = runtime_inputs.get(oid)
            proof = {"input": bool(runtime and runtime["input_matches"] and event and runtime["protocol_digest"] == event["protocol_digest"]),
                     "catalog_parameters": True, "implementation_version": True}
            cell = extract_atom(c, catalog[c["rule_id"]], inp["payload"], event, proof)
            cell.update(opaque_id=oid)
            cell["cache_lineage"].update(
                preferred_event_ref=rel(OLD / "06_e1/prediction/rule_events.jsonl") + "#line=" + str(event["R02_event_line"]) if event else None,
                original_input_ref=rel(OLD / "02_inputs") + "/" + input_manifest[oid]["input_ref"],
                runtime_record_line=runtime["line"] if runtime else None,
                saved_original_outcome=event["original_outcome"] if event else None,
                saved_original_reason=event["original_result"].get("reason") if event and event.get("original_result") else None)
            counters["registered_cells"] += 1
            counters["available_cells"] += cell["available"]
            counters["unavailable_U_cells"] += cell["state"] == "U"
            counters["failed_cells"] += cell["evaluation_status"] == "FAILED"
            counters["not_requested_cells"] += cell["evaluation_status"] == "NOT_REQUESTED"
            counters["reused_original_cells"] += cell["cache_lineage"]["reuse"]
            counters["new_predicate_calls"] += cell["cache_lineage"]["predicate_executed"]
            counters["availability_only_extractions"] += cell["cache_lineage"].get("extraction_action") == "R01_AVAILABILITY_ONLY_NO_PREDICATE_RUN"
            counters["missing_preferred_cache_cells"] += event is None
            counters["cached_unexecuted_cells"] += cell["cache_lineage"]["cache_observation"] == "UNEXECUTED"
            counters["cache_contract_mismatch_cells"] += cell["cache_lineage"].get("pre_measurement_cache_status") == "CONTRACT_MISMATCH"
            if not cell["cache_lineage"]["reuse"]:
                rejections.append({"opaque_id": oid, "atom_id": c["atom_id"], "cache_status": cell["cache_lineage"]["status"],
                                   "evaluation_status": cell["evaluation_status"], "reason": cell["reason"],
                                   "extraction_action": cell["cache_lineage"].get("extraction_action", "NOT_REQUESTED"),
                                   "row_dropped": False})
            cells.append(cell)
        by_atom = {c["atom_id"]: c for c in cells}
        core = canonical_core(candidates, by_atom)
        aliases.extend({"opaque_id": oid, **c} for c in core if len(c["aliases"]) > 1)
        canonical.append({"opaque_id": oid, "values": [c["value"] for c in core], "states": [c["state"] for c in core],
                          "available": [c["available"] for c in core], "reasons": [c["reason"] for c in core],
                          "evaluation_status": [c["evaluation_status"] for c in core]})
        matrix.append({"opaque_id": oid, "values": [c["value"] for c in cells], "states": [c["state"] for c in cells]})
        availability.append({"opaque_id": oid, "available": [c["available"] for c in cells], "reasons": [c["reason"] for c in cells],
                             "evaluation_status": [c["evaluation_status"] for c in cells]})
        atoms.extend(cells)
        control_cells = [control_input(mask(inp["payload"], [s["surface"]]), s) for s in control_specs]
        control_states.append({"opaque_id": oid, "field_states": {s["field"]: c.get("field_state", {}) for s,c in zip(control_specs,control_cells)}})
        controls.append({"opaque_id": oid, "values": [c["value"] for c in control_cells], "available": [c["available"] for c in control_cells],
                         "reasons": [c["reason"] for c in control_cells], "evaluation_status": [c["evaluation_status"] for c in control_cells]})
        fixed = []
        for spec in fixed_control_columns:
            cell = control_cells[spec["control_input_column"]]
            state = None if cell["evaluation_status"] == "FAILED" else "U" if not cell["available"] else "T" if cell["value"] == spec["equals"] else "F"
            fixed.append({**cell, "state": state, "value": {"T": True, "F": False}.get(state)})
        fixed_controls.append({"opaque_id": oid, **{name: [c[key] for c in fixed] for name,key in
            (("values","value"),("states","state"),("available","available"),("reasons","reason"),("evaluation_status","evaluation_status"))}})
    row_binding = {k: common[k] for k in ("protocol_digest", "candidate_version")}
    def bound(items):
        return ({**row_binding, **r} for r in items)
    write_rows(out / "candidate_matrix.jsonl", bound(matrix))
    write_rows(out / "availability_matrix.jsonl", bound(availability))
    write_rows(out / "atom_records.jsonl", bound(atoms))
    write_rows(out / "core_matrix.jsonl", bound(canonical))
    write_rows(out / "control_inputs.jsonl", bound(controls))
    write_rows(out / "control_field_states.jsonl", bound(control_states))
    write_rows(out / "fixed_control_matrix.jsonl", bound(fixed_controls))
    write_rows(out / "fixed_control_manifest.jsonl", fixed_control_columns)
    write(out / "TRAIN_TRANSFORM_MANIFEST.json", {**common, "status": "NOT_REQUESTED_REAL_FIT_NOT_AUTHORIZED",
        "numeric_fields": [s for s in control_specs if "TRAIN_QUANTILE" in s["encoder"]],
        "quantiles": [0.25, 0.5, 0.75], "real_thresholds": [], "support_statistics": "NOT_COMPUTED",
        "rule_rankings": "NOT_COMPUTED", "polarity_or_combination_selection": "NOT_COMPUTED", "pruning": "NOT_COMPUTED",
        "fit_interface": "hybridguard_agent.research.rule_learning.fold_data.FoldData.assert_fit",
        "synthetic_quantile_interface": "hybridguard_agent.research.rule_learning.fold_data.TrainQuantiles"})
    write_rows(out / "ALIAS_CHECKS.jsonl", aliases)
    write_rows(out / "candidate_manifest.jsonl", ({**c, **common} for c in candidates))
    write_rows(out / "evaluation_index.jsonl", roles)
    write_rows(out / "row_manifest.jsonl", ({"opaque_id": oid, "row_index": i,
               "input_ref": input_manifest[oid]["input_ref"], "input_status": input_manifest[oid]["status"],
               "evaluation_ref": "evaluation_index.jsonl#opaque_id=" + oid} for i, oid in enumerate(sorted(inputs))))
    write_rows(out / "source_manifest.jsonl", ({"atom_id": c["atom_id"], "rule_id": c["rule_id"],
        "source_groups": [c["provenance_group"]], "semantic_origin": c["semantic_origin"],
        "predicate": c["predicate"], "predicate_version": c["predicate_version"], "parameters": c["parameters"],
        "implementation_ref": c["implementation_ref"], "source_urls": c["source_urls"],
        "catalog_ref": SOURCE_FILES[-2], "R01_ledger_ref": rel(R01 / "CANDIDATE_LEDGER.jsonl")} for c in candidates))
    write_rows(out / "REJECTIONS.jsonl", rejections)
    column_manifest = {**common, "candidate_columns": candidate_columns, "core_columns": [c["atom_id"] for c in core],
                       "core_definitions": [{k: c[k] for k in ("atom_id", "canonical_rule_id", "aliases", "source_groups")} for c in core],
                       "single_surface_catalog_columns": {s: [c["atom_id"] for c in candidates if c["candidate_use"]["single_surface_control"] and c["observation_surfaces"] == [s]] for s in ("native84", "app_web67", "host26")},
                       "control_columns": control_specs, "numeric_controls": "RAW_CURRENT_SAMPLE_VALUES_ONLY_THRESHOLDS_NOT_FITTED"}
    column_manifest["fixed_control_columns"] = [r["atom_id"] for r in fixed_control_columns]
    write(out / "COLUMN_MANIFEST.json", column_manifest)
    write(out / "FOLD_INPUT_MANIFEST.json", fold_manifest(splits, roles, binding))
    counts = dict(counters)
    coverage = {}
    for name, idxs in {"core_12_original": [i for i,c in enumerate(candidates) if c["candidate_use"]["core"] and c["candidate_use"]["selectable_on_App177"]],
                       "browser_dependent_9": [i for i,c in enumerate(candidates) if "browser67" in c["observation_surfaces"]],
                       **{"catalog_"+s: [candidate_columns.index(a) for a in ids] for s,ids in column_manifest["single_surface_catalog_columns"].items()}}.items():
        available = sum(r["available"][i] for r in availability for i in idxs)
        coverage[name] = {"columns": len(idxs), "available": available, "expected": 262*len(idxs), "ratio": available/(262*len(idxs)) if idxs else None}
    coverage["core_10_canonical"] = {"columns": 10, "available": sum(sum(r["available"]) for r in canonical), "expected": 2620}
    coverage["core_10_canonical"]["ratio"] = coverage["core_10_canonical"]["available"] / 2620
    for s in ("native84", "app_web67", "host26"):
        ids = [i for i,c in enumerate(control_specs) if c["surface"] == s]
        available = sum(r["available"][i] for r in controls for i in ids)
        coverage["control_inputs_"+s] = {"columns": len(ids), "available": available, "expected": 262*len(ids), "ratio": available/(262*len(ids))}
        fixed_ids = [i for i,c in enumerate(fixed_control_columns) if c["surface"] == s]
        fixed_available = sum(r["available"][i] for r in fixed_controls for i in fixed_ids)
        coverage["fixed_control_"+s] = {"columns": len(fixed_ids), "available": fixed_available,
            "expected": 262*len(fixed_ids), "ratio": fixed_available/(262*len(fixed_ids)) if fixed_ids else None}
    summary = {**common, "rows": 262, "registered_candidates": 57, "supervised_rows": 162, "descriptive_rows": 100,
               "cohorts": dict(Counter(r["cohort"] for r in roles)), "counts": counts, "coverage": coverage,
               "coverage_scope": "POST_HOC_DESCRIPTIVE_AVAILABILITY_ONLY_NO_LABEL_RANKING_OR_RULE_FILTER",
               "alias_cells_checked": len(aliases), "alias_conflicts": sum(r["alias_check"] != "PASS" for r in aliases),
               "real_fits": 0, "risk_predictions": 0, "full_label_rankings": 0, "control_thresholds_fitted": 0,
               "R03_started": False, "old_S07_executed": False}
    summary["coverage_by_role"] = {}
    for role, supervised in (("SUPERVISED", True), ("DESCRIPTIVE", False)):
        selected = {r["opaque_id"] for r in roles if (r["supervised_label"] is not None) == supervised}
        records = [r for r in canonical if r["opaque_id"] in selected]
        available = sum(sum(r["available"]) for r in records)
        summary["coverage_by_role"][role] = {"rows": len(selected), "core_available": available,
            "core_expected": len(selected)*10, "core_ratio": available/(len(selected)*10),
            "all_104_control_inputs_available": sum(sum(r["available"]) for r in controls if r["opaque_id"] in selected),
            "control_inputs_expected": len(selected)*104}
    write(out / "CACHE_LINEAGE.json", {**common, **material_checks, "counts": counts, "per_cell_ref": "atom_records.jsonl",
         "cache_status_counts": dict(Counter(c["cache_lineage"]["status"] for c in atoms)),
         "measurement_unavailability_reasons": dict(Counter(c["reason"] for c in atoms if c["state"] == "U")),
         "reuse_rule": "original_result only after input/catalog/predicate/version/field-state and per-cell R01 domain checks",
         "legacy_risk_eligibility_used": False, "legacy_relation_gate_used": False,
         "new_extraction": "same frozen primitive under versioned R01 measurement domain; no new predicate or original-result overwrite"})
    write(out / "SUMMARY.json", summary)
    after = snapshot(protected)
    assert before == after, "HISTORICAL_INPUT_CHANGED_DURING_R02"
    write(out / "READ_ONLY_CHECK.json", {"status": "PASS", "scope": "CURRENT_R02_RUN_ONLY", "historical_R01_mtime_assertions_replayed": False,
         "same_size_and_mtime_before_after": True, "protected_files": before, "large_file_hashing": False,
         "configuration_and_source_semantics_ref": "BINDING_REVIEW.json"})
    return summary
