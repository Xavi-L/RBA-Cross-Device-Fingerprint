"""Current-row inference only: no labels, phase, train/test history or fitting."""
from .contracts import logic, negate, state


def clause_state(clause, features):
    return logic((state(features[l.atom_id]) if l.polarity == "POSITIVE"
                  else negate(state(features[l.atom_id])) for l in clause.literals), "AND")


def predict(model, opaque_id, payload):
    result = {**model.binding, "model_id": model.model_id, "method_id": model.method_id,
              "opaque_id": opaque_id, "model_status": model.status, "logical_state": None,
              "decision": "FAILED", "failure_reason": None, "source_rows": [opaque_id],
              "selected_atoms_available": 0, "selected_atoms_expected": len(model.atoms),
              "clauses_defined": 0, "clauses_expected": len(model.clauses),
              "atom_explanations": [], "clause_explanations": []}
    if model.status in ("EMPTY_MODEL", "FAILED"):
        result["decision"] = model.status
        result["failure_reason"] = model.fit.get("status")
        return result
    try:
        if set(payload) != {"features", "view_id"} or payload["view_id"] != model.view["view_id"]:
            raise ValueError("INFERENCE_ENVELOPE_OR_SOURCE_VIEW_MISMATCH")
        if model.constant:
            result["decision"] = model.constant
            result["logical_state"] = "F" if model.constant == "NO_ALERT" else "U"
            return result
        features = payload["features"]
        if not isinstance(features, dict) or any(k.startswith("UNFITTED_CONTROL:") for k in features):
            raise ValueError("UNFITTED_CONTROL_IS_NOT_A_BOOLEAN_ATOM")
        if set(features) & {"label", "phase", "tool", "config", "config_id", "group", "path", "triplet_id", "supervised_label", "future_post"}:
            raise ValueError("SIDECAR_FIELD_IN_INFERENCE_FEATURES")
        if set(features) - set(model.view["input_atom_ids"]):
            raise ValueError("UNREGISTERED_FEATURE_OR_SIDECAR_COLUMN")
        failures = []
        for atom in model.atoms:
            try:
                s = state(features[atom.atom_id])
                result["selected_atoms_available"] += s != "U"
                reason = features[atom.atom_id].get("reason")
            except (ValueError, KeyError) as exc:
                s, reason = None, str(exc)
                failures.append(atom.atom_id + ":" + reason)
            result["atom_explanations"].append({"atom_id": atom.atom_id, "state": s,
                "reason": reason, "orientation": atom.orientation, "aliases": list(atom.aliases),
                "source_groups": list(atom.sources), "surfaces": list(atom.surfaces),
                "provenance": atom.provenance})
        for clause in model.clauses:
            try:
                s = clause_state(clause, features)
            except (KeyError, ValueError):
                s = None
            result["clauses_defined"] += s in ("T", "F")
            result["clause_explanations"].append({"clause_id": clause.id, "state": s,
                "literals": [{"atom_id": l.atom_id, "polarity": l.polarity} for l in clause.literals]})
        if failures:
            raise ValueError("SELECTED_ATOM_FAILURE_NO_SHORT_CIRCUIT:" + ";".join(failures))
        s = logic((c["state"] for c in result["clause_explanations"]), "OR")
        result.update(logical_state=s, decision={"T": "MANIPULATION_ALERT", "F": "NO_ALERT", "U": "INSUFFICIENT_EVIDENCE"}[s])
    except (ValueError, KeyError, TypeError) as exc:
        result["failure_reason"] = str(exc)
    return result


def predict_batch(model, batch, view_id):
    if batch.fold_id != model.binding["fold_id"]:
        raise ValueError("MODEL_FOLD_MISMATCH")
    return [predict(model, oid, {"features": row, "view_id": view_id})
            for oid, row in zip(batch.ids, batch.records, strict=True)]


def predict_single_surface(model, opaque_id, raw_features):
    """Use the saved encoder on the current row; this entry cannot fit."""
    from .baselines import transform_numeric
    try:
        if model.view["kind"] != "SINGLE_SURFACE" or not model.encoder:
            raise ValueError("FROZEN_SINGLE_SURFACE_ENCODER_REQUIRED")
        encoded = transform_numeric(raw_features, model.encoder, [a.atom_id for a in model.atoms])
        return predict(model, opaque_id, {"features": encoded, "view_id": model.view["view_id"]})
    except (ValueError, KeyError, TypeError) as exc:
        result = predict(model, opaque_id, {})
        result.update(decision="FAILED", failure_reason="ENCODER:" + str(exc))
        return result
