"""Offline MTC quality comparisons; these observations are never attack labels.

V1 remains frozen for historical replay. V2 uses numeric value equality, with
explicit source-status and known collector-fallback gates before comparison.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .browser_pair import _policy_modes, _matches_type, UNAVAILABLE_STATUSES

POLICY_PATH = Path(__file__).resolve().parents[1] / "config/browser_pair_comparison.v2.json"
POLICY_VERSION = "browser-pair-comparison-policy-v2"


def load_policy(path=POLICY_PATH):
    policy = json.loads(Path(path).read_text())
    if (policy.get("policy_version") != POLICY_VERSION
            or policy.get("comparison_mode") != "typed_numeric_value_v2"
            or policy.get("metric_eligible") is not False
            or set(policy.get("unavailable_statuses", [])) != UNAVAILABLE_STATUSES):
        raise ValueError("Invalid MTC comparison policy")
    _policy_modes(policy)
    return policy


def semantic_equal(left, right):
    """JSON values, with finite numeric equality and no bool/string coercion."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(left) and math.isfinite(right) and left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(semantic_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(semantic_equal(left[k], right[k]) for k in left)
    return left == right


def quality_state(field, value, status, policy):
    if status != "observed":
        return "source_unavailable"
    for sentinel in policy["ambiguous_sentinels"].get(field, []):
        if semantic_equal(value, sentinel):
            return "ambiguous_sentinel"
    return "observed_value"


def compare_field(field, expected_type, app_value, browser_value, app_status, browser_status, policy):
    exact, excluded = _policy_modes(policy)
    if field in excluded:
        return {"result": "not_comparable", "reason": excluded[field]}
    if field not in exact:
        raise ValueError("Unknown comparison field: " + field)
    if app_status != "observed" or browser_status != "observed":
        return {"result": "unavailable", "reason": "source_field_unavailable"}
    if not _matches_type(app_value, expected_type) or not _matches_type(browser_value, expected_type):
        raise ValueError("Observed comparison value violates field type: " + field)
    if any(quality_state(field, value, "observed", policy) == "ambiguous_sentinel"
           for value in (app_value, browser_value)):
        return {"result": "unavailable", "reason": "ambiguous_collector_sentinel"}
    return {"result": "same" if semantic_equal(app_value, browser_value) else "different",
            "reason": "typed_value_observation_only"}


def compare_record(row, browser_types, policy):
    if row.get("record_schema_version") != "hybridguard-mtc-observation-v2":
        raise ValueError("V2 comparison requires the MTC v2 observation contract")
    if not row.get("pair") or row["pair"].get("pair_status") != "completed":
        raise ValueError("Comparison requires completed pair provenance")
    features, statuses = row["features"], row["field_status"]
    results = {}
    for field, expected_type in browser_types.items():
        a, b = "app." + field, "browser." + field
        results[field] = compare_field(field, expected_type, features[a], features[b], statuses[a], statuses[b], policy)
    return {"sample_id": row["sample_id"], "policy_version": POLICY_VERSION,
            "metric_eligible": False, "field_results": results}
