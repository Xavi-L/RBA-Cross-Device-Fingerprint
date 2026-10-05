import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hybridguard_agent.evidence.extractor import canonical_json
from hybridguard_agent.runtime.service import analyze_evidence_bundle
from hybridguard_agent.runtime.snapshot_loader import (
    load_latest_runtime_samples,
    load_runtime_sample,
)
from hybridguard_agent.scripts import run_agent_runtime
from hybridguard_agent.scripts import build_latest_paired244_snapshot as snapshot_builder
from hybridguard_agent.tests.test_build_latest_paired244_snapshot import SnapshotFixture


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class LatestRuntimeBridgeTests(unittest.TestCase):
    def build_fixture_snapshot(self, root: Path) -> tuple[Path, str, str]:
        fixture = SnapshotFixture(root)
        paired_app = fixture.add_app("latest-runtime-paired")
        fixture.add_pair(paired_app)
        app_only = fixture.add_app("latest-runtime-app-only")
        fixture.add_awaiting_event(app_only)
        output = root / "snapshot"
        snapshot_builder.build_snapshot(fixture.flush(), output, "latest-runtime-fixture")
        index = read_jsonl(output / "sample_index.jsonl")
        paired_id = next(
            row["sample_id"] for row in index if row["dataset_view"] == "paired_244"
        )
        app_only_id = next(
            row["sample_id"] for row in index if row["dataset_view"] == "app_only_177"
        )
        return output, paired_id, app_only_id

    def test_loads_paired_and_app_only_into_existing_evidence_v2(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot, paired_id, app_only_id = self.build_fixture_snapshot(Path(temp_dir))

            paired = load_runtime_sample(snapshot, paired_id)
            app_only = load_runtime_sample(snapshot, app_only_id)

            self.assertEqual(paired.snapshot["snapshot_kind"], "latest-paired244-v1")
            self.assertEqual(paired.browser_pair_status, "available_not_assessed")
            self.assertIsNotNone(paired.browser_pair_evidence)
            self.assertEqual(len(paired.browser_pair_evidence["field_results"]), 67)
            self.assertEqual(app_only.browser_pair_status, "not_available_no_browser_payload")
            self.assertIsNone(app_only.browser_pair_evidence)
            self.assertEqual(set(paired.normalized_payload) & {
                "android_native_data",
                "webview_data",
                "web_data",
            }, {"android_native_data", "webview_data", "web_data"})
            self.assertEqual(paired.evidence_bundle["evidence_bundle_version"], "evidence-bundle-v2")

    def test_runtime_uses_only_app_evidence_and_remains_uncalibrated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot, paired_id, _ = self.build_fixture_snapshot(Path(temp_dir))
            sample = load_runtime_sample(snapshot, paired_id)

            result = analyze_evidence_bundle(sample.evidence_bundle)

            self.assertIsNone(result["decision"]["calibrated_risk_score"])
            self.assertFalse(result["decision_trace"]["runtime"]["external_model_called"])
            self.assertIn("browser_pair", sample.evidence_bundle["coverage"]["not_assessed"])
            self.assertNotIn("browser_pair_evidence", result)

    def test_runtime_cli_attaches_only_browser_audit_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, paired_id, app_only_id = self.build_fixture_snapshot(root)

            for sample_id, expected_status in (
                (paired_id, "available_not_assessed"),
                (app_only_id, "not_available_no_browser_payload"),
            ):
                output = root / f"{sample_id}.jsonl"
                with mock.patch(
                    "sys.argv",
                    [
                        "run_agent_runtime.py",
                        "--snapshot-dir",
                        str(snapshot),
                        "--sample-id",
                        sample_id,
                        "--output",
                        str(output),
                    ],
                ):
                    run_agent_runtime.main()

                result = read_jsonl(output)[0]
                browser_audit = result["browser_pair_evidence"]
                self.assertEqual(browser_audit["status"], expected_status)
                self.assertFalse(browser_audit["used_by_rule_execution"])
                self.assertIsNone(result["decision"]["calibrated_risk_score"])
                self.assertFalse(
                    result["decision_trace"]["runtime"]["external_model_called"]
                )
                if sample_id == paired_id:
                    self.assertEqual(browser_audit["summary"]["field_count"], 67)
                    self.assertEqual(len(browser_audit["evidence_hash"]), 64)
                else:
                    self.assertIsNone(browser_audit["summary"])
                    self.assertIsNone(browser_audit["evidence_hash"])

    def test_bridge_does_not_expose_control_plane_identifiers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot, paired_id, _ = self.build_fixture_snapshot(Path(temp_dir))
            sample = load_runtime_sample(snapshot, paired_id)
            serialized = canonical_json(
                {
                    "payload": sample.normalized_payload,
                    "field_status": sample.field_status,
                    "evidence": sample.evidence_bundle,
                    "browser_pair": sample.browser_pair_evidence,
                }
            )

            for forbidden in (
                "latest-runtime-paired",
                "receipt-latest-runtime-paired",
                "pair-latest-runtime-paired",
                "batch-latest-runtime-paired",
                "profile-latest-runtime-paired",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_bulk_loader_is_deterministic_and_covers_both_views(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot, _, _ = self.build_fixture_snapshot(Path(temp_dir))

            first = load_latest_runtime_samples(snapshot)
            second = load_latest_runtime_samples(snapshot)

            self.assertEqual([item.sample_id for item in first], [item.sample_id for item in second])
            self.assertEqual(
                [item.evidence_bundle["evidence_hash"] for item in first],
                [item.evidence_bundle["evidence_hash"] for item in second],
            )
            self.assertEqual(
                {item.browser_pair_status for item in first},
                {"available_not_assessed", "not_available_no_browser_payload"},
            )

    def test_rejects_duplicate_sample_and_missing_feature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, paired_id, _ = self.build_fixture_snapshot(root)
            paired_path = snapshot / "paired_244.jsonl"
            paired_line = paired_path.read_text(encoding="utf-8")
            paired_path.write_text(paired_line + paired_line, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate sample_id"):
                load_runtime_sample(snapshot, paired_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, paired_id, _ = self.build_fixture_snapshot(root)
            paired_path = snapshot / "paired_244.jsonl"
            row = read_jsonl(paired_path)[0]
            removed = next(iter(row["features"]))
            del row["features"][removed]
            paired_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "feature set"):
                load_runtime_sample(snapshot, paired_id)

    def test_rejects_latest_snapshot_that_crosses_the_label_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot, paired_id, _ = self.build_fixture_snapshot(Path(temp_dir))
            manifest_path = snapshot / "dataset_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["label_status"] = "verified"
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "development-only and unlabeled"):
                load_runtime_sample(snapshot, paired_id)


if __name__ == "__main__":
    unittest.main()
