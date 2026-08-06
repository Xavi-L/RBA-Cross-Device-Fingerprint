"""Build a deterministic, redacted EvidenceBundle v2.

This extractor deliberately supports only the evidence that the current
three-layer featureapp payload can substantiate.  It does not turn an observed
inconsistency, ADB state, cloud context, or missing field into an attack label
or a calibrated risk score.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any


EVIDENCE_BUNDLE_V2 = "evidence-bundle-v2"
EVIDENCE_EXTRACTOR_VERSION = "deterministic-evidence-extractor-v2"
LAYER_NAMES = ("android_native_data", "webview_data", "web_data")
UNAVAILABLE_STATES = frozenset(
    {
        "unsupported_by_os",
        "permission_denied",
        "runtime_error",
        "timeout",
        "not_applicable",
    }
)
UNASSESSED_EVIDENCE_GROUPS = {
    "browser_pair": "No independently paired system-browser payload is part of this runtime input.",
    "attack_scenario": "Attack labels, tool names, and pair roles are intentionally excluded from runtime evidence.",
    "calibrated_fusion": "No independently validated calibration model is available in the current data stage.",
    "empirical_case_retrieval": "Training-fold-only cases are not enabled for this runtime baseline.",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def get_path(value: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = value
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return default
        current = current[segment]
    return current


def _leaf_items(value: Any, prefix: str) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaf_items(child, f"{prefix}.{key}")
        return
    yield prefix, value


def _flatten_layer(layer_name: str, value: Any) -> dict[str, Any]:
    """Accept both legacy flat payloads and v2.2 status-bearing nested layers."""
    if not isinstance(value, dict):
        return {}
    if not any(isinstance(child, dict) for child in value.values()):
        return dict(value)

    flattened: dict[str, Any] = {}
    for source_path, child in _leaf_items(value, layer_name):
        leaf = source_path.rsplit(".", maxsplit=1)[-1]
        # The frozen 177-field contract gives each layer-qualified leaf a
        # unique canonical name.  Preserve an unexpected collision instead of
        # silently overwriting it.
        key = leaf if leaf not in flattened else source_path.removeprefix(f"{layer_name}.")
        flattened[key] = child
    return flattened


def _unwrap_payload(record_or_payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(record_or_payload.get("canonical_received_payload"), dict):
        return record_or_payload["canonical_received_payload"]
    if isinstance(record_or_payload.get("payload"), dict):
        return record_or_payload["payload"]
    return record_or_payload


def _canonical_status_path(path: str) -> str | None:
    parts = path.split(".")
    if len(parts) < 2 or parts[0] not in LAYER_NAMES:
        return None
    return f"{parts[0]}.{parts[-1]}"


def _field_states(record_or_payload: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    supplied = record_or_payload.get("field_status")
    if not isinstance(supplied, dict):
        supplied = payload.get("collection_status")
    source_fields = supplied.get("fields") if isinstance(supplied, dict) else None
    if not isinstance(source_fields, dict):
        return {}
    normalized: dict[str, str] = {}
    for source_path, state in source_fields.items():
        if not isinstance(source_path, str):
            continue
        canonical = _canonical_status_path(source_path)
        if canonical is not None:
            normalized[canonical] = str(state)
    return normalized


def normalize_payload(record_or_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Return the canonical flat three-layer payload and field availability.

    Session IDs, client IPs, manifests, labels, providers and attack metadata
    are intentionally not copied into the normalized runtime input.
    """
    payload = _unwrap_payload(record_or_payload)
    normalized = {
        "collector_app": payload.get("collector_app"),
        "schema_version": payload.get("schema_version"),
    }
    for layer_name in LAYER_NAMES:
        normalized[layer_name] = _flatten_layer(layer_name, payload.get(layer_name))
    return normalized, _field_states(record_or_payload, payload)


def _status_for(fields: list[str], normalized: dict[str, Any], field_states: dict[str, str]) -> str:
    states = [field_states.get(field) for field in fields if field_states.get(field) is not None]
    if any(state in UNAVAILABLE_STATES for state in states):
        return "unavailable"
    values = [get_path(normalized, field) for field in fields]
    return "observed" if all(value is not None and value != "" for value in values) else "unknown"


