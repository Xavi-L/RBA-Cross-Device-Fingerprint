"""One fixed, deliberately loose Android/WebView memory envelope.

The caller binds these fields to one current App record.  No identity, phase,
label, clean reference, browser pair, or fitted parameter enters evaluation.
This is a research consistency condition, not an assertion that every browser
must report its device's physical RAM, or an attack label.
"""
from __future__ import annotations

from copy import deepcopy
import math

from .rule_learning.contracts import cell
from .rule_learning.models import Atom

VERSION = "mtc-resource-relations-v1"
MEMORY_ID = "MTCREL:WEB_MEMORY_ABOVE_NATIVE_POWER2_ENVELOPE"
NATIVE_MEMORY = "app.android_native_data.memory_layer.total_memory_gb"
WEB_MEMORY = "app.web_data.navigator_layer.device_memory"
FIELDS = (NATIVE_MEMORY, WEB_MEMORY)
MINIMUM_NATIVE_GIB = 0.25


def registered_atoms():
    """A new two-surface condition, with no extra selection preference."""
    return (Atom(
        MEMORY_ID, "MTC_RESOURCE_RELATION", ("native84", "app_web67"),
        ("RESEARCHER_PROPOSED_MTC_RELATION_V1",), (MEMORY_ID,),
        "CATALOG_CONDITION", {
            "field": NATIVE_MEMORY, "field_refs": list(FIELDS),
            "relation_version": VERSION, "signal_group": "memory_capacity",
            "condition": {
                "operator": "WEB_MEMORY_ABOVE_NATIVE_POWER_OF_TWO_UPPER_ENVELOPE",
                "operands": list(FIELDS),
                "parameters": {
                    "units": "GiB", "native_minimum_gib": MINIMUM_NATIVE_GIB,
                    "bound": "smallest_power_of_two_greater_than_or_equal_to_native",
                    "comparison": "strict_greater_than", "learned_parameters": False,
                    "lower_web_exposures": "allowed", "browser_upper_cap": "not_assumed",
                    "domain": "same_current_Android_App_record_with_WebView_numeric_observations",
                },
            },
            "basis": "RESOURCE_REVIEW.md; Android kernel total and Chromium power-of-two exposure",
            "interpretation": "research_relation_deviation_not_universal_attack_evidence",
        }),)


def power_two_upper_envelope(native_gib):
    """Exact binary envelope, not a logarithm rounded near powers of two."""
    fraction, exponent = math.frexp(native_gib)
    return math.ldexp(1.0, exponent - 1 if fraction == 0.5 else exponent)


def evaluate(record):
    """Return one T/F/U cell; only the two declared operands affect its value.

    Missing/default/invalid inputs are U. An observed positive pair which
    exceeds the envelope is always T, including normal counterexamples.
    The same-record loader supplies a checked binding; absent or contradictory
    binding is an execution failure, separate from missing measured evidence.
    """
    diagnostics = {"relation_version": VERSION, "field_refs": list(FIELDS),
                   "fields": [], "native_kernel_gib": None, "web_exposed_gib": None,
                   "upper_envelope_gib": None, "parameters_fitted": False}

    def result(s, reason, category):
        return {MEMORY_ID: dict(cell(s, reason), diagnostics=dict(
            diagnostics, availability_category=category))}

    binding = record.get("source_binding") if isinstance(record, dict) else None
    if (not isinstance(binding, dict) or binding.get("binding_valid") is not True
            or binding.get("same_app_record") is not True
            or not isinstance(binding.get("app_session_id"), str)
            or not binding["app_session_id"]):
        return result("FAILED", "MEMORY_SAME_APP_RECORD_BINDING_REQUIRED", "binding_failure")
    if not isinstance(record, dict) or any(not isinstance(record.get(k), dict)
            for k in ("features", "field_status", "field_quality")):
        return result("U", "MEMORY_RECORD_INPUT_MISSING", "missing")
    values = []
    for field in FIELDS:
        present = field in record["features"]
        value = record["features"].get(field)
        status, quality = record["field_status"].get(field), record["field_quality"].get(field)
        diagnostics["fields"].append({"field": field, "value": deepcopy(value),
            "value_present": present, "source_status": status, "source_quality": quality})
        if not present:
            return result("U", "MEMORY_OPERAND_MISSING:" + field, "missing")
        if status != "observed" or quality != "observed_value":
            return result("U", "MEMORY_OPERAND_QUALITY_UNAVAILABLE:" + field, "quality_insufficient")
        if type(value) not in (int, float) or not math.isfinite(value):
            return result("U", "MEMORY_OPERAND_NOT_FINITE_NUMBER:" + field, "invalid_type_or_value")
        if value <= 0:
            return result("U", "MEMORY_OPERAND_NONPOSITIVE_OR_COLLECTOR_SENTINEL:" + field,
                          "missing_or_default")
        values.append(value)
    native, web = values
    diagnostics.update(native_kernel_gib=native, web_exposed_gib=web)
    if native < MINIMUM_NATIVE_GIB:
        return result("U", "MEMORY_NATIVE_BELOW_REGISTERED_0_25_GIB_DOMAIN", "not_applicable")
    try:
        bound = power_two_upper_envelope(native)
    except OverflowError:
        return result("U", "MEMORY_NATIVE_ENVELOPE_NOT_FINITE", "invalid_type_or_value")
    diagnostics["upper_envelope_gib"] = bound
    return result("T" if web > bound else "F",
                  "WEB_MEMORY_EXCEEDS_NATIVE_POWER2_ENVELOPE" if web > bound else
                  "WEB_MEMORY_WITHIN_NATIVE_POWER2_ENVELOPE", "observed_comparable")
