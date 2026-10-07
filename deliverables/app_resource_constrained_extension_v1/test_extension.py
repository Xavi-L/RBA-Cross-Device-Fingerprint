"""Targeted selector/state boundaries, using synthetic fixtures only."""
import unittest,copy
import tempfile,sys,os
from unittest.mock import patch
from rx_common import *
from rx_selector import select,score,choose
def fixture():
    ms=[]
    for co,n in NORMAL_N.items():
        ms.extend(dict(sample_id=f'{co}:{i}',cohort=co,role='selection',identity='NORMAL',family=None) for i in range(n))
    for family,n in zip(FAMILIES,[2,2,5,5,3,3,3,3]):
        ms.extend(dict(sample_id=f'{family}:{i}',cohort='resource54',role='selection',identity='EFFECTIVE_INTERVENTION',family=family) for i in range(n))
    ix={m['sample_id']:dict(sample_id=m['sample_id'],base_states={'base':'F'},conditions={c:'F' for c in CANDIDATES}) for m in ms}
    return dict(model_id='base',rule_count=7,complexity=14),ms,ix
class SelectionTests(unittest.TestCase):
    def test_state_priority_empty_unselected(self):
        self.assertEqual(combine('F',{'M':'FAILED'},[]),'F')
        self.assertEqual(combine('T',{'M':'FAILED'},['M']),'FAILED')
        self.assertEqual(combine('F',{'M':'U'},['M']),'U')
        self.assertEqual(combine('T',{'M':'U'},['M']),'T')
        with self.assertRaises(ValueError):combine('EMPTY_MODEL',{},[])
    def test_only_base_feasible(self):
        b,ms,ix=fixture()
        for m in ms[:64]:ix[m['sample_id']]['conditions']={c:'U' for c in CANDIDATES}
        cs,w,_=select(b,ms,ix);self.assertEqual(w['set_id'],'S0');self.assertEqual(sum(c['feasible'] for c in cs),1)
    def test_increment_and_tie(self):
        b,ms,ix=fixture()
        for m in ms:
            if m['identity']=='EFFECTIVE_INTERVENTION':ix[m['sample_id']]['conditions']={c:'T' for c in CANDIDATES}
        cs,w,_=select(b,ms,ix);self.assertEqual(w['set_id'],'M');self.assertEqual(w['rule_count'],8);self.assertEqual(w['complexity'],16)
        self.assertIn('RULE_BUDGET',next(c for c in cs if c['set_id']=='MW')['reasons'])
    def test_all_fail_not_feasible_empty(self):
        b,ms,ix=fixture()
        for m in ms[:64]:ix[m['sample_id']]['base_states']['base']='FAILED'
        cs,w,_=select(b,ms,ix);self.assertIsNone(w);self.assertFalse(cs[0]['feasible'])
    def test_four_normal_budgets_independent(self):
        b,ms,ix=fixture()
        for co,n in [('mtc_discovery',32),('pilot18',1),('b2b42',2),('resource54',3)]:
            clone=copy.deepcopy(ix)
            for m in [m for m in ms if m['identity']=='NORMAL' and m['cohort']==co][:n]:clone[m['sample_id']]['conditions']['M']='T'
            result,_=score(b,['M'],ms,clone);self.assertIn('NORMAL_ALARM_BUDGET:'+co,result['reasons'])
    def test_unknown_union_not_individual_coverage(self):
        b,ms,ix=fixture()
        for m in ms[:50]:ix[m['sample_id']]['base_states']['base']='U'
        for m in ms[50:91]:ix[m['sample_id']]['conditions']['M']='U'
        result,_=score(b,['M'],ms,ix)
        self.assertEqual(result['candidate_quality']['M']['defined'],589)
        self.assertEqual(result['normals']['mtc_discovery']['defined'],539)
        self.assertIn('MODEL_DEFINED_COVERAGE:mtc_discovery',result['reasons'])
        self.assertNotIn('CANDIDATE_COVERAGE:M',result['reasons'])
    def test_evaluation_perturbation_cannot_reach_score(self):
        b,ms,ix=fixture();cs,w,_=select(b,ms,ix)
        evaluation=dict(sample_id='reserved',role='historical_evaluation',cohort='mtc_reserved_validation',identity='NORMAL',family=None)
        ix['reserved']=dict(base_states={'base':'FAILED'},conditions={'M':'T','W':'U','B':'FAILED'})
        cs2,w2,_=select(b,ms+[evaluation],ix);self.assertEqual(cs,cs2);self.assertEqual(w,w2)
        with self.assertRaisesRegex(ValueError,'EVALUATION_MEMBER'):score(b,[],[evaluation],ix)
    def test_membership_missing_duplicate_wrong_identity(self):
        m=dict(sample_id='x',cohort='c',role='selection',identity='NORMAL')
        r=dict(m,base_states={'b':'F'},app_states={'b':'F'},C1='F',conditions={'M':'F','W':'F','B':'F'})
        validate([m],[r],['b'],1)
        for inputs in ([r,r],[],[dict(r,identity='EFFECTIVE_INTERVENTION')],[dict(r,base_states={})],[dict(r,conditions={'M':'F'})]):
            with self.assertRaises(ValueError):validate([m],inputs,['b'],1)
    def test_resource_dependencies_and_invalid_values(self):
        import rx_sources as s
        c=s.legacy().rc
        r=dict(features={c.N:2,c.A:2,c.B:4},field_status={f:'observed' for f in (c.N,c.A,c.B)},field_quality={f:'observed_value' for f in (c.N,c.A,c.B)},binding={'app':True,'browser':True,'pair':True,'app_session_id':'fixture'})
        out=c.evaluate(r);self.assertEqual(out[CANDIDATES['M']]['state'],'T');self.assertEqual(out[CANDIDATES['B']]['state'],'F')
        r['field_errors']={c.N:'bad native'};out=c.evaluate(r)
        self.assertEqual(out[CANDIDATES['W']]['state'],'T');self.assertEqual(out[CANDIDATES['M']]['state'],'FAILED')
        r['binding']['app']=False;r['binding']['pair']=False
        self.assertEqual(c.evaluate(r)[CANDIDATES['B']]['state'],'F')
        for value in (True,0,float('nan'),float('inf')):
            r['features'][c.B]=value;self.assertEqual(c.evaluate(r)[CANDIDATES['B']]['state'],'U')
    def test_source_model_identity(self):
        import rx_sources as s
        models,locks=s.freeze_models();self.assertEqual(len(models),3)
        self.assertEqual([(m['rule_count'],m['complexity']) for m in models],[(7,14),(7,14),(6,12)])
    def test_real_evaluation_values_do_not_change_selection(self):
        if not (HERE/'results/models.json').exists():self.skipTest('run once before saved-data regression')
        models=read(HERE/'results/models.json');ms=rows(HERE/'results/members.jsonl');ix=index(rows(HERE/'results/inputs.jsonl'))
        mutated=copy.deepcopy(ix)
        for m in ms:
            if m['role']=='historical_evaluation':
                mutated[m['sample_id']]['base_states']={k:'FAILED' for k in mutated[m['sample_id']]['base_states']}
                mutated[m['sample_id']]['conditions']={'M':'T','W':'T','B':'FAILED'}
        saved=read(HERE/'results/candidate_checks.json')
        for model in models:
            b=read(ROOT/model['base_ref']);cs,w,_=select(b,ms,mutated)
            self.assertEqual(cs,[c for c in saved if c['base_model_id']==model['base_model_id']])
            self.assertEqual(w['set_id'],model['selected_set'])
    def test_current_pair_wrong_binding_and_endpoint_isolation(self):
        import rx_sources as s
        p=s.prepare_v16(None,None,None)
        self.assertFalse(p['record']['binding']['pair'])
        self.assertTrue(all(v['state']=='FAILED' for v in s.legacy().rc.evaluate(p['record']).values()))
        a,b,prov=s.raw_v16(dict(cohort='resource54',sample_id='resource54:RP001'))
        bad=dict(prov,app_receipt_id='synthetic_wrong_receipt');p=s.prepare_v16(a,b,bad)
        result=s.legacy().rc.evaluate(p['record'])
        self.assertEqual(result[CANDIDATES['M']]['state'],'FAILED')
        self.assertEqual(result[CANDIDATES['W']]['state'],'FAILED')
        self.assertEqual(result[CANDIDATES['B']]['state'],'F')
        p=s.prepare_v16(None,b,None)
        self.assertEqual(s.legacy().rc.evaluate(p['record'])[CANDIDATES['B']]['state'],'F')
    def test_current_entry_empty_extension_and_unselected_failure(self):
        from rx_inference import predict_prepared
        import rx_sources as s
        if not (HERE/'results/models.json').exists():self.skipTest('models not yet selected')
        m=read(HERE/'results/models.json')[0]
        prepared={'app':None,'record':{'binding':{'app':False}},'pair':{}}
        component={'C1':{'state':'U'},'resources':{name:{'state':'FAILED'} for name in CANDIDATES.values()}}
        with patch.object(s.legacy().re,'predict',return_value={'state':'F'}):
            actual=predict_prepared(m,prepared,component);self.assertEqual(actual['state'],'U');self.assertEqual(actual['base_state'],'U')
            changed=dict(m,extensions=['M'])
            self.assertEqual(predict_prepared(changed,prepared,component)['state'],'FAILED')
    def test_saved_summary_prohibits_computation_and_network(self):
        if not (HERE/'results/models.json').exists():self.skipTest('saved outputs required')
        from summarize import summarize
        import socket
        old=sys.getprofile()
        def guard(frame,event,arg):
            if event=='call' and frame.f_code.co_filename.startswith(str(ROOT)):
                name=frame.f_code.co_name
                if name in ('select','score','predict_current','predict_prepared','evaluate','collect','train') or name=='fit' or name.startswith('fit_'):raise AssertionError('SUMMARY_COMPUTATION:'+name)
        with tempfile.TemporaryDirectory() as td,patch.object(socket,'socket',side_effect=AssertionError('SUMMARY_NETWORK')):
            try:sys.setprofile(guard);summarize(HERE/'results',td)
            finally:sys.setprofile(old)
            expected=HERE/'results/summary'
            self.assertEqual({p.name for p in expected.iterdir()},{p.name for p in Path(td).iterdir()})
            for p in expected.iterdir():self.assertEqual(p.read_bytes(),(Path(td)/p.name).read_bytes())
if __name__=='__main__':unittest.main()
