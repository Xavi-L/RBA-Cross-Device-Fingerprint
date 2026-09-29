"""R_KEEP-only continuation of the four matching saved GREEDY training views.

No encoder fitting, sparse selection, candidate evaluation or record loading is
performed here.  Exact train rows, a saved initial model and its training record
are supplied by the caller.  The unchanged R_KEEP kernel owns retention math.
The caller owns the twelve-job budget and all actual execution/output records.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import time

from . import rule_semantics_retraining as sparse
from .rule_learning.baselines import transform_numeric
from .rule_learning.models import RuleModel, load_model as _load_model, save_model as _save_model
from .rule_learning.predictor import predict
from .rule_learning.selector import json_score
from .rule_learning_v2.adapter import TrainAccess, V2Problem
from .rule_learning_v2.b_engine import compact_training, frozen_atoms
from .rule_learning_v2.retention import GROUP_VERSION, retain, signal_group


VERSION = "rsr-rkeep-retraining-adapter-v1"
STUDY_VERSION = "rule-semantics-rkeep-retraining-v1"
PHASE = "RSR_RKEEP_RETRAINING"
GROUPS = sparse.GROUPS
LANG_ID, WD_ID = sparse.LANG_ID, sparse.WD_ID
OLD_LANG, OLD_WD = sparse.OLD_LANG, sparse.OLD_WD
group_definitions = sparse.group_definitions
project_rows = sparse.project_rows
kernel_cell = sparse.kernel_cell
_ADDED = {"BASE": None, "LANG_ADD": LANG_ID, "LANG_REPLACE": LANG_ID, "WD_REPLACE": WD_ID}


def _same(left, right):
    """Compare saved JSON content, allowing only its tuple-to-array round trip."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _identity(binding, group, fold_id):
    if type(group) is not str or group not in GROUPS:
        raise ValueError("UNREGISTERED_RKEEP_GROUP")
    expected = {"study_version": STUDY_VERSION, "phase": PHASE, "group_id": group,
                "fold_id": fold_id, "method_id": "R_KEEP_V1", "operating_point": "OP05"}
    if type(binding) is not dict or any(binding.get(key) != value for key, value in expected.items()):
        raise PermissionError("EXPLICIT_RSR_RKEEP_IDENTITY_REQUIRED")


def _initial_identity(initial, training, job, group):
    # Reuse the preceding adapter's binding and immutable-content validation.
    sparse._model_identity(initial)
    if (initial.status not in ("FITTED", "EMPTY_MODEL")
            or initial.binding["group_id"] != group or initial.binding["fold_id"] != job["fold_id"]
            or initial.fit["train_ids"] != job["train_ids"]
            or initial.fit["train_expected_n"] != len(job["train_ids"])
            or initial.fit["train_consumed_n"] != len(job["train_ids"])
            or initial.encoder.get("train_ids") != job["train_ids"]
            or initial.encoder.get("fold_id") != job["fold_id"]):
        raise PermissionError("INITIAL_MODEL_GROUP_FOLD_OR_TRAIN_MISMATCH")
    if (type(training) is not dict or training.get("schema_version") != "rsr-retraining-training-v1"
            or training.get("adapter_version") != sparse.VERSION or training.get("group_id") != group
            or training.get("train_ids") != job["train_ids"] or training.get("failure") is not None):
        raise PermissionError("INITIAL_TRAINING_RECORD_IDENTITY_MISMATCH")
    if (initial.encoder.get("version") != "v2-a-adapter-1"
            or initial.encoder.get("semantics") != "V1_TRAIN_QUANTILES_UNCHANGED"):
        raise PermissionError("INITIAL_ENCODER_VERSION_MISMATCH")


