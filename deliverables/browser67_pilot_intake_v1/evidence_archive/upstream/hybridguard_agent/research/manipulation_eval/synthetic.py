"""Hand-declared S04 fixtures; no loader for real material or predictions."""
import copy

from hybridguard_agent.evidence.paired244 import legacy_field_map
from hybridguard_agent.research.manipulation_eval.adapter import selected_fields, SCHEMA, VERSION
from hybridguard_agent.research.manipulation_eval.provenance_revision import FULL_UA, SYSTEM_UA

MAP = legacy_field_map()


def empty_payload():
    fields = selected_fields("App177")
    return {"record_schema_version": SCHEMA, "adapter_version": VERSION,
            "features": {f: None for f in sorted(fields)},
            "field_status": {f: "runtime_error" for f in sorted(fields)},
            "field_quality": {f: "source_unavailable" for f in sorted(fields)}}


def put(payload, alias, value):
    field = MAP[alias]
    payload["features"][field] = value
    payload["field_status"][field] = "observed"
    payload["field_quality"][field] = "observed_value"
    return payload


def consistent_payload():
    p = empty_payload()
    for alias, value in {"android_native_data.os_version": "14", "android_native_data.device_model": "ModelX",
                         "web_data.user_agent": FULL_UA, "webview_data.system_http_agent": SYSTEM_UA,
                         "webview_data.default_ua_native": FULL_UA, "webview_data.settings_user_agent": FULL_UA,
                         "android_native_data.native_gpu_renderer": "Adreno (TM) 650",
                         "android_native_data.egl_renderer": "Adreno (TM) 650", "web_data.webgl_vendor": "Qualcomm",
                         "web_data.webgl_renderer": "Adreno (TM) 650"}.items():
        put(p, alias, value)
    return p


def fixtures():
    base = consistent_payload()
    conflict = put(copy.deepcopy(base), "web_data.user_agent", FULL_UA.replace("Android 14", "Android 15"))
    software = put(empty_payload(), "android_native_data.native_gpu_renderer", "Adreno (TM) 650")
    put(software, "web_data.webgl_renderer", "SwiftShader")
    invalid = put(copy.deepcopy(base), "web_data.user_agent", False)
    return [{"fixture_id": name, "fixture_kind": "SYNTHETIC", "payload": payload, "expected_decision": decision, "expected_score": score}
            for name, payload, decision, score in (
                ("consistent", base, "NO_ALERT", 0), ("single_family_duplicate_rules", conflict, "MANIPULATION_ALERT", 1),
                ("all_missing", empty_payload(), "INSUFFICIENT_EVIDENCE", 0),
                ("software_not_applicable", software, "INSUFFICIENT_EVIDENCE", 0),
                ("invalid_type", invalid, "FAILED", None))]


