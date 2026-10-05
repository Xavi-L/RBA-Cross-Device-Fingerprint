"""Focused denominator, alignment and saved-only reporting checks."""
import importlib.util
import gzip
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / "deliverables/mtc_constrained_reselection_v1/summarize.py"
spec = importlib.util.spec_from_file_location("mtc_reselection_reporting", MODULE)
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


def row(scheme="BASELINE", fold="01", sid="x", dataset="mtc", decision="NO_ALERT", **extra):
    result = {"scheme": scheme, "fold_id": fold, "model_id": scheme + fold,
              "sample_id": sid, "dataset": dataset, "subset": "discovery" if dataset == "mtc" else "heldout",
              "decision": decision, "normal_basis": {"supported": dataset == "mtc"},
              "profile": {"manufacturer": "m", "model": "p", "android_release": "13"}, "rules": []}
    if dataset == "controlled":
        result.update(stage="attack", configuration_id="config")
    result.update(extra)
    return result


class ReportingTests(unittest.TestCase):
    def test_all_outcomes_stay_in_denominator_and_empty_is_not_normal(self):
        rows = [row(sid=str(i), decision=decision) for i, decision in enumerate(reporting.DECISIONS)]
        result = reporting.count_rows(rows)
        self.assertEqual(result["defined_coverage"], reporting.ratio(2, 5))
        self.assertEqual(result["normal_observed_alert_proportion"], reporting.ratio(1, 5))
        self.assertEqual((result["unknown"], result["failed"], result["empty_model"]), (1, 1, 1))
        self.assertEqual(result["processed_records"], 4)

    def test_unsupported_normal_basis_only_appears_in_all_record_rate(self):
        result = reporting.count_rows([row(decision="MANIPULATION_ALERT", normal_basis={"supported": False}), row(sid="y")])
        self.assertEqual(result["observed_alert_proportion"], reporting.ratio(1, 2))
        self.assertEqual(result["normal_observed_alert_proportion"], reporting.ratio(0, 1))

    def test_unknown_decision_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError, "UNRECOGNIZED_DECISION"):
            reporting.count_rows([row(decision="MAYBE")])

    def test_same_mtc_sample_three_models_counts_once(self):
        rows = [row(scheme=s, fold=f) for s in reporting.SCHEMES for f in ("01", "02", "03")]
        result = reporting.summarize_rows(rows)
        self.assertEqual(result["inventory"]["unique_mtc_records"], 1)
        self.assertEqual(result["inventory"]["model_evaluations"], 9)
        self.assertEqual(result["schemes"]["B"]["mtc_agreement"]["discovery"]["unique_records"], 1)
        self.assertEqual(result["schemes"]["B"]["folds"]["02"]["mtc"]["discovery"]["records"], 1)

    def test_comparison_requires_exact_members(self):
        with self.assertRaisesRegex(ValueError, "COMPARISON_MEMBER_MISMATCH"):
            reporting.summarize_rows([row(), row(scheme="A", sid="different")])

    def test_all_schemes_missing_same_record_is_detected_from_saved_settings(self):
        settings = {"schemes": {"A": {}, "B": {}}, "folds": [{"fold_id": "01", "outer_test_ids": ["attack"]}],
                    "mtc_primary_ids": {"discovery": ["x", "missing"]}}
        data = [row(scheme=s) for s in reporting.SCHEMES]
        data += [row(scheme=s, sid="attack", dataset="controlled") for s in reporting.SCHEMES]
        with self.assertRaisesRegex(ValueError, "SAVED_SETTINGS_MEMBER_MISMATCH"):
            reporting.validate_saved_members(data, settings)

    def test_duplicate_model_row_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PREDICTION"):
            reporting.summarize_rows([row(), row()])

    def test_oof_cannot_pool_duplicate_attack_sample(self):
        with self.assertRaisesRegex(ValueError, "CONTROLLED_OOF_RECORD_REPEATED"):
            reporting.summarize_rows([row(fold="01", dataset="controlled"), row(fold="02", dataset="controlled")])

    def test_training_support_is_not_claimed_as_heldout_alternative(self):
        old = row(dataset="controlled", decision="MANIPULATION_ALERT", rules=[{"clause_id": "old", "state": "T"}])
        new = row(scheme="A", dataset="controlled", decision="NO_ALERT")
        training = {"A01": {"candidate_statistics": [
            {"clause_id": "old", "selected": False, "admitted": True, "triggered_config_ids": ["config"], "singleton_budget_reasons": ["MTC_BUDGET"]},
            {"clause_id": "other", "selected": False, "admitted": True, "triggered_config_ids": ["config"], "singleton_budget_reasons": []}]}}
        miss = reporting.explain_new_misses([old, new], training)[0]
        self.assertEqual(miss["baseline_clauses_not_selected"], ["old"])
        self.assertEqual(miss["train_singleton_admissible_candidate_ids"], ["other"])
        self.assertEqual(miss["classification"], "TRAIN_SUPPORTED_SINGLETON_CANDIDATES_EXIST_COMBINATION_NOT_ESTABLISHED")
        self.assertIn("不能声称理论不可能", miss["limitation"])

    def test_heldout_diagnostics_keep_training_budget_rejection(self):
        old = row(dataset="controlled", decision="MANIPULATION_ALERT")
        new = row(scheme="B", dataset="controlled", decision="NO_ALERT")
        training = {"B01": {"candidate_statistics": [{"clause_id": "high_memory", "selected": False,
            "admitted": True, "triggered_config_ids": ["config"], "singleton_budget_reasons": ["MTC_SET_NORMAL_BUDGET"],
            "mtc_normal": {"expected": 630, "T": 600}}]}}
        diagnostics = [{"scheme": "B", "fold_id": "01", "configuration_id": "config", "clause_id": "high_memory",
                        "heldout_attack_T": 3, "heldout_attack_n": 3}]
        miss = reporting.explain_new_misses([old, new], training, diagnostics)[0]
        self.assertEqual(len(miss["heldout_triggering_candidates"]), 1)
        self.assertEqual(miss["heldout_triggering_train_singleton_admissible_candidate_ids"], [])
        self.assertEqual(miss["heldout_triggering_candidates"][0]["train_mtc_normal"]["T"], 600)

    def test_rule_unknown_is_preserved_even_if_other_rule_alerts(self):
        result = reporting.summarize_rows([row(decision="MANIPULATION_ALERT", rules=[
            {"clause_id": "missing", "state": "U", "reason": "MISSING_RAW_QUERY"},
            {"clause_id": "observed", "state": "T"}])])
        stats = result["schemes"]["BASELINE"]["folds"]["01"]["mtc"]["discovery"]
        self.assertEqual(stats["rules"]["missing"]["U"], 1)
        self.assertEqual(stats["rules"]["missing"]["unknown_reasons"], {"MISSING_RAW_QUERY": 1})
        self.assertEqual(stats["rules"]["observed"]["unique_alerts"], 1)
        self.assertEqual(stats["unknown"], 0)

    def test_saved_only_rebuild_does_not_touch_predictions_or_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            data = [row(), row(scheme="A")]
            predictions = out / "predictions.jsonl"
            predictions.write_text("\n".join(json.dumps(r) for r in data) + "\n")
            manifest = out / "models.json"
            manifest.write_text(json.dumps({"models": [{"scheme": "A", "fold_id": "01", "stage": "RETENTION", "model_id": "A01", "status": "EMPTY_MODEL", "selected_clauses": [], "training_path": "training.json"}]}))
            training = out / "training.json"
            training.write_text(json.dumps({"candidate_statistics": []}))
            before = {p.name: p.read_bytes() for p in (predictions, manifest, training)}
            reporting.summarize(out)
            first = (out / "REPORT.md").read_bytes(), (out / "summary.json").read_bytes()
            reporting.summarize(out)
            self.assertEqual(first, ((out / "REPORT.md").read_bytes(), (out / "summary.json").read_bytes()))
            self.assertEqual(before, {p.name: p.read_bytes() for p in (predictions, manifest, training)})
            self.assertIn("不训练、不预测", (out / "REPORT.md").read_text())

    def test_compressed_predictions_are_supported_without_decompression_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / "predictions.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(json.dumps(row()) + "\n")
            before = path.read_bytes()
            result = reporting.summarize(out)
            self.assertEqual(result["inventory"]["unique_mtc_records"], 1)
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((out / "predictions.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
