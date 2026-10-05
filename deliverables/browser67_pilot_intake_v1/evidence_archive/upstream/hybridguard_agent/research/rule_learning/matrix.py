"""Label-free R01 measurement implementation. No fitting or alarm decisions.

The old predicate functions below evaluate ONE declared relation, never a
detector/policy. Their source equality with S06 is checked by the R02 builder.
Domain checks precede cache use. Old relation/risk gates are not consumed.
"""
from __future__ import annotations

import copy
import math
import re

from hybridguard_agent.evidence.extractor import (
    _android_major, _ua_android_major, _ua_class, _platform_class,
    _derived_facts, normalize_payload,
)
from hybridguard_agent.evidence.paired244 import legacy_payload
from hybridguard_agent.research.mtc_closed_resource import (
    evaluate as closed_relation, model_token, gpu_family,
)
from hybridguard_agent.research.mtc_p3_candidates import evaluate_candidate, _dimensions
from hybridguard_agent.rules.executor import _evaluate
from hybridguard_agent.rules.legacy_backlog import evaluate_reviewed_rule
from hybridguard_agent.official_semantics.evaluator import _evaluate_compiled

VERSION = "r02-fixed-measurement-v1"
SECTIONS = ("features", "field_status", "field_quality")
PAYLOAD_KEYS = {*SECTIONS, "record_schema_version", "adapter_version"}
STATES = {"observed", "unsupported_by_os", "permission_denied", "runtime_error", "timeout", "not_applicable"}
QUALITIES = {"observed_value", "source_unavailable", "ambiguous_sentinel"}
SURFACES = {"native84": "app.android_native_data.", "host26": "app.webview_data.",
            "app_web67": "app.web_data.", "browser67": "browser.web_data."}
PLACEHOLDERS = {"", "unknown", "null", "unsupported", "not available", "error"}
OUTCOMES = {"MATCH", "COUNTEREXAMPLE", "CONTEXT_OBSERVED", "POLICY_MISMATCH",
            "UNKNOWN", "NOT_APPLICABLE", "NOT_EVALUATED"}


class SchemaError(ValueError):
    pass


class Unavailable(ValueError):
    def __init__(self, reason, outcome="UNKNOWN"):
        self.reason, self.outcome = reason, outcome
        super().__init__(reason)


def envelope(payload):
    if (type(payload) is not dict or set(payload) != PAYLOAD_KEYS
            or payload["record_schema_version"] != "hybridguard-mtc-observation-v2"
            or payload["adapter_version"] != "app177-triplet-adapter-v1"
            or any(type(payload[s]) is not dict for s in SECTIONS)):
        raise SchemaError("INVALID_SERIALIZED_RECORD_ENVELOPE")
    if any(not isinstance(p, str) or not any(p.startswith(v) for v in SURFACES.values())
           for s in SECTIONS for p in payload[s]):
        raise SchemaError("NON_FIELD_KEY_IN_PAYLOAD")


def mask(payload, surfaces):
    """Remove values, status AND quality before any derived relation/parser."""
    envelope(payload)
    prefixes = tuple(SURFACES[s] for s in surfaces)
    return {"record_schema_version": payload["record_schema_version"],
            "adapter_version": payload["adapter_version"],
            **{s: {p: copy.deepcopy(v) for p, v in payload[s].items() if p.startswith(prefixes)}
               for s in SECTIONS}}


def number(v):
    return type(v) in (int, float) and math.isfinite(v)


def count(v):
    return number(v) and v >= 0 and int(v) == v


def field_state(payload, spec):
    p, kind = spec["field"], spec["type"]
    value = payload["features"].get(p)
    status, quality = (payload[s].get(p) for s in SECTIONS[1:])
    reason = None
    if p not in payload["features"]:
        reason = "MISSING_SURFACE" if p.startswith("browser.") else "MISSING_OR_MASKED_FIELD"
    elif status is None or quality is None:
        reason = "MISSING_MEASUREMENT_STATE"
    elif status not in STATES or quality not in QUALITIES:
        raise SchemaError("INVALID_FIELD_STATE_ENUM:" + p)
    elif status != "observed":
        reason = "SOURCE_STATUS_" + status.upper()
    elif quality != "observed_value":
        reason = "SOURCE_QUALITY_" + quality.upper()
    elif value is None:
        reason = "MISSING_MEASUREMENT_VALUE"
    elif not (number(value) if kind == "number" else type(value) is {"string": str, "boolean": bool, "array": list}[kind]):
        reason = "INVALID_OPERAND_TYPE_OR_NONFINITE"
    elif isinstance(value, str) and value.strip().casefold() in PLACEHOLDERS:
        reason = "UNINTERPRETABLE_PLACEHOLDER"
    elif p.endswith((".device_memory", ".hardware_concurrency")) and value <= 0:
        reason = "AMBIGUOUS_NAVIGATOR_SENTINEL"
    return {"source_status": status, "source_quality": quality, "expected_type": kind,
            "available": reason is None, "reason": reason}


