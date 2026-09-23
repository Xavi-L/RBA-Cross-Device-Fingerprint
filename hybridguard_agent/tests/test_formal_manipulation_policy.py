"""S04 static and synthetic-only integration/contract boundary tests."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.research.manipulation_eval import provenance_revision as v2
from hybridguard_agent.research.manipulation_eval.contract import load_contract, VERSION, CONFIG_REF, POLICY_REF
from hybridguard_agent.research.manipulation_eval.definitions import variant_plan
from hybridguard_agent.research.manipulation_eval.reporting import relation_role_diagnostic
from hybridguard_agent.research.manipulation_eval.runner import worker
from hybridguard_agent.research.manipulation_eval.synthetic import fixtures, consistent_payload, empty_payload, put, MAP
from hybridguard_agent.research.manipulation_eval.verification import verify_policy_output
from hybridguard_agent.runtime.paired244 import analyze_paired244_record


def load():
    return load_contract(contract_version=VERSION, config_dir=CONFIG_REF, policy_path=Path(POLICY_REF) / "decision_policy.json")


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load()

    def run_payload(self, p, **kw):
        return worker(p, contract=self.c, condition_id=kw.pop("condition_id", "SRC-111"), **kw)

    def test_single_family_duplicate_rules_and_match_retention(self):
        result = self.run_payload(fixtures()[1]["payload"])
        self.assertEqual((result["risk"]["decision"], result["risk"]["alert_score"]), ("MANIPULATION_ALERT", 1))
        events = {r["rule_id"]: r for r in result["rule_events"]}
        self.assertEqual({rid for rid, e in events.items() if e["triggers_family"]}, {"NW-002", "OFFDER-OS-001"})
        self.assertTrue(events["NW-001"]["participates_in_risk"])
        self.assertEqual(events["NW-001"]["original_outcome"], "MATCH")
        self.assertEqual(result["risk"]["evaluated_family_count"], 5)

    def test_consistent_missing_inapplicable_invalid_have_distinct_decisions(self):
        for f in fixtures():
            with self.subTest(case=f["fixture_id"]):
                r = self.run_payload(f["payload"])
                self.assertEqual(r["risk"]["decision"], f["expected_decision"])
                self.assertEqual(r["risk"]["alert_score"], f["expected_score"])
                self.assertEqual(len(r["rule_events"]), 87)
        software = self.run_payload(fixtures()[3]["payload"])
        gpu = next(e for e in software["rule_events"] if e["rule_id"] == "NW-005")
        self.assertEqual(gpu["relation_applicability"]["status"], "NOT_APPLICABLE")
        self.assertIsNotNone(gpu["original_outcome"])

    def test_unknown_attribution_neither_vetoes_nor_becomes_attack_proof(self):
        r = self.run_payload(fixtures()[1]["payload"])
        self.assertEqual(r["risk"]["attribution_certainty"]["status"], "UNKNOWN")
        self.assertFalse(r["risk"]["attribution_certainty"]["attack_proven"])
        self.assertIsNone(r["risk"]["calibrated_attack_probability"])
        self.assertEqual(r["original_runtime"]["decision"]["attack_classification"], "NOT_EVALUATED")

    def test_complete_original_chain_not_single_relation_probe(self):
        p = consistent_payload()
        original = analyze_paired244_record(p, input_view="App177", catalog=self.c["catalog"])
        with patch.object(v2, "evaluate_contract", side_effect=AssertionError("not a runtime")), patch.object(v2, "_relation_probe", side_effect=AssertionError("not a runtime")):
            r = self.run_payload(p)
        self.assertEqual(r["execution_status"], "COMPLETED")
        for key in ("evidence_bundle", "rule_execution", "context_pack", "decision"):
            self.assertEqual(r["original_runtime"][key], original[key])
        self.assertEqual(sum(e["catalog_status"] == "ACTIVE" for e in r["rule_events"]), 57)
        self.assertEqual(len(r["original_runtime"]["context_pack"]["cards"]), 57)

    def test_all_seven_candidates_agree_with_original_predicates_on_common_domain(self):
        registry = {"scopes": list(self.c["scopes"].values()), "roles": list(self.c["roles"].values()), "bindings": list(self.c["bindings"].values())}
        checked = 0
        for f in v2.synthetic_cases(registry):
            if f["case"] not in {"consistent", "conflict"}:
                continue
            p = empty_payload()
            for section in ("features", "field_status", "field_quality"):
                p[section].update(f["payload"][section])
            result = self.run_payload(p)
            event = next(e for e in result["rule_events"] if e["rule_id"] == f["rule_id"])
            probe = v2.evaluate_contract(f["rule_id"], p, registry)
            self.assertEqual(event["original_outcome"], probe["relation_result"]["outcome"])
            self.assertTrue(event["participates_in_risk"])
            checked += 1
        self.assertEqual(checked, 14)

    def test_sources_share_gates_C_and_cannot_duplicate_families(self):
        common = None
        for cid in sorted(self.c["conditions"]):
            r = self.run_payload(fixtures()[1]["payload"], condition_id=cid)
            axes = [(e["rule_id"], e["relation_applicability"], e["risk_candidate_eligibility"]) for e in r["rule_events"]]
            if common is None:
                common = axes
            self.assertEqual(axes, common)
            bits = cid[-3:]
            self.assertEqual(r["risk"]["decision"], "MANIPULATION_ALERT" if bits[0] == "1" or bits[2] == "1" else "INSUFFICIENT_EVIDENCE")
            self.assertEqual(r["risk"]["alert_score"], 1 if bits[0] == "1" or bits[2] == "1" else 0)
            self.assertEqual(r["risk"]["eligible_family_count"], 5 if bits[2] == "1" else 2 if bits[0] == "1" else 0)
            for e in r["rule_events"]:
                if e["provenance_group"] in {"H", "C"}:
                    self.assertFalse(e["participates_in_risk"])

    def test_legal_custom_UA_stays_conflict_but_not_eligible(self):
        p = fixtures()[1]["payload"]
        put(p, "webview_data.settings_user_agent", "legitimate custom agent")
        r = self.run_payload(p)
        e = next(e for e in r["rule_events"] if e["rule_id"] == "NW-002")
        self.assertEqual(e["original_outcome"], "COUNTEREXAMPLE")
        self.assertEqual(e["relation_applicability"]["status"], "SUPPORTED")
        self.assertEqual(e["risk_candidate_eligibility"]["status"], "NOT_ELIGIBLE")
        self.assertEqual(r["risk"]["decision"], "NO_ALERT")
        self.assertTrue(r["risk"]["partial_coverage"])

    def test_reduction_Dalvik_masking_software_and_sentinel_boundaries(self):
        for ua in ("Mozilla/5.0 (Linux; Android 10; K; wv) Chrome/140.0.0.0", v2.SYSTEM_UA):
            p = put(consistent_payload(), "web_data.user_agent", ua)
            r = self.run_payload(p)
            for e in r["rule_events"]:
                if e["rule_id"] in {"NW-001", "NW-002", "OFFDER-OS-001"}:
                    self.assertEqual(e["relation_applicability"]["status"], "NOT_APPLICABLE")
                    self.assertFalse(e["participates_in_risk"])
        p = put(consistent_payload(), "web_data.webgl_renderer", "masked")
        put(p, "web_data.hardware_concurrency", 0)
        p["field_quality"][MAP["web_data.hardware_concurrency"]] = "ambiguous_sentinel"
        r = self.run_payload(p)
        self.assertEqual(r["execution_status"], "COMPLETED")
        e = next(e for e in r["rule_events"] if e["rule_id"] == "NW-005")
        self.assertEqual(e["relation_applicability"]["status"], "UNKNOWN")
        for value in (float("nan"), float("inf")):
            self.assertEqual(self.run_payload(put(consistent_payload(), "web_data.hardware_concurrency", value))["risk"]["decision"], "FAILED")

    def test_original_verifier_failure_is_FAILED_with_preserved_outcomes(self):
        with patch("hybridguard_agent.research.manipulation_eval.runner.verify_paired_output", return_value={"valid": False, "errors": ["synthetic_fault"]}):
            r = self.run_payload(fixtures()[1]["payload"])
        self.assertEqual(r["risk"]["decision"], "FAILED")
        self.assertIsNone(r["risk"]["alert_score"])
        self.assertTrue(any(e["original_outcome"] == "COUNTEREXAMPLE" for e in r["rule_events"]))
        self.assertFalse(any(e["participates_in_risk"] for e in r["rule_events"]))
        with patch("hybridguard_agent.research.manipulation_eval.runner.execute_paired_rules", side_effect=RuntimeError("synthetic runtime fault")):
            r = self.run_payload(consistent_payload())
        self.assertEqual(r["risk"]["decision"], "FAILED")
        self.assertTrue(all(e["original_outcome"] is None for e in r["rule_events"]))

    def test_gate_or_risk_verifier_exception_records_FAILED_without_reentering_gate(self):
        for target in ("hybridguard_agent.research.manipulation_eval.policy.gate_axes",
                       "hybridguard_agent.research.manipulation_eval.runner.verify_policy_output"):
            with patch(target, side_effect=RuntimeError("synthetic gate/verifier failure")):
                r = self.run_payload(fixtures()[1]["payload"])
            self.assertEqual(r["risk"]["decision"], "FAILED")
            self.assertFalse(any(e["participates_in_risk"] for e in r["rule_events"]))
            self.assertEqual(sum(e["catalog_status"] == "ACTIVE" for e in r["rule_events"]), 57)
            self.assertTrue(any(e["original_outcome"] == "COUNTEREXAMPLE" for e in r["rule_events"]))

    def test_tampered_outcome_reference_gate_or_score_fails_independent_verifier(self):
        original = self.run_payload(consistent_payload())
        for kind in ("outcome", "reference", "gate", "score", "attribution"):
            r = copy.deepcopy(original)
            if kind == "outcome": r["original_runtime"]["rule_execution"]["rule_results"][0]["outcome"] = "COUNTEREXAMPLE"
            if kind == "reference": r["original_runtime"]["rule_execution"]["rule_results"][0]["used_fields"] = ["label.attack"]
            if kind == "gate": r["rule_events"][0]["relation_applicability"]["status"] = "UNKNOWN"
            if kind == "score": r["risk"]["alert_score"] = 10
            if kind == "attribution": r["risk"]["attribution_certainty"]["attack_proven"] = True
            result = verify_policy_output(r["original_runtime"], r["rule_events"], r["risk"], self.c, condition_id="SRC-111", catalog=self.c["catalog"])
            self.assertFalse(result["valid"], kind)

    def test_legacy19_preserves_original_predicate_and_diagnostic_role(self):
        p = put(consistent_payload(), "android_native_data.sensor_total_count", 0)
        put(p, "webview_data.jsbridge_injected", True)
        r = self.run_payload(p, method="legacy19_v2")
        es = {e["rule_id"]: e for e in r["rule_events"]}
        self.assertEqual(len(es), 19)
        self.assertEqual(es["CORE-002"]["original_result"]["predicate"], "sensor_or_jsbridge_absent_v1")
        self.assertEqual(es["CORE-002"]["original_outcome"], "COUNTEREXAMPLE")
        self.assertFalse(es["CORE-002"]["participates_in_risk"])
        self.assertFalse(es["OFFDER-WEBVIEW-001"]["participates_in_risk"])
        self.assertEqual(r["risk"]["decision"], "NO_ALERT")
        self.assertEqual(r["risk"]["eligible_family_count"], 2)

    def test_explicit_v2_loading_rejects_mixed_missing_and_partial_configs(self):
        with patch.object(v2, "build_revision", side_effect=AssertionError("No S03-R rerun")):
            self.assertEqual(load()["version"], VERSION)
        with self.assertRaises(ValueError): load_contract(contract_version="v1", config_dir=CONFIG_REF, policy_path=Path(POLICY_REF) / "decision_policy.json")
        with self.assertRaises((FileNotFoundError, ValueError)): load_contract(contract_version=VERSION, config_dir="hybridguard_agent/config/formal_manipulation_v1", policy_path=Path(POLICY_REF) / "decision_policy.json")
        for failure in ("version", "missing", "partial", "candidate", "condition"):
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "v2"; shutil.copytree(CONFIG_REF, target)
                p = target / ("source_conditions.json" if failure == "condition" else "decision_roles.json")
                doc = json.loads(p.read_text())
                if failure == "version": doc["contract_version"] = "old-v1"
                if failure == "partial": doc["roles"].pop()
                if failure == "candidate": doc["roles"][0]["decision_role"] = "alert_candidate"
                if failure == "condition": doc["conditions"][0]["common_gate_ids"] = []
                p.write_text(json.dumps(doc))
                if failure == "missing": p.unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    load_contract(contract_version=VERSION, config_dir=target, policy_path=Path(POLICY_REF) / "decision_policy.json")

    def test_threshold_changes_rejected_and_static_matrix_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "policy.json"; policy = copy.deepcopy(self.c["policy"]); policy["threshold"] = 2;p.write_text(json.dumps(policy))
            with self.assertRaises(ValueError): load_contract(contract_version=VERSION, config_dir=CONFIG_REF, policy_path=p)
        plan = variant_plan(self.c)
        self.assertEqual(len(plan["variants"]), 80)
        self.assertEqual(plan, json.loads((Path(POLICY_REF) / "variant_plan.json").read_text()))
        self.assertEqual(plan["four_source_mapping"]["EO"], "SRC-111")

    def test_current_relation_projection_is_saved_diagnostic_not_an_ungated_risk_baseline(self):
        p = put(consistent_payload(), "web_data.user_agent", "Mozilla/5.0 (Linux; Android 10; K; wv) Chrome/140.0.0.0")
        r = self.run_payload(p)
        d = relation_role_diagnostic(r["rule_events"])
        self.assertIn("NW-002", d["original_candidate_conflict_rules"])
        self.assertIn("NW-002", [e["rule_id"] for e in d["suppressed_by_v2"]])
        self.assertEqual(r["risk"]["decision"], "NO_ALERT")
        self.assertNotIn("decision", d)
        self.assertTrue(d["not_a_third_independent_detector"])


if __name__ == "__main__":
    unittest.main()
