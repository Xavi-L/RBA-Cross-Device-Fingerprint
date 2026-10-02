#!/usr/bin/env python3
"""Analyze saved feasibility records; no collection, fitting, or prediction."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
from classify import classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("previous_graphics_audit", ROOT / "deliverables/rule_semantics_webgl_feasibility_v1/audit.py")
gpu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gpu)
PHASES = ("clean_pre", "attack", "clean_post")
CONTEXTS = ("webgl", "webgl2")
TARGETS = (gpu.WEB + "webgl_vendor", gpu.WEB + "webgl_renderer")


def read(path):
    return json.loads(path.read_text())


def compare(left, right, fields):
    if not all(gpu.usable(left[f], f) and gpu.usable(right[f], f) for f in fields):
        return None
    return all(left[f]["value"] == right[f]["value"] for f in fields)


def analyze():
    protocol = read(HERE / "PROTOCOL.json")
    assert read(HERE / "STARTED.json")["protocol"] == protocol
    for name in ("PROTOCOL.json", "probe.js", "classify.py", "attach_probe.mjs", "run_pairs.py"):
        assert (HERE / name).read_bytes() == (HERE / "source_snapshot" / name).read_bytes(), name + " changed since start"
    finished = read(HERE / "FINISHED.json")
    rows, triplets, failures = [], [], []
    for run in finished["paths"]:
        path = f"api{run['api']}_{run['gpu']}"
        directory = HERE / "runs" / path
        raw_path = directory / "backend/raw_expanded_payloads.jsonl"
        raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()] if raw_path.exists() else []
        captures = {a["step_id"]: a for a in run["captures"]}
        path_rows = {}
        for step, capture in captures.items():
            attempt_dir = directory / "attempts" / step
            attempt, automation, behavior = (read(attempt_dir / name) for name in ("ATTEMPT.json", "AUTOMATION.json", "BEHAVIOR.json"))
            payload = raw[capture["raw_line"] - 1]["canonical_received_payload"]
            sid = payload["session_id"]
            assert attempt["status"] == "CAPTURED"
            assert capture["session_id"] == attempt["session_id"] == behavior["session_id"] == behavior["session_id_after"] == automation["behavior_session_id"] == sid
            assert automation["status"] == "MEASURED_AND_NAVIGATED"
            assert automation["enabled_evasions"] == ([protocol["intervention"]["evasion"]] if capture["phase"] == "attack" else [])
            assert automation[protocol["intervention"]["plugin"]] == protocol["intervention"]["version"]
            if capture["phase"] == "attack":
                assert automation["options"] == protocol["intervention"]["options"]
            manifest = payload["collection_manifest"]
            assert manifest["collector_version_code"] == protocol["collector"]["version_code"]
            assert behavior["schema"] == protocol["sidecar_schema"]
            assert behavior["canonical_probe_revision"] == manifest["web_probe_revision"] == protocol["collector"]["probe_revision"]
            assert behavior["url"] == "file:///android_asset/expanded_probe.html"
            assert len(payload["collection_status"]["fields"]) == 177
            assert [c["type"] for c in behavior["contexts"]] == list(CONTEXTS)
            graphics = gpu.extract_graphics(payload)
            outcomes = {c["type"]: classify(c) for c in behavior["contexts"]}
            contexts = {c["type"]: c for c in behavior["contexts"]}
            same = {}
            for context_type, c in contexts.items():
                enabled = c.get("extension_enabled", {})
                same[context_type] = all(enabled.get(name, {}).get("numeric_before", {}).get("value") == graphics[f]["value"]
                                         and gpu.usable(graphics[f], f) for name, f in zip(("vendor", "renderer"), TARGETS))
            row = {"path": path, **capture, "raw_source": str(raw_path.relative_to(ROOT)),
                   "sidecar_source": str((attempt_dir / "BEHAVIOR.json").relative_to(ROOT)),
                   "webview_provider_version": manifest["webview_provider_version"],
                   "observed_fields": sum(v == "observed" for v in payload["collection_status"]["fields"].values()),
                   "graphics": graphics, "outcomes": outcomes, "contexts": contexts,
                   "numeric_sidecar_matches_canonical": same}
            rows.append(row); path_rows[step] = row
        if run["status"] != "COMPLETE" or len(raw) != len(captures):
            failures.append({"path": path, "status": run["status"], "error": run.get("error"), "raw": len(raw), "captured": len(captures)})
        for number in range(1, run["triplets"] + 1):
            stages = {phase: path_rows.get(f"r{number}-{phase}") for phase in PHASES}
            if not all(stages.values()):
                triplets.append({"path": path, "round": number, "status": "INCOMPLETE",
                                 "missing": [p for p, v in stages.items() if not v]})
                continue
            pre, attack, post = (stages[p] for p in PHASES)
            expected = dict(zip(TARGETS, (protocol["intervention"]["options"][k] for k in ("vendor", "renderer"))))
            usable = all(gpu.usable(row["graphics"][f], f) for row in (pre, attack, post) for f in gpu.FIELDS)
            effect = (all(attack["graphics"][f]["value"] == value and pre["graphics"][f]["value"] != value
                          for f, value in expected.items()) if usable else None)
            states = {p: {t: stages[p]["outcomes"][t]["behavior_relation"] for t in CONTEXTS} for p in PHASES}
            separation = all(states[p][t] == ("COUNTEREXAMPLE" if p == "attack" else "MATCH") for p in PHASES for t in CONTEXTS)
            triplets.append({"path": path, "round": number, "status": "COMPLETE", "session_ids": {p: r["session_id"] for p, r in stages.items()},
                             "target_effect": effect, "raw_graphics_restored": compare(pre["graphics"], post["graphics"], gpu.FIELDS),
                             "non_target_graphics_unchanged": compare(pre["graphics"], attack["graphics"], tuple(f for f in gpu.FIELDS if f not in TARGETS)),
                             "sidecar_contexts_restored": pre["contexts"] == post["contexts"], "behavior_states": states,
                             "behavior_separation_observed": separation})
    assert len({r["session_id"] for r in rows}) == len(rows)
    by_phase = {}
    for phase in PHASES:
        group = [r for r in rows if r["phase"] == phase]
        by_phase[phase] = {"collections": len(group), "contexts": {
            t: {key: dict(Counter(r["outcomes"][t][key] for r in group)) for key in
                ("extension_gate", "argument_coercion", "capability_control", "render_control", "behavior_relation")}
            for t in CONTEXTS}}
    completed = [t for t in triplets if t["status"] == "COMPLETE"]
    complete = not failures and len(rows) == protocol["planned_payloads"] and len(completed) == 4
    feasible = complete and all(t["target_effect"] is True and t["raw_graphics_restored"] is True
                               and t["sidecar_contexts_restored"] is True and t["behavior_separation_observed"] is True for t in completed)
    summary = {"status": "COMPLETE" if complete else "INCOMPLETE_OR_FAILED", "planned_payloads": protocol["planned_payloads"],
               "captured_payloads": len(rows), "fully_observed_177": sum(r["observed_fields"] == 177 for r in rows),
               "planned_triplets": 4, "complete_triplets": len(completed),
               "measured_effect_triplets": sum(t["target_effect"] is True for t in completed),
               "raw_restored_triplets": sum(t["raw_graphics_restored"] is True for t in completed),
               "sidecar_restored_triplets": sum(t["sidecar_contexts_restored"] is True for t in completed),
               "behavior_separated_triplets": sum(t["behavior_separation_observed"] for t in completed),
               "non_target_graphics_unchanged_triplets": sum(t["non_target_graphics_unchanged"] is True for t in completed),
               "feasibility": "SUPPORTED_FOR_VERSIONED_OBSERVATION_DESIGN" if feasible else "NOT_ESTABLISHED",
               "by_phase": by_phase, "failures": failures,
               "model_fits": 0, "model_predictions": 0, "new_registered_alert_candidates": 0,
               "independent_confirmation": "NOT_ACCESSED", "overall_model_improvement": "NOT_EVALUATED",
               "boundary": "One existing plugin configuration, one Mac, one WebView version, two rendering paths; phase counts are not independent TPR/FPR. Extension gating and argument coercion share one implementation defect."}
    return {"ROWS.json": rows, "TRIPLETS.json": triplets, "SUMMARY.json": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    results = analyze()
    for name, data in results.items():
        if args.write:
            (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        else:
            assert read(HERE / name) == data, "Saved result differs: " + name
    print(json.dumps(results["SUMMARY.json"], ensure_ascii=False, indent=2))
