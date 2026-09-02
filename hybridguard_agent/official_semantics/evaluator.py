"""Evaluate reviewed semantic relations derived from official field definitions.

The relation source is deliberately explicit: official documents establish
field semantics and supported capabilities, while the relation itself is a
project inference.  A strong inconsistency is a research semantic alert, not
an official verdict, calibrated attack probability, or fraud decision.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hybridguard_agent.adapters.official_kb_adapter import load_official_cards
from hybridguard_agent.evidence.extractor import (
    UNAVAILABLE_STATES,
    build_evidence_bundle_v2,
    normalize_payload,
)


AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEMANTIC_CATALOG = AGENT_ROOT / "config" / "official_semantic_relations.v1.json"
SEMANTIC_EXECUTION_VERSION = "official-semantic-execution-v1"
SEMANTIC_DECISION_VERSION = "official-semantic-decision-v1"
KNOWN_PREDICATES = {
    "native_web_android_major_equal_v1",
    "native_webview_android_major_equal_v1",
    "android_host_not_desktop_or_script_surface_v1",
    "webview_provider_runtime_chrome_major_equal_v1",
    "webview_default_runtime_ua_equal_v1",
    "mobile_ua_touch_positive_v1",
    "featureapp_jsbridge_present_v1",
    "debug_cleartext_context_v1",
    "android_gpu_not_windows_direct3d_v1",
}
MISSING = object()


def load_semantic_catalog(path: Path = DEFAULT_SEMANTIC_CATALOG) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("catalog_version") != "official-semantic-relations-v1":
        raise ValueError("Unsupported official semantic catalog version")
    if catalog.get("knowledge_source_type") != "official_derived_semantic_rule":
        raise ValueError("Official semantic catalog has an unexpected knowledge source type")
    relations = catalog.get("relations")
    if not isinstance(relations, list) or not relations:
        raise ValueError("Official semantic catalog has no relations")
    required = {
        "relation_id",
        "name",
        "relation_type",
        "premise_fields",
        "official_card_refs",
        "official_source_refs",
        "inference_level",
        "executable_status",
        "predicate_id",
        "severity",
        "risk_use_status",
        "tolerance",
        "counterexamples",
        "validation_status",
    }
    ids: set[str] = set()
    covered_cards: set[str] = set()
    _, official_cards = load_official_cards()
    known_cards = {card["source_card_id"] for card in official_cards}
    official_sources_by_card = {
        card["source_card_id"]: set(card["provenance"]["source_refs"])
        for card in official_cards
    }
    for relation in relations:
        if not isinstance(relation, dict):
            raise ValueError("Official semantic relation must be an object")
        missing = sorted(required - set(relation))
        if missing:
            raise ValueError(f"Relation is missing required fields: {missing}")
        relation_id = str(relation["relation_id"])
        if relation_id in ids:
            raise ValueError(f"Duplicate semantic relation id: {relation_id}")
        ids.add(relation_id)
        for list_field in (
            "premise_fields",
            "official_card_refs",
            "official_source_refs",
            "counterexamples",
        ):
            values = relation[list_field]
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ValueError(f"{relation_id} has an invalid {list_field}")
        if relation["severity"] not in {"strong", "soft", "context"}:
            raise ValueError(f"{relation_id} has an unsupported severity")
        unknown_cards = sorted(set(relation["official_card_refs"]) - known_cards)
        if unknown_cards:
            raise ValueError(f"{relation_id} references unknown official cards: {unknown_cards}")
        covered_cards.update(relation["official_card_refs"])
        allowed_sources = set().union(
            *(
                official_sources_by_card[card_id]
                for card_id in relation["official_card_refs"]
            )
        )
        unknown_sources = sorted(set(relation["official_source_refs"]) - allowed_sources)
        if unknown_sources:
            raise ValueError(
                f"{relation_id} cites sources not present on its official cards: "
                f"{unknown_sources}"
            )
        if relation["executable_status"] == "compiled_v1":
            predicate_id = relation.get("predicate_id")
            if predicate_id not in KNOWN_PREDICATES:
                raise ValueError(f"{relation_id} has unsupported predicate: {predicate_id}")
        elif relation.get("predicate_id") is not None:
            raise ValueError(f"Non-compiled relation {relation_id} must not declare a predicate")
    missing_cards = sorted(known_cards - covered_cards)
    if missing_cards:
        raise ValueError(f"Official semantic catalog does not cover cards: {missing_cards}")
    return catalog


def _fact_status(facts: dict[str, dict[str, Any]], fact_ids: list[str]) -> str:
    selected = [facts.get(fact_id) for fact_id in fact_ids]
    if any(item is None for item in selected):
        return "unknown"
    statuses = [str(item.get("status")) for item in selected if item is not None]
    if "unavailable" in statuses:
        return "unavailable"
    if any(status != "observed" for status in statuses):
        return "unknown"
    return "observed"


def _normalized_value(normalized: dict[str, Any], path: str) -> Any:
    layer_name, separator, leaf_name = path.partition(".")
    if not separator:
        return normalized.get(path, MISSING)
    layer = normalized.get(layer_name)
    if not isinstance(layer, dict):
        return MISSING
    return layer.get(leaf_name, MISSING)


def _field_status(
    normalized: dict[str, Any], field_states: dict[str, str], fields: list[str]
) -> str:
    states = [field_states.get(field) for field in fields if field_states.get(field) is not None]
    if any(state in UNAVAILABLE_STATES for state in states):
        return "unavailable"
    values = [_normalized_value(normalized, field) for field in fields]
    if any(value is MISSING or value is None or value == "" for value in values):
        return "unknown"
    return "observed"


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _chrome_major(value: Any) -> int | None:
    match = re.search(r"(?:Chrome|CriOS)/(\d{1,3})", str(value or ""), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _base_result(relation: dict[str, Any], outcome: str, detail: str) -> dict[str, Any]:
    return {
        "relation_id": relation["relation_id"],
        "relation_name": relation["name"],
        "predicate_id": relation["predicate_id"],
        "outcome": outcome,
        "severity": relation["severity"],
        "risk_use_status": relation["risk_use_status"],
        "source_fields": relation["premise_fields"],
        "official_card_refs": relation["official_card_refs"],
        "official_source_refs": relation["official_source_refs"],
        "inference_level": relation["inference_level"],
        "detail": detail,
    }


def _fact_equality(
    relation: dict[str, Any], facts: dict[str, dict[str, Any]], left: str, right: str
) -> dict[str, Any]:
    status = _fact_status(facts, [left, right])
    if status != "observed":
        return _base_result(relation, status, "Required parsed semantic facts are unavailable or unknown.")
    left_value = facts[left].get("value")
    right_value = facts[right].get("value")
    if left_value is None or right_value is None:
        return _base_result(relation, "unknown", "One or both semantic values cannot be parsed.")
    if left_value == right_value:
        return _base_result(relation, "consistent", "Parsed semantic values are equal.")
    return _base_result(relation, "inconsistent", "Parsed semantic values differ.")


def _evaluate_compiled(
    relation: dict[str, Any],
    normalized: dict[str, Any],
    field_states: dict[str, str],
    facts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    predicate_id = relation["predicate_id"]
    if predicate_id == "native_web_android_major_equal_v1":
        return _fact_equality(relation, facts, "native.android_major", "web.ua_android_major")
    if predicate_id == "native_webview_android_major_equal_v1":
        return _fact_equality(
            relation, facts, "native.android_major", "webview.http_android_major"
        )
    if predicate_id == "android_host_not_desktop_or_script_surface_v1":
        native_status = _fact_status(facts, ["native.android_major"])
        ua = facts.get("web.ua_class", {})
        platform = facts.get("web.platform_class", {})
        if native_status == "unavailable" or (
            ua.get("status") == "unavailable" and platform.get("status") == "unavailable"
        ):
            return _base_result(relation, "unavailable", "Host or Web surface evidence is unavailable.")
        if native_status != "observed" or facts["native.android_major"].get("value") is None:
            return _base_result(relation, "unknown", "Android host version cannot be determined.")
        ua_value = ua.get("value") if ua.get("status") == "observed" else None
        platform_value = platform.get("value") if platform.get("status") == "observed" else None
        if ua_value in {"script_client", "desktop_or_headless"} or platform_value == "desktop":
            return _base_result(
                relation,
                "inconsistent",
                "An Android Native host was observed with an explicit desktop/headless/script Web surface.",
            )
        if ua_value in {None, "unknown"} and platform_value in {None, "unknown"}:
            return _base_result(relation, "unknown", "Web surface class cannot be determined.")
        return _base_result(relation, "consistent", "No explicit desktop/headless/script marker was observed.")
    if predicate_id == "webview_provider_runtime_chrome_major_equal_v1":
        fields = ["webview_data.webview_provider_major", "web_data.user_agent"]
        status = _field_status(normalized, field_states, fields)
        if status != "observed":
            return _base_result(relation, status, "Provider major or runtime UA is unavailable or unknown.")
        provider_major = _integer(_normalized_value(normalized, fields[0]))
        runtime_major = _chrome_major(_normalized_value(normalized, fields[1]))
        if provider_major is None or runtime_major is None:
            return _base_result(relation, "unknown", "Provider or runtime Chrome major cannot be parsed.")
        if provider_major == runtime_major:
            return _base_result(relation, "consistent", "Provider and runtime Chrome majors are equal.")
        return _base_result(relation, "inconsistent", "Provider and runtime Chrome majors differ.")
    if predicate_id == "webview_default_runtime_ua_equal_v1":
        status = _fact_status(facts, ["webview.web_ua_exact_match"])
        if status != "observed":
            return _base_result(relation, status, "Default or runtime UA is unavailable or unknown.")
        if facts["webview.web_ua_exact_match"]["value"] is True:
            return _base_result(relation, "consistent", "Default and runtime UAs are exactly equal.")
        return _base_result(relation, "inconsistent", "Default and runtime UAs differ.")
    if predicate_id == "mobile_ua_touch_positive_v1":
        status = _fact_status(facts, ["web.ua_class", "web.max_touch_points"])
        if status != "observed":
            return _base_result(relation, status, "UA class or touch capability is unavailable or unknown.")
        ua_class = facts["web.ua_class"].get("value")
        touch_points = _integer(facts["web.max_touch_points"].get("value"))
        if ua_class == "unknown" or touch_points is None:
            return _base_result(relation, "unknown", "UA class or touch count cannot be parsed.")
        if ua_class not in {"android_browser", "android_webview"}:
            return _base_result(relation, "not_applicable", "The runtime UA is not an Android mobile class.")
        if touch_points > 0:
            return _base_result(relation, "consistent", "An Android mobile UA has a positive touch count.")
        return _base_result(relation, "inconsistent", "An Android mobile UA has zero touch points.")
    if predicate_id == "featureapp_jsbridge_present_v1":
        if normalized.get("collector_app") != "featureapp":
            return _base_result(relation, "not_applicable", "The collector is not featureapp.")
        status = _fact_status(facts, ["webview.jsbridge_state"])
        if status != "observed":
            return _base_result(relation, status, "JSBridge state is unavailable or unknown.")
        bridge_state = facts["webview.jsbridge_state"].get("value")
        if bridge_state is None:
            return _base_result(relation, "unknown", "JSBridge state is malformed.")
        if bridge_state is True:
            return _base_result(relation, "consistent", "FeatureApp JSBridge is present.")
        return _base_result(relation, "inconsistent", "FeatureApp JSBridge is absent.")
    if predicate_id == "debug_cleartext_context_v1":
        status = _fact_status(facts, ["webview.is_debuggable", "webview.cleartext_permitted"])
        if status != "observed":
            return _base_result(relation, status, "Debuggable or cleartext state is unavailable or unknown.")
        debuggable = facts["webview.is_debuggable"].get("value")
        cleartext = facts["webview.cleartext_permitted"].get("value")
        if debuggable is None or cleartext is None:
            return _base_result(relation, "unknown", "Debuggable or cleartext state is malformed.")
        if debuggable is True and cleartext is True:
            return _base_result(
                relation,
                "context_observed",
                "Debuggable and cleartext are both enabled; retained as development security context.",
            )
        return _base_result(relation, "consistent", "Debuggable and cleartext are not jointly enabled.")
    if predicate_id == "android_gpu_not_windows_direct3d_v1":
        native_fields = [
            "android_native_data.native_gpu_renderer",
            "android_native_data.egl_renderer",
        ]
        web_fields = ["web_data.webgl_vendor", "web_data.webgl_renderer"]
        native_values = []
        for field in native_fields:
            value = _normalized_value(normalized, field)
            if value is not MISSING and value is not None and value != "":
                native_values.append(value)
        web_values = []
        for field in web_fields:
            value = _normalized_value(normalized, field)
            if value is not MISSING and value is not None and value != "":
                web_values.append(value)
        unavailable = any(
            field_states.get(field) in UNAVAILABLE_STATES
            for field in native_fields + web_fields
        )
        if unavailable:
            return _base_result(relation, "unavailable", "Native or Web graphics evidence is unavailable.")
        if not native_values or not web_values:
            return _base_result(relation, "unknown", "Native or Web graphics evidence is missing.")
        web_text = " ".join(str(value).lower() for value in web_values)
        if any(marker in web_text for marker in ("direct3d", "d3d11", "d3d12", "windows")):
            return _base_result(
                relation,
                "inconsistent",
                "Android Native graphics evidence coexists with an explicit Windows/Direct3D WebGL marker.",
            )
        return _base_result(relation, "consistent", "No explicit Windows/Direct3D WebGL marker was observed.")
    raise ValueError(f"Unsupported official semantic predicate: {predicate_id}")


def _decision(execution: dict[str, Any]) -> dict[str, Any]:
    strong = list(execution["strong_inconsistency_relation_ids"])
    soft = list(execution["soft_inconsistency_relation_ids"])
    context = list(execution["context_relation_ids"])
    indeterminate = [
        result["relation_id"]
        for result in execution["relation_results"]
        if result["outcome"] in {"unknown", "unavailable"}
    ]
    if strong:
        status = "semantic_inconsistency_observed"
        conclusion = "strong_official_derived_relation_violated"
    elif soft:
        status = "semantic_deviation_observed"
        conclusion = "soft_official_derived_relation_violated"
    elif context:
        status = "context_observed"
        conclusion = "official_security_context_observed"
    elif indeterminate:
        status = "partially_assessed"
        conclusion = "no_inconsistency_observed_but_some_relations_indeterminate"
    else:
        status = "completed"
        conclusion = "no_compiled_semantic_inconsistency_observed"
    return {
        "decision_version": SEMANTIC_DECISION_VERSION,
        "decision_status": status,
        "conclusion": conclusion,
        "research_semantic_alert": bool(strong),
        "strong_inconsistency_relation_ids": strong,
        "soft_inconsistency_relation_ids": soft,
        "context_relation_ids": context,
        "indeterminate_relation_ids": indeterminate,
        "calibrated_risk_score": None,
        "claim_boundary": (
            "A research semantic alert means that a reviewed official-derived relation was violated. "
            "It is not an official verdict, attack label, fraud decision, or calibrated probability."
        ),
    }


def evaluate_official_semantics(
    payload: dict[str, Any],
    *,
    sample_id: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_catalog = catalog or load_semantic_catalog()
    normalized, field_states = normalize_payload(payload)
    evidence = build_evidence_bundle_v2(payload, sample_id=sample_id)
    facts = evidence["derived_facts"]
    compiled = [
        relation
        for relation in selected_catalog["relations"]
        if relation["executable_status"] == "compiled_v1"
    ]
    results = [
        _evaluate_compiled(relation, normalized, field_states, facts)
        for relation in compiled
    ]
    execution = {
        "execution_version": SEMANTIC_EXECUTION_VERSION,
        "catalog_version": selected_catalog["catalog_version"],
        "sample_id": evidence["sample_id"],
        "evidence_hash": evidence["evidence_hash"],
        "relation_results": results,
        "compiled_relation_ids": [relation["relation_id"] for relation in compiled],
        "not_executable_relation_ids": [
            relation["relation_id"]
            for relation in selected_catalog["relations"]
            if relation["executable_status"] != "compiled_v1"
        ],
        "strong_inconsistency_relation_ids": [
            result["relation_id"]
            for result in results
            if result["outcome"] == "inconsistent" and result["severity"] == "strong"
        ],
        "soft_inconsistency_relation_ids": [
            result["relation_id"]
            for result in results
            if result["outcome"] == "inconsistent" and result["severity"] == "soft"
        ],
        "context_relation_ids": [
            result["relation_id"] for result in results if result["outcome"] == "context_observed"
        ],
        "boundary": selected_catalog["boundary"],
    }
    return {
        "knowledge_source_type": selected_catalog["knowledge_source_type"],
        "decision": _decision(execution),
        "relation_execution": execution,
    }
