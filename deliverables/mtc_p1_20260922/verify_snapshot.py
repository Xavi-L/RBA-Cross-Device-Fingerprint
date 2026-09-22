"""Independent output-to-raw accounting checks; no services, labels or rules."""
from collections import Counter
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from hybridguard_agent.scripts.build_latest_paired244_snapshot import APP_ROOTS, feature_map, canonical_json


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    output = REPO / "hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final"
    manifest = json.loads((output / "manifest.json").read_text())
    freeze = Path(manifest["freeze_directory"])
    raw = rows(freeze / "sources/raw_expanded_payloads.jsonl")
    browser = rows(freeze / "sources/raw_browser_payloads.jsonl")
    provenance = rows(freeze / "sources/browser_pair_provenance.jsonl")
    selection = rows(output / "selection_audit.jsonl")
    pair_audit = rows(output / "pair_qc_audit.jsonl")
    assert Counter(r["source_line"] for r in selection) == Counter(range(1, len(raw) + 1))
    assert Counter(r["provenance_line"] for r in pair_audit) == Counter(range(1, len(provenance) + 1))
    assert len({r["sample_id"] for r in selection}) == len(raw)
    assert len(rows(output / "receipt_audit.jsonl")) == len(rows(freeze / "sources/collection_receipts.jsonl"))
    assert not rows(output / "auxiliary_issues.jsonl")
    views = {name: rows(output / (name + ".jsonl")) for name in manifest["view_counts"]}
    assert not views["quarantine"]
    actual_routes = Counter()
    profile_set = set()
    null_slots = Counter()
    for name, records in views.items():
        assert len(records) == manifest["view_counts"][name]
        for record in records:
            line = record["source_refs"]["app_raw_line"]
            actual_routes[(line, name, record["sample_id"])] += 1
            original = feature_map(raw[line - 1]["canonical_received_payload"], APP_ROOTS)
            app_values = {k.removeprefix("app."): v for k, v in record["features"].items() if k.startswith("app.")}
            assert canonical_json({k: app_values[k] for k in original}) == canonical_json(original)
            added = set(app_values) - set(original)
            assert {"app." + f for f in added} == set(record["normalization"]["null_slots_added"])
            for field in added:
                assert app_values[field] is None and record["field_status"]["app." + field] != "observed"
            if added:
                null_slots[len(original)] += 1
            if record.get("pair"):
                b = browser[record["source_refs"]["browser_raw_line"] - 1]
                original_browser = feature_map(b["canonical_received_payload"], ("web_data",))
                observed = {k.removeprefix("browser."): v for k, v in record["features"].items() if k.startswith("browser.")}
                assert canonical_json(observed) == canonical_json(original_browser)
            if name == "paired_244":
                assert record["feature_count"] == len(record["features"]) == len(record["field_status"]) == 244
                assert not record["qc"]["layers_without_observed_fields"]
                p = record["profile"]
                profile_set.add((p["manufacturer"], p["model"], p["android_release"]))
            if name == "app_only_177":
                assert len(record["features"]) == 177 and not any(k.startswith("browser.") for k in record["features"])
            assert record["label_status"] == "unlabeled"
    assert actual_routes == Counter((r["source_line"], r["destination"], r["sample_id"]) for r in selection)
    p0_profiles = {tuple(r[k] for k in ("manufacturer", "model", "android_release"))
                   for r in rows(freeze / "model_os_inventory.jsonl") if r["completed_pair_count"]}
    assert profile_set == p0_profiles
    assert manifest["qc_paired_model_os"] == len(profile_set)
    result = {"status": "PASS", "snapshot_directory": str(output),
              "app_rows_routed_once": len(raw), "pairs_routed_once": len(provenance),
              "paired_model_os_profiles_preserved": len(profile_set),
              "derived_null_observations_by_original_field_count": dict(null_slots),
              "all_original_app_browser_values_preserved": True, "labels_invented": False,
              "unit_tests_recorded_separately": "TEST_RESULTS.json"}
    (Path(__file__).parent / "VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
