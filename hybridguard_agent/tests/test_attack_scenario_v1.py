"""Contract tests for the label-free offline controlled-scenario sidecar."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hybridguard_agent.scenarios.controlled_triplet import (
    SCENARIO_INPUT_VERSION,
    build_controlled_scenario_sidecar,
    load_controlled_scenario_policy,
    sha256_value,
)


TARGET_FIELDS = [
    "web_data.webdriver",
    "web_data.platform",
    "web_data.hardware_concurrency",
    "web_data.device_memory",
    "web_data.user_agent",
]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def payload(*, user_agent: str = "pre-secret-ua", platform: str = "Linux armv8l") -> dict:
    return {
        "collector_app": "featureapp",
        "schema_version": "expanded-v2",
        "android_native_data": {},
        "webview_data": {},
        "web_data": {
            "webdriver": False,
            "platform": platform,
            "hardware_concurrency": 8,
            "device_memory": 8,
            "user_agent": user_agent,
        },
    }


def field_status(sample_id: str, *, unavailable: set[str] | None = None) -> dict:
    unavailable = unavailable or set()
    return {
        "sample_id": sample_id,
        "field_status": {
            "status_schema_version": "field-status-v1",
            "fields": {
                path: "timeout" if path in unavailable else "observed" for path in TARGET_FIELDS
            },
        },
    }


def scenario_input(
    sample_id: str,
    value: dict,
    *,
    pair_key: str | None,
    role: str | None = None,
    sequence: int | None = None,
    stable_key: str = "stable-device-a",
) -> dict:
    pair = None
    if pair_key is not None:
        assert role is not None and sequence is not None
        pair = {
            "pair_key_sha256": sha256_value(pair_key),
            "pair_role": role,
            "sequence_index": sequence,
        }
    return {
        "controlled_scenario_input_version": SCENARIO_INPUT_VERSION,
        "sample_id": sample_id,
        "normalized_payload_sha256": sha256_value(value),
        "stable_device_key_hash": sha256_value(stable_key),
        "pair": pair,
    }


def normalized_row(sample_id: str, value: dict) -> dict:
    return {"sample_id": sample_id, "schema_version": "expanded-v2", "payload": value}


def write_snapshot(
    directory: Path,
    records: list[tuple[dict, dict, set[str]]],
) -> None:
    write_jsonl(directory / "controlled_scenario_input_v1.jsonl", [item[0] for item in records])
    write_jsonl(
        directory / "normalized_expanded_v2.jsonl",
        [normalized_row(item[0]["sample_id"], item[1]) for item in records],
    )
    write_jsonl(
        directory / "field_status.jsonl",
        [field_status(item[0]["sample_id"], unavailable=item[2]) for item in records],
    )


def complete_triplet(
    *,
    pair_key: str = "opaque-pair-a",
    pre_value: dict | None = None,
    active_value: dict | None = None,
    post_value: dict | None = None,
    stable_keys: tuple[str, str, str] = ("stable-device-a", "stable-device-a", "stable-device-a"),
    unavailable: tuple[set[str], set[str], set[str]] = (set(), set(), set()),
) -> list[tuple[dict, dict, set[str]]]:
    pre_value = pre_value or payload()
    active_value = active_value or payload(user_agent="active-secret-ua")
    post_value = post_value or payload()
    rows = []
    for sample_id, value, role, sequence, stable_key, missing in zip(
        ("pre", "active", "post"),
        (pre_value, active_value, post_value),
        ("clean_pre", "attack_active", "clean_post"),
        (0, 1, 2),
        stable_keys,
        unavailable,
    ):
        rows.append(
            (
                scenario_input(
                    f"{pair_key}-{sample_id}",
                    value,
                    pair_key=pair_key,
                    role=role,
                    sequence=sequence,
                    stable_key=stable_key,
                ),
                value,
                missing,
            )
        )
    return rows


def scenarios_by_pair(sidecar: dict) -> dict[str, dict]:
    return {scenario["pair_key_sha256"]: scenario for scenario in sidecar["scenarios"]}


class AttackScenarioV1Tests(unittest.TestCase):
    def test_changed_field_is_observed_only_when_it_returns_to_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            write_snapshot(directory, complete_triplet())
            sidecar = build_controlled_scenario_sidecar(directory)

        scenario = sidecar["scenarios"][0]
        self.assertEqual(scenario["scenario_status"], "controlled_target_field_change_observed")
        changed = [
            item["field_path"]
            for item in scenario["field_comparisons"]
            if item["comparison_status"] == "changed_and_restored"
        ]
        self.assertEqual(changed, ["web_data.user_agent"])
        self.assertFalse(scenario["metric_eligible"])
        serialized = json.dumps(sidecar, ensure_ascii=False)
        self.assertNotIn("pre-secret-ua", serialized)
        self.assertNotIn("active-secret-ua", serialized)

    def test_unchanged_triplet_does_not_create_an_attack_or_normal_label(self) -> None:
        clean = payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            write_snapshot(
                directory,
                complete_triplet(pre_value=clean, active_value=clean, post_value=clean),
            )
            sidecar = build_controlled_scenario_sidecar(directory)

        scenario = sidecar["scenarios"][0]
        self.assertEqual(scenario["scenario_status"], "no_configured_target_field_change_observed")
        self.assertEqual(
            {item["comparison_status"] for item in scenario["field_comparisons"]}, {"unchanged"}
        )
        self.assertNotIn("risk_score", scenario)
        self.assertNotIn("attack_label", scenario)

    def test_unrestored_baseline_or_unavailable_field_is_insufficient_evidence(self) -> None:
        unstored_post = payload(user_agent="different-post-secret-ua")
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            records = complete_triplet(post_value=unstored_post)
            records.extend(
                complete_triplet(
                    pair_key="opaque-pair-unavailable",
                    unavailable=(set(), {"web_data.user_agent"}, set()),
                )
            )
            write_snapshot(directory, records)
            sidecar = build_controlled_scenario_sidecar(directory)

        scenarios = scenarios_by_pair(sidecar)
        unrestored = scenarios[sha256_value("opaque-pair-a")]
        unavailable = scenarios[sha256_value("opaque-pair-unavailable")]
        self.assertEqual(unrestored["scenario_status"], "insufficient_evidence")
        self.assertIn("baseline_not_restored", unrestored["reasons"])
        self.assertEqual(unavailable["scenario_status"], "insufficient_evidence")
        self.assertIn("unavailable", unavailable["reasons"])

    def test_incomplete_duplicate_and_mismatched_pairs_are_not_evaluable(self) -> None:
        incomplete_value = payload()
        incomplete = [
            (
                scenario_input(
                    "incomplete-pre",
                    incomplete_value,
                    pair_key="opaque-pair-incomplete",
                    role="clean_pre",
                    sequence=0,
                ),
                incomplete_value,
                set(),
            ),
            (
                scenario_input(
                    "incomplete-active",
                    incomplete_value,
                    pair_key="opaque-pair-incomplete",
                    role="attack_active",
                    sequence=1,
                ),
                incomplete_value,
                set(),
            ),
        ]
        duplicate = complete_triplet(pair_key="opaque-pair-duplicate")
        duplicate[2] = (
            scenario_input(
                "duplicate-clean",
                duplicate[2][1],
                pair_key="opaque-pair-duplicate",
                role="clean_pre",
                sequence=0,
            ),
            duplicate[2][1],
            set(),
        )
        mismatched = complete_triplet(
            pair_key="opaque-pair-mismatch",
            stable_keys=("stable-device-a", "stable-device-b", "stable-device-a"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            write_snapshot(directory, incomplete + duplicate + mismatched)
            sidecar = build_controlled_scenario_sidecar(directory)

        scenarios = scenarios_by_pair(sidecar)
        self.assertIn("missing_role:clean_post", scenarios[sha256_value("opaque-pair-incomplete")]["reasons"])
        duplicate_reasons = scenarios[sha256_value("opaque-pair-duplicate")]["reasons"]
        self.assertIn("duplicate_role:clean_pre", duplicate_reasons)
        self.assertIn("missing_role:clean_post", duplicate_reasons)
        self.assertIn(
            "stable_device_key_mismatch",
            scenarios[sha256_value("opaque-pair-mismatch")]["reasons"],
        )
        self.assertTrue(
            all(scenario["scenario_status"] == "not_evaluable" for scenario in scenarios.values())
        )

    def test_projection_rejects_unapproved_label_or_tool_metadata(self) -> None:
        records = complete_triplet()
        records[0][0]["label"] = "poisoned-answer"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            write_snapshot(directory, records)
            with self.assertRaisesRegex(ValueError, "approved fields"):
                build_controlled_scenario_sidecar(directory)

    def test_policy_is_fixed_to_the_five_cdp_v1_target_fields(self) -> None:
        policy = load_controlled_scenario_policy()
        self.assertEqual(policy["target_field_paths"], TARGET_FIELDS)
        self.assertFalse(policy["metric_eligible"])


if __name__ == "__main__":
    unittest.main()
