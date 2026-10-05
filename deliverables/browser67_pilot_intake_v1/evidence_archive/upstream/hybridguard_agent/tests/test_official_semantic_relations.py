"""Contract tests for official-document-derived semantic relations."""

from __future__ import annotations

import copy
import unittest

from hybridguard_agent.adapters.official_kb_adapter import load_official_cards
from hybridguard_agent.official_semantics.evaluator import (
    evaluate_official_semantics,
    load_semantic_catalog,
)
from hybridguard_agent.tests.test_two_source_rule_classification import (
    ATTACK_UA,
    payload,
)


def complete_payload(session_id: str) -> dict[str, object]:
    record = payload(session_id)
    record["android_native_data"].update(  # type: ignore[union-attr]
        {
            "native_gpu_renderer": "Adreno (TM) 740",
            "egl_renderer": "Adreno (TM) 740",
        }
    )
    record["webview_data"]["webview_provider_major"] = 120  # type: ignore[index]
    record["web_data"].update(  # type: ignore[union-attr]
        {
            "webgl_vendor": "Qualcomm",
            "webgl_renderer": "ANGLE (Qualcomm, Adreno 740, OpenGL ES 3.2)",
        }
    )
    return record


def result_by_id(result: dict[str, object], relation_id: str) -> dict[str, object]:
    execution = result["relation_execution"]
    assert isinstance(execution, dict)
    rows = execution["relation_results"]
    assert isinstance(rows, list)
    return next(row for row in rows if row["relation_id"] == relation_id)


class OfficialSemanticRelationTests(unittest.TestCase):
    def test_catalog_covers_all_official_cards_and_only_compiles_reviewed_predicates(self) -> None:
        catalog = load_semantic_catalog()
        _, official_cards = load_official_cards()
        covered_cards = {
            card_id
            for relation in catalog["relations"]
            for card_id in relation["official_card_refs"]
        }
        self.assertEqual(covered_cards, {card["source_card_id"] for card in official_cards})
        compiled = [
            relation
            for relation in catalog["relations"]
            if relation["executable_status"] == "compiled_v1"
        ]
        self.assertEqual(len(catalog["relations"]), 22)
        self.assertEqual(len(compiled), 9)
        self.assertTrue(all(relation["predicate_id"] for relation in compiled))
        self.assertTrue(
            all(
                relation["predicate_id"] is None
                for relation in catalog["relations"]
                if relation["executable_status"] != "compiled_v1"
            )
        )

    def test_consistent_baseline_has_no_research_semantic_alert(self) -> None:
        result = evaluate_official_semantics(complete_payload("baseline"))
        decision = result["decision"]
        self.assertFalse(decision["research_semantic_alert"])
        self.assertEqual(decision["decision_status"], "completed")
        self.assertEqual(decision["strong_inconsistency_relation_ids"], [])
        self.assertTrue(
            all(
                row["outcome"] == "consistent"
                for row in result["relation_execution"]["relation_results"]
            )
        )

    def test_desktop_cdp_surface_triggers_host_surface_relation(self) -> None:
        attacked = complete_payload("cdp-active")
        attacked["web_data"]["user_agent"] = ATTACK_UA  # type: ignore[index]
        attacked["web_data"]["platform"] = "Win32"  # type: ignore[index]
        result = evaluate_official_semantics(attacked)

        self.assertTrue(result["decision"]["research_semantic_alert"])
        self.assertIn(
            "OFFDER-UA-001",
            result["decision"]["strong_inconsistency_relation_ids"],
        )
        self.assertEqual(result_by_id(result, "OFFDER-UA-001")["outcome"], "inconsistent")
        self.assertEqual(
            result_by_id(result, "OFFDER-OS-001")["outcome"],
            "unknown",
            "A UA without an Android token must not be treated as a parsed version mismatch.",
        )

    def test_explicit_direct3d_surface_triggers_gpu_relation(self) -> None:
        attacked = complete_payload("stealth-active")
        attacked["web_data"]["webgl_vendor"] = "Google Inc. (NVIDIA)"  # type: ignore[index]
        attacked["web_data"]["webgl_renderer"] = (  # type: ignore[index]
            "ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"
        )
        result = evaluate_official_semantics(attacked)

        self.assertTrue(result["decision"]["research_semantic_alert"])
        self.assertEqual(result_by_id(result, "OFFDER-GPU-001")["outcome"], "inconsistent")

    def test_angle_or_nvidia_without_windows_direct3d_is_not_a_gpu_violation(self) -> None:
        legitimate = complete_payload("android-angle")
        legitimate["web_data"]["webgl_vendor"] = "NVIDIA Corporation"  # type: ignore[index]
        legitimate["web_data"]["webgl_renderer"] = (  # type: ignore[index]
            "ANGLE (NVIDIA Tegra X1, OpenGL ES 3.2)"
        )
        result = evaluate_official_semantics(legitimate)

        self.assertEqual(result_by_id(result, "OFFDER-GPU-001")["outcome"], "consistent")
        self.assertFalse(result["decision"]["research_semantic_alert"])

    def test_debug_cleartext_is_context_not_alert(self) -> None:
        development = complete_payload("development")
        development["webview_data"]["is_debuggable"] = True  # type: ignore[index]
        development["webview_data"]["is_cleartext_traffic_permitted"] = True  # type: ignore[index]
        result = evaluate_official_semantics(development)

        self.assertEqual(
            result_by_id(result, "OFFDER-DEVCONFIG-001")["outcome"],
            "context_observed",
        )
        self.assertFalse(result["decision"]["research_semantic_alert"])
        self.assertEqual(result["decision"]["decision_status"], "context_observed")

    def test_wrapped_featureapp_payload_and_unavailable_state_are_respected(self) -> None:
        unavailable = complete_payload("wrapped")
        unavailable["webview_data"]["jsbridge_injected"] = False  # type: ignore[index]
        wrapped = {
            "canonical_received_payload": unavailable,
            "field_status": {
                "fields": {"webview_data.jsbridge_injected": "permission_denied"}
            },
        }
        result = evaluate_official_semantics(wrapped)

        self.assertEqual(result_by_id(result, "OFFDER-BRIDGE-001")["outcome"], "unavailable")
        self.assertNotIn(
            "OFFDER-BRIDGE-001",
            result["decision"]["strong_inconsistency_relation_ids"],
        )

        observed = copy.deepcopy(wrapped)
        observed["field_status"] = {"fields": {}}
        observed_result = evaluate_official_semantics(observed)
        self.assertEqual(
            result_by_id(observed_result, "OFFDER-BRIDGE-001")["outcome"],
            "inconsistent",
        )

    def test_attack_labels_and_tool_metadata_do_not_change_semantic_decision(self) -> None:
        baseline = complete_payload("metadata-boundary")
        labeled = copy.deepcopy(baseline)
        labeled["attack"] = {
            "tool_name": "must-not-be-a-decision-input",
            "execution_status": "verified_success",
            "feature_effect_status": "observed",
        }
        labeled["pair"] = {"pair_role": "attack"}
        labeled["label"] = "attack"

        baseline_result = evaluate_official_semantics(baseline, sample_id="same")
        labeled_result = evaluate_official_semantics(labeled, sample_id="same")
        self.assertEqual(baseline_result["decision"], labeled_result["decision"])
        self.assertEqual(
            baseline_result["relation_execution"]["relation_results"],
            labeled_result["relation_execution"]["relation_results"],
        )
        self.assertEqual(
            baseline_result["relation_execution"]["evidence_hash"],
            labeled_result["relation_execution"]["evidence_hash"],
        )


if __name__ == "__main__":
    unittest.main()
