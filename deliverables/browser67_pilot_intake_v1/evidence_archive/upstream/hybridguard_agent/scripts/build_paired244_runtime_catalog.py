#!/usr/bin/env python3
"""Package frozen P3 checks and explicit legacy dispositions; never mine rules."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2
from hybridguard_agent.evidence.paired244 import field_contract, legacy_field_map


def build_catalog(p3_dir):
    p3 = json.loads((p3_dir / "rule_catalog.v2.json").read_text())
    if p3.get("catalog_version") != "mtc-research-rule-catalog-v2" or p3.get("risk_scoring_allowed") is not False:
        raise ValueError("Expected frozen, uncalibrated P3 research catalog")
    kb = json.loads((ROOT / "scoring/rule_knowledge_base.json").read_text())
    registry = json.loads((ROOT / "hybridguard_agent/config/deterministic_rule_predicates.v1.json").read_text())
    semantics = json.loads((ROOT / "hybridguard_agent/config/official_semantic_relations.v1.json").read_text())
    mapping = legacy_field_map()
    facts = build_evidence_bundle_v2({"collector_app": "featureapp"})["derived_facts"]
    entries = []
    for rule in kb["rules"]:
        rid = rule["id"]
        spec = registry["compiled_rules"].get(rid)
        status = "ACTIVE" if spec else "NOT_IMPLEMENTED"
        reason = "legacy_predicate_retained_without_attack_claim" if spec else "legacy_natural_language_not_executable"
        if rid == "WVWEB-001":
            status, reason = "RETIRED", "package_version_namespace_is_not_chromium_version"
        dependencies = sorted({mapping[f] for fid in spec["fact_ids"] for f in facts[fid]["source_fields"]}) if spec else []
        entry = {"rule_id": rid, "title": rule["name"], "origin": "legacy_device",
                 "source_lane": "device_mined_rule", "status": status, "disposition_reason": reason,
                 "dependencies": dependencies, "legacy_spec": spec,
                 "predicate": spec["predicate_id"] if spec else None,
                 "version": "paired244-legacy-adapter-v1", "official_source_ids": [],
                 "limitations": rule.get("tolerance", "")}
        if rid == "CORE-002":
            entry.update(predicate="featureapp_bridge_only_v2", dependencies=[mapping["webview_data.jsbridge_injected"]],
                         disposition_reason="sensor_count_branch_removed_no_short_circuit",
                         title="FeatureApp bridge presence; low sensor count is context only",
                         limitations="Bridge absence is a collection/integrity observation, never an attack label. Sensor count does not cause rejection.")
        entries.append(entry)
    for relation in semantics["relations"]:
        rid = relation["relation_id"]
        compiled = relation["executable_status"] == "compiled_v1"
        status = "ACTIVE" if compiled else "NOT_IMPLEMENTED"
        reason = "legacy_relation_retained_without_attack_claim" if compiled else "legacy_relation_not_executable"
        if rid == "OFFDER-WEBVIEW-001":
            status, reason = "RETIRED", "package_version_namespace_is_not_chromium_version"
        entries.append({"rule_id": rid, "title": relation["name"], "origin": "legacy_official",
                        "source_lane": "official_derived_semantic_rule", "status": status, "disposition_reason": reason,
                        "dependencies": [mapping[p] for p in relation["premise_fields"] if p in mapping] if compiled else [],
                        "predicate": relation["predicate_id"], "legacy_relation": relation,
                        "version": "paired244-legacy-adapter-v1", "official_source_ids": [],
                        "legacy_official_source_ids": relation["official_source_refs"],
                        "limitations": relation["tolerance"]})
    for candidate in p3["rules"]:
        entry = {k: candidate[k] for k in ("dependencies", "predicate", "parameters", "version", "source_lane",
                                           "limitations", "official_source_ids", "family", "admission_mode", "scope")}
        entry.update(rule_id=candidate["candidate_id"], title=candidate["candidate_id"], origin="p3_research",
                     status="ACTIVE", disposition_reason=candidate["disposition"], empirical_selection_applied=True,
                     p3_support={s: {k: candidate[s][k] for k in ("applicable_groups", "applicable_manufacturers", "group_outcomes")}
                                 for s in ("discovery", "development")})
        entries.append(entry)
    overlap = {
        "app_os": ["NW-002", "OFFDER-OS-001"], "host_os": ["NVW-002", "OFFDER-OS-002"],
        "app_surface": ["NW-006", "OFFDER-UA-001", "WVWEB-004"],
        "mobile_touch": ["NW-007", "OFFDER-TOUCH-001"], "featureapp_bridge": ["CORE-002", "OFFDER-BRIDGE-001"],
        "debug_cleartext": ["NVW-005", "OFFDER-DEVCONFIG-001"],
        "host_ua": ["OFFDER-UA-002", "P3-UA-DEFAULT", "P3-UA-SETTINGS"],
        "screen_geometry": ["NW-003", "OFFDER-DISPLAY-001", "P3-SCREEN-APP", "P3-SCREEN-BROWSER", "P3-X-DPR", "P3-X-SCREEN-SIZE"],
    }
    for e in entries:
        e["evidence_family"] = next((family for family, ids in overlap.items() if e["rule_id"] in ids),
                                    "sensor_structure" if e["rule_id"].startswith("P3-SENSOR-") else e["rule_id"])
        e["standalone_attack_decision"] = False
        e["risk_weight"] = None
        if not set(e["dependencies"]) <= set(field_contract()):
            raise ValueError("Unresolved runtime dependency")
    return {"catalog_version": "paired244-runtime-catalog-v1", "source_p3_run": str(p3_dir.relative_to(ROOT)),
            "source_record_version": "hybridguard-mtc-observation-v2", "rules": entries,
            "legacy_kb_binding": registry["rule_knowledge_base"],
            "execution_policy": "Evaluate all ACTIVE checks independently; no short circuit, risk weights or attack/safety label. Similar evidence families are not independent votes.",
            "overlap_policy": "Preserve source lanes and differing availability/applicability semantics; do not merge merely similar predicates. Report check counts, not independent-rule counts.",
            "reserved_validation": "LOCKED", "detection_metrics": "NOT_EVALUATED", "p4_status": "VERSIONED_EXECUTION_ONLY"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p3-dir", type=Path, default=ROOT / "hybridguard_agent/artifacts/mtc_p3_discovery_20260922_r2")
    parser.add_argument("--output", type=Path, default=ROOT / "hybridguard_agent/config/paired244_rule_catalog.v1.json")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refuse to overwrite a versioned runtime catalog")
    catalog = build_catalog(args.p3_dir.resolve())
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    from collections import Counter
    print(dict(Counter(r["status"] for r in catalog["rules"])))
