"""V2 identity + train-only adapter over unchanged V1 mathematical primitives.

No V1 capability issuance, monkeypatch, synthetic flag on real rows, or old model
mutation. Only TrainProblem's initialization is adapted; its candidate/support/
score methods and greedy search are inherited unchanged.
"""
import copy
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from hybridguard_agent.research.rule_learning.baselines import project_core, transform_numeric
from hybridguard_agent.research.rule_learning.contracts import PHASES, contract, ledger
from hybridguard_agent.research.rule_learning.fold_data import FoldBatch, TrainQuantiles, FIT_OPERATIONS
from hybridguard_agent.research.rule_learning.models import Atom, RuleModel
from hybridguard_agent.research.rule_learning.predictor import predict
from hybridguard_agent.research.rule_learning.selector import TrainProblem, greedy, json_score
from .common import VERSION, SURFACES, ROLE, digest, read, write, stamp


def atom_from_dict(a):
    return Atom(**dict(a, surfaces=tuple(a['surfaces']), sources=tuple(a['sources']), aliases=tuple(a['aliases'])))


def approved_atoms(defs):
    by_id = {a['atom_id']: atom_from_dict(a) for a in defs['atoms']}
    result = []
    for surface in SURFACES:
        names = defs['single_surface_allowlists'][surface]
        if len(names) != len(set(names)):
            raise ValueError('DUPLICATE_ALLOWLIST_ATOM')
        for name in names:
            a = by_id[name]
            if a.surfaces != (surface,):
                raise ValueError('SINGLE_SURFACE_ALLOWLIST_MISMATCH')
            result.append(a)
    if len({a.atom_id for a in result}) != len(result):
        raise ValueError('DUPLICATE_FLAT_ATOM')
    return tuple(result)


def raw_projection(rows, defs, representation):
    if representation not in ('S_FLAT', 'J0'):
        raise PermissionError('V2_A_REPRESENTATION_NOT_AUTHORIZED')
    names = [a.atom_id for a in approved_atoms(defs)]
    if representation == 'J0':
        names += [c['atom_id'] for c in ledger() if c['candidate_use']['core']
                  and c['candidate_use']['selectable_on_App177']]
    return {i: {n: copy.deepcopy(row[n]) for n in names} for i, row in rows.items()}


class TrainAccess:
    """Contains only the exact own train members and sidecar; no test store."""
    def __init__(self, job, rows, metadata):
        self.job = copy.deepcopy(job)
        self.fold_id = job['fold_id']
        self.ids = tuple(job['train_ids'])
        if (len(self.ids) != len(set(self.ids)) or set(rows) != set(self.ids)
                or set(metadata) != set(self.ids) or set(self.ids) & set(job['outer_test_ids'])):
            raise PermissionError('EXACT_TRAIN_MEMBERS_ONLY')
        if any(type(m['supervised_label']) is not int or m['supervised_label'] not in (0, 1)
               for m in metadata.values()):
            raise PermissionError('DESCRIPTIVE_NOT_AUTHORIZED_FOR_FIT')
        self.rows, self.metadata = copy.deepcopy(rows), copy.deepcopy(metadata)
        self.operations = []

    def batch(self):
        return FoldBatch(self.fold_id, 'train', self.ids, tuple(copy.deepcopy(self.rows[i]) for i in self.ids))

    def assert_fit(self, batch, operation):
        if operation not in FIT_OPERATIONS or batch != self.batch():
            raise PermissionError('FIT_REQUIRES_EXACT_V2_TRAIN_BATCH')
        self.operations.append({'operation': operation, 'ids': list(batch.ids), 'utc': stamp()})


