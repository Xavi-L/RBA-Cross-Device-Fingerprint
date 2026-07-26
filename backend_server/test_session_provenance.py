import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import export_session_provenance as provenance


def canonical_archive(
    session_id,
    timestamp,
    brand,
    model,
    os_version,
    api,
    collection_batch_id=None,
):
    payload = {
        "session_id": session_id,
        "timestamp": timestamp,
        "collector_app": "featureapp",
        "schema_version": "expanded-v2.2-status",
        "android_native_data": {
            "build_fingerprint_layer": {
                "device_brand": brand,
                "device_model": model,
                "os_version": os_version,
                "os_api_level": api,
            }
        },
        "webview_data": {
            "kernel_container_layer": {
                "webview_provider_package": "com.google.android.webview",
                "webview_provider_version": "123.0.0.0",
            },
            "host_security_layer": {
                "app_package_name": "com.example.hybridguard.featureapp",
                "app_version_name": "1.2.1-expanded-v2.2-status",
                "app_version_code": 3,
            },
        },
        "web_data": {"navigator_layer": {"language": "zh-CN"}},
    }
    payload_hash = provenance.canonical_payload_sha256(payload)
    archive = {
        "raw_payload_archive_schema_version": "expanded-raw-payload-v1",
        "session_id": session_id,
        "receipt_id": f"receipt-{session_id}",
        "payload_sha256": payload_hash,
        "canonical_received_payload": payload,
    }
    if collection_batch_id is not None:
        archive["collection_batch_id"] = collection_batch_id
        archive["collection_batch_id_source"] = provenance.BACKEND_BATCH_ID_SOURCE
    return archive


def receipt(session_id, payload_hash, received_at, collection_batch_id=None):
    result = {
        "receipt_id": f"receipt-{session_id}",
        "session_id": session_id,
        "payload_sha256": payload_hash,
        "server_received_at": received_at,
        "stored_new_jsonl_row": True,
        "validation_status": "accepted",
        "validation_warnings": [],
    }
    if collection_batch_id is not None:
        result["collection_batch_id"] = collection_batch_id
        result["collection_batch_id_source"] = provenance.BACKEND_BATCH_ID_SOURCE
    return result


def batch_event(event, batch_id, timestamp, **extra):
    return {
        "collection_batch_schema_version": provenance.BACKEND_BATCH_SCHEMA_VERSION,
        "event": event,
        "collection_batch_id": batch_id,
        **extra,
        "started_at": extra.get("started_at", timestamp),
        "ended_at": extra.get("ended_at", timestamp) if event == "closed" else None,
    }


