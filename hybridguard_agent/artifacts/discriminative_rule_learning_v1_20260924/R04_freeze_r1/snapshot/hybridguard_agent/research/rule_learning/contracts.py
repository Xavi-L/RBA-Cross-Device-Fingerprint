"""Read frozen R01 contracts. R03 adds implementation, never edits these JSONs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "hybridguard_agent/config/rule_learning_v1_20260924"
STUDY = ROOT / "hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924"


def read_json(path):
    return json.loads(Path(path).read_text())


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def contract(name):
    return read_json(CONFIG / (name + ".json"))


def binding():
    return read_json(STUDY / "R01_protocol/PROTOCOL_BINDING.json")


def ledger():
    return read_jsonl(STUDY / "R01_protocol/CANDIDATE_LEDGER.jsonl")


DECISIONS = ("MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE", "EMPTY_MODEL", "FAILED")
PHASES = ("clean_pre", "attack", "clean_post")


def state(cell):
    """A malformed/unextracted cell is an execution error, never an unknown."""
    if not isinstance(cell, dict) or cell.get("evaluation_status") != "OK":
        raise ValueError("ATOM_" + str(cell.get("evaluation_status", "SCHEMA_INVALID") if isinstance(cell, dict) else "SCHEMA_INVALID"))
    if cell.get("available") is False and cell.get("value") is None:
        return "U"
    if cell.get("available") is True and type(cell.get("value")) is bool:
        return "T" if cell["value"] else "F"
    raise ValueError("INVALID_BOOLEAN_ATOM_OR_UNFITTED_CONTROL")


def negate(s):
    return {"T": "F", "F": "T", "U": "U"}[s]


def logic(states, operator):
    states = tuple(states)
    if not states or any(s not in ("T", "F", "U") for s in states):
        raise ValueError("LOGIC_REQUIRES_NONEMPTY_VALID_STATES")
    if operator == "AND":
        return "F" if "F" in states else "T" if all(s == "T" for s in states) else "U"
    if operator == "OR":
        return "T" if "T" in states else "F" if all(s == "F" for s in states) else "U"
    raise ValueError("UNKNOWN_LOGICAL_OPERATOR")


def cell(s, reason="SYNTHETIC_HAND_SPECIFIED"):
    return {"value": {"T": True, "F": False}.get(s), "available": s in ("T", "F"),
            "evaluation_status": "FAILED" if s == "FAILED" else "NOT_REQUESTED" if s == "NOT_REQUESTED" else "OK",
            "reason": reason}