def encode_train(access, defs, representation):
    batch = access.batch()
    access.assert_fit(batch, 'numeric_thresholds')
    flat = approved_atoms(defs)
    fixed = [a for a in flat if not a.atom_id.startswith('UNFITTED_CONTROL:')]
    encoder = {'version': VERSION, 'semantics': 'V1_TRAIN_QUANTILES_UNCHANGED',
               'fold_id': access.fold_id, 'train_ids': list(batch.ids),
               'fixed_atoms': [a.atom_id for a in fixed], 'numeric': {}}
    atoms = list(fixed)
    for a in flat:
        if not a.atom_id.startswith('UNFITTED_CONTROL:'):
            continue
        q = TrainQuantiles(a.atom_id).fit(access, batch)
        names = ['CONTROL:' + a.atom_id.removeprefix('UNFITTED_CONTROL:') + ':LE:' + repr(t)
                 for t in q.thresholds]
        encoder['numeric'][a.atom_id] = {
            'thresholds': list(q.thresholds), 'atom_ids': names,
            'status': 'FROZEN' if names else 'NO_OBSERVED_TRAIN_VALUES',
            'train_observed_n': sum(r[a.atom_id]['available'] for r in batch.records),
            'train_expected_n': len(batch.ids), 'surface': a.surfaces[0]}
        atoms.extend(Atom(n, a.family, a.surfaces, a.sources, (n,), 'CONTROL_LE',
                          {'field': a.atom_id.removeprefix('UNFITTED_CONTROL:'), 'threshold': t})
                     for n, t in zip(names, q.thresholds, strict=True))
    for surface in SURFACES:
        if 2 * sum(a.surfaces == (surface,) for a in atoms) > contract('candidate_grammar')['new_encoder']['max_literals_per_surface']:
            raise ValueError('SINGLE_SURFACE_LITERAL_CAP_NO_TRUNCATION')
    rows = {i: transform_numeric(r, encoder) for i, r in access.rows.items()}
    if representation == 'J0':
        core, core_atoms = project_core(access.rows, ledger(), 'SRC-111')
        if {a.atom_id for a in atoms} & {a.atom_id for a in core_atoms}:
            raise ValueError('FLAT_CORE_ID_OVERLAP')
        atoms.extend(core_atoms)
        for i in rows:
            rows[i].update(core[i])
    view = {'view_id': 'V2-A:' + representation, 'kind': 'V2_UNIFIED',
            'representation': representation, 'input_atom_ids': sorted(a.atom_id for a in atoms),
            'cross_atoms_forced': 0, 'source_alias_support_count_once': True}
    return rows, tuple(atoms), encoder, view


class V2Problem(TrainProblem):
    def __init__(self, access, rows, atoms, deadline):
        access.assert_fit(access.batch(), 'combination_selection')
        self.search, self.grammar = contract('learning_search_space'), contract('candidate_grammar')
        self.method, self.operating_point, self.deadline = 'GREEDY_OR', 'OP05', deadline
        self.access, self.ids = access, access.ids
        self.rows = tuple(rows[i] for i in self.ids)
        self.atoms = tuple(sorted(atoms, key=lambda a: a.atom_id))
        if any(set(r) != {a.atom_id for a in atoms} for r in self.rows):
            raise ValueError('ENCODED_CANDIDATE_SET_MISMATCH')
        self.meta = copy.deepcopy(access.metadata)
        self.phase_indices = {p: [n for n, i in enumerate(self.ids) if self.meta[i]['phase'] == p] for p in PHASES}
        self.triplets = defaultdict(dict)
        for n, i in enumerate(self.ids):
            m = self.meta[i]
            if m['phase'] not in PHASES or m['supervised_label'] != int(m['phase'] == 'attack'):
                raise ValueError('LABEL_ADMITTED_PHASE_MISMATCH')
            t = self.triplets[m['bundle_id'], m['triplet_id']]
            if m['phase'] in t:
                raise ValueError('DUPLICATE_TRIPLET_PHASE')
            t[m['phase']] = n
        if not self.triplets or any(set(t) != set(PHASES) for t in self.triplets.values()):
            raise ValueError('TRAIN_REQUIRES_COMPLETE_ADMITTED_TRIPLETS')
        for t in self.triplets.values():
            if len({(self.meta[self.ids[n]]['config_id'], self.meta[self.ids[n]]['environment_group_id']) for n in t.values()}) != 1:
                raise ValueError('TRIPLET_GROUP_MISMATCH')
        self.clean = self.phase_indices['clean_pre'] + self.phase_indices['clean_post']
        alpha = next(p['alpha'] for p in self.search['operating_points'] if p['id'] == 'OP05')
        self.budget = math.floor(Fraction(str(alpha)) * len(self.clean))
        cfgs = defaultdict(lambda: defaultdict(list))
        for n in self.phase_indices['attack']:
            m = self.meta[self.ids[n]]
            cfgs[m['config_id']][m['environment_group_id']].append(n)
        self.weights = {n: Fraction(1, len(cfgs) * len(envs) * len(ns))
                        for envs in cfgs.values() for ns in envs.values() for n in ns}
        self.penalty = Fraction(str(self.search['objective']['lambda']))
        self.support, self.states, self.manifest = {}, {}, []
        self.candidates = self._pool()