def strict_major(value, agent=False):
    if agent:
        matches = re.findall(r"\bAndroid\s+(\d+)(?:[._]\d+)*\b", value, re.I)
        parsed = int(matches[0]) if len(matches) == 1 else None
        legacy = _ua_android_major(value)
    else:
        match = re.fullmatch(r"(?:Android\s*)?(\d+)(?:[._]\d+)*", value.strip(), re.I)
        parsed = int(match[1]) if match else None
        legacy = _android_major(value)
    return parsed if parsed is not None and parsed > 0 and parsed == legacy else None


def measurement_domain(candidate, payload):
    """Validate the per-atom measurement domain without evaluating its truth."""
    values = [payload["features"][p] for p in candidate["dependencies"]]
    profile, pred = candidate["measurement"]["profile"], candidate["predicate"]
    by_leaf = {p.rsplit(".", 1)[1]: v for p, v in zip(candidate["dependencies"], values)}
    if profile in {"app_android_major", "system_android_major"}:
        native, agent = values
        if profile == "system_android_major" and not re.fullmatch(r"Dalvik/\d+(?:\.\d+)+\s*\(.+\)", agent):
            raise Unavailable("OUTSIDE_EXPLICIT_DALVIK_GRAMMAR", "NOT_APPLICABLE")
        if profile == "app_android_major" and agent.startswith("Dalvik/"):
            raise Unavailable("DALVIK_NOT_CURRENT_APP_UA", "NOT_APPLICABLE")
        if profile == "app_android_major" and re.search(r"\bAndroid\s+10(?:\.0)?;\s*K(?:;|\))", agent, re.I):
            raise Unavailable("REDUCED_ANDROID10_K_NOT_OS_MEASUREMENT", "NOT_APPLICABLE")
        if strict_major(native) is None or strict_major(agent, True) is None:
            raise Unavailable("OS_MAJOR_UNPARSEABLE_AMBIGUOUS_OR_PARSER_DISAGREEMENT")
    elif profile == "model_token":
        _, outcome, reason = model_token(values[1], candidate["parameters"]["require_dalvik"])
        if outcome:
            raise Unavailable(reason, outcome)
    elif profile == "gpu_family":
        parsed = [gpu_family(v, candidate["parameters"]) for v in values]
        if any(s == "NOT_APPLICABLE" for _, s in parsed):
            raise Unavailable("SOFTWARE_NOT_HARDWARE_FAMILY", "NOT_APPLICABLE")
        if any(s for _, s in parsed):
            raise Unavailable("UNKNOWN_MASKED_OR_AMBIGUOUS_HARDWARE_FAMILY")
    elif profile in {"screen_short_side", "dimensions"}:
        try:
            for v in values[:2]:
                _dimensions(v)
        except ValueError:
            raise Unavailable("INVALID_POSITIVE_DIMENSIONS") from None
        if profile == "screen_short_side" and (not number(values[2]) or values[2] <= 0):
            raise Unavailable("INVALID_POSITIVE_DPR")
    elif profile in {"ua_platform_class", "host_web_class", "ua_touch", "ua_touch_mobile_only", "ua_class"}:
        ua = _ua_class(by_leaf["user_agent"])
        platform = _platform_class(by_leaf.get("platform", ""))
        if profile == "ua_platform_class" and (ua == "unknown" or platform == "unknown"):
            raise Unavailable("UNKNOWN_UA_OR_PLATFORM_CLASS")
        if profile == "host_web_class":
            if strict_major(by_leaf["os_version"]) is None:
                raise Unavailable("UNINTERPRETABLE_NATIVE_ANDROID_MAJOR")
            if ua == platform == "unknown":
                raise Unavailable("BOTH_WEB_CLASSES_UNKNOWN")
        if profile in {"ua_touch", "ua_touch_mobile_only", "ua_class"} and ua == "unknown":
            raise Unavailable("UNKNOWN_UA_CLASS")
        if "touch" in profile and not count(by_leaf["max_touch_points"]):
            raise Unavailable("INVALID_NONNEGATIVE_INTEGRAL_TOUCH_COUNT")
        if profile == "ua_touch_mobile_only" and ua not in {"android_browser", "android_webview"}:
            raise Unavailable("NONMOBILE_UA_OUTSIDE_MOBILE_ONLY_DOMAIN", "NOT_APPLICABLE")
    elif profile == "provider":
        if not count(values[1]) or not re.match(r"^\d+\.", values[0]):
            raise Unavailable("UNINTERPRETABLE_PROVIDER_MAJOR")
    elif profile == "nonnegative":
        if not all(number(v) and v >= 0 for v in values):
            raise Unavailable("INVALID_NONNEGATIVE_OPERAND")
        if "sensor_matrix_layer" in candidate["dependencies"][0] and not all(count(v) for v in values):
            raise Unavailable("INVALID_INTEGRAL_SENSOR_COUNT")
    elif profile in {"sensor_list", "sensor_presence"}:
        lists = [v for v in values if isinstance(v, list)]
        if not lists or any(type(v) is not int or v < 1 for vs in lists for v in vs):
            raise Unavailable("INVALID_POSITIVE_INTEGER_SENSOR_LIST")
        if pred == "list_count" and not count(values[1]):
            raise Unavailable("INVALID_INTEGRAL_SENSOR_COUNT")
        if profile == "sensor_presence" and values[0] is False:
            raise Unavailable("ANTECEDENT_FALSE_NOT_ABSENCE_PROOF", "NOT_APPLICABLE")
    elif profile == "context":
        battery = by_leaf.get("battery_level_pct")
        if battery is not None and not (number(battery) and 0 <= battery <= 100):
            raise Unavailable("BATTERY_OUTSIDE_PERCENT_DOMAIN")
        if "timezone_offset" in by_leaf and (not number(by_leaf["timezone_offset"]) or int(by_leaf["timezone_offset"]) != by_leaf["timezone_offset"]):
            raise Unavailable("NONINTEGRAL_TIMEZONE_OFFSET")
    elif profile == "deployment" and pred == "package_release_policy_v1":
        code = by_leaf["app_version_code"]
        if not count(code) or code <= 0:
            raise Unavailable("INVALID_POSITIVE_RELEASE_CODE")
    # Preserve additional, explicit frozen P3 domains; no new threshold.
    if pred == "equal":
        for p, v in zip(candidate["dependencies"], values):
            if p.endswith((".color_depth", ".pixel_depth", ".device_pixel_ratio", ".audio_sample_rate")) and (not number(v) or v <= 0):
                raise Unavailable("INVALID_POSITIVE_MEASUREMENT")
    return "R01_PROFILE_VALID_FROZEN_PREDICATE_SAME_ON_THIS_DOMAIN"


