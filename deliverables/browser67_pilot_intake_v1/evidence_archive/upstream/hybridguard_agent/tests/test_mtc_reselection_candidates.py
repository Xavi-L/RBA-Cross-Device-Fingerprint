"""Full-pool adapter checks using discovery-only MTC and existing fresh inputs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from hybridguard_agent.research import mtc_reselection_candidates as adapter
from hybridguard_agent.research import rule_semantics_webgl1_cap8 as cap8
from hybridguard_agent.research.rule_learning.baselines import transform_numeric
from hybridguard_agent.research.rule_learning.contracts import state
from hybridguard_agent.research.rule_learning.predictor import predict
from hybridguard_agent.research.rule_learning_v2.adapter import approved_atoms
from hybridguard_agent.tests.test_mtc_cap8_replay import legacy_record, MEM, CPU, WD_FIELD, LANGS_FIELD

ROOT = Path(__file__).resolve().parents[2]
PREPARED = ROOT / "deliverables/webgl1_fresh_comparison_v1/prepared"
P2 = ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922"
P1 = ROOT / "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final"
WEBGL = "RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1"
WD = "RSR-WEBDRIVER-STATE-v1"


def discovery_rows():
    # Read only the designated train rows, never materialize evaluation rows.
    members = [json.loads(line) for line in (P2 / "sample_registry.jsonl").read_text().splitlines()]
    selected = {r["source_line"]: r for r in members
                if r["analysis_role"] == "primary_representative" and r["split"] == "discovery"}
    result = []
    with (P1 / "paired_244.jsonl").open() as stream:
        for number, line in enumerate(stream, 1):
            if number in selected:
                row = json.loads(line)
                if row["sample_id"] != selected[number]["sample_id"]:
                    raise AssertionError("Wrong P2 discovery reference")
                result.append(row)
    return result


class CandidateAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs = adapter.definitions()
        cls.prepared = json.loads(next((PREPARED / "inputs").glob("*.json")).read_text())
        cls.records = discovery_rows()

    def test_full_50_candidate_pool_and_unfitted_numeric_inputs(self):
        atoms = approved_atoms(self.defs)
        self.assertEqual(len(atoms), 50)
        self.assertEqual(sum(a.atom_id.startswith("UNFITTED_CONTROL:") for a in atoms), 27)
        for mapped in (adapter.adapt_controlled(self.prepared, self.defs),
                       adapter.adapt_mtc(self.records[0], self.defs)):
            self.assertEqual(set(mapped["raw"]), {a.atom_id for a in atoms})
            self.assertEqual(set(mapped["candidate_inputs"]), set(mapped["raw"]))
            self.assertNotIn(cap8.OLD_WD, mapped["raw"])
            self.assertEqual(len(adapter.input_mapping(self.defs)), 50)

    def test_controlled_projection_equals_original_cap8_and_prediction(self):
        original = json.loads((PREPARED / "DEFINITIONS.json").read_text())
        p = self.prepared
        expected = cap8.project_rows({"opaque": p["features"]}, original, "WEBGL50",
            source_modes={"opaque": "raw_observation_v1"}, candidate_rows={"opaque": p["candidate_cells"]})["opaque"]
        actual = adapter.adapt_controlled(p, self.defs)["raw"]
        self.assertEqual(actual, expected)
        # Saved baseline parity uses its fixed thresholds, with no fit invoked.
        model = cap8.load_model(next((ROOT / "deliverables/webgl1_cap8_comparison_v1/trials").glob(
            "CAP8__WEBGL50__*__RETENTION/model.json")))
        # Independently saved original model encoder declares all base inputs,
        # including unselected ones. Equality rules out a renamed 8-rule pool.
        self.assertEqual(set(actual), set(model.encoder["fixed_atoms"]) | set(model.encoder["numeric"]))
        baseline = cap8.predict_current(model, "opaque", p["features"], p["candidate_cells"],
                                        source_mode="raw_observation_v1")
        encoded = transform_numeric(actual, model.encoder, required_atoms=[a.atom_id for a in model.atoms])
        replay = predict(model, "opaque", {"features": encoded, "view_id": model.view["view_id"]})
        self.assertEqual(replay["decision"], baseline["decision"])
        self.assertEqual(replay["atom_explanations"], baseline["atom_explanations"])

    def test_legacy_raw_modes_cannot_be_confused(self):
        historical = deepcopy(self.records[0])
        historical["source_observation_mode"] = "raw_observation_v1"
        with self.assertRaises(PermissionError):
            adapter.adapt_mtc(historical)
        fresh = deepcopy(self.prepared)
        fresh["observation_mode"] = "legacy_projection_v1"
        with self.assertRaises(PermissionError):
            adapter.adapt_controlled(fresh)
        fresh = deepcopy(self.prepared)
        fresh["candidate_cells"][WD]["diagnostics"]["mode"] = "legacy_projection_v1"
        with self.assertRaises(PermissionError):
            adapter.adapt_controlled(fresh)

    def test_historical_webgl_queries_cannot_be_invented_from_foreign_keys(self):
        r = deepcopy(self.records[0])
        r["collection_observations"] = {"webgl_parameter": {"observation": {"invented": True}}}
        r["features"]["app.web_data.graphics_layer.webgl_renderer"] = "FakeGPU"
        mapped = adapter.adapt_mtc(r)
        self.assertEqual(state(mapped["raw"][WEBGL]), "U")
        self.assertEqual(mapped["raw"][WEBGL]["reason"], "LEGACY_WEBGL1_RAW_QUERY_OBSERVATION_ABSENT")

    def test_legacy_webdriver_true_false_and_wrong_type(self):
        for value, expected in ((True, "T"), (False, "U"), ("false", "U"), (0, "U"), (None, "U")):
            with self.subTest(value=value):
                result = adapter.adapt_mtc(legacy_record(**{WD_FIELD: value}))["raw"][WD]
                self.assertEqual(state(result), expected)
        self.assertEqual(state(adapter.adapt_controlled(self.prepared)["raw"][WD]),
                         state(self.prepared["candidate_cells"][WD]))

    def test_numeric_missing_wrong_type_and_zero_remain_unknown(self):
        for field in (MEM, CPU):
            for value in (0, "8", True, None, float("inf")):
                with self.subTest(field=field, value=value):
                    measured = adapter.adapt_mtc(legacy_record(**{field: value}))["raw"]["UNFITTED_CONTROL:" + field]
                    self.assertFalse(measured["available"])
                    self.assertEqual(measured["evaluation_status"], "OK")
        r = legacy_record()
        del r["features"][MEM]
        self.assertFalse(adapter.adapt_mtc(r)["raw"]["UNFITTED_CONTROL:" + MEM]["available"])
        r["field_status"][CPU] = "invalid-status"
        self.assertEqual(adapter.adapt_mtc(r)["raw"]["UNFITTED_CONTROL:" + CPU]["evaluation_status"], "FAILED")

    def test_languages_length_and_first_relation_are_distinct(self):
        record = legacy_record(**{LANGS_FIELD: ["zh-CN", "en-US", "zh-CN"]})
        mapped = adapter.adapt_mtc(record)["raw"]
        self.assertEqual(mapped["UNFITTED_CONTROL:" + LANGS_FIELD]["value"], 3)
        self.assertEqual(state(mapped[cap8.LANG_ID]), "F")
        record["features"][LANGS_FIELD] = ["zh-CN", 1]
        mapped = adapter.adapt_mtc(record)["raw"]
        self.assertEqual(state(mapped["UNFITTED_CONTROL:" + LANGS_FIELD]), "U")
        # Original first-item relation intentionally does not require valid tail.
        self.assertEqual(state(mapped[cap8.LANG_ID]), "F")

    def test_real_discovery_raw_values_threshold_and_catalog_outputs(self):
        self.assertEqual(len(self.records), 630)
        original = self.records[0]
        raw = adapter.adapt_mtc(original)["raw"]
        # Read real original fields independently; do not derive expectations
        # by calling the same conversion helper.
        for field in (MEM, CPU, "app.web_data.screen_layer.device_pixel_ratio",
                      "app.web_data.execution_layer.timezone_offset"):
            self.assertEqual(raw["UNFITTED_CONTROL:" + field]["value"], original["features"][field])
        self.assertEqual(original["features"][MEM], 8.0)
        self.assertEqual(raw["UNFITTED_CONTROL:" + LANGS_FIELD]["value"], len(original["features"][LANGS_FIELD]))
        self.assertIn("Android", original["features"]["app.web_data.navigator_layer.user_agent"])
        self.assertGreater(original["features"]["app.web_data.navigator_layer.max_touch_points"], 0)
        self.assertEqual(state(raw["CAT:NW-006"]), "F")
        self.assertEqual(state(raw["CAT:NW-007"]), "F")
        self.assertEqual(state(raw["CAT:OFFDER-TOUCH-001"]), "T")
        self.assertEqual(state(raw["CAT:P3-COLOR-APP"]), "T")
        self.assertEqual(state(raw["CAT:WVWEB-004"]), "F")
        self.assertEqual(state(raw["CONTROL:app.web_data.navigator_layer.user_agent:EQ:android_webview"]), "T")
        self.assertEqual(state(raw["CONTROL:app.web_data.permissions_layer.permissions_api_supported:EQ:True"]), "F")
        aid = "CONTROL:" + MEM + ":LE:2.0"
        encoder = {"fixed_atoms": [], "numeric": {"UNFITTED_CONTROL:" + MEM:
            {"thresholds": [2.0], "atom_ids": [aid]}}}
        self.assertEqual(state(transform_numeric(raw, encoder, required_atoms=[aid])[aid]), "F")
        zero = next(r for r in self.records if r["features"].get(MEM) == 0)
        z = adapter.adapt_mtc(zero)
        self.assertEqual(z["candidate_inputs"]["UNFITTED_CONTROL:" + MEM]["fields"][0]["value"], 0)
        self.assertFalse(z["raw"]["UNFITTED_CONTROL:" + MEM]["available"])
        self.assertIn("AMBIGUOUS", z["raw"]["UNFITTED_CONTROL:" + MEM]["reason"])

    def test_metadata_and_unrelated_surface_cannot_change_candidates(self):
        original = self.records[0]
        changed = deepcopy(original)
        changed.update(sample_id="other", label_status="attack", split="development",
                       profile={"model": "other", "manufacturer": "other"}, triplet_id="fake")
        changed["features"]["browser.web_data.navigator_layer.device_memory"] = 1000
        changed["features"]["app.android_native_data.build_fingerprint_layer.device_model"] = "other"
        self.assertEqual(adapter.adapt_mtc(original)["raw"], adapter.adapt_mtc(changed)["raw"])
        fresh = deepcopy(self.prepared)
        fresh.update(opaque_id="other", labels="attack", model="other", collection_task_id="other")
        self.assertEqual(adapter.adapt_controlled(fresh)["raw"], adapter.adapt_controlled(self.prepared)["raw"])

    def test_real_nonbaseline_missing_api_sentinels_are_unknown(self):
        expected = {
            "app.web_data.audio_layer.audio_output_latency": 26,
            "app.web_data.network_api_layer.downlink_mbps": 32,
            "app.web_data.network_api_layer.rtt_ms": 32,
            "app.web_data.screen_layer.visual_viewport_width": 32,
            "app.web_data.screen_layer.visual_viewport_height": 32,
            "app.web_data.screen_layer.visual_viewport_scale": 32,
        }
        for field, count in expected.items():
            rows = [r for r in self.records if r["features"].get(field) == -1]
            self.assertEqual(len(rows), count)
            row = rows[0]
            self.assertEqual(row["field_status"][field], "observed")
            self.assertEqual(row["field_quality"][field], "observed_value")
            mapped = adapter.adapt_mtc(row)
            aid = "UNFITTED_CONTROL:" + field
            self.assertEqual(state(mapped["raw"][aid]), "U")
            self.assertEqual(mapped["raw"][aid]["reason"], "HISTORICAL_COLLECTOR_MINUS_ONE_UNAVAILABLE")
            detail = mapped["candidate_inputs"][aid]["fields"][0]
            self.assertEqual(detail["value"], -1)
            self.assertEqual(detail["source_quality"], "observed_value")

    def test_precise_minus_one_domain_keeps_valid_zero_and_negative_offset(self):
        for field in adapter.HISTORICAL_MINUS_ONE_FIELDS:
            aid = "UNFITTED_CONTROL:" + field
            self.assertEqual(state(adapter.adapt_mtc(legacy_record(**{field: -1}))["raw"][aid]), "U")
        for field, value in (("app.web_data.execution_layer.timezone_offset", -480),
                             ("app.web_data.execution_layer.timezone_offset", -1),
                             ("app.web_data.audio_layer.audio_output_latency", 0),
                             ("app.web_data.network_api_layer.rtt_ms", 0)):
            measured = adapter.adapt_mtc(legacy_record(**{field: value}))["raw"]["UNFITTED_CONTROL:" + field]
            self.assertTrue(measured["available"])
            self.assertEqual(measured["value"], value)
        record = legacy_record(**{"app.web_data.screen_layer.color_depth": -1,
                                  "app.web_data.screen_layer.pixel_depth": 24})
        self.assertEqual(state(adapter.adapt_mtc(record)["raw"]["CAT:P3-COLOR-APP"]), "U")
        # The engineering repair is specific to registered old collectors.
        prepared = deepcopy(self.prepared)
        aid = "UNFITTED_CONTROL:app.web_data.network_api_layer.rtt_ms"
        prepared["features"][aid]["value"] = -1
        self.assertEqual(adapter.adapt_controlled(prepared)["raw"][aid], prepared["features"][aid])

    def test_adaptation_has_no_mutations_and_rejects_pool_changes(self):
        before_defs, before_record, before_prepared = deepcopy(self.defs), deepcopy(self.records[0]), deepcopy(self.prepared)
        adapter.adapt_mtc(self.records[0], self.defs)
        adapter.adapt_controlled(self.prepared, self.defs)
        self.assertEqual(self.defs, before_defs)
        self.assertEqual(self.records[0], before_record)
        self.assertEqual(self.prepared, before_prepared)
        changed = deepcopy(self.defs)
        changed["single_surface_allowlists"]["app_web67"].pop()
        with self.assertRaises(ValueError):
            adapter.adapt_mtc(self.records[0], changed)


if __name__ == "__main__":
    unittest.main()
