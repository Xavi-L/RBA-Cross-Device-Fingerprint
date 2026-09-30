"""Synthetic helper boundaries; never run prepare(), saved campaigns or models."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest


_SOURCE = (Path(__file__).resolve().parents[2] /
           "deliverables/rule_semantics_retraining_preparation_v1/prepare.py")
_SPEC = importlib.util.spec_from_file_location("rsr_preparation_helpers", _SOURCE)
prepare = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = prepare
_SPEC.loader.exec_module(prepare)


def triplet(name, environment="SYNTHETIC-env-a", config="SYNTHETIC-config"):
    return [{"opaque_id": f"SYNTHETIC-{name}-{phase}", "bundle_id": f"SYNTHETIC-bundle-{environment}",
             "triplet_id": f"SYNTHETIC-{name}", "environment_group_id": environment,
             "config_id": config, "phase": phase, "supervised_label": int(phase == "attack")}
            for phase in prepare.PHASES]


class PreparationHelperTests(unittest.TestCase):
    def test_unique_rejects_duplicate_even_when_rows_are_identical(self):
        rows = [{"id": "SYNTHETIC-a", "value": 1}, {"id": "SYNTHETIC-b", "value": 2}]
        before = deepcopy(rows)
        self.assertEqual(set(prepare.unique(rows, "id")), {"SYNTHETIC-a", "SYNTHETIC-b"})
        self.assertEqual(rows, before)
        for duplicate in (deepcopy(rows[0]), {"id": "SYNTHETIC-a", "value": 99}):
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, "DUPLICATE_id"):
                prepare.unique(rows + [duplicate], "id")

    def test_role_assignment_excludes_all_thirteen_auxiliary_rows(self):
        steps = [{"group": "smoke", "phase": "smoke"}]
        for group, rounds, middle in (("no_attack", 3, "control_mid"),
                                     ("debug_transport_control", 1, "control_mid"),
                                     ("webdriver", 3, "attack"), ("language", 3, "attack")):
            for _ in range(rounds):
                steps.extend({"group": group, "phase": phase}
                             for phase in ("clean_pre", middle, "clean_post"))
        roles = [prepare.role_for(step) for step in steps]
        supervised = [r for r in roles if r["proposed_supervised_member"]]
        auxiliary = [r for r in roles if not r["proposed_supervised_member"]]
        self.assertEqual(len(roles), 31)
        self.assertEqual(len(auxiliary), 13)
        self.assertTrue(all(r["proposed_supervised_label"] is None for r in auxiliary))
        self.assertEqual(len(supervised), 18)
        self.assertEqual(sum(r["proposed_supervised_label"] == 1 for r in supervised), 6)
        self.assertEqual(sum(r["proposed_supervised_label"] == 0 for r in supervised), 12)
        self.assertTrue(all(r["fit_permission"] == "DENIED_PREPARATION_ONLY" for r in roles))

    def test_folds_hold_whole_environments_and_complete_triplets(self):
        rows = (triplet("a1") + triplet("a2") +
                triplet("b1", "SYNTHETIC-env-b") + triplet("b2", "SYNTHETIC-env-b"))
        before = deepcopy(rows)
        all_ids = {r["opaque_id"] for r in rows}
        folds = prepare.build_folds(rows)
        self.assertEqual(len(folds), 2)
        self.assertEqual(rows, before)
        self.assertEqual(sorted(i for fold in folds for i in fold["outer_test_ids"]), sorted(all_ids))
        for fold in folds:
            train, test = set(fold["train_ids"]), set(fold["outer_test_ids"])
            self.assertFalse(train & test)
            self.assertEqual(train | test, all_ids)
            self.assertEqual(test, {r["opaque_id"] for r in rows
                                   if r["environment_group_id"] == fold["heldout_environment"]})
            self.assertEqual((fold["train_n"], fold["test_n"]), (6, 6))
            for name in {r["triplet_id"] for r in rows}:
                members = {r["opaque_id"] for r in rows if r["triplet_id"] == name}
                self.assertTrue(members <= train or members <= test)

    def test_folds_reject_partial_duplicate_or_split_triplets_and_bad_labels(self):
        scenarios = []
        base = triplet("a") + triplet("b", "SYNTHETIC-env-b")
        scenarios.append((base[:-1], "INCOMPLETE_SUPERVISED_TRIPLET"))
        changed = deepcopy(base)
        duplicate = deepcopy(changed[0])
        duplicate["opaque_id"] += "-other"
        scenarios.append((changed + [duplicate], "DUPLICATE_TRIPLET_PHASE"))
        for field in ("environment_group_id", "config_id"):
            changed = deepcopy(base)
            changed[0][field] = "SYNTHETIC-different"
            scenarios.append((changed, "BUNDLE_ENVIRONMENT_SPLIT" if field == "environment_group_id"
                              else "TRIPLET_ENVIRONMENT_OR_CONFIG_SPLIT"))
        changed = deepcopy(base)
        changed[1]["supervised_label"] = 0
        scenarios.append((changed, "SUPERVISED_PHASE_LABEL_MISMATCH"))
        for rows, reason in scenarios:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                prepare.build_folds(rows)

    def test_folds_reject_one_bundle_across_environments_even_with_complete_triplets(self):
        rows = triplet("a") + triplet("b", "SYNTHETIC-env-b")
        for row in rows:
            row["bundle_id"] = "SYNTHETIC-shared-bundle"
        with self.assertRaisesRegex(ValueError, "BUNDLE_ENVIRONMENT_SPLIT"):
            prepare.build_folds(rows)

    def test_invalid_phase_empty_fold_input_and_boolean_label_are_rejected(self):
        for group in ("webdriver", "language"):
            with self.subTest(group=group), self.assertRaises(ValueError):
                prepare.role_for({"group": group, "phase": "SYNTHETIC-unknown"})
        with self.assertRaises(ValueError):
            prepare.build_folds([])
        for phase, boolean_label in (("attack", True), ("clean_pre", False)):
            with self.subTest(phase=phase):
                rows = triplet("a")
                next(r for r in rows if r["phase"] == phase)["supervised_label"] = boolean_label
                with self.assertRaises(ValueError):
                    prepare.build_folds(rows)

    def test_support_unknown_and_failed_are_never_false_or_complete(self):
        triples = [triplet(name) for name in ("positive", "negative", "unknown", "failed")]
        state_triples = (("F", "T", "F"), ("F", "F", "F"),
                         ("U", "T", "F"), ("F", "FAILED", "U"))
        rows = [r for members in triples for r in members]
        metadata = {r["opaque_id"]: r for r in rows}
        cells = {r["opaque_id"]: {"SYNTHETIC-candidate": state}
                 for members, states in zip(triples, state_triples)
                 for r, state in zip(members, states)}
        saved_cells = deepcopy(cells)
        positive = prepare.support_for(list(metadata), metadata, cells, "SYNTHETIC-candidate", "POSITIVE")
        negative = prepare.support_for(list(metadata), metadata, cells, "SYNTHETIC-candidate", "NEGATIVE")
        self.assertEqual(cells, saved_cells)
        self.assertEqual(positive["state_counts_before_polarity"], {"T": 2, "F": 7, "U": 2, "FAILED": 1})
        self.assertEqual(negative["state_counts_before_polarity"], positive["state_counts_before_polarity"])
        for support in (positive, negative):
            self.assertEqual(support["complete_available_triplets"], 2)
            self.assertEqual(support["true_attack_triplets"], 1)
            self.assertFalse(support["meets_count_support"])
            self.assertEqual(support["train_clean_n"], 8)
        self.assertEqual(positive["single_literal_clean_alerts"], 0)
        self.assertEqual(negative["single_literal_clean_alerts"], 6)
        # Explicitly complementing only known states and using positive polarity
        # must agree with negative polarity; U and FAILED remain unchanged.
        complement = {sid: {"SYNTHETIC-candidate": {"T": "F", "F": "T", "U": "U", "FAILED": "FAILED"}[v["SYNTHETIC-candidate"]]}
                      for sid, v in cells.items()}
        inverted = prepare.support_for(list(metadata), metadata, complement, "SYNTHETIC-candidate", "POSITIVE")
        for key in ("complete_available_triplets", "true_attack_triplets", "support_bundles",
                    "support_environments", "single_literal_clean_alerts", "train_clean_n"):
            self.assertEqual(negative[key], inverted[key])
        self.assertEqual(inverted["state_counts_before_polarity"]["U"], 2)
        self.assertEqual(inverted["state_counts_before_polarity"]["FAILED"], 1)

    def test_support_incomplete_phase_set_is_rejected(self):
        rows = triplet("a")
        metadata = {r["opaque_id"]: r for r in rows}
        cells = {sid: {"SYNTHETIC-candidate": "F"} for sid in metadata}
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_SUPPORT_TRIPLET"):
            prepare.support_for(list(metadata)[:-1], metadata, cells, "SYNTHETIC-candidate", "POSITIVE")

    def test_support_rejects_duplicate_members_phases_bad_polarity_and_state(self):
        rows = triplet("a")
        metadata = {r["opaque_id"]: r for r in rows}
        ids = list(metadata)
        cells = {sid: {"SYNTHETIC-candidate": "F"} for sid in metadata}
        with self.assertRaises(ValueError):
            prepare.support_for(ids + [ids[0]], metadata, cells, "SYNTHETIC-candidate", "POSITIVE")
        with self.assertRaises(ValueError):
            prepare.support_for(ids, metadata, cells, "SYNTHETIC-candidate", "SYNTHETIC-invalid")
        duplicate = deepcopy(rows[0])
        duplicate["opaque_id"] += "-other"
        with self.assertRaises(ValueError):
            prepare.support_for(ids + [duplicate["opaque_id"]], metadata | {duplicate["opaque_id"]: duplicate},
                                cells | {duplicate["opaque_id"]: {"SYNTHETIC-candidate": "F"}},
                                "SYNTHETIC-candidate", "POSITIVE")
        malformed = deepcopy(cells)
        malformed[ids[0]]["SYNTHETIC-candidate"] = "SYNTHETIC-not-a-state"
        for polarity in ("POSITIVE", "NEGATIVE"):
            with self.subTest(polarity=polarity), self.assertRaises((ValueError, KeyError)):
                prepare.support_for(ids, metadata, malformed, "SYNTHETIC-candidate", polarity)


if __name__ == "__main__":
    unittest.main()