def _verify_initial(initial, training, problem, atoms, groups):
    if initial.view["input_atom_ids"] != sorted(a.atom_id for a in atoms):
        raise ValueError("INITIAL_ENCODER_CANDIDATE_SET_MISMATCH")
    if not _same(training.get("encoded_atoms"), [asdict(a) for a in atoms]):
        raise ValueError("INITIAL_ENCODED_ATOM_METADATA_MISMATCH")
    if not _same(training.get("signal_groups"), groups):
        raise ValueError("INITIAL_SIGNAL_GROUP_MAPPING_MISMATCH")
    saved = training.get("candidate_manifest")
    if type(saved) is not list:
        raise ValueError("INITIAL_CANDIDATE_MANIFEST_MISSING")
    by_id = {entry["clause_id"]: entry for entry in saved}
    if len(by_id) != len(saved) or set(by_id) != {entry["clause_id"] for entry in problem.manifest}:
        raise ValueError("INITIAL_CANDIDATE_MANIFEST_SET_MISMATCH")
    selected_ids = {clause.id for clause in initial.clauses}
    for current in problem.manifest:
        old = by_id[current["clause_id"]]
        if any(not _same(old.get(key), current[key]) for key in ("eligible", "reasons", "literal_ids")):
            raise ValueError("INITIAL_CANDIDATE_SUPPORT_COMPATIBILITY_MISMATCH:" + current["clause_id"])
        if (old.get("selected") is not (current["clause_id"] in selected_ids)
                or old.get("signal_group") != groups[current["clause_id"].rsplit(":", 1)[0]]):
            raise ValueError("INITIAL_CANDIDATE_SELECTION_OR_GROUP_MISMATCH:" + current["clause_id"])
    if not _same(training.get("support"), problem.support):
        raise ValueError("INITIAL_EXACT_TRAIN_SUPPORT_MISMATCH")
    if any(clause not in problem.candidates for clause in initial.clauses):
        raise ValueError("INITIAL_SELECTED_CLAUSE_OUTSIDE_ELIGIBLE_POOL")
    computed_score = json_score(problem.score(initial.clauses))
    if not _same(computed_score, initial.fit.get("training_result")):
        raise ValueError("INITIAL_EXACT_TRAIN_SCORE_MISMATCH")
    if (initial.fit.get("clean_budget_count") != problem.budget
            or initial.fit.get("clean_denominator") != len(problem.clean)
            or initial.fit.get("candidate_pool_size") != len(problem.candidates)
            or initial.fit.get("registered_clause_count") != len(problem.manifest)):
        raise ValueError("INITIAL_TRAIN_BUDGET_OR_POOL_COUNT_MISMATCH")
    if initial.clauses and not computed_score["feasible"]:
        raise ValueError("INITIAL_MODEL_NOT_FEASIBLE")


