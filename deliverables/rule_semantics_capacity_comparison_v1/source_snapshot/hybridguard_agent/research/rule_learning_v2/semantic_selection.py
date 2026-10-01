"""ID-independent W0 selection with a registered, train-safe semantic swap.

This is a new selector, not a change to the frozen R_KEEP_V1 kernel. It accepts
an already encoded train problem and never reads files, fits thresholds, or
evaluates new observations. Quality is an observation/semantics preference;
it makes no assertion about empirical accuracy or independent evidence.
"""
from dataclasses import replace
from fractions import Fraction
import json
import math
import time

from ..rule_learning.selector import compatible, json_score
from .retention import diversity, signal_group

VERSION = "SEMANTIC_SELECTION_V2"
CATALOG_VERSION = "W0_STRUCTURAL_SEMANTICS_V2"
QUALITY_VERSION = "POSITIVE_REGISTERED_OBSERVATION_PREFERENCE_V1"
_LANG = "app.web_data.navigator_layer.language"
_LANGS = "app.web_data.navigator_layer.languages"
_WD = "app.web_data.automation_surface_layer.webdriver"
_EPSILON = Fraction(1, 10**12)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _typed(value):
    """Keep bool/int/float/string distinctions, including predicate parameters."""
    if value is None:
        return ["null", None]
    if type(value) is bool:
        return ["boolean", value]
    if type(value) is int:
        return ["integer", value]
    if type(value) is float and math.isfinite(value):
        return ["number", value]
    if type(value) is str:
        return ["string", value]
    if type(value) in (tuple, list):
        return ["array", [_typed(x) for x in value]]
    if type(value) is dict and all(type(k) is str for k in value):
        return ["object", [[k, _typed(value[k])] for k in sorted(value)]]
    raise ValueError("NON_JSON_OR_NONFINITE_SEMANTIC_VALUE")


def _saved_semantics(atom, field, refs):
    p = atom.provenance
    common = (p.get("semantic_version") == "1.0.0"
              and p.get("input_schema_version") == "rsr-input-v1"
              and p.get("input_origin") == "SAVED_CANDIDATE_RESULTS_NO_REEVALUATION")
    if not common:
        raise ValueError("UNREGISTERED_SAVED_SEMANTIC_CONTRACT")
    gate = {k: p[k] for k in ("semantic_version", "input_schema_version", "gate_version", "mode")
            if k in p}
    if (field == _LANGS and refs == [_LANG, _LANGS]
            and p.get("gate_version") == "rsr-language-first-gate-v1" and p.get("mode") == "default"):
        predicate = {"operator": "LIMITED_FULL_TAG_CASEFOLD_NEQ_FIRST_ITEM", "operands": refs,
                     "first_item_index": 0, "trim": False, "tail_used_for_decision": False}
        gate.update(source_binding="navigator_sync_v1", supported_tags="language[-script][-region]",
                    excluded_primaries=["in", "iw", "ji", "mul", "und", "zxx"],
                    invalid_or_missing="U", structural_failure="FAILED")
        return predicate, gate, 1
    if field != _WD or refs != [_WD]:
        raise ValueError("UNREGISTERED_SAVED_SEMANTIC_FIELDS_OR_GATE")
    mode = p.get("mode")
    versions = p.get("mode_gate_versions")
    raw_only = mode == "raw_observation_v1" and p.get("gate_version") == "rsr-webdriver-raw-gate-v1"
    mixed = (mode == "PER_RECORD_EXPLICIT_LEGACY_OR_RAW"
             and p.get("gate_version") == "rsr-webdriver-per-record-explicit-mode-gate-v1"
             and versions == {"legacy_projection_v1": "rsr-webdriver-legacy-gate-v1",
                              "raw_observation_v1": "rsr-webdriver-raw-gate-v1"}
             and p.get("source_mode_schema_version") == "rsr-mixed-source-modes-v1"
             and p.get("source_mode_use") == "EXTERNAL_PROVENANCE_NOT_FEATURE")
    legacy = mode == "legacy_projection_v1" and p.get("gate_version") == "rsr-webdriver-legacy-gate-v1"
    if not (raw_only or mixed or legacy):
        raise ValueError("UNREGISTERED_WEBDRIVER_MODE_GATE")
    predicate = {"operator": "WEBDRIVER_REPORTED_BOOLEAN_STATE", "operands": refs,
                 "raw_observation_path": "web_data.automation_surface_layer.webdriver_observation"}
    gate.update(source_binding={"raw": "webdriver_raw_observation_v1", "legacy": "webdriver_legacy_projection_v1"},
                raw_defined_requires=["api_present_true", "presence_and_value_observed", "boolean_type_and_value",
                                      "observer_revision_and_realm_match_external_binding"],
                raw_absent_error_nonboolean_missing="U", contradictions="FAILED", legacy_false="U")
    if mixed:
        gate.update(mode_gate_versions=versions, source_mode_schema_version=p["source_mode_schema_version"],
                    source_mode_use=p["source_mode_use"])
    return predicate, gate, int(raw_only or mixed)


