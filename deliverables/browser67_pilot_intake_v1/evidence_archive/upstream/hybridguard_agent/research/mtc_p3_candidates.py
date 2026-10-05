"""Finite P3 relation templates and status-aware, label-free predicates.

MATCH/COUNTEREXAMPLE describe a relation, never a device's attack status.
No search over arbitrary field pairs, no fit or mutation of predicates at runtime.
"""
import math
import re

N = "app.android_native_data."
H = "app.webview_data."
A = "app.web_data."
B = "browser.web_data."


def candidate_templates():
    out = []

    def add(cid, family, paths, predicate, source, limitations, *, mode="empirical", params=None, sources=None):
        out.append({"candidate_id": cid, "version": "2.0.1", "family": family,
                    "dependencies": paths, "predicate": predicate, "parameters": params or {},
                    "source_lane": source, "admission_mode": mode,
                    "scope": "P1 passed paired244 P2 primary representatives; observed dependency values only",
                    "support_scope": "global_empirical", "limitations": limitations,
                    "official_source_ids": sources or [], "standalone_attack_decision": False,
                    "runtime_integration": "NOT_INTEGRATED_P4_REQUIRED"})

    common = [
        ("TIMEZONE-ID", "execution_layer.timezone_id", "timezone aliases, per-container settings, capture time", "XENV"),
        ("TIMEZONE-OFFSET", "execution_layer.timezone_offset", "DST boundary or time/settings changes between captures", "XENV"),
        ("LANGUAGE", "navigator_layer.language", "per-app and browser language preferences", "XENV"),
        ("LANGUAGES", "navigator_layer.languages", "ordered preference list can differ between containers", "XENV"),
        ("TOUCH", "navigator_layer.max_touch_points", "browser exposure/privacy/input device differences", "XENV"),
        ("PLATFORM", "navigator_layer.platform", "legacy platform exposure is user-agent dependent", "XENV"),
        ("CORES", "navigator_layer.hardware_concurrency", "privacy caps and logical processor availability; 0 is sentinel", "MEM"),
        ("MEMORY", "navigator_layer.device_memory", "implementation-defined approximation and caps; 0 is sentinel", "MEM"),
        ("DPR", "screen_layer.device_pixel_ratio", "zoom, density and per-container window configuration", "SCREEN"),
        ("COLOR", "screen_layer.color_depth", "browser screen exposure/privacy differences", "SCREEN"),
        ("GPU-VENDOR", "graphics_layer.webgl_vendor", "ANGLE wrappers, privacy and different graphics backends", "GPU"),
        ("GPU-RENDERER", "graphics_layer.webgl_renderer", "ANGLE wrappers, privacy and different graphics backends", "GPU"),
        ("CANVAS", "graphics_layer.canvas_hash", "different rendering kernels/fonts; equality is not required", "HASH"),
        ("AUDIO-HASH", "audio_layer.audio_hash", "kernel and audio path differences; equality is not required", "HASH"),
        ("AUDIO-RATE", "audio_layer.audio_sample_rate", "audio output device and context configuration differ", "HASH"),
        ("FONT", "font_layer.available_font_hash", "font set and measurement differences between engines", "HASH"),
        ("PLUGIN", "automation_surface_layer.plugins_hash", "empty/synthetic plugin inventory is not hardware identity", "HASH"),
        ("MIME", "automation_surface_layer.mime_types_hash", "empty/synthetic MIME inventory is not hardware identity", "HASH"),
    ]
    for suffix, path, limit, family in common:
        # Hash/kernel-sensitive equalities are diagnostics even if this cohort happens to agree.
        mode = "descriptive_only" if family in {"GPU", "HASH"} else "empirical"
        add("P3-X-" + suffix, family, [A + path, B + path], "equal", "device_mined_rule", limit, mode=mode)
    add("P3-X-SCREEN-SIZE", "SCREEN", [A + "screen_layer.screen_resolution_logical", B + "screen_layer.screen_resolution_logical"],
        "dimension_equal", "device_mined_rule", "orientation normalized only; multiwindow and screen exposure can differ")

    for surface, prefix in (("APP", A), ("BROWSER", B)):
        add("P3-OS-" + surface, "OS", [N + "build_fingerprint_layer.os_version", prefix + "navigator_layer.user_agent"],
            "android_major_equal", "device_mined_rule", "naive equality ignores UA reduction/custom UA; diagnostic only", mode="descriptive_only")
        add("P3-SCREEN-" + surface, "SCREEN", [N + "screen_display_layer.screen_resolution_physical", prefix + "screen_layer.screen_resolution_logical", prefix + "screen_layer.device_pixel_ratio"],
            "screen_short_side", "device_mined_rule", "Native field is App display metrics, not panel resolution; short side avoids orientation but not split windows/zoom",
            params={"css_pixel_tolerance": 1.0})
        add("P3-COLOR-" + surface, "SCREEN", [prefix + "screen_layer.color_depth", prefix + "screen_layer.pixel_depth"],
            "equal", "official_derived_semantic_rule", "CSSOM screen exposure relation, not independent hardware evidence", mode="semantic")
    add("P3-UA-REDUCED-BROWSER", "OS", [N + "build_fingerprint_layer.os_version", B + "navigator_layer.user_agent"],
        "browser_android_compatible", "official_derived_semantic_rule", "Chrome Android >=107 reduced Android 10 token is compatible, not actual OS recovery; customized UA can still violate",
        mode="semantic", params={"reduced_chrome_min_major": 107, "reduced_android_token": 10})
    for cid, path in (("DEFAULT", "default_ua_native"), ("SETTINGS", None)):
        host_path = H + ("kernel_container_layer." + path if path else "webview_settings_layer.settings_user_agent")
        add("P3-UA-" + cid, "OS", [host_path, A + "navigator_layer.user_agent"], "equal", "device_mined_rule",
            "host configuration and JS navigator UA can differ; no universal equality guarantee")
    add("P3-PROVIDER-PARSE", "OS", [H + "kernel_container_layer.webview_provider_version", H + "kernel_container_layer.webview_provider_major"],
        "provider_parse", "collector_derived_consistency", "major is parsed from version by this collector; duplicate derivation, not new detection power", mode="collector")

    add("P3-GPU-COPY", "GPU", [N + "graphics_layer.native_gpu_renderer", N + "graphics_layer.egl_renderer"], "equal",
        "collector_derived_consistency", "both copy one glRenderer value; tautological collector consistency", mode="collector")
    add("P3-MEM-AVAILABLE", "MEM", [N + "memory_layer.avail_memory_gb", N + "memory_layer.total_memory_gb"], "less_equal",
        "official_derived_semantic_rule", "same MemoryInfo snapshot, GB units; this is memory accounting, not identity", mode="semantic")
    sensor = N + "sensor_matrix_layer."
    for name in ("sensor_name_count", "sensor_vendor_count"):
        add("P3-SENSOR-" + name.removeprefix("sensor_").upper(), "SENSOR", [sensor + name, sensor + "sensor_total_count"],
            "less_equal", "collector_derived_consistency", "distinct subset count cannot exceed source list count", mode="collector")
    add("P3-SENSOR-TYPE-COUNT", "SENSOR", [sensor + "sensor_type_list", sensor + "sensor_total_count"], "list_count",
        "collector_derived_consistency", "collector returns distinct sorted type list; same-list derivation", mode="collector")
    add("P3-SENSOR-TYPE-ORDER", "SENSOR", [sensor + "sensor_type_list"], "sorted_unique", "collector_derived_consistency",
        "collector implementation invariant, not independent evidence", mode="collector")
    for name, sensor_type in [("accelerometer", 1), ("magnetic_field", 2), ("gyroscope", 4), ("light_sensor", 5),
                               ("pressure_sensor", 6), ("proximity_sensor", 8), ("gravity_sensor", 9),
                               ("rotation_vector", 11), ("step_detector", 18), ("step_counter", 19)]:
        add("P3-SENSOR-" + name.upper(), "SENSOR", [sensor + "has_" + name, sensor + "sensor_type_list"], "sensor_presence",
            "official_derived_semantic_rule", "true -> type listed only; false may reflect permission/default-sensor differences; dynamic sensor timing can differ",
            mode="semantic", params={"sensor_type": sensor_type})
    for c in out:
        family = c["family"]
        sources = {
            "OS": ["android-webview-ua-reduction", "android-websettings-api", "android-webview-provider-api"],
            "SCREEN": ["android-display-metrics", "cssom-view-dpr"],
            "GPU": ["khronos-webgl-renderer-info"],
            "SENSOR": ["android-sensor-manager"],
            "MEM": ["whatwg-hardware-concurrency", "w3c-device-memory", "android-memory-info"],
            "HASH": ["w3c-web-audio-privacy", "whatwg-navigator-plugins"],
        }.get(family, [])
        c["official_source_ids"] = sources
        c["local_source_paths"] = [
            "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv",
            "android_app/HybridGuard/featureapp/src/main/java/com/example/hybridguard/featureapp/ExpandedFingerprintCollector.kt",
            "web_probe/canonical_web_probe.js",
        ]
        c["units_and_normalization"] = (
            "screen_short_side: native reported pixel short side / DPR versus CSS short side; absolute 1 CSS px tolerance. "
            "dimension_equal sorts axes only. Other equalities preserve exact strings/array order and numerical equality; booleans never equal numbers. "
            "Memory operands GB; timezone operands minutes; sensor operands integer counts/types. No imputation.")
        c["execution_test"] = "hybridguard_agent.tests.test_mtc_p3_candidates"
    return out


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _count(value):
    return _number(value) and value >= 0 and int(value) == value


