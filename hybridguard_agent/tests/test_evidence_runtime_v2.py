"""Focused, dependency-free contract tests for the deterministic runtime."""

from __future__ import annotations

import copy
import unittest

from hybridguard_agent.adapters.official_kb_adapter import load_field_paths, load_official_cards
from hybridguard_agent.adapters.rule_kb_adapter import KnowledgeDriftError, load_rule_cards
from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2, canonical_json
from hybridguard_agent.rules.executor import execute_deterministic_rules, load_predicate_registry
from hybridguard_agent.runtime.service import analyze_payload


WEB_UA_ANDROID_13 = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 8) AppleWebKit/537.36 "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)
WEBVIEW_UA_ANDROID_14 = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
)


def synthetic_payload() -> dict[str, object]:
    """A complete, benign-shaped three-layer input with a deliberate OS mismatch."""
    return {
        "collector_app": "featureapp",
        "schema_version": "expanded-v2.2-status",
        "session_id": "session-secret-not-for-evidence",
        "client_ip": "192.0.2.44",
        "provider": "provider-secret-not-for-evidence",
        "attack_label": "label-secret-not-for-evidence",
        "android_native_data": {
            "os_version": "14",
            "sensor_total_count": 12,
            "device_model": "Pixel 8",
            "is_adb_enabled": False,
            "battery_level_pct": 51,
            "is_charging": False,
            "build_fingerprint": "google/husky/husky:14/UP1A.1:user/release-keys",
            "build_tags": "release-keys",
            "build_type": "user",
        },
        "webview_data": {
            "system_http_agent": WEBVIEW_UA_ANDROID_14,
            "jsbridge_injected": True,
            "is_debuggable": False,
            "is_cleartext_traffic_permitted": False,
            "installer_package": "com.android.vending",
            "default_ua_native": WEB_UA_ANDROID_13,
        },
        "web_data": {
            "user_agent": WEB_UA_ANDROID_13,
            "platform": "Linux armv8l",
            "max_touch_points": 5,
            "timezone_offset": 480,
        },
    }


def result_by_rule(execution: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["rule_id"]): item
        for item in execution["rule_results"]  # type: ignore[index]
    }


