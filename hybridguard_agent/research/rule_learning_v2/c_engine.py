"""V2-C identity around the unchanged B learning program; no new method."""
from dataclasses import dataclass

from hybridguard_agent.research.rule_learning.models import RuleModel
from .b_engine import _fit_unified, predict_current, project_inputs
from .common import digest, read, write
from .retention import GROUP_VERSION

AUTH = 'USER_V2_C_OFFLINE_FINALIZATION_20260925'
VERSION = 'V2_C_ENGINE_V1'
FINAL_ROLE = 'FINAL_DEVELOPMENT_FIT_TRAINING_RESUBSTITUTION'
LOCO_ROLE = 'EXPOSED_CONFIGURATION_HOLDOUT_INTERNAL_EVALUATION'


@dataclass(frozen=True)
class CModel:
    engine: RuleModel

    def __post_init__(self):
        b=self.engine.binding
        if (b.get('phase')!='V2-C' or b.get('authorization_id')!=AUTH
                or b.get('study_version')!='discriminative-rule-learning-v2-20260925'
                or b.get('candidate_version')!=GROUP_VERSION
                or b.get('evaluation_role') not in (FINAL_ROLE,LOCO_ROLE,'SYNTHETIC_ENGINEERING_FIXTURE')
                or b.get('train_membership_digest')!=digest(self.engine.fit['train_ids'])):
            raise ValueError('EXPLICIT_V2_C_IDENTITY_AND_TRAIN_SCOPE_REQUIRED')

    def __getattr__(self,name):return getattr(self.engine,name)

    @property
    def model_id(self):return 'v2c-'+digest(self.engine.to_dict())[:24]

    def to_dict(self):
        return {'schema_version':'v2-c-model-v1','model_id':self.model_id,
                'kernel_schema':'REUSED_FROZEN_B_LEARNING_PROGRAM_NO_V1_JOB_AUTHORIZATION',
                'engine_structure':self.engine.to_dict()}


def save_model(model,path):write(path,model.to_dict())


def load_model(path):
    raw=read(path)
    if raw['schema_version']!='v2-c-model-v1':raise ValueError('WRONG_C_MODEL_SCHEMA')
    result=CModel(RuleModel.from_dict(raw['engine_structure']))
    if result.model_id!=raw['model_id']:raise ValueError('C_MODEL_CONTENT_MISMATCH')
    return result


def fit_c(access,defs,spec,binding):
    if (binding.get('phase')!='V2-C' or binding.get('authorization_id')!=AUTH
            or binding.get('train_membership_digest')!=digest(list(access.ids))):
        raise PermissionError('C_AUTHORIZED_TRAIN_SCOPE_REQUIRED')
    if (spec['representation'],spec['method']) not in (('C0','GREEDY_OR'),('W0','GREEDY_OR'),('W0','R_KEEP_V1')):
        raise PermissionError('C_FROZEN_PROCEDURES_ONLY')
    if spec['base_representation']!=spec['representation'] or spec.get('relation_families') or spec.get('matched_single_features'):
        raise PermissionError('C_NO_NEW_REPRESENTATION')
    if bool(spec.get('initial_model_ref')) != (spec['method']=='R_KEEP_V1'):
        raise PermissionError('C_RETENTION_REQUIRES_ALREADY_CHARGED_MATCHING_INITIALIZATION')
    model,training=_fit_unified(access,defs,spec,binding,None,CModel,'V2-C')
    training['schema_version']='v2-c-compact-training-v1'
    return model,training
