"""Fixed-model historical replay boundaries; never fit or alter saved inputs."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research import mtc_cap8_data as data
from hybridguard_agent.research import mtc_cap8_replay as replay
from hybridguard_agent.research import rule_semantics_webgl1_cap8 as cap8


ROOT = Path(__file__).resolve().parents[2]
TRIALS = ROOT / "deliverables/webgl1_cap8_comparison_v1/trials"
PREPARED = ROOT / "deliverables/webgl1_fresh_comparison_v1/prepared/inputs"
SNAPSHOT = ROOT / "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final"
WD = "RSR-WEBDRIVER-STATE-v1"
LANG = "RSR-LANG-FIRST-v1"
WEBGL = "RSR-WEBGL1-PARAMETER-EQUIVALENCE-v1"
MEM = "app.web_data.navigator_layer.device_memory"
CPU = "app.web_data.navigator_layer.hardware_concurrency"
DPR = "app.web_data.screen_layer.device_pixel_ratio"
TZ = "app.web_data.execution_layer.timezone_offset"
MIME = "app.web_data.automation_surface_layer.mime_types_count"
WD_FIELD = "app.web_data.automation_surface_layer.webdriver"
LANG_FIELD = "app.web_data.navigator_layer.language"
LANGS_FIELD = "app.web_data.navigator_layer.languages"
PLATFORM = "app.web_data.navigator_layer.platform"
UA = "app.web_data.navigator_layer.user_agent"


def legacy_record(**values):
    """Synthetic old MTC row using explicit source status, quality and version."""
    features = {
        MEM: 2.0, CPU: 8, DPR: 2.0, TZ: -480, MIME: 0, WD_FIELD: False,
        LANG_FIELD: "zh-CN", LANGS_FIELD: ["zh-CN"], PLATFORM: "Linux armv8l",
        UA: "Mozilla/5.0 (Linux; Android 13; TestPhone Build/TEST; wv) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
            "Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    features.update(values)
    return {
        "record_schema_version": "hybridguard-mtc-observation-v2",
        "sample_id": "synthetic-mtc-row",
        "app": {"collector_version_code": 9,
                "collector_version_name": "1.6.2-expanded-v2.2-mtc",
                "session_id": "synthetic-session"},
        "features": features,
        "field_status": dict.fromkeys(features, "observed"),
        "field_quality": dict.fromkeys(features, "observed_value"),
        "profile": {"model": "TestPhone", "manufacturer": "Test", "android_release": "13"},
        "label_status": "unlabeled",
        "source_refs": {}, "qc": {},
    }


def atom_result(prediction, atom_id):
    return next(r for r in prediction["rule_results"] if r["atom_id"] == atom_id)


class HistoricalReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_paths = sorted(TRIALS.glob("CAP8__WEBGL50__*__RETENTION/model.json"))
        if len(cls.model_paths) != 3:
            raise AssertionError("Expected all three existing WEBGL50/CAP8/RETENTION models")
        cls.models = [cap8.load_model(p) for p in cls.model_paths]

    def test_three_saved_model_identities_are_used_without_fit(self):
        self.assertEqual(len({m.model_id for m in self.models}), 3)
        with patch.object(cap8, "fit_sparse", side_effect=AssertionError("No training")), \
             patch.object(cap8, "fit_retention", side_effect=AssertionError("No training")):
            for model in self.models:
                with self.subTest(model=model.model_id):
                    result = replay.predict_historical_mtc(model, legacy_record())
                    self.assertEqual(result["model_id"], model.model_id)
                    self.assertEqual(len(model.clauses), 8)
                    self.assertEqual(len(result["rule_results"]), 8)
                    self.assertEqual(result["source_observation_mode"], "legacy_projection_v1")
                    self.assertTrue(result["adapter_version"])

    def test_original_current_entry_remains_raw_only(self):
        with self.assertRaises(PermissionError):
            cap8.predict_current(self.models[0], "legacy", {}, source_mode="legacy_projection_v1")
        adapted = replay.adapt_historical_mtc(self.models[0], legacy_record())
        rejected = replay.predict_replay(self.models[0], "wrong-mode", adapted["raw"],
            adapted["candidate_cells"], source_mode="raw_observation_v1")
        self.assertEqual(rejected["decision"], "FAILED")
        self.assertIn("MODE", rejected["failure_reason"])

    def test_unsupported_record_or_collector_is_not_promoted_to_legacy(self):
        for change in ({"record_schema_version": "expanded-v2.2-status"},
                       {"app": {"collector_version_code": 999, "collector_version_name": "unknown"}},
                       {"app": {"collector_version_code": 11,
                                "collector_version_name": "1.6.4-expanded-v2.2-mtc"}}):
            record = legacy_record()
            record.update(change)
            with self.subTest(change=change):
                result = replay.predict_historical_mtc(self.models[0], record)
                self.assertEqual(result["decision"], "FAILED")
                self.assertTrue(result["failure_reason"])

    def test_both_saved_mtc_collector_versions_are_supported(self):
        for code, name in ((9, "1.6.2-expanded-v2.2-mtc"), (11, "1.6.4-expanded-v2.2-mtc-https")):
            with self.subTest(code=code):
                record = legacy_record()
                record["app"].update(collector_version_code=code, collector_version_name=name)
                result = replay.predict_historical_mtc(self.models[0], record)
                self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")
                self.assertEqual(result["source_observation_mode"], "legacy_projection_v1")

    def test_webgl_missing_raw_stays_unknown_despite_gpu_names(self):
        record = legacy_record()
        record["features"].update({
            "app.web_data.graphics_layer.webgl_vendor": "Qualcomm",
            "app.web_data.graphics_layer.webgl_renderer": "Adreno (TM) 740",
            "browser.web_data.graphics_layer.webgl_vendor": "ARM",
        })
        result = replay.predict_historical_mtc(self.models[0], record)
        webgl = atom_result(result, WEBGL)
        self.assertEqual(webgl["state"], "U")
        self.assertTrue(webgl["reason"])
        self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")

    def test_legacy_webdriver_true_false_and_lost_information(self):
        for value, expected in ((True, "T"), (False, "U"), (None, "U"), (0, "U"), ("false", "U")):
            with self.subTest(value=value):
                result = replay.predict_historical_mtc(self.models[0], legacy_record(**{WD_FIELD: value}))
                wd = atom_result(result, WD)
                self.assertEqual(wd["state"], expected)
                if value is False:
                    self.assertIn("LEGACY_NONTRUE_PROJECTION_AMBIGUOUS", wd["reason"])
                self.assertEqual(result["decision"], "MANIPULATION_ALERT" if value is True
                                 else "INSUFFICIENT_EVIDENCE")

    def test_false_projection_does_not_gain_raw_information(self):
        record = legacy_record()
        record["collection_observations"] = {"webdriver": {
            "api_present": True, "presence_read_status": "observed",
            "value_read_status": "observed", "value_type": "boolean", "boolean_value": False,
            "observer_revision": "invented", "realm_binding": "invented",
        }}
        result = replay.predict_historical_mtc(self.models[0], record)
        self.assertEqual(atom_result(result, WD)["state"], "U")
        self.assertEqual(atom_result(result, WEBGL)["state"], "U")
        self.assertEqual(result["source_observation_mode"], "legacy_projection_v1")

    def test_numeric_values_keep_units_and_zero_sentinels(self):
        for field, valid in ((MEM, 4.0), (CPU, 8), (DPR, 2.625), (TZ, -480), (MIME, 0)):
            with self.subTest(field=field):
                measured = replay.measure_historical_numeric(legacy_record(**{field: valid}), field)
                self.assertTrue(measured["available"])
                self.assertEqual(measured["value"], valid)
                self.assertIs(type(measured["value"]), type(valid))
        for field in (MEM, CPU):
            with self.subTest(default_zero=field):
                measured = replay.measure_historical_numeric(legacy_record(**{field: 0}), field)
                self.assertFalse(measured["available"])
                self.assertIsNone(measured["value"])
                self.assertEqual(measured["reason"], "AMBIGUOUS_NAVIGATOR_SENTINEL")

    def test_missing_numeric_wrong_types_and_unavailable_status_are_unknown(self):
        for invalid in (None, "4", True, [], {}, float("inf"), float("nan")):
            with self.subTest(invalid=invalid):
                measured = replay.measure_historical_numeric(legacy_record(**{MEM: invalid}), MEM)
                self.assertFalse(measured["available"])
                self.assertEqual(measured["evaluation_status"], "OK")
        for missing_section in ("features", "field_status", "field_quality"):
            record = legacy_record()
            del record[missing_section][MEM]
            self.assertFalse(replay.measure_historical_numeric(record, MEM)["available"])
        record = legacy_record(**{MEM: 8})
        record["field_status"][MEM] = "unsupported_by_os"
        measured = replay.measure_historical_numeric(record, MEM)
        self.assertFalse(measured["available"])
        self.assertEqual(measured["reason"], "SOURCE_STATUS_UNSUPPORTED_BY_OS")

    def test_invalid_measurement_status_is_execution_failure_not_unknown(self):
        record = legacy_record()
        record["field_status"][MEM] = "not-a-real-status"
        result = replay.predict_historical_mtc(self.models[0], record)
        self.assertEqual(result["decision"], "FAILED")
        self.assertTrue(result["failure_reason"])

    def test_three_valued_or_and_saved_negative_numeric_polarity(self):
        for model in self.models:
            with self.subTest(model=model.model_id):
                baseline = replay.predict_historical_mtc(model, legacy_record())
                self.assertEqual(baseline["logical_state"], "U")  # F OR U = U
                memory = replay.predict_historical_mtc(model, legacy_record(**{MEM: 4}))
                self.assertEqual(memory["logical_state"], "T")  # T OR U = T
                self.assertEqual(memory["decision"], "MANIPULATION_ALERT")
                memory_atom = next(a for a in model.atoms if a.provenance.get("field") == MEM)
                self.assertEqual(atom_result(memory, memory_atom.atom_id)["atom_state"], "F")
                self.assertEqual(atom_result(memory, memory_atom.atom_id)["state"], "T")
                self.assertIn(memory_atom.atom_id, [l["atom_id"] for c in memory["clause_explanations"]
                                                   if c["state"] == "T" for l in c["literals"]])

    def test_language_and_ua_platform_use_values_and_source_availability(self):
        for changes, atom in (({LANGS_FIELD: ["en-US", "zh-CN"]}, LANG),
                              ({PLATFORM: "Win32"}, "CAT:NW-006")):
            result = replay.predict_historical_mtc(self.models[0], legacy_record(**changes))
            self.assertEqual(atom_result(result, atom)["state"], "T")
            self.assertEqual(result["decision"], "MANIPULATION_ALERT")
        record = legacy_record(**{LANGS_FIELD: ["en-US"]})
        record["field_quality"][LANGS_FIELD] = "source_unavailable"
        self.assertEqual(atom_result(replay.predict_historical_mtc(self.models[0], record), LANG)["state"], "U")

    def test_identifiers_labels_models_and_browser_values_do_not_change_predictions(self):
        record = legacy_record(**{MEM: 4})
        changed = deepcopy(record)
        changed.update(sample_id="another-id", label_status="attack", manipulation_present=True,
                       split="validation", collection_batch_id="different-batch",
                       profile={"model": "OtherPhone", "manufacturer": "Other", "android_release": "99"})
        changed["features"]["browser.web_data.navigator_layer.device_memory"] = 0
        changed["features"]["app.android_native_data.build_fingerprint_layer.device_model"] = "OtherPhone"
        original_result = replay.predict_historical_mtc(self.models[0], record)
        changed_result = replay.predict_historical_mtc(self.models[0], changed)
        for key in ("logical_state", "decision", "clause_explanations", "rule_results"):
            self.assertEqual(original_result[key], changed_result[key], key)

    def test_saved_full_raw_inputs_match_original_current_predictor(self):
        # Two existing inputs suffice to exercise the path without a new experiment.
        paths_by_phase = {}
        for metadata_path in sorted((PREPARED.parent / "evaluation").glob("*.json")):
            phase = json.loads(metadata_path.read_text())["phase"]
            if phase in ("clean_pre", "attack"):
                paths_by_phase.setdefault(phase, PREPARED / metadata_path.name)
            if len(paths_by_phase) == 2:
                break
        self.assertEqual(set(paths_by_phase), {"clean_pre", "attack"}, "Saved raw parity fixtures must exist")
        paths = list(paths_by_phase.values())
        observed_decisions = set()
        for path in paths:
            prepared = json.loads(path.read_text())
            for model in self.models:
                with self.subTest(input=path.name, model=model.model_id):
                    expected = cap8.predict_current(model, prepared["opaque_id"], prepared["features"],
                        prepared["candidate_cells"], source_mode="raw_observation_v1")
                    actual = replay.predict_replay(model, prepared["opaque_id"], prepared["features"],
                        prepared["candidate_cells"], source_mode="raw_observation_v1")
                    self.assertNotEqual(expected["decision"], "FAILED")
                    observed_decisions.add(actual["decision"])
                    for key, value in expected.items():
                        self.assertEqual(actual[key], value, key)
        self.assertEqual(observed_decisions, {"NO_ALERT", "MANIPULATION_ALERT"})

    def test_prediction_keeps_models_source_records_and_existing_files_unchanged(self):
        paths = self.model_paths + [ROOT / "deliverables/webgl1_cap8_comparison_v1/RESULTS.json",
                                   SNAPSHOT / "paired_244.jsonl"]
        before_files = {path: path.read_bytes() for path in paths}
        record = legacy_record()
        before_record = deepcopy(record)
        before_models = [deepcopy(m.to_dict()) for m in self.models]
        for model in self.models:
            replay.predict_historical_mtc(model, record)
        self.assertEqual(record, before_record)
        self.assertEqual([m.to_dict() for m in self.models], before_models)
        self.assertEqual({path: path.read_bytes() for path in paths}, before_files)


class HistoricalDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.p2 = self.root / "p2"
        self.snapshot = self.root / "snapshot"
        self.freeze = self.root / "freeze"
        for path in (self.p2, self.snapshot, self.freeze / "sources"):
            path.mkdir(parents=True)
        for view in data.VIEWS:
            (self.snapshot / f"{view}.jsonl").write_text("")
        (self.snapshot / "manifest.json").write_text(json.dumps({"view_counts": {"app_only_177": 1}}))
        for name in ("raw_expanded_payloads", "collection_batches"):
            (self.freeze / "sources" / f"{name}.jsonl").write_text("")
        self.record = legacy_record()
        self.record["dataset_view"] = "app_only_177"
        self.registry = {
            "sample_id": self.record["sample_id"], "source_view": "app_only_177", "source_line": 1,
            "analysis_role": "reserve_app_only_177", "profile": self.record["profile"],
            "split": "development", "app_raw_line": 1,
        }
        self._write_rows(self.p2 / "sample_registry.jsonl", [self.registry])
        self._write_rows(self.snapshot / "app_only_177.jsonl", [self.record])

    @staticmethod
    def _write_rows(path, rows):
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    def load(self):
        return data.load_mtc_replay_data(repo_root=self.root, p2_dir=self.p2,
                                         snapshot_dir=self.snapshot, freeze_dir=self.freeze)

    def test_app_only_without_raw_normal_basis_still_reaches_replay(self):
        loaded = self.load()
        self.assertEqual(len(loaded["records"]), 1)
        record = loaded["records"][0]
        self.assertIsNone(record["load_error"])
        self.assertEqual(record["observation"], self.record)
        self.assertFalse(record["normal_basis"]["supported"])
        self.assertIn("raw_app_record_unavailable", record["normal_basis"]["reasons"])
        model = cap8.load_model(sorted(TRIALS.glob("CAP8__WEBGL50__*__RETENTION/model.json"))[0])
        self.assertEqual(replay.predict_historical_mtc(model, record["observation"])["decision"],
                         "INSUFFICIENT_EVIDENCE")

    def test_missing_source_file_keeps_the_planned_record_and_failure(self):
        (self.snapshot / "app_only_177.jsonl").unlink()
        loaded = self.load()
        self.assertEqual(len(loaded["records"]), 1)
        self.assertIsNone(loaded["records"][0]["observation"])
        self.assertTrue(loaded["records"][0]["load_error"])
        summary = loaded["inventory"]["subsets"]["reserve_app_only_177"]
        self.assertEqual((summary["planned"], summary["readable"], summary["load_failures"]), (1, 0, 1))
        self.assertTrue(any("app_only_177.jsonl" in i.get("path", "") for i in loaded["issues"]))

    def test_corrupt_source_line_is_not_dropped_or_shifted(self):
        records = [self.record | {"sample_id": f"record-{i}"} for i in range(1, 4)]
        registry = [self.registry | {"sample_id": r["sample_id"], "source_line": i}
                    for i, r in enumerate(records, 1)]
        self._write_rows(self.p2 / "sample_registry.jsonl", registry)
        (self.snapshot / "app_only_177.jsonl").write_text(
            json.dumps(records[0]) + "\n{broken\n" + json.dumps(records[2]) + "\n")
        loaded = self.load()
        self.assertEqual([r["sample_id"] for r in loaded["records"]], [r["sample_id"] for r in records])
        self.assertEqual([r["load_error"] is None for r in loaded["records"]], [True, False, True])
        self.assertEqual(loaded["records"][2]["observation"], records[2])

    def test_unreadable_registry_line_is_counted_separately(self):
        with (self.p2 / "sample_registry.jsonl").open("a") as stream:
            stream.write("not-json\n")
        loaded = self.load()
        self.assertEqual(len(loaded["records"]), 2)
        self.assertEqual(loaded["inventory"]["p2_registry_invalid_rows"], 1)
        malformed = loaded["records"][1]
        self.assertEqual(malformed["subset"], "unassigned_registry_error")
        self.assertTrue(malformed["load_error"])

    def test_current_saved_p2_membership_is_preserved_with_separate_denominators(self):
        loaded = data.load_mtc_replay_data()
        registry_path = ROOT / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922/sample_registry.jsonl"
        registry = [json.loads(line) for line in registry_path.read_text().splitlines()]
        self.assertEqual([r["sample_id"] for r in loaded["records"]], [r["sample_id"] for r in registry])
        self.assertEqual(Counter(r["subset"] for r in loaded["records"]),
                         Counter(r["analysis_role"] for r in registry))
        self.assertEqual(len(loaded["records"]), 1699)
        self.assertFalse(loaded["issues"])
        expected = {"primary_representative": 891, "paired_repeat_observation": 137,
                    "reserve_app_only_177": 654, "reserve_partial": 11,
                    "reserve_repeated_observations": 6}
        self.assertEqual({k: v["planned"] for k, v in loaded["inventory"]["subsets"].items()}, expected)
        self.assertTrue(all(r["load_error"] is None for r in loaded["records"]))


if __name__ == "__main__":
    unittest.main()
