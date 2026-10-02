#!/usr/bin/env python3
"""Explicit lower-level H2 replay, not a new observation envelope or data admission."""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.research.webgl_parameter_equivalence import EVALUATOR_REVISION, evaluate_parameter_triplet

SOURCE = ROOT / "deliverables/webgl_behavior_feasibility_v1"
spec = importlib.util.spec_from_file_location("frozen_behavior_v1", SOURCE / "source_snapshot/classify.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
REQUIRED = {"argument", "argument_kind", "pre_errors", "drained", "value_kind", "value", "error",
            "context_lost_before", "context_lost_after"}


def read(path):
    return json.loads(path.read_text())


def replay():
    rows = read(SOURCE / "ROWS.json")
    details = []
    for row in rows:
        source = read(ROOT / row["sidecar_source"])
        assert source["schema"] == "webgl-behavior-probe-v1"
        assert source["session_id"] == source["session_id_after"] == row["session_id"]
        for context in source["contexts"]:
            for name, enum in (("vendor", 37445), ("renderer", 37446)):
                raw = context.get("extension_enabled", {}).get(name, {})
                projected = copy.deepcopy(raw)
                for sample in projected.values():
                    # Original observer recorded all fields inside a completed
                    # try block, or an explicit exception. Add a derived status
                    # only for this query-level replay; never edit source data.
                    sample["read_status"] = ("runtime_error" if "exception" in sample else
                        "observed" if context["status"] == "MEASURED" and REQUIRED <= set(sample) else "unavailable")
                result = evaluate_parameter_triplet(projected, parameter=enum)
                original = legacy.coerced(raw)
                details.append({"source": row["sidecar_source"], "session_id": row["session_id"],
                                "context_type": context["type"], "parameter": name,
                                "new_query_evaluator": result, "frozen_legacy_H2_outcome": original,
                                "agrees_with_original": result["outcome"] == original})
    assert len(rows) == 12 and len(details) == 48
    assert all(d["agrees_with_original"] for d in details)
    old_summary = read(SOURCE / "SUMMARY.json")
    assert old_summary["feasibility"] == "NOT_ESTABLISHED"
    summary = {"kind": "READ_ONLY_QUERY_REPLAY_NOT_NEW_COLLECTION", "evaluator_revision": EVALUATOR_REVISION,
               "source_observations": len(rows), "recorded_parameter_triplets": len(details),
               "outcomes": dict(Counter(d["new_query_evaluator"]["outcome"] for d in details)),
               "same_as_frozen_H2": sum(d["agrees_with_original"] for d in details),
               "whole_new_observer_evaluated_on_devices": False,
               "full_envelope_backfill": False, "new_registered_alert_candidates": 0,
               "new_model_fits": 0, "new_model_predictions": 0,
               "old_joint_acceptance_unchanged": old_summary["feasibility"],
               "status_projection": "read_status is explicitly derived from the old MEASURED context and its complete successful query record, or exception; this is not a new observer capture.",
               "limit": "Only evaluate_parameter_triplet is exercised. Old records lack the standalone observer preflight and its third control read; no full new-version envelope is fabricated."}
    return {"summary": summary, "queries": details}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = replay()
    destination = HERE / "REPLAY.json"
    if args.write:
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        assert read(destination) == result
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
