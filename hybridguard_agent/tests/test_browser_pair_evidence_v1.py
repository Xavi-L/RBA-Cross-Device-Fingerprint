import copy
import csv
import json
import unittest
from pathlib import Path

from hybridguard_agent.evidence import browser_pair


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_CSV = (
    REPO_ROOT
    / "android_app"
    / "HybridGuard"
    / "featureapp"
    / "src"
    / "main"
    / "assets"
    / "expanded_v2_field_catalog.csv"
)
SCHEMA_PATH = (
    REPO_ROOT
    / "hybridguard_agent"
    / "schemas"
    / "browser_pair_evidence_v1.schema.json"
)


def fixture_value(type_name):
    return {
        "boolean": False,
        "number": 1,
        "string": "fixture",
        "array": [],
    }[type_name]


def field_result(evidence, field_path):
    return next(
        result
        for result in evidence["field_results"]
        if result["field_path"] == field_path
    )


class PairSnapshotFixture:
    def __init__(self):
        with CATALOG_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if row["layer"] in {"android_native_data", "webview_data", "web_data"}
            ]
        self.app_fields = [row["field"] for row in rows]
        self.browser_fields = [row["field"] for row in rows if row["layer"] == "web_data"]
        self.app_types = {row["field"]: row["type"] for row in rows}
        self.browser_types = {
            row["field"]: row["type"] for row in rows if row["layer"] == "web_data"
        }
        self.feature_order = [f"app.{field}" for field in self.app_fields] + [
            f"browser.{field}" for field in self.browser_fields
        ]
        self.feature_types = {
            **{f"app.{field}": self.app_types[field] for field in self.app_fields},
            **{
                f"browser.{field}": self.browser_types[field]
                for field in self.browser_fields
            },
        }
        self.feature_catalog = {
            "feature_catalog_version": "latest-paired244-feature-catalog-v1",
            "paired_feature_count": 244,
            "app_feature_count": 177,
            "browser_feature_count": 67,
            "paired_feature_order": self.feature_order,
            "paired_feature_types": self.feature_types,
            "status_is_separate_from_feature_value": True,
        }

    def manifest(self, count=1):
        return {
            "dataset_manifest_version": "latest-featureapp-paired244-snapshot-v1",
            "selection": {
                "browser_probe_revision": "expanded-web-67-v1",
                "pair_status": "completed",
            },
            "views": {
                "paired_244": {
                    "path": "paired_244.jsonl",
                    "count": count,
                    "feature_count": 244,
                }
            },
            "dataset_role": "development_qc_only",
            "label_status": "unlabeled",
            "feature_catalog_path": "feature_catalog.json",
        }

    def row(self, sample_id="p244-fixture"):
        features = {
            f"app.{field}": fixture_value(self.app_types[field])
            for field in self.app_fields
        }
        features.update(
            {
                f"browser.{field}": fixture_value(self.browser_types[field])
                for field in self.browser_fields
            }
        )
        return {
            "record_schema_version": "hybridguard-paired244-view-v1",
            "sample_id": sample_id,
            "dataset_view": "paired_244",
            "dataset_role": "development_qc_only",
            "label_status": "unlabeled",
            "feature_count": 244,
            "features": features,
            "field_status": {field: "observed" for field in self.feature_order},
        }

