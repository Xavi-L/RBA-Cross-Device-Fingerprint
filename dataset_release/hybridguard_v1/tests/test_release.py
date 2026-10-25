"""Offline release-boundary tests; fixtures contain synthetic observations only."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import common
import release

REPOSITORY = SCRIPTS.parents[2]
CONTRACT = json.loads((REPOSITORY / release.CONTRACT_PATH).read_text())
NORMALIZER = SimpleNamespace(
    canonicalize_payload=lambda payload, contract: payload,
    validate_v2_row=lambda payload, contract: ([], [], {}),
)


def synthetic_record(paired=False):
    """Unavailable source fields retain real slots and explicit unknown state."""
    app = {layer: {} for layer in common.APP_LAYERS}
    states = {}
    for key in CONTRACT["fields"]:
        layer, leaf = key.split(".", 1)
        app[layer][leaf] = None
        states[key] = "unknown"
    app["collection_status"] = {"fields": states}
    app["schema_version"] = "expanded-v2.2-status"
    app["android_native_data"]["is_charging"] = False
    app["web_data"]["hardware_concurrency"] = 0
    states["android_native_data.is_charging"] = "observed"
    states["web_data.hardware_concurrency"] = "observed"
    record = {
        "source_id": "synthetic_fixture",
        "record_key": "private-synthetic-observation",
        "app": app,
        "group_key": "private-synthetic-group",
        "group_basis": "synthetic_test_group",
        "metadata": {"environment": "synthetic", "cohort": "test_only"},
        "annotation": {"label": "unlabeled", "label_verification": "unverified"},
        "provenance": [{"path": "synthetic", "line": 1}],
    }
    if paired:
        record["browser"] = {k.split(".", 1)[1]: None for k in CONTRACT["fields"] if k.startswith("web_data.")}
        record["browser_status"] = {"fields": {"web_data." + k: "unknown" for k in record["browser"]}}
    return record


class TemporaryRelease(unittest.TestCase):
    def setUp(self):
        # The test root and all mappings remain beneath the real ignored area.
        real_private = SCRIPTS.parent / ".private"
        real_private.mkdir(exist_ok=True, mode=0o700)
        self.tmp = tempfile.TemporaryDirectory(prefix="unit-tests-", dir=real_private)
        self.root = Path(self.tmp.name)
        (self.root / ".private" / "candidate").mkdir(parents=True)
        (self.root / "data").mkdir()
        self.out = self.root / ".private" / "candidate"
        self.patches = [mock.patch.object(common, "ROOT", self.root),
                        mock.patch.object(release, "ROOT", self.root),
                        mock.patch.object(release, "PRIVATE", self.root / ".private")]
        for patch in self.patches:
            patch.start()
        release.make_schema(CONTRACT)

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def candidate(self, paired=False, triplet=False):
        tables = {name: [] for name in release.DATA_FILES}
        phases = ("clean_pre", "active", "clean_post") if triplet else (None,)
        for index, phase in enumerate(phases, 1):
            record = synthetic_record(paired)
            view, fields, qc = release.normalize_record(record, CONTRACT, NORMALIZER)
            sid = "sample_" + f"{index:032x}"
            tables["features.jsonl"].append({"record_type": "features", "sample_id": sid, "view": view, "fields": fields, "supplemental": {}})
            tables["metadata.jsonl"].append({
                "record_type": "metadata", "sample_id": sid,
                "source_id": "synthetic_fixture", "group_id": "group_" + "b" * 32,
                "view": view, "android_api_level": None, **release.safe_metadata(record, qc),
            })
            annotation = {"record_type": "annotations", "sample_id": sid, **release.safe_annotation(record)}
            if phase is not None:
                annotation["phase"] = phase
            tables["annotations.jsonl"].append(annotation)
            if paired:
                tables["pairs.jsonl"].append({
                    "record_type": "pairs", "pair_id": "pair_" + f"{index:032x}",
                    "kind": "linked_app_browser", "members": [{"sample_id": sid, "phase": "linked_endpoints"}],
                })
        if triplet:
            tables["pairs.jsonl"].append({
                "record_type": "pairs", "pair_id": "pair_" + "c" * 32,
                "kind": "experiment_triplet",
                "members": [{"sample_id": row["sample_id"], "phase": phase}
                            for row, phase in zip(tables["features.jsonl"], phases)],
            })
        self.save(tables)
        return tables

    def save(self, tables):
        for name, rows in tables.items():
            common.write_jsonl(self.out / name, rows)
        common.write_json(self.out / "statistics.json", release.compute_statistics(tables))


class NormalizeTests(unittest.TestCase):
    def test_false_and_zero_are_observed_values(self):
        view, cells, qc = release.normalize_record(synthetic_record(), CONTRACT, NORMALIZER)
        self.assertEqual(view, "App177")
        self.assertIs(cells["android_native_data.is_charging"]["value"], False)
        self.assertEqual(cells["web_data.hardware_concurrency"]["value"], 0)
        self.assertEqual(cells["web_data.hardware_concurrency"]["collection_status"], "observed")
        self.assertTrue(qc["structurally_complete"])
        self.assertFalse(any(k.startswith(common.BROWSER + ".") for k in cells))

    def test_original_missing_slot_and_unavailable_status_are_distinct(self):
        record = synthetic_record()
        key = "android_native_data.screen_mode_physical_width"
        del record["app"]["android_native_data"]["screen_mode_physical_width"]
        record["app"]["collection_status"]["fields"][key] = "unsupported_by_os"
        _, cells, qc = release.normalize_record(record, CONTRACT, NORMALIZER)
        self.assertEqual(cells[key], {"value": None, "collection_status": "unsupported_by_os",
                         "status_origin": "collector_emitted", "original_field_present": False, "redaction": "none"})
        self.assertEqual(qc["source_missing_fields"], [key])
        self.assertFalse(qc["structurally_complete"])

    def test_unrecorded_status_does_not_become_observed(self):
        record = synthetic_record()
        del record["app"]["collection_status"]["fields"]["web_data.hardware_concurrency"]
        _, cells, _ = release.normalize_record(record, CONTRACT, NORMALIZER)
        self.assertEqual(cells["web_data.hardware_concurrency"]["collection_status"], "present_status_unknown")
        self.assertEqual(cells["web_data.hardware_concurrency"]["status_origin"], "not_recorded")

    def test_observed_state_requires_original_slot(self):
        record = synthetic_record()
        del record["app"]["web_data"]["hardware_concurrency"]
        with self.assertRaises(ValueError):
            release.normalize_record(record, CONTRACT, NORMALIZER)

    def test_empty_browser_cannot_create_paired_view(self):
        record = synthetic_record()
        record["browser"] = {}
        with self.assertRaises(ValueError):
            release.normalize_record(record, CONTRACT, NORMALIZER)

    def test_boolean_is_not_a_numeric_measurement(self):
        record = synthetic_record()
        record["app"]["web_data"]["hardware_concurrency"] = True
        with self.assertRaises(ValueError):
            release.normalize_record(record, CONTRACT, NORMALIZER)

    def test_free_text_and_runtime_clocks_are_suppressed(self):
        self.assertEqual(common.sanitize_value("web_data.user_agent", "private-agent", ["string"]),
                         (None, "remove_free_text_or_high_entropy_value"))
        self.assertEqual(common.sanitize_value("android_native_data.uptime_ms", 12345, ["integer"]),
                         (None, "remove_precise_time"))


class PrivateBoundaryTests(TemporaryRelease):
    def test_random_mapping_persists_without_deriving_identifier(self):
        path = self.root / ".private" / "identity_map.json"
        ids = common.RandomIDs(path)
        first = ids.get("sample", "private-input-key")
        self.assertEqual(first, ids.get("sample", "private-input-key"))
        self.assertNotEqual(first, ids.get("sample", "another-input-key"))
        ids.save()
        self.assertEqual(first, common.RandomIDs(path).get("sample", "private-input-key"))
        self.assertNotIn("private-input", first)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_private_destination_rejects_base_escape_and_symlink(self):
        self.assertEqual(common.private_destination(self.out), self.out)
        for path in (self.root / ".private", self.root / "public", self.root / ".private" / ".." / "public"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                common.private_destination(path)
        (self.root / ".private" / "escape").symlink_to(self.root / "data", target_is_directory=True)
        with self.assertRaises(ValueError):
            common.private_destination(self.root / ".private" / "escape" / "candidate")

    def test_frozen_input_drift_is_rejected_even_at_same_size(self):
        source = self.root / "fixture.txt"
        source.write_text("first\n")
        lock = {"inputs": release.frozen_inputs(self.root, ["fixture.txt"])}
        common.write_json(self.root / ".private" / "source_lock.json", lock)
        self.assertEqual(release.check_lock(self.root), lock)
        source.write_text("other\n")
        with self.assertRaisesRegex(ValueError, "Frozen input drift"):
            release.check_lock(self.root)

    def test_package_checks_source_lock_before_writing_archive(self):
        with mock.patch.object(release, "check_lock", side_effect=ValueError("Frozen input drift")) as check, \
                mock.patch.object(release, "verify"):
            with self.assertRaisesRegex(ValueError, "Frozen input drift"):
                release.package_candidate()
            check.assert_called_once()
        self.assertFalse((self.root / ".private" / "hybridguard_v1_INTERNAL_REVIEW_ONLY.zip").exists())


class SchemaAndPrivacyTests(TemporaryRelease):
    def test_schema_rejects_missing_extra_and_wrong_types(self):
        row = self.candidate()["features.jsonl"][0]
        schema = json.loads((self.root / "schema.json").read_text())
        common.validate_schema(row, schema)
        missing, extra, wrong = copy.deepcopy(row), copy.deepcopy(row), copy.deepcopy(row)
        del missing["sample_id"]
        extra["collector_install_id"] = "synthetic-private-id"
        wrong["fields"]["android_native_data.is_charging"]["value"] = 1
        for altered in (missing, extra, wrong):
            with self.assertRaises(ValueError):
                common.validate_schema(altered, schema)

    def test_privacy_scanner_detects_sensitive_text_without_echoing_it(self):
        fixtures = {
            "email": "person@example.test", "ipv4": "192.0.2.8", "home_path": "/Users/tester/private",
            "credential": "Bearer abcdefghijklmnopqrstuvwxyz123", "exact_timestamp": "2026-10-25T12:34:56Z",
            "phone": "+86 13800000000", "author_identity": common.getpass.getuser(),
        }
        for category, value in fixtures.items():
            with self.subTest(category=category):
                finding = common.privacy_findings({"note": value})
                self.assertGreater(finding.get(category, 0), 0)
                self.assertNotIn(value, json.dumps(finding))
        self.assertIn("source_identity_key", common.privacy_findings({"session_id": "synthetic"}))
        self.assertEqual(common.privacy_findings({"measurement": 13800000000, "language": "en-US"}), {})


class CandidateVerificationTests(TemporaryRelease):
    def test_valid_app_and_paired_candidate(self):
        for paired in (False, True):
            self.candidate(paired=paired)
            self.assertEqual(release.verify(self.out)["status"], "PASS")

    def test_statistics_corruption_is_rejected(self):
        self.candidate()
        path = self.out / "statistics.json"
        stats = json.loads(path.read_text())
        stats["total_unique_observations"] += 1
        common.write_json(path, stats)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_dangling_and_missing_endpoint_links_are_rejected(self):
        for corruption in ("dangling", "missing"):
            tables = self.candidate(paired=True)
            if corruption == "dangling":
                tables["pairs.jsonl"][0]["members"][0]["sample_id"] = "sample_" + "f" * 32
            else:
                tables["pairs.jsonl"] = []
            self.save(tables)
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                release.verify(self.out)

    def test_missing_feature_or_injected_public_identity_is_rejected(self):
        for corruption in ("field", "identity"):
            tables = self.candidate()
            if corruption == "field":
                del tables["features.jsonl"][0]["fields"]["web_data.hardware_concurrency"]
            else:
                tables["metadata.jsonl"][0]["environment"] = "person@example.test"
            self.save(tables)
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                release.verify(self.out)

    def test_all_absent_browser_cannot_masquerade_as_paired(self):
        tables = self.candidate(paired=True)
        f, m = tables["features.jsonl"][0], tables["metadata.jsonl"][0]
        for key, cell in f["fields"].items():
            if key.startswith(common.BROWSER + "."):
                cell.update(original_field_present=False, value=None, collection_status="missing", status_origin="not_recorded")
        m["qc"].update(original_field_slots=177, structurally_complete=False,
                         source_missing_fields=sorted(k for k in f["fields"] if k.startswith(common.BROWSER + ".")))
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_private_mapping_file_in_candidate_is_rejected(self):
        self.candidate()
        common.write_json(self.out / "identity_map.json", {})
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_fabricated_value_in_absent_slot_is_rejected(self):
        tables = self.candidate()
        key = "web_data.hardware_concurrency"
        tables["features.jsonl"][0]["fields"][key]["original_field_present"] = False
        tables["metadata.jsonl"][0]["qc"].update(original_field_slots=176, structurally_complete=False, source_missing_fields=[key])
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_qc_semantic_flags_are_recomputed(self):
        tables = self.candidate()
        tables["metadata.jsonl"][0]["qc"]["all_collection_states_observed"] = True
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_suppressed_text_cannot_be_restored_by_changing_redaction_flag(self):
        tables = self.candidate()
        cell = tables["features.jsonl"][0]["fields"]["web_data.user_agent"]
        cell.update(value="private-high-entropy-fingerprint-value", redaction="none")
        # This value intentionally matches no email/IP/token heuristic. The
        # field's suppress-all policy, not a lucky regex match, must reject it.
        self.assertEqual(common.privacy_findings(cell), {})
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_triplet_phase_matches_annotation(self):
        tables = self.candidate(triplet=True)
        self.assertEqual(release.verify(self.out)["status"], "PASS")
        tables["annotations.jsonl"][0]["phase"] = "active"
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_triplet_cannot_merge_unrelated_sources(self):
        tables = self.candidate(triplet=True)
        tables["metadata.jsonl"][0]["source_id"] = "unrelated_synthetic_source"
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)

    def test_endpoint_phase_is_not_arbitrary(self):
        tables = self.candidate(paired=True)
        tables["pairs.jsonl"][0]["members"][0]["phase"] = "arbitrary"
        self.save(tables)
        with self.assertRaises(ValueError):
            release.verify(self.out)


if __name__ == "__main__":
    unittest.main()