class SessionProvenanceTests(unittest.TestCase):
    def test_key_file_is_private_and_environment_can_override_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = Path(temp_dir) / "profile.key"
            key_file.write_text("file-key\n", encoding="utf-8")
            key_file.chmod(0o600)
            with mock.patch.dict(os.environ, {"TEST_PROFILE_HMAC_KEY": ""}, clear=False):
                key, source = provenance.load_profile_hmac_key("TEST_PROFILE_HMAC_KEY", key_file)
            self.assertEqual(key, "file-key")
            self.assertEqual(source, "file")

            with mock.patch.dict(
                os.environ,
                {"TEST_PROFILE_HMAC_KEY": "environment-key"},
                clear=False,
            ):
                key, source = provenance.load_profile_hmac_key("TEST_PROFILE_HMAC_KEY", key_file)
            self.assertEqual(key, "environment-key")
            self.assertEqual(source, "environment")

            key_file.chmod(0o644)
            with mock.patch.dict(os.environ, {"TEST_PROFILE_HMAC_KEY": ""}, clear=False):
                with self.assertRaises(provenance.ProvenanceError):
                    provenance.load_profile_hmac_key("TEST_PROFILE_HMAC_KEY", key_file)

    def test_rounds_follow_first_receipt_order_and_os_splits_profile(self):
        first = canonical_archive("s1", 1, "Google", "Pixel 8", "Android 14", 34)
        second = canonical_archive("s2", 2, "Google", "Pixel 8", "Android 14", 34)
        third = canonical_archive("s3", 3, "Google", "Pixel 8", "Android 15", 35)
        payload_entries = [(1, second), (2, third), (3, first)]
        receipt_entries = [
            (1, receipt("s2", second["payload_sha256"], "2026-07-25T00:00:02Z")),
            (2, receipt("s3", third["payload_sha256"], "2026-07-25T00:00:03Z")),
            (3, receipt("s1", first["payload_sha256"], "2026-07-25T00:00:01Z")),
        ]

        records = provenance.build_provenance_records(
            payload_entries=payload_entries,
            receipt_entries=receipt_entries,
            platform_provider="wetest",
            collection_batch_id="wetest-20260725-01",
            profile_hmac_key="test-only-key",
            payload_source_name="raw_expanded_payloads.jsonl",
        )

        by_session = {record["session_id"]: record for record in records}
        self.assertEqual(by_session["s1"]["collection_round"], 1)
        self.assertEqual(by_session["s2"]["collection_round"], 2)
        self.assertEqual(by_session["s3"]["collection_round"], 1)
        self.assertEqual(by_session["s1"]["profile_id"], by_session["s2"]["profile_id"])
        self.assertNotEqual(by_session["s1"]["profile_id"], by_session["s3"]["profile_id"])
        self.assertTrue(by_session["s1"]["raw_payload_available"])
        self.assertEqual(
            by_session["s1"]["payload_sha256_verification"],
            "verified_canonical_raw_archive",
        )
        self.assertEqual(by_session["s1"]["device_hash"], by_session["s1"]["profile_id"])
        self.assertFalse(by_session["s1"]["device_hash_is_platform_device_id"])

    def test_legacy_flattened_record_is_exported_with_explicit_boundary(self):
        legacy_payload = {
            "session_id": "legacy-s1",
            "collector_app": "featureapp",
            "schema_version": "expanded-v2",
            "android_native_data": {
                "device_brand": "HONOR",
                "device_model": "ELZ-AN00",
                "os_version": "Android 12",
                "os_api_level": 31,
            },
            "webview_data": {"app_version_name": "1.0"},
        }
        records = provenance.build_provenance_records(
            payload_entries=[(1, legacy_payload)],
            receipt_entries=[
                (
                    1,
                    receipt(
                        "legacy-s1",
                        "not-reconstructible-from-flattened-data",
                        "2026-07-25T01:00:00Z",
                    ),
                )
            ],
            platform_provider="wetest",
            collection_batch_id="legacy-01",
            profile_hmac_key="test-only-key",
            payload_source_name="expanded_collected_data.jsonl",
        )
        self.assertFalse(records[0]["raw_payload_available"])
        self.assertEqual(
            records[0]["payload_sha256_verification"],
            "not_verifiable_from_flattened_analysis_record",
        )
        self.assertEqual(
            records[0]["collection_batch_id_source"],
            provenance.LEGACY_BATCH_ID_SOURCE,
        )

    def test_latest_closed_backend_batch_is_selected_and_rounds_restart(self):
        batch_one = "hgbatch-v1-one"
        batch_two = "hgbatch-v1-two"
        first = canonical_archive(
            "batch-one-s1", 1, "Google", "Pixel 8", "Android 14", 34, batch_one
        )
        second = canonical_archive(
            "batch-two-s1", 2, "Google", "Pixel 8", "Android 14", 34, batch_two
        )
        third = canonical_archive(
            "batch-two-s2", 3, "Google", "Pixel 8", "Android 14", 34, batch_two
        )
        receipts = [
            (1, receipt("batch-one-s1", first["payload_sha256"], "2026-07-26T00:00:01Z", batch_one)),
            (2, receipt("batch-two-s1", second["payload_sha256"], "2026-07-26T00:01:01Z", batch_two)),
            (3, receipt("batch-two-s2", third["payload_sha256"], "2026-07-26T00:01:02Z", batch_two)),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "collection_batches.jsonl"
            events = [
                batch_event("started", batch_one, "2026-07-26T00:00:00Z"),
                batch_event(
                    "closed",
                    batch_one,
                    "2026-07-26T00:00:10Z",
                    lifecycle_status="closed_cleanly",
                    ended_at_source="graceful_shutdown_hook",
                ),
                batch_event("started", batch_two, "2026-07-26T00:01:00Z"),
                batch_event(
                    "closed",
                    batch_two,
                    "2026-07-26T00:01:10Z",
                    lifecycle_status="closed_cleanly",
                    ended_at_source="graceful_shutdown_hook",
                ),
            ]
            ledger.write_text(
                "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
            )
            context = provenance.resolve_collection_batch_context(
                requested_batch_id=None,
                batch_ledger=ledger,
            )

        selected_payloads = provenance.select_payload_entries_for_batch(
            [(1, first), (2, second), (3, third)],
            context,
        )
        records = provenance.build_provenance_records(
            payload_entries=selected_payloads,
            receipt_entries=receipts,
            platform_provider="wetest",
            collection_batch_id=context["collection_batch_id"],
            collection_batch_id_source=context["collection_batch_id_source"],
            collection_batch_lifecycle_status=context["collection_batch_lifecycle_status"],
            collection_batch_started_at=context["collection_batch_started_at"],
            collection_batch_ended_at=context["collection_batch_ended_at"],
            collection_batch_ended_at_source=context["collection_batch_ended_at_source"],
            collection_batch_ledger=context["collection_batch_ledger"],
            profile_hmac_key="test-only-key",
            payload_source_name="raw_expanded_payloads.jsonl",
        )
        by_session = {record["session_id"]: record for record in records}
        self.assertEqual(set(by_session), {"batch-two-s1", "batch-two-s2"})
        self.assertEqual(by_session["batch-two-s1"]["collection_round"], 1)
        self.assertEqual(by_session["batch-two-s2"]["collection_round"], 2)
        self.assertEqual(
            by_session["batch-two-s1"]["collection_batch_id"], batch_two
        )
        self.assertEqual(
            by_session["batch-two-s1"]["collection_batch_id_source"],
            provenance.BACKEND_BATCH_ID_SOURCE,
        )
        self.assertEqual(
            by_session["batch-two-s1"]["collection_batch_lifecycle_status"],
            "closed_cleanly",
        )

    def test_server_batch_mismatch_fails_closed(self):
        batch_one = "hgbatch-v1-one"
        batch_two = "hgbatch-v1-two"
        archive = canonical_archive(
            "mismatch", 1, "Google", "Pixel 8", "Android 14", 34, batch_one
        )
        with self.assertRaises(provenance.ProvenanceError):
            provenance.build_provenance_records(
                payload_entries=[(1, archive)],
                receipt_entries=[
                    (
                        1,
                        receipt(
                            "mismatch",
                            archive["payload_sha256"],
                            "2026-07-26T00:00:01Z",
                            batch_two,
                        ),
                    )
                ],
                platform_provider="wetest",
                collection_batch_id=batch_one,
                collection_batch_id_source=provenance.BACKEND_BATCH_ID_SOURCE,
                profile_hmac_key="test-only-key",
                payload_source_name="raw_expanded_payloads.jsonl",
            )

    def test_cli_automatically_selects_latest_closed_backend_batch(self):
        batch_id = "hgbatch-v1-cli"
        archive = canonical_archive(
            "cli-session", 1, "Google", "Pixel 8", "Android 14", 34, batch_id
        )
        receipt_row = receipt(
            "cli-session", archive["payload_sha256"], "2026-07-26T00:00:01Z", batch_id
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            raw_path = temp / "raw_expanded_payloads.jsonl"
            receipt_path = temp / "collection_receipts.jsonl"
            ledger = temp / "collection_batches.jsonl"
            output = temp / "session_provenance.jsonl"
            key_file = temp / "profile.key"
            raw_path.write_text(json.dumps(archive) + "\n", encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt_row) + "\n", encoding="utf-8")
            ledger.write_text(
                "".join(
                    json.dumps(event) + "\n"
                    for event in (
                        batch_event("started", batch_id, "2026-07-26T00:00:00Z"),
                        batch_event(
                            "closed",
                            batch_id,
                            "2026-07-26T00:00:02Z",
                            lifecycle_status="closed_cleanly",
                            ended_at_source="graceful_shutdown_hook",
                        ),
                    )
                ),
                encoding="utf-8",
            )
            key_file.write_text("test-only-key\n", encoding="utf-8")
            key_file.chmod(0o600)
            argv = [
                "export_session_provenance.py",
                "--platform-provider",
                "wetest",
                "--input",
                str(raw_path),
                "--receipts",
                str(receipt_path),
                "--batch-ledger",
                str(ledger),
                "--output",
                str(output),
                "--hmac-key-file",
                str(key_file),
            ]
            with mock.patch.dict(os.environ, {"HYBRIDGUARD_PROFILE_HMAC_KEY": ""}, clear=False):
                with mock.patch.object(sys, "argv", argv):
                    self.assertEqual(provenance.main(), 0)

            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["collection_batch_id"], batch_id)
            self.assertEqual(
                record["collection_batch_id_source"],
                provenance.BACKEND_BATCH_ID_SOURCE,
            )

    def test_cli_uses_explicit_legacy_label_for_unbatched_raw_archive(self):
        archive = canonical_archive(
            "legacy-raw", 1, "Google", "Pixel 8", "Android 14", 34
        )
        receipt_row = receipt(
            "legacy-raw", archive["payload_sha256"], "2026-07-25T00:00:01Z"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            raw_path = temp / "raw_expanded_payloads.jsonl"
            receipt_path = temp / "collection_receipts.jsonl"
            ledger = temp / "missing_collection_batches.jsonl"
            output = temp / "session_provenance.jsonl"
            key_file = temp / "profile.key"
            raw_path.write_text(json.dumps(archive) + "\n", encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt_row) + "\n", encoding="utf-8")
            key_file.write_text("test-only-key\n", encoding="utf-8")
            key_file.chmod(0o600)
            argv = [
                "export_session_provenance.py",
                "--platform-provider",
                "wetest",
                "--collection-batch-id",
                "legacy-20260725-01",
                "--input",
                str(raw_path),
                "--receipts",
                str(receipt_path),
                "--batch-ledger",
                str(ledger),
                "--output",
                str(output),
                "--hmac-key-file",
                str(key_file),
            ]
            with mock.patch.dict(os.environ, {"HYBRIDGUARD_PROFILE_HMAC_KEY": ""}, clear=False):
                with mock.patch.object(sys, "argv", argv):
                    self.assertEqual(provenance.main(), 0)

            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["collection_batch_id"], "legacy-20260725-01")
            self.assertEqual(
                record["collection_batch_id_source"],
                provenance.LEGACY_BATCH_ID_SOURCE,
            )
            self.assertTrue(record["raw_payload_available"])

    def test_raw_archive_hash_mismatch_fails_closed(self):
        archive = canonical_archive("broken", 1, "Google", "Pixel 8", "Android 14", 34)
        records = [
            (
                1,
                receipt("broken", "different-hash", "2026-07-25T00:00:01Z"),
            )
        ]
        with self.assertRaises(provenance.ProvenanceError):
            provenance.build_provenance_records(
                payload_entries=[(1, archive)],
                receipt_entries=records,
                platform_provider="wetest",
                collection_batch_id="wetest-20260725-01",
                profile_hmac_key="test-only-key",
                payload_source_name="raw_expanded_payloads.jsonl",
            )

    def test_same_profile_with_conflicting_api_fails_closed(self):
        first = canonical_archive("api-1", 1, "Google", "Pixel 8", "Android 14", 34)
        second = canonical_archive("api-2", 2, "Google", "Pixel 8", "Android 14", 35)
        with self.assertRaises(provenance.ProvenanceError):
            provenance.build_provenance_records(
                payload_entries=[(1, first), (2, second)],
                receipt_entries=[
                    (1, receipt("api-1", first["payload_sha256"], "2026-07-25T00:00:01Z")),
                    (2, receipt("api-2", second["payload_sha256"], "2026-07-25T00:00:02Z")),
                ],
                platform_provider="wetest",
                collection_batch_id="wetest-20260725-01",
                profile_hmac_key="test-only-key",
                payload_source_name="raw_expanded_payloads.jsonl",
            )


if __name__ == "__main__":
    unittest.main()
