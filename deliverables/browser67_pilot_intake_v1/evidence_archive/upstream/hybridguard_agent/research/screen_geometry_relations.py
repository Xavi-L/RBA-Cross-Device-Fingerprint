"""One fixed, one-sided Web/Host geometry check; no training or imputation.

The CSSOM DPR includes page zoom and excludes visual/pinch zoom. Multiplying
by the separately observed VisualViewport.scale restores that second factor.
This does not identify DPR with Android display density. The Host content
rectangle is measured independently and is never reconstructed from Web data.
"""
import math

from .rule_learning.contracts import cell, logic

VERSION = "screen-geometry-relations-v1"
ATOM_ID = "SCREEN_GEOMETRY:WEB_PHYSICAL_VIEWPORT_EXCEEDS_HOST:v1"
BASE_TOLERANCE_PX = 2.0
FLOAT32_EPSILON = 2.0 ** -23
ROUNDING_OPERATIONS = 4
WEB_FIELDS = ("visual_viewport_width", "visual_viewport_height", "device_pixel_ratio", "visual_viewport_scale")


def parameters():
    return {"version": VERSION, "template_count": 1, "model_fit_calls": 0,
            "atom_id": ATOM_ID, "formula": "visual_axis_css * device_pixel_ratio * visual_viewport_scale > host_content_axis_px + tolerance_px",
            "host_content": "view_bounds_minus_padding_no_inset_subtraction",
            "tolerance_px": {"edge_rounding_px": BASE_TOLERANCE_PX,
                             "float32_epsilon": FLOAT32_EPSILON,
                             "relative_rounding_operations": ROUNDING_OPERATIONS,
                             "formula": "2 + 4 * 2**-23 * max(abs(projected_px), abs(host_content_px), 1)"},
            "axes": "OR", "parameter_fitting": "NONE",
            "scale_source": "current_sync_Web_DPR_times_visualViewport.scale",
            "host_callback_scale_use": "diagnostic_only_not_default_or_fallback",
            "source_surfaces": ["current_android_webview", "current_sync_web_geometry"],
            "identity_view_transform_required": True,
            "webview_padding_domain": "all_four_observed_zero; nonzero WebView rendering semantics not established",
            "same_current_document_and_host_stable_window_required": True}


def number(value, *, positive=True):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _web_value(web, name):
    fields = web.get("fields", {})
    entry = fields.get(name, {}) if isinstance(fields, dict) else {}
    if not isinstance(entry, dict) or entry.get("status") != "observed":
        return None, "WEB_FIELD_NOT_OBSERVED:" + name
    value = entry.get("value")
    if not number(value):
        return None, "WEB_FIELD_NOT_FINITE_POSITIVE:" + name
    return value, None


