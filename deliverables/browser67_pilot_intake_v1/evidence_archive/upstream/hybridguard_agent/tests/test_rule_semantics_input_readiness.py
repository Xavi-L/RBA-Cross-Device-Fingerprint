"""Synthetic structural-transfer tests; no historical files or candidate calls."""

from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from hybridguard_agent.research.rule_semantics_input_readiness import (
    BINDING_SCOPES_BY_MODE, FIELDS, INPUT_STATUSES, LANGUAGE_FIELD, LANGUAGES_FIELD,
    MODES, SOURCE_STATUSES, WEBDRIVER_FIELD, inspect_inputs, make_source_binding,
    project_payload, readiness,
)


def synthetic_payload() -> dict:
    values = {LANGUAGE_FIELD: "en-US", LANGUAGES_FIELD: ["fr-FR", "en-US", None, 7],
              WEBDRIVER_FIELD: False}
    return {"features": values,
            "field_status": {key: "observed" for key in values},
            "field_quality": {key: "observed_value" for key in values}}


def synthetic_raw() -> dict:
    return {"api_present": True, "presence_read_status": "observed",
            "value_read_status": "observed", "value_type": "boolean",
            "boolean_value": False, "observer_revision": "SYNTHETIC-OBSERVER-v1",
            "realm_binding": "SYNTHETIC-REALM-1"}


def with_raw(observation: object) -> dict:
    return {"web_data": {"automation_surface_layer": {"webdriver_observation": observation}}}


def synthetic_registration(mode: str, source_status: str = "SUPPORTED_BY_EXISTING_LINEAGE") -> dict:
    return {"source_group_id": "SYNTHETIC-SOURCE-GROUP-1", "modes": {
        mode: {"source_status": source_status,
               "binding_scope": BINDING_SCOPES_BY_MODE[mode],
               "evidence_refs": ["SYNTHETIC-EVIDENCE-1"]}}}


