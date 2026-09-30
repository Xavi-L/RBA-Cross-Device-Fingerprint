"""Synthetic-only transfer checks; no saved data, candidates, fit or prediction."""
from copy import deepcopy
import unittest

from hybridguard_agent.research.rule_semantics_revision_v1.contracts import SourceBinding
from hybridguard_agent.research.rule_semantics_runtime_input import (
    BINDING_SCOPES_BY_MODE, OBSERVATION_SCHEMA, OBSERVER_REVISION, RAW_SCHEMA,
    RuntimeInputError, adapt_runtime_payload,
)

SESSION = "SYNTHETIC-session-1"
REALM = f"featureapp:{SESSION}:main-frame"
LANG = "app.web_data.navigator_layer.language"
LANGS = "app.web_data.navigator_layer.languages"
WD = "app.web_data.automation_surface_layer.webdriver"


def bindings():
    result = {mode: SourceBinding("SYNTHETIC-external-registration", scope)
              for mode, scope in BINDING_SCOPES_BY_MODE.items()}
    result["WEBDRIVER_RAW"] = SourceBinding("SYNTHETIC-external-registration",
        "webdriver_raw_observation_v1", observer_revision=OBSERVER_REVISION, realm_binding=REALM)
    return result


def payload():
    return {
        "collector_app": "featureapp", "schema_version": RAW_SCHEMA, "session_id": SESSION,
        "web_data": {"navigator_layer": {"language": "en-US", "languages": ["fr-FR", "en-US"]},
                     "automation_surface_layer": {"webdriver": False}},
        "collection_status": {"status_schema_version": "field-status-v1", "fields": {
            field.removeprefix("app."): "observed" for field in (LANG, LANGS, WD)}},
        "collection_observations": {"observation_schema_version": OBSERVATION_SCHEMA, "webdriver": {
            "api_present": True, "presence_read_status": "observed", "value_read_status": "observed",
            "value_type": "boolean", "boolean_value": False,
            "observer_revision": OBSERVER_REVISION, "realm_binding": REALM}},
    }


def adapt(raw=None, supplied=None):
    return adapt_runtime_payload(payload() if raw is None else raw, expected_session_id=SESSION,
                                 source_bindings=bindings() if supplied is None else supplied)


def raw_tuple(result):
    return result.payload["web_data"]["automation_surface_layer"]["webdriver_observation"]