class BrowserPairEvidenceV1Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = PairSnapshotFixture()
        self.policy = browser_pair.load_browser_pair_policy()

    def build(self, row):
        return browser_pair.build_browser_pair_evidence(
            row,
            self.fixture.feature_catalog,
            self.fixture.manifest(),
            self.policy,
        )

    def test_policy_and_schema_freeze_39_exact_and_28_not_comparable(self):
        exact = set(self.policy["exact_fields"])
        not_comparable = {
            field
            for fields in self.policy["not_comparable_field_groups"].values()
            for field in fields
        }
        self.assertEqual(len(exact), 39)
        self.assertEqual(len(not_comparable), 28)
        self.assertFalse(exact & not_comparable)
        self.assertEqual(exact | not_comparable, set(self.fixture.browser_fields))
        self.assertFalse(self.policy["metric_eligible"])

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertIn("evidence_hash", schema["required"])
        self.assertEqual(schema["properties"]["field_results"]["minItems"], 67)
        self.assertEqual(schema["properties"]["field_results"]["maxItems"], 67)
        self.assertEqual(schema["properties"]["metric_eligible"]["const"], False)

    def test_exact_different_unavailable_and_not_comparable_are_redacted(self):
        row = self.fixture.row()
        ua = "web_data.navigator_layer.user_agent"
        network = "web_data.network_api_layer.downlink_mbps"
        webgl = "web_data.graphics_layer.webgl_max_texture_size"
        row["features"][f"app.{ua}"] = "secret-app-user-agent"
        row["features"][f"browser.{ua}"] = "secret-browser-user-agent"
        row["features"][f"browser.{network}"] = 99
        row["field_status"][f"browser.{webgl}"] = "not_applicable"

        evidence = self.build(row)

        self.assertEqual(field_result(evidence, ua)["result"], "different")
        self.assertEqual(field_result(evidence, network)["result"], "not_comparable")
        self.assertEqual(field_result(evidence, webgl)["result"], "unavailable")
        self.assertIsNone(field_result(evidence, network)["app_value_sha256"])
        self.assertIsNone(field_result(evidence, webgl)["browser_value_sha256"])
        self.assertEqual(
            evidence["summary"],
            {
                "field_count": 67,
                "exact_policy_count": 39,
                "not_comparable_policy_count": 28,
                "same_count": 37,
                "different_count": 1,
                "unavailable_count": 1,
                "not_comparable_count": 28,
                "comparable_observed_count": 38,
            },
        )
        self.assertEqual(evidence["comparison_status"], "completed")
        self.assertFalse(evidence["metric_eligible"])
        self.assertEqual(len(evidence["evidence_hash"]), 64)
        hash_input = {
            key: value for key, value in evidence.items() if key != "evidence_hash"
        }
        self.assertEqual(evidence["evidence_hash"], browser_pair.sha256_value(hash_input))
        self.assertEqual(evidence, self.build(copy.deepcopy(row)))

        serialized = browser_pair.canonical_json(evidence)
        self.assertNotIn("secret-app-user-agent", serialized)
        self.assertNotIn("secret-browser-user-agent", serialized)
        for forbidden_key in ("session_id", "receipt_id", "browser_pair_id"):
            self.assertNotIn(f'"{forbidden_key}"', serialized)

    def test_every_non_observed_status_short_circuits_exact_comparison(self):
        field = "web_data.navigator_layer.hardware_concurrency"
        for unavailable_status in self.policy["unavailable_statuses"]:
            with self.subTest(status=unavailable_status):
                row = self.fixture.row(sample_id=f"p244-{unavailable_status}")
                row["features"][f"app.{field}"] = 8
                row["features"][f"browser.{field}"] = 8
                row["field_status"][f"browser.{field}"] = unavailable_status
                result = field_result(self.build(row), field)
                self.assertEqual(result["result"], "unavailable")
                self.assertEqual(result["reason_code"], "source_field_unavailable")
                self.assertIsNone(result["app_value_sha256"])
                self.assertIsNone(result["browser_value_sha256"])

    def test_ordered_arrays_use_exact_value_comparison(self):
        field = "web_data.navigator_layer.languages"
        row = self.fixture.row()
        row["features"][f"app.{field}"] = ["zh-CN", "en-US"]
        row["features"][f"browser.{field}"] = ["zh-CN", "en-US"]
        self.assertEqual(field_result(self.build(row), field)["result"], "same")

        row["features"][f"browser.{field}"] = ["en-US", "zh-CN"]
        self.assertEqual(field_result(self.build(row), field)["result"], "different")

    def test_numeric_literal_equality_does_not_normalize_int_and_float(self):
        field = "web_data.navigator_layer.device_memory"
        row = self.fixture.row()
        row["features"][f"app.{field}"] = 8
        row["features"][f"browser.{field}"] = 8.0
        result = field_result(self.build(row), field)
        self.assertEqual(result["result"], "different")
        self.assertNotEqual(result["app_value_sha256"], result["browser_value_sha256"])

    def test_no_observed_exact_fields_is_not_evaluable(self):
        row = self.fixture.row()
        for field in self.policy["exact_fields"]:
            row["field_status"][f"browser.{field}"] = "timeout"
        evidence = self.build(row)
        self.assertEqual(evidence["comparison_status"], "not_evaluable")
        self.assertEqual(evidence["summary"]["same_count"], 0)
        self.assertEqual(evidence["summary"]["different_count"], 0)
        self.assertEqual(evidence["summary"]["unavailable_count"], 39)
        self.assertEqual(evidence["summary"]["not_comparable_count"], 28)

    def test_required_web_field_and_catalog_type_drift_are_rejected(self):
        row = self.fixture.row("p244-drift")
        removed = "browser.web_data.automation_surface_layer.webdriver"
        row["features"].pop(removed)
        row["field_status"].pop(removed)
        with self.assertRaisesRegex(ValueError, "missing required field"):
            self.build(row)

        catalog = copy.deepcopy(self.fixture.feature_catalog)
        catalog["paired_feature_types"][removed] = "string"
        with self.assertRaisesRegex(ValueError, "type contract drifted"):
            browser_pair.build_browser_pair_evidence(
                self.fixture.row(), catalog, self.fixture.manifest(), self.policy
            )

    def test_probe_revision_drift_is_rejected(self):
        manifest = self.fixture.manifest()
        manifest["selection"]["browser_probe_revision"] = "future-probe"
        with self.assertRaisesRegex(ValueError, "manifest contract drifted"):
            browser_pair.build_browser_pair_evidence(
                self.fixture.row(),
                self.fixture.feature_catalog,
                manifest,
                self.policy,
            )

        policy = copy.deepcopy(self.policy)
        policy["required_input_contract"]["browser_probe_revision"] = "future-probe"
        with self.assertRaisesRegex(ValueError, "input contract drifted"):
            browser_pair.build_browser_pair_evidence(
                self.fixture.row(),
                self.fixture.feature_catalog,
                self.fixture.manifest(),
                policy,
            )


if __name__ == "__main__":
    unittest.main()
