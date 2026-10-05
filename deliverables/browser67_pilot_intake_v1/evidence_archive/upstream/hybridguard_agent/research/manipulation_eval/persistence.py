"""Shared persistence only; no evidence, rule, prediction or label imports."""
import json
from pathlib import Path


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, rows):
    with Path(path).open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def new_output(path, *, inputs=()):
    from hybridguard_agent.research.manipulation_eval.contract import ROOT
    out = Path(path).resolve()
    protected = [ROOT / "hybridguard_agent/config", ROOT / "deliverables/formal_experiment_execution_plan",
                 *[p for p in (ROOT / "hybridguard_agent/artifacts").iterdir() if p.is_dir()]]
    # S04 may create one new child of its study; existing step children remain protected.
    study = ROOT / "hybridguard_agent/artifacts/formal_manipulation_v1_20260923"
    protected.remove(study)
    protected += [p for p in study.iterdir() if p.name != "04_contract" or (p / "VALIDATION.json").exists()]
    for p in protected + [Path(p).resolve() for p in inputs]:
        p = p.resolve()
        if out == p or out.is_relative_to(p) or p.is_relative_to(out):
            raise ValueError("Output overlaps a protected or input path")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output must be new or empty; never overwrite a saved run")
    out.mkdir(parents=True, exist_ok=True)
    return out
