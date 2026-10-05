"""Independently verify an immutable, closed Browser67/App177 pilot.

Only the aggregate result is public. Raw archives, receipts and CDP command
events remain private inputs. No Node collector code is imported or executed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import quote, urlsplit
import zipfile


STATUSES = {"observed", "unsupported_by_os", "permission_denied", "runtime_error", "timeout", "not_applicable"}
WEB_TARGETS = {
    "language": "web_data.navigator_layer.language",
    "languages": "web_data.navigator_layer.languages",
    "timezone_id": "web_data.execution_layer.timezone_id",
    "timezone_offset": "web_data.execution_layer.timezone_offset",
}
NATIVE_TARGETS = (
    "android_native_data.locale_timezone_layer.native_locale",
    "android_native_data.locale_timezone_layer.native_language",
    "android_native_data.locale_timezone_layer.native_country",
    "android_native_data.locale_timezone_layer.native_timezone_id",
    "android_native_data.locale_timezone_layer.native_timezone_offset_min",
)
APP_SIGNAL_LAYERS = {"android_native_data", "webview_data", "web_data"}
APP_METADATA_FIELDS = {"collector_app", "schema_version", "session_id", "timestamp"}
EXPECTED = {
    "language_fr": {"language": "fr-FR", "languages": ["fr-FR"]},
    "timezone_tokyo": {"timezone_id": "Asia/Tokyo", "timezone_offset": -540},
}
STATIC_NAMES = (
    "browser-probe.html", "browser-probe-bootstrap.js", "browser-probe-adapter.js",
    "probe/canonical_web_probe.js", "probe/manifest.json",
)
CONTROL_LABEL_KEYS = {
    "configuration_id", "configuration", "stage", "attack_stage", "attack_label",
    "label", "ground_truth", "control_method", "control_params",
    "control_configuration", "expected_attack", "experiment_stage",
}
CONTROL_LABEL_VALUES = {
    *EXPECTED, "clean_pre", "attack_active", "clean_post",
    "Runtime.evaluate", "Emulation.setTimezoneOverride",
}
WARMUP_BYTES = (
    '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
    'content="default-src \'none\'; base-uri \'none\'; form-action \'none\'">'
    '<title>Local Chrome startup</title><p>Local browser startup check.</p>'
).encode("utf-8")


class VerificationError(ValueError):
    """A machine-readable verification failure without private data."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise VerificationError(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value: dict[str, Any]) -> str:
    """Match the backend's documented canonicalization independently."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return digest(encoded.encode("utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    require(not raw or raw.endswith(b"\n"), "PARTIAL_JSONL_ROW")
    result = []
    for line in raw.split(b"\n"):
        if not line.strip():
            continue
        value = json.loads(line)
        require(isinstance(value, dict), "JSONL_OBJECT_REQUIRED")
        result.append(value)
    return result


def nested(value: dict[str, Any], dotted: str) -> Any:
    current: Any = value
    for key in dotted.split("."):
        require(isinstance(current, dict) and key in current, "TARGET_FIELD_MISSING")
        current = current[key]
    return current


def observations(payload: dict[str, Any]) -> dict[str, Any]:
    return {name: nested(payload, path) for name, path in WEB_TARGETS.items()}


def verify_no_control_labels(payload: dict[str, Any]) -> None:
    """Reject experiment labels while allowing actual controlled observations."""
    pending: list[Any] = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            require(not CONTROL_LABEL_KEYS.intersection(value), "CONTROL_LABEL_KEY_IN_PAYLOAD")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            require(value not in CONTROL_LABEL_VALUES, "CONTROL_LABEL_VALUE_IN_PAYLOAD")


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "TIMESTAMP_TIMEZONE_REQUIRED")
    return parsed


def unique(rows: list[dict[str, Any]], key: str, value: Any, code: str) -> dict[str, Any]:
    matched = [row for row in rows if row.get(key) == value]
    require(len(matched) == 1, code)
    return matched[0]


@dataclass(frozen=True)
class Inputs:
    root: Path
    provenance: Path
    build: dict[str, Any]
    pilot_name: str = "pilot_r2"

    def locked_path(self, absolute: str) -> Path:
        """Locate copied artifacts without rewriting their recorded history.

        A resumed archive can retain older packaged-asset paths while recording
        newly captured paths under its current root. Only roots explicitly
        recorded in the locked build manifest may be relocated.
        """
        origins = [Path(self.build["source_checkout"]).parent]
        archived = self.build.get("resume_archive_origin", {}).get("directory")
        if archived:
            origins.append(Path(archived))
        for original in origins:
            try:
                relative = Path(absolute).relative_to(original)
            except ValueError:
                continue
            candidate = (self.root / relative).resolve()
            require(candidate.is_relative_to(self.root.resolve()), "LOCKED_PATH_ESCAPE")
            return candidate
        raise VerificationError("LOCKED_PATH_OUTSIDE_RUN")


def source_head(root: Path) -> str:
    gitdir = root / "upstream" / ".git"
    head = (gitdir / "HEAD").read_text(encoding="ascii").strip()
    if not head.startswith("ref: "):
        return head
    reference = head[5:]
    refpath = gitdir / reference
    if refpath.exists():
        return refpath.read_text(encoding="ascii").strip()
    for line in (gitdir / "packed-refs").read_text(encoding="ascii").splitlines():
        if line and not line.startswith(("#", "^")):
            commit, name = line.split(" ", 1)
            if name == reference:
                return commit
    raise VerificationError("SOURCE_HEAD_UNRESOLVED")


def app_signal_catalog(path: Path) -> set[str]:
    """Separate the CSV's four envelope metadata fields from its 177 signals."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    signals = {row["field"] for row in rows if row["layer"] in APP_SIGNAL_LAYERS}
    metadata = {row["field"] for row in rows if row["layer"] not in APP_SIGNAL_LAYERS}
    require(metadata == APP_METADATA_FIELDS and len(signals) + len(metadata) == len(rows), "SOURCE_APP_CATALOG_METADATA_MISMATCH")
    require(all(row["field"].split(".")[0] == row["layer"] for row in rows), "SOURCE_APP_CATALOG_LAYER_MISMATCH")
    return signals


