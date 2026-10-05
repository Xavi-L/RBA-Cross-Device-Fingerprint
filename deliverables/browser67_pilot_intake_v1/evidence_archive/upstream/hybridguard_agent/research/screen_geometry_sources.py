"""Explicit v15/v16 geometry batch binding, separate from historical adapters."""
from copy import deepcopy
import math

from . import mtc_relation_sources as original

VERSION = "screen-geometry-source-binding-v1"
GEOMETRY_SCHEMA = "webview-geometry-v1"
WEB_SCHEMA = "webview-web-geometry-v1"
SUPPORTED_COLLECTORS = {
    15: ("1.6.8-expanded-v2.2-geometry", "featureapp-geometry-v1"),
    16: ("1.6.9-expanded-v2.2-geometry", "featureapp-geometry-v1.1"),
}
HOST_STABLE_FIELDS = ("width_px", "height_px", "padding_left_px", "padding_top_px", "padding_right_px", "padding_bottom_px",
                     "location_in_window_px", "global_visible_rect_px", "window_visible_display_frame_px", "orientation",
                     "density", "density_dpi", "view_scale_x", "view_scale_y", "rotation_degrees", "root_width_px", "root_height_px",
                     "parent_width_px", "parent_height_px", "root_window_insets", "web_settings")


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def geometry_evidence(geometry, session_id):
    """No values from Web are compared with Host when deciding stability."""
    result = {"usable_window": False, "evaluation_status": "OK", "issues": []}
    def fail(reason, execution=False):
        result["issues"].append(reason)
        if execution: result["evaluation_status"] = "FAILED"
        return result
    if geometry is None:
        return fail("GEOMETRY_MODULE_MISSING")
    if not isinstance(geometry, dict) or geometry.get("schema_version") != GEOMETRY_SCHEMA:
        return fail("GEOMETRY_MODULE_SCHEMA_INVALID", True)
    if geometry.get("session_id") != session_id:
        return fail("GEOMETRY_CURRENT_SESSION_MISMATCH", True)
    if geometry.get("read_status") != "observed":
        return fail("GEOMETRY_MODULE_" + str(geometry.get("read_status")) + ":" + str(geometry.get("reason")),
                    geometry.get("read_status") in ("runtime_error", "error", "failed"))
    attempts = geometry.get("attempts")
    if not isinstance(attempts, list) or not attempts or len(attempts) > 2:
        return fail("GEOMETRY_ATTEMPT_HISTORY_MISSING", True)
    observation_id = geometry.get("selected_observation_id")
    if not isinstance(observation_id, str) or not observation_id or any(not isinstance(a, dict) or not isinstance(a.get("observation_id"), str) for a in attempts):
        return fail("GEOMETRY_OBSERVATION_ID_TYPE_INVALID", True)
    selected = [a for a in attempts if isinstance(a, dict) and a.get("observation_id") == observation_id]
    if not observation_id or len(selected) != 1 or len({a.get("observation_id") for a in attempts if isinstance(a, dict)}) != len(attempts):
        return fail("GEOMETRY_OBSERVATION_ID_NOT_UNIQUE", True)
    chosen = selected[0]
    if any(chosen.get(k) != geometry.get(k) for k in ("session_id", "webview_instance_id", "document_generation")):
        return fail("GEOMETRY_SELECTED_ATTEMPT_IDENTITY_MISMATCH", True)
    if any(chosen.get(k) != geometry.get(k) for k in ("host_before", "web", "host_after")):
        return fail("GEOMETRY_SELECTED_PAYLOAD_MISMATCH", True)
    before, after, web = (geometry.get(k) for k in ("host_before", "host_after", "web"))
    if not all(isinstance(x, dict) for x in (before, after, web)):
        return fail("GEOMETRY_BRACKET_OR_WEB_MISSING", True)
    if web.get("schema_version") != WEB_SCHEMA:
        return fail("GEOMETRY_WEB_SCHEMA_INVALID", True)
    binding = web.get("binding", {})
    expected = {k: chosen.get(k) for k in ("session_id", "webview_instance_id", "document_generation", "observation_id", "attempt_id")}
    if not isinstance(binding, dict) or any(binding.get(k) != v or v is None for k, v in expected.items()):
        return fail("GEOMETRY_WEB_BINDING_MISMATCH", True)
    if not geometry.get("document_id") or web.get("document_id") != geometry["document_id"]:
        return fail("GEOMETRY_DOCUMENT_ID_MISMATCH", True)
    if geometry.get("binding_valid") is not True or chosen.get("binding_valid") is not True:
        return fail("GEOMETRY_COLLECTOR_BINDING_NOT_CONFIRMED", True)
    if geometry.get("host_stable") is not True or chosen.get("host_stable") is not True:
        return fail("GEOMETRY_COLLECTOR_OBSERVED_HOST_CHANGE")
    if any(h.get("thread") != "android_main" or h.get("read_status") != "observed" for h in (before, after)):
        return fail("GEOMETRY_MAIN_THREAD_HOST_READ_REQUIRED", True)
    if not all(isinstance(h.get("sequence"), dict) and isinstance(h.get("clock"), dict) for h in (before,after)):
        return fail("GEOMETRY_HOST_SEQUENCE_OR_CLOCK_INVALID", True)
    if (not before.get("sequence") or before.get("sequence") != after.get("sequence")
            or before["sequence"].get("document") != geometry.get("document_generation")
            or any(before.get(k) != after.get(k) for k in HOST_STABLE_FIELDS)):
        return fail("GEOMETRY_HOST_CHANGED_DURING_BRACKET")
    start, end = (h.get("clock", {}).get("elapsed_realtime_ms") for h in (before, after))
    outer_start, outer_end = geometry.get("started_elapsed_realtime_ms"), geometry.get("finished_elapsed_realtime_ms")
    if (not all(_finite(x) for x in (start, end, outer_start, outer_end))
            or not outer_start <= start <= end <= outer_end or end - start > 1800):
        return fail("GEOMETRY_ANDROID_BRACKET_TIME_INVALID")
    clock = web.get("clock", {})
    if not isinstance(clock, dict):
        return fail("GEOMETRY_WEB_CLOCK_INVALID")
    for first, last in (("epoch_start_ms", "epoch_end_ms"), ("performance_start_ms", "performance_end_ms")):
        if not all(_finite(clock.get(k)) for k in (first, last)) or clock[first] > clock[last]:
            return fail("GEOMETRY_WEB_CLOCK_INVALID")
    # Deliberately do not subtract Android monotonic time from JS performance.
    if web.get("read_status") not in ("observed", "partial"):
        return fail("GEOMETRY_WEB_READ_UNAVAILABLE", web.get("read_status") == "error")
    result.update(usable_window=True, observation_id=observation_id,
                  document_id=web["document_id"], android_bracket_ms=end-start,
                  stability_claim="no_host_change_observed_not_atomic")
    return result


