"""Summarize measured operation checkpoints, without revising the v1 outcome."""
import argparse
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE / "diagnostic"


def read(path):
    return json.loads(path.read_text())


def analyze():
    protocol, finished = read(D / "PROTOCOL.json"), read(D / "FINISHED.json")
    assert (D / "diagnostic.js").read_bytes() == (D / "source_snapshot/diagnostic.js").read_bytes()
    rows = []
    for run in finished["paths"]:
        cell = f"api{run['api']}_{run['gpu']}"
        directory = D / "runs" / cell
        archive = directory / "backend/raw_expanded_payloads.jsonl"
        raw = [json.loads(line) for line in archive.read_text().splitlines()] if archive.exists() else []
        for capture in run["captures"]:
            sid = raw[capture["raw_line"] - 1]["canonical_received_payload"]["session_id"]
            for name, location in (("BLANK_DIAGNOSTIC.json", "about:blank"),
                                   ("PAGE_DIAGNOSTIC.json", "file:///android_asset/expanded_probe.html")):
                diagnostic = read(directory / "attempts" / capture["step_id"] / name)
                bound = (diagnostic["session_id_before"] == diagnostic["session_id_after"] == sid
                         and diagnostic["url"] == location and diagnostic["schema"] == protocol["diagnostic"]["schema"])
                expected = [(p, c) for p in protocol["diagnostic"]["profiles_by_location"][location] for c in ("webgl", "webgl2")]
                assert [(r["profile"], r["context_type"]) for r in diagnostic["contexts"]] == expected
                for context in diagnostic["contexts"]:
                    errors = [{"operation": e["operation"], "errors": e["errors"]} for e in context["events"] if e["errors"]]
                    rows.append({"cell": cell, "phase": capture["phase"], "round": capture["round"], "session_id": sid,
                                 "location": location, "profile": context["profile"], "context_type": context["context_type"],
                                 "bound": bound, "status": context["status"], "error_events": errors,
                                 "drained_all": all(e["drained"] for e in context["events"]),
                                 "context_lost_at_end": context.get("context_lost_at_end"),
                                 "source": str((directory / "attempts" / capture["step_id"] / name).relative_to(HERE))})
    groups = []
    for cell, location, profile, context in sorted({tuple(row[k] for k in ("cell", "location", "profile", "context_type")) for row in rows}):
        group = [r for r in rows if (r["cell"], r["location"], r["profile"], r["context_type"]) == (cell, location, profile, context)]
        groups.append({"cell": cell, "location": location, "profile": profile, "context_type": context, "n": len(group),
                       "first_error_counts": dict(Counter(r["error_events"][0]["operation"] if r["error_events"] else "NONE" for r in group))})
    host_direct = [r for r in rows if r["cell"] == "api36_host" and r["context_type"] == "webgl2" and r["profile"] == "error_first"]
    webgl1 = [r for r in rows if r["context_type"] == "webgl"]
    software = [r for r in rows if r["cell"] == "api36_swiftshader"]
    complete = (len(rows) == 96 and all(r["status"] == "COMPLETE" and len(r["captures"]) == 6 for r in finished["paths"])
                and all(r["bound"] and r["status"] == "MEASURED" and r["drained_all"] and r["context_lost_at_end"] is False for r in rows))
    localized = complete and len(host_direct) == 12 and all(r["error_events"] == [{"operation": "after_context_creation", "errors": [1280]}] for r in host_direct)
    webgl1_clean = len(webgl1) == 48 and all(not r["error_events"] for r in webgl1)
    software_clean = len(software) == 48 and all(not r["error_events"] for r in software)
    return {"status": "COMPLETE" if complete else "INCOMPLETE_OR_FAILED", "diagnostic_contexts": len(rows),
            "initial_host_webgl2_error_localized": localized,
            "webgl1_error_free_in_measured_profiles": webgl1_clean,
            "software_error_free_in_measured_profiles": software_clean,
            "supports_separate_webgl1_candidate_trial": localized and webgl1_clean and software_clean,
            "deep_cause": "NOT_ESTABLISHED; no identification of a specific browser/ANGLE/driver defect.",
            "earliest_error_observation": "First getError after getContext observes 1280 before extension, isContextLost or parameter calls" if localized else "NOT_ESTABLISHED",
            "scope": "Two API36 rendering paths, two triplets each, blank and collector page; diagnostic profiles intentionally drain errors and cannot replace original v1 quality decisions.",
            "groups": groups, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); args = parser.parse_args()
    result = analyze(); target = HERE / "LOCALIZATION.json"
    if args.write:
        with target.open("x") as f: json.dump(result, f, ensure_ascii=False, indent=2); f.write("\n")
    else:
        assert read(target) == result
    print(json.dumps({k: v for k, v in result.items() if k not in ("groups", "rows")}, indent=2))
