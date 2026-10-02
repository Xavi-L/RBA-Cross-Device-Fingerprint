#!/usr/bin/env python3
"""Paired mechanism evidence; never fit, predict, tune or admit a new rule."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("webgl_feasibility", ROOT / "deliverables/rule_semantics_webgl_feasibility_v1/audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
from hybridguard_agent.research.manipulation_eval.provenance_revision import evaluate_contract

TARGETS = ("app.web_data.graphics_layer.webgl_vendor", "app.web_data.graphics_layer.webgl_renderer")
NON_TARGETS = tuple(f for f in audit.FIELDS if f not in TARGETS)
PHASES = ("clean_pre", "attack", "clean_post")


def compare(left, right, fields=audit.FIELDS):
    unavailable = [f for f in fields if not audit.usable(left[f], f) or not audit.usable(right[f], f)]
    changed = [f for f in fields if f not in unavailable and left[f]["value"] != right[f]["value"]]
    return {"status": "UNAVAILABLE" if unavailable else "COMPARABLE", "unavailable_fields": unavailable,
            "changed_fields": changed, "equal": None if unavailable else not changed}


def triplet(phases, options):
    missing = [phase for phase in PHASES if phase not in phases]
    if missing:
        return {"status": "INCOMPLETE", "missing_phases": missing, "measured_effect": None,
                "all_graphics_restored": None, "non_target_graphics_unchanged": None}
    pre, attack, post = (phases[phase]["graphics"] for phase in PHASES)
    expected = dict(zip(TARGETS, (options["vendor"], options["renderer"])))
    target_compare = compare(pre, attack, TARGETS)
    target_values = all(audit.usable(attack[f], f) and attack[f]["value"] == v for f, v in expected.items())
    restoration = compare(pre, post)
    other = compare(pre, attack, NON_TARGETS)
    measured = (target_values and len(target_compare["changed_fields"]) == len(TARGETS)) if target_compare["status"] == "COMPARABLE" else None
    return {"status": "COMPLETE", "missing_phases": [], "target_values_observed": target_values,
            "measured_effect": measured, "target_pre_vs_attack": target_compare,
            "non_target_pre_vs_attack": other, "pre_vs_post": restoration,
            "all_graphics_restored": restoration["equal"], "non_target_graphics_unchanged": other["equal"]}


def read(path):
    return json.loads(path.read_text())


def analyze():
    protocol, start, finished = (read(HERE / filename) for filename in ("PROTOCOL.json", "STARTED.json", "FINISHED.json"))
    assert start["protocol"] == protocol
    registry = audit.load_registry()
    rows, triplets, path_reports = [], [], []
    for lifecycle in finished["paths"]:
        name = f"api{lifecycle['api']}_{lifecycle['gpu']}"
        base = HERE / "runs" / name
        source = base / "backend/raw_expanded_payloads.jsonl"
        raw = [json.loads(line) for line in source.read_text().splitlines() if line.strip()] if source.exists() else []
        capture_by_line = {r["raw_line"]: r for r in lifecycle["captures"]}
        accepted, unassigned = {}, []
        for number, envelope in enumerate(raw, 1):
            if number not in capture_by_line:
                unassigned.append(number)
                continue
            capture = capture_by_line[number]
            payload = envelope["canonical_received_payload"]
            assert payload["session_id"] == capture["session_id"]
            fields = payload["collection_status"]["fields"]
            counts = Counter(fields.values())
            assert len(fields) == payload["collection_status"]["fixed_signal_count"] == 177
            assert all(payload["collection_status"]["counts"].get(key) == count for key, count in counts.items())
            manifest = payload["collection_manifest"]
            assert manifest["web_probe_revision"] == payload["collection_diagnostics"]["web_probe_revision"] == protocol["collector"]["probe_revision"]
            assert manifest["collector_version_code"] == protocol["collector"]["version_code"]
            step_dir = base / "attempts" / capture["step_id"]
            attempt = read(step_dir / "ATTEMPT.json")
            assert attempt["status"] == "CAPTURED" and attempt["session_id"] == payload["session_id"]
            automation = None
            if capture["controlled"]:
                automation = read(step_dir / "AUTOMATION.json")
                expected_mode = "attack" if capture["phase"] == "attack" else "clean"
                assert automation["status"] == "NAVIGATED" and automation["mode"] == expected_mode
                expected_evasions = [protocol["intervention"]["evasion"]] if expected_mode == "attack" else []
                assert automation["enabled_evasions"] == expected_evasions
                assert automation["puppeteer-core"] == protocol["intervention"]["puppeteer_core_version"]
                assert automation[protocol["intervention"]["plugin"]] == protocol["intervention"]["version"]
                if expected_mode == "attack":
                    assert automation["options"] == protocol["intervention"]["options"]
            graphics = audit.extract_graphics(payload)
            projected = audit.projection(graphics, registry)
            row = {"path": name, **capture, "raw_archive": str(source.relative_to(ROOT)),
                   "field_status_counts": dict(counts), "graphics": graphics,
                   "canvas_hash": {"value": payload["web_data"]["graphics_layer"]["canvas_hash"],
                                   "source_status": fields["web_data.graphics_layer.canvas_hash"]},
                   "webview_provider_version": manifest["webview_provider_version"],
                   "observations": audit.observations(graphics),
                   "relations": {rid: evaluate_contract(rid, projected, registry) for rid in audit.RULE_IDS}}
            accepted[capture["step_id"]] = row
            rows.append(row)
        ordinary = accepted.get("ordinary")
        ordinary_comparisons = []
        for number in range(1, lifecycle["triplets"] + 1):
            phases = {phase: accepted[f"r{number}-{phase}"] for phase in PHASES if f"r{number}-{phase}" in accepted}
            triplets.append({"path": name, "round": number, "session_ids": {p: r["session_id"] for p, r in phases.items()},
                             **triplet(phases, protocol["intervention"]["options"])})
            if ordinary:
                ordinary_comparisons.extend({"step": phases[p]["step_id"], **compare(ordinary["graphics"], phases[p]["graphics"])}
                                            for p in ("clean_pre", "clean_post") if p in phases)
        path_reports.append({"path": name, "operational_status": lifecycle["status"],
            "captured": len(lifecycle["captures"]), "raw_rows": len(raw), "unassigned_raw_lines": unassigned,
            "ordinary_vs_matched_clean": ordinary_comparisons, "error": lifecycle.get("error")})
    assert len({r["session_id"] for r in rows}) == len(rows)
    by_phase = {}
    for phase in ("ordinary", *PHASES):
        group = [r for r in rows if r["phase"] == phase]
        by_phase[phase] = {"count": len(group),
            "graphics_all_observed": sum(all(audit.usable(c, f) for f, c in r["graphics"].items()) for r in group),
            "webgl2_observed_true": sum(r["graphics"]["app.web_data.graphics_layer.webgl2_supported"] == {"value": True, "source_status": "observed"} for r in group),
            "observations": {key: dict(Counter(r["observations"][key] for r in group)) for key in (rows[0]["observations"] if rows else [])},
            "relations": {rid: {key: dict(Counter(r["relations"][rid][key]["status"] for r in group))
                                for key in ("relation_applicability", "risk_candidate_eligibility")} for rid in audit.RULE_IDS}}
    complete = len(rows) == protocol["planned_payloads"] and all(p["operational_status"] == "COMPLETE" and not p["unassigned_raw_lines"] for p in path_reports)
    summary = {"status": "COMPLETE" if complete else "INCOMPLETE_OR_FAILED", "planned_payloads": protocol["planned_payloads"],
        "captured_payloads": len(rows), "fully_observed_177": sum(r["field_status_counts"].get("observed") == 177 for r in rows),
        "planned_triplets": sum(c["triplets"] for c in protocol["matrix"]),
        "complete_triplets": sum(t["status"] == "COMPLETE" for t in triplets),
        "measured_intervention_triplets": sum(t["measured_effect"] is True for t in triplets),
        "restored_triplets": sum(t["all_graphics_restored"] is True for t in triplets),
        "non_target_graphics_unchanged_triplets": sum(t["non_target_graphics_unchanged"] is True for t in triplets),
        "paths": path_reports, "by_phase": by_phase,
        "new_alert_candidates": 0, "model_fits": 0, "model_predictions": 0,
        "inference_boundary": "Intervention effects and restoration are measured, not detector TPR, FPR or independent attack truth. No new rule admitted."}
    return {"ROWS.json": rows, "TRIPLETS.json": triplets, "SUMMARY.json": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = analyze()
    for name, data in outputs.items():
        if args.write:
            with (HERE / name).open("x") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        else:
            assert read(HERE / name) == data, name
    print(json.dumps(outputs["SUMMARY.json"], ensure_ascii=False, indent=2))