def evaluation_fixture():
    """Hand arithmetic: positives 1/4, control-mid FP 1/4; 010 is 1/3."""
    from hybridguard_agent.research.manipulation_eval.contract import VERSION as CONTRACT, POLICY_VERSION, STUDY_VERSION
    cases = {f["fixture_id"]: f["payload"] for f in fixtures()}
    specs = [("t1", "clean_pre", "consistent", "NEGATIVE"), ("t1", "attack", "single_family_duplicate_rules", "POSITIVE"),
             ("t1", "clean_post", "consistent", "NEGATIVE"), ("t2", "clean_pre", "all_missing", "NEGATIVE"),
             ("t2", "attack", "invalid_type", "POSITIVE"), ("t2", "clean_post", "invalid_type", "NEGATIVE"),
             ("t3", "attack", "consistent", "POSITIVE"), ("p4", "attack", "all_missing", "POSITIVE"),
             ("c1", "control_mid", "single_family_duplicate_rules", "NEGATIVE"), ("c2", "control_mid", "consistent", "NEGATIVE"),
             ("c3", "control_mid", "all_missing", "NEGATIVE"), ("c4", "control_mid", "invalid_type", "NEGATIVE"),
             ("u1", "control_mid", "single_family_duplicate_rules", "UNKNOWN"), ("u2", "control_mid", "consistent", "UNKNOWN")]
    inputs, index = [], []
    for i, (triplet, phase, case, truth) in enumerate(specs, 1):
        opaque = f"sample-synthetic-{i:03d}"
        inputs.append({"opaque_id": opaque, "payload": copy.deepcopy(cases[case])})
        positive, negative = truth == "POSITIVE", truth == "NEGATIVE"
        fact = {"bundle_id": "bundle-" + triplet, "triplet_id": triplet, "phase": phase,
                "kind": "control" if phase == "control_mid" else "attack", "environment_group_id": "g1" if i <= 6 else "g2",
                "eligible_detection": positive, "eligible_pre_control": negative and phase == "clean_pre",
                "eligible_post_control": negative and phase == "clean_post", "eligible_temporal_control": negative and phase == "control_mid",
                "eligible_triplet": triplet in {"t1", "t2", "t3"},
                "execution": {"status": "SUPPORTED" if positive else "UNKNOWN"},
                "observable_effect": {"status": "SUPPORTED" if positive else "UNKNOWN"},
                "no_intervention": {"status": "SUPPORTED" if negative else "REFUTED" if positive else "UNKNOWN"},
                "rollback": {"status": "SUPPORTED" if phase == "clean_post" else "UNKNOWN"},
                "evidence_grade": "L1_RECEIPT_SUPPORTED" if truth != "UNKNOWN" else "L0_ANNOTATION_ONLY_OR_INCOMPLETE",
                "label_conflict": False}
        index.append({"opaque_id": opaque, "fixture_kind": "SYNTHETIC", "admission_fact": fact,
                      **{k: fact[k] for k in ("bundle_id", "triplet_id", "phase", "environment_group_id")},
                      "configuration_id": "cfg-a" if i <= 6 else "cfg-b", "cohort": "synthetic_" + truth.lower(),
                      "tool": "evaluation-only-tool", "raw_session_ref": "/evaluation-only/path", "api_level": 34})
    vid = "final_v3_v2:App177:SRC-111"
    job = {"schema_version": "formal-prediction-job-v2", "study_version": STUDY_VERSION,
           "run_id": "s04-synthetic-denominators-v2", "protocol_digest": "SYNTHETIC_HAND_DECLARED_PROTOCOL_V2",
           "contract_version": CONTRACT, "policy_version": POLICY_VERSION, "execution_scope": "SYNTHETIC_CONTRACT_TEST",
           "variants": [{"variant_id": vid, "condition_id": "SRC-111", "input_view": "App177", "method": "final_v3_v2"}],
           "expected_units": [{"opaque_id": r["opaque_id"], "variant_id": vid, "input_line": i} for i, r in enumerate(inputs, 1)]}
    triplets = [{"bundle_id": "bundle-" + t, "triplet_id": t, "kind": "attack", "eligible_triplet": True} for t in ("t1", "t2", "t3")]
    expected = {"positive": {"n": 4, "alert": 1, "no_alert": 1, "abstain": 1, "failed": 1, "rate": 0.25, "bounds": [0.25, 0.5]},
                "control_mid": {"n": 4, "alert": 1, "no_alert": 1, "abstain": 1, "failed": 1, "rate": 0.25, "bounds": [0.25, 0.5]},
                "all_negative": {"n": 8, "alert": 1, "no_alert": 3, "abstain": 2, "failed": 2},
                "unknown_truth": 2, "triplets": {"n": 3, "success_010": 1, "incomplete": 2},
                "synthetic_labels_only": True, "real_temporal_control_eligibility_changed": False}
    return {"inputs": inputs, "evaluation_index": index, "triplets": triplets, "job": job, "expected": expected}
