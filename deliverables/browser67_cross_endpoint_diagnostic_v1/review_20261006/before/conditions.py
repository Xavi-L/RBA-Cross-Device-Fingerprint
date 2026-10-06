"""Five frozen, current-pair-only diagnostics; labels never enter this module."""
import math
from hybridguard_agent.research.mtc_p3_candidates import candidate_templates, evaluate_candidate
from hybridguard_agent.research.rule_semantics_revision_v1.language import limited_full_tag
A='app.web_data.'
B='browser.web_data.'
LANG='navigator_layer.language'
LIST='navigator_layer.languages'
OFFSET='execution_layer.timezone_offset'
DEPS={'C1':[A+OFFSET,B+OFFSET],'C2':[A+LANG,B+LANG],'C3':[A+LANG,B+LANG],
      'D1':[A+LIST,B+LIST],'D2':[B+LANG,B+LIST]}
P3={c['candidate_id']:c for c in candidate_templates()}
MAPPING={'MATCH':'F','COUNTEREXAMPLE':'T','UNKNOWN':'U','NOT_APPLICABLE':'U'}

def evaluate(cid, pair):
    fields=[{'field':f,'present':f in pair.get('features',{}),'value':pair.get('features',{}).get(f),
             'status':pair.get('field_status',{}).get(f),'quality':pair.get('field_quality',{}).get(f)} for f in DEPS[cid]]
    def result(state,reason,**extra):
        if cid=='C1': extra.setdefault('time_diagnostics',pair.get('times',{}))
        saved=[]
        for field in fields:
            field=dict(field)
            if type(field['value']) is float and not math.isfinite(field['value']):
                field.update(value=repr(field['value']),raw_value_type='nonfinite_float',serialization='lossless diagnostic spelling, not a string measurement')
            saved.append(field)
        return dict(condition_id=cid,state=state,reason=reason,operands=saved,**extra)
    if pair.get('errors'): return result('FAILED','PAIR_BINDING_FAILED',errors=pair['errors'])
    for f in fields:
        if not f['present'] or f['status']!='observed' or f['quality']!='observed_value' or f['value'] is None:
            return result('U','UNAVAILABLE_OPERAND')
    x,y=[f['value'] for f in fields]
    if cid=='D1':
        p=evaluate_candidate(P3['P3-X-LANGUAGES'],{k:pair[k] for k in ('features','field_status','field_quality')})
        return result(MAPPING[p['outcome']],p['reason'],p3_outcome=p['outcome'])
    if cid=='C1':
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (x,y)):
            return result('U','OFFSET_NOT_FINITE_NUMBER')
        p=evaluate_candidate(P3['P3-X-TIMEZONE-OFFSET'],{k:pair[k] for k in ('features','field_status','field_quality')})
        return result(MAPPING[p['outcome']],p['reason'],p3_outcome=p['outcome'],time_diagnostics=pair.get('times',{}))
    if cid=='D2':
        if type(y) is not list or not y or any(type(v) is not str for v in y):
            return result('U','INVALID_LANGUAGE_LIST')
        y=y[0]
    nx,ny=limited_full_tag(x),limited_full_tag(y)
    if nx is None or ny is None: return result('U','OUTSIDE_FIXED_LIMITED_TAG_DOMAIN')
    if cid=='C3': nx,ny=nx.split('-')[0],ny.split('-')[0]
    return result('T' if nx!=ny else 'F','NORMALIZED_DIFFERENT' if nx!=ny else 'NORMALIZED_EQUAL',normalized=[nx,ny])
