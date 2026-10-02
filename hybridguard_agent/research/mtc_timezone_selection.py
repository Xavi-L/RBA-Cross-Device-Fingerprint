"""Opt-in B_REL_TZ model identity; unchanged B_REL preparation and selector.

Only representation/model identity changes. All selection functions are the
original greedy_semantic/retain_semantic and original dual-normal problem.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace

from . import mtc_constrained_reselection as base
from .rule_learning.baselines import transform_numeric
from .rule_learning.contracts import contract
from .rule_learning.models import RuleModel
from .rule_learning.predictor import predict
from .rule_learning.selector import compatible, json_score
from .rule_learning_v2.semantic_selection import semantic_catalog, greedy_semantic, retain_semantic
from .rule_semantics_webgl1_cap8 import PROFILE, apply_capacity

VERSION = 'timezone-relation-validation-v1'
SCHEMA = 'mtc-timezone-relation-model-v1'


# Reuse old encoder fitting, exact membership checks and relation merge.
from .mtc_relation_selection import RelationPrepared, prepare_fold


@dataclass(frozen=True)
class RelationModel(RuleModel):
    schema_version: str = SCHEMA

    def __post_init__(self):
        if (self.schema_version != SCHEMA or self.binding.get('experiment_id') != VERSION
                or self.binding.get('scheme') != 'B_REL_TZ'
                or self.fit.get('adapter_version') != VERSION
                or self.fit.get('capacity_profile') != PROFILE
                or self.fit.get('relation_parameters', {}).get('fitted') is not False
                or self.view.get('kind') != 'EXPLICIT_RELATION_EXTENSION'
                or self.method_id not in base.METHODS.values()):
            raise ValueError('NEW_RELATION_MODEL_IDENTITY_REQUIRED')
        if self.status not in ('FITTED', 'FAILED', 'EMPTY_MODEL') or self.constant is not None:
            raise ValueError('INVALID_RELATION_MODEL_STATUS')
        ids = [a.atom_id for a in self.atoms]
        if len(ids) != len(set(ids)) or len({c.id for c in self.clauses}) != len(self.clauses):
            raise ValueError('DUPLICATE_RELATION_MODEL_COMPONENT')
        if set(ids) != {lit.atom_id for c in self.clauses for lit in c.literals}:
            raise ValueError('MODEL_ATOMS_MUST_EQUAL_SELECTED_DEPENDENCIES')
        if (self.status == 'FITTED') != bool(self.clauses):
            raise ValueError('EMPTY_OR_FAILED_IS_NOT_A_FITTED_DETECTOR')
        limits = apply_capacity(SimpleNamespace(search=contract('learning_search_space'),
                                                grammar=contract('candidate_grammar')))
        if any(len(c.literals) != 1 for c in self.clauses) or not compatible(
                self.clauses, self.atoms, 'GREEDY_OR', limits.grammar, limits.search):
            raise ValueError('RELATION_MODEL_EXCEEDS_UNCHANGED_CAP8_LIMITS')
        semantic_catalog(self.atoms)
        object.__setattr__(self, '_frozen_content', self._content())

    @property
    def model_id(self):
        return 'mtc-rel-tz-' + super().model_id.removeprefix('r03-')


def _finish(prepared, problem, access, stage, selected, outcome, trace, started,
            failure=None, initialization=None):
    common = prepared.common
    status = 'FAILED' if outcome['status'].startswith('FAILED') else 'FITTED' if selected else 'EMPTY_MODEL'
    if status == 'FAILED':
        selected = ()
    score = json_score(problem.score(selected))
    fit = dict(outcome, adapter_version=VERSION, train_ids=list(common.ids),
        mtc_train_ids=list(common.mtc_train_ids), clean_budget_count=problem.budget,
        clean_denominator=len(problem.clean), mtc_budget_count=problem.mtc_budget,
        mtc_denominator=len(problem.mtc_ids), budget_rounding='FLOOR_SEPARATELY',
        training_result=deepcopy(score), capacity_profile=deepcopy(PROFILE),
        relation_parameters=deepcopy(prepared.relation_parameters),
        relation_atom_ids=[a.atom_id for a in prepared.relation_atoms],
        threshold_refit=False, actual_fit_invocations=1,
        freeze_time=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.monotonic()-started, failure=failure,
        initialization=initialization, set_constraint_rejection_counts=dict(problem.constraint_rejections))
    selected_ids = {lit.atom_id for c in selected for lit in c.literals}
    model = RelationModel(base.METHODS[stage], status, tuple(selected),
        tuple(a for a in common.atoms if a.atom_id in selected_ids),
        {'experiment_id': VERSION, 'scheme': 'B_REL_TZ', 'fold_id': common.job['fold_id'],
         'stage': stage, 'operating_point': 'OP05'},
        {'kind': 'EXPLICIT_RELATION_EXTENSION', 'view_id': VERSION + ':' + stage,
         'input_atom_ids': sorted(a.atom_id for a in common.atoms),
         'old_base_representation': 'WEBGL50', 'no_cross_surface_bonus': True},
        fit, encoder=deepcopy(common.encoder))
    training = {'model_id': model.model_id, 'scheme': 'B_REL_TZ', 'stage': stage,
        'fold_id': common.job['fold_id'], 'train_ids': list(common.ids),
        'mtc_train_ids': list(common.mtc_train_ids), 'trace': trace,
        'candidate_statistics': base._candidate_statistics(problem, selected),
        'whole_set_result': score, 'encoded_atoms': [asdict(a) for a in common.atoms],
        'semantic_catalog': semantic_catalog(common.atoms),
        'access_operations': deepcopy(access.operations), 'failure': failure,
        'initialization': initialization,
        'statistics_scope': 'CONTROLLED_OWN_TRAIN_AND_MTC_DISCOVERY_ONLY'}
    return model, training


def fit(prepared, *, stage, initial_model=None, initial_training=None):
    if type(prepared) is not RelationPrepared or stage not in base.METHODS:
        raise TypeError('EXPLICIT_RELATION_PREPARATION_AND_STAGE_REQUIRED')
    common = prepared.common
    initialization = None
    if stage == 'RETENTION':
        if (type(initial_model) is not RelationModel
                or initial_model.binding['fold_id'] != common.job['fold_id']
                or initial_model.binding['stage'] != 'SPARSE'
                or initial_model.fit['train_ids'] != list(common.ids)
                or initial_model.fit['mtc_train_ids'] != list(common.mtc_train_ids)
                or initial_model.encoder != common.encoder
                or initial_model.fit['relation_parameters'] != prepared.relation_parameters
                or initial_training.get('model_id') != initial_model.model_id):
            raise PermissionError('OWN_NEW_B_REL_TZ_GREEDY_INITIALIZATION_REQUIRED')
        initialization = {'model_id': initial_model.model_id, 'threshold_refit': False,
                          'kind': 'OWN_NEW_B_REL_TZ_GREEDY'}
    started = time.monotonic()
    deadline = started + 60
    problem, access = base._problem(common, 'B', deadline)
    selected, trace, failure = (), [], None
    try:
        if stage == 'SPARSE':
            access.assert_fit(access.batch(), 'pruning')
            selected, outcome, trace = greedy_semantic(problem, deadline)
        elif initial_model.status == 'FAILED':
            raise ValueError('GREEDY_INITIALIZATION_FAILED')
        else:
            selected, outcome, trace = retain_semantic(problem, initial_model.clauses, deadline)
        if selected and not problem.score(selected)['feasible']:
            raise ValueError('FINAL_OR_SET_FAILED_UNCHANGED_B_REQUIREMENTS')
    except Exception as exc:
        failure = {'type': type(exc).__name__, 'reason': str(exc)}
        outcome = {'status': 'FAILED_FIT', 'reason': str(exc), 'infeasibility_proved': False}
    return _finish(prepared, problem, access, stage, selected, outcome, trace, started,
                   failure, initialization)


def predict_current(model, sample_id, common_raw):
    if type(model) is not RelationModel:
        raise TypeError('NEW_B_REL_TZ_MODEL_REQUIRED')
    if model.status in ('EMPTY_MODEL', 'FAILED'):
        return predict(model, sample_id, {})
    try:
        names = [a.atom_id for a in model.atoms]
        features = transform_numeric(common_raw, model.encoder, names)
        for name in set(names) & set(model.fit['relation_atom_ids']):
            features[name] = deepcopy(common_raw[name])
        return predict(model, sample_id, {'features': features, 'view_id': model.view['view_id']})
    except (KeyError, ValueError, TypeError) as exc:
        result = predict(model, sample_id, {})
        result.update(decision='FAILED', failure_reason='RELATION_INPUT:' + str(exc))
        return result


def save_model(model, path):
    if type(model) is not RelationModel:
        raise TypeError('NEW_RELATION_MODEL_REQUIRED')
    with Path(path).open('x') as stream:
        json.dump(model.to_dict(), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def load_model(path):
    return RelationModel.from_dict(json.loads(Path(path).read_text()))
