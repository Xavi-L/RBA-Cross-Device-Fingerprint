import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main


def collection_status(runtime_error_count: int = 0) -> dict:
    observed_count = main.EXPECTED_EXPANDED_SIGNAL_COUNT - runtime_error_count
    states = {
        f"field_{index}": "runtime_error" if index < runtime_error_count else "observed"
        for index in range(main.EXPECTED_EXPANDED_SIGNAL_COUNT)
    }
    return {
        "status_schema_version": "field-status-v1",
        "fixed_signal_count": main.EXPECTED_EXPANDED_SIGNAL_COUNT,
        "counts": {
            "observed": observed_count,
            "unsupported_by_os": 0,
            "permission_denied": 0,
            "runtime_error": runtime_error_count,
            "timeout": 0,
            "not_applicable": 0,
        },
        "fields": states,
    }


def expanded_payload(runtime_error_count: int = 0) -> dict:
    return {
        "session_id": "contract-test-session",
        "timestamp": 1_700_000_000,
        "collector_app": "featureapp",
        "schema_version": "expanded-v2.2-status",
        "android_native_data": {"placeholder": 1},
        "webview_data": {"placeholder": 1},
        "web_data": {"placeholder": 1},
        "collection_manifest": {
            "manifest_schema_version": "device-profile-manifest-v1",
            "device_manifest_id": "contract-test-device",
            "schema_version": "expanded-v2.2-status",
        },
        "collection_status": collection_status(runtime_error_count),
    }


