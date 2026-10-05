"""Explicit mixed-observation W0 stages over caller-supplied, saved cells.

This adapter defines a new study identity; it cannot load an old legacy-only
model as a mixed model or continuation. The encoder, support, GREEDY and R_KEEP
mathematics are reused unchanged. Source modes are external provenance audited
in the model, never features. No collection, candidate evaluation, scheduling,
training or prediction runs on import. Only explicit save/load accesses files;
fit methods consult the existing frozen training contracts.

The caller owns authorization, source registration, execution budget and test
isolation. Providing a correctly shaped binding is not itself authorization.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import time

from . import rule_semantics_combination as combination
from . import rule_semantics_retraining as sparse
from .rule_semantics_rkeep_retraining import _verify_initial
from .rule_learning.baselines import transform_numeric
from .rule_learning.models import RuleModel, load_model as _load_model, save_model as _save_model
from .rule_learning.predictor import predict
from .rule_learning.selector import greedy, json_score
from .rule_learning_v2.adapter import TrainAccess, V2Problem, approved_atoms, encode_train
from .rule_learning_v2.b_engine import compact_training, frozen_atoms
from .rule_learning_v2.retention import GROUP_VERSION, retain, signal_group

VERSION = "rsr-mixed-retraining-adapter-v1"
STUDY_VERSION = "rule-semantics-mixed-retraining-v1"
PHASE = "RSR_MIXED_RETRAINING"
GROUPS = ("BASE", "LANG_ADD_WD_REPLACE")
SOURCE_MODES = ("legacy_projection_v1", "raw_observation_v1")
SOURCE_MODE_POLICY = "PER_RECORD_EXPLICIT_LEGACY_OR_RAW"
SOURCE_MODE_SCHEMA = "rsr-mixed-source-modes-v1"
LANG_ID, WD_ID = sparse.LANG_ID, sparse.WD_ID
OLD_LANG, OLD_WD = sparse.OLD_LANG, sparse.OLD_WD
kernel_cell = sparse.kernel_cell
_STAGES = {"GREEDY_OR": "SPARSE", "R_KEEP_V1": "RETENTION"}


def _group(group):
    if type(group) is not str or group not in GROUPS:
        raise ValueError("UNREGISTERED_MIXED_RETRAINING_GROUP")


def source_mode_manifest(source_modes, ids):
    """Validate exact caller registration, without guessing from values or IDs."""
    if (not ids or len(ids) != len(set(ids)) or type(source_modes) is not dict
            or set(source_modes) != set(ids)
            or any(type(sid) is not str or not sid for sid in ids)):
        raise PermissionError("EXACT_SOURCE_MODE_MEMBERS_REQUIRED")
    if any(type(mode) is not str or mode not in SOURCE_MODES for mode in source_modes.values()):
        raise PermissionError("EXPLICIT_LEGACY_OR_RAW_SOURCE_MODE_REQUIRED")
    counts = Counter(source_modes.values())
    return {"schema_version": SOURCE_MODE_SCHEMA, "policy": SOURCE_MODE_POLICY,
            "per_record": {sid: source_modes[sid] for sid in ids},
            "counts": {mode: counts[mode] for mode in SOURCE_MODES},
            "use": "PROVENANCE_ONLY_NEVER_PREDICTION_FEATURE"}


def group_definitions(defs, group):
    """BASE keeps W0; combination adds language, retains length, replaces WD."""
    _group(group)
    if group == "BASE":
        return sparse.group_definitions(defs, "BASE")
    result = combination.group_definitions(defs)
    atom = next(a for a in result["atoms"] if a["atom_id"] == WD_ID)
    atom["provenance"].update(
        mode=SOURCE_MODE_POLICY,
        gate_version="rsr-webdriver-per-record-explicit-mode-gate-v1",
        mode_gate_versions={"legacy_projection_v1": "rsr-webdriver-legacy-gate-v1",
                            "raw_observation_v1": "rsr-webdriver-raw-gate-v1"},
        source_mode_schema_version=SOURCE_MODE_SCHEMA,
        source_mode_use="EXTERNAL_PROVENANCE_NOT_FEATURE",
    )
    return result


def _check_cell_mode(cell, source_mode):
    # The registered cache must carry the mode even for U/FAILED. A cell missing
    # that lineage is rejected instead of assigning a mode from its value.
    if type(cell) is not dict:
        raise ValueError("SAVED_WEBDRIVER_CELL_REQUIRED")
    diagnostics = cell.get("diagnostics")
    if type(diagnostics) is not dict or diagnostics.get("mode") != source_mode:
        raise PermissionError("SAVED_WEBDRIVER_SOURCE_MODE_MISMATCH")


def project_rows(raw_rows, defs, group, *, source_modes, candidate_rows=None):
    """Copy only declared atom cells; per-record mode never enters a row."""
    _group(group)
    if type(raw_rows) is not dict:
        raise ValueError("RAW_ROWS_MAPPING_REQUIRED")
    source_mode_manifest(source_modes, tuple(raw_rows))
    if group == "BASE":
        return sparse.project_rows(raw_rows, defs, "BASE", candidate_rows)
    if type(candidate_rows) is not dict or set(candidate_rows) != set(raw_rows):
        raise PermissionError("EXACT_MIXED_CANDIDATE_MEMBERS_REQUIRED")
    for sid in raw_rows:
        saved = candidate_rows[sid]
        if type(saved) is not dict or WD_ID not in saved:
            raise ValueError("BOTH_SAVED_COMBINATION_CELLS_REQUIRED")
        _check_cell_mode(saved[WD_ID], source_modes[sid])
    return combination.project_rows(raw_rows, defs, candidate_rows)


def _identity(binding, group, method, fold_id):
    _group(group)
    expected = {"study_version": STUDY_VERSION, "phase": PHASE, "group_id": group,
                "method_id": method, "operating_point": "OP05", "fold_id": fold_id}
    if (method not in _STAGES or type(fold_id) is not str or not fold_id
            or type(binding) is not dict or any(binding.get(key) != value for key, value in expected.items())):
        raise PermissionError("EXPLICIT_MIXED_STAGE_IDENTITY_REQUIRED")


def _preflight(job, raw_rows, metadata, defs, binding, group, candidate_rows, source_modes, method):
    _identity(binding, group, method, job["fold_id"])
    ids = tuple(job["train_ids"])
    if (not ids or len(ids) != len(set(ids)) or type(raw_rows) is not dict or type(metadata) is not dict
            or set(raw_rows) != set(ids) or set(metadata) != set(ids)
            or set(ids) & set(job["outer_test_ids"])):
        raise PermissionError("EXACT_TRAIN_MEMBERS_ONLY")
    manifest = source_mode_manifest(source_modes, ids)
    sparse._frozen_contract()
    definitions = group_definitions(defs, group)
    for atom in approved_atoms(definitions):
        signal_group(atom)
    projected = project_rows(raw_rows, defs, group, source_modes=source_modes, candidate_rows=candidate_rows)
    return definitions, TrainAccess(job, projected, metadata), manifest


def _view(group, method, atoms):
    return {"view_id": PHASE + ":" + group + ":" + _STAGES[method],
            "representation": group, "kind": "RSR_MIXED_SAVED_STATE_W0",
            "stage": _STAGES[method], "group_id": group, "base_representation": "W0",
            "input_atom_ids": sorted(atom.atom_id for atom in atoms),
            "new_candidate_ids": [] if group == "BASE" else [LANG_ID, WD_ID],
            "candidate_evaluation": "NOT_CALLED_SAVED_CELLS_ONLY",
            "source_mode_policy": SOURCE_MODE_POLICY,
            "source_mode_schema_version": SOURCE_MODE_SCHEMA,
            "source_mode_feature": False}


def _counts():
    return {"actual_fit_invocations": 1, "actual_sparse_fit_invocations": 0,
            "actual_retention_invocations": 0, "threshold_fit_calls": 0,
            "threshold_fit_calls_unit": "TRAIN_ENCODER_INVOCATION", "candidate_evaluations": 0}


def _finish(access, binding, group, method, atoms, encoder, problem, selected, outcome,
            failure, started, counts, source_manifest, initialization=None):
    status = "FAILED" if outcome["status"].startswith("FAILED") else "FITTED" if selected else "EMPTY_MODEL"
    if status == "FAILED":
        selected = ()
        if failure is None:
            failure = {"stage": _STAGES[method], "exception_type": None,
                       "reason": outcome.get("stop", outcome["status"])}
    audit = dict(outcome, **counts, adapter_version=VERSION, group_id=group, stage=_STAGES[method],
                 train_ids=list(access.ids), train_expected_n=len(access.ids), train_consumed_n=len(access.rows),
                 fit_scope="MIXED_EXACT_AUTHORIZED_TRAIN_ONLY",
                 freeze_time=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                 candidate_pool_size=len(problem.candidates) if problem is not None else None,
                 registered_clause_count=len(problem.manifest) if problem is not None else None,
                 failure=deepcopy(failure), source_mode_manifest=deepcopy(source_manifest))
    if problem is not None:
        audit.update(training_result=json_score(problem.score(selected)), clean_budget_count=problem.budget,
                     clean_denominator=len(problem.clean), support_scope="COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY")
    if initialization is not None:
        audit.update(initialization=deepcopy(initialization), signal_group_version=GROUP_VERSION)
    selected_ids = {literal.atom_id for clause in selected for literal in clause.literals}
    model = RuleModel(method, status, tuple(selected), tuple(atom for atom in atoms if atom.atom_id in selected_ids),
                      deepcopy(binding), _view(group, method, atoms), audit, encoder=encoder)
    return model, tuple(selected), failure


def fit_sparse(job, raw_rows, metadata, defs, *, group, binding, source_modes, candidate_rows=None):
    """One own-fold sparse stage, using the unchanged train-only encoder/selector."""
    definitions, access, manifest = _preflight(
        job, raw_rows, metadata, defs, binding, group, candidate_rows, source_modes, "GREEDY_OR")
    started = time.monotonic()
    deadline = started + 60
    problem, atoms, encoder, selected, trace = None, (), {}, (), []
    failure, stage, counts = None, "TRAIN_ENCODER", _counts()
    try:
        counts["threshold_fit_calls"] += 1
        rows, atoms, encoder, _ = encode_train(access, definitions, "S_FLAT")
        if group != "BASE" and OLD_WD in {atom.atom_id for atom in atoms}:
            raise ValueError("REMOVED_WEBDRIVER_ATOM_REAPPEARED")
        stage = "TRAIN_SUPPORT"
        problem = V2Problem(access, rows, atoms, deadline)
        stage = "GREEDY_SELECTION"
        access.assert_fit(access.batch(), "pruning")
        counts["actual_sparse_fit_invocations"] += 1
        selected, outcome, trace = greedy(problem, deadline)
        stage = "FINAL_TRAIN_CONSTRAINT_CHECK"
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("MIXED_SPARSE_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": stage, "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    model, selected, failure = _finish(access, binding, group, "GREEDY_OR", atoms, encoder, problem,
                                      selected, outcome, failure, started, counts, manifest)
    training = sparse._training_details(problem, atoms, selected, trace, access, group, failure)
    training.update(schema_version="rsr-mixed-sparse-training-v1", adapter_version=VERSION,
                    stage="SPARSE", source_mode_manifest=deepcopy(manifest))
    return model, training


def _model_identity(model):
    if type(model) is not RuleModel:
        raise TypeError("RULE_MODEL_REQUIRED")
    group = model.binding.get("group_id")
    _identity(model.binding, group, model.method_id, model.binding.get("fold_id"))
    expected = _view(group, model.method_id, ())
    if (model.status not in ("FITTED", "EMPTY_MODEL", "FAILED")
            or any(model.view.get(key) != value for key, value in expected.items() if key != "input_atom_ids")
            or model.fit.get("adapter_version") != VERSION or model.fit.get("group_id") != group
            or model.fit.get("stage") != _STAGES[model.method_id]):
        raise PermissionError("MIXED_MODEL_VIEW_OR_AUDIT_IDENTITY_MISMATCH")
    manifest = model.fit.get("source_mode_manifest")
    if (type(manifest) is not dict or manifest != source_mode_manifest(
            manifest.get("per_record"), model.fit.get("train_ids", []))):
        raise PermissionError("MIXED_MODEL_SOURCE_MODE_MANIFEST_REQUIRED")
    for atom in model.atoms:
        if atom.atom_id == WD_ID and (group == "BASE" or atom.provenance.get("mode") != SOURCE_MODE_POLICY):
            raise PermissionError("LEGACY_ONLY_WEBDRIVER_MODEL_METADATA_FORBIDDEN")
        if group != "BASE" and atom.atom_id == OLD_WD:
            raise PermissionError("REMOVED_WEBDRIVER_ATOM_IN_MIXED_MODEL")
    model.model_id


def _initial_identity(initial, training, job, group, source_manifest):
    _model_identity(initial)
    if (initial.method_id != "GREEDY_OR" or initial.status not in ("FITTED", "EMPTY_MODEL")
            or initial.binding["group_id"] != group or initial.binding["fold_id"] != job["fold_id"]
            or initial.fit.get("train_ids") != job["train_ids"]
            or initial.fit.get("train_expected_n") != len(job["train_ids"])
            or initial.fit.get("train_consumed_n") != len(job["train_ids"])
            or initial.encoder.get("train_ids") != job["train_ids"]
            or initial.encoder.get("fold_id") != job["fold_id"]
            or initial.fit.get("source_mode_manifest") != source_manifest):
        raise PermissionError("MIXED_INITIAL_GROUP_STAGE_FOLD_TRAIN_OR_MODE_MISMATCH")
    if (type(training) is not dict or training.get("schema_version") != "rsr-mixed-sparse-training-v1"
            or training.get("adapter_version") != VERSION or training.get("stage") != "SPARSE"
            or training.get("group_id") != group or training.get("train_ids") != job["train_ids"]
            or training.get("source_mode_manifest") != source_manifest or training.get("failure") is not None):
        raise PermissionError("MIXED_INITIAL_TRAINING_IDENTITY_MISMATCH")
    if (initial.encoder.get("version") != "v2-a-adapter-1"
            or initial.encoder.get("semantics") != "V1_TRAIN_QUANTILES_UNCHANGED"):
        raise PermissionError("MIXED_INITIAL_ENCODER_VERSION_MISMATCH")


def fit_retention(job, raw_rows, metadata, defs, *, group, binding, source_modes,
                  candidate_rows=None, initial_model, initial_training):
    """Continue only the exact same group/fold/train/mode sparse initialization."""
    definitions, access, manifest = _preflight(
        job, raw_rows, metadata, defs, binding, group, candidate_rows, source_modes, "R_KEEP_V1")
    _initial_identity(initial_model, initial_training, job, group, manifest)
    started = time.monotonic()
    deadline = started + 60
    encoder = deepcopy(initial_model.encoder)
    atoms = frozen_atoms(definitions, encoder, "W0")
    groups = {atom.atom_id: signal_group(atom) for atom in atoms}
    rows = {sid: transform_numeric(row, encoder) for sid, row in access.rows.items()}
    problem = V2Problem(access, rows, atoms, deadline)
    _verify_initial(initial_model, initial_training, problem, atoms, groups)
    initial_ids = {clause.id for clause in initial_model.clauses}
    initialization = {"type": "MATCHING_SAVED_MIXED_SPARSE_INITIALIZATION",
                      "model_id": initial_model.model_id, "source": job.get("initial_model_ref"),
                      "threshold_refit": False, "sparse_selector_refit": False,
                      "outer_predictions_or_scores_used": False, "train_and_fold_binding_verified": True,
                      "candidate_support_and_training_score_verified": True, "signal_group_mapping_verified": True,
                      "source_mode_manifest_verified": True}
    trace, failure, counts = [], None, _counts()
    try:
        counts["actual_retention_invocations"] += 1
        selected, outcome, trace = retain(problem, initial_model.clauses, groups, deadline)
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("MIXED_RETENTION_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": "RKEEP_RETENTION", "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    model, selected, failure = _finish(access, binding, group, "R_KEEP_V1", atoms, encoder, problem,
                                      selected, outcome, failure, started, counts, manifest, initialization)
    training = compact_training(problem, atoms, selected, initial_ids, groups, trace,
                                {"method": "R_KEEP_V1"}, initialization, access)
    training.update(schema_version="rsr-mixed-retention-training-v1", adapter_version=VERSION,
                    stage="RETENTION", group_id=group, support=deepcopy(problem.support),
                    encoded_atoms=[asdict(atom) for atom in atoms], train_ids=list(access.ids),
                    failure=deepcopy(failure), source_mode_manifest=deepcopy(manifest))
    return model, training


def predict_current(model, opaque_id, raw, candidate_cells=None, *, source_mode):
    """Use the saved encoder and cells with one explicit current observation mode."""
    _model_identity(model)
    source_mode_manifest({opaque_id: source_mode}, [opaque_id])
    registered = model.fit["source_mode_manifest"]["per_record"].get(opaque_id)
    if registered is not None and registered != source_mode:
        raise PermissionError("CURRENT_SOURCE_MODE_CONFLICTS_WITH_SAVED_MEMBER")
    if model.status in ("FAILED", "EMPTY_MODEL"):
        result = predict(model, opaque_id, {})
    else:
        try:
            current = deepcopy(raw)
            selected_ids = [atom.atom_id for atom in model.atoms]
            for candidate_id in model.view["new_candidate_ids"]:
                if candidate_id in selected_ids:
                    if type(candidate_cells) is not dict or candidate_id not in candidate_cells:
                        raise ValueError("MISSING_SAVED_CURRENT_CANDIDATE_CELL:" + candidate_id)
                    if candidate_id == WD_ID:
                        _check_cell_mode(candidate_cells[candidate_id], source_mode)
                    current[candidate_id] = kernel_cell(candidate_cells[candidate_id], candidate_id)
            row = transform_numeric(current, model.encoder, required_atoms=selected_ids)
            result = predict(model, opaque_id, {"features": row, "view_id": model.view["view_id"]})
        except Exception as exc:
            result = predict(model, opaque_id, {})
            result.update(decision="FAILED", failure_reason="RSR_MIXED_TRANSFORM:" + type(exc).__name__ + ":" + str(exc))
    result["source_observation_mode"] = source_mode
    return result


def save_model(model, path):
    _model_identity(model)
    _save_model(model, path)


def load_model(path):
    model = _load_model(path)
    _model_identity(model)
    return model
