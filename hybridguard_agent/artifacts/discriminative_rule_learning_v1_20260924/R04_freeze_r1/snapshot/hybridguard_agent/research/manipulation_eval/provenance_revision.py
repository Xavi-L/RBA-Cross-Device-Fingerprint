"""S03-R v2: independent relation, research-risk and attribution contracts.

The CLI writes static registries and synthetic single-relation probes only.
It has no sample reader, alarm aggregator, performance evaluator or model call.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re

from hybridguard_agent.evidence.extractor import _android_major, _ua_android_major
from hybridguard_agent.evidence.paired244 import field_contract, legacy_field_map, valid_type
from hybridguard_agent.research.mtc_closed_resource import evaluate as evaluate_closed
from hybridguard_agent.research.mtc_closed_resource import gpu_family, model_token
from hybridguard_agent.research.manipulation_eval import provenance as v1
from hybridguard_agent.research.manipulation_eval.registry_output import validate_destinations

VERSION = "formal-manipulation-relation-risk-attribution-v2"
BASELINE = "66f9cdc2d40c41ccec0999c7a6c8d68c0a1b415f"
BASE_CONFIG = v1.STUDY_CONFIG
SCOPE_ID = "featureapp-reported-identity-coherence-research-v2"
MAPPING = legacy_field_map()
DEFAULT_UA = MAPPING["webview_data.default_ua_native"]
SETTINGS_UA = MAPPING["webview_data.settings_user_agent"]
REVIEWED = {
    "NW-001": ("alert_candidate", "app_model",
        "The existing development-screened explicit model relation is a limited reported-identity coherence hypothesis. Require an interpretable default model matching the Native naming convention; do not infer aliases or physical identity."),
    "NW-002": ("alert_candidate", "app_os",
        "Native versus full App Android-major disagreement is an interpretable identity-coherence risk hypothesis. Require an observed default/settings reference aligned with Native, without treating that snapshot as proof of authorization."),
    "OFFDER-OS-001": ("alert_candidate", "app_os",
        "Same scoped Android-major relation as NW-002, using its retained official-derived provenance; it is not another independent supporting family and not an official attack verdict."),
    "NVW-001": ("alert_candidate", "system_model",
        "A full Dalvik model token can be compared with Native as a process-property coherence hypothesis. A matching default-UA naming reference limits alias ambiguity. Mutability limits attribution, not literal comparability; this is not current JS UA or independent identity evidence."),
    "NVW-002": ("alert_candidate", "system_os",
        "The existing Native/Dalvik Android-major relation can supply a host-property coherence risk clue under the uniform relative-Native-reference scope. A legal property override remains a possible false positive and is not declared an attack."),
    "OFFDER-OS-002": ("alert_candidate", "system_os",
        "Same Native/Dalvik major relation and gate as NVW-002. Official defaults support the comparison hypothesis, not proof of an unmodified property or unauthorized intervention."),
    "NW-005": ("alert_candidate", "gpu_family",
        "The existing development-screened named hardware-family comparison supports a limited cross-renderer coherence hypothesis when both families are unique and neither is software or masked. Different legal rendering paths remain an attribution limitation."),
    "OFFDER-GPU-001": ("observation_only", "gpu_backend_marker",
        "Windows/Direct3D backend vocabulary does not itself measure a mismatch between two comparable hardware families. Existing normal host/translation counterexamples defeat the product-exclusion premise; no independent risk role is justified by this marker alone."),
}
COMMON_GATES = ["registered_current_fields", "explicit_observed_and_quality", "typed_finite_non_sentinel",
                "product_specific_relation_scope", "software_not_hardware_comparison", "separate_A_B_C",
                "uniform_research_scope", "attribution_never_inferred", "browser_evidence_only_if_present"]
PROFILE_CONDITIONS = {
    "app_model": (["one explicit non-K model-before-Build token", "Native model is meaningful", "App agent is not Dalvik"],
                  ["default/settings observed and exactly equal", "default model token equals normalized Native model; unresolved aliases stay UNKNOWN"]),
    "app_os": (["positive unambiguous Native/Android UA majors agree with frozen parsers", "App agent is not Dalvik", "Android10/K reduction excluded"],
               ["default/settings observed and exactly equal", "non-reduced default Android major agrees with Native"]),
    "system_model": (["explicit Dalvik grammar and one meaningful model-before-Build token", "Native model is meaningful"],
                     ["default App UA model token agrees with normalized Native as a naming-reference check", "property-coherence scope only, never current JS-UA identity"]),
    "system_os": (["explicit Dalvik grammar", "positive unambiguous Native/Android agent majors agree with frozen parsers"],
                  ["uniform relative-Native and process-property coherence hypothesis"]),
    "gpu_family": (["both renderers resolve to exactly one existing named hardware family", "no masked renderer", "no software-renderer token"],
                   ["reported family-coherence hypothesis only, no physical-path identity claim"]),
    "gpu_backend_marker": (["typed meaningful current Native/EGL/WebGL strings", "software and masking exclusions retained"],
                           ["NOT_ELIGIBLE: backend marker alone lacks an independent comparable identity claim"]),
}
RESEARCH_SCOPE = {
    "scope_id": SCOPE_ID, "contract_version": VERSION,
    "declaration_basis": "Existing execution plan 5.1/5.2, S03 primary-source/code review, and frozen discovery/development protocols; no formal outcomes selected.",
    "uniform_for_all_source_conditions_and_samples": True,
    "hypotheses": [
        "Current FeatureApp observations report identity across Native, host properties and App Web surfaces; a qualified discrepancy may be a suspicious-manipulation/risk clue.",
        "Native is a relative reference assumed outside the declared intervention, never a trusted hardware root or independently proven ground truth.",
        "Default/settings snapshots delimit a known current UA configuration; they do not attest a continuous, authorized or atomic origin chain.",
        "Named GPU families describe reported rendering implementations, not certified physical hardware or proof that render paths were identical.",
    ],
    "risk_alert_meaning": "Suspected manipulation/risk warning within the declared research scope, pending empirical evaluation.",
    "not_claimed": ["confirmed attack", "unauthorized origin", "malicious intent", "calibrated attack probability", "safety when no alert", "device identity or generalization"],
    "legal_counterexamples_remain_legal": True,
    "assumptions_are_not_injected_per_sample": True,
    "forbidden_scope_inputs": ["labels", "phase", "tool", "config", "session", "install", "group", "receipts", "logs", "future_post"],
    "calibrated_attack_probability": None,
    "S01_temporal_no_intervention": "UNKNOWN",
    "S04_aggregation_implemented": False,
}


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def classify_precondition(condition, rid):
    if condition == "unmodified_default_or_authorized_override_boundary_during_capture":
        return {"old_condition": condition,
                "measurement_requirements": ["parseable non-reduced current identity operands"],
                "risk_scope_requirements": ["typed current default/settings reference", "explicit custom settings exclude App UA risk eligibility", "reference agrees with Native convention"],
                "attribution_only": ["authorization of overrides", "uninterrupted default origin throughout capture"],
                "insufficient_risk_basis": []}
    if condition == "unmodified_system_http_agent_origin":
        return {"old_condition": condition, "measurement_requirements": ["explicit Dalvik grammar and interpretable identity operands"],
                "risk_scope_requirements": ["uniform host-property coherence hypothesis, not JS-UA identity"],
                "attribution_only": ["whether mutable http.agent was legitimately overridden"], "insufficient_risk_basis": []}
    if condition == "same_physical_rendering_path_and_exclusion_of_legitimate_host_or_remote_rendering":
        return {"old_condition": condition,
                "measurement_requirements": ["meaningful unmasked renderers", "software cannot be used as a hardware-family comparison", "unique named families for NW-005"],
                "risk_scope_requirements": ["reported cross-renderer family coherence, not physical-path identity"],
                "attribution_only": ["actual physical/host/remote/hybrid route and its authorization"],
                "insufficient_risk_basis": ["backend marker alone has no independent identity-coherence implication"] if rid == "OFFDER-GPU-001" else []}
    if condition in {"atomic_same_instance_ua_capture", "equivalent_window_page_zoom_and_display_context"}:
        return {"old_condition": condition, "measurement_requirements": [condition + " remains necessary for the old universal equality interpretation"],
                "risk_scope_requirements": [], "attribution_only": [],
                "insufficient_risk_basis": ["No new evidence justifies upgrading this descriptive relation; measurement scope remains UNKNOWN."]}
    if condition == "unmodified_browser_ua_origin":
        return {"old_condition": condition, "measurement_requirements": ["The frozen Browser >=107/Android10 predicate has an unresolved product-scope discrepancy; retain UNKNOWN outside explicitly excluded reduced shapes."],
                "risk_scope_requirements": [], "attribution_only": ["unmodified Browser UA origin"],
                "insufficient_risk_basis": ["No Browser risk promotion or new Browser evidence in this revision."]}
    raise ValueError("Unclassified v1 precondition: " + condition)


def build_revision():
    base = _read_jsonl(BASE_CONFIG / "source_registry.jsonl")
    old_scopes = {s["rule_id"]: s for s in v1.read_json(BASE_CONFIG / "applicability_policy.json")["scopes"]}
    catalog = v1.read_json(v1.CONFIG / "paired244_rule_catalog.v3.json")
    active = {r["rule_id"]: r for r in catalog["rules"] if r["status"] == "ACTIVE"}
    if set(active) != {r["rule_id"] for r in base} or not set(REVIEWED) <= set(active):
        raise ValueError("Pinned ACTIVE/source registry identities changed; review another version")
    bindings, roles, scopes, revisions = [], [], [], []
    for row in base:
        rid = row["rule_id"]
        if row["provenance_group"] != v1.provenance_group(active[rid]):
            raise ValueError("Source classification drift: " + rid)
        role, profile, rationale = REVIEWED.get(rid, (row["decision_role"], "retained:" + old_scopes[rid]["profile"], row["rationale"]))
        risk_fields = []
        if profile in {"app_model", "app_os"}:
            risk_fields = [DEFAULT_UA, SETTINGS_UA]
        elif profile == "system_model":
            risk_fields = [DEFAULT_UA]
        clauses = [classify_precondition(c, rid) for c in row["unobservable_alert_preconditions"]]
        revisions.extend({"rule_id": rid, **c} for c in clauses)
        basis = {"source_registry_ref": "hybridguard_agent/config/formal_manipulation_v1/source_registry.jsonl#" + rid,
                 "implementation_ref": row["researcher_derivation"]["implementation_ref"],
                 "source_ids": row["official_document_id"], "screening_scope": row["screening_scope"],
                 "discovery_split_ref": row["discovery_split_ref"],
                 "basis_limit": "Existing relation/source/development provenance is not evidence of detection accuracy or unauthorized intent."}
        common = {"rule_id": rid, "provenance_group": row["provenance_group"],
                  "decision_family": row["decision_family"], "original_evidence_family": row["original_evidence_family"]}
        bindings.append({**common, "catalog_version": row["catalog_version"], "predicate": row["researcher_derivation"]["predicate"],
                         "parameters": row["researcher_derivation"]["parameters"], "dependencies": row["dependencies"]})
        roles.append({**common, "old_decision_role": row["decision_role"], "decision_role": role,
                      "role_changed": role != row["decision_role"], "reviewed_candidate": rid in REVIEWED,
                      "rationale": rationale, "basis": basis, "known_legal_counterexamples": row["known_counterexamples"],
                      "research_scope_id": SCOPE_ID, "attribution_certainty": "UNKNOWN",
                      "attribution_unknown_does_not_veto_relation_or_eligible_risk": True,
                      "old_precondition_classification": clauses})
        scopes.append({**common, "applicability_id": "scope-v2:" + rid, "profile": profile,
                       "decision_role": role, "relation_required_fields": row["dependencies"],
                       "additional_risk_required_fields": risk_fields,
                       "relation_applicability": {"statuses": ["SUPPORTED", "UNKNOWN", "NOT_APPLICABLE"],
                          "meaning": "Current observations can be evaluated under the declared literal relation semantics, not attack truth."},
                       "risk_candidate_eligibility": {"statuses": ["ELIGIBLE", "NOT_ELIGIBLE", "UNKNOWN", "NOT_APPLICABLE"],
                          "meaning": "Eligible to supply a research-risk clue if a relation conflict occurs; eligibility also holds for consistent inputs."},
                       "attribution_certainty": {"status": "UNKNOWN", "meaning": "Allowed current fields cannot establish attack, authorization or intent."},
                       "measurement_requirements": ["registered, observed, typed, finite and non-sentinel operands", "profile-specific parsing/product/identity constraints"],
                       "relation_conditions": PROFILE_CONDITIONS.get(profile, (old_scopes[rid]["conditions"], []))[0],
                       "risk_conditions": PROFILE_CONDITIONS.get(profile, ([], ["retained non-candidate role"]))[1],
                       "legacy_scope_authority": "Used only for profiles prefixed retained:, never to veto a reviewed v2 candidate.",
                       "precondition_classification": clauses, "legacy_observation_scope": old_scopes[rid]})
    base_families = v1.read_json(BASE_CONFIG / "family_registry.json")
    family_bindings = [{"decision_family": f["decision_family"], "rule_ids": f["rule_ids"],
                        "provenance_groups": f["provenance_groups"], "original_evidence_families": f["original_evidence_families"],
                        "candidate_ids": sorted(r["rule_id"] for r in roles if r["decision_family"] == f["decision_family"] and r["decision_role"] == "alert_candidate")}
                       for f in base_families["families"]]
    conditions = copy.deepcopy(v1.read_json(BASE_CONFIG / "source_conditions.json"))
    conditions["base_registry_version"] = conditions["version"]
    conditions["version"] = VERSION
    for c in conditions["conditions"]:
        c["base_common_gate_ids"] = c["common_gate_ids"]
        c["common_gate_ids"] = COMMON_GATES
        c["applicability_policy_version"] = VERSION
        c["research_scope_id"] = SCOPE_ID
    return {"version": VERSION, "review_baseline": BASELINE, "bindings": bindings, "roles": roles,
            "scopes": scopes, "families": family_bindings, "conditions": conditions,
            "precondition_reclassifications": revisions, "research_scope": RESEARCH_SCOPE}


def _state(status, reason):
    return {"status": status, "reason": reason}


def _operands(payload, names):
    values = {}
    maps = [payload.get(key, {}) for key in ("features", "field_status", "field_quality")]
    if not all(isinstance(m, dict) for m in maps):
        return {}, _state("UNKNOWN", "invalid_evidence_container")
    features, statuses, qualities = maps
    for name in names:
        value = features.get(name)
        if statuses.get(name) != "observed" or qualities.get(name) != "observed_value":
            return values, _state("UNKNOWN", "required_field_missing_masked_or_unobserved")
        if not valid_type(value, field_contract()[name]) or not v1._finite_json(value):
            return values, _state("UNKNOWN", "invalid_type_or_nonfinite_value")
        if isinstance(value, str) and value.strip().casefold() in {"", "unknown", "null", "unsupported", "error", "not available", "masked", "redacted"}:
            return values, _state("UNKNOWN", "uninterpretable_or_masked_operand")
        if name.endswith((".hardware_concurrency", ".device_memory", ".device_pixel_ratio", ".color_depth", ".pixel_depth")) and value <= 0:
            return values, _state("UNKNOWN", "nonpositive_or_ambiguous_zero_sentinel")
        values[name] = value
    return values, None


def _reduced(ua):
    return bool(re.search(r"\bAndroid\s+10(?:\.0)?;\s*K(?:;|\))", ua, re.I))


def _major(value, *, agent=False):
    strict = v1._version(value, agent=agent)
    legacy = _ua_android_major(value) if agent else _android_major(value)
    # Keep the frozen predicate on its meaningful common parser domain.
    return strict if strict is not None and strict > 0 and strict == legacy else None


def _relation_gate(scope, payload):
    values, unavailable = _operands(payload, scope["relation_required_fields"])
    if unavailable:
        return unavailable, values
    profile = scope["profile"]
    if profile.startswith("retained:"):
        legacy = v1.evaluate_applicability(scope["legacy_observation_scope"], payload)
        reason = legacy["reason"]
        if profile == "retained:browser_os" and legacy["status"] == "UNKNOWN":
            reason = "frozen_browser_product_scope_or_current_evidence_unresolved"
        return _state(legacy["status"], reason), values
    operands = list(values.values())
    if profile in {"app_model", "app_os", "system_model", "system_os"}:
        native, ua = operands
        if profile.startswith("system_") and not ua.startswith("Dalvik/"):
            return _state("NOT_APPLICABLE", "outside_dalvik_property_scope"), values
        if profile.startswith("app_") and ua.startswith("Dalvik/"):
            return _state("NOT_APPLICABLE", "system_agent_is_not_app_browser_identity_grammar"), values
        if _reduced(ua):
            return _state("NOT_APPLICABLE", "reduced_identity_is_not_actual_os_or_model"), values
        if profile.endswith("model"):
            token, state, reason = model_token(ua, require_dalvik=profile.startswith("system_"))
            if state:
                return _state(state, reason), values
            if token in {"masked", "redacted", "generic", "0"} or native.strip().casefold() in {"k", "generic", "0"}:
                return _state("UNKNOWN", "masked_or_uninformative_model"), values
        elif _major(native) is None or _major(ua, agent=True) is None:
            return _state("UNKNOWN", "opaque_nonpositive_or_ambiguous_android_version"), values
        return _state("SUPPORTED", "identity_operands_comparable_attribution_separate"), values
    if profile in {"gpu_family", "gpu_backend_marker"}:
        texts = [value.casefold() for value in operands]
        if any(t in text for text in texts for t in v1.GPU_PARAMS["software_tokens"]):
            return _state("NOT_APPLICABLE", "software_rendering_not_hardware_comparison"), values
        if any(re.search(r"\b(?:masked|redacted)\b", t) for t in texts):
            return _state("UNKNOWN", "masked_renderer"), values
        if profile == "gpu_family":
            parsed = [gpu_family(value, v1.GPU_PARAMS) for value in operands]
            if any(state for _, state in parsed):
                return _state("UNKNOWN", "unknown_or_ambiguous_named_hardware_family"), values
        return _state("SUPPORTED", "named_family_comparison" if profile == "gpu_family" else "backend_marker_observation_only"), values
    raise ValueError("Unreviewed v2 profile: " + profile)


def _risk_gate(scope, payload, relation, values):
    if scope["decision_role"] != "alert_candidate":
        return _state("NOT_ELIGIBLE", "role_has_no_research_risk_qualification")
    if relation["status"] != "SUPPORTED":
        return _state(relation["status"], "relation_scope_not_supported")
    refs, unavailable = _operands(payload, scope["additional_risk_required_fields"])
    if unavailable:
        return _state("UNKNOWN", "risk_reference_" + unavailable["reason"])
    profile = scope["profile"]
    if profile in {"app_model", "app_os"} and refs[DEFAULT_UA] != refs[SETTINGS_UA]:
        return _state("NOT_ELIGIBLE", "explicit_custom_settings_ua_is_legal_context")
    if profile in {"app_model", "app_os", "system_model"}:
        default = refs[DEFAULT_UA]
        if _reduced(default) or default.startswith("Dalvik/"):
            return _state("UNKNOWN", "default_reference_identity_not_comparable")
        native = next(iter(values.values()))
        if profile.endswith("model"):
            token, state, _ = model_token(default)
            aligned = state is None and token == " ".join(native.split()).casefold()
        else:
            parsed = _major(default, agent=True)
            aligned = parsed is not None and parsed == _major(native)
        if not aligned:
            return _state("UNKNOWN", "native_default_naming_or_version_reference_unresolved")
    return _state("ELIGIBLE", "qualified_research_relation_not_attack_attribution")


def _relation_probe(binding, scope, payload, values, relation):
    if relation["status"] != "SUPPORTED":
        return {"outcome": relation["status"], "reason": relation["reason"], "used_fields": []}
    profile = scope["profile"]
    if profile in {"app_model", "system_model", "gpu_family"}:
        restricted = {key: {name: payload[key].get(name) for name in binding["dependencies"]}
                      for key in ("features", "field_status", "field_quality")}
        result = evaluate_closed(binding, restricted)
    elif profile in {"app_os", "system_os"}:
        native, agent = list(values.values())
        match = _android_major(native) == _ua_android_major(agent)
        result = {"outcome": "MATCH" if match else "COUNTEREXAMPLE", "reason": "frozen_android_major_relation_normalized"}
    elif profile == "gpu_backend_marker":
        text = " ".join(v.lower() for k, v in values.items() if k.startswith("app.web_data."))
        mismatch = any(t in text for t in ("direct3d", "d3d11", "d3d12", "windows"))
        result = {"outcome": "COUNTEREXAMPLE" if mismatch else "MATCH", "reason": "frozen_backend_marker_relation_observation"}
    else:
        return {"outcome": "NOT_EVALUATED", "reason": "outside_bounded_single_relation_probe", "used_fields": []}
    return {**result, "used_fields": binding["dependencies"]}


def evaluate_contract(rule_id, payload, registry):
    """Evaluate A/B/C and a single reviewed relation; never aggregate an alarm."""
    scope = next(s for s in registry["scopes"] if s["rule_id"] == rule_id)
    binding = next(s for s in registry["bindings"] if s["rule_id"] == rule_id)
    relation, values = _relation_gate(scope, payload)
    eligibility = _risk_gate(scope, payload, relation, values)
    return {"contract_version": VERSION, "rule_id": rule_id, "provenance_group": scope["provenance_group"],
            "decision_family": scope["decision_family"], "decision_role": scope["decision_role"],
            "research_scope_id": SCOPE_ID, "relation_applicability": relation,
            "risk_candidate_eligibility": eligibility,
            "relation_result": _relation_probe(binding, scope, payload, values, relation),
            "attribution_certainty": {"status": "UNKNOWN", "reason": "current_fields_do_not_prove_authorization_attack_or_intent",
                                      "attack_proven": False, "calibrated_attack_probability": None}}


FULL_UA = "Mozilla/5.0 (Linux; Android 14; ModelX Build/UP1A; wv) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
SYSTEM_UA = "Dalvik/2.1.0 (Linux; U; Android 14; ModelX Build/UP1A)"


def synthetic_payload(rule_id, registry):
    scope = next(s for s in registry["scopes"] if s["rule_id"] == rule_id)
    defaults = {"os_version": "14", "device_model": "ModelX", "user_agent": FULL_UA,
                "system_http_agent": SYSTEM_UA, "default_ua_native": FULL_UA, "settings_user_agent": FULL_UA,
                "native_gpu_renderer": "Adreno (TM) 650", "egl_renderer": "Adreno (TM) 650",
                "webgl_renderer": "ANGLE (Qualcomm, Adreno (TM) 650, OpenGL ES 3.2)", "webgl_vendor": "Qualcomm"}
    fields = scope["relation_required_fields"] + scope["additional_risk_required_fields"]
    values = {f: copy.deepcopy(defaults.get(f.rsplit(".", 1)[-1], {"string": "synthetic", "boolean": False, "number": 1, "array": []}[field_contract()[f]])) for f in fields}
    return {"features": values, "field_status": {f: "observed" for f in values}, "field_quality": {f: "observed_value" for f in values}}


def synthetic_cases(registry):
    cases = []
    for row in registry["roles"]:
        if row["decision_role"] != "alert_candidate":
            continue
        rid = row["rule_id"]
        scope = next(s for s in registry["scopes"] if s["rule_id"] == rid)
        profile = scope["profile"]
        target = scope["relation_required_fields"][1]
        for case in ("consistent", "conflict", "missing", "invalid", "not_applicable"):
            payload = synthetic_payload(rid, registry)
            if case == "conflict":
                if profile.endswith("model"):
                    payload["features"][target] = payload["features"][target].replace("ModelX", "ModelY")
                elif profile.endswith("os"):
                    payload["features"][target] = payload["features"][target].replace("Android 14", "Android 15")
                else:
                    payload["features"][target] = "Mali-G78"
            elif case == "missing":
                for mapping in payload.values():
                    mapping.pop(target)
            elif case == "invalid":
                payload["features"][target] = False
            elif case == "not_applicable":
                payload["features"][target] = ("SwiftShader" if profile == "gpu_family" else
                    FULL_UA if profile.startswith("system_") else "Mozilla/5.0 (Linux; Android 10; K; wv) Chrome/140.0.0.0")
            expected = {"consistent": ("SUPPORTED", "ELIGIBLE", "MATCH"), "conflict": ("SUPPORTED", "ELIGIBLE", "COUNTEREXAMPLE"),
                        "missing": ("UNKNOWN", "UNKNOWN", "UNKNOWN"), "invalid": ("UNKNOWN", "UNKNOWN", "UNKNOWN"),
                        "not_applicable": ("NOT_APPLICABLE", "NOT_APPLICABLE", "NOT_APPLICABLE")}[case]
            cases.append({"fixture_id": rid + ":" + case, "fixture_kind": "SYNTHETIC", "rule_id": rid, "case": case,
                          "payload": payload, "expected": {"relation_applicability": expected[0], "risk_candidate_eligibility": expected[1],
                          "relation_outcome": expected[2], "attribution_certainty": "UNKNOWN"}})
    return cases


def check_synthetic_cases(cases, registry):
    records = []
    for case in cases:
        result = evaluate_contract(case["rule_id"], case["payload"], registry)
        actual = {"relation_applicability": result["relation_applicability"]["status"],
                  "risk_candidate_eligibility": result["risk_candidate_eligibility"]["status"],
                  "relation_outcome": result["relation_result"]["outcome"], "attribution_certainty": result["attribution_certainty"]["status"]}
        records.append({"fixture_id": case["fixture_id"], "rule_id": case["rule_id"], "fixture_kind": "SYNTHETIC",
                        "case": case["case"], "expected": case["expected"], "actual": actual,
                        "passed": actual == case["expected"], "result": result})
    return records


def feasibility(registry, records):
    candidates = [r for r in registry["roles"] if r["decision_role"] == "alert_candidate"]
    reachability = []
    for r in candidates:
        observed = [x for x in records if x["rule_id"] == r["rule_id"]]
        reachability.append({"rule_id": r["rule_id"], "family": r["decision_family"],
                             "consistent_path_reachable": any(x["case"] == "consistent" and x["passed"] for x in observed),
                             "conflict_path_reachable": any(x["case"] == "conflict" and x["passed"] for x in observed),
                             "attribution_stays_unknown": all(x["actual"]["attribution_certainty"] == "UNKNOWN" for x in observed)})
    groups = {}
    for g in v1.GROUPS:
        rows = [r for r in registry["roles"] if r["provenance_group"] == g]
        qualified = [r for r in rows if r["decision_role"] == "alert_candidate"]
        groups[g] = {"total_rules": len(rows), "decision_roles": dict(Counter(r["decision_role"] for r in rows)),
                     "candidate_rule_ids": [r["rule_id"] for r in qualified],
                     "candidate_family_ids": sorted({r["decision_family"] for r in qualified}),
                     "structural_limit": "NO_RISK_CANDIDATES_ZERO_BINARY_INCREMENT_IS_STRUCTURAL" if not qualified else
                       "SYNTHETICALLY_REACHABLE_ONLY_ACTUAL_COVERAGE_AND_DETECTION_UNKNOWN"}
    candidate_conditions = []
    for condition in registry["conditions"]["conditions"]:
        included = [r for r in candidates if r["rule_id"] in condition["rule_ids"]]
        candidate_conditions.append({"condition_id": condition["condition_id"],
                                     "candidate_rule_ids": sorted(r["rule_id"] for r in included),
                                     "candidate_family_ids": sorted({r["decision_family"] for r in included})})
    shared = [f for f in registry["families"] if len({r["provenance_group"] for r in candidates if r["rule_id"] in f["candidate_ids"]}) > 1]
    return {"step": "S03-R", "contract_version": VERSION, "review_baseline": BASELINE,
            "candidate_rules": len(candidates), "candidate_families": len({r["decision_family"] for r in candidates}),
            "candidate_rule_ids": [r["rule_id"] for r in candidates], "reachability": reachability,
            "all_candidate_paths_reachable": bool(candidates) and all(x["consistent_path_reachable"] and x["conflict_path_reachable"] for x in reachability),
            "synthetic_cases": len(records), "synthetic_cases_passed": sum(r["passed"] for r in records),
            "source_groups": groups,
            "source_condition_candidate_membership": candidate_conditions,
            "shared_candidate_families": [{"decision_family": f["decision_family"], "candidate_ids": f["candidate_ids"]} for f in shared],
            "source_increment_limit": "O_u candidates duplicate E app_os/host_os candidates on the common valid domain under the same v2 gates. With E retained, they add no candidate family; a future fixed family-OR policy cannot present that structural zero as empirical absence of official-derived value. H/C have no candidate roles.",
            "feasibility_status": "LIMITED_RISK_CONTRACT_HAS_REACHABLE_PATHS_NOT_VALIDATED_DETECTION" if candidates else
                "NO_SUPPORTED_RISK_CANDIDATES_S04_OBSERVATION_ABSTENTION_ONLY",
            "actual_sample_predictions": 0, "actual_sample_scope_evaluations": 0,
            "actual_detection_performance": "NOT_EVALUATED", "temporal_control_FPR": "BLOCKED_S01_NO_INTERVENTION_UNKNOWN",
            "S04_alarm_aggregation_implemented": False, "threshold_changed": False,
            "known_legal_behavior_relabelled": False, "LLM_calls": 0,
            "candidate_count_is_not_an_acceptance_target": True}


def generate(*, output=None, config_dir=None):
    output, config_dir = validate_destinations(output, config_dir)
    registry = build_revision()
    cases = synthetic_cases(registry)
    results = check_synthetic_cases(cases, registry)
    if not all(r["passed"] for r in results):
        raise ValueError("Synthetic relation/eligibility path validation failed")
    report = feasibility(registry, results)
    payloads = {
        "applicability_policy.json": {"contract_version": VERSION, "common_gate_ids": COMMON_GATES, "scopes": registry["scopes"]},
        "decision_roles.json": {"contract_version": VERSION, "roles": registry["roles"], "risk_alert_meaning": RESEARCH_SCOPE["risk_alert_meaning"]},
        "research_scope.json": RESEARCH_SCOPE,
        "source_conditions.json": registry["conditions"],
        "family_bindings.json": {"contract_version": VERSION, "families": registry["families"], "base_family_registry": str(BASE_CONFIG.relative_to(v1.ROOT) / "family_registry.json")},
        "precondition_classification.json": {"contract_version": VERSION, "classifications": registry["precondition_reclassifications"]},
    }
    # Both destinations passed all preflight checks before either is created.
    for directory in (config_dir, output):
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in payloads.items():
            v1.write_json(directory / name, value)
        v1.write_jsonl(directory / "source_bindings.jsonl", registry["bindings"])
    v1.write_jsonl(output / "SYNTHETIC_FIXTURES.jsonl", cases)
    v1.write_jsonl(output / "SYNTHETIC_RESULTS.jsonl", results)
    v1.write_json(output / "DETECTION_FEASIBILITY.json", report)
    v1.write_json(output / "GENERATION.json", {"contract_version": VERSION, "output": str(output), "config_dir": str(config_dir),
                  "both_destinations_explicit": True, "input_scope": "saved static S03 registries and synthetic fixtures only", "real_inputs_loaded": 0})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = generate(output=args.output, config_dir=args.config_dir)
    print(json.dumps({k: summary[k] for k in ("candidate_rules", "candidate_families", "all_candidate_paths_reachable", "synthetic_cases", "synthetic_cases_passed", "actual_sample_predictions")}, ensure_ascii=False))
