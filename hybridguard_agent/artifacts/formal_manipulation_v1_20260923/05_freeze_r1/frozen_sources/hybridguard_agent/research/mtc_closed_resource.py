"""Finite final study using existing MTC records only; no attack verdicts."""
from __future__ import annotations

from collections import Counter
import math
import re

from hybridguard_agent.evidence.paired244 import field_contract, legacy_field_map, valid_type

IMPLEMENTATION = "mtc-closed-resource-predicates-v1"


def candidates():
    mapping = legacy_field_map()
    model = "android_native_data.device_model"
    specs = [
        ("NW-001", "model_build_token", [model, "web_data.user_agent"], {"require_dalvik": False},
         "Native 型号与 App UA 中显式 Build 型号的一致性", "model_app_ua",
         "Only unambiguous Android model-before-Build tokens; no inferred aliases, substring matching or recovery of reduced model. Custom UA may disagree.",
         ["closed-ua-reduction", "android-websettings-api"]),
        ("NVW-001", "model_build_token", [model, "webview_data.system_http_agent"], {"require_dalvik": True},
         "Native 型号与 Dalvik system HTTP agent 中显式型号的一致性", "model_system_agent",
         "System http.agent is a mutable process property, not current WebView JS UA. AOSP default and Native fields share Build.MODEL; not independent identity evidence.",
         ["closed-aosp-http-agent"]),
        ("NW-003", "screen_two_dimensions", ["android_native_data.screen_resolution_physical",
         "web_data.screen_resolution_logical", "web_data.device_pixel_ratio"], {"css_pixel_tolerance": 1.0},
         "App 显示尺寸与 App Web 尺寸的双边残差检查", "screen_geometry",
         "Sorted dimensions, fixed 1 CSS pixel arithmetic screen; Native is App DisplayMetrics, not panel size. Window/zoom/system UI may invalidate equality. No 10% threshold reuse.",
         ["android-display-metrics", "cssom-view-dpr"]),
        ("NW-005", "gpu_family", ["android_native_data.native_gpu_renderer", "web_data.webgl_renderer"],
         {"families": ["adreno", "mali", "powervr", "tegra", "vivante"],
          "software_tokens": ["swiftshader", "llvmpipe", "softpipe", "swrast"]},
         "Native GLES 与 App WebGL 的已识别 GPU 家族一致性", "native_app_gpu_family",
         "Narrow renderer-family relation replaces the unverified SoC/board lookup. Software fallback is not applicable; unknown/masked/ambiguous families remain unknown. Same family does not establish same GPU/device.",
         ["closed-webgl-renderer"]),
    ]
    return [{"candidate_id": rid, "rule_id": rid, "title": title, "predicate": pred,
             "implementation": IMPLEMENTATION, "version": "closed-resource-v1",
             "dependencies": [mapping[p] for p in deps], "parameters": params,
             "evidence_family": family, "source_lane": "device_mined_rule",
             "admission_mode": "empirical", "limitations": limits, "official_source_ids": refs}
            for rid, pred, deps, params, title, family, limits, refs in specs]


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in {
        "unknown", "null", "unsupported", "not available", "error"}


def model_token(ua, require_dalvik=False):
    if not _text(ua):
        return None, "UNKNOWN", "uninterpretable_agent"
    if require_dalvik and not ua.startswith("Dalvik/"):
        return None, "NOT_APPLICABLE", "outside_dalvik_agent_scope"
    matches = re.findall(r"Android\s+[^;()]+;\s*([^()]+?)\s+Build/[^\s;)]+", ua)
    if not matches:
        return None, "NOT_APPLICABLE", "no_explicit_model_build_token"
    if len(matches) != 1:
        return None, "UNKNOWN", "multiple_model_tokens"
    parts = [p.strip() for p in matches[0].split(";")]
    if len(parts) == 2 and re.fullmatch(r"[A-Za-z]{2}(?:[-_][A-Za-z]{2})?", parts[0]):
        parts = parts[1:]  # Explicit locale slot, never an arbitrary model alias.
    if len(parts) != 1 or not _text(parts[0]):
        return None, "UNKNOWN", "ambiguous_model_segment"
    if parts[0].casefold() == "k":
        return None, "NOT_APPLICABLE", "reduced_or_uninformative_model_token"
    return " ".join(parts[0].split()).casefold(), None, None


def gpu_family(value, params):
    if not _text(value):
        return None, "UNKNOWN"
    text = value.casefold()
    if any(token in text for token in params["software_tokens"]):
        return "software", "NOT_APPLICABLE"
    matches = [f for f in params["families"] if re.search(r"\b" + re.escape(f) + r"\b", text)]
    return (matches[0], None) if len(matches) == 1 else (None, "UNKNOWN")


