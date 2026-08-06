import json
import tempfile
import unittest
from pathlib import Path

from hybridguard_agent.scripts import build_evidence_bundles_v2 as builder


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def normalized_row(sample_id: str = "sample-1") -> dict:
    return {
        "sample_id": sample_id,
        "schema_version": "expanded-v2",
        "payload": {
            "collector_app": "featureapp",
            "schema_version": "expanded-v2",
            "android_native_data": {"os_version": "14", "device_model": "Pixel 7"},
            "webview_data": {"system_http_agent": "Android 14", "default_ua_native": "wv"},
            "web_data": {
                "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7)",
                "platform": "Linux armv8l",
                "max_touch_points": 5,
            },
        },
    }


def status_row(sample_id: str = "sample-1") -> dict:
    return {
        "sample_id": sample_id,
        "field_status": {
            "status_schema_version": "field-status-v1",
            "fields": {
                "android_native_data.os_version": "observed",
                "android_native_data.device_model": "observed",
                "webview_data.system_http_agent": "observed",
                "webview_data.default_ua_native": "observed",
                "web_data.user_agent": "observed",
                "web_data.platform": "observed",
                "web_data.max_touch_points": "observed",
            },
        },
    }


class BuildEvidenceBundlesV2Tests(unittest.TestCase):
    def test_builds_from_unified_sidecar_without_raw_or_provenance_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir)
            write_jsonl(snapshot_dir / "normalized_expanded_v2.jsonl", [normalized_row()])
            write_jsonl(snapshot_dir / "field_status.jsonl", [status_row()])

            bundles = builder.build_bundles(snapshot_dir)
            output_path = snapshot_dir / "evidence_bundles_v2.jsonl"
            builder.write_bundles(output_path, bundles)
            persisted = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(bundles), 1)
        self.assertEqual(persisted, bundles)
        bundle = bundles[0]
        self.assertEqual(bundle["sample_id"], "sample-1")
        self.assertEqual(bundle["evidence_bundle_version"], "evidence-bundle-v2")
        encoded = json.dumps(bundle, ensure_ascii=False)
        self.assertNotIn("Mozilla/5.0", encoded)
        self.assertNotIn('"session_id"', encoded)
        self.assertNotIn('"provider"', encoded)
        self.assertNotIn('"label"', encoded)

    def test_falls_back_to_historical_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir)
            write_jsonl(snapshot_dir / "normalized_expanded_v2.jsonl", [normalized_row()])
            write_jsonl(
                snapshot_dir / "historical_field_status_backfill.jsonl",
                [
                    {
                        "sample_id": "sample-1",
                        "session_id_hash": "not-used-by-builder",
                        "inferred_collection_status": status_row()["field_status"],
                    }
                ],
            )

            bundles = builder.build_bundles(snapshot_dir)

        self.assertEqual(bundles[0]["sample_id"], "sample-1")

    def test_rejects_non_matching_sample_id_sets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir)
            write_jsonl(snapshot_dir / "normalized_expanded_v2.jsonl", [normalized_row()])
            write_jsonl(snapshot_dir / "field_status.jsonl", [status_row("other-sample")])

            with self.assertRaisesRegex(ValueError, "not one-to-one"):
                builder.build_bundles(snapshot_dir)


if __name__ == "__main__":
    unittest.main()
