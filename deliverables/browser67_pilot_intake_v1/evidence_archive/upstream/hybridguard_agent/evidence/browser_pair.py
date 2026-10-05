"""Build deterministic, redacted App WebView versus browser pair evidence.

This module compares only the 67 App WebView fields with the paired 67 browser
fields.  A difference is a literal cross-runtime observation, never an attack
label, risk score, or device-identity conclusion.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = AGENT_ROOT / "config" / "browser_pair_comparison.v1.json"

BROWSER_PAIR_EVIDENCE_VERSION = "browser-pair-evidence-v1"
POLICY_VERSION = "browser-pair-comparison-policy-v1"
FIELD_STATUSES = frozenset(
    {
        "observed",
        "unsupported_by_os",
        "permission_denied",
        "runtime_error",
        "timeout",
        "not_applicable",
    }
)
UNAVAILABLE_STATUSES = FIELD_STATUSES - {"observed"}
VALUE_TYPES = frozenset({"number", "string", "boolean", "array"})
NOT_COMPARABLE_GROUPS = frozenset(
    {
        "diagnostic_only",
        "runtime_timing",
        "origin_or_permission_scope",
        "transient_network",
        "container_viewport",
    }
)
EXPECTED_INPUT_CONTRACT = {
    "dataset_manifest_version": "latest-featureapp-paired244-snapshot-v1",
    "paired_record_schema_version": "hybridguard-paired244-view-v1",
    "feature_catalog_version": "latest-paired244-feature-catalog-v1",
    "browser_probe_revision": "expanded-web-67-v1",
    "dataset_view": "paired_244",
    "dataset_role": "development_qc_only",
    "label_status": "unlabeled",
    "paired_feature_count": 244,
    "browser_field_count": 67,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Expected non-empty string for {field}")
    return value


def _policy_modes(policy: dict[str, Any]) -> tuple[set[str], dict[str, str]]:
    exact = policy.get("exact_fields")
    groups = policy.get("not_comparable_field_groups")
    if (
        not isinstance(exact, list)
        or len(exact) != 39
        or len(set(exact)) != 39
        or not isinstance(groups, dict)
        or set(groups) != NOT_COMPARABLE_GROUPS
    ):
        raise ValueError("Browser pair policy must freeze 39 exact fields and five groups")
    not_comparable: dict[str, str] = {}
    for group, fields in groups.items():
        if not isinstance(fields, list):
            raise ValueError(f"Invalid not-comparable group: {group}")
        for field in fields:
            if not isinstance(field, str) or field in not_comparable:
                raise ValueError(f"Invalid or duplicate not-comparable field: {field}")
            not_comparable[field] = group
    if len(not_comparable) != 28 or set(exact) & set(not_comparable):
        raise ValueError("Browser pair policy must freeze 28 disjoint not-comparable fields")
    if len(set(exact) | set(not_comparable)) != 67:
        raise ValueError("Browser pair policy must cover exactly 67 fields")
    return set(exact), not_comparable


def _validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("policy_version") != POLICY_VERSION:
        raise ValueError("Unsupported browser pair policy version")
    if policy.get("browser_pair_evidence_version") != BROWSER_PAIR_EVIDENCE_VERSION:
        raise ValueError("Unsupported browser pair evidence version in policy")
    if policy.get("comparison_mode") != "typed_exact_json_value_v1":
        raise ValueError("Unsupported browser pair comparison mode")
    if policy.get("metric_eligible") is not False:
        raise ValueError("Browser pair evidence must remain metric-ineligible")
    _nonempty(policy.get("claim_boundary"), "policy.claim_boundary")
    if set(policy.get("unavailable_statuses", [])) != UNAVAILABLE_STATUSES:
        raise ValueError("Browser pair unavailable-status policy drifted")
    if policy.get("required_input_contract") != EXPECTED_INPUT_CONTRACT:
        raise ValueError("Browser pair input contract drifted")
    _policy_modes(policy)
    return policy


def load_browser_pair_policy(
    path: Path | None = DEFAULT_POLICY_PATH,
) -> dict[str, Any]:
    """Load the frozen 39 exact / 28 not-comparable comparison policy."""
    policy_path = Path(path or DEFAULT_POLICY_PATH).resolve()
    value = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Browser pair policy must be a JSON object")
    return _validate_policy(value)


def _prepare_contract(
    feature_catalog: dict[str, Any],
    dataset_manifest: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, str], list[str], dict[str, str], set[str], dict[str, str]]:
    required = policy["required_input_contract"]
    selection = dataset_manifest.get("selection")
    views = dataset_manifest.get("views")
    paired_view = views.get("paired_244") if isinstance(views, dict) else None
    if (
        dataset_manifest.get("dataset_manifest_version")
        != required["dataset_manifest_version"]
        or dataset_manifest.get("dataset_role") != required["dataset_role"]
        or dataset_manifest.get("label_status") != required["label_status"]
        or not isinstance(selection, dict)
        or selection.get("browser_probe_revision") != required["browser_probe_revision"]
        or selection.get("pair_status") != "completed"
        or not isinstance(paired_view, dict)
        or paired_view.get("feature_count") != required["paired_feature_count"]
    ):
        raise ValueError("Paired244 manifest contract drifted")
    if (
        feature_catalog.get("feature_catalog_version")
        != required["feature_catalog_version"]
        or feature_catalog.get("browser_feature_count")
        != required["browser_field_count"]
    ):
        raise ValueError("Paired244 feature catalog contract drifted")

    order = feature_catalog.get("paired_feature_order")
    types = feature_catalog.get("paired_feature_types")
    if not isinstance(order, list) or not isinstance(types, dict):
        raise ValueError("Paired244 feature catalog has no order/type mapping")
    app_fields = [
        field.removeprefix("app.")
        for field in order
        if isinstance(field, str) and field.startswith("app.web_data.")
    ]
    browser_fields = [
        field.removeprefix("browser.")
        for field in order
        if isinstance(field, str) and field.startswith("browser.web_data.")
    ]
    if len(app_fields) != 67 or app_fields != browser_fields:
        raise ValueError("App WebView and browser 67-field catalogs do not align")
    exact, not_comparable = _policy_modes(policy)
    if set(browser_fields) != exact | set(not_comparable):
        raise ValueError("Browser pair policy does not match the current 67-field catalog")

    field_types: dict[str, str] = {}
    for field in browser_fields:
        app_type = types.get(f"app.{field}")
        browser_type = types.get(f"browser.{field}")
        if app_type not in VALUE_TYPES or browser_type != app_type:
            raise ValueError(f"App/browser type contract drifted for {field}")
        field_types[field] = app_type
    input_contract = {
        "dataset_manifest_version": required["dataset_manifest_version"],
        "paired_record_schema_version": required["paired_record_schema_version"],
        "feature_catalog_version": required["feature_catalog_version"],
        "browser_probe_revision": required["browser_probe_revision"],
    }
    return input_contract, browser_fields, field_types, exact, not_comparable


def _matches_type(value: Any, value_type: str) -> bool:
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "number":
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
        )
    if value_type == "string":
        return isinstance(value, str)
    return value_type == "array" and isinstance(value, list)


def _validate_row(
    row: dict[str, Any],
    dataset_manifest: dict[str, Any],
    policy: dict[str, Any],
    fields: list[str],
    field_types: dict[str, str],
) -> None:
    required = policy["required_input_contract"]
    if (
        row.get("record_schema_version") != required["paired_record_schema_version"]
        or row.get("dataset_view") != required["dataset_view"]
        or row.get("dataset_role") != dataset_manifest.get("dataset_role")
        or row.get("label_status") != dataset_manifest.get("label_status")
        or row.get("feature_count") != required["paired_feature_count"]
    ):
        raise ValueError("Paired244 row contract drifted")
    _nonempty(row.get("sample_id"), "paired244.sample_id")
    features = row.get("features")
    statuses = row.get("field_status")
    if not isinstance(features, dict) or not isinstance(statuses, dict):
        raise ValueError("Paired244 row has no feature/status mappings")
    for field in fields:
        for prefixed in (f"app.{field}", f"browser.{field}"):
            if prefixed not in features or prefixed not in statuses:
                raise ValueError(f"Paired244 row is missing required field: {prefixed}")
            status = statuses[prefixed]
            value = features[prefixed]
            if status not in FIELD_STATUSES:
                raise ValueError(f"Unsupported status for {prefixed}: {status}")
            if status == "observed" and value is None:
                raise ValueError(f"Observed field has null value: {prefixed}")
            if value is not None and not _matches_type(value, field_types[field]):
                raise ValueError(f"Field type drifted for {prefixed}")


def _compare_field(
    field: str,
    value_type: str,
    features: dict[str, Any],
    statuses: dict[str, str],
    exact: set[str],
    not_comparable: dict[str, str],
) -> dict[str, Any]:
    app_key = f"app.{field}"
    browser_key = f"browser.{field}"
    app_status = statuses[app_key]
    browser_status = statuses[browser_key]
    base = {
        "field_path": field,
        "value_type": value_type,
        "app_status": app_status,
        "browser_status": browser_status,
    }
    if field in not_comparable:
        return {
            **base,
            "comparison_mode": "not_comparable",
            "result": "not_comparable",
            "app_value_sha256": None,
            "browser_value_sha256": None,
            "reason_code": f"not_comparable_{not_comparable[field]}",
        }
    if field not in exact:
        raise ValueError(f"Field is missing from browser pair policy: {field}")
    if app_status != "observed" or browser_status != "observed":
        return {
            **base,
            "comparison_mode": "exact",
            "result": "unavailable",
            "app_value_sha256": None,
            "browser_value_sha256": None,
            "reason_code": "source_field_unavailable",
        }
    app_value = features[app_key]
    browser_value = features[browser_key]
    same = canonical_json(app_value) == canonical_json(browser_value)
    return {
        **base,
        "comparison_mode": "exact",
        "result": "same" if same else "different",
        "app_value_sha256": sha256_value(app_value),
        "browser_value_sha256": sha256_value(browser_value),
        "reason_code": "exact_values_equal" if same else "exact_values_different",
    }


def _check_output(evidence: dict[str, Any], expected_fields: set[str]) -> None:
    results = evidence["field_results"]
    paths = {result["field_path"] for result in results}
    counts = Counter(result["result"] for result in results)
    summary = evidence["summary"]
    if len(results) != 67 or paths != expected_fields:
        raise ValueError("Browser pair evidence field coverage drifted")
    if (
        summary["same_count"] != counts["same"]
        or summary["different_count"] != counts["different"]
        or summary["unavailable_count"] != counts["unavailable"]
        or summary["not_comparable_count"] != counts["not_comparable"]
        or sum(counts.values()) != 67
    ):
        raise ValueError("Browser pair evidence summary counts drifted")
    hash_input = {key: value for key, value in evidence.items() if key != "evidence_hash"}
    if evidence.get("evidence_hash") != sha256_value(hash_input):
        raise ValueError("Browser pair evidence hash drifted")


def build_browser_pair_evidence(
    row: dict[str, Any],
    feature_catalog: dict[str, Any],
    dataset_manifest: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Build one deterministic, raw-value-free browser-pair sidecar."""
    _validate_policy(policy)
    input_contract, fields, field_types, exact, not_comparable = _prepare_contract(
        feature_catalog, dataset_manifest, policy
    )
    _validate_row(row, dataset_manifest, policy, fields, field_types)
    field_results = [
        _compare_field(
            field,
            field_types[field],
            row["features"],
            row["field_status"],
            exact,
            not_comparable,
        )
        for field in fields
    ]
    counts = Counter(result["result"] for result in field_results)
    comparable = counts["same"] + counts["different"]
    evidence = {
        "browser_pair_evidence_version": BROWSER_PAIR_EVIDENCE_VERSION,
        "sample_id": row["sample_id"],
        "policy_version": policy["policy_version"],
        "input_contract": input_contract,
        "comparison_status": "completed" if comparable else "not_evaluable",
        "field_results": field_results,
        "summary": {
            "field_count": 67,
            "exact_policy_count": 39,
            "not_comparable_policy_count": 28,
            "same_count": counts["same"],
            "different_count": counts["different"],
            "unavailable_count": counts["unavailable"],
            "not_comparable_count": counts["not_comparable"],
            "comparable_observed_count": comparable,
        },
        "metric_eligible": False,
        "claim_boundary": policy["claim_boundary"],
    }
    evidence["evidence_hash"] = sha256_value(evidence)
    _check_output(evidence, set(fields))
    return evidence
