"""Build a label-free, offline clean/active/post comparison sidecar.

This module deliberately consumes only the safe scenario-input projection,
normalized payloads, field-status sidecars, and a frozen comparison policy.
It must not read SampleManifest, annotation registries, attack labels, or tool
metadata.  The output is for controlled-experiment replay only and is not an
input to the single-sample runtime.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = AGENT_ROOT / "config" / "controlled_scenario_v1.json"
SCENARIO_INPUT_VERSION = "controlled-scenario-input-v1"
SCENARIO_SIDECAR_VERSION = "controlled-scenario-sidecar-v1"

SCENARIO_INPUT_KEYS = {
    "controlled_scenario_input_version",
    "sample_id",
    "normalized_payload_sha256",
    "stable_device_key_hash",
    "pair",
}
PAIR_KEYS = {"pair_key_sha256", "pair_role", "sequence_index"}
HEX_LENGTH = 64


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"Expected object in {path}:{line_number}")
            yield value


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Expected non-empty string for {field}")
    return value


def _require_sha256(value: Any, *, field: str) -> str:
    text = _require_non_empty_string(value, field=field)
    if len(text) != HEX_LENGTH or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"Expected SHA-256 hex value for {field}")
    return text


def _index_rows(path: Path, *, kind: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        sample_id = _require_non_empty_string(row.get("sample_id"), field=f"{kind}.sample_id")
        if sample_id in result:
            raise ValueError(f"Duplicate sample_id in {kind}: {sample_id}")
        result[sample_id] = row
    return result


def load_controlled_scenario_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    """Load and validate the frozen, target-field comparison policy."""
    policy_path = path.resolve()
    value = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Controlled scenario policy must be an object: {policy_path}")
    if value.get("policy_version") != "controlled-scenario-policy-v1":
        raise ValueError("Unsupported controlled scenario policy version")
    if value.get("controlled_scenario_input_version") != SCENARIO_INPUT_VERSION:
        raise ValueError("Controlled scenario policy has an unsupported input version")
    if value.get("controlled_scenario_sidecar_version") != SCENARIO_SIDECAR_VERSION:
        raise ValueError("Controlled scenario policy has an unsupported sidecar version")
    required_roles = value.get("required_roles")
    if not isinstance(required_roles, list) or len(required_roles) != 3:
        raise ValueError("Controlled scenario policy must define exactly three required roles")
    expected_roles: dict[str, int] = {}
    for item in required_roles:
        if not isinstance(item, dict):
            raise ValueError("Controlled scenario policy role entry must be an object")
        role = _require_non_empty_string(item.get("pair_role"), field="policy.required_roles.pair_role")
        sequence = item.get("sequence_index")
        if not isinstance(sequence, int) or sequence < 0 or role in expected_roles:
            raise ValueError("Controlled scenario policy has invalid or duplicate role definitions")
        expected_roles[role] = sequence
    if set(expected_roles) != {"clean_pre", "attack_active", "clean_post"}:
        raise ValueError("Controlled scenario policy must use clean_pre, attack_active, clean_post")
    target_fields = value.get("target_field_paths")
    if (
        not isinstance(target_fields, list)
        or not target_fields
        or any(not isinstance(path, str) or not path for path in target_fields)
        or len(set(target_fields)) != len(target_fields)
    ):
        raise ValueError("Controlled scenario policy has invalid target_field_paths")
    minimum = value.get("minimum_changed_and_restored_fields")
    if not isinstance(minimum, int) or minimum < 1 or minimum > len(target_fields):
        raise ValueError("Controlled scenario policy has invalid minimum change count")
    if value.get("require_same_stable_device_key") is not True:
        raise ValueError("Controlled scenario policy must require a stable-device key match")
    if value.get("require_all_target_fields_observed") is not True:
        raise ValueError("Controlled scenario policy must require observed target fields")
    if value.get("metric_eligible") is not False:
        raise ValueError("Controlled scenario v1 must remain metric-ineligible")
    _require_non_empty_string(value.get("comparison_policy"), field="policy.comparison_policy")
    _require_non_empty_string(value.get("metric_eligibility_reason"), field="policy.metric_eligibility_reason")
    _require_non_empty_string(value.get("claim_boundary"), field="policy.claim_boundary")
    return value


def _load_safe_scenario_input(path: Path) -> dict[str, dict[str, Any]]:
    """Load the projection and reject accidental metadata leakage by shape."""
    rows = _index_rows(path, kind="controlled scenario input")
    for sample_id, row in rows.items():
        unexpected = sorted(set(row) - SCENARIO_INPUT_KEYS)
        missing = sorted(SCENARIO_INPUT_KEYS - set(row))
        if unexpected or missing:
            raise ValueError(
                "Controlled scenario input must contain exactly the approved fields for "
                f"{sample_id}; unexpected={unexpected}, missing={missing}"
            )
        if row.get("controlled_scenario_input_version") != SCENARIO_INPUT_VERSION:
            raise ValueError(f"Unsupported controlled scenario input version for {sample_id}")
        _require_sha256(row.get("normalized_payload_sha256"), field=f"{sample_id}.normalized_payload_sha256")
        _require_sha256(row.get("stable_device_key_hash"), field=f"{sample_id}.stable_device_key_hash")
        pair = row.get("pair")
        if pair is None:
            continue
        if not isinstance(pair, dict):
            raise ValueError(f"Controlled scenario pair must be object or null for {sample_id}")
        unexpected_pair = sorted(set(pair) - PAIR_KEYS)
        missing_pair = sorted(PAIR_KEYS - set(pair))
        if unexpected_pair or missing_pair:
            raise ValueError(
                "Controlled scenario pair must contain exactly approved fields for "
                f"{sample_id}; unexpected={unexpected_pair}, missing={missing_pair}"
            )
        _require_sha256(pair.get("pair_key_sha256"), field=f"{sample_id}.pair_key_sha256")
        _require_non_empty_string(pair.get("pair_role"), field=f"{sample_id}.pair_role")
        sequence_index = pair.get("sequence_index")
        if not isinstance(sequence_index, int) or sequence_index < 0:
            raise ValueError(f"Controlled scenario sequence_index is invalid for {sample_id}")
    return rows


def _load_normalized_payloads(path: Path) -> dict[str, dict[str, Any]]:
    rows = _index_rows(path, kind="normalized payload")
    output: dict[str, dict[str, Any]] = {}
    for sample_id, row in rows.items():
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"Normalized payload is not an object for {sample_id}")
        output[sample_id] = payload
    return output


def _load_field_status(path: Path) -> dict[str, dict[str, Any]]:
    rows = _index_rows(path, kind="field-status")
    output: dict[str, dict[str, Any]] = {}
    for sample_id, row in rows.items():
        status = row.get("field_status")
        if not isinstance(status, dict) or not isinstance(status.get("fields"), dict):
            raise ValueError(f"Field-status is missing fields map for {sample_id}")
        output[sample_id] = status
    return output


def _get_path(value: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = value
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _status_for_path(status: dict[str, Any], path: str) -> str:
    state = status.get("fields", {}).get(path)
    return state if isinstance(state, str) else "unavailable"


def _member_view(
    record: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    pair = record["pair"]
    assert isinstance(pair, dict)
    return {
        "sample_id": record["sample_id"],
        "pair_role": pair["pair_role"],
        "sequence_index": pair["sequence_index"],
        "normalized_payload_sha256": sha256_value(payload),
    }


def _field_comparison(
    *,
    path: str,
    pre_payload: dict[str, Any],
    active_payload: dict[str, Any],
    post_payload: dict[str, Any],
    pre_status: dict[str, Any],
    active_status: dict[str, Any],
    post_status: dict[str, Any],
) -> dict[str, Any]:
    statuses = {
        "clean_pre": _status_for_path(pre_status, path),
        "attack_active": _status_for_path(active_status, path),
        "clean_post": _status_for_path(post_status, path),
    }
    if any(state != "observed" for state in statuses.values()):
        return {
            "field_path": path,
            "field_status": statuses,
            "comparison_status": "unavailable",
            "value_sha256": None,
        }
    pre_present, pre_value = _get_path(pre_payload, path)
    active_present, active_value = _get_path(active_payload, path)
    post_present, post_value = _get_path(post_payload, path)
    if not (pre_present and active_present and post_present):
        return {
            "field_path": path,
            "field_status": statuses,
            "comparison_status": "unavailable",
            "value_sha256": None,
        }
    value_hashes = {
        "clean_pre": sha256_value(pre_value),
        "attack_active": sha256_value(active_value),
        "clean_post": sha256_value(post_value),
    }
    if pre_value != post_value:
        comparison_status = "baseline_not_restored"
    elif active_value != pre_value:
        comparison_status = "changed_and_restored"
    else:
        comparison_status = "unchanged"
    return {
        "field_path": path,
        "field_status": statuses,
        "comparison_status": comparison_status,
        "value_sha256": value_hashes,
    }


def _build_one_scenario(
    pair_key_sha256: str,
    members: list[dict[str, Any]],
    payloads: dict[str, dict[str, Any]],
    status_rows: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    required_roles = {
        item["pair_role"]: item["sequence_index"] for item in policy["required_roles"]
    }
    ordered_roles = sorted(required_roles, key=lambda role: required_roles[role])
    member_views: list[dict[str, Any]] = []
    role_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stable_keys: set[str] = set()
    reasons: list[str] = []

    for record in members:
        sample_id = record["sample_id"]
        payload = payloads.get(sample_id)
        if payload is None:
            raise ValueError(f"Scenario input references missing normalized payload: {sample_id}")
        if sample_id not in status_rows:
            raise ValueError(f"Scenario input references missing field-status: {sample_id}")
        if sha256_value(payload) != record["normalized_payload_sha256"]:
            raise ValueError(f"Normalized payload hash mismatch for controlled scenario input: {sample_id}")
        pair = record["pair"]
        assert isinstance(pair, dict)
        member_views.append(_member_view(record, payload))
        role_members[pair["pair_role"]].append(record)
        stable_keys.add(record["stable_device_key_hash"])

    for role, expected_sequence in required_roles.items():
        entries = role_members.get(role, [])
        if not entries:
            reasons.append(f"missing_role:{role}")
        elif len(entries) > 1:
            reasons.append(f"duplicate_role:{role}")
        elif entries[0]["pair"]["sequence_index"] != expected_sequence:
            reasons.append(f"sequence_index_mismatch:{role}")
    for role in sorted(set(role_members) - set(required_roles)):
        reasons.append(f"unsupported_role:{role}")
    if len(stable_keys) != 1:
        reasons.append("stable_device_key_mismatch")

    role_order = {role: index for index, role in enumerate(ordered_roles)}
    member_views.sort(key=lambda item: (role_order.get(item["pair_role"], 99), item["sample_id"]))
    scenario = {
        "scenario_schema_version": SCENARIO_SIDECAR_VERSION,
        "scenario_id": f"cscenario-v1-{pair_key_sha256[:24]}",
        "pair_key_sha256": pair_key_sha256,
        "members": member_views,
        "pair_invariants": {
            "stable_device_key_consistent": len(stable_keys) == 1,
            "stable_device_key_hash": next(iter(stable_keys)) if len(stable_keys) == 1 else None,
        },
        "comparison_policy": {
            "policy_version": policy["policy_version"],
            "comparison_policy": policy["comparison_policy"],
            "target_field_paths": list(policy["target_field_paths"]),
            "require_all_target_fields_observed": policy["require_all_target_fields_observed"],
            "minimum_changed_and_restored_fields": policy["minimum_changed_and_restored_fields"],
        },
        "field_comparisons": [],
        "scenario_status": "not_evaluable",
        "reasons": sorted(set(reasons)),
        "metric_eligible": policy["metric_eligible"],
        "metric_eligibility_reason": policy["metric_eligibility_reason"],
        "claim_boundary": policy["claim_boundary"],
    }
    if reasons:
        return scenario

    indexed = {role: role_members[role][0] for role in ordered_roles}
    comparisons = [
        _field_comparison(
            path=path,
            pre_payload=payloads[indexed["clean_pre"]["sample_id"]],
            active_payload=payloads[indexed["attack_active"]["sample_id"]],
            post_payload=payloads[indexed["clean_post"]["sample_id"]],
            pre_status=status_rows[indexed["clean_pre"]["sample_id"]],
            active_status=status_rows[indexed["attack_active"]["sample_id"]],
            post_status=status_rows[indexed["clean_post"]["sample_id"]],
        )
        for path in policy["target_field_paths"]
    ]
    comparison_counts = Counter(item["comparison_status"] for item in comparisons)
    scenario["field_comparisons"] = comparisons
    if comparison_counts["unavailable"] or comparison_counts["baseline_not_restored"]:
        scenario["scenario_status"] = "insufficient_evidence"
        scenario["reasons"] = sorted(comparison_counts)
    elif comparison_counts["changed_and_restored"] >= policy["minimum_changed_and_restored_fields"]:
        scenario["scenario_status"] = "controlled_target_field_change_observed"
        scenario["reasons"] = []
    elif comparison_counts["unchanged"] == len(comparisons):
        scenario["scenario_status"] = "no_configured_target_field_change_observed"
        scenario["reasons"] = []
    else:
        scenario["scenario_status"] = "insufficient_evidence"
        scenario["reasons"] = sorted(comparison_counts)
    return scenario


def build_controlled_scenario_sidecar(
    snapshot_dir: Path,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> dict[str, Any]:
    """Build the sidecar without reading label-, attack-, or tool-bearing files."""
    directory = snapshot_dir.resolve()
    input_path = directory / "controlled_scenario_input_v1.jsonl"
    normalized_path = directory / "normalized_expanded_v2.jsonl"
    field_status_path = directory / "field_status.jsonl"
    for path in (input_path, normalized_path, field_status_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing controlled-scenario input: {path}")
    policy = load_controlled_scenario_policy(policy_path)
    scenario_inputs = _load_safe_scenario_input(input_path)
    payloads = _load_normalized_payloads(normalized_path)
    status_rows = _load_field_status(field_status_path)
    input_ids = set(scenario_inputs)
    if input_ids != set(payloads) or input_ids != set(status_rows):
        raise ValueError("Controlled scenario inputs, normalized payloads, and field-status rows must be one-to-one")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in scenario_inputs.values():
        pair = record["pair"]
        if isinstance(pair, dict):
            groups[pair["pair_key_sha256"]].append(record)
    scenarios = [
        _build_one_scenario(pair_key, groups[pair_key], payloads, status_rows, policy)
        for pair_key in sorted(groups)
    ]
    status_counts = Counter(scenario["scenario_status"] for scenario in scenarios)
    policy_file = policy_path.resolve()
    try:
        policy_reference = str(policy_file.relative_to(AGENT_ROOT.parent))
    except ValueError:
        policy_reference = str(policy_file)
    return {
        "controlled_scenario_sidecar_version": SCENARIO_SIDECAR_VERSION,
        "policy": {
            "path": policy_reference,
            "sha256": sha256_file(policy_file),
            "policy_version": policy["policy_version"],
        },
        "input_audit": {
            "controlled_scenario_input_sha256": sha256_file(input_path),
            "normalized_payload_sha256": sha256_file(normalized_path),
            "field_status_sha256": sha256_file(field_status_path),
            "sample_count": len(scenario_inputs),
            "paired_group_count": len(groups),
            "scenario_status_counts": dict(sorted(status_counts.items())),
        },
        "scenarios": scenarios,
        "claim_boundary": policy["claim_boundary"],
    }


def write_controlled_scenario_sidecar(path: Path, sidecar: dict[str, Any]) -> None:
    """Persist an already-built sidecar as one stable, reviewable JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