def fit_group(job, raw_rows, metadata, defs, *, group, binding, candidate_rows=None,
              initial_model, initial_training):
    """Validate the saved own-fold initialization, then call retain once.

    Identity/initialization mismatches raise before retention and never trigger
    a new sparse fit.  Exceptions from the retention stage produce a FAILED
    model and failure details.  No automatic retry or fallback is implemented.
    """
    _identity(binding, group, job["fold_id"])
    ids = tuple(job["train_ids"])
    if (not ids or len(ids) != len(set(ids)) or type(raw_rows) is not dict or type(metadata) is not dict
            or set(raw_rows) != set(ids) or set(metadata) != set(ids)
            or set(ids) & set(job["outer_test_ids"])):
        raise PermissionError("EXACT_TRAIN_MEMBERS_ONLY")
    sparse._frozen_contract()
    _initial_identity(initial_model, initial_training, job, group)
    definitions = group_definitions(defs, group)
    projected = project_rows(raw_rows, defs, group, candidate_rows)
    access = TrainAccess(job, projected, metadata)
    started = time.monotonic()
    deadline = started + 60  # Unchanged per-fit limit from the original B engine.
    encoder = deepcopy(initial_model.encoder)
    atoms = frozen_atoms(definitions, encoder, "W0")
    groups = {atom.atom_id: signal_group(atom) for atom in atoms}
    rows = {opaque_id: transform_numeric(row, encoder) for opaque_id, row in access.rows.items()}
    problem = V2Problem(access, rows, atoms, deadline)
    _verify_initial(initial_model, initial_training, problem, atoms, groups)
    initial_ids = {clause.id for clause in initial_model.clauses}
    init_info = {"type": "MATCHING_SAVED_SPARSE_INITIALIZATION",
                 "model_id": initial_model.model_id, "source": job.get("initial_model_ref"),
                 "threshold_refit": False, "sparse_selector_refit": False,
                 "outer_predictions_or_scores_used": False,
                 "train_and_fold_binding_verified": True,
                 "candidate_support_and_training_score_verified": True,
                 "signal_group_mapping_verified": True}
    trace, failure = [], None
    actual_retention_invocations = 0
    try:
        actual_retention_invocations += 1
        selected, outcome, trace = retain(problem, initial_model.clauses, groups, deadline)
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("RKEEP_FINAL_TRAIN_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": "RKEEP_RETENTION", "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    status = "FAILED" if outcome["status"].startswith("FAILED") else "FITTED" if selected else "EMPTY_MODEL"
    if status == "FAILED":
        selected = ()
        if failure is None:
            failure = {"stage": "RKEEP_RETENTION", "exception_type": None,
                       "reason": outcome.get("stop", outcome["status"])}
    view = {"view_id": PHASE + ":" + group, "representation": group,
            "kind": "RSR_RKEEP_SAVED_STATE_W0", "base_representation": "W0", "group_id": group,
            "input_atom_ids": sorted(a.atom_id for a in atoms),
            "new_candidate_ids": [_ADDED[group]] if _ADDED[group] else [],
            "candidate_evaluation": "NOT_CALLED_SAVED_CELLS_ONLY"}
    audit = dict(outcome, train_ids=list(access.ids), train_expected_n=len(access.ids),
                 train_consumed_n=len(access.rows), fit_scope="RSR_RKEEP_EXACT_AUTHORIZED_TRAIN_ONLY",
                 freeze_time=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                 actual_fit_invocations=1, actual_retention_invocations=actual_retention_invocations,
                 new_sparse_fit_calls=0, threshold_fit_calls=0, candidate_evaluations=0,
                 candidate_pool_size=len(problem.candidates), registered_clause_count=len(problem.manifest),
                 training_result=json_score(problem.score(selected)), clean_budget_count=problem.budget,
                 clean_denominator=len(problem.clean), support_scope="COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY",
                 initialization=init_info, adapter_version=VERSION, group_id=group,
                 signal_group_version=GROUP_VERSION, failure=failure,
                 internal_stages=["frozen_encoder_reuse", "train_support", "saved_sparse_verification", "train_signal_retention"])
    selected_atoms = {literal.atom_id for clause in selected for literal in clause.literals}
    model = RuleModel("R_KEEP_V1", status, tuple(selected), tuple(a for a in atoms if a.atom_id in selected_atoms),
                      deepcopy(binding), view, audit, encoder=encoder)
    training = compact_training(problem, atoms, tuple(selected), initial_ids, groups, trace,
                                {"method": "R_KEEP_V1"}, init_info, access)
    training.update(schema_version="rsr-rkeep-retraining-training-v1", adapter_version=VERSION,
                    group_id=group, support=deepcopy(problem.support), encoded_atoms=[asdict(a) for a in atoms],
                    train_ids=list(access.ids), failure=deepcopy(failure))
    return model, training


def _model_identity(model):
    if type(model) is not RuleModel:
        raise TypeError("RULE_MODEL_REQUIRED")
    _identity(model.binding, model.view.get("group_id"), model.binding.get("fold_id"))
    group = model.binding["group_id"]
    if (model.method_id != "R_KEEP_V1" or model.view.get("kind") != "RSR_RKEEP_SAVED_STATE_W0"
            or model.view.get("view_id") != PHASE + ":" + group
            or model.view.get("new_candidate_ids") != ([_ADDED[group]] if _ADDED[group] else [])):
        raise PermissionError("RKEEP_MODEL_VIEW_OR_CANDIDATE_IDENTITY_MISMATCH")
    model.model_id


def predict_current(model, opaque_id, raw, candidate_cells=None):
    """Apply the saved encoder and cached selected cells through the old predictor."""
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
        result.update(decision="FAILED", failure_reason="RSR_RKEEP_TRANSFORM:" + type(exc).__name__ + ":" + str(exc))
        return result


def save_model(model, path):
    _model_identity(model)
    _save_model(model, path)


def load_model(path):
    model = _load_model(path)
    _model_identity(model)
    return model
