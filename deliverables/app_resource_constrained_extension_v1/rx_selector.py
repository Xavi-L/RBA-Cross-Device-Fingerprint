"""Three finite learning tasks over eight fixed OR extensions."""
from fractions import Fraction
from rx_common import SETTINGS, SETS, FAMILIES, counts, combine, require, index
def score(base, chosen, members, inputs, settings=SETTINGS):
    require(all(m['role']=='selection' for m in members),'EVALUATION_MEMBER_IN_SELECTION')
    states={m['sample_id']:combine(inputs[m['sample_id']]['base_states'][base['model_id']],inputs[m['sample_id']]['conditions'],chosen) for m in members}
    normals={};reasons=[]
    for co,n in settings['normal_counts'].items():
        c=counts(states[m['sample_id']] for m in members if m['cohort']==co and m['identity']=='NORMAL')
        require(c['n']==n,'NORMAL_DENOMINATOR:'+co)
        c.update(budget=settings['normal_alarm_budgets'][co],minimum_defined=(9*n+9)//10)
        if c['T']>c['budget']:reasons.append('NORMAL_ALARM_BUDGET:'+co)
        if c['defined']*10<n*9:reasons.append('MODEL_DEFINED_COVERAGE:'+co)
        normals[co]=c
    quality={}
    for cid in chosen:
        c=counts(inputs[m['sample_id']]['conditions'][cid] for m in members if m['cohort']=='mtc_discovery')
        quality[cid]=c
        if c['defined']*10<c['n']*9:reasons.append('CANDIDATE_COVERAGE:'+cid)
    nr=base['rule_count']+len(chosen);nc=base['complexity']+2*len(chosen)
    if nr>settings['maximum_rules']:reasons.append('RULE_BUDGET')
    if nc>settings['maximum_complexity']:reasons.append('COMPLEXITY_BUDGET')
    families={f:counts(states[m['sample_id']] for m in members if m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==f) for f in FAMILIES}
    require(all(c['n'] for c in families.values()),'MISSING_TARGET_FAMILY')
    macro=sum(Fraction(c['T'],c['n']) for c in families.values())/len(FAMILIES)
    return dict(feasible=not reasons,reasons=reasons,normals=normals,candidate_quality=quality,
        rule_count=nr,complexity=nc,families=families,
        micro=counts(states[m['sample_id']] for m in members if m['identity']=='EFFECTIVE_INTERVENTION'),
        macro=dict(numerator=macro.numerator,denominator=macro.denominator,value=float(macro))),states
def choose(checks):
    feasible=[c for c in checks if c['feasible']]
    return min(feasible,key=lambda c:(-Fraction(c['macro']['numerator'],c['macro']['denominator']),len(c['extensions']),c['order'])) if feasible else None
def select(base,members,inputs):
    # Evaluation rows cannot reach score, even if a caller supplies the entire saved input map.
    selected=[m for m in members if m['role']=='selection'];ix={m['sample_id']:inputs[m['sample_id']] for m in selected}
    index(selected);checks=[];outputs=[]
    for order,(sid,chosen) in enumerate(SETS):
        result,states=score(base,chosen,selected,ix)
        checks.append(dict(base_model_id=base['model_id'],set_id=sid,extensions=list(chosen),order=order,**result))
        outputs.extend(dict(base_model_id=base['model_id'],set_id=sid,sample_id=k,state=v) for k,v in states.items())
    return checks,choose(checks),outputs
