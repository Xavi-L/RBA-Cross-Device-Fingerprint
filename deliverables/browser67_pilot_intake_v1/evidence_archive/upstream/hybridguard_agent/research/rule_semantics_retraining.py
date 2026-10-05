"""Four bounded W0 retraining views over saved, already evaluated cells.

The original encoder, support rules, greedy selector, and predictor are reused.
No candidate is evaluated here, no record is loaded, and no fit runs on import.
The caller supplies exact train rows and enforces the experiment's job budget.
Only explicit save/load functions touch files, using the existing RuleModel
serialization with a distinct study/phase binding.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import time

from .rule_learning.baselines import transform_numeric
from .rule_learning.contracts import contract
from .rule_learning.models import Atom, RuleModel, load_model as _load_model, save_model as _save_model
from .rule_learning.predictor import predict
from .rule_learning.selector import compatible, greedy, json_score
from .rule_learning_v2.adapter import TrainAccess, V2Problem, approved_atoms, encode_train
from .rule_learning_v2.b_engine import selected_definitions
from .rule_learning_v2.retention import signal_group
from .rule_semantics_revision_v1.contracts import SemanticCell


VERSION = "rsr-retraining-adapter-v1"
STUDY_VERSION = "rule-semantics-retraining-v1"
PHASE = "RSR_RETRAINING"
GROUPS = ("BASE", "LANG_ADD", "LANG_REPLACE", "WD_REPLACE")
LANG_ID = "RSR-LANG-FIRST-v1"
WD_ID = "RSR-WEBDRIVER-STATE-v1"
OLD_LANG = "UNFITTED_CONTROL:app.web_data.navigator_layer.languages"
OLD_LANG_PREFIX = "CONTROL:app.web_data.navigator_layer.languages:LE:"
OLD_WD = "CONTROL:app.web_data.automation_surface_layer.webdriver:EQ:True"
_ADDED = {"BASE": None, "LANG_ADD": LANG_ID, "LANG_REPLACE": LANG_ID, "WD_REPLACE": WD_ID}


def _group(group):
    if type(group) is not str or group not in GROUPS:
        raise ValueError("UNREGISTERED_RETRAINING_GROUP")


def _removed(atom_id, group):
    return ((group == "LANG_REPLACE" and (atom_id == OLD_LANG or atom_id.startswith(OLD_LANG_PREFIX)))
            or (group == "WD_REPLACE" and atom_id == OLD_WD))


def group_definitions(defs, group):
    """Keep W0 metadata unchanged except for the group's explicit substitution."""
    _group(group)
    result = selected_definitions(defs, "W0")
    original = {a["atom_id"]: a for a in result["atoms"]}
    if len(original) != len(result["atoms"]):
        raise ValueError("DUPLICATE_INPUT_ATOM_DEFINITION")
    active = result["single_surface_allowlists"]["app_web67"]
    if any(name in active for name in (LANG_ID, WD_ID)):
        raise ValueError("BASE_W0_ALREADY_CONTAINS_NEW_SEMANTIC_ATOM")
    added = _ADDED[group]
    if added:
        old_id = OLD_WD if added == WD_ID else OLD_LANG
        if old_id not in original or old_id not in active:
            raise ValueError("BASE_W0_REQUIRED_REPLACEMENT_FIELD_ABSENT:" + old_id)
        previous = original[old_id]
        field = old_id.removeprefix("UNFITTED_CONTROL:") if added == LANG_ID else "app.web_data.automation_surface_layer.webdriver"
        refs = ["app.web_data.navigator_layer.language", field] if added == LANG_ID else [field]
        atom = Atom(
            added, previous["family"], ("app_web67",), tuple(previous["sources"]),
            (added,), "SAVED_SEMANTIC_STATE",
            {"field_refs": refs, "field": field,
             "signal_group": "language_preferences" if added == LANG_ID else "automation_flag",
             "candidate_id": added, "semantic_version": "1.0.0",
             "mode": "default" if added == LANG_ID else "legacy_projection_v1",
             "input_schema_version": "rsr-input-v1",
             "gate_version": "rsr-language-first-gate-v1" if added == LANG_ID else "rsr-webdriver-legacy-gate-v1",
             "input_origin": "SAVED_CANDIDATE_RESULTS_NO_REEVALUATION",
             "same_field_family_as": old_id,
             "independent_cross_layer_evidence": False},
        )
        if added in original:
            raise ValueError("NEW_SEMANTIC_ATOM_ID_ALREADY_REGISTERED")
        result["atoms"].append(asdict(atom))
    result["atoms"] = [a for a in result["atoms"] if not _removed(a["atom_id"], group)]
    result["single_surface_allowlists"]["app_web67"] = [n for n in active if not _removed(n, group)]
    if added:
        result["single_surface_allowlists"]["app_web67"].append(added)
    # Existing validation checks duplicate names, exact surfaces and references.
    approved_atoms(result)
    return result


