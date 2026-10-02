import copy
import unittest
from analyze import audit, compare, triplet, TARGETS


def graphics():
    values = {
        "native_gpu_vendor": "Google (Apple)", "native_gpu_renderer": "Apple M4",
        "egl_vendor": "Android", "egl_renderer": "Apple M4", "gles_version": "OpenGL ES 3.0",
        "webgl_vendor": "Google (Apple)", "webgl_renderer": "Apple M4", "webgl2_supported": True,
        "webgl_extensions_count": 16, "webgl_max_texture_size": 4096,
        "webgl_max_viewport_dims": "16384x16384", "webgl_aliased_line_width_range": "1-1",
    }
    return {f: {"value": values[f.rsplit('.', 1)[1]], "source_status": "observed"} for f in audit.FIELDS}


class PairedAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.options = {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)"}
        self.phases = {p: {"graphics": graphics()} for p in ("clean_pre", "attack", "clean_post")}
        for field, value in zip(TARGETS, self.options.values()):
            self.phases["attack"]["graphics"][field]["value"] = value

    def test_measured_target_and_independent_restoration(self):
        result = triplet(self.phases, self.options)
        self.assertTrue(result["measured_effect"])
        self.assertTrue(result["all_graphics_restored"])
        self.assertTrue(result["non_target_graphics_unchanged"])

    def test_failed_or_unknown_read_does_not_become_effect(self):
        self.phases["attack"]["graphics"][TARGETS[0]]["source_status"] = "runtime_error"
        self.assertIsNone(triplet(self.phases, self.options)["measured_effect"])

    def test_value_without_declared_effect_is_not_success(self):
        self.phases["attack"] = copy.deepcopy(self.phases["clean_pre"])
        self.assertFalse(triplet(self.phases, self.options)["measured_effect"])

    def test_missing_post_is_incomplete(self):
        del self.phases["clean_post"]
        result = triplet(self.phases, self.options)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIsNone(result["all_graphics_restored"])

    def test_post_unknown_does_not_count_as_restoration(self):
        self.phases["clean_post"]["graphics"][TARGETS[1]]["source_status"] = "runtime_error"
        result = triplet(self.phases, self.options)
        self.assertTrue(result["measured_effect"])
        self.assertIsNone(result["all_graphics_restored"])

    def test_non_target_change_and_incomplete_restoration_are_visible(self):
        key = "app.web_data.graphics_layer.webgl2_supported"
        self.phases["attack"]["graphics"][key]["value"] = False
        self.phases["clean_post"]["graphics"][TARGETS[1]]["value"] = "still modified"
        result = triplet(self.phases, self.options)
        self.assertFalse(result["non_target_graphics_unchanged"])
        self.assertFalse(result["all_graphics_restored"])

    def test_two_matching_failures_are_not_known_equality(self):
        left, right = graphics(), graphics()
        for data in (left, right):
            data[TARGETS[0]]["source_status"] = "runtime_error"
        self.assertIsNone(compare(left, right)["equal"])


if __name__ == "__main__":
    unittest.main()
