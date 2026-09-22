"""Verify the published P2 control plane directly against P1 metadata."""
from collections import Counter, defaultdict
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / "hybridguard_agent/artifacts/mtc_p2_frozen_20260922"


def json_rows(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    summary = json.loads((PLAN / "summary.json").read_text())
    protocol = json.loads((PLAN / "protocol.json").read_text())
    snapshot = Path(summary["source_snapshot"])
    records = {}
    for view in ("paired_244", "app_only_177", "partial", "repeated_observations"):
        with (snapshot / (view + ".jsonl")).open() as handle:
            for line, text in enumerate(handle, 1):
                row = json.loads(text)
                records[row["sample_id"]] = {"profile": row["profile"], "app": row["app"], "browser": row.get("browser"),
                    "raw_line": row["source_refs"]["app_raw_line"], "source_file": str(snapshot / (view + ".jsonl")),
                    "source_line": line, "view": view}
    registry = json_rows(PLAN / "sample_registry.jsonl")
    by_id = {r["sample_id"]: r for r in registry}
    assert len(by_id) == len(registry) == len(records) == summary["observations"]
    assert set(by_id) == set(records)
    linked = defaultdict(set)
    primary_candidates = defaultdict(list)
    for key, row in records.items():
        p = row["profile"]
        registered = by_id[key]
        assignment = (registered["group_id"], registered["split"])
        for link in [("model", p["manufacturer"], p["model"]), ("install", p["collector_install_id"]), ("session", row["app"]["session_id"])]:
            linked[link].add(assignment)
        assert registered["source_view"] == row["view"]
        assert registered["app_payload_sha256"] == row["app"]["payload_sha256"]
        assert registered["label_status"] == "unknown" and registered["manipulation_present"] is None
        assert registered["physical_device_identity"] == "unknown"
        assert registered["scenario_id"] is None and not registered["metric_eligible"]
        if row["view"] == "paired_244":
            primary_candidates[(p["manufacturer"], p["model"], p["android_release"])].append((row["raw_line"], key))
    assert all(len(v) == 1 for v in linked.values())
    expected_representatives = {min(candidates)[1] for candidates in primary_candidates.values()}
    assert {r["sample_id"] for r in registry if r["analysis_role"] == "primary_representative"} == expected_representatives
    groups = json.loads((PLAN / "group_registry.json").read_text())["groups"]
    assert len(groups) == summary["leakage_groups"]
    assert Counter(key for group in groups for key in group["sample_ids"]) == Counter(records.keys())
    for group in groups:
        assert all((by_id[key]["group_id"], by_id[key]["split"]) == (group["group_id"], group["split"]) for key in group["sample_ids"])
        assert group["physical_device_count"] is None
    for split, filename in [("discovery", "discovery_inputs.jsonl"), ("development", "development_inputs.jsonl")]:
        inputs = json_rows(PLAN / filename)
        expected = {key for key in expected_representatives if by_id[key]["split"] == split}
        assert {r["sample_id"] for r in inputs} == expected and len(inputs) == len(expected)
        for r in inputs:
            assert set(r) == {"sample_id", "source_file", "source_line", "app_payload_sha256", "browser_payload_sha256"}
            source = records[r["sample_id"]]
            assert r["source_file"] == source["source_file"] and r["source_line"] == source["source_line"]
            assert r["browser_payload_sha256"] == source["browser"]["payload_sha256"]
    assert not (PLAN / "reserved_validation_inputs.jsonl").exists()
    assert not json_rows(PLAN / "scenario_registry.jsonl") and not json_rows(PLAN / "accepted_facts.jsonl")
    assert not summary["detection_data_prerequisites_met"]
    assert not protocol["pre_split_exposure"]["pristine_blind_holdout"]
    assert not any(summary["stage_capabilities"][k] for k in ["model_training", "threshold_optimization", "detection_metrics", "rule_execution", "reserved_validation_input_release"])
    # Rebuilt protocol additions did not reroll the already-declared split.
    first = REPO / "hybridguard_agent/artifacts/mtc_experiment_plan_v1_20260922/split_manifest.jsonl"
    assert json_rows(first) == json_rows(PLAN / "split_manifest.jsonl")
    assert all(not (f.stat().st_mode & 0o222) for f in PLAN.iterdir() if f.is_file())
    result = {"status": "PASS", "p2_directory": str(PLAN), "observations_accounted_once": len(records),
              "leakage_groups": len(groups), "model_os_representatives": len(expected_representatives),
              "related_record_cross_split_violations": 0, "labels_inferred": False, "split_rerolls": 0,
              "reserved_validation_input_exported": False, "input_label_group_scenario_leakage": False,
              "artifact_files_read_only": True, "test_execution_record": "TEST_RESULTS.json"}
    (Path(__file__).parent / "VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
