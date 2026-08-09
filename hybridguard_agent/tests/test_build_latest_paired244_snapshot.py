import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hybridguard_agent.scripts import build_latest_paired244_snapshot as snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = (
    REPO_ROOT
    / "android_app"
    / "HybridGuard"
    / "featureapp"
    / "src"
    / "main"
    / "assets"
    / "expanded_v2_field_catalog.csv"
)


def set_path(target: dict, path: str, value):
    current = target
    segments = path.split(".")
    for segment in segments[:-1]:
        current = current.setdefault(segment, {})
    current[segments[-1]] = value


def catalog_rows():
    with CATALOG_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row["layer"] in snapshot.APP_ROOTS
        ]


def fixture_value(type_name: str):
    return {
        "boolean": False,
        "number": 1,
        "string": "fixture",
        "array": [],
    }[type_name]


def collection_status(fields, schema_version):
    statuses = {field: "observed" for field in fields}
    return {
        "status_schema_version": schema_version,
        "fixed_signal_count": len(fields),
        "counts": {
            "observed": len(fields),
            "unsupported_by_os": 0,
            "permission_denied": 0,
            "runtime_error": 0,
            "timeout": 0,
            "not_applicable": 0,
        },
        "fields": statuses,
    }


class SnapshotFixture:
    def __init__(self, root: Path):
        self.root = root
        self.rows = {
            "app_analysis": [],
            "app_raw": [],
            "app_receipts": [],
            "collection_batches": [],
            "browser_analysis": [],
            "browser_raw": [],
            "browser_pair_provenance": [],
            "browser_pair_events": [],
        }
        self.catalog = catalog_rows()
        self.app_fields = [row["field"] for row in self.catalog]
        self.browser_catalog = [row for row in self.catalog if row["layer"] == "web_data"]
        self.browser_fields = [row["field"] for row in self.browser_catalog]
        self.build_file = root / "build.gradle.kts"
        self.build_file.write_text(
            'versionCode = 8\nversionName = "1.6.1-expanded-v2.2-browser-recovery"\n',
            encoding="utf-8",
        )
        self.probe_manifest = root / "browser_probe_manifest.json"
        self.probe_manifest.write_text(
            json.dumps({"revision": "expanded-web-67-v1", "signal_count": 67}),
            encoding="utf-8",
        )

    def app_payload(self, session_id: str, version_code=8, version_name=None):
        payload = {}
        for row in self.catalog:
            set_path(payload, row["field"], fixture_value(row["type"]))
        version_name = version_name or (
            "1.6.1-expanded-v2.2-browser-recovery"
            if version_code == 8
            else f"legacy-{version_code}"
        )
        payload.update(
            {
                "session_id": session_id,
                "timestamp": 1_800_000_000,
                "collector_app": "featureapp",
                "schema_version": "expanded-v2.2-status",
                "collection_manifest": {
                    "manifest_schema_version": "device-profile-manifest-v1",
                    "collection_protocol_version": "featureapp-collection-protocol-v3",
                    "device_manifest_id": f"profile-{session_id}",
                    "runtime_context": "test_fixture",
                    "collection_round": 1,
                    "collector_version_code": version_code,
                    "collector_version_name": version_name,
                    "schema_version": "expanded-v2.2-status",
                },
                "collection_status": collection_status(self.app_fields, "field-status-v1"),
                "collection_diagnostics": {
                    "diagnostics_schema_version": "collection-diagnostics-v1"
                },
            }
        )
        return payload

    def add_app(
        self, session_id: str, version_code=8, include_raw=True, include_analysis=True
    ):
        payload = self.app_payload(session_id, version_code=version_code)
        if include_analysis:
            self.rows["app_analysis"].append(copy.deepcopy(payload))
        batch_id = f"batch-{session_id}"
        receipt_id = f"receipt-{session_id}"
        payload_hash = snapshot.sha256_value(payload)
        if include_raw:
            self.rows["app_raw"].append(
                {
                    "raw_payload_archive_schema_version": "expanded-raw-payload-v1",
                    "session_id": session_id,
                    "receipt_id": receipt_id,
                    "payload_sha256": payload_hash,
                    "stored_new_jsonl_row": True,
                    "duplicate_payload": False,
                    "collection_batch_id": batch_id,
                    "collection_batch_id_source": "backend_process_lifecycle",
                    "canonical_received_payload": copy.deepcopy(payload),
                }
            )
            self.rows["app_receipts"].append(
                {
                    "receipt_schema_version": "collection-receipt-v1",
                    "receipt_id": receipt_id,
                    "session_id": session_id,
                    "payload_sha256": payload_hash,
                    "stored_new_jsonl_row": True,
                    "duplicate_payload": False,
                    "collection_batch_id": batch_id,
                    "collection_batch_id_source": "backend_process_lifecycle",
                }
            )
            self.rows["collection_batches"].extend(
                [
                    {
                        "collection_batch_schema_version": "backend-collection-batch-v1",
                        "collection_batch_id": batch_id,
                        "event": "started",
                        "lifecycle_status": "open",
                    },
                    {
                        "collection_batch_schema_version": "backend-collection-batch-v1",
                        "collection_batch_id": batch_id,
                        "event": "closed",
                        "lifecycle_status": "closed_cleanly",
                    },
                ]
            )
        return {
            "session_id": session_id,
            "receipt_id": receipt_id,
            "payload_sha256": payload_hash,
            "batch_id": batch_id,
        }

    def add_pair(self, app):
        pair_id = f"pair-{app['session_id']}"
        browser_session_id = f"browser-{app['session_id']}"
        browser_receipt_id = f"browser-receipt-{app['session_id']}"
        browser_payload = {}
        for row in self.browser_catalog:
            set_path(browser_payload, row["field"], fixture_value(row["type"]))
        browser_payload.update(
            {
                "browser_session_id": browser_session_id,
                "pair_id": pair_id,
                "timestamp": 1_800_000_001,
                "collector_app": "browserprobe",
                "schema_version": "browser-web-v1-status",
                "web_probe_revision": "expanded-web-67-v1",
                "probe_metadata": {
                    "core_revision": "expanded-web-67-v1",
                    "expected_signal_count": 67,
                },
                "collection_status": collection_status(
                    self.browser_fields, "browser-field-status-v1"
                ),
                "collection_diagnostics": {
                    "diagnostics_schema_version": "browser-web-probe-diagnostics-v1"
                },
            }
        )
        browser_hash = snapshot.sha256_value(browser_payload)
        common = {
            "pair_id": pair_id,
            "app_session_id": app["session_id"],
            "app_receipt_id": app["receipt_id"],
            "app_payload_sha256": app["payload_sha256"],
            "browser_session_id": browser_session_id,
            "browser_receipt_id": browser_receipt_id,
            "browser_payload_sha256": browser_hash,
            "collection_batch_id": app["batch_id"],
        }
        self.rows["browser_raw"].append(
            {
                **common,
                "raw_browser_payload_schema_version": "browser-raw-payload-v1",
                "collection_batch_id_source": "backend_process_lifecycle",
                "canonical_received_payload": copy.deepcopy(browser_payload),
            }
        )
        self.rows["browser_analysis"].append(
            {
                **common,
                "browser_collected_data_schema_version": "browser-collected-data-v1",
                **copy.deepcopy(browser_payload),
            }
        )
        self.rows["browser_pair_provenance"].append(
            {
                **common,
                "browser_pair_provenance_schema_version": "browser-pair-provenance-v1",
                "pair_status": "completed",
                "resolved_browser_package": "com.example.browser",
                "web_probe_revision": "expanded-web-67-v1",
            }
        )
        return pair_id

    def add_awaiting_event(self, app):
        self.rows["browser_pair_events"].append(
            {
                "browser_pair_event_schema_version": "browser-pair-event-v1",
                "event": "app_receipt_bound",
                "pair_id": f"pair-{app['session_id']}",
                "pair_status": "awaiting_browser",
                "app_session_id": app["session_id"],
                "app_receipt_id": app["receipt_id"],
                "collection_batch_id": app["batch_id"],
            }
        )

    def set_app_feature(self, app, field, value):
        for analysis in self.rows["app_analysis"]:
            if analysis["session_id"] == app["session_id"]:
                set_path(analysis, field, value)
        raw = next(
            row for row in self.rows["app_raw"] if row["session_id"] == app["session_id"]
        )
        set_path(raw["canonical_received_payload"], field, value)
        payload_hash = snapshot.sha256_value(raw["canonical_received_payload"])
        raw["payload_sha256"] = payload_hash
        receipt = next(
            row for row in self.rows["app_receipts"] if row["receipt_id"] == app["receipt_id"]
        )
        receipt["payload_sha256"] = payload_hash
        app["payload_sha256"] = payload_hash

    def set_browser_feature(self, pair_id, field, value):
        analysis = next(
            row for row in self.rows["browser_analysis"] if row["pair_id"] == pair_id
        )
        raw = next(row for row in self.rows["browser_raw"] if row["pair_id"] == pair_id)
        set_path(analysis, field, value)
        set_path(raw["canonical_received_payload"], field, value)
        payload_hash = snapshot.sha256_value(raw["canonical_received_payload"])
        raw["browser_payload_sha256"] = payload_hash
        analysis["browser_payload_sha256"] = payload_hash
        provenance = next(
            row
            for row in self.rows["browser_pair_provenance"]
            if row["pair_id"] == pair_id
        )
        provenance["browser_payload_sha256"] = payload_hash

    def flush(self):
        source_paths = {}
        for name, rows in self.rows.items():
            path = self.root / f"{name}.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            source_paths[name] = str(path)
        source_paths.update(
            {
                "feature_catalog": str(CATALOG_PATH),
                "browser_probe_manifest": str(self.probe_manifest),
            }
        )
        config = {
            "config_version": "latest-paired244-sources-v1",
            "release": {
                "featureapp_version_code": 8,
                "featureapp_version_name": "1.6.1-expanded-v2.2-browser-recovery",
                "featureapp_build_file": str(self.build_file),
                "app_collector": "featureapp",
                "app_schema_version": "expanded-v2.2-status",
                "app_status_schema_version": "field-status-v1",
                "app_signal_count": 177,
                "browser_collector": "browserprobe",
                "browser_schema_version": "browser-web-v1-status",
                "browser_status_schema_version": "browser-field-status-v1",
                "browser_probe_revision": "expanded-web-67-v1",
                "browser_signal_count": 67,
                "pair_provenance_schema_version": "browser-pair-provenance-v1",
                "batch_id_source": "backend_process_lifecycle",
                "require_closed_batch": True,
            },
            "sources": source_paths,
            "policy": {
                "dataset_role": "development_qc_only",
                "label_status": "unlabeled",
            },
        }
        config_path = self.root / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return config_path


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class BuildLatestPaired244SnapshotTests(unittest.TestCase):
    def test_builds_paired_and_app_only_views(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            paired_app = fixture.add_app("app-paired")
            fixture.add_pair(paired_app)
            retained_app = fixture.add_app("app-retained")
            fixture.add_awaiting_event(retained_app)
            output = root / "snapshot"

            manifest = snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            self.assertEqual(manifest["views"]["paired_244"]["count"], 1)
            self.assertEqual(manifest["views"]["app_only_177"]["count"], 1)
            self.assertEqual(manifest["views"]["quarantine"]["count"], 0)
            paired = read_jsonl(output / "paired_244.jsonl")[0]
            retained = read_jsonl(output / "app_only_177.jsonl")[0]
            self.assertEqual(paired["feature_count"], 244)
            self.assertEqual(len(paired["features"]), 244)
            self.assertEqual(len(paired["field_status"]), 244)
            self.assertTrue(any(key.startswith("browser.web_data.") for key in paired["features"]))
            self.assertEqual(retained["feature_count"], 177)
            self.assertFalse(any(key.startswith("browser.") for key in retained["features"]))
            self.assertEqual(
                set(paired),
                {
                    "record_schema_version",
                    "sample_id",
                    "dataset_view",
                    "dataset_role",
                    "label_status",
                    "feature_count",
                    "features",
                    "field_status",
                },
            )
            index_rows = read_jsonl(output / "sample_index.jsonl")
            retained_index = next(
                row for row in index_rows if row["dataset_view"] == "app_only_177"
            )
            self.assertEqual(
                retained_index["browser_capture_status"], "attempted_incomplete"
            )
            self.assertEqual(len(index_rows), 2)
            qc = json.loads((output / "qc_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(qc["counts"]["app177_valid_count"], 2)
            self.assertEqual(qc["counts"]["browser_attempted_count"], 2)

    def test_invalid_completed_pair_retains_valid_app(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            app = fixture.add_app("app-invalid-pair")
            fixture.add_pair(app)
            fixture.rows["browser_pair_provenance"][0]["browser_payload_sha256"] = "f" * 64
            output = root / "snapshot"

            manifest = snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            self.assertEqual(manifest["views"]["paired_244"]["count"], 0)
            self.assertEqual(manifest["views"]["app_only_177"]["count"], 1)
            self.assertEqual(manifest["views"]["quarantine"]["count"], 1)
            retained = next(
                row
                for row in read_jsonl(output / "sample_index.jsonl")
                if row["dataset_view"] == "app_only_177"
            )
            self.assertEqual(
                retained["paired_exclusion_reason"],
                "completed_pair_failed_qc",
            )
            quarantine = read_jsonl(output / "quarantine.jsonl")[0]
            self.assertIn("Q_PAIR_ID_RECEIPT_HASH_BATCH_MISMATCH", quarantine["reason_codes"])

    def test_expired_browser_attempt_is_retained_as_attempted_incomplete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            app = fixture.add_app("app-expired-browser")
            fixture.rows["browser_pair_events"].append(
                {
                    "event": "browser_ticket_expired",
                    "pair_id": "pair-app-expired-browser",
                    "pair_status": "expired",
                    "app_session_id": app["session_id"],
                    "app_receipt_id": app["receipt_id"],
                    "collection_batch_id": app["batch_id"],
                }
            )
            output = root / "snapshot"

            snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            retained = read_jsonl(output / "sample_index.jsonl")[0]
            self.assertEqual(retained["browser_capture_status"], "attempted_incomplete")
            self.assertEqual(
                retained["paired_exclusion_reason"], "browser_pair_expired"
            )

    def test_old_release_is_excluded_and_invalid_latest_app_is_quarantined(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            fixture.add_app("legacy-app", version_code=7, include_raw=False)
            fixture.add_app("latest-without-raw", include_raw=False)
            output = root / "snapshot"

            manifest = snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            self.assertEqual(manifest["views"]["paired_244"]["count"], 0)
            self.assertEqual(manifest["views"]["app_only_177"]["count"], 0)
            self.assertEqual(manifest["views"]["quarantine"]["count"], 1)
            qc = json.loads((output / "qc_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(qc["excluded_input_rows_by_reason"]["legacy_featureapp_release"], 1)
            audits = read_jsonl(output / "selection_audit.jsonl")
            self.assertEqual(
                {row["outcome"] for row in audits},
                {"excluded_legacy", "quarantine"},
            )

    def test_raw_only_latest_app_is_not_lost(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            app = fixture.add_app("raw-only-app", include_analysis=False)
            fixture.add_pair(app)
            output = root / "snapshot"

            manifest = snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            self.assertEqual(manifest["views"]["paired_244"]["count"], 1)
            index = read_jsonl(output / "sample_index.jsonl")[0]
            self.assertFalse(index["app_analysis_available"])
            audit = read_jsonl(output / "selection_audit.jsonl")[0]
            self.assertEqual(audit["analysis_source_lines"], [])
            self.assertTrue(audit["raw_source_lines"])

    def test_invalid_app_feature_type_is_quarantined(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            app = fixture.add_app("app-bad-type")
            number_field = next(
                row["field"] for row in fixture.catalog if row["type"] == "number"
            )
            fixture.set_app_feature(app, number_field, "not-a-number")
            output = root / "snapshot"

            manifest = snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            self.assertEqual(manifest["views"]["paired_244"]["count"], 0)
            self.assertEqual(manifest["views"]["app_only_177"]["count"], 0)
            quarantine = read_jsonl(output / "quarantine.jsonl")[0]
            self.assertIn("Q_APP_FEATURE_TYPE_INVALID", quarantine["reason_codes"])

    def test_invalid_browser_feature_type_retains_valid_app(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            app = fixture.add_app("browser-bad-type")
            pair_id = fixture.add_pair(app)
            number_field = next(
                row["field"] for row in fixture.browser_catalog if row["type"] == "number"
            )
            fixture.set_browser_feature(pair_id, number_field, "not-a-number")
            output = root / "snapshot"

            manifest = snapshot.build_snapshot(fixture.flush(), output, "fixture-run")

            self.assertEqual(manifest["views"]["paired_244"]["count"], 0)
            self.assertEqual(manifest["views"]["app_only_177"]["count"], 1)
            quarantine = read_jsonl(output / "quarantine.jsonl")[0]
            self.assertIn("Q_BROWSER_FEATURE_TYPE_INVALID", quarantine["reason_codes"])

    def test_rejects_inputs_changed_during_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = SnapshotFixture(root)
            fixture.add_app("app-changing-input")
            config_path = fixture.flush()
            events_path = root / "browser_pair_events.jsonl"
            original_read_jsonl = snapshot.read_jsonl
            changed = False

            def read_and_change(path):
                nonlocal changed
                rows = original_read_jsonl(path)
                if path.name == "app_analysis.jsonl" and not changed:
                    with events_path.open("a", encoding="utf-8") as handle:
                        handle.write("{}\n")
                    changed = True
                return rows

            with mock.patch.object(snapshot, "read_jsonl", side_effect=read_and_change):
                with self.assertRaisesRegex(RuntimeError, "inputs changed during build"):
                    snapshot.build_snapshot(config_path, root / "snapshot", "fixture-run")


if __name__ == "__main__":
    unittest.main()
