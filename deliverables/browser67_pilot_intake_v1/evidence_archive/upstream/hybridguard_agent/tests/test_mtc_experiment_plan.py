import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hybridguard_agent.scripts import build_mtc_experiment_plan as plan


FIELD = "app.web_data.navigator_layer.hardware_concurrency"


def sample(index, model=None, os="13", install=None, session=None, view="paired_244"):
    return {"sample_id": f"sample-{index}", "view": view, "source_line": index + 1,
            "source_file": "/fixture/" + view + ".jsonl", "app_raw_line": index + 1,
            "app_session_id": session or f"session-{index}",
            "app_payload_sha256": hashlib.sha256(f"app-{index}".encode()).hexdigest(),
            "browser_payload_sha256": hashlib.sha256(f"browser-{index}".encode()).hexdigest() if view == "paired_244" else None,
            "profile": {"manufacturer": "fixture", "model": model or f"model-{index}", "android_release": os,
                        "android_api": 33, "collector_install_id": install or f"install-{index}"},
            "collector_version_code": 11, "browser_package": "fixture.browser", "qc_status": "passed", "usable_fields": [FIELD]}


def fact(row, phase="baseline"):
    active = phase == "attack_active"
    return {"fact_version": "mtc-experiment-fact-v2", **{k: row[k] for k in ("sample_id", "app_session_id", "app_payload_sha256", "browser_payload_sha256")},
            "source_kind": "controlled_intervention_record", "label_status": "verified", "manipulation_present": active,
            "reference_status": "unknown" if active else "no_active_intervention_recorded",
            "stable_identity_key": "reviewed-device", "identity_scope": "physical_device", "identity_status": "verified",
            "scenario_id": "scenario-a", "scenario_phase": phase, "scenario_repetition": 1, "attack_family": "fixture-change" if active else None,
            "phase_started_at_utc": "2026-09-22T02:01:00Z" if active else "2026-09-22T02:00:00Z",
            "execution_status": "succeeded" if active else "not_applicable", "field_effect_status": "observed" if active else "no_configured_change",
            "observable_target_fields": [FIELD] if active else [], "evidence_refs": ["evidence.txt"]}


def fixture_snapshot(root, rows):
    snapshot = root / "snapshot"
    snapshot.mkdir()
    counts = {}
    selection = []
    for view in plan.VIEWS:
        output = []
        for row in rows:
            if row["view"] != view:
                continue
            field_count = 244 if row["browser_payload_sha256"] else 177
            fields = [FIELD] + [f"app.fixture.field_{n}" for n in range(field_count - 1)]
            output.append({"sample_id": row["sample_id"], "record_schema_version": "hybridguard-mtc-observation-v2",
                "dataset_view": view, "dataset_role": "development_qc_only", "label_status": "unlabeled",
                "profile": row["profile"], "app": {"session_id": row["app_session_id"], "payload_sha256": row["app_payload_sha256"], "collector_version_code": 11},
                "browser": {"payload_sha256": row["browser_payload_sha256"], "resolved_browser_package": row["browser_package"]},
                "qc": {"status": "passed"}, "feature_count": field_count, "pair": {"pair_status": "completed"},
                "field_status": {f: "observed" for f in fields}, "field_quality": {f: "observed_value" for f in fields},
                "source_refs": {"app_raw_line": row["app_raw_line"]}})
            selection.append({"source_line": row["app_raw_line"], "sample_id": row["sample_id"], "destination": view})
        counts[view] = len(output)
        plan.write_jsonl(snapshot / (view + ".jsonl"), output)
    plan.write_jsonl(snapshot / "selection_audit.jsonl", selection)
    plan.write_json(snapshot / "manifest.json", {"dataset_manifest_version": "mtc-paired244-snapshot-v2", "p1_status": "COMPLETE",
        "dataset_role": "development_qc_only", "label_status": "unlabeled", "view_counts": counts,
        "source_rows": {"raw_expanded_payloads": len(rows)}, "source_cutoff_utc": "2026-09-22T08:39:43Z"})
    return snapshot