def semantic_catalog(atoms):
    """Return display-ID lookup with structural keys; reject ambiguous identities.

    The key begins with the primary field. Names, aliases, candidate IDs,
    family-reference IDs, input-column numbers and empirical row values are
    deliberately absent. Catalog quality applies only to POSITIVE literals;
    ``_quality`` enforces polarity when comparing executable clauses.
    """
    result, seen = {}, set()
    for atom in atoms:
        if atom.atom_id in result:
            raise ValueError("DUPLICATE_ATOM_ID")
        p = atom.provenance
        refs = p.get("field_refs", [])
        field = p.get("field") or (refs[0] if refs else None)
        if (type(field) is not str or not field or type(refs) not in (list, tuple)
                or any(type(x) is not str or not x for x in refs)):
            raise ValueError("PRIMARY_FIELD_SEMANTICS_REQUIRED")
        refs = list(refs) or [field]
        quality, gate = 0, {"unavailable": "U", "execution_failure": "FAILED"}
        if atom.orientation == "CONTROL_LE":
            if type(p.get("threshold")) not in (int, float) or isinstance(p.get("threshold"), bool):
                raise ValueError("TYPED_FINITE_THRESHOLD_REQUIRED")
            predicate = {"operator": "LE", "operands": [field], "threshold": _typed(p["threshold"]),
                         "projection": "LIST_LENGTH" if field == _LANGS else "NUMERIC_VALUE"}
        elif atom.orientation == "CONTROL_EQUALITY":
            if "equals" not in p or type(p.get("encoder")) is not str:
                raise ValueError("EXPLICIT_EQUALITY_SEMANTICS_REQUIRED")
            predicate = {"operator": "EQ", "operands": [field], "equals": _typed(p["equals"]),
                         "encoder": p["encoder"], "predicate_version": p.get("predicate_version")}
        elif atom.orientation == "CATALOG_CONDITION":
            condition = p.get("condition")
            if (type(condition) is not dict or type(condition.get("operator")) is not str
                    or type(condition.get("operands")) not in (list, tuple)
                    or not condition["operands"] or list(condition["operands"]) != refs):
                raise ValueError("ORDERED_CATALOG_PREDICATE_REQUIRED")
            predicate = {"operator": condition["operator"], "operands": refs,
                         "parameters": _typed(condition.get("parameters", {}))}
        elif atom.orientation == "SAVED_SEMANTIC_STATE":
            predicate, gate, quality = _saved_semantics(atom, field, refs)
        else:
            raise ValueError("UNREGISTERED_ATOM_SEMANTIC_ORIENTATION")
        key = [field, atom.orientation, predicate, gate]
        token = _json(key)
        if token in seen:
            raise ValueError("DUPLICATE_SEMANTIC_KEY")
        seen.add(token)
        # Existing group rules contain historical ID shortcuts. Suppress those
        # shortcuts so the group, like the key, is invariant to display renaming.
        group = signal_group(replace(atom, atom_id="SEMANTIC_UNNAMED"))
        result[atom.atom_id] = {"key": key, "quality": quality, "signal_group": group}
    return result


def _literal_key(literal, catalog):
    entry = catalog[literal.atom_id]
    return (entry["key"][0], _json(entry["key"][1:]), literal.polarity)


def _clause_key(clause, catalog):
    return tuple(sorted(_literal_key(l, catalog) for l in clause.literals))


def _set_key(clauses, catalog):
    return tuple(sorted(_clause_key(c, catalog) for c in clauses))


def _ordered(clauses, catalog):
    return tuple(sorted(clauses, key=lambda c: _clause_key(c, catalog)))


def _quality(clauses, catalog):
    return sum(catalog[l.atom_id]["quality"] if l.polarity == "POSITIVE" else 0
               for c in clauses for l in c.literals)


