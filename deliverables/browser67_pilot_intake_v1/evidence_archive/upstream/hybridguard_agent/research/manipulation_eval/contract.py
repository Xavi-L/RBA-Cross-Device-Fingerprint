"""Load one complete, explicit S03-R v2 binding; never rebuild or fall back."""
from __future__ import annotations

import json
from pathlib import Path

from hybridguard_agent.evidence.paired244 import field_contract
from hybridguard_agent.research.manipulation_eval import provenance_revision as gates

ROOT = Path(__file__).resolve().parents[3]
VERSION = gates.VERSION
POLICY_VERSION = "formal-manipulation-family-or-v2"
STUDY_VERSION = "formal-manipulation-v1"
CONFIG_REF = "hybridguard_agent/config/formal_manipulation_role_gate_v2"
POLICY_REF = "hybridguard_agent/config/formal_manipulation_policy_v2"
ROLES = {"alert_candidate", "observation_only", "context_only", "collector_consistency", "deployment_policy"}
JSON_CONFIGS = ("applicability_policy", "decision_roles", "research_scope", "source_conditions",
                "family_bindings", "precondition_classification")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Nonfinite JSON number")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def read_json(path):
    return strict_json(Path(path).read_text())


def read_jsonl(path):
    return [strict_json(line) for line in Path(path).read_text().splitlines() if line.strip()]


