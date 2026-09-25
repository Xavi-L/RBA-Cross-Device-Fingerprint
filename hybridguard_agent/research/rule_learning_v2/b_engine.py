"""Small B adapter; old candidate/score/prediction kernels remain read-only."""
import copy
import time
from dataclasses import dataclass

from hybridguard_agent.research.rule_learning.baselines import project_core, transform_numeric
from hybridguard_agent.research.rule_learning.contracts import contract, ledger
from hybridguard_agent.research.rule_learning.models import Atom, RuleModel, load_model as load_v1
from hybridguard_agent.research.rule_learning.predictor import predict
from hybridguard_agent.research.rule_learning.selector import greedy, json_score, compatible
from .adapter import V2Problem, approved_atoms, encode_train, load_model as load_a
from .common import ROOT, digest, read, write, stamp
from .retention import signal_group, retain, exclusion_reasons, GROUP_VERSION

VERSION = 'V2_B_ENGINE_V1'


@dataclass(frozen=True)
class BModel:
    engine: RuleModel

    def __post_init__(self):
        if self.engine.binding.get('phase') != 'V2-B' or self.engine.binding.get('study_version') != 'discriminative-rule-learning-v2-20260925':
            raise ValueError('EXPLICIT_V2_B_IDENTITY_REQUIRED')

    def __getattr__(self, name): return getattr(self.engine, name)

    @property
    def model_id(self): return 'v2b-' + digest(self.engine.to_dict())[:24]

    def to_dict(self):
        return {'schema_version': 'v2-b-model-v1', 'model_id': self.model_id,
                'kernel_schema': 'REUSED_RULE_STRUCTURE_NO_V1_JOB_AUTHORIZATION',
                'engine_structure': self.engine.to_dict()}


def save_model(model, path): write(path, model.to_dict())


def load_model(path):
    raw = read(path)
    if raw['schema_version'] != 'v2-b-model-v1': raise ValueError('WRONG_B_MODEL_SCHEMA')
    result = BModel(RuleModel.from_dict(raw['engine_structure']))
    if result.model_id != raw['model_id']: raise ValueError('B_MODEL_CONTENT_MISMATCH')
    return result


def load_initial(path):
    schema = read(path)['schema_version']
    return {'r03-rule-model-v1': load_v1, 'v2-a-model-v1': load_a,
            'v2-b-model-v1': load_model}[schema](path)


def selected_definitions(defs, base):
    d = copy.deepcopy(defs)
    if base == 'W0':
        d['single_surface_allowlists']['native84'] = []
        d['single_surface_allowlists']['host26'] = []
    elif base not in ('S_FLAT', 'J0', 'C0'):
        raise ValueError('UNREGISTERED_BASE_REPRESENTATION')
    return d


def project_inputs(raw, defs, base):
    names = [] if base == 'C0' else [a.atom_id for a in approved_atoms(selected_definitions(defs, base))]
    if base in ('C0', 'J0'):
        names += [c['atom_id'] for c in ledger() if c['candidate_use']['core'] and c['candidate_use']['selectable_on_App177']]
    return {i: {n: copy.deepcopy(row[n]) for n in names} for i, row in raw.items()}


def frozen_atoms(defs, encoder, base):
    flat = () if base == 'C0' else approved_atoms(selected_definitions(defs, base))
    expected_fixed = {a.atom_id for a in flat if not a.atom_id.startswith('UNFITTED_CONTROL:')}
    expected_numeric = {a.atom_id for a in flat if a.atom_id.startswith('UNFITTED_CONTROL:')}
    if set(encoder.get('fixed_atoms', [])) != expected_fixed or set(encoder.get('numeric', {})) != expected_numeric:
        raise ValueError('INITIAL_ENCODER_EXACT_INPUT_SET_MISMATCH')
    atoms = [a for a in flat if a.atom_id in expected_fixed]
    for a in flat:
        if a.atom_id not in expected_numeric: continue
        e = encoder['numeric'][a.atom_id]
        field = a.atom_id.removeprefix('UNFITTED_CONTROL:')
        expected_names = ['CONTROL:' + field + ':LE:' + repr(v) for v in e['thresholds']]
        if e['atom_ids'] != expected_names: raise ValueError('INITIAL_THRESHOLD_ID_MISMATCH')
        atoms.extend(Atom(n, a.family, a.surfaces, a.sources, (n,), 'CONTROL_LE', {'field':field,'threshold':v})
                     for n,v in zip(e['atom_ids'], e['thresholds'], strict=True))
    if base in ('C0', 'J0'):
        _, core_atoms = project_core({}, ledger(), 'SRC-111'); atoms.extend(core_atoms)
    return tuple(atoms)


def transform(raw, encoder, base):
    rows = {i: transform_numeric(row, encoder) if base != 'C0' else {} for i,row in raw.items()}
    if base in ('C0', 'J0'):
        core, _ = project_core(raw, ledger(), 'SRC-111')
        for i in rows: rows[i].update(core[i])
    return rows


