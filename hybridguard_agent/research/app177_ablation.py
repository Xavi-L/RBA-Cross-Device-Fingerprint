"""App177 component ablations over frozen encoding and the original selectors.

No Full refit, evaluation access, global budget mutation, or Browser features.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import math
import time

from . import mtc_constrained_reselection as base
from . import mtc_reselection_candidates as old
from . import mtc_timezone_candidates as candidates
from .mtc_resource_relations import MEMORY_ID
from .mtc_timezone_relation import TIMEZONE_ID
from .rule_learning.baselines import transform_numeric
from .rule_learning.contracts import contract
from .rule_learning.models import RuleModel, Atom
from .rule_learning.predictor import predict
from .rule_learning.selector import compatible, json_score
from .rule_learning_v2.adapter import TrainAccess, approved_atoms, atom_from_dict
from .rule_learning_v2.semantic_selection import semantic_catalog, greedy_semantic, retain_semantic
from .rule_semantics_webgl1_cap8 import PROFILE, apply_capacity
from types import SimpleNamespace

VERSION = 'app177-core-ablation-v1'
SCHEMA = 'app177-component-model-v1'
SCHEMES = ('A_NO_MTC_CAP', 'A_APP_WEB_ONLY', 'A_NO_MEMORY_REL', 'A_NO_TIMEZONE_REL')


def dependency(atom):
    p = atom.provenance
    refs = list(p.get('field_refs') or [p['field']])
    # Frozen kernels project to these operands before parsing/normalization.
    # WebGL/driver source manifests gate binding, never Native/Host measurements.
    surfaces = sorted({'native84' if f.startswith('app.android_native_data.') else
                       'host26' if f.startswith('app.webview_data.') else
                       'app_web67' if f.startswith(('app.web_data.', 'app.collection_observations.')) else
                       'UNREGISTERED' for f in refs})
    cross = 'native84' in surfaces or 'host26' in surfaces
    family = ('memory_relation' if cross and any('memory' in f for f in refs) else
              'timezone_relation' if cross and any('timezone' in f for f in refs) else
              'same_web_viewport' if atom.atom_id.startswith('REL:SCREEN_') else 'base')
    return dict(atom_id=atom.atom_id, operands=refs, measurement_surfaces=surfaces,
                family=family, aliases=list(atom.aliases), polarities=['POSITIVE','NEGATIVE'],
                metadata_refs=p.get('metadata_refs', []), condition=p.get('condition'),
                numeric_threshold=p.get('threshold'),
                gate='registered typed/status/quality and operand domain; same-current-record binding',
                diagnostic_only=['app.web_data.execution_layer.timezone_id'] if family=='timezone_relation' else [])


def allowed(atom, scheme):
    if scheme not in (*SCHEMES, 'APP_FULL', 'APP_TREE'):
        raise ValueError('UNKNOWN_APP_SCHEME')
    d = dependency(atom)
    if 'UNREGISTERED' in d['measurement_surfaces']:
        raise ValueError('UNREGISTERED_MEASUREMENT_DEPENDENCY')
    return not ((scheme=='A_APP_WEB_ONLY' and set(d['measurement_surfaces']) != {'app_web67'}) or
                (scheme=='A_NO_MEMORY_REL' and d['family']=='memory_relation') or
                (scheme=='A_NO_TIMEZONE_REL' and d['family']=='timezone_relation'))


def frozen_atoms(encoder):
    """Reconstruct the original atom order without fitting any quantiles."""
    flat = approved_atoms(old.definitions())
    atoms = [a for a in flat if not a.atom_id.startswith('UNFITTED_CONTROL:')]
    if encoder['fixed_atoms'] != [a.atom_id for a in atoms]:
        raise ValueError('FROZEN_FIXED_ATOMS_CHANGED')
    for a in flat:
        if a.atom_id.startswith('UNFITTED_CONTROL:'):
            fit = encoder['numeric'][a.atom_id]
            for n,t in zip(fit['atom_ids'],fit['thresholds'],strict=True):
                if n != 'CONTROL:'+a.atom_id.removeprefix('UNFITTED_CONTROL:')+':LE:'+repr(t):
                    raise ValueError('FROZEN_NUMERIC_ID_CHANGED')
                atoms.append(Atom(n,a.family,a.surfaces,a.sources,(n,),'CONTROL_LE',
                                  {'field':a.atom_id.removeprefix('UNFITTED_CONTROL:'),'threshold':t}))
    return tuple(atoms)+tuple(candidates.registered_atoms())


def encode(raw, encoder, names):
    out = transform_numeric(raw,encoder,names)
    rel = {a.atom_id for a in candidates.registered_atoms()}
    out.update({n:deepcopy(raw[n]) for n in set(names)&rel})
    if set(out)!=set(names): raise ValueError('ENCODED_SCOPE_MISMATCH')
    return out


@dataclass(frozen=True)
class Prepared:
    common: base.PreparedFold
    scheme: str
    removed: tuple


def prepare(job, raw, meta, mtc, mtc_meta, encoder, *, scheme, mtc_ids, evaluation_ids):
    if scheme not in (*SCHEMES,'APP_FULL','APP_TREE'): raise ValueError('UNKNOWN_SCHEME')
    access = TrainAccess(job,raw,meta)
    base._normal_members(mtc,mtc_meta,mtc_ids,evaluation_ids)
    if set(mtc_ids)&(set(job['train_ids'])|set(job['outer_test_ids'])):
        raise PermissionError('POPULATION_OVERLAP')
    if encoder['train_ids']!=list(access.ids) or encoder['fold_id']!=job['fold_id']:
        raise PermissionError('FROZEN_ENCODER_TRAIN_MISMATCH')
    full = frozen_atoms(encoder)
    atoms = tuple(a for a in full if allowed(a,scheme))
    names = [a.atom_id for a in atoms]
    common = base.PreparedFold(deepcopy(job),deepcopy(raw),deepcopy(meta),
        {s:encode(r,encoder,names) for s,r in raw.items()},
        {s:encode(r,encoder,names) for s,r in mtc.items()},deepcopy(mtc_meta),tuple(mtc_ids),
        tuple(evaluation_ids),atoms,deepcopy(encoder),
        {'threshold_fit_calls':0,'encoder_loaded':True,'evaluation_rows_received':False})
    return Prepared(common,scheme,tuple(dependency(a) for a in full if not allowed(a,scheme)))


class AppProblem(base.DualNormalProblem):
    def __init__(self, *args, no_mtc_cap=False, **kwargs):
        super().__init__(*args, scheme='B', **kwargs)
        # _pool builds states, never scores sets. Lock the instance constraint
        # before its first score/cache entry. No instance is shared across fits.
        if self._score_cache: raise RuntimeError('BUDGET_CHANGE_AFTER_SCORE_FORBIDDEN')
        self._app_mtc_budget = len(self.mtc_ids) if no_mtc_cap else self.mtc_budget
        self.mtc_budget = self._app_mtc_budget
    def score(self, clauses):
        if self.mtc_budget != self._app_mtc_budget:
            raise RuntimeError('IMMUTABLE_APP_CONSTRAINT_INSTANCE')
        return super().score(clauses)


def problem(prepared, deadline):
    c = prepared.common
    base._normal_members(c.mtc_rows,c.mtc_metadata,c.mtc_train_ids,c.mtc_evaluation_ids)
    access = TrainAccess(c.job,c.raw_rows,c.metadata)
    return AppProblem(access,c.controlled_rows,c.atoms,deadline,c.mtc_rows,c.mtc_train_ids,
                      no_mtc_cap=prepared.scheme=='A_NO_MTC_CAP'),access


@dataclass(frozen=True)
class AppModel(RuleModel):
    schema_version: str = SCHEMA
    def __post_init__(self):
        if (self.schema_version!=SCHEMA or self.binding.get('experiment_id')!=VERSION or
            self.binding.get('scheme') not in SCHEMES or self.fit.get('adapter_version')!=VERSION or
            self.method_id not in base.METHODS.values() or self.fit.get('capacity_profile')!=PROFILE or
            self.view.get('kind')!='APP_COMPONENT_ABLATION' or self.constant is not None):
            raise ValueError('APP_ABLATION_IDENTITY_REQUIRED')
        if self.status not in ('FITTED','FAILED','EMPTY_MODEL') or (self.status=='FITTED')!=bool(self.clauses):
            raise ValueError('INVALID_APP_MODEL_STATUS')
        names=[a.atom_id for a in self.atoms]
        if len(names)!=len(set(names)) or set(names)!={l.atom_id for c in self.clauses for l in c.literals}:
            raise ValueError('ONLY_SELECTED_DEPENDENCIES_REQUIRED')
        if any(not allowed(a,self.binding['scheme']) for a in self.atoms):
            raise ValueError('REMOVED_COMPONENT_IN_MODEL')
        limits=apply_capacity(SimpleNamespace(search=contract('learning_search_space'),grammar=contract('candidate_grammar')))
        if any(len(c.literals)!=1 for c in self.clauses) or not compatible(self.clauses,self.atoms,'GREEDY_OR',limits.grammar,limits.search):
            raise ValueError('UNCHANGED_CAP8_REQUIRED')
        semantic_catalog(self.atoms)
        object.__setattr__(self,'_frozen_content',self._content())
    @property
    def model_id(self): return 'app177-ablation-'+super().model_id.removeprefix('r03-')


def fit(prepared, *, stage, initial_model=None, initial_training=None):
    if type(prepared) is not Prepared or prepared.scheme not in SCHEMES or stage not in base.METHODS:
        raise ValueError('DEDICATED_APP_PREPARATION_REQUIRED')
    c=prepared.common; initialization=None
    if stage=='RETENTION':
        if (type(initial_model) is not AppModel or initial_model.binding['scheme']!=prepared.scheme or
            initial_model.binding['fold_id']!=c.job['fold_id'] or initial_model.binding['stage']!='SPARSE' or
            initial_model.fit['train_ids']!=list(c.ids) or initial_model.fit['mtc_train_ids']!=list(c.mtc_train_ids) or
            initial_model.encoder!=c.encoder or initial_model.view['input_atom_ids']!=sorted(a.atom_id for a in c.atoms) or
            not initial_training or initial_training.get('model_id')!=initial_model.model_id):
            raise PermissionError('OWN_VARIANT_SAME_FOLD_SPARSE_REQUIRED')
        initialization={'kind':'OWN_VARIANT_SPARSE','model_id':initial_model.model_id,'threshold_refit':False}
    started=time.monotonic();deadline=started+60
    p,access=problem(prepared,deadline)
    selected,trace,failure=(),[],None
    try:
        if stage=='SPARSE':
            access.assert_fit(access.batch(),'pruning');selected,outcome,trace=greedy_semantic(p,deadline)
        elif initial_model.status=='FAILED': raise ValueError('SPARSE_INITIALIZATION_FAILED')
        else: selected,outcome,trace=retain_semantic(p,initial_model.clauses,deadline)
        if selected and not p.score(selected)['feasible']: raise ValueError('FINAL_APP_SET_INFEASIBLE')
    except Exception as e:
        failure={'type':type(e).__name__,'reason':str(e)}
        outcome={'status':'FAILED_FIT','reason':str(e),'infeasibility_proved':False};selected=()
    status='FAILED' if outcome['status'].startswith('FAILED') else 'FITTED' if selected else 'EMPTY_MODEL'
    score=json_score(p.score(selected));selected_ids={l.atom_id for cl in selected for l in cl.literals}
    audit=dict(outcome,adapter_version=VERSION,train_ids=list(c.ids),mtc_train_ids=list(c.mtc_train_ids),
        clean_budget_count=p.budget,clean_denominator=len(p.clean),mtc_budget_count=p.mtc_budget,
        mtc_denominator=len(p.mtc_ids),training_result=score,capacity_profile=deepcopy(PROFILE),
        relation_parameters=candidates.parameters(),relation_atom_ids=[a.atom_id for a in c.atoms if a.atom_id in {a.atom_id for a in candidates.registered_atoms()}],
        threshold_refit=False,actual_fit_invocations=1,freeze_time=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.monotonic()-started,failure=failure,initialization=initialization,
        set_constraint_rejection_counts=dict(p.constraint_rejections))
    model=AppModel(base.METHODS[stage],status,tuple(selected),tuple(a for a in c.atoms if a.atom_id in selected_ids),
        {'experiment_id':VERSION,'scheme':prepared.scheme,'fold_id':c.job['fold_id'],'stage':stage,'operating_point':'OP05'},
        {'kind':'APP_COMPONENT_ABLATION','view_id':VERSION+':'+prepared.scheme+':'+stage,
         'input_atom_ids':sorted(a.atom_id for a in c.atoms)},audit,encoder=deepcopy(c.encoder))
    detail={'model_id':model.model_id,'scheme':prepared.scheme,'stage':stage,'fold_id':c.job['fold_id'],
        'train_ids':list(c.ids),'mtc_train_ids':list(c.mtc_train_ids),'trace':trace,
        'candidate_statistics':base._candidate_statistics(p,selected),'whole_set_result':score,
        'encoded_atoms':[asdict(a) for a in c.atoms],'removed_atoms':list(prepared.removed),
        'initialization':initialization,'failure':failure,'access_operations':access.operations}
    return model,detail


def predict_current(model,sid,raw):
    if type(model) is not AppModel: raise TypeError('APP_MODEL_REQUIRED')
    if model.status in ('FAILED','EMPTY_MODEL'): return predict(model,sid,{})
    try: return predict(model,sid,{'features':encode(raw,model.encoder,[a.atom_id for a in model.atoms]),'view_id':model.view['view_id']})
    except (KeyError,ValueError,TypeError) as e:
        r=predict(model,sid,{});r.update(decision='FAILED',failure_reason='APP_INPUT:'+str(e));return r
