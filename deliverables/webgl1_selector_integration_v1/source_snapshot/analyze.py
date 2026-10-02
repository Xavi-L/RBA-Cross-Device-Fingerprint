#!/usr/bin/env python3
"""Replay default App storage and compilation checks; no fit/model prediction."""
from collections import Counter
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research import webgl1_selector_integration as integration
from hybridguard_agent.research.rule_learning.models import Clause, Literal
from hybridguard_agent.research.rule_learning.predictor import clause_state
from hybridguard_agent.research.rule_learning_v2.adapter import approved_atoms
from hybridguard_agent.research.rule_learning_v2.semantic_selection import semantic_catalog
from hybridguard_agent.research.rule_semantics_capacity import group_definitions


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def analyze():
    protocol = read(HERE / "PROTOCOL.json")
    assert read(HERE / "STARTED.json")["protocol"] == protocol
    finished = read(HERE / "FINISHED.json")
    source = integration.SourceRegistration("deliverables/webgl1_selector_integration_v1/PROTOCOL.json")
    atom = integration.registered_atom()
    catalog = semantic_catalog([atom])
    write("REGISTRATION.json", {"atom": asdict(atom), "semantics": catalog[atom.atom_id],
                                "source_registration": asdict(source), "role": "OPT_IN_REGISTERED_CANDIDATE_NOT_SELECTED_MODEL_RULE"})
    # Read metadata definitions only, never old sample outcomes or fit inputs.
    prior = read(ROOT / "deliverables/rule_semantics_capacity_comparison_v1/CONTRACT.json")
    base = group_definitions(read(ROOT / prior["source_directory"] / "DEFINITIONS.json"), "LANG_ADD_WD_REPLACE")
    extended = integration.register_definitions(base)
    base_atoms, extended_atoms = approved_atoms(base), approved_atoms(extended)
    assert len(extended_atoms) == len(base_atoms) + 1
    assert extended["atoms"][:-1] == base["atoms"]
    write("SELECTOR_POOL_COMPATIBILITY.json", {"base_atoms": len(base_atoms), "extended_atoms": len(extended_atoms),
        "base_definitions_unchanged": True, "candidate_present": atom.atom_id in {a.atom_id for a in extended_atoms},
        "pool_extension": "OPT_IN_ONLY", "old_experiment_groups_changed": False, "fit_called": False})
    field_file = ROOT / "android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv"
    with field_file.open() as stream:
        fields = {r["field"] for r in csv.DictReader(stream) if r["field"].startswith(("android_native_data.", "webview_data.", "web_data."))}
    assert len(fields) == 177
    rows, triplets, failures = [], [], []
    saved = {}
    for run in finished["paths"]:
        environment = f"api{run['api']}_{run['gpu']}"
        directory = HERE / "runs" / environment
        raw = lines(directory / "backend/raw_expanded_payloads.jsonl")
        exports = {r["session_id"]: r for r in lines(directory / "backend/expanded_collected_data.jsonl")}
        receipts = {r["session_id"]: r for r in lines(directory / "backend/collection_receipts.jsonl")}
        merged_path = directory / "backend/expanded_merged_sessions.json"
        merged = read(merged_path) if merged_path.exists() else {}
        captured = {}
        if run["status"] != "COMPLETE" or len(raw) != run["triplets"] * 3:
            failures.append({"environment": environment, "status": run["status"], "error": run.get("error")})
        for capture in run["captures"]:
            step = directory / "attempts" / capture["step_id"]
            payload = raw[capture["raw_line"] - 1]["canonical_received_payload"]
            binding, automation = read(step / "BINDING.json"), read(step / "AUTOMATION.json")
            sid = capture["session_id"]
            assert sid == payload["session_id"] == binding["session_id"] == automation["observation_session_id"]
            assert automation["observer_injected_or_manually_called"] is False
            assert automation["status"] == "NAVIGATED_DEFAULT_APP_COLLECTION"
            assert automation["enabled_evasions"] == ([protocol["intervention"]["evasion"]] if capture["phase"] == "attack" else [])
            assert binding["url"] == "file:///android_asset/expanded_probe.html"
            assert binding["packaged_observer_present"] is True
            assert set(payload["collection_status"]["fields"]) == fields
            assert sid not in saved and sid in receipts and receipts[sid]["raw_payload_archived"] is True
            expected_sid = receipts[sid]["session_id"]
            compiled = integration.compile_payload(payload, expected_session_id=expected_sid, source_registration=source)
            feature = integration.kernel_cell(compiled)
            assert clause_state(Clause((Literal(atom.atom_id),)), {atom.atom_id: feature}) == compiled["state"]
            assert payload["collection_observations"] == exports[sid]["collection_observations"] == merged[sid]["collection_observations"]
            assert integration.compile_payload(exports[sid], expected_session_id=expected_sid, source_registration=source) == compiled
            assert integration.compile_payload(merged[sid], expected_session_id=expected_sid, source_registration=source) == compiled
            manifest = payload["collection_manifest"]
            graphics = payload["web_data"]["graphics_layer"]
            observation = payload["collection_observations"]["webgl_parameter"]["observation"]
            context = observation["contexts"][0]
            linked = all(context.get("parameters", {}).get(name, {}).get(query, {}).get("value") == graphics.get("webgl_" + name)
                for name in ("vendor", "renderer") for query in ("numeric_before", "numeric_after"))
            row = {"environment": environment, **capture, "state": compiled["state"], "reason": compiled["reason"],
                   "webview_version": manifest["webview_provider_version"],
                   "observed_fields": sum(v == "observed" for v in payload["collection_status"]["fields"].values()),
                   "full_observation_outcome": compiled["diagnostics"].get("full_observation_outcome"),
                   "webgl2_outcome": compiled["diagnostics"].get("webgl2", {}).get("outcome"),
                   "webgl1_numeric_links_canonical": linked, "storage_roundtrip": True,
                   "raw_file": str((directory / "backend/raw_expanded_payloads.jsonl").relative_to(ROOT))}
            saved[sid] = compiled
            rows.append(row)
            captured[capture["phase"]] = (row, graphics, context)
        if set(captured) != {"clean_pre", "attack", "clean_post"}:
            triplets.append({"environment": environment, "status": "INCOMPLETE"})
            continue
        pre, attack, post = (captured[p] for p in ("clean_pre", "attack", "clean_post"))
        targets = {"webgl_" + name: protocol["intervention"]["options"][name] for name in ("vendor", "renderer")}
        other = set(pre[1]) - set(targets)
        checks = {
            "states_F_T_F": [r[0]["state"] for r in (pre, attack, post)] == ["F", "T", "F"],
            "raw_target_effect": all(attack[1][k] == v and pre[1][k] != v for k, v in targets.items()),
            "raw_graphics_restored": pre[1] == post[1],
            "other_10_graphics_unchanged": len(other) == 10 and all(pre[1][k] == attack[1][k] == post[1][k] for k in other),
            "webgl1_observation_restored": pre[2] == post[2],
            "canonical_links": all(r[0]["webgl1_numeric_links_canonical"] for r in (pre, attack, post)),
            "all177_observed": all(r[0]["observed_fields"] == 177 for r in (pre, attack, post)),
        }
        triplets.append({"environment": environment, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"})
    summary = {"status": "PASS" if not failures and len(rows) == protocol["planned_payloads"] and
               len(triplets) == protocol["planned_triplets"] and all(t["status"] == "PASS" for t in triplets) else "FAILED_OR_INCOMPLETE",
               "planned_payloads": protocol["planned_payloads"], "captured_payloads": len(rows),
               "candidate_states": dict(Counter(r["state"] for r in rows)),
               "full_observation_outcomes": dict(Counter(r["full_observation_outcome"] for r in rows)),
               "passed_triplets": sum(t["status"] == "PASS" for t in triplets), "triplets": triplets,
               "failures": failures, "rows": rows, "model_fits": 0, "model_predictions": 0,
               "formal_retraining": "NOT_RUN_FRESH_COMPARISON_COHORT_REQUIRED", "overall_model_gain": "NOT_EVALUATED"}
    write("SAVED_CANDIDATE_CELLS.json", saved)
    write("RESULTS.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "triplets")}, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    result = analyze()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
