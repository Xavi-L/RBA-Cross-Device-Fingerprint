"""Fixed baselines and source/surface restrictions applied before learning."""
import copy
import json
from pathlib import Path
from datetime import datetime, timezone

from .access import JobTrainingAccess, _derived, authorize
from .contracts import ROOT, STUDY, binding, cell, contract, ledger, read_json, read_jsonl, state
from .fold_data import TrainQuantiles
from .matrix import canonical_core
from .models import Atom, Clause, Literal, RuleModel


def sources(condition):
    if len(condition) != 7 or not condition.startswith("SRC-") or set(condition[4:]) - {"0", "1"}:
        raise ValueError("INVALID_SOURCE_CONDITION")
    return {s for s, bit in zip(("O_u", "H", "E"), condition[4:]) if bit == "1"}


def single_surface_definitions(surface):
    """R02 manifest adapter: metadata only, no matrix/label access or fitting."""
    columns = read_json(STUDY / "R02_matrix/COLUMN_MANIFEST.json")
    if surface not in columns["single_surface_catalog_columns"]:
        raise ValueError("UNREGISTERED_SINGLE_SURFACE")
    by_id = {c["atom_id"]: c for c in ledger()}
    atoms = []
    for name in columns["single_surface_catalog_columns"][surface]:
        c = by_id[name]
        if c["observation_surfaces"] != [surface] or not c["measurement"]["defined"]:
            raise ValueError("R02_SINGLE_SURFACE_METADATA_MISMATCH")
        atoms.append(Atom(name, c["decision_family"], (surface,), (c["provenance_group"],),
                          (c["rule_id"],), "CATALOG_CONDITION", {"field_refs": c["dependencies"], "condition": c["measurement"]["condition"]}))
    for c in read_jsonl(STUDY / "R02_matrix/fixed_control_manifest.jsonl"):
        if c["surface"] == surface:
            atoms.append(Atom(c["atom_id"], "CONTROL_FIELD:" + c["field"], (surface,),
                ("PROJECT_CONTROL_NOT_E_Ou_H_C",), (c["atom_id"],), "CONTROL_EQUALITY", c))
    for c in columns["control_columns"]:
        if c["surface"] == surface and "TRAIN_QUANTILE" in c["encoder"]:
            name = "UNFITTED_CONTROL:" + c["field"]
            atoms.append(Atom(name, "CONTROL_FIELD:" + c["field"], (surface,),
                ("PROJECT_CONTROL_NOT_E_Ou_H_C",), (name,), "UNFITTED_NUMERIC_MEASUREMENT", c))
    return tuple(atoms)


def restrict_single_surface(atoms, surface, allowed_ids):
    """Exact frozen columns, before any numeric fit or support selection."""
    by_id = {a.atom_id: a for a in atoms}
    if (len(by_id) != len(atoms) or len(allowed_ids) != len(set(allowed_ids))
            or set(allowed_ids) - set(by_id)):
        raise ValueError("SINGLE_SURFACE_ALLOWLIST_MISSING_OR_DUPLICATE_ATOM")
    allowed = tuple(by_id[name] for name in allowed_ids)
    if any(a.surfaces != (surface,) for a in allowed):
        raise ValueError("SINGLE_SURFACE_ALLOWLIST_SURFACE_MISMATCH")
    return allowed


def project_core(raw_rows, candidates, condition):
    """Uses raw CAT cells. The already merged SRC-111 matrix is not accepted."""
    allowed = sources(condition)
    selected = [c for c in candidates if c["candidate_use"]["core"]
                and c["candidate_use"]["selectable_on_App177"] and c["provenance_group"] in allowed]
    groups = {}
    for c in selected:
        groups.setdefault(c["normalized_identity"], []).append(c)
    atoms = []
    for identity, members in sorted(groups.items()):
        members.sort(key=lambda x: x["rule_id"])
        if len({(m["measurement"]["profile"], tuple(m["observation_surfaces"]), m["decision_family"]) for m in members}) != 1:
            raise ValueError("NON_EQUIVALENT_ALIAS_METADATA")
        all_aliases = sorted(c["rule_id"] for c in candidates if c["normalized_identity"] == identity)
        atoms.append(Atom(identity, members[0]["decision_family"], tuple(members[0]["observation_surfaces"]),
                          tuple(sorted({m["provenance_group"] for m in members})), tuple(m["rule_id"] for m in members),
                          provenance={"canonical_rule_id": members[0]["rule_id"], "all_registered_equivalent_aliases": all_aliases,
                                      "contributing_aliases": [{"rule_id": m["rule_id"], "source": m["provenance_group"],
                                          "raw_atom_id": m["atom_id"], "deviation_polarity": m["direct_OR_deviation_polarity"],
                                          "profile": m["measurement"]["profile"], "field_refs": m["dependencies"]} for m in members]}))
    rows = {}
    for oid, row in raw_rows.items():
        cells = {}
        for c in selected:
            if c["atom_id"] not in row:
                raise ValueError("SOURCE_PROJECTION_REQUIRES_RAW_ALIAS_CELLS")
            raw = copy.deepcopy(row[c["atom_id"]])
            raw["state"] = state(raw) if raw["evaluation_status"] == "OK" else None
            raw.setdefault("reason", "REASON_NOT_PROVIDED")
            cells[c["atom_id"]] = raw
        normalized = canonical_core(selected, cells, allowed)
        rows[oid] = {c["atom_id"]: {k: c[k] for k in ("value", "available", "evaluation_status", "reason")} for c in normalized}
    return rows, tuple(atoms)


