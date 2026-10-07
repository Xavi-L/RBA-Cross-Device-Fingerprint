from pathlib import Path
import sys,unittest,copy,math
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import conditions as c
import data as d
from effects import qualify

def rec(n=2,a=2,b=2,ac=1,bc=1):
    f=dict(zip([c.N,c.A,c.B,c.AC,c.BC],[n,a,b,ac,bc]));return {'features':f,'field_status':dict.fromkeys(f,'observed'),'field_quality':dict.fromkeys(f,'observed_value'),'binding':dict(app=True,browser=True,pair=True,app_session_id='real-app')}
class Tests(unittest.TestCase):
    def test_exact_envelope_and_boolean_nonfinite_zero(self):
        for n,b,expected in [(2,2,'F'),(2,4,'T'),(2.01,4,'F'),(.25,.5,'T'),(.24,4,'U')]:self.assertEqual(c.evaluate(rec(n=n,b=b))['R_NATIVE_BROWSER_MEMORY']['state'],expected)
        for value in [True,False,0,-1,float('nan'),float('inf'),'4',None]:
            self.assertEqual(c.evaluate(rec(b=value))['D_BROWSER_MEMORY8']['state'],'U')
    def test_cpu_integer_only(self):
        for value in [True,0,1.5,float('inf')]:self.assertEqual(c.evaluate(rec(bc=value))['D_CPU_DIFFERENCE']['state'],'U')
    def test_real_normal_counterexample_stays_true(self):self.assertEqual(c.evaluate(rec(n=2,b=4))['R_NATIVE_BROWSER_MEMORY']['state'],'T')
    def test_single_side_and_native_web_dependency_isolation(self):
        r=rec();r['binding']['browser']=False;r['binding']['pair']=False
        z=c.evaluate(r);self.assertEqual(z['R_APP_MEMORY']['state'],'F');self.assertEqual(z['D_APP_MEMORY8']['state'],'F');self.assertEqual(z['R_WEB_MEMORY_DIFFERENCE']['state'],'FAILED')
        r=rec();del r['features'][c.A];self.assertEqual(c.evaluate(r)['R_NATIVE_BROWSER_MEMORY']['state'],'F')
        r=rec();del r['features'][c.N];self.assertEqual(c.evaluate(r)['R_WEB_MEMORY_DIFFERENCE']['state'],'F')
        r=rec();r['binding']['app']=False;self.assertEqual(c.evaluate(r)['D_BROWSER_MEMORY8']['state'],'F')
    def test_missing_binding_is_not_missing_operand(self):
        r=rec();r['binding']['pair']=False;self.assertEqual(c.evaluate(r)['R_NATIVE_BROWSER_MEMORY']['state'],'FAILED')
        r=rec();del r['features'][c.B];self.assertEqual(c.evaluate(r)['R_NATIVE_BROWSER_MEMORY']['state'],'U')
    def test_new_relation_does_not_call_same_app_evaluator(self):
        old=c.original.evaluate
        def app_only(r):
            self.assertNotIn(c.B,r['features']);return old(r)
        c.original.evaluate=app_only
        try:self.assertEqual(c.evaluate(rec(b=16))['R_NATIVE_BROWSER_MEMORY']['state'],'T')
        finally:c.original.evaluate=old
    def test_no_labels_targets_future_or_device_used(self):
        r=rec();expected=c.evaluate(r);r.update(scenario='x',phase='post',target=99,label='attack',device_id='new',future={'value':16});self.assertEqual(expected,c.evaluate(r))
    def test_duplicate_and_missing_capture_retained(self):
        plan={'device_manifest_id':'x'};slot={'sample_id':'x'}
        for duplicate in [False,True]:
            item=d.bind(Path('/tmp'),plan,slot,None,duplicate);self.assertTrue(all(v['state']=='FAILED' for v in c.evaluate(item['record']).values()))
    def test_mem4_no_effect_downward_and_cpu_only(self):
        for before,current,cpu_before,cpu_current,expected,effective in [(4,4,1,1,'no_observable_change',False),(8,4,1,1,'memory_only_changed',True),(16,16,1,48,'cpu_only_changed',True)]:
            target={'deviceMemory':current};applied=['deviceMemory']
            if cpu_current==48:target['hardwareConcurrency']=48;applied+=['hardwareConcurrency']
            cap={'result':'COMPLETED','control_route':{'targets':target},'app_control':{'applied':applied},'app_before':{'resources':{'deviceMemory':{'status':'observed','value':before},'hardwareConcurrency':{'status':'observed','value':cpu_before}}},'app_during':{'resources':{'deviceMemory':{'value':current},'hardwareConcurrency':{'value':cpu_current}}},'restoration':[{'endpoint':'app','status':'FAILED'}]}
            item={'record':rec(a=current,ac=cpu_current),'app':None,'browser':None};s={'scenario':'A_APP_RESOURCE','phase':'change'};q=qualify(s,cap,item)
            self.assertEqual(q['subtype'],expected);self.assertEqual(q['effective'],effective)
            if effective:self.assertEqual(q['identity'],'CONTROLLED_INTERVENTION')
    def test_physical_bad_line_and_duplicate_raw_id(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);(run/'data').mkdir();p=run/'data/raw_expanded_payloads.jsonl'
            p.write_text('{"session_id":"one"}\nBROKEN\n{"session_id":"three"}\n')
            self.assertEqual(d.raw_ref(run,{'file':'data/raw_expanded_payloads.jsonl','line':3},p.name)['session_id'],'three')
            with self.assertRaises(ValueError):d.raw_ref(run,{'file':'data/raw_expanded_payloads.jsonl','line':2},p.name)
            d.archive.cache_clear();p.write_text('{"session_id":"same"}\n{"session_id":"same"}\n')
            with self.assertRaises(ValueError):d.raw_ref(run,{'file':'data/raw_expanded_payloads.jsonl','line':1},p.name)
            d.archive.cache_clear()
    def test_unrelated_field_binding_error_is_isolated(self):
        r=rec();r['field_errors']={c.N:'WRONG_FIELD_SESSION'};z=c.evaluate(r)
        self.assertEqual(z['R_APP_MEMORY']['state'],'FAILED');self.assertEqual(z['R_NATIVE_BROWSER_MEMORY']['state'],'FAILED');self.assertEqual(z['R_WEB_MEMORY_DIFFERENCE']['state'],'F');self.assertEqual(z['D_BROWSER_MEMORY8']['state'],'F')
    def test_selected_projection_matches_original_encoder_input(self):
        from evaluate import models,required_raw_atoms
        run=Path(__file__).parent/'private_runs/formal01'
        if not (run/'captures.jsonl').exists():self.skipTest('local current-stage raw unavailable')
        plan=d.read(run/'plan.json');caps=d.rows(run/'captures.jsonl');raw=d.raw_ref(run,caps[0]['archives']['app'],'raw_expanded_payloads.jsonl');sid=raw['session_id']
        from hybridguard_agent.research import app177_ablation as ab
        for scheme,fold,model,_ in models():
            complete=d.APP.adapt_raw(raw,sid,'same_current_raw',16,scheme)['raw']
            partial=d.APP.adapt_raw(raw,sid,'same_current_raw',16,scheme,required=required_raw_atoms(model))['raw']
            names=[a.atom_id for a in model.atoms]
            self.assertEqual(ab.encode(complete,model.encoder,names),ab.encode(partial,model.encoder,names))
            self.assertTrue(all(n in complete for n in required_raw_atoms(model)))
    def test_fixed_matrix_order(self):
        p=d.read(Path(__file__).parent/'PLAN.json');self.assertEqual(len(p['positions']),54);self.assertEqual(len({s['sample_id'] for s in p['positions']}),54)
        self.assertEqual([s['phase'] for s in p['positions'][:3]],['pre','change','post']);self.assertEqual(p['fit_calls'],0)
if __name__=='__main__':unittest.main()

class SavedSummaryTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).parent/'results/model_predictions.jsonl').exists(),'frozen evaluation not complete yet')
    def test_summary_runs_with_prediction_and_network_disabled(self):
        import tempfile,socket
        from unittest.mock import patch
        import summarize
        from hybridguard_agent.research import app177_ablation as ab
        with tempfile.TemporaryDirectory() as tmp,patch.object(socket,'socket',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(ab,'predict_current',side_effect=AssertionError('PREDICT_FORBIDDEN')),patch.object(d.APP.full_engine,'predict_current',side_effect=AssertionError('PREDICT_FORBIDDEN')),patch.object(ab,'fit',side_effect=AssertionError('FIT_FORBIDDEN')):
            s=summarize.run(output=Path(tmp));self.assertEqual(s['formal_positions'],54);self.assertEqual(s['summary_prediction_calls'],0)