def verify_sources(inputs: Inputs, manifest: dict[str, Any], plan: dict[str, Any]) -> tuple[set[str], set[str], dict[str, Any]]:
    root, build = inputs.root, inputs.build
    require(manifest["build_manifest"] == build, "BUILD_LOCK_MISMATCH")
    require(plan["source_commit"] == manifest["source_commit"] == build["source_commit"] == source_head(root), "SOURCE_COMMIT_MISMATCH")
    require(digest((root / "pilot_plan.json").read_bytes()) == manifest["plan_sha256"], "PLAN_HASH_MISMATCH")
    require(digest((root / "run_paired_browser_pilot.mjs").read_bytes()) == manifest["runner_sha256"], "RUNNER_HASH_MISMATCH")
    require(build["build"]["assembly_status"] == "succeeded" and build["unit_tests"]["status"] == "passed", "BUILD_NOT_SUCCESSFUL")
    apk = inputs.locked_path(build["apk"]["path"])
    apkbytes = apk.read_bytes()
    require(digest(apkbytes) == build["apk"]["sha256"] == manifest["apk"]["sha256"], "APK_HASH_MISMATCH")
    require(len(apkbytes) == build["apk"]["bytes"] == manifest["apk"]["byte_count"], "APK_SIZE_MISMATCH")
    installed = manifest["installed_apk"]
    installed_path = inputs.locked_path(installed["path"])
    require(installed_path == (root / inputs.pilot_name / "installed_collector.apk").resolve(), "INSTALLED_APK_PATH_MISMATCH")
    installed_bytes = installed_path.read_bytes()
    require(installed["matches_local_apk"] is True and digest(installed_bytes) == installed["sha256"] == build["apk"]["sha256"]
            and len(installed_bytes) == installed["byte_count"] == len(apkbytes), "INSTALLED_APK_HASH_MISMATCH")
    require(installed["serial"] == plan["serial"] and installed["device_path"].startswith("/data/app/")
            and installed["device_path"].endswith("/base.apk"), "INSTALLED_APK_DEVICE_IDENTITY_MISMATCH")
    preflight_events = read_jsonl(root / inputs.pilot_name / "private_command_events.jsonl")
    package_paths = [row for row in preflight_events if row["kind"] == "adb_received"
                     and row["args"] == ["shell", "pm", "path", plan["app_package"]]]
    require(len(package_paths) == 1 and package_paths[0]["stdout"].strip() == f"package:{installed['device_path']}", "INSTALLED_APK_PACKAGE_PROOF_MISSING")
    pulls = [row for row in preflight_events if row["kind"] == "adb_received"
             and row["args"] == ["pull", installed["device_path"], installed["path"]]]
    require(len(pulls) == 1, "INSTALLED_APK_PULL_PROOF_MISSING")
    warmup = manifest["inert_warmup_response"]
    require(warmup == {"public_path": "/pilot-warmup.html", "byte_count": len(WARMUP_BYTES),
                       "sha256": digest(WARMUP_BYTES), "no_scripts_or_collection": True}, "WARMUP_RESPONSE_LOCK_MISMATCH")
    public = root / "upstream/browser_probe_site/public"
    locked_static = {inputs.locked_path(item["path"]): item for item in manifest["source_files"]}
    require(set(locked_static) == {(public / name).resolve() for name in STATIC_NAMES}, "STATIC_CATALOG_MISMATCH")
    for path, identity in locked_static.items():
        blob = path.read_bytes()
        require(digest(blob) == identity["sha256"] and len(blob) == identity["byte_count"], "STATIC_BYTES_MISMATCH")
    with zipfile.ZipFile(apk) as package:
        for identity in build["packaged_probe_assets"]:
            blob = package.read(identity["asset"])
            require(digest(blob) == identity["sha256"] and len(blob) == identity["bytes"], "PACKAGED_ASSET_MISMATCH")
            require(blob == inputs.locked_path(identity["source"]).read_bytes(), "PACKAGED_SOURCE_MISMATCH")
    probe = read_json(public / "probe/manifest.json")
    require(digest((public / "probe/canonical_web_probe.js").read_bytes()) == probe["sha256"], "PROBE_BUNDLE_HASH_MISMATCH")
    require(probe["revision"] == build["configuration"]["WEB_PROBE_REVISION"] and probe["signal_count"] == 67, "PROBE_REVISION_MISMATCH")
    core = (root / "upstream/web_probe/canonical_web_probe.js").read_text(encoding="utf-8")
    match = re.search(r"var FIELD_PATHS\s*=\s*(\[.*?\]);", core, re.DOTALL)
    require(match is not None, "SOURCE_WEB_CATALOG_MISSING")
    web = set(json.loads(match.group(1)))
    catalog = root / "upstream/android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv"
    app = app_signal_catalog(catalog)
    require(len(web) == 67 and len(app) == 177 and web <= app, "SOURCE_CATALOG_COUNTS")
    return app, web, probe


def verify_status(payload: dict[str, Any], catalog: set[str]) -> Counter[str]:
    status = payload["collection_status"]
    fields = status["fields"]
    require(set(fields) == catalog and status["fixed_signal_count"] == len(catalog), "STATUS_CATALOG_MISMATCH")
    require(set(fields.values()) <= STATUSES, "STATUS_VALUE_INVALID")
    counts = Counter(fields.values())
    require(set(status["counts"]) == STATUSES, "STATUS_COUNT_KEYS_INVALID")
    require(all(type(number) is int and number == counts[name] for name, number in status["counts"].items()), "STATUS_COUNTS_MISMATCH")
    if "field_statuses" in payload:
        require(payload["field_statuses"] == fields, "STATUS_PROJECTION_MISMATCH")
    for path, state in fields.items():
        if state == "observed":
            nested(payload, path)
    for path in WEB_TARGETS.values():
        require(fields[path] == "observed", "CONTROL_TARGET_NOT_OBSERVED")
    for path in NATIVE_TARGETS:
        if path in catalog:
            require(fields[path] == "observed", "APP_NATIVE_TARGET_NOT_OBSERVED")
    return counts


def verify_plan(plan: dict[str, Any], manifest: dict[str, Any], captures: list[dict[str, Any]]) -> None:
    require(plan["planned_stage_count"] == manifest["planned_stage_count"] == len(captures) == 18, "STAGE_COUNT_MISMATCH")
    require(plan["rounds_per_configuration"] == 3 and plan["stage_order"] == ["clean_pre", "attack_active", "clean_post"], "PLAN_ORDER_MISMATCH")
    require([row["configuration_id"] for row in plan["controls"]] == list(EXPECTED), "PLAN_CONTROLS_MISMATCH")
    for control in plan["controls"]:
        require(control["expected"] == EXPECTED[control["configuration_id"]], "PLAN_EXPECTATION_MISMATCH")
    expected = []
    for configuration in EXPECTED:
        for repeat in range(1, 4):
            for stage in plan["stage_order"]:
                index = len(expected) + 1
                capture = f"c{index:04}"
                expected.append({"capture_id": capture, "configuration_id": configuration, "repeat": repeat, "stage": stage,
                                 "collection_round": index, "runtime_context": f"{plan['device_manifest_id']}:{capture}"})
    require(manifest["stages"] == expected, "MANIFEST_STAGE_MISMATCH")
    for stage, capture in zip(expected, captures, strict=True):
        require(all(capture.get(key) == value for key, value in stage.items()), "CAPTURE_STAGE_MISMATCH")
        require(capture.get("result") == "completed" and capture.get("pair_completed") is True, "STAGE_NOT_COMPLETED")
        require(not capture.get("failure_code") and not capture.get("restoration_failure_code"), "STAGE_FAILURE_PRESENT")


def verify_archive_line(data: Path, identity: dict[str, Any], expected_name: str) -> dict[str, Any]:
    require(identity["file"] == expected_name, "ARCHIVE_FILE_MISMATCH")
    lines = (data / expected_name).read_bytes().split(b"\n")
    number = identity["line"]
    require(type(number) is int and 1 <= number < len(lines), "ARCHIVE_LINE_INVALID")
    line = lines[number - 1]
    require(digest(line) == identity["line_sha256"], "ARCHIVE_LINE_HASH_MISMATCH")
    return json.loads(line)