class InputProjectionTests(unittest.TestCase):
    def test_language_projection_preserves_values_types_order_and_states(self):
        payload = synthetic_payload()
        projected = project_payload(payload, "LANGUAGE")
        self.assertEqual(projected["record_schema_version"], "rsr-input-v1")
        for section in ("features", "field_status", "field_quality"):
            self.assertEqual(projected[section], {key: payload[section][key] for key in FIELDS["LANGUAGE"]})
        self.assertEqual(projected["features"][LANGUAGES_FIELD], ["fr-FR", "en-US", None, 7])
        self.assertNotIn(WEBDRIVER_FIELD, projected["features"])

    def test_legacy_false_is_complete_and_not_coerced(self):
        payload = synthetic_payload()
        projected = project_payload(payload, "WEBDRIVER_LEGACY")
        self.assertIs(projected["features"][WEBDRIVER_FIELD], False)
        report = inspect_inputs(payload, "WEBDRIVER_LEGACY")
        self.assertEqual(report["input_status"], "COMPLETE")
        self.assertEqual(report["reasons"], [])
        self.assertIn("LEGACY_STRICT_TRUE_PROJECTION_CANNOT_RECOVER_RAW_OBSERVATION", report["limitations"])

    def test_nonobserved_source_state_remains_complete_structure(self):
        payload = synthetic_payload()
        payload["field_status"][WEBDRIVER_FIELD] = "runtime_error"
        payload["field_quality"][WEBDRIVER_FIELD] = "source_unavailable"
        projected = project_payload(payload, "WEBDRIVER_LEGACY")
        self.assertEqual(projected["field_status"][WEBDRIVER_FIELD], "runtime_error")
        self.assertEqual(projected["field_quality"][WEBDRIVER_FIELD], "source_unavailable")
        report = inspect_inputs(payload, "WEBDRIVER_LEGACY")
        self.assertEqual(report["input_status"], "COMPLETE")
        self.assertEqual(report["availability"][WEBDRIVER_FIELD], "SOURCE_UNAVAILABLE")

    def test_missing_inputs_not_filled_with_values_or_states(self):
        payload = {"features": {LANGUAGE_FIELD: None}}
        projected = project_payload(payload, "LANGUAGE")
        self.assertEqual(projected, {"record_schema_version": "rsr-input-v1",
                                     "features": {LANGUAGE_FIELD: None}})
        report = inspect_inputs(payload, "LANGUAGE")
        self.assertEqual(report["input_status"], "MISSING")
        self.assertIn("MISSING_FIELD:" + LANGUAGES_FIELD, report["reasons"])
        self.assertIn("MISSING_FIELD_STATUS:" + LANGUAGE_FIELD, report["reasons"])

    def test_unknown_related_enum_preserved_and_reported(self):
        payload = synthetic_payload()
        del payload["features"][WEBDRIVER_FIELD]
        payload["field_status"][WEBDRIVER_FIELD] = "pretend_observed"
        payload["field_quality"][WEBDRIVER_FIELD] = 1
        projected = project_payload(payload, "WEBDRIVER_LEGACY")
        self.assertEqual(projected["field_status"][WEBDRIVER_FIELD], "pretend_observed")
        report = inspect_inputs(payload, "WEBDRIVER_LEGACY")
        self.assertEqual(report["input_status"], "MALFORMED")
        self.assertIn("INVALID_FIELD_STATUS:" + WEBDRIVER_FIELD, report["reasons"])
        self.assertIn("MISSING_FIELD:" + WEBDRIVER_FIELD, report["reasons"])

    def test_business_metadata_and_unrelated_fields_do_not_affect_transfer(self):
        payload = synthetic_payload()
        expected = project_payload(payload, "LANGUAGE")
        report = inspect_inputs(payload, "LANGUAGE")
        payload.update({"label": "SYNTHETIC_ATTACK", "phase": "SYNTHETIC_PHASE",
                        "tool": "SYNTHETIC_TOOL", "config": {"trusted": True},
                        "same_context": True, "source_binding": {"trusted": True}})
        for section in ("features", "field_status", "field_quality"):
            payload[section]["unrelated.invalid"] = {"not": "an enum"}
        self.assertEqual(project_payload(payload, "LANGUAGE"), expected)
        self.assertEqual(inspect_inputs(payload, "LANGUAGE"), report)

    def test_language_shape_checks_do_not_apply_tag_domain_or_compare(self):
        payload = synthetic_payload()
        for language, languages in ((" en_US\n", ["x-private"]), ("", [""]),
                                    ("en-US", ["en-US"]), ("en-US", ["fr-FR"])):
            with self.subTest(language=language, languages=languages):
                payload["features"][LANGUAGE_FIELD] = language
                payload["features"][LANGUAGES_FIELD] = languages
                self.assertEqual(inspect_inputs(payload, "LANGUAGE")["input_status"], "COMPLETE")
                self.assertEqual(project_payload(payload, "LANGUAGE")["features"][LANGUAGE_FIELD], language)

    def test_language_missing_and_invalid_structure_distinguished(self):
        for field, value, status in ((LANGUAGE_FIELD, None, "MISSING"),
                                     (LANGUAGE_FIELD, False, "MALFORMED"),
                                     (LANGUAGES_FIELD, [], "MISSING"),
                                     (LANGUAGES_FIELD, 2, "MALFORMED"),
                                     (LANGUAGES_FIELD, "en-US", "MALFORMED"),
                                     (LANGUAGES_FIELD, [None], "MALFORMED")):
            with self.subTest(field=field, value=value):
                payload = synthetic_payload()
                payload["features"][field] = value
                self.assertEqual(inspect_inputs(payload, "LANGUAGE")["input_status"], status)

    def test_tail_values_preserved_without_gating_first_item_shape(self):
        payload = synthetic_payload()
        for tail in ([None, 7, {"synthetic": True}], ["en-US-u-ca-gregory"], []):
            with self.subTest(tail=tail):
                payload["features"][LANGUAGES_FIELD] = ["en-US"] + tail
                self.assertEqual(inspect_inputs(payload, "LANGUAGE")["input_status"], "COMPLETE")
                self.assertEqual(project_payload(payload, "LANGUAGE")["features"][LANGUAGES_FIELD], ["en-US"] + tail)

    def test_key_order_and_repeated_calls_do_not_change_results(self):
        payload = synthetic_payload()
        reordered = {section: dict(reversed(list(values.items())))
                     for section, values in reversed(list(payload.items()))}
        for mode in ("LANGUAGE", "WEBDRIVER_LEGACY"):
            self.assertEqual(project_payload(payload, mode), project_payload(reordered, mode))
            self.assertEqual(inspect_inputs(payload, mode), inspect_inputs(reordered, mode))

    def test_projection_does_not_alias_or_mutate_input(self):
        payload = synthetic_payload()
        before = deepcopy(payload)
        projected = project_payload(payload, "LANGUAGE")
        inspect_inputs(payload, "LANGUAGE")
        self.assertEqual(payload, before)
        projected["features"][LANGUAGES_FIELD].append("SYNTHETIC-ADDED")
        self.assertEqual(payload, before)

    def test_raw_missing_never_inferred_from_legacy_false_or_version(self):
        payload = synthetic_payload()
        payload.update({"webview_version": "SYNTHETIC-133", "api_present": True,
                        "label": "SYNTHETIC_CLEAN"})
        projected = project_payload(payload, "WEBDRIVER_RAW")
        self.assertEqual(projected, {"record_schema_version": "rsr-input-v1"})
        self.assertEqual(inspect_inputs(payload, "WEBDRIVER_RAW")["input_status"], "MISSING")
        self.assertIn("MISSING_RAW_OBSERVATION", inspect_inputs(payload, "WEBDRIVER_RAW")["reasons"])

    def test_raw_projection_is_independent_and_detached(self):
        observation = synthetic_raw()
        expected = deepcopy(observation)
        observation["label"] = "SYNTHETIC_UNRELATED_LABEL"
        payload = with_raw(observation)
        payload.update({"features": "malformed legacy map is irrelevant", "field_status": {
            WEBDRIVER_FIELD: "runtime_error"}, "plugin_probe_error": "SYNTHETIC_HASH_ERROR"})
        before = deepcopy(payload)
        projected = project_payload(payload, "WEBDRIVER_RAW")
        self.assertEqual(inspect_inputs(payload, "WEBDRIVER_RAW")["input_status"], "COMPLETE")
        self.assertNotIn("features", projected)
        copied = projected["web_data"]["automation_surface_layer"]["webdriver_observation"]
        self.assertEqual(copied, expected)
        copied["boolean_value"] = True
        self.assertEqual(payload, before)

    def test_raw_structure_checks_do_not_interpret_tuple(self):
        observation = synthetic_raw()
        observation["api_present"] = False
        # Tuple contradiction is deliberately left to a separately authorized
        # interpreter; this test checks only retained member shapes.
        self.assertEqual(inspect_inputs(with_raw(observation), "WEBDRIVER_RAW")["input_status"], "COMPLETE")
        observation["presence_read_status"] = "timeout"
        report = inspect_inputs(with_raw(observation), "WEBDRIVER_RAW")
        self.assertEqual(report["input_status"], "MALFORMED")
        self.assertIn("INVALID_RAW_MEMBER_ENUM:presence_read_status", report["reasons"])

    def test_raw_required_members_checked_without_filling(self):
        observation = synthetic_raw()
        del observation["realm_binding"]
        observation["observer_revision"] = None
        report = inspect_inputs(with_raw(observation), "WEBDRIVER_RAW")
        self.assertEqual(report["input_status"], "MISSING")
        self.assertIn("MISSING_RAW_MEMBER:realm_binding", report["reasons"])
        projected = project_payload(with_raw(observation), "WEBDRIVER_RAW")
        self.assertNotIn("realm_binding", projected["web_data"]["automation_surface_layer"]["webdriver_observation"])

    def test_malformed_containers_rejected_without_repair(self):
        for payload, mode in (([], "LANGUAGE"), ({"features": []}, "LANGUAGE"),
                              ({"web_data": []}, "WEBDRIVER_RAW")):
            with self.subTest(payload=payload, mode=mode):
                self.assertEqual(inspect_inputs(payload, mode)["input_status"], "MALFORMED")
                with self.assertRaises(ValueError):
                    project_payload(payload, mode)

    def test_candidate_entry_points_are_never_called(self):
        with (patch("hybridguard_agent.research.rule_semantics_revision_v1.language.web_language_first_difference",
                   side_effect=AssertionError("candidate evaluation prohibited")) as language,
             patch("hybridguard_agent.research.rule_semantics_revision_v1.webdriver.webdriver_reported_state",
                   side_effect=AssertionError("candidate evaluation prohibited")) as webdriver):
            for mode in MODES:
                payload = with_raw(synthetic_raw()) if mode == "WEBDRIVER_RAW" else synthetic_payload()
                project_payload(payload, mode)
                report = inspect_inputs(payload, mode)
                readiness("SUPPORTED_BY_EXISTING_LINEAGE", report["input_status"])
                make_source_binding(synthetic_registration(mode), mode)
            language.assert_not_called()
            webdriver.assert_not_called()


