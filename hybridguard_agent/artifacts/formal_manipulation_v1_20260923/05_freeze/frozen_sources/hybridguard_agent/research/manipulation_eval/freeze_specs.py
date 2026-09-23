"""S05 finite diagnostic and missingness definitions; never execute a predicate."""
from copy import deepcopy


def diagnostic_spec(candidate_ids):
    common = {
        "source_condition": "SRC-111", "method": "final_v3_v2", "input_view": "App177",
        "candidate_rule_ids": sorted(candidate_ids), "threshold": 1,
        "original_outcomes_preserved": True, "attribution_certainty": "UNKNOWN",
        "formal_risk_prediction": False, "detection_metrics": "NOT_EVALUATED_DIAGNOSTIC",
        "implementation_status": "FROZEN_DEFINITION_IMPLEMENT_IN_AUTHORIZED_S09",
    }
    definitions = [
        {"diagnostic_id": "D1_REMOVE_UA_REDUCTION", "domains": ["main216", "synthetic_semantic"],
         "operator": "Replace only the _reduced(ua) and _reduced(default) rejection terms in v2 _relation_gate/_risk_gate with false; all other terms unchanged. Apply to the frozen candidate IDs only.",
         "preserved": "Original predicate and its model_token K/no-Build rejection, observed/type/quality, Dalvik product scope, Native/default/settings alignment, software gate, family OR and threshold remain. Do not force A or B to pass.",
         "original_probe": "Use saved original outcomes; reevaluate only the declared diagnostic gates over the frozen current payload. A gate passing with an original UNKNOWN/NOT_APPLICABLE outcome supplies no vote.",
         "not_exercised": "If the original predicate or another gate still excludes a reduced identity, record NOT_EXERCISED; no parser relaxation."},
        {"diagnostic_id": "D2_UNKNOWN_AS_COMPARABLE", "domains": ["synthetic_semantic"],
         "operator": "In an explicitly marked synthetic shadow accessor only, ignore field_status/field_quality availability rejection when an existing value is non-null, valid typed, finite and non-sentinel. Keep all parsing, masking-token, product, software, reference and role gates. Never infer or edit observed in the stored input.",
         "original_probe": "Save original outcome first; evaluate the SAME frozen predicate against the shadow accessor for the diagnostic outcome. No imputation, invented value, forced MATCH/COUNTEREXAMPLE, or real-sample risk row.",
         "not_exercised": "Absent/invalid/zero/masked value remains unavailable. This counterfactual is not a claim that a failed collection measured the value."},
        {"diagnostic_id": "D3_DUPLICATE_VOTES", "domains": ["main216", "synthetic_semantic"],
         "operator": "From saved verified events, count qualifying COUNTEREXAMPLE rule IDs instead of distinct decision_family IDs. Preserve MATCH coverage and all v2 gates/roles/source conditions. FAILED remains FAILED; no qualifying families remains INSUFFICIENT_EVIDENCE.",
         "execution": "SAVED_EVENT_DERIVATION_ONLY_NO_DETECTOR_REPLAY",
         "structural_binary_effect": "Exactly zero at threshold 1; report score and reference inflation only. Never adjust threshold to manufacture benefit."},
        {"diagnostic_id": "D4_RAW_UNCONDITIONAL_EQUALITY", "domains": ["synthetic_semantic"],
         "operator": "For each candidate's ordered pair of relation_required_fields, compare raw JSON values with type-sensitive recursive equality (object key order ignored; array order retained; bool differs from number; int/float numeric equality). Two absent keys compare equal; absent differs from present null. No parsing, normalization, availability, product or quality gate.",
         "execution": "SYNTHETIC_MECHANISM_ONLY_NOT_HISTORICAL_RUNTIME",
         "scope": "No risk decision or performance metric. Emit RAW_EQUAL/RAW_DIFFERENT plus ignored status/quality and original relation outcome; do not call raw inequality an attack."},
    ]
    return {"version": "formal-semantic-diagnostics-freeze-v2", "common": common, "definitions": definitions,
            "metrics_boundary": "Diagnostic changes cannot overwrite valid v2 risk results. Any future alternative binary detector requires a new approved contract."}


