"""Synthetic scope boundaries; no measured device rows or attack labels."""
import copy
import json
from pathlib import Path
import unittest

from hybridguard_agent.research.webgl1_parameter_candidate import evaluate_webgl1_candidate


class WebGL1CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads((Path(__file__).parent / "fixtures/webgl_parameter_equivalence_v1/observer_examples.json").read_text())
        cls.binding = fixture["expected_realm_binding"]
        cls.normal = next(c["observation"] for c in fixture["cases"] if c["id"] == "normal")

    def row(self):
        return copy.deepcopy(self.normal)

    def evaluate(self, row):
        return evaluate_webgl1_candidate(row, expected_realm_binding=self.binding)

    def conflict(self, row, context):
        for query in ("numeric_before", "numeric_after"):
            row["contexts"][context]["parameters"]["renderer"][query]["value"] = "synthetic changed renderer"

    def test_webgl1_match_and_conflict_without_input_mutation(self):
        row = self.row(); before = copy.deepcopy(row)
        self.assertEqual(self.evaluate(row)["state"], "F")
        self.assertEqual(row, before)
        self.conflict(row, 0)
        self.assertEqual(self.evaluate(row)["state"], "T")

    def test_webgl2_unknown_is_retained_without_changing_webgl1_scope(self):
        row = self.row(); row["contexts"][1]["preflight"]["errors"] = [1280]
        result = self.evaluate(row)
        self.assertEqual(result["state"], "F")
        self.assertEqual(result["diagnostics"]["full_observation_outcome"], "UNKNOWN")
        self.assertEqual(result["diagnostics"]["webgl2"]["outcome"], "UNKNOWN")

    def test_webgl2_only_conflict_is_outside_candidate_scope(self):
        row = self.row(); self.conflict(row, 1)
        result = self.evaluate(row)
        self.assertEqual(result["state"], "F")
        self.assertEqual(result["diagnostics"]["full_observation_outcome"], "COUNTEREXAMPLE")

    def test_webgl1_unavailable_cannot_borrow_webgl2_conflict(self):
        row = self.row(); self.conflict(row, 1)
        row["contexts"][0]["preflight"]["errors"] = [1280]
        result = self.evaluate(row)
        self.assertEqual(result["state"], "U")
        self.assertEqual(result["diagnostics"]["full_observation_outcome"], "COUNTEREXAMPLE")

    def test_envelope_and_external_binding_still_required(self):
        self.assertEqual(evaluate_webgl1_candidate(self.row(), expected_realm_binding="wrong")["state"], "U")
        for key in ("observation_schema_version", "observer_revision", "observation_scope"):
            row = self.row(); row[key] = "wrong"
            self.assertEqual(self.evaluate(row)["state"], "U")
        row = self.row(); row["contexts"] = row["contexts"][:1]
        self.assertEqual(self.evaluate(row)["state"], "U")

    def test_webgl1_quality_errors_and_temporal_drift_stay_unknown(self):
        for field, value in (("read_status", "runtime_error"), ("error", 1280), ("value", "unknown")):
            row = self.row(); row["contexts"][0]["parameters"]["renderer"]["numeric_string"][field] = value
            self.assertEqual(self.evaluate(row)["state"], "U")
        row = self.row(); row["contexts"][0]["parameters"]["renderer"]["numeric_after"]["value"] = "drift"
        self.assertEqual(self.evaluate(row)["state"], "U")
        row = self.row(); row["contexts"][0]["control"]["queries"]["numeric_string"]["value"] = 7
        self.assertEqual(self.evaluate(row)["state"], "U")


if __name__ == "__main__":
    unittest.main()
