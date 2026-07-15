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
            original_db = main.expanded_sessions_db
            main.expanded_sessions_db = {}
            try:
                with mock.patch.multiple(
                    main,
                    EXPANDED_DB_FILE=expanded_db,
                    EXPANDED_COLLECTED_JSONL_FILE=expanded_jsonl,
                    COLLECTION_RECEIPTS_JSONL_FILE=receipts_jsonl,
                ):
                    payload = expanded_payload(runtime_error_count=1)
                    payload["web_data"] = {}
                    model = main.FingerprintPayload(**payload)
                    first = asyncio.run(main.collect_fingerprint(model))
                    second = asyncio.run(main.collect_fingerprint(model))
            finally:
                main.expanded_sessions_db = original_db

            self.assertEqual(first["status"], "success")
            self.assertEqual(first["receipt"]["validation_status"], "accepted_with_warnings")
            self.assertTrue(first["receipt"]["stored_new_jsonl_row"])
            self.assertTrue(second["receipt"]["duplicate_payload"])
            self.assertFalse(second["receipt"]["stored_new_jsonl_row"])
            self.assertEqual(len(expanded_jsonl.read_text(encoding="utf-8").splitlines()), 1)
            receipt_rows = [json.loads(line) for line in receipts_jsonl.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(receipt_rows), 2)
            self.assertEqual(receipt_rows[0]["session_id"], "contract-test-session")


if __name__ == "__main__":
    unittest.main()
