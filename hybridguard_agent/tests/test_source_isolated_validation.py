"""Source-isolation contracts for the official and device-mined lanes."""

from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from hybridguard_agent.scripts.run_source_isolated_validation import run_source_isolated_validation
from hybridguard_agent.tests.test_two_source_rule_classification import ATTACK_UA, payload


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class SourceIsolatedValidationTests(unittest.TestCase):
    def test_runs_official_coverage_and_device_predicates_without_blending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = payload("baseline-session")
            active = copy.deepcopy(baseline)
            active["session_id"] = "active-session"
            active["web_data"]["user_agent"] = ATTACK_UA  # type: ignore[index]
            post = payload("post-session")
            normal_input = root / "normal.jsonl"
            write_jsonl(normal_input, [baseline])

            attack_dir = root / "attack"
            attack_dir.mkdir()
            write_jsonl(attack_dir / "raw_payloads.jsonl", [baseline, active, post])
            manifest = attack_dir / "attack_sample_manifest_v1.jsonl"
            write_jsonl(
                manifest,
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
                            "tool_name": "fixture-tool",
                            "tool_version": "1.0",
                            "config_id": "fixture-config",
                            "execution_status": "verified_success",
                            "feature_effect_status": "observed",
                            "observed_mutations": [
                                {
                                    "field_path": "web_data.navigator_layer.user_agent",
                                    "change_summary": "fixture UA changed",
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
            result = run_source_isolated_validation(
                run_id="source-isolated-fixture",
                normal_input=normal_input,
                attack_manifests=[manifest],
                output_dir=output_dir,
            )

            self.assertEqual(result["official_document_lane"]["independent_executable_predicate_count"], 0)
            self.assertEqual(result["device_mined_rule_lane"]["compiled_predicate_count"], 10)
            official_normal = json.loads(
                (output_dir / "official_document_normal_results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(
                official_normal["official_document_decision"]["decision_status"],
                "not_independently_evaluable",
            )
            self.assertIsNone(official_normal["official_document_decision"]["alert"])

            device_pair = json.loads(
                (output_dir / "device_mined_attack_pair_results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertFalse(device_pair["baseline"]["alert"])
            self.assertTrue(device_pair["attack_active"]["alert"])
            self.assertEqual(
                device_pair["device_mined_rule_alarm_transition"],
                "baseline_no_alert_to_attack_active_alert",
            )
            self.assertNotIn("post-session", json.dumps(device_pair, ensure_ascii=False))
            self.assertIn("NW-006", device_pair["attack_active"]["matched_rule_ids"])
            self.assertNotIn("context_pack", json.dumps(device_pair, ensure_ascii=False))

            with (output_dir / "device_mined_rule_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            nw006 = next(row for row in rows if row["rule_id"] == "NW-006")
            self.assertEqual(nw006["attack_active_match_count"], "1")
            report = (output_dir / "两类知识独立验证报告.md").read_text(encoding="utf-8")
            self.assertIn("源隔离复核", report)
            self.assertIn("官方文档轨当前有 0 条独立可执行报警 predicate", report)


if __name__ == "__main__":
    unittest.main()