def evaluate(bound):
    """Only current raw geometry is read. No labels, phases, targets or history.

    A stable contradiction stays evaluable. Host stability never depends on
    any Host/Web agreement. Missing axes obey T OR U = T, F OR U = U.
    """
    diagnostics = {"relation_version": VERSION, "parameters": parameters()}
    def result(state, reason):
        value = cell(state, reason)
        value["diagnostics"] = diagnostics
        return {ATOM_ID: value}
    if not isinstance(bound, dict) or bound.get("status") != "OK":
        return result("FAILED", "CURRENT_RAW_BINDING_FAILED")
    evidence = bound.get("geometry_evidence", {})
    if evidence.get("evaluation_status") == "FAILED":
        diagnostics["geometry_issues"] = evidence.get("issues", [])
        return result("FAILED", "GEOMETRY_SOURCE_OR_EXECUTION_FAILED")
    geometry = bound.get("geometry")
    if not isinstance(geometry, dict) or evidence.get("usable_window") is not True:
        diagnostics["geometry_issues"] = evidence.get("issues", [])
        return result("U", "CURRENT_STABLE_GEOMETRY_WINDOW_UNAVAILABLE")
    host, after, web = geometry["host_before"], geometry["host_after"], geometry["web"]
    if any(host.get(name) != expected or after.get(name) != expected for name, expected in (
            ("view_scale_x", 1), ("view_scale_y", 1), ("rotation_degrees", 0),
            ("is_attached_to_window", True), ("is_shown", True))):
        return result("U", "HOST_VIEW_NOT_ATTACHED_VISIBLE_OR_IDENTITY_TRANSFORM")
    if host.get("content_region_definition") != "view_bounds_minus_padding_no_inset_subtraction":
        return result("U", "HOST_CONTENT_REGION_SEMANTICS_UNAVAILABLE")
    if any(type(host.get("padding_" + p + "_px")) not in (int, float)
           or host.get("padding_" + p + "_px") != 0
           for p in ("left", "top", "right", "bottom")):
        return result("U", "NONZERO_OR_UNOBSERVED_WEBVIEW_PADDING_OUTSIDE_ESTABLISHED_RENDERING_DOMAIN")
    values, issues = {}, {}
    for name in WEB_FIELDS:
        value, issue = _web_value(web, name)
        values[name] = value
        if issue: issues[name] = issue
    diagnostics.update(web_values=values, field_issues=issues,
                       host_callback_scale=host.get("scale"),
                       host_diagnostic_get_scale=host.get("diagnostic_get_scale"),
                       android_density_not_used=host.get("density"))
    dpr, visual_scale = values["device_pixel_ratio"], values["visual_viewport_scale"]
    if dpr is None or visual_scale is None:
        return result("U", "WEB_PHYSICAL_CONVERSION_SCALE_UNAVAILABLE")
    conversion = dpr * visual_scale
    if not math.isfinite(conversion):
        return result("U", "WEB_PHYSICAL_CONVERSION_NONFINITE")
    axes = {}
    for axis, pads in (("width", ("left", "right")), ("height", ("top", "bottom"))):
        extent = host.get(axis + "_px")
        padding = [host.get("padding_" + p + "_px") for p in pads]
        reported = host.get("content_" + axis + "_px")
        visual = values["visual_viewport_" + axis]
        entry = {"host_view_px": extent, "host_padding_px": padding,
                 "reported_host_content_px": reported, "web_visual_css": visual,
                 "conversion_css_to_physical": conversion}
        if not number(extent) or not all(number(p, positive=False) for p in padding):
            entry.update(state="U", reason="HOST_AXIS_OR_PADDING_UNAVAILABLE")
        else:
            content = extent - sum(padding)
            entry["host_content_px"] = content
            if not number(content) or not number(reported) or reported != content:
                entry.update(state="U", reason="HOST_CONTENT_DERIVATION_INCONSISTENT")
            elif visual is None:
                entry.update(state="U", reason="WEB_AXIS_UNAVAILABLE")
            else:
                projected = visual * conversion
                if not math.isfinite(projected):
                    entry.update(state="U", reason="PROJECTED_AXIS_NONFINITE")
                else:
                    tolerance = BASE_TOLERANCE_PX + ROUNDING_OPERATIONS * FLOAT32_EPSILON * max(abs(projected), abs(content), 1)
                    entry.update(projected_physical_px=projected, tolerance_px=tolerance,
                                 excess_px=projected - content,
                                 state="T" if projected > content + tolerance else "F",
                                 reason="MEASURED_CURRENT_AXIS_COMPARISON")
        axes[axis] = entry
    diagnostics["axes"] = axes
    state = logic([entry["state"] for entry in axes.values()], "OR")
    return result(state, {"T": "WEB_PHYSICAL_VIEWPORT_EXCEEDS_HOST_CONTENT",
                          "F": "WEB_PHYSICAL_VIEWPORT_WITHIN_HOST_UPPER_BOUND",
                          "U": "AXIS_EVIDENCE_INSUFFICIENT"}[state])
