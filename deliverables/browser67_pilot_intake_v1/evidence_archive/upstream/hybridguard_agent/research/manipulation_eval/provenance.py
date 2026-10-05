"""S03 static source/role/family registry and synthetic-testable scope gates.

This module does not evaluate relation predicates, aggregate alerts, read sample
files, or implement S04 policy. Scope gates consume only declared current fields.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import csv
from itertools import combinations, product
import json
import math
from pathlib import Path
import re
import sys

from hybridguard_agent.evidence.paired244 import field_contract, legacy_field_map, valid_type
from hybridguard_agent.research.mtc_closed_resource import model_token, gpu_family
from hybridguard_agent.research.manipulation_eval.registry_output import validate_destinations

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "hybridguard_agent/config"
STUDY_CONFIG = CONFIG / "formal_manipulation_v1"
OUTPUT = ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923/03_registry"
VERSION = "formal-manipulation-source-registry-v1"
POLICY_VERSION = "formal-manipulation-applicability-v1"
HEAD = "b3d8badee44577787bdcd3cb22d70a155b1bb613"
GROUPS = ("E", "O_u", "H", "C")
ROLES = ("alert_candidate", "observation_only", "context_only", "collector_consistency", "deployment_policy")
COMMON_GATES = ["registered_current_fields", "explicit_observed_and_quality", "typed_finite_non_sentinel",
                "product_specific_ua_scope", "unmodified_agent_origin_not_inferred", "gpu_render_path_not_inferred",
                "browser_evidence_only_if_present", "source_group_never_changes_semantic_gate"]
PROPOSED_CANDIDATES = {"NW-001", "NW-002", "NVW-001", "NVW-002", "NW-005",
                       "OFFDER-OS-001", "OFFDER-OS-002", "OFFDER-GPU-001"}
CONTEXT_E = {"NVW-005", "PHYS-005", "PHYS-006", "SCENE-001"}
CONTEXT_O = {"OFFDER-DEVCONFIG-001", "OFFDER-NET-001"}
GPU_PARAMS = {"families": ["adreno", "mali", "powervr", "tegra", "vivante"],
              "software_tokens": ["swiftshader", "llvmpipe", "softpipe", "swrast", "lavapipe", "swangle"]}


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows))


def provenance_group(rule):
    lane = rule["source_lane"]
    if lane == "device_mined_rule":
        return "E"
    if lane == "official_derived_semantic_rule":
        return "H" if rule.get("empirical_selection_applied") is True else "O_u"
    if lane in {"collector_derived_consistency", "collector_context", "project_deployment_policy"}:
        return "C"
    raise ValueError("Unreviewed source lane: " + str(lane))


def decision_role(rule):
    # Explicit semantic review; ACTIVE and provenance do not imply alert eligibility.
    rid, lane = rule["rule_id"], rule["source_lane"]
    if lane == "project_deployment_policy":
        return "deployment_policy"
    if lane == "collector_derived_consistency" or rid in {"CORE-002", "OFFDER-BRIDGE-001"}:
        return "collector_consistency"
    if lane == "collector_context" or rid in CONTEXT_E | CONTEXT_O:
        return "context_only"
    return "observation_only"


def review_profile(rule):
    rid, pred = rule["rule_id"], rule["predicate"]
    if rid == "NW-001":
        return "app_model"
    if rid in {"NW-002", "OFFDER-OS-001"}:
        return "app_os"
    if rid == "NVW-001":
        return "system_model"
    if rid in {"NVW-002", "OFFDER-OS-002"}:
        return "system_os"
    if rid in {"NW-005", "OFFDER-GPU-001"}:
        return "gpu"
    if rid == "P3-UA-REDUCED-BROWSER":
        return "browser_os"
    if pred == "sensor_presence":
        return "sensor_positive"
    if rid in {"P3-UA-DEFAULT", "P3-UA-SETTINGS", "OFFDER-UA-002"}:
        return "ua_snapshot"
    if rule["evidence_family"] == "screen_geometry":
        return "screen_geometry"
    if rid in {"NW-006", "WVWEB-004", "OFFDER-UA-001", "WVWEB-002"}:
        return "ua_surface_context"
    if rid in {"NW-007", "OFFDER-TOUCH-001"}:
        return "touch_context"
    if rid in {"CORE-002", "OFFDER-BRIDGE-001"}:
        return "bridge"
    if pred == "network_context_v1":
        return "network_context"
    if rule["source_lane"] == "project_deployment_policy":
        return "deployment"
    return "declared_fields"


PROFILE_REVIEW = {
    "app_model": {
        "conditions": ["explicit unique non-K model-before-Build token", "Native model is interpretable", "current settings/default UA chain known", "UA origin and stability throughout capture established"],
        "unobservable": ["unmodified_default_or_authorized_override_boundary_during_capture"],
        "counterexamples": ["legitimate per-instance or DevTools UA override", "UA changed after settings snapshot", "OEM model alias or reduced K token"],
        "rationale": "A differing explicit model is a relation observation under the unchanged-Native threat model. The allowed fields cannot establish an atomic default-UA chain; equality of settings/default snapshots is insufficient. No alert role is granted.",
        "sources": ["android-build-api", "android-websettings-api", "android-webview-ua-reduction", "s03-devtools-ua-override"]},
    "app_os": {
        "conditions": ["explicit parseable Native version and App Android token", "App/WebView reduction excluded independently of Browser milestones", "UA origin and capture-time stability established"],
        "unobservable": ["unmodified_default_or_authorized_override_boundary_during_capture"],
        "counterexamples": ["legitimate custom UA", "WebView reduced Android 10/K", "opaque or preview Build.VERSION.RELEASE", "UA changed after host snapshot"],
        "rationale": "Parsed OS inequality alone does not exclude legitimate override. Native RELEASE is not guaranteed numeric, and WebView scope is distinct from external Chrome. Retain observation with UNKNOWN alert prerequisites.",
        "sources": ["android-build-version-api", "android-websettings-api", "android-webview-ua-reduction", "s03-devtools-ua-override"]},
    "system_model": {
        "conditions": ["explicit Dalvik grammar and unique model-before-Build token", "property is the unmodified default for this historical implementation"],
        "unobservable": ["unmodified_system_http_agent_origin"],
        "counterexamples": ["legitimate System.setProperty override retaining Dalvik grammar", "OEM/default grammar variation", "preview builds omit MODEL"],
        "rationale": "http.agent is a mutable process property, not current WebView JS UA. Its default shares Build.MODEL with Native, so it is neither an independent identity root nor an executable alert premise here.",
        "sources": ["closed-aosp-http-agent", "s03-system-property", "android-build-api"]},
    "system_os": {
        "conditions": ["explicit Dalvik Android grammar", "Native version parses without guessing", "unmodified property origin established"],
        "unobservable": ["unmodified_system_http_agent_origin"],
        "counterexamples": ["legal http.agent override", "vendor non-Dalvik agent", "preview or opaque RELEASE string"],
        "rationale": "Only a Dalvik-scoped comparison is interpretable. Current strings cannot establish that the process property retained its default; do not fill this gap using run logs or tool configuration.",
        "sources": ["closed-aosp-http-agent", "s03-system-property", "android-build-version-api"]},
    "gpu": {
        "conditions": ["unmasked meaningful renderer strings", "Native hardware family unambiguous", "software/host/remote or hybrid rendering exclusions established", "ANGLE alone never a contradiction"],
        "unobservable": ["same_physical_rendering_path_and_exclusion_of_legitimate_host_or_remote_rendering"],
        "counterexamples": ["SwiftShader/lavapipe/llvmpipe software rendering", "legitimate emulator host GPU", "remote or hybrid rendering", "privacy-masked or ambiguous renderer", "ANGLE translation on Android"],
        "rationale": "NW-005 compares named families; OFFDER-GPU-001 matches desktop backend markers. They share renderer evidence but are not equivalent. Strings do not establish the required physical rendering path; both remain observations.",
        "sources": ["khronos-webgl-renderer-info", "s03-swiftshader", "s03-angle", "s03-emulator-graphics"]},
    "browser_os": {
        "conditions": ["real admitted Browser fields present", "explicit parseable Android UA", "reduced shape is not interpreted as actual OS"],
        "unobservable": ["unmodified_browser_ua_origin"],
        "counterexamples": ["Chrome Android reduced OS/model", "older opt-in reduction", "legitimate custom Browser UA", "other browser product/version behavior"],
        "rationale": "Frozen v3 uses >=107 and Android 10 without checking K. Primary rollout distinguishes desktop M107 from Android M110; this S03 overlay records the discrepancy, guards reduced shapes, and never rewrites the frozen predicate or fabricates Browser evidence.",
        "sources": ["s03-chrome-ua-timeline", "s03-devtools-ua-override"]},
    "sensor_positive": {
        "conditions": ["boolean has_sensor and positive integer type list available", "positive antecedent only"],
        "unobservable": [],
        "counterexamples": ["permission or wake-up/default sensor differences", "dynamic sensors change between calls", "false antecedent is not absence proof"],
        "rationale": "The positive flag-to-list implication is a project consistency observation, not independent physical identity or manipulation evidence.",
        "sources": ["android-sensor-manager"]},
    "ua_snapshot": {
        "conditions": ["both current strings available", "same instance and capture interval would be required for a strong equality claim"],
        "unobservable": ["atomic_same_instance_ua_capture"],
        "counterexamples": ["custom per-instance UA", "UA change between host snapshot and JS probe"],
        "rationale": "Default, instance settings and JS UA are distinct observations; their equality is not a universal invariant. The settings snapshot is captured before the JS probe.",
        "sources": ["android-websettings-api"]},
    "screen_geometry": {
        "conditions": ["positive dimensions/DPR", "same window/zoom/display context would be needed for a universal relation"],
        "unobservable": ["equivalent_window_page_zoom_and_display_context"],
        "counterexamples": ["split window or foldable configuration", "page zoom", "orientation or app display differs from physical mode"],
        "rationale": "The Native field named physical resolution is collected from App DisplayMetrics. Retain the frozen 1 CSS-pixel arithmetic tolerance as a project choice, not an official physical equality or tuned alert threshold.",
        "sources": ["android-display-metrics", "cssom-view-dpr"]},
    "ua_surface_context": {
        "conditions": ["interpretable UA/platform fields"], "unobservable": [],
        "counterexamples": ["legitimate desktop-UA compatibility override", "authorized headless/test usage", "missing wv marker under custom UA"],
        "rationale": "Lexical desktop/script/wv markers neither authenticate product identity nor prove unauthorized manipulation. No independent alert role.",
        "sources": ["android-websettings-api", "s03-devtools-ua-override"]},
    "touch_context": {
        "conditions": ["UA string and nonnegative integer maxTouchPoints"], "unobservable": [],
        "counterexamples": ["non-touch Android device", "external input devices", "browser exposure/privacy differences"],
        "rationale": "Zero touch is a legal observation and cannot by itself justify a manipulation alert.", "sources": []},
    "bridge": {
        "conditions": ["explicit boolean bridge state", "fixed App177 study surface, never infer route from free metadata"],
        "unobservable": [], "counterexamples": ["intentionally disabled bridge", "collection failure or alternate route"],
        "rationale": "Bridge presence is collector consistency. The old topology assumption is project-specific and not an independently observed attack fact.", "sources": ["android-webview-api"]},
    "network_context": {
        "conditions": ["positive integer API level", "API >=23 for the collector capabilities path", "typed transport list/flags"],
        "unobservable": [], "counterexamples": ["VPN", "network handover", "no active network", "legacy API fallback"],
        "rationale": "Network flags share one snapshot and describe dynamic context, not attack or safety.", "sources": []},
    "deployment": {
        "conditions": ["registered package/release fields available", "fixed historical MTC deployment scope only"],
        "unobservable": [], "counterexamples": ["old 1.6.3 attack-collection APK", "debug/grey release or manual install"],
        "rationale": "The retained MTC code9/code11 policy is not the App177 attack release contract. A mismatch is deployment-only and does not alter S01 labels.", "sources": []},
    "declared_fields": {
        "conditions": ["registered predicate dependencies observed, finite and correctly typed"],
        "unobservable": [], "counterexamples": ["collector/platform behavior rather than manipulation", "missing or defaulted observation is unknown"],
        "rationale": "Keep the documented relation, collector invariant or context in its own role. ACTIVE and COUNTEREXAMPLE do not grant an alert role.", "sources": []},
}


def effective_fields(rule, profile):
    fields = set(rule["dependencies"])
    if profile in {"app_model", "app_os"}:
        mapping = legacy_field_map()
        fields.update(mapping[p] for p in ("webview_data.default_ua_native", "webview_data.settings_user_agent"))
    return sorted(fields)


def source_documents():
    documents = {}
    for name in ("mtc_p3_semantic_sources.v1.json", "paired244_review_sources.v1.json"):
        for row in read_json(CONFIG / name)["sources"]:
            documents[row["id"]] = {**row, "registry_ref": "hybridguard_agent/config/" + name}
    for row in read_json(ROOT / "deliverables/mtc_p6_20260923/SOURCE_COVERAGE.json")["embedded_sources"]:
        documents.setdefault(row["id"], {**row, "registry_ref": "deliverables/mtc_p6_20260923/SOURCE_COVERAGE.json#embedded_sources"})
    for line in (ROOT / "google_official_kb/official_sources.jsonl").read_text().splitlines():
        row = json.loads(line)
        documents.setdefault(row["source_id"], {**row, "registry_ref": "google_official_kb/official_sources.jsonl"})
    review = read_json(STUDY_CONFIG / "primary_source_review.json")
    for doc in review["documents"]:
        for sid in doc["source_ids"]:
            documents[sid] = {**documents.get(sid, {}), **doc}
    return documents


def source_ref(sid, documents):
    doc = documents.get(sid, {})
    return {"document_id": sid, "url": doc.get("url"), "version": doc.get("document_version", "UNKNOWN"),
            "review_status": doc.get("review_status", "LOCAL_REFERENCE_ONLY_NOT_REFRESHED_S03"),
            "recorded_access_date": doc.get("accessed_at"), "applicable_products": doc.get("applicable_products", ["UNKNOWN"]),
            "definition_scope": doc.get("verified_scope", doc.get("scope", doc.get("notes", "UNKNOWN"))),
            "registry_ref": doc.get("registry_ref", "hybridguard_agent/config/formal_manipulation_v1/primary_source_review.json")}


def tolerance_record(rule):
    pred = rule["predicate"]
    if "css_pixel_tolerance" in rule.get("parameters", {}):
        return {"value": rule["parameters"]["css_pixel_tolerance"], "unit": "CSS pixel",
                "origin": "PROJECT_FIXED_ARITHMETIC_TOLERANCE_NOT_OFFICIAL_NOT_FITTED",
                "reference": "hybridguard_agent/config/mtc_p3_discovery_protocol.v1.json#tolerance_policy"}
    if rule["rule_id"] in {"PHYS-005", "SCENE-001"}:
        return {"origin": "LEGACY_PROJECT_CONTEXT_THRESHOLD_NOT_RECALIBRATED",
                "reference": "hybridguard_agent/rules/executor.py::_evaluate", "use": "context only; never alert threshold"}
    if pred in {"gpu_family", "model_build_token"}:
        return {"origin": "PROJECT_LITERAL_NORMALIZATION", "parameters": rule.get("parameters", {}),
                "reference": "hybridguard_agent/research/mtc_closed_resource.py"}
    return {"origin": "EXACT_PREDICATE_OR_PROJECT_PARSER_NO_NEW_NUMERIC_TOLERANCE",
            "parameters": rule.get("parameters", {}), "legacy_semantic_tolerance": rule.get("legacy_relation", {}).get("tolerance"),
            "reference": "paired244_rule_catalog.v3.json#" + rule["rule_id"]}


def implementation_reference(rule):
    if rule.get("implementation") == "mtc-closed-resource-predicates-v1":
        return "hybridguard_agent/research/mtc_closed_resource.py::evaluate"
    if rule.get("implementation") == "paired244-legacy-backlog-v1":
        return "hybridguard_agent/rules/legacy_backlog.py::evaluate_reviewed_rule"
    if rule["origin"] == "p3_research":
        return "hybridguard_agent/research/mtc_p3_candidates.py::evaluate_candidate"
    if rule["origin"] == "legacy_official":
        return "hybridguard_agent/official_semantics/evaluator.py::_evaluate_compiled"
    return "hybridguard_agent/rules/paired244.py::execute_paired_rules / hybridguard_agent/rules/executor.py::_evaluate"


def build_registry():
    catalog = read_json(CONFIG / "paired244_rule_catalog.v3.json")
    active = [r for r in catalog["rules"] if r["status"] == "ACTIVE"]
    docs = source_documents()
    rows, scopes, roles, uncertainties = [], [], [], []
    for rule in active:
        rid, group, profile = rule["rule_id"], provenance_group(rule), review_profile(rule)
        review = PROFILE_REVIEW[profile]
        role = decision_role(rule)
        original_refs = list(dict.fromkeys(rule.get("official_source_ids", []) + rule.get("legacy_official_source_ids", [])))
        all_refs = list(dict.fromkeys(original_refs + review["sources"]))
        references = [source_ref(sid, docs) for sid in all_refs]
        screened = rule.get("empirical_selection_applied") is True
        screening = ("FROZEN_DISCOVERY_DEVELOPMENT_SCREEN" if screened else
                     "LEGACY_EMPIRICAL_HISTORY_NOT_FULLY_RECORDED" if group == "E" else "NOT_MARKED_IN_CURRENT_CATALOG")
        family = "native_app_gpu_family" if rid in {"NW-005", "OFFDER-GPU-001", "P3-GPU-COPY"} else rule["evidence_family"]
        local_uncertainties = []
        if group == "E" and not screened:
            local_uncertainties.append(("LEGACY_EMPIRICAL_HISTORY_NOT_FULLY_RECORDED", "Current E classification is retained; original per-rule discovery/version provenance is incomplete."))
        missing_versions = [r["document_id"] for r in references if "UNKNOWN" in r["version"]]
        if missing_versions:
            local_uncertainties.append(("DOCUMENT_REVISION_UNKNOWN", "Immutable document revisions are unknown for: " + ", ".join(missing_versions)))
        unrefreshed = [r["document_id"] for r in references if r["review_status"] != "VERIFIED_CURRENT_PRIMARY"]
        if unrefreshed:
            local_uncertainties.append(("LOCAL_SOURCE_REFERENCE_NOT_REFRESHED", "Bounded S03 review retained prior references without claiming current verification: " + ", ".join(unrefreshed)))
        if profile == "browser_os":
            local_uncertainties.append(("BROWSER_UA_MILESTONE_SCOPE_DISCREPANCY", "v3 >=107/Android10 is broader than Android phase6 M110/K; v3 is immutable and the rule remains observation-only."))
        for condition in review["unobservable"]:
            local_uncertainties.append(("ALERT_PRECONDITION_NOT_OBSERVABLE", condition))
        uncertainty_ids = []
        for index, (code, detail) in enumerate(local_uncertainties, 1):
            uid = rid + ":U" + str(index)
            uncertainty_ids.append(uid)
            uncertainties.append({"uncertainty_id": uid, "rule_id": rid, "provenance_group": group, "code": code,
                                  "detail": detail, "status": "RETAINED", "effect": "observation/unknown only; no source reassignment or extra collection"})
        source = {"schema_version": VERSION, "study_version": "formal-manipulation-v1", "rule_id": rid,
                  "catalog_version": catalog["catalog_version"], "rule_version": rule["version"], "status_in_catalog": rule["status"],
                  "original_source_lane": rule["source_lane"], "historical_pre_review_lane": rule.get("original_source_lane"),
                  "provenance_group": group, "semantic_origin": {"E": "empirical_or_legacy_device_relation_with_project_assumptions",
                    "O_u": "official_definitions_plus_researcher_derivation_not_marked_for_current_empirical_screening",
                    "H": "official_definitions_plus_researcher_derivation_and_empirical_screening",
                    "C": "collector_or_project_context_and_deployment_contract"}[group],
                  "official_document_id": all_refs, "official_document_version": {r["document_id"]: r["version"] for r in references},
                  "source_url": list(dict.fromkeys(r["url"] for r in references if r["url"])),
                  "official_definitions": references, "original_reference_ids": original_refs,
                  "common_semantic_gate_reference_ids": review["sources"],
                  "project_assumption": [rule["limitations"], review["rationale"]],
                  "researcher_derivation": {"predicate": rule["predicate"], "parameters": copy.deepcopy(rule.get("parameters", {})),
                                             "implementation_ref": implementation_reference(rule), "is_official_risk_verdict": False},
                  "empirically_screened": screened, "screening_scope": screening,
                  "catalog_empirical_selection_flag": rule.get("empirical_selection_applied"),
                  "selection_basis": "stored catalog flag and admission mode only; no outcomes used for role selection",
                  "discovery_split_ref": ("hybridguard_agent/artifacts/mtc_closed_resource_study_20260922" if rule.get("closure_study") else
                                            catalog["source_p3_run"]) if screened else "UNKNOWN_OR_NOT_MARKED",
                  "tolerance_source": tolerance_record(rule), "dependencies": list(rule["dependencies"]),
                  "gate_dependencies": effective_fields(rule, profile), "original_evidence_family": rule["evidence_family"],
                  "decision_family": family, "applicability_id": "scope:" + rid, "decision_role": role,
                  "proposed_alert_candidate_reviewed": rid in PROPOSED_CANDIDATES,
                  "known_counterexamples": list(dict.fromkeys(review["counterexamples"] + rule.get("legacy_relation", {}).get("counterexamples", []) + [rule["limitations"]])),
                  "rationale": review["rationale"], "unobservable_alert_preconditions": review["unobservable"],
                  "uncertainty_ids": uncertainty_ids, "review_status": "REVIEWED_WITH_LIMITS" if uncertainty_ids else "REVIEWED",
                  "O_u_definition": "unmarked-for-current-screening official-derived; not pure official rules" if group == "O_u" else None}
        rows.append(source)
        scopes.append({"applicability_id": source["applicability_id"], "rule_id": rid, "profile": profile,
                       "required_fields": source["gate_dependencies"], "predicate_dependencies": source["dependencies"],
                       "conditions": review["conditions"], "unobservable_alert_preconditions": review["unobservable"],
                       "scope_gate_executable": True, "alert_prerequisites_fully_executable": not review["unobservable"],
                       "missing_or_unverifiable_state": "UNKNOWN", "decision_role": role,
                       "parameters": copy.deepcopy(rule.get("parameters", {}))})
        roles.append({k: source[k] for k in ("rule_id", "provenance_group", "decision_role", "decision_family", "applicability_id",
                    "proposed_alert_candidate_reviewed", "known_counterexamples", "rationale", "unobservable_alert_preconditions")})
    return catalog, rows, scopes, roles, uncertainties


def source_conditions(rows):
    groups = {g: sorted(r["rule_id"] for r in rows if r["provenance_group"] == g) for g in GROUPS}
    conditions = []
    for bits in product((0, 1), repeat=3):
        included = [g for g, bit in zip(("O_u", "H", "E"), bits) if bit]
        ids = sorted(set(groups["C"]).union(*(groups[g] for g in included)))
        conditions.append({"condition_id": "SRC-" + "".join(map(str, bits)), "bit_order": ["O_u", "H", "E"],
                           "included_groups": ["C", *included], "rule_ids": ids, "rule_count": len(ids),
                           "common_C_ids": groups["C"], "common_gate_ids": COMMON_GATES,
                           "applicability_policy_version": POLICY_VERSION, "selection_mode": "source_group_ablation",
                           "official_knowledge_completely_removed": False})
    return {"version": VERSION, "groups": groups, "conditions": conditions,
            "four_source_mapping": {"C": "SRC-000", "B0": "SRC-000", "E": "SRC-001", "O": "SRC-110", "EO": "SRC-111"},
            "execution_deduplication": "four-source aliases reuse eight unique source conditions; no duplicate sample runs",
            "claim_boundary": "Removing official-derived predicates retains shared semantic gates. This is source-group ablation, not complete removal of official knowledge."}


# Exact duplicate classifications compare normalized relation outcomes on the
# common declared valid domain, not source prose or raw response message strings.
EXACT = {
    frozenset(("NW-002", "OFFDER-OS-001")): "same native.android_major / web.ua_android_major facts, equality complement normalized by paired244",
    frozenset(("NVW-002", "OFFDER-OS-002")): "same Native / system-http Android major facts, equality complement normalized by paired244",
    frozenset(("NVW-005", "OFFDER-DEVCONFIG-001")): "same debuggable AND cleartext boolean context and normalized outcomes",
    frozenset(("CORE-002", "OFFDER-BRIDGE-001")): "same bridge boolean within the fixed FeatureApp projection contract; no sensor-count branch",
}


def family_registry(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["decision_family"]].append(row)
    families = [{"decision_family": family, "rule_ids": sorted(r["rule_id"] for r in members),
                 "original_evidence_families": sorted({r["original_evidence_family"] for r in members}),
                 "provenance_groups": sorted({r["provenance_group"] for r in members}),
                 "alert_candidate_ids": sorted(r["rule_id"] for r in members if r["decision_role"] == "alert_candidate"),
                 "shared_evidence_policy": "one family identity across sources; multiplicity never adds independent support",
                 "related_does_not_imply_equivalent": True} for family, members in sorted(groups.items())]
    overlaps = []
    for a, b in combinations(sorted(rows, key=lambda r: r["rule_id"]), 2):
        shared = sorted(set(a["dependencies"]) & set(b["dependencies"]))
        same_family = a["decision_family"] == b["decision_family"]
        pair = frozenset((a["rule_id"], b["rule_id"]))
        relation = ("exact_duplicate_on_common_valid_domain" if pair in EXACT else "related_not_equivalent" if same_family
                    else "shared_input_distinct_claim" if shared else "no_declared_input_overlap")
        note = EXACT.get(pair, "shared family does not assert predicate equivalence" if same_family else
                         "field overlap does not prove either equivalent predicates or statistical independence")
        if pair == frozenset(("OFFDER-UA-002", "P3-UA-DEFAULT")):
            note = "same UA pair, but OFFDER trims strings via derived facts and P3 uses exact raw equality; not exactly equivalent"
        if "OFFDER-GPU-001" in pair and "NW-005" in pair:
            note = "desktop-backend marker predicate versus named hardware-family comparison; related GPU evidence, not equivalent"
        overlaps.append({"rule_a": a["rule_id"], "group_a": a["provenance_group"], "rule_b": b["rule_id"],
                         "group_b": b["provenance_group"], "family_a": a["decision_family"], "family_b": b["decision_family"],
                         "relation": relation, "shared_fields": shared, "same_decision_family": same_family,
                         "independent_support_from_source_membership": False, "reason": note})
    return {"version": VERSION, "families": families, "overlap_edges": [r for r in overlaps if r["relation"] != "no_declared_input_overlap"],
            "exact_equivalence_scope": "normalized relation outcome on common valid fields; availability envelopes and explanatory text can differ",
            "boundary": "Static membership only. No alert aggregation, threshold or prediction implementation."}, overlaps


def _finite_json(value):
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_json(v) for v in value)
    if isinstance(value, dict):
        return all(_finite_json(v) for v in value.values())
    return value is None or type(value) in (str, int, bool)


def _version(value, *, agent=False):
    pattern = r"\bAndroid\s+(\d+)(?:\.\d+)*(?=[; )])" if agent else r"(?:Android\s+)?(\d+)(?:\.\d+)*"
    matches = re.findall(pattern, value) if agent else re.fullmatch(pattern, value)
    return (int(matches[0]) if len(matches) == 1 else None) if agent else (int(matches.group(1)) if matches else None)


def evaluate_applicability(scope, payload):
    """Only scope/availability, never a contradiction, alert, score or prediction."""
    def result(status, reason):
        return {"applicability_id": scope["applicability_id"], "status": status, "reason": reason,
                "decision_role": scope["decision_role"], "unobservable_alert_preconditions": scope["unobservable_alert_preconditions"]}
    fields, contract = {}, field_contract()
    for field in scope["required_fields"]:
        value = payload.get("features", {}).get(field)
        try:
            good_type = valid_type(value, contract[field])
        except (ValueError, OverflowError, KeyError):
            good_type = False
        if (payload.get("field_status", {}).get(field) != "observed" or
                payload.get("field_quality", {}).get(field) != "observed_value" or
                not good_type or not _finite_json(value)):
            return result("UNKNOWN", "required_current_field_unavailable")
        if isinstance(value, str) and value.strip().casefold() in {"", "unknown", "null", "unsupported", "error", "not available"}:
            return result("UNKNOWN", "uninterpretable_placeholder")
        if field.endswith((".device_memory", ".hardware_concurrency")) and value <= 0:
            return result("UNKNOWN", "ambiguous_zero_sentinel")
        if field.endswith((".device_pixel_ratio", ".color_depth", ".pixel_depth")) and value <= 0:
            return result("UNKNOWN", "nonpositive_display_measurement")
        fields[field] = value
    profile = scope["profile"]
    by_leaf = {f.rsplit(".", 1)[-1]: value for f, value in fields.items()}
    if profile in {"app_model", "app_os", "browser_os"}:
        ua = by_leaf["user_agent"]
        # Shape guards protect any uninformative K exposure, including opt-in
        # reduction before rollout. Milestones never authenticate one session.
        if re.search(r"\bAndroid\s+10(?:\.0)?;\s*K(?:;|\))", ua, re.I):
            return result("NOT_APPLICABLE", "reduced_shape_is_not_actual_os_or_model")
        if profile == "app_model":
            _, status, reason = model_token(ua)
            if status:
                return result(status, reason)
        elif _version(by_leaf["os_version"]) is None or _version(ua, agent=True) is None:
            return result("UNKNOWN", "opaque_or_unparseable_android_version")
        if profile != "browser_os" and by_leaf["settings_user_agent"] != by_leaf["default_ua_native"]:
            return result("NOT_APPLICABLE", "explicit_custom_host_ua_configuration")
        return result("UNKNOWN", "ua_origin_and_capture_stability_not_established_by_current_fields")
    if profile in {"system_model", "system_os"}:
        ua = by_leaf["system_http_agent"]
        if not ua.startswith("Dalvik/"):
            return result("NOT_APPLICABLE", "outside_dalvik_system_agent_scope")
        if profile == "system_model":
            _, status, reason = model_token(ua, require_dalvik=True)
            if status:
                return result(status, reason)
        elif _version(by_leaf["os_version"]) is None or _version(ua, agent=True) is None:
            return result("UNKNOWN", "unparseable_system_android_version")
        return result("UNKNOWN", "mutable_system_property_origin_unobserved")
    if profile == "gpu":
        texts = [v.casefold() for v in fields.values() if isinstance(v, str)]
        if any(token in text for text in texts for token in GPU_PARAMS["software_tokens"]):
            return result("NOT_APPLICABLE", "software_rendering_is_legal_not_hardware_comparison")
        _, state = gpu_family(by_leaf["native_gpu_renderer"], GPU_PARAMS)
        if state:
            return result(state, "native_hardware_family_unknown_or_masked")
        web_renderer = by_leaf["webgl_renderer"]
        web_family, _ = gpu_family(web_renderer, GPU_PARAMS)
        if web_family is None and not re.search(r"Direct3D|D3D(?:9|11|12)|Windows", web_renderer, re.I):
            return result("UNKNOWN", "web_renderer_family_or_backend_unknown")
        return result("UNKNOWN", "physical_host_remote_render_path_not_observable")
    if profile == "sensor_positive":
        values = [fields[f] for f in scope["predicate_dependencies"]]
        if any(type(v) is not int or v < 1 for v in values[1]):
            return result("UNKNOWN", "invalid_sensor_type_list")
        if values[0] is False:
            return result("NOT_APPLICABLE", "false_sensor_antecedent")
    if profile == "touch_context":
        touch = by_leaf["max_touch_points"]
        if touch < 0 or int(touch) != touch:
            return result("UNKNOWN", "invalid_touch_count")
    if profile == "network_context":
        api = by_leaf["os_api_level"]
        if api < 1 or int(api) != api:
            return result("UNKNOWN", "invalid_android_api")
        if api < scope["parameters"]["collector_caps_min_api"]:
            return result("NOT_APPLICABLE", "legacy_collector_network_fallback")
        if any(type(v) is not str or not v for v in by_leaf["active_transport_types"]):
            return result("UNKNOWN", "invalid_transport_list")
    if scope["unobservable_alert_preconditions"]:
        return result("UNKNOWN", "required_semantic_context_unobserved")
    return result("SUPPORTED", "declared_observation_scope_only_not_alert_eligibility")


def validate_registry(catalog, rows, scopes, roles, families, conditions):
    active = {r["rule_id"]: r for r in catalog["rules"] if r["status"] == "ACTIVE"}
    ids = [r["rule_id"] for r in rows]
    scope_index = {s["rule_id"]: s for s in scopes}
    family_members = [rid for f in families["families"] for rid in f["rule_ids"]]
    checks = {
        "all_57_active_exactly_once": len(ids) == len(set(ids)) == len(active) == 57 and set(ids) == set(active),
        "exact_source_counts": Counter(r["provenance_group"] for r in rows) == {"E": 23, "O_u": 9, "H": 14, "C": 11},
        "classification_uses_catalog_flags": all(r["provenance_group"] == provenance_group(active[r["rule_id"]]) for r in rows),
        "roles_and_applicability_are_separate": {r["rule_id"] for r in roles} == set(scope_index) == set(ids)
            and all(r["decision_role"] in ROLES and r["applicability_id"] == scope_index[r["rule_id"]]["applicability_id"] for r in rows),
        "all_fields_registered": all(set(r["gate_dependencies"]) <= set(field_contract()) for r in rows),
        "original_dependencies_and_families_preserved": all(r["dependencies"] == active[r["rule_id"]]["dependencies"]
            and r["original_evidence_family"] == active[r["rule_id"]]["evidence_family"] for r in rows),
        "each_rule_has_reason_counterexamples_and_scope": all(r["rationale"] and r["known_counterexamples"] and r["project_assumption"]
            and scope_index[r["rule_id"]]["conditions"] for r in rows),
        "no_unexecutable_alert_role": all(not r["unobservable_alert_preconditions"] for r in rows if r["decision_role"] == "alert_candidate"),
        "all_proposed_candidates_explicitly_reviewed": {r["rule_id"] for r in rows if r["proposed_alert_candidate_reviewed"]} == PROPOSED_CANDIDATES,
        "family_membership_exactly_once": Counter(family_members) == Counter(ids),
        "GPU_source_overlap_unified": next(f for f in families["families"] if f["decision_family"] == "native_app_gpu_family")["rule_ids"]
            == ["NW-005", "OFFDER-GPU-001", "P3-GPU-COPY"],
        "eight_unique_id_sets": len({tuple(c["rule_ids"]) for c in conditions["conditions"]}) == 8,
        "common_C_and_gates_identical": all(c["common_C_ids"] == conditions["groups"]["C"]
            and set(c["common_C_ids"]) <= set(c["rule_ids"]) and c["common_gate_ids"] == COMMON_GATES for c in conditions["conditions"]),
        "no_complete_official_knowledge_removal_claim": all(c["official_knowledge_completely_removed"] is False for c in conditions["conditions"]),
        "no_detector_or_policy_imported": not any(n.startswith(("hybridguard_agent.rules.", "hybridguard_agent.runtime.", "hybridguard_agent.official_semantics.")) for n in sys.modules),
    }
    return checks


def generate(output=None, config_dir=None):
    output, config_dir = validate_destinations(output, config_dir)
    catalog, rows, scopes, roles, uncertainties = build_registry()
    families, overlaps = family_registry(rows)
    conditions = source_conditions(rows)
    checks = validate_registry(catalog, rows, scopes, roles, families, conditions)
    if not all(checks.values()):
        raise ValueError("Registry validation failed: " + ", ".join(k for k, v in checks.items() if not v))
    applicability = {"policy_version": POLICY_VERSION, "common_gate_ids": COMMON_GATES, "scopes": scopes,
                     "inference_evidence": "only declared features/field_status/field_quality; no labels, tool, config, phase, logs or future post",
                     "ua_product_versions": {"chrome_desktop_phase5": 107, "chrome_android_phase6": 110, "webview_default_android_release": 17,
                                             "version_only_proves_current_ua_default": False, "frozen_v3_browser_min_major_unchanged": 107},
                     "gpu_software_tokens": GPU_PARAMS["software_tokens"], "new_alarm_policy_implemented": False}
    decisions = {"version": VERSION, "roles": roles, "proposed_candidate_ids": sorted(PROPOSED_CANDIDATES),
                 "alert_candidate_ids": [r["rule_id"] for r in rows if r["decision_role"] == "alert_candidate"],
                 "structural_limit": "Current fields do not close the necessary default-origin/render-path exclusions. All proposed alert candidates remain observations. This is not measured zero detection value."}
    for directory in (config_dir, output):
        directory.mkdir(parents=True, exist_ok=True)
        write_jsonl(directory / "source_registry.jsonl", rows)
        write_json(directory / "family_registry.json", families)
        write_json(directory / "applicability_policy.json", applicability)
        write_json(directory / "decision_roles.json", decisions)
        write_json(directory / "source_conditions.json", conditions)
    write_json(output / "primary_source_review.json", read_json(STUDY_CONFIG / "primary_source_review.json"))
    write_jsonl(output / "source_uncertainties.jsonl", uncertainties)
    with (output / "source_overlap_matrix.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(overlaps[0]))
        writer.writeheader()
        writer.writerows({**r, "shared_fields": "|".join(r["shared_fields"])} for r in overlaps)
    shared = [f for f in families["families"] if len(f["provenance_groups"]) > 1]
    counts = {}
    for group in GROUPS:
        selected = [r for r in rows if r["provenance_group"] == group]
        counts[group] = {"total_rules": len(selected), "decision_roles": {role: sum(r["decision_role"] == role for r in selected) for role in ROLES},
                         "alert_candidate_families": sorted({r["decision_family"] for r in selected if r["decision_role"] == "alert_candidate"}),
                         "shared_families": [f["decision_family"] for f in shared if group in f["provenance_groups"]],
                         "source_uncertainty_rule_ids": [r["rule_id"] for r in selected if any(u["rule_id"] == r["rule_id"] and u["code"] != "ALERT_PRECONDITION_NOT_OBSERVABLE" for u in uncertainties)],
                         "unimplementable_alert_gate_rule_ids": [r["rule_id"] for r in selected if r["unobservable_alert_preconditions"]],
                         "binary_detection_increment": "STRUCTURALLY_NO_ALERT_ROLE_NOT_AN_EMPIRICAL_VALUE_JUDGMENT"}
    summary = {"step": "S03", "version": VERSION, "external_review_head": HEAD, "catalog_total": len(catalog["rules"]),
               "active_rules": len(rows), "source_groups": counts, "decision_families": len(families["families"]),
               "shared_families": shared, "source_uncertainty_items": len(uncertainties),
               "source_uncertainty_codes": dict(Counter(r["code"] for r in uncertainties)),
               "overlap_pairs": len(overlaps), "exact_duplicate_pairs": sum(r["relation"] == "exact_duplicate_on_common_valid_domain" for r in overlaps),
               "alert_candidate_rules": sum(r["decision_role"] == "alert_candidate" for r in rows),
               "alert_candidate_families": len({r["decision_family"] for r in rows if r["decision_role"] == "alert_candidate"}),
               "proposed_candidates_demoted": sorted(r["rule_id"] for r in rows if r["proposed_alert_candidate_reviewed"] and r["decision_role"] != "alert_candidate"),
               "real_predictions": 0, "detector_calls": 0, "LLM_calls": 0, "performance_metrics": "NOT_EVALUATED",
               "S04_started": False, "thresholds_modified": False}
    write_json(output / "SUMMARY.json", summary)
    write_json(output / "STRUCTURAL_CHECKS.json", {"status": "PASS", "checks": checks})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = generate(args.output, args.config_dir)
    print(json.dumps({"active_rules": summary["active_rules"], "source_groups": {k: v["total_rules"] for k, v in summary["source_groups"].items()},
                      "alert_candidate_rules": summary["alert_candidate_rules"], "S04_started": False}, ensure_ascii=False))