class EvidenceRuntimeV2Tests(unittest.TestCase):
    def test_evidence_v2_is_deterministic_and_redacts_raw_provenance(self) -> None:
        first = synthetic_payload()
        second = copy.deepcopy(first)
        second.update(
            {
                "session_id": "different-session-secret",
                "client_ip": "198.51.100.72",
                "provider": "different-provider-secret",
                "attack_label": "different-label-secret",
            }
        )

        first_bundle = build_evidence_bundle_v2(first, sample_id="redaction-test")
        second_bundle = build_evidence_bundle_v2(second, sample_id="redaction-test")
        serialized = canonical_json(first_bundle)

        self.assertEqual(first_bundle["evidence_hash"], second_bundle["evidence_hash"])
        self.assertEqual(
            first_bundle["coverage"]["supported_evidence_groups"],  # type: ignore[index]
            ["cross_layer", "runtime_context"],
        )
        self.assertIn("browser_pair", first_bundle["coverage"]["not_assessed"])  # type: ignore[index]
        for raw_value in (
            "session-secret-not-for-evidence",
            "192.0.2.44",
            "provider-secret-not-for-evidence",
            "label-secret-not-for-evidence",
            WEB_UA_ANDROID_13,
            "google/husky/husky:14/UP1A.1:user/release-keys",
        ):
            self.assertNotIn(raw_value, serialized)

    def test_unavailable_collection_status_never_becomes_a_rule_match(self) -> None:
        payload = synthetic_payload()
        payload["collection_status"] = {
            "fields": {"web_data.user_agent": "unsupported_by_os"}
        }

        bundle = build_evidence_bundle_v2(payload, sample_id="unavailable-test")
        execution = execute_deterministic_rules(bundle)
        rules = result_by_rule(execution)

        self.assertEqual(bundle["derived_facts"]["web.ua_android_major"]["status"], "unavailable")  # type: ignore[index]
        self.assertEqual(rules["NW-002"]["outcome"], "unavailable")
        self.assertEqual(rules["WVWEB-004"]["outcome"], "unavailable")
        self.assertNotIn("NW-002", execution["matched_rule_ids"])
        self.assertNotIn("WVWEB-004", execution["matched_rule_ids"])

    def test_android_webview_linux_x86_platform_is_not_desktop_evidence(self) -> None:
        payload = synthetic_payload()
        payload["web_data"]["platform"] = "Linux x86_64"  # type: ignore[index]

        bundle = build_evidence_bundle_v2(payload, sample_id="android-linux-x86")
        execution = execute_deterministic_rules(bundle)
        rules = result_by_rule(execution)

        self.assertEqual(
            bundle["derived_facts"]["web.platform_class"]["value"],  # type: ignore[index]
            "mobile_or_ambiguous",
        )
        self.assertEqual(rules["NW-006"]["outcome"], "not_matched")

    def test_android_major_mismatch_runs_without_a_calibrated_risk_score(self) -> None:
        output = analyze_payload(synthetic_payload(), sample_id="android-major-mismatch")
        rules = result_by_rule(output["rule_execution"])
        decision = output["decision"]

        self.assertEqual(rules["NW-002"]["outcome"], "matched")
        self.assertIn("NW-002", decision["matched_rule_ids"])
        self.assertEqual(decision["decision_status"], "inconsistency_observed")
        self.assertIsNone(decision["calibrated_risk_score"])
        self.assertNotIn("risk_score", decision)
        self.assertEqual(output["decision_trace"]["verification"]["valid"], True)

    def test_matching_short_circuit_stops_later_predicates_transparently(self) -> None:
        payload = synthetic_payload()
        payload["android_native_data"]["sensor_total_count"] = 2  # type: ignore[index]

        output = analyze_payload(payload, sample_id="short-circuit")
        rules = result_by_rule(output["rule_execution"])
        short_circuit = output["rule_execution"]["short_circuit_status"]

        self.assertEqual(rules["CORE-002"]["outcome"], "matched")
        self.assertEqual(short_circuit["halted_after_rule_id"], "CORE-002")
        self.assertIn("NW-002", short_circuit["skipped_rule_ids"])
        self.assertEqual(rules["NW-002"]["outcome"], "not_evaluated")
        self.assertEqual(output["decision"]["decision_status"], "manual_review_required")
        self.assertTrue(output["decision_trace"]["verification"]["valid"])

    def test_retrieval_explicitly_excludes_future_only_cards(self) -> None:
        output = analyze_payload(synthetic_payload(), sample_id="future-card-boundary")
        _, official_cards = load_official_cards()
        future_ids = {
            card["card_id"] for card in official_cards if card["applicability"] == "future_only"
        }
        retrieved_ids = {card["card_id"] for card in output["context_pack"]["cards"]}

        self.assertTrue(future_ids)
        self.assertEqual(set(output["context_pack"]["excluded_card_ids"]), future_ids)
        self.assertFalse(retrieved_ids & future_ids)
        self.assertTrue(output["decision_trace"]["verification"]["checks"]["future_only_cards_absent"])

    def test_rule_cards_expose_only_current_contract_paths(self) -> None:
        _, cards = load_rule_cards()
        canonical_paths = load_field_paths()

        self.assertTrue(cards)
        self.assertTrue(
            all(set(card["canonical_fields"]) <= canonical_paths for card in cards)
        )
        self.assertTrue(
            any(card["provenance"]["unmapped_legacy_fields"] for card in cards)
        )

    def test_changed_rule_kb_pin_is_rejected_before_execution(self) -> None:
        registry = copy.deepcopy(load_predicate_registry())
        registry["rule_knowledge_base"]["sha256"] = "0" * 64  # type: ignore[index]
        bundle = build_evidence_bundle_v2(synthetic_payload(), sample_id="pin-test")

        with self.assertRaises(KnowledgeDriftError):
            execute_deterministic_rules(bundle, predicate_registry=registry)


if __name__ == "__main__":
    unittest.main()