def evaluate(candidate, projection):
    """Inspect declared feature/status/quality values only, after any view mask."""
    values = []
    for path in candidate["dependencies"]:
        value = projection["features"].get(path)
        if (projection["field_status"].get(path) != "observed" or
                projection["field_quality"].get(path) != "observed_value" or
                not valid_type(value, field_contract()[path])):
            return {"outcome": "UNKNOWN", "reason": "unavailable_dependency"}
        values.append(value)
    pred, params = candidate["predicate"], candidate["parameters"]
    if pred == "model_build_token":
        native, agent = values
        if not _text(native):
            return {"outcome": "UNKNOWN", "reason": "uninterpretable_native_model"}
        token, state, reason = model_token(agent, params["require_dalvik"])
        if state:
            return {"outcome": state, "reason": reason}
        match = " ".join(native.split()).casefold() == token
        details = {}
    elif pred == "screen_two_dimensions":
        native, web, dpr = values
        dims = [re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", v) for v in (native, web)]
        if not all(dims) or type(dpr) not in (float, int) or not math.isfinite(dpr) or dpr <= 0:
            return {"outcome": "UNKNOWN", "reason": "invalid_screen_operand"}
        n, w = [sorted(map(int, d.groups())) for d in dims]
        if min(n + w) <= 0:
            return {"outcome": "UNKNOWN", "reason": "nonpositive_screen_dimension"}
        residual = max(abs(n[i] / dpr - w[i]) for i in range(2))
        match = residual <= params["css_pixel_tolerance"]
        details = {"max_absolute_css_pixel_residual": residual}
    elif pred == "gpu_family":
        parsed = [gpu_family(v, params) for v in values]
        states = [state for _, state in parsed]
        if "NOT_APPLICABLE" in states:
            return {"outcome": "NOT_APPLICABLE", "reason": "software_rendering_not_hardware_family_comparison"}
        if "UNKNOWN" in states:
            return {"outcome": "UNKNOWN", "reason": "unknown_masked_or_ambiguous_gpu_family"}
        match = parsed[0][0] == parsed[1][0]
        details = {}
    else:
        raise ValueError("Unknown closed-resource predicate")
    return {"outcome": "MATCH" if match else "COUNTEREXAMPLE", "reason": pred, **details}


def describe(bundle):
    """Bounded descriptive diagnostics; their categories are never attack labels."""
    mapping = legacy_field_map()

    def get(alias):
        path = mapping[alias]
        field = bundle["fields"].get(path)
        return bundle["projection"]["features"][path] if field and field["available"] else None

    native_ram, web_ram = get("android_native_data.total_memory_gb"), get("web_data.device_memory")
    ram = None
    if all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (native_ram, web_ram)):
        ram = {"native_kernel_gib": native_ram, "web_bucket_gib": web_ram,
               "absolute_difference_gib": abs(native_ram - web_ram), "web_to_native_ratio": web_ram / native_ram}
    hw = " ".join(v for v in (get("android_native_data.device_board"), get("android_native_data.device_hardware")) if isinstance(v, str)).lower()
    renderer = get("web_data.webgl_renderer")
    sensor_aliases = ["has_accelerometer", "has_gyroscope", "has_magnetic_field", "has_light_sensor", "has_proximity_sensor"]
    sensors = [get("android_native_data." + a) for a in sensor_aliases]
    plugins, mimes = get("web_data.plugins_count"), get("web_data.mime_types_count")
    plugin_state = "unavailable"
    if all(type(v) in (int, float) and v >= 0 and int(v) == v for v in (plugins, mimes)):
        plugin_state = "zero_or_api_fallback" if plugins == mimes == 0 else "nonzero_exposure_not_attack"
    return {"abi_platform": {"native_abi": get("android_native_data.cpu_abi"), "web_platform": get("web_data.platform")},
            "memory": ram,
            "hardware": {"known_keyword_tokens": [t for t in ("goldfish", "ranchu", "emulator") if t in hw],
                         "web_software_keyword_observed": any(t in (renderer or "").lower()
                                                                for t in ("swiftshader", "llvmpipe", "softpipe", "swrast"))},
            "sensors": {"reported_total_count": get("android_native_data.sensor_total_count"),
                        "five_capability_flags": sensors},
            "plugins": {"state": plugin_state, "plugins_count": plugins, "mime_types_count": mimes},
            "native_available_fields": sum(p.startswith("app.android_native_data.") and v["available"]
                                           for p, v in bundle["fields"].items()),
            "attack_label": "UNKNOWN"}


def numeric_summary(values):
    values = sorted(v for v in values if type(v) in (int, float) and math.isfinite(v))
    if not values:
        return {"n": 0}
    def q(fraction):
        position = (len(values) - 1) * fraction
        lo, hi = math.floor(position), math.ceil(position)
        return values[lo] + (values[hi] - values[lo]) * (position - lo)
    return {"n": len(values), "min": values[0], "median": q(.5), "p95": q(.95), "max": values[-1]}


def summarize_descriptions(rows):
    return {"records": len(rows), "counting_unit": "P2 primary representative records; descriptive only",
            "abi_platform_pairs": [{"native_abi": a, "web_platform": p, "records": n}
                                   for (a, p), n in Counter((r["abi_platform"]["native_abi"], r["abi_platform"]["web_platform"]) for r in rows).most_common()],
            "memory_absolute_difference_gib": numeric_summary([r["memory"]["absolute_difference_gib"] for r in rows if r["memory"]]),
            "memory_web_native_ratio": numeric_summary([r["memory"]["web_to_native_ratio"] for r in rows if r["memory"]]),
            "memory_unavailable": sum(r["memory"] is None for r in rows),
            "sensor_reported_count": numeric_summary([r["sensors"]["reported_total_count"] for r in rows]),
            "five_capability_patterns": [{"flags": list(flags), "records": n} for flags, n in Counter(tuple(r["sensors"]["five_capability_flags"]) for r in rows).most_common()],
            "hardware_keyword_records": sum(bool(r["hardware"]["known_keyword_tokens"]) for r in rows),
            "software_renderer_keyword_records": sum(r["hardware"]["web_software_keyword_observed"] for r in rows),
            "plugin_exposure_states": dict(Counter(r["plugins"]["state"] for r in rows)),
            "native_available_fields": numeric_summary([r["native_available_fields"] for r in rows]),
            "verified_attack_or_benign_labels": 0, "detection_metrics": "NOT_EVALUATED"}
