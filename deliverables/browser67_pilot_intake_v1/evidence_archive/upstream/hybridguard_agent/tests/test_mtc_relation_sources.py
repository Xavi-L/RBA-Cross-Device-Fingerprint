"""Focused source-boundary tests; no training or evaluation-set reads."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from hybridguard_agent.research import mtc_relation_sources as source


class RelationSourceTests(unittest.TestCase):
    def setUp(self):
        self.sid = "webgl1fresh-session-a"
        self.reference = {"opaque_id": self.sid, "session_id": "session-a",
            "observation_mode": "raw_observation_v1", "source_ref": "runs/env",
            "environment_group_id": "env"}
        self.field = "app.web_data.screen_layer.inner_width"
        self.raw = {"raw_payload_archive_schema_version": "expanded-raw-payload-v1",
            "session_id": "session-a", "receipt_id": "receipt-a", "payload_sha256": "payload-a",
            "canonical_received_payload": {"session_id": "session-a", "collector_app": "featureapp",
                "schema_version": "expanded-v2.2-status",
                "collection_manifest": {"device_manifest_id": "env", "collector_version_code": 14},
                "web_data": {"screen_layer": {"inner_width": 412}},
                "collection_status": {"fields": {self.field.removeprefix("app."): "observed"}}}}
        self.registry = {"sample_id": "mtc-a", "app_session_id": "app-a",
                         "app_payload_sha256": "payload-a", "app_raw_line": 4,
                         "source_view": "paired_244", "source_line": 9}
        self.observation = {"sample_id": "mtc-a", "record_schema_version": "hybridguard-mtc-observation-v2",
            "dataset_view": "paired_244", "app": {"session_id": "app-a", "payload_sha256": "payload-a",
            "collector_version_code": 9}, "source_refs": {"app_raw_line": 4, "browser_raw_line": 8},
            "features": {self.field: 412, "browser.web_data.screen_layer.inner_width": 999},
            "field_status": {self.field: "observed", "browser.web_data.screen_layer.inner_width": "observed"},
            "field_quality": {self.field: "observed_value", "browser.web_data.screen_layer.inner_width": "observed_value"}}

    def controlled(self, raw=None, ref=None):
        return source.bind_controlled_record(self.sid, ref or self.reference, raw or self.raw)

    def mtc(self, obs=None, registry=None):
        return source.bind_mtc_observation(obs or self.observation, "mtc-a", allowed_ids={"mtc-a"},
                                           expected_registry=registry or self.registry)

    def test_controlled_same_acquisition_and_detached_transfer(self):
        before = deepcopy(self.raw)
        result = self.controlled()
        self.assertEqual(result["status"], "OK")
        self.assertTrue(result["source_binding"]["binding_valid"])
        self.assertEqual(result["features"], {self.field: 412})
        self.assertEqual(result["field_quality"][self.field], "observed_value")
        result["features"][self.field] = 5
        self.assertEqual(self.raw, before)

    def test_wrong_outer_inner_session_and_device_are_failures(self):
        for location, key in (("outer", "session_id"), ("payload", "session_id"),
                              ("manifest", "device_manifest_id")):
            with self.subTest(location=location):
                row = deepcopy(self.raw)
                target = row if location == "outer" else row["canonical_received_payload"]
                if location == "manifest":
                    target = target["collection_manifest"]
                target[key] = "another-session-or-device"
                result = self.controlled(row)
                self.assertEqual(result["status"], "FAILED")
                self.assertFalse(result["source_binding"]["binding_valid"])
                self.assertFalse(result["features"])

    def test_wrong_reference_id_or_mode_cannot_authorize_raw(self):
        for key, value in (("opaque_id", "other"), ("observation_mode", "legacy_projection_v1"),
                           ("session_id", "another-session")):
            ref = dict(self.reference, **{key: value})
            self.assertEqual(self.controlled(ref=ref)["status"], "FAILED")

    def test_field_missing_sentinel_type_and_quality_are_preserved(self):
        row = deepcopy(self.raw)
        p = row["canonical_received_payload"]
        p["web_data"]["navigator_layer"] = {"device_memory": 0, "hardware_concurrency": "8"}
        p["web_data"]["screen_layer"]["inner_width"] = -1
        p["collection_status"]["fields"].update({"web_data.navigator_layer.device_memory": "observed",
            "web_data.navigator_layer.hardware_concurrency": "observed"})
        r = self.controlled(row)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["features"][self.field], -1)
        self.assertEqual(r["features"]["app.web_data.navigator_layer.hardware_concurrency"], "8")
        self.assertEqual(r["field_quality"]["app.web_data.navigator_layer.device_memory"], "ambiguous_sentinel")
        self.assertNotIn("app.web_data.screen_layer.inner_height", r["features"])

    def test_missing_unknown_or_unavailable_status_is_not_promoted(self):
        for value in (None, "made-up", {"invalid": "type"}, "runtime_error"):
            row = deepcopy(self.raw)
            row["canonical_received_payload"]["collection_status"]["fields"][self.field.removeprefix("app.")] = value
            r = self.controlled(row)
            self.assertEqual(r["status"], "OK")
            self.assertEqual(r["field_status"][self.field], value)
            self.assertNotEqual(r["field_quality"].get(self.field), "observed_value")

    def test_control_plane_and_browser_values_are_never_transferred(self):
        row = deepcopy(self.raw)
        row["canonical_received_payload"].update(phase="attack", label=1, model_id="model-a",
                                                  browser={"web_data": {"inner_width": 1000}})
        ref = dict(self.reference, phase="clean_post", proposed_supervised_label=1, config_id="tool")
        self.assertEqual(self.controlled(row, ref)["features"], self.controlled()["features"])
        mtc = self.mtc()
        self.assertEqual(mtc["features"], {self.field: 412})
        self.assertNotIn("browser_raw_line", mtc["source_binding"])

    def test_mtc_binding_rejects_every_cross_record_reference(self):
        for key in ("sample_id", "app_session_id", "app_payload_sha256", "app_raw_line", "source_view"):
            registry = dict(self.registry, **{key: "different-record"})
            result = self.mtc(registry=registry)
            self.assertEqual(result["status"], "FAILED", key)
            self.assertFalse(result["features"])

    def test_mtc_missing_app_field_never_borrows_browser(self):
        obs = deepcopy(self.observation)
        for key in ("features", "field_status", "field_quality"):
            del obs[key][self.field]
        result = self.mtc(obs)
        self.assertEqual(result["status"], "OK")
        self.assertFalse(result["features"])

    def test_known_collectors_and_sync_probe_are_explicit(self):
        for result in (self.controlled(), self.mtc()):
            self.assertTrue(result["source_binding"]["same_app_record"])
            self.assertTrue(result["source_binding"]["web_fields_same_sync_probe"])
            self.assertTrue(result["source_binding"]["app_session_id"])
        obs = deepcopy(self.observation)
        obs["app"]["collector_version_code"] = 999
        self.assertEqual(self.mtc(obs)["status"], "FAILED")
        row = deepcopy(self.raw)
        row["canonical_received_payload"]["collection_manifest"]["collector_version_code"] = 11
        self.assertEqual(self.controlled(row)["status"], "FAILED")
        row["canonical_received_payload"]["collection_manifest"]["collector_version_code"] = {"bad": "type"}
        self.assertEqual(self.controlled(row)["status"], "FAILED")
        obs["app"]["collector_version_code"] = [9]
        self.assertEqual(self.mtc(obs)["status"], "FAILED")

    def test_explicit_cross_session_field_claim_is_rejected(self):
        obs = dict(self.observation, field_session_ids={self.field: "app-other"})
        self.assertEqual(self.mtc(obs)["status"], "FAILED")
        row = deepcopy(self.raw)
        row["canonical_received_payload"]["field_session_ids"] = {self.field: "session-other"}
        self.assertEqual(self.controlled(row)["status"], "FAILED")

    def test_stage_guard_rejects_id_before_file_access(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "OUTSIDE_ALLOWED"):
                source.load_controlled_sources([self.sid], allowed_ids={"another-id"})
        with self.assertRaisesRegex(ValueError, "OUTSIDE_ALLOWED"):
            source.bind_mtc_observation(self.observation, "mtc-a", allowed_ids=set(), expected_registry=self.registry)

    def test_loader_selects_only_allowed_session_and_retains_failures(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prepared/evaluation").mkdir(parents=True)
            (root / "runs/env/backend").mkdir(parents=True)
            (root / "prepared/evaluation" / (self.sid + ".json")).write_text(json.dumps(self.reference))
            archive = root / "runs/env/backend/raw_expanded_payloads.jsonl"
            # Deliberately malformed held-out body would fail if parsed.
            archive.write_text('{"session_id":"heldout", "canonical_received_payload": BAD}\n' + json.dumps(self.raw) + "\n")
            opts = dict(allowed_ids={self.sid}, repo_root=root, prepared_dir=root / "prepared")
            result = source.load_controlled_sources([self.sid], **opts)[self.sid]
            self.assertEqual(result["status"], "OK")
            self.assertTrue(result["source_binding"]["raw_reference"].endswith(":2"))
            archive.write_text(json.dumps(self.raw) + "\n" + json.dumps(self.raw) + "\n")
            self.assertIn("RAW_APP_SESSION_NOT_UNIQUE", source.load_controlled_sources([self.sid], **opts)[self.sid]["errors"])
            archive.write_text('{"session_id":"session-a", "canonical_received_payload": BAD}\n')
            self.assertEqual(source.load_controlled_sources([self.sid], **opts)[self.sid]["status"], "FAILED")
            archive.unlink()
            self.assertEqual(source.load_controlled_sources([self.sid], **opts)[self.sid]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
