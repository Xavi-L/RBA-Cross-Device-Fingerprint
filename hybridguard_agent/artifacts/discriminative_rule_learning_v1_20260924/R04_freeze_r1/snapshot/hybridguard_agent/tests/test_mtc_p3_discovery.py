"""P3 screening boundaries with synthetic controls, never MTC feature files."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hybridguard_agent.scripts import run_mtc_p3_discovery as runner


FLOOR = {"global_empirical": {"discovery_groups": 30, "development_groups": 10,
                               "discovery_manufacturers": 3, "development_manufacturers": 2}}
PROTOCOL = {"candidate_support_floor": FLOOR, "engineering_screening_min_group_agreement": 0.95,
            "research_principle": "No inherited conclusions or legacy performance target"}


def row(group, manufacturer="A"):
    return {"_p2": {"group_id": group, "profile": {"manufacturer": manufacturer, "android_api": 30}}}


def outcome(value):
    return {"outcome": value, "reason": "synthetic"}


class MtcP3DiscoveryTests(unittest.TestCase):
    def test_group_unknown_never_turns_into_match_and_counterexample_remains_visible(self):
        rows = [row("mixed"), row("mixed"), row("bad"), row("bad"), row("good", "B"), row("na")]
        results = [outcome(v) for v in ("MATCH", "UNKNOWN", "UNKNOWN", "COUNTEREXAMPLE", "MATCH", "NOT_APPLICABLE")]
        summary = runner.aggregate({"candidate_id": "fixture"}, rows, results)
        self.assertEqual(summary["records"], 6)
        self.assertEqual(summary["groups"], 4)
        self.assertEqual(summary["applicable_groups"], 2)
        self.assertEqual(summary["matching_group_ids"], ["good"])
        self.assertEqual(summary["unknown_group_ids"], ["mixed"])
        self.assertEqual(summary["counterexample_group_ids"], ["bad"])
        self.assertEqual(summary["group_agreement"], 0.5)

    def test_duplicate_sessions_cannot_supply_independent_group_support(self):
        summary = runner.aggregate({"candidate_id": "fixture"}, [row("same")] * 100, [outcome("MATCH")] * 100)
        self.assertEqual(summary["applicable_groups"], 1)
        self.assertEqual(summary["applicable_manufacturers"], 1)
        self.assertEqual(runner.split_decision({"admission_mode": "empirical"}, summary, "discovery", PROTOCOL),
                         "INSUFFICIENT_APPLICABLE_SUPPORT")

    def test_unknown_only_has_no_agreement_and_not_enough_support(self):
        summary = runner.aggregate({"candidate_id": "fixture"}, [row("a"), row("b")],
                                   [outcome("UNKNOWN"), outcome("NOT_APPLICABLE")])
        self.assertEqual(summary["applicable_groups"], 0)
        self.assertIsNone(summary["group_agreement"])
        self.assertEqual(runner.split_decision({"admission_mode": "semantic"}, summary, "discovery", PROTOCOL),
                         "INSUFFICIENT_APPLICABLE_SUPPORT")

    def test_support_manufacturer_floor_and_fixed_agreement_boundary(self):
        candidate = {"admission_mode": "empirical"}
        summary = {"applicable_groups": 30, "applicable_manufacturers": 3, "group_agreement": 0.95}
        self.assertEqual(runner.split_decision(candidate, summary, "discovery", PROTOCOL), "PASS_RESEARCH_SCREEN")
        self.assertEqual(runner.split_decision(candidate, {**summary, "applicable_manufacturers": 2}, "discovery", PROTOCOL),
                         "INSUFFICIENT_APPLICABLE_SUPPORT")
        self.assertEqual(runner.split_decision(candidate, {**summary, "group_agreement": 0.949}, "discovery", PROTOCOL),
                         "COUNTEREXAMPLES_EXCEED_SCREEN")
        self.assertEqual(runner.split_decision({"admission_mode": "descriptive_only"}, summary, "discovery", PROTOCOL),
                         "DESCRIPTIVE_ONLY_SEMANTIC_LIMIT")

    def test_development_cannot_rescue_unselected_candidate_or_change_parameters(self):
        candidates = [{"candidate_id": cid, "admission_mode": "empirical", "source_lane": "device_mined_rule",
                       "official_source_ids": [], "parameters": {"tolerance": 1}, "dependencies": []}
                      for cid in ("both_pass", "discovery_failed", "development_failed")]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, baseline, config, output = (root / name for name in ("plan", "baseline", "config", "output"))
            for directory in (plan, baseline, config):
                directory.mkdir()
            runner.write_json(plan / "protocol.json", {"candidate_support_floor": FLOOR})
            runner.write_json(baseline / "summary.json", {"version": "mtc-legacy-rule-baseline-v1", "splits": {"discovery": {}, "development": {}},
                                                         "plan_dir": str(plan), "generated_at": "fixture"})
            runner.write_json(config / "mtc_p3_discovery_protocol.v1.json", PROTOCOL)
            runner.write_json(config / "mtc_p3_candidate_templates.v1.json", {"candidates": candidates})
            runner.write_json(config / "mtc_p3_semantic_sources.v1.json", {"sources": []})
            seen = []
            def evaluate(output_dir, split, supplied_candidates, supplied_plan, protocol):
                seen.append(split)
                self.assertEqual(supplied_candidates, candidates)
                self.assertEqual(supplied_plan, plan)
                if split == "development":
                    frozen = json.loads((output_dir / "discovery_selection_FREEZE.json").read_text())
                    self.assertEqual(frozen["candidate_ids"], ["both_pass", "development_failed"])
                    self.assertFalse(frozen["development_seen_by_this_runner"])
                return {c["candidate_id"]: {"records": 3, "screen_decision": (
                            "COUNTEREXAMPLES_EXCEED_SCREEN" if c["candidate_id"] == f"{split}_failed" else "PASS_RESEARCH_SCREEN")}
                        for c in supplied_candidates}
            with patch.object(runner, "evaluate_split", side_effect=evaluate):
                summary = runner.execute(plan, baseline, config, output)
            self.assertEqual(seen, ["discovery", "development"])
            catalog = json.loads((output / "candidate_catalog.v2.json").read_text())
            result = {c["candidate_id"]: c for c in catalog["candidates"]}
            self.assertEqual(result["both_pass"]["disposition"], "EMPIRICAL_RESEARCH_RELATION")
            self.assertTrue(result["discovery_failed"]["disposition"].startswith("NOT_SELECTED_DISCOVERY"))
            self.assertTrue(result["development_failed"]["disposition"].startswith("HELD_AFTER_DEVELOPMENT"))
            self.assertEqual(summary["reserved_feature_rows_decoded"], 0)
            self.assertEqual([r["parameters"] for r in result.values()], [{"tolerance": 1}] * 3)
            admitted = json.loads((output / "rule_catalog.v2.json").read_text())
            self.assertEqual([r["candidate_id"] for r in admitted["rules"]], ["both_pass"])
            self.assertFalse(admitted["risk_scoring_allowed"])


if __name__ == "__main__":
    unittest.main()
