"""Synthetic W0 transfer boundaries; only frozen definition metadata is read."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hybridguard_agent.research import rule_semantics_runtime_matrix as matrix

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924"
FROZEN = V1 / "R04_freeze_r1"
PROTOCOL = FROZEN / "snapshot/hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol"
W = "app.web_data."
UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7; wv) AppleWebKit/537.36 Version/4.0 Chrome/110.0.0.0 Mobile Safari/537.36"


class RuntimeMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = {
            "definitions": json.loads((FROZEN / "data/definitions.json").read_text()),
            "candidate_definitions": [json.loads(s) for s in (PROTOCOL / "CANDIDATE_LEDGER.jsonl").read_text().splitlines()],
            "rule_definitions": json.loads((ROOT / "hybridguard_agent/config/paired244_rule_catalog.v3.json").read_text())["rules"],
            "control_specs": json.loads((PROTOCOL / "SINGLE_SURFACE_FIELDS.json").read_text())["fields"],
        }

    def setUp(self):
        self.kwargs = deepcopy(self.metadata)
        values = {s["field"]: {"boolean": False, "number": 2, "string": "SYNTHETIC", "array": ["en-US"]}[s["type"]]
                  for s in self.kwargs["control_specs"] if s["surface"] == "app_web67"}
        values.update({W + "navigator_layer.user_agent": UA, W + "navigator_layer.platform": "Linux aarch64",
                       W + "screen_layer.color_depth": 24, W + "screen_layer.pixel_depth": 24,
                       W + "navigator_layer.languages": ["en-US", "fr-FR"]})
        self.payload = {"record_schema_version": "hybridguard-mtc-observation-v2",
                        "adapter_version": "app177-triplet-adapter-v1", "features": values,
                        "field_status": {p: "observed" for p in values},
                        "field_quality": {p: "observed_value" for p in values}}

    def measure(self):
        return matrix.measure_w0_base_inputs(self.payload, **self.kwargs)

    def test_exact_w0_cells_no_extra_core_no_io_and_no_input_mutation(self):
        before = deepcopy((self.payload, self.kwargs))
        with patch.object(matrix, "extract_atom", wraps=matrix.extract_atom) as extract, \
                patch("builtins.open", side_effect=AssertionError("NO_IO")), \
                patch.object(Path, "read_text", side_effect=AssertionError("NO_IO")):
            result = self.measure()
        self.assertEqual(set(result), matrix.W0_ATOM_IDS)
        self.assertEqual(len(result), 48)
        self.assertEqual({c.args[0]["atom_id"] for c in extract.call_args_list},
                         {"CAT:" + name for name in matrix._CATALOG})
        self.assertEqual(extract.call_count, 5)
        self.assertTrue(all(set(c) == {"value", "available", "evaluation_status", "reason"} for c in result.values()))
        self.assertTrue(all(c["evaluation_status"] == "OK" for c in result.values()))
        self.assertEqual((self.payload, self.kwargs), before)

    def test_false_raw_numbers_and_language_length_stay_unfitted(self):
        result = self.measure()
        self.assertIs(result["CONTROL:" + W + "automation_surface_layer.webdriver:EQ:True"]["value"], False)
        memory = result["UNFITTED_CONTROL:" + W + "navigator_layer.device_memory"]
        self.assertEqual(memory["value"], 2)
        self.assertIs(type(memory["value"]), int)
        self.assertEqual(result["UNFITTED_CONTROL:" + W + "navigator_layer.languages"]["value"], 2)
        self.assertFalse(any(":LE:" in name for name in result))

    def test_catalog_polarity_and_fixed_parser_equalities_are_unchanged(self):
        result = self.measure()
        self.assertIs(result["CAT:P3-COLOR-APP"]["value"], True)
        self.assertIs(result["CONTROL:" + W + "navigator_layer.user_agent:EQ:android_webview"]["value"], True)
        self.payload["features"][W + "screen_layer.pixel_depth"] = 16
        self.assertIs(self.measure()["CAT:P3-COLOR-APP"]["value"], False)

    def test_missing_nonobserved_and_ambiguous_numeric_stay_unavailable(self):
        field = W + "navigator_layer.device_memory"
        cases = [("missing", None), ("runtime_error", "SOURCE_STATUS_RUNTIME_ERROR"),
                 ("ambiguous_sentinel", "SOURCE_QUALITY_AMBIGUOUS_SENTINEL")]
        original = deepcopy(self.payload)
        for variant, expected in cases:
            with self.subTest(variant=variant):
                self.payload = deepcopy(original)
                if variant == "missing":
                    del self.payload["features"][field]
                elif variant == "runtime_error":
                    self.payload["field_status"][field] = "runtime_error"
                else:
                    self.payload["features"][field] = 0
                    self.payload["field_quality"][field] = variant
                cell = self.measure()["UNFITTED_CONTROL:" + field]
                self.assertEqual((cell["evaluation_status"], cell["available"], cell["value"]), ("OK", False, None))
                if expected:
                    self.assertEqual(cell["reason"], expected)

    def test_invalid_field_enums_remain_failed_for_numeric_and_catalog(self):
        for field, name in ((W + "navigator_layer.device_memory", "UNFITTED_CONTROL:" + W + "navigator_layer.device_memory"),
                            (W + "screen_layer.color_depth", "CAT:P3-COLOR-APP")):
            with self.subTest(field=field):
                self.payload["field_status"][field] = "INVALID_STATUS"
                cell = self.measure()[name]
                self.assertEqual((cell["evaluation_status"], cell["available"], cell["value"]), ("FAILED", False, None))
                self.assertIn("INVALID_FIELD_STATE_ENUM", cell["reason"])

    def test_other_surfaces_are_removed_before_measurement(self):
        expected = self.measure()
        for section in ("features", "field_status", "field_quality"):
            self.payload[section]["app.android_native_data.build_fingerprint_layer.os_version"] = {"invalid": "unused"}
            self.payload[section]["browser.web_data.navigator_layer.user_agent"] = {"invalid": "unused"}
        self.assertEqual(self.measure(), expected)

    def test_metadata_and_envelope_rejected_before_any_candidate_call(self):
        for variant in ("extra_id", "duplicate_id", "missing_id", "surface", "rule_version", "control_encoder", "label"):
            with self.subTest(variant=variant):
                self.setUp()
                names = self.kwargs["definitions"]["single_surface_allowlists"]["app_web67"]
                if variant == "extra_id":
                    names.append("CAT:EXTRA_CORE")
                elif variant == "duplicate_id":
                    names[-1] = names[0]
                elif variant == "missing_id":
                    names.pop()
                elif variant == "surface":
                    next(a for a in self.kwargs["definitions"]["atoms"] if a["atom_id"] == names[0])["surfaces"] = ["native84"]
                elif variant == "rule_version":
                    next(r for r in self.kwargs["rule_definitions"] if r["rule_id"] == "P3-COLOR-APP")["version"] = "unregistered"
                elif variant == "control_encoder":
                    next(s for s in self.kwargs["control_specs"] if s["field"] == W + "navigator_layer.languages")["encoder"] = "FITTED_THRESHOLD"
                else:
                    self.payload["supervised_label"] = 1
                with patch.object(matrix, "extract_atom", side_effect=AssertionError("MUST_VALIDATE_FIRST")) as extract:
                    with self.assertRaises(ValueError):
                        self.measure()
                    extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
