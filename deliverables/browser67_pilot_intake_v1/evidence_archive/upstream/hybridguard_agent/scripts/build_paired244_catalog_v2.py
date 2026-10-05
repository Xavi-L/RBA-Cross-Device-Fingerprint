#!/usr/bin/env python3
"""Apply the 37-item review without changing frozen P3/P4 v1 predicates."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.evidence.paired244 import field_contract, legacy_field_map
from hybridguard_agent.rules.legacy_backlog import IMPLEMENTATION

CONFIG = ROOT / "hybridguard_agent/config"


def build_catalog_v2():
    read = lambda name: json.loads((CONFIG / name).read_text(encoding="utf-8"))
    catalog = copy.deepcopy(read("paired244_rule_catalog.v1.json"))
    review = read("paired244_legacy_review.v1.json")
    reviews = {r["rule_id"]: r for r in review["entries"]}
    expected = {r["rule_id"] for r in catalog["rules"] if r["status"] == "NOT_IMPLEMENTED"}
    if len(reviews) != 37 or len(review["entries"]) != 37 or set(reviews) != expected:
        raise ValueError("Review must account for every previous unimplemented entry exactly once")
    mapping = legacy_field_map()
    deployment = {"policy_version": "mtc-featureapp-deployment-policy-v1",
                  "allowed_packages": ["com.example.hybridguard.featureapp"],
                  "allowed_releases": [{"version_code": r["featureapp_version_code"],
                                        "version_name": r["featureapp_version_name"]}
                                       for r in read("mtc_paired244_sources.v2.json")["allowed_releases"]],
                  "basis": ["android_app/HybridGuard/featureapp/build.gradle.kts:applicationId",
                            "hybridguard_agent/config/mtc_paired244_sources.v2.json:allowed_releases"],
                  "scope": "Frozen MTC FeatureApp deployment only; fingerprint claims are not package attestation.",
                  "installer_policy": "Context only; no installer is an automatic trusted/hostile verdict."}
    specs = {
        "NVW-003": ("exact_package_policy_v1", ["webview_data.app_package_name"],
                    "project_deployment_policy", "deployment_identity", deployment,
                    "FeatureApp 包名符合固定 MTC 部署配置", []),
        "NVW-004": ("installer_observation_v1", ["webview_data.installer_package"],
                    "collector_context", "installer_context", {},
                    "安装器观测及采集回退上下文", ["android-install-source-current"]),
        "WVWEB-002": ("webview_ua_markers_context_v1", ["web_data.user_agent"],
                      "collector_context", "app_surface",
                      {"wv_pattern": r";\s*wv\b", "version_pattern": r"\bVersion/4\.0\b"},
                      "App Web UA 标记上下文", ["android-websettings-current"]),
        "TOL-001": ("development_flags_context_v1", ["android_native_data.is_adb_enabled",
                     "webview_data.is_debuggable", "webview_data.is_cleartext_traffic_permitted"],
                    "collector_context", "debug_cleartext", {}, "ADB 与宿主开发配置上下文", []),
        "OFFDER-PACKAGE-001": ("package_release_policy_v1", ["webview_data.app_package_name",
                               "webview_data.app_version_code", "webview_data.app_version_name"],
                               "project_deployment_policy", "deployment_identity", deployment,
                               "FeatureApp 包名及版本配对符合固定 MTC 部署配置", []),
        "OFFDER-NET-001": ("network_context_v1", ["android_native_data.os_api_level",
                           "android_native_data.active_network_present", "android_native_data.active_transport_types",
                           "android_native_data.has_vpn_transport", "android_native_data.has_wifi_transport",
                           "android_native_data.has_cellular_transport"],
                           "official_derived_semantic_rule", "network_context", {"collector_caps_min_api": 23},
                           "有采集适用性限制的网络与 VPN 上下文", ["android-network-capabilities-current"]),
    }
    active_reviews = {rid for rid, r in reviews.items() if r["status"] == "ACTIVE"}
    if active_reviews != set(specs):
        raise ValueError("Executable contracts differ from the reviewed activation list")
    for rule in catalog["rules"]:
        entry = reviews.get(rule["rule_id"])
        if entry is None:
            continue  # Preserve all 48 original executable entries byte-for-byte as data.
        rule.update(status=entry["status"], disposition_reason=entry["reason"],
                    version="paired244-legacy-review-v1", review_version=review["review_version"],
                    next_action_and_acceptance=entry["next_action_and_acceptance"],
                    related_or_replacement_ids=entry["related_or_replacement_ids"],
                    uncollected_or_derived_fields=entry["uncollected_or_derived_fields"],
                    dependencies=[p for p in entry["required_fields"] if p in field_contract()])
        if rule["rule_id"] not in specs:
            continue
        predicate, deps, lane, family, params, title, sources = specs[rule["rule_id"]]
        rule.update(implementation=IMPLEMENTATION, predicate=predicate,
                    dependencies=[mapping[p] for p in deps], parameters=copy.deepcopy(params),
                    original_source_lane=rule["source_lane"], source_lane=lane,
                    evidence_family=family, title=title, official_source_ids=sources,
                    limitations=entry["reason"] + " " + entry["next_action_and_acceptance"],
                    admission_mode="reviewed_policy_or_context_only_not_empirical_rule",
                    legacy_conclusion_reused=False)
    catalog.update(catalog_version="paired244-runtime-catalog-v2",
                   previous_catalog_version="paired244-runtime-catalog-v1",
                   review_version=review["review_version"], deployment_policy=deployment,
                   review_scope=review["protocol"], p4_status="BACKLOG_FIRST_BATCH_ONLY")
    browser = read("paired244_browser_relations.v1.json")
    browser.update(catalog_version=catalog["catalog_version"], policy_version="paired244-browser-relation-policy-v2")
    return catalog, browser


if __name__ == "__main__":
    targets = [CONFIG / "paired244_rule_catalog.v2.json", CONFIG / "paired244_browser_relations.v2.json"]
    if any(p.exists() for p in targets):
        raise ValueError("Do not overwrite a versioned catalog or policy")
    for path, value in zip(targets, build_catalog_v2()):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
