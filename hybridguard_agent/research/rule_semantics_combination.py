"""One combined language-add/webdriver-replace view, with two explicit stages.

The caller provides exact train members and already saved candidate cells.
GREEDY initialization uses the original train encoder and selector; R_KEEP uses
only that combination's saved initialization and unchanged retention kernel.
No candidate, observation loader, experiment scheduler or fit runs on import.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import time

from . import rule_semantics_retraining as sparse
from .rule_semantics_rkeep_retraining import _verify_initial
from .rule_learning.baselines import transform_numeric
from .rule_learning.models import RuleModel, load_model as _load_model, save_model as _save_model
from .rule_learning.predictor import predict
from .rule_learning.selector import greedy, json_score
from .rule_learning_v2.adapter import TrainAccess, V2Problem, approved_atoms, encode_train
from .rule_learning_v2.b_engine import compact_training, frozen_atoms
from .rule_learning_v2.retention import GROUP_VERSION, retain, signal_group


VERSION = "rsr-combination-adapter-v1"
STUDY_VERSION = "rule-semantics-combination-v1"
PHASE = "RSR_COMBINATION"
GROUP = "LANG_ADD_WD_REPLACE"
LANG_ID, WD_ID = sparse.LANG_ID, sparse.WD_ID
OLD_LANG, OLD_WD = sparse.OLD_LANG, sparse.OLD_WD
kernel_cell = sparse.kernel_cell
_STAGES = {"GREEDY_OR": "SPARSE", "R_KEEP_V1": "RETENTION"}


def group_definitions(defs):
    """Compose the reviewed substitutions, retaining the entire length family."""
    result = sparse.group_definitions(defs, "WD_REPLACE")
    language_view = sparse.group_definitions(defs, "LANG_ADD")
    language_atom = next(atom for atom in language_view["atoms"] if atom["atom_id"] == LANG_ID)
    result["atoms"].append(deepcopy(language_atom))
    result["single_surface_allowlists"]["app_web67"].append(LANG_ID)
    active = {atom.atom_id for atom in approved_atoms(result)}
    original = set(defs["single_surface_allowlists"]["app_web67"])
    if active != (original - {OLD_WD}) | {LANG_ID, WD_ID}:
        raise ValueError("COMBINATION_EXACT_POOL_MISMATCH")
    if OLD_LANG not in active or OLD_WD in active:
        raise ValueError("COMBINATION_REQUIRED_FIELD_SUBSTITUTION_MISMATCH")
    return result


def project_rows(raw_rows, defs, candidate_rows):
    """Copy only declared atoms and both saved cells, preserving row membership."""
    if (type(raw_rows) is not dict or type(candidate_rows) is not dict
            or set(candidate_rows) != set(raw_rows)):
        raise PermissionError("EXACT_COMBINATION_CANDIDATE_MEMBERS_REQUIRED")
    names = [atom.atom_id for atom in approved_atoms(group_definitions(defs))]
    rows = {}
    for opaque_id, raw in raw_rows.items():
        saved = candidate_rows[opaque_id]
        if type(raw) is not dict or type(saved) is not dict or any(cid not in saved for cid in (LANG_ID, WD_ID)):
            raise ValueError("BOTH_SAVED_COMBINATION_CELLS_REQUIRED")
        rows[opaque_id] = {
            name: kernel_cell(saved[name], name) if name in (LANG_ID, WD_ID) else deepcopy(raw[name])
            for name in names
        }
    return rows


def _identity(binding, method, fold_id):
    expected = {"study_version": STUDY_VERSION, "phase": PHASE, "group_id": GROUP,
                "method_id": method, "operating_point": "OP05", "fold_id": fold_id}
    if (method not in _STAGES or type(fold_id) is not str or not fold_id
            or type(binding) is not dict or any(binding.get(key) != value for key, value in expected.items())):
        raise PermissionError("EXPLICIT_COMBINATION_STAGE_IDENTITY_REQUIRED")


def _preflight(job, raw_rows, metadata, defs, binding, candidate_rows, method):
    _identity(binding, method, job["fold_id"])
    ids = tuple(job["train_ids"])
    if (not ids or len(ids) != len(set(ids)) or type(raw_rows) is not dict or type(metadata) is not dict
            or set(raw_rows) != set(ids) or set(metadata) != set(ids)
            or set(ids) & set(job["outer_test_ids"])):
        raise PermissionError("EXACT_TRAIN_MEMBERS_ONLY")
    sparse._frozen_contract()
    definitions = group_definitions(defs)
    for atom in approved_atoms(definitions):
        signal_group(atom)
    projected = project_rows(raw_rows, defs, candidate_rows)
    return definitions, TrainAccess(job, projected, metadata)


def _view(method, atoms):
    return {"view_id": PHASE + ":" + GROUP + ":" + _STAGES[method],
            "representation": GROUP, "kind": "RSR_COMBINATION_SAVED_STATE_W0",
            "stage": _STAGES[method], "group_id": GROUP, "base_representation": "W0",
            "input_atom_ids": sorted(atom.atom_id for atom in atoms),
            "new_candidate_ids": [LANG_ID, WD_ID],
            "candidate_evaluation": "NOT_CALLED_SAVED_CELLS_ONLY"}


def _counts():
    return {"actual_fit_invocations": 1, "actual_sparse_fit_invocations": 0,
            "actual_retention_invocations": 0, "threshold_fit_calls": 0,
            "threshold_fit_calls_unit": "TRAIN_ENCODER_INVOCATION", "candidate_evaluations": 0}


def _finish(access, binding, method, atoms, encoder, problem, selected, outcome,
            failure, started, counts, initialization=None):
    status = "FAILED" if outcome["status"].startswith("FAILED") else "FITTED" if selected else "EMPTY_MODEL"
    if status == "FAILED":
        selected = ()
        if failure is None:
            failure = {"stage": _STAGES[method], "exception_type": None,
                       "reason": outcome.get("stop", outcome["status"])}
    audit = dict(outcome, **counts, adapter_version=VERSION, group_id=GROUP, stage=_STAGES[method],
                 train_ids=list(access.ids), train_expected_n=len(access.ids), train_consumed_n=len(access.rows),
                 fit_scope="COMBINATION_EXACT_AUTHORIZED_TRAIN_ONLY",
                 freeze_time=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                 candidate_pool_size=len(problem.candidates) if problem is not None else None,
                 registered_clause_count=len(problem.manifest) if problem is not None else None,
                 failure=deepcopy(failure))
    if problem is not None:
        audit.update(training_result=json_score(problem.score(selected)), clean_budget_count=problem.budget,
                     clean_denominator=len(problem.clean), support_scope="COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY")
    if initialization is not None:
        audit.update(initialization=deepcopy(initialization), signal_group_version=GROUP_VERSION)
    selected_ids = {literal.atom_id for clause in selected for literal in clause.literals}
    model = RuleModel(method, status, tuple(selected), tuple(atom for atom in atoms if atom.atom_id in selected_ids),
                      deepcopy(binding), _view(method, atoms), audit, encoder=encoder)
    return model, tuple(selected), failure


def fit_sparse(job, raw_rows, metadata, defs, *, binding, candidate_rows):
    """One own-fold GREEDY initialization, never a borrowed four-group model."""
    definitions, access = _preflight(job, raw_rows, metadata, defs, binding, candidate_rows, "GREEDY_OR")
    started = time.monotonic()
    deadline = started + 60
    problem, atoms, encoder, selected, trace = None, (), {}, (), []
    failure, stage, counts = None, "TRAIN_ENCODER", _counts()
    try:
        counts["threshold_fit_calls"] += 1
        rows, atoms, encoder, _ = encode_train(access, definitions, "S_FLAT")
        if OLD_WD in {atom.atom_id for atom in atoms}:
            raise ValueError("REMOVED_WEBDRIVER_ATOM_REAPPEARED")
        stage = "TRAIN_SUPPORT"
        problem = V2Problem(access, rows, atoms, deadline)
        stage = "GREEDY_SELECTION"
        access.assert_fit(access.batch(), "pruning")
        counts["actual_sparse_fit_invocations"] += 1
        selected, outcome, trace = greedy(problem, deadline)
        stage = "FINAL_TRAIN_CONSTRAINT_CHECK"
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("COMBINATION_SPARSE_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": stage, "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    model, selected, failure = _finish(access, binding, "GREEDY_OR", atoms, encoder, problem,
                                      selected, outcome, failure, started, counts)
    training = sparse._training_details(problem, atoms, selected, trace, access, GROUP, failure)
    training.update(schema_version="rsr-combination-sparse-training-v1", adapter_version=VERSION, stage="SPARSE")
    return model, training


def _initial_identity(initial, training, job):
    _model_identity(initial)
    if (initial.method_id != "GREEDY_OR" or initial.status not in ("FITTED", "EMPTY_MODEL")
            or initial.binding["fold_id"] != job["fold_id"]
            or initial.fit.get("train_ids") != job["train_ids"]
            or initial.fit.get("train_expected_n") != len(job["train_ids"])
            or initial.fit.get("train_consumed_n") != len(job["train_ids"])
            or initial.encoder.get("train_ids") != job["train_ids"]
            or initial.encoder.get("fold_id") != job["fold_id"]):
        raise PermissionError("COMBINATION_INITIAL_GROUP_STAGE_FOLD_OR_TRAIN_MISMATCH")
    if (type(training) is not dict or training.get("schema_version") != "rsr-combination-sparse-training-v1"
            or training.get("adapter_version") != VERSION or training.get("stage") != "SPARSE"
            or training.get("group_id") != GROUP or training.get("train_ids") != job["train_ids"]
            or training.get("failure") is not None):
        raise PermissionError("COMBINATION_INITIAL_TRAINING_IDENTITY_MISMATCH")
    if (initial.encoder.get("version") != "v2-a-adapter-1"
            or initial.encoder.get("semantics") != "V1_TRAIN_QUANTILES_UNCHANGED"):
        raise PermissionError("COMBINATION_INITIAL_ENCODER_VERSION_MISMATCH")


def fit_retention(job, raw_rows, metadata, defs, *, binding, candidate_rows,
                  initial_model, initial_training):
    """Continue only this combination's verified saved sparse initialization."""
    definitions, access = _preflight(job, raw_rows, metadata, defs, binding, candidate_rows, "R_KEEP_V1")
    _initial_identity(initial_model, initial_training, job)
    started = time.monotonic()
    deadline = started + 60
    encoder = deepcopy(initial_model.encoder)
    atoms = frozen_atoms(definitions, encoder, "W0")
    groups = {atom.atom_id: signal_group(atom) for atom in atoms}
    rows = {opaque_id: transform_numeric(row, encoder) for opaque_id, row in access.rows.items()}
    problem = V2Problem(access, rows, atoms, deadline)
    # Generic content comparison only; this helper does not issue an old-group
    # identity or invoke any fit.  New stage identity was checked above.
    _verify_initial(initial_model, initial_training, problem, atoms, groups)
    initial_ids = {clause.id for clause in initial_model.clauses}
    initialization = {"type": "MATCHING_SAVED_COMBINATION_SPARSE_INITIALIZATION",
                      "model_id": initial_model.model_id, "source": job.get("initial_model_ref"),
                      "threshold_refit": False, "sparse_selector_refit": False,
                      "outer_predictions_or_scores_used": False, "train_and_fold_binding_verified": True,
                      "candidate_support_and_training_score_verified": True, "signal_group_mapping_verified": True}
    trace, failure, counts = [], None, _counts()
    try:
        counts["actual_retention_invocations"] += 1
        selected, outcome, trace = retain(problem, initial_model.clauses, groups, deadline)
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("COMBINATION_RETENTION_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": "RKEEP_RETENTION", "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    model, selected, failure = _finish(access, binding, "R_KEEP_V1", atoms, encoder, problem,
                                      selected, outcome, failure, started, counts, initialization)
    training = compact_training(problem, atoms, selected, initial_ids, groups, trace,
                                {"method": "R_KEEP_V1"}, initialization, access)
    training.update(schema_version="rsr-combination-retention-training-v1", adapter_version=VERSION,
                    stage="RETENTION", group_id=GROUP, support=deepcopy(problem.support),
                    encoded_atoms=[asdict(atom) for atom in atoms], train_ids=list(access.ids),
                    failure=deepcopy(failure))
    return model, training


