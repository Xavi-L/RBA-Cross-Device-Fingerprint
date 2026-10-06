"""Three finite incremental learning tasks. No App training or encoder fitting."""
from fractions import Fraction
from common import counts, require, MODE
SETS = (('S0', ()), ('S1', ('C1',)), ('S2', ('C2',)), ('S12', ('C1','C2')))
FAMILIES = ('App_language', 'App_timezone', 'Browser_language', 'Browser_timezone')
BUDGETS = {'mtc_discovery':31, 'pilot18':0, 'b2b42':1}
NORMAL_N = {'mtc_discovery':630, 'pilot18':12, 'b2b42':34}
SETTINGS = dict(mode=MODE, sets=[{'id':k,'extensions':list(v)} for k,v in SETS],
    normal_counts=NORMAL_N, normal_alarm_budgets=BUDGETS, minimum_coverage='9/10',
    minimum_candidate_mtc_coverage='9/10', maximum_rules=8, maximum_complexity=16,
    new_single_literal_complexity=2, families=list(FAMILIES),
    ordering=['all_constraints_satisfied','max_macro_trigger_rate','min_new_rules','S0,S1,S2,S12'])

def combine(base, extensions, selected):
    """Same selected-input failure priority as the original predictor; then Kleene OR."""
    states = [base] + [extensions[c] for c in selected]
    require(all(s in ('T','F','U','FAILED') for s in states), 'INVALID_INPUT_STATE')
    if 'FAILED' in states: return 'FAILED'
    if 'T' in states: return 'T'
    return 'F' if all(s=='F' for s in states) else 'U'

def score(mid, chosen, members, inputs, base_size, base_complexity, settings=SETTINGS):
    require(all(m['role']=='selection' for m in members), 'EVALUATION_MEMBER_IN_SELECTION')
    states = {m['sample_id']:combine(inputs[m['sample_id']]['base_states'][mid],
        inputs[m['sample_id']]['conditions'],chosen) for m in members}
    normals={}; reasons=[]
    for cohort,budget in settings['normal_alarm_budgets'].items():
        sub=[m for m in members if m['cohort']==cohort and m['identity']=='NORMAL']
        c=counts(states[m['sample_id']] for m in sub)
        require(c['n']==settings['normal_counts'][cohort], 'NORMAL_MEMBERSHIP_CHANGED:'+cohort)
        c.update(budget=budget, minimum_defined=(c['n']*9+9)//10)
        if c['T']>budget: reasons.append('NORMAL_ALARM_BUDGET:'+cohort)
        if c['defined']*10<c['n']*9: reasons.append('MODEL_DEFINED_COVERAGE:'+cohort)
        normals[cohort]=c
    candidate_coverage={}
    mtc=[m for m in members if m['cohort']=='mtc_discovery']
    for cid in chosen:
        c=counts(inputs[m['sample_id']]['conditions'][cid] for m in mtc)
        candidate_coverage[cid]=c
        if c['defined']*10<c['n']*9: reasons.append('CANDIDATE_COVERAGE:'+cid)
    rules=base_size+len(chosen); complexity=base_complexity+2*len(chosen)
    if rules>settings['maximum_rules']: reasons.append('RULE_BUDGET')
    if complexity>settings['maximum_complexity']: reasons.append('COMPLEXITY_BUDGET')
    families={}; fractions=[]
    for family in FAMILIES:
        c=counts(states[m['sample_id']] for m in members if m['identity']=='EFFECTIVE_INTERVENTION' and m['family']==family)
        require(c['n']>0, 'EMPTY_TARGET_FAMILY:'+family)
        fractions.append(Fraction(c['T'],c['n'])); families[family]=c
    macro=sum(fractions)/len(FAMILIES)
    pref=counts(states[m['sample_id']] for m in members if m.get('scenario')=='L_BROWSER_LANG' and m['phase']=='change' and m['identity']=='NORMAL')
    return dict(feasible=not reasons, reasons=reasons, normals=normals, candidates=candidate_coverage,
        families=families, macro=dict(numerator=macro.numerator,denominator=macro.denominator,value=float(macro)),
        normal_browser_preference_change=pref, rule_count=rules, complexity=complexity), states

def select(mid, members, inputs, base_size, base_complexity, settings=SETTINGS):
    checks=[]; per_member=[]
    for order,(sid,chosen) in enumerate(SETS):
        result,states=score(mid,chosen,members,inputs,base_size,base_complexity,settings)
        checks.append(dict(base_model_id=mid,set_id=sid,extensions=list(chosen),order=order,**result))
        per_member.extend(dict(base_model_id=mid,set_id=sid,sample_id=k,state=v) for k,v in states.items())
    feasible=[c for c in checks if c['feasible']]
    winner=min(feasible,key=lambda c:(-Fraction(c['macro']['numerator'],c['macro']['denominator']),len(c['extensions']),c['order'])) if feasible else None
    return checks, winner, per_member
