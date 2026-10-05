from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2
from hybridguard_agent.scripts import build_latest_runtime_inputs as builder


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def app_payload(tag: str) -> dict:
    return {
        "collector_app": "featureapp",
        "schema_version": "expanded-v2.2-status",
        "android_native_data": {
            "os_version": "14",
            "device_model": f"Pixel-{tag}",
            "sensor_total_count": 12,
        },
        "webview_data": {
            "system_http_agent": "Mozilla/5.0 (Linux; Android 14; wv)",
            "default_ua_native": "Mozilla/5.0 (Linux; Android 14; wv)",
            "jsbridge_injected": True,
        },
        "web_data": {
            "user_agent": f"Mozilla/5.0 (Linux; Android 14; Pixel-{tag})",
            "platform": "Linux armv8l",
            "max_touch_points": 5,
        },
    }


def browser_sidecar(sample_id: str) -> dict:
    return {
        "browser_pair_evidence_version": "browser-pair-evidence-v1",
        "sample_id": sample_id,
        "policy_version": "browser-pair-policy-v1",
        "input_contract": {
            "dataset_manifest_version": "latest-featureapp-paired244-snapshot-v1",
            "record_schema_version": "hybridguard-paired244-view-v1",
        },
        "comparison_status": "completed",
        "field_results": [
            {
                "field_path": "web_data.navigator_layer.platform",
                "value_type": "string",
                "comparison_mode": "exact",
                "app_status": "observed",
                "browser_status": "observed",
                "result": "same",
                "app_value_sha256": "a" * 64,
                "browser_value_sha256": "a" * 64,
                "reason_code": "values_equal",
            }
        ],
        "summary": {
            "configured_field_count": 1,
            "same_count": 1,
            "different_count": 0,
            "unavailable_count": 0,
            "not_comparable_count": 0,
        },
        "metric_eligible": False,
        "claim_boundary": "Observation only; no attack or risk conclusion.",
        "evidence_hash": "b" * 64,
    }


def runtime_sample(sample_id: str, dataset_view: str) -> SimpleNamespace:
    evidence = build_evidence_bundle_v2(app_payload(sample_id), sample_id=sample_id)
    paired = dataset_view == "paired_244"
    return SimpleNamespace(
        snapshot={"run_id": "latest-fixture"},
        sample_id=sample_id,
        normalized_payload=app_payload(sample_id),
        field_status={},
        input_quality={
            "qc_status": "accepted",
            "qc_reasons": [],
            "dataset_view": dataset_view,
        },
        evidence_bundle=evidence,
        browser_pair_evidence=browser_sidecar(sample_id) if paired else None,
        browser_pair_status=(
            "available_not_assessed" if paired else "not_available_no_browser_payload"
        ),
    )