def original_relation(rule, payload):
    """Evaluate only the frozen predicate on its restricted dependencies."""
    refs = rule["dependencies"]
    projection = {s: {p: payload[s][p] for p in refs} for s in SECTIONS}
    if rule.get("implementation") == "mtc-closed-resource-predicates-v1":
        return closed_relation(rule, projection)
    if rule.get("implementation") == "paired244-legacy-backlog-v1":
        return evaluate_reviewed_rule(rule, projection)
    if rule["origin"] == "p3_research":
        return evaluate_candidate(rule, projection)
    if rule["predicate"] == "featureapp_bridge_only_v2":
        return {"outcome": "MATCH" if projection["features"][refs[0]] else "COUNTEREXAMPLE",
                "reason": "bridge_presence_only_sensor_count_is_not_a_veto"}
    normalized, states = normalize_payload(legacy_payload(projection))
    facts = _derived_facts(normalized, states)
    if rule["origin"] == "legacy_device":
        raw = _evaluate({"id": rule["rule_id"]}, {**rule["legacy_spec"], "short_circuit": False}, facts)
        mapping = {"matched": "COUNTEREXAMPLE", "not_matched": "MATCH", "context_observed": "CONTEXT_OBSERVED",
                   "unknown": "UNKNOWN", "unavailable": "NOT_EVALUATED"}
    elif rule["origin"] == "legacy_official":
        raw = _evaluate_compiled(rule["legacy_relation"], normalized, states, facts)
        mapping = {"consistent": "MATCH", "inconsistent": "COUNTEREXAMPLE", "context_observed": "CONTEXT_OBSERVED",
                   "not_applicable": "NOT_APPLICABLE", "unknown": "UNKNOWN", "unavailable": "NOT_EVALUATED"}
    else:
        raise ValueError("UNREGISTERED_ORIGINAL_IMPLEMENTATION")
    return {"outcome": mapping[raw["outcome"]], "reason": raw["detail"]}


