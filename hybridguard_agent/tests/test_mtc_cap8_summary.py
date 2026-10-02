"""Replay accounting boundaries; no fitting or captured predictions."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / "deliverables/mtc_cap8_replay_v1/run_replay.py"
SPEC = importlib.util.spec_from_file_location("mtc_replay_runner", PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def row(sid, decision, triggers=(), model="m1", supported=True, load_error=None):
    return {"sample_id": sid, "decision": decision, "model_id": model, "fold_id": "fold-01",
            "subset": runner.SUBSETS[0], "profile": {"manufacturer": "test", "model": sid, "android_release": "12"},
            "normal_basis": {"supported": supported}, "load_error": load_error,
            "rules": [{"atom_id": aid, "state": "T" if aid in triggers else "U", "triggered": aid in triggers,
                       "reason": "test", "fields": []} for aid in ("a", "b")]}


class ReplaySummaryTests(unittest.TestCase):
    def test_unknown_and_failure_remain_in_denominator(self):
        rows = [row("1", "MANIPULATION_ALERT", ("a",)), row("2", "NO_ALERT"),
                row("3", "INSUFFICIENT_EVIDENCE"), row("4", "FAILED", load_error="missing"),
                row("5", "MANIPULATION_ALERT", ("b",), supported=False)]
        s = runner.counts(rows)
        self.assertEqual((s["planned_records"], s["processed_records"], s["alerts"], s["no_alert"], s["unknown"], s["failed"]), (5, 4, 2, 1, 1, 1))
        self.assertEqual(s["defined_coverage"], runner.ratio(3, 5))
        self.assertEqual(s["normal_observed_alert_proportion"], runner.ratio(1, 4))

    def test_unique_overlap_and_models_do_not_multiply_samples(self):
        rows = [row("1", "MANIPULATION_ALERT", ("a",)), row("2", "MANIPULATION_ALERT", ("a", "b"))]
        rows += [dict(r, model_id="m2") for r in rows]
        rows += [row("1", "INSUFFICIENT_EVIDENCE", model="m3"), row("2", "MANIPULATION_ALERT", ("a", "b"), model="m3")]
        s = runner.summarize_rows(rows)
        rules = s["models"]["m1"]["subsets"][runner.SUBSETS[0]]["rules"]
        self.assertEqual((rules["a"]["unique_alerts"], rules["b"]["unique_alerts"]), (1, 0))
        a = s["agreement"][runner.SUBSETS[0]]
        self.assertEqual((a["distinct_records"], a["same_decision_records"], a["different_decision_ids"]), (2, 1, ["1"]))


if __name__ == "__main__":
    unittest.main()
