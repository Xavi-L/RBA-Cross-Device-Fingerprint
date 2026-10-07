"""Saved-state contracts, with no prediction or selection at import time."""
import json
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE.parent / 'cross_endpoint_constrained_extension_v1'
RESOURCE = HERE.parent / 'app_resource_paired_validation_v1'
CANDIDATES = {'M': 'R_NATIVE_BROWSER_MEMORY', 'W': 'R_WEB_MEMORY_DIFFERENCE', 'B': 'D_BROWSER_MEMORY8'}
SETS = (('S0', ()), ('M', ('M',)), ('W', ('W',)), ('B', ('B',)),
        ('MW', ('M','W')), ('MB', ('M','B')), ('WB', ('W','B')), ('MWB', ('M','W','B')))
FAMILIES = ('App_language','App_timezone','Browser_language','Browser_timezone',
            'App_resource16_48','App_memory4','Browser_resource16_48','Browser_memory4')
NORMAL_N = {'mtc_discovery':630, 'pilot18':12, 'b2b42':34, 'resource54':42}
SETTINGS = dict(mode='DEVELOPMENT_RESOURCE_EXTENSION_SELECTION', candidate_order=list(CANDIDATES),
    candidates=CANDIDATES, sets=[dict(id=k,extensions=list(v)) for k,v in SETS], families=list(FAMILIES),
    normal_counts=NORMAL_N, normal_alarm_budgets={'mtc_discovery':31,'pilot18':0,'b2b42':1,'resource54':2},
    minimum_coverage='9/10', minimum_candidate_mtc_coverage='9/10', maximum_rules=8,
    maximum_complexity=16, new_single_literal_complexity=2,
    ordering=['all_constraints','max_eight_family_macro','min_added_conditions','fixed_set_order'],
    selection_positions=744, historical_evaluation_positions=261, collection=0, app_fit=0, tree_fit=0, encoder_fit=0)
def require(ok, reason):
    if not ok: raise ValueError(reason)
def read(p): return json.loads(Path(p).read_text())
def rows(p): return [json.loads(line) for line in Path(p).read_text().splitlines()]
def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,x): Path(p).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in x))
def index(rs,key=lambda r:r['sample_id']):
    out={key(r):r for r in rs};require(len(out)==len(rs),'DUPLICATE_ID_OR_COMBINATION');return out
def counts(ss):
    c=Counter(ss);require(set(c)<=set(('T','F','U','FAILED')),'INVALID_STATE')
    return dict(n=sum(c.values()),**{s:c[s] for s in ('T','F','U','FAILED')},defined=c['T']+c['F'])
def combine(base, states, chosen):
    ss=[base]+[states[c] for c in chosen];counts(ss)
    return 'FAILED' if 'FAILED' in ss else 'T' if 'T' in ss else 'U' if 'U' in ss else 'F'
def validate(members, inputs, mids, expected_n=None):
    mi=index(members);ix=index(inputs)
    require(set(mi)==set(ix),'INPUT_MEMBERSHIP_MISMATCH')
    if expected_n is not None: require(len(mi)==expected_n,'MEMBER_COUNT')
    for sid,m in mi.items():
        r=ix[sid]
        require(all(r[k]==m[k] for k in ('cohort','role','identity')),'OUTPUT_IDENTITY_MISMATCH')
        require(set(r['base_states'])==set(mids),'MODEL_CARTESIAN_MISMATCH')
        require(set(r['conditions'])==set(CANDIDATES),'CONDITION_CARTESIAN_MISMATCH')
        counts([*r['base_states'].values(),*r['conditions'].values(),r['C1'],*r['app_states'].values()])
    return ix