def mapped_state(candidate, outcome):
    if outcome not in OUTCOMES:
        raise SchemaError("UNKNOWN_ORIGINAL_OUTCOME")
    state = candidate["measurement"]["outcome_to_state"].get(outcome)
    if state not in {"T", "F", "U"}:
        raise SchemaError("OUTCOME_HAS_NO_DEFINED_BOOLEAN_MAPPING:" + outcome)
    return state


def negate(state):
    if state not in {"T", "F", "U"}:
        raise ValueError("FAILED_OR_UNREQUESTED_IS_NOT_A_LOGICAL_STATE")
    return {"T": "F", "F": "T", "U": "U"}[state]


def extract_atom(candidate, rule, payload, cached=None, cache_proof=None, *, execute_missing=True):
    """No sample ID/label/phase/group is accepted by the semantic conversion."""
    old = cached.get("original_result") if cached else None
    lineage = {"status": "ABSENT" if cached is None else "UNCHECKED", "reuse": False,
               "extraction_version": VERSION, "predicate_executed": False, "checks": copy.deepcopy(cache_proof or {}),
               "cache_observation": "ABSENT" if cached is None else "MISSING_ORIGINAL_RESULT" if old is None
               else "UNEXECUTED" if old.get("outcome") == "NOT_EVALUATED" else "ORIGINAL_RESULT_PRESENT"}
    cell = {"atom_id": candidate["atom_id"], "predicate_version": candidate["predicate_version"],
            "measurement_version": "r01-measurement-v1", "value": None, "state": None,
            "available": False, "reason": "NOT_REQUESTED", "original_outcome": old.get("outcome") if old else None,
            "original_reason": old.get("reason") if old else None, "evaluation_status": "NOT_REQUESTED",
            "field_states": {}, "cache_lineage": lineage, "relation_result": None}
    try:
        envelope(payload)
        cell["field_states"] = {s["field"]: field_state(payload, s) for s in candidate["dependency_schema"]}
        proof = lineage["checks"]
        proof["event_identity"] = bool(cached and cached.get("rule_id") == candidate["rule_id"]
                                       and cached.get("method") == "final_v3_v2" and cached.get("verification_valid") is True)
        proof["predicate_and_version"] = bool(old and old.get("predicate") == candidate["predicate"]
                                              and old.get("rule_version") == candidate["predicate_version"]
                                              and old.get("required_fields") == candidate["dependencies"])
        proof["field_states"] = bool(cached and all(
            cached.get("field_states", {}).get(p, {}).get("source_status") == fs["source_status"]
            and cached.get("field_states", {}).get(p, {}).get("source_quality") == fs["source_quality"]
            for p, fs in cell["field_states"].items() if p in payload["features"]))
        required = ("input", "catalog_parameters", "implementation_version", "event_identity", "predicate_and_version", "field_states")
        lineage["status"] = "ABSENT" if not cached else "CONTRACT_MISMATCH" if not all(proof.get(k) is True for k in required) else "VERIFIED_ORIGINAL"
        lineage["pre_measurement_cache_status"] = lineage["status"]
        if not candidate["measurement"]["defined"]:
            lineage["status"] = "NO_BOOLEAN_ATOM" if cached else "ABSENT_NO_BOOLEAN_ATOM"
            cell["reason"] = "NO_BOOLEAN_ATOM_CONTEXT_SUMMARY_RETAINED_IN_REGISTRY"
            return cell
        unavailable = [(p, f["reason"]) for p, f in cell["field_states"].items() if not f["available"]]
        if unavailable:
            raise Unavailable("MISSING_SURFACE" if any(r == "MISSING_SURFACE" for _, r in unavailable) else unavailable[0][1])
        measurement_domain(candidate, payload)
        proof["measurement_domain"] = "R01_PROFILE_VALID_FROZEN_PREDICATE_SAME_ON_THIS_DOMAIN"
        reuse = lineage["status"] == "VERIFIED_ORIGINAL" and old.get("outcome") != "NOT_EVALUATED"
        if old and old.get("outcome") == "NOT_EVALUATED" and lineage["status"] == "VERIFIED_ORIGINAL":
            lineage["status"] = "UNEXECUTED_WITH_AVAILABLE_OPERANDS"
        if reuse:
            raw = {"outcome": old["outcome"], "reason": old["reason"]}
            lineage.update(status="REUSED_ORIGINAL_RESULT", reuse=True)
        elif execute_missing:
            lineage["predicate_executed"] = True
            raw = original_relation(rule, payload)
            lineage["extraction_action"] = "NEW_VERSION_SINGLE_RELATION_EXTRACTION"
        else:
            cell["reason"] = "CACHE_REQUIRES_EXTRACTION_NOT_REQUESTED"
            return cell
        if raw["outcome"] == "NOT_EVALUATED":
            cell.update(reason="ORIGINAL_RELATION_UNEXECUTED", relation_result=raw)
            return cell
        state = mapped_state(candidate, raw["outcome"])
        cell.update(state=state, value={"T": True, "F": False, "U": None}[state], available=state != "U",
                    reason="CONDITION_DEFINED" if state != "U" else raw["reason"],
                    evaluation_status="OK", relation_result=raw)
        if not reuse and not old:
            cell.update(original_outcome=raw["outcome"], original_reason=raw["reason"])
    except Unavailable as exc:
        lineage["measurement_rejection"] = exc.reason
        lineage["extraction_action"] = "R01_AVAILABILITY_ONLY_NO_PREDICATE_RUN"
        if cached:
            lineage["status"] = "R01_DOMAIN_UNAVAILABLE_OLD_RESULT_NOT_REUSED"
        cell.update(state="U", evaluation_status="OK", reason=exc.reason,
                    relation_result={"outcome": exc.outcome, "reason": exc.reason})
    except Exception as exc:
        cell.update(state=None, value=None, available=False, evaluation_status="FAILED",
                    reason=type(exc).__name__ + ":" + str(exc))
        lineage["extraction_action"] = "FAILED"
        lineage["reuse"] = False
    return cell