class CollectionContractTests(unittest.TestCase):
    def test_complete_and_partial_status_are_distinguished(self) -> None:
        self.assertEqual(main.expanded_payload_warnings(expanded_payload()), [])
        self.assertIn(
            "W_COLLECTION_PARTIAL",
            main.expanded_payload_warnings(expanded_payload(runtime_error_count=1)),
        )

    def test_partial_expanded_payload_is_stored_and_receipted_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            expanded_db = temp / "expanded_merged_sessions.json"
            expanded_jsonl = temp / "expanded_collected_data.jsonl"
            receipts_jsonl = temp / "collection_receipts.jsonl"
            raw_payloads_jsonl = temp / "raw_expanded_payloads.jsonl"
            batches_jsonl = temp / "collection_batches.jsonl"
            active_batch_state = temp / "active_collection_batch.json"
            original_db = main.expanded_sessions_db
            original_batch = main.active_collection_batch
            main.expanded_sessions_db = {}
            try:
                with mock.patch.multiple(
                    main,
                    EXPANDED_DB_FILE=expanded_db,
                    EXPANDED_COLLECTED_JSONL_FILE=expanded_jsonl,
                    COLLECTION_RECEIPTS_JSONL_FILE=receipts_jsonl,
                    RAW_EXPANDED_PAYLOADS_JSONL_FILE=raw_payloads_jsonl,
                    COLLECTION_BATCHES_JSONL_FILE=batches_jsonl,
                    ACTIVE_COLLECTION_BATCH_STATE_FILE=active_batch_state,
                ):
                    batch = main.start_collection_batch()
                    payload = expanded_payload(runtime_error_count=1)
                    payload["web_data"] = {}
                    model = main.FingerprintPayload(**payload)
                    first = asyncio.run(main.collect_fingerprint(model))
                    second = asyncio.run(main.collect_fingerprint(model))
                    closed_batch = main.close_active_collection_batch()
            finally:
                main.expanded_sessions_db = original_db
                main.active_collection_batch = original_batch

            self.assertEqual(first["status"], "success")
            self.assertEqual(first["receipt"]["validation_status"], "accepted_with_warnings")
            self.assertTrue(first["receipt"]["stored_new_jsonl_row"])
            self.assertTrue(second["receipt"]["duplicate_payload"])
            self.assertFalse(second["receipt"]["stored_new_jsonl_row"])
            self.assertEqual(len(expanded_jsonl.read_text(encoding="utf-8").splitlines()), 1)
            receipt_rows = [json.loads(line) for line in receipts_jsonl.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(receipt_rows), 2)
            self.assertEqual(receipt_rows[0]["session_id"], "contract-test-session")
            self.assertTrue(receipt_rows[0]["raw_payload_archived"])
            self.assertFalse(receipt_rows[1]["raw_payload_archived"])
            self.assertEqual(receipt_rows[0]["collection_batch_id"], batch["collection_batch_id"])
            self.assertEqual(receipt_rows[1]["collection_batch_id"], batch["collection_batch_id"])
            self.assertEqual(
                receipt_rows[0]["collection_batch_id_source"],
                main.COLLECTION_BATCH_ID_SOURCE,
            )

            raw_rows = [json.loads(line) for line in raw_payloads_jsonl.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(raw_rows), 1)
            self.assertEqual(raw_rows[0]["session_id"], "contract-test-session")
            self.assertEqual(raw_rows[0]["receipt_id"], receipt_rows[0]["receipt_id"])
            self.assertEqual(raw_rows[0]["payload_sha256"], receipt_rows[0]["payload_sha256"])
            self.assertEqual(raw_rows[0]["collection_batch_id"], batch["collection_batch_id"])
            self.assertEqual(
                main.canonical_payload_sha256(raw_rows[0]["canonical_received_payload"]),
                receipt_rows[0]["payload_sha256"],
            )

            batch_events = [
                json.loads(line)
                for line in batches_jsonl.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([event["event"] for event in batch_events], ["started", "closed"])
            self.assertEqual(closed_batch["lifecycle_status"], "closed_cleanly")
            self.assertEqual(closed_batch["receipt_count"], 2)
            self.assertEqual(closed_batch["stored_new_jsonl_row_count"], 1)

    def test_app_observations_preserve_false_null_and_legacy_across_storage_and_retry(self) -> None:
        cases = {
            "false": ("observed", "boolean", False),
            "undefined": ("observed", "undefined", None),
            "runtime_error": ("runtime_error", None, None),
            "legacy": None,
        }
        for name, values in cases.items():
            with self.subTest(observation=name), tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                original_db = main.expanded_sessions_db
                original_batch = main.active_collection_batch
                main.expanded_sessions_db = {}
                try:
                    with mock.patch.multiple(
                        main,
                        EXPANDED_DB_FILE=temp / "expanded_merged_sessions.json",
                        EXPANDED_COLLECTED_JSONL_FILE=temp / "expanded_collected_data.jsonl",
                        COLLECTION_RECEIPTS_JSONL_FILE=temp / "collection_receipts.jsonl",
                        RAW_EXPANDED_PAYLOADS_JSONL_FILE=temp / "raw_expanded_payloads.jsonl",
                        COLLECTION_BATCHES_JSONL_FILE=temp / "collection_batches.jsonl",
                        ACTIVE_COLLECTION_BATCH_STATE_FILE=temp / "active_collection_batch.json",
                    ):
                        main.start_collection_batch()
                        payload = expanded_payload()
                        payload["web_data"] = {"automation_surface_layer": {"webdriver": False}}
                        if values is not None:
                            read_status, value_type, boolean_value = values
                            payload["collection_observations"] = {
                                "observation_schema_version": "app-web-observations-v1",
                                "webdriver": {
                                    "api_present": True,
                                    "presence_read_status": "observed",
                                    "value_read_status": read_status,
                                    "value_type": value_type,
                                    "boolean_value": boolean_value,
                                    "observer_revision": "app-webdriver-observer-v1",
                                    "realm_binding": "featureapp:contract-test-session:main-frame",
                                },
                            }
                        model = main.FingerprintPayload(**payload)
                        first = asyncio.run(main.collect_fingerprint(model))
                        second = asyncio.run(main.collect_fingerprint(model))
                        main.close_active_collection_batch()
                finally:
                    main.expanded_sessions_db = original_db
                    main.active_collection_batch = original_batch

                raw_rows = [json.loads(line) for line in
                            (temp / "raw_expanded_payloads.jsonl").read_text(encoding="utf-8").splitlines()]
                flat_rows = [json.loads(line) for line in
                             (temp / "expanded_collected_data.jsonl").read_text(encoding="utf-8").splitlines()]
                receipts = [json.loads(line) for line in
                            (temp / "collection_receipts.jsonl").read_text(encoding="utf-8").splitlines()]
                merged = json.loads((temp / "expanded_merged_sessions.json").read_text(encoding="utf-8"))
                self.assertEqual((len(raw_rows), len(flat_rows), len(receipts)), (1, 1, 2))
                for saved in (raw_rows[0]["canonical_received_payload"], merged[payload["session_id"]], flat_rows[0]):
                    if values is None:
                        self.assertNotIn("collection_observations", saved)
                    else:
                        self.assertEqual(saved["collection_observations"], payload["collection_observations"])
                        self.assertIs(saved["collection_observations"]["webdriver"]["boolean_value"], values[2])
                    self.assertEqual(saved["collection_status"], payload["collection_status"])
                    self.assertEqual(len(saved["collection_status"]["fields"]), 177)
                self.assertIs(flat_rows[0]["web_data"]["webdriver"], False)
                self.assertEqual(first["receipt"]["validation_warnings"], [])
                self.assertTrue(first["receipt"]["raw_payload_archived"])
                self.assertTrue(second["receipt"]["duplicate_payload"])
                self.assertFalse(second["receipt"]["raw_payload_archived"])
                self.assertFalse(second["receipt"]["stored_new_jsonl_row"])
                self.assertEqual(first["receipt"]["payload_sha256"], second["receipt"]["payload_sha256"])
                self.assertEqual([r["duplicate_payload"] for r in receipts], [False, True])


if __name__ == "__main__":
    unittest.main()
