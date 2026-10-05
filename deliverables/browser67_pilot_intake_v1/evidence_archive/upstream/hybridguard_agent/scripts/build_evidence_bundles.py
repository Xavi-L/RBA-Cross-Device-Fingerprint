#!/usr/bin/env python3
"""Build deterministic, label-free evidence bundles from a frozen snapshot.

The output records observed relationships only. It intentionally does not emit a
risk label, tool name, provider, pair role, or final score.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACT_ROOT = AGENT_ROOT / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                yield json.loads(text)


def get_path(payload: dict[str, Any], path: str, default: Any = None) -> Any:
    value: Any = payload
    for segment in path.split("."):
        if not isinstance(value, dict) or segment not in value:
            return default
        value = value[segment]
    return value


def observation(
    observation_id: str,
    fields: list[str],
    status: str,
    note: str,
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "fields": fields,
        "status": status,
        "note": note,
    }


def android_major(text: Any) -> str | None:
    match = re.search(r"Android\s+(\d+)", str(text or ""), flags=re.IGNORECASE)
    return match.group(1) if match else None


def model_ua_observation(payload: dict[str, Any]) -> dict[str, Any]:
    model = str(get_path(payload, "android_native_data.device_model", "")).strip()
    ua = str(get_path(payload, "web_data.user_agent", "")).lower()
    if not model or not ua:
        return observation(
            "native_web_model_ua", ["android_native_data.device_model", "web_data.user_agent"], "unknown", "model or web user-agent absent"
        )
    if model.lower() in ua:
        return observation(
            "native_web_model_ua", ["android_native_data.device_model", "web_data.user_agent"], "matched", "native model string appears in web user-agent"
        )
    return observation(
        "native_web_model_ua", ["android_native_data.device_model", "web_data.user_agent"], "not_matched", "native model string does not appear verbatim in web user-agent"
    )


def os_ua_observation(payload: dict[str, Any]) -> dict[str, Any]:
    native_os = android_major(get_path(payload, "android_native_data.os_version"))
    ua_os = android_major(get_path(payload, "web_data.user_agent"))
    if native_os is None or ua_os is None:
        return observation(
            "native_web_os_ua", ["android_native_data.os_version", "web_data.user_agent"], "unknown", "Android version could not be parsed on both sides"
        )
    return observation(
        "native_web_os_ua", ["android_native_data.os_version", "web_data.user_agent"], "matched" if native_os == ua_os else "not_matched", f"native={native_os}; web_ua={ua_os}"
    )


def webview_web_ua_observation(payload: dict[str, Any]) -> dict[str, Any]:
    webview_ua = get_path(payload, "webview_data.default_ua_native")
    web_ua = get_path(payload, "web_data.user_agent")
    if not webview_ua or not web_ua:
        return observation(
            "webview_web_user_agent", ["webview_data.default_ua_native", "web_data.user_agent"], "unknown", "WebView or web user-agent absent"
        )
    return observation(
        "webview_web_user_agent", ["webview_data.default_ua_native", "web_data.user_agent"], "matched" if webview_ua == web_ua else "not_matched", "exact normalized string comparison"
    )


def runtime_context(payload: dict[str, Any]) -> list[dict[str, Any]]:
    contexts = [
        ("adb_enabled", "android_native_data.is_adb_enabled"),
        ("developer_options_enabled", "android_native_data.developer_options_enabled"),
        ("webview_debuggable", "webview_data.is_debuggable"),
        ("http_proxy_setting", "android_native_data.http_proxy_setting"),
        ("webdriver", "web_data.webdriver"),
    ]
    output = []
    for name, path in contexts:
        value = get_path(payload, path)
        if value is None or value == "":
            state = "absent_or_unknown"
        elif isinstance(value, bool):
            state = "true" if value else "false"
        else:
            state = "present"
        output.append(observation(f"runtime_{name}", [path], state, "runtime context only; not a risk conclusion"))
    return output


def build_bundle(record: dict[str, Any]) -> dict[str, Any]:
    payload = record["payload"]
    return {
        "evidence_bundle_version": "evidence-bundle-v1",
        "sample_id": record["sample_id"],
        "schema_version": "expanded-v2",
        "evidence_groups": {
            "cross_layer": [
                model_ua_observation(payload),
                os_ua_observation(payload),
                webview_web_ua_observation(payload),
            ],
            "runtime_context": runtime_context(payload),
        },
        "boundary_note": "Deterministic observations only; no source, label, attack tool, provider, pair metadata, or risk score is included.",
    }


def main() -> None:
    args = parse_args()
    snapshot_dir = args.snapshot_dir.resolve()
    normalized_path = snapshot_dir / "normalized_expanded_v2.jsonl"
    if not normalized_path.exists():
        raise FileNotFoundError(f"Missing normalized snapshot input: {normalized_path}")
    bundles = [build_bundle(record) for record in read_jsonl(normalized_path)]
    output_path = snapshot_dir / "evidence_bundles.jsonl"
    with output_path.open("w", encoding="utf-8") as handle:
        for bundle in bundles:
            handle.write(json.dumps(bundle, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Evidence bundles written: {output_path} ({len(bundles)} rows)")


if __name__ == "__main__":
    main()
