"""Focused semantic boundaries for the audit adapter and existing v2 GPU gates."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit import NATIVE, WEB, extract_graphics, load_registry, observations, projection, evaluate_contract


def raw(native="Adreno (TM) 650", web="ANGLE (Qualcomm, Adreno (TM) 650, OpenGL ES 3.2)"):
    data = {
        "android_native_data": {"graphics_layer": {"native_gpu_renderer": native, "egl_renderer": native}},
        "web_data": {"graphics_layer": {"webgl_vendor": "Google Inc.", "webgl_renderer": web}},
    }
    data["collection_status"] = {"fields": {n.removeprefix("app."): "observed" for n in (
        NATIVE + "native_gpu_renderer", NATIVE + "egl_renderer", WEB + "webgl_vendor", WEB + "webgl_renderer")}}
    return data


class GPUAuditBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry()

    def evaluate(self, data, rule="NW-005"):
        return evaluate_contract(rule, projection(extract_graphics(data), self.registry), self.registry)

    def test_presence_does_not_replace_explicit_observed_status(self):
        data = raw()
        del data["collection_status"]["fields"]["android_native_data.graphics_layer.native_gpu_renderer"]
        result = self.evaluate(data)
        self.assertEqual(result["relation_applicability"]["status"], "UNKNOWN")
        self.assertEqual(result["risk_candidate_eligibility"]["status"], "UNKNOWN")

    def test_angle_and_different_spelling_can_be_matching_hardware(self):
        data = raw()
        result = self.evaluate(data)
        self.assertEqual(result["relation_result"]["outcome"], "MATCH")
        self.assertEqual(result["risk_candidate_eligibility"]["status"], "ELIGIBLE")
        observed = observations(extract_graphics(data))
        self.assertEqual(observed["native_web_renderer_text_unequal"], "T")
        self.assertEqual(observed["lexical_web_desktop_backend_marker"], "F")

    def test_named_family_conflict_is_eligible_without_attack_attribution(self):
        result = self.evaluate(raw(web="Mali-G78"))
        self.assertEqual(result["relation_result"]["outcome"], "COUNTEREXAMPLE")
        self.assertEqual(result["risk_candidate_eligibility"]["status"], "ELIGIBLE")
        self.assertEqual(result["attribution_certainty"]["status"], "UNKNOWN")
        self.assertFalse(result["attribution_certainty"]["attack_proven"])

    def test_software_excludes_hardware_comparison_even_with_desktop_marker(self):
        for token in ("SwiftShader", "lavapipe", "llvmpipe", "softpipe", "swrast", "swangle"):
            with self.subTest(token=token):
                data = raw(native=token, web="ANGLE (NVIDIA, GeForce, Direct3D11)")
                self.assertEqual(self.evaluate(data)["relation_result"]["outcome"], "NOT_APPLICABLE")
                self.assertEqual(self.evaluate(data, "OFFDER-GPU-001")["relation_applicability"]["status"], "NOT_APPLICABLE")
                self.assertEqual(observations(extract_graphics(data))["lexical_web_desktop_backend_marker"], "T")

    def test_masking_ambiguity_and_malformed_values_remain_unknown(self):
        for renderer in (None, 42, "", "masked", "ANGLE redacted", "Adreno and Mali", "unrecognized renderer",
                         "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)"):
            with self.subTest(renderer=renderer):
                result = self.evaluate(raw(web=renderer))
                self.assertEqual(result["relation_applicability"]["status"], "UNKNOWN")

    def test_backend_marker_does_not_gain_risk_role_when_it_fires(self):
        for renderer, outcome in (("ANGLE (NVIDIA, GeForce, Direct3D11)", "COUNTEREXAMPLE"),
                                  ("ANGLE (Qualcomm, Adreno 650, OpenGL ES)", "MATCH")):
            with self.subTest(renderer=renderer):
                result = self.evaluate(raw(web=renderer), "OFFDER-GPU-001")
                self.assertEqual(result["relation_result"]["outcome"], outcome)
                self.assertEqual(result["risk_candidate_eligibility"]["status"], "NOT_ELIGIBLE")

    def test_unavailable_diagnostic_is_not_false_and_metadata_is_excluded(self):
        data = raw()
        data["collection_status"]["fields"]["web_data.graphics_layer.webgl_renderer"] = "runtime_error"
        data.update(supervised_label=1, environment_group_id="must-not-enter-relation", phase="attack")
        original = deepcopy(data)
        graphics = extract_graphics(data)
        projected = projection(graphics, self.registry)
        self.assertEqual(observations(graphics)["native_web_renderer_text_unequal"], "U")
        self.assertEqual(len(projected["features"]), 4)
        self.assertNotIn("supervised_label", projected["features"])
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
