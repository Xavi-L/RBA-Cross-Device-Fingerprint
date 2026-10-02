#!/usr/bin/env python3
"""WebGL feasibility on the closed CAP7 cohort; no fit/predict/threshold search.

Only two existing v2 single-relation contracts are evaluated. Diagnostic lexical
observations are not alert candidates or new model predictions. Default is
read-only; --write creates this audit's outputs exclusively.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hybridguard_agent.evidence.paired244 import field_contract, valid_type
from hybridguard_agent.research.manipulation_eval.provenance import GPU_PARAMS
from hybridguard_agent.research.manipulation_eval.provenance_revision import evaluate_contract

BASE = ROOT / "deliverables/rule_semantics_capacity_comparison_v1"
SOURCE = ROOT / "deliverables/rule_semantics_raw_only_expansion_v1/prepared"
CONFIG = ROOT / "hybridguard_agent/config/formal_manipulation_role_gate_v2"
RULE_IDS = ("NW-005", "OFFDER-GPU-001")
PHASES = ("clean_pre", "attack", "clean_post")
TARGET = "w9-stealth-boundary-webgl-pair-v1"
NATIVE = "app.android_native_data.graphics_layer."
WEB = "app.web_data.graphics_layer."
FIELDS = tuple(NATIVE + name for name in (
    "native_gpu_vendor", "native_gpu_renderer", "egl_vendor", "egl_renderer", "gles_version"
)) + tuple(WEB + name for name in (
    "webgl_vendor", "webgl_renderer", "webgl2_supported", "webgl_extensions_count",
    "webgl_max_texture_size", "webgl_max_viewport_dims", "webgl_aliased_line_width_range"
))
SENTINELS = {"", "unknown", "null", "unsupported", "error", "not available", "masked", "redacted"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_rows(path):
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                yield number, json.loads(line)


def load_registry():
    scopes = [s for s in read(CONFIG / "applicability_policy.json")["scopes"] if s["rule_id"] in RULE_IDS]
    bindings = [r for _, r in json_rows(CONFIG / "source_bindings.jsonl") if r["rule_id"] in RULE_IDS]
    assert {s["rule_id"] for s in scopes} == set(RULE_IDS) == {b["rule_id"] for b in bindings}
    assert len(scopes) == len(bindings) == 2
    return {"scopes": scopes, "bindings": bindings}


def extract_graphics(payload):
    """Preserve raw values and explicit field status; never infer observed from presence."""
    statuses = payload.get("collection_status", {}).get("fields", {})
    result = {}
    for name in FIELDS:
        value = payload
        for part in name.removeprefix("app.").split("."):
            value = value.get(part) if isinstance(value, dict) else None
        result[name] = {"value": value, "source_status": statuses.get(name.removeprefix("app."), "STATUS_MISSING")}
    return result


def usable(cell, name):
    value = cell["value"]
    return (cell["source_status"] == "observed" and valid_type(value, field_contract()[name])
            and not (isinstance(value, str) and value.strip().casefold() in SENTINELS))


def projection(graphics, registry):
    names = {n for s in registry["scopes"] for n in s["relation_required_fields"]}
    assert names <= set(FIELDS)
    return {
        "features": {n: graphics[n]["value"] for n in sorted(names)},
        "field_status": {n: graphics[n]["source_status"] for n in sorted(names)},
        "field_quality": {n: "observed_value" if usable(graphics[n], n) else "source_unavailable" for n in sorted(names)},
    }


def text_observation(graphics, names, predicate):
    if not all(usable(graphics[n], n) for n in names):
        return "U"
    return "T" if predicate(*(graphics[n]["value"] for n in names)) else "F"


def observations(graphics):
    software = lambda value: any(t in value.casefold() for t in GPU_PARAMS["software_tokens"])
    return {
        "lexical_web_desktop_backend_marker": text_observation(graphics, (WEB + "webgl_vendor", WEB + "webgl_renderer"),
            lambda v, r: any(t in (v + " " + r).casefold() for t in ("direct3d", "d3d11", "d3d12", "windows"))),
        "native_web_renderer_text_unequal": text_observation(graphics, (NATIVE + "native_gpu_renderer", WEB + "webgl_renderer"), lambda n, w: n != w),
        "native_renderer_alias_equal": text_observation(graphics, (NATIVE + "native_gpu_renderer", NATIVE + "egl_renderer"), lambda n, e: n == e),
        "native_software_token": text_observation(graphics, (NATIVE + "native_gpu_renderer",), software),
        "web_software_token": text_observation(graphics, (WEB + "webgl_renderer",), software),
    }


def load_members(contract):
    by_run, result = defaultdict(dict), {}
    ids = contract["sample_ids"]
    assert len(ids) == len(set(ids)) == 378
    assert contract["evaluation_role"] == "EXPOSED_RETROSPECTIVE_DEVELOPMENT"
    for oid in ids:
        meta = read(SOURCE / "evaluation" / (oid + ".json"))
        row = read(SOURCE / "inputs" / (oid + ".json"))
        assert row["opaque_id"] == meta["opaque_id"] == oid
        assert row["observation_mode"] == meta["observation_mode"] == "raw_observation_v1"
        assert row["source_ref"] == meta["source_ref"] and row["session_id"] == meta["session_id"]
        assert not any("GPU-001" in name or "NW-005" in name for name in row["features"])
        assert meta["phase"] in PHASES
        ref, sid = meta["source_ref"], meta["session_id"]
        assert sid not in by_run[ref]
        by_run[ref][sid] = meta
    for ref, members in sorted(by_run.items()):
        assert ref.startswith(("deliverables/featureapp_webdriver_runtime_v1/runs/",
            "deliverables/featureapp_webdriver_raw_multienv_v1/runs/",
            "deliverables/rule_semantics_raw_only_expansion_v1/runs/"))
        archive = ROOT / ref / "backend/raw_expanded_payloads.jsonl"
        assert archive.resolve().is_relative_to(ROOT)
        for line, raw in json_rows(archive):
            sid = raw["session_id"]
            if sid not in members:
                continue
            meta, payload = members[sid], raw["canonical_received_payload"]
            oid = meta["opaque_id"]
            assert oid not in result and payload["session_id"] == sid
            result[oid] = (meta, payload, str(archive.relative_to(ROOT)), line)
    assert set(result) == set(ids)
    return result


def counts(rows):
    return {phase: {"n": len(part := [r for r in rows if r["phase"] == phase]),
        "observations": {name: dict(sorted(Counter(r["observations"][name] for r in part).items()))
                         for name in rows[0]["observations"]},
        "relations": {rid: {key: dict(sorted(Counter(r["relations"][rid][key]["status"] for r in part).items()))
            for key in ("relation_applicability", "risk_candidate_eligibility")}
            for rid in RULE_IDS}}
        for phase in PHASES}


def audit():
    contract, registry = read(BASE / "CONTRACT.json"), load_registry()
    assert read(BASE / "EXECUTION.json")["execution_complete"]
    assert read(BASE / "RESULT_REVIEW.json")["status"] == "PASS"
    members = load_members(contract)
    rows = []
    for oid, (meta, payload, archive, line) in sorted(members.items()):
        graphics = extract_graphics(payload)
        projected = projection(graphics, registry)
        relations = {rid: evaluate_contract(rid, projected, registry) for rid in RULE_IDS}
        rows.append({"opaque_id": oid, **{k: meta[k] for k in (
            "phase", "triplet_id", "config_id", "environment_group_id", "session_id")},
            "raw_archive": archive, "raw_line": line, "graphics": graphics,
            "collector_context": {k: payload.get("collection_manifest", {}).get(k) for k in (
                "web_probe_revision", "webview_provider_version", "runtime_context")},
            "observations": observations(graphics), "relations": relations})
    assert Counter(r["phase"] for r in rows) == dict.fromkeys(PHASES, 126)
    triplets = defaultdict(dict)
    for row in rows:
        assert row["phase"] not in triplets[row["triplet_id"]]
        triplets[row["triplet_id"]][row["phase"]] = row
    evidence = []
    for tid, phases in sorted(triplets.items()):
        assert set(phases) == set(PHASES)
        assert len({r["config_id"] for r in phases.values()}) == len({r["environment_group_id"] for r in phases.values()}) == 1
        pre, attack, post = (phases[p] for p in PHASES)
        changes = []
        for name in FIELDS:
            if pre["graphics"][name] != attack["graphics"][name]:
                changes.append(name)
        evidence.append({"triplet_id": tid, "config_id": pre["config_id"], "environment_group_id": pre["environment_group_id"],
            "members": {phase: row["opaque_id"] for phase, row in phases.items()},
            "changed_graphics_fields": changes, "graphics_restored": pre["graphics"] == post["graphics"]})
    assert len(evidence) == 126
    definitions = read(SOURCE / "DEFINITIONS.json")
    reviewed_atoms = [a for a in definitions["atoms"] if a["atom_id"] in {"CAT:" + rid for rid in RULE_IDS}]
    assert len(reviewed_atoms) == 2
    assert not {a["atom_id"] for a in reviewed_atoms} & set(definitions["single_surface_allowlists"]["app_web67"])
    summary = {
        "audit_id": "rule-semantics-webgl-feasibility-v1", "date": "2026-10-01",
        "role": contract["evaluation_role"], "sample_count": len(rows), "triplets": len(evidence),
        "source_archives": sorted({r["raw_archive"] for r in rows}),
        "execution": {"new_fit_calls": 0, "new_model_prediction_calls": 0, "new_threshold_fits": 0,
            "existing_relation_contract_evaluations": len(rows) * len(RULE_IDS), "fresh_android_collection": 0},
        "by_phase": counts(rows),
        "by_config": {cfg: counts([r for r in rows if r["config_id"] == cfg]) for cfg in sorted({r["config_id"] for r in rows})},
        "by_environment": {env: counts([r for r in rows if r["environment_group_id"] == env]) for env in sorted({r["environment_group_id"] for r in rows})},
        "field_usable_definition": "Explicit observed status, valid type and non-sentinel value only; not a guarantee of collector semantics. Historical WebGL2 false is retained but is not capability evidence.",
        "fields": {name: {"usable": sum(usable(r["graphics"][name], name) for r in rows),
            "source_statuses": dict(Counter(r["graphics"][name]["source_status"] for r in rows)),
            "values": [{"value": json.loads(value), "n": n} for value, n in sorted(Counter(
                json.dumps(r["graphics"][name]["value"], ensure_ascii=False) for r in rows).items())]}
            for name in FIELDS},
        "existing_W0_contains_reviewed_GPU_relations": False,
        "proposed_new_alert_candidates_admitted": 0,
        "diagnostic_observations_are_model_predictions": False,
    }
    models = []
    for job in contract["jobs"]:
        if job["stage"] == "RETENTION":
            path = BASE / "trials" / job["job_id"] / "model.json"
            model = read(path)
            assert len(model["clauses"]) == 7
            models.append({"path": str(path.relative_to(ROOT)), "model_id": model["model_id"],
                "fold_id": job["fold_id"], "clauses": len(model["clauses"]), "complexity": model["complexity"]})
    baseline = {"commit": "512ac0b7cfddd2691144ba8d959ca7d8a7635ba0", "models": models,
        "saved_metrics": read(BASE / "RESULTS.json")["groups"]["CAP7"],
        "role": "FROZEN_DEVELOPMENT_REFERENCE_NOT_INDEPENDENT_CONFIRMATION",
        "metrics_origin": "Copied verbatim from completed CAP7 results; flags inside saved_metrics describe that original experiment, not this audit.",
        "new_fit_or_prediction_calls": 0}
    return {"SUMMARY.json": summary, "BASELINE.json": baseline, "REVIEWED_RULES.json": registry | {"W0_definition_atoms": reviewed_atoms},
            "TRIPLETS.json": evidence, "ROWS.jsonl": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = audit()
    if args.write:
        assert not any((HERE / name).exists() for name in outputs), "REFUSE_OVERWRITE_AUDIT_OUTPUTS"
        for name, value in outputs.items():
            with (HERE / name).open("x", encoding="utf-8") as stream:
                if name.endswith(".jsonl"):
                    for row in value:
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                else:
                    json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write("\n")
    summary = outputs["SUMMARY.json"]
    print(json.dumps({k: summary[k] for k in ("audit_id", "sample_count", "triplets", "execution", "by_phase",
        "proposed_new_alert_candidates_admitted")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