def encode(access, defs, spec):
    base = spec['base_representation']
    if spec.get('initial_model_ref'):
        initial = load_initial(ROOT / spec['initial_model_ref'])
        if (initial.method_id != 'GREEDY_OR' or initial.binding['operating_point'] != 'OP05'
                or initial.binding['fold_id'] != access.fold_id or initial.fit['train_ids'] != list(access.ids)
                or initial.status not in ('FITTED', 'EMPTY_MODEL')):
            raise ValueError('INITIAL_MODEL_TRAIN_METHOD_OR_FOLD_MISMATCH')
        if spec.get('relation_families') or spec.get('matched_single_features'):
            if initial.view.get('relation_families') != spec.get('relation_families') or initial.view.get('matched_single_features') != spec.get('matched_single_features'):
                raise ValueError('INITIAL_RELATION_CONTRACT_MISMATCH')
        expected_rep = spec['representation']
        actual_rep = initial.view.get('representation')
        if expected_rep == 'W0' and actual_rep is None:
            if initial.view.get('surface') != 'app_web67': raise ValueError('INITIAL_SURFACE_MISMATCH')
        elif actual_rep != expected_rep: raise ValueError('INITIAL_REPRESENTATION_MISMATCH')
        encoder = copy.deepcopy(initial.encoder)
        if base != 'C0' and (encoder['train_ids'] != list(access.ids) or encoder['fold_id'] != access.fold_id):
            raise ValueError('INITIAL_ENCODER_BINDING_MISMATCH')
        atoms = frozen_atoms(defs, encoder, base)
        rows = transform(access.rows, encoder, base)
        init_info = {'type':'MATCHING_SAVED_TRAIN_MODEL', 'source':spec['initial_model_ref'],
                     'model_id':initial.model_id, 'threshold_refit':False,
                     'outer_predictions_or_scores_used':False, 'train_and_fold_binding_verified':True}
    else:
        initial = None
        if base == 'C0':
            rows, atoms = project_core(access.rows, ledger(), 'SRC-111'); encoder = {}
        else:
            rows, atoms, encoder, _ = encode_train(access, selected_definitions(defs, base), 'J0' if base=='J0' else 'S_FLAT')
        init_info = {'type':'SPARSE_INITIALIZATION_WITHIN_THIS_COUNTED_FIT', 'threshold_refit':base!='C0',
                     'outer_predictions_or_scores_used':False}
    return rows, atoms, encoder, initial, init_info


def compact_training(problem, atoms, selected, initial_ids, groups, trace, spec, init_info, access):
    pool = {c.id:c for c in problem.candidates}
    selected_ids = {c.id for c in selected}
    records = []
    for item in problem.manifest:
        cid = item['clause_id']; s = problem.support[cid]
        reasons = list(item['reasons'])
        if cid in selected_ids:
            reasons = ['SPARSE_INITIALIZATION' if cid in initial_ids else 'RETAINED_TRAIN_SIGNAL' if spec['method']=='R_KEEP_V1' else 'SPARSE_SELECTED']
        elif cid in pool:
            if spec['method']=='R_KEEP_V1': reasons = exclusion_reasons(problem, selected, pool[cid], groups)[0]
            else:
                score = problem.score(selected+(pool[cid],))
                if not compatible(selected+(pool[cid],),atoms,problem.method,problem.grammar,problem.search): reasons.append('STRUCTURE_OR_FAMILY_LIMIT')
                if score['clean_alarms']>problem.budget: reasons.append('SET_CLEAN_BUDGET')
                if not score['feasible']: reasons.append('FINAL_SET_CONSTRAINT')
                if score['objective']<=problem.score(selected)['objective']: reasons.append('NO_POSITIVE_SPARSE_OBJECTIVE_GAIN')
                if not reasons: reasons.append('GREEDY_SEARCH_OR_TIME_LIMIT')
        records.append({'clause_id':cid, 'eligible':item['eligible'], 'selected':cid in selected_ids,
                        'signal_group':groups[cid.rsplit(':',1)[0]], 'reasons':reasons,
                        'triplets':s['triplets'], 'true_attack_triplets':s['true_attack_triplets'],
                        'bundles':s['bundles'], 'environments':s['environments'],
                        'phase_availability':s['phase_availability'],
                        'singleton_train_clean_alarms':sum(problem.states[cid][n]=='T' for n in problem.clean)})
    return {'schema_version':'v2-b-compact-training-v1','initialization':init_info,
            'initial_clause_ids':sorted(initial_ids),'trace':trace,
            'candidate_manifest':records,'atoms':[vars(a) for a in atoms],
            'signal_group_version':GROUP_VERSION,'signal_groups':groups,
            'access_operations':access.operations,'train_ids_once':list(access.ids),
            'statistics_scope':'EXACT_OWN_TRAIN_ONLY_NO_OOF_INPUT',
            'omitted_repeated_matrices':'Regenerate from referenced frozen train inputs and encoder; no duplicate full V1/A matrices.'}


