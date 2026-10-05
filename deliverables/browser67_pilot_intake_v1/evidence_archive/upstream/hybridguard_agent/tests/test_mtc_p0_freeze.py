import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.scripts import freeze_mtc_collection_p0 as freeze


def receipt_fixture():
    payload = {"session_id": "s", "collection_manifest": {
        "manufacturer": "fixture", "model": "model", "android_release": "12",
        "android_api": 31, "collector_install_id": "install", "collector_version_code": 11,
        "collector_version_name": "v11",
    }}
    raw = {"session_id": "s", "receipt_id": "original", "payload_sha256": "stored-id",
           "collection_batch_id": "batch", "canonical_received_payload": payload}
    receipt = {"session_id": "s", "receipt_id": "retry", "payload_sha256": "stored-id",
               "collection_batch_id": "batch", "duplicate_payload": True, "stored_new_jsonl_row": False}
    pair = {"pair_id": "pair", "pair_status": "completed", "app_session_id": "s",
            "app_receipt_id": "retry", "app_payload_sha256": "stored-id", "browser_receipt_id": "br",
            "browser_session_id": "bs", "browser_payload_sha256": "browser-stored-id",
            "collection_batch_id": "batch", "paired_at": "2026-09-22T08:00:00Z"}
    browser = {k: pair[k] for k in ("pair_id", "app_session_id", "app_receipt_id", "browser_receipt_id",
                                    "browser_session_id", "browser_payload_sha256", "collection_batch_id")}
    return {
        "expanded_collected_data.jsonl": [(1, payload)], "raw_expanded_payloads.jsonl": [(1, raw)],
        "raw_browser_payloads.jsonl": [(1, browser)], "collection_receipts.jsonl": [(1, receipt)],
        "browser_pair_provenance.jsonl": [(1, pair)], "browser_collected_data.jsonl": [(1, {"pair_id": "pair"})],
        "browser_pair_events.jsonl": [(1, {"pair_id": "pair", "event": "ticket_issued", "pair_status": "completed"})],
        "collection_batches.jsonl": [(1, {"collection_batch_id": "batch", "lifecycle_status": "open"})],
    }


class MtcP0FreezeTests(unittest.TestCase):
    def test_user_waiver_removes_procurement_target_without_inventing_reconciliation(self):
        summary, ledgers = freeze.inventory(receipt_fixture(), "2026-09-22T08:01:00Z", procurement_waived=True)
        self.assertTrue(summary["p0_complete"])
        self.assertFalse(summary["procurement_reconciliation_required"])
        self.assertFalse(summary["procurement_reconciliation_complete"])
        self.assertIsNone(summary["procurement"]["arithmetic_gap_only"])
        self.assertEqual(ledgers["model_os_inventory.jsonl"][0]["procurement_match_status"], "NOT_REQUIRED_USER_WAIVED")

    def test_retired_source_must_have_no_active_batch_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, _, _ = self.make_source(Path(temporary))
            with self.assertRaisesRegex(ValueError, "Source file set differs"):
                freeze.signatures(source, retired=True)
            (source / "active_collection_batch.json").unlink()
            self.assertEqual(len(freeze.signatures(source, retired=True)), len(freeze.FILES) - 1)

    def test_duplicate_receipt_alias_keeps_original_archive_and_later_gates_pending(self):
        summary, ledgers = freeze.inventory(receipt_fixture(), "2026-09-22T08:01:00Z", 900)
        self.assertEqual(summary["pair_reference_status_counts"], {"duplicate_receipt_alias_resolved": 1})
        row = ledgers["paired_receipt_inventory.jsonl"][0]
        self.assertEqual(row["app_receipt_id"], "retry")
        self.assertEqual(row["archived_app_receipt_id"], "original")
        self.assertFalse(summary["p0_complete"])
        self.assertEqual(summary["formal_experiment_qc"], "NOT_EVALUATED_P1_REQUIRED")

    def test_same_payload_without_duplicate_receipt_evidence_is_rejected(self):
        data = copy.deepcopy(receipt_fixture())
        data["collection_receipts.jsonl"][0][1]["duplicate_payload"] = False
        with self.assertRaisesRegex(ValueError, "Pair references"):
            freeze.inventory(data, "2026-09-22T08:01:00Z", 900)

    def test_browser_app_session_mismatch_is_rejected(self):
        data = copy.deepcopy(receipt_fixture())
        data["raw_browser_payloads.jsonl"][0][1]["app_session_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Pair references"):
            freeze.inventory(data, "2026-09-22T08:01:00Z", 900)

    def make_source(self, root):
        source, output, ready = root / "live", root / "freeze", root / "ready.json"
        source.mkdir()
        for name in freeze.FILES:
            (source / name).write_text("{}\n")
        ready.write_text(json.dumps({"status": "ready", "collection_storage_name": "live",
                                     "collection_storage_isolated": True, "collection_batch_id": "batch"}))
        argv = ["freeze", "--source-dir", str(source), "--output-dir", str(output),
                "--readiness", str(ready), "--expected-purchased", "900"]
        return source, output, argv

    def test_live_write_during_copy_aborts_without_publishing(self):
        with tempfile.TemporaryDirectory(prefix="mtc-p0-test-") as temporary:
            root = Path(temporary).resolve()
            source, output, argv = self.make_source(root)
            original_copy = freeze.shutil.copyfile

            def copy_then_append(src, dst):
                result = original_copy(src, dst)
                if Path(src) == source / freeze.FILES[0]:
                    with Path(src).open("a") as handle:
                        handle.write(" ")
                return result

            with patch.object(sys, "argv", argv), patch.object(freeze.shutil, "copyfile", copy_then_append):
                with self.assertRaisesRegex(RuntimeError, "changed during copy"):
                    freeze.main()
            self.assertFalse(output.exists())
            self.assertFalse(list(root.glob("freeze.building-*")))

    def test_existing_freeze_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="mtc-p0-test-") as temporary:
            _, output, argv = self.make_source(Path(temporary).resolve())
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep")
            with patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(ValueError, "new directory"):
                    freeze.main()
            self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
