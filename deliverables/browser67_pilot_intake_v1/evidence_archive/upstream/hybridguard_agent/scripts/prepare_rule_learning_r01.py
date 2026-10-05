#!/usr/bin/env python3
"""R01 metadata-only build. No detector imports, payload reads, fits or predictions.

Rebuild into a new --output directory. Existing acceptance artifacts are never
overwritten. The eight reviewed K configs are inputs, not learned parameters.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923"
K = ROOT / "hybridguard_agent/config/rule_learning_v1_20260924"
DEFAULT = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol"
N = "app.android_native_data."
A = "app.web_data."
H = "app.webview_data."
SURFACES = {N: "native84", A: "app_web67", H: "host26", "browser.web_data.": "browser67"}
CONFIGS = ["study_protocol", "candidate_grammar", "measurement_contract", "split_policy",
           "learning_search_space", "metric_spec", "experiment_matrix", "figure_spec"]
CORE = set("NW-001 NW-002 NW-005 NVW-001 NVW-002 OFFDER-OS-001 OFFDER-OS-002 OFFDER-UA-001 OFFDER-UA-002 P3-X-TIMEZONE-OFFSET P3-X-LANGUAGE P3-X-TOUCH P3-X-CORES P3-X-DPR P3-X-SCREEN-SIZE P3-SCREEN-APP P3-SCREEN-BROWSER P3-UA-REDUCED-BROWSER P3-UA-DEFAULT P3-UA-SETTINGS".split())
COLLECTOR = set("CORE-002 OFFDER-BRIDGE-001 P3-PROVIDER-PARSE P3-GPU-COPY P3-SENSOR-NAME_COUNT P3-SENSOR-VENDOR_COUNT P3-SENSOR-TYPE-COUNT P3-SENSOR-TYPE-ORDER".split())
SAME = set("NW-006 NW-007 OFFDER-TOUCH-001 P3-COLOR-APP P3-COLOR-BROWSER P3-MEM-AVAILABLE".split())
CONDITIONAL_CONTEXT = set("NVW-005 OFFDER-DEVCONFIG-001 PHYS-005 PHYS-006 SCENE-001".split())
NO_BOOLEAN = set("NVW-004 WVWEB-002 TOL-001 OFFDER-NET-001".split())
NEQ = {"NW-002", "NVW-002", "NW-006", "NW-007", "WVWEB-004"}
ALIASES = {"OFFDER-OS-001": "NW-002", "OFFDER-OS-002": "NVW-002"}

# The operator describes T, not a risk verdict. Arguments are the ordered
# catalog dependencies. No expression is evaluated on real observations here.
SEMANTICS = {
    "featureapp_bridge_only_v2": ("BOOL_TRUE", "bridge boolean is true", "boolean", "MATCH"),
    "featureapp_jsbridge_present_v1": ("BOOL_TRUE_FIXED_FEATUREAPP", "bridge boolean is true in the fixed FeatureApp projection", "boolean", "MATCH"),
    "model_build_token": ("NORMALIZED_MODEL_EQUALS_EXPLICIT_BUILD_TOKEN", "normalized Native model equals the single explicit Android model-before-Build token", "model_token", "MATCH"),
    "native_web_android_major_neq_v1": ("NEQ_PARSED_ANDROID_MAJORS", "Native Android major differs from App UA Android major", "app_android_major", "COUNTEREXAMPLE"),
    "native_webview_android_major_neq_v1": ("NEQ_PARSED_ANDROID_MAJORS", "Native Android major differs from Dalvik system agent Android major", "system_android_major", "COUNTEREXAMPLE"),
    "native_web_android_major_equal_v1": ("EQ_PARSED_ANDROID_MAJORS", "Native Android major equals App UA Android major", "app_android_major", "MATCH"),
    "native_webview_android_major_equal_v1": ("EQ_PARSED_ANDROID_MAJORS", "Native Android major equals Dalvik system agent Android major", "system_android_major", "MATCH"),
    "gpu_family": ("EQ_UNAMBIGUOUS_HARDWARE_FAMILIES", "both renderer strings identify the same single registered hardware family", "gpu_family", "MATCH"),
    "desktop_or_script_ua_surface_v1": ("DESKTOP_OR_SCRIPT_UA_OR_DESKTOP_PLATFORM", "UA class is script/desktop/headless or platform class is desktop", "ua_platform_class", "COUNTEREXAMPLE"),
    "android_host_not_desktop_or_script_surface_v1": ("ANDROID_HOST_AND_NO_EXPLICIT_DESKTOP_SCRIPT_WEB_MARKER", "interpretable Android host with no explicit desktop/headless/script UA or desktop platform marker", "host_web_class", "MATCH"),
    "mobile_ua_zero_touch_v1": ("ANDROID_MOBILE_UA_AND_TOUCH_EQ_ZERO", "Android-mobile UA and zero touch points; defined nonmobile UA is F in this legacy predicate", "ua_touch", "COUNTEREXAMPLE"),
    "mobile_ua_touch_positive_v1": ("TOUCH_GT_ZERO_GIVEN_ANDROID_MOBILE_UA", "positive touch points inside Android-mobile UA domain; nonmobile is U/NA", "ua_touch_mobile_only", "MATCH"),
    "script_user_agent_surface_v1": ("UA_CLASS_EQ_SCRIPT_CLIENT", "UA class is script_client", "ua_class", "COUNTEREXAMPLE"),
    "webview_default_runtime_ua_equal_v1": ("TRIMMED_STRING_EQUAL", "trimmed default Native WebView UA equals trimmed current JS UA", "literal_equality", "MATCH"),
    "equal": ("TYPED_SEMANTIC_EQUAL", "ordered operands are equal under frozen typed equality (list order retained)", "literal_equality", "MATCH"),
    "dimension_equal": ("SORTED_POSITIVE_DIMENSIONS_EQUAL", "orientation-normalized positive dimension pairs are equal", "dimensions", "MATCH"),
    "screen_short_side": ("CSS_SHORT_SIDE_RESIDUAL_LE_TOLERANCE", "abs(min(native dimensions)/DPR-min(Web dimensions)) <= frozen tolerance", "screen_short_side", "MATCH"),
    "browser_android_compatible": ("EQ_ANDROID_MAJOR_OUTSIDE_REDUCED_UA_DOMAIN", "Native and Browser Android majors equal outside the frozen reduction exclusion", "browser", "MATCH"),
    "provider_parse": ("PROVIDER_PARSED_MAJOR_EQUAL", "version leading integer before dot equals collected provider major", "provider", "MATCH"),
    "less_equal": ("NONNEGATIVE_LEFT_LE_RIGHT", "left nonnegative quantity <= right quantity in shared units; sensor counts must be integral", "nonnegative", "MATCH"),
    "list_count": ("TYPE_LIST_LENGTH_LE_SENSOR_TOTAL", "positive integer type-list length <= nonnegative integral total sensor count", "sensor_list", "MATCH"),
    "sorted_unique": ("LIST_EQUALS_SORTED_UNIQUE", "positive integer list equals its sorted unique representation", "sensor_list", "MATCH"),
    "sensor_presence": ("SENSOR_TYPE_MEMBER_GIVEN_FLAG_TRUE", "configured sensor_type belongs to type list when capability flag is true", "sensor_presence", "MATCH"),
    "exact_package_policy_v1": ("PACKAGE_IN_FROZEN_ALLOWLIST", "package exactly belongs to old deployment allowlist", "deployment", "MATCH"),
    "package_release_policy_v1": ("PACKAGE_AND_RELEASE_PAIR_IN_FROZEN_ALLOWLIST", "package and code/name pair match one old allowed release", "deployment", "MATCH"),
    "debug_and_cleartext_context_v1": ("DEBUGGABLE_AND_CLEARTEXT", "debuggable and cleartext-permitted booleans both true", "boolean", "CONTEXT_OBSERVED"),
    "debug_cleartext_context_v1": ("DEBUGGABLE_AND_CLEARTEXT", "debuggable and cleartext-permitted booleans both true", "boolean", "CONTEXT_OBSERVED"),
    "adb_and_high_battery_context_v1": ("ADB_AND_BATTERY_GE_97", "ADB enabled and battery percent >= 97; is_charging remains a legacy dependency, not a condition", "context", "CONTEXT_OBSERVED"),
    "normalized_build_marker_context_v1": ("NONEMPTY_NORMALIZED_BUILD_MARKER_SET", "frozen extractor returns at least one build marker category", "context", "CONTEXT_OBSERVED"),
    "test_rig_context_v1": ("LEGACY_TEST_RIG_BOOLEAN", "(installer manual AND (timezone offset zero OR ADB)) OR (ADB AND battery>=97)", "context", "CONTEXT_OBSERVED"),
    "android_gpu_not_windows_direct3d_v1": ("NO_DESKTOP_WEBGL_BACKEND_TOKEN", "WebGL vendor/renderer have no direct3d, d3d11, d3d12 or windows token; Native strings only prerequisites", "backend_marker", "MATCH"),
    "installer_observation_v1": ("NO_BOOLEAN_ATOM", "all interpretable installer categories produce context; this outcome does not identify a category", "context_summary", None),
    "webview_ua_markers_context_v1": ("NO_BOOLEAN_ATOM", "both/present/absent marker cases all produce context; do not map context to marker=true", "context_summary", None),
    "development_flags_context_v1": ("NO_BOOLEAN_ATOM", "all flag combinations including none produce context", "context_summary", None),
    "network_context_v1": ("NO_BOOLEAN_ATOM", "VPN/no-network/other snapshots all produce context; do not treat context as VPN=true", "context_summary", None),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def rel(path):
    return str(path.relative_to(ROOT))


def put(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def put_lines(path, rows):
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def csv_out(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def surface(field):
    return next(v for p, v in SURFACES.items() if field.startswith(p))


def candidate_ledger(catalog, sources, roles, families, fields):
    out = []
    for rule in sorted(catalog["rules"], key=lambda r: r["rule_id"]):
        if rule["status"] != "ACTIVE":
            continue
        rid = rule["rule_id"]
        src = sources[rid]
        operator, definition, profile, true_outcome = SEMANTICS[rule["predicate"]]
        surfaces = sorted({surface(f) for f in rule["dependencies"]})
        if rid in CORE:
            kind = "CROSS_SURFACE_RELATION"
        elif rid in COLLECTOR:
            kind = "COLLECTOR_CONSISTENCY"
        elif rid in {"NVW-003", "OFFDER-PACKAGE-001"}:
            kind = "DEPLOYMENT_POLICY"
        elif rid in SAME or rule["predicate"] == "sensor_presence":
            kind = "SAME_SURFACE_MULTIFIELD"
        elif len(rule["dependencies"]) == 1:
            kind = "SINGLE_FIELD_CONTEXT"
        else:
            kind = "OTHER_DIAGNOSTIC"
        browser = "browser67" in surfaces
        mapping = {"UNKNOWN": "U", "NOT_APPLICABLE": "U", "NOT_EVALUATED": "U_IF_MISSING_OTHERWISE_NOT_REQUESTED"}
        if true_outcome:
            mapping[true_outcome] = "T"
            mapping["MATCH" if true_outcome != "MATCH" else
                    "POLICY_MISMATCH" if kind == "DEPLOYMENT_POLICY" else "COUNTEREXAMPLE"] = "F"
        else:
            mapping["CONTEXT_OBSERVED"] = "NO_BOOLEAN_ATOM"
        cross = rid in CORE
        single = true_outcome is not None and len(surfaces) == 1 and kind != "DEPLOYMENT_POLICY"
        reason = ("DEFINED_CROSS_SURFACE_OBSERVATION_LEGAL_ALTERNATIVES_LIMIT_ATTRIBUTION_ONLY" if cross else
                  "NO_BOOLEAN_CONDITION_IN_CONTEXT_OUTCOME_USE_DECLARED_CONTROL_ENCODER" if rid in NO_BOOLEAN else
                  "DEPLOYMENT_ALLOWLIST_NOT_A_CROSS_SURFACE_RELATION" if kind == "DEPLOYMENT_POLICY" else
                  "SINGLE_SURFACE_OR_SHARED_COPY_CONTROL_NOT_CROSS_SURFACE_CONTRIBUTION" if single else
                  "MULTISURFACE_DEPENDENCIES_DO_NOT_CREATE_RELATIONAL_COMPARISON")
        related = [e for e in families["overlap_edges"] if rid in (e["rule_a"], e["rule_b"])
                   and e["relation"] != "disjoint_evidence"]
        # Preserve a compact link per actual shared/equivalent pair, no inferred
        # independence and no outcome-based correlation calculation.
        related = [{"other_rule_id": e["rule_b"] if e["rule_a"] == rid else e["rule_a"],
                    "relation": e["relation"]} for e in related
                   if e.get("shared_fields") or e.get("same_decision_family")]
        out.append({
            "study_version": "discriminative-rule-learning-v1-20260924", "candidate_version": "r01-atoms-v1",
            "atom_id": "CAT:" + rid, "rule_id": rid, "catalog_version": catalog["catalog_version"],
            "predicate": rule["predicate"], "predicate_version": rule["version"],
            "parameters": rule.get("parameters", {}), "legacy_spec": rule.get("legacy_spec"),
            "implementation_ref": src["researcher_derivation"]["implementation_ref"],
            "dependencies": rule["dependencies"], "dependency_schema": [{"field": f, **fields[f]} for f in rule["dependencies"]],
            "observation_surfaces": surfaces, "relation_type": kind,
            "provenance_group": src["provenance_group"], "semantic_origin": src["semantic_origin"],
            "source_urls": src["source_url"], "official_document_versions": src["official_document_version"],
            "screening_history": {key: src.get(key) for key in ["empirically_screened", "screening_scope", "catalog_empirical_selection_flag", "discovery_split_ref", "selection_basis", "tolerance_source"]},
            "original_family": rule["evidence_family"], "decision_family": src["decision_family"],
            "legacy_S03_role": src["decision_role"], "legacy_S03R_role": roles[rid]["decision_role"],
            "legacy_role_used_for_inclusion": False, "related_rules": related,
            "measurement": {"defined": true_outcome is not None, "profile": profile,
                            "condition": {"operator": operator, "operands": rule["dependencies"], "parameters": rule.get("parameters", {})},
                            "T_definition": definition, "outcome_to_state": mapping,
                            "requirements": ["registered_observed_typed_finite_quality_values", "profile_requirements_in_measurement_contract"],
                            "predicate_extra_domain": "PRESERVE_RAW_UNKNOWN_AND_NOT_APPLICABLE_WITH_ORIGINAL_REASON",
                            "removed_attribution_vetoes": src.get("unobservable_alert_preconditions", []),
                            "old_gate_dependencies_not_automatically_required": src["gate_dependencies"]},
            "known_counterexamples": src["known_counterexamples"], "catalog_limitations": rule.get("limitations"),
            "candidate_use": {"core": cross, "single_surface_control": single, "diagnostic": not cross,
                              "selectable_on_App177": (cross or single) and not browser,
                              "browser_material_role": "REFERENCE_ONLY_NO_SUPERVISED_LABEL" if browser else "NOT_APPLICABLE",
                              "allowed_polarities": ["POSITIVE", "NEGATIVE"] if (cross or single) and true_outcome else [],
                              "learned_selection": "NOT_FITTED", "inclusion_or_exclusion_reason": reason,
                              "structural_unavailability": "BROWSER_SURFACE_ABSENT" if browser else None},
            "direct_OR_deviation_polarity": ("POSITIVE" if rid in NEQ else "NEGATIVE") if cross else None,
            "normalized_identity": "DEVIATION:" + ALIASES.get(rid, rid),
            "identity_scope": "R01_EQUAL_MEASUREMENT_DOMAIN_ONLY_KEEP_ORIGINAL_PROVENANCE",
            "source_ref": rel(OLD / "03_registry/source_registry.jsonl") + "#rule_id=" + rid,
        })
    return out


def build(out):
    if out.exists():
        raise SystemExit("Refusing existing output directory; choose a fresh --output.")
    configs = {name: read(K / (name + ".json")) for name in CONFIGS}
    paths = [ROOT / "RESEARCH_MAINLINE.md", ROOT / "deliverables/formal_experiment_execution_plan/EXECUTION_PLAN.md",
             ROOT / "deliverables/formal_experiment_execution_plan/research_references.bib",
             OLD / "01_admission/facts_and_eligibility.jsonl", OLD / "01_admission/material_inventory.jsonl",
             OLD / "01_admission/stage_accounting.jsonl", OLD / "01_admission/triplet_registry.jsonl",
             OLD / "01_admission/environment_group_registry.json", OLD / "02_inputs/input_manifest.jsonl",
             OLD / "02_inputs/evaluation_index.jsonl", OLD / "02_inputs/phase_associations.json",
             OLD / "02_inputs/field_mapping.json", OLD / "02_inputs/inference_inputs.jsonl",
             OLD / "03_registry/source_registry.jsonl", OLD / "03_registry/family_registry.json",
             OLD / "06_e1/prediction/rule_events.jsonl", OLD / "06_e1/prediction/predictions.jsonl",
             OLD / "06_e1/STEP_REPORT.md", ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json",
             ROOT / "hybridguard_agent/config/formal_manipulation_role_gate_v2/decision_roles.json"]
    mtc = ROOT / "hybridguard_agent/artifacts/mtc_p6_fixed_20260923"
    paths += [mtc / "p2_control/summary.json", mtc / "p2_control/split_manifest.jsonl", mtc / "RESERVED_FIRST_READ.json"]
    source_stats = [{"path": rel(p), "size": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns} for p in paths]
    facts = lines(OLD / "01_admission/facts_and_eligibility.jsonl")
    fact_by_id = {r["candidate_id"]: r for r in facts}
    inventory = lines(OLD / "01_admission/material_inventory.jsonl")
    index = lines(OLD / "02_inputs/evaluation_index.jsonl")
    inputs = {r["opaque_id"]: r for r in lines(OLD / "02_inputs/input_manifest.jsonl")}
    associations = read(OLD / "02_inputs/phase_associations.json")
    groups = read(OLD / "01_admission/environment_group_registry.json")
    mapping = read(OLD / "02_inputs/field_mapping.json")
    fields = {f["field"]: {"type": f["type"], "surface": f["surface"]} for f in mapping["fields"]}
    fields.update({f.replace("app.", "browser.", 1): {"type": t["type"], "surface": "browser67"}
                   for f, t in list(fields.items()) if f.startswith(A)})
    catalog = read(ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json")
    sources = {r["rule_id"]: r for r in lines(OLD / "03_registry/source_registry.jsonl")}
    roles = {r["rule_id"]: r for r in read(ROOT / "hybridguard_agent/config/formal_manipulation_role_gate_v2/decision_roles.json")["roles"]}
    families = read(OLD / "03_registry/family_registry.json")
    candidates = candidate_ledger(catalog, sources, roles, families, fields)
    field_sets = sorted({tuple(sorted((f.get("original_attack_annotation") or {}).get("expected_mutations", []))) for f in facts})
    field_ids = {fs: "declared-fields-%02d" % i for i, fs in enumerate(field_sets) if fs}
    ledger = []
    for row in index:
        fact = fact_by_id[row["candidate_id"]]
        annotation = fact.get("original_attack_annotation") or {}
        expected = tuple(sorted(annotation.get("expected_mutations", [])))
        eligible = fact["eligible_detection"] or fact["eligible_pre_control"] or fact["eligible_post_control"]
        ledger.append({
            "study_version": "discriminative-rule-learning-v1-20260924", "opaque_id": row["opaque_id"],
            "candidate_id": row["candidate_id"], "bundle_id": row["bundle_id"], "triplet_id": row["triplet_id"],
            "session_id": row["session_id"], "phase": row["phase"], "cohort": row["cohort"],
            "environment_group_id": row["environment_group_id"], "collector_install_id": row["collector_install_id"],
            "config_id": row["config_id"], "configuration_name": row["configuration_id"], "tool_name": row["tool"],
            "declared_field_set_id": field_ids.get(expected), "declared_modified_fields": list(expected),
            "mechanism_id": None, "mechanism_status": "UNVERIFIED_NOT_INFERRED_FROM_TOOL_CONFIG_OR_FIELD_SET",
            "supervised_label": 1 if fact["eligible_detection"] else 0 if eligible else None,
            "data_role": "SUPERVISED_DEVELOPMENT_BY_FOLD" if eligible else "DESCRIPTIVE_ONLY",
            "fit_permission": "ONLY_WHEN_IN_OUTER_TRAIN" if eligible else "DENIED",
            "internal_validation_permission": "DENIED_FIXED_PARAMETERS",
            "outer_evaluation_permission": "ONLY_WHEN_IN_OUTER_TEST" if eligible else "DESCRIPTIVE_ONLY_NO_METRICS",
            "prospective_confirmation_permission": "DENIED_ALREADY_EXPOSED",
            "fact_status": fact["adjudication_status"], "evidence_grade": fact["evidence_grade"],
            "no_intervention_status": fact["no_intervention"]["status"], "label_scope": fact["ground_truth_scope"],
            "eligible_detection": fact["eligible_detection"], "eligible_pre_control": fact["eligible_pre_control"],
            "eligible_post_control": fact["eligible_post_control"], "eligible_temporal_control": fact["eligible_temporal_control"],
            "S01_fact_ref": rel(OLD / "01_admission/facts_and_eligibility.jsonl") + "#candidate_id=" + row["candidate_id"],
            "S02_input_ref": rel(OLD / "02_inputs") + "/" + inputs[row["opaque_id"]]["input_ref"],
            "exposure": "EXPOSED_RETROSPECTIVE", "independent_physical_device_count": None,
        })
    ledger.sort(key=lambda r: r["candidate_id"])
    supervised = [r for r in ledger if r["supervised_label"] is not None]
    envs = sorted({r["environment_group_id"] for r in supervised})
    configs_supervised = sorted({r["config_id"] for r in supervised})
    config_review = []
    for cfg in configs_supervised:
        rows = [r for r in ledger if r["config_id"] == cfg]
        admitted = [r for r in rows if r["supervised_label"] is not None]
        config_review.append({"config_id": cfg, "configuration_names": sorted({r["configuration_name"] for r in rows if r["configuration_name"]}),
                              "tool_names": sorted({r["tool_name"] for r in rows}),
                              "declared_field_set_ids": sorted({r["declared_field_set_id"] for r in rows if r["declared_field_set_id"]}),
                              "environment_groups": sorted({r["environment_group_id"] for r in admitted}),
                              "bundles": sorted({r["bundle_id"] for r in rows}),
                              "admitted_triplets": len({r["triplet_id"] for r in admitted}),
                              "mechanism_id": None, "mechanism_status": "UNVERIFIED",
                              "basis": "S01 annotation and S02 config identity; execution support does not adjudicate mechanism equivalence"})
    support = []
    grouped = defaultdict(list)
    for r in ledger:
        grouped[(r["environment_group_id"], r["config_id"] or "UNSPECIFIED_CONTROL_CONFIG", r["cohort"])].append(r)
    for (env, cfg, cohort), rows in sorted(grouped.items()):
        support.append({"environment_group_id": env, "config_id": cfg, "cohort": cohort,
                        "mechanism_status": "UNVERIFIED", "tool_names": "|".join(sorted({r["tool_name"] or "UNKNOWN" for r in rows})),
                        "declared_field_sets": "|".join(sorted({r["declared_field_set_id"] or "NOT_DECLARED" for r in rows})),
                        "bundles": len({r["bundle_id"] for r in rows}), "triplet_or_partial_groups": len({r["triplet_id"] for r in rows}),
                        "stages": len(rows), "eligible_attack": sum(r["supervised_label"] == 1 for r in rows),
                        "eligible_pre": sum(r["eligible_pre_control"] for r in rows), "eligible_post": sum(r["eligible_post_control"] for r in rows),
                        "unknown_label_stages": sum(r["supervised_label"] is None for r in rows)})
    splits, fold_manifest = [], []
    for track, targets, field in [("LOEO-v1", envs, "environment_group_id"), ("LOCO-v1", configs_supervised, "config_id")]:
        for i, target in enumerate(targets, 1):
            fold = "%s-%02d" % (track, i)
            membership = {"split_id": track, "fold_id": fold, "target": target, "target_field": field,
                          "train": [], "outer_test": [], "descriptive_train_side": [], "descriptive_test_side": []}
            for r in ledger:
                test = r[field] == target
                key = ("outer_test" if test else "train") if r["supervised_label"] is not None else ("descriptive_test_side" if test else "descriptive_train_side")
                membership[key].append(r["opaque_id"])
            for key in ["train", "outer_test", "descriptive_train_side", "descriptive_test_side"]:
                membership[key].sort()
            splits.append(membership)
            summary = {"split_id": track, "fold_id": fold, "target": target, "inner_selection": "NONE_FIXED_HYPERPARAMETERS", "sides": {}}
            for side in ["train", "outer_test"]:
                ids = set(membership[side])
                rows = [r for r in ledger if r["opaque_id"] in ids]
                clean_n = sum(r["supervised_label"] == 0 for r in rows)
                summary["sides"][side] = {"stages": len(rows), "attack": sum(r["supervised_label"] == 1 for r in rows),
                                         "clean": clean_n, "pre": sum(r["eligible_pre_control"] for r in rows), "post": sum(r["eligible_post_control"] for r in rows),
                                         "triplets": len({r["triplet_id"] for r in rows}),
                                         "environments": sorted({r["environment_group_id"] for r in rows}),
                                         "configurations": sorted({r["config_id"] for r in rows}),
                                         "one_clean_alarm_resolution": 1 / clean_n,
                                         "clean_budgets": {p["id"]: int(round(p["alpha"] * 100)) * clean_n // 100 for p in configs["learning_search_space"]["operating_points"]}}
            tr, te = summary["sides"]["train"], summary["sides"]["outer_test"]
            feasible = len(tr["environments"]) >= 2 and tr["triplets"] >= 6 and len(tr["configurations"]) >= 2 and te["triplets"] >= 3
            summary.update(status="FEASIBLE_FIXED_PARAMETERS" if feasible else "NOT_EVALUABLE", shared_environments=sorted(set(tr["environments"]) & set(te["environments"])))
            fold_manifest.append(summary)
    flow = [{"bundle_id": r["bundle_id"], "environment_group_id": r["environment_group_id"],
             "source_stage_count": r["raw_rows"], "material_disposition": r["material_disposition"],
             "validator_status_saved_not_rerun": r["validator_status"],
             "data_roles": dict(Counter(d["data_role"] for d in ledger if d["bundle_id"] == r["bundle_id"])),
             "zero_stage_role": "MATERIAL_HISTORY_ONLY" if not r["raw_rows"] else "NOT_APPLICABLE",
             "source_ref": rel(OLD / "01_admission/material_inventory.jsonl") + "#bundle_id=" + r["bundle_id"]} for r in inventory]
    exclusions = {N + "build_fingerprint_layer.elapsed_realtime_ms", N + "build_fingerprint_layer.uptime_ms",
                  N + "build_fingerprint_layer.build_time_ms", H + "temporal_build_layer.first_install_time",
                  H + "temporal_build_layer.last_update_time", A + "execution_layer.performance_time_origin",
                  A + "execution_layer.compute_task_time_ms"}
    single_fields = [{"field": f["field"], "type": f["type"], "surface": f["surface"],
                      "encoder": "BOOL_EQ_TRUE" if f["type"] == "boolean" else "TRAIN_QUANTILE_LE"}
                     for f in mapping["fields"] if f["type"] in {"number", "boolean"} and f["field"] not in exclusions]
    for fld, encoder in [(A + "navigator_layer.user_agent", "UA_CLASS"), (A + "navigator_layer.platform", "PLATFORM_CLASS"),
                         (H + "kernel_container_layer.default_ua_native", "UA_CLASS"), (H + "webview_settings_layer.settings_user_agent", "UA_CLASS"),
                         (A + "navigator_layer.languages", "LIST_LENGTH_TRAIN_QUANTILE")]:
        single_fields.append({"field": fld, **fields[fld], "encoder": encoder})
    summary = {"inventory": len(candidates), "sources": dict(Counter(r["provenance_group"] for r in candidates)),
               "relation_types": dict(Counter(r["relation_type"] for r in candidates)),
               "core_including_browser": sum(r["candidate_use"]["core"] for r in candidates),
               "App177_core_before_alias_dedup": sum(r["candidate_use"]["core"] and r["candidate_use"]["selectable_on_App177"] for r in candidates),
               "App177_core_canonical": len({r["normalized_identity"] for r in candidates if r["candidate_use"]["core"] and r["candidate_use"]["selectable_on_App177"]}),
               "browser_dependent": sum("browser67" in r["observation_surfaces"] for r in candidates),
               "stages": len(ledger), "cohorts": dict(Counter(r["cohort"] for r in ledger)),
               "supervised": len(supervised), "attack": sum(r["supervised_label"] == 1 for r in ledger), "clean": sum(r["supervised_label"] == 0 for r in ledger),
               "environment_groups": envs, "configuration_count": len(configs_supervised), "folds": len(splits),
               "real_fits": 0, "real_predictions": 0, "outcome_rankings": 0}
    # Digest only these new, small protocol objects. Never hash historical data.
    canonical = json.dumps({"configs": configs, "candidates": candidates}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    out.mkdir(parents=True)
    put_lines(out / "CANDIDATE_LEDGER.jsonl", candidates)
    put_lines(out / "DATA_ROLE_LEDGER.jsonl", ledger)
    put_lines(out / "MATERIAL_FLOW.jsonl", flow)
    put_lines(out / "SPLIT_MEMBERSHIP.jsonl", splits)
    put(out / "FOLD_MANIFEST.json", fold_manifest)
    csv_out(out / "GROUP_SUPPORT.csv", support)
    put(out / "CONFIGURATION_REVIEW.json", {"configurations": config_review, "declared_field_sets": {field_ids[s]: list(s) for s in field_ids},
                                           "mechanism_partition": "UNVERIFIED", "control_config_missing": "PRESERVED_NULL_NOT_IMPUTED_FROM_FILENAME"})
    put(out / "SINGLE_SURFACE_FIELDS.json", {"encoder": "SINGLE_SURFACE_TRAIN_ENCODER_V1", "fields": single_fields,
                                            "excluded_numeric_fields": sorted(exclusions), "source": rel(OLD / "02_inputs/field_mapping.json"),
                                            "thresholds_fitted": False, "strings_not_explicitly_listed": "EXCLUDED", "lineage": "COLLECTOR_SCHEMA_NOT_LABEL_OUTCOMES"})
    put(out / "GROUP_GENERATION.json", {"source_groups": groups["groups"], "source_rules": groups["rules"],
                                       "phase_associations_ref": rel(OLD / "02_inputs/phase_associations.json"), "phase_association_count": len(associations),
                                       "membership_generator": "hybridguard_agent/scripts/prepare_rule_learning_r01.py",
                                       "all_bundle_stages_same_side": True, "seed": 20260924, "shuffle": False})
    put(out / "MTC_ROLE_DECLARATION.json", {"role": "EXPOSED_RELATION_REFERENCE_ONLY", "population_manifest": rel(mtc / "p2_control/split_manifest.jsonl"),
                                          "population_scope": "ALL_ROWS_IN_REFERENCED_MANIFEST_NO_SAMPLING", "saved_counts": read(mtc / "p2_control/summary.json"),
                                          "current_reserved_status": "CONSUMED_IN_P6", "consumption_evidence": rel(mtc / "RESERVED_FIRST_READ.json"),
                                          "supervised_fit_allowed": False, "TPR_FPR": "NOT_EVALUABLE_NO_TRUTH", "prospective_role": "DENIED"})
    put(out / "SUMMARY.json", summary)
    put(out / "PROTOCOL_BINDING.json", {"study_version": "discriminative-rule-learning-v1-20260924", "protocol_id": "r01-protocol-v1-20260924",
                                       "protocol_digest": digest, "algorithm": "sha256_canonical_json_configs_plus_candidates",
                                       "candidate_version": "r01-atoms-v1", "split_id": "PER_MEMBERSHIP_RECORD", "fold_id": "PER_MEMBERSHIP_RECORD",
                                       "model_id": "NOT_FITTED", "input_manifest_ref": rel(OLD / "02_inputs/input_manifest.jsonl"),
                                       "config_refs": [rel(K / (n + ".json")) for n in CONFIGS], "historical_files_hashed": 0})
    put(out / "READ_ONLY_BASELINE.json", {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                                         "protected_inputs": source_stats, "check_kind": "TARGETED_SIZE_MTIME_AND_GIT_DIFF_NOT_SECURITY_ATTESTATION"})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    build(parser.parse_args().output.resolve())
