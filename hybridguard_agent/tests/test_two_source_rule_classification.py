"""Contract tests for the one-shot two-source classification package."""

from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from hybridguard_agent.scripts.run_two_source_rule_classification import run_classification


BASELINE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
)
ATTACK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/122.0.0.0 Safari/537.36"
)


def payload(session_id: str, user_agent: str = BASELINE_UA) -> dict[str, object]:
    return {
        "collector_app": "featureapp",
        "schema_version": "expanded-v2.2-status",
        "session_id": session_id,
        "android_native_data": {
            "os_version": "14",
            "sensor_total_count": 12,
            "device_model": "Pixel 8",
            "is_adb_enabled": False,
            "battery_level_pct": 51,
            "is_charging": False,
            "build_fingerprint": "google/husky/husky:14/UP1A.1:user/release-keys",
            "build_tags": "release-keys",
            "build_type": "user",
        },
        "webview_data": {
            "system_http_agent": BASELINE_UA,
            "jsbridge_injected": True,
            "is_debuggable": False,
            "is_cleartext_traffic_permitted": False,
            "installer_package": "com.android.vending",
            "default_ua_native": BASELINE_UA,
        },
        "web_data": {
            "user_agent": user_agent,
            "platform": "Linux armv8l",
            "max_touch_points": 5,
            "timezone_offset": 480,
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class TwoSourceRuleClassificationTests(unittest.TestCase):
    def test_compares_only_baseline_and_active_and_confirms_direct_feature_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            normal_input = root / "normal.jsonl"
            baseline = payload("baseline-session")
            active = copy.deepcopy(baseline)
            active["session_id"] = "active-session"
            active["web_data"]["user_agent"] = ATTACK_UA  # type: ignore[index]
            post = payload("post-session")
            write_jsonl(normal_input, [baseline])

            attack_dir = root / "attack"
            attack_dir.mkdir()
            write_jsonl(attack_dir / "raw_payloads.jsonl", [baseline, active, post])
            manifest = attack_dir / "attack_sample_manifest_v1.jsonl"
            pair_id = "pair-1"
            write_jsonl(
                manifest,
                [
                    {
                        "session_id": "baseline-session",
                        "pair": {"pair_id": pair_id, "pair_role": "clean_pre"},
                        "attack": {},
                    },
                    {
                        "session_id": "active-session",
                        "pair": {"pair_id": pair_id, "pair_role": "attack"},
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
                        "pair": {"pair_id": pair_id, "pair_role": "clean_post"},
                        "attack": {},
                    },
                ],
            )

            output_dir = root / "out"
            result = run_classification(
                run_id="fixture-run",
                normal_input=normal_input,
                attack_manifests=[manifest],
                output_dir=output_dir,
            )

            self.assertEqual(result["protocol"]["states_compared"], ["baseline", "attack_active"])
            self.assertEqual(result["inputs"]["attack"]["ignored_historical_post_count"], 1)
            pair_result = json.loads(
                (output_dir / "attack_pair_results.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertTrue(pair_result["eligible_for_two_state_validation"])
            self.assertEqual(pair_result["ignored_historical_post_count"], 1)
            direct_fields = {
                row["field_path"]
                for row in pair_result["feature_comparison"]["direct_changed_fields"]
            }
            self.assertIn("web_data.user_agent", direct_fields)
            annotation = pair_result["feature_comparison"]["annotated_field_results"][0]
            self.assertEqual(annotation["field_path"], "web_data.user_agent")
            self.assertEqual(annotation["annotation_status"], "confirmed_by_direct_payload_comparison")

            classification_text = (output_dir / "classification_records.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("post-session", classification_text)
            pair_text = (output_dir / "attack_pair_results.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(BASELINE_UA, pair_text)
            self.assertNotIn(ATTACK_UA, pair_text)
            with (output_dir / "feature_delta_summary.csv").open(encoding="utf-8") as handle:
                feature_summary = list(csv.DictReader(handle))
            ua_row = next(row for row in feature_summary if row["field_path"] == "web_data.user_agent")
            self.assertEqual(ua_row["direct_change_pair_count"], "1")
            self.assertEqual(ua_row["stable_direct_change_within_available_pairs"], "True")
            self.assertEqual(
                ua_row["stable_attack_attributable_change_within_available_pairs"], "True"
            )


if __name__ == "__main__":
    unittest.main()
