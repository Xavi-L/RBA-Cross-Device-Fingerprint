#!/usr/bin/env python3
"""Explain the saved result per predeclared hypothesis without changing it."""
import argparse
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def diagnose():
    rows = json.loads((HERE / "ROWS.json").read_text())
    summary = json.loads((HERE / "SUMMARY.json").read_text())
    hypotheses = {}
    for name, key in (("H1_extension_gate", "extension_gate"), ("H2_argument_coercion", "argument_coercion"),
                      ("capability_positive_control", "capability_control"), ("drawing_positive_control", "render_control")):
        hypotheses[name] = {context: {phase: dict(Counter(r["outcomes"][context][key] for r in rows if r["phase"] == phase))
                                     for phase in ("clean_pre", "attack", "clean_post")}
                            for context in ("webgl", "webgl2")}
    dirty = []
    for row in rows:
        for context, details in row["contexts"].items():
            sample = details.get("extension_disabled", {}).get("vendor", {})
            if sample.get("pre_errors"):
                dirty.append(dict(path=row["path"], phase=row["phase"], round=row["round"],
                                  session_id=row["session_id"], context=context, pre_errors=sample["pre_errors"],
                                  drained=sample["drained"], observed_query_value=sample.get("value"),
                                  observed_query_error=sample.get("error")))
    h2_supported = len(rows) == 12 and all(
        row["outcomes"][context]["argument_coercion"] == ("COUNTEREXAMPLE" if row["phase"] == "attack" else "MATCH")
        and row["outcomes"][context]["capability_control"] == "MATCH"
        and row["outcomes"][context]["render_control"] == "MATCH"
        for row in rows for context in ("webgl", "webgl2"))
    return {"kind": "POST_RUN_EXPLANATION_OF_PREDECLARED_HYPOTHESES",
            "original_joint_feasibility_unchanged": summary["feasibility"],
            "original_joint_separated_triplets": summary["behavior_separated_triplets"],
            "H2_local_mechanism_supported": h2_supported, "hypotheses": hypotheses,
            "first_query_preexisting_error_records": dirty,
            "diagnosis": "All six host/WebGL2 contexts have INVALID_ENUM queued before the first vendor query, including both clean phases. The frozen classifier keeps this query UNKNOWN despite draining. The exact producing initialization/driver call is not isolated.",
            "not_changed": ["raw observations", "frozen classifier", "protocol", "joint acceptance", "model results"],
            "interpretation": "H2 is a predeclared individual hypothesis, not a replacement acceptance criterion. This only supports versioned observation design for one plugin configuration; it does not establish population FPR/TPR or current selector improvement."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = diagnose()
    path = HERE / "DIAGNOSIS.json"
    if args.write:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        assert json.loads(path.read_text()) == data
    print(json.dumps({k: v for k, v in data.items() if k not in ("hypotheses", "first_query_preexisting_error_records")}, ensure_ascii=False, indent=2))
