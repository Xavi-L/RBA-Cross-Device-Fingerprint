import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import main


class CollectionStorageTests(unittest.TestCase):
    def test_default_runs_are_distinct_and_relative_paths_ignore_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with mock.patch.object(main, "BACKEND_DIR", root), mock.patch.dict(
                os.environ, {"HYBRIDGUARD_DATA_DIR": ""}
            ):
                first = main.resolve_collection_data_dir()
                second = main.resolve_collection_data_dir()
                self.assertNotEqual(first, second)
                self.assertEqual(first.parent, root / "collection_runs")
            with mock.patch.object(main, "BACKEND_DIR", root), mock.patch.dict(
                os.environ, {"HYBRIDGUARD_DATA_DIR": "collection_runs/mtc-test"}
            ):
                self.assertEqual(main.resolve_collection_data_dir(), root / "collection_runs/mtc-test")
            with mock.patch.object(main, "BACKEND_DIR", root), mock.patch.dict(
                os.environ, {"HYBRIDGUARD_DATA_DIR": str(root)}
            ):
                with self.assertRaises(ValueError):
                    main.resolve_collection_data_dir()

    def test_real_collection_writes_only_to_selected_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, HYBRIDGUARD_DATA_DIR=directory, PYTHONDONTWRITEBYTECODE="1")
            script = """
import asyncio, json
from pathlib import Path
import main
assert main.sessions_db == {} and main.expanded_sessions_db == {}
paths = [value for name, value in vars(main).items() if name.endswith('_FILE') and isinstance(value, Path)]
assert len(paths) == 14, len(paths)
assert all(path.parent == main.DATA_DIR for path in paths)
main.start_collection_batch()
payload = main.FingerprintPayload(session_id='storage-test', timestamp=1800000000,
    collector_app='featureapp', schema_version='expanded-v2.2-status',
    android_native_data={}, webview_data={}, web_data={})
asyncio.run(main.collect_fingerprint(payload))
readiness = asyncio.run(main.collection_readiness())
assert readiness['collection_storage_isolated'] is True
main.close_active_collection_batch()
"""
            result = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=Path(__file__).parent, env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            root = Path(directory)
            self.assertIn("storage-test", json.loads((root / "expanded_merged_sessions.json").read_text()))
            self.assertTrue((root / "raw_expanded_payloads.jsonl").exists())
            self.assertTrue((root / "collection_receipts.jsonl").exists())
            self.assertFalse((root / "active_collection_batch.json").exists())


if __name__ == "__main__":
    unittest.main()
