"""End-to-end contract test for the official semantic validation package."""

from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from hybridguard_agent.scripts.run_official_semantic_validation import (
    run_official_semantic_validation,
)
from hybridguard_agent.tests.test_official_semantic_relations import complete_payload
from hybridguard_agent.tests.test_two_source_rule_classification import write_jsonl
from hybridguard_agent.validation_inputs import resolve_attack_inputs


class OfficialSemanticValidationTests(unittest.TestCase):
    def test_writes_source_bounded_two_state_package_and_ignores_clean_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            normal_input = root / "normal.jsonl"
            normal = complete_payload("normal-session")
            write_jsonl(normal_input, [normal])

            baseline = complete_payload("baseline-session")
            active = copy.deepcopy(baseline)
            active["session_id"] = "active-session"
            active["web_data"]["webgl_vendor"] = "Google Inc. (NVIDIA)"  # type: ignore[index]
            active["web_data"]["webgl_renderer"] = (  # type: ignore[index]
                "ANGLE (NVIDIA GeForce RTX 3060 Direct3D11)"
            )
            post = complete_payload("post-session")

            attack_dir = root / "attack"
            attack_dir.mkdir()
            write_jsonl(attack_dir / "raw_payloads.jsonl", [baseline, active, post])
            manifest_path = attack_dir / "attack_sample_manifest_v1.jsonl"
            write_jsonl(
                manifest_path,
                [
                    {
                        "session_id": "baseline-session",
                        "pair": {"pair_id": "pair-1", "pair_role": "clean_pre"},
                        "attack": {},
                    },
                    {
                        "session_id": "active-session",
                        "pair": {"pair_id": "pair-1", "pair_role": "attack"},
                        "attack": {
                            "tool_name": "fixture-stealth",
                            "tool_version": "1.0",
                            "attack_family": "fingerprint_override",
                            "config_id": "gpu-direct3d",
                            "execution_status": "verified_success",
                            "feature_effect_status": "observed",
                            "observed_mutations": [
                                {
                                    "field_path": "web_data.webgl_renderer",
                                    "change_summary": "fixture Direct3D renderer",
                                }
                            ],
                        },
                    },
                    {
                        "session_id": "post-session",
                        "pair": {"pair_id": "pair-1", "pair_role": "clean_post"},
                        "attack": {},
                    },
                ],
            )

            output_dir = root / "out"
            result = run_official_semantic_validation(
                run_id="semantic-fixture",
                normal_input=normal_input,
                attack_manifests=[manifest_path],
                output_dir=output_dir,
            )

            self.assertEqual(result["protocol"]["states_compared"], ["baseline", "attack_active"])
            self.assertEqual(result["inputs"]["ignored_historical_post_count"], 1)
            self.assertEqual(
                result["official_derived_semantic_lane"]["compiled_relation_count"], 9
            )
            self.assertEqual(result["observed_results"]["normal_research_semantic_alert_count"], 0)
            self.assertEqual(
                result["observed_results"][
                    "baseline_no_alert_to_attack_active_alert_count"
                ],
                1,
            )

            pair = json.loads(
                (output_dir / "attack_semantic_pair_results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(
                pair["research_semantic_alert_transition"],
                "baseline_no_alert_to_attack_active_alert",
            )
            self.assertIn("OFFDER-GPU-001", pair["new_inconsistency_relation_ids"])
            self.assertEqual(
                pair["new_strong_inconsistency_relation_ids"], ["OFFDER-GPU-001"]
            )
            self.assertTrue(
                pair["all_new_strong_inconsistencies_have_direct_premise_change"]
            )
            gpu_premise_evidence = next(
                item
                for item in pair["new_inconsistency_direct_premise_evidence"]
                if item["relation_id"] == "OFFDER-GPU-001"
            )
            self.assertIn(
                "web_data.webgl_renderer",
                gpu_premise_evidence["direct_changed_premise_fields"],
            )
            self.assertNotIn("post-session", json.dumps(pair, ensure_ascii=False))
            self.assertNotIn("Direct3D11", json.dumps(pair, ensure_ascii=False))
            self.assertEqual(
                pair["feature_comparison"]["annotated_field_results"][0][
                    "annotation_status"
                ],
                "confirmed_by_direct_payload_comparison",
            )

            with (output_dir / "semantic_relation_summary.csv").open(
                encoding="utf-8"
            ) as handle:
                rows = list(csv.DictReader(handle))
            gpu = next(row for row in rows if row["relation_id"] == "OFFDER-GPU-001")
            self.assertEqual(gpu["baseline_to_active_new_inconsistency_count"], "1")
            display = next(
                row for row in rows if row["relation_id"] == "OFFDER-DISPLAY-001"
            )
            self.assertEqual(display["predicate_id"], "")
            self.assertEqual(
                json.loads(display["normal_outcome_counts"]), {"not_executed": 1}
            )

    def test_frozen_input_set_tags_cohort_and_validates_expected_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            normal_input = root / "normal.jsonl"
            write_jsonl(normal_input, [complete_payload("normal-session")])

            baseline = complete_payload("baseline-session")
            active = copy.deepcopy(baseline)
            active["session_id"] = "active-session"
            active["web_data"]["user_agent"] = (  # type: ignore[index]
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/127.0"
            )
            post = complete_payload("post-session")
            attack_dir = root / "accepted"
            attack_dir.mkdir()
            write_jsonl(attack_dir / "raw_payloads.jsonl", [baseline, active, post])
            manifest_path = attack_dir / "attack_sample_manifest_v1.jsonl"
            write_jsonl(
                manifest_path,
                [
                    {
                        "session_id": "baseline-session",
                        "pair": {"pair_id": "pair-1", "pair_role": "clean_pre"},
                        "attack": {},
                    },
                    {
                        "session_id": "active-session",
                        "pair": {"pair_id": "pair-1", "pair_role": "attack"},
                        "attack": {
                            "tool_name": "fixture-cdp",
                            "tool_version": "1.0",
                            "config_id": "ua-only",
                            "execution_status": "verified_success",
                            "feature_effect_status": "observed",
                        },
                    },
                    {
                        "session_id": "post-session",
                        "pair": {"pair_id": "pair-1", "pair_role": "clean_post"},
                        "attack": {},
                    },
                ],
            )
            excluded_path = root / "excluded" / "attack_sample_manifest_v1.jsonl"
            input_set = root / "input-set.json"
            input_set.write_text(
                json.dumps(
                    {
                        "schema_version": "official-semantic-attack-input-set-v1",
                        "input_set_id": "fixture-expanded",
                        "cohorts": [
                            {
                                "cohort_id": "new-fixture",
                                "label": "新增配置 fixture",
                                "relation_design_exposure": "not_inspected_before_semantic_catalog_freeze",
                                "acceptance_reference": "fixture-ledger",
                                "manifests": [str(manifest_path)],
                            }
                        ],
                        "excluded_new_manifests": [
                            {"path": str(excluded_path), "reason": "empty_fixture"}
                        ],
                        "expected_counts": {
                            "selected_manifest_count": 1,
                            "legacy_pair_count": 0,
                            "new_pair_count": 1,
                            "total_pair_count": 1,
                            "eligible_pair_count": 1,
                            "ignored_historical_post_count": 1,
                            "unique_tool_name_count": 1,
                            "unique_config_id_count": 1,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            output_dir = root / "out"
            result = run_official_semantic_validation(
                run_id="semantic-input-set-fixture",
                normal_input=normal_input,
                attack_input_set=input_set,
                output_dir=output_dir,
            )

            selection = result["inputs"]["attack_input_selection"]
            self.assertEqual(selection["input_set_id"], "fixture-expanded")
            self.assertEqual(selection["observed_counts"]["total_pair_count"], 1)
            self.assertEqual(selection["excluded_manifests"][0]["reason"], "empty_fixture")
            pair = json.loads(
                (output_dir / "attack_semantic_pair_results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(pair["input_cohort_id"], "new-fixture")
            self.assertEqual(
                pair["relation_design_exposure"],
                "not_inspected_before_semantic_catalog_freeze",
            )
            report = (output_dir / "官方知识语义关联规则验证报告.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("新增配置 fixture", report)
            self.assertIn("empty_fixture", report)

    def test_input_set_rejects_duplicate_manifest_and_observed_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            attack_dir = root / "attack"
            attack_dir.mkdir()
            manifest_path = attack_dir / "attack_sample_manifest_v1.jsonl"
            write_jsonl(attack_dir / "raw_payloads.jsonl", [])
            write_jsonl(manifest_path, [])
            duplicate_set = root / "duplicate.json"
            duplicate_set.write_text(
                json.dumps(
                    {
                        "schema_version": "official-semantic-attack-input-set-v1",
                        "input_set_id": "duplicate-fixture",
                        "cohorts": [
                            {
                                "cohort_id": "a",
                                "label": "A",
                                "relation_design_exposure": "not_declared",
                                "acceptance_reference": "fixture",
                                "manifests": [str(manifest_path)],
                            },
                            {
                                "cohort_id": "b",
                                "label": "B",
                                "relation_design_exposure": "not_declared",
                                "acceptance_reference": "fixture",
                                "manifests": [str(manifest_path)],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate attack manifest"):
                resolve_attack_inputs(input_set_path=duplicate_set)

            mismatch_set = root / "mismatch.json"
            mismatch_set.write_text(
                json.dumps(
                    {
                        "schema_version": "official-semantic-attack-input-set-v1",
                        "input_set_id": "mismatch-fixture",
                        "cohorts": [
                            {
                                "cohort_id": "only",
                                "label": "Only",
                                "relation_design_exposure": "not_declared",
                                "acceptance_reference": "fixture",
                                "manifests": [str(manifest_path)],
                            }
                        ],
                        "expected_counts": {
                            "selected_manifest_count": 1,
                            "total_pair_count": 2,
                        },
                    }
                ),
                encoding="utf-8",
            )
            normal_input = root / "normal.jsonl"
            write_jsonl(normal_input, [complete_payload("normal")])
            output_dir = root / "mismatch-out"
            with self.assertRaisesRegex(ValueError, "observed count mismatch"):
                run_official_semantic_validation(
                    run_id="mismatch",
                    normal_input=normal_input,
                    attack_input_set=mismatch_set,
                    output_dir=output_dir,
                )
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