def core_view(access, condition="SRC-111", candidates=None):
    rows, atoms = project_core(access._data._features, candidates or ledger(), condition)
    return _derived(access, rows, atoms, {"view_id": "CORE:" + condition, "kind": "CANONICAL_DEVIATION", "source_condition": condition})


def fixed_model(access, method):
    access.assert_method(method, "NOT_APPLICABLE")
    if method == "DIRECT_CORE_OR":
        if access.view["kind"] != "CANONICAL_DEVIATION" or any(a.orientation != "CANONICAL_DEVIATION" for a in access.atoms):
            raise ValueError("DIRECT_OR_REQUIRES_CANONICAL_DEVIATION_NOT_CATALOG_POLARITY")
        atoms = access.atoms
        clauses = tuple(Clause((Literal(a.atom_id),)) for a in atoms)
        status, constant = ("FIXED" if clauses else "EMPTY_MODEL"), None
    elif method in ("ALWAYS_NO_ALERT", "ALWAYS_ABSTAIN"):
        atoms, clauses, status = (), (), "FIXED"
        constant = "NO_ALERT" if method == "ALWAYS_NO_ALERT" else "INSUFFICIENT_EVIDENCE"
    else:
        raise ValueError("UNKNOWN_FIXED_BASELINE")
    return RuleModel(method, status, clauses, atoms,
        access.model_binding("NOT_APPLICABLE"), access.view,
        {"status": "FIXED_NO_FIT", "train_ids": [], "support_filter": False,
         **access.fit_context(), "freeze_time": datetime.now(timezone.utc).isoformat(),
         "cap_exemption": method == "DIRECT_CORE_OR", "measurement_contract": "r01-measurement-v1"}, constant=constant)


def transform_numeric(features, encoder, required_atoms=None):
    """Frozen threshold transform. Returns only the declared surface features."""
    wanted = set(required_atoms) if required_atoms is not None else None
    out = {name: copy.deepcopy(features[name]) for name in encoder["fixed_atoms"] if wanted is None or name in wanted}
    for name, fit in encoder["numeric"].items():
        if wanted is not None and not wanted.intersection(fit["atom_ids"]):
            continue
        c = features[name]
        for atom_id, threshold in zip(fit["atom_ids"], fit["thresholds"], strict=True):
            if wanted is not None and atom_id not in wanted:
                continue
            if c["evaluation_status"] != "OK":
                out[atom_id] = dict(c, value=None, available=False)
            elif not c["available"]:
                out[atom_id] = cell("U", c.get("reason", "UNAVAILABLE"))
            else:
                import math
                if type(c["value"]) not in (int, float) or not math.isfinite(c["value"]):
                    raise ValueError("INVALID_NUMERIC_TRANSFORM_INPUT")
                out[atom_id] = cell("T" if c["value"] <= threshold else "F", "FROZEN_TRAIN_QUANTILE")
    return out


