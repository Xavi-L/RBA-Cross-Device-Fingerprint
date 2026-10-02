"""Synthetic boundary tests, not experiment records."""
import copy
import unittest
from classify import classify, combine


def sample(value, kind, error=0):
    return dict(value=value, value_kind=kind, error=error, pre_errors=[], drained=True,
                context_lost_before=False, context_lost_after=False)


def normal():
    row = dict(status="MEASURED", context_lost_at_end=False, extension_available=True,
               extension_constants=dict(vendor=37445, renderer=37446))
    row["extension_disabled"] = {k: sample(None, "null", 1280) for k in ("vendor", "renderer")}
    row["extension_enabled"] = {k: {q: sample("some driver", "string") for q in
        ("numeric_before", "numeric_string", "numeric_after")} for k in ("vendor", "renderer")}
    row["capability"] = dict(numeric=sample(16, "number"), numeric_string=sample(16, "number"),
        last_valid_index=sample(None, "undefined"), first_invalid_index=sample(None, "undefined", 1281))
    row["render"] = sample(dict(status="EXECUTED", pixels=[255, 0, 0, 255] * 64), "object")
    return row


class Boundaries(unittest.TestCase):
    def test_conformant(self):
        self.assertEqual(set(classify(normal()).values()), {"MATCH"})

    def test_known_plugin_shape(self):
        row = normal()
        row["extension_disabled"]["renderer"] = sample("fake", "string", 1280)
        for name in ("numeric_before", "numeric_after"):
            row["extension_enabled"]["renderer"][name]["value"] = "fake"
        result = classify(row)
        self.assertEqual(result["extension_gate"], "COUNTEREXAMPLE")
        self.assertEqual(result["argument_coercion"], "COUNTEREXAMPLE")
        self.assertEqual(result["behavior_relation"], "COUNTEREXAMPLE")

    def test_context_loss_and_unavailability(self):
        for key, value in (("context_lost_at_end", True), ("status", "UNAVAILABLE")):
            row = normal(); row[key] = value
            self.assertEqual(set(classify(row).values()), {"UNKNOWN"})

    def test_dirty_error_queue_and_exception(self):
        for key, value in (("pre_errors", [1280]), ("exception", "error"), ("drained", False)):
            row = normal()
            row["extension_disabled"]["renderer"][key] = value
            self.assertEqual(classify(row)["extension_gate"], "UNKNOWN")

    def test_temporal_drift_is_unknown(self):
        row = normal()
        row["extension_enabled"]["renderer"]["numeric_after"]["value"] = "changed driver"
        self.assertEqual(classify(row)["argument_coercion"], "UNKNOWN")

    def test_unusable_and_missing_values(self):
        for value in (None, "Unknown", ""):
            row = normal()
            row["extension_enabled"]["renderer"]["numeric_string"]["value"] = value
            self.assertEqual(classify(row)["argument_coercion"], "UNKNOWN")
        row = normal(); del row["extension_disabled"]["renderer"]
        self.assertEqual(classify(row)["extension_gate"], "UNKNOWN")

    def test_absent_extension_not_a_coercion_pass(self):
        row = normal(); row["extension_available"] = False; row["extension_enabled"] = {}
        self.assertEqual(classify(row)["argument_coercion"], "UNKNOWN")

    def test_failed_positive_control_does_not_alarm(self):
        row = normal(); row["extension_disabled"]["renderer"] = sample("fake", "string", 1280)
        for target in ("render", "capability"):
            broken = copy.deepcopy(row)
            if target == "render": broken[target]["value"]["pixels"][0] = 0
            else: broken[target]["numeric_string"]["value"] = 15
            self.assertEqual(classify(broken)["behavior_relation"], "UNKNOWN")

    def test_partial_verified_conflict_retained(self):
        self.assertEqual(combine(["COUNTEREXAMPLE", "UNKNOWN"]), "COUNTEREXAMPLE")
        self.assertEqual(combine(["MATCH", "UNKNOWN"]), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
