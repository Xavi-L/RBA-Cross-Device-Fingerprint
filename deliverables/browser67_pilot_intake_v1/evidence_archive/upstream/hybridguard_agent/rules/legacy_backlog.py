"""Reviewed legacy observations; no learned threshold or attack classification."""
from __future__ import annotations

import re

from hybridguard_agent.evidence.paired244 import legacy_field_map


IMPLEMENTATION = "paired244-legacy-backlog-v1"


def evaluate_reviewed_rule(rule, projection):
    """Only explicitly declared, available dependencies enter this function."""
    mapping = legacy_field_map()
    values = projection["features"]

    def get(alias):
        return values[mapping[alias]]

    def result(outcome, reason):
        return {"outcome": outcome, "reason": reason}

    predicate = rule["predicate"]
    params = rule["parameters"]
    if predicate in {"exact_package_policy_v1", "package_release_policy_v1"}:
        package = get("webview_data.app_package_name")
        if not package or package.lower() in {"unknown", "null"}:
            return result("UNKNOWN", "package_identifier_not_observed")
        if package not in params["allowed_packages"]:
            return result("POLICY_MISMATCH", "package_outside_explicit_mtc_policy")
        if predicate == "exact_package_policy_v1":
            return result("MATCH", "package_matches_deployment_policy_not_attestation")
        code, name = get("webview_data.app_version_code"), get("webview_data.app_version_name")
        if code < 1 or int(code) != code or not name or name.lower() in {"unknown", "null"}:
            return result("UNKNOWN", "release_identity_not_interpretable")
        allowed = any(code == release["version_code"] and name == release["version_name"]
                      for release in params["allowed_releases"])
        return result("MATCH" if allowed else "POLICY_MISMATCH",
                      "release_matches_deployment_policy_not_attestation" if allowed
                      else "release_pair_outside_explicit_mtc_policy")
    if predicate == "installer_observation_v1":
        installer = get("webview_data.installer_package")
        if not installer.strip() or installer.lower() in {"unknown", "null"}:
            return result("UNKNOWN", "installer_unavailable_or_collector_error")
        if installer == "manual":
            return result("CONTEXT_OBSERVED", "installer_null_fallback_not_proof_of_manual_install")
        return result("CONTEXT_OBSERVED", "installer_identifier_present_not_proof_of_trust")
    if predicate == "webview_ua_markers_context_v1":
        ua = get("web_data.user_agent")
        if not ua.strip() or ua.lower() in {"unknown", "null"}:
            return result("UNKNOWN", "ua_not_interpretable")
        wv = re.search(params["wv_pattern"], ua, re.IGNORECASE) is not None
        version = re.search(params["version_pattern"], ua, re.IGNORECASE) is not None
        marker = "both" if wv and version else "wv" if wv else "version" if version else "none"
        return result("CONTEXT_OBSERVED", "ua_markers_" + marker + "_not_container_proof")
    if predicate == "development_flags_context_v1":
        flags = {"adb": get("android_native_data.is_adb_enabled"),
                 "debuggable": get("webview_data.is_debuggable"),
                 "cleartext": get("webview_data.is_cleartext_traffic_permitted")}
        enabled = "_".join(name for name, value in flags.items() if value) or "none"
        return result("CONTEXT_OBSERVED", "development_flags_" + enabled + "_not_attack_evidence")
    if predicate == "network_context_v1":
        api = get("android_native_data.os_api_level")
        if api < 1 or int(api) != api:
            return result("UNKNOWN", "android_api_not_interpretable")
        if api < params["collector_caps_min_api"]:
            return result("NOT_APPLICABLE", "collector_legacy_network_flags_are_fallbacks")
        transports = get("android_native_data.active_transport_types")
        if any(not isinstance(t, str) or not t for t in transports):
            return result("UNKNOWN", "invalid_transport_list_elements")
        # These fields share the same collector source. Never treat them as
        # independent evidence or infer absence of VPN from a missing network.
        if not get("android_native_data.active_network_present"):
            return result("CONTEXT_OBSERVED", "no_active_network_observed_not_proof_of_no_vpn")
        if get("android_native_data.has_vpn_transport") or "vpn" in transports:
            return result("CONTEXT_OBSERVED", "vpn_transport_observed_not_attack_evidence")
        return result("CONTEXT_OBSERVED", "network_snapshot_observed_not_identity_evidence")
    raise ValueError("Unsupported reviewed legacy predicate: " + str(predicate))