def verify_capture(inputs: Inputs, capture: dict[str, Any], rows: dict[str, list[dict[str, Any]]], plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    data = inputs.root / "data"
    app = verify_archive_line(data, capture["archives"]["app"], "raw_expanded_payloads.jsonl")
    browser = verify_archive_line(data, capture["archives"]["browser"], "raw_browser_payloads.jsonl")
    pair = verify_archive_line(data, capture["archives"]["provenance"], "browser_pair_provenance.jsonl")
    binding = capture["binding"]
    require(all(pair.get(key) == value for key, value in binding.items()), "PAIR_BINDING_MISMATCH")
    require(pair["pair_status"] == "completed", "PAIR_NOT_COMPLETED")
    require(pair["selected_browser_package"] == pair["resolved_browser_package"] == plan["browser_package"], "BROWSER_PACKAGE_MISMATCH")
    app_payload, browser_payload = app["canonical_received_payload"], browser["canonical_received_payload"]
    require(canonical_digest(app_payload) == app["payload_sha256"] == pair["app_payload_sha256"], "APP_CANONICAL_HASH_MISMATCH")
    require(canonical_digest(browser_payload) == browser["browser_payload_sha256"] == pair["browser_payload_sha256"], "BROWSER_CANONICAL_HASH_MISMATCH")
    for key in ("session_id", "receipt_id", "payload_sha256"):
        require(app[key] == binding[f"app_{key}"] and app[key] == pair[f"app_{key}"], "APP_BINDING_MISMATCH")
    for key in ("pair_id", "app_session_id", "app_receipt_id", "browser_session_id", "browser_receipt_id", "browser_payload_sha256", "collection_batch_id"):
        require(browser[key] == pair[key], "BROWSER_BINDING_MISMATCH")
    require(app_payload["session_id"] == app["session_id"] and browser_payload["pair_id"] == pair["pair_id"] and browser_payload["browser_session_id"] == pair["browser_session_id"], "RAW_SESSION_BINDING_MISMATCH")
    require(app["collection_batch_id"] == pair["collection_batch_id"], "APP_BATCH_MISMATCH")
    context = app_payload["collection_manifest"]
    require(context == capture["app_manifest"], "APP_MANIFEST_PROJECTION_MISMATCH")
    require(context["runtime_context"] == capture["runtime_context"] and context["collection_round"] == capture["collection_round"] and context["device_manifest_id"] == plan["device_manifest_id"], "APP_CONTEXT_BINDING_MISMATCH")
    context_apps = [item for item in rows["apps"] if item["canonical_received_payload"]["collection_manifest"].get("runtime_context") == capture["runtime_context"]]
    require(len(context_apps) == 1 and context_apps[0] == app, "APP_CONTEXT_NOT_UNIQUE")
    require(unique(rows["pairs"], "pair_id", pair["pair_id"], "PAIR_NOT_UNIQUE") == pair, "PAIR_ARCHIVE_MISMATCH")
    require(unique(rows["browsers"], "pair_id", pair["pair_id"], "BROWSER_NOT_UNIQUE") == browser, "BROWSER_ARCHIVE_MISMATCH")
    pair_events = [row for row in rows["pair_events"] if row.get("pair_id") == pair["pair_id"]]
    issued = [row for row in pair_events if row.get("event") in {"ticket_issued", "provisional_ticket_issued"}]
    require(len(issued) == 1, "PAIR_TICKET_NOT_UNIQUE")
    ticket = issued[0]
    require(all(ticket.get(key) == pair[key] for key in (
        "app_session_id", "collection_batch_id", "ticket_request_id", "ticket_binding_mode",
        "selected_browser_package", "resolved_browser_package",
    )), "PAIR_TICKET_BINDING_MISMATCH")
    accepted = unique(pair_events, "event", "browser_payload_accepted", "BROWSER_ACCEPTANCE_EVENT_NOT_UNIQUE")
    require(all(accepted.get(key) == pair[key] for key in (
        "app_session_id", "app_receipt_id", "collection_batch_id", "browser_session_id",
        "browser_receipt_id", "browser_payload_sha256",
    )) and accepted["pair_status"] == "completed", "BROWSER_ACCEPTANCE_BINDING_MISMATCH")
    require(instant(ticket["event_at"]) <= instant(accepted["event_at"]), "PAIR_EVENT_ORDER_INVALID")
    receipt = unique(rows["receipts"], "receipt_id", app["receipt_id"], "APP_RECEIPT_NOT_UNIQUE")
    require(all(receipt[key] == app[key] for key in ("session_id", "payload_sha256", "collection_batch_id")), "APP_RECEIPT_MISMATCH")
    require(receipt["validation_status"] in {"accepted", "accepted_with_warnings"} and receipt["stored_new_jsonl_row"] is True and receipt["duplicate_payload"] is False, "APP_RECEIPT_NOT_ACCEPTED")
    require(capture["observed"] == observations(browser_payload), "OBSERVATION_PROJECTION_MISMATCH")
    return app, browser, receipt


def successful_command(events: list[dict[str, Any]], method: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    sent = [event for event in events if event["kind"] == "cdp_sent" and event["command"]["method"] == method
            and (params is None or event["command"].get("params") == params)]
    require(len(sent) == 1, "CDP_COMMAND_NOT_UNIQUE")
    sent_event = sent[0]
    channel = sent_event.get("cdp_channel")
    require(isinstance(channel, str), "CDP_CHANNEL_MISSING")
    endpoint = urlsplit(channel)
    expected_path = "/devtools/browser" if method == "Target.closeTarget" else "/devtools/page/"
    require(endpoint.scheme == "ws" and endpoint.hostname in {"127.0.0.1", "localhost"}
            and endpoint.port == 9340 and not endpoint.username and not endpoint.password
            and (endpoint.path == expected_path if method == "Target.closeTarget" else endpoint.path.startswith(expected_path)),
            "CDP_COMMAND_CHANNEL_INVALID")
    reply = [event for event in events if event["kind"] == "cdp_received"
             and event.get("cdp_channel") == channel and event["message"].get("id") == sent_event["command"]["id"]]
    require(len(reply) == 1 and "result" in reply[0]["message"] and "error" not in reply[0]["message"], "CDP_COMMAND_NOT_SUCCESSFUL")
    require("exceptionDetails" not in reply[0]["message"]["result"], "CDP_REALM_EXCEPTION")
    require(events.index(sent_event) < events.index(reply[0]), "CDP_REPLY_ORDER_INVALID")
    return sent_event, reply[0]


def public_realm(value: dict[str, Any]) -> dict[str, Any]:
    parsed = urlsplit(value.get("href", ""))
    return {"page_origin": f"{parsed.scheme}://{parsed.netloc}", "page_path": parsed.path,
             **{key: value.get(key) for key in ("readyState", "coreRevision", "languageHasOwn", "languagesHasOwn")}}


def verify_startup(capture: dict[str, Any], events: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    """Separate the inert warmup connection from the probe's CDP connection."""
    stage_indices = [index for index, event in enumerate(events)
                     if event["kind"] == "stage_started" and event.get("capture_id") == capture["capture_id"]]
    require(len(stage_indices) == 1, "COMMAND_STAGE_NOT_UNIQUE")
    stage_index = stage_indices[0]
    stop_args = ["-s", plan["serial"], "shell", "am", "force-stop", plan["app_package"]]
    stop_indices = [index for index in range(stage_index) if events[index]["kind"] == "adb_sent"
                    and events[index]["args"] == stop_args]
    require(bool(stop_indices), "FRESH_APP_STOP_MISSING")
    prefix = events[stop_indices[-1]:stage_index]
    require(instant(prefix[0]["at"]) >= instant(capture["started_at"]), "STARTUP_PRECEDES_CAPTURE")
    for package in (plan["app_package"], plan["browser_package"]):
        args = ["shell", "am", "force-stop", package]
        sent = [event for event in prefix if event["kind"] == "adb_sent" and event["args"] == ["-s", plan["serial"], *args]]
        replies = [event for event in prefix if event["kind"] == "adb_received" and event["args"] == args]
        require(len(sent) == len(replies) == 1 and prefix.index(sent[0]) < prefix.index(replies[0]), "FRESH_PROCESS_STOP_PROOF_MISSING")
    ready = unique(prefix, "kind", "fresh_chrome_ready", "FRESH_CHROME_READY_NOT_UNIQUE")
    warm = unique(prefix, "kind", "warmup_target_closed", "WARMUP_CLOSE_NOT_UNIQUE")
    query = "/pilot-warmup.html?context=" + quote(capture["runtime_context"], safe="-_.!~*'()")
    url = plan["static_origin"] + query
    require(ready["prewarm_url"] == warm["url"] == url, "WARMUP_URL_MISMATCH")
    served = unique(prefix, "kind", "warmup_file_sent", "WARMUP_DELIVERY_NOT_UNIQUE")
    require(served["url"] == query and served["sha256"] == digest(WARMUP_BYTES)
            and served["byte_count"] == len(WARMUP_BYTES), "WARMUP_DELIVERY_BYTES_MISMATCH")
    discovery = ready["discovery"]
    require(discovery == capture["fresh_chrome_startup"] and discovery["Android-Package"] == plan["browser_package"]
            and discovery["Browser"].startswith(("Chrome/", "HeadlessChrome/")), "CHROME_PACKAGE_IDENTITY_MISMATCH")
    websocket = urlsplit(discovery["webSocketDebuggerUrl"])
    require(websocket.scheme == "ws" and websocket.hostname in {"127.0.0.1", "localhost"}
            and websocket.port == 9340 and websocket.path == "/devtools/browser"
            and not websocket.username and not websocket.password, "CHROME_DISCOVERY_ORIGIN_MISMATCH")
    require(capture["warmup_target"] == {key: value for key, value in warm.items() if key not in {"kind", "at"}}, "WARMUP_PROJECTION_MISMATCH")
    require(warm["command_channel"] == "browser", "WARMUP_CLOSE_CHANNEL_INVALID")
    require(re.fullmatch(r"\d+(?: \d+)*", warm["chrome_pid"]) is not None, "WARMUP_CHROME_PID_INVALID")
    close_sent, closed = successful_command(prefix, "Target.closeTarget", {"targetId": warm["target_id"]})
    require(close_sent["cdp_channel"] == discovery["webSocketDebuggerUrl"], "WARMUP_CLOSE_SOCKET_MISMATCH")
    require(closed["message"]["result"] == warm["close_result"] and warm["close_result"].get("success") is True,
            "WARMUP_TARGET_NOT_CLOSED")
    require(prefix.index(ready) < prefix.index(closed) < prefix.index(warm), "WARMUP_EVENT_ORDER_INVALID")
    require(prefix.index(served) < prefix.index(closed), "WARMUP_DELIVERY_ORDER_INVALID")
    require(warm["remaining_managed_probe_count"] == 0, "MANAGED_PROBE_REMAINING")
    cleanups = [event for event in prefix if event["kind"] == "stale_managed_target_closed"]
    require(warm["stale_cleanup"] == [{key: value for key, value in event.items() if key not in {"kind", "at"}}
                                      for event in cleanups], "STALE_CLEANUP_PROJECTION_MISMATCH")
    for cleanup in cleanups:
        managed = urlsplit(cleanup["url"])
        require(managed.scheme == "http" and managed.hostname in {"127.0.0.1", "localhost"}
                and managed.port == 8001 and managed.path in {"/browser-probe.html", "/pilot-warmup.html"}
                and not managed.username and not managed.password and cleanup["target_id"] != warm["target_id"],
                "STALE_CLEANUP_TARGET_OUTSIDE_SCOPE")
        cleanup_sent, cleanup_reply = successful_command(prefix, "Target.closeTarget", {"targetId": cleanup["target_id"]})
        require(cleanup_sent["cdp_channel"] == discovery["webSocketDebuggerUrl"] and cleanup_reply["message"]["result"] == cleanup["result"]
                and cleanup["result"].get("success") is True, "STALE_CLEANUP_CLOSE_FAILED")
        require(prefix.index(cleanup_reply) < prefix.index(cleanup) < prefix.index(closed), "STALE_CLEANUP_ORDER_INVALID")
    require(not any(event["kind"] == "chrome_startup_timeout" for event in prefix), "CHROME_STARTUP_FAILURE_PRESENT")


def verify_gate(capture: dict[str, Any], browser: dict[str, Any], events: list[dict[str, Any]], control: dict[str, Any], static: dict[str, bytes], pair_events: list[dict[str, Any]]) -> None:
    starts = [index for index, row in enumerate(events) if row["kind"] == "stage_started" and row.get("capture_id") == capture["capture_id"]]
    require(len(starts) == 1, "COMMAND_STAGE_NOT_UNIQUE")
    end = next((index for index in range(starts[0] + 1, len(events)) if events[index]["kind"] == "stage_started"), len(events))
    # The next stage's warmup uses new CDP connections before its stage_started.
    # Exclude those replies even though their browser socket URL and IDs repeat.
    end = next((index for index in range(starts[0] + 1, end)
                if instant(events[index]["at"]) > instant(capture["finished_at"])), end)
    block = events[starts[0]:end]
    released = unique(block, "kind", "gate_released", "GATE_RELEASE_NOT_UNIQUE")
    held = unique(block, "kind", "gate_held", "GATE_HOLD_NOT_UNIQUE")
    target = unique(block, "kind", "target_selected", "TARGET_SELECTION_NOT_UNIQUE")
    require(target["ticket"]["pair_id"] == capture["binding"]["pair_id"], "GATE_TICKET_BINDING_MISMATCH")
    baseline_line = capture["browser_pair_event_baseline_line"]
    require(type(baseline_line) is int and 0 <= baseline_line < len(pair_events), "TICKET_EVENT_BASELINE_INVALID")
    new_tickets = [row for row in pair_events[baseline_line:] if row.get("event") in {"ticket_issued", "provisional_ticket_issued"}]
    matching_tickets = [row for row in new_tickets if row == target["ticket"]]
    require(len(matching_tickets) == 1, "SELECTED_TICKET_EVENT_MISSING")
    require(instant(target["ticket"]["event_at"]) >= instant(block[0]["at"]), "SELECTED_TICKET_PRECEDES_STAGE")
    require(held["capture_id"] == released["capture_id"] == target["capture_id"] == capture["capture_id"], "GATE_CAPTURE_BINDING_MISMATCH")
    adapter = static["browser-probe-adapter.js"]
    require(held["path"] == "/browser-probe-adapter.js", "GATE_RESOURCE_MISMATCH")
    require(held["upstream_adapter_sha256"] == released["upstream_adapter_sha256"] == digest(adapter) and released["response_byte_count"] == len(adapter), "GATE_ADAPTER_BYTES_MISMATCH")
    require(not any(row["kind"] in {"gate_rejected", "static_error"} for row in block), "GATE_ERROR_PRESENT")
    before = block[:block.index(released)]
    for event in (row for row in block if row["kind"] == "static_file_sent"):
        require(event["capture_id"] == capture["capture_id"] and event["public_path"] in static, "STATIC_EVENT_SCOPE_MISMATCH")
        blob = static[event["public_path"]]
        require(event["sha256"] == digest(blob) and event["byte_count"] == len(blob), "STATIC_EVENT_BYTES_MISMATCH")
    for name in ("browser-probe.html", "browser-probe-bootstrap.js", "probe/canonical_web_probe.js"):
        require(any(row["kind"] == "static_file_sent" and row["public_path"] == name for row in before), "REQUIRED_STATIC_DELIVERY_MISSING")
    realm = capture["committed_realm"]
    require(realm["readyState"] == "interactive" and realm["coreRevision"] == "expanded-web-67-v2", "COMMITTED_REALM_INVALID")
    realm_replies = [row for row in before if row["kind"] == "cdp_received"
                     and isinstance(row["message"].get("result", {}).get("result", {}).get("value"), dict)
                     and public_realm(row["message"]["result"]["result"]["value"]) == realm]
    require(len(realm_replies) >= 1, "COMMITTED_REALM_PROOF_MISSING")
    page_channel = target["target"]["webSocketDebuggerUrl"]
    require(realm_replies[-1].get("cdp_channel") == page_channel, "COMMITTED_REALM_SOCKET_MISMATCH")
    process = [event for event in before if event["kind"] == "adb_received"
               and event["args"] == ["shell", "pidof", capture["fresh_chrome_startup"]["Android-Package"]]]
    require(len(process) == 1 and process[0]["stdout"].strip() == capture["warmup_target"]["chrome_pid"], "PROBE_CHROME_PROCESS_MISMATCH")
    version_sent, version_reply = successful_command(before, "Browser.getVersion", {})
    require(version_sent["cdp_channel"] == page_channel and version_reply["message"]["result"] == capture["browser_version"]
            and capture["browser_version"]["product"] == capture["fresh_chrome_startup"]["Browser"], "PROBE_BROWSER_VERSION_MISMATCH")
    require(realm_replies[-1]["message"]["result"]["result"]["value"]["href"] == target["target"]["url"], "COMMITTED_REALM_TARGET_MISMATCH")
    require(realm["page_origin"] == "http://127.0.0.1:8001" and realm["page_path"] == "/browser-probe.html", "COMMITTED_REALM_ORIGIN_MISMATCH")
    if capture["stage"] == "attack_active":
        install_sent, installed = successful_command(before, control["method"], control["params"])
        expected_installation = {"method": control["method"], "params": control["params"], "result": installed["message"]["result"]}
        if control["method"] == "Runtime.evaluate":
            require(realm["languageHasOwn"] is False and realm["languagesHasOwn"] is False, "ORIGINAL_NAVIGATOR_OWN_PROPERTY_PRESENT")
            expected_installation["original_own_property_proof"] = {"language": False, "languages": False}
        require(capture["control_installation"] == expected_installation, "CONTROL_INSTALLATION_MISMATCH")
    else:
        install_sent, installed = successful_command(before, "Emulation.setTimezoneOverride", {"timezoneId": ""})
        require(capture["control_installation"] == {"method": "none", "fresh_chrome_process": True, "timezone_reset_result": installed["message"]["result"]}, "CLEAN_CONTROL_INVALID")
    upload_time = instant(browser["server_received_at"])
    require(install_sent["cdp_channel"] == page_channel, "CONTROL_INSTALLATION_SOCKET_MISMATCH")
    require(block.index(held) < block.index(target) < block.index(installed) < block.index(released), "GATE_EVENT_ORDER_INVALID")
    require(instant(held["at"]) <= instant(target["at"]) <= instant(installed["at"]) <= instant(released["at"]) < upload_time <= instant(capture["finished_at"]), "GATE_CONTROL_UPLOAD_ORDER_INVALID")
    after = block[block.index(released) + 1:]
    reset_sent, reset = successful_command(after, "Emulation.setTimezoneOverride", {"timezoneId": ""})
    require(reset_sent["cdp_channel"] == page_channel, "RESTORATION_SOCKET_MISMATCH")
    require(instant(reset["at"]) >= upload_time, "RESTORATION_BEFORE_UPLOAD")
    close_sent, closed = successful_command(after, "Target.closeTarget", {"targetId": target["target"]["id"]})
    require(close_sent["cdp_channel"] == capture["fresh_chrome_startup"]["webSocketDebuggerUrl"], "TARGET_CLOSE_SOCKET_MISMATCH")
    require(closed["message"]["result"].get("success") is True, "BROWSER_TARGET_NOT_CLOSED")
    require(after.index(reset) < after.index(closed) and instant(closed["at"]) <= instant(capture["finished_at"]), "RESTORATION_EVENT_ORDER_INVALID")
    restoration = [{"method": "Emulation.setTimezoneOverride", "params": {"timezoneId": ""}, "result": reset["message"]["result"]},
                   {"method": "Target.closeTarget", "params": {"targetId": target["target"]["id"]}, "result": closed["message"]["result"]}]
    if capture["stage"] == "attack_active" and control["method"] == "Runtime.evaluate":
        delete_sent, deleted = successful_command(after, "Runtime.evaluate", control["restoration"])
        proof_params = {"returnByValue": True, "expression": "({languageHasOwn:Object.prototype.hasOwnProperty.call(navigator,'language'),languagesHasOwn:Object.prototype.hasOwnProperty.call(navigator,'languages')})"}
        proof_sent, proof = successful_command(after, "Runtime.evaluate", proof_params)
        require(delete_sent["cdp_channel"] == proof_sent["cdp_channel"] == page_channel, "LANGUAGE_RESTORATION_SOCKET_MISMATCH")
        proof_value = proof["message"]["result"]["result"]["value"]
        require(proof_value == {"languageHasOwn": False, "languagesHasOwn": False}, "OWN_PROPERTY_RESTORATION_FAILED")
        require(upload_time <= instant(deleted["at"]) <= instant(proof["at"]) <= instant(reset["at"])
                and after.index(deleted) < after.index(proof) < after.index(reset), "LANGUAGE_RESTORATION_ORDER_INVALID")
        restoration[:0] = [{"method": "Runtime.evaluate", "params": control["restoration"], "result": deleted["message"]["result"]},
                           {"method": "Runtime.evaluate", "own_property_restoration_proof": proof_value}]
    require(capture["restoration"] == restoration, "RESTORATION_PROJECTION_MISMATCH")


def verify_triplets(captures: list[dict[str, Any]], matched: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]) -> int:
    complete = 0
    for configuration, expected in EXPECTED.items():
        for repeat in range(1, 4):
            group = [row for row in captures if row["configuration_id"] == configuration and row["repeat"] == repeat]
            require(len(group) == 3 and [row["stage"] for row in group] == ["clean_pre", "attack_active", "clean_post"], "TRIPLET_INCOMPLETE")
            app_raw = [matched[row["capture_id"]][0]["canonical_received_payload"] for row in group]
            browser_raw = [matched[row["capture_id"]][1]["canonical_received_payload"] for row in group]
            before, active, after = [observations(payload) for payload in browser_raw]
            require(any(before[key] != value for key, value in expected.items()), "BASELINE_EQUALS_CONTROL")
            require(all(active[key] == value for key, value in expected.items()), "CONTROL_NOT_OBSERVED")
            require(before == after, "RESTORATION_OBSERVATION_MISMATCH")
            require(all(active[key] == before[key] for key in WEB_TARGETS.keys() - expected.keys()), "BROWSER_UNTARGETED_SCOPE_CHANGED")
            require(observations(app_raw[0]) == observations(app_raw[1]) == observations(app_raw[2]), "APP_WEB_SCOPE_CHANGED")
            for path in NATIVE_TARGETS:
                require(nested(app_raw[0], path) == nested(app_raw[1], path) == nested(app_raw[2], path), "APP_NATIVE_SCOPE_CHANGED")
            complete += 1
    return complete


def verify_lifecycle(inputs: Inputs, matches: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]) -> None:
    data = inputs.root / "data"
    batches = read_jsonl(data / "collection_batches.jsonl")
    require(len(batches) == 2 and [row["event"] for row in batches] == ["started", "closed"], "BATCH_LIFECYCLE_NOT_SINGLE_CLOSED")
    started, closed = batches
    require(started["collection_batch_id"] == closed["collection_batch_id"] and closed["lifecycle_status"] == "closed_cleanly" and closed["ended_at_source"] == "graceful_shutdown_hook", "BATCH_NOT_CLOSED_CLEANLY")
    require(not (data / "active_collection_batch.json").exists(), "ACTIVE_BATCH_MARKER_PRESENT")
    summary = read_json(inputs.root / "backend_lifecycle_summary.json")
    require(summary["closed_cleanly"] is True and summary["active_marker_removed"] is True and summary["started_event_count"] == summary["closed_event_count"] == 1, "BACKEND_SUMMARY_MISMATCH")
    for app, browser, _ in matches.values():
        require(app["collection_batch_id"] == browser["collection_batch_id"] == closed["collection_batch_id"], "CAPTURE_BATCH_MISMATCH")
        require(instant(started["started_at"]) <= instant(app["server_received_at"]) <= instant(browser["server_received_at"]) <= instant(closed["ended_at"]), "BATCH_CAPTURE_TIME_INVALID")
    provenance = read_jsonl(inputs.provenance)
    require(len(provenance) == len(read_jsonl(data / "raw_expanded_payloads.jsonl")), "EXPORT_ARCHIVE_COUNT_MISMATCH")
    for app, _, _ in matches.values():
        row = unique(provenance, "session_id", app["session_id"], "EXPORT_SESSION_NOT_UNIQUE")
        require(row["receipt_id"] == app["receipt_id"] and row["payload_sha256"] == app["payload_sha256"] and row["collection_batch_id"] == app["collection_batch_id"], "EXPORT_HASH_BINDING_MISMATCH")
        require(row["collection_batch_lifecycle_status"] == "closed_cleanly" and row["payload_sha256_verification"] == "verified_canonical_raw_archive" and row["raw_payload_available"] is True, "EXPORT_CANONICAL_PROOF_MISSING")
        require(row["declared_collection_round"] == app["canonical_received_payload"]["collection_manifest"]["collection_round"], "EXPORT_DECLARED_ROUND_MISMATCH")


def verify_locked(root: Path, provenance: Path, pilot_name: str = "pilot_r2") -> dict[str, Any]:
    """Return aggregate evidence only, or raise on any incomplete claim."""
    inputs = Inputs(root.resolve(), provenance, read_json(root / "collector_build_manifest.json"), pilot_name)
    pilot = (root / pilot_name).resolve()
    require(pilot.is_relative_to(root.resolve()), "PILOT_PATH_OUTSIDE_RUN")
    manifest, plan = read_json(pilot / "run_manifest.json"), read_json(root / "pilot_plan.json")
    captures = read_jsonl(pilot / "captures.jsonl")
    verify_plan(plan, manifest, captures)
    app_catalog, web_catalog, probe = verify_sources(inputs, manifest, plan)
    names = {"apps": "raw_expanded_payloads.jsonl", "browsers": "raw_browser_payloads.jsonl", "pairs": "browser_pair_provenance.jsonl", "receipts": "collection_receipts.jsonl", "pair_events": "browser_pair_events.jsonl"}
    rows = {key: read_jsonl(root / "data" / name) for key, name in names.items()}
    require(all(len(rows[key]) >= 18 for key in ("apps", "browsers", "pairs")), "ARCHIVE_STAGE_COUNT_MISMATCH")
    events = read_jsonl(pilot / "private_command_events.jsonl")
    static = {name: (root / "upstream/browser_probe_site/public" / name).read_bytes() for name in STATIC_NAMES}
    controls = {row["configuration_id"]: row for row in plan["controls"]}
    totals: dict[str, Counter[str]] = {"app": Counter(), "browser": Counter()}
    matches = {}
    accepted = 0
    for capture in captures:
        app, browser, receipt = verify_capture(inputs, capture, rows, plan)
        matches[capture["capture_id"]] = app, browser, receipt
        accepted += receipt["validation_status"] == "accepted"
        payload = app["canonical_received_payload"]
        verify_no_control_labels(payload)
        verify_no_control_labels(browser["canonical_received_payload"])
        totals["app"].update(verify_status(payload, app_catalog))
        totals["browser"].update(verify_status(browser["canonical_received_payload"], web_catalog))
        context = payload["collection_manifest"]
        require(context["collector_version_code"] == inputs.build["version_code"] and context["collector_version_name"] == inputs.build["version_name"] and context["collector_package"] == inputs.build["application_id"], "APP_BUILD_IDENTITY_MISMATCH")
        raw_browser = browser["canonical_received_payload"]
        require(raw_browser["web_probe_revision"] == probe["revision"] and raw_browser["probe_metadata"]["core_revision"] == probe["revision"] and raw_browser["probe_metadata"]["core_bundle_sha256"] == probe["sha256"], "BROWSER_PROBE_IDENTITY_MISMATCH")
        verify_startup(capture, events, plan)
        verify_gate(capture, browser, events, controls[capture["configuration_id"]], static, rows["pair_events"])
    require(accepted >= 1, "NO_ACCEPTED_APP_RECEIPT")
    require(len({match[0]["session_id"] for match in matches.values()}) == 18 and len({match[1]["browser_session_id"] for match in matches.values()}) == 18, "SESSION_REUSE")
    triplets = verify_triplets(captures, matches)
    verify_lifecycle(inputs, matches)
    selected_apps = {match[0]["session_id"] for match in matches.values()}
    selected_browsers = {match[1]["browser_session_id"] for match in matches.values()}
    selected_pairs = {capture["binding"]["pair_id"] for capture in captures}
    require(len(selected_pairs) == 18, "SELECTED_PAIR_REUSE")
    all_pair_ids = [pair["pair_id"] for pair in rows["pairs"]]
    all_browser_pairs = [browser["pair_id"] for browser in rows["browsers"]]
    require(len(set(all_pair_ids)) == len(all_pair_ids) and len(set(all_browser_pairs)) == len(all_browser_pairs)
            and set(all_pair_ids) == set(all_browser_pairs), "ALL_PAIR_INVENTORY_NOT_ONE_TO_ONE")
    unselected_pairs = [pair for pair in rows["pairs"] if pair["pair_id"] not in selected_pairs]
    require(all(pair["pair_status"] == "completed" and pair["app_session_id"] not in selected_apps
                and pair["browser_session_id"] not in selected_browsers for pair in unselected_pairs), "ENGINEERING_PAIR_REUSES_SELECTED_SESSION")
    paired_apps = {pair["app_session_id"] for pair in rows["pairs"]}
    require(paired_apps <= {app["session_id"] for app in rows["apps"]}, "PAIR_APP_ARCHIVE_MISSING")
    unpaired = [row for row in rows["apps"] if row["session_id"] not in paired_apps]
    return {"schema_version": "browser67-independent-verification-v1", "verification": "passed", "source_commit": plan["source_commit"],
            "planned_stages": 18, "verified_stages": 18, "complete_triplets": triplets, "configurations": 2, "devices": 1,
            "app_canonical_hashes_verified": 18, "browser_canonical_hashes_verified": 18, "accepted_app_receipts": accepted,
            "inventory": {"app_raw_archives": len(rows["apps"]), "browser_raw_archives": len(rows["browsers"]), "completed_pairs": len(rows["pairs"]),
                          "selected_pairs": len(selected_pairs), "unselected_completed_pairs": len(unselected_pairs), "app_only_archives": len(unpaired)},
            "app_signal_catalog_size": 177, "browser_signal_catalog_size": 67,
            "aggregate_field_status_counts": {name: dict(sorted(counts.items())) for name, counts in totals.items()},
            "browser_only_control_scope_verified": True, "clean_post_matches_clean_pre": True,
            "gate_control_upload_order_verified": True, "build_static_and_probe_locks_verified": True,
            "experimental_labels_absent_from_payloads": True, "backend_ticket_events_verified": 18,
            "installed_apk_bytes_verified": True, "fresh_chrome_startup_verified": True,
            "backend_closed_cleanly": True, "exported_app_provenance_verified": 18,
            "limitations": ["One owned emulator and two browser controls; no population stability estimate.",
                            "Target locale/timezone observations are conserved in App Native/App Web; whole payloads vary naturally.",
                            "CDP and backend ledgers share a local host clock; this is an archived event-order check, not a network timing experiment.",
                             "No detector, model quality, ablation result, or old App177 denominator is established."]}


def input_hashes(root: Path, provenance: Path, pilot_name: str) -> dict[str, str]:
    """Hash all file inputs, using only paths confined to the selected run root."""
    root = root.resolve()
    pilot = (root / pilot_name).resolve()
    require(pilot.is_relative_to(root), "PILOT_PATH_OUTSIDE_RUN")
    require(provenance.resolve().is_relative_to(root), "PROVENANCE_PATH_OUTSIDE_RUN")
    build = read_json(root / "collector_build_manifest.json")
    inputs = Inputs(root, provenance, build, pilot_name)
    manifest = read_json(pilot / "run_manifest.json")
    paths = {
        root / "collector_build_manifest.json", root / "pilot_plan.json",
        root / "run_paired_browser_pilot.mjs", root / "backend_lifecycle_summary.json",
        pilot / "run_manifest.json", pilot / "captures.jsonl", pilot / "private_command_events.jsonl",
        pilot / "installed_collector.apk", provenance.resolve(),
    }
    paths.update(root / "data" / name for name in (
        "raw_expanded_payloads.jsonl", "raw_browser_payloads.jsonl", "browser_pair_provenance.jsonl",
        "collection_receipts.jsonl", "collection_batches.jsonl", "browser_pair_events.jsonl",
    ))
    paths.update(inputs.locked_path(item["path"]) for item in manifest["source_files"])
    paths.update(inputs.locked_path(item["source"]) for item in build["packaged_probe_assets"])
    paths.add(inputs.locked_path(build["apk"]["path"]))
    gitdir = root / "upstream/.git"
    paths.add(gitdir / "HEAD")
    head = (gitdir / "HEAD").read_text(encoding="ascii").strip()
    if head.startswith("ref: "):
        paths.add(gitdir / head[5:] if (gitdir / head[5:]).exists() else gitdir / "packed-refs")
    result = {}
    for path in paths:
        resolved = path.resolve()
        require(resolved.is_relative_to(root), "INPUT_PATH_OUTSIDE_RUN")
        result[resolved.relative_to(root).as_posix()] = digest(resolved.read_bytes())
    return dict(sorted(result.items()))


def verify(root: Path, provenance: Path, pilot_name: str = "pilot_r2") -> dict[str, Any]:
    """Lock the report to immutable input bytes and the selected attempt."""
    before = input_hashes(root, provenance, pilot_name)
    result = verify_locked(root, provenance, pilot_name)
    require(before == input_hashes(root, provenance, pilot_name), "INPUT_CHANGED_DURING_VERIFICATION")
    require(not (root / "data/active_collection_batch.json").exists(), "ACTIVE_BATCH_MARKER_PRESENT")
    return {**result, "selected_pilot": pilot_name, "input_file_sha256": before}


def copied_fixture(root: Path, destination: Path, provenance: Path, pilot_name: str) -> Path:
    """Copy real evidence into a disposable tree, leaving originals untouched."""
    build = read_json(root / "collector_build_manifest.json")
    inputs = Inputs(root.resolve(), provenance, build)
    for name in ("data", pilot_name):
        shutil.copytree(root / name, destination / name)
    paths = {root / "collector_build_manifest.json", root / "pilot_plan.json", root / "run_paired_browser_pilot.mjs", root / "backend_lifecycle_summary.json",
             root / pilot_name / "installed_collector.apk"}
    manifest = read_json(root / pilot_name / "run_manifest.json")
    paths.update(inputs.locked_path(row["path"]) for row in manifest["source_files"])
    paths.update(inputs.locked_path(row["source"]) for row in build["packaged_probe_assets"])
    paths.add(inputs.locked_path(build["apk"]["path"]))
    gitdir = root / "upstream/.git"
    paths.add(gitdir / "HEAD")
    head = (gitdir / "HEAD").read_text(encoding="ascii").strip()
    if head.startswith("ref: "):
        paths.add(gitdir / head[5:] if (gitdir / head[5:]).exists() else gitdir / "packed-refs")
    for source in paths:
        target = destination / source.resolve().relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    target_provenance = destination / "independent_test_provenance.jsonl"
    shutil.copyfile(provenance, target_provenance)
    return target_provenance


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rewrite_browser_copy(root: Path, index: int, change: dict[str, Any], pilot_name: str, payload_updates: dict[str, Any] | None = None) -> None:
    """Create a coherent falsified copy; canonical hashes alone must not pass it."""
    data, pilot = root / "data", root / pilot_name
    browsers, pairs, captures = read_jsonl(data / "raw_browser_payloads.jsonl"), read_jsonl(data / "browser_pair_provenance.jsonl"), read_jsonl(pilot / "captures.jsonl")
    capture = captures[index]
    browser = browsers[capture["archives"]["browser"]["line"] - 1]
    for name, value in change.items():
        layer, field = WEB_TARGETS[name].split(".")[1:]
        browser["canonical_received_payload"]["web_data"][layer][field] = value
    if payload_updates:
        browser["canonical_received_payload"].update(payload_updates)
    newhash = canonical_digest(browser["canonical_received_payload"])
    browser["browser_payload_sha256"] = capture["binding"]["browser_payload_sha256"] = newhash
    pair = pairs[capture["archives"]["provenance"]["line"] - 1]
    pair["browser_payload_sha256"] = newhash
    pair_events = read_jsonl(data / "browser_pair_events.jsonl")
    accepted = unique([row for row in pair_events if row.get("pair_id") == pair["pair_id"]],
                      "event", "browser_payload_accepted", "BROWSER_ACCEPTANCE_EVENT_NOT_UNIQUE")
    accepted["browser_payload_sha256"] = newhash
    capture["observed"] = observations(browser["canonical_received_payload"])
    write_jsonl(data / "raw_browser_payloads.jsonl", browsers)
    write_jsonl(data / "browser_pair_provenance.jsonl", pairs)
    write_jsonl(data / "browser_pair_events.jsonl", pair_events)
    for key, name in (("browser", "raw_browser_payloads.jsonl"), ("provenance", "browser_pair_provenance.jsonl")):
        lines = (data / name).read_bytes().split(b"\n")
        for item in captures:
            item["archives"][key]["line_sha256"] = digest(lines[item["archives"][key]["line"] - 1])
    write_jsonl(pilot / "captures.jsonl", captures)


def self_test(root: Path, provenance: Path, pilot_name: str = "pilot_r2") -> dict[str, Any]:
    """Check actual evidence, then reject tampering in temporary copies."""
    verify(root, provenance, pilot_name)
    mutations = {
        "canonical_hash_tampering": "APP_CANONICAL_HASH_MISMATCH",
        "missing_stage": "STAGE_COUNT_MISMATCH",
        "scope_changed_with_coherent_hashes": "BROWSER_UNTARGETED_SCOPE_CHANGED",
        "false_restoration_with_coherent_hashes": "RESTORATION_OBSERVATION_MISMATCH",
        "label_leakage_with_coherent_hashes": "CONTROL_LABEL_KEY_IN_PAYLOAD",
        "backend_ticket_removed": "PAIR_TICKET_NOT_UNIQUE",
        "installed_apk_tampering": "INSTALLED_APK_HASH_MISMATCH",
    }
    for name, expected_error in mutations.items():
        with tempfile.TemporaryDirectory(prefix="rba-verifier-") as directory:
            copyroot = Path(directory)
            copy_provenance = copied_fixture(root, copyroot, provenance, pilot_name)
            if name == "missing_stage":
                path = copyroot / pilot_name / "captures.jsonl"
                write_jsonl(path, read_jsonl(path)[:-1])
            elif name == "scope_changed_with_coherent_hashes":
                rewrite_browser_copy(copyroot, 1, {"timezone_id": "Etc/GMT", "timezone_offset": 0}, pilot_name)
            elif name == "false_restoration_with_coherent_hashes":
                rewrite_browser_copy(copyroot, 2, EXPECTED["language_fr"], pilot_name)
            elif name == "label_leakage_with_coherent_hashes":
                rewrite_browser_copy(copyroot, 1, {}, pilot_name, {"configuration_id": "language_fr"})
            elif name == "backend_ticket_removed":
                path = copyroot / "data/browser_pair_events.jsonl"
                captures = read_jsonl(copyroot / pilot_name / "captures.jsonl")
                pair_id = captures[0]["binding"]["pair_id"]
                write_jsonl(path, [row for row in read_jsonl(path) if row.get("pair_id") != pair_id
                                  or row.get("event") not in {"ticket_issued", "provisional_ticket_issued"}])
            elif name == "installed_apk_tampering":
                path = copyroot / pilot_name / "installed_collector.apk"
                blob = bytearray(path.read_bytes())
                blob[-1] ^= 1
                path.write_bytes(blob)
            else:
                path = copyroot / "data/raw_expanded_payloads.jsonl"
                rows = read_jsonl(path)
                captures_path = copyroot / pilot_name / "captures.jsonl"
                captures = read_jsonl(captures_path)
                target_line = captures[0]["archives"]["app"]["line"] - 1
                rows[target_line]["canonical_received_payload"]["timestamp"] += 1
                write_jsonl(path, rows)
                lines = path.read_bytes().split(b"\n")
                for capture in captures:
                    identity = capture["archives"]["app"]
                    identity["line_sha256"] = digest(lines[identity["line"] - 1])
                write_jsonl(captures_path, captures)
            try:
                verify(copyroot, copy_provenance, pilot_name)
            except VerificationError as error:
                require(str(error) == expected_error, "NEGATIVE_TEST_WRONG_FAILURE")
            else:
                raise VerificationError("NEGATIVE_TEST_UNEXPECTED_PASS")
    return {"schema_version": "browser67-independent-verifier-tests-v1", "tests": len(mutations) + 1, "passed": len(mutations) + 1,
            "selected_pilot": pilot_name, "real_data_baseline_passed": True, "rejected_mutations": list(mutations), "original_evidence_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--pilot", default="pilot_r2", help="Relative directory of the selected 18-slot run")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    provenance = args.provenance or root / args.pilot / "session_provenance.jsonl"
    output = root / ("verification_tests.json" if args.self_test else "verification.json")
    try:
        result = self_test(root, provenance, args.pilot) if args.self_test else verify(root, provenance, args.pilot)
    except (VerificationError, OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as error:
        code = str(error) if isinstance(error, VerificationError) else type(error).__name__
        result = {"schema_version": "browser67-independent-verification-v1", "verification": "failed", "failure_code": code}
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        raise SystemExit(1) from None
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