class MtcExperimentPlanTests(unittest.TestCase):
    def setUp(self):
        self.protocol = plan.load_protocol(plan.DEFAULT_PROTOCOL)

    def test_transitive_model_install_session_links_never_cross_splits(self):
        rows = [sample(0, "A", os="12"), sample(1, "A", os="13", install="bridge"),
                sample(2, "B", install="bridge", session="shared-session"),
                sample(3, "C", session="shared-session"), sample(4, "D")]
        groups, membership = plan.build_groups(rows, {}, self.protocol)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len({membership[r["sample_id"]] for r in rows[:4]}), 1)
        self.assertTrue(any(g["multi_model_link"] for g in groups))
        self.assertTrue(all(g["physical_device_count"] is None for g in groups))

    def test_order_and_feature_availability_do_not_select_split_or_representative(self):
        rows = [sample(8, "A"), sample(1, "A"), sample(4, "A", os="14"), sample(3, "B")]
        g1, m1 = plan.build_groups(rows, {}, self.protocol)
        shuffled = copy.deepcopy(list(reversed(rows)))
        shuffled[0]["usable_fields"] = []
        g2, m2 = plan.build_groups(shuffled, {}, self.protocol)
        self.assertEqual((g1, m1), (g2, m2))
        self.assertEqual(plan.representative_ids(rows, {}), {"sample-1", "sample-4", "sample-3"})

    def test_missing_facts_remain_unknown_and_reserved_input_export_is_denied(self):
        rows = [sample(i) for i in range(20)]
        _, membership = plan.build_groups(rows, {}, self.protocol)
        inv = plan.build_inventory(rows, membership, {}, plan.representative_ids(rows, {}), set())
        self.assertTrue(all(r["label_status"] == "unknown" and r["manipulation_present"] is None for r in inv))
        self.assertTrue(all(not r["metric_eligible"] and r["physical_device_identity"] == "unknown" for r in inv))
        with self.assertRaisesRegex(ValueError, "remain locked"):
            plan.select_task_inputs(rows, inv, "reserved_rule_validation")
        allowed = plan.select_task_inputs(rows, inv, "rule_discovery")
        self.assertTrue(allowed)
        self.assertTrue(all(set(r) == {"sample_id", "source_file", "source_line", "app_payload_sha256", "browser_payload_sha256"} for r in allowed))

    def test_exact_both_surface_fact_binding_and_independent_evidence_required(self):
        row = sample(0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence.txt").write_text("synthetic unit-test evidence only")
            valid = fact(row)
            plan.validate_fact(valid, row, root)
            for key, value in [("browser_payload_sha256", "a" * 64), ("app_payload_sha256", "b" * 64),
                               ("source_kind", "rule_alert"), ("evidence_refs", []), ("manipulation_present", 0),
                               ("phase_started_at_utc", "2026-09-22T02:00:00")]:
                with self.subTest(key=key):
                    invalid = {**valid, key: value}
                    with self.assertRaises(ValueError):
                        plan.validate_fact(invalid, row, root)

    def test_two_state_scenario_links_models_and_needs_time_identity_and_effect(self):
        rows = [sample(0, "A"), sample(1, "B")]
        facts = {rows[0]["sample_id"]: fact(rows[0]), rows[1]["sample_id"]: fact(rows[1], "attack_active")}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence.txt").write_text("synthetic fixture only")
            for row in rows:
                plan.validate_fact(facts[row["sample_id"]], row, root)
            _, membership = plan.build_groups(rows, facts, self.protocol)
            self.assertEqual(membership["sample-0"], membership["sample-1"])
            scenarios, qualified = plan.build_scenarios(rows, facts, membership)
            self.assertEqual(qualified, {"sample-0", "sample-1"})
            self.assertEqual(scenarios[0]["data_contract_status"], "QUALIFIED")
            self.assertFalse(scenarios[0]["metric_eligible"])
            facts["sample-1"]["phase_started_at_utc"] = "2026-09-22T01:00:00Z"
            self.assertFalse(plan.build_scenarios(rows, facts, membership)[1])
            facts["sample-1"]["field_effect_status"] = "not_observed"
            with self.assertRaisesRegex(ValueError, "observable field-effect"):
                plan.validate_fact(facts["sample-1"], rows[1], root)

    def test_partial_phase_and_incomplete_scenario_never_qualify_detection(self):
        rows = [sample(0), sample(1, view="partial")]
        facts = {rows[0]["sample_id"]: fact(rows[0]), rows[1]["sample_id"]: fact(rows[1], "attack_active")}
        _, membership = plan.build_groups(rows, facts, self.protocol)
        scenarios, qualified = plan.build_scenarios(rows, facts, membership)
        self.assertFalse(qualified)
        self.assertIn("both_phases_require_qc_paired244", scenarios[0]["reasons"])
        scenarios, qualified = plan.build_scenarios(rows, {"sample-0": facts["sample-0"]}, membership)
        self.assertFalse(qualified)
        self.assertIn("missing_or_ambiguous_two_state_phases", scenarios[0]["reasons"])

    def test_coverage_reports_absent_strata_instead_of_omitting_them(self):
        rows = [sample(0)]
        _, membership = plan.build_groups(rows, {}, self.protocol)
        coverage = plan.coverage(rows, membership, {"sample-0"})
        api = [r for r in coverage if r["dimension"] == "android_api"]
        self.assertEqual(len(api), 3)
        self.assertEqual(sum(r["paired_samples"] == 0 for r in api), 2)

    def test_candidate_support_floor_is_group_based_and_fixed_before_mining(self):
        evidence = {"discovery_groups": 30, "development_groups": 10, "discovery_manufacturers": 3, "development_manufacturers": 2}
        self.assertTrue(plan.empirical_support_floor_met("global_empirical", evidence, self.protocol))
        self.assertFalse(plan.empirical_support_floor_met("global_empirical", {**evidence, "discovery_groups": 29}, self.protocol))
        self.assertFalse(plan.empirical_support_floor_met("global_empirical", {**evidence, "development_manufacturers": 1}, self.protocol))
        with self.assertRaises(ValueError):
            plan.empirical_support_floor_met("global_empirical", {"session_count": 1000}, self.protocol)

    def test_end_to_end_counts_frozen_outputs_and_no_label_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [sample(i) for i in range(15)]
            rows += [sample(15, "model-0", view="app_only_177"), sample(16, "model-1", view="repeated_observations")]
            snapshot = fixture_snapshot(root, rows)
            output = root / "out"
            result = plan.build_plan(snapshot, output)
            self.assertEqual(result["observations"], 17)
            self.assertEqual(result["primary_model_os_representatives"], 15)
            self.assertEqual(result["leakage_groups"], 15)
            self.assertEqual(result["fact_sidecar_rows"], 0)
            self.assertFalse(result["detection_data_prerequisites_met"])
            self.assertFalse((output / "reserved_validation_inputs.jsonl").exists())
            registry = [r for _, r in plan.read_jsonl(output / "sample_registry.jsonl")]
            self.assertEqual(len(registry), 17)
            self.assertTrue(all(r["manipulation_present"] is None for r in registry))
            with self.assertRaisesRegex(ValueError, "new directory"):
                plan.build_plan(snapshot, output)
            manifest = plan.read_json(snapshot / "manifest.json")
            manifest["view_counts"]["paired_244"] += 1
            plan.write_json(snapshot / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "count drifted"):
                plan.build_plan(snapshot, root / "bad")
            self.assertFalse((root / "bad").exists())


if __name__ == "__main__":
    unittest.main()
