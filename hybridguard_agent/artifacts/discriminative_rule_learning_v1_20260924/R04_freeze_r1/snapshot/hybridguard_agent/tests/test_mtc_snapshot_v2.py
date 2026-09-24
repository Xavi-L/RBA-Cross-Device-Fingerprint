import copy
from collections import Counter
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from hybridguard_agent.evidence import browser_pair_v2 as comparison
from hybridguard_agent.scripts import build_mtc_paired244_snapshot as mtc
from hybridguard_agent.scripts import build_latest_paired244_snapshot as legacy
from hybridguard_agent.tests.test_build_latest_paired244_snapshot import SnapshotFixture, CATALOG_PATH, read_jsonl


def status_change(payload, fields, state):
    for field in fields:
        payload["collection_status"]["fields"][field] = state
        obj = payload
        parts = field.split(".")
        for part in parts[:-1]:
            obj = obj[part]
        obj.pop(parts[-1])
    counts = Counter(payload["collection_status"]["fields"].values())
    payload["collection_status"]["counts"] = {s: counts[s] for s in legacy.ALLOWED_FIELD_STATES}


class MtcSnapshotV2Tests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(mtc.DEFAULT_CONFIG.read_text())
        self.policy = comparison.load_policy()
        self.fields, self.web_fields, self.types, self.web_types = legacy.load_catalog(CATALOG_PATH, 177, 67)
        self.release = {**self.config["release_contract"], **self.config["allowed_releases"][0]}

    def payload(self, root):
        return SnapshotFixture(root).app_payload("fixture", version_code=9, version_name=self.release["featureapp_version_name"])

    def test_only_explicit_unavailable_missing_fields_receive_null_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.payload(Path(tmp))
            field = "android_native_data.build_fingerprint_layer.security_patch"
            status_change(payload, [field], "unsupported_by_os")
            original = copy.deepcopy(payload)
            errors, features, statuses, inserted, empty = mtc.normalize_app(payload, self.release, self.fields, self.types)
            self.assertEqual((errors, inserted, empty), ([], [field], []))
            self.assertIsNone(features[field])
            self.assertEqual(statuses[field], "unsupported_by_os")
            self.assertEqual(payload, original)
            payload["collection_status"]["fields"][field] = "observed"
            self.assertIn("Q_APP_FEATURESET_INVALID", mtc.normalize_app(payload, self.release, self.fields, self.types)[0])

    def test_whole_web_layers_timeout_remain_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.payload(Path(tmp))
            fields = [f for f in self.fields if not f.startswith("android_native_data.")]
            status_change(payload, fields, "timeout")
            errors, features, statuses, inserted, empty = mtc.normalize_app(payload, self.release, self.fields, self.types)
            self.assertEqual(errors, [])
            self.assertEqual(len(inserted), 93)
            self.assertEqual(empty, ["webview_data", "web_data"])
            self.assertEqual(sum(v == "observed" for v in statuses.values()), 84)

    def test_numeric_equality_preserves_bool_null_array_and_string_boundaries(self):
        for a, b, expected in [(8, 8.0, True), (True, 1, False), (None, 0, False), ("8", 8, False),
                               ([8, False], [8.0, False], True), ([1, 2], [2, 1], False), (float("nan"), float("nan"), False)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(comparison.semantic_equal(a, b), expected)

    def test_unavailable_and_known_sentinel_cannot_create_false_conflict(self):
        field = "web_data.navigator_layer.device_memory"
        check = lambda a, b, state="observed": comparison.compare_field(field, "number", a, b, state, "observed", self.policy)
        self.assertEqual(check(8, 8.0)["result"], "same")
        self.assertEqual(check(0, 8)["result"], "unavailable")
        self.assertEqual(check(None, 8, "unsupported_by_os")["result"], "unavailable")
        self.assertEqual(check(None, 8, "timeout")["result"], "unavailable")
        self.assertEqual(comparison.quality_state("web_data.navigator_layer.max_touch_points", 0, "observed", self.policy), "observed_value")
        with self.assertRaisesRegex(ValueError, "violates field type"):
            check(True, 1)

    def test_duplicate_receipt_resolution_needs_evidence_and_exact_payload(self):
        row = legacy.SourceRow
        raw = row(1, {"receipt_id": "original", "session_id": "s", "payload_sha256": "h", "collection_batch_id": "b"})
        r = {"receipt_id": "retry", "session_id": "s", "payload_sha256": "h", "collection_batch_id": "b", "duplicate_payload": True, "stored_new_jsonl_row": False}
        pair = {"app_receipt_id": "retry", "app_session_id": "s", "app_payload_sha256": "h", "collection_batch_id": "b"}
        args = ({"retry": [row(2, r)]}, {"original": [raw]}, {("s", "h", "b"): [raw]})
        resolved, _, alias = mtc.resolve_pair_raw(pair, *args)
        self.assertEqual(resolved.line_number, 1)
        self.assertTrue(alias)
        r["duplicate_payload"] = False
        with self.assertRaisesRegex(ValueError, "ARCHIVE_NOT_UNIQUE"):
            mtc.resolve_pair_raw(pair, *args)
        r["duplicate_payload"] = True
        pair["app_payload_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "IDENTITY_MISMATCH"):
            mtc.resolve_pair_raw(pair, *args)

    def test_end_to_end_mixed_versions_partial_and_receipt_bound_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = SnapshotFixture(root)

            def add_app(session, version_index, partial=False):
                app = fixture.add_app(session)
                raw = fixture.rows["app_raw"][-1]
                payload = raw["canonical_received_payload"]
                release = self.config["allowed_releases"][version_index]
                payload["collection_manifest"].update(collector_version_code=release["featureapp_version_code"],
                    collector_version_name=release["featureapp_version_name"], manufacturer="fixture", model=session,
                    android_release="12", android_api=31, collector_install_id="install-" + session)
                if partial:
                    status_change(payload, [f for f in self.fields if not f.startswith("android_native_data.")], "timeout")
                digest = legacy.sha256_value(payload)
                raw["payload_sha256"] = app["payload_sha256"] = fixture.rows["app_receipts"][-1]["payload_sha256"] = digest
                fixture.rows["app_analysis"][-1] = copy.deepcopy(payload)
                return app

            first = add_app("paired", 0)
            fixture.add_pair(first)
            second = add_app("partial", 1, partial=True)
            fixture.add_pair(second)
            add_app("app-only", 1)
            revision = copy.deepcopy(fixture.rows["app_raw"][0])
            revision["receipt_id"] = "revision-receipt"
            revision["canonical_received_payload"]["timestamp"] += 100
            revision["payload_sha256"] = legacy.sha256_value(revision["canonical_received_payload"])
            fixture.rows["app_raw"].append(revision)
            revision_receipt = copy.deepcopy(fixture.rows["app_receipts"][0])
            revision_receipt.update(receipt_id=revision["receipt_id"], payload_sha256=revision["payload_sha256"])
            fixture.rows["app_receipts"].append(revision_receipt)
            fixture.rows["app_analysis"].append(copy.deepcopy(revision["canonical_received_payload"]))
            for analysis in fixture.rows["app_analysis"]:
                for layer in legacy.APP_ROOTS:
                    analysis[layer] = {k.rsplit(".", 1)[-1]: v for k, v in legacy.feature_map(analysis, (layer,)).items()}
            freeze = root / "freeze"
            (freeze / "sources").mkdir(parents=True)
            (freeze / "contracts").mkdir()
            shutil.copyfile(CATALOG_PATH, freeze / "contracts/expanded_v2_field_catalog.csv")
            shutil.copyfile(fixture.probe_manifest, freeze / "contracts/manifest.json")
            mapping = {"app_raw": "raw_expanded_payloads", "app_analysis": "expanded_collected_data", "app_receipts": "collection_receipts",
                       "browser_raw": "raw_browser_payloads", "browser_analysis": "browser_collected_data"}
            names = []
            for key, rows in fixture.rows.items():
                name = mapping.get(key, key) + ".jsonl"
                names.append(name)
                legacy.write_jsonl(freeze / "sources" / name, rows)
            legacy.write_json(freeze / "FREEZE_MANIFEST.json", {"freeze_schema_version": "mtc-p0-closed-source-copy-v2", "collection_retired": True,
                "source_directory": "/fixture/mtc_20260917", "cutoff_utc": "2026-09-22T08:39:43Z", "source_files": {n: {} for n in names}})
            legacy.write_json(freeze / "SUMMARY.json", {"p0_complete": True, "paired_manufacturer_model_os": 2})
            config_path = root / "mtc.json"
            legacy.write_json(config_path, {**self.config, "freeze_directory": str(freeze)})
            out = root / "out"
            result = mtc.build(config_path, out)
            self.assertEqual(result["view_counts"], {"paired_244": 1, "app_only_177": 1, "partial": 1, "repeated_observations": 1, "quarantine": 0})
            self.assertEqual(result["auxiliary_issue_count"], 0)
            paired = read_jsonl(out / "paired_244.jsonl")[0]
            self.assertEqual(paired["app"]["receipt_id"], first["receipt_id"])
            self.assertEqual(len(paired["features"]), 244)
            self.assertEqual(len(read_jsonl(out / "selection_audit.jsonl")), 4)
            self.assertEqual(read_jsonl(out / "partial.jsonl")[0]["qc"]["layers_without_observed_fields"], ["webview_data", "web_data"])
            with self.assertRaisesRegex(ValueError, "must be new"):
                mtc.build(config_path, out)


if __name__ == "__main__":
    unittest.main()