def fixtures(base, mapping, scopes):
    """Fully materialize synthetic inputs without evaluating outcomes."""
    alias = {r["legacy_alias"]: r["field"] for r in mapping["fields"]}
    ua = "Mozilla/5.0 (Linux; Android 14; ModelX Build/UP1A; wv) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
    reduced = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
    rows = []

    def add(fid, suite, values=None, states=None, qualities=None, note=""):
        payload = deepcopy(base)
        for section, changes in (("features", values), ("field_status", states), ("field_quality", qualities)):
            payload[section].update(changes or {})
        rows.append({"fixture_id": fid, "opaque_id": "sample-synthetic-" + fid.lower().replace("_", "-"),
                     "suite": suite, "payload": payload, "truth": "UNKNOWN_SYNTHETIC_NO_ATTACK_LABEL",
                     "purpose": note, "outcomes": "NOT_EXECUTED"})

    app = alias["web_data.user_agent"]
    default = alias["webview_data.default_ua_native"]
    settings = alias["webview_data.settings_user_agent"]
    add("SEM_CONSISTENT", "E4")
    add("SEM_OS_CONFLICT", "E4", {app: ua.replace("Android 14", "Android 15")})
    add("SEM_REDUCED_APP", "E4", {app: reduced}, note="Legal reduced UA; not an attack label")
    add("SEM_REDUCED_REFERENCE", "E4", {default: reduced, settings: reduced})
    add("SEM_DALVIK_APP", "E4", {app: "Dalvik/2.1.0 (Linux; U; Android 14; ModelX Build/UP1A)"})
    add("SEM_SOFTWARE_GPU", "E4", {alias["web_data.webgl_renderer"]: "ANGLE SwiftShader"})
    add("SEM_MASKED_MODEL", "E4", {alias["android_native_data.device_model"]: "redacted"})
    add("SEM_TIMEOUT_TYPED", "E4", {app: ua.replace("Android 14", "Android 15")},
        {app: "timeout"}, {app: "source_unavailable"}, "Retained value is not certified as observed")
    add("SEM_UNSUPPORTED_TYPED", "E4", states={app: "unsupported_by_os"}, qualities={app: "source_unavailable"})
    add("SEM_MISSING_VALUE", "E4", {app: None}, {app: "runtime_error"}, {app: "source_unavailable"})
    add("SEM_MEMORY_APPROX", "E4", {alias["android_native_data.total_memory_gb"]: 7.5,
        alias["web_data.device_memory"]: 8}, note="Legal approximation; non-candidate observation remains so")
    add("SEM_TIMEZONE_ALIAS", "E4", {alias["android_native_data.native_timezone_id"]: "Asia/Shanghai",
        alias["web_data.timezone_id"]: "Asia/Chongqing"}, note="Equivalent-zone example, no role promotion")
    fields = sorted({f for s in scopes if s["decision_role"] == "alert_candidate"
                     for f in s["relation_required_fields"] + s["additional_risk_required_fields"]})
    for i, f in enumerate(fields, 1):
        for state in ("timeout", "unsupported_by_os", "runtime_error"):
            add(f"MISS_F{i:02d}_{state.upper()}", "E5", states={f: state}, qualities={f: "source_unavailable"})
        add(f"MISS_F{i:02d}_QUALITY", "E5", qualities={f: "source_unavailable"},
            note="Observed/quality disagreement must stay unavailable or fail closed, not become a vote")
    for surface in ("native84", "host26", "app_web67"):
        names = [r["field"] for r in mapping["fields"] if r["surface"] == surface]
        add("MISS_LAYER_" + surface.upper(), "E5", {f: None for f in names},
            {f: "not_applicable" for f in names}, {f: "source_unavailable" for f in names},
            "Whole-layer erasure before worker: no original value, availability or quality retained; full 177-key transport remains valid")
    changes = {alias["android_native_data.os_version"]: "15", app: ua.replace("Android 14", "Android 15"),
               default: ua.replace("Android 14", "Android 15"), settings: ua.replace("Android 14", "Android 15"),
               alias["webview_data.system_http_agent"]: "Dalvik/2.1.0 (Linux; U; Android 15; ModelX Build/UP1A)"}
    add("COORDINATED_IDENTITIES", "E5", changes, note="Coordinated equal identities; not a true-attack fixture")
    add("INDISTINGUISHABLE_TWIN", "E5", changes, note="Same observable payload, separate synthetic unit; do not deduplicate or assign opposite truth labels")
    return rows


def timing_spec(sample_ids):
    return {"version": "formal-cost-freeze-v2", "sample_opaque_ids": sorted(sample_ids),
        "selection": "Main216 only; strata=(S01 environment group,S02 cohort,phase). Within each stratum opaque-ID sort, take one per lexicographically ordered stratum each round until 24, then sort selected IDs. No value/outcome/timing selection.",
        "methods": ["final_v3_v2", "legacy19_v2"], "input_view": "App177", "condition_id": "SRC-111",
        "cold_repeats": 1, "warmup_repeats": 3, "measured_repeats": 20,
        "order": "opaque ID, method lexicographic; cold in fresh process; separate persistent process per sample/method for 3 warmups then 20 measured iterations, serial, no parallelism",
        "record": ["hardware", "OS", "Python", "source_binding", "sequence", "cold_warm", "repeat", "failure", "parse", "evidence", "rules", "retrieval", "original_verifier", "risk_policy", "risk_verifier", "total", "cold_process_wall_ms"],
        "cost_boundary": "Worker total includes original and risk Verifier recomputations; cold process startup/end-to-end reported separately. Unassigned overhead=total-sum(named stages), never removed.",
        "summary": "Median and nearest-rank P95 (ceil(0.95*n)-1); all raw repetitions/failed slots retained; failed timings excluded only from numeric quantiles with explicit count. No best-run selection or population interval.",
        "consistency": "Compare untimed semantic output with saved same-version official unit excluding timing/run metadata; mismatch blocks cost conclusions and remains recorded.",
        "scope": "Offline local Python cost, not Android latency; no hardware replacement selected for results",
        "explanation_audit": {"automatic": "All saved S06/S07 events and cards; IDs, versions, used fields, status/quality, role/gates and original verification references",
            "manual_queue": "Only unresolved normative meaning/causal wording after automatic reference checks; deduplicate by (rule_id,reason_code), sort lexicographically, first 12 with lowest opaque ID each; blind method names. NOT_REVIEWED unless separately reviewed; never tune method.",
            "LLM_calls": 0}}
