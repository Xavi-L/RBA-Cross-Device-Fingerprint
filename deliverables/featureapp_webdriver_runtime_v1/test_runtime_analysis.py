import copy
from collections import Counter
import unittest

from runtime_analysis import (
    WD_KEYS, campaign_plan, compare_observations, describe_payload,
    payload_issues, raw_tuple_issues, smoke_plan,
)


def raw_observation(**updates):
    return {"api_present": True, "presence_read_status": "observed",
            "value_read_status": "observed", "value_type": "boolean", "boolean_value": False,
            "observer_revision": "app-webdriver-observer-v1", "realm_binding": "featureapp:synthetic:main-frame",
            **updates}


def fixture():
    step = smoke_plan("synthetic")
    release = {"schema_version": "expanded-v2.2-status", "application_id": "com.example.hybridguard.featureapp",
               "version_name": "synthetic", "version_code": 12, "fixed_signal_count": 177,
               "observation_schema_version": "app-web-observations-v1", "observer_revision": "app-webdriver-observer-v1"}
    fields = {f"synthetic.field_{index}": "observed" for index in range(175)}
    fields.update({"web_data.navigator_layer.language": "observed", "web_data.navigator_layer.languages": "observed"})
    payload = {
        "session_id": "synthetic", "collector_app": "featureapp", "schema_version": release["schema_version"],
        "collection_manifest": {"runtime_context": step["runtime_context"], "collection_round": 1,
                                "device_manifest_id": "synthetic-device", "collector_install_id": "synthetic-install",
                                "collector_package": release["application_id"], "collector_version_name": "synthetic",
                                "collector_version_code": 12, "schema_version": release["schema_version"], "android_api": 36,
                                "webview_provider_package": "synthetic-webview", "webview_provider_version": "1"},
        "collection_observations": {"observation_schema_version": release["observation_schema_version"], "webdriver": raw_observation()},
        "collection_status": {"status_schema_version": "field-status-v1", "fixed_signal_count": 177,
                              "fields": fields, "counts": {"observed": 177}},
        "web_data": {"navigator_layer": {"language": "en-US", "languages": ["en-US", "en"]},
                     "automation_surface_layer": {"webdriver": False}},
    }
    return payload, step, {"device_manifest_id": "synthetic-device"}, release, set(fields)


class RuntimeAnalysisTest(unittest.TestCase):
    def test_fixed_plan_has_thirty_campaign_positions_and_one_smoke(self):
        plan = campaign_plan("synthetic")
        self.assertEqual(30, len(plan))
        self.assertEqual(30, len({step["runtime_context"] for step in plan}))
        self.assertEqual({"no_attack": 9, "debug_transport_control": 3, "webdriver": 9, "language": 9},
                         dict(Counter(step["group"] for step in plan)))
        self.assertEqual(1, sum(step["debug_transport_only"] for step in plan))
        self.assertEqual(6, sum(step["configuration"] is not None for step in plan))
        self.assertTrue(all(step["phase"] != "attack" for step in plan if step["group"] in ("no_attack", "debug_transport_control")))
        self.assertNotIn(smoke_plan("synthetic")["runtime_context"], {step["runtime_context"] for step in plan})

    def test_catalog_checks_exact_paths_even_when_count_is_177(self):
        payload, step, config, release, fields = fixture()
        self.assertEqual([], payload_issues(payload, step, config, release, fields))
        payload["collection_status"]["fields"]["wrong.field"] = payload["collection_status"]["fields"].pop("synthetic.field_0")
        self.assertIn("field_status_contract_mismatch", payload_issues(payload, step, config, release, fields))

    def test_legal_unknown_states_remain_unknown_and_accepted(self):
        for observation in (
            raw_observation(api_present=False, value_read_status="not_attempted", value_type=None, boolean_value=None),
            raw_observation(value_type="undefined", boolean_value=None),
            raw_observation(value_read_status="runtime_error", value_type=None, boolean_value=None),
            raw_observation(api_present=None, presence_read_status="runtime_error", value_read_status="not_attempted", value_type=None, boolean_value=None),
        ):
            with self.subTest(observation=observation):
                payload, step, config, release, fields = fixture()
                payload["collection_observations"]["webdriver"] = observation
                self.assertEqual([], raw_tuple_issues(observation))
                self.assertEqual([], payload_issues(payload, step, config, release, fields))
                self.assertEqual("U", describe_payload(payload)["webdriver_value_class"])

    def test_invalid_raw_types_enums_and_contradictions_fail(self):
        for updates in (
            {"api_present": 1}, {"presence_read_status": "timeout"},
            {"value_read_status": "invented"}, {"value_type": "bool"},
            {"boolean_value": "false"}, {"boolean_value": None},
            {"api_present": False}, {"presence_read_status": "runtime_error"},
            {"value_read_status": "runtime_error"}, {"value_type": "string"},
        ):
            with self.subTest(updates=updates):
                payload, step, config, release, fields = fixture()
                payload["collection_observations"]["webdriver"].update(updates)
                self.assertTrue(payload_issues(payload, step, config, release, fields))
                self.assertEqual("FAILED", describe_payload(payload)["webdriver_value_class"])

    def test_missing_raw_keys_are_not_fabricated(self):
        payload, step, config, release, fields = fixture()
        del payload["collection_observations"]["webdriver"]["boolean_value"]
        description = describe_payload(payload)
        self.assertNotIn("boolean_value", description["webdriver_raw"])
        self.assertNotEqual(list(WD_KEYS), description["webdriver_raw_keys_present"])
        self.assertIn("webdriver_raw_keys_missing", payload_issues(payload, step, config, release, fields))

    def test_raw_unknown_tuple_restoration_is_distinct_from_known_false(self):
        payload, *_ = fixture()
        payload["collection_observations"]["webdriver"] = raw_observation(value_type="undefined", boolean_value=None)
        left = describe_payload(payload)
        other = copy.deepcopy(payload)
        other["collection_observations"]["webdriver"]["realm_binding"] = "featureapp:different-session:main-frame"
        comparison = compare_observations(left, describe_payload(other))
        self.assertIsNone(comparison["webdriver_known_values_equal"])
        self.assertTrue(comparison["webdriver_raw_tuple_equal_excluding_realm"])
        self.assertEqual("U", comparison["webdriver_comparison_status"])
        other["web_data"]["navigator_layer"]["languages"] = ["en", "en-US"]
        self.assertFalse(compare_observations(left, describe_payload(other))["language_and_ordered_languages_equal"])


if __name__ == "__main__":
    unittest.main()
