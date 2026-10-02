"""Independent MTC normal constraints over the existing semantic OR selectors.

Controlled triplets alone fit thresholds, attack support, weights and diversity.
MTC discovery observations remain a separate normal population, never triplets.
The two prespecified schemes share one controlled-training encoder per fold.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fractions import Fraction
import json
import math
from pathlib import Path
import time

from .rule_learning.baselines import transform_numeric
from .rule_learning.models import RuleModel as BaseRuleModel
from .rule_learning.predictor import clause_state, predict
from .rule_learning.selector import compatible, json_score
from .rule_learning_v2.adapter import TrainAccess, V2Problem, approved_atoms, encode_train
from .rule_learning_v2.semantic_selection import greedy_semantic, retain_semantic, semantic_catalog
from .rule_semantics_webgl1_cap8 import apply_capacity, PROFILE

VERSION = 'mtc-constrained-reselection-v1'
SCHEMA = 'mtc-constrained-rule-model-v1'
SCHEMES = ('A', 'B')
SCHEME_NAMES = {'A': 'FULL_WEBGL50_DUAL_NORMAL', 'B': 'HISTORICAL_MTC_COMPATIBLE'}
METHODS = {'SPARSE': 'GREEDY_SEMANTIC_V2', 'RETENTION': 'R_KEEP_SWAP_V2'}
ALPHA = Fraction(1, 20)
MTC_COVERAGE = Fraction(9, 10)


@dataclass(frozen=True)
class PreparedFold:
    job: dict
    raw_rows: dict
    metadata: dict
    controlled_rows: dict
    mtc_rows: dict
    mtc_metadata: dict
    mtc_train_ids: tuple
    mtc_evaluation_ids: tuple
    atoms: tuple
    encoder: dict
    preparation: dict

    @property
    def ids(self):
        return tuple(self.job['train_ids'])


def _normal_members(rows, metadata, train_ids, evaluation_ids):
    ids = tuple(train_ids)
    if (not ids or len(ids) != len(set(ids)) or set(rows) != set(ids)
            or set(metadata) != set(ids) or set(ids) & set(evaluation_ids)):
        raise PermissionError('EXACT_MTC_DISCOVERY_TRAIN_MEMBERS_ONLY')
    for m in metadata.values():
        if m.get('split') != 'discovery' or m.get('normal_basis') is not True:
            raise PermissionError('MTC_TRAIN_REQUIRES_DISCOVERY_NORMAL_BASIS')
        if any(k in m for k in ('phase', 'triplet_id', 'supervised_label', 'config_id')):
            raise PermissionError('MTC_MUST_REMAIN_INDEPENDENT_NORMAL_NOT_TRIPLET')
    return ids


def prepare_fold(job, controlled_raw_rows, controlled_metadata, definitions,
                 mtc_raw_rows, mtc_metadata, *, mtc_train_ids, mtc_evaluation_ids=()):
    """Fit the unchanged quantiles once, without receiving any evaluation rows."""
    ids = _normal_members(mtc_raw_rows, mtc_metadata, mtc_train_ids, mtc_evaluation_ids)
    if set(ids) & (set(job['train_ids']) | set(job['outer_test_ids'])):
        raise PermissionError('CONTROLLED_AND_MTC_POPULATIONS_MUST_BE_DISJOINT')
    names = {a.atom_id for a in approved_atoms(definitions)}
    if any(set(r) != names for r in (*controlled_raw_rows.values(), *mtc_raw_rows.values())):
        raise ValueError('EXACT_COMMON_CANDIDATE_SEMANTICS_REQUIRED')
    access = TrainAccess(job, controlled_raw_rows, controlled_metadata)
    rows, atoms, encoder, _ = encode_train(access, definitions, 'S_FLAT')
    semantic_catalog(atoms)  # Reject undeclared semantics before either fit.
    mtc = {sid: transform_numeric(mtc_raw_rows[sid], encoder) for sid in ids}
    preparation = {'adapter_version': VERSION, 'threshold_fit_calls': 1,
                   'threshold_fit_calls_unit': 'CONTROLLED_TRAIN_ENCODER_INVOCATION',
                   'numeric_fit_member_ids': list(access.ids),
                   'base_candidate_count': len(names),
                   'mtc_used_for_numeric_thresholds': False,
                   'evaluation_rows_received': False,
                   'access_operations': deepcopy(access.operations)}
    return PreparedFold(deepcopy(job), deepcopy(controlled_raw_rows), deepcopy(controlled_metadata),
                        rows, mtc, deepcopy(mtc_metadata), ids, tuple(mtc_evaluation_ids),
                        atoms, encoder, preparation)


def _counts(states):
    counts = Counter(s if s is not None else 'FAILED' for s in states)
    return {'expected': len(states), 'defined': counts['T'] + counts['F'],
            **{s: counts[s] for s in ('T', 'F', 'U', 'FAILED', 'EMPTY_MODEL')}}


class DualNormalProblem(V2Problem):
    """V2 controlled support/score plus a separate MTC whole-OR constraint."""
    def __init__(self, access, rows, atoms, deadline, mtc_rows, mtc_ids, scheme):
        if scheme not in SCHEMES:
            raise ValueError('ONLY_PRESPECIFIED_A_OR_B')
        if not mtc_ids or set(mtc_rows) != set(mtc_ids):
            raise ValueError('EXACT_NONEMPTY_MTC_ROWS_REQUIRED')
        self.scheme, self.mtc_ids = scheme, tuple(mtc_ids)
        self.mtc_rows = tuple(mtc_rows[i] for i in self.mtc_ids)
        if any(set(r) != {a.atom_id for a in atoms} for r in self.mtc_rows):
            raise ValueError('MTC_ENCODED_CANDIDATE_SET_MISMATCH')
        self.mtc_budget = math.floor(ALPHA * len(self.mtc_ids))
        self.mtc_states, self._mtc_masks, self._score_cache = {}, {}, {}
        self.constraint_rejections = Counter()
        super().__init__(access, rows, atoms, deadline)
        apply_capacity(self)
        self._mtc_mask_all = (1 << len(self.mtc_ids)) - 1

    def _pool(self):
        controlled_candidates = super()._pool()
        by_id = {c.id: c for c in controlled_candidates}
        # Every literal, including unsupported ones, retains separate MTC stats.
        from .rule_learning.models import Clause, Literal
        all_clauses = {Literal(a.atom_id, p).id: Clause((Literal(a.atom_id, p),))
                       for a in self.atoms for p in self.grammar['literal']['polarity_choices']}
        admitted = []
        for item in self.manifest:
            clause = all_clauses[item['clause_id']]
            states = []
            for row in self.mtc_rows:
                try:
                    states.append(clause_state(clause, row))
                except (ValueError, KeyError, TypeError):
                    states.append(None)
            self.mtc_states[clause.id] = states
            self._mtc_masks[clause.id] = {
                s: sum(1 << i for i, value in enumerate(states) if value == s)
                for s in ('T', 'F', 'U', None)}
            counts = _counts(states)
            ratio = Fraction(counts['defined'], len(states))
            item.update(mtc_normal=counts, mtc_evaluable_ratio=float(ratio))
            if counts['FAILED']:
                item['reasons'].append('MTC_TRAIN_EXECUTION_FAILURE')
            if self.scheme == 'B' and ratio < MTC_COVERAGE:
                item['reasons'].append('MTC_CANDIDATE_EVALUABILITY_BELOW_90_PERCENT')
            item['eligible'] = not item['reasons']
            if item['eligible']:
                admitted.append(by_id[clause.id])
        return tuple(admitted)

    def score(self, clauses):
        clauses = tuple(sorted(clauses, key=lambda c: c.id))
        key = tuple(c.id for c in clauses)
        if key in self._score_cache:
            return self._score_cache[key]
        result = super().score(clauses)
        if clauses:
            true, false, failed = 0, self._mtc_mask_all, 0
            for c in clauses:
                masks = self._mtc_masks[c.id]
                true |= masks['T']
                false &= masks['F']
                failed |= masks[None]
            true &= ~failed
            false &= ~failed
            counts = {'expected': len(self.mtc_ids), 'T': true.bit_count(), 'F': false.bit_count(),
                      'FAILED': failed.bit_count(), 'EMPTY_MODEL': 0}
            counts['defined'] = counts['T'] + counts['F']
            counts['U'] = len(self.mtc_ids) - counts['defined'] - counts['FAILED']
        else:
            counts = _counts(['EMPTY_MODEL'] * len(self.mtc_ids))
        coverage = Fraction(counts['defined'], len(self.mtc_ids))
        reasons = []
        if result['clean_alarms'] > self.budget:
            reasons.append('CONTROLLED_SET_NORMAL_BUDGET')
        if counts['T'] > self.mtc_budget:
            reasons.append('MTC_SET_NORMAL_BUDGET')
        if counts['FAILED']:
            reasons.append('MTC_SET_EXECUTION_FAILURE')
        normal_ok = counts['T'] <= self.mtc_budget and not counts['FAILED']
        coverage_ok = self.scheme != 'B' or coverage >= MTC_COVERAGE
        if self.scheme == 'B' and not coverage_ok:
            reasons.append('MTC_SET_DECISION_COVERAGE_BELOW_90_PERCENT')
        # Intermediate GREEDY prefixes may regain coverage by adding a T signal.
        # Only the final feasible model must meet B's 90%; both budgets apply at
        # every addition, prune, retention addition and semantic swap.
        result.update(mtc_alarms=counts['T'], mtc_budget=self.mtc_budget,
                      mtc_denominator=len(self.mtc_ids), mtc_coverage=coverage,
                      mtc_state_counts=counts, constraint_reasons=reasons,
                      partial_feasible=result['partial_feasible'] and normal_ok,
                      feasible=result['feasible'] and normal_ok and coverage_ok)
        self.constraint_rejections.update(reasons)
        self._score_cache[key] = result
        return result


@dataclass(frozen=True)
class ReselectionModel(BaseRuleModel):
    """New experiment/schema identity with the existing CAP8 structural limits."""
    schema_version: str = SCHEMA

    def __post_init__(self):
        if (self.schema_version != SCHEMA or self.binding.get('experiment_id') != VERSION
                or self.binding.get('scheme') not in SCHEMES
                or self.method_id not in METHODS.values()
                or self.fit.get('adapter_version') != VERSION
                or self.view.get('kind') != 'MTC_CONSTRAINED_COMMON_CANDIDATES'
                or self.fit.get('capacity_profile') != PROFILE):
            raise ValueError('NEW_MTC_RESELECTION_MODEL_IDENTITY_REQUIRED')
        if self.status not in ('FITTED', 'EMPTY_MODEL', 'FAILED') or self.constant is not None:
            raise ValueError('INVALID_RESELECTION_STATUS')
        ids = [a.atom_id for a in self.atoms]
        if len(ids) != len(set(ids)) or len({c.id for c in self.clauses}) != len(self.clauses):
            raise ValueError('DUPLICATE_MODEL_ATOM_OR_CLAUSE')
        if set(ids) != {l.atom_id for c in self.clauses for l in c.literals}:
            raise ValueError('MODEL_ATOMS_MUST_EQUAL_SELECTED_DEPENDENCIES')
        if self.status != 'FITTED' and self.clauses:
            raise ValueError('NONEXECUTABLE_MODEL_HAS_RULES')
        if self.status == 'FITTED' and not self.clauses:
            raise ValueError('EMPTY_IS_NOT_ALWAYS_NO_ALERT')
        from .rule_learning.contracts import contract
        from types import SimpleNamespace
        limits = apply_capacity(SimpleNamespace(search=contract('learning_search_space'),
                                               grammar=contract('candidate_grammar')))
        if any(len(c.literals) != 1 for c in self.clauses) or not compatible(
                self.clauses, self.atoms, 'GREEDY_OR', limits.grammar, limits.search):
            raise ValueError('FITTED_MODEL_EXCEEDS_REGISTERED_CAPACITY')
        object.__setattr__(self, '_frozen_content', self._content())

    @property
    def model_id(self):
        return 'mtc-reselection-' + super().model_id.removeprefix('r03-')


def _problem(prepared, scheme, deadline):
    if type(prepared) is not PreparedFold:
        raise TypeError('PREPARED_CONTROLLED_ONLY_FOLD_REQUIRED')
    _normal_members(prepared.mtc_rows, prepared.mtc_metadata, prepared.mtc_train_ids,
                    prepared.mtc_evaluation_ids)
    access = TrainAccess(prepared.job, prepared.raw_rows, prepared.metadata)
    if prepared.encoder.get('train_ids') != list(access.ids):
        raise PermissionError('ENCODER_MUST_MATCH_EXACT_CONTROLLED_TRAIN')
    return DualNormalProblem(access, prepared.controlled_rows, prepared.atoms, deadline,
                             prepared.mtc_rows, prepared.mtc_train_ids, scheme), access


def _compact_support(record):
    # Exact membership is saved once at training-file level; keep the actual
    # sufficient support counts here without repeating hundreds of IDs per literal.
    return {k: deepcopy(v) for k, v in record.items()
            if k not in ('train_ids', 'complete_triplet_ids', 'true_attack_triplet_ids')}


def _candidate_statistics(problem, selected):
    selected_ids = {c.id for c in selected}
    atoms = {a.atom_id: a for a in problem.atoms}
    rows = []
    for item in problem.manifest:
        cid = item['clause_id']
        aid, polarity = cid.rsplit(':', 1)
        states = problem.states[cid]
        clean = _counts([states[i] for i in problem.clean])
        attack = _counts([states[i] for i in problem.phase_indices['attack']])
        mtc = deepcopy(item['mtc_normal'])
        configs = sorted({problem.meta[problem.ids[i]]['config_id']
                          for i in problem.phase_indices['attack'] if states[i] == 'T'})
        budgets = []
        if clean['T'] > problem.budget:
            budgets.append('CONTROLLED_SET_NORMAL_BUDGET')
        if mtc['T'] > problem.mtc_budget:
            budgets.append('MTC_SET_NORMAL_BUDGET')
        reasons = (['SELECTED'] if cid in selected_ids else item['reasons'] + budgets
                   or ['NOT_CHOSEN_BY_PRESPECIFIED_HEURISTIC_NO_IMPOSSIBILITY_CLAIM'])
        rows.append({'clause_id': cid, 'atom_id': aid, 'polarity': polarity,
                     'provenance': deepcopy(atoms[aid].provenance),
                     'controlled_attack': attack, 'controlled_clean': clean, 'mtc_normal': mtc,
                     'attack_configurations': len(configs), 'triggered_config_ids': configs,
                     'controlled_support': _compact_support(problem.support[cid]),
                     'mtc_evaluable_ratio': item['mtc_evaluable_ratio'],
                     'admitted': item['eligible'], 'admission_reasons': list(item['reasons']),
                     'singleton_budget_reasons': budgets, 'selected': cid in selected_ids,
                     'selection_reasons': reasons})
    return rows


def _finish(prepared, problem, access, scheme, stage, selected, outcome, trace, started,
            failure=None, initialization=None):
    status = 'FAILED' if outcome['status'].startswith('FAILED') else 'FITTED' if selected else 'EMPTY_MODEL'
    if status == 'FAILED':
        selected = ()
    result = json_score(problem.score(selected))
    binding = {'experiment_id': VERSION, 'study_version': VERSION, 'fold_id': prepared.job['fold_id'],
               'scheme': scheme, 'scheme_name': SCHEME_NAMES[scheme], 'stage': stage,
               'method_id': METHODS[stage], 'operating_point': 'OP05',
               'capacity_profile': PROFILE['profile_id']}
    fit = dict(outcome, adapter_version=VERSION, train_ids=list(prepared.ids),
               mtc_train_ids=list(prepared.mtc_train_ids),
               train_expected_n=len(prepared.ids), train_consumed_n=len(prepared.controlled_rows),
               mtc_expected_n=len(prepared.mtc_train_ids), mtc_consumed_n=len(prepared.mtc_rows),
               clean_budget_count=problem.budget, clean_denominator=len(problem.clean),
               mtc_budget_count=problem.mtc_budget, mtc_denominator=len(problem.mtc_ids),
               budget_rounding='FLOOR_SEPARATELY', alpha=0.05,
               training_result=deepcopy(result), capacity_profile=deepcopy(PROFILE),
               actual_fit_invocations=1, actual_sparse_fit_invocations=int(stage == 'SPARSE'),
               actual_retention_invocations=int(stage == 'RETENTION'), threshold_fit_calls=0,
               encoder_prepared_once_on_controlled_train=True,
               support_scope='CONTROLLED_COMPLETE_TRIPLETS_ONLY_MTC_NOT_IN_SUPPORT',
               freeze_time=datetime.now(timezone.utc).isoformat(),
               elapsed_seconds=time.monotonic() - started, failure=deepcopy(failure),
               initialization=deepcopy(initialization),
               set_constraint_rejection_counts=dict(problem.constraint_rejections))
    view = {'view_id': VERSION + ':' + scheme + ':' + stage,
            'kind': 'MTC_CONSTRAINED_COMMON_CANDIDATES', 'base_representation': 'WEBGL50',
            'input_atom_ids': sorted(a.atom_id for a in prepared.atoms),
            'source_modes_are_reading_contract_only': True}
    selected_atoms = {l.atom_id for c in selected for l in c.literals}
    model = ReselectionModel(METHODS[stage], status, tuple(selected),
                             tuple(a for a in prepared.atoms if a.atom_id in selected_atoms),
                             binding, view, fit, encoder=deepcopy(prepared.encoder))
    training = {'schema_version': 'mtc-constrained-training-v1', 'adapter_version': VERSION,
                'scheme': scheme, 'stage': stage, 'fold_id': prepared.job['fold_id'],
                'model_id': model.model_id, 'train_ids': list(prepared.ids),
                'mtc_train_ids': list(prepared.mtc_train_ids),
                'trace': trace, 'candidate_statistics': _candidate_statistics(problem, selected),
                'whole_set_result': result, 'encoded_atoms': [asdict(a) for a in prepared.atoms],
                'semantic_catalog': semantic_catalog(prepared.atoms),
                'access_operations': deepcopy(access.operations), 'failure': failure,
                'statistics_scope': 'CONTROLLED_OWN_TRAIN_AND_MTC_DISCOVERY_ONLY',
                'initialization': initialization}
    return model, training


def fit_sparse(prepared, *, scheme):
    started = time.monotonic()
    deadline = started + 60
    problem, access = _problem(prepared, scheme, deadline)
    access.assert_fit(access.batch(), 'pruning')
    selected, trace, failure = (), [], None
    try:
        selected, outcome, trace = greedy_semantic(problem, deadline)
        if selected and not problem.score(selected)['feasible']:
            raise ValueError('FINAL_DUAL_NORMAL_CONSTRAINT_FAILURE')
    except Exception as exc:
        failure = {'stage': 'SPARSE', 'exception_type': type(exc).__name__, 'reason': str(exc)}
        outcome = {'status': 'FAILED_FIT', 'reason': str(exc), 'infeasibility_proved': False}
    return _finish(prepared, problem, access, scheme, 'SPARSE', selected, outcome, trace, started, failure)


def fit_retention(prepared, *, scheme, initial_model, initial_training):
    if type(initial_model) is not ReselectionModel:
        raise TypeError('NEW_OWN_SCHEME_GREEDY_INITIALIZATION_REQUIRED')
    if (initial_model.binding.get('scheme') != scheme
            or initial_model.binding.get('fold_id') != prepared.job['fold_id']
            or initial_model.method_id != METHODS['SPARSE']
            or initial_model.status not in ('FITTED', 'EMPTY_MODEL')
            or initial_model.fit['train_ids'] != list(prepared.ids)
            or initial_model.fit['mtc_train_ids'] != list(prepared.mtc_train_ids)
            or initial_model.encoder != prepared.encoder
            or initial_training.get('model_id') != initial_model.model_id
            or initial_training.get('stage') != 'SPARSE'):
        raise PermissionError('EXACT_OWN_SCHEME_FOLD_TRAIN_GREEDY_INITIALIZATION_REQUIRED')
    started = time.monotonic()
    deadline = started + 60
    problem, access = _problem(prepared, scheme, deadline)
    selected, trace, failure = (), [], None
    initialization = {'model_id': initial_model.model_id, 'scheme': scheme,
                      'kind': 'OWN_NEW_GREEDY_ONLY', 'threshold_refit': False,
                      'old_CAP8_used_for_initialization': False}
    try:
        selected, outcome, trace = retain_semantic(problem, initial_model.clauses, deadline)
        if selected and not problem.score(selected)['feasible']:
            raise ValueError('FINAL_DUAL_NORMAL_RETENTION_CONSTRAINT_FAILURE')
    except Exception as exc:
        failure = {'stage': 'RETENTION', 'exception_type': type(exc).__name__, 'reason': str(exc)}
        outcome = {'status': 'FAILED_FIT', 'reason': str(exc), 'infeasibility_proved': False}
    return _finish(prepared, problem, access, scheme, 'RETENTION', selected, outcome, trace, started,
                   failure, initialization)


def predict_current(model, opaque_id, common_raw):
    """Inference on an explicit common-candidate row, with the saved encoder."""
    if type(model) is not ReselectionModel:
        raise TypeError('NEW_MTC_RESELECTION_MODEL_REQUIRED')
    try:
        if model.status in ('EMPTY_MODEL', 'FAILED'):
            return predict(model, opaque_id, {})
        features = transform_numeric(common_raw, model.encoder, [a.atom_id for a in model.atoms])
        return predict(model, opaque_id, {'features': features, 'view_id': model.view['view_id']})
    except (ValueError, KeyError, TypeError) as exc:
        result = predict(model, opaque_id, {})
        result.update(decision='FAILED', failure_reason='MTC_COMMON_ENCODER:' + str(exc))
        return result


def save_model(model, path):
    if type(model) is not ReselectionModel:
        raise TypeError('NEW_MTC_RESELECTION_MODEL_REQUIRED')
    with Path(path).open('x') as stream:
        json.dump(model.to_dict(), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def load_model(path):
    return ReselectionModel.from_dict(json.loads(Path(path).read_text()))
