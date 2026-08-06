"""Run only reviewed, explicit predicates against a redacted EvidenceBundle v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hybridguard_agent.adapters.rule_kb_adapter import assert_pinned_rule_kb, load_rule_knowledge_base


AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICATE_REGISTRY = AGENT_ROOT / "config" / "deterministic_rule_predicates.v1.json"
RULE_EXECUTION_VERSION = "rule-execution-v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_predicate_registry(path: Path = DEFAULT_PREDICATE_REGISTRY) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _combined_fact_status(facts: dict[str, dict[str, Any]], fact_ids: list[str]) -> str:
    selected = [facts.get(fact_id) for fact_id in fact_ids]
    if any(item is None for item in selected):
        return "unknown"
    statuses = [str(item.get("status")) for item in selected if item is not None]
    if "unavailable" in statuses:
        return "unavailable"
    if any(status != "observed" for status in statuses):
        return "unknown"
    return "observed"


def _result(
    rule: dict[str, Any],
    spec: dict[str, Any],
    outcome: str,
    fact_ids: list[str],
    facts: dict[str, dict[str, Any]],
    detail: str,
) -> dict[str, Any]:
    fields = sorted({field for fact_id in fact_ids for field in facts.get(fact_id, {}).get("source_fields", [])})
    return {
        "rule_id": rule["id"],
        "card_id": f"RULE-{rule['id']}",
        "predicate_id": spec["predicate_id"],
        "outcome": outcome,
        "short_circuit": bool(spec.get("short_circuit", False)),
        "source_fact_ids": fact_ids,
        "source_fields": fields,
        "detail": detail,
    }


def _not_evaluated_result(
    rule: dict[str, Any],
    spec: dict[str, Any],
    facts: dict[str, dict[str, Any]],
    *,
    halted_by_rule_id: str,
) -> dict[str, Any]:
    return _result(
        rule,
        spec,
        "not_evaluated",
        list(spec["fact_ids"]),
        facts,
        f"Not evaluated because short-circuit rule {halted_by_rule_id} already matched.",
    )


def _evaluate(rule: dict[str, Any], spec: dict[str, Any], facts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fact_ids = list(spec["fact_ids"])
    status = _combined_fact_status(facts, fact_ids)
    if status != "observed":
        return _result(rule, spec, status, fact_ids, facts, "Required evidence is unavailable or cannot be determined.")

    values = {fact_id: facts[fact_id]["value"] for fact_id in fact_ids}
    predicate_id = spec["predicate_id"]
    outcome = "not_matched"
    detail = "The explicit predicate did not observe its documented condition."

    if predicate_id == "sensor_or_jsbridge_absent_v1":
        outcome = "matched" if float(values["native.sensor_total_count"]) < 10 or values["webview.jsbridge_state"] is False else "not_matched"
        detail = "Sensor total is below 10 or JSBridge is false." if outcome == "matched" else detail
    elif predicate_id == "native_web_android_major_neq_v1":
        outcome = "matched" if values["native.android_major"] != values["web.ua_android_major"] else "not_matched"
        detail = "Native and Web Android majors differ." if outcome == "matched" else detail
    elif predicate_id == "desktop_or_script_ua_surface_v1":
        outcome = "matched" if values["web.ua_class"] in {"script_client", "desktop_or_headless"} or values["web.platform_class"] == "desktop" else "not_matched"
        detail = "Coarse UA or platform classification is desktop/headless/script." if outcome == "matched" else detail
    elif predicate_id == "mobile_ua_zero_touch_v1":
        outcome = "matched" if values["web.ua_class"] in {"android_browser", "android_webview"} and int(values["web.max_touch_points"]) == 0 else "not_matched"
        detail = "Android-mobile UA class was observed with zero touch points." if outcome == "matched" else detail
    elif predicate_id == "native_webview_android_major_neq_v1":
        outcome = "matched" if values["native.android_major"] != values["webview.http_android_major"] else "not_matched"
        detail = "Native and WebView HTTP Android majors differ." if outcome == "matched" else detail
    elif predicate_id == "debug_and_cleartext_context_v1":
        outcome = "context_observed" if values["webview.is_debuggable"] is True and values["webview.cleartext_permitted"] is True else "not_matched"
        detail = "Debuggable plus cleartext is recorded as development context, not a risk score." if outcome == "context_observed" else detail
    elif predicate_id == "adb_and_high_battery_context_v1":
        outcome = "context_observed" if values["native.adb_enabled"] is True and float(values["native.battery_level_pct"]) >= 97 else "not_matched"
        detail = "ADB with high battery is recorded as collection/test context, not an attack label." if outcome == "context_observed" else detail
    elif predicate_id == "normalized_build_marker_context_v1":
        outcome = "context_observed" if values["native.build_marker_categories"] else "not_matched"
        detail = "Normalized build-marker categories were observed; they require context and do not calibrate a score." if outcome == "context_observed" else detail
    elif predicate_id == "test_rig_context_v1":
        manual = values["webview.installer_class"] == "manual"
        adb = values["native.adb_enabled"] is True
        high_battery = float(values["native.battery_level_pct"]) >= 97
        utc = values["web.timezone_offset"] == 0
        outcome = "context_observed" if (manual and (utc or adb)) or (adb and high_battery) else "not_matched"
        detail = "A documented collection/test-rig context combination was observed; it is not an attack label." if outcome == "context_observed" else detail
    elif predicate_id == "script_user_agent_surface_v1":
        outcome = "matched" if values["web.ua_class"] == "script_client" else "not_matched"
        detail = "The coarse UA class is a script client." if outcome == "matched" else detail
    else:
        raise ValueError(f"Unsupported predicate id: {predicate_id}")
    return _result(rule, spec, outcome, fact_ids, facts, detail)


def execute_deterministic_rules(
    evidence_bundle: dict[str, Any],
    predicate_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = predicate_registry or load_predicate_registry()
    rule_kb_hash = assert_pinned_rule_kb(registry)
    kb = load_rule_knowledge_base()
    rules = {str(rule["id"]): rule for rule in kb.get("rules", [])}
    specs = registry.get("compiled_rules")
    if not isinstance(specs, dict):
        raise ValueError("Predicate registry has no compiled_rules mapping")
    facts = evidence_bundle.get("derived_facts")
    if not isinstance(facts, dict):
        raise ValueError("EvidenceBundle has no derived_facts")

    results = []
    halted_by_rule_id: str | None = None
    for rule_id, spec in specs.items():
        if rule_id not in rules:
            raise ValueError(f"Predicate registry references an unknown rule: {rule_id}")
        if halted_by_rule_id is not None:
            results.append(
                _not_evaluated_result(
                    rules[rule_id],
                    spec,
                    facts,
                    halted_by_rule_id=halted_by_rule_id,
                )
            )
            continue
        result = _evaluate(rules[rule_id], spec, facts)
        results.append(result)
        if result["short_circuit"] and result["outcome"] == "matched":
            halted_by_rule_id = str(result["rule_id"])
    results.sort(key=lambda item: (-int(rules[item["rule_id"]].get("priority", 0)), item["rule_id"]))

    compiled_rule_ids = set(specs)
    mandatory_rule_ids = {str(rule["id"]) for rule in rules.values() if rule.get("short_circuit")}
    short_circuit_matches = [
        result["rule_id"]
        for result in results
        if result["short_circuit"] and result["outcome"] == "matched"
    ]
    return {
        "rule_execution_version": RULE_EXECUTION_VERSION,
        "predicate_registry_version": registry.get("predicate_registry_version"),
        "rule_kb_version": kb.get("version"),
        "rule_kb_sha256": rule_kb_hash,
        "sample_id": evidence_bundle.get("sample_id"),
        "evidence_hash": evidence_bundle.get("evidence_hash"),
        "rule_results": results,
        "matched_rule_ids": [result["rule_id"] for result in results if result["outcome"] == "matched"],
        "tolerance_or_context_rule_ids": [
            result["rule_id"] for result in results if result["outcome"] == "context_observed"
        ],
        "unevaluated_rule_ids": sorted(set(rules) - compiled_rule_ids),
        "short_circuit_status": {
            "matched_rule_ids": short_circuit_matches,
            "halted_after_rule_id": halted_by_rule_id,
            "skipped_rule_ids": [
                result["rule_id"] for result in results if result["outcome"] == "not_evaluated"
            ],
            "unevaluated_mandatory_rule_ids": sorted(mandatory_rule_ids - compiled_rule_ids),
            "clear": not short_circuit_matches and not (mandatory_rule_ids - compiled_rule_ids),
        },
        "boundary_note": registry.get("boundary"),
    }
