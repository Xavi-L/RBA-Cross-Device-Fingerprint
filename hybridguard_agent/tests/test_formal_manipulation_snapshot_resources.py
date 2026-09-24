"""S05-R finite packaging boundaries; no real data or detector execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from hybridguard_agent.research.manipulation_eval import freeze as f
from hybridguard_agent.research.manipulation_eval import freeze_revision as revision
from hybridguard_agent.research.manipulation_eval import runtime_resources as r


class SnapshotResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="s05r-resource-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "snapshot"
        for rel in r.resource_paths():
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f.ROOT / rel, dest)
        self.ledger = r.resource_manifest(self.root, freeze_revision=revision.REVISION)
        self.write_ledger()

    def write_ledger(self):
        (self.root / r.MANIFEST).write_text(json.dumps(self.ledger))

    def test_explicit_resources_preserve_old_set_and_add_exact_three(self):
        old = f.read(f.ROOT / f.ARTIFACT / "05_freeze/FREEZE_MANIFEST.json")
        inherited = {str(Path(e["path"]).relative_to("frozen_sources")) for e in old["bound_files"] if e["category"] == "RUNTIME_CONFIG"}
        current = [str(p) for p in r.resource_paths()]
        self.assertEqual(set(current), inherited | set(r.SOURCE_FILES))
        self.assertEqual(len(current), len(set(current)))
        self.assertEqual(r.preflight(root=self.root, require_manifest=True)["resource_count"], len(current))

    def test_each_required_source_missing_fails_even_if_unregistered(self):
        for missing in r.SOURCE_FILES:
            with self.subTest(missing=missing):
                path = self.root / missing
                data = path.read_bytes()
                path.unlink()
                self.ledger["resources"] = [row for row in self.ledger["resources"] if row["path"] != missing]
                self.ledger["resource_count"] = len(self.ledger["resources"])
                self.write_ledger()
                with self.assertRaises(r.ResourcePreflightError) as caught:
                    r.preflight(root=self.root, require_manifest=True)
                self.assertEqual(caught.exception.code, "MISSING_RUNTIME_RESOURCE")
                self.assertEqual(caught.exception.paths, [missing])
                path.write_bytes(data)

    def test_manifest_cannot_omit_present_required_file_or_duplicate_it(self):
        for rows in (self.ledger["resources"][1:], self.ledger["resources"] + [deepcopy(self.ledger["resources"][0])]):
            self.ledger["resources"], self.ledger["resource_count"] = rows, len(rows)
            self.write_ledger()
            with self.assertRaisesRegex(r.ResourcePreflightError, "RUNTIME_RESOURCE_MANIFEST_SET_MISMATCH"):
                r.preflight(root=self.root, require_manifest=True)

    def test_digest_binds_actual_resource_bytes(self):
        (self.root / r.SOURCE_FILES[0]).write_text("{}\n")
        with self.assertRaisesRegex(r.ResourcePreflightError, "RUNTIME_RESOURCE_DIGEST_MISMATCH"):
            r.preflight(root=self.root, require_manifest=True)

    def test_formal_preflight_requires_manifest_and_copied_config_binding(self):
        with self.assertRaisesRegex(r.ResourcePreflightError, "RUNTIME_CONFIG_OUTSIDE_FROZEN_BINDING"):
            r.preflight(root=self.root, require_manifest=True, config_dir=f.ROOT / r.ROLE)
        with self.assertRaisesRegex(r.ResourcePreflightError, "RUNTIME_CONFIG_OUTSIDE_FROZEN_BINDING"):
            r.preflight(root=self.root, require_manifest=True, policy_path=f.ROOT / r.POLICY / "decision_policy.json")
        (self.root / r.MANIFEST).unlink()
        with self.assertRaisesRegex(r.ResourcePreflightError, "MISSING_RUNTIME_RESOURCE_MANIFEST"):
            r.preflight(root=self.root, require_manifest=True)

    def test_resource_symlink_cannot_fall_back_to_main_workspace(self):
        path = self.root / r.SOURCE_FILES[0]
        path.unlink()
        path.symlink_to(f.ROOT / r.SOURCE_FILES[0])
        with self.assertRaisesRegex(r.ResourcePreflightError, "RUNTIME_RESOURCE_OUTSIDE_SNAPSHOT"):
            r.preflight(root=self.root, require_manifest=True)

    def test_both_destinations_explicit_and_parent_cannot_be_extended(self):
        out = Path(self.temp.name) / "new-freeze"
        with self.assertRaisesRegex(ValueError, "Both"):
            f.destinations(f.ROOT, out, None)
        with self.assertRaisesRegex(ValueError, "Protected"):
            f.destinations(f.ROOT, f.ROOT / f.ARTIFACT / "05_freeze/patch", Path(self.temp.name) / "config")
        with self.assertRaisesRegex(ValueError, "Protected"):
            f.destinations(f.ROOT, out, f.ROOT / "hybridguard_agent/config/formal_manipulation_protocol_v2/patch")
        self.assertFalse(out.exists())

    def test_semantic_protocol_change_rejected_before_file_comparison(self):
        parent = f.ROOT / f.ARTIFACT / "05_freeze"
        protocol = f.read(parent / "protocol.json")
        protocol["candidate_rules"] += 1
        with self.assertRaisesRegex(ValueError, "Experimental protocol semantics changed"):
            revision.invariance(parent, self.root, protocol)

    def test_original_worker_and_job_schema_preserved(self):
        rel = "hybridguard_agent/research/manipulation_eval/runner.py"
        parent = f.ROOT / f.ARTIFACT / "05_freeze/frozen_sources" / rel
        for function in ("worker", "validate_protocol"):
            self.assertEqual(revision.function_ast(parent, function), revision.function_ast(f.ROOT / rel, function))


if __name__ == "__main__":
    unittest.main()
