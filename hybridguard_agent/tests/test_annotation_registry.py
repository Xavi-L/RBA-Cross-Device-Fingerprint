import unittest
from collections import Counter
from pathlib import Path

from hybridguard_agent.scripts import build_dataset_snapshot as snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = (
    REPO_ROOT
    / "hybridguard-browser-fingerprint-research"
    / "execution_log"
    / "evidence"
    / "experiment_session_annotation_registry_v1.csv"
)
EVIDENCE_ROOT = REPO_ROOT / "hybridguard-browser-fingerprint-research"


class AnnotationRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = snapshot.load_annotation_registry(REGISTRY_PATH, EVIDENCE_ROOT)

    def test_registry_has_complete_dual_key_indexes(self) -> None:
        self.assertIsNotNone(self.registry)
        assert self.registry is not None
        self.assertEqual(len(self.registry["rows"]), 51)
        self.assertEqual(len(self.registry["by_sample_id"]), 51)
        self.assertEqual(len(self.registry["by_session_id"]), 51)
        for row in self.registry["rows"]:
            self.assertIs(self.registry["by_sample_id"][row["sample_id"]], row)
            self.assertIs(self.registry["by_session_id"][row["source_session_id"]], row)

    def test_registry_rows_are_split_into_non_interchangeable_tasks(self) -> None:
        assert self.registry is not None
        counts = Counter(
            task
            for row in self.registry["rows"]
            for task in snapshot.annotation_task_memberships(row)
        )
        self.assertEqual(counts["fingerprint_field_effect_pilot"], 9)
        self.assertEqual(counts["transport_path_effect_pilot"], 9)
        self.assertEqual(counts["baseline_qc"], 24)
        self.assertEqual(counts["incomplete_attempt_failure_analysis"], 9)

    def test_complete_attack_pairs_have_no_held_out_split(self) -> None:
        assert self.registry is not None
        complete = [
            row
            for row in self.registry["rows"]
            if row["include_in_complete_pair_evaluation"] == "true"
        ]
        self.assertEqual(len(complete), 18)
        self.assertEqual({row["split"] for row in complete}, {"train"})


if __name__ == "__main__":
    unittest.main()