def fit_b(access, defs, spec, binding, relation_rows=None):
    started = time.monotonic(); deadline = started + 60
    rows, atoms, encoder, initial, init_info = encode(access, defs, spec)
    if spec.get('relation_families') or spec.get('matched_single_features'):
        from .relations import encode_relations
        if set(relation_rows or {}) != set(access.ids): raise ValueError('EXACT_TRAIN_RELATION_INPUTS_REQUIRED')
        relation_encoded, extras, rel_encoder = encode_relations(access, relation_rows, spec,
            encoder.get('v2_relations') if initial is not None else None)
        encoder['v2_relations'] = rel_encoder
        atoms = atoms + extras
        for i in rows: rows[i].update(relation_encoded[i])
    else: extras = ()
    view = {'view_id':'V2-B:'+spec['representation'], 'representation':spec['representation'],
            'kind':'V2_B_UNIFIED','base_representation':spec['base_representation'],
            'relation_families':spec.get('relation_families',[]),
            'matched_single_features':spec.get('matched_single_features',False),
            'input_atom_ids':sorted(a.atom_id for a in atoms),'new_relation_ids':[a.atom_id for a in extras]}
    problem = V2Problem(access, rows, atoms, deadline)
    groups = {a.atom_id:signal_group(a) for a in atoms}
    if initial is not None:
        old_manifest = read((ROOT/spec['initial_model_ref']).with_name('training.json'))['candidate_manifest']
        if {r['clause_id'] for r in old_manifest} != {r['clause_id'] for r in problem.manifest}:
            raise ValueError('SAVED_INITIAL_CANDIDATE_SET_MISMATCH')
        if {r['clause_id'] for r in old_manifest if r['eligible']} != {c.id for c in problem.candidates}:
            raise ValueError('SAVED_INITIAL_SUPPORT_COMPATIBILITY_MISMATCH')
        selected = initial.clauses
        outcome = {'status':'MATCHING_SAVED_SPARSE_INITIALIZATION'}; trace=[]
        check = json_score(problem.score(selected))
        old = initial.fit['training_result']
        for k in ('macro_tpr','clean_alarms','complexity','coverage','objective'):
            if check[k] != old[k]: raise ValueError('SAVED_INITIAL_TRAIN_CONTRACT_MISMATCH:'+k)
        init_info['candidate_support_and_training_score_verified'] = True
    else:
        access.assert_fit(access.batch(),'pruning')
        selected, outcome, trace = greedy(problem, deadline)
        if outcome['status'].startswith('FAILED'):
            raise RuntimeError('SPARSE_INITIALIZATION_FAILED:' + str(outcome))
    initial_ids = {c.id for c in selected}
    if spec['method']=='R_KEEP_V1':
        selected, outcome, retained = retain(problem, selected, groups, deadline)
        trace.extend(retained)
        if outcome['status']=='FAILED_FIT':
            raise RuntimeError('RETENTION_TIMEOUT_WITHOUT_FEASIBLE_INCUMBENT')
    elif spec['method']!='GREEDY_OR': raise PermissionError('UNAUTHORIZED_B_METHOD')
    if selected and not problem.score(selected)['feasible']: raise ValueError('B_FINAL_CONSTRAINT_FAILURE')
    status = 'FITTED' if selected else 'EMPTY_MODEL'
    selected_ids = {l.atom_id for c in selected for l in c.literals}
    audit = dict(outcome, train_ids=list(access.ids), train_expected_n=len(access.ids),
                 train_consumed_n=len(access.rows), fit_scope='V2_B_EXACT_AUTHORIZED_TRAIN_ONLY',
                 freeze_time=stamp(), elapsed_seconds=time.monotonic()-started,
                 candidate_pool_size=len(problem.candidates),registered_clause_count=len(problem.manifest),
                 training_result=json_score(problem.score(selected)),clean_budget_count=problem.budget,
                 clean_denominator=len(problem.clean),initialization=init_info,
                 actual_fit_invocations=1, internal_stages=['frozen_encoder_reuse' if initial else 'train_encoder_fit',
                    'train_support', 'saved_sparse_reuse' if initial else 'sparse_greedy',
                    'train_signal_retention' if spec['method']=='R_KEEP_V1' else 'sparse_result'])
    model = BModel(RuleModel(spec['method'],status,tuple(selected),tuple(a for a in atoms if a.atom_id in selected_ids),
                            binding,view,audit,encoder=encoder))
    training = compact_training(problem,atoms,selected,initial_ids,groups,trace,spec,init_info,access)
    return model, training


def predict_current(model, oid, raw, relation_input=None):
    if model.status in ('EMPTY_MODEL','FAILED'):
        return predict(model,oid,{})
    try:
        row = transform({'current':raw}, model.encoder, model.view['base_representation'])['current']
        if model.view['new_relation_ids']:
            from .relations import evaluate_relations
            row.update(evaluate_relations(relation_input, model.view, model.encoder['v2_relations']))
        return predict(model,oid,{'features':row,'view_id':model.view['view_id']})
    except (ValueError,KeyError,TypeError) as exc:
        result=predict(model,oid,{})
        result.update(decision='FAILED',failure_reason='V2_B_TRANSFORM:'+str(exc))
        return result
