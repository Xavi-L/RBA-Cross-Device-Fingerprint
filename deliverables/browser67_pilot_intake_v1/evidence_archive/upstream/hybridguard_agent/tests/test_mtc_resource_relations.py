import copy
import math
import unittest

from hybridguard_agent.research import mtc_resource_relations as r
from hybridguard_agent.research.rule_learning.contracts import logic, negate, state
from hybridguard_agent.research.rule_learning_v2.semantic_selection import semantic_catalog


def record(native, web):
    return {"features": {r.NATIVE_MEMORY: native, r.WEB_MEMORY: web},
            "field_status": {f: "observed" for f in r.FIELDS},
            "field_quality": {f: "observed_value" for f in r.FIELDS},
            "source_binding": {"binding_valid": True, "same_app_record": True,
                               "app_session_id": "one-current-session"}}


def value(native, web):
    return state(r.evaluate(record(native, web))[r.MEMORY_ID])


class ResourceRelationsTest(unittest.TestCase):
    def test_normal_quantization_cap_and_old_ratio_counterexamples(self):
        for native, web in ((1.934, 2), (2.415, 2), (6, 8), (32, 8), (8, 0.5), (0.25, 0.25)):
            with self.subTest(native=native, web=web):
                self.assertEqual(value(native, web), "F")

    def test_cross_layer_value_dependency_and_observed_normal_deviation_retained(self):
        self.assertEqual(value(2.415, 8), "T")
        self.assertEqual(value(8, 8), "F")
        original = record(2.415, 8)
        original.update(label="normal", model="new-device", sample_id="held-out", phase="clean_post")
        self.assertEqual(state(r.evaluate(original)[r.MEMORY_ID]), "T")

    def test_units_and_exact_power_boundaries(self):
        self.assertEqual(r.power_two_upper_envelope(6), 8)
        self.assertEqual(r.power_two_upper_envelope(4), 4)
        self.assertEqual(r.power_two_upper_envelope(math.nextafter(4, math.inf)), 8)
        self.assertEqual(r.power_two_upper_envelope(math.nextafter(4, 0)), 4)
        self.assertEqual(value(2, 4), "T")
        self.assertEqual(value(2.1, 4), "F")

    def test_missing_quality_sentinels_and_wrong_types(self):
        for bad in (None, 0, -1, -2, True, False, "8", float("nan"), float("inf")):
            for field in r.FIELDS:
                with self.subTest(bad=bad, field=field):
                    obj = record(2.415, 8)
                    obj["features"][field] = bad
                    self.assertEqual(state(r.evaluate(obj)[r.MEMORY_ID]), "U")
        obj = record(2.415, 8)
        del obj["features"][r.NATIVE_MEMORY]
        self.assertIn("MISSING", r.evaluate(obj)[r.MEMORY_ID]["reason"])
        obj = record(2.415, 8)
        obj["field_quality"][r.NATIVE_MEMORY] = "default_value"
        self.assertEqual(state(r.evaluate(obj)[r.MEMORY_ID]), "U")
        self.assertEqual(value(0.125, 0.25), "U")

    def test_no_available_memory_substitution_or_metadata_feature(self):
        obj = record(2.415, 8)
        first = r.evaluate(obj)
        obj["features"]["app.android_native_data.memory_layer.avail_memory_gb"] = 0.01
        obj.update(sample_id="different", phase="attack", label="attack", source="different")
        obj["features"]["model_id"] = "different"
        self.assertEqual(r.evaluate(obj), first)
        before = copy.deepcopy(obj)
        r.evaluate(obj)
        self.assertEqual(obj, before)

    def test_negation_and_or_preserve_unknown(self):
        t, f, u = value(2, 8), value(8, 8), value(0, 8)
        self.assertEqual((negate(t), negate(f), negate(u)), ("F", "T", "U"))
        self.assertEqual(logic((t, u), "OR"), "T")
        self.assertEqual(logic((f, u), "OR"), "U")

    def test_explicit_two_surface_registration_and_no_quality_bonus(self):
        atoms = r.registered_atoms()
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].surfaces, ("native84", "app_web67"))
        entry = semantic_catalog(atoms)[r.MEMORY_ID]
        self.assertEqual(entry["quality"], 0)
        self.assertEqual(entry["signal_group"], "memory_capacity")
        self.assertFalse(atoms[0].provenance["condition"]["parameters"]["learned_parameters"])

    def test_binding_required_before_value_evaluation(self):
        for binding in (None, {}, {"binding_valid": False},
                        {"binding_valid": True, "same_app_record": False, "app_session_id": "a"},
                        {"binding_valid": True, "same_app_record": True, "app_session_id": ""}):
            obj = record(2, 8)
            obj["source_binding"] = binding
            got = r.evaluate(obj)[r.MEMORY_ID]
            self.assertEqual(got["evaluation_status"], "FAILED")
            self.assertEqual(got["diagnostics"]["availability_category"], "binding_failure")
        obj = record(2, 8)
        obj["source_binding"]["app_session_id"] = "another-whole-current-session"
        self.assertEqual(state(r.evaluate(obj)[r.MEMORY_ID]), "T")


if __name__ == "__main__":
    unittest.main()