def keyed(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate binding: " + key)
    return result


def load_contract(*, contract_version, config_dir, policy_path):
    if contract_version != VERSION or config_dir is None or policy_path is None:
        raise ValueError("Explicit complete S03-R v2 contract and policy required")
    directory = Path(config_dir).resolve()
    docs = {name: read_json(directory / (name + ".json")) for name in JSON_CONFIGS}
    for name, doc in docs.items():
        version_key = "version" if name == "source_conditions" else "contract_version"
        if doc.get(version_key) != VERSION:
            raise ValueError("Mixed or missing contract version: " + name)
    required_rows = {
        "decision_roles": ("roles", {"rule_id", "provenance_group", "decision_family", "original_evidence_family", "old_decision_role", "decision_role", "role_changed", "reviewed_candidate", "rationale", "basis", "known_legal_counterexamples", "research_scope_id", "attribution_certainty", "attribution_unknown_does_not_veto_relation_or_eligible_risk", "old_precondition_classification"}),
        "applicability_policy": ("scopes", {"rule_id", "provenance_group", "decision_family", "original_evidence_family", "applicability_id", "profile", "decision_role", "relation_required_fields", "additional_risk_required_fields", "relation_applicability", "risk_candidate_eligibility", "attribution_certainty", "measurement_requirements", "relation_conditions", "risk_conditions", "legacy_scope_authority", "precondition_classification", "legacy_observation_scope"}),
        "family_bindings": ("families", {"decision_family", "rule_ids", "provenance_groups", "original_evidence_families", "candidate_ids"}),
        "precondition_classification": ("classifications", {"rule_id", "old_condition", "measurement_requirements", "risk_scope_requirements", "attribution_only", "insufficient_risk_basis"}),
    }
    for name, (key, required) in required_rows.items():
        if not isinstance(docs[name].get(key), list) or any(not isinstance(row, dict) or set(row) != required for row in docs[name][key]):
            raise ValueError("Incomplete or mixed configuration rows: " + name)
    policy = read_json(policy_path)
    if (policy.get("policy_version") != POLICY_VERSION or policy.get("contract_version") != VERSION
            or policy.get("role_gate_config_ref") != CONFIG_REF or policy.get("threshold") != 1
            or type(policy.get("threshold")) is not int or policy.get("aggregation") != "distinct_family_OR"
            or policy.get("calibrated_attack_probability") is not None
            or policy.get("research_scope_id") != gates.SCOPE_ID):
        raise ValueError("Policy/config binding conflict; no fallback or tuning")
    if docs["research_scope"] != gates.RESEARCH_SCOPE:
        raise ValueError("Research scope differs from reviewed v2 executable contract")
    if docs["applicability_policy"]["common_gate_ids"] != gates.COMMON_GATES:
        raise ValueError("Common gate version mismatch")
    from hybridguard_agent.rules.paired244 import load_catalog
    catalog = load_catalog(ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json")
    active = {r["rule_id"]: r for r in catalog["rules"] if r["status"] == "ACTIVE"}
    bindings = keyed(read_jsonl(directory / "source_bindings.jsonl"), "rule_id")
    roles = keyed(docs["decision_roles"]["roles"], "rule_id")
    scopes = keyed(docs["applicability_policy"]["scopes"], "rule_id")
    families = keyed(docs["family_bindings"]["families"], "decision_family")
    if not (len(active) == 57 and set(active) == set(bindings) == set(roles) == set(scopes)):
        raise ValueError("Incomplete ACTIVE binding")
    known = set(field_contract())
    for rid, rule in active.items():
        b, r, s = bindings[rid], roles[rid], scopes[rid]
        if b["catalog_version"] != catalog["catalog_version"] or any(
                b[k] != rule.get(k, {}) for k in ("predicate", "parameters", "dependencies")):
            raise ValueError("Predicate binding mismatch: " + rid)
        for k in ("provenance_group", "decision_family", "original_evidence_family"):
            if not b[k] == r[k] == s[k]:
                raise ValueError("Role/scope/source/family mismatch: " + rid)
        if (r["decision_role"] not in ROLES or r["decision_role"] != s["decision_role"]
                or r["research_scope_id"] != gates.SCOPE_ID or r["attribution_certainty"] != "UNKNOWN"
                or s["relation_required_fields"] != b["dependencies"]
                or not set(s["additional_risk_required_fields"]) <= known):
            raise ValueError("Invalid role/scope: " + rid)
        if rid in gates.REVIEWED:
            role, profile, _ = gates.REVIEWED[rid]
            refs = ([gates.DEFAULT_UA, gates.SETTINGS_UA] if profile in {"app_model", "app_os"}
                    else [gates.DEFAULT_UA] if profile == "system_model" else [])
            if (r["decision_role"], s["profile"], s["additional_risk_required_fields"]) != (role, profile, refs):
                raise ValueError("Reviewed v2 candidate changed: " + rid)
        elif r["decision_role"] == "alert_candidate" or not s["profile"].startswith("retained:"):
            raise ValueError("Unreviewed promotion: " + rid)
        if b["original_evidence_family"] != rule["evidence_family"]:
            raise ValueError("Original family changed")
    all_members = [rid for f in families.values() for rid in f["rule_ids"]]
    if len(all_members) != 57 or set(all_members) != set(active):
        raise ValueError("Family membership incomplete or duplicated")
    for fid, family in families.items():
        members = {rid for rid, b in bindings.items() if b["decision_family"] == fid}
        if set(family["rule_ids"]) != members or set(family["candidate_ids"]) != {
                rid for rid in members if roles[rid]["decision_role"] == "alert_candidate"}:
            raise ValueError("Family candidate mapping mismatch")
    source = docs["source_conditions"]
    groups = {g: sorted(rid for rid, r in roles.items() if r["provenance_group"] == g) for g in ("E", "O_u", "H", "C")}
    if groups != source["groups"]:
        raise ValueError("Source ID sets mismatch")
    conditions = keyed(source["conditions"], "condition_id")
    if set(conditions) != {f"SRC-{i:03b}" for i in range(8)}:
        raise ValueError("Eight unique conditions required")
    for cid, c in conditions.items():
        included = ["C"] + [g for bit, g in zip(cid[-3:], ("O_u", "H", "E")) if bit == "1"]
        expected = sorted(rid for g in included for rid in groups[g])
        if (c["rule_ids"] != expected or c["rule_count"] != len(expected)
                or c["included_groups"] != included or c["common_C_ids"] != groups["C"]
                or c["common_gate_ids"] != gates.COMMON_GATES or c["applicability_policy_version"] != VERSION
                or c["research_scope_id"] != gates.SCOPE_ID):
            raise ValueError("Source condition/gate mismatch: " + cid)
    if source["four_source_mapping"] != {"C": "SRC-000", "B0": "SRC-000", "E": "SRC-001", "O": "SRC-110", "EO": "SRC-111"}:
        raise ValueError("Four/eight source aliases mismatch")
    if len(docs["precondition_classification"]["classifications"]) != 16:
        raise ValueError("Incomplete precondition ledger")
    return {"version": VERSION, "policy": policy, "catalog": catalog, "roles": roles, "scopes": scopes,
            "bindings": bindings, "families": families, "conditions": conditions, "documents": docs,
            "config_dir": str(directory)}