def single_surface_view(access, surface):
    """Mask metadata/fields first; fit numeric thresholds on this train only."""
    if surface not in ("native84", "host26", "app_web67"):
        raise ValueError("UNREGISTERED_SINGLE_SURFACE")
    batch = access.batch("train")
    authorize(access, batch, "numeric_thresholds")
    if type(access) is JobTrainingAccess:
        spec = access.view.get("single_surface_allowlist")
        if not spec or spec["surface"] != surface:
            raise ValueError("JOB_SINGLE_SURFACE_REQUIRES_FROZEN_ALLOWLIST")
        allowed = restrict_single_surface(access.atoms, surface, spec["atom_ids"])
    else:
        # R03's separately issued built-in toy capability retains its declared
        # toy columns. It cannot issue a real or caller-supplied job capability.
        allowed = [a for a in access.atoms if a.surfaces == (surface,)]
    fixed = [a for a in allowed if not a.atom_id.startswith("UNFITTED_CONTROL:")]
    numeric = [a for a in allowed if a.atom_id.startswith("UNFITTED_CONTROL:")]
    encoder = {"version": "SINGLE_SURFACE_TRAIN_ENCODER_V1", "surface": surface,
               "fold_id": access.fold_id, "train_ids": list(batch.ids),
               "fixed_atoms": [a.atom_id for a in fixed], "numeric": {}}
    atoms = list(fixed)
    for a in numeric:
        transform = TrainQuantiles(a.atom_id).fit(access, batch)
        names = ["CONTROL:" + a.atom_id.removeprefix("UNFITTED_CONTROL:") + ":LE:" + repr(t) for t in transform.thresholds]
        encoder["numeric"][a.atom_id] = {"thresholds": list(transform.thresholds), "atom_ids": names,
            "status": "FROZEN" if names else "NO_OBSERVED_TRAIN_VALUES", "train_observed_n": sum(r[a.atom_id]["available"] for r in batch.records),
            "train_expected_n": len(batch.ids)}
        atoms.extend(Atom(n, a.family, (surface,), ("PROJECT_CONTROL_NOT_E_Ou_H_C",), (n,), "CONTROL_LE",
                          {"field": a.atom_id.removeprefix("UNFITTED_CONTROL:"), "threshold": t}) for n, t in zip(names, transform.thresholds))
    if 2 * len(atoms) > contract("candidate_grammar")["new_encoder"]["max_literals_per_surface"]:
        raise ValueError("NOT_RUN_SINGLE_SURFACE_LITERAL_CAP_NO_TRUNCATION")
    # transform_numeric only reads allowed keys, including status and quality.
    features = {oid: transform_numeric(row, encoder) for oid, row in access._data._features.items()}
    return _derived(access, features, atoms, {"view_id": "SINGLE:" + surface, "kind": "SINGLE_SURFACE", "surface": surface}, encoder)


def historical_seven_contract():
    roles = json.loads((ROOT / "hybridguard_agent/config/formal_manipulation_role_gate_v2/decision_roles.json").read_text())["roles"]
    return {"rule_ids": sorted(r["rule_id"] for r in roles if r["decision_role"] == "alert_candidate"),
            "method": "final_v3_v2", "condition_id": "SRC-111", "input_view": "App177",
            "policy_version": "formal-manipulation-family-or-v2",
            "contract_version": "formal-manipulation-relation-risk-attribution-v2",
            "schema_version": "formal-prediction-v2", "catalog_version": "paired244-runtime-catalog-v3",
            "adapter_version": "app177-triplet-adapter-v1", "runtime_adapter_version": "original-paired244-chain-v3",
            "variant_id": "final_v3_v2:App177:SRC-111",
            "protocol_digest": "9a6cb92a5d973a42d230305e176ab9ef824bca2e8aae045dafed515ce61c0f19"}


def adapt_historical_seven(expected_ids, saved_rows, verified_input_ids):
    """Exact saved final outputs only, never recompute old gates on R02 atoms.

    R04 runner must supply IDs whose frozen input/version binding was checked.
    Historical family coverage is retained separately from R01 atom coverage.
    """
    spec = historical_seven_contract()
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("DUPLICATE_EXPECTED_IDS")
    indexed = {}
    for r in saved_rows:
        if r.get("opaque_id") not in expected_ids or any(r.get(k) != v for k, v in spec.items() if k != "rule_ids"):
            raise ValueError("HISTORICAL_METHOD_OR_INPUT_BINDING_MISMATCH")
        if r["opaque_id"] in indexed:
            raise ValueError("HISTORICAL_DUPLICATE_STAGE")
        indexed[r["opaque_id"]] = r
    result = []
    for oid in expected_ids:
        r = indexed.get(oid)
        good = r is not None and oid in verified_input_ids and r.get("execution_status") == "COMPLETED"
        decision = r.get("risk", {}).get("decision") if good else "FAILED"
        if decision not in ("MANIPULATION_ALERT", "NO_ALERT", "INSUFFICIENT_EVIDENCE"):
            decision = "FAILED"
        result.append({"opaque_id": oid, "method_id": "HISTORICAL_SEVEN", "decision": decision,
            "model_status": "FIXED" if decision != "FAILED" else "FAILED",
            "failure_reason": None if decision != "FAILED" else "MISSING_FAILED_OR_UNVERIFIED_HISTORICAL_UNIT",
            "source_rows": [oid], "historical_family_coverage": r.get("risk", {}).get("family_coverage") if r else None,
            "selected_atoms_available": 0, "selected_atoms_expected": 0, "clauses_defined": 0, "clauses_expected": 0,
            "coverage_status": "HISTORICAL_FAMILY_COVERAGE_NOT_R01_ATOM_COVERAGE", "historical_contract": spec})
    return result