def _fact(
    fact_id: str,
    value: Any,
    fields: list[str],
    normalized: dict[str, Any],
    field_states: dict[str, str],
) -> dict[str, Any]:
    status = _status_for(fields, normalized, field_states)
    return {
        "fact_id": fact_id,
        "value": value if status == "observed" else None,
        "status": status,
        "source_fields": fields,
    }


def _android_major(value: Any) -> int | None:
    text = str(value or "")
    match = re.search(r"(?:Android\s*)?(\d{1,2})(?:[._]\d+)?", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _ua_android_major(value: Any) -> int | None:
    match = re.search(r"Android\s+(\d{1,2})", str(value or ""), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _ua_class(value: Any) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("python-requests", "python-urllib", "curl/", "okhttp")):
        return "script_client"
    if any(token in text for token in ("headless", "windows nt", "win64", "macintosh", "x11; linux")):
        return "desktop_or_headless"
    if "android" in text and " wv" in text:
        return "android_webview"
    if "android" in text:
        return "android_browser"
    return "unknown"


def _platform_class(value: Any) -> str:
    text = str(value or "").lower()
    if "android" in text:
        return "android"
    # Android WebView may report Linux armv8l *or* Linux x86_64 on an
    # emulator.  navigator.platform alone cannot distinguish that from a
    # desktop Linux browser; the UA classifier must supply any desktop signal.
    if "linux" in text or "armv" in text:
        return "mobile_or_ambiguous"
    if "win" in text or "mac" in text:
        return "desktop"
    return "unknown"


def _build_marker_categories(values: Iterable[Any]) -> list[str]:
    text = " ".join(str(value or "").lower() for value in values)
    markers = []
    for category, tokens in (
        ("test_keys", ("test-keys",)),
        ("dev_keys", ("dev-keys",)),
        ("userdebug", ("userdebug",)),
        ("generic_build", ("generic",)),
        ("emulator_marker", ("sdk_gphone", "emulator", "goldfish", "ranchu")),
    ):
        if any(token in text for token in tokens):
            markers.append(category)
    return markers


def _installer_class(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    if text == "manual":
        return "manual"
    if "packageinstaller" in text or "vending" in text or "play" in text:
        return "package_manager_or_store"
    return "other_installer"


def _integer(value: Any) -> int | None:
    """Return only an unambiguous integer; malformed direct API input stays unknown."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _observation(
    observation_id: str,
    fact_ids: list[str],
    fields: list[str],
    status: str,
    summary: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "fact_ids": fact_ids,
        "fields": fields,
        "status": status,
        "summary": summary,
        "details": details or {},
    }


def _comparison_status(left: dict[str, Any], right: dict[str, Any]) -> str:
    if left["status"] == "unavailable" or right["status"] == "unavailable":
        return "unavailable"
    if left["status"] != "observed" or right["status"] != "observed":
        return "unknown"
    return "matched" if left["value"] == right["value"] else "not_matched"


def _derived_facts(normalized: dict[str, Any], field_states: dict[str, str]) -> dict[str, dict[str, Any]]:
    native = normalized["android_native_data"]
    webview = normalized["webview_data"]
    web = normalized["web_data"]
    facts = {
        "native.android_major": _fact(
            "native.android_major",
            _android_major(native.get("os_version")),
            ["android_native_data.os_version"],
            normalized,
            field_states,
        ),
        "web.ua_android_major": _fact(
            "web.ua_android_major",
            _ua_android_major(web.get("user_agent")),
            ["web_data.user_agent"],
            normalized,
            field_states,
        ),
        "webview.http_android_major": _fact(
            "webview.http_android_major",
            _ua_android_major(webview.get("system_http_agent")),
            ["webview_data.system_http_agent"],
            normalized,
            field_states,
        ),
        "web.ua_class": _fact(
            "web.ua_class",
            _ua_class(web.get("user_agent")),
            ["web_data.user_agent"],
            normalized,
            field_states,
        ),
        "web.platform_class": _fact(
            "web.platform_class",
            _platform_class(web.get("platform")),
            ["web_data.platform"],
            normalized,
            field_states,
        ),
        "web.max_touch_points": _fact(
            "web.max_touch_points",
            _integer(web.get("max_touch_points")),
            ["web_data.max_touch_points"],
            normalized,
            field_states,
        ),
        "webview.jsbridge_state": _fact(
            "webview.jsbridge_state",
            _boolean(webview.get("jsbridge_injected")),
            ["webview_data.jsbridge_injected"],
            normalized,
            field_states,
        ),
        "native.sensor_total_count": _fact(
            "native.sensor_total_count",
            _integer(native.get("sensor_total_count")),
            ["android_native_data.sensor_total_count"],
            normalized,
            field_states,
        ),
        "webview.is_debuggable": _fact(
            "webview.is_debuggable",
            _boolean(webview.get("is_debuggable")),
            ["webview_data.is_debuggable"],
            normalized,
            field_states,
        ),
        "webview.cleartext_permitted": _fact(
            "webview.cleartext_permitted",
            _boolean(webview.get("is_cleartext_traffic_permitted")),
            ["webview_data.is_cleartext_traffic_permitted"],
            normalized,
            field_states,
        ),
        "native.adb_enabled": _fact(
            "native.adb_enabled",
            _boolean(native.get("is_adb_enabled")),
            ["android_native_data.is_adb_enabled"],
            normalized,
            field_states,
        ),
        "native.battery_level_pct": _fact(
            "native.battery_level_pct",
            _number(native.get("battery_level_pct")),
            ["android_native_data.battery_level_pct"],
            normalized,
            field_states,
        ),
        "native.is_charging": _fact(
            "native.is_charging",
            _boolean(native.get("is_charging")),
            ["android_native_data.is_charging"],
            normalized,
            field_states,
        ),
        "native.build_marker_categories": _fact(
            "native.build_marker_categories",
            _build_marker_categories(
                (native.get("build_fingerprint"), native.get("build_tags"), native.get("build_type"))
            ),
            [
                "android_native_data.build_fingerprint",
                "android_native_data.build_tags",
                "android_native_data.build_type",
            ],
            normalized,
            field_states,
        ),
        "webview.installer_class": _fact(
            "webview.installer_class",
            _installer_class(webview.get("installer_package")),
            ["webview_data.installer_package"],
            normalized,
            field_states,
        ),
        "web.timezone_offset": _fact(
            "web.timezone_offset",
            _integer(web.get("timezone_offset")),
            ["web_data.timezone_offset"],
            normalized,
            field_states,
        ),
        "native.model_in_web_ua": _fact(
            "native.model_in_web_ua",
            (
                str(native.get("device_model") or "").strip().lower()
                in str(web.get("user_agent") or "").lower()
            ),
            ["android_native_data.device_model", "web_data.user_agent"],
            normalized,
            field_states,
        ),
        "webview.web_ua_exact_match": _fact(
            "webview.web_ua_exact_match",
            str(webview.get("default_ua_native") or "").strip()
            == str(web.get("user_agent") or "").strip(),
            ["webview_data.default_ua_native", "web_data.user_agent"],
            normalized,
            field_states,
        ),
    }
    # A failed parse remains unknown even when the raw field itself was observed.
    for fact_id in (
        "native.android_major",
        "web.ua_android_major",
        "webview.http_android_major",
        "web.max_touch_points",
        "webview.jsbridge_state",
        "native.sensor_total_count",
        "webview.is_debuggable",
        "webview.cleartext_permitted",
        "native.adb_enabled",
        "native.battery_level_pct",
        "native.is_charging",
        "web.timezone_offset",
    ):
        if facts[fact_id]["status"] == "observed" and facts[fact_id]["value"] is None:
            facts[fact_id]["status"] = "unknown"
    for fact_id in ("web.ua_class", "web.platform_class"):
        if facts[fact_id]["status"] == "observed" and facts[fact_id]["value"] == "unknown":
            facts[fact_id]["status"] = "unknown"
    return facts


def _evidence_groups(facts: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    native_web_status = _comparison_status(facts["native.android_major"], facts["web.ua_android_major"])
    native_webview_status = _comparison_status(
        facts["native.android_major"], facts["webview.http_android_major"]
    )
    model_status = facts["native.model_in_web_ua"]["status"]
    if model_status == "observed":
        model_status = "matched" if facts["native.model_in_web_ua"]["value"] else "not_matched"
    webview_web_status = facts["webview.web_ua_exact_match"]["status"]
    if webview_web_status == "observed":
        webview_web_status = "matched" if facts["webview.web_ua_exact_match"]["value"] else "not_matched"

    mobile_touch_status = "unknown"
    if facts["web.ua_class"]["status"] == "unavailable" or facts["web.max_touch_points"]["status"] == "unavailable":
        mobile_touch_status = "unavailable"
    elif facts["web.ua_class"]["status"] == "observed" and facts["web.max_touch_points"]["status"] == "observed":
        if facts["web.ua_class"]["value"] in {"android_browser", "android_webview"}:
            mobile_touch_status = (
                "not_matched" if facts["web.max_touch_points"]["value"] == 0 else "matched"
            )
        else:
            mobile_touch_status = "not_applicable"

    bridge_sensor_status = "unknown"
    if facts["webview.jsbridge_state"]["status"] == "unavailable" or facts["native.sensor_total_count"]["status"] == "unavailable":
        bridge_sensor_status = "unavailable"
    elif facts["webview.jsbridge_state"]["status"] == "observed" and facts["native.sensor_total_count"]["status"] == "observed":
        bridge_sensor_status = "observed"

    return {
        "cross_layer": [
            _observation(
                "native_web_android_major",
                ["native.android_major", "web.ua_android_major"],
                ["android_native_data.os_version", "web_data.user_agent"],
                native_web_status,
                "Native Android major and Web UA Android major comparison.",
            ),
            _observation(
                "native_webview_android_major",
                ["native.android_major", "webview.http_android_major"],
                ["android_native_data.os_version", "webview_data.system_http_agent"],
                native_webview_status,
                "Native Android major and WebView HTTP agent Android major comparison.",
            ),
            _observation(
                "native_web_model_ua",
                ["native.model_in_web_ua"],
                ["android_native_data.device_model", "web_data.user_agent"],
                model_status,
                "Whether the normalized Native model token occurs in the Web UA; a soft identity observation only.",
            ),
            _observation(
                "webview_web_ua_exact",
                ["webview.web_ua_exact_match"],
                ["webview_data.default_ua_native", "web_data.user_agent"],
                webview_web_status,
                "WebView default UA and Web UA exact comparison; legitimate runtime differences remain possible.",
            ),
            _observation(
                "web_mobile_touch_surface",
                ["web.ua_class", "web.max_touch_points"],
                ["web_data.user_agent", "web_data.max_touch_points"],
                mobile_touch_status,
                "Mobile UA class and touch-surface relationship.",
            ),
        ],
        "runtime_context": [
            _observation(
                "native_sensor_and_webview_bridge",
                ["native.sensor_total_count", "webview.jsbridge_state"],
                ["android_native_data.sensor_total_count", "webview_data.jsbridge_injected"],
                bridge_sensor_status,
                "Sensor and JSBridge observations are runtime context, not a calibrated decision.",
            ),
            _observation(
                "web_ua_surface_class",
                ["web.ua_class", "web.platform_class"],
                ["web_data.user_agent", "web_data.platform"],
                (
                    "unavailable"
                    if "unavailable" in {facts["web.ua_class"]["status"], facts["web.platform_class"]["status"]}
                    else ("observed" if facts["web.ua_class"]["status"] == "observed" else "unknown")
                ),
                "Coarse UA and platform classes only; raw UA is not included.",
            ),
            _observation(
                "webview_host_security_context",
                ["webview.is_debuggable", "webview.cleartext_permitted"],
                ["webview_data.is_debuggable", "webview_data.is_cleartext_traffic_permitted"],
                (
                    "unavailable"
                    if "unavailable" in {facts["webview.is_debuggable"]["status"], facts["webview.cleartext_permitted"]["status"]}
                    else ("observed" if facts["webview.is_debuggable"]["status"] == "observed" and facts["webview.cleartext_permitted"]["status"] == "observed" else "unknown")
                ),
                "Debuggable and cleartext settings are recorded as development context only.",
            ),
            _observation(
                "native_build_marker_categories",
                ["native.build_marker_categories"],
                [
                    "android_native_data.build_fingerprint",
                    "android_native_data.build_tags",
                    "android_native_data.build_type",
                ],
                facts["native.build_marker_categories"]["status"],
                "Only normalized build-marker categories are retained.",
            ),
            _observation(
                "test_rig_context",
                [
                    "native.adb_enabled",
                    "native.battery_level_pct",
                    "native.is_charging",
                    "webview.installer_class",
                    "web.timezone_offset",
                ],
                [
                    "android_native_data.is_adb_enabled",
                    "android_native_data.battery_level_pct",
                    "android_native_data.is_charging",
                    "webview_data.installer_package",
                    "web_data.timezone_offset",
                ],
                (
                    "unavailable"
                    if any(facts[fact_id]["status"] == "unavailable" for fact_id in (
                        "native.adb_enabled",
                        "native.battery_level_pct",
                        "native.is_charging",
                        "webview.installer_class",
                        "web.timezone_offset",
                    ))
                    else "observed"
                    if all(facts[fact_id]["status"] == "observed" for fact_id in (
                        "native.adb_enabled",
                        "native.battery_level_pct",
                        "native.is_charging",
                        "webview.installer_class",
                        "web.timezone_offset",
                    ))
                    else "unknown"
                ),
                "Testing or collection context is preserved separately from any attack conclusion.",
            ),
        ],
    }


def _observed_fields(evidence_groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted(
        {
            field
            for observations in evidence_groups.values()
            for observation in observations
            for field in observation["fields"]
        }
    )


def _derive_sample_id(normalized: dict[str, Any]) -> str:
    return f"runtime-{sha256_value(normalized)[:24]}"


def build_evidence_bundle_v2(record_or_payload: dict[str, Any], sample_id: str | None = None) -> dict[str, Any]:
    """Build a redacted v2 bundle from an inline payload, archive envelope, or snapshot row."""
    normalized, field_states = normalize_payload(record_or_payload)
    facts = _derived_facts(normalized, field_states)
    evidence_groups = _evidence_groups(facts)
    bundle = {
        "evidence_bundle_version": EVIDENCE_BUNDLE_V2,
        "extractor_version": EVIDENCE_EXTRACTOR_VERSION,
        "sample_id": sample_id or str(record_or_payload.get("sample_id") or _derive_sample_id(normalized)),
        "schema_version": "expanded-v2",
        "derived_facts": facts,
        "evidence_groups": evidence_groups,
        "observed_fields": _observed_fields(evidence_groups),
        "coverage": {
            "supported_evidence_groups": ["cross_layer", "runtime_context"],
            "not_assessed": UNASSESSED_EVIDENCE_GROUPS,
        },
        "boundary_note": (
            "Deterministic, redacted observations only. No raw session ID, client IP, raw user-agent, "
            "full build fingerprint, label, provider, attack tool, pair role, risk score, or calibrated risk band is included."
        ),
    }
    bundle["evidence_hash"] = sha256_value(
        {
            "evidence_bundle_version": bundle["evidence_bundle_version"],
            "extractor_version": bundle["extractor_version"],
            "schema_version": bundle["schema_version"],
            "derived_facts": bundle["derived_facts"],
            "evidence_groups": bundle["evidence_groups"],
            "coverage": bundle["coverage"],
        }
    )
    validate_evidence_bundle_v2(bundle)
    return bundle


def validate_evidence_bundle_v2(bundle: dict[str, Any]) -> None:
    """Small dependency-free validation matching evidence_bundle_v2.schema.json."""
    required = {
        "evidence_bundle_version",
        "extractor_version",
        "sample_id",
        "schema_version",
        "evidence_hash",
        "derived_facts",
        "evidence_groups",
        "observed_fields",
        "coverage",
        "boundary_note",
    }
    missing = sorted(required - set(bundle))
    if missing:
        raise ValueError(f"EvidenceBundle v2 missing fields: {missing}")
    if bundle["evidence_bundle_version"] != EVIDENCE_BUNDLE_V2:
        raise ValueError("Unsupported EvidenceBundle version")
    if bundle["schema_version"] != "expanded-v2":
        raise ValueError("EvidenceBundle v2 must use the frozen expanded-v2 schema")
    if not isinstance(bundle["evidence_hash"], str) or len(bundle["evidence_hash"]) != 64:
        raise ValueError("EvidenceBundle v2 requires a SHA-256 evidence_hash")
    for group in ("cross_layer", "runtime_context"):
        if group not in bundle["evidence_groups"]:
            raise ValueError(f"EvidenceBundle v2 missing supported group: {group}")
    if not isinstance(bundle["coverage"].get("not_assessed"), dict):
        raise ValueError("EvidenceBundle v2 must declare not_assessed coverage")
    forbidden = ("session_id", "client_ip", "provider", "attack", "label")
    serialized = canonical_json(bundle)
    if any(f'"{name}"' in serialized for name in forbidden):
        raise ValueError("EvidenceBundle v2 contains a forbidden provenance or label field")