def canonical_core(candidates, cells, allowed_sources=None):
    """Canonical deviation polarity; never pick a convenient alias on conflict."""
    groups = {}
    for c in candidates:
        if c["candidate_use"]["core"] and c["candidate_use"]["selectable_on_App177"] and (
                allowed_sources is None or c["provenance_group"] in allowed_sources):
            groups.setdefault(c["normalized_identity"], []).append(c)
    result = []
    for identity, members in sorted(groups.items()):
        members.sort(key=lambda c: c["rule_id"])
        normalized = []
        for c in members:
            cell = cells[c["atom_id"]]
            state = cell["state"]
            if state is not None and c["direct_OR_deviation_polarity"] == "NEGATIVE":
                state = negate(state)
            normalized.append((state, cell["available"], cell["evaluation_status"],
                               cell["reason"], c["measurement"]["profile"]))
        equal = all(n == normalized[0] for n in normalized)
        state, available, status, reason, _ = normalized[0]
        if not equal:
            state, available, status, reason = None, False, "FAILED", "ALIAS_DOMAIN_OR_VALUE_CONFLICT"
        result.append({"atom_id": identity, "canonical_rule_id": members[0]["rule_id"],
                       "aliases": [c["rule_id"] for c in members],
                       "source_groups": sorted({c["provenance_group"] for c in members}),
                       "state": state, "value": {"T": True, "F": False}.get(state),
                       "available": available, "evaluation_status": status, "reason": reason,
                       "alias_check": "PASS" if equal else "FAIL"})
    return result


def control_input(payload, spec):
    """Fixed per-field control representation. Numerical thresholds stay unfitted."""
    try:
        envelope(payload)
        fs = field_state(payload, spec)
        if not fs["available"]:
            return {"value": None, "available": False, "reason": fs["reason"], "evaluation_status": "OK", "field_state": fs}
        value = payload["features"][spec["field"]]
        encoder = spec["encoder"]
        if encoder == "UA_CLASS":
            value = _ua_class(value)
        elif encoder == "PLATFORM_CLASS":
            value = _platform_class(value)
        elif encoder == "LIST_LENGTH_TRAIN_QUANTILE":
            if any(type(v) is not str or not v.strip() for v in value):
                raise Unavailable("INVALID_LANGUAGE_LIST_ELEMENT")
            value = len(value)
        if value == "unknown":
            raise Unavailable("UNKNOWN_PARSER_CLASS")
        return {"value": value, "available": True, "reason": "OBSERVED_FIXED_CONTROL_INPUT", "evaluation_status": "OK", "field_state": fs}
    except Unavailable as exc:
        return {"value": None, "available": False, "reason": exc.reason, "evaluation_status": "OK", "field_state": fs}
    except Exception as exc:
        return {"value": None, "available": False, "reason": type(exc).__name__ + ":" + str(exc), "evaluation_status": "FAILED"}
