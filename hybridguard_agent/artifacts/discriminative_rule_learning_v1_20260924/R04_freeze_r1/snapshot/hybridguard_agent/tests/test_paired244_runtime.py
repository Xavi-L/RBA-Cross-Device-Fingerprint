"""Focused Full244 boundary checks; synthetic records are not attack evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.evidence.paired244 import field_contract, build_paired_evidence
from hybridguard_agent.runtime.paired244 import analyze_paired244_record, paired_runtime_readiness
from hybridguard_agent.runtime.service import analyze_payload
from hybridguard_agent.rules.paired244 import LEGACY_CATALOG, load_catalog
from hybridguard_agent.verification.paired244 import verify_paired_output

N = "app.android_native_data."
H = "app.webview_data."
A = "app.web_data."
B = "browser.web_data."


def fixture():
    features = {p: {"number": 1, "string": "fixture", "boolean": False, "array": []}[kind]
                for p, kind in field_contract().items()}
    ua = "Mozilla/5.0 (Linux; Android 14; Fixture) AppleWebKit/537.36 Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
    features.update({N + "build_fingerprint_layer.os_version": "Android 14",
                     N + "screen_display_layer.screen_resolution_physical": "1080x2400",
                     N + "memory_layer.avail_memory_gb": 2, N + "memory_layer.total_memory_gb": 8,
                     N + "sensor_matrix_layer.sensor_total_count": 2,
                     N + "sensor_matrix_layer.sensor_type_list": [1, 4],
                     N + "sensor_matrix_layer.has_accelerometer": True, N + "sensor_matrix_layer.has_gyroscope": True,
                     H + "bridge_routing_layer.jsbridge_injected": True,
                     H + "kernel_container_layer.default_ua_native": ua,
                     H + "kernel_container_layer.system_http_agent": ua,
                     H + "webview_settings_layer.settings_user_agent": ua,
                     H + "kernel_container_layer.webview_provider_version": "14.0.1.2",
                     H + "kernel_container_layer.webview_provider_major": 14})
    for prefix in (A, B):
        features.update({prefix + "navigator_layer.user_agent": ua,
                         prefix + "navigator_layer.platform": "Linux armv8l",
                         prefix + "navigator_layer.max_touch_points": 5,
                         prefix + "navigator_layer.hardware_concurrency": 8,
                         prefix + "navigator_layer.device_memory": 8,
                         prefix + "screen_layer.screen_resolution_logical": "360x800",
                         prefix + "screen_layer.device_pixel_ratio": 3,
                         prefix + "screen_layer.color_depth": 24, prefix + "screen_layer.pixel_depth": 24})
    return {"record_schema_version": "hybridguard-mtc-observation-v2", "features": features,
            "field_status": {p: "observed" for p in features}, "field_quality": {p: "observed_value" for p in features},
            "pair": {"pair_status": "completed", "browser_pair_id": "pair-fixture", "collection_batch_id": "batch-fixture"},
            "app": {"session_id": "app-session-secret", "receipt_id": "app-receipt", "payload_sha256": "fixture-app-binding"},
            "browser": {"session_id": "browser-session-secret", "receipt_id": "browser-receipt", "payload_sha256": "fixture-browser-binding"}}


def by_rule(output):
    return {r["rule_id"]: r for r in output["rule_execution"]["rule_results"]}


class PairedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(LEGACY_CATALOG)

    def run_record(self, row, view="Full244"):
        return analyze_paired244_record(row, input_view=view, catalog=self.catalog)

    def test_catalog_and_namespaces_are_explicit(self):
        ready = paired_runtime_readiness(catalog=self.catalog)
        self.assertEqual(ready["entry_status_counts"], {"NOT_IMPLEMENTED": 37, "ACTIVE": 48, "RETIRED": 2})
        output = self.run_record(fixture())
        self.assertEqual(len(output["evidence_bundle"]["fields"]), 244)
        self.assertIn("app.web.ua_android_major", output["evidence_bundle"]["derived_facts"])
        self.assertIn("browser.web.ua_android_major", output["evidence_bundle"]["derived_facts"])
        self.assertEqual(len(output["context_pack"]["cards"]), 48)
        cards = {c["rule_id"]: c for c in output["context_pack"]["cards"]}
        self.assertEqual(cards["P3-SCREEN-BROWSER"]["parameters"], {"css_pixel_tolerance": 1.0})
        self.assertEqual(cards["P3-SENSOR-GYROSCOPE"]["parameters"], {"sensor_type": 4})
        self.assertTrue(output["decision_trace"]["verification"]["valid"])
        self.assertEqual(output["decision"]["attack_classification"], "NOT_EVALUATED")
        self.assertIsNone(output["decision"]["calibrated_risk_score"])

    def test_browser_change_reaches_execution_retrieval_verifier_and_trace(self):
        row = fixture()
        initial = self.run_record(row)
        row["features"][B + "navigator_layer.language"] = "en-US"
        changed = self.run_record(row)
        self.assertEqual(by_rule(initial)["P3-X-LANGUAGE"]["outcome"], "MATCH")
        result = by_rule(changed)["P3-X-LANGUAGE"]
        self.assertEqual(result["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(result["used_fields"], [A + "navigator_layer.language", B + "navigator_layer.language"])
        self.assertIn("P3-X-LANGUAGE", changed["decision"]["relation_deviation_rule_ids"])
        self.assertIn(B + "navigator_layer.language", changed["decision_trace"]["citations"]["field_ids"])
        self.assertNotEqual(initial["decision_id"], changed["decision_id"])

    def test_masking_occurs_before_hidden_values_status_quality_and_pair_are_read(self):
        row = fixture()
        before = self.run_record(row, "App177")
        for section in ("features", "field_status", "field_quality"):
            for path in row[section]:
                if path.startswith("browser."):
                    row[section][path] = {"hidden-marker": ["must-not-leak"]}
        row["browser"] = {"attack_label": "hidden-label"}
        row["pair"] = {"pair_status": "broken-hidden-pair"}
        after = self.run_record(row, "App177")
        self.assertEqual(before, after)
        self.assertEqual(len(after["evidence_bundle"]["fields"]), 177)
        self.assertEqual(by_rule(after)["P3-X-LANGUAGE"]["outcome"], "NOT_EVALUATED")
        self.assertFalse(any(p.startswith("browser.") for p in after["context_pack"]["query_fields"]))

    def test_missing_browser_and_unadmitted_pair_cannot_use_browser(self):
        row = fixture()
        for section in ("features", "field_status", "field_quality"):
            row[section] = {p: v for p, v in row[section].items() if p.startswith("app.")}
        output = self.run_record(row)
        self.assertEqual(by_rule(output)["P3-X-TOUCH"]["outcome"], "NOT_EVALUATED")
        for mutation in ("pair", "browser"):
            row = fixture(); row[mutation] = {}
            output = self.run_record(row)
            self.assertEqual(by_rule(output)["P3-X-TOUCH"]["outcome"], "NOT_EVALUATED")
            self.assertEqual(by_rule(output)["P3-COLOR-APP"]["outcome"], "MATCH")

    def test_unavailable_status_sentinel_and_invalid_types_do_not_conflict(self):
        target = B + "navigator_layer.hardware_concurrency"
        cases = [(0, "observed", "observed_value"), (None, "timeout", "source_unavailable"),
                 (True, "observed", "observed_value"), (float("inf"), "observed", "observed_value"),
                 (8, "permission_denied", "source_unavailable"), (8, "observed", "ambiguous_sentinel"),
                 (8, {"invalid_state": True}, "observed_value"), (8, "observed", "invalid_quality")]
        for value, status, quality in cases:
            with self.subTest(value=value, status=status, quality=quality):
                row = fixture();row["features"][target]=value;row["field_status"][target]=status;row["field_quality"][target]=quality
                output = self.run_record(row)
                self.assertEqual(by_rule(output)["P3-X-CORES"]["outcome"], "NOT_EVALUATED")
                self.assertNotIn("P3-X-CORES", output["decision"]["relation_deviation_rule_ids"])

    def test_numeric_semantics_and_valid_zero_false(self):
        row = fixture();row["features"][B + "navigator_layer.hardware_concurrency"] = 8.0
        for prefix in (A, B):row["features"][prefix + "navigator_layer.max_touch_points"] = 0
        output = self.run_record(row)
        self.assertEqual(by_rule(output)["P3-X-CORES"]["outcome"], "MATCH")
        self.assertEqual(by_rule(output)["P3-X-TOUCH"]["outcome"], "MATCH")
        self.assertEqual(by_rule(output)["P3-SENSOR-PRESSURE_SENSOR"]["outcome"], "NOT_APPLICABLE")

    def test_low_sensor_count_cannot_veto_bridge_or_skip_checks(self):
        row = fixture()
        result = self.run_record(row)
        self.assertEqual(by_rule(result)["CORE-002"]["outcome"], "MATCH")
        self.assertEqual(by_rule(result)["P3-X-LANGUAGE"]["outcome"], "MATCH")
        row["features"][H + "bridge_routing_layer.jsbridge_injected"] = False
        result = self.run_record(row)
        self.assertEqual(by_rule(result)["CORE-002"]["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(by_rule(result)["P3-X-LANGUAGE"]["outcome"], "MATCH")
        self.assertFalse(result["rule_execution"]["short_circuit_enabled"])

    def test_provider_namespace_rule_retired_but_parser_self_check_retained(self):
        result = self.run_record(fixture())
        self.assertEqual(by_rule(result)["OFFDER-WEBVIEW-001"]["outcome"], "DISABLED")
        self.assertEqual(by_rule(result)["WVWEB-001"]["outcome"], "DISABLED")
        self.assertEqual(by_rule(result)["P3-PROVIDER-PARSE"]["outcome"], "MATCH")
        self.assertNotIn("P4-RULE-OFFDER-WEBVIEW-001", result["decision_trace"]["citations"]["card_ids"])

    def test_control_plane_metadata_never_changes_evidence_decision_or_retrieval(self):
        row = fixture();before = self.run_record(row)
        row.update(sample_id="attack_active", label_status="verified", manipulation_present=True,
                   scenario_phase="attack_active", provider="secret-provider", profile={"model":"secret-model"},
                   _p2={"split":"reserved_validation", "group_id":"secret-group"})
        self.assertEqual(before, self.run_record(row))
        serialized = str(before)
        self.assertNotIn("app-session-secret", serialized)
        self.assertNotIn("browser-session-secret", serialized)

    def test_verifier_rejects_wrong_surface_fake_outcome_card_or_decision(self):
        original = self.run_record(fixture())
        for mutation in ("field", "outcome", "card", "decision", "evidence"):
            result = copy.deepcopy(original)
            if mutation == "field":
                by_rule(result)["P3-X-LANGUAGE"]["used_fields"] = [A + "navigator_layer.language"]
            elif mutation == "outcome":by_rule(result)["P3-X-LANGUAGE"]["outcome"] = "COUNTEREXAMPLE"
            elif mutation == "card":result["context_pack"]["cards"][0]["source_lane"] = "official_document"
            elif mutation == "decision":result["decision"]["calibrated_risk_score"] = 99
            else:result["evidence_bundle"]["projection"]["features"][A + "navigator_layer.language"] = "tampered"
            verified = verify_paired_output(result["evidence_bundle"], result["rule_execution"], result["context_pack"], result["decision"], self.catalog)
            self.assertFalse(verified["valid"], mutation)

    def test_service_routes_p1_contract_to_new_chain(self):
        result = analyze_payload(fixture(), sample_id="control-identifier-not-in-evidence")
        self.assertEqual(result["response_schema_version"], "agent-runtime-response-v2-paired244")
        self.assertNotIn("control-identifier-not-in-evidence", str(result))

    def test_browser_only_cannot_peek_at_native_or_host(self):
        result = self.run_record(fixture(), "Browser67")
        self.assertEqual(len(result["evidence_bundle"]["fields"]), 67)
        self.assertEqual(by_rule(result)["P3-COLOR-BROWSER"]["outcome"], "MATCH")
        self.assertEqual(by_rule(result)["P3-UA-REDUCED-BROWSER"]["outcome"], "NOT_EVALUATED")
        self.assertEqual(by_rule(result)["CORE-002"]["outcome"], "NOT_EVALUATED")

    def test_acceptance_driver_rejects_reserved_before_any_input_read(self):
        from hybridguard_agent.scripts.run_mtc_p4_runtime import execute
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "reserved stays locked"):
                execute(root / "missing", root / "missing", root / "output", ("reserved_validation",))
            self.assertFalse((root / "output").exists())

    def test_acceptance_failure_is_persisted_and_not_counted_completed(self):
        from hybridguard_agent.scripts.run_mtc_p4_runtime import execute
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, p3, output = root / "plan", root / "p3", root / "output"
            plan.mkdir(); p3.mkdir()
            (p3 / "summary.json").write_text(json.dumps({"p3_status": "COMPLETE", "p2_plan": str(plan)}))
            (p3 / "discovery_results.jsonl").write_text("")
            bad_row = {"sample_id": "invalid-fixture", "record_schema_version": "unsupported"}
            with patch("hybridguard_agent.scripts.run_mtc_p4_runtime.load_split_records", return_value=[bad_row]):
                with self.assertRaisesRegex(RuntimeError, "runtime failures"):
                    execute(plan, p3, output, ("discovery",))
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["p4_status"], "FAILED")
            self.assertEqual(len(summary["runtime_failures"]), 2)
            self.assertEqual(summary["views"], [])


if __name__ == "__main__":
    unittest.main()
