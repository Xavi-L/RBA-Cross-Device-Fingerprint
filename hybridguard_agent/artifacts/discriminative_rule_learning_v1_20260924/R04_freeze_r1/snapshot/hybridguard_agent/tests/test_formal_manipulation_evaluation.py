"""Synthetic persisted-worker, denominator, join and plotting interface tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research.manipulation_eval.contract import read_jsonl, POLICY_REF
from hybridguard_agent.research.manipulation_eval.evaluation import evaluate_saved, evaluation_label, load_closed_predictions, join_rows, summarize, temporal_results, matched_deltas
from hybridguard_agent.research.manipulation_eval.persistence import write_json, write_jsonl
from hybridguard_agent.research.manipulation_eval.reporting import export_figure_data, source_overlap
from hybridguard_agent.research.manipulation_eval.runner import run_predictions, validate_protocol
from hybridguard_agent.research.manipulation_eval.synthetic import evaluation_fixture
from hybridguard_agent.tests.test_formal_manipulation_policy import load


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name)
        cls.fixture = evaluation_fixture(); cls.contract = load()
        for key in ("inputs", "evaluation_index", "triplets"):
            write_jsonl(cls.root / (key + ".jsonl"), cls.fixture[key])
        cls.manifest = run_predictions(input_path=cls.root / "inputs.jsonl", protocol=cls.fixture["job"], contract=cls.contract, output=cls.root / "prediction")
        cls.metrics = evaluate_saved(prediction_dir=cls.root / "prediction", index_path=cls.root / "evaluation_index.jsonl",
                                     triplets_path=cls.root / "triplets.jsonl", output=cls.root / "evaluation")
        cls.joined = read_jsonl(cls.root / "evaluation/evaluation_joined.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixed_positive_and_negative_denominators_include_failure_abstention(self):
        m = self.metrics["variants"][0]
        for key in ("positive_TPR", "primary_control_mid_FPR"):
            r = m[key]
            self.assertEqual((r["n"], r["alert"], r["no_alert"], r["abstain"], r["failed"]), (4, 1, 1, 1, 1))
            self.assertEqual((r["rate"], r["decision_coverage"], r["conditional_rate"]), (0.25, 0.5, 0.5))
            self.assertEqual(r["identifiable_bounds"], [0.25, 0.5])
            self.assertEqual(r["status"], "INCOMPLETE")
        r = m["verified_negative_all"]
        self.assertEqual((r["n"], r["alert"], r["no_alert"], r["abstain"], r["failed"]), (8, 1, 3, 2, 2))
        self.assertEqual(m["unknown_truth"], 2)

    def test_exact_010_missing_post_and_failed_post_never_become_zero(self):
        triplets = read_jsonl(self.root / "evaluation/triplet_results.jsonl")
        by_id = {t["triplet_id"]: t for t in triplets}
        self.assertTrue(by_id["t1"]["success_010"])
        self.assertFalse(by_id["t2"]["success_010"])
        self.assertEqual(by_id["t3"]["phase_decisions"]["clean_post"], "MISSING_PHASE")
        self.assertEqual(self.metrics["variants"][0]["triplets"]["rate_010"], 1 / 3)
        self.assertEqual(self.metrics["variants"][0]["triplets"]["incomplete"], 2)
        self.assertEqual(self.metrics["variants"][0]["triplets"]["conditional_recovery_rate"], 1)

    def test_unknown_time_controls_never_acquire_negative_eligibility(self):
        e = copy.deepcopy(self.fixture["evaluation_index"][-1])
        self.assertEqual(evaluation_label(e), "UNKNOWN")
        e["admission_fact"]["eligible_temporal_control"] = True
        with self.assertRaises(ValueError): evaluation_label(e)
        e = copy.deepcopy(self.fixture["evaluation_index"][2])
        e["admission_fact"]["rollback"]["status"] = "UNKNOWN"
        with self.assertRaises(ValueError): evaluation_label(e)

    def test_labels_change_evaluation_not_saved_prediction_and_unknown_has_no_rate(self):
        _, predictions = load_closed_predictions(self.root / "prediction")
        original = copy.deepcopy(predictions)
        index = copy.deepcopy(self.fixture["evaluation_index"])
        for row in index:
            for flag in ("eligible_detection", "eligible_pre_control", "eligible_post_control", "eligible_temporal_control", "eligible_triplet"):
                row["admission_fact"][flag] = False
            row.update(tool="swapped", configuration_id="another", raw_session_ref="/other")
        joined = join_rows(predictions, index)
        metrics, _ = summarize(joined, [])
        self.assertIsNone(metrics["variants"][0]["positive_TPR"]["rate"])
        self.assertIsNone(metrics["variants"][0]["primary_control_mid_FPR"]["rate"])
        self.assertEqual(predictions, original)

    def test_equal_payloads_are_distinct_units_and_metadata_only_in_join(self):
        _, predictions = load_closed_predictions(self.root / "prediction")
        self.assertEqual(len(predictions), len({r["opaque_id"] for r in predictions}))
        self.assertEqual(self.fixture["inputs"][0]["payload"], self.fixture["inputs"][2]["payload"])
        self.assertNotEqual(predictions[0]["opaque_id"], predictions[2]["opaque_id"])
        for table in ("predictions", "rule_events", "runtime_records", "failures", "abstentions"):
            data = (self.root / "prediction" / (table + ".jsonl")).read_text()
            self.assertNotIn("evaluation-only-tool", data)
            self.assertNotIn("/evaluation-only/path", data)
            self.assertNotIn('"phase":', data)
        self.assertIn("evaluation-only-tool", (self.root / "evaluation/evaluation_joined.jsonl").read_text())

    def test_join_rejects_unclosed_missing_duplicate_and_foreign_run_records(self):
        original_read = json.loads((self.root / "prediction/run_manifest.json").read_text())
        for change in ("open", "count", "identity"):
            m = copy.deepcopy(original_read)
            if change == "open": m["prediction_files_closed"] = False
            if change == "count": m["expected_units"].pop()
            if change == "identity": m["run_id"] = "foreign"
            with patch("hybridguard_agent.research.manipulation_eval.evaluation.read_json", return_value=m):
                with self.assertRaises(ValueError): load_closed_predictions(self.root / "prediction")
        _, predictions = load_closed_predictions(self.root / "prediction")
        with self.assertRaises(ValueError): join_rows(predictions, self.fixture["evaluation_index"][:-1])
        with self.assertRaises(ValueError): join_rows(predictions, self.fixture["evaluation_index"] + self.fixture["evaluation_index"][:1])

    def test_bad_json_and_missing_input_still_have_unique_FAILED_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "input.jsonl").write_text('{bad json\n')
            job = copy.deepcopy(self.fixture["job"]); job["expected_units"] = job["expected_units"][:2]
            m = run_predictions(input_path=root / "input.jsonl", protocol=job, contract=self.contract, output=root / "out")
            self.assertEqual((m["prediction_count"], m["failure_count"]), (2, 2))
            _, rows = load_closed_predictions(root / "out")
            self.assertTrue(all(r["risk"]["decision"] == "FAILED" for r in rows))
            (root / "bad-encoding.jsonl").write_bytes(b'\xff\xfe')
            m = run_predictions(input_path=root / "bad-encoding.jsonl", protocol=job, contract=self.contract, output=root / "bad-encoding-out")
            self.assertEqual((m["prediction_count"], m["failure_count"]), (2, 2))

    def test_macro_average_uses_fixed_configuration_then_environment_groups(self):
        macro = self.metrics["variants"][0]["macro"]["positive_TPR"]
        # cfg-a/g1: one alert in two; cfg-b/g2: zero in two.
        self.assertEqual(macro["configuration_equal_weight"], 0.25)
        self.assertEqual(macro["environment_then_configuration_equal_weight"], 0.25)
        self.assertFalse(macro["independent_device_claim"])

    def test_temporal_three_points_remain_linked_without_truth_promotion(self):
        template = copy.deepcopy(self.joined[-1]); rows = []
        for i, phase in enumerate(("clean_pre", "control_mid", "clean_post")):
            r = copy.deepcopy(template); r["opaque_id"] = "sample-window-" + str(i)
            r["evaluation"]["phase"] = phase; r["evaluation"]["admission_fact"]["phase"] = phase
            r["prediction"]["risk"]["alert_score"] = i
            rows.append(r)
        trajectory = temporal_results(rows)[0]
        self.assertEqual(trajectory["mid_minus_pre"], 1)
        self.assertEqual(trajectory["post_minus_pre"], 2)
        self.assertEqual(set(trajectory["phase_truth"].values()), {"UNKNOWN"})
        self.assertFalse(trajectory["truth_inferred_from_trajectory"])
        comparison = matched_deltas([{"bundle_id": "a", "triplet_id": "a", "active_minus_pre": 3}], [trajectory],
                                    [{"attack_key": ["a", "a"], "control_key": [trajectory["bundle_id"], trajectory["triplet_id"]], "matching_basis": "PREDECLARED_ENVIRONMENT_BATCH"}])
        self.assertEqual(comparison[0]["difference_in_deltas"], 2)
        self.assertFalse(comparison[0]["adds_negative_denominator_units"])

    def test_reporting_consumes_saved_outputs_without_detector(self):
        with patch("hybridguard_agent.research.manipulation_eval.runner.worker", side_effect=AssertionError("No re-prediction")):
            result = export_figure_data(evaluation_dir=self.root / "evaluation", output=self.root / "figure_data", figure_spec_path=Path(POLICY_REF) / "figure_spec.json")
        self.assertEqual(result["detector_calls"], 0)
        self.assertEqual(result["source_prediction_rows"], 14)
        self.assertFalse(result["paper_result"])
        self.assertEqual(result["rendered_figures"], [])
        self.assertIn("n", (self.root / "figure_data/metric_points.csv").read_text().splitlines()[0])

    def test_source_overlap_retains_failures_and_unknown_truth_separately(self):
        left = self.joined[0]["variant_id"]
        copied = copy.deepcopy(self.joined)
        for r in copied: r["variant_id"] = "alias-for-synthetic-comparison"
        result = source_overlap(self.joined + copied, left, "alias-for-synthetic-comparison")
        pos = next(r for r in result if r["label_scope"] == "POSITIVE")
        self.assertEqual((pos["n"], pos["both_alert"], pos["failed_pair"], pos["abstention_pair"]), (4, 1, 1, 1))
        self.assertEqual(pos["net_alert_count_change"], 0)

    def test_job_alias_duplicates_leaky_keys_and_unfrozen_formal_runs_rejected(self):
        for what in ("alias", "label", "formal", "version"):
            p = copy.deepcopy(self.fixture["job"])
            if what == "alias": p["variants"].append({**p["variants"][0], "variant_id": "same-execution"})
            if what == "label": p["expected_units"][0]["phase"] = "attack"
            if what == "formal": p["execution_scope"] = "FROZEN_FORMAL_EVALUATION"
            if what == "version": p["contract_version"] = "v1"
            with self.assertRaises(ValueError): validate_protocol(p, self.contract)


if __name__ == "__main__":
    unittest.main()
