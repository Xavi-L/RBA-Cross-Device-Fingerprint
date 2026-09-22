"""Focused legacy replay isolation, missingness, and sequence-boundary tests."""

import unittest

from hybridguard_agent.adapters.rule_kb_adapter import load_rule_knowledge_base
from hybridguard_agent.official_semantics.evaluator import load_semantic_catalog
from hybridguard_agent.rules.executor import load_predicate_registry
from hybridguard_agent.scripts.run_mtc_legacy_rule_baseline import (
    aggregate_result, app_payload, category, evaluate_record, finish_aggregate,
    gate_result, new_aggregate, provider_diagnostic,
)
from hybridguard_agent.tests.test_official_semantic_relations import complete_payload


def observation():
    legacy = complete_payload("fixture")
    features = {f"app.{layer}.test_layer.{key}": value for layer in ("android_native_data", "webview_data", "web_data")
                for key, value in legacy[layer].items()}
    features["app.web_data.test_layer.device_memory"] = 0
    return {"sample_id": "fixture", "features": features,
            "field_status": {path: "observed" for path in features},
            "field_quality": {path: "observed_value" for path in features},
            "_p2": {"group_id": "NEVER_MODEL_INPUT", "split": "discovery", "label": "NEVER_LABEL_INPUT"}}


class MtcLegacyBaselineTests(unittest.TestCase):
    def test_payload_excludes_browser_labels_and_p2_controls_but_keeps_status(self):
        row = observation()
        row["features"]["browser.web_data.navigator_layer.user_agent"] = "BROWSER_SECRET"
        path = "app.web_data.test_layer.device_memory"
        row["field_status"][path] = "unsupported_by_os"
        payload, lookup = app_payload(row)
        self.assertNotIn("NEVER", str(payload))
        self.assertNotIn("BROWSER_SECRET", str(payload))
        self.assertEqual(payload["collection_status"]["fields"]["web_data.device_memory"], "unsupported_by_os")
        self.assertEqual(lookup["web_data.device_memory"], path)

    def test_leaf_collision_is_rejected(self):
        row = observation()
        row["features"]["app.web_data.other_layer.device_memory"] = 1
        with self.assertRaisesRegex(ValueError, "collides"):
            app_payload(row)

    def test_gate_respects_sentinel_missing_status_and_valid_false_zero(self):
        row = observation()
        _, lookup = app_payload(row)
        field = "app.web_data.test_layer.device_memory"
        row["field_quality"][field] = "ambiguous_sentinel"
        result = {"outcome": "not_matched", "source_fields": ["web_data.device_memory"]}
        self.assertEqual(gate_result(row, result, lookup)["outcome"], "unknown_availability_gate")
        row["field_quality"][field] = "observed_value"
        self.assertEqual(gate_result(row, result, lookup)["outcome"], "not_matched")
        del row["field_status"][field]
        self.assertEqual(gate_result(row, result, lookup)["outcome"], "unknown_availability_gate")
        result["source_fields"] = ["android_native_data.is_charging"]
        self.assertEqual(gate_result(row, result, lookup)["outcome"], "not_matched")

    def test_legacy_short_circuit_retained_and_independent_diagnostic_explicit(self):
        row = observation()
        row["features"]["app.android_native_data.test_layer.sensor_total_count"] = 2
        result, _ = evaluate_record(row, load_predicate_registry(), load_rule_knowledge_base(), load_semantic_catalog())
        mined = result["device_mined_rule"]
        ordered = {r["rule_id"]: r for r in mined["legacy_ordered"]}
        independent = {r["rule_id"]: r for r in mined["legacy_independent_diagnostic"]}
        self.assertEqual(ordered["CORE-002"]["outcome"], "matched")
        self.assertEqual(ordered["NW-002"]["outcome"], "not_evaluated")
        self.assertEqual(independent["NW-002"]["outcome"], "not_matched")

    def test_unknown_not_counted_as_evaluable_and_repeat_group_not_independent(self):
        agg = new_aggregate()
        for outcome in ("unknown", "unavailable", "not_evaluated", "not_executable", "matched", "matched"):
            aggregate_result(agg, {"outcome": outcome}, "one-group")
        value = finish_aggregate(("discovery", "device_mined_rule", "legacy_ordered", "RULE"), agg)
        self.assertEqual(value["records"], 6)
        self.assertEqual(value["evaluable_records"], 2)
        self.assertEqual(value["evaluable_groups"], 1)
        self.assertEqual(value["groups_by_category"]["violation"], 1)
        self.assertEqual(category("unknown"), "unknown_or_not_evaluated")

    def test_provider_diagnostic_identifies_namespace_not_attack_label(self):
        row = observation()
        for leaf, value in {"webview_provider_package": "vendor.webview", "webview_provider_version": "14.0.0.370",
                            "webview_provider_major": 14, "webview_provider_version_code": 123,
                            "settings_user_agent": row["features"]["app.web_data.test_layer.user_agent"]}.items():
            path = f"app.webview_data.test_layer.{leaf}"
            row["features"][path] = value
            row["field_status"][path] = "observed"
            row["field_quality"][path] = "observed_value"
        result = provider_diagnostic(row)
        self.assertTrue(result["namespace_equality_counterexample"])
        self.assertTrue(result["default_settings_runtime_ua_exact_equal"])
        self.assertNotIn("attack_label", result)
        row["field_status"]["app.webview_data.test_layer.webview_provider_major"] = "runtime_error"
        self.assertFalse(provider_diagnostic(row)["namespace_equality_counterexample"])


if __name__ == "__main__":
    unittest.main()