def kernel_cell(cell, candidate_id):
    """Validate saved semantic identity/encoding without executing its candidate.

    FAILED remains a failed input cell, so the unchanged selector excludes its
    literal.  U is unavailable with value None and is never negated into F.
    """
    if (candidate_id not in (LANG_ID, WD_ID) or type(cell) is not dict
            or cell.get("candidate_id") != candidate_id or cell.get("version") != "1.0.0"):
        raise ValueError("SAVED_CANDIDATE_IDENTITY_MISMATCH")
    checked = SemanticCell(**cell)
    return {"value": checked.value, "available": checked.available,
            "evaluation_status": checked.evaluation_status, "reason": checked.reason,
            "source_reason": checked.source_reason, "diagnostics": deepcopy(checked.diagnostics)}


def project_rows(raw_rows, defs, group, candidate_rows=None):
    """Take an explicit group allowlist; never select or discard member IDs."""
    _group(group)
    if type(raw_rows) is not dict:
        raise ValueError("RAW_ROWS_MAPPING_REQUIRED")
    selected = group_definitions(defs, group)
    names = [a.atom_id for a in approved_atoms(selected)]
    added = _ADDED[group]
    if added:
        if type(candidate_rows) is not dict or set(candidate_rows) != set(raw_rows):
            raise PermissionError("EXACT_SAVED_CANDIDATE_MEMBERS_REQUIRED")
    elif candidate_rows not in (None, {}):
        raise PermissionError("BASE_GROUP_DOES_NOT_CONSUME_CANDIDATE_ROWS")
    rows = {}
    for opaque_id, raw in raw_rows.items():
        if type(raw) is not dict:
            raise ValueError("RAW_ATOM_ROW_MAPPING_REQUIRED")
        row = {name: deepcopy(raw[name]) for name in names if name != added}
        if added:
            saved = candidate_rows[opaque_id]
            if type(saved) is not dict or added not in saved:
                raise ValueError("MISSING_SAVED_CANDIDATE_CELL:" + added)
            row[added] = kernel_cell(saved[added], added)
        rows[opaque_id] = row
    return rows


def _identity(binding, group, fold_id):
    _group(group)
    required = {"study_version": STUDY_VERSION, "phase": PHASE, "group_id": group,
                "method_id": "GREEDY_OR", "operating_point": "OP05", "fold_id": fold_id}
    if type(binding) is not dict or any(binding.get(k) != v for k, v in required.items()):
        raise PermissionError("EXPLICIT_RSR_RETRAINING_IDENTITY_REQUIRED")


def _frozen_contract():
    search, grammar = contract("learning_search_space"), contract("candidate_grammar")
    expected_support = {"minimum_available_triplets": 3,
                        "minimum_true_attack_triplets_per_literal_or_clause": 2,
                        "minimum_support_bundles": 1, "minimum_support_environments": 1}
    expected_constraints = {"max_clauses": 6, "max_literals": 12, "max_complexity_primary": 12,
                            "max_clause_length_primary": 1, "min_decision_coverage": 0.8,
                            "train_execution_failures_max": 0}
    expected_ties = ["higher_objective", "higher_MacroTPR", "fewer_clean_alarms",
                     "higher_min_stratum_decision_coverage", "lower_complexity",
                     "lexicographically_sorted_atom_polarity_clause_ids"]
    if (any(search["support"].get(k) != v for k, v in expected_support.items())
            or any(search["constraints"].get(k) != v for k, v in expected_constraints.items())
            or search["objective"]["lambda"] != 0.005
            or [p["alpha"] for p in search["operating_points"] if p["id"] == "OP05"] != [0.05]
            or search["tie_break"] != expected_ties
            or search["objective_tolerance"] != 1e-12
            or search["algorithms"]["GREEDY_OR"]["max_additions"] != 6
            or search["algorithms"]["GREEDY_OR"]["backward_pruning_passes"] != 1
            or search["algorithms"]["GREEDY_OR"]["time_limit_seconds_per_fit"] != 60
            or grammar["literal"]["polarity_choices"] != ["POSITIVE", "NEGATIVE"]
            or grammar["composition"]["max_clauses_per_family"] != 2
            or grammar["new_encoder"]["number"]["threshold_quantiles"] != [0.25, 0.5, 0.75]):
        raise PermissionError("FROZEN_TRAINING_CONTRACT_CHANGED")
    return search


