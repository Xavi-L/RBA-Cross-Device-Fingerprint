"""Saved-result accounting; these tests do not train or run a detector."""
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("relation_saved_reporting", ROOT / "deliverables/mtc_relation_extension_v1/summarize.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)
REL = "NEW_RELATION"


def records():
    rows = []
    for scheme in ("B", "B_REL"):
        for sid, dataset, subset, stage in (
            ("attack", "controlled", "heldout", "attack"),
            ("clean", "controlled", "heldout", "clean_pre"),
            ("d", "mtc", "discovery", None),
            ("v", "mtc", "development", None),
            ("r", "mtc", "reserved_validation", None)):
            row = {"scheme": scheme, "fold_id": "fold-01", "model_id": scheme + "-model",
                   "sample_id": sid, "dataset": dataset, "subset": subset,
                   "decision": "NO_ALERT", "rules": [], "profile": {"model": "normal-tablet", "android_release": "12"},
                   "normal_basis": {"supported": stage != "attack"}}
            if stage:
                row.update(stage=stage, configuration_id="screen")
            if scheme == "B_REL":
                row["relation_results"] = [{"atom_id": REL, "state": "F", "reason": "within",
                                            "fields": [{"field": "current", "value": 1}]}]
            rows.append(row)
    return rows


def settings():
    return {"folds": [{"fold_id": "fold-01", "outer_test_ids": ["attack", "clean"]}],
            "mtc_primary_ids": {"discovery": ["d"], "development": ["v"], "reserved_validation": ["r"]}}


class RelationReportingTests(unittest.TestCase):
    def test_unique_sample_denominator_and_all_states(self):
        rows = records()
        for row, decision in zip(rows[5:], ("MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE", "FAILED", "EMPTY_MODEL")):
            row["decision"] = decision
        s = report.summarize_rows(rows, settings())
        self.assertEqual(s["inventory"]["unique_mtc_records"], 3)
        self.assertEqual(s["inventory"]["model_evaluations"], 10)
        mtc = s["schemes"]["B_REL"]["folds"]["fold-01"]["mtc"]
        self.assertEqual(mtc["discovery"]["unknown"], 1)
        self.assertEqual(mtc["development"]["failed"], 1)
        self.assertEqual(mtc["reserved_validation"]["empty_model"], 1)
        self.assertEqual(mtc["development"]["no_alert"], 0)
        self.assertEqual(mtc["development"]["defined_coverage"]["denominator"], 1)

    def test_missing_even_in_both_schemes_and_duplicate_rejected(self):
        rows = records()
        with self.assertRaisesRegex(ValueError, "SAVED_SETTINGS_MEMBER_MISMATCH"):
            report.summarize_rows([r for r in rows if r["sample_id"] != "v"], settings())
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PREDICTION"):
            report.summarize_rows(rows + [deepcopy(rows[0])], settings())

    def test_new_selected_relation_gain_and_normal_false_alarm(self):
        rows = records()
        for r in rows[5:]:
            if r["sample_id"] not in ("attack", "v"):
                continue
            r["decision"] = "MANIPULATION_ALERT"
            r["rules"] = [{"atom_id": REL, "clause_id": REL + ":POSITIVE", "state": "T", "polarity": "POSITIVE"}]
            r["relation_results"][0]["state"] = "T"
        s = report.summarize_rows(rows, settings())
        a = next(r for r in s["relation_analysis"] if r["subset"] == "controlled_attack")
        n = next(r for r in s["relation_analysis"] if r["subset"] == "development")
        self.assertEqual(a["new_attack_detections_vs_B"], 1)
        self.assertEqual(a["unique_selected_rule_alerts"], 1)
        self.assertEqual(n["new_normal_alerts_vs_B"], 1)
        self.assertEqual(n["normal_T_examples"][0]["profile"]["model"], "normal-tablet")

    def test_unselected_relation_true_not_counted_as_model_contribution(self):
        rows = records(); row = rows[5]
        row["decision"] = "MANIPULATION_ALERT"
        row["rules"] = [{"atom_id": "OLD", "state": "T"}]
        row["relation_results"][0]["state"] = "T"
        s = report.summarize_rows(rows, settings())
        a = next(r for r in s["relation_analysis"] if r["subset"] == "controlled_attack")
        self.assertEqual(a["T"], 1)
        self.assertEqual(a["selected_literal_T"], 0)
        self.assertEqual(a["new_attack_detections_vs_B"], 0)
        self.assertEqual(len(s["relation_analysis"]), 5)  # B has no raw relations, never counted as failures.

    def test_negative_literal_and_duplicate_triggers_distinguished(self):
        rows = records(); row = rows[5]
        row["decision"] = "MANIPULATION_ALERT"
        row["rules"] = [{"atom_id": REL, "state": "T", "polarity": "NEGATIVE"}, {"atom_id": "OLD", "state": "T"}]
        s = report.summarize_rows(rows, settings())
        a = next(r for r in s["relation_analysis"] if r["subset"] == "controlled_attack")
        self.assertEqual(a["F"], 1)
        self.assertEqual(a["selected_literal_T"], 1)
        self.assertEqual(a["unique_selected_rule_alerts"], 0)

    def test_training_reasons_preserve_missing_and_normal_constraints(self):
        c = {"atom_id": REL, "clause_id": REL + ":POSITIVE", "admitted": False, "selected": False,
             "controlled_attack": {"T": 0, "expected": 84}, "controlled_clean": {"T": 9, "expected": 168},
             "mtc_normal": {"T": 32, "expected": 630, "defined": 500}}
        reasons = report.relation_training({"candidate_statistics": [c]}, {REL})[0]["diagnostic_classification"]
        self.assertEqual(len(reasons), 4)
        self.assertIn("NO_TRAIN_ATTACK_TRIGGER", reasons)
        self.assertIn("MTC_EVALUABLE_COVERAGE_BELOW_90_PERCENT", reasons)

    def test_saved_compressed_summary_is_reproducible_without_raw_data(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "SETTINGS.json").write_text(json.dumps(settings()))
            with gzip.open(p / "predictions.jsonl.gz", "wt") as stream:
                for r in records():
                    stream.write(json.dumps(r) + "\n")
            models = []
            for scheme in ("B", "B_REL"):
                path = scheme + ".json"
                model = {"model_id": scheme + "-model", "status": "FITTED", "clauses": [], "atoms": [],
                         "complexity": {"objective_complexity": 0}}
                (p / path).write_text(json.dumps(model))
                train = scheme + "-training.json"
                (p / train).write_text(json.dumps({"candidate_statistics": []}))
                models.append({"scheme": scheme, "fold_id": "fold-01", "stage": "RETENTION", "model_id": model["model_id"],
                               "path": path, "training_path": train})
            (p / "models.json").write_text(json.dumps({"models": models}))
            report.summarize(p)
            first = [(p / n).read_bytes() for n in ("summary.json", "REPORT.md")]
            report.summarize(p)
            self.assertEqual(first, [(p / n).read_bytes() for n in ("summary.json", "REPORT.md")])


if __name__ == "__main__":
    unittest.main()
