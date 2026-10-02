"""Evaluate the prospective WebGL1 contract and preserve original v1 results."""
import argparse
from collections import Counter
from datetime import datetime
import json

import analyze as base

HERE, ROOT = base.HERE, base.ROOT


def evaluate():
    protocol = base.read(HERE / "PROTOCOL.json")
    contract = base.read(HERE / "CANDIDATE_CONTRACT.json")
    started = base.read(HERE / "STARTED.json")
    assert datetime.fromisoformat(contract["frozen_at"]) < datetime.fromisoformat(started["started_at"])
    snapshot = HERE / "source_snapshot"
    for source in (HERE / "analyze_candidate.py", HERE / "CANDIDATE_CONTRACT.json", ROOT / protocol["candidate"]["source"]):
        assert source.read_bytes() == (snapshot / source.name).read_bytes(), str(source) + " changed after freeze"
    assert base.read(HERE.parent / "CANDIDATE_CONTRACT.json") == contract
    candidate = base.module("hybridguard_agent.research._frozen_webgl1_candidate", snapshot / "webgl1_parameter_candidate.py")
    assert candidate.CANDIDATE_REVISION == contract["candidate_revision"] == protocol["candidate"]["candidate_revision"]
    assert candidate.CANDIDATE_SCOPE == contract["candidate_scope"] == protocol["candidate"]["candidate_scope"]
    outputs = base.analyze()
    rows = []
    for row in outputs["ROWS.json"]:
        observed = base.read(ROOT / row["observation_source"])
        result = candidate.evaluate_webgl1_candidate(observed, expected_realm_binding="featureapp:" + row["session_id"] + ":main-frame")
        if not row["binding_valid"]:
            result = {**result, "state": "U", "outcome": "UNKNOWN", "reason": "CAPTURE_BINDING_INVALID"}
        rows.append({"cell": row["cell"], "phase": row["phase"], "round": row["round"], "step_id": row["step_id"],
                     "session_id": row["session_id"], "observation_source": row["observation_source"],
                     "binding_valid": row["binding_valid"], "candidate": result})
    prior_ids = set()
    for previous in (HERE.parent / "diagnostic/FINISHED.json", ROOT / "deliverables/webgl_parameter_environment_v1/FINISHED.json"):
        prior_ids.update(c["session_id"] for run in base.read(previous)["paths"] for c in run["captures"])
    assert not prior_ids.intersection(row["session_id"] for row in rows), "Prospective validation reused previous sessions"
    triplets = []
    for original in outputs["TRIPLETS.json"]:
        group = {r["phase"]: r for r in rows if (r["cell"], r["round"]) == (original["cell"], original["round"])}
        states = {p: group[p]["candidate"]["state"] if p in group else "MISSING" for p in base.PHASES}
        controls = original["status"] == "COMPLETE" and all(original.get(k) is True for k in (
            "target_effect", "raw_graphics_restored", "non_target_graphics_unchanged", "sidecar_contexts_restored", "canonical_webgl1_link"))
        passed = controls and states == {"clean_pre": "F", "attack": "T", "clean_post": "F"}
        triplets.append({"cell": original["cell"], "round": original["round"], "status": original["status"],
                         "states": states, "controls_passed": controls, "candidate_triplet_passed": passed,
                         "original_full_envelope_positive_triplet": original["positive_triplet"]})

    def counts(group):
        return {phase: dict(Counter(r["candidate"]["state"] for r in group if r["phase"] == phase)) for phase in base.PHASES}

    full = outputs["SUMMARY.json"]
    environments = []
    for env in full["environments"]:
        group = [t for t in triplets if t["cell"] == env["cell"]]
        passed = env["execution_complete"] and len(group) == env["planned_triplets"] and all(t["candidate_triplet_passed"] for t in group)
        environments.append({"cell": env["cell"], "environment_identity": env["environment_identity"],
                             "candidate_gate": "PASS" if passed else "NOT_ESTABLISHED", "by_phase": counts([r for r in rows if r["cell"] == env["cell"]]),
                             "original_full_envelope_gate": env["environment_gate"]})
    passed = (full["status"] == "COMPLETE" and len(rows) == protocol["planned_payloads"]
              and len(triplets) == protocol["planned_triplets"] and all(t["candidate_triplet_passed"] for t in triplets)
              and all(e["candidate_gate"] == "PASS" for e in environments))
    summary = {"candidate_revision": candidate.CANDIDATE_REVISION, "candidate_scope": candidate.CANDIDATE_SCOPE,
               "status": full["status"], "candidate_gate": "PASS_FROZEN_CANDIDATE_LOCAL_MATRIX" if passed else "NOT_ESTABLISHED",
               "planned_payloads": protocol["planned_payloads"], "captured_payloads": len(rows),
               "planned_triplets": protocol["planned_triplets"], "positive_candidate_triplets": sum(t["candidate_triplet_passed"] for t in triplets),
               "by_phase": counts(rows), "unknown_rows": sum(r["candidate"]["state"] == "U" for r in rows),
               "original_full_envelope_gate": full["versioned_observer_environment_gate"],
               "original_full_envelope_positive_triplets": full["positive_triplets"],
               "environments": environments, "fresh_sessions_verified": True, "contract_frozen_before_capture": True,
               "selector_registration": "NOT_REGISTERED", "model_fits": 0, "model_predictions": 0,
               "overall_model_improvement": "NOT_EVALUATED", "independent_confirmation": "NOT_ACCESSED",
               "next_gate": "Supports formal collection/input integration and candidate registration work within the tested scope; broader comparison data and selector admission are still required before training.",
               "limits": contract["inference_scope"], "scope_counterexample": contract["scope_counterexample"]}
    outputs.update({"CANDIDATE_ROWS.json": rows, "CANDIDATE_TRIPLETS.json": triplets, "CANDIDATE_SUMMARY.json": summary})
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); args = parser.parse_args()
    outputs = evaluate()
    for name, result in outputs.items():
        if args.write:
            with (HERE / name).open("x") as f: json.dump(result, f, ensure_ascii=False, indent=2); f.write("\n")
        else:
            assert base.read(HERE / name) == result, "Saved result differs: " + name
    print(json.dumps(outputs["CANDIDATE_SUMMARY.json"], ensure_ascii=False, indent=2))
