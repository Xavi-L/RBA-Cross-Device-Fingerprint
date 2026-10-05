"""Same-cohort BASE49 versus WEBGL50 with an independent CAP8 profile.

Only WEBGL50 adds the registered saved WebGL1 cell. No candidate evaluation,
source-field repair, old-observation backfill or test-dependent selection occurs.
Caller owns exact membership, authorization and the twelve-stage-fit schedule.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import time
from itertools import combinations
from pathlib import Path

from . import rule_semantics_combination as combination
from . import rule_semantics_retraining as sparse
from .rule_semantics_rkeep_retraining import _verify_initial
from .rule_learning.baselines import transform_numeric
from .rule_learning.models import save_model as _save_model
from .rule_learning.models import RuleModel as BaseRuleModel
from . import webgl1_selector_integration as webgl
from . import rule_semantics_capacity as capacity
from .rule_learning.predictor import predict
from .rule_learning.selector import json_score
from .rule_learning_v2.semantic_selection import CATALOG_VERSION, greedy_semantic, retain_semantic, semantic_catalog
from .rule_learning_v2.adapter import TrainAccess, V2Problem, approved_atoms, encode_train
from .rule_learning_v2.b_engine import frozen_atoms
from .rule_learning_v2.retention import signal_group

VERSION = "rsr-webgl1-cap8-adapter-v1"
EXPERIMENT = "webgl1-cap8-comparison-v1"
STUDY_VERSION = "rule-semantics-webgl1-cap8-v1"
PHASE = "RSR_WEBGL1_CAP8_COMPARISON"
GROUPS = ("BASE49", "WEBGL50")
SOURCE_MODES = ("legacy_projection_v1", "raw_observation_v1")
SOURCE_MODE_POLICY = "PER_RECORD_EXPLICIT_LEGACY_OR_RAW"
SOURCE_MODE_SCHEMA = "rsr-mixed-source-modes-v1"
LANG_ID, WD_ID = sparse.LANG_ID, sparse.WD_ID
OLD_LANG, OLD_WD = sparse.OLD_LANG, sparse.OLD_WD
kernel_cell = sparse.kernel_cell
_STAGES = {"GREEDY_SEMANTIC_V2": "SPARSE", "R_KEEP_SWAP_V2": "RETENTION"}


# Local profile: never mutate or override the frozen CAP7 module globals.
PROFILE = {"profile_id": "W0_CAPACITY_8_V1", "max_clauses": 8,
           "max_complexity": 16, "max_additions": 8, "max_literals": 12,
           "max_distinct_atoms": 12, "max_clauses_per_family": 2}


def apply_capacity(problem):
    """Change only the registered capacity controls on private contract copies."""
    problem.search = deepcopy(problem.search)
    problem.grammar = deepcopy(problem.grammar)
    problem.search["constraints"]["max_clauses"] = PROFILE["max_clauses"]
    problem.search["constraints"]["max_complexity_primary"] = PROFILE["max_complexity"]
    problem.search["algorithms"]["GREEDY_OR"]["max_additions"] = PROFILE["max_additions"]
    problem.grammar["composition"]["max_selected_clauses"] = PROFILE["max_clauses"]
    return problem


@dataclass(frozen=True)
class RuleModel(BaseRuleModel):
    """CAP8 structural checks with an independent model identity."""
    schema_version: str = "rsr-webgl1-cap8-rule-model-v1"

    def __post_init__(self):
        expected = {"experiment_id": EXPERIMENT, "study_version": STUDY_VERSION, "phase": PHASE,
                    "capacity_profile": PROFILE["profile_id"]}
        if (any(self.binding.get(k) != v for k, v in expected.items())
                or self.method_id not in ("GREEDY_SEMANTIC_V2", "R_KEEP_SWAP_V2")
                or self.fit.get("capacity_profile") != PROFILE
                or self.view.get("capacity_profile") != PROFILE):
            raise ValueError("EXPLICIT_CAPACITY_MODEL_IDENTITY_REQUIRED")

        if self.schema_version != "rsr-webgl1-cap8-rule-model-v1" or self.status not in ("FITTED", "FIXED", "EMPTY_MODEL", "FAILED"):
            raise ValueError("INVALID_MODEL_SCHEMA_OR_STATUS")
        ids = [a.atom_id for a in self.atoms]
        if len(ids) != len(set(ids)) or len({c.id for c in self.clauses}) != len(self.clauses):
            raise ValueError("DUPLICATE_MODEL_ATOM_OR_CLAUSE")
        if any(l.atom_id not in ids for c in self.clauses for l in c.literals):
            raise ValueError("UNBOUND_MODEL_LITERAL")
        if self.status in ("FAILED", "EMPTY_MODEL") and (self.clauses or self.constant):
            raise ValueError("NONEXECUTABLE_MODEL_HAS_RULES")
        if self.status in ("FITTED", "FIXED") and not self.clauses and self.constant is None:
            raise ValueError("EMPTY_IS_NOT_ALWAYS_NO_ALERT")
        if self.constant is not None and (self.status != "FIXED" or self.clauses or self.constant not in ("NO_ALERT", "INSUFFICIENT_EVIDENCE")):
            raise ValueError("INVALID_CONSTANT_REFERENCE")
        if set(ids) != {l.atom_id for c in self.clauses for l in c.literals}:
            raise ValueError("MODEL_ATOMS_MUST_EQUAL_SELECTED_DEPENDENCIES")
        atom_index = {a.atom_id: a for a in self.atoms}
        signs, families = defaultdict(set), Counter()
        for c in self.clauses:
            fs = {atom_index[l.atom_id].family for l in c.literals}
            if len(fs) != len(c.literals):
                raise ValueError("SAME_FAMILY_AND_FORBIDDEN")
            families.update(fs)
            for l in c.literals:
                signs[l.atom_id].add(l.polarity)
        if any(len(s) > 1 for s in signs.values()):
            raise ValueError("MODEL_OPPOSITE_POLARITIES_FORBIDDEN")
        if any(set(a.literals) <= set(b.literals) or set(b.literals) <= set(a.literals) for a, b in combinations(self.clauses, 2)):
            raise ValueError("MODEL_SUBSUMED_CLAUSES_FORBIDDEN")
        if self.status == "FITTED":
            maximum_length = 2 if self.method_id == "FINITE_IP_DNF2" else 1
            maximum_cost = PROFILE["max_complexity"]
            if (len(self.clauses) > PROFILE["max_clauses"] or len(ids) > 12 or sum(len(c.literals) for c in self.clauses) > 12
                    or sum(c.cost for c in self.clauses) > maximum_cost or any(v > 2 for v in families.values())
                    or any(len(c.literals) > maximum_length for c in self.clauses)):
                raise ValueError("FITTED_MODEL_EXCEEDS_REGISTERED_CAPACITY")
        object.__setattr__(self, "_frozen_content", self._content())

    @property
    def model_id(self):
        return "rsr-webgl1-cap8-" + super().model_id.removeprefix("r03-")


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
    """Unchanged candidate pools; WEBGL50 has exactly one extra registered atom."""
    _group(group)
    base = capacity.group_definitions(defs, "LANG_ADD_WD_REPLACE")
    return webgl.register_definitions(base) if group == "WEBGL50" else base


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
    if type(candidate_rows) is not dict or set(candidate_rows) != set(raw_rows):
        raise PermissionError("EXACT_MIXED_CANDIDATE_MEMBERS_REQUIRED")
    for sid in raw_rows:
        saved = candidate_rows[sid]
        if type(saved) is not dict or WD_ID not in saved:
            raise ValueError("BOTH_SAVED_COMBINATION_CELLS_REQUIRED")
        _check_cell_mode(saved[WD_ID], source_modes[sid])
    base = combination.project_rows(raw_rows, defs, candidate_rows)
    if group == "BASE49":
        return base
    saved_webgl = {}
    for sid, saved in candidate_rows.items():
        if webgl.CANDIDATE_ID not in saved:
            raise ValueError("SAVED_WEBGL1_CELL_REQUIRED:" + sid)
        saved_webgl[sid] = saved[webgl.CANDIDATE_ID]
    return webgl.project_rows(base, group_definitions(defs, group), saved_webgl)


def _identity(binding, group, method, fold_id):
    _group(group)
    expected = {"study_version": STUDY_VERSION, "phase": PHASE,
                "experiment_id": EXPERIMENT, "group_id": group,
                "method_id": method, "operating_point": "OP05", "fold_id": fold_id,
                "capacity_profile": PROFILE["profile_id"]}
    if (method not in _STAGES or type(fold_id) is not str or not fold_id
            or type(binding) is not dict or any(binding.get(key) != value for key, value in expected.items())):
        raise PermissionError("EXPLICIT_MIXED_STAGE_IDENTITY_REQUIRED")


def _preflight(job, raw_rows, metadata, defs, binding, group, candidate_rows, source_modes, method):
    _identity(binding, group, method, job["fold_id"])
    if job.get("capacity_profile") != PROFILE["profile_id"]:
        raise PermissionError("EXPLICIT_CAPACITY_JOB_REQUIRED")
    ids = tuple(job["train_ids"])
    if (not ids or len(ids) != len(set(ids)) or type(raw_rows) is not dict or type(metadata) is not dict
            or set(raw_rows) != set(ids) or set(metadata) != set(ids)
            or set(ids) & set(job["outer_test_ids"])):
        raise PermissionError("EXACT_TRAIN_MEMBERS_ONLY")
    manifest = source_mode_manifest(source_modes, ids)
    # Verify the original support/constraints/encoder baseline is untouched.
    # Its original lexical tie declaration is overridden only in this new study.
    sparse._frozen_contract()
    if any(mode != "raw_observation_v1" for mode in source_modes.values()):
        raise PermissionError("SELECTOR_V2_RAW_ONLY_REQUIRED")
    definitions = group_definitions(defs, group)
    for atom in approved_atoms(definitions):
        signal_group(atom)
    projected = project_rows(raw_rows, defs, group, source_modes=source_modes, candidate_rows=candidate_rows)
    return definitions, TrainAccess(job, projected, metadata), manifest


def _view(group, method, atoms):
    return {"view_id": PHASE + ":" + group + ":" + _STAGES[method],
            "representation": group, "kind": "RSR_WEBGL1_CAP8_SAVED_STATE_W0",
            "capacity_profile": deepcopy(PROFILE),
            "stage": _STAGES[method], "group_id": group, "base_representation": "W0",
            "input_atom_ids": sorted(atom.atom_id for atom in atoms),
            "new_candidate_ids": [LANG_ID, WD_ID] + ([webgl.CANDIDATE_ID] if group == "WEBGL50" else []),
            "webgl_registration_version": webgl.VERSION if group == "WEBGL50" else None,
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
                 fit_scope="RAW_ONLY_SEMANTIC_SELECTOR_EXACT_TRAIN_ONLY",
                 freeze_time=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                 candidate_pool_size=len(problem.candidates) if problem is not None else None,
                 registered_clause_count=len(problem.manifest) if problem is not None else None,
                 failure=deepcopy(failure), source_mode_manifest=deepcopy(source_manifest),
                 selector_policy="semantic-ties-and-guarded-swap-v2", capacity_profile=deepcopy(PROFILE))
    if problem is not None:
        audit.update(training_result=json_score(problem.score(selected)), clean_budget_count=problem.budget,
                     clean_denominator=len(problem.clean), support_scope="COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY")
    if initialization is not None:
        audit.update(initialization=deepcopy(initialization), signal_group_version=CATALOG_VERSION)
    selected_ids = {literal.atom_id for clause in selected for literal in clause.literals}
    model = RuleModel(method, status, tuple(selected), tuple(atom for atom in atoms if atom.atom_id in selected_ids),
                      deepcopy(binding), _view(group, method, atoms), audit, encoder=encoder)
    return model, tuple(selected), failure



def _training_details(problem, atoms, selected, trace, access, group, failure):
    catalog = semantic_catalog(atoms) if atoms and failure is None else {}
    groups = {atom_id: entry["signal_group"] for atom_id, entry in catalog.items()}
    selected_ids = {clause.id for clause in selected}
    manifest = []
    if problem is not None:
        for item in problem.manifest:
            record = deepcopy(item)
            record.update(selected=item["clause_id"] in selected_ids,
                          signal_group=groups.get(item["clause_id"].rsplit(":", 1)[0]),
                          selection_reasons=(list(item["reasons"]) or
                             ["V2_SELECTED" if item["clause_id"] in selected_ids else
                              "FIT_FAILED" if failure else "NOT_CHOSEN_BY_FROZEN_V2_SEARCH"]))
            manifest.append(record)
    return {"group_id": group, "trace": deepcopy(trace), "candidate_manifest": manifest,
            "support": deepcopy(problem.support) if problem is not None else {},
            "encoded_atoms": [asdict(atom) for atom in atoms], "signal_groups": groups,
            "semantic_catalog": catalog, "signal_group_version": CATALOG_VERSION,
            "access_operations": deepcopy(access.operations), "train_ids": list(access.ids),
            "statistics_scope": "EXACT_OWN_TRAIN_ONLY_NO_TEST_INPUT", "failure": deepcopy(failure)}


def fit_sparse(job, raw_rows, metadata, defs, *, group, binding, source_modes, candidate_rows=None):
    """One own-fold stage using original encoder and versioned semantic GREEDY."""
    definitions, access, manifest = _preflight(
        job, raw_rows, metadata, defs, binding, group, candidate_rows, source_modes, "GREEDY_SEMANTIC_V2")
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
        problem = apply_capacity(V2Problem(access, rows, atoms, deadline))
        stage = "GREEDY_SELECTION"
        access.assert_fit(access.batch(), "pruning")
        counts["actual_sparse_fit_invocations"] += 1
        selected, outcome, trace = greedy_semantic(problem, deadline)
        stage = "FINAL_TRAIN_CONSTRAINT_CHECK"
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("MIXED_SPARSE_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": stage, "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    model, selected, failure = _finish(access, binding, group, "GREEDY_SEMANTIC_V2", atoms, encoder, problem,
                                      selected, outcome, failure, started, counts, manifest)
    training = _training_details(problem, atoms, selected, trace, access, group, failure)
    training.update(schema_version="rsr-webgl1-cap8-sparse-training-v1", adapter_version=VERSION,
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
            or model.fit.get("selector_policy") != "semantic-ties-and-guarded-swap-v2"
            or model.fit.get("adapter_version") != VERSION or model.fit.get("group_id") != group
            or model.fit.get("stage") != _STAGES[model.method_id]):
        raise PermissionError("MIXED_MODEL_VIEW_OR_AUDIT_IDENTITY_MISMATCH")
    manifest = model.fit.get("source_mode_manifest")
    if (type(manifest) is not dict or manifest != source_mode_manifest(
            manifest.get("per_record"), model.fit.get("train_ids", []))):
        raise PermissionError("MIXED_MODEL_SOURCE_MODE_MANIFEST_REQUIRED")
    if any(mode != "raw_observation_v1" for mode in manifest["per_record"].values()):
        raise PermissionError("SELECTOR_V2_RAW_ONLY_REQUIRED")
    for atom in model.atoms:
        if atom.atom_id == WD_ID and atom.provenance.get("mode") != SOURCE_MODE_POLICY:
            raise PermissionError("LEGACY_ONLY_WEBDRIVER_MODEL_METADATA_FORBIDDEN")
        if atom.atom_id == webgl.CANDIDATE_ID and group != "WEBGL50":
            raise PermissionError("WEBGL1_FORBIDDEN_IN_BASE_MODEL")
        if atom.atom_id == OLD_WD:
            raise PermissionError("REMOVED_WEBDRIVER_ATOM_IN_MIXED_MODEL")
    model.model_id


def _initial_identity(initial, training, job, group, source_manifest):
    _model_identity(initial)
    if (initial.method_id != "GREEDY_SEMANTIC_V2" or initial.status not in ("FITTED", "EMPTY_MODEL")
            or initial.binding["group_id"] != group or initial.binding["fold_id"] != job["fold_id"]
            or initial.fit.get("train_ids") != job["train_ids"]
            or initial.fit.get("train_expected_n") != len(job["train_ids"])
            or initial.fit.get("train_consumed_n") != len(job["train_ids"])
            or initial.encoder.get("train_ids") != job["train_ids"]
            or initial.encoder.get("fold_id") != job["fold_id"]
            or initial.fit.get("source_mode_manifest") != source_manifest):
        raise PermissionError("MIXED_INITIAL_GROUP_STAGE_FOLD_TRAIN_OR_MODE_MISMATCH")
    if (type(training) is not dict or training.get("schema_version") != "rsr-webgl1-cap8-sparse-training-v1"
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
        job, raw_rows, metadata, defs, binding, group, candidate_rows, source_modes, "R_KEEP_SWAP_V2")
    _initial_identity(initial_model, initial_training, job, group, manifest)
    started = time.monotonic()
    deadline = started + 60
    encoder = deepcopy(initial_model.encoder)
    atoms = frozen_atoms(definitions, encoder, "W0")
    catalog = semantic_catalog(atoms)
    groups = {atom_id: entry["signal_group"] for atom_id, entry in catalog.items()}
    rows = {sid: transform_numeric(row, encoder) for sid, row in access.rows.items()}
    problem = apply_capacity(V2Problem(access, rows, atoms, deadline))
    _verify_initial(initial_model, initial_training, problem, atoms, groups)
    if json.dumps(initial_training.get("semantic_catalog"), sort_keys=True) != json.dumps(catalog, sort_keys=True):
        raise PermissionError("INITIAL_SEMANTIC_CATALOG_MISMATCH")
    initial_ids = {clause.id for clause in initial_model.clauses}
    initialization = {"type": "MATCHING_SAVED_SEMANTIC_SPARSE_INITIALIZATION",
                      "model_id": initial_model.model_id, "source": job.get("initial_model_ref"),
                      "threshold_refit": False, "sparse_selector_refit": False,
                      "outer_predictions_or_scores_used": False, "train_and_fold_binding_verified": True,
                      "candidate_support_and_training_score_verified": True, "signal_group_mapping_verified": True,
                      "source_mode_manifest_verified": True}
    trace, failure, counts = [], None, _counts()
    try:
        counts["actual_retention_invocations"] += 1
        selected, outcome, trace = retain_semantic(problem, initial_model.clauses, deadline)
        if selected and not problem.score(selected)["feasible"]:
            raise ValueError("MIXED_RETENTION_CONSTRAINT_FAILURE")
    except Exception as exc:
        selected = ()
        failure = {"stage": "RKEEP_RETENTION", "exception_type": type(exc).__name__, "reason": str(exc)}
        outcome = {"status": "FAILED_FIT", "reason": type(exc).__name__ + ":" + str(exc),
                   "infeasibility_proved": False}
    model, selected, failure = _finish(access, binding, group, "R_KEEP_SWAP_V2", atoms, encoder, problem,
                                      selected, outcome, failure, started, counts, manifest, initialization)
    training = _training_details(problem, atoms, selected, trace, access, group, failure)
    training.update(initialization=initialization, initial_clause_ids=sorted(initial_ids))
    training.update(schema_version="rsr-webgl1-cap8-retention-training-v1", adapter_version=VERSION,
                    stage="RETENTION", group_id=group, support=deepcopy(problem.support),
                    encoded_atoms=[asdict(atom) for atom in atoms], train_ids=list(access.ids),
                    failure=deepcopy(failure), source_mode_manifest=deepcopy(manifest))
    return model, training


def predict_current(model, opaque_id, raw, candidate_cells=None, *, source_mode):
    """Use the saved encoder and cells with one explicit current observation mode."""
    _model_identity(model)
    if source_mode != "raw_observation_v1":
        raise PermissionError("SELECTOR_V2_RAW_ONLY_REQUIRED")
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
                    current[candidate_id] = (webgl.kernel_cell(candidate_cells[candidate_id])
                        if candidate_id == webgl.CANDIDATE_ID
                        else kernel_cell(candidate_cells[candidate_id], candidate_id))
            row = transform_numeric(current, model.encoder, required_atoms=selected_ids)
            result = predict(model, opaque_id, {"features": row, "view_id": model.view["view_id"]})
        except Exception as exc:
            result = predict(model, opaque_id, {})
            result.update(decision="FAILED", failure_reason="RSR_SELECTOR_V2_TRANSFORM:" + type(exc).__name__ + ":" + str(exc))
    result["source_observation_mode"] = source_mode
    return result


def save_model(model, path):
    _model_identity(model)
    _save_model(model, path)


def load_model(path):
    model = RuleModel.from_dict(json.loads(Path(path).read_text()))
    _model_identity(model)
    return model
