from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/build_latest_experiment_plan.py"
SPEC = importlib.util.spec_from_file_location("build_latest_experiment_plan", SCRIPT_PATH)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def make_snapshot(root: Path, paired_count: int, app_only_count: int) -> tuple[Path, list[dict[str, object]]]:
    snapshot = root / "snapshot"
    snapshot.mkdir()
    app_fields = [f"app.android_native_data.fixture_{number:03d}" for number in range(177)]
    browser_fields = [f"browser.web_data.fixture_{number:03d}" for number in range(67)]
    paired_fields = app_fields + browser_fields
    paired_rows: list[dict[str, object]] = []
    app_only_rows: list[dict[str, object]] = []
    index_rows: list[dict[str, object]] = []
    for view, count, prefix in (
        ("paired_244", paired_count, "paired"),
        ("app_only_177", app_only_count, "app-only"),
    ):
        target = paired_rows if view == "paired_244" else app_only_rows
        for number in range(count):
            sample_id = f"{prefix}-{number:03d}"
            session_id = f"session-{prefix}-{number:03d}"
            payload_hash = hashlib.sha256(("payload:" + session_id).encode()).hexdigest()
            fields = paired_fields if view == "paired_244" else app_fields
            target.append(
                {
                    "record_schema_version": (
                        "hybridguard-paired244-view-v1"
                        if view == "paired_244"
                        else "hybridguard-app177-reserve-view-v1"
                    ),
                    "sample_id": sample_id,
                    "dataset_view": view,
                    "dataset_role": "development_qc_only",
                    "label_status": "unlabeled",
                    "feature_count": len(fields),
                    "features": {field: "fixture" for field in fields},
                    "field_status": {field: "observed" for field in fields},
                }
            )
            index_rows.append(
                {
                    "sample_index_version": "latest-paired244-sample-index-v1",
                    "sample_id": sample_id,
                    "app_session_id": session_id,
                    "app_payload_sha256": payload_hash,
                    "dataset_view": view,
                    "dataset_role": "development_qc_only",
                    "label_status": "unlabeled",
                }
            )
    write_jsonl(snapshot / "paired_244.jsonl", paired_rows)
    write_jsonl(snapshot / "app_only_177.jsonl", app_only_rows)
    write_jsonl(snapshot / "sample_index.jsonl", index_rows)
    write_json(
        snapshot / "feature_catalog.json",
        {
            "feature_catalog_version": "latest-paired244-feature-catalog-v1",
            "paired_feature_order": paired_fields,
            "paired_feature_types": {field: "string" for field in paired_fields},
        },
    )
    write_json(
        snapshot / "dataset_manifest.json",
        {
            "dataset_manifest_version": "latest-featureapp-paired244-snapshot-v1",
            "run_id": "fixture-latest",
            "dataset_role": "development_qc_only",
            "label_status": "unlabeled",
            "views": {
                "paired_244": {"path": "paired_244.jsonl", "count": paired_count},
                "app_only_177": {"path": "app_only_177.jsonl", "count": app_only_count},
            },
            "sample_index_path": "sample_index.jsonl",
            "feature_catalog_path": "feature_catalog.json",
        },
    )
    return snapshot, index_rows


def fact(
    sample: dict[str, object],
    group_hash: str,
    label: bool,
    *,
    scenario: str,
    task: str = builder.PRIMARY_TASK,
    scope: str = "provider_device_profile",
    stability: str = "provider_verified",
) -> dict[str, object]:
    return {
        "experiment_fact_version": "latest-experiment-fact-v1",
        "app_session_id": sample["app_session_id"],
        "app_payload_sha256": sample["app_payload_sha256"],
        "label_status": "verified",
        "manipulation_present": label,
        "evaluation_task": task,
        "execution_status": "succeeded" if label else "not_applicable",
        "field_effect_status": "observed" if label else "no_configured_change",
        "stable_group_key_hash": group_hash,
        "identity_scope": scope,
        "identity_stability": stability,
        "scenario_group_id": scenario,
        "scenario_phase": "attack_active" if label else "clean_pre",
        "scenario_repetition": 1,
        "attack_family": "synthetic-fingerprint-effect" if label else None,
        "evidence_refs": [f"evidence:{sample['app_session_id']}"],
    }