def _better(score, selected, incumbent, incumbent_selected, catalog):
    if incumbent is None:
        return True
    if abs(score["objective"] - incumbent["objective"]) > _EPSILON:
        return score["objective"] > incumbent["objective"]
    for key, maximize in (("macro_tpr", True), ("clean_alarms", False),
                          ("minimum_coverage", True), ("complexity", False)):
        if score[key] != incumbent[key]:
            return score[key] > incumbent[key] if maximize else score[key] < incumbent[key]
    q, other = _quality(selected, catalog), _quality(incumbent_selected, catalog)
    return q > other if q != other else _set_key(selected, catalog) < _set_key(incumbent_selected, catalog)


def greedy_semantic(problem, deadline):
    """Original sparse objective/addition/prune policy, structural tie ordering."""
    catalog = semantic_catalog(problem.atoms)
    candidates = _ordered(problem.candidates, catalog)
    selected, best, best_score, trace = (), (), None, []
    current = problem.score(())
    stop = "max_additions"
    for _ in range(problem.search["algorithms"]["GREEDY_OR"]["max_additions"]):
        if time.monotonic() >= deadline:
            stop = "time_limit"; break
        choice, score = None, None
        for c in candidates:
            if time.monotonic() >= deadline:
                stop = "time_limit"; break
            if c in selected:
                continue
            test = _ordered(selected + (c,), catalog)
            s = problem.score(test)
            if (s["partial_feasible"] and s["objective"] - current["objective"] > _EPSILON
                    and _better(s, test, score, choice or (), catalog)):
                choice, score = test, s
        if stop == "time_limit":
            break
        if choice is None:
            stop = "no_positive_objective_improvement"; break
        selected, current = choice, score
        trace.append({"operation": "ADD", "selected": [c.id for c in selected], "score": json_score(score)})
        if score["feasible"] and _better(score, selected, best_score, best, catalog):
            best, best_score = selected, score
    # One pass, exactly as before, but never traverse display IDs.
    for c in _ordered(best, catalog):
        if time.monotonic() >= deadline:
            stop = "time_limit"; break
        proposal = tuple(x for x in best if x != c)
        score = problem.score(proposal)
        if score["feasible"] and score["objective"] >= best_score["objective"]:
            best, best_score = proposal, score
            trace.append({"operation": "PRUNE", "removed": c.id, "score": json_score(score)})
    status = (("TIME_LIMIT_FEASIBLE" if best else "FAILED_FIT") if stop == "time_limit"
              else ("HEURISTIC_FEASIBLE" if best else "HEURISTIC_NO_FEASIBLE_MODEL_FOUND_EMPTY_MODEL"))
    return best, {"status": status, "stop": stop, "optimality": "NONE", "infeasibility_proved": False,
                  "best_bound": None, "gap": None, "solver": VERSION,
                  "catalog_version": CATALOG_VERSION, "quality_version": QUALITY_VERSION}, trace


def _nonregression(problem, before, after):
    reasons = []
    if any(before["states"][i] == "T" and after["states"][i] != "T" for i in problem.weights):
        reasons.append("ATTACK_DETECTION_LOSS")
    if any(before["states"][i] != "T" and after["states"][i] == "T" for i in problem.clean):
        reasons.append("NEW_CLEAN_ALARM")
    if any(a in ("T", "F") and b not in ("T", "F") for a, b in zip(before["states"], after["states"], strict=True)):
        reasons.append("DEFINED_SAMPLE_BECAME_UNKNOWN_OR_FAILED")
    return reasons