class RuntimeInputTests(unittest.TestCase):
    def test_exact_mapping_and_deep_copy_without_metadata_leak(self):
        raw = payload()
        raw.update({"label": "attack", "source_binding": {"trusted": True}, "phase": "attack"})
        raw["collection_observations"]["webdriver"]["extra_page_claim"] = "trusted"
        before = deepcopy(raw)
        result = adapt(raw)
        self.assertEqual(raw, before)
        self.assertEqual(set(result.payload), {"record_schema_version", "features", "field_status", "field_quality", "web_data"})
        self.assertEqual(set(result.payload["features"]), {LANG, LANGS, WD})
        self.assertIs(raw_tuple(result)["boolean_value"], False)
        self.assertNotIn("extra_page_claim", raw_tuple(result))
        language, external = result.input_for("LANGUAGE")
        self.assertEqual(external.source_contract_id, "SYNTHETIC-external-registration")
        self.assertEqual(language["features"][LANGS], ["fr-FR", "en-US"])
        language["features"][LANGS].append("de-DE")
        raw["web_data"]["navigator_layer"]["languages"][0] = "zh-CN"
        raw["collection_observations"]["webdriver"]["boolean_value"] = True
        self.assertEqual(result.payload["features"][LANGS], ["fr-FR", "en-US"])
        self.assertIs(raw_tuple(result)["boolean_value"], False)

    def test_explicit_status_quality_policy_and_missing_status_not_invented(self):
        raw = payload()
        fields = raw["collection_status"]["fields"]
        fields[LANG.removeprefix("app.")] = "runtime_error"
        del fields[LANGS.removeprefix("app.")]
        result = adapt(raw).payload
        self.assertEqual(result["features"][LANG], "en-US")
        self.assertEqual(result["field_status"][LANG], "runtime_error")
        self.assertEqual(result["field_quality"][LANG], "source_unavailable")
        self.assertNotIn(LANGS, result["field_status"])
        self.assertNotIn(LANGS, result["field_quality"])
        self.assertEqual(result["field_quality"][WD], "observed_value")
        fields[WD.removeprefix("app.")] = "pretend_observed"
        result = adapt(raw).payload
        self.assertEqual(result["field_status"][WD], "pretend_observed")
        self.assertNotIn(WD, result["field_quality"])

    def test_missing_raw_never_recovers_false_from_legacy(self):
        raw = payload()
        del raw["collection_observations"]
        result = adapt(raw)
        legacy, _ = result.input_for("WEBDRIVER_LEGACY")
        self.assertIs(legacy["features"][WD], False)
        self.assertNotIn("web_data", result.payload)
        with self.assertRaises(RuntimeInputError) as caught:
            result.input_for("WEBDRIVER_RAW")
        self.assertEqual(caught.exception.state, "U")

    def test_missing_nonboolean_read_error_and_contradiction_remain_unrepaired(self):
        cases = [
            {"api_present": False, "value_read_status": "not_attempted", "value_type": None, "boolean_value": None},
            {"value_type": "undefined", "boolean_value": None},
            {"value_type": "string", "boolean_value": None},
            {"value_read_status": "runtime_error", "value_type": None, "boolean_value": None},
            {"presence_read_status": "runtime_error", "api_present": None,
             "value_read_status": "not_attempted", "value_type": None, "boolean_value": None},
            {"value_type": "string", "boolean_value": False},
        ]
        for change in cases:
            with self.subTest(change=change):
                raw = payload()
                raw["collection_observations"]["webdriver"].update(change)
                result = adapt(raw)
                actual, _ = result.input_for("WEBDRIVER_RAW")
                self.assertEqual(actual["web_data"]["automation_surface_layer"]["webdriver_observation"],
                                 raw["collection_observations"]["webdriver"])
        raw = payload()
        del raw["collection_observations"]["webdriver"]["boolean_value"]
        self.assertNotIn("boolean_value", raw_tuple(adapt(raw)))

    def test_payload_cannot_supply_own_binding(self):
        raw = payload()
        raw["source_bindings"] = bindings()
        raw["same_context"] = True
        result = adapt(raw, supplied={})
        for mode in BINDING_SCOPES_BY_MODE:
            with self.subTest(mode=mode), self.assertRaises(RuntimeInputError) as caught:
                result.input_for(mode)
            self.assertEqual(caught.exception.state, "U")
        supplied = bindings()
        supplied["WEBDRIVER_RAW"] = vars(supplied["WEBDRIVER_RAW"])
        with self.assertRaises(RuntimeInputError):
            adapt(raw, supplied).input_for("WEBDRIVER_RAW")

    def test_external_session_and_binding_realm_are_checked_before_release(self):
        raw = payload()
        raw["session_id"] = "SYNTHETIC-other-session"
        result = adapt(raw)
        for mode in BINDING_SCOPES_BY_MODE:
            with self.subTest(mode=mode), self.assertRaises(RuntimeInputError) as caught:
                result.input_for(mode)
            self.assertEqual(caught.exception.state, "FAILED")
        for revision, realm in ((OBSERVER_REVISION, "featureapp:OTHER:main-frame"),
                                ("unknown-observer", REALM)):
            with self.subTest(revision=revision, realm=realm):
                supplied = bindings()
                supplied["WEBDRIVER_RAW"] = SourceBinding("SYNTHETIC-external-registration",
                    "webdriver_raw_observation_v1", observer_revision=revision, realm_binding=realm)
                result = adapt(supplied=supplied)
                with self.assertRaises(RuntimeInputError) as caught:
                    result.input_for("WEBDRIVER_RAW")
                self.assertEqual(caught.exception.state, "FAILED")

    def test_unmatched_payload_observer_or_realm_fails_registration(self):
        for key in ("observer_revision", "realm_binding"):
            with self.subTest(key=key):
                raw = payload()
                raw["collection_observations"]["webdriver"][key] = "different"
                result = adapt(raw)
                with self.assertRaises(RuntimeInputError) as caught:
                    result.input_for("WEBDRIVER_RAW")
                self.assertEqual(caught.exception.state, "FAILED")
                self.assertEqual(caught.exception.to_dict()["reason"], "RUNTIME_OBSERVATION_IDENTITY_MISMATCH")
                self.assertEqual(raw_tuple(result)[key], "different")

    def test_schema_and_container_failures_do_not_turn_into_missing(self):
        cases = [("schema_version", "older", "LANGUAGE"),
                 ("collection_observations", [], "WEBDRIVER_RAW"),
                 ("collection_status", [], "LANGUAGE"),
                 ("web_data", [], "LANGUAGE")]
        for key, value, mode in cases:
            with self.subTest(key=key):
                raw = payload()
                raw[key] = value
                with self.assertRaises(RuntimeInputError) as caught:
                    adapt(raw).input_for(mode)
                self.assertEqual(caught.exception.state, "FAILED")
        raw = payload()
        raw["collection_observations"]["observation_schema_version"] = "future"
        with self.assertRaises(RuntimeInputError):
            adapt(raw).input_for("WEBDRIVER_RAW")


if __name__ == "__main__":
    unittest.main()
