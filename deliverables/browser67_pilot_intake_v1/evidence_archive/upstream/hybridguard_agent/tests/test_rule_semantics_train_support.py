"""Synthetic, train-only support checks; never load real candidate results."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest

from deliverables.rule_semantics_candidate_evaluation.support_diagnostic import (
    build_train_support, SUPPORT_THRESHOLDS,
)


ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R04_freeze_r1/snapshot"
SEARCH = FROZEN / "hybridguard_agent/config/rule_learning_v1_20260924/learning_search_space.json"
SUPPORT = json.loads(SEARCH.read_text())["support"]
KEY = ("SYNTHETIC-CANDIDATE", "default")
PHASES = ("clean_pre", "attack", "clean_post")


def fixture(patterns):
    results, metadata, ids = [], {}, []
    for number, pattern in enumerate(patterns):
        for phase, state in zip(PHASES, pattern):
            opaque_id = f"synthetic-{number}-{phase}"
            ids.append(opaque_id)
            metadata[opaque_id] = {"phase": phase, "bundle_id": "B0", "triplet_id": f"TRIO-{number}",
                "config_id": "C0", "environment_group_id": "E0", "supervised_label": int(phase == "attack")}
            results.append({"opaque_id": opaque_id, "candidate_id": KEY[0], "mode": KEY[1], "state": state})
    folds = {"folds": [{"fold_id": "LOEO-v1-01", "split_id": "LOEO-v1",
                       "target": "HELD_OUT", "train": ids, "outer_test": ["held-out"]}]}
    return results, metadata, folds


def diagnose(data):
    return build_train_support(*data, SUPPORT, [KEY])


def signed(report, polarity):
    return next(r for r in report["fold_candidate_diagnostics"] if r["literal_polarity"] == polarity)


class TrainSupportTests(unittest.TestCase):
    def test_frozen_thresholds_and_selector_four_conditions(self):
        self.assertEqual({k: SUPPORT[k] for k in SUPPORT_THRESHOLDS}, SUPPORT_THRESHOLDS)
        source = (FROZEN / "hybridguard_agent/research/rule_learning/selector.py").read_text()
        tree = ast.parse(source)
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_support")
        assignment = next(n for n in ast.walk(method) if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                    and t.slice.value == "eligible" for t in n.targets))
        checks = [node for node in ast.walk(assignment.value) if isinstance(node, ast.Compare)]
        self.assertEqual(len(checks), 4)
        keys = {node.comparators[0].slice.value for node in checks}
        self.assertEqual(keys, set(SUPPORT_THRESHOLDS))

    def test_three_available_two_true_boundary_is_eligible(self):
        data = fixture(["FTF", "FTF", "FFF"])
        before = deepcopy(data)
        out = diagnose(data)
        pos = signed(out, "POSITIVE")
        self.assertEqual((pos["complete_metadata_triplets"], pos["available_complete_triplets"], pos["true_attack_triplets"]), (3, 3, 2))
        self.assertEqual((pos["support_bundles"], pos["support_environments"], pos["support_configurations"]), (1, 1, 1))
        self.assertTrue(pos["support_eligible"])
        self.assertFalse(signed(out, "NEGATIVE")["support_eligible"])
        self.assertEqual(out["expected_signed_diagnostic_count"], 2)
        self.assertEqual(data, before)

    def test_constant_false_negative_support_is_not_signal_or_selection(self):
        out = diagnose(fixture(["FFF"] * 3))
        self.assertFalse(signed(out, "POSITIVE")["support_eligible"])
        neg = signed(out, "NEGATIVE")
        self.assertTrue(neg["support_eligible"])
        self.assertEqual(neg["train_clean_literal_true"], {"k": 6, "n": 6})
        self.assertEqual(neg["model_feasibility_or_selection"], "NOT_EVALUATED")
        self.assertEqual(out["execution_counts"], {"candidate_calls": 0, "fit": 0, "model_prediction": 0})

    def test_unknown_any_phase_removes_whole_triplet_for_both_polarities(self):
        out = diagnose(fixture(["FTF", "FTF", "UUF"]))
        for rec in out["fold_candidate_diagnostics"]:
            self.assertEqual(rec["complete_metadata_triplets"], 3)
            self.assertEqual(rec["available_complete_triplets"], 2)
            self.assertEqual(rec["train_state_counts"]["U"], 2)
            self.assertFalse(rec["support_eligible"])
            self.assertEqual(sum(rec["train_state_counts"].values()), 9)
            for phase in PHASES:
                p = rec["phase_availability"][phase]
                self.assertEqual(sum(p[s] for s in ("T", "F", "U", "FAILED")), p["expected"])

    def test_any_train_failed_forbids_even_when_minimum_support_passes(self):
        out = diagnose(fixture(["FTF", "FTF", "FFF", ("FAILED", "F", "F")]))
        pos = signed(out, "POSITIVE")
        self.assertTrue(pos["support_thresholds_satisfied"])
        self.assertFalse(pos["support_eligible"])
        self.assertIn("TRAIN_EXECUTION_FAILURE", pos["reasons"])
        self.assertEqual(signed(out, "NEGATIVE")["train_state_counts"]["FAILED"], 1)

    def test_held_out_states_and_metadata_are_never_read(self):
        class HeldOutResult(dict):
            def get(self, key, default=None):
                if key == "state":
                    raise AssertionError("HELD_OUT_STATE_READ")
                return super().get(key, default)
        class Meta(dict):
            def get(self, key, default=None):
                if key == "held-out":
                    raise AssertionError("HELD_OUT_METADATA_READ")
                return super().get(key, default)
        data = fixture(["FTF", "FTF", "FFF"])
        expected = diagnose(data)
        results, metadata, folds = data
        results.append(HeldOutResult(opaque_id="held-out", candidate_id=KEY[0], mode=KEY[1], state="FAILED"))
        self.assertEqual(diagnose((results, Meta(metadata), folds)), expected)

    def test_exact_pairing_never_joins_similar_triplet_ids_across_bundles(self):
        data = fixture(["FTF", "FTF", "FFF"])
        for oid, meta in data[1].items():
            number = oid.split("-")[1]
            meta["bundle_id"], meta["triplet_id"] = "B" + number, "SAME-TRIPLET-ID"
        pos = signed(diagnose(data), "POSITIVE")
        self.assertEqual(pos["complete_metadata_triplets"], 3)
        self.assertEqual(pos["support_bundles"], 2)
        self.assertTrue(pos["support_eligible"])

    def test_pairing_gap_blocks_without_reordering_to_fill_it(self):
        data = fixture(["FTF", "FTF", "FTF", "FTF"])
        data[1]["synthetic-0-clean_pre"]["triplet_id"] = "OTHER"
        pos = signed(diagnose(data), "POSITIVE")
        self.assertEqual(pos["complete_metadata_triplets"], 3)
        self.assertTrue(pos["support_thresholds_satisfied"])
        self.assertFalse(pos["support_eligible"])
        self.assertEqual(len(pos["triplet_pairing_gaps"]), 2)

    def test_missing_or_duplicate_saved_train_result_stays_failed(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                data = fixture(["FTF", "FTF", "FTF", "FTF"])
                if duplicate:
                    data[0].append(dict(data[0][0]))
                else:
                    data[0].pop(0)
                pos = signed(diagnose(data), "POSITIVE")
                self.assertEqual(pos["train_state_counts"]["FAILED"], 1)
                self.assertFalse(pos["support_eligible"])
                self.assertEqual(pos["unique_train_stages"], 12)

    def test_loco_is_ignored_and_train_test_overlap_cannot_pass(self):
        data = fixture(["FTF", "FTF", "FFF"])
        data[2]["folds"].append({"split_id": "LOCO-v1", "train": None})
        out = diagnose(data)
        self.assertEqual(out["selected_folds"], ["LOEO-v1-01"])
        data[2]["folds"][0]["outer_test"].append(data[2]["folds"][0]["train"][0])
        rec = signed(diagnose(data), "POSITIVE")
        self.assertIn("TRAIN_TEST_MEMBER_OVERLAP", rec["membership_issues"])
        self.assertFalse(rec["support_eligible"])

    def test_lowered_threshold_is_not_accepted(self):
        contract = deepcopy(SUPPORT)
        contract["minimum_available_triplets"] = 2
        with self.assertRaisesRegex(ValueError, "UNREVIEWED_SUPPORT_THRESHOLD"):
            build_train_support(*fixture(["FTF"] * 2), contract, [KEY])


if __name__ == "__main__":
    unittest.main()
