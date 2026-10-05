"""Predicate boundary tests; no MTC observation data is read."""
import copy
import math
import unittest

from hybridguard_agent.research import mtc_p3_candidates as candidates


TEMPLATES = {row["candidate_id"]: row for row in candidates.candidate_templates()}


def record_for(candidate, values):
    return {
        "features": dict(zip(candidate["dependencies"], values)),
        "field_status": {path: "observed" for path in candidate["dependencies"]},
        "field_quality": {path: "observed_value" for path in candidate["dependencies"]},
    }


def evaluate(candidate_id, values):
    candidate = TEMPLATES[candidate_id]
    return candidates.evaluate_candidate(candidate, record_for(candidate, values))


class MtcP3CandidateTests(unittest.TestCase):
    def assert_outcome(self, candidate_id, values, expected):
        result = evaluate(candidate_id, values)
        self.assertEqual(result["outcome"], expected, result)
        return result

    def test_missing_status_quality_and_placeholder_values_remain_unknown(self):
        candidate = TEMPLATES["P3-X-LANGUAGE"]
        path = candidate["dependencies"][0]
        valid = record_for(candidate, ["en-US", "fr-FR"])
        for mapping in ("features", "field_status", "field_quality"):
            with self.subTest(missing=mapping):
                record = copy.deepcopy(valid)
                del record[mapping][path]
                self.assertEqual(candidates.evaluate_candidate(candidate, record)["outcome"], "UNKNOWN")
        for state in ("unsupported_by_os", "permission_denied", "runtime_error", "timeout", "not_applicable"):
            with self.subTest(state=state):
                record = copy.deepcopy(valid)
                record["field_status"][path] = state
                self.assertEqual(candidates.evaluate_candidate(candidate, record)["outcome"], "UNKNOWN")
        for quality in ("source_unavailable", "ambiguous_sentinel"):
            with self.subTest(quality=quality):
                record = copy.deepcopy(valid)
                record["field_quality"][path] = quality
                self.assertEqual(candidates.evaluate_candidate(candidate, record)["outcome"], "UNKNOWN")
        for placeholder in (None, "", "unknown", " ERROR ", "unsupported", "not available"):
            with self.subTest(placeholder=placeholder):
                self.assert_outcome("P3-X-LANGUAGE", [placeholder, "en-US"], "UNKNOWN")

    def test_navigator_zero_sentinels_do_not_become_agreement(self):
        for candidate_id in ("P3-X-CORES", "P3-X-MEMORY"):
            for value in (0, -1, False, "8"):
                with self.subTest(candidate_id=candidate_id, value=value):
                    self.assert_outcome(candidate_id, [value, value], "UNKNOWN")
            self.assert_outcome(candidate_id, [8, 8.0], "MATCH")

    def test_legal_zero_false_and_empty_lists_are_not_globally_missing(self):
        self.assert_outcome("P3-X-TOUCH", [0, 0.0], "MATCH")
        self.assert_outcome("P3-X-TIMEZONE-OFFSET", [0, 0], "MATCH")
        self.assert_outcome("P3-X-LANGUAGES", [[], []], "MATCH")
        self.assert_outcome("P3-SENSOR-TYPE-COUNT", [[], 0], "MATCH")
        self.assert_outcome("P3-SENSOR-TYPE-ORDER", [[]], "MATCH")
        self.assert_outcome("P3-SENSOR-ACCELEROMETER", [False, []], "NOT_APPLICABLE")
        self.assert_outcome("P3-SENSOR-ACCELEROMETER", [False, [1]], "NOT_APPLICABLE")
        self.assertTrue(candidates._semantic_equal(False, False))
        self.assertFalse(candidates._semantic_equal(False, 0))

    def test_numeric_equality_does_not_coerce_bools_strings_or_list_order(self):
        self.assertTrue(candidates._semantic_equal(8, 8.0))
        self.assertFalse(candidates._semantic_equal(1, True))
        self.assertFalse(candidates._semantic_equal("8", 8))
        self.assertFalse(candidates._semantic_equal([1, 2], [2, 1]))
        self.assertFalse(candidates._semantic_equal([1], [True]))
        self.assert_outcome("P3-MEM-AVAILABLE", [True, 4], "UNKNOWN")
        self.assert_outcome("P3-MEM-AVAILABLE", [0, 4.0], "MATCH")
        self.assert_outcome("P3-MEM-AVAILABLE", [5, 4], "COUNTEREXAMPLE")

    def test_nonfinite_numeric_dependencies_are_unknown(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.subTest(value=value):
                self.assert_outcome("P3-X-DPR", [value, value], "UNKNOWN")
                self.assert_outcome("P3-MEM-AVAILABLE", [value, 4], "UNKNOWN")

    def test_positive_measurement_fields_do_not_accept_zero_or_invalid_types(self):
        for candidate_id in ("P3-X-COLOR", "P3-COLOR-APP", "P3-COLOR-BROWSER", "P3-X-DPR", "P3-X-AUDIO-RATE"):
            for invalid in (0, -1, False, "24"):
                with self.subTest(candidate_id=candidate_id, invalid=invalid):
                    self.assert_outcome(candidate_id, [invalid, invalid], "UNKNOWN")
        self.assert_outcome("P3-X-COLOR", [24, 24.0], "MATCH")
        self.assert_outcome("P3-X-TOUCH", [0, 0], "MATCH")

    def test_collector_android_prefix_and_numeric_os_formats_have_same_semantics(self):
        ua = "Mozilla/5.0 (Linux; Android 14; Fixture) AppleWebKit/537.36 Chrome/106.0.0.0 Mobile Safari/537.36"
        for candidate_id in ("P3-OS-APP", "P3-OS-BROWSER", "P3-UA-REDUCED-BROWSER"):
            for native in ("Android 14", "14", "Android 14.0", "14.0"):
                with self.subTest(candidate_id=candidate_id, native=native):
                    self.assert_outcome(candidate_id, [native, ua], "MATCH")
            for native in ("Android 16", "16"):
                with self.subTest(candidate_id=candidate_id, native=native):
                    self.assert_outcome(candidate_id, [native, ua], "COUNTEREXAMPLE")

    def test_reduced_browser_ua_is_not_an_os_agreement_vote(self):
        reduced = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/123.0.0.0 Mobile Safari/537.36"
        for native in ("10", "10.0", "14", "Android 10", "Android 10.0", "Android 14"):
            with self.subTest(native=native):
                result = self.assert_outcome("P3-UA-REDUCED-BROWSER", [native, reduced], "NOT_APPLICABLE")
                self.assertEqual(result["reason"], "reduced_ua_os_unidentifiable")
        old = reduced.replace("Chrome/123.", "Chrome/106.")
        self.assert_outcome("P3-UA-REDUCED-BROWSER", ["14", old], "COUNTEREXAMPLE")
        actual = reduced.replace("Android 10; K", "Android 14; Device")
        self.assert_outcome("P3-UA-REDUCED-BROWSER", ["14", actual], "MATCH")
        firefox = "Mozilla/5.0 (Android 14; Mobile; rv:130.0) Gecko/130.0 Firefox/130.0"
        self.assert_outcome("P3-UA-REDUCED-BROWSER", ["14", firefox], "MATCH")
        self.assert_outcome("P3-UA-REDUCED-BROWSER", ["13", firefox], "COUNTEREXAMPLE")
        self.assert_outcome("P3-UA-REDUCED-BROWSER", ["14", "unparseable UA"], "UNKNOWN")

    def test_short_side_uses_css_units_orientation_and_closed_one_pixel_tolerance(self):
        for native, logical in (("1080x1920", "360x640"), ("1920x1080", "640x360")):
            self.assert_outcome("P3-SCREEN-APP", [native, logical, 3], "MATCH")
        edge = self.assert_outcome("P3-SCREEN-APP", ["1083x1920", "360x640", 3], "MATCH")
        self.assertEqual(edge["absolute_css_pixel_residual"], 1)
        self.assert_outcome("P3-SCREEN-APP", ["1084x1920", "360x640", 3], "COUNTEREXAMPLE")
        # This predicate intentionally makes no assertion about the long side.
        self.assert_outcome("P3-SCREEN-APP", ["1080x1920", "360x800", 3], "MATCH")
        self.assert_outcome("P3-X-SCREEN-SIZE", ["360x640", "640x360"], "MATCH")

    def test_invalid_screen_dimensions_or_dpr_are_unknown(self):
        for dimensions in ("0x640", "-1x640", "360.5x640", [360, 640]):
            with self.subTest(dimensions=dimensions):
                self.assert_outcome("P3-SCREEN-APP", ["1080x1920", dimensions, 3], "UNKNOWN")
        for dpr in (0, -1, True, "3", math.inf):
            with self.subTest(dpr=dpr):
                self.assert_outcome("P3-SCREEN-APP", ["1080x1920", "360x640", dpr], "UNKNOWN")

    def test_sensor_presence_is_directional_and_rejects_invalid_type_elements(self):
        self.assert_outcome("P3-SENSOR-ACCELEROMETER", [True, [1, 2]], "MATCH")
        self.assert_outcome("P3-SENSOR-ACCELEROMETER", [True, [2]], "COUNTEREXAMPLE")
        for invalid in ([True], ["1"], [0], [1.5]):
            with self.subTest(invalid=invalid):
                self.assert_outcome("P3-SENSOR-ACCELEROMETER", [True, invalid], "UNKNOWN")
        self.assert_outcome("P3-SENSOR-ACCELEROMETER", [1, [1]], "UNKNOWN")

    def test_distinct_sensor_types_and_counts_keep_structure_explicit(self):
        self.assert_outcome("P3-SENSOR-TYPE-ORDER", [[1, 2, 4]], "MATCH")
        self.assert_outcome("P3-SENSOR-TYPE-ORDER", [[2, 1]], "COUNTEREXAMPLE")
        self.assert_outcome("P3-SENSOR-TYPE-ORDER", [[1, 1]], "COUNTEREXAMPLE")
        self.assert_outcome("P3-SENSOR-TYPE-ORDER", [[True]], "UNKNOWN")
        self.assert_outcome("P3-SENSOR-TYPE-COUNT", [[1, 4], 3], "MATCH")
        self.assert_outcome("P3-SENSOR-TYPE-COUNT", [[1, 4], 3.0], "MATCH")
        self.assert_outcome("P3-SENSOR-TYPE-COUNT", [[1, 4], 1], "COUNTEREXAMPLE")
        for invalid in (True, -1, 1.5):
            with self.subTest(invalid_count=invalid):
                self.assert_outcome("P3-SENSOR-TYPE-COUNT", [[1], invalid], "UNKNOWN")
        self.assert_outcome("P3-SENSOR-TYPE-COUNT", [[True], 1], "UNKNOWN")

    def test_provider_major_parse_distinguishes_mismatch_from_invalid_major(self):
        self.assert_outcome("P3-PROVIDER-PARSE", ["123.0.1.2", 123], "MATCH")
        self.assert_outcome("P3-PROVIDER-PARSE", ["123.0.1.2", 123.0], "MATCH")
        self.assert_outcome("P3-PROVIDER-PARSE", ["123.0.1.2", 122], "COUNTEREXAMPLE")
        self.assert_outcome("P3-PROVIDER-PARSE", ["missing-version", 123], "UNKNOWN")
        for major in (True, "123", 123.5, -1):
            with self.subTest(major=major):
                self.assert_outcome("P3-PROVIDER-PARSE", ["123.0.1.2", major], "UNKNOWN")

    def test_hash_and_literal_gpu_equalities_cannot_be_promoted_from_agreement(self):
        all_candidates = candidates.candidate_templates()
        self.assertEqual(len(TEMPLATES), len(all_candidates))
        for candidate in all_candidates:
            with self.subTest(candidate_id=candidate["candidate_id"]):
                self.assertFalse(candidate["standalone_attack_decision"])
                self.assertEqual(candidate["runtime_integration"], "NOT_INTEGRATED_P4_REQUIRED")
                if candidate["family"] == "HASH" or candidate["candidate_id"] in {"P3-X-GPU-VENDOR", "P3-X-GPU-RENDERER"}:
                    self.assertEqual(candidate["admission_mode"], "descriptive_only")
        self.assert_outcome("P3-X-CANVAS", ["same-hash", "same-hash"], "MATCH")
        for candidate_id in ("P3-X-PLUGIN", "P3-X-MIME"):
            self.assert_outcome(candidate_id, ["", ""], "UNKNOWN")
        self.assertEqual(TEMPLATES["P3-X-CANVAS"]["admission_mode"], "descriptive_only")


if __name__ == "__main__":
    unittest.main()