def group_for_split(protocol: dict[str, object], split: str, ordinal: int) -> str:
    for attempt in range(10000):
        value = hashlib.sha256(f"{split}:{ordinal}:{attempt}".encode()).hexdigest()
        if builder.assign_split(protocol, scope="provider_device_profile", group_hash=value) == split:
            return value
    raise AssertionError(f"Could not find a deterministic group for {split}")


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class LatestExperimentPlanTest(unittest.TestCase):
    def test_frozen_contract_matches_the_builder(self) -> None:
        schema = json.loads(builder.DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
        protocol = builder.load_protocol(builder.DEFAULT_PROTOCOL_PATH)
        self.assertEqual(set(schema["required"]), builder.FACT_KEYS)
        self.assertEqual(set(schema["properties"]), builder.FACT_KEYS)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(protocol["eligibility"]["primary_evaluation_task"], builder.PRIMARY_TASK)

    def test_current_shape_without_facts_is_blocked_but_preserves_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, _ = make_snapshot(root, paired_count=17, app_only_count=9)
            output = root / "plan"
            readiness = builder.build_plan(snapshot, output)
            registry = read_jsonl(output / "experiment_registry.jsonl")

            self.assertEqual(readiness["counts"]["indexed_sample_count"], 26)
            self.assertEqual(readiness["counts"]["paired244_primary_count"], 17)
            self.assertEqual(readiness["counts"]["app177_reserve_count"], 9)
            self.assertEqual(readiness["counts"]["grouped_input_eligible_count"], 0)
            self.assertFalse(readiness["structural_ready"])
            self.assertFalse(readiness["grouped_data_prerequisites_met"])
            self.assertFalse(readiness["downstream_permissions"]["report_performance_metrics"])
            self.assertEqual(len(registry), 26)
            self.assertEqual((output / "split_manifest.jsonl").read_text(), "")
            self.assertEqual(
                sum(row["exclusion_reasons"] == ["X_APP_ONLY_RESERVE"] for row in registry),
                9,
            )
            self.assertTrue(all(row["manipulation_present"] is None for row in registry))

    def test_verified_grouped_facts_unlock_structural_and_formal_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, index_rows = make_snapshot(root, paired_count=30, app_only_count=1)
            protocol = builder.load_protocol(builder.DEFAULT_PROTOCOL_PATH)
            facts: list[dict[str, object]] = []
            cursor = 0
            for split in ("train", "development", "test"):
                for ordinal in range(5):
                    group_hash = group_for_split(protocol, split, ordinal)
                    scenario = f"scenario-{split}-{ordinal}"
                    facts.append(fact(index_rows[cursor], group_hash, False, scenario=scenario))
                    facts.append(fact(index_rows[cursor + 1], group_hash, True, scenario=scenario))
                    cursor += 2
            facts_path = root / "facts.jsonl"
            write_jsonl(facts_path, facts)
            output = root / "plan"
            readiness = builder.build_plan(snapshot, output, facts_path=facts_path)
            split_rows = read_jsonl(output / "split_manifest.jsonl")

            self.assertTrue(readiness["structural_ready"])
            self.assertTrue(readiness["grouped_data_prerequisites_met"])
            self.assertEqual(readiness["counts"]["grouped_input_eligible_count"], 30)
            self.assertFalse(readiness["downstream_permissions"]["train_or_tune_model"])
            self.assertFalse(readiness["downstream_permissions"]["report_performance_metrics"])
            self.assertEqual(
                readiness["counts"]["split_group_counts"],
                {"train": 5, "development": 5, "test": 5},
            )
            group_splits: dict[str, set[str]] = {}
            for row in split_rows:
                group_splits.setdefault(row["stable_group_key_hash"], set()).add(row["split"])
            self.assertTrue(all(len(values) == 1 for values in group_splits.values()))
            self.assertFalse(
                {"app_session_id", "app_payload_sha256", "evidence_refs", "features"}
                & set(split_rows[0])
            )

    def test_same_semantic_facts_are_byte_reproducible_when_rows_are_reordered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, rows = make_snapshot(root, paired_count=2, app_only_count=0)
            protocol = builder.load_protocol(builder.DEFAULT_PROTOCOL_PATH)
            group_hash = group_for_split(protocol, "train", 0)
            facts = [
                fact(rows[0], group_hash, False, scenario="scenario-one"),
                fact(rows[1], group_hash, True, scenario="scenario-one"),
            ]
            first_facts = root / "facts-first.jsonl"
            second_facts = root / "facts-second.jsonl"
            write_jsonl(first_facts, facts)
            write_jsonl(second_facts, list(reversed(facts)))
            first_output = root / "first"
            second_output = root / "second"
            builder.build_plan(snapshot, first_output, facts_path=first_facts)
            builder.build_plan(snapshot, second_output, facts_path=second_facts)

            first_files = {path.name: path.read_bytes() for path in first_output.iterdir()}
            second_files = {path.name: path.read_bytes() for path in second_output.iterdir()}
            self.assertEqual(first_files, second_files)

    def test_split_assignment_does_not_depend_on_label(self) -> None:
        protocol = builder.load_protocol(builder.DEFAULT_PROTOCOL_PATH)
        for split in ("train", "development", "test"):
            group_hash = group_for_split(protocol, split, 7)
            before = builder.assign_split(
                protocol, scope="provider_device_profile", group_hash=group_hash
            )
            after_label_flip = builder.assign_split(
                protocol, scope="provider_device_profile", group_hash=group_hash
            )
            self.assertEqual(before, after_label_flip)
            self.assertEqual(before, split)

    def test_plan_identity_binds_validated_view_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, _ = make_snapshot(root, paired_count=1, app_only_count=0)
            builder.build_plan(snapshot, root / "first")
            first_manifest = json.loads(
                (root / "first/experiment_input_manifest.json").read_text(encoding="utf-8")
            )
            paired_path = snapshot / "paired_244.jsonl"
            row = read_jsonl(paired_path)[0]
            field = next(iter(row["features"]))
            row["features"][field] = "changed-but-valid"
            write_jsonl(paired_path, [row])
            builder.build_plan(snapshot, root / "second")
            second_manifest = json.loads(
                (root / "second/experiment_input_manifest.json").read_text(encoding="utf-8")
            )
            self.assertNotEqual(first_manifest["run_id"], second_manifest["run_id"])

            row["features"][field] = 42
            write_jsonl(paired_path, [row])
            with self.assertRaisesRegex(ValueError, "field type is invalid"):
                builder.build_plan(snapshot, root / "invalid")
            self.assertFalse((root / "invalid").exists())

    def test_rejects_duplicate_unknown_and_payload_mismatched_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, rows = make_snapshot(root, paired_count=1, app_only_count=0)
            group_hash = hashlib.sha256(b"group").hexdigest()
            valid = fact(rows[0], group_hash, False, scenario="scenario")
            cases = {
                "duplicate": ([valid, valid], "duplicate app_session_id"),
                "unknown": ([{**valid, "app_session_id": "unknown"}], "E_SIDECAR_JOIN_MISMATCH"),
                "payload": ([{**valid, "app_payload_sha256": "0" * 64}], "E_SIDECAR_JOIN_MISMATCH"),
                "string-label": ([{**valid, "manipulation_present": "false"}], "must be boolean"),
            }
            for name, (facts, message) in cases.items():
                with self.subTest(name=name):
                    facts_path = root / f"facts-{name}.jsonl"
                    write_jsonl(facts_path, facts)
                    output = root / f"plan-{name}"
                    with self.assertRaisesRegex(ValueError, message):
                        builder.build_plan(snapshot, output, facts_path=facts_path)
                    self.assertFalse(output.exists())

    def test_rejects_scenario_spanning_stable_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, rows = make_snapshot(root, paired_count=2, app_only_count=0)
            facts = [
                fact(rows[0], hashlib.sha256(b"group-a").hexdigest(), False, scenario="same"),
                fact(rows[1], hashlib.sha256(b"group-b").hexdigest(), True, scenario="same"),
            ]
            facts_path = root / "facts.jsonl"
            write_jsonl(facts_path, facts)
            with self.assertRaisesRegex(ValueError, "E_SCENARIO_GROUP_MISMATCH"):
                builder.build_plan(snapshot, root / "plan", facts_path=facts_path)

    def test_transport_untrusted_and_app_only_facts_never_enter_primary_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, rows = make_snapshot(root, paired_count=2, app_only_count=1)
            group_hashes = [hashlib.sha256(f"group-{number}".encode()).hexdigest() for number in range(3)]
            facts = [
                fact(
                    rows[0],
                    group_hashes[0],
                    True,
                    scenario="transport",
                    task="transport_path_effect",
                ),
                fact(
                    rows[1],
                    group_hashes[1],
                    False,
                    scenario="untrusted",
                    scope="collector_install_profile_not_physical_device",
                    stability="run_scoped_unverified",
                ),
                fact(rows[2], group_hashes[2], False, scenario="app-only"),
            ]
            facts_path = root / "facts.jsonl"
            write_jsonl(facts_path, facts)
            output = root / "plan"
            readiness = builder.build_plan(snapshot, output, facts_path=facts_path)
            registry = {row["sample_id"]: row for row in read_jsonl(output / "experiment_registry.jsonl")}

            self.assertEqual(readiness["counts"]["grouped_input_eligible_count"], 0)
            self.assertIn("X_TASK_NOT_PRIMARY", registry["paired-000"]["exclusion_reasons"])
            self.assertIn("X_IDENTITY_SCOPE_UNTRUSTED", registry["paired-001"]["exclusion_reasons"])
            self.assertEqual(registry["app-only-000"]["exclusion_reasons"], ["X_APP_ONLY_RESERVE"])

    def test_rejects_output_inside_snapshot_or_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot, _ = make_snapshot(root, paired_count=1, app_only_count=0)
            with self.assertRaisesRegex(ValueError, "outside"):
                builder.build_plan(snapshot, snapshot / "plan")
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                builder.build_plan(snapshot, existing)


if __name__ == "__main__":
    unittest.main()
