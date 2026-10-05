"""Publication boundaries and credential checks; no devices or collectors."""

from pathlib import Path
import shutil
import tempfile
import unittest

import review_evidence as review
import intake


class PublicationTests(unittest.TestCase):
    def test_git_identity_files_are_ordinary_files_until_temporary_restore(self):
        self.assertEqual(review.stored_name("upstream/.git/refs/heads/main"), "upstream_git_metadata/refs/heads/main")
        self.assertEqual(review.stored_name("data/raw_expanded_payloads.jsonl"), "data/raw_expanded_payloads.jsonl")
        with self.assertRaises(ValueError):
            review.stored_name("unexpected/.git/HEAD")

    def test_traversal_is_not_a_public_member(self):
        for name in ("../private.key", "/tmp/private.key", "upstream/.git/../../escape"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                review.stored_name(name)

    def test_real_key_formats_block_but_source_markers_do_not(self):
        self.assertTrue(review.credential_findings("fixture", b"AIza" + b"x" * 35))
        self.assertFalse(review.credential_findings("source.py", b'"-----BEGIN OPENSSH PRIVATE KEY-----"'))
        data = b"-----BEGIN OPENSSH PRIVATE KEY-----\n" + b"A" * 64 + b"\n-----END OPENSSH PRIVATE KEY-----\n"
        self.assertTrue(review.credential_findings("fixture", data))

    def test_duplicate_manifest_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "publication.json"
            intake.write(manifest, {"archive_file_count": 488, "archive_files": [{"stored_path": "same"}] * 488})
            with self.assertRaisesRegex(ValueError, "DUPLICATE_PUBLIC_ARCHIVE_PATH"):
                review.materialize(root / "out", root, manifest)

    @unittest.skipUnless(review.MANIFEST.exists(), "published evidence not installed")
    def test_all_published_members_match_original_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "inputs"
            publication = review.materialize(root)
            self.assertEqual(publication["archive_file_count"], 488)
            self.assertEqual(intake.check_inventory(root)["listed_members_verified"], 487)
            self.assertTrue((root / "upstream/.git/HEAD").is_file())
            self.assertFalse((review.ARCHIVE / "upstream/.git").exists())

    @unittest.skipUnless(review.MANIFEST.exists(), "published evidence not installed")
    def test_changed_public_raw_is_rejected_before_verifier_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive"
            shutil.copytree(review.ARCHIVE, archive)
            with (archive / "data/raw_browser_payloads.jsonl").open("ab") as handle:
                handle.write(b"\n")
            with self.assertRaisesRegex(ValueError, "PUBLIC_ARCHIVE_BYTES_MISMATCH"):
                review.materialize(root / "inputs", archive)
            self.assertFalse((root / "inputs").exists())


if __name__ == "__main__":
    unittest.main()
