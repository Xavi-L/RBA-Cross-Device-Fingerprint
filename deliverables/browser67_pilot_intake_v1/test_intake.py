"""Focused public path tests plus optional private, real-evidence integration tests."""

import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intake
import path_compat
from hybridguard_agent.scripts import build_latest_paired244_snapshot as snapshot
from hybridguard_agent.scripts import build_latest_experiment_plan as experiment


class PathCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.build = {"source_checkout": r"C:\research\resumed\upstream",
                      "resume_archive_origin": {"directory": r"C:\research\original"}}

    def test_two_registered_roots_map_relative_paths(self):
        for origin in (r"C:\research\resumed", r"C:\research\original"):
            self.assertEqual(path_compat.map_locked_path(self.root, self.build, origin + r"\upstream\probe.js"),
                             self.root / "upstream/probe.js")
        self.assertNotEqual(path_compat.map_locked_path(self.root, self.build, r"C:\research\original\a\same.json"),
                            path_compat.map_locked_path(self.root, self.build, r"C:\research\original\b\same.json"))

    def test_unknown_root_and_drive_rejected(self):
        for path in (r"D:\research\resumed\probe.js", r"C:\unknown\probe.js",
                     r"C:\research\resumed_suffix\probe.js"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "LOCKED_PATH_OUTSIDE_RUN"):
                path_compat.map_locked_path(self.root, self.build, path)

    def test_traversal_and_unsupported_paths_rejected(self):
        for path in (r"C:\research\resumed\..\probe.js", r"C:\research\resumed\a\..\probe.js",
                     r"C:research\resumed\probe.js", r"\\host\share\probe.js", r"\\?\C:\probe.js",
                     "/tmp/probe.js", "probe.js", r"C:\research\resumed\probe.js:stream",
                     r"C:\research\resumed\a.\probe.js", r"C:\research\resumed\*.js"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                path_compat.map_locked_path(self.root, self.build, path)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "LOCKED_PATH_ESCAPE"):
                path_compat.map_locked_path(self.root, self.build, r"C:\research\resumed\escape\probe.js")

    def test_zip_traversal_rejected(self):
        for path in ("../raw.jsonl", "/raw.jsonl", "C:/raw.jsonl", "a/../../raw.jsonl", "a\\raw.jsonl"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                intake.relative_path(path)

    def test_comparison_distinguishes_false_from_zero(self):
        self.assertNotEqual(intake.canonical({"value": False}), intake.canonical({"value": 0}))


EVIDENCE = intake.PRIVATE / "originals/evidence"


@unittest.skipUnless((EVIDENCE / "package_contents.json").exists(), "private evidence not installed; run local intake first")
class RealEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="browser67-intake-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.json"
        self.config = intake.generate_config(EVIDENCE, self.config_path)

    def mutable_sources(self):
        sources = {}
        for key in intake.DATA_SOURCES:
            sources[key] = intake.rows(Path(self.config["sources"][key]))
            self.config["sources"][key] = str(self.root / (key + ".jsonl"))
        return sources

    def build(self, sources=None, name="snapshot"):
        if sources is not None:
            for key, values in sources.items():
                intake.write_rows(self.config["sources"][key], values)
        intake.write(self.config_path, self.config)
        output = self.root / name
        snapshot.build_snapshot(self.config_path, output, name)
        return output

    def test_real_baseline_244_values_states_identity_and_empty_splits(self):
        output = self.build()
        result, members = intake.compare_snapshots(EVIDENCE / "delivery/paired244_snapshot", output)
        self.assertEqual((result["members"], result["values_equal"], result["states_equal"]), (18, 4392, 4392))
        self.assertEqual(len(members), 18)
        self.assertEqual(len(intake.stage_inventory(EVIDENCE, output)), 18)
        readiness = experiment.build_plan(output, self.root / "plan", facts_path=EVIDENCE / "delivery/latest_experiment_facts.jsonl")
        self.assertEqual(readiness, intake.read(EVIDENCE / "delivery/experiment_plan/experiment_readiness.json"))
        self.assertEqual(readiness["counts"]["split_sample_counts"], {"train": 0, "development": 0, "test": 0})
        self.assertFalse(readiness["structural_ready"])

    def test_v16_v2_release_files_do_not_accept_old_version_claims(self):
        for key, value in (("featureapp_version_code", 8), ("featureapp_version_name", "wrong"),
                           ("browser_probe_revision", "expanded-web-67-v1")):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.config)
                changed["release"][key] = value
                with self.assertRaises(ValueError):
                    snapshot.verify_release_files(changed)

    def test_raw_and_analysis_versions_cannot_impersonate_v16_v2(self):
        app = intake.rows(EVIDENCE / "data/raw_expanded_payloads.jsonl")[0]["canonical_received_payload"]
        browser = intake.rows(EVIDENCE / "data/raw_browser_payloads.jsonl")[0]["canonical_received_payload"]
        app_fields, browser_fields, app_types, browser_types = snapshot.load_catalog(
            Path(self.config["sources"]["feature_catalog"]), 177, 67)
        app["collection_manifest"]["collector_version_code"] = 8
        browser["web_probe_revision"] = "expanded-web-67-v1"
        self.assertTrue(snapshot.validate_app_payload(app, self.config["release"], app_fields, app_types)[0])
        self.assertTrue(snapshot.validate_browser_payload(browser, self.config["release"], browser_fields, browser_types)[0])

    def test_reordered_source_rows_still_pair_by_identity(self):
        sources = self.mutable_sources()
        for key, values in sources.items():
            # Pairing records may be reordered; lifecycle/event chronology is
            # itself evidence and must keep its original order.
            if key not in ("collection_batches", "browser_pair_events"):
                values.reverse()
        output = self.build(sources)
        # selection_audit intentionally keeps physical source line numbers;
        # those change on reordering, whereas pairing and observations must not.
        for name in ("paired_244.jsonl", "sample_index.jsonl"):
            expected = intake.index_unique(intake.rows(EVIDENCE / "delivery/paired244_snapshot" / name), "sample_id")
            actual = intake.index_unique(intake.rows(output / name), "sample_id")
            self.assertEqual(len(actual), 18)
            self.assertEqual(intake.canonical(expected), intake.canonical(actual))

    def test_bad_pairs_and_duplicate_sessions_keep_all_app_positions(self):
        original = self.mutable_sources()
        for mode in ("mismatched_receipt", "duplicate_pair", "duplicate_browser_session", "missing_browser_raw", "hash_mismatch", "duplicate_app_raw"):
            with self.subTest(mode=mode):
                sources = copy.deepcopy(original)
                pairs = sources["browser_pair_provenance"]
                if mode == "mismatched_receipt":
                    pairs[0]["app_receipt_id"] = pairs[1]["app_receipt_id"]
                elif mode == "duplicate_pair":
                    pairs.append(copy.deepcopy(pairs[0]))
                elif mode == "duplicate_browser_session":
                    pairs[0]["browser_session_id"] = pairs[1]["browser_session_id"]
                elif mode == "missing_browser_raw":
                    sources["browser_raw"].pop(0)
                elif mode == "hash_mismatch":
                    pairs[0]["browser_payload_sha256"] = "0" * 64
                else:
                    sources["app_raw"].append(copy.deepcopy(sources["app_raw"][0]))
                output = self.build(sources, mode)
                counts = intake.read(output / "qc_summary.json")["counts"]
                self.assertLess(counts["paired_244_count"], 18)
                self.assertEqual(counts["paired_244_count"] + counts["app_only_177_count"] + counts["quarantined_app_count"], 18)
                self.assertTrue(intake.rows(output / "quarantine.jsonl"))
                for value in intake.rows(output / "app_only_177.jsonl"):
                    self.assertEqual(value["feature_count"], 177)
                    self.assertFalse(any(key.startswith("browser.") for key in value["features"]))

    def test_unknown_value_and_status_not_filled_or_reclassified(self):
        sources = self.mutable_sources()
        raw = sources["browser_raw"][0]
        pair = next(p for p in sources["browser_pair_provenance"] if p["pair_id"] == raw["pair_id"])
        analysis = next(p for p in sources["browser_analysis"] if p["pair_id"] == raw["pair_id"])
        field = "web_data.navigator_layer.language"
        for payload in (raw["canonical_received_payload"], analysis):
            payload["web_data"]["navigator_layer"]["language"] = None
            status = payload["collection_status"]
            status["fields"][field] = "runtime_error"
            if "field_statuses" in payload:
                payload["field_statuses"][field] = "runtime_error"
            status["counts"]["observed"] -= 1
            status["counts"]["runtime_error"] += 1
        digest = snapshot.sha256_value(raw["canonical_received_payload"])
        for value in (raw, pair, analysis):
            value["browser_payload_sha256"] = digest
        output = self.build(sources)
        sample_id = next(v["sample_id"] for v in intake.rows(output / "sample_index.jsonl") if v["browser_pair_id"] == pair["pair_id"])
        value = next(v for v in intake.rows(output / "paired_244.jsonl") if v["sample_id"] == sample_id)
        self.assertIsNone(value["features"]["browser." + field])
        self.assertEqual(value["field_status"]["browser." + field], "runtime_error")

    def test_archived_real_evidence_self_tests_are_unchanged(self):
        result = path_compat.run_verifier(EVIDENCE, self.root / "self_tests.json", self_test=True)
        self.assertEqual(result, intake.read(EVIDENCE / "verification_tests.json"))
        self.assertEqual((result["passed"], len(result["rejected_mutations"])), (8, 7))

    def test_member_comparison_rejects_duplicate_or_changed_identity(self):
        original = EVIDENCE / "delivery/paired244_snapshot"
        copied = self.root / "copied_snapshot"
        shutil.copytree(original, copied)
        values = intake.rows(copied / "sample_index.jsonl")
        values[0]["browser_receipt_id"] = "incorrect-receipt"
        intake.write_rows(copied / "sample_index.jsonl", values)
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_MEMBER_CONTENT_MISMATCH"):
            intake.compare_snapshots(original, copied)
        values[0] = values[1]
        intake.write_rows(copied / "sample_index.jsonl", values)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SAMPLE_ID"):
            intake.compare_snapshots(original, copied)


if __name__ == "__main__":
    unittest.main()