def _training_details(problem, atoms, selected, trace, access, group, failure):
    groups = {a.atom_id: signal_group(a) for a in atoms}
    selected_ids = {c.id for c in selected}
    manifest = []
    if problem is not None:
        eligible = {c.id: c for c in problem.candidates}
        final_score = problem.score(selected)
        for item in problem.manifest:
            rec = deepcopy(item)
            reasons = list(item["reasons"])
            if item["clause_id"] in selected_ids:
                reasons = ["SPARSE_SELECTED"]
            elif failure:
                reasons.append("FIT_FAILED_NO_SELECTED_MODEL")
            elif item["clause_id"] in eligible:
                proposal = selected + (eligible[item["clause_id"]],)
                score = problem.score(proposal)
                if not compatible(proposal, atoms, problem.method, problem.grammar, problem.search):
                    reasons.append("STRUCTURE_OR_FAMILY_LIMIT")
                if score["clean_alarms"] > problem.budget:
                    reasons.append("SET_CLEAN_BUDGET")
                if not score["feasible"]:
                    reasons.append("FINAL_SET_CONSTRAINT")
                if score["objective"] <= final_score["objective"]:
                    reasons.append("NO_POSITIVE_SPARSE_OBJECTIVE_GAIN")
                if not reasons:
                    reasons.append("GREEDY_SEARCH_OR_TIME_LIMIT")
            rec.update(selected=item["clause_id"] in selected_ids,
                       signal_group=groups[item["clause_id"].rsplit(":", 1)[0]],
                       selection_reasons=reasons)
            manifest.append(rec)
    return {"schema_version": "rsr-retraining-training-v1", "adapter_version": VERSION,
            "group_id": group, "trace": deepcopy(trace), "candidate_manifest": manifest,
            "support": deepcopy(problem.support) if problem is not None else {},
            "encoded_atoms": [asdict(atom) for atom in atoms], "signal_groups": groups,
            "signal_group_interpretation": "Shared signal labels do not assert independent evidence or predicate equivalence.",
            "access_operations": deepcopy(access.operations), "train_ids": list(access.ids),
            "statistics_scope": "EXACT_OWN_TRAIN_ONLY_NO_TEST_INPUT",
            "failure": deepcopy(failure)}