def bind_current(raw, *, session_id, source_reference, environment_id=None):
    """Explicit v15 batch and v16 error-boundary fix; old adapters unchanged."""
    binding = {"sample_id": "screengeometry-" + session_id, "app_session_id": session_id,
               "mode": VERSION, "raw_reference": source_reference}
    errors = []
    if not isinstance(raw, dict) or not isinstance(raw.get("canonical_received_payload"), dict):
        return original._result(binding, errors=["SCREEN_RAW_PAYLOAD_MISSING"])
    payload = raw["canonical_received_payload"]
    manifest = payload.get("collection_manifest", {})
    if not isinstance(manifest, dict): manifest = {}
    if not session_id or raw.get("session_id") != session_id or payload.get("session_id") != session_id:
        errors.append("SCREEN_CURRENT_APP_SESSION_MISMATCH")
    code = manifest.get("collector_version_code")
    collector = SUPPORTED_COLLECTORS.get(code) if type(code) is int else None
    if (raw.get("raw_payload_archive_schema_version") != "expanded-raw-payload-v1"
            or payload.get("schema_version") != "expanded-v2.2-status"
            or payload.get("collector_app") != "featureapp"
            or collector is None or manifest.get("collector_version_name") != collector[0]):
        errors.append("SCREEN_UNSUPPORTED_BATCH_COLLECTOR")
    if environment_id is not None and manifest.get("device_manifest_id") != environment_id:
        errors.append("SCREEN_CURRENT_APP_ENVIRONMENT_MISMATCH")
    errors.extend(original._field_sessions(payload, session_id))
    features = {}
    for name in original.APP_ROOTS:
        if name in payload:
            if not isinstance(payload[name], dict): errors.append("SCREEN_APP_SURFACE_NOT_OBJECT:" + name)
            else: features.update(original._flatten(payload[name], "app." + name))
    status_container = payload.get("collection_status", {})
    statuses = status_container.get("fields", {}) if isinstance(status_container, dict) else None
    if not isinstance(statuses, dict):
        errors.append("SCREEN_FIELD_STATUS_MISSING"); statuses = {}
    statuses = {"app." + k: v for k, v in statuses.items()
                if isinstance(k, str) and k.startswith(tuple(n + "." for n in original.APP_ROOTS))}
    qualities = {k: original._quality(k, features.get(k), v) for k, v in statuses.items()}
    binding.update(collector_version_code=manifest.get("collector_version_code"),
                   collector_version_name=manifest.get("collector_version_name"), receipt_id=raw.get("receipt_id"))
    bound = original._result(binding, features, statuses, qualities, errors)
    observations = payload.get("collection_observations", {})
    geometry = observations.get("webview_geometry") if isinstance(observations, dict) else None
    bound["geometry"] = deepcopy(geometry)
    bound["geometry_evidence"] = geometry_evidence(geometry, session_id)
    module_version = geometry.get("collector_version") if isinstance(geometry, dict) else None
    # The App can be destroyed after accepting the legacy payload but before
    # dispatching this module. Its small unavailable receipt has no module
    # header; the same payload's manifest already declares the version. This
    # admits no geometry values or usable window and does not invent a version.
    if (isinstance(geometry, dict) and module_version is None
            and geometry.get("read_status") == "unavailable"
            and geometry.get("reason") == "activity_destroyed_before_geometry_dispatch"):
        module_version = manifest.get("geometry_observer_version")
        bound["geometry_evidence"]["module_version_source"] = "current_collection_manifest.geometry_observer_version"
    if isinstance(geometry, dict) and collector is not None and module_version != collector[1]:
        bound["geometry_evidence"] = {"usable_window": False, "evaluation_status": "FAILED",
                                      "issues": ["GEOMETRY_MODULE_COLLECTOR_VERSION_MISMATCH"]}
    return bound
