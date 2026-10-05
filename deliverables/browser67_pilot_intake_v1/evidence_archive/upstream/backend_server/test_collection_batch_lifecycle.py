import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main


class CollectionBatchLifecycleTests(unittest.TestCase):
    def test_fastapi_lifecycle_hooks_are_registered(self) -> None:
        self.assertIn(
            main.start_collection_batch_for_server_lifecycle,
            main.app.router.on_startup,
        )
        self.assertIn(
            main.close_collection_batch_for_server_lifecycle,
            main.app.router.on_shutdown,
        )

    def test_start_readiness_and_graceful_close_are_one_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            ledger = temp / "collection_batches.jsonl"
            state = temp / "active_collection_batch.json"
            receipts = temp / "collection_receipts.jsonl"
            original_batch = main.active_collection_batch
            main.active_collection_batch = None
            try:
                with mock.patch.multiple(
                    main,
                    COLLECTION_BATCHES_JSONL_FILE=ledger,
                    ACTIVE_COLLECTION_BATCH_STATE_FILE=state,
                    COLLECTION_RECEIPTS_JSONL_FILE=receipts,
                ):
                    started = main.start_collection_batch()
                    readiness = asyncio.run(main.collection_readiness())
                    closed = main.close_active_collection_batch()
            finally:
                main.active_collection_batch = original_batch

            events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["event"] for event in events], ["started", "closed"])
            self.assertEqual(readiness["collection_batch_id"], started["collection_batch_id"])
            self.assertEqual(readiness["collection_batch_status"], "open")
            self.assertEqual(closed["collection_batch_id"], started["collection_batch_id"])
            self.assertEqual(closed["lifecycle_status"], "closed_cleanly")
            self.assertFalse(state.exists())

    def test_next_start_recovers_an_unclean_previous_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            ledger = temp / "collection_batches.jsonl"
            state = temp / "active_collection_batch.json"
            receipts = temp / "collection_receipts.jsonl"
            original_batch = main.active_collection_batch
            main.active_collection_batch = None
            try:
                with mock.patch.multiple(
                    main,
                    COLLECTION_BATCHES_JSONL_FILE=ledger,
                    ACTIVE_COLLECTION_BATCH_STATE_FILE=state,
                    COLLECTION_RECEIPTS_JSONL_FILE=receipts,
                ):
                    first = main.start_collection_batch()
                    main.save_to_jsonl(
                        {
                            "session_id": "unclean-session",
                            "server_received_at": "2026-07-26T01:02:03.000000Z",
                            "stored_new_jsonl_row": True,
                            "duplicate_payload": False,
                            "collection_batch_id": first["collection_batch_id"],
                        },
                        receipts,
                    )
                    # Simulate SIGKILL: no shutdown hook runs, so the marker remains.
                    main.active_collection_batch = None
                    stale_state = json.loads(state.read_text(encoding="utf-8"))
                    stale_state["backend_process_id"] = 0
                    main.write_json_atomically(stale_state, state)
                    second = main.start_collection_batch()
                    main.close_active_collection_batch()
            finally:
                main.active_collection_batch = original_batch

            events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            recovered = next(
                event
                for event in events
                if event["event"] == "closed"
                and event["collection_batch_id"] == first["collection_batch_id"]
            )
            self.assertNotEqual(first["collection_batch_id"], second["collection_batch_id"])
            self.assertEqual(recovered["lifecycle_status"], "unclean_shutdown_recovered")
            self.assertEqual(recovered["ended_at"], "2026-07-26T01:02:03.000000Z")
            self.assertEqual(recovered["ended_at_source"], "last_receipt_at")

    def test_live_active_marker_rejects_a_second_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            original_batch = main.active_collection_batch
            main.active_collection_batch = None
            try:
                with mock.patch.multiple(
                    main,
                    COLLECTION_BATCHES_JSONL_FILE=temp / "collection_batches.jsonl",
                    ACTIVE_COLLECTION_BATCH_STATE_FILE=temp / "active_collection_batch.json",
                    COLLECTION_RECEIPTS_JSONL_FILE=temp / "collection_receipts.jsonl",
                ):
                    main.start_collection_batch()
                    # A second process would not share this in-memory value, but it would
                    # encounter the same on-disk marker with a live owner PID.
                    main.active_collection_batch = None
                    with self.assertRaises(main.CollectionBatchError):
                        main.start_collection_batch()
            finally:
                main.active_collection_batch = original_batch

    def test_upload_without_server_lifecycle_batch_is_rejected(self) -> None:
        original_batch = main.active_collection_batch
        main.active_collection_batch = None
        try:
            payload = main.FingerprintPayload(
                session_id="not-ready",
                timestamp=1,
            )
            with self.assertRaises(main.HTTPException) as raised:
                asyncio.run(main.collect_fingerprint(payload))
        finally:
            main.active_collection_batch = original_batch
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
