"""Pure measurement of the frozen W0 base inputs for newly adapted App rows.

The caller supplies reviewed metadata. No files, labels, cache, model, fitted
thresholds or source-binding inference enter this function. This is the original
48-input W0 contract; semantic variant additions/removals belong to a later step.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .rule_learning.matrix import control_input, envelope, extract_atom, mask

VERSION = "w0-new-runtime-base-matrix-v1"
_PREFIX = "app.web_data."
_CATALOG = ("NW-006", "NW-007", "OFFDER-TOUCH-001", "P3-COLOR-APP", "WVWEB-004")
_BOOLEANS = (
    "audio_layer.audio_context_supported", "automation_surface_layer.webdriver",
    "execution_layer.local_storage_available", "execution_layer.session_storage_available",
    "graphics_layer.webgl2_supported", "navigator_layer.cookie_enabled",
    "navigator_layer.online", "network_api_layer.save_data",
    "permissions_layer.permissions_api_supported",
)
_NUMBERS = (
    "audio_layer.audio_output_latency", "audio_layer.audio_sample_rate",
    "automation_surface_layer.mime_types_count", "automation_surface_layer.plugins_count",
    "execution_layer.timezone_offset", "font_layer.font_probe_count",
    "graphics_layer.webgl_extensions_count", "graphics_layer.webgl_max_texture_size",
    "navigator_layer.device_memory", "navigator_layer.hardware_concurrency",
    "navigator_layer.max_touch_points", "network_api_layer.downlink_mbps",
    "network_api_layer.rtt_ms", "screen_layer.avail_height", "screen_layer.avail_width",
    "screen_layer.color_depth", "screen_layer.device_pixel_ratio", "screen_layer.inner_height",
    "screen_layer.inner_width", "screen_layer.orientation_angle", "screen_layer.outer_height",
    "screen_layer.outer_width", "screen_layer.pixel_depth", "screen_layer.visual_viewport_height",
    "screen_layer.visual_viewport_scale", "screen_layer.visual_viewport_width",
)
_PARSERS = {
    "navigator_layer.user_agent": ("UA_CLASS", ("script_client", "desktop_or_headless", "android_browser", "android_webview")),
    "navigator_layer.platform": ("PLATFORM_CLASS", ("android", "mobile_or_ambiguous", "desktop")),
}
_CONTROL_CONTRACT = {
    **{_PREFIX + f: ("boolean", "BOOL_EQ_TRUE") for f in _BOOLEANS},
    **{_PREFIX + f: ("number", "TRAIN_QUANTILE_LE") for f in _NUMBERS},
    **{_PREFIX + f: ("string", values[0]) for f, values in _PARSERS.items()},
    _PREFIX + "navigator_layer.languages": ("array", "LIST_LENGTH_TRAIN_QUANTILE"),
}
_EQUALITY = {
    **{"CONTROL:" + _PREFIX + f + ":EQ:True": True for f in _BOOLEANS},
    **{"CONTROL:" + _PREFIX + f + ":EQ:" + category: category
       for f, (_, categories) in _PARSERS.items() for category in categories},
}
W0_ATOM_IDS = frozenset(
    ["CAT:" + name for name in _CATALOG] + list(_EQUALITY)
    + ["UNFITTED_CONTROL:" + _PREFIX + f for f in (*_NUMBERS, "navigator_layer.languages")]
)
_CELL_KEYS = ("value", "available", "evaluation_status", "reason")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _index(records: Any, key: str, name: str) -> dict:
    _require(type(records) in (list, tuple), "INVALID_" + name)
    result = {}
    for item in records:
        _require(type(item) is dict and type(item.get(key)) is str and bool(item[key]), "INVALID_" + name)
        _require(item[key] not in result, "DUPLICATE_" + name)
        result[item[key]] = item
    return result


def measure_w0_base_inputs(payload: dict, *, definitions: dict,
                           candidate_definitions: list, rule_definitions: list,
                           control_specs: list) -> dict[str, dict]:
    """Return exactly 48 R04-compatible cells, leaving numeric inputs unfitted.

    Envelope or metadata mismatches raise ValueError before any measurement.
    Individual field unavailability and execution failure remain U/FAILED cells
    under the unchanged measurement kernels. Missing fields are never repaired.
    Metadata arguments are lists from the frozen ledger, catalog and field specs.
    """
    envelope(payload)
    _require(type(definitions) is dict, "INVALID_DEFINITIONS")
    allowlists = definitions.get("single_surface_allowlists")
    _require(type(allowlists) is dict, "INVALID_W0_ALLOWLIST")
    names = allowlists.get("app_web67")
    _require(type(names) is list and all(type(n) is str for n in names), "INVALID_W0_ALLOWLIST")
    _require(len(names) == len(set(names)) == 48 and set(names) == W0_ATOM_IDS,
             "EXACT_FROZEN_W0_ALLOWLIST_REQUIRED")
    atoms = _index(definitions.get("atoms"), "atom_id", "ATOM_DEFINITIONS")
    candidates = _index(candidate_definitions, "atom_id", "CANDIDATE_DEFINITIONS")
    rules = _index(rule_definitions, "rule_id", "RULE_DEFINITIONS")
    specs = _index(control_specs, "field", "CONTROL_SPECS")
    operations = []
    for name in names:
        atom = atoms.get(name)
        _require(type(atom) is dict and atom.get("surfaces") == ["app_web67"], "W0_ATOM_SURFACE_MISMATCH")
        provenance = atom.get("provenance")
        _require(type(provenance) is dict, "INVALID_W0_PROVENANCE")
        if name.startswith("CAT:"):
            candidate, rule = candidates.get(name), rules.get(name[4:])
            _require(type(candidate) is dict and type(rule) is dict, "W0_CATALOG_DEFINITION_MISSING")
            measurement = candidate.get("measurement")
            refs = provenance.get("field_refs")
            _require(type(refs) is list and refs and all(type(p) is str and p.startswith(_PREFIX) for p in refs),
                     "W0_CATALOG_FIELD_SCOPE_MISMATCH")
            _require(atom.get("orientation") == "CATALOG_CONDITION"
                     and candidate.get("rule_id") == name[4:]
                     and candidate.get("observation_surfaces") == ["app_web67"]
                     and candidate.get("dependencies") == rule.get("dependencies") == refs
                     and candidate.get("predicate") == rule.get("predicate")
                     and candidate.get("predicate_version") == rule.get("version")
                     and type(measurement) is dict and measurement.get("defined") is True
                     and measurement.get("condition") == provenance.get("condition"),
                     "W0_CATALOG_CONTRACT_MISMATCH")
            schema = candidate.get("dependency_schema")
            _require(type(schema) is list and [s.get("field") for s in schema if type(s) is dict] == refs
                     and all(type(s) is dict and s.get("surface") == "app_web67" for s in schema),
                     "W0_CATALOG_DEPENDENCY_SCHEMA_MISMATCH")
            operations.append((name, candidate, rule))
        else:
            field = provenance.get("field")
            _require(type(field) is str and field in _CONTROL_CONTRACT, "W0_CONTROL_FIELD_MISMATCH")
            spec = specs.get(field)
            _require(type(spec) is dict and spec.get("surface") == provenance.get("surface") == "app_web67"
                     and (spec.get("type"), spec.get("encoder")) == _CONTROL_CONTRACT[field]
                     and spec.get("encoder") == provenance.get("encoder"), "W0_CONTROL_SPEC_MISMATCH")
            if name in _EQUALITY:
                equals = provenance.get("equals")
                _require(atom.get("orientation") == "CONTROL_EQUALITY"
                         and name == "CONTROL:" + field + ":EQ:" + str(equals)
                         and type(equals) is type(_EQUALITY[name]) and equals == _EQUALITY[name]
                         and provenance.get("fit_required") is False,
                         "W0_FIXED_EQUALITY_MISMATCH")
            else:
                _require(atom.get("orientation") == "UNFITTED_NUMERIC_MEASUREMENT"
                         and name == "UNFITTED_CONTROL:" + field, "W0_UNFITTED_INPUT_MISMATCH")
            operations.append((name, spec, None))

    projected = mask(payload, ["app_web67"])
    result = {}
    for name, declaration, rule in operations:
        if rule is not None:
            measured = extract_atom(declaration, rule, projected)
        else:
            measured = control_input(projected, declaration)
            if name in _EQUALITY:
                measured["value"] = (measured["value"] == _EQUALITY[name]
                                     if measured["evaluation_status"] == "OK" and measured["available"] else None)
        result[name] = {key: deepcopy(measured[key]) for key in _CELL_KEYS}
    return result
