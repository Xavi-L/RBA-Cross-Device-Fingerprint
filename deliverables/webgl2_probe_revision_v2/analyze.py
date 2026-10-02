#!/usr/bin/env python3
"""Check saved normal controls; evaluate only two pre-existing relation scopes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "deliverables/rule_semantics_webgl_feasibility_v1"))
from audit import extract_graphics, load_registry, observations, projection, RULE_IDS
from hybridguard_agent.research.manipulation_eval.provenance_revision import evaluate_contract


def read(path):
    return json.loads(path.read_text())


def analyze(output_root=HERE):
    finished = read(output_root / "CONTROLS_FINISHED.json")
    registry = load_registry()
    result, cells = [], []
    for cell in finished["cells"]:
        name = f"api{cell['api']}_{cell['gpu']}"
        base = output_root / "controls" / name
        path = base / "backend/raw_expanded_payloads.jsonl"
        raw = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
        assert len(raw) == len(cell["captures"]), "Unaccounted received raw payload"
        for capture in cell["captures"]:
            payload = raw[capture["raw_line"] - 1]["canonical_received_payload"]
            assert payload["session_id"] == capture["session_id"]
            manifest, diagnostics = payload["collection_manifest"], payload["collection_diagnostics"]
            assert manifest["collector_version_code"] == 13
            assert manifest["web_probe_revision"] == diagnostics["web_probe_revision"] == "expanded-web-67-v2"
            assert manifest["upload_endpoint_origin"] == "http://127.0.0.1:8765"
            assert manifest["android_api"] == cell["api"]
            assert manifest["collection_round"] == capture["launch"]
            assert payload["collection_status"]["fixed_signal_count"] == 177
            assert len(payload["collection_status"]["fields"]) == 177
            graphics = extract_graphics(payload)
            projected = projection(graphics, registry)
            result.append({"cell": name, **capture, "raw_archive": str(path.relative_to(ROOT)),
                "field_status_counts": payload["collection_status"]["counts"],
                "webview_provider_version": manifest["webview_provider_version"],
                "graphics": graphics, "observations": observations(graphics),
                "relations": {rid: evaluate_contract(rid, projected, registry) for rid in RULE_IDS}})
        reused = [i for i in range(1, cell["launches"] + 1)
                  if (base / f"start-{i}.log").exists()
                  and "Activity not started" in (base / f"start-{i}.log").read_text()]
        cells.append({"cell": name, "planned": cell["launches"], "captured": len(raw),
                      "status": cell["status"], "error": cell.get("error"), "activity_reuse_warnings": reused})
    assert len({r["session_id"] for r in result}) == len(result)
    gl2 = "app.web_data.graphics_layer.webgl2_supported"
    summary = {
        "status": "COMPLETE" if all(c["status"] == "COMPLETE" for c in cells) else "COMPLETE_WITH_CAPTURE_LIMITATIONS",
        "planned_captures": sum(c["planned"] for c in cells), "received_captures": len(result),
        "fully_observed_177": sum(r["field_status_counts"]["observed"] == 177 for r in result),
        "webgl2_true_observed": sum(r["graphics"][gl2] == {"value": True, "source_status": "observed"} for r in result),
        "cells": cells,
        "observations": {key: dict(Counter(r["observations"][key] for r in result)) for key in result[0]["observations"]},
        "relations": {rid: {
            key: dict(Counter(r["relations"][rid][key]["status"] for r in result))
            for key in ("relation_applicability", "risk_candidate_eligibility")
        } for rid in RULE_IDS},
        "new_alert_candidates": 0, "new_model_fits": 0, "new_model_predictions": 0,
        "limits": ["Same Mac host; repeated launches are not independent devices",
                   "Declared benign controls are not independently adjudicated population labels",
                   "No real-device FPR, attack TPR, or model gain estimate from these controls",
                   "Historical v1 false values remain unchanged and semantically separate"]
    }
    return result, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create outputs once; otherwise verify saved outputs")
    parser.add_argument("--fresh-launch-check", action="store_true")
    args = parser.parse_args()
    output_root = HERE / "fresh_launch" if args.fresh_launch_check else HERE
    rows, summary = analyze(output_root)
    outputs = {"OBSERVATIONS.json": rows, "SUMMARY.json": summary}
    for filename, value in outputs.items():
        if args.write:
            with (output_root / filename).open("x") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        else:
            assert read(output_root / filename) == value, filename + " differs from raw controls"
    print(json.dumps(summary, ensure_ascii=False, indent=2))
