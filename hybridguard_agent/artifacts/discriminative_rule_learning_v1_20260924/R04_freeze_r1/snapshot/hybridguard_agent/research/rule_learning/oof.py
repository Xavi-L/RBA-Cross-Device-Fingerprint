"""Explicit fold/model/stage reconciliation before any OOF arithmetic."""
from collections import defaultdict
import copy

from .evaluation import evaluate

KEYS = ("experiment_id", "protocol_digest", "split_id", "method_id", "operating_point", "source_condition", "input_view", "evaluation_track", "data_origin")


def expected_cells(receipt):
    if receipt is None:
        return None, None, "MISSING_RECEIPT"
    if not receipt.get("model_id"):
        return None, None, "RECEIPT_WITHOUT_MODEL"
    counts = tuple(receipt.get(k) for k in ("atoms", "clauses"))
    if any(v is not None and (type(v) is not int or v < 0) for v in counts):
        raise ValueError("INVALID_RECEIPT_MODEL_CELL_COUNTS")
    return (*counts, "KNOWN_MODEL_CELL_COUNTS" if None not in counts else "MODEL_CELL_COUNTS_UNKNOWN")


def aggregate_oof(expected_models, predictions, model_receipts, metadata):
    expected = {j["model_unit_id"]: j for j in expected_models}
    if len(expected) != len(expected_models):
        raise ValueError("DUPLICATE_EXPECTED_MODEL")
    if set(model_receipts) - set(expected) or any(r.get("model_unit_id") != k for k, r in model_receipts.items()):
        raise ValueError("UNEXPECTED_OR_MISBOUND_MODEL_RECEIPT")
    received, groups = {}, defaultdict(list)
    for j in expected_models:
        groups[tuple(j[k] for k in KEYS)].append(j)
    for r in predictions:
        uid, oid = r["model_unit_id"], r["opaque_id"]
        if uid not in expected or oid not in expected[uid]["outer_test_ids"] or (uid, oid) in received:
            raise ValueError("UNEXPECTED_OR_DUPLICATE_OOF_UNIT")
        j = expected[uid]
        if any(r.get(k) != j[k] for k in (*KEYS, "fold_id")):
            raise ValueError("OOF_MIXED_POINT_SOURCE_TRACK_OR_FOLD")
        receipt = model_receipts.get(uid)
        if receipt and r.get("model_id") != receipt.get("model_id"):
            raise ValueError("OOF_MODEL_RECEIPT_MISMATCH")
        received[uid, oid] = r
    result = []
    for key, jobs in sorted(groups.items()):
        ids, rows, missing, folds = [], [], [], []
        for j in jobs:
            uid = j["model_unit_id"]
            receipt = model_receipts.get(uid)
            atoms, clauses, coverage_state = expected_cells(receipt)
            folds.append({"fold_id": j["fold_id"], "model_unit_id": uid, "receipt": receipt,
                          "coverage_expectation": coverage_state,
                          "state": receipt.get("state", "UNKNOWN") if receipt else "MISSING_EXPECTED_MODEL"})
            for oid in j["outer_test_ids"]:
                if oid in ids:
                    raise ValueError("OOF_STAGE_REPEATED_WITHIN_SAME_TRACK")
                ids.append(oid)
                r = received.get((uid, oid)) if receipt else None
                if r is None:
                    missing.append({"model_unit_id": uid, "fold_id": j["fold_id"], "opaque_id": oid})
                    r = {"opaque_id": oid, "decision": "FAILED", "failure_reason": "MISSING_EXPECTED_OOF_UNIT_OR_MODEL",
                         "selected_atoms_available": 0, "selected_atoms_expected": atoms,
                         "clauses_defined": 0, "clauses_expected": clauses}
                # Only after reconciliation, feed arithmetic an explicit aggregate
                # context. Original model/fold bindings remain intact in fold rows.
                r = copy.deepcopy(r)
                # Receipt/model structure is authoritative. In particular old
                # failed-row zeros cannot turn an unrun model into an empty one.
                r.update(selected_atoms_expected=atoms, clauses_expected=clauses,
                         coverage_expectation=coverage_state)
                r.pop("model_id", None)
                r.update(fold_id="EXPLICIT_OOF_AGGREGATE", model_unit_id=uid)
                rows.append(r)
        report = evaluate(ids, rows, metadata, evaluation_role="SYNTHETIC_OOF" if key[-1] == "BUILTIN_SYNTHETIC" else "EXPOSED_RETROSPECTIVE_OOF")
        unavailable = [f for f in folds if f["state"] not in ("COMPLETED", "EMPTY_MODEL", "REUSED")]
        report["status"] = "INCOMPLETE_EXPECTED_OOF_UNITS" if missing or unavailable else "COMPLETE_RECONCILIATION"
        result.append({"group": dict(zip(KEYS, key)), "expected_fold_n": len(jobs), "folds": folds,
                       "missing_units": missing, "unavailable_models": unavailable, "report": report})
    return result
