#!/usr/bin/env python3
"""Freeze MTC research groups, splits and task admission without running rules.

Grouping uses metadata only. Model families, installations, sessions, declared
scenarios and verified identities are transitive links, never inferred labels.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = REPO / "hybridguard_agent/config/mtc_experiment_protocol.v1.json"
FACT_SCHEMA = REPO / "hybridguard_agent/schemas/mtc_experiment_fact_v2.schema.json"
VIEWS = ("paired_244", "app_only_177", "partial", "repeated_observations", "quarantine")
SPLITS = ("discovery", "development", "reserved_validation")


def read_json(path):
    return json.loads(path.read_text())


def read_jsonl(path):
    with path.open() as handle:
        for line, text in enumerate(handle, 1):
            if text.strip():
                yield line, json.loads(text)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path, rows):
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def stable_id(prefix, value):
    # Stable identifiers and allocation, not file-integrity/security scanning.
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(text.encode()).hexdigest()[:24]


def resolve_path(value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO / path).resolve()


def load_protocol(path):
    p = read_json(path)
    if (p.get("protocol_version") != "mtc-experiment-protocol-v1"
            or p.get("source_manifest_version") != "mtc-paired244-snapshot-v2"
            or p.get("source_record_version") != "hybridguard-mtc-observation-v2"
            or p["grouping"]["algorithm"] != "transitive_union"
            or p["grouping"]["keys"] != ["exact_manufacturer_model_across_android_versions", "collector_install_id", "app_session_id", "declared_scenario_id", "verified_identity_key"]
            or p["grouping"]["physical_device_identity_inferred"] is not False
            or p["grouping"]["manufacturer_model_normalization"] != "none_preserve_exact_source_strings"
            or p["split"]["algorithm"] != "sha256_bucket_100"
            or p["split"]["thresholds"] != [["discovery", 0, 70], ["development", 70, 85], ["reserved_validation", 85, 100]]
            or not p["split"].get("seed")):
        raise ValueError("Unsupported MTC grouping/split protocol")
    if p["primary_cohort"] != {
        "view": "paired_244", "representative_unit": "exact_manufacturer_model_android_release",
        "representative_selection": "smallest_app_raw_source_line_then_sample_id",
        "all_other_observations": "retain_in_same_split_for_repeatability_and_missingness_only",
        "support_unit": "unique_leakage_group_never_session_count",
    }:
        raise ValueError("Unsupported representative/support protocol")
    if any(type(p["admission"].get(k)) is not int or p["admission"][k] < 1 for k in (
        "minimum_groups_for_rule_discovery", "minimum_groups_per_detection_split", "minimum_groups_per_detection_class_per_split")):
        raise ValueError("Invalid admission group floor")
    capabilities = p["stage_capabilities"]
    if any(capabilities.get(k) is not False for k in ("reserved_validation_input_release", "model_training", "threshold_optimization", "detection_metrics", "rule_execution")):
        raise ValueError("P2 cannot enable rule execution, final validation or metrics")
    if capabilities.get("rule_discovery_input_selection") is not True or capabilities.get("development_input_selection") is not True:
        raise ValueError("Unexpected P2 input-selection contract")
    return p


def model_key(row):
    p = row["profile"]
    return (p["manufacturer"], p["model"])


def model_os_key(row):
    return model_key(row) + (row["profile"]["android_release"],)


def load_snapshot(snapshot, protocol):
    manifest = read_json(snapshot / "manifest.json")
    if (manifest.get("dataset_manifest_version") != protocol["source_manifest_version"]
            or manifest.get("p1_status") != "COMPLETE" or manifest.get("label_status") != "unlabeled"
            or manifest.get("dataset_role") != "development_qc_only"):
        raise ValueError("P2 requires the completed unlabeled MTC v2 QC snapshot")
    rows, seen, source_inputs = [], set(), []
    if manifest["view_counts"].get("quarantine") != 0:
        raise ValueError("This protocol requires explicit review of new P1 quarantines before grouping")
    for view in VIEWS:
        path = snapshot / (view + ".jsonl")
        count = 0
        for line, source in read_jsonl(path):
            count += 1
            sample_id = source.get("sample_id")
            if (not isinstance(sample_id, str) or not sample_id or sample_id in seen
                    or source.get("record_schema_version") != protocol["source_record_version"]
                    or source.get("dataset_view") != view or source.get("label_status") != "unlabeled"
                    or source.get("dataset_role") != "development_qc_only"):
                raise ValueError("Invalid or repeated P1 observation")
            seen.add(sample_id)
            profile = source["profile"]
            if any(not isinstance(profile.get(k), str) or not profile[k] for k in ("manufacturer", "model", "android_release", "collector_install_id")):
                raise ValueError("P1 observation lacks explicit grouping metadata")
            app = source["app"]
            if not re.fullmatch("[0-9a-f]{64}", app.get("payload_sha256", "")):
                raise ValueError("P1 observation lacks App payload binding")
            if view == "paired_244" and (source["qc"]["status"] != "passed" or source["feature_count"] != 244
                    or source.get("pair", {}).get("pair_status") != "completed"):
                raise ValueError("P1 paired cohort contract drifted")
            if len(source["field_status"]) != source["feature_count"] or set(source["field_quality"]) != set(source["field_status"]):
                raise ValueError("P1 field availability contract drifted")
            # Retain field availability, never fingerprint values, in the control plane.
            usable = sorted(k for k, state in source["field_status"].items()
                            if state == "observed" and source["field_quality"].get(k) == "observed_value")
            rows.append({"sample_id": sample_id, "view": view, "source_line": line,
                         "source_file": str(path), "app_raw_line": source["source_refs"]["app_raw_line"],
                         "app_session_id": app["session_id"], "app_payload_sha256": app["payload_sha256"],
                         "browser_payload_sha256": source.get("browser", {}).get("payload_sha256"),
                         "profile": profile, "collector_version_code": app["collector_version_code"],
                         "browser_package": source.get("browser", {}).get("resolved_browser_package"),
                         "qc_status": source["qc"]["status"], "usable_fields": usable})
        if count != manifest["view_counts"][view]:
            raise ValueError("P1 view row count drifted: " + view)
        source_inputs.append({"path": str(path), "row_count": count, "size_bytes": path.stat().st_size})
    if len(rows) != manifest["source_rows"]["raw_expanded_payloads"]:
        raise ValueError("P1 archive accounting drifted")
    selection = [row for _, row in read_jsonl(snapshot / "selection_audit.jsonl")]
    if Counter((r["source_line"], r["sample_id"], r["destination"]) for r in selection) != Counter(
            (r["app_raw_line"], r["sample_id"], r["view"]) for r in rows):
        raise ValueError("P1 source-row routing differs from its selection audit")
    return manifest, sorted(rows, key=lambda r: r["sample_id"]), source_inputs


def validate_fact(fact, sample, evidence_base):
    schema = read_json(FACT_SCHEMA)
    if set(fact) != set(schema["required"]):
        raise ValueError("Fact keys differ from the v2 contract")
    for key, spec in schema["properties"].items():
        value = fact[key]
        if "const" in spec and value != spec["const"] or "enum" in spec and value not in spec["enum"]:
            raise ValueError("Invalid fact value: " + key)
        if "type" in spec:
            types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            actual = "null" if value is None else "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "string" if isinstance(value, str) else "array" if isinstance(value, list) else "other"
            if actual not in types:
                raise ValueError("Invalid fact type: " + key)
            if isinstance(value, str) and (len(value) < spec.get("minLength", 0) or ("pattern" in spec and not re.fullmatch(spec["pattern"], value))):
                raise ValueError("Invalid fact string: " + key)
            if actual == "integer" and value < spec.get("minimum", value):
                raise ValueError("Invalid fact integer: " + key)
            if isinstance(value, list) and (any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value)):
                raise ValueError("Invalid fact list: " + key)
    if any(fact[k] != sample[k] for k in ("sample_id", "app_session_id", "app_payload_sha256", "browser_payload_sha256")):
        raise ValueError("Fact is not bound to the exact App/Browser observation")
    refs = fact["evidence_refs"]
    if any(not (Path(ref) if Path(ref).is_absolute() else evidence_base / ref).is_file() for ref in refs):
        raise ValueError("Fact evidence file does not exist")
    asserted = fact["label_status"] == "verified" or fact["identity_status"] == "verified" or fact["reference_status"] == "no_active_intervention_recorded"
    if asserted and (not refs or fact["source_kind"] == "unknown"):
        raise ValueError("Verified facts require independent evidence references")
    if fact["identity_status"] == "verified" and (not fact["stable_identity_key"] or fact["identity_scope"] == "unknown"):
        raise ValueError("Verified identity lacks an explicit key/scope")
    scenario = [fact[k] is not None for k in ("scenario_id", "scenario_phase", "scenario_repetition", "phase_started_at_utc")]
    if any(scenario) and not all(scenario):
        raise ValueError("Scenario id, phase, repetition and UTC time must be declared together")
    if all(scenario):
        stamp = datetime.fromisoformat(fact["phase_started_at_utc"].replace("Z", "+00:00"))
        if stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            raise ValueError("Scenario time must contain an explicit UTC offset")
    if fact["reference_status"] == "no_active_intervention_recorded" and fact["manipulation_present"] is True:
        raise ValueError("Reference and manipulation assertions contradict")
    if fact["label_status"] == "verified":
        if not isinstance(fact["manipulation_present"], bool):
            raise ValueError("Verified label requires an explicit boolean")
        if fact["manipulation_present"]:
            if not (fact["source_kind"] == "controlled_intervention_record" and fact["scenario_phase"] == "attack_active"
                    and fact["attack_family"] and fact["execution_status"] == "succeeded"
                    and fact["field_effect_status"] == "observed" and fact["observable_target_fields"]
                    and set(fact["observable_target_fields"]) <= set(sample["usable_fields"])):
                raise ValueError("Verified positive lacks executed, observable field-effect facts")
        elif not (fact["reference_status"] == "no_active_intervention_recorded"
                  and fact["execution_status"] == "not_applicable" and fact["field_effect_status"] == "no_configured_change"
                  and fact["scenario_phase"] in (None, "baseline")):
            raise ValueError("Verified negative lacks independent baseline facts")


def load_facts(path, rows):
    if path is None:
        return {}
    samples = {r["sample_id"]: r for r in rows}
    facts = {}
    for _, fact in read_jsonl(path):
        key = fact.get("sample_id")
        if key not in samples or key in facts:
            raise ValueError("Unmatched or duplicate fact sample")
        validate_fact(fact, samples[key], path.parent)
        facts[key] = fact
    return facts


class UnionFind:
    def __init__(self, ids):
        self.parent = {key: key for key in ids}

    def find(self, key):
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def link_keys(row, facts):
    keys = [("model_family", model_key(row)), ("install", row["profile"]["collector_install_id"]),
            ("app_session", row["app_session_id"])]
    fact = facts.get(row["sample_id"], {})
    if fact.get("scenario_id"):
        keys.append(("declared_scenario", fact["scenario_id"]))
    if fact.get("identity_status") == "verified":
        keys.append(("verified_identity", (fact["identity_scope"], fact["stable_identity_key"])))
    return keys


def assign_split(group_id, protocol):
    value = protocol["split"]["seed"] + "\0" + group_id
    bucket = int(hashlib.sha256(value.encode()).hexdigest()[:16], 16) % 100
    for name, low, high in protocol["split"]["thresholds"]:
        if low <= bucket < high:
            return name
    raise ValueError("Split bucket is uncovered")


def build_groups(rows, facts, protocol):
    union = UnionFind(r["sample_id"] for r in rows)
    first = {}
    for row in rows:
        for key in link_keys(row, facts):
            if key in first:
                union.union(row["sample_id"], first[key])
            else:
                first[key] = row["sample_id"]
    components = defaultdict(list)
    for row in rows:
        components[union.find(row["sample_id"])].append(row)
    groups, membership = [], {}
    for members in components.values():
        families = sorted({model_key(r) for r in members})
        group_id = stable_id("mtc-group-", families)
        split = assign_split(group_id, protocol)
        for r in members:
            membership[r["sample_id"]] = (group_id, split)
        groups.append({"group_id": group_id, "split": split, "group_kind": "conservative_leakage_group",
                       "physical_device_count": None, "model_families": [list(v) for v in families],
                       "model_os_profiles": [list(v) for v in sorted({model_os_key(r) for r in members})],
                       "installation_ids": sorted({r["profile"]["collector_install_id"] for r in members}),
                       "app_session_ids": sorted({r["app_session_id"] for r in members}),
                       "scenario_ids": sorted({facts[r["sample_id"]]["scenario_id"] for r in members
                                               if facts.get(r["sample_id"], {}).get("scenario_id")}),
                       "sample_ids": sorted(r["sample_id"] for r in members),
                       "view_counts": dict(Counter(r["view"] for r in members)),
                       "multi_model_link": len(families) > 1})
    if len({g["group_id"] for g in groups}) != len(groups):
        raise ValueError("Group identifiers collide")
    # Independent constraint check after transitive grouping and allocation.
    linked_splits = defaultdict(set)
    for row in rows:
        for key in link_keys(row, facts):
            linked_splits[key].add(membership[row["sample_id"]][1])
    if any(len(splits) != 1 for splits in linked_splits.values()):
        raise AssertionError("Related observations cross a split boundary")
    return sorted(groups, key=lambda g: g["group_id"]), membership


def build_scenarios(rows, facts, membership):
    by_id = {r["sample_id"]: r for r in rows}
    scenarios = defaultdict(list)
    for key, fact in facts.items():
        if fact["scenario_id"]:
            scenarios[(fact["scenario_id"], fact["scenario_repetition"])].append(key)
    result, qualified = [], set()
    for (scenario_id, repetition), ids in sorted(scenarios.items()):
        reasons = []
        phases = Counter(facts[key]["scenario_phase"] for key in ids)
        identities = {(facts[key]["identity_scope"], facts[key]["stable_identity_key"]) for key in ids}
        if phases != {"baseline": 1, "attack_active": 1}:
            reasons.append("missing_or_ambiguous_two_state_phases")
        if len(identities) != 1 or any(facts[key]["identity_status"] != "verified" for key in ids):
            reasons.append("identity_not_verified_consistent")
        if any(by_id[key]["view"] != "paired_244" for key in ids):
            reasons.append("both_phases_require_qc_paired244")
        if any(facts[key]["label_status"] != "verified" for key in ids):
            reasons.append("labels_not_independently_verified")
        if any(facts[key]["manipulation_present"] is not (facts[key]["scenario_phase"] == "attack_active") for key in ids):
            reasons.append("phase_label_conflict")
        if phases == {"baseline": 1, "attack_active": 1}:
            times = {facts[key]["scenario_phase"]: datetime.fromisoformat(facts[key]["phase_started_at_utc"].replace("Z", "+00:00")) for key in ids}
            if times["baseline"] >= times["attack_active"]:
                reasons.append("baseline_must_precede_attack_active")
        assignments = {membership[key] for key in ids}
        if len(assignments) != 1:
            raise AssertionError("Same scenario crossed a leakage group")
        if not reasons:
            qualified.update(ids)
        group_id, split = next(iter(assignments))
        result.append({"scenario_id": scenario_id, "repetition": repetition, "sample_ids": sorted(ids),
                       "group_id": group_id, "split": split, "data_contract_status": "QUALIFIED" if not reasons else "NOT_QUALIFIED",
                       "reasons": reasons, "execution_temporal_evidence": "requires_upstream_review_of_referenced_records",
                       "metric_eligible": False})
    return result, qualified


def representative_ids(rows, facts):
    chosen = {}
    for row in rows:
        fact = facts.get(row["sample_id"], {})
        if row["view"] != "paired_244" or fact.get("manipulation_present") is True or fact.get("scenario_phase") == "attack_active":
            continue
        key = model_os_key(row)
        rank = (row["app_raw_line"], row["sample_id"])
        if key not in chosen or rank < chosen[key][0]:
            chosen[key] = (rank, row["sample_id"])
    return {value[1] for value in chosen.values()}


def inference_projection(row):
    """The only projection offered to later extractors: no labels/groups/phases."""
    return {k: row[k] for k in ("sample_id", "source_file", "source_line", "app_payload_sha256", "browser_payload_sha256")}


def empirical_support_floor_met(scope, evidence, protocol):
    """A necessary coverage floor only; never an effect/correctness decision."""
    if scope not in ("global_empirical", "scoped_empirical"):
        raise ValueError("Unknown empirical candidate scope")
    floor = protocol["candidate_support_floor"][scope]
    if set(evidence) != set(floor) or any(type(v) is not int or v < 0 for v in evidence.values()):
        raise ValueError("Support evidence must contain nonnegative unique-group/manufacturer counts")
    return all(evidence[key] >= value for key, value in floor.items())


def select_task_inputs(rows, inventory, task):
    if task not in {"rule_discovery", "rule_development"}:
        raise ValueError("Reserved validation and detection inputs remain locked at P2")
    allowed = {r["sample_id"] for r in inventory if r["task_admission"][task] == "ADMITTED"}
    return [inference_projection(r) for r in rows if r["sample_id"] in allowed]


def build_inventory(rows, membership, facts, representatives, scenario_qualified):
    result = []
    for row in rows:
        key = row["sample_id"]
        group, split = membership[key]
        fact = facts.get(key, {})
        is_rep = key in representatives
        reference_ok = row["view"] == "paired_244" and fact.get("reference_status") == "no_active_intervention_recorded"
        detection_ok = key in scenario_qualified
        role = "primary_representative" if is_rep else "paired_repeat_observation" if row["view"] == "paired_244" else "reserve_" + row["view"]
        result.append({"sample_id": key, "source_view": row["view"], "source_line": row["source_line"],
                       "app_raw_line": row["app_raw_line"], "app_session_id": row["app_session_id"],
                       "app_payload_sha256": row["app_payload_sha256"], "browser_payload_sha256": row["browser_payload_sha256"],
                       "group_id": group, "split": split, "analysis_role": role, "profile": row["profile"],
                       "physical_device_identity": "externally_asserted_verified" if fact.get("identity_status") == "verified" and fact.get("identity_scope") == "physical_device" else "unknown",
                       "verified_identity_scope": fact.get("identity_scope") if fact.get("identity_status") == "verified" else None,
                       "label_status": fact.get("label_status", "unknown"), "manipulation_present": fact.get("manipulation_present"),
                       "scenario_id": fact.get("scenario_id"), "scenario_phase": fact.get("scenario_phase"),
                       "task_admission": {
                           "rule_discovery": "ADMITTED" if is_rep and split == "discovery" else "NOT_IN_TASK_COHORT",
                           "rule_development": "ADMITTED" if is_rep and split == "development" else "NOT_IN_TASK_COHORT",
                           "reserved_rule_validation": "LOCKED_PENDING_RULE_FREEZE" if is_rep and split == "reserved_validation" else "NOT_IN_TASK_COHORT",
                           "verified_reference_observation": "FACT_QUALIFIED" if reference_ok else "NOT_EVALUATED_NO_REFERENCE_FACTS",
                           "paired244_detection": "FACT_QUALIFIED_NOT_METRIC_READY" if detection_ok else "NOT_EVALUATED_NO_QUALIFIED_TWO_STATE_FACTS"},
                       "labels_are_control_plane_only": True, "metric_eligible": False})
    return result


def coverage(rows, membership, representatives):
    cells = defaultdict(lambda: {"samples": 0, "groups": set(), "representatives": 0})
    categories = defaultdict(set)
    for row in rows:
        if row["view"] != "paired_244":
            continue
        group, split = membership[row["sample_id"]]
        dims = {"manufacturer": row["profile"]["manufacturer"], "android_api": str(row["profile"]["android_api"]),
                "apk_version_code": str(row["collector_version_code"]), "browser_package": str(row["browser_package"])}
        for dimension, value in dims.items():
            categories[dimension].add(value)
            c = cells[(dimension, value, split)]
            c["samples"] += 1
            c["groups"].add(group)
            c["representatives"] += row["sample_id"] in representatives
    for dimension, values in categories.items():
        for value in values:
            for split in SPLITS:
                cells[(dimension, value, split)]
    return [{"dimension": dim, "value": value, "split": split, "paired_samples": c["samples"],
             "leakage_groups": len(c["groups"]), "primary_representatives": c["representatives"],
             "sparse_less_than_five_groups": len(c["groups"]) < 5, "stratum_metric_eligible": False}
            for (dim, value, split), c in sorted(cells.items())]


def build_plan(snapshot, output, protocol_path=DEFAULT_PROTOCOL, facts_path=None):
    snapshot, output = snapshot.resolve(), output.resolve()
    if output.exists() or output == snapshot or snapshot in output.parents:
        raise ValueError("Output must be a new directory outside the source snapshot")
    protocol = load_protocol(protocol_path)
    manifest, rows, inputs = load_snapshot(snapshot, protocol)
    facts = load_facts(facts_path, rows)
    groups, membership = build_groups(rows, facts, protocol)
    scenarios, scenario_qualified = build_scenarios(rows, facts, membership)
    representatives = representative_ids(rows, facts)
    inventory = build_inventory(rows, membership, facts, representatives, scenario_qualified)
    counts = {}
    for split in SPLITS:
        members = [r for r in rows if membership[r["sample_id"]][1] == split]
        paired = [r for r in members if r["view"] == "paired_244"]
        counts[split] = {"all_groups": sum(g["split"] == split for g in groups),
                         "paired_groups": len({membership[r["sample_id"]][0] for r in paired}),
                         "all_observations": len(members), "paired_observations": len(paired),
                         "representative_groups": len({membership[r["sample_id"]][0] for r in members if r["sample_id"] in representatives}),
                         "model_os_representatives": sum(r["sample_id"] in representatives for r in members),
                         "view_counts": dict(Counter(r["view"] for r in members))}
    detection_counts = {s: {str(label).lower(): len({membership[r["sample_id"]][0] for r in rows
                          if r["sample_id"] in scenario_qualified and membership[r["sample_id"]][1] == s
                          and facts[r["sample_id"]]["manipulation_present"] is label}) for label in (False, True)} for s in SPLITS}
    detection_group_totals = {s: len({membership[key][0] for key in scenario_qualified if membership[key][1] == s}) for s in SPLITS}
    detection_data_ready = all(detection_group_totals[s] >= protocol["admission"]["minimum_groups_per_detection_split"]
                              and min(detection_counts[s].values()) >= protocol["admission"]["minimum_groups_per_detection_class_per_split"] for s in SPLITS)
    admitted_discovery = counts["discovery"]["representative_groups"] >= protocol["admission"]["minimum_groups_for_rule_discovery"]
    if not admitted_discovery:
        for r in inventory:
            if r["task_admission"]["rule_discovery"] == "ADMITTED":
                r["task_admission"]["rule_discovery"] = "NOT_EVALUATED_INSUFFICIENT_GROUPS"
    registry = {"registry_version": "mtc-group-registry-v1", "grouping_policy": protocol["grouping"], "groups": groups}
    summary = {
        "plan_version": "mtc-experiment-plan-v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "p2_status": "COMPLETE", "source_snapshot": str(snapshot), "source_cutoff_utc": manifest["source_cutoff_utc"],
        "protocol_version": protocol["protocol_version"], "split_seed": protocol["split"]["seed"],
        "research_principle": protocol["research_principle"], "statistical_basis": "own_frozen_MTC_inventory",
        "observations": len(rows), "app_sessions": len({r["app_session_id"] for r in rows}),
        "observed_installations": len({r["profile"]["collector_install_id"] for r in rows}),
        "model_families": len({model_key(r) for r in rows}), "model_os_profiles": len({model_os_key(r) for r in rows}),
        "leakage_groups": len(groups), "multi_model_groups": sum(g["multi_model_link"] for g in groups),
        "primary_paired_observations": sum(r["view"] == "paired_244" for r in rows),
        "primary_model_os_representatives": len(representatives),
        "paired_leakage_groups": len({membership[r["sample_id"]][0] for r in rows if r["view"] == "paired_244"}),
        "split_counts": counts, "cross_split_known_link_violations": 0,
        "fact_sidecar_rows": len(facts), "verified_label_rows": sum(f["label_status"] == "verified" for f in facts.values()),
        "verified_identity_rows": sum(f["identity_status"] == "verified" for f in facts.values()),
        "reference_fact_rows": sum(f["reference_status"] == "no_active_intervention_recorded" for f in facts.values()),
        "declared_scenario_repetitions": len(scenarios), "qualified_two_state_scenarios": sum(s["data_contract_status"] == "QUALIFIED" for s in scenarios),
        "detection_class_group_counts": detection_counts,
        "detection_data_group_totals": detection_group_totals,
        "detection_data_prerequisites_met": detection_data_ready,
        "task_gates": {
            "rule_discovery": "READY_FOR_P3" if admitted_discovery else "NOT_EVALUATED_INSUFFICIENT_GROUPS",
            "rule_development": "REFERENCE_COUNTEREXAMPLES_ONLY_NO_DETECTION_METRICS",
            "reserved_rule_validation": "LOCKED_PENDING_FROZEN_RULES_AND_P6_PROTOCOL",
            "verified_reference_validation": "FACTS_PRESENT_REVIEW_TASK_SCOPE" if any(f["reference_status"] == "no_active_intervention_recorded" for f in facts.values()) else "NOT_EVALUATED_NO_INDEPENDENT_REFERENCE_RECORDS",
            "paired244_detection_metrics": "NOT_EVALUATED_REQUIRES_LABELS_IDENTITIES_SCENARIOS_P4_P5_P6"},
        "pre_split_exposure": protocol["pre_split_exposure"], "stage_capabilities": protocol["stage_capabilities"],
        "candidate_support_floor": protocol["candidate_support_floor"],
        "sampling_boundary": "One earliest QC-paired representative per exact model/OS for the primary reference cohort; support and uncertainty must aggregate by leakage group. No physical independence claim.",
        "annotation_boundary": "No facts inferred from MTC origin, legacy labels, model scores, rule alerts or browser differences. Supplied verified assertions require upstream evidence review; file existence is only a join contract check.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=output.name + ".building-", dir=output.parent))
    try:
        write_json(stage / "summary.json", summary)
        write_json(stage / "group_registry.json", registry)
        write_json(stage / "admission_report.json", {"task_gates": summary["task_gates"],
                   "discovery_input_count": sum(r["task_admission"]["rule_discovery"] == "ADMITTED" for r in inventory),
                   "development_input_count": sum(r["task_admission"]["rule_development"] == "ADMITTED" for r in inventory),
                   "reference_fact_qualified_rows": sum(r["task_admission"]["verified_reference_observation"] == "FACT_QUALIFIED" for r in inventory),
                   "detection_fact_qualified_rows": len(scenario_qualified),
                   "detection_data_prerequisites_met": detection_data_ready,
                   "minimum_group_floors": {k: v for k, v in protocol["admission"].items() if k.startswith("minimum_")},
                   "statistical_sufficiency_proven": False, "metric_execution_enabled": False,
                   "input_admission_does_not_override_per_field_quality": True})
        write_jsonl(stage / "sample_registry.jsonl", inventory)
        write_jsonl(stage / "scenario_registry.jsonl", scenarios)
        write_jsonl(stage / "split_manifest.jsonl", [{k: r[k] for k in ("sample_id", "group_id", "split", "analysis_role", "source_view")} for r in inventory])
        write_jsonl(stage / "coverage_by_split.jsonl", coverage(rows, membership, representatives))
        write_jsonl(stage / "discovery_inputs.jsonl", select_task_inputs(rows, inventory, "rule_discovery"))
        write_jsonl(stage / "development_inputs.jsonl", select_task_inputs(rows, inventory, "rule_development"))
        write_json(stage / "reserved_validation_LOCK.json", {"status": "LOCKED", "input_manifest_exported": False,
                   "requires": ["frozen_rule_catalog_and_versions", "predeclared_evaluation_protocol", "exposure_disclosure"],
                   "rule": "Never tune or select rules on this split; new links require a new version/conflict audit, not silent reallocation."})
        write_json(stage / "input_manifest.json", {"source_snapshot": str(snapshot), "source_p1_manifest": manifest,
                   "source_views": inputs, "facts_path": str(facts_path) if facts_path else None,
                   "accepted_facts_evidence_reference_base": str(facts_path.parent) if facts_path else None,
                   "facts_binding": "sample_id+App session+App payload+Browser payload", "integrity_scope": "P1 row accounting and existing payload bindings; no repeated full-file hash scan"})
        write_json(stage / "protocol.json", protocol)
        write_json(stage / "fact_schema.json", read_json(FACT_SCHEMA))
        write_jsonl(stage / "accepted_facts.jsonl", [facts[k] for k in sorted(facts)])
        shutil.copyfile(Path(__file__), stage / "builder.py")
        for file in stage.iterdir():
            if file.is_file():
                file.chmod(0o444)
        stage.rename(output)
    except Exception:
        shutil.rmtree(stage)
        raise
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    protocol = load_protocol(args.protocol)
    snapshot = args.snapshot_dir or resolve_path(protocol["source_snapshot"])
    result = build_plan(snapshot, args.output_dir, args.protocol, args.facts.resolve() if args.facts else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
