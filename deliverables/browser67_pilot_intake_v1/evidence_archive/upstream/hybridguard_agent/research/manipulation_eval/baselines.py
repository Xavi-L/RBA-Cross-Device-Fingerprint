"""Exact historical compiled19 benchmark; no mutation of any frozen catalog."""
import copy

from hybridguard_agent.evidence.paired244 import legacy_field_map
from hybridguard_agent.research.manipulation_eval.contract import ROOT, read_json
from hybridguard_agent.rules.paired244 import load_catalog


def legacy19_catalog():
    original = load_catalog(ROOT / "hybridguard_agent/config/paired244_rule_catalog.v1.json")
    device = read_json(ROOT / "hybridguard_agent/config/deterministic_rule_predicates.v1.json")["compiled_rules"]
    official = {r["relation_id"]: r for r in read_json(ROOT / "hybridguard_agent/config/official_semantic_relations.v1.json")["relations"]
                if r["executable_status"] == "compiled_v1"}
    ids = set(device) | set(official)
    if (len(device), len(official), len(ids)) != (10, 9, 19):
        raise ValueError("Historical compiled19 definition drift")
    catalog = copy.deepcopy(original)
    catalog["rules"] = [r for r in catalog["rules"] if r["rule_id"] in ids]
    mapping = legacy_field_map()
    for r in catalog["rules"]:
        r["historical_paired_disposition"] = r["status"]
        r["status"] = "ACTIVE"
        r["version"] = "formal-legacy19-predicate-preserving-adapter-v1"
        if r["rule_id"] in device:
            r["legacy_spec"] = copy.deepcopy(device[r["rule_id"]])
            r["predicate"] = r["legacy_spec"]["predicate_id"]
            if r["rule_id"] == "CORE-002":
                r["dependencies"] = [mapping["android_native_data.sensor_total_count"], mapping["webview_data.jsbridge_injected"]]
        else:
            r["legacy_relation"] = copy.deepcopy(official[r["rule_id"]])
            r["predicate"] = r["legacy_relation"]["predicate_id"]
            premises = r["legacy_relation"]["premise_fields"]
            if set(premises) - set(mapping) - {"collector_app"}:
                raise ValueError("Unregistered legacy premise")
            # collector_app is the fixed FeatureApp transport constant supplied
            # by legacy_payload, never identity/metadata read from a sample.
            r["dependencies"] = [mapping[f] for f in premises if f in mapping]
    catalog["benchmark_adapter_version"] = "formal-legacy19-predicate-preserving-adapter-v1"
    catalog["benchmark_boundary"] = "Original 10+9 compiled predicates; all run without short circuit. Retired provider relation is diagnostic only. Same external v2 family policy; original short-circuit service is an appendix, never its risk score."
    return catalog
