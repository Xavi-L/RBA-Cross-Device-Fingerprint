"""Geometry remains auxiliary evidence, including unavailable values and attempts."""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import main
from test_collection_contract import expanded_payload


class GeometryObservationStorageTests(unittest.TestCase):
    def test_geometry_null_error_attempts_and_existing_observers_roundtrip_once(self):
        payload = expanded_payload()
        payload["web_data"] = {"screen_layer": {"inner_height": 0, "device_pixel_ratio": 1}}
        payload["collection_observations"] = {
            "observation_schema_version": "app-web-observations-v1",
            "webdriver": {"boolean_value": False, "value_read_status": "observed"},
            "webgl_parameter": {"read_status": "runtime_error", "observation": None, "reason": "prior_error"},
            "geometry_document_id": "document:fixture",
            "webview_geometry": {
                "schema_version": "webview-geometry-v1", "status": "partial",
                "observation_id": "geometry:fixture", "session_id": payload["session_id"],
                "attempts": [{"status": "timeout", "web": None, "host_after": None,
                              "reason": "javascript_callback_timeout"},
                             {"status": "stable", "web": {"fields": {
                                 "inner_width": {"value": 0, "status": "observed"},
                                 "visual_viewport_scale": {"value": None, "status": "runtime_error",
                                                           "reason": "getter_failed"}}}}],
                "host": {"scale": None, "scale_status": "unavailable", "insets_supported": False},
            },
        }
        original = copy.deepcopy(payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patch_paths = {name: root / filename for name, filename in {
                "EXPANDED_DB_FILE": "merged.json", "EXPANDED_COLLECTED_JSONL_FILE": "flat.jsonl",
                "COLLECTION_RECEIPTS_JSONL_FILE": "receipts.jsonl", "RAW_EXPANDED_PAYLOADS_JSONL_FILE": "raw.jsonl",
                "COLLECTION_BATCHES_JSONL_FILE": "batches.jsonl", "ACTIVE_COLLECTION_BATCH_STATE_FILE": "active.json",
            }.items()}
            with mock.patch.multiple(main, **patch_paths), mock.patch.object(main, "expanded_sessions_db", {}), \
                    mock.patch.object(main, "active_collection_batch", None):
                main.start_collection_batch()
                model = main.FingerprintPayload(**payload)
                first = asyncio.run(main.collect_fingerprint(model))
                retry = asyncio.run(main.collect_fingerprint(model))
                main.close_active_collection_batch()
            raws = [json.loads(line) for line in (root / "raw.jsonl").read_text().splitlines()]
            flats = [json.loads(line) for line in (root / "flat.jsonl").read_text().splitlines()]
            merged = json.loads((root / "merged.json").read_text())[payload["session_id"]]
            self.assertEqual((len(raws), len(flats)), (1, 1))
            for saved in (raws[0]["canonical_received_payload"], flats[0], merged):
                self.assertEqual(saved["collection_observations"], original["collection_observations"])
                self.assertEqual(saved["collection_status"], original["collection_status"])
                self.assertEqual(len(saved["collection_status"]["fields"]), 177)
            self.assertEqual(raws[0]["canonical_received_payload"]["web_data"], original["web_data"])
            self.assertEqual(flats[0]["web_data"], {"inner_height": 0, "device_pixel_ratio": 1})
            self.assertTrue(first["receipt"]["stored_new_jsonl_row"])
            self.assertTrue(retry["receipt"]["duplicate_payload"])
            self.assertFalse(retry["receipt"]["stored_new_jsonl_row"])
            self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
