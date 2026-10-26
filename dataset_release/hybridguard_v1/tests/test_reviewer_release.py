"""Regression tests for the standalone reviewer contract and anonymous archive.

Only already-exported observations are read. No collection, fitting, detector
execution or relabeling occurs. Integration checks skip in a code-only checkout
without the authorized local release input.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CANDIDATE = ROOT / ".private" / "candidate"
ARCHIVE = ROOT / "reviewer_release" / "Cross_View_Consistency_Dataset_v1.0_Reviewer.zip"
LICENSE_BASELINE_ARCHIVE = ROOT / ".private" / "license_update_baseline" / "old_reviewer.zip"
sys.path.insert(0, str(SCRIPTS))


@unittest.skipUnless((CANDIDATE / "features.jsonl").is_file(),
                     "Private candidate inputs are not distributed with code")
class ReviewerSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = importlib.import_module("reviewer_runtime")
        tables = cls.runtime.load_tables(CANDIDATE)
        metadata = {row["sample_id"]: row for row in tables["metadata.jsonl"]}
        annotations = {row["sample_id"]: row for row in tables["annotations.jsonl"]}
        # Small genuine fixtures preserve source-specific semantics and keep
        # corruption tests fast. Include one real five-slot incomplete record.
        selected = set()
        for source in ("controlled_main", "linked_browser_pilot18", "specialist_geometry"):
            pair = next(row for row in tables["pairs.jsonl"]
                        if row["kind"] == "experiment_triplet"
                        and metadata[row["members"][0]["sample_id"]]["source_id"] == source)
            selected.update(member["sample_id"] for member in pair["members"])
        selected.add(next(row["sample_id"] for row in metadata.values()
                          if not row["qc"]["structurally_complete"]))
        no_effect_pair = next(row for row in tables["pairs.jsonl"]
                              if row["kind"] == "experiment_triplet"
                              and any(annotations[m["sample_id"]]["label"] == "no_effect"
                                      for m in row["members"]))
        selected.update(member["sample_id"] for member in no_effect_pair["members"])
        cls.fixture = {name: [row for row in rows if
                             (all(member["sample_id"] in selected for member in row["members"])
                              if name == "pairs.jsonl" else row["sample_id"] in selected)]
                       for name, rows in tables.items()}
        for row in cls.fixture["metadata.jsonl"]:
            row["public_release_status"] = "AUTHORIZED_FOR_PUBLIC_RELEASE"
        cls.schema = json.loads((ROOT / "schema.json").read_text())
        cls.schema["$defs"]["metadata"]["properties"]["public_release_status"] = {
            "const": "AUTHORIZED_FOR_PUBLIC_RELEASE"}
        cls.catalog = json.loads((ROOT / "field_catalog.json").read_text())

    def setUp(self):
        self.tables = copy.deepcopy(self.fixture)

    def check(self):
        return self.runtime.validate_tables(self.tables, self.schema, self.catalog)

    def source_rows(self, source):
        meta = next(row for row in self.tables["metadata.jsonl"] if row["source_id"] == source)
        sid = meta["sample_id"]
        feature = next(row for row in self.tables["features.jsonl"] if row["sample_id"] == sid)
        annotation = next(row for row in self.tables["annotations.jsonl"] if row["sample_id"] == sid)
        return feature, meta, annotation

    def test_authorized_projection_validates_without_repository_objects(self):
        report = self.check()
        self.assertEqual(report["status"], "PASS")
        stats = self.runtime.compute_statistics(self.tables)
        self.assertEqual(stats["publication_status"], "AUTHORIZED_FOR_PUBLIC_RELEASE")
        self.assertEqual(stats["release_records"], 13)
        self.assertNotIn("public_data_records", stats)
        self.assertIsNone(stats["independent_physical_devices"])

    def test_original_missing_slots_remain_absent_and_unsupported(self):
        feature, meta, _ = self.source_rows("mtc_historical_891")
        self.assertFalse(meta["qc"]["structurally_complete"])
        self.assertEqual(len(meta["qc"]["source_missing_fields"]), 5)
        for field in meta["qc"]["source_missing_fields"]:
            self.assertEqual(feature["fields"][field], {
                "value": None, "original_field_present": False,
                "collection_status": "unsupported_by_os", "status_origin": "collector_emitted",
                "redaction": "none"})
        self.check()

    def test_approval_is_not_a_label_or_availability_upgrade(self):
        _, meta, annotation = self.source_rows("mtc_historical_891")
        self.assertEqual(annotation["label"], "unlabeled")
        self.assertEqual(annotation["label_verification"], "unverified")
        self.assertEqual(meta["public_release_status"], "AUTHORIZED_FOR_PUBLIC_RELEASE")
        self.assertFalse(meta["qc"]["all_collection_states_observed"])
        annotation.update(label="normal_control", label_verification="verified_recorded_evidence")
        with self.assertRaises(ValueError):
            self.check()

    def test_no_effect_operation_is_not_reclassified_as_modified(self):
        annotation = next(row for row in self.tables["annotations.jsonl"] if row["label"] == "no_effect")
        self.assertEqual(annotation["target_effect_status"], "no_observable_effect")
        self.check()
        annotation["label"] = "modified"
        with self.assertRaises(ValueError):
            self.check()

    def test_mtc_effect_and_detector_states_cannot_be_fabricated(self):
        for key in ("tool_execution_status", "target_effect_status", "detector_outcome"):
            with self.subTest(key=key):
                self.tables = copy.deepcopy(self.fixture)
                self.source_rows("mtc_historical_891")[2][key] = "verified"
                with self.assertRaises(ValueError):
                    self.check()

    def test_internal_status_cannot_pass_formal_release_schema(self):
        self.tables["metadata.jsonl"][0]["public_release_status"] = "NOT_APPROVED"
        with self.assertRaises(ValueError):
            self.check()

    def test_sidecar_identifier_and_view_corruption_are_rejected(self):
        for key, value in (("sample_id", "sample_" + "f" * 32), ("view", "Paired244")):
            with self.subTest(key=key):
                self.tables = copy.deepcopy(self.fixture)
                self.source_rows("controlled_main")[1][key] = value
                with self.assertRaises(ValueError):
                    self.check()

    def test_schema_omitted_extra_and_wrong_type_fields_are_rejected(self):
        for corruption in ("missing", "extra", "type"):
            with self.subTest(corruption=corruption):
                self.tables = copy.deepcopy(self.fixture)
                feature = self.tables["features.jsonl"][0]
                if corruption == "missing":
                    del feature["fields"]["web_data.hardware_concurrency"]
                elif corruption == "extra":
                    feature["collector_install_id"] = "synthetic-fixture-identity"
                else:
                    feature["fields"]["web_data.hardware_concurrency"]["value"] = True
                with self.assertRaises(ValueError):
                    self.check()

    def test_redaction_policy_cannot_be_bypassed_with_unrecognized_text(self):
        feature = self.tables["features.jsonl"][0]
        feature["fields"]["web_data.user_agent"].update(
            value="synthetic-unrecognized-high-entropy-text", redaction="none")
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_slot_cannot_acquire_a_value_or_observed_state(self):
        for corruption in ("value", "status"):
            with self.subTest(corruption=corruption):
                self.tables = copy.deepcopy(self.fixture)
                feature, meta, _ = self.source_rows("mtc_historical_891")
                cell = feature["fields"][meta["qc"]["source_missing_fields"][0]]
                cell.update({"value": 1} if corruption == "value" else {"collection_status": "observed"})
                with self.assertRaises(ValueError):
                    self.check()

    def test_qc_cannot_claim_redacted_values_are_retained(self):
        self.tables["metadata.jsonl"][0]["qc"]["all_values_retained"] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_unrecorded_collector_status_cannot_be_promoted_to_observed(self):
        cell = self.tables["features.jsonl"][0]["fields"]["web_data.hardware_concurrency"]
        cell.update(status_origin="not_recorded", collection_status="observed")
        with self.assertRaises(ValueError):
            self.check()

    def test_numeric_zero_and_boolean_false_survive_statistics(self):
        before = copy.deepcopy(self.tables)
        cells = [cell for row in self.tables["features.jsonl"] for cell in row["fields"].values()]
        self.assertTrue(any(type(cell["value"]) is bool and cell["value"] is False for cell in cells))
        self.assertTrue(any(type(cell["value"]) in (int, float) and cell["value"] == 0 for cell in cells))
        self.runtime.compute_statistics(self.tables)
        self.check()
        self.assertEqual(self.tables, before)

    def test_missing_duplicate_or_dangling_endpoint_relationship_rejected(self):
        for corruption in ("missing", "duplicate", "dangling"):
            with self.subTest(corruption=corruption):
                self.tables = copy.deepcopy(self.fixture)
                pair = next(row for row in self.tables["pairs.jsonl"] if row["kind"] == "linked_app_browser")
                if corruption == "missing":
                    self.tables["pairs.jsonl"].remove(pair)
                elif corruption == "duplicate":
                    self.tables["pairs.jsonl"].append(copy.deepcopy(pair))
                else:
                    pair["members"][0]["sample_id"] = "sample_" + "f" * 32
                with self.assertRaises(ValueError):
                    self.check()

    def test_triplet_phase_or_group_corruption_rejected(self):
        for corruption in ("phase", "group"):
            with self.subTest(corruption=corruption):
                self.tables = copy.deepcopy(self.fixture)
                _, metadata, annotation = self.source_rows("controlled_main")
                if corruption == "phase":
                    annotation["phase"] = "incorrect_phase"
                else:
                    metadata["group_id"] = "group_" + "f" * 32
                with self.assertRaises(ValueError):
                    self.check()


class ReviewerParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = importlib.import_module("reviewer_runtime")

    def test_ambiguous_json_and_nonfinite_numbers_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for filename in self.runtime.DATA_FILES:
                (root / filename).write_text('{}\n')
            for content in ('{"a":1,"a":2}\n', '{"a":NaN}\n', '\n', '[]\n'):
                with self.subTest(content=content):
                    (root / "features.jsonl").write_text(content)
                    with self.assertRaises(ValueError):
                        self.runtime.load_tables(root)

    def test_portable_privacy_scan_detects_identifiers_and_links_without_echoing(self):
        fixtures = {"email": "fixture@example.invalid", "home_path": "/Users/synthetic/private",
                    "ipv4": "192.0.2.17", "credential": "Bearer abcdefghijklmnopqrstuvwxyz",
                    "external_link": "https://example.invalid/project", "exact_timestamp": "2026-10-25T00:00:00Z"}
        for category, value in fixtures.items():
            with self.subTest(category=category):
                findings = self.runtime.privacy_findings({"note": value})
                self.assertGreater(findings.get(category, 0), 0)
                self.assertNotIn(value, json.dumps(findings))
        self.assertIn("source_identity_key", self.runtime.privacy_findings({"session_id": "fixture"}))
        self.assertEqual(self.runtime.privacy_findings({"measurement": 13800000000, "language": "en-US"}), {})


class ReviewerLicenseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = importlib.import_module("reviewer_runtime")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reviewer-license-")
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name)
        for name in self.runtime.PACKAGE_FILES:
            (self.package / name).write_text('{}\n')
        self.notice = ("Creative Commons Attribution 4.0 International\n"
                       "CC-BY-4.0\nhttps://creativecommons.org/licenses/by/4.0/\n")
        (self.package / "LICENSE_DATA.md").write_text(self.notice)
        (self.package / "schema.json").write_text(json.dumps({
            "$defs": {"reviewer_manifest_licensing": self.runtime.manifest_license_schema()}}))
        self.manifest = {
            "release_records": 1509,
            "publication_status": "AUTHORIZED_FOR_PUBLIC_RELEASE",
            "dataset_version": "1.0", "data_license": "CC-BY-4.0",
            "data_license_url": "https://creativecommons.org/licenses/by/4.0/",
            "data_license_file": "LICENSE_DATA.md",
            "data_license_scope": sorted(self.runtime.DATA_LICENSE_FILES),
            "software_license": "NOT_SPECIFIED",
            "software_license_scope": ["load_example.py", "validate.py"],
        }
        self.save_manifest()

    def save_manifest(self):
        self.manifest["file_inventory"] = [
            {"path": name, "bytes": (self.package / name).stat().st_size}
            for name in sorted(self.runtime.PACKAGE_FILES - {"manifest.json"})]
        (self.package / "manifest.json").write_text(json.dumps(self.manifest))

    def test_data_license_scope_excludes_software_and_license_notice(self):
        self.assertEqual(self.runtime.DATA_LICENSE, "CC-BY-4.0")
        self.assertEqual(self.runtime.DATA_LICENSE_URL, "https://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(self.runtime.SOFTWARE_LICENSE, "NOT_SPECIFIED")
        self.assertEqual(len(self.runtime.PACKAGE_FILES), 18)
        self.assertIn("LICENSE_DATA.md", self.runtime.PACKAGE_FILES)
        self.assertNotIn("LICENSE_OPTIONS.md", self.runtime.PACKAGE_FILES)
        self.assertEqual(set(self.runtime.DATA_LICENSE_FILES), set(self.runtime.PACKAGE_FILES)
                         - {"validate.py", "load_example.py", "LICENSE_DATA.md"})
        self.assertEqual(len(self.runtime.DATA_LICENSE_FILES), 15)

    def test_valid_license_contract_reaches_data_validation(self):
        # A valid license contract must pass before the deliberately synthetic
        # data fixture is read. No full release data are required by this test.
        with mock.patch.object(self.runtime, "load_tables", side_effect=RuntimeError("data validation reached")):
            with self.assertRaisesRegex(RuntimeError, "data validation reached"):
                self.runtime.validate(self.package)

    def test_pending_wrong_url_and_misassigned_license_scopes_are_rejected(self):
        mutations = (
            ("data_license", "PENDING_SELECTION"),
            ("data_license", "PENDING_APPROVAL"),
            ("data_license_url", "https://creativecommons.org/publicdomain/zero/1.0/"),
            ("data_license_file", "LICENSE_OPTIONS.md"),
            ("data_license_scope", sorted(self.runtime.DATA_LICENSE_FILES - {"statistics.json"})),
            ("data_license_scope", sorted(self.runtime.DATA_LICENSE_FILES | {"validate.py"})),
            ("data_license_scope", sorted(self.runtime.DATA_LICENSE_FILES | {"LICENSE_DATA.md"})),
            ("software_license", "CC-BY-4.0"),
            ("software_license", "MIT"),
            ("software_license_scope", ["validate.py"]),
            ("software_license_scope", ["features.jsonl", "load_example.py", "validate.py"]),
        )
        original = copy.deepcopy(self.manifest)
        for key, value in mutations:
            with self.subTest(field=key, changed_value=value):
                self.manifest = copy.deepcopy(original)
                self.manifest[key] = value
                self.save_manifest()
                with mock.patch.object(self.runtime, "load_tables") as load:
                    with self.assertRaisesRegex(ValueError, "license"):
                        self.runtime.validate(self.package)
                    load.assert_not_called()

    def test_missing_new_license_file_and_extra_old_options_file_are_rejected(self):
        notice = self.package / "LICENSE_DATA.md"
        notice.unlink()
        with self.assertRaisesRegex(ValueError, "package file"):
            self.runtime.validate(self.package)
        notice.write_text(self.notice)
        (self.package / "LICENSE_OPTIONS.md").write_text("Legacy license options\n")
        with self.assertRaisesRegex(ValueError, "package file"):
            self.runtime.validate(self.package)

    def test_notice_must_have_official_license_and_no_pending_data_license(self):
        invalid_notices = (
            self.notice.replace("CC-BY-4.0", "CC0-1.0"),
            self.notice.replace("https://creativecommons.org/licenses/by/4.0/", "unavailable"),
            self.notice + "Dataset license remains PENDING_SELECTION.\n",
            self.notice + "The data license remains pending.\n",
        )
        for notice in invalid_notices:
            with self.subTest(notice=notice):
                (self.package / "LICENSE_DATA.md").write_text(notice)
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, "license"):
                    self.runtime.validate(self.package)

    def test_manifest_license_schema_cannot_be_missing_or_weakened(self):
        for weakened in (None, {"type": "object"}):
            with self.subTest(schema=weakened):
                definitions = {} if weakened is None else {"reviewer_manifest_licensing": weakened}
                (self.package / "schema.json").write_text(json.dumps({"$defs": definitions}))
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, "license schema"):
                    self.runtime.validate(self.package)


class ReviewerLicensePreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = importlib.import_module("build_reviewer_release")
        cls.runtime = importlib.import_module("reviewer_runtime")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reviewer-license-digests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.filenames = (*self.runtime.DATA_FILES, "statistics.json")
        self.before = self.base / "before.zip"
        self.after = self.base / "after.zip"

    def make_archive(self, path, changed=None, missing=None, duplicate=None, note="before license update"):
        with zipfile.ZipFile(path, "w") as archive:
            for name in self.filenames:
                if name != missing:
                    text = "changed fixture\n" if name == changed else "unchanged fixture\n"
                    archive.writestr(self.builder.PREFIX + name, text)
            archive.writestr(self.builder.PREFIX + "README.md", note)
            if duplicate:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(self.builder.PREFIX + duplicate, "unchanged fixture\n")

    def test_documentation_only_change_preserves_all_five_data_digests(self):
        self.make_archive(self.before)
        self.make_archive(self.after, note="selected CC BY 4.0")
        report = self.builder.verify_data_unchanged(self.before, self.after)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(set(report["files"]), set(self.filenames))
        for entry in report["files"].values():
            self.assertTrue(entry["unchanged"])
            self.assertEqual(entry["before_sha256"], entry["after_sha256"])
        self.assertEqual(self.builder.data_file_digests(self.before), self.builder.data_file_digests(self.after))

    def test_change_to_any_one_of_the_five_data_files_is_rejected(self):
        self.make_archive(self.before)
        for name in self.filenames:
            with self.subTest(filename=name):
                self.make_archive(self.after, changed=name)
                with self.assertRaises(ValueError):
                    self.builder.verify_data_unchanged(self.before, self.after)

    def test_missing_data_member_is_rejected(self):
        self.make_archive(self.before)
        self.make_archive(self.after, missing="statistics.json")
        with self.assertRaises(ValueError):
            self.builder.verify_data_unchanged(self.before, self.after)
        with self.assertRaises(ValueError):
            self.builder.verify_data_unchanged(self.after, self.before)

    def test_duplicate_data_member_is_rejected(self):
        self.make_archive(self.before)
        self.make_archive(self.after, duplicate="features.jsonl")
        with self.assertRaises(ValueError):
            self.builder.verify_data_unchanged(self.before, self.after)
        with self.assertRaises(ValueError):
            self.builder.verify_data_unchanged(self.after, self.before)


class ReviewerPreservationBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = importlib.import_module("release")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reviewer-baseline-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = self.root / ".private"
        self.candidate = self.private / "candidate"
        self.candidate.mkdir(parents=True)
        self.baseline = self.private / "pre_reviewer_baseline"
        for filename in self.release.DATA_FILES:
            (self.candidate / filename).write_text('{"fixture":"existing randomized export"}\n')
        (self.private / "identity_map.json").write_text('{"sample":{"fixture":"sample_ffffffffffffffffffffffffffffffff"}}\n')
        (self.private / "source_lock.json").write_text('{"inputs":[]}\n')
        patcher = mock.patch.object(self.release, "PRIVATE", self.private)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_baseline_copies_existing_ids_and_lock_once_with_private_permissions(self):
        self.release.ensure_preservation_baseline()
        self.assertEqual({path.name for path in self.baseline.iterdir()},
                         set(self.release.DATA_FILES) | {"identity_map.json", "source_lock.json"})
        self.assertEqual(self.baseline.stat().st_mode & 0o777, 0o700)
        before = {}
        for path in self.baseline.iterdir():
            source = (self.candidate if path.name in self.release.DATA_FILES else self.private) / path.name
            self.assertEqual(path.read_bytes(), source.read_bytes())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            before[path.name] = path.read_bytes()
        self.release.ensure_preservation_baseline()
        self.assertEqual({path.name: path.read_bytes() for path in self.baseline.iterdir()}, before)

    def test_initial_missing_input_is_rejected_without_creating_partial_baseline(self):
        for filename in (*self.release.DATA_FILES, "identity_map.json", "source_lock.json"):
            path = (self.candidate if filename in self.release.DATA_FILES else self.private) / filename
            content = path.read_bytes()
            try:
                path.unlink()
                with self.subTest(filename=filename), self.assertRaises(ValueError):
                    self.release.ensure_preservation_baseline()
                self.assertFalse(self.baseline.exists())
            finally:
                path.write_bytes(content)

    def test_missing_or_changed_existing_identity_map_and_lock_are_rejected(self):
        self.release.ensure_preservation_baseline()
        snapshot = {path.name: path.read_bytes() for path in self.baseline.iterdir()}
        for filename in ("identity_map.json", "source_lock.json"):
            path = self.private / filename
            content = path.read_bytes()
            try:
                path.unlink()
                with self.subTest(filename=filename, corruption="missing"), self.assertRaises(ValueError):
                    self.release.ensure_preservation_baseline()
                path.write_bytes(content + b" ")
                with self.subTest(filename=filename, corruption="changed"), self.assertRaises(ValueError):
                    self.release.ensure_preservation_baseline()
            finally:
                path.write_bytes(content)
            self.assertEqual({path.name: path.read_bytes() for path in self.baseline.iterdir()}, snapshot)

    def test_build_preservation_guard_runs_before_source_or_output_mutation(self):
        with mock.patch.object(self.release, "ensure_preservation_baseline", side_effect=ValueError("preservation guard")) as guard, \
                mock.patch.object(self.release, "check_lock") as source_check, \
                mock.patch.object(self.release, "extract") as extraction:
            with self.assertRaisesRegex(ValueError, "preservation guard"):
                self.release.build(self.root)
            guard.assert_called_once()
            extraction.assert_not_called()
            source_check.assert_not_called()


class ReviewerPackageBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = importlib.import_module("build_reviewer_release")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reviewer-boundary-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.package = self.base / "package"
        self.package.mkdir()
        for name in self.builder.PACKAGE_FILES:
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}\n', encoding="utf-8")
        self.archive = self.base / "reviewer.zip"

    def test_exact_file_allowlist_rejects_missing_and_extra_private_files(self):
        for name in ("identity_map.json", ".git/config", "internal.log", "__MACOSX/._README.md"):
            with self.subTest(name=name):
                path = self.package / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic private fixture\n")
                with self.assertRaises(ValueError):
                    self.builder.audit_anonymity(self.package)
                path.unlink()
                if path.parent != self.package:
                    path.parent.rmdir()
        missing = self.package / "README.md"
        missing.unlink()
        with self.assertRaises(ValueError):
            self.builder.audit_anonymity(self.package)

    def test_source_paths_digests_and_author_denylist_are_rejected(self):
        document = self.package / "README.md"
        cases = [
            ("deliverables/synthetic-source/raw.jsonl", "forbidden_terms"),
            ("FixtureResearcher", "forbidden_terms"),
            ("synthetic_author_account", "forbidden_terms"),
            ("a" * 64, "forbidden_digests"),
        ]
        for text, argument in cases:
            with self.subTest(argument=argument):
                document.write_text(text + "\n")
                with self.assertRaises(ValueError):
                    self.builder.audit_anonymity(self.package, **{argument: (text,)})

    def test_prose_and_script_literals_cannot_leak_email_or_credentials(self):
        cases = ("fixture@example.invalid", "Bearer abcdefghijklmnopqrstuvwxyz",
                 "-----BEGIN PRIVATE KEY-----")
        for filename in ("README.md", "load_example.py"):
            for text in cases:
                with self.subTest(filename=filename, value_type=text.split()[0]):
                    path = self.package / filename
                    path.write_text((repr(text) if filename.endswith(".py") else text) + "\n")
                    try:
                        with self.assertRaises(ValueError):
                            self.builder.audit_anonymity(self.package)
                    finally:
                        path.write_text('{}\n')

    def test_directory_symlink_is_not_followed_into_package(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "identity_map.json").write_text('{}\n')
        (self.package / "linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.builder.audit_anonymity(self.package)

    def test_allowed_filename_cannot_hide_a_symlink(self):
        target = self.base / "source.txt"
        target.write_text("synthetic source content\n")
        (self.package / "README.md").unlink()
        (self.package / "README.md").symlink_to(target)
        with self.assertRaises(ValueError):
            self.builder.audit_anonymity(self.package)

    def test_zip_metadata_and_bytes_are_deterministic(self):
        self.builder.write_zip(self.package, self.archive)
        second = self.base / "second.zip"
        self.builder.write_zip(self.package, second)
        self.assertEqual(self.archive.read_bytes(), second.read_bytes())
        self.builder.validate_archive(self.archive)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(len(archive.namelist()), len(self.builder.PACKAGE_FILES))
            self.assertEqual(archive.comment, b"")
            self.assertEqual(len({info.date_time for info in archive.infolist()}), 1)
            for info in archive.infolist():
                self.assertFalse(info.comment)
                self.assertFalse(info.extra)
                self.assertEqual(info.filename.split("/", 1)[0], "cross_view_consistency_v1")

    def changed_archive(self, name, change):
        self.builder.write_zip(self.package, self.archive)
        target = self.base / name
        with zipfile.ZipFile(self.archive) as original, zipfile.ZipFile(target, "w") as altered:
            for index, info in enumerate(original.infolist()):
                modified = copy.copy(info)
                if index == 0:
                    change(modified)
                altered.writestr(modified, original.read(info))
        return target

    def test_zip_traversal_absolute_paths_and_symlink_members_are_rejected(self):
        mutations = {
            "traversal.zip": lambda info: setattr(info, "filename", "cross_view_consistency_v1/../identity_map.json"),
            "absolute.zip": lambda info: setattr(info, "filename", "/absolute/README.md"),
            "backslash.zip": lambda info: setattr(info, "filename", "cross_view_consistency_v1\\README.md"),
            "symlink.zip": lambda info: setattr(info, "external_attr", (0o120777 << 16)),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                target = self.changed_archive(name, mutation)
                with self.assertRaises(ValueError):
                    self.builder.validate_archive(target)

    def test_zip_comments_and_extra_metadata_are_rejected(self):
        mutations = {
            "comment.zip": lambda info: setattr(info, "comment", b"synthetic author metadata"),
            "extra.zip": lambda info: setattr(info, "extra", b"\xfe\xca\x00\x00"),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                target = self.changed_archive(name, mutation)
                with self.assertRaises(ValueError):
                    self.builder.validate_archive(target)
        self.builder.write_zip(self.package, self.archive)
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.comment = b"synthetic author metadata"
        with self.assertRaises(ValueError):
            self.builder.validate_archive(self.archive)

    def test_zip_extra_members_are_rejected(self):
        self.builder.write_zip(self.package, self.archive)
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("cross_view_consistency_v1/identity_map.json", '{}\n')
        with self.assertRaises(ValueError):
            self.builder.validate_archive(self.archive)


@unittest.skipUnless(ARCHIVE.is_file(), "Build the reviewer archive to run the independent integration checks")
class ReviewerArchiveIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = importlib.import_module("build_reviewer_release")
        cls.runtime = importlib.import_module("reviewer_runtime")
        cls.builder.validate_archive(ARCHIVE)
        cls.temporary = tempfile.TemporaryDirectory(prefix="reviewer-independent-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        with zipfile.ZipFile(ARCHIVE) as archive:
            archive.extractall(cls.base)
        cls.package = cls.base / "cross_view_consistency_v1"

    def test_full_projection_preserves_candidate_ids_values_labels_and_relations(self):
        if not CANDIDATE.is_dir():
            self.skipTest("Private input is unavailable for preservation comparison")
        for filename in ("features.jsonl", "annotations.jsonl", "pairs.jsonl"):
            self.assertEqual((self.package / filename).read_bytes(), (CANDIDATE / filename).read_bytes())
        before = [json.loads(line) for line in (CANDIDATE / "metadata.jsonl").read_text().splitlines()]
        after = [json.loads(line) for line in (self.package / "metadata.jsonl").read_text().splitlines()]
        self.assertEqual(len(after), 1509)
        for row in before:
            row["public_release_status"] = "AUTHORIZED_FOR_PUBLIC_RELEASE"
        self.assertEqual(after, before)

    def test_selected_data_license_and_anonymous_attribution_notice(self):
        manifest = json.loads((self.package / "manifest.json").read_text())
        self.assertEqual(manifest["data_license"], "CC-BY-4.0")
        self.assertEqual(manifest["data_license_url"], "https://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(manifest["data_license_file"], "LICENSE_DATA.md")
        self.assertEqual(manifest["data_license_scope"], sorted(self.runtime.DATA_LICENSE_FILES))
        self.assertEqual(manifest["software_license"], "NOT_SPECIFIED")
        self.assertEqual(manifest["software_license_scope"], ["load_example.py", "validate.py"])
        notice = (self.package / "LICENSE_DATA.md").read_text()
        self.assertIn("Creative Commons Attribution 4.0 International", notice)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", notice)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/legalcode.en", notice)
        self.assertIn("Attribution during anonymous review", notice)
        self.assertIn("no personal author identity", notice)
        self.assertIn("NOT_SPECIFIED", notice)
        self.assertNotIn("PENDING_SELECTION", notice)
        self.assertFalse((self.package / "LICENSE_OPTIONS.md").exists())

    @unittest.skipUnless(LICENSE_BASELINE_ARCHIVE.is_file(), "Local pre-license archive is unavailable")
    def test_license_change_preserves_sha256_of_all_five_data_files(self):
        filenames = (*self.runtime.DATA_FILES, "statistics.json")
        with zipfile.ZipFile(LICENSE_BASELINE_ARCHIVE) as before:
            old_manifest = json.loads(before.read(self.builder.PREFIX + "manifest.json"))
            self.assertEqual(old_manifest["data_license"], "PENDING_SELECTION")
            for name in filenames:
                with self.subTest(filename=name):
                    old_digest = hashlib.sha256(before.read(self.builder.PREFIX + name)).hexdigest()
                    new_digest = hashlib.sha256((self.package / name).read_bytes()).hexdigest()
                    self.assertEqual(new_digest, old_digest)
            old_schema = json.loads(before.read(self.builder.PREFIX + "schema.json"))
            new_schema = json.loads((self.package / "schema.json").read_text())
            self.assertEqual(new_schema["oneOf"], old_schema["oneOf"])
            for definition in ("features", "metadata", "annotations", "pairs"):
                self.assertEqual(new_schema["$defs"][definition], old_schema["$defs"][definition])

    def test_isolated_loader_validator_and_statistics_work_without_repository(self):
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        self.assertFalse((self.package / ".git").exists())
        self.assertFalse((self.package / ".private").exists())
        validation = subprocess.run(
            [sys.executable, "-I", "-B", str(self.package / "validate.py"), "--root", ".",
             "--recompute-statistics", str(self.base / "recomputed_statistics.json")],
            cwd=self.package, env=env, capture_output=True, text=True, check=True)
        report = json.loads(validation.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["observations"], 1509)
        self.assertEqual(json.loads((self.base / "recomputed_statistics.json").read_text()),
                         json.loads((self.package / "statistics.json").read_text()))
        loaded = subprocess.run(
            [sys.executable, "-I", "-B", str(self.package / "load_example.py"), "--data", "."],
            cwd=self.package, env=env, capture_output=True, text=True, check=True)
        result = json.loads(loaded.stdout)
        self.assertEqual(result["observations"], 1509)
        self.assertEqual(result["views"], {"App177": 558, "Paired244": 951})
        self.assertEqual(result["labels"], {"modified": 170, "normal_control": 442, "no_effect": 6, "unlabeled": 891})

    def test_standalone_validator_rejects_unexpected_private_file(self):
        injected = self.package / "identity_map.json"
        try:
            injected.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, "Unexpected or missing package file"):
                self.runtime.validate(self.package)
        finally:
            injected.unlink(missing_ok=True)

    def test_standalone_validator_rejects_same_size_statistics_corruption(self):
        path = self.package / "statistics.json"
        original = path.read_text()
        altered = original.replace('"total_unique_observations": 1509', '"total_unique_observations": 1508', 1)
        self.assertNotEqual(altered, original)
        self.assertEqual(len(altered), len(original))
        try:
            path.write_text(altered)
            with self.assertRaisesRegex(ValueError, "statistics.*recomputation"):
                self.runtime.validate(self.package)
        finally:
            path.write_text(original)


if __name__ == "__main__":
    unittest.main()
