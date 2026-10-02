#!/usr/bin/env python3
"""Cross-check saved audit evidence and original references; no relation/model calls."""
import argparse
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "deliverables/rule_semantics_capacity_comparison_v1"
PREPARED = ROOT / "deliverables/rule_semantics_raw_only_expansion_v1/prepared"


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify():
    summary, baseline = read(HERE / "SUMMARY.json"), read(HERE / "BASELINE.json")
    rows, triplets = lines(HERE / "ROWS.jsonl"), read(HERE / "TRIPLETS.json")
    by_id = {r["opaque_id"]: r for r in rows}
    contract = read(BASE / "CONTRACT.json")
    assert len(rows) == len(by_id) == 378 and set(by_id) == set(contract["sample_ids"])
    assert Counter(r["phase"] for r in rows) == {"clean_pre": 126, "attack": 126, "clean_post": 126}
    archives = {ref: (ROOT / ref).read_text().splitlines() for ref in summary["source_archives"]}
    for row in rows:
        original = json.loads(archives[row["raw_archive"]][row["raw_line"] - 1])
        payload = original["canonical_received_payload"]
        assert original["session_id"] == payload["session_id"] == row["session_id"]
        meta = read(PREPARED / "evaluation" / (row["opaque_id"] + ".json"))
        assert all(row[key] == meta[key] for key in ("phase", "config_id", "triplet_id", "environment_group_id", "session_id"))
        assert row["raw_archive"] == meta["source_ref"] + "/backend/raw_expanded_payloads.jsonl"
        for name, saved in row["graphics"].items():
            path = name.removeprefix("app.")
            current = payload
            for part in path.split("."):
                current = current[part]
            assert saved == {"value": current, "source_status": payload["collection_status"]["fields"][path]}
        for relation in row["relations"].values():
            assert relation["relation_applicability"]["status"] == "NOT_APPLICABLE"
            assert relation["relation_result"]["outcome"] == "NOT_APPLICABLE"
            assert relation["attribution_certainty"]["status"] == "UNKNOWN"
        assert row["relations"]["NW-005"]["risk_candidate_eligibility"]["status"] == "NOT_APPLICABLE"
        assert row["relations"]["OFFDER-GPU-001"]["risk_candidate_eligibility"]["status"] == "NOT_ELIGIBLE"
    for phase, expected in summary["by_phase"].items():
        part = [r for r in rows if r["phase"] == phase]
        assert len(part) == expected["n"]
        for name, counts in expected["observations"].items():
            assert Counter(r["observations"][name] for r in part) == counts
    changed = Counter()
    for triplet in triplets:
        pre, attack, post = (by_id[triplet["members"][phase]] for phase in ("clean_pre", "attack", "clean_post"))
        assert all(r["triplet_id"] == triplet["triplet_id"] for r in (pre, attack, post))
        actual = [name for name in pre["graphics"] if pre["graphics"][name] != attack["graphics"][name]]
        assert actual == triplet["changed_graphics_fields"]
        assert pre["graphics"] == post["graphics"] and triplet["graphics_restored"]
        if actual:
            assert set(actual) == {"app.web_data.graphics_layer.webgl_vendor", "app.web_data.graphics_layer.webgl_renderer"}
            changed[triplet["config_id"]] += 1
    assert len(triplets) == 126 and changed == {"w6-tool-058-legacy-default-v1": 9, "w9-stealth-boundary-webgl-pair-v1": 9}
    predictions = {}
    for model in baseline["models"]:
        path = ROOT / model["path"]
        current = read(path)
        assert model["model_id"] == current["model_id"] and len(current["clauses"]) == model["clauses"] == 7
        for row in lines(path.with_name("predictions.jsonl")):
            assert row["opaque_id"] not in predictions
            predictions[row["opaque_id"]] = row["decision"]
    assert set(predictions) == set(by_id)
    attacks = [r for r in rows if r["phase"] == "attack"]
    misses = [r for r in attacks if predictions[r["opaque_id"]] == "NO_ALERT"]
    markers = [r for r in rows if r["observations"]["lexical_web_desktop_backend_marker"] == "T"]
    assert len(markers) == 18 and all(r["phase"] == "attack" for r in markers)
    assert len(misses) == 9 and all(r["config_id"] == "w9-stealth-boundary-webgl-pair-v1" for r in misses)
    assert sum(predictions[r["opaque_id"]] == "MANIPULATION_ALERT" for r in markers) == 9
    assert baseline["saved_metrics"] == read(BASE / "RESULTS.json")["groups"]["CAP7"]
    browser = read(HERE / "BROWSER_CONTEXT_RESULT.json")
    assert browser["first_webgl_available"] and not browser["webgl2_on_same_canvas_after_webgl"] and browser["webgl2_on_fresh_canvas"]
    assert not read(HERE / "FEASIBILITY.json")["candidates_admitted_for_retraining"]
    return {"status": "PASS", "method": "Saved rows versus exact raw archive lines, contract membership, metadata, triplets and existing CAP7 outputs",
        "raw_rows_checked": len(rows), "graphics_fields_per_row": 12, "triplets_checked": len(triplets),
        "saved_CAP7_predictions_read": len(predictions), "diagnostic_marker_rows": len(markers),
        "marker_rows_already_alerted_by_CAP7": 9, "existing_CAP7_misses": len(misses),
        "new_relation_evaluations": 0, "new_fit_calls": 0, "new_model_prediction_calls": 0,
        "browser_context_reproduction": "Desktop browser result retained separately; Android capability not inferred"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write:
        with (HERE / "VERIFICATION.json").open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
