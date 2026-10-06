import copy, tempfile, unittest
from pathlib import Path
from common import *
from selector import *
from adapter import qualify
from inference import predict_saved

def fixture():
    settings=copy.deepcopy(SETTINGS)
    settings['normal_counts']={c:10 for c in BUDGETS}
    settings['normal_alarm_budgets']={c:0 for c in BUDGETS}
    members=[]; inputs={}
    for c in BUDGETS:
        for i in range(10):
            sid=f'{c}:{i}';members.append(dict(sample_id=sid,cohort=c,role='selection',identity='NORMAL',scenario='control',phase='pre'))
    for f in FAMILIES:members.append(dict(sample_id=f,cohort='b2b42',role='selection',identity='EFFECTIVE_INTERVENTION',family=f,scenario='attack',phase='change'))
    for m in members:inputs[m['sample_id']]=dict(base_states={'base':'F'},conditions={'C1':'F','C2':'F'})
    for f in FAMILIES:
        inputs[f]['conditions']['C1' if f.endswith('timezone') else 'C2']='T'
    # Genuine normal counterexample: same C2 state as language interventions.
    inputs['b2b42:0']['conditions']['C2']='T'
    return members,inputs,settings

class Semantics(unittest.TestCase):
    def test_or_truth_table(self):
        expected={('F','F'):'F',('F','U'):'U',('T','U'):'T',('U','U'):'U',('U','T'):'T',('F','T'):'T'}
        for (a,b),c in expected.items():self.assertEqual(combine(a,{'C1':b},['C1']),c)
    def test_failure_no_short_circuit(self):
        self.assertEqual(combine('T',{'C1':'FAILED'},['C1']),'FAILED')
        self.assertEqual(combine('FAILED',{'C1':'T'},['C1']),'FAILED')
    def test_unselected_failure_and_empty_extension(self):
        for s in STATES:self.assertEqual(combine(s,{'C2':'FAILED'},[]),s)
        self.assertEqual(combine('F',{'C1':'F','C2':'FAILED'},['C1']),'F')
    def test_missing_browser_keeps_app_but_not_false_fallback(self):
        self.assertEqual(combine('F',{'C1':'U'},['C1']),'U')
        self.assertEqual(combine('T',{'C1':'U'},['C1']),'T')
    def test_only_c1_feasible_increment(self):
        m,i,s=fixture();checks,w,_=select('base',m,i,5,10,s)
        self.assertEqual(w['set_id'],'S1');self.assertFalse(checks[2]['feasible']);self.assertEqual(w['macro']['value'],.5)
    def test_only_baseline_feasible_combined_coverage(self):
        m,i,s=fixture();i['mtc_discovery:0']['base_states']['base']='U';i['mtc_discovery:1']['conditions']['C1']='U'
        checks,w,_=select('base',m,i,5,10,s)
        self.assertEqual(w['set_id'],'S0');self.assertEqual(checks[1]['candidates']['C1']['defined'],9)
        self.assertIn('MODEL_DEFINED_COVERAGE:mtc_discovery',checks[1]['reasons'])
    def test_no_feasible_set(self):
        m,i,s=fixture();i['pilot18:0']['base_states']['base']='T'
        checks,w,_=select('base',m,i,5,10,s);self.assertIsNone(w)
    def test_fixed_tie_fewest_then_id(self):
        m,i,s=fixture();i['b2b42:0']['conditions']['C2']='F'
        for f in FAMILIES:i[f]['conditions']={'C1':'T','C2':'T'}
        self.assertEqual(select('base',m,i,5,10,s)[1]['set_id'],'S1')
        for f in FAMILIES:i[f]['base_states']['base']='T'
        self.assertEqual(select('base',m,i,5,10,s)[1]['set_id'],'S0')
    def test_normal_budgets_never_pooled(self):
        m,i,s=fixture();s['normal_alarm_budgets']['mtc_discovery']=31
        checks,w,_=select('base',m,i,5,10,s)
        self.assertIn('NORMAL_ALARM_BUDGET:b2b42',checks[2]['reasons'])
        self.assertEqual(i['b2b42:0']['conditions']['C2'],i['App_language']['conditions']['C2'])
    def test_preference_really_changes_feasibility(self):
        m,i,s=fixture();checks,w,_=select('base',m,i,5,10,s)
        self.assertFalse(checks[3]['feasible'])
        # Unit fixture demonstrates constraint is data-driven, not a C2 name ban.
        i['b2b42:0']['conditions']['C2']='F'
        self.assertEqual(select('base',m,i,5,10,s)[1]['set_id'],'S12')
    def test_no_evaluation_leak(self):
        m,i,s=fixture();a=select('base',m,i,5,10,s)
        i['heldout144']={'base_states':{'base':'T'},'conditions':{'C1':'FAILED','C2':'T'}}
        self.assertEqual(a,select('base',m,i,5,10,s))
        m.append(dict(sample_id='heldout144',role='historical_evaluation'))
        with self.assertRaisesRegex(ValueError,'EVALUATION_MEMBER'):select('base',m,i,5,10,s)
    def test_failed_attack_kept_in_macro(self):
        m,i,s=fixture();i['App_language']['base_states']['base']='FAILED'
        checks,w,_=select('base',m,i,5,10,s)
        self.assertEqual(checks[0]['families']['App_language']['n'],1)
        self.assertEqual(checks[0]['families']['App_language']['FAILED'],1)
    def test_capacity_unchanged(self):
        m,i,s=fixture();checks,w,_=select('base',m,i,8,16,s)
        self.assertEqual(w['set_id'],'S0');self.assertIn('COMPLEXITY_BUDGET',checks[1]['reasons'])

class Denominator(unittest.TestCase):
    def position(self,identity='CONTROLLED_INTERVENTION'):
        return dict(meta=dict(scenario='A_APP_LANG',phase='change'),qualification=dict(identity=identity,operation_effect='OBSERVED_CHANGE',fully_qualified=False,runtime_restored=False),app_errors=['UNREADABLE'],browser_errors=[],pair_errors=[])
    def test_effective_but_restore_failed_stays(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.json';write(p,self.position());q=qualify(read(p),None)
        self.assertEqual(q['identity'],'EFFECTIVE_INTERVENTION');self.assertFalse(q['app_input_available']);self.assertFalse(q['full_recovery_qualified'])
    def test_confirmed_normal_not_lost_by_future_failure(self):
        p=self.position('NORMAL');p['meta'].update(scenario='L_BROWSER_LANG')
        self.assertEqual(qualify(p,None)['identity'],'NORMAL')
    def test_pre_stage_independent_operation_basis(self):
        p=self.position('UNCONFIRMED');p['meta']['phase']='pre'
        cap=dict(control_installed=False,setting={'status':'NOT_NEEDED','after':{'locale':'en-US','timezone':'Asia/Shanghai'}},**{e+'_before':{'languageHasOwn':False,'languagesHasOwn':False} for e in ('app','browser')})
        self.assertEqual(qualify(p,cap)['identity'],'NORMAL')
    def test_no_effect_and_unknown_not_attack(self):
        p=self.position('UNCONFIRMED');p['qualification']['operation_effect']='NO_OBSERVABLE_EFFECT'
        self.assertEqual(qualify(p,None)['identity'],'UNCONFIRMED')
    def test_no_feasible_model_not_silently_baseline(self):
        with self.assertRaises(ValueError):predict_saved({'status':'NO_FEASIBLE_SET'},'F',{})

if __name__=='__main__':unittest.main()
