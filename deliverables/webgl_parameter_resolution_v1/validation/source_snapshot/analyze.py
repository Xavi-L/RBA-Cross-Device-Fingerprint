#!/usr/bin/env python3
"""Reproduce the frozen environment validation; never train or predict a model."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
PHASES = ("clean_pre", "attack", "clean_post")
CONTEXTS = ("webgl", "webgl2")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


gpu = module("graphics_fields", ROOT / "deliverables/rule_semantics_webgl_feasibility_v1/audit.py")
TARGETS = (gpu.WEB + "webgl_vendor", gpu.WEB + "webgl_renderer")


def read(path):
    return json.loads(path.read_text())


def validate_binding(binding, observation, session_id, revision):
    """Session expectation is from the received App row, never the observation itself."""
    if not isinstance(binding, dict) or not isinstance(observation, dict):
        return False
    return (binding.get("session_id_before") == binding.get("session_id_after") == session_id
            and isinstance(session_id, str) and bool(session_id)
            and binding.get("url_before") == binding.get("url_after") == "file:///android_asset/expanded_probe.html"
            and binding.get("canonical_probe_revision") == revision
            and observation.get("realm_binding") == "featureapp:" + session_id + ":main-frame")


def compare(left, right, fields):
    if not all(gpu.usable(left[f], f) and gpu.usable(right[f], f) for f in fields):
        return None
    return all(left[f]["value"] == right[f]["value"] for f in fields)


def triplet_passes(row):
    return row.get("status") == "COMPLETE" and all(row.get(key) is True for key in (
        "target_effect", "raw_graphics_restored", "non_target_graphics_unchanged",
        "sidecar_contexts_restored", "relation_separation_observed", "canonical_webgl1_link"))


def environment_gate(triplets, expected, execution_complete):
    return (execution_complete and len(triplets) == expected
            and all(triplet_passes(row) for row in triplets))


def phase_counts(rows):
    return {phase: {"collections": len(group := [r for r in rows if r["phase"] == phase]),
                    "aggregate": dict(Counter(r["evaluation"]["outcome"] for r in group)),
                    "contexts": {context: {
                        "outcomes": dict(Counter(r["evaluation"]["contexts"].get(context, {}).get("outcome", "UNKNOWN") for r in group)),
                        "unknown_reasons": dict(Counter(r["evaluation"]["contexts"].get(context, {}).get("reason", r["evaluation"]["reason"])
                            for r in group if r["evaluation"]["contexts"].get(context, {}).get("outcome", "UNKNOWN") == "UNKNOWN"))}
                        for context in CONTEXTS}}
            for phase in PHASES}


def analyze():
    protocol = read(HERE / "PROTOCOL.json")
    assert read(HERE / "STARTED.json")["protocol"] == protocol
    snapshot = HERE / "source_snapshot"
    sources = [HERE / name for name in ("PROTOCOL.json", "attach_probe.mjs", "run_pairs.py", "analyze.py")]
    sources += [ROOT / protocol["observer"][key] for key in ("source", "evaluator")]
    for source in sources:
        assert source.read_bytes() == (snapshot / source.name).read_bytes(), str(source) + " changed since start"
    evaluator = module("frozen_parameter_evaluator", snapshot / "webgl_parameter_equivalence.py")
    assert evaluator.EVALUATOR_REVISION == protocol["observer"]["evaluator_revision"]
    finished = read(HERE / "FINISHED.json")
    assert [{k: run[k] for k in cell} for cell, run in zip(protocol["matrix"], finished["paths"])] == protocol["matrix"]
    assert len(finished["paths"]) == len(protocol["matrix"])
    rows, triplets, failures, environments = [], [], [], []
    for run in finished["paths"]:
        cell = f"api{run['api']}_{run['gpu']}"
        directory = HERE / "runs" / cell
        raw_path = directory / "backend/raw_expanded_payloads.jsonl"
        raw = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()] if raw_path.exists() else []
        captures = {capture["step_id"]: capture for capture in run["captures"]}
        assert len(captures) == len(run["captures"])
        path_rows, observations = {}, {}
        for step, capture in captures.items():
            attempt_dir = directory / "attempts" / step
            attempt, automation, observation, binding = (read(attempt_dir / name) for name in (
                "ATTEMPT.json", "AUTOMATION.json", "OBSERVATION.json", "BINDING.json"))
            payload = raw[capture["raw_line"] - 1]["canonical_received_payload"]
            session_id, manifest = payload["session_id"], payload["collection_manifest"]
            assert attempt["status"] == "CAPTURED"
            assert session_id == capture["session_id"] == attempt["session_id"] == automation["observation_session_id"]
            assert automation["status"] == "MEASURED_AND_NAVIGATED"
            assert automation["enabled_evasions"] == ([protocol["intervention"]["evasion"]] if capture["phase"] == "attack" else [])
            for name, version in ((protocol["intervention"]["plugin"], protocol["intervention"]["version"]),
                                  ("puppeteer-core", protocol["intervention"]["puppeteer_core_version"])):
                assert automation[name] == version
            if capture["phase"] == "attack":
                assert automation["options"] == protocol["intervention"]["options"]
            assert manifest["android_api"] == run["api"]
            assert manifest["collector_version_code"] == protocol["collector"]["version_code"]
            assert manifest["web_probe_revision"] == protocol["collector"]["probe_revision"]
            bound = validate_binding(binding, observation, session_id, manifest["web_probe_revision"])
            evaluation = (evaluator.evaluate_observation(observation, expected_realm_binding="featureapp:" + session_id + ":main-frame")
                          if bound else {"outcome": "UNKNOWN", "reason": "CAPTURE_BINDING_INVALID", "contexts": {},
                                         "decision_role": "observation_only", "evaluator_revision": evaluator.EVALUATOR_REVISION})
            graphics = gpu.extract_graphics(payload)
            # Canonical graphics reads WebGL1. WebGL2 need not expose identical strings.
            numeric_links = {}
            for context in observation["contexts"]:
                numeric_links[context["context_type"]] = all(
                    gpu.usable(graphics[field], field)
                    and context.get("parameters", {}).get(name, {}).get(query, {}).get("value") == graphics[field]["value"]
                    for name, field in zip(("vendor", "renderer"), TARGETS)
                    for query in ("numeric_before", "numeric_after"))
            row = {"cell": cell, **capture, "raw_source": str(raw_path.relative_to(ROOT)),
                   "observation_source": str((attempt_dir / "OBSERVATION.json").relative_to(ROOT)),
                   "binding_valid": bound, "webview_provider_package": manifest["webview_provider_package"],
                   "webview_provider_version": manifest["webview_provider_version"],
                   "observed_fields": sum(v == "observed" for v in payload["collection_status"]["fields"].values()),
                   "graphics": graphics, "evaluation": evaluation, "numeric_sidecar_matches_canonical": numeric_links}
            rows.append(row); path_rows[step] = row; observations[step] = observation
        complete = run["status"] == "COMPLETE" and len(raw) == len(captures) == run["triplets"] * 3
        if not complete:
            failures.append({"cell": cell, "status": run["status"], "error": run.get("error"), "raw": len(raw), "captured": len(captures)})
        cell_triplets = []
        for number in range(1, run["triplets"] + 1):
            stages = {phase: path_rows.get(f"r{number}-{phase}") for phase in PHASES}
            if not all(stages.values()):
                item = {"cell": cell, "round": number, "status": "INCOMPLETE", "missing": [p for p, v in stages.items() if not v]}
            else:
                pre, attack, post = (stages[p] for p in PHASES)
                expected = dict(zip(TARGETS, (protocol["intervention"]["options"][key] for key in ("vendor", "renderer"))))
                usable = all(gpu.usable(row["graphics"][field], field) for row in (pre, attack, post) for field in gpu.FIELDS)
                effect = (all(attack["graphics"][field]["value"] == value and pre["graphics"][field]["value"] != value
                              for field, value in expected.items()) if usable else None)
                states = {p: stages[p]["evaluation"]["outcome"] for p in PHASES}
                item = {"cell": cell, "round": number, "status": "COMPLETE",
                        "session_ids": {p: r["session_id"] for p, r in stages.items()}, "target_effect": effect,
                        "raw_graphics_restored": compare(pre["graphics"], post["graphics"], gpu.FIELDS),
                        "non_target_graphics_unchanged": compare(pre["graphics"], attack["graphics"], tuple(f for f in gpu.FIELDS if f not in TARGETS)),
                        "sidecar_contexts_restored": observations[f"r{number}-clean_pre"]["contexts"] == observations[f"r{number}-clean_post"]["contexts"],
                        "relation_states": states,
                        "relation_separation_observed": all(states[p] == ("COUNTEREXAMPLE" if p == "attack" else "MATCH") for p in PHASES),
                        "canonical_webgl1_link": all(r["binding_valid"] and r["numeric_sidecar_matches_canonical"].get("webgl") is True for r in stages.values())}
            item["positive_triplet"] = triplet_passes(item)
            cell_triplets.append(item)
        triplets.extend(cell_triplets)
        environments.append({"cell": cell, "api": run["api"], "gpu": run["gpu"],
                             "environment_identity": run.get("environment_identity"),
                             "execution_complete": complete, "planned_triplets": run["triplets"],
                             "positive_triplets": sum(t["positive_triplet"] for t in cell_triplets),
                             "environment_gate": "PASS" if environment_gate(cell_triplets, run["triplets"], complete) else "NOT_ESTABLISHED",
                             "by_phase": phase_counts(list(path_rows.values()))})
    assert len({row["session_id"] for row in rows}) == len(rows)
    complete = not failures and len(rows) == protocol["planned_payloads"]
    overall_gate = complete and all(e["environment_gate"] == "PASS" for e in environments)
    completed = [t for t in triplets if t["status"] == "COMPLETE"]
    summary = {"protocol_version": protocol["protocol_version"], "status": "COMPLETE" if complete else "INCOMPLETE_OR_FAILED",
               "planned_payloads": protocol["planned_payloads"], "captured_payloads": len(rows),
               "fully_observed_177": sum(row["observed_fields"] == 177 for row in rows),
               "planned_triplets": protocol["planned_triplets"], "complete_triplets": len(completed),
               "positive_triplets": sum(t["positive_triplet"] for t in triplets),
               "measured_effect_triplets": sum(t["target_effect"] is True for t in completed),
               "raw_restored_triplets": sum(t["raw_graphics_restored"] is True for t in completed),
               "sidecar_restored_triplets": sum(t["sidecar_contexts_restored"] is True for t in completed),
               "non_target_graphics_unchanged_triplets": sum(t["non_target_graphics_unchanged"] is True for t in completed),
               "versioned_observer_environment_gate": "PASS_MEASURED_LOCAL_CONFIGURATIONS" if overall_gate else "NOT_ESTABLISHED_FOR_FULL_MATRIX",
               "webview_versions": sorted({row["webview_provider_version"] for row in rows}),
               "environments": environments, "by_phase": phase_counts(rows), "failures": failures,
               "model_fits": 0, "model_predictions": 0, "new_registered_alert_candidates": 0,
               "independent_confirmation": "NOT_ACCESSED", "overall_model_improvement": "NOT_EVALUATED",
               "boundary": protocol["analysis"]["inference_boundary"]}
    return {"ROWS.json": rows, "TRIPLETS.json": triplets, "SUMMARY.json": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = analyze()
    for name, data in outputs.items():
        if args.write:
            with (HERE / name).open("x") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2); stream.write("\n")
        else:
            assert read(HERE / name) == data, "Saved output differs: " + name
    print(json.dumps(outputs["SUMMARY.json"], ensure_ascii=False, indent=2))
