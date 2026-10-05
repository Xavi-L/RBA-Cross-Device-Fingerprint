"""Version/binding/quality boundaries and actual-JS synthetic fixture consumption."""
import copy
import json
from pathlib import Path
import unittest

from hybridguard_agent.research.webgl_parameter_equivalence import (
    EVALUATOR_REVISION, evaluate_observation, evaluate_parameter_triplet,
)

FIXTURES = Path(__file__).parent / "fixtures/webgl_parameter_equivalence_v1/observer_examples.json"


class ParameterEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURES.read_text())
        cls.cases = {row["id"]: row for row in cls.fixture["cases"]}

    def observation(self, name="normal"):
        return copy.deepcopy(self.cases[name]["observation"])

    def evaluate(self, observation):
        return evaluate_observation(observation, expected_realm_binding=self.fixture["expected_realm_binding"])

    def test_actual_js_output_and_no_input_mutation(self):
        self.assertEqual(self.fixture["kind"], "SYNTHETIC_ONLY_NOT_DEVICE_SAMPLES")
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                before = copy.deepcopy(case["observation"])
                result = self.evaluate(case["observation"])
                self.assertEqual(result["outcome"], case["expected"])
                self.assertEqual(result["evaluator_revision"], EVALUATOR_REVISION)
                self.assertEqual(result["decision_role"], "observation_only")
                self.assertEqual(case["observation"], before)

    def test_version_scope_and_external_binding_required(self):
        for field in ("observation_schema_version", "observer_revision", "observation_scope", "realm_binding"):
            with self.subTest(field=field):
                observation = self.observation(); observation[field] = "wrong"
                self.assertEqual(self.evaluate(observation)["outcome"], "UNKNOWN")
        for binding in (None, "", "  "):
            self.assertEqual(evaluate_observation(self.observation(), expected_realm_binding=binding)["reason"],
                             "CALLER_REALM_BINDING_REQUIRED")

    def test_context_set_cannot_drop_or_duplicate_a_requested_context(self):
        for change in (lambda c: c[:1], lambda c: [c[0], c[0]], lambda c: list(reversed(c)), lambda c: [None, c[1]]):
            observation = self.observation(); observation["contexts"] = change(observation["contexts"])
            self.assertEqual(self.evaluate(observation)["reason"], "CONTEXT_SET_MISMATCH")

    def test_argument_metadata_and_observation_state_are_mandatory(self):
        original = self.observation()["contexts"][0]["parameters"]["renderer"]
        for field, value in (("argument", 37445), ("argument_kind", "number"), ("read_status", "runtime_error"),
                             ("error", False), ("drained", 1), ("context_lost_before", None),
                             ("context_lost_after", True), ("pre_errors", [1280]), ("exception", None)):
            with self.subTest(field=field):
                reads = copy.deepcopy(original); reads["numeric_string"][field] = value
                self.assertEqual(evaluate_parameter_triplet(reads, parameter=37446)["outcome"], "UNKNOWN")
        reads = copy.deepcopy(original); del reads["numeric_string"]["read_status"]
        self.assertEqual(evaluate_parameter_triplet(reads, parameter=37446)["reason"], "QUERY_NOT_OBSERVED")

    def test_missing_sentinel_and_invalid_type_values_are_unknown(self):
        original = self.observation()["contexts"][0]["parameters"]["renderer"]
        for value in (None, "", "Unknown", "masked", True, 123, {}, []):
            with self.subTest(value=value):
                reads = copy.deepcopy(original); reads["numeric_string"]["value"] = value
                self.assertEqual(evaluate_parameter_triplet(reads, parameter=37446)["outcome"], "UNKNOWN")
        self.assertEqual(evaluate_parameter_triplet({}, parameter=37446)["outcome"], "UNKNOWN")

    def test_numeric_temporal_drift_is_not_a_parameter_conflict(self):
        reads = self.observation()["contexts"][0]["parameters"]["renderer"]
        reads["numeric_after"]["value"] = "different driver now"
        self.assertEqual(evaluate_parameter_triplet(reads, parameter=37446)["reason"], "TEMPORAL_INSTABILITY")

    def test_control_rejects_nonfinite_bool_and_out_of_domain_numbers(self):
        original = self.observation()["contexts"][0]["control"]["queries"]
        for value in (True, float("nan"), float("inf"), 10 ** 400, -1, 0, 1.5, 2147483648):
            with self.subTest(value=repr(value)):
                reads = copy.deepcopy(original); reads["numeric_before"]["value"] = value
                self.assertEqual(evaluate_parameter_triplet(reads, parameter=34921, value_kind="number")["outcome"], "UNKNOWN")
        reads = copy.deepcopy(original); reads["numeric_before"]["argument"] = 10 ** 400
        self.assertEqual(evaluate_parameter_triplet(reads, parameter=34921, value_kind="number")["outcome"], "UNKNOWN")

    def test_failed_control_does_not_make_renderer_conflict_eligible(self):
        observation = self.observation("numeric_string_conflict")
        for context in observation["contexts"]:
            context["control"]["queries"]["numeric_string"]["value"] = 17
        result = self.evaluate(observation)
        self.assertEqual(result["outcome"], "UNKNOWN")
        self.assertEqual(result["contexts"]["webgl"]["reason"], "POSITIVE_CONTROL_NOT_MATCHED")

    def test_context_and_preflight_quality_never_become_normal_passes(self):
        for field, value in (("context_creation_status", "unavailable"), ("context_lost_at_end", True),
                             ("extension_available", False), ("extension_read_status", "runtime_error"),
                             ("extension_constants", {"vendor": 37446, "renderer": 37445})):
            observation = self.observation()
            observation["contexts"][0][field] = value
            self.assertEqual(self.evaluate(observation)["outcome"], "UNKNOWN")
        observation = self.observation("numeric_string_conflict")
        for context in observation["contexts"]:
            context["preflight"]["errors"] = [1280]
        self.assertEqual(self.evaluate(observation)["outcome"], "UNKNOWN")

    def test_one_valid_conflict_survives_other_context_unavailability(self):
        observation = self.observation("numeric_string_conflict")
        observation["contexts"][1]["context_creation_status"] = "unavailable"
        result = self.evaluate(observation)
        self.assertEqual(result["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(result["contexts"]["webgl2"]["outcome"], "UNKNOWN")

    def test_labels_do_not_influence_pure_evaluation(self):
        observation = self.observation()
        expected = self.evaluate(observation)
        observation.update(label="attack", phase="attack", model_score=1.0, expected_outcome="COUNTEREXAMPLE")
        self.assertEqual(self.evaluate(observation), expected)

    def test_unsupported_parameters_and_incomplete_envelopes(self):
        for value in (None, {}, [], "text"):
            self.assertEqual(self.evaluate(value)["outcome"], "UNKNOWN")
        self.assertEqual(evaluate_parameter_triplet({}, parameter=True)["reason"], "UNSUPPORTED_PARAMETER")
        self.assertEqual(evaluate_parameter_triplet({}, parameter=37446, value_kind="number")["reason"], "UNSUPPORTED_VALUE_KIND")


if __name__ == "__main__":
    unittest.main()
