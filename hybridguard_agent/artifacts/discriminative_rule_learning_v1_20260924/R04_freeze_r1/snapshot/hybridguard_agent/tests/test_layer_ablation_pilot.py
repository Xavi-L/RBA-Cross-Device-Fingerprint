"""Boundaries that make a layer ablation interpretable, without model fitting."""
import copy
import unittest

from hybridguard_agent.scripts.run_layer_ablation_pilot import (
    GROUPS, NATIVE, HOST, WEB, compare_stages, evaluate_view, mask_payload,
    load_predicate_registry, load_semantic_catalog,
)
from hybridguard_agent.official_semantics.evaluator import evaluate_official_semantics
from hybridguard_agent.rules.executor import execute_deterministic_rules
from hybridguard_agent.evidence.extractor import build_evidence_bundle_v2
from hybridguard_agent.tests.test_official_semantic_relations import complete_payload
from hybridguard_agent.tests.test_two_source_rule_classification import ATTACK_UA


class LayerAblationPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_semantic_catalog()
        cls.registry = load_predicate_registry()

    def evaluate(self, payload, group):
        return evaluate_view(payload, GROUPS[group], catalog=self.catalog, registry=self.registry)

    def test_wrapped_metadata_and_ablated_layers_cannot_affect_decisions(self):
        original = complete_payload("baseline")
        wrapped = {"payload": original, "field_status": {"fields": {f"{WEB}.user_agent": "observed"}},
                   "attack": {"tool_name": "secret-label"}, "pair_role": "attack_active"}
        saved = copy.deepcopy(wrapped)
        masked = mask_payload(wrapped, (WEB,))
        self.assertNotIn(NATIVE, masked)
        self.assertNotIn(HOST, masked)
        self.assertNotIn("attack", masked)
        self.assertNotIn("session_id", masked)
        self.assertEqual(wrapped, saved)
        first = self.evaluate(wrapped, "app_web67")
        wrapped["payload"][NATIVE]["os_version"] = "99"
        wrapped["payload"][HOST]["jsbridge_injected"] = False
        wrapped["attack"]["tool_name"] = "changed-label"
        self.assertEqual(first, self.evaluate(wrapped, "app_web67"))

    def test_no_native_detector_is_not_a_negative_result(self):
        result = self.evaluate(complete_payload("base"), "native84")
        for lane in result.values():
            self.assertEqual(lane["status"], "NOT_EVALUATED")
            self.assertIsNone(lane["alert"])
        self.assertTrue(any(row["outcome"] == "not_evaluated" for row in result["device_mined"]["rules"]))

    def test_missing_web_ua_preserves_source_status_and_does_not_create_alert(self):
        p = complete_payload("base")
        p[WEB]["user_agent"] = ATTACK_UA
        p["collection_status"] = {"fields": {f"{WEB}.user_agent": "permission_denied"}}
        masked = mask_payload(p, (WEB,))
        self.assertEqual(masked["collection_status"], p["collection_status"])
        result = self.evaluate(p, "app_web67")["device_mined"]
        rule = next(row for row in result["rules"] if row["id"] == "WVWEB-004")
        self.assertEqual(rule["outcome"], "unavailable")
        self.assertFalse(rule["alert"])

    def test_full_view_preserves_both_frozen_evaluators(self):
        p = complete_payload("active")
        p[WEB]["user_agent"] = ATTACK_UA
        result = self.evaluate(p, "app177")
        existing = execute_deterministic_rules(build_evidence_bundle_v2(p))
        semantic = evaluate_official_semantics(p)
        self.assertEqual(result["device_mined"]["matched_rule_ids"], existing["matched_rule_ids"])
        self.assertEqual(result["official_derived"]["matched_rule_ids"], semantic["decision"]["strong_inconsistency_relation_ids"])
        # collector_app is shared schema context, not an ablated fourth layer.
        host = self.evaluate(p, "webview_host26")["official_derived"]
        self.assertIn("OFFDER-BRIDGE-001", host["assessed_alert_rule_ids"])

    def test_unknown_to_hit_is_not_reported_as_observed_negative_to_alert(self):
        baseline = complete_payload("base")
        baseline[HOST].pop("jsbridge_injected")
        active = complete_payload("active")
        active[HOST]["jsbridge_injected"] = False
        before = self.evaluate(baseline, "webview_host26")["official_derived"]
        after = self.evaluate(active, "webview_host26")["official_derived"]
        result = compare_stages(before, after)
        self.assertFalse(result["new_alert_pair"])
        self.assertEqual(result["assessed_to_alert_rule_ids"], [])
        self.assertEqual(result["indeterminate_to_alert_rule_ids"], ["OFFDER-BRIDGE-001"])


if __name__ == "__main__":
    unittest.main()
