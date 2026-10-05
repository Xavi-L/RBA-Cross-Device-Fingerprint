"""Read only P2 admitted representative rows; never decode reserved features."""
import json
from pathlib import Path


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_split_records(plan_dir: Path, split: str) -> list[dict]:
    if split not in {"discovery", "development"}:
        raise ValueError("P3 only permits discovery/development; reserved validation is locked")
    plan_dir = Path(plan_dir)
    summary = _json(plan_dir / "summary.json")
    lock = _json(plan_dir / "reserved_validation_LOCK.json")
    if summary.get("p2_status") != "COMPLETE" or lock.get("status") != "LOCKED":
        raise ValueError("P3 requires completed P2 with locked reserved validation")
    snapshot = Path(summary["source_snapshot"]).resolve()
    source = snapshot / "paired_244.jsonl"
    registry = {}
    with (plan_dir / "sample_registry.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)  # Metadata only, no field values.
            if row["sample_id"] in registry:
                raise ValueError("Duplicate P2 registry sample")
            registry[row["sample_id"]] = row
    admitted = {sid: row for sid, row in registry.items()
                if row["split"] == split and row["analysis_role"] == "primary_representative"
                and row["source_view"] == "paired_244"}
    selected = {}
    order = []
    with (plan_dir / f"{split}_inputs.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            ref = json.loads(line)
            if set(ref) != {"sample_id", "source_file", "source_line", "app_payload_sha256", "browser_payload_sha256"}:
                raise ValueError("Input projection includes unsupported/control fields")
            sid = ref["sample_id"]
            meta = admitted.get(sid)
            if meta is None or sid in order:
                raise ValueError("Input is not a unique admitted representative in this split")
            if Path(ref["source_file"]).resolve() != source:
                raise ValueError("Input source differs from frozen P2 snapshot")
            for key in ("source_line", "app_payload_sha256", "browser_payload_sha256"):
                if ref[key] != meta[key]:
                    raise ValueError(f"P2 binding mismatch: {key}")
            if type(ref["source_line"]) is not int or ref["source_line"] < 1 or ref["source_line"] in selected:
                raise ValueError("Invalid or duplicate source line")
            selected[ref["source_line"]] = ref
            order.append(sid)
    if set(order) != set(admitted):
        raise ValueError("Input projection omits admitted representatives")
    rows = {}
    with source.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            ref = selected.get(number)
            if ref is None:
                continue  # Crucially: do not JSON-decode unselected/reserved features.
            row = json.loads(line)
            sid = row["sample_id"]
            if sid != ref["sample_id"] or row.get("record_schema_version") != "hybridguard-mtc-observation-v2":
                raise ValueError("P1 identity/version mismatch")
            if row.get("dataset_view") != "paired_244" or row.get("feature_count") != 244:
                raise ValueError("P3 requires full paired244 representatives")
            if row["app"]["payload_sha256"] != ref["app_payload_sha256"] or row["browser"]["payload_sha256"] != ref["browser_payload_sha256"]:
                raise ValueError("P1 payload binding mismatch")
            meta = admitted[sid]
            if row["profile"] != meta["profile"]:
                raise ValueError("Profile differs from frozen P2 registry")
            row["_p2"] = {key: meta[key] for key in ("group_id", "split", "profile", "analysis_role", "source_line")}
            rows[sid] = row
    if set(rows) != set(order):
        raise ValueError("Missing selected source rows")
    return [rows[sid] for sid in order]


def inference_record(row: dict) -> dict:
    """Only source fields enter predicates; profile/group/labels stay outside."""
    return {key: row[key] for key in ("features", "field_status", "field_quality")}