class ReadinessAndBindingTests(unittest.TestCase):
    def test_readiness_axes_are_explicit_and_total(self):
        for source in SOURCE_STATUSES:
            for inputs in INPUT_STATUSES:
                with self.subTest(source=source, inputs=inputs):
                    expected = ("READY" if source == "SUPPORTED_BY_EXISTING_LINEAGE"
                                else "CONDITIONAL" if source == "CONDITIONAL_ASSUMPTION"
                                else "BLOCKED") if inputs == "COMPLETE" else "BLOCKED"
                    self.assertEqual(readiness(source, inputs), expected)
        self.assertEqual(readiness("page_says_verified", "COMPLETE"), "BLOCKED")
        self.assertEqual(readiness("SUPPORTED_BY_EXISTING_LINEAGE", "unknown"), "BLOCKED")

    def test_binding_only_from_supported_scope_and_evidence(self):
        for mode in MODES:
            registration = synthetic_registration(mode)
            binding = make_source_binding(registration, mode)
            self.assertEqual(binding.source_contract_id, registration["source_group_id"])
            self.assertEqual(binding.observation_scope, BINDING_SCOPES_BY_MODE[mode])
            for status in SOURCE_STATUSES[1:]:
                self.assertIsNone(make_source_binding(synthetic_registration(mode, status), mode))
            for patch_value in ({"evidence_refs": []}, {"evidence_refs": [""]},
                                {"evidence_refs": "verified"}, {"binding_scope": "same_context"}):
                with self.subTest(mode=mode, patch_value=patch_value):
                    invalid = deepcopy(registration)
                    invalid["modes"][mode].update(patch_value)
                    self.assertIsNone(make_source_binding(invalid, mode))

    def test_binding_metadata_is_separate_and_never_inferred(self):
        registration = synthetic_registration("WEBDRIVER_RAW")
        before = deepcopy(registration)
        binding = make_source_binding(registration, "WEBDRIVER_RAW")
        self.assertIsNone(binding.observer_revision)
        self.assertIsNone(binding.realm_binding)
        self.assertEqual(registration, before)
        self.assertIsNone(make_source_binding({"trusted": True, "same_context": True}, "LANGUAGE"))
        entry = registration["modes"]["WEBDRIVER_RAW"]
        entry.update(observer_revision="SYNTHETIC-OBSERVER-v1", realm_binding="SYNTHETIC-REALM-1")
        binding = make_source_binding(registration, "WEBDRIVER_RAW")
        self.assertEqual(binding.observer_revision, "SYNTHETIC-OBSERVER-v1")
        self.assertEqual(binding.realm_binding, "SYNTHETIC-REALM-1")

    def test_unknown_modes_do_not_choose_an_alternate(self):
        for mode in (None, "legacy_projection_v1", "AUTO", []):
            with self.subTest(mode=mode):
                for function, argument in ((project_payload, {}), (inspect_inputs, {}),
                                           (make_source_binding, {})):
                    with self.assertRaises(ValueError):
                        function(argument, mode)


if __name__ == "__main__":
    unittest.main()