@dataclass(frozen=True)
class V2Model:
    """V2 model envelope; the embedded structure uses the existing rule validator."""
    engine: RuleModel

    def __post_init__(self):
        if self.engine.binding.get('study_version') != 'discriminative-rule-learning-v2-20260925':
            raise ValueError('V2_IDENTITY_REQUIRED')

    def __getattr__(self, name):
        return getattr(self.engine, name)

    @property
    def model_id(self):
        return 'v2a-' + digest(self.engine.to_dict())[:24]

    def to_dict(self):
        return {'schema_version': 'v2-a-model-v1', 'model_id': self.model_id,
                'kernel_schema': 'REUSED_R03_RULE_STRUCTURE_NOT_V1_JOB_AUTHORIZATION',
                'engine_structure': self.engine.to_dict()}

    @classmethod
    def from_dict(cls, data):
        if data['schema_version'] != 'v2-a-model-v1':
            raise ValueError('INVALID_V2_SCHEMA')
        model = cls(RuleModel.from_dict(data['engine_structure']))
        if model.model_id != data['model_id']:
            raise ValueError('V2_MODEL_CONTENT_MISMATCH')
        return model


def save_model(model, path):
    write(path, model.to_dict())


def load_model(path):
    return V2Model.from_dict(read(path))


def fit_authorized(access, defs, binding):
    """One counted V2 fit, including train encoder, support and greedy selection."""
    started = time.monotonic()
    deadline = started + contract('learning_search_space')['algorithms']['GREEDY_OR']['time_limit_seconds_per_fit']
    problem, encoder, trace, selected, atoms = None, {}, [], (), ()
    view = {'view_id': 'V2-A:' + access.job['representation'], 'kind': 'V2_UNIFIED', 'input_atom_ids': []}
    try:
        rows, atoms, encoder, view = encode_train(access, defs, access.job['representation'])
        problem = V2Problem(access, rows, atoms, deadline)
        access.assert_fit(access.batch(), 'pruning')
        if problem.candidates:
            selected, outcome, trace = greedy(problem, deadline)
        else:
            outcome = {'status': 'EMPTY_CANDIDATE_POOL', 'infeasibility_proved': False}
        if selected and not problem.score(selected)['feasible']:
            raise ValueError('INCUMBENT_FAILED_CONSTRAINT_CHECK')
    except Exception as exc:
        selected = ()
        outcome = {'status': 'FAILED_FIT', 'reason': type(exc).__name__ + ':' + str(exc),
                   'infeasibility_proved': False}
    status = 'FAILED' if outcome['status'].startswith('FAILED') else 'FITTED' if selected else 'EMPTY_MODEL'
    selected_ids = {l.atom_id for c in selected for l in c.literals}
    audit = dict(outcome, train_ids=list(access.ids), train_expected_n=len(access.ids),
                 train_consumed_n=len(access.rows), fit_scope='V2_EXACT_AUTHORIZED_TRAIN_ONLY',
                 freeze_time=stamp(), elapsed_seconds=time.monotonic() - started,
                 candidate_pool_size=len(problem.candidates) if problem else None,
                 registered_clause_count=len(problem.manifest) if problem else None)
    if problem:
        audit.update(training_result=json_score(problem.score(selected)), clean_budget_count=problem.budget,
                     clean_denominator=len(problem.clean), support_scope='COMPLETE_ADMITTED_TRAIN_TRIPLETS_ONLY')
    model = V2Model(RuleModel('GREEDY_OR', status, tuple(selected), tuple(a for a in atoms if a.atom_id in selected_ids),
                             binding, view, audit, encoder=encoder))
    return model, {'trace': trace, 'support': problem.support if problem else {},
                   'candidate_manifest': problem.manifest if problem else [],
                   'atoms': [vars(a) for a in atoms], 'access_operations': access.operations}


def transform_current(raw, model, *, selected_only=False):
    if model.status in ('FAILED', 'EMPTY_MODEL'):
        return {}
    wanted = [a.atom_id for a in model.atoms] if selected_only else None
    row = transform_numeric(raw, model.encoder, wanted)
    if model.view['representation'] == 'J0':
        core, _ = project_core({'current': raw}, ledger(), 'SRC-111')
        row.update({k: v for k, v in core['current'].items() if wanted is None or k in wanted})
    return row


def predict_current(model, opaque_id, raw):
    try:
        return predict(model, opaque_id, {'features': transform_current(raw, model, selected_only=True),
                                          'view_id': model.view['view_id']})
    except (ValueError, KeyError, TypeError) as exc:
        result = predict(model, opaque_id, {})
        result.update(decision='FAILED', failure_reason='V2_ENCODER:' + str(exc))
        return result