def _semantic_equal(left, right):
    if _number(left) and _number(right):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_semantic_equal(a, b) for a, b in zip(left, right))
    return left == right


def _dimensions(value):
    match = re.fullmatch(r"(\d+)[xX](\d+)", value) if isinstance(value, str) else None
    if not match or min(map(int, match.groups())) <= 0:
        raise ValueError("invalid_positive_dimensions")
    return sorted(map(int, match.groups()))


def _major(value, pattern):
    match = re.search(pattern, value) if isinstance(value, str) else None
    if not match:
        raise ValueError("version_token_unavailable")
    return int(match.group(1))


def evaluate_candidate(candidate, record):
    """Record projection contains features/status/quality only; all unknowns explicit."""
    deps = candidate["dependencies"]
    values = []
    for path in deps:
        value = record["features"].get(path)
        if (record["field_status"].get(path) != "observed" or
                record["field_quality"].get(path) != "observed_value" or value is None or value == ""):
            return {"outcome": "UNKNOWN", "reason": "unavailable_dependency", "dependency": path}
        if isinstance(value, str) and value.strip().lower() in {"unknown", "error", "unsupported", "not available"}:
            return {"outcome": "UNKNOWN", "reason": "collector_placeholder", "dependency": path}
        if path.endswith((".device_memory", ".hardware_concurrency")) and (not _number(value) or value <= 0):
            return {"outcome": "UNKNOWN", "reason": "nonpositive_navigator_sentinel", "dependency": path}
        if type(value) is float and not math.isfinite(value):
            return {"outcome": "UNKNOWN", "reason": "nonfinite_numeric_value", "dependency": path}
        if path.endswith((".color_depth", ".pixel_depth", ".device_pixel_ratio", ".audio_sample_rate")) and (not _number(value) or value <= 0):
            return {"outcome": "UNKNOWN", "reason": "invalid_positive_measurement", "dependency": path}
        values.append(value)
    name = candidate["predicate"]
    params = candidate["parameters"]
    details = {}
    try:
        if name == "equal":
            matches = _semantic_equal(*values)
        elif name == "dimension_equal":
            matches = _dimensions(values[0]) == _dimensions(values[1])
        elif name == "less_equal":
            if not all(_number(v) and v >= 0 for v in values):
                raise ValueError("invalid_nonnegative_numeric_operand")
            if "sensor_matrix_layer" in deps[0] and not all(_count(v) for v in values):
                raise ValueError("invalid_sensor_count")
            matches = values[0] <= values[1]
        elif name == "list_count":
            if (not isinstance(values[0], list) or not _count(values[1])
                    or not all(type(v) is int and v >= 1 for v in values[0])):
                raise ValueError("invalid_sensor_count")
            matches = len(values[0]) <= values[1]
        elif name == "sorted_unique":
            if not isinstance(values[0], list) or not all(type(v) is int and v >= 1 for v in values[0]):
                raise ValueError("invalid_sensor_type_list")
            matches = values[0] == sorted(set(values[0]))
        elif name == "sensor_presence":
            if (type(values[0]) is not bool or not isinstance(values[1], list)
                    or not all(type(v) is int and v >= 1 for v in values[1])):
                raise ValueError("invalid_sensor_presence")
            if not values[0]:
                return {"outcome": "NOT_APPLICABLE", "reason": "antecedent_false_not_evidence_of_attack"}
            matches = params["sensor_type"] in values[1]
        elif name == "provider_parse":
            if not _count(values[1]):
                raise ValueError("invalid_provider_major")
            matches = _major(values[0], r"^(\d+)\.") == values[1]
        elif name in {"android_major_equal", "browser_android_compatible"}:
            native = _major(values[0], r"^(?:Android\s+)?(\d+)")
            exposed = _major(values[1], r"Android\s+(\d+)")
            matches = native == exposed
            if name == "browser_android_compatible":
                chrome_token = re.search(r"Chrome/(\d+)\.", values[1])
                chrome = int(chrome_token.group(1)) if chrome_token else 0
                # A reduced UA is deliberately not an OS measurement. This branch is NA,
                # never a positive consistency vote or a way to inflate agreement.
                if chrome >= params["reduced_chrome_min_major"] and exposed == params["reduced_android_token"]:
                    return {"outcome": "NOT_APPLICABLE", "reason": "reduced_ua_os_unidentifiable"}
        elif name == "screen_short_side":
            native, web = _dimensions(values[0]), _dimensions(values[1])
            dpr = values[2]
            if not _number(dpr) or dpr <= 0:
                raise ValueError("invalid_positive_dpr")
            residual = abs(native[0] / dpr - web[0])
            details = {"absolute_css_pixel_residual": residual}
            matches = residual <= params["css_pixel_tolerance"]
        else:
            raise ValueError("uncompiled_predicate")
    except (ValueError, TypeError) as exc:
        return {"outcome": "UNKNOWN", "reason": str(exc)}
    return {"outcome": "MATCH" if matches else "COUNTEREXAMPLE", "reason": name, **details}
