#!/usr/bin/env python3
"""Read-only semantic review checks; --write saves outputs in this directory.

Uses ten explicit synthetic boundaries and twenty existing paired observations.
Never loads a model, fits, predicts, collects data, or changes a rule registry.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location(
    "existing_gpu_audit", ROOT / "deliverables/rule_semantics_webgl_feasibility_v1/audit.py"
)
gpu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gpu)


def read(path):
    return json.loads(path.read_text())


def check():
    sources = read(HERE / "SOURCE_REGISTER.json")["sources"]
    source_ids = {s["id"] for s in sources}
    assert len(source_ids) == len(sources)
    anchors_checked = 0
    for source in sources:
        path = (HERE if source["root"] == "review" else ROOT) / source["local_path"]
        lines = path.read_text().splitlines()
        for anchor in source["anchors"]:
            assert anchor["contains"] in lines[anchor["line"] - 1], source["id"]
            anchors_checked += 1
    revision = "914c97c116e09ef01a99fbbbe9cd28cda56552c7"
    assert revision in (HERE / "sources/chromium134_deps.txt").read_text()
    assert all(s["revision"] == revision for s in sources if s["id"].startswith("angle_"))
    counterexamples = read(HERE / "COUNTEREXAMPLES.json")["cases"]
    case_ids = {c["id"] for c in counterexamples}
    assert len(case_ids) == len(counterexamples)
    for case in counterexamples:
        assert set(case["sources"]) <= source_ids
    cards = read(HERE / "CANDIDATE_CARDS.json")
    assert cards["new_alert_candidates"] == cards["model_fits"] == cards["model_predictions"] == 0
    assert cards["registry_changed"] is False
    for card in cards["cards"]:
        assert set(card["evidence_sources"]) <= source_ids
        assert set(card["counterexample_cases"]) <= case_ids

    registry = gpu.load_registry()
    roles = {s["rule_id"]: s["decision_role"] for s in registry["scopes"]}
    assert roles == {"NW-005": "alert_candidate", "OFFDER-GPU-001": "observation_only"}
    assert gpu.GPU_PARAMS["families"] == ["adreno", "mali", "powervr", "tegra", "vivante"]
    outputs = []
    synthetic = read(HERE / "BOUNDARY_CASES.json")
    assert synthetic["kind"] == "SYNTHETIC_BOUNDARY_CASES_NOT_EXPERIMENTAL_SAMPLES"
    for case in synthetic["cases"]:
        graphics = {f: {"value": None, "source_status": "STATUS_MISSING"} for f in gpu.FIELDS}
        for field, value in ((gpu.NATIVE + "native_gpu_renderer", case["native"]),
                             (gpu.NATIVE + "egl_renderer", case["native"]),
                             (gpu.WEB + "webgl_renderer", case["web"]),
                             (gpu.WEB + "webgl_vendor", "fixture-vendor")):
            graphics[field] = {"value": value, "source_status": "observed"}
        graphics[gpu.WEB + "webgl_renderer"]["source_status"] = case.get("web_status", "observed")
        observations = gpu.observations(graphics)
        assert observations["native_web_renderer_text_unequal"] == case["text_unequal"], case["id"]
        assert observations["lexical_web_desktop_backend_marker"] == case["marker"], case["id"]
        projected = gpu.projection(graphics, registry)
        relations = {rid: gpu.evaluate_contract(rid, projected, registry) for rid in gpu.RULE_IDS}
        family, backend = (relations[rid] for rid in gpu.RULE_IDS)
        assert family["relation_result"]["outcome"] == case["family_outcome"], case["id"]
        assert family["risk_candidate_eligibility"]["status"] == case["family_eligibility"], case["id"]
        assert backend["relation_result"]["outcome"] == case["backend_outcome"], case["id"]
        assert backend["risk_candidate_eligibility"]["status"] == "NOT_ELIGIBLE", case["id"]
        assert all(r["attribution_certainty"]["status"] == "UNKNOWN" and
                   r["attribution_certainty"]["attack_proven"] is False for r in relations.values())
        outputs.append({"id": case["id"], "kind": "SYNTHETIC_NOT_A_SAMPLE", "status": "PASS",
                        "observations": observations, "relations": relations})

    rows = read(ROOT / "deliverables/webgl2_paired_paths_v1/ROWS.json")
    raw_by_path = {}
    for row in rows:
        path = row["raw_archive"]
        if path not in raw_by_path:
            raw_by_path[path] = [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line.strip()]
        payload = raw_by_path[path][row["raw_line"] - 1]["canonical_received_payload"]
        assert payload["session_id"] == row["session_id"]
        graphics = gpu.extract_graphics(payload)
        assert graphics == row["graphics"]
        assert gpu.observations(graphics) == row["observations"]
        projected = gpu.projection(graphics, registry)
        assert {rid: gpu.evaluate_contract(rid, projected, registry) for rid in gpu.RULE_IDS} == row["relations"]
    assert len(rows) == 20 and len({r["session_id"] for r in rows}) == 20
    counts = {}
    for group, selected in (("intervention", [r for r in rows if r["phase"] == "attack"]),
                            ("ordinary_or_matched_clean", [r for r in rows if r["phase"] != "attack"])):
        counts[group] = {"n": len(selected), **{k: dict(Counter(r["observations"][k] for r in selected))
                            for k in ("native_web_renderer_text_unequal", "lexical_web_desktop_backend_marker")}}
    assert counts["intervention"] == {"n": 6, "native_web_renderer_text_unequal": {"T": 6},
                                       "lexical_web_desktop_backend_marker": {"T": 6}}
    assert counts["ordinary_or_matched_clean"] == {"n": 14, "native_web_renderer_text_unequal": {"F": 14},
                                                  "lexical_web_desktop_backend_marker": {"F": 14}}
    scope_counts = dict(Counter(r["relations"]["NW-005"]["relation_applicability"]["status"] for r in rows))
    assert scope_counts == {"UNKNOWN": 10, "NOT_APPLICABLE": 10}
    assert all(r["relations"]["OFFDER-GPU-001"]["risk_candidate_eligibility"]["status"] == "NOT_ELIGIBLE" for r in rows)
    assert all(r["graphics"][gpu.NATIVE + "native_gpu_renderer"] == r["graphics"][gpu.NATIVE + "egl_renderer"] for r in rows)
    baseline = read(ROOT / "deliverables/rule_semantics_capacity_comparison_v1/RESULTS.json")["groups"]["CAP7"]
    snapshot = {k: baseline[k] for k in ("attack_alerts", "attack_n", "clean_alerts", "clean_n", "defined", "expected")}
    assert snapshot == dict(attack_alerts=117, attack_n=126, clean_alerts=0, clean_n=252, defined=378, expected=378)
    summary = {"review_id": "renderer-semantics-review-v1", "status": "PASS",
               "source_entries": len(sources), "source_anchors_checked": anchors_checked,
               "candidate_cards": len(cards["cards"]), "counterexample_entries": len(counterexamples),
               "synthetic_boundary_cases_passed": len(outputs), "prior_raw_rows_checked": len(rows),
               "prior_controlled_observation_counts": counts, "prior_NW_005_applicability": scope_counts,
               "saved_CAP7_context_not_rerun": snapshot,
               "new_alert_candidates": 0, "new_runtime_samples": 0, "model_fits": 0, "model_predictions": 0,
               "new_TPR_or_FPR": "NOT_EVALUATED", "independent_confirmation": "NOT_ACCESSED",
               "binary_build_linkage": "NOT_VERIFIED"}
    return {"BOUNDARY_RESULTS.json": outputs, "SUMMARY.json": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Save only this review's result JSON files.")
    args = parser.parse_args()
    outputs = check()
    for name, data in outputs.items():
        if args.write:
            (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        else:
            assert read(HERE / name) == data, "Saved review differs: " + name
    print(json.dumps(outputs["SUMMARY.json"], ensure_ascii=False, indent=2))