def fit_group(job, raw_rows, metadata, defs, *, group, binding, candidate_rows=None):
    """One counted fit: old train encoder -> old support -> old sparse greedy.

    Identity/member/cache-schema errors fail before fit starts.  Runtime errors
    after entry preserve a FAILED model and structured failure record.  The
    caller owns the maximum twelve-job ledger; this function never retries.
    """
    _identity(binding, group, job["fold_id"])
    train_ids = tuple(job["train_ids"])
    # Reject any test/extra member by keys before inspecting or copying values.
    if (not train_ids or len(train_ids) != len(set(train_ids))
            or type(raw_rows) is not dict or type(metadata) is not dict
            or set(raw_rows) != set(train_ids) or set(metadata) != set(train_ids)
            or set(train_ids) & set(job["outer_test_ids"])):
        raise PermissionError("EXACT_TRAIN_MEMBERS_ONLY")
    search = _frozen_contract()
    selected_defs = group_definitions(defs, group)
    # Metadata defects must fail before an actual fit, not while serializing it.
    for atom in approved_atoms(selected_defs):
        signal_group(atom)
    projected = project_rows(raw_rows, defs, group, candidate_rows)
    access = TrainAccess(job, projected, metadata)
    started = time.monotonic()
    deadline = started + search["algorithms"]["GREEDY_OR"]["time_limit_seconds_per_fit"]
    problem, encoder, atoms, selected, trace = None, {}, (), (), []
    failure = None
    stage = "TRAIN_ENCODER"
    view = {"view_id": PHASE + ":" + group, "representation": group,
            "kind": "RSR_SAVED_STATE_W0", "base_representation": "W0",
            "group_id": group, "input_atom_ids": [],
            "new_candidate_ids": [_ADDED[group]] if _ADDED[group] else [],
            "candidate_evaluation": "NOT_CALLED_SAVED_CELLS_ONLY"}
    try:
        rows, atoms, encoder, _ = encode_train(access, selected_defs, "S_FLAT")
        view["input_atom_ids"] = sorted(a.atom_id for a in atoms)
        if any(_removed(a.atom_id, group) for a in atoms):
            raise ValueError("REMOVED_ATOM_FAMILY_REAPPEARED_AFTER_ENCODING")
        stage = "TRAIN_SUPPORT"
        problem = V2Problem(access, rows, atoms, deadline)
        stage = "GREEDY_SELECTION"
        access.assert_fit(access.batch(), "pruning")
        selected, outcome, trace = greedy(problem, deadline)
        stage = "FINAL_TRAIN_CONSTRAINT_CHECK"
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("FINAL_TRAIN_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": stage, "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    status = "FAILED" if outcome["status"].startswith("FAILED") else "FITTED" if selected else "EMPTY_MODEL"
    if status == "FAILED":
        selected = ()
        if failure is None:
            failure = {"stage": "GREEDY_SELECTION", "exception_type": None,
                       "reason": outcome.get("stop", outcome["status"])}
    audit = dict(outcome, train_ids=list(access.ids), train_expected_n=len(access.ids),
                 train_consumed_n=len(access.rows), fit_scope="RSR_EXACT_AUTHORIZED_TRAIN_ONLY",
                 freeze_time=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                 actual_fit_invocations=1, candidate_evaluations=0,
                 candidate_pool_size=len(problem.candidates) if problem else None,
                 registered_clause_count=len(problem.manifest) if problem else None,
                 adapter_version=VERSION, group_id=group, failure=failure)
    if problem is not None:
        audit.update(training_result=json_score(problem.score(selected)), clean_budget_count=problem.budget,
                     clean_denominator=len(problem.clean), support_scope="COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY")
    selected_atoms = {literal.atom_id for clause in selected for literal in clause.literals}
    model = RuleModel("GREEDY_OR", status, tuple(selected), tuple(a for a in atoms if a.atom_id in selected_atoms),
                      deepcopy(binding), view, audit, encoder=encoder)
    return model, _training_details(problem, atoms, tuple(selected), trace, access, group, failure)


def _model_identity(model):
    if type(model) is not RuleModel:
        raise TypeError("RULE_MODEL_REQUIRED")
    _identity(model.binding, model.view.get("group_id"), model.binding.get("fold_id"))
    if (model.method_id != "GREEDY_OR" or model.view.get("kind") != "RSR_SAVED_STATE_W0"
            or model.view.get("view_id") != PHASE + ":" + model.binding["group_id"]
            or model.view.get("new_candidate_ids") != ([_ADDED[model.binding["group_id"]]] if _ADDED[model.binding["group_id"]] else [])):
        raise PermissionError("MODEL_VIEW_OR_CANDIDATE_IDENTITY_MISMATCH")
    # This also detects mutation of any otherwise-valid frozen model content.
    model.model_id


def predict_current(model, opaque_id, raw, candidate_cells=None):
    """Use frozen train thresholds and saved current-row cells; never fit/retry."""
    _model_identity(model)
    if model.status in ("FAILED", "EMPTY_MODEL"):
        return predict(model, opaque_id, {})
    try:
        current = deepcopy(raw)
        selected_ids = [a.atom_id for a in model.atoms]
        for candidate_id in model.view["new_candidate_ids"]:
            if candidate_id in selected_ids:
                if type(candidate_cells) is not dict or candidate_id not in candidate_cells:
                    raise ValueError("MISSING_SAVED_CURRENT_CANDIDATE_CELL:" + candidate_id)
                current[candidate_id] = kernel_cell(candidate_cells[candidate_id], candidate_id)
        row = transform_numeric(current, model.encoder, required_atoms=selected_ids)
        return predict(model, opaque_id, {"features": row, "view_id": model.view["view_id"]})
    except Exception as exc:
        result = predict(model, opaque_id, {})
        result.update(decision="FAILED", failure_reason="RSR_TRANSFORM:" + type(exc).__name__ + ":" + str(exc))
        return result


def save_model(model, path):
    _model_identity(model)
    _save_model(model, path)


def load_model(path):
    model = _load_model(path)
    _model_identity(model)
    return model