def _model_identity(model):
    if type(model) is not RuleModel:
        raise TypeError("RULE_MODEL_REQUIRED")
    _identity(model.binding, model.method_id, model.binding.get("fold_id"))
    expected = _view(model.method_id, ())
    if any(model.view.get(key) != expected[key] for key in
           ("view_id", "kind", "stage", "group_id", "base_representation", "new_candidate_ids")):
        raise PermissionError("COMBINATION_MODEL_VIEW_IDENTITY_MISMATCH")
    model.model_id


def predict_current(model, opaque_id, raw, candidate_cells=None):
    """Apply the saved stage model with cached selected cells, without refitting."""
    _model_identity(model)
    if model.status in ("FAILED", "EMPTY_MODEL"):
        return predict(model, opaque_id, {})
    try:
        current = deepcopy(raw)
        selected_ids = [atom.atom_id for atom in model.atoms]
        for candidate_id in (LANG_ID, WD_ID):
            if candidate_id in selected_ids:
                if type(candidate_cells) is not dict or candidate_id not in candidate_cells:
                    raise ValueError("MISSING_SAVED_CURRENT_CANDIDATE_CELL:" + candidate_id)
                current[candidate_id] = kernel_cell(candidate_cells[candidate_id], candidate_id)
        row = transform_numeric(current, model.encoder, required_atoms=selected_ids)
        return predict(model, opaque_id, {"features": row, "view_id": model.view["view_id"]})
    except Exception as exc:
        result = predict(model, opaque_id, {})
        result.update(decision="FAILED", failure_reason="RSR_COMBINATION_TRANSFORM:" + type(exc).__name__ + ":" + str(exc))
        return result


def save_model(model, path):
    _model_identity(model)
    _save_model(model, path)


def load_model(path):
    model = _load_model(path)
    _model_identity(model)
    return model