class BuildLatestRuntimeInputsTests(unittest.TestCase):
    def test_writes_separate_app_and_browser_outputs_without_touching_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_dir = root / "snapshot"
            output_dir = root / "runtime-inputs"
            snapshot_dir.mkdir()
            manifest_path = snapshot_dir / "dataset_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "dataset_manifest_version": "latest-featureapp-paired244-snapshot-v1",
                        "run_id": "latest-fixture",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            before = {path.name: path.read_bytes() for path in snapshot_dir.iterdir()}
            samples = [
                runtime_sample("paired-sample", "paired_244"),
                runtime_sample("app-only-sample", "app_only_177"),
            ]

            with mock.patch.object(
                builder.snapshot_loader,
                "load_latest_runtime_samples",
                return_value=samples,
                create=True,
            ) as loader:
                manifest = builder.build_runtime_inputs(
                    snapshot_dir,
                    output_dir,
                    run_id="runtime-fixture",
                )

            loader.assert_called_once_with(snapshot_dir.resolve(), browser_policy_path=None)
            after = {path.name: path.read_bytes() for path in snapshot_dir.iterdir()}
            self.assertEqual(after, before)

            app_rows = read_jsonl(output_dir / builder.APP_EVIDENCE_FILENAME)
            browser_rows = read_jsonl(output_dir / builder.BROWSER_EVIDENCE_FILENAME)
            index_rows = read_jsonl(output_dir / builder.SAMPLE_INDEX_FILENAME)
            persisted_manifest = json.loads(
                (output_dir / builder.MANIFEST_FILENAME).read_text(encoding="utf-8")
            )

        self.assertEqual(manifest, persisted_manifest)
        self.assertEqual([row["sample_id"] for row in app_rows], ["app-only-sample", "paired-sample"])
        self.assertEqual([row["sample_id"] for row in browser_rows], ["paired-sample"])
        self.assertEqual(manifest["counts"]["runtime_sample_count"], 2)
        self.assertEqual(manifest["counts"]["app_evidence_bundle_v2_count"], 2)
        self.assertEqual(manifest["counts"]["browser_pair_evidence_v1_count"], 1)
        self.assertEqual(
            manifest["counts"]["dataset_view_counts"],
            {"app_only_177": 1, "paired_244": 1},
        )
        self.assertFalse(manifest["runtime_boundary"]["browser_pair_evidence_enters_rule_execution"])
        paired_index = next(row for row in index_rows if row["sample_id"] == "paired-sample")
        app_only_index = next(row for row in index_rows if row["sample_id"] == "app-only-sample")
        self.assertEqual(paired_index["browser_pair_evidence_sha256"], "b" * 64)
        self.assertIsNone(app_only_index["browser_pair_evidence_sha256"])
        forbidden_index_keys = {
            "session_id",
            "receipt_id",
            "pair_id",
            "collection_batch_id",
            "device_manifest_id",
        }
        self.assertFalse(forbidden_index_keys & set(paired_index))

    def test_rejects_duplicate_sample_ids_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_dir = root / "snapshot"
            output_dir = root / "runtime-inputs"
            snapshot_dir.mkdir()
            (snapshot_dir / "dataset_manifest.json").write_text("{}\n", encoding="utf-8")
            samples = [
                runtime_sample("duplicate", "paired_244"),
                runtime_sample("duplicate", "app_only_177"),
            ]

            with mock.patch.object(
                builder.snapshot_loader,
                "load_latest_runtime_samples",
                return_value=samples,
                create=True,
            ):
                with self.assertRaisesRegex(ValueError, "Duplicate runtime sample_id"):
                    builder.build_runtime_inputs(snapshot_dir, output_dir)

            self.assertFalse(output_dir.exists())

    def test_fixed_snapshot_build_is_byte_reproducible_without_explicit_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_dir = root / "snapshot"
            first_output = root / "runtime-inputs-first"
            second_output = root / "runtime-inputs-second"
            snapshot_dir.mkdir()
            (snapshot_dir / "dataset_manifest.json").write_text(
                '{"run_id":"fixed-source"}\n', encoding="utf-8"
            )
            samples = [
                runtime_sample("paired-sample", "paired_244"),
                runtime_sample("app-only-sample", "app_only_177"),
            ]

            with mock.patch.object(
                builder.snapshot_loader,
                "load_latest_runtime_samples",
                return_value=samples,
                create=True,
            ):
                first_manifest = builder.build_runtime_inputs(snapshot_dir, first_output)
                second_manifest = builder.build_runtime_inputs(snapshot_dir, second_output)

            first_files = {
                path.name: path.read_bytes() for path in first_output.iterdir() if path.is_file()
            }
            second_files = {
                path.name: path.read_bytes() for path in second_output.iterdir() if path.is_file()
            }

        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_files, second_files)
        self.assertTrue(first_manifest["run_id"].startswith("latest-runtime-"))

    def test_rejects_app_only_sample_with_fabricated_browser_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_dir = root / "snapshot"
            output_dir = root / "runtime-inputs"
            snapshot_dir.mkdir()
            (snapshot_dir / "dataset_manifest.json").write_text("{}\n", encoding="utf-8")
            sample = runtime_sample("app-only", "app_only_177")
            sample.browser_pair_evidence = browser_sidecar("app-only")

            with mock.patch.object(
                builder.snapshot_loader,
                "load_latest_runtime_samples",
                return_value=[sample],
                create=True,
            ):
                with self.assertRaisesRegex(ValueError, "must not fabricate"):
                    builder.build_runtime_inputs(snapshot_dir, output_dir)

            self.assertFalse(output_dir.exists())

    def test_rejects_existing_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_dir = root / "snapshot"
            output_dir = root / "runtime-inputs"
            snapshot_dir.mkdir()
            output_dir.mkdir()
            (snapshot_dir / "dataset_manifest.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                builder.build_runtime_inputs(snapshot_dir, output_dir)

    def test_rejects_output_inside_the_source_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshot"
            snapshot_dir.mkdir()

            with self.assertRaisesRegex(ValueError, "outside the immutable source snapshot"):
                builder.build_runtime_inputs(
                    snapshot_dir,
                    snapshot_dir / "runtime-inputs",
                )


if __name__ == "__main__":
    unittest.main()
