"""Local integration checks for the archived linked-Browser export.

The private archive is deliberately absent from a public documentation bundle.
These checks skip when its source data are unavailable; they never collect,
score, train, or recreate an intervention.
"""
import collections
import sys
import unittest
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1]
REPO = RELEASE.parents[1]
sys.path.insert(0, str(RELEASE / "scripts"))
import adapter_browser


@unittest.skipUnless((REPO / adapter_browser.PILOT / "evidence_archive/data/raw_expanded_payloads.jsonl").exists(),
                     "Private source archive is not distributed")
class BrowserReleaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = adapter_browser.extract(REPO)
        cls.records = cls.export["records"]

    def test_raw_observation_units_and_complete_grouping(self):
        self.assertEqual(len(self.records), 60)
        self.assertEqual(len({r["record_key"] for r in self.records}), 60)
        grouped = collections.defaultdict(list)
        for record in self.records:
            grouped[record["triplet_key"]].append(record)
            self.assertEqual(len(adapter_browser._flatten(record["app"], "app")), 177)
            self.assertEqual(sum(len(layer) for layer in record["browser"].values()), 67)
        self.assertEqual(len(grouped), 20)
        self.assertTrue(all(len(group) == 3 for group in grouped.values()))
        self.assertEqual(len({r["group_key"] for r in self.records}), 2)

    def test_execution_effect_and_predictions_are_separate(self):
        annotations = [r["annotation"] for r in self.records]
        self.assertEqual(collections.Counter(a["label"] for a in annotations),
                         {"normal_control": 46, "modified": 14})
        self.assertEqual(collections.Counter(a["tool_execution_status"] for a in annotations),
                         {"NOT_APPLICABLE": 12, "RECORDED_SUCCESS": 6,
                          "RECORDED_CONTROL_INSTALLED": 8, "NOT_NEEDED": 22, "EXECUTED": 12})
        # Legitimate operations can execute and change fields while remaining
        # normal controls; an operation effect alone is not an attack label.
        legitimate_changes = [a for a in annotations if a["label"] == "normal_control"
                              and a["target_effect_status"] == "OBSERVED_CHANGE"]
        self.assertEqual(len(legitimate_changes), 6)
        for configuration in ("saved_configuration_1", "saved_configuration_2", "saved_configuration_3"):
            modified = [a for a in annotations if a["label"] == "modified"]
            self.assertEqual(sum(a["detector_outcome"][configuration]["app"] == "T" for a in modified), 2)
            self.assertEqual(sum(a["detector_outcome"][configuration]["app_plus_browser_C1"] == "T" for a in modified), 7)

    def test_original_statuses_and_private_provenance(self):
        self.assertEqual(sum(len(r["browser_status"]) for r in self.records), 4020)
        self.assertTrue(all(v == "observed" for r in self.records for v in r["browser_status"].values()))
        self.assertTrue(all(r["provenance"] for r in self.records))
        self.assertTrue(all(s["permission_status"] == "PENDING_CONFIRMATION" for s in self.export["sources"]))
        for record in self.records:
            self.assertNotIn("capture", record)
            self.assertNotIn("ticket", record)
            self.assertNotIn("source_meta", record["metadata"])


if __name__ == "__main__":
    unittest.main()
