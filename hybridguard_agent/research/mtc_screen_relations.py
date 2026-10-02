"""One same-probe viewport boundary; no Native display equality is assumed."""
from __future__ import annotations

import math

from .rule_learning.contracts import cell, logic
from .rule_learning.models import Atom


VERSION = "mtc-screen-relations-v1"
ATOM_ID = "REL:SCREEN_VISUAL_EXCEEDS_LAYOUT:v1"
PREFIX = "app.web_data.screen_layer."
FIELDS = tuple(PREFIX + name for name in (
    "inner_width", "inner_height", "visual_viewport_width",
    "visual_viewport_height", "visual_viewport_scale"))
CSS_PIXEL_TOLERANCE = 1.0


def registered_atoms():
    """A fixed CSS-pixel boundary, with the ordinary semantic quality of zero."""
    return (Atom(
        ATOM_ID, "SCREEN_VIEWPORT_RELATION", ("app_web67",),
        ("RESEARCHER_PROPOSED_RELATION_V1",), (ATOM_ID,), "CATALOG_CONDITION",
        {"field_refs": list(FIELDS), "relation_version": VERSION,
         "signal_group": "display_geometry", "semantic_quality": 0,
         "condition": {
             "operator": "VISUAL_VIEWPORT_EXCEEDS_LAYOUT_AT_SCALE_GE_ONE",
             "operands": list(FIELDS),
             "parameters": {"minimum_visual_scale": 1.0,
                            "css_pixel_rounding_tolerance": CSS_PIXEL_TOLERANCE,
                            "axes": "OR", "parameter_fitting": "NONE"}},
         "units": "CSS pixels; visual_viewport_scale is dimensionless",
         "evidence_scope": "SAME_WEB_PROBE_NOT_INDEPENDENT_CROSS_LAYER",
         "source_refs": ["web_probe/canonical_web_probe.js:368",
                         "https://drafts.csswg.org/cssom-view/#dom-window-innerwidth",
                         "https://drafts.csswg.org/cssom-view/#the-visualviewport-interface"]}),)


def _positive_observation(record, field):
    features = record.get("features", {})
    if not isinstance(features, dict) or field not in features:
        return None, "FIELD_MISSING"
    status = record.get("field_status", {}).get(field)
    quality = record.get("field_quality", {}).get(field)
    if status != "observed":
        return None, "FIELD_NOT_OBSERVED:" + str(status)
    if quality != "observed_value":
        return None, "FIELD_QUALITY_INSUFFICIENT:" + str(quality)
    value = features[field]
    if type(value) not in (int, float):
        return None, "NUMERIC_TYPE_REQUIRED"
    if not math.isfinite(value):
        return None, "NONFINITE_NUMBER"
    if value in (0, -1):
        return None, "LEGACY_DEFAULT_OR_UNAVAILABLE_SENTINEL"
    if value < 0:
        return None, "POSITIVE_DIMENSION_REQUIRED"
    return value, None


def _binding_problem(record):
    binding = record.get("source_binding", {})
    if not isinstance(binding, dict) or any(binding.get(key) is not True for key in (
            "binding_valid", "same_app_record", "web_fields_same_sync_probe")):
        return "SAME_APP_SYNC_PROBE_BINDING_REQUIRED"
    session = binding.get("app_session_id")
    if type(session) is not str or not session:
        return "APP_SESSION_BINDING_REQUIRED"
    field_sessions = binding.get("field_session_ids", {})
    if not isinstance(field_sessions, dict):
        return "INVALID_FIELD_SESSION_BINDING"
    if any(field_sessions.get(field, session) != session for field in FIELDS):
        return "CROSS_SESSION_FIELDS_FORBIDDEN"
    return None


def evaluate(record):
    """Consume only current-record measurements and provenance validity gates.

    A known contradiction on one axis remains T if the other axis is unknown.
    Valid large displays, rotation, keyboard shrinkage, and zoom >= 1 are not
    turned into unknowns. Scale < 1 is outside this deliberately narrow domain.
    """
    if not isinstance(record, dict):
        return {ATOM_ID: {"value": None, "available": False,
                          "evaluation_status": "FAILED", "reason": "INVALID_RECORD"}}
    issue = _binding_problem(record)
    if issue:
        result = cell("U", issue)
        result["diagnostics"] = {"availability": "binding_insufficient"}
        return {ATOM_ID: result}
    values, problems = {}, {}
    for field in FIELDS:
        value, reason = _positive_observation(record, field)
        values[field] = value
        if reason:
            problems[field] = reason
    scale = values[FIELDS[4]]
    diagnostics = {"relation_version": VERSION, "field_issues": problems,
                   "observed_values": {f: record.get("features", {}).get(f) for f in FIELDS},
                   "units": "CSS pixels", "css_pixel_rounding_tolerance": CSS_PIXEL_TOLERANCE,
                   "parameter_fitting": "NONE"}
    if scale is None:
        result = cell("U", "VISUAL_SCALE_UNAVAILABLE")
        diagnostics["availability"] = "insufficient_observation"
    elif scale < 1:
        result = cell("U", "VISUAL_SCALE_BELOW_ONE_OUTSIDE_APPLICABLE_DOMAIN")
        diagnostics["availability"] = "not_applicable"
    else:
        axes = {}
        for axis, layout, visual in (("width", FIELDS[0], FIELDS[2]),
                                     ("height", FIELDS[1], FIELDS[3])):
            left, right = values[layout], values[visual]
            axes[axis] = ("U" if left is None or right is None else
                          "T" if right > left + CSS_PIXEL_TOLERANCE else "F")
        state = logic(axes.values(), "OR")
        result = cell(state, {"T": "VISUAL_VIEWPORT_EXCEEDS_LAYOUT_BOUNDARY",
                              "F": "VISUAL_VIEWPORT_WITHIN_LAYOUT_BOUNDARY",
                              "U": "AXIS_OBSERVATION_INSUFFICIENT"}[state])
        diagnostics.update(axes=axes, availability="evaluated" if state != "U" else "insufficient_observation")
    result["diagnostics"] = diagnostics
    return {ATOM_ID: result}
