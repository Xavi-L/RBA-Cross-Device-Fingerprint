import copy
import json
from pathlib import Path
import tempfile
import unittest

from hybridguard_agent.evidence.paired244 import build_paired_evidence, legacy_payload
from hybridguard_agent.research.mtc_p6 import (
    METRICS, definitions, variants, load_p6_rows, summarize, paired_comparison, group_outcome, write_json,
)
from hybridguard_agent.runtime.paired244 import analyze_paired244_record
from hybridguard_agent.scripts.run_mtc_p6 import execute_one, claim_release
from hybridguard_agent.tests.test_paired244_runtime import fixture


def row(sid="a", split="discovery", group="group-a", line=1):
    r = fixture()
    r.update(sample_id=sid, dataset_view="paired_244", feature_count=244,
             profile={"manufacturer": "fixture", "model": "M", "android_release": "14", "android_api": 34,
                      "collector_install_id": "fixture-install"},
             _p2={"group_id": group, "split": split, "source_line": line, "analysis_role": "primary_representative"})
    return r


def metric_row(sid, group, value):
    return {"sample_id": sid, "group_id": group, "status": "COMPLETE", "decision_status": "context_observed",
            "metrics": {m: value for m in METRICS}, "elapsed_ms": 1, "outcome_counts": {"MATCH": 1}}


