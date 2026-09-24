"""Versioned, status-aware App/Browser evidence for offline paired244 execution.

Only registered fingerprint values survive projection. Collection identities,
profiles, labels, groups and experiment roles are control-plane data, not facts.
Unlike historical v2, this local-only contract retains selected source values
for reproducible predicates; retrieval and the trace cite fields, not raw values.
"""
from __future__ import annotations

import copy
import csv
from functools import lru_cache
import math
from pathlib import Path

from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2, sha256_value

ROOT = Path(__file__).resolve().parents[2]
VERSION = "evidence-bundle-v3-paired244"
SURFACES = {
    "native84": "app.android_native_data.", "host26": "app.webview_data.",
    "app_web67": "app.web_data.", "browser67": "browser.web_data.",
}
VIEWS = {
    "Full244": tuple(SURFACES), "App177": ("native84", "host26", "app_web67"),
    "Native84": ("native84",), "Host26": ("host26",),
    "AppWeb67": ("app_web67",), "Browser67": ("browser67",),
    "NativeAppWeb151": ("native84", "app_web67"),
    "AppWebBrowser134": ("app_web67", "browser67"),
}
STATES = {"observed", "unsupported_by_os", "permission_denied", "runtime_error", "timeout", "not_applicable"}


@lru_cache(maxsize=1)
def field_contract():
    path = ROOT / "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv"
    with path.open(encoding="utf-8") as stream:
        app = {"app." + r["field"]: r["type"] for r in csv.DictReader(stream)
               if r["layer"] in {"android_native_data", "webview_data", "web_data"}}
    browser = {p.replace("app.", "browser.", 1): t for p, t in app.items() if p.startswith("app.web_data.")}
    if len(app) != 177 or len(browser) != 67:
        raise ValueError("Paired244 field contract changed; review the version before execution")
    return {**app, **browser}


def surface_of(path):
    return next((s for s, prefix in SURFACES.items() if path.startswith(prefix)), None)


def valid_type(value, kind):
    if kind == "number":
        return type(value) in (int, float) and math.isfinite(value)
    return {"string": str, "boolean": bool, "array": list}.get(kind) is type(value)


def legacy_field_map():
    result = {}
    for path in field_contract():
        if path.startswith("app."):
            parts = path.split(".")
            key = parts[1] + "." + parts[-1]
            if key in result:
                raise ValueError("Legacy field alias is ambiguous")
            result[key] = path
    return result


def legacy_payload(projection):
    """Build App-only legacy facts after view masking, with no metadata carryover."""
    payload = {"collector_app": "featureapp", "schema_version": "expanded-v2.2-status",
               "android_native_data": {}, "webview_data": {}, "web_data": {},
               "collection_status": {"fields": {}}}
    for field, value in projection["features"].items():
        if not field.startswith("app."):
            continue
        parts = field.split(".")
        alias = parts[1] + "." + parts[-1]
        payload[parts[1]][parts[-1]] = copy.deepcopy(value)
        payload["collection_status"]["fields"][alias] = projection["field_status"].get(field, "runtime_error")
    return payload


def _pair_admitted(record):
    pair = record.get("pair") or {}
    if pair.get("pair_status") != "completed" or not pair.get("browser_pair_id") or not pair.get("collection_batch_id"):
        return False
    return all(isinstance(record.get(side, {}).get(key), str) and record[side][key]
               for side in ("app", "browser") for key in ("session_id", "receipt_id", "payload_sha256"))


def build_paired_evidence(record, input_view="Full244"):
    if record.get("record_schema_version") != "hybridguard-mtc-observation-v2":
        raise ValueError("Paired runtime requires the P1 v2 observation contract")
    if input_view not in VIEWS:
        raise ValueError("Unsupported paired runtime input view")
    source = record.get("features")
    if not isinstance(source, dict):
        raise ValueError("Fingerprint feature mapping is required")
    contract = field_contract()
    if set(source) - set(contract):
        raise ValueError("Unregistered fingerprint feature")
    # Select before reading values, state, quality or pair metadata for that view.
    selected = sorted(p for p in source if surface_of(p) in VIEWS[input_view])
    projection = {name: {p: copy.deepcopy(record.get(name, {}).get(p)) for p in selected}
                  for name in ("features", "field_status", "field_quality")}
    has_browser = any(surface_of(p) == "browser67" for p in selected)
    pair_admitted = _pair_admitted(record) if has_browser else False
    fields = {}
    for path in selected:
        value, state, quality = (projection[n][path] for n in ("features", "field_status", "field_quality"))
        state = state if isinstance(state, str) and state in STATES else None
        quality = quality if isinstance(quality, str) and quality in {"observed_value", "source_unavailable", "ambiguous_sentinel"} else None
        reason = None
        if surface_of(path) == "browser67" and not pair_admitted:
            reason = "browser_pair_not_admitted"
        elif state != "observed":
            reason = "source_status_unavailable"
        elif quality != "observed_value":
            reason = "source_quality_unavailable"
        elif not valid_type(value, contract[path]):
            reason = "invalid_source_type"
        elif path.endswith((".device_memory", ".hardware_concurrency")) and value <= 0:
            reason = "ambiguous_navigator_sentinel"
        fields[path] = {"field_id": path, "surface": surface_of(path), "source_status": state,
                        "source_quality": quality, "expected_type": contract[path],
                        "available": reason is None, "unavailable_reason": reason}
        if reason:
            # Invalid/nonfinite values are never passed to old fact parsers.
            projection["features"][path] = None
            projection["field_status"][path] = "runtime_error" if state == "observed" else state
            projection["field_quality"][path] = "source_unavailable"
    legacy = build_evidence_bundle_v2(legacy_payload(projection), sample_id="projected-app")
    mapping = legacy_field_map()
    facts = {"app." + name: {"value": fact["value"], "status": fact["status"],
                            "source_fields": [mapping[p] for p in fact["source_fields"]]}
             for name, fact in legacy["derived_facts"].items()
             if all(mapping.get(p) in fields for p in fact["source_fields"])}
    if has_browser:
        browser_payload = {"web_data": {}, "collection_status": {"fields": {}}}
        for path in selected:
            if path.startswith("browser."):
                leaf = path.rsplit(".", 1)[1]
                browser_payload["web_data"][leaf] = projection["features"][path]
                browser_payload["collection_status"]["fields"]["web_data." + leaf] = projection["field_status"][path]
        browser = build_evidence_bundle_v2(browser_payload, sample_id="projected-browser")
        for name, fact in browser["derived_facts"].items():
            if name.startswith("web."):
                refs = [mapping[p].replace("app.", "browser.", 1) for p in fact["source_fields"]]
                if all(p in fields for p in refs):
                    facts["browser." + name] = {"value": fact["value"], "status": fact["status"], "source_fields": refs}
    bundle = {"evidence_bundle_version": VERSION, "extractor_version": "paired244-extractor-v1",
              "input_view": input_view, "selected_surfaces": list(VIEWS[input_view]),
              "present_surfaces": sorted({surface_of(p) for p in selected}),
              "pair_admitted": pair_admitted, "projection": projection, "fields": fields, "derived_facts": facts,
              "boundary": "Local offline fingerprint evidence only; control-plane identities, labels and groups excluded."}
    bundle["evidence_hash"] = sha256_value(bundle)
    bundle["sample_id"] = "evidence-" + bundle["evidence_hash"][:24]
    return bundle