def retain_semantic(problem, initial, deadline):
    """Original positive-diversity additions plus monotonic-quality same-group swaps."""
    catalog = semantic_catalog(problem.atoms)
    groups = {aid: item["signal_group"] for aid, item in catalog.items()}
    candidates = _ordered(problem.candidates, catalog)
    if any(len(c.literals) != 1 for c in candidates):
        raise ValueError("SEMANTIC_RETENTION_SINGLETON_OR_REQUIRED")
    if any(c not in candidates for c in initial):
        raise ValueError("INITIAL_RULE_OUTSIDE_ELIGIBLE_TRAIN_POOL")
    selected = _ordered(initial, catalog)
    if selected and not problem.score(selected)["feasible"]:
        raise ValueError("INITIAL_RULE_SET_NOT_FEASIBLE")
    trace, rejected = [], {}
    visited = {_set_key(selected, catalog)}
    visited_order = [_set_key(selected, catalog)]
    # At most max_clauses additions and max_clauses 0->1 swaps; no deletion.
    max_steps = 2 * problem.search["constraints"]["max_clauses"]
    stop = "NO_LEGAL_POSITIVE_SIGNAL_INCREMENT_OR_QUALITY_SWAP"
    for _ in range(max_steps + 1):
        if time.monotonic() >= deadline:
            stop = "TIME_LIMIT"; break
        current = problem.score(selected)
        old_d = diversity(problem, selected, groups)
        choices = []
        for c in candidates:
            if time.monotonic() >= deadline:
                stop = "TIME_LIMIT"; break
            if c in selected:
                continue
            operations = [("RETAIN_SIGNAL", None)]
            for removed in selected:
                if (groups[c.literals[0].atom_id] == groups[removed.literals[0].atom_id]
                        and _quality((c,), catalog) > _quality((removed,), catalog)):
                    operations.append(("SWAP_SEMANTIC_QUALITY", removed))
            for operation, removed in operations:
                proposal = _ordered(tuple(x for x in selected if x != removed) + (c,), catalog)
                score = problem.score(proposal)
                inc = diversity(problem, proposal, groups) - old_d
                reasons = []
                if not compatible(proposal, problem.atoms, problem.method, problem.grammar, problem.search):
                    reasons.append("STRUCTURE_OR_FAMILY_LIMIT")
                if score["clean_alarms"] > problem.budget:
                    reasons.append("SET_CLEAN_BUDGET")
                if score["minimum_coverage"] < Fraction(str(problem.search["constraints"]["min_decision_coverage"])):
                    reasons.append("PHASE_DECISION_COVERAGE")
                if operation == "RETAIN_SIGNAL":
                    if any(current["states"][i] == "T" and score["states"][i] != "T" for i in problem.weights):
                        reasons.append("ATTACK_DETECTION_LOSS")
                    if inc <= 0:
                        reasons.append("NO_NEW_SIGNAL_COVERAGE")
                else:
                    reasons.extend(_nonregression(problem, current, score))
                if _set_key(proposal, catalog) in visited:
                    reasons.append("VISITED_STRUCTURAL_RULE_SET")
                if reasons or not score["feasible"]:
                    for reason in reasons or ["INFEASIBLE"]:
                        rejected[reason] = rejected.get(reason, 0) + 1
                    continue
                key = (-(score["macro_tpr"] - current["macro_tpr"]), -inc,
                       score["clean_alarms"], -score["minimum_coverage"], score["complexity"],
                       -_quality(proposal, catalog), _set_key(proposal, catalog))
                choices.append((key, operation, c, removed, proposal, score, inc))
        if stop == "TIME_LIMIT":
            break
        if not choices:
            if len(selected) >= problem.search["constraints"]["max_clauses"]:
                stop = "ORIGINAL_CLAUSE_LIMIT_NO_LEGAL_QUALITY_SWAP"
            break
        if len(trace) >= max_steps:
            raise ValueError("SEMANTIC_RETENTION_FINITE_BOUND_EXCEEDED")
        _, operation, c, removed, proposal, score, inc = min(choices, key=lambda x: x[0])
        trace.append({"operation": operation, "added": c.id, "removed": removed.id if removed else None,
                      "signal_group": groups[c.literals[0].atom_id],
                      "delta_macro_tpr": float(score["macro_tpr"] - current["macro_tpr"]),
                      "delta_D": float(inc), "D_after": float(old_d + inc),
                      "D_decrease_permitted_for_quality_swap": operation == "SWAP_SEMANTIC_QUALITY",
                      "quality_before": _quality(selected, catalog), "quality_after": _quality(proposal, catalog),
                      "per_sample_nonregression_required": operation == "SWAP_SEMANTIC_QUALITY",
                      "selected_structural_key": _set_key(proposal, catalog),
                      "score": {k: v for k, v in json_score(score).items() if k != "states"}})
        selected = proposal
        visited.add(_set_key(selected, catalog))
        visited_order.append(_set_key(selected, catalog))
    status = (("TIME_LIMIT_FEASIBLE" if selected else "FAILED_FIT") if stop == "TIME_LIMIT"
              else ("RETENTION_FEASIBLE" if selected else "RETENTION_EMPTY_MODEL"))
    return selected, {"status": status, "stop": stop, "optimality": "NONE", "solver": VERSION,
                      "catalog_version": CATALOG_VERSION, "quality_version": QUALITY_VERSION,
                      "old_sparse_objective_still_optimized": False, "new_generalization_guarantee": False,
                      "D_initial": float(diversity(problem, initial, groups)),
                      "D_final": float(diversity(problem, selected, groups)),
                      "visited_structural_keys": visited_order, "finite_operation_cap": max_steps,
                      "rejection_counts": rejected}, trace