class P6RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = variants()

    def test_fifteen_frozen_conditions_and_source_accounting(self):
        self.assertEqual(len(definitions()), 15)
        self.assertEqual([self.specs[n]["active_count"] for n in
                          ("Full244", "Full244_empirical", "Full244_official", "Full244_support",
                           "Full244_empirical_official", "Full244_no_cross", "App177_v1", "App177_v2")],
                         [57, 23, 23, 11, 46, 49, 48, 54])
        self.assertEqual(len(self.specs["Full244_official"]["empirically_screened_official_ids"]), 14)
        self.assertEqual(self.specs["Full244_no_cross"]["cross_rule_ids"], [])

    def test_subset_selection_never_rewrites_predicates(self):
        original = {r["rule_id"]: r for r in self.specs["Full244"]["catalog_object"]["rules"]}
        for name in ("Full244_empirical", "Full244_official", "Full244_support", "Full244_no_cross"):
            for r in self.specs[name]["catalog_object"]["rules"]:
                self.assertEqual(r, original[r["rule_id"]])

    def test_combined_views_mask_before_extraction(self):
        source = row()
        for view, count, excluded_prefixes in (("NativeAppWeb151", 151, ("browser.", "app.webview_data.")),
                                               ("AppWebBrowser134", 134, ("app.android_native_data.", "app.webview_data."))):
            baseline = build_paired_evidence(source, view)
            changed = copy.deepcopy(source)
            for path in changed["features"]:
                if path.startswith(excluded_prefixes):
                    changed["features"][path] = "invalid excluded operand"
                    changed["field_status"][path] = "runtime_error"
            self.assertEqual(len(baseline["fields"]), count)
            self.assertEqual(build_paired_evidence(changed, view), baseline)
            result, _ = execute_one(changed, self.specs[view])
            self.assertEqual(result["status"], "COMPLETE")

    def test_control_metadata_is_not_runtime_evidence(self):
        a = row()
        b = copy.deepcopy(a)
        b.update(sample_id="attack-label-do-not-use", profile={"manufacturer": "manipulated"},
                 _p2={"split": "reserved_validation", "group_id": "different-group"})
        for key in ("decision", "rule_execution", "evidence_bundle"):
            self.assertEqual(analyze_paired244_record(a)[key], analyze_paired244_record(b)[key])

    def test_failure_is_retained_and_not_counted_as_zero_deviation(self):
        bad = row(); bad["record_schema_version"] = "invalid"
        result, rules = execute_one(bad, self.specs["Full244"])
        self.assertEqual(result["status"], "FAILED")
        self.assertIsNone(result["metrics"])
        self.assertEqual(rules, [])
        aggregate = summarize([metric_row("ok", "other", 1), result])
        self.assertEqual(aggregate["records"], 2)
        self.assertEqual(aggregate["failed_records"], 1)
        self.assertIsNone(aggregate["group_weighted_means"])

    def test_group_weighting_does_not_overweight_extra_os_representatives(self):
        summary = summarize([metric_row("a", "g1", 100), metric_row("b", "g1", 100), metric_row("c", "g2", 0)])
        self.assertEqual(summary["group_weighted_means"]["applicable_checks"], 50)
        self.assertEqual(summary["groups"], 2)

    def test_unknown_and_inapplicable_are_not_positive_group_votes(self):
        self.assertEqual(group_outcome(["MATCH", "UNKNOWN"]), "UNKNOWN")
        self.assertEqual(group_outcome(["MATCH", "NOT_EVALUATED"]), "NOT_EVALUATED")
        self.assertEqual(group_outcome(["MATCH", "COUNTEREXAMPLE"]), "COUNTEREXAMPLE")
        self.assertEqual(group_outcome(["NOT_APPLICABLE"]), "NOT_APPLICABLE")

    def test_paired_group_bootstrap_and_fixed_denominator(self):
        before = [metric_row("a", "g1", 1), metric_row("b", "g1", 3), metric_row("c", "g2", 7)]
        after = [metric_row("a", "g1", 4), metric_row("b", "g1", 6), metric_row("c", "g2", 10)]
        result = paired_comparison(before, after, interval=True, bootstrap_replicates=40)
        self.assertEqual(result["group_weighted_delta"]["applicable_checks"], 3)
        self.assertEqual(result["conditional_95_percent_bootstrap"]["applicable_checks"], [3, 3])
        with self.assertRaisesRegex(ValueError, "same cohort"):
            paired_comparison(before, after[:2])
        after[0].update(status="FAILED", metrics=None)
        failed = paired_comparison(before, after, interval=True)
        self.assertEqual(failed["failed_pairs"], 1)
        self.assertIsNone(failed["group_weighted_delta"])

    def test_one_protocol_cannot_claim_release_twice(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            claim_release(root / "ledger.json", root / "out", {"protocol_version": "fixture"})
            with self.assertRaises(FileExistsError):
                claim_release(root / "ledger.json", root / "new-out", {"protocol_version": "fixture"})

    def test_history_does_not_infer_observed_status_from_old_values(self):
        from hybridguard_agent.scripts.run_mtc_p6_history import legacy_row
        with self.assertRaisesRegex(ValueError, "explicit App177"):
            legacy_row({"android_native_data": {"device_model": "M"}})
        payload = legacy_payload(build_paired_evidence(row(), "App177")["projection"])
        adapted = legacy_row(payload)
        self.assertEqual(len(adapted["features"]), 177)
        self.assertFalse(any(p.startswith("browser.") for p in adapted["features"]))
        self.assertEqual(analyze_paired244_record(adapted, input_view="App177")["status"], "completed")


class P6ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.snapshot = self.root / "plan", self.root / "snapshot"
        self.plan.mkdir(); self.snapshot.mkdir()
        self.rows = [row(), row("reserved", "reserved_validation", "reserved-group", 2)]
        self.metas = [{"sample_id": r["sample_id"], "source_view": "paired_244", **r["_p2"],
                       "profile": r["profile"], "app_payload_sha256": r["app"]["payload_sha256"],
                       "browser_payload_sha256": r["browser"]["payload_sha256"]} for r in self.rows]
        write_json(self.plan / "reserved_validation_LOCK.json", {"status": "LOCKED"})
        self.release = self.root / "release.json"
        self.guard = {"status": "FROZEN_FOR_FIXED_EVALUATION", "protocol_frozen": True, "rules_frozen": True,
                      "exposure_disclosed": True, "plan_dir": str(self.plan), "snapshot_dir": str(self.snapshot)}
        write_json(self.release, self.guard)
        self.save()

    def save(self):
        (self.plan / "sample_registry.jsonl").write_text("".join(json.dumps(r) + "\n" for r in self.metas))
        (self.snapshot / "paired_244.jsonl").write_text("".join(json.dumps(r) + "\n" for r in self.rows))

    def load(self, split):
        return load_p6_rows(self.plan, self.snapshot, split, "primary_representative", self.release)

    def test_unselected_reserved_features_are_not_decoded(self):
        with (self.snapshot / "paired_244.jsonl").open("w") as f:
            f.write(json.dumps(self.rows[0]) + "\nINVALID_RESERVED_FEATURE_JSON\n")
        self.assertEqual(len(self.load("discovery")), 1)

    def test_reserved_requires_complete_release_before_read(self):
        self.guard["rules_frozen"] = False
        write_json(self.release, self.guard)
        (self.snapshot / "paired_244.jsonl").write_text("INVALID_UNREAD_INPUT\n")
        with self.assertRaisesRegex(ValueError, "frozen rules/protocol"):
            self.load("reserved_validation")

    def test_p6_release_preserves_historical_p2_guard(self):
        result = self.load("reserved_validation")
        self.assertEqual([r["sample_id"] for r in result], ["reserved"])
        self.assertEqual(json.loads((self.plan / "reserved_validation_LOCK.json").read_text())["status"], "LOCKED")
        from hybridguard_agent.research.mtc_p3_data import load_split_records
        with self.assertRaisesRegex(ValueError, "reserved validation is locked"):
            load_split_records(self.plan, "reserved_validation")

    def test_cross_split_groups_rejected_before_data_decode(self):
        self.metas[1]["group_id"] = self.metas[0]["group_id"]
        self.save()
        (self.snapshot / "paired_244.jsonl").write_text("INVALID_UNREAD_INPUT\n")
        with self.assertRaisesRegex(ValueError, "cross-split"):
            self.load("discovery")

    def test_source_binding_mismatch_is_not_silently_skipped(self):
        self.rows[1]["app"]["payload_sha256"] = "wrong-binding"
        self.save()
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            self.load("reserved_validation")


if __name__ == "__main__":
    unittest.main()
