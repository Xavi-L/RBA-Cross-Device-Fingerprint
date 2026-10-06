"""Failure and scope tests; fake values below are tests, never collection evidence."""
import copy, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import evaluate as e
import summarize
class SavedSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir=HERE/'private_runs/engineering/smoke01'
        if not cls.run_dir.exists():raise unittest.SkipTest('Local engineering raw evidence not published')
        cls.plan=e.read(cls.run_dir/'plan.json');cls.slots=cls.plan['positions'];cls.caps=e.lines(cls.run_dir/'captures.jsonl')
    def item(self,n=0,cap=None):return e.bind(self.run_dir,self.plan,self.slots[n],copy.deepcopy(cap or self.caps[n]))
    def test_real_same_stage_has_244_fields(self):
        x=self.item();self.assertFalse(x['pair']['errors']);self.assertEqual(len(x['pair']['features']),244)
    def test_missing_browser_retains_app(self):
        c=copy.deepcopy(self.caps[0]);del c['archives']['browser'];x=self.item(cap=c)
        self.assertIsNotNone(x['raw']);self.assertFalse(x['app_errors']);self.assertEqual(e.b2.cond.evaluate('C1',x['pair'])['state'],'FAILED')
    def test_missing_app_retains_browser_and_d2(self):
        c=copy.deepcopy(self.caps[0]);del c['archives']['app'];x=self.item(cap=c)
        self.assertIsNotNone(x['browser_raw']);self.assertEqual(e.b2.cond.evaluate('D2',x['pair'])['state'],'F');self.assertEqual(e.b2.cond.evaluate('C2',x['pair'])['state'],'FAILED')
    def test_wrong_ticket_is_not_nearest_time_join(self):
        c=copy.deepcopy(self.caps[0]);c['ticket']['pair_id']='another-pair';x=self.item(cap=c)
        self.assertIsNotNone(x['raw']);self.assertTrue(x['browser_errors'])
    def test_wrong_stage_does_not_reuse_raw(self):
        x=e.bind(self.run_dir,self.plan,self.slots[1],copy.deepcopy(self.caps[0]));self.assertIsNone(x['raw']);self.assertEqual(e.b2.cond.evaluate('D2',x['pair'])['state'],'FAILED')
    def test_duplicate_capture_identity_fails_explicitly(self):
        x=e.bind(self.run_dir,self.plan,self.slots[0],self.caps[0],True);self.assertIsNone(x['raw']);self.assertIn('DUPLICATE_CAPTURE_ID',x['pair']['errors'])
    def test_duplicate_app_rows_do_not_invalidate_browser_only_check(self):
        c=copy.deepcopy(self.caps[0]);c['endpoint_counts']['app']=2;x=self.item(cap=c)
        self.assertIsNone(x['raw']);self.assertEqual(e.b2.cond.evaluate('D2',x['pair'])['state'],'F')
    def test_wrong_physical_reference_fails_only_affected_side(self):
        c=copy.deepcopy(self.caps[0]);c['archives']['app']['line']=2;x=self.item(cap=c)
        self.assertIsNone(x['raw']);self.assertIsNotNone(x['browser_raw'])
    def qualify(self,n,cap=None,item=None):
        return e.qualify(self.slots[n],cap or self.caps[n],item or self.item(n),self.item(n//3*3),self.item(n//3*3+2))
    def test_all_four_runtime_scopes_proven_in_actual_smoke(self):
        for n in [1,4,7,10]:
            q=self.qualify(n);self.assertTrue(q['fully_qualified']);self.assertEqual(q['identity'],'CONTROLLED_INTERVENTION');self.assertTrue(q['held_through_both_receipts'])
    def test_restore_failure_does_not_erase_effective_intervention(self):
        c=copy.deepcopy(self.caps[1]);c['restoration'][0]['status']='FAILED';q=self.qualify(1,cap=c)
        self.assertEqual(q['identity'],'CONTROLLED_INTERVENTION');self.assertFalse(q['fully_qualified'])
    def test_no_effect_is_not_successful_intervention(self):
        q=self.qualify(1,item=self.item(0));self.assertEqual(q['operation_effect'],'NO_OBSERVABLE_EFFECT');self.assertFalse(q['fully_qualified'])
    def test_early_rollback_fails_interval_proof(self):
        c=copy.deepcopy(self.caps[1]);c['control_end']=c['control_begin'];self.assertFalse(self.qualify(1,cap=c)['fully_qualified'])
    def test_non_target_change_fails_scope(self):
        x=self.item(1);x['pair']['features']['browser.web_data.navigator_layer.language']='de-DE';self.assertFalse(self.qualify(1,item=x)['fully_qualified'])
    def test_not_executed_normal_setting_is_not_attack(self):
        s={**self.slots[7],'scenario':'L_BROWSER_LANG'};c=copy.deepcopy(self.caps[7]);c['control_installed']=False;c['setting']['status']='NOT_EXECUTED'
        q=e.qualify(s,c,self.item(7),self.item(6),self.item(8));self.assertEqual(q['intended_identity'],'normal');self.assertEqual(q['identity'],'UNCONFIRMED')
    def test_normal_browser_preference_stays_normal_when_same_operands_as_attack(self):
        s={**self.slots[7],'scenario':'L_BROWSER_LANG'};c=copy.deepcopy(self.caps[7]);c['control_installed']=False;c['setting']['status']='EXECUTED'
        c['setting']['operation']={'durability_verified':True}
        q=e.qualify(s,c,self.item(7),self.item(6),self.item(8));self.assertEqual(q['identity'],'NORMAL');self.assertTrue(q['fully_qualified'])
    def test_normal_setting_no_observable_effect_is_distinct(self):
        s={**self.slots[7],'scenario':'L_BROWSER_LANG'};c=copy.deepcopy(self.caps[7]);c['control_installed']=False;c['setting']['status']='EXECUTED'
        q=e.qualify(s,c,self.item(6),self.item(6),self.item(8));self.assertEqual(q['identity'],'NORMAL');self.assertEqual(q['operation_effect'],'NO_OBSERVABLE_EFFECT')
    def test_app_prediction_never_receives_browser_projection(self):
        # Check the original real inference entry point argument boundary without fitting.
        x=self.item();seen=[]
        def compile_raw(raw,sid,ref):seen.append(copy.deepcopy(raw));return {'raw':{'current_app_only':True},'candidate_inputs':{}},{'features':{},'field_status':{},'field_quality':{},'acquisition_time':{}}
        class Model:atoms=[];model_id='fixture'
        with patch.object(e.b2,'compile_app',compile_raw),patch.object(e.b2.selection,'predict_current',return_value={'decision':'NO_ALERT','logical_state':'F'}) as predict:
            e.b2.predict_item(x,Model());x['pair']['features']['browser.web_data.navigator_layer.language']='different';e.b2.predict_item(x,Model())
            self.assertEqual(seen[0],seen[1]);self.assertEqual(predict.call_args.args[2],{'current_app_only':True})
class FrozenSemanticsTests(unittest.TestCase):
    def pair(self,a,b):
        f={'app.web_data.navigator_layer.language':a,'browser.web_data.navigator_layer.language':b}
        return {'features':f,'field_status':dict.fromkeys(f,'observed'),'field_quality':dict.fromkeys(f,'observed_value'),'errors':[]}
    def test_region_blindness_is_not_equivalence(self):
        p=self.pair('en-US','en-GB');self.assertEqual(e.b2.cond.evaluate('C2',p)['state'],'T');self.assertEqual(e.b2.cond.evaluate('C3',p)['state'],'F')
    def test_script_blindness(self):
        p=self.pair('zh-Hans','zh-Hant');self.assertEqual(e.b2.cond.evaluate('C2',p)['state'],'T');self.assertEqual(e.b2.cond.evaluate('C3',p)['state'],'F')
    def test_parser_unsupported_is_unknown_not_failed(self):
        self.assertEqual(e.b2.cond.evaluate('C2',self.pair('zh-RCN','en-US'))['state'],'U')
    def test_missing_status_is_unknown(self):
        p=self.pair('en-US','fr-FR');p['field_status']={};self.assertEqual(e.b2.cond.evaluate('C2',p)['state'],'U')
    def test_frozen_conditions_models_and_collectors(self):
        lock=e.read(HERE/'FROZEN.json')
        repairs=e.read(HERE/'ENGINEERING_REPAIR.json')['changed_collection_files'] if (HERE/'ENGINEERING_REPAIR.json').exists() else {}
        self.assertLessEqual(set(repairs),{'deliverables/cross_endpoint_matched_controls_v1/settings_control.py'})
        for f,h in {**lock['files'],**lock['collection_files']}.items():
            if f in repairs:
                self.assertEqual(e.hashlib.sha256((e.ROOT/repairs[f]['initial_copy']).read_bytes()).hexdigest(),h)
                h=repairs[f]['repaired_sha256']
            self.assertEqual(e.hashlib.sha256((e.ROOT/f).read_bytes()).hexdigest(),h,f)
        models,_=e.b2.load_models();self.assertEqual([m.model_id for m in models],e.b2.IDS)
    def test_saved_summary_duplicate_not_equal_count(self):
        plan=e.read(HERE/'PLAN.json');slots=plan['positions'];ps=[{'meta':s} for s in slots]
        ap=[{'meta':s,'prediction':{'model_id':m,'decision':'NO_ALERT','logical_state':'F'}} for s in slots for m in summarize.IDS]
        cp=[{'meta':s,'condition_id':c,'state':'F'} for s in slots for c in summarize.CS]
        summarize.validate(plan,ps,ap,cp);cp[-1]=cp[-2]
        with self.assertRaises(ValueError):summarize.validate(plan,ps,ap,cp)
    def test_summary_module_cannot_import_runtime(self):
        import ast
        tree=ast.parse((HERE/'summarize.py').read_text());names=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):names += [a.name.split('.')[0] for a in n.names]
            elif isinstance(n,ast.ImportFrom):names.append(n.module.split('.')[0])
        self.assertLessEqual(set(names),{'argparse','csv','json','collections','pathlib'})
    def test_repair_selection_is_six_predeclared_positions_not_best_score(self):
        if not (HERE/'ATTEMPT_SELECTION.json').exists():self.skipTest('No engineering repair')
        a=e.read(HERE/'ATTEMPT_SELECTION.json');plan=e.read(HERE/'PLAN.json')
        expected={s['sample_id'] for s in plan['positions'] if s['scenario']=='L_BROWSER_LANG'}
        self.assertEqual(set(a['replacement_sample_ids']),expected);self.assertEqual(len(expected),6);self.assertTrue(a['selected_before_repair_results'])
if __name__=='__main__':unittest.main()
